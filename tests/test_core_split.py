"""RED-phase tests for CR-MDB-001 (Model B core split).

Originally written against the LIVE ~/.claude tree. CR-MDB-032 §S2 retargeted
them to the repo (the 2026-07-22 repo-local authoring rule): the model-b skill
under skills-src/, the rendered agents under generator/agents/, the memory
templates under skills-src/memory-templates/, the archive/ copies, and the
repo AGENTS.md / CLAUDE.md symlink. Assertions that could only ever describe
the user's real home (the universal ~/.claude/AGENTS.md line budget, the
shim files' absence from ~/.claude/memory) were deleted.

Stdlib only (unittest + pathlib + re).
"""

import os
import re
import unittest
from pathlib import Path

from tests._helpers import read_text_lenient as _read

REPO_ROOT = Path(__file__).resolve().parent.parent
MODEL_B_SKILL_DIR = REPO_ROOT / "skills-src" / "model-b"


def _files_under(dir_path: Path):
    """Yield all regular files under dir_path (recursive). Empty if dir absent."""
    if not dir_path.is_dir():
        return
    for root, _dirs, files in os.walk(dir_path):
        for name in files:
            yield Path(root) / name


def _files_containing(dir_path: Path, needle: str):
    """Return sorted relative paths of files under dir_path whose content contains needle."""
    hits = []
    for f in _files_under(dir_path):
        try:
            content = _read(f)
        except (UnicodeDecodeError, OSError):
            continue
        if needle in content:
            hits.append(str(f.relative_to(dir_path)))
    return sorted(hits)


class CoreSplitS2AgentsMdTest(unittest.TestCase):
    """§S2 — the repo AGENTS.md is the project contract, and CLAUDE.md is a
    symlink to it (harness compatibility; never de-symlinked)."""

    AGENTS_MD = REPO_ROOT / "AGENTS.md"
    CLAUDE_MD = REPO_ROOT / "CLAUDE.md"

    def test_s2_claude_md_symlinks_to_agents_md(self):
        self.assertTrue(
            self.CLAUDE_MD.is_symlink(),
            f"{self.CLAUDE_MD} must be a symlink to AGENTS.md",
        )
        target = os.readlink(self.CLAUDE_MD)
        # POSITIVE — exact (relative) target match, resolving to AGENTS.md.
        self.assertEqual(target, "AGENTS.md")
        self.assertEqual(self.CLAUDE_MD.resolve(), self.AGENTS_MD.resolve())
        # NEGATIVE bound — must not point at the retired shim.
        self.assertNotIn("agent-baseline", target)

    def test_s2_agents_md_trigger_table_contains_model_b_and_crucible(self):
        content = _read(self.AGENTS_MD)
        lines = content.splitlines()
        model_b_lines = [ln for ln in lines if "model-b" in ln]
        crucible_lines = [ln for ln in lines if "crucible" in ln]
        # POSITIVE — at least one line for each trigger keyword.
        self.assertGreaterEqual(
            len(model_b_lines), 1,
            "AGENTS.md must contain at least one line mentioning 'model-b'",
        )
        self.assertGreaterEqual(
            len(crucible_lines), 1,
            "AGENTS.md must contain at least one line mentioning 'crucible'",
        )

    def test_s2_agents_md_contains_no_attribution_clause(self):
        # The universal sub-agent procedure CR-MDB-001 split out carries the
        # clause; in the repo that is the model-b skill's reference.
        content = _read(MODEL_B_SKILL_DIR / "references" / "sub-agent-procedure.md")
        pattern = re.compile(r"(no (ai|claude) attribution|never add claude attribution)", re.IGNORECASE)
        match = pattern.search(content)
        self.assertIsNotNone(
            match,
            "AGENTS.md must contain a 'no AI/Claude attribution' clause",
        )

    def test_s2_agents_md_zero_worktree_boundary_mentions(self):
        content = _read(self.AGENTS_MD)
        occurrences = content.count("worktree boundary")
        # EXACT bound — the trimmed doc must not re-embed the worktree-boundary section.
        self.assertEqual(
            occurrences, 0,
            f"AGENTS.md must contain zero 'worktree boundary' mentions, found {occurrences}",
        )


class CoreSplitS3ModelBSkillTest(unittest.TestCase):
    """§S3 — sub-agent procedure lives at
    skills-src/model-b/references/sub-agent-procedure.md, and the
    model-b skill has a valid SKILL.md."""

    PROCEDURE_MD = MODEL_B_SKILL_DIR / "references" / "sub-agent-procedure.md"
    SKILL_MD = MODEL_B_SKILL_DIR / "SKILL.md"

    def test_s3_sub_agent_procedure_exists_and_contains_key_phrases(self):
        self.assertTrue(
            self.PROCEDURE_MD.is_file(),
            f"{self.PROCEDURE_MD} must exist",
        )
        content = _read(self.PROCEDURE_MD)
        for phrase in (
            "git rev-parse --show-toplevel",
            "Register immediately on startup",
            "A compile failure IS a RED",
        ):
            self.assertIn(
                phrase, content,
                f"sub-agent-procedure.md must contain the phrase: {phrase!r}",
            )

    def test_s3_sub_agent_procedure_zero_plan_b_and_agent_baseline_mentions(self):
        self.assertTrue(self.PROCEDURE_MD.is_file(), f"{self.PROCEDURE_MD} must exist")
        content = _read(self.PROCEDURE_MD)
        plan_b_count = content.count("Plan B")
        agent_baseline_count = content.count("agent-baseline")
        # EXACT bounds on both forbidden terms.
        self.assertEqual(plan_b_count, 0, f"expected zero 'Plan B' mentions, found {plan_b_count}")
        self.assertEqual(
            agent_baseline_count, 0,
            f"expected zero 'agent-baseline' mentions, found {agent_baseline_count}",
        )

    def test_s3_skill_md_exists_with_frontmatter_name_and_description(self):
        self.assertTrue(self.SKILL_MD.is_file(), f"{self.SKILL_MD} must exist")
        content = _read(self.SKILL_MD)
        lines = content.splitlines()

        name_lines = [ln for ln in lines if ln.strip() == "name: model-b"]
        self.assertEqual(
            len(name_lines), 1,
            "SKILL.md frontmatter must contain exactly one 'name: model-b' line, "
            f"found {len(name_lines)}",
        )

        description_lines = [
            ln for ln in lines
            if ln.strip().startswith("description:") and ln.strip() != "description:"
        ]
        self.assertGreaterEqual(
            len(description_lines), 1,
            "SKILL.md frontmatter must contain a non-empty 'description:' line",
        )
        # NEGATIVE — the description value itself must not be blank.
        description_value = description_lines[0].split("description:", 1)[1].strip()
        self.assertNotEqual(description_value, "", "description value must not be empty")


class CoreSplitS4NoStaleShimReferencesTest(unittest.TestCase):
    """§S4 — nothing under the rendered agents, the memory templates or the
    skill sources references the retired agent-baseline /
    orchestration-universal shim files by name."""

    AGENTS_DIR = REPO_ROOT / "generator" / "agents"
    MEMORY_DIR = REPO_ROOT / "skills-src" / "memory-templates"
    SKILLS_DIR = REPO_ROOT / "skills-src"

    def test_s4_agents_dir_no_agent_baseline_mentions(self):
        self.assertTrue(self.AGENTS_DIR.is_dir(), f"{self.AGENTS_DIR} must exist")
        hits = _files_containing(self.AGENTS_DIR, "agent-baseline")
        # EXACT bound — zero files under agents/ may reference agent-baseline.
        self.assertEqual(
            hits, [],
            f"expected zero files under {self.AGENTS_DIR} referencing 'agent-baseline', found: {hits}",
        )

    def test_s4_no_orchestration_universal_mentions_in_memory_agents_skills(self):
        all_hits = {}
        for label, d in (
            ("memory", self.MEMORY_DIR),
            ("agents", self.AGENTS_DIR),
            ("skills", self.SKILLS_DIR),
        ):
            hits = _files_containing(d, "orchestration-universal")
            if hits:
                all_hits[label] = hits
        # EXACT bound — zero files across all three trees may reference orchestration-universal.
        self.assertEqual(
            all_hits, {},
            f"expected zero 'orchestration-universal' references under memory/agents/skills, found: {all_hits}",
        )


class CoreSplitS5ShimRemovalAndArchiveTest(unittest.TestCase):
    """§S5 — content-preserving archived copies of the retired shim files
    exist in the repo."""

    ARCHIVE_AGENT_BASELINE = REPO_ROOT / "archive" / "wave1" / "agent-baseline.md"
    ARCHIVE_ORCH_UNIVERSAL = REPO_ROOT / "archive" / "wave1" / "orchestration-universal.md"

    def test_s5_archive_wave1_copies_exist(self):
        self.assertTrue(
            self.ARCHIVE_AGENT_BASELINE.is_file(),
            f"{self.ARCHIVE_AGENT_BASELINE} must exist",
        )
        self.assertTrue(
            self.ARCHIVE_ORCH_UNIVERSAL.is_file(),
            f"{self.ARCHIVE_ORCH_UNIVERSAL} must exist",
        )
        # Behavioural (not just existence): the archived copy must be a real
        # copy of the original shim content, not an empty/stub file.
        agent_baseline_content = _read(self.ARCHIVE_AGENT_BASELINE)
        orch_universal_content = _read(self.ARCHIVE_ORCH_UNIVERSAL)
        self.assertIn(
            "Legacy alias for the universal sub-agent procedure",
            agent_baseline_content,
            "archived agent-baseline.md must retain its original distinctive content",
        )
        self.assertIn(
            "role-split + lean",
            orch_universal_content,
            "archived orchestration-universal.md must retain its original distinctive content",
        )
        # NEGATIVE bound — archived copies must not be empty stubs.
        self.assertGreater(len(agent_baseline_content.strip()), 0)
        self.assertGreater(len(orch_universal_content.strip()), 0)


if __name__ == "__main__":
    unittest.main()
