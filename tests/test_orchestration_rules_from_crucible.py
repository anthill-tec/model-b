"""The orchestration rules adopted from Crucible's wave 7: the board through client verbs only,
story points, a brief that adds no proof steps, unnumbered cycle labels and cycle-id agent ids,
the pre-merge gate inside the last cycle, test leaks, and release fixes, the test-hygiene CR and
the gate's intent (CR-MDB-059 §S1–§S7; PRD D5, AMENDED 2026-10-15).

Contract: ``docs/changes/CR-MDB-059-orchestration-rules-from-crucible-wave-7.md`` and its
acceptance criteria. §S4 (cycle labels, agent ids, the ``worktree-flow`` cycle field) is gated
here too, except its routing check, which lives with the other routing checks in
``tests.test_pi_worktree_isolation.WorktreeRoutingTest``.

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
- ``order_findings`` — §S5's eight-step close-out order, searched step after step: in
  ``orchestration-common.md`` § Close-out through its numbered steps only (``numbered_steps``), so
  the bullets after the list never supply a step; in ``AGENTS.md`` § Workflow Rules through the
  section.
- ``unbound_list_findings`` — §S5: the unbound list ends after its three items, and a non-list
  line comes before the rest of § Close-out's bullets.
- ``plan_file_points_spans`` — §S2: no ``plan-file`` code span of ``cr-authoring`` carries
  ``--points``.
- ``absence_findings`` — §S5: the ``crucible`` skill no longer says "verify cycle activated" or
  "LAST linked run".
- ``http_read_invitations`` — §S1: no sentence of the ``crucible`` skill invites reading the board
  over HTTP (an HTTP surface and an invitation, with no ``never``/``not``/"only through" and no
  "what the clients receive").
- ``cr_plan_points_findings`` — §S2: the ``crucible`` skill's queue-verbs ``cr-plan`` write-verb
  example carries ``--points <n>``.
- ``bare_leak_findings`` — §S6: a unit stating the test-leak rule says "test leak", never a bare
  "leak" (which already means a write outside the worktree).
- ``unexcepted_finish_findings`` — §S5: wherever the body of the ``shutdown`` skill (its
  frontmatter excluded) or ``orchestration-track.md`` says to finish the (plan's) active cycle, in
  any form, the same unit carries the pre-merge-gate exception; the emergency path's "do not
  finish" is not such a line.
- ``exception_site_findings`` — §S5: each named site (the ``shutdown`` skill's introduction, its
  Track paragraph, Step 1A, Step 2A and the guardrails; ``orchestration-track.md``'s graceful
  line) states the exception.

§S4's detectors, each proved both ways in ``CycleIdDetectorsOnSyntheticTextTest``:

- ``label_gate_files`` and ``old_cycle_form_hits`` — the negative label gate: over its file set
  (``skills-src/**/*.md`` minus the imported bundles, the generator's templates and stacks,
  ``AGENTS.md``, ``contracts/crucible-envelope.md``), no line carries a numbered label or a
  positional agent-id tag (``OLD_CYCLE_FORMS``; ``AGENTS_ONLY_OLD_FORMS`` in ``AGENTS.md`` only).
- ``plan_file_label_findings`` — every ``plan-file`` example's ``--cycle`` is ``"<label>"``.
- ``reference_id_form_findings`` — the five ``crucible/references/<stack>.md`` give one TDD form,
  ``CR-<ACRONYM>-NNN-<cycle id>-<ROLE>``, and none says ``<PHASE>``.
- ``agents_test_command_findings`` — ``AGENTS.md``'s ``--tests`` client runs use a cycle-id id.
- ``baseline_citation_findings`` — ``AGENTS.md`` cites its baselines "at CR-MDB-NNN's
  ``<cycle label>`` cycle".
- ``docstring_id_findings`` — ``pi-package/extensions/worktree.ts``'s leading comment gives its
  agent-id example in the cycle-id form, and no numbered tag.

§S4's ``worktree-flow.py status`` check drives the real script on a throwaway git repo.

The ``crucible`` skill's stale-binding bullet (§S5) is gated where it always was,
``tests.test_ambient_manifest_discovery.CrucibleLifecycleRulesS5Test`` (migrated there).

Hermetic: reads repo files, and writes only temp dirs (the ``worktree-flow`` fixture repo and the
negative gate's fixture tree). Stdlib only.
"""

import re
import shutil
import tempfile
import unittest
from pathlib import Path

from tests._helpers import REPO_ROOT, build_tree, decode_envelope, read_text
from tests._helpers import unchanged_text as whole
from tests.test_board_holds_the_queue import (
    CR_AUTHORING_QUEUE_HEADING,
    CR_CLOSE,
    MAINLINE_FILING_HEADING,
    _numbered_item,
    code_spans,
    invocation_lines,
    norm_units,
    section,
    section_matching,
    units,
)
from tests.test_bootstrap_shutdown_registry import normalise
from tests.test_suite_hygiene import _client_runs
from tests.test_worktree_flow_dbless import _run_wf
from tests.test_worktree_layout_and_bundles import _git_c3 as _git

CRUCIBLE = "skills-src/crucible/SKILL.md"
COMMON = "skills-src/model-b/references/orchestration-common.md"
MAINLINE = "skills-src/model-b/references/orchestration-mainline.md"
TRACK = "skills-src/model-b/references/orchestration-track.md"
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
#: A numbered step at column 0 (§S5, F1): ``<n>.`` opens the unit.
_NUMBERED_STEP = re.compile(r"^\d+\.\s")
_FRONTMATTER = re.compile(r"\A---\n.*?\n---\n", re.S)

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


def shutdown_step_2a(text: str) -> str:
    return section_matching(text, r"^step 2a\b")


def shutdown_guardrails(text: str) -> str:
    return section_matching(text, r"^guardrails\b")


def body(text: str) -> str:
    """``text`` without its leading ``---`` frontmatter block, when it has one."""
    return _FRONTMATTER.sub("", text, count=1)


def numbered_steps(region: str) -> list[str]:
    """The raw units of ``region`` that open with a numbered step at column 0, wrapped lines
    kept: the steps of a numbered list, and never the bullets after it (§S5, F1)."""
    return [u for u in units(region) if _NUMBERED_STEP.match(u)]


def procedure_code_quality(text: str) -> str:
    return section(text, "Code quality")


def git_releases(text: str) -> str:
    return section_matching(text, r"^releases\b")


def model_b_item_5(text: str) -> str:
    return _numbered_item(section_matching(text, r"^4\. universal conventions"), 5)


def agents_workflow_rules(text: str) -> str:
    return section_matching(text, r"^workflow rules\b")


def _item_unit(sec: str, n: int) -> str:
    """The raw unit of numbered item ``n`` (``n.`` at line start) in ``sec``, its wrapped lines
    kept; ``""`` when there is none."""
    hit = [u for u in units(sec) if re.match(rf"^\s*{n}\.\s", u)]
    return hit[0] if hit else ""


def model_b_item_1(text: str) -> str:
    return _item_unit(section_matching(text, r"^4\. universal conventions"), 1)


def model_b_item_3(text: str) -> str:
    return _item_unit(section_matching(text, r"^4\. universal conventions"), 3)


def crucible_identity(text: str) -> str:
    return section_matching(text, r"^identity\b")


def crucible_workflow_classification(text: str) -> str:
    return section_matching(text, r"^workflow classification\b")


def common_parallel_agents(text: str) -> str:
    return section(text, "Parallel agents in one tree")


def contract_agent_naming(text: str) -> str:
    return section_matching(text, r"^agent-naming header\b")


def contract_plan_verbs(text: str) -> str:
    return section_matching(text, r"^universal plan verbs\b")


def agents_testing(text: str) -> str:
    return section_matching(text, r"^testing\b")


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


#: §S5 — a unit saying to finish the (plan's) active cycle, in any of its forms (F5).
FINISH_ACTIVE_CYCLE = re.compile(
    r"\bfinish\w* (?:the |its )?(?:plan'?s )?active cycle\b"
    r"|\bactive cycle (?:is |was )?finished\b")
#: The words just before a match that make it the emergency path's NOT finishing.
_NOT_FINISHING = re.compile(r"\b(?:skip|not|no|never|without)\s+$")
#: §S5 — the exception: a last cycle awaiting the pre-merge gate.
PRE_MERGE_EXCEPTION = re.compile(r"\b(?:except|unless)\b[^.]{0,100}\bpre-merge gate\b")


def says_finish_active_cycle(unit: str) -> bool:
    """Whether the normalised ``unit`` says to finish the active cycle, a negated form
    ("skip finishing", "do not finish") aside."""
    return any(not _NOT_FINISHING.search(unit[max(0, m.start() - 12):m.start()])
               for m in FINISH_ACTIVE_CYCLE.finditer(unit))


def unexcepted_finish_findings(text: str) -> list[str]:
    """Each normalised unit of ``text``'s body (its frontmatter excluded) saying to finish the
    active cycle with no pre-merge-gate exception in the same unit."""
    return [u for u in norm_units(body(text))
            if says_finish_active_cycle(u) and not PRE_MERGE_EXCEPTION.search(u)]


def exception_site_findings(text: str, sites) -> list[str]:
    """The name of each ``(name, region, lead)`` site whose region holds no unit (opening with
    ``lead``, when given) that says to finish the active cycle and carries the exception."""
    return [name for name, region_of, lead in sites
            if not any((lead is None or re.match(lead, u)) and says_finish_active_cycle(u)
                       and PRE_MERGE_EXCEPTION.search(u)
                       for u in norm_units(region_of(text)))]


UNBOUND_LEAD = re.compile(r"^every other orchestrator run stays unbound:")
#: §S5 — the unbound list: baselines, the post-merge develop gate, the release's own gate.
UNBOUND_ITEMS = 3


def unbound_list_findings(region: str) -> list[str]:
    """``[]`` when ``region``'s one unbound-list lead is followed by its three items and then a
    non-list line, so no later bullet renders as an item of that list (F6)."""
    raw = units(region)
    leads = [i for i, u in enumerate(raw) if UNBOUND_LEAD.match(normalise(u))]
    if len(leads) != 1:
        return [f"{len(leads)} unbound-list leads, not one"]
    items = []
    for nxt in raw[leads[0] + 1:]:
        if not _LIST_ITEM.match(nxt):
            break
        items.append(nxt)
    if len(items) != UNBOUND_ITEMS:
        return [f"the unbound list runs to {len(items)} items, not {UNBOUND_ITEMS}: no non-list "
                "line ends it before the next bullets"]
    return []


_PLAN_FILE_SPAN = re.compile(r"(?:^|[\s>])plan-file(?![\w-])")
_POINTS_FLAG = re.compile(r"(?<![\w-])--points(?![\w-])")


def plan_file_points_spans(text: str) -> list[str]:
    """Each code span of ``text`` (read per unit, so a wrapped span counts) that invokes
    ``plan-file`` and carries ``--points`` — which ``plan-file`` does not take (§S2, F2)."""
    return [span for u in units(text) for span in code_spans(" ".join(u.split()))
            if _PLAN_FILE_SPAN.search(span) and _POINTS_FLAG.search(span)]


# ------------------------------------------------------------------ §S4 detectors ----

CONTRACT = "contracts/crucible-envelope.md"
WORKTREE_TS = "pi-package/extensions/worktree.ts"
REFERENCE_STACKS = ("arduino", "bun", "java", "python", "rust")
#: §S4: the TDD-role agent-id form, exactly as the five stack references give it.
TDD_ID_FORM = "CR-<ACRONYM>-NNN-<cycle id>-<ROLE>"

#: The imported bundles the negative label gate leaves out (§S4 AC; non-goal: they stay
#: byte-identical, and their generic ``<cycle>`` slot admits a cycle id).
IMPORTED_BUNDLE = re.compile(r"^(?:crucible-report-[^/]+|crucible-register)$")

#: §S4 AC — the retired forms, on every file of the gate. The AC writes the first as
#: ``\bC<n>\b``; a trailing ``\b`` after ``>`` holds only before a word character, so taken
#: literally it never fires on ``C<n> <label>``, the very form it retires. The token alone is
#: the gate (interpretation, raised as an ESCALATION in the RED report).
OLD_CYCLE_FORMS = (
    ("numbered-label placeholder C<n>", re.compile(r"\bC<n>")),
    ('a --cycle "C<digits> example', re.compile(r'--cycle\s+"C\d+')),
    ("a numbered label C<digits> <label>", re.compile(r"\bC\d+ <label>")),
    ("a positional agent-id tag", re.compile(r"CR-[^\s`]*-[CF]\d+-(?:RED|GREEN|VERIFY|FIX)\b")),
)
#: §S4 AC — in ``AGENTS.md`` only.
AGENTS_ONLY_OLD_FORMS = (
    ("a numbered cycle with a role C<digits> <ROLE>",
     re.compile(r"\bC\d+ (?:RED|GREEN|VERIFY|FIX)\b")),
)


def label_gate_files(root: Path = REPO_ROOT) -> list[str]:
    """The negative label gate's file set under ``root``, repo-relative: ``skills-src/**/*.md``
    minus the imported bundles, ``generator/templates/*.tmpl``, ``generator/stacks/*.toml``,
    ``AGENTS.md`` and ``contracts/crucible-envelope.md``."""
    root = Path(root)
    skills = root / "skills-src"
    rels = [p.relative_to(root).as_posix() for p in sorted(skills.rglob("*.md"))
            if not IMPORTED_BUNDLE.match(p.relative_to(skills).parts[0])]
    rels += [p.relative_to(root).as_posix()
             for pattern in ("generator/templates/*.tmpl", "generator/stacks/*.toml")
             for p in sorted(root.glob(pattern))]
    rels += [rel for rel in (AGENTS, CONTRACT) if (root / rel).is_file()]
    return rels


def old_cycle_form_hits(rel: str, text: str) -> list[str]:
    """``rel:line: form: match`` for each retired form on each line of ``text`` (the file
    ``rel``); the ``AGENTS.md``-only form counts in ``AGENTS.md`` alone."""
    forms = OLD_CYCLE_FORMS + (AGENTS_ONLY_OLD_FORMS if rel == AGENTS else ())
    return [f"{rel}:{n}: {name}: {m.group(0)}"
            for n, line in enumerate(text.splitlines(), 1)
            for name, rx in forms for m in rx.finditer(line)]


def plan_file_label_findings(region: str) -> list[str]:
    """``[]`` when ``region`` shows a ``plan-file`` example (one code span) with ``--cycle``
    and every such ``--cycle`` is ``"<label>"``; otherwise what is wrong."""
    spans = [span for _line, span in invocation_lines(region, "plan-file")
             if re.search(r'--cycle\s+"', span)]
    if not spans:
        return ["no plan-file example shows --cycle"]
    return [f'--cycle "{label}" in: {span}' for span in spans
            for label in re.findall(r'--cycle\s+"([^"]*)"', span) if label != "<label>"]


def reference_id_form_findings(texts: dict) -> list[str]:
    """What keeps the stack references (``stack -> text``) from giving, each in ONE
    ``Agent naming:`` bullet, the one TDD form ``TDD_ID_FORM``, with no ``<PHASE>`` anywhere."""
    findings = []
    for stack, text in texts.items():
        if "<PHASE>" in text:
            findings.append(f"{stack}: still writes <PHASE>")
        naming = [u for u in units(text) if re.match(r"^\s*[-*]\s+Agent naming:", u)]
        if len(naming) != 1:
            findings.append(f"{stack}: {len(naming)} 'Agent naming:' bullets, not one")
            continue
        tdd = [s for s in code_spans(" ".join(naming[0].split())) if s.startswith("CR-")]
        if tdd != [TDD_ID_FORM]:
            findings.append(f"{stack}: the TDD form is {tdd}, not [{TDD_ID_FORM!r}]")
    return findings


#: A ``--agent`` TDD id in the cycle-id form, placeholder or concrete.
CYCLE_ID_AGENT = re.compile(
    r"--agent\s+CR-MDB-(?:NNN|\d{3})-(?:<cycle id>|\d+)-(?:RED|GREEN|VERIFY|FIX)(?![\w-])")


def agents_test_command_findings(region: str) -> list[str]:
    """Each ``--tests`` client run of ``region``'s fenced blocks whose ``--agent`` is not a
    cycle-id TDD id; one finding when there is no such run at all."""
    runs = [c for c in _client_runs(region) if "--tests" in c]
    if not runs:
        return ["no --tests client run"]
    return [c for c in runs if not CYCLE_ID_AGENT.search(c)]


#: §S4: "at CR-MDB-NNN's `<cycle label>` cycle" — a real or placeholder number, a
#: back-quoted label.
BASELINE_CITATION = re.compile(r"\bat\s+CR-MDB-(?:\d{3}|NNN)['’]s\s+`[^`]+`\s+cycle\b")


def baseline_citation_findings(region: str) -> list[str]:
    """``[]`` when a unit of ``region`` stating the Baselines cites them at a CR's
    back-quoted cycle label."""
    if any(re.search(r"\bBaselines\b", u) and BASELINE_CITATION.search(u) for u in units(region)):
        return []
    return ["the baselines are not cited at CR-MDB-NNN's `<cycle label>` cycle"]


def leading_block_comment(text: str) -> str:
    """The body of the ``/** … */`` comment opening ``text``; ``""`` when it opens with none."""
    match = re.match(r"\s*/\*\*(.*?)\*/", text, re.S)
    return match.group(1) if match else ""


def docstring_id_findings(doc: str) -> list[str]:
    """What keeps ``doc`` from giving its agent-id example in the cycle-id form only."""
    findings = []
    if not re.search(r"\bCR-[A-Z]+-\d{3}-(?:\d+|<cycle id>)-(?:RED|GREEN|VERIFY|FIX)\b", doc):
        findings.append("no agent-id example in the cycle-id form")
    findings += [f"numbered tag: {m.group(0)}" for m in re.finditer(
        r"\bCR-[A-Z]+-\d{3}[ -][CF]\d+[ -](?:RED|GREEN|VERIFY|FIX)\b", doc)]
    return findings


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
    # MIGRATED at CR-MDB-059 (§S2): the retired "plan-file --release … --points" pin becomes
    # the cr-plan score, and plan-file taking no --points (F2).
    ("every CR is scored when filed, with cr-plan --points",
     (r"\bevery cr\b[^.;]{0,10}\bscored when (?:it is )?filed\b", r"cr-plan --points\b")),
    ("a CR filed by plan-file --release is scored the same way, since plan-file takes no --points",
     (r"plan-file --release\b[^.;]{0,20}\bscored\b",
      r"\bplan-file\b[^.;]{0,15}\btakes no --points\b")),
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
    ("a red gate: unregister then register clears the orchestrator's binding before the fix "
     "cycle is appended",
     (r"\bred gate\b", r"\bclears the orchestrator'?s binding\b",
      r"(?<![\w-])unregister,? then,? register(?![\w-]).*\bfix cycle is appended\b")),
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
    ("read the plan before the last cycle's cycle-done (every earlier cycle done), and before "
     "proposing a merge, finish or cr-close (every cycle, VERIFY included, done)",
     (r"\bread the (?:crucible )?plan before the last cycle'?s cycle-done\b",
      r"\bevery earlier cycle\b", r"\bbefore proposing a merge,? finish,? or cr-close\b",
      r"\bevery cycle, verify included\b")),
    ("a release-fix CR follows steps 2–5 and 8, with no feature branch to sync or merge, and its "
     "cr-close takes its last commit on the release branch",
     (r"\brelease-fix cr\b", r"\bsteps 2[–-]5 and 8\b", r"\bno feature branch\b",
      r"(?<![\w-])cr-close\b[^.;]{0,20}\blast commit on the release branch\b")),
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
#: §S5 — ``orchestration-track.md``'s sign-off path points at close-out steps 1–4 (F7).
S5_TRACK_SIGN_OFF = (
    ("the sign-off follows close-out steps 1–4 (orchestration-common.md § Close-out)",
     (r"\bsign-off\b[^.;]{0,40}\bfollows\b[^.;]{0,20}\bclose-out steps 1[–-]4\b",
      r"orchestration-common(?:\.md)?[^.;]{0,6}§ ?close-out\b")),
)
#: §S5 — every site of the ``shutdown`` skill's body that says to finish the active cycle and
#: must carry the exception: ``(name, region, lead)`` (F5).
SHUTDOWN_EXCEPTION_SITES = (
    ("the introduction's graceful bullet", intro, r"^- graceful \(default\)"),
    ("the introduction's Track paragraph", intro, r"^- track\b"),
    ("Step 1A", shutdown_graceful, None),
    ("Step 2A", shutdown_step_2a, None),
    ("the guardrails", shutdown_guardrails, None),
)
#: §S5 — ``orchestration-track.md``'s graceful-shutdown line carries the same exception (F5).
TRACK_EXCEPTION_SITES = (
    ("the graceful-shutdown line", whole, r"^- graceful \(default\):"),
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

#: §S4 — a TDD-role id placeholder and a concrete cycle-id example (normalised text).
ID_FORM_ACRONYM = r"cr-<acronym>-nnn-<cycle id>-<role>"
CONCRETE_CYCLE_ID = r"\bcr-[a-z]+-\d{3}-\d+-(?:red|green|verify|fix)\b"
#: §S4 — a cycle label is ``<label> (§S…)``, with no number before it.
LABEL_FORM = r"\blabels?(?::| is| are)? <label> \(§s"

#: §S4 — ``model-b`` SKILL §4.1: the TDD form beside the orchestrator form, the role by ``--role``.
S4_MODEL_B_41 = (
    ("§4.1 gives the TDD form CR-<ACRONYM>-NNN-<cycle id>-<ROLE> beside the orchestrator form",
     (r"<agent-type>-<project>", ID_FORM_ACRONYM)),
    ("§4.1: the role is declared with --role; the suffix is a readability habit, never parsed",
     (r"--role\b", r"\breadability habit\b", r"\bnever parsed\b")),
)
#: §S4 — ``model-b`` SKILL §4.3: the label carries no number.
S4_MODEL_B_43 = (
    ("§4.3: a cycle label is <label> (§S…)", (LABEL_FORM,)),
)
#: §S4 — the ``crucible`` skill's Identity section.
S4_CRUCIBLE_IDENTITY = (
    ("TDD-role agents are CR-<ACRONYM>-NNN-<cycle id>-<ROLE>, with a concrete cycle-id example",
     (r"\btdd-role agents?\b", ID_FORM_ACRONYM, CONCRETE_CYCLE_ID)),
)
#: §S4 — ``orchestration-common.md``'s parallel-agents suffix example keeps ``-1`` … ``-N``.
S4_COMMON_PARALLEL = (
    ("ids are suffixed -1 … -N, the example a cycle-id id",
     (r"(?<![\w-])-1\b[^.;]{0,12}(?<![\w-])-n\b",
      r"\bcr-[a-z]+-(?:nnn|\d{3})-(?:<cycle id>|\d+)-(?:red|green|verify|fix)-\d+\b")),
)
#: §S4 — ``contracts/crucible-envelope.md``'s agent-naming header (the ``<PHASE>`` supersession
#: line stays, pinned by ``tests.test_contracts``).
S4_CONTRACT = (
    ("TDD-ROLE agents are CR-<PROJ>-NNN-<cycle id>-<ROLE>, with a concrete cycle-id example",
     (r"\btdd-role agents\b", r"cr-<(?:proj|acronym)>-nnn-<cycle id>-<role>", CONCRETE_CYCLE_ID)),
)
#: §S4 — Model B's ``AGENTS.md`` agent-ids line; the pre-review and orchestrator ids unchanged.
S4_AGENTS_IDS = (
    ("the agent-ids line gives CR-MDB-NNN-<cycle id>-<ROLE> with a concrete cycle-id example, "
     "CR-MDB-NNN-SPEC-REVIEW and vidushi-mdb",
     (r"^- agent ids:", r"cr-mdb-nnn-<cycle id>-<role>", CONCRETE_CYCLE_ID,
      r"cr-mdb-nnn-spec-review", r"\bvidushi-mdb\b")),
)
#: §S4 — Model B's ``AGENTS.md`` workflow rules: the stage-flip label and the label form.
S4_AGENTS_WORKFLOW = (
    ("the stage-flip milestone label is \"<CR> <cycle label> done\"",
     (r'--type stage-flip --label "<cr> <cycle label> done"',)),
    ("a cycle label is <label> (§S…)", (LABEL_FORM,)),
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
    "S5 orchestration-track sign-off": (TRACK, whole, S5_TRACK_SIGN_OFF),
    "S6 sub-agent-procedure": (PROCEDURE, procedure_code_quality, S6_TEST_LEAK),
    "S6 orchestration-common": (COMMON, whole, S6_TEST_LEAK),
    "S7 git-workflow": (GIT_WORKFLOW, git_releases, S7_GIT_RELEASES),
    "S7 model-b 4.5": (MODEL_B, model_b_item_5, S7_MODEL_B),
    "S7 cr-authoring": (CR_AUTHORING, cr_authoring_queue, S7_CR_AUTHORING),
    "S7 crucible gate-run": (CRUCIBLE, whole, S7_CRUCIBLE_GATE),
    "S7 AGENTS.md": (AGENTS, agents_workflow_rules, S7_AGENTS_GATE),
    "S4 model-b 4.1": (MODEL_B, model_b_item_1, S4_MODEL_B_41),
    "S4 model-b 4.3": (MODEL_B, model_b_item_3, S4_MODEL_B_43),
    "S4 crucible identity": (CRUCIBLE, crucible_identity, S4_CRUCIBLE_IDENTITY),
    "S4 orchestration-common parallel agents": (COMMON, common_parallel_agents,
                                                 S4_COMMON_PARALLEL),
    "S4 contracts agent-naming": (CONTRACT, contract_agent_naming, S4_CONTRACT),
    "S4 AGENTS.md agent ids": (AGENTS, agents_testing, S4_AGENTS_IDS),
    "S4 AGENTS.md workflow rules": (AGENTS, agents_workflow_rules, S4_AGENTS_WORKFLOW),
}

#: §S4 — the surfaces whose ``plan-file`` examples must show ``--cycle "<label>"``:
#: ``key -> (file, region)``.
PLAN_FILE_SURFACES = {
    "model-b 4.3": (MODEL_B, model_b_item_3),
    "crucible plan verbs": (CRUCIBLE, crucible_workflow_classification),
    "contracts plan verbs": (CONTRACT, contract_plan_verbs),
    "AGENTS.md workflow rules": (AGENTS, agents_workflow_rules),
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

    def test_no_cr_authoring_plan_file_example_carries_points(self):
        self.assertEqual(plan_file_points_spans(read_text(REPO_ROOT / CR_AUTHORING)), [])

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
        # MIGRATED at CR-MDB-059 (§S5): the order is read from the numbered steps only, so the
        # bullets after the list never supply a step (F1).
        steps = numbered_steps(region)
        self.assertEqual(len(steps), 8, steps)
        self.assertEqual(order_findings("\n".join(steps), CLOSE_OUT_ORDER), [])

    def test_orchestration_common_close_out_ends_the_unbound_list_before_the_rest(self):
        region = common_close_out(read_text(REPO_ROOT / COMMON))
        self.assertEqual(unbound_list_findings(region), [])

    def test_orchestration_track_sign_off_follows_close_out_steps_1_to_4(self):
        self.assertEqual(surface_findings("S5 orchestration-track sign-off"), [])

    def test_orchestration_common_close_out_states_binding_loops_and_the_unbound_list(self):
        self.assertEqual(surface_findings("S5 orchestration-common close-out"), [])

    def test_the_crucible_orchestrator_bullet_runs_the_gate_in_the_last_cycle(self):
        self.assertEqual(surface_findings("S5 crucible who runs what"), [])

    def test_the_crucible_skill_no_longer_says_verify_cycle_activated_or_last_linked_run(self):
        self.assertEqual(absence_findings(read_text(REPO_ROOT / CRUCIBLE), S5_CRUCIBLE_RETIRED), [])

    def test_the_shutdown_graceful_mode_keeps_the_last_cycle_awaiting_the_pre_merge_gate(self):
        self.assertEqual(surface_findings("S5 shutdown"), [])

    # MIGRATED at CR-MDB-059 (§S5): the "always finishes" detector widens to every form of
    # finishing the active cycle, in the shutdown skill's body and orchestration-track.md (F5).
    def test_no_shutdown_or_track_line_finishes_the_active_cycle_without_the_exception(self):
        for rel in (SHUTDOWN, TRACK):
            with self.subTest(file=rel):
                self.assertEqual(unexcepted_finish_findings(read_text(REPO_ROOT / rel)), [])

    def test_every_shutdown_site_that_finishes_the_active_cycle_states_the_exception(self):
        self.assertEqual(exception_site_findings(read_text(REPO_ROOT / SHUTDOWN),
                                                 SHUTDOWN_EXCEPTION_SITES), [])

    def test_the_track_graceful_shutdown_line_states_the_exception(self):
        self.assertEqual(exception_site_findings(read_text(REPO_ROOT / TRACK),
                                                 TRACK_EXCEPTION_SITES), [])

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


class CycleLabelsAndAgentIdsTest(unittest.TestCase):
    """§S4 — cycle labels carry no number; a TDD-role agent id carries the cycle's server id."""

    maxDiff = None

    def test_no_gated_file_carries_a_numbered_label_or_a_positional_agent_id_tag(self):
        files = label_gate_files()
        hits = [hit for rel in files
                for hit in old_cycle_form_hits(rel, read_text(REPO_ROOT / rel))]
        self.assertEqual(hits, [])

    def test_the_label_gate_reads_every_surface_of_its_file_set_and_no_imported_bundle(self):
        files = label_gate_files()
        for rel in (AGENTS, CONTRACT, MODEL_B, CRUCIBLE, COMMON,
                    "skills-src/crucible/references/python.md",
                    "generator/templates/red.md.tmpl", "generator/stacks/python.toml"):
            with self.subTest(rel=rel):
                self.assertIn(rel, files)
        self.assertEqual([r for r in files if "/crucible-report-" in r
                          or r.startswith("skills-src/crucible-register/")], [])
        self.assertEqual([r for r in files if r.startswith(("tests/", "docs/"))], [])

    def test_model_b_section_4_1_gives_the_tdd_form_beside_the_orchestrator_form(self):
        self.assertEqual(surface_findings("S4 model-b 4.1"), [])

    def test_model_b_section_4_1_stays_on_its_single_line(self):
        item = model_b_item_1(read_text(REPO_ROOT / MODEL_B))
        self.assertTrue(item.strip(), "§4.1 is missing")
        self.assertNotIn("\n", item.strip())

    def test_model_b_section_4_3_labels_carry_no_number(self):
        self.assertEqual(surface_findings("S4 model-b 4.3"), [])

    def test_every_plan_file_example_shows_an_unnumbered_cycle_label(self):
        for key, (rel, region_of) in PLAN_FILE_SURFACES.items():
            with self.subTest(surface=key):
                self.assertEqual(
                    plan_file_label_findings(region_of(read_text(REPO_ROOT / rel))), [])

    def test_the_crucible_identity_section_gives_the_cycle_id_form(self):
        self.assertEqual(surface_findings("S4 crucible identity"), [])

    def test_the_five_stack_references_give_the_cycle_id_form_in_parity(self):
        texts = {stack: read_text(REPO_ROOT / f"skills-src/crucible/references/{stack}.md")
                 for stack in REFERENCE_STACKS}
        self.assertEqual(reference_id_form_findings(texts), [])

    def test_orchestration_common_parallel_agents_example_keeps_the_suffix(self):
        self.assertEqual(surface_findings("S4 orchestration-common parallel agents"), [])

    def test_the_envelope_contract_example_id_carries_a_cycle_id(self):
        self.assertEqual(surface_findings("S4 contracts agent-naming"), [])

    def test_the_worktree_extension_docstring_example_carries_a_cycle_id(self):
        doc = leading_block_comment(read_text(REPO_ROOT / WORKTREE_TS))
        self.assertTrue(doc.strip(), f"{WORKTREE_TS} opens with no /** … */ comment")
        self.assertEqual(docstring_id_findings(doc), [])

    def test_agents_md_agent_ids_line_gives_the_cycle_id_form(self):
        self.assertEqual(surface_findings("S4 AGENTS.md agent ids"), [])

    def test_agents_md_test_command_examples_use_a_cycle_id_agent_id(self):
        self.assertEqual(
            agents_test_command_findings(agents_testing(read_text(REPO_ROOT / AGENTS))), [])

    def test_agents_md_stage_flip_label_and_cycle_label_form(self):
        self.assertEqual(surface_findings("S4 AGENTS.md workflow rules"), [])

    def test_agents_md_cites_its_baselines_at_a_cycle_label(self):
        self.assertEqual(
            baseline_citation_findings(agents_testing(read_text(REPO_ROOT / AGENTS))), [])


class WorktreeFlowStatusCycleFieldTest(unittest.TestCase):
    """§S4 — ``worktree-flow.py status`` no longer parses ``C<n>`` from a commit subject: no
    ``cycle`` field in the envelope, no cycle on the human board. Drives the real script on a
    throwaway repo with one CR worktree whose latest commit subject holds ``C1``."""

    SUBJECT = "test(CR-FOO-001 C1): RED — write the failing tests"

    def setUp(self):
        base = Path(tempfile.mkdtemp(prefix="modelb-wf-cycle-")).resolve()
        self.addCleanup(shutil.rmtree, base, ignore_errors=True)
        self.repo = base / "repo"
        self.repo.mkdir()
        self.worktree = self.repo / ".worktrees" / "CR-FOO-001"
        for cwd, argv in (
                (self.repo, ("init", "-q", "-b", "develop", ".")),
                (self.repo, ("-c", "commit.gpgsign=false", "commit", "-q", "--allow-empty",
                             "-m", "init")),
                (self.repo, ("worktree", "add", "-q", "-b", "feature/CR-FOO-001-labels",
                             str(self.worktree))),
                (self.worktree, ("-c", "commit.gpgsign=false", "commit", "-q", "--allow-empty",
                                 "-m", self.SUBJECT))):
            proc = _git(cwd, *argv)
            self.assertEqual(proc.returncode, 0, f"fixture git {argv}: {proc.stderr}")
        self.result = _run_wf("status", "--project-dir", str(self.repo))
        self.assertEqual(self.result.returncode, 0, self.result.stderr)

    def _row(self) -> dict:
        axi = decode_envelope(self.result.stdout)["axi"]
        rows = [r for r in axi["worktrees"] if r.get("cr") == "CR-FOO-001"]
        self.assertEqual(len(rows), 1, axi["worktrees"])
        return rows[0]

    def test_the_status_envelope_row_carries_no_cycle_field(self):
        row = self._row()
        self.assertEqual(row["last_subject"], self.SUBJECT, "the board still reads the branch")
        self.assertEqual(row["phase"], "RED", "the phase parse is not §S4's to remove")
        self.assertNotIn("cycle", row)

    def test_no_status_envelope_row_carries_a_cycle_field(self):
        axi = decode_envelope(self.result.stdout)["axi"]
        self.assertEqual(len(axi["worktrees"]), 2, axi["worktrees"])
        self.assertEqual([sorted(r) for r in axi["worktrees"] if "cycle" in r], [])

    def test_the_human_board_phase_line_names_no_cycle(self):
        phase_lines = [line.strip() for line in self.result.stderr.splitlines()
                       if line.strip().startswith("phase:")]
        self.assertEqual(len(phase_lines), 1, self.result.stderr)
        before_subject = phase_lines[0].split("last:", 1)[0]
        self.assertIn("RED", before_subject)
        self.assertNotRegex(before_subject, r"\bC1\b")
        self.assertIn(self.SUBJECT, phase_lines[0], "the last subject is still shown whole")


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

- **A red gate** is ingested, then `cycle-done` closes the cycle with it, and `unregister` then
  `register` clears the orchestrator's binding. A `fix` cycle is appended (`cycle-add --kind fix`),
  and the gate runs again inside that new last cycle.
- **A sign-off that sends changes back** after `cycle-done` follows the same path.

Every other orchestrator run stays unbound:

- baselines;
- the post-merge develop gate;
- the release's own verification gate, which runs under `--release`.

The rest of the close-out:

- Steps 6 and 8 bracket the merge: before the merge, the spec's `**Status:**` flip; after it, `cr-close --commit <merge sha> --agent <id>`, which posts `cr-merged`.
- **Read the Crucible plan before the last cycle's `cycle-done`** (every earlier cycle done), **and before proposing a merge, `finish` or `cr-close`** (every cycle, VERIFY included, done).
- **A release-fix CR** follows steps 2–5 and 8: it has no feature branch to sync or merge, and its `cr-close` takes its last commit on the release branch.
- **The close-out's `**Status:**` flip is the LAST commit on the feature branch** — after the merge, touch zero docs for the shipped CR.

## Investigation discipline
- Read the actual errors first.
"""

GOOD_MAINLINE = """# Orchestration — MAINLINE

## Filing/assigning a CR — COMMIT docs FIRST, schedule write LAST
- Order: write the spec → `git commit` to `develop` → THEN file it on the board (`cr-plan --points <n>`, `cr-depends`, `wave-sequence`) and assign the lane.
"""

GOOD_CR_AUTHORING = """# CR / PRD / DN Authoring

## The CR queue — structure only (queue idiom, 2026-07-20)
- **Scoring:** every CR is scored when filed, with `cr-plan --points <n> --agent <id>`; a CR filed by `plan-file --release` is scored the same way, since `plan-file` takes no `--points`. The scale is 1, 2, 3, 5, 8, 13. 13 is the cap; a CR scoring more is split before it is filed.
- **A release is NOT a CR.** A release is a boundary event: the wave carrying it drains its queue on the board. Work the release genuinely needs is an ordinary CR in the wave, among it every release's test-hygiene CR, sequenced last in the final wave, so the wave has not drained while it is open.
- **A project scaffolded before the board held the queue**: only those CRs are filed, with `cr-plan`, each scored with `--points`.

## Closing a CR
- x
"""

GOOD_GAP_ANALYSIS = """# Gap Analysis

## Rules
23. **Re-score the CR** — the analysis re-scores the CR with `cr-plan --points`, re-sending its current title, release and wave. A CR the analysis finds above 13 is split before the pre-review. In multi mode a Track raises the re-score or split to Mainline, which runs `cr-plan` and files the split CRs.
"""

GOOD_SHUTDOWN = """---
name: shutdown
description: End-of-run teardown — finishes its active step, finishes its plan's active cycle on the Crucible board, acks.
---

# Shutdown — end-of-run orchestrator teardown

**Two modes, chosen by the `emergency` flag:**
- **Graceful (default)** — finish the active step, finish the plan's active cycle (except a last
  cycle awaiting the pre-merge gate, which stays active), commit so nothing dangles, ack, then
  stop the watcher.
- **Emergency** — close only the active write, **fast-abort** the rest
  (skip finishing the active cycle, no merge), best-effort ack, then stop the watcher.

**Role asymmetry is the point of this skill:**
- **Track** is normally shut down by **MAINLINE**.
  A Track never tears down before its active cycle is finished (except a last cycle awaiting the
  pre-merge gate) and its worktree committed, unless told to emergency-stop.

## Step 1 — Classify the shutdown (BOTH roles)

### Step 1A — GRACEFUL (default)
Nothing is abandoned. A graceful shutdown finishes the plan's active cycle, except when that cycle is the last one and its pre-merge gate has not run: that cycle stays active and is reported as "awaiting the pre-merge gate".

### Step 1B — EMERGENCY (`emergency` flag set)
- **Fast-abort** the rest — do NOT finish the active cycle, do NOT attempt a CR merge.

## Step 2A — TRACK shutdown

**Graceful (1A):**
1. **Finish the active step** (Step 1).
2. **Mid-CR with an active cycle on the plan? ESCALATE first.** *"Track N got a shutdown; mid
   CR-XXX. Non-emergency → I'll finish the active cycle (unless it is the last one, awaiting the
   pre-merge gate), commit the worktree and ack."*
   - **Non-emergency (default):** keep working — finish the plan's active cycle, except a last
     cycle awaiting the pre-merge gate.

**Emergency (1B):**
2. Fast-abort — no finishing of the active cycle, no merge.

## Guardrails
- **Fast-abort (skip finishing the active cycle + CR merge) is permitted ONLY under the `emergency` flag.**
  A normal shutdown ALWAYS finishes the plan's active cycle, except a last cycle awaiting the
  pre-merge gate, and commits a clean tree.
"""

GOOD_TRACK = """# Orchestration — TRACK

## HOLD the merge for Mainline's relayed approval
- The ONE user-facing gate is the MERGE. The sign-off follows close-out steps 1–4 (`orchestration-common.md` § Close-out); present VERIFY to Mainline and HOLD.

## On a shutdown directive — invoke the `/shutdown` skill
- **Graceful (default):** finish the active step; if mid-CR with an active cycle on the plan, **ESCALATE to Mainline** (mid-cycle, will finish the active cycle then ack); finish the plan's active cycle, except a last cycle awaiting the pre-merge gate; leave a clean worktree.
- **`emergency` flag:** close only the active write, fast-abort (no drain/merge), best-effort ack.
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

GOOD_S4_MODEL_B = """# Model B

## 4. Universal conventions (PRD §D3 — every project instantiates these)

1. **Naming registry + static init:** CR ids `CR-<ACRONYM>-NNN`, Crucible agentId `<agent-type>-<project>` for an orchestrator and `CR-<ACRONYM>-NNN-<cycle id>-<ROLE>` for a TDD-role agent (e.g. `CR-MDB-059-237-RED`); the role is declared with `--role`, and the role suffix is a readability habit, never parsed.
2. **Queue idiom:** the board holds the queue.
3. **Plan/cycle idiom:** `plan-file --cr <id> --title <t> --cycle "<label>" --cycle-kind red-green --cycle "<label>" --cycle-kind verify --wave <n> --agent <registered-id>`; server-assigned cycle ids only; cycle labels `<label> (§S…)`.

## 5. Role routing
"""

GOOD_S4_CRUCIBLE = """# Crucible

## Identity — ONE agent id for the whole session

- Orchestrators: `<agent-type>-<project>`.
- TDD-role agents: `CR-<ACRONYM>-NNN-<cycle id>-<ROLE>` (e.g. `CR-MDB-059-237-RED`), the cycle's server id.

## Workflow classification — cycle attach + display context

- **Plan verbs:** `plan-file --cr <id> --title <t> --cycle "<label>" --cycle-kind red-green --cycle "<label>" --cycle-kind verify --wave <w> --agent <id>`.
"""

GOOD_S4_COMMON = """# Orchestration — COMMON

## Parallel agents in one tree
- **Agent ids are suffixed `-1` … `-N`** on the phase's id (e.g. `CR-MDB-059-237-GREEN-2`).

## Integration
- x
"""

GOOD_S4_CONTRACT = """# Crucible envelope

### Universal plan verbs (fleet-wide)
- `plan-file --cr <id> --title <t> --cycle "<label>" --cycle-kind red-green --cycle "<label>" --cycle-kind verify --wave <w> --agent <id>`

### Agent-naming header (bundled agent-naming skill)
- TDD-ROLE agents: `CR-<PROJ>-NNN-<cycle id>-<ROLE>` (e.g. `CR-MDB-059-237-GREEN`) — a
  readability habit, never a parsed key.
- The older spelling of the same habit, `CR-<PROJ>-NNN-<cycle>-<PHASE>`, is superseded.

## Filed requests / gaps
"""

GOOD_S4_AGENTS = """# Repository Guidelines

## Testing & QA

```bash
python3 ~/.crucible/clients/python-crucible.py test --tests tests.test_hooks --agent CR-MDB-NNN-<cycle id>-RED  # one module
python3 ~/.crucible/clients/python-crucible.py test --tests tests.test_contracts.ContractsS2Test --agent CR-MDB-059-237-RED  # one class
python3 ~/.crucible/clients/python-crucible.py test --agent vidushi-mdb --log /tmp/full.log  # full suite
```

- **Agent ids:** free-form — TDD-role agents by convention `CR-MDB-NNN-<cycle id>-<ROLE>` (e.g. `CR-MDB-059-237-RED`), the spec pre-review `CR-MDB-NNN-SPEC-REVIEW`, orchestrator ops `vidushi-mdb`.
- **The suite is expected to be GREEN.** Baselines for the full suite, measured 2026-10-16 at CR-MDB-059's `Cycle labels, agent ids and the worktree-flow cycle field (§S4)` cycle:
  - real `HOME`: **3400 tests, 0 failures, 0 errors, 1 skip**.

## Workflow Rules (Model B, solo)

- Plans are filed via the client: `plan-file --cr <id> --title <t> --cycle "<label>" --cycle-kind red-green --cycle "<label>" --cycle-kind verify --wave <n> --agent vidushi-mdb`. Cycle labels: `<label> (§S…)`.
- Post a `milestone` at every workflow moment: `--type stage-flip --label "<CR> <cycle label> done"` at each cycle-done.
"""

GOOD_S4_WORKTREE_TS = """/**
 * Worktree isolation (CR-MDB-039 §S1).
 *
 * `prepare` sends a child to the registered git worktree `.worktrees/<CR>`
 * of the CR id that OPENS the dispatch description (`CR-MDB-039-237-RED`; a CR
 * id elsewhere does not route).
 */

const CR_ID_RE = /^CR-[A-Z][A-Z0-9]*-[0-9]+/;
"""

#: §S5 — four of the numbered close-out steps of ``GOOD_COMMON``, for the order proofs (F1).
STEP_5 = "5. The merge sign-off.\n"
STEP_6 = ("6. The spec's `**Status:**` flip, a docs-only commit and still the last commit on the "
          "branch.\n")
STEP_7 = "7. The merge.\n"
STEP_8 = "8. `cr-close`.\n"

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
        S2_CR_AUTHORING[1][0]: ", since `plan-file` takes no `--points`",
        S2_CR_AUTHORING[2][0]: "1, 2, 3, 5, 8, 13",
        S2_CR_AUTHORING[3][0]: "13 is the cap; ",
        S2_CR_AUTHORING[4][0]: ", each scored with `--points`",
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
        S5_COMMON_CLOSE_OUT[6][0]: (", and `unregister` then\n  `register` clears the orchestrator's "
                                    "binding"),
        S5_COMMON_CLOSE_OUT[7][0]: " inside that new last cycle",
        S5_COMMON_CLOSE_OUT[8][0]: " follows the same path",
        S5_COMMON_CLOSE_OUT[9][0]: "the post-merge develop gate;",
        S5_COMMON_CLOSE_OUT[10][0]: " (every earlier cycle done)",
        S5_COMMON_CLOSE_OUT[11][0]: (", and its `cr-close` takes its last commit on the release "
                                     "branch"),
    }),
    "S5 orchestration-track sign-off": (GOOD_TRACK, {
        S5_TRACK_SIGN_OFF[0][0]: ("The sign-off follows close-out steps 1–4 "
                                  "(`orchestration-common.md` § Close-out); "),
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
    "S4 model-b 4.1": (GOOD_S4_MODEL_B, {
        S4_MODEL_B_41[0][0]: " and `CR-<ACRONYM>-NNN-<cycle id>-<ROLE>` for a TDD-role agent",
        S4_MODEL_B_41[1][0]: ", never parsed",
    }),
    "S4 model-b 4.3": (GOOD_S4_MODEL_B, {
        S4_MODEL_B_43[0][0]: "; cycle labels `<label> (§S…)`",
    }),
    "S4 crucible identity": (GOOD_S4_CRUCIBLE, {
        S4_CRUCIBLE_IDENTITY[0][0]: " (e.g. `CR-MDB-059-237-RED`)",
    }),
    "S4 orchestration-common parallel agents": (GOOD_S4_COMMON, {
        S4_COMMON_PARALLEL[0][0]: "`CR-MDB-059-237-GREEN-2`",
    }),
    "S4 contracts agent-naming": (GOOD_S4_CONTRACT, {
        S4_CONTRACT[0][0]: "`CR-<PROJ>-NNN-<cycle id>-<ROLE>` ",
    }),
    "S4 AGENTS.md agent ids": (GOOD_S4_AGENTS, {
        S4_AGENTS_IDS[0][0]: "`CR-MDB-NNN-<cycle id>-<ROLE>` ",
    }),
    "S4 AGENTS.md workflow rules": (GOOD_S4_AGENTS, {
        S4_AGENTS_WORKFLOW[0][0]: " --label \"<CR> <cycle label> done\"",
        S4_AGENTS_WORKFLOW[1][0]: " Cycle labels: `<label> (§S…)`.",
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

    def test_the_order_detector_reads_the_numbered_steps_only(self):
        """F1: proved with the bullets after the list present — the whole region lets them
        supply a step (the defect), the numbered steps alone bite."""
        good = common_close_out(GOOD_COMMON)
        self.assertIn("Steps 6 and 8 bracket the merge", good, "the trailing bullets are kept")
        self.assertEqual(len(numbered_steps(good)), 8, numbered_steps(good))
        self.assertEqual(order_findings("\n".join(numbered_steps(good)), CLOSE_OUT_ORDER), [])
        cases = {
            "swap 6/7": (good.replace(STEP_6 + STEP_7, STEP_7.replace("7.", "6.")
                                      + STEP_6.replace("6.", "7.")),
                         "step 7 (the merge) is missing or out of order"),
            "swap 7/8": (good.replace(STEP_7 + STEP_8, STEP_8.replace("8.", "7.")
                                      + STEP_7.replace("7.", "8.")),
                         "step 8 (cr-close) is missing or out of order"),
            "delete 5": (good.replace(STEP_5, ""),
                         "step 5 (the merge sign-off) is missing or out of order"),
        }
        for name, (text, finding) in cases.items():
            with self.subTest(case=name):
                self.assertNotEqual(text, good, "the case must change the sample")
                self.assertEqual(order_findings(text, CLOSE_OUT_ORDER), [],
                                 "the whole region lets the trailing bullets supply the step")
                self.assertEqual(
                    order_findings("\n".join(numbered_steps(text)), CLOSE_OUT_ORDER), [finding])

    # MIGRATED at CR-MDB-059 (§S5): the close-out sample now keeps the bullets after the list, so
    # its order is read from the numbered steps, as the shipped gate reads it (F1).
    def test_the_order_detector_both_ways(self):
        def steps(region: str) -> str:
            return "\n".join(numbered_steps(region))

        good = common_close_out(GOOD_COMMON)
        self.assertEqual(order_findings(steps(good), CLOSE_OUT_ORDER), [])
        self.assertEqual(order_findings(common_close_out(GOOD_AGENTS.replace(
            "## Workflow Rules (Model B, solo)", "## Close-out")), CLOSE_OUT_ORDER), [])
        swapped = good.replace("3. `cycle-done`.", "3. Hold.").replace(
            "5. The merge sign-off.", "5. `cycle-done`, then the merge sign-off.")
        self.assertEqual(order_findings(steps(swapped), CLOSE_OUT_ORDER),
                         ["step 4 (unregister, then register) is missing or out of order"])
        dropped = good.replace("1. Merge `develop` into the feature branch until behind=0.",
                               "1. Rebase.")
        self.assertEqual(order_findings(steps(dropped), CLOSE_OUT_ORDER),
                         ["step 1 (merge develop into the feature branch until behind=0) is "
                          "missing or out of order"])
        last = good.replace("8. `cr-close`.", "8. Done.")
        self.assertEqual(order_findings(steps(last), CLOSE_OUT_ORDER),
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

    # MIGRATED at CR-MDB-059 (§S5): the "always finishes" proof widens to every form (F5).
    def test_the_unexcepted_finish_detector_both_ways(self):
        for good in (GOOD_SHUTDOWN, GOOD_TRACK):
            with self.subTest(sample=good.splitlines()[0]):
                self.assertEqual(unexcepted_finish_findings(good), [])
        self.assertIn("finishes its plan's active cycle", GOOD_SHUTDOWN,
                      "precondition: the frontmatter description says it, with no exception")
        cuts = {
            "intro graceful bullet": (" (except a last\n  cycle awaiting the pre-merge gate, "
                                      "which stays active)", "- graceful (default)"),
            "Track paragraph": (" (except a last cycle awaiting the\n  pre-merge gate)",
                                "- track is normally"),
            "Step 1A": (", except when that cycle is the last one and its pre-merge gate has "
                        "not run", "nothing is abandoned"),
            "Step 2A quote": (" (unless it is the last one, awaiting the\n   pre-merge gate)",
                              "2. mid-cr"),
            "Step 2A bullet": (", except a last\n     cycle awaiting the pre-merge gate",
                               "- non-emergency (default)"),
            "guardrails": (", except a last cycle awaiting the\n  pre-merge gate", "- fast-abort"),
        }
        for name, (cut, opens) in cuts.items():
            with self.subTest(site=name):
                self.assertIn(cut, GOOD_SHUTDOWN)
                found = unexcepted_finish_findings(GOOD_SHUTDOWN.replace(cut, ""))
                self.assertEqual(len(found), 1, found)
                self.assertTrue(found[0].startswith(opens), found)
        track_cut = ", except a last cycle awaiting the pre-merge gate"
        self.assertIn(track_cut, GOOD_TRACK)
        found = unexcepted_finish_findings(GOOD_TRACK.replace(track_cut, ""))
        self.assertEqual(len(found), 1, found)
        self.assertTrue(found[0].startswith("- graceful (default):"), found)

    def test_the_unexcepted_finish_detector_leaves_the_emergency_not_finishing_alone(self):
        for line in ("- Fast-abort — do NOT finish the active cycle.\n",
                     "- Emergency — (skip finishing the active cycle, no merge).\n",
                     "2. Fast-abort — no finishing of the active cycle, no merge.\n"):
            with self.subTest(line=line):
                self.assertEqual(unexcepted_finish_findings(line), [])
        self.assertEqual(len(unexcepted_finish_findings(
            "- Graceful: finish the active cycle, unless told to emergency-stop.\n")), 1,
            "an exception that is not the pre-merge gate's does not count")

    def test_the_exception_site_detector_both_ways(self):
        self.assertEqual(exception_site_findings(GOOD_SHUTDOWN, SHUTDOWN_EXCEPTION_SITES), [])
        self.assertEqual(exception_site_findings(GOOD_TRACK, TRACK_EXCEPTION_SITES), [])
        cuts = {
            "the introduction's graceful bullet": (" (except a last\n  cycle awaiting the "
                                                   "pre-merge gate, which stays active)"),
            "the introduction's Track paragraph": (" (except a last cycle awaiting the\n  "
                                                   "pre-merge gate)"),
            "Step 1A": (", except when that cycle is the last one and its pre-merge gate has "
                        "not run"),
            "the guardrails": ", except a last cycle awaiting the\n  pre-merge gate",
        }
        self.assertEqual(sorted([*cuts, "Step 2A"]),
                         sorted(n for n, _r, _l in SHUTDOWN_EXCEPTION_SITES))
        for name, cut in cuts.items():
            with self.subTest(site=name):
                self.assertIn(cut, GOOD_SHUTDOWN)
                self.assertEqual(exception_site_findings(GOOD_SHUTDOWN.replace(cut, ""),
                                                         SHUTDOWN_EXCEPTION_SITES), [name])
        both_2a = GOOD_SHUTDOWN.replace(
            " (unless it is the last one, awaiting the\n   pre-merge gate)", "").replace(
            ", except a last\n     cycle awaiting the pre-merge gate", "")
        self.assertEqual(exception_site_findings(both_2a, SHUTDOWN_EXCEPTION_SITES),
                         ["Step 2A"])
        self.assertEqual(exception_site_findings(
            GOOD_TRACK.replace(", except a last cycle awaiting the pre-merge gate", ""),
            TRACK_EXCEPTION_SITES), ["the graceful-shutdown line"])

    def test_the_unbound_list_detector_both_ways(self):
        good = common_close_out(GOOD_COMMON)
        self.assertEqual(unbound_list_findings(good), [])
        run_on = good.replace("The rest of the close-out:\n\n", "")
        self.assertNotEqual(run_on, good)
        self.assertEqual(unbound_list_findings(run_on), [
            "the unbound list runs to 7 items, not 3: no non-list line ends it before the next "
            "bullets"])
        self.assertEqual(unbound_list_findings("- baselines;\n"), ["0 unbound-list leads, not one"])

    def test_the_plan_file_points_detector_both_ways(self):
        self.assertEqual(plan_file_points_spans(GOOD_CR_AUTHORING), [])
        retired = GOOD_CR_AUTHORING.replace(
            "with `cr-plan --points <n> --agent <id>`; a CR filed by `plan-file --release` is "
            "scored the same way, since `plan-file` takes no `--points`.",
            "(`cr-plan --points`, or `plan-file --release … --points`).")
        self.assertNotEqual(retired, GOOD_CR_AUTHORING)
        self.assertEqual(plan_file_points_spans(retired), ["plan-file --release … --points"])
        wrapped = "- File it with `plan-file --cr <id>\n  --points 3`.\n"
        self.assertEqual(plan_file_points_spans(wrapped), ["plan-file --cr <id> --points 3"],
                         "a span wrapped across lines still counts")
        self.assertEqual(plan_file_points_spans("- `cr-plan --points <n>`; `plan-file`.\n"), [])


class CycleIdDetectorsOnSyntheticTextTest(unittest.TestCase):
    """§S4's detectors proved both ways: the new forms pass, today's retired forms bite."""

    maxDiff = None

    def test_the_label_gate_file_set_both_ways(self):
        tmp = tempfile.TemporaryDirectory(prefix="modelb-label-gate-")
        with tmp:
            root = build_tree(tmp.name, (
                "skills-src/model-b/SKILL.md", "skills-src/model-b/references/deep/x.md",
                "skills-src/CRUCIBLE-HANDOVER.md", "skills-src/crucible/references/rust.md",
                "skills-src/crucible-report-python/SKILL.md", "skills-src/crucible-register/SKILL.md",
                "skills-src/model-b/notes.txt", "generator/templates/red.md.tmpl",
                "generator/stacks/python.toml", "generator/agents/python-red-agent.md",
                "AGENTS.md", "contracts/crucible-envelope.md", "contracts/gate-lock.md",
                "docs/changes/CR-X.md", "README.md"))
            self.assertEqual(label_gate_files(root), [
                "skills-src/CRUCIBLE-HANDOVER.md", "skills-src/crucible/references/rust.md",
                "skills-src/model-b/SKILL.md", "skills-src/model-b/references/deep/x.md",
                "generator/templates/red.md.tmpl", "generator/stacks/python.toml",
                "AGENTS.md", "contracts/crucible-envelope.md"])

    def test_the_label_gate_bites_on_each_retired_form(self):
        lines = {
            "numbered-label placeholder C<n>": "cycle labels `C<n> <label> (§S…)`",
            'a --cycle "C<digits> example': 'plan-file --cycle "C2 x" --cycle-kind verify',
            "a numbered label C<digits> <label>": "a label like C3 <label>",
            "a positional agent-id tag": "(e.g. `CR-MDB-017-F1-FIX`)",
        }
        for name, line in lines.items():
            with self.subTest(form=name):
                hits = old_cycle_form_hits(MODEL_B, f"ok\n{line}\n")
                self.assertEqual(len(hits), 1, hits)
                self.assertTrue(hits[0].startswith(f"{MODEL_B}:2: {name}: "), hits)

    def test_the_agents_only_form_bites_in_agents_md_alone(self):
        line = "measured 2026-10-15 at CR-MDB-071 C5 FIX through the client\n"
        self.assertEqual(old_cycle_form_hits(AGENTS, line),
                         [f"{AGENTS}:1: a numbered cycle with a role C<digits> <ROLE>: C5 FIX"])
        self.assertEqual(old_cycle_form_hits(MODEL_B, line), [])

    def test_the_label_gate_passes_the_new_forms(self):
        for good in (GOOD_S4_MODEL_B, GOOD_S4_CRUCIBLE, GOOD_S4_COMMON, GOOD_S4_CONTRACT,
                     GOOD_S4_AGENTS):
            with self.subTest(sample=good.splitlines()[0]):
                self.assertEqual(old_cycle_form_hits(AGENTS, good), [])

    def test_the_ac_literal_c_n_pattern_misses_the_form_it_retires(self):
        """Why ``OLD_CYCLE_FORMS`` drops the AC's trailing ``\\b``: taken literally it never
        fires on ``C<n> <label>``."""
        line = "cycle labels `C<n> <label> (§S…)`"
        self.assertIsNone(re.search(r"\bC<n>\b", line))
        self.assertEqual(len(old_cycle_form_hits(MODEL_B, line)), 1)

    def test_the_section_4_1_single_line_check_both_ways(self):
        self.assertNotIn("\n", model_b_item_1(GOOD_S4_MODEL_B).strip())
        wrapped = GOOD_S4_MODEL_B.replace("; the role is declared", ";\n   the role is declared")
        self.assertIn("\n", model_b_item_1(wrapped).strip())

    def test_the_plan_file_label_detector_both_ways(self):
        for region_of, good in ((model_b_item_3, GOOD_S4_MODEL_B),
                                (crucible_workflow_classification, GOOD_S4_CRUCIBLE),
                                (contract_plan_verbs, GOOD_S4_CONTRACT),
                                (agents_workflow_rules, GOOD_S4_AGENTS)):
            with self.subTest(region=region_of.__name__):
                self.assertEqual(plan_file_label_findings(region_of(good)), [])
                old = good.replace('--cycle "<label>" --cycle-kind red-green',
                                   '--cycle "C1 <label>" --cycle-kind red-green')
                self.assertEqual(len(plan_file_label_findings(region_of(old))), 1)
        self.assertEqual(plan_file_label_findings("- `plan-file --cr <id> --agent <id>`\n"),
                         ["no plan-file example shows --cycle"])

    def test_the_reference_id_form_detector_both_ways(self):
        good = ("# Python\n\n- Agent naming: `CR-<ACRONYM>-NNN-<cycle id>-<ROLE>` for TDD-role "
                "agents;\n  `<agent-type>-<project>` for orchestrators.\n")
        self.assertEqual(reference_id_form_findings(dict.fromkeys(REFERENCE_STACKS, good)), [])
        old = good.replace("<cycle id>-<ROLE>", "<cycle>-<PHASE>")
        self.assertEqual(reference_id_form_findings({"python": good, "rust": old}), [
            "rust: still writes <PHASE>",
            "rust: the TDD form is ['CR-<ACRONYM>-NNN-<cycle>-<PHASE>'], not "
            "['CR-<ACRONYM>-NNN-<cycle id>-<ROLE>']"])
        drifted = good.replace("<cycle id>-<ROLE>", "<cycle>-<ROLE>")
        self.assertEqual(len(reference_id_form_findings({"java": drifted})), 1,
                         "parity: every reference gives the one form")
        self.assertEqual(reference_id_form_findings({"bun": "# Bun\n"}),
                         ["bun: 0 'Agent naming:' bullets, not one"])

    def test_the_agents_test_command_detector_both_ways(self):
        good = agents_testing(GOOD_S4_AGENTS)
        self.assertEqual(agents_test_command_findings(good), [])
        old = good.replace("--agent CR-MDB-059-237-RED", "--agent CR-MDB-NNN-C1-RED")
        found = agents_test_command_findings(old)
        self.assertEqual(len(found), 1, found)
        self.assertIn("CR-MDB-NNN-C1-RED", found[0])
        self.assertEqual(agents_test_command_findings("```bash\nls\n```\n"),
                         ["no --tests client run"])

    def test_the_baseline_citation_detector_both_ways(self):
        good = agents_testing(GOOD_S4_AGENTS)
        self.assertEqual(baseline_citation_findings(good), [])
        old = re.sub(r"at CR-MDB-059's `[^`]+` cycle", "at CR-MDB-071 C5 FIX", good)
        self.assertNotEqual(old, good)
        self.assertEqual(len(baseline_citation_findings(old)), 1)

    def test_the_docstring_id_detector_both_ways(self):
        doc = leading_block_comment(GOOD_S4_WORKTREE_TS)
        self.assertIn("OPENS the dispatch description", doc)
        self.assertNotIn("CR_ID_RE", doc, "only the leading comment is read")
        self.assertEqual(docstring_id_findings(doc), [])
        old = doc.replace("`CR-MDB-039-237-RED`", "`CR-MDB-039 C1 RED`")
        self.assertEqual(docstring_id_findings(old), [
            "no agent-id example in the cycle-id form", "numbered tag: CR-MDB-039 C1 RED"])
        self.assertEqual(leading_block_comment("const x = 1;\n"), "")


if __name__ == "__main__":
    unittest.main()
