"""RED-phase tests for CR-MDB-006 (memory model: global -> project-level
migration).

Originally written against the LIVE ~/.claude tree AND this repo. CR-MDB-032
SS2 retargeted them to the repo only (the 2026-07-22 repo-local authoring
rule): the memory templates under skills-src/memory-templates/, the
archive/wave2/ copies, and the consumer grep gate over skills-src/,
generator/agents/ and the repo AGENTS.md. Deleted as real-home-only: the
~/.claude/memory set equality (SS4), the live absence half of SS3, and the
two ~/.claude/AGENTS.md trigger-row checks (SS2 Java row, SS5
scaffold-instantiated row) -- the repo AGENTS.md carries no trigger table.

Stdlib only (unittest + subprocess + pathlib + os). No SUT import: this CR's
deliverable is markdown/template content, not Python modules.
"""

import subprocess
import unittest
from pathlib import Path

from tests._helpers import (
    archive_has_content_move as _archive_has_content_move,
    read_text_lenient as _read,
)

REPO_ROOT = Path(__file__).resolve().parent.parent

SKILLS_SRC_DIR = REPO_ROOT / "skills-src"
AGENTS_MD = REPO_ROOT / "AGENTS.md"
MEMORY_TEMPLATES_DIR = SKILLS_SRC_DIR / "memory-templates"

JAVA_TESTING_PRACTICES_MD = MEMORY_TEMPLATES_DIR / "java-testing-practices.md"

# SS4 relocation targets.
JAVA_ORCHESTRATION_TEMPLATE = MEMORY_TEMPLATES_DIR / "java-orchestration.md"
RUST_ORCHESTRATION_TEMPLATE = MEMORY_TEMPLATES_DIR / "rust-orchestration.md"
OPERATIONAL_COMMANDS_TEMPLATE = MEMORY_TEMPLATES_DIR / "operational-commands.md"

ARCHIVE_WAVE2 = REPO_ROOT / "archive" / "wave2"

# SS4's relocated scaffold templates left ~/.claude/memory, so the live SS5
# gate never scanned them; the repo gate keeps that scope.
SS5_GATE_EXCLUDED = frozenset({
    JAVA_ORCHESTRATION_TEMPLATE, RUST_ORCHESTRATION_TEMPLATE, OPERATIONAL_COMMANDS_TEMPLATE,
})

# SS5's AC names this exact grep invocation verbatim.
STALE_REF_PATTERN = (
    r"QUICK_REFERENCE\|stack-detection\|plan_b_workflow\|devops-environment"
    r"\|memory/java-orchestration\|memory/rust-orchestration"
    r"\|memory/operational-commands"
)


class MemoryModelS2Test(unittest.TestCase):
    """SS2 -- merge the UNIQUE content of memory/devops-environment.md into
    memory/java-testing-practices.md (TestContainers, DevServices, @Nested
    continuous-testing gotcha, container-runtime/Podman, CI considerations),
    and wire the orphaned java-modern-syntax.md into the AGENTS.md Java
    stack-reference row (the AGENTS.md half was real-home only and is
    deleted, CR-MDB-032 SS2)."""

    def test_s2_java_testing_practices_contains_full_merge_anchor_set(self):
        self.assertTrue(
            JAVA_TESTING_PRACTICES_MD.is_file(),
            f"{JAVA_TESTING_PRACTICES_MD} must exist",
        )
        content = _read(JAVA_TESTING_PRACTICES_MD)

        # POSITIVE -- the AC's conjunction of 3 literal required terms.
        required_terms = ["TestContainers", "DevServices", "@Nested"]
        missing = [term for term in required_terms if term not in content]
        self.assertEqual(
            missing, [],
            f"{JAVA_TESTING_PRACTICES_MD} missing required merge-anchor terms: {missing}",
        )

        # POSITIVE -- "Podman" OR "container runtime" per the AC's own
        # tolerant alternative.
        container_runtime_variants = ("Podman", "container runtime")
        has_container_runtime = any(v in content for v in container_runtime_variants)
        self.assertTrue(
            has_container_runtime,
            f"{JAVA_TESTING_PRACTICES_MD} must contain 'Podman' or 'container runtime', "
            f"tried {container_runtime_variants}",
        )

class MemoryModelS3Test(unittest.TestCase):
    """SS3 -- delete QUICK_REFERENCE.md (superseded by the trigger table),
    stack-detection.md (superseded by the crucible skill),
    plan_b_workflow_model.md (broken mis-paste; canonical = model-b skill),
    devops-environment.md (after SS2 merge) -- archived, content preserved
    under <repo>/archive/wave2/."""

    def test_s3_deletion_targets_removed_with_content_preserving_archive(self):
        # POSITIVE -- an archived, content-preserving copy of each must
        # exist under <repo>/archive/wave2/ (tolerant of exact layout, plus
        # a content anchor proving it's a real move, not a stub).
        not_archived = []
        if not _archive_has_content_move(
            "QUICK_REFERENCE.md", "Memory Files Quick Reference",
        ):
            not_archived.append("QUICK_REFERENCE.md")
        if not _archive_has_content_move(
            "stack-detection.md", "Stack Detection",
        ):
            not_archived.append("stack-detection.md")
        if not _archive_has_content_move(
            "plan_b_workflow_model.md",
            "Plan B project model is a structural framework",
        ):
            not_archived.append("plan_b_workflow_model.md")
        if not _archive_has_content_move(
            "devops-environment.md", "DevOps Environment Configuration",
        ):
            not_archived.append("devops-environment.md")
        self.assertEqual(
            not_archived, [],
            f"expected an archived copy retaining its anchor under {ARCHIVE_WAVE2} "
            f"for every SS3 deletion target, missing/anchor-less for: {not_archived}",
        )


class MemoryModelS4Test(unittest.TestCase):
    """SS4 -- move java-orchestration.md, rust-orchestration.md,
    operational-commands.md to <repo>/skills-src/memory-templates/ (D10.6
    scaffold source material), fixing rust-orchestration.md's dangling
    memory/sandesh.md reference to
    ~/.claude/skills/model-b/references/sandesh.md. (The ~/.claude/memory
    end-state set equality was real-home only and is dropped, CR-MDB-032
    SS2.)"""

    def test_s4_relocated_template_files_exist_in_repo(self):
        template_files = {
            "java-orchestration.md": JAVA_ORCHESTRATION_TEMPLATE,
            "rust-orchestration.md": RUST_ORCHESTRATION_TEMPLATE,
            "operational-commands.md": OPERATIONAL_COMMANDS_TEMPLATE,
        }
        missing = [name for name, path in template_files.items() if not path.is_file()]
        # POSITIVE -- all 3 relocation targets must exist under
        # skills-src/memory-templates/ in this repo.
        self.assertEqual(
            missing, [],
            f"expected all 3 SS4 template files under {MEMORY_TEMPLATES_DIR}, "
            f"missing: {missing}",
        )

        # NEGATIVE/bound -- each relocated template must carry real content,
        # not an empty stub.
        empty = [name for name, path in template_files.items() if path.is_file() and len(_read(path).strip()) == 0]
        self.assertEqual(
            empty, [],
            f"expected non-empty relocated template content, empty for: {empty}",
        )

    def test_s4_rust_orchestration_template_sandesh_reference_fixed(self):
        self.assertTrue(
            RUST_ORCHESTRATION_TEMPLATE.is_file(),
            f"{RUST_ORCHESTRATION_TEMPLATE} must exist",
        )
        content = _read(RUST_ORCHESTRATION_TEMPLATE)

        # POSITIVE -- the fixed reference must be present.
        self.assertIn(
            "skills/model-b/references/sandesh.md", content,
            f"{RUST_ORCHESTRATION_TEMPLATE} must contain the fixed "
            "'skills/model-b/references/sandesh.md' reference",
        )
        # NEGATIVE -- the dangling reference must be gone, exactly zero
        # occurrences (not "reduced").
        dangling_count = content.count("memory/sandesh.md")
        self.assertEqual(
            dangling_count, 0,
            f"{RUST_ORCHESTRATION_TEMPLATE} must contain zero occurrences of "
            f"the dangling 'memory/sandesh.md' reference, found {dangling_count}",
        )

class MemoryModelS5Test(unittest.TestCase):
    """SS5 -- repoint consumers: AGENTS.md Java row adds java-modern-syntax.md
    and drops java-orchestration.md; Rust-stack row and Operational-commands
    row replaced by one scaffold-instantiated row; the 4 quarkus agent defs'
    java-orchestration.md citations repointed."""

    def test_s5_grep_gate_zero_stale_references_across_consumers(self):
        result = subprocess.run(
            [
                "grep", "-rl", STALE_REF_PATTERN,
                str(SKILLS_SRC_DIR),
                str(AGENTS_MD),
                str(REPO_ROOT / "generator" / "agents"),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        matched_files = [
            ln for ln in result.stdout.splitlines()
            if ln.strip() and Path(ln) not in SS5_GATE_EXCLUDED
        ]
        # EXACT bound -- the AC requires this exact grep invocation to
        # return zero files.
        self.assertEqual(
            matched_files, [],
            "grep gate must return 0 files referencing QUICK_REFERENCE, "
            "stack-detection, plan_b_workflow, devops-environment, "
            f"memory/java-orchestration, memory/rust-orchestration or "
            f"memory/operational-commands, found: {matched_files}",
        )

if __name__ == "__main__":
    unittest.main()
