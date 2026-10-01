"""The installer's Sandesh and direnv requirements (CR-MDB-047 §S1; DN-multi-
harness §D20 with its Sandesh 0.4.0 amendment, PRD D10).

- ``sandesh-pi`` — Sandesh's own Pi extension, the wake path — is a tier-1
  ``required`` row. ``--yes`` still never installs it (a third-party package):
  an absent one fails the pre-flight naming its remediation, unless
  ``--allow-missing-capabilities``.
- The ``watcher`` row becomes the ``worktree`` row: the same provider
  (``@anthill-tec/modelb-pi``), policy, probe and ``--yes`` install, with tools
  ``modelb_worktree_enter``/``_exit`` only. ``read_tool_verdicts`` reads a
  recorded ``watcher`` verdict as ``worktree``'s, so an ``install.toml``
  written before CR-MDB-047 still reports it.
- The ``sandesh`` probe runs ``sandesh --version``; below 0.4.0 the verdict is
  ``outdated`` — reported like ``absent`` with ``uv tool upgrade
  sandesh-relay``, recorded in ``[deps]``, and read by ``init`` as not present.
- ``direnv`` is a tier-2 ``path`` probe, policy ``recommended``, whose
  remediation names installing direnv and its shell hook. The hook is never
  probed.

Isolation (NON-NEGOTIABLE): every ``install.toml``, Pi agent dir, home and
``sandesh`` binary is a fixture under a per-test temp dir; ``PATH`` is a
fake-bin dir holding a fake ``sandesh`` that answers ``--version``. The
installer runs with ``HOME``, ``PATH``, ``PI_CODING_AGENT_DIR``,
``MODELB_HOME`` and ``XDG_DATA_HOME`` pinned there; the in-process pre-flight
and ``init`` run with ``HOME``, ``PATH`` and ``PI_CODING_AGENT_DIR`` pinned.
No test reads the real ``~/.local/share/modelb``, ``~/.pi`` or ``sandesh``.

Stdlib only.
"""

import argparse
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
from unittest import mock

from tests._helpers import decode_axi, write_executable
from tests.pi_capability_sandbox import (
    AGENT_DIR_ENV,
    MODELB_PI_PACKAGE,
    fake_sandesh,
    make_agent_dir,
    make_home,
    make_provisioned_agent_dir,
    parse_group_line,
)

REPO_ROOT = Path(__file__).resolve().parent.parent

SANDESH_PI_PACKAGE = "@anthill-tec/sandesh-pi"
SANDESH_PI_REMEDIATION = f"pi install npm:{SANDESH_PI_PACKAGE}"
WORKTREE_TOOLS = ["modelb_worktree_enter", "modelb_worktree_exit"]
UPGRADE_SANDESH = "uv tool upgrade sandesh-relay"
DIRENV_FISH_HOOK = "direnv hook fish | source"
DIRENV_BASH_HOOK = 'eval "$(direnv hook bash)"'

_FAKE_OK = "#!/bin/sh\nexit 0\n"
#: The scaffold's ``--token`` value (a project short name, not a credential).
PROJECT_SHORT_NAME = "floorproj"


def _requirements() -> tuple:
    from modelb_axi import requirements
    return requirements.REQUIREMENTS


def _row(requirement_id: str) -> dict:
    rows = [r for r in _requirements() if r.get("id") == requirement_id]
    if len(rows) != 1:
        raise AssertionError(
            f"CR-MDB-047 §S1: exactly one `{requirement_id}` requirement row expected; "
            f"found {len(rows)} among {[r.get('id') for r in _requirements()]}")
    return rows[0]


def _recording_shim(log: Path) -> str:
    """A fake binary appending ``$*`` to ``log`` on every execution."""
    return f'#!/bin/sh\nprintf \'%s\\n\' "$*" >> "{log}"\nexit 0\n'


def _lines(path: Path) -> list[str]:
    if not path.exists():
        return []
    return [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln]


# ---------------------------------------------------------------------------
# The declared rows
# ---------------------------------------------------------------------------

class SandeshPiRequiredRowTest(unittest.TestCase):
    """§S1: ``sandesh-pi`` is tier 1, policy ``required`` (was recommended)."""

    def test_sandesh_pi_is_a_tier1_required_pi_package_row(self):
        row = _row("sandesh-pi")
        self.assertEqual(
            (row["tier"], row["policy"], row["provider"], row["probe"], row["scope"]),
            (1, "required", SANDESH_PI_PACKAGE, "pi-package", "always"),
            row,
        )

    def test_sandesh_pi_remediation_stays_its_pi_install_command(self):
        self.assertEqual(_row("sandesh-pi")["remediation"], SANDESH_PI_REMEDIATION)


class WorktreeRequirementRowTest(unittest.TestCase):
    """§S1: the ``watcher`` row becomes ``worktree`` — same provider, ``--yes``
    install and policy; its tools drop ``sandesh_watcher``."""

    def test_no_watcher_row_is_declared(self):
        from modelb_axi import requirements
        ids = [r.get("id") for r in _requirements()]
        self.assertNotIn("watcher", ids)
        with self.assertRaises(KeyError) as ctx:
            requirements.requirement("watcher")
        self.assertIn("watcher", str(ctx.exception))

    def test_worktree_row_keeps_the_watcher_rows_provider_policy_probe_and_remediation(self):
        row = _row("worktree")
        self.assertEqual(
            (row["tier"], row["provider"], row["policy"], row["scope"], row["probe"],
             row["remediation"]),
            (1, MODELB_PI_PACKAGE, "recommended", "always", "pi-package",
             f"pi install npm:{MODELB_PI_PACKAGE}"),
            row,
        )

    def test_worktree_tools_are_exactly_the_two_worktree_tools(self):
        self.assertEqual(sorted(_row("worktree")["tools"]), WORKTREE_TOOLS)

    def test_no_row_declares_the_sandesh_watcher_tool(self):
        declaring = [r["id"] for r in _requirements() if "sandesh_watcher" in r.get("tools", ())]
        self.assertEqual(declaring, [], "§S1: `sandesh_watcher` is no Model B tool any more")

    def test_the_package_yes_installs_is_the_worktree_rows_provider(self):
        from modelb_axi import preflight
        self.assertEqual(preflight.MODELB_PI_PACKAGE, _row("worktree")["provider"])


class DirenvRequirementRowTest(unittest.TestCase):
    """§S1: direnv is a tier-2 ``path`` probe, policy ``recommended``; its
    remediation names installing direnv and its shell hook."""

    def test_direnv_is_a_tier2_recommended_always_scoped_path_probe(self):
        row = _row("direnv")
        self.assertEqual(
            (row["tier"], row["policy"], row["scope"], row["probe"]),
            (2, "recommended", "always", "path"),
            row,
        )

    def test_direnv_remediation_names_installing_it_and_both_shell_hooks(self):
        remediation = _row("direnv")["remediation"]
        self.assertRegex(remediation, r"(?i)install\w*\b.*\bdirenv",
                         f"names installing direnv; got {remediation!r}")
        self.assertIn(DIRENV_FISH_HOOK, remediation)
        self.assertIn(DIRENV_BASH_HOOK, remediation)


# ---------------------------------------------------------------------------
# The pre-flight, in process, against a sandboxed PATH
# ---------------------------------------------------------------------------

class _PreflightSandboxCase(unittest.TestCase):
    """A fake-bin ``PATH`` (``uv``, a fake ``sandesh`` per test), a fully
    provisioned Pi agent dir and a Crucible-less home; ``run_preflight`` is
    called in process with ``HOME``, ``PATH`` and ``PI_CODING_AGENT_DIR``
    pinned to them."""

    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="modelb-cr047-preflight-")).resolve()
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.bin_dir = self.root / "bin"
        self.bin_dir.mkdir()
        self.home = make_home(self.root / "home", crucible_manifest=False)
        self.agent_dir = make_provisioned_agent_dir(self.root / "pi-agent")
        self.sandesh_log = self.root / "sandesh-runs"
        self.uv_log = self.root / "uv-runs"
        write_executable(self.bin_dir, "uv", _recording_shim(self.uv_log))

    def sandesh_at(self, version: str) -> None:
        write_executable(self.bin_dir, "sandesh", fake_sandesh(version, self.sandesh_log))

    def preflight(self) -> tuple[int, dict, dict, list[str], str]:
        from modelb_axi import preflight
        warnings: list[str] = []
        err = io.StringIO()
        env = {"HOME": str(self.home), "PATH": str(self.bin_dir),
               AGENT_DIR_ENV: str(self.agent_dir)}
        with mock.patch.dict(os.environ, env), contextlib.redirect_stderr(err):
            rc, deps, caps = preflight.run_preflight(
                lambda _prompt: False, warnings, stacks=(), harnesses=("pi",))
        return rc, deps, caps, warnings, err.getvalue()


class SandeshVersionFloorTest(_PreflightSandboxCase):
    """§S1 / AC "Version floor": ``sandesh --version`` below 0.4.0 is
    ``outdated``, reported like ``absent`` with ``uv tool upgrade
    sandesh-relay``; 0.4.0 or later is ``detected``."""

    def test_a_sandesh_below_the_floor_is_outdated_and_names_the_upgrade(self):
        self.sandesh_at("0.3.9")
        rc, deps, caps, warnings, err = self.preflight()
        self.assertEqual(rc, 0, f"recommended: an outdated sandesh never fails; err={err!r}")
        self.assertEqual(deps.get("sandesh"), "outdated", f"[deps]; err={err!r}")
        self.assertEqual(caps.get("sandesh"), "outdated", caps)
        self.assertEqual((parse_group_line(err, "deps:") or {}).get("sandesh"), "outdated",
                         f"the deps: line reports it; err={err!r}")
        hits = [w for w in warnings if UPGRADE_SANDESH in w]
        self.assertEqual(len(hits), 1, f"one warning names `{UPGRADE_SANDESH}`; {warnings!r}")
        self.assertIn("--version", _lines(self.sandesh_log),
                      "§S1: the probe runs `sandesh --version`")

    def test_a_sandesh_at_the_floor_is_detected_without_an_upgrade_warning(self):
        self.sandesh_at("0.4.0")
        rc, deps, caps, warnings, err = self.preflight()
        self.assertEqual(rc, 0, err)
        self.assertEqual((deps.get("sandesh"), caps.get("sandesh")), ("detected", "detected"),
                         f"err={err!r}")
        self.assertEqual([w for w in warnings if UPGRADE_SANDESH in w], [], warnings)
        self.assertEqual(_lines(self.uv_log), [], "a current sandesh runs no uv command")

    def test_versions_compare_numerically_not_as_text(self):
        """0.10.0 is above the floor although "0.10.0" < "0.4.0" as text."""
        self.sandesh_at("0.10.0")
        _rc, deps, _caps, warnings, err = self.preflight()
        self.assertEqual(deps.get("sandesh"), "detected", f"err={err!r}")
        self.assertEqual([w for w in warnings if UPGRADE_SANDESH in w], [], warnings)

    def test_a_patch_release_below_the_floor_is_outdated(self):
        self.sandesh_at("0.3.12")
        _rc, deps, _caps, _warnings, err = self.preflight()
        self.assertEqual(deps.get("sandesh"), "outdated", f"err={err!r}")

    def test_deps_still_carries_exactly_uv_sandesh_and_crucible(self):
        self.sandesh_at("0.3.9")
        _rc, deps, _caps, _warnings, _err = self.preflight()
        self.assertEqual(sorted(deps), ["crucible", "sandesh", "uv"])


class DirenvProbeTest(_PreflightSandboxCase):
    """§S1: direnv is probed on PATH and recorded in ``[capabilities]``; an
    absent one WARNs with its remediation; the hook is never probed (the
    binary is never executed)."""

    def setUp(self):
        super().setUp()
        self.sandesh_at("0.4.0")

    def test_an_absent_direnv_is_recorded_absent_and_warns_with_the_hook_remediation(self):
        rc, deps, caps, warnings, err = self.preflight()
        self.assertEqual(rc, 0, f"recommended: an absent direnv never fails; err={err!r}")
        self.assertEqual(caps.get("direnv"), "absent", caps)
        self.assertNotIn("direnv", deps, "direnv is a [capabilities] tool, never a [deps] one")
        hits = [w for w in warnings if w.startswith("direnv") and DIRENV_FISH_HOOK in w]
        self.assertEqual(len(hits), 1,
                         f"one warning names direnv and its hook remediation; {warnings!r}")

    def test_a_direnv_on_path_is_detected_and_never_executed(self):
        direnv_log = self.root / "direnv-runs"
        write_executable(self.bin_dir, "direnv", _recording_shim(direnv_log))
        _rc, _deps, caps, warnings, err = self.preflight()
        self.assertEqual(caps.get("direnv"), "detected", f"err={err!r}")
        self.assertEqual([w for w in warnings if w.startswith("direnv")], [], warnings)
        self.assertEqual(_lines(direnv_log), [], "§S1: the hook is not probed — direnv never runs")


# ---------------------------------------------------------------------------
# The installer flow, end to end, in a sandbox
# ---------------------------------------------------------------------------

class _InstallerSandboxCase(unittest.TestCase):
    """Per-test sandbox for ``python3 -m modelb_axi --yes``: ``HOME``,
    ``PATH`` (fake ``uv``, ``sandesh``, ``python3`` and a recording ``pi``),
    ``PI_CODING_AGENT_DIR``, ``MODELB_HOME`` and ``XDG_DATA_HOME`` all under a
    temp dir."""

    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="modelb-cr047-installer-")).resolve()
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.modelb_home = self.root / "modelb-home"
        self.target_root = self.root / "target"
        self.xdg_data = self.root / "xdg-data"
        self.bin_dir = self.root / "bin"
        self.agent_dir = self.root / "pi-agent"
        self.pi_log = self.root / "pi-runs"
        self.uv_log = self.root / "uv-runs"
        for path in (self.modelb_home, self.target_root, self.xdg_data, self.bin_dir):
            path.mkdir(parents=True)
        self.home = make_home(self.root / "home", crucible_manifest=False)
        write_executable(self.bin_dir, "uv", _recording_shim(self.uv_log))
        write_executable(self.bin_dir, "sandesh", fake_sandesh("0.4.0"))
        write_executable(self.bin_dir, "python3", _FAKE_OK)
        write_executable(self.bin_dir, "pi", _recording_shim(self.pi_log))

    def run_yes(self, *extra) -> subprocess.CompletedProcess:
        env = dict(os.environ)
        env.pop("MODELB_TARGET_ROOT", None)
        existing = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = str(REPO_ROOT) + (os.pathsep + existing if existing else "")
        env.update({
            "HOME": str(self.home), "PATH": str(self.bin_dir),
            AGENT_DIR_ENV: str(self.agent_dir), "MODELB_HOME": str(self.modelb_home),
            "XDG_DATA_HOME": str(self.xdg_data),
        })
        for name in ("HOME", AGENT_DIR_ENV, "MODELB_HOME", "XDG_DATA_HOME", "PATH"):
            self.assertTrue(env[name].startswith(str(self.root)),
                            f"sandbox guard: {name}={env[name]!r} outside {self.root}")
        return subprocess.run(
            [sys.executable, "-m", "modelb_axi", "--yes", "--harnesses", "pi",
             "--modelb-home", str(self.modelb_home), "--target-root", str(self.target_root),
             "--stacks", "python", *extra],
            capture_output=True, text=True, timeout=120,
            stdin=subprocess.DEVNULL, env=env,
        )

    def install_toml(self) -> dict:
        path = self.modelb_home / "install.toml"
        self.assertTrue(path.is_file(), "install.toml was not written")
        with open(path, "rb") as fh:
            return tomllib.load(fh)


class SandeshPiRequiredInstallerTest(_InstallerSandboxCase):
    """§S1: a missing ``sandesh-pi`` now fails the pre-flight (required), and
    ``--yes`` still never runs ``pi install`` for it."""

    def test_an_absent_sandesh_pi_fails_the_preflight_naming_its_remediation(self):
        make_provisioned_agent_dir(self.agent_dir, omit=("sandesh-pi",))
        settings_before = (self.agent_dir / "settings.json").read_bytes()
        result = self.run_yes()
        axi = decode_axi(result.stdout)
        self.assertNotEqual(result.returncode, 0, result.stderr)
        self.assertEqual(axi.get("outcome"), "preflight_failed", f"axi={axi!r}")
        self.assertEqual((parse_group_line(result.stderr, "harness:") or {}).get("sandesh-pi"),
                         "absent", result.stderr)
        hits = [w for w in axi.get("warnings", [])
                if "sandesh-pi" in w and SANDESH_PI_REMEDIATION in w]
        self.assertEqual(len(hits), 1, f"one error names sandesh-pi and its remediation; {axi!r}")
        self.assertEqual(_lines(self.pi_log), [], "--yes never runs a third-party `pi install`")
        self.assertEqual((self.agent_dir / "settings.json").read_bytes(), settings_before)
        self.assertFalse((self.modelb_home / "install.toml").exists(),
                         "a failed pre-flight writes no install.toml")

    def test_the_override_proceeds_records_sandesh_pi_absent_and_installs_nothing(self):
        make_provisioned_agent_dir(self.agent_dir, omit=("sandesh-pi",))
        result = self.run_yes("--allow-missing-capabilities")
        axi = decode_axi(result.stdout)
        self.assertEqual((result.returncode, axi.get("outcome")), (0, "installed"), result.stderr)
        self.assertEqual(self.install_toml()["capabilities"].get("sandesh-pi"), "absent")
        self.assertEqual(_lines(self.pi_log), [], "--yes never runs a third-party `pi install`")


class InstallerRecordsTheNewVerdictsTest(_InstallerSandboxCase):
    """§S1 through the real installer entry: ``outdated`` lands in
    ``[deps]`` (and the envelope), ``direnv`` in ``[capabilities]``, and the
    ``worktree`` capability replaces ``watcher`` on the harness line and in
    ``[capabilities]``."""

    def test_an_outdated_sandesh_is_recorded_in_deps_and_reported_with_the_upgrade(self):
        make_provisioned_agent_dir(self.agent_dir)
        write_executable(self.bin_dir, "sandesh", fake_sandesh("0.3.9"))
        result = self.run_yes()
        axi = decode_axi(result.stdout)
        self.assertEqual((result.returncode, axi.get("outcome")), (0, "installed"), result.stderr)
        data = self.install_toml()
        self.assertEqual(data["deps"].get("sandesh"), "outdated", f"[deps]={data['deps']!r}")
        self.assertEqual((axi.get("deps") or {}).get("sandesh"), "outdated", f"axi={axi!r}")
        self.assertTrue([w for w in axi.get("warnings", []) if UPGRADE_SANDESH in w],
                        f"the envelope names `{UPGRADE_SANDESH}`; {axi.get('warnings')!r}")
        self.assertNotIn("tool install sandesh-relay", _lines(self.uv_log),
                         "an outdated sandesh is upgraded, never re-installed")

    def test_direnv_and_worktree_are_recorded_and_watcher_is_not(self):
        make_provisioned_agent_dir(self.agent_dir)
        result = self.run_yes()
        self.assertEqual(result.returncode, 0, result.stderr)
        harness = parse_group_line(result.stderr, "harness:") or {}
        self.assertEqual(harness.get("worktree"), "detected", result.stderr)
        self.assertNotIn("watcher", harness, result.stderr)
        caps = self.install_toml()["capabilities"]
        self.assertEqual((caps.get("worktree"), caps.get("direnv")), ("detected", "absent"), caps)
        self.assertNotIn("watcher", caps)

    def test_yes_installs_an_absent_worktree_package_and_nothing_third_party(self):
        make_provisioned_agent_dir(self.agent_dir, omit=("worktree", "permissions"))
        result = self.run_yes()
        self.assertEqual(decode_axi(result.stdout).get("outcome"), "installed", result.stderr)
        self.assertEqual(_lines(self.pi_log), [f"install npm:{MODELB_PI_PACKAGE}"],
                         "--yes runs Model B's own package install, and only that")
        self.assertEqual((parse_group_line(result.stderr, "harness:") or {}).get("worktree"),
                         "absent", result.stderr)


# ---------------------------------------------------------------------------
# init reads the recorded verdicts
# ---------------------------------------------------------------------------

def _install_toml_text(home: Path, capabilities: dict, deps: dict) -> str:
    lines = [
        "[install]", 'version = "0.1.0"', 'harnesses = ["pi"]',
        f'asset_root = "{home / "no-asset-root-here"}"',
        f'hooks_scripts_dir = "{home / ".agents" / "hooks" / "scripts"}"',
        'stacks = ["python"]', "", "[deps]",
        *(f'{k} = "{v}"' for k, v in deps.items()), "", "[capabilities]",
        *(f'"{k}" = "{v}"' for k, v in capabilities.items()),
    ]
    return "\n".join(lines) + "\n"


class InitReadsTheRecordedVerdictsTest(unittest.TestCase):
    """§S1: ``read_tool_verdicts`` reads a recorded ``watcher`` verdict as
    ``worktree``'s, and ``outdated`` as not present — driven through
    ``run_init`` in process against a sandboxed ``install.toml``."""

    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="modelb-cr047-init-")).resolve()
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.modelb_home = self.root / "modelb-home"
        self.modelb_home.mkdir()
        self.home = make_home(self.root / "home", crucible_manifest=False)
        self.agent_dir = make_agent_dir(self.root / "pi-agent", packages=[], on_disk=())

    def verdicts(self) -> dict:
        from modelb_axi.requirements import REQUIREMENTS, STACK_TOOLCHAINS
        caps = {r["id"]: "detected" for r in REQUIREMENTS if r["scope"] == "always"}
        caps["python.client"] = "detected"
        for probe in STACK_TOOLCHAINS["python"]:
            caps[f"python.{probe['name']}"] = "detected"
        return caps

    def run_init(self, capabilities: dict, deps: dict) -> tuple[dict, str]:
        from modelb_axi import scaffold
        (self.modelb_home / "install.toml").write_text(
            _install_toml_text(self.modelb_home, capabilities, deps), encoding="utf-8")
        args = argparse.Namespace(
            name="Floor Project", token=PROJECT_SHORT_NAME, acronym="FLR", mode="solo",
            repo_shape="standalone", stacks="python", owner="tester",
            target=str(self.root / "proj"), dry_run=True, no_commit=True, register=False,
        )
        out, err = io.StringIO(), io.StringIO()
        with (mock.patch.dict(os.environ, {"HOME": str(self.home),
                                           AGENT_DIR_ENV: str(self.agent_dir)}),
              contextlib.redirect_stdout(out), contextlib.redirect_stderr(err)):
            rc = scaffold.run_init(args, self.modelb_home)
        axi = decode_axi(out.getvalue())
        self.assertEqual((rc, axi.get("ok")), (0, True), f"init must succeed; err={err.getvalue()!r}")
        return axi.get("tools") or {}, err.getvalue()

    def pre_047_verdicts(self, watcher: str) -> dict:
        """``[capabilities]`` as an installation before CR-MDB-047 recorded it:
        a ``watcher`` key, no ``worktree`` or ``direnv`` key."""
        caps = {k: v for k, v in self.verdicts().items() if k not in ("worktree", "direnv")}
        caps["watcher"] = watcher
        return caps

    def test_a_recorded_watcher_verdict_is_read_as_the_worktree_verdict(self):
        tools, err = self.run_init(self.pre_047_verdicts("detected"),
                                   {"uv": "detected", "sandesh": "detected", "crucible": "detected"})
        self.assertEqual(tools.get("worktree"), "present", tools)
        self.assertNotIn("watcher", tools, "the tools map names the worktree row only")
        notes = [ln for ln in err.splitlines() if "records no verdict" in ln]
        self.assertFalse(any("worktree" in ln for ln in notes),
                         f"a recorded watcher verdict leaves worktree recorded; err={err!r}")

    def test_a_recorded_absent_watcher_reads_as_an_absent_worktree(self):
        tools, _err = self.run_init(self.pre_047_verdicts("absent"),
                                    {"uv": "detected", "sandesh": "detected", "crucible": "detected"})
        self.assertEqual(tools.get("worktree"), "absent", tools)

    def test_read_tool_verdicts_maps_watcher_to_worktree(self):
        from modelb_axi import scaffold
        install = {"capabilities": self.pre_047_verdicts("installed"),
                   "deps": {"uv": "detected", "sandesh": "detected", "crucible": "detected"}}
        tools, unrecorded = scaffold.read_tool_verdicts(install, ["python"])
        self.assertEqual(tools.get("worktree"), "present", tools)
        self.assertNotIn("worktree", unrecorded, unrecorded)

    def test_an_outdated_sandesh_is_read_as_not_present(self):
        caps = self.verdicts()
        caps["sandesh"] = "outdated"
        tools, err = self.run_init(caps, {"uv": "detected", "sandesh": "outdated",
                                          "crucible": "detected"})
        self.assertIn(tools.get("sandesh"), ("absent", "unknown"), tools)
        self.assertNotEqual(tools.get("sandesh"), "present", tools)


if __name__ == "__main__":
    unittest.main()
