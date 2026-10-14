"""The two shipped release scripts, ``workflows-src/stamp_version.py`` and
``workflows-src/changelog_section.py`` (CR-MDB-068 §S3).

Contract: ``docs/changes/CR-MDB-068-release-and-ci-workflow-templates.md`` §S3, carrying
CR-MDB-067 §S1's ref and run-number grammar and its refusals.

Each script runs two ways, in a temp tree that is the working directory: loaded by path
(``importlib.util.spec_from_file_location`` as ``__main__`` with its argv) and as the CLI
(``python3 <script> ...``). The tree holds only the version sources a case names; the script itself
is read from ``workflows-src/``, so "nothing written" is every byte of the tree unchanged.

Class map:

- ``StampWithoutTargetsTest`` — ``stamp <ref> <run-number>`` checks the ref and the run number and
  prints ``X.Y.Z``, writing nothing; every CR-MDB-067 ref and run-number refusal.
- ``StampTargetsTest`` — ``stamp`` with ``pypi:.`` (static and hatch-dynamic), ``pypi:<sub>``,
  ``npm:.``, ``npm:<sub>`` and both: ``X.Y.Z.devN`` / ``X.Y.Z-dev.N`` written, only those values
  changed, ``X.Y.Z`` printed. CR-MDB-068 C5 RED (VERIFY F2/F3): CRLF sources and a
  ``__version__`` line with a trailing comment are stamped (and checked), each ``\r\n`` and the
  comment kept byte for byte.
- ``CheckTargetsTest`` — ``check <tag> <target>...`` passes, and fails naming each source whose
  version is not ``<tag>``, writing nothing.
- ``VersionSourceRefusalsTest`` — every §S3 refusal: exit 1, one stderr line naming the file,
  nothing written.
- ``ChangelogSectionScriptTest`` — today's behaviour on every CR-MDB-058 sample case.
- ``WorkflowScriptsSourceTest`` — both: Python 3.12 syntax, stdlib imports, and docstrings saying
  the script is rendered into a project by ``modelb-axi`` and is not part of the ``modelb_axi``
  package.

Stdlib only.
"""

import ast
import contextlib
import importlib.util
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.test_changelog_release_body import FOUND_CASES, REFUSED_CASES
from tests.test_release_rehearsal import REFUSED_REFS, REFUSED_RUNS

REPO_ROOT = Path(__file__).resolve().parent.parent
STAMP = REPO_ROOT / "workflows-src" / "stamp_version.py"
SECTION = REPO_ROOT / "workflows-src" / "changelog_section.py"


# ------------------------------------------------------------------ runners ----

def _exit_code(exc: SystemExit, err) -> int:
    """The interpreter's exit status for ``exc``: ``None`` is 0, an int is itself, anything else
    is printed to ``err`` and is 1."""
    if exc.code is None:
        return 0
    if isinstance(exc.code, int):
        return exc.code
    print(exc.code, file=err)
    return 1


def run_script_by_path(script: Path, argv: list[str], cwd: Path) -> tuple[int, str, str]:
    """Load ``script`` by path as ``__main__`` with ``sys.argv = [script, *argv]``, from ``cwd``.
    ``(exit code, stdout, stderr)``."""
    if not script.is_file():
        raise AssertionError(f"§S3: {script.relative_to(REPO_ROOT)} must exist")
    spec = importlib.util.spec_from_file_location("__main__", script)
    if spec is None or spec.loader is None:
        raise AssertionError(f"§S3: {script} cannot be loaded by path")
    module = importlib.util.module_from_spec(spec)
    out_bytes, err_bytes = io.BytesIO(), io.BytesIO()
    out = io.TextIOWrapper(out_bytes, encoding="utf-8", newline="")
    err = io.TextIOWrapper(err_bytes, encoding="utf-8", newline="")
    saved_argv, saved_cwd = sys.argv, os.getcwd()
    code = 0
    try:
        sys.argv = [str(script), *argv]
        os.chdir(cwd)
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                spec.loader.exec_module(module)
            except SystemExit as exc:
                code = _exit_code(exc, err)
    finally:
        sys.argv = saved_argv
        os.chdir(saved_cwd)
    out.flush()
    err.flush()
    return code, out_bytes.getvalue().decode("utf-8"), err_bytes.getvalue().decode("utf-8")


def run_script_cli(script: Path, argv: list[str], cwd: Path) -> tuple[int, str, str]:
    """``python3 <script> <argv...>`` from ``cwd``. ``(exit code, stdout, stderr)``."""
    if not script.is_file():
        raise AssertionError(f"§S3: {script.relative_to(REPO_ROOT)} must exist")
    result = subprocess.run([sys.executable, str(script), *argv], cwd=cwd, capture_output=True,
                            text=True, encoding="utf-8", timeout=30, stdin=subprocess.DEVNULL)
    return result.returncode, result.stdout, result.stderr


RUNNERS = (("loaded by path", run_script_by_path), ("the CLI", run_script_cli))


def snapshot(tree: Path) -> dict[str, bytes | None]:
    """Every path under ``tree``: a file's bytes, ``None`` for a directory."""
    return {path.relative_to(tree).as_posix(): (path.read_bytes() if path.is_file() else None)
            for path in sorted(tree.rglob("*"))}


# ------------------------------------------------------------------ fixtures ----

def pyproject_static(version: str) -> str:
    """A hatchling ``pyproject.toml`` whose ``[project] version`` is ``version``; ``1.2.3`` also
    appears in a dependency pin and as another table's ``version`` above ``[project]``."""
    return ("[build-system]\n"
            'requires = ["hatchling"]\n'
            'build-backend = "hatchling.build"\n'
            "\n"
            "[tool.fixture]\n"
            'version = "1.2.3"\n'
            "\n"
            "[project]\n"
            'name = "fixture"\n'
            f'version = "{version}"\n'
            'dependencies = ["dep==1.2.3"]\n'
            "\n"
            "[tool.other]\n"
            'note = "version 1.2.3"\n')


HATCH_PATH = "src/fixture/__init__.py"


def pyproject_hatch(tail: str = f'[tool.hatch.version]\npath = "{HATCH_PATH}"\n') -> str:
    """A hatchling ``pyproject.toml`` with ``version`` in ``[project] dynamic`` and ``tail``."""
    return ("[build-system]\n"
            'requires = ["hatchling"]\n'
            'build-backend = "hatchling.build"\n'
            "\n"
            "[project]\n"
            'name = "fixture"\n'
            'dynamic = ["version"]\n'
            'dependencies = ["dep==1.2.3"]\n'
            "\n" + tail)


def init_py(version_line: str) -> str:
    return f'"""Fixture package."""\n\n{version_line}\n_PREVIOUS = "1.2.3"\n'


def package_json(version: str, indent: str = "  ") -> str:
    """A ``package.json`` whose top-level ``"version"`` is ``version`` at ``indent``; a nested
    ``"version"`` and a dependency on ``1.2.3`` precede and follow it."""
    return ("{\n"
            f'{indent}"name": "fixture",\n'
            f'{indent}"engines": {{\n'
            f'{indent}{indent}"version": "9.9.9"\n'
            f"{indent}}},\n"
            f'{indent}"version": "{version}",\n'
            f'{indent}"dependencies": {{\n'
            f'{indent}{indent}"x": "1.2.3"\n'
            f"{indent}}}\n"
            "}\n")


def crlf(text: str) -> str:
    """``text`` with every line ending CRLF (CR-MDB-068 C5 RED, VERIFY F2)."""
    return text.replace("\n", "\r\n")


#: CR-MDB-068 C5 RED (VERIFY F3) - a ``__version__`` line carrying a trailing comment.
COMMENTED_VERSION = '__version__ = "1.2.3"  # the release version, kept by the stamp'


def with_version(text: str, old_line: str, new_line: str) -> str:
    """``text`` with its one ``old_line`` replaced: the only bytes a stamp may change."""
    if text.count(old_line) != 1:
        raise AssertionError(f"fixture: {old_line!r} must occur once")
    return text.replace(old_line, new_line)


class _TreeCase(unittest.TestCase):
    """A temp tree per call, removed after the test."""

    def tree(self, files: dict[str, str]) -> Path:
        root = Path(tempfile.mkdtemp(prefix="r68-scripts-"))
        self.addCleanup(shutil.rmtree, root, True)
        for rel, text in files.items():
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(text.encode("utf-8"))
        return root

    def run_both(self, files: dict[str, str], argv: list[str], script: Path = STAMP):
        """``(label, tree, (code, out, err))`` for each runner, each in a fresh tree."""
        for label, runner in RUNNERS:
            tree = self.tree(files)
            yield label, tree, runner(script, argv, tree)

    def assert_prints(self, out: str, version: str):
        self.assertIn(out, (version, version + "\n"), f"§S3: prints {version}; got {out!r}")

    def assert_refused(self, files: dict[str, str], argv: list[str], *named: str):
        """Exit 1, exactly one stderr line naming each of ``named``, no stdout, nothing written."""
        for label, tree, (code, out, err) in self.run_both(files, argv):
            with self.subTest(runner=label, argv=argv):
                self.assertEqual(code, 1, f"§S3: a refusal exits 1; stderr={err!r}")
                lines = err.splitlines()
                self.assertEqual(len(lines), 1, f"§S3: one stderr line; got {err!r}")
                self.assertNotIn("Traceback", err)
                for name in named:
                    self.assertIn(name, lines[0], f"§S3: the line names {name!r}")
                self.assertEqual(out, "")
                self.assertEqual(snapshot(tree), snapshot(self.tree(files)),
                                 "§S3: a refusal writes nothing")


# ------------------------------------------------------------------ stamp ----

class StampWithoutTargetsTest(_TreeCase):
    """§S3 — ``stamp <ref> <run-number>``: the ref and run number checked, ``X.Y.Z`` printed,
    nothing read or written."""

    def test_a_release_or_hotfix_ref_prints_its_version_and_writes_nothing(self):
        for ref, version in (("release/1.2.3", "1.2.3"), ("hotfix/10.0.11", "10.0.11")):
            for label, tree, (code, out, err) in self.run_both({}, ["stamp", ref, "7"]):
                with self.subTest(runner=label, ref=ref):
                    self.assertEqual(code, 0, f"stderr={err!r}")
                    self.assert_prints(out, version)
                    self.assertEqual(snapshot(tree), {}, "§S3: no target, nothing written")

    def test_every_other_ref_is_refused_naming_it(self):
        for ref in REFUSED_REFS:
            self.assert_refused({}, ["stamp", ref, "7"], ref)

    def test_every_other_run_number_is_refused_naming_it(self):
        for run in REFUSED_RUNS:
            self.assert_refused({}, ["stamp", "release/1.2.3", run], run)

    def test_a_bad_ref_is_refused_before_any_target_is_read(self):
        files = {"pyproject.toml": pyproject_static("1.2.3")}
        self.assert_refused(files, ["stamp", "feature/x", "7", "pypi:."], "feature/x")


class StampTargetsTest(_TreeCase):
    """§S3 — ``stamp`` with targets: every source equal to ``X.Y.Z``, then the dev versions
    written, only those values changed, and ``X.Y.Z`` printed."""

    def assert_stamps(self, files: dict[str, str], targets: list[str], expected: dict[str, str]):
        for label, tree, (code, out, err) in self.run_both(
                files, ["stamp", "release/1.2.3", "7", *targets]):
            with self.subTest(runner=label, targets=targets):
                self.assertEqual(code, 0, f"stderr={err!r}")
                self.assert_prints(out, "1.2.3")
                self.assertEqual(snapshot(tree), snapshot(self.tree(expected)),
                                 "§S3: only the version values change, every other byte stays")

    def test_pypi_dot_with_a_static_project_version(self):
        text = pyproject_static("1.2.3")
        self.assert_stamps({"pyproject.toml": text}, ["pypi:."], {"pyproject.toml": with_version(
            text, 'name = "fixture"\nversion = "1.2.3"\n',
            'name = "fixture"\nversion = "1.2.3.dev7"\n')})

    def test_pypi_dot_with_a_hatch_dynamic_version(self):
        init = init_py('__version__ = "1.2.3"')
        files = {"pyproject.toml": pyproject_hatch(), HATCH_PATH: init}
        self.assert_stamps(files, ["pypi:."], {
            "pyproject.toml": pyproject_hatch(),
            HATCH_PATH: with_version(init, '__version__ = "1.2.3"', '__version__ = "1.2.3.dev7"')})

    def test_pypi_in_a_sub_directory(self):
        text = pyproject_static("1.2.3")
        init = init_py('__version__ = "1.2.3"')
        files = {"py/pyproject.toml": text, "py/" + HATCH_PATH: init,
                 "pyproject.toml": pyproject_static("0.0.1")}
        expected = dict(files, **{"py/pyproject.toml": with_version(
            text, 'version = "1.2.3"\ndependencies', 'version = "1.2.3.dev7"\ndependencies')})
        self.assert_stamps(files, ["pypi:py"], expected)

    def test_npm_dot_writes_the_npm_dev_form_into_the_top_level_version(self):
        text = package_json("1.2.3")
        self.assert_stamps({"package.json": text}, ["npm:."], {"package.json": with_version(
            text, '  "version": "1.2.3",', '  "version": "1.2.3-dev.7",')})

    def test_npm_in_a_sub_directory(self):
        text = package_json("1.2.3")
        files = {"pkg/package.json": text, "package.json": package_json("0.0.1")}
        expected = dict(files, **{"pkg/package.json": with_version(
            text, '  "version": "1.2.3",', '  "version": "1.2.3-dev.7",')})
        self.assert_stamps(files, ["npm:pkg"], expected)

    def test_both_targets_together(self):
        py, npm = pyproject_static("1.2.3"), package_json("1.2.3")
        files = {"pyproject.toml": py, "pkg/package.json": npm}
        self.assert_stamps(files, ["pypi:.", "npm:pkg"], {
            "pyproject.toml": with_version(py, 'version = "1.2.3"\ndependencies',
                                           'version = "1.2.3.dev7"\ndependencies'),
            "pkg/package.json": with_version(npm, '  "version": "1.2.3",',
                                             '  "version": "1.2.3-dev.7",')})

    # CR-MDB-068 C5 RED (VERIFY F2/F3): CRLF sources and a commented __version__ line are
    # stamped, every other byte - each \r\n and the comment included - unchanged.

    def test_pypi_dot_with_a_crlf_static_project_version_keeps_every_crlf(self):
        text = crlf(pyproject_static("1.2.3"))
        self.assert_stamps({"pyproject.toml": text}, ["pypi:."], {"pyproject.toml": with_version(
            text, 'name = "fixture"\r\nversion = "1.2.3"\r\n',
            'name = "fixture"\r\nversion = "1.2.3.dev7"\r\n')})

    def test_pypi_dot_with_a_crlf_hatch_dynamic_version_keeps_every_crlf(self):
        init = crlf(init_py('__version__ = "1.2.3"'))
        files = {"pyproject.toml": crlf(pyproject_hatch()), HATCH_PATH: init}
        self.assert_stamps(files, ["pypi:."], dict(files, **{HATCH_PATH: with_version(
            init, '__version__ = "1.2.3"\r\n', '__version__ = "1.2.3.dev7"\r\n')}))

    def test_both_targets_with_crlf_sources(self):
        py, npm = crlf(pyproject_static("1.2.3")), crlf(package_json("1.2.3"))
        self.assert_stamps({"pyproject.toml": py, "pkg/package.json": npm}, ["pypi:.", "npm:pkg"], {
            "pyproject.toml": with_version(py, 'version = "1.2.3"\r\ndependencies',
                                           'version = "1.2.3.dev7"\r\ndependencies'),
            "pkg/package.json": with_version(npm, '  "version": "1.2.3",\r\n',
                                             '  "version": "1.2.3-dev.7",\r\n')})

    def test_a_commented_dunder_version_is_stamped_keeping_the_comment(self):
        init = init_py(COMMENTED_VERSION)
        files = {"pyproject.toml": pyproject_hatch(), HATCH_PATH: init}
        self.assert_stamps(files, ["pypi:."], dict(files, **{HATCH_PATH: with_version(
            init, COMMENTED_VERSION, COMMENTED_VERSION.replace('"1.2.3"', '"1.2.3.dev7"'))}))

    def test_a_commented_crlf_dunder_version_is_stamped_keeping_the_comment_and_crlf(self):
        init = crlf(init_py(COMMENTED_VERSION))
        files = {"pyproject.toml": crlf(pyproject_hatch()), HATCH_PATH: init}
        self.assert_stamps(files, ["pypi:."], dict(files, **{HATCH_PATH: with_version(
            init, COMMENTED_VERSION + "\r\n",
            COMMENTED_VERSION.replace('"1.2.3"', '"1.2.3.dev7"') + "\r\n")}))

    def test_a_later_targets_refusal_leaves_the_earlier_target_unwritten(self):
        files = {"pyproject.toml": pyproject_static("1.2.3"),
                 "pkg/package.json": package_json("1.2.2")}
        self.assert_refused(files, ["stamp", "release/1.2.3", "7", "pypi:.", "npm:pkg"],
                            "pkg/package.json", "1.2.2", "1.2.3")

    def test_a_version_other_than_the_refs_is_refused_naming_file_found_and_wanted(self):
        for files, named in (
                ({"pyproject.toml": pyproject_static("1.2.2")}, ("pyproject.toml", "1.2.2")),
                ({"pyproject.toml": pyproject_static("1.2.3.dev0")},
                 ("pyproject.toml", "1.2.3.dev0")),
                ({"pyproject.toml": pyproject_hatch(),
                  HATCH_PATH: init_py('__version__ = "1.2.4"')}, (HATCH_PATH, "1.2.4")),
                ({"package.json": package_json("1.2.3-dev.0")}, ("package.json", "1.2.3-dev.0"))):
            target = "npm:." if "package.json" in files else "pypi:."
            self.assert_refused(files, ["stamp", "release/1.2.3", "7", target], *named, "1.2.3")


class CheckTargetsTest(_TreeCase):
    """§S3 — ``check <tag> <target>...``: exit 0 when every source is ``<tag>``; else exit 1
    naming each source that is not; never writes."""

    FILES = {"pyproject.toml": pyproject_static("1.2.3"), "pkg/package.json": package_json("1.2.3")}

    def test_every_source_at_the_tag_passes_and_writes_nothing(self):
        for label, tree, (code, _out, err) in self.run_both(
                self.FILES, ["check", "1.2.3", "pypi:.", "npm:pkg"]):
            with self.subTest(runner=label):
                self.assertEqual(code, 0, f"stderr={err!r}")
                self.assertEqual(snapshot(tree), snapshot(self.tree(self.FILES)))

    def test_a_hatch_dynamic_source_at_the_tag_passes(self):
        files = {"pyproject.toml": pyproject_hatch(), HATCH_PATH: init_py('__version__ = "2.0.0"')}
        for label, _tree, (code, _out, err) in self.run_both(files, ["check", "2.0.0", "pypi:."]):
            with self.subTest(runner=label):
                self.assertEqual(code, 0, f"stderr={err!r}")

    def test_one_source_off_the_tag_fails_naming_it_and_not_the_other(self):
        files = dict(self.FILES, **{"pyproject.toml": pyproject_static("1.2.2")})
        for label, tree, (code, out, err) in self.run_both(
                files, ["check", "1.2.3", "pypi:.", "npm:pkg"]):
            with self.subTest(runner=label):
                self.assertEqual(code, 1, f"stdout={out!r} stderr={err!r}")
                self.assertIn("pyproject.toml", err)
                self.assertIn("1.2.2", err)
                self.assertNotIn("package.json", err, "§S3: names only the source that is off")
                self.assertEqual(snapshot(tree), snapshot(self.tree(files)))

    def test_every_source_off_the_tag_is_named(self):
        files = {"pyproject.toml": pyproject_static("1.2.2"),
                 "pkg/package.json": package_json("1.2.1")}
        for label, _tree, (code, _out, err) in self.run_both(
                files, ["check", "1.2.3", "pypi:.", "npm:pkg"]):
            with self.subTest(runner=label):
                self.assertEqual(code, 1, f"stderr={err!r}")
                for named in ("pyproject.toml", "1.2.2", "pkg/package.json", "1.2.1"):
                    self.assertIn(named, err)

    def test_a_missing_source_is_refused_by_check_too(self):
        self.assert_refused({}, ["check", "1.2.3", "npm:pkg"], "pkg/package.json")

    # CR-MDB-068 C5 RED (VERIFY F2/F3): check reads CRLF sources and a commented __version__.

    def assert_check_passes(self, files: dict[str, str], argv: list[str]):
        for label, tree, (code, _out, err) in self.run_both(files, argv):
            with self.subTest(runner=label, argv=argv):
                self.assertEqual(code, 0, f"stderr={err!r}")
                self.assertEqual(snapshot(tree), snapshot(self.tree(files)), "check writes nothing")

    def assert_check_names(self, files: dict[str, str], argv: list[str], *named: str):
        for label, tree, (code, out, err) in self.run_both(files, argv):
            with self.subTest(runner=label, argv=argv):
                self.assertEqual(code, 1, f"stdout={out!r} stderr={err!r}")
                for name in (*named, "is not the tag"):
                    self.assertIn(name, err)
                self.assertEqual(snapshot(tree), snapshot(self.tree(files)))

    def test_crlf_sources_at_the_tag_pass_and_keep_their_bytes(self):
        self.assert_check_passes({"pyproject.toml": crlf(pyproject_static("1.2.3")),
                                  "pkg/package.json": crlf(package_json("1.2.3"))},
                                 ["check", "1.2.3", "pypi:.", "npm:pkg"])

    def test_a_crlf_hatch_source_at_the_tag_passes(self):
        self.assert_check_passes({"pyproject.toml": crlf(pyproject_hatch()),
                                  HATCH_PATH: crlf(init_py('__version__ = "2.0.0"'))},
                                 ["check", "2.0.0", "pypi:."])

    def test_a_crlf_source_off_the_tag_fails_naming_its_version(self):
        self.assert_check_names({"pyproject.toml": crlf(pyproject_static("1.2.2"))},
                                ["check", "1.2.3", "pypi:."], "pyproject.toml", "1.2.2")

    def test_a_commented_dunder_version_at_the_tag_passes_and_off_it_is_named(self):
        files = {"pyproject.toml": pyproject_hatch(), HATCH_PATH: init_py(COMMENTED_VERSION)}
        self.assert_check_passes(files, ["check", "1.2.3", "pypi:."])
        self.assert_check_names(files, ["check", "1.2.4", "pypi:."], HATCH_PATH, "1.2.3")


class VersionSourceRefusalsTest(_TreeCase):
    """§S3 — each refusal: exit 1, one stderr line naming the file, nothing written."""

    ARGV = ["stamp", "release/1.2.3", "7"]

    def test_a_missing_file_is_refused_naming_it(self):
        self.assert_refused({}, [*self.ARGV, "pypi:sub"], "sub/pyproject.toml")
        self.assert_refused({}, [*self.ARGV, "npm:pkg"], "pkg/package.json")
        self.assert_refused({}, [*self.ARGV, "npm:."], "package.json")
        self.assert_refused({"pyproject.toml": pyproject_hatch()}, [*self.ARGV, "pypi:."],
                            HATCH_PATH)

    def test_an_unreadable_file_is_refused_naming_it(self):
        files = {"pyproject.toml/placeholder": "a directory where the file should be\n"}
        self.assert_refused(files, [*self.ARGV, "pypi:."], "pyproject.toml")

    def test_another_dynamic_backend_is_refused_naming_the_pyproject(self):
        text = ("[build-system]\n"
                'requires = ["setuptools"]\n'
                'build-backend = "setuptools.build_meta"\n'
                "\n"
                "[project]\n"
                'name = "fixture"\n'
                'dynamic = ["version"]\n'
                "\n"
                "[tool.setuptools.dynamic]\n"
                'version = {attr = "fixture.__version__"}\n')
        self.assert_refused({"pyproject.toml": text}, [*self.ARGV, "pypi:."], "pyproject.toml")

    def test_a_hatch_version_without_a_path_is_refused_naming_the_pyproject(self):
        text = pyproject_hatch('[tool.hatch.version]\nsource = "vcs"\n')
        self.assert_refused({"pyproject.toml": text}, [*self.ARGV, "pypi:."], "pyproject.toml")

    def test_a_project_with_no_version_at_all_is_refused_naming_the_pyproject(self):
        text = '[project]\nname = "fixture"\n'
        self.assert_refused({"pyproject.toml": text}, [*self.ARGV, "pypi:."], "pyproject.toml")

    def test_an_absent_or_single_quoted_dunder_version_is_refused_naming_its_file(self):
        for line in ("VERSION = \"1.2.3\"", "__version__ = '1.2.3'"):
            files = {"pyproject.toml": pyproject_hatch(), HATCH_PATH: init_py(line)}
            self.assert_refused(files, [*self.ARGV, "pypi:."], HATCH_PATH)

    def test_a_single_quoted_dunder_version_with_a_comment_is_still_refused(self):
        # CR-MDB-068 C5 RED (VERIFY F3): a trailing comment does not admit a single-quoted value.
        files = {"pyproject.toml": pyproject_hatch(),
                 HATCH_PATH: init_py("__version__ = '1.2.3'  # a comment")}
        self.assert_refused(files, [*self.ARGV, "pypi:."], HATCH_PATH)

    def test_a_package_json_without_a_two_space_top_level_version_is_refused_naming_it(self):
        for text in (package_json("1.2.3", indent="    "), package_json("1.2.3", indent="\t"),
                     '{\n  "name": "fixture"\n}\n'):
            self.assert_refused({"pkg/package.json": text}, [*self.ARGV, "npm:pkg"],
                                "pkg/package.json")

    def test_a_nested_matching_version_never_satisfies_the_top_level_one(self):
        text = package_json("1.2.2").replace('"9.9.9"', '"1.2.3"')
        self.assert_refused({"package.json": text}, [*self.ARGV, "npm:."], "package.json", "1.2.2")


# ------------------------------------------------------------------ changelog_section ----

class ChangelogSectionScriptTest(_TreeCase):
    """§S3 — ``changelog_section.py``: today's behaviour (CR-MDB-058 §S2's sample cases)."""

    def test_prints_the_tags_section_body_on_every_found_case(self):
        for case, sample, tag, expected in FOUND_CASES:
            for label, _tree, (code, out, err) in self.run_both(
                    {"CHANGELOG.md": sample}, ["CHANGELOG.md", tag], SECTION):
                with self.subTest(case=case, runner=label):
                    self.assertEqual(code, 0, f"stderr={err!r}")
                    self.assertIn(out, (expected, expected + "\n"))

    def test_exits_1_naming_the_tag_on_every_refused_case(self):
        for case, sample, tag in REFUSED_CASES:
            for label, _tree, (code, out, err) in self.run_both(
                    {"CHANGELOG.md": sample}, ["CHANGELOG.md", tag], SECTION):
                with self.subTest(case=case, runner=label):
                    self.assertEqual(code, 1, f"stdout={out!r} stderr={err!r}")
                    self.assertIn(tag, err)

    def test_a_missing_changelog_exits_1_naming_the_path_and_the_tag(self):
        for label, _tree, (code, out, err) in self.run_both({}, ["absent/CHANGELOG.md", "1.0.0"],
                                                            SECTION):
            with self.subTest(runner=label):
                self.assertEqual((code, out), (1, ""), f"stderr={err!r}")
                self.assertNotIn("Traceback", err)
                self.assertIn("absent/CHANGELOG.md", err)
                self.assertIn("1.0.0", err)


# ------------------------------------------------------------------ the sources ----

#: §S3 — what both docstrings say (lower-cased, whitespace collapsed, backticks dropped).
DOCSTRING_RENDERED = re.compile(r"rendered into (?:a|each|the) project by modelb-axi")
DOCSTRING_NOT_PACKAGE = re.compile(r"not part of the modelb_axi package")


def docstring_faults(source: str) -> list[str]:
    """What the module docstring of ``source`` lacks of §S3's two statements, or still says of
    the retired "repo-only" one; ``[]`` when it says both."""
    doc = ast.get_docstring(ast.parse(source)) or ""
    flat = " ".join(doc.replace("`", "").split()).lower()
    faults = []
    if not DOCSTRING_RENDERED.search(flat):
        faults.append("does not say it is rendered into a project by modelb-axi")
    if not DOCSTRING_NOT_PACKAGE.search(flat):
        faults.append("does not say it is not part of the modelb_axi package")
    if "repo-only" in flat:
        faults.append("still says it is repo-only")
    return faults


def imported_top_levels(source: str) -> set[str]:
    """The top-level module names ``source`` imports (a relative import is ``.``)."""
    found = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            found.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            found.add("." if node.level else (node.module or "").split(".")[0])
    return found


class DocstringCheckerProofTest(unittest.TestCase):
    """:func:`docstring_faults` on sample text, both ways."""

    GOOD = ('"""Stamp a dev version.\n\nRendered into each project by `modelb-axi`; not part of '
            'the\n`modelb_axi` package. Stdlib only.\n"""\n')

    def test_the_conforming_docstring_passes(self):
        self.assertEqual(docstring_faults(self.GOOD), [])

    def test_each_missing_statement_and_the_retired_one_bite(self):
        for bad, fault in (
                (self.GOOD.replace("Rendered into each project", "Copied"), "rendered into"),
                (self.GOOD.replace("not part of", "part of"), "not part of"),
                (self.GOOD.replace("Stdlib only.", "Repo-only. Stdlib only."), "repo-only")):
            with self.subTest(fault=fault):
                faults = docstring_faults(bad)
                self.assertEqual(len(faults), 1, faults)
                self.assertIn(fault, faults[0])


class WorkflowScriptsSourceTest(unittest.TestCase):
    """§S3 — both scripts: no syntax newer than Python 3.12, stdlib imports only, the docstring."""

    def _sources(self):
        for script in (STAMP, SECTION):
            if not script.is_file():
                raise AssertionError(f"§S3: {script.relative_to(REPO_ROOT)} must exist")
            yield script.name, script.read_text(encoding="utf-8")

    def test_each_script_parses_as_python_3_12(self):
        for name, source in self._sources():
            with self.subTest(script=name):
                ast.parse(source, filename=name, feature_version=(3, 12))

    def test_each_script_imports_the_standard_library_only(self):
        for name, source in self._sources():
            with self.subTest(script=name):
                self.assertEqual(sorted(imported_top_levels(source) - sys.stdlib_module_names), [])

    def test_each_docstring_says_rendered_by_modelb_axi_and_not_the_package(self):
        for name, source in self._sources():
            with self.subTest(script=name):
                self.assertEqual(docstring_faults(source), [])


if __name__ == "__main__":
    unittest.main()
