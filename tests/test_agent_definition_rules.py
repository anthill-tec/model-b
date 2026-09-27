"""The agent definitions carry the how — CR-MDB-044 §S3, and the FIX/VERIFY half of §S1's #1407 rule.

Contract: ``docs/changes/CR-MDB-044-agent-definitions-and-briefs.md`` (design reference PRD D6,
amended 2026-09-27). The surfaces under test:

- ``generator/templates/{red,green,verify,fix}.md.tmpl``, asserted through the RENDERED agents —
  every stack x role, rendered in memory by ``modelb_axi.agents.neutral_definition`` from the
  committed templates and stack files (the ``generator/build.py --check`` gate keeps the committed
  ``generator/agents/`` in step, so it is not re-checked here);
- ``skills-src/model-b/references/sub-agent-procedure.md``;
- ``skills-src/git-workflow/SKILL.md``;
- every text file under ``skills-src/`` and ``generator/templates/`` (the ``git add -A`` gate).

What is pinned (GREEN writes to the surfaces; the patterns are the spec's own words, the rest of each
sentence is free):

- **Reading the CR.** Every rendered agent has exactly one section headed ``Reading the CR``
  (a parenthetical suffix such as ``(NON-NEGOTIABLE)`` is allowed). Its body names the spec's parts
  (``§S`` scope sections, acceptance criteria, non-goals, design reference — ``SPEC_PARTS``), states
  which of them bind the agent's role (``ROLE_BINDINGS``) and states that the spec outranks the brief,
  that a brief narrows the work to a cycle's scope and may add boundaries, and that a brief
  contradicting the spec is escalated, never followed (``OUTRANK_RULES``).
- **Prompt Precedence.** No template and no rendered agent says ``ABSOLUTE precedence``. The rule
  that replaces it — the brief's scope and boundaries bind; where it contradicts the spec, escalate
  (``PRECEDENCE_RULES``) — is stated in § "Prompt Precedence" when the agent keeps that heading, else
  in § "Reading the CR".
- **Cycles.** The FIX agent binds to a ``fix``-kind cycle opened after VERIFY closed; the VERIFY
  agent's report ends the VERIFY cycle's work and no fix round runs inside it (``CYCLE_RULES``).
- **Committing.** No template, no rendered agent and no skill instructs ``git add -A`` (nor
  ``--all`` / ``git add .``) unless the clause negates it. RED, GREEN and FIX stage by path and
  report the commit range ``<base>..<head>`` (``COMMIT_RULES``). ``git-workflow`` loses "Always
  ``git add -A``" and its § "Commit Timing" says "stage what you changed, by path".
- **Field rules, written once** (``FIELD_RULES``): each is stated in the file §S3 names and in no
  other of the five agent surfaces (``sub-agent-procedure.md`` and the four raw templates). The
  checker rules sit in ``sub-agent-procedure.md`` § "Code quality", beside the content-anchor rule,
  which stays.
- **Stack surface kept.** Every rendered agent carries its stack's test, register and unregister
  commands and its Crucible client reference.

A rule is carried when ONE block — a list item with its wrapped lines, or a paragraph — matches
every pattern of the rule (``rule_blocks`` / ``missing_rules``, case-insensitive, ``**`` and
backticks dropped). Every checker is a pure function returning a list of problem strings (``[]`` =
clean) and is proved on synthetic text in ``AgentDefinitionCheckersOnSyntheticTextTest``. Stdlib
only.
"""

import re
import unittest

from modelb_axi.agents import load_stack_params, neutral_definition
from tests._helpers import REPO_ROOT, read_text
from tests.test_generator_role_contract import _role_names, _stack_names
from tests.test_orchestration_acceptance_model import missing_rules, rule_blocks
from tests.test_orchestrator_rule_triage import markdown_headings, section_body

GENERATOR_DIR = REPO_ROOT / "generator"
TEMPLATES_DIR = GENERATOR_DIR / "templates"
STACKS_DIR = GENERATOR_DIR / "stacks"
SKILLS_DIR = REPO_ROOT / "skills-src"
PROCEDURE_REL = "skills-src/model-b/references/sub-agent-procedure.md"
GIT_WORKFLOW_REL = "skills-src/git-workflow/SKILL.md"

READING_HEADING = "Reading the CR"
PRECEDENCE_HEADING = "Prompt Precedence"
CODE_QUALITY_HEADING = "Code quality"
COMMIT_TIMING_HEADING = "Commit Timing"

#: §S3 — the spec's parts every "Reading the CR" section names (section-level, any block).
SPEC_PARTS = {
    "§S scope sections": r"§\s?S",
    "acceptance criteria": r"acceptance criteri",
    "non-goals": r"non-goals?",
    "design reference": r"design reference",
}

#: §S3 — which parts bind each role. The block names the role or says what binds.
ROLE_BINDINGS = {
    "red": {"RED binds to the ACs in its scope sections, asserted exactly": (
        r"\bbind\w*|\bRED\b", r"\bACs?\b|acceptance criteri", r"scope sections?|§\s?S", r"\bexact")},
    "green": {"GREEN binds to those ACs through the RED tests": (
        r"\bbind\w*|\bGREEN\b", r"\bACs?\b|acceptance criteri", r"RED tests")},
    "verify": {"VERIFY binds to every AC, the non-goals and the design reference": (
        r"\bbind\w*|\bVERIFY\b", r"every AC|all (?:the )?ACs|every acceptance criteri",
        r"non-goals?", r"design reference")},
    "fix": {"FIX binds to the findings it was given, read against the ACs they cite": (
        r"\bbind\w*|\bFIX\b", r"\bfindings\b", r"\bACs?\b|acceptance criteri", r"\bcite")},
}

#: §S3 — the spec outranks the brief.
OUTRANK_RULES = {
    "the spec outranks the brief": (r"\bspec\b", r"outrank", r"\bbrief\b"),
    "a brief narrows the work to a cycle's scope and may add boundaries": (
        r"\bbrief\b", r"narrow", r"\bscope\b", r"boundar"),
    "a brief that contradicts the spec is escalated, never followed": (
        r"\bbrief\b", r"contradict", r"escalat", r"never follow"),
}

#: §S3 — § "Prompt Precedence" is replaced to match.
PRECEDENCE_RULES = {
    "the brief's scope and boundaries bind": (r"\bbrief\b", r"\bscope\b", r"boundar", r"\bbind"),
    "where the brief contradicts the spec, escalate": (r"contradict", r"\bspec\b", r"escalat"),
}

#: §S3 Cycles / §S1 (#1407) — the FIX and VERIFY templates' half of the VERIFY -> FIX switch.
CYCLE_RULES = {
    "fix": {"FIX binds to a fix-kind cycle opened after VERIFY closed": (
        r"\bfix\W{0,3}kind\b|\bkind\W{1,3}fix\b", r"\bcycle", r"\bafter\b", r"\bVERIFY\b",
        r"\bclos")},
    "verify": {
        "the VERIFY report ends the VERIFY cycle's work": (
            r"\breport\b", r"\bends?\b", r"VERIFY cycle"),
        "no fix round runs inside the VERIFY cycle": (
            r"fix round", r"\b(?:no|never|not)\b", r"\b(?:inside|within|in)\b"),
    },
}

#: §S3 Committing — RED, GREEN and FIX.
COMMIT_ROLES = ("red", "green", "fix")
COMMIT_RULES = {
    "stages the files it changed by path": (r"\bstag", r"by path"),
    "reports the commit range <base>..<head>": (
        r"\breport", r"commit range", r"<base>\.\.<head>"),
}

#: §S3 Committing — git-workflow's § "Commit Timing".
GIT_WORKFLOW_RULES = {
    "stage what you changed, by path": (r"stage what you changed", r"by path"),
}

#: The five agent surfaces a field rule may live on.
SURFACES = ("procedure", "red", "green", "verify", "fix")

#: §S3 Field rules — name -> (home surfaces, home section or None, patterns). Written once: each
#: rule is carried on its home surfaces and on no other surface.
FIELD_RULES = {
    "long runs: a run longer than a minute or two gets a tool timeout longer than the run": (
        ("procedure",), None, (r"\bminute", r"tool timeout", r"longer than the run")),
    "long runs: a timed-out run is never re-invoked blind; the board is checked for the own open run": (
        ("procedure",), None,
        (r"\btime(?:s|d)? out", r"never re-?(?:invok|run)", r"\bblind", r"\bboard\b",
         r"own open run")),
    "unrelated failure: trace every consumer (scripts, CLIs, other clients) first": (
        ("verify",), None,
        (r"\bunrelated\b", r"\btrac", r"every consumer", r"\bscripts\b", r"\bCLIs?\b",
         r"other clients")),
    "unrelated failure: the report says how the attribution was established": (
        ("verify",), None, (r"\breport", r"attribution", r"establish")),
    "dead code needs no reference anywhere": (
        ("green", "fix"), None, (r"dead code", r"no reference anywhere")),
    "dead code: own file, dynamic lookups (getattr, string names), mock and patch targets": (
        ("green", "fix"), None,
        (r"own file", r"dynamic lookups?", r"getattr", r"string names?", r"\bmock",
         r"patch targets?")),
    "checkers are proved on synthetic fixtures": (
        ("procedure",), CODE_QUALITY_HEADING, (r"\bcheckers?\b", r"\bprov", r"synthetic fixtures?")),
    "a test never pins live repo violations": (
        ("procedure",), CODE_QUALITY_HEADING, (r"never pins?", r"\blive\b", r"violations?")),
}

#: The content-anchor rule § "Code quality" keeps (the checker rules sit beside it).
CONTENT_ANCHOR_RULE = {
    "a guard's allowlist is keyed to an annotation marker, never a line number": (
        r"annotation marker", r"never a line number"),
}

_ABSOLUTE = re.compile(r"absolute\s+precedence", re.IGNORECASE)
_STAGE_ALL = re.compile(r"git\s+add\s+(?:-A\b|--all\b|\.(?=[\s`\"')&;]|$))")
_NEGATION = re.compile(
    r"\b(?:never|not|no|nor|don't|forbidden|instead of|rather than)\b", re.IGNORECASE)
_CLAUSE_BREAK = re.compile(r"[.;]\s|\s\u2014\s")
_ALWAYS_ADD_ALL = re.compile(r"always\W+git add -A", re.IGNORECASE)


# ------------------------------------------------------------------ checkers ----

def named_sections(text: str, name: str) -> list[str]:
    """The body of every heading named ``name`` — exactly, or followed by a parenthetical or an
    em-dash suffix (``Prompt Precedence (NON-NEGOTIABLE)``) — up to the next heading of the same or
    a higher level."""
    headings = markdown_headings(text)
    lines = text.splitlines()
    bodies = []
    for n, (idx, level, htext) in enumerate(headings):
        if htext == name or htext.startswith((name + " (", name + " \u2014")):
            end = next((j for j, lvl, _ in headings[n + 1:] if lvl <= level), len(lines))
            bodies.append("\n".join(lines[idx + 1:end]))
    return bodies


def reading_the_cr_findings(body: str, role: str) -> list[str]:
    """The "Reading the CR" section: present once, names the spec's parts, the role's binding parts
    and the spec-outranks-the-brief rules."""
    sections = named_sections(body, READING_HEADING)
    problems = []
    if not sections:
        problems.append(f"no '{READING_HEADING}' section")
    elif len(sections) != 1:
        problems.append(f"'{READING_HEADING}' appears {len(sections)} times, not once")
    section = sections[0] if sections else ""
    flat = " ".join(rule_blocks(section))
    problems += [f"{READING_HEADING}: part {name}" for name, pattern in SPEC_PARTS.items()
                 if not re.search(pattern, flat, re.IGNORECASE)]
    problems += [f"{READING_HEADING}: {name}"
                 for name in missing_rules(section, ROLE_BINDINGS[role])]
    problems += [f"{READING_HEADING}: {name}" for name in missing_rules(section, OUTRANK_RULES)]
    return problems


def absolute_precedence_lines(text: str) -> list[str]:
    """``<line>: ABSOLUTE precedence`` for each line saying it (case-insensitive)."""
    return [f"{n}: ABSOLUTE precedence" for n, line in enumerate(text.splitlines(), 1)
            if _ABSOLUTE.search(line)]


def precedence_findings(body: str) -> list[str]:
    """No ``ABSOLUTE precedence``; the replacing rule sits in § "Prompt Precedence" when the agent
    keeps that heading, else in § "Reading the CR"."""
    problems = absolute_precedence_lines(body)
    home = PRECEDENCE_HEADING
    sections = named_sections(body, PRECEDENCE_HEADING)
    if not sections:
        home, sections = READING_HEADING, named_sections(body, READING_HEADING)
    text = "\n\n".join(sections) if sections else None
    return problems + [f"{home}: {name}" for name in missing_rules(text, PRECEDENCE_RULES)]


def cycle_findings(body: str, role: str) -> list[str]:
    """FIX binds to a fix-kind cycle opened after VERIFY closed; VERIFY's report ends its cycle."""
    return [f"cycle: {name}" for name in missing_rules(body, CYCLE_RULES.get(role, {}))]


def stage_all_instructions(text: str) -> list[str]:
    """``<line>: <line text>`` for each line that stages everything (``git add -A`` / ``--all`` /
    ``.``) without a negation earlier in the same clause."""
    found = []
    for n, line in enumerate(text.splitlines(), 1):
        for match in _STAGE_ALL.finditer(line.replace("`", "")):
            clause = _CLAUSE_BREAK.split(line.replace("`", "")[:match.start()])[-1]
            if not _NEGATION.search(clause):
                found.append(f"{n}: {line.strip()}")
                break
    return found


def commit_findings(body: str, role: str) -> list[str]:
    """RED, GREEN and FIX stage by path and report ``<base>..<head>``; no agent stages everything."""
    problems = [f"stages everything: {hit}" for hit in stage_all_instructions(body)]
    if role in COMMIT_ROLES:
        problems += [f"commit: {name}" for name in missing_rules(body, COMMIT_RULES)]
    return problems


def git_workflow_findings(text: str) -> list[str]:
    """``git-workflow`` drops "Always ``git add -A``" and § "Commit Timing" stages by path."""
    problems = [f"{n}: Always git add -A" for n, line in enumerate(text.splitlines(), 1)
                if _ALWAYS_ADD_ALL.search(line.replace("`", "").replace("**", ""))]
    body = section_body(text, COMMIT_TIMING_HEADING)
    if body is None:
        return problems + [f"{COMMIT_TIMING_HEADING}: no heading"]
    return problems + [f"{COMMIT_TIMING_HEADING}: {name}"
                       for name in missing_rules(body, GIT_WORKFLOW_RULES)]


def field_rule_findings(surfaces: dict[str, str]) -> list[str]:
    """Each field rule is carried on its home surfaces (in its home section, where one is named) and
    restated on no other surface."""
    problems = []
    for name, (homes, heading, patterns) in FIELD_RULES.items():
        rule = {name: patterns}
        for surface in SURFACES:
            text = surfaces[surface]
            if surface in homes:
                scoped = section_body(text, heading) if heading else text
                if missing_rules(scoped, rule):
                    where = f"{surface} § {heading}" if heading else surface
                    problems.append(f"{name}: missing from {where}")
            elif not missing_rules(text, rule):
                problems.append(f"{name}: restated in {surface}")
    return problems


def code_quality_anchor_findings(procedure: str) -> list[str]:
    """§ "Code quality" keeps the content-anchor rule."""
    body = section_body(procedure, CODE_QUALITY_HEADING)
    return [f"{CODE_QUALITY_HEADING}: {name}" for name in missing_rules(body, CONTENT_ANCHOR_RULE)]


def stack_surface_findings(body: str, params: dict) -> list[str]:
    """The rendered agent carries its stack's test/register/unregister commands and client ref."""
    return [f"stack: {key}" for key in
            ("test_command", "register_command", "unregister_command", "crucible_reference")
            if params[key] not in body]


# ------------------------------------------------------------------ the tree ----

def _stacks() -> list[str]:
    return _stack_names()


def _roles() -> list[str]:
    return _role_names()


def _rendered_agents():
    """``(stack, role, params, body)`` for every stack x role, rendered from the committed sources."""
    out = []
    for stack in _stacks():
        params = load_stack_params(STACKS_DIR, stack)
        for role in _roles():
            body = neutral_definition(stack, role, params, TEMPLATES_DIR)["body"]
            out.append((stack, role, params, body))
    return out


def _template(role: str) -> str:
    return read_text(TEMPLATES_DIR / f"{role}.md.tmpl")


def _surfaces() -> dict[str, str]:
    surfaces = {role: _template(role) for role in ("red", "green", "verify", "fix")}
    surfaces["procedure"] = read_text(REPO_ROOT / PROCEDURE_REL)
    return surfaces


def _per_agent(check) -> list[str]:
    return [f"{stack}-{role}: {problem}" for stack, role, params, body in _rendered_agents()
            for problem in check(stack, role, params, body)]


class RenderedAgentSetTest(unittest.TestCase):
    def test_every_stack_renders_all_four_roles(self):
        agents = _rendered_agents()
        self.assertEqual(_roles(), ["fix", "green", "red", "verify"])
        self.assertEqual(len(agents), len(_stacks()) * 4)
        self.assertEqual(len(_stacks()), 5)


class ReadingTheCrSectionTest(unittest.TestCase):
    """§S3 "Reading the CR" — every rendered agent, each stack x role."""

    def test_every_rendered_agent_has_one_reading_the_cr_section(self):
        self.assertEqual(_per_agent(lambda s, r, p, b: [
            x for x in reading_the_cr_findings(b, r) if not x.startswith(f"{READING_HEADING}:")]),
            [])

    def test_reading_the_cr_names_the_spec_parts(self):
        self.assertEqual(_per_agent(lambda s, r, p, b: [
            x for x in reading_the_cr_findings(b, r) if ": part " in x]), [])

    def test_reading_the_cr_names_the_parts_that_bind_the_role(self):
        self.assertEqual(_per_agent(lambda s, r, p, b: [
            x for x in reading_the_cr_findings(b, r)
            if any(x.endswith(name) for name in ROLE_BINDINGS[r])]), [])

    def test_reading_the_cr_states_that_the_spec_outranks_the_brief(self):
        self.assertEqual(_per_agent(lambda s, r, p, b: [
            x for x in reading_the_cr_findings(b, r)
            if any(x.endswith(name) for name in OUTRANK_RULES)]), [])


class PromptPrecedenceTest(unittest.TestCase):
    """§S3 — § "Prompt Precedence" is replaced: the brief's scope and boundaries bind; a brief that
    contradicts the spec is escalated."""

    def test_no_template_says_absolute_precedence(self):
        self.assertEqual([f"{role}.md.tmpl {hit}" for role in _roles()
                          for hit in absolute_precedence_lines(_template(role))], [])

    def test_every_rendered_agent_states_the_replacing_precedence_rule(self):
        self.assertEqual(_per_agent(lambda s, r, p, b: precedence_findings(b)), [])


class CycleBindingTest(unittest.TestCase):
    """§S3 Cycles / §S1 #1407 — the FIX and VERIFY templates' half of the VERIFY -> FIX switch."""

    def test_fix_agents_bind_to_a_fix_kind_cycle_opened_after_verify_closed(self):
        self.assertEqual(_per_agent(
            lambda s, r, p, b: cycle_findings(b, r) if r == "fix" else []), [])

    def test_verify_agents_report_ends_the_verify_cycle_with_no_fix_round_inside(self):
        self.assertEqual(_per_agent(
            lambda s, r, p, b: cycle_findings(b, r) if r == "verify" else []), [])


class CommittingByPathTest(unittest.TestCase):
    """§S3 Committing."""

    def test_no_template_instructs_staging_everything(self):
        self.assertEqual([f"{role}.md.tmpl {hit}" for role in _roles()
                          for hit in stage_all_instructions(_template(role))], [])

    def test_no_skill_instructs_staging_everything(self):
        hits = []
        for path in sorted(SKILLS_DIR.rglob("*")):
            if not path.is_file() or "__pycache__" in path.parts:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, ValueError):
                continue
            hits += [f"{path.relative_to(REPO_ROOT).as_posix()} {hit}"
                     for hit in stage_all_instructions(text)]
        self.assertEqual(hits, [])

    def test_red_green_fix_agents_stage_by_path_and_report_the_commit_range(self):
        self.assertEqual(_per_agent(lambda s, r, p, b: commit_findings(b, r)), [])

    def test_git_workflow_stages_what_you_changed_by_path(self):
        self.assertEqual(git_workflow_findings(read_text(REPO_ROOT / GIT_WORKFLOW_REL)), [])


class FieldRulesTest(unittest.TestCase):
    """§S3 Field rules, written once — each in the file §S3 names."""

    def test_each_field_rule_is_carried_in_the_file_s3_names(self):
        self.assertEqual([p for p in field_rule_findings(_surfaces()) if ": missing from " in p], [])

    def test_no_field_rule_is_restated_on_another_agent_surface(self):
        self.assertEqual([p for p in field_rule_findings(_surfaces()) if ": restated in " in p], [])

    def test_code_quality_keeps_the_content_anchor_rule(self):
        self.assertEqual(code_quality_anchor_findings(read_text(REPO_ROOT / PROCEDURE_REL)), [])


class StackSurfaceKeptTest(unittest.TestCase):
    """§S3 — every rendered agent carries its stack's test command and Crucible client."""

    def test_every_rendered_agent_carries_its_stacks_commands_and_client(self):
        self.assertEqual(_per_agent(lambda s, r, p, b: stack_surface_findings(b, p)), [])


# ------------------------------------------------------------------ synthetic ----

_BINDING_LINES = {
    "red": "- What binds you (RED): the ACs in your scope sections, asserted exactly.",
    "green": "- What binds you (GREEN): those ACs, through the RED tests.",
    "verify": "- What binds you (VERIFY): every AC, the non-goals and the design reference.",
    "fix": "- What binds you (FIX): the findings you were given, read against the ACs they cite.",
}

_READING = """## Reading the CR
A CR spec has four parts: its `§S` scope sections, its acceptance criteria, its non-goals and its
design reference.
{binding}
- The spec outranks the brief.
- A brief narrows the work to a cycle's scope and may add boundaries.
- A brief that contradicts the spec is escalated, never followed.
"""

_PRECEDENCE = """## Prompt Precedence (NON-NEGOTIABLE)
The brief's scope and boundaries bind you. Where the brief contradicts the spec, escalate.
"""

_CYCLES = {
    "fix": "You bind to a `fix`-kind cycle, opened after the VERIFY cycle closed.\n",
    "verify": "Your report ends the VERIFY cycle's work; no fix round runs inside it.\n",
}

_COMMIT = """## Final Actions
1. Stage the files you changed by path (`git add <path> …`), then `git commit`.
2. Your report names the commit range you produced (`<base>..<head>`).
"""


def _good_body(role: str) -> str:
    parts = ["# Agent\n", _READING.format(binding=_BINDING_LINES[role]), _PRECEDENCE,
             _CYCLES.get(role, "")]
    if role in COMMIT_ROLES:
        parts.append(_COMMIT)
    return "\n".join(parts)


def _once(text: str, old: str, new: str) -> str:
    assert text.count(old) == 1, old
    return text.replace(old, new)


_GOOD_SURFACES = {
    "procedure": """# AGENTS
## Long runs
- A run longer than a minute or two gets a tool timeout longer than the run.
- A run that times out is never re-invoked blind: the agent first checks the board for its own
  open run.

## Code quality
- Key a guard's allowlist to an annotation marker at the site, never a line number.
- Checkers are proved on synthetic fixtures; a test never pins live repo violations.
""",
    "red": "# RED\n- Write the tests.\n",
    "green": """# GREEN
- Dead code needs no reference anywhere. No reference counts from its own file, dynamic lookups
  (`getattr`, string names) or mock and patch targets.
""",
    "verify": """# VERIFY
- Before calling a failure unrelated, trace every consumer of the changed behaviour (scripts, CLIs,
  other clients).
- The report says how the attribution was established.
""",
    "fix": """# FIX
- Dead code needs no reference anywhere. No reference counts from its own file, dynamic lookups
  (`getattr`, string names) or mock and patch targets.
""",
}

_GOOD_GIT_WORKFLOW = """# Git Workflow
## Commit Timing
- **Stage what you changed, by path** before commit.

## Working Directory
- Verify the branch.
"""


class AgentDefinitionCheckersOnSyntheticTextTest(unittest.TestCase):
    def test_well_formed_fixture_yields_no_finding_for_every_role(self):
        for role in ("red", "green", "verify", "fix"):
            body = _good_body(role)
            with self.subTest(role=role):
                self.assertEqual(reading_the_cr_findings(body, role), [])
                self.assertEqual(precedence_findings(body), [])
                self.assertEqual(cycle_findings(body, role), [])
                self.assertEqual(commit_findings(body, role), [])
        self.assertEqual(field_rule_findings(_GOOD_SURFACES), [])
        self.assertEqual(code_quality_anchor_findings(_GOOD_SURFACES["procedure"]), [])
        self.assertEqual(git_workflow_findings(_GOOD_GIT_WORKFLOW), [])

    def test_missing_or_duplicated_reading_the_cr_section_is_reported(self):
        body = _good_body("red")
        self.assertEqual(reading_the_cr_findings(
            _once(body, "## Reading the CR", "## Reading"), "red"), ["no 'Reading the CR' section"]
            + [f"Reading the CR: part {name}" for name in SPEC_PARTS]
            + [f"Reading the CR: {name}" for name in ROLE_BINDINGS["red"]]
            + [f"Reading the CR: {name}" for name in OUTRANK_RULES])
        twice = body + "\n## Reading the CR (NON-NEGOTIABLE)\n- x\n"
        self.assertEqual(reading_the_cr_findings(twice, "red"),
                         ["'Reading the CR' appears 2 times, not once"])

    def test_a_missing_spec_part_is_reported_by_name(self):
        body = _once(_good_body("green"), "its non-goals and its", "its")
        self.assertEqual(reading_the_cr_findings(body, "green"), ["Reading the CR: part non-goals"])

    def test_another_roles_binding_does_not_satisfy_the_role(self):
        body = _once(_good_body("red"), _BINDING_LINES["red"], _BINDING_LINES["green"])
        self.assertEqual(reading_the_cr_findings(body, "red"), [
            "Reading the CR: RED binds to the ACs in its scope sections, asserted exactly"])
        body = _once(_good_body("verify"), _BINDING_LINES["verify"], _BINDING_LINES["red"])
        self.assertEqual(reading_the_cr_findings(body, "verify"), [
            "Reading the CR: VERIFY binds to every AC, the non-goals and the design reference"])

    def test_a_brief_that_wins_over_the_spec_is_reported(self):
        body = _once(_good_body("fix"), "- A brief that contradicts the spec is escalated, never followed.\n",
                     "- A brief that contradicts the spec is followed.\n")
        body = _once(body, "- The spec outranks the brief.\n", "")
        self.assertEqual(reading_the_cr_findings(body, "fix"), [
            "Reading the CR: the spec outranks the brief",
            "Reading the CR: a brief that contradicts the spec is escalated, never followed",
        ])

    def test_absolute_precedence_and_a_missing_replacing_rule_are_reported(self):
        old = ("## Prompt Precedence (NON-NEGOTIABLE)\n\nExact test names in the dispatch prompt "
               "take ABSOLUTE precedence over your interpretation.\n")
        body = _once(_good_body("red"), _PRECEDENCE, old)
        self.assertEqual(precedence_findings(body), [
            f"{body.splitlines().index(old.splitlines()[2]) + 1}: ABSOLUTE precedence",
            "Prompt Precedence: the brief's scope and boundaries bind",
            "Prompt Precedence: where the brief contradicts the spec, escalate",
        ])

    def test_without_a_precedence_heading_the_rule_is_looked_for_in_reading_the_cr(self):
        body = _once(_good_body("green"), _PRECEDENCE, "")
        self.assertEqual(precedence_findings(body), [
            "Reading the CR: the brief's scope and boundaries bind",
        ])
        bare = _once(body, "- A brief that contradicts the spec is escalated, never followed.\n", "")
        self.assertEqual(precedence_findings(bare), [
            "Reading the CR: the brief's scope and boundaries bind",
            "Reading the CR: where the brief contradicts the spec, escalate",
        ])
        moved = _once(body, "- The spec outranks the brief.\n",
                      "- The spec outranks the brief.\n" + _PRECEDENCE.splitlines()[1] + "\n")
        self.assertEqual(precedence_findings(moved), [])

    def test_missing_cycle_rules_are_reported_for_fix_and_verify_only(self):
        self.assertEqual(cycle_findings(_once(_good_body("fix"), _CYCLES["fix"], ""), "fix"),
                         ["cycle: FIX binds to a fix-kind cycle opened after VERIFY closed"])
        unbound = _once(_good_body("fix"), _CYCLES["fix"], "You bind to the cycle in your brief.\n")
        self.assertEqual(cycle_findings(unbound, "fix"),
                         ["cycle: FIX binds to a fix-kind cycle opened after VERIFY closed"])
        self.assertEqual(
            cycle_findings(_once(_good_body("verify"), _CYCLES["verify"], ""), "verify"),
            ["cycle: the VERIFY report ends the VERIFY cycle's work",
             "cycle: no fix round runs inside the VERIFY cycle"])
        self.assertEqual(cycle_findings(_good_body("red"), "red"), [])

    def test_staging_everything_is_reported_unless_the_clause_negates_it(self):
        text = "\n".join([
            "2. Commit test files: `git add -A && git commit -m \"test: x\"`.",
            "- **Always `git add -A`** before commit — don't leave unstaged changes",
            "git add --all",
            "git add . && git commit",
            "- Stage by path, never `git add -A`.",
            "- Each agent commits only its own files; never `git add -A`, stash or reset.",
            "- Stage by path instead of `git add -A`.",
            "git add tests/test_x.py && git commit",
            "git add .gitignore",
        ])
        self.assertEqual([hit.split(":", 1)[0] for hit in stage_all_instructions(text)],
                         ["1", "2", "3", "4"])

    def test_commit_rules_are_required_of_red_green_fix_but_not_verify(self):
        for role in COMMIT_ROLES:
            body = _once(_good_body(role), _COMMIT,
                         "## Final Actions\n1. Commit: `git add -A && git commit`.\n")
            with self.subTest(role=role):
                self.assertEqual(commit_findings(body, role), [
                    f"stages everything: {body.splitlines().index('1. Commit: `git add -A && git commit`.') + 1}: "
                    "1. Commit: `git add -A && git commit`.",
                    "commit: stages the files it changed by path",
                    "commit: reports the commit range <base>..<head>",
                ])
        self.assertEqual(commit_findings(_good_body("verify"), "verify"), [])

    def test_git_workflow_always_add_all_and_missing_stage_by_path_are_reported(self):
        bad = _once(_GOOD_GIT_WORKFLOW, "- **Stage what you changed, by path** before commit.",
                    "- **Always `git add -A`** before commit — don't leave unstaged changes")
        self.assertEqual(git_workflow_findings(bad), [
            "3: Always git add -A", "Commit Timing: stage what you changed, by path"])
        self.assertEqual(git_workflow_findings("# Git\n"), ["Commit Timing: no heading"])

    def test_a_field_rule_missing_from_its_home_or_restated_elsewhere_is_reported(self):
        surfaces = dict(_GOOD_SURFACES)
        surfaces["fix"] = "# FIX\n- Fix the findings.\n"
        self.assertEqual(field_rule_findings(surfaces), [
            "dead code needs no reference anywhere: missing from fix",
            "dead code: own file, dynamic lookups (getattr, string names), mock and patch targets: "
            "missing from fix",
        ])
        surfaces = dict(_GOOD_SURFACES)
        surfaces["red"] = surfaces["red"] + _GOOD_SURFACES["verify"].split("\n", 1)[1]
        self.assertEqual(field_rule_findings(surfaces), [
            "unrelated failure: trace every consumer (scripts, CLIs, other clients) first: "
            "restated in red",
            "unrelated failure: the report says how the attribution was established: restated in red",
        ])

    def test_checker_rules_outside_code_quality_are_reported_missing_from_that_section(self):
        surfaces = dict(_GOOD_SURFACES)
        line = "- Checkers are proved on synthetic fixtures; a test never pins live repo violations.\n"
        surfaces["procedure"] = _once(surfaces["procedure"], line, "") + "\n## Elsewhere\n" + line
        self.assertEqual(field_rule_findings(surfaces), [
            "checkers are proved on synthetic fixtures: missing from procedure § Code quality",
            "a test never pins live repo violations: missing from procedure § Code quality",
        ])
        self.assertEqual(code_quality_anchor_findings(surfaces["procedure"]), [])
        no_anchor = _once(_GOOD_SURFACES["procedure"],
                          "- Key a guard's allowlist to an annotation marker at the site, never a "
                          "line number.\n", "")
        self.assertEqual(code_quality_anchor_findings(no_anchor), [
            "Code quality: a guard's allowlist is keyed to an annotation marker, never a line number"])

    def test_a_missing_stack_command_or_client_is_reported(self):
        params = {"test_command": "stack-client test", "register_command": "stack-client register",
                  "unregister_command": "stack-client unregister",
                  "crucible_reference": "~/.agents/skills/crucible/references/stack.md"}
        body = "run `stack-client test`; `stack-client register`; `stack-client unregister`"
        self.assertEqual(stack_surface_findings(body, params), ["stack: crucible_reference"])
        body += " — see ~/.agents/skills/crucible/references/stack.md"
        self.assertEqual(stack_surface_findings(body, params), [])


if __name__ == "__main__":
    unittest.main()
