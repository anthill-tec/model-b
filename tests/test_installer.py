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


def _write_fake_executable(bin_dir: str, name: str, script_body: str) -> Path:
    """Write an executable shell-script fixture at ``bin_dir/name`` -- the
    dependency-injection seam pinned for CR-MDB-014 C2 §S4 pre-flight
    tests: fake `uv`/`sandesh` binaries on an isolated tmp PATH, so
    detection/install is exercised with zero real network or install
    side effects."""
    path = Path(bin_dir) / name
    path.write_text(script_body, encoding="utf-8")
    path.chmod(0o755)
    return path


# Fake `uv` fixture: `uv tool install <pkg>` writes an invocation marker
# (when $FAKE_UV_INSTALL_MARKER is set) instead of touching the network;
# any other invocation (e.g. `--version`) just exits 0.
_FAKE_UV_SCRIPT = (
    "#!/bin/sh\n"
    'if [ "$1" = "tool" ] && [ "$2" = "install" ]; then\n'
    '    if [ -n "$FAKE_UV_INSTALL_MARKER" ]; then\n'
    '        printf \'%s\\n\' "$*" > "$FAKE_UV_INSTALL_MARKER"\n'
    "    fi\n"
    "    exit 0\n"
    "fi\n"
    'echo "uv 0.0.0-fake"\n'
    "exit 0\n"
)

# Fake `sandesh` fixture: presence on PATH is all that's needed for
# detection-truthfulness tests -- it is never actually invoked for
# anything besides being *found*.
_FAKE_SANDESH_SCRIPT = (
    "#!/bin/sh\n"
    'echo "sandesh-relay 0.0.0-fake"\n'
    "exit 0\n"
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


# --------------------------------------------------------------------
# CR-MDB-014 cycle C2 -- §S4 dependency pre-flight (AC4). New tests only;
# everything above this point is untouched C1 (§S2/§S3, AC1/AC3/AC8).
# --------------------------------------------------------------------


class DependencyPreflightReportingTest(unittest.TestCase):
    """AC4 items 1+2 -- pre-flight runs as installer-flow stage 1 and
    REPORTS each of `uv`/Sandesh/Crucible with a detected/absent verdict
    on stdout, via the machine-greppable line

        deps: uv=<verdict> sandesh=<verdict> crucible=<verdict>

    (verdict in {"detected", "absent"} for uv/crucible here; Sandesh also
    gets "installed" -- see SandeshAbsentInstallViaUvShimTest). Per the
    dispatch's item 5: `[deps]` TOML persistence lands with the
    install.toml write in C3/§S6 -- C2 owns the stdout report only,
    pinned by the negative install.toml-must-not-exist-yet check below.
    """

    def setUp(self):
        self._tmp_home = tempfile.mkdtemp(prefix="modelb-axi-home-")
        self._tmp_bin = tempfile.mkdtemp(prefix="modelb-axi-fakebin-")

    def tearDown(self):
        shutil.rmtree(self._tmp_home, ignore_errors=True)
        shutil.rmtree(self._tmp_bin, ignore_errors=True)

    def test_all_three_deps_reported_with_exact_detected_and_absent_verdicts(self):
        _write_fake_executable(self._tmp_bin, "uv", _FAKE_UV_SCRIPT)
        _write_fake_executable(self._tmp_bin, "sandesh", _FAKE_SANDESH_SCRIPT)
        # No fake `crucible` binary is ever provided in this whole file --
        # Crucible ships no installer yet per DN §4, so it is always absent.
        result = _run_module(
            "--yes", "--harnesses", "claude-code",
            "--modelb-home", self._tmp_home,
            env_overrides={"PATH": self._tmp_bin},
        )
        # POSITIVE -- exact machine-greppable deps line, all three named.
        self.assertIn(
            "deps: uv=detected sandesh=detected crucible=absent",
            result.stdout,
            "AC4: pre-flight must report all three deps with exact "
            f"detected/absent verdicts; got exit={result.returncode} "
            f"stdout={result.stdout!r} stderr={result.stderr!r}",
        )
        self.assertEqual(
            result.returncode, 0,
            f"AC4: a fully-detected pre-flight must not fail the run; "
            f"got exit={result.returncode} stderr={result.stderr!r}",
        )
        # NEGATIVE -- [deps] persistence is C3/§S6's install.toml write,
        # not C2's; the stdout report is what C2 owns (dispatch item 5).
        self.assertFalse(
            (Path(self._tmp_home) / "install.toml").exists(),
            "AC4/§S4 (C2 scope): install.toml persistence lands with "
            "§S6 in C3 -- C2 must not write it yet",
        )

    def test_sandesh_absent_from_path_reported_as_absent_not_detected(self):
        _write_fake_executable(self._tmp_bin, "uv", _FAKE_UV_SCRIPT)
        # No fake `sandesh` written -- the isolated PATH (only this tmp
        # bin dir, never the host's real PATH) guarantees truthful
        # absence regardless of what's installed on the machine running
        # this test.
        result = _run_module(
            "--yes", "--harnesses", "claude-code",
            "--modelb-home", self._tmp_home,
            env_overrides={"PATH": self._tmp_bin},
        )
        self.assertIn(
            "deps: uv=detected sandesh=absent crucible=absent",
            result.stdout,
            "AC4: with no sandesh binary on PATH, pre-flight must report "
            f"sandesh=absent truthfully (not detected); got "
            f"stdout={result.stdout!r} stderr={result.stderr!r}",
        )

    def test_preflight_deps_report_precedes_harness_targeting_stage(self):
        """Pre-flight is stage 1 of the installer flow (§S3 stage order,
        dispatch item 1) -- its deps report must appear in stdout before
        the stage-2 harness-targeting announcement."""
        _write_fake_executable(self._tmp_bin, "uv", _FAKE_UV_SCRIPT)
        _write_fake_executable(self._tmp_bin, "sandesh", _FAKE_SANDESH_SCRIPT)
        result = _run_module(
            "--yes", "--harnesses", "claude-code",
            "--modelb-home", self._tmp_home,
            env_overrides={"PATH": self._tmp_bin},
        )
        stdout = result.stdout
        deps_index = stdout.find("deps: uv=")
        harness_index = stdout.lower().find("harness targeting")
        self.assertNotEqual(
            deps_index, -1,
            f"AC4: deps report line not found in stdout={stdout!r}",
        )
        self.assertNotEqual(
            harness_index, -1,
            f"§S3: harness-targeting stage announcement not found in "
            f"stdout={stdout!r}",
        )
        self.assertLess(
            deps_index, harness_index,
            "§S4: pre-flight (deps report) must run as stage 1, before "
            f"the harness-targeting stage; stdout={stdout!r}",
        )


class CrucibleAbsentWarnsRecordsAbsentAndDeploysNothingTest(unittest.TestCase):
    """AC4 item 3 -- Crucible absent must WARN naming Crucible's OWN
    installer (never hand-deploy their assets, per DN §4 / decision D),
    record `crucible=absent` on the deps line, and deploy ZERO Crucible
    files anywhere under the sandbox MODELB_HOME tree (grep gate:
    `*-crucible.py`, `_crucible_axi.py`, `toon.py`)."""

    _FORBIDDEN_CRUCIBLE_GLOBS = ("*-crucible.py", "_crucible_axi.py", "toon.py")

    def setUp(self):
        self._tmp_home = tempfile.mkdtemp(prefix="modelb-axi-home-")
        self._tmp_bin = tempfile.mkdtemp(prefix="modelb-axi-fakebin-")

    def tearDown(self):
        shutil.rmtree(self._tmp_home, ignore_errors=True)
        shutil.rmtree(self._tmp_bin, ignore_errors=True)

    def test_crucible_absent_warns_names_own_installer_and_deploys_zero_files(self):
        _write_fake_executable(self._tmp_bin, "uv", _FAKE_UV_SCRIPT)
        _write_fake_executable(self._tmp_bin, "sandesh", _FAKE_SANDESH_SCRIPT)
        result = _run_module(
            "--yes", "--harnesses", "claude-code",
            "--modelb-home", self._tmp_home,
            env_overrides={"PATH": self._tmp_bin},
        )
        combined = result.stdout + result.stderr
        # POSITIVE -- warning names Crucible.
        self.assertIn(
            "Crucible", combined,
            f"AC4: Crucible-absent warning must name Crucible; got "
            f"stdout={result.stdout!r} stderr={result.stderr!r}",
        )
        # POSITIVE -- and points at THEIR OWN installer (never "we'll
        # deploy it for you").
        self.assertRegex(
            combined.lower(),
            r"crucible.{0,80}(its own|their own|own installer)",
            "AC4: the Crucible warning must name THEIR OWN installer "
            f"(never hand-deploy their assets); got combined={combined!r}",
        )
        # POSITIVE -- deps line records crucible as absent.
        self.assertIn(
            "deps: uv=detected sandesh=detected crucible=absent",
            result.stdout,
            f"AC4: crucible must be recorded absent on the deps line; "
            f"got stdout={result.stdout!r}",
        )
        # NEGATIVE / bound -- zero Crucible files deployed under the
        # sandbox MODELB_HOME, now AND as a standing regression guard
        # once §S6 deploy lands in C3.
        home_root = Path(self._tmp_home)
        found = []
        for pattern in self._FORBIDDEN_CRUCIBLE_GLOBS:
            found.extend(str(p) for p in home_root.rglob(pattern))
        self.assertEqual(
            found, [],
            "AC4: zero Crucible files may ever be deployed by us under "
            f"the sandbox MODELB_HOME; found={found}",
        )


class SandeshAbsentInstallViaUvShimTest(unittest.TestCase):
    """AC4 item 4 -- Sandesh absent + `--yes`.

    PINNED CONTRACT (chosen from the dispatch's two offered alternatives):
    in non-interactive `--yes` mode the flow PROACTIVELY INVOKES the
    install THROUGH THE PROVIDER'S OWN METHOD (`uv tool install
    sandesh-relay`), rather than only recording `sandesh = "absent"` with
    a warning. Chosen because DN §4 explicitly differentiates the two
    deps asymmetrically: Sandesh gets "propose + install via the
    provider's own method", while Crucible gets "WARN with instructions"
    only (because Crucible ships no installer yet) -- that asymmetry
    only makes sense if Sandesh's path is a real, active install
    attempt, and `--yes` (per AC2/AC8, "end-to-end"/"skippable via
    flags") is what supplies the implicit confirm that DN §4's "on
    confirm" wording requires.

    Exercised with zero real network/install side effects: a fake `uv`
    shim on an isolated tmp PATH writes an invocation marker (instead of
    touching the network) when called as `uv tool install
    sandesh-relay`. We assert the shim actually RECEIVED that exact
    invocation (mock verification), not merely that the run finished.
    """

    def setUp(self):
        self._tmp_home = tempfile.mkdtemp(prefix="modelb-axi-home-")
        self._tmp_bin = tempfile.mkdtemp(prefix="modelb-axi-fakebin-")
        marker_fd, self._marker_path = tempfile.mkstemp(
            prefix="fake-uv-install-marker-",
        )
        os.close(marker_fd)
        os.remove(self._marker_path)  # must NOT exist yet -- proves invocation

    def tearDown(self):
        shutil.rmtree(self._tmp_home, ignore_errors=True)
        shutil.rmtree(self._tmp_bin, ignore_errors=True)
        if os.path.exists(self._marker_path):
            os.remove(self._marker_path)

    def test_sandesh_absent_yes_invokes_uv_tool_install_sandesh_relay_via_shim(self):
        _write_fake_executable(self._tmp_bin, "uv", _FAKE_UV_SCRIPT)
        # No fake `sandesh` -- absent, which must trigger the proactive
        # install path under this chosen contract.
        result = _run_module(
            "--yes", "--harnesses", "claude-code",
            "--modelb-home", self._tmp_home,
            env_overrides={
                "PATH": self._tmp_bin,
                "FAKE_UV_INSTALL_MARKER": self._marker_path,
            },
        )
        # MOCK VERIFICATION -- assert the fake `uv` shim actually
        # RECEIVED the install invocation (not just that the run exited
        # cleanly).
        self.assertTrue(
            os.path.exists(self._marker_path),
            "AC4 (chosen contract): sandesh absent + --yes must invoke "
            "the install THROUGH the fake `uv` shim on PATH -- no "
            f"marker file was written; stdout={result.stdout!r} "
            f"stderr={result.stderr!r}",
        )
        marker_contents = Path(self._marker_path).read_text(encoding="utf-8")
        self.assertIn(
            "tool install sandesh-relay", marker_contents,
            "AC4: the shim must have been invoked as exactly `uv tool "
            f"install sandesh-relay`; got marker contents={marker_contents!r}",
        )
        # POSITIVE -- deps line reflects the proactive install, never a
        # silent "absent".
        self.assertIn(
            "deps: uv=detected sandesh=installed crucible=absent",
            result.stdout,
            "AC4: after a successful proactive install via the shim, the "
            f"deps line must report sandesh=installed; got "
            f"stdout={result.stdout!r} stderr={result.stderr!r}",
        )
        self.assertEqual(
            result.returncode, 0,
            f"AC4: a successful proactive sandesh install must not fail "
            f"the run; got exit={result.returncode} stderr={result.stderr!r}",
        )


class UvAbsentBootstrapFailureTest(unittest.TestCase):
    """AC4 item 6 -- `uv` itself absent is the pre-flight FAILURE mode
    (DN: uv is the bootstrap dependency everything else rides on) --
    exit non-zero with bootstrap instructions naming `uv`, never a soft
    "absent" verdict that lets the flow continue as if nothing were
    wrong."""

    def setUp(self):
        self._tmp_home = tempfile.mkdtemp(prefix="modelb-axi-home-")
        self._tmp_bin = tempfile.mkdtemp(prefix="modelb-axi-fakebin-")

    def tearDown(self):
        shutil.rmtree(self._tmp_home, ignore_errors=True)
        shutil.rmtree(self._tmp_bin, ignore_errors=True)

    def test_uv_absent_from_path_exits_nonzero_with_bootstrap_instructions(self):
        # Isolated PATH with NO `uv` (and no `sandesh`) -- guarantees
        # absence regardless of the host running this test (which does
        # have a real `uv` on its real PATH, per PackageSkeletonTest's
        # integration probe).
        result = _run_module(
            "--yes", "--harnesses", "claude-code",
            "--modelb-home", self._tmp_home,
            env_overrides={"PATH": self._tmp_bin},
        )
        # POSITIVE -- non-zero exit is the failure signal.
        self.assertNotEqual(
            result.returncode, 0,
            "AC4: with `uv` absent from PATH, the installer flow must "
            f"exit non-zero; got exit={result.returncode} "
            f"stdout={result.stdout!r} stderr={result.stderr!r}",
        )
        combined = (result.stdout + result.stderr).lower()
        # POSITIVE -- bootstrap instructions actually name `uv`.
        self.assertIn(
            "uv", combined,
            f"AC4: uv-absent failure must mention `uv`; got "
            f"combined={combined!r}",
        )
        self.assertRegex(
            combined,
            r"(install|bootstrap).{0,40}uv|uv.{0,40}(install|bootstrap)",
            "AC4: uv-absent failure must print bootstrap instructions "
            f"naming `uv`; got combined={combined!r}",
        )
        # NEGATIVE -- must not fabricate a deps report and proceed as if
        # uv were present.
        self.assertNotIn(
            "deps: uv=detected", result.stdout,
            f"AC4: must not report uv=detected when uv is absent from "
            f"PATH; got stdout={result.stdout!r}",
        )


if __name__ == "__main__":
    unittest.main()
