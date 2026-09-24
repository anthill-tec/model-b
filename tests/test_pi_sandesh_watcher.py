"""Behaviour tests for the Model B Pi package's Sandesh watcher supervisor,
``pi-package/extensions/sandesh-watcher.ts`` (CR-MDB-029 \u00a7S2).

The extension is loaded by ``tests/fixtures/pi_watcher_harness.mjs``, which
uses the ``jiti`` mechanism Pi's own loader uses (the CR-MDB-030 \u00a7S8
pattern, ``tests/test_pi_hook_runtime.py``). The harness hands the factory
a recording fake ``pi`` and runs a JSON step script against the registered
``sandesh_watcher`` tool and ``/watcher`` command. The extension's real
child processes are a fake ``sandesh`` (a POSIX ``sh`` script written per
test into a temp ``bin/`` placed FIRST on ``PATH``). The real ``sandesh`` is
never run. ``HOME`` and ``PI_CODING_AGENT_DIR`` are sandboxed temp dirs.

The fake ``sandesh`` takes one plan line per launch; the last line repeats.
It appends its pid to ``launches.log``, its argv to ``argv.<n>`` and the
``PYTHONUNBUFFERED`` it was given to ``env.<n>``, prints
``[notify] watching <to> in <project> (pid <pid>)`` (the Sandesh 0.3.5
banner), then acts:

- ``exit N`` -- exit ``N`` at once;
- ``mail IDS`` -- print Sandesh 0.3.5's exit-0 lines for the comma-separated
  ids (``[notify] <time> \u2709 N unread 'to' message(s): [a, b]`` and the
  ``WAKE`` fetch line), then exit ``0``;
- ``signal TERM`` -- kill itself with ``SIGTERM``;
- ``alive`` -- ``exec sleep 30``, keeping its pid;
- ``late`` -- sleep 0.7 s and touch ``banner.marker`` BEFORE printing the
  banner, then ``exec sleep 30``;
- ``hold N`` -- wait until ``release.<n>`` exists, then exit ``N``;
- ``nobanner N`` -- print an error on stderr and exit ``N`` without a banner.

Any plan line may be prefixed ``nomail`` (``nomail exit 0``, ``nomail mail 7``):
the fake then prints Sandesh 0.3.5's poll line ``[notify] <time> no 'to' mail
-- next check in 30s`` right after the banner, before acting on the rest.

Like Sandesh's own ``print()`` into a pipe, the fake BUFFERS its stdout
unless ``PYTHONUNBUFFERED`` is set: buffered, nothing reaches the pipe until
it exits, so a ``sleep``-ing child never shows its banner (CR-MDB-029 \u00a7S2,
amended at C5, VERIFY finding 1). ``drive`` removes the variable from the
harness's environment, so only the extension can supply it.

Orchestrator rulings (2026-09-24, on the cycle-112 RED design), as amended
by the C5 user ruling (the watcher runs at all times):

- W -- the 3-timeouts-in-a-minute cap. The AC cap test needs no clock seam,
  because the fake exits in milliseconds. A NEGATIVE test is added too:
  ``2`` exits spread more than a minute apart do NOT surface and keep
  relaunching. Without it, a cap on three timeouts in TOTAL would pass, and
  that watcher would die after three normal multi-hour timeouts. The
  harness fakes time by overriding ``Date.now`` before load, so GREEN must
  use ``Date.now()`` for the window.
- C -- "surfaced" is observed on three channels: ``pi.sendUserMessage``,
  ``pi.sendMessage`` and ``ctx.ui.notify``. Expectations per exit:
  - ``0`` -- exactly one ``sendUserMessage`` naming the address, the ids
    Sandesh printed and ``sandesh fetch --project <p> --to '<address>'``
    (address shell-quoted), and a relaunch at once; a relaunch exiting ``0``
    with the SAME ids wakes nothing and retries every 30 s (observed through
    the harness's ``timeScale`` timer wrapper, which records the requested
    delay and runs it scaled); NEW ids wake again;
  - ``2`` -- exactly one relaunch and nothing on any channel;
  - ``1``/``3``/``4``/``5``/signal -- exactly one surfacing whose text holds
    the code and a meaning keyword, and no relaunch. The keywords are:
    ``1`` usage|configuration, ``3`` tombston, ``4`` evict,
    ``5`` already|dedup, SIGTERM signal + (SIGTERM|15|143);
  - three ``2`` exits -- exactly one surfacing and exactly three launches.
- T -- tool and command results:
  - ``start`` answers /ready/i naming the address, and resolves only once
    the banner is out (the fake's marker exists when ``execute`` resolves);
  - a second ``start`` answers /already|running/i and spawns nothing;
  - ``stop`` (the tool, and ``/watcher stop``) ends the child's pid within
    3 s;
  - ``status`` / ``/watcher status`` names the address while the watcher
    runs;
  - the child's argv is exactly ``notify --to <addr> --project <p>``.
- H -- a new fixture, this test file, and an exact ``pi.extensions`` pin in
  ``tests/test_pi_package.py::PiPackageManifestTest``. No existing test is
  migrated.

Stdlib only.
"""

import contextlib
import json
import os
import re
import shutil
import signal
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.test_pi_hook_runtime import _require_loader_env

REPO_ROOT = Path(__file__).resolve().parent.parent
EXTENSION = REPO_ROOT / "pi-package" / "extensions" / "sandesh-watcher.ts"
HARNESS_MJS = REPO_ROOT / "tests" / "fixtures" / "pi_watcher_harness.mjs"

ADDRESS = "Mainline - WatcherTest"
PROJECT = "WatcherTest"
FETCH = f"sandesh fetch --project {PROJECT} --to '{ADDRESS}'"
RETRY_MS = 30_000
#: The retry wait is run at 1/100 of what the extension asks for.
_TIME_SCALE = 0.01

_HARNESS_BUDGET_S = 45.0
_SETTLE_MS = 2000

FAKE_SANDESH = r"""#!/bin/sh
# Fake `sandesh` for CR-MDB-029 S2 tests -- never the real one.
dir="$FAKE_SANDESH_DIR"
log="$dir/launches.log"
touch "$log"
n=$(( $(wc -l < "$log") + 1 ))
echo "$$" >> "$log"
: > "$dir/argv.$n"
for a in "$@"; do printf '%s\n' "$a" >> "$dir/argv.$n"; done
printf '%s\n' "${PYTHONUNBUFFERED-<unset>}" > "$dir/env.$n"
to=""; project=""
while [ $# -gt 0 ]; do
  case "$1" in
    --to) to="$2"; shift 2 ;;
    --project) project="$2"; shift 2 ;;
    *) shift ;;
  esac
done
lines=$(wc -l < "$dir/plan")
if [ "$n" -le "$lines" ]; then line=$(sed -n "${n}p" "$dir/plan"); else line=$(sed -n "${lines}p" "$dir/plan"); fi
set -- $line
nomail=""
if [ "$1" = nomail ]; then nomail=1; shift; fi
# Sandesh's print() into a pipe is block-buffered unless PYTHONUNBUFFERED is
# set: buffered, nothing reaches the pipe until the process exits (flush).
buf="$dir/stdout.$n"
say() {
  if [ -n "${PYTHONUNBUFFERED:-}" ]; then printf '%s\n' "$1"; else printf '%s\n' "$1" >> "$buf"; fi
}
flush() { if [ -f "$buf" ]; then cat "$buf"; fi; }
banner() {
  say "[notify] watching $to in $project (pid $$)"
  if [ -n "$nomail" ]; then say "[notify] 12:00:00 no 'to' mail — next check in 30s"; fi
}
case "$1" in
  exit) banner; flush; exit "$2" ;;
  mail)
    banner
    count=$(printf '%s\n' "$2" | tr ',' '\n' | wc -l)
    list=$(printf '%s' "$2" | sed 's/,/, /g')
    say "[notify] 12:00:00 ✉ $((count)) unread 'to' message(s): [$list]"
    say "[notify] WAKE — fetch with: sandesh fetch --project $project --to '$to'"
    flush; exit 0 ;;
  signal) banner; kill -"$2" $$; sleep 5; exit 99 ;;
  alive) banner; exec sleep 30 ;;
  late) sleep 0.7; touch "$dir/banner.marker"; banner; exec sleep 30 ;;
  hold)
    banner
    i=0
    while [ ! -e "$dir/release.$n" ] && [ $i -lt 300 ]; do sleep 0.1; i=$((i+1)); done
    flush; exit "$2" ;;
  nobanner) echo "error: usage: sandesh notify --to ADDR --project P" >&2; exit "$2" ;;
  *) echo "fake sandesh: bad plan line: $line" >&2; exit 97 ;;
esac
"""


def _start(**extra) -> dict:
    return {"op": "tool", "params": {"action": "start", "address": ADDRESS, "project": PROJECT}, **extra}


def _stop() -> dict:
    return {"op": "tool", "params": {"action": "stop", "address": ADDRESS}}


class SandeshWatcherTestCase(unittest.TestCase):
    """Sandbox + drive fixture: a fake ``sandesh`` first on ``PATH``, a temp
    ``HOME`` and ``PI_CODING_AGENT_DIR``, the extension loaded by jiti."""

    @classmethod
    def setUpClass(cls):
        env = _require_loader_env()
        cls.node_bin = env["node_bin"]
        cls.jiti_mjs = env["jiti_mjs"]
        cls.pi_pkg_root = env["pi_pkg_root"]

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="modelb-pi-watcher-"))
        self.bin = self.tmp / "bin"
        self.fake_dir = self.tmp / "fake"
        for d in (self.bin, self.fake_dir, self.tmp / "home", self.tmp / "pi-agent"):
            d.mkdir()
        shim = self.bin / "sandesh"
        shim.write_text(FAKE_SANDESH, encoding="utf-8")
        shim.chmod(0o755)
        self.addCleanup(self._cleanup)

    def _cleanup(self):
        for pid in self._launch_pids():
            try:
                cmdline = Path(f"/proc/{pid}/cmdline").read_bytes()
            except OSError:
                continue
            if b"sleep" in cmdline or b"sandesh" in cmdline:
                with contextlib.suppress(OSError):
                    os.kill(pid, signal.SIGKILL)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _launch_pids(self) -> list[int]:
        log = self.fake_dir / "launches.log"
        if not log.is_file():
            return []
        return [int(x) for x in log.read_text().split() if x.strip()]

    def argv_of(self, launch: int) -> list[str]:
        return (self.fake_dir / f"argv.{launch}").read_text(encoding="utf-8").splitlines()

    def env_of(self, launch: int) -> str:
        """The ``PYTHONUNBUFFERED`` value launch ``launch`` was given."""
        return (self.fake_dir / f"env.{launch}").read_text(encoding="utf-8").strip()

    def drive(self, plan: list[str], steps: list[dict], fake_clock: bool = False,
              time_scale: float | None = None) -> dict:
        (self.fake_dir / "plan").write_text("\n".join(plan) + "\n", encoding="utf-8")
        env = dict(os.environ)
        # Only the extension may make the child unbuffered.
        env.pop("PYTHONUNBUFFERED", None)
        env.update({
            "PATH": f"{self.bin}{os.pathsep}{env.get('PATH', '')}",
            "HOME": str(self.tmp / "home"),
            "PI_CODING_AGENT_DIR": str(self.tmp / "pi-agent"),
            "FAKE_SANDESH_DIR": str(self.fake_dir),
        })
        scenario = {
            "fakeClock": fake_clock,
            "timeScale": time_scale,
            "fakeDir": str(self.fake_dir),
            "markerPath": str(self.fake_dir / "banner.marker"),
            "steps": steps,
        }
        try:
            result = subprocess.run(
                [self.node_bin, str(HARNESS_MJS), str(EXTENSION), str(self.jiti_mjs), str(self.pi_pkg_root)],
                input=json.dumps(scenario), capture_output=True, text=True,
                timeout=_HARNESS_BUDGET_S, env=env, cwd=str(self.tmp),
            )
        except subprocess.TimeoutExpired as exc:
            self.fail(f"watcher harness did not exit within {_HARNESS_BUDGET_S}s: {exc}")
        self.assertEqual(result.returncode, 0, f"harness crashed: {result.stderr[-2000:]}")
        try:
            out = json.loads(result.stdout)
        except json.JSONDecodeError:
            self.fail(f"harness emitted no JSON: stdout={result.stdout[-2000:]!r} stderr={result.stderr[-2000:]!r}")
        self.assertIsNone(out["harnessError"], out["harnessError"])
        self.assertIsNone(
            out["importError"],
            f"jiti could not load {EXTENSION}: {str(out['importError'])[:1500]}",
        )
        self.assertTrue(out["defaultIsFunction"], "the extension must default-export a factory")
        for step in out["steps"]:
            self.assertFalse(step.get("missing"), f"a step addressed an unregistered tool/command: {step}")
        return out

    # -- helpers over a harness report ------------------------------------

    @staticmethod
    def surfacings(out: dict) -> list[str]:
        return [r["text"] for r in out["userMessages"] + out["messages"] + out["notifies"]]

    def tool_steps(self, out: dict) -> list[dict]:
        return [s for s in out["steps"] if s["op"] == "tool"]


class SandeshWatcherRegistrationTest(SandeshWatcherTestCase):
    """\u00a7S2 AC1 -- the extension registers the tool and the command."""

    def test_factory_registers_the_sandesh_watcher_tool_and_the_watcher_command(self):
        out = self.drive(["alive"], [])
        self.assertEqual(out["tools"], ["sandesh_watcher"], "exactly one tool, sandesh_watcher")
        self.assertEqual(out["commands"], ["watcher"], "exactly one command, /watcher")
        self.assertEqual(out["launches"], [], "loading the extension must spawn nothing")

    def test_tool_schema_declares_start_status_stop_and_address_project(self):
        out = self.drive(["alive"], [])
        schema = out["toolParameters"].get("sandesh_watcher", "")
        for word in ("start", "status", "stop", "address", "project", "action"):
            self.assertIn(f'"{word}"', schema, f"the sandesh_watcher schema must name {word!r}: {schema[:800]}")


class SandeshWatcherStartTest(SandeshWatcherTestCase):
    """\u00a7S2 AC3 -- readiness on the banner, one watcher per address, stop,
    status, and the exact child argv (ruling T)."""

    def test_start_spawns_sandesh_notify_with_exactly_to_and_project(self):
        out = self.drive(["alive"], [_start(), _stop()])
        self.assertEqual(len(out["launches"]), 1)
        self.assertEqual(self.argv_of(1), ["notify", "--to", ADDRESS, "--project", PROJECT])

    def test_start_spawns_the_child_with_pythonunbuffered_so_the_banner_is_not_held(self):
        # VERIFY finding 1 (C5): Sandesh prints its banner with an unflushed
        # print(); piped and buffered, the banner arrives only at exit.
        out = self.drive(["alive"], [_start(), _stop()])
        start = self.tool_steps(out)[0]
        self.assertEqual(self.env_of(1), "1", "the child must run with PYTHONUNBUFFERED=1")
        self.assertFalse(start["timedOut"], "a buffered child hides its banner and start hangs")
        self.assertRegex(start["text"] or "", re.compile("ready", re.I))
    def test_start_reports_ready_naming_the_address_only_after_the_banner(self):
        out = self.drive(["late"], [_start(), {"op": "snapshot", "label": "after"}, _stop()])
        start = self.tool_steps(out)[0]
        self.assertFalse(start["timedOut"], "start must resolve once the banner appears")
        self.assertIsNone(start["threw"])
        self.assertRegex(start["text"] or "", re.compile("ready", re.I))
        self.assertIn(ADDRESS, start["text"] or "")
        self.assertTrue(
            start["markerExistedAtResolve"],
            "start resolved before the fake printed its banner (the marker is touched just before it)",
        )
        self.assertEqual(out["snapshots"]["after"]["launches"], 1)

    def test_start_does_not_hang_when_the_child_exits_without_a_banner(self):
        out = self.drive(["nobanner 1"], [_start(), {"op": "sleep", "ms": 500}])
        start = self.tool_steps(out)[0]
        self.assertFalse(start["timedOut"], "a child dying before its banner must still end start")
        if start["threw"] is None:
            self.assertRegex(
                start["text"] or "", re.compile(r"\b1\b|exit|usage|configuration", re.I),
                "start must report the pre-banner exit, not success",
            )
        self.assertEqual(len(out["launches"]), 1, "no relaunch after an exit-1 before the banner")

    def test_start_while_one_runs_reports_it_and_spawns_nothing(self):
        out = self.drive(["alive"], [
            _start(), _start(), {"op": "sleep", "ms": 500},
            {"op": "snapshot", "label": "twice"}, _stop(),
        ])
        second = self.tool_steps(out)[1]
        self.assertIsNone(second["threw"])
        self.assertRegex(second["text"] or "", re.compile("already|running", re.I))
        self.assertEqual(out["snapshots"]["twice"]["launches"], 1, "a second start must spawn nothing")

    def test_stop_tool_terminates_the_child(self):
        out = self.drive(["alive"], [
            _start(), _stop(), {"op": "waitPidDead", "launch": 1, "timeoutMs": 3000},
        ])
        dead = out["steps"][-1]
        self.assertIsNotNone(dead["pid"])
        self.assertTrue(dead["dead"], f"stop must terminate the child pid {dead['pid']}")
        self.assertEqual(len(out["launches"]), 1, "stop must not relaunch")

    def test_watcher_stop_command_terminates_the_child(self):
        out = self.drive(["alive"], [
            _start(), {"op": "command", "name": "watcher", "args": "stop"},
            {"op": "waitPidDead", "launch": 1, "timeoutMs": 3000},
        ])
        cmd = [s for s in out["steps"] if s["op"] == "command"][0]
        self.assertFalse(cmd["timedOut"])
        self.assertIsNone(cmd["threw"])
        self.assertTrue(out["steps"][-1]["dead"], "/watcher stop must terminate the child")

    def test_status_tool_names_the_running_address(self):
        out = self.drive(["alive"], [_start(), {"op": "tool", "params": {"action": "status"}}, _stop()])
        status = self.tool_steps(out)[1]
        self.assertIsNone(status["threw"])
        self.assertIn(ADDRESS, status["text"] or "")

    def test_watcher_status_command_names_the_running_address(self):
        out = self.drive(["alive"], [
            _start(), {"op": "snapshot", "label": "before"},
            {"op": "command", "name": "watcher", "args": "status"},
            {"op": "snapshot", "label": "after"}, _stop(),
        ])
        before, after = out["snapshots"]["before"], out["snapshots"]["after"]
        new = (out["notifies"][before["notifies"]:after["notifies"]]
               + out["messages"][before["messages"]:after["messages"]])
        self.assertTrue(
            any(ADDRESS in r["text"] for r in new),
            f"/watcher status must report the running address, got {[r['text'] for r in new]}",
        )


class SandeshWatcherExitTest(SandeshWatcherTestCase):
    """\u00a7S2 AC2 -- one test per exit code (ruling C)."""

    def test_exit_0_wakes_once_naming_the_ids_and_quoted_fetch_and_relaunches_at_once(self):
        out = self.drive(["mail 12,13", "alive"], [
            _start(), {"op": "waitUntil", "userMessages": 1, "timeoutMs": 5000},
            {"op": "waitUntil", "launches": 2, "timeoutMs": 5000},
            {"op": "sleep", "ms": _SETTLE_MS}, {"op": "snapshot", "label": "woken"},
            _start(), {"op": "snapshot", "label": "restarted"}, _stop(),
            {"op": "waitPidDead", "launch": 2, "timeoutMs": 3000},
        ])
        woken = out["snapshots"]["woken"]
        self.assertEqual(woken["launches"], 2, "exit 0 must relaunch at once, and only once")
        self.assertEqual(len(out["userMessages"]), 1, f"exactly one wake message, got {out['userMessages']}")
        self.assertEqual(out["messages"], [], "the wake is sendUserMessage only")
        self.assertEqual(out["notifies"], [], "the wake is sendUserMessage only")
        text = out["userMessages"][0]["text"]
        self.assertIn(FETCH, text, "the fetch must shell-quote the address")
        self.assertIn(ADDRESS, text)
        self.assertRegex(text, r"\b12\b", "the wake must name the unread ids Sandesh printed")
        self.assertRegex(text, r"\b13\b", "the wake must name the unread ids Sandesh printed")
        second = self.tool_steps(out)[1]
        self.assertRegex(second["text"] or "", re.compile("already|running", re.I),
                         "after a wake the watcher is still running")
        self.assertEqual(out["snapshots"]["restarted"]["launches"], 2, "a start while it runs spawns nothing")
        self.assertTrue(out["steps"][-1]["dead"], "stop must terminate the relaunched child")

    def test_exit_0_again_with_the_same_ids_does_not_wake_and_retries_every_30s(self):
        out = self.drive(["mail 7"], [
            _start(), {"op": "waitUntil", "launches": 4, "timeoutMs": 8000},
            {"op": "sleep", "ms": 400}, {"op": "snapshot", "label": "retrying"},
            {"op": "tool", "params": {"action": "status"}}, _stop(),
            {"op": "snapshot", "label": "stopped"}, {"op": "sleep", "ms": 1200},
            {"op": "snapshot", "label": "after_stop"},
        ], time_scale=_TIME_SCALE)
        snap = out["snapshots"]["retrying"]
        self.assertEqual(len(out["userMessages"]), 1, f"the same ids must not wake again, got {out['userMessages']}")
        self.assertEqual(out["messages"] + out["notifies"], [], "retries are silent")
        self.assertGreaterEqual(snap["launches"], 4, "relaunches must keep going while the mail waits")
        self.assertLessEqual(snap["launches"], 10, "same-ids relaunches must wait, not spin")
        self.assertGreaterEqual(out["timerDelays"].count(RETRY_MS), 2,
                                f"each same-ids retry waits 30 s; delays asked for: {out['timerDelays']}")
        self.assertIn(ADDRESS, self.tool_steps(out)[1]["text"] or "", "status names the retrying watcher")
        # C6 VERIFY finding 2: stop cancels the pending 30 s retry. The retry
        # runs at 1/100 scale (0.3 s), so 1.2 s after stop spans four of them.
        self.assertEqual(out["snapshots"]["after_stop"]["launches"], out["snapshots"]["stopped"]["launches"],
                         "stop must cancel the pending retry: nothing may launch after it")

    def test_status_during_a_retry_does_not_name_the_dead_childs_pid(self):
        # C6 VERIFY finding 3. Unscaled, the retry waits a real 30 s, so
        # 0.5 s after the second exit the watcher is certainly waiting and
        # both children are dead.
        out = self.drive(["mail 7"], [
            _start(), {"op": "waitUntil", "launches": 2, "timeoutMs": 5000},
            {"op": "sleep", "ms": 500}, {"op": "snapshot", "label": "retrying"},
            {"op": "tool", "params": {"action": "status"}}, _stop(),
        ])
        self.assertEqual(out["snapshots"]["retrying"]["launches"], 2, "the watcher must be waiting to retry")
        status = self.tool_steps(out)[1]["text"] or ""
        self.assertIn(ADDRESS, status, "status names the retrying watcher")
        for pid in out["launches"]:
            self.assertNotRegex(status, rf"\b{pid}\b",
                                f"status during a retry must not name the dead child's pid {pid}: {status!r}")

    def test_exit_0_without_ids_wakes_again_after_a_relaunch_reports_no_mail(self):
        # C6 VERIFY finding 1(a): the no-readable-ids suppression clears as
        # soon as a relaunch prints Sandesh's `no 'to' mail` line.
        out = self.drive(["exit 0", "nomail exit 0", "alive"], [
            _start(), {"op": "waitUntil", "launches": 3, "timeoutMs": 8000},
            {"op": "sleep", "ms": 500}, {"op": "snapshot", "label": "watching"}, _stop(),
        ], time_scale=_TIME_SCALE)
        self.assertEqual(len(out["userMessages"]), 2,
                         f"one wake per exit 0, the relaunch having reported no mail, got {out['userMessages']}")
        self.assertEqual(out["snapshots"]["watching"]["launches"], 3)
        self.assertNotIn(RETRY_MS, out["timerDelays"], "a wake relaunches at once, never after a retry wait")
        self.assertEqual(out["messages"] + out["notifies"], [])

    def test_exit_0_with_the_same_ids_wakes_again_after_a_relaunch_reports_no_mail(self):
        # C6 VERIFY finding 1(b): the same-ids suppression clears the same way.
        out = self.drive(["mail 7", "nomail mail 7", "alive"], [
            _start(), {"op": "waitUntil", "launches": 3, "timeoutMs": 8000},
            {"op": "sleep", "ms": 500}, {"op": "snapshot", "label": "watching"}, _stop(),
        ], time_scale=_TIME_SCALE)
        wakes = [m["text"] for m in out["userMessages"]]
        self.assertEqual(len(wakes), 2, f"the mail was fetched in between, so 7 wakes again, got {wakes}")
        for w in wakes:
            self.assertRegex(w, r"\b7\b")
        self.assertEqual(out["snapshots"]["watching"]["launches"], 3)
        self.assertNotIn(RETRY_MS, out["timerDelays"], "a wake relaunches at once, never after a retry wait")
        self.assertEqual(out["messages"] + out["notifies"], [])

    def test_exit_0_with_new_ids_wakes_again(self):
        out = self.drive(["mail 41", "mail 41", "mail 41,42", "alive"], [
            _start(), {"op": "waitUntil", "userMessages": 2, "timeoutMs": 8000},
            {"op": "waitUntil", "launches": 4, "timeoutMs": 5000},
            {"op": "sleep", "ms": 500}, {"op": "snapshot", "label": "woken"}, _stop(),
        ], time_scale=_TIME_SCALE)
        snap = out["snapshots"]["woken"]
        wakes = [m["text"] for m in out["userMessages"]]
        self.assertEqual(len(wakes), 2, f"one wake for 41, one for the new 42, got {wakes}")
        self.assertRegex(wakes[0], r"\b41\b")
        self.assertNotRegex(wakes[0], r"\b42\b")
        self.assertRegex(wakes[1], r"\b42\b", "the second wake names the new id")
        self.assertEqual(snap["launches"], 4, "relaunched after each exit, then watching")
        self.assertEqual(out["messages"] + out["notifies"], [])

    def test_exit_2_relaunches_once_silently(self):
        out = self.drive(["exit 2", "alive"], [
            _start(), {"op": "waitUntil", "launches": 2, "timeoutMs": 5000},
            {"op": "sleep", "ms": _SETTLE_MS // 2}, {"op": "snapshot", "label": "relaunched"}, _stop(),
        ])
        snap = out["snapshots"]["relaunched"]
        self.assertEqual(snap["launches"], 2, "exit 2 must relaunch exactly once")
        self.assertEqual(snap["surfaced"], 0, f"exit 2 must be silent, got {self.surfacings(out)}")
        self.assertEqual(self.argv_of(2), ["notify", "--to", ADDRESS, "--project", PROJECT])

    def test_three_exit_2_within_a_minute_surface_and_stop_relaunching(self):
        out = self.drive(["exit 2"], [
            _start(), {"op": "waitUntil", "surfaced": 1, "timeoutMs": 8000},
            {"op": "sleep", "ms": _SETTLE_MS}, {"op": "snapshot", "label": "capped"},
        ])
        snap = out["snapshots"]["capped"]
        self.assertEqual(snap["launches"], 3, "three launches, never a fourth")
        self.assertEqual(snap["surfaced"], 1, f"exactly one surfacing, got {self.surfacings(out)}")

    def test_exit_2_spread_over_more_than_a_minute_keeps_relaunching_silently(self):
        # Ruling W: a cap on three timeouts in total would die here.
        steps = [_start(), {"op": "waitUntil", "launches": 1, "timeoutMs": 5000}]
        for n in range(1, 5):
            steps += [
                {"op": "advanceClock", "ms": 61_000},
                {"op": "touch", "path": str(self.fake_dir / f"release.{n}")},
                {"op": "waitUntil", "launches": n + 1, "timeoutMs": 5000},
            ]
        steps += [{"op": "sleep", "ms": 1000}, {"op": "snapshot", "label": "spread"}, _stop()]
        out = self.drive(["hold 2", "hold 2", "hold 2", "hold 2", "alive"], steps, fake_clock=True)
        snap = out["snapshots"]["spread"]
        self.assertEqual(snap["launches"], 5, "each spread-out exit 2 must relaunch")
        self.assertEqual(snap["surfaced"], 0, f"spread-out timeouts must not surface, got {self.surfacings(out)}")

    def _assert_surfaced_once_without_relaunch(self, plan_line: str, code_re: str, meaning_re: str):
        out = self.drive([plan_line], [
            _start(), {"op": "waitUntil", "surfaced": 1, "timeoutMs": 5000},
            {"op": "sleep", "ms": _SETTLE_MS}, {"op": "snapshot", "label": "stopped"},
        ])
        snap = out["snapshots"]["stopped"]
        self.assertEqual(snap["launches"], 1, f"{plan_line!r} must never relaunch")
        texts = self.surfacings(out)
        self.assertEqual(len(texts), 1, f"{plan_line!r} must surface exactly once, got {texts}")
        self.assertRegex(texts[0], re.compile(code_re), f"the surfacing must name the code: {texts[0]!r}")
        self.assertRegex(texts[0], re.compile(meaning_re, re.I), f"the surfacing must give the meaning: {texts[0]!r}")

    def test_exit_1_surfaces_usage_or_configuration_error_without_relaunch(self):
        self._assert_surfaced_once_without_relaunch("exit 1", r"\b1\b", "usage|configuration")

    def test_exit_3_surfaces_tombstoned_project_without_relaunch(self):
        self._assert_surfaced_once_without_relaunch("exit 3", r"\b3\b", "tombston")

    def test_exit_4_surfaces_eviction_without_relaunch(self):
        self._assert_surfaced_once_without_relaunch("exit 4", r"\b4\b", "evict")

    def test_exit_5_surfaces_already_live_dedup_without_relaunch(self):
        self._assert_surfaced_once_without_relaunch("exit 5", r"\b5\b", "already|dedup")

    def test_signal_exit_surfaces_the_signal_without_relaunch(self):
        self._assert_surfaced_once_without_relaunch("signal TERM", r"SIGTERM|\b15\b|\b143\b", "signal")


if __name__ == "__main__":
    unittest.main()
