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
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path
from unittest import mock

from tests._helpers import (
    code_string_literals,
    python3_stub,
    uv_stub,
    write_interpreter_fixture,
)
from tests._helpers import decode_axi as _decode
from tests._helpers import write_executable as _write_exe
from tests.pi_capability_sandbox import (
    AGENT_DIR_ENV,
    make_home,
    make_provisioned_agent_dir,
    parse_group_line,
)
from tests.scripted_terminal import (
    PROCEED_PROMPT,
    last_line,
    make_responder,
    run_installer_interactive,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS_SRC = REPO_ROOT / "skills-src"

#: ``init``'s stack vocabulary (§S7).
ALL_STACKS = ("arduino", "bun", "python", "quarkus", "rust", "java")

#: §S8 table: stack -> the binaries/modules probed, in table order.
#: MIGRATED at CR-MDB-063 C1 RED (§S1): every stack's probes begin with
#: ``python3`` — each stack's Crucible client is a python script run as
#: ``python3 <client>``.
STACK_PROBES = {
    "python": ("python3", "xmlrunner", "coverage"),
    "rust": ("python3", "cargo", "cargo-nextest", "cargo-llvm-cov"),
    "quarkus": ("python3", "mvn", "java"),
    "java": ("python3", "mvn", "java"),
    "bun": ("python3", "bun", "node"),
    "arduino": ("python3", "arduino-cli", "g++"),
}

#: CR-MDB-063 §S1: the ``python3`` PATH probe every stack leads with — its
#: remediation, its install argv and where a re-probe looks after it ran.
PYTHON3_REMEDIATION = "put python3 on PATH with uv: `uv python install --default 3.14`"
PYTHON3_INSTALL = ("uv", "python", "install", "--default", "3.14")
PYTHON3_INSTALL_DISPLAY = "uv python install --default 3.14"
PYTHON3_EXPECTED = (
    "in uv's executable directory (~/.local/bin, unless UV_PYTHON_BIN_DIR or "
    "XDG_BIN_HOME names another), which must be on PATH"
)

#: CR-MDB-063 §S2: the project ``.venv`` route for ``xmlrunner`` and
#: ``coverage``, in order.
ROUTE_COMMANDS = ("uv venv --python 3.14", "uv pip install unittest-xml-reporting coverage")

#: CR-MDB-063 §S2: why a probe has no install argv — each such probe
#: declares exactly one, as data.
NO_INSTALL_REASONS = ("elevated", "per-project")
ELEVATED_PROBES = ("mvn", "java", "node", "g++")
PER_PROJECT_PROBES = ("xmlrunner", "coverage")


def _module_route_warning(name: str, verdict: str) -> str:
    """§S2's exact warning for an absent (or unknown) python module."""
    return (
        f"stack python: {name}={verdict} — the PATH python3 cannot run python tests; "
        "a python project's tests run under its own .venv: in the project, run "
        "`uv venv --python 3.14`, then `uv pip install unittest-xml-reporting coverage`"
    )


def _declared_reasons(probe: dict) -> list[str]:
    """The no-install reasons ``probe`` declares, read from its data whatever
    the field holding it is called: every value exactly ``elevated`` or
    ``per-project`` (§S2 names the values, not the field)."""
    return [v for v in probe.values() if isinstance(v, str) and v in NO_INSTALL_REASONS]


def _as_commands(value) -> tuple[str, ...] | None:
    """``value`` read as a sequence of commands — each item a command string
    or an argv of strings, joined — else ``None``."""
    if not isinstance(value, (tuple, list)) or not value:
        return None
    commands = []
    for item in value:
        if isinstance(item, str):
            commands.append(item)
        elif isinstance(item, (tuple, list)) and item and all(isinstance(p, str) for p in item):
            commands.append(" ".join(item))
        else:
            return None
    return tuple(commands)


def _declared_route() -> dict[str, tuple[str, ...]]:
    """Every module-level attribute of ``modelb_axi.requirements`` whose value
    is §S2's route — exactly :data:`ROUTE_COMMANDS`, in order. §S2 declares
    the route as data there without naming the attribute."""
    from modelb_axi import requirements
    return {name: ROUTE_COMMANDS for name, value in vars(requirements).items()
            if _as_commands(value) == ROUTE_COMMANDS}


class _RecordingOffer:
    """An ``offer`` seam that records every prompt and answers ``answer``."""

    def __init__(self, answer: bool):
        self.answer = answer
        self.prompts: list[str] = []

    def __call__(self, prompt: str) -> bool:
        self.prompts.append(prompt)
        return self.answer

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
# MIGRATED at CR-MDB-047 C1 RED (§S1 version floor): a fake standing for a
# present Sandesh answers `--version` like the real CLI, at the 0.4.0 floor.
_FAKE_SANDESH = "#!/bin/sh\necho 'sandesh 0.4.0'\nexit 0\n"

def _is_sandesh_version(argv) -> bool:
    """Whether a logged Popen argv is the sandesh probe's ``sandesh --version``
    (CR-MDB-047 §S1) — a list or a command string, the binary by basename."""
    parts = argv if isinstance(argv, list) else str(argv).split()
    return len(parts) == 2 and Path(parts[0]).name == "sandesh" and parts[1] == "--version"


def _runs_python3(argv) -> bool:
    """Whether a logged Popen argv runs a ``python3`` (by basename)."""
    parts = argv if isinstance(argv, list) else str(argv).split()
    return bool(parts) and Path(parts[0]).name == "python3"


#: The stack python probe's module check: ``import <module>`` and nothing else (§S8).
_IMPORT_CHECK_RE = re.compile(r"import [\w.]+")
#: The same check as the fixture's ``python3`` logs it.
_LOGGED_IMPORT_CHECK_RE = re.compile(r"python3 -c import [\w.]+")


def _is_import_check(argv) -> bool:
    """Whether a logged Popen argv is the stack python probe's module check,
    ``python3 -c "import <module>"`` (§S8)."""
    return (isinstance(argv, list) and len(argv) == 3 and _runs_python3(argv)
            and argv[1] == "-c" and _IMPORT_CHECK_RE.fullmatch(argv[2]) is not None)


def _is_interpreter_probe(argv) -> bool:
    """Whether a logged Popen argv belongs to the installer's interpreter probe
    (CR-MDB-064 §S2): a run of ``python3`` that is not a module check, or the
    second candidate's ``uv python find``."""
    if _runs_python3(argv):
        return not _is_import_check(argv)
    parts = argv if isinstance(argv, list) else str(argv).split()
    return len(parts) >= 3 and Path(parts[0]).name == "uv" and parts[1:3] == ["python", "find"]


def _recording_shim(marker: Path, exit_code: int = 0) -> str:
    """A fake binary that appends ``<name> <args>`` to ``marker`` on every
    EXECUTION, then exits ``exit_code``."""
    return (
        "#!/bin/sh\n"
        f'printf \'%s %s\\n\' "${{0##*/}}" "$*" >> "{marker}"\n'
        f"exit {exit_code}\n"
    )


def _report_bundles() -> set[str]:
    return {
        p.name for p in SKILLS_SRC.iterdir()
        if p.is_dir() and p.name.startswith("crucible-report-") and (p / "SKILL.md").is_file()
    }

#: Non-report bundles that are nevertheless STACK-SCOPED (CR-MDB-023 \u00a7S4):
#: ``code-health`` drives Rust-only tools, so it deploys only when ``rust``
#: is selected (or no stack filter is given) -- the same CR-MDB-036 \u00a7S7
#: rule the ``crucible-report-*`` bundles follow. It is therefore NOT an
#: always-deployed bundle.
STACK_SCOPED_NON_REPORT_BUNDLES = {"code-health": "rust"}

def _always_bundles() -> set[str]:
    return {
        p.name for p in SKILLS_SRC.iterdir()
        if p.is_dir() and not p.name.startswith("crucible-report-")
        and p.name not in STACK_SCOPED_NON_REPORT_BUNDLES
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
        # MIGRATED at CR-MDB-064 C2 RED (§S7): the shared installer fixture — a
        # `python3` at the 3.14 floor (the interpreter is required, §S2) and a `uv`
        # answering `uv python find --system '>=3.14'`, otherwise this module's fake.
        write_interpreter_fixture(self.bin_dir, uv_body=_FAKE_UV)
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
        # MIGRATED (CR-MDB-023 §S4): selecting rust adds every rust-scoped
        # bundle -- its report bundle AND code-health. Each bundle's SKILL.md
        # is expected by name, so an absent bundle cannot vanish from the
        # expectation.
        rust_bundles = ("crucible-report-rust", *sorted(
            name for name, stack in STACK_SCOPED_NON_REPORT_BUNDLES.items() if stack == "rust"
        ))
        rust_files = sorted(
            {f".agents/skills/{p.relative_to(SKILLS_SRC)}"
             for bundle in rust_bundles if (SKILLS_SRC / bundle).is_dir()
             for p in (SKILLS_SRC / bundle).rglob("*") if p.is_file()}
            | {f".agents/skills/{bundle}/SKILL.md" for bundle in rust_bundles}
        )
        self.assertEqual(added, rust_files, "§S7: exactly the rust-scoped bundles are added")
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
        # MIGRATED at CR-MDB-064 C2 RED (§S7): the fixture's python3, not a recording
        # shim that reports no version (it would be refused, §S2).
        result, log = self.run_counting("--stacks", "rust")
        self.assert_installed(result)
        which = log["which"]
        for tool in STACK_PROBES["rust"]:
            self.assertEqual(which.count(tool), 1, f"§S8: probe {tool} exactly once; which={which}")
        others = sorted({t for t in which if t in TOOLCHAIN_BINARIES and t not in STACK_PROBES["rust"]})
        self.assertEqual(others, [], f"§S8: unselected stacks cost no probe; which={which}")
        # MIGRATED at CR-MDB-063 C1 RED (§S1): the line leads with python3.
        self.assertEqual(self.stack_lines(result.stderr), [
            "stack rust: python3=detected cargo=detected cargo-nextest=detected "
            "cargo-llvm-cov=detected client=absent",
        ])

    def test_rust_selection_runs_no_subprocess_and_executes_no_toolchain(self):
        result, log = self.run_counting("--stacks", "rust")
        self.assert_installed(result)
        # MIGRATED at CR-MDB-047 C1 RED (§S1: the sandesh probe runs
        # `sandesh --version`): that run is the one probe subprocess left
        # without python selected; no toolchain probe runs one.
        version_runs = [a for a in log["popen"] if _is_sandesh_version(a)]
        self.assertEqual(len(version_runs), 1, f"one `sandesh --version`; popen={log['popen']!r}")
        # MIGRATED at CR-MDB-064 C2 RED (§S2/§S7): the interpreter probe reads the
        # fixture's PATH python3 by running it, whatever the stacks; it is no toolchain
        # probe.
        interpreter_runs = [a for a in log["popen"] if _is_interpreter_probe(a)]
        self.assertGreaterEqual(len(interpreter_runs), 1,
                                f"§S2: the interpreter is read by running it; "
                                f"popen={log['popen']!r}")
        self.assertEqual(
            [a for a in log["popen"]
             if not _is_sandesh_version(a) and not _is_interpreter_probe(a)], [],
            "§S8: no toolchain probe subprocess without python selected")
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
        # MIGRATED at CR-MDB-064 C2 RED (§S7): the fixture's python3, recording its runs;
        # besides the module checks the interpreter probe runs it (§S2), and that is no
        # toolchain probe.
        write_interpreter_fixture(self.bin_dir, uv_body=_FAKE_UV, python3_log=self.marker)
        result, log = self.run_counting("--stacks", "python")
        self.assert_installed(result)
        runs = self.executions()
        self.assertTrue(runs, "§S8: the PATH python3 import check must run for python")
        self.assertEqual(
            [r for r in runs if not r.startswith("python3 ")], [],
            f"§S8: python3 is the only executable a probe runs; ran={runs!r}",
        )
        checks = [r for r in runs if _LOGGED_IMPORT_CHECK_RE.fullmatch(r)]
        self.assertEqual(sorted(r.split()[-1] for r in checks), ["coverage", "xmlrunner"],
                         f"§S8: one `python3 -c import <module>` per module; ran={runs!r}")
        # MIGRATED at CR-MDB-047 C1 RED (§S1): `sandesh --version` is the
        # sandesh probe's own run, not a toolchain probe's.
        version_runs = [a for a in log["popen"] if _is_sandesh_version(a)]
        self.assertEqual(len(version_runs), 1, f"one `sandesh --version`; popen={log['popen']!r}")
        toolchain_popen = [a for a in log["popen"]
                           if not _is_sandesh_version(a) and not _is_interpreter_probe(a)]
        popen_bins = [Path(a[0] if isinstance(a, list) else a.split()[0]).name
                      for a in toolchain_popen]
        self.assertEqual(set(popen_bins), {"python3"}, f"popen={log['popen']!r}")
        self.assertTrue(all(_is_import_check(a) for a in toolchain_popen), toolchain_popen)
        self.assertLessEqual(len(toolchain_popen), 2, "§S8: at most one check per module")
        self.assertGreaterEqual(len([a for a in log["popen"] if _is_interpreter_probe(a)]), 1,
                                f"§S2: the interpreter is read by running it; "
                                f"popen={log['popen']!r}")
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
        # MIGRATED at CR-MDB-063 C1 RED (§S1): the group leads with python3.
        self.assertEqual(self.stack_group(result.stderr, "rust"), {
            "python3": "detected",
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

    def test_absent_python_modules_name_the_project_venv_route(self):
        # MIGRATED at CR-MDB-063 C1 RED (§S2), was
        # test_absent_python_modules_name_the_install_command: each module's warning
        # is §S2's exact route warning, and no `python3 -m pip install` is named.
        # MIGRATED at CR-MDB-064 C2 RED (§S7): the fixture's python3 at the floor,
        # every import check failing.
        write_interpreter_fixture(self.bin_dir, uv_body=_FAKE_UV, imports_ok=False)
        result = self.run_installer("--stacks", "python")
        axi = self.assert_installed(result)
        group = self.stack_group(result.stderr, "python")
        self.assertEqual(group.get("python3"), "detected", result.stderr)
        self.assertEqual(group.get("xmlrunner"), "absent", result.stderr)
        self.assertEqual(group.get("coverage"), "absent", result.stderr)
        warnings = axi.get("warnings", [])
        for module in ("xmlrunner", "coverage"):
            with self.subTest(module=module):
                own = [w for w in warnings if w.startswith(f"stack python: {module}=")]
                self.assertEqual(own, [_module_route_warning(module, "absent")],
                                 f"§S2: {module}'s warning names the .venv route; {warnings!r}")
        self.assertEqual([w for w in warnings if "-m pip" in w], [],
                         f"§S2: no pip install into the PATH python3 is named; {warnings!r}")
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
        # MIGRATED at CR-MDB-063 C1 RED (§S1): the group leads with python3, which
        # the fixture puts on PATH — so the all-yes answer meets no python3 offer.
        self.assertEqual(self.stack_group(result.stderr, "java"),
                         {"python3": "detected", "mvn": "absent", "java": "absent",
                          "client": "absent"})
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
        # MIGRATED at CR-MDB-064 C2 RED (§S7): python3 is the fixture's.
        self.shim("cargo", "cargo-nextest")
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

# ---------------------------------------------------------------------------
# CR-MDB-036 cycle-91 VERIFY findings (fixed at C92): child output, the
# re-probe after a confirmed install, shared-install warnings, warning
# shape, duplicate stack names.
# ---------------------------------------------------------------------------

def _backticked(text: str) -> list[str]:
    import re
    return re.findall(r"`([^`]+)`", text)


def _install_display(install: tuple[str, ...]) -> str:
    """How a provider installer argv reads as a command: an ``sh -c``
    pipeline is its script; anything else is the argv joined."""
    return install[-1] if tuple(install[:2]) == ("sh", "-c") else " ".join(install)


def _tool_path(name: str) -> str:
    """Absolute path of a real coreutil, resolved on the TEST's PATH so a
    shim can call it under the sandbox's one-directory PATH."""
    found = shutil.which(name)
    if found is None:
        raise unittest.SkipTest(f"{name} not available to build the shim")
    return found


def _terminal_shim(marker: Path) -> str:
    """A fake installer that records its run and reports whether its
    STDOUT is the user's terminal (not a capture pipe), plus one stderr
    line."""
    return (
        "#!/bin/sh\n"
        f'printf \'%s %s\\n\' "${{0##*/}}" "$*" >> "{marker}"\n'
        'if [ -t 1 ]; then echo "CHILD-STDOUT-ON-TERMINAL ${0##*/}"; '
        'else echo "CHILD-STDOUT-CAPTURED ${0##*/}"; fi\n'
        'echo "CHILD-STDERR ${0##*/}" >&2\n'
        "exit 0\n"
    )


class ChildInstallerOutputOnTerminalTest(_StackSandboxCase):
    """Findings 1+8 (§S3/§S8): a confirmed provider installer and a
    confirmed ``pi install`` are NOT captured — the child's stdout goes to
    the user's stderr (the terminal), so its prompts and errors are
    visible while it runs; the envelope on stdout stays clean.

    Driven through a real subprocess whose stdin AND stderr are one
    pseudo-terminal (the only way to reach an interactive offer with a
    real file descriptor); stdout is a pipe carrying the envelope.
    Fixture: ``permissions`` missing (one ``pi install`` offer), rust
    selected with ``cargo``/``cargo-llvm-cov`` present and
    ``cargo-nextest`` absent (one ``cargo install`` offer); both shims
    report whether their stdout is the terminal."""

    def setUp(self):
        super().setUp()
        self.agent_dir = self._root / "agent-no-permissions"
        make_provisioned_agent_dir(self.agent_dir, omit=("permissions",))
        _write_exe(self.bin_dir, "pi", _terminal_shim(self.marker))
        _write_exe(self.bin_dir, "cargo", _terminal_shim(self.marker))
        self.shim("cargo-llvm-cov")

    def _run_on_terminal(self, *extra, answers: str = "y\n" * 3 + "n\n" * 6):
        import pty
        import threading
        master, slave = pty.openpty()
        proc = subprocess.Popen(
            [sys.executable, "-m", "modelb_axi", *self._installer_args(*extra)],
            stdin=slave, stdout=subprocess.PIPE, stderr=slave,
            env=self._subprocess_env(), close_fds=True,
        )
        os.close(slave)
        os.write(master, answers.encode())
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
        return proc.returncode, stdout.decode(), b"".join(chunks).decode(errors="replace")

    def test_confirmed_installers_write_to_the_users_terminal_not_a_capture(self):
        code, stdout, terminal = self._run_on_terminal("--stacks", "rust")
        runs = self.executions()
        self.assertTrue(any(r.startswith("pi install") for r in runs),
                        f"precondition: pi install confirmed; ran={runs!r} terminal={terminal!r}")
        self.assertTrue(any(r.startswith("cargo install") for r in runs),
                        f"precondition: cargo install confirmed; ran={runs!r} terminal={terminal!r}")
        for child in ("pi", "cargo"):
            with self.subTest(child=child):
                self.assertIn(
                    f"CHILD-STDOUT-ON-TERMINAL {child}", terminal,
                    f"findings 1+8: {child}'s stdout must reach the user's terminal "
                    f"(stderr), not a capture pipe; terminal={terminal!r}",
                )
                self.assertIn(f"CHILD-STDERR {child}", terminal,
                              f"{child}'s errors must be visible; terminal={terminal!r}")
        self.assertNotIn("CHILD-", stdout, "stdout carries only the envelope")
        self.assertEqual(code, 0, f"stdout={stdout!r} terminal={terminal!r}")


class ProviderInstallerReprobeTest(_StackSandboxCase):
    """Finding 2 + the re-probe rule (§S8): after a CONFIRMED provider
    installer, that one tool is re-probed — ``installed`` only if it is now
    found, else ``absent`` with a warning naming where it was expected.
    ``sh -c`` installers are exercised through a recording ``sh`` shim.
    arduino-cli's installer runs with ``BINDIR=~/.local/bin`` (created if
    missing). Under ``--yes`` no ``sh -c`` installer ever runs."""

    def _sh_shim(self, body: str = "") -> None:
        _write_exe(self.bin_dir, "sh", (
            "#!/bin/sh\n"
            f'printf \'sh %s BINDIR=%s\\n\' "$*" "$BINDIR" >> "{self.marker}"\n'
            f"{body}"
            "exit 0\n"
        ))

    def _sh_runs(self) -> list[str]:
        return [r for r in self.executions() if r.startswith("sh ")]

    @staticmethod
    def _offer_naming(needle: str):
        return lambda chunk: needle in chunk

    def test_yes_never_runs_an_sh_c_provider_installer(self):
        self._sh_shim()
        axi = self.assert_installed(self.run_installer("--stacks", "bun,arduino"))
        self.assertEqual(self._sh_runs(), [], "§S8: --yes never confirms an sh -c installer")
        self.assertEqual(self.install_toml()["capabilities"].get("bun.bun"), "absent", axi)

    def test_confirmed_sh_c_installer_that_provides_the_tool_records_installed(self):
        chmod = _tool_path("chmod")
        self._sh_shim(
            f"printf '#!/bin/sh\\nexit 0\\n' > \"{self.bin_dir}/bun\"\n"
            f'{chmod} 755 "{self.bin_dir}/bun"\n'
        )
        result = self.run_interactive(
            make_responder([(self._offer_naming("bun.sh/install"), "y")]), "--stacks", "bun",
        )
        self.assertEqual(len(result.offers_naming("bun.sh/install")), 1, f"reads={result.reads!r}")
        self.assertEqual(len(self._sh_runs()), 1, f"ran once; ran={self.executions()!r}")
        self.assertIn("-c", self._sh_runs()[0])
        self.assert_installed(result)
        self.assertEqual(self.install_toml()["capabilities"].get("bun.bun"), "installed",
                         "re-probe found bun on PATH after the confirmed install")

    def test_confirmed_sh_c_installer_that_leaves_the_tool_unfound_records_absent(self):
        self._sh_shim()
        result = self.run_interactive(
            make_responder([(self._offer_naming("bun.sh/install"), "y")]), "--stacks", "bun",
        )
        self.assertEqual(len(self._sh_runs()), 1, f"ran={self.executions()!r}")
        axi = self.assert_installed(result)
        self.assertEqual(self.install_toml()["capabilities"].get("bun.bun"), "absent",
                         "exit 0 alone is not `installed` — the re-probe decides")
        hits = [w for w in axi.get("warnings", []) if "bun" in w and "~/.bun/bin" in w]
        self.assertTrue(hits, f"the warning names where bun was expected; {axi!r}")

    def test_arduino_cli_installer_gets_bindir_local_bin_created_if_missing(self):
        local_bin = self.home / ".local" / "bin"
        self.assertFalse(local_bin.exists(), "precondition: ~/.local/bin is missing")
        self._sh_shim(
            f'printf \'#!/bin/sh\\nexit 0\\n\' > "$BINDIR/arduino-cli"\n'
            f'{_tool_path("chmod")} 755 "$BINDIR/arduino-cli"\n'
        )
        result = self.run_interactive(
            make_responder([(self._offer_naming("arduino-cli"), "y")]), "--stacks", "arduino",
        )
        runs = self._sh_runs()
        self.assertEqual(len(runs), 1, f"ran={self.executions()!r} reads={result.reads!r}")
        self.assertTrue(runs[0].endswith(f"BINDIR={local_bin}"),
                        f"finding 2: arduino-cli's installer runs with BINDIR=~/.local/bin; {runs!r}")
        self.assertTrue(local_bin.is_dir(), "~/.local/bin is created when missing")
        axi = self.assert_installed(result)
        # ~/.local/bin is not on the sandbox PATH: the re-probe cannot find it.
        self.assertEqual(self.install_toml()["capabilities"].get("arduino.arduino-cli"), "absent")
        hits = [w for w in axi.get("warnings", []) if "arduino-cli" in w and "~/.local/bin" in w
                and "declin" not in w.lower()]
        self.assertTrue(hits, f"the warning names ~/.local/bin as where it was expected; {axi!r}")

    def test_arduino_cli_found_in_local_bin_on_path_records_installed(self):
        local_bin = self.home / ".local" / "bin"
        self._sh_shim(
            f'printf \'#!/bin/sh\\nexit 0\\n\' > "$BINDIR/arduino-cli"\n'
            f'{_tool_path("chmod")} 755 "$BINDIR/arduino-cli"\n'
        )
        env = self.sandbox_env()
        env["PATH"] = f"{self.bin_dir}{os.pathsep}{local_bin}"
        result = run_installer_interactive(
            self._installer_args("--stacks", "arduino"), env,
            make_responder([(self._offer_naming("arduino-cli"), "y")]),
        )
        self.assert_installed(result)
        self.assertEqual(self.install_toml()["capabilities"].get("arduino.arduino-cli"), "installed")

    def test_declining_the_arduino_cli_installer_leaves_local_bin_absent(self):
        # Finding 1 (C3 VERIFY): env dirs are created only after an explicit
        # yes — a decline must leave ~/.local/bin exactly as it was.
        local_bin = self.home / ".local" / "bin"
        self.assertFalse(local_bin.exists(), "precondition: ~/.local/bin is missing")
        self._sh_shim()  # the runner resolves, so the offer is really made
        result = self.run_interactive(
            make_responder([(self._offer_naming("arduino-cli"), "n")]), "--stacks", "arduino",
        )
        self.assertEqual(len(result.offers_naming("BINDIR=~/.local/bin")), 1,
                         f"precondition: the installer is offered; reads={result.reads!r}")
        self.assertEqual(self._sh_runs(), [], "declined: the installer never runs")
        self.assert_installed(result)
        self.assertFalse(local_bin.exists(),
                         "a declined installer must not create its BINDIR ~/.local/bin")
        self.assertFalse((self.home / ".local").exists(), "nor any parent of it")

    def test_yes_with_arduino_selected_leaves_local_bin_absent(self):
        # Finding 1 (C3 VERIFY): --yes never confirms an installer, so it
        # never creates the installer's env dirs either.
        local_bin = self.home / ".local" / "bin"
        self.assertFalse(local_bin.exists(), "precondition: ~/.local/bin is missing")
        self._sh_shim()
        self.assert_installed(self.run_installer("--stacks", "arduino"))
        self.assertEqual(self._sh_runs(), [], "§S8: --yes never runs the installer")
        self.assertFalse(local_bin.exists(), "--yes must not create the installer's BINDIR")
        self.assertFalse((self.home / ".local").exists(), "nor any parent of it")

    def _assert_env_dir_failure_warns_and_records_absent(self, local_bin: Path):
        self._sh_shim()
        result = self.run_interactive(
            make_responder([(self._offer_naming("arduino-cli"), "y")]), "--stacks", "arduino",
        )
        axi = self.assert_installed(result)
        self.assertEqual(self._sh_runs(), [],
                         "an installer whose BINDIR cannot be created is not run")
        self.assertEqual(self.install_toml()["capabilities"].get("arduino.arduino-cli"), "absent")
        hits = [w for w in axi.get("warnings", []) if str(local_bin) in w]
        self.assertTrue(hits, f"finding 4: the warning names {local_bin}; {axi!r}")

    def test_non_directory_local_warns_naming_the_path_and_records_absent(self):
        # Finding 4 (C3 VERIFY): ~/.local exists as a FILE, so creating
        # ~/.local/bin fails — WARN naming the path, record absent, never raise.
        (self.home / ".local").write_text("not a directory\n", encoding="utf-8")
        self._assert_env_dir_failure_warns_and_records_absent(self.home / ".local" / "bin")

    def test_unwritable_local_warns_naming_the_path_and_records_absent(self):
        # Finding 4 (C3 VERIFY): ~/.local exists but is read-only.
        if hasattr(os, "geteuid") and os.geteuid() == 0:
            self.skipTest("root ignores directory permissions")
        local = self.home / ".local"
        local.mkdir()
        local.chmod(0o500)
        try:
            self._assert_env_dir_failure_warns_and_records_absent(local / "bin")
        finally:
            local.chmod(0o700)


class ModuleRouteWarningTest(_StackSandboxCase):
    """Finding 5 (§S8), as CR-MDB-063 §S2 changes it: ``xmlrunner`` and
    ``coverage`` are never offered anything — their route, the project
    ``.venv``, runs in each python project — and each keeps its OWN warning
    naming that route. Fixture: the PATH ``python3`` (at the floor, so the
    interpreter probe accepts it, and on PATH, so no ``uv python install
    --default`` offer is met) fails every import check, recording every run.

    MIGRATED at CR-MDB-063 C1 RED (§S2), was SharedInstallCommandWarningTest
    (the shared ``python3 -m pip install`` offer, accepted or declined): the run
    answers yes to everything, and nothing but the proceed gate is asked.
    MIGRATED at CR-MDB-064 C2 RED (§S7): the shared fixture's python3."""

    def setUp(self):
        super().setUp()
        write_interpreter_fixture(self.bin_dir, uv_body=_FAKE_UV, imports_ok=False,
                                  python3_log=self.marker)

    def test_an_all_yes_run_asks_nothing_for_the_modules_and_installs_nothing(self):
        result = self.run_interactive(make_responder([], default="y"), "--stacks", "python")
        axi = self.assert_installed(result)
        prompts = [last_line(chunk) for chunk, _ in result.reads]
        self.assertEqual([p for p in prompts if PROCEED_PROMPT not in p], [],
                         f"§S2: neither module is offered anything, and python3 is on "
                         f"PATH so no `{PYTHON3_INSTALL_DISPLAY}` offer is met; "
                         f"prompts={prompts!r}")
        installs = [r for r in self.executions() if " -m " in f"{r} "]
        self.assertEqual(installs, [], f"§S2: nothing is installed; ran={self.executions()!r}")
        warnings = axi.get("warnings", [])
        for module in ("xmlrunner", "coverage"):
            with self.subTest(module=module):
                own = [w for w in warnings if w.startswith(f"stack python: {module}=")]
                self.assertEqual(own, [_module_route_warning(module, "absent")],
                                 f"finding 5: {module} keeps its own route warning; {warnings!r}")
        caps = self.install_toml()["capabilities"]
        self.assertEqual((caps.get("python.xmlrunner"), caps.get("python.coverage")),
                         ("absent", "absent"))


def _non_command_spans(warnings: list[str], commands: set[str]) -> list[str]:
    """Every backticked span in ``warnings`` that is not exactly one of
    ``commands`` — finding 7's shape check."""
    return [s for w in warnings for s in _backticked(w) if s not in commands]


class WarningCommandShapeTest(_StackSandboxCase):
    """Finding 7: a warning separates the command from the prose — every
    backticked span is exactly a command from the requirements data,
    never prose such as ``install Rust with rustup: …``.

    MIGRATED at CR-MDB-063 C1 RED (§S2): the invariant is widened — a span is
    an install argv's display OR one of the route commands declared in
    ``modelb_axi.requirements`` — and still fails on any other span. The run's
    import checks fail, so the module warnings (and their route) are exercised."""

    def _commands(self) -> set[str]:
        from modelb_axi.requirements import STACK_TOOLCHAINS
        route = _declared_route()
        self.assertEqual(len(route), 1,
                         f"§S2: the route {ROUTE_COMMANDS!r} is declared once in "
                         f"modelb_axi.requirements; found {sorted(route)!r}")
        displays = {
            _install_display(p["install"])
            for probes in STACK_TOOLCHAINS.values() for p in probes if p["install"]
        }
        return displays | set(next(iter(route.values())))

    def test_backticked_spans_in_toolchain_warnings_are_commands_only(self):
        write_interpreter_fixture(self.bin_dir, uv_body=_FAKE_UV, imports_ok=False)
        commands = self._commands()
        axi = self.assert_installed(self.run_installer())
        warnings = axi.get("warnings", [])
        spans = [s for w in warnings for s in _backticked(w)]
        self.assertTrue(set(ROUTE_COMMANDS) <= set(spans),
                        f"precondition: the module warnings name the route; spans={spans!r}")
        self.assertEqual(_non_command_spans(warnings, commands), [],
                         f"finding 7: backticks hold a command only; spans={spans!r}")

    def test_the_shape_check_fails_on_any_other_span(self):
        """The check proved on synthetic warnings: a declared command passes;
        prose, a truncated command and a retired command each fail."""
        commands = {"cargo install cargo-nextest", *ROUTE_COMMANDS}
        clean = ["stack rust: cargo-nextest=absent — install it with cargo: "
                 "`cargo install cargo-nextest`",
                 _module_route_warning("coverage", "absent")]
        self.assertEqual(_non_command_spans(clean, commands), [])
        for span in ("install Rust with rustup: cargo install cargo-nextest", "uv venv",
                     "python3 -m pip install unittest-xml-reporting coverage"):
            with self.subTest(span=span):
                self.assertEqual(_non_command_spans([f"x — `{span}`"], commands), [span])


# ---------------------------------------------------------------------------
# CR-MDB-063 §S1 — python3 on PATH for every stack's client
# ---------------------------------------------------------------------------

class Python3ProbeDataTest(unittest.TestCase):
    """§S1 AC: ``STACK_TOOLCHAINS`` gives each of the six stacks a first probe
    named ``python3`` — a PATH presence check — with §S1's exact
    remediation, install argv and ``expected`` text; the rest of each
    stack's group is unchanged."""

    def test_every_stack_leads_with_the_python3_path_probe(self):
        from modelb_axi.requirements import STACK_TOOLCHAINS
        self.assertEqual(sorted(STACK_TOOLCHAINS), sorted(ALL_STACKS))
        for stack in ALL_STACKS:
            with self.subTest(stack=stack):
                probes = STACK_TOOLCHAINS[stack]
                self.assertEqual(tuple(p["name"] for p in probes), STACK_PROBES[stack])
                first = probes[0]
                self.assertEqual(
                    (first["name"], first["kind"], first["remediation"], first["install"],
                     first["expected"]),
                    ("python3", "binary", PYTHON3_REMEDIATION, PYTHON3_INSTALL,
                     PYTHON3_EXPECTED),
                )


class Python3ProbePreflightTest(_StackSandboxCase):
    """§S1 AC through the real installer (``run_preflight``): a six-stack
    pre-flight prints six ``stack <name>:`` lines, each beginning
    ``python3=``; with no offer accepted ``python3`` is resolved once; each
    selected stack records ``<stack>.python3``. The §D22 ``python3:`` line is
    a separate check, pinned by tests.test_installer_interpreter_probe."""

    def test_a_six_stack_preflight_prints_six_lines_each_leading_with_python3(self):
        result = self.run_installer()
        self.assert_installed(result)
        lines = self.stack_lines(result.stderr)
        self.assertEqual(sorted(ln.split(":", 1)[0][len("stack "):] for ln in lines),
                         sorted(ALL_STACKS), f"one line per stack; lines={lines!r}")
        for line in lines:
            with self.subTest(line=line):
                self.assertRegex(line, r"^stack [a-z]+: python3=detected ",
                                 "§S1: every stack line begins python3=<verdict>")

    def test_python3_is_resolved_once_whatever_the_number_of_stacks(self):
        result, log = self.run_counting()
        self.assert_installed(result)
        lines = self.stack_lines(result.stderr)
        self.assertEqual(len([ln for ln in lines if ": python3=detected " in ln]), 6,
                         f"§S1: all six stacks probe python3; lines={lines!r}")
        self.assertEqual(log["which"].count("python3"), 1,
                         f"§S1: python3 resolved once per run; which={log['which']!r}")

    def test_every_selected_stack_records_its_python3_key(self):
        self.assert_installed(self.run_installer())
        caps = self.install_toml().get("capabilities", {})
        self.assertEqual({s: caps.get(f"{s}.python3") for s in ALL_STACKS},
                         dict.fromkeys(ALL_STACKS, "detected"), f"caps={caps!r}")

    def test_an_unselected_stack_records_no_python3_key(self):
        self.assert_installed(self.run_installer("--stacks", "rust"))
        caps = self.install_toml().get("capabilities", {})
        self.assertEqual(sorted(k for k in caps if k.endswith(".python3")), ["rust.python3"],
                         f"caps={caps!r}")


class Python3OfferRemediationTest(unittest.TestCase):
    """§S1 AC through the real ``remediate_toolchains``: the ``python3``
    offer is made at most once per run, whatever the number of stacks, and
    an accepted one is re-probed for every stack it covers. ``run_on_terminal``
    and ``shutil.which`` are stubbed: nothing is run, nothing is resolved on
    the real PATH."""

    _UV = "/sandbox/bin/uv"
    _PYTHON3 = "/sandbox/bin/python3"

    @staticmethod
    def _verdicts() -> dict:
        return {
            "rust": {"python3": "absent", "cargo": "detected", "cargo-nextest": "detected",
                     "cargo-llvm-cov": "detected"},
            "bun": {"python3": "absent", "bun": "detected", "node": "detected"},
        }

    def _remediate(self, answer: bool):
        from modelb_axi.toolchains import remediate_toolchains
        verdicts, warnings, offer = self._verdicts(), [], _RecordingOffer(answer)
        which_calls: list[str] = []

        def which(name, *args, **kwargs):
            which_calls.append(name)
            return self._PYTHON3 if name == "python3" else None

        with mock.patch("modelb_axi.toolchains.run_on_terminal", return_value=0) as run, \
                mock.patch("modelb_axi.toolchains.shutil.which", side_effect=which):
            remediate_toolchains(verdicts, {"uv": self._UV, "python3": None},
                                 warnings.append, offer)
        return verdicts, warnings, offer, run, which_calls

    def test_an_accepted_offer_runs_once_and_is_reprobed_for_every_stack(self):
        verdicts, warnings, offer, run, which_calls = self._remediate(True)
        self.assertEqual(len(offer.prompts), 1, f"one offer per run; prompts={offer.prompts!r}")
        self.assertIn(PYTHON3_INSTALL_DISPLAY, offer.prompts[0])
        self.assertEqual([c.args[0] for c in run.call_args_list],
                         [[self._UV, *PYTHON3_INSTALL[1:]]],
                         "the installer runs once, its runner resolved on PATH")
        self.assertEqual((verdicts["rust"]["python3"], verdicts["bun"]["python3"]),
                         ("installed", "installed"), "re-probed for every stack it covers")
        self.assertEqual(which_calls.count("python3"), 2,
                         f"one re-probe per stack covered; which={which_calls!r}")
        for stack in ("rust", "bun"):
            with self.subTest(stack=stack):
                own = [w for w in warnings if w.startswith(f"stack {stack}: python3=absent")]
                self.assertEqual(len(own), 1, f"each stack its own warning; {warnings!r}")
                self.assertIn(PYTHON3_REMEDIATION, own[0])

    def test_a_declined_offer_is_made_once_and_runs_nothing(self):
        verdicts, warnings, offer, run, _ = self._remediate(False)
        self.assertEqual(len(offer.prompts), 1, f"one offer per run; prompts={offer.prompts!r}")
        self.assertIn(PYTHON3_INSTALL_DISPLAY, offer.prompts[0])
        run.assert_not_called()
        self.assertEqual((verdicts["rust"]["python3"], verdicts["bun"]["python3"]),
                         ("absent", "absent"))
        declined = [w for w in warnings if "declined" in w and PYTHON3_INSTALL_DISPLAY in w]
        self.assertEqual(len(declined), 1, f"the decline is recorded once; {warnings!r}")


class Python3OfferOnAUvOnlyMachineTest(_StackSandboxCase):
    """§S1 through the real installer: a machine whose only 3.14 is uv's
    passes the §D22 interpreter check (``uv python find``) but has no
    ``python3`` on PATH, so every stack's client cannot run. Interactively
    ``uv python install --default 3.14`` is offered once and, accepted, run
    once (a fake ``uv`` that logs the run and puts a ``python3`` on the
    sandbox PATH); ``--yes`` never runs it. rust and bun are selected with
    their toolchains present, so ``python3`` is the only offer."""

    def setUp(self):
        super().setUp()
        self.uv_runs = self._root / "uv-python-installs"
        # uv's own 3.14, off PATH: the §D22 check finds it through `uv python find`.
        uv_managed = self._root / "uv-managed"
        uv_managed.mkdir()
        uv_python = _write_exe(uv_managed, "python3", python3_stub())
        (self.bin_dir / "python3").unlink()
        cp = _tool_path("cp")
        body = (
            "#!/bin/sh\n"
            'if [ "$1" = "python" ] && [ "$2" = "install" ]; then\n'
            f'    printf \'%s\\n\' "$*" >> "{self.uv_runs}"\n'
            f'    {cp} "{uv_python}" "{self.bin_dir}/python3"\n'
            "    exit 0\n"
            "fi\n"
            'if [ "$1" = "tool" ] && [ "$2" = "install" ]; then exit 0; fi\n'
            'echo "uv 0.0.0-fake"\n'
            "exit 0\n"
        )
        _write_exe(self.bin_dir, "uv", uv_stub(uv_python, body))
        self.shim("cargo", "cargo-nextest", "cargo-llvm-cov", "bun", "node")

    def _uv_installs(self) -> list[str]:
        if not self.uv_runs.exists():
            return []
        return [ln for ln in self.uv_runs.read_text(encoding="utf-8").splitlines() if ln]

    def _run(self, answer: str):
        return self.run_interactive(
            make_responder([(lambda chunk: PYTHON3_INSTALL_DISPLAY in last_line(chunk), answer)]),
            "--stacks", "rust,bun",
        )

    def _assert_detection_reported(self, stderr: str):
        for stack in ("rust", "bun"):
            self.assertEqual(self.stack_group(stderr, stack).get("python3"), "absent",
                             f"the detection report comes first; stderr={stderr!r}")

    def test_an_accepted_offer_runs_uv_once_and_records_installed_for_every_stack(self):
        result = self._run("y")
        offers = [c for c, _ in result.reads if PYTHON3_INSTALL_DISPLAY in last_line(c)]
        self.assertEqual(len(offers), 1, f"one offer for both stacks; reads={result.reads!r}")
        self.assertEqual(self._uv_installs(), ["python install --default 3.14"])
        self.assert_installed(result)
        self._assert_detection_reported(result.stderr)
        caps = self.install_toml()["capabilities"]
        self.assertEqual((caps.get("rust.python3"), caps.get("bun.python3")),
                         ("installed", "installed"), f"caps={caps!r}")

    def test_a_declined_offer_runs_nothing_and_records_absent(self):
        result = self._run("n")
        offers = [c for c, _ in result.reads if PYTHON3_INSTALL_DISPLAY in last_line(c)]
        self.assertEqual(len(offers), 1, f"reads={result.reads!r}")
        self.assertEqual(self._uv_installs(), [])
        self.assert_installed(result)
        caps = self.install_toml()["capabilities"]
        self.assertEqual((caps.get("rust.python3"), caps.get("bun.python3")),
                         ("absent", "absent"))

    def test_yes_never_runs_it_and_names_it_for_every_stack(self):
        result = self.run_installer("--stacks", "rust,bun")
        axi = self.assert_installed(result)
        self.assertEqual(self._uv_installs(), [], "--yes never confirms a provider installer")
        self._assert_detection_reported(result.stderr)
        warnings = axi.get("warnings", [])
        for stack in ("rust", "bun"):
            with self.subTest(stack=stack):
                own = [w for w in warnings if w.startswith(f"stack {stack}: python3=absent")]
                self.assertEqual(len(own), 1, f"each stack its own warning; {warnings!r}")
                self.assertIn(PYTHON3_REMEDIATION, own[0])


# ---------------------------------------------------------------------------
# CR-MDB-063 §S2 — xmlrunner and coverage: the project .venv route
# ---------------------------------------------------------------------------

class NoInstallReasonDataTest(unittest.TestCase):
    """§S2 AC: every probe without an install argv declares why, as data —
    ``elevated`` (mvn, java, node, g++) or ``per-project`` (xmlrunner,
    coverage) — and a probe with one declares neither."""

    def test_every_probe_without_an_installer_declares_elevated_or_per_project(self):
        from modelb_axi.requirements import STACK_TOOLCHAINS
        expected = {**dict.fromkeys(ELEVATED_PROBES, "elevated"),
                    **dict.fromkeys(PER_PROJECT_PROBES, "per-project")}
        seen: dict[str, str] = {}
        for stack, probes in STACK_TOOLCHAINS.items():
            for probe in probes:
                with self.subTest(stack=stack, probe=probe["name"]):
                    reasons = _declared_reasons(probe)
                    if probe["install"]:
                        self.assertEqual(reasons, [], f"an installer needs no reason: {probe!r}")
                    else:
                        self.assertEqual(len(reasons), 1, f"exactly one reason: {probe!r}")
                        seen[probe["name"]] = reasons[0]
        self.assertEqual(seen, expected)


class ModuleRouteDeclarationTest(unittest.TestCase):
    """§S2 AC: the route's commands are declared once, as data, in
    ``modelb_axi.requirements`` — no other module, and no second literal
    there, carries either command."""

    def test_the_route_is_declared_once_in_requirements(self):
        found = _declared_route()
        self.assertEqual(len(found), 1,
                         f"one declaration of {ROUTE_COMMANDS!r}; found {sorted(found)!r}")
        package = REPO_ROOT / "modelb_axi"
        for path in sorted(package.rglob("*.py")):
            literals = code_string_literals(path.read_text(encoding="utf-8"))
            bound = 1 if path == package / "requirements.py" else 0
            for command in ROUTE_COMMANDS:
                with self.subTest(module=path.name, command=command):
                    hits = [lit for lit in literals if command in lit]
                    self.assertLessEqual(len(hits), bound,
                                         f"the route is read from the data, never copied; "
                                         f"{path.relative_to(REPO_ROOT)}: {hits!r}")


class ModuleRouteRemediationTest(unittest.TestCase):
    """§S2 AC through the real ``remediate_toolchains``: with both modules
    absent and a recording ``offer`` there are zero prompts and each module
    gets §S2's exact warning; ``_ELEVATED_NOTE`` rides an ``elevated``
    warning (node) and never a ``per-project`` one (xmlrunner)."""

    _RESOLVED = {"python3": "/sandbox/bin/python3", "uv": "/sandbox/bin/uv"}

    def _remediate(self, verdicts: dict, offer) -> list[str]:
        from modelb_axi.toolchains import remediate_toolchains
        warnings: list[str] = []
        with mock.patch("modelb_axi.toolchains.run_on_terminal") as run:
            remediate_toolchains(verdicts, dict(self._RESOLVED), warnings.append, offer)
        run.assert_not_called()
        return warnings

    def test_absent_modules_get_no_prompt_and_the_exact_route_warning(self):
        offer = _RecordingOffer(True)
        verdicts = {"python": {"python3": "detected", "xmlrunner": "absent",
                               "coverage": "absent"}}
        warnings = self._remediate(verdicts, offer)
        self.assertEqual(offer.prompts, [], "§S2: neither module is offered anything")
        self.assertEqual(warnings, [_module_route_warning("xmlrunner", "absent"),
                                    _module_route_warning("coverage", "absent")])
        self.assertEqual(verdicts["python"], {"python3": "detected", "xmlrunner": "absent",
                                              "coverage": "absent"})

    def test_an_unknown_module_verdict_reads_in_the_same_warning(self):
        offer = _RecordingOffer(True)
        warnings = self._remediate({"python": {"python3": "detected", "xmlrunner": "unknown",
                                               "coverage": "detected"}}, offer)
        self.assertEqual(offer.prompts, [])
        self.assertEqual(warnings, [_module_route_warning("xmlrunner", "unknown")])

    def test_the_elevated_note_rides_node_and_never_xmlrunner(self):
        from modelb_axi.toolchains import _ELEVATED_NOTE
        warnings = self._remediate({
            "bun": {"python3": "detected", "bun": "detected", "node": "absent"},
            "python": {"python3": "detected", "xmlrunner": "absent", "coverage": "detected"},
        }, None)
        node = [w for w in warnings if w.startswith("stack bun: node=")]
        self.assertEqual(len(node), 1, warnings)
        self.assertTrue(node[0].endswith(_ELEVATED_NOTE), f"elevated: {node[0]!r}")
        xmlrunner = [w for w in warnings if w.startswith("stack python: xmlrunner=")]
        self.assertEqual(xmlrunner, [_module_route_warning("xmlrunner", "absent")],
                         "per-project: the route warning, without the elevated note")
        self.assertNotIn(_ELEVATED_NOTE, xmlrunner[0])


class DuplicateStackNamesTest(_StackSandboxCase):
    """Finding 10 (§S7): duplicate names in ``--stacks`` are de-duplicated
    (first occurrence order kept) before anything is recorded or
    deployed."""

    def test_duplicate_stack_names_are_recorded_and_probed_once(self):
        result = self.run_installer("--stacks", "python,rust,python,rust")
        self.assert_installed(result)
        self.assertEqual(self.install_toml()["install"]["stacks"], ["python", "rust"])
        self.assertEqual(
            [ln.split(":")[0] for ln in self.stack_lines(result.stderr)],
            ["stack python", "stack rust"],
        )
        self.assertIn("stacks selected: python, rust\n", result.stderr)

    def test_parse_stacks_deduplicates_keeping_first_order(self):
        from modelb_axi.scaffold import parse_stacks
        self.assertEqual(parse_stacks("rust, python,rust,python"), ["rust", "python"])


class StacksRejectedEnvelopeTest(_StackSandboxCase):
    """Finding 4: the ``stacks_rejected`` outcome is ``ok=false`` and its
    envelope warnings carry the rejection listing the supported stacks —
    both for ``--stacks`` and for an interactive answer."""

    def _assert_rejected(self, axi: dict):
        self.assertEqual(axi.get("outcome"), "stacks_rejected", axi)
        self.assertIs(axi.get("ok"), False, axi)
        warnings = axi.get("warnings", [])
        hits = [w for w in warnings if "cobol" in w and all(s in w for s in ALL_STACKS)]
        self.assertTrue(hits, f"the rejection is an envelope warning; {warnings!r}")

    def test_flag_rejection_envelope(self):
        result = self.run_installer("--stacks", "python,cobol")
        self.assertNotEqual(result.returncode, 0)
        self._assert_rejected(_decode(result.stdout))

    def test_interactive_answer_rejection_envelope(self):
        result = self.run_interactive(make_responder([(
            lambda chunk: all(s in chunk for s in ALL_STACKS) and "client=" not in chunk, "cobol",
        )]))
        self.assertNotEqual(result.returncode, 0)
        self._assert_rejected(_decode(result.stdout))
        self.assertFalse((self.modelb_home / "install.toml").exists())


if __name__ == "__main__":
    unittest.main()
