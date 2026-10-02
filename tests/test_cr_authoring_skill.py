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

import subprocess
import unittest
from pathlib import Path

from tests._helpers import archive_has_content_move as _archive_has_content_move
from tests._helpers import md_section
from tests._helpers import read_text_lenient as _read
from tests._helpers import split_frontmatter as _split_frontmatter

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

#: The CR-042 triage heading CR-MDB-048 §S1 keeps verbatim while its body changes.
QUEUE_IDIOM_HEADING = "The CR queue — structure only (queue idiom, 2026-07-20)"


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
        """MIGRATED at CR-MDB-048 C1 RED (§S1: the board holds the queue). Was: the
        queue-idiom anchors ``DERIVED`` (statuses derived on the board, a README rule),
        ``release CR`` and ``structure only`` / ``structure-only`` anywhere in the file. Now:
        the CR-042 triage heading stays verbatim, its body files a CR on the board (``cr-plan``,
        ``cr-depends``, ``wave-sequence``), and "a release is not a CR" keeps its rule."""
        self.assertTrue(SKILL_MD.is_file(), f"{SKILL_MD} must exist")
        content = _read(SKILL_MD)

        required_terms = [
            "Design reference",
            "§S",
            "Depends on",
            "grouping of CRs",
        ]
        missing = [term for term in required_terms if term not in content]
        # POSITIVE -- every required doc-model term must appear.
        self.assertEqual(
            missing, [],
            f"SKILL.md missing required doc-model terms: {missing}",
        )

        # POSITIVE -- the release rule, as the spec states it (case-insensitive).
        self.assertIn(
            "a release is not a cr", content.replace("*", "").lower(),
            "SKILL.md must keep the rule 'a release is not a CR'",
        )

        # POSITIVE -- the kept CR-042 heading's body files the CR on the board.
        queue_section = md_section(content, f"## {QUEUE_IDIOM_HEADING}")
        self.assertNotEqual(
            queue_section, "",
            f"SKILL.md must keep the heading '## {QUEUE_IDIOM_HEADING}' verbatim",
        )
        verbs_missing = [verb for verb in ("cr-plan", "cr-depends", "wave-sequence")
                         if f"`{verb}" not in queue_section]
        self.assertEqual(
            verbs_missing, [],
            f"the queue-idiom section must file a CR on the board; missing verbs: {verbs_missing}",
        )
        # NEGATIVE -- the section no longer makes the README the queue.
        self.assertNotIn("`docs/changes/README.md` is the queue", queue_section)

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
