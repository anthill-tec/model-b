"""``scripts/skill-release-gate.py`` names no project (CR-MDB-081 §S7 — AC8, AC9).

- ``SkillDiscoveryTest`` — AC8 / §S7: with no configured skill paths and an ``agentskills``
  stand-in on ``PATH``, phase 1 validates exactly the skills under ``skills/``,
  ``.agents/skills/`` and ``.pi/skills/`` -- each ``<name>/SKILL.md`` once -- and not one under
  ``.claude/skills/``, which is no longer read.
- ``MongoTeardownRemovedTest`` — AC9 / §S7: the script carries neither the Mongo-drop teardown
  step nor ``VIDUSHI_MONGO_URI``; a configuration carrying ``[teardown] drop_mongo_db``, with no
  engine or checks, is refused when the configuration loads -- the gate exits non-zero naming
  ``[teardown] cmd`` before any phase runs, wherever the configuration is found.
- ``ConfigDiscoveryTest`` — §S8: where the configuration is found -- ``pyproject.toml``'s
  ``[tool.skill-release]``, the standalone ``.skill-release.toml``, ``--config`` nested or at top
  level -- and the exit code when there is none.
- ``PhaseOneValidatorTest`` — §S8: phase 1 with an ``agentskills`` stand-in that passes and one
  that fails, and the verdict each gives.

Those gate runs are subprocesses of the test interpreter under ``tests/_helpers.py``'s
``run_tool`` (§S9): a fixture project in a temp directory, the tools' own variables
(``SKILLGATE_SOON`` among them) cleared, a private ``TMPDIR`` set in the test process, and on
``PATH`` a logging ``agentskills`` stand-in that records each call's argv -- so no run ever
provisions ``skills-ref``, and no test reaches a package index or runs a real ``pip``.

The rest run in process (§S8): the script loaded as a module by its path, ``Gate.make_venv``
replaced by a stand-in returning a stand-in interpreter that writes a wheel or a console script,
and ``PATH`` set in the test process to a directory holding only the stand-ins a case calls.

- ``ProvisionValidatorTest`` — phase 1 with ``agentskills`` absent: ``skills-ref`` provisioned
  through ``make_venv`` and the provisioned validator used.
- ``EngineBuildTest`` — phase 2: the wheel built or not, the entry point, a forbidden entry point,
  glob counts and globs.
- ``CleanInstallTest`` — phase 3: the console installed or not, the import check.
- ``LifecycleCheckTest`` — phase 4: every check field.
- ``SubstitutionTest`` — ``$TMP``, ``$THROWAWAY_DB``, ``$SOON`` (with and without
  ``SKILLGATE_SOON``) and ``$TODAY``.
- ``TeardownTest`` — ``[teardown] cmd`` runs with the substitutions applied (AC9).
- ``GateRunVerdictTest`` — ``Gate.run``'s exit codes and verdict lines.

Stdlib only.
"""

import ast
import contextlib
import datetime
import importlib.util
import io
import json
import os
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests._helpers import (
    TOOL_OWN_ENV,
    TOOL_SCRIPTS_DIR,
    run_tool,
    tool_bin_dir,
    use_private_tmpdir,
    write_executable,
    write_files,
)

#: The script under test, in ``scripts/``.
SKILL_RELEASE_GATE = "skill-release-gate.py"

#: A ``SKILL.md`` body a fixture skill carries; the stand-in validator never reads it.
SKILL_MD = "---\nname: fixture\ndescription: a fixture skill\n---\n\n# Fixture\n"

#: The headers the gate prints as it enters each phase, and its closing result line: none may
#: appear when the configuration is refused at load.
PHASE_MARKERS = (
    "1. skill conformance",
    "2. engine build",
    "3. clean-install",
    "4. lifecycle",
    "RESULT:",
)

#: The retired teardown key and the configuration that carries it alone: no engine, no checks.
RETIRED_TEARDOWN_KEY = "drop_mongo_db"
RETIRED_TEARDOWN_TABLE = f'[teardown]\n{RETIRED_TEARDOWN_KEY} = "$THROWAWAY_DB"\n'

#: What the refusal names as the replacement (§S7).
TEARDOWN_CMD = "[teardown] cmd"

#: What a gate that checked nothing (``0 passed, 0 failed``) says as it fails.
NOTHING_CHECKED = re.compile(r"\bnothing\b(?: was| is)? checked\b|\bchecked nothing\b",
                             re.IGNORECASE)


class _SkillReleaseGateCase(unittest.TestCase):
    """A work area with a fixture project and a ``PATH`` of the host's ``git``/``tar`` plus a
    logging ``agentskills`` stand-in that prints ``valid skill`` and exits 0."""

    def setUp(self):
        self.work = Path(os.path.realpath(tempfile.mkdtemp(prefix="mdb-skill-gate-")))
        self.addCleanup(shutil.rmtree, self.work, True)
        use_private_tmpdir(self, self.work)
        self.project = self.work / "project"
        self.project.mkdir()
        self.validator_log = self.work / "agentskills.log"
        stand_in = (
            f"#!{sys.executable}\n"
            "import json, sys\n"
            f"with open({str(self.validator_log)!r}, 'a', encoding='utf-8') as fh:\n"
            "    fh.write(json.dumps(sys.argv[1:]) + '\\n')\n"
            "print('valid skill')\n"
        )
        self.bin_dir = tool_bin_dir(self.work / "bin", {"agentskills": stand_in})

    def _gate(self, *args):
        return run_tool(SKILL_RELEASE_GATE, "--project-dir", self.project, *args,
                        bin_dir=self.bin_dir, cwd=self.work)

    def _validator_calls(self) -> list:
        if not self.validator_log.exists():
            return []
        return [json.loads(line) for line in
                self.validator_log.read_text(encoding="utf-8").splitlines() if line]

    def _add_skills(self, *bases_and_names):
        write_files(self.project, {f"{rel}/SKILL.md": SKILL_MD for rel in bases_and_names})

    @staticmethod
    def _output(result) -> str:
        return f"exit {result.returncode}\n--- stdout\n{result.stdout}\n--- stderr\n{result.stderr}"


class SkillDiscoveryTest(_SkillReleaseGateCase):
    """AC8 / §S7: phase 1's discovery reads ``skills/``, ``.agents/skills/`` and ``.pi/skills/``
    and no longer ``.claude/skills/``."""

    def setUp(self):
        super().setUp()
        # A [skills] table with no `paths`: the gate discovers the skills itself.
        write_files(self.project, {".skill-release.toml": "[skills]\n"})

    def test_phase_one_validates_exactly_the_skills_under_the_three_skill_roots(self):
        self._add_skills("skills/alpha", ".agents/skills/beta", ".pi/skills/gamma",
                         ".claude/skills/delta")
        # A directory without a SKILL.md is not a skill, under any root.
        (self.project / ".agents" / "skills" / "not-a-skill").mkdir()

        result = self._gate()

        self.assertEqual(result.returncode, 0, self._output(result))
        calls = self._validator_calls()
        self.assertEqual([call[0] for call in calls], ["validate"] * len(calls),
                         f"every agentskills call is `validate <dir>`: {calls}")
        validated = sorted(os.path.realpath(call[1]) for call in calls)
        expected = sorted(os.path.realpath(self.project / rel) for rel in
                          ("skills/alpha", ".agents/skills/beta", ".pi/skills/gamma"))
        self.assertEqual(validated, expected,
                         "phase 1 validates each skill under skills/, .agents/skills/ and "
                         ".pi/skills/ exactly once, and nothing else\n" + self._output(result))
        for rel in ("skills/alpha", ".agents/skills/beta", ".pi/skills/gamma"):
            self.assertIn(rel, result.stdout, self._output(result))
        self.assertNotIn(".claude", result.stdout + result.stderr, self._output(result))

    def test_a_skill_under_claude_skills_alone_is_never_validated_and_the_gate_fails(self):
        self._add_skills(".claude/skills/delta")

        result = self._gate()

        self.assertEqual(self._validator_calls(), [],
                         ".claude/skills/ is no longer read\n" + self._output(result))
        output = result.stdout + result.stderr
        self.assertNotIn("1. skill conformance", result.stdout, self._output(result))
        self.assertNotIn(".claude", output, self._output(result))
        # With .claude/skills/ unread, nothing is checked -- and a gate that checked nothing
        # fails, saying so; it never passes the release.
        self.assertNotEqual(result.returncode, 0, self._output(result))
        self.assertRegex(_ANSI.sub("", output), NOTHING_CHECKED, self._output(result))
        self.assertNotIn("Release gate PASSED", output, self._output(result))


class MongoTeardownRemovedTest(_SkillReleaseGateCase):
    """AC9 / §S7: no Mongo-drop step, no ``VIDUSHI_MONGO_URI``; ``[teardown] drop_mongo_db`` is
    refused when the configuration loads, naming ``[teardown] cmd``, before any phase."""

    def _source(self) -> str:
        return (TOOL_SCRIPTS_DIR / SKILL_RELEASE_GATE).read_text(encoding="utf-8")

    def test_the_script_names_no_vidushi_mongo_uri(self):
        self.assertNotIn("VIDUSHI_MONGO_URI", self._source())

    def test_the_script_carries_no_mongo_drop_step(self):
        source = self._source()
        self.assertEqual([token for token in ("pymongo", "MongoClient", "drop_database")
                          if token in source], [],
                         "§S7: the teardown's Mongo-drop step is removed")

    def test_no_function_that_runs_a_command_reads_drop_mongo_db(self):
        # `drop_mongo_db` may still be named -- to refuse it -- but never by code that runs a
        # command, which is what a teardown step is.
        tree = ast.parse(self._source())
        docstrings = {id(node.body[0].value) for node in ast.walk(tree)
                      if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef))
                      and node.body and isinstance(node.body[0], ast.Expr)
                      and isinstance(node.body[0].value, ast.Constant)}
        steps = []
        for func in ast.walk(tree):
            if not isinstance(func, ast.FunctionDef):
                continue
            nodes = list(ast.walk(func))
            runs_a_command = any(
                isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and isinstance(n.func.value, ast.Name)
                and (n.func.value.id, n.func.attr) in {("subprocess", "run"),
                                                       ("subprocess", "Popen"),
                                                       ("subprocess", "call"),
                                                       ("subprocess", "check_call"),
                                                       ("os", "system")}
                for n in nodes)
            names_the_key = any(
                isinstance(n, ast.Constant) and isinstance(n.value, str)
                and id(n) not in docstrings and RETIRED_TEARDOWN_KEY in n.value
                for n in nodes)
            if runs_a_command and names_the_key:
                steps.append(func.name)
        self.assertEqual(steps, [], "§S7: drop_mongo_db is no longer a teardown step")

    def _assert_refused_before_any_phase(self, result):
        output = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0, self._output(result))
        self.assertIn(TEARDOWN_CMD, output,
                      "the refusal names `[teardown] cmd` as the replacement\n"
                      + self._output(result))
        self.assertEqual([marker for marker in PHASE_MARKERS if marker in output], [],
                         "refused when the configuration loads, before any phase\n"
                         + self._output(result))
        self.assertNotIn("Release gate PASSED", output, self._output(result))

    def test_a_standalone_config_carrying_drop_mongo_db_is_refused(self):
        write_files(self.project, {".skill-release.toml": RETIRED_TEARDOWN_TABLE})

        self._assert_refused_before_any_phase(self._gate())

    def test_a_pyproject_config_carrying_drop_mongo_db_is_refused(self):
        write_files(self.project, {"pyproject.toml": (
            '[project]\nname = "fixture"\nversion = "0.1.0"\n\n'
            f'[tool.skill-release.teardown]\n{RETIRED_TEARDOWN_KEY} = "$THROWAWAY_DB"\n')})

        self._assert_refused_before_any_phase(self._gate())

    def test_an_explicit_config_carrying_drop_mongo_db_is_refused(self):
        config = write_files(self.work / "elsewhere",
                             {"gate.toml": RETIRED_TEARDOWN_TABLE}) / "gate.toml"

        self._assert_refused_before_any_phase(self._gate("--config", config))

    def test_the_refusal_comes_before_phase_one_validates_a_present_skill(self):
        write_files(self.project, {".skill-release.toml": RETIRED_TEARDOWN_TABLE})
        self._add_skills("skills/alpha")

        result = self._gate()

        self._assert_refused_before_any_phase(result)
        self.assertEqual(self._validator_calls(), [],
                         "no skill is validated once the configuration is refused\n"
                         + self._output(result))


# ------------------------------------------------------------------ verdict parsing ----

#: The colour codes the gate wraps its PASS/FAIL words and headers in.
_ANSI = re.compile(r"\x1b\[[0-9;]*m")

#: The verdict line ``Gate.run`` prints last.
RESULT_PASSED = ("Release gate PASSED — skill + artifact conformance OK; "
                 "safe to `git flow release finish`.")
RESULT_FAILED = "Release gate FAILED — do not finish the release."


class _VerdictReading:
    """Reads the gate's printed verdicts with its colour codes stripped."""

    @staticmethod
    def _plain(text: str) -> str:
        return _ANSI.sub("", text)

    def _verdicts(self, text: str) -> list:
        """``[("PASS"|"FAIL", message), ...]`` in the order the gate printed them."""
        return re.findall(r"^  (PASS|FAIL) (.*)$", self._plain(text), re.M)

    def _details(self, text: str) -> list:
        """The ``      | <line>`` detail lines a FAIL prints, in order."""
        return re.findall(r"^      \| (.*)$", self._plain(text), re.M)

    def _headers(self, text: str) -> list:
        return re.findall(r"^== (.*)$", self._plain(text), re.M)

# ------------------------------------------------------------------ as subprocesses ----


class ConfigDiscoveryTest(_SkillReleaseGateCase, _VerdictReading):
    """§S8: the configuration is ``pyproject.toml``'s ``[tool.skill-release]``, else the
    standalone ``.skill-release.toml``; ``--config`` names a file nested or at top level; with
    none the gate exits 2. Each configuration names one skill path, so the validated path proves
    which configuration the gate read."""

    def setUp(self):
        super().setUp()
        self._add_skills("from-pyproject", "from-standalone", "from-config")

    def _validated(self) -> list:
        return [os.path.relpath(call[1], self.project) for call in self._validator_calls()]

    def _assert_read(self, result, rel):
        self.assertEqual(result.returncode, 0, self._output(result))
        self.assertEqual(self._validated(), [rel], self._output(result))
        self.assertEqual(self._verdicts(result.stdout), [("PASS", f"{rel}: valid skill")],
                         self._output(result))

    def test_pyproject_tool_skill_release_is_the_configuration(self):
        write_files(self.project, {"pyproject.toml": (
            '[project]\nname = "fixture"\nversion = "0.1.0"\n\n'
            '[tool.skill-release.skills]\npaths = ["from-pyproject"]\n')})

        self._assert_read(self._gate(), "from-pyproject")

    def test_pyproject_is_read_before_the_standalone_file(self):
        write_files(self.project, {
            "pyproject.toml": '[tool.skill-release.skills]\npaths = ["from-pyproject"]\n',
            ".skill-release.toml": '[skills]\npaths = ["from-standalone"]\n',
        })

        self._assert_read(self._gate(), "from-pyproject")

    def test_the_standalone_file_is_read_when_pyproject_has_no_gate_table(self):
        write_files(self.project, {
            "pyproject.toml": '[project]\nname = "fixture"\nversion = "0.1.0"\n',
            ".skill-release.toml": '[skills]\npaths = ["from-standalone"]\n',
        })

        self._assert_read(self._gate(), "from-standalone")

    def test_a_standalone_file_nesting_under_tool_skill_release_is_read_nested(self):
        write_files(self.project, {".skill-release.toml": (
            '[tool.skill-release.skills]\npaths = ["from-standalone"]\n')})

        self._assert_read(self._gate(), "from-standalone")

    def test_config_naming_a_nested_file_overrides_the_project_files(self):
        write_files(self.project, {
            "pyproject.toml": '[tool.skill-release.skills]\npaths = ["from-pyproject"]\n',
            ".skill-release.toml": '[skills]\npaths = ["from-standalone"]\n',
        })
        config = write_files(self.work / "elsewhere", {"gate.toml": (
            '[tool.skill-release.skills]\npaths = ["from-config"]\n')}) / "gate.toml"

        self._assert_read(self._gate("--config", config), "from-config")

    def test_config_naming_a_top_level_file_is_read_whole(self):
        config = write_files(self.work / "elsewhere", {"gate.toml": (
            '[skills]\npaths = ["from-config"]\n')}) / "gate.toml"

        self._assert_read(self._gate("--config", config), "from-config")

    def test_no_configuration_exits_2_naming_the_project_and_runs_no_phase(self):
        result = self._gate()

        self.assertEqual(result.returncode, 2, self._output(result))
        self.assertIn(f"no [tool.skill-release] config found in {self.project}",
                      self._plain(result.stdout), self._output(result))
        self.assertEqual([marker for marker in PHASE_MARKERS
                          if marker in result.stdout + result.stderr], [],
                         self._output(result))
        self.assertEqual(self._validator_calls(), [], self._output(result))

    def test_a_pyproject_without_the_gate_table_and_no_standalone_file_exits_2(self):
        write_files(self.project, {
            "pyproject.toml": '[project]\nname = "fixture"\nversion = "0.1.0"\n'})

        result = self._gate()

        self.assertEqual(result.returncode, 2, self._output(result))
        self.assertIn("no [tool.skill-release] config found in", self._plain(result.stdout),
                      self._output(result))
        self.assertEqual(self._validator_calls(), [], self._output(result))


class PhaseOneValidatorTest(_SkillReleaseGateCase, _VerdictReading):
    """§S8: phase 1 with an ``agentskills`` stand-in that passes and one that fails -- a pass
    prints the validator's own line, a failure its stdout and stderr, and the gate's exit code
    and verdict follow."""

    def setUp(self):
        super().setUp()
        write_files(self.project, {".skill-release.toml": (
            '[skills]\npaths = ["skills/alpha", "skills/bad-beta"]\n')})
        self._add_skills("skills/alpha", "skills/bad-beta")

    def _validator(self, *, fail_on: str, stdout: str):
        """Replace the stand-in: a skill directory whose name contains ``fail_on`` is refused
        (stdout ``missing description``, stderr ``frontmatter error``, exit 1); any other is
        accepted with ``stdout`` printed."""
        write_executable(self.bin_dir, "agentskills", (
            f"#!{sys.executable}\n"
            "import json, os, sys\n"
            f"with open({str(self.validator_log)!r}, 'a', encoding='utf-8') as fh:\n"
            "    fh.write(json.dumps(sys.argv[1:]) + '\\n')\n"
            f"if {fail_on!r} and {fail_on!r} in os.path.basename(sys.argv[2]):\n"
            "    print('missing description')\n"
            "    print('frontmatter error', file=sys.stderr)\n"
            "    sys.exit(1)\n"
            f"sys.stdout.write({stdout!r})\n"))

    def test_a_passing_validator_passes_each_skill_with_its_own_line(self):
        self._validator(fail_on="", stdout="Valid skill: checked\n")

        result = self._gate()

        self.assertEqual(result.returncode, 0, self._output(result))
        self.assertEqual(self._verdicts(result.stdout), [
            ("PASS", "skills/alpha: Valid skill: checked"),
            ("PASS", "skills/bad-beta: Valid skill: checked"),
        ], self._output(result))
        self.assertIn("RESULT: 2 passed, 0 failed", self._plain(result.stdout))
        self.assertIn(RESULT_PASSED, self._plain(result.stdout), self._output(result))

    def test_a_silent_passing_validator_is_reported_as_a_valid_skill(self):
        self._validator(fail_on="", stdout="")

        result = self._gate()

        self.assertEqual(result.returncode, 0, self._output(result))
        self.assertEqual(self._verdicts(result.stdout)[0], ("PASS", "skills/alpha: valid skill"),
                         self._output(result))

    def test_a_failing_validator_fails_the_gate_with_its_stdout_and_stderr(self):
        self._validator(fail_on="bad", stdout="Valid skill\n")

        result = self._gate()

        self.assertEqual(result.returncode, 1, self._output(result))
        self.assertEqual(self._verdicts(result.stdout), [
            ("PASS", "skills/alpha: Valid skill"),
            ("FAIL", "skills/bad-beta: agentskills validate failed"),
        ], self._output(result))
        self.assertEqual(self._details(result.stdout),
                         ["missing description", "frontmatter error"], self._output(result))
        self.assertIn("RESULT: 1 passed, 1 failed", self._plain(result.stdout))
        self.assertIn(RESULT_FAILED, self._plain(result.stdout), self._output(result))
        self.assertNotIn("Release gate PASSED", result.stdout, self._output(result))
        validated = [os.path.relpath(call[1], self.project) for call in self._validator_calls()]
        self.assertEqual(validated, ["skills/alpha", "skills/bad-beta"],
                         "a failure does not stop the next skill's validation")

# ------------------------------------------------------------------ in process ----


#: The wheel the stand-in build writes, and its members.
WHEEL_NAME = "fixture-0.1.0-py3-none-any.whl"
ENTRY_POINTS_TXT = "[console_scripts]\nfixture = fixture.cli:main\n"
WHEEL_MEMBERS = {
    "fixture/__init__.py": "",
    "fixture/cli.py": "def main():\n    return 0\n",
    "fixture/data/a.md": "a\n",
    "fixture/data/b.md": "b\n",
    "fixture-0.1.0.dist-info/entry_points.txt": ENTRY_POINTS_TXT,
    "fixture-0.1.0.dist-info/METADATA": "Name: fixture\nVersion: 0.1.0\n",
}

#: The stand-in interpreter ``Gate.make_venv``'s stand-in returns: it logs each call (argv and
#: cwd) and, per its behaviour, writes a wheel for ``-m build``, a console script beside itself
#: for ``-m pip install``, and prints a module directory for ``-c``. It never runs pip or build.
INTERPRETER_SOURCE = """\
import json, os, sys, zipfile
B = json.loads(BEHAVIOUR)
args = sys.argv[1:]
with open(B["log"], "a", encoding="utf-8") as fh:
    fh.write(json.dumps({"argv": args, "cwd": os.getcwd()}) + "\\n")
if args[:2] == ["-m", "build"]:
    outdir = args[args.index("--outdir") + 1]
    if B["make_outdir"]:
        os.makedirs(outdir, exist_ok=True)
        for name, members in B["dist"].items():
            with zipfile.ZipFile(os.path.join(outdir, name), "w") as z:
                for member, text in members.items():
                    z.writestr(member, text)
    sys.stderr.write(B["build_stderr"])
    sys.exit(0 if B["dist"] else 1)
if args[:2] == ["-m", "pip"]:
    if B["console"]:
        target = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), B["console"])
        with open(target, "w", encoding="utf-8") as fh:
            fh.write(B["console_body"])
        os.chmod(target, 0o755)
    sys.stderr.write(B["pip_stderr"])
    sys.exit(0 if B["console"] else 1)
if args[:1] == ["-c"]:
    print(B["import_stdout"])
    sys.exit(0)
sys.exit(97)
"""

#: The console stand-in phase 4 runs: it logs each call (argv, cwd, the fixture variables) and
#: acts on its first argument.
CONSOLE_SOURCE = """\
import json, os, sys
args = sys.argv[1:]
with open(LOG, "a", encoding="utf-8") as fh:
    fh.write(json.dumps({"argv": args, "cwd": os.getcwd(),
                         "env": {k: os.environ.get(k) for k in
                                 ("FIXTURE_HOME", "FIXTURE_DB", "FIXTURE_COUNT")}}) + "\\n")
verb, rest = (args[0], args[1:]) if args else ("", [])
if verb == "say":
    print(" ".join(rest))
elif verb == "warn":
    print(" ".join(rest), file=sys.stderr)
elif verb == "both":
    print(rest[0])
    print(rest[1], file=sys.stderr)
elif verb == "exit":
    print("exiting")
    sys.exit(int(rest[0]))
elif verb == "env":
    print(os.environ.get(rest[0], "<unset>"))
elif verb == "":
    print("bare")
"""

#: The recorder a teardown ``cmd`` calls, on ``PATH``: it logs its argv and the fixture DB
#: variable.
RECORDER_SOURCE = """\
import json, os, sys
with open(LOG, "a", encoding="utf-8") as fh:
    fh.write(json.dumps({"argv": sys.argv[1:], "db": os.environ.get("FIXTURE_DB")}) + "\\n")
"""


def _read_log(path) -> list:
    path = Path(path)
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


class _GateInProcessCase(unittest.TestCase, _VerdictReading):
    """The script loaded as a module by its path; ``Gate.make_venv`` replaced by a stand-in that
    records ``(name, install)`` and returns ``<gate tmp>/<name>`` with a stand-in interpreter in
    its ``bin``; ``PATH`` in the test process set to a directory of the case's stand-ins alone and
    the tools' own variables cleared."""

    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location(
            "skill_release_gate_under_test", TOOL_SCRIPTS_DIR / SKILL_RELEASE_GATE)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"fixture: cannot load {SKILL_RELEASE_GATE} by its path")
        cls.gate_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.gate_module)

    def setUp(self):
        self.work = Path(os.path.realpath(tempfile.mkdtemp(prefix="mdb-skill-gate-inproc-")))
        self.addCleanup(shutil.rmtree, self.work, True)
        use_private_tmpdir(self, self.work)
        self.project = self.work / "project"
        self.project.mkdir()
        self.gate_tmp = self.work / "gate-tmp"
        self.gate_tmp.mkdir()
        self.bin_dir = self.work / "bin"
        self.bin_dir.mkdir()
        env = mock.patch.dict(os.environ, {"PATH": str(self.bin_dir)})
        env.start()
        self.addCleanup(env.stop)
        for name in TOOL_OWN_ENV:
            os.environ.pop(name, None)
        self.interpreter_log = self.work / "interpreter.log"
        self.console_log = self.work / "console.log"
        self.validator_log = self.work / "agentskills.log"
        self.behaviour = {
            "log": str(self.interpreter_log),
            "make_outdir": True,
            "dist": {WHEEL_NAME: dict(WHEEL_MEMBERS)},
            "build_stderr": "",
            "console": "fixture",
            "console_body": self._console_body(),
            "pip_stderr": "",
            "import_stdout": str(self.gate_tmp / "runvenv" / "lib" / "python3.14"
                                 / "site-packages" / "fixture"),
        }
        self.venv_calls = []
        case = self

        def make_venv_stand_in(gate, name, install=()):
            case.venv_calls.append((name, list(install)))
            path = os.path.join(gate.tmp, name)
            bin_dir = os.path.join(path, "bin")
            os.makedirs(bin_dir, exist_ok=True)
            py = write_executable(bin_dir, "python", (
                f"#!{sys.executable}\n"
                f"BEHAVIOUR = {json.dumps(case.behaviour)!r}\n" + INTERPRETER_SOURCE))
            if name == "srefvenv":
                write_executable(bin_dir, "agentskills", case._validator_body("provisioned"))
            return path, str(py)

        patcher = mock.patch.object(self.gate_module.Gate, "make_venv", make_venv_stand_in)
        patcher.start()
        self.addCleanup(patcher.stop)

    # ---- stand-ins ----
    def _console_body(self) -> str:
        return f"#!{sys.executable}\nLOG = {str(self.console_log)!r}\n" + CONSOLE_SOURCE

    def _validator_body(self, label: str) -> str:
        return (f"#!{sys.executable}\n"
                "import json, sys\n"
                f"with open({str(self.validator_log)!r}, 'a', encoding='utf-8') as fh:\n"
                f"    fh.write(json.dumps([{label!r}] + sys.argv[1:]) + '\\n')\n"
                f"print('valid skill ({label})')\n")

    def _console(self) -> str:
        """A console stand-in written straight into the work area, for phase 4 run alone."""
        console_bin = self.work / "console-bin"
        console_bin.mkdir(exist_ok=True)
        return str(write_executable(console_bin, "fixture", self._console_body()))

    # ---- runs ----
    def _gate(self):
        return self.gate_module.Gate(str(self.project), str(self.gate_tmp))

    def _call(self, method, *args):
        """``(return value, stdout)`` of ``method(*args)`` with the gate's prints captured."""
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            value = method(*args)
        return value, out.getvalue()

    def _interpreter_calls(self) -> list:
        return _read_log(self.interpreter_log)

    def _console_calls(self) -> list:
        return _read_log(self.console_log)


class ProvisionValidatorTest(_GateInProcessCase):
    """§S8 phase 1 with ``agentskills`` absent: ``skills-ref`` is provisioned in a throwaway
    venv through ``make_venv`` and the validator in that venv's ``bin`` validates each skill."""

    def setUp(self):
        super().setUp()
        write_files(self.project, {"skills/alpha/SKILL.md": SKILL_MD})

    def test_an_absent_validator_is_provisioned_and_the_provisioned_one_validates(self):
        gate = self._gate()

        _, out = self._call(gate.phase_skills, {})

        self.assertEqual(self.venv_calls, [("srefvenv", ["skills-ref"])], out)
        self.assertIn("(agentskills not on PATH — provisioning skills-ref in a throwaway venv)",
                      self._plain(out))
        self.assertEqual(_read_log(self.validator_log),
                         [["provisioned", "validate", str(self.project / "skills" / "alpha")]])
        self.assertEqual(self._verdicts(out), [("PASS", "skills/alpha: valid skill (provisioned)")])
        self.assertEqual((gate.passed, gate.failed), (1, 0))

    def test_a_validator_on_path_is_used_and_nothing_is_provisioned(self):
        write_executable(self.bin_dir, "agentskills", self._validator_body("on-path"))
        gate = self._gate()

        _, out = self._call(gate.phase_skills, {})

        self.assertEqual(self.venv_calls, [], out)
        self.assertNotIn("provisioning", out)
        self.assertEqual(_read_log(self.validator_log),
                         [["on-path", "validate", str(self.project / "skills" / "alpha")]])

    def test_a_project_with_no_skill_provisions_nothing_and_prints_no_phase(self):
        shutil.rmtree(self.project / "skills")
        gate = self._gate()

        _, out = self._call(gate.phase_skills, {})

        self.assertEqual((self.venv_calls, out, gate.passed, gate.failed), ([], "", 0, 0))


class EngineBuildTest(_GateInProcessCase):
    """§S8 phase 2: the wheel built or not, the entry point, a forbidden entry point, glob
    counts and globs -- each checked against the members of the wheel the stand-in build wrote."""

    def _engine(self, **extra):
        return {"engine": {"build": True, "console": "fixture", **extra}}

    @staticmethod
    def _phase_two(verdicts) -> list:
        """The verdicts phase 2 printed (phase 3's name the console)."""
        return [v for v in verdicts if not v[1].startswith("console ")]

    def test_no_engine_or_no_build_skips_phases_two_and_three(self):
        for cfg in ({}, {"engine": {"console": "fixture"}}, {"engine": {"build": False}}):
            with self.subTest(cfg=cfg):
                gate = self._gate()
                console, out = self._call(gate.phase_engine, cfg)
                self.assertEqual((console, out, self.venv_calls), (None, "", []))

    def test_the_wheel_is_built_in_a_build_venv_into_the_gates_dist(self):
        gate = self._gate()

        console, out = self._call(gate.phase_engine, self._engine())

        self.assertEqual(self.venv_calls, [("buildvenv", ["build"]), ("runvenv", [])], out)
        build = self._interpreter_calls()[0]
        self.assertEqual(build["argv"], ["-m", "build", "--wheel", "--outdir",
                                         str(self.gate_tmp / "dist"), str(self.project)])
        self.assertEqual(self._verdicts(out)[0], ("PASS", f"built {WHEEL_NAME}"), out)
        self.assertEqual(self._headers(out)[0], "2. engine build + packaging invariants")
        self.assertEqual(console, str(self.gate_tmp / "runvenv" / "bin" / "fixture"))

    def test_no_dist_directory_fails_the_build_with_its_output_and_stops(self):
        self.behaviour.update(make_outdir=False, dist={}, build_stderr="error: backend failed\n")
        gate = self._gate()

        console, out = self._call(gate.phase_engine, self._engine())

        self.assertIsNone(console)
        self.assertEqual(self._verdicts(out), [("FAIL", "wheel build failed")], out)
        self.assertEqual(self._details(out), ["error: backend failed"], out)
        self.assertEqual(self.venv_calls, [("buildvenv", ["build"])],
                         "no install after a failed build")
        self.assertNotIn("3. clean-install", out)
        self.assertEqual((gate.passed, gate.failed), (0, 1))

    def test_a_dist_without_a_wheel_fails_the_build(self):
        self.behaviour.update(dist={"fixture-0.1.0.tar.gz": {"fixture/__init__.py": ""}},
                              build_stderr="wheel step skipped\n")
        gate = self._gate()

        console, out = self._call(gate.phase_engine, self._engine())

        self.assertIsNone(console)
        self.assertEqual(self._verdicts(out), [("FAIL", "wheel build failed")], out)
        self.assertEqual(self._details(out), ["wheel step skipped"], out)

    def test_a_declared_entry_point_present_passes(self):
        gate = self._gate()

        _, out = self._call(gate.phase_engine,
                            self._engine(entry_point="fixture = fixture.cli:main"))

        self.assertEqual(self._phase_two(self._verdicts(out)), [
            ("PASS", f"built {WHEEL_NAME}"),
            ("PASS", "entry point 'fixture = fixture.cli:main'"),
        ], out)
        self.assertEqual(gate.failed, 0, out)

    def test_a_declared_entry_point_absent_fails_showing_the_entry_points(self):
        gate = self._gate()

        _, out = self._call(gate.phase_engine,
                            self._engine(entry_point="fixture = fixture.app:run"))

        self.assertIn(("FAIL", "entry point 'fixture = fixture.app:run'"), self._verdicts(out), out)
        self.assertEqual(self._details(out), ["[console_scripts]", "fixture = fixture.cli:main"])
        self.assertEqual(gate.failed, 1, out)

    def test_a_forbidden_entry_point_present_fails_and_a_prefix_is_not_a_match(self):
        gate = self._gate()

        _, out = self._call(gate.phase_engine,
                            self._engine(forbid_entry_points=["fixture", "fix", "legacy"]))

        self.assertEqual(self._phase_two(self._verdicts(out)), [
            ("PASS", f"built {WHEEL_NAME}"),
            ("FAIL", "forbidden entry point 'fixture' present"),
            ("PASS", "no forbidden entry point 'fix'"),
            ("PASS", "no forbidden entry point 'legacy'"),
        ], out)

    def test_glob_counts_match_exactly_and_a_star_stays_inside_one_directory(self):
        gate = self._gate()

        _, out = self._call(gate.phase_engine, self._engine(wheel_glob_counts={
            "fixture/data/*.md": 2, "fixture/*.md": 0, "fixture/data/*.json": 1}))

        self.assertEqual(self._phase_two(self._verdicts(out))[1:], [
            ("PASS", "wheel bundles 2x 'fixture/data/*.md' (found 2)"),
            ("PASS", "wheel bundles 0x 'fixture/*.md' (found 0)"),
            ("FAIL", "wheel bundles 1x 'fixture/data/*.json' (found 0)"),
        ], out)

    def test_a_glob_count_short_of_the_wanted_count_fails(self):
        gate = self._gate()

        _, out = self._call(gate.phase_engine, self._engine(wheel_glob_counts={
            "fixture/data/*.md": 3}))

        self.assertIn(("FAIL", "wheel bundles 3x 'fixture/data/*.md' (found 2)"),
                      self._verdicts(out), out)

    def test_globs_pass_when_present_and_fail_when_absent(self):
        gate = self._gate()

        _, out = self._call(gate.phase_engine, self._engine(wheel_globs=[
            "fixture/cli.py", "fixture/data/*.md", "fixture/*.json"]))

        self.assertEqual(self._phase_two(self._verdicts(out))[1:], [
            ("PASS", "wheel bundles 'fixture/cli.py' (found 1)"),
            ("PASS", "wheel bundles 'fixture/data/*.md' (found 2)"),
            ("FAIL", "wheel bundles 'fixture/*.json' (found 0)"),
        ], out)

    def test_glob_counts_take_fnmatch_question_mark_and_bracket_patterns(self):
        gate = self._gate()

        _, out = self._call(gate.phase_engine, self._engine(wheel_glob_counts={
            "fixture/data/?.md": 2, "fixture/data/[a].md": 1, "fixture/data/[!a].md": 1,
            "fixture/c?i.py": 1, "fixture/data/[c-z].md": 1}))

        self.assertEqual(self._phase_two(self._verdicts(out))[1:], [
            ("PASS", "wheel bundles 2x 'fixture/data/?.md' (found 2)"),
            ("PASS", "wheel bundles 1x 'fixture/data/[a].md' (found 1)"),
            ("PASS", "wheel bundles 1x 'fixture/data/[!a].md' (found 1)"),
            ("PASS", "wheel bundles 1x 'fixture/c?i.py' (found 1)"),
            ("FAIL", "wheel bundles 1x 'fixture/data/[c-z].md' (found 0)"),
        ], out)
        self.assertEqual(gate.failed, 1, out)

    def test_globs_take_fnmatch_question_mark_and_bracket_patterns(self):
        gate = self._gate()

        _, out = self._call(gate.phase_engine, self._engine(wheel_globs=[
            "fixture/c?i.py", "fixture/data/[ab].md", "fixture-0.1.0.dist-info/[eM]*",
            "fixture/data/[!ab].md"]))

        self.assertEqual(self._phase_two(self._verdicts(out))[1:], [
            ("PASS", "wheel bundles 'fixture/c?i.py' (found 1)"),
            ("PASS", "wheel bundles 'fixture/data/[ab].md' (found 2)"),
            ("PASS", "wheel bundles 'fixture-0.1.0.dist-info/[eM]*' (found 2)"),
            ("FAIL", "wheel bundles 'fixture/data/[!ab].md' (found 0)"),
        ], out)


class CleanInstallTest(_GateInProcessCase):
    """§S8 phase 3: the wheel installed into a fresh venv, the console found or not, and the
    import check run from the gate's scratch directory."""

    def _engine(self, **extra):
        return {"engine": {"build": True, "console": "fixture", **extra}}

    def _phase_three(self, out) -> list:
        return [v for v in self._verdicts(out) if not v[1].startswith("built ")]

    def test_the_installed_console_passes_and_is_returned(self):
        gate = self._gate()

        console, out = self._call(gate.phase_engine, self._engine())

        self.assertEqual(console, str(self.gate_tmp / "runvenv" / "bin" / "fixture"))
        self.assertEqual(self._phase_three(out), [("PASS", "console 'fixture' installed")], out)
        self.assertEqual(self._headers(out)[1],
                         "3. clean-install smoke (fresh venv — simulates pip install)")
        calls = self._interpreter_calls()
        self.assertEqual(calls[1]["argv"], ["-m", "pip", "install", "-q",
                                            str(self.gate_tmp / "dist" / WHEEL_NAME)])
        self.assertEqual(len(calls), 2, "no import check unless configured")

    def test_a_console_not_installed_fails_with_pips_output_and_returns_none(self):
        self.behaviour.update(console=None, pip_stderr="ERROR: could not install\n")
        gate = self._gate()

        console, out = self._call(gate.phase_engine, self._engine(import_check="fixture"))

        self.assertIsNone(console)
        self.assertEqual(self._phase_three(out), [("FAIL", "console 'fixture' not installed")],
                         out)
        self.assertEqual(self._details(out), ["ERROR: could not install"], out)
        self.assertEqual([c["argv"][:2] for c in self._interpreter_calls()],
                         [["-m", "build"], ["-m", "pip"]],
                         "no import check once the console is missing")

    def test_an_engine_naming_no_console_fails_phase_three_naming_the_missing_key(self):
        gate = self._gate()

        console, out = self._call(gate.phase_engine, {"engine": {"build": True}})

        self.assertIsNone(console)
        fails = [v for v in self._verdicts(out) if v[0] == "FAIL"]
        self.assertEqual(len(fails), 1, out)
        self.assertEqual(gate.failed, 1, out)
        # The message names the `console` key the [engine] table lacks -- never `'None'`.
        self.assertRegex(fails[0][1], r"\bconsole\b", out)
        self.assertRegex(fails[0][1], r"\b(?:no|missing|names no|not set|unset|lacks)\b", out)
        self.assertNotIn("None", self._plain(out), out)

    def test_an_import_from_site_packages_passes_run_from_the_gates_scratch_directory(self):
        gate = self._gate()

        _, out = self._call(gate.phase_engine, self._engine(import_check="fixture"))

        self.assertEqual(self._phase_three(out), [
            ("PASS", "console 'fixture' installed"),
            ("PASS", "'fixture' imports from site-packages (not the repo)"),
        ], out)
        check = self._interpreter_calls()[2]
        self.assertEqual(check["argv"][0], "-c")
        self.assertIn("import fixture,os", check["argv"][1])
        self.assertEqual(check["cwd"], str(self.gate_tmp), "the import runs from a neutral cwd")

    def test_an_import_resolving_to_the_repository_fails_showing_where_it_resolved(self):
        self.behaviour["import_stdout"] = str(self.project / "fixture")
        gate = self._gate()

        _, out = self._call(gate.phase_engine, self._engine(import_check="fixture"))

        self.assertEqual(self._phase_three(out)[1],
                         ("FAIL", "'fixture' imports from site-packages (not the repo)"), out)
        self.assertEqual(self._details(out), [str(self.project / "fixture")], out)
        self.assertEqual(gate.failed, 1, out)


class LifecycleCheckTest(_GateInProcessCase):
    """§S8 phase 4: every check field -- ``expect``, ``expect_re``, ``reject``, ``json_type``,
    ``allow_nonzero``, ``combine_stderr`` -- against the console stand-in, run from the gate's
    scratch directory under the configured ``env``."""

    def _checks(self, *checks, **cfg):
        gate = self._gate()
        _, out = self._call(gate.phase_checks, {"check": list(checks), **cfg}, self._console())
        return gate, out

    def test_no_checks_or_no_console_skips_phase_four(self):
        gate = self._gate()
        _, out = self._call(gate.phase_checks, {"check": []}, self._console())
        self.assertEqual((out, self._console_calls()), ("", []))
        _, out = self._call(gate.phase_checks, {"check": [{"argv": ["say", "x"]}]}, None)
        self.assertEqual((out, self._console_calls(), gate.passed, gate.failed), ("", [], 0, 0))

    def test_expect_passes_on_a_substring_and_fails_naming_the_missing_one(self):
        gate, out = self._checks(
            {"name": "greets", "argv": ["say", "hello", "world"], "expect": ["hello world"]},
            {"name": "greets twice", "argv": ["say", "hello"], "expect": ["hello", "goodbye"]})

        self.assertEqual(self._verdicts(out), [("PASS", "greets"), ("FAIL", "greets twice")], out)
        self.assertEqual(self._details(out), ["missing 'goodbye'", "hello"], out)
        self.assertEqual(self._headers(out),
                         ["4. lifecycle + AXI conformance (declarative checks, throwaway env)"])
        self.assertEqual((gate.passed, gate.failed), (1, 1))

    def test_expect_re_passes_on_a_match_and_fails_naming_the_pattern(self):
        _, out = self._checks(
            {"name": "versioned", "argv": ["say", "v1.2.3"], "expect_re": [r"^v\d+\.\d+\.\d+$"]},
            {"name": "unversioned", "argv": ["say", "v1"], "expect_re": [r"v\d+\.\d+"]})

        self.assertEqual(self._verdicts(out), [("PASS", "versioned"), ("FAIL", "unversioned")])
        self.assertEqual(self._details(out)[0], r"no regex match /v\d+\.\d+/", out)

    def test_reject_fails_on_a_present_substring_and_passes_on_an_absent_one(self):
        _, out = self._checks(
            {"name": "clean", "argv": ["say", "ok"], "reject": ["Traceback"]},
            {"name": "crashed", "argv": ["say", "Traceback here"], "reject": ["Traceback"]})

        self.assertEqual(self._verdicts(out), [("PASS", "clean"), ("FAIL", "crashed")], out)
        self.assertEqual(self._details(out)[0], "unexpected 'Traceback'", out)

    def test_json_type_accepts_list_array_and_object_shapes(self):
        _, out = self._checks(
            {"name": "list", "argv": ["say", "[1, 2]"], "json_type": "list"},
            {"name": "array", "argv": ["say", "[]"], "json_type": "array"},
            {"name": "object", "argv": ["say", '{"a": 1}'], "json_type": "object"})

        self.assertEqual(self._verdicts(out),
                         [("PASS", "list"), ("PASS", "array"), ("PASS", "object")], out)

    def test_json_type_fails_on_the_wrong_shape_and_on_unparseable_output(self):
        _, out = self._checks(
            {"name": "wrong shape", "argv": ["say", '{"a": 1}'], "json_type": "list"},
            {"name": "not json", "argv": ["say", "plain text"], "json_type": "dict"})

        self.assertEqual(self._verdicts(out), [("FAIL", "wrong shape"), ("FAIL", "not json")])
        details = self._details(out)
        self.assertEqual(details[0], "json is dict, expected list", out)
        self.assertTrue(details[2].startswith("json parse error: "), out)

    def test_json_type_parses_stdout_alone_even_when_stderr_is_combined(self):
        _, out = self._checks({"name": "json with noise", "argv": ["both", "[1]", "noise"],
                               "json_type": "list", "combine_stderr": True,
                               "expect": ["noise"]})

        self.assertEqual(self._verdicts(out), [("PASS", "json with noise")], out)

    def test_a_nonzero_exit_fails_unless_allowed(self):
        gate, out = self._checks(
            {"name": "exits 3", "argv": ["exit", "3"]},
            {"name": "allowed 3", "argv": ["exit", "3"], "allow_nonzero": True,
             "expect": ["exiting"]})

        self.assertEqual(self._verdicts(out), [("FAIL", "exits 3"), ("PASS", "allowed 3")], out)
        self.assertEqual(self._details(out)[0], "exit 3", out)
        self.assertEqual((gate.passed, gate.failed), (1, 1))

    def test_stderr_is_matched_only_when_combined(self):
        _, out = self._checks(
            {"name": "stdout only", "argv": ["warn", "on-stderr"], "expect": ["on-stderr"]},
            {"name": "combined", "argv": ["warn", "on-stderr"], "expect": ["on-stderr"],
             "combine_stderr": True},
            {"name": "combined reject", "argv": ["warn", "on-stderr"], "reject": ["on-stderr"],
             "combine_stderr": True})

        self.assertEqual(self._verdicts(out), [("FAIL", "stdout only"), ("PASS", "combined"),
                                               ("FAIL", "combined reject")], out)

    def test_failures_are_joined_and_followed_by_the_output(self):
        gate, out = self._checks({"name": "all wrong", "argv": ["exit", "4"],
                                  "expect": ["absent"], "reject": ["exiting"]})

        self.assertEqual(self._details(out), ["exit 4; missing 'absent'; unexpected 'exiting'",
                                              "exiting"], out)
        self.assertEqual((gate.passed, gate.failed), (0, 1))

    def test_cmd_is_split_like_a_shell_and_an_unnamed_check_is_named_by_its_argv(self):
        _, out = self._checks({"cmd": "say 'hello world'", "expect": ["hello world"]},
                              {"argv": [], "expect": ["bare"]})

        self.assertEqual(self._verdicts(out), [("PASS", "say hello world"), ("PASS", "<bare>")])
        self.assertEqual([c["argv"] for c in self._console_calls()], [["say", "hello world"], []])

    def test_checks_run_from_the_gates_scratch_directory_under_the_configured_env(self):
        _, out = self._checks({"name": "env", "argv": ["env", "FIXTURE_HOME"]},
                              env={"FIXTURE_HOME": "$TMP/data", "FIXTURE_DB": "$THROWAWAY_DB",
                                   "FIXTURE_COUNT": 5})

        call = self._console_calls()[0]
        self.assertEqual(call["cwd"], str(self.gate_tmp))
        self.assertEqual(call["env"], {"FIXTURE_HOME": f"{self.gate_tmp}/data",
                                       "FIXTURE_DB": f"skillrelcheck_{os.getpid()}",
                                       "FIXTURE_COUNT": "5"})
        self.assertTrue((self.gate_tmp / "data").is_dir(), "phase 4 makes $TMP/data")
        self.assertEqual(self._verdicts(out), [("PASS", "env")], out)


class SubstitutionTest(_GateInProcessCase):
    """§S8: ``$TMP``, ``$THROWAWAY_DB``, ``$SOON`` and ``$TODAY`` in a check's argv,
    ``expect`` and ``reject``; ``$SOON`` ten days out unless ``SKILLGATE_SOON`` sets it."""

    ARGV = ["say", "$TMP", "$THROWAWAY_DB", "$SOON", "$TODAY"]

    def _run_substituted(self):
        before = datetime.date.today()
        gate = self._gate()
        _, out = self._call(gate.phase_checks, {"check": [{"name": "subst", "argv": self.ARGV,
                                                          "expect": ["$THROWAWAY_DB"],
                                                          "reject": ["$TMP/elsewhere"]}]},
                            self._console())
        after = datetime.date.today()
        return out, self._console_calls()[0]["argv"], (before, after)

    def test_soon_is_ten_days_out_without_skillgate_soon(self):
        out, argv, days = self._run_substituted()

        self.assertEqual(argv[:3], ["say", str(self.gate_tmp), f"skillrelcheck_{os.getpid()}"])
        self.assertIn((argv[3], argv[4]), {((d + datetime.timedelta(days=10)).isoformat(),
                                            d.isoformat()) for d in days})
        self.assertEqual(self._verdicts(out), [("PASS", "subst")], out)

    def test_skillgate_soon_sets_soon(self):
        os.environ["SKILLGATE_SOON"] = "2001-02-03"

        out, argv, days = self._run_substituted()

        self.assertEqual(argv[3], "2001-02-03", out)
        self.assertIn(argv[4], {d.isoformat() for d in days})
        self.assertEqual(self._gate().subst("due $SOON"), "due 2001-02-03")

    def test_reject_is_substituted_before_matching(self):
        gate = self._gate()
        _, out = self._call(gate.phase_checks, {"check": [
            {"name": "names the db", "argv": ["say", "db=$THROWAWAY_DB"],
             "reject": ["$THROWAWAY_DB"]}]}, self._console())

        self.assertEqual(self._verdicts(out), [("FAIL", "names the db")], out)
        self.assertEqual(self._details(out)[0], "unexpected '$THROWAWAY_DB'", out)


class TeardownTest(_GateInProcessCase):
    """AC9 / §S8: ``[teardown] cmd`` runs through the shell after the checks, with the
    substitutions applied and the configured ``env``."""

    def setUp(self):
        super().setUp()
        self.recorder_log = self.work / "recorder.log"
        write_executable(self.bin_dir, "record", (
            f"#!{sys.executable}\nLOG = {str(self.recorder_log)!r}\n" + RECORDER_SOURCE))
        os.environ["SKILLGATE_SOON"] = "2030-01-02"

    def _phase_four(self, checks, teardown):
        gate = self._gate()
        cfg = {"check": checks, "env": {"FIXTURE_DB": "$THROWAWAY_DB"}, "teardown": teardown}
        _, out = self._call(gate.phase_checks, cfg, self._console())
        return gate, out

    def test_teardown_cmd_runs_with_the_substitutions_applied(self):
        today = {datetime.date.today().isoformat()}
        _, out = self._phase_four([{"argv": ["say", "x"]}],
                                  {"cmd": 'record "$TMP" "$THROWAWAY_DB" "$SOON" "$TODAY"'})
        today.add(datetime.date.today().isoformat())

        calls = _read_log(self.recorder_log)
        self.assertEqual(len(calls), 1, out)
        argv = calls[0]["argv"]
        self.assertEqual(argv[:3], [str(self.gate_tmp), f"skillrelcheck_{os.getpid()}",
                                    "2030-01-02"])
        self.assertIn(argv[3], today)
        self.assertEqual(calls[0]["db"], f"skillrelcheck_{os.getpid()}",
                         "the teardown runs under the configured env")

    def test_teardown_runs_after_a_failing_check(self):
        gate, out = self._phase_four([{"name": "fails", "argv": ["exit", "1"]}],
                                     {"cmd": "record after"})

        self.assertEqual(gate.failed, 1, out)
        self.assertEqual([c["argv"] for c in _read_log(self.recorder_log)], [["after"]])

    def test_no_cmd_and_no_checks_run_no_teardown(self):
        self._phase_four([{"argv": ["say", "x"]}], {})
        self._phase_four([], {"cmd": "record skipped"})

        self.assertEqual(_read_log(self.recorder_log), [])


class GateRunVerdictTest(_GateInProcessCase):
    """§S8: ``Gate.run`` runs the phases in order and returns 0 with the PASSED verdict when
    nothing failed, 1 with the FAILED verdict otherwise."""

    def setUp(self):
        super().setUp()
        write_files(self.project, {"skills/alpha/SKILL.md": SKILL_MD})
        write_executable(self.bin_dir, "agentskills", self._validator_body("on-path"))

    @staticmethod
    def _cfg(expect):
        return {"engine": {"build": True, "console": "fixture", "import_check": "fixture"},
                "check": [{"name": "greets", "argv": ["say", "hello"], "expect": [expect]}]}

    def test_a_clean_run_through_every_phase_returns_0_with_the_passed_verdict(self):
        gate = self._gate()

        code, out = self._call(gate.run, self._cfg("hello"))

        self.assertEqual(code, 0, out)
        self.assertEqual([h.split(" ")[0] for h in self._headers(out)],
                         ["1.", "2.", "3.", "4.", "RESULT:"], out)
        self.assertEqual(self._headers(out)[-1], "RESULT: 5 passed, 0 failed", out)
        self.assertEqual(self._plain(out).rstrip().splitlines()[-1], RESULT_PASSED)
        self.assertNotIn("FAILED", out)

    def test_one_failure_returns_1_with_the_failed_verdict(self):
        gate = self._gate()

        code, out = self._call(gate.run, self._cfg("goodbye"))

        self.assertEqual(code, 1, out)
        self.assertEqual(self._headers(out)[-1], "RESULT: 4 passed, 1 failed", out)
        self.assertEqual(self._plain(out).rstrip().splitlines()[-1], RESULT_FAILED)
        self.assertNotIn("PASSED", out)

    def test_a_failed_build_skips_phase_four_and_returns_1(self):
        self.behaviour.update(dist={}, build_stderr="boom\n")
        gate = self._gate()

        code, out = self._call(gate.run, self._cfg("hello"))

        self.assertEqual(code, 1, out)
        self.assertEqual(self._console_calls(), [], "no check runs without a console")
        self.assertNotIn("4. lifecycle", out)
        self.assertEqual(self._headers(out)[-1], "RESULT: 1 passed, 1 failed", out)

    def test_a_run_that_checked_nothing_fails_saying_nothing_was_checked(self):
        shutil.rmtree(self.project / "skills")
        configurations = (
            {},
            {"engine": {"build": False, "console": "fixture"}},
            # Checks with no engine have no console to run against: phase 4 is skipped too.
            {"check": [{"name": "greets", "argv": ["say", "hello"], "expect": ["hello"]}]},
        )
        for cfg in configurations:
            with self.subTest(cfg=cfg):
                gate = self._gate()
                err = io.StringIO()

                with contextlib.redirect_stderr(err):
                    code, out = self._call(gate.run, cfg)

                out += err.getvalue()
                self.assertEqual((gate.passed, gate.failed), (0, 0), out)
                self.assertNotEqual(code, 0, "a gate that checked nothing never passes\n" + out)
                self.assertRegex(self._plain(out), NOTHING_CHECKED, out)
                self.assertNotIn("PASSED", out)
                self.assertEqual((self.venv_calls, self._console_calls()), ([], []), out)


if __name__ == "__main__":
    unittest.main()
