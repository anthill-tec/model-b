"""The rendered ``release.yml`` for every stack and target set (CR-MDB-068 §S4), its action pin
table (§S2), and its command lines executed under ``bash -e`` (CR-MDB-070's way).

Contract: ``docs/changes/CR-MDB-068-release-and-ci-workflow-templates.md`` §S4 (CR-MDB-070's
shape: one workflow, test jobs with no ``if:`` gating every publish, ``create-release`` on the
``master`` push, the guarded publishes on the release event).

The matrix (§S4 AC): each stack alone and all six together, crossed with the target sets none,
``pypi``, ``npm:pkg``, ``github-assets`` and ``pypi,npm:pkg,github-assets``; plus ``pypi:py`` for
a ``pypi`` sub-directory. Every structural class reads the rendered text with the stdlib readers
in ``tests/_helpers.py`` and ``tests.test_release_rehearsal`` — they already read every key this
module needs (job keys, ``needs:``, permissions, a step's ``uses``/``with``/``env``/``id``/``if``/
``working-directory``, ``defaults.run``), so none is extended.

Each class also runs, through a ``*ConformingSampleProofTest`` subclass, against a hand-written
workflow meeting §S4 for two combinations (:data:`SAMPLE_FULL`, :data:`SAMPLE_ALL_STACKS`):
proof that a renderer written to the spec can pass what the real render must. The two execution
classes that need the new ``stamp_version.py`` (``RehearseStampExecutionTest``,
``CreateReleaseCheckExecutionTest``) have no sample proof: the script does not exist yet.

Stdlib only.
"""

import itertools
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests._helpers import (
    workflow_job,
    workflow_job_key,
    workflow_job_names,
    workflow_job_permissions,
    workflow_job_working_directory,
    workflow_key,
    workflow_permissions,
    workflow_push_triggers,
    workflow_steps,
    write_executable,
)
from tests.test_release_rehearsal import (
    CHANGELOG_GOOD,
    CHANGELOG_MISSING,
    CONFORMING_RELEASE,
    CREATE_RELEASE_IF,
    CREATE_RELEASE_TODAY,
    NO_TAG_NOTICE,
    NPM_DRY_RUN,
    PUBLISH_IF,
    REHEARSE_IF,
    RELEASE_BRANCHES,
    TAG_FROM_STEP,
    TAG_STEP_IF,
    action_pin_faults,
    bash_e,
    guard_fixture,
    header_red_run_faults,
    job_keys,
    job_needs,
    normalised_if,
    run_guard,
    run_tag_step,
)
from tests.test_workflow_render import (
    MARKER_PREFIX,
    RELEASE_YML,
    SECTION,
    STAMP,
    render_files,
    workflows_module,
)

REPO_ROOT = Path(__file__).resolve().parent.parent

ALL_STACKS = ("python", "bun", "rust", "quarkus", "java", "arduino")
STACK_SETS = tuple((stack,) for stack in ALL_STACKS) + (ALL_STACKS,)
FULL_TARGETS = ("pypi", "npm:pkg", "github-assets")
TARGET_SETS = ((), ("pypi",), ("npm:pkg",), ("github-assets",), FULL_TARGETS)
#: §S4 AC's matrix, plus a ``pypi`` sub-directory.
MATRIX = tuple(itertools.product(STACK_SETS, TARGET_SETS)) + ((("python",), ("pypi:py",)),)

#: The combination every single-combination class renders.
FULL = (("python",), FULL_TARGETS)
ALL_STACKS_NO_TARGET = (ALL_STACKS, ())

#: §S2 — every action a rendered workflow uses.
ACTIONS = frozenset({"actions/checkout", "actions/setup-python", "astral-sh/setup-uv",
                     "pypa/gh-action-pypi-publish", "actions/setup-node", "oven-sh/setup-bun",
                     "actions/setup-java"})
_USES = re.compile(r"^\s*(?:-\s+)?uses:\s*([\w.-]+/[\w./-]+)@([0-9a-f]{40})\s+#\s+(v\d+\.\d+\.\d+)\s*$")

#: §S4 — the step lines pinned exactly.
PYTHON_TEST = "python -m unittest discover -s tests -t ."
BUN_TEST = ["bun install --frozen-lockfile", "bun test"]
RUST_TEST = ["cargo test --workspace --locked"]
MAVEN_TEST = ["./mvnw -B verify"]
CI_TEST = ".github/scripts/ci-test"
BUILD_ASSETS = ".github/scripts/build-assets"
NOTES_CHECK = 'python3 .github/scripts/changelog_section.py CHANGELOG.md "$version" > /dev/null'
NPM_INSTALL = "npm install -g npm@latest"
NPM_PUBLISH = "npm publish --provenance --access public"
UPLOAD = 'gh release upload "$TAG" dist-assets/* --clobber'
TESTPYPI = {"repository-url": "https://test.pypi.org/legacy/", "skip-existing": "true"}

#: §S4 — the header's phrases (lower-cased, whitespace collapsed, backticks dropped).
HEADER_PHRASES = (
    "the test jobs run in every run",
    "carry no if:",
    "must never be scoped",
    "a publish that needs a skipped job is itself skipped",
    "a release or hotfix push runs the tests and the rehearsal",
    "a master push runs the tests and create-release",
    "a published release runs the tests",
    "every publish needs the tests",
    "dispatch the workflow on master",
)
#: §S4 — a project-neutral header names no account, package or Model B document.
HEADER_FORBIDDEN = ("anthill", "modelb", "model b", "pi-package", "crucible", "docs/", "dn-",
                    "§")


# ------------------------------------------------------------------ the model ----

def parse_target(target: str) -> tuple[str, str]:
    """``(name, dir)`` of a canonical target; ``dir`` is ``.`` when none is given."""
    name, _sep, directory = target.partition(":")
    return name, directory or "."


def versioned(targets) -> list[str]:
    """The ``pypi:<dir>``/``npm:<dir>`` arguments the renderer writes for ``stamp_version.py``."""
    return [f"{name}:{directory}" for name, directory in map(parse_target, targets)
            if name in ("pypi", "npm")]


def stamp_line(targets) -> str:
    args = "".join(f" {arg}" for arg in versioned(targets))
    return ('version=$(python3 .github/scripts/stamp_version.py stamp "$GITHUB_REF_NAME" '
            f'"$GITHUB_RUN_NUMBER"{args})')


def check_line(targets) -> str:
    return 'python3 .github/scripts/stamp_version.py check "$TAG" ' + " ".join(versioned(targets))


def expected_jobs(stacks, targets) -> list[str]:
    return sorted([f"test-{stack}" for stack in stacks] + ["create-release", "rehearse"]
                  + [f"publish-{parse_target(target)[0]}" for target in targets])


def action(step: dict) -> str | None:
    return step["uses"].split("@", 1)[0] if step["uses"] else None


def header_text(text: str) -> str:
    """The leading comment block after the marker line: one lower-cased line, whitespace
    collapsed, backticks dropped."""
    words = []
    for number, line in enumerate(text.splitlines()):
        if number == 0 and line.startswith(MARKER_PREFIX):
            continue
        if line.strip() and not line.startswith("#"):
            break
        words.append(line.lstrip("#").strip())
    return " ".join(" ".join(words).replace("`", "").split()).lower()


def run_lines(steps: list[dict]) -> list[str]:
    """The command lines of ``steps``, in order, comments and blanks dropped."""
    return [line.strip() for step in steps for line in step["run"]
            if line.strip() and not line.strip().startswith("#")]


def target_dirs(test: unittest.TestCase, combos, name: str):
    """``(stacks, targets, dir)`` for each combination carrying target ``name``; at least one."""
    found = [(stacks, targets, parse_target(target)[1]) for stacks, targets in combos
             for target in targets if parse_target(target)[0] == name]
    test.assertTrue(found, f"no combination renders a {name} target")
    return found


# ------------------------------------------------------------------ the sources ----

_CO = "actions/checkout@11d5960a326750d5838078e36cf38b85af677262 # v4.4.0"
_SP = "actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97 # v7.0.0"
_UV = "astral-sh/setup-uv@d0cc045d04ccac9d8b7881df0226f9e82c39688e # v6.8.0"
_PP = "pypa/gh-action-pypi-publish@dc37677b2e1c63e2034f94d8a5b11f265b73ba33 # v1.14.2"
_SN = "actions/setup-node@49933ea5288caeca8642d1e84afbd3f7d6820020 # v4.4.0"
_SB = "oven-sh/setup-bun@" + "b" * 40 + " # v2.0.2"
_SJ = "actions/setup-java@" + "c" * 40 + " # v5.0.0"


def _pin(uses: str) -> tuple[str, tuple[str, str]]:
    match = _USES.match(f"uses: {uses}")
    if match is None:
        raise AssertionError(f"fixture pin {uses!r}")
    return match.group(1), (match.group(2), match.group(3))


#: The sample proofs' pin table: Model B's pins today, and invented ones for the two new actions.
SAMPLE_PINS = dict(map(_pin, (_CO, _SP, _UV, _PP, _SN, _SB, _SJ)))

_GUARD = """\
      - name: Guard - a version tag on master's history
        run: |
          if ! [[ "$GITHUB_REF" =~ ^refs/tags/[0-9]+\\.[0-9]+\\.[0-9]+$ ]]; then
            echo "::error::refusing to publish: $GITHUB_REF is not an X.Y.Z tag ref"
            exit 1
          fi
          git fetch --no-tags origin master
          if ! git merge-base --is-ancestor "$GITHUB_SHA" origin/master; then
            echo "::error::refusing to publish: $GITHUB_SHA is not on origin/master"
            exit 1
          fi
"""

_HEADER = """\
# generated by modelb-axi (Model B release workflow); sha256 0000
# Release workflow: the project's test jobs gate every publish.
#
# The test jobs run in every run. They carry no `if:` and must never be
# scoped: `needs:` orders jobs only within one run, and a publish that
# needs a skipped job is itself skipped, silently.
#
# - A release or hotfix push runs the tests and the rehearsal.
# - A master push runs the tests and create-release, which releases the
#   version tag at HEAD.
# - A published release runs the tests{publishes}.
# Every publish needs the tests.
#
# Recovery: when the master run finds no version tag at HEAD, dispatch
# the workflow on master.
#
# A red run: when the master run or the release run fails its tests,
# nothing publishes. Re-run the failed jobs; a real failure is fixed on
# a hotfix branch.
#
# One-time setup:
# - repository secret RELEASE_PAT: fine-grained, this repository only,
#   Contents read/write;
{setup}
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
"""

_SETUP_FULL = """\
# - pypi: environments `pypi` and `testpypi`; the `testpypi` environment
#   admits the `release/**` and `hotfix/**` branches and carries no
#   required reviewers; pending trusted publishers on pypi.org and
#   test.pypi.org for this workflow;
# - npm: environment `npm`; the NPM_TOKEN secret for the first publish,
#   deleted once the npm trusted publisher exists;
# - github-assets: an executable .github/scripts/build-assets.
"""

_CREATE_RELEASE = """\
  create-release:
    needs: [{needs}]
    if: >-
      github.ref == 'refs/heads/master' &&
      (github.event_name == 'push' || github.event_name == 'workflow_dispatch')
    runs-on: ubuntu-latest
    permissions:
      contents: write
    steps:
      - uses: {co}
        with:
          fetch-depth: 0
      - name: The version tag at HEAD
        id: tag
        run: |
          tags=$(git tag --points-at HEAD | grep -E '^[0-9]+\\.[0-9]+\\.[0-9]+$' || true)
          count=$(printf '%s' "$tags" | grep -c . || true)
          if [ "$count" -gt 1 ]; then
            echo "::error::more than one version tag at HEAD: $(echo $tags)"
            exit 1
          fi
          if [ -z "$tags" ]; then
            echo "::notice::no version tag at HEAD — nothing to release"
          fi
          echo "tag=$tags" >> "$GITHUB_OUTPUT"
{check}      - name: Create the GitHub Release
        if: steps.tag.outputs.tag != ''
        env:
          GH_TOKEN: ${{{{ secrets.RELEASE_PAT }}}}
          TAG: ${{{{ steps.tag.outputs.tag }}}}
        run: |
          python3 .github/scripts/changelog_section.py CHANGELOG.md "$TAG" > "$RUNNER_TEMP/notes.md"
          if ! gh release view "$TAG" >/dev/null 2>&1; then
            gh release create "$TAG" --notes-file "$RUNNER_TEMP/notes.md" --verify-tag
          fi

"""

_REHEARSE_HEAD = """\
  rehearse:
    needs: [{needs}]
    if: >-
      (startsWith(github.ref, 'refs/heads/release/') ||
       startsWith(github.ref, 'refs/heads/hotfix/')) &&
      (github.event_name == 'push' || github.event_name == 'workflow_dispatch')
    runs-on: ubuntu-latest
{permissions}    steps:
      - uses: {co}
      - name: Stamp the dev version and check the release notes
        run: |
          {stamp}
          python3 .github/scripts/changelog_section.py CHANGELOG.md "$version" > /dev/null
"""

_SAMPLE_FULL_JOBS = f"""\
  test-python:
    runs-on: ubuntu-latest
    steps:
      - uses: {_CO}
        with:
          fetch-depth: 0
      - uses: {_SP}
        with:
          python-version: "3.14"
      - uses: {_UV}
      - name: Run the tests
        run: python -m unittest discover -s tests -t .

""" + _CREATE_RELEASE.format(needs="test-python", co=_CO, check="""\
      - name: The tag matches every version source
        if: steps.tag.outputs.tag != ''
        env:
          TAG: ${{ steps.tag.outputs.tag }}
        run: python3 .github/scripts/stamp_version.py check "$TAG" pypi:. npm:pkg
""") + _REHEARSE_HEAD.format(
    needs="test-python", co=_CO, stamp=stamp_line(FULL_TARGETS),
    permissions="    environment: testpypi\n    permissions:\n      contents: read\n"
                "      id-token: write\n") + f"""\
      - uses: {_UV}
      - run: uv build
      - uses: {_PP}
        with:
          repository-url: https://test.pypi.org/legacy/
          skip-existing: true
      - uses: {_SN}
        with:
          node-version: "22"
      - name: npm new enough for the dry-run publish
        run: npm install -g npm@latest
      - name: Ship the root CHANGELOG.md in the package
        working-directory: pkg
        run: cp "$GITHUB_WORKSPACE/CHANGELOG.md" .
      - name: Dry-run the npm publish
        working-directory: pkg
        run: npm publish --dry-run --access public --tag dev
      - name: Build the release assets
        run: |
          test -x .github/scripts/build-assets
          .github/scripts/build-assets
      - name: The release assets are not empty
        run: |
          if [ -z "$(ls -A dist-assets 2>/dev/null)" ]; then
            echo "::error::dist-assets/ is empty"
            exit 1
          fi

  publish-pypi:
    needs: [test-python]
    if: github.event_name == 'release'
    runs-on: ubuntu-latest
    environment: pypi
    permissions:
      contents: read
      id-token: write
    steps:
      - uses: {_CO}
        with:
          fetch-depth: 0
{_GUARD}      - uses: {_UV}
      - run: uv build
      - uses: {_PP}

  publish-npm:
    needs: [test-python]
    if: github.event_name == 'release'
    runs-on: ubuntu-latest
    environment: npm
    permissions:
      contents: read
      id-token: write
    defaults:
      run:
        working-directory: pkg
    steps:
      - uses: {_CO}
        with:
          fetch-depth: 0
{_GUARD}      - uses: {_SN}
        with:
          node-version: "22"
          registry-url: https://registry.npmjs.org
      - name: npm new enough for Trusted Publishing
        run: npm install -g npm@latest
      - name: Ship the root CHANGELOG.md in the package
        run: cp "$GITHUB_WORKSPACE/CHANGELOG.md" .
      - name: Publish
        env:
          NODE_AUTH_TOKEN: ${{{{ secrets.NPM_TOKEN }}}}
        run: npm publish --provenance --access public

  publish-github-assets:
    needs: [test-python]
    if: github.event_name == 'release'
    runs-on: ubuntu-latest
    permissions:
      contents: write
    steps:
      - uses: {_CO}
        with:
          fetch-depth: 0
{_GUARD}      - name: Build the release assets
        run: |
          test -x .github/scripts/build-assets
          .github/scripts/build-assets
      - name: Upload the release assets
        env:
          GH_TOKEN: ${{{{ github.token }}}}
          TAG: ${{{{ github.ref_name }}}}
        run: gh release upload "$TAG" dist-assets/* --clobber
"""

_SAMPLE_ALL_STACKS_JOBS = f"""\
  test-python:
    runs-on: ubuntu-latest
    steps:
      - uses: {_CO}
        with:
          fetch-depth: 0
      - uses: {_SP}
        with:
          python-version: "3.14"
      - uses: {_UV}
      - run: python -m unittest discover -s tests -t .

  test-bun:
    runs-on: ubuntu-latest
    steps:
      - uses: {_CO}
        with:
          fetch-depth: 0
      - uses: {_SB}
      - run: bun install --frozen-lockfile
      - run: bun test

  test-rust:
    runs-on: ubuntu-latest
    steps:
      - uses: {_CO}
        with:
          fetch-depth: 0
      - run: cargo test --workspace --locked

  test-quarkus:
    runs-on: ubuntu-latest
    steps:
      - uses: {_CO}
        with:
          fetch-depth: 0
      - uses: {_SJ}
        with:
          distribution: temurin
          java-version: "21"
      - run: ./mvnw -B verify

  test-java:
    runs-on: ubuntu-latest
    steps:
      - uses: {_CO}
        with:
          fetch-depth: 0
      - uses: {_SJ}
        with:
          distribution: temurin
          java-version: "21"
      - run: ./mvnw -B verify

  test-arduino:
    runs-on: ubuntu-latest
    steps:
      - uses: {_CO}
        with:
          fetch-depth: 0
      - name: Run the project's CI test script
        run: |
          if ! test -x .github/scripts/ci-test; then
            echo "::error::.github/scripts/ci-test is missing or not executable"
            exit 1
          fi
          .github/scripts/ci-test

""" + _CREATE_RELEASE.format(
    needs=", ".join(f"test-{stack}" for stack in ALL_STACKS), co=_CO, check="") + \
    _REHEARSE_HEAD.format(needs=", ".join(f"test-{stack}" for stack in ALL_STACKS), co=_CO,
                          stamp=stamp_line(()), permissions="    permissions:\n"
                                                            "      contents: read\n")

#: A ``release.yml`` meeting §S4 for :data:`FULL`.
SAMPLE_FULL = _HEADER.format(
    publishes=" and the guarded publishes", setup=_SETUP_FULL) + _SAMPLE_FULL_JOBS
#: A ``release.yml`` meeting §S4 for :data:`ALL_STACKS_NO_TARGET`.
SAMPLE_ALL_STACKS = _HEADER.format(publishes="", setup="") + _SAMPLE_ALL_STACKS_JOBS
SAMPLES = {FULL: SAMPLE_FULL, ALL_STACKS_NO_TARGET: SAMPLE_ALL_STACKS}


class _RenderSource:
    """Where a class reads the rendered workflow: ``workflows.render`` over :data:`MATRIX`, unless
    a proof subclass sets ``SAMPLES`` (then ``COMBOS`` is their keys and the pin table is
    :data:`SAMPLE_PINS`)."""

    SAMPLES: dict | None = None

    @classmethod
    def combos(cls):
        return tuple(cls.SAMPLES) if cls.SAMPLES is not None else MATRIX

    @classmethod
    def release_text(cls, stacks, targets) -> str:
        if cls.SAMPLES is not None:
            return cls.SAMPLES[(tuple(stacks), tuple(targets))]
        return render_files(list(stacks), list(targets))[RELEASE_YML]

    @classmethod
    def pins(cls) -> dict:
        return SAMPLE_PINS if cls.SAMPLES is not None else workflows_module().ACTION_PINS

    @classmethod
    def section_script(cls) -> str:
        """The ``changelog_section.py`` an execution writes into its temp repository."""
        if cls.SAMPLES is not None:
            return (REPO_ROOT / ".github" / "scripts" / "changelog_section.py").read_text(
                encoding="utf-8")
        return render_files(list(FULL[0]), list(FULL[1]))[SECTION]

    def job(self, stacks, targets, name: str) -> list[str]:
        return workflow_job(self.release_text(stacks, targets), name)

    def each(self, predicate=lambda _stacks, _targets: True):
        """``(stacks, targets, text)`` for each combination matching ``predicate``; at least one."""
        chosen = [(stacks, targets) for stacks, targets in self.combos()
                  if predicate(stacks, targets)]
        if not chosen:
            raise AssertionError("no combination matches; the check would be vacuous")
        for stacks, targets in chosen:
            yield stacks, targets, self.release_text(stacks, targets)


# ------------------------------------------------------------------ the workflow ----

class RenderedWorkflowShapeTest(_RenderSource, unittest.TestCase):
    """§S4 — name, triggers, permissions, the job set, runners, no ``shell:``, and ``needs:``."""

    def test_name_triggers_and_workflow_permissions(self):
        for stacks, targets, text in self.each():
            with self.subTest(stacks=stacks, targets=targets):
                self.assertEqual(workflow_key(text, "name"), "release")
                triggers = workflow_push_triggers(text)
                self.assertEqual(sorted(triggers["branches"]), sorted(RELEASE_BRANCHES))
                self.assertEqual(triggers["tags"], [])
                self.assertEqual(triggers["release"], ["published"])
                self.assertTrue(triggers["workflow_dispatch"])
                self.assertFalse(triggers["pull_request"])
                self.assertEqual(workflow_permissions(text), {"contents": "read"})

    def test_the_jobs_are_a_test_job_per_stack_create_release_rehearse_and_a_publish_per_target(self):
        for stacks, targets, text in self.each():
            with self.subTest(stacks=stacks, targets=targets):
                self.assertEqual(sorted(workflow_job_names(text)), expected_jobs(stacks, targets))

    def test_every_job_runs_on_ubuntu_latest_and_no_step_sets_a_shell(self):
        for stacks, targets, text in self.each():
            with self.subTest(stacks=stacks, targets=targets):
                for name in workflow_job_names(text):
                    self.assertEqual(workflow_job_key(workflow_job(text, name), "runs-on"),
                                     "ubuntu-latest", name)
                self.assertEqual([ln for ln in text.splitlines()
                                  if re.match(r"\s*(?:-\s+)?shell:", ln)], [])

    def test_every_other_job_needs_every_test_job(self):
        for stacks, targets, text in self.each():
            tests = sorted(f"test-{stack}" for stack in stacks)
            for name in workflow_job_names(text):
                if name.startswith("test-"):
                    continue
                with self.subTest(stacks=stacks, targets=targets, job=name):
                    self.assertEqual(sorted(job_needs(workflow_job(text, name)) or []), tests)


class RenderedTestJobsTest(_RenderSource, unittest.TestCase):
    """§S4 — ``test-<stack>``: no ``if:``, no ``needs:``, a full-history checkout first, then the
    stack's row of the table."""

    def _jobs(self, stack: str):
        for stacks, targets, text in self.each(lambda stacks, _targets: stack in stacks):
            yield stacks, targets, workflow_job(text, f"test-{stack}")

    def test_no_test_job_has_if_or_needs_and_each_checks_out_full_history_first(self):
        for stack in ALL_STACKS:
            for stacks, targets, job in self._jobs(stack):
                with self.subTest(stack=stack, stacks=stacks, targets=targets):
                    self.assertEqual([k for k in job_keys(job) if k in ("if", "needs")], [])
                    first = workflow_steps(job)[0]
                    self.assertEqual((action(first), first["with"]),
                                     ("actions/checkout", {"fetch-depth": "0"}))

    def test_python_sets_up_python_3_14_and_uv_then_runs_unittest_discovery(self):
        for stacks, targets, job in self._jobs("python"):
            with self.subTest(stacks=stacks, targets=targets):
                steps = workflow_steps(job)
                self.assertEqual([(action(s), s["with"]) for s in steps[:3]],
                                 [("actions/checkout", {"fetch-depth": "0"}),
                                  ("actions/setup-python", {"python-version": "3.14"}),
                                  ("astral-sh/setup-uv", {})])
                self.assertEqual(len(steps), 4, steps)
                self.assertEqual((steps[3]["uses"], steps[3]["run"], steps[3]["env"],
                                  steps[3]["working-directory"]), (None, [PYTHON_TEST], {}, None),
                                 "§S4/§S7: the suite at the root, no sandbox variables")

    def _assert_row(self, stack: str, setup: list[str], lines: list[str]):
        for stacks, targets, job in self._jobs(stack):
            with self.subTest(stack=stack, stacks=stacks, targets=targets):
                steps = workflow_steps(job)
                uses = [step for step in steps if step["uses"]]
                self.assertEqual([action(step) for step in uses], ["actions/checkout", *setup])
                self.assertEqual(steps[:len(uses)], uses, "§S4: the setup precedes the commands")
                self.assertEqual(run_lines(steps), lines)
                self.assertEqual({step["working-directory"] for step in steps}, {None},
                                 "§S4: the jobs run at the repository root")

    def test_bun_sets_up_bun_then_installs_frozen_then_tests(self):
        self._assert_row("bun", ["oven-sh/setup-bun"], BUN_TEST)

    def test_rust_uses_the_runners_toolchain(self):
        self._assert_row("rust", [], RUST_TEST)

    def test_quarkus_and_java_set_up_temurin_21_then_verify_with_the_wrapper(self):
        for stack in ("quarkus", "java"):
            self._assert_row(stack, ["actions/setup-java"], MAVEN_TEST)
            for _stacks, _targets, job in self._jobs(stack):
                setup = workflow_steps(job)[1]
                self.assertEqual(setup["with"], {"distribution": "temurin", "java-version": "21"})

    def test_arduino_checks_ci_test_is_executable_then_runs_it(self):
        for stacks, targets, job in self._jobs("arduino"):
            with self.subTest(stacks=stacks, targets=targets):
                steps = workflow_steps(job)
                self.assertEqual([action(step) for step in steps if step["uses"]],
                                 ["actions/checkout"])
                lines = run_lines(steps)
                self.assertEqual(lines[-1], CI_TEST, "§S4: ci-test runs last")
                checks = [i for i, line in enumerate(lines) if f"test -x {CI_TEST}" in line]
                self.assertEqual(len(checks), 1, lines)


class RenderedCreateReleaseTest(_RenderSource, unittest.TestCase):
    """§S4 — ``create-release``, always: CR-MDB-070's ``if:``, ``contents: write``, checkout, the
    ``id: tag`` step, the check step exactly with a versioned target, the release step."""

    def test_its_if_keys_and_permission(self):
        for stacks, targets, _text in self.each():
            with self.subTest(stacks=stacks, targets=targets):
                job = self.job(stacks, targets, "create-release")
                self.assertEqual(normalised_if(workflow_job_key(job, "if")), CREATE_RELEASE_IF)
                self.assertEqual(sorted(job_keys(job)),
                                 sorted(["needs", "if", "runs-on", "permissions", "steps"]))
                self.assertEqual(workflow_job_permissions(job), {"contents": "write"})

    def test_checkout_then_the_tag_step_of_cr_mdb_070(self):
        reference = next(step for step in workflow_steps(workflow_job(CONFORMING_RELEASE,
                                                                      "create-release"))
                         if step["id"] == "tag")
        for stacks, targets, _text in self.each():
            with self.subTest(stacks=stacks, targets=targets):
                steps = workflow_steps(self.job(stacks, targets, "create-release"))
                self.assertEqual((action(steps[0]), steps[0]["with"]),
                                 ("actions/checkout", {"fetch-depth": "0"}))
                self.assertEqual((steps[1]["id"], steps[1]["if"], steps[1]["uses"]),
                                 ("tag", None, None))
                self.assertEqual(steps[1]["run"], reference["run"])

    def test_the_check_step_is_there_exactly_with_a_versioned_target(self):
        for stacks, targets, _text in self.each():
            with self.subTest(stacks=stacks, targets=targets):
                steps = workflow_steps(self.job(stacks, targets, "create-release"))
                if not versioned(targets):
                    self.assertEqual(len(steps), 3, [s["run"] or s["uses"] for s in steps])
                    continue
                self.assertEqual(len(steps), 4, [s["run"] or s["uses"] for s in steps])
                check = steps[2]
                self.assertEqual((check["uses"], check["if"], check["env"], run_lines([check])),
                                 (None, TAG_STEP_IF, {"TAG": TAG_FROM_STEP}, [check_line(targets)]))

    def test_the_release_step_is_cr_mdb_070s_last(self):
        reference = workflow_steps(CREATE_RELEASE_TODAY.splitlines())[2]
        for stacks, targets, _text in self.each():
            with self.subTest(stacks=stacks, targets=targets):
                release = workflow_steps(self.job(stacks, targets, "create-release"))[-1]
                self.assertEqual((release["uses"], release["if"], release["run"]),
                                 (None, TAG_STEP_IF, reference["run"]))
                self.assertEqual(release["env"], {"GH_TOKEN": "${{ secrets.RELEASE_PAT }}",
                                                  "TAG": TAG_FROM_STEP})


class RenderedRehearseTest(_RenderSource, unittest.TestCase):
    """§S4 — ``rehearse``, always: the release/hotfix ``if:``; ``testpypi`` and ``id-token``
    exactly with ``pypi``; checkout, the stamp-and-notes step, then each target's steps in
    canonical order."""

    def test_its_if_keys_environment_and_permissions(self):
        for stacks, targets, _text in self.each():
            pypi = any(parse_target(t)[0] == "pypi" for t in targets)
            with self.subTest(stacks=stacks, targets=targets):
                job = self.job(stacks, targets, "rehearse")
                self.assertEqual(normalised_if(workflow_job_key(job, "if")), REHEARSE_IF)
                self.assertEqual(workflow_job_key(job, "environment"),
                                 "testpypi" if pypi else None)
                self.assertEqual(workflow_job_permissions(job),
                                 {"contents": "read", "id-token": "write"} if pypi
                                 else {"contents": "read"})
                self.assertEqual(sorted(job_keys(job)), sorted(
                    ["needs", "if", "runs-on", "permissions", "steps"]
                    + (["environment"] if pypi else [])))
                self.assertIsNone(workflow_job_working_directory(job))

    def test_checkout_then_the_stamp_and_notes_step(self):
        for stacks, targets, _text in self.each():
            with self.subTest(stacks=stacks, targets=targets):
                steps = workflow_steps(self.job(stacks, targets, "rehearse"))
                self.assertEqual(action(steps[0]), "actions/checkout")
                self.assertIsNone(steps[1]["uses"])
                self.assertEqual(run_lines([steps[1]]), [stamp_line(targets), NOTES_CHECK])

    def test_each_targets_steps_follow_in_canonical_order_and_nothing_else(self):
        for stacks, targets, _text in self.each():
            with self.subTest(stacks=stacks, targets=targets):
                steps = workflow_steps(self.job(stacks, targets, "rehearse"))
                self.assertEqual(self._consume(steps, targets), len(steps),
                                 "§S4: nothing follows the last target's steps")

    def _consume(self, steps: list[dict], targets) -> int:
        """Assert each target's steps from ``steps[2]`` on; the index after the last."""
        at = 2
        for target in targets:
            name, directory = parse_target(target)
            where = None if directory == "." else directory
            if name == "pypi":
                setup, build, upload = steps[at:at + 3]
                self.assertEqual(action(setup), "astral-sh/setup-uv", target)
                self.assertEqual((build["uses"], build["run"], build["working-directory"]),
                                 (None, ["uv build"], where), target)
                packages = {} if where is None else {"packages-dir": f"{directory}/dist"}
                self.assertEqual((action(upload), upload["with"]),
                                 ("pypa/gh-action-pypi-publish", {**TESTPYPI, **packages}))
                at += 3
            elif name == "npm":
                self.assertEqual((action(steps[at]), steps[at]["with"]),
                                 ("actions/setup-node", {"node-version": "22"}))
                self.assertEqual(run_lines([steps[at + 1]]), [NPM_INSTALL])
                at += 2 + (where is not None)
                if where is not None:
                    self.assertIsNone(steps[at - 1]["uses"], "§S4: the CHANGELOG.md copy")
                dry = steps[at]
                self.assertEqual((dry["uses"], run_lines([dry]), dry["working-directory"]),
                                 (None, [NPM_DRY_RUN], where), target)
                at += 1
            else:
                rest = steps[at:]
                self.assertTrue(rest and all(step["uses"] is None for step in rest), rest)
                lines = run_lines(rest)
                check = [i for i, line in enumerate(lines) if f"test -x {BUILD_ASSETS}" in line]
                self.assertEqual(len(check), 1, lines)
                self.assertIn(BUILD_ASSETS, lines[check[0] + 1:])
                self.assertTrue(any("dist-assets" in line for line in
                                    lines[lines.index(BUILD_ASSETS):]), lines)
                at = len(steps)
        return at


class RenderedPublishJobsTest(_RenderSource, unittest.TestCase):
    """§S4 — one publish job per target, on the release event: id, permissions, environment, a
    full-history checkout, CR-MDB-070's guard, then the target's steps."""

    GUARD = workflow_steps(workflow_job(CONFORMING_RELEASE, "publish-pypi"))[1]["run"]

    def _head(self, job: list[str], keys: list[str], permissions: dict, environment):
        self.assertEqual(normalised_if(workflow_job_key(job, "if")), PUBLISH_IF)
        self.assertEqual(sorted(job_keys(job)), sorted(keys))
        self.assertEqual(workflow_job_permissions(job), permissions)
        self.assertEqual(workflow_job_key(job, "environment"), environment)
        steps = workflow_steps(job)
        self.assertEqual((action(steps[0]), steps[0]["with"]),
                         ("actions/checkout", {"fetch-depth": "0"}))
        self.assertEqual((steps[1]["uses"], steps[1]["run"]), (None, self.GUARD),
                         "§S4: CR-MDB-070's ref guard second")
        return steps[2:]

    def test_publish_pypi(self):
        for stacks, targets, directory in target_dirs(self, self.combos(), "pypi"):
            with self.subTest(stacks=stacks, targets=targets):
                job = self.job(stacks, targets, "publish-pypi")
                rest = self._head(job, ["needs", "if", "runs-on", "environment", "permissions",
                                        "steps"], {"contents": "read", "id-token": "write"}, "pypi")
                where = None if directory == "." else directory
                self.assertEqual([(action(s), s["run"], s["working-directory"], s["with"])
                                  for s in rest],
                                 [("astral-sh/setup-uv", [], None, {}),
                                  (None, ["uv build"], where, {}),
                                  ("pypa/gh-action-pypi-publish", [], None,
                                   {} if where is None else {"packages-dir": f"{where}/dist"})])

    def test_publish_npm(self):
        for stacks, targets, directory in target_dirs(self, self.combos(), "npm"):
            with self.subTest(stacks=stacks, targets=targets):
                job = self.job(stacks, targets, "publish-npm")
                where = None if directory == "." else directory
                keys = ["needs", "if", "runs-on", "environment", "permissions", "steps"]
                rest = self._head(job, keys + (["defaults"] if where else []),
                                  {"contents": "read", "id-token": "write"}, "npm")
                self.assertEqual(workflow_job_working_directory(job), where)
                self.assertEqual((action(rest[0]), rest[0]["with"]),
                                 ("actions/setup-node", {"node-version": "22",
                                                         "registry-url": "https://registry.npmjs.org"}))
                self.assertEqual(run_lines([rest[1]]), [NPM_INSTALL])
                self.assertEqual(len(rest), 4 if where else 3, [s["run"] for s in rest])
                publish = rest[-1]
                self.assertEqual((publish["uses"], run_lines([publish]), publish["env"]),
                                 (None, [NPM_PUBLISH],
                                  {"NODE_AUTH_TOKEN": "${{ secrets.NPM_TOKEN }}"}))
                self.assertEqual({s["working-directory"] for s in rest}, {None},
                                 "§S4: the job's defaults.run carry the directory")

    def test_publish_github_assets(self):
        for stacks, targets, _directory in target_dirs(self, self.combos(), "github-assets"):
            with self.subTest(stacks=stacks, targets=targets):
                job = self.job(stacks, targets, "publish-github-assets")
                rest = self._head(job, ["needs", "if", "runs-on", "permissions", "steps"],
                                  {"contents": "write"}, None)
                self.assertTrue(all(step["uses"] is None for step in rest), rest)
                upload = rest[-1]
                self.assertEqual((run_lines([upload]), upload["env"]),
                                 ([UPLOAD], {"GH_TOKEN": "${{ github.token }}",
                                             "TAG": "${{ github.ref_name }}"}))
                lines = run_lines(rest[:-1])
                check = [i for i, line in enumerate(lines) if f"test -x {BUILD_ASSETS}" in line]
                self.assertEqual(len(check), 1, lines)
                self.assertIn(BUILD_ASSETS, lines[check[0] + 1:])


class RenderedHeaderTest(_RenderSource, unittest.TestCase):
    """§S4 — the header: project-neutral; the never-scope warning, the map, both recoveries; the
    one-time setup for the rendered targets only."""

    def test_the_header_names_every_phrase(self):
        for stacks, targets, text in self.each():
            with self.subTest(stacks=stacks, targets=targets):
                header = header_text(text)
                self.assertEqual([p for p in HEADER_PHRASES if p not in header], [])

    def test_the_header_says_a_red_run_publishes_nothing_re_run_or_hotfix(self):
        for stacks, targets, text in self.each():
            with self.subTest(stacks=stacks, targets=targets):
                self.assertEqual(header_red_run_faults(text), [])

    def test_the_header_is_project_neutral(self):
        for stacks, targets, text in self.each():
            with self.subTest(stacks=stacks, targets=targets):
                header = header_text(text)
                self.assertEqual([word for word in HEADER_FORBIDDEN if word in header], [])

    def test_the_setup_names_release_pat_and_each_rendered_targets_needs(self):
        for stacks, targets, text in self.each():
            names = {parse_target(t)[0] for t in targets}
            with self.subTest(stacks=stacks, targets=targets):
                header = header_text(text)
                self.assertIn("one-time setup", header)
                setup = header.split("one-time setup", 1)[1]
                self.assertIn("release_pat", setup)
                if "pypi" in names:
                    for needle in ("testpypi", "release/**", "hotfix/**",
                                   "no required reviewers", "trusted publisher"):
                        self.assertIn(needle, setup, needle)
                else:
                    self.assertNotIn("testpypi", header, "§S4: only the rendered targets")
                if "npm" in names:
                    for needle in ("npm_token", "trusted publisher"):
                        self.assertIn(needle, setup, needle)
                else:
                    self.assertNotIn("npm_token", header, "§S4: only the rendered targets")


class ActionPinTableTest(_RenderSource, unittest.TestCase):
    """§S2 — one pin table maps every action to a 40-hex SHA and a ``vX.Y.Z``; every rendered
    ``uses:`` is its entry, and no entry is unused."""

    def test_every_uses_line_is_pinned_from_the_table(self):
        pins = self.pins()
        for stacks, targets, text in self.each():
            with self.subTest(stacks=stacks, targets=targets):
                self.assertEqual(action_pin_faults(text), [])
                for line in text.splitlines():
                    match = _USES.match(line)
                    if match is None:
                        self.assertNotRegex(line, r"^\s*(?:-\s+)?uses:")
                        continue
                    self.assertEqual(pins.get(match.group(1)), (match.group(2), match.group(3)),
                                     line)

    def test_the_table_is_exactly_the_rendered_actions_each_well_formed(self):
        pins = self.pins()
        used = {match.group(1) for _stacks, _targets, text in self.each()
                for match in map(_USES.match, text.splitlines()) if match}
        self.assertEqual(set(pins), set(ACTIONS))
        self.assertEqual(used, set(ACTIONS))
        for name, (sha, version) in pins.items():
            with self.subTest(action=name):
                self.assertRegex(sha, r"^[0-9a-f]{40}$")
                self.assertRegex(version, r"^v\d+\.\d+\.\d+$")

    def test_the_actions_model_b_pins_today_keep_their_pins(self):
        today = {}
        for line in (REPO_ROOT / ".github" / "workflows" / "release.yml").read_text(
                encoding="utf-8").splitlines():
            match = _USES.match(line)
            if match:
                today[match.group(1)] = (match.group(2), match.group(3))
        self.assertTrue(today, "precondition: Model B's release.yml pins actions")
        pins = self.pins()
        self.assertEqual({name: pins.get(name) for name in today}, today)


# ------------------------------------------------------------------ executions ----

def _bin_with_gh(work: Path) -> tuple[Path, Path]:
    """A ``bin/gh`` shim logging each call's argv to ``gh.log``; ``gh release view`` exits 1."""
    log = work / "gh.log"
    write_executable(work / "bin", "gh", (
        "#!/bin/sh\n"
        f'printf "%s\\n" "$*" >> "{log}"\n'
        'if [ "$1 $2" = "release view" ]; then exit 1; fi\n'
        "exit 0\n"))
    return work / "bin", log


class _ExecutionCase(_RenderSource, unittest.TestCase):
    """A temp repository tree and a clean environment for running steps."""

    def repo(self, files: dict[str, str]) -> Path:
        work = Path(tempfile.mkdtemp(prefix="r68-exec-"))
        self.addCleanup(shutil.rmtree, work, True)
        for sub in ("repo", "home", "runner-temp", "bin"):
            (work / sub).mkdir()
        repo = work / "repo"
        for rel, text in files.items():
            path = repo / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        return repo

    def env(self, repo: Path, **extra: str) -> dict:
        work = repo.parent
        env = {key: value for key, value in os.environ.items() if not key.startswith("GIT")}
        env.update(HOME=str(work / "home"), GITHUB_WORKSPACE=str(repo),
                   RUNNER_TEMP=str(work / "runner-temp"),
                   PATH=f"{work / 'bin'}{os.pathsep}{os.environ.get('PATH', '')}")
        env.update(extra)
        return env

    def run_steps(self, job: list[str], steps: list[dict], repo: Path, env: dict
                  ) -> subprocess.CompletedProcess:
        """Each run step from its working directory under ``bash -e``, as a job runs them;
        stops at the first failure and returns that run, else the last."""
        self.assertTrue(steps)
        results = []
        for step in steps:
            self.assertIsNone(step["uses"], step)
            where = step["working-directory"] or workflow_job_working_directory(job) or "."
            results.append(bash_e(step["run"], repo / where, env))
            if results[-1].returncode != 0:
                break
        return results[-1]

    def scripts(self) -> dict[str, str]:
        return {SECTION: self.section_script()}


def _executable(repo: Path, rel: str, body: str) -> None:
    (repo / rel).parent.mkdir(parents=True, exist_ok=True)
    write_executable((repo / rel).parent, Path(rel).name, body)


class CreateReleaseExecutionTest(_ExecutionCase):
    """§S4 — ``create-release``'s tag step and release step run under ``bash -e``."""

    def _steps(self) -> list[dict]:
        return workflow_steps(self.job(*FULL, "create-release"))

    def test_the_tag_step_outputs_the_one_version_tag_at_head(self):
        tag = next(step for step in self._steps() if step["id"] == "tag")
        result, output = run_tag_step(self, tag["run"], ("1.2.3",))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(output.strip(), "tag=1.2.3")

    def test_the_tag_step_with_no_tag_exits_0_with_the_notice(self):
        tag = next(step for step in self._steps() if step["id"] == "tag")
        result, output = run_tag_step(self, tag["run"], ())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(output.strip(), "tag=")
        self.assertIn(NO_TAG_NOTICE, result.stdout + result.stderr)

    def test_the_release_step_creates_the_release_with_the_tags_notes(self):
        job = workflow_job(self.release_text(*FULL), "create-release")
        repo = self.repo({**self.scripts(), "CHANGELOG.md": CHANGELOG_GOOD})
        _bin, log = _bin_with_gh(repo.parent)
        result = self.run_steps(job, [self._steps()[-1]], repo, self.env(repo, TAG="1.2.3"))
        self.assertEqual(result.returncode, 0, result.stderr)
        notes = repo.parent / "runner-temp" / "notes.md"
        self.assertEqual(log.read_text(encoding="utf-8").splitlines(), [
            "release view 1.2.3", f"release create 1.2.3 --notes-file {notes} --verify-tag"])
        self.assertIn("The rehearsed release — its notes body.", notes.read_text(encoding="utf-8"))


class RehearseTargetStepsExecutionTest(_ExecutionCase):
    """§S4 — ``rehearse``'s npm copy step and ``github-assets`` steps under ``bash -e``."""

    def _job_and_steps(self) -> tuple[list[str], list[dict]]:
        job = self.job(*FULL, "rehearse")
        return job, workflow_steps(job)

    def test_the_npm_copy_step_puts_the_root_changelog_into_the_package_dir(self):
        job, steps = self._job_and_steps()
        dry = next(i for i, step in enumerate(steps) if NPM_DRY_RUN in step["run"])
        repo = self.repo({"CHANGELOG.md": CHANGELOG_GOOD, "pkg/package.json": "{}\n"})
        result = self.run_steps(job, [steps[dry - 1]], repo, self.env(repo))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((repo / "pkg" / "CHANGELOG.md").read_text(encoding="utf-8"),
                         CHANGELOG_GOOD)

    def _assets(self, build: str | None) -> subprocess.CompletedProcess:
        job, steps = self._job_and_steps()
        dry = next(i for i, step in enumerate(steps) if NPM_DRY_RUN in step["run"])
        repo = self.repo({})
        if build is not None:
            _executable(repo, BUILD_ASSETS, build)
        return self.run_steps(job, steps[dry + 1:], repo, self.env(repo))

    def test_built_assets_pass(self):
        result = self._assets("#!/bin/sh\nmkdir -p dist-assets\necho fw > dist-assets/fw.bin\n")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_no_build_script_fails(self):
        self.assertNotEqual(self._assets(None).returncode, 0)

    def test_a_build_leaving_dist_assets_empty_fails(self):
        self.assertNotEqual(self._assets("#!/bin/sh\nmkdir -p dist-assets\n").returncode, 0)

    def test_a_failing_build_fails(self):
        self.assertNotEqual(self._assets("#!/bin/sh\nexit 3\n").returncode, 0)


class PublishExecutionTest(_ExecutionCase):
    """§S4 — each publish job's guard, ``publish-npm``'s copy, and ``publish-github-assets``'s
    build and upload, under ``bash -e``."""

    PUBLISH_JOBS = ("publish-pypi", "publish-npm", "publish-github-assets")

    def test_each_guard_passes_a_tag_on_master_and_refuses_the_rest(self):
        fixture = guard_fixture(self)
        (fixture["clone"] / "pkg").mkdir()
        for name in self.PUBLISH_JOBS:
            job = self.job(*FULL, name)
            guard = workflow_steps(job)[1]
            where = guard["working-directory"] or workflow_job_working_directory(job) or "."
            for ref, sha, code in (("refs/tags/1.2.3", fixture["tagged"], 0),
                                   ("refs/tags/v1.2.3", fixture["tagged"], 1),
                                   ("refs/tags/1.2.4", fixture["side"], 1)):
                with self.subTest(job=name, ref=ref):
                    result = run_guard(fixture, guard["run"], where, ref, sha)
                    self.assertEqual(result.returncode, code, result.stdout + result.stderr)

    def test_publish_npm_copies_the_root_changelog_into_its_directory(self):
        job = self.job(*FULL, "publish-npm")
        steps = workflow_steps(job)
        repo = self.repo({"CHANGELOG.md": CHANGELOG_GOOD, "pkg/package.json": "{}\n"})
        result = self.run_steps(job, [steps[-2]], repo, self.env(repo))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((repo / "pkg" / "CHANGELOG.md").read_text(encoding="utf-8"),
                         CHANGELOG_GOOD)

    def test_publish_github_assets_builds_then_uploads_with_clobber(self):
        job = self.job(*FULL, "publish-github-assets")
        repo = self.repo({})
        _executable(repo, BUILD_ASSETS, "#!/bin/sh\nmkdir -p dist-assets\necho fw > dist-assets/fw.bin\n")
        _bin, log = _bin_with_gh(repo.parent)
        result = self.run_steps(job, workflow_steps(job)[2:], repo, self.env(repo, TAG="1.2.3"))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(log.read_text(encoding="utf-8").splitlines(),
                         ["release upload 1.2.3 dist-assets/fw.bin --clobber"])

    def test_publish_github_assets_without_a_build_script_uploads_nothing(self):
        job = self.job(*FULL, "publish-github-assets")
        repo = self.repo({})
        _bin, log = _bin_with_gh(repo.parent)
        result = self.run_steps(job, workflow_steps(job)[2:], repo, self.env(repo, TAG="1.2.3"))
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(log.exists(), "§S4: no upload without a build")


class ArduinoTestJobExecutionTest(_ExecutionCase):
    """§S4 — ``test-arduino``: a missing or non-executable ``ci-test`` fails naming it; an
    executable one runs, and its failure fails the job."""

    def _run(self, body: str | None, mode: int = 0o755) -> subprocess.CompletedProcess:
        job = self.job(*ALL_STACKS_NO_TARGET, "test-arduino")
        repo = self.repo({})
        if body is not None:
            _executable(repo, CI_TEST, body)
            (repo / CI_TEST).chmod(mode)
        return self.run_steps(job, workflow_steps(job)[1:], repo, self.env(repo))

    def test_an_absent_or_non_executable_ci_test_fails_naming_it(self):
        for body, mode in ((None, 0), ("#!/bin/sh\nexit 0\n", 0o644)):
            with self.subTest(present=body is not None):
                result = self._run(body, mode)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(CI_TEST, result.stdout + result.stderr)

    def test_an_executable_ci_test_runs_and_its_status_is_the_jobs(self):
        result = self._run("#!/bin/sh\necho ci-test ran r68\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("ci-test ran r68", result.stdout)
        self.assertNotEqual(self._run("#!/bin/sh\nexit 3\n").returncode, 0)


# ------------------------------------------------------------------ the new script, executed ----

def _version_sources(version: str) -> dict[str, str]:
    return {"pyproject.toml": ('[project]\nname = "fixture"\n'
                               f'version = "{version}"\n'),
            "pkg/package.json": ('{\n  "name": "fixture",\n'
                                 f'  "version": "{version}"\n' + "}\n")}


class RehearseStampExecutionTest(_ExecutionCase):
    """§S4 — the stamp-and-notes step under ``bash -e`` with the rendered scripts: stamped and
    checked; a bad ref fails at the stamp, writing nothing; a missing section fails naming
    ``CHANGELOG.md``."""

    def scripts(self) -> dict[str, str]:
        files = render_files(list(FULL[0]), list(FULL[1]))
        return {STAMP: files[STAMP], SECTION: files[SECTION]}

    def _run(self, targets, ref: str, changelog: str, sources: dict[str, str]):
        job = self.job(("python",), targets, "rehearse")
        repo = self.repo({**self.scripts(), "CHANGELOG.md": changelog, **sources})
        env = self.env(repo, GITHUB_REF_NAME=ref, GITHUB_RUN_NUMBER="7")
        return self.run_steps(job, [workflow_steps(job)[1]], repo, env), repo

    def test_a_release_ref_stamps_every_versioned_target(self):
        result, repo = self._run(FULL_TARGETS, "release/1.2.3", CHANGELOG_GOOD,
                                 _version_sources("1.2.3"))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('version = "1.2.3.dev7"', (repo / "pyproject.toml").read_text(encoding="utf-8"))
        self.assertIn('"version": "1.2.3-dev.7"',
                      (repo / "pkg/package.json").read_text(encoding="utf-8"))

    def test_no_target_needs_no_version_source(self):
        result, _repo = self._run((), "hotfix/1.2.3", CHANGELOG_GOOD, {})
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_a_bad_ref_fails_at_the_stamp_writing_nothing(self):
        result, repo = self._run(FULL_TARGETS, "feature/x", CHANGELOG_GOOD,
                                 _version_sources("1.2.3"))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("feature/x", result.stderr)
        self.assertNotIn("no section for tag", result.stderr)
        self.assertEqual((repo / "pyproject.toml").read_text(encoding="utf-8"),
                         _version_sources("1.2.3")["pyproject.toml"])

    def test_a_missing_section_fails_naming_the_changelog(self):
        result, _repo = self._run(FULL_TARGETS, "release/1.2.3", CHANGELOG_MISSING,
                                  _version_sources("1.2.3"))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("CHANGELOG.md", result.stderr)


class CreateReleaseCheckExecutionTest(_ExecutionCase):
    """§S4 — ``create-release``'s check step under ``bash -e`` with the rendered script: a tag
    every source carries passes; a source off the tag fails naming it."""

    def _run(self, tag: str, version: str) -> subprocess.CompletedProcess:
        files = render_files(list(FULL[0]), list(FULL[1]))
        job = self.job(*FULL, "create-release")
        repo = self.repo({STAMP: files[STAMP], **_version_sources(version)})
        return self.run_steps(job, [workflow_steps(job)[2]], repo, self.env(repo, TAG=tag))

    def test_a_tag_every_source_carries_passes(self):
        result = self._run("1.2.3", "1.2.3")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_a_source_off_the_tag_fails_naming_it(self):
        result = self._run("1.2.4", "1.2.3")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("pyproject.toml", result.stderr)


# ------------------------------------------------------------------ sample proofs ----

class RenderedWorkflowShapeConformingSampleProofTest(RenderedWorkflowShapeTest):
    SAMPLES = SAMPLES


class RenderedTestJobsConformingSampleProofTest(RenderedTestJobsTest):
    SAMPLES = SAMPLES


class RenderedCreateReleaseConformingSampleProofTest(RenderedCreateReleaseTest):
    SAMPLES = SAMPLES


class RenderedRehearseConformingSampleProofTest(RenderedRehearseTest):
    SAMPLES = SAMPLES


class RenderedPublishJobsConformingSampleProofTest(RenderedPublishJobsTest):
    SAMPLES = SAMPLES


class RenderedHeaderConformingSampleProofTest(RenderedHeaderTest):
    SAMPLES = SAMPLES


class ActionPinTableConformingSampleProofTest(ActionPinTableTest):
    SAMPLES = SAMPLES


class CreateReleaseExecutionConformingSampleProofTest(CreateReleaseExecutionTest):
    SAMPLES = SAMPLES


class RehearseTargetStepsExecutionConformingSampleProofTest(RehearseTargetStepsExecutionTest):
    SAMPLES = SAMPLES


class PublishExecutionConformingSampleProofTest(PublishExecutionTest):
    SAMPLES = SAMPLES


class ArduinoTestJobExecutionConformingSampleProofTest(ArduinoTestJobExecutionTest):
    SAMPLES = SAMPLES


class SampleBiteProofTest(_ExecutionCase):
    """The checks bite: each sample broken in one place fails the check that guards it."""

    SAMPLES = SAMPLES

    def _fails(self, case: type, method: str, broken: str):
        """Run ``case.method`` with :data:`SAMPLE_FULL` replaced by ``broken``; assert it fails."""
        proof = type("Broken", (case,), {"SAMPLES": {**SAMPLES, FULL: broken}})
        result = unittest.TestResult()
        proof(method).run(result)
        self.assertTrue(result.failures or result.errors, f"{case.__name__}.{method} passed")

    def test_a_test_job_with_an_if_bites(self):
        self._fails(RenderedTestJobsTest,
                    "test_no_test_job_has_if_or_needs_and_each_checks_out_full_history_first",
                    SAMPLE_FULL.replace("  test-python:\n", "  test-python:\n    if: always()\n"))

    def test_a_publish_job_not_needing_the_tests_bites(self):
        self._fails(RenderedWorkflowShapeTest, "test_every_other_job_needs_every_test_job",
                    SAMPLE_FULL.replace("  publish-pypi:\n    needs: [test-python]\n",
                                        "  publish-pypi:\n"))

    def test_a_check_step_without_the_npm_target_bites(self):
        self._fails(RenderedCreateReleaseTest,
                    "test_the_check_step_is_there_exactly_with_a_versioned_target",
                    SAMPLE_FULL.replace('check "$TAG" pypi:. npm:pkg', 'check "$TAG" pypi:.'))

    def test_targets_out_of_canonical_order_bite(self):
        pypi = SAMPLE_FULL.index(f"      - uses: {_UV}\n      - run: uv build\n      - uses: {_PP}\n"
                                 "        with:\n")
        npm = SAMPLE_FULL.index(f"      - uses: {_SN}\n        with:\n          node-version: \"22\"\n"
                                "      - name: npm new enough for the dry")
        assets = SAMPLE_FULL.index("      - name: Build the release assets\n")
        swapped = (SAMPLE_FULL[:pypi] + SAMPLE_FULL[npm:assets] + SAMPLE_FULL[pypi:npm]
                   + SAMPLE_FULL[assets:])
        self._fails(RenderedRehearseTest,
                    "test_each_targets_steps_follow_in_canonical_order_and_nothing_else", swapped)

    def test_a_header_naming_the_project_bites(self):
        self._fails(RenderedHeaderTest, "test_the_header_is_project_neutral",
                    SAMPLE_FULL.replace("# Every publish needs the tests.\n",
                                        "# Every publish needs the tests. See docs/research.\n"))

    def test_an_unpinned_action_bites(self):
        self._fails(ActionPinTableTest, "test_every_uses_line_is_pinned_from_the_table",
                    SAMPLE_FULL.replace(_SN, "actions/setup-node@v4", 1))

    def test_a_copy_that_misses_the_package_dir_bites(self):
        self._fails(RehearseTargetStepsExecutionTest,
                    "test_the_npm_copy_step_puts_the_root_changelog_into_the_package_dir",
                    SAMPLE_FULL.replace('        working-directory: pkg\n        run: cp "$GITHUB'
                                        '_WORKSPACE/CHANGELOG.md" .\n',
                                        '        run: cp "$GITHUB_WORKSPACE/CHANGELOG.md" .\n'))

    def test_an_empty_dist_assets_check_dropped_bites(self):
        cut = SAMPLE_FULL.index("      - name: The release assets are not empty\n")
        end = SAMPLE_FULL.index("\n  publish-pypi:")
        self._fails(RehearseTargetStepsExecutionTest, "test_a_build_leaving_dist_assets_empty_fails",
                    SAMPLE_FULL[:cut] + SAMPLE_FULL[end + 1:])


if __name__ == "__main__":
    unittest.main()
