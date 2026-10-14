"""The test job of the one release workflow, ``.github/workflows/release.yml`` (CR-MDB-070 §S1,
§S7), once the CI workflow ``ci.yml`` (CR-MDB-067 §S3 as amended by CR-MDB-069 §S2, and
CR-MDB-067 §S6's readers).

Contract: ``docs/changes/CR-MDB-070-one-workflow-tests-gate-every-publish.md`` §S1: ``name:
release``, workflow ``permissions: contents: read``, pushes to ``master``, ``release/**`` and
``hotfix/**`` plus ``release: types: [published]`` and ``workflow_dispatch`` (no tag pattern, no
``develop``, no ``pull_request``); a ``test`` job on ``ubuntu-latest`` among the jobs, with no
``if:`` and no ``needs``, whose four steps are CR-MDB-067 §S3's as amended by CR-MDB-069 §S2 —
checkout with ``fetch-depth: 0``, ``actions/setup-python`` with ``python-version: "3.14"``,
``setup-uv``, and the suite run directly with the three sandbox variables under
``${{ runner.temp }}``; every publish job (``rehearse``, ``create-release``, ``publish-pypi``,
``publish-npm``) ``needs: test``; ``ci.yml`` no longer exists.

MIGRATED at CR-MDB-070 C1 RED (§S1/§S7): the checks read ``release.yml``, not ``ci.yml``;
``name_faults`` wants ``release``; ``trigger_faults`` the master/release/hotfix pushes, the
published release and dispatch, and no ``develop`` or ``pull_request``; ``job_faults`` a ``test``
job among the jobs with no ``if:`` and no ``needs`` (no longer the one job); ``needs_faults`` is
new; ``permission_faults`` is unchanged; :data:`CONFORMING_CI` and :data:`MUTATIONS` take the
release workflow's shape; ``CiWorkflowTest`` asserts ``ci.yml`` is absent.

Each §S3 item is one check, a pure function of the workflow text returning its faults (``[]``
when the item holds). The checks are proved on sample text in both directions before they are
applied to the real file:

- ``CiWorkflowReadersProofTest`` — §S6: the readers this module adds to ``tests/_helpers.py``
  (``workflow_key``, ``workflow_permissions``, ``workflow_job_names``, a step's ``env``) on
  sample text, both ways.
- ``CiWorkflowChecksProofTest`` — every check passes :data:`CONFORMING_CI`, and each
  mutation in :data:`MUTATIONS` makes its check report exactly one fault.
- ``CiWorkflowTest`` — every check applied to the real ``release.yml``, and ``ci.yml`` asserted
  absent. MIGRATED at CR-MDB-070 C4 RED (VERIFY F4): was "every check applied to the real
  ``ci.yml``".

CR-MDB-069 §S2 amends CR-MDB-067 §S3: the ``python -m pip install build`` step (once step 4)
is gone, because every built-wheel check builds in isolation through ``uv build``. MIGRATED at
CR-MDB-069 C1 RED (§S2): ``STEP_ORDER`` lists four steps; ``build_faults`` is inverted, a fault
for every step whose run line holds ``install`` and a whole-word ``build`` or ``hatchling`` (so
``uv build`` never matches); :data:`CONFORMING_CI` loses the step; the "bare pip" mutation is
replaced by a re-added ``python -m pip install build`` step and a ``pip install hatchling`` step;
``test_the_four_steps_run_in_order`` and ``test_no_build_frontend_or_backend_is_installed``
replace the five-step and build-frontend tests.

MIGRATED at CR-MDB-068 C2 RED (§S7): Model B's ``release.yml`` is rendered
(``workflows.render(["python"], ["pypi", "npm:pi-package"], workflows-src)``, CR-MDB-068 §S4/§S7):
the test job is :data:`TEST_JOB`, ``test-python``; every publish job needs ``[test-python]``; and
the rendered test job carries no sandbox variables (a hosted runner is disposable), so
``sandbox_faults`` is inverted — a fault when the suite step sets any environment variable.
:data:`CONFORMING_CI`, :data:`MUTATIONS` and ``CiWorkflowTest`` follow. What any render's test job
must be is proved by ``tests.test_rendered_release_workflow``; these checks stay retargeted at
Model B's own file.

Stdlib only.
"""

import re
import unittest
from pathlib import Path

from tests._helpers import (
    md_section,
    workflow_job,
    workflow_job_key,
    workflow_job_names,
    workflow_key,
    workflow_permissions,
    workflow_push_triggers,
    workflow_steps,
)
# MIGRATED at CR-MDB-068 C2 RED (§S7): TEST_JOB, the rendered python test job, defined once there.
from tests.test_release_rehearsal import (
    CONFORMING_RELEASE,
    PUBLISH_JOBS,
    TEST_JOB,
    _action,
    action_pin_faults,
    job_needs,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
# MIGRATED at CR-MDB-070 C1 RED (§S1): the checks read release.yml; ci.yml must be absent.
CI_REL = ".github/workflows/release.yml"
CI_YML = REPO_ROOT / ".github" / "workflows" / "release.yml"
RETIRED_CI_REL = ".github/workflows/ci.yml"
RETIRED_CI_YML = REPO_ROOT / ".github" / "workflows" / "ci.yml"
CR_067 = REPO_ROOT / "docs" / "changes" / "CR-MDB-067-release-rehearsal-and-ci.md"

#: §S3's values.
# MIGRATED at CR-MDB-070 C1 RED (§S1): was develop, release/** and hotfix/**.
CI_BRANCHES = ("master", "release/**", "hotfix/**")
#: CR-MDB-070 §S1 — the release event's types.
RELEASE_TYPES = ["published"]
CHECKOUT = "actions/checkout"
SETUP_PYTHON = "actions/setup-python"
SETUP_UV = "astral-sh/setup-uv"
#: MIGRATED at CR-MDB-069 C1 RED (§S2): the step CR-MDB-069 §S2 retired; a mutation re-adds it.
BUILD_LINE = "python -m pip install build"
SUITE_LINE = "python -m unittest discover -s tests -t ."
#: The variables the test job once set; a mutation re-adds one. MIGRATED at CR-MDB-068 C2 RED
#: (§S7): the rendered test job sets none of them.
SANDBOX_VARS = ("MODELB_HOME", "XDG_DATA_HOME", "PI_CODING_AGENT_DIR")
# MIGRATED at CR-MDB-069 C1 RED (§S2): was five steps, with BUILD_LINE fourth.
STEP_ORDER = [CHECKOUT, SETUP_PYTHON, SETUP_UV, SUITE_LINE]

_QUOTED_PYTHON_VERSION = re.compile(r"""\s*python-version:\s*(["'])3\.14\1\s*(?:#.*)?""")
_BUILD_TOOL = re.compile(r"\b(?:build|hatchling)\b")


# ------------------------------------------------------------------ the checks ----

def _test_steps(text: str) -> list[dict]:
    return workflow_steps(workflow_job(text, TEST_JOB))


# MIGRATED at CR-MDB-070 C4 RED (VERIFY F5): ``_action`` is test_release_rehearsal's, defined once
# (was a second ``_action(step)`` here); each caller passes the step's ``uses``.
def _steps_using(text: str, action: str) -> list[dict]:
    return [step for step in _test_steps(text) if _action(step["uses"]) == action]


def _steps_running(text: str, line: str) -> list[dict]:
    return [step for step in _test_steps(text) if [ln.strip() for ln in step["run"]] == [line]]


def name_faults(text: str) -> list[str]:
    """CR-MDB-070 §S1 — the workflow is ``name: release``.

    MIGRATED at CR-MDB-070 C1 RED (§S1): was ``name: ci``."""
    name = workflow_key(text, "name")
    return [] if name == "release" else [f"the workflow name is {name!r}, not 'release'"]


def trigger_faults(text: str) -> list[str]:
    """CR-MDB-070 §S1 — pushes to exactly ``master``, ``release/**`` and ``hotfix/**`` (no tag
    push, no ``develop``); ``release: types: [published]``; ``workflow_dispatch``; no
    ``pull_request``.

    MIGRATED at CR-MDB-070 C1 RED (§S1): was ``develop``/``release/**``/``hotfix/**`` pushes,
    ``pull_request`` and ``workflow_dispatch``."""
    triggers = workflow_push_triggers(text)
    faults = []
    if sorted(triggers["branches"]) != sorted(CI_BRANCHES):
        faults.append(f"on.push.branches are {triggers['branches']!r}, not {list(CI_BRANCHES)!r}")
    if triggers["tags"]:
        faults.append(f"on.push also runs on tags {triggers['tags']!r}")
    if triggers["release"] != RELEASE_TYPES:
        faults.append(f"on.release.types are {triggers['release']!r}, not {RELEASE_TYPES!r}")
    if not triggers["workflow_dispatch"]:
        faults.append("on: has no workflow_dispatch")
    if triggers["pull_request"]:
        faults.append("on: runs on pull_request")
    return faults


def permission_faults(text: str) -> list[str]:
    """§S3 — workflow-level ``permissions: contents: read``, nothing more."""
    permissions = workflow_permissions(text)
    if permissions == {"contents": "read"}:
        return []
    return [f"the workflow permissions are {permissions!r}, not {{'contents': 'read'}}"]


def job_faults(text: str) -> list[str]:
    """CR-MDB-070 §S1 — a :data:`TEST_JOB` job among the jobs, on ``ubuntu-latest``, with no
    ``if:`` (it exists in every run) and no ``needs``.

    MIGRATED at CR-MDB-070 C1 RED (§S1): was one job, ``test``, and nothing else.
    MIGRATED at CR-MDB-068 C2 RED (§S7): the job is ``test-python``, was ``test``."""
    names = workflow_job_names(text)
    if TEST_JOB not in names:
        return [f"the jobs {names!r} hold no {TEST_JOB!r} job"]
    job = workflow_job(text, TEST_JOB)
    faults = []
    runs_on = workflow_job_key(job, "runs-on")
    if runs_on != "ubuntu-latest":
        faults.append(f"test runs on {runs_on!r}, not ubuntu-latest")
    condition = workflow_job_key(job, "if")
    if condition is not None:
        faults.append(f"the test job carries an if: ({condition!r}); it must exist in every run")
    needs = workflow_job_key(job, "needs")
    if needs is not None:
        faults.append(f"the test job needs {needs!r}; it needs nothing")
    return faults


def needs_faults(text: str) -> list[str]:
    """CR-MDB-070 §S1 — every publish job (``rehearse``, ``create-release``, ``publish-pypi``,
    ``publish-npm``) exists and needs the test job, exactly.

    MIGRATED at CR-MDB-068 C2 RED (§S7): ``needs: [test-python]``, was ``needs: test``."""
    names = workflow_job_names(text)
    faults = []
    for name in PUBLISH_JOBS:
        if name not in names:
            faults.append(f"there is no {name} job")
            continue
        needs = job_needs(workflow_job(text, name))
        if needs != [TEST_JOB]:
            faults.append(f"{name} needs {needs!r}, not {[TEST_JOB]!r}")
    return faults


def step_order_faults(text: str) -> list[str]:
    """§S3 as amended by CR-MDB-069 §S2 — the four steps, in order, and nothing else."""
    found = [_action(step["uses"]) or " / ".join(ln.strip() for ln in step["run"])
             for step in _test_steps(text)]
    return [] if found == STEP_ORDER else [f"the steps are {found!r}, not {STEP_ORDER!r}"]


def checkout_faults(text: str) -> list[str]:
    """§S3 step 1 — one checkout, with ``fetch-depth: 0``."""
    steps = _steps_using(text, CHECKOUT)
    if len(steps) != 1:
        return [f"expected one {CHECKOUT} step; found {len(steps)}"]
    depth = steps[0]["with"].get("fetch-depth")
    return [] if depth == "0" else [f"the checkout's fetch-depth is {depth!r}, not '0'"]


def python_faults(text: str) -> list[str]:
    """§S3 step 2 — one ``actions/setup-python`` with ``python-version: "3.14"``, quoted."""
    steps = _steps_using(text, SETUP_PYTHON)
    if len(steps) != 1:
        return [f"expected one {SETUP_PYTHON} step; found {len(steps)}"]
    version = steps[0]["with"].get("python-version")
    if version != "3.14":
        return [f"python-version is {version!r}, not '3.14'"]
    if not any(_QUOTED_PYTHON_VERSION.fullmatch(line) for line in workflow_job(text, TEST_JOB)):
        return ['python-version must be the quoted string "3.14", not a YAML number']
    return []


def uv_faults(text: str) -> list[str]:
    """§S3 step 3 — one ``setup-uv`` step."""
    count = len(_steps_using(text, SETUP_UV))
    return [] if count == 1 else [f"expected one {SETUP_UV} step; found {count}"]


def build_faults(text: str) -> list[str]:
    """CR-MDB-069 §S2 — no step installs a build frontend or backend: one fault for every step
    whose run line holds ``install`` and a whole-word ``build`` or ``hatchling`` (``uv build``
    installs nothing, so it never matches).

    MIGRATED at CR-MDB-069 C1 RED (§S2): was one step running exactly ``python -m pip install build``."""
    faults = []
    for step in _test_steps(text):
        lines = [ln.strip() for ln in step["run"] if "install" in ln and _BUILD_TOOL.search(ln)]
        if lines:
            faults.append(f"a step installs a build frontend or backend: {lines[0]!r}")
    return faults


def suite_faults(text: str) -> list[str]:
    """§S3 step 5 — one step running exactly the suite command, from the workspace root."""
    steps = _steps_running(text, SUITE_LINE)
    if len(steps) != 1:
        return [f"expected one step running {SUITE_LINE!r}; found {len(steps)}"]
    where = steps[0]["working-directory"]
    return [] if where is None else [f"the suite runs in {where!r}, not the workspace root"]


def sandbox_faults(text: str) -> list[str]:
    """CR-MDB-068 §S7 — the suite step sets no environment variable: the rendered test job carries
    no sandbox variables (a hosted runner is disposable).

    MIGRATED at CR-MDB-068 C2 RED (§S7): was "the suite step's ``env:`` is exactly the three
    sandbox variables, each under ``${{ runner.temp }}``" (CR-MDB-067 §S3 step 5)."""
    steps = _steps_running(text, SUITE_LINE)
    if len(steps) != 1:
        return [f"no single suite step to read the environment from; found {len(steps)}"]
    env = steps[0]["env"]
    return [] if not env else [f"the suite step sets {sorted(env)!r}; it sets no variable"]


def pin_faults(text: str) -> list[str]:
    """§S3 — every action pinned as §S2 pins them: a 40-hex SHA with a ``# vX.Y.Z`` comment."""
    uses = sum(1 for step in _test_steps(text) if step["uses"])
    faults = action_pin_faults(text)
    if uses == 0:
        faults.append("the test job uses no action at all")
    return faults


CHECKS = {
    "name": name_faults,
    "triggers": trigger_faults,
    "permissions": permission_faults,
    "job": job_faults,
    "needs": needs_faults,
    "step order": step_order_faults,
    "checkout": checkout_faults,
    "python": python_faults,
    "uv": uv_faults,
    "build": build_faults,
    "suite": suite_faults,
    "sandbox": sandbox_faults,
    "pins": pin_faults,
}


# ------------------------------------------------------------------ sample text ----

_SHA = "08c6903cd8c0fde910a37f88322edcfb5dd907a8"

#: A release workflow meeting every CR-MDB-070 §S1 item (``@PIN`` stands for a pinned ref).
#: MIGRATED at CR-MDB-070 C1 RED (§S1): was a ``ci.yml`` with one ``test`` job.
#: MIGRATED at CR-MDB-068 C2 RED (§S7): the job is ``test-python``, its suite step sets no
#: variable, and every publish job needs ``test-python``.
CONFORMING_CI = """\
# The release workflow: the tests gate every publish.
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
  test-python:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@PIN # v5.0.0
        with:
          fetch-depth: 0
      - uses: actions/setup-python@PIN # v6.0.0
        with:
          python-version: "3.14"
      - uses: astral-sh/setup-uv@PIN # v7.1.0
      - name: The suite
        run: python -m unittest discover -s tests -t .

  rehearse:
    needs: test-python
    runs-on: ubuntu-latest
    steps:
      - run: echo rehearse

  create-release:
    needs: [test-python]
    runs-on: ubuntu-latest
    steps:
      - run: echo create

  publish-pypi:
    needs: "test-python"
    runs-on: ubuntu-latest
    steps:
      - run: echo pypi

  publish-npm:
    needs:
      - test-python
    runs-on: ubuntu-latest
    steps:
      - run: echo npm
""".replace("@PIN", "@" + _SHA)

_EXTRA_JOB = "  lint:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo lint\n"
_REHEARSE = "  rehearse:\n    needs: test-python\n"
_PUBLISH_NPM = "  publish-npm:\n    needs:\n      - test-python\n"

#: ``(label, old, new, check)``: replacing ``old`` by ``new`` in :data:`CONFORMING_CI` must make
#: ``CHECKS[check]`` report exactly one fault.
MUTATIONS = (
    # MIGRATED at CR-MDB-070 C1 RED (§S1/§S7): the name, trigger and job mutations take the
    # release workflow's shape; "a second job" no longer bites (the test job is among the jobs).
    ("another workflow name", "name: release\n", "name: ci\n", "name"),
    ("no workflow name", "name: release\n", "", "name"),
    ("master dropped", "[master, ", "[", "triggers"),
    ("develop added", "[master, ", "[develop, master, ", "triggers"),
    ("an extra branch", "[master, ", "[master, main, ", "triggers"),
    ("a tag push", "  push:\n", '  push:\n    tags: ["*"]\n', "triggers"),
    ("a pull_request", "  workflow_dispatch:\n", "  pull_request:\n  workflow_dispatch:\n",
     "triggers"),
    ("no release event", "  release:\n    types: [published]\n", "", "triggers"),
    ("another release type", "types: [published]", "types: [created]", "triggers"),
    ("no workflow_dispatch", "  workflow_dispatch:\n", "", "triggers"),
    ("write permission", "  contents: read\n\njobs", "  contents: write\n\njobs", "permissions"),
    ("no workflow permissions", "permissions:\n  contents: read\n\n", "", "permissions"),
    # MIGRATED at CR-MDB-068 C2 RED (§S7): the job is test-python; "the job renamed" renames it
    # back to test, and a publish job needing the old test job bites.
    ("another runner", "  test-python:\n    runs-on: ubuntu-latest",
     "  test-python:\n    runs-on: ubuntu-22.04", "job"),
    ("the job renamed", "  test-python:\n", "  test:\n", "job"),
    ("the test job scoped", "  test-python:\n",
     "  test-python:\n    if: github.event_name == 'push'\n", "job"),
    ("the test job needs another", "  test-python:\n", "  test-python:\n    needs: lint\n", "job"),
    ("rehearse needs nothing", _REHEARSE, "  rehearse:\n", "needs"),
    ("create-release needs another job", "    needs: [test-python]\n", "    needs: [lint]\n",
     "needs"),
    ("publish-pypi needs a second job", '  publish-pypi:\n    needs: "test-python"\n',
     "  publish-pypi:\n    needs: [test-python, lint]\n", "needs"),
    ("rehearse needs the retired test job", _REHEARSE, "  rehearse:\n    needs: test\n", "needs"),
    ("publish-npm renamed", _PUBLISH_NPM, "  publish-node:\n    needs:\n      - test-python\n",
     "needs"),
    ("setup-uv before setup-python",
     "      - uses: actions/setup-python@" + _SHA + " # v6.0.0\n        with:\n"
     '          python-version: "3.14"\n      - uses: astral-sh/setup-uv@' + _SHA + " # v7.1.0\n",
     "      - uses: astral-sh/setup-uv@" + _SHA + " # v7.1.0\n      - uses: actions/setup-python@"
     + _SHA + ' # v6.0.0\n        with:\n          python-version: "3.14"\n', "step order"),
    ("an extra step", "      - name: The suite\n",
     "      - run: python --version\n      - name: The suite\n", "step order"),
    ("a shallow checkout", "fetch-depth: 0", "fetch-depth: 1", "checkout"),
    ("no fetch-depth", "        with:\n          fetch-depth: 0\n", "", "checkout"),
    ("Python 3.13", 'python-version: "3.14"', 'python-version: "3.13"', "python"),
    ("an unquoted version", 'python-version: "3.14"', "python-version: 3.14", "python"),
    ("another uv action", "astral-sh/setup-uv@", "yezz123/setup-uv@", "uv"),
    # MIGRATED at CR-MDB-069 C1 RED (§S2): was "bare pip" (the step's pip spelled bare).
    ("a re-added python -m pip install build step", "      - name: The suite\n",
     "      - name: The build frontend\n        run: " + BUILD_LINE + "\n      - name: The suite\n",
     "build"),
    ("a pip install hatchling step", "      - name: The suite\n",
     "      - run: pip install hatchling\n      - name: The suite\n", "build"),
    ("another top level", "discover -s tests -t .", "discover -s tests -t tests", "suite"),
    ("python3", "run: python -m unittest", "run: python3 -m unittest", "suite"),
    ("a working directory", "      - name: The suite\n",
     "      - name: The suite\n        working-directory: tests\n", "suite"),
    # MIGRATED at CR-MDB-068 C2 RED (§S7): the suite step sets no variable; each mutation
    # re-adds an env block (was: a fixed path, a missing, an extra and a bare-runner.temp variable).
    ("the sandbox variables re-added", "      - name: The suite\n",
     "      - name: The suite\n        env:\n"
     + "".join(f"          {var}: ${{{{ runner.temp }}}}/{var.lower()}\n" for var in SANDBOX_VARS),
     "sandbox"),
    ("one variable set", "      - name: The suite\n",
     "      - name: The suite\n        env:\n          HOME: /tmp/home\n", "sandbox"),
    ("a tag ref", "actions/checkout@" + _SHA + " # v5.0.0", "actions/checkout@v5", "pins"),
    ("no version comment", "astral-sh/setup-uv@" + _SHA + " # v7.1.0",
     "astral-sh/setup-uv@" + _SHA, "pins"),
)


#: Sample text for the readers: top-level keys, job keys and step keys of the same names.
SAMPLE_READERS = f"""\
# A sample workflow.
name: "ci"  # the workflow's name

on:
  push:
    branches: [develop]

permissions:
  contents: read

jobs:
  test:
    name: not-the-workflow-name
    runs-on: ubuntu-latest
    permissions:
      contents: write
    env:
      JOB_LEVEL: not-a-step-env
    steps:
      - name: Checkout
        uses: actions/checkout@{_SHA} # v5.0.0
        with:
          fetch-depth: 0
      - name: Suite
        env:
          MODELB_HOME: ${{{{ runner.temp }}}}/mh
          XDG_DATA_HOME: "${{{{ runner.temp }}}}/xdg"  # quoted
        with:
          not-env: x
        run: python -m unittest discover -s tests -t .
  lint:
    # a comment line
    runs-on: ubuntu-latest
    steps:
      - run: echo hi
"""

#: No top-level ``name:`` or ``permissions:``; its job and steps carry both.
SAMPLE_NO_TOP_LEVEL = """\
on: [push]
jobs:
  build:
    name: a job name
    permissions: read-all
    steps:
      - name: a step name
        run: echo hi
"""


# ------------------------------------------------------------------ §S6 the readers ----

class CiWorkflowReadersProofTest(unittest.TestCase):
    """§S6 — the readers §S3 needs, proved on sample text both ways."""

    def test_workflow_key_reads_the_top_level_name_without_quotes_or_comment(self):
        self.assertEqual(workflow_key(SAMPLE_READERS, "name"), "ci")

    def test_workflow_key_never_reads_a_jobs_or_a_steps_key(self):
        self.assertIsNone(workflow_key(SAMPLE_NO_TOP_LEVEL, "name"),
                          "a job's and a step's name: are not the workflow's")
        self.assertIsNone(workflow_key(SAMPLE_READERS, "runs-on"))

    def test_workflow_key_of_a_block_valued_key_is_present_but_empty(self):
        self.assertEqual(workflow_key(SAMPLE_READERS, "jobs"), "")

    def test_workflow_permissions_read_the_top_level_mapping_not_the_jobs(self):
        self.assertEqual(workflow_permissions(SAMPLE_READERS), {"contents": "read"})

    def test_workflow_permissions_read_the_scalar_form(self):
        self.assertEqual(workflow_permissions("permissions: read-all\non: [push]\n"), "read-all")

    def test_workflow_permissions_are_none_when_only_a_job_declares_them(self):
        self.assertIsNone(workflow_permissions(SAMPLE_NO_TOP_LEVEL))

    def test_job_names_are_the_keys_under_jobs_in_order(self):
        self.assertEqual(workflow_job_names(SAMPLE_READERS), ["test", "lint"])
        self.assertEqual(workflow_job_names(SAMPLE_NO_TOP_LEVEL), ["build"])

    def test_job_names_raise_without_a_jobs_key(self):
        with self.assertRaises(AssertionError) as ctx:
            workflow_job_names("name: x\non: [push]\n")
        self.assertIn("jobs:", str(ctx.exception))

    def test_a_steps_env_reads_as_a_dict_of_its_unquoted_scalars(self):
        steps = workflow_steps(workflow_job(SAMPLE_READERS, "test"))
        self.assertEqual(steps[1]["env"], {"MODELB_HOME": "${{ runner.temp }}/mh",
                                           "XDG_DATA_HOME": "${{ runner.temp }}/xdg"})
        self.assertEqual(steps[1]["with"], {"not-env": "x"}, "env never leaks into with")
        self.assertEqual(steps[1]["run"], ["python -m unittest discover -s tests -t ."])

    def test_a_step_without_env_reads_an_empty_env_and_never_the_jobs(self):
        steps = workflow_steps(workflow_job(SAMPLE_READERS, "test"))
        self.assertEqual(steps[0]["env"], {}, "the job-level env is not a step's")
        self.assertEqual(steps[0]["with"], {"fetch-depth": "0"}, "with never leaks into env")

    def test_the_step_reader_keeps_every_key_existing_callers_read(self):
        # MIGRATED at CR-MDB-070 C1 RED (§S7): the step reader also returns ``id`` and ``if``.
        for step in workflow_steps(workflow_job(SAMPLE_READERS, "test")):
            self.assertEqual(set(step), {"name", "run", "working-directory", "uses", "with",
                                         "env", "id", "if"})


# ------------------------------------------------------------------ the checks, proved ----

class CiWorkflowChecksProofTest(unittest.TestCase):
    """Every §S3 check passes the conforming sample and bites, once, on its mutation."""

    def test_every_check_passes_the_conforming_sample(self):
        for label, check in CHECKS.items():
            with self.subTest(check=label):
                self.assertEqual(check(CONFORMING_CI), [])

    # CR-MDB-070 C1 RED (§S1) — the full conforming release.yml sample of
    # tests.test_release_rehearsal passes every check, too.
    def test_every_check_passes_the_full_conforming_release_sample(self):
        for label, check in CHECKS.items():
            with self.subTest(check=label):
                self.assertEqual(check(CONFORMING_RELEASE), [])

    def test_each_mutation_makes_its_check_report_exactly_one_fault(self):
        for label, old, new, check in MUTATIONS:
            with self.subTest(mutation=label):
                if old:
                    self.assertEqual(CONFORMING_CI.count(old), 1, f"{old!r} must occur once")
                    text = CONFORMING_CI.replace(old, new)
                else:
                    text = CONFORMING_CI + new
                self.assertNotEqual(text, CONFORMING_CI)
                faults = CHECKS[check](text)
                self.assertEqual(len(faults), 1, faults)

    def test_every_check_has_a_mutation_that_bites_it(self):
        self.assertEqual(sorted({check for *_rest, check in MUTATIONS}), sorted(CHECKS))

    # CR-MDB-070 C1 RED (§S1) — the test job is among the jobs: another job beside it is no fault.
    def test_another_job_beside_the_test_job_is_no_job_fault(self):
        self.assertEqual(job_faults(CONFORMING_CI + _EXTRA_JOB), [])
        self.assertEqual(workflow_job_names(CONFORMING_CI + _EXTRA_JOB)[-1], "lint")

    def test_the_suite_command_is_read_from_the_workflow_text(self):
        self.assertEqual(_steps_running(CONFORMING_CI, SUITE_LINE)[0]["run"], [SUITE_LINE])

    def test_build_faults_never_match_uv_build_or_an_unrelated_install(self):
        # CR-MDB-069 §S2: `uv build` installs nothing; installing a test dependency is no build tool.
        text = CONFORMING_CI.replace(
            "      - name: The suite\n",
            "      - run: uv build --wheel\n"
            "      - run: python -m pip install unittest-xml-reporting\n"
            "      - run: echo build\n"
            "      - name: The suite\n")
        self.assertEqual(build_faults(text), [])

    def test_build_faults_report_every_installing_step_once(self):
        # CR-MDB-069 §S2: one fault per step, including a line inside a `run: |` block.
        text = CONFORMING_CI.replace(
            "      - name: The suite\n",
            "      - run: uv pip install build hatchling\n"
            "      - run: |\n"
            "          uv sync\n"
            "          python -m pip install --upgrade hatchling\n"
            "      - name: The suite\n")
        self.assertEqual(build_faults(text), [
            "a step installs a build frontend or backend: 'uv pip install build hatchling'",
            "a step installs a build frontend or backend: "
            "'python -m pip install --upgrade hatchling'",
        ])


# ------------------------------------------------------------------ §S1 the real file ----

def _ci_text() -> str:
    if not CI_YML.is_file():
        raise AssertionError(f"§S1: {CI_REL} does not exist")
    return CI_YML.read_text(encoding="utf-8")


class CiWorkflowTest(unittest.TestCase):
    """CR-MDB-070 §S1 — every check applied to the real ``.github/workflows/release.yml``; the
    CI workflow ``ci.yml`` is gone.

    MIGRATED at CR-MDB-070 C1 RED (§S1): was every check applied to ``ci.yml``."""

    def test_ci_yml_no_longer_exists(self):
        self.assertFalse(RETIRED_CI_YML.exists(), f"§S1: {RETIRED_CI_REL} is deleted")

    # MIGRATED at CR-MDB-070 C1 RED (§S1): was test_the_workflow_is_named_ci.
    def test_the_workflow_is_named_release(self):
        self.assertEqual(name_faults(_ci_text()), [])

    # MIGRATED at CR-MDB-070 C1 RED (§S1): was
    # test_it_runs_on_develop_release_and_hotfix_pushes_pull_requests_and_dispatch.
    def test_it_runs_on_master_release_and_hotfix_pushes_the_published_release_and_dispatch(self):
        self.assertEqual(trigger_faults(_ci_text()), [])

    def test_the_workflow_permissions_are_contents_read(self):
        self.assertEqual(permission_faults(_ci_text()), [])

    # MIGRATED at CR-MDB-070 C1 RED (§S1): was test_its_one_job_test_runs_on_ubuntu_latest.
    def test_its_test_job_runs_on_ubuntu_latest_with_no_if_and_no_needs(self):
        self.assertEqual(job_faults(_ci_text()), [])

    def test_every_publish_job_needs_the_test_job(self):
        self.assertEqual(needs_faults(_ci_text()), [])

    # MIGRATED at CR-MDB-069 C1 RED (§S2): was test_the_five_steps_run_in_order.
    def test_the_four_steps_run_in_order(self):
        self.assertEqual(step_order_faults(_ci_text()), [])

    def test_the_checkout_fetches_the_whole_history(self):
        self.assertEqual(checkout_faults(_ci_text()), [])

    def test_python_is_3_14(self):
        self.assertEqual(python_faults(_ci_text()), [])

    def test_uv_is_set_up(self):
        self.assertEqual(uv_faults(_ci_text()), [])

    # MIGRATED at CR-MDB-069 C1 RED (§S2): was test_the_build_frontend_is_installed.
    def test_no_build_frontend_or_backend_is_installed(self):
        self.assertEqual(build_faults(_ci_text()), [])

    def test_the_suite_runs_directly_with_unittest_discover(self):
        self.assertEqual(suite_faults(_ci_text()), [])

    # MIGRATED at CR-MDB-068 C2 RED (§S7): was
    # test_the_three_sandbox_variables_are_set_under_runner_temp.
    def test_the_suite_step_sets_no_sandbox_variable(self):
        self.assertEqual(sandbox_faults(_ci_text()), [])

    def test_every_action_is_pinned_to_a_sha_with_a_version_comment(self):
        self.assertEqual(pin_faults(_ci_text()), [])


class CiWorkflowAmendmentNoteTest(unittest.TestCase):
    """CR-MDB-069 §S4 — CR-MDB-067's §S3 carries the dated line retiring its step 4."""

    def test_cr_mdb_067_s3_records_step_4_retired_by_cr_mdb_069(self):
        section = md_section(CR_067.read_text(encoding="utf-8"), "### §S3", stop_prefix="#")
        self.assertIn("python -m pip install build", section)
        self.assertIn("retired by CR-MDB-069 §S2, 2026-10-14", section,
                      "CR-MDB-069 §S4: CR-MDB-067 §S3 step 4 carries no dated retirement line")


if __name__ == "__main__":
    unittest.main()
