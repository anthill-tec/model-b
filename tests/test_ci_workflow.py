"""The CI test workflow, ``.github/workflows/ci.yml`` (CR-MDB-067 §S3, and §S6's readers).

Contract: ``docs/changes/CR-MDB-067-release-rehearsal-and-ci.md`` §S3: ``name: ci``, workflow
``permissions: contents: read``, one job ``test`` on ``ubuntu-latest``, pushes to ``develop``,
``release/**`` and ``hotfix/**`` plus ``pull_request`` and ``workflow_dispatch``, and five steps in
order — checkout with ``fetch-depth: 0``, ``actions/setup-python`` with ``python-version: "3.14"``,
``setup-uv``, ``python -m pip install build``, and the suite run directly with the three sandbox
variables under ``${{ runner.temp }}`` — every action pinned as §S2 pins them.

Each §S3 item is one check, a pure function of the workflow text returning its faults (``[]``
when the item holds). The checks are proved on sample text in both directions before they are
applied to the real file:

- ``CiWorkflowReadersProofTest`` — §S6: the readers this module adds to ``tests/_helpers.py``
  (``workflow_key``, ``workflow_permissions``, ``workflow_job_names``, a step's ``env``) on
  sample text, both ways.
- ``CiWorkflowChecksProofTest`` — every check passes :data:`CONFORMING_CI`, and each
  mutation in :data:`MUTATIONS` makes its check report exactly one fault.
- ``CiWorkflowTest`` — every check applied to the real ``ci.yml``.

Stdlib only.
"""

import re
import unittest
from pathlib import Path

from tests._helpers import (
    workflow_job,
    workflow_job_key,
    workflow_job_names,
    workflow_key,
    workflow_permissions,
    workflow_push_triggers,
    workflow_steps,
)
from tests.test_release_rehearsal import action_pin_faults

REPO_ROOT = Path(__file__).resolve().parent.parent
CI_REL = ".github/workflows/ci.yml"
CI_YML = REPO_ROOT / ".github" / "workflows" / "ci.yml"

#: §S3's values.
CI_BRANCHES = ("develop", "release/**", "hotfix/**")
CHECKOUT = "actions/checkout"
SETUP_PYTHON = "actions/setup-python"
SETUP_UV = "astral-sh/setup-uv"
BUILD_LINE = "python -m pip install build"
SUITE_LINE = "python -m unittest discover -s tests -t ."
SANDBOX_VARS = ("MODELB_HOME", "XDG_DATA_HOME", "PI_CODING_AGENT_DIR")
STEP_ORDER = [CHECKOUT, SETUP_PYTHON, SETUP_UV, BUILD_LINE, SUITE_LINE]

_UNDER_RUNNER_TEMP = re.compile(r"\$\{\{\s*runner\.temp\s*\}\}/\S+")
_QUOTED_PYTHON_VERSION = re.compile(r"""\s*python-version:\s*(["'])3\.14\1\s*(?:#.*)?""")


# ------------------------------------------------------------------ the checks ----

def _test_steps(text: str) -> list[dict]:
    return workflow_steps(workflow_job(text, "test"))


def _action(step: dict) -> str | None:
    """A ``uses:`` step's action without its ``@ref``; ``None`` for a ``run`` step."""
    return step["uses"].split("@", 1)[0] if step["uses"] else None


def _steps_using(text: str, action: str) -> list[dict]:
    return [step for step in _test_steps(text) if _action(step) == action]


def _steps_running(text: str, line: str) -> list[dict]:
    return [step for step in _test_steps(text) if [ln.strip() for ln in step["run"]] == [line]]


def name_faults(text: str) -> list[str]:
    """§S3 — the workflow is ``name: ci``."""
    name = workflow_key(text, "name")
    return [] if name == "ci" else [f"the workflow name is {name!r}, not 'ci'"]


def trigger_faults(text: str) -> list[str]:
    """§S3 — pushes to exactly ``develop``, ``release/**`` and ``hotfix/**`` (no tag push);
    ``pull_request``; ``workflow_dispatch``."""
    triggers = workflow_push_triggers(text)
    faults = []
    if sorted(triggers["branches"]) != sorted(CI_BRANCHES):
        faults.append(f"on.push.branches are {triggers['branches']!r}, not {list(CI_BRANCHES)!r}")
    if triggers["tags"]:
        faults.append(f"on.push also runs on tags {triggers['tags']!r}")
    for event in ("pull_request", "workflow_dispatch"):
        if not triggers[event]:
            faults.append(f"on: has no {event}")
    return faults


def permission_faults(text: str) -> list[str]:
    """§S3 — workflow-level ``permissions: contents: read``, nothing more."""
    permissions = workflow_permissions(text)
    if permissions == {"contents": "read"}:
        return []
    return [f"the workflow permissions are {permissions!r}, not {{'contents': 'read'}}"]


def job_faults(text: str) -> list[str]:
    """§S3 — one job, ``test``, on ``ubuntu-latest``."""
    names = workflow_job_names(text)
    if names != ["test"]:
        return [f"the jobs are {names!r}, not ['test']"]
    runs_on = workflow_job_key(workflow_job(text, "test"), "runs-on")
    return [] if runs_on == "ubuntu-latest" else [f"test runs on {runs_on!r}, not ubuntu-latest"]


def step_order_faults(text: str) -> list[str]:
    """§S3 — the five steps, in order, and nothing else."""
    found = [_action(step) or " / ".join(ln.strip() for ln in step["run"])
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
    if not any(_QUOTED_PYTHON_VERSION.fullmatch(line) for line in workflow_job(text, "test")):
        return ['python-version must be the quoted string "3.14", not a YAML number']
    return []


def uv_faults(text: str) -> list[str]:
    """§S3 step 3 — one ``setup-uv`` step."""
    count = len(_steps_using(text, SETUP_UV))
    return [] if count == 1 else [f"expected one {SETUP_UV} step; found {count}"]


def build_faults(text: str) -> list[str]:
    """§S3 step 4 — one step running exactly ``python -m pip install build``."""
    count = len(_steps_running(text, BUILD_LINE))
    return [] if count == 1 else [f"expected one step running {BUILD_LINE!r}; found {count}"]


def suite_faults(text: str) -> list[str]:
    """§S3 step 5 — one step running exactly the suite command, from the workspace root."""
    steps = _steps_running(text, SUITE_LINE)
    if len(steps) != 1:
        return [f"expected one step running {SUITE_LINE!r}; found {len(steps)}"]
    where = steps[0]["working-directory"]
    return [] if where is None else [f"the suite runs in {where!r}, not the workspace root"]


def sandbox_faults(text: str) -> list[str]:
    """§S3 step 5 — the suite step's ``env:`` is exactly the three sandbox variables, each under
    ``${{ runner.temp }}``."""
    steps = _steps_running(text, SUITE_LINE)
    if len(steps) != 1:
        return [f"no single suite step to read the sandbox variables from; found {len(steps)}"]
    env = steps[0]["env"]
    if sorted(env) != sorted(SANDBOX_VARS):
        return [f"the suite step's env is {sorted(env)!r}, not {sorted(SANDBOX_VARS)!r}"]
    outside = sorted(var for var in SANDBOX_VARS if not _UNDER_RUNNER_TEMP.fullmatch(env[var]))
    return [] if not outside else [f"{outside!r} are not set under ${{{{ runner.temp }}}}"]


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

#: A ``ci.yml`` meeting every §S3 item (``@PIN`` stands for a pinned ref).
CONFORMING_CI = """\
# CI: the unittest suite on a clean runner, outside any agent session.
name: ci

on:
  push:
    branches: [develop, "release/**", "hotfix/**"]
  pull_request:
  workflow_dispatch:

permissions:
  contents: read

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@PIN # v5.0.0
        with:
          fetch-depth: 0
      - uses: actions/setup-python@PIN # v6.0.0
        with:
          python-version: "3.14"
      - uses: astral-sh/setup-uv@PIN # v7.1.0
      - name: The build frontend, for the built-wheel checks
        run: python -m pip install build
      - name: The suite
        env:
          MODELB_HOME: ${{ runner.temp }}/modelb-home
          XDG_DATA_HOME: ${{ runner.temp }}/xdg-data
          PI_CODING_AGENT_DIR: "${{ runner.temp }}/pi-agent"
        run: python -m unittest discover -s tests -t .
""".replace("@PIN", "@" + _SHA)

_EXTRA_JOB = "  lint:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo lint\n"

#: ``(label, old, new, check)``: replacing ``old`` by ``new`` in :data:`CONFORMING_CI` must make
#: ``CHECKS[check]`` report exactly one fault.
MUTATIONS = (
    ("another workflow name", "name: ci\n", "name: tests\n", "name"),
    ("no workflow name", "name: ci\n", "", "name"),
    ("develop dropped", "[develop, ", "[", "triggers"),
    ("an extra branch", "[develop, ", "[develop, main, ", "triggers"),
    ("a tag push", "  push:\n", '  push:\n    tags: ["*"]\n', "triggers"),
    ("no pull_request", "  pull_request:\n", "", "triggers"),
    ("no workflow_dispatch", "  workflow_dispatch:\n", "", "triggers"),
    ("write permission", "  contents: read\n\njobs", "  contents: write\n\njobs", "permissions"),
    ("no workflow permissions", "permissions:\n  contents: read\n\n", "", "permissions"),
    ("another runner", "runs-on: ubuntu-latest", "runs-on: ubuntu-22.04", "job"),
    ("a second job", "", _EXTRA_JOB, "job"),
    ("the job renamed", "  test:\n", "  tests:\n", "job"),
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
    ("bare pip", "run: python -m pip install build", "run: pip install build", "build"),
    ("another top level", "discover -s tests -t .", "discover -s tests -t tests", "suite"),
    ("python3", "run: python -m unittest", "run: python3 -m unittest", "suite"),
    ("a working directory", "      - name: The suite\n",
     "      - name: The suite\n        working-directory: tests\n", "suite"),
    ("a fixed path", "MODELB_HOME: ${{ runner.temp }}/modelb-home", "MODELB_HOME: /tmp/mh",
     "sandbox"),
    ("a missing variable", '          PI_CODING_AGENT_DIR: "${{ runner.temp }}/pi-agent"\n', "",
     "sandbox"),
    ("an extra variable", "        env:\n",
     "        env:\n          HOME: ${{ runner.temp }}/home\n", "sandbox"),
    ("a bare runner.temp", "XDG_DATA_HOME: ${{ runner.temp }}/xdg-data",
     "XDG_DATA_HOME: ${{ runner.temp }}", "sandbox"),
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
        for step in workflow_steps(workflow_job(SAMPLE_READERS, "test")):
            self.assertEqual(set(step),
                             {"name", "run", "working-directory", "uses", "with", "env"})


# ------------------------------------------------------------------ the checks, proved ----

class CiWorkflowChecksProofTest(unittest.TestCase):
    """Every §S3 check passes the conforming sample and bites, once, on its mutation."""

    def test_every_check_passes_the_conforming_sample(self):
        for label, check in CHECKS.items():
            with self.subTest(check=label):
                self.assertEqual(check(CONFORMING_CI), [])

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

    def test_the_suite_command_is_read_from_the_workflow_text(self):
        self.assertEqual(_steps_running(CONFORMING_CI, SUITE_LINE)[0]["run"], [SUITE_LINE])


# ------------------------------------------------------------------ §S3 the real file ----

def _ci_text() -> str:
    if not CI_YML.is_file():
        raise AssertionError(f"§S3: {CI_REL} does not exist")
    return CI_YML.read_text(encoding="utf-8")


class CiWorkflowTest(unittest.TestCase):
    """§S3 — every check applied to the real ``.github/workflows/ci.yml``."""

    def test_the_workflow_is_named_ci(self):
        self.assertEqual(name_faults(_ci_text()), [])

    def test_it_runs_on_develop_release_and_hotfix_pushes_pull_requests_and_dispatch(self):
        self.assertEqual(trigger_faults(_ci_text()), [])

    def test_the_workflow_permissions_are_contents_read(self):
        self.assertEqual(permission_faults(_ci_text()), [])

    def test_its_one_job_test_runs_on_ubuntu_latest(self):
        self.assertEqual(job_faults(_ci_text()), [])

    def test_the_five_steps_run_in_order(self):
        self.assertEqual(step_order_faults(_ci_text()), [])

    def test_the_checkout_fetches_the_whole_history(self):
        self.assertEqual(checkout_faults(_ci_text()), [])

    def test_python_is_3_14(self):
        self.assertEqual(python_faults(_ci_text()), [])

    def test_uv_is_set_up(self):
        self.assertEqual(uv_faults(_ci_text()), [])

    def test_the_build_frontend_is_installed(self):
        self.assertEqual(build_faults(_ci_text()), [])

    def test_the_suite_runs_directly_with_unittest_discover(self):
        self.assertEqual(suite_faults(_ci_text()), [])

    def test_the_three_sandbox_variables_are_set_under_runner_temp(self):
        self.assertEqual(sandbox_faults(_ci_text()), [])

    def test_every_action_is_pinned_to_a_sha_with_a_version_comment(self):
        self.assertEqual(pin_faults(_ci_text()), [])


if __name__ == "__main__":
    unittest.main()
