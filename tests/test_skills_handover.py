"""RED-phase tests for CR-MDB-016 cycle C1 (Sec1-Sec3 -- Crucible skills
handover: import the 7 canonical skill bundles into skills-src/, rewrite
the crucible skill's routing/ownership/protocol-sync content, and cover
the handover in the wheel/_assets packaging).

Written before any of Sec1-Sec3's production content lands:
  - skills-src/ has no crucible-register/ or crucible-report-*/
    directories yet, and no skills-src/CRUCIBLE-HANDOVER.md -- the AC1
    existence/provenance/byte-identity assertions below fail cleanly.
  - skills-src/crucible/SKILL.md still routes stacks to
    `crucible:clients/skills/crucible-report-*` ("managed and updated by
    Crucible") and describes the phantom "there is NO separate heartbeat
    endpoint ... or helper script" claim -- the AC3 routing/protocol-sync
    assertions fail cleanly.
  - skills-src/crucible/references/arduino.md does not exist yet -- the
    AC7 router-parity assertion fails cleanly.

Byte-identity assertions compare against the origin repo copy
(~/Documents/data_projects/crucible/clients/skills/) WHEN that directory
exists on this machine; the origin freezes/retires after handover per the
CR context, so those specific assertions pytest-skip (not fail) when the
directory is absent -- keeping the gate durable post-freeze.

The heartbeat grep gate (AC8) is scoped to the LIVE artifact tree this
CR produces -- skills-src/ -- per the amended spec (AC8 names the
live-tree scope explicitly), mirroring the scoping CR-MDB-003 used for
the identical PRD Sec4.2 criterion. Historical CR/PRD/DN/audit documents
legitimately quote the retired phantom-heartbeat defect while describing
it and are out of gate scope per the cr-authoring convention.

Stdlib only: unittest + subprocess + re + hashlib + pathlib. No SUT
import: this CR's Sec1-Sec3 deliverable is markdown/skill content, not
Python modules.
"""

import hashlib
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS_SRC_DIR = REPO_ROOT / "skills-src"
HANDOVER_MD = SKILLS_SRC_DIR / "CRUCIBLE-HANDOVER.md"
CRUCIBLE_SKILL_DIR = SKILLS_SRC_DIR / "crucible"
CRUCIBLE_SKILL_MD = CRUCIBLE_SKILL_DIR / "SKILL.md"
REFERENCES_DIR = CRUCIBLE_SKILL_DIR / "references"

ORIGIN_SKILLS_DIR = (
    Path.home() / "Documents" / "data_projects" / "crucible" / "clients" / "skills"
)

# CR-MDB-024 \u00a7S3 (this cycle, C2 RED, 2026-09-22 VS Code ruling): the 6
# bundles Sec1 imports verbatim (agent-protocol deliberately excluded --
# Option B, absorbed into crucible instead; the VS Code crucible-report
# bundle deliberately excluded too -- retired outright, an IDE is not a
# stack).
IMPORTED_BUNDLE_NAMES = (
    "crucible-register",
    "crucible-report-arduino",
    "crucible-report-bun",
    "crucible-report-java",
    "crucible-report-python",
    "crucible-report-rust",
)

ALL_STACKS = ("rust", "java", "bun", "python", "arduino")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _split_frontmatter(content: str):
    """Split a skill markdown file into (frontmatter, body) on the '---'
    delimiters. Returns ("", content) if there is no well-formed
    frontmatter block."""
    lines = content.splitlines()
    if not lines or lines[0].strip() != "---":
        return "", content
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            frontmatter = "\n".join(lines[1:idx])
            body = "\n".join(lines[idx + 1:])
            return frontmatter, body
    return "", content


def _relative_file_hashes(root: Path) -> dict:
    hashes = {}
    for p in sorted(root.rglob("*")):
        if p.is_file():
            rel = str(p.relative_to(root))
            hashes[rel] = hashlib.sha256(p.read_bytes()).hexdigest()
    return hashes


def _missing_imported_bundles():
    return [
        name for name in IMPORTED_BUNDLE_NAMES
        if not (SKILLS_SRC_DIR / name / "SKILL.md").is_file()
    ]


class ImportedBundleExistenceAndMetadataTest(unittest.TestCase):
    """AC1 -- the 7 bundles exist under skills-src/ with Vercel-Skills
    `metadata:` frontmatter; NO skills-src/agent-protocol/ directory.

    CR-MDB-024 \u00a7S3 AMENDMENT (this cycle, C2 RED, 2026-09-22 VS Code ruling):
    narrowed from 7 to 6 -- the VS Code crucible-report bundle is retired
    outright (an IDE is not a stack).
    """

    def test_six_bundles_exist_with_skill_md_and_metadata_frontmatter_and_no_agent_protocol(self):
        missing = _missing_imported_bundles()
        no_metadata = []
        for name in IMPORTED_BUNDLE_NAMES:
            skill_md = SKILLS_SRC_DIR / name / "SKILL.md"
            if not skill_md.is_file():
                continue
            frontmatter, _ = _split_frontmatter(_read(skill_md))
            if "metadata:" not in frontmatter:
                no_metadata.append(name)
        # POSITIVE/EXACT -- every one of the 6 bundles has a SKILL.md.
        self.assertEqual(
            missing, [],
            f"expected skills-src/<bundle>/SKILL.md for all 6 imported "
            f"bundles {IMPORTED_BUNDLE_NAMES}; missing: {missing}",
        )
        # POSITIVE -- every bundle's SKILL.md carries Vercel-Skills
        # `metadata:` frontmatter (not just name/description).
        self.assertEqual(
            no_metadata, [],
            f"expected 'metadata:' key in the frontmatter of every "
            f"imported bundle's SKILL.md; missing metadata in: {no_metadata}",
        )
        # NEGATIVE -- Option B excludes agent-protocol entirely; it must
        # never appear as a standalone skills-src/ directory.
        agent_protocol_dir = SKILLS_SRC_DIR / "agent-protocol"
        self.assertFalse(
            agent_protocol_dir.exists(),
            f"{agent_protocol_dir} must NOT exist -- agent-protocol is "
            f"absorbed into crucible, never imported standalone (Option B)",
        )


class HandoverProvenanceDocTest(unittest.TestCase):
    """AC1 -- skills-src/CRUCIBLE-HANDOVER.md records origin repo, origin
    commit, date, refs #1336/#1337, and the agent-protocol Option-B
    exclusion."""

    def test_handover_doc_records_full_provenance(self):
        self.assertTrue(
            HANDOVER_MD.is_file(),
            f"{HANDOVER_MD} must exist recording the handover provenance",
        )
        content = _read(HANDOVER_MD)

        # POSITIVE -- origin repo + path identified.
        self.assertIn(
            "crucible", content.lower(),
            "CRUCIBLE-HANDOVER.md must name the origin repo (crucible)",
        )
        self.assertIn(
            "clients/skills", content,
            "CRUCIBLE-HANDOVER.md must cite the origin path (clients/skills)",
        )
        # POSITIVE -- an origin commit hash is recorded (7-40 hex chars).
        self.assertIsNotNone(
            re.search(r"\b[0-9a-f]{7,40}\b", content),
            "CRUCIBLE-HANDOVER.md must record an origin commit hash",
        )
        # POSITIVE -- an ISO-format date is recorded.
        self.assertIsNotNone(
            re.search(r"\b\d{4}-\d{2}-\d{2}\b", content),
            "CRUCIBLE-HANDOVER.md must record an ISO-format date",
        )
        # POSITIVE -- both ratification refs are cited.
        self.assertIn("#1336", content, "CRUCIBLE-HANDOVER.md must cite Sandesh #1336")
        self.assertIn("#1337", content, "CRUCIBLE-HANDOVER.md must cite Sandesh #1337")
        # POSITIVE -- the Option-B exclusion of agent-protocol is recorded.
        self.assertIn(
            "agent-protocol", content,
            "CRUCIBLE-HANDOVER.md must document the agent-protocol exclusion",
        )
        self.assertIn(
            "Option B", content,
            "CRUCIBLE-HANDOVER.md must cite the ratified 'Option B' exclusion decision",
        )


class ImportedBundleByteIdentityTest(unittest.TestCase):
    """AC1 -- each imported bundle is byte-identical to its counterpart
    under crucible:clients/skills/, WHEN that origin dir still exists on
    this machine (it freezes/retires post-handover, per CR context)."""

    def test_each_bundle_byte_identical_to_origin(self):
        if not ORIGIN_SKILLS_DIR.is_dir():
            self.skipTest(
                f"{ORIGIN_SKILLS_DIR} absent -- origin has frozen/retired "
                f"post-handover; byte-identity is no longer checkable"
            )
        mismatches = {}
        for name in IMPORTED_BUNDLE_NAMES:
            origin_dir = ORIGIN_SKILLS_DIR / name
            imported_dir = SKILLS_SRC_DIR / name
            if not origin_dir.is_dir():
                mismatches[name] = f"origin dir {origin_dir} missing"
                continue
            if not imported_dir.is_dir():
                mismatches[name] = f"imported dir {imported_dir} missing"
                continue
            origin_hashes = _relative_file_hashes(origin_dir)
            imported_hashes = _relative_file_hashes(imported_dir)
            if origin_hashes != imported_hashes:
                mismatches[name] = (
                    f"origin={origin_hashes} imported={imported_hashes}"
                )
        # POSITIVE/EXACT -- byte-for-byte identical file sets + content.
        self.assertEqual(
            mismatches, {},
            f"expected every imported bundle to be byte-identical to its "
            f"origin counterpart under {ORIGIN_SKILLS_DIR}; mismatches: {mismatches}",
        )


class ZeroWorkflowCycleIdUnderSkillsSrcTest(unittest.TestCase):
    """AC2 -- zero WORKFLOW_CYCLE_ID occurrences anywhere under
    skills-src/. Gated on the 7 imported bundles existing first (so this
    fails now, for a real content reason, rather than vacuously passing
    over an empty tree); the invariant it protects holds for the origin
    content, so it is expected to flip GREEN once Sec1 lands."""

    def test_bundles_present_and_zero_workflow_cycle_id_occurrences(self):
        missing = _missing_imported_bundles()
        self.assertEqual(
            missing, [],
            f"the 7 imported bundles must exist under skills-src/ first; "
            f"missing: {missing}",
        )
        offending = {}
        for p in sorted(SKILLS_SRC_DIR.rglob("*")):
            if not p.is_file():
                continue
            try:
                content = _read(p)
            except (UnicodeDecodeError, OSError):
                continue
            count = content.count("WORKFLOW_CYCLE_ID")
            if count:
                offending[str(p.relative_to(REPO_ROOT))] = count
        # EXACT bound -- zero occurrences anywhere under skills-src/.
        self.assertEqual(
            offending, {},
            f"expected zero 'WORKFLOW_CYCLE_ID' occurrences under "
            f"{SKILLS_SRC_DIR}, found: {offending}",
        )


class CrucibleSkillRoutingAndProtocolSyncTest(unittest.TestCase):
    """AC3 -- skills-src/crucible/SKILL.md routes every stack row
    (arduino included) to a crucible-report-<stack> bundle; zero
    occurrences of `clients/skills` as a live authority (the provenance
    doc is the only allowed place); documents the v2 touch contract per
    Sec2(b)."""

    def test_per_stack_table_routes_every_stack_to_crucible_report_bundle(self):
        self.assertTrue(CRUCIBLE_SKILL_MD.is_file(), f"{CRUCIBLE_SKILL_MD} must exist")
        content = _read(CRUCIBLE_SKILL_MD)
        missing_routes = [
            stack for stack in ALL_STACKS
            if f"crucible-report-{stack}" not in content
        ]
        # POSITIVE -- every stack row (arduino included) names its
        # Model-B-owned crucible-report-<stack> bundle.
        self.assertEqual(
            missing_routes, [],
            f"SKILL.md must route every stack {ALL_STACKS} to its "
            f"'crucible-report-<stack>' bundle; missing routes for: {missing_routes}",
        )

    def test_zero_clients_skills_live_authority_outside_handover_doc(self):
        offending = {}
        for p in sorted(SKILLS_SRC_DIR.rglob("*")):
            if not p.is_file() or p == HANDOVER_MD:
                continue
            try:
                content = _read(p)
            except (UnicodeDecodeError, OSError):
                continue
            count = content.count("clients/skills")
            if count:
                offending[str(p.relative_to(REPO_ROOT))] = count
        # EXACT bound -- 'clients/skills' as a live authority is banned
        # everywhere under skills-src/ except CRUCIBLE-HANDOVER.md.
        self.assertEqual(
            offending, {},
            f"expected zero 'clients/skills' occurrences under {SKILLS_SRC_DIR} "
            f"outside {HANDOVER_MD}, found: {offending}",
        )

    def test_v2_touch_contract_documented_and_phantom_claim_replaced(self):
        self.assertTrue(CRUCIBLE_SKILL_MD.is_file(), f"{CRUCIBLE_SKILL_MD} must exist")
        content = _read(CRUCIBLE_SKILL_MD)
        # POSITIVE -- the live v2 touch surface is documented.
        self.assertIn(
            "/api/v2/agents/heartbeat", content,
            "SKILL.md must document the '/api/v2/agents/heartbeat' v2 touch surface",
        )
        # NEGATIVE -- the stale "no separate heartbeat endpoint" claim
        # must be gone (replaced per Sec2(b)).
        self.assertNotIn(
            "there is NO separate heartbeat endpoint", content,
            "SKILL.md must not claim 'there is NO separate heartbeat endpoint' -- "
            "the v2 upsert handler makes this claim stale",
        )
        # EXACT bound -- zero references to the un-adopted shell helper.
        heartbeat_sh_count = content.count("heartbeat" + ".sh")
        self.assertEqual(
            heartbeat_sh_count, 0,
            f"expected zero heartbeat-helper-script occurrences in SKILL.md, "
            f"found {heartbeat_sh_count}",
        )


class ReferenceRoutersParityTest(unittest.TestCase):
    """AC7 (router part) -- references/{rust,java,bun,python}.md all still
    exist, and references/arduino.md EXISTS (new parity router).

    CR-MDB-024 \u00a7S3 AMENDMENT (this cycle, C2 RED, 2026-09-22 VS Code ruling):
    narrowed from six stacks to five -- the VS Code reference router is
    retired outright along with the rest of that substrate (an IDE is not
    a stack); its absence is gated separately in
    tests/test_ide_overlay_retirement.py.
    """

    def test_all_five_stack_reference_routers_exist_including_new_arduino(self):
        missing = [
            stack for stack in ALL_STACKS
            if not (REFERENCES_DIR / f"{stack}.md").is_file()
        ]
        # POSITIVE/EXACT -- consumer constraint: the four surviving
        # routers keep resolving, and arduino gains parity.
        self.assertEqual(
            missing, [],
            f"expected references/{{rust,java,bun,python,arduino}}.md to "
            f"all exist (arduino is the new parity router); missing: {missing}",
        )

    def test_arduino_reference_router_content_routes_to_bundle(self):
        arduino_ref = REFERENCES_DIR / "arduino.md"
        self.assertTrue(
            arduino_ref.is_file(),
            f"{arduino_ref} must exist as the new parity router",
        )
        content = _read(arduino_ref)
        self.assertGreater(len(content.strip()), 0, "references/arduino.md must not be empty")
        # POSITIVE -- the router routes to its bundled skill, matching the
        # thin-router pattern the other five references/*.md files use.
        self.assertIn(
            "crucible-report-arduino", content,
            "references/arduino.md must route to the bundled crucible-report-arduino skill",
        )


class RepoWideHeartbeatGrepGateTest(unittest.TestCase):
    """AC8 -- the amended PRD Sec4.2 grep gate (commit 3bd3561 semantics),
    scoped to skills-src/ -- the tree this CR's Sec1-Sec3 actually
    produces, mirroring the scoping CR-MDB-003 used for the identical
    criterion (pinned to the live SKILL.md, never the whole git tree).
    Gated on the 7 imported bundles existing first (so this fails now,
    for a real content reason)."""

    def test_heartbeat_helper_script_zero_hits_under_skills_src(self):
        missing = _missing_imported_bundles()
        self.assertEqual(
            missing, [],
            f"the 7 imported bundles must exist under skills-src/ first; "
            f"missing: {missing}",
        )
        script_basename = "heartbeat" + ".sh"
        offending = []
        for p in sorted(SKILLS_SRC_DIR.rglob("*")):
            if not p.is_file():
                continue
            try:
                content = _read(p)
            except (UnicodeDecodeError, OSError):
                continue
            if script_basename in content:
                offending.append(str(p.relative_to(REPO_ROOT)))
        # EXACT bound -- the un-adopted shell helper has zero hits under
        # skills-src/.
        self.assertEqual(
            offending, [],
            f"expected zero '{script_basename}' hits under {SKILLS_SRC_DIR}, "
            f"found: {offending}",
        )

    def test_every_agents_heartbeat_hit_under_skills_src_is_the_v2_form(self):
        missing = _missing_imported_bundles()
        self.assertEqual(
            missing, [],
            f"the 7 imported bundles must exist under skills-src/ first; "
            f"missing: {missing}",
        )
        phantom_endpoint = "/agents" + "/heartbeat"
        live_endpoint = "/api/v2" + phantom_endpoint
        non_v2_hits = []
        for p in sorted(SKILLS_SRC_DIR.rglob("*")):
            if not p.is_file():
                continue
            try:
                content = _read(p)
            except (UnicodeDecodeError, OSError):
                continue
            for line_no, line in enumerate(content.splitlines(), start=1):
                if phantom_endpoint in line and live_endpoint not in line:
                    non_v2_hits.append(f"{p.relative_to(REPO_ROOT)}:{line_no}")
        # EXACT bound -- every hit of the endpoint substring under
        # skills-src/ must be the live v2 form; zero bare/phantom hits.
        self.assertEqual(
            non_v2_hits, [],
            f"expected every '{phantom_endpoint}' hit under {SKILLS_SRC_DIR} to "
            f"be the '{live_endpoint}' form, found non-v2 hits: {non_v2_hits}",
        )


if __name__ == "__main__":
    unittest.main()
