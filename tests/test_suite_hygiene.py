"""Test-suite hygiene gates — CR-MDB-032 §S3, §S4, §S5 and §S6.

Contract: ``docs/changes/CR-MDB-032-test-suite-relocation.md``. §S1/§S2 (hermeticity) live in
``tests/test_suite_hermeticity.py``; this module holds the rest of the CR's gates.

Class map:

- ``DuplicateHelperDetectorS3Test`` — §S3 detector fixtures: the duplicate-body scan
  (``_duplicate_module_functions``) bites on two synthetic modules sharing a helper body, and
  ignores what the gate excludes (unittest hooks, methods, a body that differs).
- ``OneCopyOfEachHelperS3Test`` — §S3 gate: no module-level function body appears in two
  modules under ``tests/``.
- ``PiOnlyInstallWritesNothingClaudeShapedS4Test`` — §S4: a REAL Pi-only sandboxed install (the
  ``test_deployed_asset_freshness`` e2e fixture, reused by subclassing) leaves no
  ``<target-root>/.claude`` and no manifest entry under ``.claude/``.
- ``ImportOrderDetectorS5Test`` / ``ImportOrderS5Test`` — §S5: the listed import blocks are sorted
  by the rule below, and the rule's detector bites.
- ``StyleBacklogS5Test`` — §S5: the textual style items with a precise pattern — no
  ``"…".format(…)`` in ``test_client_verb_sweep``, no directly nested ``with`` in
  ``test_installer_correctness``, and no un-chained ``raise`` inside an ``except`` handler in
  ``test_toon_codec`` (B904; added by the orchestrator's dispatch for this cycle).
- ``AgentsMdTestingSectionS6Test`` — §S6: ``AGENTS.md`` Testing & QA tells the truth; with
  CR-MDB-056 §S1, Testing & QA and Development Commands show client commands only (the full suite,
  ``--tests`` for a module and a class, the empty-``HOME`` run, ``--python``).
- ``AgentsMdClientCommandDetectorTest`` — CR-MDB-056 §S1: those client-command checks, proved on
  synthetic text.
- ``NoUnicodeEscapeInCommentsTest`` — CR-MDB-047 (VERIFY F11): no comment the CR wrote carries a
  literal unicode escape — every comment of :data:`CR047_FILES`, and elsewhere each comment block
  naming CR-MDB-047; its detector bites on synthetic text first.
- ``AgentsMdCiWorkflowsDetectorTest`` / ``AgentsMdCiWorkflowsTest`` — CR-MDB-067 §S6, MIGRATED at
  CR-MDB-070 C2 RED (§S6): ``AGENTS.md`` names one workflow, ``release.yml`` — its test job runs the
  suite on every release, hotfix and ``master`` push and every published release, outside agent
  sessions; it rehearses on release and hotfix pushes, creates the release from the ``master`` push
  (recovered by a dispatch on ``master``) and publishes on the release event, every publish gated on
  the tests — names ``ci.yml`` nowhere, and no longer says Model B has no CI test workflow; proved on
  synthetic text first (was: ``ci.yml`` running the suite on ``develop``, release and hotfix pushes
  and pull requests beside ``release.yml``'s rehearsal). That it shows no runner in a code span is
  the raw-runner guard's, not repeated here.
- ``AgentsMdTddCommitDetectorTest`` / ``AgentsMdTddCommitTest`` — CR-MDB-093 §S3 (PRD D5, ruling
  of 2026-10-29): one block of ``AGENTS.md`` § Testing & QA lets RED commit its failing tests on
  their own (:data:`AGENTS_TDD_RULES`), and the file never says "never commit failing tests"
  (:func:`agents_md_tdd_findings`, reusing ``tests.test_agent_definition_rules``' matcher); proved
  on synthetic text first.

§S3 rule (``_duplicate_module_functions``). For every ``tests/*.py`` file, every MODULE-LEVEL
``def``/``async def`` (a direct child of the module body) is keyed by ``ast.dump`` of its body with
a leading docstring removed. A key found in two or more DIFFERENT files is a duplicate, whatever the
functions are named (``_decode`` and ``decode_axi`` with one body are one helper). Excluded:
``setUpModule``, ``tearDownModule``, ``load_tests`` (unittest hooks). Out of scope by decision:
methods and functions nested in another scope — the spec says "module-level function bodies", and
a shared method belongs in a shared base class, which is a different refactor. A body repeated
twice inside ONE file is not a cross-module duplicate. ``tests/_helpers.py`` is scanned like every
other file, so a helper hoisted there and left behind in its old module still fails.

§S5 import-order rule (``_import_order_violations``) — stdlib-only, isort-profile-compatible, applied
to the backlog's listed files only (the whole repo does not pass it today; see the RED report).
The TOP-OF-FILE import block is the run of consecutive ``import``/``from … import`` statements in
the module body, after an optional module docstring. Each statement is in a section:
``0`` ``from __future__``; ``1`` stdlib (top-level name in ``sys.stdlib_module_names`` — so
``tomllib`` IS stdlib on the project's 3.14 floor); ``3`` first-party (``modelb_axi``, ``tests``,
``generator``, or a relative import); ``2`` anything else (third-party). The block is sorted when:

1. every ``import`` statement names exactly one module;
2. statements are in non-decreasing ``(section, kind, module.lower())`` order, ``kind`` being ``0``
   for ``import x`` and ``1`` for ``from x import y`` (plain imports before from-imports within a
   section — isort's default, ``force_sort_within_sections = false``);
3. two consecutive statements of the SAME section have no blank line between them, and two of
   DIFFERENT sections exactly one.

Member order inside ``from x import (a, b)`` is not judged.

Stdlib only.
"""

import ast
import io
import itertools
import re
import sys
import tempfile
import tokenize
import tomllib
import unittest
from pathlib import Path

from tests import test_deployed_asset_freshness as freshness
from tests._helpers import md_section
from tests.test_agent_definition_rules import missing_rules, retired_phrases
from tests.test_board_holds_the_queue import norm_units

REPO_ROOT = Path(__file__).resolve().parent.parent
TESTS_DIR = REPO_ROOT / "tests"
AGENTS_MD = REPO_ROOT / "AGENTS.md"

# ------------------------------------------------------------------ §S3 duplicates ----

#: unittest's module-level hooks: the same one-liner in many modules is not a shared helper.
UNITTEST_HOOKS = frozenset({"setUpModule", "tearDownModule", "load_tests"})


def _body_key(func: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    """``ast.dump`` of ``func``'s body with a leading docstring dropped (an all-docstring body is
    kept whole, so two unrelated stubs are not merged)."""
    body = list(func.body)
    first = body[0] if body else None
    if (len(body) > 1 and isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant)
            and isinstance(first.value.value, str)):
        body = body[1:]
    return ast.dump(ast.Module(body=body, type_ignores=[]))


def _duplicate_module_functions(tests_root: Path) -> dict:
    """``{(names, ...): (files, ...)}`` for every module-level function body found in two or more
    ``*.py`` files directly under ``tests_root``. Both tuples are sorted; see the module
    docstring for the rule."""
    seen: dict = {}
    for path in sorted(tests_root.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in tree.body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if node.name in UNITTEST_HOOKS:
                continue
            seen.setdefault(_body_key(node), set()).add((node.name, path.name))
    duplicates = {}
    for owners in seen.values():
        files = tuple(sorted({file for _, file in owners}))
        if len(files) > 1:
            duplicates[tuple(sorted({name for name, _ in owners}))] = files
    return duplicates


def _write_modules(root: Path, modules: dict) -> None:
    for name, text in modules.items():
        (root / name).write_text(text, encoding="utf-8")


class DuplicateHelperDetectorS3Test(unittest.TestCase):
    """§S3 — the duplicate-body scan bites on synthetic modules, and only where it should."""

    HELPER_A = (
        '"""Module a."""\n'
        "from pathlib import Path\n\n\n"
        "def _slurp(path):\n"
        '    """Read it (module a\'s wording)."""\n'
        '    return Path(path).read_text(encoding="utf-8")\n'
    )
    #: The same body under another name and another docstring.
    HELPER_B = (
        '"""Module b."""\n'
        "from pathlib import Path\n\n\n"
        "def _read_text(path):\n"
        '    """Different docstring, same body."""\n'
        '    return Path(path).read_text(encoding="utf-8")\n'
    )

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="mdb-032-dup-")
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_s3_one_body_in_two_modules_is_reported_with_both_names_and_both_modules(self):
        _write_modules(self.root, {"test_a.py": self.HELPER_A, "test_b.py": self.HELPER_B})
        self.assertEqual(
            _duplicate_module_functions(self.root),
            {("_read_text", "_slurp"): ("test_a.py", "test_b.py")},
            "§S3 detector: one helper body in two modules (docstrings and names differ) must be "
            "reported exactly once, naming both functions and both modules",
        )

    def test_s3_a_helper_shared_through_the_helpers_module_is_still_a_duplicate(self):
        _write_modules(self.root, {"_helpers.py": self.HELPER_A, "test_b.py": self.HELPER_B})
        self.assertEqual(
            _duplicate_module_functions(self.root),
            {("_read_text", "_slurp"): ("_helpers.py", "test_b.py")},
            "§S3 detector: a helper hoisted into _helpers.py but left behind in a module is "
            "still two copies",
        )

    def test_s3_different_bodies_are_not_reported(self):
        other = self.HELPER_B.replace('encoding="utf-8"', 'encoding="latin-1"')
        _write_modules(self.root, {"test_a.py": self.HELPER_A, "test_b.py": other})
        self.assertEqual(_duplicate_module_functions(self.root), {},
                         "§S3 detector: bodies that differ are not duplicates")

    def test_s3_unittest_hooks_are_excluded(self):
        hooks = (
            "import unittest\n\n\n"
            "def setUpModule():\n    unittest.installHandler()\n\n\n"
            "def tearDownModule():\n    unittest.removeHandler()\n\n\n"
            "def load_tests(loader, tests, pattern):\n    return tests\n"
        )
        _write_modules(self.root, {"test_a.py": hooks, "test_b.py": hooks})
        self.assertEqual(_duplicate_module_functions(self.root), {},
                         "§S3 detector: setUpModule/tearDownModule/load_tests are excluded")

    def test_s3_methods_and_nested_functions_are_out_of_scope(self):
        shared_method = (
            "import unittest\n\n\n"
            "class ThingTest(unittest.TestCase):\n"
            "    def _helper(self):\n        return 42\n\n"
            "    def test_it(self):\n"
            "        def inner():\n            return 7\n"
            "        self.assertEqual(self._helper() + inner(), 49)\n"
        )
        _write_modules(self.root, {"test_a.py": shared_method, "test_b.py": shared_method})
        self.assertEqual(_duplicate_module_functions(self.root), {},
                         "§S3 detector: only module-level functions are compared")

    def test_s3_a_body_repeated_inside_one_module_is_not_a_cross_module_duplicate(self):
        twice = self.HELPER_A + "\n\ndef _slurp_again(path):\n" \
            '    return Path(path).read_text(encoding="utf-8")\n'
        _write_modules(self.root, {"test_a.py": twice, "test_b.py": '"""Nothing shared."""\n'})
        self.assertEqual(_duplicate_module_functions(self.root), {},
                         "§S3 detector: the gate is cross-module")


class OneCopyOfEachHelperS3Test(unittest.TestCase):
    """§S3 — no module-level function body appears in two modules under ``tests/``."""

    def test_s3_no_module_level_function_body_is_duplicated_across_test_modules(self):
        duplicates = _duplicate_module_functions(TESTS_DIR)
        listing = "\n".join(
            f"  {' / '.join(names)} -> {', '.join(files)}"
            for names, files in sorted(duplicates.items())
        )
        self.assertEqual(
            duplicates, {},
            f"§S3: {len(duplicates)} helper bodies are defined in more than one tests/ module — "
            f"move each to tests/_helpers.py and import it:\n{listing}",
        )


# ------------------------------------------------------------------ §S4 Pi-only ----

class PiOnlyInstallWritesNothingClaudeShapedS4Test(freshness._InstalledMachineCase):
    """§S4 — the existing Pi-only sandboxed install e2e (``--harnesses pi --stacks bun`` into a
    sandbox ``--target-root``, ``HOME``/``PATH``/``MODELB_HOME``/``XDG_DATA_HOME``/
    ``PI_CODING_AGENT_DIR`` all pinned by the fixture) writes nothing under
    ``<target-root>/.claude/``."""

    ROOT_PREFIX = "mdb-032-pi-only-"

    def test_s4_pi_only_install_creates_no_claude_directory_under_the_target_root(self):
        # Preconditions: the install ran, for Pi only, and deployed into this target root.
        self.assertEqual(self.load_install()["install"]["harnesses"], ["pi"],
                         "fixture: the install must be recorded for pi only")
        self.assertTrue((self.target_root / freshness.SKILL_REL).is_file(),
                        f"fixture: the Pi-only install must deploy {freshness.SKILL_REL}")
        claude_dir = self.target_root / ".claude"
        self.assertFalse(
            claude_dir.exists() or claude_dir.is_symlink(),
            f"§S4: a Pi-only install must write nothing under <target-root>/.claude/; found "
            f"{sorted(p.relative_to(self.target_root).as_posix() for p in claude_dir.rglob('*'))!r}"
            if claude_dir.is_dir() else f"§S4: {claude_dir} exists after a Pi-only install",
        )
        claude_shaped = sorted(
            p.relative_to(self.target_root).as_posix() for p in self.target_root.rglob("*")
            if ".claude" in p.relative_to(self.target_root).parts
        )
        self.assertEqual(claude_shaped, [],
                         "§S4: no path anywhere under the target root may pass through .claude")

    def test_s4_pi_only_install_records_no_manifest_entry_under_claude(self):
        paths = self.manifest_paths()
        self.assertIn(freshness.SKILL_REL, paths,
                      "fixture: the manifest must list the deployed Pi-side skill")
        self.assertEqual([p for p in paths if p.split("/", 1)[0] == ".claude"], [],
                         "§S4: a Pi-only install's manifest must list nothing under .claude/")


# ------------------------------------------------------------------ §S5 import order ----

FIRST_PARTY = frozenset({"modelb_axi", "tests", "generator"})

#: The backlog's unsorted-import-block files (CR-MDB-032 Context, "Hygiene backlog").
IMPORT_ORDER_FILES = (
    "tests/test_package_publishing.py",
    "tests/test_hooks.py",
    "tests/test_agent_generator.py",
    "tests/test_rust_stack_generator.py",
    "tests/test_installer_correctness.py",
    "tests/test_installer.py",
    "generator/build.py",
)


def _import_section(node: ast.Import | ast.ImportFrom) -> int:
    if isinstance(node, ast.ImportFrom) and node.level:
        return 3
    module = node.module if isinstance(node, ast.ImportFrom) else node.names[0].name
    top = (module or "").split(".")[0]
    if top == "__future__":
        return 0
    if top in sys.stdlib_module_names:
        return 1
    if top in FIRST_PARTY:
        return 3
    return 2


def _import_key(node: ast.Import | ast.ImportFrom) -> tuple:
    module = node.module if isinstance(node, ast.ImportFrom) else node.names[0].name
    kind = 1 if isinstance(node, ast.ImportFrom) else 0
    return (_import_section(node), kind, (module or "").lower())


def _import_order_violations(text: str) -> list:
    """``["<line>: <why>", ...]`` for the top-of-file import block of ``text`` (module docstring
    rule above). Empty when the block is sorted."""
    tree = ast.parse(text)
    lines = text.splitlines()
    body = list(tree.body)
    if (body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)):
        body = body[1:]
    block = []
    for node in body:
        if not isinstance(node, (ast.Import, ast.ImportFrom)):
            break
        block.append(node)
    problems = []
    for node in block:
        if isinstance(node, ast.Import) and len(node.names) != 1:
            problems.append(f"{node.lineno}: one module per import statement")
    for prev, node in itertools.pairwise(block):
        if _import_key(node) < _import_key(prev):
            problems.append(f"{node.lineno}: {lines[node.lineno - 1].strip()!r} sorts before "
                            f"{lines[prev.lineno - 1].strip()!r}")
        blanks = sum(1 for line in lines[prev.end_lineno:node.lineno - 1] if not line.strip())
        same = _import_section(node) == _import_section(prev)
        if same and blanks:
            problems.append(f"{node.lineno}: blank line inside one import section")
        if not same and blanks != 1:
            problems.append(f"{node.lineno}: {blanks} blank lines between import sections "
                            "(want exactly 1)")
    return problems


class ImportOrderDetectorS5Test(unittest.TestCase):
    """§S5 — the import-order rule's detector: it bites on each defect shape, and passes a sorted
    block (including ``tomllib`` among the stdlib, on the project's 3.14 floor)."""

    SORTED = (
        '"""Doc."""\n\n'
        "from __future__ import annotations\n\n"
        "import importlib.util\n"
        "import os\n"
        "import tomllib\n"
        "import unittest\n"
        "from pathlib import Path\n"
        "from unittest import mock\n\n"
        "from modelb_axi.harness import HARNESS_ROSTER_IDS\n"
        "from tests.pi_capability_sandbox import make_home\n\n"
        "X = 1\n"
    )

    def test_s5_a_sorted_block_with_tomllib_among_the_stdlib_passes(self):
        self.assertEqual(_import_order_violations(self.SORTED), [])

    def test_s5_out_of_order_statements_are_reported(self):
        text = self.SORTED.replace("import os\nimport tomllib\n", "import tomllib\nimport os\n")
        self.assertEqual(_import_order_violations(text),
                         ["7: 'import os' sorts before 'import tomllib'"])

    def test_s5_a_blank_line_inside_a_section_is_reported(self):
        text = self.SORTED.replace("import unittest\nfrom pathlib", "import unittest\n\nfrom pathlib")
        self.assertEqual(_import_order_violations(text),
                         ["10: blank line inside one import section"])

    def test_s5_first_party_split_into_two_misordered_groups_is_reported(self):
        text = self.SORTED.replace(
            "from modelb_axi.harness import HARNESS_ROSTER_IDS\n"
            "from tests.pi_capability_sandbox import make_home\n",
            "from tests.pi_capability_sandbox import make_home\n\n"
            "from modelb_axi.harness import HARNESS_ROSTER_IDS\n",
        )
        self.assertEqual(
            _import_order_violations(text),
            ["14: 'from modelb_axi.harness import HARNESS_ROSTER_IDS' sorts before "
             "'from tests.pi_capability_sandbox import make_home'",
             "14: blank line inside one import section"],
        )

    def test_s5_a_multi_module_import_statement_is_reported(self):
        text = self.SORTED.replace("import os\n", "import os, re\n")
        self.assertEqual(_import_order_violations(text),
                         ["6: one module per import statement"])


class ImportOrderS5Test(unittest.TestCase):
    """§S5 — every import block the backlog lists is sorted by the module-docstring rule."""

    def test_s5_listed_import_blocks_are_sorted(self):
        violations = {}
        for rel in IMPORT_ORDER_FILES:
            problems = _import_order_violations((REPO_ROOT / rel).read_text(encoding="utf-8"))
            if problems:
                violations[rel] = problems
        listing = "\n".join(f"  {rel}:{p}" for rel, ps in violations.items() for p in ps)
        self.assertEqual(violations, {},
                         "§S5: unsorted top-of-file import blocks (rule in this module's "
                         f"docstring):\n{listing}")


# ------------------------------------------------------------------ §S5 style ----

def _module_tree(rel: str) -> ast.AST:
    path = REPO_ROOT / rel
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _unchained_raises_in_handlers(tree: ast.AST) -> list:
    """Line numbers of ``raise <new exception>`` without ``from`` directly inside an ``except``
    handler (nested function/class scopes excluded). A bare ``raise`` and a re-raise of the
    handler's own name are fine."""
    found = []

    def visit(node, handler):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)):
                visit(child, None)
                continue
            if isinstance(child, ast.ExceptHandler):
                visit(child, child)
                continue
            if (isinstance(child, ast.Raise) and handler is not None and child.exc is not None
                    and child.cause is None
                    and not (isinstance(child.exc, ast.Name) and child.exc.id == handler.name)):
                found.append(child.lineno)
            visit(child, handler)

    visit(tree, None)
    return sorted(found)


class StyleBacklogS5Test(unittest.TestCase):
    """§S5 — the style items with a precise textual pattern. No behaviour change is implied: each
    fix is a spelling of the same statement."""

    def test_s5_client_verb_sweep_uses_no_str_format_on_a_literal(self):
        tree = _module_tree("tests/test_client_verb_sweep.py")
        sites = sorted(
            node.lineno for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and node.func.attr == "format"
            and isinstance(node.func.value, (ast.Constant, ast.JoinedStr))
        )
        self.assertEqual(sites, [], "§S5: replace '...'.format(...) with an f-string")

    def test_s5_installer_correctness_has_no_directly_nested_with(self):
        tree = _module_tree("tests/test_installer_correctness.py")
        sites = sorted(
            node.lineno for node in ast.walk(tree)
            if isinstance(node, (ast.With, ast.AsyncWith)) and len(node.body) == 1
            and isinstance(node.body[0], (ast.With, ast.AsyncWith))
        )
        self.assertEqual(sites, [],
                         "§S5: a `with` whose whole body is another `with` becomes one `with a, b:`")

    def test_s5_toon_codec_chains_every_exception_raised_inside_an_except_handler(self):
        sites = _unchained_raises_in_handlers(_module_tree("tests/test_toon_codec.py"))
        self.assertEqual(sites, [],
                         "§S5 (B904): `raise X(...)` inside `except ... as exc:` needs `from exc`")

    def test_s5_unchained_raise_detector_bites_and_spares_chained_and_bare_raises(self):
        text = (
            "def f():\n"
            "    try:\n        pass\n"
            "    except ValueError as exc:\n"
            "        raise AssertionError('x')\n"            # line 5 — bites
            "    try:\n        pass\n"
            "    except ValueError as exc:\n"
            "        raise AssertionError('x') from exc\n"
            "    try:\n        pass\n"
            "    except ValueError as exc:\n"
            "        raise\n"
            "    try:\n        pass\n"
            "    except ValueError as exc:\n"
            "        raise exc\n"
            "    raise RuntimeError('outside any handler')\n"
        )
        self.assertEqual(_unchained_raises_in_handlers(ast.parse(text)), [5])


# ------------------------------------------------------- CR-MDB-047 comment escapes ----

#: A literal ``\uXXXX`` escape: inside a comment it is never decoded, so the
#: reader sees six characters instead of ``§`` or ``—``.
UNICODE_ESCAPE = re.compile(r"\\u[0-9a-fA-F]{4}")
#: The files CR-MDB-047's comments live in whole (VERIFY F11 names the
#: first and the fourth); in every other module a comment block is gated when
#: one of its lines names CR-MDB-047.
CR047_FILES = (
    "modelb_axi/scaffold.py", "modelb_axi/requirements.py", "modelb_axi/preflight.py",
    "tests/test_pi_package.py", "tests/test_init_sandesh_address_and_envrc.py",
    "tests/test_installer_sandesh_requirements.py",
)


def _comment_blocks(text: str) -> list:
    """``[[(line, comment), ...], ...]``: each run of comment tokens on
    consecutive lines is one block."""
    blocks: list = []
    for tok in tokenize.generate_tokens(io.StringIO(text).readline):
        if tok.type != tokenize.COMMENT:
            continue
        line = tok.start[0]
        if blocks and blocks[-1][-1][0] == line - 1:
            blocks[-1].append((line, tok.string))
        else:
            blocks.append([(line, tok.string)])
    return blocks


def _escaped_comments(text: str, *, whole: bool) -> list:
    """Lines of the comments in ``text`` that carry a literal unicode
    escape: every comment when ``whole``, else only blocks naming CR-MDB-047."""
    return [line for block in _comment_blocks(text)
            if whole or any("CR-MDB-047" in c for _, c in block)
            for line, comment in block if UNICODE_ESCAPE.search(comment)]


class NoUnicodeEscapeInCommentsTest(unittest.TestCase):
    """CR-MDB-047 AC "Docs and contract" (VERIFY F11): no source comment the
    CR wrote carries a literal unicode escape."""

    def test_no_cr047_comment_carries_a_literal_unicode_escape(self):
        hits = []
        for path in sorted([*(REPO_ROOT / "modelb_axi").glob("*.py"), *TESTS_DIR.glob("*.py")]):
            rel = path.relative_to(REPO_ROOT).as_posix()
            lines = _escaped_comments(path.read_text(encoding="utf-8"), whole=rel in CR047_FILES)
            hits += [f"{rel}:{n}" for n in lines]
        self.assertEqual(hits, [], "write the character itself (§, —) in a comment")

    def test_escape_detector_bites_on_comments_and_spares_strings(self):
        esc = "\\" + "u00a7"
        text = (
            f"x = '{esc}S1'  # plain\n"
            f"# CR-MDB-045 {esc}S1: the start of a block\n"
            "# ... that CR-MDB-047 continues\n"
            "\n"
            f"# CR-MDB-045 {esc}S2: a block of its own\n"
        )
        self.assertEqual(_escaped_comments(text, whole=False), [2])
        self.assertEqual(_escaped_comments(text, whole=True), [2, 5])


# ------------------------------------------------------------------ §S6 AGENTS.md ----

def _testing_section(text: str) -> str:
    match = re.search(r"^## Testing & QA\n(.*?)(?=^## |\Z)", text, re.S | re.M)
    return match.group(1) if match else ""


#: ``<N> modules`` / ``<N> `unittest` modules`` / ``<N> test modules`` — not ``wave-1/2 modules``.
MODULE_COUNT = re.compile(r"(?<![\d/.\-])\b(\d+)\s+(?:`?unittest`?\s+|test\s+)?modules\b")
#: ``<N> tests, <F> failures, <S> skips`` (singular or plural; commas or slashes).
BASELINE = re.compile(r"(\d+)\s+tests?\W+(\d+)\s+failures?\W+(?:(\d+)\s+errors?\W+)?(\d+)\s+skips?")
#: Figures AGENTS.md stated before CR-MDB-032; each matches only as a whole
#: number, so a current figure containing one (``1359 tests``) is not stale.
STALE_FIGURES = ("19 modules", "19 `unittest` modules", "359 tests")


def _stale_figures(text: str) -> list[str]:
    """The :data:`STALE_FIGURES` ``text`` states, each matched as a whole
    number (no digit before it)."""
    return [s for s in STALE_FIGURES if re.search(rf"(?<!\d){re.escape(s)}", text)]


# CR-MDB-056 §S1 — AGENTS.md's Testing and Development Commands show client commands only.

#: A test run through Model B's client.
CLIENT_TEST_RUN = re.compile(r"python-crucible\.py\s+(?:test|regression|pre-merge-gate)\b")
#: A command line that runs tests at all — through the client or not.
TEST_RUN_COMMAND = re.compile(
    r"-crucible\.py\s+(?:test|regression|pre-merge-gate)\b|-m\s+(?:unittest|pytest|xmlrunner)\b"
    r"|(?:^|[\s/])py\.?test\b|\bdiscover\b")
#: A runner invoked itself in a code span (only this section's runner: unittest, pytest, xmlrunner).
RAW_RUN_SPAN = re.compile(r"(?:^|\s)-m\s+(?:unittest|pytest|xmlrunner)\b|^(?:\S*/)?py\.?test\b")
#: A whole-word prohibition earlier in the sentence governs a span.
PROHIBITION = re.compile(r"\b(?:never|not)\b", re.IGNORECASE)
#: ``--tests tests.test_x`` (a module) and ``--tests tests.test_x.SomeTest`` (a class).
TESTS_MODULE = re.compile(r"--tests\s+tests\.test_\w+(?=\s|$)")
TESTS_CLASS = re.compile(r"--tests\s+tests\.test_\w+\.[A-Z]\w*(?=\s|$)")


def _fenced_commands(section: str) -> list[str]:
    """Each command inside the fenced blocks of ``section``: blank and ``#`` comment lines
    dropped, a trailing comment cut, a ``\\`` continuation joined to its next line."""
    commands, fenced, pending = [], False, ""
    for line in section.splitlines():
        if line.lstrip().startswith("```"):
            fenced, pending = not fenced, ""
            continue
        stripped = line.strip()
        if not fenced or not stripped or stripped.startswith("#"):
            continue
        command = " ".join((pending + " " + stripped.split("  #", 1)[0]).split())
        if command.endswith("\\"):
            pending = command[:-1]
            continue
        commands.append(command)
        pending = ""
    return commands


def _raw_test_runs(section: str) -> list[str]:
    """Every test run ``section`` shows outside the client: a fenced command that runs tests
    and is no client run, and a prose code span invoking a runner with no prohibition earlier in
    its sentence."""
    found = [f"fenced: {c}" for c in _fenced_commands(section)
             if TEST_RUN_COMMAND.search(c) and not CLIENT_TEST_RUN.search(c)]
    prose = re.sub(r"^[ \t]*```.*?^[ \t]*```[^\n]*$", " ", section, flags=re.S | re.M)
    for sentence in re.split(r"(?<=[.!?])\s+", " ".join(prose.split())):
        for match in re.finditer(r"`([^`]+)`", sentence):
            if RAW_RUN_SPAN.search(match.group(1)) and not PROHIBITION.search(sentence[: match.start()]):
                found.append(f"prose: {match.group(1)}")
    return found


def _client_runs(section: str) -> list[str]:
    """The fenced commands of ``section`` that run tests through the client."""
    return [c for c in _fenced_commands(section) if CLIENT_TEST_RUN.search(c)]


def _full_suite_runs(section: str) -> list[str]:
    """The client runs of ``section`` over the full suite: ``test`` without ``--tests``, or
    ``regression``."""
    return [c for c in _client_runs(section)
            if re.search(r"python-crucible\.py\s+regression\b", c)
            or (re.search(r"python-crucible\.py\s+test\b", c) and "--tests" not in c)]


class AgentsMdTestingSectionS6Test(unittest.TestCase):
    """§S6 — ``AGENTS.md`` Testing & QA states the real module count, the post-CR baseline for a
    real ``HOME`` and an empty ``HOME``, the skip causes, the naming convention as practised, and
    no ``MODELB_REALHOME_GATE``. Anchors are meaning-bearing numbers and terms, not sentences."""

    @classmethod
    def setUpClass(cls):
        cls.text = AGENTS_MD.read_text(encoding="utf-8")
        cls.section = _testing_section(cls.text)

    def test_s6_the_testing_section_exists(self):
        self.assertTrue(self.section.strip(), "AGENTS.md must keep a '## Testing & QA' section")

    def test_s6_every_module_count_in_agents_md_is_the_real_count(self):
        real = len(list(TESTS_DIR.glob("test_*.py")))
        in_section = [int(n) for n in MODULE_COUNT.findall(self.section)]
        self.assertTrue(in_section, "§S6: Testing & QA must state how many test modules exist")
        everywhere = [int(n) for n in MODULE_COUNT.findall(self.text)]
        self.assertEqual(sorted(set(everywhere)), [real],
                         f"§S6: every module count AGENTS.md states must be the real "
                         f"count of tests/test_*.py ({real}); found {everywhere}")

    def test_s6_baselines_are_stated_for_real_home_and_empty_home_with_zero_failures(self):
        paragraphs = [p for p in re.split(r"\n\s*\n", self.section) if BASELINE.search(p)]
        lines = [line for p in paragraphs for line in p.splitlines() if BASELINE.search(line)]
        shown = [line[:200] for line in lines]
        real = [line for line in lines if re.search(r"real\s+`?HOME`?", line)]
        empty = [line for line in lines if re.search(r"empty\s+`?HOME`?", line)]
        self.assertEqual(len(real), 1,
                         "§S6: exactly one baseline line (`N tests, 0 failures, S skips`) for a "
                         f"real HOME; baseline lines found: {shown}")
        self.assertEqual(len(empty), 1,
                         "§S6: exactly one baseline line for an empty HOME; baseline lines "
                         f"found: {shown}")
        for label, line in (("real HOME", real[0]), ("empty HOME", empty[0])):
            match = BASELINE.search(line)
            assert match is not None  # every line in `lines` matched BASELINE above
            tests, failures, errors, _skips = match.groups()
            self.assertEqual(int(failures), 0, f"§S6: the {label} baseline has 0 failures: {line}")
            self.assertIn(errors, (None, "0"), f"§S6: the {label} baseline has 0 errors: {line}")
            self.assertNotIn(int(tests), (240, 270, 359, 361, 1021),
                             f"§S6: the {label} baseline is a stale pre-CR figure: {line}")

    def test_s6_skip_causes_name_the_crucible_manifest_and_not_the_retired_ones(self):
        self.assertTrue("crucible-clients.json" in self.section,
                        "§S6: the remaining skips are the installed-client reads that skip when "
                        "~/.crucible/crucible-clients.json is absent — say so in Testing & QA")
        stale = [c for c in ("origin tree", "origin directory") if c in self.section]
        self.assertEqual(stale, [],
                         "§S6: these no longer cause a skip (CR-MDB-032 §S1/§S2)")

    def test_s6_naming_convention_as_practised_covers_both_generations(self):
        missing = [label for label, pattern in (
            ("<Topic><Section>Test", r"<Topic><Section>Test"),
            ("test_s<n>_…", r"test_s(?:<n>|\d+)_"),
            ("<Feature>Test", r"<Feature>Test"),
        ) if not re.search(pattern, self.section)]
        self.assertEqual(missing, [], "§S6: the naming convention as practised must name these")

    def test_s6_no_realhome_gate_and_no_deleted_module_is_named(self):
        named = [t for t in ("MODELB_REALHOME_GATE", "test_realhome_supersede") if t in self.text]
        self.assertEqual(named, [], "§S6: AGENTS.md must not mention these")

    def test_s6_no_stale_counts_remain(self):
        stale = _stale_figures(self.text)
        self.assertEqual(stale, [], "§S6: stale figures in AGENTS.md")

    def test_s6_stale_figure_matches_only_as_a_whole_number(self):
        """A figure containing a stale one (``1359 tests``) is not flagged;
        the stale figure alone still is (CR-MDB-040 C3 FIX)."""
        self.assertEqual(_stale_figures("**1359 tests**, 119 modules, 219 `unittest` modules"),
                         [])
        self.assertEqual(_stale_figures("**359 tests**, 19 modules, 19 `unittest` modules"),
                         list(STALE_FIGURES))
        self.assertEqual(_stale_figures("(359 tests)"), ["359 tests"])

    def test_s6_the_crucible_run_command_stays_as_cr_mdb_020_left_it(self):
        self.assertTrue("python-crucible.py regression --coverage" in self.section,
                        "§S6: the canonical Crucible run command stays in Testing & QA")

    # CR-MDB-056 §S1/§S5 — the Testing section's commands are client commands only.

    def test_testing_section_runs_tests_only_through_the_client(self):
        self.assertEqual(_raw_test_runs(self.section), [],
                         "CR-MDB-056 §S1: Testing & QA shows only client commands")
        self.assertTrue(_full_suite_runs(self.section),
                        "CR-MDB-056 §S1: Testing & QA shows the full suite through the client")

    def test_testing_section_runs_a_module_and_a_class_through_the_client_tests_flag(self):
        runs = _client_runs(self.section)
        self.assertTrue([c for c in runs if TESTS_MODULE.search(c)],
                        f"CR-MDB-056 §S1: a module through `--tests`; client runs: {runs}")
        self.assertTrue([c for c in runs if TESTS_CLASS.search(c)],
                        f"CR-MDB-056 §S1: a class through `--tests`; client runs: {runs}")

    def test_testing_section_runs_the_empty_home_suite_through_the_client(self):
        runs = [c for c in _client_runs(self.section) if re.search(r"(?<![\w$])HOME=", c)]
        self.assertTrue(runs, "CR-MDB-056 §S1: the empty-HOME run goes through the client")

    def test_testing_section_runs_another_interpreter_through_the_client_python_flag(self):
        runs = [c for c in _client_runs(self.section) if re.search(r"\s--python\s+\S", c)]
        self.assertTrue(runs, "CR-MDB-056 §S1: another interpreter runs through `--python`")

    def test_development_commands_run_tests_only_through_the_client(self):
        section = md_section(self.text, "## Development Commands")
        self.assertTrue(section, "AGENTS.md keeps a '## Development Commands' section")
        self.assertEqual(_raw_test_runs(section), [],
                         "CR-MDB-056 §S1: Development Commands shows only client commands")
        self.assertTrue(_client_runs(section),
                        "CR-MDB-056 §S1: Development Commands runs the tests through the client")


class AgentsMdClientCommandDetectorTest(unittest.TestCase):
    """CR-MDB-056 §S1 — the AGENTS.md client-command checks, proved on synthetic text."""

    OLD = ("Pure **`unittest`**.\n\n"
           "```bash\n"
           "python3 -m unittest tests.test_hooks                       # one module\n"
           "python3 -m unittest discover -s tests -t .                 # full suite\n"
           "```\n\n"
           "```bash\n"
           "python3 ~/.crucible/clients/python-crucible.py regression --coverage \\\n"
           "  --agent vidushi-mdb --project-dir \"$PWD\"\n"
           "```\n\n"
           "- Baselines for `python3 -m unittest discover -s tests -t .`, measured today.\n"
           "- Never run `python3 -m pytest` here.\n")
    NEW = ("```bash\n"
           "# one module, one class, the full suite\n"
           "python3 ~/.crucible/clients/python-crucible.py test --tests tests.test_hooks --agent A --log /tmp/a.log\n"
           "python3 ~/.crucible/clients/python-crucible.py test --tests tests.test_contracts.ContractsS2Test --agent A\n"
           "python3 ~/.crucible/clients/python-crucible.py test --agent A --log /tmp/full.log\n"
           "env HOME=\"$(mktemp -d)\" PYTHONUSERBASE=\"$HOME/.local\" python3 ~/.crucible/clients/python-crucible.py test --agent A\n"
           "python3 ~/.crucible/clients/python-crucible.py test --python python3.14 --agent A\n"
           "```\n")

    def test_raw_runs_are_found_in_fences_and_ungoverned_prose_spans(self):
        self.assertEqual(_raw_test_runs(self.OLD), [
            "fenced: python3 -m unittest tests.test_hooks",
            "fenced: python3 -m unittest discover -s tests -t .",
            "prose: python3 -m unittest discover -s tests -t .",
        ])

    def test_a_continued_client_command_is_one_client_run(self):
        self.assertEqual(_client_runs(self.OLD), [
            "python3 ~/.crucible/clients/python-crucible.py regression --coverage "
            "--agent vidushi-mdb --project-dir \"$PWD\""])
        self.assertEqual(len(_full_suite_runs(self.OLD)), 1)

    def test_client_commands_only_pass_and_each_anchor_is_found(self):
        self.assertEqual(_raw_test_runs(self.NEW), [])
        runs = _client_runs(self.NEW)
        self.assertEqual(len(runs), 5)
        self.assertEqual(len([c for c in runs if TESTS_MODULE.search(c)]), 1)
        self.assertEqual(len([c for c in runs if TESTS_CLASS.search(c)]), 1)
        self.assertEqual(len(_full_suite_runs(self.NEW)), 3)
        self.assertEqual(len([c for c in runs if re.search(r"(?<![\w$])HOME=", c)]), 1)
        self.assertEqual(len([c for c in runs if re.search(r"\s--python\s+\S", c)]), 1)


# ------------------------------------------------------- CR-MDB-067/070 §S6 AGENTS.md ----

# MIGRATED at CR-MDB-070 C2 RED (§S6): AGENTS.md names one workflow, release.yml, and no ci.yml
# (was AGENTS_CI_WORKFLOW: "ci.yml runs the suite on develop, release and hotfix pushes and pull
# requests, on a clean runner, outside agent sessions"). Every regex of a statement matches ONE
# normalised unit (``tests.test_board_holds_the_queue.norm_units``: backticks and ``*`` dropped,
# lower-cased); the statements may share a unit or take one each.
_EVERY_PUBLISHED_RELEASE = r"\b(?:every|each) published release\b"
_MASTER_PUSH = r"\bmaster push(?:es)?\b|\bpush(?:es)? (?:to|of) master\b"
_RELEASE_OR_HOTFIX_PUSH = (r"\brelease (?:or|and) hotfix (?:branch )?push(?:es)?\b"
                           r"|\bpush(?:es)? (?:to|of) (?:a |every |each )?release (?:or|and) hotfix "
                           r"branch(?:es)?\b")
#: CR-MDB-070 §S6 — one workflow, ``release.yml``.
AGENTS_ONE_WORKFLOW = (r"\b(?:one|a single|the only) workflow\b", r"(?<![\w-])release\.yml\b")
#: …its test job runs the suite on every release, hotfix and ``master`` push and every published
#: release, outside agent sessions.
AGENTS_TEST_JOB = (
    r"\btest job\b", r"\bsuite\b",
    r"\b(?:every|each) release,? hotfix,? (?:and|or) master push(?:es)?\b"
    r"|\b(?:every|each) push(?:es)? (?:to|of) (?:a )?release, hotfix,? (?:and|or) master "
    r"branch(?:es)?\b",
    _EVERY_PUBLISHED_RELEASE, r"\boutside (?:of )?(?:any |an |every )?agent sessions?\b",
)
#: MIGRATED at CR-MDB-070 C2 RED (§S6): it rehearses on release and hotfix pushes (was also
#: ``release.yml`` and "every" in the same unit — the one-workflow unit names the file now).
AGENTS_REHEARSAL = (r"\brehears\w*\b", _RELEASE_OR_HOTFIX_PUSH)
#: …it creates the release from the ``master`` push, recovered by a dispatch on ``master``.
AGENTS_CREATE_RELEASE = (r"\bcreates? the release\b", _MASTER_PUSH, r"\bdispatch\w*\b",
                         r"\bon master\b")
#: …it publishes on the release event.
AGENTS_PUBLISH = (r"\bpublish(?:es)?\b", r"\b(?:on|from) the release event\b")
#: …every publish gated on the tests.
AGENTS_GATED = (r"\b(?:every|each|all) publish(?:es|ing)?\b(?! release)", r"\bgated\b|\bneeds?\b",
                r"\btests?\b|\btest job\b")
#: CR-MDB-070 §S6 — ``ci.yml`` is named nowhere, in any unit, negated or not.
AGENTS_CI_YML = re.compile(r"(?<![\w-])ci\.yml\b")
#: The sentence CR-MDB-067 §S6 retires: "**no** CI test workflow".
#: MIGRATED at CR-MDB-070 C2 RED (§S6): "the only workflow" is dropped — release.yml is again the
#: only workflow (was: ("the only workflow", r"\bthe only workflow\b") beside it).
AGENTS_RETIRED_CI = (
    ("no ci test workflow", re.compile(r"\bno ci (?:test )?workflows?\b")),
)
AGENTS_NO_ONE_WORKFLOW_UNIT = "AGENTS.md: no unit names one workflow, release.yml"
AGENTS_NO_TEST_JOB_UNIT = ("AGENTS.md: no unit names its test job running the suite on every "
                           "release, hotfix and master push and every published release, outside "
                           "agent sessions")
AGENTS_NO_REHEARSAL_UNIT = "AGENTS.md: no unit names the rehearsal on release and hotfix pushes"
AGENTS_NO_CREATE_RELEASE_UNIT = ("AGENTS.md: no unit names the release created from the master "
                                 "push, recovered by a dispatch on master")
AGENTS_NO_PUBLISH_UNIT = "AGENTS.md: no unit names publishing on the release event"
AGENTS_NO_GATED_UNIT = "AGENTS.md: no unit names every publish gated on the tests"
AGENTS_NAMES_CI_YML = "AGENTS.md: names ci.yml"
#: CR-MDB-068 §S8 — the workflow is rendered: one unit says it is rendered and names
#: ``modelb-axi release-workflow`` (a ``re-rendered`` alone does not say it is rendered).
AGENTS_RENDERED = (r"(?<![\w-])rendered\b", r"(?<![\w-])modelb-axi release-workflow(?![\w-])")
AGENTS_NO_RENDERED_UNIT = ("AGENTS.md: no unit names the workflow rendered, re-rendered by "
                           "modelb-axi release-workflow")
#: The statements in report order, each (regexes, its finding).
#: MIGRATED at CR-MDB-068 C3 RED (§S8): the rendered-workflow statement joins them, last.
AGENTS_CI_STATEMENTS = (
    (AGENTS_ONE_WORKFLOW, AGENTS_NO_ONE_WORKFLOW_UNIT),
    (AGENTS_TEST_JOB, AGENTS_NO_TEST_JOB_UNIT),
    (AGENTS_REHEARSAL, AGENTS_NO_REHEARSAL_UNIT),
    (AGENTS_CREATE_RELEASE, AGENTS_NO_CREATE_RELEASE_UNIT),
    (AGENTS_PUBLISH, AGENTS_NO_PUBLISH_UNIT),
    (AGENTS_GATED, AGENTS_NO_GATED_UNIT),
    (AGENTS_RENDERED, AGENTS_NO_RENDERED_UNIT),
)


def agents_md_ci_findings(text: str) -> list[str]:
    """What ``text`` (an ``AGENTS.md``) lacks of CR-MDB-070 §S6 (one workflow, ``release.yml``),
    whether it names ``ci.yml``, and the retired sentence it still carries; ``[]`` when it
    conforms. MIGRATED at CR-MDB-070 C2 RED (§S6): was CR-MDB-067 §S6's ``ci.yml`` unit and
    ``release.yml`` rehearsal unit."""
    units = norm_units(text)
    out = [finding for regexes, finding in AGENTS_CI_STATEMENTS
           if not any(all(re.search(rx, u) for rx in regexes) for u in units)]
    if any(AGENTS_CI_YML.search(u) for u in units):
        out.append(AGENTS_NAMES_CI_YML)
    out += [f"AGENTS.md: still says {label!r}" for label, rx in AGENTS_RETIRED_CI
            if any(rx.search(u) for u in units)]
    return out


class AgentsMdCiWorkflowsDetectorTest(unittest.TestCase):
    """CR-MDB-070 §S6 — :func:`agents_md_ci_findings`, both ways on synthetic text.

    MIGRATED at CR-MDB-070 C2 RED (§S6): GOOD is one workflow, ``release.yml``, and CR-MDB-067's
    two-workflow text is the departure (was: GOOD named ``ci.yml`` and ``release.yml``)."""

    WORKFLOW = "One workflow runs on GitHub, `.github/workflows/release.yml`:\n\n"
    TEST_JOB = ("- its test job runs the suite on every release, hotfix and `master` push and every "
                "published release, outside any agent session;\n")
    REHEARSAL = "- it rehearses the release on release and hotfix pushes;\n"
    CREATE = ("- it creates the release from the `master` push (recovery: dispatch the workflow on "
              "`master`);\n")
    PUBLISH = "- it publishes to PyPI and npm on the release event, every publish gated on the tests;\n"
    # MIGRATED at CR-MDB-068 C3 RED (§S8): the rendered-workflow statement joins GOOD; PUBLISH
    # ends in `;` now that a list item follows it.
    RENDERED = "- the workflow is rendered: `modelb-axi release-workflow` re-renders it.\n"
    GOOD = ("## Development Commands\n\nThere is **no** Makefile and **no** linter.\n\n"
            + WORKFLOW + TEST_JOB + REHEARSAL + CREATE + PUBLISH + RENDERED + "\n## Next\n")
    #: CR-MDB-067's text, as AGENTS.md carries it today.
    TWO_WORKFLOWS = (
        "## Development Commands\n\nThere is **no** Makefile/justfile and **no** linter. Two "
        "workflows run on GitHub:\n\n"
        "- `.github/workflows/ci.yml` runs the unittest suite on every push to `develop`, release "
        "and hotfix branches and on pull requests, on a clean runner, outside any agent session.\n"
        "- `.github/workflows/release.yml` rehearses the release on every release or hotfix push "
        "(the stamped dev version to TestPyPI, the npm dry-run publish, the notes check), and "
        "publishes a pushed release tag to PyPI and npm.\n")
    #: The sentence CR-MDB-067 retired.
    OLD = ("## Development Commands\n\nThere is **no** Makefile/justfile, **no** CI test workflow (the "
           "only workflow is `.github/workflows/release.yml`, which publishes a pushed release tag "
           "to PyPI and npm), and **no** linter.\n")

    def test_the_conforming_text_passes(self):
        self.assertEqual(agents_md_ci_findings(self.GOOD), [])

    def test_the_two_workflow_text_is_reported_for_each_missing_statement_and_ci_yml(self):
        self.assertEqual(agents_md_ci_findings(self.TWO_WORKFLOWS), [
            AGENTS_NO_ONE_WORKFLOW_UNIT, AGENTS_NO_TEST_JOB_UNIT, AGENTS_NO_CREATE_RELEASE_UNIT,
            AGENTS_NO_PUBLISH_UNIT, AGENTS_NO_GATED_UNIT, AGENTS_NO_RENDERED_UNIT,
            AGENTS_NAMES_CI_YML])

    def test_ci_yml_is_named_nowhere_even_negated(self):
        for named in ("\nThe old `.github/workflows/ci.yml` is deleted.\n",
                      "\nThere is no `ci.yml`.\n"):
            with self.subTest(named=named):
                self.assertEqual(agents_md_ci_findings(self.GOOD + named), [AGENTS_NAMES_CI_YML])
        self.assertEqual(agents_md_ci_findings(self.GOOD + "\nThe `pci.yml` file is other.\n"), [],
                         "a longer name is not ci.yml")

    def test_no_ci_test_workflow_stays_retired_and_the_only_workflow_is_allowed_again(self):
        self.assertEqual(AGENTS_RETIRED_CI[0][0], "no ci test workflow")
        self.assertEqual([label for label, _ in AGENTS_RETIRED_CI], ["no ci test workflow"])
        self.assertEqual(agents_md_ci_findings(self.OLD), [
            AGENTS_NO_TEST_JOB_UNIT, AGENTS_NO_REHEARSAL_UNIT, AGENTS_NO_CREATE_RELEASE_UNIT,
            AGENTS_NO_PUBLISH_UNIT, AGENTS_NO_GATED_UNIT, AGENTS_NO_RENDERED_UNIT,
            "AGENTS.md: still says 'no ci test workflow'"])
        self.assertEqual(agents_md_ci_findings(self.GOOD + "\n" + self.OLD),
                         ["AGENTS.md: still says 'no ci test workflow'"],
                         "the new text beside the retired sentence does not excuse it")
        self.assertEqual(agents_md_ci_findings(self.GOOD.replace(
            "One workflow runs on GitHub,", "The only workflow is")), [],
            "'the only workflow' is no longer a finding")

    def test_each_element_of_each_statement_bites_alone(self):
        cases = (
            (AGENTS_NO_ONE_WORKFLOW_UNIT, (("One workflow runs", "Workflows run"),
                                           ("workflows/release.yml", "workflows/publish.yml"))),
            (AGENTS_NO_TEST_JOB_UNIT, (("its test job runs", "it runs"),
                                       ("runs the suite on", "runs a lint on"),
                                       ("on every release, hotfix", "on a release, hotfix"),
                                       ("every release, hotfix and", "every hotfix and"),
                                       ("release, hotfix and `master`", "release and `master`"),
                                       (" and `master` push and", " push and"),
                                       (" and every published release", ""),
                                       (", outside any agent session", ""))),
            (AGENTS_NO_REHEARSAL_UNIT, (("rehearses the release", "builds the release"),
                                        ("on release and hotfix pushes", "on a tag push"))),
            (AGENTS_NO_CREATE_RELEASE_UNIT, (("creates the release", "drafts the notes"),
                                             ("from the `master` push", "from the tag push"),
                                             ("recovery: dispatch the workflow on `master`",
                                              "recovery: a re-run"),
                                             ("dispatch the workflow on `master`",
                                              "dispatch the workflow"))),
            (AGENTS_NO_PUBLISH_UNIT, (("on the release event", "on a tag push"),)),
            (AGENTS_NO_GATED_UNIT, ((", every publish gated on the tests", ""),
                                    ("every publish gated", "it is gated"),
                                    ("gated on the tests", "after the build"))),
            (AGENTS_NO_RENDERED_UNIT, (("workflow is rendered:", "workflow is hand-written:"),
                                       ("`modelb-axi release-workflow` re-renders it",
                                        "`modelb-axi agents` re-renders it"),
                                       ("is rendered: `modelb-axi release-workflow` re-renders",
                                        "is re-rendered by `modelb-axi release-workflow`, which "
                                        "re-renders"))),
        )
        good = self.GOOD
        for finding, edits in cases:
            for old, new in edits:
                with self.subTest(finding=finding, removed=old):
                    self.assertEqual(good.count(old), 1, old)
                    self.assertEqual(agents_md_ci_findings(good.replace(old, new)), [finding])
        self.assertEqual(agents_md_ci_findings(self.GOOD.replace(
            "on release and hotfix pushes", "on every push to a release or hotfix branch")), [],
            "'every push to a release or hotfix branch' reads the same")
        self.assertEqual(agents_md_ci_findings(self.GOOD.replace(
            "from the `master` push", "from each push to `master`")), [],
            "'push to master' reads the same as 'master push'")

    def test_elements_split_across_two_units_do_not_count(self):
        split = self.GOOD.replace(", outside any agent session;\n",
                                  ";\n- it runs outside any agent session;\n")
        self.assertEqual(agents_md_ci_findings(split), [AGENTS_NO_TEST_JOB_UNIT])
        recovery = self.GOOD.replace(" (recovery: dispatch the workflow on `master`);\n",
                                     ";\n- recovery: dispatch the workflow on `master`;\n")
        self.assertEqual(agents_md_ci_findings(recovery), [AGENTS_NO_CREATE_RELEASE_UNIT])


class AgentsMdCiWorkflowsTest(unittest.TestCase):
    """CR-MDB-070 §S6 — the real ``AGENTS.md`` names one workflow, ``release.yml``, its test job,
    rehearsal, release from the ``master`` push and publish on the release event, every publish
    gated on the tests; names ``ci.yml`` nowhere; and does not say Model B has no CI test
    workflow."""

    # MIGRATED at CR-MDB-070 C2 RED (§S6): was
    # test_agents_md_names_ci_yml_and_the_release_rehearsal_and_not_no_ci.
    def test_agents_md_names_one_release_workflow_gating_every_publish_and_no_ci_yml(self):
        self.assertEqual(agents_md_ci_findings(AGENTS_MD.read_text(encoding="utf-8")), [])


# ------------------------------------------------ CR-MDB-068 §S8 AGENTS.md asset roots ----

PYPROJECT = REPO_ROOT / "pyproject.toml"
#: A table row of ``## Key Directories``: its first cell, backticks dropped.
_FIRST_CELL = re.compile(r"^\|\s*([^|]*?)\s*\|")


def force_include_roots() -> list[str]:
    """The asset roots ``pyproject.toml`` force-includes into the wheel, in file order — derived,
    never hand-copied (CR-MDB-068 §S8)."""
    with PYPROJECT.open("rb") as fh:
        return list(tomllib.load(fh)["tool"]["hatch"]["build"]["targets"]["wheel"]["force-include"])


def _names_root(unit: str, root: str) -> bool:
    """``root`` as a whole path token of ``unit`` (``root`` or ``root/``, never ``x/root``)."""
    return re.search(r"(?<![\w/-])" + re.escape(root) + r"(?![\w-])", unit) is not None


def agents_md_asset_root_findings(text: str, roots) -> list[str]:
    """CR-MDB-068 §S8: what ``text`` (an ``AGENTS.md``) lacks of the asset ``roots``. The
    force-include list — each unit naming ``force-include`` and at least one root — names
    every root (one finding per root a list misses; one when no unit is a list); the
    ``## Key Directories`` table has a row whose first cell is the root (``root`` or ``root/``)."""
    units = [u for u in norm_units(text) if "force-include" in u
             and any(_names_root(u, root) for root in roots)]
    out = [] if units else ["AGENTS.md: no unit lists the force-include roots"]
    out += [f"AGENTS.md: the force-include list does not name {root}"
            for root in roots if any(not _names_root(u, root) for u in units)]
    cells = {m.group(1).replace("`", "").rstrip("/")
             for line in md_section(text, "## Key Directories").splitlines()
             if (m := _FIRST_CELL.match(line.strip()))}
    out += [f"AGENTS.md: the Key Directories table has no row for {root}/"
            for root in roots if root not in cells]
    return out


class AgentsMdAssetRootsDetectorTest(unittest.TestCase):
    """CR-MDB-068 §S8 — :func:`agents_md_asset_root_findings`, both ways on synthetic text."""

    ROOTS = ("skills-src", "generator", "scripts", "hooks-src", "workflows-src")
    GOOD = (
        "## Key Directories\n\n| Path | Purpose |\n|---|---|\n"
        "| `skills-src/` | skill bundles |\n| `generator/` | agent definitions |\n"
        "| `hooks-src/` | hook scripts |\n| `scripts/` | tool scripts |\n"
        "| `workflows-src/` | the release workflow's parts and scripts |\n"
        "| `tests/` | the suite |\n\n"
        "## Important Files\n\n"
        "- `pyproject.toml` — hatchling; `force-include` maps `skills-src`, `generator`, `scripts`, "
        "`hooks-src`, `workflows-src` into `modelb_axi/_assets/`.\n"
        "- `deploy.default_asset_root()` prefers the packaged assets (wheel force-include).\n\n"
        "## Next\n")

    def test_the_derived_roots_are_pyprojects_five(self):
        self.assertEqual(force_include_roots(), list(self.ROOTS))

    def test_the_conforming_text_passes(self):
        self.assertEqual(agents_md_asset_root_findings(self.GOOD, self.ROOTS), [])

    def test_a_root_missing_from_the_force_include_list_is_a_finding(self):
        dropped = self.GOOD.replace("`hooks-src`, `workflows-src` into", "`hooks-src` into")
        self.assertEqual(agents_md_asset_root_findings(dropped, self.ROOTS),
                         ["AGENTS.md: the force-include list does not name workflows-src"])
        nested = self.GOOD.replace("`hooks-src`, `workflows-src` into",
                                   "`hooks-src`, `hooks-src/workflows-src` into")
        self.assertEqual(agents_md_asset_root_findings(nested, self.ROOTS),
                         ["AGENTS.md: the force-include list does not name workflows-src"],
                         "a path under another root is not the root")
        self.assertEqual(agents_md_asset_root_findings(
            self.GOOD.replace("`force-include` maps", "the wheel maps"), self.ROOTS),
            ["AGENTS.md: no unit lists the force-include roots"],
            "a unit naming force-include and no root is not the list")

    def test_a_root_missing_from_the_key_directories_table_is_a_finding(self):
        dropped = self.GOOD.replace("| `workflows-src/` | the release workflow's parts and scripts |\n",
                                    "")
        self.assertEqual(agents_md_asset_root_findings(dropped, self.ROOTS),
                         ["AGENTS.md: the Key Directories table has no row for workflows-src/"])
        self.assertEqual(agents_md_asset_root_findings(
            dropped.replace("| `tests/` | the suite |",
                            "| `tests/` | the suite, and `workflows-src/` |"), self.ROOTS),
            ["AGENTS.md: the Key Directories table has no row for workflows-src/"],
            "a root named in another row's purpose is not its row")
        moved = dropped.replace("## Next\n", "| `workflows-src/` | parts |\n\n## Next\n")
        self.assertEqual(agents_md_asset_root_findings(moved, self.ROOTS),
                         ["AGENTS.md: the Key Directories table has no row for workflows-src/"],
                         "a row outside ## Key Directories does not count")
        self.assertEqual(agents_md_asset_root_findings(
            self.GOOD.replace("| `workflows-src/` |", "| `workflows-src` |"), self.ROOTS), [],
            "the row may omit the trailing slash")


class AgentsMdAssetRootsTest(unittest.TestCase):
    """CR-MDB-068 §S8 — the real ``AGENTS.md`` names every force-included asset root,
    ``workflows-src/`` included, in its force-include list and its Key Directories table."""

    def test_agents_md_names_every_force_included_root_in_the_list_and_the_table(self):
        self.assertEqual(agents_md_asset_root_findings(AGENTS_MD.read_text(encoding="utf-8"),
                                                       force_include_roots()), [])


# ------------------------------------------------- CR-MDB-071 §S6 AGENTS.md release-check ----

#: CR-MDB-071 §S6 — the sections where ``AGENTS.md`` describes the CLI and its verbs.
AGENTS_CLI_SECTIONS = ("## Project Overview", "## Architecture & Data Flow", "## Key Directories",
                       "## Development Commands")
#: ONE normalised unit of those sections names ``modelb-axi release-check`` and the release
#: readiness it reports.
AGENTS_RELEASE_CHECK = (r"(?<![\w-])modelb-axi release-check(?![\w-])", r"\breadiness\b|\bready\b")
AGENTS_NO_RELEASE_CHECK_UNIT = ("AGENTS.md: no unit where it describes the CLI names modelb-axi "
                                "release-check and the release readiness it reports")


def agents_md_release_check_findings(text: str) -> list[str]:
    """CR-MDB-071 §S6: ``[AGENTS_NO_RELEASE_CHECK_UNIT]`` unless one unit of the
    :data:`AGENTS_CLI_SECTIONS` of ``text`` (an ``AGENTS.md``) matches every regex of
    :data:`AGENTS_RELEASE_CHECK`; ``[]`` when one does."""
    units = [u for heading in AGENTS_CLI_SECTIONS for u in norm_units(md_section(text, heading))]
    if any(all(re.search(rx, u) for rx in AGENTS_RELEASE_CHECK) for u in units):
        return []
    return [AGENTS_NO_RELEASE_CHECK_UNIT]


class AgentsMdReleaseCheckDetectorTest(unittest.TestCase):
    """CR-MDB-071 §S6 — :func:`agents_md_release_check_findings`, both ways on synthetic
    text."""

    OVERVIEW = ("- **`modelb_axi`** — the `modelb-axi` CLI: universal installer + project scaffolder "
                "(`init`), and `modelb-axi release-check`, which reports a project's release "
                "readiness.\n")
    GOOD = ("# Repository Guidelines\n\n## Project Overview\n\n" + OVERVIEW + "\n"
            "## Development Commands\n\n```bash\nmodelb-axi --version\n```\n\n"
            "## Testing & QA\n\nPure unittest.\n")

    def test_the_conforming_text_passes(self):
        self.assertEqual(agents_md_release_check_findings(self.GOOD), [])

    def test_todays_text_without_the_verb_is_a_finding(self):
        todays = self.GOOD.replace(self.OVERVIEW, "- **`modelb_axi`** — the `modelb-axi` CLI: "
                                   "universal installer + project scaffolder (`init`).\n")
        self.assertEqual(agents_md_release_check_findings(todays), [AGENTS_NO_RELEASE_CHECK_UNIT])

    def test_each_element_bites_alone(self):
        for old, new, why in (
                ("`modelb-axi release-check`", "`modelb-axi release-checks`", "a longer verb"),
                ("`modelb-axi release-check`", "`release-check`", "the bare verb is not the command"),
                ("which reports a project's release readiness", "which writes nothing",
                 "what it reports")):
            with self.subTest(why=why):
                self.assertEqual(self.GOOD.count(old), 1, old)
                self.assertEqual(agents_md_release_check_findings(self.GOOD.replace(old, new)),
                                 [AGENTS_NO_RELEASE_CHECK_UNIT])

    def test_the_verb_counts_only_where_agents_md_describes_the_cli(self):
        bare = ("- **`modelb_axi`** — the `modelb-axi` CLI: universal installer + project scaffolder "
                "(`init`).\n")
        moved = self.GOOD.replace(self.OVERVIEW, bare).replace("Pure unittest.\n",
                                                               "Pure unittest.\n\n" + self.OVERVIEW)
        self.assertEqual(agents_md_release_check_findings(moved), [AGENTS_NO_RELEASE_CHECK_UNIT],
                         "Testing & QA does not describe the CLI")
        fenced = self.GOOD.replace(self.OVERVIEW, bare).replace(
            "modelb-axi --version\n",
            "modelb-axi --version\nmodelb-axi release-check   # read-only: the release readiness\n")
        self.assertEqual(agents_md_release_check_findings(fenced), [],
                         "a Development Commands line with its comment counts")
        split = self.GOOD.replace(", which reports a project's release readiness.\n",
                                  ".\n- It reports a project's release readiness.\n")
        self.assertEqual(agents_md_release_check_findings(split), [AGENTS_NO_RELEASE_CHECK_UNIT],
                         "the verb and what it reports split across two units do not count")


class AgentsMdReleaseCheckTest(unittest.TestCase):
    """CR-MDB-071 §S6 — the real ``AGENTS.md`` names ``modelb-axi release-check`` where it
    describes the CLI and its verbs."""

    def test_agents_md_names_modelb_axi_release_check_where_it_describes_the_cli(self):
        self.assertEqual(agents_md_release_check_findings(AGENTS_MD.read_text(encoding="utf-8")), [])


# ------------------------------------------------- CR-MDB-093 §S3 AGENTS.md TDD commits ----

#: CR-MDB-093 §S3 — Testing & QA's TDD bullet: RED commits its failing tests on their own.
AGENTS_TDD_RULES = {
    "TDD is mandatory: RED commits its failing tests on their own (a test-only commit); every other "
    "commit is on a clean build, and nothing stays red past the cycle's GREEN": (
        r"TDD is mandatory", r"test-only", r"clean build", r"past the cycle's GREEN"),
}
#: CR-MDB-093 §S3 — the retired rule, said nowhere in ``AGENTS.md``.
AGENTS_TDD_RETIRED = ("never commit failing tests",)


def agents_md_tdd_findings(text: str) -> list[str]:
    """CR-MDB-093 §S3: ``AGENTS.md`` never says "never commit failing tests", and one block of
    its § Testing & QA carries :data:`AGENTS_TDD_RULES`."""
    problems = [f"retired phrase: {phrase}" for phrase in retired_phrases(text, AGENTS_TDD_RETIRED)]
    return problems + [f"Testing & QA: {name}"
                       for name in missing_rules(_testing_section(text), AGENTS_TDD_RULES)]


_AGENTS_TDD_RULE = f"Testing & QA: {next(iter(AGENTS_TDD_RULES))}"
_AGENTS_TDD_RETIRED_FINDING = "retired phrase: never commit failing tests"


class AgentsMdTddCommitDetectorTest(unittest.TestCase):
    """CR-MDB-093 §S3 — :func:`agents_md_tdd_findings`, both ways on synthetic text."""

    BULLET = ("- TDD is mandatory: RED before GREEN. RED commits its failing tests on their own (a "
              "test-only\n  commit); every other commit is on a clean build with its tests passing, and "
              "nothing stays red\n  past the cycle's GREEN or across a merge.\n")
    GOOD = ("# Repository Guidelines\n\n## Testing & QA\n\nPure unittest.\n\n" + BULLET + "\n"
            "## Workflow Rules\n\n- Solo project.\n")

    def test_the_conforming_text_passes(self):
        self.assertEqual(agents_md_tdd_findings(self.GOOD), [])

    def test_each_pattern_cut_alone_bites(self):
        for old, new, pattern in (
                ("TDD is mandatory", "TDD is required", "TDD is mandatory"),
                ("(a test-only\n  commit)", "(a tests-only\n  commit)", "test-only"),
                ("on a clean build", "on a green build", "clean build"),
                ("past the cycle's GREEN", "past the cycle's end", "past the cycle's GREEN")):
            with self.subTest(pattern=pattern):
                self.assertEqual(self.GOOD.count(old), 1, old)
                self.assertEqual(agents_md_tdd_findings(self.GOOD.replace(old, new)),
                                 [_AGENTS_TDD_RULE])

    def test_never_commit_failing_tests_bites_anywhere_in_the_file(self):
        for added in ("- Never commit **failing** tests.\n", "- RED before GREEN, never commit\n  failing "
                      "tests.\n", "### Never commit failing tests\n"):
            with self.subTest(added=added):
                self.assertEqual(agents_md_tdd_findings(self.GOOD + added),
                                 [_AGENTS_TDD_RETIRED_FINDING])
        todays = self.GOOD.replace(self.BULLET, "- TDD is mandatory: RED before GREEN, never commit "
                                   "failing tests, clean build before every commit.\n")
        self.assertEqual(agents_md_tdd_findings(todays),
                         [_AGENTS_TDD_RETIRED_FINDING, _AGENTS_TDD_RULE])

    def test_the_rule_split_across_two_blocks_or_outside_testing_and_qa_bites(self):
        split = self.GOOD.replace("commit); every other commit", "commit).\n- Every other commit")
        self.assertNotEqual(split, self.GOOD)
        self.assertEqual(agents_md_tdd_findings(split), [_AGENTS_TDD_RULE])
        moved = self.GOOD.replace(self.BULLET, "") + self.BULLET
        self.assertEqual(agents_md_tdd_findings(moved), [_AGENTS_TDD_RULE],
                         "the rule under Workflow Rules is not Testing & QA's")
        self.assertEqual(agents_md_tdd_findings("# Repository Guidelines\n"), [_AGENTS_TDD_RULE])


class AgentsMdTddCommitTest(unittest.TestCase):
    """CR-MDB-093 §S3 — the real ``AGENTS.md`` lets RED commit its failing tests on their own."""

    def test_testing_and_qa_lets_red_commit_its_failing_tests_on_their_own(self):
        self.assertEqual([p for p in agents_md_tdd_findings(AGENTS_MD.read_text(encoding="utf-8"))
                          if p.startswith("Testing & QA: ")], [])

    def test_agents_md_never_says_never_commit_failing_tests(self):
        self.assertEqual(
            retired_phrases(AGENTS_MD.read_text(encoding="utf-8"), AGENTS_TDD_RETIRED), [])


if __name__ == "__main__":
    unittest.main()
