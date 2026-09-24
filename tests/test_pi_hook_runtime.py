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
  * §S6 (.gitignore / worktree carry) — C3. §S7 (retire the cycle-todo-
    naming guard) moved INTO C2 (orchestrator scope widen, this pass) --
    see tests/test_hook_retirement.py, which owns its retired identifier
    and every AC about it; this file never spells that name.

CR-MDB-030 cycle C2 ADDS (this pass — §S3 payload contract + §S4 matcher on
the neutral name, per the mapping table in the CR spec):
  * `PiHookNeutralPayloadMappingTest` — one subtest per §S3 mapping-table
    row (echoed via the same `echo-stdin` fixture §S2 already proved byte-
    faithful transport with), plus a dedicated ctx_patch multi-operation
    `paths` collection subtest.
  * `ScriptVocabularyAndSchemaDocTest` — the grep gate (zero Claude Code
    tool-name/`file_path` literals in `hooks-src/scripts/*`) and the
    schema.md neutral-payload/mapping documentation checks. Scans the WHOLE
    `hooks-src/scripts/*` directory per the AC's literal wording; §S7 (the
    cycle-todo-naming guard's retirement) is now ALSO C2's job (scope
    widened), so this grep gate is expected to reach GREEN entirely within
    this cycle once tests/test_hook_retirement.py's own AC does too --
    porting the six surviving scripts to the neutral vocabulary was
    always C2's job.
  * `PiHookWriteBoundaryAcrossToolsTest` — `block-write-outside-worktree`
    through `write`, `edit`, `ctx_edit`, `ctx_patch` (incl. a second
    ctx_patch operation targeting the outside path), and an allowed `read`
    — all through the REAL `hooks-src/scripts/block-write-outside-worktree`
    script, driven through the emitted pi shim (never the fixture scripts).
  * `PiHookCargoMvnGuardAcrossToolsTest` — `block-direct-cargo-test` /
    `block-direct-mvn-test` through `bash`, `ctx_shell`, and a shell-
    language `ctx_execute`, against the REAL scripts through the emitted
    shim.
  * `PiHookMatcherFiltersOnNeutralNameTest` — the counting-fake-script
    AC: a `write|edit` matcher does not spawn for `bash`/`ctx_shell` and
    DOES spawn for `ctx_patch`, using the new
    `tests/fixtures/pi_hook_scripts/counts-invocations` fixture (counts
    real invocations via a side-channel file, independent of its own
    exit code, since a non-spawn and an allowed-spawn both report `{}`).

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

Stdlib only: unittest + json + os + subprocess + shutil + tempfile +
pathlib + unittest.mock.
"""

import json
import os
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

# §S3/§S4 (C2): the REAL protocol-script library and schema doc -- never
# copied, never mutated by this file; referenced by absolute path only.
HOOKS_SRC_DIR = REPO_ROOT / "hooks-src"
REAL_SCRIPTS_ROOT = HOOKS_SRC_DIR / "scripts"
SCHEMA_MD = HOOKS_SRC_DIR / "schema.md"

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
        self.assertNotIn("refusals", report)  # CR-MDB-031 §S1: no refusal path

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

        # MIGRATED (CR-MDB-030 \u00a7S3, orchestrator-approved at C2 GREEN): the
        # shim now pipes the NEUTRAL payload it built, not the raw Pi event.
        # An unmapped pass-through tool keeps its input unchanged, so the
        # probe proves byte-exact transport of what the shim built.
        event = {
            "type": "tool_call",
            "toolCallId": "probe-1",
            "toolName": "ctx_glob",
            "input": {"pattern": "**/*.py", "__probe": "transport-fidelity-xyz"},
        }
        cwd = "/srv/example-project"
        loaded = self._drive(ext_path, event=event, ctx={"cwd": cwd})
        self.assertIsNone(loaded["importError"])
        self.assertIsNone(loaded["handlerThrew"])
        result = loaded["handlerResult"]
        self.assertIsNotNone(result, "expected a block result from the echo script (exit 2)")
        self.assertTrue(result.get("block"), f"expected block: true, got {result!r}")
        echoed = json.loads(result["reason"])
        self.assertEqual(
            echoed,
            {
                "tool_name": "ctx_glob",
                "tool_input": {"pattern": "**/*.py", "__probe": "transport-fidelity-xyz"},
                "cwd": cwd,
                "session_id": None,  # the ctx exposes no sessionManager
                "harness_tool": "ctx_glob",
            },
            "the script's stdin must be EXACTLY the neutral JSON the shim built "
            "for this event -- not a subset, not re-ordered, not stringified twice",
        )

    def test_a_different_event_produces_a_different_exact_echo(self):
        """Guards against a stub that always pipes a fixed literal instead
        of the real, per-call payload."""
        _, ext_path = self._echo_extension()
        event = {
            "type": "tool_call",
            "toolCallId": "probe-2",
            "toolName": "ctx_tree",
            "input": {"path": "/srv/other-project", "__probe": "second-distinct-marker"},
        }
        cwd = "/srv/other-project"
        loaded = self._drive(ext_path, event=event, ctx={"cwd": cwd})
        result = loaded["handlerResult"]
        self.assertTrue(result and result.get("block"))
        echoed = json.loads(result["reason"])
        self.assertEqual(
            echoed,
            {
                "tool_name": "ctx_tree",
                "tool_input": {"path": "/srv/other-project", "__probe": "second-distinct-marker"},
                "cwd": cwd,
                "session_id": None,
                "harness_tool": "ctx_tree",
            },
        )
        self.assertNotEqual(
            echoed["tool_input"].get("__probe"), "transport-fidelity-xyz",
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


# --------------------------------------------------------------------------
# \u00a7S3 (C2) -- the neutral payload contract: the shim maps a Pi ToolCallEvent
# into the neutral shape (tool_name, tool_input, cwd, harness_tool, and --
# structurally only, see below -- session_id) BEFORE it reaches the script's
# stdin. One subtest per row of the CR's mapping table, proven via the same
# echo-stdin fixture \u00a7S2 already used for byte-faithful transport.
#
# session_id note: ctx.sessionManager.getSessionId() is a live METHOD on the
# real ExtensionContext -- not something a JSON-only test payload can supply
# (no functions cross the stdin JSON boundary this harness drives handlers
# through). This test therefore asserts the key's PRESENCE (the schema
# declares it unconditionally) without pinning a derivation formula that
# this exact harness mechanism cannot exercise faithfully either way.
# --------------------------------------------------------------------------

class PiHookNeutralPayloadMappingTest(PiLoaderTestCase):
    def _echo_extension(self):
        report, ts_files = self._compile({
            "event": "pre-tool-use",
            "matcher": "*",
            "command": "echo-stdin",
            "tier": "core",
            "timeout": 3,
            "fail_direction": "open",
        })
        self.assertEqual(len(ts_files), 1)
        self.assertNotIn("refusals", report)  # CR-MDB-031 §S1: no refusal path
        return ts_files[0]

    def _echoed_neutral_payload(self, ext_path, tool_name, tool_input, cwd):
        event = {
            "type": "tool_call",
            "toolCallId": "map-" + tool_name,
            "toolName": tool_name,
            "input": tool_input,
        }
        loaded = self._drive(ext_path, event=event, ctx={"cwd": cwd})
        self.assertIsNone(loaded["importError"], f"import failed: {loaded['importError']!r}")
        self.assertIsNone(loaded["handlerThrew"], f"handler threw: {loaded['handlerThrew']!r}")
        result = loaded["handlerResult"]
        self.assertIsNotNone(result, "expected a block result from the echo script (exit 2)")
        self.assertTrue(result.get("block"), f"expected block: true, got {result!r}")
        return json.loads(result["reason"])

    # One subtest per \u00a7S3 mapping-table row (plus the ctx_execute
    # non-shell-language boundary and the "any other tool" catch-all row).
    _MAPPING_TABLE_CASES = [
        ("bash toolName -> neutral bash", "bash",
         {"command": "echo hi", "timeout": 30},
         "bash", {"command": "echo hi"}),
        ("ctx_shell toolName -> neutral bash", "ctx_shell",
         {"command": "ls -la"},
         "bash", {"command": "ls -la"}),
        ("ctx_execute language=shell -> neutral bash", "ctx_execute",
         {"language": "shell", "code": "echo a", "timeout": 5},
         "bash", {"command": "echo a"}),
        ("ctx_execute language=bash -> neutral bash", "ctx_execute",
         {"language": "bash", "code": "echo b"},
         "bash", {"command": "echo b"}),
        ("ctx_execute language=sh -> neutral bash", "ctx_execute",
         {"language": "sh", "code": "echo c"},
         "bash", {"command": "echo c"}),
        ("write toolName -> neutral write", "write",
         {"path": "/work/project/out.txt", "content": "hello"},
         "write", {"path": "/work/project/out.txt", "paths": ["/work/project/out.txt"]}),
        ("edit toolName -> neutral edit", "edit",
         {"path": "/work/project/a.py", "edits": [{"oldText": "x", "newText": "y"}]},
         "edit", {"path": "/work/project/a.py", "paths": ["/work/project/a.py"]}),
        ("ctx_edit toolName -> neutral edit", "ctx_edit",
         {"path": "/work/project/b.py", "new_string": "z"},
         "edit", {"path": "/work/project/b.py", "paths": ["/work/project/b.py"]}),
        ("ctx_patch (single path) toolName -> neutral edit", "ctx_patch",
         {"path": "/work/project/c.py", "ops": [{"op": "set_line", "line": 1, "new_text": "n"}]},
         "edit", {"path": "/work/project/c.py", "paths": ["/work/project/c.py"]}),
        ("read toolName -> neutral read", "read",
         {"path": "/work/project/d.py", "limit": 100},
         "read", {"path": "/work/project/d.py", "paths": ["/work/project/d.py"]}),
        ("grep toolName -> neutral grep", "grep",
         {"pattern": "foo", "path": "/work/project"},
         "grep", {"path": "/work/project", "paths": ["/work/project"]}),
        ("find toolName -> neutral find", "find",
         {"pattern": "*.ts", "path": "/work/project/src"},
         "find", {"path": "/work/project/src", "paths": ["/work/project/src"]}),
        ("ls toolName -> neutral ls", "ls",
         {"path": "/work/project"},
         "ls", {"path": "/work/project", "paths": ["/work/project"]}),
        ("ctx_execute language=python (NOT a shell language) -> passthrough", "ctx_execute",
         {"language": "python", "code": "print(1)"},
         "ctx_execute", {"language": "python", "code": "print(1)"}),
        ("any other tool -> passthrough under its own name, input unchanged", "ctx_glob",
         {"pattern": "**/*.ts", "max_results": 5},
         "ctx_glob", {"pattern": "**/*.ts", "max_results": 5}),
    ]

    def test_mapping_table_rows_produce_the_documented_neutral_payload(self):
        ext_path = self._echo_extension()
        cwd = "/work/project"
        for case_name, pi_tool_name, raw_input, expect_tool_name, expect_tool_input in self._MAPPING_TABLE_CASES:
            with self.subTest(row=case_name):
                payload = self._echoed_neutral_payload(ext_path, pi_tool_name, raw_input, cwd)
                self.assertEqual(
                    payload.get("tool_name"), expect_tool_name,
                    f"[{case_name}] neutral tool_name: got {payload!r}",
                )
                self.assertEqual(
                    payload.get("tool_input"), expect_tool_input,
                    f"[{case_name}] neutral tool_input (exact shape, no leaked "
                    f"extra keys): got {payload!r}",
                )
                self.assertEqual(
                    payload.get("cwd"), cwd,
                    f"[{case_name}] cwd must be carried through from ctx.cwd: got {payload!r}",
                )
                self.assertEqual(
                    payload.get("harness_tool"), pi_tool_name,
                    f"[{case_name}] harness_tool must be the ORIGINAL Pi toolName "
                    f"(audit only): got {payload!r}",
                )
                self.assertIn(
                    "session_id", payload,
                    f"[{case_name}] the neutral payload must carry a session_id key: got {payload!r}",
                )

    def test_ctx_patch_collects_every_operation_path_into_paths(self):
        """\u00a7S3 prose beyond the table: "every per-operation path a ctx_patch
        call carries, into paths" -- a SECOND operation targeting a distinct
        path must also land in the neutral tool_input.paths list, not just
        the top-level/primary path."""
        ext_path = self._echo_extension()
        payload = self._echoed_neutral_payload(
            ext_path, "ctx_patch",
            {
                "path": "/work/project/a.py",
                "ops": [
                    {"op": "set_line", "line": 3, "new_text": "x = 1"},
                    {"op": "create", "path": "/etc/outside/b.py", "new_text": "y = 2"},
                ],
            },
            cwd="/work/project",
        )
        self.assertEqual(payload.get("tool_name"), "edit")
        self.assertCountEqual(
            payload.get("tool_input", {}).get("paths"),
            ["/work/project/a.py", "/etc/outside/b.py"],
            f"every per-operation path must land in tool_input.paths: got {payload!r}",
        )
        self.assertEqual(payload.get("harness_tool"), "ctx_patch")


# --------------------------------------------------------------------------
# \u00a7S3 (C2) -- zero Claude Code tool-name/file_path literals survive in the
# ported protocol scripts, and schema.md documents the neutral payload shape
# plus \u00a7S3's Pi-toolName mapping.
# --------------------------------------------------------------------------

class ScriptVocabularyAndSchemaDocTest(unittest.TestCase):
    """AC (\u00a7S3): grep gate over hooks-src/scripts/* + schema.md doc checks.

    \u00a7S7's cycle-todo-naming guard retirement moved into THIS cycle (C2) --
    its script's own removal, and every reference to its name, is
    tests/test_hook_retirement.py's job (the ONE module allowed to spell
    it). This gate still scans the WHOLE hooks-src/scripts/* directory
    (the AC's literal scope) for the SIX SURVIVING scripts' vocabulary
    (`Bash`/`Write`/`Edit`/`NotebookEdit`/`TaskCreate`/`MultiEdit`/
    `file_path`); it would ALSO catch the retired script's own leftover
    `TaskCreate` reference if that file still physically exists when this
    runs -- a second, independent signal alongside
    tests/test_hook_retirement.py's dedicated existence check, not a
    duplicate of it (this gate's job is the SIX-script vocabulary; the
    retired script's presence/absence is incidental to it).
    """

    _FORBIDDEN_LITERALS = (
        '"Bash"', '"Write"', '"Edit"', '"NotebookEdit"', '"TaskCreate"',
        '"MultiEdit"', "file_path",
    )

    def test_zero_claude_code_tool_vocabulary_literals_in_protocol_scripts(self):
        self.assertTrue(REAL_SCRIPTS_ROOT.is_dir(), f"expected {REAL_SCRIPTS_ROOT}")
        failures = []
        for path in sorted(REAL_SCRIPTS_ROOT.iterdir()):
            if not path.is_file():
                continue
            text = path.read_text(encoding="utf-8")
            for literal in self._FORBIDDEN_LITERALS:
                if literal in text:
                    failures.append(f"{path.name}: contains forbidden literal {literal!r}")
        # POSITIVE/EXACT -- zero occurrences across the whole script library.
        self.assertEqual(failures, [], "\n".join(failures))

    def test_schema_md_documents_the_neutral_payload_fields(self):
        self.assertTrue(SCHEMA_MD.is_file(), f"expected {SCHEMA_MD}")
        content = SCHEMA_MD.read_text(encoding="utf-8")
        for field in ("tool_name", "tool_input", "harness_tool", "session_id", "neutral payload"):
            self.assertIn(
                field, content,
                f"schema.md must document '{field}' (the \u00a7S3 neutral payload contract)",
            )

    def test_schema_md_documents_s3_pi_tool_name_mapping(self):
        self.assertTrue(SCHEMA_MD.is_file(), f"expected {SCHEMA_MD}")
        content = SCHEMA_MD.read_text(encoding="utf-8")
        for pi_tool_name in ("ctx_shell", "ctx_execute", "ctx_edit", "ctx_patch"):
            self.assertIn(
                pi_tool_name, content,
                f"schema.md must document the {pi_tool_name!r} -> neutral "
                f"tool_name mapping (\u00a7S3's table)",
            )


# --------------------------------------------------------------------------
# \u00a7S3 (C2) -- block-write-outside-worktree through EVERY tool \u00a7S3's table
# maps to the file class: write, edit, ctx_edit, ctx_patch (incl. a second
# operation targeting the outside path), plus an allowed read -- all through
# the REAL hooks-src/scripts/block-write-outside-worktree script, driven
# through the emitted pi shim (never invoked as a bare subprocess).
# --------------------------------------------------------------------------

class PiHookWriteBoundaryAcrossToolsTest(PiLoaderTestCase):
    def setUp(self):
        super().setUp()
        self._worktree_root = Path(tempfile.mkdtemp(dir=self.target))

    def _compile_guard(self):
        report, ts_files = self._compile(
            {
                "event": "pre-tool-use",
                "matcher": "write|edit",
                "command": "block-write-outside-worktree",
                "tier": "core",
                "timeout": 5,
                "fail_direction": "closed",
            },
            scripts_root=REAL_SCRIPTS_ROOT,
        )
        self.assertEqual(len(ts_files), 1)
        self.assertNotIn("refusals", report)  # CR-MDB-031 §S1: no refusal path
        return ts_files[0]

    def _drive_guard(self, ext_path, tool_name, tool_input):
        event = {
            "type": "tool_call",
            "toolCallId": "wb-" + tool_name,
            "toolName": tool_name,
            "input": tool_input,
        }
        with mock.patch.dict(os.environ, {"WF_WORKTREE_ROOT": str(self._worktree_root)}):
            loaded = self._drive(ext_path, event=event, ctx={"cwd": str(self._worktree_root)})
        self.assertIsNone(loaded["importError"], f"import failed: {loaded['importError']!r}")
        self.assertIsNone(loaded["handlerThrew"], f"handler threw: {loaded['handlerThrew']!r}")
        return loaded["handlerResult"]

    def test_blocks_write_outside_worktree_through_every_file_class_tool(self):
        ext_path = self._compile_guard()
        outside = "/etc/modelb-hooks-outside-fixture-s3.txt"
        cases = [
            ("write", "write", {"path": outside, "content": "x"}),
            ("edit", "edit", {"path": outside, "edits": [{"oldText": "a", "newText": "b"}]}),
            ("ctx_edit", "ctx_edit", {"path": outside, "new_string": "z"}),
            ("ctx_patch (single op)", "ctx_patch",
             {"path": outside, "ops": [{"op": "set_line", "line": 1, "new_text": "x"}]}),
        ]
        for case_name, tool_name, tool_input in cases:
            with self.subTest(tool=case_name):
                result = self._drive_guard(ext_path, tool_name, tool_input)
                self.assertIsInstance(result, dict, f"[{case_name}] expected a block result, got {result!r}")
                self.assertIs(result.get("block"), True, f"[{case_name}] must block: {result!r}")
                self.assertIn(
                    "worktree", (result.get("reason") or "").lower(),
                    f"[{case_name}] reason must name the worktree boundary: {result!r}",
                )

    def test_blocks_ctx_patch_when_only_the_second_operation_targets_outside_the_worktree(self):
        ext_path = self._compile_guard()
        inside = str(self._worktree_root / "src" / "main.py")
        outside = "/etc/modelb-hooks-outside-fixture-s3-secondop.txt"
        result = self._drive_guard(
            ext_path, "ctx_patch",
            {
                "path": inside,
                "ops": [
                    {"op": "set_line", "line": 1, "new_text": "x"},
                    {"op": "insert_after", "path": outside, "new_text": "y"},
                ],
            },
        )
        self.assertIsInstance(result, dict, f"expected a block result, got {result!r}")
        self.assertIs(result.get("block"), True, f"must block on the SECOND operation's outside path: {result!r}")
        self.assertIn("worktree", (result.get("reason") or "").lower())

    def test_allows_a_read_outside_the_worktree(self):
        """Regression pin, not new-behaviour RED: `read` was never in the
        script's gated tool_name set even before this CR's \u00a7S3/\u00a7S4 port
        (Write|Edit|NotebookEdit pre-port, write|edit post-port -- `read` is
        outside both), so this already passes pre-GREEN. It stays here as
        the AC's own explicit companion assertion to the block cases above,
        proving §S3's mapping (`read` -> neutral `read`, never `write`/
        `edit`) and §S4's matcher (`write|edit` not matching `read`) do NOT
        regress this safety invariant once they land -- it would fail if a
        future mapping bug folded `read` into the gated file class, or if
        the matcher were ever loosened past `write|edit`."""
        ext_path = self._compile_guard()
        outside = "/etc/modelb-hooks-outside-fixture-s3-read.txt"
        result = self._drive_guard(ext_path, "read", {"path": outside})
        self.assertEqual(
            result, {},
            f"a read (not write|edit-matched, and not a gated neutral tool_name "
            f"even if it were) must allow: {result!r}",
        )


# --------------------------------------------------------------------------
# \u00a7S3 (C2) -- block-direct-cargo-test / block-direct-mvn-test through bash,
# ctx_shell, and a shell-language ctx_execute, against the REAL scripts
# driven through the emitted pi shim.
# --------------------------------------------------------------------------

class PiHookCargoMvnGuardAcrossToolsTest(PiLoaderTestCase):
    def _compile_guard(self, command):
        report, ts_files = self._compile(
            {
                "event": "pre-tool-use",
                "matcher": "bash",
                "command": command,
                "tier": "core",
                "timeout": 5,
                "fail_direction": "closed",
            },
            scripts_root=REAL_SCRIPTS_ROOT,
        )
        self.assertEqual(len(ts_files), 1)
        self.assertNotIn("refusals", report)  # CR-MDB-031 §S1: no refusal path
        return ts_files[0]

    def _drive_guard(self, ext_path, tool_name, tool_input, cwd):
        event = {
            "type": "tool_call",
            "toolCallId": "guard-" + tool_name,
            "toolName": tool_name,
            "input": tool_input,
        }
        loaded = self._drive(ext_path, event=event, ctx={"cwd": cwd})
        self.assertIsNone(loaded["importError"], f"import failed: {loaded['importError']!r}")
        self.assertIsNone(loaded["handlerThrew"], f"handler threw: {loaded['handlerThrew']!r}")
        return loaded["handlerResult"]

    def test_block_direct_cargo_test_through_bash_ctx_shell_and_shell_ctx_execute(self):
        rust_project = Path(tempfile.mkdtemp(dir=self.target))
        (rust_project / "Cargo.toml").write_text('[package]\nname = "fixture"\n', encoding="utf-8")
        ext_path = self._compile_guard("block-direct-cargo-test")
        cases = [
            ("bash", "bash", {"command": "cargo test -p fixture"}),
            ("ctx_shell", "ctx_shell", {"command": "cargo test -p fixture"}),
            ("ctx_execute (language=bash)", "ctx_execute", {"language": "bash", "code": "cargo test -p fixture"}),
        ]
        for case_name, tool_name, tool_input in cases:
            with self.subTest(tool=case_name):
                result = self._drive_guard(ext_path, tool_name, tool_input, cwd=str(rust_project))
                self.assertIsInstance(result, dict, f"[{case_name}] expected a block result, got {result!r}")
                self.assertIs(result.get("block"), True, f"[{case_name}] must block: {result!r}")
                self.assertIn(
                    "rust-crucible", (result.get("reason") or "").lower(),
                    f"[{case_name}] reason must point at the rust-crucible.py wrapper: {result!r}",
                )

    def test_ctx_execute_with_a_non_shell_language_does_not_spawn_the_bash_matched_guard(self):
        """Boundary: only ctx_execute with a SHELL language (shell/bash/sh)
        maps to the neutral bash class; a python-language payload must not
        spawn a bash-matcher hook AT ALL. Proven via the counting side
        channel (not the real cargo script), because "did not spawn" and
        "spawned then the script itself allowed" both report handlerResult
        == {} and would be indistinguishable through the real script alone."""
        report, ts_files = self._compile({
            "event": "pre-tool-use",
            "matcher": "bash",
            "command": "counts-invocations",
            "tier": "core",
            "timeout": 3,
            "fail_direction": "open",
        })
        self.assertEqual(len(ts_files), 1)
        ext_path = ts_files[0]
        counter_file = self.target / "cargo-boundary-invocation-counter.txt"
        event = {
            "type": "tool_call", "toolCallId": "boundary-1", "toolName": "ctx_execute",
            "input": {"language": "python", "code": "import subprocess; subprocess.run(['cargo','test'])"},
        }
        with mock.patch.dict(os.environ, {"HOOK_INVOCATION_COUNTER_FILE": str(counter_file)}):
            loaded = self._drive(ext_path, event=event, ctx={"cwd": str(self.target)})
        self.assertIsNone(loaded["handlerThrew"], f"handler threw: {loaded['handlerThrew']!r}")
        count = len(counter_file.read_text(encoding="utf-8").splitlines()) if counter_file.is_file() else 0
        self.assertEqual(
            count, 0,
            "a non-shell-language ctx_execute (stays neutral tool_name "
            "'ctx_execute', never 'bash') must not spawn a bash-matched hook",
        )

    def test_block_direct_mvn_test_through_bash_ctx_shell_and_shell_ctx_execute(self):
        java_project = Path(tempfile.mkdtemp(dir=self.target))
        (java_project / "pom.xml").write_text("<project></project>\n", encoding="utf-8")
        ext_path = self._compile_guard("block-direct-mvn-test")
        cases = [
            ("bash", "bash", {"command": "mvn test"}),
            ("ctx_shell", "ctx_shell", {"command": "mvn test -pl module-a"}),
            ("ctx_execute (language=sh)", "ctx_execute", {"language": "sh", "code": "mvn test"}),
        ]
        for case_name, tool_name, tool_input in cases:
            with self.subTest(tool=case_name):
                result = self._drive_guard(ext_path, tool_name, tool_input, cwd=str(java_project))
                self.assertIsInstance(result, dict, f"[{case_name}] expected a block result, got {result!r}")
                self.assertIs(result.get("block"), True, f"[{case_name}] must block: {result!r}")
                self.assertIn(
                    "mvn-crucible", (result.get("reason") or "").lower(),
                    f"[{case_name}] reason must point at the mvn-crucible.py wrapper: {result!r}",
                )


# --------------------------------------------------------------------------
# \u00a7S4 (C2) -- matcher filters on the NEUTRAL name: a write|edit hook must
# not spawn for bash/ctx_shell (both map to neutral bash) and MUST spawn for
# ctx_patch (maps to neutral edit). Proven with a counting fake script since
# both "did not spawn" and "spawned and allowed" report handlerResult == {}.
# --------------------------------------------------------------------------

class PiHookMatcherFiltersOnNeutralNameTest(PiLoaderTestCase):
    def test_write_or_edit_matcher_spawns_only_for_the_mapped_edit_class_tool(self):
        report, ts_files = self._compile({
            "event": "pre-tool-use",
            "matcher": "write|edit",
            "command": "counts-invocations",
            "tier": "core",
            "timeout": 3,
            "fail_direction": "open",
        })
        self.assertEqual(len(ts_files), 1)
        self.assertNotIn("refusals", report)  # CR-MDB-031 §S1: no refusal path
        ext_path = ts_files[0]
        counter_file = self.target / "invocation-counter.txt"

        def _count():
            return len(counter_file.read_text(encoding="utf-8").splitlines()) if counter_file.is_file() else 0

        with mock.patch.dict(os.environ, {"HOOK_INVOCATION_COUNTER_FILE": str(counter_file)}):
            loaded = self._drive(
                ext_path,
                event={"type": "tool_call", "toolCallId": "m-1", "toolName": "bash", "input": {"command": "true"}},
                ctx={"cwd": str(self.target)},
            )
            self.assertIsNone(loaded["handlerThrew"])
            self.assertEqual(loaded["handlerResult"], {})
            self.assertEqual(_count(), 0, "bash (neutral bash) must NOT spawn a write|edit-matched hook")

            loaded = self._drive(
                ext_path,
                event={"type": "tool_call", "toolCallId": "m-2", "toolName": "ctx_shell", "input": {"command": "true"}},
                ctx={"cwd": str(self.target)},
            )
            self.assertIsNone(loaded["handlerThrew"])
            self.assertEqual(loaded["handlerResult"], {})
            self.assertEqual(_count(), 0, "ctx_shell (neutral bash) must NOT spawn a write|edit-matched hook")

            loaded = self._drive(
                ext_path,
                event={
                    "type": "tool_call", "toolCallId": "m-3", "toolName": "ctx_patch",
                    "input": {"path": str(self.target / "x.py"), "ops": [{"op": "set_line", "line": 1, "new_text": "x"}]},
                },
                ctx={"cwd": str(self.target)},
            )
            self.assertIsNone(loaded["handlerThrew"])
            self.assertEqual(loaded["handlerResult"], {})
            self.assertEqual(
                _count(), 1,
                "ctx_patch (neutral edit) MUST spawn the write|edit-matched hook exactly once",
            )


if __name__ == "__main__":
    unittest.main()
