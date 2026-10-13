"""The deployed hook and tool scripts carry the recorded interpreter (CR-MDB-064 §S3).

One rendering produces a script's deployed bytes: a hook or tool script whose first line is
``#!/usr/bin/env python3`` deploys with that line replaced by ``#!<recorded interpreter>`` (the
``[install] python`` the installer records, CR-MDB-064 §S2) and every other byte its source's;
any other script (``gate-lock.sh``, ``toon.py``, ``schedule_db.py``) deploys as its source bytes.
The manifest records the rendered bytes' hash, and the unchanged / hand-modified / unmanaged
decisions and the prune compare against it.

Every case here drives the REAL installer (``python -m modelb_axi``) in a sandbox — ``HOME``,
``PATH``, ``MODELB_HOME``, ``XDG_DATA_HOME``, ``PI_CODING_AGENT_DIR``, ``--modelb-home`` and
``--target-root`` — on the shared installer fixture (``tests/_helpers.py``): a ``python3`` stub
at the 3.14 floor and a ``uv`` stub. The expected deployed bytes are computed here, from the
packaged source and the interpreter ``install.toml`` records, never read back from what the
installer produced.

Stdlib only.
"""

import hashlib
import json
import os
import stat
import subprocess
import sys
import tomllib
import unittest
from pathlib import Path

from tests._helpers import (
    HOOKS_STORE,
    TOOLS_STORE,
    deployed_scripts,
    python3_stub,
    python_shebang_scripts,
)
from tests._helpers import decode_axi as _decode
from tests._helpers import render_script as render
from tests._helpers import write_executable as _write_exe
from tests.test_deployed_asset_freshness import _InstalledMachineCase

REPO_ROOT = Path(__file__).resolve().parent.parent
TOOLS_SRC = REPO_ROOT / "scripts"

#: The scripts §S3 names as rendering to their source bytes.
VERBATIM_SCRIPTS = (f"{TOOLS_STORE}/gate-lock.sh", f"{TOOLS_STORE}/toon.py",
                    f"{TOOLS_STORE}/schedule_db.py")

#: A hook that answers a payload on its own (no Crucible, no git): the direct-run probe.
CARGO_HOOK = f"{HOOKS_STORE}/block-direct-cargo-test"
#: A tool script carrying the python shebang.
WORKTREE_FLOW = f"{TOOLS_STORE}/worktree-flow.py"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class ScriptSetPreconditionTest(unittest.TestCase):
    """The script sets the cases below iterate are what §S3 names, so a green run covers them."""

    def test_python_shebang_set_holds_the_hooks_and_python_tools_and_not_the_three_verbatim(self):
        rendered = python_shebang_scripts()
        self.assertIn(CARGO_HOOK, rendered)
        self.assertIn(WORKTREE_FLOW, rendered)
        self.assertEqual(
            sorted(set(deployed_scripts()) - set(rendered)), sorted(VERBATIM_SCRIPTS),
            "§S3: exactly gate-lock.sh, toon.py and schedule_db.py render to their source bytes",
        )


class _RenderingCase(_InstalledMachineCase):
    """A real sandboxed install (``--harnesses pi --stacks bun``) whose recorded interpreter is
    the fixture's ``<bin>/python3``, plus re-runs of the installer against it."""

    def recorded_python(self) -> str:
        python = self.load_install()["install"].get("python")
        self.assertEqual(python, str(self.bin_dir / "python3"),
                         "fixture: the install records the fixture's python3 (§S2)")
        return python

    def run_installer(self, *extra, path=None, modelb_home=None, target_root=None):
        """The installer with ``--reinstall`` (or a first install into another home), ``PATH``
        overridable; returns ``(result, axi)``."""
        modelb_home = modelb_home or self.modelb_home
        target_root = target_root or self.target_root
        argv = [sys.executable, "-m", "modelb_axi", "--yes", "--harnesses", "pi",
                "--modelb-home", str(modelb_home), "--target-root", str(target_root),
                "--stacks", "bun", *extra]
        env = self._env({"PATH": path} if path else None)
        env["MODELB_HOME"] = str(modelb_home)
        result = subprocess.run(argv, capture_output=True, text=True, timeout=120,
                                stdin=subprocess.DEVNULL, env=env, cwd=str(self.cwd))
        return result, _decode(result.stdout)

    def assert_installed(self, result, axi):
        self.assertEqual(result.returncode, 0,
                         f"exit={result.returncode} axi={axi!r} stderr={result.stderr!r}")
        self.assertEqual(axi.get("outcome"), "installed", f"axi={axi!r}")

    def manifest_hashes(self, home=None) -> dict[str, str]:
        install_toml = Path(home or self.modelb_home) / "install.toml"
        with open(install_toml, "rb") as fh:
            data = tomllib.load(fh)
        return {entry["path"]: entry["sha256"] for entry in data.get("files", [])}

    def second_interpreter(self) -> Path:
        """Another ``python3`` at the floor, in a directory placed first on ``PATH``."""
        other_bin = self._root / "other-bin"
        other_bin.mkdir()
        return _write_exe(other_bin, "python3", python3_stub())

    def make_pre_cr_install(self) -> None:
        """An install made before CR-MDB-064: every script deployed as its source bytes, the
        manifest recording the source's hash, no ``[install] python``."""
        data = self.load_install()
        data["install"].pop("python", None)
        for entry in data["files"]:
            source = deployed_scripts().get(entry["path"])
            if source is not None:
                (self.target_root / entry["path"]).write_bytes(source.read_bytes())
                entry["sha256"] = _sha256(source.read_bytes())
        self.write_install(data)

    def assert_rendered_with(self, interpreter: str, *, except_paths=()) -> None:
        """Every deployed script holds the bytes §S3 renders with ``interpreter``, and the
        manifest records their hash."""
        recorded = self.manifest_hashes()
        for rel, source in deployed_scripts().items():
            if rel in except_paths:
                continue
            expected = render(source.read_bytes(), interpreter)
            with self.subTest(script=rel):
                deployed = (self.target_root / rel).read_bytes()
                self.assertEqual(deployed.partition(b"\n")[0], expected.partition(b"\n")[0],
                                 f"§S3: {rel}'s first line")
                self.assertEqual(deployed, expected,
                                 f"§S3: {rel} is the source with only its shebang rendered")
                self.assertEqual(recorded.get(rel), _sha256(expected),
                                 f"§S3: the manifest records {rel}'s rendered hash")


class DeployedScriptRenderingTest(_RenderingCase):
    """A fresh install renders the python-shebang scripts and records their rendered hash."""

    def test_python_shebang_scripts_start_with_the_recorded_interpreter_and_are_otherwise_the_source(self):
        python = self.recorded_python()
        for rel, source in python_shebang_scripts().items():
            with self.subTest(script=rel):
                deployed = (self.target_root / rel).read_bytes()
                self.assertEqual(deployed.partition(b"\n")[0], b"#!" + python.encode(),
                                 f"§S3: {rel} starts #!<recorded interpreter>")
                self.assertEqual(deployed.partition(b"\n")[2],
                                 source.read_bytes().partition(b"\n")[2],
                                 f"§S3: every byte after {rel}'s first line is the source's")

    def test_gate_lock_toon_and_schedule_db_deploy_byte_identical(self):
        for rel in VERBATIM_SCRIPTS:
            with self.subTest(script=rel):
                self.assertEqual((self.target_root / rel).read_bytes(),
                                 deployed_scripts()[rel].read_bytes(),
                                 f"§S3: {rel} renders to its source bytes")

    def test_each_deployed_script_keeps_its_source_mode(self):
        for rel, source in deployed_scripts().items():
            with self.subTest(script=rel):
                self.assertEqual(
                    oct(stat.S_IMODE((self.target_root / rel).stat().st_mode)),
                    oct(stat.S_IMODE(source.stat().st_mode)),
                    f"§S3: {rel} keeps its source's mode",
                )

    def test_manifest_records_the_hash_of_the_rendered_bytes(self):
        python = self.recorded_python()
        recorded = self.manifest_hashes()
        for rel, source in deployed_scripts().items():
            with self.subTest(script=rel):
                self.assertEqual(recorded.get(rel), _sha256(render(source.read_bytes(), python)),
                                 f"§S3: the manifest records {rel}'s rendered hash")

    def test_deployed_hook_runs_directly_on_the_recorded_interpreter_with_no_python3_on_path(self):
        python = self.recorded_python()
        log = self._root / "python3.log"
        # The recorded path now logs every run: the same interpreter, now observable.
        _write_exe(self.bin_dir, "python3", python3_stub(log=log))
        empty_bin = self._root / "empty-bin"
        empty_bin.mkdir()
        project = self._root / "rust-project"
        project.mkdir()
        (project / "Cargo.toml").write_text("[package]\nname = \"p\"\n", encoding="utf-8")
        hook = self.target_root / CARGO_HOOK
        payload = {"tool_name": "bash", "tool_input": {"command": "cargo test"},
                   "cwd": str(project)}
        result = subprocess.run(
            [str(hook)], input=json.dumps(payload), capture_output=True, text=True, timeout=60,
            env={"PATH": str(empty_bin), "HOME": str(self.home)}, cwd=str(project),
        )
        self.assertEqual(result.returncode, 2,
                         f"§S3/§S4: the deployed hook runs directly and blocks `cargo test`; "
                         f"exit={result.returncode} stdout={result.stdout!r} "
                         f"stderr={result.stderr!r}")
        self.assertEqual(json.loads(result.stdout).get("decision"), "block",
                         f"stdout={result.stdout!r}")
        self.assertEqual(log.read_text(encoding="utf-8").splitlines(), [f"python3 {hook}"],
                         f"§S3: exactly one run, on the recorded interpreter {python}")


class RenderedManifestDecisionsTest(_RenderingCase):
    """The unchanged / hand-modified / unmanaged decisions and the prune, against the rendered
    hashes, across re-runs of the installer."""

    def test_first_run_after_this_cr_re_renders_scripts_deployed_unrendered(self):
        self.make_pre_cr_install()
        result, axi = self.run_installer("--reinstall")
        self.assert_installed(result, axi)
        self.assertEqual(axi.get("skipped"), [], f"managed and unchanged; axi={axi!r}")
        self.assertEqual(axi.get("unmanaged"), [], f"axi={axi!r}")
        self.assert_rendered_with(self.recorded_python())

    def test_re_run_with_the_same_interpreter_writes_no_script(self):
        python = self.recorded_python()
        self.assert_rendered_with(python)
        before = {rel: ((self.target_root / rel).stat().st_ino,
                        (self.target_root / rel).stat().st_mtime_ns,
                        (self.target_root / rel).read_bytes())
                  for rel in deployed_scripts()}
        result, axi = self.run_installer("--reinstall")
        self.assert_installed(result, axi)
        self.assertEqual(axi.get("skipped"), [], f"axi={axi!r}")
        rewritten = [rel for rel, (ino, mtime, data) in before.items()
                     if ((self.target_root / rel).stat().st_ino,
                         (self.target_root / rel).stat().st_mtime_ns,
                         (self.target_root / rel).read_bytes()) != (ino, mtime, data)]
        self.assertEqual(rewritten, [], "§S3: a re-run with the same interpreter writes nothing")
        self.assert_rendered_with(python)

    def test_re_run_with_a_different_interpreter_re_renders_every_managed_script(self):
        self.recorded_python()
        other = self.second_interpreter()
        result, axi = self.run_installer(
            "--reinstall", path=f"{other.parent}{os.pathsep}{self.bin_dir}")
        self.assert_installed(result, axi)
        self.assertEqual(self.load_install()["install"].get("python"), str(other),
                         "fixture: the re-run records the python3 first on PATH (§S2)")
        self.assertEqual(axi.get("skipped"), [],
                         f"§S3: an unedited script is not hand-modified; axi={axi!r}")
        self.assert_rendered_with(str(other))

    def test_hand_edited_script_is_skipped_and_the_rest_re_rendered_on_a_different_interpreter(self):
        self.recorded_python()
        edited = self.target_root / WORKTREE_FLOW
        edited.write_bytes(edited.read_bytes() + b"\n# my local change\n")
        edited_bytes = edited.read_bytes()
        other = self.second_interpreter()
        path = f"{other.parent}{os.pathsep}{self.bin_dir}"
        result, axi = self.run_installer("--reinstall", path=path)
        self.assert_installed(result, axi)
        self.assertEqual(axi.get("skipped"), [WORKTREE_FLOW],
                         f"§S3: exactly the hand-edited script is skipped; axi={axi!r}")
        self.assertEqual(edited.read_bytes(), edited_bytes,
                         "§S3: a hand-edited script is never overwritten without --force-managed")
        self.assert_rendered_with(str(other), except_paths=(WORKTREE_FLOW,))

        forced, forced_axi = self.run_installer("--reinstall", "--force-managed", path=path)
        self.assert_installed(forced, forced_axi)
        self.assertEqual(forced_axi.get("skipped"), [], f"axi={forced_axi!r}")
        self.assert_rendered_with(str(other))

    def test_prune_removes_a_rendered_script_no_longer_shipped(self):
        python = self.recorded_python()
        retired = f"{TOOLS_STORE}/retired-tool.py"
        self.assertNotIn(retired, deployed_scripts(), "fixture: no longer shipped")
        rendered = render((TOOLS_SRC / "worktree-flow.py").read_bytes(), python)
        (self.target_root / retired).write_bytes(rendered)
        data = self.load_install()
        data["files"].append({"path": retired, "sha256": _sha256(rendered)})
        self.write_install(data)
        result, axi = self.run_installer("--reinstall")
        self.assert_installed(result, axi)
        self.assertEqual(axi.get("removed"), [retired], f"§S3: the prune; axi={axi!r}")
        self.assertFalse((self.target_root / retired).exists())
        self.assertNotIn(retired, self.manifest_hashes())


class AdoptionWithoutInstallTomlTest(_RenderingCase):
    """With no ``install.toml``, a script already at a deployed path is adopted only when it
    equals the bytes rendered with the current interpreter; otherwise it is ``unmanaged``."""

    def setUp(self):
        super().setUp()
        self.fresh_home = self._root / "fresh-home"
        self.fresh_target = self._root / "fresh-target"
        self.fresh_home.mkdir()
        self.interpreter = self.recorded_python()

    def plant(self, rel: str, data: bytes) -> Path:
        path = self.fresh_target / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def first_install(self):
        result, axi = self.run_installer(modelb_home=self.fresh_home,
                                         target_root=self.fresh_target)
        self.assert_installed(result, axi)
        return axi

    def test_script_equal_to_the_bytes_rendered_with_the_current_interpreter_is_adopted(self):
        rendered = render(python_shebang_scripts()[CARGO_HOOK].read_bytes(), self.interpreter)
        self.plant(CARGO_HOOK, rendered)
        axi = self.first_install()
        self.assertEqual(axi.get("unmanaged"), [], f"§S3: adopted, not unmanaged; axi={axi!r}")
        self.assertEqual(self.manifest_hashes(self.fresh_home).get(CARGO_HOOK), _sha256(rendered))
        self.assertEqual((self.fresh_target / CARGO_HOOK).read_bytes(), rendered)

    def test_script_equal_to_its_unrendered_source_is_reported_unmanaged(self):
        source = python_shebang_scripts()[WORKTREE_FLOW].read_bytes()
        planted = self.plant(WORKTREE_FLOW, source)
        axi = self.first_install()
        self.assertEqual(axi.get("unmanaged"), [WORKTREE_FLOW],
                         f"§S3: not the rendered bytes, so not Model B's; axi={axi!r}")
        self.assertEqual(planted.read_bytes(), source, "an unmanaged file is left untouched")
        self.assertNotIn(WORKTREE_FLOW, self.manifest_hashes(self.fresh_home),
                         "an unmanaged file is recorded in no manifest entry")


if __name__ == "__main__":
    unittest.main()
