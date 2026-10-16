"""The pre-merge gate measures coverage of the package and every script — the config, the check
tool and the gate's text.

Contract: ``docs/changes/CR-MDB-073-coverage-for-the-package-and-scripts.md`` (design record:
PRD D5's 2026-10-17 ruling). This module holds §S1, §S2, §S3, §S4 and §S5.

Class map:

- ``CoverageConfigTest`` — §S1: ``pyproject.toml`` parses, its ``[tool.coverage.run]`` is exactly
  §S1's ``source`` (in order) and ``patch``, its ``[tool.coverage.report]`` exactly §S1's ``omit``.
- ``CovSourceDetectorTest`` / ``AgentsMdCovSourceTest`` — §S1: every coverage command
  ``AGENTS.md`` shows (``python-crucible.py regression --coverage`` or ``pre-merge-gate``, fenced or
  in a code span) carries a ``--cov-source`` whose value, split on ``,``, is ``source`` in order;
  proved on synthetic text first (:func:`cov_source_findings`).
- ``CoverageCheckTableTest``, ``CoverageCheckMissingFilesTest``, ``CoverageCheckVerdictTest``,
  ``CoverageCheckErrorTest``, ``CoverageCheckWritesNothingTest`` — §S2: ``tools/coverage-check.py``
  driven as a subprocess from a temp project root holding a synthetic ``pyproject.toml``, lcov and
  baseline file. Nothing here runs coverage or the suite.
- ``CoverageCheckStdlibTest`` — §S2: the tool imports only the standard library and its first line
  is ``#!/usr/bin/env python3``.
- ``GateStepsDetectorTest`` / ``AgentsMdGateStepsTest`` — §S3: ``AGENTS.md``'s Testing & QA states
  the gate's steps (:data:`GATE_CHECKS`); proved on synthetic text first, each element alone.
- ``AgentsMdCoverageBaselineTest`` — §S3, the first figure (its format half): exactly one
  ``Coverage baseline:`` line, in Testing & QA, carrying ``<hit>/<found>``, and the tool parses it.
- ``CloseOutBulletDetectorTest`` / ``AgentsMdCloseOutBulletTest`` — §S3, Workflow Rules: the
  close-out bullet names the status flip and the ``Coverage baseline:`` line together, as the
  branch's last commit, while the close-out order gate stays green.
- ``AgentsMdMapDetectorTest`` / ``AgentsMdMapTest`` — §S5: the ``tools/`` row, the check tool in
  Development Commands, the two coverage tables in Important Files, and the force-include sentence
  unchanged.
- ``PythonReferenceDeltasDetectorTest`` / ``PythonReferenceDeltasTest`` — §S4: the ``crucible``
  skill's ``references/python.md`` "Model B deltas" states, for a project measuring coverage
  through the python client, ``--cov-source`` naming the project's own sources beside the client's
  default being Crucible's; coverage.py 7.10 or later with ``patch = ["subprocess"]``, in a child
  whose interpreter has coverage.py and inherits the environment; and removing ``.coverage`` and
  ``.coverage.*`` before a coverage run (:data:`DELTA_CHECKS`). Proved on synthetic text first,
  each element alone; the conforming sample also passes the skill guards (raw runner, AXI
  envelope, client-path anchoring, registry key, manual run), so the contract is satisfiable.
- ``TreeDriftDetectorTest`` / ``CrucibleReportPythonUnchangedTest`` — §S4: the byte-faithful
  ``skills-src/crucible-report-python/`` is byte-identical to its committed state on the
  merge-base with develop, and the ``crucible`` skill's frontmatter is unchanged; the drift reader
  is proved on a temp git repository first. (The skills loading in Pi with no diagnostics is the
  existing Pi skill-loader gate in ``tests/test_skill_frontmatter.py``, not repeated here.)

The §S2 tests assert the observable contract only: a table line per area and one for the total
(the area or ``total``, ``<hit>/<found>`` and the one-decimal percent as whole tokens), the
expected files the lcov has no record for named on stdout and no other expected file, a line
naming ``scripts/gate-lock.sh`` as unmeasured, the exit code, and the reason on stderr. Every tool
test first asserts the tool exists, because a missing script also makes ``python3`` exit 2.

Stdlib only.
"""

import ast
import hashlib
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path

from tests._helpers import REPO_ROOT, files_under, md_section, split_frontmatter
from tests.test_axi_envelope_read_whole import axi_findings
from tests.test_board_holds_the_queue import norm_units, section_matching, units
from tests.test_bootstrap_shutdown_registry import normalise
from tests.test_client_path_anchoring import _anchoring_hits, _fixture_tree
from tests.test_client_run_rule import manual_run_findings
from tests.test_installer_assets import (
    _DevelopRefUnresolvable,
    _git_committed_blob_sha256,
    _git_merge_base_with_develop,
)
from tests.test_orchestration_rules_from_crucible import CLOSE_OUT_ORDER, order_findings
from tests.test_project_registry_schema import _registry_names_named
from tests.test_raw_runner_guard import runner_findings
from tests.test_suite_hygiene import _fenced_commands, _full_suite_runs

AGENTS_MD = REPO_ROOT / "AGENTS.md"
PYPROJECT = REPO_ROOT / "pyproject.toml"
TOOL = REPO_ROOT / "tools" / "coverage-check.py"

#: §S1 — ``[tool.coverage.run]`` and ``[tool.coverage.report]``, exactly.
SOURCE = ["modelb_axi", "scripts", "hooks-src/scripts", "workflows-src", "tools"]
PATCH = ["subprocess"]
OMIT = ["scripts/toon.py"]
COV_SOURCE = ",".join(SOURCE)

#: The Important Files sentence §S5 keeps as it is.
FORCE_INCLUDE_SENTENCE = (
    "`force-include` maps `skills-src`, `generator`, `scripts`, `hooks-src`, `workflows-src` into "
    "`modelb_axi/_assets/` (`contracts/` is repo-only: no runtime consumer, not in the wheel or the "
    "sdist). **Any new asset root must be added there or it will not ship in the wheel.**")


# ------------------------------------------------------------------ helpers ----

def _commands(text: str) -> list[str]:
    """Every command ``text`` shows: its fenced commands (comments cut, continuations joined) and
    the code spans of its prose, each with its whitespace collapsed."""
    prose = re.sub(r"^[ \t]*```.*?^[ \t]*```[^\n]*$", " ", text, flags=re.S | re.M)
    spans = [" ".join(span.split()) for span in re.findall(r"`([^`]+)`", prose)]
    return _fenced_commands(text) + spans


def _flat(text: str) -> str:
    """``text`` with backticks dropped, whitespace collapsed and lower-cased — ``*`` kept, so a
    ``.coverage.*`` glob survives (``normalise`` drops it)."""
    return " ".join(text.replace("`", " ").split()).lower()


#: A coverage command: the client's ``regression --coverage`` or its ``pre-merge-gate``.
COVERAGE_COMMAND = re.compile(
    r"python-crucible\.py\s+(?:regression\b(?=.*\s--coverage(?![\w-]))|pre-merge-gate(?![\w-]))")
#: ``--cov-source <value>`` or ``--cov-source=<value>``, the value bare or quoted.
COV_SOURCE_FLAG = re.compile(r"\s--cov-source(?:\s+|=)(\"[^\"]*\"|'[^']*'|\S+)")


def cov_source_findings(text: str, source) -> list[str]:
    """§S1: what the coverage commands of ``text`` (an ``AGENTS.md``) get wrong — none shown, one
    with no ``--cov-source``, or one whose value split on ``,`` is not ``source`` in order."""
    runs = [c for c in _commands(text) if COVERAGE_COMMAND.search(c)]
    if not runs:
        return ["no coverage command"]
    out = []
    for run in runs:
        match = COV_SOURCE_FLAG.search(run)
        if match is None:
            out.append(f"no --cov-source: {run}")
        elif match.group(1).strip("\"'").split(",") != list(source):
            out.append(f"--cov-source is not the [tool.coverage.run] source: {run}")
    return out


# ----------------------------------------------------------------- §S3 checks ----

STEP_1 = "step 1 removes test-reports/vidushi-mdb/.coverage and .coverage.* before the gate run"
STEP_2 = ("step 2 runs pre-merge-gate with --cov-source, --agent vidushi-mdb, --cycle, --log and "
          "MODELB_HOME, XDG_DATA_HOME and PI_CODING_AGENT_DIR")
STEP_3 = "the empty-HOME and clean-runner runs stay test runs"
STEP_4 = ("step 4 runs python3 tools/coverage-check.py test-reports/vidushi-mdb/coverage.lcov "
          "against the branch's AGENTS.md")
STEP_5 = "a drop needs the user's explicit approval"
STEP_6 = "the orchestrator records the total on the Coverage baseline: line in the status-flip commit"
POST_MERGE = "the post-merge develop gate is a coverage run"
BASELINE_LINE = "a Coverage baseline: line carrying <hit>/<found> in Testing & QA"
REGRESSION_EXAMPLE = "the regression --coverage example carries --cov-source after --coverage"
FULL_SUITE_TEST = "a full-suite test command is still shown"

GATE_COMMAND = re.compile(r"python-crucible\.py\s+pre-merge-gate(?![\w-])")
REMOVAL = (re.compile(r"test-reports/vidushi-mdb/\.coverage(?![\w.*])"),
           re.compile(r"\.coverage\.\*"),
           re.compile(r"(?<![\w-])(?:rm|remove[sd]?|delete[sd]?)(?![\w-])"))
CHECK_COMMAND = re.compile(
    r"^python3 tools/coverage-check\.py test-reports/vidushi-mdb/coverage\.lcov"
    r"(?: --baseline (?:\./)?AGENTS\.md)?$")
#: A ``Coverage baseline:`` line's first ``<hit>/<found>``.
FIGURE = re.compile(r"(?<![\d/])(\d+)/(\d+)(?![\d/])")


def testing_section(text: str) -> str:
    return md_section(text, "## Testing & QA")


def _first_index(items, predicate) -> int | None:
    return next((i for i, item in enumerate(items) if predicate(item)), None)


def _removes_before_the_run(section: str) -> bool:
    raw = units(section)
    removal = _first_index(raw, lambda u: all(rx.search(_flat(u)) for rx in REMOVAL))
    gate = _first_index(raw, lambda u: GATE_COMMAND.search(u) is not None)
    return removal is not None and gate is not None and removal < gate


def _gate_command_complete(section: str) -> bool:
    def complete(cmd: str) -> bool:
        return (GATE_COMMAND.search(cmd) is not None
                and COV_SOURCE_FLAG.search(cmd) is not None
                and re.search(r"\s--agent\s+vidushi-mdb(?![\w-])", cmd) is not None
                and re.search(r"\s--cycle(?:\s+|=)\S", cmd) is not None
                and re.search(r"\s--log(?:\s+|=)\S", cmd) is not None
                and all(re.search(rf"(?<![\w$]){var}=\S", cmd)
                        for var in ("MODELB_HOME", "XDG_DATA_HOME", "PI_CODING_AGENT_DIR")))
    return any(complete(c) for c in _commands(section))


def _other_runs_stay_test_runs(section: str) -> bool:
    stated = [u for u in norm_units(section)
              if re.search(r"\bempty[- ]home\b", u) and re.search(r"\bclean[- ]runner\b", u)
              and re.search(r"(?<![\w-])test runs?\b", u)]
    empty_home = [c for c in _fenced_commands(section)
                  if re.search(r"python-crucible\.py\s+test\b", c)
                  and re.search(r"(?<![\w$])HOME=", c)]
    return bool(stated) and bool(empty_home)


def _check_against_the_branch(section: str) -> bool:
    invoked = [c for c in _commands(section) if CHECK_COMMAND.match(c)]
    stated = [u for u in norm_units(section)
              if "tools/coverage-check.py" in u and re.search(r"\bbranch'?s agents\.md\b", u)]
    return bool(invoked) and bool(stated)


def _unit_matches(section: str, *patterns: str) -> bool:
    return any(all(re.search(p, u) for p in patterns) for u in norm_units(section))


def baseline_lines(text: str) -> list[str]:
    """The lines of ``text`` that start with ``Coverage baseline:``."""
    return [line for line in text.splitlines() if line.startswith("Coverage baseline:")]


def baseline_figure(line: str) -> tuple[int, int] | None:
    """The ``(hit, found)`` a ``Coverage baseline:`` line carries; ``None`` when it carries none,
    or one with ``found`` zero or ``hit`` above ``found``."""
    match = FIGURE.search(line[len("Coverage baseline:"):])
    if match is None:
        return None
    hit, found = int(match.group(1)), int(match.group(2))
    return (hit, found) if found > 0 and hit <= found else None


def _baseline_line_in_testing(section: str) -> bool:
    lines = baseline_lines(section)
    return len(lines) == 1 and baseline_figure(lines[0]) is not None


def _regression_example(section: str) -> bool:
    return any(re.search(r"python-crucible\.py\s+regression\s.*--coverage(?![\w-]).*\s--cov-source"
                         r"(?:\s+|=)\S", c) for c in _fenced_commands(section))


def _full_suite_test_shown(section: str) -> bool:
    return any(re.search(r"python-crucible\.py\s+test\b", c) for c in _full_suite_runs(section))


#: §S3 — each element of the gate ``AGENTS.md``'s Testing & QA states, as ``(name, check)``; a
#: check takes the Testing & QA section.
GATE_CHECKS = (
    (STEP_1, _removes_before_the_run),
    (STEP_2, _gate_command_complete),
    (STEP_3, _other_runs_stay_test_runs),
    (STEP_4, _check_against_the_branch),
    (STEP_5, lambda s: _unit_matches(
        s, r"\bdrop\b[^.;]{0,40}\bneeds the user'?s explicit approval\b")),
    (STEP_6, lambda s: _unit_matches(
        s, r"\borchestrator records\b[^.;]{0,30}\btotal\b", r"coverage baseline:",
        r"\bstatus[- ]flip commit\b")),
    (POST_MERGE, lambda s: _unit_matches(
        s, r"\bpost-merge develop gate\b[^.;]{0,30}\bcoverage run\b")),
    (BASELINE_LINE, _baseline_line_in_testing),
    (REGRESSION_EXAMPLE, _regression_example),
    (FULL_SUITE_TEST, _full_suite_test_shown),
)


def gate_findings(text: str) -> list[str]:
    """§S3: the name of every :data:`GATE_CHECKS` element the Testing & QA of ``text`` (an
    ``AGENTS.md``) lacks, in order."""
    section = testing_section(text)
    return [name for name, check in GATE_CHECKS if not check(section)]


CLOSE_OUT_LAST_COMMIT = ("the close-out bullet names the status flip and the Coverage baseline: "
                         "line together, as the branch's last commit")


def close_out_findings(text: str) -> list[str]:
    """§S3, Workflow Rules: one ``;`` clause of the Workflow Rules close-out bullet of ``text``
    names the ``**Status:**`` flip, the ``Coverage baseline:`` line and the branch's last commit."""
    rules = section_matching(text, r"^workflow rules\b")
    bullets = [u for u in norm_units(rules) if u.startswith("- close-out order")]
    clauses = [c for b in bullets for c in b.split(";")]
    if any(re.search(r"\bstatus:\s*flip\b", c) and "coverage baseline:" in c
           and re.search(r"\bbranch'?s last commit\b", c) for c in clauses):
        return []
    return [CLOSE_OUT_LAST_COMMIT]


# ----------------------------------------------------------------- §S5 checks ----

TOOLS_ROW = "the Key Directories table has a tools/ row: repo-only, never deployed"
DEV_COMMAND = "Development Commands show python3 tools/coverage-check.py <lcov>"
COVERAGE_TABLES = ("Important Files name pyproject.toml's [tool.coverage.run] and "
                   "[tool.coverage.report]")
FORCE_INCLUDE = "the force-include sentence is unchanged"


def map_findings(text: str) -> list[str]:
    """§S5: what ``AGENTS.md``'s map (``text``) lacks."""
    out = []
    rows = [normalise(line) for line in md_section(text, "## Key Directories").splitlines()
            if re.match(r"^\|\s*`?tools/?`?\s*\|", line.strip())]
    if not [r for r in rows if re.search(r"\brepo-only\b", r) and re.search(r"\bnever deployed\b", r)]:
        out.append(TOOLS_ROW)
    if not [c for c in _fenced_commands(md_section(text, "## Development Commands"))
            if re.match(r"^python3 tools/coverage-check\.py \S+", c)]:
        out.append(DEV_COMMAND)
    important = md_section(text, "## Important Files")
    if not [u for u in norm_units(important) if "pyproject.toml" in u
            and "[tool.coverage.run]" in u and "[tool.coverage.report]" in u]:
        out.append(COVERAGE_TABLES)
    if FORCE_INCLUDE_SENTENCE not in important:
        out.append(FORCE_INCLUDE)
    return out


# ------------------------------------------------------- synthetic AGENTS.md ----

GOOD_KEY_DIRS = (
    "## Key Directories\n\n| Path | Purpose |\n|---|---|\n"
    "| `scripts/` | The tool-script asset class, deployed to `~/.agents/scripts/` |\n"
    "| `tools/` | Repo-only tools, never deployed: `coverage-check.py`, the gate's coverage check |\n\n")
GOOD_DEV = (
    "## Development Commands\n\n```bash\n"
    "python3 generator/build.py --check\n"
    "python3 tools/coverage-check.py test-reports/vidushi-mdb/coverage.lcov   # the coverage check\n"
    "```\n\n")
GOOD_IMPORTANT = (
    "## Important Files\n\n"
    "- `pyproject.toml` — hatchling; " + FORCE_INCLUDE_SENTENCE + "\n"
    "- `pyproject.toml`'s `[tool.coverage.run]` (`source`, `patch`) and `[tool.coverage.report]` "
    "(`omit`) — the config every coverage run measures under.\n\n")
GOOD_TESTING = (
    "## Testing & QA\n\nPure **`unittest`**.\n\n```bash\n"
    "python3 ~/.crucible/clients/python-crucible.py test --tests tests.test_hooks --agent X  # one module\n"
    "python3 ~/.crucible/clients/python-crucible.py test --agent vidushi-mdb --log /tmp/full.log  # full suite\n"
    "env HOME=\"$(mktemp -d)\" python3 ~/.crucible/clients/python-crucible.py test --agent vidushi-mdb  # empty HOME\n"
    "python3 ~/.crucible/clients/python-crucible.py regression --coverage --cov-source " + COV_SOURCE + " \\\n"
    "  --agent vidushi-mdb --project-dir \"$PWD\"\n"
    "```\n\n"
    "Coverage baseline: 4188/6121 lines (68.4%), measured under the `[tool.coverage]` config.\n\n"
    "Model B's pre-merge gate, in order:\n\n"
    "1. **Clear the stale data.** Remove `test-reports/vidushi-mdb/.coverage` and every "
    "`.coverage.*` beside it.\n"
    "2. **The real-`HOME` run:** `env MODELB_HOME=\"$(mktemp -d)\" XDG_DATA_HOME=\"$(mktemp -d)\" "
    "PI_CODING_AGENT_DIR=\"$(mktemp -d)\" python3 ~/.crucible/clients/python-crucible.py "
    "pre-merge-gate --cov-source " + COV_SOURCE + " --agent vidushi-mdb --cycle <last cycle> "
    "--log /tmp/gate.log`.\n"
    "3. **The other two runs:** the empty-`HOME` run and the clean-runner run stay `test` runs.\n"
    "4. **The check:** `python3 tools/coverage-check.py test-reports/vidushi-mdb/coverage.lcov` runs "
    "against the branch's `AGENTS.md`; its table goes into the merge sign-off.\n"
    "5. **A drop** (exit 1) needs the user's explicit approval at sign-off.\n"
    "6. **The orchestrator records the new total** on the `Coverage baseline:` line, in the "
    "close-out's docs-only status-flip commit.\n\n"
    "- **When develop moves before the merge,** the post-merge develop gate is a coverage run, run "
    "as steps 1–2.\n\n")
GOOD_RULES = (
    "## Workflow Rules (Model B, solo)\n\n"
    "- Close-out order (`orchestration-common.md` § Close-out): merge `develop` into the feature "
    "branch until behind=0; run the pre-merge gate while the plan's last cycle is still active, "
    "bound to it with `--cycle`; `cycle-done`; `unregister`, then `register`, which clears the "
    "binding; the merge sign-off; the spec's `**Status:**` flip and the `Coverage baseline:` line "
    "together, the branch's last commit; the merge; `cr-close`.\n")
GOOD_AGENTS = ("# Repository Guidelines\n\n" + GOOD_KEY_DIRS + GOOD_DEV + GOOD_IMPORTANT
               + GOOD_TESTING + GOOD_RULES)


# ------------------------------------------------------------------- §S1 ----

class CoverageConfigTest(unittest.TestCase):
    """§S1 — ``pyproject.toml``'s two coverage tables, exactly."""

    @classmethod
    def setUpClass(cls):
        with PYPROJECT.open("rb") as fh:
            cls.config = tomllib.load(fh)
        cls.coverage = cls.config.get("tool", {}).get("coverage", {})

    def test_coverage_run_is_exactly_the_source_list_in_order_and_the_subprocess_patch(self):
        self.assertEqual(self.coverage.get("run"), {"source": SOURCE, "patch": PATCH},
                         "§S1: [tool.coverage.run] is exactly source (in order) and patch")

    def test_coverage_report_omits_exactly_the_generated_toon_twin(self):
        self.assertEqual(self.coverage.get("report"), {"omit": OMIT},
                         "§S1: [tool.coverage.report] is exactly omit = [\"scripts/toon.py\"]")

    def test_the_wheel_force_include_is_untouched_by_the_coverage_tables(self):
        roots = list(self.config["tool"]["hatch"]["build"]["targets"]["wheel"]["force-include"])
        self.assertEqual(roots, ["skills-src", "generator", "scripts", "hooks-src", "workflows-src"],
                         "§S1/§S2: tools/ is repo-only and never ships in the wheel")


class CovSourceDetectorTest(unittest.TestCase):
    """§S1 — :func:`cov_source_findings`, both ways on synthetic text."""

    def test_the_conforming_text_passes(self):
        self.assertEqual(cov_source_findings(GOOD_AGENTS, SOURCE), [])

    def test_todays_regression_example_without_cov_source_is_a_finding(self):
        todays = GOOD_AGENTS.replace(" --cov-source " + COV_SOURCE + " \\\n", " \\\n")
        self.assertEqual(len(cov_source_findings(todays, SOURCE)), 1)
        self.assertTrue(cov_source_findings(todays, SOURCE)[0].startswith("no --cov-source: "))

    def test_a_reordered_or_shorter_list_is_a_finding_in_a_code_span_too(self):
        reordered = ",".join(reversed(SOURCE))
        text = GOOD_AGENTS.replace(
            "pre-merge-gate --cov-source " + COV_SOURCE, "pre-merge-gate --cov-source " + reordered)
        self.assertEqual(len(cov_source_findings(text, SOURCE)), 1, "the code-span gate command")
        shorter = GOOD_AGENTS.replace("--cov-source " + COV_SOURCE + " \\",
                                      "--cov-source modelb_axi,scripts \\")
        self.assertEqual(len(cov_source_findings(shorter, SOURCE)), 1, "the fenced example")

    def test_a_quoted_or_equals_value_counts(self):
        text = GOOD_AGENTS.replace("--cov-source " + COV_SOURCE + " \\",
                                   f"--cov-source=\"{COV_SOURCE}\" \\")
        self.assertEqual(cov_source_findings(text, SOURCE), [])

    def test_text_with_no_coverage_command_is_a_finding(self):
        self.assertEqual(cov_source_findings("# Nothing\n\n```bash\nls\n```\n", SOURCE),
                         ["no coverage command"])


class AgentsMdCovSourceTest(unittest.TestCase):
    """§S1 — every coverage command in the real ``AGENTS.md`` names ``source`` as
    ``--cov-source``."""

    def test_every_coverage_command_in_agents_md_passes_the_source_list_as_cov_source(self):
        with PYPROJECT.open("rb") as fh:
            source = tomllib.load(fh).get("tool", {}).get("coverage", {}).get("run", {}).get("source")
        self.assertEqual(source, SOURCE, "precondition: §S1's source list")
        self.assertEqual(cov_source_findings(AGENTS_MD.read_text(encoding="utf-8"), SOURCE), [])


# ------------------------------------------------------------------- §S2 ----

def _toml_list(items) -> str:
    return "[" + ", ".join(f'"{item}"' for item in items) + "]"


def _pyproject(source=SOURCE, omit=OMIT) -> str:
    return ("[project]\nname = \"fixture\"\nversion = \"0.0.0\"\n\n"
            f"[tool.coverage.run]\nsource = {_toml_list(source)}\npatch = [\"subprocess\"]\n\n"
            f"[tool.coverage.report]\nomit = {_toml_list(omit)}\n")


def _record(path: str, hit: int, found: int) -> str:
    """One lcov record as coverage.py 7.16 writes it: ``SF``, the ``DA`` lines, ``LF``/``LH``, a
    function block, ``end_of_record``."""
    lines = "".join(f"DA:{n},{1 if n <= hit else 0}\n" for n in range(1, found + 1))
    return (f"SF:{path}\n{lines}LF:{found}\nLH:{hit}\n"
            f"FN:1,{found},main\nFNDA:{1 if hit else 0},main\nFNF:1\nFNH:{1 if hit else 0}\n"
            "end_of_record\n")


def _lcov(records) -> str:
    return "".join(_record(*r) for r in records)


#: The fixture tree: every file the temp project root holds besides the config and lcov.
TREE = (
    "modelb_axi/__init__.py", "modelb_axi/cli.py", "modelb_axi/deploy.py", "modelb_axi/axi.py",
    "modelb_axi/sub/inner.py", "modelb_axi/__pycache__/cached.py",
    "scripts/worktree-flow.py", "scripts/schedule_db.py", "scripts/toon.py", "scripts/gate-lock.sh",
    "hooks-src/schema.md", "hooks-src/scripts/block-direct-python-test",
    "hooks-src/scripts/session-start-banner", "hooks-src/scripts/__pycache__/x.cpython-314.pyc",
    "workflows-src/stamp_version.py", "workflows-src/changelog_section.py",
    "workflows-src/release/test.yml",
    "tools/other.py",
    "docs/notes.md",
)
#: The known lcov: ``(path, hit, found)``; per area modelb_axi 12/16, scripts 1/4,
#: hooks-src/scripts 5/6, workflows-src 2/3, tools 0/7; total 20/36.
KNOWN = (
    ("modelb_axi/__init__.py", 1, 1),
    ("modelb_axi/cli.py", 8, 10),
    ("modelb_axi/deploy.py", 3, 5),
    ("scripts/worktree-flow.py", 1, 4),
    ("hooks-src/scripts/block-direct-python-test", 5, 6),
    ("workflows-src/stamp_version.py", 2, 3),
    ("tools/other.py", 0, 7),
)
KNOWN_AREAS = (("modelb_axi", 12, 16), ("scripts", 1, 4), ("hooks-src/scripts", 5, 6),
               ("workflows-src", 2, 3), ("tools", 0, 7))
KNOWN_TOTAL = (20, 36)
#: The expected files :data:`KNOWN` has no record for, under §S1's omit.
KNOWN_MISSING = ("modelb_axi/axi.py", "modelb_axi/sub/inner.py", "scripts/schedule_db.py",
                 "hooks-src/scripts/session-start-banner", "workflows-src/changelog_section.py")
#: Fixture files that are never expected: a ``report.omit`` path, a non-``*.py`` file under an
#: area, anything under ``__pycache__``, a file outside every area.
NEVER_EXPECTED = ("scripts/toon.py", "workflows-src/release/test.yml",
                  "modelb_axi/__pycache__/cached.py",
                  "hooks-src/scripts/__pycache__/x.cpython-314.pyc", "hooks-src/schema.md",
                  "docs/notes.md")


def _token(text: str) -> re.Pattern:
    """``text`` as a whole token: no path or word character on either side."""
    return re.compile(r"(?<![\w./-])" + re.escape(text) + r"(?![\w./-])")


def _figure(hit: int, found: int) -> re.Pattern:
    return re.compile(rf"(?<![\d/]){hit}/{found}(?![\d/])")


def _percent(hit: int, found: int) -> re.Pattern:
    return re.compile(r"(?<![\d.])" + re.escape(f"{100 * hit / found:.1f}") + r"(?![\d])")


def _table_lines(stdout: str, label: re.Pattern, hit: int, found: int) -> list[str]:
    """The stdout lines carrying ``label``, ``<hit>/<found>`` and the one-decimal percent."""
    return [line for line in stdout.splitlines()
            if label.search(line) and _figure(hit, found).search(line)
            and _percent(hit, found).search(line)]


def _snapshot(root: Path) -> dict:
    """Every path under ``root`` → its sha256 (``None`` for a directory)."""
    return {str(p.relative_to(root)): (hashlib.sha256(p.read_bytes()).hexdigest()
                                       if p.is_file() else None)
            for p in sorted(root.rglob("*"))}


class CoverageCheckFixture(unittest.TestCase):
    """A temp project root: :data:`TREE`, a ``pyproject.toml`` with §S1's tables, the known
    lcov at ``coverage.lcov`` and an ``AGENTS.md`` whose baseline is the known total."""

    def setUp(self):
        self.assertTrue(TOOL.is_file(), "§S2: tools/coverage-check.py exists")
        self.root = Path(tempfile.mkdtemp(prefix="mdb-covcheck-"))
        self.addCleanup(shutil.rmtree, self.root, True)
        for rel in TREE:
            path = self.root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("# fixture\n", encoding="utf-8")
        self.write("pyproject.toml", _pyproject())
        self.write("coverage.lcov", _lcov(KNOWN))
        self.baseline(*KNOWN_TOTAL)

    def write(self, rel: str, text: str) -> Path:
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def baseline(self, hit: int, found: int, rel: str = "AGENTS.md") -> Path:
        return self.write(rel, "# Fixture\n\nSome text about 3/4 of nothing.\n\n"
                          f"Coverage baseline: {hit}/{found} lines, measured under the fixture.\n"
                          "\nMore text.\n")

    def run_tool(self, *args: str) -> subprocess.CompletedProcess:
        proc = subprocess.run([sys.executable, str(TOOL), *args], cwd=self.root,
                              capture_output=True, text=True, timeout=60)
        self.assertNotIn("Traceback", proc.stderr, "the tool never fails with a traceback")
        return proc


class CoverageCheckTableTest(CoverageCheckFixture):
    """§S2 — the per-area table and the total, from the known lcov."""

    def test_each_area_has_exactly_one_line_with_its_hit_found_and_one_decimal_percent(self):
        proc = self.run_tool("coverage.lcov")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        for area, hit, found in KNOWN_AREAS:
            with self.subTest(area=area):
                self.assertEqual(len(_table_lines(proc.stdout, _token(area), hit, found)), 1,
                                 f"§S2: one table line for {area}, {hit}/{found}; stdout:\n"
                                 f"{proc.stdout}")

    def test_the_extensionless_hook_record_counts_in_the_hooks_area_not_the_scripts_area(self):
        proc = self.run_tool("coverage.lcov")
        self.assertEqual(_table_lines(proc.stdout, _token("scripts"), 6, 10), [],
                         "§S2: hooks-src/scripts/<name> does not fold into scripts")
        self.assertEqual(len(_table_lines(proc.stdout, _token("hooks-src/scripts"), 5, 6)), 1,
                         proc.stdout)

    def test_the_total_line_carries_the_sum_and_its_one_decimal_percent(self):
        proc = self.run_tool("coverage.lcov")
        total = re.compile(r"\btotal\b", re.IGNORECASE)
        self.assertEqual(len(_table_lines(proc.stdout, total, *KNOWN_TOTAL)), 1,
                         f"§S2: one total line, 20/36 and 55.6; stdout:\n{proc.stdout}")

    def test_the_areas_come_from_the_projects_pyproject_source(self):
        self.write("pyproject.toml", _pyproject(source=["pkg", "bin"], omit=[]))
        self.write("pkg/a.py", "")
        self.write("bin/b.py", "")
        self.write("coverage.lcov", _lcov((("pkg/a.py", 2, 3), ("bin/b.py", 1, 7))))
        self.baseline(1, 10)
        proc = self.run_tool("coverage.lcov")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(len(_table_lines(proc.stdout, _token("pkg"), 2, 3)), 1, proc.stdout)
        self.assertEqual(len(_table_lines(proc.stdout, _token("bin"), 1, 7)), 1, proc.stdout)
        self.assertEqual([line for line in proc.stdout.splitlines()
                          if _token("modelb_axi").search(line)], [],
                         "§S2: an area the config does not declare has no line")


class CoverageCheckMissingFilesTest(CoverageCheckFixture):
    """§S2 — the expected files with no record, and ``scripts/gate-lock.sh`` as unmeasured."""

    def test_every_expected_file_without_a_record_is_named_and_no_other(self):
        proc = self.run_tool("coverage.lcov")
        for rel in KNOWN_MISSING:
            with self.subTest(missing=rel):
                self.assertRegex(proc.stdout, _token(rel), f"§S2: {rel} has no record")
        for rel, _hit, _found in KNOWN:
            with self.subTest(recorded=rel):
                self.assertNotRegex(proc.stdout, _token(rel), "a recorded file is not missing")

    def test_a_report_omit_path_a_yml_pycache_and_a_file_outside_the_areas_are_never_expected(self):
        proc = self.run_tool("coverage.lcov")
        for rel in NEVER_EXPECTED:
            with self.subTest(never=rel):
                self.assertNotRegex(proc.stdout, _token(rel), f"§S2: {rel} is not expected")

    def test_the_omit_comes_from_the_projects_report_table(self):
        self.write("pyproject.toml", _pyproject(omit=["modelb_axi/axi.py"]))
        proc = self.run_tool("coverage.lcov")
        self.assertNotRegex(proc.stdout, _token("modelb_axi/axi.py"), "now omitted")
        self.assertRegex(proc.stdout, _token("scripts/toon.py"),
                         "§S2: with no omit for it, scripts/toon.py is expected and missing")

    def test_scripts_gate_lock_sh_is_named_as_unmeasured(self):
        proc = self.run_tool("coverage.lcov")
        lines = [line for line in proc.stdout.splitlines()
                 if _token("scripts/gate-lock.sh").search(line)
                 and re.search(r"\bunmeasured\b|\bnot measured\b", line, re.IGNORECASE)]
        self.assertEqual(len(lines), 1, f"§S2: one line names it unmeasured; stdout:\n{proc.stdout}")


class CoverageCheckVerdictTest(CoverageCheckFixture):
    """§S2 — the exact comparison against the baseline, and ``--baseline``."""

    def test_an_equal_total_exits_0(self):
        proc = self.run_tool("coverage.lcov")
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_an_equal_ratio_with_other_figures_exits_0(self):
        self.baseline(40, 72)
        self.assertEqual(self.run_tool("coverage.lcov").returncode, 0)

    def test_a_higher_total_exits_0(self):
        self.baseline(19, 36)
        self.assertEqual(self.run_tool("coverage.lcov").returncode, 0)

    def test_a_lower_total_exits_1_naming_both_figures_on_stderr(self):
        self.baseline(21, 36)
        proc = self.run_tool("coverage.lcov")
        self.assertEqual(proc.returncode, 1, proc.stderr)
        self.assertRegex(proc.stderr, _figure(20, 36), "§S2: the measured total")
        self.assertRegex(proc.stderr, _figure(21, 36), "§S2: the baseline")

    def test_equal_rounded_percents_with_a_lower_exact_ratio_exit_1(self):
        # 24/36 and 667/1000 both print 66.7; 24/36 is the lower ratio.
        self.write("coverage.lcov", _lcov((("modelb_axi/cli.py", 10, 15),
                                           ("modelb_axi/deploy.py", 4, 6),
                                           ("scripts/worktree-flow.py", 2, 3),
                                           ("hooks-src/scripts/block-direct-python-test", 4, 6),
                                           ("workflows-src/stamp_version.py", 2, 3),
                                           ("tools/other.py", 2, 3))))
        self.baseline(667, 1000)
        proc = self.run_tool("coverage.lcov")
        self.assertEqual(f"{100 * 24 / 36:.1f}", f"{100 * 667 / 1000:.1f}", "precondition")
        self.assertEqual(proc.returncode, 1, proc.stderr)
        self.assertRegex(proc.stderr, _figure(24, 36))
        self.assertRegex(proc.stderr, _figure(667, 1000))
        self.baseline(2, 3)
        self.assertEqual(self.run_tool("coverage.lcov").returncode, 0, "the same ratio passes")

    def test_baseline_names_a_file_other_than_agents_md(self):
        self.baseline(30, 36)
        self.baseline(10, 36, rel="docs/other-baseline.md")
        default = self.run_tool("coverage.lcov")
        self.assertEqual(default.returncode, 1, "§S2: the default is ./AGENTS.md, 30/36")
        other = self.run_tool("coverage.lcov", "--baseline", "docs/other-baseline.md")
        self.assertEqual(other.returncode, 0, other.stderr)
        self.baseline(30, 36, rel="docs/other-baseline.md")
        self.baseline(10, 36)
        self.assertEqual(self.run_tool("coverage.lcov", "--baseline",
                                       "docs/other-baseline.md").returncode, 1,
                         "§S2: --baseline is read, not ./AGENTS.md")


class CoverageCheckErrorTest(CoverageCheckFixture):
    """§S2 — exit 2, its reason on stderr."""

    def test_a_missing_lcov_exits_2_naming_it(self):
        proc = self.run_tool("missing.lcov")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("missing.lcov", proc.stderr)

    def test_an_lcov_with_no_records_exits_2(self):
        self.write("coverage.lcov", "")
        proc = self.run_tool("coverage.lcov")
        self.assertEqual(proc.returncode, 2)
        self.assertRegex(proc.stderr, re.compile(r"record", re.IGNORECASE))

    def test_a_record_outside_every_area_exits_2_naming_it(self):
        self.write("coverage.lcov", _lcov(KNOWN + (("docs/notes.py", 1, 2),)))
        proc = self.run_tool("coverage.lcov")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("docs/notes.py", proc.stderr)

    def test_a_record_outside_the_projects_areas_exits_2(self):
        self.write("pyproject.toml", _pyproject(source=["pkg"], omit=[]))
        self.write("pkg/a.py", "")
        self.write("coverage.lcov", _lcov((("pkg/a.py", 1, 2),) + KNOWN))
        proc = self.run_tool("coverage.lcov")
        self.assertEqual(proc.returncode, 2, "§S2: modelb_axi is no area of this config")
        self.assertIn("modelb_axi/", proc.stderr)

    def test_a_baseline_file_with_no_coverage_baseline_line_exits_2(self):
        self.write("AGENTS.md", "# Fixture\n\nNo figure here, though 20/36 appears.\n")
        proc = self.run_tool("coverage.lcov")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("Coverage baseline", proc.stderr)

    def test_a_baseline_line_not_at_the_start_of_its_line_does_not_count(self):
        self.write("AGENTS.md", "# Fixture\n\n- Coverage baseline: 20/36 lines.\n")
        proc = self.run_tool("coverage.lcov")
        self.assertEqual(proc.returncode, 2, "§S2: the line starts with `Coverage baseline:`")
        self.assertIn("Coverage baseline", proc.stderr)

    def test_a_baseline_file_with_two_coverage_baseline_lines_exits_2(self):
        self.write("AGENTS.md", "# Fixture\n\nCoverage baseline: 20/36\n\nCoverage baseline: 20/36\n")
        proc = self.run_tool("coverage.lcov")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("Coverage baseline", proc.stderr)


class CoverageCheckWritesNothingTest(CoverageCheckFixture):
    """§S2 — the tool writes nothing: the temp root is unchanged after a pass, a drop and an
    error."""

    def test_the_temp_root_is_unchanged_after_every_verdict(self):
        before = _snapshot(self.root)
        self.assertEqual(self.run_tool("coverage.lcov").returncode, 0)
        self.assertEqual(_snapshot(self.root), before, "after exit 0")
        lower = self.baseline(21, 36)
        before = _snapshot(self.root)
        self.assertEqual(self.run_tool("coverage.lcov").returncode, 1)
        self.assertEqual(_snapshot(self.root), before, "after exit 1")
        lower.write_text("# no line\n", encoding="utf-8")
        before = _snapshot(self.root)
        self.assertEqual(self.run_tool("coverage.lcov").returncode, 2)
        self.assertEqual(_snapshot(self.root), before, "after exit 2")


def _imported_top_level_modules(source: str) -> set[str]:
    """The top-level module of every absolute import in ``source``."""
    names = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.add(node.module.split(".")[0])
    return names


class CoverageCheckStdlibTest(unittest.TestCase):
    """§S2, stdlib — the tool imports only the standard library; its first line is the
    ``env`` shebang."""

    def test_the_import_scan_bites_on_a_third_party_import(self):
        source = "import os\nfrom coverage import Coverage\nimport xml.dom\nfrom . import x\n"
        self.assertEqual(_imported_top_level_modules(source) - set(sys.stdlib_module_names),
                         {"coverage"})

    def test_the_tool_imports_only_the_standard_library(self):
        self.assertTrue(TOOL.is_file(), "§S2: tools/coverage-check.py exists")
        imported = _imported_top_level_modules(TOOL.read_text(encoding="utf-8"))
        self.assertIn("tomllib", imported, "§S2: the areas are read with tomllib")
        self.assertEqual(sorted(imported - set(sys.stdlib_module_names)), [])

    def test_the_tools_first_line_is_the_env_python3_shebang(self):
        self.assertTrue(TOOL.is_file(), "§S2: tools/coverage-check.py exists")
        first = TOOL.read_text(encoding="utf-8").splitlines()[0]
        self.assertEqual(first, "#!/usr/bin/env python3")


# ------------------------------------------------------------------- §S3 ----

class GateStepsDetectorTest(unittest.TestCase):
    """§S3 — :func:`gate_findings`, both ways on synthetic text, each element alone."""

    def test_the_conforming_text_passes(self):
        self.assertEqual(gate_findings(GOOD_AGENTS), [])

    def test_todays_testing_section_lacks_every_gate_element_but_the_full_suite_run(self):
        todays = GOOD_AGENTS.split("Coverage baseline:")[0].replace(
            " --cov-source " + COV_SOURCE, "") + GOOD_RULES
        self.assertEqual(gate_findings(todays),
                         [name for name, _check in GATE_CHECKS if name != FULL_SUITE_TEST])

    def test_each_element_bites_alone(self):
        cases = (
            (STEP_1, "Remove `test-reports/vidushi-mdb/.coverage` and every `.coverage.*`",
             "Keep `test-reports/vidushi-mdb/.coverage` and every `.coverage.*`"),
            (STEP_1, "every `.coverage.*` beside it", "the lcov beside it"),
            (STEP_2, " --cycle <last cycle>", ""),
            (STEP_2, " --log /tmp/gate.log", ""),
            (STEP_2, "--agent vidushi-mdb --cycle", "--agent someone --cycle"),
            (STEP_2, "PI_CODING_AGENT_DIR=\"$(mktemp -d)\" ", ""),
            (STEP_2, "pre-merge-gate --cov-source " + COV_SOURCE, "pre-merge-gate"),
            (STEP_3, "the clean-runner run stay `test` runs",
             "the clean-runner run become `pre-merge-gate` runs"),
            (STEP_4, "`python3 tools/coverage-check.py test-reports/vidushi-mdb/coverage.lcov` runs",
             "`python3 tools/coverage-check.py --lcov test-reports/vidushi-mdb/coverage.lcov` runs"),
            (STEP_4, "against the branch's `AGENTS.md`", "against develop"),
            (STEP_5, "needs the user's explicit approval", "is recorded"),
            (STEP_6, "in the close-out's docs-only status-flip commit", "later"),
            (STEP_6, "on the `Coverage baseline:` line", "somewhere"),
            (POST_MERGE, "the post-merge develop gate is a coverage run",
             "the post-merge develop gate is a test run"),
            (BASELINE_LINE, "Coverage baseline: 4188/6121 lines", "Coverage baseline: unknown"),
            (BASELINE_LINE, "Coverage baseline: 4188/6121 lines", "- Coverage baseline: 4188/6121"),
            (BASELINE_LINE, "Coverage baseline: 4188/6121 lines", "Coverage baseline: 6121/4188"),
            (REGRESSION_EXAMPLE, "regression --coverage --cov-source " + COV_SOURCE + " \\",
             "regression --coverage \\"),
        )
        for name, old, new in cases:
            with self.subTest(element=name, old=old):
                self.assertEqual(GOOD_AGENTS.count(old), 1, old)
                self.assertIn(name, gate_findings(GOOD_AGENTS.replace(old, new)))

    def test_regression_and_gate_runs_do_not_replace_the_full_suite_test_command(self):
        text = GOOD_AGENTS.replace("test --agent vidushi-mdb --log /tmp/full.log  # full suite",
                                   "test --tests tests.test_x --agent vidushi-mdb  # a module")
        text = text.replace("python-crucible.py test --agent vidushi-mdb  # empty HOME",
                            "python-crucible.py test --tests tests.test_y --agent vidushi-mdb")
        self.assertEqual(GOOD_AGENTS.count("python-crucible.py test --agent"), 2, "precondition")
        self.assertNotIn("python-crucible.py test --agent", text)
        self.assertIn(FULL_SUITE_TEST, gate_findings(text),
                      "§S3: a pre-merge-gate or regression run does not replace the test command")

    def test_the_removal_counts_only_before_the_gate_run(self):
        step_1 = ("1. **Clear the stale data.** Remove `test-reports/vidushi-mdb/.coverage` and every "
                  "`.coverage.*` beside it.\n")
        moved = GOOD_AGENTS.replace(step_1, "1. **Start.**\n").replace(
            "6. **The orchestrator", step_1.replace("1.", "7.", 1) + "6. **The orchestrator")
        self.assertEqual(gate_findings(moved), [STEP_1])

    def test_a_baseline_line_outside_testing_and_qa_does_not_count(self):
        line = "Coverage baseline: 4188/6121 lines (68.4%), measured under the `[tool.coverage]` config.\n\n"
        moved = GOOD_AGENTS.replace(line, "").replace("## Key Directories", line + "## Key Directories")
        self.assertEqual(gate_findings(moved), [BASELINE_LINE])


class AgentsMdGateStepsTest(unittest.TestCase):
    """§S3, the steps — the real ``AGENTS.md``'s Testing & QA states each element."""

    @classmethod
    def setUpClass(cls):
        cls.findings = gate_findings(AGENTS_MD.read_text(encoding="utf-8"))

    def test_step_1_removes_the_stale_coverage_data_before_the_run(self):
        self.assertNotIn(STEP_1, self.findings)

    def test_step_2_runs_pre_merge_gate_with_cov_source_cycle_log_and_the_sandbox(self):
        self.assertNotIn(STEP_2, self.findings)

    def test_the_empty_home_and_clean_runner_runs_stay_test_runs(self):
        self.assertNotIn(STEP_3, self.findings)

    def test_step_4_runs_the_existing_check_tool_against_the_branchs_agents_md(self):
        self.assertTrue(TOOL.is_file(), "§S3: step 4 names the existing tools/coverage-check.py")
        self.assertNotIn(STEP_4, self.findings)

    def test_a_drop_needs_the_users_explicit_approval(self):
        self.assertNotIn(STEP_5, self.findings)

    def test_the_orchestrator_records_the_total_in_the_status_flip_commit(self):
        self.assertNotIn(STEP_6, self.findings)

    def test_the_post_merge_develop_gate_is_a_coverage_run(self):
        self.assertNotIn(POST_MERGE, self.findings)

    def test_the_regression_coverage_example_carries_cov_source(self):
        self.assertNotIn(REGRESSION_EXAMPLE, self.findings)

    def test_a_full_suite_test_command_is_still_shown(self):
        self.assertNotIn(FULL_SUITE_TEST, self.findings)


class AgentsMdCoverageBaselineTest(unittest.TestCase):
    """§S3, the first figure (its format half) — one ``Coverage baseline:`` line, in Testing &
    QA, carrying ``<hit>/<found>``; and the tool parses it (the re-measure is the orchestrator's
    gate, not a test)."""

    @classmethod
    def setUpClass(cls):
        cls.text = AGENTS_MD.read_text(encoding="utf-8")

    def test_agents_md_has_exactly_one_coverage_baseline_line_in_testing_and_qa(self):
        self.assertEqual(len(baseline_lines(self.text)), 1,
                         "§S3: exactly one line starts with `Coverage baseline:`")
        self.assertNotIn(BASELINE_LINE, gate_findings(self.text))

    def test_the_tool_parses_the_real_baseline_line(self):
        self.assertTrue(TOOL.is_file(), "§S2: tools/coverage-check.py exists")
        lines = baseline_lines(self.text)
        self.assertEqual(len(lines), 1, "§S3: one `Coverage baseline:` line")
        figure = baseline_figure(lines[0])
        self.assertIsNotNone(figure, lines[0])
        assert figure is not None
        self.assertGreater(figure[0], 0, "a measured baseline hits lines")
        with tempfile.TemporaryDirectory(prefix="mdb-covcheck-real-") as tmp:
            root = Path(tmp)
            (root / "pyproject.toml").write_text(_pyproject(), encoding="utf-8")
            files = [f"{area}/f.py" for area in SOURCE]
            for rel in files:
                (root / rel).parent.mkdir(parents=True, exist_ok=True)
                (root / rel).write_text("", encoding="utf-8")
            for name, (hit, want) in (("full.lcov", (1, 0)), ("empty.lcov", (0, 1))):
                (root / name).write_text(_lcov([(rel, hit, 1) for rel in files]),
                                         encoding="utf-8")
                proc = subprocess.run([sys.executable, str(TOOL), name, "--baseline", str(AGENTS_MD)],
                                      cwd=root, capture_output=True, text=True, timeout=60)
                with self.subTest(lcov=name):
                    self.assertEqual(proc.returncode, want, proc.stderr)


class CloseOutBulletDetectorTest(unittest.TestCase):
    """§S3, Workflow Rules — :func:`close_out_findings`, both ways on synthetic text; the close-out
    order gate passes on the conforming sample."""

    def test_the_conforming_text_passes_and_keeps_the_close_out_order(self):
        self.assertEqual(close_out_findings(GOOD_AGENTS), [])
        self.assertEqual(order_findings(section_matching(GOOD_AGENTS, r"^workflow rules\b"),
                                        CLOSE_OUT_ORDER), [])

    def test_todays_bullet_without_the_baseline_line_is_a_finding(self):
        todays = GOOD_AGENTS.replace(" and the `Coverage baseline:` line together", "")
        self.assertEqual(close_out_findings(todays), [CLOSE_OUT_LAST_COMMIT])

    def test_the_baseline_line_in_another_clause_is_a_finding(self):
        split = GOOD_AGENTS.replace(
            "the spec's `**Status:**` flip and the `Coverage baseline:` line together, the branch's "
            "last commit;",
            "the `Coverage baseline:` line; the spec's `**Status:**` flip, the branch's last commit;")
        self.assertNotEqual(split, GOOD_AGENTS)
        self.assertEqual(close_out_findings(split), [CLOSE_OUT_LAST_COMMIT])

    def test_no_last_commit_is_a_finding(self):
        text = GOOD_AGENTS.replace("together, the branch's last commit;", "together;")
        self.assertNotEqual(text, GOOD_AGENTS)
        self.assertEqual(close_out_findings(text), [CLOSE_OUT_LAST_COMMIT])


class AgentsMdCloseOutBulletTest(unittest.TestCase):
    """§S3, Workflow Rules — the real close-out bullet."""

    def test_the_close_out_bullet_names_the_status_flip_and_the_baseline_line_as_the_last_commit(self):
        text = AGENTS_MD.read_text(encoding="utf-8")
        self.assertEqual(close_out_findings(text), [])
        self.assertEqual(order_findings(section_matching(text, r"^workflow rules\b"),
                                        CLOSE_OUT_ORDER), [], "the close-out order stays")


# ------------------------------------------------------------------- §S5 ----

class AgentsMdMapDetectorTest(unittest.TestCase):
    """§S5 — :func:`map_findings`, both ways on synthetic text, each element alone."""

    def test_the_conforming_text_passes(self):
        self.assertEqual(map_findings(GOOD_AGENTS), [])

    def test_each_element_bites_alone(self):
        cases = (
            (TOOLS_ROW, "| `tools/` | Repo-only tools, never deployed:", "| `tools/` | Tools:"),
            (TOOLS_ROW, "| `tools/` |", "| `toolsx/` |"),
            (DEV_COMMAND, "python3 tools/coverage-check.py test-reports/vidushi-mdb/coverage.lcov   #",
             "python3 tools/other.py   #"),
            (COVERAGE_TABLES, " and `[tool.coverage.report]` (`omit`)", ""),
            (FORCE_INCLUDE, "or it will not ship in the wheel.**", "or it may not ship.**"),
        )
        for name, old, new in cases:
            with self.subTest(element=name, old=old):
                self.assertEqual(GOOD_AGENTS.count(old), 1, old)
                self.assertEqual(map_findings(GOOD_AGENTS.replace(old, new)), [name])

    def test_the_tools_row_counts_only_in_key_directories(self):
        row = "| `tools/` | Repo-only tools, never deployed: `coverage-check.py`, the gate's coverage check |\n"
        moved = GOOD_AGENTS.replace(row, "").replace("## Important Files\n\n",
                                                     "## Important Files\n\n" + row + "\n")
        self.assertIn(TOOLS_ROW, map_findings(moved))


class AgentsMdMapTest(unittest.TestCase):
    """§S5 — the real ``AGENTS.md``'s map."""

    @classmethod
    def setUpClass(cls):
        cls.findings = map_findings(AGENTS_MD.read_text(encoding="utf-8"))

    def test_key_directories_names_tools_as_repo_only_and_never_deployed(self):
        self.assertNotIn(TOOLS_ROW, self.findings)

    def test_development_commands_show_the_check_tool(self):
        self.assertNotIn(DEV_COMMAND, self.findings)

    def test_important_files_name_the_two_coverage_tables(self):
        self.assertNotIn(COVERAGE_TABLES, self.findings)

    def test_the_force_include_sentence_is_unchanged(self):
        self.assertNotIn(FORCE_INCLUDE, self.findings)


# ----------------------------------------------------------------- "Model B deltas" ----

PYTHON_REFERENCE = REPO_ROOT / "skills-src" / "crucible" / "references" / "python.md"
PYTHON_REFERENCE_REL = "skills-src/crucible/references/python.md"
REPORT_PYTHON_BUNDLE = "skills-src/crucible-report-python"
CRUCIBLE_SKILL_REL = "skills-src/crucible/SKILL.md"

DELTA_COV_SOURCE = ("--cov-source names the project's own sources, beside the client's default "
                    "being Crucible's")
DELTA_SUBPROCESS = ('coverage.py 7.10 or later with patch = ["subprocess"], in a child whose '
                    "interpreter has coverage.py and inherits the environment")
DELTA_STALE_DATA = "remove .coverage and .coverage.* before a coverage run"

#: Where "Model B deltas" opens: its lead-in line, or a heading of that name.
_DELTAS_START = re.compile(r"^(?:#{1,6}\s+)?Model B deltas\b")
_FENCE_LINE = re.compile(r"^\s*(?:```|~~~)")


def model_b_deltas(text: str) -> str:
    """The "Model B deltas" section of a ``crucible`` reference: from its lead-in line (or a
    heading of that name) to the next heading outside a fence, or the end; ``""`` when absent."""
    lines = text.splitlines()
    start = next((i for i, line in enumerate(lines) if _DELTAS_START.match(line)), None)
    if start is None:
        return ""
    fenced, end = False, len(lines)
    for i in range(start + 1, len(lines)):
        if _FENCE_LINE.match(lines[i]):
            fenced = not fenced
        elif not fenced and lines[i].startswith("#"):
            end = i
            break
    return "\n".join(lines[start:end])


def _delta_unit(unit: str) -> str:
    """A unit read for the §S4 checks: :func:`_flat` (``*`` kept) with curly quotes straightened."""
    return _flat(unit).replace("’", "'").replace("‘", "'")


#: §S4 — each element of "Model B deltas" as ``(name, regexes)``; ONE unit (a bullet with its
#: continuation lines, or a paragraph) of the section must match every regex of an element.
DELTA_CHECKS = (
    (DELTA_COV_SOURCE, (
        r"(?<![\w-])--cov-source(?![\w-])",
        r"\b(?:the project'?s|its) own (?:packages?|directories|sources?|source directories|code)\b",
        r"\bdefault[^.;]{0,80}(?:\bcrucible'?s\b|crucible_axi)"
        r"|(?:\bcrucible'?s\b|crucible_axi)[^.;]{0,80}\bdefault",
    )),
    (DELTA_SUBPROCESS, (
        r"\bcoverage\.py (?:(?:>=|≥) ?7\.10(?![\d.])|7\.10(?![\d.])(?:\+| or (?:later|newer)\b))",
        r"\bpatch\s*=\s*\[\s*[\"']subprocess[\"']\s*\]",
        r"\bchild\b",
        r"\binterpreter\b[^.;]{0,60}\bcoverage\.py\b"
        r"|\bcoverage\.py\b[^.;]{0,20}\binstalled\b[^.;]{0,40}\binterpreter\b",
        r"\binherit\w*\b[^.;]{0,30}\benvironment\b",
    )),
    (DELTA_STALE_DATA, (
        r"(?<![\w.])\.coverage(?![\w.*])",
        r"\.coverage\.\*",
        REMOVAL[2].pattern,
        r"\bbefore\b[^.;]{0,40}\bcoverage run\b",
    )),
)


def deltas_findings(text: str) -> list[str]:
    """§S4: the name of every :data:`DELTA_CHECKS` element the "Model B deltas" of ``text`` (the
    python reference) does not state in one unit, in order."""
    found = [_delta_unit(u) for u in units(model_b_deltas(text))]
    return [name for name, rxs in DELTA_CHECKS
            if not any(all(re.search(rx, u) for rx in rxs) for u in found)]


#: The python reference as it stands before §S4 (the shape §S4 adds to).
TODAYS_PYTHON_REFERENCE = (
    "# Crucible — Python stack (thin router)\n\n"
    "**Authority:** the Model-B-owned bundled skill `crucible-report-python`\n"
    "(`skills-src/crucible-report-python/`, deployed by the modelb-axi installer)\n"
    "— the full verb surface (`test --tests <dotted.path>`, `regression\n"
    "[--coverage]`, `check`, `auto-ingest` (recovery only), gates), endpoint routing,\n"
    "venv/interpreter rules, and report locations live THERE. Read it before\n"
    "running anything.\n\n"
    "Model B deltas only:\n\n"
    "- Client: `~/.crucible/clients/python-crucible.py` — Crucible's installed\n"
    "  client, listed in `~/.crucible/crucible-clients.json`; never a checkout of\n"
    "  the Crucible project (see the `crucible` skill for why).\n"
    "- Agent naming: `CR-<ACRONYM>-NNN-<cycle id>-<ROLE>` for TDD-role agents;\n"
    "  `<agent-type>-<project>` for orchestrators. Pass `--agent` and\n"
    "  `--project-dir` explicitly.\n")
#: The three §S4 bullets, one line each so a cut names exactly what it removes.
GOOD_DELTA_BULLETS = (
    "- Coverage: pass `--cov-source` to `regression --coverage` and `pre-merge-gate`, naming the "
    "project's own packages and directories, because the client's default names Crucible's own "
    "(`crucible_axi,clients`).\n"
    "- Subprocesses: scripts the tests run as subprocesses are measured only with coverage.py 7.10 "
    "or later and `patch = [\"subprocess\"]` in the project's coverage config, and only in a child "
    "whose interpreter has coverage.py and inherits the environment.\n"
    "- Stale data: remove the reports directory's `.coverage` and every `.coverage.*` before a "
    "coverage run, because a stale data file is merged into the next run's figures.\n")
GOOD_PYTHON_REFERENCE = TODAYS_PYTHON_REFERENCE + GOOD_DELTA_BULLETS


# ------------------------------------------------- crucible-report-python drift ----

def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def live_digests(root: Path, rel_dir: str) -> dict[str, str]:
    """``{path: sha256}`` of every file under ``root/rel_dir`` (``__pycache__`` aside), each path
    relative to ``root``, POSIX-spelled."""
    return {p.relative_to(root).as_posix(): _sha256_bytes(p.read_bytes())
            for p in files_under(root / rel_dir) if "__pycache__" not in p.parts}


def committed_digests(root: Path, commit: str, rel_dir: str) -> dict[str, str]:
    """``{path: sha256}`` of every file under ``rel_dir`` as committed at ``commit`` in the git
    repository ``root`` (``git ls-tree``, then each blob through ``git show``)."""
    listed = subprocess.run(["git", "ls-tree", "-r", "--name-only", commit, "--", rel_dir],
                            cwd=str(root), capture_output=True, text=True, timeout=30)
    if listed.returncode != 0:
        raise RuntimeError(f"git ls-tree {commit} -- {rel_dir} failed: {listed.stderr.strip()}")
    return {rel: _git_committed_blob_sha256(commit, rel, root)
            for rel in listed.stdout.splitlines() if rel.strip()}


def committed_text(root: Path, commit: str, rel: str) -> str:
    """``rel`` as committed at ``commit`` in the git repository ``root``, as UTF-8 text."""
    shown = subprocess.run(["git", "show", f"{commit}:{rel}"], cwd=str(root),
                           capture_output=True, timeout=30)
    if shown.returncode != 0:
        raise RuntimeError(f"git show {commit}:{rel} failed: "
                           f"{shown.stderr.decode('utf-8', errors='replace').strip()}")
    return shown.stdout.decode("utf-8")


def tree_drift(committed: dict[str, str], live: dict[str, str]) -> list[str]:
    """How ``live`` differs from ``committed`` (both ``{path: sha256}``): ``changed: <path>``,
    ``removed: <path>`` and ``added: <path>``, each sorted."""
    return ([f"changed: {p}" for p in sorted(committed.keys() & live.keys())
             if committed[p] != live[p]]
            + [f"removed: {p}" for p in sorted(committed.keys() - live.keys())]
            + [f"added: {p}" for p in sorted(live.keys() - committed.keys())])


# ------------------------------------------------------------------- §S4 ----

class PythonReferenceDeltasDetectorTest(unittest.TestCase):
    """§S4 — :func:`deltas_findings`, both ways on synthetic text, each element alone."""

    def test_the_conforming_text_passes(self):
        self.assertEqual(deltas_findings(GOOD_PYTHON_REFERENCE), [])

    def test_todays_python_reference_lacks_every_element(self):
        self.assertEqual(deltas_findings(TODAYS_PYTHON_REFERENCE),
                         [DELTA_COV_SOURCE, DELTA_SUBPROCESS, DELTA_STALE_DATA])

    def test_each_element_bites_alone(self):
        cases = (
            (DELTA_COV_SOURCE, "pass `--cov-source` to", "pass a source list to"),
            (DELTA_COV_SOURCE, ", naming the project's own packages and directories,", ","),
            (DELTA_COV_SOURCE,
             "because the client's default names Crucible's own (`crucible_axi,clients`)",
             "because it is required"),
            (DELTA_SUBPROCESS, "coverage.py 7.10 or later and", "coverage.py 7.1 or later and"),
            (DELTA_SUBPROCESS, "coverage.py 7.10 or later and", "coverage.py 7.10 and"),
            (DELTA_SUBPROCESS, "coverage.py 7.10 or later and", "coverage.py and"),
            (DELTA_SUBPROCESS, '`patch = ["subprocess"]`', '`patch = ["thread"]`'),
            (DELTA_SUBPROCESS, '`patch = ["subprocess"]`', "the patch"),
            (DELTA_SUBPROCESS,
             "in a child whose interpreter has coverage.py and inherits the environment",
             "in a child that inherits the environment"),
            (DELTA_SUBPROCESS,
             "in a child whose interpreter has coverage.py and inherits the environment",
             "in a child whose interpreter has coverage.py"),
            (DELTA_SUBPROCESS, "only in a child whose", "only in a process whose"),
            (DELTA_STALE_DATA, "and every `.coverage.*` before", "and the lcov before"),
            (DELTA_STALE_DATA, "the reports directory's `.coverage` and every `.coverage.*`",
             "every `.coverage.*`"),
            (DELTA_STALE_DATA, "Stale data: remove the reports", "Stale data: keep the reports"),
            (DELTA_STALE_DATA, "before a coverage run", "after a coverage run"),
        )
        for name, old, new in cases:
            with self.subTest(element=name, old=old, new=new):
                self.assertEqual(GOOD_PYTHON_REFERENCE.count(old), 1, old)
                self.assertEqual(deltas_findings(GOOD_PYTHON_REFERENCE.replace(old, new)), [name])

    def test_each_element_counts_only_within_one_unit(self):
        split = GOOD_PYTHON_REFERENCE.replace(
            " because the client's default names Crucible's own",
            "\n\nThe client's default names Crucible's own")
        self.assertNotEqual(split, GOOD_PYTHON_REFERENCE)
        self.assertEqual(deltas_findings(split), [DELTA_COV_SOURCE])

    def test_the_elements_count_only_inside_model_b_deltas(self):
        before = TODAYS_PYTHON_REFERENCE.replace(
            "Model B deltas only:\n", GOOD_DELTA_BULLETS + "\nModel B deltas only:\n")
        after = TODAYS_PYTHON_REFERENCE + "\n## Elsewhere\n\n" + GOOD_DELTA_BULLETS
        for where, text in (("before the lead-in", before), ("under a later heading", after)):
            with self.subTest(where=where):
                self.assertEqual(text.count("--cov-source"), 1, "precondition")
                self.assertEqual(deltas_findings(text),
                                 [DELTA_COV_SOURCE, DELTA_SUBPROCESS, DELTA_STALE_DATA])

    def test_a_model_b_deltas_heading_and_a_fenced_comment_keep_the_section(self):
        heading = GOOD_PYTHON_REFERENCE.replace("Model B deltas only:", "## Model B deltas")
        fenced = GOOD_PYTHON_REFERENCE.replace(
            "- Coverage:", "```bash\n# a comment, not a heading\n```\n\n- Coverage:")
        for shape, text in (("heading", heading), ("fence", fenced)):
            with self.subTest(shape=shape):
                self.assertNotEqual(text, GOOD_PYTHON_REFERENCE)
                self.assertEqual(deltas_findings(text), [])

    def test_a_missing_model_b_deltas_section_lacks_every_element(self):
        text = GOOD_PYTHON_REFERENCE.replace("Model B deltas only:", "Notes:")
        self.assertEqual(deltas_findings(text),
                         [DELTA_COV_SOURCE, DELTA_SUBPROCESS, DELTA_STALE_DATA])

    def test_the_conforming_text_passes_the_skill_guards(self):
        """The contract is satisfiable: the conforming sample trips none of the guards over
        ``skills-src/`` that §S4's new text must keep green."""
        text = GOOD_PYTHON_REFERENCE
        self.assertEqual(runner_findings(text), [], "the raw-runner guard")
        self.assertEqual(axi_findings(text), [], "the AXI-envelope guard")
        self.assertEqual(_registry_names_named(PYTHON_REFERENCE_REL, text), [],
                         "the registry-key detector")
        self.assertEqual(manual_run_findings(text), [], "the client-run rule's manual-run phrases")
        self.assertIn("~/.crucible/clients/python-crucible.py", text, "the installed client")
        tmp, root = _fixture_tree({PYTHON_REFERENCE_REL: text})
        with tmp:
            hits = _anchoring_hits(root, ("skills-src",))
        self.assertEqual(hits, [], "the client-path anchoring gate")


class PythonReferenceDeltasTest(unittest.TestCase):
    """§S4 — the real ``skills-src/crucible/references/python.md``'s "Model B deltas"."""

    @classmethod
    def setUpClass(cls):
        cls.findings = deltas_findings(PYTHON_REFERENCE.read_text(encoding="utf-8"))

    def test_cov_source_names_the_projects_own_sources_beside_the_clients_crucible_default(self):
        self.assertNotIn(DELTA_COV_SOURCE, self.findings)

    def test_subprocesses_need_coverage_7_10_the_subprocess_patch_and_a_child_with_coverage(self):
        self.assertNotIn(DELTA_SUBPROCESS, self.findings)

    def test_the_stale_coverage_data_is_removed_before_a_coverage_run(self):
        self.assertNotIn(DELTA_STALE_DATA, self.findings)


class TreeDriftDetectorTest(unittest.TestCase):
    """§S4 — :func:`tree_drift` over :func:`committed_digests` and :func:`live_digests`, both
    ways on a temp git repository."""

    BUNDLE = "skills-src/bundle"

    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="mdb-drift-")
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        (self.root / self.BUNDLE).mkdir(parents=True)
        (self.root / self.BUNDLE / "SKILL.md").write_bytes(b"---\nname: bundle\n---\nbody\n")
        (self.root / "elsewhere.md").write_bytes(b"outside the bundle\n")
        for args in (["init", "-q"], ["add", "-A"],
                     ["-c", "user.name=t", "-c", "user.email=t@example.invalid",
                      "-c", "commit.gpgsign=false", "-c", "core.hooksPath=/dev/null",
                      "commit", "-q", "-m", "base"]):
            done = subprocess.run(["git", *args], cwd=str(self.root), capture_output=True,
                                  text=True, timeout=30)
            self.assertEqual(done.returncode, 0, done.stderr)

    def drift(self) -> list[str]:
        return tree_drift(committed_digests(self.root, "HEAD", self.BUNDLE),
                          live_digests(self.root, self.BUNDLE))

    def test_an_untouched_bundle_has_no_drift_and_the_reader_sees_only_the_bundle(self):
        self.assertEqual(committed_digests(self.root, "HEAD", self.BUNDLE).keys(),
                         {f"{self.BUNDLE}/SKILL.md"})
        self.assertEqual(self.drift(), [])

    def test_a_one_byte_change_is_drift(self):
        (self.root / self.BUNDLE / "SKILL.md").write_bytes(b"---\nname: bundle\n---\nbody \n")
        self.assertEqual(self.drift(), [f"changed: {self.BUNDLE}/SKILL.md"])

    def test_an_added_file_is_drift(self):
        (self.root / self.BUNDLE / "references").mkdir()
        (self.root / self.BUNDLE / "references" / "new.md").write_bytes(b"new\n")
        self.assertEqual(self.drift(), [f"added: {self.BUNDLE}/references/new.md"])

    def test_a_removed_file_is_drift(self):
        (self.root / self.BUNDLE / "SKILL.md").unlink()
        self.assertEqual(self.drift(), [f"removed: {self.BUNDLE}/SKILL.md"])

    def test_a_change_outside_the_bundle_is_not_drift(self):
        (self.root / "elsewhere.md").write_bytes(b"changed\n")
        self.assertEqual(self.drift(), [])

    def test_the_committed_text_reads_the_commit_not_the_working_tree(self):
        (self.root / self.BUNDLE / "SKILL.md").write_bytes(b"---\nname: other\n---\nbody\n")
        committed = committed_text(self.root, "HEAD", f"{self.BUNDLE}/SKILL.md")
        self.assertEqual(split_frontmatter(committed)[0], "name: bundle")


class CrucibleReportPythonUnchangedTest(unittest.TestCase):
    """§S4 — ``crucible-report-python`` is a byte-faithful import and is not changed: it is
    byte-identical to its committed state on the merge-base with develop; the ``crucible`` skill's
    frontmatter is unchanged too."""

    def merge_base(self) -> str:
        try:
            return _git_merge_base_with_develop(REPO_ROOT)
        except _DevelopRefUnresolvable as exc:
            self.skipTest(f"cannot resolve 'develop' or 'origin/develop' in this clone: {exc}")

    def test_crucible_report_python_is_byte_identical_to_the_merge_base_with_develop(self):
        base = self.merge_base()
        committed = committed_digests(REPO_ROOT, base, REPORT_PYTHON_BUNDLE)
        self.assertIn(f"{REPORT_PYTHON_BUNDLE}/SKILL.md", committed, "precondition: the bundle")
        self.assertEqual(tree_drift(committed, live_digests(REPO_ROOT, REPORT_PYTHON_BUNDLE)), [],
                         "§S4: crucible-report-python is a byte-faithful import, not changed")

    def test_the_crucible_skills_frontmatter_is_unchanged(self):
        base = self.merge_base()
        committed = split_frontmatter(committed_text(REPO_ROOT, base, CRUCIBLE_SKILL_REL))[0]
        self.assertIn("name: crucible", committed, "precondition: the committed frontmatter")
        live = split_frontmatter((REPO_ROOT / CRUCIBLE_SKILL_REL).read_text(encoding="utf-8"))[0]
        self.assertEqual(live, committed, "§S4: the crucible skill's frontmatter is unchanged")


if __name__ == "__main__":
    unittest.main()
