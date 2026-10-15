"""``modelb-axi release-check`` reports a project's release readiness (CR-MDB-071 §S5).

Contract: ``docs/changes/CR-MDB-071-crates-maven-targets-and-readiness.md`` §S5 and its acceptance
criterion: in sandbox projects, with a stub ``gh`` on ``PATH`` (never the real ``gh``) and a stub
origin — every local item ready and missing (the stale render and a target with no test job
included); the three URL forms parsed, a non-GitHub remote and no remote ``unknown``; each GitHub
item ready and missing, and ``unknown`` for no ``gh``, ``gh`` exit 1, a 403 on the secrets list and
unparseable output; the policy semantics; the registry checklist; the envelope fields and counts;
exit codes 0, 1 and 2; nothing written; only the three subprocesses, ``gh`` with ``--method GET``.

Class map:

- ``ReleaseCheckVerbTest`` — the subcommand, ``_add_release_check_parser`` and ``main``'s dispatch
  to ``scaffold.run_release_check``.
- ``ReleaseCheckRefusalTest`` — exit 2 with an ``ok: false`` envelope and nothing written: no
  ``.env`` in the current directory, ``PROJECT_STACKS`` or ``RELEASE_TARGETS`` absent or invalid; an
  empty ``RELEASE_TARGETS`` (no target) is not refused.
- ``ReleaseCheckEnvelopeTest`` — a ready project: exit 0, the envelope's fields, each item's four
  fields, the areas, the states and the counts; a project missing something exits 1 with counts
  that still tally.
- ``ReleaseCheckRenderedFilesTest`` — each rendered file ready when it equals ``workflows.render``;
  a stale render and an absent file missing, naming ``modelb-axi release-workflow``; a
  hand-modified file ready with a note.
- ``ReleaseCheckVersionTest`` — each versioned target's version read by the shipped script from the
  target's ``dir``; missing with the script's own line otherwise.
- ``ReleaseCheckPrerequisiteTest`` — each stack's and target's prerequisite missing alone, an
  executable one present but not executable.
- ``ReleaseCheckNoTestJobTest`` — ``crates`` without the ``rust`` stack and ``maven-central`` without
  ``java`` or ``quarkus`` missing; with the stack, ready.
- ``ReleaseCheckChangelogTest`` — ``CHANGELOG.md`` absent missing; no ``[Unreleased]`` a note.
- ``ReleaseCheckOriginTest`` — the three URL forms with and without ``.git``; another host and no
  remote make every GitHub item ``unknown`` and run no ``gh``.
- ``ReleaseCheckGhTest`` — the argv (``api --method GET --paginate <path>``) and the three paths;
  no ``gh``, ``gh`` exit 1, a 403 on the secrets list and unparseable output each ``unknown``.
- ``ReleaseCheckEnvironmentPolicyTest`` — each environment present or absent; the policy semantics
  (null, ``protected_branches``, a tag policy) for a publish environment; ``testpypi`` admitting
  ``release/**`` and ``hotfix/**``.
- ``ReleaseCheckSecretsTest`` — each secret the rendered jobs name; ``NPM_TOKEN`` and
  ``CARGO_REGISTRY_TOKEN`` ``unknown`` when absent; organisation and environment secrets not read.
- ``ReleaseCheckRegistryTest`` — each target's publisher ``unknown``, its detail naming the fields.
- ``ReleaseCheckReadOnlyTest`` — the sandbox byte for byte unchanged; only the three subprocesses.
- ``ReleaseCheckCliEntryTest`` — ``python -m modelb_axi release-check`` in a sandbox project.

Isolation: every project is built by hand under a ``mkdtemp`` sandbox (``.env``, the files
``workflows.render`` returns, the version sources, the prerequisites, ``CHANGELOG.md``, a ``git
init`` with the origin under test). The verb runs in-process through ``cli.main`` from the project
directory, with ``os.environ`` replaced by a sandbox environment whose ``PATH`` is ONE sandbox
``bin`` directory holding a ``git`` and a ``python3`` that exec the real ones, and the ``gh`` stub
(or no ``gh``) — so the stub always wins and a real ``gh`` is never reachable, on any machine.
``subprocess.Popen`` is wrapped to record every argv the verb starts. The stub ``gh`` logs its
argv and answers from a fixture file keyed by the API path. Area names are the spec's three
headings: ``local``, ``github``, ``registry``.

Stdlib only.
"""

import contextlib
import io
import json
import os
import re
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path, PurePosixPath
from typing import NamedTuple
from unittest import mock

from modelb_axi import cli, scaffold, workflows
from tests._helpers import decode_axi, write_executable
from tests.pi_capability_sandbox import AGENT_DIR_ENV

REPO_ROOT = Path(__file__).resolve().parent.parent
VERB = "release-check"
#: §S5 — the four fields of every item, the three areas and the three states.
ITEM_FIELDS = ("area", "item", "state", "detail")
AREAS = ("local", "github", "registry")
STATES = ("ready", "missing", "unknown")
#: §S5 — the envelope's fields beside ``verb`` and ``ok``.
ENVELOPE_FIELDS = ("items", "ready", "missing", "unknown", "warnings")
#: The command a stale or absent rendered file's detail names.
RERENDER = "modelb-axi release-workflow"
RENDERED = (workflows.RELEASE_YML, workflows.STAMP_SCRIPT, workflows.SECTION_SCRIPT)

#: The repository every GitHub origin below names, and its API prefix.
REPOS = "repos/acme/widget"
#: §S5 — the three origin URL forms, each with and without ``.git``.
GITHUB_ORIGINS = (
    "https://github.com/acme/widget",
    "https://github.com/acme/widget.git",
    "git@github.com:acme/widget",
    "git@github.com:acme/widget.git",
    "ssh://git@github.com/acme/widget",
    "ssh://git@github.com/acme/widget.git",
)
#: §S5 — origins on another host: every GitHub item ``unknown``.
OTHER_HOST_ORIGINS = (
    "https://gitlab.com/acme/widget.git",
    "git@gitlab.com:acme/widget.git",
    "ssh://git@bitbucket.org/acme/widget.git",
)

VERSION = "1.2.3"
#: A version-tag pattern a tag policy carries (§S5: shown in the detail, not evaluated).
TAG_PATTERN = "[0-9]*.[0-9]*.[0-9]*"
#: Each target's version source, by name: its file under the target's dir and its text.
VERSION_SOURCES = {
    "pypi": ("pyproject.toml", f'[project]\nname = "widget"\nversion = "{VERSION}"\n'),
    "npm": ("package.json", f'{{\n  "name": "widget",\n  "version": "{VERSION}"\n}}\n'),
    "crates": ("Cargo.toml", f'[package]\nname = "widget"\nversion = "{VERSION}"\n'),
    "maven-central": ("pom.xml", (
        "<project>\n  <modelVersion>4.0.0</modelVersion>\n  <groupId>io.acme</groupId>\n"
        f"  <artifactId>widget</artifactId>\n  <version>{VERSION}</version>\n</project>\n")),
}
#: §S5 — each stack's prerequisite and each target's, by project-relative path.
STACK_PREREQUISITES = {
    "python": "tests/__init__.py",
    "bun": "bun.lock",
    "rust": "Cargo.lock",
    "quarkus": "mvnw",
    "java": "mvnw",
    "arduino": ".github/scripts/ci-test",
}
TARGET_PREREQUISITES = {"github-assets": ".github/scripts/build-assets", "maven-central": "mvnw"}
#: The prerequisites that must be executable.
EXECUTABLES = ("mvnw", ".github/scripts/ci-test", ".github/scripts/build-assets")
#: Each target's GitHub environments (the rendered jobs').
TARGET_ENVIRONMENTS = {
    "pypi": ("pypi", "testpypi"),
    "npm": ("npm",),
    "crates": ("crates",),
    "maven-central": ("maven-central",),
    "github-assets": (),
}
ALL_ENVIRONMENTS = ("testpypi", "pypi", "npm", "crates", "maven-central")
#: §S5 — absent, these are ``unknown`` (a trusted publisher replaces them).
FIRST_PUBLISH_TOKENS = ("NPM_TOKEN", "CARGO_REGISTRY_TOKEN")
ALL_SECRETS = ("RELEASE_PAT", "NPM_TOKEN", "CARGO_REGISTRY_TOKEN", "MAVEN_CENTRAL_USERNAME",
               "MAVEN_CENTRAL_PASSWORD", "MAVEN_GPG_PRIVATE_KEY", "MAVEN_GPG_PASSPHRASE")

#: A project carrying every stack the release workflow tests and all five targets.
FULL_STACKS = ("python", "bun", "rust", "java", "arduino")
FULL_TARGETS = ("pypi", "npm:pkg", "crates", "maven-central", "github-assets")

CHANGELOG = "# Changelog\n\n## [Unreleased]\n\n## [1.2.2] - 2026-01-01\n\n- Earlier.\n"
CHANGELOG_NO_UNRELEASED = "# Changelog\n\n## [1.2.2] - 2026-01-01\n\n- Earlier.\n"

#: A deployment-branch-policy shape (§S5's three) or an absent environment.
NULL, PROTECTED, ABSENT = "null", "protected", "absent"

def branch(name: str) -> dict:
    return {"id": 1, "name": name, "type": "branch"}

def tag(name: str) -> dict:
    return {"id": 2, "name": name, "type": "tag"}

#: The environments of a ready repository: ``testpypi`` admits the release and hotfix branches,
#: ``pypi`` admits the version tags through a tag policy, the others carry no policy.
READY_POLICIES = {
    "testpypi": [branch("release/**"), branch("hotfix/**")],
    "pypi": [tag(TAG_PATTERN)],
    "npm": NULL,
    "crates": NULL,
    "maven-central": NULL,
}

#: An answer of the ``gh`` stub: stdout, stderr and the exit status.
def answer(stdout: str = "", stderr: str = "", status: int = 0) -> dict:
    return {"stdout": stdout, "stderr": stderr, "exit": status}

UNAUTHENTICATED = answer(stderr="To get started with GitHub CLI, please run:  gh auth login\n",
                         status=1)
FORBIDDEN = answer(stderr="gh: Resource not accessible by integration (HTTP 403)\n", status=1)
NOT_FOUND = answer(stderr="gh: Not Found (HTTP 404)\n", status=1)
UNPARSEABLE = answer(stdout="<html><body>Service Unavailable</body></html>\n")

def github_answers(policies: dict | None = None, secrets=ALL_SECRETS) -> dict:
    """The stub's answers, keyed by API path: the environments list (each environment's
    ``deployment_branch_policy`` from ``policies``: ``NULL``, ``PROTECTED``, a list of custom
    policies, or ``ABSENT``), each environment's ``deployment-branch-policies`` and the secrets."""
    shapes = dict(READY_POLICIES)
    shapes.update(policies or {})
    environments, answers = [], {}
    for index, name in enumerate(ALL_ENVIRONMENTS, start=1):
        shape = shapes[name]
        if shape == ABSENT:
            continue
        if shape == NULL:
            policy, listed = None, []
        elif shape == PROTECTED:
            policy, listed = {"protected_branches": True, "custom_branch_policies": False}, []
        else:
            policy, listed = {"protected_branches": False, "custom_branch_policies": True}, shape
        environments.append({"id": index, "name": name, "deployment_branch_policy": policy,
                             "protection_rules": []})
        answers[f"{REPOS}/environments/{name}/deployment-branch-policies"] = answer(json.dumps(
            {"total_count": len(listed), "branch_policies": listed}))
    answers[f"{REPOS}/environments"] = answer(json.dumps(
        {"total_count": len(environments), "environments": environments}))
    answers[f"{REPOS}/actions/secrets"] = answer(json.dumps(
        {"total_count": len(secrets), "secrets": [
            {"name": s, "created_at": "2026-01-01T00:00:00Z",
             "updated_at": "2026-01-01T00:00:00Z"} for s in secrets]}))
    return answers

def gh_stub_source(log: Path, fixture: Path) -> str:
    """A ``gh`` that appends its argv (JSON) to ``log`` and answers from ``fixture`` (API path ->
    answer; ``*`` the default; else a 404)."""
    return "\n".join((
        f"#!{sys.executable}",
        "import json",
        "import sys",
        f"with open({str(log)!r}, 'a', encoding='utf-8') as handle:",
        "    handle.write(json.dumps(sys.argv[1:]) + '\\n')",
        f"with open({str(fixture)!r}, encoding='utf-8') as handle:",
        "    answers = json.load(handle)",
        "path = sys.argv[-1] if len(sys.argv) > 1 else ''",
        f"reply = answers.get(path, answers.get('*', {NOT_FOUND!r}))",
        "sys.stdout.write(reply['stdout'])",
        "sys.stderr.write(reply['stderr'])",
        "sys.exit(reply['exit'])",
        "",
    ))

def exec_wrapper(real: str) -> str:
    return f"#!/bin/sh\nexec {shlex.quote(real)} \"$@\"\n"

def whole_word(needle: str, text: str) -> bool:
    """``needle`` in ``text`` as a whole name (``pypi`` is not found in ``testpypi``)."""
    return re.search(rf"(?<![\w./-]){re.escape(needle)}(?![\w/-])", text) is not None

def secrets_named(release_yml: str) -> list[str]:
    """Every repository secret a rendered ``release.yml`` names."""
    return sorted(set(re.findall(r"secrets\.([A-Z][A-Z0-9_]*)", release_yml)))

class Run(NamedTuple):
    rc: int
    axi: dict
    stderr: str
    #: Every argv the verb started, as strings.
    calls: list
    #: Every argv the ``gh`` stub received (without ``gh``).
    gh: list

# ------------------------------------------------------------------ the sandbox ----

class _CheckCase(unittest.TestCase):
    """A sandbox: a home, a ``MODELB_HOME``, a ``bin`` holding ``git``, ``python3`` and the ``gh``
    stub, and projects built by :meth:`make_project`."""

    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="mdb-release-check-"))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.home = self.root / "home"
        self.modelb_home = self.root / "modelb-home"
        self.xdg = self.root / "xdg"
        self.agent_dir = self.root / "pi-agent"
        self.stub = self.root / "stub"
        self.bin = self.stub / "bin"
        for directory in (self.home, self.modelb_home, self.xdg, self.agent_dir, self.bin):
            directory.mkdir(parents=True)
        real_git = shutil.which("git")
        self.assertIsNotNone(real_git, "git runs the origin fixture")
        write_executable(self.bin, "git", exec_wrapper(str(real_git)))
        write_executable(self.bin, "python3", exec_wrapper(sys.executable))
        self.gh_log = self.stub / "gh.log"
        self.gh_fixture = self.stub / "gh.json"
        self.set_github(github_answers())
        self.project = self.root / "proj"
        self.serial = 0

    # -------------------------------------------------------------- fixtures ----

    def env(self) -> dict:
        env = {"PATH": str(self.bin), "HOME": str(self.home),
               "MODELB_HOME": str(self.modelb_home), "XDG_DATA_HOME": str(self.xdg),
               AGENT_DIR_ENV: str(self.agent_dir), "GIT_CONFIG_NOSYSTEM": "1"}
        for name in ("HOME", "MODELB_HOME", "XDG_DATA_HOME", AGENT_DIR_ENV):
            self.assertTrue(env[name].startswith(str(self.root)), f"sandbox guard: {name}")
        return env

    def set_github(self, answers: dict) -> None:
        self.gh_fixture.write_text(json.dumps(answers), encoding="utf-8")

    def git(self, *args: str, cwd: Path) -> None:
        subprocess.run([str(self.bin / "git"), *args], cwd=str(cwd), env=self.env(),
                       check=True, capture_output=True, text=True, timeout=60,
                       stdin=subprocess.DEVNULL)

    def make_project(self, stacks=("python",), targets=("pypi",), *,
                     origin: str | None = GITHUB_ORIGINS[1], changelog: str | None = CHANGELOG,
                     rendered_for=None) -> Path:
        """A fresh project at :attr:`project`: ``.env`` recording ``stacks`` and ``targets``, the
        files ``workflows.render`` returns for them (or for ``rendered_for``'s targets), each
        versioned target's source reading :data:`VERSION`, each prerequisite, ``CHANGELOG.md`` and
        a git repository with ``origin`` (``None``: no remote). Every item ready."""
        self.serial += 1
        self.project = root = self.root / f"proj-{self.serial}"
        root.mkdir()
        (root / ".env").write_text(
            "PROJECT_NAME=Widget\n"
            f"PROJECT_STACKS={','.join(stacks)}\n"
            f"RELEASE_TARGETS={','.join(targets)}\n", encoding="utf-8")
        texts = workflows.render(list(stacks),
                                 list(targets if rendered_for is None else rendered_for),
                                 scaffold._workflow_sources(self.modelb_home))
        for rel, text in texts.items():
            self.write(rel, text)
        for target in targets:
            name, directory = workflows.parse_target(target)
            if name in VERSION_SOURCES:
                filename, text = VERSION_SOURCES[name]
                self.write(str(PurePosixPath(directory) / filename), text)
            if name in TARGET_PREREQUISITES:
                self.write(TARGET_PREREQUISITES[name], "#!/bin/sh\nexit 0\n")
        for stack in stacks:
            self.write(STACK_PREREQUISITES[stack], "#!/bin/sh\nexit 0\n")
        for rel in EXECUTABLES:
            if (root / rel).is_file():
                (root / rel).chmod(0o755)
        if changelog is not None:
            self.write("CHANGELOG.md", changelog)
        self.git("init", "-q", ".", cwd=root)
        if origin is not None:
            self.git("remote", "add", "origin", origin, cwd=root)
        return root

    def write(self, rel: str, text: str) -> Path:
        path = self.project / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def set_env_key(self, key: str, value: str | None) -> None:
        env_path = self.project / ".env"
        lines = [ln for ln in env_path.read_text(encoding="utf-8").splitlines(keepends=True)
                 if not ln.startswith(key + "=")]
        if value is not None:
            lines.append(f"{key}={value}\n")
        env_path.write_text("".join(lines), encoding="utf-8")

    def tree_state(self) -> dict:
        """Every path under the sandbox (the stub's own directory aside): a file's bytes and mode,
        a directory's mode."""
        state = {}
        for path in sorted(self.root.rglob("*")):
            rel = path.relative_to(self.root)
            if rel.parts[0] == "stub":
                continue
            mode = stat.S_IMODE(path.lstat().st_mode)
            state[rel.as_posix()] = (mode, path.read_bytes() if path.is_file() else None)
        return state

    # -------------------------------------------------------------- the run ----

    def check(self, *, cwd: Path | None = None, gh: bool = True) -> Run:
        """``modelb-axi --modelb-home <home> release-check`` through ``cli.main`` from ``cwd``
        (default: the project), ``os.environ`` the sandbox's, every started argv recorded."""
        stub = self.bin / "gh"
        if gh:
            write_executable(self.bin, "gh", gh_stub_source(self.gh_log, self.gh_fixture))
        else:
            stub.unlink(missing_ok=True)
        self.gh_log.unlink(missing_ok=True)
        calls: list = []
        real_popen = subprocess.Popen

        class _Recording(real_popen):
            def __init__(self, args, *rest, **kwargs):
                calls.append([str(a) for a in args] if isinstance(args, (list, tuple))
                             else [str(args)])
                super().__init__(args, *rest, **kwargs)

        out, err = io.StringIO(), io.StringIO()
        with contextlib.ExitStack() as stack:
            stack.enter_context(mock.patch.dict(os.environ, self.env(), clear=True))
            stack.enter_context(mock.patch.object(subprocess, "Popen", _Recording))
            stack.enter_context(contextlib.chdir(cwd or self.project))
            stack.enter_context(contextlib.redirect_stdout(out))
            stack.enter_context(contextlib.redirect_stderr(err))
            try:
                rc = cli.main(["--modelb-home", str(self.modelb_home), VERB])
            except SystemExit as exc:
                rc = exc.code if isinstance(exc.code, int) else 1
        gh_calls = ([json.loads(line) for line in
                     self.gh_log.read_text(encoding="utf-8").splitlines()]
                    if self.gh_log.is_file() else [])
        return Run(rc, decode_axi(out.getvalue()), err.getvalue(), calls, gh_calls)

    # -------------------------------------------------------------- readers ----

    @staticmethod
    def items(run: Run) -> list:
        return list(run.axi.get("items") or [])

    def area(self, run: Run, area: str) -> list:
        return [i for i in self.items(run) if i.get("area") == area]

    def named(self, run: Run, area: str, needle: str) -> list:
        """The items of ``area`` whose ``item`` names ``needle`` as a whole name."""
        return [i for i in self.area(run, area) if whole_word(needle, str(i.get("item", "")))]

    def in_state(self, run: Run, state: str) -> list:
        return [i for i in self.items(run) if i.get("state") == state]

    @staticmethod
    def text(item: dict) -> str:
        return f"{item.get('item', '')} {item.get('detail', '')}"

    def assert_ran(self, run: Run, rc: int) -> None:
        self.assertEqual((run.rc, run.axi.get("verb")), (rc, VERB),
                         f"§S5: release-check exits {rc}; stderr={run.stderr!r}; axi={run.axi!r}")

    def assert_ready(self, run: Run) -> None:
        self.assert_ran(run, 0)
        self.assertEqual((run.axi.get("ok"), run.axi.get("missing")), (True, 0),
                         f"§S5: nothing missing; missing={self.in_state(run, 'missing')!r}")

    def assert_only_missing(self, run: Run, *needles: str) -> dict:
        """Exit 1 with exactly one missing item, which names every one of ``needles``."""
        self.assert_ran(run, 1)
        missing = self.in_state(run, "missing")
        self.assertEqual(len(missing), 1, f"§S5: exactly one item missing; got {missing!r}")
        for needle in needles:
            self.assertIn(needle, self.text(missing[0]),
                          f"§S5: the missing item names {needle!r}; got {missing[0]!r}")
        self.assertEqual(run.axi.get("missing"), 1, "§S5: the missing count")
        return missing[0]

    def assert_refused(self, run: Run, *named: str) -> None:
        self.assertEqual((run.rc, run.axi.get("verb"), run.axi.get("ok")), (2, VERB, False),
                         f"§S5: a refusal exits 2 with an ok:false envelope; "
                         f"stderr={run.stderr!r}; axi={run.axi!r}")
        warnings = run.axi.get("warnings") or []
        for needle in named:
            self.assertTrue([w for w in warnings if needle in w],
                            f"§S5: the refusal names {needle!r}; warnings={warnings!r}")

# ------------------------------------------------------------------ the verb ----

class ReleaseCheckVerbTest(unittest.TestCase):
    """§S5 — ``_add_release_check_parser``, ``main``'s dispatch, ``scaffold.run_release_check``."""

    def test_release_check_is_a_subcommand_beside_release_workflow(self):
        parser = cli._build_parser()
        sub = next(a for a in parser._actions if isinstance(a, cli.argparse._SubParsersAction))
        self.assertIn(VERB, sub.choices, f"§S5: the subcommands are {sorted(sub.choices)}")
        self.assertIn("release-workflow", sub.choices)

    def test_cli_declares_the_parser_and_main_dispatches_to_run_release_check(self):
        source = (REPO_ROOT / "modelb_axi" / "cli.py").read_text(encoding="utf-8")
        self.assertRegex(source, r"(?m)^def _add_release_check_parser\(",
                         "§S5: the verb's parser is `_add_release_check_parser` in cli.py")
        main = source[source.index("\ndef main("):]
        self.assertIn("run_release_check(", main, "§S5: main dispatches the verb")
        self.assertTrue(callable(getattr(scaffold, "run_release_check", None)),
                        "§S5: the verb is run by scaffold.run_release_check")

# ------------------------------------------------------------------ refusals ----

class ReleaseCheckRefusalTest(_CheckCase):
    """§S5 — where it runs and what it reads: exit 2, ``ok: false``, nothing written."""

    def test_a_directory_without_env_is_refused_naming_where_to_run_it(self):
        self.make_project()
        sub = self.project / "docs"
        sub.mkdir()
        before = self.tree_state()
        run = self.check(cwd=sub)
        self.assert_refused(run, ".env", "release-check")
        self.assertEqual(run.gh, [], "§S5: a refusal asks GitHub nothing")
        self.assertEqual(self.tree_state(), before, "§S5: it never writes")

    def test_an_absent_or_invalid_project_stacks_is_refused(self):
        for value, needle in ((None, "PROJECT_STACKS"), ("cobol", "cobol")):
            with self.subTest(value=value):
                self.make_project()
                self.set_env_key("PROJECT_STACKS", value)
                before = self.tree_state()
                run = self.check()
                self.assert_refused(run, needle)
                self.assertEqual(self.tree_state(), before, "§S5: it never writes")

    def test_an_absent_or_invalid_release_targets_is_refused(self):
        for value, needles in ((None, ("RELEASE_TARGETS",)),
                               ("cargo", ("RELEASE_TARGETS", "cargo")),
                               ("pypi,pypi", ("RELEASE_TARGETS", "pypi"))):
            with self.subTest(value=value):
                self.make_project()
                self.set_env_key("RELEASE_TARGETS", value)
                before = self.tree_state()
                run = self.check()
                self.assert_refused(run, *needles)
                self.assertEqual(self.tree_state(), before, "§S5: it never writes")

    def test_an_empty_release_targets_is_no_target_and_not_refused(self):
        self.make_project(targets=())
        run = self.check()
        self.assert_ready(run)
        self.assertEqual(self.area(run, "registry"), [],
                         "§S5: no target, no registry publisher to check")
        self.assertEqual([i.get("state") for i in self.named(run, "github", "RELEASE_PAT")],
                         ["ready"], "§S5: RELEASE_PAT is checked with no target")

# ------------------------------------------------------------------ the envelope ----

class ReleaseCheckEnvelopeTest(_CheckCase):
    """§S5 — one envelope: ``items`` (``area``, ``item``, ``state``, ``detail``) and the counts."""

    def assert_tally(self, run: Run) -> None:
        items = self.items(run)
        for item in items:
            self.assertEqual(sorted(item), sorted(ITEM_FIELDS),
                             f"§S5: each item carries exactly {ITEM_FIELDS}; got {item!r}")
            self.assertIn(item["area"], AREAS, item)
            self.assertIn(item["state"], STATES, item)
        for state in STATES:
            self.assertEqual(run.axi.get(state), len(self.in_state(run, state)),
                             f"§S5: the {state!r} count is the number of {state} items")
        self.assertEqual(sum(run.axi.get(s, 0) for s in STATES), len(items))

    def test_a_ready_project_exits_0_with_every_field_and_counts_that_tally(self):
        self.make_project(FULL_STACKS, FULL_TARGETS)
        run = self.check()
        self.assert_ready(run)
        self.assertEqual(sorted(f for f in ENVELOPE_FIELDS if f in run.axi),
                         sorted(ENVELOPE_FIELDS), f"§S5: the envelope's fields; got {run.axi!r}")
        self.assert_tally(run)
        self.assertEqual(sorted({i["area"] for i in self.items(run)}), sorted(AREAS),
                         "§S5: local, GitHub and registry items")
        registry = self.area(run, "registry")
        self.assertEqual(run.axi.get("unknown"), len(registry),
                         "§S5: in a ready project only the registry checklist is unknown")
        self.assertEqual(run.axi.get("ready"), len(self.items(run)) - len(registry))
        self.assertEqual(run.axi.get("warnings"), [])

    def test_a_project_missing_an_item_exits_1_with_counts_that_tally(self):
        self.make_project(FULL_STACKS, FULL_TARGETS, changelog=None)
        run = self.check()
        self.assert_only_missing(run, "CHANGELOG.md")
        self.assert_tally(run)

# ------------------------------------------------------------------ the local items ----

class ReleaseCheckRenderedFilesTest(_CheckCase):
    """§S5 — each rendered file against ``workflows.render`` for the current ``.env``."""

    def test_each_rendered_file_equal_to_the_render_is_ready(self):
        self.make_project()
        run = self.check()
        self.assert_ready(run)
        for rel in RENDERED:
            with self.subTest(file=rel):
                found = [i for i in self.area(run, "local") if rel in i.get("item", "")]
                self.assertEqual([i["state"] for i in found], ["ready"],
                                 f"§S5: one ready item for {rel}; got {found!r}")

    def test_a_stale_render_is_missing_and_names_release_workflow(self):
        self.make_project(targets=("pypi", "github-assets"), rendered_for=("pypi",))
        run = self.check()
        item = self.assert_only_missing(run, workflows.RELEASE_YML)
        self.assertIn(RERENDER, item["detail"], "§S5: run `modelb-axi release-workflow`")
        self.assertEqual(item["area"], "local")

    def test_an_absent_rendered_file_is_missing_and_names_release_workflow(self):
        self.make_project()
        (self.project / workflows.SECTION_SCRIPT).unlink()
        run = self.check()
        item = self.assert_only_missing(run, workflows.SECTION_SCRIPT)
        self.assertIn(RERENDER, item["detail"], "§S5: run `modelb-axi release-workflow`")

    def test_a_hand_modified_file_is_ready_with_a_note(self):
        self.make_project()
        path = self.project / workflows.RELEASE_YML
        path.write_text(path.read_text(encoding="utf-8") + "# a local tweak\n", encoding="utf-8")
        self.assertEqual(workflows.ownership_state(path.read_text(encoding="utf-8")),
                         "hand_modified", "fixture: the marker is kept, the digest is not")
        run = self.check()
        self.assert_ready(run)
        found = [i for i in self.area(run, "local") if workflows.RELEASE_YML in i.get("item", "")]
        self.assertEqual([i["state"] for i in found], ["ready"], f"§S5: got {found!r}")
        self.assertIn("hand", found[0]["detail"].lower(),
                      f"§S5: the note says it is hand-modified; got {found[0]!r}")

class ReleaseCheckVersionTest(_CheckCase):
    """§S5 — each versioned target's version, read by ``stamp_version.py read``."""

    def script_line(self, target: str) -> str:
        """The refusal line the project's own ``stamp_version.py read <target>`` prints."""
        result = subprocess.run(
            [sys.executable, workflows.STAMP_SCRIPT, "read", target], cwd=str(self.project),
            capture_output=True, text=True, timeout=60, stdin=subprocess.DEVNULL)
        self.assertEqual(result.returncode, 1, f"fixture: the script refuses; {result!r}")
        return result.stderr.strip()

    def test_each_versioned_target_read_from_its_dir_is_ready(self):
        self.make_project(FULL_STACKS, FULL_TARGETS)
        run = self.check()
        self.assert_ready(run)
        local = self.area(run, "local")
        for name in ("pypi", "npm", "crates", "maven-central"):
            with self.subTest(target=name):
                found = [i for i in local if whole_word(name, i.get("item", ""))]
                self.assertTrue(found, f"§S5: a local item for {name}'s version; got {local!r}")
                self.assertEqual({i["state"] for i in found}, {"ready"}, found)

    def test_an_unreadable_version_is_missing_with_the_scripts_line(self):
        cases = (
            ("pypi", "pyproject.toml", '[project]\nname = "widget"\n'),
            ("npm:pkg", "pkg/package.json", None),
            ("crates", "Cargo.toml", '[workspace]\nmembers = []\n'),
            ("maven-central", "pom.xml",
             "<project>\n  <parent>\n    <version>1.0.0</version>\n  </parent>\n</project>\n"),
        )
        stacks = {"pypi": ("python",), "npm:pkg": ("bun",), "crates": ("rust",),
                  "maven-central": ("java",)}
        for target, rel, broken in cases:
            with self.subTest(target=target):
                self.make_project(stacks[target], (target,))
                if broken is None:
                    (self.project / rel).unlink()
                else:
                    self.write(rel, broken)
                name, directory = workflows.parse_target(target)
                line = self.script_line(f"{name}:{directory}")
                item = self.assert_only_missing(run=self.check())
                self.assertIn(line, item["detail"], f"§S5: the script's line; got {item!r}")
                self.assertEqual(item["area"], "local")

class ReleaseCheckPrerequisiteTest(_CheckCase):
    """§S5 — each stack's and target's prerequisite."""

    def test_each_stack_prerequisite_absent_is_missing(self):
        for stack, rel in STACK_PREREQUISITES.items():
            with self.subTest(stack=stack):
                self.make_project((stack,), ())
                target = self.project / rel
                if stack == "python":
                    shutil.rmtree(target.parent)
                else:
                    target.unlink()
                self.assert_only_missing(self.check(), PurePosixPath(rel).name
                                         if stack != "python" else "tests")

    def test_the_build_assets_script_absent_is_missing(self):
        self.make_project(("python",), ("github-assets",))
        (self.project / TARGET_PREREQUISITES["github-assets"]).unlink()
        self.assert_only_missing(self.check(), "build-assets")

    def test_an_executable_prerequisite_present_but_not_executable_is_missing(self):
        for stacks, targets, rel in ((("arduino",), (), ".github/scripts/ci-test"),
                                     (("python",), ("github-assets",),
                                      ".github/scripts/build-assets")):
            with self.subTest(file=rel):
                self.make_project(stacks, targets)
                (self.project / rel).chmod(0o644)
                self.assert_only_missing(self.check(), PurePosixPath(rel).name)

    def test_every_prerequisite_present_is_ready(self):
        self.make_project(FULL_STACKS, FULL_TARGETS)
        self.assert_ready(self.check())

class ReleaseCheckNoTestJobTest(_CheckCase):
    """§S5 — a target no test job builds is missing."""

    def test_crates_without_the_rust_stack_is_missing(self):
        self.make_project(("python",), ("crates",))
        item = self.assert_only_missing(self.check(), "crates", "rust")
        self.assertEqual(item["area"], "local")

    def test_maven_central_without_java_or_quarkus_is_missing(self):
        self.make_project(("python",), ("maven-central",))
        item = self.assert_only_missing(self.check(), "maven-central")
        self.assertTrue("java" in item["detail"] or "quarkus" in item["detail"],
                        f"§S5: the detail names the stacks that build it; got {item!r}")

    def test_each_target_beside_a_stack_that_builds_it_is_ready(self):
        for stacks, targets in ((("rust",), ("crates",)), (("quarkus",), ("maven-central",)),
                                (("java",), ("maven-central",))):
            with self.subTest(stacks=stacks):
                self.make_project(stacks, targets)
                self.assert_ready(self.check())

class ReleaseCheckChangelogTest(_CheckCase):
    """§S5 — ``CHANGELOG.md``: missing when absent; no ``[Unreleased]`` is a note."""

    def test_an_absent_changelog_is_missing(self):
        self.make_project(changelog=None)
        item = self.assert_only_missing(self.check(), "CHANGELOG.md")
        self.assertEqual(item["area"], "local")

    def test_a_changelog_without_unreleased_is_ready_with_a_note(self):
        self.make_project(changelog=CHANGELOG_NO_UNRELEASED)
        run = self.check()
        self.assert_ready(run)
        found = [i for i in self.area(run, "local") if "CHANGELOG.md" in i.get("item", "")]
        self.assertEqual([i["state"] for i in found], ["ready"], f"§S5: got {found!r}")
        self.assertIn("Unreleased", found[0]["detail"], "§S5: the note names [Unreleased]")

    def test_a_changelog_with_unreleased_is_ready(self):
        self.make_project()
        run = self.check()
        self.assert_ready(run)
        found = [i for i in self.area(run, "local") if "CHANGELOG.md" in i.get("item", "")]
        self.assertEqual([i["state"] for i in found], ["ready"], f"§S5: got {found!r}")

# ------------------------------------------------------------------ the GitHub items ----

class ReleaseCheckOriginTest(_CheckCase):
    """§S5 — the repository from ``git remote get-url origin``."""

    def test_each_github_url_form_names_the_repository(self):
        for origin in GITHUB_ORIGINS:
            with self.subTest(origin=origin):
                self.make_project(origin=origin)
                run = self.check()
                self.assert_ready(run)
                paths = [argv[-1] for argv in run.gh]
                self.assertIn(f"{REPOS}/environments", paths, f"§S5: got {run.gh!r}")
                self.assertIn(f"{REPOS}/actions/secrets", paths, f"§S5: got {run.gh!r}")
                self.assertEqual([p for p in paths if not p.startswith(REPOS + "/")], [],
                                 "§S5: every path names acme/widget, without `.git`")
                self.assertEqual([i for i in self.area(run, "github")
                                  if i["state"] == "unknown"], [],
                                 "§S5: a parsed origin with gh answering leaves none unknown")

    def assert_every_github_item_unknown(self, run: Run) -> None:
        self.assert_ready(run)
        github = self.area(run, "github")
        self.assertTrue(self.named(run, "github", "RELEASE_PAT"),
                        f"§S5: the GitHub items are still listed; got {github!r}")
        self.assertTrue(self.named(run, "github", "pypi"), f"§S5: got {github!r}")
        self.assertEqual({i["state"] for i in github}, {"unknown"},
                         f"§S5: every GitHub item unknown; got {github!r}")
        self.assertEqual(run.gh, [], "§S5: with no repository, gh is not run")

    def test_another_host_makes_every_github_item_unknown(self):
        for origin in OTHER_HOST_ORIGINS:
            with self.subTest(origin=origin):
                self.make_project(origin=origin)
                self.assert_every_github_item_unknown(self.check())

    def test_no_remote_makes_every_github_item_unknown(self):
        self.make_project(origin=None)
        self.assert_every_github_item_unknown(self.check())

class ReleaseCheckGhTest(_CheckCase):
    """§S5 — ``gh api --method GET --paginate <path>``; each failure ``unknown`` with its error."""

    def test_gh_is_run_as_api_get_paginate_on_the_three_paths_only(self):
        self.make_project(FULL_STACKS, FULL_TARGETS)
        run = self.check()
        self.assert_ready(run)
        allowed = {f"{REPOS}/environments", f"{REPOS}/actions/secrets",
                   *(f"{REPOS}/environments/{e}/deployment-branch-policies"
                     for e in ALL_ENVIRONMENTS)}
        for argv in run.gh:
            self.assertEqual(argv[:4], ["api", "--method", "GET", "--paginate"],
                             f"§S5: the argv is `gh api --method GET --paginate <path>`; {argv!r}")
            self.assertEqual(len(argv), 5, f"§S5: one path and nothing else; {argv!r}")
            self.assertIn(argv[4], allowed, "§S5: the three endpoints only")
        paths = [argv[-1] for argv in run.gh]
        self.assertEqual(paths.count(f"{REPOS}/environments"), 1, paths)
        self.assertEqual(paths.count(f"{REPOS}/actions/secrets"), 1, paths)
        self.assertEqual(len(paths), len(set(paths)), f"§S5: each path asked once; {paths!r}")

    def env_and_secret_items(self, run: Run) -> tuple[list, list]:
        environments = [i for e in ("pypi", "testpypi") for i in self.named(run, "github", e)]
        return environments, self.named(run, "github", "RELEASE_PAT")

    def test_no_gh_makes_every_item_it_covers_unknown(self):
        self.make_project()
        run = self.check(gh=False)
        self.assert_ready(run)
        environments, secrets = self.env_and_secret_items(run)
        self.assertTrue(environments and secrets, f"§S5: got {self.items(run)!r}")
        for item in environments + secrets:
            self.assertEqual(item["state"], "unknown", f"§S5: no gh; got {item!r}")
            self.assertIn("gh", item["detail"], f"§S5: the detail says why; got {item!r}")

    def test_gh_exit_1_makes_every_item_it_covers_unknown_with_the_error(self):
        self.make_project()
        self.set_github({"*": UNAUTHENTICATED})
        run = self.check()
        self.assert_ready(run)
        environments, secrets = self.env_and_secret_items(run)
        self.assertTrue(environments and secrets, f"§S5: got {self.items(run)!r}")
        for item in environments + secrets:
            self.assertEqual(item["state"], "unknown", f"§S5: gh exit 1; got {item!r}")
            self.assertIn("gh auth login", item["detail"], f"§S5: the error; got {item!r}")

    def test_a_403_on_the_secrets_list_makes_only_the_secret_items_unknown(self):
        self.make_project()
        answers = github_answers()
        answers[f"{REPOS}/actions/secrets"] = FORBIDDEN
        self.set_github(answers)
        run = self.check()
        self.assert_ready(run)
        environments, secrets = self.env_and_secret_items(run)
        self.assertTrue(secrets, f"§S5: got {self.items(run)!r}")
        for item in secrets:
            self.assertEqual(item["state"], "unknown", f"§S5: a 403; got {item!r}")
            self.assertIn("HTTP 403", item["detail"], f"§S5: the error; got {item!r}")
        self.assertEqual({i["state"] for i in environments}, {"ready"},
                         f"§S5: the environments are still read; got {environments!r}")

    def test_unparseable_output_makes_the_items_it_covers_unknown(self):
        self.make_project()
        answers = github_answers()
        answers[f"{REPOS}/environments"] = UNPARSEABLE
        self.set_github(answers)
        run = self.check()
        self.assert_ready(run)
        environments, secrets = self.env_and_secret_items(run)
        self.assertTrue(environments, f"§S5: got {self.items(run)!r}")
        for item in environments:
            self.assertEqual(item["state"], "unknown", f"§S5: unparseable; got {item!r}")
            self.assertTrue(item["detail"].strip(), f"§S5: the error; got {item!r}")
        self.assertEqual({i["state"] for i in secrets}, {"ready"},
                         f"§S5: the secrets are still read; got {secrets!r}")

def two_pages(reply: dict, key: str, at: int, second: dict | None = None) -> dict:
    """VERIFY F2: ``reply`` (a one-page answer listing ``key``) as ``gh api --paginate`` prints
    two pages, two JSON documents one after the other: the entries before ``at``, then the rest
    (or ``second``, a document of another shape)."""
    page = json.loads(reply["stdout"])
    first = dict(page, **{key: page[key][:at]})
    last = second if second is not None else dict(page, **{key: page[key][at:]})
    return answer(json.dumps(first) + "\n" + json.dumps(last))

#: VERIFY F2 — a second page of another shape.
OTHER_SHAPE = {"x": 1}

class ReleaseCheckPaginatedTest(_CheckCase):
    """§S5 (VERIFY F2) — ``gh api --paginate`` prints one JSON document per page: every page
    is read; a page of another shape makes the items it covers ``unknown``, saying unparseable."""

    def run_paged(self, path: str, key: str, second: dict | None = None) -> Run:
        self.make_project(FULL_STACKS, FULL_TARGETS)
        answers = github_answers()
        answers[path] = two_pages(answers[path], key, 2, second)
        self.set_github(answers)
        return self.check()

    def by_name(self, run: Run, names) -> dict:
        """Each of ``names``' one GitHub item."""
        found = {name: self.named(run, "github", name) for name in names}
        for name, items in found.items():
            self.assertEqual(len(items), 1, f"§S5: one item for {name}; got {self.items(run)!r}")
        return {name: items[0] for name, items in found.items()}

    def assert_states(self, items: dict, state: str, detail: str | None = None) -> None:
        for name, item in items.items():
            self.assertEqual(item["state"], state, f"{name}: got {item!r}")
            if detail is not None:
                self.assertIn(detail, item["detail"], f"{name}: got {item!r}")

    def test_secrets_split_across_two_pages_are_every_one_ready(self):
        run = self.run_paged(f"{REPOS}/actions/secrets", "secrets")
        self.assert_ready(run)
        self.assert_states(self.by_name(run, ALL_SECRETS), "ready")

    def test_a_second_secrets_page_of_another_shape_makes_the_secrets_unknown(self):
        run = self.run_paged(f"{REPOS}/actions/secrets", "secrets", OTHER_SHAPE)
        self.assert_ready(run)
        self.assert_states(self.by_name(run, ALL_SECRETS), "unknown", "unparseable")
        self.assert_states(self.by_name(run, ALL_ENVIRONMENTS), "ready")

    def test_environments_split_across_two_pages_are_every_one_ready(self):
        run = self.run_paged(f"{REPOS}/environments", "environments")
        self.assert_ready(run)
        self.assert_states(self.by_name(run, ALL_ENVIRONMENTS), "ready")

    def test_a_second_environments_page_of_another_shape_makes_the_environments_unknown(self):
        run = self.run_paged(f"{REPOS}/environments", "environments", OTHER_SHAPE)
        self.assert_ready(run)
        self.assert_states(self.by_name(run, ALL_ENVIRONMENTS), "unknown", "unparseable")
        self.assert_states(self.by_name(run, ALL_SECRETS), "ready")

class ReleaseCheckEnvironmentPolicyTest(_CheckCase):
    """§S5 — each target's environment and its deployment-branch policy."""

    def run_with(self, policies: dict, stacks=("python",), targets=("pypi",)) -> Run:
        self.make_project(stacks, targets)
        self.set_github(github_answers(policies))
        return self.check()

    def assert_environment(self, run: Run, name: str, state: str) -> list:
        found = self.named(run, "github", name)
        self.assertTrue(found, f"§S5: an item for the {name} environment; got {self.items(run)!r}")
        states = {i["state"] for i in found}
        if state == "ready":
            self.assert_ready(run)
            self.assertEqual(states, {"ready"}, f"§S5: {name} ready; got {found!r}")
        else:
            self.assert_ran(run, 1)
            self.assertIn("missing", states, f"§S5: {name} missing; got {found!r}")
            others = [i for i in self.in_state(run, "missing") if i not in found]
            self.assertEqual(others, [], "§S5: nothing else is missing")
        return found

    def test_each_targets_environment_absent_is_missing(self):
        for stacks, target, environment in (
                (("python",), "pypi", "pypi"), (("python",), "pypi", "testpypi"),
                (("bun",), "npm", "npm"), (("rust",), "crates", "crates"),
                (("java",), "maven-central", "maven-central")):
            with self.subTest(environment=environment):
                run = self.run_with({environment: ABSENT}, stacks, (target,))
                self.assert_environment(run, environment, "missing")

    def test_a_publish_environment_with_a_null_policy_is_ready(self):
        self.assert_environment(self.run_with({"pypi": NULL}), "pypi", "ready")

    def test_a_publish_environment_limited_to_protected_branches_is_missing(self):
        self.assert_environment(self.run_with({"pypi": PROTECTED}), "pypi", "missing")

    def test_a_publish_environment_with_a_tag_policy_is_ready_with_its_patterns(self):
        found = self.assert_environment(
            self.run_with({"pypi": [tag(TAG_PATTERN), tag("v*")]}), "pypi", "ready")
        details = " ".join(i["detail"] for i in found)
        for pattern in (TAG_PATTERN, "v*"):
            self.assertIn(pattern, details, f"§S5: the patterns in the detail; got {found!r}")

    def test_a_publish_environment_with_branch_policies_only_is_missing(self):
        run = self.run_with({"pypi": [branch("main")]})
        self.assert_environment(run, "pypi", "missing")

    def test_each_publish_environment_reads_the_policy_semantics(self):
        for stacks, target in ((("bun",), "npm"), (("rust",), "crates"),
                               (("java",), "maven-central")):
            with self.subTest(target=target):
                self.assert_environment(self.run_with({target: PROTECTED}, stacks, (target,)),
                                        target, "missing")
                self.assert_environment(self.run_with({target: [tag(TAG_PATTERN)]}, stacks,
                                                      (target,)), target, "ready")

    def test_testpypi_admitting_release_and_hotfix_branches_is_ready(self):
        for shape in (NULL, [branch("release/**"), branch("hotfix/**")]):
            with self.subTest(shape=shape):
                self.assert_environment(self.run_with({"testpypi": shape}), "testpypi", "ready")

    def test_testpypi_not_admitting_both_branch_patterns_is_missing(self):
        for shape in (PROTECTED, [branch("release/**")], [branch("hotfix/**")],
                      [tag(TAG_PATTERN)]):
            with self.subTest(shape=shape):
                self.assert_environment(self.run_with({"testpypi": shape}), "testpypi",
                                        "missing")

class ReleaseCheckSecretsTest(_CheckCase):
    """§S5 — each repository secret the rendered jobs name."""

    def test_each_secret_the_rendered_jobs_name_absent_is_missing_or_unknown(self):
        self.make_project(FULL_STACKS, FULL_TARGETS)
        release_yml = (self.project / workflows.RELEASE_YML).read_text(encoding="utf-8")
        named = secrets_named(release_yml)
        self.assertEqual(named, sorted(ALL_SECRETS), "fixture: the secrets the jobs name")
        for secret in named:
            with self.subTest(secret=secret):
                self.set_github(github_answers(secrets=[s for s in ALL_SECRETS if s != secret]))
                run = self.check()
                found = self.named(run, "github", secret)
                self.assertTrue(found, f"§S5: an item for {secret}; got {self.items(run)!r}")
                if secret in FIRST_PUBLISH_TOKENS:
                    self.assert_ready(run)
                    self.assertEqual({i["state"] for i in found}, {"unknown"},
                                     f"§S5: {secret} absent is unknown; got {found!r}")
                else:
                    self.assertEqual([i["state"] for i in found], ["missing"],
                                     f"§S5: {secret} absent is missing; got {found!r}")
                    self.assert_only_missing(run, secret)

    def test_each_secret_present_is_ready(self):
        self.make_project(FULL_STACKS, FULL_TARGETS)
        run = self.check()
        self.assert_ready(run)
        for secret in ALL_SECRETS:
            with self.subTest(secret=secret):
                found = self.named(run, "github", secret)
                self.assertEqual([i["state"] for i in found], ["ready"], f"§S5: got {found!r}")

    def test_release_pat_is_checked_for_every_target_set(self):
        self.make_project(("python",), ("github-assets",))
        self.set_github(github_answers(secrets=["NPM_TOKEN"]))
        self.assert_only_missing(self.check(), "RELEASE_PAT")

    def test_a_secret_no_rendered_job_names_is_not_listed(self):
        self.make_project()
        run = self.check()
        self.assert_ready(run)
        for secret in ("NPM_TOKEN", "CARGO_REGISTRY_TOKEN", "MAVEN_CENTRAL_USERNAME"):
            self.assertEqual(self.named(run, "github", secret), [],
                             f"§S5: a pypi-only workflow names no {secret}")

    def test_the_detail_says_organisation_and_environment_secrets_are_not_read(self):
        self.make_project()
        run = self.check()
        details = " ".join(i["detail"] for i in self.area(run, "github"))
        self.assertRegex(details, r"(?i)organi[sz]ation",
                         "§S5: the detail says organisation secrets are not read")
        self.assertRegex(details, r"(?i)environment secret",
                         "§S5: the detail says environment secrets are not read")
        self.assertEqual([a for a in run.gh if "orgs/" in a[-1] or a[-1].endswith("/secrets")
                          and a[-1] != f"{REPOS}/actions/secrets"], [],
                         "§S5: no organisation or environment secret is read")

class ReleaseCheckRegistryTest(_CheckCase):
    """§S5 — each target's publisher is ``unknown``, its detail naming the fields to check."""

    def test_each_targets_publisher_is_unknown_naming_the_fields(self):
        self.make_project(FULL_STACKS, FULL_TARGETS)
        run = self.check()
        self.assert_ready(run)
        registry = self.area(run, "registry")
        self.assertTrue(registry, "§S5: a registry checklist")
        self.assertEqual({i["state"] for i in registry}, {"unknown"},
                         f"§S5: every registry item unknown; got {registry!r}")
        expected = {"pypi": ("release.yml", "testpypi"), "npm": ("release.yml",),
                    "crates": ("release.yml",), "maven-central": ("namespace",)}
        keyword = {"pypi": "pypi", "npm": "npm", "crates": "crates", "maven-central": "central"}
        for target, fields in expected.items():
            with self.subTest(target=target):
                found = [i for i in registry if keyword[target] in self.text(i).lower()]
                self.assertTrue(found, f"§S5: {target}'s publisher listed; got {registry!r}")
                text = " ".join(self.text(i) for i in found).lower()
                for field in fields:
                    self.assertIn(field, text, f"§S5: {target}'s detail names {field!r}")
        self.assertEqual([i for i in registry if "github-assets" in self.text(i)], [],
                         "§S5: github-assets has no registry publisher")

    def test_no_registry_target_lists_no_publisher(self):
        self.make_project(("python",), ("github-assets",))
        run = self.check()
        self.assert_ready(run)
        self.assertEqual(self.area(run, "registry"), [], "§S5: github-assets has no registry")

# ------------------------------------------------------------------ read-only ----

class ReleaseCheckReadOnlyTest(_CheckCase):
    """§S5 — it never writes; its only subprocesses are the three."""

    def test_a_ready_project_and_a_failing_one_are_left_byte_for_byte(self):
        for broken in (False, True):
            with self.subTest(broken=broken):
                self.make_project(FULL_STACKS, FULL_TARGETS,
                                  changelog=None if broken else CHANGELOG,
                                  rendered_for=("pypi",) if broken else None)
                if broken:
                    (self.project / ".github/scripts/build-assets").chmod(0o644)
                    self.write("pkg/package.json", "{}\n")
                before = self.tree_state()
                run = self.check()
                self.assert_ran(run, 1 if broken else 0)
                self.assertEqual(self.tree_state(), before, "§S5: it never writes")

    def test_only_git_remote_gh_api_get_and_the_stamp_script_read_are_run(self):
        self.make_project(FULL_STACKS, FULL_TARGETS)
        run = self.check()
        self.assert_ready(run)
        script = (self.project / workflows.STAMP_SCRIPT).resolve()
        git, gh, python, other = [], [], [], []
        for argv in run.calls:
            program = Path(argv[0]).name
            if program == "git":
                git.append(argv)
            elif program == "gh":
                gh.append(argv)
            elif (program.startswith("python") and len(argv) > 2
                  and (self.project / argv[1]).resolve() == script and argv[2] == "read"):
                python.append(argv)
            else:
                other.append(argv)
        self.assertEqual(other, [], "§S5: no other subprocess")
        self.assertEqual([a[1:] for a in git], [["remote", "get-url", "origin"]],
                         "§S5: `git remote get-url origin`, once")
        self.assertTrue(gh, "§S5: gh is run")
        for argv in gh:
            self.assertEqual(argv[1:4], ["api", "--method", "GET"], f"§S5: GET only; {argv!r}")
        self.assertEqual(len(gh), len(run.gh), "every gh run reached the stub")
        self.assertTrue(python, "§S5: the stamp script reads the versions")
        read = {workflows.parse_target(t) for argv in python for t in argv[3:]}
        self.assertEqual(read, {("pypi", "."), ("npm", "pkg"), ("crates", "."),
                                ("maven-central", ".")},
                         "§S5: every versioned target, from its dir")

# ------------------------------------------------------------------ the real entry ----

class ReleaseCheckCliEntryTest(_CheckCase):
    """§S5 — ``python -m modelb_axi release-check`` in a sandbox project."""

    def test_the_module_entry_runs_the_check_from_the_project(self):
        self.make_project(("python", "bun"), ("pypi", "npm:pkg"))
        write_executable(self.bin, "gh", gh_stub_source(self.gh_log, self.gh_fixture))
        env = self.env()
        env["PYTHONPATH"] = str(REPO_ROOT)
        before = self.tree_state()
        result = subprocess.run(
            [sys.executable, "-m", "modelb_axi", "--modelb-home", str(self.modelb_home), VERB],
            cwd=str(self.project), env=env, capture_output=True, text=True, timeout=120,
            stdin=subprocess.DEVNULL)
        axi = decode_axi(result.stdout)
        self.assertEqual((result.returncode, axi.get("verb"), axi.get("ok"), axi.get("missing")),
                         (0, VERB, True, 0), f"§S5: stderr={result.stderr!r}; axi={axi!r}")
        logged = [json.loads(line)[-1] for line in
                  self.gh_log.read_text(encoding="utf-8").splitlines()]
        self.assertIn(f"{REPOS}/environments", logged, "§S5: the stub gh answered")
        self.assertEqual({i["state"] for i in axi.get("items", []) if i["area"] == "github"},
                         {"ready"}, "§S5: the GitHub items read through the stub")
        self.assertEqual(self.tree_state(), before, "§S5: it never writes")


if __name__ == "__main__":
    unittest.main()
