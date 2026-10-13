"""``init`` checks the deployed hook-script store before its first write (CR-MDB-062 §S7/§S8).

Once the store resolves (``install.toml [install].hooks_scripts_dir``), every hook ``init``
would emit must have its script there as an **executable file**. When one is missing or not
executable, ``init`` refuses: exit 2, nothing written under ``--target``, the envelope
``ok: false``, its message naming each such script and ``modelb-axi --reinstall``. A
``--dry-run`` carries the same text as a warning. When the store does not resolve, today's
error stands alone; with no roster harness no hooks are compiled, so no check runs. When every
script is present, ``init`` succeeds and wires them.

The second half pins the fixtures (§S8): every install fixture that leads ``init`` to emit
hooks deploys all eight scripts, executable, into the store its ``install.toml`` names
(``tests._helpers.deploy_hook_scripts``). The fixtures are DISCOVERED (CR-MDB-062 C5 F4,
``store_fixtures``): every function in ``tests/*.py`` holding a string that writes a
``hooks_scripts_dir =`` line into an install TOML must deploy the hook scripts — it calls
``deploy_hook_scripts``, directly or through a function that does (in its module or imported
from another test module), or every caller of it in its module does — or point that line's
value at the repo's ``hooks-src/scripts`` (a name bound to ``... / "hooks-src" / "scripts"``,
such as ``HOOK_SCRIPTS_DIR``). The discovery is proved on sample module text both ways, and
every fixture it finds is one the run-time check drives.

Every run is sandboxed: ``--modelb-home`` and ``--target`` under temp dirs, ``PI_CODING_AGENT_DIR``
pinned by ``run_module``. Stdlib only.
"""

import argparse
import ast
import contextlib
import io
import os
import re
import shutil
import stat
import tempfile
import tomllib
import unittest
from pathlib import Path
from unittest import mock

from modelb_axi import scaffold
from tests import test_claude_era_retirement as _retirement
from tests import test_harness_capability_contract as _capability
from tests import test_init_tool_verdicts as _verdicts
from tests import test_installer_correctness as _correctness
from tests import test_installer_sandesh_requirements as _sandesh_requirements
from tests import test_pi_agent_definitions as _agent_definitions
from tests import test_project_permission_policy as _permission_policy
from tests import test_project_trust as _project_trust
from tests._helpers import (
    HOOK_SCRIPTS_DIR,
    REPO_ROOT,
    decode_axi,
    deploy_hook_scripts,
    docstring_nodes,
    run_module,
    write_install_toml,
)
from tests.pi_capability_sandbox import with_agent_dir
from tests.test_installer_assets import HOOK_SCRIPT_NAMES

#: What a solo ``--stacks python`` init emits (CR-MDB-062 §S7): the two always-on hooks and the
#: python runner hook.
PYTHON_SOLO_HOOKS = (
    "ambient-board-status",
    "post-regression-disk-reminder",
    "block-direct-python-test",
)

REINSTALL = "modelb-axi --reinstall"


def _files_under(root: Path) -> list[str]:
    """Every file under ``root`` (relative, sorted), ``.git`` included — nothing may be written."""
    return sorted(str(p.relative_to(root)) for p in root.rglob("*") if p.is_file())


class _InitCase(unittest.TestCase):
    """A sandboxed pi install whose store holds every hook script, and a solo python init."""

    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="modelb-cr062-script-check-")).resolve()
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.home = self.root / "modelb-home"
        self.home.mkdir()
        self.target = self.root / "target"
        self.target.mkdir()
        self.dry_target = self.root / "dry-target"
        self.dry_target.mkdir()

    @property
    def store(self) -> Path:
        return self.home / ".agents" / "hooks" / "scripts"

    def install(self) -> None:
        write_install_toml(str(self.home), harnesses=("pi",))

    def init(self, *extra: str, stacks: str = "python", target: Path | None = None):
        """``python -m modelb_axi --yes init`` (solo, ``--no-commit``); ``(result, axi)``."""
        result = run_module(
            "--yes", "init",
            "--name", "X", "--token", "xproj", "--acronym", "XP",
            "--mode", "solo", "--repo-shape", "standalone",
            "--stacks", stacks, "--owner", "tester",
            "--target", str(target or self.target),
            "--modelb-home", str(self.home),
            "--no-commit", *extra,
            timeout=60,
        )
        return result, decode_axi(result.stdout)

    def assert_refused(self, result, axi, target: Path) -> str:
        """The §S7 refusal: exit 2, nothing under ``target``, ``ok: false``, one message —
        returned."""
        detail = f"exit={result.returncode} axi={axi!r} stderr={result.stderr!r}"
        self.assertEqual(result.returncode, 2, f"§S7: init refuses with exit 2; {detail}")
        self.assertEqual(_files_under(target), [], f"§S7: nothing written under --target; {detail}")
        self.assertIs(axi.get("ok"), False, f"§S7: the envelope says ok: false; {detail}")
        warnings = axi.get("warnings") or []
        self.assertEqual(len(warnings), 1, f"§S7: one refusal message; {detail}")
        message = str(warnings[0])
        self.assertIn(REINSTALL, message, f"§S7: the message names `{REINSTALL}`; {message!r}")
        return message


class InitRefusesOnUnusableHookScriptTest(_InitCase):
    """A store that resolves but lacks a usable script for an emitted hook: init refuses."""

    def test_missing_emitted_script_refuses_naming_it_and_reinstall(self):
        self.install()
        (self.store / "block-direct-python-test").unlink()
        result, axi = self.init()
        message = self.assert_refused(result, axi, self.target)
        self.assertIn("block-direct-python-test", message,
                      f"§S7: the message names the missing script; {message!r}")

    def test_non_executable_emitted_script_mode_0644_refuses_naming_it(self):
        self.install()
        script = self.store / "block-direct-python-test"
        script.chmod(0o644)
        self.assertEqual(stat.S_IMODE(script.stat().st_mode), 0o644, "fixture: mode 0644")
        result, axi = self.init()
        message = self.assert_refused(result, axi, self.target)
        self.assertIn("block-direct-python-test", message,
                      f"§S7: the message names the non-executable script; {message!r}")

    def test_one_missing_of_several_names_only_that_script(self):
        self.install()
        (self.store / "post-regression-disk-reminder").unlink()
        result, axi = self.init()
        message = self.assert_refused(result, axi, self.target)
        self.assertIn("post-regression-disk-reminder", message,
                      f"§S7: the message names the missing script; {message!r}")
        # NEGATIVE -- the usable scripts of the other emitted hooks are not blamed.
        for present in ("ambient-board-status", "block-direct-python-test"):
            self.assertNotIn(present, message,
                             f"§S7: {present} is present and executable; {message!r}")

    def test_each_unusable_script_is_named(self):
        self.install()
        (self.store / "ambient-board-status").unlink()
        (self.store / "block-direct-python-test").chmod(0o644)
        result, axi = self.init()
        message = self.assert_refused(result, axi, self.target)
        for unusable in ("ambient-board-status", "block-direct-python-test"):
            self.assertIn(unusable, message, f"§S7: the message names {unusable}; {message!r}")
        self.assertNotIn("post-regression-disk-reminder", message,
                         f"§S7: a usable script is not named; {message!r}")

    def test_empty_store_names_every_emitted_hook_script(self):
        self.install()
        for script in self.store.iterdir():
            script.unlink()
        result, axi = self.init()
        message = self.assert_refused(result, axi, self.target)
        for command in PYTHON_SOLO_HOOKS:
            self.assertIn(command, message, f"§S7: the message names {command}; {message!r}")

    def test_dry_run_carries_the_same_text_as_a_warning_and_writes_nothing(self):
        self.install()
        (self.store / "block-direct-python-test").unlink()
        result, axi = self.init()
        message = self.assert_refused(result, axi, self.target)
        dry, dry_axi = self.init("--dry-run", target=self.dry_target)
        detail = f"exit={dry.returncode} axi={dry_axi!r} stderr={dry.stderr!r}"
        self.assertEqual(dry.returncode, 0, f"§S7: a dry run still exits 0; {detail}")
        self.assertEqual(_files_under(self.dry_target), [], f"a dry run writes nothing; {detail}")
        self.assertIn(message, dry_axi.get("warnings") or [],
                      f"§S7: the dry run carries the refusal's text as a warning; {detail}")


class InitHookScriptCheckScopeTest(_InitCase):
    """The check covers exactly the hooks init would emit, and runs only when the store
    resolves for a roster harness."""

    def test_every_script_present_init_succeeds_and_wires_the_python_runner_hook(self):
        self.install()
        result, axi = self.init()
        detail = f"exit={result.returncode} axi={axi!r} stderr={result.stderr!r}"
        self.assertEqual((result.returncode, axi.get("ok")), (0, True), f"§S7: succeeds; {detail}")
        for command in PYTHON_SOLO_HOOKS:
            with self.subTest(command=command):
                self.assertTrue(
                    (self.target / ".pi" / "extensions" / f"{command}.ts").is_file(),
                    f"§S7: {command} is wired for pi; {detail}",
                )

    def test_script_of_a_hook_not_emitted_may_be_missing(self):
        # The bun hook is not emitted for a python project, so its script is not checked.
        self.install()
        (self.store / "block-direct-bun-test").unlink()
        (self.store / "block-direct-cargo-test").chmod(0o644)
        result, axi = self.init()
        self.assertEqual((result.returncode, axi.get("ok")), (0, True),
                         f"§S7: only emitted hooks' scripts are checked; axi={axi!r} "
                         f"stderr={result.stderr!r}")

    def test_bun_project_refuses_on_missing_bun_runner_script(self):
        self.install()
        (self.store / "block-direct-bun-test").unlink()
        result, axi = self.init(stacks="bun")
        message = self.assert_refused(result, axi, self.target)
        self.assertIn("block-direct-bun-test", message,
                      f"§S7: the bun runner hook's script is checked; {message!r}")

    def _todays_store_error(self) -> str:
        with self.assertRaises(scaffold.ScaffoldError) as ctx:
            scaffold._hook_scripts_root(self.home)
        return str(ctx.exception)

    def test_no_install_toml_today_error_stands_alone(self):
        expected = self._todays_store_error()
        for flags, target in (((), self.target), (("--dry-run",), self.dry_target)):
            with self.subTest(dry_run=bool(flags)):
                result, axi = self.init("--harnesses", "pi", *flags, target=target)
                self.assertEqual(axi.get("warnings"), [expected],
                                 f"§S7: today's error alone, one not two; axi={axi!r}")
                self.assertEqual(_files_under(target), [], "nothing written")

    def test_install_toml_without_hooks_scripts_dir_today_error_stands_alone(self):
        (self.home / "install.toml").write_text(
            '[install]\nversion = "0.1.0"\nharnesses = ["pi"]\n'
            'asset_root = "/tmp/does-not-matter-for-this-test"\n\n[deps]\nuv = "detected"\n'
            "\n[files]\n",
            encoding="utf-8",
        )
        expected = self._todays_store_error()
        for flags, target in (((), self.target), (("--dry-run",), self.dry_target)):
            with self.subTest(dry_run=bool(flags)):
                result, axi = self.init(*flags, target=target)
                self.assertEqual(axi.get("warnings"), [expected],
                                 f"§S7: today's error alone, one not two; axi={axi!r}")
                self.assertEqual(_files_under(target), [], "nothing written")

    def test_no_roster_harness_runs_no_check(self):
        # No CLI path selects no roster harness (every recorded or requested id is checked
        # against the roster, and an empty set is refused), so the resolved harness set is
        # stubbed in process as empty: with no roster harness no hooks are compiled.
        self.install()
        shutil.rmtree(self.store)
        args = argparse.Namespace(
            name="X", token="xproj", acronym="XP", mode="solo", repo_shape="standalone",
            stacks="python", owner="tester", target=str(self.target), dry_run=False,
            no_commit=True, register=False, harnesses=None,
        )
        out, err = io.StringIO(), io.StringIO()
        with (
            mock.patch.object(scaffold, "resolve_harnesses",
                              return_value=([], "test stub")),
            mock.patch.dict(os.environ, with_agent_dir(None)),
            contextlib.redirect_stdout(out), contextlib.redirect_stderr(err),
        ):
            rc = scaffold.run_init(args, self.home)
        axi = decode_axi(out.getvalue())
        self.assertEqual((rc, axi.get("ok")), (0, True),
                         f"§S7: no roster harness, no check; axi={axi!r} err={err.getvalue()!r}")
        self.assertFalse(any(REINSTALL in str(w) for w in axi.get("warnings") or []),
                         f"no script-check message; axi={axi!r}")


def _store_named_by(install_toml: Path) -> Path:
    with open(install_toml, "rb") as fh:
        return Path(tomllib.load(fh)["install"]["hooks_scripts_dir"])


#: A line of an install TOML naming the hook-script store.
_STORE_LINE = re.compile(r"(?m)^[ \t]*hooks_scripts_dir[ \t]*=")
#: A path expression naming the repo's own hook scripts: ``"hooks-src" / "scripts"`` or the
#: string ``"hooks-src/scripts"``.
_REPO_SCRIPTS = re.compile(r"""["']hooks-src["']\s*/\s*["']scripts["']|hooks-src/scripts""")
#: The shared fixture that copies every hook script into a store.
_DEPLOY = "deploy_hook_scripts"


def _called_names(node: ast.AST) -> set[str]:
    """The bare name of each call under ``node``: ``f(...)`` and ``x.f(...)`` both give ``f``."""
    names = set()
    for call in ast.walk(node):
        if isinstance(call, ast.Call):
            if isinstance(call.func, ast.Name):
                names.add(call.func.id)
            elif isinstance(call.func, ast.Attribute):
                names.add(call.func.attr)
    return names


def _store_line_value(text: str, constant: ast.Constant, parent: ast.AST | None):
    """The expression a store line in ``text`` (the value of ``constant``) takes its value
    from: the f-string field right after it on the same line, or ``None`` for a literal value."""
    last = list(_STORE_LINE.finditer(text))[-1]
    if not isinstance(parent, ast.JoinedStr) or "\n" in text[last.end():]:
        return None
    parts = parent.values
    following = parts[parts.index(constant) + 1:]
    if following and isinstance(following[0], ast.FormattedValue):
        return following[0].value
    return None


def _module_facts(source: str) -> dict:
    """What ``store_fixtures`` reads of one module: its functions, the names it imports from
    another test module, the module-level names bound to the repo's hook scripts, and each
    store line as ``(enclosing function or None, value expression or None)``."""
    tree = ast.parse(source)
    docstrings = docstring_nodes(tree)
    facts = {"functions": [], "imports": {}, "repo_names": set(), "sites": []}
    for node in tree.body:
        if isinstance(node, ast.Assign) and _REPO_SCRIPTS.search(ast.unparse(node.value)):
            facts["repo_names"].update(t.id for t in node.targets if isinstance(t, ast.Name))
        elif isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("tests."):
            origin = node.module.removeprefix("tests.")
            for alias in node.names:
                facts["imports"][alias.asname or alias.name] = (origin, alias.name)

    def visit(node, parent, enclosing):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            facts["functions"].append(node)
            enclosing = node
        if (isinstance(node, ast.Constant) and isinstance(node.value, str)
                and id(node) not in docstrings and _STORE_LINE.search(node.value)):
            facts["sites"].append((enclosing, _store_line_value(node.value, node, parent)))
        for child in ast.iter_child_nodes(node):
            visit(child, node, enclosing)

    visit(tree, None, None)
    return facts


def store_fixtures(sources: dict[str, str]) -> dict[str, tuple[str, frozenset]]:
    """Each function in ``sources`` (``{module stem: source}``) holding a string that writes a
    ``hooks_scripts_dir =`` line into an install TOML, as ``"<module>.<function>"`` (a store
    line outside a function is ``"<module>.<module level>"``) mapped to how it qualifies and
    the functions of its module that a run-time check drives:

    - ``("deploys", {itself})`` — it calls ``deploy_hook_scripts``, directly or through a
      function that does, in its module or imported from another module in ``sources``;
    - ``("callers deploy", {each caller})`` — it has a caller in its module, and each one
      qualifies;
    - ``("repo scripts", {itself})`` — the line's value names the repo's ``hooks-src/scripts``;
    - ``("neither", {})`` — none of these: the fixture leaves the store it names empty.
    """
    facts = {module: _module_facts(source) for module, source in sources.items()}
    deploying = {module: set() for module in facts}
    changed = True
    while changed:  # the fixed point of "calls something that deploys", across modules
        changed = False
        for module, fact in facts.items():
            reach = {_DEPLOY} | deploying[module] | {
                local for local, (origin, name) in fact["imports"].items()
                if name == _DEPLOY or name in deploying.get(origin, ())}
            for function in fact["functions"]:
                if function.name not in deploying[module] and _called_names(function) & reach:
                    deploying[module].add(function.name)
                    changed = True

    def repo_names(module):
        fact = facts[module]
        return fact["repo_names"] | {
            local for local, (origin, name) in fact["imports"].items()
            if name in facts.get(origin, {}).get("repo_names", ())}

    def qualifying_callers(module, function, seen):
        """The deploying callers of ``function`` in ``module``, or ``None`` when it has no
        caller there or one of them neither deploys nor has only qualifying callers itself."""
        callers = [f for f in facts[module]["functions"]
                   if f is not function and function.name in _called_names(f)]
        if not callers:
            return None
        drivers = set()
        for caller in callers:
            if caller.name in deploying[module]:
                drivers.add(caller.name)
                continue
            if caller.name in seen:
                return None
            above = qualifying_callers(module, caller, seen | {caller.name})
            if above is None:
                return None
            drivers |= above
        return drivers

    found = {}
    for module, fact in facts.items():
        for function, value in fact["sites"]:
            name = function.name if function else "<module level>"
            names_repo = value is not None and (
                {n.id for n in ast.walk(value) if isinstance(n, ast.Name)} & repo_names(module)
                or _REPO_SCRIPTS.search(ast.unparse(value)))
            if names_repo:
                verdict = ("repo scripts", frozenset({name}))
            elif function and function.name in deploying[module]:
                verdict = ("deploys", frozenset({name}))
            else:
                drivers = function and qualifying_callers(module, function, {function.name})
                verdict = (("callers deploy", frozenset(drivers)) if drivers
                           else ("neither", frozenset()))
            found[f"{module}.{name}"] = verdict
    return found


def _tree_sources() -> dict[str, str]:
    """Every ``tests/*.py`` module's source, keyed by its stem."""
    return {path.stem: path.read_text(encoding="utf-8")
            for path in sorted((REPO_ROOT / "tests").glob("*.py"))}


class InstallFixturesDeployHookScriptsTest(unittest.TestCase):
    """§S8: every install fixture that leads ``init`` to emit hooks deploys all eight hook
    scripts, executable, into the store its ``install.toml`` names — or names the repo's own
    ``hooks-src/scripts`` as that store. Every fixture ``store_fixtures`` discovers in
    ``tests/*.py`` qualifies one of these ways, and is one the run-time check drives."""

    def _fixtures(self, home: Path) -> dict:
        """Each fixture, writing into ``home``; returns its ``install.toml`` path."""
        def project_trust():
            sandbox = _project_trust._TrustSandbox()
            sandbox.modelb_home = home
            sandbox.write_install_toml(("pi",))
            return home / "install.toml"

        def permission_policy():
            _permission_policy.write_install_toml(home)
            return home / "install.toml"

        def sandesh_requirements():
            case = _sandesh_requirements.InitReadsTheRecordedVerdictsTest()
            case.modelb_home = home
            return case.write_install({}, {"uv": "detected"})

        def pre036():
            case = _capability.InstallTomlCapabilitiesRecordTest()
            case.modelb_home, case.target_root = home, home / "target"
            case._write_pre036()
            return home / "install.toml"

        return {
            "_helpers.write_install_toml": lambda: write_install_toml(str(home)),
            "test_project_permission_policy.write_install_toml": permission_policy,
            "test_project_trust._TrustSandbox.write_install_toml": project_trust,
            "test_pi_agent_definitions._write_install_toml_c3":
                lambda: _agent_definitions._write_install_toml_c3(home, home / "assets"),
            "test_init_tool_verdicts._write_install_toml":
                lambda: _verdicts._write_install_toml(home, None, {"uv": "detected"}),
            "test_installer_correctness._write_full_install_toml":
                lambda: _correctness._write_full_install_toml(str(home)),
            "test_installer_sandesh_requirements.InitReadsTheRecordedVerdictsTest.write_install":
                sandesh_requirements,
            "test_harness_capability_contract.InstallTomlCapabilitiesRecordTest._write_pre036":
                pre036,
            # Qualifies through the repo path: its store IS the repo's hooks-src/scripts.
            "test_claude_era_retirement.pi_install_toml": lambda: _retirement.pi_install_toml(home),
        }

    def test_every_fixture_store_holds_all_eight_scripts_executable(self):
        names = sorted(self._fixtures(Path("/nonexistent")))
        for name in names:
            with self.subTest(fixture=name):
                home = Path(tempfile.mkdtemp(prefix="modelb-cr062-fixture-")).resolve()
                self.addCleanup(shutil.rmtree, home, ignore_errors=True)
                install_toml = self._fixtures(home)[name]()
                store = _store_named_by(install_toml)
                if store.resolve() == HOOK_SCRIPTS_DIR.resolve():
                    # the repo's own scripts dir: a local __pycache__ beside them is no script
                    found = sorted(p.name for p in store.iterdir() if p.is_file())
                else:
                    found = sorted(p.name for p in store.iterdir()) if store.is_dir() else []
                self.assertEqual(found, sorted(HOOK_SCRIPT_NAMES),
                                 f"§S8: {name}'s store {store} holds all eight scripts")
                for script in found:
                    path = store / script
                    self.assertTrue(path.is_file() and os.access(path, os.X_OK),
                                    f"§S8: {name}: {script} is an executable file")
                    self.assertEqual(path.read_bytes(), (HOOK_SCRIPTS_DIR / script).read_bytes(),
                                     f"§S8: {name}: {script} is the repo's script")

    def test_deploy_hook_scripts_copies_every_source_script_with_mode_0755(self):
        store = Path(tempfile.mkdtemp(prefix="modelb-cr062-store-")).resolve() / "a" / "store"
        self.addCleanup(shutil.rmtree, store.parent.parent, ignore_errors=True)
        returned = deploy_hook_scripts(store)
        self.assertEqual(returned, store)
        self.assertEqual(sorted(p.name for p in store.iterdir()), sorted(HOOK_SCRIPT_NAMES))
        for script in store.iterdir():
            self.assertEqual(oct(stat.S_IMODE(script.stat().st_mode)), oct(0o755), script.name)

    def test_every_discovered_fixture_deploys_or_names_the_repo_scripts(self):
        found = store_fixtures(_tree_sources())
        self.assertGreater(len(found), 0, "precondition: the discovery finds the store fixtures")
        self.assertEqual({site: how for site, (how, _drivers) in found.items() if how == "neither"},
                         {}, "C5 F4: a fixture writes a hooks_scripts_dir line into an install "
                             "TOML but neither deploys the hook scripts nor names hooks-src/scripts")

    def test_the_run_time_check_drives_every_discovered_fixture(self):
        driven = {(key.split(".")[0], key.split(".")[-1])
                  for key in self._fixtures(Path("/nonexistent"))}
        for site, (how, drivers) in store_fixtures(_tree_sources()).items():
            module = site.split(".")[0]
            with self.subTest(site=site):
                self.assertTrue(drivers, f"{site} qualifies {how!r} through no fixture")
                self.assertEqual(sorted(d for d in drivers if (module, d) not in driven), [],
                                 f"C5 F4: {site} ({how}) is written by a fixture the run-time "
                                 "check never drives")


class StoreFixtureDiscoveryOnSampleTextTest(unittest.TestCase):
    """C5 F4 — ``store_fixtures`` proved on sample module text both ways: each way a fixture
    qualifies is found, and a fixture that does neither is caught."""

    #: A shared-fixture module the samples import from.
    SHARED = (
        "from tests._helpers import deploy_hook_scripts\n"
        "SCRIPTS = REPO_ROOT / 'hooks-src' / 'scripts'\n"
        "def prepare(home):\n"
        "    return deploy_hook_scripts(home / 'store')\n"
    )

    def assertFound(self, source: str, expected: dict):
        found = store_fixtures({"shared": self.SHARED, "sample": source})
        self.assertEqual({site: (how, sorted(drivers)) for site, (how, drivers) in found.items()
                          if site.startswith("sample.")}, expected, source)

    def test_a_fixture_that_calls_deploy_hook_scripts_directly_deploys(self):
        self.assertFound(
            "from tests._helpers import deploy_hook_scripts\n"
            "def fixture(home):\n"
            "    store = deploy_hook_scripts(home / 'store')\n"
            "    (home / 'install.toml').write_text(\n"
            "        '[install]\\n'\n"
            "        f'hooks_scripts_dir = \"{store}\"\\n')\n",
            {"sample.fixture": ("deploys", ["fixture"])})

    def test_a_fixture_that_deploys_through_a_helper_or_a_shared_fixture_deploys(self):
        self.assertFound(
            "from tests._helpers import deploy_hook_scripts\n"
            "from tests.shared import prepare as _prepare\n"
            "def _store(home):\n"
            "    return deploy_hook_scripts(home / 'store')\n"
            "class Case:\n"
            "    def local(self, home):\n"
            "        store = _store(home)\n"
            "        return f'hooks_scripts_dir = \"{store}\"'\n"
            "    def shared(self, home):\n"
            "        store = _prepare(home)\n"
            "        return f'hooks_scripts_dir = \"{store}\"'\n",
            {"sample.local": ("deploys", ["local"]), "sample.shared": ("deploys", ["shared"])})

    def test_a_text_builder_qualifies_when_each_of_its_callers_deploys(self):
        self.assertFound(
            "from tests._helpers import deploy_hook_scripts\n"
            "def _text(home):\n"
            "    return '\\n'.join(['[install]', f'hooks_scripts_dir = \"{home}/s\"'])\n"
            "def write(home):\n"
            "    deploy_hook_scripts(home / 's')\n"
            "    (home / 'install.toml').write_text(_text(home))\n",
            {"sample._text": ("callers deploy", ["write"])})

    def test_a_fixture_that_names_the_repo_scripts_qualifies_through_the_repo_path(self):
        self.assertFound(
            "import json\n"
            "from tests._helpers import HOOK_SCRIPTS_DIR\n"
            "from tests.shared import SCRIPTS\n"
            "HOOKS = REPO_ROOT / 'hooks-src' / 'scripts'\n"
            "def own(home):\n"
            "    return f'hooks_scripts_dir = {json.dumps(str(HOOKS))}'\n"
            "def imported(home):\n"
            "    return f'hooks_scripts_dir = \"{SCRIPTS}\"'\n"
            "def inline(home):\n"
            "    return f'hooks_scripts_dir = \"{REPO_ROOT / \"hooks-src\" / \"scripts\"}\"'\n",
            {"sample.own": ("repo scripts", ["own"]),
             "sample.imported": ("repo scripts", ["imported"]),
             "sample.inline": ("repo scripts", ["inline"])})

    def test_a_fixture_that_does_neither_is_caught(self):
        self.assertFound(
            "def literal(home):\n"
            "    (home / 'install.toml').write_text(\n"
            "        '[install]\\n'\n"
            "        'hooks_scripts_dir = \"/tmp/store\"\\n')\n"
            "def temp_store(home):\n"
            "    return f'hooks_scripts_dir = \"{home}/.agents/hooks/scripts\"'\n"
            "def deploys_elsewhere(home):\n"
            "    return f'version = \"0.1.0\"\\nhooks_scripts_dir = \"{home}\"'\n",
            {"sample.literal": ("neither", []), "sample.temp_store": ("neither", []),
             "sample.deploys_elsewhere": ("neither", [])})

    def test_a_text_builder_with_one_caller_that_does_not_deploy_is_caught(self):
        self.assertFound(
            "from tests._helpers import deploy_hook_scripts\n"
            "def _text(home):\n"
            "    return f'hooks_scripts_dir = \"{home}/s\"'\n"
            "def write(home):\n"
            "    deploy_hook_scripts(home / 's')\n"
            "    return _text(home)\n"
            "def write_bare(home):\n"
            "    return _text(home)\n",
            {"sample._text": ("neither", [])})

    def test_a_store_line_at_module_level_is_caught(self):
        self.assertFound("TOML = 'hooks_scripts_dir = \"/tmp/store\"'\n",
                         {"sample.<module level>": ("neither", [])})

    def test_a_docstring_or_a_key_read_is_no_store_fixture(self):
        key = "hooks_scripts_dir"  # spliced in, so this module's own text holds no store line
        self.assertFound(
            "def reader(data):\n"
            f"    '''Reads the {key} = line:\n"
            f"    {key} = \"/tmp/store\" is what it parses.'''\n"
            f"    return data['install']['{key}']\n",
            {})


if __name__ == "__main__":
    unittest.main()
