"""Test-suite hermeticity gates — CR-MDB-032 §S1 and §S2.

Contract: ``docs/changes/CR-MDB-032-test-suite-relocation.md``. The suite is the release gate, so
it must run on any machine: no test reaches a personal Crucible checkout, no test asserts the
user's real home, and the dead or superseded real-home tests are gone.

Class map:

- ``CheckoutLiteralS1Test`` — §S1: no Crucible-checkout path string anywhere under ``tests/``
  (every spelling: the joined path, the ``Path`` segment chain, the absolute ``/home/<user>/``
  form). This module builds every such string from split literals, so the gate covers ``tests/``
  INCLUDING this file with no self-exclusion.
- ``AnchoringCoversTestsS1Test`` — §S1: CR-MDB-020's §S2 anchoring gate
  (``tests.test_client_path_anchoring``) drops ``tests/`` from its exemptions, scans ``tests/``,
  and its exemption assertion no longer pins ``tests/``.
- ``ImportGateExtensionS1Test`` — §S1: CR-MDB-022's AST import gate
  (``tests.test_toon_codec.ToonCodecS2Test.test_s2_no_repo_file_imports_a_module_from_crucible_checkout``)
  is run, unmodified, against throwaway fixture trees by re-pointing its ``REPO_ROOT`` seam. It
  must also catch ``importlib.util.spec_from_file_location`` and subprocess program strings that
  point outside the repo. Two controls prove the harness: a clean tree passes, and the form the
  gate already catches (a literal ``sys.path`` insert) fails.
- ``ManifestResolvedOracleS1Test`` — §S1: the toon oracle and the gate-lock read resolve the
  installed client through ``~/.crucible/crucible-clients.json``; with ``HOME`` pointed at an empty
  directory they SKIP naming that manifest, and with the manifest present they RUN.
- ``DeadOriginTreeTestsS1Test`` — §S1: the two permanently-skipped origin-tree tests are deleted.
- ``RealHomeReadsS2Test`` — §S2: no test module reads the real home outside the reviewed
  ``HOME_READ_ALLOWLIST`` and the one ``INSTALLED_PI_PACKAGE_READS`` entry below (AST scan of
  ``tests/*.py``).
- ``SupersededRealHomeTestsS2Test`` — §S2: ``test_realhome_supersede.py`` and the superseded or
  real-home classes are deleted; ``WorktreeFlowSkillConsumerNotesTest`` stays and reads
  ``skills-src/``.
- ``SandboxedExecutionS2Test`` — §S2: the generator drift test mutates a temp copy, never a tracked
  file; ``test_installer``'s ``python -m modelb_axi`` children run with ``HOME`` and ``PATH`` pinned.

What §S2 counts as a REAL-HOME READ (``_home_reads``). An AST call or subscript, not a string:
``Path.home()``; any ``expanduser`` (``os.path.expanduser(...)`` or ``<path>.expanduser()``); and a
read of the ``HOME`` variable (``os.environ["HOME"]`` in load context, ``os.environ.get("HOME")``,
``os.getenv("HOME")``). A string literal such as ``"~/.agents/scripts/"`` is NOT a read: the suite
asserts shipped TEXT that names those paths, which is repo content, not the user's home. Assigning
``env["HOME"] = <sandbox>`` is sandbox construction and is not a read.

Permitted reads, and ONLY these:

1. The installed Crucible surface §S1 itself mandates — ``Path.home() / ".crucible" / …`` (the
   ``Path.home()`` call is the left operand of ``/ ".crucible"``) or ``expanduser`` of a literal
   starting ``~/.crucible/``. The manifest and the installed clients are the one sanctioned
   out-of-repo dependency (standing rule 2026-09-18).
2. ``HOME_READ_ALLOWLIST`` — ``(file, enclosing scope)`` → the reviewed reason. Each entry uses the
   home path as a STRING (path algebra, or a value that must NOT appear in output) and never stats,
   opens or lists anything under it. ``test_s2_every_allowlist_entry_names_a_live_use`` keeps the
   list from going stale. This is the "reviewed list of remaining ``Path.home()`` uses" the §S2
   acceptance criterion records in the merge note.
3. ``INSTALLED_PI_PACKAGE_READS`` (CR-MDB-039) — ``(file, enclosing scope)`` → the reason. A
   separately named exception, parallel to rule 1 and NOT part of the allowlist (whose "never
   stat, open or list" rule stays true): an installed Pi package's RELEASED source, read-only,
   resolved ``$PI_CODING_AGENT_DIR`` first and then ``~/.pi/agent``; the reading test skips,
   naming the path, when it is absent. It holds exactly one entry — the contract read of the
   installed pi-subagents service key — and the scope must be a function that names both
   ``PI_CODING_AGENT_DIR`` and ``.pi``. A same-named function in another module, or any other
   function in the listed module, is not covered.

§S2's empty-``HOME`` full-suite property is proved by the orchestrator / VERIFY with a full run,
never by a test here that recurses into the whole suite.

Stdlib only.
"""

import ast
import builtins
import importlib
import inspect
import json
import os
import pathlib
import re
import site
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
TESTS_DIR = REPO_ROOT / "tests"
THIS_FILE = Path(__file__).resolve().name

# ------------------------------------------------------------------ §S1 checkout ----

#: Built from split literals so this module never carries the string it forbids.
_CHECKOUT_DIR = "data" + "_projects"
_CHECKOUT_PATH = _CHECKOUT_DIR + "/" + "crucible"
#: A fake user's checkout, for fixtures only.
_FIXTURE_CHECKOUT = "/" + "home/someone/Documents/" + _CHECKOUT_PATH

#: §S1 — every spelling that reaches a personal Crucible checkout: the joined path, the
#: ``"…" / "crucible"`` Path-segment chain (a separator of up to 12 non-word characters), and an
#: absolute path under a user's home ``Documents`` directory that ends in the checkout.
CHECKOUT_PATTERNS = (
    ("checkout-path", re.compile(_CHECKOUT_DIR + r"\W{1,12}crucible")),
    ("home-checkout", re.compile("/" + r"home/[^/\s'\"]+/Documents/[^\s'\"]*crucible")),
)


def _checkout_literal_hits(tests_root: Path) -> list:
    """``[(rel, lineno, kind)]`` for every checkout spelling in any text file under
    ``tests_root`` (``__pycache__`` skipped). ``rel`` is relative to ``tests_root``'s parent."""
    hits = []
    for path in sorted(tests_root.rglob("*")):
        if not path.is_file() or "__pycache__" in path.parts:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        rel = path.relative_to(tests_root.parent).as_posix()
        for lineno, line in enumerate(text.splitlines(), 1):
            for kind, pattern in CHECKOUT_PATTERNS:
                if pattern.search(line):
                    hits.append((rel, lineno, kind))
    return hits


def _write_tree(root: Path, files: dict) -> None:
    for rel, text in files.items():
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")


def _gate_module(name: str):
    """Import a sibling gate module lazily, so a broken sibling fails ONE test, not collection."""
    return importlib.import_module(f"tests.{name}")


class CheckoutLiteralS1Test(unittest.TestCase):
    """§S1 — no literal Crucible-checkout path string in ``tests/``."""

    maxDiff = None

    def test_s1_tests_tree_names_no_crucible_checkout_path(self):
        hits = _checkout_literal_hits(TESTS_DIR)
        self.assertEqual(
            hits, [],
            "§S1: tests/ must name no personal Crucible checkout. Use modelb_axi.toon, resolve "
            "installed clients through ~/.crucible/crucible-clients.json, and build any detector "
            "fixture from split literals. Offenders:\n"
            + "\n".join(f"  {rel}:{n} [{kind}]" for rel, n, kind in hits),
        )

    def test_s1_checkout_detector_flags_each_literal_form(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_tree(root, {
                "tests/joined.py": f'CLIENTS = "~/Documents/{_CHECKOUT_PATH}/clients"\n',
                "tests/segments.py": (
                    "from pathlib import Path\n"
                    f'TOON = Path.home() / "Documents" / "{_CHECKOUT_DIR}" / "crucible" / "toon.py"\n'
                ),
                "tests/absolute.py": f'DIR = "{_FIXTURE_CHECKOUT}/clients"\n',
                "tests/fixtures/note.md": f"see {_FIXTURE_CHECKOUT}\n",
            })
            hits = _checkout_literal_hits(root / "tests")
        self.assertEqual(sorted(hits), sorted([
            ("tests/joined.py", 1, "checkout-path"),
            ("tests/segments.py", 2, "checkout-path"),
            ("tests/absolute.py", 1, "checkout-path"),
            ("tests/absolute.py", 1, "home-checkout"),
            ("tests/fixtures/note.md", 1, "checkout-path"),
            ("tests/fixtures/note.md", 1, "home-checkout"),
        ]))

    def test_s1_checkout_detector_passes_split_literals_and_installed_clients(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_tree(root, {
                "tests/split.py": 'CHECKOUT = "data" + "_projects" + "/" + "crucible"\n',
                "tests/installed.py": 'MANIFEST = "~/.crucible/crucible-clients.json"\n',
                "tests/prose.py": '# the Crucible project owns its clients\n',
            })
            hits = _checkout_literal_hits(root / "tests")
        self.assertEqual(hits, [])


# ------------------------------------------------------------ §S1 anchoring ----


class AnchoringCoversTestsS1Test(unittest.TestCase):
    """§S1 — CR-MDB-020's §S2 anchoring gate covers ``tests/`` with no ``tests/`` exemption."""

    maxDiff = None

    def test_s1_anchoring_gate_exempts_no_tests_prefix(self):
        anchoring = _gate_module("test_client_path_anchoring")
        self.assertNotIn(
            "tests/", anchoring.EXEMPT_PREFIXES,
            "§S1: CR-MDB-020's anchoring gate must drop tests/ from EXEMPT_PREFIXES",
        )
        self.assertEqual(
            anchoring.EXEMPT_PREFIXES, ("archive/", "audits/", "docs/changes/"),
            "§S1: only tests/ is dropped; the dated-record exemptions stay exactly as they are",
        )

    def test_s1_anchoring_gate_scans_a_tests_fixture_by_default(self):
        anchoring = _gate_module("test_client_path_anchoring")
        client = "rust" + "-crucible.py"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_tree(root, {
                "tests/test_x.py": (
                    f'CHECKOUT = "~/Documents/{_CHECKOUT_PATH}/x"\n'
                    f'UNROOTED = "clients/{client}"\n'
                    f'MIRROR = "~/.claude/scripts/{client}"\n'
                    f'ANCHORED = "~/.crucible/clients/{client}"\n'
                ),
            })
            hits = [(rel, n, kind) for rel, n, kind, _ in anchoring._anchoring_hits(root)]
        self.assertEqual(
            hits,
            [("tests/test_x.py", 1, "checkout"),
             ("tests/test_x.py", 2, "unrooted"),
             ("tests/test_x.py", 3, "mirror")],
            "§S1: the anchoring gate, run over its DEFAULT trees, must scan tests/ — a checkout, an "
            "unrooted clients/ path and the retired mirror under tests/ are each one hit; the "
            "installed-client anchor is none",
        )

    def test_s1_exemption_assertion_no_longer_pins_tests_prefix(self):
        anchoring = _gate_module("test_client_path_anchoring")
        method = getattr(anchoring.ClientPathAnchoringS2Test, "test_s2_exemption_list_is_exact", None)
        if method is None:
            self.fail("§S1: the anchoring gate's exemption assertion must be updated, not deleted")
        source = inspect.getsource(method)
        self.assertNotIn(
            '"tests/"', source,
            "§S1: test_s2_exemption_list_is_exact still pins the tests/ exemption",
        )
        self.assertIn('"docs/changes/"', source, "§S1: the remaining exemptions stay asserted")

    def test_s1_tests_tree_carries_no_unanchored_client_path(self):
        anchoring = _gate_module("test_client_path_anchoring")
        kept = tuple(p for p in anchoring.EXEMPT_PREFIXES if p != "tests/")
        with mock.patch.object(anchoring, "EXEMPT_PREFIXES", kept):
            hits = anchoring._anchoring_hits(anchoring.REPO_ROOT, ("tests",))
        self.assertEqual(
            hits, [],
            f"§S1: {len(hits)} anchoring-gate hit(s) under tests/ — detector fixtures must build "
            "checkout, unrooted and mirror paths from split literals:\n" + anchoring._fmt_hits(hits),
        )


# --------------------------------------------------------- §S1 AST import gate ----

IMPORT_GATE_CLASS = "ToonCodecS2Test"
IMPORT_GATE_METHOD = "test_s2_no_repo_file_imports_a_module_from_crucible_checkout"


def _clean_fixture_files(sanctioned: str) -> dict:
    """A tree the extended gate must PASS: a sanctioned installed-client invocation, a
    repo-relative ``spec_from_file_location``, and a subprocess program naming no path."""
    return {
        "tests/invoker.py": (
            "import subprocess\n"
            "import sys\n"
            f"# sanctioned invocation: {sanctioned}\n"
            "def run(client):\n"
            "    return subprocess.run([sys.executable, client, '--help'], check=False)\n"
        ),
        "tests/repo_loader.py": (
            "import importlib.util\n"
            "from pathlib import Path\n"
            "REPO = Path(__file__).resolve().parents[1]\n"
            "SPEC = importlib.util.spec_from_file_location('x', str(REPO / 'scripts' / 'toon.py'))\n"
        ),
        "tests/pathless_child.py": (
            "import subprocess\n"
            "import sys\n"
            "PROGRAM = 'import json, sys\\nsys.stdout.write(json.dumps(sys.argv[1:]))\\n'\n"
            "subprocess.run([sys.executable, '-c', PROGRAM, 'a'], check=False)\n"
        ),
    }


class ImportGateExtensionS1Test(unittest.TestCase):
    """§S1 — the CR-MDB-022 AST gate also catches ``spec_from_file_location`` and subprocess
    program strings pointing outside the repo (negative tests over fixture trees)."""

    maxDiff = None

    def _run_gate_on(self, extra_files: dict) -> unittest.TestResult:
        toon_gate = _gate_module("test_toon_codec")
        files = _clean_fixture_files(toon_gate.SANCTIONED_INVOCATION)
        files.update(extra_files)
        result = unittest.TestResult()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            _write_tree(root, files)
            with mock.patch.object(toon_gate, "REPO_ROOT", root):
                getattr(toon_gate, IMPORT_GATE_CLASS)(IMPORT_GATE_METHOD).run(result)
        self.assertEqual(result.testsRun, 1, "the pinned CR-MDB-022 gate method must run once")
        return result

    def _assert_gate_fails_naming(self, result: unittest.TestResult, rel: str, form: str):
        self.assertEqual(
            [t for t, _ in result.errors], [],
            f"§S1: the import gate must FAIL cleanly on {form}, not error:\n"
            + "\n".join(tb for _, tb in result.errors),
        )
        self.assertEqual(
            len(result.failures), 1,
            f"§S1: the CR-MDB-022 AST gate did not catch {form} — a fixture tree whose only "
            f"out-of-repo load is {rel} passed {IMPORT_GATE_CLASS}.{IMPORT_GATE_METHOD}",
        )
        self.assertIn(rel, result.failures[0][1], f"§S1: the gate's failure must name {rel}")

    def test_s1_import_gate_passes_a_clean_fixture_tree(self):
        result = self._run_gate_on({})
        self.assertTrue(
            result.wasSuccessful(),
            "control: a tree with only sanctioned invocations and repo-relative loads must pass "
            "the import gate:\n" + "\n".join(tb for _, tb in result.failures + result.errors),
        )

    def test_s1_import_gate_still_fails_on_an_out_of_repo_sys_path_insert(self):
        result = self._run_gate_on({
            "tests/path_insert.py": "import sys\nsys.path.insert(0, '/elsewhere/clients')\n",
        })
        self._assert_gate_fails_naming(result, "tests/path_insert.py", "a literal sys.path insert")

    def test_s1_import_gate_fails_on_spec_from_file_location_outside_the_repo(self):
        result = self._run_gate_on({
            "tests/loads_elsewhere.py": (
                "import importlib.util\n"
                "SPEC = importlib.util.spec_from_file_location('x', '/elsewhere/toon.py')\n"
            ),
        })
        self._assert_gate_fails_naming(
            result, "tests/loads_elsewhere.py", "importlib.util.spec_from_file_location('x', '/elsewhere/toon.py')",
        )

    def test_s1_import_gate_fails_on_spec_from_file_location_via_module_constant(self):
        result = self._run_gate_on({
            "tests/loads_via_constant.py": (
                "import importlib.util\n"
                "ELSEWHERE_TOON = '/elsewhere/toon.py'\n"
                "SPEC = importlib.util.spec_from_file_location('x', ELSEWHERE_TOON)\n"
            ),
        })
        self._assert_gate_fails_naming(
            result, "tests/loads_via_constant.py",
            "spec_from_file_location fed by a module-level string constant",
        )

    def test_s1_import_gate_fails_on_a_subprocess_program_naming_a_checkout(self):
        program = f"import sys; sys.path.insert(0, '{_FIXTURE_CHECKOUT}/clients'); import toon"
        result = self._run_gate_on({
            "tests/child_names_checkout.py": (
                "import subprocess\n"
                "import sys\n"
                f"subprocess.run([sys.executable, '-c', {program!r}], check=False)\n"
            ),
        })
        self._assert_gate_fails_naming(
            result, "tests/child_names_checkout.py", "a subprocess program string naming a checkout",
        )


# ------------------------------------------------ §S1 manifest-resolved oracle ----

MANIFEST_REL = ".crucible/crucible-clients.json"
TOON_ORACLE_TEST_IDS = (
    "tests.test_toon_codec.ToonEnvelopeS3Test.test_s3_emitted_wire_form_is_accepted_by_crucibles_port",
    "tests.test_toon_codec.ToonEnvelopeS3Test.test_s3_empty_list_headers_are_left_alone",
)
GATE_LOCK_READ_TEST_ID = (
    "tests.test_tooling_detachment.GateLockContractS5Test."
    "test_s5_both_projects_derive_a_byte_identical_lock_path"
)

#: Executed by a SEPARATE interpreter (cwd = repo root): loads the named tests, runs them, and
#: writes a JSON outcome report to argv[1].
_CHILD_RUNNER = (
    "import json, sys, unittest\n"
    "out, names = sys.argv[1], sys.argv[2:]\n"
    "suite = unittest.defaultTestLoader.loadTestsFromNames(names)\n"
    "result = unittest.TestResult()\n"
    "suite.run(result)\n"
    "report = {'run': result.testsRun,\n"
    "          'skipped': {t.id(): r for t, r in result.skipped},\n"
    "          'failures': {t.id(): tb[-1500:] for t, tb in result.failures},\n"
    "          'errors': {t.id(): tb[-1500:] for t, tb in result.errors}}\n"
    "with open(out, 'w', encoding='utf-8') as fh:\n"
    "    fh.write(json.dumps(report))\n"
)


def _run_tests_in_child(names, env: dict) -> dict:
    with tempfile.TemporaryDirectory(prefix="mdb-hermetic-report-") as tmp:
        report = Path(tmp) / "report.json"
        proc = subprocess.run(
            [sys.executable, "-c", _CHILD_RUNNER, str(report), *names],
            cwd=str(REPO_ROOT), env=env, capture_output=True, text=True, timeout=600,
            stdin=subprocess.DEVNULL,
        )
        if not report.is_file():
            raise AssertionError(
                f"child test runner wrote no report (rc={proc.returncode}): {proc.stderr[-2000:]}"
            )
        return json.loads(report.read_text(encoding="utf-8"))


def _empty_home_env(sandbox: Path) -> dict:
    """The ambient environment with HOME (and every Model B / Pi state root) re-pointed into
    ``sandbox``; the user site-packages stay importable, as in the CR's empty-HOME measurement."""
    home = sandbox / "home"
    home.mkdir()
    env = dict(os.environ)
    env.update({
        "HOME": str(home),
        "MODELB_HOME": str(sandbox / "modelb-home"),
        "XDG_DATA_HOME": str(sandbox / "xdg-data"),
        "PI_CODING_AGENT_DIR": str(sandbox / "pi-agent"),
        "PYTHONUSERBASE": site.getuserbase(),
    })
    return env


class ManifestResolvedOracleS1Test(unittest.TestCase):
    """§S1 — the toon oracle and the gate-lock read skip naming the manifest when it is absent,
    and run when it is present."""

    maxDiff = None

    def _assert_skipped_naming_manifest(self, report: dict, test_ids):
        self.assertEqual(report["failures"], {}, "§S1: nothing may FAIL with an empty HOME")
        self.assertEqual(report["errors"], {}, "§S1: nothing may ERROR with an empty HOME")
        for test_id in test_ids:
            with self.subTest(test=test_id):
                self.assertIn(
                    test_id, report["skipped"],
                    f"§S1: {test_id} must SKIP when {MANIFEST_REL} is absent",
                )
                self.assertIn(
                    MANIFEST_REL, report["skipped"][test_id],
                    f"§S1: the skip reason must name the manifest path {MANIFEST_REL}, got "
                    f"{report['skipped'][test_id]!r}",
                )

    def test_s1_toon_oracle_skips_naming_the_manifest_when_home_is_empty(self):
        with tempfile.TemporaryDirectory(prefix="mdb-empty-home-") as tmp:
            report = _run_tests_in_child(["tests.test_toon_codec"], _empty_home_env(Path(tmp)))
        self.assertGreater(report["run"], len(TOON_ORACLE_TEST_IDS), "the whole module must run")
        self._assert_skipped_naming_manifest(report, TOON_ORACLE_TEST_IDS)

    def test_s1_gate_lock_read_skips_naming_the_manifest_when_home_is_empty(self):
        with tempfile.TemporaryDirectory(prefix="mdb-empty-home-") as tmp:
            report = _run_tests_in_child([GATE_LOCK_READ_TEST_ID], _empty_home_env(Path(tmp)))
        self.assertEqual(report["run"], 1)
        self._assert_skipped_naming_manifest(report, (GATE_LOCK_READ_TEST_ID,))

    def test_s1_oracle_and_gate_lock_read_run_when_the_manifest_is_present(self):
        manifest = Path.home() / ".crucible" / "crucible-clients.json"
        if not manifest.is_file():
            self.skipTest(f"{manifest} is absent on this machine; the present-manifest half needs it")
        report = _run_tests_in_child([*TOON_ORACLE_TEST_IDS, GATE_LOCK_READ_TEST_ID], dict(os.environ))
        self.assertEqual(report["run"], 3)
        self.assertEqual(
            report["skipped"], {},
            f"§S1: with {manifest} present the oracle and the gate-lock read must RUN",
        )
        self.assertEqual(report["failures"], {})
        self.assertEqual(report["errors"], {})


# ------------------------------------------------------ §S1 dead origin tests ----


def _class_methods(module_file: Path) -> dict:
    """``{class name: {method names}}`` for every top-level class in ``module_file``."""
    tree = ast.parse(module_file.read_text(encoding="utf-8"), str(module_file))
    return {
        node.name: {
            item.name for item in node.body
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        for node in tree.body if isinstance(node, ast.ClassDef)
    }


class DeadOriginTreeTestsS1Test(unittest.TestCase):
    """§S1 — the two dead origin-tree tests are deleted."""

    def test_s1_imported_bundle_byte_identity_test_is_deleted(self):
        classes = _class_methods(TESTS_DIR / "test_skills_handover.py")
        self.assertNotIn("ImportedBundleByteIdentityTest", classes)

    def test_s1_handover_origin_file_set_method_is_deleted(self):
        classes = _class_methods(TESTS_DIR / "test_installer_assets.py")
        self.assertIn(
            "CrucibleHandoverBundleFidelityTest", classes,
            "§S1 deletes one METHOD, not the class",
        )
        self.assertNotIn(
            "test_each_handover_bundle_exists_and_covers_origin_file_set",
            classes["CrucibleHandoverBundleFidelityTest"],
        )


# ------------------------------------------------------------ §S2 home reads ----

#: §S2 — the reviewed real-home reads that REMAIN. ``(file, enclosing scope)`` → reason. Every entry
#: treats the home path as a string and never stats, opens or lists anything under it.
HOME_READ_ALLOWLIST = {
    ("test_installer_assets.py",
     "BuildPyCliRetargetTest.test_build_py_list_is_repo_local_check_clean_and_zero_chezmoi_refs"):
        "negative leak check: no path `build.py --list` prints may start with the home prefix",
    ("test_installer_correctness.py",
     "PiExtensionTargetRootRoundTripTest.test_compiled_pi_extension_references_target_root_not_real_home"):
        "negative leak check: the compiled Pi extension must not contain the home path string",
    ("test_tooling_detachment.py",
     "DetachmentS6Test.test_s6_seven_consuming_surfaces_name_the_deployed_store_path"):
        "path algebra only (PRD §D9): the documented store spelling equals deploy.py's target",
    ("test_toon_codec.py", "_path_inserts_outside_repo"):
        "the import gate normalises a `~` literal it found in scanned source before comparing",
    (THIS_FILE, "SandboxedExecutionS2Test.test_s2_installer_module_runs_pin_home_and_path"):
        "reads the ambient HOME value only to prove the children did NOT inherit it",
}

#: §S2 rule 3 (CR-MDB-039) — the ONE sanctioned read of an installed Pi package's released
#: source, parallel to the installed Crucible reads and deliberately NOT an allowlist entry (it
#: opens the file). ``(file, enclosing scope)`` → reason; read-only, ``$PI_CODING_AGENT_DIR``
#: first then ``~/.pi/agent``, the reading test skips naming the path when it is absent.
INSTALLED_PI_PACKAGE_READS = {
    ("test_pi_worktree_isolation.py", "_installed_service_ts"):
        "CR-MDB-039 AC: contract read of the installed pi-subagents service key",
}

_HOME_ENV_KEY = "HOME"


def _is_environ(node) -> bool:
    return (isinstance(node, ast.Attribute) and node.attr == "environ") or (
        isinstance(node, ast.Name) and node.id == "environ"
    )


def _is_home_key(node) -> bool:
    return isinstance(node, ast.Constant) and node.value == _HOME_ENV_KEY


def _literal_of(node):
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def _installed_crucible_read(node, parent) -> bool:
    """Is this read the installed Crucible surface §S1 mandates?"""
    if isinstance(node.func, ast.Attribute) and node.func.attr == "home":
        return (
            isinstance(parent, ast.BinOp) and isinstance(parent.op, ast.Div)
            and parent.left is node and _literal_of(parent.right) == ".crucible"
        )
    target = None
    if node.args:  # os.path.expanduser("~/.crucible/…")
        target = _literal_of(node.args[0])
    elif isinstance(node.func.value, ast.Call) and node.func.value.args:  # Path("~/.crucible/…").expanduser()
        target = _literal_of(node.func.value.args[0])
    return bool(target) and target.startswith("~/.crucible/")


def _home_read_form(node):
    """The read form ``node`` is, or ``None``."""
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        attr = node.func.attr
        if attr == "home" and not node.args:
            return "Path.home()"
        if attr == "expanduser":
            return "expanduser"
        if attr == "getenv" and node.args and _is_home_key(node.args[0]):
            return "getenv(HOME)"
        if attr == "get" and _is_environ(node.func.value) and node.args and _is_home_key(node.args[0]):
            return "environ.get(HOME)"
    if (isinstance(node, ast.Subscript) and isinstance(node.ctx, ast.Load)
            and _is_environ(node.value) and _is_home_key(node.slice)):
        return "environ[HOME]"
    return None


def _home_reads(path: Path) -> list:
    """``[(lineno, form, scope, installed_crucible)]`` for every real-home read in ``path``."""
    tree = ast.parse(path.read_text(encoding="utf-8"), str(path))
    parents = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[child] = node
    reads = []
    for node in ast.walk(tree):
        form = _home_read_form(node)
        if form is None:
            continue
        names, cursor = [], node
        while cursor in parents:
            cursor = parents[cursor]
            if isinstance(cursor, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                names.append(cursor.name)
        scope = ".".join(reversed(names)) or "<module>"
        crucible = isinstance(node, ast.Call) and _installed_crucible_read(node, parents.get(node))
        reads.append((getattr(node, "lineno", 0), form, scope, crucible))
    return sorted(reads)


def _unpermitted_home_reads(tests_dir: Path, allowlist: dict, pi_package_reads=None) -> list:
    permitted = set(allowlist) | set(pi_package_reads or {})
    offenders = []
    for path in sorted(tests_dir.glob("*.py")):
        for lineno, form, scope, crucible in _home_reads(path):
            if crucible or (path.name, scope) in permitted:
                continue
            offenders.append((path.name, lineno, form, scope))
    return offenders


class RealHomeReadsS2Test(unittest.TestCase):
    """§S2 — no test reads the real home except the installed Crucible surface, the reviewed
    allowlist and the one installed-Pi-package read (rule 3)."""

    maxDiff = None

    def test_s2_no_test_module_reads_the_real_home_outside_the_allowlist(self):
        offenders = _unpermitted_home_reads(TESTS_DIR, HOME_READ_ALLOWLIST, INSTALLED_PI_PACKAGE_READS)
        self.assertEqual(
            offenders, [],
            "§S2: real-home reads outside the reviewed allowlist — retarget to skills-src/, "
            "archive/ or the repo AGENTS.md, pin a sandbox, or delete the superseded test:\n"
            + "\n".join(f"  tests/{f}:{n} {form} in {scope}" for f, n, form, scope in offenders),
        )

    def test_s2_every_allowlist_entry_names_a_live_use(self):
        live = set()
        for path in sorted(TESTS_DIR.glob("*.py")):
            live.update((path.name, scope) for _, _, scope, _ in _home_reads(path))
        stale = sorted(set(HOME_READ_ALLOWLIST) - live)
        self.assertEqual(stale, [], f"§S2: allowlist entries with no remaining use — drop them: {stale}")

    def test_s2_home_read_detector_flags_each_access_form(self):
        source = (
            "import os\n"                                                        # 1
            "from pathlib import Path\n"                                         # 2
            "A = Path.home() / '.claude'\n"                                      # 3 flagged
            "B = Path.home() / '.crucible' / 'crucible-clients.json'\n"          # 4 installed
            "def f():\n"                                                         # 5
            "    return os.path.expanduser('~')\n"                               # 6 flagged
            "def g():\n"                                                         # 7
            "    return Path('~/.agents').expanduser()\n"                        # 8 flagged
            "def h():\n"                                                         # 9
            "    return os.path.expanduser('~/.crucible/crucible-clients.json')\n"  # 10 installed
            "class K:\n"                                                         # 11
            "    def m(self):\n"                                                 # 12
            "        return os.environ['HOME']\n"                                # 13 flagged
            "    def n(self, env):\n"                                            # 14
            "        env['HOME'] = '/tmp/sandbox'\n"                             # 15 construction
            "        os.environ['HOME'] = '/tmp/sandbox'\n"                      # 16 construction
            "        return os.environ.get('HOME'), os.getenv('HOME')\n"         # 17 flagged x2
            "C = '~/.claude/skills/x/SKILL.md'\n"                                # 18 text, not a read
        )
        with tempfile.TemporaryDirectory() as tmp:
            tests_dir = Path(tmp) / "tests"
            tests_dir.mkdir()
            (tests_dir / "test_probe.py").write_text(source, encoding="utf-8")
            offenders = _unpermitted_home_reads(tests_dir, {})
            allowed = _unpermitted_home_reads(tests_dir, {("test_probe.py", "K.n"): "probe"})
        self.assertEqual(offenders, [
            ("test_probe.py", 3, "Path.home()", "<module>"),
            ("test_probe.py", 6, "expanduser", "f"),
            ("test_probe.py", 8, "expanduser", "g"),
            ("test_probe.py", 13, "environ[HOME]", "K.m"),
            ("test_probe.py", 17, "environ.get(HOME)", "K.n"),
            ("test_probe.py", 17, "getenv(HOME)", "K.n"),
        ])
        self.assertEqual(
            [o for o in allowed if o[3] == "K.n"], [],
            "an allowlisted (file, scope) permits exactly that scope's reads",
        )
        self.assertEqual(len(allowed), 4)


class InstalledPiPackageReadS2Test(unittest.TestCase):
    """§S2 rule 3 (CR-MDB-039) — the one installed-Pi-package read is a separate, single-entry
    exception that names a live use, and the gate still bites around it."""

    maxDiff = None

    def test_s2_the_installed_pi_package_exception_is_exactly_one_entry_apart_from_the_allowlist(self):
        self.assertEqual(sorted(INSTALLED_PI_PACKAGE_READS),
                         [("test_pi_worktree_isolation.py", "_installed_service_ts")])
        self.assertEqual(set(INSTALLED_PI_PACKAGE_READS) & set(HOME_READ_ALLOWLIST), set(),
                         "rule 3 is not an allowlist entry: the allowlist's never-open rule stays true")
        for reason in INSTALLED_PI_PACKAGE_READS.values():
            self.assertIn("CR-MDB-039", reason)

    def test_s2_the_installed_pi_package_read_is_live_and_resolves_the_pi_agent_dir(self):
        for file_name, scope in INSTALLED_PI_PACKAGE_READS:
            with self.subTest(scope=f"{file_name}:{scope}"):
                path = TESTS_DIR / file_name
                self.assertIn(scope, {s for _, _, s, _ in _home_reads(path)},
                              f"§S2 rule 3: {file_name}:{scope} no longer reads the home — drop it")
                tree = ast.parse(path.read_text(encoding="utf-8"))
                funcs = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == scope]
                self.assertEqual(len(funcs), 1, f"{scope} is one module-level function")
                source = ast.get_source_segment(path.read_text(encoding="utf-8"), funcs[0]) or ""
                self.assertIn("PI_CODING_AGENT_DIR", source, "$PI_CODING_AGENT_DIR is resolved first")
                self.assertIn('".pi"', source, "then ~/.pi/agent")

    def test_s2_the_gate_still_bites_an_unlisted_read_and_a_listed_name_in_another_module(self):
        reader = (
            "from pathlib import Path\n"                                          # 1
            "def _installed_service_ts():\n"                                      # 2
            "    return Path.home() / '.pi' / 'agent'\n"                          # 3 sanctioned
            "def _other_reader():\n"                                              # 4
            "    return Path.home() / '.pi' / 'agent'\n"                          # 5 flagged
        )
        with tempfile.TemporaryDirectory() as tmp:
            tests_dir = Path(tmp) / "tests"
            tests_dir.mkdir()
            (tests_dir / "test_pi_worktree_isolation.py").write_text(reader, encoding="utf-8")
            (tests_dir / "test_elsewhere.py").write_text(reader, encoding="utf-8")
            with_rule = _unpermitted_home_reads(tests_dir, {}, INSTALLED_PI_PACKAGE_READS)
            without_rule = _unpermitted_home_reads(tests_dir, {})
        self.assertEqual(with_rule, [
            ("test_elsewhere.py", 3, "Path.home()", "_installed_service_ts"),
            ("test_elsewhere.py", 5, "Path.home()", "_other_reader"),
            ("test_pi_worktree_isolation.py", 5, "Path.home()", "_other_reader"),
        ])
        self.assertIn(("test_pi_worktree_isolation.py", 3, "Path.home()", "_installed_service_ts"),
                      without_rule, "without rule 3 the sanctioned read is an offender too")


# ------------------------------------------------------ §S2 superseded tests ----


class SupersededRealHomeTestsS2Test(unittest.TestCase):
    """§S2 — the real-home module and the superseded / real-home classes are deleted."""

    def test_s2_realhome_supersede_module_is_deleted(self):
        self.assertFalse(
            (TESTS_DIR / "test_realhome_supersede.py").exists(),
            "§S2: tests/test_realhome_supersede.py must be deleted; CR-MDB-020's anchoring gate "
            "covers its one retained mirror-absence assertion",
        )

    def test_s2_realhome_skip_guard_test_is_deleted(self):
        classes = _class_methods(TESTS_DIR / "test_tooling_detachment.py")
        self.assertIn("DetachmentS6Test", classes)
        self.assertNotIn(
            "test_s6_realhome_gate_covers_the_eight_and_stays_behind_its_env_gate",
            classes["DetachmentS6Test"],
            "§S2: test_tooling_detachment's tests of test_realhome_supersede's skip guards go with it",
        )

    def test_s2_superseded_worktree_flow_classes_are_deleted(self):
        classes = _class_methods(TESTS_DIR / "test_worktree_flow_axi.py")
        self.assertEqual(
            sorted({"WorktreeFlowCodecDeploymentTest", "WorktreeFlowEnvelopeTest"} & set(classes)), [],
        )
        self.assertIn(
            "WorktreeFlowSkillConsumerNotesTest", classes,
            "§S2 migrates the consumer-notes class; it is not deleted",
        )

    def test_s2_worktree_flow_consumer_notes_test_reads_skills_src(self):
        reads = []
        real_path_open = pathlib.Path.open

        def spy_path_open(self, mode="r", *args, **kwargs):
            if self.name == "SKILL.md":
                reads.append(Path(os.fspath(self)).resolve())
            return real_path_open(self, mode, *args, **kwargs)

        result = unittest.TestResult()
        suite = unittest.defaultTestLoader.loadTestsFromName(
            "tests.test_worktree_flow_axi.WorktreeFlowSkillConsumerNotesTest"
        )
        with mock.patch.object(pathlib.Path, "open", spy_path_open):
            suite.run(result)
        self.assertTrue(
            result.wasSuccessful(),
            "the consumer-notes class itself must pass:\n"
            + "\n".join(tb for _, tb in result.failures + result.errors),
        )
        self.assertGreater(len(reads), 0, "the consumer-notes class read no SKILL.md — vacuous")
        outside = sorted({str(p) for p in reads if not p.is_relative_to(REPO_ROOT / "skills-src")})
        self.assertEqual(
            outside, [],
            "§S2: WorktreeFlowSkillConsumerNotesTest must read the repo's skills-src/, never a "
            "deployed copy under the home directory",
        )

    def test_s2_deployed_agents_consumer_constraint_test_is_deleted(self):
        classes = _class_methods(TESTS_DIR / "test_agent_generator.py")
        self.assertNotIn("DeployedAgentsConsumerConstraintTest", classes)

    def test_s2_imported_skill_bundle_fidelity_test_is_deleted(self):
        classes = _class_methods(TESTS_DIR / "test_installer_assets.py")
        self.assertNotIn("ImportedSkillBundleFidelityTest", classes)


# --------------------------------------------------- §S2 sandboxed execution ----

DRIFT_TEST_ID = (
    "tests.test_agent_generator.BuildPyIdempotenceS3Test."
    "test_s3_check_flag_exits_one_and_names_the_mutated_file"
)
_WRITE_MODE_CHARS = frozenset("wax+")
_IGNORED_WRITE_PARTS = frozenset({"__pycache__", "test-reports"})


class SandboxedExecutionS2Test(unittest.TestCase):
    """§S2 — no test mutates a tracked file; the installer module's children run sandboxed."""

    maxDiff = None

    def test_s2_generator_drift_test_writes_no_tracked_file(self):
        writes = set()
        real_open, real_path_open = builtins.open, pathlib.Path.open

        def _note(target, mode):
            if not (_WRITE_MODE_CHARS & set(str(mode))):
                return
            try:
                resolved = Path(os.fspath(target)).resolve()
            except TypeError:
                return
            if resolved.is_relative_to(REPO_ROOT) and not (_IGNORED_WRITE_PARTS & set(resolved.parts)):
                writes.add(resolved.relative_to(REPO_ROOT).as_posix())

        def spy_open(file, mode="r", *args, **kwargs):
            _note(file, mode)
            return real_open(file, mode, *args, **kwargs)

        def spy_path_open(self, mode="r", *args, **kwargs):
            _note(self, mode)
            return real_path_open(self, mode, *args, **kwargs)

        result = unittest.TestResult()
        suite = unittest.defaultTestLoader.loadTestsFromName(DRIFT_TEST_ID)
        with mock.patch.object(builtins, "open", spy_open), \
                mock.patch.object(pathlib.Path, "open", spy_path_open):
            suite.run(result)
        self.assertEqual(result.testsRun, 1)
        self.assertTrue(
            result.wasSuccessful(),
            "the drift test itself must pass:\n" + "\n".join(tb for _, tb in result.failures + result.errors),
        )
        self.assertEqual(
            sorted(writes), [],
            "§S2: the generator drift test must mutate a TEMP COPY of the generator tree, never a "
            "tracked file in place",
        )

    def test_s2_installer_module_runs_pin_home_and_path(self):
        ambient_home = os.environ.get("HOME")
        ambient_path = os.environ.get("PATH")
        envs = []
        real_run = subprocess.run

        def spy_run(*args, **kwargs):
            argv = args[0] if args else kwargs.get("args")
            if isinstance(argv, (list, tuple)) and "-m" in argv and "modelb_axi" in argv:
                envs.append((list(map(str, argv[2:])), kwargs.get("env")))
            return real_run(*args, **kwargs)

        result = unittest.TestResult()
        suite = unittest.defaultTestLoader.loadTestsFromName("tests.test_installer")
        with mock.patch.object(subprocess, "run", spy_run):
            suite.run(result)
        self.assertTrue(
            result.wasSuccessful(),
            "tests.test_installer itself must pass:\n"
            + "\n".join(tb for _, tb in result.failures + result.errors),
        )
        self.assertGreater(len(envs), 0, "no `python -m modelb_axi` child was observed — vacuous run")
        leaks = [
            (argv, "HOME" if env is None or env.get("HOME") == ambient_home else "PATH")
            for argv, env in envs
            if env is None or env.get("HOME") == ambient_home or env.get("PATH") == ambient_path
        ]
        self.assertEqual(
            leaks, [],
            f"§S2: {len(leaks)} of {len(envs)} `python -m modelb_axi` children in tests.test_installer "
            "inherit the ambient HOME or PATH; every _run_module call pins both to the sandbox",
        )


if __name__ == "__main__":
    unittest.main()
