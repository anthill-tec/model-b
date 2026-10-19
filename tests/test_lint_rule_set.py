"""Model B's lint rule set and gate step — the configuration, the suppressions, the code shapes and
the ``AGENTS.md`` text.

Contract: ``docs/changes/CR-MDB-053-script-lint.md``. This module holds the structure §S6 assigns
to the tests, with the standard library only: AC1 (§S1), AC2's suppression clause (§S2), AC3
(§S3), AC4's code clauses (§S4) and AC5 (§S5). ``ruff check``'s exit code and ``pycodestyle``
(AC2's and AC4's tool clauses) are not tests: GREEN, FIX, VERIFY and the gate's lint step run them.

Class map:

- ``RuffConfigTest`` — AC1: ``pyproject.toml``'s ``[tool.ruff]`` keys other than ``lint`` and its
  ``[tool.ruff.lint]`` are exactly §S1's; ``[project] dependencies`` stays empty.
- ``CoveredFilesDetectorTest`` / ``NoqaDetectorTest`` / ``NoqaBoundariesTest`` — AC2: in the files
  the rule set covers (:func:`covered_files`), every ``noqa`` naming a selected code is
  ``# noqa: BLE001`` with a stated reason, only on the blind catch of one of the five never-fail
  boundaries (:data:`BOUNDARIES`), and every such catch carries one (:func:`noqa_findings`).
- ``NamedExceptionsDetectorTest`` / ``NamedExceptionsTest`` — AC2: the two ``git_head`` functions
  catch ``(subprocess.CalledProcessError, OSError)``; phase 4's JSON check catches ``ValueError``.
- ``PyrightShapesDetectorTest`` / ``PyrightShapesTest`` — AC3: in the three rust tools no
  ``None``-default parameter's annotation excludes ``None``, no attribute of ``__doc__`` is read
  without a fallback, and ``rust-dead-scan.py``'s ``report`` is annotated ``dict[str, object]``.
- ``DeadCodeDetectorTest`` / ``DeadCodeTest`` — AC4: ``worktree-flow.py`` defines no
  ``_pid_alive``; ``count_signals`` and ``mode_inventory`` carry no ``//`` guard.
- ``LintGateDetectorTest`` / ``AgentsMdLintGateTest`` — AC5: the pre-merge gate opens with a step
  running ``ruff check`` that must exit 0, before the ``pre-merge-gate`` run; the six existing steps
  keep their wording, renumbered after it (:func:`lint_gate_findings`).
- ``LintDocsDetectorTest`` / ``AgentsMdLintDocsTest`` — AC5: Development Commands names
  ``ruff check`` and ``uv tool install ruff`` and keeps the unit naming
  ``.github/workflows/release.yml``; Important Files names ``[tool.ruff]``; no sentence says no
  linter is configured (:func:`lint_docs_findings`).

Every checker is proved on synthetic text first; the tests on the real tree then apply it.

Stdlib only.
"""

import ast
import fnmatch
import io
import os
import re
import tempfile
import tokenize
import tomllib
import unittest
from pathlib import Path

from tests._helpers import REPO_ROOT, md_section
from tests.test_board_holds_the_queue import norm_units, units
from tests.test_bootstrap_shutdown_registry import normalise
from tests.test_client_path_anchoring import _read
from tests.test_coverage_gate import GATE_COMMAND, _commands, testing_section
from tests.test_suite_hygiene import AGENTS_ONE_WORKFLOW

AGENTS_MD = REPO_ROOT / "AGENTS.md"
PYPROJECT = REPO_ROOT / "pyproject.toml"
CRATE_MAP = "scripts/rust-crate-map.py"
DEAD_SCAN = "scripts/rust-dead-scan.py"
CODE_HEALTH = "scripts/rust-code-health.py"
RUST_TOOLS = (CRATE_MAP, DEAD_SCAN, CODE_HEALTH)
RELEASE_GATE = "scripts/skill-release-gate.py"
WORKTREE_FLOW = "scripts/worktree-flow.py"
SCHEDULE_DB = "scripts/schedule_db.py"
AMBIENT_HOOK = "hooks-src/scripts/ambient-board-status"

#: AC1 — ``[tool.ruff]``'s keys other than ``lint``, exactly.
EXTEND_INCLUDE = ["hooks-src/scripts/*"]
EXTEND_EXCLUDE = ["scripts/toon.py", ".github/scripts", "tests", "archive", "generator/agents"]
RUFF = {
    "required-version": ">=0.16",
    "target-version": "py314",
    "extend-include": EXTEND_INCLUDE,
    "extend-exclude": EXTEND_EXCLUDE,
}
#: AC1 — ``[tool.ruff.lint]``, exactly.
SELECT = ["F", "I", "BLE001", "PIE810", "RUF059", "SIM102", "SIM105"]
RUFF_LINT = {"select": SELECT}

#: A rule code :data:`SELECT` selects: ``F`` and ``I`` are whole linters (their codes are the
#: prefix and digits), the other five single codes.
SELECTED_CODE = re.compile(r"F\d+|I\d+|BLE001|PIE810|RUF059|SIM102|SIM105")

#: The directories ruff never walks into here: its default ``exclude`` and those ``.gitignore``
#: names (ruff respects ``.gitignore``).
RUFF_PRUNED = frozenset({
    ".bzr", ".direnv", ".eggs", ".git", ".git-rewrite", ".hg", ".ipynb_checkpoints", ".mypy_cache",
    ".nox", ".pants.d", ".pyenv", ".pytest_cache", ".pytype", ".ruff_cache", ".svn", ".tox",
    ".venv", ".vscode", "__pypackages__", "_build", "buck-out", "build", "dist", "node_modules",
    "site-packages", "venv", "__pycache__", ".worktrees", ".lean-ctx", "test-reports",
})

#: AC2 / §S2 — the five never-fail boundaries, as ``(file, function): blind catches it keeps``:
#: the board true-up in ``rust-code-health.py``'s snapshot (``cmd_snapshot``), the ledger hook in
#: ``schedule_db.py`` (``_ledger_hook``), the ``.env`` copy in ``worktree-flow.py``'s start
#: (``cmd_start``), and the hook's two (``_run``).
BOUNDARIES = {
    (CODE_HEALTH, "cmd_snapshot"): 1,
    (SCHEDULE_DB, "_ledger_hook"): 1,
    (WORKTREE_FLOW, "cmd_start"): 1,
    (AMBIENT_HOOK, "_run"): 2,
}

#: AC2 / §S2 — what the two ``git_head`` functions and phase 4's JSON check catch.
GIT_HEAD_CATCHES = [["OSError", "subprocess.CalledProcessError"]]
JSON_CHECK_CATCHES = [["ValueError"]]

#: A ``noqa`` comment: its codes (ruff's code shape, comma- or space-separated) and what follows.
NOQA = re.compile(r"#\s*(?i:noqa)(?::\s*(?P<codes>[A-Z]+[0-9]+(?:(?:\s*,\s*|\s+)[A-Z]+[0-9]+)*))?"
                  r"(?P<rest>.*)$")


# ------------------------------------------------------------- AC2: noqa ----

def _excluded(rel: str) -> bool:
    return any(rel == path or rel.startswith(path + "/") for path in EXTEND_EXCLUDE)


def covered_files(root: Path) -> list[str]:
    """The repo-relative paths, sorted, of the files the rule set covers under ``root``: every
    ``.py``/``.pyi`` file and every :data:`EXTEND_INCLUDE` match, outside :data:`EXTEND_EXCLUDE`
    and :data:`RUFF_PRUNED`."""
    found = []
    for current, dirs, files in os.walk(root):
        base = Path(current)
        dirs[:] = sorted(d for d in dirs if d not in RUFF_PRUNED
                         and not _excluded((base / d).relative_to(root).as_posix()))
        for name in files:
            rel = (base / name).relative_to(root).as_posix()
            if _excluded(rel):
                continue
            if name.endswith((".py", ".pyi")) or any(fnmatch.fnmatch(rel, p) for p in EXTEND_INCLUDE):
                found.append(rel)
    return sorted(found)


def _functions(tree: ast.AST) -> list[tuple[int, int, str]]:
    return [(n.lineno, n.end_lineno or n.lineno, n.name) for n in ast.walk(tree)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]


def _enclosing(functions, line: int) -> str | None:
    """The name of the innermost function of ``functions`` spanning ``line``."""
    spans = [(start, name) for start, end, name in functions if start <= line <= end]
    return max(spans)[1] if spans else None


def _blind_catches(tree: ast.AST, functions) -> dict[int, str | None]:
    """``{except line: enclosing function}`` for every blind catch — bare, ``Exception`` or
    ``BaseException``."""
    out = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler) and (
                node.type is None or (isinstance(node.type, ast.Name)
                                      and node.type.id in ("Exception", "BaseException"))):
            out[node.lineno] = _enclosing(functions, node.lineno)
    return out


def _comments(text: str) -> list[tuple[int, str]]:
    return [(tok.start[0], tok.string)
            for tok in tokenize.generate_tokens(io.StringIO(text).readline)
            if tok.type == tokenize.COMMENT]


def noqa_findings(sources: dict[str, str], boundaries: dict[tuple[str, str], int]) -> list[str]:
    """AC2: what the ``noqa`` comments of ``sources`` (``{path: text}``) get wrong — one naming a
    selected code that is not exactly ``# noqa: BLE001``, one stating no reason, one off a
    boundary's blind catch — and what each boundary of ``boundaries`` lacks: its function, its
    count of blind catches, a reasoned ``# noqa: BLE001`` on each."""
    out = []
    for (rel, function), _ in boundaries.items():
        if rel not in sources:
            out.append(f"{rel}: absent, so {function} carries no # noqa: BLE001")
    for rel, text in sorted(sources.items()):
        tree = ast.parse(text)
        functions = _functions(tree)
        blind = _blind_catches(tree, functions)
        reasoned = set()
        for line, comment in _comments(text):
            match = NOQA.search(comment)
            if match is None or not match.group("codes"):
                continue
            codes = re.split(r"[\s,]+", match.group("codes").strip())
            if not any(SELECTED_CODE.fullmatch(code) for code in codes):
                continue
            where = f"{rel} line {line} ({_enclosing(functions, line) or 'module'})"
            if codes != ["BLE001"]:
                out.append(f"{where}: names {', '.join(codes)}, not exactly BLE001")
            elif not re.search(r"[A-Za-z]{2,}", match.group("rest")):
                out.append(f"{where}: # noqa: BLE001 states no reason")
            elif line not in blind or (rel, blind[line]) not in boundaries:
                out.append(f"{where}: # noqa: BLE001 off a never-fail boundary's blind catch")
            else:
                reasoned.add(line)
        for (brel, function), want in boundaries.items():
            if brel != rel:
                continue
            if function not in {name for _, _, name in functions}:
                out.append(f"{rel}: no function {function}")
                continue
            lines = sorted(line for line, name in blind.items() if name == function)
            if len(lines) != want:
                out.append(f"{rel} {function}: {len(lines)} blind catches, §S2 keeps {want}")
            out += [f"{rel} line {line} ({function}): blind catch without a reasoned "
                    "# noqa: BLE001" for line in lines if line not in reasoned]
    return out


# ------------------------------------------------- AC2: named exceptions ----

def _caught(handler: ast.ExceptHandler) -> list[str]:
    if handler.type is None:
        return ["<bare>"]
    if isinstance(handler.type, ast.Tuple):
        return sorted(ast.unparse(e) for e in handler.type.elts)
    return [ast.unparse(handler.type)]


def _function(tree: ast.AST, name: str):
    return next((n for n in ast.walk(tree)
                 if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name), None)


def handler_catches(text: str, function: str) -> list[list[str]] | None:
    """What each ``except`` handler inside ``function`` of ``text`` catches, each sorted;
    ``None`` when ``text`` defines no ``function``."""
    node = _function(ast.parse(text), function)
    if node is None:
        return None
    return [_caught(h) for h in ast.walk(node) if isinstance(h, ast.ExceptHandler)]


def _calls_json_loads(node: ast.AST) -> bool:
    return any(isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
               and n.func.attr == "loads" and isinstance(n.func.value, ast.Name)
               and n.func.value.id == "json" for n in ast.walk(node))


def json_check_catches(text: str) -> list[list[str]] | None:
    """What the handlers of each ``try`` in ``phase_checks`` of ``text`` whose body calls
    ``json.loads`` catch; ``None`` when ``text`` defines no ``phase_checks``."""
    node = _function(ast.parse(text), "phase_checks")
    if node is None:
        return None
    return [_caught(h) for t in ast.walk(node) if isinstance(t, ast.Try)
            and any(_calls_json_loads(s) for s in t.body) for h in t.handlers]


# ----------------------------------------------------------- AC3: Pyright ----

def _allows_none(ann: ast.AST) -> bool:
    if isinstance(ann, ast.Constant):
        if ann.value is None:
            return True
        if isinstance(ann.value, str):
            try:
                return _allows_none(ast.parse(ann.value, mode="eval").body)
            except SyntaxError:
                return False
        return False
    if isinstance(ann, ast.BinOp) and isinstance(ann.op, ast.BitOr):
        return _allows_none(ann.left) or _allows_none(ann.right)
    if isinstance(ann, ast.Subscript):
        head = ast.unparse(ann.value).rsplit(".", 1)[-1]
        if head == "Optional":
            return True
        if head == "Union":
            elts = ann.slice.elts if isinstance(ann.slice, ast.Tuple) else [ann.slice]
            return any(_allows_none(e) for e in elts)
        return False
    return ast.unparse(ann).rsplit(".", 1)[-1] in ("Any", "object")


def none_default_findings(text: str) -> list[str]:
    """AC3: every parameter of ``text`` whose default is ``None`` and whose annotation excludes
    ``None``, as ``function(parameter: annotation = None)``."""
    out = []
    for fn in ast.walk(ast.parse(text)):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        args = fn.args
        positional = args.posonlyargs + args.args
        pairs = list(zip(positional[len(positional) - len(args.defaults):], args.defaults,
                         strict=True))
        pairs += [(a, d) for a, d in zip(args.kwonlyargs, args.kw_defaults, strict=True)
                  if d is not None]
        out += [f"{fn.name}({a.arg}: {ast.unparse(a.annotation)} = None)" for a, d in pairs
                if isinstance(d, ast.Constant) and d.value is None and a.annotation is not None
                and not _allows_none(a.annotation)]
    return out


def _is_doc(node: ast.AST) -> bool:
    return ((isinstance(node, ast.Name) and node.id == "__doc__")
            or (isinstance(node, ast.Attribute) and node.attr == "__doc__"))


def doc_read_findings(text: str) -> list[str]:
    """AC3: every attribute of ``__doc__`` that ``text`` reads with no fallback for a missing
    docstring — read straight off ``__doc__``, outside the body of an ``if`` (statement or
    expression) testing ``__doc__``."""
    out = []

    def visit(node: ast.AST, guarded: bool) -> None:
        if isinstance(node, ast.Attribute) and _is_doc(node.value) and not guarded:
            out.append(ast.unparse(node))
        if isinstance(node, (ast.If, ast.IfExp)) and any(_is_doc(n) for n in ast.walk(node.test)):
            body = node.body if isinstance(node, ast.If) else [node.body]
            orelse = node.orelse if isinstance(node, ast.If) else [node.orelse]
            visit(node.test, guarded)
            for child in body:
                visit(child, True)
            for child in orelse:
                visit(child, guarded)
            return
        for child in ast.iter_child_nodes(node):
            visit(child, guarded)

    visit(ast.parse(text), False)
    return out


def report_annotations(text: str) -> list[str]:
    """AC3: the annotation of every annotated assignment to ``report`` in ``main`` of ``text``."""
    node = _function(ast.parse(text), "main")
    if node is None:
        return []
    return [ast.unparse(n.annotation) for n in ast.walk(node) if isinstance(n, ast.AnnAssign)
            and isinstance(n.target, ast.Name) and n.target.id == "report"]


# --------------------------------------------------------- AC4: dead code ----

def defines(text: str, name: str) -> bool:
    """Whether ``text`` defines a function named ``name``, at any depth."""
    return _function(ast.parse(text), name) is not None


def comment_guards(text: str, function: str) -> list[str] | None:
    """AC4: every string constant naming ``//`` in ``function`` of ``text``, its docstring
    aside; ``None`` when ``text`` defines no ``function``."""
    node = _function(ast.parse(text), function)
    if node is None:
        return None
    body = node.body
    if (body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)):
        body = body[1:]
    return [n.value for stmt in body for n in ast.walk(stmt)
            if isinstance(n, ast.Constant) and isinstance(n.value, str) and "//" in n.value]


# ------------------------------------------------------- AC5: the gate step ----

#: The six steps of the pre-merge gate as the spec commit states them, their numbers dropped:
#: §S5 keeps their wording, renumbered after the lint step.
SIX_STEPS = (
    "**Clear the stale data.** Remove `test-reports/vidushi-mdb/.coverage` and every `.coverage.*` "
    "beside it. The lcov step merges a run into any data file already there, so a stale one would "
    "inflate the figure.",
    "**The real-`HOME` run:** `env MODELB_HOME=\"$(mktemp -d)\" XDG_DATA_HOME=\"$(mktemp -d)\" "
    "PI_CODING_AGENT_DIR=\"$(mktemp -d)\" python3 ~/.crucible/clients/python-crucible.py "
    "pre-merge-gate --cov-source modelb_axi,scripts,hooks-src/scripts,workflows-src,tools --agent "
    "vidushi-mdb --cycle <last cycle> --log /tmp/gate.log`.",
    "**The other two runs:** the empty-`HOME` run and the clean-runner run stay `test` runs.",
    "**The check:** `python3 tools/coverage-check.py test-reports/vidushi-mdb/coverage.lcov` runs "
    "against the branch's `AGENTS.md`. Close-out step 1 has merged develop in, so that file "
    "carries develop's baseline. The tool's table goes into the merge sign-off.",
    "**A drop** (exit 1) needs the user's explicit approval at sign-off.",
    "**The orchestrator records the new total** on the `Coverage baseline:` line, in the "
    "close-out's docs-only status-flip commit. That includes a drop the user approved.",
)

LINT_FIRST = "the gate's first step runs ruff check, which must exit 0"
LINT_BEFORE_GATE = "a step running ruff check comes before the pre-merge-gate run"
SIX_KEPT = "the six existing steps follow the lint step, their wording kept"
RENUMBERED = "the steps are numbered 1 to 7"

RUFF_CHECK = re.compile(r"(?<![\w-])ruff check(?![\w-])")
EXITS_ZERO = re.compile(r"\bexit(?:s|ing)?(?: with)?(?: code| status)?:? 0\b")
NUMBERED = re.compile(r"^\s*(\d+)[.)]\s+")


def gate_steps(section: str) -> list[tuple[int, str]]:
    """``(number, normalised text)`` for each numbered item of ``section``, in order."""
    return [(int(m.group(1)), normalise(u[m.end():])) for u in units(section)
            if (m := NUMBERED.match(u))]


def lint_gate_findings(text: str) -> list[str]:
    """AC5: what the pre-merge gate in the Testing & QA of ``text`` (an ``AGENTS.md``) lacks of
    its lint step, in order."""
    section = testing_section(text)
    steps = gate_steps(section)
    out = []
    if not (steps and RUFF_CHECK.search(steps[0][1]) and EXITS_ZERO.search(steps[0][1])):
        out.append(LINT_FIRST)
    raw = units(section)
    lint = next((i for i, u in enumerate(raw) if RUFF_CHECK.search(normalise(u))), None)
    gate = next((i for i, u in enumerate(raw) if GATE_COMMAND.search(u)), None)
    if lint is None or gate is None or lint >= gate:
        out.append(LINT_BEFORE_GATE)
    if [t for _, t in steps[1:]] != [normalise(s) for s in SIX_STEPS]:
        out.append(SIX_KEPT)
    if [n for n, _ in steps] != list(range(1, len(SIX_STEPS) + 2)):
        out.append(RENUMBERED)
    return out


# ------------------------------------------------------------ AC5: the docs ----

RUFF_CHECK_SHOWN = "Development Commands show ruff check"
UV_INSTALL_SHOWN = "Development Commands show uv tool install ruff"
ONE_WORKFLOW_KEPT = "Development Commands keep the unit naming one workflow, release.yml"
TOOL_RUFF_NAMED = "Important Files name pyproject.toml's [tool.ruff]"
NO_LINTER_SAID = "a sentence says no linter is configured"

#: A unit saying no linter is configured: "no linter", "**no** linter/formatter/…", or a "no
#: ``[tool.ruff|…]``" aside.
NO_LINTER = (re.compile(r"\bno (?:[\w-]+/)*linters?\b"), re.compile(r"\bno \[tool\.ruff\b"))


def no_linter_units(text: str) -> list[str]:
    """The normalised units of ``text`` that say no linter is configured."""
    return [u for u in norm_units(text) if any(rx.search(u) for rx in NO_LINTER)]


def lint_docs_findings(text: str) -> list[str]:
    """AC5: what ``text`` (an ``AGENTS.md``) gets wrong of the lint docs, in order."""
    dev = md_section(text, "## Development Commands")
    commands = _commands(dev)
    out = []
    if not any(re.match(r"ruff check(?![\w-])", c) for c in commands):
        out.append(RUFF_CHECK_SHOWN)
    if not any(re.match(r"uv tool install ruff(?![\w-])", c) for c in commands):
        out.append(UV_INSTALL_SHOWN)
    if not any(all(re.search(rx, u) for rx in AGENTS_ONE_WORKFLOW) for u in norm_units(dev)):
        out.append(ONE_WORKFLOW_KEPT)
    if not any("pyproject.toml" in u and "[tool.ruff]" in u
               for u in norm_units(md_section(text, "## Important Files"))):
        out.append(TOOL_RUFF_NAMED)
    if no_linter_units(text):
        out.append(NO_LINTER_SAID)
    return out


# --------------------------------------------------------- synthetic texts ----

GOOD_LINT_STEP = ("1. **Lint.** `ruff check` from the repository root exits 0; a finding is fixed on "
                  "the branch before the gate runs.\n")
GOOD_GATE = "".join(f"{n}. {step}\n" for n, step in enumerate(SIX_STEPS, 2))
TODAYS_GATE = "".join(f"{n}. {step}\n" for n, step in enumerate(SIX_STEPS, 1))
WORKFLOW = "One workflow runs on GitHub, `.github/workflows/release.yml`:\n\n"
GOOD_DEV = (
    "## Development Commands\n\n```bash\n"
    "uv tool install ruff                 # get ruff, a development tool\n"
    "ruff check                           # the rule set lives in pyproject.toml\n"
    "```\n\n"
    "Ruff is configured, as a development tool; no formatter or type checker is. " + WORKFLOW)
GOOD_IMPORTANT = (
    "## Important Files\n\n"
    "- `pyproject.toml`'s `[tool.ruff]` and `[tool.ruff.lint]` — the rule set, beside its "
    "`[tool.coverage.run]` and `[tool.coverage.report]`.\n\n")
GOOD_TESTING = ("## Testing & QA\n\nModel B's pre-merge gate, in order:\n\n" + GOOD_LINT_STEP
                + GOOD_GATE + "\n")
GOOD_AGENTS = "# Repository Guidelines\n\n" + GOOD_DEV + GOOD_IMPORTANT + GOOD_TESTING
#: The retired sentence, as the spec commit's ``AGENTS.md`` carries it.
NO_LINTER_SENTENCE = (
    "There is **no** Makefile/justfile and **no** linter/formatter/type-checker configured (no "
    "`[tool.ruff|black|mypy|pytest]`). Do not invent lint commands; match surrounding style by "
    "hand. ")

#: A boundary-conforming pair of sources for :func:`noqa_findings`.
GOOD_BOUNDARY = (
    "import subprocess\n\n\n"
    "def boundary():\n"
    "    try:\n"
    "        subprocess.run(['x'])\n"
    "    except Exception as e:  # noqa: BLE001 — the caller must never fail\n"
    "        print(e)\n\n\n"
    "def other():\n"
    "    import json  # noqa: S314 - not a selected code\n"
    "    s = '# noqa: F401'\n"
    "    try:\n"
    "        return json.loads(s)\n"
    "    except ValueError:\n"
    "        return None\n")
GOOD_HOOK = (
    "def _run():\n"
    "    try:\n"
    "        return main()\n"
    "    except Exception:  # noqa: BLE001 — the hook must never fail\n"
    "        try:\n"
    "            return 1\n"
    "        except Exception:  # noqa: BLE001 — even the note may not print\n"
    "            return 0\n")
SYNTH_BOUNDARIES = {("a.py", "boundary"): 1, ("hook", "_run"): 2}


def _synthetic_sources(**replace) -> dict[str, str]:
    sources = {"a.py": GOOD_BOUNDARY, "hook": GOOD_HOOK}
    for old, new in replace.items():
        sources = {k: v.replace(old.replace("_SP_", " "), new) for k, v in sources.items()}
    return sources


# ----------------------------------------------------------------- AC1 ----

class RuffConfigTest(unittest.TestCase):
    """AC1 — ``pyproject.toml`` pins the rule set; ruff is never a runtime dependency."""

    @classmethod
    def setUpClass(cls):
        with PYPROJECT.open("rb") as fh:
            cls.config = tomllib.load(fh)
        cls.ruff = cls.config.get("tool", {}).get("ruff")

    def test_tool_ruff_keys_other_than_lint_are_exactly_the_pinned_four(self):
        self.assertEqual(self.config["project"].get("dependencies", []), [],
                         "AC1: [project] dependencies stays empty")
        self.assertIsInstance(self.ruff, dict, "AC1: pyproject.toml has no [tool.ruff]")
        self.assertEqual({k: v for k, v in self.ruff.items() if k != "lint"}, RUFF,
                         "AC1: [tool.ruff] keys other than lint are exactly required-version, "
                         "target-version, extend-include and extend-exclude")

    def test_tool_ruff_lint_selects_exactly_the_seven_codes(self):
        self.assertIsInstance(self.ruff, dict, "AC1: pyproject.toml has no [tool.ruff]")
        self.assertEqual(self.ruff.get("lint"), RUFF_LINT,
                         "AC1: [tool.ruff.lint] is exactly select = " + repr(SELECT))


# ----------------------------------------------------------------- AC2 ----

class CoveredFilesDetectorTest(unittest.TestCase):
    """AC2 — :func:`covered_files` on a temp tree: the ``.py`` files and the extensionless hooks,
    without the excluded trees, ruff's default excludes or the gitignored directories."""

    def test_covered_files_follow_extend_include_and_extend_exclude(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for rel in ("modelb_axi/cli.py", "scripts/worktree-flow.py", "scripts/toon.py",
                        "scripts/gate-lock.sh", "hooks-src/scripts/ambient-board-status",
                        "hooks-src/schema.md", ".github/scripts/stamp_version.py",
                        ".github/tool.py", "tests/test_x.py", "archive/old.py",
                        "generator/agents/x.py", "generator/build.py", ".venv/lib/x.py",
                        ".worktrees/cr/scripts/a.py", "modelb_axi/__pycache__/cli.py",
                        "stubs/a.pyi"):
                path = root / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("x = 1\n", encoding="utf-8")
            self.assertEqual(covered_files(root), [
                ".github/tool.py", "generator/build.py", "hooks-src/scripts/ambient-board-status",
                "modelb_axi/cli.py", "scripts/worktree-flow.py", "stubs/a.pyi"])

    def test_the_real_tree_covers_the_hooks_and_the_five_boundary_files_but_no_test(self):
        covered = covered_files(REPO_ROOT)
        for rel in {rel for rel, _ in BOUNDARIES}:
            self.assertIn(rel, covered)
        self.assertEqual([r for r in covered if r.startswith(("tests/", "archive/"))], [])
        self.assertNotIn("scripts/toon.py", covered)


class NoqaDetectorTest(unittest.TestCase):
    """AC2 — :func:`noqa_findings`, both ways on synthetic sources."""

    def test_the_conforming_sources_pass(self):
        self.assertEqual(noqa_findings(_synthetic_sources(), SYNTH_BOUNDARIES), [])

    def test_a_selected_code_other_than_ble001_is_a_finding_anywhere(self):
        sources = _synthetic_sources(**{"import json  # noqa: S314 - not a selected code":
                                        "import json  # noqa: F401 - unused"})
        self.assertEqual(noqa_findings(sources, SYNTH_BOUNDARIES),
                         ["a.py line 12 (other): names F401, not exactly BLE001"])
        for codes in ("BLE001, SIM105", "SIM105", "I001", "RUF059"):
            with self.subTest(codes=codes):
                sources = _synthetic_sources(**{"# noqa: BLE001 — the caller":
                                                f"# noqa: {codes} — the caller"})
                findings = noqa_findings(sources, SYNTH_BOUNDARIES)
                self.assertEqual(findings, [
                    f"a.py line 7 (boundary): names {codes}, not exactly BLE001",
                    "a.py line 7 (boundary): blind catch without a reasoned # noqa: BLE001"])

    def test_a_ble001_with_no_stated_reason_is_a_finding(self):
        sources = _synthetic_sources(**{"  # noqa: BLE001 — the caller must never fail":
                                        "  # noqa: BLE001"})
        self.assertEqual(noqa_findings(sources, SYNTH_BOUNDARIES), [
            "a.py line 7 (boundary): # noqa: BLE001 states no reason",
            "a.py line 7 (boundary): blind catch without a reasoned # noqa: BLE001"])

    def test_a_ble001_off_a_boundary_is_a_finding(self):
        sources = _synthetic_sources(**{"    except ValueError:\n":
                                        "    except Exception:  # noqa: BLE001 — convenient\n"})
        self.assertEqual(noqa_findings(sources, SYNTH_BOUNDARIES), [
            "a.py line 16 (other): # noqa: BLE001 off a never-fail boundary's blind catch"])

    def test_a_ble001_on_a_boundary_line_that_is_not_its_blind_catch_is_a_finding(self):
        sources = _synthetic_sources(**{"        subprocess.run(['x'])\n":
                                        "        subprocess.run(['x'])  # noqa: BLE001 — why\n"})
        self.assertEqual(noqa_findings(sources, SYNTH_BOUNDARIES), [
            "a.py line 6 (boundary): # noqa: BLE001 off a never-fail boundary's blind catch"])

    def test_a_boundary_blind_catch_without_its_noqa_is_a_finding(self):
        sources = _synthetic_sources(**{"  # noqa: BLE001 — even the note may not print": ""})
        self.assertEqual(noqa_findings(sources, SYNTH_BOUNDARIES), [
            "hook line 7 (_run): blind catch without a reasoned # noqa: BLE001"])

    def test_a_boundary_whose_blind_catch_names_its_exceptions_is_a_finding(self):
        sources = _synthetic_sources(**{
            "    except Exception as e:  # noqa: BLE001 — the caller must never fail\n":
            "    except OSError as e:\n"})
        self.assertEqual(noqa_findings(sources, SYNTH_BOUNDARIES),
                         ["a.py boundary: 0 blind catches, §S2 keeps 1"])

    def test_a_missing_boundary_function_or_file_is_a_finding(self):
        sources = _synthetic_sources(**{"def boundary():": "def renamed():"})
        self.assertEqual(noqa_findings(sources, SYNTH_BOUNDARIES), [
            "a.py line 7 (renamed): # noqa: BLE001 off a never-fail boundary's blind catch",
            "a.py: no function boundary"])
        self.assertEqual(noqa_findings({"hook": GOOD_HOOK}, SYNTH_BOUNDARIES),
                         ["a.py: absent, so boundary carries no # noqa: BLE001"])

    def test_an_unselected_code_and_a_noqa_inside_a_string_are_not_findings(self):
        self.assertEqual(noqa_findings({"b.py": "import os  # noqa: E402\ns = '# noqa: F401'\n"},
                                       {}), [])


class NoqaBoundariesTest(unittest.TestCase):
    """AC2 — the real tree: every selected-code ``noqa`` is a reasoned ``# noqa: BLE001`` on one of
    the five never-fail boundaries' blind catches, and each of them carries one."""

    def test_every_selected_code_noqa_is_a_reasoned_ble001_at_the_five_never_fail_boundaries(self):
        sources = {rel: _read(rel) for rel in covered_files(REPO_ROOT)}
        findings = noqa_findings(sources, BOUNDARIES)
        self.assertEqual(findings, [], "AC2 / §S2: the noqa suppressions:\n  " + "\n  ".join(findings))


class NamedExceptionsDetectorTest(unittest.TestCase):
    """AC2 — :func:`handler_catches` and :func:`json_check_catches` on synthetic text."""

    GIT_HEAD = ("def git_head(root):\n    try:\n        return run(root)\n"
                "    except (subprocess.CalledProcessError, OSError):\n        return 'unknown'\n")
    PHASE = ("class G:\n    def phase_checks(self, out):\n        if out:\n            try:\n"
             "                val = json.loads(out)\n            except ValueError as e:\n"
             "                print(e)\n        try:\n            x()\n"
             "        except Exception:\n            pass\n")

    def test_the_named_catches_are_read_back_sorted(self):
        self.assertEqual(handler_catches(self.GIT_HEAD, "git_head"), GIT_HEAD_CATCHES)
        self.assertEqual(json_check_catches(self.PHASE), JSON_CHECK_CATCHES)

    def test_a_blind_or_partial_catch_reads_back_as_such(self):
        blind = self.GIT_HEAD.replace("(subprocess.CalledProcessError, OSError)", "Exception")
        self.assertEqual(handler_catches(blind, "git_head"), [["Exception"]])
        partial = self.GIT_HEAD.replace("(subprocess.CalledProcessError, OSError)", "OSError")
        self.assertEqual(handler_catches(partial, "git_head"), [["OSError"]])
        self.assertEqual(json_check_catches(self.PHASE.replace("except ValueError as e",
                                                               "except Exception as e")),
                         [["Exception"]])

    def test_an_absent_function_reads_back_none(self):
        self.assertIsNone(handler_catches(self.GIT_HEAD, "other"))
        self.assertIsNone(json_check_catches(self.GIT_HEAD))


class NamedExceptionsTest(unittest.TestCase):
    """AC2 / §S2 — the real tools name the exceptions their non-boundary catches expect."""

    def test_git_head_catches_called_process_error_and_os_error_in_both_rust_tools(self):
        for rel in (CRATE_MAP, DEAD_SCAN):
            with self.subTest(tool=rel):
                self.assertEqual(handler_catches(_read(rel), "git_head"), GIT_HEAD_CATCHES,
                                 f"AC2: {rel}'s git_head catches "
                                 "(subprocess.CalledProcessError, OSError)")

    def test_phase_4_json_check_catches_value_error(self):
        self.assertEqual(json_check_catches(_read(RELEASE_GATE)), JSON_CHECK_CATCHES,
                         "AC2: phase 4's json.loads check in skill-release-gate.py catches "
                         "ValueError")


# ----------------------------------------------------------------- AC3 ----

class PyrightShapesDetectorTest(unittest.TestCase):
    """AC3 — the three shape checkers, both ways on synthetic text."""

    def test_a_none_default_must_be_allowed_by_its_annotation(self):
        text = ("def f(a, base: Path = None, modules: list = None, *, k: int = None,\n"
                "      ok: Path | None = None, o2: Optional[list] = None, o3: 'list | None' = None,\n"
                "      u: Union[int, None] = None, bare=None, other: int = 3):\n    pass\n")
        self.assertEqual(none_default_findings(text), [
            "f(base: Path = None)", "f(modules: list = None)", "f(k: int = None)"])

    def test_a_docstring_attribute_needs_a_fallback(self):
        bad = "def main():\n    d = __doc__.splitlines()[0]\n    e = mod.__doc__.strip()\n"
        self.assertEqual(doc_read_findings(bad), ["__doc__.splitlines", "mod.__doc__.strip"])
        good = ("def main():\n    d = (__doc__ or '').splitlines()[0]\n"
                "    e = __doc__.strip() if __doc__ else ''\n    f = __doc__\n"
                "    if __doc__:\n        g = __doc__.splitlines()\n")
        self.assertEqual(doc_read_findings(good), [])

    def test_the_report_annotation_is_read_back(self):
        self.assertEqual(report_annotations("def main():\n    report = {'a': 1}\n"), [])
        self.assertEqual(report_annotations(
            "def main():\n    report: dict[str, object] = {'a': 1}\n"), ["dict[str, object]"])
        self.assertEqual(report_annotations("def other():\n    report: dict = {}\n"), [])


class PyrightShapesTest(unittest.TestCase):
    """AC3 — the three rust tools carry the shapes §S3 corrects to."""

    def test_no_none_default_parameter_has_an_annotation_excluding_none(self):
        for rel in RUST_TOOLS:
            with self.subTest(tool=rel):
                self.assertEqual(none_default_findings(_read(rel)), [],
                                 f"AC3: {rel} annotates a None default as excluding None")

    def test_no_docstring_attribute_is_read_without_a_fallback(self):
        for rel in RUST_TOOLS:
            with self.subTest(tool=rel):
                self.assertEqual(doc_read_findings(_read(rel)), [],
                                 f"AC3: {rel} reads __doc__ with no fallback for a missing "
                                 "docstring")

    def test_dead_scan_report_is_annotated_dict_str_object(self):
        self.assertEqual(report_annotations(_read(DEAD_SCAN)), ["dict[str, object]"],
                         "AC3: rust-dead-scan.py's report is annotated dict[str, object]")


# ----------------------------------------------------------------- AC4 ----

class DeadCodeDetectorTest(unittest.TestCase):
    """AC4 — :func:`defines` and :func:`comment_guards`, both ways on synthetic text."""

    GUARDED = ('def count_signals(text):\n    """Lines starting // are comments."""\n'
               "    for s in text.splitlines():\n        if not s.startswith('//'):\n"
               "            yield s\n")

    def test_a_definition_is_found_at_any_depth(self):
        self.assertTrue(defines("class A:\n    def _pid_alive(self):\n        pass\n", "_pid_alive"))
        self.assertFalse(defines("x = _pid_alive\n", "_pid_alive"))

    def test_a_comment_guard_is_found_and_the_docstring_spared(self):
        self.assertEqual(comment_guards(self.GUARDED, "count_signals"), ["//"])
        unguarded = self.GUARDED.replace("        if not s.startswith('//'):\n            yield s\n",
                                         "        yield s\n")
        self.assertEqual(comment_guards(unguarded, "count_signals"), [])
        self.assertIsNone(comment_guards(self.GUARDED, "mode_inventory"))


class DeadCodeTest(unittest.TestCase):
    """AC4 — the dead helper and the two unkillable comment guards are gone."""

    def test_worktree_flow_defines_no_pid_alive(self):
        self.assertFalse(defines(_read(WORKTREE_FLOW), "_pid_alive"),
                         "AC4: scripts/worktree-flow.py defines no _pid_alive")

    def test_count_signals_and_mode_inventory_carry_no_comment_guard(self):
        for rel, function in ((CRATE_MAP, "count_signals"), (DEAD_SCAN, "mode_inventory")):
            with self.subTest(function=function):
                self.assertEqual(comment_guards(_read(rel), function), [],
                                 f"AC4: {function} in {rel} carries no // guard")


# ----------------------------------------------------------------- AC5 ----

class LintGateDetectorTest(unittest.TestCase):
    """AC5 — :func:`lint_gate_findings`, both ways on synthetic text, each element alone."""

    def test_the_conforming_text_passes(self):
        self.assertEqual(lint_gate_findings(GOOD_AGENTS), [])

    def test_todays_gate_with_no_lint_step_is_reported_for_every_element(self):
        todays = GOOD_AGENTS.replace(GOOD_LINT_STEP + GOOD_GATE, TODAYS_GATE)
        self.assertEqual(lint_gate_findings(todays),
                         [LINT_FIRST, LINT_BEFORE_GATE, SIX_KEPT, RENUMBERED])

    def test_a_lint_step_after_the_gate_run_is_reported(self):
        late = GOOD_AGENTS.replace(GOOD_LINT_STEP + GOOD_GATE,
                                   TODAYS_GATE + GOOD_LINT_STEP.replace("1. ", "7. "))
        self.assertEqual(lint_gate_findings(late), [LINT_FIRST, LINT_BEFORE_GATE, SIX_KEPT])

    def test_a_lint_step_that_need_not_exit_0_is_reported(self):
        text = GOOD_AGENTS.replace("from the repository root exits 0", "from the repository root")
        self.assertEqual(lint_gate_findings(text), [LINT_FIRST])

    def test_a_reworded_step_is_reported(self):
        text = GOOD_AGENTS.replace("needs the user's explicit approval",
                                   "needs the orchestrator's approval")
        self.assertEqual(lint_gate_findings(text), [SIX_KEPT])

    def test_steps_not_renumbered_after_the_lint_step_are_reported(self):
        text = GOOD_AGENTS.replace(GOOD_GATE, TODAYS_GATE)
        self.assertEqual(lint_gate_findings(text), [RENUMBERED])


class AgentsMdLintGateTest(unittest.TestCase):
    """AC5 — the real ``AGENTS.md``'s pre-merge gate opens with the lint step."""

    def test_the_gate_opens_with_a_ruff_check_step_and_keeps_the_six_steps_after_it(self):
        self.assertEqual(lint_gate_findings(AGENTS_MD.read_text(encoding="utf-8")), [],
                         "AC5 / §S5: the pre-merge gate's lint step")


class LintDocsDetectorTest(unittest.TestCase):
    """AC5 — :func:`lint_docs_findings`, both ways on synthetic text, each element alone."""

    def test_the_conforming_text_passes(self):
        self.assertEqual(lint_docs_findings(GOOD_AGENTS), [])

    def test_each_element_bites_alone(self):
        cases = (
            (RUFF_CHECK_SHOWN, "ruff check                           #", "ruff format --check  #"),
            (UV_INSTALL_SHOWN, "uv tool install ruff ", "pipx install ruff "),
            (ONE_WORKFLOW_KEPT, WORKFLOW, "\n"),
            (TOOL_RUFF_NAMED, "`[tool.ruff]` and ", ""),
            (NO_LINTER_SAID, "Ruff is configured, ", NO_LINTER_SENTENCE),
        )
        for finding, old, new in cases:
            with self.subTest(finding=finding):
                self.assertIn(old, GOOD_AGENTS)
                self.assertEqual(lint_docs_findings(GOOD_AGENTS.replace(old, new)), [finding])

    def test_the_no_linter_sentence_is_found_anywhere_in_either_form(self):
        for said in ("There is **no** linter.", "Nothing is configured (no `[tool.ruff]`)."):
            with self.subTest(said=said):
                self.assertEqual(lint_docs_findings(GOOD_AGENTS + "\n## Other\n\n" + said + "\n"),
                                 [NO_LINTER_SAID])
        self.assertEqual(no_linter_units("No formatter or type checker is configured.\n"), [])


class AgentsMdLintDocsTest(unittest.TestCase):
    """AC5 — the real ``AGENTS.md`` documents the rule set and the lint command."""

    def test_development_commands_and_important_files_name_ruff_and_no_sentence_denies_it(self):
        text = AGENTS_MD.read_text(encoding="utf-8")
        self.assertEqual(lint_docs_findings(text), [],
                         "AC5 / §S5: the lint docs; units saying no linter is configured:\n  "
                         + "\n  ".join(no_linter_units(text)))


if __name__ == "__main__":
    unittest.main()
