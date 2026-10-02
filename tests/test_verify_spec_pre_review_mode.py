"""The VERIFY agent's spec pre-review mode, and branch verification scoped as such
(CR-MDB-046 §S3; PRD D6, amended 2026-09-27: a spec is reviewed before it is approved, and the
pre-review proceeds unregistered when Crucible is down; PRD D5).

Contract: ``docs/changes/CR-MDB-046-gap-analysis-reach-and-spec-review.md`` §S3 and its ACs
"Every rendered VERIFY agent", "Branch-mode scoping" and "Other agents unchanged". Asserted on the
RENDERED agents — every stack (globbed from ``generator/stacks/*.toml``), each in its lean-ctx form
and its built-in form, rendered in memory by ``modelb_axi.agents.render`` from the committed
templates, stack files and ``builtin-tools.toml`` (``generator/build.py --check`` keeps the
committed ``generator/agents/`` in step; it is gated in ``tests.test_generator_role_contract``).

What is pinned (the patterns are the spec's own words; the rest of each sentence is free):

- **One section, placed after First Actions.** Exactly one heading ``Spec pre-review mode`` (a
  suffix is allowed), at First Actions' level, and it is the next section after First Actions
  (``pre_review_placement_findings``).
- **Its rules** (``PRE_REVIEW_RULES``, each read in ONE bullet or paragraph of that section):
  branch verification stays the default; the mode applies only when the brief declares it
  explicitly, never inferred from a missing cycle or from the agent id; it registers
  ``--role report`` with no ``--cycle`` under the id the brief gives; Crucible down or absent →
  proceeds unregistered and says so in its report; it reads the whole spec, its design reference
  and the current code; it applies the ``gap-analysis`` skill's Dimensions 1–10 read-only, and the
  skill's Step 0 and Rule 1 do not apply; no test suite, no ingest, no edit, no commit; a ``/tmp``
  sandbox only where reading cannot settle a case; findings F1…Fn, each naming the spec section or
  AC it needs and whether it adds scope or corrects it; it unregisters when registered. The section
  cites the skill by its installed path, as the agent cites ``sub-agent-procedure.md``
  (``SKILL_CITATION``). The output-format rule is read in prose: a fenced template may accompany
  it, but fenced lines are not a bullet or paragraph.
- **The registration command** (``report_command_findings``): exactly one stack register command
  carrying ``--role report``, inside the pre-review section, binding no ``--cycle``, after the
  branch-mode register command (``--role VERIFY --cycle``), which stays.
- **Branch-mode scoping** (``branch_scope_findings``): every statement of First Actions' cycle
  requirement, the targeted regression and the ingest (in First Actions, What You Do and Final
  Actions), every statement under Gate Criteria, the output format's Regression line, and the
  report ending the VERIFY cycle's work is scoped to branch verification — by the statement
  itself, or by a heading it sits under. Each site must also still be stated.
- **The stack's VERIFY gotchas** (``gotchas_scope_findings``): the section holding each stack's
  rendered ``[gotchas].verify`` is stated as branch-verification specifics (its heading or a unit
  of it), and their mandated runs are said not to apply in the pre-review mode (in that section,
  or in the pre-review section naming the stack specifics).
- **The built-in form renders** for every stack — ``builtin_form`` refuses a body still naming
  lean-ctx, so a lean-ctx phrase the new section adds needs its ``builtin-tools.toml`` passage.
- **Other agents** carry no pre-review mode and no ``report`` registration, in both forms.

A rule is read phrase-level in one unit: a list item with its nested items, or a paragraph
(``units`` from ``tests.test_gap_analysis_reach_and_pre_review``: ``rule_units`` with each table row
a unit), normalised (lower-cased, backticks and ``*`` dropped). Every detector is a pure function
returning problem strings (``[]`` = clean), proven both ways on synthetic text in
``PreReviewModeDetectorTest``; no test pins a line number.

Hermetic: reads only repo files. Stdlib only.
"""

import re
import unittest
from functools import cache

from modelb_axi.agents import AgentRenderError, load_stack_params, render
from tests._helpers import split_frontmatter
from tests.test_bootstrap_shutdown_registry import normalise
from tests.test_gap_analysis_reach_and_pre_review import missing, units
from tests.test_generator_role_contract import (
    STACKS_DIR,
    TEMPLATES_DIR,
    _role_names,
    _stack_names,
)
from tests.test_orchestrator_rule_triage import markdown_headings

FORMS = (("lean-ctx", True), ("built-in", False))

#: A heading or statement scoping a rule to branch verification.
BRANCH = r"\bbranch[- ]verification\b|\bbranch[- ]mode\b"

PRE_REVIEW_HEADING = re.compile(r"^spec pre-review mode\b")
FIRST_ACTIONS_HEADING = re.compile(r"^first actions\b")
#: The sections whose statements of the cycle requirement, regression and ingest are mandates.
MANDATE_HEADING = re.compile(r"^(?:first actions|what you do|final actions)\b")
GATE_HEADING = re.compile(r"^gate criteria\b")

NO_CYCLE = (r"\bno --cycle\b|\bwithout (?:a |any )?--cycle\b|\bno cycle\b(?!\s+id)"
            r"|\bwithout (?:a )?cycle\b(?!\s+id)")
NOT_APPLY = r"\b(?:do(?:es)? not|don't|never)\s+(?:appl(?:y|ies)|run)\b"
TEN_DIMENSIONS = r"\bdimensions? 1\s*[–-]\s*10\b|\ball ten dimensions\b"
NO_SUITE = (r"\bruns? no (?:test )?suites?\b|\bno test suites?\b"
            r"|\bnever runs? (?:a |the |any )?(?:test )?suites?\b")
NO_INGEST = r"\bingests? nothing\b|\bno ingest\b|\bnever ingests?\b"
NO_EDIT = r"\bedits? nothing\b|\bno edits?\b|\bnever edits?\b"
NO_COMMIT = r"\bcommits? nothing\b|\bno commits?\b|\bnever commits?\b"

#: §S3 — the rules of the "Spec pre-review mode" section, each in one unit.
PRE_REVIEW_RULES = {
    "trigger: branch verification stays the default": (BRANCH, r"\bdefault\b"),
    "trigger: only when the brief declares it explicitly": (
        r"\bbrief\b", r"\bdeclar\w*\b", r"\bexplicit\w*\b"),
    "trigger: never inferred from a missing cycle or from the agent id": (
        r"\b(?:never|not)\s+(?:be\s+)?inferred\b", r"\bcycle\b", r"\bagent id\b"),
    "registration: --role report with no --cycle, under the id the brief gives": (
        r"--role report\b", NO_CYCLE, r"\bbrief\b"),
    "Crucible down or absent: proceeds unregistered and says so in its report": (
        r"\bcrucible\b", r"\bdown\b|\babsent\b", r"\bunregistered\b", r"\breport\b"),
    "reads the whole spec, its design reference and the current code": (
        r"\bwhole spec\b", r"\bdesign reference\b", r"\bcurrent code\b"),
    "applies the gap-analysis skill's Dimensions 1–10 read-only": (
        r"\bgap-analysis\b", TEN_DIMENSIONS, r"\bread-only\b"),
    "the skill's Step 0 and Rule 1 do not apply": (
        r"\bstep 0\b", r"\brule 1\b", r"\b(?:do(?:es)? not|don't|never)\s+appl(?:y|ies)\b"),
    "runs no test suite, ingests nothing, edits nothing, commits nothing": (
        NO_SUITE, NO_INGEST, NO_EDIT, NO_COMMIT),
    "a /tmp sandbox only where reading cannot settle a case": (
        r"/(?:tmp)\b", r"\bsandbox\b", r"\breading cannot settle\b"),
    "findings F1…Fn, each naming the spec section or AC, and whether it adds or corrects scope": (
        r"\bf1\b", r"\bfn\b", r"\bspec section\b|§\s?s\d", r"\bacs?\b", r"\badds?\b",
        r"\bscope\b", r"\bcorrects?\b"),
    "unregisters when registered": (
        r"\bunregisters?\b", r"\b(?:when|if)\b.{0,30}\bregistered\b"),
}

#: The skill, cited by its installed path as ``sub-agent-procedure.md`` is (normalised form).
SKILL_CITATION = "~/.agents/skills/gap-analysis/skill.md"

#: Branch-mode mandate markers (read in units of the mandate sections).
CYCLE_REQUIREMENT = (r"--cycle\b", r"\brequired\b")
TARGETED_REGRESSION = r"\btargeted regression\b|\baffected targets\b|\btargeted results\b"
INGEST = r"\bingest\w*\b"
INGEST_NEGATED = NO_INGEST
ENDS_CYCLE = r"\bends?\b.{0,40}\bverify cycle\b"
REGRESSION_LINE = re.compile(r"^\s*#{1,6}\s*regression\b", re.IGNORECASE)

BRANCH_SITES = (
    "cycle requirement",
    "targeted regression",
    "ingest",
    "Gate Criteria",
    "Regression line",
    "report ends the VERIFY cycle's work",
)

#: A pre-review-section unit naming the stack's VERIFY specifics.
STACK_SPECIFICS_NAMED = r"\bverify specifics\b|\bgotchas\b|\bstack(?:'s)? (?:verify )?specifics\b"

#: What a RED, GREEN or FIX agent must never carry.
PRE_REVIEW_LEAK = re.compile(r"pre-review|--role\s+`?report\b", re.IGNORECASE)


# ------------------------------------------------------------------ reading ----

def sections(body: str) -> list[dict]:
    """Every heading's own text (up to the next heading of any level) with its ``chain`` — the
    normalised texts of the heading and its ancestors; the text before the first heading has an
    empty chain. Headings inside fenced code are not headings."""
    lines = body.splitlines()
    heads = markdown_headings(body)
    out = [{"chain": [], "start": 0,
            "text": "\n".join(lines[:heads[0][0]] if heads else lines)}]
    open_heads: list[tuple[int, str]] = []
    for n, (idx, level, htext) in enumerate(heads):
        while open_heads and open_heads[-1][0] >= level:
            open_heads.pop()
        open_heads.append((level, normalise(htext)))
        end = heads[n + 1][0] if n + 1 < len(heads) else len(lines)
        out.append({"chain": [h for _, h in open_heads], "start": idx + 1,
                    "text": "\n".join(lines[idx + 1:end])})
    return out


def _chain_has(chain: list[str], rx: re.Pattern) -> bool:
    return any(rx.match(h) for h in chain)


def _scoped(unit: str, chain: list[str]) -> bool:
    return any(re.search(BRANCH, text) for text in [*chain, unit])


def pre_review_bounds(body: str) -> list[tuple[int, int]]:
    """``(first, end)`` line indices of every "Spec pre-review mode" section, heading included,
    up to the next heading of the same or a higher level."""
    heads = markdown_headings(body)
    total = len(body.splitlines())
    bounds = []
    for n, (idx, level, htext) in enumerate(heads):
        if PRE_REVIEW_HEADING.match(normalise(htext)):
            end = next((j for j, lvl, _ in heads[n + 1:] if lvl <= level), total)
            bounds.append((idx, end))
    return bounds


def pre_review_sections(body: str) -> list[str]:
    lines = body.splitlines()
    return ["\n".join(lines[first + 1:end]) for first, end in pre_review_bounds(body)]


def pre_review_placement_findings(body: str) -> list[str]:
    """Exactly one "Spec pre-review mode" section, at First Actions' level, directly after it."""
    heads = markdown_headings(body)
    pre = [n for n, (_, _, h) in enumerate(heads) if PRE_REVIEW_HEADING.match(normalise(h))]
    if len(pre) != 1:
        return [f"expected exactly one 'Spec pre-review mode' section, found {len(pre)}"]
    first = [n for n, (_, _, h) in enumerate(heads) if FIRST_ACTIONS_HEADING.match(normalise(h))]
    if len(first) != 1:
        return [f"expected exactly one 'First Actions' section, found {len(first)}"]
    fa_level = heads[first[0]][1]
    following = next((k for k in range(first[0] + 1, len(heads)) if heads[k][1] <= fa_level), None)
    if heads[pre[0]][1] != fa_level or following != pre[0]:
        return ["the 'Spec pre-review mode' section is not the section directly after First "
                "Actions, at its level"]
    return []


def pre_review_rule_findings(body: str) -> list[str]:
    """The ``PRE_REVIEW_RULES`` no single unit of the pre-review section states, and the skill's
    citation when the section lacks it."""
    found = pre_review_sections(body)
    if len(found) != 1:
        return [f"expected exactly one 'Spec pre-review mode' section, found {len(found)}"]
    section = found[0]
    problems = [f"{name} — {missing(section, rule)}" for name, rule in PRE_REVIEW_RULES.items()
                if not any(all(re.search(p, u) for p in rule) for u in units(section))]
    if SKILL_CITATION not in normalise(section):
        problems.append(f"the section does not cite the skill as {SKILL_CITATION}")
    return problems


def report_command_findings(body: str, register_command: str) -> list[str]:
    """Exactly one register command with ``--role report``, inside the pre-review section, binding
    no ``--cycle``, after the branch-mode command ``--role VERIFY --cycle``, which stays."""
    lines = body.splitlines()
    branch = [i for i, ln in enumerate(lines)
              if register_command in ln and re.search(r"--role VERIFY(?![\w-])", ln)
              and re.search(r"--cycle(?![\w-])", ln)]
    report = [i for i, ln in enumerate(lines)
              if register_command in ln and re.search(r"--role report(?![\w-])", ln)]
    problems = []
    if not branch:
        problems.append("no branch-mode register command (--role VERIFY --cycle)")
    if len(report) != 1:
        problems.append(f"expected exactly one `--role report` register command, found "
                        f"{len(report)}")
        return problems
    at = report[0]
    if re.search(r"--cycle(?![\w-])", lines[at]):
        problems.append("the `--role report` command binds a --cycle")
    if branch and at < branch[0]:
        problems.append("the `--role report` command comes before the branch-mode command")
    if not any(first < at < end for first, end in pre_review_bounds(body)):
        problems.append("the `--role report` command is not in the 'Spec pre-review mode' section")
    return problems


def branch_scope_findings(body: str) -> list[str]:
    """Each branch-mode non-negotiable site still stated, and every statement of it scoped to
    branch verification (the statement itself, or a heading it sits under). The pre-review
    section is outside the check."""
    flags: dict[str, list[bool]] = {site: [] for site in BRANCH_SITES}
    for sec in sections(body):
        chain = sec["chain"]
        if _chain_has(chain, PRE_REVIEW_HEADING):
            continue
        sec_units = units(sec["text"])
        if _chain_has(chain, MANDATE_HEADING):
            for u in sec_units:
                if all(re.search(p, u) for p in CYCLE_REQUIREMENT) and not re.search(NO_CYCLE, u):
                    flags["cycle requirement"].append(_scoped(u, chain))
                if re.search(TARGETED_REGRESSION, u):
                    flags["targeted regression"].append(_scoped(u, chain))
                if re.search(INGEST, u) and not re.search(INGEST_NEGATED, u):
                    flags["ingest"].append(_scoped(u, chain))
        if _chain_has(chain, GATE_HEADING):
            flags["Gate Criteria"].extend(_scoped(u, chain) for u in sec_units)
        for u in sec_units:
            if re.search(ENDS_CYCLE, u):
                flags["report ends the VERIFY cycle's work"].append(_scoped(u, chain))
        noted = any(re.search(r"\bregression\b", u) and re.search(BRANCH, u) for u in sec_units)
        for line in sec["text"].splitlines():
            if REGRESSION_LINE.match(line):
                flags["Regression line"].append(noted or _scoped(normalise(line), chain))
    problems = []
    for site, marks in flags.items():
        if not marks:
            problems.append(f"{site}: not stated at all")
        elif not all(marks):
            problems.append(f"{site}: {marks.count(False)} statement(s) not scoped to branch "
                            "verification")
    return problems


def gotchas_scope_findings(body: str, gotchas: str) -> list[str]:
    """The section holding the stack's VERIFY gotchas is stated as branch-verification specifics,
    and their mandated runs are said not to apply in the pre-review mode."""
    first_line = next((ln for ln in gotchas.splitlines() if ln.strip()), "")
    locator = normalise(first_line)[:60]
    homes = [sec for sec in sections(body) if locator and locator in normalise(sec["text"])]
    if len(homes) != 1:
        return [f"the stack's VERIFY gotchas sit under {len(homes)} headings, expected one"]
    chain, home_units = homes[0]["chain"], units(homes[0]["text"])
    problems = []
    if not (any(re.search(BRANCH, h) for h in chain)
            or any(re.search(BRANCH, u) for u in home_units)):
        problems.append("the stack's VERIFY gotchas are not stated as branch-verification "
                        "specifics")
    exempt_home = any(re.search(r"\bpre-review\b", u) and re.search(NOT_APPLY, u)
                      for u in home_units)
    exempt_mode = any(re.search(STACK_SPECIFICS_NAMED, u) and re.search(NOT_APPLY, u)
                      for section in pre_review_sections(body) for u in units(section))
    if not (exempt_home or exempt_mode):
        problems.append("the gotchas' mandated runs are not said not to apply in the pre-review "
                        "mode")
    return problems


# ------------------------------------------------------------------ rendering ----

@cache
def _rendered_body(stack: str, role: str, lean_ctx: bool) -> str:
    params = load_stack_params(STACKS_DIR, stack)
    _, body = split_frontmatter(render(stack, role, params, TEMPLATES_DIR, lean_ctx=lean_ctx))
    return body


class _RenderedVerify(unittest.TestCase):
    def each_verify(self):
        """Yield ``(stack, form, body, params)`` for every stack's VERIFY agent, both forms."""
        stacks = _stack_names()
        self.assertTrue(stacks, "no stack files under generator/stacks/")
        for stack in stacks:
            params = load_stack_params(STACKS_DIR, stack)
            for form, lean in FORMS:
                try:
                    body = _rendered_body(stack, "verify", lean)
                except AgentRenderError as exc:
                    self.fail(f"{stack}-verify-agent ({form}) does not render: {exc}")
                yield stack, form, body, params


# ----------------------------------------------- §S3 — the pre-review section ----

class VerifyPreReviewSectionTest(_RenderedVerify):
    """§S3 / AC "Every rendered VERIFY agent": one "Spec pre-review mode" section after First
    Actions, stating each rule the spec gives it, in each stack and each form."""

    def test_every_verify_agent_has_exactly_one_pre_review_section_directly_after_first_actions(self):
        for stack, form, body, _ in self.each_verify():
            with self.subTest(stack=stack, form=form):
                self.assertEqual(pre_review_placement_findings(body), [],
                                 f"{stack}-verify-agent ({form})")

    def test_the_pre_review_section_states_every_rule_the_spec_gives_it(self):
        for stack, form, body, _ in self.each_verify():
            with self.subTest(stack=stack, form=form):
                self.assertEqual(pre_review_rule_findings(body), [],
                                 f"{stack}-verify-agent ({form}) § Spec pre-review mode")

    def test_the_report_registration_binds_no_cycle_and_follows_the_branch_mode_command(self):
        for stack, form, body, params in self.each_verify():
            with self.subTest(stack=stack, form=form):
                self.assertEqual(report_command_findings(body, params["register_command"]), [],
                                 f"{stack}-verify-agent ({form})")


# ------------------------------------------------- §S3 — branch-mode scoping ----

class VerifyBranchModeScopingTest(_RenderedVerify):
    """§S3 / AC "Branch-mode scoping": every branch-mode non-negotiable and every stack's
    ``[gotchas].verify`` is stated as branch verification only."""

    def test_every_branch_mode_non_negotiable_is_scoped_to_branch_verification(self):
        for stack, form, body, _ in self.each_verify():
            with self.subTest(stack=stack, form=form):
                self.assertEqual(branch_scope_findings(body), [],
                                 f"{stack}-verify-agent ({form})")

    def test_every_stacks_verify_gotchas_are_branch_specifics_whose_runs_skip_the_pre_review(self):
        for stack, form, body, params in self.each_verify():
            with self.subTest(stack=stack, form=form):
                self.assertEqual(gotchas_scope_findings(body, params["gotchas"]["verify"]), [],
                                 f"{stack}-verify-agent ({form})")


# --------------------------------------------- §S3 — built-in form, other roles ----

class VerifyBuiltinFormRendersTest(unittest.TestCase):
    """§S3 "The built-in form": every stack's VERIFY agent renders in the built-in form —
    ``builtin_form`` raises ``AgentRenderError`` on a body still naming lean-ctx — and that body
    names no lean-ctx tool. Regression pin: it fails the moment the new section adds a lean-ctx
    phrase without its ``builtin-tools.toml`` passage."""

    def test_every_verify_agent_renders_in_the_builtin_form_naming_no_lean_ctx(self):
        for stack in _stack_names():
            with self.subTest(stack=stack):
                try:
                    body = _rendered_body(stack, "verify", False)
                except AgentRenderError as exc:
                    self.fail(f"{stack}-verify-agent (built-in) does not render: {exc}")
                leftover = [ln for ln in body.splitlines()
                            if re.search(r"ctx_|(?i:lean[-_]ctx)", ln)]
                self.assertEqual(leftover, [], f"{stack}-verify-agent (built-in)")


class OtherRolesCarryNoPreReviewTest(unittest.TestCase):
    """§S3 / AC "Other agents unchanged": the pre-review mode is VERIFY's alone — no RED, GREEN or
    FIX agent, in either form, carries it or a ``report`` registration. Regression pin: it fails
    if the section or its passage leaks into another role's render."""

    def test_red_green_and_fix_renders_carry_no_pre_review_mode_or_report_registration(self):
        roles = [r for r in _role_names() if r != "verify"]
        self.assertEqual(roles, ["fix", "green", "red"])
        for stack in _stack_names():
            for role in roles:
                for form, lean in FORMS:
                    with self.subTest(stack=stack, role=role, form=form):
                        body = _rendered_body(stack, role, lean)
                        hits = [ln.strip() for ln in body.splitlines()
                                if PRE_REVIEW_LEAK.search(ln)]
                        self.assertEqual(hits, [], f"{stack}-{role}-agent ({form})")


# ------------------------------------------------- detectors, synthetic text ----

REGISTER = "stack-client register --agent YOUR_AGENT_ID"
GOTCHAS = "- **Gates to run INDEPENDENTLY:** the full native suite + ingest; report the counts.\n"

FIRST_ACTIONS_GOOD = f"""\
## First Actions (IN THIS ORDER — NON-NEGOTIABLE)

1. **Register with Crucible** with the agentId from your dispatch prompt. In branch verification,
   `--cycle` is REQUIRED for this role: an unbound TDD registration is refused by the server (409).
   ```bash
   {REGISTER} --role VERIFY --cycle <cycleId>
   ```
2. **Read project context** — AGENTS.md.
3. **Run the targeted regression** (branch verification only):
   ```bash
   stack-client test
   ```
"""

PRE_REVIEW_GOOD = f"""\
## Spec pre-review mode

- **Trigger.** Branch verification stays the default. This mode applies only when the brief
  declares it explicitly; it is never inferred from a missing cycle or from the agent id.
- **Registration.** Register `--role report` with no `--cycle`, under the id the brief gives:
  ```bash
  {REGISTER} --role report
  ```
- **Crucible down.** If Crucible is down or absent, proceed unregistered and say so in your report.
- **What you read.** Read the whole spec, its design reference and the current code.
- **The skill.** Apply the `gap-analysis` skill's Dimensions 1–10 read-only:
  `~/.agents/skills/gap-analysis/SKILL.md`. Its Step 0 (running the suites) and Rule 1 do not
  apply to you.
- **What you do not do.** You run no test suite, ingest nothing, edit nothing and commit nothing.
- **Sandbox.** You may run a `/tmp` sandbox where reading cannot settle a case.
- **Output.** Findings F1…Fn, each naming the spec section or AC it needs, and whether it adds
  scope or corrects it.
- **Last.** Unregister when registered.
"""

REST_GOOD = f"""\
## Reading the CR

Read the whole spec.

## What You Do (branch verification)

### 1. Targeted Regression
Run the AFFECTED targets only; ingest via the stack crucible client under your agent id.

## VERIFY specifics — Stack

These are branch-verification specifics: their mandated runs do not apply in the spec pre-review
mode.

{GOTCHAS}
## Output Format

In branch verification, the report carries the Regression line below.

```
## Verification Report — <CR-ID>
### Regression: PASS/FAIL (N/N green, affected targets)
```

In branch verification, your report ends the VERIFY cycle's work; no fix round runs inside it.

## Gate Criteria (branch verification)

All targeted tests pass; report the total test count.

## Final Actions (IN THIS ORDER — NON-NEGOTIABLE)

1. In branch verification, ensure targeted results were ingested.
2. **Unregister — last action.**

**Lifecycle bracket (branch verification): register → verify → ingest → unregister.**
"""

GOOD_BODY = FIRST_ACTIONS_GOOD + "\n" + PRE_REVIEW_GOOD + "\n" + REST_GOOD

#: Today's (pre-§S3) VERIFY wording, abridged: no pre-review mode, nothing scoped.
TODAY_BODY = f"""\
## First Actions (IN THIS ORDER — NON-NEGOTIABLE)

1. **Register with Crucible** via the stable stack client. `--cycle` is REQUIRED for this role:
   the cycle id is server-assigned and arrives in your dispatch prompt; never invent one.
   ```bash
   {REGISTER} --role VERIFY --cycle <cycleId>
   ```
2. **Read project context** — AGENTS.md + referenced docs.
3. **Detect the stack layout** and the affected targets, then run the targeted regression:
   ```bash
   stack-client test
   ```

## Reading the CR

Read the whole spec.

## What You Do

### 1. Targeted Regression (NO full-suite, NO coverage)
Run the AFFECTED targets only; ingest via the stack crucible client under your agent id. ALL must
pass.

## VERIFY specifics — Stack

{GOTCHAS}
## Output Format

```
## Verification Report — <CR-ID>
### Regression: PASS/FAIL (N/N green, affected targets)
```

Your report ends the VERIFY cycle's work. No fix round runs inside the VERIFY cycle.

## Gate Criteria

All targeted tests pass (any failure = STOP, don't approve); report the total test count.

## Final Actions (IN THIS ORDER — NON-NEGOTIABLE)

1. Ensure targeted results were ingested via the stack crucible client under your agent id.
2. **Unregister — last action.**

**Lifecycle bracket: register → verify → ingest → unregister.**
"""


class PreReviewModeDetectorTest(unittest.TestCase):
    """Every detector proven both ways: the spec-worded synthetic body satisfies it, today's
    wording fails it, and a one-phrase mutation makes it bite."""

    def swap(self, text: str, old: str, new: str) -> str:
        self.assertEqual(text.count(old), 1, f"fixture phrase not unique: {old!r}")
        return text.replace(old, new)

    def assert_flags(self, problems: list[str], name: str):
        self.assertTrue(any(name in p for p in problems),
                        f"expected a finding naming {name!r}; got {problems!r}")

    # -- the spec-worded body passes, today's fails ------------------------------

    def test_the_spec_worded_body_satisfies_every_detector(self):
        self.assertEqual(pre_review_placement_findings(GOOD_BODY), [])
        self.assertEqual(pre_review_rule_findings(GOOD_BODY), [])
        self.assertEqual(report_command_findings(GOOD_BODY, REGISTER), [])
        self.assertEqual(branch_scope_findings(GOOD_BODY), [])
        self.assertEqual(gotchas_scope_findings(GOOD_BODY, GOTCHAS), [])

    def test_todays_wording_fails_every_detector(self):
        self.assertEqual(pre_review_placement_findings(TODAY_BODY),
                         ["expected exactly one 'Spec pre-review mode' section, found 0"])
        self.assertEqual(pre_review_rule_findings(TODAY_BODY),
                         ["expected exactly one 'Spec pre-review mode' section, found 0"])
        self.assertEqual(report_command_findings(TODAY_BODY, REGISTER),
                         ["expected exactly one `--role report` register command, found 0"])
        scope = branch_scope_findings(TODAY_BODY)
        self.assertEqual(len(scope), len(BRANCH_SITES), scope)
        for site in BRANCH_SITES:
            with self.subTest(site=site):
                self.assertIn(f"{site}: ", "\n".join(scope))
                self.assertNotIn(f"{site}: not stated at all", scope)
        self.assertEqual(len(gotchas_scope_findings(TODAY_BODY, GOTCHAS)), 2)

    # -- placement ----------------------------------------------------------------

    def test_placement_bites_on_a_missing_a_doubled_a_misplaced_or_a_nested_section(self):
        doubled = GOOD_BODY + "\n" + PRE_REVIEW_GOOD
        self.assertEqual(pre_review_placement_findings(doubled),
                         ["expected exactly one 'Spec pre-review mode' section, found 2"])
        before = PRE_REVIEW_GOOD + "\n" + FIRST_ACTIONS_GOOD + "\n" + REST_GOOD
        self.assert_flags(pre_review_placement_findings(before), "directly after First Actions")
        at_end = FIRST_ACTIONS_GOOD + "\n" + REST_GOOD + "\n" + PRE_REVIEW_GOOD
        self.assert_flags(pre_review_placement_findings(at_end), "directly after First Actions")
        nested = self.swap(GOOD_BODY, "## Spec pre-review mode", "### Spec pre-review mode")
        self.assert_flags(pre_review_placement_findings(nested), "directly after First Actions")
        suffixed = self.swap(GOOD_BODY, "## Spec pre-review mode",
                             "## Spec pre-review mode (NON-NEGOTIABLE)")
        self.assertEqual(pre_review_placement_findings(suffixed), [])

    # -- the section's rules --------------------------------------------------------

    def test_each_pre_review_rule_bites_when_its_phrase_is_changed(self):
        mutations = {
            "trigger: branch verification stays the default": (
                "Branch verification stays the default.", "Branch verification is one mode."),
            "trigger: only when the brief declares it explicitly": (
                "only when the brief\n  declares it explicitly", "when the brief\n  suggests it"),
            "trigger: never inferred from a missing cycle or from the agent id": (
                "it is never inferred from", "it may be inferred from"),
            "registration: --role report with no --cycle, under the id the brief gives": (
                "with no `--cycle`, under", "with a `--cycle`, under"),
            "Crucible down or absent: proceeds unregistered and says so in its report": (
                "proceed unregistered", "stop"),
            "reads the whole spec, its design reference and the current code": (
                "and the current code.", "and the brief."),
            "applies the gap-analysis skill's Dimensions 1–10 read-only": (
                "Dimensions 1–10", "Dimensions 1–7"),
            "the skill's Step 0 and Rule 1 do not apply": (
                "Rule 1 do not\n  apply to you", "Rule 1 apply\n  to you too"),
            "runs no test suite, ingests nothing, edits nothing, commits nothing": (
                "and commit nothing", "and commit your notes"),
            "a /tmp sandbox only where reading cannot settle a case": (
                "where reading cannot settle a case", "whenever you like"),
            "findings F1…Fn, each naming the spec section or AC, and whether it adds or corrects scope": (
                ", and whether it adds\n  scope or corrects it", ""),
            "unregisters when registered": ("Unregister when registered.", "Unregister."),
        }
        self.assertEqual(set(mutations), set(PRE_REVIEW_RULES))
        for name, (old, new) in mutations.items():
            with self.subTest(rule=name):
                problems = pre_review_rule_findings(self.swap(GOOD_BODY, old, new))
                self.assertEqual(len(problems), 1, problems)
                self.assertTrue(problems[0].startswith(name), problems)

    def test_the_skill_citation_bites_when_the_installed_path_is_missing(self):
        problems = pre_review_rule_findings(
            self.swap(GOOD_BODY, "`~/.agents/skills/gap-analysis/SKILL.md`", "the skill"))
        self.assertEqual(problems,
                         [f"the section does not cite the skill as {SKILL_CITATION}"])

    def test_a_rule_split_across_two_bullets_is_not_satisfied(self):
        split = self.swap(GOOD_BODY, "You run no test suite, ingest nothing, edit nothing and "
                          "commit nothing.",
                          "You run no test suite and ingest nothing.\n- You edit nothing and "
                          "commit nothing.")
        problems = pre_review_rule_findings(split)
        self.assertEqual(len(problems), 1, problems)
        self.assertTrue(problems[0].startswith("runs no test suite"), problems)

    # -- the registration command ---------------------------------------------------

    def test_the_report_command_bites_on_a_cycle_a_double_a_misplacement_or_no_branch_command(self):
        cycled = self.swap(GOOD_BODY, f"{REGISTER} --role report",
                           f"{REGISTER} --role report --cycle <cycleId>")
        self.assertEqual(report_command_findings(cycled, REGISTER),
                         ["the `--role report` command binds a --cycle"])
        doubled = GOOD_BODY + f"\n```bash\n{REGISTER} --role report\n```\n"
        self.assertEqual(report_command_findings(doubled, REGISTER),
                         ["expected exactly one `--role report` register command, found 2"])
        outside = self.swap(GOOD_BODY, f"  {REGISTER} --role report\n", "  stack-client noop\n")
        outside = outside + f"\n```bash\n{REGISTER} --role report\n```\n"
        self.assertEqual(report_command_findings(outside, REGISTER),
                         ["the `--role report` command is not in the 'Spec pre-review mode' "
                          "section"])
        no_branch = self.swap(GOOD_BODY, f"{REGISTER} --role VERIFY --cycle <cycleId>",
                              "stack-client noop")
        self.assertEqual(report_command_findings(no_branch, REGISTER),
                         ["no branch-mode register command (--role VERIFY --cycle)"])
        early = PRE_REVIEW_GOOD + "\n" + FIRST_ACTIONS_GOOD + "\n" + REST_GOOD
        self.assertEqual(report_command_findings(early, REGISTER),
                         ["the `--role report` command comes before the branch-mode command"])

    # -- branch-mode scoping ---------------------------------------------------------

    def test_each_branch_mode_site_bites_when_its_scoping_is_dropped(self):
        mutations = {
            "cycle requirement": ("In branch verification,\n   `--cycle` is REQUIRED",
                                  "`--cycle` is REQUIRED"),
            "targeted regression": ("(branch verification only):", ":"),
            "ingest": ("## What You Do (branch verification)", "## What You Do"),
            "Gate Criteria": ("## Gate Criteria (branch verification)", "## Gate Criteria"),
            "Regression line": ("In branch verification, the report carries the Regression line "
                                "below.", "The report carries these lines."),
            "report ends the VERIFY cycle's work": (
                "In branch verification, your report ends", "Your report ends"),
        }
        self.assertEqual(set(mutations), set(BRANCH_SITES))
        for site, (old, new) in mutations.items():
            with self.subTest(site=site):
                problems = branch_scope_findings(self.swap(GOOD_BODY, old, new))
                self.assertIn(f"{site}: 1 statement(s) not scoped to branch verification",
                              problems)

    def test_the_lifecycle_bracket_is_an_ingest_statement_to_scope(self):
        problems = branch_scope_findings(self.swap(
            GOOD_BODY, "**Lifecycle bracket (branch verification):", "**Lifecycle bracket:"))
        self.assertEqual(problems, ["ingest: 1 statement(s) not scoped to branch verification"])

    def test_a_removed_site_is_reported_as_not_stated(self):
        problems = branch_scope_findings(self.swap(
            GOOD_BODY, "## Gate Criteria (branch verification)\n\nAll targeted tests pass; report "
            "the total test count.\n\n", ""))
        self.assertEqual(problems, ["Gate Criteria: not stated at all"])

    def test_the_pre_review_sections_own_no_cycle_and_no_ingest_are_not_mandates(self):
        # The pre-review section's "--role report with no --cycle" and "ingest nothing" are
        # outside the check: the spec-worded body passes with them in place.
        self.assertIn("ingest nothing", GOOD_BODY)
        self.assertEqual(branch_scope_findings(GOOD_BODY), [])

    # -- the stack's VERIFY gotchas --------------------------------------------------

    def test_the_gotchas_detector_bites_on_each_half_and_accepts_either_home(self):
        unscoped = self.swap(GOOD_BODY, "These are branch-verification specifics: their mandated "
                             "runs do not apply in the spec pre-review\nmode.\n\n", "")
        self.assertEqual(len(gotchas_scope_findings(unscoped, GOTCHAS)), 2)
        heading_only = self.swap(unscoped, "## VERIFY specifics — Stack",
                                 "## VERIFY specifics — Stack (branch verification)")
        self.assertEqual(gotchas_scope_findings(heading_only, GOTCHAS),
                         ["the gotchas' mandated runs are not said not to apply in the pre-review "
                          "mode"])
        exempt_in_mode = self.swap(
            heading_only, "- **Last.** Unregister when registered.\n",
            "- **Last.** Unregister when registered.\n- **Stack specifics.** The stack's VERIFY "
            "specifics are for branch verification; their mandated runs do not apply here.\n")
        self.assertEqual(gotchas_scope_findings(exempt_in_mode, GOTCHAS), [])
        self.assertEqual(gotchas_scope_findings(GOOD_BODY, "- **Missing:** nowhere.\n"),
                         ["the stack's VERIFY gotchas sit under 0 headings, expected one"])

    # -- other roles -----------------------------------------------------------------

    def test_the_leak_detector_bites_on_the_section_and_the_report_flag_only(self):
        self.assertTrue(PRE_REVIEW_LEAK.search("## Spec pre-review mode"))
        self.assertTrue(PRE_REVIEW_LEAK.search(f"{REGISTER} --role report"))
        self.assertTrue(PRE_REVIEW_LEAK.search("register `--role report` with no cycle"))
        self.assertIsNone(PRE_REVIEW_LEAK.search(f"{REGISTER} --role RED --cycle <cycleId>"))
        self.assertIsNone(PRE_REVIEW_LEAK.search("Report every run; the review is yours."))


if __name__ == "__main__":
    unittest.main()
