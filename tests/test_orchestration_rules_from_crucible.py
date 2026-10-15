"""The orchestration rules adopted from Crucible's wave 7: the board through client verbs only,
story points, a brief that adds no proof steps, the pre-merge gate inside the last cycle, test
leaks, and release fixes, the test-hygiene CR and the gate's intent (CR-MDB-059 §S1–§S3,
§S5–§S7; PRD D5, AMENDED 2026-10-15).

Contract: ``docs/changes/CR-MDB-059-orchestration-rules-from-crucible-wave-7.md`` and its
acceptance criteria. §S4 (cycle labels, agent ids, the ``worktree-flow`` cycle field) is not
gated here.

The module is table-driven: ``SURFACES`` maps each shipped surface — a file and the region of it a
rule must sit in (a section, the intro, a numbered item, or the whole file) — to the rules §S
assigns it. A rule is carried when ONE unit of the region matches every pattern of the rule, on
normalised text (backticks and ``*`` dropped, whitespace collapsed, lower-cased). A unit is a
bullet or numbered item with its wrapped lines, a table row or a paragraph
(``tests.test_board_holds_the_queue.units``), or a lead ending in ``:`` together with the list it
introduces (``led_lists``: "Every other orchestrator run stays unbound:" and its three items).

Detector kinds, each proved both ways on synthetic text in ``DetectorsOnSyntheticTextTest``:

- ``rule_findings`` — the phrase gates of ``SURFACES``. Every surface's synthetic sample passes,
  and one cut per rule reports that rule alone; a rule moved out of its region is reported.
- ``order_findings`` — §S5's eight-step close-out order, searched step after step through the
  region, in ``orchestration-common.md`` § Close-out and in ``AGENTS.md`` § Workflow Rules.
- ``absence_findings`` — §S5: the ``crucible`` skill no longer says "verify cycle activated" or
  "LAST linked run".
- ``http_read_invitations`` — §S1: no sentence of the ``crucible`` skill invites reading the board
  over HTTP (an HTTP surface and an invitation, with no ``never``/``not``/"only through" and no
  "what the clients receive").
- ``cr_plan_points_findings`` — §S2: the ``crucible`` skill's queue-verbs ``cr-plan`` write-verb
  example carries ``--points <n>``.
- ``bare_leak_findings`` — §S6: a unit stating the test-leak rule says "test leak", never a bare
  "leak" (which already means a write outside the worktree).
- ``unexcepted_always_findings`` — §S5: wherever the ``shutdown`` skill says a shutdown ALWAYS
  finishes the plan's active cycle, the same unit carries the exception.

The ``crucible`` skill's stale-binding bullet (§S5) is gated where it always was,
``tests.test_ambient_manifest_discovery.CrucibleLifecycleRulesS5Test`` (migrated there).

Hermetic: reads repo files only. Stdlib only.
"""

import re
import unittest

from tests._helpers import REPO_ROOT, read_text
from tests.test_board_holds_the_queue import (
    CR_AUTHORING_QUEUE_HEADING,
    CR_CLOSE,
    MAINLINE_FILING_HEADING,
    _numbered_item,
    invocation_lines,
    norm_units,
    section,
    section_matching,
    units,
)
from tests.test_bootstrap_shutdown_registry import normalise

CRUCIBLE = "skills-src/crucible/SKILL.md"
COMMON = "skills-src/model-b/references/orchestration-common.md"
MAINLINE = "skills-src/model-b/references/orchestration-mainline.md"
PROCEDURE = "skills-src/model-b/references/sub-agent-procedure.md"
MODEL_B = "skills-src/model-b/SKILL.md"
CR_AUTHORING = "skills-src/cr-authoring/SKILL.md"
GAP_ANALYSIS = "skills-src/gap-analysis/SKILL.md"
SHUTDOWN = "skills-src/shutdown/SKILL.md"
GIT_WORKFLOW = "skills-src/git-workflow/SKILL.md"
AGENTS = "AGENTS.md"

COMMON_BRIEF_HEADING = "Never author code — dispatch with an accurate brief"
SHUTDOWN_GRACEFUL_HEADING = "Step 1A — GRACEFUL (default)"

_HEADING_LINE = re.compile(r"^#{1,6}\s")
_LIST_ITEM = re.compile(r"^(\s*)(?:[-*+]|\d+[.)])\s+")

#: A wave that has not drained (§S7: the hygiene CR keeps the wave from draining).
DRAIN = r"\b(?:has not|hasn't|not|never|does not|doesn't) (?:yet )?drain(?:ed)?\b"
#: The gate's intent: do not stop a server the gate did not start (§S7).
GATE_INTENT = r"\bintent\b[^.;]{0,40}\bnot (?:to )?stop any server\b[^.;]{0,20}\bdid not start\b"


# ------------------------------------------------------------------ regions ----

def intro(text: str) -> str:
    """The lines between the document's first heading and the next heading of any level."""
    out, started = [], False
    for line in text.splitlines():
        if _HEADING_LINE.match(line):
            if started:
                break
            started = True
            continue
        if started:
            out.append(line)
    return "\n".join(out)


def whole(text: str) -> str:
    return text


def crucible_envelope(text: str) -> str:
    return section_matching(text, r"^envelope\b")


def crucible_who_runs_what(text: str) -> str:
    return section_matching(text, r"^who runs what\b")


def crucible_queue_verbs(text: str) -> str:
    return section_matching(text, r"^queue verbs\b")


def common_brief(text: str) -> str:
    return section(text, COMMON_BRIEF_HEADING)


def common_close_out(text: str) -> str:
    return section(text, "Close-out")


def mainline_filing(text: str) -> str:
    return section(text, MAINLINE_FILING_HEADING)


def cr_authoring_queue(text: str) -> str:
    return section(text, CR_AUTHORING_QUEUE_HEADING)


def shutdown_graceful(text: str) -> str:
    return section(text, SHUTDOWN_GRACEFUL_HEADING)


def procedure_code_quality(text: str) -> str:
    return section(text, "Code quality")


def git_releases(text: str) -> str:
    return section_matching(text, r"^releases\b")


def model_b_item_5(text: str) -> str:
    return _numbered_item(section_matching(text, r"^4\. universal conventions"), 5)


def agents_workflow_rules(text: str) -> str:
    return section_matching(text, r"^workflow rules\b")


# ------------------------------------------------------------------ detectors ----

def led_lists(text: str) -> list[str]:
    """Each lead unit ending in ``:`` joined with the list items it introduces — the items
    deeper than the lead when the lead is itself an item, any items after a paragraph lead —
    normalised."""
    raw = units(text)
    out = []
    for i, unit in enumerate(raw):
        if not normalise(unit).endswith(":"):
            continue
        lead = _LIST_ITEM.match(unit)
        depth = len(lead.group(1)) if lead else -1
        items = []
        for nxt in raw[i + 1:]:
            item = _LIST_ITEM.match(nxt)
            if not item or len(item.group(1)) <= depth:
                break
            items.append(nxt)
        if items:
            out.append(normalise("\n".join([unit, *items])))
    return out


def rule_findings(region: str, rules) -> list[str]:
    """The name of each ``(name, patterns)`` rule no single unit of ``region`` states."""
    found = norm_units(region) + led_lists(region)
    return [name for name, patterns in rules
            if not any(all(re.search(p, u) for p in patterns) for u in found)]


def order_findings(region: str, steps) -> list[str]:
    """The first ``(name, regex)`` step not found after the step before it, searched through the
    normalised ``region``; ``[]`` when every step comes in order."""
    norm, pos = normalise(region), 0
    for n, (name, rx) in enumerate(steps, 1):
        match = re.compile(rx).search(norm, pos)
        if match is None:
            return [f"step {n} ({name}) is missing or out of order"]
        pos = match.end()
    return []


def absence_findings(text: str, forbidden) -> list[str]:
    """The name of each ``(name, regex)`` phrase the normalised ``text`` still carries."""
    norm = normalise(text)
    return [name for name, rx in forbidden if re.search(rx, norm)]


_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
HTTP_SURFACE = re.compile(r"\?fmt=toon|text/toon|\bgets?\b|\bhttp\b|/api/")
HTTP_INVITATION = re.compile(
    r"\bread (?:them|it)\b|\b(?:gets?|endpoints?|the api) (?:also )?serves?\b|\bover http\b")
HTTP_QUALIFIER = re.compile(r"\bnever\b|\bnot\b|\bonly through\b|\bclients? receives?\b")


def http_read_invitations(text: str) -> list[str]:
    """Each normalised sentence of ``text`` naming an HTTP read surface with an invitation to use
    it and no qualifier making it the clients' business."""
    return [s for u in norm_units(text) for s in _SENTENCE_SPLIT.split(u)
            if HTTP_SURFACE.search(s) and HTTP_INVITATION.search(s)
            and not HTTP_QUALIFIER.search(s)]


def cr_plan_points_findings(region: str) -> list[str]:
    """``[]`` when a ``cr-plan`` example in ``region`` (one code span) carries ``--points <n>``
    with ``--agent``."""
    if any("--points <n>" in span and "--agent" in span
           for _line, span in invocation_lines(region, "cr-plan")):
        return []
    return ["no cr-plan write-verb example carries --points <n>"]


BARE_LEAK = re.compile(r"(?<!test )(?<!test-)\bleak(?:s|ed|ing)?\b")


def bare_leak_findings(region: str) -> list[str]:
    """Each normalised unit of ``region`` that names a test leak and also says a bare "leak"."""
    return [u for u in norm_units(region) if "test leak" in u and BARE_LEAK.search(u)]


ALWAYS_FINISHES = re.compile(r"\balways finishes the plan'?s active cycle\b")


def unexcepted_always_findings(text: str) -> list[str]:
    """Each normalised unit saying a shutdown ALWAYS finishes the plan's active cycle with no
    ``except`` in the same unit."""
    return [u for u in norm_units(text)
            if ALWAYS_FINISHES.search(u) and not re.search(r"\bexcept\b", u)]


# ------------------------------------------------------------------ rules ----

#: §S1 — the ``crucible`` skill's widened opening sentence and its propose-a-verb step.
S1_CRUCIBLE_INTRO = (
    ("the orchestrator reads and writes the board only through client verbs, never the HTTP API",
     (r"\borchestrator\b", r"\breads? and writes?\b[^.;]{0,30}\bboard\b",
      r"\bonly through\b[^.;]{0,20}\bclient verbs?\b", r"\bnever\b[^.;]{0,20}\bhttp api\b")),
    ("where no verb fits, it says so and proposes one to Crucible",
     (r"\bno verb fits\b", r"\bsays so\b", r"\bpropos\w*\b[^.;]{0,30}\bcrucible\b")),
)
#: §S1 — the envelope section describes what the clients receive.
S1_CRUCIBLE_ENVELOPE = (
    ("the board's TOON replies are described as what the clients receive",
     (r"\btoon\b", r"\bclients?\b[^.;]{0,30}\breceives?\b")),
)
#: §S1 — ``orchestration-common.md`` states the same rule.
S1_COMMON = (
    ("the board is read and written only through client verbs, never the HTTP API",
     (r"\breads? and writes?\b[^.;]{0,30}\bboard\b",
      r"\bonly through\b[^.;]{0,20}\bclient verbs?\b", r"\bnever\b[^.;]{0,20}\bhttp api\b")),
    ("where no verb fits, it says so and proposes one to Crucible",
     (r"\bno verb fits\b", r"\bsays so\b", r"\bpropos\w*\b[^.;]{0,30}\bcrucible\b")),
)

#: §S2 — ``cr-authoring``'s filing rules (its queue section).
S2_CR_AUTHORING = (
    ("every CR is scored when filed, with cr-plan --points or plan-file --release … --points",
     (r"\bevery cr\b[^.;]{0,10}\bscored when (?:it is )?filed\b", r"cr-plan --points\b",
      r"plan-file --release\b[^.;()]{0,20}--points\b")),
    ("the scale is 1, 2, 3, 5, 8, 13",
     (r"\bscale\b", r"\b1,\s?2,\s?3,\s?5,\s?8,\s?13\b")),
    ("13 is the cap, and a CR scoring more is split before it is filed",
     (r"\b13 is the cap\b|\bcap is 13\b|\bcapped at 13\b",
      r"\bsplit\b[^.;]{0,20}\bbefore it is filed\b")),
    ("the legacy-filing path (a project scaffolded before the board held the queue) scores each "
     "CR it files",
     (r"scaffolded before|older project", r"\bscor(?:e|es|ed|ing)\b")),
)
#: §S2 — the ``gap-analysis`` skill re-scores, splits, and routes a Track's re-score to Mainline.
S2_GAP_ANALYSIS = (
    ("the analysis re-scores the CR with cr-plan --points, re-sending its title, release and wave",
     (r"\bre-?scores?\b", r"cr-plan --points\b",
      r"\bre-?send\w*\b[^.;]{0,20}\btitle,? release,? and wave\b")),
    ("a CR found above 13 is split before the pre-review",
     (r"\babove 13\b|\bover 13\b|\bmore than 13\b",
      r"\bsplit\b[^.;]{0,20}\bbefore the (?:spec )?pre-review\b")),
    ("in multi mode a Track raises the re-score or split to Mainline, which runs cr-plan and files "
     "the split CRs",
     (r"\bmulti\b", r"\btrack raises\b[^.;]{0,40}\bto mainline\b",
      r"\bmainline\b[^.;]{0,20}\bruns cr-plan\b", r"\bfiles the split crs\b")),
)
#: §S2 — ``orchestration-mainline.md``'s filing order names the score in ``cr-plan``.
S2_MAINLINE = (
    ("the filing order names the score in cr-plan",
     (r"\bwrite the spec\b", r"\bfile (?:it )?on the board\b",
      r"cr-plan(?: --points\b|[^,;)]{0,30}\b(?:score|points)\b)")),
)

#: §S3 — ``orchestration-common.md``'s brief rules.
S3_COMMON = (
    ("a brief states the scope, the approved spec (the spec wins) and the definition's standard "
     "procedure",
     (r"\bbrief\b", r"\bscope\b", r"\bapproved spec\b", r"\bthe spec wins\b",
      r"\bstandard procedure\b")),
    ("the orchestrator adds no extra proof steps, because VERIFY and the gate catch drift",
     (r"\bno extra proof steps\b", r"\bverify\b[^.;]{0,20}\bgate\b[^.;]{0,10}\bcatch(?:es)? drift\b")),
)

#: §S5 — ``orchestration-common.md`` § Close-out: the binding mechanics, the two loops back into a
#: fix cycle, and the unbound list.
S5_COMMON_CLOSE_OUT = (
    ("the last cycle is the VERIFY cycle, or the last fix cycle appended after it",
     (r"\bverify cycle\b", r"\blast fix cycle\b[^.;]{0,10}\bappended after\b")),
    ("the gate runs under the orchestrator's own id, bound to that cycle",
     (r"\bgate runs under the orchestrator'?s own id\b", r"\bbound to\b")),
    ("--cycle <last cycle> is passed on the gate's first run",
     (r"--cycle <last cycle>", r"\bfirst run\b")),
    ("where the verb takes no --cycle, register --role ORCHESTRATOR --cycle <last> first",
     (r"\btakes no --cycle\b", r"register --role orchestrator --cycle <last>")),
    ("later runs inherit the binding",
     (r"\blater runs inherit the binding\b",)),
    ("a red gate is ingested, then cycle-done closes the cycle with it",
     (r"\bred gate\b", r"\bingested\b", r"(?<![\w-])cycle-done closes the cycle\b")),
    ("a fix cycle is appended with cycle-add --kind fix, and the gate runs again inside that new "
     "last cycle",
     (r"cycle-add --kind fix\b", r"\bgate runs again\b", r"\bnew last cycle\b")),
    ("a sign-off that sends changes back after cycle-done follows the same path",
     (r"\bsign-off that sends changes back\b", r"\bafter cycle-done\b", r"\bsame path\b")),
    ("every other orchestrator run stays unbound: baselines, the post-merge develop gate, the "
     "release's own verification gate under --release",
     (r"\bevery other orchestrator run stays unbound\b", r"\bbaselines\b",
      r"\bpost-merge develop gate\b", r"\brelease'?s own verification gate\b",
      r"(?<![\w-])--release(?![\w-])")),
)
#: §S5 — the close-out order, step after step (normalised text).
CLOSE_OUT_ORDER = (
    ("merge develop into the feature branch until behind=0",
     r"\bmerge develop into the feature branch\b[^.;]{0,30}\bbehind\s?=\s?0\b"),
    ("the pre-merge gate while the plan's last cycle is still active",
     r"\bpre-merge gate\b[^.;]{0,80}\blast cycle\b"),
    ("cycle-done", r"(?<![\w-])cycle-done(?![\w-])"),
    ("unregister, then register", r"(?<![\w-])unregister,?\s+then,?\s+register(?![\w-])"),
    ("the merge sign-off", r"\bsign-off\b"),
    ("the spec's **Status:** flip", r"\bstatus:"),
    ("the merge", r"\bmerge\b"),
    ("cr-close", CR_CLOSE),
)
#: §S5 — the ``crucible`` skill's "Who runs what" ORCHESTRATOR bullet.
S5_CRUCIBLE_WHO = (
    ("the ORCHESTRATOR bullet: the gate runs in the plan's last cycle, bound with --cycle",
     (r"^- orchestrator\b", r"\bgate\b", r"\bplan'?s last cycle\b",
      r"\bbound with --cycle\b")),
)
#: §S5 — what the ``crucible`` skill no longer says.
S5_CRUCIBLE_RETIRED = (
    ("'verify cycle activated'", r"\bverify cycle activated\b"),
    ("'LAST linked run'", r"\blast linked run\b"),
)
#: §S5 — the ``shutdown`` skill's graceful-mode exception.
S5_SHUTDOWN = (
    ("a graceful shutdown finishes the plan's active cycle, except the last one whose pre-merge "
     "gate has not run, which stays active and is reported as \"awaiting the pre-merge gate\"",
     (r"\bfinish(?:es)? the plan'?s active cycle\b", r"\bexcept\b[^.;]{0,40}\blast (?:one|cycle)\b",
      r"\bpre-merge gate has not run\b", r"\bstays active\b", r"\bawaiting the pre-merge gate\b")),
)

#: §S6 — the test-leak rule, in ``sub-agent-procedure.md`` § Code quality and in
#: ``orchestration-common.md``.
S6_TEST_LEAK = (
    ("a test leak is state one test leaves for another: an environment variable, a stub, a global",
     (r"\btest leak\b", r"\bone test leaves for another\b", r"\benvironment variable\b",
      r"\bstub\b", r"\bglobal\b")),
    ("a test leak is fixed at its source, never in the tests it breaks",
     (r"\btest leak\b", r"\bfixed at (?:its|the) source\b", r"\bnever in the tests it breaks\b")),
)

#: §S7 — ``git-workflow`` § Releases.
S7_GIT_RELEASES = (
    ("a failure the release's own verification finds is fixed by a CR filed into that release, "
     "with a plan and cycle-bound agents",
     (r"\brelease'?s own verification\b", r"\brehearsal\b", r"\bregression\b", r"\bgate\b",
      r"\bcr filed into (?:that|the) release\b", r"\bwith a plan\b", r"\bcycle-bound agents\b")),
    ("the release fix commits directly on the release branch, never on a separate bugfix branch, "
     "and reaches develop at finish",
     (r"\bdirectly on the release branch\b", r"\bnever on a separate bugfix branch\b",
      r"\breaches develop at finish\b")),
    ("its runs are cycle runs", (r"\bits runs are cycle runs\b",)),
    ("its cr-close takes the fix's last commit on the release branch",
     (r"(?<![\w-])cr-close\b[^.;]{0,20}\blast commit on the release branch\b",)),
    ("the release's own regression and pre-merge-gate stay --release runs from an unbound id",
     (r"\bregression\b", r"\bpre-merge-gate\b", r"--release runs?\b", r"\bunbound id\b")),
    ("'highly discouraged' applies to new, unplanned work; a release fix is the rule and needs no "
     "extra approval",
     (r"\bhighly discouraged\b", r"\bnew,? unplanned work\b", r"\brelease fix is the rule\b",
      r"\bno extra approval\b")),
    ("unchanged: fix a real failure on a hotfix branch",
     (r"\bfix a real failure on a hotfix branch\b",)),
    ("every release carries a test-hygiene CR, sequenced last in the release's final wave",
     (r"\bevery release carries a test-hygiene cr\b", r"\blast in the release'?s final wave\b")),
    ("because it is last, the wave has not drained while it is open, so the release does not start",
     (r"\bit is last\b", DRAIN, r"\brelease does not start\b")),
    ("the hygiene CR sweeps analyzer findings, flaky, slow or network-bound tests, skip reasons, "
     "duplicated helpers and the hygiene notes the release's CRs deferred",
     (r"\bsweeps\b", r"\banalyzer findings\b", r"\bflaky\b", r"\bslow\b", r"\bnetwork-bound\b",
      r"\bskip reasons\b", r"\bduplicated helpers\b", r"\bhygiene notes\b[^.;]{0,40}\bdeferred\b")),
    ("no dependency edge is added; CRs stay non-gates",
     (r"\bno dependency edge\b", r"\bnon-gates\b")),
)
#: §S7 — ``model-b`` SKILL §4.5 states the hygiene-CR rule, worded as the drain.
S7_MODEL_B = (
    ("§4.5: the test-hygiene CR, last in the final wave, keeps the wave from draining",
     (r"\btest-hygiene cr\b", r"\blast\b[^.;]{0,30}\bfinal wave\b", DRAIN)),
)
#: §S7 — ``cr-authoring``'s "A release is NOT a CR" bullet names it as work the release needs.
S7_CR_AUTHORING = (
    ("the release bullet names the test-hygiene CR, last in the final wave, as work the release "
     "needs, worded as the drain",
     (r"^- a release is not a cr\b", r"\bwork the release (?:genuinely )?needs\b",
      r"\btest-hygiene cr\b", r"\blast\b[^.;]{0,30}\bfinal wave\b", DRAIN)),
)
#: §S7 — the gate's intent in the ``crucible`` skill's ``gate-run`` text.
S7_CRUCIBLE_GATE = (
    ("the gate-run text: the intent tells the gate not to stop any server it did not start",
     (r"gate-run\b", GATE_INTENT)),
)
#: §S7 — ``AGENTS.md``'s wave-gate line.
S7_AGENTS_GATE = (
    ("the wave-boundary gate line: the intent tells the gate not to stop any server it did not "
     "start",
     (r"^- wave-boundary gate:", GATE_INTENT)),
)

#: Every phrase gate: ``key -> (file, region, rules)``.
SURFACES = {
    "S1 crucible intro": (CRUCIBLE, intro, S1_CRUCIBLE_INTRO),
    "S1 crucible envelope": (CRUCIBLE, crucible_envelope, S1_CRUCIBLE_ENVELOPE),
    "S1 orchestration-common": (COMMON, whole, S1_COMMON),
    "S2 cr-authoring": (CR_AUTHORING, cr_authoring_queue, S2_CR_AUTHORING),
    "S2 gap-analysis": (GAP_ANALYSIS, whole, S2_GAP_ANALYSIS),
    "S2 orchestration-mainline": (MAINLINE, mainline_filing, S2_MAINLINE),
    "S3 orchestration-common": (COMMON, common_brief, S3_COMMON),
    "S5 orchestration-common close-out": (COMMON, common_close_out, S5_COMMON_CLOSE_OUT),
    "S5 crucible who runs what": (CRUCIBLE, crucible_who_runs_what, S5_CRUCIBLE_WHO),
    "S5 shutdown": (SHUTDOWN, shutdown_graceful, S5_SHUTDOWN),
    "S6 sub-agent-procedure": (PROCEDURE, procedure_code_quality, S6_TEST_LEAK),
    "S6 orchestration-common": (COMMON, whole, S6_TEST_LEAK),
    "S7 git-workflow": (GIT_WORKFLOW, git_releases, S7_GIT_RELEASES),
    "S7 model-b 4.5": (MODEL_B, model_b_item_5, S7_MODEL_B),
    "S7 cr-authoring": (CR_AUTHORING, cr_authoring_queue, S7_CR_AUTHORING),
    "S7 crucible gate-run": (CRUCIBLE, whole, S7_CRUCIBLE_GATE),
    "S7 AGENTS.md": (AGENTS, agents_workflow_rules, S7_AGENTS_GATE),
}


def surface_findings(key: str, text: str | None = None) -> list[str]:
    """What the surface ``key`` lacks: its region, or each rule its region does not state.
    ``text`` stands in for the file (the synthetic proofs)."""
    rel, region_of, rules = SURFACES[key]
    region = region_of(read_text(REPO_ROOT / rel) if text is None else text)
    if not region.strip():
        return [f"{rel}: no {region_of.__name__} region"] + [name for name, _ in rules]
    return rule_findings(region, rules)


# ------------------------------------------------------------------ shipped surfaces ----

class BoardThroughClientVerbsTest(unittest.TestCase):
    """§S1 — the board is read and written through client verbs only."""

    maxDiff = None

    def test_the_crucible_skill_opening_widens_to_client_verbs_and_proposing_a_verb(self):
        self.assertEqual(surface_findings("S1 crucible intro"), [])

    def test_the_crucible_envelope_section_describes_what_the_clients_receive(self):
        self.assertEqual(surface_findings("S1 crucible envelope"), [])

    def test_the_crucible_skill_never_invites_reading_the_board_over_http(self):
        self.assertEqual(http_read_invitations(read_text(REPO_ROOT / CRUCIBLE)), [])

    def test_orchestration_common_states_the_client_verbs_rule(self):
        self.assertEqual(surface_findings("S1 orchestration-common"), [])


class StoryPointsTest(unittest.TestCase):
    """§S2 — one gate per surface, each pinning what §S2 assigns it."""

    maxDiff = None

    def test_cr_authoring_scores_every_cr_at_filing_on_the_scale_with_the_13_cap(self):
        self.assertEqual(surface_findings("S2 cr-authoring"), [])

    def test_gap_analysis_re_scores_splits_before_the_pre_review_and_routes_a_track_to_mainline(self):
        self.assertEqual(surface_findings("S2 gap-analysis"), [])

    def test_orchestration_mainline_filing_order_names_the_score_in_cr_plan(self):
        self.assertEqual(surface_findings("S2 orchestration-mainline"), [])

    def test_the_crucible_skill_cr_plan_example_carries_points(self):
        region = crucible_queue_verbs(read_text(REPO_ROOT / CRUCIBLE))
        self.assertTrue(region.strip(), "precondition: the crucible skill has a queue-verbs section")
        self.assertEqual(cr_plan_points_findings(region), [])


class BriefAddsNoProofStepsTest(unittest.TestCase):
    """§S3 — ``orchestration-common.md``'s brief rules."""

    maxDiff = None

    def test_the_brief_states_scope_spec_and_procedure_and_adds_no_proof_steps(self):
        self.assertEqual(surface_findings("S3 orchestration-common"), [])


class PreMergeGateInsideTheLastCycleTest(unittest.TestCase):
    """§S5 — the pre-merge gate runs inside the last cycle."""

    maxDiff = None

    def test_orchestration_common_close_out_states_the_eight_step_order(self):
        region = common_close_out(read_text(REPO_ROOT / COMMON))
        self.assertTrue(region.strip(), "precondition: orchestration-common has § Close-out")
        self.assertEqual(order_findings(region, CLOSE_OUT_ORDER), [])

    def test_orchestration_common_close_out_states_binding_loops_and_the_unbound_list(self):
        self.assertEqual(surface_findings("S5 orchestration-common close-out"), [])

    def test_the_crucible_orchestrator_bullet_runs_the_gate_in_the_last_cycle(self):
        self.assertEqual(surface_findings("S5 crucible who runs what"), [])

    def test_the_crucible_skill_no_longer_says_verify_cycle_activated_or_last_linked_run(self):
        self.assertEqual(absence_findings(read_text(REPO_ROOT / CRUCIBLE), S5_CRUCIBLE_RETIRED), [])

    def test_the_shutdown_graceful_mode_keeps_the_last_cycle_awaiting_the_pre_merge_gate(self):
        self.assertEqual(surface_findings("S5 shutdown"), [])

    def test_no_shutdown_unit_says_always_finishes_the_active_cycle_without_the_exception(self):
        self.assertEqual(unexcepted_always_findings(read_text(REPO_ROOT / SHUTDOWN)), [])

    def test_agents_md_workflow_rules_state_the_close_out_order(self):
        region = agents_workflow_rules(read_text(REPO_ROOT / AGENTS))
        self.assertTrue(region.strip(), "precondition: AGENTS.md has § Workflow Rules")
        self.assertEqual(order_findings(region, CLOSE_OUT_ORDER), [])


class TestLeakRuleTest(unittest.TestCase):
    """§S6 — a test leak is fixed at its source."""

    maxDiff = None

    def test_sub_agent_procedure_code_quality_states_the_test_leak_rule(self):
        self.assertEqual(surface_findings("S6 sub-agent-procedure"), [])

    def test_orchestration_common_states_the_test_leak_rule(self):
        self.assertEqual(surface_findings("S6 orchestration-common"), [])

    def test_the_test_leak_rule_never_says_a_bare_leak(self):
        found = (bare_leak_findings(procedure_code_quality(read_text(REPO_ROOT / PROCEDURE)))
                 + bare_leak_findings(read_text(REPO_ROOT / COMMON)))
        self.assertEqual(found, [])


class ReleasesAndTheGateTest(unittest.TestCase):
    """§S7 — release fixes, the test-hygiene CR and the gate's intent."""

    maxDiff = None

    def test_git_workflow_releases_states_the_release_fix_cr_and_the_hygiene_cr(self):
        self.assertEqual(surface_findings("S7 git-workflow"), [])

    def test_git_workflow_releases_keeps_the_hotfix_sentence(self):
        rules = [r for r in S7_GIT_RELEASES if r[0].startswith("unchanged:")]
        self.assertEqual(len(rules), 1)
        self.assertEqual(rule_findings(git_releases(read_text(REPO_ROOT / GIT_WORKFLOW)), rules), [])

    def test_model_b_section_4_5_states_the_hygiene_cr_as_the_drain(self):
        self.assertEqual(surface_findings("S7 model-b 4.5"), [])

    def test_cr_authoring_release_bullet_names_the_hygiene_cr(self):
        self.assertEqual(surface_findings("S7 cr-authoring"), [])

    def test_the_crucible_gate_run_text_says_the_intent_spares_servers_it_did_not_start(self):
        self.assertEqual(surface_findings("S7 crucible gate-run"), [])

    def test_agents_md_wave_gate_line_says_the_intent_spares_servers_it_did_not_start(self):
        self.assertEqual(surface_findings("S7 AGENTS.md"), [])


# ------------------------------------------------------------------ synthetic proofs ----

GOOD_CRUCIBLE = """---
name: crucible
description: x
---

# Crucible — agent lifecycle + test ingest

The client runs the tests AND ingests in one call under your agent id. Never hand-roll `curl`: the orchestrator reads and writes the board only through client verbs, never the HTTP API. Where no verb fits, it says so and proposes one to Crucible.

## Workflow classification

- **Gate verb — `gate-run`.** `gate-run --intent <goal> --agent <id>` streams the pipeline; the intent tells the gate not to stop any server it did not start.

## Queue verbs — the board holds the queue

- **Write verbs are the orchestrator's only:**
  - `cr-plan --cr <id> --title <t> --release <label> --wave <w> --points <n> --agent <id>` records the CR's title, release, wave and score.

## Envelope — TOON-AXI on stdout (shipped fleet-wide)

Every client verb emits one TOON envelope on stdout. The board answers in compact TOON with `help` hints naming the next step: that is what the clients receive.

## Who runs what (roles — the boundary the output can't tell you)

- **ORCHESTRATOR** — runs the pre-merge gate itself, in the plan's last cycle, bound with `--cycle`, under its own identity — then the user-gated merge.
"""

GOOD_COMMON = """# Orchestration — COMMON

## Cycle discipline
- The orchestrator reads and writes the board only through client verbs, never the HTTP API; where no verb fits, it says so and proposes one to Crucible.
- **A test leak** — state one test leaves for another: an environment variable, a stub, a global — is fixed at its source, never in the tests it breaks.

## Never author code — dispatch with an accurate brief
- **A brief states the scope, the approved spec (the spec wins) and the definition's standard procedure.** The orchestrator adds no extra proof steps, because VERIFY and the gate catch drift.

## Close-out
The CR's close-out order:

1. Merge `develop` into the feature branch until behind=0.
2. Run the pre-merge gate while the plan's last cycle is still active. That cycle is the VERIFY cycle, or the last `fix` cycle appended after it. The gate runs under the orchestrator's own id, bound to that cycle:
   - pass `--cycle <last cycle>` on the gate's first run;
   - where that verb takes no `--cycle`, first `register --role ORCHESTRATOR --cycle <last>`;
   - later runs inherit the binding.
3. `cycle-done`.
4. `unregister`, then `register`, of the orchestrator, which clears the binding.
5. The merge sign-off.
6. The spec's `**Status:**` flip, a docs-only commit and still the last commit on the branch.
7. The merge.
8. `cr-close`.

Two loops back into a fix cycle:

- **A red gate** is ingested, then `cycle-done` closes the cycle with it. A `fix` cycle is appended (`cycle-add --kind fix`), and the gate runs again inside that new last cycle.
- **A sign-off that sends changes back** after `cycle-done` follows the same path.

Every other orchestrator run stays unbound:

- baselines;
- the post-merge develop gate;
- the release's own verification gate, which runs under `--release`.

## Investigation discipline
- Read the actual errors first.
"""

GOOD_MAINLINE = """# Orchestration — MAINLINE

## Filing/assigning a CR — COMMIT docs FIRST, schedule write LAST
- Order: write the spec → `git commit` to `develop` → THEN file it on the board (`cr-plan --points <n>`, `cr-depends`, `wave-sequence`) and assign the lane.
"""

GOOD_CR_AUTHORING = """# CR / PRD / DN Authoring

## The CR queue — structure only (queue idiom, 2026-07-20)
- **Scoring:** every CR is scored when filed (`cr-plan --points`, or `plan-file --release … --points`), on the scale 1, 2, 3, 5, 8, 13. 13 is the cap; a CR scoring more is split before it is filed.
- **A release is NOT a CR.** A release is a boundary event: the wave carrying it drains its queue on the board. Work the release genuinely needs is an ordinary CR in the wave, among it every release's test-hygiene CR, sequenced last in the final wave, so the wave has not drained while it is open.
- **A project scaffolded before the board held the queue**: only those CRs are filed, with `cr-plan`, each scored with `--points`.

## Closing a CR
- x
"""

GOOD_GAP_ANALYSIS = """# Gap Analysis

## Rules
23. **Re-score the CR** — the analysis re-scores the CR with `cr-plan --points`, re-sending its current title, release and wave. A CR the analysis finds above 13 is split before the pre-review. In multi mode a Track raises the re-score or split to Mainline, which runs `cr-plan` and files the split CRs.
"""

GOOD_SHUTDOWN = """# Shutdown

### Step 1A — GRACEFUL (default)
Nothing is abandoned. A graceful shutdown finishes the plan's active cycle, except when that cycle is the last one and its pre-merge gate has not run: that cycle stays active and is reported as "awaiting the pre-merge gate".

### Step 1B — EMERGENCY (`emergency` flag set)
- Fast-abort the rest.

## Guardrails
- A normal shutdown ALWAYS finishes the plan's active cycle, except a last cycle awaiting the pre-merge gate, and commits a clean tree.
"""

GOOD_PROCEDURE = """# AGENTS

## Code quality
- Remove ALL unused imports.
- **A test leak** — state one test leaves for another: an environment variable, a stub, a global — is fixed at its source, never in the tests it breaks.

## Consequences
- x
"""

GOOD_GIT_WORKFLOW = """# Git Workflow

## Releases (NON-NEGOTIABLE)

- **Running a CR during a release is HIGHLY DISCOURAGED** for new, unplanned work. A release fix is the rule, and needs no extra approval.
- **A release fix is a CR.** A failure the release's own verification finds (the rehearsal, the regression, the gate) is fixed by a CR filed into that release, with a plan and cycle-bound agents. It commits directly on the release branch, never on a separate bugfix branch, and reaches develop at `finish`.
  - Its runs are cycle runs.
  - Its `cr-close` takes the fix's last commit on the release branch.
  - The release's own `regression` and `pre-merge-gate` stay `--release` runs from an unbound id.
- **The test-hygiene CR.** Every release carries a test-hygiene CR, sequenced last in the release's final wave. It sweeps:
  - the suite's analyzer findings;
  - its flaky, slow or network-bound tests;
  - its skip reasons and duplicated helpers;
  - the hygiene notes the release's CRs deferred.

  Because it is last, the wave has not drained while it is open, so the release does not start. No dependency edge is added; CRs stay non-gates.

When the `master` run fails its tests, nothing publishes: re-run the failed jobs, and fix a real failure on a hotfix branch.

## Multi-Account Pushing
- x
"""

GOOD_MODEL_B = """# Model B

## 4. Universal conventions (PRD §D3 — every project instantiates these)

5. **Releases:** a wave is never a release, and a release is not a CR. Work a release genuinely needs is an ordinary CR in the wave. Every release carries a test-hygiene CR, sequenced last in its final wave: while it is open the wave has not drained, so the release does not start.

## 5. Role routing
"""

GOOD_AGENTS = """# Repository Guidelines

## Workflow Rules (Model B, solo)

- Close-out order: merge `develop` into the feature branch until behind=0; run the pre-merge gate while the plan's last cycle is still active, bound to it with `--cycle`; `cycle-done`; `unregister`, then `register`; the merge sign-off; the spec's `**Status:**` flip, the branch's last commit; the merge; `cr-close`.
- Wave-boundary gate: no-mistakes via `gate-run --intent <goal> --agent vidushi-mdb`, ingested as gate evidence; the intent tells the gate not to stop any server it did not start.
"""

#: Each surface's synthetic file, and for each of its rules the one cut that removes that rule.
GOOD_SURFACES = {
    "S1 crucible intro": (GOOD_CRUCIBLE, {
        S1_CRUCIBLE_INTRO[0][0]: "only through client verbs, ",
        S1_CRUCIBLE_INTRO[1][0]: " and proposes one to Crucible",
    }),
    "S1 crucible envelope": (GOOD_CRUCIBLE, {
        S1_CRUCIBLE_ENVELOPE[0][0]: "that is what the clients receive",
    }),
    "S1 orchestration-common": (GOOD_COMMON, {
        S1_COMMON[0][0]: "only through client verbs, ",
        S1_COMMON[1][0]: " and proposes one to Crucible",
    }),
    "S2 cr-authoring": (GOOD_CR_AUTHORING, {
        S2_CR_AUTHORING[0][0]: "is scored when filed",
        S2_CR_AUTHORING[1][0]: "1, 2, 3, 5, 8, 13",
        S2_CR_AUTHORING[2][0]: "13 is the cap; ",
        S2_CR_AUTHORING[3][0]: ", each scored with `--points`",
    }),
    "S2 gap-analysis": (GOOD_GAP_ANALYSIS, {
        S2_GAP_ANALYSIS[0][0]: ", re-sending its current title, release and wave",
        S2_GAP_ANALYSIS[1][0]: " is split before the pre-review",
        S2_GAP_ANALYSIS[2][0]: ("In multi mode a Track raises the re-score or split to Mainline, "
                                "which runs `cr-plan` and files the split CRs."),
    }),
    "S2 orchestration-mainline": (GOOD_MAINLINE, {
        S2_MAINLINE[0][0]: " --points <n>",
    }),
    "S3 orchestration-common": (GOOD_COMMON, {
        S3_COMMON[0][0]: " (the spec wins)",
        S3_COMMON[1][0]: "because VERIFY and the gate catch drift",
    }),
    "S5 orchestration-common close-out": (GOOD_COMMON, {
        S5_COMMON_CLOSE_OUT[0][0]: ", or the last `fix` cycle appended after it",
        S5_COMMON_CLOSE_OUT[1][0]: " under the orchestrator's own id",
        S5_COMMON_CLOSE_OUT[2][0]: " on the gate's first run",
        S5_COMMON_CLOSE_OUT[3][0]: "first `register --role ORCHESTRATOR --cycle <last>`",
        S5_COMMON_CLOSE_OUT[4][0]: "later runs inherit the binding",
        S5_COMMON_CLOSE_OUT[5][0]: "then `cycle-done` closes the cycle with it",
        S5_COMMON_CLOSE_OUT[6][0]: " inside that new last cycle",
        S5_COMMON_CLOSE_OUT[7][0]: " follows the same path",
        S5_COMMON_CLOSE_OUT[8][0]: "the post-merge develop gate;",
    }),
    "S5 crucible who runs what": (GOOD_CRUCIBLE, {
        S5_CRUCIBLE_WHO[0][0]: " in the plan's last cycle,",
    }),
    "S5 shutdown": (GOOD_SHUTDOWN, {
        S5_SHUTDOWN[0][0]: (", except when that cycle is the last one and its pre-merge gate has "
                            "not run: that cycle stays active and is reported as \"awaiting the "
                            "pre-merge gate\""),
    }),
    "S6 sub-agent-procedure": (GOOD_PROCEDURE, {
        S6_TEST_LEAK[0][0]: "state one test leaves for another: ",
        S6_TEST_LEAK[1][0]: ", never in the tests it breaks",
    }),
    "S6 orchestration-common": (GOOD_COMMON, {
        S6_TEST_LEAK[0][0]: "state one test leaves for another: ",
        S6_TEST_LEAK[1][0]: ", never in the tests it breaks",
    }),
    "S7 git-workflow": (GOOD_GIT_WORKFLOW, {
        S7_GIT_RELEASES[0][0]: ", with a plan and cycle-bound agents",
        S7_GIT_RELEASES[1][0]: ", never on a separate bugfix branch",
        S7_GIT_RELEASES[2][0]: "Its runs are cycle runs.",
        S7_GIT_RELEASES[3][0]: "takes the fix's last commit on the release branch",
        S7_GIT_RELEASES[4][0]: " from an unbound id",
        S7_GIT_RELEASES[5][0]: "for new, unplanned work",
        S7_GIT_RELEASES[6][0]: ", and fix a real failure on a hotfix branch",
        S7_GIT_RELEASES[7][0]: ", sequenced last in the release's final wave",
        S7_GIT_RELEASES[8][0]: "the wave has not drained while it is open, so ",
        S7_GIT_RELEASES[9][0]: "its flaky, slow or network-bound tests;",
        S7_GIT_RELEASES[10][0]: "No dependency edge is added; ",
    }),
    "S7 model-b 4.5": (GOOD_MODEL_B, {
        S7_MODEL_B[0][0]: "while it is open the wave has not drained, so ",
    }),
    "S7 cr-authoring": (GOOD_CR_AUTHORING, {
        S7_CR_AUTHORING[0][0]: ", so the wave has not drained while it is open",
    }),
    "S7 crucible gate-run": (GOOD_CRUCIBLE, {
        S7_CRUCIBLE_GATE[0][0]: "not to stop any server it did not start",
    }),
    "S7 AGENTS.md": (GOOD_AGENTS, {
        S7_AGENTS_GATE[0][0]: "; the intent tells the gate not to stop any server it did not start",
    }),
}


class DetectorsOnSyntheticTextTest(unittest.TestCase):
    """Every detector kind proved both ways: a conforming sample passes, a sample without the
    phrase (or with the retired phrase) bites."""

    def test_every_surface_has_a_synthetic_sample_and_one_cut_per_rule(self):
        self.assertEqual(sorted(GOOD_SURFACES), sorted(SURFACES))
        for key, (_rel, _region, rules) in SURFACES.items():
            with self.subTest(surface=key):
                self.assertEqual(sorted(GOOD_SURFACES[key][1]), sorted(n for n, _ in rules))

    def test_the_rule_detector_passes_each_conforming_sample(self):
        for key, (good, _cuts) in GOOD_SURFACES.items():
            with self.subTest(surface=key):
                self.assertEqual(surface_findings(key, good), [])

    def test_the_rule_detector_bites_on_each_cut_alone(self):
        for key, (good, cuts) in GOOD_SURFACES.items():
            for name, cut in cuts.items():
                with self.subTest(surface=key, rule=name):
                    self.assertIn(cut, good, "the cut must be text of the sample")
                    self.assertEqual(surface_findings(key, good.replace(cut, " ")), [name])

    def test_the_rule_detector_bites_when_the_rule_leaves_its_region(self):
        moved = GOOD_COMMON.replace("## Close-out\n", "## Somewhere else\n")
        found = surface_findings("S5 orchestration-common close-out", moved)
        self.assertEqual(found[0], f"{COMMON}: no common_close_out region")
        self.assertEqual(found[1:], [name for name, _ in S5_COMMON_CLOSE_OUT])
        intro_moved = GOOD_CRUCIBLE.replace(
            "Never hand-roll `curl`: the orchestrator reads and writes the board only through "
            "client verbs, never the HTTP API. Where no verb fits, it says so and proposes one to "
            "Crucible.", "Never hand-roll `curl`.").replace(
            "## Envelope", "The orchestrator reads and writes the board only through client "
            "verbs, never the HTTP API. Where no verb fits, it says so and proposes one to "
            "Crucible.\n\n## Envelope")
        self.assertEqual(surface_findings("S1 crucible intro", intro_moved),
                         [name for name, _ in S1_CRUCIBLE_INTRO])

    def test_the_led_list_joins_a_lead_with_only_the_list_it_introduces(self):
        text = "Every other run stays unbound:\n\n- baselines;\n- the gate.\n\nAfter.\n"
        self.assertEqual(led_lists(text),
                         ["every other run stays unbound: - baselines; - the gate."])
        nested = "- Lead:\n  - one;\n  - two.\n- Sibling.\n"
        self.assertEqual(led_lists(nested), ["- lead: - one; - two."])

    def test_the_order_detector_both_ways(self):
        good = common_close_out(GOOD_COMMON)
        self.assertEqual(order_findings(good, CLOSE_OUT_ORDER), [])
        self.assertEqual(order_findings(common_close_out(GOOD_AGENTS.replace(
            "## Workflow Rules (Model B, solo)", "## Close-out")), CLOSE_OUT_ORDER), [])
        swapped = good.replace("3. `cycle-done`.", "3. Hold.").replace(
            "5. The merge sign-off.", "5. `cycle-done`, then the merge sign-off.")
        self.assertEqual(order_findings(swapped, CLOSE_OUT_ORDER),
                         ["step 4 (unregister, then register) is missing or out of order"])
        dropped = good.replace("1. Merge `develop` into the feature branch until behind=0.",
                               "1. Rebase.")
        self.assertEqual(order_findings(dropped, CLOSE_OUT_ORDER),
                         ["step 1 (merge develop into the feature branch until behind=0) is "
                          "missing or out of order"])
        last = good.replace("8. `cr-close`.", "8. Done.")
        self.assertEqual(order_findings(last, CLOSE_OUT_ORDER),
                         ["step 8 (cr-close) is missing or out of order"])

    def test_the_absence_detector_both_ways(self):
        self.assertEqual(absence_findings(GOOD_CRUCIBLE, S5_CRUCIBLE_RETIRED), [])
        old = GOOD_CRUCIBLE + (
            "\n- **ORCHESTRATOR** — runs the gate with the verify cycle\n  activated "
            "(`cycle-activate`) so the gate attaches as that cycle's LAST\n  linked run.\n")
        self.assertEqual(absence_findings(old, S5_CRUCIBLE_RETIRED),
                         ["'verify cycle activated'", "'LAST linked run'"])

    def test_the_http_invitation_detector_both_ways(self):
        self.assertEqual(http_read_invitations(GOOD_CRUCIBLE), [])
        shipped_shape = GOOD_CRUCIBLE + (
            "\nParse stdout as the machine channel. GETs also serve compact TOON (`?fmt=toon` /\n"
            "`Accept: text/toon`), and JSON replies carry `help` hints — read them; they\n"
            "name the next step.\n")
        found = http_read_invitations(shipped_shape)
        self.assertEqual(len(found), 1, found)
        self.assertIn("gets also serve compact toon", found[0])
        for clean in ("Never read the board over HTTP; the client is the interface.\n",
                      "The board's HTTP replies are compact TOON: that is what the clients "
                      "receive — read them in the envelope.\n"):
            with self.subTest(clean=clean):
                self.assertEqual(http_read_invitations(clean), [])

    def test_the_cr_plan_points_detector_both_ways(self):
        region = crucible_queue_verbs(GOOD_CRUCIBLE)
        self.assertEqual(cr_plan_points_findings(region), [])
        self.assertEqual(cr_plan_points_findings(region.replace(" --points <n>", "")),
                         ["no cr-plan write-verb example carries --points <n>"])
        prose_only = "- `cr-plan` takes a score with --points <n> --agent <id>.\n"
        self.assertEqual(len(cr_plan_points_findings(prose_only)), 1,
                         "--points in prose outside the cr-plan span does not count")

    def test_the_bare_leak_detector_both_ways(self):
        self.assertEqual(bare_leak_findings(procedure_code_quality(GOOD_PROCEDURE)), [])
        bare = GOOD_PROCEDURE.replace("never in the tests it breaks.",
                                      "never in the tests the leak breaks.")
        self.assertEqual(len(bare_leak_findings(procedure_code_quality(bare))), 1)
        worktree = "- Absolute paths are the usual leak.\n"
        self.assertEqual(bare_leak_findings(worktree), [],
                         "a worktree leak outside the test-leak rule is not this gate's")

    def test_the_always_finishes_detector_both_ways(self):
        self.assertEqual(unexcepted_always_findings(GOOD_SHUTDOWN), [])
        old = GOOD_SHUTDOWN.replace(", except a last cycle awaiting the pre-merge gate,", "")
        found = unexcepted_always_findings(old)
        self.assertEqual(len(found), 1, found)
        self.assertIn("always finishes the plan's active cycle", found[0])


if __name__ == "__main__":
    unittest.main()
