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

import unittest
from pathlib import Path

from tests._helpers import read_text_lenient as _read

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


if __name__ == "__main__":
    unittest.main()
