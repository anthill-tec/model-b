"""RED-phase tests for CR-MDB-033 cycle C1 (installer correctness):
§S1 -- one source of truth for the deployed root, and §S3 -- unmanaged
files are skipped, never clobbered, with the manifest consulted
regardless of the ``--reinstall`` flag.

Written against the MEASURED defects in
``docs/changes/CR-MDB-033-installer-correctness.md`` (Context table,
defects 1/3/4) -- every test below is expected to FAIL against the
current tree:

  - AC1 (§S1): ``cli.py:238-245`` never writes ``[install].target_root``,
    so ``scaffold.py:_hook_scripts_root`` falls back to ``Path.home()``
    and the compiled ``.pi/extensions/*.ts`` wiring points at the real
    home instead of the installed ``--target-root``.
  - AC2 (§S1): the manifest never records ``target_root``/``skills_dir``/
    ``hooks_scripts_dir`` (only ``tool_scripts_dir`` exists today), and a
    manifest missing them silently falls back instead of raising a named
    error pointing at ``--reinstall``.
  - AC3 (§S3): ``deploy.py:_deploy_file`` -- dest exists, differs from
    source, NOT in the manifest -- falls through to ``shutil.copyfile``
    and clobbers a foreign (non-Model-B) file on first install.
  - AC5 (§S3): ``cli.py:_deploy_stage`` only loads the prior-install
    manifest when ``--reinstall`` is passed
    (``prior_hashes = load_manifest_hashes(home) if reinstall else {}``),
    so a hand-modified managed file is silently re-clobbered on any
    deploy call made without that flag, even though ``home`` already
    carries a manifest on disk.

All CLI-level invocations are subprocess probes against tmp sandboxes
(``--modelb-home``/``--target-root``/``--target``) -- nothing here ever
deploys into the real ``~/.claude`` or ``~/.agents``, mirroring
``tests/test_installer.py``/``tests/test_scaffold.py``'s AC7 sandbox
guard. The §S3-no-flag test (AC5) drives ``modelb_axi.cli._deploy_stage``
directly in-process (same idiom ``tests/test_tooling_adoption.py`` uses
for ``modelb_axi.deploy.deploy_assets``) because the CLI's own state
gate (``main()``: an existing ``install.toml`` without ``--reinstall``
always enters scaffold mode) makes the defective code path otherwise
unreachable through a subprocess run.

Stdlib only: unittest + subprocess + tempfile + shutil + tomllib +
pathlib + contextlib/io for in-process stdout/stderr capture.
"""

import argparse
import contextlib
import hashlib
import io
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path
from unittest import mock

from modelb_axi.harness import HARNESS_ROSTER_IDS

REPO_ROOT = Path(__file__).resolve().parent.parent

CLAUDE_DIR = Path.home() / ".claude"
AGENTS_HOME_DIR = Path.home() / ".agents"
# AC7-style sandbox guard (mirrors tests/test_installer.py): these two
# real, live trees must never be touched by anything in this module.
_GUARD_DIRS = [CLAUDE_DIR / "skills", AGENTS_HOME_DIR]


def _snapshot_mtimes(roots):
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
            f"tests/test_installer_correctness.py; changed paths (up to "
            f"20): {changed[:20]}"
        )


def _run_module(*args, env_overrides=None, timeout=20, stdin=subprocess.DEVNULL):
    """Invoke `python -m modelb_axi <args>` with the repo root on
    PYTHONPATH (mirrors tests/test_installer.py's `_run_module`)."""
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
    path = Path(bin_dir) / name
    path.write_text(script_body, encoding="utf-8")
    path.chmod(0o755)
    return path


# Fake `uv`/`sandesh` fixtures (mirror tests/test_installer.py exactly):
# presence on PATH is enough for the pre-flight to report `detected`
# without touching the network.
_FAKE_UV_SCRIPT = (
    "#!/bin/sh\n"
    'if [ "$1" = "tool" ] && [ "$2" = "install" ]; then\n'
    "    exit 0\n"
    "fi\n"
    'echo "uv 0.0.0-fake"\n'
    "exit 0\n"
)

_FAKE_SANDESH_SCRIPT = (
    "#!/bin/sh\n"
    'echo "sandesh-relay 0.0.0-fake"\n'
    "exit 0\n"
)

# Fake `uv` fixture that ALSO writes an invocation marker for `uv tool
# install <pkg>` (when $FAKE_UV_INSTALL_MARKER is set) -- mirrors
# tests/test_installer.py's SandeshAbsentInstallViaUvShimTest fixture
# exactly; C3's \u00a7S6 stdout/stderr-split test needs the proactive
# Sandesh install to actually fire (BOTH `deps:` lines), which the
# plain _FAKE_UV_SCRIPT above (a no-op `exit 0`) never triggers.
_FAKE_UV_SCRIPT_WITH_INSTALL_MARKER = (
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

_INIT_REQUIRED_FLAGS = [
    "--name", "X", "--token", "x", "--acronym", "XX",
    "--mode", "solo", "--repo-shape", "standalone",
    "--stacks", "python", "--owner", "tester",
]


def _write_legacy_manifest_missing_hooks_scripts_dir(home: str, harnesses=("claude-code",)) -> Path:
    """A pre-CR-MDB-033 ``install.toml``: harnesses/version/asset_root/
    tool_scripts_dir present (exactly what a v1 install wrote), but NO
    ``target_root``/``hooks_scripts_dir`` -- the AC-a fixture ("an
    install.toml lacking hooks_scripts_dir"). Mirrors the inline fixture
    already used by ``InstallTomlSchemaKeysTest.
    test_legacy_manifest_missing_hooks_scripts_dir_fails_naming_reinstall_flag``,
    extracted here for reuse by the RED2 (§S1 write-ordering) tests."""
    harnesses_toml = ", ".join(f'"{h}"' for h in harnesses)
    install_toml = Path(home) / "install.toml"
    install_toml.write_text(
        "[install]\n"
        'version = "0.1.0"\n'
        f"harnesses = [{harnesses_toml}]\n"
        'asset_root = "/tmp/does-not-matter-for-this-test"\n'
        'tool_scripts_dir = "/tmp/does-not-matter-for-this-test/.agents/scripts"\n'
        "\n"
        "[deps]\n"
        'uv = "detected"\n'
        "\n"
        "[files]\n",
        encoding="utf-8",
    )
    return install_toml


def _files_under_excluding_git(root: str) -> list:
    """Relative file paths under ``root``, recursively, skipping
    anything inside a ``.git`` directory -- the AC-a/AC-b/AC-c "leaves
    NO FILE under --target" checks must not trip on git's own
    bookkeeping (which is irrelevant to whether `init` clobbered the
    target with scaffold output)."""
    base = Path(root)
    found = []
    for path in base.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(base)
        if ".git" in rel.parts:
            continue
        found.append(str(rel))
    return sorted(found)


def _decode_envelope(stdout: str) -> dict:
    """Decode a `modelb_axi` TOON envelope printed on stdout, using the
    package's OWN codec (in-process import of the SUT package, the same
    idiom ``ManifestAlwaysConsultedWithoutReinstallFlagTest`` already
    uses for ``modelb_axi.cli._deploy_stage``)."""
    from modelb_axi.toon import decode
    return decode(stdout)


class PiExtensionTargetRootRoundTripTest(unittest.TestCase):
    """AC1 (§S1) -- installing to `--target-root /tmp/x` then `init`-ing
    a project must compile `.pi/extensions/*.ts` wiring that calls the
    scripts deployed under `/tmp/x/.agents/hooks/scripts/...`, never the
    real `~/.agents` -- a round-trip through the real installer AND the
    real scaffold compiler, exactly the CR's AC1 wording."""

    def setUp(self):
        self._tmp_home = tempfile.mkdtemp(prefix="modelb-axi-c1-home-")
        self._tmp_bin = tempfile.mkdtemp(prefix="modelb-axi-c1-fakebin-")
        self._tmp_target_root = tempfile.mkdtemp(prefix="modelb-axi-c1-target-")
        self._tmp_project = tempfile.mkdtemp(prefix="modelb-axi-c1-project-")
        _write_fake_executable(self._tmp_bin, "uv", _FAKE_UV_SCRIPT)
        _write_fake_executable(self._tmp_bin, "sandesh", _FAKE_SANDESH_SCRIPT)

    def tearDown(self):
        for root in (self._tmp_home, self._tmp_bin, self._tmp_target_root, self._tmp_project):
            shutil.rmtree(root, ignore_errors=True)

    def test_compiled_pi_extension_references_target_root_not_real_home(self):
        install_result = _run_module(
            "--yes", "--harnesses", "claude-code,pi",
            "--modelb-home", self._tmp_home,
            "--target-root", self._tmp_target_root,
            env_overrides={"PATH": self._tmp_bin},
        )
        self.assertEqual(
            install_result.returncode, 0,
            f"precondition: the real install must succeed; got "
            f"exit={install_result.returncode} "
            f"stdout={install_result.stdout!r} stderr={install_result.stderr!r}",
        )
        init_result = _run_module(
            "--yes", "init", *_INIT_REQUIRED_FLAGS,
            "--target", self._tmp_project,
            "--modelb-home", self._tmp_home,
        )
        self.assertEqual(
            init_result.returncode, 0,
            f"precondition: `init` reading the real install.toml must "
            f"succeed; got exit={init_result.returncode} "
            f"stdout={init_result.stdout!r} stderr={init_result.stderr!r}",
        )
        ext_path = (
            Path(self._tmp_project) / ".pi" / "extensions" / "ambient-board-status.ts"
        )
        self.assertTrue(
            ext_path.is_file(),
            f"AC1 precondition: {ext_path} must be emitted for an "
            f"installed `pi` harness; init stdout={init_result.stdout!r} "
            f"stderr={init_result.stderr!r}",
        )
        content = ext_path.read_text(encoding="utf-8")
        expected_script_path = str(
            Path(self._tmp_target_root) / ".agents" / "hooks" / "scripts" / "ambient-board-status"
        )
        # POSITIVE -- the compiled wiring calls the script under the
        # INSTALLED --target-root, never a home-relative guess.
        self.assertIn(
            expected_script_path, content,
            f"AC1: the compiled pi extension must call the deployed "
            f"script under the installed --target-root "
            f"({expected_script_path!r}); got content={content!r}",
        )
        # NEGATIVE -- the real user home must never appear in the
        # compiled wiring; this is the exact one-source-of-truth defect
        # (scaffold.py:_hook_scripts_root falling back to Path.home()).
        self.assertNotIn(
            str(Path.home()), content,
            f"AC1: the compiled pi extension must NOT reference the real "
            f"user home ({str(Path.home())!r}) -- target_root must be the "
            f"single source of truth for the deployed scripts dir; got "
            f"content={content!r}",
        )


class InstallTomlSchemaKeysTest(unittest.TestCase):
    """AC2 (§S1) -- `install.toml` must carry `target_root` plus the
    per-asset-class dirs that exist today (`skills_dir`,
    `hooks_scripts_dir`, `tool_scripts_dir` -- `agent_defs_dir` is
    deliberately out of scope per the 2026-09-22 gap-analysis correction
    and is never asserted here); a manifest missing them must fail with
    a named error pointing at `modelb-axi --reinstall`, not silently
    fall back to `Path.home()`."""

    def setUp(self):
        self._tmp_home = tempfile.mkdtemp(prefix="modelb-axi-c1-schema-home-")
        self._tmp_bin = tempfile.mkdtemp(prefix="modelb-axi-c1-schema-bin-")
        self._tmp_target_root = tempfile.mkdtemp(prefix="modelb-axi-c1-schema-target-")
        self._tmp_project = tempfile.mkdtemp(prefix="modelb-axi-c1-schema-project-")
        _write_fake_executable(self._tmp_bin, "uv", _FAKE_UV_SCRIPT)
        _write_fake_executable(self._tmp_bin, "sandesh", _FAKE_SANDESH_SCRIPT)

    def tearDown(self):
        for root in (self._tmp_home, self._tmp_bin, self._tmp_target_root, self._tmp_project):
            shutil.rmtree(root, ignore_errors=True)

    def _read_install_toml(self) -> dict:
        with open(Path(self._tmp_home) / "install.toml", "rb") as fh:
            return tomllib.load(fh)

    def test_fresh_install_records_target_root_and_per_class_dirs(self):
        result = _run_module(
            "--yes", "--harnesses", "claude-code",
            "--modelb-home", self._tmp_home,
            "--target-root", self._tmp_target_root,
            env_overrides={"PATH": self._tmp_bin},
        )
        self.assertEqual(
            result.returncode, 0,
            f"precondition: the real install must succeed; got "
            f"exit={result.returncode} stderr={result.stderr!r}",
        )
        install_section = self._read_install_toml().get("install", {})
        target_root = str(Path(self._tmp_target_root))
        # POSITIVE -- target_root itself is the one source of truth §S1
        # requires.
        self.assertEqual(
            install_section.get("target_root"), target_root,
            f"AC2/§S1: [install].target_root must equal the resolved "
            f"--target-root ({target_root!r}); got "
            f"{install_section.get('target_root')!r} -- full [install]="
            f"{install_section!r}",
        )
        self.assertEqual(
            install_section.get("skills_dir"),
            str(Path(target_root) / ".agents" / "skills"),
            f"AC2/§S1: [install].skills_dir must be recorded; got "
            f"{install_section.get('skills_dir')!r}",
        )
        self.assertEqual(
            install_section.get("hooks_scripts_dir"),
            str(Path(target_root) / ".agents" / "hooks" / "scripts"),
            f"AC2/§S1: [install].hooks_scripts_dir must be recorded (the "
            f"key scaffold._hook_scripts_root reads DIRECTLY, no "
            f"Path.home() fallback); got "
            f"{install_section.get('hooks_scripts_dir')!r}",
        )
        # POSITIVE -- tool_scripts_dir already exists pre-CR-033; pinned
        # here too so a future regression in the same write call is
        # caught by this same test.
        self.assertEqual(
            install_section.get("tool_scripts_dir"),
            str(Path(target_root) / ".agents" / "scripts"),
            f"AC2/§S1: [install].tool_scripts_dir must be recorded; got "
            f"{install_section.get('tool_scripts_dir')!r}",
        )

    def test_legacy_manifest_missing_hooks_scripts_dir_fails_naming_reinstall_flag(self):
        # A pre-CR-033 manifest: harnesses/version/asset_root/
        # tool_scripts_dir present (exactly what today's cli.py writes),
        # but NO target_root/hooks_scripts_dir -- the upgrade case §S1
        # names explicitly.
        install_toml = Path(self._tmp_home) / "install.toml"
        install_toml.write_text(
            "[install]\n"
            'version = "0.1.0"\n'
            'harnesses = ["claude-code", "pi"]\n'
            'asset_root = "/tmp/does-not-matter-for-this-test"\n'
            'tool_scripts_dir = "/tmp/does-not-matter-for-this-test/.agents/scripts"\n'
            "\n"
            "[deps]\n"
            'uv = "detected"\n'
            "\n"
            "[files]\n",
            encoding="utf-8",
        )
        result = _run_module(
            "--yes", "init", *_INIT_REQUIRED_FLAGS,
            "--target", self._tmp_project,
            "--modelb-home", self._tmp_home,
            # NOT --dry-run: _hook_scripts_root is only reached during
            # the real §S3 emission (_emit_plan), never during --dry-run.
        )
        combined = result.stdout + result.stderr
        # POSITIVE -- non-zero exit is the failure signal.
        self.assertNotEqual(
            result.returncode, 0,
            f"AC2/§S1: a manifest missing hooks_scripts_dir must fail "
            f"the run, never silently fall back to Path.home(); got "
            f"exit={result.returncode} combined={combined!r}",
        )
        # POSITIVE -- the error names the exact remedy the CR specifies.
        self.assertIn(
            "--reinstall", combined,
            f"AC2/§S1: the named error must point at `modelb-axi "
            f"--reinstall` as the remedy; got combined={combined!r}",
        )
        # POSITIVE -- the error names the specific missing key, not a
        # vague message.
        self.assertIn(
            "hooks_scripts_dir", combined,
            f"AC2/§S1: the named error must name the missing "
            f"hooks_scripts_dir key; got combined={combined!r}",
        )


class FirstInstallNeverClobbersForeignFileTest(unittest.TestCase):
    """AC3 (§S3, gap-analysis-corrected) -- a foreign (non-Model-B) file
    already sitting at a path Model B REALLY deploys to
    (`<target-root>/.agents/scripts/gate-lock.sh`, one of the CR-MDB-022
    adopted tool scripts) must survive a first install byte-identical,
    the run must report it as unmanaged, and a second run WITH
    `--force-managed` must still leave it byte-identical (force-managed
    overwrites managed-but-modified files only, never a file absent from
    the manifest entirely -- DN §D3)."""

    def setUp(self):
        self._tmp_home = tempfile.mkdtemp(prefix="modelb-axi-c1-foreign-home-")
        self._tmp_bin = tempfile.mkdtemp(prefix="modelb-axi-c1-foreign-bin-")
        self._tmp_target_root = tempfile.mkdtemp(prefix="modelb-axi-c1-foreign-target-")
        _write_fake_executable(self._tmp_bin, "uv", _FAKE_UV_SCRIPT)
        _write_fake_executable(self._tmp_bin, "sandesh", _FAKE_SANDESH_SCRIPT)
        self._foreign_content = (
            b"#!/bin/sh\n# NOT Model B's file -- pre-existing, hand-placed.\n"
            b"echo FOREIGN-CONTENT-MUST-SURVIVE\n"
        )
        self._gate_lock_path = (
            Path(self._tmp_target_root) / ".agents" / "scripts" / "gate-lock.sh"
        )
        self._gate_lock_path.parent.mkdir(parents=True, exist_ok=True)
        self._gate_lock_path.write_bytes(self._foreign_content)

    def tearDown(self):
        for root in (self._tmp_home, self._tmp_bin, self._tmp_target_root):
            shutil.rmtree(root, ignore_errors=True)

    def _run_install(self, *extra_args):
        return _run_module(
            "--yes", "--harnesses", "claude-code",
            "--modelb-home", self._tmp_home,
            "--target-root", self._tmp_target_root,
            *extra_args,
            env_overrides={"PATH": self._tmp_bin},
        )

    def test_foreign_file_at_deployed_path_survives_first_install_and_force_managed_reinstall(self):
        first = self._run_install()
        first_combined = first.stdout + first.stderr
        # POSITIVE -- byte-identical to the foreign content after the
        # FIRST install (this is the AC's central claim: nothing absent
        # from the manifest is Model B's to overwrite, DN §D3).
        self.assertEqual(
            self._gate_lock_path.read_bytes(), self._foreign_content,
            "AC3/§S3: a foreign file at a path Model B really deploys to "
            "must survive a first install byte-identical; got content="
            f"{self._gate_lock_path.read_bytes()!r} (expected unchanged "
            f"foreign content); install combined={first_combined!r}",
        )
        # POSITIVE -- the run reports it as unmanaged, naming the file.
        self.assertIn(
            "unmanaged", first_combined.lower(),
            f"AC3/§S3: the run must report the foreign file as unmanaged "
            f"with a distinct warning; got combined={first_combined!r}",
        )
        self.assertIn(
            "gate-lock.sh", first_combined,
            f"AC3/§S3: the unmanaged warning must name the affected "
            f"file; got combined={first_combined!r}",
        )

        second = self._run_install("--reinstall", "--force-managed")
        second_combined = second.stdout + second.stderr
        # POSITIVE -- --force-managed must NOT adopt a file that was
        # never Model B's; still byte-identical to the ORIGINAL foreign
        # content (not the deployed gate-lock.sh source).
        self.assertEqual(
            self._gate_lock_path.read_bytes(), self._foreign_content,
            "AC3/§S3: --force-managed must never overwrite a file absent "
            "from the manifest (unmanaged != hand-modified-managed); got "
            f"content={self._gate_lock_path.read_bytes()!r} after a "
            f"--force-managed re-run; combined={second_combined!r}",
        )


class ManifestAlwaysConsultedWithoutReinstallFlagTest(unittest.TestCase):
    """AC5 (§S3) -- the prior-install manifest must be consulted whenever
    it exists on disk, not only when `--reinstall` is passed
    (`cli.py:221`: `prior_hashes = load_manifest_hashes(home) if
    reinstall else {}`). `tests/test_installer.py:1012` already covers
    the `--reinstall` idempotent-noop path; this drives
    `modelb_axi.cli._deploy_stage` directly (mirrors
    `tests/test_tooling_adoption.py`'s direct `deploy_assets` calls)
    because the CLI's own state-detection gate in `main()` makes a
    second bare invocation over an ALREADY-installed home enter scaffold
    mode outright, never reaching the deploy stage at all -- so the only
    way to exercise a `reinstall=False` deploy call against a home that
    already carries a real manifest is to call the deploy stage
    function itself, exactly as the defect's own citation names it."""

    def setUp(self):
        self._tmp_home = Path(tempfile.mkdtemp(prefix="modelb-axi-c1-noflag-home-"))
        self._tmp_target_root = Path(tempfile.mkdtemp(prefix="modelb-axi-c1-noflag-target-"))

    def tearDown(self):
        shutil.rmtree(self._tmp_home, ignore_errors=True)
        shutil.rmtree(self._tmp_target_root, ignore_errors=True)

    def _call_deploy_stage(self, *, reinstall: bool, force_managed: bool = False):
        from modelb_axi.cli import _deploy_stage

        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            exit_code = _deploy_stage(
                self._tmp_home, self._tmp_target_root, ["claude-code"],
                {"uv": "detected", "sandesh": "detected", "crucible": "absent"},
                reinstall, force_managed,
            )
        return exit_code, out.getvalue() + err.getvalue()

    def test_deploy_stage_without_reinstall_flag_still_detects_hand_modified_managed_file(self):
        first_exit, first_combined = self._call_deploy_stage(reinstall=False)
        self.assertEqual(
            first_exit, 0,
            f"precondition: the first (genuinely fresh) deploy call must "
            f"succeed; got exit={first_exit} combined={first_combined!r}",
        )
        self.assertTrue(
            (self._tmp_home / "install.toml").is_file(),
            "precondition: the first deploy call must write install.toml "
            f"under {self._tmp_home}",
        )
        store_skill_md = (
            self._tmp_target_root / ".agents" / "skills" / "crucible" / "SKILL.md"
        )
        self.assertTrue(
            store_skill_md.is_file(),
            f"precondition: {store_skill_md} must be deployed by the "
            f"first call; combined={first_combined!r}",
        )
        marker = "\n<!-- hand-edited between deploy calls, must survive -->\n"
        original_content = store_skill_md.read_text(encoding="utf-8")
        hand_modified_content = original_content + marker
        store_skill_md.write_text(hand_modified_content, encoding="utf-8")

        # The defect under test: a SECOND deploy call over the SAME home
        # (which already carries install.toml with this file's ORIGINAL
        # hash) made WITHOUT --reinstall (reinstall=False) -- exactly
        # the "no-flag path" the CR's AC names.
        second_exit, second_combined = self._call_deploy_stage(reinstall=False)

        current_content = store_skill_md.read_text(encoding="utf-8")
        # POSITIVE -- the hand-modified content must survive: the
        # manifest already on disk must be consulted even without
        # --reinstall, so the mismatch is detected and the file is
        # skipped, not silently rewritten back to the source content.
        self.assertEqual(
            current_content, hand_modified_content,
            "AC5/§S3: a hand-modified managed file must be detected and "
            "skipped on a deploy call made WITHOUT --reinstall, as long "
            "as home already carries a manifest on disk (manifest must "
            "be consulted whenever it exists, not only with "
            f"--reinstall); got current_content={current_content!r} "
            f"(expected the hand-edited content to survive); "
            f"second call combined={second_combined!r}",
        )
        # POSITIVE -- the skip is surfaced, not silent.
        self.assertIn(
            "SKILL.md", second_combined,
            f"AC5/§S3: the hash-mismatch detection must name the "
            f"affected file even without --reinstall; got "
            f"combined={second_combined!r}",
        )


class RealInitLegacyManifestNoWriteBeforeFailureTest(unittest.TestCase):
    """AC-a (§S1, RED2) -- with an `install.toml` lacking
    `hooks_scripts_dir`, a REAL (non-dry) `init` must exit non-zero AND
    leave NO FILE under `--target`. MEASURED current defect: exit=3 but
    11 files already written (`_hook_scripts_root` is called from
    inside `_emit_plan`, mid-emission, after writes) -- this test pins
    the write-BEFORE-check ordering bug that
    `InstallTomlSchemaKeysTest.
    test_legacy_manifest_missing_hooks_scripts_dir_fails_naming_reinstall_flag`
    (same fixture) does not: that test only asserts the error text, not
    that the target tree stayed empty."""

    def setUp(self):
        self._tmp_home = tempfile.mkdtemp(prefix="modelb-axi-c1-red2-legacy-home-")
        self._tmp_target = tempfile.mkdtemp(prefix="modelb-axi-c1-red2-legacy-target-")
        _write_legacy_manifest_missing_hooks_scripts_dir(self._tmp_home)

    def tearDown(self):
        for root in (self._tmp_home, self._tmp_target):
            shutil.rmtree(root, ignore_errors=True)

    def test_real_init_exits_nonzero_and_leaves_target_empty(self):
        result = _run_module(
            "--yes", "init", *_INIT_REQUIRED_FLAGS,
            "--target", self._tmp_target,
            "--modelb-home", self._tmp_home,
            "--no-commit",
        )
        combined = result.stdout + result.stderr
        # POSITIVE -- non-zero exit is the failure signal.
        self.assertNotEqual(
            result.returncode, 0,
            f"AC-a: a real init against an install.toml lacking "
            f"hooks_scripts_dir must exit non-zero; got "
            f"exit={result.returncode} combined={combined!r}",
        )
        # Confirm the RIGHT reason (the §S1 named-key defect), not
        # some unrelated failure (e.g. missing flags/unknown stack).
        self.assertIn(
            "hooks_scripts_dir", combined,
            f"AC-a precondition: the failure must be the missing "
            f"hooks_scripts_dir key, not an unrelated error; got "
            f"combined={combined!r}",
        )
        # NEGATIVE / bound -- the exact defect: NO file anywhere under
        # --target, not merely "fewer files than a full run".
        leftover = _files_under_excluding_git(self._tmp_target)
        self.assertEqual(
            leftover, [],
            f"AC-a: a real init that fails on the missing "
            f"hooks_scripts_dir key must leave NO FILE under --target "
            f"(the check must run BEFORE the first write); found "
            f"{leftover!r}; run combined={combined!r}",
        )


class RealInitWithoutInstallTomlNoWriteBeforeFailureTest(unittest.TestCase):
    """AC-b (§S1, RED2) -- with NO `install.toml` at all (the
    `--harnesses` dev override), a real `init` must exit non-zero, leave
    no file under `--target`, and its error must state that no
    `install.toml` exists at the resolved home and name the installer --
    it must NOT say the file "does not record" a key (that wording is
    only correct when the file exists but lacks the key -- AC-a).
    MEASURED current defect: exit=3 after 11 files, message reads
    "<home>/install.toml does not record [install].hooks_scripts_dir
    ..." even though that file does not exist on disk."""

    def setUp(self):
        self._tmp_home = tempfile.mkdtemp(prefix="modelb-axi-c1-red2-nomanifest-home-")
        self._tmp_target = tempfile.mkdtemp(prefix="modelb-axi-c1-red2-nomanifest-target-")
        # Deliberately no install.toml under self._tmp_home.

    def tearDown(self):
        for root in (self._tmp_home, self._tmp_target):
            shutil.rmtree(root, ignore_errors=True)

    def test_real_init_exits_nonzero_leaves_target_empty_and_names_installer_not_does_not_record(self):
        result = _run_module(
            "--yes", "init", *_INIT_REQUIRED_FLAGS,
            "--harnesses", "claude-code",
            "--target", self._tmp_target,
            "--modelb-home", self._tmp_home,
            "--no-commit",
        )
        combined = result.stdout + result.stderr
        # POSITIVE -- non-zero exit is the failure signal.
        self.assertNotEqual(
            result.returncode, 0,
            f"AC-b: a real init with no install.toml at all (dev-override "
            f"--harnesses) must exit non-zero; got "
            f"exit={result.returncode} combined={combined!r}",
        )
        # NEGATIVE / bound -- the exact defect: no file anywhere under
        # --target.
        leftover = _files_under_excluding_git(self._tmp_target)
        self.assertEqual(
            leftover, [],
            f"AC-b: a real init that fails because no install.toml exists "
            f"must leave NO FILE under --target; found {leftover!r}; run "
            f"combined={combined!r}",
        )
        combined_lower = combined.lower()
        # POSITIVE -- the error states that no install.toml EXISTS at
        # the resolved home (not that a present file "does not record" a
        # key), and names the resolved home path.
        self.assertIn(
            "no install.toml", combined_lower,
            f"AC-b: the error must state that no install.toml exists at "
            f"the resolved home; got combined={combined!r}",
        )
        self.assertIn(
            self._tmp_home, combined,
            f"AC-b: the error must name the resolved home it looked "
            f"under; got home={self._tmp_home!r} combined={combined!r}",
        )
        # POSITIVE -- the error names the installer as the remedy.
        self.assertIn(
            "modelb-axi", combined_lower,
            f"AC-b: the error must name the installer (modelb-axi) as "
            f"the remedy for a home with no install.toml; got "
            f"combined={combined!r}",
        )
        # NEGATIVE -- this is the exact measured defect: the v1 message
        # is reused verbatim even though the file does not exist, wrongly
        # claiming a present file "does not record" the key.
        self.assertNotIn(
            "does not record", combined,
            f"AC-b: a home with NO install.toml at all must never be "
            f"told the file 'does not record' a key -- that wording "
            f"implies the file exists; got combined={combined!r}",
        )


class DryRunSurfacesSameErrorTextAsWarningTest(unittest.TestCase):
    """AC-c (§S1, RED2) -- in both the AC-a (legacy manifest
    missing the key) and AC-b (no install.toml at all) cases, `--dry-run`
    must still write nothing, exit 0, and its envelope must carry the
    SAME error text the real (non-dry) run fails with, as a warning --
    so a plan real `init` cannot emit is never previewed as clean.
    MEASURED current defect: `--dry-run` exits 0 with `ok: true` and NO
    warning in both cases (`_hook_scripts_root` is never called under
    `if not dry_run:`)."""

    def setUp(self):
        self._tmp_home = tempfile.mkdtemp(prefix="modelb-axi-c1-red2-dryrun-home-")
        self._tmp_real_target = tempfile.mkdtemp(prefix="modelb-axi-c1-red2-dryrun-real-target-")
        self._tmp_dry_target = tempfile.mkdtemp(prefix="modelb-axi-c1-red2-dryrun-dry-target-")

    def tearDown(self):
        for root in (self._tmp_home, self._tmp_real_target, self._tmp_dry_target):
            shutil.rmtree(root, ignore_errors=True)

    def _real_error_text(self, *extra_flags):
        """Run the REAL (non-dry) init and return the exact warning text
        it fails with, per the envelope's own `warnings[0]` field --
        never a hand-typed guess at the message."""
        result = _run_module(
            "--yes", "init", *_INIT_REQUIRED_FLAGS, *extra_flags,
            "--target", self._tmp_real_target,
            "--modelb-home", self._tmp_home,
            "--no-commit",
        )
        self.assertNotEqual(
            result.returncode, 0,
            f"precondition: the real (non-dry) run must fail so there is "
            f"an error text to compare the dry-run warning against; got "
            f"exit={result.returncode} stdout={result.stdout!r} "
            f"stderr={result.stderr!r}",
        )
        envelope = _decode_envelope(result.stdout)
        warnings = envelope.get("axi", {}).get("warnings", [])
        self.assertEqual(
            len(warnings), 1,
            f"precondition: the real run's failure envelope must carry "
            f"exactly one warning (the error text); got envelope={envelope!r}",
        )
        return warnings[0]

    def test_legacy_manifest_missing_key_dry_run_writes_nothing_exits_zero_and_warns_same_text(self):
        _write_legacy_manifest_missing_hooks_scripts_dir(self._tmp_home)
        real_error = self._real_error_text()

        dry_result = _run_module(
            "--yes", "init", *_INIT_REQUIRED_FLAGS,
            "--target", self._tmp_dry_target,
            "--modelb-home", self._tmp_home,
            "--no-commit", "--dry-run",
        )
        combined = dry_result.stdout + dry_result.stderr
        # POSITIVE -- dry-run still exits 0.
        self.assertEqual(
            dry_result.returncode, 0,
            f"AC-c: --dry-run must exit 0 even when the real run would "
            f"fail on the missing hooks_scripts_dir key; got "
            f"exit={dry_result.returncode} combined={combined!r}",
        )
        # NEGATIVE / bound -- dry-run writes nothing, as always.
        leftover = _files_under_excluding_git(self._tmp_dry_target)
        self.assertEqual(
            leftover, [],
            f"AC-c: --dry-run must write NOTHING under --target even when "
            f"it detects the missing-key defect; found {leftover!r}; "
            f"combined={combined!r}",
        )
        dry_envelope = _decode_envelope(dry_result.stdout)
        dry_warnings = dry_envelope.get("axi", {}).get("warnings", [])
        # POSITIVE -- the exact same error text the real run fails with
        # is carried as a dry-run warning, not a paraphrase or omission.
        self.assertIn(
            real_error, dry_warnings,
            f"AC-c: the dry-run envelope must carry the SAME error text "
            f"the real run fails with, as a warning; real_error="
            f"{real_error!r} dry_warnings={dry_warnings!r}",
        )

    def test_missing_install_toml_dry_run_writes_nothing_exits_zero_and_warns_same_text(self):
        # Deliberately no install.toml under self._tmp_home for either run.
        real_error = self._real_error_text("--harnesses", "claude-code")

        dry_result = _run_module(
            "--yes", "init", *_INIT_REQUIRED_FLAGS,
            "--harnesses", "claude-code",
            "--target", self._tmp_dry_target,
            "--modelb-home", self._tmp_home,
            "--no-commit", "--dry-run",
        )
        combined = dry_result.stdout + dry_result.stderr
        # POSITIVE -- dry-run still exits 0.
        self.assertEqual(
            dry_result.returncode, 0,
            f"AC-c: --dry-run must exit 0 even when the real run would "
            f"fail because no install.toml exists; got "
            f"exit={dry_result.returncode} combined={combined!r}",
        )
        # NEGATIVE / bound -- dry-run writes nothing, as always.
        leftover = _files_under_excluding_git(self._tmp_dry_target)
        self.assertEqual(
            leftover, [],
            f"AC-c: --dry-run must write NOTHING under --target even when "
            f"it detects the missing-install.toml defect; found "
            f"{leftover!r}; combined={combined!r}",
        )
        dry_envelope = _decode_envelope(dry_result.stdout)
        dry_warnings = dry_envelope.get("axi", {}).get("warnings", [])
        # POSITIVE -- the exact same error text the real run fails with
        # is carried as a dry-run warning.
        self.assertIn(
            real_error, dry_warnings,
            f"AC-c: the dry-run envelope must carry the SAME error text "
            f"the real run fails with, as a warning; real_error="
            f"{real_error!r} dry_warnings={dry_warnings!r}",
        )


# ---------------------------------------------------------------------------
# CR-MDB-033 cycle C2 -- §S2 atomic writes everywhere, §S4 honest partial
# emission. Appended below the cycle C1 (§S1/§S3) classes above, which are
# GREEN as of this cycle's baseline (measured 368 tests / 0 failures / 11
# skips at 74b10f2) and are left untouched.
#
# MEASURED defects this cycle's tests pin (docs/changes/
# CR-MDB-033-installer-correctness.md §S2/§S4, C2-tightened ACs):
#   - AC1: deploy._deploy_file uses `shutil.copyfile(src, dest)`; the four
#     hooks.py emitters and scaffold._emit_plan's inner `write()` use
#     `.write_text(`/`.write_bytes(` directly -- none of the six sites calls
#     `os.replace` at all, so monkeypatching it to raise has NO effect on
#     them today: the prior destination content is unconditionally
#     overwritten rather than preserved.
#   - AC2: the grep gate finds `shutil.copyfile` in deploy.py, `.write_text(`
#     in hooks.py (x4) and scaffold.py's `_emit_plan.write()`, and there is
#     no `modelb_axi/_fsutil.py` yet.
#   - AC3: `config.write_install_toml` writes via `tempfile.mkstemp`, whose
#     default mode is 0600, not 0644.
#   - AC4: the `init` failure envelope is `envelope("init", False,
#     warnings=[str(exc)], dry_run=False)` (scaffold.py:752-755) -- no
#     `emitted` field at all, even though `_emit_plan` may already have
#     written several files before the failure.
#   - The module docstring (scaffold.py:20) still reads "`--dry-run` (and
#     any failure) writes NOTHING under `--target`."
# ---------------------------------------------------------------------------


def _write_full_install_toml(home: str, harnesses=("claude-code",)) -> Path:
    """A §S1-valid ``install.toml`` (records ``target_root`` and all three
    per-class dirs, the shape ``InstallTomlSchemaKeysTest`` already pins as
    GREEN) -- the C2 (§S2/§S4) fixtures need a manifest that PASSES §S1's
    own strict rule so a §S2/§S4 test never fails on an unrelated §S1
    defect. Mirrors ``tests/test_scaffold.py::_write_install_toml`` plus the
    ``target_root``/``skills_dir``/``tool_scripts_dir`` keys §S1 added."""
    harnesses_toml = ", ".join(f'"{h}"' for h in harnesses)
    target_root = Path(home) / "target-root-placeholder"
    skills_dir = target_root / ".agents" / "skills"
    hooks_scripts_dir = target_root / ".agents" / "hooks" / "scripts"
    tool_scripts_dir = target_root / ".agents" / "scripts"
    install_toml = Path(home) / "install.toml"
    install_toml.write_text(
        "[install]\n"
        'version = "0.1.0"\n'
        f"harnesses = [{harnesses_toml}]\n"
        f'target_root = "{target_root}"\n'
        'asset_root = "/tmp/does-not-matter-for-this-test"\n'
        f'skills_dir = "{skills_dir}"\n'
        f'hooks_scripts_dir = "{hooks_scripts_dir}"\n'
        f'tool_scripts_dir = "{tool_scripts_dir}"\n'
        "\n"
        "[deps]\n"
        'uv = "detected"\n'
        "\n"
        "[files]\n",
        encoding="utf-8",
    )
    return install_toml


def _init_args(target, dry_run: bool, no_commit: bool = True, harnesses=None) -> argparse.Namespace:
    """A minimal, valid ``argparse.Namespace`` for a direct in-process
    ``scaffold.run_init(args, home)`` call -- used by the AC4 test, which
    needs to monkeypatch a production function mid-emission; a subprocess
    run cannot be monkeypatched (see class docstring for the justification
    already established by ``ManifestAlwaysConsultedWithoutReinstallFlagTest``
    above, which drives ``cli._deploy_stage`` the same way)."""
    return argparse.Namespace(
        name="X", token="xproj", acronym="XP", mode="solo",
        repo_shape="standalone", stacks="python", owner="tester",
        target=str(target), dry_run=dry_run, no_commit=no_commit,
        register=False, harnesses=harnesses,
    )


class AtomicWriteSixSitesTest(unittest.TestCase):
    """AC1 (§S2, C2) -- each of the six write sites --
    ``deploy._deploy_file``, ``hooks._emit_claude_code``,
    ``hooks._emit_opencode``, ``hooks._emit_pi``,
    ``hooks._emit_hermes_advisory``, ``scaffold._emit_plan``'s inner writer
    -- must write through an atomic helper (tmp-in-the-same-directory +
    ``os.replace``): with ``os.replace`` monkeypatched to raise, re-running
    that site over an EXISTING destination must leave the prior file
    byte-identical and leave no temp file in its directory. Asserted per
    site via ``subTest`` -- a site not asserted here is a site not wired
    (§S2's own wording). Each subtest drives the real function/entry point
    directly (never a mock of the function itself -- only ``os.replace`` is
    mocked), with a scenario shaped to reach that function's real write
    branch (e.g. site 1's ``prior_hashes`` entry must match the current
    destination hash, or ``_deploy_file`` takes an earlier ``return`` before
    ever reaching the copy)."""

    def test_all_six_sites_preserve_prior_file_when_os_replace_fails(self):
        with self.subTest(site="deploy._deploy_file"):
            self._check_deploy_deploy_file()
        with self.subTest(site="hooks._emit_claude_code"):
            self._check_hooks_emitter("_emit_claude_code", Path(".claude") / "settings.json")
        with self.subTest(site="hooks._emit_opencode"):
            self._check_hooks_emitter("_emit_opencode", Path(".opencode") / "plugin" / "modelb-hooks.ts")
        with self.subTest(site="hooks._emit_pi"):
            self._check_hooks_emitter("_emit_pi", Path(".pi") / "extensions" / "guard-example.ts")
        with self.subTest(site="hooks._emit_hermes_advisory"):
            self._check_hooks_emitter("_emit_hermes_advisory", Path("hooks") / "hermes-manual.yaml")
        with self.subTest(site="scaffold._emit_plan"):
            self._check_scaffold_emit_plan()

    def _check_deploy_deploy_file(self):
        from modelb_axi import deploy

        with tempfile.TemporaryDirectory(prefix="modelb-axi-c2-ac1-deploy-") as tmp:
            tmp_path = Path(tmp)
            src = tmp_path / "src.txt"
            dest = tmp_path / "dest.txt"
            prior_content = b"PRIOR DEST CONTENT -- must survive an os.replace failure\n"
            new_content = b"NEW SOURCE CONTENT -- must NOT land when os.replace fails\n"
            src.write_bytes(new_content)
            dest.write_bytes(prior_content)
            # `recorded == dest_hash`: dest is UNCHANGED since the prior
            # install, so `_deploy_file` takes the real upgrade-copy branch
            # (not the unmanaged/hand-modified early returns) -- this is the
            # scenario that reaches `shutil.copyfile` today.
            prior_hash = hashlib.sha256(prior_content).hexdigest()
            skipped: list = []
            unmanaged: list = []
            with mock.patch("os.replace", side_effect=OSError("AC1 injected os.replace failure")):
                with self.assertRaises(OSError):
                    deploy._deploy_file(
                        src, dest, "dest.txt", {"dest.txt": prior_hash},
                        False, skipped, unmanaged,
                    )
            self.assertEqual(
                dest.read_bytes(), prior_content,
                "AC1/§S2 site=deploy._deploy_file: the prior destination "
                "content must survive an os.replace failure byte-identical; "
                f"got {dest.read_bytes()!r} (prior was {prior_content!r})",
            )
            extra = sorted(
                p.name for p in tmp_path.iterdir()
                if p.name not in {"src.txt", "dest.txt"}
            )
            self.assertEqual(
                extra, [],
                "AC1/§S2 site=deploy._deploy_file: no temp file may remain "
                f"in the destination directory; found {extra!r}",
            )

    def _check_hooks_emitter(self, emitter_name: str, dest_rel: Path):
        from modelb_axi import hooks

        with tempfile.TemporaryDirectory(prefix=f"modelb-axi-c2-ac1-{emitter_name}-") as tmp:
            target = Path(tmp)
            dest = target / dest_rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            prior_content = f"PRIOR {emitter_name} CONTENT -- must survive\n".encode()
            dest.write_bytes(prior_content)
            instances = [{
                "event": "pre-tool-use",
                "command": "guard-example",
                "matcher": None,
                "timeout": None,
                "fail_direction": None,
            }]
            entry = hooks._new_report_entry()
            scripts_root = target / "scripts-root-placeholder"
            emitter = getattr(hooks, emitter_name)
            with mock.patch("os.replace", side_effect=OSError("AC1 injected os.replace failure")):
                with self.assertRaises(OSError):
                    emitter(instances, target, scripts_root, entry)
            self.assertEqual(
                dest.read_bytes(), prior_content,
                f"AC1/§S2 site=hooks.{emitter_name}: the prior destination "
                f"content must survive an os.replace failure byte-identical; "
                f"got {dest.read_bytes()!r} (prior was {prior_content!r})",
            )
            extra = sorted(p.name for p in dest.parent.iterdir() if p.name != dest.name)
            self.assertEqual(
                extra, [],
                f"AC1/§S2 site=hooks.{emitter_name}: no temp file may remain "
                f"in the destination directory; found {extra!r}",
            )

    def _check_scaffold_emit_plan(self):
        from modelb_axi import scaffold

        with tempfile.TemporaryDirectory(prefix="modelb-axi-c2-ac1-home-") as home_dir, \
             tempfile.TemporaryDirectory(prefix="modelb-axi-c2-ac1-target-") as target_dir:
            home = Path(home_dir)
            target = Path(target_dir)
            target.mkdir(parents=True, exist_ok=True)
            env_path = target / ".env"
            prior_content = "PRIOR ENV CONTENT -- must survive an os.replace failure\n"
            env_path.write_text(prior_content, encoding="utf-8")
            with mock.patch("os.replace", side_effect=OSError("AC1 injected os.replace failure")):
                with self.assertRaises(OSError):
                    scaffold._emit_plan(
                        target,
                        name="X", token="xproj", acronym="XP", mode="solo",
                        owner="tester", stacks=["python"], harnesses=[],
                        sub_projects=[], no_commit=True, home=home,
                        hook_scripts_root=None,
                    )
            self.assertEqual(
                env_path.read_text(encoding="utf-8"), prior_content,
                "AC1/§S2 site=scaffold._emit_plan: the prior .env content "
                "must survive an os.replace failure byte-identical; got "
                f"{env_path.read_text(encoding='utf-8')!r} (prior was "
                f"{prior_content!r})",
            )
            top_level = {p.name for p in target.iterdir() if p.is_file()}
            stray = sorted(
                n for n in top_level
                if n.startswith(".env") and n not in {".env", ".env.local"}
            )
            self.assertEqual(
                stray, [],
                "AC1/§S2 site=scaffold._emit_plan: no temp file may remain "
                f"beside .env in --target; found {stray!r}",
            )


class NoDirectWriteCallsOutsideFsutilTest(unittest.TestCase):
    """AC2 (§S2, C2) -- grep gate: no ``shutil.copyfile``, ``.write_text(``
    or ``.write_bytes(`` remains anywhere in ``modelb_axi/`` outside
    ``modelb_axi/_fsutil.py`` (which does not exist yet on this branch --
    the gate tolerates its absence rather than requiring it, so this test
    is meaningful both before and after ``_fsutil.py`` lands). Scans real
    source files only (skips ``__pycache__``)."""

    _FORBIDDEN_PATTERNS = ("shutil.copyfile", ".write_text(", ".write_bytes(")

    def test_no_direct_write_calls_remain_outside_fsutil_module(self):
        module_dir = REPO_ROOT / "modelb_axi"
        offenders = []
        for path in sorted(module_dir.rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            if path.name == "_fsutil.py":
                continue
            text = path.read_text(encoding="utf-8")
            for lineno, line in enumerate(text.splitlines(), start=1):
                for pattern in self._FORBIDDEN_PATTERNS:
                    if pattern in line:
                        offenders.append(
                            f"{path.relative_to(REPO_ROOT)}:{lineno}: {line.strip()}"
                        )
        self.assertEqual(
            offenders, [],
            "AC2/§S2: no shutil.copyfile/.write_text(/.write_bytes( may "
            "remain in modelb_axi/ outside _fsutil.py -- every write site "
            f"must go through the atomic helper; found: {offenders!r}",
        )


class InstallTomlWrittenWithMode0644Test(unittest.TestCase):
    """AC3 (§S2, C2) -- ``install.toml`` is written with mode 0644 (today
    0600, ``tempfile.mkstemp``'s default rather than a decision -- it
    holds no secrets)."""

    def setUp(self):
        self._tmp_home = tempfile.mkdtemp(prefix="modelb-axi-c2-mode-home-")
        self._tmp_bin = tempfile.mkdtemp(prefix="modelb-axi-c2-mode-bin-")
        self._tmp_target_root = tempfile.mkdtemp(prefix="modelb-axi-c2-mode-target-")
        _write_fake_executable(self._tmp_bin, "uv", _FAKE_UV_SCRIPT)
        _write_fake_executable(self._tmp_bin, "sandesh", _FAKE_SANDESH_SCRIPT)

    def tearDown(self):
        for root in (self._tmp_home, self._tmp_bin, self._tmp_target_root):
            shutil.rmtree(root, ignore_errors=True)

    def test_fresh_install_writes_install_toml_with_mode_0644(self):
        result = _run_module(
            "--yes", "--harnesses", "claude-code",
            "--modelb-home", self._tmp_home,
            "--target-root", self._tmp_target_root,
            env_overrides={"PATH": self._tmp_bin},
        )
        self.assertEqual(
            result.returncode, 0,
            f"precondition: the real install must succeed; got "
            f"exit={result.returncode} stdout={result.stdout!r} "
            f"stderr={result.stderr!r}",
        )
        install_toml = Path(self._tmp_home) / "install.toml"
        self.assertTrue(
            install_toml.is_file(),
            f"precondition: {install_toml} must exist after a real install",
        )
        mode = stat.S_IMODE(install_toml.stat().st_mode)
        self.assertEqual(
            mode, 0o644,
            f"AC3/§S2: install.toml must be written with mode 0644; got "
            f"{oct(mode)}",
        )


class MidEmissionFailureHonestPartialEmissionTest(unittest.TestCase):
    """AC4 (§S4, C2) -- ``init`` with an ``OSError`` injected mid-emission
    (after SOME files are already written) exits non-zero, and the failure
    envelope's ``emitted`` field lists EXACTLY the files present under
    ``--target`` (compared as sets of relative paths, excluding ``.git/``)
    -- the same field name the success envelope already uses
    (scaffold.py ~line 767). ``--dry-run`` still writes nothing even with
    the same failure injected.

    In-process call to ``scaffold.run_init`` (not a subprocess): a
    subprocess invocation cannot have a production function monkeypatched
    mid-run, and an in-process call is the only way to guarantee the
    injection lands AFTER some files are written but BEFORE emission
    finishes -- the same idiom this file's own
    ``ManifestAlwaysConsultedWithoutReinstallFlagTest`` already uses for
    ``cli._deploy_stage``. The injection point is ``scaffold._render_agents_md``
    (patched to raise), reached from ``_emit_plan`` only AFTER `.env`,
    `.env.local`, `.gitignore`, `docs/changes/README.md` and
    `docs/research/.gitkeep` are already written -- a genuinely non-empty
    partial tree, not the §S1 write-before-check case (which leaves zero
    files)."""

    def setUp(self):
        self._tmp_home = tempfile.mkdtemp(prefix="modelb-axi-c2-partial-home-")
        self._tmp_target = tempfile.mkdtemp(prefix="modelb-axi-c2-partial-target-")
        self._tmp_dry_target = tempfile.mkdtemp(prefix="modelb-axi-c2-partial-dry-target-")
        _write_full_install_toml(self._tmp_home, harnesses=("claude-code",))

    def tearDown(self):
        for root in (self._tmp_home, self._tmp_target, self._tmp_dry_target):
            shutil.rmtree(root, ignore_errors=True)

    def test_mid_emission_oserror_exits_nonzero_and_emitted_lists_exact_partial_tree(self):
        from modelb_axi import scaffold

        args = _init_args(self._tmp_target, dry_run=False)
        out = io.StringIO()
        with mock.patch(
            "modelb_axi.scaffold._render_agents_md",
            side_effect=OSError("CR-MDB-033 C2 injected mid-emission failure"),
        ):
            with contextlib.redirect_stdout(out):
                exit_code = scaffold.run_init(args, Path(self._tmp_home))
        combined = out.getvalue()

        # POSITIVE -- non-zero exit is the failure signal.
        self.assertNotEqual(
            exit_code, 0,
            f"AC4/§S4: a mid-emission OSError must exit non-zero; got "
            f"exit={exit_code} stdout={combined!r}",
        )

        leftover = _files_under_excluding_git(self._tmp_target)
        # NEGATIVE / bound -- the injection point is reached only AFTER
        # five files are written, so the partial tree must be genuinely
        # non-empty (never zero -- that would be the §S1 defect, not §S4's).
        self.assertTrue(
            len(leftover) > 0,
            f"AC4 precondition: the injection point must leave a NON-EMPTY "
            f"partial tree under --target; found nothing -- got "
            f"exit={exit_code} stdout={combined!r}",
        )

        envelope = _decode_envelope(combined)
        axi = envelope.get("axi", {})
        # POSITIVE -- axi.ok is false on this path.
        self.assertIs(
            axi.get("ok"), False,
            f"AC4: the failure envelope must report axi.ok false; got "
            f"envelope={envelope!r}",
        )
        emitted = axi.get("emitted")
        # POSITIVE -- `emitted` is present (the SAME field name the success
        # envelope already uses) and its value, compared as a SET of
        # relative paths, equals EXACTLY the files present under --target.
        self.assertEqual(
            set(emitted or []), set(leftover),
            "AC4/§S4: the failure envelope's `emitted` field must list "
            "EXACTLY the files present under --target (compared as sets of "
            f"relative paths); got emitted={emitted!r} leftover on disk="
            f"{leftover!r}; envelope={envelope!r}",
        )

        # AC4 (continued) -- --dry-run must still write nothing even with
        # the same failure injected (asserted after the primary emitted-
        # field claim above, which is the new C2 behaviour this test
        # exists to pin).
        dry_args = _init_args(self._tmp_dry_target, dry_run=True)
        with mock.patch(
            "modelb_axi.scaffold._render_agents_md",
            side_effect=OSError("CR-MDB-033 C2 injected mid-emission failure"),
        ):
            with contextlib.redirect_stdout(io.StringIO()):
                scaffold.run_init(dry_args, Path(self._tmp_home))
        dry_leftover = _files_under_excluding_git(self._tmp_dry_target)
        self.assertEqual(
            dry_leftover, [],
            f"AC4/§S4: --dry-run must still write NOTHING even when a "
            f"mid-emission failure is injected; found {dry_leftover!r}",
        )


class ScaffoldDocstringNoLongerClaimsFailureWritesNothingTest(unittest.TestCase):
    """AC4 (§S4, C2) -- the module docstring of ``modelb_axi/scaffold.py``
    no longer contains the claim "(and any failure) writes NOTHING" (§S4:
    a failure mid-emission may leave a partial tree; the docstring must say
    so, and the failure envelope now carries ``emitted`` instead of a bare
    promise of nothing)."""

    def test_module_docstring_does_not_claim_failure_writes_nothing(self):
        import ast

        source = (REPO_ROOT / "modelb_axi" / "scaffold.py").read_text(encoding="utf-8")
        docstring = ast.get_docstring(ast.parse(source)) or ""
        self.assertNotIn(
            "(and any failure) writes NOTHING", docstring,
            "AC4/§S4: modelb_axi/scaffold.py's module docstring must no "
            "longer claim a failure writes nothing -- a mid-emission "
            "failure may leave a partial tree, and the failure envelope "
            f"now carries `emitted` instead; got docstring={docstring!r}",
        )


class RegressionPinFilePermissionsUnaffectedByAtomicWritesTest(unittest.TestCase):
    """REGRESSION PIN (\u00a7S2, C2 RED2) -- NOT a failing test: pins that
    atomic writes change no file's permissions BEFORE the coming GREEN
    replaces `write_text`/`shutil.copyfile` with a `tempfile.mkstemp` +
    `os.replace` helper. `mkstemp` creates files 0600; today `write_text`
    honours the umask and `deploy._deploy_file` + `shutil.copymode`
    preserves a hook script's source mode -- these three tests MUST PASS
    on current code, and must keep passing once `atomic_write(mode=None)`
    lands (CR-MDB-033 \u00a7S2's own AC: "produces the mode a plain write
    would (0o666 & ~umask), not mkstemp's 0600").

    Umask is set EXPLICITLY (0o022, saved/restored in setUp/tearDown) so
    the expected mode is computed from it rather than hard-coded 0o644 --
    a real installer run (`--harnesses claude-code,pi`) followed by a real
    `init` reading that install.toml drives every site under test through
    a subprocess that inherits the parent's umask at fork time (verified
    inheritance, not assumed)."""

    _UMASK = 0o022

    def setUp(self):
        self._prior_umask = os.umask(self._UMASK)
        self._tmp_home = tempfile.mkdtemp(prefix="modelb-axi-c2-perm-home-")
        self._tmp_bin = tempfile.mkdtemp(prefix="modelb-axi-c2-perm-bin-")
        self._tmp_target_root = tempfile.mkdtemp(prefix="modelb-axi-c2-perm-target-")
        self._tmp_project = tempfile.mkdtemp(prefix="modelb-axi-c2-perm-project-")
        _write_fake_executable(self._tmp_bin, "uv", _FAKE_UV_SCRIPT)
        _write_fake_executable(self._tmp_bin, "sandesh", _FAKE_SANDESH_SCRIPT)

    def tearDown(self):
        os.umask(self._prior_umask)
        for root in (self._tmp_home, self._tmp_bin, self._tmp_target_root, self._tmp_project):
            shutil.rmtree(root, ignore_errors=True)

    def _run_real_install_and_init(self):
        install_result = _run_module(
            "--yes", "--harnesses", "claude-code,pi",
            "--modelb-home", self._tmp_home,
            "--target-root", self._tmp_target_root,
            env_overrides={"PATH": self._tmp_bin},
        )
        self.assertEqual(
            install_result.returncode, 0,
            f"precondition: the real install must succeed; got "
            f"exit={install_result.returncode} "
            f"stdout={install_result.stdout!r} stderr={install_result.stderr!r}",
        )
        init_result = _run_module(
            "--yes", "init", *_INIT_REQUIRED_FLAGS,
            "--target", self._tmp_project,
            "--modelb-home", self._tmp_home,
        )
        self.assertEqual(
            init_result.returncode, 0,
            f"precondition: `init` reading the real install.toml must "
            f"succeed; got exit={init_result.returncode} "
            f"stdout={init_result.stdout!r} stderr={init_result.stderr!r}",
        )
        return install_result, init_result

    def test_compiled_pi_extension_has_umask_default_mode_not_mkstemp_0600(self):
        _install_result, init_result = self._run_real_install_and_init()
        ext_dir = Path(self._tmp_project) / ".pi" / "extensions"
        ts_files = sorted(ext_dir.glob("*.ts")) if ext_dir.is_dir() else []
        self.assertTrue(
            ts_files,
            f"precondition: at least one compiled .pi/extensions/*.ts must "
            f"exist; init stdout={init_result.stdout!r} "
            f"stderr={init_result.stderr!r}",
        )
        expected_mode = 0o666 & ~self._UMASK
        for ts_path in ts_files:
            mode = stat.S_IMODE(ts_path.stat().st_mode)
            # POSITIVE -- exact mode a plain write would produce under
            # this umask.
            self.assertEqual(
                mode, expected_mode,
                "REGRESSION PIN \u00a7S2: a compiled .pi/extensions/*.ts "
                f"must carry the mode a plain write would under umask "
                f"{oct(self._UMASK)} ({oct(expected_mode)}); got "
                f"{oct(mode)} for {ts_path}",
            )
            # NEGATIVE -- never mkstemp's 0600 default.
            self.assertNotEqual(
                mode, 0o600,
                f"REGRESSION PIN \u00a7S2: {ts_path} must NOT carry "
                f"mkstemp's 0600 default; got {oct(mode)}",
            )

    def test_scaffolded_agents_md_has_umask_default_mode_not_mkstemp_0600(self):
        _install_result, init_result = self._run_real_install_and_init()
        agents_path = Path(self._tmp_project) / "AGENTS.md"
        self.assertTrue(
            agents_path.is_file(),
            f"precondition: AGENTS.md must be emitted; init "
            f"stdout={init_result.stdout!r} stderr={init_result.stderr!r}",
        )
        expected_mode = 0o666 & ~self._UMASK
        mode = stat.S_IMODE(agents_path.stat().st_mode)
        # POSITIVE -- exact mode a plain write would produce under this umask.
        self.assertEqual(
            mode, expected_mode,
            "REGRESSION PIN \u00a7S2: a scaffolded AGENTS.md must carry "
            f"the mode a plain write would under umask {oct(self._UMASK)} "
            f"({oct(expected_mode)}); got {oct(mode)}",
        )
        # NEGATIVE -- never mkstemp's 0600 default.
        self.assertNotEqual(
            mode, 0o600,
            f"REGRESSION PIN \u00a7S2: AGENTS.md must NOT carry mkstemp's "
            f"0600 default; got {oct(mode)}",
        )

    def test_deployed_hook_script_keeps_source_executable_bit(self):
        install_result, _init_result = self._run_real_install_and_init()
        src_path = REPO_ROOT / "hooks-src" / "scripts" / "ambient-board-status"
        deployed_path = (
            Path(self._tmp_target_root) / ".agents" / "hooks" / "scripts"
            / "ambient-board-status"
        )
        self.assertTrue(
            deployed_path.is_file(),
            f"precondition: {deployed_path} must exist after a real "
            f"install; install stdout={install_result.stdout!r} "
            f"stderr={install_result.stderr!r}",
        )
        src_mode = stat.S_IMODE(src_path.stat().st_mode)
        deployed_mode = stat.S_IMODE(deployed_path.stat().st_mode)
        src_exec_bits = src_mode & 0o111
        deployed_exec_bits = deployed_mode & 0o111
        # precondition, not the pin itself -- the source script really is
        # executable in the tree this test reads from.
        self.assertEqual(
            src_exec_bits, 0o111,
            f"precondition: {src_path} must be executable (all-exec bits "
            f"set) in the source tree; got {oct(src_mode)}",
        )
        # POSITIVE -- the deployed copy keeps AT LEAST the source's exec bits.
        self.assertEqual(
            deployed_exec_bits, src_exec_bits,
            "REGRESSION PIN \u00a7S2: a deployed hook script must keep "
            f"its source's executable bit (0o111); source={oct(src_mode)} "
            f"deployed={oct(deployed_mode)}",
        )


class MidEmissionFailureInsideWiringCompilationEmittedTest(unittest.TestCase):
    """AC4 (\u00a7S4, C2) -- a mid-emission ``OSError`` injected INSIDE
    ``hooks.compile_wiring`` (after some wiring files are already written
    to disk, but BEFORE ``compile_wiring`` returns) must still leave the
    failure envelope's ``emitted`` field listing EXACTLY the files present
    under ``--target``.

    Distinct from ``MidEmissionFailureHonestPartialEmissionTest`` above,
    which injects its failure in ``_render_agents_md`` -- BEFORE hook
    compilation ever starts, so ``scaffold._emit_plan``'s
    ``emitted.extend(harness_entry["emitted_files"])`` line (only reached
    once ``compile_wiring`` RETURNS) is never exercised by that test at
    all. Here the injection is on ``hooks.atomic_write`` (the name
    ``hooks.py`` imports it under), patched to call the REAL
    ``_fsutil.atomic_write`` for its first two successful calls and then
    raise -- landing the failure mid-way through the FIRST (roster-order)
    harness's wiring emission, after real files already landed on disk.

    Measured (orchestrator repro): with harnesses ``["pi", "claude-code",
    "opencode", "hermes"]`` recorded in that order in ``install.toml``,
    ``scaffold._emit_plan``'s ``roster_harnesses`` preserves that order,
    so ``compile_wiring`` starts wiring "pi" first; a failure after the
    2nd successful wiring write leaves ``.pi/extensions/ambient-board-
    status.ts`` and ``.pi/extensions/block-bad-cycle-task-name.ts`` on
    disk (from ``hooks._emit_pi``'s per-instance loop), while
    ``scaffold._emit_plan`` never reaches its ``emitted.extend(...)``
    line for this harness -- ``compile_wiring`` raised before returning
    a report at all -- so NEITHER file is listed in the failure
    envelope's ``emitted``, even though both are really on disk under
    ``--target``. This breaks the \u00a7S4 AC's "exactly the files
    present" contract specifically for wiring output, which the
    ``_render_agents_md``-injection test above cannot reach."""

    def setUp(self):
        self._tmp_home = tempfile.mkdtemp(prefix="modelb-axi-c2-wiring-partial-home-")
        self._tmp_target = tempfile.mkdtemp(prefix="modelb-axi-c2-wiring-partial-target-")
        _write_full_install_toml(
            self._tmp_home,
            harnesses=("pi", "claude-code", "opencode", "hermes"),
        )

    def tearDown(self):
        for root in (self._tmp_home, self._tmp_target):
            shutil.rmtree(root, ignore_errors=True)

    def test_failure_inside_compile_wiring_still_lists_exact_partial_tree_in_emitted(self):
        from modelb_axi import scaffold
        from modelb_axi._fsutil import atomic_write as real_atomic_write

        call_count = {"n": 0}
        FAIL_AFTER = 2  # let exactly two real wiring files land, then raise.

        def _flaky_atomic_write(path, data, mode=None):
            call_count["n"] += 1
            if call_count["n"] > FAIL_AFTER:
                raise OSError(
                    "CR-MDB-033 C2 injected mid-compile_wiring failure"
                )
            return real_atomic_write(path, data, mode=mode)

        args = _init_args(self._tmp_target, dry_run=False)
        out = io.StringIO()
        with mock.patch(
            "modelb_axi.hooks.atomic_write", side_effect=_flaky_atomic_write,
        ), contextlib.redirect_stdout(out):
            exit_code = scaffold.run_init(args, Path(self._tmp_home))
        combined = out.getvalue()

        # POSITIVE -- non-zero exit is the failure signal.
        self.assertNotEqual(
            exit_code, 0,
            "AC4/\u00a7S4 (wiring variant): a mid-compile_wiring OSError "
            f"must exit non-zero; got exit={exit_code} stdout={combined!r}",
        )

        leftover = _files_under_excluding_git(self._tmp_target)

        # NEGATIVE / bound -- the injection lands after exactly two real
        # wiring writes succeed, so the two known pi-extension files must
        # be genuinely present on disk (never zero -- and never the full
        # wiring set, which would mean the injection missed its mark).
        expected_partial_wiring = {
            str(Path(".pi") / "extensions" / "ambient-board-status.ts"),
            str(Path(".pi") / "extensions" / "block-bad-cycle-task-name.ts"),
        }
        self.assertTrue(
            expected_partial_wiring.issubset(set(leftover)),
            "AC4 precondition: the injection must leave exactly the first "
            f"two pi wiring files on disk; expected "
            f"{sorted(expected_partial_wiring)} to be a subset of leftover "
            f"{leftover!r} -- got exit={exit_code} stdout={combined!r}",
        )
        third_pi_file = str(
            Path(".pi") / "extensions" / "post-regression-disk-reminder.ts"
        )
        self.assertNotIn(
            third_pi_file, leftover,
            "AC4 precondition: the 3rd pi wiring write must be the one "
            f"that raised, so {third_pi_file!r} must NOT be on disk; got "
            f"leftover={leftover!r}",
        )

        envelope = _decode_envelope(combined)
        axi = envelope.get("axi", {})
        # POSITIVE -- axi.ok is false on this path.
        self.assertIs(
            axi.get("ok"), False,
            "AC4 (wiring variant): the failure envelope must report "
            f"axi.ok false; got envelope={envelope!r}",
        )
        emitted = axi.get("emitted")

        # THE BUG this test pins: the two pi wiring files that are REALLY
        # on disk must be listed in `emitted` -- today they are not,
        # because `scaffold._emit_plan` only calls
        # `emitted.extend(harness_entry["emitted_files"])` AFTER
        # `compile_wiring` returns, and `compile_wiring` raised instead of
        # returning.
        self.assertTrue(
            expected_partial_wiring.issubset(set(emitted or [])),
            "AC4/\u00a7S4 (wiring variant): every wiring file really on "
            "disk under --target must be listed in the failure envelope's "
            f"`emitted` field; expected {sorted(expected_partial_wiring)} "
            f"to be a subset of emitted={emitted!r} (files really on disk: "
            f"{leftover!r}); envelope={envelope!r}",
        )

        # POSITIVE -- `emitted`, compared as a SET of relative paths, must
        # equal EXACTLY the files present under --target -- the same
        # "exactly the files present" contract
        # ``MidEmissionFailureHonestPartialEmissionTest`` already pins for
        # the pre-wiring injection point, now pinned for the INSIDE-
        # wiring-compilation injection point too.
        self.assertEqual(
            set(emitted or []), set(leftover),
            "AC4/\u00a7S4 (wiring variant): the failure envelope's "
            "`emitted` field must list EXACTLY the files present under "
            f"--target (compared as sets of relative paths); got "
            f"emitted={emitted!r} leftover on disk={leftover!r}; "
            f"envelope={envelope!r}",
        )


# ---------------------------------------------------------------------------
# CR-MDB-033 cycle C3 -- \u00a7S5 validation and hygiene, \u00a7S6 the installer's
# result is one AXI envelope on stdout. Appended below the cycle C1 (\u00a7S1/
# \u00a7S3) and C2 (\u00a7S2/\u00a7S4) classes above, which are GREEN as of this
# cycle's baseline (measured 377 tests / 0 failures / 11 skips at fee5f6b)
# and are left untouched.
#
# MEASURED defects this cycle's tests pin (docs/changes/
# CR-MDB-033-installer-correctness.md \u00a7S5/\u00a7S6):
#   - scaffold.resolve_harnesses trusts install.toml's `harnesses` list
#     UNCHECKED -- only the --harnesses dev-override branch validates
#     against HARNESS_ROSTER_IDS -- so a stale/typo'd id silently reaches
#     _emit_plan's roster filter instead of raising UnknownHarnessError.
#   - modelb_axi.cli never calls modelb_axi.axi.envelope for ANY
#     installer-flow exit path; every stage prints bare `print(...)` to
#     stdout by default (preflight.py's two `deps: ...` lines included),
#     so none of the CR's eight exit paths emits an AXI envelope at all.
#   - config._toml_string escapes only backslash/quote/\n/\t/\r -- every
#     other C0 control and DEL pass through RAW, which tomllib's basic-
#     string grammar rejects; scaffold._render_instance_toml has its OWN
#     unescaped `f'{field} = "{value}"'` quoting (context-table defect #7).
#   - deploy.py/hooks.py/cli.py/preflight.py/harness.py cite bare
#     `DN \u00a7N` without naming the DN file, and deploy.py calls the shared
#     asset store the "Vercel store" twice.
#   - tests/test_tooling_adoption.py's module docstring cites
#     `modelb_axi/cli.py:233-237` by line range.
# ---------------------------------------------------------------------------


def _run_main_in_process(argv, env_overrides=None, isatty=False, input_answers=None):
    """Drive ``modelb_axi.cli.main()`` IN-PROCESS (never subprocess) so the
    interactive confirm prompts can be exercised: a subprocess's stdin is
    never a real tty (``sys.stdin.isatty()`` is always False under
    ``subprocess.DEVNULL``/``PIPE``), so ``--yes`` is not even needed to
    stay non-interactive under `_run_module` -- which also means a
    subprocess probe can NEVER reach the "user declines" exit paths at
    all. Mirrors the in-process idiom this file's own C1/C2 classes
    already use for ``cli._deploy_stage``/``scaffold.run_init`` when a
    production seam (here: a real tty + real stdin answers) is otherwise
    unreachable through a subprocess run. Returns
    ``(returncode, stdout_text, stderr_text)``."""
    from modelb_axi import cli

    env_patch = dict(env_overrides) if env_overrides else {}
    answers = list(input_answers) if input_answers else []
    stdout_buf = io.StringIO()
    stderr_buf = io.StringIO()
    with mock.patch.dict(os.environ, env_patch), \
         mock.patch.object(sys.stdin, "isatty", return_value=isatty), \
         mock.patch("builtins.input", side_effect=answers), \
         contextlib.redirect_stdout(stdout_buf), \
         contextlib.redirect_stderr(stderr_buf):
        code = cli.main(argv)
    return code, stdout_buf.getvalue(), stderr_buf.getvalue()


class InstallTomlUnknownHarnessIdRejectedTest(unittest.TestCase):
    """AC (\u00a7S5) -- an install.toml listing a non-roster harness id makes
    a real `init` fail with the SAME UnknownHarnessError and exit code as
    the `--harnesses` dev-override rejection, naming the id, before any
    file is written under --target -- and on --dry-run too. MEASURED
    current defect: `scaffold.resolve_harnesses` trusts install.toml's
    `harnesses` list UNCHECKED (only the `--harnesses` override path
    validates against `HARNESS_ROSTER_IDS`), so a stale/typo'd id
    silently reaches `_emit_plan`'s
    `roster_harnesses = [h for h in harnesses if h in HARNESS_ROSTER_IDS]`
    filter instead of raising a named error -- today the run SUCCEEDS
    (exit 0, full scaffold tree written) with the bad id silently
    dropped."""

    def setUp(self):
        self._tmp_home = tempfile.mkdtemp(prefix="modelb-axi-c3-s5-badharness-home-")
        self._tmp_target = tempfile.mkdtemp(prefix="modelb-axi-c3-s5-badharness-target-")
        self._tmp_dry_target = tempfile.mkdtemp(prefix="modelb-axi-c3-s5-badharness-dry-target-")
        _write_full_install_toml(self._tmp_home, harnesses=("bogus-harness",))

    def tearDown(self):
        for root in (self._tmp_home, self._tmp_target, self._tmp_dry_target):
            shutil.rmtree(root, ignore_errors=True)

    def test_stale_id_in_install_toml_exits_same_as_dev_override_before_any_write(self):
        override_home = tempfile.mkdtemp(prefix="modelb-axi-c3-s5-badharness-override-home-")
        override_target = tempfile.mkdtemp(prefix="modelb-axi-c3-s5-badharness-override-target-")
        try:
            override_result = _run_module(
                "--yes", "init", *_INIT_REQUIRED_FLAGS,
                "--harnesses", "bogus-harness",
                "--target", override_target,
                "--modelb-home", override_home,
                "--no-commit",
            )
        finally:
            shutil.rmtree(override_home, ignore_errors=True)
            shutil.rmtree(override_target, ignore_errors=True)
        self.assertNotEqual(
            override_result.returncode, 0,
            "precondition: the --harnesses dev-override rejection itself "
            f"must fail; got exit={override_result.returncode} "
            f"combined={override_result.stdout + override_result.stderr!r}",
        )

        result = _run_module(
            "--yes", "init", *_INIT_REQUIRED_FLAGS,
            "--target", self._tmp_target,
            "--modelb-home", self._tmp_home,
            "--no-commit",
        )
        combined = result.stdout + result.stderr
        # POSITIVE -- non-zero exit, and the SAME exit code as the
        # already-validated --harnesses override rejection.
        self.assertNotEqual(
            result.returncode, 0,
            f"\u00a7S5: a stale harness id read from install.toml must fail "
            f"`init`; got exit={result.returncode} combined={combined!r}",
        )
        self.assertEqual(
            result.returncode, override_result.returncode,
            f"\u00a7S5: an install.toml-sourced unknown harness id must exit "
            f"with the SAME code as the --harnesses override rejection "
            f"({override_result.returncode}); got {result.returncode}",
        )
        # POSITIVE -- names the offending id and the valid roster (the
        # SAME UnknownHarnessError vocabulary the override path uses).
        self.assertIn("bogus-harness", combined)
        for harness_id in HARNESS_ROSTER_IDS:
            self.assertIn(
                harness_id, combined,
                f"\u00a7S5: the error must name the valid roster (missing "
                f"{harness_id!r}); got combined={combined!r}",
            )
        # NEGATIVE / bound -- no file anywhere under --target.
        leftover = _files_under_excluding_git(self._tmp_target)
        self.assertEqual(
            leftover, [],
            f"\u00a7S5: a rejected harness id must leave NO FILE under "
            f"--target; found {leftover!r}; combined={combined!r}",
        )

    def test_dry_run_also_rejects_the_stale_id_before_any_write(self):
        result = _run_module(
            "--yes", "init", *_INIT_REQUIRED_FLAGS,
            "--target", self._tmp_dry_target,
            "--modelb-home", self._tmp_home,
            "--no-commit", "--dry-run",
        )
        combined = result.stdout + result.stderr
        self.assertNotEqual(
            result.returncode, 0,
            f"\u00a7S5: --dry-run must ALSO reject a stale install.toml "
            f"harness id (a hard validation error, unlike the \u00a7S1 "
            f"hooks_scripts_dir case which --dry-run may preview as a "
            f"warning); got exit={result.returncode} combined={combined!r}",
        )
        self.assertIn("bogus-harness", combined)
        leftover = _files_under_excluding_git(self._tmp_dry_target)
        self.assertEqual(
            leftover, [],
            f"\u00a7S5: --dry-run must write NOTHING under --target even "
            f"when rejecting a stale harness id; found {leftover!r}",
        )


class TomlStringControlCharacterRoundTripTest(unittest.TestCase):
    """AC (\u00a7S5) -- config._toml_string must escape every C0 control
    (U+0000-U+001F) and DEL (U+007F) as \\uXXXX so every install.toml
    string write round-trips through tomllib. MEASURED current defect:
    `_toml_string` only escapes backslash/quote/\\n/\\t/\\r -- every other
    C0 control and DEL pass through RAW, which tomllib's basic-string
    grammar refuses to parse (or parses to the wrong character)."""

    def test_every_c0_control_and_del_round_trips_through_tomllib(self):
        from modelb_axi.config import _toml_string

        offenders = []
        for codepoint in list(range(0x20)) + [0x7F]:
            char = chr(codepoint)
            if char in ("\n", "\t", "\r"):
                continue  # already correctly short-escaped -- not this gap
            serialized = _toml_string(char)
            toml_text = f"value = {serialized}\n"
            try:
                parsed = tomllib.loads(toml_text)
            except tomllib.TOMLDecodeError as exc:
                offenders.append(f"U+{codepoint:04X}: TOMLDecodeError({exc})")
                continue
            if parsed.get("value") != char:
                offenders.append(
                    f"U+{codepoint:04X}: round-tripped to {parsed.get('value')!r}"
                )
        self.assertEqual(
            offenders, [],
            f"\u00a7S5: _toml_string must escape every C0 control and DEL as "
            f"\\uXXXX so it round-trips through tomllib; offenders={offenders!r}",
        )


class RenderInstanceTomlUsesSharedStringWriterTest(unittest.TestCase):
    """AC (\u00a7S5) -- scaffold._render_instance_toml must write its string
    values through config._toml_string (the ONE TOML string writer), not
    its own unescaped `f'{field} = "{value}"'` quoting (context-table
    defect #7: two hand-rolled TOML writers, one escapes, one does not).
    MEASURED current defect: a string value carrying a double-quote or
    backslash renders unescaped TOML that tomllib refuses to parse."""

    def test_command_value_with_quote_and_backslash_round_trips_through_tomllib(self):
        from modelb_axi.scaffold import _render_instance_toml

        instance = {
            "event": "pre-tool-use",
            "matcher": 'weird "matcher" value \\with\\ backslashes',
            "command": "guard-example",
            "tier": None,
            "timeout": None,
            "fail_direction": None,
        }
        rendered = _render_instance_toml(instance)
        try:
            parsed = tomllib.loads(rendered)
        except tomllib.TOMLDecodeError as exc:
            self.fail(
                f"\u00a7S5: _render_instance_toml must escape string values "
                f"through config._toml_string so the output parses as valid "
                f"TOML; tomllib raised {exc} on rendered={rendered!r}"
            )
        self.assertEqual(
            parsed.get("matcher"), instance["matcher"],
            f"\u00a7S5: the rendered matcher value must round-trip exactly "
            f"through tomllib; got {parsed.get('matcher')!r}",
        )


class DnCitationsNameTheirFileAndNoVercelReferenceTest(unittest.TestCase):
    """AC (\u00a7S5) -- every `DN \u00a7` citation in modelb_axi/ names its DN
    file (e.g. `DN-harness-agnostic-hooks \u00a74`, never the bare `DN \u00a74`),
    and the string 'Vercel' appears nowhere in modelb_axi/ ('shared store'
    is the correct term) -- two grep gates. MEASURED current defects:
    deploy.py/hooks.py/cli.py/preflight.py/harness.py/scaffold.py cite
    bare `DN \u00a7N` without naming which DN doc, and deploy.py calls the
    shared asset store the 'Vercel store' twice."""

    def test_no_bare_dn_section_citation_without_a_named_dn_file(self):
        module_dir = REPO_ROOT / "modelb_axi"
        offenders = []
        for path in sorted(module_dir.rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            text = path.read_text(encoding="utf-8")
            for lineno, line in enumerate(text.splitlines(), start=1):
                if "DN \u00a7" in line:
                    offenders.append(
                        f"{path.relative_to(REPO_ROOT)}:{lineno}: {line.strip()}"
                    )
        self.assertEqual(
            offenders, [],
            "\u00a7S5: every `DN \u00a7` citation must name its DN file (e.g. "
            "`DN-harness-agnostic-hooks \u00a74`), never the bare `DN \u00a7N`; "
            f"offending lines: {offenders!r}",
        )

    def test_vercel_appears_nowhere_in_modelb_axi(self):
        module_dir = REPO_ROOT / "modelb_axi"
        offenders = []
        for path in sorted(module_dir.rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            text = path.read_text(encoding="utf-8")
            for lineno, line in enumerate(text.splitlines(), start=1):
                if "Vercel" in line:
                    offenders.append(
                        f"{path.relative_to(REPO_ROOT)}:{lineno}: {line.strip()}"
                    )
        self.assertEqual(
            offenders, [],
            "\u00a7S5: 'Vercel' must not appear anywhere in modelb_axi/ "
            "('shared store' is the correct term); offending lines: "
            f"{offenders!r}",
        )


class ToolingAdoptionCitesCliPyByFunctionNotLineRangeTest(unittest.TestCase):
    """AC (\u00a7S6 tail) -- tests/test_tooling_adoption.py must cite
    modelb_axi/cli.py by FUNCTION name, never by line range (a moving
    target once \u00a7S6 adds envelope emission to cli.py). MEASURED current
    defect: its module docstring cites `modelb_axi/cli.py:233-237`."""

    def test_cli_py_citation_names_a_function_never_a_line_range(self):
        target = REPO_ROOT / "tests" / "test_tooling_adoption.py"
        text = target.read_text(encoding="utf-8")
        self.assertIn(
            "cli.py", text,
            "\u00a7S6 precondition: tests/test_tooling_adoption.py must still "
            "cite modelb_axi/cli.py somewhere (the fix renames the "
            "citation to a function, it does not delete it)",
        )
        offenders = [
            f"tests/test_tooling_adoption.py:{i}: {line.strip()}"
            for i, line in enumerate(text.splitlines(), start=1)
            if re.search(r"cli\.py:\d+", line)
        ]
        self.assertEqual(
            offenders, [],
            "\u00a7S6: tests/test_tooling_adoption.py must cite "
            "modelb_axi/cli.py by function name, never a line range; "
            f"offending lines: {offenders!r}",
        )


class InstallerEightExitPathsEnvelopeTest(unittest.TestCase):
    """AC (\u00a7S6) -- every one of the eight installer exit paths in the
    CR's table writes EXACTLY ONE AXI envelope to stdout (verb=install)
    whose outcome/ok match the table, and the process exit code matches
    too -- asserted per path via subTest (a path not asserted is a path
    not wired, mirroring this file's own AtomicWriteSixSitesTest
    precedent). MEASURED current defect: modelb_axi.cli never calls
    modelb_axi.axi.envelope for ANY installer-flow exit path (only
    scaffold.run_init does) -- every subtest below decodes bare human
    prose on stdout today, not a TOON envelope."""

    def setUp(self):
        self._tmp_bin = tempfile.mkdtemp(prefix="modelb-axi-c3-envelope-bin-")
        _write_fake_executable(self._tmp_bin, "uv", _FAKE_UV_SCRIPT)
        _write_fake_executable(self._tmp_bin, "sandesh", _FAKE_SANDESH_SCRIPT)

    def tearDown(self):
        shutil.rmtree(self._tmp_bin, ignore_errors=True)

    def _decode_axi(self, stdout: str, label: str) -> dict:
        try:
            return _decode_envelope(stdout).get("axi", {})
        except Exception as exc:
            self.fail(
                f"\u00a7S6 path={label}: stdout must decode as a TOON AXI "
                f"envelope via modelb_axi.toon; got exc={exc!r} "
                f"stdout={stdout!r}"
            )

    def _assert_path(self, label, returncode, stdout, expected_exit, expected_outcome, expected_ok):
        axi = self._decode_axi(stdout, label)
        self.assertEqual(
            axi.get("verb"), "install",
            f"\u00a7S6 path={label}: envelope verb must be 'install'; got axi={axi!r}",
        )
        self.assertEqual(
            axi.get("outcome"), expected_outcome,
            f"\u00a7S6 path={label}: envelope outcome must be "
            f"{expected_outcome!r}; got axi={axi!r}",
        )
        self.assertEqual(
            axi.get("ok"), expected_ok,
            f"\u00a7S6 path={label}: envelope ok must be {expected_ok!r}; "
            f"got axi={axi!r}",
        )
        self.assertEqual(
            returncode, expected_exit,
            f"\u00a7S6 path={label}: process exit code must be "
            f"{expected_exit}; got {returncode} (envelope axi={axi!r})",
        )

    def test_each_of_the_eight_exit_paths_writes_one_matching_envelope(self):
        with self.subTest(path="already_installed"):
            self._check_already_installed()
        with self.subTest(path="aborted (decline proceed)"):
            self._check_aborted_decline_proceed()
        with self.subTest(path="preflight_failed"):
            self._check_preflight_failed()
        with self.subTest(path="harness_rejected"):
            self._check_harness_rejected()
        with self.subTest(path="aborted (decline harness set)"):
            self._check_aborted_decline_harness_set()
        with self.subTest(path="deploy_failed"):
            self._check_deploy_failed()
        with self.subTest(path="deploy_skipped"):
            self._check_deploy_skipped()
        with self.subTest(path="installed"):
            self._check_installed()

    def _check_already_installed(self):
        home = tempfile.mkdtemp(prefix="modelb-axi-c3-envelope-installed-notice-")
        try:
            _write_full_install_toml(home, harnesses=("claude-code",))
            result = _run_module("--yes", "--modelb-home", home)
            self._assert_path(
                "already_installed", result.returncode, result.stdout,
                expected_exit=0, expected_outcome="already_installed", expected_ok=True,
            )
        finally:
            shutil.rmtree(home, ignore_errors=True)

    def _check_aborted_decline_proceed(self):
        home = tempfile.mkdtemp(prefix="modelb-axi-c3-envelope-declineproceed-")
        try:
            code, stdout, _stderr = _run_main_in_process(
                ["--modelb-home", home], isatty=True, input_answers=["n"],
            )
            self._assert_path(
                "aborted-decline-proceed", code, stdout,
                expected_exit=1, expected_outcome="aborted", expected_ok=False,
            )
        finally:
            shutil.rmtree(home, ignore_errors=True)

    def _check_preflight_failed(self):
        home = tempfile.mkdtemp(prefix="modelb-axi-c3-envelope-nouv-home-")
        empty_bin = tempfile.mkdtemp(prefix="modelb-axi-c3-envelope-nouv-bin-")
        try:
            result = _run_module(
                "--yes", "--modelb-home", home,
                env_overrides={"PATH": empty_bin},
            )
            self._assert_path(
                "preflight_failed", result.returncode, result.stdout,
                expected_exit=1, expected_outcome="preflight_failed", expected_ok=False,
            )
        finally:
            shutil.rmtree(home, ignore_errors=True)
            shutil.rmtree(empty_bin, ignore_errors=True)

    def _check_harness_rejected(self):
        home = tempfile.mkdtemp(prefix="modelb-axi-c3-envelope-badharness-")
        try:
            result = _run_module(
                "--yes", "--harnesses", "bogus-harness",
                "--modelb-home", home,
                env_overrides={"PATH": self._tmp_bin},
            )
            self._assert_path(
                "harness_rejected", result.returncode, result.stdout,
                expected_exit=1, expected_outcome="harness_rejected", expected_ok=False,
            )
        finally:
            shutil.rmtree(home, ignore_errors=True)

    def _check_aborted_decline_harness_set(self):
        home = tempfile.mkdtemp(prefix="modelb-axi-c3-envelope-declineharness-home-")
        target_root = tempfile.mkdtemp(prefix="modelb-axi-c3-envelope-declineharness-target-")
        try:
            code, stdout, _stderr = _run_main_in_process(
                ["--modelb-home", home, "--target-root", target_root],
                env_overrides={"PATH": self._tmp_bin},
                isatty=True, input_answers=["y", "n"],
            )
            self._assert_path(
                "aborted-decline-harness-set", code, stdout,
                expected_exit=1, expected_outcome="aborted", expected_ok=False,
            )
        finally:
            shutil.rmtree(home, ignore_errors=True)
            shutil.rmtree(target_root, ignore_errors=True)

    def _check_deploy_failed(self):
        home = tempfile.mkdtemp(prefix="modelb-axi-c3-envelope-deployfailed-home-")
        target_root = tempfile.mkdtemp(prefix="modelb-axi-c3-envelope-deployfailed-target-")
        try:
            # A non-symlink file already occupying the harness-skill link
            # path makes `deploy._link_harness_skills` raise DeployError
            # deterministically (the claude-code skills-dir mapping).
            blocker = Path(target_root) / ".claude" / "skills" / "crucible"
            blocker.parent.mkdir(parents=True, exist_ok=True)
            blocker.write_text(
                "not a symlink -- blocks the harness link step\n", encoding="utf-8",
            )
            result = _run_module(
                "--yes", "--harnesses", "claude-code",
                "--modelb-home", home,
                "--target-root", target_root,
                env_overrides={"PATH": self._tmp_bin},
            )
            self._assert_path(
                "deploy_failed", result.returncode, result.stdout,
                expected_exit=1, expected_outcome="deploy_failed", expected_ok=False,
            )
            self.assertFalse(
                (Path(home) / "install.toml").exists(),
                "\u00a7S6 path=deploy_failed: install.toml must never be "
                "written on a deploy failure (written last, on full "
                "success only)",
            )
        finally:
            shutil.rmtree(home, ignore_errors=True)
            shutil.rmtree(target_root, ignore_errors=True)

    def _check_deploy_skipped(self):
        home = tempfile.mkdtemp(prefix="modelb-axi-c3-envelope-noroot-")
        try:
            result = _run_module(
                "--yes", "--harnesses", "claude-code",
                "--modelb-home", home,
                env_overrides={"PATH": self._tmp_bin},
            )
            self._assert_path(
                "deploy_skipped", result.returncode, result.stdout,
                expected_exit=0, expected_outcome="deploy_skipped", expected_ok=True,
            )
        finally:
            shutil.rmtree(home, ignore_errors=True)

    def _check_installed(self):
        home = tempfile.mkdtemp(prefix="modelb-axi-c3-envelope-installed-")
        target_root = tempfile.mkdtemp(prefix="modelb-axi-c3-envelope-installed-target-")
        try:
            result = _run_module(
                "--yes", "--harnesses", "claude-code",
                "--modelb-home", home,
                "--target-root", target_root,
                env_overrides={"PATH": self._tmp_bin},
            )
            self._assert_path(
                "installed", result.returncode, result.stdout,
                expected_exit=0, expected_outcome="installed", expected_ok=True,
            )
        finally:
            shutil.rmtree(home, ignore_errors=True)
            shutil.rmtree(target_root, ignore_errors=True)


class StdoutCarriesOnlyEnvelopeAllHumanLinesOnStderrTest(unittest.TestCase):
    """AC (\u00a7S6) -- on every path, stdout carries NOTHING but the one AXI
    envelope, and every human line from cli.py AND preflight.py is on
    stderr -- including BOTH `deps:` lines (the pre-remediation report and
    the post-install update, CR-MDB-014 AC4) on a run that installs
    Sandesh. MEASURED current defect: preflight.py's two `deps: ...`
    prints and every cli.py progress/banner line go to stdout today (no
    `file=sys.stderr`)."""

    _HUMAN_MARKERS = (
        "modelb-axi:", "deps:", "harnesses selected:",
        "[stage 1/3]", "[stage 2/3]", "[stage 3/3]", "wrote ",
    )

    def setUp(self):
        self._tmp_home = tempfile.mkdtemp(prefix="modelb-axi-c3-s6-stdout-home-")
        self._tmp_bin = tempfile.mkdtemp(prefix="modelb-axi-c3-s6-stdout-bin-")
        self._tmp_target_root = tempfile.mkdtemp(prefix="modelb-axi-c3-s6-stdout-target-")
        marker_fd, self._marker_path = tempfile.mkstemp(prefix="c3-s6-uv-install-marker-")
        os.close(marker_fd)
        os.remove(self._marker_path)  # must NOT exist yet -- proves invocation
        _write_fake_executable(self._tmp_bin, "uv", _FAKE_UV_SCRIPT_WITH_INSTALL_MARKER)
        # Deliberately NO fake `sandesh` binary -- triggers the proactive
        # install path, so BOTH `deps:` lines print (pre-remediation +
        # post-install update).

    def tearDown(self):
        for root in (self._tmp_home, self._tmp_bin, self._tmp_target_root):
            shutil.rmtree(root, ignore_errors=True)
        if os.path.exists(self._marker_path):
            os.remove(self._marker_path)

    def test_stdout_is_exactly_one_envelope_and_both_deps_lines_are_on_stderr(self):
        result = _run_module(
            "--yes", "--harnesses", "claude-code",
            "--modelb-home", self._tmp_home,
            "--target-root", self._tmp_target_root,
            env_overrides={
                "PATH": self._tmp_bin,
                "FAKE_UV_INSTALL_MARKER": self._marker_path,
            },
        )
        self.assertEqual(
            result.returncode, 0,
            f"precondition: full install must succeed; exit={result.returncode} "
            f"stdout={result.stdout!r} stderr={result.stderr!r}",
        )
        self.assertTrue(
            os.path.exists(self._marker_path),
            "precondition: the sandesh proactive-install shim must have "
            f"fired; stdout={result.stdout!r} stderr={result.stderr!r}",
        )

        # POSITIVE -- stdout decodes as exactly one AXI envelope.
        try:
            axi = _decode_envelope(result.stdout).get("axi", {})
        except Exception as exc:
            self.fail(
                f"\u00a7S6: stdout must be exactly one decodable TOON AXI "
                f"envelope; exc={exc!r} stdout={result.stdout!r}"
            )
        self.assertEqual(
            axi.get("outcome"), "installed",
            f"precondition: outcome must be installed; got axi={axi!r}",
        )

        # NEGATIVE -- no human/progress marker text leaks onto stdout.
        offenders = [m for m in self._HUMAN_MARKERS if m in result.stdout]
        self.assertEqual(
            offenders, [],
            f"\u00a7S6: stdout must carry NOTHING but the envelope; found "
            f"human markers {offenders!r} in stdout={result.stdout!r}",
        )

        # POSITIVE -- BOTH deps: lines (pre-remediation report + the
        # post-install update) land on stderr.
        self.assertIn(
            "deps: uv=detected sandesh=absent crucible=absent", result.stderr,
            f"\u00a7S6: the pre-remediation deps: line must be on stderr; "
            f"got stderr={result.stderr!r}",
        )
        self.assertIn(
            "deps: uv=detected sandesh=installed crucible=absent", result.stderr,
            f"\u00a7S6: the post-install-update deps: line must be on "
            f"stderr; got stderr={result.stderr!r}",
        )
        # POSITIVE -- the stage/progress banners are on stderr too.
        self.assertIn(
            "harnesses selected:", result.stderr,
            f"\u00a7S6: 'harnesses selected:' must be on stderr; got "
            f"stderr={result.stderr!r}",
        )
        self.assertIn(
            "[stage 1/3]", result.stderr,
            f"\u00a7S6: stage banners must be on stderr; got "
            f"stderr={result.stderr!r}",
        )


class InstalledEnvelopeFieldsMatchInstallTomlAndForeignFileTest(unittest.TestCase):
    """AC (\u00a7S6) -- on the `installed` outcome, the envelope's `deps`
    equals install.toml's [deps] table, `managed_files` equals the number
    of [[files]] entries, and a foreign
    `<target-root>/.agents/scripts/gate-lock.sh` (present before the run,
    absent from any prior manifest) appears in `unmanaged`."""

    def setUp(self):
        self._tmp_home = tempfile.mkdtemp(prefix="modelb-axi-c3-s6-fields-home-")
        self._tmp_bin = tempfile.mkdtemp(prefix="modelb-axi-c3-s6-fields-bin-")
        self._tmp_target_root = tempfile.mkdtemp(prefix="modelb-axi-c3-s6-fields-target-")
        _write_fake_executable(self._tmp_bin, "uv", _FAKE_UV_SCRIPT)
        _write_fake_executable(self._tmp_bin, "sandesh", _FAKE_SANDESH_SCRIPT)
        # A foreign, non-Model-B file at a path the tool scripts deploy
        # to -- present BEFORE the run, absent from any manifest.
        self._foreign_content = "#!/bin/sh\necho not-model-bs-gate-lock\n"
        self._foreign = Path(self._tmp_target_root) / ".agents" / "scripts" / "gate-lock.sh"
        self._foreign.parent.mkdir(parents=True, exist_ok=True)
        self._foreign.write_text(self._foreign_content, encoding="utf-8")

    def tearDown(self):
        for root in (self._tmp_home, self._tmp_bin, self._tmp_target_root):
            shutil.rmtree(root, ignore_errors=True)

    def test_installed_envelope_deps_managed_files_and_unmanaged_match_install_toml(self):
        result = _run_module(
            "--yes", "--harnesses", "claude-code",
            "--modelb-home", self._tmp_home,
            "--target-root", self._tmp_target_root,
            env_overrides={"PATH": self._tmp_bin},
        )
        self.assertEqual(
            result.returncode, 0,
            f"precondition: full install must succeed; exit={result.returncode} "
            f"stdout={result.stdout!r} stderr={result.stderr!r}",
        )
        try:
            axi = _decode_envelope(result.stdout).get("axi", {})
        except Exception as exc:
            self.fail(
                f"\u00a7S6: stdout must decode as a TOON AXI envelope; "
                f"exc={exc!r} stdout={result.stdout!r}"
            )
        self.assertEqual(
            axi.get("outcome"), "installed",
            f"precondition: outcome must be installed; got axi={axi!r}",
        )

        with open(Path(self._tmp_home) / "install.toml", "rb") as fh:
            toml_data = tomllib.load(fh)

        # POSITIVE -- deps equals install.toml [deps] exactly.
        self.assertEqual(
            axi.get("deps"), toml_data.get("deps"),
            f"\u00a7S6: envelope deps must equal install.toml [deps]; "
            f"envelope={axi.get('deps')!r} toml={toml_data.get('deps')!r}",
        )
        # POSITIVE -- managed_files equals the [[files]] entry count.
        files_section = toml_data.get("files", [])
        self.assertEqual(
            axi.get("managed_files"), len(files_section),
            f"\u00a7S6: envelope managed_files must equal len([[files]]) "
            f"({len(files_section)}); got {axi.get('managed_files')!r}",
        )
        # POSITIVE -- the foreign gate-lock.sh appears in unmanaged.
        unmanaged = axi.get("unmanaged", [])
        expected_rel = str(Path(".agents") / "scripts" / "gate-lock.sh")
        self.assertIn(
            expected_rel, unmanaged,
            f"\u00a7S6: the foreign gate-lock.sh must appear in envelope "
            f"unmanaged (rel={expected_rel!r}); got unmanaged={unmanaged!r}",
        )
        # NEGATIVE -- byte-identical, never adopted into the manifest.
        self.assertEqual(
            self._foreign.read_text(encoding="utf-8"), self._foreign_content,
            "\u00a7S6/\u00a7S3: the foreign file must remain byte-identical",
        )
        manifest_paths = {
            e.get("path") for e in files_section if isinstance(e, dict)
        }
        self.assertNotIn(
            expected_rel, manifest_paths,
            f"\u00a7S6/\u00a7S3: the foreign file must NEVER be recorded in "
            f"the manifest ([[files]]); got manifest_paths={manifest_paths!r}",
        )


if __name__ == "__main__":
    unittest.main()
