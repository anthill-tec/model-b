"""The Python 3.14 floor in Model B's own text and tool scripts (CR-MDB-064 §S5, §S6).

Contract: ``docs/changes/CR-MDB-064-python-floor-3-14.md``. §S1 (the published metadata) is
gated in ``tests/test_package_publishing.py``; §S5's install-guide half in
``tests/test_install_guide.py`` (``InstallGuidePythonInterpreterTest``). This module holds:

- ``AgentsMdPythonFloorTest`` — §S5: ``AGENTS.md`` states Python ≥ 3.14 under Runtime/Tooling,
  has a sentence that the pre-merge gate runs one interpreter, the floor, and its skip list's
  "interpreter without the ``build`` frontend" example names no ``python3.11``.
- ``TomllibFallbackRemovedTest`` — §S6: no ``tomli`` fallback in ``scripts/skill-release-gate.py``;
  no ``tomllib = None`` fallback, and no branch on it, in ``scripts/rust-crate-map.py`` and
  ``scripts/rust-dead-scan.py``. Proved two ways: the source carries no fallback shape
  (``tomllib_fallback_faults``), and a script loaded where ``tomllib`` cannot be imported now
  fails to load instead of degrading.
- ``FloorCommentTest`` — §S6: the comments that described 3.11/3.12 behaviour
  (``hooks-src/scripts/ambient-board-status``, ``tests/test_ambient_manifest_discovery.py``)
  state the behaviour on the floor; ``tests/test_suite_hygiene.py``'s note that ``tomllib`` is
  stdlib names the 3.14 floor.

Every checker is proved on synthetic text first (``*CheckerProofTest``).

Stdlib only.
"""

import ast
import io
import re
import subprocess
import sys
import tokenize
import unittest
from pathlib import Path

from tests._helpers import md_section

REPO_ROOT = Path(__file__).resolve().parent.parent
AGENTS_MD = REPO_ROOT / "AGENTS.md"
SCRIPTS = REPO_ROOT / "scripts"
SUITE_HYGIENE = REPO_ROOT / "tests" / "test_suite_hygiene.py"

PYTHON_FLOOR_MINOR = 14
RUNTIME_HEADING = "## Runtime/Tooling Preferences"
#: §S6 — the tool scripts that carried a ``< 3.11`` import fallback.
TOMLLIB_SCRIPTS = ("skill-release-gate.py", "rust-crate-map.py", "rust-dead-scan.py")
#: §S6 — the files whose comments described 3.11/3.12 behaviour.
FLOOR_COMMENT_FILES = ("hooks-src/scripts/ambient-board-status",
                       "tests/test_ambient_manifest_discovery.py")

_FLOOR_STATEMENT = re.compile(r"Python\s*(?:≥|>=)\s*3\.(\d+)")
_INTERPRETER_NAME = re.compile(r"python3\.(\d+)")
#: A ``3.<minor>`` version token (not part of a longer dotted number such as ``0.3.12`` or a
#: three-part version such as a contract's ``3.0.0``).
_VERSION_TOKEN = re.compile(r"(?<![\d.])3\.(\d{1,2})(?!\d|\.\d)")
_BUILD_FRONTEND_EXAMPLE = "without the `build` frontend"


# ------------------------------------------------------------------ §S5 AGENTS.md ----

def _sentences(text: str) -> list[str]:
    return re.split(r"(?<=[.!?])\s+", " ".join(text.split()))


def agents_md_floor_faults(text: str) -> list[str]:
    """§S5 — what ``AGENTS.md`` must say about the 3.14 floor (empty = conforming)."""
    out = []
    runtime = md_section(text, RUNTIME_HEADING)
    floors = [int(m) for m in _FLOOR_STATEMENT.findall(runtime)]
    if PYTHON_FLOOR_MINOR not in floors:
        out.append("Runtime/Tooling: does not state Python ≥ 3.14")
    out += [f"Runtime/Tooling: states Python ≥ 3.{m}, not the 3.14 floor"
            for m in floors if m != PYTHON_FLOOR_MINOR]
    if not any("pre-merge gate" in s.lower() and "one interpreter" in s.lower()
               and ("floor" in s.lower() or "3.14" in s) for s in _sentences(text)):
        out.append("no sentence says the pre-merge gate runs one interpreter, the floor")
    skip_lines = [line for line in text.splitlines() if _BUILD_FRONTEND_EXAMPLE in line]
    if not skip_lines:
        out.append("the skip list names no interpreter without the `build` frontend")
    for line in skip_lines:
        out += [f"the skip list's `build`-frontend example names python3.{m}, below the floor"
                for m in _INTERPRETER_NAME.findall(line) if int(m) < PYTHON_FLOOR_MINOR]
    return out


_CONFORMING_AGENTS_MD = (
    "# Repository Guidelines\n\n"
    f"{RUNTIME_HEADING}\n\n"
    "- **Python ≥ 3.14** (`tomllib`). Package manager: **uv**.\n\n"
    "## Testing & QA\n\n"
    "- The pre-merge gate runs one interpreter, the 3.14 floor.\n"
    "- **Every skip is an absent `pi` CLI or an interpreter without the `build` frontend.** "
    "An interpreter without the `build` frontend (e.g. a `python3.14` with only the stdlib) "
    "skips the built-wheel checks.\n"
)


class AgentsMdFloorCheckerProofTest(unittest.TestCase):
    """The §S5 ``AGENTS.md`` checker passes conforming text and bites on each fault."""

    def test_conforming_text_passes(self):
        self.assertEqual(agents_md_floor_faults(_CONFORMING_AGENTS_MD), [])

    def test_bites_on_the_3_11_floor(self):
        text = _CONFORMING_AGENTS_MD.replace("Python ≥ 3.14", "Python ≥ 3.11")
        self.assertEqual(agents_md_floor_faults(text), [
            "Runtime/Tooling: does not state Python ≥ 3.14",
            "Runtime/Tooling: states Python ≥ 3.11, not the 3.14 floor",
        ])

    def test_a_floor_outside_runtime_tooling_does_not_count(self):
        text = _CONFORMING_AGENTS_MD.replace("- **Python ≥ 3.14** (`tomllib`). ", "- ").replace(
            "## Testing & QA\n\n", "## Testing & QA\n\n- Python ≥ 3.14.\n")
        self.assertEqual(agents_md_floor_faults(text),
                         ["Runtime/Tooling: does not state Python ≥ 3.14"])

    def test_bites_on_a_missing_pre_merge_sentence(self):
        for broken in ("The pre-merge gate runs every interpreter.",
                       "The regression gate runs one interpreter, the 3.14 floor.",
                       "The pre-merge gate runs one interpreter."):
            with self.subTest(sentence=broken):
                text = _CONFORMING_AGENTS_MD.replace(
                    "The pre-merge gate runs one interpreter, the 3.14 floor.", broken)
                self.assertEqual(agents_md_floor_faults(text), [
                    "no sentence says the pre-merge gate runs one interpreter, the floor"])

    def test_bites_on_python3_11_in_the_skip_example(self):
        text = _CONFORMING_AGENTS_MD.replace("a `python3.14`", "`python3.11`")
        self.assertEqual(agents_md_floor_faults(text), [
            "the skip list's `build`-frontend example names python3.11, below the floor"])

    def test_bites_when_the_skip_example_is_gone(self):
        text = _CONFORMING_AGENTS_MD.replace(" or an interpreter without the `build` frontend", "")
        text = text.replace("An interpreter without the `build` frontend (e.g. a `python3.14` with "
                            "only the stdlib) skips the built-wheel checks.", "")
        self.assertEqual(agents_md_floor_faults(text), [
            "the skip list names no interpreter without the `build` frontend"])


class AgentsMdPythonFloorTest(unittest.TestCase):
    """§S5 — ``AGENTS.md`` states the 3.14 floor."""

    maxDiff = None

    def test_agents_md_states_the_3_14_floor_the_one_interpreter_gate_and_no_python3_11(self):
        self.assertEqual(agents_md_floor_faults(AGENTS_MD.read_text(encoding="utf-8")), [])


# ------------------------------------------------------------- §S6 import fallbacks ----

def _imports(node: ast.AST, name: str) -> bool:
    if isinstance(node, ast.Import):
        return any(a.name == name or a.name.startswith(name + ".") for a in node.names)
    if isinstance(node, ast.ImportFrom):
        return bool(node.module) and node.module.split(".")[0] == name
    return False


def tomllib_fallback_faults(source: str) -> list[str]:
    """§S6 — every ``< 3.11`` fallback shape in ``source``: an import of ``tomli``; an import of
    ``tomllib`` inside a ``try``; an assignment to ``tomllib``; any use of the bare name
    ``tomllib`` other than an attribute access (``tomllib is None``, ``if tomllib``, ``and
    tomllib``) — a branch on it; and no unconditional module-level ``import tomllib``."""
    tree = ast.parse(source)
    found: list[tuple[int, str]] = []
    attribute_bases = {id(n.value) for n in ast.walk(tree)
                       if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name)}
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)) and _imports(node, "tomli"):
            found.append((node.lineno, "imports tomli"))
        if isinstance(node, ast.Try) and any(_imports(n, "tomllib") for n in node.body):
            found.append((node.lineno, "imports tomllib inside a try"))
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "tomllib" for t in node.targets):
            found.append((node.lineno, "assigns tomllib"))
        if (isinstance(node, ast.Name) and node.id == "tomllib"
                and isinstance(node.ctx, ast.Load) and id(node) not in attribute_bases):
            found.append((node.lineno, "branches on tomllib"))
    out = [f"line {line}: {what}" for line, what in sorted(found)]
    if not any(isinstance(n, ast.Import) and any(a.name == "tomllib" and a.asname is None
                                                 for a in n.names) for n in tree.body):
        out.append("no unconditional module-level `import tomllib`")
    return out


_CLEAN_TOMLLIB_SOURCE = (
    "import sys\n"
    "import tomllib\n\n\n"
    "def load(path):\n"
    "    if not path.exists():\n"
    "        return {}\n"
    "    return tomllib.loads(path.read_text())\n"
)


class TomllibFallbackCheckerProofTest(unittest.TestCase):
    """The §S6 fallback checker passes an unconditional ``import tomllib`` and bites on each
    fallback shape the three scripts carried."""

    def test_clean_source_passes(self):
        self.assertEqual(tomllib_fallback_faults(_CLEAN_TOMLLIB_SOURCE), [])

    def test_bites_on_the_tomli_fallback(self):
        source = _CLEAN_TOMLLIB_SOURCE.replace(
            "import tomllib\n",
            "try:\n    import tomllib\nexcept ModuleNotFoundError:\n    import tomli as tomllib\n")
        self.assertEqual(tomllib_fallback_faults(source), [
            "line 2: imports tomllib inside a try",
            "line 5: imports tomli",
            "no unconditional module-level `import tomllib`",
        ])

    def test_bites_on_tomllib_none_and_its_branches(self):
        source = (
            "try:\n    import tomllib\nexcept ImportError:\n    tomllib = None\n\n\n"
            "def a(p):\n    if not p.exists() or tomllib is None:\n        return {}\n"
            "    return tomllib.loads(p.read_text())\n\n\n"
            "def b(p):\n    if p.exists() and tomllib:\n        return tomllib.loads(p.read_text())\n"
        )
        self.assertEqual(tomllib_fallback_faults(source), [
            "line 1: imports tomllib inside a try",
            "line 4: assigns tomllib",
            "line 8: branches on tomllib",
            "line 14: branches on tomllib",
            "no unconditional module-level `import tomllib`",
        ])

    def test_bites_on_a_lone_truthiness_branch(self):
        source = _CLEAN_TOMLLIB_SOURCE.replace("if not path.exists():", "if not tomllib:")
        self.assertEqual(tomllib_fallback_faults(source), ["line 6: branches on tomllib"])


#: Loads a script as a module where ``tomllib`` cannot be imported. ``argv[1]`` = the script;
#: ``argv[2] == "tomli"`` also plants a stand-in ``tomli`` (so a ``tomli`` fallback would load).
_LOAD_WITHOUT_TOMLLIB = (
    "import importlib.util, sys, types\n"
    "sys.modules['tomllib'] = None\n"
    "if sys.argv[2] == 'tomli':\n"
    "    sys.modules['tomli'] = types.ModuleType('tomli')\n"
    "spec = importlib.util.spec_from_file_location('floor_probe', sys.argv[1])\n"
    "spec.loader.exec_module(importlib.util.module_from_spec(spec))\n"
    "print('loaded')\n"
)
_TOMLLIB_IMPORT_ERROR = re.compile(r"(?:ModuleNotFoundError|ImportError): .*tomllib")


class TomllibFallbackRemovedTest(unittest.TestCase):
    """§S6 — the ``< 3.11`` import fallbacks are gone from the three tool scripts."""

    maxDiff = None

    def test_scripts_carry_no_tomli_or_tomllib_none_fallback_or_branch(self):
        for name in TOMLLIB_SCRIPTS:
            with self.subTest(script=name):
                source = (SCRIPTS / name).read_text(encoding="utf-8")
                self.assertEqual(tomllib_fallback_faults(source), [],
                                 f"§S6: scripts/{name} must import tomllib unconditionally")

    def test_a_script_without_tomllib_fails_to_load_instead_of_degrading(self):
        # skill-release-gate.py is loaded with a stand-in `tomli`, so its fallback (were it kept)
        # loads it; the rust scripts' fallback set `tomllib = None` and loaded silently.
        for name, plant in (("skill-release-gate.py", "tomli"),
                            ("rust-crate-map.py", "-"), ("rust-dead-scan.py", "-")):
            with self.subTest(script=name):
                result = subprocess.run(
                    [sys.executable, "-c", _LOAD_WITHOUT_TOMLLIB, str(SCRIPTS / name), plant],
                    capture_output=True, text=True, timeout=30, stdin=subprocess.DEVNULL,
                    cwd=REPO_ROOT,
                )
                self.assertNotIn("loaded", result.stdout,
                                 f"§S6: scripts/{name} loaded without tomllib — a fallback is kept")
                self.assertNotEqual(result.returncode, 0)
                self.assertRegex(result.stderr, _TOMLLIB_IMPORT_ERROR,
                                 f"§S6: scripts/{name} must fail on the tomllib import itself")


# ---------------------------------------------------------------- §S6 comments ----

def _comment_blocks(source: str) -> list[tuple[int, str]]:
    """``(first line, text)`` of each run of comments on consecutive lines."""
    blocks: list[tuple[int, list[str], int]] = []
    for tok in tokenize.generate_tokens(io.StringIO(source).readline):
        if tok.type != tokenize.COMMENT:
            continue
        line = tok.start[0]
        if blocks and blocks[-1][2] == line - 1:
            first, texts, _last = blocks[-1]
            blocks[-1] = (first, [*texts, tok.string], line)
        else:
            blocks.append((line, [tok.string], line))
    return [(first, "\n".join(texts)) for first, texts, _last in blocks]


def floor_comment_faults(source: str, rel: str) -> list[str]:
    """§S6 — no comment of ``source`` names a Python version below the floor, and the comment that
    describes ``is_file`` states its behaviour on the floor (names ``3.14`` or the floor)."""
    out = []
    blocks = _comment_blocks(source)
    for first, text in blocks:
        out += [f"{rel}: comment at line {first} names 3.{m}, below the 3.14 floor"
                for m in _VERSION_TOKEN.findall(text) if int(m) < PYTHON_FLOOR_MINOR]
    described = [(first, text) for first, text in blocks if "is_file" in text]
    if not described:
        out.append(f"{rel}: no comment describes `is_file`")
    out += [f"{rel}: the `is_file` comment at line {first} does not state the behaviour on the "
            "3.14 floor" for first, text in described if "3.14" not in text and "floor" not in text]
    return out


def tomllib_note_faults(source: str) -> list[str]:
    """§S6 — each note saying ``tomllib`` is stdlib names the 3.14 floor and no older version. A
    note writes the name in a double-backtick span, so a test method named after it is no note."""
    lines = [(n, line) for n, line in enumerate(source.splitlines(), 1)
             if "``tomllib``" in line and "stdlib" in line]
    if not lines:
        return ["no note says `tomllib` is stdlib"]
    out = []
    for n, line in lines:
        out += [f"line {n}: the tomllib note names 3.{m}, below the 3.14 floor"
                for m in _VERSION_TOKEN.findall(line) if int(m) < PYTHON_FLOOR_MINOR]
        if "3.14" not in line:
            out.append(f"line {n}: the tomllib note does not name the 3.14 floor")
    return out


class FloorCommentCheckerProofTest(unittest.TestCase):
    """The §S6 comment checkers pass floor-stated text and bite on the 3.11/3.12 wording."""

    GOOD = ("x = 1\n"
            "# os.path.isfile swallows every OSError; so does Path.is_file on the 3.14 floor.\n"
            "y = 2  # unrelated\n")

    def test_floor_stated_comment_passes(self):
        self.assertEqual(floor_comment_faults(self.GOOD, "f"), [])
        self.assertEqual(floor_comment_faults(self.GOOD.replace("3.14 floor", "floor"), "f"), [])

    def test_bites_on_the_3_11_3_12_wording(self):
        old = ("x = 1\n"
               "# os.path.isfile swallows every OSError on every Python version\n"
               "# (Path.is_file raises e.g. PermissionError on 3.11/3.12).\n")
        self.assertEqual(floor_comment_faults(old, "f"), [
            "f: comment at line 2 names 3.11, below the 3.14 floor",
            "f: comment at line 2 names 3.12, below the 3.14 floor",
            "f: the `is_file` comment at line 2 does not state the behaviour on the 3.14 floor",
        ])

    def test_bites_on_3_13_plus_and_python3_11(self):
        old = "# Path.is_file() on 3.13+ swallows it; run under python3.11 to see it bite.\n"
        self.assertEqual(floor_comment_faults(old, "f"), [
            "f: comment at line 1 names 3.13, below the 3.14 floor",
            "f: comment at line 1 names 3.11, below the 3.14 floor",
            "f: the `is_file` comment at line 1 does not state the behaviour on the 3.14 floor",
        ])

    def test_a_dotted_version_that_is_not_python_is_ignored(self):
        text = self.GOOD + "# sandesh 0.3.12 is outdated\n\nz = 3  # Contract 3.0.0: never exits non-zero\n"
        self.assertEqual(floor_comment_faults(text, "f"), [])

    def test_bites_when_the_is_file_comment_is_gone(self):
        self.assertEqual(floor_comment_faults("x = 1  # nothing here\n", "f"),
                         ["f: no comment describes `is_file`"])

    def test_tomllib_note_checker_both_ways(self):
        self.assertEqual(tomllib_note_faults("``tomllib`` IS stdlib on the 3.14 floor\n"), [])
        self.assertEqual(tomllib_note_faults("``tomllib`` IS stdlib on the project's Python ≥3.11)\n"), [
            "line 1: the tomllib note names 3.11, below the 3.14 floor",
            "line 1: the tomllib note does not name the 3.14 floor",
        ])
        self.assertEqual(tomllib_note_faults("nothing\n"), ["no note says `tomllib` is stdlib"])
        method = ("``tomllib`` IS stdlib on the 3.14 floor\n"
                  "    def test_s5_a_sorted_block_with_tomllib_among_the_stdlib_passes(self):\n")
        self.assertEqual(tomllib_note_faults(method), [], "a method name is not a note")


class FloorCommentTest(unittest.TestCase):
    """§S6 — the 3.11/3.12 comments state the floor's behaviour; the suite-hygiene note names
    the 3.14 floor."""

    maxDiff = None

    def test_is_file_comments_state_the_behaviour_on_the_floor(self):
        for rel in FLOOR_COMMENT_FILES:
            with self.subTest(file=rel):
                source = (REPO_ROOT / rel).read_text(encoding="utf-8")
                self.assertEqual(floor_comment_faults(source, rel), [])

    def test_suite_hygiene_tomllib_note_names_the_3_14_floor(self):
        self.assertEqual(tomllib_note_faults(SUITE_HYGIENE.read_text(encoding="utf-8")), [])


if __name__ == "__main__":
    unittest.main()
