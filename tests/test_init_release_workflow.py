"""``modelb-axi init`` renders the project's release workflow and its two scripts (CR-MDB-068 §S5).

Contract: ``docs/changes/CR-MDB-068-release-and-ci-workflow-templates.md`` §S5 and its acceptance
criterion: through the real ``run_init`` in a sandbox (solo, ``multi:2``, ``monorepo:a,b``; no
target and each target; arduino and ``github-assets``), the three files planned and emitted, each
intact under its marker, written after validation; the setup tasks; the ``--force-managed`` help.

Class map:

- ``InitPlansReleaseFilesTest`` — ``scaffold.plan_files`` lists ``.github/workflows/release.yml``,
  ``.github/scripts/stamp_version.py`` and ``.github/scripts/changelog_section.py`` once each, at
  the root only.
- ``InitRendersReleaseFilesTest`` — each shape, each target set, and arduino with
  ``github-assets``: the envelope's ``planned`` and ``emitted`` list the three files once each,
  every file on disk is byte for byte ``workflows.render(<stacks>, <canonical targets>,
  scaffold._workflow_sources(home))``'s text and intact under its first-line marker, and no
  monorepo sub-project gets a copy.
- ``InitPrerendersReleaseFilesTest`` — the files are rendered before the first write: a render
  failure (a part missing from the asset root's ``workflows-src/``) is refused with exit 2 and
  writes nothing, ``--dry-run`` included; an invalid ``--release-targets`` writes nothing.
- ``InitReleaseSetupTasksTest`` — the release setup tasks, per stack and per target, in the
  envelope's ``release_setup`` list and, each as one unchecked ``- [ ] `` line, in the root
  ``AGENTS.md``'s ``## Setup`` section: ``tests/`` (python), ``bun.lock`` (bun), ``Cargo.lock``
  (rust), ``mvnw`` (quarkus, java), an executable ``.github/scripts/ci-test`` (arduino), an
  executable ``.github/scripts/build-assets`` (``github-assets``); ``pypi``: the ``pypi`` and
  ``testpypi`` environments and the trusted publishers; ``npm``: the ``npm`` environment, the
  ``NPM_TOKEN`` secret and the trusted publisher. Nothing else but, at most, one ``RELEASE_PAT``
  task.
- ``InitForceManagedHelpTest`` — ``init --force-managed``'s help names the release workflow files
  beside the permission policy.

The envelope field is ``release_setup`` — a list of strings, the release-workflow setup tasks
only (the other Setup tasks stay where they are); each string is a task's text without its
``- [ ] `` prefix. CR-MDB-068 §S5 leaves the field's name open; this module fixes it.

Isolation: every ``init`` runs in process in the sandbox of ``tests.test_project_setup_section``
(``MODELB_HOME``, ``HOME`` and ``PI_CODING_AGENT_DIR`` under a per-test temp dir; the
``install.toml`` asset root ``<home>/no-asset-root-here`` holds nothing, so the workflow sources
resolve to the repository's ``workflows-src/``).

CR-MDB-071 (§S1/§S3/§S4) adds ``crates`` and ``maven-central`` to the target sets, their setup
tasks (attributed by ``CARGO_REGISTRY_TOKEN`` and ``MAVEN_CENTRAL_USERNAME``, in canonical order)
and the wiring case ``test_crates_and_maven_central_render_their_publish_jobs``.

Stdlib only.
"""

import re
import shutil
import unittest

from modelb_axi import agents, scaffold
from tests import test_project_setup_section as _setup
from tests.test_release_workflow_verb import cli_subparser
from tests.test_workflow_render import (
    MARKER_PREFIX,
    RENDERED_FILES,
    SOURCE,
    render_files,
)

SUBS = ("a", "b")
#: §S5 AC — the three shapes.
SHAPES = (("solo", "standalone"), ("multi:2", "standalone"), ("solo", "monorepo:a,b"))
#: §S5 AC — no target and each target, as given to ``--release-targets``, with the canonical
#: list the workflow renders (CR-MDB-068 §S1).
TARGET_VALUES = (
    (None, []),
    ("", []),
    ("pypi", ["pypi"]),
    ("npm:pkg", ["npm:pkg"]),
    ("github-assets", ["github-assets"]),
    ("github-assets,npm:./pkg/,pypi", ["pypi", "npm:pkg", "github-assets"]),
    # MIGRATED at CR-MDB-071 (§S4): the crates and maven-central targets, alone, in
    # sub-directories and with every other target.
    ("crates", ["crates"]),
    ("maven-central", ["maven-central"]),
    ("maven-central:./b/,crates:a", ["crates:a", "maven-central:b"]),
    ("github-assets,maven-central,crates,npm:pkg,pypi",
     ["pypi", "npm:pkg", "crates", "maven-central", "github-assets"]),
)
#: §S5 — the file each stack's release task names (the attribution key of its task).
STACK_TOKENS = {
    "python": "tests/",
    "bun": "bun.lock",
    "rust": "Cargo.lock",
    "quarkus": "mvnw",
    "java": "mvnw",
    "arduino": ".github/scripts/ci-test",
}
#: §S5 — the token that attributes a task to each target, then what that task must name: its
#: environment(s), secret and publisher, or its executable script.
# MIGRATED at CR-MDB-071 (§S4): crates and maven-central join, each attributed by a secret
# only its task names, and each needing the header's items as its task.
TARGET_TOKENS = {"pypi": "testpypi", "npm": "NPM_TOKEN", "crates": "CARGO_REGISTRY_TOKEN",
                 "maven-central": "MAVEN_CENTRAL_USERNAME", "github-assets": "build-assets"}
TARGET_NEEDS = {
    "pypi": (r"(?<![\w.-])pypi(?![\w.-])", r"(?<![\w.-])testpypi(?![\w.-])", r"\benvironments?\b",
             r"(?i)\btrusted publishers?\b"),
    "npm": (r"(?<![\w.-])npm(?![\w.-])", r"\benvironment\b", r"\bNPM_TOKEN\b",
            r"(?i)\btrusted publisher\b"),
    "crates": (r"(?<![\w.-])crates(?![\w.-])", r"\benvironment\b", r"\bCARGO_REGISTRY_TOKEN\b",
               r"(?i)\brepository secret\b", r"(?i)\bfirst publish\b", r"(?i)\btrusted publisher\b",
               r"\bcrates\.io\b", r"(?i)\bdelete\b"),
    "maven-central": (r"(?<![\w.-])maven-central(?![\w.-])", r"\benvironment\b",
                      r"(?i)\bnamespace\b", r"(?i)\bcentral portal\b", r"(?i)\brepository secrets?\b",
                      r"\bMAVEN_CENTRAL_USERNAME\b", r"\bMAVEN_CENTRAL_PASSWORD\b",
                      r"(?i)\buser token\b", r"\bMAVEN_GPG_PRIVATE_KEY\b",
                      r"\bMAVEN_GPG_PASSPHRASE\b", r"\bcentral-publishing-maven-plugin\b",
                      re.escape("<extensions>true</extensions>"), r"(?i)\bsources\b",
                      r"(?i)\bjavadoc\b", r"\bmaven-gpg-plugin\b", re.escape("3.2.0"),
                      r"\bmvnw\b", r"(?i)\brepository root\b"),
    "github-assets": (re.escape(".github/scripts/build-assets"), r"(?i)\bexecutable\b"),
}
#: The one task allowed beyond the stacks' and the targets': the repository secret every
#: rendered ``create-release`` needs.
RELEASE_PAT = "RELEASE_PAT"


def target_names(targets: list[str]) -> list[str]:
    return [target.partition(":")[0] for target in targets]


class InitPlansReleaseFilesTest(unittest.TestCase):
    """§S5 — ``plan_files`` adds the three files, at the root only."""

    def test_plan_files_lists_each_release_file_once_at_the_root(self):
        sub_sets: tuple[list[str], ...] = ([], [str(sub) for sub in SUBS])
        for subs in sub_sets:
            with self.subTest(subs=subs):
                plan = scaffold.plan_files(subs)
                for rel in RENDERED_FILES:
                    self.assertEqual(plan.count(rel), 1, f"§S5: {rel} planned once; plan={plan!r}")
                self.assertEqual([p for p in plan for sub in subs if p.startswith(f"{sub}/.github/")],
                                 [], "§S5: no sub-project gets a release workflow")


class _ReleaseInitCase(_setup._Case):
    """The CR-MDB-045 init sandbox plus the expected render."""

    def expected(self, stacks: list[str], targets: list[str]) -> dict:
        """The three files ``init`` must write, rendered from the sources the sandbox resolves."""
        return render_files(stacks, targets, scaffold._workflow_sources(self.modelb_home))

    def init_with(self, name: str, release_targets=None, **fields) -> dict:
        """``init`` into ``<root>/<name>`` (``--release-targets`` only when not ``None``)."""
        self.target = self.root / name
        if release_targets is not None:
            fields["release_targets"] = release_targets
        axi, _err = self.init_ok(**fields)
        return axi


class InitRendersReleaseFilesTest(_ReleaseInitCase):
    """§S5 AC — the three files planned, emitted and written intact under their marker."""

    def assert_rendered(self, axi: dict, stacks: list[str], targets: list[str],
                        subs: tuple = ()) -> None:
        planned, emitted = axi.get("planned") or [], axi.get("emitted") or []
        for rel, text in self.expected(stacks, targets).items():
            with self.subTest(file=rel):
                self.assertEqual(planned.count(rel), 1, f"§S5: planned once; planned={planned!r}")
                self.assertEqual(emitted.count(rel), 1, f"§S5: emitted once; emitted={emitted!r}")
                path = self.target / rel
                self.assertTrue(path.is_file(), f"§S5: {rel} is written")
                written = path.read_text(encoding="utf-8")
                self.assertEqual(written, text,
                                 f"§S5: {rel} is render({stacks!r}, {targets!r})'s text")
                self.assertEqual(agents.first_line_ownership(written, MARKER_PREFIX),
                                 agents.OWNED_INTACT, f"§S5: {rel} is intact under its marker")
                for sub in subs:
                    self.assertFalse((self.target / sub / rel).exists(),
                                     f"§S5: no copy under the sub-project {sub}/")

    def test_each_shape_plans_emits_and_writes_the_three_files_intact(self):
        for mode, shape in SHAPES:
            with self.subTest(mode=mode, shape=shape):
                axi = self.init_with(f"proj-{mode.replace(':', '')}-{shape.split(':')[0]}",
                                     mode=mode, repo_shape=shape)
                subs = SUBS if shape.startswith("monorepo:") else ()
                self.assert_rendered(axi, ["python"], [], subs)

    def test_each_target_set_renders_its_workflow(self):
        for index, (value, targets) in enumerate(TARGET_VALUES):
            with self.subTest(release_targets=value):
                axi = self.init_with(f"proj-targets-{index}", release_targets=value)
                self.assertEqual((axi.get("registry") or {}).get("RELEASE_TARGETS"),
                                 ",".join(targets), "precondition: the canonical value recorded")
                self.assert_rendered(axi, ["python"], targets)

    def test_arduino_with_github_assets_renders_their_jobs(self):
        axi = self.init_with("proj-arduino", release_targets="github-assets", stacks="arduino")
        self.assert_rendered(axi, ["arduino"], ["github-assets"])
        path = self.target / RENDERED_FILES[0]
        self.assertTrue(path.is_file(), f"§S5: {RENDERED_FILES[0]} is written")
        text = path.read_text(encoding="utf-8")
        self.assertIn("\n  test-arduino:\n", text, "§S5: the arduino test job is rendered")
        self.assertIn("\n  publish-github-assets:\n", text, "§S5: the github-assets publish job")
        self.assertNotIn("\n  test-python:\n", text, "§S5: only the project's stacks get a job")

    def test_crates_and_maven_central_render_their_publish_jobs(self):
        # CR-MDB-071 §S1/§S3 wiring: init renders the new targets beside their stacks' tests.
        axi = self.init_with("proj-crates-maven", release_targets="maven-central:b,crates:a",
                             stacks="rust,java")
        self.assertEqual((axi.get("registry") or {}).get("RELEASE_TARGETS"),
                         "crates:a,maven-central:b", "§S1: the canonical value recorded")
        self.assert_rendered(axi, ["rust", "java"], ["crates:a", "maven-central:b"])
        text = (self.target / RENDERED_FILES[0]).read_text(encoding="utf-8")
        for job in ("test-rust", "test-java", "publish-crates", "publish-maven-central"):
            self.assertEqual(text.count(f"\n  {job}:\n"), 1, f"§S3: the {job} job, once")
        self.assertIn('check "$TAG" crates:a maven-central:b', text,
                      "§S3: create-release checks both version sources")

    def test_a_multi_stack_project_renders_one_workflow_for_its_stacks(self):
        axi = self.init_with("proj-multi-stack", release_targets="pypi", stacks="python,bun")
        self.assert_rendered(axi, ["python", "bun"], ["pypi"])


class InitPrerendersReleaseFilesTest(_ReleaseInitCase):
    """§S5 — the three files are rendered in validation, before the first write."""

    def setUp(self):
        super().setUp()
        # The sandbox's install.toml names <modelb_home>/no-asset-root-here as its asset root:
        # a workflows-src/ there is the one init resolves (scaffold._workflow_sources).
        broken = self.modelb_home / "no-asset-root-here" / "workflows-src"
        shutil.copytree(SOURCE, broken, ignore=shutil.ignore_patterns("__pycache__"))
        (broken / "release" / "header.yml").unlink()

    def test_a_render_failure_is_refused_before_the_first_write_dry_run_included(self):
        for dry_run in (False, True):
            with self.subTest(dry_run=dry_run):
                target = self.root / f"proj-broken-{dry_run}"
                rc, axi, err = self.run_init(target, dry_run=dry_run)
                self.assertEqual((rc, axi.get("ok")), (2, False),
                                 f"§S5: a render failure is refused; stderr={err!r}")
                self.assertTrue([w for w in axi.get("warnings") or [] if "header.yml" in w],
                                f"§S5: the refusal names the missing part; {axi!r}")
                self.assertFalse(target.exists(), "§S5: nothing is written")

    def test_an_invalid_release_targets_value_writes_nothing(self):
        # Regression pin: the registry already validates the value before any write (§S1); it
        # fails the moment init writes the project before validating --release-targets.
        # MIGRATED at CR-MDB-071 (§S1): the invalid value is the unknown name cargo (was: crates).
        target = self.root / "proj-invalid"
        rc, axi, err = self.run_init(target, release_targets="cargo")
        self.assertEqual((rc, axi.get("ok")), (2, False), f"stderr={err!r}")
        self.assertTrue([w for w in axi.get("warnings") or [] if "cargo" in w], axi)
        self.assertFalse(target.exists(), "§S5: nothing is written")


class InitReleaseSetupTasksTest(_ReleaseInitCase):
    """§S5 — the setup tasks, per stack and target, in the envelope and the Setup section."""

    def tasks_of(self, name: str, **fields) -> tuple[list[str], list[str]]:
        """``(release_setup, the Setup section's lines)`` of an ``init`` run."""
        axi = self.init_with(name, **fields)
        tasks = axi.get("release_setup")
        if not isinstance(tasks, list) or not all(isinstance(t, str) for t in tasks):
            self.fail(f"§S5: the init envelope carries a `release_setup` list of tasks; got {axi!r}")
        body = _setup.setup_body(self.text("AGENTS.md"))
        self.assertTrue(body, "precondition: the root AGENTS.md carries a ## Setup section")
        return tasks, body.splitlines()

    def assert_tasks(self, tasks: list[str], lines: list[str], stacks: list[str],
                     targets: list[str]) -> None:
        names = target_names(targets)
        attributed: set[int] = set()
        # MIGRATED at CR-MDB-071 (§S4): the targets' tasks are attributed first, then each
        # stack's among the rest, since the maven-central task names `mvnw` as the Maven stacks'
        # task does (was: the stacks first, over every task); the target tasks follow in
        # canonical order.
        order = []
        for name, token in TARGET_TOKENS.items():
            hits = [i for i, task in enumerate(tasks) if token in task]
            if name in names:
                self.assertEqual(len(hits), 1,
                                 f"§S5: one task for the {name} target; tasks={tasks!r}")
                attributed.update(hits)
                order.append(hits[0])
                for need in TARGET_NEEDS[name]:
                    self.assertRegex(tasks[hits[0]], need, f"§S5: the {name} task names it")
            else:
                self.assertEqual(hits, [], f"§S5: no {name} task; tasks={tasks!r}")
        self.assertEqual(order, sorted(order), f"the target tasks in canonical order; {tasks!r}")
        for stack, token in STACK_TOKENS.items():
            hits = [i for i, task in enumerate(tasks) if token in task and i not in attributed]
            if stack in stacks:
                self.assertEqual(len(hits), 1,
                                 f"§S5: one task names {token!r} for {stack}; tasks={tasks!r}")
                attributed.update(hits)
                if stack == "arduino":
                    self.assertRegex(tasks[hits[0]], r"(?i)\bexecutable\b",
                                     "§S5: an executable .github/scripts/ci-test")
            elif not any(token == STACK_TOKENS[s] for s in stacks):
                self.assertEqual(hits, [], f"§S5: no {stack} task; tasks={tasks!r}")
        rest = [task for i, task in enumerate(tasks) if i not in attributed]
        self.assertLessEqual(len(rest), 1, f"§S5: nothing else but a RELEASE_PAT task; {rest!r}")
        for task in rest:
            self.assertIn(RELEASE_PAT, task, f"§S5: an unattributed task; {task!r}")
        for task in tasks:
            self.assertEqual(lines.count(f"- [ ] {task}"), 1,
                             f"§S5: {task!r} is one unchecked line of the Setup section; "
                             f"Setup={lines!r}")

    def test_each_stack_alone_carries_its_task(self):
        for stack in STACK_TOKENS:
            with self.subTest(stack=stack):
                tasks, lines = self.tasks_of(f"proj-{stack}", stacks=stack)
                self.assert_tasks(tasks, lines, [stack], [])

    def test_each_target_carries_its_environment_secret_and_publisher_task(self):
        for index, (value, targets) in enumerate(TARGET_VALUES):
            with self.subTest(release_targets=value):
                tasks, lines = self.tasks_of(f"proj-target-{index}", release_targets=value)
                self.assert_tasks(tasks, lines, ["python"], targets)

    def test_arduino_with_github_assets_names_both_executable_scripts(self):
        tasks, lines = self.tasks_of("proj-arduino-assets", stacks="arduino",
                                     release_targets="github-assets")
        self.assert_tasks(tasks, lines, ["arduino"], ["github-assets"])

    def test_a_multi_stack_project_carries_one_task_per_stack(self):
        tasks, lines = self.tasks_of("proj-python-bun-rust", stacks="python,bun,rust",
                                     release_targets="pypi,npm")
        self.assert_tasks(tasks, lines, ["python", "bun", "rust"], ["pypi", "npm"])

    def test_each_shape_carries_the_tasks_in_the_root_agents_md_only(self):
        for mode, shape in SHAPES:
            with self.subTest(mode=mode, shape=shape):
                tasks, lines = self.tasks_of(
                    f"proj-shape-{mode.replace(':', '')}-{shape.split(':')[0]}", mode=mode,
                    repo_shape=shape, release_targets="pypi")
                self.assert_tasks(tasks, lines, ["python"], ["pypi"])
                if shape.startswith("monorepo:"):
                    for sub in SUBS:
                        sub_text = self.text(f"{sub}/AGENTS.md")
                        self.assertEqual([t for t in tasks if t in sub_text], [],
                                         f"§S5: no release task in {sub}/AGENTS.md")


class InitForceManagedHelpTest(unittest.TestCase):
    """§S5 — ``init --force-managed``'s help names the workflow files beside the policy."""

    def test_the_help_names_the_release_workflow_files_beside_the_permission_policy(self):
        action = next((a for a in cli_subparser("init")._actions
                       if "--force-managed" in a.option_strings), None)
        if action is None:
            self.fail("init accepts --force-managed")
        text = " ".join((action.help or "").split()).lower()
        self.assertIn("permission policy", text, f"§S5: the policy stays named; help={text!r}")
        self.assertRegex(text, r"release[- ]workflow",
                         f"§S5: the help names the release workflow files; help={text!r}")


if __name__ == "__main__":
    unittest.main()
