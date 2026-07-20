"""RED-phase tests for CR-MODELB-001 (Model B core split).

These tests assert the acceptance criteria of CR-MODELB-001 §S2-§S5 against the
LIVE ~/.claude tree on this machine. They are intentionally written before
the GREEN-phase reorganization runs, so most of them are expected to FAIL
against the current (pre-CR-MODELB-001) state of ~/.claude.

Stdlib only (unittest + subprocess + pathlib + re + shutil).
"""

import os
import re
import shutil
import subprocess
import unittest
from pathlib import Path

CLAUDE_DIR = Path.home() / ".claude"
REPO_ROOT = Path(__file__).resolve().parent.parent


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


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
    """§S2 — ~/.claude/AGENTS.md is the new, trimmed universal sub-agent doc,
    and ~/.claude/CLAUDE.md is a symlink to it."""

    AGENTS_MD = CLAUDE_DIR / "AGENTS.md"
    CLAUDE_MD = CLAUDE_DIR / "CLAUDE.md"

    def test_s2_agents_md_line_count_at_most_100(self):
        self.assertTrue(self.AGENTS_MD.is_file(), f"{self.AGENTS_MD} must exist")
        lines = _read(self.AGENTS_MD).splitlines()
        line_count = len(lines)
        # POSITIVE (exact bound) + implicit lower bound sanity (non-empty doc).
        self.assertLessEqual(
            line_count, 100,
            f"AGENTS.md must be trimmed to <=100 lines, found {line_count}",
        )
        self.assertGreater(line_count, 0, "AGENTS.md must not be empty")

    def test_s2_claude_md_symlinks_to_agents_md(self):
        self.assertTrue(
            self.CLAUDE_MD.is_symlink(),
            f"{self.CLAUDE_MD} must be a symlink to AGENTS.md",
        )
        target = os.readlink(self.CLAUDE_MD)
        # POSITIVE — exact target match.
        self.assertEqual(target, str(self.AGENTS_MD))
        # NEGATIVE bound — must not point at some other file.
        self.assertNotEqual(target, str(CLAUDE_DIR / "memory" / "agent-baseline.md"))

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
        content = _read(self.AGENTS_MD)
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
    ~/.claude/skills/model-b/references/sub-agent-procedure.md, and the
    model-b skill has a valid SKILL.md."""

    PROCEDURE_MD = CLAUDE_DIR / "skills" / "model-b" / "references" / "sub-agent-procedure.md"
    SKILL_MD = CLAUDE_DIR / "skills" / "model-b" / "SKILL.md"

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
    """§S4 — nothing under agents/memory/skills references the retired
    agent-baseline / orchestration-universal shim files by name."""

    AGENTS_DIR = CLAUDE_DIR / "agents"
    MEMORY_DIR = CLAUDE_DIR / "memory"
    SKILLS_DIR = CLAUDE_DIR / "skills"

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
    """§S5 — the shim files are physically removed from ~/.claude/memory,
    archived copies exist in the repo, and chezmoi's view of ~/.claude is
    clean (no drift, no resurrection of the retired files on dry-run apply)."""

    AGENT_BASELINE_SHIM = CLAUDE_DIR / "memory" / "agent-baseline.md"
    ORCH_UNIVERSAL_SHIM = CLAUDE_DIR / "memory" / "orchestration-universal.md"
    ARCHIVE_AGENT_BASELINE = REPO_ROOT / "archive" / "wave1" / "agent-baseline.md"
    ARCHIVE_ORCH_UNIVERSAL = REPO_ROOT / "archive" / "wave1" / "orchestration-universal.md"

    def test_s5_shim_files_removed_from_memory(self):
        # NEGATIVE — these must NOT exist anymore (bound: exactly absent, not "reduced").
        self.assertFalse(
            self.AGENT_BASELINE_SHIM.exists(),
            f"{self.AGENT_BASELINE_SHIM} must be removed",
        )
        self.assertFalse(
            self.ORCH_UNIVERSAL_SHIM.exists(),
            f"{self.ORCH_UNIVERSAL_SHIM} must be removed",
        )

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

    def test_s5_chezmoi_diff_clean_on_cr_touched_paths(self):
        """chezmoi's source state must exactly match the live state of the
        specific paths CR-MODELB-001 touches (AGENTS.md, CLAUDE.md, agents/,
        memory/, skills/). Pre-existing, out-of-scope drift elsewhere in the
        dotfiles tree (e.g. .bashrc) is NOT part of this AC and is excluded
        by scoping the diff to these five target args."""
        chezmoi = shutil.which("chezmoi")
        if chezmoi is None:
            self.skipTest("chezmoi binary not found on PATH — cannot verify dotfile-manager drift")
        result = subprocess.run(
            [
                chezmoi, "diff",
                str(CLAUDE_DIR / "AGENTS.md"),
                str(CLAUDE_DIR / "CLAUDE.md"),
                str(CLAUDE_DIR / "agents"),
                str(CLAUDE_DIR / "memory"),
                str(CLAUDE_DIR / "skills"),
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        # POSITIVE — chezmoi's source state must exactly match the live state
        # of the CR-touched paths only.
        self.assertEqual(
            result.stdout.strip(), "",
            f"chezmoi diff on CR-touched paths must be empty (no drift), got ({len(result.stdout)} chars):\n"
            f"{result.stdout[:2000]}",
        )
        # EXACT bound — a clean exit is required too. An "unmanaged path"
        # abort (e.g. "chezmoi: ~/.claude/AGENTS.md: not managed", exit 1)
        # produces empty stdout WITHOUT proving the CR-touched paths are
        # actually drift-free, so it must FAIL this gate, not vacuously pass
        # it. GREEN must bring AGENTS.md and the CLAUDE.md symlink under
        # chezmoi management for this check to pass meaningfully.
        self.assertEqual(
            result.returncode, 0,
            "chezmoi diff on CR-touched paths must exit 0 — a non-zero exit "
            "(e.g. an 'unmanaged path' abort) means chezmoi never actually "
            f"compared the paths, even if stdout looked empty. stderr:\n{result.stderr[:2000]}",
        )

    def test_s5_chezmoi_apply_dry_run_no_shim_mentions(self):
        chezmoi = shutil.which("chezmoi")
        if chezmoi is None:
            self.skipTest("chezmoi binary not found on PATH — cannot verify dry-run apply output")
        result = subprocess.run(
            [chezmoi, "apply", "--dry-run", "--verbose", str(CLAUDE_DIR)],
            capture_output=True,
            text=True,
            timeout=60,
        )
        combined = result.stdout + result.stderr
        agent_baseline_mentions = combined.count("agent-baseline")
        orch_universal_mentions = combined.count("orchestration-universal")
        # EXACT bounds — a non-mutating dry-run apply must not attempt to
        # resurrect either retired shim file.
        self.assertEqual(
            agent_baseline_mentions, 0,
            f"dry-run apply output must not mention 'agent-baseline', found {agent_baseline_mentions} "
            f"time(s) (showing first 2000 chars):\n{combined[:2000]}",
        )
        self.assertEqual(
            orch_universal_mentions, 0,
            f"dry-run apply output must not mention 'orchestration-universal', found "
            f"{orch_universal_mentions} time(s) (showing first 2000 chars):\n{combined[:2000]}",
        )


if __name__ == "__main__":
    unittest.main()
