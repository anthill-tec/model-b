"""RED-phase tests for CR-MDB-030 cycle C1 (§S1 default-export factory,
§S2 piped-child-process payload transport, §S5 real fail-closed/open, §S8
runtime proof through Pi's own (jiti) loader).

Out of scope for C1 (land in later cycles, NOT tested here):
  * §S3 neutral payload MAPPING TABLE (Pi toolName -> neutral tool_name) and
    the six ported `hooks-src/scripts/*` — C2. The payload-transport test
    below (`PiHookPayloadTransportTest`) proves §S2's piped-stdin transport
    is byte-for-byte faithful using a GENERIC marker payload; it does not
    assert any particular neutral-schema SHAPE, since that shape is §S3's
    job. Each C2 mapping-table row gets its own echo subtest against the
    ported scripts once §S3 lands.
  * §S4 matcher-on-neutral-name filtering (the "counting fake script" test)
    — C2.
  * §S6 (.gitignore / worktree carry) and §S7 (retire
    block-bad-cycle-task-name) — C3.

Runtime harness (§S8): `tests/fixtures/pi_hook_loader_harness.mjs` loads an
emitted `.pi/extensions/*.ts` with the exact mechanism Pi 0.87.1's own
loader uses (`jiti.import(path, { default: true })` —
`dist/core/extensions/loader.js:414` in the installed
`@earendil-works/pi-coding-agent`), invokes the factory with a recording
`pi`, and drives the registered handler with a synthetic event/ctx pair.
This is real jiti loading real emitted TypeScript spawning real child
processes (the fixture scripts under `tests/fixtures/pi_hook_scripts/`) --
no mocking of the extension runtime itself.

Environment detection (`_require_loader_env`) resolves `node`, the
installed `pi` binary's un-bundled package root (needs
`dist/core/extensions/loader.js` -- the bundled single-file CLI alone does
not expose it), and the `jiti` package Pi's own loader re-exports, raising
`unittest.SkipTest` naming exactly what is missing at each step (AC: "the
loader test... SKIPS, naming what is missing"). `LoaderEnvironmentDetectionTest`
exercises all three skip paths directly via monkeypatching, so the skip
behaviour itself is proven on every machine, not only ones missing a
component.

MIGRATED from tests/test_hooks_compiler.py::PiExtensionEmitterTest (this
cycle, replacing the OLD `pi.exec`/no-default-export characterization with
the NEW default-export / no-`pi.exec` / session_before_compact contract --
CR-MDB-030 §S1/§S2/§S5):
  * test_extension_subscribes_session_start_and_tool_call_via_pi_exec
    -> test_extension_default_exports_a_factory_and_never_uses_pi_exec
  * test_pre_compact_is_a_declared_gap_for_pi_not_emitted_not_refused
    -> test_pre_compact_maps_to_session_before_compact_and_is_emitted

Stdlib only: unittest + json + subprocess + shutil + tempfile + pathlib +
unittest.mock.
"""

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures"
HARNESS_MJS = FIXTURES_DIR / "pi_hook_loader_harness.mjs"
FIXTURE_SCRIPTS_ROOT = FIXTURES_DIR / "pi_hook_scripts"

# Generous but bounded: the loader harness always reaches an explicit
# process.exit(); a hang here means a real defect (e.g. a kill-on-timeout
# path that doesn't actually kill), and subprocess.run(timeout=...) turns
# that into a normal test failure instead of stalling the suite.
_DEFAULT_DRIVE_BUDGET_S = 10.0

# --------------------------------------------------------------------------
# §S8 loader-environment detection -- SKIPS, naming what is missing.
# --------------------------------------------------------------------------

def _find_pi_package_root(pi_binary_resolved: Path) -> Path | None:
    """Walk up from the resolved `pi` binary looking for the un-bundled
    package root (needs `dist/core/extensions/loader.js` -- the compiled
    single-file `dist/bundle/cli.js` alone does not expose jiti loading)."""
    for parent in pi_binary_resolved.parents:
        if (parent / "dist" / "core" / "extensions" / "loader.js").is_file():
            return parent
    return None


def _find_jiti_near(pi_pkg_root: Path) -> Path | None:
    """Walk up from the pi package root looking for the `jiti` package its
    own `dist/core/extensions/jiti-loader.js` re-exports `createJiti` from
    (hoisted node_modules, so it need not be nested under the package)."""
    for ancestor in (pi_pkg_root, *pi_pkg_root.parents):
        candidate = ancestor / "node_modules" / "jiti" / "lib" / "jiti.mjs"
        if candidate.is_file():
            return candidate
    return None


def _require_loader_env() -> dict:
    """Resolve node / pi / jiti or raise `unittest.SkipTest` naming exactly
    what is missing (CR-MDB-030 §S8's loader-test skip contract)."""
    node_bin = shutil.which("node")
    if node_bin is None:
        raise unittest.SkipTest(
            "pi hook runtime loader test: node is not installed (no `node` on PATH)"
        )

    pi_bin = shutil.which("pi")
    if pi_bin is None:
        raise unittest.SkipTest(
            "pi hook runtime loader test: pi is not installed (no `pi` on PATH)"
        )

    pi_pkg_root = _find_pi_package_root(Path(pi_bin).resolve())
    if pi_pkg_root is None:
        raise unittest.SkipTest(
            "pi hook runtime loader test: installed pi has no "
            "dist/core/extensions/loader.js under any parent of the resolved "
            f"`pi` binary ({Path(pi_bin).resolve()}) -- jiti loading unavailable"
        )

    jiti_mjs = _find_jiti_near(pi_pkg_root)
    if jiti_mjs is None:
        raise unittest.SkipTest(
            f"pi hook runtime loader test: jiti not found near installed pi "
            f"package {pi_pkg_root} (no node_modules/jiti/lib/jiti.mjs in any "
            "ancestor)"
        )

    return {"node_bin": node_bin, "pi_pkg_root": pi_pkg_root, "jiti_mjs": jiti_mjs}


class LoaderEnvironmentDetectionTest(unittest.TestCase):
    """§S8's loader test SKIPS, naming what is missing, for each of
    node / pi / jiti absent -- exercised directly via monkeypatching so the
    skip behaviour itself is proven regardless of what this machine has
    installed."""

    def test_missing_node_skips_naming_node(self):
        with mock.patch("shutil.which", return_value=None), self.assertRaises(
            unittest.SkipTest
        ) as ctx:
            _require_loader_env()
        self.assertIn("node", str(ctx.exception).lower())

    def test_missing_pi_binary_skips_naming_pi(self):
        def fake_which(name):
            return "/usr/bin/node" if name == "node" else None

        with mock.patch("shutil.which", side_effect=fake_which), self.assertRaises(
            unittest.SkipTest
        ) as ctx:
            _require_loader_env()
        message = str(ctx.exception).lower()
        self.assertIn("pi is not installed", message)

    def test_missing_pi_package_loader_skips_naming_the_gap(self):
        def fake_which(name):
            return f"/usr/bin/{name}"

        with mock.patch("shutil.which", side_effect=fake_which), mock.patch(
            f"{__name__}._find_pi_package_root", return_value=None
        ), self.assertRaises(unittest.SkipTest) as ctx:
            _require_loader_env()
        self.assertIn("loader.js", str(ctx.exception))

    def test_missing_jiti_skips_naming_jiti(self):
        fake_root = Path("/fake/pi-coding-agent")

        def fake_which(name):
            return f"/usr/bin/{name}"

        with mock.patch("shutil.which", side_effect=fake_which), mock.patch(
            f"{__name__}._find_pi_package_root", return_value=fake_root
        ), mock.patch(f"{__name__}._find_jiti_near", return_value=None), self.assertRaises(
            unittest.SkipTest
        ) as ctx:
            _require_loader_env()
        self.assertIn("jiti", str(ctx.exception).lower())


# --------------------------------------------------------------------------
# Shared fixture for every test that actually drives the loader.
# --------------------------------------------------------------------------

class PiLoaderTestCase(unittest.TestCase):
    """Common tmp-target + compile + drive fixture for tests that load a
    REAL emitted `.pi/extensions/*.ts` through jiti and run REAL child
    processes (never the real project or `~/.claude`)."""

    @classmethod
    def setUpClass(cls):
        env = _require_loader_env()
        cls.node_bin = env["node_bin"]
        cls.jiti_mjs = env["jiti_mjs"]

    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="modelb-pi-hook-runtime-")
        self.target = Path(self._tmp)

    def tearDown(self):
        shutil.rmtree(self._tmp, ignore_errors=True)

    def _compile(self, instance: dict, scripts_root: Path = FIXTURE_SCRIPTS_ROOT):
        """Compile ONE neutral instance for pi only, into a FRESH isolated
        subdirectory of the tmp target (never the shared root -- a prior
        subTest's files must never leak into this one's count, including
        when that prior subTest FAILED before reaching any cleanup).
        Returns (pi_report, [emitted .ts Paths])."""
        from modelb_axi.hooks import compile_wiring

        call_target = Path(tempfile.mkdtemp(dir=self.target))
        report = compile_wiring(
            schema_instances=[instance],
            harnesses=["pi"],
            target=call_target,
            scripts_root=scripts_root,
        )
        ext_dir = call_target / ".pi" / "extensions"
        ts_files = sorted(ext_dir.glob("*.ts")) if ext_dir.is_dir() else []
        return report["pi"], ts_files

    def _drive(self, ext_path: Path, event: dict, ctx: dict | None = None,
               budget_s: float = _DEFAULT_DRIVE_BUDGET_S) -> dict:
        """Load `ext_path` with jiti exactly as Pi's own loader does, then
        drive the handler registered for `event["type"]` with (event, ctx).
        Always returns the harness's parsed JSON report; never raises for an
        in-band load/handler failure (those are reported IN the JSON so the
        caller can assert on them) -- only a harness-process-level failure
        (crash, bad JSON, timeout) fails the test outright."""
        try:
            result = subprocess.run(
                [self.node_bin, str(HARNESS_MJS), str(ext_path), str(self.jiti_mjs)],
                input=json.dumps({"event": event, "ctx": ctx or {}}),
                capture_output=True,
                text=True,
                timeout=budget_s,
            )
        except subprocess.TimeoutExpired as exc:
            self.fail(
                f"loader harness did not exit within {budget_s}s driving "
                f"{ext_path} (a kill-on-timeout path that doesn't actually "
                f"kill would look exactly like this): {exc}"
            )
        if result.returncode != 0:
            self.fail(
                f"loader harness crashed (exit {result.returncode}) driving "
                f"{ext_path}; stderr={result.stderr!r}"
            )
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError:
            self.fail(
                f"loader harness did not emit valid JSON driving {ext_path}: "
                f"stdout={result.stdout!r} stderr={result.stderr!r}"
            )


# --------------------------------------------------------------------------
# §S1 -- default-export factory Pi's jiti can import; calling it registers
# a handler for the instance's event.
# --------------------------------------------------------------------------

class DefaultExportFactoryTest(PiLoaderTestCase):
    def test_emitted_extension_default_exports_a_function_jiti_can_import(self):
        report, ts_files = self._compile({
            "event": "session-start",
            "matcher": "*",
            "command": "always-allow",
            "tier": "core",
            "timeout": 3,
            "fail_direction": None,
        })
        self.assertEqual(len(ts_files), 1, f"expected exactly one emitted file: {ts_files!r}")
        self.assertEqual(report["refusals"], [])

        loaded = self._drive(ts_files[0], event={"type": "session_start"})
        self.assertIsNone(
            loaded["importError"],
            f"jiti import of the emitted extension failed: {loaded['importError']!r}",
        )
        self.assertTrue(
            loaded["defaultIsFunction"],
            "emitted .pi/extensions/*.ts must default-export a function Pi's "
            "jiti can import with { default: true }",
        )

    def test_calling_the_factory_registers_a_handler_for_each_instance_event(self):
        cases = [
            ("pre-tool-use", "tool_call"),
            ("session-start", "session_start"),
        ]
        for neutral_event, expected_pi_event in cases:
            with self.subTest(neutral_event=neutral_event):
                report, ts_files = self._compile({
                    "event": neutral_event,
                    "matcher": "*",
                    "command": "always-allow",
                    "tier": "core",
                    "timeout": 3,
                    "fail_direction": None,
                })
                self.assertEqual(len(ts_files), 1)
                loaded = self._drive(ts_files[0], event={"type": expected_pi_event})
                self.assertTrue(loaded["defaultIsFunction"])
                self.assertEqual(
                    loaded["registeredEvents"],
                    [expected_pi_event],
                    f"calling the factory must register exactly one handler "
                    f"for {expected_pi_event!r}",
                )

    def test_pre_compact_maps_to_session_before_compact_and_registers_it(self):
        """§S5: pre-compact's Pi counterpart is session_before_compact, not
        a declared gap. Proven at runtime via the real loader (the static
        compiler-report assertion for this is migrated in
        tests/test_hooks_compiler.py -- see this file's module docstring)."""
        report, ts_files = self._compile({
            "event": "pre-compact",
            "matcher": "*",
            "command": "always-allow",
            "tier": "core",
            "timeout": 3,
            "fail_direction": None,
        })
        self.assertEqual(len(ts_files), 1, f"pre-compact must be emitted for pi: {ts_files!r}")
        loaded = self._drive(ts_files[0], event={"type": "session_before_compact"})
        self.assertTrue(loaded["defaultIsFunction"])
        self.assertEqual(loaded["registeredEvents"], ["session_before_compact"])


# --------------------------------------------------------------------------
# §S2 -- piped child process: the shim must deliver EXACTLY the payload it
# built to the script's stdin, with pi.exec never used. Mapping the Pi
# event into the §S3 neutral shape is C2's job -- this proves TRANSPORT
# fidelity with a generic marker payload, independent of that shape.
# --------------------------------------------------------------------------

class PiHookPayloadTransportTest(PiLoaderTestCase):
    def _echo_extension(self, fail_direction="open"):
        report, ts_files = self._compile({
            "event": "pre-tool-use",
            "matcher": "*",
            "command": "echo-stdin",
            "tier": "core",
            "timeout": 3,
            "fail_direction": fail_direction,
        })
        self.assertEqual(len(ts_files), 1)
        return report, ts_files[0]

    def test_shim_pipes_the_exact_event_json_to_the_script_stdin(self):
        _, ext_path = self._echo_extension()
        text = ext_path.read_text(encoding="utf-8")
        self.assertNotIn(
            "pi.exec(", text,
            "§S2: pi.exec has no stdin option (ExecOptions = {signal?, "
            "timeout?, cwd?}) -- the shim must not use it",
        )

        event = {
            "type": "tool_call",
            "toolCallId": "probe-1",
            "toolName": "ctx_shell",
            "input": {"command": "echo hi", "__probe": "transport-fidelity-xyz"},
        }
        loaded = self._drive(ext_path, event=event)
        self.assertIsNone(loaded["importError"])
        self.assertIsNone(loaded["handlerThrew"])
        result = loaded["handlerResult"]
        self.assertIsNotNone(result, "expected a block result from the echo script (exit 2)")
        self.assertTrue(result.get("block"), f"expected block: true, got {result!r}")
        echoed = json.loads(result["reason"])
        self.assertEqual(
            echoed, event,
            "the script's stdin must be EXACTLY the JSON the shim built for "
            "this event -- not a subset, not re-ordered, not stringified twice",
        )

    def test_a_different_event_produces_a_different_exact_echo(self):
        """Guards against a stub that always pipes a fixed literal instead
        of the real, per-call payload."""
        _, ext_path = self._echo_extension()
        event = {
            "type": "tool_call",
            "toolCallId": "probe-2",
            "toolName": "write",
            "input": {"path": "/srv/example-project/file.txt", "__probe": "second-distinct-marker"},
        }
        loaded = self._drive(ext_path, event=event)
        result = loaded["handlerResult"]
        self.assertTrue(result and result.get("block"))
        echoed = json.loads(result["reason"])
        self.assertEqual(echoed, event)
        self.assertNotEqual(
            echoed.get("toolCallId"), "probe-1",
            "the echoed payload must reflect THIS call's event, not a fixture "
            "from a previous test",
        )


# --------------------------------------------------------------------------
# §S5 -- fail-closed that is real: 4 failure modes (spawn error, other exit
# code, kill-on-timeout, unparseable output) x {closed, open} = 8 subtests.
# --------------------------------------------------------------------------

class PiHookFailDirectionTest(PiLoaderTestCase):
    _FAILURE_MODES = {
        "spawn error (script is missing)": {
            "command": "this-script-does-not-exist-anywhere",
            "reason_keyword": "spawn",
        },
        "other exit code (exits 1)": {
            "command": "exits-with-error",
            "reason_keyword": "exit",
        },
        "kill on timeout": {
            "command": "sleeps-past-timeout",
            "reason_keyword": "timeout",
        },
        "unparseable output": {
            "command": "prints-garbage",
            "reason_keyword": "unparseable",
        },
    }

    def test_closed_blocks_and_open_allows_for_each_failure_mode(self):
        event = {
            "type": "tool_call",
            "toolCallId": "fd-1",
            "toolName": "bash",
            "input": {"command": "true"},
        }
        for mode_name, mode in self._FAILURE_MODES.items():
            for fail_direction in ("closed", "open"):
                with self.subTest(mode=mode_name, fail_direction=fail_direction):
                    _, ts_files = self._compile({
                        "event": "pre-tool-use",
                        "matcher": "*",
                        "command": mode["command"],
                        "tier": "core",
                        "timeout": 1,
                        "fail_direction": fail_direction,
                    })
                    self.assertEqual(len(ts_files), 1)
                    budget = 8.0 if mode_name == "kill on timeout" else _DEFAULT_DRIVE_BUDGET_S
                    loaded = self._drive(ts_files[0], event=event, budget_s=budget)
                    self.assertIsNone(
                        loaded["importError"],
                        f"[{mode_name}/{fail_direction}] import failed: {loaded['importError']!r}",
                    )
                    self.assertIsNone(
                        loaded["handlerThrew"],
                        f"[{mode_name}/{fail_direction}] handler threw: {loaded['handlerThrew']!r}",
                    )
                    result = loaded["handlerResult"]
                    if fail_direction == "closed":
                        self.assertIsInstance(
                            result, dict,
                            f"[{mode_name}/closed] expected a block result, got {result!r}",
                        )
                        self.assertIs(
                            result.get("block"), True,
                            f"[{mode_name}/closed] must block: {result!r}",
                        )
                        reason = result.get("reason")
                        self.assertIsInstance(reason, str)
                        self.assertTrue(reason, f"[{mode_name}/closed] reason must be non-empty")
                        self.assertIn(
                            mode["reason_keyword"], reason.lower(),
                            f"[{mode_name}/closed] reason {reason!r} does not name "
                            f"the failure mode ({mode['reason_keyword']!r})",
                        )
                    else:
                        self.assertEqual(
                            result, {},
                            f"[{mode_name}/open] a fail-open guard must allow "
                            f"(return {{}}) on this failure mode, got {result!r}",
                        )


if __name__ == "__main__":
    unittest.main()
