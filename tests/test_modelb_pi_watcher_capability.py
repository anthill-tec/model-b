"""The ``watcher`` capability — Model B's own Pi package declared, probed,
offered and recorded by the installer (CR-MDB-029 §S3).

- ``REQUIREMENTS`` carries a tier-1 ``watcher`` row: provider
  ``@anthill-tec/modelb-pi``, policy ``recommended``, scope ``always``, the
  orchestration skills as dependents, tools ``["sandesh_watcher"]``,
  remediation ``pi install npm:@anthill-tec/modelb-pi``.
- The harness probe reports ``watcher=<verdict>`` on the ``harness:`` line
  like the other tier-1 capabilities (listed in ``settings.json``
  ``packages[]`` AND on disk under ``npm/node_modules``).
- With ``pi`` among the harnesses and the package absent the installer
  offers ``pi install npm:@anthill-tec/modelb-pi``; an interactive
  confirmation OR ``--yes`` runs it (user ruling: Model B's own package,
  like Sandesh — unlike the third-party extensions, which ``--yes`` never
  confirms: see ``NoThirdPartyInstallUnderYesTest``). Its output goes to the
  terminal, the capability is re-probed before ``installed`` is recorded,
  an already-listed package runs nothing, and Model B never writes
  ``settings.json`` (only the ``pi`` shim — standing for Pi — does).

Isolation (NON-NEGOTIABLE): every run pins ``HOME``, ``PATH`` (a fake-bin
dir), ``PI_CODING_AGENT_DIR``, ``MODELB_HOME`` and ``XDG_DATA_HOME`` to the
per-test sandbox and passes ``--modelb-home``/``--target-root`` naming it;
``pi`` is a recording shim. The real ``~/.pi``, ``~/.crucible`` and
``~/.local/share/modelb`` are never read or written.

Stdlib only.
"""

import os
import shutil
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path

from tests._helpers import decode_axi as _decode
from tests._helpers import write_executable as _write_exe
from tests.pi_capability_sandbox import (
    AGENT_DIR_ENV,
    MODELB_PI_PACKAGE,
    make_home,
    make_provisioned_agent_dir,
    npm_spec,
    parse_group_line,
)

REPO_ROOT = Path(__file__).resolve().parent.parent

WATCHER_INSTALL = f"pi install npm:{MODELB_PI_PACKAGE}"
WATCHER_PI_ARGS = f"install npm:{MODELB_PI_PACKAGE}"

_FAKE_UV = "#!/bin/sh\necho uv-fake\nexit 0\n"
_FAKE_OK = "#!/bin/sh\nexit 0\n"


def _watcher_row() -> dict:
    from modelb_axi.requirements import REQUIREMENTS
    rows = [r for r in REQUIREMENTS if r.get("id") == "watcher"]
    if len(rows) != 1:
        raise AssertionError(
            f"CR-MDB-029 §S3: exactly one `watcher` requirement row expected; "
            f"found {len(rows)}"
        )
    return rows[0]

# ---------------------------------------------------------------------------
# The declared row
# ---------------------------------------------------------------------------

class WatcherRequirementRowTest(unittest.TestCase):
    """§S3 AC1 (first half): ``REQUIREMENTS`` carries the ``watcher`` row
    with the §S3 fields, exactly."""

    def test_watcher_row_is_tier1_recommended_always_scoped(self):
        row = _watcher_row()
        self.assertEqual(
            (row["tier"], row["policy"], row["scope"]), (1, "recommended", "always"), row,
        )

    def test_watcher_provider_is_model_bs_own_npm_package(self):
        self.assertEqual(_watcher_row()["provider"], "@anthill-tec/modelb-pi")

    def test_watcher_remediation_is_exactly_the_pi_install_command(self):
        self.assertEqual(
            _watcher_row()["remediation"], "pi install npm:@anthill-tec/modelb-pi",
        )

    def test_watcher_tools_are_exactly_sandesh_watcher(self):
        self.assertEqual(list(_watcher_row()["tools"]), ["sandesh_watcher"])

    def test_watcher_dependents_are_the_orchestration_skills(self):
        self.assertEqual(list(_watcher_row()["asset_families"]), ["orchestration skills"])

    def test_watcher_is_probed_as_a_pi_package_like_the_other_tier1_rows(self):
        """"reports it like the other tier-1 capabilities" — the same probe
        kind as dispatch/lean-ctx/permissions."""
        from modelb_axi.requirements import REQUIREMENTS
        kinds = {r["id"]: r.get("probe") for r in REQUIREMENTS if r["tier"] == 1}
        self.assertEqual(
            kinds,
            {"dispatch": "pi-package", "lean-ctx": "pi-package",
             "permissions": "pi-package", "watcher": "pi-package"},
        )

# ---------------------------------------------------------------------------
# Sandbox
# ---------------------------------------------------------------------------

class _WatcherSandboxCase(unittest.TestCase):
    """Per-test sandbox: MODELB_HOME, target root, XDG_DATA_HOME, fake-bin
    PATH (``uv``, ``sandesh``, a succeeding ``python3``), a Crucible-less
    HOME, and an agent dir. ``pi`` is a recording shim added per test."""

    def setUp(self):
        self._root = Path(tempfile.mkdtemp(prefix="modelb-cr029-watcher-")).resolve()
        self.addCleanup(shutil.rmtree, self._root, ignore_errors=True)
        self.modelb_home = self._root / "modelb-home"
        self.target_root = self._root / "target"
        self.xdg_data = self._root / "xdg-data"
        self.bin_dir = self._root / "bin"
        self.agent_dir = self._root / "agent"
        self.pi_marker = self._root / "pi-ran"
        for d in (self.modelb_home, self.target_root, self.xdg_data, self.bin_dir):
            d.mkdir(parents=True)
        self.home = make_home(self._root / "home", crucible_manifest=False)
        _write_exe(self.bin_dir, "uv", _FAKE_UV)
        _write_exe(self.bin_dir, "sandesh", _FAKE_OK)
        _write_exe(self.bin_dir, "python3", _FAKE_OK)

    # -- fixtures ---------------------------------------------------------

    def agent_without_watcher(self) -> Path:
        """Every third-party tier-1 extension listed and on disk; Model B's
        own package neither listed nor on disk."""
        return make_provisioned_agent_dir(self.agent_dir, omit=("watcher",))

    def agent_listing_missing_watcher(self) -> bytes:
        """Model B's own package LISTED in ``settings.json`` but missing from
        disk (VERIFY finding 4, the C3 amendment). Returns the settings bytes."""
        import json
        make_provisioned_agent_dir(self.agent_dir, omit=("watcher",))
        settings = json.loads(self.settings_bytes())
        settings["packages"].append(npm_spec(MODELB_PI_PACKAGE))
        (self.agent_dir / "settings.json").write_text(json.dumps(settings), encoding="utf-8")
        return self.settings_bytes()

    def recording_pi(self, extra: str = "") -> None:
        """A ``pi`` shim recording ``$*`` per run, then running ``extra``."""
        _write_exe(self.bin_dir, "pi", (
            "#!/bin/sh\n"
            f'printf \'%s\\n\' "$*" >> "{self.pi_marker}"\n'
            f"{extra}"
            "exit 0\n"
        ))

    def provisioning_pi(self) -> Path:
        """A ``pi`` shim that, like Pi, lists AND materialises every tier-1
        package (copying a fully provisioned agent dir over the sandbox's).
        Returns the settings.json it writes, for byte comparison."""
        provisioned = make_provisioned_agent_dir(self._root / "provisioned")
        cp = shutil.which("cp")
        if cp is None:
            self.fail("cp is required to build the provisioning pi shim")
        self.recording_pi(f'{cp} -R "{provisioned}/." "{self.agent_dir}/"\n')
        return provisioned / "settings.json"

    def pi_runs(self) -> list[str]:
        if not self.pi_marker.exists():
            return []
        return [ln for ln in self.pi_marker.read_text(encoding="utf-8").splitlines() if ln]

    # -- runners ----------------------------------------------------------

    def sandbox_env(self) -> dict:
        return {
            "HOME": str(self.home),
            "PATH": str(self.bin_dir),
            AGENT_DIR_ENV: str(self.agent_dir),
            "MODELB_HOME": str(self.modelb_home),
            "XDG_DATA_HOME": str(self.xdg_data),
        }

    def subprocess_env(self) -> dict:
        env = dict(os.environ)
        env.pop("MODELB_TARGET_ROOT", None)
        existing_pp = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = str(REPO_ROOT) + (os.pathsep + existing_pp if existing_pp else "")
        env.update(self.sandbox_env())
        return env

    def installer_args(self, harnesses: str = "pi", *extra) -> list[str]:
        return ["--harnesses", harnesses, "--modelb-home", str(self.modelb_home),
                "--target-root", str(self.target_root), "--stacks", "python", *extra]

    def run_yes(self, harnesses: str = "pi", *extra):
        return subprocess.run(
            [sys.executable, "-m", "modelb_axi", "--yes", *self.installer_args(harnesses, *extra)],
            capture_output=True, text=True, timeout=60,
            stdin=subprocess.DEVNULL, env=self.subprocess_env(),
        )

    def run_interactive(self, answer: str):
        from tests.scripted_terminal import make_responder, run_installer_interactive
        responder = make_responder([(lambda chunk: WATCHER_INSTALL in chunk, answer)])
        return run_installer_interactive(self.installer_args(), self.sandbox_env(), responder)

    # -- observations -----------------------------------------------------

    def harness_line(self, stderr: str) -> dict:
        verdicts = parse_group_line(stderr, "harness:")
        if verdicts is None:
            self.fail(f"no `harness:` line on stderr; stderr={stderr!r}")
        return verdicts

    def capabilities(self) -> dict:
        with open(self.modelb_home / "install.toml", "rb") as fh:
            return tomllib.load(fh).get("capabilities", {})

    def settings_bytes(self) -> bytes:
        return (self.agent_dir / "settings.json").read_bytes()

# ---------------------------------------------------------------------------
# The probe reports it
# ---------------------------------------------------------------------------

class WatcherHarnessProbeTest(_WatcherSandboxCase):
    """§S3 AC1 (second half): the harness probe reports ``watcher=`` on the
    ``harness:`` line, judged like the other tier-1 capabilities. No ``pi``
    on PATH here, so nothing can be installed."""

    def test_listed_and_on_disk_reports_watcher_detected_and_records_it(self):
        make_provisioned_agent_dir(self.agent_dir)
        result = self.run_yes()
        self.assertEqual(self.harness_line(result.stderr).get("watcher"), "detected",
                         result.stderr)
        self.assertEqual(_decode(result.stdout).get("outcome"), "installed", result.stderr)
        self.assertEqual(self.capabilities().get("watcher"), "detected")

    def test_unlisted_reports_watcher_absent_warns_and_continues(self):
        self.agent_without_watcher()
        result = self.run_yes()
        self.assertEqual(self.harness_line(result.stderr).get("watcher"), "absent",
                         result.stderr)
        axi = _decode(result.stdout)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(axi.get("outcome"), "installed",
                         f"recommended: a missing watcher never fails the pre-flight; {axi!r}")
        hits = [w for w in axi.get("warnings", []) if "watcher" in w and WATCHER_INSTALL in w]
        self.assertTrue(hits, f"the absent watcher WARNs naming `{WATCHER_INSTALL}`; {axi!r}")
        self.assertEqual(self.capabilities().get("watcher"), "absent")

    def test_listed_but_not_on_disk_reports_watcher_absent(self):
        make_provisioned_agent_dir(self.agent_dir, omit=("watcher",))
        import json
        settings = json.loads(self.settings_bytes())
        settings["packages"].append(npm_spec(MODELB_PI_PACKAGE))
        (self.agent_dir / "settings.json").write_text(json.dumps(settings), encoding="utf-8")
        result = self.run_yes()
        self.assertEqual(self.harness_line(result.stderr).get("watcher"), "absent",
                         result.stderr)

# ---------------------------------------------------------------------------
# --yes runs Model B's own pi install
# ---------------------------------------------------------------------------

class WatcherInstallUnderYesTest(_WatcherSandboxCase):
    """§S3 AC2: with the package absent, ``--yes`` runs
    ``pi install npm:@anthill-tec/modelb-pi`` exactly once (shim), the
    verdict is re-probed, and ``settings.json`` is never written by Model
    B — all against a sandboxed ``PI_CODING_AGENT_DIR``."""

    def test_yes_runs_the_install_once_and_a_reprobe_that_finds_it_records_installed(self):
        self.agent_without_watcher()
        pi_written = self.provisioning_pi()
        result = self.run_yes()
        self.assertEqual(self.pi_runs(), [WATCHER_PI_ARGS],
                         f"exactly one pi install of Model B's own package; stderr={result.stderr!r}")
        self.assertEqual(self.harness_line(result.stderr).get("watcher"), "absent",
                         "the harness: line reports the pre-install verdict")
        axi = _decode(result.stdout)
        self.assertEqual(axi.get("outcome"), "installed", result.stderr)
        self.assertEqual(self.capabilities().get("watcher"), "installed",
                         "re-probed: Pi now loads it, so `installed` is recorded")
        self.assertEqual(self.settings_bytes(), pi_written.read_bytes(),
                         "settings.json holds exactly what Pi wrote — never a Model B edit")
        self.assertFalse([w for w in axi.get("warnings", []) if w.startswith("watcher=")],
                         f"an installed watcher draws no policy warning; {axi!r}")

    def test_yes_install_the_reprobe_does_not_find_records_absent_naming_where(self):
        self.agent_without_watcher()
        before = self.settings_bytes()
        self.recording_pi()
        result = self.run_yes()
        self.assertEqual(self.pi_runs(), [WATCHER_PI_ARGS], result.stderr)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.capabilities().get("watcher"), "absent",
                         "no `installed` without the re-probe finding it")
        self.assertEqual(self.settings_bytes(), before, "Model B never writes settings.json")
        axi = _decode(result.stdout)
        hits = [w for w in axi.get("warnings", [])
                if MODELB_PI_PACKAGE in w and "settings.json" in w and "node_modules" in w]
        self.assertEqual(len(hits), 1,
                         f"one warning naming where Pi was expected to load it; {axi!r}")

    def test_already_listed_package_runs_nothing(self):
        make_provisioned_agent_dir(self.agent_dir)
        before = self.settings_bytes()
        self.recording_pi()
        result = self.run_yes()
        self.assertEqual(_decode(result.stdout).get("outcome"), "installed", result.stderr)
        self.assertEqual(self.pi_runs(), [], "an already-listed package runs nothing")
        self.assertEqual(self.capabilities().get("watcher"), "detected")
        self.assertEqual(self.settings_bytes(), before)

    def test_yes_installs_a_package_listed_but_missing_from_disk(self):
        # C3 amendment / VERIFY finding 4: listed in settings.json but not
        # on disk is absent, so --yes installs it and the re-probe records it.
        self.agent_listing_missing_watcher()
        pi_written = self.provisioning_pi()
        result = self.run_yes()
        self.assertEqual(self.harness_line(result.stderr).get("watcher"), "absent", result.stderr)
        self.assertEqual(self.pi_runs(), [WATCHER_PI_ARGS],
                         f"a listed-but-missing package is installed under --yes; stderr={result.stderr!r}")
        self.assertEqual(self.capabilities().get("watcher"), "installed")
        self.assertEqual(self.settings_bytes(), pi_written.read_bytes(),
                         "settings.json holds exactly what Pi wrote — never a Model B edit")

    def test_yes_runs_only_model_bs_own_install_never_a_third_party_one(self):
        """The separation: third-party extensions missing too, ``--yes``
        runs the watcher install and nothing else."""
        make_provisioned_agent_dir(self.agent_dir, omit=("watcher", "permissions"))
        self.recording_pi()
        result = self.run_yes()
        self.assertEqual(_decode(result.stdout).get("outcome"), "installed", result.stderr)
        self.assertEqual(self.pi_runs(), [WATCHER_PI_ARGS],
                         "--yes never confirms a third-party pi install")

    def test_install_output_goes_to_the_users_terminal_not_a_capture(self):
        """The child's stdout is the user's terminal (``[ -t 1 ]``), never a
        capture re-printed later; the envelope on stdout stays clean. Driven
        through a pseudo-terminal carrying stdin and stderr."""
        import pty
        import threading
        self.agent_without_watcher()
        self.recording_pi(
            'if [ -t 1 ]; then echo "CHILD-STDOUT-ON-TERMINAL pi"; '
            'else echo "CHILD-STDOUT-CAPTURED pi"; fi\n'
            'echo "CHILD-STDERR pi" >&2\n'
        )
        master, slave = pty.openpty()
        proc = subprocess.Popen(
            [sys.executable, "-m", "modelb_axi", "--yes", *self.installer_args()],
            stdin=slave, stdout=subprocess.PIPE, stderr=slave,
            env=self.subprocess_env(), close_fds=True,
        )
        os.close(slave)
        chunks: list[bytes] = []

        def pump():
            while True:
                try:
                    data = os.read(master, 4096)
                except OSError:
                    return
                if not data:
                    return
                chunks.append(data)

        reader = threading.Thread(target=pump, daemon=True)
        reader.start()
        try:
            stdout, _ = proc.communicate(timeout=60)
        finally:
            reader.join(timeout=10)
            os.close(master)
        terminal = b"".join(chunks).decode(errors="replace")
        stdout = stdout.decode()
        self.assertEqual(self.pi_runs(), [WATCHER_PI_ARGS], f"terminal={terminal!r}")
        self.assertIn("CHILD-STDOUT-ON-TERMINAL pi", terminal)
        self.assertNotIn("CHILD-STDOUT-CAPTURED", terminal + stdout)
        self.assertIn("CHILD-STDERR pi", terminal)
        self.assertNotIn("CHILD-", stdout, "stdout carries only the envelope")
        self.assertEqual(_decode(stdout).get("outcome"), "installed", terminal)

# ---------------------------------------------------------------------------
# Interactive: confirmation runs it, a decline is recorded
# ---------------------------------------------------------------------------

class WatcherInteractiveOfferTest(_WatcherSandboxCase):
    """§S3: interactively the installer OFFERS
    ``pi install npm:@anthill-tec/modelb-pi`` (once) and a confirmation runs
    it; a decline runs nothing and is recorded. Scripted TTY, in-process."""

    def test_confirmation_runs_the_offered_install_once(self):
        self.agent_without_watcher()
        before = self.settings_bytes()
        self.recording_pi()
        result = self.run_interactive("y")
        self.assertEqual(len(result.offers_naming(WATCHER_INSTALL)), 1,
                         f"one offer naming `{WATCHER_INSTALL}`; reads={result.reads!r}")
        self.assertEqual(self.pi_runs(), [WATCHER_PI_ARGS], result.stderr)
        self.assertEqual(self.settings_bytes(), before, "Model B never writes settings.json")

    def test_decline_runs_nothing_and_is_recorded(self):
        self.agent_without_watcher()
        self.recording_pi()
        result = self.run_interactive("n")
        self.assertEqual(len(result.offers_naming(WATCHER_INSTALL)), 1,
                         f"precondition: the install was offered; reads={result.reads!r}")
        self.assertEqual(self.pi_runs(), [], "a declined install runs nothing")
        axi = _decode(result.stdout)
        self.assertEqual(axi.get("outcome"), "installed", result.stderr)
        declined = [w for w in axi.get("warnings", [])
                    if "declin" in w.lower() and WATCHER_INSTALL in w]
        self.assertEqual(len(declined), 1, f"one decline warning; {axi!r}")
        self.assertEqual(self.capabilities().get("watcher"), "absent")

    def test_already_listed_package_is_not_offered(self):
        make_provisioned_agent_dir(self.agent_dir)
        self.recording_pi()
        result = self.run_interactive("y")
        self.assertEqual(result.offers_naming(WATCHER_INSTALL), [], result.stderr)
        self.assertEqual(self.pi_runs(), [])
        self.assertEqual(self.capabilities().get("watcher"), "detected")

    def test_listed_but_missing_from_disk_is_offered_like_an_absent_one(self):
        # C3 amendment / VERIFY finding 4: a listed-but-missing package
        # probes absent and is OFFERED; confirming runs the install once.
        before = self.agent_listing_missing_watcher()
        self.recording_pi()
        result = self.run_interactive("y")
        self.assertEqual(len(result.offers_naming(WATCHER_INSTALL)), 1,
                         f"one offer naming `{WATCHER_INSTALL}`; reads={result.reads!r}")
        self.assertEqual(self.pi_runs(), [WATCHER_PI_ARGS], result.stderr)
        self.assertEqual(self.settings_bytes(), before, "Model B never writes settings.json")

if __name__ == "__main__":
    unittest.main()
