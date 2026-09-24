"""RED-phase tests for CR-MDB-005 (git-workflow + chezmoi skills: memory-twin
merges + delete procedure). CR-MDB-031 SS4 retired the chezmoi bundle and
with it this module's SS3 chezmoi-skill class.

Originally written against the LIVE ~/.claude tree. CR-MDB-032 SS2
retargeted them to the repo (the 2026-07-22 repo-local authoring rule): the
skills under skills-src/, the archive/wave2/ copies, the consumer grep gate
over skills-src/ + generator/agents/ + the repo AGENTS.md, and the repo
AGENTS.md itself. The live-memory absence half of SS4 was deleted.

Stdlib only (unittest + subprocess + pathlib + os). No SUT import: this CR's
deliverable is markdown/skill content, not Python modules.
"""

import subprocess
import unittest
from pathlib import Path

from tests._helpers import archive_has_content_move as _archive_has_content_move
from tests._helpers import read_text_lenient as _read

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS_SRC_DIR = REPO_ROOT / "skills-src"
REPO_AGENTS_MD = REPO_ROOT / "AGENTS.md"

GIT_WORKFLOW_SKILL_MD = SKILLS_SRC_DIR / "git-workflow" / "SKILL.md"

ARCHIVE_WAVE2 = REPO_ROOT / "archive" / "wave2"

# CR-MDB-021 §S2 retired the chezmoi-diff scope-path constant along
# with its sole consumer, the chezmoi-diff invocation test that used
# to close out DeletionsS4Test below. That test duplicated coverage
# already carried directly against the repo
# by test_s4_legacy_memory_files_removed_with_archived_content,
# with no dependency on the user's chezmoi source repo or on the
# chezmoi binary being present on PATH -- see
# docs/changes/CR-MDB-021-chezmoi-retirement.md §S2 for the full
# disposition.

# §S5's AC names this exact grep invocation verbatim.
STALE_REF_PATTERN = r"memory/git-workflow\|git-multi-account\|chezmoi-integration"


class GitWorkflowSkillS2Test(unittest.TestCase):
    """SS2 -- git-workflow skill absorbs memory/git-workflow.md (branch
    discipline, commit conventions incl. no-AI-attribution, versioning,
    10-step release) + the git parts of memory/git-multi-account.md
    (account switching around push)."""

    def test_s2_skill_md_contains_attribution_release_and_account_switch_terms(self):
        self.assertTrue(
            GIT_WORKFLOW_SKILL_MD.is_file(), f"{GIT_WORKFLOW_SKILL_MD} must exist"
        )
        content = _read(GIT_WORKFLOW_SKILL_MD)

        # POSITIVE -- the AC's two literal required terms.
        required_terms = ["attribution", "git flow release"]
        missing = [term for term in required_terms if term not in content]
        self.assertEqual(
            missing, [],
            f"{GIT_WORKFLOW_SKILL_MD} missing required AC terms: {missing}",
        )

        # POSITIVE -- a multi-account/account-switch line ("gh auth switch"
        # or equivalent), case-insensitive per the AC's tolerant phrasing.
        account_switch_variants = ("gh auth switch", "account switch", "multi-account")
        lowered = content.lower()
        has_account_switch = any(v in lowered for v in account_switch_variants)
        self.assertTrue(
            has_account_switch,
            f"{GIT_WORKFLOW_SKILL_MD} must contain a multi-account/account-switch "
            f"line, tried {account_switch_variants}",
        )

    def test_s2_skill_md_not_empty(self):
        self.assertTrue(
            GIT_WORKFLOW_SKILL_MD.is_file(), f"{GIT_WORKFLOW_SKILL_MD} must exist"
        )
        content = _read(GIT_WORKFLOW_SKILL_MD)
        # POSITIVE sanity, EXACT bound -- non-empty, and materially larger
        # than the current pre-absorption skill (91 lines) once it has
        # absorbed the two memory-twin files.
        self.assertGreater(len(content.strip()), 0, "SKILL.md must not be empty")
        line_count = len(content.splitlines())
        self.assertGreaterEqual(
            line_count, 150,
            f"{GIT_WORKFLOW_SKILL_MD} has only {line_count} lines -- too short to "
            "have absorbed memory/git-workflow.md's release process and the "
            "git-multi-account.md account-switch content",
        )


class DeletionsS4Test(unittest.TestCase):
    """SS4 -- memory/git-workflow.md, memory/git-multi-account.md,
    memory/chezmoi-integration.md: archived to <repo>/archive/wave2/
    (CR-MDB-032 SS2 dropped the live ~/.claude absence half)."""

    def test_s4_legacy_memory_files_removed_with_archived_content(self):
        # POSITIVE -- an archived, content-preserving copy of each must
        # exist under <repo>/archive/wave2/ (tolerant of exact layout: name
        # as a path component or matching filename, plus a content anchor
        # proving it's a real move, not a stub).
        not_archived = []
        if not _archive_has_content_move(
            "git-workflow.md", "CRITICAL RULE - NO Claude Attribution",
        ):
            not_archived.append("git-workflow.md")
        if not _archive_has_content_move(
            "git-multi-account.md", "gh auth switch --user antojk",
        ):
            not_archived.append("git-multi-account.md")
        if not _archive_has_content_move(
            "chezmoi-integration.md", "Chezmoi Integration for Claude Memory Management",
        ):
            not_archived.append("chezmoi-integration.md")
        self.assertEqual(
            not_archived, [],
            f"expected an archived copy retaining its anchor under {ARCHIVE_WAVE2} "
            f"for every deletion target, missing/anchor-less for: {not_archived}",
        )

    # CR-MDB-021 retired test_s4_chezmoi_diff_clean_on_cr_touched_paths.
    # The method shelled out to `chezmoi diff` scoped to the same five
    # CR-MDB-005-touched paths as the scope-path constant retired above
    # in this module, and asserted an empty, exit-0 diff.
    #
    # Per the CR-MDB-021 Context table (measured 2026-08-27), that
    # coverage was never load-bearing: three of the five scope arguments
    # are directories that `chezmoi diff`'s default --recursive=false
    # compares shallowly, never reaching the files this CR actually
    # touches, and the skills/ argument cannot see Model-B-owned skill
    # drift at all (CR-MDB-016 de-chezmoi'd the skills tree).
    #
    # The real acceptance criterion -- that memory/git-workflow.md,
    # memory/git-multi-account.md and memory/chezmoi-integration.md
    # have a content-preserving archived copy under <repo>/archive/wave2/
    # -- is carried by test_s4_legacy_memory_files_removed_with_archived_content
    # above, asserted directly against the repo (CR-MDB-032 SS2) with no
    # dependency on the user's chezmoi source repo or on the chezmoi
    # binary being present on PATH.
    #
    # See docs/changes/CR-MDB-021-chezmoi-retirement.md (Scope section) for the
    # full disposition and the sanctioned-amendment rationale for
    # removing coverage from this CLOSED CR's (CR-MDB-005) gate set --
    # the acceptance criterion moved, no coverage was lost.





class ConsumerRepointS5Test(unittest.TestCase):
    """SS5 -- repoint consumers: skills/git-flow-release/SKILL.md citations
    of memory/git-workflow.md -> the skill; memory/QUICK_REFERENCE.md
    repointed. (The AGENTS.md chezmoi-trigger half retired with the chezmoi
    bundle, CR-MDB-031 SS4.)"""

    def test_s5_grep_gate_zero_stale_references_across_consumers(self):
        # EXACT -- the AC names this exact grep invocation verbatim.
        result = subprocess.run(
            [
                "grep", "-rl", STALE_REF_PATTERN,
                str(SKILLS_SRC_DIR),
                str(REPO_AGENTS_MD),
                str(REPO_ROOT / "generator" / "agents"),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        matched_files = [ln for ln in result.stdout.splitlines() if ln.strip()]
        # EXACT bound -- the AC requires this exact grep invocation to
        # return zero files.
        self.assertEqual(
            matched_files, [],
            f"grep gate must return 0 files referencing memory/git-workflow, "
            f"git-multi-account, or chezmoi-integration, found: {matched_files}",
        )

if __name__ == "__main__":
    unittest.main()
