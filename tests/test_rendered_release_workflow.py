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

CR-MDB-068 C5 RED (VERIFY F6/F7) adds the setup-wording classes: ``SetupWordingCheckerProofTest``
(:func:`npm_token_faults`, :func:`tag_admission_faults` and :func:`setup_items` proved both ways
on sample text), ``NpmSetupTaskTest`` (``init``'s npm setup task) and ``RenderedHeaderSetupTest``
(the rendered header's setup items).

CR-MDB-071 (§S1-§S4) extends the matrix with the target sets ``crates``, ``maven-central``,
``crates:a,maven-central:b`` and all five (:data:`FULL_TARGETS`, which :data:`SAMPLE_FULL` now
meets): the crates and maven-central rehearsal steps (``RenderedRehearseTest._consume``), the
``publish-crates`` and ``publish-maven-central`` jobs, their setup items, the crates.io auth
action's pin (``CratesAuthActionPinTest``), the bundle check run under ``bash -e`` on sample zips
(``MavenBundleCheckExecutionTest``), and ``init``'s crates task (``CratesSetupTaskTest``). The
first-publish reader takes the token (:func:`first_publish_token_faults`).

Stdlib only.
"""

import itertools
import os
import re
import shutil
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path

from modelb_axi import scaffold
from tests._helpers import (
    workflow_job,
    workflow_job_env,
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
from tests.test_bootstrap_shutdown_registry import normalise
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
from tests.test_workflow_scripts import cargo_package, pom

REPO_ROOT = Path(__file__).resolve().parent.parent

ALL_STACKS = ("python", "bun", "rust", "quarkus", "java", "arduino")
STACK_SETS = tuple((stack,) for stack in ALL_STACKS) + (ALL_STACKS,)
# MIGRATED at CR-MDB-071 (§S3): all five targets (was: ("pypi", "npm:pkg", "github-assets")),
# and the target sets gain crates, maven-central and both in sub-directories (was: none, pypi,
# npm:pkg, github-assets and the full set).
FULL_TARGETS = ("pypi", "npm:pkg", "crates", "maven-central", "github-assets")
#: CR-MDB-071 §S3 AC — crates and maven-central each in a sub-directory.
CRATES_MAVEN_DIRS = ("crates:a", "maven-central:b")
TARGET_SETS = ((), ("pypi",), ("npm:pkg",), ("crates",), ("maven-central",), CRATES_MAVEN_DIRS,
               ("github-assets",), FULL_TARGETS)
#: §S4 AC's matrix, plus a ``pypi`` sub-directory.
MATRIX = tuple(itertools.product(STACK_SETS, TARGET_SETS)) + ((("python",), ("pypi:py",)),)

#: The combination every single-combination class renders.
FULL = (("python",), FULL_TARGETS)
ALL_STACKS_NO_TARGET = (ALL_STACKS, ())

#: §S2 — every action a rendered workflow uses.
# MIGRATED at CR-MDB-071 (§S3): rust-lang/crates-io-auth-action joins (publish-crates).
ACTIONS = frozenset({"actions/checkout", "actions/setup-python", "astral-sh/setup-uv",
                     "pypa/gh-action-pypi-publish", "actions/setup-node", "oven-sh/setup-bun",
                     "actions/setup-java", "rust-lang/crates-io-auth-action"})
#: CR-MDB-071 §S3 — the crates.io auth action and its measured pin (a lightweight tag).
CRATES_AUTH = "rust-lang/crates-io-auth-action"
CRATES_AUTH_PIN = ("c6f97d42243bad5fab37ca0427f495c86d5b1a18", "v1.0.5")
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

#: CR-MDB-071 §S3 — the crates and maven-central steps pinned exactly.
CARGO_DRY_RUN = "cargo publish --dry-run --allow-dirty"
CARGO_PUBLISH = "cargo publish"
#: publish-crates: the job env naming the first-publish token, the auth step's if, the publish env.
CARGO_JOB_ENV = {"CARGO_FIRST_TOKEN": "${{ secrets.CARGO_REGISTRY_TOKEN }}"}
CARGO_AUTH_IF = "env.CARGO_FIRST_TOKEN == ''"
CARGO_PUBLISH_ENV = {
    "CARGO_REGISTRY_TOKEN": "${{ steps.auth.outputs.token || secrets.CARGO_REGISTRY_TOKEN }}"}
#: actions/setup-java's inputs: the rehearsal's (temurin 21 and the GPG key), the publish's (those
#: and the Central server credentials, by env-var name).
JAVA_GPG = {"distribution": "temurin", "java-version": "21",
            "gpg-private-key": "${{ secrets.MAVEN_GPG_PRIVATE_KEY }}",
            "gpg-passphrase-env-var": "MAVEN_GPG_PASSPHRASE"}
JAVA_CENTRAL = {**JAVA_GPG, "server-id": "central",
                "server-username-env-var": "MAVEN_CENTRAL_USERNAME",
                "server-password-env-var": "MAVEN_CENTRAL_PASSWORD"}
MAVEN_REHEARSE_ENV = {"MAVEN_GPG_PASSPHRASE": "${{ secrets.MAVEN_GPG_PASSPHRASE }}"}
#: The four MAVEN_* names, each from the repository secret of the same name.
MAVEN_SECRETS = ("MAVEN_CENTRAL_USERNAME", "MAVEN_CENTRAL_PASSWORD", "MAVEN_GPG_PRIVATE_KEY",
                 "MAVEN_GPG_PASSPHRASE")
MAVEN_PUBLISH_ENV = {name: f"${{{{ secrets.{name} }}}}" for name in MAVEN_SECRETS}


def maven_deploy(directory: str, flags: str) -> str:
    """The Maven deploy line, run from the repository root against ``<dir>/pom.xml``."""
    return f"./mvnw -B -ntp -f {directory}/pom.xml deploy -DskipTests {flags}"


MAVEN_REHEARSE_FLAGS = "-DskipUpload=true"
MAVEN_PUBLISH_FLAGS = "-DautoPublish=true -DwaitUntil=PUBLISHED"

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


#: The targets carrying a version source (CR-MDB-071 §S1 adds crates and maven-central).
VERSIONED_NAMES = ("pypi", "npm", "crates", "maven-central")


def versioned(targets) -> list[str]:
    """The ``<name>:<dir>`` arguments the renderer writes for ``stamp_version.py``."""
    # MIGRATED at CR-MDB-071 (§S1/§S3): crates and maven-central carry a version source too
    # (was: pypi and npm only).
    return [f"{name}:{directory}" for name, directory in map(parse_target, targets)
            if name in VERSIONED_NAMES]


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
#: CR-MDB-071 §S3 — an invented pin for the crates.io auth action (the sample's table only).
_CA = "rust-lang/crates-io-auth-action@" + "a" * 40 + " # v1.0.0"


def _pin(uses: str) -> tuple[str, tuple[str, str]]:
    match = _USES.match(f"uses: {uses}")
    if match is None:
        raise AssertionError(f"fixture pin {uses!r}")
    return match.group(1), (match.group(2), match.group(3))


#: The sample proofs' pin table: Model B's pins today, and invented ones for the two new actions.
SAMPLE_PINS = dict(map(_pin, (_CO, _SP, _UV, _PP, _SN, _SB, _SJ, _CA)))

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
# - crates: environment `crates`, which admits the version tags; the
#   repository secret CARGO_REGISTRY_TOKEN for the first publish, then
#   add the crates.io trusted publisher (this repository, release.yml,
#   environment `crates`) and delete the token;
# - maven-central: environment `maven-central`, which admits the version
#   tags; the namespace verified on the Central Portal; the repository
#   secrets MAVEN_CENTRAL_USERNAME and MAVEN_CENTRAL_PASSWORD (a Portal
#   user token), MAVEN_GPG_PRIVATE_KEY and MAVEN_GPG_PASSPHRASE; the POM
#   carrying central-publishing-maven-plugin with
#   <extensions>true</extensions>, the sources and javadoc jars, and
#   maven-gpg-plugin 3.2.0 or newer; one mvnw at the repository root;
# - github-assets: an executable .github/scripts/build-assets.
"""

#: CR-MDB-071 §S3 — a conforming bundle check (``unzip -Z1`` lists the bundle): every
#: ``.jar``/``.pom`` has its ``.asc``; a ``-sources.jar`` and a ``-javadoc.jar`` are there; each
#: failure is an ``::error::`` line naming the bundle and what is missing.
# MIGRATED at CR-MDB-071 (§S3, VERIFY F3): the entries are read line by line (was: a `for` over
# an unquoted `$(...)`, which word-splits and glob-expands each name), and a missing
# `-sources.jar` or `-javadoc.jar` is an `::error::` line (was: a silent `grep -q`).
_BUNDLE_CHECK = """\
      - name: The Central bundle holds the signatures, sources and javadoc
        run: |
          bundle={dir}/target/central-publishing/central-bundle.zip
          files=$(unzip -Z1 "$bundle")
          while IFS= read -r f; do
            case "$f" in
              *.jar|*.pom)
                if ! printf '%s\\n' "$files" | grep -qxF -- "$f.asc"; then
                  echo "::error::$bundle: $f has no .asc signature"
                  exit 1
                fi
                ;;
            esac
          done <<< "$files"
          if ! printf '%s\\n' "$files" | grep -q -- '-sources\\.jar$'; then
            echo "::error::$bundle: no -sources.jar"
            exit 1
          fi
          if ! printf '%s\\n' "$files" | grep -q -- '-javadoc\\.jar$'; then
            echo "::error::$bundle: no -javadoc.jar"
            exit 1
          fi
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

#: CR-MDB-071 §S3 — the sample's crates and maven-central rehearsal steps (both at the root).
_REHEARSE_CRATES_MAVEN = f"""\
      - name: Dry-run the crate publish
        run: cargo publish --dry-run --allow-dirty
      - uses: {_SJ}
        with:
          distribution: temurin
          java-version: "21"
          gpg-private-key: ${{{{ secrets.MAVEN_GPG_PRIVATE_KEY }}}}
          gpg-passphrase-env-var: MAVEN_GPG_PASSPHRASE
      - name: Bundle and sign for Maven Central, uploading nothing
        env:
          MAVEN_GPG_PASSPHRASE: ${{{{ secrets.MAVEN_GPG_PASSPHRASE }}}}
        run: ./mvnw -B -ntp -f ./pom.xml deploy -DskipTests -DskipUpload=true
""" + _BUNDLE_CHECK.format(dir=".")

#: CR-MDB-071 §S3 — the sample's publish-crates and publish-maven-central jobs.
_PUBLISH_CRATES_MAVEN = f"""\
  publish-crates:
    needs: [test-python]
    if: github.event_name == 'release'
    runs-on: ubuntu-latest
    environment: crates
    permissions:
      contents: read
      id-token: write
    env:
      CARGO_FIRST_TOKEN: ${{{{ secrets.CARGO_REGISTRY_TOKEN }}}}
    steps:
      - uses: {_CO}
        with:
          fetch-depth: 0
{_GUARD}      - uses: {_CA}
        id: auth
        if: env.CARGO_FIRST_TOKEN == ''
      - name: Publish
        env:
          CARGO_REGISTRY_TOKEN: ${{{{ steps.auth.outputs.token || secrets.CARGO_REGISTRY_TOKEN }}}}
        run: cargo publish

  publish-maven-central:
    needs: [test-python]
    if: github.event_name == 'release'
    runs-on: ubuntu-latest
    environment: maven-central
    permissions:
      contents: read
    steps:
      - uses: {_CO}
        with:
          fetch-depth: 0
{_GUARD}      - uses: {_SJ}
        with:
          distribution: temurin
          java-version: "21"
          server-id: central
          server-username-env-var: MAVEN_CENTRAL_USERNAME
          server-password-env-var: MAVEN_CENTRAL_PASSWORD
          gpg-private-key: ${{{{ secrets.MAVEN_GPG_PRIVATE_KEY }}}}
          gpg-passphrase-env-var: MAVEN_GPG_PASSPHRASE
      - name: Publish
        env:
          MAVEN_CENTRAL_USERNAME: ${{{{ secrets.MAVEN_CENTRAL_USERNAME }}}}
          MAVEN_CENTRAL_PASSWORD: ${{{{ secrets.MAVEN_CENTRAL_PASSWORD }}}}
          MAVEN_GPG_PRIVATE_KEY: ${{{{ secrets.MAVEN_GPG_PRIVATE_KEY }}}}
          MAVEN_GPG_PASSPHRASE: ${{{{ secrets.MAVEN_GPG_PASSPHRASE }}}}
        run: ./mvnw -B -ntp -f ./pom.xml deploy -DskipTests -DautoPublish=true -DwaitUntil=PUBLISHED
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
        run: python3 .github/scripts/stamp_version.py check "$TAG" pypi:. npm:pkg crates:. maven-central:.
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
{_REHEARSE_CRATES_MAVEN}      - name: Build the release assets
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

{_PUBLISH_CRATES_MAVEN}
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
            # MIGRATED at CR-MDB-071 (§S3): crates and maven-central steps (the last branch was
            # every other name; now github-assets alone, and an unknown name fails).
            elif name == "crates":
                dry = steps[at]
                self.assertEqual((dry["uses"], run_lines([dry]), dry["working-directory"],
                                  dry["env"]), (None, [CARGO_DRY_RUN], where, {}),
                                 f"CR-MDB-071 §S3: the crate's dry-run publish in {directory}")
                at += 1
            elif name == "maven-central":
                setup, deploy, check = steps[at:at + 3]
                self.assertEqual((action(setup), setup["with"]), ("actions/setup-java", JAVA_GPG),
                                 "CR-MDB-071 §S3: temurin 21 with the GPG key")
                self.assertEqual((deploy["uses"], run_lines([deploy]), deploy["working-directory"],
                                  deploy["env"]),
                                 (None, [maven_deploy(directory, MAVEN_REHEARSE_FLAGS)], None,
                                  MAVEN_REHEARSE_ENV),
                                 "CR-MDB-071 §S3: deploy from the root, uploading nothing")
                self.assertEqual((check["uses"], check["working-directory"]), (None, None),
                                 "CR-MDB-071 §S3: the bundle check runs from the root")
                self.assertTrue(run_lines([check]), "CR-MDB-071 §S3: the bundle check runs")
                at += 3
            elif name == "github-assets":
                rest = steps[at:]
                self.assertTrue(rest and all(step["uses"] is None for step in rest), rest)
                lines = run_lines(rest)
                check = [i for i, line in enumerate(lines) if f"test -x {BUILD_ASSETS}" in line]
                self.assertEqual(len(check), 1, lines)
                self.assertIn(BUILD_ASSETS, lines[check[0] + 1:])
                self.assertTrue(any("dist-assets" in line for line in
                                    lines[lines.index(BUILD_ASSETS):]), lines)
                at = len(steps)
            else:
                self.fail(f"no rehearsal model for the target {target!r}")
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

    def test_publish_crates(self):
        # CR-MDB-071 §S3: environment crates, OIDC, the first-publish token in the job env, the auth
        # step only without it, then `cargo publish` in the crate's directory.
        for stacks, targets, directory in target_dirs(self, self.combos(), "crates"):
            with self.subTest(stacks=stacks, targets=targets):
                job = self.job(stacks, targets, "publish-crates")
                where = None if directory == "." else directory
                defaults = workflow_job_working_directory(job)
                keys = ["needs", "if", "runs-on", "environment", "permissions", "env", "steps"]
                rest = self._head(job, keys + (["defaults"] if defaults is not None else []),
                                  {"contents": "read", "id-token": "write"}, "crates")
                self.assertEqual(workflow_job_env(job), CARGO_JOB_ENV)
                self.assertEqual(len(rest), 2, [s["run"] or s["uses"] for s in rest])
                auth, publish = rest
                self.assertEqual((action(auth), auth["id"], auth["if"], auth["with"], auth["run"]),
                                 (CRATES_AUTH, "auth", CARGO_AUTH_IF, {}, []))
                self.assertEqual((publish["uses"], run_lines([publish]), publish["env"]),
                                 (None, [CARGO_PUBLISH], CARGO_PUBLISH_ENV))
                self.assertEqual(publish["working-directory"] or defaults, where,
                                 "§S3: cargo publish runs in the crate's directory")

    def test_publish_maven_central(self):
        # CR-MDB-071 §S3: environment maven-central, contents read only; setup-java with the
        # Central server credentials and the GPG inputs; deploy from the root with the four MAVEN_*.
        for stacks, targets, directory in target_dirs(self, self.combos(), "maven-central"):
            with self.subTest(stacks=stacks, targets=targets):
                job = self.job(stacks, targets, "publish-maven-central")
                rest = self._head(job, ["needs", "if", "runs-on", "environment", "permissions",
                                        "steps"], {"contents": "read"}, "maven-central")
                self.assertIsNone(workflow_job_working_directory(job))
                self.assertEqual(len(rest), 2, [s["run"] or s["uses"] for s in rest])
                setup, deploy = rest
                self.assertEqual((action(setup), setup["with"]), ("actions/setup-java", JAVA_CENTRAL))
                self.assertEqual((deploy["uses"], run_lines([deploy]), deploy["working-directory"],
                                  deploy["env"]),
                                 (None, [maven_deploy(directory, MAVEN_PUBLISH_FLAGS)], None,
                                  MAVEN_PUBLISH_ENV))

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

    def test_the_setup_items_are_release_pat_then_each_target_in_canonical_order(self):
        # CR-MDB-071 §S3: one item per rendered target, in the targets' canonical order.
        for stacks, targets, text in self.each():
            names = [parse_target(t)[0] for t in targets]
            with self.subTest(stacks=stacks, targets=targets):
                self.assertEqual(list(setup_items(text)),
                                 ["repository secret RELEASE_PAT", *names])

    def test_the_crates_setup_item(self):
        # CR-MDB-071 §S3: the environment crates admitting the version tags; the repository
        # secret CARGO_REGISTRY_TOKEN for the first publish, then the crates.io trusted publisher
        # (repository, release.yml, environment crates) added and the token deleted.
        for stacks, targets, text in self.each():
            names = {parse_target(t)[0] for t in targets}
            with self.subTest(stacks=stacks, targets=targets):
                if "crates" not in names:
                    self.assertNotIn("cargo_registry_token", header_text(text),
                                     "§S3: only the rendered targets")
                    continue
                item = setup_items(text).get("crates", "")
                self.assertEqual(tag_admission_faults(item, "crates"), [], item)
                self.assertEqual(first_publish_token_faults(item, CARGO_SECRET_NAME), [], item)
                for needle in ("crates.io", "release.yml"):
                    self.assertIn(needle, normalise(item), needle)

    def test_the_maven_central_setup_item(self):
        # CR-MDB-071 §S3: the environment maven-central admitting the version tags; the verified
        # namespace; the four repository secrets; the POM's plugins and jars; one root mvnw.
        for stacks, targets, text in self.each():
            names = {parse_target(t)[0] for t in targets}
            with self.subTest(stacks=stacks, targets=targets):
                if "maven-central" not in names:
                    self.assertNotIn("maven_central_username", header_text(text),
                                     "§S3: only the rendered targets")
                    continue
                item = setup_items(text).get("maven-central", "")
                self.assertEqual(tag_admission_faults(item, "maven-central"), [], item)
                flat = normalise(item)
                for needle in MAVEN_SETUP_NEEDLES:
                    self.assertIn(needle, flat, needle)


class CratesAuthActionPinTest(unittest.TestCase):
    """CR-MDB-071 §S3 — ``ACTION_PINS`` gains the crates.io auth action at its measured pin."""

    def test_the_crates_io_auth_action_is_pinned_to_v1_0_5(self):
        self.assertEqual(workflows_module().ACTION_PINS.get(CRATES_AUTH), CRATES_AUTH_PIN)


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
        # MIGRATED at CR-MDB-071 (§S3): the github-assets steps start at the build step (was: every
        # step after the npm dry run, which the crates and maven-central steps now follow).
        job, steps = self._job_and_steps()
        start = next(i for i, step in enumerate(steps)
                     if any(f"test -x {BUILD_ASSETS}" in line for line in step["run"]))
        repo = self.repo({})
        if build is not None:
            _executable(repo, BUILD_ASSETS, build)
        return self.run_steps(job, steps[start:], repo, self.env(repo))

    def test_built_assets_pass(self):
        result = self._assets("#!/bin/sh\nmkdir -p dist-assets\necho fw > dist-assets/fw.bin\n")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_no_build_script_fails(self):
        self.assertNotEqual(self._assets(None).returncode, 0)

    def test_a_build_leaving_dist_assets_empty_fails(self):
        self.assertNotEqual(self._assets("#!/bin/sh\nmkdir -p dist-assets\n").returncode, 0)

    def test_a_failing_build_fails(self):
        self.assertNotEqual(self._assets("#!/bin/sh\nexit 3\n").returncode, 0)


#: CR-MDB-071 §S3 — the Central bundle the maven-central rehearsal builds, under ``<dir>``.
CENTRAL_BUNDLE = "target/central-publishing/central-bundle.zip"
_COORDINATES = "org/example/fixture/1.2.3/fixture-1.2.3"
SOURCES_JAR = f"{_COORDINATES}-sources.jar"
JAVADOC_JAR = f"{_COORDINATES}-javadoc.jar"
#: The bundle's artifacts: each ships with its ``.asc`` and its checksums (not artifacts).
BUNDLE_ARTIFACTS = (f"{_COORDINATES}.pom", f"{_COORDINATES}.jar", SOURCES_JAR, JAVADOC_JAR)


def bundle_entries(drop: tuple[str, ...] = (), without: str | None = None) -> list[str]:
    """A bundle's entry names: each artifact with its ``.asc``, ``.md5`` and ``.sha1``; minus the
    names in ``drop`` and every entry of the artifact ``without``."""
    return [artifact + suffix for artifact in BUNDLE_ARTIFACTS if artifact != without
            for suffix in ("", ".asc", ".md5", ".sha1") if artifact + suffix not in drop]


#: CR-MDB-071 §S3 (VERIFY F3) — artifacts whose names a shell would split or expand: one holding a
#: space, one holding a glob character. :data:`GLOB_DECOY` is a file in the working directory that
#: the glob name matches, so a loop that glob-expands names checks the decoy instead.
SPACED_ARTIFACT = f"{_COORDINATES} extra.jar"
GLOB_ARTIFACT = f"{_COORDINATES}-*.jar"
GLOB_DECOY = f"{_COORDINATES}-shaded.jar"
ODD_ARTIFACTS = (SPACED_ARTIFACT, GLOB_ARTIFACT)


def error_lines(result: subprocess.CompletedProcess) -> list[str]:
    """The ``::error::`` workflow-command lines a step printed."""
    return [line for line in (result.stdout + result.stderr).splitlines()
            if line.startswith("::error::")]


def write_central_bundle(path: Path, entries: list[str]) -> None:
    """A zip at ``path`` holding ``entries`` (each a line of fixture text)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as bundle:
        for name in entries:
            bundle.writestr(name, f"fixture {name}\n")


class MavenBundleCheckExecutionTest(_ExecutionCase):
    """CR-MDB-071 §S3 — the maven-central rehearsal's bundle check, run under ``bash -e`` from
    the repository root on sample ``<dir>/target/central-publishing/central-bundle.zip`` files:
    complete passes; an artifact without its ``.asc``, no ``-sources.jar``, no ``-javadoc.jar`` or
    no bundle fails. One case per ``maven-central`` dir the combinations render."""

    def _checks(self):
        """``(dir, rehearse job, bundle-check step)`` per rendered maven-central dir: the check is
        the step after the deploy that uploads nothing."""
        cases: dict[str, tuple] = {}
        for stacks, targets, directory in target_dirs(self, self.combos(), "maven-central"):
            cases.setdefault(directory, (stacks, targets))
        for directory, (stacks, targets) in cases.items():
            job = self.job(stacks, targets, "rehearse")
            steps = workflow_steps(job)
            deploy = next(i for i, step in enumerate(steps)
                          if any(MAVEN_REHEARSE_FLAGS in line for line in step["run"]))
            yield directory, job, steps[deploy + 1]

    def _run(self, directory: str, job, check, entries,
             files: dict[str, str] | None = None) -> subprocess.CompletedProcess:
        repo = self.repo(files or {})
        if entries is not None:
            write_central_bundle(repo / directory / CENTRAL_BUNDLE, entries)
        return self.run_steps(job, [check], repo, self.env(repo))

    def assert_error(self, result: subprocess.CompletedProcess, directory: str, *named: str):
        """VERIFY F3: the step fails with exactly one ``::error::`` line, naming the bundle and
        each of ``named``."""
        output = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0, output)
        errors = error_lines(result)
        self.assertEqual(len(errors), 1, f"one ::error:: line; got {output!r}")
        for name in (f"{directory}/{CENTRAL_BUNDLE}", *named):
            self.assertIn(name, errors[0], f"the ::error:: line names {name!r}")

    @staticmethod
    def odd_entries(odd: str, signed: bool) -> list[str]:
        """A complete bundle plus the artifact ``odd``, with its ``.asc`` when ``signed``."""
        return bundle_entries() + [odd] + ([odd + ".asc"] if signed else [])

    def test_a_complete_bundle_passes(self):
        for directory, job, check in self._checks():
            with self.subTest(dir=directory):
                result = self._run(directory, job, check, bundle_entries())
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(error_lines(result), [])

    # MIGRATED at CR-MDB-071 (§S3, VERIFY F3): the failure is its ::error:: line naming the bundle
    # and the unsigned artifact (was: any non-zero exit, which a missing tool also gives).
    def test_an_artifact_without_its_signature_fails(self):
        for directory, job, check in self._checks():
            for artifact in BUNDLE_ARTIFACTS:
                with self.subTest(dir=directory, unsigned=artifact):
                    result = self._run(directory, job, check,
                                       bundle_entries(drop=(artifact + ".asc",)))
                    self.assert_error(result, directory, artifact, ".asc")

    # MIGRATED at CR-MDB-071 (§S3, VERIFY F3): the failure is its ::error:: line naming the bundle
    # and the missing jar (was: any non-zero exit, from a silent `grep -q`).
    def test_a_bundle_without_sources_or_javadoc_fails(self):
        for directory, job, check in self._checks():
            for jar, kind in ((SOURCES_JAR, "-sources.jar"), (JAVADOC_JAR, "-javadoc.jar")):
                with self.subTest(dir=directory, missing=jar):
                    result = self._run(directory, job, check, bundle_entries(without=jar))
                    self.assert_error(result, directory, kind)

    # MIGRATED at CR-MDB-071 (§S3, VERIFY F3): the failure names the bundle (was: any non-zero
    # exit, which a missing `unzip` also gives).
    def test_no_bundle_fails(self):
        for directory, job, check in self._checks():
            with self.subTest(dir=directory):
                result = self._run(directory, job, check, None)
                output = result.stdout + result.stderr
                self.assertNotEqual(result.returncode, 0, output)
                self.assertIn(f"{directory}/{CENTRAL_BUNDLE}", output)

    def test_names_holding_a_space_or_a_glob_character_are_checked_whole(self):
        # VERIFY F3: each entry name is one artifact — never word-split, never glob-expanded
        # (the decoy on disk is what a glob-expanding loop would check instead).
        for directory, job, check in self._checks():
            for odd in ODD_ARTIFACTS:
                with self.subTest(dir=directory, signed=odd):
                    result = self._run(directory, job, check, self.odd_entries(odd, True),
                                       {GLOB_DECOY: "decoy\n"})
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    self.assertEqual(error_lines(result), [])

    def test_an_unsigned_name_holding_a_space_or_a_glob_character_fails_naming_it(self):
        for directory, job, check in self._checks():
            for odd in ODD_ARTIFACTS:
                with self.subTest(dir=directory, unsigned=odd):
                    result = self._run(directory, job, check, self.odd_entries(odd, False),
                                       {GLOB_DECOY: "decoy\n"})
                    self.assert_error(result, directory, odd, ".asc")


class PublishExecutionTest(_ExecutionCase):
    """§S4 — each publish job's guard, ``publish-npm``'s copy, and ``publish-github-assets``'s
    build and upload, under ``bash -e``."""

    # MIGRATED at CR-MDB-071 (§S3): publish-crates and publish-maven-central carry the guard
    # second too (was: the pypi, npm and github-assets jobs).
    PUBLISH_JOBS = ("publish-pypi", "publish-npm", "publish-crates", "publish-maven-central",
                    "publish-github-assets")

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
    # MIGRATED at CR-MDB-071 (§S3): FULL renders crates:. and maven-central:. too, so the
    # tree carries a root Cargo.toml and pom.xml at the version (was: pyproject.toml and
    # pkg/package.json only).
    return {"pyproject.toml": ('[project]\nname = "fixture"\n'
                               f'version = "{version}"\n'),
            "pkg/package.json": ('{\n  "name": "fixture",\n'
                                 f'  "version": "{version}"\n' + "}\n"),
            "Cargo.toml": cargo_package(f'version = "{version}"'),
            "pom.xml": pom(version)}


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
        # CR-MDB-071 §S2/§S3: crates and maven-central are passed to the stamp and left unchanged.
        self.assertEqual((repo / "Cargo.toml").read_text(encoding="utf-8"),
                         _version_sources("1.2.3")["Cargo.toml"])
        self.assertEqual((repo / "pom.xml").read_text(encoding="utf-8"),
                         _version_sources("1.2.3")["pom.xml"])

    def test_a_crates_or_maven_version_off_the_ref_fails_the_stamp_writing_nothing(self):
        # CR-MDB-071 §S2: the stamp refuses a crates or Maven version other than the ref's X.Y.Z.
        for source, off in (("Cargo.toml", cargo_package('version = "1.2.2"')),
                            ("pom.xml", pom("1.2.3-SNAPSHOT"))):
            with self.subTest(source=source):
                sources = dict(_version_sources("1.2.3"), **{source: off})
                result, repo = self._run(FULL_TARGETS, "release/1.2.3", CHANGELOG_GOOD, sources)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(source, result.stderr)
                self.assertEqual((repo / "pyproject.toml").read_text(encoding="utf-8"),
                                 sources["pyproject.toml"], "nothing is stamped")

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


class MavenBundleCheckExecutionConformingSampleProofTest(MavenBundleCheckExecutionTest):
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

    # MIGRATED at CR-MDB-071 (§S3): the full check line names crates and maven-central too.
    def test_a_check_step_without_the_npm_target_bites(self):
        self._fails(RenderedCreateReleaseTest,
                    "test_the_check_step_is_there_exactly_with_a_versioned_target",
                    SAMPLE_FULL.replace('check "$TAG" pypi:. npm:pkg crates:. maven-central:.',
                                        'check "$TAG" pypi:. crates:. maven-central:.'))

    def test_a_check_step_without_the_maven_target_bites(self):
        self._fails(RenderedCreateReleaseTest,
                    "test_the_check_step_is_there_exactly_with_a_versioned_target",
                    SAMPLE_FULL.replace(' crates:. maven-central:.\n', ' crates:.\n'))

    def test_an_auth_step_running_always_bites(self):
        self._fails(RenderedPublishJobsTest, "test_publish_crates",
                    SAMPLE_FULL.replace("        if: env.CARGO_FIRST_TOKEN == ''\n", ""))

    def test_a_maven_publish_without_its_gpg_inputs_bites(self):
        self._fails(RenderedPublishJobsTest, "test_publish_maven_central",
                    SAMPLE_FULL.replace("          server-password-env-var: MAVEN_CENTRAL_PASSWORD\n"
                                        "          gpg-private-key",
                                        "          server-password-env-var: MAVEN_CENTRAL_PASSWORD\n"
                                        "          no-gpg-private-key"))

    def test_a_maven_rehearsal_that_uploads_bites(self):
        self._fails(RenderedRehearseTest,
                    "test_each_targets_steps_follow_in_canonical_order_and_nothing_else",
                    SAMPLE_FULL.replace(" -DskipUpload=true\n", "\n"))

    # MIGRATED at CR-MDB-071 (§S3, VERIFY F3): the javadoc check is an if-block (was: a line).
    def test_a_bundle_check_without_the_javadoc_check_bites(self):
        self._fails(MavenBundleCheckExecutionTest, "test_a_bundle_without_sources_or_javadoc_fails",
                    SAMPLE_FULL.replace(
                        "          if ! printf '%s\\n' \"$files\" | grep -q -- '-javadoc\\.jar$'; then\n"
                        "            echo \"::error::$bundle: no -javadoc.jar\"\n"
                        "            exit 1\n"
                        "          fi\n", ""))

    # MIGRATED at CR-MDB-071 (§S3, VERIFY F3): the signature check sits in the read loop's case.
    def test_a_bundle_check_ignoring_signatures_bites(self):
        self._fails(MavenBundleCheckExecutionTest, "test_an_artifact_without_its_signature_fails",
                    SAMPLE_FULL.replace("                  exit 1\n                fi\n                ;;\n",
                                        "                fi\n                ;;\n"))

    def test_a_silent_sources_check_bites(self):
        # VERIFY F3: a bare `grep -q` fails the step with no ::error:: line.
        self._fails(MavenBundleCheckExecutionTest, "test_a_bundle_without_sources_or_javadoc_fails",
                    SAMPLE_FULL.replace(
                        "          if ! printf '%s\\n' \"$files\" | grep -q -- '-sources\\.jar$'; then\n"
                        "            echo \"::error::$bundle: no -sources.jar\"\n"
                        "            exit 1\n"
                        "          fi\n",
                        "          printf '%s\\n' \"$files\" | grep -q -- '-sources\\.jar$'\n"))

    def test_a_word_splitting_signature_loop_bites(self):
        # VERIFY F3: a `for` over an unquoted `$(...)` splits the spaced name and expands the glob.
        loop = SAMPLE_FULL.index("          while IFS= read -r f; do\n")
        end = SAMPLE_FULL.index("          done <<< \"$files\"\n") + len("          done <<< \"$files\"\n")
        split = ("          for f in $(printf '%s\\n' \"$files\" | grep -E '\\.(jar|pom)$'); do\n"
                 "            if ! printf '%s\\n' \"$files\" | grep -qxF \"$f.asc\"; then\n"
                 "              echo \"::error::$bundle: $f has no .asc signature\"\n"
                 "              exit 1\n"
                 "            fi\n"
                 "          done\n")
        self._fails(MavenBundleCheckExecutionTest,
                    "test_names_holding_a_space_or_a_glob_character_are_checked_whole",
                    SAMPLE_FULL[:loop] + split + SAMPLE_FULL[end:])

    def test_a_crates_setup_item_without_the_order_bites(self):
        self._fails(RenderedHeaderTest, "test_the_crates_setup_item",
                    SAMPLE_FULL.replace("environment `crates`) and delete the token;",
                                        "environment `crates`);"))

    def test_a_maven_setup_item_without_the_gpg_plugin_bites(self):
        self._fails(RenderedHeaderTest, "test_the_maven_central_setup_item",
                    SAMPLE_FULL.replace("maven-gpg-plugin 3.2.0 or newer", "a signing plugin"))

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


# ------------------------------------------------------------------ the setup wording ----
# CR-MDB-068 C5 RED (VERIFY F6/F7): NPM_TOKEN is a repository secret, given in order (the
# token for the first publish, then the trusted publisher added and the token deleted) by
# init's npm setup task and the rendered header's npm setup item; the header's pypi and npm
# setup items say their environment admits the version tags, because the release event's
# ref is the tag. (The git-workflow skill's targets table: tests.test_install_guide.)

#: F6 - each fault :func:`npm_token_faults` reports.
NO_NPM_TOKEN = " ".join(("names", "no", 'NPM_TOKEN'))
NOT_A_REPOSITORY_SECRET = " ".join(("does not call", 'NPM_TOKEN', "a repository", "secret"))
AN_ENVIRONMENT_SECRET = " ".join(("calls", 'NPM_TOKEN', "an environment", "secret"))
NO_ORDER = ("does not give the order: the token for the first publish, then the trusted "
            "publisher added and the token deleted")

_REPOSITORY_SECRET = re.compile(r"\brepository secrets?\b")
_FIRST_PUBLISH = re.compile(r"\bfirst publish\b")
_TRUSTED_PUBLISHER = re.compile(r"\btrusted publishers?\b")
_DELETED = re.compile(r"\bdelet(?:e|es|ed|ing)\b")
#: CR-MDB-071 §S3/§S4 — the crates first-publish token.
CARGO_SECRET_NAME = "_".join(("CARGO", "REGISTRY", "TOKEN"))


def first_publish_token_faults(text: str, token: str) -> list[str]:
    """F6: the faults of ``text`` (a setup task or setup item), normalised: it names ``token``,
    calls it a repository secret and never an environment secret, and says, in this order, the
    first publish, the trusted publisher (added) and the token deleted."""
    # MIGRATED at CR-MDB-071 (§S3/§S4): the reader takes the token, so the crates item and
    # task are read for CARGO_REGISTRY_TOKEN as npm's are for NPM_TOKEN (was npm_token_faults,
    # NPM_TOKEN only; npm_token_faults now delegates here).
    flat = normalise(text)
    name = re.escape(token.lower())
    if not re.search(rf"(?<![\w-]){name}(?![\w-])", flat):
        return [" ".join(("names", "no", token))]
    out = []
    if not _REPOSITORY_SECRET.search(flat):
        out.append(" ".join(("does not call", token, "a repository", "secret")))
    if re.search(rf"\benvironment secrets?\b|\benvironment\b[^.;]{{0,60}}\bwith the {name}\b",
                 flat):
        out.append(" ".join(("calls", token, "an environment", "secret")))
    first = _FIRST_PUBLISH.search(flat)
    added = _TRUSTED_PUBLISHER.search(flat, first.end()) if first else None
    if (_DELETED.search(flat, added.end()) if added else None) is None:
        out.append(NO_ORDER)
    return out


def npm_token_faults(text: str) -> list[str]:
    """F6: :func:`first_publish_token_faults` for ``NPM_TOKEN``."""
    return first_publish_token_faults(text, "NPM_TOKEN")


#: CR-MDB-071 §S3 — what the maven-central setup item names (normalised: lower-cased,
#: backticks dropped).
MAVEN_SETUP_NEEDLES = (
    "namespace", "central portal", "repository secret", "maven_central_username",
    "maven_central_password", "user token", "maven_gpg_private_key", "maven_gpg_passphrase",
    "central-publishing-maven-plugin", "<extensions>true</extensions>", "sources", "javadoc",
    "maven-gpg-plugin", "3.2.0", "mvnw", "repository root",
)


#: F7 - the release event's ref is the tag: why the publish environments admit the tags.
TAG_REF_REASON = re.compile(r"\brelease event'?s ref is the (?:version )?tag\b")
_ADMITS = r"(?:admits (?:the )?version tags|carries no branch rule|has no branch rule)"


def tag_admission_faults(item: str, environment: str) -> list[str]:
    """F7: ``the <environment> environment admits the version tags`` (or ``carries no branch
    rule``) in one clause (no ``;``) of the normalised setup ``item``; ``environment
    <environment>`` naming it works too. ``testpypi`` is never ``pypi``."""
    flat = normalise(item)
    env = re.escape(environment)
    pattern = (rf"(?<![\w.-]){env} environment\b[^;]*?\b{_ADMITS}"
               rf"|\benvironment {env}(?![\w.-])[^;]*?\b{_ADMITS}")
    if re.search(pattern, flat):
        return []
    return [f"the {environment} setup item does not say the {environment} environment admits "
            "the version tags"]


def setup_items(text: str) -> dict[str, str]:
    """The rendered header's one-time setup items, keyed by the text before each item's first
    ``:`` (``pypi``, ``npm``, ...): every ``# - `` line after ``# One-time setup:`` with its
    ``#   `` continuation lines, up to the first line that is not a comment. Raw text, joined."""
    items: dict[str, list[str]] = {}
    current: list[str] | None = None
    in_setup = False
    for line in text.splitlines():
        if not line.startswith("#"):
            if in_setup:
                break
            continue
        body = line[1:].strip()
        if not in_setup:
            in_setup = body.lower().startswith("one-time setup")
            continue
        if body.startswith("- "):
            current = items.setdefault(body[2:].split(":", 1)[0].strip(), [])
            current.append(body[2:])
        elif current is not None and body:
            current.append(body)
    return {key: " ".join(lines) for key, lines in items.items()}


def setup_text(text: str) -> str:
    """Every setup item of ``text``, joined: where :data:`TAG_REF_REASON` is looked for."""
    return " ".join(setup_items(text).values())


#: Conforming samples: the wording F6/F7 settle, as a renderer or ``init`` may give it.
SAMPLE_NPM_TASK = ("Create the `npm` environment in the repository settings and add the "
                   "`NPM_TOKEN` repository secret for the first publish; then add `release.yml` "
                   "as the package's trusted publisher on npm (environment `npm`) and delete the "
                   "token")
SAMPLE_SETUP_HEADER = """\
# One-time setup:
# - repository secret RELEASE_PAT: fine-grained, this repository only,
#   Contents read/write;
# - pypi: environments `pypi` and `testpypi`; the `pypi` environment
#   admits the version tags, because the release event's ref is the tag;
#   the `testpypi` environment admits the `release/**` and `hotfix/**`
#   branches and carries no required reviewers; pending trusted
#   publishers on pypi.org and test.pypi.org for this workflow;
# - npm: environment `npm`, which admits the version tags; the
#   repository secret NPM_TOKEN for the first publish, then add the npm
#   trusted publisher and delete the token;
# - github-assets: an executable .github/scripts/build-assets.

name: release
"""


class SetupWordingCheckerProofTest(unittest.TestCase):
    """The three readers proved both ways on sample text."""

    def test_the_sample_task_and_header_pass(self):
        self.assertEqual(npm_token_faults(SAMPLE_NPM_TASK), [])
        items = setup_items(SAMPLE_SETUP_HEADER)
        self.assertEqual(list(items), ["repository secret RELEASE_PAT", "pypi", "npm",
                                       "github-assets"])
        self.assertEqual(npm_token_faults(items["npm"]), [])
        self.assertEqual(tag_admission_faults(items["pypi"], "pypi"), [])
        self.assertEqual(tag_admission_faults(items["npm"], "npm"), [])
        self.assertRegex(normalise(setup_text(SAMPLE_SETUP_HEADER)), TAG_REF_REASON)

    def test_npm_token_faults_bite_on_todays_wording(self):
        today_task = ("Create the `npm` environment in the repository settings with the "
                      "`NPM_TOKEN` secret, and add `release.yml` as the package's trusted "
                      "publisher on npm (environment `npm`)")
        self.assertEqual(npm_token_faults(today_task),
                         [NOT_A_REPOSITORY_SECRET, AN_ENVIRONMENT_SECRET, NO_ORDER])
        today_item = ("npm: environment `npm`; the NPM_TOKEN secret for the first publish, "
                      "deleted once the npm trusted publisher exists;")
        self.assertEqual(npm_token_faults(today_item), [NOT_A_REPOSITORY_SECRET, NO_ORDER],
                         "deleted before the publisher is added is the wrong order")

    def test_npm_token_faults_bite_once_per_defect(self):
        good = SAMPLE_NPM_TASK
        cases = (
            ("`NPM_TOKEN` repository secret", "`NPM_TOKEN` secret", [NOT_A_REPOSITORY_SECRET]),
            ("repository secret", "environment secret",
             [NOT_A_REPOSITORY_SECRET, AN_ENVIRONMENT_SECRET]),
            (" for the first publish", "", [NO_ORDER]),
            (" and delete the token", "", [NO_ORDER]),
            ("`NPM_TOKEN`", "a token", [NO_NPM_TOKEN]),
        )
        for old, new, faults in cases:
            with self.subTest(old=old, new=new):
                self.assertEqual(good.count(old), 1, old)
                self.assertEqual(npm_token_faults(good.replace(old, new)), faults)
        swapped = ("Add the `NPM_TOKEN` repository secret for the first publish; delete the "
                   "token, then add the trusted publisher")
        self.assertEqual(npm_token_faults(swapped), [NO_ORDER], "delete comes after the publisher")

    def test_tag_admission_faults_bite(self):
        items = setup_items(SAMPLE_SETUP_HEADER)
        pypi_fault = ["the pypi setup item does not say the pypi environment admits the version "
                      "tags"]
        self.assertEqual(tag_admission_faults(items["pypi"].replace(
            "the `pypi` environment admits the version tags, because the release event's ref "
            "is the tag; ", ""), "pypi"), pypi_fault,
            "testpypi admitting the branches is not pypi admitting the tags")
        self.assertEqual(tag_admission_faults(items["pypi"].replace(
            "the `pypi` environment admits the version tags", "the `pypi` environment admits "
            "the `master` branch"), "pypi"), pypi_fault)
        self.assertEqual(tag_admission_faults(
            "pypi: the `pypi` environment carries no branch rule;", "pypi"), [])
        self.assertEqual(tag_admission_faults(items["npm"].replace(
            ", which admits the version tags", ""), "npm"),
            ["the npm setup item does not say the npm environment admits the version tags"])
        self.assertNotRegex(normalise(setup_text(SAMPLE_SETUP_HEADER).replace(
            ", because the release event's ref is the tag", "")), TAG_REF_REASON)

    def test_setup_items_read_only_the_setup_block(self):
        text = "# - npm: before the setup;\n" + SAMPLE_SETUP_HEADER + "# - npm: after the comment;\n"
        self.assertNotIn("before the setup", setup_items(text).get("npm", ""))
        self.assertNotIn("after the comment", setup_items(text).get("npm", ""))
        self.assertEqual(setup_items("name: release\n"), {})


class NpmSetupTaskTest(unittest.TestCase):
    """F6 - ``init``'s npm setup task calls ``NPM_TOKEN`` a repository secret and gives the order."""

    def test_the_npm_setup_task_meets_f6(self):
        tasks = [task for task in scaffold.release_setup_tasks(["python"], ["npm:pkg"])
                 if "NPM_TOKEN" in task]
        self.assertEqual(len(tasks), 1, f"one npm task; got {tasks!r}")
        self.assertEqual(npm_token_faults(tasks[0]), [], tasks[0])


class CratesSetupTaskTest(unittest.TestCase):
    """CR-MDB-071 §S4 - ``init``'s crates setup task, in the npm task's form: the
    ``CARGO_REGISTRY_TOKEN`` repository secret for the first publish, then the crates.io trusted
    publisher added and the token deleted."""

    def test_the_crates_setup_task_meets_f6(self):
        tasks = [task for task in scaffold.release_setup_tasks(["rust"], ["crates"])
                 if CARGO_SECRET_NAME in task]
        self.assertEqual(len(tasks), 1, f"one crates task; got {tasks!r}")
        self.assertEqual(first_publish_token_faults(tasks[0], CARGO_SECRET_NAME), [], tasks[0])
        self.assertIn("crates.io", tasks[0])


#: The target sets the header is read for: each holding a target with a publish environment.
# MIGRATED at CR-MDB-071 (§S3): the crates and maven-central sets join (was: pypi, npm:pkg and
# pypi,npm:pkg,github-assets).
SETUP_TARGET_SETS = (("pypi",), ("npm:pkg",), ("pypi", "npm:pkg", "github-assets"), ("crates",),
                     ("maven-central",), CRATES_MAVEN_DIRS, FULL_TARGETS)
#: The publish environments whose setup item must admit the version tags.
TAG_ENVIRONMENTS = {"pypi", "npm", "crates", "maven-central"}


class RenderedHeaderSetupTest(unittest.TestCase):
    """F6/F7 - the rendered header's setup items."""

    def each(self):
        for targets in SETUP_TARGET_SETS:
            text = render_files(["python"], list(targets))[RELEASE_YML]
            yield targets, {target.partition(":")[0] for target in targets}, text

    def test_the_npm_setup_item_calls_npm_token_a_repository_secret_in_order(self):
        for targets, names, text in self.each():
            if "npm" in names:
                with self.subTest(targets=targets):
                    self.assertEqual(npm_token_faults(setup_items(text).get("npm", "")), [])

    def test_the_crates_setup_item_calls_the_cargo_token_a_repository_secret_in_order(self):
        # CR-MDB-071 §S3: the first-publish reader, extended to the crates item.
        for targets, names, text in self.each():
            if "crates" in names:
                with self.subTest(targets=targets):
                    self.assertEqual(first_publish_token_faults(
                        setup_items(text).get("crates", ""), CARGO_SECRET_NAME), [])

    # MIGRATED at CR-MDB-071 (§S3): the tag-admission reader runs over crates and maven-central
    # too (was: pypi and npm).
    def test_each_publish_environment_admits_the_version_tags(self):
        for targets, names, text in self.each():
            items = setup_items(text)
            for name in sorted(names & TAG_ENVIRONMENTS):
                with self.subTest(targets=targets, environment=name):
                    self.assertEqual(tag_admission_faults(items.get(name, ""), name), [])

    def test_the_setup_says_the_release_events_ref_is_the_tag(self):
        for targets, _names, text in self.each():
            with self.subTest(targets=targets):
                self.assertRegex(normalise(setup_text(text)), TAG_REF_REASON)



if __name__ == "__main__":
    unittest.main()
