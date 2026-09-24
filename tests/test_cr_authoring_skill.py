"""RED-phase tests for CR-MDB-004 (cr-authoring skill: doc model +
project-management split).

Originally written against the LIVE ~/.claude tree. CR-MDB-032 SS2
retargeted them to the repo (the 2026-07-22 repo-local authoring rule): the
skill under skills-src/cr-authoring/, the archive/wave2/ copies, the memory
templates under skills-src/memory-templates/, the rendered agents under
generator/agents/ and the repo AGENTS.md. The live-memory absence half of SS3
was deleted; the two named consumers with no repo copy (QUICK_REFERENCE.md,
chezmoi-integration.md) left the SS4 surface list.

Stdlib only (unittest + subprocess + pathlib + os). No SUT import: this CR's
deliverable is markdown/skill content, not Python modules.
"""

import os
import subprocess
import unittest
from pathlib import Path

from tests._helpers import read_text_lenient as _read, split_frontmatter as _split_frontmatter

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS_SRC_DIR = REPO_ROOT / "skills-src"
MEMORY_TEMPLATES_DIR = SKILLS_SRC_DIR / "memory-templates"
REPO_AGENTS_MD = REPO_ROOT / "AGENTS.md"

SKILL_DIR = SKILLS_SRC_DIR / "cr-authoring"
SKILL_MD = SKILL_DIR / "SKILL.md"
REFERENCES_DIR = SKILL_DIR / "references"
CREQ_CRES_MD = REFERENCES_DIR / "creq-cres.md"

ARCHIVE_WAVE2 = REPO_ROOT / "archive" / "wave2"

# §S4 consumer surfaces the CR spec names explicitly that have a repo copy.
CONSUMER_SURFACES = (
    MEMORY_TEMPLATES_DIR / "rust-orchestration.md",
    MEMORY_TEMPLATES_DIR / "java-orchestration.md",
    REPO_AGENTS_MD,
)

STALE_REF_PATTERN = r"cr-prd-dn-conventions\|project-management.md"


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


class CrAuthoringSkillS2Test(unittest.TestCase):
    """SS2 -- NEW skill skills-src/cr-authoring/ (doc model +
    2026-07-20 queue-idiom rules)."""

    def test_s2_skill_md_frontmatter_name_and_description(self):
        self.assertTrue(SKILL_MD.is_file(), f"{SKILL_MD} must exist")
        content = _read(SKILL_MD)
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
            name_lines[0].split(":", 1)[1].strip(), "cr-authoring",
            f"frontmatter 'name:' must be exactly 'cr-authoring', got: {name_lines[0]!r}",
        )

        description_lines = [
            ln for ln in frontmatter.splitlines() if ln.strip().startswith("description:")
        ]
        self.assertEqual(
            len(description_lines), 1,
            f"frontmatter must have exactly one 'description:' key, found: {description_lines}",
        )
        description = description_lines[0].split(":", 1)[1]
        # POSITIVE -- description must contain both "CR" and "PRD".
        self.assertIn("CR", description, "frontmatter description must contain 'CR'")
        self.assertIn("PRD", description, "frontmatter description must contain 'PRD'")

    def test_s2_skill_md_contains_required_doc_model_and_queue_idiom_anchors(self):
        self.assertTrue(SKILL_MD.is_file(), f"{SKILL_MD} must exist")
        content = _read(SKILL_MD)

        required_terms = [
            "Design reference",
            "§S",
            "Depends on",
            "DERIVED",
            "release CR",
            "grouping of CRs",
        ]
        missing = [term for term in required_terms if term not in content]
        # POSITIVE -- every required doc-model/queue-idiom term must appear.
        self.assertEqual(
            missing, [],
            f"SKILL.md missing required doc-model/queue-idiom terms: {missing}",
        )

        # POSITIVE -- structure-only queue rule, tolerant of hyphen variant.
        structure_only_variants = ("structure only", "structure-only")
        has_structure_only = any(v in content for v in structure_only_variants)
        self.assertTrue(
            has_structure_only,
            f"SKILL.md must contain 'structure only' or 'structure-only', tried {structure_only_variants}",
        )

        # POSITIVE -- the AC-precision test line, verbatim-equivalent tolerant.
        ac_test_variants = (
            "Can I write the assertion directly from this AC?",
            "Can I write the assertion directly from this AC",
        )
        has_ac_test_line = any(v in content for v in ac_test_variants)
        self.assertTrue(
            has_ac_test_line,
            f"SKILL.md must contain the AC precision test line, tried {ac_test_variants}",
        )

    def test_s2_skill_md_not_empty_and_creq_cres_reference_exists(self):
        self.assertTrue(SKILL_MD.is_file(), f"{SKILL_MD} must exist")
        content = _read(SKILL_MD)
        # POSITIVE sanity -- the file must actually have content to check.
        self.assertGreater(len(content.strip()), 0, "SKILL.md must not be empty")

        self.assertTrue(
            CREQ_CRES_MD.is_file(), f"{CREQ_CRES_MD} must exist"
        )
        creq_content = _read(CREQ_CRES_MD)
        # POSITIVE -- both CReq and CRes terms must appear in the extracted
        # reference file (the INBOX/OUTBOX library-communication pattern).
        self.assertIn("CReq", creq_content, "references/creq-cres.md must contain 'CReq'")
        self.assertIn("CRes", creq_content, "references/creq-cres.md must contain 'CRes'")
        self.assertGreater(
            len(creq_content.strip()), 0, "references/creq-cres.md must not be empty"
        )


class CrAuthoringSkillS3Test(unittest.TestCase):
    """SS3 -- project-management.md split + deletion (content-preserving
    archive)."""

    def test_s3_legacy_memory_files_removed_with_archived_content(self):
        # POSITIVE -- an archived, content-preserving copy of each must
        # exist under <repo>/archive/wave2/ (tolerant of exact layout: name
        # as a path component or matching filename, plus a content anchor
        # proving it's a real move, not a stub).
        not_archived = []
        if not _archive_has_content_move(
            "cr-prd-dn-conventions.md",
            "Can I write the assertion directly from this AC?",
        ):
            not_archived.append("cr-prd-dn-conventions.md")
        if not _archive_has_content_move(
            "project-management.md",
            "CReq",
        ):
            not_archived.append("project-management.md")
        self.assertEqual(
            not_archived, [],
            f"expected an archived copy retaining its anchor under {ARCHIVE_WAVE2} "
            f"for every deletion target, missing/anchor-less for: {not_archived}",
        )


class CrAuthoringSkillS4Test(unittest.TestCase):
    """SS4 -- repoint consumers away from the retired memory files."""

    def test_s4_grep_gate_zero_stale_references_across_consumers(self):
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
            f"grep gate must return 0 files referencing cr-prd-dn-conventions/"
            f"project-management.md, found: {matched_files}",
        )

    def test_s4_named_consumer_surfaces_no_longer_reference_retired_files(self):
        """Belt-and-suspenders per-file check on the exact surfaces the CR
        spec names that have a repo copy (the rust/java orchestration
        memory templates and AGENTS.md) -- none may still mention the
        retired memory file paths, and AGENTS.md must name the
        cr-authoring skill."""
        still_stale = []
        for path in CONSUMER_SURFACES:
            if not path.is_file():
                # Missing entirely is not a stale-reference failure by
                # itself; the grep gate above covers existence-independent
                # scanning. Skip silently here.
                continue
            content = _read(path)
            if "cr-prd-dn-conventions" in content or "project-management.md" in content:
                still_stale.append(str(path))
        # NEGATIVE -- none of the named consumer surfaces may still
        # reference the retired memory file paths.
        self.assertEqual(
            still_stale, [],
            f"expected zero named consumer surfaces still referencing retired paths, "
            f"found: {still_stale}",
        )

        # POSITIVE -- AGENTS.md's CR/PRD/DN trigger row must repoint to the
        # new cr-authoring skill.
        self.assertTrue(REPO_AGENTS_MD.is_file(), f"{REPO_AGENTS_MD} must exist")
        agents_content = _read(REPO_AGENTS_MD)
        self.assertIn(
            "cr-authoring", agents_content,
            "AGENTS.md must point CR/PRD/DN authoring at the 'cr-authoring' skill",
        )


if __name__ == "__main__":
    unittest.main()
