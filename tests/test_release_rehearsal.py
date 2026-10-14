"""The release rehearsal: the version stamp, the ``rehearse`` job, and the workflow readers
(CR-MDB-067 §S1, §S2, §S6).

Contract: ``docs/changes/CR-MDB-067-release-rehearsal-and-ci.md``; rulings in
``docs/research/release-automation-crucible-procedure.md`` § "… at CR-MDB-067's gap analysis".

Class map:

- ``WorkflowReadersProofTest`` — §S6: the readers in ``tests/_helpers.py`` (``_workflow_step``'s
  ``uses`` and ``with``, ``workflow_job_key``, ``workflow_job_permissions``,
  ``workflow_push_triggers``) proved on sample text in both directions.
- ``ActionPinCheckerProofTest`` — §S2: :func:`action_pin_faults` passes a 40-hex SHA with a
  ``# vX.Y.Z`` comment and bites on every other spelling.
- ``StampVersionScriptTest`` — §S1: ``.github/scripts/stamp_version.py``, loaded by path and run as
  the CLI, in a temp tree holding copies of both version files: it stamps a release or hotfix ref,
  and refuses every other ref, run number and committed version with one stderr line, writing
  nothing.
- ``StampVersionScriptSourceTest`` — §S1: stdlib only, parses as Python 3.12.
- ``StampVersionScriptNotShippedTest`` — §S1: in neither the sdist nor the wheel, read from REAL
  artifacts built by ``tests.test_package_publishing``'s fixture.
- ``ReleaseWorkflowTriggersTest`` — §S2: the push triggers, ``create-release``'s ``if:``, and
  ``create-release``, ``publish-pypi`` and ``publish-npm`` otherwise unchanged.
- ``RehearseJobTest`` — §S2: ``rehearse`` replaces ``rehearse-testpypi``; its ``if:``, runner,
  environment, permissions, no ``defaults.run``, no ``shell:``, and its steps in order.
- ``ReleaseWorkflowPinsAndHeaderTest`` — §S2: every action pinned to a SHA with a version
  comment; the header comment.
- ``RehearseStampStepExecutionTest`` — §S2: step 2's command lines EXECUTED under ``bash -e`` in a
  temp tree with ``GITHUB_REF_NAME`` and ``GITHUB_RUN_NUMBER`` set.

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

from tests import test_package_publishing as publishing
from tests._helpers import (
    workflow_job,
    workflow_job_key,
    workflow_job_permissions,
    workflow_push_triggers,
    workflow_steps,
)
from tests.test_pi_package import npm_semver

REPO_ROOT = Path(__file__).resolve().parent.parent
STAMP_REL = ".github/scripts/stamp_version.py"
STAMP = REPO_ROOT / ".github" / "scripts" / "stamp_version.py"
SECTION_REL = ".github/scripts/changelog_section.py"
SECTION = REPO_ROOT / ".github" / "scripts" / "changelog_section.py"
RELEASE_YML = REPO_ROOT / ".github" / "workflows" / "release.yml"
INIT_REL = "modelb_axi/__init__.py"
PACKAGE_JSON_REL = "pi-package/package.json"

_INIT_VERSION = re.compile(r'^__version__ = "[^"]*"$', re.M)
_PACKAGE_VERSION = re.compile(r'^(\s*"version":\s*)"[^"]*"', re.M)


# ------------------------------------------------------------------ §S6 the readers ----

_SHA = "11d5960a326750d5838078e36cf38b85af677262"

SAMPLE_WORKFLOW = f"""\
# A sample workflow, shaped like release.yml.
name: sample

on:
  push:
    tags:
      - "[0-9]+.[0-9]+.[0-9]+"
    branches: ["release/**", "hotfix/**"]
  release:
    types: [published]
    branches:
      - not-a-push-branch
  workflow_dispatch:

permissions:
  contents: read

jobs:
  first:
    if: github.event_name == 'push' && startsWith(github.ref, 'refs/tags/')
    runs-on: ubuntu-latest
    environment: testpypi  # the TestPyPI environment
    permissions:
      contents: read
      id-token: write
    steps:
      - uses: actions/checkout@{_SHA} # v4.4.0
      - name: Upload
        if: always()
        uses: pypa/gh-action-pypi-publish@{_SHA} # v1.13.0
        with:
          repository-url: https://test.pypi.org/legacy/
          skip-existing: true
      - uses: actions/setup-node@{_SHA} # v4.4.0
        with:
          node-version: "22"  # the LTS
      - name: Publish
        working-directory: pi-package
        env:
          TOKEN: from-env
        run: |
          cp ../CHANGELOG.md .
          npm publish --dry-run
  second:
    if: >-
      github.event_name == 'workflow_dispatch' ||
      github.event_name == 'push'
    runs-on: ubuntu-latest
    permissions: read-all
    defaults:
      run:
        working-directory: pi-package
    steps:
      - run: echo hi
  third:
    if: github.event_name == 'workflow_dispatch' ||
      (github.event_name == 'push' && startsWith(github.ref, 'refs/heads/'))
    runs-on: "ubuntu-latest"
    steps:
      - name: A step-level if is not the job's
        if: success()
        environment: not-a-job-key
        run: echo hi
"""


class WorkflowReadersProofTest(unittest.TestCase):
    """§S6 — the workflow readers, proved on sample text both ways; existing keys unchanged."""

    def test_a_uses_step_reads_its_action_without_the_comment_and_no_with(self):
        step = workflow_steps(workflow_job(SAMPLE_WORKFLOW, "first"))[0]
        self.assertEqual(step["uses"], f"actions/checkout@{_SHA}")
        self.assertEqual(step["with"], {})
        self.assertEqual(step["run"], [])
        self.assertIsNone(step["name"])

    def test_a_with_block_reads_as_a_dict_of_its_unquoted_scalars(self):
        steps = workflow_steps(workflow_job(SAMPLE_WORKFLOW, "first"))
        self.assertEqual(steps[1]["uses"], f"pypa/gh-action-pypi-publish@{_SHA}")
        self.assertEqual(steps[1]["name"], "Upload")
        self.assertEqual(steps[1]["with"], {"repository-url": "https://test.pypi.org/legacy/",
                                            "skip-existing": "true"})
        self.assertEqual(steps[2]["with"], {"node-version": "22"},
                         "quotes and the trailing comment go")

    def test_a_run_step_has_no_uses_and_its_env_never_leaks_into_with(self):
        step = workflow_steps(workflow_job(SAMPLE_WORKFLOW, "first"))[3]
        self.assertIsNone(step["uses"])
        self.assertEqual(step["with"], {})
        self.assertEqual(step["run"], ["cp ../CHANGELOG.md .", "npm publish --dry-run"])
        self.assertEqual(step["working-directory"], "pi-package")
        self.assertEqual(step["name"], "Publish")

    def test_the_step_reader_still_returns_the_keys_existing_callers_read(self):
        # MIGRATED at CR-MDB-067 C2 RED (§S3): the step reader also returns ``env`` for §S3's
        # sandbox variables; the five keys existing callers read are unchanged.
        for step in workflow_steps(workflow_job(SAMPLE_WORKFLOW, "first")):
            self.assertEqual(set(step),
                             {"name", "run", "working-directory", "uses", "with", "env"})

    def test_a_job_key_reads_one_line_scalars_without_comment_or_quotes(self):
        first = workflow_job(SAMPLE_WORKFLOW, "first")
        self.assertEqual(workflow_job_key(first, "if"),
                         "github.event_name == 'push' && startsWith(github.ref, 'refs/tags/')")
        self.assertEqual(workflow_job_key(first, "runs-on"), "ubuntu-latest")
        self.assertEqual(workflow_job_key(first, "environment"), "testpypi")
        self.assertEqual(workflow_job_key(workflow_job(SAMPLE_WORKFLOW, "third"), "runs-on"),
                         "ubuntu-latest")

    def test_a_folded_block_and_a_plain_continuation_fold_into_one_line(self):
        self.assertEqual(workflow_job_key(workflow_job(SAMPLE_WORKFLOW, "second"), "if"),
                         "github.event_name == 'workflow_dispatch' || "
                         "github.event_name == 'push'")
        self.assertEqual(workflow_job_key(workflow_job(SAMPLE_WORKFLOW, "third"), "if"),
                         "github.event_name == 'workflow_dispatch' || (github.event_name == "
                         "'push' && startsWith(github.ref, 'refs/heads/'))")

    def test_a_job_key_is_none_when_absent_and_never_read_from_a_step(self):
        first = workflow_job(SAMPLE_WORKFLOW, "first")
        self.assertIsNone(workflow_job_key(first, "timeout-minutes"))
        self.assertIsNone(workflow_job_key(first, "working-directory"),
                          "a step's working-directory is not a job key")
        self.assertIsNone(workflow_job_key(first, "defaults"))
        third = workflow_job(SAMPLE_WORKFLOW, "third")
        self.assertIsNone(workflow_job_key(third, "environment"),
                          "a step's environment line is not a job key")

    def test_a_block_valued_job_key_is_present_but_empty(self):
        self.assertEqual(workflow_job_key(workflow_job(SAMPLE_WORKFLOW, "second"), "defaults"), "")

    def test_job_permissions_read_the_mapping_the_scalar_and_the_absence(self):
        self.assertEqual(workflow_job_permissions(workflow_job(SAMPLE_WORKFLOW, "first")),
                         {"contents": "read", "id-token": "write"})
        self.assertEqual(workflow_job_permissions(workflow_job(SAMPLE_WORKFLOW, "second")),
                         "read-all")
        self.assertIsNone(workflow_job_permissions(workflow_job(SAMPLE_WORKFLOW, "third")),
                          "the workflow-level permissions are not the job's")

    def test_push_triggers_read_block_tags_flow_branches_and_the_events(self):
        self.assertEqual(workflow_push_triggers(SAMPLE_WORKFLOW), {
            "tags": ["[0-9]+.[0-9]+.[0-9]+"],
            "branches": ["release/**", "hotfix/**"],
            "pull_request": False,
            "workflow_dispatch": True,
        })

    def test_push_triggers_read_block_branches_and_a_bare_pull_request(self):
        text = ("name: ci\n"
                "on:\n"
                "  push:\n"
                "    branches:\n"
                "      - develop\n"
                "      - \"release/**\"  # releases\n"
                "      - 'hotfix/**'\n"
                "  pull_request:\n"
                "permissions:\n"
                "  contents: read\n")
        self.assertEqual(workflow_push_triggers(text), {
            "tags": [],
            "branches": ["develop", "release/**", "hotfix/**"],
            "pull_request": True,
            "workflow_dispatch": False,
        })

    def test_other_events_branches_and_pull_request_target_are_not_counted(self):
        text = ("on:\n"
                "  pull_request_target:\n"
                "    branches: [main]\n"
                "  workflow_run:\n"
                "    workflows: [ci]\n")
        self.assertEqual(workflow_push_triggers(text), {
            "tags": [], "branches": [], "pull_request": False, "workflow_dispatch": False})

    def test_the_flow_form_of_on_reads_its_events(self):
        self.assertEqual(workflow_push_triggers("on: [push, workflow_dispatch]\njobs: {}\n"), {
            "tags": [], "branches": [], "pull_request": False, "workflow_dispatch": True})

    def test_a_workflow_with_no_on_key_raises(self):
        with self.assertRaises(AssertionError) as ctx:
            workflow_push_triggers("name: x\njobs:\n  a:\n    runs-on: ubuntu-latest\n")
        self.assertIn("on:", str(ctx.exception))


# ------------------------------------------------------------------ §S2 the pin checker ----

_PIN_LINE = re.compile(r"^\s*(?:-\s+)?uses:\s*(.*?)\s*$")
_PINNED = re.compile(r"[\w.-]+/[\w./-]+@[0-9a-f]{40}\s+# v\d+\.\d+\.\d+")


def action_pin_faults(text: str) -> list[str]:
    """§S2 — every ``uses:`` line of a workflow is pinned to a 40-hex commit SHA with its release
    version in a ``# vX.Y.Z`` comment. One fault per line that is not; ``[]`` when all are."""
    faults = []
    for number, line in enumerate(text.splitlines(), start=1):
        match = _PIN_LINE.match(line)
        if match and not _PINNED.fullmatch(match.group(1)):
            faults.append(f"line {number}: {match.group(1)!r} is not pinned to a SHA with a "
                          "# vX.Y.Z comment")
    return faults


class ActionPinCheckerProofTest(unittest.TestCase):
    """:func:`action_pin_faults` on sample text: the pinned form passes, every other bites."""

    def test_sha_pins_with_version_comments_pass_in_both_step_forms(self):
        text = (f"    steps:\n      - uses: actions/checkout@{_SHA} # v4.4.0\n"
                f"      - name: Up\n        uses: pypa/gh-action-pypi-publish@{_SHA} # v1.13.0\n")
        self.assertEqual(action_pin_faults(text), [])

    def test_every_unpinned_or_uncommented_spelling_bites_once(self):
        for bad in ("actions/checkout@v4",
                    f"actions/checkout@{_SHA}",
                    f"pypa/gh-action-pypi-publish@{_SHA} # release/v1",
                    f"actions/checkout@{_SHA} # v4",
                    f"actions/checkout@{_SHA[:12]} # v4.4.0",
                    "pypa/gh-action-pypi-publish@release/v1 # v1.13.0"):
            with self.subTest(bad=bad):
                faults = action_pin_faults(f"    steps:\n      - uses: {bad}\n")
                self.assertEqual(len(faults), 1, faults)
                self.assertIn(bad, faults[0])


# ------------------------------------------------------------------ §S1 the stamp ----

def _require_stamp() -> None:
    if not STAMP.is_file():
        raise AssertionError(f"§S1: {STAMP_REL} must exist")


def _version_files(version: str, npm_version: str) -> tuple[str, str]:
    """Copies of the real ``modelb_axi/__init__.py`` and ``pi-package/package.json`` with their
    versions set to ``version`` and ``npm_version``."""
    init, count = _INIT_VERSION.subn(f'__version__ = "{version}"',
                                     (REPO_ROOT / INIT_REL).read_text(encoding="utf-8"))
    if count != 1:
        raise AssertionError(f"{INIT_REL} must hold one __version__ line; found {count}")
    package, count = _PACKAGE_VERSION.subn(rf'\g<1>"{npm_version}"',
                                           (REPO_ROOT / PACKAGE_JSON_REL).read_text(encoding="utf-8"),
                                           count=1)
    if count != 1:
        raise AssertionError(f"{PACKAGE_JSON_REL} must hold a version")
    return init, package


def _stamped(init: str, package: str, release: str, run: str) -> tuple[bytes, bytes]:
    """The bytes §S1 leaves: only the two version values changed."""
    new_init, n = re.subn(rf'^__version__ = "{re.escape(release)}"$',
                          f'__version__ = "{release}.dev{run}"', init, count=1, flags=re.M)
    new_package, m = re.subn(rf'"version": "{re.escape(release)}"',
                             f'"version": "{release}-dev.{run}"', package, count=1)
    assert n == m == 1
    return new_init.encode("utf-8"), new_package.encode("utf-8")


def _tree(test: unittest.TestCase, init: str, package: str, changelog: str | None = None) -> Path:
    """A temp repository tree holding the two version files, a copy of each script that exists,
    and ``CHANGELOG.md`` when given."""
    tree = Path(tempfile.mkdtemp(prefix="stamp-version-"))
    test.addCleanup(shutil.rmtree, tree, True)
    (tree / "modelb_axi").mkdir()
    (tree / "pi-package").mkdir()
    (tree / ".github" / "scripts").mkdir(parents=True)
    (tree / INIT_REL).write_bytes(init.encode("utf-8"))
    (tree / PACKAGE_JSON_REL).write_bytes(package.encode("utf-8"))
    for script, rel in ((STAMP, STAMP_REL), (SECTION, SECTION_REL)):
        if script.is_file():
            shutil.copy2(script, tree / rel)
    if changelog is not None:
        (tree / "CHANGELOG.md").write_text(changelog, encoding="utf-8")
    return tree


def _files(tree: Path) -> tuple[bytes, bytes]:
    return (tree / INIT_REL).read_bytes(), (tree / PACKAGE_JSON_REL).read_bytes()


# CR-MDB-067 C5 RED (VERIFY F1)
def _nested_version_first(package: str, nested: str) -> str:
    """``package`` with an ``engines`` object, whose ``"version": "<nested>"`` sits on its own
    line, inserted after the ``name`` line, so it precedes the top-level ``version`` line. §S1's
    ``version`` is ``package.json``'s top-level key; a nested key on its own line must not be the
    one checked or stamped."""
    lines = package.splitlines(keepends=True)
    name = next((i for i, line in enumerate(lines) if line.startswith('  "name":')), None)
    top = next((i for i, line in enumerate(lines) if line.startswith('  "version":')), None)
    if name is None or top is None or name > top:
        raise AssertionError(f"{PACKAGE_JSON_REL} must hold a name line before its version line")
    block = ['  "engines": {\n', f'    "version": "{nested}"\n', '  },\n']
    sample = "".join(lines[:name + 1] + block + lines[name + 1:])
    first = re.search(r'^\s*"version":\s*"([^"]*)"', sample, re.M)
    if first is None or first.group(1) != nested:
        raise AssertionError("the nested version line must be the first version line")
    return sample


def run_stamp_by_path(tree: Path, ref: str, run: str) -> tuple[int, str, str]:
    """Load the tree's copy of the script by path and run it as ``__main__`` from the tree's root
    with ``argv = [script, ref, run]``. ``(exit code, stdout, stderr)`` as the interpreter would
    give them: ``SystemExit(None)`` is 0, an int is itself, anything else goes to stderr and is 1."""
    _require_stamp()
    script = tree / STAMP_REL
    spec = importlib.util.spec_from_file_location("__main__", script)
    if spec is None or spec.loader is None:
        raise AssertionError(f"§S1: {STAMP_REL} cannot be loaded by path")
    loader = spec.loader
    module = importlib.util.module_from_spec(spec)
    out_bytes, err_bytes = io.BytesIO(), io.BytesIO()
    out = io.TextIOWrapper(out_bytes, encoding="utf-8", newline="")
    err = io.TextIOWrapper(err_bytes, encoding="utf-8", newline="")
    saved_argv, saved_cwd = sys.argv, os.getcwd()
    sys.argv = [str(script), ref, run]
    code = 0
    try:
        os.chdir(tree)
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                loader.exec_module(module)
            except SystemExit as exc:
                if exc.code is None:
                    code = 0
                elif isinstance(exc.code, int):
                    code = exc.code
                else:
                    print(exc.code, file=err)
                    code = 1
    finally:
        sys.argv = saved_argv
        os.chdir(saved_cwd)
    out.flush()
    err.flush()
    return code, out_bytes.getvalue().decode("utf-8"), err_bytes.getvalue().decode("utf-8")


def run_stamp_cli(tree: Path, ref: str, run: str) -> tuple[int, str, str]:
    """``python3 .github/scripts/stamp_version.py <ref> <run-number>`` from the tree's root — §S1's
    calling form."""
    _require_stamp()
    result = subprocess.run(
        [sys.executable, STAMP_REL, ref, run], cwd=tree,
        capture_output=True, text=True, encoding="utf-8", timeout=30, stdin=subprocess.DEVNULL,
    )
    return result.returncode, result.stdout, result.stderr


RUNNERS = (("loaded by path", run_stamp_by_path), ("the CLI", run_stamp_cli))

#: §S1 AC — refs of another form than ``release/X.Y.Z`` or ``hotfix/X.Y.Z``.
REFUSED_REFS = ("develop", "feature/x", "release/1.2", "release/v1.2.3", "release/01.2.3", "1.2.3")
#: §S1 AC — run numbers of another form than ``[1-9][0-9]*``.
REFUSED_RUNS = ("0", "-1", "x", "07")


class StampVersionScriptTest(unittest.TestCase):
    """§S1 — the script stamps ``X.Y.Z.devN`` and ``X.Y.Z-dev.N``, prints ``X.Y.Z``, or refuses
    with one stderr line, exit 1, both files untouched."""

    def _assert_stamps(self, ref: str, release: str, run: str, init: str, package: str):
        expected = _stamped(init, package, release, run)
        for label, runner in RUNNERS:
            with self.subTest(runner=label):
                tree = _tree(self, init, package)
                code, out, err = runner(tree, ref, run)
                self.assertEqual(code, 0, f"stderr={err!r}")
                self.assertIn(out, (release, release + "\n"),
                              f"§S1: prints {release} on stdout; got {out!r}")
                self.assertEqual(_files(tree), expected,
                                 "§S1: only the two version values change, every other byte stays")

    def test_a_release_ref_stamps_both_files_and_prints_the_release_version(self):
        init, package = _version_files("1.2.3", "1.2.3")
        self._assert_stamps("release/1.2.3", "1.2.3", "7", init, package)

    def test_a_hotfix_ref_stamps_the_same_way(self):
        init, package = _version_files("1.2.4", "1.2.4")
        self._assert_stamps("hotfix/1.2.4", "1.2.4", "7", init, package)

    def test_only_the_two_version_values_change_when_the_release_appears_elsewhere(self):
        init, package = _version_files("1.2.3", "1.2.3")
        init += '\n_PREVIOUS = "1.2.3"  # not the version\n'
        package = package.replace('"keywords"', '"engines": {"version": "1.2.3"},\n  "keywords"', 1)
        self.assertIn('"engines": {"version": "1.2.3"}', package)
        self._assert_stamps("release/1.2.3", "1.2.3", "7", init, package)

    def test_the_stamped_versions_are_the_pep_440_and_npm_dev_forms(self):
        init, package = _version_files("1.2.3", "1.2.3")
        tree = _tree(self, init, package)
        code, _out, err = run_stamp_cli(tree, "release/1.2.3", "7")
        self.assertEqual(code, 0, f"stderr={err!r}")
        self.assertIn('__version__ = "1.2.3.dev7"', (tree / INIT_REL).read_text(encoding="utf-8"))
        self.assertIn('"version": "1.2.3-dev.7"',
                      (tree / PACKAGE_JSON_REL).read_text(encoding="utf-8"))

    def test_the_npm_form_is_npm_semver_of_the_pep_440_form(self):
        for run in ("1", "7", "123"):
            with self.subTest(run=run):
                init, package = _version_files("1.2.3", "1.2.3")
                tree = _tree(self, init, package)
                code, _out, err = run_stamp_cli(tree, "release/1.2.3", run)
                self.assertEqual(code, 0, f"stderr={err!r}")
                pep = re.search(r'^__version__ = "([^"]*)"$',
                                (tree / INIT_REL).read_text(encoding="utf-8"), re.M)
                npm = re.search(r'^\s*"version":\s*"([^"]*)"',
                                (tree / PACKAGE_JSON_REL).read_text(encoding="utf-8"), re.M)
                if pep is None or npm is None:
                    self.fail(f"§S1: both files keep their version line; got {pep!r}, {npm!r}")
                pep_version, npm_version = pep.group(1), npm.group(1)
                self.assertEqual(pep_version, f"1.2.3.dev{run}")
                self.assertEqual(npm_version, npm_semver(pep_version))

    def _assert_refuses(self, ref: str, run: str, init: str, package: str, *named: str):
        for label, runner in RUNNERS:
            with self.subTest(runner=label, ref=ref, run=run, named=named):
                tree = _tree(self, init, package)
                before = _files(tree)
                code, out, err = runner(tree, ref, run)
                self.assertEqual(code, 1, f"§S1: a refusal exits 1; stderr={err!r}")
                lines = err.splitlines()
                self.assertEqual(len(lines), 1, f"§S1: exactly one stderr line; got {err!r}")
                for name in named:
                    self.assertIn(name, lines[0], f"§S1: the line names {name!r}")
                self.assertEqual(out, "", "§S1: a refusal prints no version")
                self.assertEqual(_files(tree), before, "§S1: a refusal writes nothing")

    def test_every_other_ref_form_is_refused_naming_the_ref(self):
        init, package = _version_files("1.2.3", "1.2.3")
        for ref in REFUSED_REFS:
            self._assert_refuses(ref, "7", init, package, ref)

    def test_every_other_run_number_form_is_refused_naming_it(self):
        init, package = _version_files("1.2.3", "1.2.3")
        for run in REFUSED_RUNS:
            self._assert_refuses("release/1.2.3", run, init, package, run)

    def test_a_committed_version_other_than_the_refs_is_refused_naming_file_found_and_wanted(self):
        for found in ("1.2.2", "1.2.3.dev0"):
            init, package = _version_files(found, "1.2.3")
            self._assert_refuses("release/1.2.3", "7", init, package, INIT_REL, found, "1.2.3")

    def test_a_package_json_version_other_than_the_refs_is_refused_naming_file_found_and_wanted(self):
        for found in ("1.2.2", "1.2.3-dev.0"):
            init, package = _version_files("1.2.3", found)
            self._assert_refuses("hotfix/1.2.3", "7", init, package, PACKAGE_JSON_REL, found,
                                 "1.2.3")

    # CR-MDB-067 C5 RED (VERIFY F1) — §S1: the checked and stamped ``version`` is package.json's
    # top-level key, never a nested ``"version"`` that starts a line above it.
    def test_a_nested_version_on_its_own_line_above_the_top_level_one_is_left_unstamped(self):
        init, package = _version_files("1.2.3", "1.2.3")
        package = _nested_version_first(package, "9.9.9")
        self._assert_stamps("release/1.2.3", "1.2.3", "7", init, package)
        tree = _tree(self, init, package)
        code, _out, err = run_stamp_cli(tree, "release/1.2.3", "7")
        self.assertEqual(code, 0, f"§S1: the top-level version is checked; stderr={err!r}")
        stamped = (tree / PACKAGE_JSON_REL).read_text(encoding="utf-8")
        self.assertIn('  "engines": {\n    "version": "9.9.9"\n  },\n  "version": "1.2.3-dev.7",\n',
                      stamped, "§S1: the nested 9.9.9 stays; the top-level version is stamped")
        self.assertEqual(stamped.count("-dev.7"), 1, "§S1: exactly one value is stamped")

    # CR-MDB-067 C5 RED (VERIFY F1) — §S1: a nested ``X.Y.Z`` never satisfies the check.
    def test_a_nested_matching_version_does_not_satisfy_a_mismatched_top_level_one(self):
        for found in ("1.2.2", "1.2.3-dev.0"):
            init, package = _version_files("1.2.3", found)
            package = _nested_version_first(package, "1.2.3")
            self._assert_refuses("release/1.2.3", "7", init, package, PACKAGE_JSON_REL, found,
                                 "1.2.3")


class StampVersionScriptSourceTest(unittest.TestCase):
    """§S1 — stdlib only, and no syntax newer than Python 3.12 (the hosted runner's default)."""

    def test_the_script_parses_as_python_3_12(self):
        _require_stamp()
        ast.parse(STAMP.read_text(encoding="utf-8"), filename=STAMP_REL, feature_version=(3, 12))

    def test_the_script_imports_the_standard_library_only(self):
        _require_stamp()
        imported = set()
        for node in ast.walk(ast.parse(STAMP.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                self.assertEqual(node.level, 0, "§S1: the script imports nothing relative")
                imported.add((node.module or "").split(".")[0])
        self.assertEqual(sorted(imported - sys.stdlib_module_names), [])


def tearDownModule():
    # The artifacts are tests.test_package_publishing's, cached on that module: remove the build
    # and drop the cache, so that module rebuilds rather than reading a removed directory.
    publishing.tearDownModule()
    publishing._BUILD_ROOT = None


class StampVersionScriptNotShippedTest(unittest.TestCase):
    """§S1 — a repo-only script: neither the sdist nor the wheel carries it."""

    def test_neither_the_sdist_nor_the_wheel_carries_the_script(self):
        _require_stamp()  # otherwise "not shipped" would hold of nothing
        sdist, wheel = publishing.artifacts()
        offenders = [f"sdist:{rel}" for rel in publishing.sdist_members(sdist)
                     if rel.startswith(".github/") or rel.endswith("stamp_version.py")]
        offenders += [f"wheel:{name}" for name in publishing.wheel_names(wheel)
                      if ".github" in name.split("/") or name.endswith("stamp_version.py")]
        self.assertEqual(offenders, [])


# ------------------------------------------------------------------ §S2 the workflow ----

_TAG_PATTERN = "[0-9]+.[0-9]+.[0-9]+"
CREATE_RELEASE_IF = "github.event_name == 'push' && startsWith(github.ref, 'refs/tags/')"
REHEARSE_IF = ("github.event_name == 'workflow_dispatch' || (github.event_name == 'push' && "
               "startsWith(github.ref, 'refs/heads/'))")
STAMP_LINE = ('version=$(python3 .github/scripts/stamp_version.py "$GITHUB_REF_NAME" '
              '"$GITHUB_RUN_NUMBER")')
_NOTES_CHECK = re.compile(
    r'python3 \.github/scripts/changelog_section\.py CHANGELOG\.md "\$version" *1?> */dev/null')
NPM_DRY_RUN = "npm publish --dry-run --access public --tag dev"

#: Today's jobs, read with every ``uses:`` reduced to its action name (§S2 re-pins actions and
#: leaves these jobs otherwise unchanged). ``create-release`` is without its ``if:`` line.
CREATE_RELEASE_TODAY = """\
  create-release:
    runs-on: ubuntu-latest
    permissions:
      contents: write
    steps:
      - uses: actions/checkout
      - name: Tag matches the package version
        run: |
          python3 - <<'PY'
          import os, pathlib, re, sys
          text = pathlib.Path("modelb_axi/__init__.py").read_text()
          version = re.search(r'__version__\\s*=\\s*"([^"]+)"', text)[1]
          tag = os.environ["GITHUB_REF_NAME"]
          if version != tag:
              sys.exit(f"tag {tag} != __version__ {version}")
          PY
      - name: Create the GitHub Release
        env:
          GH_TOKEN: ${{ secrets.RELEASE_PAT }}
          TAG: ${{ github.ref_name }}
        run: |
          python3 .github/scripts/changelog_section.py CHANGELOG.md "$TAG" > "$RUNNER_TEMP/notes.md"
          if ! gh release view "$TAG" >/dev/null 2>&1; then
            gh release create "$TAG" --notes-file "$RUNNER_TEMP/notes.md" --verify-tag
          fi"""

PUBLISH_PYPI_TODAY = """\
  publish-pypi:
    if: github.event_name == 'release'
    runs-on: ubuntu-latest
    environment: pypi
    permissions:
      id-token: write
    steps:
      - uses: actions/checkout
      - uses: astral-sh/setup-uv
      - run: uv build
      - uses: pypa/gh-action-pypi-publish"""

PUBLISH_NPM_TODAY = """\
  publish-npm:
    if: github.event_name == 'release'
    runs-on: ubuntu-latest
    environment: npm
    permissions:
      contents: read
      id-token: write
    defaults:
      run:
        working-directory: pi-package
    steps:
      - uses: actions/checkout
      - uses: actions/setup-node
        with:
          node-version: "22"
          registry-url: https://registry.npmjs.org
      - name: npm new enough for Trusted Publishing
        run: npm install -g npm@latest
      - name: Ship the root CHANGELOG.md in the package
        run: cp ../CHANGELOG.md .
      - name: Publish
        env:
          NODE_AUTH_TOKEN: ${{ secrets.NPM_TOKEN }}
        run: npm publish --provenance --access public"""


def _unpinned(lines: list[str]) -> list[str]:
    """``lines`` without blank or comment-only lines, each ``uses:`` reduced to its action."""
    out = []
    for line in lines:
        if not line.strip() or line.strip().startswith("#"):
            continue
        out.append(re.sub(r"(uses:\s*[^@\s]+)@\S+(\s+#.*)?$", r"\1", line.rstrip()))
    return out


def _without_job_key(job: list[str], key: str) -> list[str]:
    """``job`` without its job-level ``key:`` line and that key's continuation lines."""
    base = len(job[0]) - len(job[0].lstrip()) + 2
    out, skipping = [], False
    for line in job:
        indent = len(line) - len(line.lstrip())
        if line.strip() and indent == base:
            skipping = re.match(rf"\s*{re.escape(key)}:", line) is not None
        elif line.strip() and indent < base:
            skipping = False
        if not skipping:
            out.append(line)
    return out


def _release_text() -> str:
    return RELEASE_YML.read_text(encoding="utf-8")


def _header(text: str) -> str:
    """The leading comment block, as one lower-cased line with whitespace collapsed."""
    words = []
    for line in text.splitlines():
        if not line.strip():
            continue
        if not line.startswith("#"):
            break
        words.append(line[1:].strip())
    return " ".join(" ".join(words).split()).lower()


class ReleaseWorkflowTriggersTest(unittest.TestCase):
    """§S2 — the triggers, ``create-release``'s ``if:``, and the publish jobs unchanged."""

    def test_push_triggers_are_the_tag_pattern_and_exactly_release_and_hotfix_branches(self):
        triggers = workflow_push_triggers(_release_text())
        self.assertEqual(triggers["tags"], [_TAG_PATTERN], "§S2: on.push keeps the tag pattern")
        self.assertEqual(sorted(triggers["branches"]), ["hotfix/**", "release/**"],
                         "§S2: on.push gains exactly release/** and hotfix/**")

    def test_workflow_dispatch_stays(self):
        # Regression pin: holds today; fails the moment the dispatch trigger is dropped.
        self.assertTrue(workflow_push_triggers(_release_text())["workflow_dispatch"])

    def test_create_release_runs_only_on_a_tag_push(self):
        job = workflow_job(_release_text(), "create-release")
        self.assertEqual(" ".join((workflow_job_key(job, "if") or "").split()), CREATE_RELEASE_IF)

    def test_create_release_is_otherwise_unchanged(self):
        # Regression pin: holds today; fails if a step, the runner or the permissions change.
        job = _without_job_key(workflow_job(_release_text(), "create-release"), "if")
        self.assertEqual(_unpinned(job), CREATE_RELEASE_TODAY.splitlines())

    def test_publish_pypi_is_unchanged_but_for_its_pins(self):
        # Regression pin: holds today; fails if anything but an action's pin changes.
        job = workflow_job(_release_text(), "publish-pypi")
        self.assertEqual(_unpinned(job), PUBLISH_PYPI_TODAY.splitlines())

    def test_publish_npm_is_unchanged_but_for_its_pins(self):
        # Regression pin: holds today; fails if anything but an action's pin changes.
        job = workflow_job(_release_text(), "publish-npm")
        self.assertEqual(_unpinned(job), PUBLISH_NPM_TODAY.splitlines())


class RehearseJobTest(unittest.TestCase):
    """§S2 — ``rehearse`` replaces ``rehearse-testpypi``: its keys and its six steps in order."""

    @classmethod
    def setUpClass(cls):
        cls.text = _release_text()

    def _job(self) -> list[str]:
        return workflow_job(self.text, "rehearse")

    def _steps(self) -> list[dict]:
        return workflow_steps(self._job())

    def test_there_is_no_rehearse_testpypi_job(self):
        self.assertNotIn("rehearse-testpypi", self.text)

    def test_rehearse_runs_on_a_dispatch_or_a_branch_push(self):
        value = workflow_job_key(self._job(), "if") or ""
        self.assertEqual(" ".join(value.split()), REHEARSE_IF)

    def test_rehearse_runs_on_ubuntu_latest_in_the_testpypi_environment(self):
        job = self._job()
        self.assertEqual(workflow_job_key(job, "runs-on"), "ubuntu-latest")
        self.assertEqual(workflow_job_key(job, "environment"), "testpypi")

    def test_rehearse_permissions_are_contents_read_and_id_token_write(self):
        self.assertEqual(workflow_job_permissions(self._job()),
                         {"contents": "read", "id-token": "write"})

    def test_rehearse_has_no_job_defaults_and_no_step_shell(self):
        job = self._job()
        self.assertIsNone(workflow_job_key(job, "defaults"), "§S2: no job-level defaults.run")
        shells = [line.strip() for line in job if re.match(r"\s*(?:-\s+)?shell:", line)]
        self.assertEqual(shells, [], "§S2: no shell: on any step")

    def test_step_1_is_the_checkout(self):
        step = self._steps()[0]
        self.assertTrue((step["uses"] or "").startswith("actions/checkout@"), step)

    def test_step_2_stamps_then_checks_the_notes_in_one_run_step(self):
        step = self._steps()[1]
        self.assertIsNone(step["uses"])
        lines = [line.strip() for line in step["run"] if not line.strip().startswith("#")]
        self.assertEqual(len(lines), 2, f"§S2: two command lines; got {lines!r}")
        self.assertEqual(lines[0], STAMP_LINE, "§S2: the stamp line stands alone, first")
        self.assertRegex(lines[1], _NOTES_CHECK.pattern + "$",
                         "§S2: the notes check on $version, stdout to /dev/null")

    def test_step_3_sets_up_uv_then_builds(self):
        steps = self._steps()
        self.assertTrue((steps[2]["uses"] or "").startswith("astral-sh/setup-uv@"), steps[2])
        self.assertEqual(steps[3]["run"], ["uv build"])
        self.assertIsNone(steps[3]["uses"])

    def test_step_4_uploads_to_testpypi_skipping_existing_files(self):
        step = self._steps()[4]
        self.assertTrue((step["uses"] or "").startswith("pypa/gh-action-pypi-publish@"), step)
        self.assertEqual(step["with"].get("repository-url"), "https://test.pypi.org/legacy/")
        self.assertEqual(step["with"].get("skip-existing"), "true")

    def test_step_5_sets_up_node_22_then_updates_npm(self):
        steps = self._steps()
        self.assertTrue((steps[5]["uses"] or "").startswith("actions/setup-node@"), steps[5])
        self.assertEqual(steps[5]["with"].get("node-version"), "22")
        self.assertEqual(steps[6]["run"], ["npm install -g npm@latest"])

    def test_step_6_copies_the_changelog_then_dry_runs_the_publish_from_pi_package(self):
        tail = [(step["working-directory"], line.strip())
                for step in self._steps()[7:] for line in step["run"]
                if line.strip() and not line.strip().startswith("#")]
        self.assertEqual(tail, [("pi-package", "cp ../CHANGELOG.md ."),
                                ("pi-package", NPM_DRY_RUN)])
        self.assertTrue(all(step["uses"] is None for step in self._steps()[7:]),
                        "§S2: nothing follows the dry-run publish")


class ReleaseWorkflowPinsAndHeaderTest(unittest.TestCase):
    """§S2 — every action pinned to a SHA with its version comment; the header comment."""

    def test_every_action_is_pinned_to_a_sha_with_a_version_comment(self):
        text = _release_text()
        self.assertTrue(any(_PIN_LINE.match(line) for line in text.splitlines()))
        self.assertEqual(action_pin_faults(text), [])

    def test_the_header_names_release_and_hotfix_pushes(self):
        self.assertIn("release or hotfix push", _header(_release_text()))

    def test_the_header_no_longer_says_a_manual_run_rehearses_the_python_upload(self):
        self.assertNotIn("rehearses the python upload", _header(_release_text()))

    def test_the_setup_list_says_testpypi_admits_release_and_hotfix_with_no_reviewers(self):
        header = _header(_release_text())
        self.assertIn("one-time setup", header)
        setup = header.split("one-time setup", 1)[1]
        for needle in ("testpypi", "release/**", "hotfix/**", "no required reviewers"):
            self.assertIn(needle, setup, f"§S2: the setup list names {needle!r}")


CHANGELOG_PREAMBLE = (
    "# Changelog\n\n"
    "All notable changes to this project are documented in this file.\n\n"
    "## [Unreleased]\n\n"
)
CHANGELOG_GOOD = CHANGELOG_PREAMBLE + (
    "## [1.2.3] - 2026-10-14\n\n### Added\n\n- The rehearsed release — its notes body.\n\n"
    "## [1.2.2] - 2026-10-01\n\n### Fixed\n\n- An earlier fix.\n"
)
CHANGELOG_MISSING = CHANGELOG_PREAMBLE + (
    "## [1.2.2] - 2026-10-01\n\n### Fixed\n\n- An earlier fix.\n"
)
CHANGELOG_EMPTY = CHANGELOG_PREAMBLE + (
    "## [1.2.3] - 2026-10-14\n\n### Added\n\n"
    "## [1.2.2] - 2026-10-01\n\n### Fixed\n\n- An earlier fix.\n"
)


class RehearseStampStepExecutionTest(unittest.TestCase):
    """§S2 — step 2's command lines, run under ``bash -e`` (a step without ``shell:``) in a temp
    tree with ``GITHUB_REF_NAME`` and ``GITHUB_RUN_NUMBER`` set."""

    def _execute(self, ref: str, changelog: str) -> tuple[subprocess.CompletedProcess, Path]:
        steps = workflow_steps(workflow_job(_release_text(), "rehearse"))
        hits = [step for step in steps if any(STAMP_REL in line for line in step["run"])]
        self.assertEqual(len(hits), 1, f"§S2: one run step stamps the version; found {len(hits)}")
        _require_stamp()
        init, package = _version_files("1.2.3", "1.2.3")
        tree = _tree(self, init, package, changelog)
        home = tree / "home"
        home.mkdir()
        env = dict(os.environ, GITHUB_REF_NAME=ref, GITHUB_RUN_NUMBER="7",
                   GITHUB_WORKSPACE=str(tree), HOME=str(home))
        result = subprocess.run(
            ["bash", "--noprofile", "--norc", "-e", "-c", "\n".join(hits[0]["run"]) + "\n"],
            cwd=tree, env=env, capture_output=True, text=True, encoding="utf-8", timeout=60,
            stdin=subprocess.DEVNULL,
        )
        return result, tree

    def test_a_good_ref_and_section_exit_0_with_both_files_stamped(self):
        result, tree = self._execute("release/1.2.3", CHANGELOG_GOOD)
        self.assertEqual(result.returncode, 0, f"stderr={result.stderr!r}")
        self.assertIn('__version__ = "1.2.3.dev7"', (tree / INIT_REL).read_text(encoding="utf-8"))
        self.assertIn('"version": "1.2.3-dev.7"',
                      (tree / PACKAGE_JSON_REL).read_text(encoding="utf-8"))
        self.assertNotIn("its notes body", result.stdout, "§S2: the notes go to /dev/null")

    def test_a_refused_ref_fails_at_the_stamp_before_the_notes_check(self):
        result, tree = self._execute("feature/x", CHANGELOG_GOOD)
        self.assertNotEqual(result.returncode, 0, "§S2: a refusing stamp fails the step")
        self.assertIn("feature/x", result.stderr)
        self.assertNotIn("no section for tag", result.stderr,
                         "§S2: the step stops at the stamp, before the notes check")
        self.assertEqual(_files(tree), tuple(s.encode("utf-8") for s in
                                             _version_files("1.2.3", "1.2.3")))

    def test_a_missing_section_fails_the_step_naming_the_changelog(self):
        result, _tree_ = self._execute("release/1.2.3", CHANGELOG_MISSING)
        self.assertNotEqual(result.returncode, 0, "§S2: a missing section fails the step")
        self.assertIn("CHANGELOG.md", result.stderr)

    def test_an_empty_section_fails_the_step_naming_the_changelog(self):
        result, _tree_ = self._execute("release/1.2.3", CHANGELOG_EMPTY)
        self.assertNotEqual(result.returncode, 0, "§S2: an empty section fails the step")
        self.assertIn("CHANGELOG.md", result.stderr)


if __name__ == "__main__":
    unittest.main()
