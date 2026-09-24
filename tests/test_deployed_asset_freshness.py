"""Deployed assets report their state on an installed machine
(CR-MDB-037 §S2 + the Migration AC for the ``already_installed`` envelope).

Against the manifest (``install.toml`` ``[[files]]``) and the package the
installer is running from, a deployed asset is:

- **current** — deployed hash = manifest hash = packaged source hash;
- **stale** — deployed = manifest, but the packaged source differs;
- **hand-modified** — deployed ≠ manifest;
- **retired** — in the manifest, but the package ships no source for it.

A bare ``modelb-axi`` on an installed machine (the ``already_installed``
outcome) reports ``stale``, ``hand_modified`` and ``retired`` as lists of
target-root-relative paths. Without a recorded ``target_root`` the
envelope carries ``freshness: unknown`` and a warning naming the re-run,
and reads no deployed file.

Orchestrator rulings (2026-09-24, CR-MDB-037 C2 RED) pin what the spec
leaves open:

1. With a known ``target_root`` the three lists are ALWAYS present (``[]``
   when clean), each the exact sorted list of manifest paths as recorded in
   ``install.toml``; ``freshness`` is asserted only to be not ``unknown``.
2. Without ``target_root``: ``freshness: unknown``, the three lists ABSENT,
   one warning naming both ``--reinstall`` and ``--target-root``; outcome
   ``already_installed``, ok=true, exit 0 — findings never flip ok/exit.
3. "Reads no deployed file" is observed with ``sys.addaudithook`` in a
   subprocess wrapper, logging every ``open`` event.
4. Stale is built WITHOUT swapping the package: after a real sandboxed
   install, one deployed file AND its manifest hash are rewritten to an
   "older" revision (deployed = manifest ≠ the real packaged source).

Isolation (NON-NEGOTIABLE): every run pins ``HOME`` (sandbox, no Crucible
manifest), ``PATH`` (a fake-bin dir of shims), ``MODELB_HOME`` (via
``--modelb-home`` and the env) and ``PI_CODING_AGENT_DIR`` (a provisioned
sandbox agent dir). The real ``~/.pi``, ``~/.agents`` and ``~/.crucible``
are never touched.

Stdlib only.
"""

import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path

from tests.pi_capability_sandbox import (
    AGENT_DIR_ENV,
    make_home,
    make_provisioned_agent_dir,
)

REPO_ROOT = Path(__file__).resolve().parent.parent

#: Manifest paths exercised below (target-root-relative, as recorded).
SKILL_REL = ".agents/skills/crucible/SKILL.md"
OTHER_SKILL_REL = ".agents/skills/model-b/SKILL.md"
HOOK_REL = ".agents/hooks/scripts/ambient-board-status"
TOOL_REL = ".agents/scripts/gate-lock.sh"
#: A bundle the running package no longer ships — the shape of the spec's
#: example (a report bundle whose source was deleted, still listed by old
#: installs); named neutrally so the retired-IDE grep gate stays clean.
RETIRED_REL = ".agents/skills/crucible-report-retired/SKILL.md"

_FAKE_UV = (
    "#!/bin/sh\n"
    'if [ "$1" = "tool" ] && [ "$2" = "install" ]; then exit 0; fi\n'
    'echo "uv 0.0.0-fake"\n'
    "exit 0\n"
)
_FAKE_TOOL = "#!/bin/sh\necho fake\nexit 0\n"

#: Runs ``modelb_axi.cli.main`` with an audit hook logging every path
#: OPENED (builtins/io/os.open all raise the ``open`` audit event).
_OPEN_LOGGING_WRAPPER = r"""
import json, os, sys
_log_path = os.environ["MODELB_TEST_OPEN_LOG"]
_opened = []
def _hook(event, args):
    if event == "open" and args:
        target = args[0]
        if isinstance(target, (str, bytes, os.PathLike)):
            _opened.append(os.fsdecode(target))
sys.addaudithook(_hook)
import atexit
def _dump():
    snapshot = list(_opened)
    with open(_log_path, "w", encoding="utf-8") as fh:
        json.dump(snapshot, fh)
atexit.register(_dump)
from modelb_axi.cli import main
sys.exit(main(sys.argv[1:]))
"""


def _write_exe(bin_dir: Path, name: str, body: str) -> Path:
    path = Path(bin_dir) / name
    path.write_text(body, encoding="utf-8")
    path.chmod(0o755)
    return path


def _sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _decode(stdout: str) -> dict:
    from modelb_axi.toon import decode
    try:
        return decode(stdout).get("axi", {})
    except Exception:  # noqa: BLE001 — a non-envelope stdout fails the caller's asserts
        return {}


class _InstalledMachineCase(unittest.TestCase):
    """A REAL sandboxed install (``--harnesses pi --stacks bun``) into a
    sandbox target root, then helpers to mutate the deployed tree and the
    manifest, and to run bare ``modelb-axi`` against it."""

    #: The sandbox root's prefix (a subclass may put a space in it).
    ROOT_PREFIX = "modelb-cr037-freshness-"

    def setUp(self):
        self._root = Path(tempfile.mkdtemp(prefix=self.ROOT_PREFIX))
        self.modelb_home = self._root / "modelb-home"
        self.target_root = self._root / "target"
        self.bin_dir = self._root / "bin"
        self.home = self._root / "home"
        self.agent_dir = self._root / "agent"
        self.cwd = self._root / "cwd"
        #: XDG_DATA_HOME for every run — a sandbox, never the real one;
        #: the default home (``<it>/modelb``) is NOT ``self.modelb_home``.
        self.xdg_data_home = self._root / "xdg-data"
        for d in (self.modelb_home, self.target_root, self.bin_dir, self.cwd,
                  self.xdg_data_home):
            d.mkdir(parents=True)
        make_home(self.home, crucible_manifest=False)
        make_provisioned_agent_dir(self.agent_dir)
        _write_exe(self.bin_dir, "uv", _FAKE_UV)
        for name in ("sandesh", "bun", "node"):
            _write_exe(self.bin_dir, name, _FAKE_TOOL)
        self._install()

    def tearDown(self):
        shutil.rmtree(self._root, ignore_errors=True)

    # -- runners ----------------------------------------------------------

    def _env(self, extra=None) -> dict:
        env = dict(os.environ)
        env.pop("MODELB_TARGET_ROOT", None)
        existing_pp = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = str(REPO_ROOT) + (os.pathsep + existing_pp if existing_pp else "")
        env.update({
            "HOME": str(self.home),
            "PATH": str(self.bin_dir),
            "MODELB_HOME": str(self.modelb_home),
            "XDG_DATA_HOME": str(self.xdg_data_home),
            AGENT_DIR_ENV: str(self.agent_dir),
        })
        env.update(extra or {})
        return env

    def _install(self):
        result = subprocess.run(
            [sys.executable, "-m", "modelb_axi", "--yes", "--harnesses", "pi",
             "--modelb-home", str(self.modelb_home),
             "--target-root", str(self.target_root), "--stacks", "bun"],
            capture_output=True, text=True, timeout=120, stdin=subprocess.DEVNULL,
            env=self._env(), cwd=str(self.cwd),
        )
        axi = _decode(result.stdout)
        if result.returncode != 0 or axi.get("outcome") != "installed":
            self.fail(
                f"fixture precondition: the sandboxed install must succeed; "
                f"exit={result.returncode} axi={axi!r} stderr={result.stderr!r}"
            )

    def run_bare(self):
        """Bare ``modelb-axi --yes`` on the installed machine."""
        result = subprocess.run(
            [sys.executable, "-m", "modelb_axi", "--yes",
             "--modelb-home", str(self.modelb_home)],
            capture_output=True, text=True, timeout=60, stdin=subprocess.DEVNULL,
            env=self._env(), cwd=str(self.cwd),
        )
        return result, _decode(result.stdout)

    def run_bare_logging_opens(self):
        """As :meth:`run_bare`, returning the list of every path opened."""
        log_path = self._root / "open-log.json"
        result = subprocess.run(
            [sys.executable, "-c", _OPEN_LOGGING_WRAPPER, "--yes",
             "--modelb-home", str(self.modelb_home)],
            capture_output=True, text=True, timeout=60, stdin=subprocess.DEVNULL,
            env=self._env({"MODELB_TEST_OPEN_LOG": str(log_path)}), cwd=str(self.cwd),
        )
        if not log_path.is_file():
            self.fail(f"open log not written; exit={result.returncode} stderr={result.stderr!r}")
        return result, _decode(result.stdout), json.loads(log_path.read_text(encoding="utf-8"))

    # -- manifest ----------------------------------------------------------

    @property
    def install_toml_path(self) -> Path:
        return self.modelb_home / "install.toml"

    def load_install(self) -> dict:
        with open(self.install_toml_path, "rb") as fh:
            return tomllib.load(fh)

    def write_install(self, data: dict) -> None:
        from modelb_axi.config import serialize_install_toml
        self.install_toml_path.write_text(
            serialize_install_toml(
                data["install"], data["deps"], data.get("files", []),
                data.get("capabilities"),
            ),
            encoding="utf-8",
        )

    def manifest_paths(self) -> list[str]:
        return [entry["path"] for entry in self.load_install().get("files", [])]

    def set_manifest_hash(self, rel: str, sha: str) -> None:
        data = self.load_install()
        hits = [e for e in data["files"] if e["path"] == rel]
        self.assertEqual(len(hits), 1, f"fixture: exactly one manifest entry for {rel}")
        hits[0]["sha256"] = sha
        self.write_install(data)

    # -- states ------------------------------------------------------------

    def make_stale(self, rel: str) -> None:
        """deployed = manifest ≠ packaged source: the deployed file and its
        manifest hash both carry an OLDER revision (ruling 4)."""
        deployed = self.target_root / rel
        self.assertIn(rel, self.manifest_paths(), f"fixture: {rel} must be deployed")
        deployed.write_bytes(deployed.read_bytes() + b"\n# an older packaged revision\n")
        self.set_manifest_hash(rel, _sha256(deployed))

    def make_hand_modified(self, rel: str) -> None:
        """deployed ≠ manifest (the manifest still holds the source hash)."""
        deployed = self.target_root / rel
        self.assertIn(rel, self.manifest_paths(), f"fixture: {rel} must be deployed")
        deployed.write_bytes(deployed.read_bytes() + b"\n# edited by hand\n")

    def make_retired(self, rel: str) -> None:
        """A manifest entry (deployed = manifest) whose packaged source the
        running package no longer ships."""
        source = REPO_ROOT / "skills-src" / Path(rel).relative_to(".agents/skills")
        self.assertFalse(source.exists(), f"fixture: {source} must not be packaged")
        deployed = self.target_root / rel
        deployed.parent.mkdir(parents=True, exist_ok=True)
        deployed.write_text("---\nname: crucible-report-retired\n---\n", encoding="utf-8")
        data = self.load_install()
        data["files"].append({"path": rel, "sha256": _sha256(deployed)})
        self.write_install(data)

    # -- assertions ----------------------------------------------------------

    def _hint(self, stderr: str, state: str) -> str:
        """The one stderr hint line for ``state`` (``<state>: re-run …``)."""
        hits = [ln.strip() for ln in stderr.splitlines()
                if ln.strip().startswith(f"{state}:")]
        self.assertEqual(len(hits), 1, f"exactly one `{state}:` hint; stderr={stderr!r}")
        return hits[0]

    def assert_already_installed(self, result, axi):
        self.assertEqual(result.returncode, 0,
                         f"exit={result.returncode} stdout={result.stdout!r} stderr={result.stderr!r}")
        self.assertEqual(axi.get("outcome"), "already_installed", f"axi={axi!r}")
        self.assertIs(axi.get("ok"), True, f"findings never flip ok; axi={axi!r}")

    def assert_lists(self, axi, *, stale=(), hand_modified=(), retired=()):
        for key, expected in (("stale", stale), ("hand_modified", hand_modified),
                              ("retired", retired)):
            with self.subTest(list=key):
                self.assertEqual(
                    axi.get(key), sorted(expected),
                    f"§S2: envelope `{key}` must be exactly {sorted(expected)!r}; "
                    f"axi={axi!r}",
                )


class DeployedAssetFreshnessTest(_InstalledMachineCase):
    """§S2 with a recorded ``target_root``: each state lands in its own
    list, and only there."""

    def test_nothing_changed_reports_three_empty_lists(self):
        result, axi = self.run_bare()
        self.assert_already_installed(result, axi)
        self.assert_lists(axi)
        self.assertNotEqual(axi.get("freshness"), "unknown",
                            f"a recorded target_root is judged; axi={axi!r}")

    def test_deployed_skill_left_as_installed_with_changed_source_is_listed_under_stale_only(self):
        self.make_stale(SKILL_REL)
        result, axi = self.run_bare()
        self.assert_already_installed(result, axi)
        self.assert_lists(axi, stale=[SKILL_REL])

    def test_deployed_skill_edited_by_hand_is_listed_under_hand_modified_only(self):
        self.make_hand_modified(SKILL_REL)
        result, axi = self.run_bare()
        self.assert_already_installed(result, axi)
        self.assert_lists(axi, hand_modified=[SKILL_REL])

    def test_manifest_entry_without_packaged_source_is_listed_under_retired_only(self):
        self.make_retired(RETIRED_REL)
        result, axi = self.run_bare()
        self.assert_already_installed(result, axi)
        self.assert_lists(axi, retired=[RETIRED_REL])

    def test_stale_covers_hook_and_tool_scripts_not_only_skills(self):
        self.make_stale(HOOK_REL)
        self.make_stale(TOOL_REL)
        result, axi = self.run_bare()
        self.assert_already_installed(result, axi)
        self.assert_lists(axi, stale=[HOOK_REL, TOOL_REL])

    def test_each_state_lands_in_its_own_list_when_all_three_occur_together(self):
        self.make_stale(SKILL_REL)
        self.make_hand_modified(OTHER_SKILL_REL)
        self.make_retired(RETIRED_REL)
        result, axi = self.run_bare()
        self.assert_already_installed(result, axi)
        self.assert_lists(axi, stale=[SKILL_REL], hand_modified=[OTHER_SKILL_REL],
                          retired=[RETIRED_REL])

    def test_stale_hint_names_the_re_run_that_works(self):
        """VERIFY finding 1: a bare ``--reinstall`` is not a re-run that
        works — it needs the target root and the stacks, as the guide says."""
        self.make_stale(SKILL_REL)
        result, axi = self.run_bare()
        self.assert_already_installed(result, axi)
        hint = self._hint(result.stderr, "stale")
        for flag in ("--reinstall", "--target-root", "--stacks"):
            with self.subTest(flag=flag):
                self.assertIn(flag, hint, f"the stale hint must name {flag}; hint={hint!r}")
        self.assertNotIn("--force-managed", hint,
                         f"a stale file needs no --force-managed; hint={hint!r}")

    def test_hand_modified_hint_names_the_re_run_with_force_managed(self):
        """VERIFY finding 1: ``--force-managed`` alone never reaches the
        installer on an installed machine — the re-run needs ``--reinstall``
        with the target root and stacks as well."""
        self.make_hand_modified(SKILL_REL)
        result, axi = self.run_bare()
        self.assert_already_installed(result, axi)
        hint = self._hint(result.stderr, "hand_modified")
        for flag in ("--reinstall", "--target-root", "--stacks", "--force-managed"):
            with self.subTest(flag=flag):
                self.assertIn(flag, hint,
                              f"the hand_modified hint must name {flag}; hint={hint!r}")

    def test_reporting_writes_neither_the_deployed_tree_nor_install_toml(self):
        self.make_stale(SKILL_REL)
        self.make_hand_modified(OTHER_SKILL_REL)
        before_toml = self.install_toml_path.read_bytes()
        before = {rel: (self.target_root / rel).read_bytes()
                  for rel in (SKILL_REL, OTHER_SKILL_REL)}
        result, axi = self.run_bare()
        self.assert_already_installed(result, axi)
        self.assert_lists(axi, stale=[SKILL_REL], hand_modified=[OTHER_SKILL_REL])
        self.assertEqual(self.install_toml_path.read_bytes(), before_toml,
                         "a report never rewrites install.toml")
        for rel, content in before.items():
            self.assertEqual((self.target_root / rel).read_bytes(), content,
                             f"a report never rewrites {rel}")


def _tree_snapshot(root: Path) -> dict:
    """Every file under ``root`` (relative path -> bytes)."""
    return {str(p.relative_to(root)): p.read_bytes()
            for p in sorted(Path(root).rglob("*")) if p.is_file()}


class _ExecutedHintCase(_InstalledMachineCase):
    """VERIFY (cycle 100) findings 1 and 3: the printed re-run is EXECUTED
    — parsed with ``shlex.split`` as a shell would — and must act on the
    very install it was printed for. A ``pi`` shim stands in for the
    harness the install targeted (the re-run detects it on ``PATH``).

    Sandbox guard: a hint is executed only after it is shown to carry
    ``--modelb-home`` and ``--target-root`` naming THIS sandbox, so no
    executed hint ever relies on a default."""

    def setUp(self):
        super().setUp()
        _write_exe(self.bin_dir, "pi", _FAKE_TOOL)

    def hint_argv(self, stderr: str, state: str) -> list[str]:
        line = self._hint(stderr, state)
        match = re.search(r"`([^`]+)`", line)
        if match is None:
            self.fail(f"the `{state}:` hint quotes a command; line={line!r}")
        return shlex.split(match.group(1))

    def assert_hint_targets_this_install(self, argv: list[str]) -> None:
        self.assertEqual(argv[:1], ["modelb-axi"], f"argv={argv!r}")
        # No subTest: a failed guard must abort BEFORE the hint is executed.
        for flag, expected in (("--modelb-home", self.modelb_home),
                               ("--target-root", self.target_root)):
            self.assertIn(flag, argv, f"the re-run must carry {flag}; argv={argv!r}")
            at = argv.index(flag)
            self.assertEqual(
                argv[at + 1:at + 2], [str(expected)],
                f"{flag} must name {expected} as ONE shell word; argv={argv!r}",
            )

    def run_hint(self, argv: list[str]):
        result = subprocess.run(
            [sys.executable, "-m", "modelb_axi", *argv[1:]],
            capture_output=True, text=True, timeout=120, stdin=subprocess.DEVNULL,
            env=self._env(), cwd=str(self.cwd),
        )
        return result, _decode(result.stdout)

    def assert_executed_stale_hint_refreshes_this_install(self):
        self.make_stale(SKILL_REL)
        result, axi = self.run_bare()
        self.assert_already_installed(result, axi)
        self.assert_lists(axi, stale=[SKILL_REL])
        argv = self.hint_argv(result.stderr, "stale")
        self.assert_hint_targets_this_install(argv)
        before_toml = self.install_toml_path.read_bytes()
        other_before = _tree_snapshot(self.xdg_data_home)

        rerun, rerun_axi = self.run_hint(argv)
        self.assertEqual(rerun.returncode, 0,
                         f"the hinted re-run must succeed; axi={rerun_axi!r} "
                         f"stderr={rerun.stderr!r}")
        self.assertEqual(rerun_axi.get("outcome"), "installed", f"axi={rerun_axi!r}")
        self.assertTrue(self.install_toml_path.read_bytes() != before_toml,
                        "the hinted re-run must update THIS install's install.toml")
        self.assertEqual(_tree_snapshot(self.xdg_data_home), other_before,
                         "the hinted re-run must leave the default MODELB_HOME untouched")

        after, after_axi = self.run_bare()
        self.assert_already_installed(after, after_axi)
        self.assertEqual(after_axi.get("freshness"), "current",
                         f"following the hint leaves the install current; axi={after_axi!r}")
        self.assert_lists(after_axi)


class ReinstallHintActsOnTheSameInstallTest(_ExecutedHintCase):
    """Finding 1: installed with ``--modelb-home <A>`` while the default
    home (``$XDG_DATA_HOME/modelb``, and ``MODELB_HOME`` too) is another
    sandbox B, the printed re-run updates A's install and leaves B alone."""

    def _env(self, extra=None) -> dict:
        env = super()._env(extra)
        env["MODELB_HOME"] = str(self.xdg_data_home / "modelb")
        return env

    def test_executed_stale_hint_updates_the_install_it_was_printed_for(self):
        self.assertNotEqual(self.xdg_data_home / "modelb", self.modelb_home,
                            "fixture: the default home is another sandbox")
        self.assert_executed_stale_hint_refreshes_this_install()


class ReinstallHintQuotesPathsWithSpacesTest(_ExecutedHintCase):
    """Finding 3: the target root and the Model B home contain a space;
    the hint quotes each as one shell word, and following it works."""

    ROOT_PREFIX = "modelb cr037 spaced "

    def test_hint_quotes_each_path_as_one_shell_word_and_works(self):
        self.assertIn(" ", str(self.target_root), "fixture: the path has a space")
        self.assert_executed_stale_hint_refreshes_this_install()


class ReinstallHintKeepsTheRecordedHarnessesTest(_ExecutedHintCase):
    """VERIFY (cycle 102) finding 1: the printed re-run carries the
    harnesses ``install.toml`` records, so following it targets the same
    harnesses whatever is on ``PATH`` now. Installed with ``--harnesses pi``."""

    def recorded_harnesses(self):
        return self.load_install()["install"].get("harnesses")

    def test_hint_ignores_a_harness_detected_since_the_install(self):
        self.assertEqual(self.recorded_harnesses(), ["pi"], "fixture: installed for pi only")
        _write_exe(self.bin_dir, "claude", _FAKE_TOOL)
        self.assert_executed_stale_hint_refreshes_this_install()
        self.assertEqual(self.recorded_harnesses(), ["pi"],
                         "following the hint must keep the recorded harnesses exactly")
        self.assertFalse((self.target_root / ".claude").exists(),
                         "following the hint must deploy nothing for a harness the "
                         "install never targeted")

    def test_hint_keeps_a_recorded_harness_no_longer_on_path(self):
        self.assertEqual(self.recorded_harnesses(), ["pi"], "fixture: installed for pi only")
        (self.bin_dir / "pi").unlink()
        self.assert_executed_stale_hint_refreshes_this_install()
        self.assertEqual(self.recorded_harnesses(), ["pi"],
                         "following the hint must still record the install's harness")

class FreshnessUnknownWithoutTargetRootTest(_InstalledMachineCase):
    """§S2: an install.toml older than CR-MDB-033 (no ``target_root`` nor
    the per-class dirs) yields ``freshness: unknown`` and a warning naming
    the re-run — and guesses no location: copies of the deployed tree are
    planted under the sandbox HOME and cwd, and no path ending in a
    manifest path is ever opened."""

    def setUp(self):
        super().setUp()
        self.make_hand_modified(SKILL_REL)  # would be a finding if judged
        data = self.load_install()
        for key in ("target_root", "skills_dir", "hooks_scripts_dir", "tool_scripts_dir"):
            data["install"].pop(key, None)
        self.write_install(data)
        self.manifest = self.manifest_paths()
        self.assertIn(SKILL_REL, self.manifest)
        for guess in (self.home, self.cwd):
            shutil.copytree(self.target_root / ".agents", guess / ".agents",
                            dirs_exist_ok=True)

    def test_envelope_carries_freshness_unknown_and_no_state_lists(self):
        result, axi = self.run_bare()
        self.assert_already_installed(result, axi)
        self.assertEqual(axi.get("freshness"), "unknown", f"axi={axi!r}")
        for key in ("stale", "hand_modified", "retired"):
            self.assertNotIn(key, axi, f"ruling 2: `{key}` would claim a judgement; axi={axi!r}")

    def test_warning_names_the_re_run_that_records_a_target_root(self):
        result, axi = self.run_bare()
        self.assert_already_installed(result, axi)
        hits = [w for w in axi.get("warnings", [])
                if "--reinstall" in w and "--target-root" in w]
        self.assertEqual(len(hits), 1,
                         f"exactly one warning naming the re-run; warnings={axi.get('warnings')!r}")
        # Existing scaffold-mode guards assert this phrase is absent.
        self.assertNotIn("installer flow", result.stderr.lower())

    def test_reads_no_deployed_file(self):
        result, axi, opened = self.run_bare_logging_opens()
        self.assert_already_installed(result, axi)
        self.assertEqual(axi.get("freshness"), "unknown", f"axi={axi!r}")
        self.assertTrue(any(p.endswith("install.toml") for p in opened),
                        f"audit hook live: install.toml must be seen opened; opened={opened!r}")
        touched = sorted({p for p in opened for rel in self.manifest if p.endswith(rel)})
        self.assertEqual(touched, [], "no deployed file may be read without a target_root")

    # -- VERIFY (cycle 102) finding 2: the warning names the full re-run --

    def unknown_rerun_argv(self):
        """The re-run the ``freshness unknown`` warning quotes, split as a
        shell would; asserts the scaffold-mode guard phrase stays absent."""
        result, axi = self.run_bare()
        self.assert_already_installed(result, axi)
        self.assertEqual(axi.get("freshness"), "unknown", f"axi={axi!r}")
        self.assertNotIn("installer flow", result.stderr.lower())
        hits = [w for w in axi.get("warnings", []) if "freshness unknown" in w]
        self.assertEqual(len(hits), 1, f"warnings={axi.get('warnings')!r}")
        match = re.search(r"`([^`]+)`", hits[0])
        if match is None:
            self.fail(f"the warning quotes a command; warning={hits[0]!r}")
        return shlex.split(match.group(1))

    def assert_flag(self, argv, flag, value):
        self.assertIn(flag, argv, f"the re-run must carry {flag}; argv={argv!r}")
        at = argv.index(flag)
        self.assertEqual(argv[at + 1:at + 2], [value],
                         f"{flag} must be followed by {value!r}; argv={argv!r}")

    def test_warning_names_home_stacks_and_harnesses_the_install_records(self):
        self.assertNotEqual(self.xdg_data_home / "modelb", self.modelb_home,
                            "fixture: the install's home is not the default")
        argv = self.unknown_rerun_argv()
        self.assertEqual(argv[:2], ["modelb-axi", "--reinstall"], f"argv={argv!r}")
        self.assert_flag(argv, "--target-root", "<dir>")
        self.assert_flag(argv, "--modelb-home", str(self.modelb_home))
        self.assert_flag(argv, "--stacks", "bun")
        self.assert_flag(argv, "--harnesses", "pi")

    def test_warning_omits_modelb_home_when_the_install_uses_the_default(self):
        default_home = self.xdg_data_home / "modelb"
        default_home.mkdir(parents=True)
        shutil.copy2(self.install_toml_path, default_home / "install.toml")
        self.modelb_home = default_home
        argv = self.unknown_rerun_argv()
        self.assertNotIn("--modelb-home", argv, f"a default home needs no flag; argv={argv!r}")
        self.assert_flag(argv, "--target-root", "<dir>")
        self.assert_flag(argv, "--stacks", "bun")
        self.assert_flag(argv, "--harnesses", "pi")

    def test_warning_omits_stacks_and_harnesses_the_install_does_not_record(self):
        data = self.load_install()
        for key in ("stacks", "harnesses"):
            data["install"].pop(key, None)
        self.write_install(data)
        argv = self.unknown_rerun_argv()
        self.assertEqual(argv[:2], ["modelb-axi", "--reinstall"], f"argv={argv!r}")
        self.assert_flag(argv, "--target-root", "<dir>")
        for flag in ("--stacks", "--harnesses"):
            with self.subTest(flag=flag):
                self.assertNotIn(flag, argv, f"nothing recorded, nothing named; argv={argv!r}")


class FreshnessUnknownQuotesPathsWithSpacesTest(FreshnessUnknownWithoutTargetRootTest):
    """Finding 2, shlex quoting: a Model B home with a space stays one word."""

    ROOT_PREFIX = "modelb cr037 unknown spaced "



if __name__ == "__main__":
    unittest.main()
