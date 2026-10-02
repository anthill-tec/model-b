"""RED-phase tests for CR-MDB-009 (contracts/: the AXI evolution interface).

These tests assert the acceptance criteria of CR-MDB-009 SS2-SS5 against the
LIVE repo tree: each of the four `contracts/*.md` files must exist and carry
the exact anchor strings its AC bullet names, proving the doc was actually
authored (not stubbed) with the required content. CR-MDB-031 SS4 moved
`contracts/mail-axi.md` to `archive/contracts/` and retired its SS4 class;
tests/test_worktree_layout_and_bundles.py pins the archived copy.

Repo-only CR (per SS1: "no ~/.claude writes, no chezmoi ops") -- these tests
assert repo-relative paths only, no ~/.claude / chezmoi checks (unlike
tests/test_memory_model.py, whose CR touched the global memory tree).

At RED time `contracts/` holds only `.gitkeep`, so all four tests below are
expected to FAIL on the `is_file()` existence assertion.

Stdlib only (unittest + pathlib). No SUT import: this CR's deliverable is
markdown contract content, not Python modules.
"""

import re
import unittest
from pathlib import Path

from tests._helpers import read_text_lenient as _read
from tests.test_watcher_launch_supervision import _blocks, _names_exit

REPO_ROOT = Path(__file__).resolve().parent.parent
CONTRACTS_DIR = REPO_ROOT / "contracts"

CRUCIBLE_ENVELOPE_MD = CONTRACTS_DIR / "crucible-envelope.md"
SANDESH_CLI_MD = CONTRACTS_DIR / "sandesh-cli.md"
LEAN_CTX_MD = CONTRACTS_DIR / "lean-ctx.md"

# The exact phase-agent id form cited verbatim in the SS2 AC bullet.
PHASE_AGENT_ID_FORM = "CR-<PROJ>-NNN-<cycle>-<PHASE>"

# The seven sandesh-cli message verbs the SS3 AC bullet names verbatim.
SANDESH_MESSAGE_VERBS = (
    "send",
    "reply",
    "fetch",
    "inbox",
    "addressbook",
    "register",
    "unregister",
)


class ContractsS2Test(unittest.TestCase):
    """SS2 -- contracts/crucible-envelope.md: the CRUCIBLE-owned contract
    mirroring the incoming CR-CRU-030 client contract."""

    def test_s2_crucible_envelope_exists_with_required_anchors(self):
        self.assertTrue(
            CRUCIBLE_ENVELOPE_MD.is_file(),
            f"{CRUCIBLE_ENVELOPE_MD} must exist",
        )
        content = _read(CRUCIBLE_ENVELOPE_MD)

        # POSITIVE -- the AC's conjunction of literal required terms.
        required_terms = [
            "{axi:",
            "warnings[]",
            "WORKFLOW_",
            "plan-file",
            "CR-CRU-030",
            PHASE_AGENT_ID_FORM,
            "TRACKS",
        ]
        missing = [term for term in required_terms if term not in content]
        self.assertEqual(
            missing, [],
            f"{CRUCIBLE_ENVELOPE_MD} missing required anchor terms: {missing}",
        )

        # NEGATIVE -- the final contract has NO refusal rule; the
        # unknown-cycleId REFUSED/(400) anchor is gone.
        self.assertNotIn(
            "REFUSED", content,
            f"{CRUCIBLE_ENVELOPE_MD} must not contain 'REFUSED' -- the refusal rule is gone",
        )
        self.assertNotIn(
            "(400)", content,
            f"{CRUCIBLE_ENVELOPE_MD} must not reference the '(400)' refusal status",
        )

        # POSITIVE -- server-resolved cycle-attach + no-active-cycle
        # withhold semantics, and DELIVERED status.
        self.assertIn(
            "resolve_attach_cycle", content,
            f"{CRUCIBLE_ENVELOPE_MD} must contain 'resolve_attach_cycle'",
        )
        self.assertIn(
            "no-active-cycle", content,
            f"{CRUCIBLE_ENVELOPE_MD} must contain 'no-active-cycle'",
        )
        self.assertIn(
            "DELIVERED", content,
            f"{CRUCIBLE_ENVELOPE_MD} must contain 'DELIVERED' (status)",
        )

        # NEGATIVE/bound -- not a stub: the file must carry real content,
        # not just an empty or near-empty placeholder.
        self.assertGreater(
            len(content.strip()), 0,
            f"{CRUCIBLE_ENVELOPE_MD} must not be empty",
        )

    def test_ac1_zero_workflow_cycle_id_occurrences_in_crucible_envelope(self):
        self.assertTrue(
            CRUCIBLE_ENVELOPE_MD.is_file(),
            f"{CRUCIBLE_ENVELOPE_MD} must exist",
        )
        content = _read(CRUCIBLE_ENVELOPE_MD)
        count = content.count("WORKFLOW_CYCLE_ID")
        # EXACT bound -- zero occurrences of the retired env carrier.
        self.assertEqual(
            count, 0,
            f"expected zero 'WORKFLOW_CYCLE_ID' occurrences in {CRUCIBLE_ENVELOPE_MD}, "
            f"found {count}",
        )


class ContractsS3Test(unittest.TestCase):
    """SS3 -- contracts/sandesh-cli.md: the SANDESH-owned contract for the
    CLI surface replacing the MCP-only message verbs, plus the dogfooding
    defect/gap register (zombie project, display-name update, admin-name
    leak)."""

    def test_s3_sandesh_cli_exists_with_required_anchors(self):
        self.assertTrue(
            SANDESH_CLI_MD.is_file(),
            f"{SANDESH_CLI_MD} must exist",
        )
        content = _read(SANDESH_CLI_MD)

        # POSITIVE -- all seven message verbs the AC names verbatim.
        missing_verbs = [v for v in SANDESH_MESSAGE_VERBS if v not in content]
        self.assertEqual(
            missing_verbs, [],
            f"{SANDESH_CLI_MD} missing required message verbs: {missing_verbs}",
        )

        # POSITIVE -- the defect/gap register anchors (a) zombie, (b)
        # display-name update, (c) admin-name leak -- and SANDESH ownership.
        required_terms = ["zombie", "display", "admin name", "SANDESH"]
        missing_terms = [term for term in required_terms if term not in content]
        self.assertEqual(
            missing_terms, [],
            f"{SANDESH_CLI_MD} missing required anchor terms: {missing_terms}",
        )

        # NEGATIVE/bound -- not a stub.
        self.assertGreater(
            len(content.strip()), 0,
            f"{SANDESH_CLI_MD} must not be empty",
        )


class ContractsS5Test(unittest.TestCase):
    """SS5 -- contracts/lean-ctx.md: the LEAN-CTX-owned CLI-preference
    contract documenting preference order plus operational findings
    (shell-allowlist friction, file-write redirect block interplay)."""

    def test_s5_lean_ctx_exists_with_required_anchors(self):
        self.assertTrue(
            LEAN_CTX_MD.is_file(),
            f"{LEAN_CTX_MD} must exist",
        )
        content = _read(LEAN_CTX_MD)

        # POSITIVE -- "allowlist" is a required literal term.
        self.assertIn(
            "allowlist", content,
            f"{LEAN_CTX_MD} must contain 'allowlist'",
        )

        # POSITIVE -- "dual" OR "MCP + CLI" per the AC's own tolerant
        # alternative describing the dual MCP/CLI preference.
        dual_variants = ("dual", "MCP + CLI")
        has_dual_marker = any(v in content for v in dual_variants)
        self.assertTrue(
            has_dual_marker,
            f"{LEAN_CTX_MD} must contain 'dual' or 'MCP + CLI', tried {dual_variants}",
        )

        # NEGATIVE/bound -- not a stub.
        self.assertGreater(
            len(content.strip()), 0,
            f"{LEAN_CTX_MD} must not be empty",
        )


class SandeshCliRelease040Test(unittest.TestCase):
    """CR-MDB-047 \u00a7S5 -- contracts/sandesh-cli.md records Sandesh 0.4.0 as Model B
    relies on it: the version floor; ``status`` and ``--format toon``; the notify exit
    table as sandesh-pi's supervision treats it (after mail it injects a turn and
    relaunches; it retries once when the address is already live; it stops with a
    notice on exit 1, 3 or 4); and that only the extension starts the supervised
    watcher. Each rule is checked inside one bullet, paragraph or table row."""

    def setUp(self):
        self.content = _read(SANDESH_CLI_MD)
        self.blocks = [b for _, b in _blocks(self.content)]

    def _blocks_with(self, *patterns):
        return [b for b in self.blocks if all(re.search(p, b, re.IGNORECASE) for p in patterns)]

    def _exit_rows(self, code):
        return [b for b in self.blocks if b.startswith("|") and _names_exit(b, code)]

    def test_records_the_sandesh_0_4_0_version_floor(self):
        self.assertTrue(
            self._blocks_with(r"\b0\.4\.0\b", r"floor|or later|at least|minimum|older", r"sandesh"),
            "sandesh-cli.md must record the floor: the `sandesh` CLI 0.4.0 or later",
        )

    def test_records_the_status_home_view_and_toon_output(self):
        self.assertTrue(self._blocks_with(r"sandesh status\b"), "sandesh-cli.md must record `sandesh status`")
        self.assertTrue(self._blocks_with(r"--format toon"), "sandesh-cli.md must record `--format toon`")

    def test_exit_table_records_mail_as_a_turn_and_a_relaunch_by_the_extension(self):
        rows = [r for r in self._exit_rows("0") if re.search(r"mail", r, re.IGNORECASE)
                and re.search(r"\bturn\b|inject", r, re.IGNORECASE)]
        self.assertTrue(rows, "the exit table's 0 row: mail arrived -> sandesh-pi injects a turn naming the ids")

    def test_exit_table_stops_with_a_notice_on_exits_1_3_and_4(self):
        reasons = {"1": r"error|usage|config", "3": r"tombston", "4": r"evict"}
        for code, reason in reasons.items():
            with self.subTest(exit=code):
                rows = [r for r in self._exit_rows(code)
                        if re.search(reason, r, re.IGNORECASE)
                        and re.search(r"\bstops?\b", r, re.IGNORECASE)
                        and re.search(r"\bnotice\b", r, re.IGNORECASE)]
                self.assertEqual(len(rows), 1, f"exactly one exit-{code} row: {reason} -> stops with a notice")

    def test_exit_table_retries_once_when_already_live(self):
        rows = [r for r in self._exit_rows("5") if re.search(r"already[- ]live|dedup", r, re.IGNORECASE)
                and re.search(r"\bretr(?:y|ies)\b[^|]{0,20}\bonce\b", r, re.IGNORECASE)]
        self.assertTrue(rows, "the exit table's 5 row: already live -> sandesh-pi retries once")

    def test_exit_table_relaunches_silently_on_exit_2(self):
        # CR-MDB-047 §S5 amended at 5dd8a36 (VERIFY F10): every exit, 2 included.
        rows = [r for r in self._exit_rows("2") if re.search(r"timeout|timed out", r, re.IGNORECASE)
                and re.search(r"relaunch", r, re.IGNORECASE)
                and re.search(r"silent", r, re.IGNORECASE)]
        self.assertEqual(len(rows), 1, "exactly one exit-2 row: timeout -> relaunched silently")

    def test_exit_table_stops_with_a_notice_on_a_signal(self):
        # CR-MDB-047 §S5 amended at 5dd8a36 (VERIFY F10): a signal included.
        rows = [r for r in self.blocks if r.startswith("|") and re.search(r"\bsignal\b", r, re.IGNORECASE)
                and re.search(r"128\s*\+\s*n", r)
                and re.search(r"\bstops?\b", r, re.IGNORECASE)
                and re.search(r"\bnotice\b", r, re.IGNORECASE)]
        self.assertEqual(len(rows), 1, "exactly one signal row: 128+n -> stops with a notice")

    def test_exit_table_is_attributed_to_sandesh_pi_supervision(self):
        self.assertTrue(
            self._blocks_with(r"sandesh-pi", r"supervis", r"exit"),
            "the exit table is recorded as sandesh-pi's supervision treats it",
        )

    def test_only_the_extension_starts_the_supervised_watcher(self):
        self.assertTrue(
            self._blocks_with(r"\bonly\b", r"extension|sandesh-pi", r"\bstart", r"supervised watcher"),
            "sandesh-cli.md must record that only the extension starts the supervised watcher",
        )

    def test_rule_detectors_read_one_block_or_row(self):
        synthetic = (
            "Model B relies on the `sandesh` CLI **0.4.0 or later**.\n\n"
            "| Exit | Reason | sandesh-pi |\n|---|---|---|\n"
            "| `1` | usage or configuration error | stops with a notice |\n"
            "| `3` | tombstoned | relaunches |\n"
        )
        blocks = [b for _, b in _blocks(synthetic)]
        self.assertEqual(blocks[0], "Model B relies on the sandesh CLI 0.4.0 or later.")
        rows_1 = [b for b in blocks if b.startswith("|") and _names_exit(b, "1")]
        rows_3 = [b for b in blocks if b.startswith("|") and _names_exit(b, "3")]
        self.assertEqual(rows_1, ["| 1 | usage or configuration error | stops with a notice |"])
        self.assertFalse(re.search(r"\bnotice\b", rows_3[0]), "a row is judged alone, never with its neighbour")


if __name__ == "__main__":
    unittest.main()
