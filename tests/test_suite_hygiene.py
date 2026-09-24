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
- ``AgentsMdTestingSectionS6Test`` — §S6: ``AGENTS.md`` Testing & QA tells the truth.

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
``tomllib`` IS stdlib on the project's Python ≥3.11); ``3`` first-party (``modelb_axi``, ``tests``,
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
import itertools
import re
import sys
import tempfile
import unittest
from pathlib import Path

from tests import test_deployed_asset_freshness as freshness

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
    block (including ``tomllib`` among the stdlib, since the project targets Python ≥3.11)."""

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


# ------------------------------------------------------------------ §S6 AGENTS.md ----

def _testing_section(text: str) -> str:
    match = re.search(r"^## Testing & QA\n(.*?)(?=^## |\Z)", text, re.S | re.M)
    return match.group(1) if match else ""


#: ``<N> modules`` / ``<N> `unittest` modules`` / ``<N> test modules`` — not ``wave-1/2 modules``.
MODULE_COUNT = re.compile(r"(?<![\d/.\-])\b(\d+)\s+(?:`?unittest`?\s+|test\s+)?modules\b")
#: ``<N> tests, <F> failures, <S> skips`` (singular or plural; commas or slashes).
BASELINE = re.compile(r"(\d+)\s+tests?\W+(\d+)\s+failures?\W+(?:(\d+)\s+errors?\W+)?(\d+)\s+skips?")


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
        stale = [s for s in ("19 modules", "19 `unittest` modules", "359 tests") if s in self.text]
        self.assertEqual(stale, [], "§S6: stale figures in AGENTS.md")

    def test_s6_the_crucible_run_command_stays_as_cr_mdb_020_left_it(self):
        self.assertTrue("python-crucible.py regression --coverage" in self.section,
                        "§S6: the canonical Crucible run command stays in Testing & QA")


if __name__ == "__main__":
    unittest.main()
