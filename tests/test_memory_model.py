"""RED-phase tests for CR-MDB-006 (memory model: global -> project-level
migration).

These tests assert the acceptance criteria of CR-MDB-006 SS2-SS5 against the
LIVE ~/.claude tree on this machine AND this repo. They are intentionally
written before the GREEN-phase work (the devops-environment.md merge into
java-testing-practices.md, the java-modern-syntax.md AGENTS.md wiring, the
SS3 deletions with archival, the SS4 relocations to
skills-src/memory-templates/, and the SS5 consumer repoints) lands, so most
of them are expected to FAIL against the current (pre-CR-MDB-006) state.
The suite overall must be RED, not necessarily every single test (some
content greps may vacuously pass depending on what already happens to be
true of the live tree today -- that is still correct behaviour, not a test
bug; see e.g. the SS2 merge-anchor test, and the SS4 chezmoi-diff test which
is a no-drift regression guard that legitimately holds before any live edits
have been made).

Stdlib only (unittest + subprocess + pathlib + os). No SUT import: this CR's
deliverable is markdown/template content, not Python modules.
"""

import os
import subprocess
import unittest
from pathlib import Path

CLAUDE_DIR = Path.home() / ".claude"
REPO_ROOT = Path(__file__).resolve().parent.parent

MEMORY_DIR = CLAUDE_DIR / "memory"
AGENTS_MD = CLAUDE_DIR / "AGENTS.md"

JAVA_TESTING_PRACTICES_MD = MEMORY_DIR / "java-testing-practices.md"

# SS3 deletion targets (post SS2-merge for devops-environment.md).
QUICK_REFERENCE_MD = MEMORY_DIR / "QUICK_REFERENCE.md"
STACK_DETECTION_MD = MEMORY_DIR / "stack-detection.md"
PLAN_B_WORKFLOW_MODEL_MD = MEMORY_DIR / "plan_b_workflow_model.md"
DEVOPS_ENVIRONMENT_MD = MEMORY_DIR / "devops-environment.md"

# SS4 relocation targets.
MEMORY_TEMPLATES_DIR = REPO_ROOT / "skills-src" / "memory-templates"
JAVA_ORCHESTRATION_TEMPLATE = MEMORY_TEMPLATES_DIR / "java-orchestration.md"
RUST_ORCHESTRATION_TEMPLATE = MEMORY_TEMPLATES_DIR / "rust-orchestration.md"
OPERATIONAL_COMMANDS_TEMPLATE = MEMORY_TEMPLATES_DIR / "operational-commands.md"

ARCHIVE_WAVE2 = REPO_ROOT / "archive" / "wave2"

# D5's exact end-state global memory set (PRD-model-b-rationalization.md
# SD5): cross-project LANGUAGE references only.
D5_GLOBAL_MEMORY_FILES = frozenset(
    {
        "convex-client-server.md",
        "java-coding-standards.md",
        "java-modern-syntax.md",
        "java-testing-practices.md",
        "maven-best-practices.md",
        "quarkus-patterns.md",
    }
)

# The 5 standard chezmoi-diff scope paths (same convention CR-MDB-002/003/
# 004/005 used -- see tests/test_git_chezmoi_skills.py).
CHEZMOI_SCOPE_PATHS = (
    CLAUDE_DIR / "AGENTS.md",
    CLAUDE_DIR / "CLAUDE.md",
    CLAUDE_DIR / "agents",
    CLAUDE_DIR / "memory",
    CLAUDE_DIR / "skills",
)

# SS5's AC names this exact grep invocation verbatim.
STALE_REF_PATTERN = (
    r"QUICK_REFERENCE\|stack-detection\|plan_b_workflow\|devops-environment"
    r"\|memory/java-orchestration\|memory/rust-orchestration"
    r"\|memory/operational-commands"
)


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


class MemoryModelS2Test(unittest.TestCase):
    """SS2 -- merge the UNIQUE content of memory/devops-environment.md into
    memory/java-testing-practices.md (TestContainers, DevServices, @Nested
    continuous-testing gotcha, container-runtime/Podman, CI considerations),
    and wire the orphaned java-modern-syntax.md into the AGENTS.md Java
    stack-reference row."""

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

    def test_s2_agents_md_java_row_contains_java_modern_syntax(self):
        self.assertTrue(AGENTS_MD.is_file(), f"{AGENTS_MD} must exist")
        content = _read(AGENTS_MD)
        java_rows = [
            ln for ln in content.splitlines()
            if "Java" in ln and "memory" in ln.lower()
        ]
        # POSITIVE -- the AGENTS.md Java stack-reference row must cite
        # java-modern-syntax.md (currently orphaned since the audit).
        self.assertIn(
            "java-modern-syntax.md", content,
            f"{AGENTS_MD} Java stack row must contain 'java-modern-syntax.md', "
            f"Java-related rows found: {java_rows}",
        )


class MemoryModelS3Test(unittest.TestCase):
    """SS3 -- delete QUICK_REFERENCE.md (superseded by the trigger table),
    stack-detection.md (superseded by the crucible skill),
    plan_b_workflow_model.md (broken mis-paste; canonical = model-b skill),
    devops-environment.md (after SS2 merge) -- via chezmoi discipline,
    archived to <repo>/archive/wave2/."""

    def test_s3_deletion_targets_removed_with_content_preserving_archive(self):
        deletion_targets = (
            QUICK_REFERENCE_MD,
            STACK_DETECTION_MD,
            PLAN_B_WORKFLOW_MODEL_MD,
            DEVOPS_ENVIRONMENT_MD,
        )
        still_present = [str(p) for p in deletion_targets if p.exists()]
        # NEGATIVE -- none of the four deletion targets may still exist live.
        self.assertEqual(
            still_present, [],
            f"expected zero SS3 deletion targets still present, found: {still_present}",
        )

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
    ~/.claude/skills/model-b/references/sandesh.md, then delete the three
    from ~/.claude/memory/. Global memory end state: EXACTLY the 6 D5
    files."""

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

    def test_s4_global_memory_has_exactly_the_six_d5_files(self):
        self.assertTrue(MEMORY_DIR.is_dir(), f"{MEMORY_DIR} must exist")
        live_files = frozenset(
            entry.name
            for entry in MEMORY_DIR.iterdir()
            if entry.is_file() and not entry.name.startswith(".")
        )
        # EXACT set equality -- not just a count of 6, the SIX NAMED D5
        # files specifically.
        self.assertEqual(
            live_files, D5_GLOBAL_MEMORY_FILES,
            f"{MEMORY_DIR} must contain exactly the 6 D5 files "
            f"{sorted(D5_GLOBAL_MEMORY_FILES)}, found {sorted(live_files)} "
            f"(extra: {sorted(live_files - D5_GLOBAL_MEMORY_FILES)}, "
            f"missing: {sorted(D5_GLOBAL_MEMORY_FILES - live_files)})",
        )
        # Redundant explicit count check per the AC's literal
        # `ls ~/.claude/memory/ | wc -l` == 6 wording.
        self.assertEqual(len(live_files), 6, f"found {len(live_files)} files: {sorted(live_files)}")

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


class MemoryModelS5Test(unittest.TestCase):
    """SS5 -- repoint consumers: AGENTS.md Java row adds java-modern-syntax.md
    and drops java-orchestration.md; Rust-stack row and Operational-commands
    row replaced by one scaffold-instantiated row; the 4 quarkus agent defs'
    java-orchestration.md citations repointed."""

    def test_s5_grep_gate_zero_stale_references_across_consumers(self):
        # EXACT -- the AC names this exact grep invocation verbatim.
        result = subprocess.run(
            [
                "grep", "-rl", STALE_REF_PATTERN,
                str(MEMORY_DIR),
                str(CLAUDE_DIR / "skills"),
                str(AGENTS_MD),
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
            "grep gate must return 0 files referencing QUICK_REFERENCE, "
            "stack-detection, plan_b_workflow, devops-environment, "
            f"memory/java-orchestration, memory/rust-orchestration or "
            f"memory/operational-commands, found: {matched_files}",
        )

    def test_s5_agents_md_scaffold_instantiated_row_and_no_rust_orchestration_ref(self):
        self.assertTrue(AGENTS_MD.is_file(), f"{AGENTS_MD} must exist")
        content = _read(AGENTS_MD)

        # POSITIVE -- the AC's exact required term for the merged
        # Rust-stack + Operational-commands replacement row.
        self.assertIn(
            "scaffold-instantiated", content,
            f"{AGENTS_MD} must contain 'scaffold-instantiated' (the project-level row)",
        )

        # NEGATIVE/bound -- exactly zero occurrences of the stale
        # memory/rust-orchestration.md reference, not "fewer".
        stale_count = content.count("memory/rust-orchestration.md")
        self.assertEqual(
            stale_count, 0,
            f"{AGENTS_MD} must contain zero occurrences of "
            f"'memory/rust-orchestration.md', found {stale_count}",
        )


if __name__ == "__main__":
    unittest.main()
