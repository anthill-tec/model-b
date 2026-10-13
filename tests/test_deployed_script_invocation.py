"""Deployed scripts are run directly, never through ``python3`` (CR-MDB-064 §S4).

A deployed script is one of Model B's hook or tool scripts under ``~/.agents/hooks/scripts/``
or ``~/.agents/scripts/``; its shebang names the recorded interpreter (§S3), so an invocation
that puts ``python3`` in front of it runs it on whatever ``python3`` comes first on ``PATH``
instead. Crucible's clients (``~/.crucible/clients/``) are not deployed scripts.

The gate scans every text file under ``skills-src/``, ``contracts/``, ``generator/templates/``,
``scripts/`` and ``hooks-src/``. The texts that said a deployed ``worktree-flow.py`` runs
"under a bare ``python3``" — ``contracts/crucible-envelope.md`` and the docstring of
``modelb_axi/toon.py`` and its generated copy ``scripts/toon.py`` — name the recorded
interpreter instead.

Stdlib only.
"""

import ast
import re
import unittest
from pathlib import Path

from tests._helpers import files_under, read_text

REPO_ROOT = Path(__file__).resolve().parent.parent

#: The roots §S4's grep gate covers.
GATED_ROOTS = ("skills-src", "contracts", "generator/templates", "scripts", "hooks-src")

#: An interpreter word followed by a deployed Model B script's path, in any home spelling.
THROUGH_PYTHON_RE = re.compile(
    r"\bpython(?:3(?:\.\d+)?)?\s+[\"']?(?:~|\$HOME|\$\{HOME\})"
    r"/\.agents/(?:hooks/scripts|scripts)/"
)

#: "a bare python3", in any of the code spans the docs use.
BARE_PYTHON3_RE = re.compile(r"bare\s+`{1,2}python3`{1,2}")
#: The recorded interpreter, named in either word order and across a line wrap.
RECORDED_INTERPRETER_RE = re.compile(
    r"(?i)recorded\s+interpreter|interpreter\s+(?:that\s+)?(?:the\s+installer\s+)?recorded")

CONTRACT = REPO_ROOT / "contracts" / "crucible-envelope.md"
TOON_SOURCES = (REPO_ROOT / "modelb_axi" / "toon.py", REPO_ROOT / "scripts" / "toon.py")
RELEASE_GATE = REPO_ROOT / "scripts" / "skill-release-gate.py"


def through_python_sites(text: str) -> list[tuple[int, str]]:
    """``(line number, line)`` for every line that runs a deployed script through python."""
    return [(n, line.strip()) for n, line in enumerate(text.splitlines(), 1)
            if THROUGH_PYTHON_RE.search(line)]


def _gated_files() -> list[Path]:
    """Every text file under the gated roots (``__pycache__`` excluded: compiled bytes)."""
    files = []
    for root in GATED_ROOTS:
        for path in files_under(REPO_ROOT / root):
            if "__pycache__" in path.parts:
                continue
            try:
                path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            files.append(path)
    return sorted(files)


class ThroughPythonDetectorProofTest(unittest.TestCase):
    """The detector bites on every spelling of the defect and spares the direct form."""

    def test_bites_on_python3_before_a_deployed_tool_or_hook_in_any_home_spelling(self):
        for line in (
            "python3 ~/.agents/scripts/rust-code-health.py snapshot --phase post",
            'python3 "$HOME/.agents/scripts/worktree-flow.py" status',
            "python3 ${HOME}/.agents/hooks/scripts/ambient-board-status",
            "python ~/.agents/scripts/skill-release-gate.py",
            "  python3.12 ~/.agents/scripts/rust-dead-scan.py inventory",
        ):
            with self.subTest(line=line):
                self.assertEqual(len(through_python_sites(line)), 1)

    def test_spares_a_direct_invocation_and_a_crucible_client(self):
        for line in (
            "~/.agents/scripts/rust-code-health.py snapshot --phase post",
            '"$HOME/.agents/scripts/worktree-flow.py" status',
            "python3 ~/.crucible/clients/rust-crucible.py test --crate c",
            "python3 generator/build.py --check",
        ):
            with self.subTest(line=line):
                self.assertEqual(through_python_sites(line), [])


class DeployedScriptsRunDirectlyTest(unittest.TestCase):
    """§S4: no skill, contract, template, tool script or hook script runs a deployed script
    through ``python3``."""

    def test_gated_roots_are_scanned(self):
        scanned = {str(p.relative_to(REPO_ROOT)).split("/")[0] for p in _gated_files()}
        self.assertEqual(scanned, {"skills-src", "contracts", "generator", "scripts",
                                   "hooks-src"})
        self.assertIn(REPO_ROOT / "skills-src" / "code-health" / "SKILL.md", _gated_files())

    def test_no_gated_file_runs_a_deployed_script_through_python(self):
        hits = [f"{path.relative_to(REPO_ROOT)}:{n}: {line}"
                for path in _gated_files()
                for n, line in through_python_sites(read_text(path))]
        self.assertEqual(hits, [], "§S4: a deployed script is run directly")

    def test_skill_release_gate_usage_runs_the_deployed_script_directly(self):
        doc = ast.get_docstring(ast.parse(read_text(RELEASE_GATE))) or ""
        usage = [ln.strip() for ln in doc.splitlines()
                 if "~/.agents/scripts/skill-release-gate.py" in ln]
        self.assertEqual(usage, ["~/.agents/scripts/skill-release-gate.py [--project-dir .]"],
                         "§S4: the usage line runs the deployed script directly")


class RecordedInterpreterNamedTest(unittest.TestCase):
    """§S4: the texts that said a deployed ``worktree-flow.py`` runs under a bare ``python3``
    state that it runs on the recorded interpreter."""

    def assert_names_the_recorded_interpreter(self, text: str, where: str) -> None:
        self.assertEqual(BARE_PYTHON3_RE.findall(text), [],
                         f"§S4: {where} no longer says a deployed script runs under a bare python3")
        self.assertRegex(text, RECORDED_INTERPRETER_RE,
                         f"§S4: {where} names the recorded interpreter")

    def test_crucible_envelope_contract_names_the_recorded_interpreter(self):
        text = read_text(CONTRACT)
        paragraph = next((p for p in text.split("\n\n") if "worktree-flow.py" in p), "")
        self.assertIn("scripts/toon.py", paragraph, "fixture: the codec paragraph")
        self.assert_names_the_recorded_interpreter(paragraph, "contracts/crucible-envelope.md")

    def test_toon_docstrings_name_the_recorded_interpreter(self):
        for source in TOON_SOURCES:
            with self.subTest(source=str(source.relative_to(REPO_ROOT))):
                doc = ast.get_docstring(ast.parse(read_text(source))) or ""
                self.assertIn("worktree-flow.py", doc, "fixture: the docstring names the tool")
                self.assert_names_the_recorded_interpreter(
                    doc, f"{source.relative_to(REPO_ROOT)}'s docstring")

    def test_detectors_bite_on_the_old_wording_and_spare_the_new(self):
        old = "a deployed ``worktree-flow.py`` runs under a bare ``python3`` that cannot"
        new = "a deployed ``worktree-flow.py`` runs on the recorded interpreter, which cannot"
        self.assertEqual(len(BARE_PYTHON3_RE.findall(old)), 1)
        self.assertIsNone(RECORDED_INTERPRETER_RE.search(old))
        self.assertEqual(BARE_PYTHON3_RE.findall(new), [])
        self.assertIsNotNone(RECORDED_INTERPRETER_RE.search(new))
        self.assertIsNotNone(RECORDED_INTERPRETER_RE.search("on the interpreter the\ninstaller recorded"))


if __name__ == "__main__":
    unittest.main()
