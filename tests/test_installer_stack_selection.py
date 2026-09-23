"""Installer stack selection and per-stack toolchain probes
(CR-MDB-036 §S7, §S8, and the §S4 ``"<stack>.<probe>"`` verdict keys).

- §S7: ``--stacks CSV`` (``init``'s vocabulary) scopes the
  ``crucible-report-*`` bundles; omitting it selects all; interactively the
  list is offered; the selection round-trips through ``install.toml`` and
  a wider re-run adds only the new stack's bundle.
- §S8: only selected stacks are probed, by ``shutil.which`` resolution —
  never execution — except python's ``xmlrunner``/``coverage`` checked by
  the PATH ``python3 -c "import …"``; an absent toolchain WARNs, records
  ``absent`` and names the provider's installer; a provider installer runs
  only on an explicit interactive yes, never under ``--yes``, and never
  when it needs elevated privileges.
- §S4: each selected stack's verdicts land in ``[capabilities]`` under
  quoted ``"<stack>.<probe>"`` keys (``"<stack>.client"`` for Crucible).

Isolation (NON-NEGOTIABLE): every run pins ``HOME`` (a sandbox with or
without Crucible's manifest), ``PATH`` (a fake-bin dir of recording
shims — every toolchain binary here records any EXECUTION in a marker
file) and ``PI_CODING_AGENT_DIR`` (a provisioned sandbox agent dir). The
real ``~/.pi``, ``~/.crucible`` and toolchains are never touched.

Stdlib only.
"""

import json
import os
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
    parse_group_line,
)
from tests.scripted_terminal import make_responder, run_installer_interactive

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS_SRC = REPO_ROOT / "skills-src"

#: ``init``'s stack vocabulary (§S7).
ALL_STACKS = ("arduino", "bun", "python", "quarkus", "rust", "java")

#: §S8 table: stack -> the binaries/modules probed, in table order.
STACK_PROBES = {
    "python": ("python3", "xmlrunner", "coverage"),
    "rust": ("cargo", "cargo-nextest", "cargo-llvm-cov"),
    "quarkus": ("mvn", "java"),
    "java": ("mvn", "java"),
    "bun": ("bun", "node"),
    "arduino": ("arduino-cli", "g++"),
}

#: Every toolchain BINARY in the §S8 table (xmlrunner/coverage are modules).
TOOLCHAIN_BINARIES = (
    "cargo", "cargo-nextest", "cargo-llvm-cov", "mvn", "java",
    "bun", "node", "arduino-cli", "g++",
)

#: Installers that need elevated privileges — named, never run (§S8).
ELEVATED_INSTALLERS = (
    "sudo", "pkexec", "doas", "apt", "apt-get", "dnf", "yum", "pacman", "zypper",
)

_FAKE_UV = (
    "#!/bin/sh\n"
    'if [ "$1" = "tool" ] && [ "$2" = "install" ]; then exit 0; fi\n'
    'echo "uv 0.0.0-fake"\n'
    "exit 0\n"
)
_FAKE_SANDESH = "#!/bin/sh\necho sandesh-fake\nexit 0\n"

def _recording_shim(marker: Path, exit_code: int = 0) -> str:
    """A fake binary that appends ``<name> <args>`` to ``marker`` on every
    EXECUTION, then exits ``exit_code``."""
    return (
        "#!/bin/sh\n"
        f'printf \'%s %s\\n\' "${{0##*/}}" "$*" >> "{marker}"\n'
        f"exit {exit_code}\n"
    )

def _write_exe(bin_dir: Path, name: str, body: str) -> Path:
    path = Path(bin_dir) / name
    path.write_text(body, encoding="utf-8")
    path.chmod(0o755)
    return path

def _decode(stdout: str) -> dict:
    from modelb_axi.toon import decode
    try:
        return decode(stdout).get("axi", {})
    except Exception:  # noqa: BLE001 — a non-envelope stdout fails the caller's asserts
        return {}

def _report_bundles() -> set[str]:
    return {
        p.name for p in SKILLS_SRC.iterdir()
        if p.is_dir() and p.name.startswith("crucible-report-") and (p / "SKILL.md").is_file()
    }

def _always_bundles() -> set[str]:
    return {
        p.name for p in SKILLS_SRC.iterdir()
        if p.is_dir() and not p.name.startswith("crucible-report-")
        and (p / "SKILL.md").is_file()
    }

# Wraps the installer so every shutil.which / subprocess.Popen call is
# logged BEFORE modelb_axi is imported (so a `from shutil import which`
# in any module is covered too). The log path comes from the env.
_COUNTING_WRAPPER = r"""
import atexit, json, os, shutil, subprocess, sys
_log = {"which": [], "popen": []}
_orig_which = shutil.which
def _which(cmd, *a, **k):
    _log["which"].append(str(cmd))
    return _orig_which(cmd, *a, **k)
shutil.which = _which
_OrigPopen = subprocess.Popen
class _Popen(_OrigPopen):
    def __init__(self, args, *a, **k):
        _log["popen"].append(args if isinstance(args, str) else [str(x) for x in args])
        super().__init__(args, *a, **k)
subprocess.Popen = _Popen
_path = os.environ["MODELB_TEST_PROBE_LOG"]
def _dump():
    with open(_path, "w", encoding="utf-8") as fh:
        json.dump(_log, fh)
atexit.register(_dump)
from modelb_axi.cli import main
sys.exit(main(sys.argv[1:]))
"""

class _StackSandboxCase(unittest.TestCase):
    """Per-test sandbox: MODELB_HOME, target root, fake-bin PATH (uv +
    sandesh), sandbox HOME without a Crucible manifest, provisioned agent
    dir (all tier-1 capabilities detected)."""

    def setUp(self):
        self._root = Path(tempfile.mkdtemp(prefix="modelb-cr036-stacks-"))
        self.modelb_home = self._root / "modelb-home"
        self.target_root = self._root / "target"
        self.bin_dir = self._root / "bin"
        self.home = self._root / "home"
        self.agent_dir = self._root / "agent"
        self.marker = self._root / "executed"
        for d in (self.modelb_home, self.target_root, self.bin_dir):
            d.mkdir(parents=True)
        make_home(self.home, crucible_manifest=False)
        make_provisioned_agent_dir(self.agent_dir)
        _write_exe(self.bin_dir, "uv", _FAKE_UV)
        _write_exe(self.bin_dir, "sandesh", _FAKE_SANDESH)

    def tearDown(self):
        shutil.rmtree(self._root, ignore_errors=True)

    # -- fixtures ---------------------------------------------------------

    def shim(self, *names, exit_code: int = 0):
        for name in names:
            _write_exe(self.bin_dir, name, _recording_shim(self.marker, exit_code))

    def executions(self) -> list[str]:
        if not self.marker.exists():
            return []
        return [ln for ln in self.marker.read_text(encoding="utf-8").splitlines() if ln.strip()]

    def sandbox_env(self) -> dict:
        return {
            "HOME": str(self.home),
            "PATH": str(self.bin_dir),
            AGENT_DIR_ENV: str(self.agent_dir),
        }

    # -- runners ----------------------------------------------------------

    def _subprocess_env(self, extra=None) -> dict:
        env = dict(os.environ)
        env.pop(AGENT_DIR_ENV, None)
        env.pop("MODELB_HOME", None)
        env.pop("MODELB_TARGET_ROOT", None)
        existing_pp = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = str(REPO_ROOT) + (os.pathsep + existing_pp if existing_pp else "")
        env.update(self.sandbox_env())
        env.update(extra or {})
        return env

    def _installer_args(self, *extra) -> list[str]:
        return ["--harnesses", "pi", "--modelb-home", str(self.modelb_home),
                "--target-root", str(self.target_root), *extra]

    def run_installer(self, *extra):
        """A ``--yes`` subprocess run (stdin is /dev/null)."""
        return subprocess.run(
            [sys.executable, "-m", "modelb_axi", "--yes", *self._installer_args(*extra)],
            capture_output=True, text=True, timeout=60,
            stdin=subprocess.DEVNULL, env=self._subprocess_env(),
        )

    def run_counting(self, *extra):
        """A ``--yes`` subprocess run logging every ``shutil.which`` name
        and every ``subprocess.Popen`` argv. Returns ``(result, log)``."""
        log_path = self._root / "probe-log.json"
        result = subprocess.run(
            [sys.executable, "-c", _COUNTING_WRAPPER, "--yes", *self._installer_args(*extra)],
            capture_output=True, text=True, timeout=60, stdin=subprocess.DEVNULL,
            env=self._subprocess_env({"MODELB_TEST_PROBE_LOG": str(log_path)}),
        )
        if not log_path.exists():
            self.fail(f"probe log not written; exit={result.returncode} stderr={result.stderr!r}")
        return result, json.loads(log_path.read_text(encoding="utf-8"))

    def run_interactive(self, responder, *extra):
        return run_installer_interactive(self._installer_args(*extra), self.sandbox_env(), responder)

    # -- readers ----------------------------------------------------------

    def install_toml(self) -> dict:
        path = self.modelb_home / "install.toml"
        if not path.is_file():
            self.fail(f"install.toml not written under {self.modelb_home}")
        with open(path, "rb") as fh:
            return tomllib.load(fh)

    def deployed_bundles(self) -> set[str]:
        store = self.target_root / ".agents" / "skills"
        return {p.name for p in store.iterdir() if p.is_dir()} if store.is_dir() else set()

    def stack_lines(self, stderr: str) -> list[str]:
        return [ln.strip() for ln in stderr.splitlines() if ln.strip().startswith("stack ")]

    def stack_group(self, stderr: str, stack: str) -> dict:
        verdicts = parse_group_line(stderr, f"stack {stack}:")
        if verdicts is None:
            self.fail(f"§S3: no `stack {stack}:` line on stderr; stderr={stderr!r}")
        return verdicts

    def assert_installed(self, result):
        axi = _decode(result.stdout)
        self.assertEqual(
            result.returncode, 0,
            f"exit={result.returncode} stdout={result.stdout!r} stderr={result.stderr!r}",
        )
        self.assertEqual(axi.get("outcome"), "installed", f"axi={axi!r}")
        return axi

def _declined_record(axi: dict, toml_text: str, name: str) -> bool:
    """A decline naming ``name`` is recorded in the envelope warnings or
    in install.toml (§S3/§S8: "declining is recorded")."""
    in_warnings = any(
        "declin" in w.lower() and name in w for w in axi.get("warnings", [])
    )
    in_toml = "declin" in toml_text.lower() and name in toml_text
    return in_warnings or in_toml

# ---------------------------------------------------------------------------
# §S7 — a stack selector on the installer
# ---------------------------------------------------------------------------

class StackSelectorBundleScopeTest(_StackSandboxCase):
    """§S7 AC1/AC2: ``--stacks`` scopes the ``crucible-report-*`` bundles;
    every other bundle, the hook scripts and the tool scripts always
    deploy; no agent definition is written."""

    def _assert_always_assets_deployed(self):
        bundles = self.deployed_bundles()
        missing = sorted(_always_bundles() - bundles)
        self.assertEqual(missing, [], f"§S7: non-report bundles always deploy; missing {missing}")
        hooks = {p.name for p in (REPO_ROOT / "hooks-src" / "scripts").iterdir() if p.is_file()}
        deployed_hooks = {
            p.name for p in (self.target_root / ".agents" / "hooks" / "scripts").glob("*")
        }
        self.assertEqual(sorted(hooks - deployed_hooks), [], "§S7: hook scripts always deploy")
        tools = {p.name for p in (REPO_ROOT / "scripts").iterdir() if p.is_file()}
        deployed_tools = {p.name for p in (self.target_root / ".agents" / "scripts").glob("*")}
        self.assertEqual(sorted(tools - deployed_tools), [], "§S7: tool scripts always deploy")

    def _assert_no_agent_definitions(self):
        written = [
            str(p.relative_to(self.target_root)) for p in self.target_root.rglob("*")
            if p.name.endswith("-agent.md") or (p.is_dir() and p.name == "agents")
        ]
        self.assertEqual(written, [], "§S7: the installer deploys no agent definitions (DN §D17)")
        manifest = [f["path"] for f in self.install_toml().get("files", [])]
        self.assertEqual([m for m in manifest if m.endswith("-agent.md")], [])

    def _report_bundles_for(self, stacks_csv: str) -> set[str]:
        result = self.run_installer("--stacks", stacks_csv)
        self.assert_installed(result)
        self._assert_always_assets_deployed()
        self._assert_no_agent_definitions()
        return {b for b in self.deployed_bundles() if b.startswith("crucible-report-")}

    def test_python_selection_deploys_only_the_python_report_bundle(self):
        self.assertEqual(self._report_bundles_for("python"), {"crucible-report-python"})

    def test_quarkus_selection_deploys_the_java_report_bundle(self):
        self.assertEqual(self._report_bundles_for("quarkus"), {"crucible-report-java"})

    def test_java_selection_deploys_the_java_report_bundle(self):
        self.assertEqual(self._report_bundles_for("java"), {"crucible-report-java"})

    def test_rust_and_bun_selection_deploys_exactly_their_two_report_bundles(self):
        self.assertEqual(
            self._report_bundles_for("rust,bun"),
            {"crucible-report-rust", "crucible-report-bun"},
        )

    def test_selection_scopes_the_manifest_not_just_the_tree(self):
        self.assert_installed(self.run_installer("--stacks", "python"))
        report_paths = {
            f["path"].split("/")[2] for f in self.install_toml().get("files", [])
            if f["path"].startswith(".agents/skills/crucible-report-")
        }
        self.assertEqual(report_paths, {"crucible-report-python"})

    def test_omitting_stacks_selects_all_and_deploys_every_report_bundle(self):
        """Regression pin: current behaviour unchanged when ``--stacks``
        is omitted (would fail if the default narrowed)."""
        result = self.run_installer()
        self.assert_installed(result)
        self.assertEqual(
            {b for b in self.deployed_bundles() if b.startswith("crucible-report-")},
            _report_bundles(),
        )
        self.assertEqual(sorted(self.install_toml()["install"]["stacks"]), sorted(ALL_STACKS))
        self._assert_always_assets_deployed()

class StackSelectorValidationTest(_StackSandboxCase):
    """§S7 AC1: ``init``'s vocabulary is accepted; an unsupported name is
    rejected with a message listing the supported stacks."""

    def test_every_init_stack_name_is_accepted_together(self):
        result = self.run_installer("--stacks", ",".join(ALL_STACKS))
        self.assert_installed(result)
        self.assertEqual(sorted(self.install_toml()["install"]["stacks"]), sorted(ALL_STACKS))

    def test_unsupported_stack_is_rejected_listing_the_supported_stacks(self):
        result = self.run_installer("--stacks", "python,cobol")
        self.assertNotEqual(result.returncode, 0, result.stderr)
        combined = result.stdout + result.stderr
        self.assertIn("cobol", combined)
        self.assertNotIn("unrecognized arguments", combined,
                         "§S7: --stacks must be a real installer option")
        for stack in ALL_STACKS:
            self.assertIn(stack, combined, f"§S7: the rejection must list {stack!r}")
        self.assertFalse((self.modelb_home / "install.toml").exists())
        self.assertEqual(list(self.target_root.iterdir()), [], "§S7: nothing deployed")

class StackSelectionOfferTest(_StackSandboxCase):
    """§S7 AC3: with neither ``--stacks`` nor ``--yes`` the selection is
    offered; ``--yes`` takes the default (all) without reading stdin, and
    selection is never inferred from the machine."""

    @staticmethod
    def _is_stack_offer(chunk: str) -> bool:
        # The offer lists every stack; a pre-flight chunk carrying the
        # `stack <name>: … client=<v>` report lines is not the offer.
        return all(stack in chunk for stack in ALL_STACKS) and "client=" not in chunk

    def test_interactive_run_offers_the_stack_list_and_enter_takes_all(self):
        result = self.run_interactive(make_responder([(self._is_stack_offer, "")]))
        offers = [c for c, _ in result.reads if self._is_stack_offer(c)]
        self.assertEqual(
            len(offers), 1,
            f"§S7: exactly one stack-selection offer listing every stack; reads={result.reads!r}",
        )
        self.assert_installed(result)
        self.assertEqual(sorted(self.install_toml()["install"]["stacks"]), sorted(ALL_STACKS))

    def test_interactive_answer_selects_the_named_stack(self):
        result = self.run_interactive(make_responder([(self._is_stack_offer, "python")]))
        self.assertEqual(len([c for c, _ in result.reads if self._is_stack_offer(c)]), 1,
                         f"reads={result.reads!r}")
        self.assert_installed(result)
        self.assertEqual(self.install_toml()["install"]["stacks"], ["python"])
        self.assertEqual(
            {b for b in self.deployed_bundles() if b.startswith("crucible-report-")},
            {"crucible-report-python"},
        )

    def test_explicit_stacks_flag_suppresses_the_offer(self):
        result = self.run_interactive(make_responder([(self._is_stack_offer, "rust")]), "--stacks", "bun")
        self.assertEqual([c for c, _ in result.reads if self._is_stack_offer(c)], [],
                         f"§S7: --stacks given — nothing to offer; reads={result.reads!r}")
        self.assert_installed(result)
        self.assertEqual(self.install_toml()["install"]["stacks"], ["bun"])

    def test_yes_takes_the_default_without_reading_stdin_and_never_infers(self):
        """Regression pin (never inferred): only rust's toolchain is on
        PATH, yet ``--yes`` still selects every stack and reads nothing."""
        self.shim("cargo", "cargo-nextest", "cargo-llvm-cov")
        result = run_installer_interactive(
            ["--yes", *self._installer_args()], self.sandbox_env(),
            make_responder([], default="rust"),
        )
        self.assertEqual(result.reads, [], "§S7: --yes never reads stdin")
        self.assert_installed(result)
        self.assertEqual(sorted(self.install_toml()["install"]["stacks"]), sorted(ALL_STACKS))

class StackSelectionPersistenceTest(_StackSandboxCase):
    """§S7 AC4: the selection round-trips through ``install.toml``; a
    re-run with a wider ``--stacks`` adds the new stack's bundle and leaves
    every other manifest entry unchanged."""

    def _manifest(self) -> dict[str, str]:
        return {f["path"]: f["sha256"] for f in self.install_toml().get("files", [])}

    def test_selection_round_trips_through_install_toml(self):
        self.assert_installed(self.run_installer("--stacks", "rust,python"))
        from modelb_axi.config import load_install_toml
        self.assertEqual(sorted(load_install_toml(self.modelb_home)["install"]["stacks"]),
                         ["python", "rust"])

    def test_wider_rerun_adds_only_the_new_stack_bundle(self):
        self.assert_installed(self.run_installer("--stacks", "python"))
        before = self._manifest()
        self.assertFalse(any("crucible-report-rust" in p for p in before), before)

        self.assert_installed(self.run_installer("--reinstall", "--stacks", "python,rust"))
        after = self._manifest()
        self.assertEqual(sorted(self.install_toml()["install"]["stacks"]), ["python", "rust"])
        changed = {p: (before[p], after.get(p)) for p in before if after.get(p) != before[p]}
        self.assertEqual(changed, {}, "§S7: prior manifest entries must be unchanged")
        added = sorted(set(after) - set(before))
        rust_files = sorted(
            f".agents/skills/{p.relative_to(SKILLS_SRC)}"
            for p in (SKILLS_SRC / "crucible-report-rust").rglob("*") if p.is_file()
        )
        self.assertEqual(added, rust_files, "§S7: exactly the rust report bundle is added")
        self.assertIn("crucible-report-rust", self.deployed_bundles())

# ---------------------------------------------------------------------------
# §S8 — toolchains: probed cheaply, installed only on confirmation
# ---------------------------------------------------------------------------

class ToolchainProbeScopeTest(_StackSandboxCase):
    """§S8 AC1/AC2: only the selected stack's row is probed (counted), by
    resolution, never execution; the only probe subprocess is the PATH
    ``python3`` import check, and only when python is selected."""

    def setUp(self):
        super().setUp()
        # Every toolchain binary present — and recording any execution.
        self.shim(*TOOLCHAIN_BINARIES)

    def test_rust_selection_probes_only_the_rust_row_once_each(self):
        self.shim("python3")
        result, log = self.run_counting("--stacks", "rust")
        self.assert_installed(result)
        which = log["which"]
        for tool in STACK_PROBES["rust"]:
            self.assertEqual(which.count(tool), 1, f"§S8: probe {tool} exactly once; which={which}")
        others = sorted({t for t in which if t in TOOLCHAIN_BINARIES and t not in STACK_PROBES["rust"]})
        self.assertEqual(others, [], f"§S8: unselected stacks cost no probe; which={which}")
        self.assertEqual(self.stack_lines(result.stderr), [
            "stack rust: cargo=detected cargo-nextest=detected cargo-llvm-cov=detected client=absent",
        ])

    def test_rust_selection_runs_no_subprocess_and_executes_no_toolchain(self):
        self.shim("python3")
        result, log = self.run_counting("--stacks", "rust")
        self.assert_installed(result)
        self.assertEqual(log["popen"], [], "§S8: no probe subprocess without python selected")
        self.assertEqual(self.executions(), [], "§S8: toolchains resolved, never executed")
        self.assertEqual(self.stack_group(result.stderr, "rust").get("cargo"), "detected")

    def test_unselected_stacks_get_no_line_warning_or_mention(self):
        result, _ = self.run_counting("--stacks", "rust")
        self.assert_installed(result)
        self.assertEqual([ln.split(":")[0] for ln in self.stack_lines(result.stderr)], ["stack rust"])
        warnings = _decode(result.stdout).get("warnings", [])
        for tool in ("mvn", "arduino-cli", "g++", "xmlrunner", "coverage"):
            self.assertFalse(
                any(tool in w for w in warnings),
                f"§S8: unselected stack tool {tool!r} mentioned; warnings={warnings!r}",
            )

    def test_python_selection_runs_only_the_path_python3_import_check(self):
        self.shim("python3")
        result, log = self.run_counting("--stacks", "python")
        self.assert_installed(result)
        runs = self.executions()
        self.assertTrue(runs, "§S8: the PATH python3 import check must run for python")
        self.assertEqual(
            [r for r in runs if not r.startswith("python3 ")], [],
            f"§S8: python3 is the only executable a probe runs; ran={runs!r}",
        )
        for run in runs:
            self.assertIn(" -c ", f" {run.split(' ', 1)[1]} ", f"§S8: python3 -c only; ran={run!r}")
            self.assertIn("import", run)
        joined = "\n".join(runs)
        self.assertIn("xmlrunner", joined)
        self.assertIn("coverage", joined)
        popen_bins = [Path(a[0] if isinstance(a, list) else a.split()[0]).name for a in log["popen"]]
        self.assertEqual(set(popen_bins), {"python3"}, f"popen={log['popen']!r}")
        self.assertLessEqual(len(log["popen"]), 2, "§S8: at most one check per module")
        self.assertEqual(self.stack_lines(result.stderr), [
            "stack python: python3=detected xmlrunner=detected coverage=detected client=absent",
        ])
        others = sorted({t for t in log["which"] if t in TOOLCHAIN_BINARIES})
        self.assertEqual(others, [], f"§S8: python selection probes no other stack; which={log['which']}")

class ToolchainAbsentWarningTest(_StackSandboxCase):
    """§S8 AC3: an absent toolchain WARNs, records ``absent``, names the
    provider's installer, and the install succeeds; ``xmlrunner``/
    ``coverage`` absence names the exact install command."""

    def test_absent_rust_toolchain_warns_names_installers_and_installs(self):
        result = self.run_installer("--stacks", "rust")
        axi = self.assert_installed(result)
        self.assertEqual(self.stack_group(result.stderr, "rust"), {
            "cargo": "absent", "cargo-nextest": "absent", "cargo-llvm-cov": "absent",
            "client": "absent",
        })
        warnings = axi.get("warnings", [])
        self.assertTrue(any("cargo" in w and "rustup" in w for w in warnings),
                        f"§S8: cargo absence names rustup; warnings={warnings!r}")
        self.assertTrue(any("cargo install cargo-nextest" in w for w in warnings),
                        f"§S8: names `cargo install cargo-nextest`; warnings={warnings!r}")
        caps = self.install_toml().get("capabilities", {})
        self.assertEqual(caps.get("rust.cargo"), "absent")
        self.assertEqual(caps.get("rust.cargo-nextest"), "absent")

    def test_absent_python_modules_name_the_install_command(self):
        self.shim("python3", exit_code=1)  # python3 present, every import fails
        result = self.run_installer("--stacks", "python")
        axi = self.assert_installed(result)
        group = self.stack_group(result.stderr, "python")
        self.assertEqual(group.get("python3"), "detected", result.stderr)
        self.assertEqual(group.get("xmlrunner"), "absent", result.stderr)
        self.assertEqual(group.get("coverage"), "absent", result.stderr)
        warnings = axi.get("warnings", [])
        for module in ("xmlrunner", "coverage"):
            hits = [w for w in warnings if module in w and "pip install" in w]
            self.assertTrue(hits, f"§S8: {module} absence names its install command; {warnings!r}")
        caps = self.install_toml().get("capabilities", {})
        self.assertEqual(caps.get("python.xmlrunner"), "absent")
        self.assertEqual(caps.get("python.coverage"), "absent")

class ToolchainInstallerConfirmationTest(_StackSandboxCase):
    """§S8 AC4: under ``--yes`` no toolchain installer runs; interactively
    one runs only after an explicit yes; an elevated-privilege installer is
    never run; declining is recorded. Fixture: rust selected, ``cargo`` and
    ``cargo-llvm-cov`` present (recording shims), ``cargo-nextest`` absent —
    so the one offer is ``cargo install cargo-nextest``."""

    def setUp(self):
        super().setUp()
        self.shim("cargo", "cargo-llvm-cov")

    @staticmethod
    def _nextest_offer(chunk: str) -> bool:
        return "cargo install cargo-nextest" in chunk

    def _cargo_installs(self) -> list[str]:
        return [r for r in self.executions() if r.startswith("cargo ") and "install" in r]

    def test_yes_never_runs_the_toolchain_installer_but_names_it(self):
        result = self.run_installer("--stacks", "rust")
        axi = self.assert_installed(result)
        self.assertEqual(self.executions(), [], "§S8: --yes never confirms a toolchain installer")
        self.assertTrue(any("cargo install cargo-nextest" in w for w in axi.get("warnings", [])),
                        f"axi={axi!r}")

    def test_explicit_yes_runs_the_provider_installer_once(self):
        result = self.run_interactive(make_responder([(self._nextest_offer, "y")]), "--stacks", "rust")
        self.assertEqual(len(result.offers_naming("cargo install cargo-nextest")), 1,
                         f"§S8: one offer; reads={result.reads!r}")
        installs = self._cargo_installs()
        self.assertEqual(len(installs), 1, f"§S8: ran once on explicit yes; ran={self.executions()!r}")
        self.assertIn("cargo-nextest", installs[0])
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_blank_enter_is_not_an_explicit_yes(self):
        result = self.run_interactive(make_responder([(self._nextest_offer, "")]), "--stacks", "rust")
        self.assertEqual(len(result.offers_naming("cargo install cargo-nextest")), 1,
                         f"§S8: the offer must be made; reads={result.reads!r}")
        self.assertEqual(self._cargo_installs(), [], "§S8: only an explicit yes runs it")

    def test_declining_is_recorded_and_the_install_continues(self):
        result = self.run_interactive(make_responder([(self._nextest_offer, "n")]), "--stacks", "rust")
        self.assertEqual(len(result.offers_naming("cargo install cargo-nextest")), 1,
                         f"reads={result.reads!r}")
        self.assertEqual(self._cargo_installs(), [])
        axi = self.assert_installed(result)
        toml_text = (self.modelb_home / "install.toml").read_text(encoding="utf-8")
        self.assertTrue(_declined_record(axi, toml_text, "cargo-nextest"),
                        f"§S8: the decline must be recorded; axi={axi!r} toml={toml_text!r}")
        self.assertEqual(self.install_toml()["capabilities"].get("rust.cargo-nextest"), "absent")

    def test_elevated_installer_is_named_never_run_even_on_yes(self):
        self.shim(*ELEVATED_INSTALLERS)
        result = self.run_interactive(make_responder([], default="y"), "--stacks", "java")
        axi = self.assert_installed(result)
        ran = [r for r in self.executions() if r.split(" ", 1)[0] in ELEVATED_INSTALLERS]
        self.assertEqual(ran, [], f"§S8: elevated installers are never run; ran={ran!r}")
        self.assertEqual(self.stack_group(result.stderr, "java"),
                         {"mvn": "absent", "java": "absent", "client": "absent"})
        warnings = axi.get("warnings", [])
        self.assertTrue(any("mvn" in w for w in warnings), f"warnings={warnings!r}")
        caps = self.install_toml()["capabilities"]
        self.assertEqual((caps.get("java.mvn"), caps.get("java.java")), ("absent", "absent"))

# ---------------------------------------------------------------------------
# §S4 — per-stack "<stack>.<probe>" verdict keys
# ---------------------------------------------------------------------------

class StackVerdictKeysTest(_StackSandboxCase):
    """§S4 AC2: each selected stack's client and toolchain verdicts are
    recorded under quoted ``"<stack>.<probe>"`` keys (``"<stack>.client"``
    for Crucible's client); an unselected stack records none."""

    def test_selected_stacks_record_flat_quoted_probe_keys(self):
        make_home(self.home, crucible_manifest=True, clients=("python",))
        self.shim("python3", "cargo", "cargo-nextest")
        self.assert_installed(self.run_installer("--stacks", "python,rust"))
        caps = self.install_toml().get("capabilities", {})
        stack_keys = {k: v for k, v in caps.items() if k.split(".", 1)[0] in ALL_STACKS}
        self.assertEqual(stack_keys, {
            "python.python3": "detected",
            "python.xmlrunner": "detected",
            "python.coverage": "detected",
            "python.client": "detected",
            "rust.cargo": "detected",
            "rust.cargo-nextest": "detected",
            "rust.cargo-llvm-cov": "absent",
            "rust.client": "absent",
        }, f"§S4: flat quoted keys expected (a dotted bare key nests); caps={caps!r}")

    def test_quarkus_and_java_each_record_their_own_keys(self):
        make_home(self.home, crucible_manifest=True, clients=("mvn",))
        self.shim("mvn")
        self.assert_installed(self.run_installer("--stacks", "quarkus,java"))
        caps = self.install_toml().get("capabilities", {})
        for stack in ("quarkus", "java"):
            with self.subTest(stack=stack):
                self.assertEqual(
                    (caps.get(f"{stack}.mvn"), caps.get(f"{stack}.java"), caps.get(f"{stack}.client")),
                    ("detected", "absent", "detected"),
                )

    def test_unselected_stack_records_no_key(self):
        self.assert_installed(self.run_installer("--stacks", "bun"))
        caps = self.install_toml().get("capabilities", {})
        prefixes = sorted({k.split(".", 1)[0] for k in caps if "." in k})
        self.assertEqual(prefixes, ["bun"], f"caps={caps!r}")
        self.assertEqual(
            {k for k in caps if k.startswith("bun.")},
            {"bun.bun", "bun.node", "bun.client"},
        )

if __name__ == "__main__":
    unittest.main()
