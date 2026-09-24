"""RED-phase tests for CR-MDB-003 (crucible skill rewrite: real surfaces,
absorb report skills + agent-protocol).

SS4/SS5 were originally written against the LIVE ~/.claude tree. CR-MDB-032
SS2 retargeted them to the repo (the 2026-07-22 repo-local authoring rule):
the archive/wave2/ copies, and the consumer grep gate over skills-src/, the
rendered agents under generator/agents/ and the repo AGENTS.md. The live-home
halves (deletion targets absent from ~/.claude, crucible-report-* deployed as
symlinks) were deleted -- the installer's sha256 manifest proves deployed
state.

Stdlib only (unittest + subprocess + pathlib + os). No SUT import: this CR's
deliverable is markdown/skill content, not Python modules.
"""

import re
import subprocess
import unittest
from pathlib import Path

from tests._helpers import archive_has_content_move as _archive_has_content_move
from tests._helpers import read_text_lenient as _read

REPO_ROOT = Path(__file__).resolve().parent.parent

SKILL_DIR = REPO_ROOT / "skills-src" / "crucible"
SKILL_MD = SKILL_DIR / "SKILL.md"
REFERENCES_DIR = SKILL_DIR / "references"
ARCHIVE_WAVE2 = REPO_ROOT / "archive" / "wave2"

# ------------------------------------------------------------------------
# CR-MDB-017 §S1 -- the `ac7` re-pin.
#
# The original assertion was a bare whole-file `AGENTS.md.count(...) == 0`
# over the retired per-run cycle-id environment variable.  That made
# DOCUMENTING the prohibition indistinguishable from VIOLATING it: the gate
# forbade naming what it forbids, so AGENTS.md could not describe its own
# grep-gate family or its own baseline failure without tripping it, and the
# suite carried the result as a permanent recorded failure.
#
# Re-pointed at the CLAIM the gate exists to prevent: no SENTENCE may say the
# per-project context wrapper injects that variable.  Naming the variable in
# order to prohibit it is legal; asserting that something sets it is not.
# The product-surface guarantee -- zero occurrences anywhere the variable
# could actually be injected -- is asserted separately and positively below,
# so nothing the old bare count protected is lost.
CYCLE_ID_ENV_VAR = "WORKFLOW_CYCLE_ID"

# Verbs that turn a mention into an injection CLAIM.
INJECTION_VERB_RE = re.compile(
    r"\b(?:inject(?:s|ed|ing)?|pin(?:s|ned|ning)?|set(?:s|ting)?|export(?:s|ed|ing)?"
    r"|pass(?:es|ed|ing)?|provid(?:e|es|ed|ing)|suppl(?:y|ies|ied)"
    r"|plumb(?:s|ed|ing)?|populat(?:e|es|ed|ing))\b",
    re.IGNORECASE,
)

# Sentence-ish split: markdown lines, then terminal punctuation.  Narrower
# units mean a verb elsewhere in a long bullet cannot manufacture a hit.
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.;:!?])\s+")

# Where the variable could ACTUALLY be injected: the product surfaces.
# AGENTS.md, docs/, audits/ and archive/ DESCRIBE the gate rather than violate
# it -- a sweep that edits the gate's own definition defeats it.
CYCLE_ID_PRODUCT_DIRS = ("modelb_axi", "scripts", "generator", "skills-src")


def _sentences(text):
    """Every sentence-ish fragment of `text` as (lineno, fragment)."""
    out = []
    for lineno, line in enumerate(text.splitlines(), 1):
        for fragment in _SENTENCE_SPLIT_RE.split(line):
            fragment = fragment.strip()
            if fragment:
                out.append((lineno, fragment))
    return out


def _injection_claims(text, token=CYCLE_ID_ENV_VAR):
    """Sentences that both NAME `token` and assert something injects it."""
    return [
        (lineno, fragment)
        for lineno, fragment in _sentences(text)
        if token in fragment and INJECTION_VERB_RE.search(fragment)
    ]


# The 10 skill dirs §S4 requires gone from ~/.claude/skills/ (5 report skills
# + agent-protocol + the 4 TDD-phase skills), each keyed to a distinctive
# anchor phrase drawn from its CURRENT SKILL.md body -- proves an archived
# copy is a real content-preserving move, not an empty stub.
# CR-MDB-016 (handover rebirth) legitimately re-ships crucible-report-{rust,
# java,bun,python} (+ arduino) as installer-owned symlinks into
# ~/.claude/skills -- removed from the deletion-target list below.
# agent-protocol remains banned (CR-MDB-016 Option B) and stays a target.
# CR-MDB-024 \u00a7S3 (2026-09-22 VS Code ruling): the VS Code crucible-report
# bundle is no longer a legitimate handover bundle -- it is retired outright (an IDE is
# not a stack), so it drops out of the handover set
# and back onto DELETION_TARGET_SKILLS' effective footprint via the
# dedicated VS Code retirement gates in
# tests/test_ide_overlay_retirement.py (this file's DELETION_TARGET_SKILLS
# dict stays scoped to CR-MDB-016's own original wave-2 targets, never
# grown for a later CR's retirement).
DELETION_TARGET_SKILLS = {
    "agent-protocol": "liveness through run ingests",
    "bun-red-testing": "ingest RED",
    "bun-green-testing": "ingest GREEN",
    "bun-regression-testing": "ingest with coverage",
    "quarkus-regression-testing": "ingest with JaCoCo coverage",
}

MEMORY_DELETION_TARGET = "crucible-ingest.md"
MEMORY_DELETION_ANCHOR = "NEVER hand-roll curl/python"


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
            # CR-MDB-017 §S1 (sanctioned amendment): Crucible retired `--phase`
            # in their 0.1.0 clean break, with no alias, so the pinned term was
            # superseded upstream. Inverted to the released register surface --
            # `--role` (argparse-required, case-exact enumeration) plus the
            # `--cycle` binding the server demands of the four TDD roles.
            "--role",
            "--cycle",
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
    still-true content, corrected against the drift audit).

    CR-MDB-024 \u00a7S3 AMENDMENT (this cycle, C2 RED, 2026-09-22 VS Code ruling):
    the VS Code reference router (its ``references/`` entry) and its row in
    this SKILL.md are retired along with the rest of the VS Code substrate
    -- an IDE is not a stack, so it never belonged among the per-STACK
    reference routers. The method below narrows from five routers to four;
    the dedicated absence gate lives in
    ``tests/test_ide_overlay_retirement.py``."""

    def test_s3_all_four_reference_files_exist_with_stack_specific_content(self):
        stacks = ("rust", "java", "bun", "python")
        missing_files = []
        for stack in stacks:
            path = REFERENCES_DIR / f"{stack}.md"
            if not path.is_file():
                missing_files.append(str(path))
        # POSITIVE -- all four reference files must exist.
        self.assertEqual(
            missing_files, [],
            f"expected all four references/{{rust,java,bun,python}}.md to exist, "
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


class CrucibleSkillS4Test(unittest.TestCase):
    """SS4 -- deletions: the retired skill dirs + the one memory stub have
    content-preserving archived copies in the repo."""

    def test_s4_ten_skill_dirs_and_memory_stub_removed_with_archived_content(self):
        """CR-MDB-016 (handover rebirth, supersession class): the wave-2
        deletion targets never resurrect EXCEPT crucible-report-{rust,java,
        bun,python,arduino}, which CR-MDB-016 legitimately re-ships as
        real deployed handover bundles (installer-owned symlinks). Those are
        excluded from DELETION_TARGET_SKILLS above; agent-protocol remains
        banned per CR-MDB-016 Option B and every other original target still
        applies unchanged. CR-MDB-024 \u00a7S3 (this cycle, 2026-09-22 VS Code
        ruling) drops the VS Code crucible-report bundle out of that legitimate-reappear
        set entirely -- its dedicated retirement gate lives in
        tests/test_ide_overlay_retirement.py, not here. CR-MDB-032 SS2 dropped
        the live ~/.claude halves (absence, symlink shape)."""
        not_archived = []
        for name, anchor in DELETION_TARGET_SKILLS.items():
            if not _archive_has_content_move(name, anchor):
                not_archived.append(name)
        if not _archive_has_content_move(MEMORY_DELETION_TARGET, MEMORY_DELETION_ANCHOR):
            not_archived.append(MEMORY_DELETION_TARGET)

        # POSITIVE -- every deleted item must have a content-preserving
        # archived copy under <repo>/archive/wave2/.
        self.assertEqual(
            not_archived, [],
            f"expected an archived copy retaining its anchor under {ARCHIVE_WAVE2} "
            f"for every deletion target, missing/anchor-less for: {not_archived}",
        )


class CrucibleSkillS5Test(unittest.TestCase):
    """SS5 -- repoint consumers away from the retired skills/paths."""

    #: The provenance record names the deliberately NOT-imported
    #: agent-protocol bundle (Option B) -- a record, not a consumer.
    GREP_GATE_EXEMPT = ("CRUCIBLE-HANDOVER.md",)

    def test_s5_grep_gate_zero_stale_references_across_consumers(self):
        """The consumers (skill sources, rendered agents, AGENTS.md) name no
        retired skill or memory stub. `crucible-report` left the pattern with
        CR-MDB-016, which re-ships those bundles as live handover bundles
        (the supersession SS4's DELETION_TARGET_SKILLS already records)."""
        pattern = r"\|".join(
            [*DELETION_TARGET_SKILLS, MEMORY_DELETION_TARGET.removesuffix(".md")]
        )
        result = subprocess.run(
            [
                "grep", "-rl", pattern,
                str(REPO_ROOT / "skills-src"),
                str(REPO_ROOT / "AGENTS.md"),
                str(REPO_ROOT / "generator" / "agents"),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        matched_files = [
            ln for ln in result.stdout.splitlines()
            if ln.strip() and Path(ln).name not in self.GREP_GATE_EXEMPT
        ]
        # EXACT bound -- zero consumer files.
        self.assertEqual(
            matched_files, [],
            f"grep gate must return 0 files referencing agent-protocol/"
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
        stacks = ("rust", "java", "bun", "python")
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

    def test_ac6_all_four_reference_files_still_exist(self):
        """CR-MDB-024 \u00a7S3 AMENDMENT (this cycle, C2 RED, 2026-09-22 VS Code
        ruling): narrowed from five stacks to four -- the VS Code reference
        router is retired outright along with the rest of that substrate
        (an IDE is not a stack); its absence is gated separately in
        tests/test_ide_overlay_retirement.py."""
        stacks = ("rust", "java", "bun", "python")
        missing_files = [
            str(REFERENCES_DIR / f"{stack}.md")
            for stack in stacks
            if not (REFERENCES_DIR / f"{stack}.md").is_file()
        ]
        # POSITIVE -- consumer constraint: the surviving agents + refactorer
        # skills reference these exact paths, so they must keep resolving.
        self.assertEqual(
            missing_files, [],
            f"expected all four references/{{rust,java,bun,python}}.md paths "
            f"to still exist (consumer constraint), missing: {missing_files}",
        )

    def test_ac7_repo_agents_md_no_longer_claims_workflow_cycle_id_injection(self):
        """CR-MDB-017 §S1 re-pin: the CLAIM, not a bare substring count.

        The assertion used to be `AGENTS.md.count(CYCLE_ID_ENV_VAR) == 0`,
        which forbade naming what it forbids -- both occurrences it counted
        were META (the grep-gate-family description and the baseline sentence
        naming this very failure) while the guarantee itself held everywhere
        the variable could be injected.  It now measures the claim: no
        sentence may say the per-project context wrapper injects it.
        """
        agents_md = REPO_ROOT / "AGENTS.md"
        self.assertTrue(agents_md.is_file(), f"{agents_md} must exist")
        claims = _injection_claims(_read(agents_md))
        # EXACT bound -- zero sentences asserting injection.  Mentioning the
        # variable in order to prohibit it stays legal.
        self.assertEqual(
            claims, [],
            f"expected no sentence in {agents_md} to claim the wrapper injects "
            f"{CYCLE_ID_ENV_VAR}; offending sentences: "
            + "; ".join(f"{lineno}: {frag}" for lineno, frag in claims),
        )

    def test_ac7_injection_claim_detector_bites(self):
        """The re-pinned gate is PROVEN to bite, so the green above is not a
        regex that matches nothing."""
        violating = (
            f"# Per-project context wrapper (pins CRUCIBLE_PROJECT_KEY and "
            f"{CYCLE_ID_ENV_VAR})."
        )
        self.assertNotEqual(
            _injection_claims(violating), [],
            "a sentence claiming the wrapper pins the retired cycle-id variable "
            f"must be reported; detector returned nothing for: {violating}",
        )
        permitted = (
            f"They assert grep-gates for retired terms (e.g. zero "
            f"`{CYCLE_ID_ENV_VAR}`)."
        )
        self.assertEqual(
            _injection_claims(permitted), [],
            "naming the variable in order to PROHIBIT it must stay legal, or the "
            f"gate forbids documenting itself again: {permitted}",
        )

    def test_ac7_product_surfaces_carry_zero_cycle_id_injection_points(self):
        """The guarantee the bare count was standing in for, asserted where it
        actually means something: the surfaces that could inject the variable.
        """
        offending = {}
        for dirname in CYCLE_ID_PRODUCT_DIRS:
            root = REPO_ROOT / dirname
            self.assertTrue(root.is_dir(), f"{root} must exist")
            for path in sorted(p for p in root.rglob("*") if p.is_file()):
                count = _read(path).count(CYCLE_ID_ENV_VAR)
                if count:
                    offending[str(path.relative_to(REPO_ROOT))] = count
        # EXACT bound -- zero occurrences across every product surface.
        self.assertEqual(
            offending, {},
            f"expected zero {CYCLE_ID_ENV_VAR!r} occurrences across "
            f"{list(CYCLE_ID_PRODUCT_DIRS)}; found: {offending}",
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
