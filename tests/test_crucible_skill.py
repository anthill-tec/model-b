"""RED-phase tests for CR-MDB-003 (crucible skill rewrite: real surfaces,
absorb report skills + agent-protocol).

These tests assert the acceptance criteria of CR-MDB-003 SS2-SS5 against the
LIVE ~/.claude tree on this machine. They are intentionally written before
the GREEN-phase work (SKILL.md rewrite, references/ population, the 10-dir +
1-file deletion/archival, consumer repointing) lands, so most of them are
expected to FAIL against the current (pre-CR-MDB-003) state of ~/.claude.
The suite overall must be RED, not necessarily every single test (some
content greps may vacuously fail because the terms are simply absent yet --
that is still a correct FAIL, not a vacuous pass).

Stdlib only (unittest + subprocess + pathlib + os). No SUT import: this CR's
deliverable is markdown/skill content, not Python modules.
"""

import os
import subprocess
import unittest
from pathlib import Path

CLAUDE_DIR = Path.home() / ".claude"
REPO_ROOT = Path(__file__).resolve().parent.parent

SKILL_DIR = CLAUDE_DIR / "skills" / "crucible"
SKILL_MD = SKILL_DIR / "SKILL.md"
REFERENCES_DIR = SKILL_DIR / "references"
ARCHIVE_WAVE2 = REPO_ROOT / "archive" / "wave2"

# The 10 skill dirs §S4 requires gone from ~/.claude/skills/ (5 report skills
# + agent-protocol + the 4 TDD-phase skills), each keyed to a distinctive
# anchor phrase drawn from its CURRENT SKILL.md body -- proves an archived
# copy is a real content-preserving move, not an empty stub.
DELETION_TARGET_SKILLS = {
    "crucible-report-rust": "clients/rust-crucible.py",
    "crucible-report-java": "clients/mvn-crucible.py",
    "crucible-report-bun": "clients/bun-crucible.py",
    "crucible-report-python": "Python parallel of",
    "crucible-report-vscode": "no `*-crucible.py` CLI client",
    "agent-protocol": "liveness through run ingests",
    "bun-red-testing": "ingest RED",
    "bun-green-testing": "ingest GREEN",
    "bun-regression-testing": "ingest with coverage",
    "quarkus-regression-testing": "ingest with JaCoCo coverage",
}

MEMORY_DELETION_TARGET = "crucible-ingest.md"
MEMORY_DELETION_ANCHOR = "NEVER hand-roll curl/python"

# The 5 standard chezmoi-diff scope paths (same convention CR-MDB-002 used).
CHEZMOI_SCOPE_PATHS = (
    CLAUDE_DIR / "AGENTS.md",
    CLAUDE_DIR / "CLAUDE.md",
    CLAUDE_DIR / "agents",
    CLAUDE_DIR / "memory",
    CLAUDE_DIR / "skills",
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


class CrucibleSkillS2Test(unittest.TestCase):
    """SS2 -- SKILL.md rewrite (real lifecycle + true per-stack surfaces)."""

    def test_s2_heartbeat_near_register_and_zero_deprecated_endpoint_terms(self):
        self.assertTrue(SKILL_MD.is_file(), f"{SKILL_MD} must exist")
        content = _read(SKILL_MD)
        lines = content.splitlines()

        # POSITIVE -- "heartbeat" must appear within 3 lines of "register"
        # somewhere in the file (heartbeat IS the register verb, not a
        # separate endpoint).
        register_line_idxs = [i for i, ln in enumerate(lines) if "register" in ln]
        heartbeat_line_idxs = [i for i, ln in enumerate(lines) if "heartbeat" in ln]
        found_near = any(
            abs(r - h) <= 3 for r in register_line_idxs for h in heartbeat_line_idxs
        )
        self.assertTrue(
            found_near,
            "SKILL.md must contain 'heartbeat' within 3 lines of 'register' "
            f"(register lines: {register_line_idxs}, heartbeat lines: {heartbeat_line_idxs})",
        )

        # NEGATIVE/EXACT bounds -- the phantom endpoint + shell-script must
        # be entirely gone.
        heartbeat_endpoint_count = content.count("/agents/heartbeat")
        heartbeat_sh_count = content.count("heartbeat.sh")
        self.assertEqual(
            heartbeat_endpoint_count, 0,
            f"expected zero '/agents/heartbeat' occurrences, found {heartbeat_endpoint_count}",
        )
        self.assertEqual(
            heartbeat_sh_count, 0,
            f"expected zero 'heartbeat.sh' occurrences, found {heartbeat_sh_count}",
        )

    def test_s2_contains_required_identity_and_true_per_stack_verbs(self):
        self.assertTrue(SKILL_MD.is_file(), f"{SKILL_MD} must exist")
        content = _read(SKILL_MD)

        required_terms = [
            "<agent-type>-<project>",
            "--phase",
            "regression-ingest",  # rust
            "unit --test",  # java
            "plan-file",  # bun
            "--tests",  # python
        ]
        missing = [term for term in required_terms if term not in content]
        # POSITIVE -- every required identity/verb term must appear.
        self.assertEqual(
            missing, [],
            f"SKILL.md missing required identity/per-stack-verb terms: {missing}",
        )

        # POSITIVE -- the incoming-contract markers must be present.
        has_incoming_cycle_marker = ("REFUSED" in content) or ("400" in content)
        self.assertTrue(
            has_incoming_cycle_marker,
            "SKILL.md must contain 'REFUSED' or '400' (incoming unknown-cycleId contract)",
        )
        self.assertIn(
            "CR-CRU-030", content,
            "SKILL.md must contain 'CR-CRU-030' (envelope contract marked incoming)",
        )

    def test_s2_zero_plan_b_and_same_across_stacks_mentions(self):
        self.assertTrue(SKILL_MD.is_file(), f"{SKILL_MD} must exist")
        content = _read(SKILL_MD)
        # POSITIVE sanity -- the file must actually have content to check.
        self.assertGreater(len(content.strip()), 0, "SKILL.md must not be empty")

        plan_b_count = content.count("Plan B")
        same_across_stacks_count = content.count("same across stacks")
        # EXACT bounds on both forbidden (stale false-universality) terms.
        self.assertEqual(plan_b_count, 0, f"expected zero 'Plan B' mentions, found {plan_b_count}")
        self.assertEqual(
            same_across_stacks_count, 0,
            f"expected zero 'same across stacks' mentions, found {same_across_stacks_count}",
        )


class CrucibleSkillS3Test(unittest.TestCase):
    """SS3 -- references/ per stack (absorbs each crucible-report-* skill's
    still-true content, corrected against the drift audit)."""

    def test_s3_all_five_reference_files_exist_with_stack_specific_content(self):
        stacks = ("rust", "java", "bun", "python", "vscode")
        missing_files = []
        for stack in stacks:
            path = REFERENCES_DIR / f"{stack}.md"
            if not path.is_file():
                missing_files.append(str(path))
        # POSITIVE -- all five reference files must exist.
        self.assertEqual(
            missing_files, [],
            f"expected all five references/{{rust,java,bun,python,vscode}}.md to exist, "
            f"missing: {missing_files}",
        )

        rust_path = REFERENCES_DIR / "rust.md"
        self.assertTrue(rust_path.is_file(), f"{rust_path} must exist")
        rust_content = _read(rust_path)
        self.assertIn(
            "workspace-regression", rust_content,
            "references/rust.md must contain 'workspace-regression'",
        )
        self.assertGreater(len(rust_content.strip()), 0, "references/rust.md must not be empty")

        bun_path = REFERENCES_DIR / "bun.md"
        self.assertTrue(bun_path.is_file(), f"{bun_path} must exist")
        bun_content = _read(bun_path)
        self.assertIn(
            "cycle-activate", bun_content,
            "references/bun.md must contain 'cycle-activate'",
        )
        self.assertGreater(len(bun_content.strip()), 0, "references/bun.md must not be empty")

        vscode_path = REFERENCES_DIR / "vscode.md"
        self.assertTrue(vscode_path.is_file(), f"{vscode_path} must exist")
        vscode_content = _read(vscode_path)
        no_client_variants = ("no client", "no `*-crucible.py`", "No CLI client", "no CLI client")
        has_no_client_marker = any(v in vscode_content for v in no_client_variants)
        self.assertTrue(
            has_no_client_marker,
            f"references/vscode.md must contain a 'no client' (or equivalent) marker, "
            f"tried variants {no_client_variants}",
        )
        self.assertIn(
            "interim", vscode_content,
            "references/vscode.md must contain 'interim'",
        )
        self.assertGreater(len(vscode_content.strip()), 0, "references/vscode.md must not be empty")


class CrucibleSkillS4Test(unittest.TestCase):
    """SS4 -- deletions (chezmoi discipline): the 10 skill dirs + the one
    memory stub are archived into the repo then physically removed."""

    def test_s4_ten_skill_dirs_and_memory_stub_removed_with_archived_content(self):
        still_present = []
        not_archived = []
        for name, anchor in DELETION_TARGET_SKILLS.items():
            live_dir = CLAUDE_DIR / "skills" / name
            if live_dir.exists():
                still_present.append(str(live_dir))
            if not _archive_has_content_move(name, anchor):
                not_archived.append(name)

        live_memory = CLAUDE_DIR / "memory" / MEMORY_DELETION_TARGET
        if live_memory.exists():
            still_present.append(str(live_memory))
        if not _archive_has_content_move(MEMORY_DELETION_TARGET, MEMORY_DELETION_ANCHOR):
            not_archived.append(MEMORY_DELETION_TARGET)

        # NEGATIVE -- none of the 10 skill dirs + memory/crucible-ingest.md
        # may still exist in the live ~/.claude tree.
        self.assertEqual(
            still_present, [],
            f"expected zero deletion-target paths still present, found: {still_present}",
        )
        # POSITIVE -- every deleted item must have a content-preserving
        # archived copy under <repo>/archive/wave2/.
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


class CrucibleSkillS5Test(unittest.TestCase):
    """SS5 -- repoint consumers away from the retired skills/paths."""

    def test_s5_grep_gate_zero_stale_references_across_consumers(self):
        pattern = (
            r"crucible-report\|agent-protocol\|crucible-ingest\|"
            r"bun-red-testing\|bun-green-testing\|bun-regression-testing\|"
            r"quarkus-regression-testing"
        )
        result = subprocess.run(
            [
                "grep", "-rl", pattern,
                str(CLAUDE_DIR / "memory"),
                str(CLAUDE_DIR / "skills"),
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
            f"grep gate must return 0 files referencing crucible-report/agent-protocol/"
            f"crucible-ingest/bun-*-testing/quarkus-regression-testing, found: {matched_files}",
        )


if __name__ == "__main__":
    unittest.main()
