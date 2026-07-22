"""RED-phase tests for CR-MDB-014 cycle C1 (universal installer,
`modelb-axi`): §S2 package skeleton + §S3 state detection/adaptive TUI
shell, plus the sandbox-guard half of AC7.

Written before any of §S2/§S3's production code lands (no `pyproject.toml`,
no `modelb_axi/` module dir exist yet on this branch), so every test below
is expected to FAIL against the current tree:
  - AC1: `pyproject.toml` and `modelb_axi/` don't exist -- structural
    assertions fail cleanly; the `uv tool install` integration probe fails
    because there is nothing installable yet.
  - AC3/AC8: `python -m modelb_axi ...` fails at the subprocess level
    (`ModuleNotFoundError` on stderr, non-zero exit) since the package
    doesn't exist -- this is a subprocess-level failure, not an in-process
    import, so it does NOT kill collection of this file.

All invocations are subprocess probes (`uv tool install`, `python -m
modelb_axi`) against tmp sandboxes (`UV_TOOL_DIR`/`UV_TOOL_BIN_DIR`,
`MODELB_HOME`/`--modelb-home`) -- per the CR's binding rule and DN §7,
nothing here ever deploys into the real `~/.claude` or `~/.agents`. A
module-level `setUpModule`/`tearDownModule` fixture snapshots the mtimes of
the real `~/.claude/skills` and `~/.agents` trees before and after the
whole module runs and fails loudly if anything in this file touched them
(AC7 sandbox-guard slice for C1).

Stdlib only: unittest + subprocess + sys + os + shutil + tempfile +
tomllib + pathlib.
"""

import os
import shutil
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PYPROJECT_TOML = REPO_ROOT / "pyproject.toml"
MODULE_DIR = REPO_ROOT / "modelb_axi"
MODULE_INIT = MODULE_DIR / "__init__.py"

PACKAGE_NAME = "modelb-axi"
CONSOLE_SCRIPT_NAME = "modelb-axi"

CLAUDE_DIR = Path.home() / ".claude"
AGENTS_HOME_DIR = Path.home() / ".agents"
# AC7 sandbox-guard slice (C1): these two real, live trees must never be
# touched by anything in this test module.
_GUARD_DIRS = [CLAUDE_DIR / "skills", AGENTS_HOME_DIR]


def _snapshot_mtimes(roots):
    """Best-effort recursive mtime snapshot of `roots` for the AC7 guard.
    Missing roots are simply absent from the snapshot (not an error)."""
    snap = {}
    for root in roots:
        if not root.exists():
            continue
        snap[root] = root.stat().st_mtime
        for child in root.rglob("*"):
            try:
                snap[child] = child.stat().st_mtime
            except OSError:
                continue
    return snap


_guard_snapshot_before = {}


def setUpModule():
    global _guard_snapshot_before
    _guard_snapshot_before = _snapshot_mtimes(_GUARD_DIRS)


def tearDownModule():
    after = _snapshot_mtimes(_GUARD_DIRS)
    if after != _guard_snapshot_before:
        all_paths = set(_guard_snapshot_before) | set(after)
        changed = sorted(
            str(p) for p in all_paths
            if _guard_snapshot_before.get(p) != after.get(p)
        )
        raise AssertionError(
            "AC7 sandbox guard violated: the real ~/.claude/skills and/or "
            "~/.agents tree changed mtime while running "
            f"tests/test_installer.py; changed paths (up to 20): {changed[:20]}"
        )


def _run_module(*args, env_overrides=None, timeout=15, stdin=subprocess.DEVNULL):
    """Invoke `python -m modelb_axi <args>` with the repo root on
    PYTHONPATH, so a not-yet-existing package surfaces as a clean
    subprocess-level failure (`ModuleNotFoundError` on stderr, non-zero
    exit) instead of an in-process ImportError that would kill collection
    of this whole test file."""
    env = dict(os.environ)
    existing_pp = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(REPO_ROOT) + (os.pathsep + existing_pp if existing_pp else "")
    if env_overrides:
        env.update(env_overrides)
    cmd = [sys.executable, "-m", "modelb_axi", *args]
    return subprocess.run(
        cmd, capture_output=True, text=True, timeout=timeout, stdin=stdin, env=env,
    )


class PackageSkeletonTest(unittest.TestCase):
    """AC1 -- `pyproject.toml` (package `modelb-axi` + console script
    `modelb-axi`) and `modelb_axi/` module dir skeleton."""

    def test_pyproject_declares_modelb_axi_package_name(self):
        if not PYPROJECT_TOML.is_file():
            self.fail(
                f"AC1: {PYPROJECT_TOML} does not exist yet -- package "
                "skeleton (§S2) is missing"
            )
        with open(PYPROJECT_TOML, "rb") as fh:
            data = tomllib.load(fh)
        project = data.get("project", {})
        # POSITIVE -- exact declared package name.
        self.assertEqual(
            project.get("name"), PACKAGE_NAME,
            f"AC1: pyproject.toml [project].name must be exactly "
            f"{PACKAGE_NAME!r}, got {project.get('name')!r}",
        )

    def test_pyproject_declares_modelb_axi_console_script(self):
        if not PYPROJECT_TOML.is_file():
            self.fail(
                f"AC1: {PYPROJECT_TOML} does not exist yet -- console "
                "script entry (§S2) is missing"
            )
        with open(PYPROJECT_TOML, "rb") as fh:
            data = tomllib.load(fh)
        scripts = data.get("project", {}).get("scripts", {})
        # POSITIVE -- exact console-script key present.
        self.assertIn(
            CONSOLE_SCRIPT_NAME, scripts,
            f"AC1: pyproject.toml [project.scripts] must declare the "
            f"{CONSOLE_SCRIPT_NAME!r} console script, got keys "
            f"{list(scripts.keys())}",
        )

    def test_modelb_axi_module_dir_exists_with_init(self):
        self.assertTrue(
            MODULE_DIR.is_dir(),
            f"AC1: package module directory {MODULE_DIR} must exist",
        )
        self.assertTrue(
            MODULE_INIT.is_file(),
            f"AC1: {MODULE_INIT} must exist for modelb_axi/ to be a real "
            "importable package",
        )

    def test_uv_tool_install_produces_runnable_modelb_axi_version_exit_zero(self):
        """C1 INTEGRATION TEST for AC1's heavier probe: `uv tool install
        <repo> --force` into a fully sandboxed UV_TOOL_DIR/UV_TOOL_BIN_DIR
        (tempfile dirs, never the real uv tool dirs), then run the
        installed `modelb-axi --version` and expect exit 0. Must FAIL now
        -- there is no `pyproject.toml` for `uv` to install anything from."""
        uv = shutil.which("uv")
        if uv is None:
            self.fail(
                "AC1 integration probe: `uv` binary not found on PATH -- "
                "cannot verify installability (guarded, not skipped)"
            )
        tool_dir = tempfile.mkdtemp(prefix="modelb-axi-uv-tool-dir-")
        tool_bin_dir = tempfile.mkdtemp(prefix="modelb-axi-uv-tool-bin-")
        try:
            env = dict(os.environ)
            env["UV_TOOL_DIR"] = tool_dir
            env["UV_TOOL_BIN_DIR"] = tool_bin_dir
            install = subprocess.run(
                [uv, "tool", "install", str(REPO_ROOT), "--force"],
                capture_output=True, text=True, timeout=120, env=env,
            )
            # POSITIVE -- the sandboxed install must succeed.
            self.assertEqual(
                install.returncode, 0,
                f"AC1: `uv tool install {REPO_ROOT} --force` must exit 0 "
                "into the sandboxed UV_TOOL_DIR/UV_TOOL_BIN_DIR; got "
                f"exit={install.returncode}\nstdout={install.stdout[-2000:]}"
                f"\nstderr={install.stderr[-2000:]}",
            )
            installed_bin = Path(tool_bin_dir) / CONSOLE_SCRIPT_NAME
            self.assertTrue(
                installed_bin.exists(),
                f"AC1: installed console script {installed_bin} must "
                "exist after `uv tool install`",
            )
            version = subprocess.run(
                [str(installed_bin), "--version"],
                capture_output=True, text=True, timeout=30,
            )
            # POSITIVE -- the installed console script must run and exit 0.
            self.assertEqual(
                version.returncode, 0,
                f"AC1: installed `{CONSOLE_SCRIPT_NAME} --version` must "
                f"exit 0, got exit={version.returncode} "
                f"stdout={version.stdout!r} stderr={version.stderr!r}",
            )
        finally:
            shutil.rmtree(tool_dir, ignore_errors=True)
            shutil.rmtree(tool_bin_dir, ignore_errors=True)


class StateDetectionTest(unittest.TestCase):
    """AC3 -- state detection both ways: no `install.toml` under
    `$MODELB_HOME` enters the INSTALLER flow; a valid `install.toml`
    enters SCAFFOLD mode (v1 stub naming CR-MDB-013). Exercises both the
    `--modelb-home` flag (preferred) and the `MODELB_HOME` env var (tested
    at least once) per DN §3's config seam."""

    def setUp(self):
        self._tmp_home = tempfile.mkdtemp(prefix="modelb-axi-home-")

    def tearDown(self):
        shutil.rmtree(self._tmp_home, ignore_errors=True)

    def test_missing_install_toml_enters_installer_flow_via_modelb_home_flag(self):
        result = _run_module(
            "--yes", "--harnesses", "claude-code",
            "--modelb-home", self._tmp_home,
        )
        # POSITIVE -- with no install.toml, stdout must name the installer
        # flow (not scaffold mode).
        self.assertIn(
            "installer", result.stdout.lower(),
            "AC3: with no install.toml under --modelb-home, stdout must "
            f"mention the installer flow; got exit={result.returncode} "
            f"stdout={result.stdout!r} stderr={result.stderr!r}",
        )
        # NEGATIVE -- must NOT claim to be in scaffold mode / name CR-MDB-013.
        self.assertNotIn(
            "CR-MDB-013", result.stdout,
            "AC3: with no install.toml present, the run must NOT enter "
            f"scaffold mode; got stdout={result.stdout!r}",
        )

    def test_missing_install_toml_enters_installer_flow_via_modelb_home_env_var(self):
        """Confirms $MODELB_HOME (the env var, not just --modelb-home)
        also resolves the config seam per DN §3."""
        result = _run_module(
            "--yes", "--harnesses", "claude-code",
            env_overrides={"MODELB_HOME": self._tmp_home},
        )
        self.assertIn(
            "installer", result.stdout.lower(),
            "AC3: MODELB_HOME env var (no --modelb-home flag) with no "
            f"install.toml must still enter installer flow; got "
            f"exit={result.returncode} stdout={result.stdout!r} "
            f"stderr={result.stderr!r}",
        )

    def test_valid_install_toml_enters_scaffold_mode_naming_cr_mdb_013(self):
        install_toml = Path(self._tmp_home) / "install.toml"
        install_toml.write_text(
            '[install]\n'
            'version = "0.1.0"\n'
            'harnesses = ["claude-code"]\n'
            'asset_root = "/tmp/does-not-matter-for-this-test"\n'
            '\n'
            '[deps]\n'
            'uv = "present"\n'
            '\n'
            '[files]\n',
            encoding="utf-8",
        )
        result = _run_module("--yes", "--modelb-home", self._tmp_home)
        # POSITIVE -- v1 scaffold stub exits 0 and names CR-MDB-013.
        self.assertEqual(
            result.returncode, 0,
            "AC3: scaffold-mode v1 stub must exit 0 when install.toml is "
            f"present; got exit={result.returncode} stdout={result.stdout!r} "
            f"stderr={result.stderr!r}",
        )
        self.assertIn(
            "CR-MDB-013", result.stdout,
            "AC3: with install.toml present, launch must enter scaffold "
            f"mode and name CR-MDB-013 in stdout; got "
            f"stdout={result.stdout!r} stderr={result.stderr!r}",
        )
        # NEGATIVE -- must NOT re-run the installer flow once scaffolded.
        self.assertNotIn(
            "installer flow", result.stdout.lower(),
            "AC3: with install.toml present, the run must NOT re-enter the "
            f"installer flow; got stdout={result.stdout!r}",
        )


class NonInteractivePromptsTest(unittest.TestCase):
    """AC8 -- the TUI is skippable end-to-end via flags (CI-safe):
    `--yes` must complete without ever reading stdin."""

    def setUp(self):
        self._tmp_home = tempfile.mkdtemp(prefix="modelb-axi-home-")

    def tearDown(self):
        shutil.rmtree(self._tmp_home, ignore_errors=True)

    def test_yes_flag_completes_without_blocking_on_stdin(self):
        try:
            result = _run_module(
                "--yes", "--harnesses", "claude-code",
                "--modelb-home", self._tmp_home,
                stdin=subprocess.DEVNULL,
                timeout=10,
            )
        except subprocess.TimeoutExpired:
            self.fail(
                "AC8: `modelb-axi --yes ...` with stdin=DEVNULL must not "
                "hang waiting on interactive input; timed out after 10s "
                "(a CI-safe, non-interactive flow must never read stdin)"
            )
        # POSITIVE -- the non-interactive installer flow completes cleanly.
        self.assertEqual(
            result.returncode, 0,
            "AC8: non-interactive installer-flow invocation with --yes "
            f"must exit 0; got exit={result.returncode} "
            f"stdout={result.stdout!r} stderr={result.stderr!r}",
        )


if __name__ == "__main__":
    unittest.main()
