"""``scripts/skill-release-gate.py`` names no project (CR-MDB-081 §S7 — AC8, AC9).

- ``SkillDiscoveryTest`` — AC8 / §S7: with no configured skill paths and an ``agentskills``
  stand-in on ``PATH``, phase 1 validates exactly the skills under ``skills/``,
  ``.agents/skills/`` and ``.pi/skills/`` -- each ``<name>/SKILL.md`` once -- and not one under
  ``.claude/skills/``, which is no longer read.
- ``MongoTeardownRemovedTest`` — AC9 / §S7: the script carries neither the Mongo-drop teardown
  step nor ``VIDUSHI_MONGO_URI``; a configuration carrying ``[teardown] drop_mongo_db``, with no
  engine or checks, is refused when the configuration loads -- the gate exits non-zero naming
  ``[teardown] cmd`` before any phase runs, wherever the configuration is found.

Every gate run is a subprocess of the test interpreter under ``tests/_helpers.py``'s
``run_tool`` (§S9): a fixture project in a temp directory, the tools' own variables
(``SKILLGATE_SOON`` among them) cleared, a private ``TMPDIR`` set in the test process, and on
``PATH`` a logging ``agentskills`` stand-in that records each call's argv -- so no run ever
provisions ``skills-ref``, and no test reaches a package index or runs a real ``pip``.

Stdlib only.
"""

import ast
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

from tests._helpers import (
    TOOL_SCRIPTS_DIR,
    run_tool,
    tool_bin_dir,
    use_private_tmpdir,
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

    def test_a_skill_under_claude_skills_alone_is_never_validated(self):
        self._add_skills(".claude/skills/delta")

        result = self._gate()

        self.assertEqual(self._validator_calls(), [],
                         ".claude/skills/ is no longer read\n" + self._output(result))
        self.assertNotIn("1. skill conformance", result.stdout, self._output(result))
        self.assertNotIn(".claude", result.stdout + result.stderr, self._output(result))
        self.assertEqual(result.returncode, 0, self._output(result))


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


if __name__ == "__main__":
    unittest.main()
