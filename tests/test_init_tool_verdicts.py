"""The workflow's tools reach a project through the installation's verdicts
(CR-MDB-045 §S1–§S3; PRD D10, amended 2026-09-27, and D11).

- §S1 — ``REQUIREMENTS`` declares Sandesh's own Pi extension as the tier-1
  ``sandesh-pi`` row: provider ``@anthill-tec/sandesh-pi``, probe
  ``pi-package``, policy ``required`` since CR-MDB-047 §S1 (was
  ``recommended``), remediation ``pi install npm:@anthill-tec/sandesh-pi``. A
  ``--yes`` installer run never installs it (a third-party package) and
  records its verdict in ``[capabilities]`` like any other tier-1 row.
- §S2 — ``run_init`` reads the verdicts ``install.toml`` records and never
  probes. ``detected``/``installed`` count as present; a missing verdict —
  including an ``install.toml`` without ``[capabilities]`` — counts as
  unknown, and stderr says to re-run the installer. The ``init`` envelope's
  ``tools`` field maps each requirement row id to ``present``, ``absent`` or
  ``unknown``, in real and ``--dry-run`` runs alike.
- §S3 — a schema key may carry ``when = "<requirement id>"``: rendered only
  when that tool is present. ``load_schema`` rejects a ``when`` naming an id
  ``REQUIREMENTS`` does not declare.

How the ``tools`` keys are read: the spec maps "each row id", so the keys are
the ``REQUIREMENTS`` row ids — the stack-scoped ``crucible-client`` and
``toolchain`` rows are judged, for a one-stack project, from that stack's
``[capabilities]`` entries (``<stack>.client``; ``<stack>.<probe>`` for every
probe in ``STACK_TOOLCHAINS[<stack>]``, the keys ``run_preflight`` records).

Isolation (NON-NEGOTIABLE): every ``install.toml``, Pi agent dir and home is a
fixture under a per-test temp dir. The installer runs with ``HOME``, ``PATH``
(a fake-bin dir with a recording ``pi``), ``PI_CODING_AGENT_DIR``,
``MODELB_HOME`` and ``XDG_DATA_HOME`` pinned there; ``init`` runs in process
with ``HOME`` and ``PI_CODING_AGENT_DIR`` pinned, and through the CLI with all
four pinned. No test reads the real ``~/.local/share/modelb``, ``~/.pi`` or
``~/.crucible``.

Stdlib only.
"""

import argparse
import contextlib
import io
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

from modelb_axi import scaffold
from modelb_axi.requirements import REQUIREMENTS, STACK_TOOLCHAINS
from tests._helpers import decode_axi, parse_env_file, run_module, write_executable
from tests.pi_capability_sandbox import (
    AGENT_DIR_ENV,
    fake_sandesh,
    make_agent_dir,
    make_home,
    make_provisioned_agent_dir,
    npm_spec,
    parse_group_line,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = REPO_ROOT / "modelb_axi" / "project_schema.toml"

SANDESH_PI_ID = "sandesh-pi"
SANDESH_PI_PACKAGE = "@anthill-tec/sandesh-pi"
SANDESH_PI_REMEDIATION = "pi install npm:@anthill-tec/sandesh-pi"

PRESENT, ABSENT, UNKNOWN = "present", "absent", "unknown"

#: The rows every project's ``tools`` map carries (scope ``always``), tier 1
#: then tier 2, as §S1 leaves them: the five Pi extensions, then uv, Sandesh,
#: Crucible and the PATH tools. MIGRATED at CR-MDB-047 C1 RED (§S1): the
#: ``watcher`` row is ``worktree``, and ``direnv`` is a tier-2 PATH tool.
TIER1_IDS = ("dispatch", "lean-ctx", "permissions", "worktree", SANDESH_PI_ID)
ALWAYS_TIER2_IDS = ("uv", "sandesh", "crucible", "python3", "bash", "gh", "jq", "direnv")
#: The stack-scoped rows, judged for the project's own stacks.
STACK_ROW_IDS = ("crucible-client", "toolchain")
#: Every key the ``tools`` field carries for a one-stack project — exactly these.
EXPECTED_TOOL_IDS = frozenset(TIER1_IDS + ALWAYS_TIER2_IDS + STACK_ROW_IDS)

# The scaffold inputs of every in-process ``init`` below.
NAME, TOKEN, ACRONYM, OWNER, STACK = "Verdict Project", "verdproj", "VRD", "tester", "python"
DERIVED_CHANNEL = "VerdictProject"

#: A stderr line telling the user to re-run the installer (§S2).
RERUN_INSTALLER_RE = re.compile(r"(?i)re-?run[^\n]*\b(installer|modelb-axi)\b")

_FAKE_UV = "#!/bin/sh\necho uv-fake\nexit 0\n"
_FAKE_OK = "#!/bin/sh\nexit 0\n"


def _complete_verdicts(verdict: str = "detected") -> dict:
    """``[capabilities]`` as a ``--stacks python`` installer run records it
    once every row is judged ``verdict``: the always-scoped rows by id, the
    python client as ``python.client``, each python toolchain probe as
    ``python.<probe>``."""
    verdicts: dict[str, str] = dict.fromkeys(TIER1_IDS + ALWAYS_TIER2_IDS, verdict)
    verdicts[f"{STACK}.client"] = verdict
    for probe in STACK_TOOLCHAINS[STACK]:
        verdicts[f"{STACK}.{probe['name']}"] = verdict
    return verdicts


def _install_toml_text(home: Path, capabilities: dict | None, deps: dict) -> str:
    """A post-§S4 (or, with ``capabilities`` ``None``, a pre-CR-MDB-036)
    ``install.toml``: every value a TOML basic string, every
    ``[capabilities]`` key quoted (``"python.client"`` stays one flat key)."""
    scripts = home / ".agents" / "hooks" / "scripts"
    lines = [
        "[install]",
        'version = "0.1.0"',
        'harnesses = ["pi"]',
        f'asset_root = "{home / "no-asset-root-here"}"',
        f'hooks_scripts_dir = "{scripts}"',
        f'stacks = ["{STACK}"]',
        "",
        "[deps]",
        *(f'{key} = "{value}"' for key, value in deps.items()),
    ]
    if capabilities is not None:
        lines += ["", "[capabilities]"]
        lines += [f'"{key}" = "{value}"' for key, value in capabilities.items()]
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# §S1 — the declared row
# ---------------------------------------------------------------------------

class SandeshPiRequirementRowTest(unittest.TestCase):
    """§S1 AC (first half): ``REQUIREMENTS`` declares ``sandesh-pi`` as a
    tier-1 ``pi-package`` row, exactly once — required since CR-MDB-047 §S1."""

    def _row(self) -> dict:
        rows = [r for r in REQUIREMENTS if r.get("id") == SANDESH_PI_ID]
        self.assertEqual(len(rows), 1,
                         f"§S1: exactly one `{SANDESH_PI_ID}` row; ids="
                         f"{[r.get('id') for r in REQUIREMENTS]!r}")
        return rows[0]

    def test_sandesh_pi_is_a_tier1_required_pi_package_row_provided_by_its_npm_package(self):
        # MIGRATED at CR-MDB-047 C1 RED (§S1: policy `required`, was
        # `recommended`); was test_sandesh_pi_is_a_tier1_recommended_pi_package_row_...
        row = self._row()
        self.assertEqual(
            (row["tier"], row["provider"], row["probe"], row["policy"]),
            (1, SANDESH_PI_PACKAGE, "pi-package", "required"),
            row,
        )

    def test_sandesh_pi_remediation_is_exactly_its_pi_install_command(self):
        self.assertEqual(self._row()["remediation"], SANDESH_PI_REMEDIATION)


# ---------------------------------------------------------------------------
# §S1 — the installer records it and never installs it
# ---------------------------------------------------------------------------

class SandeshPiInstallerVerdictTest(unittest.TestCase):
    """§S1 AC (second half): a sandboxed ``--yes`` installer run never runs
    ``pi install`` for ``sandesh-pi`` and records its verdict in
    ``[capabilities]``. Every other tier-1 extension is provisioned, so the
    run has no other install to make; ``pi`` is a recording shim."""

    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="modelb-cr045-sandesh-pi-")).resolve()
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.modelb_home = self.root / "modelb-home"
        self.target_root = self.root / "target"
        self.xdg_data = self.root / "xdg-data"
        self.bin_dir = self.root / "bin"
        self.agent_dir = self.root / "pi-agent"
        self.pi_log = self.root / "pi-runs"
        for path in (self.modelb_home, self.target_root, self.xdg_data, self.bin_dir):
            path.mkdir(parents=True)
        self.home = make_home(self.root / "home", crucible_manifest=False)
        write_executable(self.bin_dir, "uv", _FAKE_UV)
        # MIGRATED at CR-MDB-047 C1 RED (§S1 version floor): a current sandesh.
        write_executable(self.bin_dir, "sandesh", fake_sandesh())
        write_executable(self.bin_dir, "python3", _FAKE_OK)
        write_executable(self.bin_dir, "pi", (
            "#!/bin/sh\n"
            f'printf \'%s\\n\' "$*" >> "{self.pi_log}"\n'
            "exit 0\n"
        ))

    def _run_yes(self, *extra: str) -> subprocess.CompletedProcess:
        env = dict(os.environ)
        env.pop("MODELB_TARGET_ROOT", None)
        existing = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = str(REPO_ROOT) + (os.pathsep + existing if existing else "")
        env.update({
            "HOME": str(self.home),
            "PATH": str(self.bin_dir),
            AGENT_DIR_ENV: str(self.agent_dir),
            "MODELB_HOME": str(self.modelb_home),
            "XDG_DATA_HOME": str(self.xdg_data),
        })
        for name in ("HOME", AGENT_DIR_ENV, "MODELB_HOME", "XDG_DATA_HOME"):
            self.assertTrue(env[name].startswith(str(self.root)),
                            f"sandbox guard: {name}={env[name]!r} outside {self.root}")
        return subprocess.run(
            [sys.executable, "-m", "modelb_axi", "--yes",
             "--harnesses", "pi", "--modelb-home", str(self.modelb_home),
             "--target-root", str(self.target_root), "--stacks", STACK, *extra],
            capture_output=True, text=True, timeout=90,
            stdin=subprocess.DEVNULL, env=env,
        )

    def _pi_runs(self) -> list[str]:
        if not self.pi_log.exists():
            return []
        return [ln for ln in self.pi_log.read_text(encoding="utf-8").splitlines() if ln]

    def _capabilities(self) -> dict:
        with open(self.modelb_home / "install.toml", "rb") as fh:
            return tomllib.load(fh).get("capabilities", {})

    def test_yes_never_installs_an_absent_sandesh_pi_and_records_it_absent(self):
        # MIGRATED at CR-MDB-047 C1 RED (§S1: sandesh-pi is required, so only
        # --allow-missing-capabilities lets the run proceed and record it; the
        # failing pre-flight is pinned by tests.test_installer_sandesh_requirements).
        make_provisioned_agent_dir(self.agent_dir, omit=(SANDESH_PI_ID,))
        settings_before = (self.agent_dir / "settings.json").read_bytes()
        result = self._run_yes("--allow-missing-capabilities")
        axi = decode_axi(result.stdout)
        self.assertEqual((result.returncode, axi.get("outcome")), (0, "installed"),
                         f"the override lets an absent sandesh-pi proceed; "
                         f"stderr={result.stderr!r}")
        self.assertEqual(self._pi_runs(), [],
                         "--yes never runs a third-party `pi install`; nothing else is "
                         "missing, so pi must not run at all")
        self.assertEqual((self.agent_dir / "settings.json").read_bytes(), settings_before,
                         "Model B never writes Pi's settings.json")
        self.assertFalse((self.agent_dir / "npm" / "node_modules" / SANDESH_PI_PACKAGE).exists(),
                         "nothing materialised the package")
        self.assertEqual((parse_group_line(result.stderr, "harness:") or {}).get(SANDESH_PI_ID),
                         "absent", f"the harness: line reports it; stderr={result.stderr!r}")
        self.assertEqual(self._capabilities().get(SANDESH_PI_ID), "absent",
                         "§S1: its verdict is recorded in [capabilities]")
        hits = [w for w in axi.get("warnings", []) if SANDESH_PI_REMEDIATION in w]
        self.assertEqual(len(hits), 1,
                         f"one warning names `{SANDESH_PI_REMEDIATION}`; {axi.get('warnings')!r}")

    def test_a_listed_and_installed_sandesh_pi_is_recorded_detected_without_a_warning(self):
        make_provisioned_agent_dir(self.agent_dir)
        settings = (self.agent_dir / "settings.json").read_text(encoding="utf-8")
        self.assertIn(npm_spec(SANDESH_PI_PACKAGE), settings,
                      "fixture precondition: the provisioned dir lists sandesh-pi")
        result = self._run_yes()
        axi = decode_axi(result.stdout)
        self.assertEqual((result.returncode, axi.get("outcome")), (0, "installed"), result.stderr)
        self.assertEqual(self._pi_runs(), [])
        self.assertEqual(self._capabilities().get(SANDESH_PI_ID), "detected",
                         f"§S1: recorded like any other tier-1 row; stderr={result.stderr!r}")
        self.assertEqual([w for w in axi.get("warnings", []) if SANDESH_PI_PACKAGE in w], [],
                         "a detected extension draws no warning")


# ---------------------------------------------------------------------------
# §S2 — init reads the installation's verdicts
# ---------------------------------------------------------------------------

class _InitSandboxCase(unittest.TestCase):
    """A per-test sandbox for an in-process ``scaffold.run_init``: an empty
    Pi agent dir (a probe would find every extension absent) and a home
    WITHOUT Crucible's manifest (a probe would find Crucible absent), so a
    verdict the run reports can only have come from ``install.toml``."""

    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="modelb-cr045-init-")).resolve()
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.modelb_home = self.root / "modelb-home"
        self.modelb_home.mkdir()
        self.home = make_home(self.root / "home", crucible_manifest=False)
        self.agent_dir = make_agent_dir(self.root / "pi-agent", packages=[], on_disk=())

    def write_install(self, capabilities: dict | None, deps: dict | None = None) -> None:
        if deps is None:
            deps = {"uv": "detected", "sandesh": "detected", "crucible": "detected"}
        (self.modelb_home / "install.toml").write_text(
            _install_toml_text(self.modelb_home, capabilities, deps), encoding="utf-8")

    def run_init(self, target: Path, *, schema: Path = SCHEMA_PATH, **fields):
        """``scaffold.run_init`` in process; returns ``(rc, axi, stderr)``."""
        args = argparse.Namespace(
            name=NAME, token=TOKEN, acronym=ACRONYM, mode="solo",
            repo_shape="standalone", stacks=STACK, owner=OWNER,
            target=str(target), dry_run=False, no_commit=True, register=False,
        )
        for key, value in fields.items():
            setattr(args, key, value)
        out, err = io.StringIO(), io.StringIO()
        with (
            mock.patch.object(scaffold, "PROJECT_SCHEMA_PATH", schema),
            mock.patch.dict(os.environ, {"HOME": str(self.home),
                                         AGENT_DIR_ENV: str(self.agent_dir)}),
            contextlib.redirect_stdout(out), contextlib.redirect_stderr(err),
        ):
            rc = scaffold.run_init(args, self.modelb_home)
        return rc, decode_axi(out.getvalue()), err.getvalue()

    def tools_of(self, target: Path, **fields) -> tuple[dict, str]:
        rc, axi, err = self.run_init(target, **fields)
        self.assertEqual((rc, axi.get("ok")), (0, True), f"init must succeed; stderr={err!r}")
        tools = axi.get("tools")
        if not isinstance(tools, dict):
            self.fail(f"§S2: the init envelope carries a `tools` map; got {axi!r}")
        return tools, err


class InitToolsEnvelopeTest(_InitSandboxCase):
    """§S2 AC: the envelope's ``tools`` maps every tier-1 and tier-2 row, plus
    the project's stack's ``crucible-client`` and ``toolchain``, to
    ``present``, ``absent`` or ``unknown`` — read from ``install.toml``."""

    def test_tools_maps_exactly_every_requirement_row_id(self):
        self.write_install(_complete_verdicts())
        tools, _err = self.tools_of(self.root / "proj")
        self.assertEqual(frozenset(tools), EXPECTED_TOOL_IDS,
                         "§S2: one key per row id — no per-probe key such as python.client")
        self.assertEqual(frozenset(tools), frozenset(r["id"] for r in REQUIREMENTS),
                         "every declared row — tier 1, tier 2 and the stack rows — is mapped")

    def test_detected_everywhere_maps_every_tool_to_present(self):
        self.write_install(_complete_verdicts("detected"))
        tools, _err = self.tools_of(self.root / "proj")
        self.assertEqual(tools, dict.fromkeys(EXPECTED_TOOL_IDS, PRESENT))

    def test_installed_counts_as_present(self):
        verdicts = _complete_verdicts("detected")
        # MIGRATED at CR-MDB-047 C1 RED (§S1: watcher -> worktree).
        for key in ("worktree", "sandesh", f"{STACK}.xmlrunner", f"{STACK}.client"):
            verdicts[key] = "installed"
        self.write_install(verdicts)
        tools, _err = self.tools_of(self.root / "proj")
        for tool in ("worktree", "sandesh", "toolchain", "crucible-client"):
            with self.subTest(tool=tool):
                self.assertEqual(tools.get(tool), PRESENT, tools)

    def test_absent_and_unknown_verdicts_are_reported_as_recorded(self):
        verdicts = _complete_verdicts("detected")
        verdicts.update({"permissions": "absent", "gh": "absent", "jq": "unknown",
                         f"{STACK}.client": "absent", SANDESH_PI_ID: "unknown"})
        self.write_install(verdicts)
        tools, _err = self.tools_of(self.root / "proj")
        expected = dict.fromkeys(EXPECTED_TOOL_IDS, PRESENT)
        expected.update({"permissions": ABSENT, "gh": ABSENT, "jq": UNKNOWN,
                         "crucible-client": ABSENT, SANDESH_PI_ID: UNKNOWN})
        self.assertEqual(tools, expected)

    def test_toolchain_is_absent_when_one_of_the_stacks_probes_is_absent(self):
        verdicts = _complete_verdicts("detected")
        verdicts[f"{STACK}.coverage"] = "absent"
        self.write_install(verdicts)
        tools, _err = self.tools_of(self.root / "proj")
        self.assertEqual(tools.get("toolchain"), ABSENT, tools)
        self.assertEqual(tools.get("python3"), PRESENT,
                         "the tier-2 python3 row is its own verdict, not the toolchain's")

    def test_dry_run_reports_the_same_tools_map_and_writes_nothing(self):
        verdicts = _complete_verdicts("detected")
        verdicts.update({"lean-ctx": "absent", "gh": "unknown"})
        self.write_install(verdicts)
        dry_target = self.root / "dry"
        dry_tools, _err = self.tools_of(dry_target, dry_run=True)
        self.assertFalse(dry_target.exists(), "--dry-run writes nothing")
        real_tools, _err = self.tools_of(self.root / "real")
        self.assertEqual(dry_tools, real_tools, "real and --dry-run runs report alike")
        self.assertEqual((dry_tools.get("lean-ctx"), dry_tools.get("gh"),
                          dry_tools.get("dispatch")), (ABSENT, UNKNOWN, PRESENT))

    def test_the_cli_init_envelope_carries_tools(self):
        """The production entry: ``modelb-axi --yes init`` in a subprocess with
        ``HOME``, ``MODELB_HOME``, ``XDG_DATA_HOME`` and ``PI_CODING_AGENT_DIR``
        all in the sandbox."""
        verdicts = _complete_verdicts("detected")
        verdicts["bash"] = "absent"
        self.write_install(verdicts)
        xdg = self.root / "xdg"
        xdg.mkdir()
        target = self.root / "cli-proj"
        result = run_module(
            "--yes", "init", "--name", NAME, "--token", TOKEN, "--acronym", ACRONYM,
            "--mode", "solo", "--repo-shape", "standalone", "--stacks", STACK,
            "--owner", OWNER, "--target", str(target), "--no-commit",
            "--modelb-home", str(self.modelb_home),
            env_overrides={"HOME": str(self.home), "MODELB_HOME": str(self.modelb_home),
                           "XDG_DATA_HOME": str(xdg), AGENT_DIR_ENV: str(self.agent_dir)},
            timeout=180,
        )
        axi = decode_axi(result.stdout)
        self.assertEqual((result.returncode, axi.get("ok")), (0, True), result.stderr)
        expected = dict.fromkeys(EXPECTED_TOOL_IDS, PRESENT)
        expected["bash"] = ABSENT
        self.assertEqual(axi.get("tools"), expected, f"stdout={result.stdout!r}")


class InitNeverProbesTest(_InitSandboxCase):
    """§S2 AC "runs no probe": every verdict below CONTRADICTS the sandboxed
    machine — the agent dir lists no extension, the home has no Crucible
    manifest, and ``python3`` is on this PATH — so only a read of
    ``install.toml`` reports them as recorded. The probe entry points are
    also watched and must not be called."""

    def test_recorded_verdicts_win_over_what_a_probe_would_find(self):
        self.assertIsNotNone(shutil.which("python3"), "precondition: python3 is on PATH")
        verdicts = _complete_verdicts("detected")
        verdicts["python3"] = "absent"
        self.write_install(verdicts)
        names = (
            "modelb_axi.preflight.run_preflight",
            "modelb_axi.capabilities.probe_harness",
            "modelb_axi.capabilities.load_crucible_clients",
            "modelb_axi.capabilities.probe_crucible_client",
            "modelb_axi.toolchains.probe_toolchains",
        )
        watched: dict[str, mock.MagicMock] = {}
        with contextlib.ExitStack() as stack:
            for name in names:
                watched[name] = stack.enter_context(mock.patch(
                    name, side_effect=AssertionError(f"init probed via {name}")))
            tools, err = self.tools_of(self.root / "proj")
        self.assertEqual(
            {k: tools.get(k) for k in ("lean-ctx", "dispatch", SANDESH_PI_ID, "crucible",
                                       "crucible-client", "python3")},
            {"lean-ctx": PRESENT, "dispatch": PRESENT, SANDESH_PI_ID: PRESENT,
             "crucible": PRESENT, "crucible-client": PRESENT, "python3": ABSENT},
            "§S2: init reports the recorded verdicts, never a fresh probe",
        )
        self.assertEqual([name for name, m in watched.items() if m.called], [],
                         "§S2: init calls no probe")
        for prefix in ("harness:", "deps:", f"stack {STACK}:"):
            self.assertIsNone(parse_group_line(err, prefix),
                              f"no pre-flight `{prefix}` report on init's stderr; err={err!r}")


class InitUnknownVerdictsTest(_InitSandboxCase):
    """§S2 AC: a missing verdict is ``unknown`` — an ``install.toml`` written
    before ``[capabilities]`` existed, or a row the installation never
    probed — and stderr says to re-run the installer."""

    def test_an_install_toml_without_capabilities_gives_unknown_for_the_extensions(self):
        self.write_install(None)
        tools, err = self.tools_of(self.root / "proj")
        never_recorded = TIER1_IDS + ("python3", "bash", "gh", "jq", "direnv") + STACK_ROW_IDS
        self.assertEqual({k: tools.get(k) for k in never_recorded},
                         dict.fromkeys(never_recorded, UNKNOWN),
                         f"§S2: no [capabilities] means no verdict; tools={tools!r}")
        self.assertRegex(err, RERUN_INSTALLER_RE,
                         "§S2: stderr says to re-run the installer")

    def test_a_row_the_installation_never_probed_is_unknown(self):
        verdicts = _complete_verdicts("detected")
        del verdicts[SANDESH_PI_ID]
        self.write_install(verdicts)
        tools, err = self.tools_of(self.root / "proj")
        self.assertEqual(tools.get(SANDESH_PI_ID), UNKNOWN, tools)
        self.assertEqual(tools.get("lean-ctx"), PRESENT, "a recorded row keeps its verdict")
        self.assertRegex(err, RERUN_INSTALLER_RE)

    def test_a_stack_the_installation_never_probed_gives_unknown_stack_rows(self):
        verdicts = {k: v for k, v in _complete_verdicts("detected").items()
                    if not k.startswith(f"{STACK}.")}
        self.write_install(verdicts)
        tools, err = self.tools_of(self.root / "proj")
        self.assertEqual({k: tools.get(k) for k in STACK_ROW_IDS},
                         dict.fromkeys(STACK_ROW_IDS, UNKNOWN), tools)
        self.assertRegex(err, RERUN_INSTALLER_RE)

    def test_complete_verdicts_draw_no_re_run_notice(self):
        verdicts = _complete_verdicts("detected")
        verdicts["gh"] = "absent"
        self.write_install(verdicts)
        _tools, err = self.tools_of(self.root / "proj")
        self.assertIsNone(RERUN_INSTALLER_RE.search(err),
                          f"every row has a verdict: nothing to re-run; err={err!r}")


# ---------------------------------------------------------------------------
# §S3 — a key conditional on a tool
# ---------------------------------------------------------------------------

class ConditionalSchemaKeyTest(_InitSandboxCase):
    """§S3 AC: ``load_schema`` rejects a ``when`` naming an undeclared id, and
    a ``when`` key is rendered only when its tool is present (§S2) — in the
    root ``.env`` and, for a ``root+sub`` key, each sub-project's."""

    def setUp(self):
        super().setUp()
        data = tomllib.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        self.table = next(k for k, v in data.items() if isinstance(v, list))

    def schema(self, when: str) -> Path:
        """The packaged schema plus ``TOOL_CHANNEL``, a derived ``root+sub``
        key carrying ``when = <when>`` (a TOML literal)."""
        path = self.root / "when-schema.toml"
        path.write_text(
            SCHEMA_PATH.read_text(encoding="utf-8")
            + f"\n[[{self.table}]]\n"
            'name = "TOOL_CHANNEL"\n'
            'description = "fixture: a key conditional on a tool"\n'
            "required = false\n"
            'file = ".env"\n'
            'scope = "root+sub"\n'
            'source = "derive"\n'
            'rule = "remove_whitespace"\n'
            'inputs = ["PROJECT_NAME"]\n'
            'validate = "non_empty"\n'
            'readers = ["fixture"]\n'
            f"when = {when}\n",
            encoding="utf-8",
        )
        return path

    def test_load_schema_accepts_a_declared_id_and_rejects_an_undeclared_one(self):
        entries = {e["name"]: e for e in scaffold.load_schema(self.schema('"lean-ctx"'))}
        self.assertEqual(entries["TOOL_CHANNEL"].get("when"), "lean-ctx",
                         "control: a declared requirement id loads")
        with self.assertRaises(scaffold.ScaffoldError) as ctx:
            scaffold.load_schema(self.schema('"no-such-tool-r45"'))
        message = str(ctx.exception)
        for word in ("TOOL_CHANNEL", "when", "no-such-tool-r45"):
            self.assertIn(word, message, f"the refusal names {word!r}; got {message!r}")

    def test_load_schema_rejects_a_when_that_is_not_a_requirement_id_string(self):
        with self.assertRaises(scaffold.ScaffoldError) as ctx:
            scaffold.load_schema(self.schema("1"))
        self.assertIn("TOOL_CHANNEL", str(ctx.exception))
        self.assertIn("when", str(ctx.exception))

    def test_init_refuses_an_undeclared_when_before_writing_anything(self):
        self.write_install(_complete_verdicts())
        target = self.root / "refused"
        rc, axi, err = self.run_init(target, schema=self.schema('"no-such-tool-r45"'),
                                     repo_shape="monorepo:a")
        self.assertEqual((rc, axi.get("ok")), (2, False), f"stderr={err!r}")
        self.assertIn("no-such-tool-r45", " ".join(axi.get("warnings", [])))
        self.assertFalse(target.exists(), "refused before anything is written")

    def test_a_when_key_is_rendered_only_when_its_tool_is_present(self):
        cases = {"detected": True, "installed": True, "absent": False,
                 "unknown": False, "missing": False}
        for verdict, rendered in cases.items():
            with self.subTest(verdict=verdict):
                verdicts = _complete_verdicts("detected")
                if verdict == "missing":
                    del verdicts["lean-ctx"]
                else:
                    verdicts["lean-ctx"] = verdict
                self.write_install(verdicts)
                target = self.root / f"proj-{verdict}"
                rc, axi, err = self.run_init(target, schema=self.schema('"lean-ctx"'),
                                             repo_shape="monorepo:a")
                self.assertEqual((rc, axi.get("ok")), (0, True), f"stderr={err!r}")
                root_env = parse_env_file(target / ".env")
                sub_env = parse_env_file(target / "a" / ".env")
                expected = DERIVED_CHANNEL if rendered else None
                self.assertEqual((root_env.get("TOOL_CHANNEL"), sub_env.get("TOOL_CHANNEL")),
                                 (expected, expected),
                                 f"lean-ctx={verdict}: root .env={root_env!r} a/.env={sub_env!r}")
                self.assertEqual(root_env.get("SANDESH_PROJECT"), DERIVED_CHANNEL,
                                 "control: an unconditional key is always rendered")

    def test_a_when_key_is_not_rendered_from_a_pre_capabilities_install_toml(self):
        self.write_install(None)
        target = self.root / "proj-pre036"
        rc, axi, err = self.run_init(target, schema=self.schema('"lean-ctx"'))
        self.assertEqual((rc, axi.get("ok")), (0, True), f"stderr={err!r}")
        text = (target / ".env").read_text(encoding="utf-8")
        self.assertNotIn("TOOL_CHANNEL", text, "nothing is set up for an unknown tool")
        self.assertRegex(err, RERUN_INSTALLER_RE)


if __name__ == "__main__":
    unittest.main()
