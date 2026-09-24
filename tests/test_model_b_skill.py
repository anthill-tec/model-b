"""RED-phase tests for CR-MDB-002 (model-b skill: canonical definition +
universal conventions).

Originally written against the LIVE ~/.claude tree. CR-MDB-032 SS2
retargeted them to the repo (the 2026-07-22 repo-local authoring rule): the
skill under skills-src/model-b/, the archive/wave2/ copies, and the grep gate
over skills-src/ + the repo AGENTS.md. The live-memory absence half of SS4 and
the ~/.claude/AGENTS.md trigger-table row check (the repo AGENTS.md carries no
trigger table) were deleted.

Stdlib only (unittest + subprocess + pathlib + os).
"""

import subprocess
import unittest
from pathlib import Path

from tests._helpers import (
    files_containing as _files_containing,
    read_text_lenient as _read,
    split_frontmatter as _split_frontmatter,
)

REPO_ROOT = Path(__file__).resolve().parent.parent

SKILL_DIR = REPO_ROOT / "skills-src" / "model-b"
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
            # The plan idiom's orchestrator flag: `--orchestrator` was retired by
            # the CR-MDB-017 verb sweep (the registered `--agent` id IS the plan's
            # orchestrator); the stale deployed copy still said `--orchestrator`.
            "--agent",
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
    """SS4 -- memory deletions: the four source files have content-preserving
    archived copies in the repo."""

    MEMORY_FILES = (
        "orchestration-common.md",
        "orchestration-mainline.md",
        "orchestration-track.md",
        "sandesh.md",
    )

    def test_s4_memory_shim_files_removed_and_archived_under_wave2_with_preserved_content(self):
        for filename in self.MEMORY_FILES:
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


class ModelBSkillS5Test(unittest.TestCase):
    """SS5 -- consumers are repointed away from the retired
    memory/orchestration-* and memory/sandesh.md paths."""

    def test_s5_grep_gate_zero_stale_memory_references_in_skills_and_agents_md(self):
        result = subprocess.run(
            [
                "grep", "-rl", "memory/orchestration-\\|memory/sandesh",
                str(REPO_ROOT / "skills-src"),
                str(REPO_ROOT / "AGENTS.md"),
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

if __name__ == "__main__":
    unittest.main()
