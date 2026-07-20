"""RED-phase tests for CR-MDB-002 (model-b skill: canonical definition +
universal conventions).

These tests assert the acceptance criteria of CR-MDB-002 SS2-SS5 against the
LIVE ~/.claude tree on this machine. They are intentionally written before
the GREEN-phase work (SKILL.md full body, references/ population, memory
deletions, consumer repointing) lands, so most of them are expected to FAIL
against the current (pre-CR-MDB-002) state of ~/.claude. A few ACs may
already hold true incidentally (e.g. the stub's description already
mentions "orchestration" and "sub-agent") -- that is fine, the SUITE overall
must be RED, not necessarily every single test.

Stdlib only (unittest + subprocess + pathlib + os).
"""

import os
import subprocess
import unittest
from pathlib import Path

CLAUDE_DIR = Path.home() / ".claude"
REPO_ROOT = Path(__file__).resolve().parent.parent

SKILL_DIR = CLAUDE_DIR / "skills" / "model-b"
SKILL_MD = SKILL_DIR / "SKILL.md"
REFERENCES_DIR = SKILL_DIR / "references"
ARCHIVE_WAVE2 = REPO_ROOT / "archive" / "wave2"

# Distinctive anchor each SS3 reference file must retain (content-preserving
# move), shared with the SS4 archived-copy check since the archive copy is
# taken from the very same source file.
REFERENCE_ANCHORS = {
    "orchestration-common.md": "MODE-MAP",
    "orchestration-mainline.md": "SCRUM",
    "orchestration-track.md": "NEVER self-schedule",
    "sandesh.md": "PRIME DIRECTIVE",
}


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


def _split_frontmatter(content: str):
    """Split a skill markdown file into (frontmatter, body) on the '---' delimiters.

    Returns ("", content) if the file has no well-formed '---' frontmatter block.
    """
    lines = content.splitlines()
    if not lines or lines[0].strip() != "---":
        return "", content
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            frontmatter = "\n".join(lines[1:idx])
            body = "\n".join(lines[idx + 1:])
            return frontmatter, body
    return "", content


class ModelBSkillS2Test(unittest.TestCase):
    """SS2 -- SKILL.md full body (replaces the stub)."""

    def test_s2_skill_md_frontmatter_has_name_model_b_and_description_with_required_keywords(self):
        self.assertTrue(SKILL_MD.is_file(), f"{SKILL_MD} must exist")
        frontmatter, _body = _split_frontmatter(_read(SKILL_MD))

        name_lines = [ln for ln in frontmatter.splitlines() if ln.strip() == "name: model-b"]
        # POSITIVE -- exactly one frontmatter line declares the skill name.
        self.assertEqual(
            len(name_lines), 1,
            f"SKILL.md frontmatter must contain exactly one 'name: model-b' line, found {len(name_lines)}",
        )

        description_lines = [
            ln for ln in frontmatter.splitlines()
            if ln.strip().startswith("description:") and ln.strip() != "description:"
        ]
        self.assertGreaterEqual(
            len(description_lines), 1,
            "SKILL.md frontmatter must contain a non-empty 'description:' line",
        )
        description_value = description_lines[0].split("description:", 1)[1].strip()
        # POSITIVE -- description must carry both workflow-scoped trigger keywords.
        self.assertIn(
            "orchestration", description_value,
            f"description must contain 'orchestration', got: {description_value!r}",
        )
        self.assertIn(
            "sub-agent", description_value,
            f"description must contain 'sub-agent', got: {description_value!r}",
        )
        # NEGATIVE bound -- description must not be a blank/empty value.
        self.assertNotEqual(description_value, "", "description value must not be empty")

    def test_s2_skill_md_body_contains_required_convention_terms(self):
        self.assertTrue(SKILL_MD.is_file(), f"{SKILL_MD} must exist")
        _frontmatter, body = _split_frontmatter(_read(SKILL_MD))

        required_terms = [
            "vidushi-",
            "Mainline-<",
            "track<N>-<",
            "track-<n>",
            "red-green",
            "verify",
            "fix",
            "sync boundary",
            "plan-file",
            "--wave",
            "--orchestrator",
            "PROJECT_ACRONYM",
            "release",
        ]
        missing = [term for term in required_terms if term not in body]
        # POSITIVE -- every required convention term from the AC must appear
        # somewhere in the body (checked as one list so the failure message
        # names exactly which terms are still missing).
        self.assertEqual(
            missing, [],
            f"SKILL.md body missing required convention terms: {missing}",
        )

    def test_s2_skill_md_body_zero_close_out_wave_mentions(self):
        self.assertTrue(SKILL_MD.is_file(), f"{SKILL_MD} must exist")
        _frontmatter, body = _split_frontmatter(_read(SKILL_MD))
        occurrences = body.count("close-out wave")
        # EXACT bound -- release CRs must never be described as having a close-out wave.
        self.assertEqual(
            occurrences, 0,
            f"SKILL.md body must contain zero 'close-out wave' mentions, found {occurrences}",
        )

    def test_s2_skill_md_body_zero_plan_b_and_orchestration_universal_mentions(self):
        self.assertTrue(SKILL_MD.is_file(), f"{SKILL_MD} must exist")
        _frontmatter, body = _split_frontmatter(_read(SKILL_MD))
        # POSITIVE sanity -- the body must actually have content to check.
        self.assertGreater(len(body.strip()), 0, "SKILL.md body must not be empty")
        plan_b_count = body.count("Plan B")
        orchestration_universal_count = body.count("orchestration-universal")
        # EXACT bounds on both forbidden terms.
        self.assertEqual(plan_b_count, 0, f"expected zero 'Plan B' mentions, found {plan_b_count}")
        self.assertEqual(
            orchestration_universal_count, 0,
            f"expected zero 'orchestration-universal' mentions, found {orchestration_universal_count}",
        )


class ModelBSkillS3Test(unittest.TestCase):
    """SS3 -- references/ population (content-preserving move of the four
    orchestration/sandesh docs into skills/model-b/references/)."""

    def test_s3_all_four_reference_files_exist_with_distinctive_anchors(self):
        for filename, anchor in REFERENCE_ANCHORS.items():
            path = REFERENCES_DIR / filename
            self.assertTrue(
                path.is_file(),
                f"{path} must exist under {REFERENCES_DIR}",
            )
            content = _read(path)
            # POSITIVE -- the moved file retains its distinctive anchor phrase
            # (proves content-preserving move, not an empty/renamed stub).
            self.assertIn(
                anchor, content,
                f"{filename} must retain its distinctive anchor {anchor!r}",
            )
            # NEGATIVE bound -- must not be an empty stub.
            self.assertGreater(len(content.strip()), 0, f"{filename} must not be empty")

    def test_s3_zero_plan_b_mentions_across_model_b_skill_dir(self):
        self.assertTrue(SKILL_DIR.is_dir(), f"{SKILL_DIR} must exist")
        hits = _files_containing(SKILL_DIR, "Plan B")
        # EXACT bound -- zero files anywhere under skills/model-b/ may mention "Plan B".
        self.assertEqual(
            hits, [],
            f"expected zero files under {SKILL_DIR} referencing 'Plan B', found: {hits}",
        )


class ModelBSkillS4Test(unittest.TestCase):
    """SS4 -- memory deletions (chezmoi discipline): the four source files are
    archived into the repo then physically removed from ~/.claude/memory."""

    MEMORY_FILES = (
        "orchestration-common.md",
        "orchestration-mainline.md",
        "orchestration-track.md",
        "sandesh.md",
    )

    def test_s4_memory_shim_files_removed_and_archived_under_wave2_with_preserved_content(self):
        for filename in self.MEMORY_FILES:
            live = CLAUDE_DIR / "memory" / filename
            # NEGATIVE -- must NOT exist any more in the live memory tree.
            self.assertFalse(live.exists(), f"{live} must be removed from ~/.claude/memory")

            archived = ARCHIVE_WAVE2 / filename
            # POSITIVE -- an archived copy must exist in the repo.
            self.assertTrue(archived.is_file(), f"{archived} must exist")

            archived_content = _read(archived)
            anchor = REFERENCE_ANCHORS[filename]
            # Behavioural -- the archived copy is a real copy of the original
            # content (retains its distinctive anchor), not an empty stub.
            self.assertIn(
                anchor, archived_content,
                f"archived {filename} must retain its distinctive anchor {anchor!r}",
            )
            self.assertGreater(len(archived_content.strip()), 0, f"archived {filename} must not be empty")

    def test_s4_chezmoi_diff_clean_on_cr_touched_paths(self):
        """chezmoi's source state must exactly match the live state of the
        specific paths CR-MDB-002 touches (AGENTS.md, CLAUDE.md, agents/,
        memory/, skills/), per the AC's exact `chezmoi diff` invocation."""
        import shutil

        chezmoi = shutil.which("chezmoi")
        if chezmoi is None:
            self.skipTest("chezmoi binary not found on PATH -- cannot verify dotfile-manager drift")
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


class ModelBSkillS5Test(unittest.TestCase):
    """SS5 -- repoint consumers away from the retired memory/orchestration-*
    and memory/sandesh.md paths, and drop the transitional "until Wave 2"
    caveat from AGENTS.md's trigger table."""

    def test_s5_grep_gate_zero_stale_memory_references_in_skills_and_agents_md(self):
        result = subprocess.run(
            [
                "grep", "-rl", "memory/orchestration-\\|memory/sandesh",
                str(CLAUDE_DIR / "skills"),
                str(CLAUDE_DIR / "AGENTS.md"),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        matched_files = [ln for ln in result.stdout.splitlines() if ln.strip()]
        # EXACT bound -- the AC requires this grep to return zero files.
        self.assertEqual(
            matched_files, [],
            f"grep gate must return 0 files referencing memory/orchestration-* or "
            f"memory/sandesh, found: {matched_files}",
        )

    def test_s5_agents_md_trigger_table_model_b_row_has_no_until_wave_2_caveat(self):
        """The Model B WORKFLOW trigger-table row (topic cell starts with
        'Model B workflow', target `model-b` skill) must exist exactly once
        and carry no transitional "until Wave 2" caveat. Selects by the
        topic cell -- not by any-row-containing-"model-b" -- so other rows
        that merely mention the model-b repo (e.g. the memory-templates
        row added by CR-MDB-006) don't trip the exactly-one bound."""
        self.assertTrue(
            (CLAUDE_DIR / "AGENTS.md").is_file(),
            f"{CLAUDE_DIR / 'AGENTS.md'} must exist",
        )
        content = _read(CLAUDE_DIR / "AGENTS.md")
        lines = content.splitlines()
        model_b_workflow_rows = [
            ln for ln in lines
            if ln.strip().startswith("|")
            and ln.strip().lstrip("|").strip().startswith("Model B workflow")
        ]
        # POSITIVE -- the trigger table must still carry the Model B workflow
        # row after repointing.
        self.assertEqual(
            len(model_b_workflow_rows), 1,
            f"expected exactly one 'Model B workflow' trigger-table row, "
            f"found {len(model_b_workflow_rows)}: {model_b_workflow_rows}",
        )
        # NEGATIVE/EXACT bound -- that row must no longer carry the
        # transitional "until Wave 2" caveat.
        self.assertNotIn(
            "until Wave 2", model_b_workflow_rows[0],
            f"'Model B workflow' trigger-table row must not contain "
            f"'until Wave 2': {model_b_workflow_rows[0]!r}",
        )


if __name__ == "__main__":
    unittest.main()
