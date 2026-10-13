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
(``tests._helpers.deploy_hook_scripts``).

Every run is sandboxed: ``--modelb-home`` and ``--target`` under temp dirs, ``PI_CODING_AGENT_DIR``
pinned by ``run_module``. Stdlib only.
"""

import argparse
import contextlib
import io
import os
import shutil
import stat
import tempfile
import tomllib
import unittest
from pathlib import Path
from unittest import mock

from modelb_axi import scaffold
from tests import test_init_tool_verdicts as _verdicts
from tests import test_installer_correctness as _correctness
from tests import test_installer_sandesh_requirements as _sandesh_requirements
from tests import test_pi_agent_definitions as _agent_definitions
from tests import test_project_permission_policy as _permission_policy
from tests import test_project_trust as _project_trust
from tests._helpers import (
    HOOK_SCRIPTS_DIR,
    decode_axi,
    deploy_hook_scripts,
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


class InstallFixturesDeployHookScriptsTest(unittest.TestCase):
    """§S8: every install fixture that leads ``init`` to emit hooks deploys all eight hook
    scripts, executable, into the store its ``install.toml`` names."""

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
        }

    def test_every_fixture_store_holds_all_eight_scripts_executable(self):
        names = sorted(self._fixtures(Path("/nonexistent")))
        for name in names:
            with self.subTest(fixture=name):
                home = Path(tempfile.mkdtemp(prefix="modelb-cr062-fixture-")).resolve()
                self.addCleanup(shutil.rmtree, home, ignore_errors=True)
                install_toml = self._fixtures(home)[name]()
                store = _store_named_by(install_toml)
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


if __name__ == "__main__":
    unittest.main()
