"""RED-phase tests for CR-MDB-015 cycle C2 (§S4 compiler: neutral schema ->
per-harness wiring).

C1 (schema.md v1 + modelb_axi.hooks.validate_schema + the seven protocol
scripts) already shipped and stays untouched -- see tests/test_hooks.py.
This file targets ONLY the §S4 compiler, which does not exist yet on this
branch. `modelb_axi.hooks.compile_wiring` is imported INSIDE each test
method (never at module scope) so a missing symbol fails only that one
test rather than killing collection of the whole file.

PINNED CONTRACT (RED-authored -- none of this exists in code yet; GREEN
implements against this pin, not the other way around):

    modelb_axi.hooks.compile_wiring(
        schema_instances: list[dict],
        harnesses: list[str],
        target: pathlib.Path,
        scripts_root: pathlib.Path,
    ) -> dict

Harness ids are the four from modelb_axi.harness.HARNESS_ROSTER_IDS:
"claude-code", "hermes", "pi", "opencode".

Emission targets (all relative to `target`, which is always a tmp dir --
never the real project or `~/.claude`; `scripts_root` is the real
hooks-src/scripts/ tree, referenced by absolute path, never copied):

  * claude-code -> `.claude/settings.json`. Structure:
    `{"hooks": {"<EventKey>": [{"matcher": <str>, "hooks": [{"type":
    "command", "command": "<scripts_root>/<name>", "timeout": <int
    seconds>}]}]}}`. Event-key mapping (v1, pinned here since neither the
    CR spec nor the DN fixes exact per-harness key casing):
    pre-tool-use -> "PreToolUse", session-start -> "SessionStart".
    `fail_direction=open` guards are emitted normally (claude-code is a
    fail-open harness per DN §2's survey point -- "others fail-open").

  * opencode -> a generated TS spawn-shim file under `.opencode/` whose
    text (pinned as substring markers only, not TS semantics) contains a
    subprocess spawn of the protocol script's absolute path and maps
    exit code 2 to a block result (`{ block: true` marker).

  * pi -> `.pi/extensions/<name>.ts` (DN §2 roster addendum: pi has FULL
    TS-extension support). Text subscribes `session_start` (ambient) and
    `tool_call` (guard), spawns via `pi.exec`, returns `{ block: true` on
    exit 2. pi honors fail-closed (DN: "Fail-closed IS honorable (shim
    blocks on spawn failure)") so a `fail_direction=closed` guard is
    EMITTED for pi, never refused.

  * hermes -> NO project-level wiring file at all (DN: "no project-level
    hook declaration exists" for Hermes). Instead an ADVISORY snippet at
    `hooks/hermes-manual.yaml` under `target` containing the user-scope
    `~/.hermes/config.yaml` shape plus a consent-allowlist note
    (`~/.hermes/shell-hooks-allowlist.json`). `fail_direction=closed`
    guards are REFUSED for hermes (DN: "blocking semantics unverifiable").

  * claude-code is ALSO a fail-open harness (DN §2: "fail-direction
    diverges (Copilot preToolUse fail-closed, others fail-open)" --
    Copilot is outside the settled four-harness roster, so "others"
    covers claude-code here): a `fail_direction=closed` guard is REFUSED
    for claude-code too, named in the report.

Report shape (pinned): `dict` keyed by harness id; each value a `dict`
with keys `emitted_files` (list[str], paths relative to `target`),
`refusals` (list[dict] each `{"command": str, "reason": str}`),
`degraded` (bool), `notes` (list[str]). Every input schema-instance
`command` must be accounted for per harness -- either present in
`emitted_files` content, in `refusals`, or explained by a `degraded`
note; nothing silent (AC4/AC6).

Error state (AC5): `compile_wiring` returns the report dict normally
whenever AT LEAST ONE harness emits at least one hook. When EVERY
requested harness refuses EVERY hook (zero wiring emitted anywhere), it
raises `modelb_axi.hooks.AllTargetsRefusedError` (a distinct exception,
not a silent empty report) naming the refused command(s).

Stdlib only: unittest + json + tempfile + shutil + pathlib.
"""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_ROOT = REPO_ROOT / "hooks-src" / "scripts"

# Sample schema instances shared across tests (AC4 happy path): one
# fail_direction=open security-class guard (pre-tool-use) + one ambient
# informational hook (session-start) -- exactly the prompt's pinned pair.
CARGO_GUARD_OPEN = {
    "event": "pre-tool-use",
    "matcher": "bash",
    "command": "block-direct-cargo-test",
    "tier": "core",
    "timeout": 5,
    "fail_direction": "open",
}

AMBIENT_STATUS = {
    "event": "session-start",
    "matcher": "*",
    "command": "ambient-board-status",
    "tier": "core",
    "timeout": 3,
    "fail_direction": None,
}

# AC5: a security-class guard declaring fail_direction=closed.
WRITE_GUARD_CLOSED = {
    "event": "pre-tool-use",
    "matcher": "write|edit",
    "command": "block-write-outside-worktree",
    "tier": "core",
    "timeout": 5,
    "fail_direction": "closed",
}

# F1 (VERIFY B2): pi event-map instances. turn-stop/prompt-submit are SOURCED
# pi events (`turn_end`/`input`, DN §2 roster addendum event-map citations);
# pre-compact has NO pi counterpart -- declared gap, never silently dropped.
TURN_STOP_HOOK = {
    "event": "turn-stop",
    "matcher": "*",
    "command": "post-regression-disk-reminder",
    "tier": "core",
    "timeout": 3,
    "fail_direction": None,
}

PROMPT_SUBMIT_HOOK = {
    "event": "prompt-submit",
    "matcher": "*",
    "command": "ambient-board-status",
    "tier": "core",
    "timeout": 3,
    "fail_direction": None,
}

PRE_COMPACT_HOOK = {
    "event": "pre-compact",
    "matcher": "*",
    "command": "post-regression-disk-reminder",
    "tier": "core",
    "timeout": 3,
    "fail_direction": None,
}


class HooksCompilerTestCase(unittest.TestCase):
    """Common tmp-target fixture; never writes outside `tempfile.mkdtemp()`."""

    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="modelb-hooks-compiler-")
        self.target = Path(self._tmp)

    def tearDown(self):
        shutil.rmtree(self._tmp, ignore_errors=True)


class ClaudeCodeEmitterTest(HooksCompilerTestCase):
    """AC4 claude-code: `.claude/settings.json` wiring for the happy-path
    sample (fail_direction=open guard + ambient session-start hook)."""

    def test_settings_json_has_correct_event_matcher_command_and_timeout(self):
        from modelb_axi.hooks import compile_wiring

        compile_wiring(
            schema_instances=[CARGO_GUARD_OPEN, AMBIENT_STATUS],
            harnesses=["claude-code"],
            target=self.target,
            scripts_root=SCRIPTS_ROOT,
        )

        settings_path = self.target / ".claude" / "settings.json"
        self.assertTrue(
            settings_path.is_file(),
            f"expected {settings_path} to be emitted for claude-code",
        )
        raw = settings_path.read_text(encoding="utf-8")
        settings = json.loads(raw)  # must be valid, parseable JSON

        pre_tool_use = settings["hooks"]["PreToolUse"]
        self.assertEqual(len(pre_tool_use), 1)
        cargo_entry = pre_tool_use[0]
        # CR-MDB-030 §S4: the emitter translates the neutral matcher into
        # Claude Code's own tool name -- never the neutral `bash`.
        self.assertEqual(cargo_entry["matcher"], "Bash")
        cargo_cmd = cargo_entry["hooks"][0]
        expected_cargo_path = str(SCRIPTS_ROOT / "block-direct-cargo-test")
        self.assertEqual(cargo_cmd["command"], expected_cargo_path)
        self.assertEqual(cargo_cmd["timeout"], 5)

        session_start = settings["hooks"]["SessionStart"]
        self.assertEqual(len(session_start), 1)
        ambient_cmd = session_start[0]["hooks"][0]
        expected_ambient_path = str(SCRIPTS_ROOT / "ambient-board-status")
        self.assertEqual(ambient_cmd["command"], expected_ambient_path)
        self.assertEqual(ambient_cmd["timeout"], 3)

        # Negative/bound: exactly these two events, nothing extra invented.
        self.assertEqual(set(settings["hooks"].keys()), {"PreToolUse", "SessionStart"})

    def test_settings_json_matcher_uses_claude_code_tool_names(self):
        """CR-MDB-030 §S4 / AC: `.claude/settings.json` carries Claude Code's
        own tool names for every neutral matcher -- each class in §S4's
        table, an alternation translated per member, and a name with no
        Claude Code equivalent passed through unchanged. One subtest per
        row. Instances are `open` so claude-code emits rather than refuses."""
        from modelb_axi.hooks import compile_wiring

        cases = [
            ("bash", "Bash"),
            ("write", "Write"),
            ("edit", "Edit|MultiEdit|NotebookEdit"),
            ("read", "Read"),
            ("grep", "Grep"),
            ("find", "Glob"),
            ("ls", "LS"),
            ("write|edit", "Write|Edit|MultiEdit|NotebookEdit"),
            ("bash|read", "Bash|Read"),
            ("mcp__example__tool", "mcp__example__tool"),
            ("*", "*"),
        ]
        for neutral, expected in cases:
            with self.subTest(neutral=neutral):
                target = self.target / neutral.replace("|", "_").replace("*", "star")
                instance = {
                    "event": "pre-tool-use",
                    "matcher": neutral,
                    "command": "block-direct-cargo-test",
                    "tier": "core",
                    "timeout": 5,
                    "fail_direction": "open",
                }
                compile_wiring(
                    schema_instances=[instance],
                    harnesses=["claude-code"],
                    target=target,
                    scripts_root=SCRIPTS_ROOT,
                )
                settings = json.loads(
                    (target / ".claude" / "settings.json").read_text(encoding="utf-8")
                )
                entries = settings["hooks"]["PreToolUse"]
                self.assertEqual(len(entries), 1)
                self.assertEqual(
                    entries[0]["matcher"], expected,
                    f"§S4: neutral matcher {neutral!r} must be written as "
                    f"Claude Code's {expected!r} in settings.json",
                )

    def test_fail_open_guard_is_emitted_not_refused_for_claude_code(self):
        from modelb_axi.hooks import compile_wiring

        report = compile_wiring(
            schema_instances=[CARGO_GUARD_OPEN, AMBIENT_STATUS],
            harnesses=["claude-code"],
            target=self.target,
            scripts_root=SCRIPTS_ROOT,
        )

        cc_report = report["claude-code"]
        self.assertEqual(cc_report["refusals"], [])
        self.assertFalse(cc_report["degraded"])
        self.assertIn(".claude/settings.json", cc_report["emitted_files"])


class OpenCodeEmitterTest(HooksCompilerTestCase):
    """AC4 opencode: generated TS spawn-shim plugin."""

    def test_ts_shim_spawns_protocol_script_and_maps_exit_two_to_block(self):
        from modelb_axi.hooks import compile_wiring

        report = compile_wiring(
            schema_instances=[CARGO_GUARD_OPEN, AMBIENT_STATUS],
            harnesses=["opencode"],
            target=self.target,
            scripts_root=SCRIPTS_ROOT,
        )

        oc_report = report["opencode"]
        self.assertFalse(oc_report["degraded"])
        self.assertEqual(oc_report["refusals"], [])
        self.assertTrue(oc_report["emitted_files"], "opencode should emit at least one file")

        ts_text = ""
        for rel in oc_report["emitted_files"]:
            path = self.target / rel
            self.assertTrue(path.is_file(), f"reported file {rel} missing on disk")
            ts_text += path.read_text(encoding="utf-8")

        expected_cargo_path = str(SCRIPTS_ROOT / "block-direct-cargo-test")
        self.assertIn(expected_cargo_path, ts_text)
        self.assertIn("exit", ts_text.lower())
        self.assertIn("2", ts_text)
        self.assertIn("{ block: true", ts_text)

    def test_closed_guard_emitted_for_opencode_with_spawn_failure_block_path(self):
        """F1 (VERIFY B1): opencode honors fail-closed -- the closed guard is
        EMITTED (not refused) and the generated shim BLOCKS on spawn failure
        (status null / thrown), mirroring the pi spawn-shim semantics."""
        from modelb_axi.hooks import compile_wiring

        report = compile_wiring(
            schema_instances=[WRITE_GUARD_CLOSED],
            harnesses=["opencode"],
            target=self.target,
            scripts_root=SCRIPTS_ROOT,
        )

        oc_report = report["opencode"]
        self.assertEqual(oc_report["refusals"], [])
        self.assertTrue(
            oc_report["emitted_files"],
            "fail-closed guard must be emitted for opencode, not dropped",
        )

        ts_text = ""
        for rel in oc_report["emitted_files"]:
            ts_text += (self.target / rel).read_text(encoding="utf-8")

        expected_guard_path = str(SCRIPTS_ROOT / "block-write-outside-worktree")
        self.assertIn(expected_guard_path, ts_text)
        # The failure-path block marker: spawn failure -> BLOCK with a reason
        # naming the spawn failure (fail-closed honored, never silently open).
        self.assertIn("fail-closed guard: hook spawn failed", ts_text)
        self.assertIn("{ block: true", ts_text)


class PiExtensionEmitterTest(HooksCompilerTestCase):
    """AC4 pi: `.pi/extensions/<name>.ts` -- full TS-extension emitter."""

    def test_extension_default_exports_a_factory_and_never_uses_pi_exec(self):
        """MIGRATED (CR-MDB-030 §S1/§S2, C1): the pre-030 characterization
        asserted `pi.on(...)` at module top level (no default export -- the
        loader drops it) and `pi.exec` (no `stdin` option on 0.87.1's
        `ExecOptions`, so no script ever received its payload). The 030
        contract is a default-export factory that never spawns via
        `pi.exec` -- runtime-loadability is proven separately by
        tests/test_pi_hook_runtime.py::DefaultExportFactoryTest, which
        drives the REAL emitted file through Pi's own jiti loader."""
        from modelb_axi.hooks import compile_wiring

        report = compile_wiring(
            schema_instances=[CARGO_GUARD_OPEN, AMBIENT_STATUS],
            harnesses=["pi"],
            target=self.target,
            scripts_root=SCRIPTS_ROOT,
        )

        pi_report = report["pi"]
        self.assertFalse(pi_report["degraded"])
        self.assertEqual(pi_report["refusals"], [])

        extensions_dir = self.target / ".pi" / "extensions"
        ts_files = list(extensions_dir.glob("*.ts")) if extensions_dir.is_dir() else []
        self.assertTrue(
            ts_files, f"expected at least one .ts file under {extensions_dir}"
        )
        combined = "".join(p.read_text(encoding="utf-8") for p in ts_files)

        self.assertIn("export default function", combined)
        self.assertNotIn(
            "pi.exec(", combined,
            "§S2: pi.exec has no stdin option -- the shim must pipe stdin via "
            "node:child_process instead",
        )
        self.assertIn("node:child_process", combined)
        self.assertIn("session_start", combined)
        self.assertIn("tool_call", combined)
        self.assertIn("{ block: true", combined)
        expected_cargo_path = str(SCRIPTS_ROOT / "block-direct-cargo-test")
        self.assertIn(expected_cargo_path, combined)

        # Trust-gate re-confirm step (DN §4.5) must be documented, not silent.
        self.assertTrue(
            any("trust" in note.lower() for note in pi_report["notes"]),
            f"expected a project-trust re-confirm note in pi report notes: {pi_report['notes']!r}",
        )

    def test_closed_fail_direction_guard_is_emitted_for_pi_not_refused(self):
        """DN §2 roster addendum: pi's spawn shim blocks on spawn failure,
        so fail-closed IS honorable -- unlike claude-code/hermes."""
        from modelb_axi.hooks import compile_wiring

        report = compile_wiring(
            schema_instances=[WRITE_GUARD_CLOSED],
            harnesses=["pi"],
            target=self.target,
            scripts_root=SCRIPTS_ROOT,
        )

        pi_report = report["pi"]
        self.assertEqual(pi_report["refusals"], [])
        self.assertTrue(pi_report["emitted_files"])
        extensions_dir = self.target / ".pi" / "extensions"
        ts_files = list(extensions_dir.glob("*.ts"))
        combined = "".join(p.read_text(encoding="utf-8") for p in ts_files)
        expected_guard_path = str(SCRIPTS_ROOT / "block-write-outside-worktree")
        self.assertIn(expected_guard_path, combined)

    def test_turn_stop_and_prompt_submit_map_to_sourced_pi_events(self):
        """F1 (VERIFY B2): turn-stop -> `turn_end`, prompt-submit -> `input`
        (DN §2 roster addendum event-map citations; both SOURCED)."""
        from modelb_axi.hooks import compile_wiring

        report = compile_wiring(
            schema_instances=[TURN_STOP_HOOK, PROMPT_SUBMIT_HOOK],
            harnesses=["pi"],
            target=self.target,
            scripts_root=SCRIPTS_ROOT,
        )

        pi_report = report["pi"]
        self.assertEqual(pi_report["refusals"], [])
        self.assertEqual(len(pi_report["emitted_files"]), 2)

        extensions_dir = self.target / ".pi" / "extensions"
        combined = "".join(
            p.read_text(encoding="utf-8") for p in extensions_dir.glob("*.ts")
        )
        self.assertIn('pi.on("turn_end"', combined)
        self.assertIn('pi.on("input"', combined)

    def test_pre_compact_maps_to_session_before_compact_and_is_emitted(self):
        """MIGRATED (CR-MDB-030 \u00a7S5, C1): pre-compact's pi counterpart is
        `session_before_compact` -- it is EMITTED, not a declared gap, and
        the old 'no documented pi counterpart' note is gone. Runtime
        registration through the real jiti loader is proven separately by
        tests/test_pi_hook_runtime.py::DefaultExportFactoryTest
        ::test_pre_compact_maps_to_session_before_compact_and_registers_it."""
        from modelb_axi.hooks import compile_wiring

        report = compile_wiring(
            schema_instances=[PRE_COMPACT_HOOK],
            harnesses=["pi"],
            target=self.target,
            scripts_root=SCRIPTS_ROOT,
        )

        pi_report = report["pi"]
        self.assertEqual(pi_report["refusals"], [])
        self.assertFalse(pi_report["degraded"])
        self.assertEqual(
            pi_report["emitted_files"],
            [str(Path(".pi") / "extensions" / "post-regression-disk-reminder.ts")],
        )

        ext_file = (
            self.target / ".pi" / "extensions" / "post-regression-disk-reminder.ts"
        )
        self.assertTrue(ext_file.is_file())
        text = ext_file.read_text(encoding="utf-8")
        self.assertIn('pi.on("session_before_compact"', text)

        stale_notes = [
            n for n in pi_report["notes"]
            if "no" in n.lower() and "counterpart" in n.lower()
        ]
        self.assertEqual(
            stale_notes, [],
            f"the 'no documented pi counterpart' note must be gone: {pi_report['notes']!r}",
        )


class HermesDegradationTest(HooksCompilerTestCase):
    """AC4 hermes: declared degradation, no project wiring, advisory
    snippet only."""

    def test_emits_no_project_level_wiring_file(self):
        from modelb_axi.hooks import compile_wiring

        compile_wiring(
            schema_instances=[CARGO_GUARD_OPEN, AMBIENT_STATUS],
            harnesses=["hermes"],
            target=self.target,
            scripts_root=SCRIPTS_ROOT,
        )

        # No `.hermes/` project directory and no `.claude`-style wiring --
        # Hermes has no project-level hook declaration (DN §2).
        self.assertFalse((self.target / ".hermes").exists())

    def test_advisory_snippet_declares_degradation_with_user_scope_shape(self):
        from modelb_axi.hooks import compile_wiring

        report = compile_wiring(
            schema_instances=[CARGO_GUARD_OPEN, AMBIENT_STATUS],
            harnesses=["hermes"],
            target=self.target,
            scripts_root=SCRIPTS_ROOT,
        )

        hermes_report = report["hermes"]
        self.assertTrue(hermes_report["degraded"])
        self.assertTrue(
            hermes_report["notes"], "hermes report must declare the degradation, never silently"
        )

        advisory_path = self.target / "hooks" / "hermes-manual.yaml"
        self.assertTrue(
            advisory_path.is_file(),
            f"expected advisory snippet at {advisory_path}",
        )
        text = advisory_path.read_text(encoding="utf-8")
        self.assertIn("~/.hermes/config.yaml", text)
        self.assertIn("allowlist", text.lower())
        expected_cargo_path = str(SCRIPTS_ROOT / "block-direct-cargo-test")
        self.assertIn(expected_cargo_path, text)


class ReportAccountingTest(HooksCompilerTestCase):
    """AC4/AC6 report shape: every input hook accounted for per harness,
    nothing silent."""

    def test_report_accounts_for_every_hook_across_all_four_harnesses(self):
        from modelb_axi.hooks import compile_wiring

        harnesses = ["claude-code", "opencode", "pi", "hermes"]
        report = compile_wiring(
            schema_instances=[CARGO_GUARD_OPEN, AMBIENT_STATUS],
            harnesses=harnesses,
            target=self.target,
            scripts_root=SCRIPTS_ROOT,
        )

        self.assertEqual(set(report.keys()), set(harnesses))

        for harness in harnesses:
            entry = report[harness]
            for key in ("emitted_files", "refusals", "degraded", "notes"):
                self.assertIn(key, entry, f"{harness} report missing {key!r} key")

            if entry["degraded"]:
                # Degraded harnesses (hermes) must still name why, in notes.
                self.assertTrue(entry["notes"])
            else:
                # Non-degraded harnesses emitted something for our 2 hooks.
                self.assertTrue(
                    entry["emitted_files"],
                    f"{harness} neither degraded nor emitted anything",
                )


class RefusalTest(HooksCompilerTestCase):
    """AC5: fail_direction=closed refusal for harnesses that cannot honor
    fail-closed, non-error overall when another target still emits, and a
    distinct error state when every target refuses."""

    def test_closed_guard_refused_for_claude_code_and_hermes_with_named_reason(self):
        from modelb_axi.hooks import compile_wiring

        report = compile_wiring(
            schema_instances=[WRITE_GUARD_CLOSED],
            harnesses=["claude-code", "hermes", "pi"],
            target=self.target,
            scripts_root=SCRIPTS_ROOT,
        )

        cc_refusals = report["claude-code"]["refusals"]
        self.assertEqual(len(cc_refusals), 1)
        self.assertEqual(cc_refusals[0]["command"], "block-write-outside-worktree")
        self.assertTrue(cc_refusals[0]["reason"])

        hermes_refusals = report["hermes"]["refusals"]
        self.assertEqual(len(hermes_refusals), 1)
        self.assertEqual(hermes_refusals[0]["command"], "block-write-outside-worktree")
        self.assertTrue(hermes_refusals[0]["reason"])

        # pi honors fail-closed -- not refused, per DN §2 roster addendum.
        self.assertEqual(report["pi"]["refusals"], [])

        # No wiring file emitted for claude-code (the sole hook was refused).
        self.assertNotIn(".claude/settings.json", report["claude-code"]["emitted_files"])

    def test_all_targets_refused_raises_distinct_error(self):
        from modelb_axi.hooks import AllTargetsRefusedError, compile_wiring

        with self.assertRaises(AllTargetsRefusedError) as ctx:
            compile_wiring(
                schema_instances=[WRITE_GUARD_CLOSED],
                harnesses=["claude-code", "hermes"],
                target=self.target,
                scripts_root=SCRIPTS_ROOT,
            )

        self.assertIn("block-write-outside-worktree", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
