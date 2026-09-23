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

import hashlib
import os
import re
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


def _decode_envelope(stdout: str) -> dict:
    """Decode a `modelb_axi` TOON AXI envelope printed on stdout, using
    the package's OWN codec (CR-MDB-033 §S6 migration: the `deps:`
    verdicts, `_extract_selected_harnesses`, and the already-installed
    notice read installer FACTS from here now, not from stdout text --
    per the CR's own AC)."""
    from modelb_axi.toon import decode
    return decode(stdout)


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
        # POSITIVE -- CR-MDB-033 §S6 migration: this is a PROSE check
        # (does the run mention the installer flow) -- stdout carries
        # nothing but the envelope now, so it reads stderr.
        self.assertIn(
            "installer", result.stderr.lower(),
            "AC3: with no install.toml under --modelb-home, stderr must "
            f"mention the installer flow; got exit={result.returncode} "
            f"stdout={result.stdout!r} stderr={result.stderr!r}",
        )
        # NEGATIVE -- must NOT claim to be in scaffold mode / name CR-MDB-013.
        self.assertNotIn(
            "CR-MDB-013", result.stderr,
            "AC3: with no install.toml present, the run must NOT enter "
            f"scaffold mode; got stderr={result.stderr!r}",
        )

    def test_missing_install_toml_enters_installer_flow_via_modelb_home_env_var(self):
        """Confirms $MODELB_HOME (the env var, not just --modelb-home)
        also resolves the config seam per DN §3."""
        result = _run_module(
            "--yes", "--harnesses", "claude-code",
            env_overrides={"MODELB_HOME": self._tmp_home},
        )
        self.assertIn(
            "installer", result.stderr.lower(),
            "AC3: MODELB_HOME env var (no --modelb-home flag) with no "
            f"install.toml must still enter installer flow; got "
            f"exit={result.returncode} stdout={result.stdout!r} "
            f"stderr={result.stderr!r}",
        )

    def test_valid_install_toml_enters_scaffold_mode_proposing_init(self):
        """CR-MDB-013 sanctioned 014-gate amendment: retargets the C1 v1
        stub pin (which named CR-MDB-013 literally) to the real
        scaffold-mode entry contract pinned by CR-MDB-013 §S2 --
        tests/test_scaffold.py::ScaffoldModeEntryTest -- a scaffold-mode
        banner on stdout that PROPOSES running `init`, exiting 0
        non-interactively. The literal "CR-MDB-013" stub string is
        dropped: the real banner is not required to name the CR."""
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
        # POSITIVE -- scaffold-mode entry exits 0 when install.toml is
        # present.
        self.assertEqual(
            result.returncode, 0,
            "AC3/S2: scaffold-mode entry must exit 0 when install.toml is "
            f"present; got exit={result.returncode} stdout={result.stdout!r} "
            f"stderr={result.stderr!r}",
        )
        self.assertIn(
            "scaffold", result.stderr.lower(),
            "AC3/S2: with install.toml present, launch must banner scaffold "
            f"mode; got stdout={result.stdout!r} stderr={result.stderr!r}",
        )
        self.assertIn(
            "init", result.stderr.lower(),
            "AC3/S2: the scaffold-mode banner must propose running `init`; "
            f"got stdout={result.stdout!r} stderr={result.stderr!r}",
        )
        # NEGATIVE -- must NOT re-run the installer flow once scaffolded.
        # CR-MDB-033 §S6 migration: this absence guard now reads
        # stderr (stdout carries nothing but the envelope, so checking
        # stdout would be vacuous once §S6 lands).
        self.assertNotIn(
            "installer flow", result.stderr.lower(),
            "AC3: with install.toml present, the run must NOT re-enter the "
            f"installer flow; got stderr={result.stderr!r}",
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
        # POSITIVE -- CR-MDB-033 §S6 migration: the deps verdicts are an
        # installer FACT, read from the envelope's `deps` field, never
        # scraped from stdout text.
        axi = _decode_envelope(result.stdout).get("axi", {})
        self.assertEqual(
            axi.get("deps"),
            {"uv": "detected", "sandesh": "detected", "crucible": "absent"},
            "AC4: the envelope's deps field must report all three deps "
            f"with exact detected/absent verdicts; got exit={result.returncode} "
            f"axi={axi!r} stdout={result.stdout!r} stderr={result.stderr!r}",
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
        # CR-MDB-033 §S6 migration: this checks the TRUTHFUL PRE-
        # REMEDIATION detection line specifically (AC4: "records ...
        # detection truthfully" BEFORE any remediation mutates the
        # picture) -- not the envelope's `deps` field, which is the
        # FINAL post-remediation verdict and would legitimately read
        # sandesh=installed here once the proactive-install attempt
        # against the shared fake `uv` shim succeeds (this fixture sets
        # no FAKE_UV_INSTALL_MARKER and doesn't care about that outcome
        # -- only that the FIRST report was truthful). This is a PROSE/
        # moment-in-time text check, so it reads stderr.
        self.assertIn(
            "deps: uv=detected sandesh=absent crucible=absent", result.stderr,
            "AC4: with no sandesh binary on PATH, pre-flight's PRE-"
            f"remediation report must state sandesh=absent truthfully "
            f"(not detected); got stderr={result.stderr!r}",
        )

    def test_preflight_deps_report_precedes_harness_targeting_stage(self):
        """Pre-flight is stage 1 of the installer flow (§S3 stage order,
        dispatch item 1) -- its deps report must appear in stderr before
        the stage-2 harness-targeting announcement (CR-MDB-033 §S6
        migration: this is an ORDERING check over human prose, which now
        lives entirely on stderr, not stdout)."""
        _write_fake_executable(self._tmp_bin, "uv", _FAKE_UV_SCRIPT)
        _write_fake_executable(self._tmp_bin, "sandesh", _FAKE_SANDESH_SCRIPT)
        result = _run_module(
            "--yes", "--harnesses", "claude-code",
            "--modelb-home", self._tmp_home,
            env_overrides={"PATH": self._tmp_bin},
        )
        stderr = result.stderr
        deps_index = stderr.find("deps: uv=")
        harness_index = stderr.lower().find("harness targeting")
        self.assertNotEqual(
            deps_index, -1,
            f"AC4: deps report line not found in stderr={stderr!r}",
        )
        self.assertNotEqual(
            harness_index, -1,
            f"§S3: harness-targeting stage announcement not found in "
            f"stderr={stderr!r}",
        )
        self.assertLess(
            deps_index, harness_index,
            "§S4: pre-flight (deps report) must run as stage 1, before "
            f"the harness-targeting stage; stderr={stderr!r}",
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
        # CR-MDB-033 §S6 migration: the warning is PROSE -- it must live
        # entirely on stderr now (stdout carries nothing but the envelope).
        combined = result.stderr
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
        # POSITIVE -- CR-MDB-033 §S6 migration: the deps FACT is read
        # from the envelope, not scraped from a stdout deps: line.
        axi = _decode_envelope(result.stdout).get("axi", {})
        self.assertEqual(
            axi.get("deps"),
            {"uv": "detected", "sandesh": "detected", "crucible": "absent"},
            f"AC4: crucible must be recorded absent in the envelope's deps "
            f"field; got axi={axi!r} stdout={result.stdout!r}",
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
        # POSITIVE -- CR-MDB-033 §S6 migration: the deps FACT (the
        # proactive install's final verdict, never a silent "absent") is
        # read from the envelope, not scraped from a stdout deps: line.
        axi = _decode_envelope(result.stdout).get("axi", {})
        self.assertEqual(
            axi.get("deps"),
            {"uv": "detected", "sandesh": "installed", "crucible": "absent"},
            "AC4: after a successful proactive install via the shim, the "
            f"envelope's deps field must report sandesh=installed; got "
            f"axi={axi!r} stdout={result.stdout!r} stderr={result.stderr!r}",
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
        # uv were present. CR-MDB-033 §S6 migration: this absence guard
        # must assert against STDERR (where every `deps:` line lives now,
        # §S6's own table) -- checking stdout would be vacuously true
        # once stdout carries nothing but the envelope, defeating the
        # guard's purpose of catching a fabricated report.
        self.assertNotIn(
            "deps: uv=detected", result.stderr,
            f"AC4: must not report uv=detected when uv is absent from "
            f"PATH; got stderr={result.stderr!r}",
        )


# CR-MDB-014 cycle C3 -- §S5 harness targeting + §S6 deploy engine (AC2,
# AC3 regression against a REAL deploy, AC5 idempotent-upgrade + hand-
# modified detection, install.toml-written-last atomicity). New tests
# only; everything above this point is untouched C1/C2 (§S2-S4,
# AC1/AC3-stub/AC4/AC8).
#
# Deploy-target sandboxing (repo-local rule + DN §7): production code's
# per-harness/Vercel-store deploy roots default to the real user home
# (~/.agents, ~/.claude) -- UNTESTED BY DESIGN. Every test below pins a
# `--target-root <dir>` flag that overrides those roots to a tmp sandbox,
# so the deploy engine under test NEVER touches the real trees (on top
# of the module-level AC7 mtime guard already in force for this whole
# file). A `MODELB_TARGET_ROOT` env var is the documented flag/env
# alternative (mirroring --modelb-home/MODELB_HOME) but is not itself
# exercised here -- these tests pin the flag form only.
#
# Roster-to-harness-id mapping pinned for this cycle: the probed binary
# name differs from the harness id in exactly one case --
#   claude   -> "claude-code"
#   hermes   -> "hermes"
#   pi       -> "pi"
#   opencode -> "opencode"
#
# New flags pinned by this cycle's tests: `--target-root`, `--reinstall`
# (forces a run with an existing install.toml back into the installer
# flow instead of the scaffold stub), `--force-managed` (overwrite a
# hash-mismatched managed file and update its manifest entry).

HARNESS_ROSTER_IDS = ["claude-code", "hermes", "pi", "opencode"]

_FAKE_HARNESS_BIN_SCRIPT = (
    "#!/bin/sh\n"
    'echo "fake-harness-binary"\n'
    "exit 0\n"
)


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _package_version() -> str:
    """Read `__version__` straight from modelb_axi/__init__.py's source
    text -- avoids relying on the repo root being importable in-process
    for this subprocess-driven test module."""
    text = MODULE_INIT.read_text(encoding="utf-8")
    match = re.search(r'__version__\s*=\s*"([^"]+)"', text)
    if not match:
        raise AssertionError(f"could not find __version__ in {MODULE_INIT}")
    return match.group(1)


def _snapshot_relpaths(root: Path):
    """Set of every file/symlink path under `root`, relative to `root` --
    used to prove a re-run touches nothing outside the manifest."""
    if not root.exists():
        return set()
    return {
        str(p.relative_to(root))
        for p in root.rglob("*")
        if p.is_file() or p.is_symlink()
    }


class HarnessTargetingTest(unittest.TestCase):
    """§S5 -- roster probe of claude/hermes/pi/opencode binaries on an
    isolated PATH; explicit --harnesses wins over the detected set;
    unknown harness names in --harnesses are rejected naming the valid
    roster."""

    def setUp(self):
        self._tmp_home = tempfile.mkdtemp(prefix="modelb-axi-home-")
        self._tmp_bin = tempfile.mkdtemp(prefix="modelb-axi-fakebin-")
        self._tmp_target_root = tempfile.mkdtemp(prefix="modelb-axi-target-")

    def tearDown(self):
        shutil.rmtree(self._tmp_home, ignore_errors=True)
        shutil.rmtree(self._tmp_bin, ignore_errors=True)
        shutil.rmtree(self._tmp_target_root, ignore_errors=True)

    @staticmethod
    def _extract_selected_harnesses(stdout: str) -> list:
        """CR-MDB-033 §S6 migration: the selected-harnesses FACT is read
        from the envelope's `harnesses` field, never scraped from a
        `harnesses selected:` stdout text line."""
        from modelb_axi.toon import decode
        axi = decode(stdout).get("axi", {})
        return list(axi.get("harnesses", []))

    def test_detected_roster_binaries_proposed_as_default_selection_without_harnesses_flag(self):
        _write_fake_executable(self._tmp_bin, "uv", _FAKE_UV_SCRIPT)
        _write_fake_executable(self._tmp_bin, "sandesh", _FAKE_SANDESH_SCRIPT)
        _write_fake_executable(self._tmp_bin, "claude", _FAKE_HARNESS_BIN_SCRIPT)
        _write_fake_executable(self._tmp_bin, "opencode", _FAKE_HARNESS_BIN_SCRIPT)
        # No "hermes"/"pi" binaries written -- must be excluded from the
        # detected set.
        result = _run_module(
            "--yes", "--modelb-home", self._tmp_home,
            "--target-root", self._tmp_target_root,
            env_overrides={"PATH": self._tmp_bin},
        )
        selected = self._extract_selected_harnesses(result.stdout)
        # POSITIVE -- exact detected set, roster order preserved.
        self.assertEqual(
            selected, ["claude-code", "opencode"],
            "§S5: with only `claude`+`opencode` binaries on PATH and no "
            "--harnesses flag, the proposed/selected set must be exactly "
            f"['claude-code', 'opencode']; got stdout={result.stdout!r} "
            f"stderr={result.stderr!r}",
        )
        self.assertEqual(
            result.returncode, 0,
            f"§S5: a clean detected-set run must exit 0; got "
            f"exit={result.returncode} stderr={result.stderr!r}",
        )

    def test_explicit_harnesses_flag_wins_over_detected_set(self):
        _write_fake_executable(self._tmp_bin, "uv", _FAKE_UV_SCRIPT)
        _write_fake_executable(self._tmp_bin, "sandesh", _FAKE_SANDESH_SCRIPT)
        # Detected set would be hermes+pi -- but explicit --harnesses
        # claude-code must win outright.
        _write_fake_executable(self._tmp_bin, "hermes", _FAKE_HARNESS_BIN_SCRIPT)
        _write_fake_executable(self._tmp_bin, "pi", _FAKE_HARNESS_BIN_SCRIPT)
        result = _run_module(
            "--yes", "--harnesses", "claude-code",
            "--modelb-home", self._tmp_home,
            "--target-root", self._tmp_target_root,
            env_overrides={"PATH": self._tmp_bin},
        )
        selected = self._extract_selected_harnesses(result.stdout)
        # POSITIVE -- explicit selection wins outright.
        self.assertEqual(
            selected, ["claude-code"],
            "§S5: explicit --harnesses claude-code must win over the "
            f"detected (hermes, pi) set; got selected={selected} "
            f"stdout={result.stdout!r}",
        )
        # NEGATIVE -- detected-but-not-selected harnesses must not leak in.
        self.assertNotIn("hermes", selected)
        self.assertNotIn("pi", selected)

    def test_unknown_harness_name_in_flag_exits_nonzero_naming_valid_roster(self):
        _write_fake_executable(self._tmp_bin, "uv", _FAKE_UV_SCRIPT)
        _write_fake_executable(self._tmp_bin, "sandesh", _FAKE_SANDESH_SCRIPT)
        result = _run_module(
            "--yes", "--harnesses", "bogus-harness",
            "--modelb-home", self._tmp_home,
            "--target-root", self._tmp_target_root,
            env_overrides={"PATH": self._tmp_bin},
        )
        combined = result.stdout + result.stderr
        # POSITIVE -- non-zero exit is the failure signal.
        self.assertNotEqual(
            result.returncode, 0,
            "§S5: an unknown harness name in --harnesses must exit "
            f"non-zero; got exit={result.returncode} combined={combined!r}",
        )
        # POSITIVE -- names the offending value AND the full valid roster.
        self.assertIn("bogus-harness", combined)
        for harness_id in HARNESS_ROSTER_IDS:
            self.assertIn(
                harness_id, combined,
                f"§S5: unknown-harness error must name the valid roster "
                f"(missing {harness_id!r}); got combined={combined!r}",
            )


class DeployEngineTest(unittest.TestCase):
    """§S6 -- manifest-driven deploy engine + install.toml config write
    (AC2 end-to-end), the AC3 regression guard against a REAL deploy,
    AC5 idempotent-upgrade + hand-modified-file detection, and the
    install.toml-written-last atomicity guarantee."""

    CRUCIBLE_SKILL_MD = REPO_ROOT / "skills-src" / "crucible" / "SKILL.md"

    def setUp(self):
        self._tmp_home = tempfile.mkdtemp(prefix="modelb-axi-home-")
        self._tmp_bin = tempfile.mkdtemp(prefix="modelb-axi-fakebin-")
        self._tmp_target_root = tempfile.mkdtemp(prefix="modelb-axi-target-")
        _write_fake_executable(self._tmp_bin, "uv", _FAKE_UV_SCRIPT)
        _write_fake_executable(self._tmp_bin, "sandesh", _FAKE_SANDESH_SCRIPT)

    def tearDown(self):
        # Undo any deliberately-broken permissions before cleanup so
        # rmtree can actually remove the tree.
        for root in (self._tmp_home, self._tmp_bin, self._tmp_target_root):
            for p in Path(root).rglob("*"):
                try:
                    p.chmod(0o700)
                except OSError:
                    continue
        shutil.rmtree(self._tmp_home, ignore_errors=True)
        shutil.rmtree(self._tmp_bin, ignore_errors=True)
        shutil.rmtree(self._tmp_target_root, ignore_errors=True)

    def _run_install(self, *extra_args, env_overrides=None):
        overrides = {"PATH": self._tmp_bin}
        if env_overrides:
            overrides.update(env_overrides)
        return _run_module(
            "--yes", "--harnesses", "claude-code",
            "--modelb-home", self._tmp_home,
            "--target-root", self._tmp_target_root,
            *extra_args,
            env_overrides=overrides,
        )

    def _store_skill_dir(self) -> Path:
        return Path(self._tmp_target_root) / ".agents" / "skills" / "crucible"

    def _harness_symlink(self) -> Path:
        return Path(self._tmp_target_root) / ".claude" / "skills" / "crucible"

    def _read_install_toml(self) -> dict:
        with open(Path(self._tmp_home) / "install.toml", "rb") as fh:
            return tomllib.load(fh)

    def test_end_to_end_install_deploys_crucible_skill_once_symlinked_and_writes_install_toml(self):
        result = self._run_install()
        self.assertEqual(
            result.returncode, 0,
            f"AC2: end-to-end installer run must exit 0; got "
            f"exit={result.returncode} stdout={result.stdout!r} "
            f"stderr={result.stderr!r}",
        )
        store_dir = self._store_skill_dir()
        store_skill_md = store_dir / "SKILL.md"
        # POSITIVE -- ONE copy in the harness-neutral Vercel store,
        # content matching the shipped skills-src/crucible/SKILL.md
        # exactly.
        self.assertTrue(
            store_skill_md.is_file(),
            f"AC2/§S6: {store_skill_md} must exist (Vercel-store deploy "
            f"of the crucible skill bundle); target_root listing="
            f"{list(Path(self._tmp_target_root).rglob('*'))}",
        )
        self.assertEqual(
            store_skill_md.read_text(encoding="utf-8"),
            self.CRUCIBLE_SKILL_MD.read_text(encoding="utf-8"),
            "AC2: the deployed crucible SKILL.md must match "
            "skills-src/crucible/SKILL.md byte-for-byte",
        )
        # POSITIVE -- the harness's skills dir gets a SYMLINK pointing at
        # the store copy, not a second physical copy.
        symlink_path = self._harness_symlink()
        self.assertTrue(
            symlink_path.is_symlink(),
            f"AC2/§S6: {symlink_path} must be a symlink into the Vercel "
            f"store (not a physical copy)",
        )
        self.assertEqual(
            symlink_path.resolve(), store_dir.resolve(),
            f"AC2: {symlink_path} must resolve to the store dir "
            f"{store_dir}; got {symlink_path.resolve()}",
        )
        # install.toml structure -- parsed via tomllib, not string greps.
        data = self._read_install_toml()
        install_section = data.get("install", {})
        self.assertEqual(
            install_section.get("version"), _package_version(),
            f"AC2: [install].version must match the package __version__ "
            f"({_package_version()!r}); got {install_section.get('version')!r}",
        )
        self.assertEqual(
            install_section.get("harnesses"), ["claude-code"],
            f"AC2: [install].harnesses must be exactly ['claude-code']; "
            f"got {install_section.get('harnesses')!r}",
        )
        self.assertEqual(
            Path(str(install_section.get("asset_root", ""))), REPO_ROOT,
            f"AC2: [install].asset_root must resolve to the package's "
            f"asset root ({REPO_ROOT}); got {install_section.get('asset_root')!r}",
        )
        self.assertEqual(
            data.get("deps"),
            {"uv": "detected", "sandesh": "detected", "crucible": "absent"},
            f"AC2: [deps] must persist the pre-flight verdicts exactly; "
            f"got {data.get('deps')!r}",
        )
        files_section = data.get("files")
        self.assertIsInstance(
            files_section, list,
            f"AC2: [[files]] must parse as a list of entries; got "
            f"{type(files_section)}",
        )
        self.assertGreaterEqual(
            len(files_section), 1,
            "AC2: [[files]] must record at least one deployed file entry",
        )
        skill_entries = [
            e for e in files_section
            if isinstance(e, dict) and str(e.get("path", "")).endswith("crucible/SKILL.md")
        ]
        self.assertEqual(
            len(skill_entries), 1,
            f"AC2: exactly one [[files]] entry for the deployed "
            f"crucible/SKILL.md; got entries={files_section!r}",
        )
        expected_hash = _sha256_file(store_skill_md)
        self.assertEqual(
            skill_entries[0].get("sha256"), expected_hash,
            f"AC2: the manifest sha256 for crucible/SKILL.md must match "
            f"its actual deployed content hash ({expected_hash}); got "
            f"{skill_entries[0].get('sha256')!r}",
        )

    def test_second_launch_after_real_install_enters_scaffold_mode_naming_cr_mdb_013(self):
        first = self._run_install()
        self.assertEqual(
            first.returncode, 0,
            f"setup precondition: the first install must succeed; got "
            f"exit={first.returncode} stderr={first.stderr!r}",
        )
        second = _run_module("--yes", "--modelb-home", self._tmp_home)
        # POSITIVE -- AC3, exercised against a REAL deploy-written
        # install.toml (not a hand-authored stub as in C1's
        # StateDetectionTest). CR-MDB-033 §S6 migration: the
        # already-installed FACT is read from the envelope's `outcome`,
        # not scraped from a "CR-MDB-013" stdout text mention.
        self.assertEqual(
            second.returncode, 0,
            f"AC3: scaffold-mode stub must exit 0; got "
            f"exit={second.returncode} stdout={second.stdout!r}",
        )
        axi = _decode_envelope(second.stdout).get("axi", {})
        self.assertEqual(
            axi.get("outcome"), "already_installed",
            f"AC3/CR-MDB-033 §S6: with a REAL install.toml on disk from "
            f"a completed install, a second launch's envelope outcome must "
            f"be 'already_installed'; got axi={axi!r} stdout={second.stdout!r}",
        )
        self.assertTrue(
            axi.get("ok"),
            f"AC3/CR-MDB-033 §S6: the already-installed envelope must "
            f"carry ok=true; got axi={axi!r}",
        )
        # PROSE -- the human notice (naming CR-MDB-013) is on stderr now.
        self.assertIn(
            "CR-MDB-013", second.stderr,
            f"AC3: with a REAL install.toml on disk from a completed "
            f"install, a second launch must enter scaffold mode naming "
            f"CR-MDB-013 on stderr; got stderr={second.stderr!r}",
        )
        # NEGATIVE -- must not re-run the installer flow. CR-MDB-033 §S6
        # migration: this absence guard now reads stderr (stdout carries
        # nothing but the envelope, so checking stdout would be vacuous).
        self.assertNotIn("installer flow", second.stderr.lower())

    def test_reinstall_run_is_noop_when_no_managed_files_changed(self):
        first = self._run_install()
        self.assertEqual(
            first.returncode, 0,
            f"precondition: first install must succeed; stderr={first.stderr!r}",
        )
        before_data = self._read_install_toml()
        before_hashes = {e["path"]: e["sha256"] for e in before_data["files"]}
        before_tree = _snapshot_relpaths(Path(self._tmp_target_root))

        second = self._run_install("--reinstall")
        self.assertEqual(
            second.returncode, 0,
            f"AC5: an idempotent --reinstall run must exit 0; got "
            f"exit={second.returncode} stderr={second.stderr!r}",
        )
        after_data = self._read_install_toml()
        after_hashes = {e["path"]: e["sha256"] for e in after_data["files"]}
        # POSITIVE -- identical hashes, identical manifest entry count.
        self.assertEqual(
            after_hashes, before_hashes,
            f"AC5: a second identical --reinstall run must leave every "
            f"managed file's hash unchanged; before={before_hashes!r} "
            f"after={after_hashes!r}",
        )
        after_tree = _snapshot_relpaths(Path(self._tmp_target_root))
        # NEGATIVE / bound -- nothing outside the manifest (no new files,
        # no removed files) appears under target_root.
        self.assertEqual(
            after_tree, before_tree,
            f"AC5: a no-op reinstall must never touch paths outside the "
            f"manifest; before={sorted(before_tree)} after={sorted(after_tree)}",
        )

    def test_hand_modified_managed_file_detected_and_not_silently_overwritten(self):
        first = self._run_install()
        self.assertEqual(
            first.returncode, 0,
            f"precondition: first install must succeed; stderr={first.stderr!r}",
        )
        store_skill_md = self._store_skill_dir() / "SKILL.md"
        marker = "\n<!-- hand-edited by test, must not be silently clobbered -->\n"
        original_content = store_skill_md.read_text(encoding="utf-8")
        store_skill_md.write_text(original_content + marker, encoding="utf-8")

        second = self._run_install("--reinstall")
        combined = second.stdout + second.stderr
        # POSITIVE -- the hand edit must survive: no silent overwrite.
        current_content = store_skill_md.read_text(encoding="utf-8")
        self.assertIn(
            marker, current_content,
            "AC5: a hand-modified managed file must NOT be silently "
            f"overwritten without --force-managed; content after "
            f"reinstall={current_content!r}",
        )
        # POSITIVE -- detection surfaces via non-zero exit OR an explicit
        # skip-with-warning naming the file (dispatch-pinned disjunction).
        self.assertTrue(
            second.returncode != 0 or re.search(r"skip", combined, re.IGNORECASE),
            "AC5: a hash-mismatched managed file must be surfaced as "
            "either a non-zero exit or an explicit skip-with-warning; "
            f"got exit={second.returncode} combined={combined!r}",
        )
        self.assertIn(
            "SKILL.md", combined,
            f"AC5: the hash-mismatch detection must name the affected "
            f"file; got combined={combined!r}",
        )
        # NEGATIVE (CR-MDB-033 §S3 regression guard) -- a hash-mismatched
        # MANAGED file (recorded in the prior manifest) must keep using
        # the existing hand-modified-managed vocabulary; the CR-MDB-033
        # "unmanaged:" wording is reserved for files ABSENT from the
        # manifest entirely (AC3) and must never leak into this path.
        self.assertNotIn(
            "unmanaged:", combined,
            "CR-MDB-033 §S3: a hash-mismatched MANAGED file must never be "
            "reported via the 'unmanaged:' wording reserved for files "
            f"absent from the manifest; got combined={combined!r}",
        )

    def test_force_managed_flag_overwrites_hand_modified_file_and_updates_manifest(self):
        first = self._run_install()
        self.assertEqual(
            first.returncode, 0,
            f"precondition: first install must succeed; stderr={first.stderr!r}",
        )
        store_skill_md = self._store_skill_dir() / "SKILL.md"
        original_content = store_skill_md.read_text(encoding="utf-8")
        store_skill_md.write_text(
            original_content + "\n<!-- clobber me -->\n", encoding="utf-8",
        )

        second = self._run_install("--reinstall", "--force-managed")
        self.assertEqual(
            second.returncode, 0,
            f"AC5: --force-managed must overwrite cleanly and exit 0; "
            f"got exit={second.returncode} stderr={second.stderr!r}",
        )
        # POSITIVE -- content restored to the package's source exactly.
        restored_content = store_skill_md.read_text(encoding="utf-8")
        self.assertEqual(
            restored_content, original_content,
            "AC5: --force-managed must overwrite the hand-modified file "
            "back to the package's source content",
        )
        # POSITIVE -- manifest hash updated to match the restored content.
        data = self._read_install_toml()
        skill_entries = [
            e for e in data["files"]
            if str(e.get("path", "")).endswith("crucible/SKILL.md")
        ]
        self.assertEqual(len(skill_entries), 1)
        self.assertEqual(
            skill_entries[0]["sha256"], _sha256_file(store_skill_md),
            "AC5: the manifest entry's sha256 must be updated to match "
            "the --force-managed-restored file",
        )
        # NEGATIVE (CR-MDB-033 §S3 regression guard) -- same vocabulary
        # guard as the hand-modified-detection test above: this file WAS
        # in the manifest, so the existing --force-managed message
        # applies, never the new unmanaged-file wording (AC3).
        combined = second.stdout + second.stderr
        self.assertNotIn(
            "unmanaged:", combined,
            "CR-MDB-033 §S3: --force-managed overwriting a MANAGED "
            "hand-modified file must never be reported via the "
            f"'unmanaged:' wording; got combined={combined!r}",
        )

    def test_deploy_failure_leaves_no_install_toml_atomicity(self):
        # Force a deploy-stage failure: pre-create the store parent dir
        # unwritable, so the crucible-skill copy step fails partway
        # through, without ever reaching the install.toml write.
        broken_parent = Path(self._tmp_target_root) / ".agents" / "skills"
        broken_parent.mkdir(parents=True, exist_ok=True)
        broken_parent.chmod(0o000)
        try:
            result = self._run_install()
            combined = result.stdout + result.stderr
            # GUARD -- this failure must come from the deploy engine
            # actually attempting (and failing at) the write, not from
            # --target-root being an unrecognized flag; otherwise this
            # test would pass vacuously before §S6 exists at all.
            self.assertNotIn(
                "unrecognized arguments", combined,
                "atomicity test precondition: --target-root must be a "
                f"recognized flag reaching the deploy stage; got "
                f"combined={combined!r}",
            )
            # POSITIVE -- the broken deploy target must fail the run.
            self.assertNotEqual(
                result.returncode, 0,
                f"atomicity: a deploy failure (unwritable target subdir) "
                f"must exit non-zero; got exit={result.returncode} "
                f"stdout={result.stdout!r} stderr={result.stderr!r}",
            )
        finally:
            broken_parent.chmod(0o700)
        # POSITIVE -- install.toml is written LAST: on any deploy
        # failure, no install.toml must exist (state stays "not
        # installed").
        self.assertFalse(
            (Path(self._tmp_home) / "install.toml").exists(),
            "atomicity: install.toml must never exist after a failed "
            "deploy (it is written LAST, only on full success)",
        )


if __name__ == "__main__":
    unittest.main()
