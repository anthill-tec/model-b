"""The release rehearsal: the version stamp, the ``rehearse`` job, and the workflow readers
(CR-MDB-067 §S1, §S2, §S6); the one release workflow whose test job gates every publish
(CR-MDB-070 §S1–§S5, §S7).

Contract: ``docs/changes/CR-MDB-067-release-rehearsal-and-ci.md``; rulings in
``docs/research/release-automation-crucible-procedure.md`` § "… at CR-MDB-067's gap analysis".
``docs/changes/CR-MDB-070-one-workflow-tests-gate-every-publish.md`` reshapes the triggers,
``create-release`` (now on the ``master`` push), the rehearsal's ``if:``, the guarded registry
publishes and the header; the test job itself is read by ``tests.test_ci_workflow``.

Class map:

- ``WorkflowReadersProofTest`` — §S6: the readers in ``tests/_helpers.py`` (``_workflow_step``'s
  ``uses`` and ``with``, ``workflow_job_key``, ``workflow_job_permissions``,
  ``workflow_push_triggers``) proved on sample text in both directions; CR-MDB-070 §S7 adds a
  step's ``id`` and step-level ``if`` and the ``release`` event's types.
- ``ActionPinCheckerProofTest`` — §S2: :func:`action_pin_faults` passes a 40-hex SHA with a
  ``# vX.Y.Z`` comment and bites on every other spelling.
- ``StampVersionScriptTest`` — §S1: ``.github/scripts/stamp_version.py``, loaded by path and run as
  the CLI, in a temp tree holding copies of both version files: it stamps a release or hotfix ref,
  and refuses every other ref, run number and committed version with one stderr line, writing
  nothing.
- ``StampVersionScriptSourceTest`` — §S1: stdlib only, parses as Python 3.12.
- ``StampVersionScriptNotShippedTest`` — §S1: in neither the sdist nor the wheel, read from REAL
  artifacts built by ``tests.test_package_publishing``'s fixture.
- ``ReleaseWorkflowTriggersTest`` — CR-MDB-070 §S1 (MIGRATED at CR-MDB-070 C1 RED, §S1): the
  ``master``, ``release/**`` and ``hotfix/**`` pushes, the published release, dispatch; no tag
  pattern, no ``pull_request``.
- ``CreateReleaseJobTest`` — CR-MDB-070 §S2: ``create-release``'s ``if:``, ``needs: test``,
  permissions, no ``shell:``, and its four steps (checkout with full history, ``id: tag``, the
  version check and the release step, both guarded on the tag).
- ``PublishJobsGuardTest`` — CR-MDB-070 §S4: ``publish-pypi`` and ``publish-npm`` need the tests,
  check out with full history first, guard second, then the baseline's steps unchanged.
- ``RehearseJobTest`` — §S2: ``rehearse`` replaces ``rehearse-testpypi``; its ``if:`` (CR-MDB-070
  §S3: release and hotfix refs only), ``needs: test``, runner, environment, permissions, no
  ``defaults.run``, no ``shell:``, and its steps in order.
- ``ReleaseWorkflowPinsAndHeaderTest`` — §S2: every action pinned to a SHA with a version
  comment; the header comment (CR-MDB-070 §S5's phrases). CR-MDB-070 C4 RED (VERIFY F6): one
  header unit says a red ``master`` or release run publishes nothing, to re-run the failed jobs,
  and that a real failure is fixed on a hotfix branch (:func:`header_red_run_faults`).
- ``HeaderRedRunCheckerProofTest`` — CR-MDB-070 C4 RED (VERIFY F6): :func:`header_red_run_faults`
  proved both ways on sample text.
- ``SkillReleaseSnippetExecutionTest`` — CR-MDB-070 C4 RED (VERIFY F1): the git-workflow skill's
  release-job snippet's release step EXECUTED under ``bash -e`` in a temp git repository with a
  ``gh`` shim first on ``PATH``: two version tags at ``HEAD`` fail naming both, one with its
  section reaches ``gh release create``, none exits 0 with nothing to release; its
  ``SkillReleaseSnippetConformingSampleProofTest`` runs it on :data:`CONFORMING_SKILL_SNIPPET`
  and ``SkillReleaseSnippetBiteProofTest`` shows it bites without the count.
- ``RehearseStampStepExecutionTest`` — §S2: step 2's command lines EXECUTED under ``bash -e`` in a
  temp tree with ``GITHUB_REF_NAME`` and ``GITHUB_RUN_NUMBER`` set.
- ``CreateReleaseTagStepExecutionTest`` — CR-MDB-070 §S2: the ``id: tag`` step EXECUTED under
  ``bash -e`` in a temp git repository with ``GITHUB_OUTPUT`` at a temp file.
- ``CreateReleaseVersionCheckExecutionTest`` — CR-MDB-070 §S2: the version check EXECUTED, reading
  ``TAG`` while ``GITHUB_REF_NAME`` is ``master``.
- ``PublishGuardExecutionTest`` — CR-MDB-070 §S4: each publish job's guard EXECUTED under
  ``bash -e`` in a clone of a bare ``origin``.

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
    workflow_job_working_directory,
    workflow_push_triggers,
    workflow_steps,
)
from tests.test_board_holds_the_queue import norm_units
from tests.test_install_guide import GIT_WORKFLOW_SKILL, release_job_snippet
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


#: CR-MDB-070 §S7 — a step's ``id`` and step-level ``if`` beside a job's and a ``with:``/``env:``
#: key of the same names.
SAMPLE_STEP_KEYS = f"""\
jobs:
  only:
    if: github.event_name == 'push'
    id: not-a-step-id
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@{_SHA} # v4.4.0
        with:
          id: not-the-step-id
          if: not-the-step-if
      - id: tag
        run: echo tag
      - name: Guarded
        id: "check"  # quoted, commented
        if: steps.tag.outputs.tag != ''
        env:
          if: not-the-step-if
          TAG: ${{{{ steps.tag.outputs.tag }}}}
        run: |
          echo "$TAG"
      - name: Folded
        if: >-
          github.event_name == 'push' &&
          success()
        run: echo folded
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
        # MIGRATED at CR-MDB-070 C1 RED (§S7): it also returns the step's ``id`` and step-level
        # ``if``; the six keys existing callers read are unchanged.
        for step in workflow_steps(workflow_job(SAMPLE_WORKFLOW, "first")):
            self.assertEqual(set(step), {"name", "run", "working-directory", "uses", "with",
                                         "env", "id", "if"})

    # CR-MDB-070 C1 RED (§S7) — a step's ``id`` and step-level ``if``, both ways.
    def test_a_step_level_if_reads_as_the_steps_and_never_the_jobs(self):
        first = workflow_steps(workflow_job(SAMPLE_WORKFLOW, "first"))
        self.assertEqual([step["if"] for step in first], [None, "always()", None, None])
        third = workflow_steps(workflow_job(SAMPLE_WORKFLOW, "third"))
        self.assertEqual(third[0]["if"], "success()", "the step's if:, not the job's")

    def test_a_step_id_reads_from_the_dash_line_or_a_later_key_without_quotes_or_comment(self):
        steps = workflow_steps(workflow_job(SAMPLE_STEP_KEYS, "only"))
        self.assertEqual([step["id"] for step in steps], [None, "tag", "check", None])
        self.assertEqual(steps[1]["run"], ["echo tag"], "an id on the dash line keeps the run")

    def test_a_step_if_reads_one_line_and_folded_and_is_none_when_absent(self):
        steps = workflow_steps(workflow_job(SAMPLE_STEP_KEYS, "only"))
        self.assertEqual([step["if"] for step in steps],
                         [None, None, "steps.tag.outputs.tag != ''",
                          "github.event_name == 'push' && success()"])

    def test_an_id_or_if_nested_under_with_or_env_is_not_the_steps(self):
        steps = workflow_steps(workflow_job(SAMPLE_STEP_KEYS, "only"))
        self.assertEqual(steps[0]["with"], {"id": "not-the-step-id", "if": "not-the-step-if"})
        self.assertIsNone(steps[0]["id"])
        self.assertIsNone(steps[0]["if"])
        self.assertEqual(steps[2]["env"], {"if": "not-the-step-if",
                                           "TAG": "${{ steps.tag.outputs.tag }}"})
        self.assertEqual(steps[2]["if"], "steps.tag.outputs.tag != ''")
        self.assertEqual(steps[2]["run"], ['echo "$TAG"'])

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
        # MIGRATED at CR-MDB-070 C1 RED (§S7): the reader also reports the release event's types.
        self.assertEqual(workflow_push_triggers(SAMPLE_WORKFLOW), {
            "tags": ["[0-9]+.[0-9]+.[0-9]+"],
            "branches": ["release/**", "hotfix/**"],
            "pull_request": False,
            "workflow_dispatch": True,
            "release": ["published"],
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
        # MIGRATED at CR-MDB-070 C1 RED (§S7): no release event reads as ``"release": None``.
        self.assertEqual(workflow_push_triggers(text), {
            "tags": [],
            "branches": ["develop", "release/**", "hotfix/**"],
            "pull_request": True,
            "workflow_dispatch": False,
            "release": None,
        })

    def test_other_events_branches_and_pull_request_target_are_not_counted(self):
        text = ("on:\n"
                "  pull_request_target:\n"
                "    branches: [main]\n"
                "  workflow_run:\n"
                "    workflows: [ci]\n")
        # MIGRATED at CR-MDB-070 C1 RED (§S7): no release event reads as ``"release": None``.
        self.assertEqual(workflow_push_triggers(text), {
            "tags": [], "branches": [], "pull_request": False, "workflow_dispatch": False,
            "release": None})

    def test_the_flow_form_of_on_reads_its_events(self):
        # MIGRATED at CR-MDB-070 C1 RED (§S7): no release event reads as ``"release": None``.
        self.assertEqual(workflow_push_triggers("on: [push, workflow_dispatch]\njobs: {}\n"), {
            "tags": [], "branches": [], "pull_request": False, "workflow_dispatch": True,
            "release": None})

    # CR-MDB-070 C1 RED (§S7) — the release event, both ways.
    def test_the_release_event_reads_its_block_types_and_no_push_branch_leaks(self):
        text = ("on:\n"
                "  push:\n"
                "    branches: [master]\n"
                "  release:\n"
                "    types:\n"
                "      - published\n"
                "      - 'created'  # also\n"
                "    branches: [not-a-push-branch]\n")
        triggers = workflow_push_triggers(text)
        self.assertEqual(triggers["release"], ["published", "created"])
        self.assertEqual(triggers["branches"], ["master"])

    def test_a_release_event_with_no_types_reads_as_an_empty_list_not_none(self):
        self.assertEqual(workflow_push_triggers("on:\n  release:\n  workflow_dispatch:\n")["release"],
                         [])
        self.assertEqual(workflow_push_triggers("on: [push, release]\njobs: {}\n")["release"], [])

    def test_another_events_types_are_not_the_release_events(self):
        text = ("on:\n"
                "  pull_request:\n"
                "    types: [opened]\n"
                "  release_x:\n"
                "    types: [published]\n"
                "  push:\n"
                "    types: [published]\n")
        triggers = workflow_push_triggers(text)
        self.assertIsNone(triggers["release"])
        self.assertEqual((triggers["tags"], triggers["branches"]), ([], []))

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

# MIGRATED at CR-MDB-070 C1 RED (§S1): no tag pattern; pushes to master, release/** and hotfix/**.
RELEASE_BRANCHES = ("master", "release/**", "hotfix/**")
# MIGRATED at CR-MDB-070 C1 RED (§S2): was the tag push; now the master push, or a dispatch on master.
CREATE_RELEASE_IF = ("github.ref == 'refs/heads/master' && (github.event_name == 'push' || "
                     "github.event_name == 'workflow_dispatch')")
# MIGRATED at CR-MDB-070 C1 RED (§S3): was any dispatch or any branch push; now a push or a dispatch
# on a release or hotfix ref only.
REHEARSE_IF = ("(startsWith(github.ref, 'refs/heads/release/') || startsWith(github.ref, "
               "'refs/heads/hotfix/')) && (github.event_name == 'push' || github.event_name == "
               "'workflow_dispatch')")
#: CR-MDB-070 §S4 — the registry publishes still run on the release event only.
PUBLISH_IF = "github.event_name == 'release'"
#: CR-MDB-070 §S1 — every publish job, the rehearsal included, needs the test job.
PUBLISH_JOBS = ("rehearse", "create-release", "publish-pypi", "publish-npm")
#: CR-MDB-070 §S2 — the version check's and the release step's ``if:`` and ``TAG``.
TAG_STEP_IF = "steps.tag.outputs.tag != ''"
TAG_FROM_STEP = "${{ steps.tag.outputs.tag }}"
#: CR-MDB-070 §S2 — the ``id: tag`` step's line when ``HEAD`` carries no ``X.Y.Z`` tag.
NO_TAG_NOTICE = "::notice::no version tag at HEAD — nothing to release"
STAMP_LINE = ('version=$(python3 .github/scripts/stamp_version.py "$GITHUB_REF_NAME" '
              '"$GITHUB_RUN_NUMBER")')
_NOTES_CHECK = re.compile(
    r'python3 \.github/scripts/changelog_section\.py CHANGELOG\.md "\$version" *1?> */dev/null')
NPM_DRY_RUN = "npm publish --dry-run --access public --tag dev"

#: The jobs as CR-MDB-067 left them, read with every ``uses:`` reduced to its action name.
#: MIGRATED at CR-MDB-070 C1 RED (§S2/§S4): no longer the file's text but the baseline the
#: reshaped jobs are measured against — ``create-release``'s release step keeps its command lines;
#: ``publish-pypi`` and ``publish-npm`` keep every step after the new checkout and guard, unchanged
#: apart from pins. ``create-release`` is without its ``if:`` line.
CREATE_RELEASE_TODAY: str = """\
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

PUBLISH_PYPI_TODAY: str = """\
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

PUBLISH_NPM_TODAY: str = """\
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

#: CR-MDB-070 §S4 — each publish job's expected job-level shape beside its baseline.
PUBLISH_SHAPES = {
    "publish-pypi": (PUBLISH_PYPI_TODAY, {"contents": "read", "id-token": "write"},
                     ["needs", "if", "runs-on", "environment", "permissions", "steps"]),
    "publish-npm": (PUBLISH_NPM_TODAY, {"contents": "read", "id-token": "write"},
                    ["needs", "if", "runs-on", "environment", "permissions", "defaults", "steps"]),
}

#: CR-MDB-070 §S5 — the header's phrases (lower-cased, whitespace collapsed): the never-scope
#: warning, the branch/event map, every publish gated on the tests, and the recovery.
HEADER_PHRASES = (
    "the test job runs in every run",
    "the test job carries no if:",
    "must never be scoped",
    "a publish that needs a skipped job is itself skipped",
    "a release or hotfix push runs the tests and the rehearsal",
    "a master push runs the tests and create-release",
    "a published release runs the tests and the guarded registry publishes",
    "every publish needs the tests",
    "dispatch the workflow on master",
)
#: CR-MDB-070 §S5 — what the header no longer says: the tag push and the second workflow are gone.
HEADER_RETIRED = ("when a release tag is pushed", "ci.yml")
#: CR-MDB-070 C4 RED (VERIFY F6) — recovery from a red or flaky run: when the ``master`` run or the
#: release run fails its tests, nothing publishes; re-run the failed jobs, and a real failure is
#: fixed on a hotfix branch. Every regex matches ONE unit of :func:`header_units`.
HEADER_RED_RUN_RECOVERY = (r"\bnothing publishes\b", r"\bre-run the failed jobs\b",
                           r"(?<![\w-])hotfix(?![\w-])")
HEADER_RED_RUN_FAULT = ("the header does not say, in one unit, that a red run publishes nothing: "
                        "re-run the failed jobs, fix a real failure on a hotfix branch")


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


def header_units(text: str) -> list[str]:
    """The leading comment block with its ``#`` markers dropped, split into normalised units as
    ``tests.test_board_holds_the_queue.norm_units`` splits Markdown: one per paragraph and one per
    bullet (with its continuation lines) — CR-MDB-070 C4 RED (VERIFY F6)."""
    body = []
    for line in text.splitlines():
        if line.strip() and not line.startswith("#"):
            break
        body.append(line[2:] if line.startswith("# ") else line[1:])
    return norm_units("\n".join(body))


def header_red_run_faults(text: str) -> list[str]:
    """``[HEADER_RED_RUN_FAULT]`` unless one header unit matches every
    :data:`HEADER_RED_RUN_RECOVERY` regex; ``[]`` when one does (CR-MDB-070 C4 RED, VERIFY F6)."""
    if any(all(re.search(rx, unit) for rx in HEADER_RED_RUN_RECOVERY)
           for unit in header_units(text)):
        return []
    return [HEADER_RED_RUN_FAULT]


def normalised_if(value: str | None) -> str:
    """An ``if:`` expression with its whitespace collapsed and none just inside a parenthesis, so a
    folded or re-wrapped expression compares equal to its one-line form."""
    flat = " ".join((value or "").split())
    return re.sub(r"\s+\)", ")", re.sub(r"\(\s+", "(", flat))


def job_keys(job: list[str]) -> list[str]:
    """The job's own keys, in order, read at the job's key indent only (CR-MDB-070 §S2/§S4)."""
    base = len(job[0]) - len(job[0].lstrip()) + 2
    keys = []
    for line in job[1:]:
        if not line.strip() or line.strip().startswith("#"):
            continue
        match = re.match(r"(\s*)([\w-]+):", line)
        if match and len(match.group(1)) == base:
            keys.append(match.group(2))
    return keys


def job_needs(job: list[str]) -> list[str] | None:
    """The job's ``needs:`` as a list — ``needs: test``, ``needs: [test]`` and a block list all
    read as ``["test"]`` — ``None`` when the job declares none (CR-MDB-070 §S1)."""
    value = workflow_job_key(job, "needs")
    if value is None:
        return None
    if value.startswith("[") and value.endswith("]"):
        return [part.strip().strip("'\"") for part in value[1:-1].split(",") if part.strip()]
    if value:
        return [value]
    base = len(job[0]) - len(job[0].lstrip()) + 2
    start = next(i for i, line in enumerate(job)
                 if re.match(rf"\s{{{base}}}needs:\s*(?:#.*)?$", line))
    items = []
    for line in job[start + 1:]:
        if line.strip() and len(line) - len(line.lstrip()) <= base:
            break
        if line.strip().startswith("- "):
            items.append(line.strip()[2:].split(" #", 1)[0].strip().strip("'\""))
    return items


def _action(uses: str | None) -> str | None:
    return uses.split("@", 1)[0] if uses else None


def step_shape(step: dict) -> dict:
    """A step as the reader gives it, its ``uses`` reduced to the action name (pins aside)."""
    return {**step, "uses": _action(step["uses"])}


#: CR-MDB-070 — a ``release.yml`` meeting every §S1–§S5 item (``@PIN`` stands for a pinned ref).
#: Every release-file class below also runs against it (the ``*ConformingSampleProofTest``
#: subclasses), proving that a workflow written to the spec passes what the real file must.
CONFORMING_RELEASE = r"""# Release workflow: the one workflow of this repository. Its test job
# runs the unittest suite, and every publish job needs it.
#
# The test job runs in every run. The test job carries no if: and must
# never be scoped: `needs:` orders jobs only within one run, and a
# publish that needs a skipped job is itself skipped, silently.
#
# - A release or hotfix push runs the tests and the rehearsal.
# - A master push runs the tests and create-release, which releases the
#   version tag at HEAD.
# - A published release runs the tests and the guarded registry publishes.
# Every publish needs the tests.
#
# Recovery: when the master run finds no version tag at HEAD, dispatch
# the workflow on master.
#
# A red run: when the master run or the release run fails its tests,
# nothing publishes. Re-run the failed jobs; a real failure is fixed on
# a hotfix branch.
#
# One-time setup by the maintainer:
# - repository secret RELEASE_PAT;
# - environments `pypi`, `testpypi` and `npm`; the `testpypi`
#   environment admits the `release/**` and `hotfix/**` branches and
#   carries no required reviewers.

name: release

on:
  push:
    branches: [master, "release/**", "hotfix/**"]
  release:
    types: [published]
  workflow_dispatch:

permissions:
  contents: read

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@PIN # v4.4.0
        with:
          fetch-depth: 0
      - uses: actions/setup-python@PIN # v7.0.0
        with:
          python-version: "3.14"
      - uses: astral-sh/setup-uv@PIN # v6.8.0
      - name: Run the suite
        env:
          MODELB_HOME: ${{ runner.temp }}/modelb-home
          XDG_DATA_HOME: ${{ runner.temp }}/xdg-data
          PI_CODING_AGENT_DIR: ${{ runner.temp }}/pi-agent
        run: python -m unittest discover -s tests -t .

  create-release:
    needs: test
    if: >-
      github.ref == 'refs/heads/master' &&
      (github.event_name == 'push' || github.event_name == 'workflow_dispatch')
    runs-on: ubuntu-latest
    permissions:
      contents: write
    steps:
      - uses: actions/checkout@PIN # v4.4.0
        with:
          fetch-depth: 0
      - name: The version tag at HEAD
        id: tag
        run: |
          tags=$(git tag --points-at HEAD | grep -E '^[0-9]+\.[0-9]+\.[0-9]+$' || true)
          count=$(printf '%s' "$tags" | grep -c . || true)
          if [ "$count" -gt 1 ]; then
            echo "::error::more than one version tag at HEAD: $(echo $tags)"
            exit 1
          fi
          if [ -z "$tags" ]; then
            echo "::notice::no version tag at HEAD — nothing to release"
          fi
          echo "tag=$tags" >> "$GITHUB_OUTPUT"
      - name: Tag matches the package version
        if: steps.tag.outputs.tag != ''
        env:
          TAG: ${{ steps.tag.outputs.tag }}
        run: |
          python3 - <<'PY'
          import os, pathlib, re, sys
          text = pathlib.Path("modelb_axi/__init__.py").read_text()
          version = re.search(r'__version__\s*=\s*"([^"]+)"', text)[1]
          tag = os.environ["TAG"]
          if version != tag:
              sys.exit(f"tag {tag} != __version__ {version}")
          PY
      - name: Create the GitHub Release
        if: steps.tag.outputs.tag != ''
        env:
          GH_TOKEN: ${{ secrets.RELEASE_PAT }}
          TAG: ${{ steps.tag.outputs.tag }}
        run: |
          python3 .github/scripts/changelog_section.py CHANGELOG.md "$TAG" > "$RUNNER_TEMP/notes.md"
          if ! gh release view "$TAG" >/dev/null 2>&1; then
            gh release create "$TAG" --notes-file "$RUNNER_TEMP/notes.md" --verify-tag
          fi

  publish-pypi:
    needs: test
    if: github.event_name == 'release'
    runs-on: ubuntu-latest
    environment: pypi
    permissions:
      contents: read
      id-token: write
    steps:
      - uses: actions/checkout@PIN # v4.4.0
        with:
          fetch-depth: 0
      - name: Guard - a version tag on master's history
        run: |
          if ! [[ "$GITHUB_REF" =~ ^refs/tags/[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
            echo "::error::refusing to publish: $GITHUB_REF is not an X.Y.Z tag ref"
            exit 1
          fi
          git fetch --no-tags origin master
          if ! git merge-base --is-ancestor "$GITHUB_SHA" origin/master; then
            echo "::error::refusing to publish: $GITHUB_SHA is not on origin/master"
            exit 1
          fi
      - uses: astral-sh/setup-uv@PIN # v6.8.0
      - run: uv build
      - uses: pypa/gh-action-pypi-publish@PIN # v1.14.2

  rehearse:
    needs: test
    if: >-
      (startsWith(github.ref, 'refs/heads/release/') ||
       startsWith(github.ref, 'refs/heads/hotfix/')) &&
      (github.event_name == 'push' || github.event_name == 'workflow_dispatch')
    runs-on: ubuntu-latest
    environment: testpypi
    permissions:
      contents: read
      id-token: write
    steps:
      - uses: actions/checkout@PIN # v4.4.0
      - name: Stamp the dev version and check the release notes
        run: |
          version=$(python3 .github/scripts/stamp_version.py "$GITHUB_REF_NAME" "$GITHUB_RUN_NUMBER")
          python3 .github/scripts/changelog_section.py CHANGELOG.md "$version" > /dev/null
      - uses: astral-sh/setup-uv@PIN # v6.8.0
      - run: uv build
      - uses: pypa/gh-action-pypi-publish@PIN # v1.14.2
        with:
          repository-url: https://test.pypi.org/legacy/
          skip-existing: true
      - uses: actions/setup-node@PIN # v4.4.0
        with:
          node-version: "22"
      - name: npm new enough for the dry-run publish
        run: npm install -g npm@latest
      - name: Ship the root CHANGELOG.md in the package
        working-directory: pi-package
        run: cp ../CHANGELOG.md .
      - name: Dry-run the npm publish
        working-directory: pi-package
        run: npm publish --dry-run --access public --tag dev

  publish-npm:
    needs: test
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
      - uses: actions/checkout@PIN # v4.4.0
        with:
          fetch-depth: 0
      - name: Guard - a version tag on master's history
        run: |
          if ! [[ "$GITHUB_REF" =~ ^refs/tags/[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
            echo "::error::refusing to publish: $GITHUB_REF is not an X.Y.Z tag ref"
            exit 1
          fi
          git fetch --no-tags origin master
          if ! git merge-base --is-ancestor "$GITHUB_SHA" origin/master; then
            echo "::error::refusing to publish: $GITHUB_SHA is not on origin/master"
            exit 1
          fi
      - uses: actions/setup-node@PIN # v4.4.0
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
        run: npm publish --provenance --access public
""".replace("@PIN", "@" + _SHA)


class _ReleaseSource:
    """Where a release-file class reads ``release.yml``: the real file, unless a proof subclass
    sets ``SOURCE`` to sample text."""

    SOURCE: str | None = None

    @classmethod
    def release_text(cls) -> str:
        return cls.SOURCE if cls.SOURCE is not None else _release_text()


class ReleaseWorkflowTriggersTest(_ReleaseSource, unittest.TestCase):
    """CR-MDB-070 §S1 — the triggers: ``master``, ``release/**`` and ``hotfix/**`` pushes, the
    published release, dispatch; no tag pattern, no ``develop``, no ``pull_request``."""

    # MIGRATED at CR-MDB-070 C1 RED (§S1): was the tag pattern and exactly release/** and hotfix/**.
    def test_push_triggers_are_exactly_master_release_and_hotfix_branches_and_no_tag(self):
        triggers = workflow_push_triggers(self.release_text())
        self.assertEqual(triggers["tags"], [], "§S1: no tag pattern")
        self.assertEqual(sorted(triggers["branches"]), sorted(RELEASE_BRANCHES),
                         "§S1: on.push is exactly master, release/** and hotfix/**")

    def test_the_published_release_triggers_and_no_pull_request_does(self):
        triggers = workflow_push_triggers(self.release_text())
        self.assertEqual(triggers["release"], ["published"], "§S1: release: types: [published]")
        self.assertFalse(triggers["pull_request"], "§S1: no pull_request trigger")

    def test_workflow_dispatch_stays(self):
        # Regression pin: holds today; fails the moment the dispatch trigger is dropped.
        self.assertTrue(workflow_push_triggers(self.release_text())["workflow_dispatch"])


class CreateReleaseJobTest(_ReleaseSource, unittest.TestCase):
    """CR-MDB-070 §S2 — ``create-release`` runs from the ``master`` push (or a dispatch on
    ``master``), after the tests: checkout with full history, the ``id: tag`` step, then the
    version check and the release step, each guarded on the tag."""

    @classmethod
    def setUpClass(cls):
        cls.job = workflow_job(cls.release_text(), "create-release")
        cls.steps = workflow_steps(cls.job)
        cls.today = workflow_steps(CREATE_RELEASE_TODAY.splitlines())

    # MIGRATED at CR-MDB-070 C1 RED (§S2): was test_create_release_runs_only_on_a_tag_push.
    def test_create_release_runs_on_the_master_push_or_a_dispatch_on_master(self):
        self.assertEqual(normalised_if(workflow_job_key(self.job, "if")), CREATE_RELEASE_IF)

    # MIGRATED at CR-MDB-070 C1 RED (§S2): test_create_release_is_otherwise_unchanged, split into
    # the job's keys, its runner and permissions, and its four steps.
    def test_create_release_needs_the_tests_and_keeps_its_runner_and_write_permission(self):
        self.assertEqual(job_needs(self.job), ["test"], "§S2: needs: test")
        self.assertEqual(workflow_job_key(self.job, "runs-on"), "ubuntu-latest")
        self.assertEqual(workflow_job_permissions(self.job), {"contents": "write"})
        self.assertEqual(sorted(job_keys(self.job)),
                         sorted(["needs", "if", "runs-on", "permissions", "steps"]))

    def test_create_release_declares_no_shell_anywhere(self):
        shells = [line.strip() for line in self.job if re.match(r"\s*(?:-\s+)?shell:", line)]
        self.assertEqual(shells, [], "§S2: no shell: (the id: tag step runs under bash -e)")
        self.assertIsNone(workflow_job_key(self.job, "defaults"))

    def test_there_are_four_steps_checkout_tag_check_release(self):
        self.assertEqual(len(self.steps), 4, [step_shape(step) for step in self.steps])

    def test_step_1_checks_out_with_full_history(self):
        step = self.steps[0]
        self.assertEqual(_action(step["uses"]), "actions/checkout")
        self.assertEqual(step["with"], {"fetch-depth": "0"}, "§S2: checkout with fetch-depth: 0")

    def test_step_2_is_the_tag_step_with_id_tag_and_no_release_creation(self):
        step = self.steps[1]
        self.assertEqual(step["id"], "tag", "§S2: the second step has id: tag")
        self.assertIsNone(step["uses"])
        self.assertIsNone(step["if"], "§S2: the tag step runs in every create-release run")
        self.assertTrue(step["run"], "§S2: the tag step runs command lines")
        self.assertFalse(any("gh release create" in line for line in step["run"]),
                         "§S2: the tag step holds no gh release create")

    def test_step_3_checks_the_version_against_tag_when_there_is_one(self):
        step = self.steps[2]
        self.assertIsNone(step["uses"])
        self.assertTrue(any("__version__" in line for line in step["run"]),
                        "§S2: the third step is the tag == __version__ check")
        self.assertEqual(step["if"], TAG_STEP_IF)
        self.assertEqual(step["env"], {"TAG": TAG_FROM_STEP})
        self.assertFalse(any("GITHUB_REF_NAME" in line for line in step["run"]),
                         "§S2: the check reads TAG, not GITHUB_REF_NAME")

    def test_step_4_creates_the_release_with_unchanged_command_lines(self):
        self.assertEqual(len(self.steps), 4, "§S2: the release step is the fourth of four")
        step, today = self.steps[3], self.today[2]
        self.assertIsNone(step["uses"])
        self.assertEqual(step["if"], TAG_STEP_IF)
        self.assertEqual(step["env"], {"GH_TOKEN": today["env"]["GH_TOKEN"], "TAG": TAG_FROM_STEP})
        self.assertEqual(step["run"], today["run"], "§S2: the release step's lines are unchanged")


class PublishJobsGuardTest(_ReleaseSource, unittest.TestCase):
    """CR-MDB-070 §S4 — ``publish-pypi`` and ``publish-npm``: ``needs: test``, still the release
    event only; checkout with full history first, the guard second, then every step of the
    baseline after its checkout, unchanged apart from pins."""

    def _job(self, name: str) -> list[str]:
        return workflow_job(self.release_text(), name)

    # MIGRATED at CR-MDB-070 C1 RED (§S4): was test_publish_pypi_is_unchanged_but_for_its_pins and
    # test_publish_npm_is_unchanged_but_for_its_pins (whole-job text pins of PUBLISH_*_TODAY).
    def test_each_publish_job_keeps_its_keys_and_values_and_needs_the_tests(self):
        for name, (today, permissions, keys) in PUBLISH_SHAPES.items():
            with self.subTest(job=name):
                job, base = self._job(name), today.splitlines()
                self.assertEqual(job_needs(job), ["test"], "§S4: needs: test")
                self.assertEqual(normalised_if(workflow_job_key(job, "if")), PUBLISH_IF)
                self.assertEqual(workflow_job_permissions(job), permissions)
                for key in ("runs-on", "environment"):
                    self.assertEqual(workflow_job_key(job, key), workflow_job_key(base, key))
                self.assertEqual(sorted(job_keys(job)), sorted(keys))

    def test_publish_npm_keeps_its_pi_package_working_directory(self):
        self.assertEqual(workflow_job_working_directory(self._job("publish-npm")), "pi-package")

    def test_each_publish_job_checks_out_with_full_history_first(self):
        for name in PUBLISH_SHAPES:
            with self.subTest(job=name):
                step = workflow_steps(self._job(name))[0]
                self.assertEqual(_action(step["uses"]), "actions/checkout")
                self.assertEqual(step["with"], {"fetch-depth": "0"},
                                 "§S4: checkout with fetch-depth: 0")

    def test_each_publish_jobs_second_step_is_a_run_step_guard(self):
        for name in PUBLISH_SHAPES:
            with self.subTest(job=name):
                step = workflow_steps(self._job(name))[1]
                self.assertIsNone(step["uses"], f"§S4: step 2 of {name} is the guard, a run step")
                self.assertTrue(any("merge-base --is-ancestor" in line for line in step["run"]),
                                f"§S4: step 2 of {name} checks the ancestry on origin/master")

    def test_every_later_step_is_the_baselines_unchanged_apart_from_pins(self):
        for name, (today, _permissions, _keys) in PUBLISH_SHAPES.items():
            with self.subTest(job=name):
                later = [step_shape(step) for step in workflow_steps(self._job(name))[2:]]
                base = [step_shape(step) for step in workflow_steps(today.splitlines())[1:]]
                self.assertEqual(later, base)

    def test_the_guard_steps_lines_are_the_same_in_both_jobs(self):
        guards = [workflow_steps(self._job(name))[1]["run"] for name in PUBLISH_SHAPES]
        self.assertTrue(guards[0], "§S4: the guard runs command lines")
        self.assertEqual(guards[0], guards[1], "§S4: both publish jobs carry the same guard")


class RehearseJobTest(_ReleaseSource, unittest.TestCase):
    """§S2 — ``rehearse`` replaces ``rehearse-testpypi``: its keys and its six steps in order;
    CR-MDB-070 §S3 — it needs the tests and admits only release and hotfix refs."""

    @classmethod
    def setUpClass(cls):
        cls.text = cls.release_text()

    def _job(self) -> list[str]:
        return workflow_job(self.text, "rehearse")

    def _steps(self) -> list[dict]:
        return workflow_steps(self._job())

    def test_there_is_no_rehearse_testpypi_job(self):
        self.assertNotIn("rehearse-testpypi", self.text)

    # MIGRATED at CR-MDB-070 C1 RED (§S3): was test_rehearse_runs_on_a_dispatch_or_a_branch_push.
    def test_rehearse_runs_on_a_push_or_dispatch_on_a_release_or_hotfix_ref(self):
        self.assertEqual(normalised_if(workflow_job_key(self._job(), "if")), REHEARSE_IF)

    def test_rehearse_needs_the_tests(self):
        self.assertEqual(job_needs(self._job()), ["test"], "§S3: needs: test")

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


class ReleaseWorkflowPinsAndHeaderTest(_ReleaseSource, unittest.TestCase):
    """§S2 — every action pinned to a SHA with its version comment; the header comment
    (CR-MDB-070 §S5: one workflow, the never-scope warning, the branch/event map, the recovery,
    the one-time setup list)."""

    def test_every_action_is_pinned_to_a_sha_with_a_version_comment(self):
        text = self.release_text()
        self.assertTrue(any(_PIN_LINE.match(line) for line in text.splitlines()))
        self.assertEqual(action_pin_faults(text), [])

    def test_the_header_names_release_and_hotfix_pushes(self):
        self.assertIn("release or hotfix push", _header(self.release_text()))

    def test_the_header_no_longer_says_a_manual_run_rehearses_the_python_upload(self):
        self.assertNotIn("rehearses the python upload", _header(self.release_text()))

    # CR-MDB-070 C1 RED (§S5) — the header's phrases.
    def test_the_header_names_the_never_scope_warning_the_map_and_the_recovery(self):
        header = _header(self.release_text())
        missing = [phrase for phrase in HEADER_PHRASES if phrase not in header]
        self.assertEqual(missing, [], "§S5: the header names every phrase")

    def test_the_header_no_longer_names_the_tag_push_or_ci_yml(self):
        header = _header(self.release_text())
        self.assertEqual([phrase for phrase in HEADER_RETIRED if phrase in header], [])

    # CR-MDB-070 C4 RED (VERIFY F6) — recovery from a red or flaky run.
    def test_the_header_says_a_red_run_publishes_nothing_re_run_the_failed_jobs_or_hotfix(self):
        self.assertEqual(header_red_run_faults(self.release_text()), [])

    def test_the_setup_list_says_testpypi_admits_release_and_hotfix_with_no_reviewers(self):
        header = _header(self.release_text())
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
        return bash_e(hits[0]["run"], tree, env), tree

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


# ------------------------------------------------------------------ CR-MDB-070 executions ----

def bash_e(lines: list[str], cwd: Path, env: dict) -> subprocess.CompletedProcess:
    """A step's command lines run as GitHub runs a step with no ``shell:`` — ``bash -e``."""
    return subprocess.run(
        ["bash", "--noprofile", "--norc", "-e", "-c", "\n".join(lines) + "\n"],
        cwd=cwd, env=env, capture_output=True, text=True, encoding="utf-8", timeout=60,
        stdin=subprocess.DEVNULL,
    )


def _git_env(home: Path) -> dict:
    """A git environment that reads no user or system configuration and commits as a fixed
    identity; no ``GIT_*`` variable of the calling process leaks in."""
    env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    env.update(HOME=str(home), GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull,
               GIT_AUTHOR_NAME="Fixture", GIT_AUTHOR_EMAIL="fixture@example.invalid",
               GIT_COMMITTER_NAME="Fixture", GIT_COMMITTER_EMAIL="fixture@example.invalid",
               GIT_TERMINAL_PROMPT="0")
    return env


def _git(cwd: Path, env: dict, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=cwd, env=env, capture_output=True, text=True,
                            encoding="utf-8", timeout=30, stdin=subprocess.DEVNULL)
    if result.returncode != 0:
        raise AssertionError(f"fixture: git {' '.join(args)} failed: {result.stderr}")
    return result.stdout.strip()


def _workdir(test: unittest.TestCase, prefix: str) -> tuple[Path, dict]:
    work = Path(tempfile.mkdtemp(prefix=prefix))
    test.addCleanup(shutil.rmtree, work, True)
    (work / "home").mkdir()
    return work, _git_env(work / "home")


def _annotations(result: subprocess.CompletedProcess) -> list[str]:
    """Every output line of a step run, stdout then stderr, stripped."""
    return [line.strip() for line in (result.stdout + result.stderr).splitlines()]


def _outputs(text: str) -> dict:
    """``$GITHUB_OUTPUT``'s ``key=value`` lines as a dict; any other non-blank line fails."""
    out = {}
    for line in text.splitlines():
        if not line.strip():
            continue
        key, sep, value = line.partition("=")
        if not sep:
            raise AssertionError(f"§S2: GITHUB_OUTPUT holds a line not of the key=value form: "
                                 f"{line!r}")
        out[key] = value
    return out


def run_tag_step(test: unittest.TestCase, lines: list[str], head_tags: tuple,
                 earlier_tags: tuple = ("1.2.2",)) -> tuple[subprocess.CompletedProcess, str]:
    """Run ``lines`` under ``bash -e`` in a temp repository on ``master``: an earlier commit
    carrying ``earlier_tags``, ``HEAD`` carrying ``head_tags`` (annotated, as git flow tags), and
    ``GITHUB_OUTPUT`` at a temp file. ``(the run, the output file's text)``."""
    work, env = _workdir(test, "create-release-tag-")
    repo = work / "repo"
    _git(work, env, "init", "-q", "-b", "master", str(repo))
    _git(repo, env, "commit", "-q", "--allow-empty", "-m", "earlier")
    for tag in earlier_tags:
        _git(repo, env, "tag", "-a", tag, "-m", tag)
    _git(repo, env, "commit", "-q", "--allow-empty", "-m", "head")
    for tag in head_tags:
        _git(repo, env, "tag", "-a", tag, "-m", tag)
    output = work / "github-output"
    output.write_text("", encoding="utf-8")
    result = bash_e(lines, repo, dict(env, GITHUB_OUTPUT=str(output), GITHUB_REF_NAME="master",
                                      GITHUB_REF="refs/heads/master"))
    return result, output.read_text(encoding="utf-8")


def guard_fixture(test: unittest.TestCase) -> dict:
    """A bare ``origin`` whose ``master`` holds the commit tagged ``1.2.3`` and one commit after
    it, and a clone of it (with an empty ``pi-package/``) holding one more commit, ``side``, on no
    branch of ``origin``: ``{"clone", "env", "tagged", "side"}``."""
    work, env = _workdir(test, "publish-guard-")
    origin, seed, clone = work / "origin.git", work / "seed", work / "clone"
    _git(work, env, "init", "-q", "--bare", "-b", "master", str(origin))
    _git(work, env, "init", "-q", "-b", "master", str(seed))
    _git(seed, env, "commit", "-q", "--allow-empty", "-m", "the release")
    _git(seed, env, "tag", "-a", "1.2.3", "-m", "1.2.3")
    tagged = _git(seed, env, "rev-parse", "HEAD")
    _git(seed, env, "commit", "-q", "--allow-empty", "-m", "master moves on")
    _git(seed, env, "push", "-q", str(origin), "master")
    _git(work, env, "clone", "-q", str(origin), str(clone))
    tree = _git(clone, env, "rev-parse", f"{tagged}^{{tree}}")
    side = _git(clone, env, "commit-tree", tree, "-p", tagged, "-m", "side")
    (clone / "pi-package").mkdir()
    return {"clone": clone, "env": env, "tagged": tagged, "side": side}


def run_guard(fixture: dict, lines: list[str], where: str, ref: str, sha: str
              ) -> subprocess.CompletedProcess:
    """Run a guard's ``lines`` under ``bash -e`` from ``where`` in the fixture's clone, with
    ``GITHUB_REF`` and ``GITHUB_SHA`` set."""
    clone = fixture["clone"]
    return bash_e(lines, clone / where, dict(fixture["env"], GITHUB_REF=ref, GITHUB_SHA=sha,
                                             GITHUB_WORKSPACE=str(clone)))


class CreateReleaseTagStepExecutionTest(_ReleaseSource, unittest.TestCase):
    """CR-MDB-070 §S2 — the ``id: tag`` step's command lines, run under ``bash -e`` in a temp git
    repository on ``master`` with ``GITHUB_OUTPUT`` at a temp file: the one ``X.Y.Z`` tag at
    ``HEAD`` is the output; none is a notice and an empty output; two fail naming both."""

    def _tag_lines(self) -> list[str]:
        steps = workflow_steps(workflow_job(self.release_text(), "create-release"))
        hits = [step for step in steps if step["id"] == "tag"]
        self.assertEqual(len(hits), 1, f"§S2: one create-release step has id: tag; found {len(hits)}")
        self.assertTrue(hits[0]["run"], "§S2: the id: tag step runs command lines")
        return hits[0]["run"]

    def _execute(self, head_tags: tuple, earlier_tags: tuple = ("1.2.2",)
                 ) -> tuple[subprocess.CompletedProcess, str]:
        return run_tag_step(self, self._tag_lines(), head_tags, earlier_tags)

    def test_one_version_tag_at_head_is_the_output_and_an_earlier_one_is_not(self):
        result, output = self._execute(("1.2.3",))
        self.assertEqual(result.returncode, 0, f"stdout={result.stdout!r} stderr={result.stderr!r}")
        self.assertEqual(_outputs(output), {"tag": "1.2.3"})
        self.assertNotIn(NO_TAG_NOTICE, _annotations(result))

    def test_a_non_version_tag_beside_the_version_tag_is_ignored(self):
        result, output = self._execute(("v1.2.3", "1.2.3", "1.2.3-rc.1"))
        self.assertEqual(result.returncode, 0, f"stdout={result.stdout!r} stderr={result.stderr!r}")
        self.assertEqual(_outputs(output), {"tag": "1.2.3"})

    def test_no_tag_at_head_exits_0_with_an_empty_output_and_the_notice(self):
        result, output = self._execute(())
        self.assertEqual(result.returncode, 0,
                         f"§S2: no tag must not fail the step under bash -e; stderr={result.stderr!r}")
        self.assertEqual(_outputs(output), {"tag": ""})
        self.assertIn(NO_TAG_NOTICE, _annotations(result))

    def test_only_non_version_tags_at_head_exit_0_with_an_empty_output_and_the_notice(self):
        result, output = self._execute(("v1.2.3", "1.2.3-rc.1", "release-1.2.3", "1.2",
                                        "1.2.3.4"))
        self.assertEqual(result.returncode, 0, f"stdout={result.stdout!r} stderr={result.stderr!r}")
        self.assertEqual(_outputs(output), {"tag": ""})
        self.assertIn(NO_TAG_NOTICE, _annotations(result))

    def test_two_version_tags_at_head_exit_1_with_an_error_naming_both(self):
        result, _output = self._execute(("1.2.3", "1.2.4"))
        self.assertEqual(result.returncode, 1, f"stdout={result.stdout!r} stderr={result.stderr!r}")
        errors = [line for line in _annotations(result) if line.startswith("::error::")]
        self.assertTrue(any("1.2.3" in line and "1.2.4" in line for line in errors),
                        f"§S2: an ::error:: line names every version tag; got {errors!r}")
        self.assertNotIn(NO_TAG_NOTICE, _annotations(result))


class CreateReleaseVersionCheckExecutionTest(_ReleaseSource, unittest.TestCase):
    """CR-MDB-070 §S2 — the tag == ``__version__`` check reads ``TAG`` (the ``id: tag`` step's
    output), not ``GITHUB_REF_NAME`` (``master`` on the master push): run under ``bash -e``."""

    def _execute(self, tag: str) -> subprocess.CompletedProcess:
        steps = workflow_steps(workflow_job(self.release_text(), "create-release"))
        hits = [step for step in steps if any("__version__" in line for line in step["run"])]
        self.assertEqual(len(hits), 1, f"§S2: one step checks __version__; found {len(hits)}")
        work, env = _workdir(self, "create-release-check-")
        (work / "modelb_axi").mkdir()
        (work / INIT_REL).write_text(_version_files("1.2.3", "1.2.3")[0], encoding="utf-8")
        return bash_e(hits[0]["run"], work, dict(env, TAG=tag, GITHUB_REF_NAME="master",
                                                  GITHUB_REF="refs/heads/master"))

    def test_a_tag_equal_to_the_version_passes_on_the_master_push(self):
        result = self._execute("1.2.3")
        self.assertEqual(result.returncode, 0, f"§S2: the check reads TAG; stderr={result.stderr!r}")

    def test_a_tag_other_than_the_version_fails_naming_both(self):
        result = self._execute("1.2.4")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("1.2.4", result.stderr, "§S2: the failure names the tag it read from TAG")
        self.assertIn("1.2.3", result.stderr)


class PublishGuardExecutionTest(_ReleaseSource, unittest.TestCase):
    """CR-MDB-070 §S4 — each publish job's guard (its second step), run under ``bash -e`` from
    its working directory in a clone of a bare ``origin``: a clean ``X.Y.Z`` tag ref on
    ``master``'s history passes; a non-version ref, or a commit not on ``master``, exits 1 with an
    ``::error::`` line."""

    def setUp(self):
        self.fixture = guard_fixture(self)
        self.tagged, self.side = self.fixture["tagged"], self.fixture["side"]

    def _run_guard(self, name: str, ref: str, sha: str) -> subprocess.CompletedProcess:
        job = workflow_job(self.release_text(), name)
        step = workflow_steps(job)[1]
        self.assertIsNone(step["uses"], f"§S4: step 2 of {name} is the guard, a run step; "
                                        f"got uses {step['uses']!r}")
        self.assertTrue(step["run"], f"§S4: the guard of {name} runs command lines")
        where = step["working-directory"] or workflow_job_working_directory(job) or "."
        return run_guard(self.fixture, step["run"], where, ref, sha)

    def test_a_clean_tag_ref_on_masters_history_passes_in_both_jobs(self):
        for name in PUBLISH_SHAPES:
            with self.subTest(job=name):
                result = self._run_guard(name, "refs/tags/1.2.3", self.tagged)
                self.assertEqual(result.returncode, 0,
                                 f"stdout={result.stdout!r} stderr={result.stderr!r}")
                self.assertFalse([line for line in _annotations(result)
                                  if line.startswith("::error::")])

    def test_a_non_version_ref_exits_1_with_an_error_in_both_jobs(self):
        for name in PUBLISH_SHAPES:
            for ref in ("refs/heads/master", "refs/tags/v1.2.3", "refs/tags/1.2.3-rc.1",
                        "refs/tags/1.2", "refs/tags/1.2.3.4", "refs/tags/x/1.2.3"):
                with self.subTest(job=name, ref=ref):
                    result = self._run_guard(name, ref, self.tagged)
                    self.assertEqual(result.returncode, 1,
                                     f"stdout={result.stdout!r} stderr={result.stderr!r}")
                    self.assertTrue(any(line.startswith("::error::")
                                        for line in _annotations(result)),
                                    "§S4: the refusal is an ::error:: line")

    def test_a_commit_not_on_master_exits_1_with_an_error_in_both_jobs(self):
        for name in PUBLISH_SHAPES:
            with self.subTest(job=name):
                result = self._run_guard(name, "refs/tags/1.2.4", self.side)
                self.assertEqual(result.returncode, 1,
                                 f"stdout={result.stdout!r} stderr={result.stderr!r}")
                self.assertTrue(any(line.startswith("::error::")
                                    for line in _annotations(result)),
                                "§S4: the refusal is an ::error:: line")



class ExecutionHarnessBiteProofTest(unittest.TestCase):
    """CR-MDB-070 §S2/§S4 — the execution harness bites the defects it exists for: run on
    :data:`CONFORMING_RELEASE`'s steps with one defect each, the outcome the execution tests
    assert does not hold."""

    def _sample_steps(self, job: str) -> list[dict]:
        return workflow_steps(workflow_job(CONFORMING_RELEASE, job))

    def test_a_tag_step_without_or_true_fails_on_no_tag_under_bash_e(self):
        lines = next(step["run"] for step in self._sample_steps("create-release")
                     if step["id"] == "tag")
        broken = [line.replace(" || true)", ")", 1) if line.startswith("tags=") else line
                  for line in lines]
        self.assertNotEqual(broken, lines, "the sample's tag line carries || true")
        result, _output = run_tag_step(self, broken, ())
        self.assertNotEqual(result.returncode, 0,
                            "bash -e fails an assignment from a grep that matched nothing")

    def test_a_tag_step_taking_the_first_tag_does_not_name_both(self):
        broken = ["tag=$(git tag --points-at HEAD | grep -E '^[0-9]+\\.[0-9]+\\.[0-9]+$' "
                  "| head -1 || true)",
                  'echo "tag=$tag" >> "$GITHUB_OUTPUT"']
        result, output = run_tag_step(self, broken, ("1.2.3", "1.2.4"))
        self.assertEqual(result.returncode, 0, "the defect: two tags pass silently")
        self.assertEqual(_outputs(output), {"tag": "1.2.3"})

    def test_a_guard_without_the_ancestry_check_passes_a_commit_not_on_master(self):
        guard = self._sample_steps("publish-pypi")[1]["run"]
        broken = [line for line in guard if "merge-base" not in line]
        cut = broken.index("git fetch --no-tags origin master")
        broken = broken[:cut + 1]
        fixture = guard_fixture(self)
        result = run_guard(fixture, broken, ".", "refs/tags/1.2.4", fixture["side"])
        self.assertEqual(result.returncode, 0, f"the defect: no refusal; stderr={result.stderr!r}")

    def test_a_guard_pattern_without_its_end_anchor_passes_a_prerelease_ref(self):
        guard = self._sample_steps("publish-npm")[1]["run"]
        broken = [line.replace("[0-9]+$ ]]", "[0-9]+ ]]") for line in guard]
        self.assertNotEqual(broken, guard)
        fixture = guard_fixture(self)
        result = run_guard(fixture, broken, "pi-package", "refs/tags/1.2.3-rc.1",
                           fixture["tagged"])
        self.assertEqual(result.returncode, 0, f"the defect: no refusal; stderr={result.stderr!r}")

# ------------------------------------------------------------------ CR-MDB-070 the proofs ----
# Each release-file class run against CONFORMING_RELEASE: a workflow written to the spec passes.

class ReleaseWorkflowTriggersConformingSampleProofTest(ReleaseWorkflowTriggersTest):
    SOURCE = CONFORMING_RELEASE


class CreateReleaseJobConformingSampleProofTest(CreateReleaseJobTest):
    SOURCE = CONFORMING_RELEASE


class PublishJobsGuardConformingSampleProofTest(PublishJobsGuardTest):
    SOURCE = CONFORMING_RELEASE


class RehearseJobConformingSampleProofTest(RehearseJobTest):
    SOURCE = CONFORMING_RELEASE


class ReleaseWorkflowPinsAndHeaderConformingSampleProofTest(ReleaseWorkflowPinsAndHeaderTest):
    SOURCE = CONFORMING_RELEASE


class CreateReleaseTagStepConformingSampleProofTest(CreateReleaseTagStepExecutionTest):
    SOURCE = CONFORMING_RELEASE


class CreateReleaseVersionCheckConformingSampleProofTest(CreateReleaseVersionCheckExecutionTest):
    SOURCE = CONFORMING_RELEASE


class PublishGuardConformingSampleProofTest(PublishGuardExecutionTest):
    SOURCE = CONFORMING_RELEASE


# ---------------------------------------------- CR-MDB-070 C4 RED (VERIFY F1) — the skill snippet ----

#: VERIFY F1 — a CHANGELOG.md with sections for both 1.0.0 and 1.0.1, so a refusal of two tags at HEAD is the count's,
#: never a missing section's.
CHANGELOG_TWO_TAGS = CHANGELOG_PREAMBLE + (
    "## [1.0.1] - 2026-10-14\n\n### Fixed\n\n- The second tag's notes.\n\n"
    "## [1.0.0] - 2026-10-13\n\n### Added\n\n- The first tag's notes.\n"
)
#: A ``gh`` stand-in first on ``PATH``: it records each call's arguments, one line each, in
#: ``$GH_SHIM_LOG``; ``release view`` exits 1 (no such release yet), every other call exits 0.
GH_SHIM = ('#!/bin/sh\n'
           'printf \'%s\\n\' "$*" >> "$GH_SHIM_LOG"\n'
           '[ "$1 $2" != "release view" ]\n')
#: VERIFY F1 — a skill ``## Releases`` whose release-job snippet meets the finding: it counts the
#: version tags at HEAD and refuses more than one, naming them.
CONFORMING_SKILL_SNIPPET = r"""## Releases (NON-NEGOTIABLE)

```yaml
create-release:
  needs: test
  if: github.ref == 'refs/heads/master'
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4 # pin to a full commit SHA
      with:
        fetch-depth: 0
    - name: Create the release
      env:
        GH_TOKEN: ${{ secrets.RELEASE_PAT }}
      run: |
        tags=$(git tag --points-at HEAD | grep -E '^[0-9]+\.[0-9]+\.[0-9]+$' || true)
        [ -n "$tags" ] || { echo "no version tag at HEAD, nothing to release"; exit 0; }
        [ "$(printf '%s\n' "$tags" | wc -l)" -eq 1 ] || { echo "more than one version tag at HEAD:" $tags >&2; exit 1; }
        tag=$tags
        awk -v head="## [$tag] - " '
          index($0, head) == 1 { found = 1; next }
          found && (/^## / || /^\[[^]]+\]: /) { exit }
          found { print }
          END { if (!found) exit 1 }
        ' CHANGELOG.md > release-notes.md || { echo "no CHANGELOG.md section for $tag" >&2; exit 1; }
        grep -Eqv -e '^###([[:space:]]|$)' -e '^[[:space:]]*$' release-notes.md || { echo "empty section for $tag" >&2; exit 1; }
        gh release view "$tag" >/dev/null 2>&1 || gh release create "$tag" --notes-file release-notes.md --verify-tag
```

## Next
"""
#: The line of :data:`CONFORMING_SKILL_SNIPPET` that counts the tags (the bite proof drops it).
SNIPPET_COUNT_LINE = ('[ "$(printf \'%s\\n\' "$tags" | wc -l)" -eq 1 ] || { echo "more than one '
                      'version tag at HEAD:" $tags >&2; exit 1; }')


def run_skill_snippet(test: unittest.TestCase, lines: list[str], head_tags: tuple,
                      changelog: str) -> tuple[subprocess.CompletedProcess, list[str], Path]:
    """Run the skill snippet's ``lines`` under ``bash -e`` in a temp repository on ``master``: an
    earlier commit tagged ``0.9.0``, ``HEAD`` carrying ``head_tags`` (annotated, as git flow
    tags), ``changelog`` as ``CHANGELOG.md``, and :data:`GH_SHIM` first on ``PATH`` so nothing
    calls GitHub. ``(the run, the gh calls in order, the repository)`` (VERIFY F1)."""
    work, env = _workdir(test, "skill-release-snippet-")
    repo = work / "repo"
    _git(work, env, "init", "-q", "-b", "master", str(repo))
    _git(repo, env, "commit", "-q", "--allow-empty", "-m", "earlier")
    _git(repo, env, "tag", "-a", "0.9.0", "-m", "0.9.0")
    _git(repo, env, "commit", "-q", "--allow-empty", "-m", "head")
    for tag in head_tags:
        _git(repo, env, "tag", "-a", tag, "-m", tag)
    (repo / "CHANGELOG.md").write_text(changelog, encoding="utf-8")
    shim_dir = work / "bin"
    shim_dir.mkdir()
    (shim_dir / "gh").write_text(GH_SHIM, encoding="utf-8")
    (shim_dir / "gh").chmod(0o755)
    log = work / "gh-calls"
    result = bash_e(lines, repo, dict(env, PATH=f"{shim_dir}{os.pathsep}{env.get('PATH', os.defpath)}",
                                      GH_SHIM_LOG=str(log)))
    calls = log.read_text(encoding="utf-8").splitlines() if log.exists() else []
    return result, calls, repo


class SkillReleaseSnippetExecutionTest(unittest.TestCase):
    """CR-MDB-070 C4 RED (VERIFY F1) — the git-workflow skill's release-job snippet (``## Releases``,
    the fenced ``create-release`` block): its release step's ``run:`` lines EXECUTED under
    ``bash -e`` with a ``gh`` shim. Two version tags at ``HEAD`` fail naming both, before any
    ``gh`` call; one tag with its section reaches ``gh release create``; none exits 0 with nothing
    to release."""

    SKILL: str | None = None

    def _lines(self) -> list[str]:
        text = self.SKILL if self.SKILL is not None else GIT_WORKFLOW_SKILL.read_text(encoding="utf-8")
        snippet = release_job_snippet(text)
        self.assertIsNotNone(snippet, "## Releases carries the release-job snippet")
        steps = workflow_steps((snippet or "").splitlines())
        hits = [step for step in steps if any("gh release create" in line for line in step["run"])]
        self.assertEqual(len(hits), 1, f"one snippet step creates the release; found {len(hits)}")
        return hits[0]["run"]

    def test_two_version_tags_at_head_fail_naming_both_before_any_gh_call(self):
        result, calls, _repo = run_skill_snippet(self, self._lines(), ("1.0.0", "1.0.1"),
                                                 CHANGELOG_TWO_TAGS)
        output = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0, f"two tags fail the step; output={output!r}")
        self.assertIn("more than one version tag", output, f"output={output!r}")
        self.assertIn("1.0.0", output)
        self.assertIn("1.0.1", output)
        self.assertNotIn("no CHANGELOG.md section", output, "not the misleading missing-section error")
        self.assertEqual(calls, [], "nothing reaches gh")

    def test_one_version_tag_with_its_section_reaches_gh_release_create_with_the_notes(self):
        for head_tags in (("1.2.3",), ("v1.2.3", "1.2.3", "1.2.3-rc.1")):
            with self.subTest(head_tags=head_tags):
                result, calls, repo = run_skill_snippet(self, self._lines(), head_tags,
                                                        CHANGELOG_GOOD)
                self.assertEqual(result.returncode, 0,
                                 f"stdout={result.stdout!r} stderr={result.stderr!r}")
                self.assertEqual(len(calls), 2, f"gh view then gh create; calls={calls!r}")
                self.assertEqual(calls[0].split()[:3], ["release", "view", "1.2.3"])
                created = calls[1].split()
                self.assertEqual(created[:3], ["release", "create", "1.2.3"])
                self.assertIn("--verify-tag", created)
                self.assertIn("--notes-file", created)
                notes = (repo / created[created.index("--notes-file") + 1]).read_text(encoding="utf-8")
                self.assertIn("The rehearsed release — its notes body.", notes)
                self.assertNotIn("An earlier fix.", notes)

    def test_no_version_tag_at_head_exits_0_with_nothing_to_release_and_no_gh_call(self):
        for head_tags in ((), ("v1.2.3",)):
            with self.subTest(head_tags=head_tags):
                result, calls, _repo = run_skill_snippet(self, self._lines(), head_tags,
                                                         CHANGELOG_GOOD)
                self.assertEqual(result.returncode, 0,
                                 f"stdout={result.stdout!r} stderr={result.stderr!r}")
                self.assertIn("nothing to release", result.stdout + result.stderr)
                self.assertEqual(calls, [], "nothing reaches gh")


class SkillReleaseSnippetConformingSampleProofTest(SkillReleaseSnippetExecutionTest):
    """VERIFY F1 — a snippet written to the finding passes what the skill's must."""

    SKILL = CONFORMING_SKILL_SNIPPET


class SkillReleaseSnippetBiteProofTest(unittest.TestCase):
    """VERIFY F1 — the execution test bites: without its count line the conforming snippet takes
    two tags as one multi-line tag and fails on the misleading missing-section message."""

    def test_a_snippet_without_the_count_fails_two_tags_on_the_wrong_message(self):
        self.assertEqual(CONFORMING_SKILL_SNIPPET.count(SNIPPET_COUNT_LINE), 1)
        broken = CONFORMING_SKILL_SNIPPET.replace(SNIPPET_COUNT_LINE + "\n", "")
        steps = workflow_steps((release_job_snippet(broken) or "").splitlines())
        lines = next(step["run"] for step in steps
                     if any("gh release create" in line for line in step["run"]))
        result, calls, _repo = run_skill_snippet(self, lines, ("1.0.0", "1.0.1"),
                                                 CHANGELOG_TWO_TAGS)
        output = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("more than one version tag", output)
        self.assertIn("no CHANGELOG.md section for 1.0.0", output, f"output={output!r}")
        self.assertEqual(calls, [])


# ------------------------------------------------------------- CR-MDB-070 C4 RED (VERIFY F6) ----

class HeaderRedRunCheckerProofTest(unittest.TestCase):
    """VERIFY F6 — the header says, in one unit, that a red ``master`` or release run publishes
    nothing, to re-run the failed jobs, and that a real failure is fixed on a hotfix branch:
    :func:`header_red_run_faults` proved both ways on :data:`CONFORMING_RELEASE`."""

    PARAGRAPH = ("# A red run: when the master run or the release run fails its tests,\n"
                 "# nothing publishes. Re-run the failed jobs; a real failure is fixed on\n"
                 "# a hotfix branch.\n")

    def test_the_conforming_header_passes(self):
        self.assertIn(self.PARAGRAPH, CONFORMING_RELEASE)
        self.assertEqual(header_red_run_faults(CONFORMING_RELEASE), [])

    def test_each_phrase_taken_out_of_the_unit_is_a_fault(self):
        cases = {
            "the paragraph gone": (self.PARAGRAPH + "#\n", ""),
            "no re-run": ("Re-run the failed jobs;", "Push again;"),
            "a whole re-run is not the failed jobs": ("Re-run the failed jobs;",
                                                      "Re-run the workflow;"),
            "no hotfix": ("on\n# a hotfix branch.", "on\n# a new release branch."),
            "nothing publishes unsaid": ("# nothing publishes. ", "# the run stops. "),
        }
        for label, (old, new) in cases.items():
            with self.subTest(case=label):
                self.assertEqual(CONFORMING_RELEASE.count(old), 1, old)
                self.assertEqual(header_red_run_faults(CONFORMING_RELEASE.replace(old, new)),
                                 [HEADER_RED_RUN_FAULT])

    def test_the_phrases_split_across_two_units_do_not_count(self):
        split = CONFORMING_RELEASE.replace(
            "Re-run the failed jobs; a real failure is fixed on\n# a hotfix branch.\n",
            "Re-run the failed jobs.\n#\n# A real failure is fixed on a hotfix branch.\n")
        self.assertNotEqual(split, CONFORMING_RELEASE)
        self.assertEqual(header_red_run_faults(split), [HEADER_RED_RUN_FAULT])
        no_hotfix = CONFORMING_RELEASE.replace("on\n# a hotfix branch.", "on\n# a new branch.")
        self.assertIn("a release or hotfix push", _header(no_hotfix),
                      "another unit of the header still names hotfix")
        self.assertEqual(header_red_run_faults(no_hotfix), [HEADER_RED_RUN_FAULT],
                         "the hotfix of another unit does not count")

    def test_a_paragraph_after_the_header_is_not_the_headers(self):
        moved = CONFORMING_RELEASE.replace(self.PARAGRAPH + "#\n", "").replace(
            "\nname: release\n", "\nname: release\n" + self.PARAGRAPH)
        self.assertNotEqual(moved, CONFORMING_RELEASE)
        self.assertEqual(header_red_run_faults(moved), [HEADER_RED_RUN_FAULT])

    def test_a_rewrapped_paragraph_still_counts(self):
        rewrapped = CONFORMING_RELEASE.replace(
            self.PARAGRAPH,
            "# A red run: when the master run or the release run fails its tests, nothing\n"
            "# publishes. Re-run the failed\n# jobs; a real failure is fixed on a hotfix branch.\n")
        self.assertNotEqual(rewrapped, CONFORMING_RELEASE)
        self.assertEqual(header_red_run_faults(rewrapped), [])


if __name__ == "__main__":
    unittest.main()
