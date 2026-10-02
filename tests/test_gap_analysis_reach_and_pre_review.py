"""Gap analysis reaches every consumer, and a spec is reviewed before it is approved
(CR-MDB-046 §S1, §S2; PRD D6, amended 2026-09-27; PRD D5; DN-multi-harness §D18).

- §S1 — ``skills-src/gap-analysis/SKILL.md`` gains, under its dimension headings, Dimension 8
  (rule and behaviour reach: every file that states or uses a changed rule — the skills and role
  references, the agent templates, ``builtin-tools.toml`` and the stack files, the memory templates
  and everything the scaffold renders, the tests that pin it; a hit the spec does not cover is a
  gap, not a follow-up), Dimension 9 (the scenario matrix: stack, agent role, orchestrator role,
  a tool present/absent/unknown, repo shape, a project scaffolded before the change, an upstream
  provider down; walked by reading, a sandbox only where reading cannot settle it; each case an AC
  or a non-goal) and Dimension 10 (standing invariants: ``AGENTS.md`` rules and existing gates).
  Its frontmatter ``description``, its intro and its finding format's Dimension field cover all
  ten. Under "Rules": re-scoping reruns both steps; the pre-review comes after the analysis and
  before approval, folded before locking; who and where (``CR-<ACRONYM>-NNN-SPEC-REVIEW``, the
  nearest registry, a VERIFY agent of a ``PROJECT_STACKS`` stack, read-only in the main tree);
  Rule 1 points to the pre-review as a separate review of the drafted spec.
- §S2 — ``orchestration-common`` (§ "Two-phase workflow", § "Gap-analysis discipline",
  § "Cycle discipline", the ``design-review`` milestone, the re-render rule for older projects),
  ``orchestration-mainline``'s design→execution gate, ``orchestration-track`` (setup ordering,
  main-tree pre-review, findings to Mainline, the reconciled in-worktree bullet), the ``crucible``
  skill (§ "Identity", "who runs what"), the ``model-b`` skill § 2, ``sub-agent-procedure.md`` and
  Model B's ``AGENTS.md`` agent-id note. (The scaffolded naming line ``_render_agents_md`` renders
  is pinned in ``tests.test_project_registry_schema``, where its golden is migrated.)
- §S4 — every other file that states the changed rules says the same: ``sub-agent-procedure.md``
  § "Worktree boundary" and ``contracts/worktree-layout.md`` carve the spec pre-review out of "a
  dispatch naming a CR runs in that CR's worktree" (main tree, read-only, a rerun after re-scoping
  included, even when the worktree exists; the pre-review asserts its toplevel is the main tree; the
  contract's ``worktree.ts`` row says the extension roots it there, by CR id or with a root
  entered), as does ``orchestration-common``'s dispatch-routing bullet; Model B's ``AGENTS.md``
  § "Workflow Rules" lists ``design-review``; the ``gap-analysis`` skill's Dimension 7 counts the
  other nine, ``READY`` leads to the pre-review and "When to Use" gives the new ordering;
  ``cr-authoring``'s design phase names the pre-review; ``orchestration-common`` says the
  orchestrator posts ``design-review`` after folding, never the ``report`` agent, and that the
  re-render rule upgrades Model B first; and no shipped file states the old ordering. (The VERIFY
  agent's First Actions are pinned in ``tests.test_verify_spec_pre_review_mode``, the scaffolded
  stack lines in ``tests.test_project_registry_schema``, the routing in
  ``tests.test_pi_worktree_isolation``.)

How a rule is read: phrase-level inside ONE unit — a list item with its nested items, or a
paragraph (``rule_units`` from ``tests.test_execution_knowledge_rules``); a Markdown table row is a
unit of its own. A dimension's enumeration (its file classes, its cases) is read across that
dimension's own section, which is the dimension. Every detector is proven both ways on synthetic,
spec-worded text in ``PreReviewRuleDetectorTest``; no test pins a line number. Skills name
capabilities, never a harness tool (§D18): no rule here needs a tool name.

Hermetic: reads only repo files. Stdlib only.
"""

import re
import unittest

from tests._helpers import REPO_ROOT, md_section, split_frontmatter
from tests.test_bootstrap_shutdown_registry import normalise
from tests.test_execution_knowledge_rules import _read, rule_units
from tests.test_orchestrator_rule_triage import section_body

GAP_REL = "skills-src/gap-analysis/SKILL.md"
COMMON_REL = "skills-src/model-b/references/orchestration-common.md"
MAINLINE_REL = "skills-src/model-b/references/orchestration-mainline.md"
TRACK_REL = "skills-src/model-b/references/orchestration-track.md"
CRUCIBLE_REL = "skills-src/crucible/SKILL.md"
MODEL_B_REL = "skills-src/model-b/SKILL.md"
PROCEDURE_REL = "skills-src/model-b/references/sub-agent-procedure.md"
AGENTS_REL = "AGENTS.md"

GA = r"\bgap[- ]analysis\b"

# ------------------------------------------------------------- §S1 rules ----

#: The three new dimension headings, by number: their titles.
NEW_DIMENSION_TITLES = {
    8: r"\brule and behaviou?r reach\b",
    9: r"\bscenario matrix\b",
    10: r"\bstanding invariants\b",
}

#: Dimension 8 — what it finds, and its file classes (read across the dimension's section).
DIM8_CLASSES = (
    r"\bevery file\b.{0,40}\bstates? or uses?\b",
    r"\bskills\b",
    r"\brole references\b",
    r"\bagent templates\b",
    r"builtin-tools\.toml",
    r"\bstack files\b",
    r"\bmemory templates\b",
    r"\bscaffold renders\b|\brendered by the scaffold\b",
    r"\btests? that pins?\b",
)
#: Dimension 8 — list each hit and where the spec covers it (one unit).
DIM8_LIST_EACH_HIT = (r"\blist each hit\b", r"\bwhere the spec covers it\b")
#: Dimension 8 — an uncovered hit is a gap, not a follow-up (one unit).
DIM8_GAP_NOT_FOLLOW_UP = (
    r"\bhit\b", r"\bspec does(?: not|n't) cover\b", r"\bis a gap\b", r"\bnot a follow-up\b")

#: Dimension 9 — its cases (read across the dimension's section).
DIM9_CASES = (
    r"\bstack\b",
    r"\bagent role\b",
    r"\borchestrator role\b",
    r"\bmainline\b",
    r"\btrack\b",
    r"\bsolo\b",
    r"\bpresent\b.{0,20}\babsent\b.{0,20}\bunknown\b",
    r"\brepo shape\b",
    r"\bscaffolded before the change\b",
    r"\bupstream provider\b.{0,30}\bdown\b",
)
#: Dimension 9 — walked by reading; a sandbox only where reading cannot settle it (one unit).
DIM9_BY_READING = (
    r"\bby reading\b",
    r"\bsandbox\b.{0,40}\bonly where reading cannot settle\b",
)
#: Dimension 9 — each case is an AC or a non-goal (one unit).
DIM9_AC_OR_NON_GOAL = (r"\beach case\b", r"\ban ac\b", r"\bnon-goal\b")

#: Dimension 10 — every new code path set against AGENTS.md's rules and existing gates (one unit).
DIM10_INVARIANTS = (
    r"\bnew code path\b",
    r"\bagents\.md\b",
    r"\brules\b",
    r"\bexisting gates\b",
)
#: Dimension 10 — a path that could break one gets an AC (one unit).
DIM10_GETS_AN_AC = (r"\bcould break\b", r"\bgets an ac\b")

#: "All ten dimensions": either a range form, or the three new dimensions named by their titles.
TEN_RANGE = r"\b1\s*[–-]\s*10\b|\bten dimensions\b|\ball ten\b"
TEN_NAMES = (r"\breach\b", r"\bscenario matrix\b|\bscenarios?\b", r"\binvariants\b")

#: Rules — re-scoping reruns both steps (one unit).
RULE_RESCOPING = (
    r"\bre-?scop\w*\b",
    r"\b(?:fresh|re-?runs?|again)\b",
    GA,
    r"\bpre-review\b",
)
#: Rules — after the analysis, before approval; folded in before locking (one unit).
RULE_PRE_REVIEW_ORDER = (
    r"\bpre-review\b",
    r"\bdispatch\w*\b",
    r"\bafter\b.{0,40}\banalysis\b",
    r"\bbefore\b.{0,60}\b(?:locks?|locking|approval)\b",
    r"\bfold\w*\b.{0,40}\bbefore lock\w*\b",
)
#: Rules — who and where (one unit, nested items included).
RULE_WHO_AND_WHERE = (
    r"cr-<acronym>-nnn-spec-review",
    r"\bnearest\b.{0,20}\bregistry\b",
    r"\bverify agent\b",
    r"\bproject_stacks\b",
    r"\bread-only\b",
    r"\bmain tree\b",
)
#: Rules — Rule 1 stands, and points to the pre-review (one numbered item).
RULE_ONE_POINTER = (
    r"\bnever delegate this analysis\b",
    r"\bpre-review\b",
    r"\bseparate\b",
    r"\bdrafted spec\b",
)

# ------------------------------------------------------------- §S2 rules ----

#: Two-phase workflow — the design phase lists gap analysis, then the pre-review.
TWO_PHASE_DESIGN = (r"\bdesign phase\b", GA + r".{0,80}\bpre-review\b")
#: Two-phase workflow — the VERIFY *agent* may run in the design phase, as the pre-review.
TWO_PHASE_VERIFY_WORD = (
    r"\bverify agent\b",
    r"\bdesign[- ]phase\b",
    r"\bpre-review\b",
    r"\bnever\b.{0,40}\bverify\b",
)
#: Gap-analysis discipline — kept: the orchestrator runs the gap analysis itself.
GA_DISCIPLINE_ITSELF = (r"\bthe orchestrator runs (?:the )?gap[- ]analysis itself\b",)
#: Gap-analysis discipline — the pre-review is a separate, dispatched review of the drafted spec.
GA_DISCIPLINE_SEPARATE = (
    r"\bpre-review\b", r"\bseparate\b", r"\bdispatch\w*\b", r"\bdrafted spec\b")
#: Gap-analysis discipline — points to the skill for the dimensions and the verdicts.
GA_DISCIPLINE_POINTER = (r"gap-analysis skill\b", r"\bdimensions\b", r"\bverdicts\b")
#: Gap-analysis discipline — none of these is listed in the section (raw text).
GA_DISCIPLINE_FORBIDDEN = {
    "spec↔PRD": re.compile(r"spec\s*↔\s*PRD"),
    "design-lineage": re.compile(r"design-lineage", re.IGNORECASE),
    "public-symbol": re.compile(r"public-symbol", re.IGNORECASE),
    "READY": re.compile(r"\bREADY\b"),
    "SPEC_UPDATE_NEEDED": re.compile(r"SPEC_UPDATE_NEEDED"),
}
#: The ordered chain gap-analysis → pre-review → approval → plan-file → branch/worktree.
ORDER_TO_PLAN_FILE = (
    GA + r".{0,30}\bpre-review\b.{0,40}\bapproval\b.{0,30}\bplan-file\b"
    r".{0,40}\b(?:branch|worktree)\b")
#: Cycle discipline — the setup ordering names the pre-review before approval.
CYCLE_SETUP_ORDER = (r"\bsetup ordering\b", ORDER_TO_PLAN_FILE)
#: A pre-review is a workflow moment: it posts a design-review milestone.
DESIGN_REVIEW_MILESTONE = (r"\bpre-review\b", r"\bmilestone\b", r"\bdesign-review\b")
#: Older projects re-render their agents before their first pre-review.
RE_RENDER_OLDER = (
    r"\bscaffolded before\b",
    r"\bre-?render\w*\b",
    r"\bmodelb-axi agents\b",
    r"\bbefore (?:its|the) first pre-review\b",
    r"\bhand-modified\b",
    r"\breported to the user\b|\breports? (?:it )?to the user\b",
)

#: Mainline — design→execution gate: gap-analysis → pre-review → fold → lock → present →
#: approval → plan.
MAINLINE_GATE = (
    r"design\s*→\s*execution gate",
    GA + r".{0,30}\bpre-review\b.{0,40}\bfold\w*\b.{0,60}\block\w*\b.{0,40}\bpresent\b"
    r".{0,60}\bapproval\b.{0,60}\bplan\b",
)

#: Track — the setup ordering names the pre-review, then plan-file, then worktree-flow start.
TRACK_SETUP_ORDER = (
    r"\bsetup ordering\b",
    GA + r".{0,30}\bpre-review\b.{0,60}\bapproval\b.{0,30}\bplan-file\b.{0,60}"
    r"\bworktree-flow start\b",
)
#: Track — the pre-review runs in the main tree, read-only.
TRACK_MAIN_TREE = (r"\bpre-review\b", r"\bmain tree\b", r"\bread-only\b")
#: Track — a Track raises its pre-review findings to Mainline, which folds them on develop.
TRACK_FINDINGS_TO_MAINLINE = (
    r"\bpre-review\b",
    r"\bfindings\b",
    r"\b(?:rais\w*|send\w*|report\w*)\b.{0,60}\bto mainline\b",
    r"\bfolds?\b.{0,60}\bdevelop\b",
)
#: Track — the reconciled in-worktree bullet.
TRACK_IN_WORKTREE_RECONCILED = (
    r"\bdesign[- ]phase\b",
    GA,
    r"\bpre-review\b",
    r"\bbefore the worktree exists\b",
    r"\beverything from worktree-flow start\b",
)
#: A unit claiming CR work is in-worktree …
IN_WORKTREE_CLAIM = r"\bin-worktree\b|\b100% of cr work\b"
#: … that still names the gap analysis or spec writing as worktree work.
IN_WORKTREE_DESIGN_WORK = GA + r"|\bspec[- ]writing\b"

#: crucible § Identity — the spec-review id, registered as report with no cycle.
CRUCIBLE_IDENTITY = (
    r"cr-<acronym>-nnn-spec-review",
    r"\breport\b",
    r"\bno (?:--)?cycle\b|\bwithout (?:a )?(?:--)?cycle\b|\bunbound\b",
)
#: crucible "who runs what" — the pre-review, a VERIFY-agent duty with no runs and no ingest.
CRUCIBLE_WHO_RUNS = (
    r"\bpre-review\b",
    r"\bverify[- ]agent\b",
    r"\bno (?:test )?runs\b|\bruns nothing\b|\bruns no\b",
    r"\bno ingest\b|\bingests nothing\b",
)
#: model-b § 2 — the pre-review is a report actor on the board, outside any cycle.
MODEL_B_ROLE = (
    r"\bpre-review\b",
    r"\breport\b",
    r"\bactor\b",
    r"\bboard\b",
    r"\boutside (?:any|a) cycle\b",
)
#: sub-agent procedure — a run-less report registration needs no heartbeat and no run to report.
PROCEDURE_RUN_LESS = (
    r"\brun-?less\b",
    r"\breport\b.{0,20}\bregistration\b",
    r"\bno heartbeat\b",
    r"\bno run to report\b",
)
#: Model B AGENTS.md — the agent-id note names the spec-review form.
AGENTS_ID_NOTE = (r"\bagent ids\b", r"cr-mdb-nnn-spec-review")

# ------------------------------------------------------------- §S4 rules ----

CONTRACT_REL = "contracts/worktree-layout.md"
CR_AUTHORING_REL = "skills-src/cr-authoring/SKILL.md"

SPEC_REVIEW_ID = r"cr-<acronym>-nnn-spec-review"
EVEN_WHEN_EXISTS = r"\beven when\b.{0,60}\bworktree\b.{0,30}\bexists\b"

#: Worktree boundary — the spec pre-review is the exception: main tree, read-only, a rerun after
#: re-scoping included, even when the worktree exists (one unit).
PROCEDURE_CARVE_OUT = (
    SPEC_REVIEW_ID,
    r"\bexception\b|\bexcept\b",
    r"\bmain tree\b",
    r"\bread-only\b",
    r"\bre-?scop\w*\b",
    EVEN_WHEN_EXISTS,
)
#: Worktree boundary — the pre-review asserts its toplevel is the main tree, and STOPs otherwise.
PROCEDURE_PRE_REVIEW_TOPLEVEL = (
    r"\bpre-review\b",
    r"\btoplevel\b",
    r"\bmain tree\b",
    r"\bstop\b",
)
#: The contract — the same carve-out, stated once (one unit).
CONTRACT_CARVE_OUT = (SPEC_REVIEW_ID, r"\bmain tree\b", r"\bread-only\b", EVEN_WHEN_EXISTS)
#: The contract's worktree.ts row — the extension roots a pre-review in the main tree, by its CR
#: id or with a root entered (the row is one unit).
CONTRACT_EXTENSION_ROW = (
    r"^\|\s*pi-package/extensions/worktree\.ts\s*\|",
    r"\bspec pre-review\b|spec-review",
    r"\bmain tree\b",
    r"\bentered\b",
)
#: orchestration-common — the dispatch-routing bullet names the pre-review's main-tree exception.
COMMON_DISPATCH_ROUTING = (
    r"\bdispatch description\b",
    r"\bspec pre-review\b|spec-review",
    r"\bmain tree\b",
)
#: Model B AGENTS.md § Workflow Rules — design-review listed with the other milestones (one unit).
AGENTS_WORKFLOW_MILESTONES = (
    r"\bmilestone\b",
    r"--type gap-analysis\b",
    r"--type design-review\b",
    r"\bstage-flip\b",
)
#: gap-analysis Dimension 7 — counts the other nine dimensions …
DIM7_NINE = (r"\bthe other nine dimensions\b",)
#: … and no longer the other six.
DIM7_OLD_COUNT = r"\bother (?:six|seven|eight)\b"
#: gap-analysis — the READY verdict leads to the pre-review, not to the feature branch.
READY_VERDICT = r"^- ready:"
#: gap-analysis "When to Use" — the new ordering (one unit).
WHEN_TO_USE_ORDER = (
    r"\bafter the spec is drafted\b",
    r"\bbefore\b.{0,20}\bpre-review\b",
    r"(?:gap[- ]analysis|this analysis).{0,30}\bpre-review\b.{0,40}\bapproval\b.{0,30}"
    r"\bplan-file\b.{0,60}\b(?:branch|worktree)\b",
)
#: gap-analysis "When to Use" — the old items that skipped the pre-review.
WHEN_TO_USE_OLD = r"\bbefore creating a feature branch\b|\bafter the spec is written but before red\b"
#: orchestration-common — the orchestrator posts design-review after folding, never the report
#: agent (one unit).
COMMON_WHO_POSTS = (
    r"\bdesign-review\b",
    r"\borchestrator\b.{0,30}\bposts?\b",
    r"\bfold\w*\b",
    r"\bnever\b.{0,40}\breport\b",
)
#: orchestration-common — the re-render rule upgrades Model B first, since `modelb-axi agents`
#: renders from the installed templates (one unit).
COMMON_UPGRADE_FIRST = (
    r"\bupgrades?\b.{0,20}\bmodel b\b",
    r"\brelease\b",
    r"\bmodelb-axi agents\b.{0,40}\brenders? from the installed templates\b",
    r"\bbefore (?:its|the) first pre-review\b",
)
#: No shipped file states the old ordering: an approval, lock or branch straight after the analysis.
OLD_ORDERING = re.compile(
    r"gap[- ]analysis\s*→\s*(?:lock|approval|present|`?plan-file)|proceed to feature branch",
    re.IGNORECASE)
#: The shipped surfaces the old-ordering gate reads.
ORDERING_SURFACES = ("skills-src", "generator/templates", "generator/stacks")


# ------------------------------------------------------------------ reading ----

def units(text: str) -> list[str]:
    """``rule_units`` over ``text``, every Markdown table row a unit of its own."""
    return rule_units(re.sub(r"(?m)^(\s*\|.*)$", r"\1\n", text))


def satisfying(text: str, rule: tuple) -> list[str]:
    return [u for u in units(text) if all(re.search(p, u) for p in rule)]


def missing(text: str, rule: tuple) -> str:
    all_units = units(text)
    if not all_units:
        return "no bullet or paragraph at all"
    best = max(all_units, key=lambda u: sum(1 for p in rule if re.search(p, u)))
    lacking = [p for p in rule if not re.search(p, best)]
    return f"closest unit {best[:240]!r} lacks {lacking!r}"


def lacking_across(text: str, patterns: tuple) -> list[str]:
    """The patterns absent from ``text`` read as one normalised whole."""
    whole = normalise(text)
    return [p for p in patterns if not re.search(p, whole)]


def covers_ten(text: str) -> bool:
    """``text`` (normalised) covers Dimensions 1–10: a range form, or the three new ones named."""
    t = normalise(text)
    return bool(re.search(TEN_RANGE, t)) or all(re.search(p, t) for p in TEN_NAMES)


def dimension_headings(text: str) -> list[tuple[int, str]]:
    """``(number, title)`` of every ``### Dimension N: title`` heading, in file order."""
    return [(int(m.group(1)), m.group(2).strip())
            for m in re.finditer(r"(?m)^###\s+Dimension\s+(\d+)\s*:\s*(.*)$", text)]


def dimension_body(text: str, number: int) -> str:
    """The section under ``### Dimension <number>:``; ``""`` when there is none."""
    for n, title in dimension_headings(text):
        if n == number:
            return section_body(text, f"Dimension {n}: {title}") or ""
    return ""


def dimensions_intro(text: str) -> str:
    """The prose of § "The Dimensions" before its first ``###`` heading."""
    body = section_body(text, "The Dimensions") or ""
    return re.split(r"(?m)^###\s", body, maxsplit=1)[0]


def dimension_field_lines(text: str) -> list[str]:
    """The finding format's ``Dimension`` field line(s) in § "Output Format"."""
    body = section_body(text, "Output Format") or ""
    return [ln for ln in body.splitlines() if re.match(r"^\s*-\s*\*\*Dimension\*\*\s*:", ln)]


def description(text: str) -> str:
    front, _ = split_frontmatter(text)
    m = re.search(r"(?m)^description:\s*(.*)$", front)
    return m.group(1) if m else ""


def forbidden_in(text: str) -> list[str]:
    return [name for name, rx in GA_DISCIPLINE_FORBIDDEN.items() if rx.search(text)]


def in_worktree_design_claims(text: str) -> list[str]:
    """Units claiming CR work is in-worktree that still name the gap analysis or spec writing as
    worktree work — unless the unit places the design phase before the worktree exists."""
    return [u for u in units(text)
            if re.search(IN_WORKTREE_CLAIM, u) and re.search(IN_WORKTREE_DESIGN_WORK, u)
            and not re.search(r"\bbefore the worktree exists\b", u)]


def _section(rel: str, prefix: str) -> str:
    text = md_section(_read(rel), prefix)
    if not text:
        raise AssertionError(f"{rel} has no section headed {prefix!r}")
    return text


class _RuleAssertions(unittest.TestCase):
    def assert_rule(self, text: str, rule: tuple, where: str):
        self.assertTrue(satisfying(text, rule),
                        f"{where}: no single bullet or paragraph states the rule; "
                        f"{missing(text, rule)}")

    def assert_across(self, text: str, patterns: tuple, where: str):
        self.assertEqual(lacking_across(text, patterns), [],
                         f"{where}: the section does not name these")


# ------------------------------------------------- §S1 — gap-analysis skill ----

class GapAnalysisNewDimensionsTest(_RuleAssertions):
    """§S1: Dimensions 8–10 under the skill's existing dimension headings, each saying what the
    spec gives it."""

    def test_the_dimension_headings_run_one_to_ten_in_order_under_the_dimensions(self):
        body = section_body(_read(GAP_REL), "The Dimensions") or ""
        numbers = [n for n, _ in dimension_headings(body)]
        self.assertEqual(numbers, list(range(1, 11)),
                         f"{GAP_REL} § The Dimensions: ### Dimension 1..10, each once, in order")

    def test_dimensions_eight_to_ten_carry_their_spec_titles(self):
        headings = dict(dimension_headings(_read(GAP_REL)))
        for number, title in NEW_DIMENSION_TITLES.items():
            with self.subTest(dimension=number):
                self.assertIn(number, headings, f"{GAP_REL}: no '### Dimension {number}:' heading")
                self.assertRegex(normalise(headings[number]), title)

    def test_dimension_eight_names_every_file_class_that_states_or_uses_a_rule(self):
        body = dimension_body(_read(GAP_REL), 8)
        self.assertTrue(body.strip(), f"{GAP_REL}: no Dimension 8")
        self.assert_across(body, DIM8_CLASSES, f"{GAP_REL} Dimension 8")

    def test_dimension_eight_lists_each_hit_and_an_uncovered_hit_is_a_gap_not_a_follow_up(self):
        body = dimension_body(_read(GAP_REL), 8)
        self.assertTrue(body.strip(), f"{GAP_REL}: no Dimension 8")
        self.assert_rule(body, DIM8_LIST_EACH_HIT, f"{GAP_REL} Dimension 8")
        self.assert_rule(body, DIM8_GAP_NOT_FOLLOW_UP, f"{GAP_REL} Dimension 8")

    def test_dimension_nine_lists_every_case_of_the_scenario_matrix(self):
        body = dimension_body(_read(GAP_REL), 9)
        self.assertTrue(body.strip(), f"{GAP_REL}: no Dimension 9")
        self.assert_across(body, DIM9_CASES, f"{GAP_REL} Dimension 9")

    def test_dimension_nine_walks_by_reading_with_a_sandbox_only_where_reading_cannot_settle(self):
        body = dimension_body(_read(GAP_REL), 9)
        self.assertTrue(body.strip(), f"{GAP_REL}: no Dimension 9")
        self.assert_rule(body, DIM9_BY_READING, f"{GAP_REL} Dimension 9")
        self.assert_rule(body, DIM9_AC_OR_NON_GOAL, f"{GAP_REL} Dimension 9")

    def test_dimension_ten_sets_new_code_paths_against_agents_md_rules_and_existing_gates(self):
        body = dimension_body(_read(GAP_REL), 10)
        self.assertTrue(body.strip(), f"{GAP_REL}: no Dimension 10")
        self.assert_rule(body, DIM10_INVARIANTS, f"{GAP_REL} Dimension 10")
        self.assert_rule(body, DIM10_GETS_AN_AC, f"{GAP_REL} Dimension 10")


class GapAnalysisCoversAllTenTest(unittest.TestCase):
    """§S1: the frontmatter ``description``, the intro on how the dimensions group, and the finding
    format's Dimension field each cover Dimensions 1–10."""

    def test_the_frontmatter_description_covers_all_ten_dimensions(self):
        desc = description(_read(GAP_REL))
        self.assertTrue(desc, f"{GAP_REL}: no frontmatter description")
        self.assertTrue(covers_ten(desc), f"{GAP_REL} description stops short of 1–10: {desc!r}")

    def test_the_intro_on_how_the_dimensions_group_covers_all_ten(self):
        intro = dimensions_intro(_read(GAP_REL))
        self.assertTrue(intro.strip(), f"{GAP_REL}: § The Dimensions has no intro")
        self.assertTrue(covers_ten(intro), f"{GAP_REL} intro stops short of 1–10: {intro!r}")

    def test_the_finding_formats_dimension_field_covers_all_ten(self):
        fields = dimension_field_lines(_read(GAP_REL))
        self.assertEqual(len(fields), 1, f"{GAP_REL}: exactly one Dimension field; got {fields!r}")
        self.assertTrue(covers_ten(fields[0]),
                        f"{GAP_REL} Dimension field stops short of 1–10: {fields[0]!r}")


class GapAnalysisPreReviewRulesTest(_RuleAssertions):
    """§S1 "Under Rules": re-scoping reruns both steps; the pre-review's place; who and where;
    Rule 1 stands and points to the pre-review."""

    def _rules(self) -> str:
        body = section_body(_read(GAP_REL), "Rules") or ""
        self.assertTrue(body.strip(), f"{GAP_REL}: no '## Rules' section")
        return body

    def test_re_scoping_reruns_the_gap_analysis_and_the_pre_review(self):
        self.assert_rule(self._rules(), RULE_RESCOPING, f"{GAP_REL} § Rules")

    def test_the_pre_review_is_dispatched_after_the_analysis_before_approval_folded_before_locking(self):
        self.assert_rule(self._rules(), RULE_PRE_REVIEW_ORDER, f"{GAP_REL} § Rules")

    def test_who_and_where_id_form_nearest_registry_project_stacks_verify_main_tree_read_only(self):
        self.assert_rule(self._rules(), RULE_WHO_AND_WHERE, f"{GAP_REL} § Rules")

    def test_rule_one_stands_and_points_to_the_separate_pre_review_of_the_drafted_spec(self):
        self.assert_rule(self._rules(), RULE_ONE_POINTER, f"{GAP_REL} § Rules")
        first = [u for u in units(self._rules()) if u.startswith("1. ")]
        self.assertEqual(len(first), 1, "§ Rules has exactly one Rule 1")
        self.assertRegex(first[0], r"\bnever delegate this analysis\b",
                         "Rule 1 is still 'never delegate this analysis'")


# --------------------------------------------- §S2 — orchestration-common ----

class OrchestrationCommonPreReviewTest(_RuleAssertions):
    """§S2 ``orchestration-common``: the design phase, the narrowed VERIFY word rule, the
    gap-analysis discipline, the setup ordering, the milestone and the re-render rule."""

    def test_the_design_phase_lists_gap_analysis_then_the_pre_review(self):
        self.assert_rule(_section(COMMON_REL, "## Two-phase workflow"), TWO_PHASE_DESIGN,
                         f"{COMMON_REL} § Two-phase workflow")

    def test_the_verify_word_rule_scopes_the_phase_not_the_agent(self):
        self.assert_rule(_section(COMMON_REL, "## Two-phase workflow"), TWO_PHASE_VERIFY_WORD,
                         f"{COMMON_REL} § Two-phase workflow")

    def test_the_orchestrator_still_runs_the_gap_analysis_itself(self):
        # Regression pin: §S2 keeps the sentence.
        self.assert_rule(_section(COMMON_REL, "## Gap-analysis discipline"), GA_DISCIPLINE_ITSELF,
                         f"{COMMON_REL} § Gap-analysis discipline")

    def test_the_pre_review_is_a_separate_dispatched_review_of_the_drafted_spec(self):
        self.assert_rule(_section(COMMON_REL, "## Gap-analysis discipline"),
                         GA_DISCIPLINE_SEPARATE, f"{COMMON_REL} § Gap-analysis discipline")

    def test_it_points_to_the_skill_for_the_dimensions_and_the_verdicts(self):
        self.assert_rule(_section(COMMON_REL, "## Gap-analysis discipline"),
                         GA_DISCIPLINE_POINTER, f"{COMMON_REL} § Gap-analysis discipline")

    def test_it_lists_neither_the_dimensions_nor_the_verdicts(self):
        section = _section(COMMON_REL, "## Gap-analysis discipline")
        self.assertEqual(forbidden_in(section), [],
                         f"{COMMON_REL} § Gap-analysis discipline names what the skill owns")

    def test_the_cycle_setup_ordering_names_the_pre_review_before_approval(self):
        self.assert_rule(_section(COMMON_REL, "## Cycle discipline"), CYCLE_SETUP_ORDER,
                         f"{COMMON_REL} § Cycle discipline")

    def test_a_pre_review_posts_a_design_review_milestone(self):
        self.assert_rule(_read(COMMON_REL), DESIGN_REVIEW_MILESTONE, COMMON_REL)

    def test_an_older_project_re_renders_its_agents_before_its_first_pre_review(self):
        self.assert_rule(_read(COMMON_REL), RE_RENDER_OLDER, COMMON_REL)


# ------------------------------------- §S2 — orchestration-mainline / track ----

class OrchestrationMainlineGateTest(_RuleAssertions):
    """§S2: the design→execution gate is gap-analysis → pre-review → fold its findings → lock the
    spec → present → wait for approval → the cycle plan."""

    def test_the_design_to_execution_gate_reads_pre_review_then_fold_lock_present_approval_plan(self):
        self.assert_rule(_read(MAINLINE_REL), MAINLINE_GATE, MAINLINE_REL)


class OrchestrationTrackPreReviewTest(_RuleAssertions):
    """§S2 ``orchestration-track``: the setup ordering matches; the pre-review runs in the main
    tree, read-only; findings go to Mainline; the in-worktree bullet is reconciled."""

    def test_the_setup_ordering_names_the_pre_review_before_plan_file_and_the_worktree(self):
        self.assert_rule(_read(TRACK_REL), TRACK_SETUP_ORDER, TRACK_REL)

    def test_the_pre_review_runs_in_the_main_tree_read_only(self):
        self.assert_rule(_read(TRACK_REL), TRACK_MAIN_TREE, TRACK_REL)

    def test_a_track_raises_its_pre_review_findings_to_mainline_who_folds_them_on_develop(self):
        self.assert_rule(_read(TRACK_REL), TRACK_FINDINGS_TO_MAINLINE, TRACK_REL)

    def test_design_phase_steps_happen_before_the_worktree_and_the_rest_from_start_on_in_it(self):
        self.assert_rule(_read(TRACK_REL), TRACK_IN_WORKTREE_RECONCILED, TRACK_REL)

    def test_the_in_worktree_bullet_no_longer_claims_the_gap_analysis_or_spec_writing(self):
        self.assertEqual(in_worktree_design_claims(_read(TRACK_REL)), [],
                         f"{TRACK_REL}: an in-worktree claim still names design-phase work")


# ------------------------------- §S2 — crucible, model-b, procedure, AGENTS ----

class RoleDescriptionsPreReviewTest(_RuleAssertions):
    """§S2: the ``crucible`` skill's Identity and who-runs-what, the ``model-b`` skill § 2,
    ``sub-agent-procedure.md`` and Model B's ``AGENTS.md`` agent-id note."""

    def test_crucible_identity_names_the_spec_review_id_registered_as_report_with_no_cycle(self):
        self.assert_rule(_section(CRUCIBLE_REL, "## Identity"), CRUCIBLE_IDENTITY,
                         f"{CRUCIBLE_REL} § Identity")

    def test_crucible_who_runs_what_lists_the_pre_review_as_a_verify_duty_with_no_runs_or_ingest(self):
        self.assert_rule(_section(CRUCIBLE_REL, "## Who runs what"), CRUCIBLE_WHO_RUNS,
                         f"{CRUCIBLE_REL} § Who runs what")

    def test_model_b_section_two_makes_the_pre_review_a_report_actor_outside_any_cycle(self):
        self.assert_rule(_section(MODEL_B_REL, "## 2."), MODEL_B_ROLE, f"{MODEL_B_REL} § 2")

    def test_the_sub_agent_procedure_needs_no_heartbeat_and_no_run_for_a_run_less_report(self):
        self.assert_rule(_read(PROCEDURE_REL), PROCEDURE_RUN_LESS, PROCEDURE_REL)

    def test_model_b_agents_md_agent_id_note_names_the_spec_review_form(self):
        self.assert_rule(_read(AGENTS_REL), AGENTS_ID_NOTE, AGENTS_REL)


# ----------------------------------- §S4 — every other file states the same ----

class WorktreeBoundaryPreReviewCarveOutTest(_RuleAssertions):
    """§S4: the worktree boundary, the layout contract and the dispatch-routing bullet carve the
    spec pre-review out — main tree, read-only, a rerun after re-scoping included, even when the
    CR's worktree exists."""

    def test_the_worktree_boundary_carves_out_the_pre_review_in_the_main_tree_even_with_a_worktree(self):
        self.assert_rule(_section(PROCEDURE_REL, "## Worktree boundary"), PROCEDURE_CARVE_OUT,
                         f"{PROCEDURE_REL} § Worktree boundary")

    def test_the_pre_review_asserts_its_toplevel_is_the_main_tree_and_stops_otherwise(self):
        self.assert_rule(_section(PROCEDURE_REL, "## Worktree boundary"),
                         PROCEDURE_PRE_REVIEW_TOPLEVEL, f"{PROCEDURE_REL} § Worktree boundary")

    def test_the_layout_contract_states_the_carve_out(self):
        self.assert_rule(_read(CONTRACT_REL), CONTRACT_CARVE_OUT, CONTRACT_REL)

    def test_the_contracts_extension_row_says_it_roots_the_pre_review_in_the_main_tree(self):
        self.assert_rule(_section(CONTRACT_REL, "## Consumers"), CONTRACT_EXTENSION_ROW,
                         f"{CONTRACT_REL} § Consumers")

    def test_the_dispatch_routing_bullet_names_the_pre_reviews_main_tree_exception(self):
        self.assert_rule(_section(COMMON_REL, "## Worktree isolation"), COMMON_DISPATCH_ROUTING,
                         f"{COMMON_REL} § Worktree isolation")


class ReachOfTheChangedRulesTest(_RuleAssertions):
    """§S4: Model B's ``AGENTS.md`` milestones, the ``gap-analysis`` skill's own text,
    ``cr-authoring``'s design phase, and ``orchestration-common``'s milestone and re-render rules."""

    def test_model_b_agents_md_workflow_rules_list_the_design_review_milestone(self):
        self.assert_rule(_section(AGENTS_REL, "## Workflow Rules"), AGENTS_WORKFLOW_MILESTONES,
                         f"{AGENTS_REL} § Workflow Rules")

    def test_dimension_seven_counts_the_other_nine_dimensions(self):
        body = dimension_body(_read(GAP_REL), 7)
        self.assertTrue(body.strip(), f"{GAP_REL}: no Dimension 7")
        self.assert_rule(body, DIM7_NINE, f"{GAP_REL} Dimension 7")
        self.assertNotRegex(normalise(body), DIM7_OLD_COUNT, f"{GAP_REL} Dimension 7: a stale count")

    def test_the_ready_verdict_leads_to_the_pre_review_not_to_the_feature_branch(self):
        ready = [u for u in units(section_body(_read(GAP_REL), "Verdicts:") or "")
                 if re.match(READY_VERDICT, u)]
        self.assertEqual(len(ready), 1, f"{GAP_REL}: exactly one READY verdict; got {ready!r}")
        self.assertRegex(ready[0], r"\bpre-review\b", "READY leads to the pre-review")
        self.assertNotRegex(ready[0], r"\bfeature branch\b", "READY no longer leads to the branch")

    def test_when_to_use_gives_the_new_ordering_and_drops_the_old_items(self):
        body = section_body(_read(GAP_REL), "When to Use") or ""
        self.assertTrue(body.strip(), f"{GAP_REL}: no '## When to Use'")
        self.assert_rule(body, WHEN_TO_USE_ORDER, f"{GAP_REL} § When to Use")
        self.assertEqual([u for u in units(body) if re.search(WHEN_TO_USE_OLD, u)], [],
                         f"{GAP_REL} § When to Use still gives the old ordering")

    def test_cr_authoring_design_phase_lists_the_pre_review(self):
        self.assert_rule(_section(CR_AUTHORING_REL, "## Two-phase workflow"), TWO_PHASE_DESIGN,
                         f"{CR_AUTHORING_REL} § Two-phase workflow")

    def test_the_orchestrator_posts_design_review_after_folding_never_the_report_agent(self):
        self.assert_rule(_read(COMMON_REL), COMMON_WHO_POSTS, COMMON_REL)

    def test_the_re_render_rule_upgrades_model_b_first(self):
        self.assert_rule(_read(COMMON_REL), COMMON_UPGRADE_FIRST, COMMON_REL)

    def test_no_shipped_file_states_the_old_ordering(self):
        hits = [f"{rel}: {m.group(0)!r}" for rel, text in _ordering_surfaces()
                for m in OLD_ORDERING.finditer(text)]
        self.assertEqual(hits, [], "a shipped file states the ordering without the pre-review")


def _ordering_surfaces() -> list[tuple[str, str]]:
    """``(repo-relative path, text)`` of every Markdown, template and TOML file under
    :data:`ORDERING_SURFACES`, plus Model B's ``AGENTS.md``."""
    out = [(AGENTS_REL, _read(AGENTS_REL))]
    for surface in ORDERING_SURFACES:
        for path in sorted((REPO_ROOT / surface).rglob("*")):
            if path.is_file() and path.suffix in (".md", ".tmpl", ".toml"):
                out.append((path.relative_to(REPO_ROOT).as_posix(),
                            path.read_text(encoding="utf-8")))
    return out


# ------------------------------------------------- detectors, synthetic text ----

GOOD_GAP = """\
---
name: gap-analysis
description: Pre-implementation gap analysis for CR specs along ten dimensions — spec vs PRD, spec vs code, code vs PRD, reinvention, design-lineage, public-symbol removal, cost, rule and behaviour reach, scenario matrix and standing invariants.
---

# Gap Analysis

## The Dimensions

Every gap analysis checks these dimensions. The first three are the core triangle; four to seven
guard against reinvention, mistaken retire calls, orphaned consumers and cost; eight to ten check
reach, the scenario matrix and the standing invariants.

### Dimension 7: Cost — Is each criterion worth it?

- [ ] What must be built?

### Dimension 8: Rule and behaviour reach — Is every consumer covered?

For every rule or behaviour the CR changes, find every file that states or uses it:
- the skills and role references;
- the agent templates, `builtin-tools.toml` and the stack files;
- the memory templates, and everything the scaffold renders;
- the tests that pin any of it.

List each hit and where the spec covers it. A hit the spec does not cover is a gap, not a follow-up.

### Dimension 9: Scenario matrix — Is every case covered?

Enumerate every case the change varies over, as applicable:
- the stack and the agent role;
- the orchestrator role (Mainline, Track, Solo);
- a tool that is present, absent or unknown;
- the repo shape;
- a project scaffolded before the change;
- an upstream provider that is down.

Walk each case once against the current code, by reading. Run it in a `/tmp` sandbox only where
reading cannot settle it. Each case is covered by an AC, or named as a non-goal.

### Dimension 10: Standing invariants — Does a new path break a rule?

Set every new code path or step against the project's `AGENTS.md` rules and its existing gates.
Any path that could break one gets an AC.

## Output Format

```
### DRIFT-N: [title]
- **Dimension**: 1 (Spec vs PRD) / 2 (Spec vs Code) / 3 (Code vs PRD) / 4 (Reinvention) / 5 (Design-lineage) / 6 (Public-symbol removal) / 7 (Cost) / 8 (Reach) / 9 (Scenario matrix) / 10 (Standing invariants)
```

## Rules

1. **Never delegate this analysis to a sub-agent** — this is the orchestrator's responsibility.
   The pre-review is a separate review of the drafted spec.
2. **Re-scoping reruns both steps.** A spec that is restructured or re-scoped gets a fresh gap
   analysis and a fresh pre-review.
3. **The pre-review comes after the analysis, before approval.** The orchestrator dispatches it
   after its own analysis and before it locks and presents the spec. The findings are folded in
   before locking.
4. **Who and where:**
   - **Id:** `CR-<ACRONYM>-NNN-SPEC-REVIEW`, the acronym taken from the nearest registry.
   - **Reviewer:** the VERIFY agent of a stack in that registry's `PROJECT_STACKS`.
   - **Where it runs:** read-only in the main tree.
"""

#: Today's (pre-CR) wording, abridged: seven dimensions, no pre-review anywhere.
OLD_GAP = """\
---
name: gap-analysis
description: Pre-implementation gap and drift analysis for CR specs. Multi-dimensional check — spec vs PRD, spec vs code, code vs PRD, spec vs existing mechanisms, design-lineage, public-symbol removal, and cost (is each criterion worth what satisfying it requires building).
---

## The Dimensions

Every gap analysis checks these dimensions. Missing any one causes design drift. The first three
are the core triangle (spec ↔ PRD ↔ code); the last three guard against reinvention, mistaken
retire/delete calls, and orphaned consumers.

### Dimension 7: Cost — Is each criterion worth what satisfying it requires?

- [ ] What must be built?

## Output Format

```
- **Dimension**: 1 (Spec vs PRD) / 2 (Spec vs Code) / 3 (Code vs PRD) / 4 (Reinvention) / 5 (Design-lineage) / 6 (Public-symbol removal) / 7 (Cost)
```

## Rules

1. **Never delegate this analysis to a sub-agent** — this is the orchestrator's responsibility
"""

GOOD_COMMON = """\
## Two-phase workflow
- **Design phase → `develop`.** Gap-analysis, then the spec pre-review; spec/PRD/DN/queue edits.
- **Execution phase → feature branch.** RED+GREEN cycles, VERIFY, FIX, regression, merge.
- `VERIFY` names the execution phase only: the VERIFY agent may run in the design phase in its spec
  pre-review mode, and that step is called the pre-review, never "verify".

## Gap-analysis discipline (gap-analysis FIRST, before any branch/RED)
- **The orchestrator runs the gap analysis itself** (never delegate to a sub-agent).
- **The pre-review is a separate, dispatched review of the drafted spec**, after the analysis.
- **The dimensions and the verdicts live in the `gap-analysis` skill** — read it; they are not
  listed here.
- **A pre-review is a workflow moment:** it posts a `design-review` milestone.
- **Older projects:** a project scaffolded before the pre-review mode re-renders its agents with
  `modelb-axi agents` before its first pre-review. A definition left alone as hand-modified is
  reported to the user.

## Cycle discipline
- Setup ordering: gap-analysis → pre-review → approval → `plan-file` → THEN the branch / worktree.
"""

OLD_COMMON = """\
## Two-phase workflow
- **Design phase → `develop`.** Gap-analysis, spec/PRD/DN/queue edits. No feature branch.
- `VERIFY` is an EXECUTION-phase word ONLY — design-phase validation is **gap-analysis**; never call it "verify".

## Gap-analysis discipline (gap-analysis FIRST, before any branch/RED)
- **The orchestrator runs gap-analysis itself** (never delegate to a sub-agent).
- **The dimensions are the single authority in the `gap-analysis` skill** — read it for the full check (spec↔PRD↔code + spec-vs-existing-mechanisms + design-lineage + public-symbol-removal). Do NOT re-list them here.
- Verdict: READY / SPEC_UPDATE_NEEDED / PREREQUISITE_NEEDED / BLOCKED.

## Cycle discipline
- Setup ordering: gap-analysis → approval → `plan-file` → THEN the branch / worktree.
"""

GOOD_MAINLINE = """\
- **Design→execution gate:** gap-analysis → pre-review → fold its findings → lock the spec →
  present → WAIT for explicit approval → ONLY THEN cycle plan.
"""
OLD_MAINLINE = """\
- **Design→execution gate:** gap-analysis → lock the spec → present → WAIT for explicit approval → ONLY THEN cycle plan.
"""

GOOD_TRACK = """\
- **Design-phase steps (the gap analysis, the pre-review) happen before the worktree exists**, and
  everything from `worktree-flow start` on happens in it — RED / GREEN / VERIFY / builds.
- Setup ordering: spec → gap-analysis → pre-review → present + get approval → `plan-file` → THEN
  `worktree-flow start` + dispatch.
- The pre-review runs in the main tree, read-only.
- A Track raises its pre-review findings to Mainline, which folds them into the spec on develop.
"""
OLD_TRACK = """\
- **100% of CR work is in-worktree** — investigation / §S1 / gap-analysis / spec-writing / RED / GREEN / VERIFY / builds.
- Setup ordering: spec → gap-analysis → present + get approval → `plan-file` → THEN `worktree-flow start` + dispatch.
"""

GOOD_CRUCIBLE_IDENTITY = """\
## Identity — ONE agent id for the whole session

- TDD-role agents: `CR-<ACRONYM>-NNN-<cycle>-<ROLE>`.
- Spec pre-review: `CR-<ACRONYM>-NNN-SPEC-REVIEW`, registered as `--role report` with no cycle.
"""
GOOD_CRUCIBLE_WHO = """\
## Who runs what

- **VERIFY agent** — registers + REVIEWS. Does NOT run the regression.
  - Its spec pre-review is a VERIFY-agent duty with no runs and no ingest.
"""
GOOD_MODEL_B = """\
## 2. Role hierarchy + labels

| Role | Scope | Authority |
|---|---|---|
| **RED / GREEN / VERIFY / FIX** (phase agents) | one phase of one cycle | execute and report |
| **Spec pre-review** (a VERIFY agent) | one drafted spec | a `report` actor on the board, outside any cycle |
"""
GOOD_PROCEDURE = """\
## Crucible lifecycle — register FIRST, unregister LAST
- Heartbeat ~every 2 min. A run-less `report` registration needs no heartbeat, and has no run to report.
"""
GOOD_AGENTS = """\
- **Agent ids:** free-form — TDD-role agents by convention `CR-MDB-NNN-<cycle>-<ROLE>`, the spec
  pre-review `CR-MDB-NNN-SPEC-REVIEW` (registered `report`), orchestrator ops `vidushi-mdb`.
"""


class PreReviewRuleDetectorTest(unittest.TestCase):
    """Every detector proven both ways on synthetic text: the spec-worded text satisfies it, and
    today's wording (or a one-phrase mutation) does not."""

    def test_a_table_row_is_a_unit_of_its_own(self):
        table = ("| Role | Scope |\n|---|---|\n| pre-review | a report actor |\n"
                 "| other | on the board, outside any cycle |\n")
        self.assertEqual(satisfying(table, MODEL_B_ROLE), [])
        self.assertEqual(len(satisfying(GOOD_MODEL_B, MODEL_B_ROLE)), 1)

    def test_a_rule_split_across_two_bullets_is_not_satisfied(self):
        split = "- The pre-review runs in the main tree.\n- It is read-only.\n"
        self.assertEqual(satisfying(split, TRACK_MAIN_TREE), [])
        self.assertEqual(len(satisfying("- The pre-review runs in the main tree, read-only.\n",
                                        TRACK_MAIN_TREE)), 1)

    def test_the_spec_worded_gap_analysis_satisfies_every_s1_detector(self):
        self.assertEqual([n for n, _ in dimension_headings(GOOD_GAP)], [7, 8, 9, 10])
        headings = dict(dimension_headings(GOOD_GAP))
        for number, title in NEW_DIMENSION_TITLES.items():
            with self.subTest(heading=number):
                self.assertRegex(normalise(headings[number]), title)
        self.assertEqual(lacking_across(dimension_body(GOOD_GAP, 8), DIM8_CLASSES), [])
        self.assertEqual(lacking_across(dimension_body(GOOD_GAP, 9), DIM9_CASES), [])
        for number, rule in ((8, DIM8_LIST_EACH_HIT), (8, DIM8_GAP_NOT_FOLLOW_UP),
                             (9, DIM9_BY_READING), (9, DIM9_AC_OR_NON_GOAL),
                             (10, DIM10_INVARIANTS), (10, DIM10_GETS_AN_AC)):
            body = dimension_body(GOOD_GAP, number)
            with self.subTest(dimension=number, rule=rule[0]):
                self.assertTrue(satisfying(body, rule), missing(body, rule))
        self.assertTrue(covers_ten(description(GOOD_GAP)))
        self.assertTrue(covers_ten(dimensions_intro(GOOD_GAP)))
        self.assertEqual(len(dimension_field_lines(GOOD_GAP)), 1)
        self.assertTrue(covers_ten(dimension_field_lines(GOOD_GAP)[0]))
        rules = section_body(GOOD_GAP, "Rules") or ""
        for rule in (RULE_RESCOPING, RULE_PRE_REVIEW_ORDER, RULE_WHO_AND_WHERE, RULE_ONE_POINTER):
            with self.subTest(rule=rule[0]):
                self.assertTrue(satisfying(rules, rule), missing(rules, rule))

    def test_todays_gap_analysis_wording_fails_every_s1_detector(self):
        self.assertEqual([n for n, _ in dimension_headings(OLD_GAP)], [7])
        self.assertEqual(dimension_body(OLD_GAP, 8), "")
        self.assertFalse(covers_ten(description(OLD_GAP)))
        self.assertFalse(covers_ten(dimensions_intro(OLD_GAP)))
        self.assertFalse(covers_ten(dimension_field_lines(OLD_GAP)[0]))
        rules = section_body(OLD_GAP, "Rules") or ""
        for rule in (RULE_RESCOPING, RULE_PRE_REVIEW_ORDER, RULE_WHO_AND_WHERE, RULE_ONE_POINTER):
            with self.subTest(rule=rule[0]):
                self.assertEqual(satisfying(rules, rule), [])

    def test_each_s1_detector_bites_when_its_phrase_is_changed(self):
        mutations = {
            "classes": (8, DIM8_CLASSES, "- the memory templates, and everything the scaffold renders;\n", ""),
            "builtin": (8, DIM8_CLASSES, "`builtin-tools.toml` and ", ""),
            "gap": (8, DIM8_GAP_NOT_FOLLOW_UP, "not a follow-up", "a follow-up"),
            "unknown": (9, DIM9_CASES, "present, absent or unknown", "present or absent"),
            "scaffolded": (9, DIM9_CASES, "- a project scaffolded before the change;\n", ""),
            "provider": (9, DIM9_CASES, "- an upstream provider that is down.\n", ""),
            "orchestrator": (9, DIM9_CASES, "(Mainline, Track, Solo)", "(Mainline, Track)"),
            "sandbox": (9, DIM9_BY_READING, "only where\nreading cannot settle it",
                        "for every case"),
            "gates": (10, DIM10_INVARIANTS, " and its existing gates", ""),
        }
        for name, (number, rule, old, new) in mutations.items():
            with self.subTest(mutation=name):
                self.assertIn(old, GOOD_GAP)
                body = dimension_body(GOOD_GAP.replace(old, new), number)
                if rule in (DIM8_CLASSES, DIM9_CASES):
                    self.assertNotEqual(lacking_across(body, rule), [])
                else:
                    self.assertEqual(satisfying(body, rule), [])

    def test_each_rules_detector_bites_when_its_phrase_is_changed(self):
        mutations = {
            "rescope": (RULE_RESCOPING, " and a fresh pre-review", ""),
            "fold": (RULE_PRE_REVIEW_ORDER, "folded in\n   before locking", "noted"),
            "id": (RULE_WHO_AND_WHERE, "-SPEC-REVIEW", "-REVIEW"),
            "nearest": (RULE_WHO_AND_WHERE, "the nearest registry", "the root registry"),
            "stacks": (RULE_WHO_AND_WHERE, "`PROJECT_STACKS`", "stack list"),
            "main tree": (RULE_WHO_AND_WHERE, "in the main tree", "in the worktree"),
            "rule 1": (RULE_ONE_POINTER, "\n   The pre-review is a separate review of the drafted spec.", ""),
        }
        for name, (rule, old, new) in mutations.items():
            with self.subTest(mutation=name):
                self.assertIn(old, GOOD_GAP)
                rules = section_body(GOOD_GAP.replace(old, new), "Rules") or ""
                self.assertEqual(satisfying(rules, rule), [])

    def test_covers_ten_accepts_a_range_or_the_new_names_and_rejects_seven(self):
        for good in ("Dimensions 1–10", "all ten dimensions",
                     "8 (Reach) / 9 (Scenario matrix) / 10 (Standing invariants)"):
            with self.subTest(good=good):
                self.assertTrue(covers_ten(good))
        for bad in ("1 (Spec vs PRD) / 7 (Cost)", "seven dimensions", "Dimensions 1–7"):
            with self.subTest(bad=bad):
                self.assertFalse(covers_ten(bad))

    def test_the_spec_worded_orchestration_common_satisfies_every_detector(self):
        two = md_section(GOOD_COMMON, "## Two-phase workflow")
        disc = md_section(GOOD_COMMON, "## Gap-analysis discipline")
        cycle = md_section(GOOD_COMMON, "## Cycle discipline")
        for text, rule in ((two, TWO_PHASE_DESIGN), (two, TWO_PHASE_VERIFY_WORD),
                           (disc, GA_DISCIPLINE_ITSELF), (disc, GA_DISCIPLINE_SEPARATE),
                           (disc, GA_DISCIPLINE_POINTER), (cycle, CYCLE_SETUP_ORDER),
                           (GOOD_COMMON, DESIGN_REVIEW_MILESTONE), (GOOD_COMMON, RE_RENDER_OLDER)):
            with self.subTest(rule=rule[0]):
                self.assertTrue(satisfying(text, rule), missing(text, rule))
        self.assertEqual(forbidden_in(disc), [])

    def test_todays_orchestration_common_wording_fails_the_new_detectors(self):
        two = md_section(OLD_COMMON, "## Two-phase workflow")
        disc = md_section(OLD_COMMON, "## Gap-analysis discipline")
        cycle = md_section(OLD_COMMON, "## Cycle discipline")
        for text, rule in ((two, TWO_PHASE_DESIGN), (two, TWO_PHASE_VERIFY_WORD),
                           (disc, GA_DISCIPLINE_SEPARATE), (disc, GA_DISCIPLINE_POINTER),
                           (cycle, CYCLE_SETUP_ORDER), (OLD_COMMON, DESIGN_REVIEW_MILESTONE),
                           (OLD_COMMON, RE_RENDER_OLDER)):
            with self.subTest(rule=rule[0]):
                self.assertEqual(satisfying(text, rule), [])
        self.assertTrue(satisfying(disc, GA_DISCIPLINE_ITSELF), "today's sentence is kept")
        self.assertEqual(forbidden_in(disc),
                         ["spec↔PRD", "design-lineage", "public-symbol", "READY",
                          "SPEC_UPDATE_NEEDED"])

    def test_the_forbidden_terms_detector_spares_already_and_bites_each_term(self):
        self.assertEqual(forbidden_in("- the work is already ready in lower case.\n"), [])
        for term in GA_DISCIPLINE_FORBIDDEN:
            with self.subTest(term=term):
                self.assertEqual(forbidden_in(f"- {term}\n"), [term])

    def test_each_common_detector_bites_when_its_phrase_is_changed(self):
        mutations = {
            "milestone": (DESIGN_REVIEW_MILESTONE, "`design-review`", "`stage-flip`"),
            "re-render": (RE_RENDER_OLDER, "`modelb-axi agents`", "hand"),
            "reported": (RE_RENDER_OLDER, "reported to the user", "kept"),
            "order": (CYCLE_SETUP_ORDER, "pre-review → approval", "approval → pre-review"),
        }
        for name, (rule, old, new) in mutations.items():
            with self.subTest(mutation=name):
                self.assertIn(old, GOOD_COMMON)
                self.assertEqual(satisfying(GOOD_COMMON.replace(old, new), rule), [])

    def test_the_mainline_gate_detector_reads_the_full_chain_in_order(self):
        self.assertEqual(len(satisfying(GOOD_MAINLINE, MAINLINE_GATE)), 1)
        self.assertEqual(satisfying(OLD_MAINLINE, MAINLINE_GATE), [])
        no_fold = GOOD_MAINLINE.replace(" → fold its findings", "")
        self.assertEqual(satisfying(no_fold, MAINLINE_GATE), [])
        reordered = GOOD_MAINLINE.replace("gap-analysis → pre-review", "pre-review → gap-analysis")
        self.assertEqual(satisfying(reordered, MAINLINE_GATE), [])

    def test_the_track_detectors_both_ways(self):
        for rule in (TRACK_SETUP_ORDER, TRACK_MAIN_TREE, TRACK_FINDINGS_TO_MAINLINE,
                     TRACK_IN_WORKTREE_RECONCILED):
            with self.subTest(rule=rule[0]):
                self.assertTrue(satisfying(GOOD_TRACK, rule), missing(GOOD_TRACK, rule))
                self.assertEqual(satisfying(OLD_TRACK, rule), [])
        self.assertEqual(in_worktree_design_claims(GOOD_TRACK), [])
        self.assertEqual(len(in_worktree_design_claims(OLD_TRACK)), 1)
        self.assertEqual(
            satisfying(GOOD_TRACK.replace("folds them into the spec on develop", "edits its spec"),
                       TRACK_FINDINGS_TO_MAINLINE), [])

    def test_the_role_description_detectors_both_ways(self):
        cases = (
            (GOOD_CRUCIBLE_IDENTITY, CRUCIBLE_IDENTITY, "with no cycle", "bound to the cycle"),
            (GOOD_CRUCIBLE_WHO, CRUCIBLE_WHO_RUNS, " and no ingest", ""),
            (GOOD_MODEL_B, MODEL_B_ROLE, "outside any cycle", "inside the verify cycle"),
            (GOOD_PROCEDURE, PROCEDURE_RUN_LESS, "needs no heartbeat", "heartbeats"),
            (GOOD_AGENTS, AGENTS_ID_NOTE, "`CR-MDB-NNN-SPEC-REVIEW`", "`CR-MDB-NNN-REVIEW`"),
        )
        for text, rule, old, new in cases:
            with self.subTest(rule=rule[0]):
                self.assertTrue(satisfying(text, rule), missing(text, rule))
                self.assertIn(old, text)
                self.assertEqual(satisfying(text.replace(old, new), rule), [])


GOOD_PROCEDURE_BOUNDARY = """\
## Worktree boundary (NON-NEGOTIABLE)
- **If spawned in a worktree, that worktree is your ONLY writable root.** A dispatch naming a CR runs
  rooted in that CR's worktree.
- **The spec pre-review is the exception.** A spec pre-review (`CR-<ACRONYM>-NNN-SPEC-REVIEW`) runs
  read-only in the main tree \u2014 a rerun after re-scoping included, even when the CR's worktree
  already exists. Its first check asserts `git rev-parse --show-toplevel` is the main tree, not a
  `.worktrees/<cr>`; if it is not, STOP and report.
"""
OLD_PROCEDURE_BOUNDARY = """\
## Worktree boundary (NON-NEGOTIABLE)
- **If spawned in a worktree, that worktree is your ONLY writable root.** A dispatch naming a CR runs
  rooted in that CR's worktree. Establish it FIRST: `git rev-parse --show-toplevel` from cwd.
"""
GOOD_CONTRACT = """\
A spec pre-review (`CR-<ACRONYM>-NNN-SPEC-REVIEW`) is the exception: it runs read-only in the main
tree, even when the CR's worktree already exists.

## Consumers

| Consumer | How it carries the string |
|---|---|
| `pi-package/extensions/worktree.ts` | routes each dispatch naming a CR to its registered `.worktrees/<cr>`, except a spec pre-review (`CR-<ACRONYM>-NNN-SPEC-REVIEW`), which it roots in the main tree, by its CR id or with a root entered |
"""
OLD_CONTRACT = """\
## Consumers

| Consumer | How it carries the string |
|---|---|
| `pi-package/extensions/worktree.ts` | routes each dispatch naming a CR to its registered `.worktrees/<cr>`; `modelb_worktree_enter` accepts only such a registered worktree |
"""
GOOD_ROUTING = """\
- Name the CR id in every dispatch description (that routes the agent into the CR's worktree) \u2014
  except a spec pre-review (`CR-<ACRONYM>-NNN-SPEC-REVIEW`), which runs in the main tree.
"""
OLD_ROUTING = """\
- Name the CR id in every dispatch description (that routes the agent into the CR's worktree).
"""
GOOD_AGENTS_MILESTONES = """\
- Post a `milestone` at every workflow moment: `--type gap-analysis` when gap analysis completes,
  `--type design-review` when the orchestrator has folded a spec pre-review's findings,
  `--type stage-flip --label "<CR> <cycle> done"` at each cycle-done.
"""
OLD_AGENTS_MILESTONES = """\
- Post a `milestone` at every workflow moment: `--type gap-analysis` when gap analysis completes, `--type stage-flip --label "<CR> <cycle> done"` at each cycle-done.
"""
GOOD_GAP_REACH = """\
## When to Use

- After the spec is drafted, before its pre-review: the ordering is this analysis \u2192 the spec
  pre-review \u2192 approval \u2192 `plan-file` \u2192 the feature branch or worktree \u2192 RED.
- When a CR predates recent codebase changes

### Dimension 7: Cost \u2014 Is each criterion worth it?

**The other nine dimensions ask whether a criterion is TRUE. This one asks whether it is WORTH IT.**

### Verdicts:

- **READY**: Spec is accurate, code matches PRD; proceed to the spec pre-review
- **BLOCKED**: Fundamental design issue
"""
OLD_GAP_REACH = """\
## When to Use

- Before starting ANY CR implementation
- Before creating a feature branch
- After the spec is written but before RED phase

### Dimension 7: Cost \u2014 Is each criterion worth it?

**The other six dimensions ask whether a criterion is TRUE. This one asks whether it is WORTH IT.**

### Verdicts:

- **READY**: Spec is accurate, code matches PRD, proceed to feature branch
"""
GOOD_CR_AUTHORING = """\
## Two-phase workflow (universal) + where work commits
- **Design phase \u2192 the integration branch (`develop`/`main`).** Gap analysis, then the spec
  pre-review; spec authoring, queue/PRD/DN updates. No feature branch.
"""
OLD_CR_AUTHORING = """\
## Two-phase workflow (universal) + where work commits
- **Design phase \u2192 the integration branch (`develop`/`main`).** Gap analysis, spec authoring, queue/PRD/DN updates. No feature branch.
"""
GOOD_COMMON_REACH = """\
- **A pre-review is a workflow moment:** the orchestrator posts a `design-review` milestone once it
  has folded the pre-review's findings into the spec \u2014 never the `report` agent.
- **Older projects:** a project scaffolded before the spec pre-review existed first upgrades Model B
  to a release carrying it \u2014 `modelb-axi agents` renders from the installed templates \u2014 then
  re-renders its agents with `modelb-axi agents` before its first pre-review. A definition left
  alone as hand-modified is reported to the user.
"""
OLD_COMMON_REACH = """\
- **A pre-review is a workflow moment:** it posts a `design-review` milestone, as a completed gap analysis posts a `gap-analysis` one.
- **Older projects:** a project scaffolded before the spec pre-review existed re-renders its agents with `modelb-axi agents` before its first pre-review. A definition left alone as hand-modified is reported to the user.
"""


class ReachDetectorTest(unittest.TestCase):
    """Every \u00a7S4 detector proven both ways on synthetic text: the spec-worded text satisfies it,
    today's wording does not, and a one-phrase mutation bites."""

    CASES = (
        ("boundary", GOOD_PROCEDURE_BOUNDARY, OLD_PROCEDURE_BOUNDARY, PROCEDURE_CARVE_OUT,
         ", even when the CR's worktree\n  already exists", ""),
        ("toplevel", GOOD_PROCEDURE_BOUNDARY, OLD_PROCEDURE_BOUNDARY, PROCEDURE_PRE_REVIEW_TOPLEVEL,
         "STOP and report", "carry on"),
        ("contract", GOOD_CONTRACT, OLD_CONTRACT, CONTRACT_CARVE_OUT, "read-only ", ""),
        ("row", GOOD_CONTRACT, OLD_CONTRACT, CONTRACT_EXTENSION_ROW,
         ", by its CR id or with a root entered", ""),
        ("routing", GOOD_ROUTING, OLD_ROUTING, COMMON_DISPATCH_ROUTING,
         "which runs in the main tree", "which is routed too"),
        ("milestones", GOOD_AGENTS_MILESTONES, OLD_AGENTS_MILESTONES, AGENTS_WORKFLOW_MILESTONES,
         "`--type design-review`", "a review"),
        ("cr-authoring", GOOD_CR_AUTHORING, OLD_CR_AUTHORING, TWO_PHASE_DESIGN,
         ", then the spec\n  pre-review", ""),
        ("who posts", GOOD_COMMON_REACH, OLD_COMMON_REACH, COMMON_WHO_POSTS,
         " \u2014 never the `report` agent", ""),
        ("upgrade", GOOD_COMMON_REACH, OLD_COMMON_REACH, COMMON_UPGRADE_FIRST,
         "first upgrades Model B\n  to a release carrying it \u2014 ", ""),
    )

    def test_each_reach_detector_both_ways_and_bites_on_its_phrase(self):
        for name, good, old, rule, phrase, swap in self.CASES:
            with self.subTest(detector=name):
                section = good if name != "row" else md_section(good, "## Consumers")
                self.assertTrue(satisfying(section, rule), missing(section, rule))
                self.assertEqual(satisfying(old, rule), [])
                self.assertIn(phrase, good)
                mutated = good.replace(phrase, swap)
                if name == "row":
                    mutated = md_section(mutated, "## Consumers")
                self.assertEqual(satisfying(mutated, rule), [])

    def test_the_contract_row_rule_reads_only_the_extensions_row(self):
        other = ("| `skills-src/model-b/references/sub-agent-procedure.md` | a spec pre-review "
                 "asserts the main tree, worktree entered or not |\n")
        self.assertEqual(satisfying(other, CONTRACT_EXTENSION_ROW), [])

    def test_the_gap_analysis_reach_detectors_both_ways(self):
        for text, good in ((GOOD_GAP_REACH, True), (OLD_GAP_REACH, False)):
            with self.subTest(good=good):
                dim7 = dimension_body(text, 7)
                self.assertEqual(bool(satisfying(dim7, DIM7_NINE)), good)
                self.assertEqual(bool(re.search(DIM7_OLD_COUNT, normalise(dim7))), not good)
                ready = [u for u in units(section_body(text, "Verdicts:") or "")
                         if re.match(READY_VERDICT, u)]
                self.assertEqual(len(ready), 1)
                self.assertEqual(bool(re.search(r"\bpre-review\b", ready[0])), good)
                self.assertEqual(bool(re.search(r"\bfeature branch\b", ready[0])), not good)
                when = section_body(text, "When to Use") or ""
                self.assertEqual(bool(satisfying(when, WHEN_TO_USE_ORDER)), good)
                self.assertEqual(any(re.search(WHEN_TO_USE_OLD, u) for u in units(when)), not good)
        reordered = GOOD_GAP_REACH.replace("the spec\n  pre-review \u2192 approval",
                                           "approval \u2192 the spec\n  pre-review")
        self.assertEqual(satisfying(section_body(reordered, "When to Use") or "",
                                    WHEN_TO_USE_ORDER), [])

    def test_the_old_ordering_gate_bites_on_each_old_form_and_spares_the_new(self):
        for old in ("gap-analysis \u2192 approval \u2192 `plan-file`", "gap-analysis \u2192 lock the spec",
                    "spec \u2192 gap-analysis \u2192 present + get approval",
                    "Spec is accurate, proceed to feature branch"):
            with self.subTest(old=old):
                self.assertIsNotNone(OLD_ORDERING.search(old))
        for new in ("gap-analysis \u2192 pre-review \u2192 approval \u2192 `plan-file`",
                    "gap-analysis \u2192 pre-review \u2192 fold its findings \u2192 lock the spec",
                    "proceed to the spec pre-review"):
            with self.subTest(new=new):
                self.assertIsNone(OLD_ORDERING.search(new))


if __name__ == "__main__":
    unittest.main()
