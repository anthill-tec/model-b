"""A redeploy removes what it no longer deploys (CR-MDB-040 §S1/§S2).

After a successful deploy and before ``install.toml`` is written, the
installer prunes every path the PRIOR manifest records and the NEW manifest
does not (``deploy.prune_assets(prior_root, prior_files, new_paths)``):

- unchanged (deployed hash = recorded hash) — removed, then every directory
  left empty is removed, walking up and stopping at the store root
  (``.agents/skills``, ``.agents/hooks/scripts``, ``.agents/scripts``); a
  store root is never removed;
- hand-modified — kept and reported, ``--force-managed`` or not; the new
  manifest keeps its entry with the recorded hash, so later runs report it
  again until it is restored (then removed) or deleted;
- already gone — nothing to do, not reported;
- outside the three store directories (after normalising ``..``, or
  absolute) — a corrupt entry, never touched, dropped from the new manifest,
  in neither list, warned about once by path.

``prior_root`` is the prior manifest's ``target_root``, else this run's
target root; a different recorded root prunes nothing and warns, naming it.
A pruning ``OSError`` is a ``DeployError`` (outcome ``deploy_failed``, no
``install.toml`` written); a
run failing earlier removes nothing. The ``installed`` envelope always
carries ``removed`` and ``kept`` lists; stderr prints one line per removed
path and one warning per kept path. The ``already_installed`` report's
``retired`` hint and the install guide say ``--reinstall`` removes them.

Shape assumed for the unit seam (the spec names the signature only):
``prior_files`` is the manifest's ``[[files]]`` list of ``{path, sha256}``
dicts, ``new_paths`` a set of target-root-relative strings, and the result
is ``(removed, kept)`` — also accepted as a mapping with those two keys.

Isolation (NON-NEGOTIABLE): every run pins ``HOME`` (a sandbox without a
Crucible manifest), ``PATH`` (a fake-bin dir), ``MODELB_HOME`` (flag and
env), ``XDG_DATA_HOME`` and ``PI_CODING_AGENT_DIR`` (a provisioned sandbox
agent dir), and deploys only under a temp target root.

Stdlib only.
"""

import hashlib
import os
import re
import shlex
import shutil
import site
import stat
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path

from modelb_axi.config import serialize_install_toml
from modelb_axi.deploy import DeployError
from tests._helpers import decode_axi as _decode
from tests._helpers import write_executable as _write_exe
from tests.pi_capability_sandbox import (
    AGENT_DIR_ENV,
    make_home,
    make_provisioned_agent_dir,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS_SRC = REPO_ROOT / "skills-src"
INSTALL_GUIDE = REPO_ROOT / "docs" / "install-guide.md"
PI_README = REPO_ROOT / "pi-package" / "README.md"

#: The bundles a ``rust`` selection adds over ``python`` (CR-MDB-036 §S7,
#: CR-MDB-023 §S4).
RUST_ONLY_BUNDLES = ("crucible-report-rust", "code-health")
RUST_REPORT_SKILL = ".agents/skills/crucible-report-rust/SKILL.md"
CODE_HEALTH_SKILL = ".agents/skills/code-health/SKILL.md"
#: A bundle retired by CR-MDB-031, still recorded by pre-1.0 manifests.
RETIRED_SKILL = ".agents/skills/chezmoi/SKILL.md"
RETIRED_REFERENCE = ".agents/skills/chezmoi/references/cheatsheet.md"
RETIRED_HOOK = ".agents/hooks/scripts/retired-hook"
RETIRED_TOOL = ".agents/scripts/retired-tool.py"
#: The three store roots (§S1).
STORE_ROOTS = (".agents/skills", ".agents/hooks/scripts", ".agents/scripts")

_FAKE_UV = (
    "#!/bin/sh\n"
    'if [ "$1" = "tool" ] && [ "$2" = "install" ]; then exit 0; fi\n'
    'echo "uv 0.0.0-fake"\n'
    "exit 0\n"
)
_FAKE_TOOL = "#!/bin/sh\necho fake\nexit 0\n"


class _PruneSandboxCase(unittest.TestCase):
    """Per-test sandbox plus helpers to install, rewrite the manifest and
    re-run the installer against it."""

    def setUp(self):
        self._root = Path(tempfile.mkdtemp(prefix="modelb-cr040-prune-"))
        self.modelb_home = self._root / "modelb-home"
        self.target_root = self._root / "target"
        self.bin_dir = self._root / "bin"
        self.home = self._root / "home"
        self.agent_dir = self._root / "agent"
        self.xdg_data_home = self._root / "xdg-data"
        self.cwd = self._root / "cwd"
        for d in (self.modelb_home, self.target_root, self.bin_dir,
                  self.xdg_data_home, self.cwd):
            d.mkdir(parents=True)
        make_home(self.home, crucible_manifest=False)
        make_provisioned_agent_dir(self.agent_dir)
        _write_exe(self.bin_dir, "uv", _FAKE_UV)
        for name in ("sandesh", "pi"):
            _write_exe(self.bin_dir, name, _FAKE_TOOL)
        self.addCleanup(shutil.rmtree, self._root, True)

    # -- runners ----------------------------------------------------------

    def env(self, agent_dir: Path | None = None) -> dict:
        env = dict(os.environ)
        env.pop("MODELB_TARGET_ROOT", None)
        # User site-packages stay reachable once HOME is a sandbox.
        env.setdefault("PYTHONUSERBASE", site.getuserbase())
        existing_pp = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = str(REPO_ROOT) + (os.pathsep + existing_pp if existing_pp else "")
        env.update({
            "HOME": str(self.home),
            "PATH": str(self.bin_dir),
            "MODELB_HOME": str(self.modelb_home),
            "XDG_DATA_HOME": str(self.xdg_data_home),
            AGENT_DIR_ENV: str(agent_dir or self.agent_dir),
        })
        return env

    def run_argv(self, argv: list[str], agent_dir: Path | None = None):
        result = subprocess.run(
            [sys.executable, "-m", "modelb_axi", *argv],
            capture_output=True, text=True, timeout=120, stdin=subprocess.DEVNULL,
            env=self.env(agent_dir), cwd=str(self.cwd),
        )
        return result, _decode(result.stdout)

    def run_installer(self, *extra, target_root: Path | None = None,
                      harnesses: str = "pi", agent_dir: Path | None = None):
        """A ``--yes`` installer run into ``target_root`` (default: the sandbox's)."""
        return self.run_argv(
            ["--yes", "--harnesses", harnesses, "--modelb-home", str(self.modelb_home),
             "--target-root", str(target_root or self.target_root), *extra],
            agent_dir=agent_dir,
        )

    def install(self, *extra, target_root: Path | None = None):
        """A fixture install that must succeed."""
        result, axi = self.run_installer(*extra, target_root=target_root)
        if result.returncode != 0 or axi.get("outcome") != "installed":
            self.fail(f"fixture precondition: the sandboxed install must succeed; "
                      f"exit={result.returncode} axi={axi!r} stderr={result.stderr!r}")
        return result, axi

    def reinstall(self, *extra, target_root: Path | None = None):
        return self.run_installer("--reinstall", *extra, target_root=target_root)

    # -- manifest ----------------------------------------------------------

    @property
    def install_toml_path(self) -> Path:
        return self.modelb_home / "install.toml"

    def load_install(self) -> dict:
        with open(self.install_toml_path, "rb") as fh:
            return tomllib.load(fh)

    def write_install(self, data: dict) -> None:
        self.install_toml_path.write_text(
            serialize_install_toml(data["install"], data["deps"], data.get("files", []),
                                   data.get("capabilities")),
            encoding="utf-8",
        )

    def manifest_paths(self) -> set[str]:
        return {entry["path"] for entry in self.load_install().get("files", [])}

    def manifest_hashes(self, rel: str) -> list[str]:
        """Every hash the current manifest records for ``rel`` (one entry expected)."""
        return [entry["sha256"] for entry in self.load_install().get("files", [])
                if entry["path"] == rel]

    def sha(self, path: Path) -> str:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()

    def record_deployed(self, rel: str, content: bytes, *, deployed_at: Path | None = None,
                        write: bool = True) -> Path:
        """Write ``content`` at ``<root>/rel`` and add a manifest entry whose
        hash matches it (a file Model B deployed and nobody edited)."""
        path = (deployed_at or self.target_root) / rel
        if write:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        data = self.load_install()
        data.setdefault("files", []).append(
            {"path": rel, "sha256": hashlib.sha256(content).hexdigest()})
        self.write_install(data)
        return path

    def drop_install_keys(self, *keys: str) -> None:
        data = self.load_install()
        for key in keys:
            data["install"].pop(key, None)
        self.write_install(data)

    # -- trees -------------------------------------------------------------

    def snapshot(self, root: Path) -> dict:
        return {str(p.relative_to(root)): p.read_bytes()
                for p in sorted(Path(root).rglob("*")) if p.is_file()}

    def rust_only_files(self) -> set[str]:
        """Every file the rust-only bundles deploy, target-root-relative;
        each bundle's ``SKILL.md`` is named so none can vanish."""
        files = {f".agents/skills/{p.relative_to(SKILLS_SRC)}"
                 for bundle in RUST_ONLY_BUNDLES
                 for p in (SKILLS_SRC / bundle).rglob("*") if p.is_file()}
        return files | {RUST_REPORT_SKILL, CODE_HEALTH_SKILL}

    # -- assertions ----------------------------------------------------------

    def assert_installed(self, result, axi):
        self.assertEqual(result.returncode, 0,
                         f"exit={result.returncode} axi={axi!r} stderr={result.stderr!r}")
        self.assertEqual(axi.get("outcome"), "installed", f"axi={axi!r}")

    def assert_envelope_lists(self, axi, *, removed=(), kept=()):
        for key, expected in (("removed", removed), ("kept", kept)):
            with self.subTest(list=key):
                value = axi.get(key)
                self.assertIsInstance(
                    value, list,
                    f"§S2: the installed envelope always carries `{key}` as a list; axi={axi!r}")
                self.assertEqual(sorted(value), sorted(expected),
                                 f"§S2: envelope `{key}` must be exactly {sorted(expected)!r}")
                self.assertEqual(len(value), len(set(value)), f"`{key}` lists a path twice")

    def stderr_lines_naming(self, stderr: str, rel: str) -> list[str]:
        return [ln for ln in stderr.splitlines() if rel in ln]

    def warnings_naming(self, axi, needle: str) -> list[str]:
        return [w for w in axi.get("warnings", []) if needle in w]


# ---------------------------------------------------------------------------
# §S1 AC1 — a narrowed --stacks prunes what is no longer deployed
# ---------------------------------------------------------------------------

class NarrowedStacksReinstallPruneTest(_PruneSandboxCase):
    """Installing ``--stacks python,rust``, then ``--reinstall --stacks
    python``, removes every ``crucible-report-rust`` and ``code-health``
    file and their directories; the new manifest records neither; the
    envelope's ``removed`` lists them."""

    def setUp(self):
        super().setUp()
        self.install("--stacks", "python,rust")
        missing = sorted(rel for rel in self.rust_only_files()
                         if not (self.target_root / rel).is_file())
        self.assertEqual(missing, [], "fixture: the rust-only bundles must be deployed")
        self.assertTrue(self.rust_only_files() <= self.manifest_paths(),
                        "fixture: the first manifest must record the rust-only files")

    def test_narrowed_reinstall_removes_every_rust_only_file_and_its_directory(self):
        result, axi = self.reinstall("--stacks", "python")
        self.assert_installed(result, axi)
        left = sorted(rel for rel in self.rust_only_files() if (self.target_root / rel).exists())
        self.assertEqual(left, [], "§S1: an unchanged file no longer deployed is removed")
        for bundle in RUST_ONLY_BUNDLES:
            with self.subTest(bundle=bundle):
                self.assertFalse((self.target_root / ".agents" / "skills" / bundle).exists(),
                                 f"§S1: the emptied {bundle}/ directory is removed")

    def test_narrowed_reinstall_manifest_records_neither_bundle(self):
        result, axi = self.reinstall("--stacks", "python")
        self.assert_installed(result, axi)
        recorded = sorted(p for p in self.manifest_paths()
                          if any(f"/{b}/" in p for b in RUST_ONLY_BUNDLES))
        self.assertEqual(recorded, [])
        # Precondition for the envelope check below to mean anything.
        self.assert_envelope_lists(axi, removed=self.rust_only_files())

    def test_narrowed_reinstall_envelope_lists_exactly_the_removed_relative_paths(self):
        result, axi = self.reinstall("--stacks", "python")
        self.assert_installed(result, axi)
        self.assert_envelope_lists(axi, removed=self.rust_only_files(), kept=())
        absolute = [p for p in axi.get("removed") or [] if Path(p).is_absolute()]
        self.assertEqual(absolute, [], "§S2: `removed` paths are target-root-relative")

    def test_narrowed_reinstall_prints_one_stderr_line_per_removed_path(self):
        result, axi = self.reinstall("--stacks", "python")
        self.assert_installed(result, axi)
        for rel in sorted(self.rust_only_files()):
            with self.subTest(rel=rel):
                self.assertEqual(
                    len(self.stderr_lines_naming(result.stderr, rel)), 1,
                    f"§S2: exactly one human line names removed {rel}; "
                    f"stderr={result.stderr!r}")

    def test_narrowed_reinstall_leaves_everything_still_deployed_in_place(self):
        """Regression pin: pruning removes only leftovers — every path the
        new manifest records is on disk (fails if the prune over-reaches)."""
        result, axi = self.reinstall("--stacks", "python")
        self.assert_installed(result, axi)
        missing = sorted(p for p in self.manifest_paths()
                         if not (self.target_root / p).is_file())
        self.assertEqual(missing, [], "§S1: a still-deployed file is never pruned")
        self.assertTrue((self.target_root / ".agents/skills/crucible-report-python/SKILL.md")
                        .is_file())
        self.assert_envelope_lists(axi, removed=self.rust_only_files())


# ---------------------------------------------------------------------------
# §S1 AC2 — a retired bundle is removed on --reinstall
# ---------------------------------------------------------------------------

class RetiredBundlePruneTest(_PruneSandboxCase):
    """A prior manifest recording ``.agents/skills/chezmoi/SKILL.md`` with
    its deployed file (hash matching) loses it on ``--reinstall``."""

    def setUp(self):
        super().setUp()
        self.install("--stacks", "python")
        self.retired = self.record_deployed(RETIRED_SKILL, b"---\nname: chezmoi\n---\n")

    def test_reinstall_removes_the_retired_bundle_file_and_directory(self):
        result, axi = self.reinstall("--stacks", "python")
        self.assert_installed(result, axi)
        self.assertFalse(self.retired.exists(), "§S1: the unchanged retired file is removed")
        self.assertFalse(self.retired.parent.exists(), "§S1: its emptied bundle dir is removed")
        self.assertNotIn(RETIRED_SKILL, self.manifest_paths())
        self.assert_envelope_lists(axi, removed=[RETIRED_SKILL], kept=())

    def test_reinstall_names_the_removed_retired_file_on_stderr_once(self):
        result, axi = self.reinstall("--stacks", "python")
        self.assert_installed(result, axi)
        self.assertEqual(len(self.stderr_lines_naming(result.stderr, RETIRED_SKILL)), 1,
                         f"stderr={result.stderr!r}")
        self.assert_envelope_lists(axi, removed=[RETIRED_SKILL])


# ---------------------------------------------------------------------------
# §S1 AC3/AC4 — the prior root
# ---------------------------------------------------------------------------

class PriorManifestWithoutTargetRootPruneTest(_PruneSandboxCase):
    """A manifest written before CR-MDB-033 records no ``target_root``: the
    prune runs against this run's ``--target-root``."""

    def setUp(self):
        super().setUp()
        self.install("--stacks", "python,rust")
        self.retired = self.record_deployed(RETIRED_SKILL, b"retired\n")
        self.drop_install_keys("target_root", "skills_dir", "hooks_scripts_dir",
                               "tool_scripts_dir")
        self.assertNotIn("target_root", self.load_install()["install"], "fixture")

    def test_reinstall_prunes_against_this_runs_target_root(self):
        result, axi = self.reinstall("--stacks", "python")
        self.assert_installed(result, axi)
        expected = self.rust_only_files() | {RETIRED_SKILL}
        self.assert_envelope_lists(axi, removed=expected, kept=())
        left = sorted(rel for rel in expected if (self.target_root / rel).exists())
        self.assertEqual(left, [])
        self.assertEqual(self.load_install()["install"].get("target_root"),
                         str(self.target_root))


class PriorManifestAtAnotherTargetRootPruneTest(_PruneSandboxCase):
    """A recorded ``target_root`` different from this run's prunes nothing;
    a warning names the prior root and says its files were left in place."""

    def setUp(self):
        super().setUp()
        self.install("--stacks", "python,rust")
        self.record_deployed(RETIRED_SKILL, b"retired\n")
        self.other_root = self._root / "elsewhere"
        self.before = self.snapshot(self.target_root)

    def test_reinstall_elsewhere_prunes_nothing_under_the_prior_root(self):
        result, axi = self.reinstall("--stacks", "python", target_root=self.other_root)
        self.assert_installed(result, axi)
        self.assertEqual(self.snapshot(self.target_root), self.before,
                         "§S1: nothing under the prior root is removed")
        self.assert_envelope_lists(axi, removed=(), kept=())

    def test_reinstall_elsewhere_warns_naming_the_prior_root(self):
        result, axi = self.reinstall("--stacks", "python", target_root=self.other_root)
        self.assert_installed(result, axi)
        hits = self.warnings_naming(axi, str(self.target_root))
        self.assertEqual(len(hits), 1,
                         f"§S1: one warning names the prior root {self.target_root}; "
                         f"warnings={axi.get('warnings')!r}")
        self.assertRegex(hits[0], r"(?i)\bleft\b",
                         "§S1: the warning says the prior root's files were left in place")
        self.assertTrue(any(str(self.target_root) in ln and "warning" in ln
                            for ln in result.stderr.splitlines()),
                        f"the warning is printed on stderr too; stderr={result.stderr!r}")


# ---------------------------------------------------------------------------
# §S1 AC5 — a hand-modified leftover is kept
# ---------------------------------------------------------------------------

class HandModifiedLeftoverKeptTest(_PruneSandboxCase):
    """A hand-edited leftover is kept, with or without ``--force-managed``;
    it is listed in ``kept`` and warned about by path. The new manifest
    keeps its entry with the RECORDED hash, so the next ``--reinstall``
    reports it again, and restoring (or deleting) it lets it be pruned."""

    def setUp(self):
        super().setUp()
        self.install("--stacks", "python,rust")
        self.edited = self.target_root / RUST_REPORT_SKILL
        self.original_bytes = self.edited.read_bytes()
        self.recorded = self.manifest_hashes(RUST_REPORT_SKILL)
        self.assertEqual(self.recorded, [hashlib.sha256(self.original_bytes).hexdigest()],
                         "fixture: the first manifest records the deployed hash once")
        self.edited.write_bytes(self.original_bytes + b"\n# my local notes\n")
        self.edited_bytes = self.edited.read_bytes()

    def _assert_kept(self, *flags):
        result, axi = self.reinstall("--stacks", "python", *flags)
        self.assert_installed(result, axi)
        self.assertEqual(self.edited.read_bytes(), self.edited_bytes,
                         "§S1: a hand-edited leftover is never deleted or rewritten")
        self.assert_envelope_lists(axi, removed=self.rust_only_files() - {RUST_REPORT_SKILL},
                                   kept=[RUST_REPORT_SKILL])
        self.assertEqual(self.manifest_hashes(RUST_REPORT_SKILL), self.recorded,
                         "§S1: the new manifest keeps the kept leftover's entry with its "
                         "RECORDED hash (not the edited one)")
        hits = self.warnings_naming(axi, RUST_REPORT_SKILL)
        self.assertEqual(len(hits), 1, f"§S2: one warning names the kept path; "
                                       f"warnings={axi.get('warnings')!r}")
        self.assertIn("edit", hits[0].lower(),
                      "§S2: the warning says it was left because it was edited")
        stderr_hits = [ln for ln in self.stderr_lines_naming(result.stderr, RUST_REPORT_SKILL)
                       if "warning" in ln]
        self.assertEqual(len(stderr_hits), 1, f"stderr={result.stderr!r}")
        self.assertFalse((self.target_root / CODE_HEALTH_SKILL).exists(),
                         "the unchanged leftover beside it is still removed")

    def test_hand_modified_leftover_is_kept_and_reported(self):
        self._assert_kept()

    def test_hand_modified_leftover_is_kept_even_with_force_managed(self):
        self._assert_kept("--force-managed")

    def test_next_reinstall_reports_the_kept_leftover_again(self):
        self._assert_kept()
        result, axi = self.reinstall("--stacks", "python")
        self.assert_installed(result, axi)
        self.assert_envelope_lists(axi, removed=(), kept=[RUST_REPORT_SKILL])
        self.assertEqual(self.edited.read_bytes(), self.edited_bytes)
        self.assertEqual(self.manifest_hashes(RUST_REPORT_SKILL), self.recorded,
                         "§S1: still recorded, still with the recorded hash")

    def test_restored_leftover_is_removed_by_the_next_reinstall(self):
        self._assert_kept()
        self.edited.write_bytes(self.original_bytes)
        result, axi = self.reinstall("--stacks", "python")
        self.assert_installed(result, axi)
        self.assert_envelope_lists(axi, removed=[RUST_REPORT_SKILL], kept=())
        self.assertFalse(self.edited.exists(), "§S1: a restored leftover is pruned")
        self.assertFalse(self.edited.parent.exists(), "its emptied bundle dir too")
        self.assertEqual(self.manifest_hashes(RUST_REPORT_SKILL), [],
                         "§S1: once pruned, the manifest stops recording it")

    def test_deleted_leftover_drops_out_of_the_manifest_unreported(self):
        self._assert_kept()
        self.edited.unlink()
        result, axi = self.reinstall("--stacks", "python")
        self.assert_installed(result, axi)
        self.assert_envelope_lists(axi, removed=(), kept=())
        self.assertEqual(self.manifest_hashes(RUST_REPORT_SKILL), [],
                         "§S1: a deleted leftover is no longer recorded")


# ---------------------------------------------------------------------------
# §S1 AC6 — unmanaged files and corrupt entries are never removed
# ---------------------------------------------------------------------------

class UnmanagedAndCorruptEntriesNeverRemovedTest(_PruneSandboxCase):
    """Files never in the manifest, and files a corrupt prior entry names
    outside the three store directories, survive a prune that otherwise
    runs (a retired entry beside them is removed)."""

    def setUp(self):
        super().setUp()
        self.install("--stacks", "python,rust")
        self.record_deployed(RETIRED_SKILL, b"retired\n")

    def test_unmanaged_files_survive_even_inside_a_pruned_bundle_directory(self):
        own_skill = self.target_root / ".agents/skills/my-own-skill/SKILL.md"
        notes = self.target_root / ".agents/skills/crucible-report-rust/my-notes.md"
        for path in (own_skill, notes):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("mine\n", encoding="utf-8")
        result, axi = self.reinstall("--stacks", "python")
        self.assert_installed(result, axi)
        self.assertEqual(own_skill.read_text(encoding="utf-8"), "mine\n")
        self.assertEqual(notes.read_text(encoding="utf-8"), "mine\n",
                         "§S1: an unmanaged file is never removed")
        self.assertTrue(notes.parent.is_dir(), "a non-empty bundle dir is not removed")
        self.assert_envelope_lists(axi, removed=self.rust_only_files() | {RETIRED_SKILL})

    def _assert_corrupt_entry_untouched(self, rel: str, where: Path, *, on_disk: bool = True):
        content = f"not model b's: {rel}\n".encode()
        if on_disk:
            where.parent.mkdir(parents=True, exist_ok=True)
            where.write_bytes(content)
        self.record_deployed(rel, content, write=False)
        result, axi = self.reinstall("--stacks", "python,rust")
        self.assert_installed(result, axi)
        self.assertEqual(where.read_bytes() if where.is_file() else None,
                         content if on_disk else None,
                         f"§S1: a corrupt entry {rel!r} outside the stores is never touched")
        self.assert_envelope_lists(axi, removed=[RETIRED_SKILL], kept=())
        self.assertEqual(self.manifest_hashes(rel), [],
                         f"§S1: the corrupt entry {rel!r} is dropped from the new manifest")
        hits = [w for w in axi.get("warnings", []) if rel in w or str(where) in w]
        self.assertEqual(len(hits), 1,
                         f"§S1: exactly one warning names the corrupt entry {rel!r}; "
                         f"warnings={axi.get('warnings')!r}")

    def test_corrupt_entry_whose_file_is_absent_is_still_dropped_and_warned(self):
        self._assert_corrupt_entry_untouched(".bashrc", self.target_root / ".bashrc",
                                             on_disk=False)

    def test_dotfile_at_the_target_root_is_never_removed(self):
        self._assert_corrupt_entry_untouched(".bashrc", self.target_root / ".bashrc")

    def test_parent_relative_entry_is_never_removed(self):
        self._assert_corrupt_entry_untouched("../outside.txt", self._root / "outside.txt")

    def test_entry_escaping_a_store_through_dotdot_is_never_removed(self):
        self._assert_corrupt_entry_untouched(".agents/skills/../../escape.txt",
                                             self.target_root / "escape.txt")

    def test_absolute_entry_is_never_removed(self):
        where = self._root / "absolute-target.txt"
        self._assert_corrupt_entry_untouched(str(where), where)

    def test_agents_path_outside_the_three_stores_is_never_removed(self):
        rel = ".agents/other/thing.txt"
        self._assert_corrupt_entry_untouched(rel, self.target_root / rel)

    def test_hooks_path_beside_the_hook_scripts_store_is_never_removed(self):
        rel = ".agents/hooks/not-a-script.txt"
        self._assert_corrupt_entry_untouched(rel, self.target_root / rel)


# ---------------------------------------------------------------------------
# §S1 AC7 — store roots are never removed; empty bundle directories are
# ---------------------------------------------------------------------------

class StoreRootsAndEmptyBundleDirsTest(_PruneSandboxCase):
    """Nested retired bundle directories are removed up to the store root;
    each store root survives."""

    def setUp(self):
        super().setUp()
        self.install("--stacks", "python")
        for rel in (RETIRED_SKILL, RETIRED_REFERENCE, RETIRED_HOOK, RETIRED_TOOL):
            self.record_deployed(rel, f"retired {rel}\n".encode())

    def test_nested_retired_bundle_directories_are_removed(self):
        result, axi = self.reinstall("--stacks", "python")
        self.assert_installed(result, axi)
        chezmoi = self.target_root / ".agents/skills/chezmoi"
        self.assertFalse((chezmoi / "references").exists(), "§S1: emptied subdir removed")
        self.assertFalse(chezmoi.exists(), "§S1: emptied bundle dir removed")
        self.assert_envelope_lists(
            axi, removed=[RETIRED_SKILL, RETIRED_REFERENCE, RETIRED_HOOK, RETIRED_TOOL])

    def test_store_roots_survive_the_prune(self):
        result, axi = self.reinstall("--stacks", "python")
        self.assert_installed(result, axi)
        for rel in (RETIRED_HOOK, RETIRED_TOOL):
            self.assertFalse((self.target_root / rel).exists(), f"§S1: {rel} removed")
        for store in STORE_ROOTS:
            with self.subTest(store=store):
                self.assertTrue((self.target_root / store).is_dir(),
                                f"§S1: the store root {store} is never removed")
        self.assert_envelope_lists(
            axi, removed=[RETIRED_SKILL, RETIRED_REFERENCE, RETIRED_HOOK, RETIRED_TOOL])


# ---------------------------------------------------------------------------
# §S1 AC8 — failed runs remove nothing; a pruning OSError writes no manifest
# ---------------------------------------------------------------------------

class FailedRunRemovesNothingTest(_PruneSandboxCase):
    """A run failing in pre-flight, validation or deploy removes nothing
    and leaves the prior manifest; the next successful run then prunes."""

    def setUp(self):
        super().setUp()
        self.install("--stacks", "python,rust")
        self.tree_before = self.snapshot(self.target_root)
        self.toml_before = self.install_toml_path.read_bytes()

    def _assert_failed_run_removed_nothing(self, result, axi):
        self.assertNotEqual(result.returncode, 0, f"fixture: the run must fail; axi={axi!r}")
        self.assertIs(axi.get("ok"), False, f"axi={axi!r}")
        self.assertEqual(self.snapshot(self.target_root), self.tree_before,
                         "§S1: a failed run removes nothing")
        self.assertEqual(self.install_toml_path.read_bytes(), self.toml_before,
                         "§S1: a failed run leaves the prior install.toml")

    def _assert_next_run_prunes(self):
        result, axi = self.reinstall("--stacks", "python")
        self.assert_installed(result, axi)
        self.assert_envelope_lists(axi, removed=self.rust_only_files(), kept=())

    def test_unknown_stack_removes_nothing_and_the_next_run_prunes(self):
        self._assert_failed_run_removed_nothing(*self.reinstall("--stacks", "cobol"))
        self._assert_next_run_prunes()

    def test_unknown_harness_removes_nothing_and_the_next_run_prunes(self):
        self._assert_failed_run_removed_nothing(
            *self.run_installer("--reinstall", "--stacks", "python", harnesses="bogus"))
        self._assert_next_run_prunes()

    def test_preflight_failure_removes_nothing_and_the_next_run_prunes(self):
        lacking = make_provisioned_agent_dir(self._root / "agent-lacking", omit=("dispatch",))
        result, axi = self.run_installer("--reinstall", "--stacks", "python", agent_dir=lacking)
        self.assertEqual(axi.get("outcome"), "preflight_failed", f"fixture: axi={axi!r}")
        self._assert_failed_run_removed_nothing(result, axi)
        self._assert_next_run_prunes()

    def test_deploy_error_removes_nothing_and_the_next_run_prunes(self):
        # A directory where a tool script must be written: the deploy fails.
        blocker = self.target_root / ".agents/scripts/gate-lock.sh"
        blocker.unlink()
        blocker.mkdir()
        (blocker / "keep").write_text("x\n", encoding="utf-8")
        self.tree_before = self.snapshot(self.target_root)
        result, axi = self.reinstall("--stacks", "python")
        self.assertEqual(axi.get("outcome"), "deploy_failed", f"fixture: axi={axi!r}")
        self._assert_failed_run_removed_nothing(result, axi)
        shutil.rmtree(blocker)
        self._assert_next_run_prunes()


class PruneOSErrorWritesNoInstallTomlTest(_PruneSandboxCase):
    """An ``OSError`` while pruning fails the run with no ``install.toml``
    written; the next run completes the prune, skipping what is gone."""

    def setUp(self):
        super().setUp()
        self.install("--stacks", "python,rust")
        self.locked = self.target_root / ".agents/skills/crucible-report-rust"
        self.locked.chmod(stat.S_IRUSR | stat.S_IXUSR)
        self.addCleanup(self._unlock)
        if os.access(self.locked, os.W_OK):
            self.fail("fixture: the bundle dir must be unwritable (run as a non-root user)")
        self.toml_before = self.install_toml_path.read_bytes()

    def _unlock(self):
        """Restore write access, when the pruned bundle dir still exists."""
        if self.locked.is_dir():
            self.locked.chmod(stat.S_IRWXU)

    def test_pruning_oserror_fails_and_keeps_the_prior_install_toml(self):
        result, axi = self.reinstall("--stacks", "python")
        self.assertNotEqual(result.returncode, 0,
                            f"§S1: a pruning OSError fails the run; axi={axi!r}")
        self.assertIs(axi.get("ok"), False, f"axi={axi!r}")
        self.assertEqual(axi.get("outcome"), "deploy_failed",
                         f"§S1: a pruning OSError ends like any deploy failure; axi={axi!r}")
        self.assertEqual(self.install_toml_path.read_bytes(), self.toml_before,
                         "§S1: no install.toml is written after a pruning OSError")
        self.assertTrue((self.target_root / RUST_REPORT_SKILL).is_file())

    def test_the_next_run_completes_the_prune(self):
        self.reinstall("--stacks", "python")
        self._unlock()
        result, axi = self.reinstall("--stacks", "python")
        self.assert_installed(result, axi)
        left = sorted(rel for rel in self.rust_only_files() if (self.target_root / rel).exists())
        self.assertEqual(left, [], "§S1: the later run re-prunes")
        removed = axi.get("removed")
        if not isinstance(removed, list):
            self.fail(f"§S2: the installed envelope carries a `removed` list; axi={axi!r}")
        self.assertIn(RUST_REPORT_SKILL, removed)
        self.assertEqual(sorted(set(removed) - self.rust_only_files()), [],
                         "only leftovers are reported; already-gone ones are skipped")
        recorded = sorted(p for p in self.manifest_paths()
                          if any(f"/{b}/" in p for b in RUST_ONLY_BUNDLES))
        self.assertEqual(recorded, [])


# ---------------------------------------------------------------------------
# §S2 — removed/kept always present on the installed outcome
# ---------------------------------------------------------------------------

class InstalledEnvelopeRemovedKeptTest(_PruneSandboxCase):
    """``removed`` and ``kept`` are always present on ``installed``, and
    empty when there is nothing to report."""

    def test_first_install_carries_empty_removed_and_kept(self):
        result, axi = self.run_installer("--stacks", "python")
        self.assert_installed(result, axi)
        self.assert_envelope_lists(axi, removed=(), kept=())

    def test_same_stacks_reinstall_carries_empty_removed_and_kept(self):
        self.install("--stacks", "python")
        before = self.snapshot(self.target_root)
        result, axi = self.reinstall("--stacks", "python")
        self.assert_installed(result, axi)
        self.assert_envelope_lists(axi, removed=(), kept=())
        self.assertEqual(self.snapshot(self.target_root), before)

    def test_already_gone_leftover_is_not_reported(self):
        self.install("--stacks", "python")
        self.record_deployed(RETIRED_SKILL, b"never on disk\n", write=False)
        result, axi = self.reinstall("--stacks", "python")
        self.assert_installed(result, axi)
        self.assert_envelope_lists(axi, removed=(), kept=())
        self.assertEqual(self.stderr_lines_naming(result.stderr, RETIRED_SKILL), [])
        self.assertNotIn(RETIRED_SKILL, self.manifest_paths())


# ---------------------------------------------------------------------------
# §S2 — the `retired` hint and the install guide
# ---------------------------------------------------------------------------

class RetiredHintReportTest(_PruneSandboxCase):
    """The ``already_installed`` report's ``retired`` hint names the
    ``--reinstall`` re-run, not a manual removal; following the printed
    re-run removes the unchanged retired file."""

    def setUp(self):
        super().setUp()
        self.install("--stacks", "python")
        self.retired = self.record_deployed(RETIRED_SKILL, b"retired\n")

    def run_bare(self):
        return self.run_argv(["--yes", "--modelb-home", str(self.modelb_home)])

    def _retired_hint(self, stderr: str) -> str:
        hits = [ln.strip() for ln in stderr.splitlines() if ln.strip().startswith("retired:")]
        self.assertEqual(len(hits), 1, f"exactly one `retired:` hint; stderr={stderr!r}")
        return hits[0]

    def test_retired_hint_names_reinstall_not_a_manual_removal(self):
        result, axi = self.run_bare()
        self.assertEqual(axi.get("outcome"), "already_installed", f"axi={axi!r}")
        self.assertEqual(axi.get("retired"), [RETIRED_SKILL], f"fixture: axi={axi!r}")
        hint = self._retired_hint(result.stderr)
        self.assertNotIn("by hand", hint, f"§S2: no manual removal any more; hint={hint!r}")
        self.assertIn("--reinstall", hint, f"§S2: the hint names the re-run; hint={hint!r}")

    def test_following_the_printed_reinstall_removes_the_retired_file(self):
        result, _axi = self.run_bare()
        commands = [c for c in re.findall(r"`([^`]+)`", result.stderr)
                    if c.startswith("modelb-axi ") and "--reinstall" in c]
        self.assertTrue(commands, f"§S2: a `--reinstall` command is printed; "
                                  f"stderr={result.stderr!r}")
        argv = shlex.split(commands[0])
        # Sandbox guard: only a re-run naming THIS sandbox is executed.
        for flag, expected in (("--modelb-home", self.modelb_home),
                               ("--target-root", self.target_root)):
            self.assertIn(flag, argv, f"argv={argv!r}")
            self.assertEqual(argv[argv.index(flag) + 1], str(expected), f"argv={argv!r}")
        rerun, rerun_axi = self.run_argv(argv[1:])
        self.assert_installed(rerun, rerun_axi)
        self.assertFalse(self.retired.exists(), "§S2: the re-run removes the retired file")
        after, after_axi = self.run_bare()
        self.assertEqual(after_axi.get("retired"), [], f"axi={after_axi!r}")


class RetiredHintDocsTest(unittest.TestCase):
    """``docs/install-guide.md`` says ``--reinstall`` removes unchanged
    retired files; ``pi-package/README.md`` carries the same text."""

    def _retired_bullet(self, path: Path) -> str:
        lines = path.read_text(encoding="utf-8").splitlines()
        starts = [i for i, ln in enumerate(lines) if ln.startswith("- `retired`")]
        self.assertEqual(len(starts), 1, f"{path.name}: exactly one `retired` bullet")
        bullet = [lines[starts[0]]]
        for ln in lines[starts[0] + 1:]:
            if not ln.strip() or ln.startswith(("- ", "<!--", "#")):
                break
            bullet.append(ln)
        return " ".join(part.strip() for part in bullet)

    def test_install_guide_says_reinstall_removes_unchanged_retired_files(self):
        bullet = self._retired_bullet(INSTALL_GUIDE)
        self.assertNotIn("by hand", bullet, f"§S2: bullet={bullet!r}")
        self.assertIn("--reinstall", bullet, f"§S2: bullet={bullet!r}")
        self.assertRegex(bullet, r"(?i)\bremov", f"§S2: the re-run removes them; bullet={bullet!r}")

    def test_pi_readme_retired_bullet_matches_the_guide(self):
        guide = self._retired_bullet(INSTALL_GUIDE)
        self.assertNotIn("by hand", guide, "§S2: the guide is updated first")
        self.assertEqual(self._retired_bullet(PI_README), guide,
                         "§S2: pi-package/README.md is regenerated from the guide")


# ---------------------------------------------------------------------------
# §S1 — deploy.prune_assets, the unit seam
# ---------------------------------------------------------------------------

class PruneAssetsTest(unittest.TestCase):
    """``deploy.prune_assets(prior_root, prior_files, new_paths)`` on a
    temp target root (no installer run)."""

    def setUp(self):
        self._root = Path(tempfile.mkdtemp(prefix="modelb-cr040-unit-"))
        self.target = self._root / "target"
        self.target.mkdir()
        self.addCleanup(shutil.rmtree, self._root, True)

    def put(self, rel: str, content: bytes = b"deployed\n", root: Path | None = None) -> dict:
        path = (root or self.target) / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return {"path": rel, "sha256": hashlib.sha256(content).hexdigest()}

    def prune(self, prior_files, new_paths=()):
        from modelb_axi import deploy
        result = deploy.prune_assets(self.target, list(prior_files), set(new_paths))
        if isinstance(result, dict):
            return list(result["removed"]), list(result["kept"])
        removed, kept = result
        return list(removed), list(kept)

    def test_unchanged_leftover_is_removed_and_returned(self):
        entry = self.put(RETIRED_SKILL)
        keep = self.put(".agents/skills/crucible/SKILL.md")
        removed, kept = self.prune([entry, keep], new_paths=[keep["path"]])
        self.assertEqual((removed, kept), ([RETIRED_SKILL], []))
        self.assertFalse((self.target / RETIRED_SKILL).exists())
        self.assertTrue((self.target / keep["path"]).is_file(),
                        "a path still in the new manifest is never touched")

    def test_emptied_directories_are_removed_up_to_the_store_root(self):
        entries = [self.put(RETIRED_SKILL), self.put(".agents/skills/chezmoi/a/b/deep.md")]
        removed, _kept = self.prune(entries)
        self.assertEqual(sorted(removed), sorted(e["path"] for e in entries))
        self.assertFalse((self.target / ".agents/skills/chezmoi").exists())
        self.assertTrue((self.target / ".agents/skills").is_dir())

    def test_store_roots_survive_when_every_file_in_them_is_pruned(self):
        entries = [self.put(RETIRED_SKILL), self.put(RETIRED_HOOK), self.put(RETIRED_TOOL)]
        removed, kept = self.prune(entries)
        self.assertEqual((sorted(removed), kept),
                         (sorted([RETIRED_SKILL, RETIRED_HOOK, RETIRED_TOOL]), []))
        for store in STORE_ROOTS:
            with self.subTest(store=store):
                self.assertTrue((self.target / store).is_dir(),
                                f"{store} is never removed, even empty")
                self.assertEqual(list((self.target / store).iterdir()), [])

    def test_directory_holding_an_unmanaged_file_is_kept(self):
        entry = self.put(RETIRED_SKILL)
        (self.target / ".agents/skills/chezmoi/mine.md").write_text("mine\n", encoding="utf-8")
        removed, _kept = self.prune([entry])
        self.assertEqual(removed, [RETIRED_SKILL])
        self.assertEqual((self.target / ".agents/skills/chezmoi/mine.md")
                         .read_text(encoding="utf-8"), "mine\n")

    def test_hand_modified_leftover_is_kept_and_returned_untouched(self):
        entry = self.put(RETIRED_SKILL, b"as deployed\n")
        (self.target / RETIRED_SKILL).write_bytes(b"edited\n")
        removed, kept = self.prune([entry])
        self.assertEqual((removed, kept), ([], [RETIRED_SKILL]))
        self.assertEqual((self.target / RETIRED_SKILL).read_bytes(), b"edited\n")

    def test_already_gone_leftover_is_neither_removed_nor_kept(self):
        entry = self.put(RETIRED_SKILL)
        (self.target / RETIRED_SKILL).unlink()
        self.assertEqual(self.prune([entry]), ([], []))

    def test_paths_outside_the_three_stores_are_never_touched(self):
        outside = {
            ".bashrc": self.target / ".bashrc",
            "../outside.txt": self._root / "outside.txt",
            ".agents/skills/../../escape.txt": self.target / "escape.txt",
            str(self._root / "absolute.txt"): self._root / "absolute.txt",
            ".agents/other/thing.txt": self.target / ".agents/other/thing.txt",
            ".agents/hooks/not-a-script.txt": self.target / ".agents/hooks/not-a-script.txt",
        }
        entries = []
        for rel, path in outside.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"not model b's\n")
            entries.append({"path": rel, "sha256": hashlib.sha256(b"not model b's\n").hexdigest()})
        entries.append(self.put(RETIRED_SKILL))
        removed, kept = self.prune(entries)
        self.assertEqual((removed, kept), ([RETIRED_SKILL], []),
                         "a corrupt entry is in neither list")
        for rel, path in outside.items():
            with self.subTest(rel=rel):
                self.assertEqual(path.read_bytes(), b"not model b's\n")

    def test_unremovable_leftover_raises_deploy_error(self):
        entry = self.put(RETIRED_SKILL)
        bundle = self.target / ".agents/skills/chezmoi"
        bundle.chmod(stat.S_IRUSR | stat.S_IXUSR)
        self.addCleanup(bundle.chmod, stat.S_IRWXU)
        if os.access(bundle, os.W_OK):
            self.fail("fixture: the bundle dir must be unwritable (run as a non-root user)")
        with self.assertRaises(DeployError) as ctx:
            self.prune([entry])
        self.assertIsInstance(ctx.exception.__cause__, OSError,
                              "§S1: the OSError is carried as the DeployError's cause")
        self.assertTrue((self.target / RETIRED_SKILL).is_file())


if __name__ == "__main__":
    unittest.main()
