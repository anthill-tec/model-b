"""Gap analysis reaches every consumer, and a spec is reviewed before it is approved
(CR-MDB-046 §S1, §S2; PRD D6, amended 2026-09-27; PRD D5; DN-multi-harness §D18).

- §S1 — ``skills-src/gap-analysis/SKILL.md`` gains, under its dimension headings, Dimension 8
  (rule and behaviour reach: every file that states or uses a changed rule — the skills and role
  references, the agent templates, ``builtin-tools.toml`` and the stack files, the stack skills and
  their references (MIGRATED, CR-MDB-060 §S4.2: were the memory templates, which Dimension 8 no
  longer names) and everything the scaffold renders, the tests that pin it; a hit the spec does
  not cover is a gap, not a follow-up), Dimension 9 (the scenario matrix: stack, agent role, orchestrator role,
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

CR-MDB-096 (§S1, §S2, §S4.1; PRD D6, amended 2026-10-30) — the pre-review runs where it pays:

- §S1 — the ``gap-analysis`` skill states the rule once: § When to Use and ``READY`` carry the
  conditional (Rule 21), Rule 1 points to Rules 21, 22, 24 and 25, Rule 20 decides the triggers
  again, Rule 21 the three triggers and their definitions, Rule 24 the checklist, Rule 25 the
  record on the ``**Status:**`` line; Rules 21, 24 and 25 are each one unit.
- §S2 — the role table row, ``orchestration-common``/``-mainline``/``-track``, ``cr-authoring``
  and ``crucible`` name the pre-review as conditional; none restates the triggers or the checklist
  (the restatement detector, AC2).
- §S4.1 — the migrated pins each require their conditional in the same unit; the ordering guard
  (AC3) finds a pre-review linked into an ordering without it; ``OLD_ORDERING`` is kept.

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

#: CR-MDB-096 §S4.1 — the conditional a migrated pin requires in its own unit. §S1.5's Rule 21
#: lead is worded "when at least one trigger applies"; that form is the same conditional.
TRIGGER_APPLIES = r"\bwhen (?:at least one|a) trigger applies\b"
#: CR-MDB-096 AC3 — the conditionals the ordering guard accepts.
GUARD_CONDITIONAL = TRIGGER_APPLIES + r"|\bwhen the cr meets a trigger\b"
#: CR-MDB-096 §S2 — the pointer to the triggers' one home.
RULE_21_POINTER = r"\bgap-analysis rule 21\b"

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
    # MIGRATED (CR-MDB-060 §S4.2/AC5): was r"\bmemory templates\b" — Dimension 8 names the stack
    # skills and their references where it named the memory templates.
    r"\bstack skills\b.{0,80}\breferences\b",
    r"\bscaffold renders\b|\brendered by the scaffold\b",
    r"\btests? that pins?\b",
)
#: CR-MDB-060 §S4.2/AC5 — what Dimension 8 no longer names: the retired memory templates.
DIM8_RETIRED = re.compile(r"\bmemory[\s-]+templates?\b", re.IGNORECASE)
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
#: MIGRATED (CR-MDB-096 §S4.1): the fresh pre-review is conditional — `when a trigger applies`.
RULE_RESCOPING = (
    r"\bre-?scop\w*\b",
    r"\b(?:fresh|re-?runs?|again)\b",
    GA,
    r"\bpre-review\b",
    TRIGGER_APPLIES,
)
#: Rules — after the analysis, before approval; folded in before locking (one unit).
#: MIGRATED (CR-MDB-096 §S4.1): dispatched when a trigger applies; "fold … before locking" kept.
RULE_PRE_REVIEW_ORDER = (
    r"\bpre-review\b",
    r"\bdispatch\w*\b",
    r"\bafter\b.{0,40}\banalysis\b",
    r"\bbefore\b.{0,60}\b(?:locks?|locking|approval)\b",
    r"\bfold\w*\b.{0,40}\bbefore lock\w*\b",
    TRIGGER_APPLIES,
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
#: MIGRATED (CR-MDB-096 §S4.1): "then the spec pre-review when a trigger applies".
TWO_PHASE_DESIGN = (r"\bdesign phase\b", GA + r".{0,80}\bpre-review\b", TRIGGER_APPLIES)
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
#: MIGRATED (CR-MDB-096 §S4.1): dispatched when a trigger applies.
GA_DISCIPLINE_SEPARATE = (
    r"\bpre-review\b", r"\bseparate\b", r"\bdispatch\w*\b", r"\bdrafted spec\b", TRIGGER_APPLIES)
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
#: MIGRATED (CR-MDB-096 §S4.1): the chain carries `when a trigger applies` in the same unit.
ORDER_TO_PLAN_FILE = (
    GA + r".{0,30}\bpre-review\b.{0,40}\bapproval\b.{0,30}\bplan-file\b"
    r".{0,40}\b(?:branch|worktree)\b",
    TRIGGER_APPLIES,
)
#: Cycle discipline — the setup ordering names the pre-review before approval.
CYCLE_SETUP_ORDER = (r"\bsetup ordering\b",) + ORDER_TO_PLAN_FILE
#: A pre-review is a workflow moment: it posts a design-review milestone.
#: MIGRATED (CR-MDB-096 §S4.1): posted `when a pre-review ran` — a CR with no trigger posts none.
DESIGN_REVIEW_MILESTONE = (
    r"\bpre-review\b", r"\bmilestone\b", r"\bdesign-review\b", r"\bwhen a pre-review ran\b")
#: Older projects re-render their agents before their next pre-review.
#: MIGRATED (CR-MDB-096 §S4.1): was `before (?:its|the) first pre-review`; now `before its next
#: pre-review`, and the agents rendered before the pre-review's `checklist` are older too.
RE_RENDER_OLDER = (
    r"\bscaffolded before\b",
    r"\bre-?render\w*\b",
    r"\bmodelb-axi agents\b",
    r"\bbefore its next pre-review\b",
    r"\bchecklist\b",
    r"\bhand-modified\b",
    r"\breported to the user\b|\breports? (?:it )?to the user\b",
)

#: Mainline — design→execution gate: gap-analysis → pre-review → fold → lock → present →
#: approval → plan.
#: MIGRATED (CR-MDB-096 §S4.1): the pre-review link carries `when a trigger applies`.
MAINLINE_GATE = (
    r"design\s*→\s*execution gate",
    GA + r".{0,30}\bpre-review\b.{0,40}\bfold\w*\b.{0,60}\block\w*\b.{0,40}\bpresent\b"
    r".{0,60}\bapproval\b.{0,60}\bplan\b",
    TRIGGER_APPLIES,
)
#: CR-MDB-096 §S2.3 — the gate presents the spec with the pre-review record (one unit).
MAINLINE_GATE_RECORD = (r"design\s*→\s*execution gate", r"\bpresent, with the pre-review record\b")

#: Track — the setup ordering names the pre-review, then plan-file, then worktree-flow start.
#: MIGRATED (CR-MDB-096 §S4.1): the pre-review link carries `when a trigger applies`.
TRACK_SETUP_ORDER = (
    r"\bsetup ordering\b",
    GA + r".{0,30}\bpre-review\b.{0,60}\bapproval\b.{0,30}\bplan-file\b.{0,60}"
    r"\bworktree-flow start\b",
    TRIGGER_APPLIES,
)
#: Track — the pre-review runs in the main tree, read-only.
TRACK_MAIN_TREE = (r"\bpre-review\b", r"\bmain tree\b", r"\bread-only\b")
#: Track — a Track raises its pre-review findings to Mainline, which folds them on develop.
#: MIGRATED (CR-MDB-096 §S4.1): it raises its `trigger decision` too.
TRACK_FINDINGS_TO_MAINLINE = (
    r"\bpre-review\b",
    r"\bfindings\b",
    r"\b(?:rais\w*|send\w*|report\w*)\b.{0,60}\bto mainline\b",
    r"\bfolds?\b.{0,60}\bdevelop\b",
    r"\btrigger decision\b",
)
#: CR-MDB-096 §S2.4 — the design-phase steps: the gap analysis and, when a trigger applies, the
#: spec pre-review, before the worktree exists (one unit).
TRACK_DESIGN_STEPS = (
    r"\bdesign[- ]phase steps\b", GA, r"\bpre-review\b", TRIGGER_APPLIES,
    r"\bbefore the worktree exists\b")
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
#: MIGRATED (CR-MDB-096 §S4.1): `before its next pre-review` in place of `before (?:its|the)
#: first pre-review`, and the release is the one carrying the checklist.
COMMON_UPGRADE_FIRST = (
    r"\bupgrades?\b.{0,20}\bmodel b\b",
    r"\brelease carrying the checklist\b",
    r"\bmodelb-axi agents\b.{0,40}\brenders? from the installed templates\b",
    r"\bbefore its next pre-review\b",
)
#: No shipped file states the old ordering: an approval, lock or branch straight after the analysis.
OLD_ORDERING = re.compile(
    r"gap[- ]analysis\s*→\s*(?:lock|approval|present|`?plan-file)|proceed to feature branch",
    re.IGNORECASE)
#: The shipped surfaces the old-ordering gate reads.
# MIGRATED (CR-MDB-085 §S6.1): the stack skills' sources are an ordering surface too.
ORDERING_SURFACES = ("skills-src", "generator/templates", "generator/stacks", "generator/skills")

# ------------------------------- CR-MDB-096 §S1 — the triggers, checklist, record ----

#: §S1.1 — § When to Use's ordering carries the conditional and points to Rule 21 (one unit).
WHEN_TO_USE_CONDITIONAL = WHEN_TO_USE_ORDER + (TRIGGER_APPLIES, r"\brule 21\b")
#: §S1.2 — READY: the pre-review when a trigger applies (Rule 21), else approval (one unit).
READY_CONDITIONAL = (
    r"\bpre-review\b", TRIGGER_APPLIES, r"\brule 21\b", r"\belse\b.{0,20}\bapproval\b")
#: §S1.3 — Rule 1 points to Rules 21, 22, 24 and 25.
RULE_ONE_POINTS_TO = (r"\brules 21, 22, 24 and 25\b",)
#: §S1.4 / AC6 — Rule 20: a re-scoped spec's fresh gap analysis decides the triggers again.
RULE_TWENTY_TRIGGERS_AGAIN = (r"\bre-?scop\w*\b", r"\bdecides? the triggers again\b")

#: §S1 — every pin on the `gap-analysis` skill: ``(name, where, rule)``. ``where`` is
#: ``when to use``, ``ready`` or ``rule <n>`` (the one unit that IS numbered rule <n>). One cut of a
#: spec phrase yields exactly its own name (``GapAnalysisTriggerRuleDetectorTest``).
GAP_PINS = (
    ("when to use: the ordering carries the conditional", "when to use", WHEN_TO_USE_CONDITIONAL),
    ("ready: the pre-review when a trigger applies, else approval", "ready", READY_CONDITIONAL),
    ("rule 1: points to rules 21, 22, 24 and 25", "rule 1", RULE_ONE_POINTS_TO),
    ("rule 20: a fresh pre-review when a trigger applies", "rule 20", RULE_RESCOPING),
    ("rule 20: the triggers decided again", "rule 20", RULE_TWENTY_TRIGGERS_AGAIN),
    ("rule 21: dispatched when a trigger applies, folded before locking", "rule 21",
     RULE_PRE_REVIEW_ORDER),
    ("rule 21: 8 points or more", "rule 21", (r"\b8 points or more\b",)),
    ("rule 21: a contract, a hook or another project's surface", "rule 21",
     (r"\ba contract, a hook or another project's surface\b",)),
    ("rule 21: a ruling from the user", "rule 21", (r"\ba ruling from the user\b",)),
    ("rule 21: a contract is a file under contracts/ or an interface agents.md names", "rule 21",
     (r"\bcontract is a file under\b.{0,30}\bcontracts/",
      r"\binterface\b.{0,20}\bagents\.md names as a contract\b")),
    ("rule 21: a hook is a hook script, the hook schema or compiled hook wiring", "rule 21",
     (r"\bhook is a hook script\b", r"\bthe hook schema\b", r"\bcompiled hook wiring\b")),
    ("rule 21: a surface is a file, cli, api or message format another project consumes or "
     "provides", "rule 21",
     (r"\bsurface is a file, cli, api or message format\b",
      r"\banother project consumes or provides\b")),
    ("rule 21: any other spec goes from the analysis to approval", "rule 21",
     (r"\bany other spec goes from the analysis to approval\b",)),
    ("rule 24: a pre-review looks only for", "rule 24", (r"\bpre-review looks only for\b",)),
    ("rule 24: no test can meet or check", "rule 24",
     (r"\ban acceptance criterion no test can meet or check\b",)),
    ("rule 24: a missing failure path or edge case", "rule 24",
     (r"\ba missing failure path or edge case\b",)),
    ("rule 24: a gap in scope or design", "rule 24", (r"\ba gap in scope or design\b",)),
    ("rule 24: a conflict with the prd or a dn", "rule 24",
     (r"\ba conflict with the prd or a dn\b",)),
    ("rule 24: wording and naming are not findings", "rule 24",
     (r"\bwording and naming are not findings\b",)),
    ("rule 24: folds in nothing outside", "rule 24", (r"\bfolds in nothing outside\b",)),
    ("rule 25: on the status line", "rule 25", (r"\bstatus: line\b",)),
    ("rule 25: due — decided, not yet run", "rule 25",
     (r"pre-review: due — <trigger>", r"\bdecided, not yet run\b")),
    ("rule 25: ran — <trigger>", "rule 25", (r"pre-review: ran — <trigger>",)),
    ("rule 25: none — no trigger", "rule 25", (r"pre-review: none — no trigger",)),
    ("rule 25: written when the analysis decides the triggers", "rule 25",
     (r"\bwrites? it when the analysis decides the triggers\b",)),
    ("rule 25: due moves to ran at the fold", "rule 25",
     (r"\bmoves? due to ran\b.{0,30}\bfold\w*\b",)),
    ("rule 25: repeated at approval", "rule 25", (r"\brepeats? it\b.{0,60}\bapproval\b",)),
    ("rule 25: a re-scoping rewrites it", "rule 25", (r"\bre-?scoping\b.{0,20}\brewrites? it\b",)),
    ("rule 25: the completed flip keeps it", "rule 25", (r"\bcompleted flip keeps it\b",)),
    ("rule 25: a track reports its decision to mainline, which records it", "rule 25",
     (r"\btrack reports? its decision to mainline\b", r"\bmainline records? it\b")),
)
#: §S1 lead / AC1 — the rules that are each ONE block, with no blank line inside.
ONE_BLOCK_RULES = (21, 24, 25)

# ----------------------------- CR-MDB-096 §S2 — the references follow the one home ----

#: §S2.1 — the role table's pre-review row (a table row is a unit of its own).
ROLE_ROW_TRIGGER = (
    r"^\| spec pre-review\b",
    r"\bone drafted spec, before approval, when a trigger applies\b",
    RULE_21_POINTER,
)
#: §S2.2 — the older-projects bullet: §S4.1's two migrated pins read as the one unit they are.
OLDER_PROJECTS = tuple(dict.fromkeys(RE_RENDER_OLDER + COMMON_UPGRADE_FIRST))
#: §S2.5 — `cr-authoring`'s front matter: `**Status:**` carries the pre-review record (Rule 25).
CR_AUTHORING_STATUS_RECORD = (
    r"\bfront matter\b", r"\bstatus:", r"\bpre-review record\b", r"\bgap-analysis rule 25\b")
#: §S2.6 — `crucible`: the VERIFY agent's pre-review duty is when the CR meets a trigger.
CRUCIBLE_DUTY_TRIGGER = (
    r"\bspec pre-review\b", r"\bverify[- ]agent\b", r"\bwhen the cr meets a trigger\b",
    RULE_21_POINTER)

#: §S2 — every item, in its file: ``(name, rel, section prefix or None, rule)``.
S2_PINS = (
    ("model-b: the role row names the trigger", MODEL_B_REL, "## 2.", ROLE_ROW_TRIGGER),
    ("common: the design phase", COMMON_REL, "## Two-phase workflow", TWO_PHASE_DESIGN),
    ("common: the separate review", COMMON_REL, "## Gap-analysis discipline",
     GA_DISCIPLINE_SEPARATE + (RULE_21_POINTER,)),
    ("common: the design-review milestone", COMMON_REL, None, DESIGN_REVIEW_MILESTONE),
    ("common: older projects", COMMON_REL, None, OLDER_PROJECTS),
    ("common: the setup ordering", COMMON_REL, "## Cycle discipline", CYCLE_SETUP_ORDER),
    ("mainline: the gate's conditional", MAINLINE_REL, None, MAINLINE_GATE),
    ("mainline: the gate presents the record", MAINLINE_REL, None, MAINLINE_GATE_RECORD),
    ("track: the design-phase steps", TRACK_REL, None, TRACK_DESIGN_STEPS),
    ("track: the trigger decision and findings to mainline", TRACK_REL, None,
     TRACK_FINDINGS_TO_MAINLINE),
    ("track: the setup ordering", TRACK_REL, None, TRACK_SETUP_ORDER),
    ("cr-authoring: the design phase", CR_AUTHORING_REL, "## Two-phase workflow",
     TWO_PHASE_DESIGN),
    ("cr-authoring: the status carries the record", CR_AUTHORING_REL, None,
     CR_AUTHORING_STATUS_RECORD),
    ("crucible: the verify duty's trigger", CRUCIBLE_REL, "## Who runs what",
     CRUCIBLE_DUTY_TRIGGER),
)
#: The §S2 files: the restatement detector reads these.
S2_FILES = (MODEL_B_REL, COMMON_REL, MAINLINE_REL, TRACK_REL, CR_AUTHORING_REL, CRUCIBLE_REL)
#: The files §S1–§S2 list: the ordering guard reads these.
GUARD_FILES = (GAP_REL,) + S2_FILES

#: AC2 — Rule 21's trigger phrases and Rule 24's item phrases; a §S2 unit holding two or more
#: of either set restates the rule.
TRIGGER_PHRASES = (
    r"\b8 points or more\b",
    r"\ba contract, a hook or another project's surface\b",
    r"\ba ruling from the user\b",
)
CHECKLIST_PHRASES = (
    r"\bno test can meet or check\b",
    r"\bmissing failure path or edge case\b",
    r"\bgap in scope or design\b",
    r"\bconflict with the prd or a dn\b",
)
#: AC3 — the pre-review as a link of an arrow chain (`→` right before it, or right after it
#: or its parenthesis), or as the object of "dispatches / proceed to the (spec) pre-review".
PRE_REVIEW_LINK = re.compile(
    r"→\s*(?:the\s+)?(?:spec\s+)?pre-review\b"
    r"|\bpre-review\b\s*(?:\([^)]*\)\s*)?→"
    r"|\bdispatch(?:es)? the (?:spec )?pre-review\b"
    r"|\bproceed to the (?:spec )?pre-review\b")


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


# ------------------------------------------------- CR-MDB-096 reading ----

def numbered_rule_units(rules_body: str, number: int) -> list[str]:
    """The unit(s) that ARE numbered rule ``number`` of a "Rules" section: the item with its
    nested items and continuation lines, up to the first blank line."""
    return [u for u in units(rules_body) if u.startswith(f"{number}. ")]


def gap_candidates(text: str, where: str) -> list[str]:
    """The units of the ``gap-analysis`` skill text ``text`` a :data:`GAP_PINS` entry reads."""
    if where == "when to use":
        return units(section_body(text, "When to Use") or "")
    if where == "ready":
        return [u for u in units(section_body(text, "Verdicts:") or "")
                if re.match(READY_VERDICT, u)]
    return numbered_rule_units(section_body(text, "Rules") or "", int(where.split()[1]))


def gap_pin_findings(text: str) -> list[str]:
    """The name of every :data:`GAP_PINS` entry no unit of ``text`` meets, in table order."""
    return [name for name, where, rule in GAP_PINS
            if not any(all(re.search(p, u) for p in rule) for u in gap_candidates(text, where))]


def top_level_rule_numbers(rules_body: str) -> list[int]:
    """The number of every unindented numbered item of a "Rules" section, in file order."""
    return [int(m.group(1)) for m in re.finditer(r"(?m)^(\d+)\.\s", rules_body)]


def rules_not_one_block(rules_body: str, numbers: tuple) -> list[str]:
    """For each of ``numbers``: ``rule N: absent``, or ``rule N: a blank line inside`` when the
    rule's text goes on (an indented line) after a blank line, so it is two units, not one."""
    lines = rules_body.splitlines()
    out = []
    for n in numbers:
        start = next((i for i, ln in enumerate(lines) if re.match(rf"^{n}\.\s", ln)), None)
        if start is None:
            out.append(f"rule {n}: absent")
            continue
        for j in range(start + 1, len(lines)):
            if re.match(r"^\d+\.\s", lines[j]):
                break
            if lines[j].strip():
                continue
            following = next((ln for ln in lines[j + 1:] if ln.strip()), "")
            if following[:1].isspace():
                out.append(f"rule {n}: a blank line inside")
            break
    return out


def s2_pin_findings(texts: dict) -> list[str]:
    """The name of every :data:`S2_PINS` entry whose file (``texts[rel]``), or section of it,
    has no unit meeting its rule, in table order."""
    out = []
    for name, rel, prefix, rule in S2_PINS:
        text = texts.get(rel, "")
        if prefix:
            text = md_section(text, prefix)
        if not satisfying(text, rule):
            out.append(name)
    return out


def restates_the_rule(unit: str) -> bool:
    """AC2: a unit holding two or more of Rule 21's trigger phrases, or two or more of Rule 24's
    item phrases."""
    return (sum(1 for p in TRIGGER_PHRASES if re.search(p, unit)) >= 2
            or sum(1 for p in CHECKLIST_PHRASES if re.search(p, unit)) >= 2)


def restatements(texts: dict) -> list[str]:
    """``rel: unit`` for every unit of ``texts`` that restates the triggers or the checklist."""
    return [f"{rel}: {u[:200]!r}" for rel, text in texts.items() for u in units(text)
            if restates_the_rule(u)]


def unconditional_link(unit: str) -> bool:
    """AC3: the pre-review is a link of an arrow chain, or the object of "dispatches / proceed to
    the (spec) pre-review", and the unit carries no conditional."""
    return bool(PRE_REVIEW_LINK.search(unit)) and not re.search(GUARD_CONDITIONAL, unit)


def unconditional_links(texts: dict) -> list[str]:
    """``rel: unit`` for every unit of ``texts`` the ordering guard finds."""
    return [f"{rel}: {u[:200]!r}" for rel, text in texts.items() for u in units(text)
            if unconditional_link(u)]


def _real(rels: tuple) -> dict:
    return {rel: _read(rel) for rel in rels}


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

    def test_dimension_eight_names_no_memory_templates(self):
        # CR-MDB-060 §S4.2/AC5: the templates are gone; the stack skills carry the notes.
        body = dimension_body(_read(GAP_REL), 8)
        self.assertTrue(body.strip(), f"{GAP_REL}: no Dimension 8")
        self.assertEqual([m.group(0) for m in DIM8_RETIRED.finditer(body)], [],
                         f"CR-MDB-060 §S4.2/AC5: {GAP_REL} Dimension 8 names a memory template")

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

    def test_an_older_project_re_renders_its_agents_before_its_next_pre_review(self):
        # MIGRATED (CR-MDB-096 §S4.1): was ..._before_its_first_pre_review.
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
        # KEPT (CR-MDB-096 §S4.1): the no-trigger path is prose only, never an arrow chain.
        hits = [f"{rel}: {m.group(0)!r}" for rel, text in _ordering_surfaces()
                for m in OLD_ORDERING.finditer(text)]
        self.assertEqual(hits, [], "a shipped file states the ordering without the pre-review")


# ------------------- CR-MDB-096 §S1 — the triggers, the checklist and the record ----

class GapAnalysisTriggerRulesTest(unittest.TestCase):
    """CR-MDB-096 §S1 / AC1 / AC6: the `gap-analysis` skill states the rule once — § When to
    Use and READY carry the conditional, Rule 1 points to Rules 21, 22, 24 and 25, Rule 20 decides
    the triggers again, Rule 21 the triggers, Rule 24 the checklist, Rule 25 the record."""

    def _lacking(self, prefix: str) -> list[str]:
        return [n for n in gap_pin_findings(_read(GAP_REL)) if n.startswith(prefix)]

    def test_when_to_use_gives_the_ordering_with_the_trigger_conditional(self):
        self.assertEqual(self._lacking("when to use"), [], f"{GAP_REL} § When to Use")

    def test_ready_proceeds_to_the_pre_review_when_a_trigger_applies_else_to_approval(self):
        self.assertEqual(self._lacking("ready"), [], f"{GAP_REL} READY verdict")

    def test_rule_one_points_to_rules_21_22_24_and_25(self):
        self.assertEqual(self._lacking("rule 1:"), [], f"{GAP_REL} Rule 1")

    def test_rule_20_decides_the_triggers_again_and_a_fresh_pre_review_when_a_trigger_applies(self):
        self.assertEqual(self._lacking("rule 20:"), [], f"{GAP_REL} Rule 20")

    def test_rule_21_states_the_three_triggers_their_definitions_and_the_no_trigger_path(self):
        self.assertEqual(self._lacking("rule 21:"), [], f"{GAP_REL} Rule 21 (one unit)")

    def test_rule_24_states_the_four_checklist_items_and_folds_nothing_outside_them(self):
        self.assertEqual(self._lacking("rule 24:"), [], f"{GAP_REL} Rule 24 (one unit)")

    def test_rule_25_states_the_three_record_forms_and_the_records_lifecycle(self):
        self.assertEqual(self._lacking("rule 25:"), [], f"{GAP_REL} Rule 25 (one unit)")

    def test_the_rules_keep_numbers_one_to_23_and_append_24_and_25(self):
        body = section_body(_read(GAP_REL), "Rules") or ""
        self.assertEqual(top_level_rule_numbers(body), list(range(1, 26)),
                         f"{GAP_REL} § Rules: 1..25, each once, in order")

    def test_rules_21_24_and_25_are_each_one_block_with_no_blank_line_inside(self):
        body = section_body(_read(GAP_REL), "Rules") or ""
        self.assertEqual(rules_not_one_block(body, ONE_BLOCK_RULES), [], f"{GAP_REL} § Rules")

    def test_rules_22_and_23_are_unchanged(self):
        # Regression pin (passes today): §S1.6 — Rule 22 who and where, Rule 23 the re-score
        # and the split before the pre-review, each still under its number.
        body = section_body(_read(GAP_REL), "Rules") or ""
        twenty_two = numbered_rule_units(body, 22)
        twenty_three = numbered_rule_units(body, 23)
        self.assertEqual(len(twenty_two), 1, "exactly one Rule 22")
        self.assertEqual(len(twenty_three), 1, "exactly one Rule 23")
        self.assertTrue(all(re.search(p, twenty_two[0]) for p in RULE_WHO_AND_WHERE),
                        missing(twenty_two[0], RULE_WHO_AND_WHERE))
        self.assertRegex(twenty_three[0], r"^23\. re-score the cr\b")
        self.assertRegex(twenty_three[0], r"\babove 13 is split before the pre-review\b")


# ------------------------ CR-MDB-096 §S2 — the references follow the one home ----

class ReferencesFollowTheTriggerRuleTest(unittest.TestCase):
    """CR-MDB-096 §S2 / AC2 / AC6: each reference names the pre-review as conditional, in one
    unit, and none restates the triggers or the checklist."""

    def _lacking(self, prefix: str) -> list[str]:
        return [n for n in s2_pin_findings(_real(S2_FILES)) if n.startswith(prefix)]

    def test_model_b_role_row_reviews_one_drafted_spec_when_a_trigger_applies(self):
        self.assertEqual(self._lacking("model-b:"), [], f"{MODEL_B_REL} § 2")

    def test_orchestration_common_makes_every_pre_review_mention_conditional(self):
        self.assertEqual(self._lacking("common:"), [], COMMON_REL)

    def test_orchestration_mainline_gate_is_conditional_and_presents_the_record(self):
        self.assertEqual(self._lacking("mainline:"), [], MAINLINE_REL)

    def test_orchestration_track_steps_findings_and_ordering_are_conditional(self):
        self.assertEqual(self._lacking("track:"), [], TRACK_REL)

    def test_cr_authoring_design_phase_is_conditional_and_status_carries_the_record(self):
        self.assertEqual(self._lacking("cr-authoring:"), [], CR_AUTHORING_REL)

    def test_crucible_verify_duty_runs_when_the_cr_meets_a_trigger(self):
        self.assertEqual(self._lacking("crucible:"), [], f"{CRUCIBLE_REL} § Who runs what")

    def test_no_reference_restates_the_triggers_or_the_checklist(self):
        # Guard (passes today): the references point to Rule 21; none lists its triggers or
        # Rule 24's items.
        self.assertEqual(restatements(_real(S2_FILES)), [],
                         "a §S2 file restates gap-analysis Rule 21 or Rule 24")

    def test_the_real_units_holding_one_phrase_alone_are_not_restatements(self):
        # Must-pass samples (AC2; pass today): the scoring scale and another project's working
        # tree each look like a phrase of the rule, and are not one.
        samples = ((CR_AUTHORING_REL, r"\b1, 2, 3, 5, 8, 13\b"),
                   (CRUCIBLE_REL, r"\b1, 2, 3, 5, 8, 13\b"),
                   (MODEL_B_REL, r"\banother project's working tree\b"))
        for rel, sample in samples:
            with self.subTest(rel=rel, sample=sample):
                found = [u for u in units(_read(rel)) if re.search(sample, u)]
                self.assertEqual(len(found), 1, f"{rel}: exactly one unit holds {sample!r}")
                self.assertFalse(restates_the_rule(found[0]), found[0])


class PreReviewOrderingGuardTest(unittest.TestCase):
    """CR-MDB-096 AC3: in the files §S1–§S2 list, a unit linking the pre-review into an
    ordering, or dispatching / proceeding to it, carries the conditional."""

    maxDiff = None

    def test_every_pre_review_link_in_the_rule_files_carries_the_conditional(self):
        self.assertEqual(unconditional_links(_real(GUARD_FILES)), [],
                         "a unit orders the pre-review without `when a trigger applies`")

    def test_the_real_units_this_cr_leaves_alone_pass_the_guard(self):
        # Must-pass samples (AC3; pass today): Rule 23, the dispatch-description bullet, the
        # VERIFY-word bullet and crucible's identity bullet.
        rules = section_body(_read(GAP_REL), "Rules") or ""
        samples = (
            ("rule 23", numbered_rule_units(rules, 23), r"\bsplit before the pre-review\b"),
            ("dispatch description", units(_read(COMMON_REL)),
             r"\bname the cr id in every dispatch description\b.*\bexcept a spec pre-review\b"),
            ("verify word", units(_read(COMMON_REL)),
             r"\bmay run in the design phase in its spec pre-review mode\b"),
            ("crucible identity", units(_section(CRUCIBLE_REL, "## Identity")),
             r"\breviewing a drafted spec before approval\b"),
        )
        for name, candidates, phrase in samples:
            with self.subTest(sample=name):
                found = [u for u in candidates if re.search(phrase, u)]
                self.assertEqual(len(found), 1, f"exactly one {name} unit")
                self.assertFalse(unconditional_link(found[0]), found[0])


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
- the stack skills and their references, and everything the scaffold renders;
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
   analysis and a fresh pre-review when a trigger applies.
3. **The pre-review comes after the analysis, before approval.** The orchestrator dispatches it
   after its own analysis and before it locks and presents the spec, when a trigger applies. The
   findings are folded in
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
- **Design phase → `develop`.** Gap-analysis, then the spec pre-review when a trigger applies;
  spec/PRD/DN/queue edits.
- **Execution phase → feature branch.** RED+GREEN cycles, VERIFY, FIX, regression, merge.
- `VERIFY` names the execution phase only: the VERIFY agent may run in the design phase in its spec
  pre-review mode, and that step is called the pre-review, never "verify".

## Gap-analysis discipline (gap-analysis FIRST, before any branch/RED)
- **The orchestrator runs the gap analysis itself** (never delegate to a sub-agent).
- **The pre-review is a separate, dispatched review of the drafted spec**, after the analysis,
  when a trigger applies.
- **The dimensions and the verdicts live in the `gap-analysis` skill** — read it; they are not
  listed here.
- **A pre-review is a workflow moment:** when a pre-review ran, it posts a `design-review`
  milestone.
- **Older projects:** a project scaffolded before the pre-review's checklist re-renders its agents
  with `modelb-axi agents` before its next pre-review. A definition left alone as hand-modified is
  reported to the user.

## Cycle discipline
- Setup ordering: gap-analysis → pre-review (when a trigger applies) → approval → `plan-file` →
  THEN the branch / worktree.
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
- **Design→execution gate:** gap-analysis → pre-review when a trigger applies → fold its findings
  → lock the spec → present, with the pre-review record → WAIT for explicit approval → ONLY THEN
  cycle plan.
"""
OLD_MAINLINE = """\
- **Design→execution gate:** gap-analysis → lock the spec → present → WAIT for explicit approval → ONLY THEN cycle plan.
"""

GOOD_TRACK = """\
- **Design-phase steps (the gap analysis, the pre-review) happen before the worktree exists**, and
  everything from `worktree-flow start` on happens in it — RED / GREEN / VERIFY / builds.
- Setup ordering: spec → gap-analysis → pre-review (when a trigger applies) → present + get
  approval → `plan-file` → THEN `worktree-flow start` + dispatch.
- The pre-review runs in the main tree, read-only.
- A Track raises its trigger decision and its pre-review findings to Mainline, which folds them
  into the spec on develop.
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
        self.assertIsNone(DIM8_RETIRED.search(dimension_body(GOOD_GAP, 8)))
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
            # MIGRATED (CR-MDB-060 §S4.2): the bullet names the stack skills, not the templates.
            "classes": (8, DIM8_CLASSES,
                        "- the stack skills and their references, and everything the scaffold renders;\n",
                        ""),
            "stack-skills": (8, DIM8_CLASSES, "the stack skills and their references",
                             "the memory templates"),
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

    def test_the_retired_memory_template_detector_bites_on_the_old_bullet_and_spares_the_new(self):
        # CR-MDB-060 §S4.2: the pre-CR Dimension 8 bullet is found; the spec-worded one is not.
        old_body = dimension_body(GOOD_GAP.replace(
            "the stack skills and their references", "the memory templates"), 8)
        self.assertEqual([m.group(0) for m in DIM8_RETIRED.finditer(old_body)], ["memory templates"])
        self.assertEqual([m.group(0) for m in DIM8_RETIRED.finditer("a memory-template copy")],
                         ["memory-template"])
        self.assertIsNone(DIM8_RETIRED.search(dimension_body(GOOD_GAP, 8)))
        self.assertIsNone(DIM8_RETIRED.search("the agent templates; the project's memory"))

    def test_each_rules_detector_bites_when_its_phrase_is_changed(self):
        mutations = {
            "rescope": (RULE_RESCOPING, " and a fresh pre-review", ""),
            # MIGRATED (CR-MDB-096 §S4.1): each conditional bites too.
            "rescope trigger": (RULE_RESCOPING, "pre-review when a trigger applies.", "pre-review."),
            "order trigger": (RULE_PRE_REVIEW_ORDER, "the spec, when a trigger applies.",
                              "the spec."),
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
            "order": (CYCLE_SETUP_ORDER, "pre-review (when a trigger applies) → approval",
                      "approval → pre-review (when a trigger applies)"),
            # MIGRATED (CR-MDB-096 §S4.1): each pin's conditional bites.
            "design trigger": (TWO_PHASE_DESIGN, "pre-review when a trigger applies;",
                               "pre-review;"),
            "separate trigger": (GA_DISCIPLINE_SEPARATE, ",\n  when a trigger applies.", "."),
            "milestone ran": (DESIGN_REVIEW_MILESTONE, "when a pre-review ran, ", ""),
            "next": (RE_RENDER_OLDER, "before its next pre-review", "before its first pre-review"),
            "checklist": (RE_RENDER_OLDER, "the pre-review's checklist", "the pre-review mode"),
            "setup trigger": (CYCLE_SETUP_ORDER, " (when a trigger applies)", ""),
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
        # MIGRATED (CR-MDB-096 §S4.1): the conditional bites.
        no_trigger = GOOD_MAINLINE.replace(" when a trigger applies", "")
        self.assertEqual(satisfying(no_trigger, MAINLINE_GATE), [])
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
            satisfying(GOOD_TRACK.replace("folds them\n  into the spec on develop", "edits its spec"),
                       TRACK_FINDINGS_TO_MAINLINE), [])
        # MIGRATED (CR-MDB-096 §S4.1): the trigger decision and the conditional bite.
        self.assertEqual(satisfying(GOOD_TRACK.replace("its trigger decision and ", ""),
                                    TRACK_FINDINGS_TO_MAINLINE), [])
        self.assertEqual(satisfying(GOOD_TRACK.replace(" (when a trigger applies)", ""),
                                    TRACK_SETUP_ORDER), [])

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
  pre-review when a trigger applies; spec authoring, queue/PRD/DN updates. No feature branch.
"""
OLD_CR_AUTHORING = """\
## Two-phase workflow (universal) + where work commits
- **Design phase \u2192 the integration branch (`develop`/`main`).** Gap analysis, spec authoring, queue/PRD/DN updates. No feature branch.
"""
GOOD_COMMON_REACH = """\
- **A pre-review is a workflow moment:** the orchestrator posts a `design-review` milestone once it
  has folded the pre-review's findings into the spec \u2014 never the `report` agent.
- **Older projects:** a project scaffolded before the spec pre-review existed, or whose agents were
  rendered before the pre-review's checklist, first upgrades Model B to a release carrying the
  checklist — `modelb-axi agents` renders from the installed templates — then re-renders its
  agents with `modelb-axi agents` before its next pre-review. A definition left alone as
  hand-modified is reported to the user.
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
        # MIGRATED (CR-MDB-096 §S4.1): the conditional bites.
        ("cr-authoring trigger", GOOD_CR_AUTHORING, OLD_CR_AUTHORING, TWO_PHASE_DESIGN,
         " when a trigger applies", ""),
        ("who posts", GOOD_COMMON_REACH, OLD_COMMON_REACH, COMMON_WHO_POSTS,
         " \u2014 never the `report` agent", ""),
        ("upgrade", GOOD_COMMON_REACH, OLD_COMMON_REACH, COMMON_UPGRADE_FIRST,
         "first upgrades Model B to a release carrying the\n  checklist — ", ""),
        # MIGRATED (CR-MDB-096 §S4.1): `next`, not `first`; the release carries the checklist.
        ("upgrade next", GOOD_COMMON_REACH, OLD_COMMON_REACH, COMMON_UPGRADE_FIRST,
         "before its next pre-review", "before its first pre-review"),
        ("upgrade checklist", GOOD_COMMON_REACH, OLD_COMMON_REACH, COMMON_UPGRADE_FIRST,
         "carrying the\n  checklist", "carrying it"),
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


# ------------------------------- CR-MDB-096 detectors, synthetic text ----

#: The skill worded as CR-MDB-096 §S1 words it (abridged to the units the pins read).
GOOD_GAP_096 = """\
## When to Use

- After the spec is drafted, before its pre-review: the ordering is this analysis → the spec
  pre-review, when a trigger applies (Rule 21) → approval → `plan-file` → the feature branch or
  worktree → RED
- When a CR predates recent codebase changes

### Verdicts:

- **READY**: Spec is accurate, code matches PRD; proceed to the spec pre-review when a trigger
  applies (Rule 21), else to approval
- **BLOCKED**: Fundamental design issue, needs human decision

## Rules

1. **Never delegate this analysis to a sub-agent** — this is the orchestrator's responsibility.
   The spec pre-review (Rules 21, 22, 24 and 25) does not change that: it is a separate review of
   the drafted spec, not this analysis handed off.
2. **Never trust memory or summaries** — read the actual source code and PRDs
20. **Re-scoping reruns both steps** — a re-scoped spec gets a fresh gap analysis, which decides the
    triggers again, and a fresh pre-review when a trigger applies.
21. **The triggers** — the orchestrator dispatches the pre-review after its own analysis and before
    it locks and presents the spec, when at least one trigger applies:
    - the CR scores 8 points or more (the re-score of Rule 23);
    - it touches a contract, a hook or another project's surface:
      - a *contract* is a file under the project's `contracts/` or an interface its
        `AGENTS.md` names as a contract;
      - a *hook* is a hook script, the hook schema or compiled hook wiring;
      - *another project's surface* is a file, CLI, API or message format another project
        consumes or provides;
    - its gap analysis needed a ruling from the user.
    Any other spec goes from the analysis to approval. The findings a pre-review reports are folded
    in before locking.
22. **Who and where:**
    - **Id:** `CR-<ACRONYM>-NNN-SPEC-REVIEW`, the acronym taken from the nearest registry.
    - **Reviewer:** the VERIFY agent of a stack in that registry's `PROJECT_STACKS`.
    - **Where it runs:** read-only in the main tree.
23. **Re-score the CR** — a CR the analysis finds above 13 is split before the pre-review.
24. **The checklist** — a pre-review looks only for:
    - an acceptance criterion no test can meet or check;
    - a missing failure path or edge case;
    - a gap in scope or design;
    - a conflict with the PRD or a DN.
    Wording and naming are not findings, and the orchestrator folds in nothing outside this list.
25. **The record** — the spec's `**Status:**` line carries one of three forms:
    `Pre-review: due — <trigger>` (decided, not yet run), `Pre-review: ran — <trigger>` or
    `Pre-review: none — no trigger`.
    The orchestrator writes it when the analysis decides the triggers,
    moves `due` to `ran` when it folds the findings,
    and repeats it when it presents the spec for approval.
    A re-scoping (Rule 20) rewrites it.
    The close-out's `COMPLETED` flip keeps it.
    In multi mode a Track reports its decision to Mainline with its re-score, and Mainline
    records it on the spec.
"""

#: Today's (pre-CR-MDB-096) skill, abridged: no trigger, no checklist, no record.
TODAYS_GAP_096 = """\
## When to Use

- After the spec is drafted, before its pre-review: the ordering is this analysis → the spec
  pre-review → approval → `plan-file` → the feature branch or worktree → RED

### Verdicts:

- **READY**: Spec is accurate, code matches PRD; proceed to the spec pre-review (Rules 21–22)

## Rules

1. **Never delegate this analysis to a sub-agent** — this is the orchestrator's responsibility.
   The spec pre-review (Rules 21–22) does not change that: it is a separate review of the drafted
   spec, not this analysis handed off.
20. **Re-scoping reruns both steps** — a spec that is restructured or re-scoped gets a fresh gap
    analysis and a fresh pre-review. Findings against the old shape say nothing about the new one.
21. **The pre-review comes after the analysis, before approval** — the orchestrator dispatches the
    spec pre-review after its own analysis and before it locks and presents the spec. Its findings
    are folded into the spec before locking.
23. **Re-score the CR** — a CR the analysis finds above 13 is split before the pre-review.
"""

#: One cut per :data:`GAP_PINS` entry: ``name: (old, new)`` — each yields exactly its finding.
GAP_CUTS = {
    "when to use: the ordering carries the conditional":
        (", when a trigger applies (Rule 21) →", " →"),
    "ready: the pre-review when a trigger applies, else approval":
        (" when a trigger\n  applies (Rule 21), else to approval", ""),
    "rule 1: points to rules 21, 22, 24 and 25": ("Rules 21, 22, 24 and 25", "Rules 21–22"),
    "rule 20: a fresh pre-review when a trigger applies":
        ("a fresh pre-review when a trigger applies.", "a fresh pre-review."),
    "rule 20: the triggers decided again": (", which decides the\n    triggers again,", ","),
    "rule 21: dispatched when a trigger applies, folded before locking":
        (", when at least one trigger applies:", ":"),
    "rule 21: 8 points or more": ("8 points or more", "many points"),
    "rule 21: a contract, a hook or another project's surface":
        ("a contract, a hook or another project's surface:", "a protected file:"),
    "rule 21: a ruling from the user": ("a ruling from the user", "more time"),
    "rule 21: a contract is a file under contracts/ or an interface agents.md names":
        ("      - a *contract* is a file under the project's `contracts/` or an interface its\n"
         "        `AGENTS.md` names as a contract;\n", ""),
    "rule 21: a hook is a hook script, the hook schema or compiled hook wiring":
        ("      - a *hook* is a hook script, the hook schema or compiled hook wiring;\n", ""),
    "rule 21: a surface is a file, cli, api or message format another project consumes or "
    "provides":
        ("      - *another project's surface* is a file, CLI, API or message format another project\n"
         "        consumes or provides;\n", ""),
    "rule 21: any other spec goes from the analysis to approval":
        ("Any other spec goes from the analysis to approval. ", ""),
    "rule 24: a pre-review looks only for": ("a pre-review looks only for:", "a pre-review looks for:"),
    "rule 24: no test can meet or check":
        ("    - an acceptance criterion no test can meet or check;\n", ""),
    "rule 24: a missing failure path or edge case": ("    - a missing failure path or edge case;\n", ""),
    "rule 24: a gap in scope or design": ("    - a gap in scope or design;\n", ""),
    "rule 24: a conflict with the prd or a dn": ("    - a conflict with the PRD or a DN.\n", ""),
    "rule 24: wording and naming are not findings":
        ("Wording and naming are not findings, and the", "The"),
    "rule 24: folds in nothing outside": ("folds in nothing outside this list", "folds in what it likes"),
    "rule 25: on the status line": ("the spec's `**Status:**` line carries", "the spec carries"),
    "rule 25: due — decided, not yet run":
        ("`Pre-review: due — <trigger>` (decided, not yet run), ", ""),
    "rule 25: ran — <trigger>": ("`Pre-review: ran — <trigger>` or\n    ", ""),
    "rule 25: none — no trigger": (" or\n    `Pre-review: none — no trigger`", ""),
    "rule 25: written when the analysis decides the triggers":
        ("The orchestrator writes it when the analysis decides the triggers,\n    ", "The orchestrator "),
    "rule 25: due moves to ran at the fold":
        ("moves `due` to `ran` when it folds the findings,\n    and ", ""),
    "rule 25: repeated at approval":
        ("and repeats it when it presents the spec for approval.", "and stops."),
    "rule 25: a re-scoping rewrites it": ("A re-scoping (Rule 20) rewrites it.\n    ", ""),
    "rule 25: the completed flip keeps it": ("The close-out's `COMPLETED` flip keeps it.\n    ", ""),
    "rule 25: a track reports its decision to mainline, which records it":
        ("In multi mode a Track reports its decision to Mainline with its re-score, and Mainline\n"
         "    records it on the spec.", ""),
}


class GapAnalysisTriggerRuleDetectorTest(unittest.TestCase):
    """CR-MDB-096 AC1, proved on synthetic text: the spec-worded skill meets every pin, today's
    wording misses every one, and one cut of a spec phrase yields exactly its own finding."""

    def test_the_spec_worded_skill_meets_every_pin_and_passes_the_ordering_guard(self):
        self.assertEqual(gap_pin_findings(GOOD_GAP_096), [])
        rules = section_body(GOOD_GAP_096, "Rules") or ""
        self.assertEqual(top_level_rule_numbers(rules), [1, 2, 20, 21, 22, 23, 24, 25])
        self.assertEqual(rules_not_one_block(rules, ONE_BLOCK_RULES), [])
        self.assertEqual(unconditional_links({GAP_REL: GOOD_GAP_096}), [])

    def test_todays_skill_wording_misses_every_pin(self):
        self.assertEqual(gap_pin_findings(TODAYS_GAP_096), [name for name, _, _ in GAP_PINS])
        rules = section_body(TODAYS_GAP_096, "Rules") or ""
        self.assertEqual(rules_not_one_block(rules, ONE_BLOCK_RULES),
                         ["rule 24: absent", "rule 25: absent"])
        self.assertEqual(len(unconditional_links({GAP_REL: TODAYS_GAP_096})), 3)

    def test_every_pin_has_one_cut_and_each_cut_yields_exactly_its_finding(self):
        self.assertEqual(sorted(GAP_CUTS), sorted(name for name, _, _ in GAP_PINS))
        for name, (old, new) in GAP_CUTS.items():
            with self.subTest(pin=name):
                self.assertIn(old, GOOD_GAP_096)
                self.assertEqual(gap_pin_findings(GOOD_GAP_096.replace(old, new)), [name])

    def test_a_blank_line_inside_rule_21_splits_it_and_its_pins_bite(self):
        split = GOOD_GAP_096.replace("\n    Any other spec goes", "\n\n    Any other spec goes")
        rules = section_body(split, "Rules") or ""
        self.assertEqual(rules_not_one_block(rules, ONE_BLOCK_RULES), ["rule 21: a blank line inside"])
        self.assertEqual(gap_pin_findings(split),
                         ["rule 21: dispatched when a trigger applies, folded before locking",
                          "rule 21: any other spec goes from the analysis to approval"])

    def test_a_blank_line_between_two_rules_is_no_finding_and_an_absent_rule_is(self):
        body = "21. One rule,\n    one block.\n\n24. Another.\n\nA closing paragraph.\n"
        self.assertEqual(rules_not_one_block(body, (21, 24)), [])
        self.assertEqual(rules_not_one_block(body, (21, 25)), ["rule 25: absent"])

    def test_the_conditional_accepts_rule_21s_lead_and_rejects_a_bare_trigger(self):
        for good in ("when a trigger applies", "when at least one trigger applies"):
            with self.subTest(good=good):
                self.assertRegex(good, TRIGGER_APPLIES)
        for bad in ("when it applies", "a trigger applies", "when triggers apply"):
            with self.subTest(bad=bad):
                self.assertNotRegex(bad, TRIGGER_APPLIES)


#: The §S2 files worded as CR-MDB-096 §S2 words them (abridged to the units the pins read).
GOOD_S2 = {
    MODEL_B_REL: """\
## 2. Role hierarchy + labels

| Role | Scope | Authority |
|---|---|---|
| **Spec pre-review** (a VERIFY agent) | one drafted spec, before approval, when a trigger applies \
(`gap-analysis` Rule 21) | a `report` actor on the board, outside any cycle |

## 7. Operating rules (every role)

- **Never read another project's working tree without the user's permission.**
""",
    COMMON_REL: """\
## Two-phase workflow
- **Design phase → `develop`.** Gap-analysis, then the spec pre-review when a trigger applies;
  spec/PRD/DN edits. No feature branch.
- `VERIFY` names the EXECUTION phase only. The VERIFY *agent* may run in the design phase in its
  spec pre-review mode, and that step is called the pre-review, never "verify".

## Gap-analysis discipline
- **The orchestrator runs gap-analysis itself** (never delegate to a sub-agent).
- **The spec pre-review is separate:** a review of the drafted spec, dispatched when a trigger
  applies (`gap-analysis` Rule 21), run after the orchestrator's own analysis.
- **A pre-review is a workflow moment:** when a pre-review ran, the orchestrator posts a
  `design-review` milestone once it has folded the findings — never the `report` agent.
- **Older projects:** a project scaffolded before the spec pre-review existed, or whose agents were
  rendered before the pre-review's checklist, first upgrades Model B to a release carrying the
  checklist — `modelb-axi agents` renders from the installed templates — then re-renders its
  agents with `modelb-axi agents` before its next pre-review. A definition left alone as
  hand-modified is reported to the user.

## Cycle discipline
- Setup ordering: gap-analysis → pre-review (when a trigger applies) → approval → `plan-file` →
  THEN the branch / worktree.

## Worktree isolation
- Name the CR id in every dispatch description — except a spec pre-review, which runs in the
  main tree.
""",
    MAINLINE_REL: """\
- **Design→execution gate:** gap-analysis → pre-review when a trigger applies → fold its findings
  → lock the spec → present, with the pre-review record → WAIT for explicit approval → ONLY THEN
  cycle plan.
""",
    TRACK_REL: """\
- **Design-phase steps — the gap analysis and, when a trigger applies, the spec pre-review —
  happen before the worktree exists**; the pre-review runs in the main tree, read-only.
- **Raise your decision and findings to Mainline** — a Track raises its trigger decision and its
  pre-review findings to Mainline, which folds them into the spec on develop.
- Setup ordering: spec → gap-analysis → pre-review (when a trigger applies) → present + get
  approval → `plan-file` → THEN `worktree-flow start` + dispatch.
""",
    CR_AUTHORING_REL: """\
## Two-phase workflow (universal) + where work commits
- **Design phase → the integration branch.** Gap analysis, then the spec pre-review when a trigger
  applies; spec authoring, filing on the board. No feature branch.

## CR spec structure
1. **Front matter** — `**Status:**` (it carries the pre-review record, `gap-analysis` Rule 25),
   `**Type:**`, `**Priority:**`.

## The CR queue
- **Scoring:** the scale is 1, 2, 3, 5, 8, 13. 13 is the cap.
""",
    CRUCIBLE_REL: """\
## Identity
- Spec pre-review: `CR-<ACRONYM>-NNN-SPEC-REVIEW`. A VERIFY agent reviewing a drafted spec before
  approval registers as `--role report` with no cycle.

## Queue verbs
- **Story points:** `cr-plan` takes a story-point score on the scale 1, 2, 3, 5, 8, 13.

## Who runs what
- **VERIFY agent** — registers + REVIEWS. Does NOT run the regression.
  - Its spec pre-review (design phase, before `plan-file`) is a VERIFY-agent duty when the CR
    meets a trigger (`gap-analysis` Rule 21), with no runs and no ingest.
""",
}

#: One cut per :data:`S2_PINS` entry: ``name: (rel, old, new)`` — each yields exactly its finding.
S2_CUTS = {
    "model-b: the role row names the trigger":
        (MODEL_B_REL, ", when a trigger applies (`gap-analysis` Rule 21)", ""),
    "common: the design phase": (COMMON_REL, "pre-review when a trigger applies;", "pre-review;"),
    "common: the separate review":
        (COMMON_REL, ", dispatched when a trigger\n  applies (`gap-analysis` Rule 21)", ""),
    "common: the design-review milestone": (COMMON_REL, "when a pre-review ran, ", ""),
    "common: older projects":
        (COMMON_REL, "before its next pre-review", "before its first pre-review"),
    "common: the setup ordering":
        (COMMON_REL, "pre-review (when a trigger applies) → approval", "pre-review → approval"),
    "mainline: the gate's conditional":
        (MAINLINE_REL, "pre-review when a trigger applies →", "pre-review →"),
    "mainline: the gate presents the record":
        (MAINLINE_REL, "present, with the pre-review record →", "present →"),
    "track: the design-phase steps": (TRACK_REL, "and, when a trigger applies, the", "and the"),
    "track: the trigger decision and findings to mainline":
        (TRACK_REL, "its trigger decision and its", "its"),
    "track: the setup ordering":
        (TRACK_REL, "pre-review (when a trigger applies) → present", "pre-review → present"),
    "cr-authoring: the design phase":
        (CR_AUTHORING_REL, "pre-review when a trigger\n  applies;", "pre-review;"),
    "cr-authoring: the status carries the record":
        (CR_AUTHORING_REL, " (it carries the pre-review record, `gap-analysis` Rule 25)", ""),
    "crucible: the verify duty's trigger":
        (CRUCIBLE_REL, " when the CR\n    meets a trigger (`gap-analysis` Rule 21)", ""),
}


class ReferencesTriggerRuleDetectorTest(unittest.TestCase):
    """CR-MDB-096 AC2, proved on synthetic text: the spec-worded references meet every pin and one
    cut yields exactly its finding; the restatement detector both ways."""

    def test_the_spec_worded_references_meet_every_pin_restate_nothing_and_pass_the_guard(self):
        self.assertEqual(s2_pin_findings(GOOD_S2), [])
        self.assertEqual(restatements(GOOD_S2), [])
        self.assertEqual(unconditional_links(GOOD_S2), [])

    def test_every_pin_has_one_cut_and_each_cut_yields_exactly_its_finding(self):
        self.assertEqual(sorted(S2_CUTS), sorted(name for name, _, _, _ in S2_PINS))
        for name, (rel, old, new) in S2_CUTS.items():
            with self.subTest(pin=name):
                self.assertIn(old, GOOD_S2[rel])
                cut = dict(GOOD_S2, **{rel: GOOD_S2[rel].replace(old, new)})
                self.assertEqual(s2_pin_findings(cut), [name])

    def test_a_unit_holding_two_trigger_phrases_is_exactly_one_restatement(self):
        text = ("- A pre-review runs when the CR scores 8 points or more or needed a ruling from the "
                "user.\n- A CR of 8 points or more is re-scored.\n")
        self.assertEqual(len(restatements({"x.md": text})), 1)
        self.assertTrue(restatements({"x.md": text})[0].startswith("x.md: "))

    def test_a_unit_holding_two_checklist_phrases_is_exactly_one_restatement(self):
        text = ("- Report a gap in scope or design, or a conflict with the PRD or a DN.\n"
                "- A missing failure path or edge case is a finding.\n")
        self.assertEqual(len(restatements({"x.md": text})), 1)

    def test_a_nested_list_restating_the_triggers_is_one_finding_on_its_parent(self):
        text = ("- The pre-review runs when:\n  - the CR scores 8 points or more;\n"
                "  - it touches a contract, a hook or another project's surface;\n"
                "  - its gap analysis needed a ruling from the user.\n")
        found = restatements({"x.md": text})
        self.assertEqual(len(found), 1)
        self.assertIn("the pre-review runs when:", found[0])

    def test_one_phrase_alone_and_the_look_alikes_are_no_restatement(self):
        for unit in ("- the CR scores 8 points or more (gap-analysis Rule 21).\n",
                     "- The scale is 1, 2, 3, 5, 8, 13. 13 is the cap.\n",
                     "- Never read another project's working tree without permission.\n",
                     "- A missing failure path or edge case is a finding.\n"):
            with self.subTest(unit=unit):
                self.assertEqual(restatements({"x.md": unit}), [])


class PreReviewOrderingGuardDetectorTest(unittest.TestCase):
    """CR-MDB-096 AC3, proved on synthetic text: an ordering with the conditional passes, the same
    ordering without it yields exactly one finding naming its file, and a mere mention passes."""

    #: ``(name, unit with its conditional, the conditional to cut)``.
    LINKS = (
        ("arrow before", "- Setup ordering: gap-analysis → pre-review (when a trigger applies) → "
         "approval → `plan-file` → THEN the branch.\n", " (when a trigger applies)"),
        ("arrow before, bare", "- Gate: gap-analysis → pre-review when a trigger applies → fold its "
         "findings → lock the spec.\n", " when a trigger applies"),
        ("arrow after", "- The pre-review (when a trigger applies) → approval → `plan-file`.\n",
         " (when a trigger applies)"),
        ("dispatches", "21. The orchestrator dispatches the pre-review after its own analysis, when "
         "at least one trigger applies.\n", ", when at least one trigger applies"),
        ("dispatches the spec", "- It dispatches the spec pre-review when the CR meets a trigger.\n",
         " when the CR meets a trigger"),
        ("proceed to", "- **READY**: proceed to the spec pre-review when a trigger applies (Rule "
         "21), else to approval\n", " when a trigger applies (Rule 21), else to approval"),
    )
    #: Units in which the pre-review is mentioned, not ordered.
    MENTIONS = (
        "23. **Re-score the CR** — a CR above 13 is split before the pre-review.\n",
        "- Name the CR id in every dispatch description — except a spec pre-review, which runs in "
        "the main tree.\n",
        "- The VERIFY agent may run in the design phase in its spec pre-review mode.\n",
        "- A VERIFY agent reviewing a drafted spec before approval registers as report.\n",
        "- Design phase → `develop`. Gap-analysis, then the spec pre-review; spec edits.\n",
    )

    def test_an_ordering_with_its_conditional_passes(self):
        text = "".join(unit for _, unit, _ in self.LINKS)
        self.assertEqual(unconditional_links({"x.md": text}), [])

    def test_the_same_ordering_without_its_conditional_yields_exactly_one_finding(self):
        text = "".join(unit for _, unit, _ in self.LINKS)
        for name, unit, conditional in self.LINKS:
            with self.subTest(link=name):
                self.assertIn(conditional, unit)
                cut = text.replace(unit, unit.replace(conditional, ""))
                found = unconditional_links({"x.md": cut})
                self.assertEqual(len(found), 1, found)
                self.assertTrue(found[0].startswith("x.md: "), found[0])

    def test_a_mention_that_orders_nothing_passes(self):
        for unit in self.MENTIONS:
            with self.subTest(unit=unit):
                self.assertEqual(unconditional_links({"x.md": unit}), [])

    def test_todays_orderings_are_each_one_finding(self):
        # Today's orderings name the pre-review as an unconditional link: one finding per file.
        today = {COMMON_REL: "- Setup ordering: gap-analysis → pre-review → approval → `plan-file`.\n",
                 MAINLINE_REL: "- **Design→execution gate:** gap-analysis → pre-review → fold its "
                               "findings → lock the spec.\n",
                 TRACK_REL: "- Setup ordering: spec → gap-analysis → pre-review → present + get "
                            "approval.\n"}
        self.assertEqual([f.split(":")[0] for f in unconditional_links(today)],
                         [COMMON_REL, MAINLINE_REL, TRACK_REL])


#: CR-MDB-096 §S4.1 — each migrated pin and the conditional it requires in the same unit:
#: ``(name, rule, a unit meeting it, its conditional)``.
MIGRATED_CONDITIONALS = (
    ("ORDER_TO_PLAN_FILE", ORDER_TO_PLAN_FILE, "- gap-analysis → pre-review (when a trigger applies) → "
     "approval → `plan-file` → THEN the branch / worktree.\n", "(when a trigger applies) "),
    ("MAINLINE_GATE", MAINLINE_GATE, "- **Design→execution gate:** gap-analysis → pre-review when a "
     "trigger applies → fold its findings → lock the spec → present → WAIT for explicit approval → "
     "ONLY THEN cycle plan.\n", "when a trigger applies "),
    ("TRACK_SETUP_ORDER", TRACK_SETUP_ORDER, "- Setup ordering: spec → gap-analysis → pre-review (when "
     "a trigger applies) → present + get approval → `plan-file` → THEN `worktree-flow start` + "
     "dispatch.\n", "(when a trigger applies) "),
    ("TWO_PHASE_DESIGN", TWO_PHASE_DESIGN, "- **Design phase → `develop`.** Gap-analysis, then the "
     "spec pre-review when a trigger applies; spec edits.\n", " when a trigger applies"),
    ("RULE_PRE_REVIEW_ORDER", RULE_PRE_REVIEW_ORDER, "21. The orchestrator dispatches the "
     "pre-review after its own analysis and before it locks and presents the spec, when at least "
     "one trigger applies. The findings are folded in before locking.\n",
     ", when at least one trigger applies"),
    ("RULE_RESCOPING", RULE_RESCOPING, "20. **Re-scoping reruns both steps** — a re-scoped spec "
     "gets a fresh gap analysis and a fresh pre-review when a trigger applies.\n",
     " when a trigger applies"),
    ("GA_DISCIPLINE_SEPARATE", GA_DISCIPLINE_SEPARATE, "- **The spec pre-review is separate:** a "
     "review of the drafted spec, dispatched when a trigger applies (`gap-analysis` Rule 21).\n",
     " when a trigger applies"),
    ("DESIGN_REVIEW_MILESTONE", DESIGN_REVIEW_MILESTONE, "- **A pre-review is a workflow moment:** "
     "when a pre-review ran, the orchestrator posts a `design-review` milestone.\n",
     "when a pre-review ran, "),
    ("RE_RENDER_OLDER next", RE_RENDER_OLDER, "- **Older projects:** a project scaffolded before "
     "the spec pre-review existed, or whose agents were rendered before the pre-review's "
     "checklist, re-renders its agents with `modelb-axi agents` before its next pre-review. A "
     "definition left alone as hand-modified is reported to the user.\n",
     "before its next pre-review"),
    ("RE_RENDER_OLDER checklist", RE_RENDER_OLDER, "- **Older projects:** a project scaffolded "
     "before the spec pre-review existed, or whose agents were rendered before the pre-review's "
     "checklist, re-renders its agents with `modelb-axi agents` before its next pre-review. A "
     "definition left alone as hand-modified is reported to the user.\n",
     ", or whose agents were rendered before the pre-review's checklist"),
    ("COMMON_UPGRADE_FIRST next", COMMON_UPGRADE_FIRST, "- **Older projects:** first upgrades "
     "Model B to a release carrying the checklist — `modelb-axi agents` renders from the "
     "installed templates — then re-renders before its next pre-review.\n",
     "before its next pre-review"),
    ("COMMON_UPGRADE_FIRST checklist", COMMON_UPGRADE_FIRST, "- **Older projects:** first upgrades "
     "Model B to a release carrying the checklist — `modelb-axi agents` renders from the "
     "installed templates — then re-renders before its next pre-review.\n",
     "release carrying the checklist"),
    ("TRACK_FINDINGS_TO_MAINLINE", TRACK_FINDINGS_TO_MAINLINE, "- A Track raises its trigger "
     "decision and its pre-review findings to Mainline, which folds them into the spec on "
     "develop.\n", "its trigger decision and "),
)


class MigratedPinConditionalTest(unittest.TestCase):
    """CR-MDB-096 §S4.1: each migrated pin requires its conditional IN THE SAME UNIT — the
    unit with it passes; cut, or moved to a bullet of its own, it does not."""

    def test_each_migrated_pin_needs_its_conditional_in_the_same_unit(self):
        for name, rule, unit, conditional in MIGRATED_CONDITIONALS:
            with self.subTest(pin=name):
                self.assertEqual(len(satisfying(unit, rule)), 1, missing(unit, rule))
                self.assertIn(conditional, unit)
                cut = unit.replace(conditional, "")
                self.assertEqual(satisfying(cut, rule), [], "cut")
                moved = cut + f"- {conditional.strip(' ,')}.\n"
                self.assertEqual(satisfying(moved, rule), [], "moved to its own bullet")

    def test_the_old_first_pre_review_wording_no_longer_meets_the_older_project_pins(self):
        for rule in (RE_RENDER_OLDER, COMMON_UPGRADE_FIRST):
            with self.subTest(rule=rule[0]):
                unit = ("- **Older projects:** a project scaffolded before the pre-review's "
                        "checklist first upgrades Model B to a release carrying the checklist — "
                        "`modelb-axi agents` renders from the installed templates — then "
                        "re-renders its agents with `modelb-axi agents` before its first "
                        "pre-review. A definition left alone as hand-modified is reported to the "
                        "user.\n")
                self.assertEqual(satisfying(unit, rule), [])
                self.assertEqual(
                    len(satisfying(unit.replace("its first", "its next"), rule)), 1)


if __name__ == "__main__":
    unittest.main()
