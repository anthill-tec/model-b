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

import contextlib
import io
import os
import shutil
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path

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


if __name__ == "__main__":
    unittest.main()
