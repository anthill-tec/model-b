"""RED-phase tests for CR-MDB-005 (git-workflow + chezmoi skills: memory-twin
merges + delete procedure).

These tests assert the acceptance criteria of CR-MDB-005 SS2-SS5 against the
LIVE ~/.claude tree on this machine. They are intentionally written before
the GREEN-phase work (git-workflow SKILL.md absorbing the memory-twin
content, the NEW chezmoi skill, deletion of the three redundant memory
files, and repointing consumers) lands, so most of them are expected to FAIL
against the current (pre-CR-MDB-005) state of ~/.claude. The suite overall
must be RED, not necessarily every single test (some content greps may
vacuously pass or fail depending on what already happens to be true of the
live tree today -- that is still correct behaviour, not a test bug).

Stdlib only (unittest + subprocess + pathlib + os). No SUT import: this CR's
deliverable is markdown/skill content, not Python modules.
"""

import os
import subprocess
import unittest
from pathlib import Path

CLAUDE_DIR = Path.home() / ".claude"
REPO_ROOT = Path(__file__).resolve().parent.parent

GIT_WORKFLOW_SKILL_MD = CLAUDE_DIR / "skills" / "git-workflow" / "SKILL.md"

CHEZMOI_SKILL_DIR = CLAUDE_DIR / "skills" / "chezmoi"
CHEZMOI_SKILL_MD = CHEZMOI_SKILL_DIR / "SKILL.md"

GIT_WORKFLOW_MEMORY_MD = CLAUDE_DIR / "memory" / "git-workflow.md"
GIT_MULTI_ACCOUNT_MD = CLAUDE_DIR / "memory" / "git-multi-account.md"
CHEZMOI_INTEGRATION_MD = CLAUDE_DIR / "memory" / "chezmoi-integration.md"

ARCHIVE_WAVE2 = REPO_ROOT / "archive" / "wave2"

# The 5 standard chezmoi-diff scope paths (same convention CR-MDB-002/003/004
# used -- see tests/test_cr_authoring_skill.py).
CHEZMOI_SCOPE_PATHS = (
    CLAUDE_DIR / "AGENTS.md",
    CLAUDE_DIR / "CLAUDE.md",
    CLAUDE_DIR / "agents",
    CLAUDE_DIR / "memory",
    CLAUDE_DIR / "skills",
)

# §S5's AC names this exact grep invocation verbatim.
STALE_REF_PATTERN = r"memory/git-workflow\|git-multi-account\|chezmoi-integration"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _files_under(dir_path: Path):
    """Yield all regular files under dir_path (recursive). Empty if dir absent."""
    if not dir_path.is_dir():
        return
    for root, _dirs, files in os.walk(dir_path):
        for name in files:
            yield Path(root) / name


def _archive_has_content_move(name: str, anchor: str) -> bool:
    """True if some file under archive/wave2/ has `name` as a path component
    (or matching filename) and its content contains `anchor` -- tolerant of
    exact archival layout (flat file vs mirrored subdirectory) while still
    proving it is a REAL content-preserving copy, not a stub."""
    for f in _files_under(ARCHIVE_WAVE2):
        if name not in f.parts and f.name != name:
            continue
        try:
            content = _read(f)
        except (UnicodeDecodeError, OSError):
            continue
        if anchor in content:
            return True
    return False


def _split_frontmatter(content: str):
    """Split a skill markdown file into (frontmatter, body) on the '---'
    delimiters. Returns ("", content) if the file has no well-formed '---'
    frontmatter block."""
    lines = content.splitlines()
    if not lines or lines[0].strip() != "---":
        return "", content
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            frontmatter = "\n".join(lines[1:idx])
            body = "\n".join(lines[idx + 1:])
            return frontmatter, body
    return "", content


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


class ChezmoiSkillS3Test(unittest.TestCase):
    """SS3 -- NEW ~/.claude/skills/chezmoi/SKILL.md: add/diff/apply cycle,
    the DELETE/RENAME procedure, the non-TTY agent-session workaround, the
    chezmoi side of multi-account, source-ahead-drift reconciliation, and
    the `diff <dir>` silent-empty quirk."""

    def test_s3_skill_md_frontmatter_name_and_description(self):
        self.assertTrue(CHEZMOI_SKILL_MD.is_file(), f"{CHEZMOI_SKILL_MD} must exist")
        content = _read(CHEZMOI_SKILL_MD)
        frontmatter, _body = _split_frontmatter(content)
        self.assertNotEqual(
            frontmatter, "",
            "SKILL.md must have a well-formed '---' frontmatter block",
        )

        # POSITIVE -- exact frontmatter key required by the AC.
        name_lines = [
            ln for ln in frontmatter.splitlines() if ln.strip().startswith("name:")
        ]
        self.assertEqual(
            len(name_lines), 1,
            f"frontmatter must have exactly one 'name:' key, found: {name_lines}",
        )
        self.assertEqual(
            name_lines[0].split(":", 1)[1].strip(), "chezmoi",
            f"frontmatter 'name:' must be exactly 'chezmoi', got: {name_lines[0]!r}",
        )

        description_lines = [
            ln for ln in frontmatter.splitlines() if ln.strip().startswith("description:")
        ]
        self.assertEqual(
            len(description_lines), 1,
            f"frontmatter must have exactly one 'description:' key, found: {description_lines}",
        )
        # POSITIVE -- description must actually contain text (non-empty).
        description = description_lines[0].split(":", 1)[1].strip()
        self.assertGreater(
            len(description), 0, "frontmatter 'description:' must be non-empty"
        )

    def test_s3_skill_md_contains_delete_and_non_tty_workaround_anchors(self):
        self.assertTrue(CHEZMOI_SKILL_MD.is_file(), f"{CHEZMOI_SKILL_MD} must exist")
        content = _read(CHEZMOI_SKILL_MD)

        # POSITIVE -- literal, case-sensitive required terms from the AC.
        required_terms = ["chezmoi destroy", "resurrect", "autoCommit"]
        missing = [term for term in required_terms if term not in content]
        self.assertEqual(
            missing, [],
            f"{CHEZMOI_SKILL_MD} missing required delete/gotcha terms: {missing}",
        )

        # POSITIVE -- "no-auto" or the sed workaround verbatim (tolerant,
        # per the AC's own parenthetical alternative).
        no_auto_variants = ("no-auto", "autoCommit = false", "chezmoi-noauto")
        has_no_auto = any(v in content for v in no_auto_variants)
        self.assertTrue(
            has_no_auto,
            f"{CHEZMOI_SKILL_MD} must contain 'no-auto' or the sed workaround "
            f"verbatim, tried {no_auto_variants}",
        )

        # POSITIVE -- "never push" case-insensitive per the AC.
        self.assertIn(
            "never push", content.lower(),
            f"{CHEZMOI_SKILL_MD} must contain 'never push' (case-insensitive)",
        )

        # POSITIVE -- the `diff <dir>` silent-empty quirk mention.
        self.assertIn(
            "diff <dir>", content,
            f"{CHEZMOI_SKILL_MD} must mention the `diff <dir>` silent-empty quirk",
        )

    def test_s3_skill_dir_and_md_exist_together(self):
        # NEGATIVE/bound -- the skill directory existing without a SKILL.md
        # (or vice versa) is not a valid skill; both must hold.
        self.assertEqual(
            CHEZMOI_SKILL_DIR.is_dir(), CHEZMOI_SKILL_MD.is_file(),
            f"{CHEZMOI_SKILL_DIR} directory presence and {CHEZMOI_SKILL_MD} file "
            "presence must agree -- a half-created skill is not valid",
        )
        self.assertTrue(
            CHEZMOI_SKILL_MD.is_file(), f"{CHEZMOI_SKILL_MD} must exist"
        )


class DeletionsS4Test(unittest.TestCase):
    """SS4 -- memory/git-workflow.md, memory/git-multi-account.md,
    memory/chezmoi-integration.md: archive to <repo>/archive/wave2/, delete
    via chezmoi discipline."""

    def test_s4_legacy_memory_files_removed_with_archived_content(self):
        still_present = []
        for path in (GIT_WORKFLOW_MEMORY_MD, GIT_MULTI_ACCOUNT_MD, CHEZMOI_INTEGRATION_MD):
            if path.exists():
                still_present.append(str(path))
        # NEGATIVE -- none of the three legacy memory files may still exist live.
        self.assertEqual(
            still_present, [],
            f"expected zero legacy memory files still present, found: {still_present}",
        )

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

    def test_s4_chezmoi_diff_clean_on_cr_touched_paths(self):
        """chezmoi's source state must exactly match the live state of the 5
        standard CR-touched paths, per the AC's scoped `chezmoi diff`."""
        import shutil

        chezmoi = shutil.which("chezmoi")
        if chezmoi is None:
            self.skipTest("chezmoi binary not found on PATH -- cannot verify dotfile-manager drift")
        result = subprocess.run(
            [chezmoi, "diff", *[str(p) for p in CHEZMOI_SCOPE_PATHS]],
            capture_output=True,
            text=True,
            timeout=60,
        )
        # POSITIVE -- chezmoi's source state must exactly match the live
        # state of the CR-touched paths (empty diff).
        self.assertEqual(
            result.stdout.strip(), "",
            f"chezmoi diff on CR-touched paths must be empty (no drift), got ({len(result.stdout)} chars):\n"
            f"{result.stdout[:2000]}",
        )
        # EXACT bound -- a clean exit is required too, so an "unmanaged
        # path" abort (empty stdout but non-zero exit) does not vacuously pass.
        self.assertEqual(
            result.returncode, 0,
            "chezmoi diff on CR-touched paths must exit 0 -- a non-zero exit "
            f"means chezmoi never actually compared the paths. stderr:\n{result.stderr[:2000]}",
        )


class ConsumerRepointS5Test(unittest.TestCase):
    """SS5 -- repoint consumers: skills/git-flow-release/SKILL.md citations
    of memory/git-workflow.md -> the skill; memory/QUICK_REFERENCE.md
    repointed; ~/.claude/AGENTS.md chezmoi trigger row -> the chezmoi skill,
    dropping "until Wave 2"."""

    def test_s5_grep_gate_zero_stale_references_across_consumers(self):
        # EXACT -- the AC names this exact grep invocation verbatim.
        result = subprocess.run(
            [
                "grep", "-rl", STALE_REF_PATTERN,
                str(CLAUDE_DIR / "skills"),
                str(CLAUDE_DIR / "memory"),
                str(CLAUDE_DIR / "AGENTS.md"),
                str(CLAUDE_DIR / "agents"),
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

    def test_s5_agents_md_no_longer_ties_chezmoi_trigger_to_wave2(self):
        """AGENTS.md's chezmoi trigger row must repoint to the chezmoi skill
        and drop the "until Wave 2" qualifier now that Wave 2 delivers it."""
        agents_md = CLAUDE_DIR / "AGENTS.md"
        self.assertTrue(agents_md.is_file(), f"{agents_md} must exist")
        content = _read(agents_md)
        # NEGATIVE -- the stale "until Wave 2" qualifier must be gone.
        self.assertNotIn(
            "until Wave 2", content,
            f"{agents_md} chezmoi trigger row must drop the 'until Wave 2' qualifier",
        )
        # POSITIVE -- it must now cite the chezmoi skill by name.
        self.assertIn(
            "chezmoi", content.lower(),
            f"{agents_md} must still mention 'chezmoi' after repointing",
        )


if __name__ == "__main__":
    unittest.main()
