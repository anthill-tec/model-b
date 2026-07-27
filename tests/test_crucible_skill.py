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

SKILL_DIR = REPO_ROOT / "skills-src" / "crucible"
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

        # NEGATIVE/EXACT bound -- superseded by CR-MDB-016 AC8 (PRD §4.2 as
        # amended): the phantom endpoint is no longer required to be absent
        # outright -- every '/agents/heartbeat' hit must be the live
        # '/api/v2/agents/heartbeat' form (mirrors the composed-pattern style
        # of tests/test_skills_handover.py's AC8 tests).
        phantom_endpoint = "/agents" + "/heartbeat"
        live_endpoint = "/api/v2" + phantom_endpoint
        non_v2_hits = [
            line_no for line_no, ln in enumerate(lines, start=1)
            if phantom_endpoint in ln and live_endpoint not in ln
        ]
        self.assertEqual(
            non_v2_hits, [],
            f"expected every '{phantom_endpoint}' occurrence in SKILL.md to "
            f"be the '{live_endpoint}' form, found non-v2 hits at lines: {non_v2_hits}",
        )
        # NEGATIVE/EXACT bound -- the un-adopted shell helper must be
        # entirely gone.
        heartbeat_sh_count = content.count("heartbeat.sh")
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

        # NEGATIVE -- the final contract has NO refusal rule; the CR-024
        # unknown-cycleId REFUSED/(400) text must be gone per §S2(b).
        self.assertNotIn(
            "REFUSED", content,
            "SKILL.md must not contain 'REFUSED' -- the CR-024 refusal rule is gone",
        )
        self.assertNotIn(
            "(400)", content,
            "SKILL.md must not reference the '(400)' refusal status",
        )
        # POSITIVE -- the CR-CRU-030 client-contract token must still be
        # present, now in DELIVERED context (CR-CRU-030 shipped).
        self.assertIn(
            "CR-CRU-030", content,
            "SKILL.md must contain 'CR-CRU-030' (delivered client contract)",
        )
        # NEGATIVE -- the envelope section must no longer mark the contract
        # as "INCOMING" -- CR-CRU-030 shipped.
        self.assertNotIn(
            "INCOMING", content,
            "SKILL.md must not contain 'INCOMING' -- CR-CRU-030 shipped, envelope is DELIVERED",
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


class CrucibleSkillCRMDB011Test(unittest.TestCase):
    """CR-MDB-011 SS1 -- AC gate tests for the FINAL Crucible client contract
    (post CR-CRU-030/036): server-resolved cycle attach, no-active-cycle
    withhold semantics, and routing to Crucible-bundled per-stack skill docs.
    """

    def test_ac1_zero_workflow_cycle_id_in_skill_md_and_all_references(self):
        self.assertTrue(SKILL_MD.is_file(), f"{SKILL_MD} must exist")
        skill_content = _read(SKILL_MD)
        skill_count = skill_content.count("WORKFLOW_CYCLE_ID")
        # EXACT bound -- zero occurrences in SKILL.md.
        self.assertEqual(
            skill_count, 0,
            f"expected zero 'WORKFLOW_CYCLE_ID' occurrences in {SKILL_MD}, found {skill_count}",
        )

        self.assertTrue(REFERENCES_DIR.is_dir(), f"{REFERENCES_DIR} must exist")
        offending = {}
        for ref_path in sorted(REFERENCES_DIR.glob("*.md")):
            ref_content = _read(ref_path)
            count = ref_content.count("WORKFLOW_CYCLE_ID")
            if count:
                offending[ref_path.name] = count
        # EXACT bound -- zero occurrences across every references/*.md.
        self.assertEqual(
            offending, {},
            f"expected zero 'WORKFLOW_CYCLE_ID' occurrences across references/*.md, "
            f"found: {offending}",
        )

    def test_ac2_no_active_cycle_withhold_and_cycle_activate_present(self):
        self.assertTrue(SKILL_MD.is_file(), f"{SKILL_MD} must exist")
        content = _read(SKILL_MD)

        # POSITIVE -- server-driven no-active-cycle warn/withhold semantics.
        self.assertIn(
            "no-active-cycle", content,
            "SKILL.md must contain 'no-active-cycle'",
        )
        self.assertIn(
            "withhold", content.lower(),
            "SKILL.md must contain 'withhold' (case-insensitive)",
        )
        # POSITIVE -- cycle-activate named as the orchestrator's only cycle
        # input.
        self.assertIn(
            "cycle-activate", content,
            "SKILL.md must contain 'cycle-activate' (orchestrator's only cycle input)",
        )

    def test_ac3_bundled_doc_route_and_arduino_client_row_present(self):
        """Superseded by CR-MDB-016 AC3: the literal
        'clients/skills/crucible-report-' route requirement is gone --
        AC3 instead requires zero references to 'crucible:clients/skills/'
        as a live authority (provenance doc excepted). The arduino
        per-stack row requirement (full surface) still applies."""
        self.assertTrue(SKILL_MD.is_file(), f"{SKILL_MD} must exist")
        content = _read(SKILL_MD)

        # POSITIVE -- the per-stack table gains an arduino row (full surface).
        self.assertIn(
            "arduino-crucible.py", content,
            "SKILL.md must contain an 'arduino-crucible.py' per-stack row",
        )

    def test_ac4_each_reference_routes_to_its_crucible_report_bundle(self):
        stacks = ("rust", "java", "bun", "python", "vscode")
        missing_route = []
        for stack in stacks:
            path = REFERENCES_DIR / f"{stack}.md"
            self.assertTrue(path.is_file(), f"{path} must exist")
            content = _read(path)
            if "crucible-report-" not in content:
                missing_route.append(stack)
        # POSITIVE -- every reference doc routes to its bundled skill.
        self.assertEqual(
            missing_route, [],
            f"expected every references/{{stack}}.md to route to its "
            f"'crucible-report-<stack>' bundle, missing route in: {missing_route}",
        )

    def test_ac6_all_five_reference_files_still_exist(self):
        stacks = ("rust", "java", "bun", "python", "vscode")
        missing_files = [
            str(REFERENCES_DIR / f"{stack}.md")
            for stack in stacks
            if not (REFERENCES_DIR / f"{stack}.md").is_file()
        ]
        # POSITIVE -- consumer constraint: 22 agents + 2 refactorer skills
        # reference these exact paths, so they must keep resolving.
        self.assertEqual(
            missing_files, [],
            f"expected all five references/{{rust,java,bun,python,vscode}}.md paths "
            f"to still exist (consumer constraint), missing: {missing_files}",
        )

    def test_ac7_repo_agents_md_no_longer_claims_workflow_cycle_id_injection(self):
        agents_md = REPO_ROOT / "AGENTS.md"
        self.assertTrue(agents_md.is_file(), f"{agents_md} must exist")
        content = _read(agents_md)
        count = content.count("WORKFLOW_CYCLE_ID")
        # EXACT bound -- the wrapper sentence must no longer claim
        # WORKFLOW_CYCLE_ID injection.
        self.assertEqual(
            count, 0,
            f"expected zero 'WORKFLOW_CYCLE_ID' occurrences in {agents_md}, found {count}",
        )

    def test_ac8_zero_claude_scripts_client_path_mentions_in_authored_skill(self):
        self.assertTrue(SKILL_MD.is_file(), f"{SKILL_MD} must exist")
        offending = {}

        skill_content = _read(SKILL_MD)
        skill_count = skill_content.count(".claude/scripts")
        if skill_count:
            offending[str(SKILL_MD)] = skill_count

        self.assertTrue(REFERENCES_DIR.is_dir(), f"{REFERENCES_DIR} must exist")
        for ref_path in sorted(REFERENCES_DIR.glob("*.md")):
            ref_content = _read(ref_path)
            count = ref_content.count(".claude/scripts")
            if count:
                offending[str(ref_path)] = count

        # EXACT bound -- the authored copy must route every client-path
        # mention to the Crucible repo's own clients/ directory, never the
        # deployed ~/.claude/scripts/ location (deployment is the
        # installer's job, CR-MDB-014).
        self.assertEqual(
            offending, {},
            f"expected zero '.claude/scripts' occurrences across skills-src/crucible/ "
            f"(SKILL.md + references/*.md), found: {offending}",
        )


if __name__ == "__main__":
    unittest.main()
