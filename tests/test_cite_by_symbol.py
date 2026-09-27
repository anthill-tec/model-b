"""Cite code by symbol, never by path and line — CR-MDB-044 §S4.

Contract: ``docs/changes/CR-MDB-044-agent-definitions-and-briefs.md`` §S4. The surfaces under test:

- **Rules.** ``skills-src/cr-authoring/SKILL.md`` states that code is cited by symbol and file (the
  spec's own example: the symbol in backticks, then its file in parentheses), never by
  ``path:line`` (``CR_AUTHORING_RULE``). Each role template
  ``generator/templates/{red,green,verify,fix}.md.tmpl`` — and so every rendered agent — carries the
  same rule for comments, docstrings and reports (``TEMPLATE_RULE``), and no longer instructs a
  ``file:line`` / ``path:line`` citation outside a clause that negates it
  (``line_citation_instructions``).
- **Guard.** No file under the guarded surfaces (``GUARDED_DIRS`` plus the root ``AGENTS.md``;
  ``node_modules`` and ``__pycache__`` pruned, undecodable files skipped) carries a path-and-line
  citation: a file name with an extension, a colon, then digits (``PATH_LINE``). Out of the guard:
  ``docs/``, ``archive/`` and ``audits/`` (§S4 "Out of the guard", non-goals).

A rule is carried when ONE block — a list item with its wrapped lines, or a paragraph — matches
every pattern of the rule (``missing_rules``, case-insensitive, ``**`` and backticks dropped).

The guard's matcher and walker are pure functions proved on synthetic text and on a synthetic tree
built in a temp dir at run time (``CiteBySymbolCheckersOnSyntheticTextTest``,
``CitationGuardWalkerOnSyntheticTreeTest``). Every citation-shaped fixture string is assembled at run
time by ``_cite``, so this module never carries one in its own source and the guard never trips on
itself (``test_this_module_carries_no_path_line_citation_of_its_own``). No test pins a live
violation: the tree test asserts the guarded surfaces are clean. Stdlib only.
"""

import os
import re
import shutil
import tempfile
import unittest
from pathlib import Path

from tests._helpers import REPO_ROOT, read_text
from tests.test_agent_definition_rules import _rendered_agents, _template
from tests.test_orchestration_acceptance_model import missing_rules

CR_AUTHORING_REL = "skills-src/cr-authoring/SKILL.md"
TEMPLATE_ROLES = ("red", "green", "verify", "fix")

#: §S4 Guard — the guarded directories, relative to the repo root, plus the root ``AGENTS.md``.
GUARDED_DIRS = (
    "skills-src",
    "generator/templates",
    "generator/stacks",
    "modelb_axi",
    "pi-package",
    "scripts",
    "tests",
)
GUARDED_FILES = ("AGENTS.md",)

#: §S4 Guard — directory names never walked (``pi-package`` guards its sources, not its deps).
PRUNED_DIRS = frozenset({"node_modules", "__pycache__"})

#: §S4 Guard — ``<file>.<ext>:<digits>``: an optional directory path, a file name, an extension
#: starting with a letter, a colon and digits. The token must start a path word (a URL's
#: ``host:port`` never does — it follows ``//``), and a dotted-quad address has no lettered
#: extension, so ``127.0.0.1`` with a port is not a citation.
PATH_LINE = re.compile(
    r"(?<![\w.\-/~])/?(?:[\w.\-~]+/)*[\w\-]+(?:\.[\w\-]+)*\.[A-Za-z]\w*:\d+")

#: §S4 Rules — ``cr-authoring``: code is cited by symbol and file, never by ``path:line``; the rule
#: shows the symbol-and-file form (a name, then a file with its extension in parentheses).
CR_AUTHORING_RULE = {
    "code is cited by symbol and file, never by path:line": (
        r"\bcit", r"\bsymbol", r"\bfile\b", r"\bnever\b", r"path:line"),
    "the rule shows the symbol-and-file form": (
        r"\bsymbol", r"path:line", r"\w+\s+\((?:[\w.\-]+/)*[\w\-]+\.[A-Za-z]\w*\)"),
}

#: §S4 Rules — the role templates carry the same rule for comments, docstrings and reports.
TEMPLATE_RULE = {
    "code is cited by symbol and file, never by path:line, in comments, docstrings and reports": (
        r"\bcit", r"\bsymbol", r"\bfile\b", r"\bnever\b", r"path:line", r"\bcomments?\b",
        r"\bdocstrings?\b", r"\breports?\b"),
}

_LINE_CITATION_WORD = re.compile(r"\b(?:file|path):line\b", re.IGNORECASE)
_NEGATION = re.compile(
    r"\b(?:never|not|no|nor|don't|forbidden|instead of|rather than)\b", re.IGNORECASE)
_CLAUSE_BREAK = re.compile(r"[.;]\s|\s\u2014\s")

# ------------------------------------------------------------------ checkers ----


def path_line_citations(text: str) -> list[str]:
    """``<line>: <citation>`` for every ``<file>.<ext>:<digits>`` citation in ``text``."""
    return [f"{n}: {match.group(0)}" for n, line in enumerate(text.splitlines(), 1)
            for match in PATH_LINE.finditer(line)]


def guarded_files(root: Path) -> list[Path]:
    """Every regular file on the guarded surfaces under ``root``, sorted; ``PRUNED_DIRS`` are never
    entered and an absent surface contributes nothing."""
    found = [root / rel for rel in GUARDED_FILES if (root / rel).is_file()]
    for rel in GUARDED_DIRS:
        top = root / rel
        if not top.is_dir():
            continue
        for current, dirs, files in os.walk(top):
            dirs[:] = sorted(d for d in dirs if d not in PRUNED_DIRS)
            found += [Path(current) / name for name in files]
    return sorted(found)


def citation_findings(root: Path) -> list[str]:
    """``<rel> line <n>: <citation>`` for every path-and-line citation on the guarded surfaces under
    ``root``. A file that is not UTF-8 text is skipped."""
    problems = []
    for path in guarded_files(root):
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, ValueError):
            continue
        rel = path.relative_to(root).as_posix()
        problems += [f"{rel} line {hit}" for hit in path_line_citations(text)]
    return problems


def line_citation_instructions(text: str) -> list[str]:
    """``<line>: <line text>`` for each line naming a ``file:line`` / ``path:line`` citation without
    a negation earlier in the same clause (the cite-by-symbol rule itself negates it)."""
    found = []
    for n, line in enumerate(text.splitlines(), 1):
        plain = line.replace("`", "").replace("**", "")
        for match in _LINE_CITATION_WORD.finditer(plain):
            clause = _CLAUSE_BREAK.split(plain[:match.start()])[-1]
            if not _NEGATION.search(clause):
                found.append(f"{n}: {line.strip()}")
                break
    return found


def rule_findings(text: str, rules: dict[str, tuple[str, ...]]) -> list[str]:
    """The name of each cite-by-symbol rule ``text`` does not carry in one block."""
    return missing_rules(text, rules)


# ------------------------------------------------------------------ fixtures ----


def _cite(path: str, line: int) -> str:
    """A path-and-line citation, assembled at run time so this module's source never carries one."""
    return f"{path}{chr(58)}{line}"


_GOOD_CR_AUTHORING = """# CR / PRD / DN Authoring
## Citing code
- **Cite code by symbol and file** (`handleCrPlan` (src/v2.ts)), never by `path:line`: a line
  number moves with every edit.
"""

_GOOD_TEMPLATE = """# RED
## Code quality
- Cite code by symbol and file (`build_plan` (modelb_axi/scaffold.py)) in comments, docstrings and
  reports — never by `path:line`.
"""


# ------------------------------------------------------------------ synthetic ----


class CiteBySymbolCheckersOnSyntheticTextTest(unittest.TestCase):
    """The matcher, the instruction checker and the rule checker, proved on synthetic text."""

    def test_matcher_flags_each_path_line_citation_shape(self):
        cases = {
            "see " + _cite("modelb_axi/cli.py", 42) + " for it": _cite("modelb_axi/cli.py", 42),
            "bare " + _cite("cli.py", 7): _cite("cli.py", 7),
            "`" + _cite("src/v2.ts", 12) + "`": _cite("src/v2.ts", 12),
            "(" + _cite("skills-src/b/SKILL.md", 3) + ")": _cite("skills-src/b/SKILL.md", 3),
            "a range " + _cite("modelb_axi/axi.py", 10) + "-12": _cite("modelb_axi/axi.py", 10),
            "home " + _cite("~/.crucible/clients/toon.py", 5): _cite("~/.crucible/clients/toon.py", 5),
            "abs " + _cite("/srv/app/run.sh", 9): _cite("/srv/app/run.sh", 9),
            "crucible:" + _cite("clients/toon.py", 1243): _cite("clients/toon.py", 1243),
            "carried by " + _cite("orchestration-common.md", 63) + ".": _cite(
                "orchestration-common.md", 63),
            "dotted " + _cite("tests/test_a.b.py", 1): _cite("tests/test_a.b.py", 1),
        }
        for text, citation in cases.items():
            with self.subTest(text=text):
                self.assertEqual(path_line_citations(text), [f"1: {citation}"])

    def test_matcher_reports_every_citation_with_its_line_number(self):
        text = "\n".join(["clean line", "a " + _cite("x.py", 1) + " and " + _cite("y.md", 22),
                          "clean", _cite("z.toml", 3)])
        self.assertEqual(path_line_citations(text), [
            "2: " + _cite("x.py", 1), "2: " + _cite("y.md", 22), "4: " + _cite("z.toml", 3)])

    def test_matcher_spares_symbol_form_urls_addresses_and_placeholders(self):
        clean = [
            "`handleCrPlan` (src/v2.ts)",
            "`build_plan` (modelb_axi/scaffold.py) builds it",
            "the server at http" + "://localhost" + chr(58) + "3849/api",
            "https" + "://api.example.com" + chr(58) + "443/v1",
            "127.0.0.1" + chr(58) + "4000",
            "never by `path:line` and never `file:line`",
            "the shape `<file>.<ext>:<digits>`",
            "at 12" + chr(58) + "30 today; ratio 3" + chr(58) + "4",
            '{"a.b": 1, "key": 2}',
            "cli.py and scaffold.py, no line",
            "localhost" + chr(58) + "13305",
        ]
        for text in clean:
            with self.subTest(text=text):
                self.assertEqual(path_line_citations(text), [])

    def test_instruction_checker_flags_an_unnegated_file_line_or_path_line(self):
        self.assertEqual(line_citation_instructions(
            "- Report findings as [file:line] — issue.\n"
            "- Keep the detail (test ids, `path:line`, values).\n"), [
            "1: - Report findings as [file:line] — issue.",
            "2: - Keep the detail (test ids, `path:line`, values)."])

    def test_instruction_checker_spares_a_negated_clause(self):
        self.assertEqual(line_citation_instructions(
            "- Cite by symbol, never by `path:line`.\n"
            "- No `file:line` breadcrumbs.\n"
            "- Name the symbol rather than file:line.\n"), [])

    def test_instruction_checker_negation_is_clause_scoped(self):
        self.assertEqual(line_citation_instructions(
            "- Never dump a log. Keep failing ids and file:line.\n"),
            ["1: - Never dump a log. Keep failing ids and file:line."])

    def test_rule_checker_passes_well_formed_fixtures(self):
        self.assertEqual(rule_findings(_GOOD_CR_AUTHORING, CR_AUTHORING_RULE), [])
        self.assertEqual(rule_findings(_GOOD_TEMPLATE, TEMPLATE_RULE), [])
        self.assertEqual(line_citation_instructions(_GOOD_TEMPLATE), [])
        self.assertEqual(path_line_citations(_GOOD_CR_AUTHORING + _GOOD_TEMPLATE), [])

    def test_rule_checker_reports_a_rule_without_the_never_clause(self):
        text = _GOOD_CR_AUTHORING.replace(", never by `path:line`", "")
        self.assertEqual(rule_findings(text, CR_AUTHORING_RULE), list(CR_AUTHORING_RULE))

    def test_rule_checker_reports_cr_authoring_rule_without_the_symbol_and_file_form(self):
        text = _GOOD_CR_AUTHORING.replace(" (`handleCrPlan` (src/v2.ts))", "")
        self.assertEqual(rule_findings(text, CR_AUTHORING_RULE),
                         ["the rule shows the symbol-and-file form"])

    def test_rule_checker_reports_a_template_rule_missing_a_scope(self):
        for scope in ("comments, ", "docstrings and\n  ", "reports"):
            with self.subTest(scope=scope):
                text = _GOOD_TEMPLATE.replace(scope, "")
                self.assertEqual(rule_findings(text, TEMPLATE_RULE), list(TEMPLATE_RULE))

    def test_rule_split_across_two_blocks_is_not_carried(self):
        text = ("- Cite code by symbol and file in comments, docstrings and reports.\n"
                "- Never by `path:line`.\n")
        self.assertEqual(rule_findings(text, TEMPLATE_RULE), list(TEMPLATE_RULE))


class CitationGuardWalkerOnSyntheticTreeTest(unittest.TestCase):
    """The guard's walker, proved on a tree built in a temp dir at run time."""

    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="cite-by-symbol-"))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)

    def _write(self, rel: str, text: str) -> None:
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def test_every_guarded_surface_is_walked(self):
        hit = "see " + _cite("modelb_axi/cli.py", 4) + "\n"
        rels = ["AGENTS.md", "skills-src/b/SKILL.md", "generator/templates/red.md.tmpl",
                "generator/stacks/python.toml", "modelb_axi/deploy.py",
                "pi-package/extensions/worktree.ts", "scripts/w.py", "tests/test_x.py"]
        for rel in rels:
            self._write(rel, hit)
        self.assertEqual(citation_findings(self.root), sorted(
            f"{rel} line 1: " + _cite("modelb_axi/cli.py", 4) for rel in rels))

    def test_surfaces_outside_the_guard_are_not_walked(self):
        hit = _cite("modelb_axi/cli.py", 4) + "\n"
        for rel in ("docs/changes/CR-X.md", "docs/research/PRD.md", "archive/wave2/a.md",
                    "audits/2026-01-01.md", "generator/agents/python-red-agent.md",
                    "contracts/lean-ctx.md", "README.md"):
            self._write(rel, hit)
        self.assertEqual(citation_findings(self.root), [])

    def test_node_modules_and_pycache_are_pruned(self):
        hit = _cite("index.js", 10) + "\n"
        self._write("pi-package/node_modules/dep/index.js", hit)
        self._write("tests/__pycache__/mod.txt", hit)
        self._write("pi-package/extensions/ok.ts", "clean\n")
        self.assertEqual(citation_findings(self.root), [])

    def test_undecodable_file_is_skipped_and_the_walk_goes_on(self):
        path = self.root / "tests" / "blob.bin"
        path.parent.mkdir(parents=True)
        path.write_bytes(b"\xff\xfe\x00" + _cite("x.py", 1).encode())
        self._write("tests/test_y.py", "# " + _cite("scaffold.py", 752) + "\n")
        self.assertEqual(citation_findings(self.root),
                         ["tests/test_y.py line 1: " + _cite("scaffold.py", 752)])

    def test_clean_tree_yields_no_finding(self):
        self._write("AGENTS.md", "`deploy_assets` (modelb_axi/deploy.py)\n")
        self._write("tests/test_z.py", '"""`handleCrPlan` (src/v2.ts)."""\n')
        self.assertEqual(citation_findings(self.root), [])


# ------------------------------------------------------------------ the tree ----


class CitationGuardTest(unittest.TestCase):
    """§S4 Guard — the guarded surfaces carry no path-and-line citation."""

    def test_the_guarded_surfaces_are_the_ones_s4_lists(self):
        self.assertEqual(GUARDED_DIRS, ("skills-src", "generator/templates", "generator/stacks",
                                        "modelb_axi", "pi-package", "scripts", "tests"))
        self.assertEqual(GUARDED_FILES, ("AGENTS.md",))
        missing = [rel for rel in GUARDED_DIRS + GUARDED_FILES if not (REPO_ROOT / rel).exists()]
        self.assertEqual(missing, [])

    def test_the_walk_reaches_this_module(self):
        self.assertIn(Path(__file__).resolve(),
                      [path.resolve() for path in guarded_files(REPO_ROOT)])

    def test_this_module_carries_no_path_line_citation_of_its_own(self):
        self.assertEqual(path_line_citations(read_text(Path(__file__))), [])

    def test_no_guarded_surface_carries_a_path_line_citation(self):
        self.assertEqual(citation_findings(REPO_ROOT), [])


class CiteBySymbolRuleTest(unittest.TestCase):
    """§S4 Rules — ``cr-authoring`` and the role templates carry the cite-by-symbol rule."""

    def test_cr_authoring_carries_the_cite_by_symbol_rule(self):
        self.assertEqual(rule_findings(read_text(REPO_ROOT / CR_AUTHORING_REL), CR_AUTHORING_RULE),
                         [])

    def test_every_role_template_carries_the_rule_for_comments_docstrings_and_reports(self):
        self.assertEqual({role: rule_findings(_template(role), TEMPLATE_RULE)
                          for role in TEMPLATE_ROLES}, {role: [] for role in TEMPLATE_ROLES})

    def test_every_rendered_agent_carries_the_rule(self):
        self.assertEqual([f"{stack}-{role}: {name}" for stack, role, _params, body in
                          _rendered_agents() for name in rule_findings(body, TEMPLATE_RULE)], [])

    def test_no_role_template_instructs_a_file_line_citation(self):
        self.assertEqual([f"{role}.md.tmpl {hit}" for role in TEMPLATE_ROLES
                          for hit in line_citation_instructions(_template(role))], [])


if __name__ == "__main__":
    unittest.main()
