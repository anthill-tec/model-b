"""RED-phase tests for CR-MDB-013 cycle C1 (scaffold flow entry + flags +
dry-run, §S2): the `modelb-axi init` subcommand and its flags, the
scaffold-mode bare-invocation banner, the `--dry-run` empty-target +
TOON-envelope contract, the install.toml-vs-`--harnesses` seam, and a
stdlib-only import guard over the `modelb_axi` package.

Written before any of §S2's production code lands (`init` is not yet a
recognised subcommand on `cli.py`), so every behavioural test below is
expected to FAIL against the current tree -- either a clean argparse usage
error (`init` unrecognised) or, once flags partially exist, a missing
flag/behavior. `StdlibOnlyImportScanTest` is a structural forward-guard
(scans whatever `modelb_axi/*.py` modules currently exist); it may
legitimately PASS today since the package is already stdlib-only and no new
module exists yet to violate it -- see the RED-run report for why this one
is not a spec-behavior assertion.

All invocations are subprocess probes (`python -m modelb_axi ...`) against
tmp sandboxes (`$MODELB_HOME`, `--target`) -- per the CR's binding rule and
DN-scaffold-packaging.md §7, nothing here ever deploys into the real
`~/.claude` or `~/.agents`. Reuses the AC7-style module-level mtime sandbox
guard from `tests/test_installer.py`.

Stdlib only: ast + unittest + subprocess + sys + os + shutil + tempfile +
importlib.util + pathlib.
"""

import ast
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MODULE_DIR = REPO_ROOT / "modelb_axi"

CLAUDE_DIR = Path.home() / ".claude"
AGENTS_HOME_DIR = Path.home() / ".agents"
# Sandbox guard (mirrors tests/test_installer.py's AC7 slice): these two
# real, live trees must never be touched by anything in this test module.
_GUARD_DIRS = [CLAUDE_DIR / "skills", AGENTS_HOME_DIR]

# READ-ONLY test-side import of Crucible's TOON codec -- production
# `modelb_axi` code must never depend on it; the envelope is Model B's own
# emitter per contracts/crucible-envelope.md's non-client-adopter shape.
TOON_CODEC_PATH = (
    Path.home() / "Documents" / "data_projects" / "crucible" / "clients" / "toon.py"
)


def _snapshot_mtimes(roots):
    """Best-effort recursive mtime snapshot of `roots` for the sandbox
    guard."""
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
            "sandbox guard violated: the real ~/.claude/skills and/or "
            "~/.agents tree changed mtime while running "
            f"tests/test_scaffold.py; changed paths (up to 20): {changed[:20]}"
        )


def _run_module(*args, env_overrides=None, timeout=15, stdin=subprocess.DEVNULL):
    """Invoke `python -m modelb_axi <args>` with the repo root on
    PYTHONPATH (mirrors tests/test_installer.py's `_run_module`), so a
    not-yet-existing subcommand surfaces as a clean subprocess-level
    argparse failure instead of an in-process error."""
    env = dict(os.environ)
    existing_pp = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(REPO_ROOT) + (os.pathsep + existing_pp if existing_pp else "")
    if env_overrides:
        env.update(env_overrides)
    cmd = [sys.executable, "-m", "modelb_axi", *args]
    return subprocess.run(
        cmd, capture_output=True, text=True, timeout=timeout, stdin=stdin, env=env,
    )


def _write_install_toml(home: str, harnesses=("claude-code",)) -> Path:
    """Valid install.toml fixture -- the seam §S2 reads the installed
    harness set from (DN-scaffold-packaging.md §3)."""
    harnesses_toml = ", ".join(f'"{h}"' for h in harnesses)
    install_toml = Path(home) / "install.toml"
    install_toml.write_text(
        "[install]\n"
        'version = "0.1.0"\n'
        f"harnesses = [{harnesses_toml}]\n"
        'asset_root = "/tmp/does-not-matter-for-this-test"\n'
        "\n"
        "[deps]\n"
        'uv = "present"\n'
        "\n"
        "[files]\n",
        encoding="utf-8",
    )
    return install_toml


def _load_toon_codec():
    """READ-ONLY import of Crucible's TOON codec for TEST-side parsing
    only."""
    spec = importlib.util.spec_from_file_location(
        "crucible_toon_readonly_for_tests", TOON_CODEC_PATH,
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class InitHelpFlagsTest(unittest.TestCase):
    """§S2 AC -- `modelb-axi init --help` exits 0 and lists every flag the
    scaffold subcommand accepts."""

    def test_init_help_exits_zero_and_lists_all_flags(self):
        result = _run_module("init", "--help")
        self.assertEqual(
            result.returncode, 0,
            "S2: `modelb-axi init --help` must exit 0; got "
            f"exit={result.returncode} stdout={result.stdout!r} "
            f"stderr={result.stderr!r}",
        )
        required_flags = [
            "--name", "--token", "--acronym", "--mode", "--repo-shape",
            "--stacks", "--harnesses", "--owner", "--target", "--dry-run",
            "--no-commit", "--register",
        ]
        missing = [flag for flag in required_flags if flag not in result.stdout]
        self.assertEqual(
            missing, [],
            "S2: `init --help` must list every scaffold flag; missing "
            f"{missing} from stdout={result.stdout!r}",
        )


class ScaffoldModeEntryTest(unittest.TestCase):
    """§S2 AC -- with a valid install.toml present under $MODELB_HOME, a
    bare non-interactive invocation (no subcommand) banners scaffold mode
    and proposes `init`, exiting 0."""

    def setUp(self):
        self._tmp_home = tempfile.mkdtemp(prefix="modelb-axi-scaffold-home-")

    def tearDown(self):
        shutil.rmtree(self._tmp_home, ignore_errors=True)

    def test_bare_invocation_with_install_toml_banners_scaffold_and_proposes_init(self):
        _write_install_toml(self._tmp_home)
        result = _run_module("--yes", "--modelb-home", self._tmp_home)
        self.assertEqual(
            result.returncode, 0,
            "S2: bare non-interactive invocation with install.toml present "
            f"must exit 0; got exit={result.returncode} "
            f"stdout={result.stdout!r} stderr={result.stderr!r}",
        )
        self.assertIn(
            "scaffold", result.stdout.lower(),
            "S2: with install.toml present, stdout must banner scaffold "
            f"mode; got stdout={result.stdout!r}",
        )
        self.assertIn(
            "init", result.stdout.lower(),
            "S2: the scaffold-mode banner must propose running `init`; got "
            f"stdout={result.stdout!r}",
        )
        # NEGATIVE -- must not re-enter the installer flow.
        self.assertNotIn(
            "installer flow", result.stdout.lower(),
            f"S2: must not re-enter the installer flow; got stdout={result.stdout!r}",
        )


class InitDryRunTest(unittest.TestCase):
    """§S2 AC -- `init --dry-run` with a full flag set writes NOTHING
    under --target and emits a TOON envelope on stdout naming
    `axi.verb == "init"` with a true `dry_run` field."""

    def setUp(self):
        self._tmp_home = tempfile.mkdtemp(prefix="modelb-axi-init-home-")
        self._tmp_target = tempfile.mkdtemp(prefix="modelb-axi-init-target-")

    def tearDown(self):
        shutil.rmtree(self._tmp_home, ignore_errors=True)
        shutil.rmtree(self._tmp_target, ignore_errors=True)

    def _full_flags(self):
        return [
            "init",
            "--name", "X", "--token", "x", "--acronym", "XX",
            "--mode", "solo", "--repo-shape", "standalone",
            "--stacks", "python", "--owner", "tester",
            "--target", self._tmp_target, "--dry-run",
        ]

    def test_dry_run_with_install_toml_writes_nothing_and_emits_toon_envelope(self):
        _write_install_toml(self._tmp_home)
        result = _run_module(
            "--yes", *self._full_flags(), "--modelb-home", self._tmp_home,
        )
        self.assertEqual(
            result.returncode, 0,
            "S2: `init --dry-run` with a full flag set must exit 0; got "
            f"exit={result.returncode} stdout={result.stdout!r} "
            f"stderr={result.stderr!r}",
        )
        # NEGATIVE / bound -- --target must remain a genuinely empty dir.
        listing = sorted(os.listdir(self._tmp_target))
        self.assertEqual(
            listing, [],
            f"S2: `--dry-run` must write NOTHING under --target; found {listing!r}",
        )
        toon = _load_toon_codec()
        try:
            envelope = toon.decode(result.stdout)
        except Exception as exc:
            self.fail(
                "S2: init --dry-run stdout must parse as a TOON envelope; "
                f"decode failed with {exc!r} on stdout={result.stdout!r}"
            )
        axi = envelope.get("axi", {})
        self.assertEqual(
            axi.get("verb"), "init",
            f"S2: envelope axi.verb must be 'init'; got envelope={envelope!r}",
        )
        self.assertIs(
            axi.get("dry_run"), True,
            f"S2: envelope axi.dry_run must be true; got envelope={envelope!r}",
        )

    def test_dry_run_envelope_reports_ok_true_with_no_warnings(self):
        _write_install_toml(self._tmp_home)
        result = _run_module(
            "--yes", *self._full_flags(), "--modelb-home", self._tmp_home,
        )
        toon = _load_toon_codec()
        try:
            envelope = toon.decode(result.stdout)
        except Exception as exc:
            self.fail(
                "S2: init --dry-run stdout must parse as a TOON envelope; "
                f"decode failed with {exc!r} on stdout={result.stdout!r}"
            )
        axi = envelope.get("axi", {})
        # POSITIVE -- a clean dry-run reports ok:true.
        self.assertIs(
            axi.get("ok"), True,
            f"S2: envelope axi.ok must be true for a clean dry-run; got envelope={envelope!r}",
        )
        # NEGATIVE / bound -- a clean run carries no warnings.
        self.assertEqual(
            axi.get("warnings", None), [],
            f"S2: envelope axi.warnings must be an empty list; got envelope={envelope!r}",
        )


class HarnessSeamTest(unittest.TestCase):
    """§S2 AC -- `--harnesses` is the DEV-ONLY override of the installed
    set when install.toml is absent; without install.toml AND without
    --harnesses, `init` refuses to guess and fails non-zero naming
    install.toml."""

    def setUp(self):
        self._tmp_home = tempfile.mkdtemp(prefix="modelb-axi-devharness-home-")
        self._tmp_target = tempfile.mkdtemp(prefix="modelb-axi-devharness-target-")

    def tearDown(self):
        shutil.rmtree(self._tmp_home, ignore_errors=True)
        shutil.rmtree(self._tmp_target, ignore_errors=True)

    def _full_flags(self, *, harnesses=None):
        flags = [
            "init",
            "--name", "X", "--token", "x", "--acronym", "XX",
            "--mode", "solo", "--repo-shape", "standalone",
            "--stacks", "python", "--owner", "tester",
            "--target", self._tmp_target, "--dry-run",
        ]
        if harnesses is not None:
            flags += ["--harnesses", harnesses]
        return flags

    def test_dev_override_harnesses_without_install_toml_dry_run_succeeds(self):
        # No install.toml written under self._tmp_home -- installer-state.
        result = _run_module(
            "--yes", *self._full_flags(harnesses="claude-code"),
            "--modelb-home", self._tmp_home,
        )
        self.assertEqual(
            result.returncode, 0,
            "S2: `init --dry-run --harnesses claude-code` without "
            "install.toml (dev override) must still succeed; got "
            f"exit={result.returncode} stdout={result.stdout!r} "
            f"stderr={result.stderr!r}",
        )
        listing = sorted(os.listdir(self._tmp_target))
        self.assertEqual(
            listing, [],
            f"S2: dev-override dry-run must still write NOTHING under --target; found {listing!r}",
        )

    def test_missing_install_toml_and_missing_harnesses_fails_naming_install_toml(self):
        # Neither install.toml nor --harnesses -- the seam must refuse to
        # guess the installed harness set.
        result = _run_module(
            "--yes", *self._full_flags(harnesses=None),
            "--modelb-home", self._tmp_home,
        )
        self.assertNotEqual(
            result.returncode, 0,
            "S2: `init` without install.toml and without --harnesses must "
            f"fail non-zero (never guess harnesses); got exit="
            f"{result.returncode} stdout={result.stdout!r} "
            f"stderr={result.stderr!r}",
        )
        combined = (result.stdout + result.stderr).lower()
        self.assertIn(
            "install.toml", combined,
            "S2: the failure message must name install.toml as the missing "
            f"seam; got stdout={result.stdout!r} stderr={result.stderr!r}",
        )
        listing = sorted(os.listdir(self._tmp_target))
        self.assertEqual(
            listing, [],
            f"S2: a failed init must write NOTHING under --target; found {listing!r}",
        )


class StdlibOnlyImportScanTest(unittest.TestCase):
    """§S2 AC -- the scaffold flow lives in the stdlib-only `modelb_axi`
    package; scan every module's imports statically (AST, not execution)
    so a new module can never sneak in a third-party runtime dependency."""

    def test_all_modelb_axi_modules_import_only_stdlib_or_local(self):
        stdlib_names = set(sys.stdlib_module_names)
        offenders = {}
        for path in sorted(MODULE_DIR.glob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            bad = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        top = alias.name.split(".")[0]
                        if top != "modelb_axi" and top not in stdlib_names:
                            bad.add(top)
                elif isinstance(node, ast.ImportFrom):
                    if node.level and node.level > 0:
                        continue  # relative import -- local, always fine
                    top = (node.module or "").split(".")[0]
                    if top and top != "modelb_axi" and top not in stdlib_names:
                        bad.add(top)
            if bad:
                offenders[path.name] = sorted(bad)
        self.assertEqual(
            offenders, {},
            "S2: every modelb_axi/*.py module must import only stdlib or "
            f"local (modelb_axi.*) modules; found third-party imports: {offenders!r}",
        )


if __name__ == "__main__":
    unittest.main()
