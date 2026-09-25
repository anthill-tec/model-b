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

The roster is Pi alone (CR-MDB-031 §S1): modelb_axi.harness.HARNESS_ROSTER_IDS
== ("pi",). The claude-code / opencode / hermes emitters, their refusal path and
AllTargetsRefusedError were retired by CR-MDB-031 §S1 together with the tests
that pinned them.

Emission target (relative to `target`, which is always a tmp dir;
`scripts_root` is the real hooks-src/scripts/ tree, referenced by absolute
path, never copied):

  * pi -> `.pi/extensions/<name>.ts` (DN §2 roster addendum: pi has FULL
    TS-extension support). Text subscribes `session_start` (ambient) and
    `tool_call` (guard) and returns `{ block: true` on exit 2. pi honors
    fail-closed, so a `fail_direction=closed` guard is EMITTED.

Report shape (pinned): `dict` keyed by harness id; each value a `dict`
with keys `emitted_files` (list[str], paths relative to `target`) and
`notes` (list[str]) -- no `refusals` key (CR-MDB-031 §S1: there is no
refusal path) and no `degraded` flag (CR-MDB-031 C5 F8: nothing ever set
it). Every input schema-instance
`command` must be accounted for (AC4/AC6).

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
        self.assertNotIn("degraded", pi_report)
        self.assertNotIn("refusals", pi_report)

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
        so fail-closed IS honorable (emitted, never refused)."""
        from modelb_axi.hooks import compile_wiring

        report = compile_wiring(
            schema_instances=[WRITE_GUARD_CLOSED],
            harnesses=["pi"],
            target=self.target,
            scripts_root=SCRIPTS_ROOT,
        )

        pi_report = report["pi"]
        self.assertNotIn("refusals", pi_report)
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
        self.assertNotIn("refusals", pi_report)
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
        self.assertNotIn("refusals", pi_report)
        self.assertNotIn("degraded", pi_report)
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


class ReportAccountingTest(HooksCompilerTestCase):
    """AC4/AC6 report shape: every input hook accounted for per harness,
    nothing silent."""

    def test_report_accounts_for_every_hook_for_the_pi_harness(self):
        # CR-MDB-031 §S1: flipped to the Pi-only roster; the report entry
        # carries no `refusals` key (no refusal path) and, C5 F8, no
        # `degraded` flag (nothing ever set it).
        from modelb_axi.hooks import compile_wiring

        harnesses = ["pi"]
        report = compile_wiring(
            schema_instances=[CARGO_GUARD_OPEN, AMBIENT_STATUS],
            harnesses=harnesses,
            target=self.target,
            scripts_root=SCRIPTS_ROOT,
        )

        self.assertEqual(set(report.keys()), set(harnesses))

        for harness in harnesses:
            entry = report[harness]
            self.assertEqual(sorted(entry), ["emitted_files", "notes"],
                             f"{harness} report keys")
            # Pi emits something for our 2 hooks.
            self.assertTrue(
                entry["emitted_files"],
                f"{harness} emitted nothing",
            )


if __name__ == "__main__":
    unittest.main()
