"""Every test run goes through the Crucible client — CR-MDB-056 §S1 and §S4.

Contract: ``docs/changes/CR-MDB-056-tests-run-only-through-crucible-clients.md`` (design reference
DN-multi-harness-deploy-model §D21 and its 2026-10-13 amendments). The surfaces under test:

- the four role templates ``generator/templates/{red,green,verify,fix}.md.tmpl`` and every
  definition rendered from them into ``generator/agents/`` (4 roles × 5 stacks);
- Model B's own ``.pi/agents/python-*-agent.md``, byte-identical to their ``generator/agents/``
  counterparts (§S4);
- the five stack files ``generator/stacks/*.toml``;
- ``skills-src/model-b/references/sub-agent-procedure.md``,
  ``skills-src/model-b/references/orchestration-common.md``, ``skills-src/crucible/SKILL.md`` and
  ``skills-src/gap-analysis/SKILL.md``'s Step 0.

What is pinned (the patterns are the spec's own words; the rest of each sentence is free):

- **The rule** (``RUN_RULE``): every test run goes through the stack's client; never a runner
  invoked directly; a runner the client cannot drive is a client gap, raised with the orchestrator;
  a brief that says otherwise is refused and escalated; the escape hatch ``ALLOW_RAW_<RUNNER>=1``
  only with the orchestrator's approval; the two known client gaps (the python client drives
  ``unittest`` only; ``bun-crucible.py test`` takes no test-name filter). Carried by each role
  template, each rendered definition and the sub-agent procedure. No template and no rendered
  definition admits a manual run ("If running manually", "best path", "+ auto-ingest").
- **The orchestrator's own runs** (``ORCHESTRATOR_RUN_RULE``): ``orchestration-common`` states the
  rule with the orchestrator's own runs — a baseline, the empty-``HOME`` run, a run under another
  interpreter through ``--python`` — through the client, and the client gap raised with Crucible.
- **The crucible skill**: its § "Lifecycle" states the rule, its verb table keeps every run on the
  client's run verbs, its § "Who runs what" names the orchestrator's own runs, and the file names
  the client gap, the escape hatch, the refused brief and the two gaps.
- **gap-analysis Step 0**: the baseline is measured through the client.
- **The stack files**: an "ALLOWED" list names client verbs only (``allowed_list_findings``);
  python's stdlib-only check is ``test --python <interpreter>`` and the "run xmlrunner by hand"
  sentence is gone; quarkus's compile check is the client's, with no raw ``mvn … test-compile``;
  arduino's native suite runs through ``arduino-crucible.py``, never via ``make``.

§S3's guard — the scan of every guarded file for a runner invocation in a code span — is not pinned
here (CR-MDB-056 C3). A rule is carried when ONE block — a list item with its wrapped lines, or a
paragraph — matches every pattern of the rule (``missing_rules``, case-insensitive, ``**`` and
backticks dropped). Every checker is a pure function and is proved on synthetic text in
``ClientRunRuleCheckersOnSyntheticTextTest`` before it is applied to the tree. Stdlib only.
"""

import re
import tempfile
import unittest
from pathlib import Path

from tests._helpers import REPO_ROOT, md_section, read_text
from tests.test_generator_role_contract import _role_names, _stack_names
from tests.test_orchestration_acceptance_model import missing_rules, rule_blocks

GENERATOR_DIR = REPO_ROOT / "generator"
TEMPLATES_DIR = GENERATOR_DIR / "templates"
STACKS_DIR = GENERATOR_DIR / "stacks"
GENERATED_AGENTS_DIR = GENERATOR_DIR / "agents"
PI_AGENTS_DIR = REPO_ROOT / ".pi" / "agents"
PROCEDURE = REPO_ROOT / "skills-src" / "model-b" / "references" / "sub-agent-procedure.md"
ORCHESTRATION_COMMON = REPO_ROOT / "skills-src" / "model-b" / "references" / "orchestration-common.md"
CRUCIBLE_SKILL = REPO_ROOT / "skills-src" / "crucible" / "SKILL.md"
GAP_ANALYSIS_SKILL = REPO_ROOT / "skills-src" / "gap-analysis" / "SKILL.md"

#: Model B's own project stack: ``.pi/agents/`` holds its four python definitions.
PI_PROJECT_STACK = "python"

#: "through the client", "via the stack's Crucible client", "through `python-crucible.py`".
THROUGH_CLIENT = r"\b(?:through|via)\s(?:\S+\s){0,5}?\S*(?:client\b|-crucible\.py)"
#: The blocking hooks' escape hatch, as the spec names it (or a concrete runner's own).
ESCAPE_HATCH = r"ALLOW_RAW_(?:<RUNNER>|[A-Z]+)=1"

#: The two client gaps known when the rule was written (§S1), named where the rule is stated.
KNOWN_GAPS = {
    "known gap: the python client drives unittest only (a pytest project)": (
        r"\bpython\b", r"\bunittest\b", r"\bonly\b", r"\bpytest\b"),
    "known gap: bun-crucible.py test takes no test-name filter (a one-test bun run)": (
        r"bun-crucible\.py test\b", r"\bfilter"),
}

#: §S1 — the rule as the role templates, the rendered definitions and the sub-agent procedure
#: state it.
RUN_RULE = {
    "every test run goes through the stack's client": (
        r"\bevery\b[^.]{0,40}\bruns?\b", THROUGH_CLIENT),
    "never a runner invoked directly": (r"\bnever\b[^.]{0,60}\brunners?\b", r"\bdirectly\b"),
    "a runner the client cannot drive is a client gap, raised with the orchestrator": (
        r"\bclient gap\b", r"\braise", r"\borchestrator"),
    "a brief that says otherwise is refused and escalated": (
        r"\bbrief\b", r"\brefuse", r"ESCALATION:|\bescalat"),
    "the escape hatch ALLOW_RAW_<RUNNER>=1 only with the orchestrator's approval": (
        ESCAPE_HATCH, r"\bapprov", r"\borchestrator"),
    **KNOWN_GAPS,
}

#: §S1 — the orchestrator's own runs: a baseline, the pre-merge gate's empty-HOME run, a run under
#: another interpreter through the client's --python.
OWN_RUNS_RULE = {
    "the orchestrator's own runs — a baseline, the empty-HOME run, --python — go through the client": (
        r"\bbaseline", r"\bempty\W{1,3}HOME\b", r"--python\b", r"\bclient\b"),
}

#: §S1 — the rule as ``orchestration-common`` states it for the orchestrator.
ORCHESTRATOR_RUN_RULE = {
    "every test run goes through the stack's client": RUN_RULE[
        "every test run goes through the stack's client"],
    "never a runner invoked directly": RUN_RULE["never a runner invoked directly"],
    **OWN_RUNS_RULE,
    "a client gap is raised with Crucible": (r"\bclient gap\b", r"\bCrucible\b"),
    "the escape hatch ALLOW_RAW_<RUNNER>=1 only with approval": (ESCAPE_HATCH, r"\bapprov"),
    **KNOWN_GAPS,
}

#: The crucible skill's § "Lifecycle" carries the rule's head.
LIFECYCLE_RULE = {
    "every test run goes through the stack's client": RUN_RULE[
        "every test run goes through the stack's client"],
    "never a runner invoked directly": RUN_RULE["never a runner invoked directly"],
}

#: The crucible skill as a whole names the rest of the rule.
CRUCIBLE_SKILL_RULE = {
    "a runner the client cannot drive is a client gap, raised": (r"\bclient gap\b", r"\braise"),
    "a brief that says otherwise is refused and escalated": RUN_RULE[
        "a brief that says otherwise is refused and escalated"],
    "the escape hatch ALLOW_RAW_<RUNNER>=1 only with the orchestrator's approval": RUN_RULE[
        "the escape hatch ALLOW_RAW_<RUNNER>=1 only with the orchestrator's approval"],
    **KNOWN_GAPS,
}

#: gap-analysis Step 0 — the baseline is measured through the client.
STEP0_RULE = {
    "the baseline is run through the client": (r"\b(?:run|measur)\w*", THROUGH_CLIENT),
}

#: What a template admitted before this change: a manual run, the client as a mere "best path",
#: and a run step followed by "+ auto-ingest".
MANUAL_RUN_PHRASES = (
    ("If running manually", re.compile(r"\bif running manually\b", re.IGNORECASE)),
    ("best path", re.compile(r"\bbest path\b", re.IGNORECASE)),
    ("+ auto-ingest", re.compile(r"\+\s*auto-ingest\b", re.IGNORECASE)),
)

CODE_SPAN = re.compile(r"`([^`]+)`")
CLIENT_SCRIPT = re.compile(r"[\w-]+-crucible\.py")
#: A code span that invokes a test runner itself (the ALLOWED-list check; the tree-wide scan is
#: §S3's guard). ``mvn-crucible.py`` is a client, not ``mvn``.
RAW_RUNNER_SPAN = re.compile(
    r"^(?:[\w.~-]*/)?(?:"
    r"python[\d.]*\s.*-m\s+(?:unittest|pytest)\b"
    r"|py\.?test\b"
    r"|bunx?\s+(?:test|run\s+test)\b"
    r"|npm\s+(?:test|run\s+test)\b"
    r"|mvnw?(?![\w.-])"
    r"|cargo\s+(?:test|nextest|llvm-cov)\b"
    r"|make\b"
    r")"
)
#: python's stdlib-only check, through the client: ``test --python <interpreter>``.
TEST_WITH_PYTHON_SPAN = re.compile(r"(?:^|\s)test\b[^`]*\s--python\b")
#: The removed stdlib-only instruction: run a test file directly with an interpreter.
DIRECT_TEST_FILE = re.compile(r"\bpython[\d.]*\s+tests/test_\S*\.py")
#: quarkus's removed raw compile check.
RAW_MVN_COMPILE_SPAN = re.compile(r"^(?:[\w.~-]*/)?mvnw?\s[^`]*\btest-compile\b")
#: arduino's removed raw native run: ``make junit``, or "via `make`".
RAW_MAKE_RUN = re.compile(r"`make\s+junit\b[^`]*`|\bvia\s+`make`", re.IGNORECASE)
#: arduino's native suite, run through its client.
ARDUINO_NATIVE_RULE = {
    "the native suite under tests/native runs through arduino-crucible.py": (
        r"tests/native", r"arduino-crucible\.py"),
}


# ------------------------------------------------------------------ checkers ----

def manual_run_findings(text: str) -> list[str]:
    """``line N: <phrase>`` for every line of ``text`` admitting a manual run."""
    return [f"line {n}: {label}"
            for n, line in enumerate(text.splitlines(), 1)
            for label, pattern in MANUAL_RUN_PHRASES if pattern.search(line)]


def allowed_list_findings(text: str, client: str) -> list[str]:
    """Problems with each "ALLOWED" list of a stack file's ``text``: a code span that invokes a
    runner itself, or a list that names no client verb (``client`` or "the client's")."""
    problems = []
    for n, line in enumerate(text.splitlines(), 1):
        if "ALLOWED" not in line:
            continue
        segment = line.split("ALLOWED", 1)[1].split("FORBIDDEN", 1)[0]
        problems += [f"line {n}: ALLOWED names the runner `{span}`"
                     for span in CODE_SPAN.findall(segment) if RAW_RUNNER_SPAN.match(span.strip())]
        if client not in segment and not re.search(r"\bclient's\b", segment):
            problems.append(f"line {n}: ALLOWED names no {client} verb")
    return problems


def python_stdlib_check_findings(text: str) -> list[str]:
    """The stdlib-only check is ``test --python <interpreter>``; no test file is run directly;
    no sentence tells the agent to run xmlrunner by hand."""
    problems = []
    if not any(TEST_WITH_PYTHON_SPAN.search(span) for span in CODE_SPAN.findall(text)):
        problems.append("no `test --python <interpreter>` client run for the stdlib-only check")
    problems += [f"runs a test file directly: {m.group(0)}" for m in DIRECT_TEST_FILE.finditer(text)]
    problems += [f"runs xmlrunner by hand: {block[:100]}" for block in rule_blocks(text)
                 if re.search(r"xmlrunner", block, re.I) and re.search(r"\bby hand\b", block, re.I)]
    return problems


def quarkus_compile_findings(text: str) -> list[str]:
    """The compile check is ``mvn-crucible.py compile``; no raw ``mvn … test-compile`` span."""
    problems = [f"raw compile `{span}`" for span in CODE_SPAN.findall(text)
                if RAW_MVN_COMPILE_SPAN.match(span.strip())]
    if not re.search(r"mvn-crucible\.py compile\b", text):
        problems.append("no `mvn-crucible.py compile` compile check")
    return problems


def arduino_native_findings(text: str) -> list[str]:
    """The native suite runs through ``arduino-crucible.py``; never ``make junit`` / via ``make``."""
    problems = [f"raw native run: {m.group(0)}" for m in RAW_MAKE_RUN.finditer(text)]
    problems += missing_rules(text, ARDUINO_NATIVE_RULE)
    return problems


def byte_mismatches(left: Path, right: Path, names: list[str]) -> list[str]:
    """``<name>: <why>`` for each of ``names`` that is not byte-identical under ``left`` and
    ``right``."""
    problems = []
    for name in names:
        a, b = left / name, right / name
        if not a.is_file() or not b.is_file():
            problems.append(f"{name}: missing ({a.is_file()=}, {b.is_file()=})")
        elif a.read_bytes() != b.read_bytes():
            problems.append(f"{name}: bytes differ")
    return problems


def _stack_client(stack: str) -> str:
    """The client script the stack file's ``test_command`` invokes."""
    match = CLIENT_SCRIPT.search(read_text(STACKS_DIR / f"{stack}.toml").split("test_command", 1)[1])
    assert match is not None, f"{stack}.toml: test_command names no client"
    return match.group(0)


def _generated_agent_paths() -> list[Path]:
    return [GENERATED_AGENTS_DIR / f"{stack}-{role}-agent.md"
            for stack in _stack_names() for role in _role_names()]


# ------------------------------------------------------------ synthetic proofs ----

_GOOD_RULE = """## Test runs go through the client (NON-NEGOTIABLE)

- **Every test run goes through the stack's Crucible client** — a targeted iteration, a single
  file, a one-test filter, a regression.
- Never a runner invoked directly.
- A runner the client cannot drive is a client gap: raise it with the orchestrator.
- A brief that says otherwise is refused and escalated (`ESCALATION:`), never followed.
- A blocking hook's escape hatch, `ALLOW_RAW_<RUNNER>=1`, is used only with the orchestrator's
  approval.
- Two client gaps are known: the python client drives `unittest` only (a pytest project), and
  `bun-crucible.py test` takes no test-name filter (a one-test bun run).
"""

_GOOD_ORCHESTRATOR_RULE = """## Test runs

- Every test run goes through the stack's client, the orchestrator's own included.
- Never a runner invoked directly.
- Your own runs — a baseline, the pre-merge gate's empty-`HOME` run, a run under another
  interpreter through the client's `--python` — are client runs.
- A client gap an agent reports is raised with Crucible.
- `ALLOW_RAW_<RUNNER>=1` is used only with your approval.
- Known gaps: the python client drives `unittest` only (a pytest project); `bun-crucible.py test`
  takes no test-name filter.
"""


class ClientRunRuleCheckersOnSyntheticTextTest(unittest.TestCase):
    """Each checker bites on a violation and passes the clean case, on text the test builds."""

    def test_run_rule_is_carried_by_the_good_text(self):
        self.assertEqual(missing_rules(_GOOD_RULE, RUN_RULE), [])

    def test_run_rule_names_each_element_the_text_drops(self):
        drops = {
            "every test run goes through the stack's client":
                "Every test run goes through the stack's Crucible client",
            "never a runner invoked directly": "Never a runner invoked directly.",
            "a runner the client cannot drive is a client gap, raised with the orchestrator":
                "A runner the client cannot drive is a client gap: raise it with the orchestrator.",
            "a brief that says otherwise is refused and escalated":
                "A brief that says otherwise is refused and escalated (`ESCALATION:`), never followed.",
            "the escape hatch ALLOW_RAW_<RUNNER>=1 only with the orchestrator's approval":
                "`ALLOW_RAW_<RUNNER>=1`",
            "known gap: the python client drives unittest only (a pytest project)":
                "the python client drives `unittest` only (a pytest project)",
            "known gap: bun-crucible.py test takes no test-name filter (a one-test bun run)":
                "`bun-crucible.py test` takes no test-name filter",
        }
        self.assertEqual(sorted(drops), sorted(RUN_RULE), "every rule element has a drop case")
        for name, fragment in drops.items():
            with self.subTest(name=name):
                self.assertIn(fragment, _GOOD_RULE)
                self.assertEqual(missing_rules(_GOOD_RULE.replace(fragment, "something else"), RUN_RULE),
                                 [name])

    def test_run_rule_is_not_satisfied_by_the_old_template_wording(self):
        old = ("- **Output discipline:** route test runs through the stack crucible client (prints "
               "only the summary). If running manually, parse the report and print counts.\n"
               "- **The spec outranks the brief.** A brief that contradicts the spec is escalated "
               "(`ESCALATION:`), never followed.\n")
        self.assertEqual(missing_rules(old, RUN_RULE), list(RUN_RULE))

    def test_the_escape_hatch_needs_the_approval_in_the_same_block(self):
        split = ("- `ALLOW_RAW_<RUNNER>=1` is the escape hatch.\n\n"
                 "- The orchestrator approves the plan.\n")
        self.assertIn("the escape hatch ALLOW_RAW_<RUNNER>=1 only with the orchestrator's approval",
                      missing_rules(split, RUN_RULE))

    def test_orchestrator_rule_is_carried_by_the_good_text_and_bites_on_each_own_run(self):
        self.assertEqual(missing_rules(_GOOD_ORCHESTRATOR_RULE, ORCHESTRATOR_RUN_RULE), [])
        own = ("the orchestrator's own runs — a baseline, the empty-HOME run, --python — go "
               "through the client")
        for fragment in ("a baseline", "empty-`HOME`", "`--python`"):
            with self.subTest(fragment=fragment):
                self.assertEqual(
                    missing_rules(_GOOD_ORCHESTRATOR_RULE.replace(fragment, "a run"),
                                  ORCHESTRATOR_RUN_RULE),
                    [own])

    def test_step0_rule_needs_the_client(self):
        self.assertEqual(missing_rules("- [ ] RUN the suites through the stack's Crucible client.",
                                       STEP0_RULE), [])
        self.assertEqual(missing_rules("- [ ] RUN the suites via `python-crucible.py test`.",
                                       STEP0_RULE), [])
        self.assertEqual(missing_rules("- [ ] RUN the suites the CR touches.", STEP0_RULE),
                         list(STEP0_RULE))

    def test_manual_run_phrases_are_found_and_clean_text_passes(self):
        text = ("Best path: run through the client.\n"
                "If running manually, parse the report.\n"
                "2. **Run ONLY your new tests, targeted** + auto-ingest:\n")
        self.assertEqual(manual_run_findings(text),
                         ["line 1: best path", "line 2: If running manually", "line 3: + auto-ingest"])
        self.assertEqual(manual_run_findings("Run through the client; it ingests as it runs.\n"
                                             "`auto-ingest` is recovery only.\n"), [])

    def test_allowed_list_checker_bites_on_a_runner_and_passes_client_verbs(self):
        old = ("- ALLOWED — `python -m unittest`/`pytest`/`python-crucible.py test` (run-only), "
               "`ruff` in check mode. FORBIDDEN — `black`.")
        self.assertEqual(allowed_list_findings(old, "python-crucible.py"),
                         ["line 1: ALLOWED names the runner `python -m unittest`",
                          "line 1: ALLOWED names the runner `pytest`"])
        quarkus = "- ALLOWED — `mvn test`/`verify`, `mvn-crucible.py module` runs. FORBIDDEN — x."
        self.assertEqual(allowed_list_findings(quarkus, "mvn-crucible.py"),
                         ["line 1: ALLOWED names the runner `mvn test`"])
        good = ("- ALLOWED — `python-crucible.py test` / `check` (run-only), `ruff` in check mode. "
                "FORBIDDEN — `pytest`, `black`.")
        self.assertEqual(allowed_list_findings(good, "python-crucible.py"), [])
        rust = "- ALLOWED — the client's `test` / `check` verbs. FORBIDDEN — `cargo fix`."
        self.assertEqual(allowed_list_findings(rust, "rust-crucible.py"), [])
        self.assertEqual(allowed_list_findings("- ALLOWED — `tsc --noEmit`. FORBIDDEN — x.",
                                               "bun-crucible.py"),
                         ["line 1: ALLOWED names no bun-crucible.py verb"])

    def test_python_stdlib_check_checker(self):
        old = ("- **Stale reports:** if you ever run xmlrunner by hand, clear the reports dir.\n"
               "- **Stdlib-only test path:** run `python3 tests/test_*.py` directly.\n")
        self.assertEqual(len(python_stdlib_check_findings(old)), 3)
        good = ("- **Stdlib-only test path:** run `python-crucible.py test --python /usr/bin/python3 "
                "--agent YOUR_AGENT_ID` — the client runs the suite under that interpreter.\n")
        self.assertEqual(python_stdlib_check_findings(good), [])
        self.assertEqual(python_stdlib_check_findings("- run `test --python <interpreter>`.\n"), [])

    def test_quarkus_compile_checker(self):
        old = "after each file `mvn-crucible.py compile --agent X` (or `mvn -q clean test-compile`)"
        self.assertEqual(quarkus_compile_findings(old), ["raw compile `mvn -q clean test-compile`"])
        self.assertEqual(quarkus_compile_findings("after each file `mvn-crucible.py compile --agent X`"),
                         [])
        self.assertEqual(quarkus_compile_findings("compile with care"),
                         ["no `mvn-crucible.py compile` compile check"])

    def test_arduino_native_checker(self):
        old = ("- **Native test layout:** `sheetal-firmware/tests/native/` — Run via `make` from "
               "`tests/native/` (`make junit` emits `reports/TEST-*.xml`).\n")
        self.assertEqual(arduino_native_findings(old),
                         ["raw native run: via `make`", "raw native run: `make junit`",
                          "the native suite under tests/native runs through arduino-crucible.py"])
        good = ("- **Native test layout:** `sheetal-firmware/tests/native/` — the suite runs through "
                "`arduino-crucible.py unit --agent YOUR_AGENT_ID`; it is not in the `make` SRC.\n")
        self.assertEqual(arduino_native_findings(good), [])

    def test_byte_mismatches_bites_on_one_byte_and_a_missing_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            left, right = Path(tmp, "left"), Path(tmp, "right")
            left.mkdir()
            right.mkdir()
            (left / "a.md").write_bytes(b"same\n")
            (right / "a.md").write_bytes(b"same\n")
            (left / "b.md").write_bytes(b"one\n")
            (right / "b.md").write_bytes(b"one \n")
            (left / "c.md").write_bytes(b"only left\n")
            self.assertEqual(byte_mismatches(left, right, ["a.md"]), [])
            self.assertEqual(byte_mismatches(left, right, ["b.md"]), ["b.md: bytes differ"])
            self.assertEqual(len(byte_mismatches(left, right, ["c.md"])), 1)


# ------------------------------------------------------------------ the tree ----

class RoleTemplatesStateTheRunRuleTest(unittest.TestCase):
    """§S1 — each role template states the rule and admits no manual run."""

    def test_every_role_template_states_the_run_rule(self):
        roles = _role_names()
        self.assertEqual(roles, ["fix", "green", "red", "verify"])
        problems = [f"{role}.md.tmpl: {name}" for role in roles
                    for name in missing_rules(read_text(TEMPLATES_DIR / f"{role}.md.tmpl"), RUN_RULE)]
        self.assertEqual(problems, [], "§S1: every role template states the client-run rule")

    def test_no_role_template_admits_a_manual_run(self):
        problems = [f"{role}.md.tmpl {finding}" for role in _role_names()
                    for finding in manual_run_findings(read_text(TEMPLATES_DIR / f"{role}.md.tmpl"))]
        self.assertEqual(problems, [],
                         "§S1: 'If running manually', 'best path' and '+ auto-ingest' are gone")


class RenderedDefinitionsCarryTheRunRuleTest(unittest.TestCase):
    """§S4 — every rendered definition carries the rule; Model B's own .pi/agents/python-* are
    byte-identical to their generator/agents/ counterparts."""

    def test_every_rendered_definition_states_the_run_rule(self):
        paths = _generated_agent_paths()
        self.assertEqual(len(paths), 20, "4 roles × 5 stacks")
        problems = [f"{path.name}: {name}" for path in paths
                    for name in missing_rules(read_text(path), RUN_RULE)]
        self.assertEqual(problems, [], "§S4: each rendered definition carries the client-run rule")

    def test_no_rendered_definition_admits_a_manual_run(self):
        problems = [f"{path.name} {finding}" for path in _generated_agent_paths()
                    for finding in manual_run_findings(read_text(path))]
        self.assertEqual(problems, [], "§S4: no rendered definition admits a manual run")

    def test_pi_agents_are_byte_identical_to_their_generator_counterparts(self):
        names = [f"{PI_PROJECT_STACK}-{role}-agent.md" for role in _role_names()]
        self.assertEqual(sorted(p.name for p in PI_AGENTS_DIR.glob("*.md")), sorted(names),
                         "§S4: .pi/agents holds exactly the four python definitions")
        self.assertEqual(byte_mismatches(PI_AGENTS_DIR, GENERATED_AGENTS_DIR, names), [],
                         "§S4: each .pi/agents/python-* is byte-identical to generator/agents/")


class StackFilesNameOnlyClientRunsTest(unittest.TestCase):
    """§S1 — the stack files: client verbs where they list allowed runs, and no direct runner
    instruction for python's stdlib-only check, quarkus's compile or arduino's native suite."""

    def test_every_allowed_list_names_client_verbs_only(self):
        stacks = _stack_names()
        self.assertEqual(stacks, ["arduino", "bun", "python", "quarkus", "rust"])
        lists = [s for s in stacks if "ALLOWED" in read_text(STACKS_DIR / f"{s}.toml")]
        self.assertTrue(lists, "precondition: at least one stack file lists its allowed runs")
        problems = [f"{stack}.toml {finding}" for stack in stacks
                    for finding in allowed_list_findings(read_text(STACKS_DIR / f"{stack}.toml"),
                                                         _stack_client(stack))]
        self.assertEqual(problems, [], "§S1: an ALLOWED list names client verbs only")

    def test_python_stdlib_only_check_runs_through_the_client_with_python(self):
        self.assertEqual(python_stdlib_check_findings(read_text(STACKS_DIR / "python.toml")), [],
                         "§S1: python's stdlib-only check is `test --python <interpreter>`; the "
                         "'run xmlrunner by hand' sentence is gone")

    def test_quarkus_compile_check_is_the_clients_compile(self):
        self.assertEqual(quarkus_compile_findings(read_text(STACKS_DIR / "quarkus.toml")), [],
                         "§S1: quarkus's compile check is `mvn-crucible.py compile`")

    def test_arduino_native_suite_runs_through_the_arduino_client(self):
        self.assertEqual(arduino_native_findings(read_text(STACKS_DIR / "arduino.toml")), [],
                         "§S1: arduino's native suite runs through arduino-crucible.py")


class SkillsStateTheRunRuleTest(unittest.TestCase):
    """§S1 — the sub-agent procedure, orchestration-common, the crucible skill and gap-analysis's
    Step 0, the orchestrator's own runs included."""

    def test_sub_agent_procedure_states_the_run_rule(self):
        self.assertEqual(missing_rules(read_text(PROCEDURE), RUN_RULE), [],
                         "§S1: the sub-agent procedure states the client-run rule")

    def test_orchestration_common_states_the_rule_with_the_orchestrators_own_runs(self):
        self.assertEqual(missing_rules(read_text(ORCHESTRATION_COMMON), ORCHESTRATOR_RUN_RULE), [],
                         "§S1: orchestration-common states the rule, the orchestrator's own runs "
                         "included")

    def test_crucible_skill_lifecycle_states_the_rule(self):
        lifecycle = md_section(read_text(CRUCIBLE_SKILL), "## Lifecycle")
        self.assertTrue(lifecycle, "precondition: the crucible skill has a § Lifecycle")
        self.assertEqual(missing_rules(lifecycle, LIFECYCLE_RULE), [],
                         "§S1: the crucible skill's lifecycle states the rule")

    def test_crucible_skill_verb_table_keeps_every_run_on_the_client(self):
        table = md_section(read_text(CRUCIBLE_SKILL), "## Per-stack client surfaces")
        self.assertTrue(table, "precondition: the crucible skill has its verb table")
        self.assertEqual(missing_rules(table, LIFECYCLE_RULE), [],
                         "§S1: the crucible skill's verb table states the rule")

    def test_crucible_skill_who_runs_what_names_the_orchestrators_own_runs(self):
        who = md_section(read_text(CRUCIBLE_SKILL), "## Who runs what")
        self.assertTrue(who, "precondition: the crucible skill has a § Who runs what")
        self.assertEqual(missing_rules(who, OWN_RUNS_RULE), [],
                         "§S1: 'Who runs what' puts the orchestrator's own runs on the client")

    def test_crucible_skill_names_the_gap_the_escape_hatch_the_brief_and_the_known_gaps(self):
        self.assertEqual(missing_rules(read_text(CRUCIBLE_SKILL), CRUCIBLE_SKILL_RULE), [],
                         "§S1: the crucible skill states the rest of the rule")

    def test_gap_analysis_step0_measures_the_baseline_through_the_client(self):
        step0 = md_section(read_text(GAP_ANALYSIS_SKILL), "## Step 0")
        self.assertTrue(step0, "precondition: gap-analysis has a Step 0")
        self.assertEqual(missing_rules(step0, STEP0_RULE), [],
                         "§S1: gap-analysis Step 0 measures the baseline through the client")


if __name__ == "__main__":
    unittest.main()
