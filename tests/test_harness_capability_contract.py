"""Harness capability contract (CR-MDB-036 §S1–§S4).

The installer's pre-flight declares every requirement once (§S1), probes
Pi harness capabilities by what Pi actually loads — ``packages[]`` in
``<agent-dir>/settings.json`` AND ``npm/node_modules/<name>/package.json``
on disk (§S2), applies a per-capability policy (§S3), and records the
verdicts in ``install.toml`` (§S4).

Isolation (NON-NEGOTIABLE): every installer run here pins
``PI_CODING_AGENT_DIR`` (or a sandbox ``HOME`` whose ``.pi/agent`` is the
fixture) to a throw-away agent dir, and a sandbox ``HOME`` for the
Crucible manifest — the real ``~/.pi`` and ``~/.crucible`` are never read.
PATH is an isolated fake-bin dir (fake ``uv``/``sandesh``, plus marker
shims for ``pi``/``npm``/``crucible`` where a test must prove they were
NEVER executed).

Stdlib only.
"""

import ast
import os
import shutil
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path

from tests._helpers import decode_axi as _decode
from tests.pi_capability_sandbox import (
    AGENT_DIR_ENV,
    MODELB_PI_PACKAGE,
    THIRD_PARTY_TIER1,
    TIER1_PACKAGES,
    install_on_disk,
    make_agent_dir,
    make_home,
    make_provisioned_agent_dir,
    npm_spec,
    parse_group_line,
    write_settings,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
MODELB_AXI_DIR = REPO_ROOT / "modelb_axi"

ALL_STACKS = {"arduino", "bun", "python", "quarkus", "rust", "java"}
DISPATCH_PKG = TIER1_PACKAGES["dispatch"]
LEAN_CTX_PKG = TIER1_PACKAGES["lean-ctx"]
PERMISSIONS_PKG = TIER1_PACKAGES["permissions"]

_FAKE_UV = (
    "#!/bin/sh\n"
    'if [ "$1" = "tool" ] && [ "$2" = "install" ]; then exit 0; fi\n'
    'echo "uv 0.0.0-fake"\n'
    "exit 0\n"
)
_FAKE_SANDESH = "#!/bin/sh\necho sandesh-fake\nexit 0\n"


def _fake_uv_placing_sandesh(bin_dir: Path) -> str:
    """CR-MDB-037 \u00a7S5 migration: a confirmed Sandesh install is RE-PROBED
    before ``installed`` is recorded, so a fake ``uv`` standing for a
    successful install leaves ``sandesh`` on the sandbox PATH (the real
    ``chmod`` is resolved on the test's PATH)."""
    chmod = shutil.which("chmod")
    if chmod is None:
        raise unittest.SkipTest("chmod not available to build the uv shim")
    sandesh = Path(bin_dir) / "sandesh"
    return (
        "#!/bin/sh\n"
        'if [ "$1" = "tool" ] && [ "$2" = "install" ]; then\n'
        f"    printf '#!/bin/sh\\nexit 0\\n' > \"{sandesh}\"\n"
        f"    \"{chmod}\" 755 \"{sandesh}\"\n"
        "    exit 0\n"
        "fi\n"
        'echo "uv 0.0.0-fake"\n'
        "exit 0\n"
    )


def _marker_shim(marker: Path) -> str:
    """A fake binary that records every invocation in ``marker``."""
    return f'#!/bin/sh\nprintf \'%s\\n\' "$0 $*" >> "{marker}"\nexit 0\n'


def _write_exe(bin_dir: Path, name: str, body: str) -> Path:
    path = Path(bin_dir) / name
    path.write_text(body, encoding="utf-8")
    path.chmod(0o755)
    return path


def _requirements():
    """The §S1 declarative structure: ``modelb_axi.requirements.REQUIREMENTS``,
    a sequence of plain-dict rows keyed by the §S1 field names."""
    from modelb_axi.requirements import REQUIREMENTS
    return list(REQUIREMENTS)


def _row(requirement_id: str) -> dict:
    rows = [r for r in _requirements() if r.get("id") == requirement_id]
    if len(rows) != 1:
        raise AssertionError(
            f"§S1: exactly one requirement row with id {requirement_id!r} "
            f"expected; found {len(rows)}"
        )
    return rows[0]


class _SandboxedInstallerCase(unittest.TestCase):
    """Per-test sandbox: MODELB_HOME, target root, fake-bin PATH, sandbox
    HOME (no Crucible manifest unless a test adds one) and agent dir."""

    def setUp(self):
        self._root = Path(tempfile.mkdtemp(prefix="modelb-cr036-"))
        self.modelb_home = self._root / "modelb-home"
        self.target_root = self._root / "target"
        self.bin_dir = self._root / "bin"
        self.home = self._root / "home"
        self.agent_dir = self._root / "agent"
        for d in (self.modelb_home, self.target_root, self.bin_dir, self.home):
            d.mkdir(parents=True)
        _write_exe(self.bin_dir, "uv", _FAKE_UV)
        _write_exe(self.bin_dir, "sandesh", _FAKE_SANDESH)

    def tearDown(self):
        shutil.rmtree(self._root, ignore_errors=True)

    def run_installer(self, *extra, agent_dir_env=True, deploy=True, env_extra=None):
        env = dict(os.environ)
        existing_pp = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = str(REPO_ROOT) + (os.pathsep + existing_pp if existing_pp else "")
        env["PATH"] = str(self.bin_dir)
        env["HOME"] = str(self.home)
        env.pop(AGENT_DIR_ENV, None)
        if agent_dir_env:
            env[AGENT_DIR_ENV] = str(self.agent_dir)
        if env_extra:
            env.update(env_extra)
        args = ["--yes", "--harnesses", "pi", "--modelb-home", str(self.modelb_home)]
        if deploy:
            args += ["--target-root", str(self.target_root)]
        return subprocess.run(
            [sys.executable, "-m", "modelb_axi", *args, *extra],
            capture_output=True, text=True, timeout=60,
            stdin=subprocess.DEVNULL, env=env,
        )

    def harness_verdicts(self, result) -> dict:
        return self.group(result, "harness:")

    def group(self, result, prefix: str) -> dict:
        verdicts = parse_group_line(result.stderr, prefix)
        if verdicts is None:
            self.fail(
                f"§S3: the pre-flight must print a `{prefix} ...=<v>` line on "
                f"stderr; got exit={result.returncode} stderr={result.stderr!r}"
            )
        return verdicts

    def install_toml(self) -> dict:
        with open(self.modelb_home / "install.toml", "rb") as fh:
            return tomllib.load(fh)


# ---------------------------------------------------------------------------
# §S1 — the requirement, declared once
# ---------------------------------------------------------------------------

class RequirementsDeclarationTest(unittest.TestCase):
    """§S1 AC1/AC2: one declarative structure in ``modelb_axi/`` holds
    every §S1 row with all its fields; tier-1 rows list their tools."""

    _ROW_FIELDS = {"id", "tier", "provider", "policy", "scope", "asset_families", "remediation"}

    # (id, tier, policy, always-scoped) — straight from the §S1 table.
    _TABLE = [
        ("dispatch", 1, "required", True),
        ("lean-ctx", 1, "required", True),
        ("permissions", 1, "recommended", True),
        # CR-MDB-029 \u00a7S3: Model B's own Pi package.
        ("watcher", 1, "recommended", True),
        ("uv", 2, "required", True),
        ("sandesh", 2, "recommended", True),
        ("crucible", 2, "recommended", True),
        ("crucible-client", 2, "recommended", False),
        ("python3", 2, "recommended", True),
        ("bash", 2, "recommended", True),
        ("gh", 2, "recommended", True),
        ("jq", 2, "recommended", True),
    ]

    def test_every_row_carries_every_field(self):
        rows = _requirements()
        missing = {
            str(r.get("id")): sorted(self._ROW_FIELDS - set(r)) for r in rows
            if self._ROW_FIELDS - set(r)
        }
        self.assertEqual(missing, {}, f"§S1: rows missing fields: {missing}")
        blank_remediation = [r["id"] for r in rows if not str(r["remediation"]).strip()]
        self.assertEqual(blank_remediation, [], "§S1: every row names a remediation")

    def test_ids_are_unique(self):
        ids = [r.get("id") for r in _requirements()]
        self.assertEqual(len(ids), len(set(ids)), f"§S1: duplicate ids in {ids}")

    def test_tier_policy_and_scope_match_the_spec_table(self):
        for req_id, tier, policy, always in self._TABLE:
            with self.subTest(id=req_id):
                row = _row(req_id)
                self.assertEqual(row["tier"], tier)
                self.assertEqual(row["policy"], policy)
                if always:
                    self.assertEqual(row["scope"], "always")
                else:
                    self.assertNotEqual(
                        row["scope"], "always",
                        f"§S1: {req_id} is per selected stack, not always",
                    )

    def test_tier3_toolchain_rows_are_recommended_and_stack_scoped(self):
        tier3 = [r for r in _requirements() if r.get("tier") == 3]
        self.assertGreaterEqual(len(tier3), 1, "§S1: the tier-3 toolchain row is missing")
        for row in tier3:
            with self.subTest(id=row.get("id")):
                self.assertEqual(row["policy"], "recommended")
                self.assertNotEqual(row["scope"], "always")

    def test_only_dispatch_lean_ctx_and_uv_are_required(self):
        required = sorted(r["id"] for r in _requirements() if r.get("policy") == "required")
        self.assertEqual(required, ["dispatch", "lean-ctx", "uv"])

    def test_tier1_providers_are_the_exact_npm_packages(self):
        for cap, pkg in TIER1_PACKAGES.items():
            with self.subTest(id=cap):
                self.assertEqual(_row(cap)["provider"], pkg)

    def test_tier1_remediation_names_pi_install_npm_package(self):
        for cap, pkg in TIER1_PACKAGES.items():
            with self.subTest(id=cap):
                self.assertIn(f"pi install npm:{pkg}", _row(cap)["remediation"])

    def test_tier1_rows_name_the_asset_families_that_depend_on_them(self):
        for cap in TIER1_PACKAGES:
            with self.subTest(id=cap):
                families = _row(cap)["asset_families"]
                self.assertIsInstance(families, (list, tuple))
                self.assertGreaterEqual(len(families), 1)
                self.assertTrue(all(isinstance(f, str) and f.strip() for f in families))

    def test_tier2_providers_name_their_source(self):
        self.assertIn("sandesh-relay", _row("sandesh")["provider"])
        self.assertIn("crucible-clients.json", _row("crucible")["provider"])
        self.assertIn("-crucible.py", _row("crucible-client")["provider"])

    def test_dispatch_lists_exactly_the_three_subagent_tools(self):
        self.assertEqual(
            set(_row("dispatch")["tools"]),
            {"subagent", "get_subagent_result", "steer_subagent"},
        )
        self.assertEqual(len(_row("dispatch")["tools"]), 3)

    def test_lean_ctx_lists_lean_ctx_and_only_ctx_tools(self):
        tools = list(_row("lean-ctx")["tools"])
        for expected in ("lean_ctx", "ctx_shell", "ctx_read", "ctx_search"):
            self.assertIn(expected, tools)
        strays = [t for t in tools if t != "lean_ctx" and not t.startswith("ctx_")]
        self.assertEqual(strays, [], f"§S1: lean-ctx tools must be ctx_* or lean_ctx; got {tools}")

    def test_path_probed_rows_are_declared_by_their_probe_kind(self):
        """Finding 3: the tier-2 PATH tools are DATA \u2014 each row carries a
        probe kind, and the ``path`` rows are exactly python3/bash/gh/jq."""
        path_rows = sorted(r["id"] for r in _requirements() if r.get("probe") == "path")
        self.assertEqual(path_rows, ["bash", "gh", "jq", "python3"])
        for row in _requirements():
            if row.get("probe") == "path":
                self.assertEqual(row["tier"], 2, row)


# ---------------------------------------------------------------------------
# Tier-2 PATH tools and the per-stack client warning (cycle-91 findings 3/4)
# ---------------------------------------------------------------------------

class PathToolsRecordAndWarnTest(_SandboxedInstallerCase):
    """Finding 4: the tier-2 PATH tools are recorded in ``[capabilities]``
    and each absent one WARNs naming itself; a present one does not."""

    def test_path_tools_are_recorded_and_absent_ones_warn(self):
        make_provisioned_agent_dir(self.agent_dir)
        _write_exe(self.bin_dir, "gh", "#!/bin/sh\nexit 0\n")
        result = self.run_installer("--stacks", "rust")
        axi = _decode(result.stdout)
        self.assertEqual(axi.get("outcome"), "installed", result.stderr)
        caps = self.install_toml()["capabilities"]
        self.assertEqual(
            {t: caps.get(t) for t in ("python3", "bash", "gh", "jq")},
            {"python3": "absent", "bash": "absent", "gh": "detected", "jq": "absent"},
        )
        warnings = axi.get("warnings", [])
        for tool in ("python3", "bash", "jq"):
            with self.subTest(tool=tool):
                self.assertTrue(
                    any(w.startswith(f"{tool} not found on PATH") for w in warnings),
                    f"an absent {tool} WARNs naming itself; {warnings!r}",
                )
        self.assertFalse(any(w.startswith("gh ") for w in warnings), warnings)


class PathToolsAreDataDrivenTest(_SandboxedInstallerCase):
    """Finding 3: adding a tier-2 PATH tool touches only the requirements
    data \u2014 a new ``probe: path`` row is probed, recorded and warned by
    the unchanged pre-flight. In-process, with the row added by patching
    ``REQUIREMENTS`` wherever it is bound."""

    _NEW_ROW = {
        "id": "sentinel-tool-c92",
        "tier": 2,
        "provider": "the sentinel project",
        "policy": "recommended",
        "scope": "always",
        "probe": "path",
        "asset_families": ("sentinel scripts",),
        "remediation": "install sentinel-tool-c92 from the sentinel project",
    }

    def test_a_new_path_row_is_probed_recorded_and_warned(self):
        import contextlib
        import io
        from unittest import mock

        from modelb_axi import preflight, requirements

        make_provisioned_agent_dir(self.agent_dir)
        rows = (*requirements.REQUIREMENTS, dict(self._NEW_ROW))
        env = {"HOME": str(self.home), "PATH": str(self.bin_dir),
               AGENT_DIR_ENV: str(self.agent_dir)}
        warnings: list[str] = []
        patches = [mock.patch.object(requirements, "REQUIREMENTS", rows)]
        if hasattr(preflight, "REQUIREMENTS"):
            patches.append(mock.patch.object(preflight, "REQUIREMENTS", rows))
        with contextlib.ExitStack() as stack:
            for patch in patches:
                stack.enter_context(patch)
            stack.enter_context(mock.patch.dict(os.environ, env, clear=True))
            stack.enter_context(contextlib.redirect_stderr(io.StringIO()))
            code, _, caps = preflight.run_preflight(lambda _p: False, warnings)
        self.assertEqual(code, 0, warnings)
        self.assertEqual(caps.get("sentinel-tool-c92"), "absent", caps)
        self.assertTrue(
            any(w.startswith("sentinel-tool-c92 not found on PATH") for w in warnings),
            f"the new row WARNs with its remediation; {warnings!r}",
        )


class CrucibleClientWarningWordingTest(_SandboxedInstallerCase):
    """Finding 4: a selected stack whose Crucible client is absent (while
    the manifest is detected) WARNs \u2014 and the wording distinguishes a
    manifest with NO entry for the stack from an entry naming a missing
    file (which it names)."""

    def test_no_entry_and_missing_file_warn_distinctly(self):
        make_provisioned_agent_dir(self.agent_dir)
        make_home(self.home, crucible_manifest=True, dangling=("python",))
        dangling = str(self.home / ".crucible" / "clients" / "python-crucible.py")
        result = self.run_installer("--stacks", "python,rust")
        axi = _decode(result.stdout)
        self.assertEqual(axi.get("outcome"), "installed", result.stderr)
        warnings = axi.get("warnings", [])
        python = [w for w in warnings if w.startswith("stack python: client=")]
        rust = [w for w in warnings if w.startswith("stack rust: client=")]
        self.assertEqual(len(python), 1, warnings)
        self.assertEqual(len(rust), 1, warnings)
        self.assertIn(dangling, python[0], "the missing file is named")
        self.assertIn("does not exist", python[0])
        self.assertNotIn("no entry", python[0])
        self.assertIn("no entry", rust[0])
        self.assertNotIn("does not exist", rust[0])
        for w in python + rust:
            self.assertIn("Crucible's own installer", w)


class CrucibleVerdictSourceTest(_SandboxedInstallerCase):
    """§S1 AC3, as amended by the orchestrator (2026-09-24): ``crucible``
    is ``detected`` iff ``<home>/.crucible/crucible-clients.json`` exists
    and parses as JSON with a ``clients`` object; otherwise ``absent``;
    an unparseable manifest is ``unknown``. Never a ``crucible`` binary on
    PATH; no probe contacts a Crucible server."""

    def setUp(self):
        super().setUp()
        make_provisioned_agent_dir(self.agent_dir)

    def _crucible(self):
        result = self.run_installer()
        self.assertNotIn("Traceback", result.stderr)
        return self.group(result, "deps:").get("crucible"), result

    def test_manifest_with_clients_object_is_detected(self):
        make_home(self.home, crucible_manifest=True, clients=("python",))
        verdict, result = self._crucible()
        self.assertEqual(verdict, "detected", result.stderr)
        self.assertEqual(_decode(result.stdout).get("deps", {}).get("crucible"), "detected")

    def test_manifest_with_empty_clients_object_is_detected(self):
        make_home(self.home, crucible_manifest=True)
        verdict, result = self._crucible()
        self.assertEqual(verdict, "detected", result.stderr)

    def test_no_manifest_is_absent(self):
        verdict, result = self._crucible()
        self.assertEqual(verdict, "absent", result.stderr)

    def test_manifest_under_clients_subdir_only_is_absent(self):
        """The un-amended spec's location is NOT the manifest."""
        (self.home / ".crucible" / "clients").mkdir(parents=True)
        (self.home / ".crucible" / "clients" / "crucible-clients.json").write_text(
            '{"clients": {}}\n', encoding="utf-8",
        )
        verdict, result = self._crucible()
        self.assertEqual(verdict, "absent", result.stderr)

    def test_manifest_without_clients_object_is_absent(self):
        make_home(self.home, crucible_manifest=False,
                  manifest_text='{"version": "1", "clients": ["python"]}\n')
        verdict, result = self._crucible()
        self.assertEqual(verdict, "absent", result.stderr)

    def test_unparseable_manifest_is_unknown_without_crashing(self):
        make_home(self.home, crucible_manifest=False, manifest_text='{"clients": {')
        verdict, result = self._crucible()
        self.assertEqual(verdict, "unknown", result.stderr)

    def test_binary_on_path_without_manifest_is_absent_and_never_executed(self):
        marker = self._root / "crucible-ran"
        _write_exe(self.bin_dir, "crucible", _marker_shim(marker))
        result = self.run_installer()
        deps = self.group(result, "deps:")
        self.assertEqual(
            deps.get("crucible"), "absent",
            f"§S1: a `crucible` binary on PATH is not Crucible's released "
            f"clients; stderr={result.stderr!r}",
        )
        self.assertFalse(marker.exists(), "§S1: the probe must never execute a crucible binary")

    def test_no_modelb_axi_module_imports_a_network_client(self):
        offenders = []
        for path in sorted(MODELB_AXI_DIR.rglob("*.py")):
            if "_assets" in path.parts:
                continue
            offenders += [
                f"{path.name}:{hit}" for hit in _network_imports(path.read_text(encoding="utf-8"))
            ]
        self.assertEqual(offenders, [], "§S1: no probe contacts a Crucible server")

    def test_network_import_detector_bites(self):
        """The gate above is proven to bite, not assumed to work."""
        fixture = "import socket\nimport urllib.request\nfrom http import client\nimport json\n"
        self.assertEqual(
            _network_imports(fixture),
            ["1:socket", "2:urllib.request", "3:http"],
        )


def _network_imports(source: str) -> list[str]:
    """``lineno:module`` for every import of a network client module."""
    forbidden = {"socket", "urllib", "urllib.request", "http", "http.client"}
    hits = []
    for node in ast.walk(ast.parse(source)):
        names = []
        if isinstance(node, ast.Import):
            names = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            names = [node.module]
        hits += [f"{getattr(node, 'lineno', '?')}:{n}" for n in names if n in forbidden]
    return sorted(hits)


# ---------------------------------------------------------------------------
# §S2 — probe capability, not package presence
# ---------------------------------------------------------------------------

class HarnessProbeTest(_SandboxedInstallerCase):
    """§S2: one test per case. ``lean-ctx`` and ``permissions`` stay
    listed+on disk so each case isolates the ``dispatch`` verdict."""

    _OTHERS = [LEAN_CTX_PKG, PERMISSIONS_PKG]

    def _agent(self, dispatch_entries, dispatch_on_disk, extra_settings=None):
        make_agent_dir(
            self.agent_dir,
            packages=[npm_spec(p) for p in self._OTHERS] + list(dispatch_entries),
            on_disk=self._OTHERS + ([DISPATCH_PKG] if dispatch_on_disk else []),
            extra_settings=extra_settings,
        )

    def _dispatch(self, **run_kwargs):
        # No override flag: the harness line is printed BEFORE any policy
        # decision (§S3 AC4), so it is observable even when a missing
        # required capability then fails the pre-flight.
        result = self.run_installer(**run_kwargs)
        verdicts = self.harness_verdicts(result)
        self.assertEqual(verdicts.get("lean-ctx"), "detected", result.stderr)
        self.assertEqual(verdicts.get("permissions"), "detected", result.stderr)
        return verdicts.get("dispatch")

    def test_listed_and_on_disk_is_detected(self):
        self._agent(
            [npm_spec(DISPATCH_PKG)], True,
            # Other keys, even odd-shaped ones, are never read.
            extra_settings={"defaultModel": {"x": [1, 2]}, "extensions": 5},
        )
        self.assertEqual(self._dispatch(), "detected")

    def test_on_disk_but_unlisted_is_absent(self):
        self._agent([], True)
        # The measured `@pi-archimedes` shape: a dir on disk, empty, unlisted.
        (self.agent_dir / "npm" / "node_modules" / "@pi-archimedes").mkdir(parents=True)
        self.assertEqual(self._dispatch(), "absent")

    def test_listed_but_not_on_disk_is_absent(self):
        self._agent([npm_spec(DISPATCH_PKG)], False)
        self.assertEqual(self._dispatch(), "absent")

    def test_listed_with_package_dir_lacking_package_json_is_absent(self):
        self._agent([npm_spec(DISPATCH_PKG)], False)
        (self.agent_dir / "npm" / "node_modules" / DISPATCH_PKG).mkdir(parents=True)
        self.assertEqual(self._dispatch(), "absent")

    def test_versioned_npm_spec_is_matched(self):
        self._agent([npm_spec(DISPATCH_PKG, "1.4.2")], True)
        self.assertEqual(self._dispatch(), "detected")

    def test_object_form_with_source_is_matched(self):
        self._agent([{"source": npm_spec(DISPATCH_PKG)}], True)
        self.assertEqual(self._dispatch(), "detected")

    def test_object_form_with_empty_extensions_is_absent(self):
        self._agent([{"source": npm_spec(DISPATCH_PKG), "extensions": []}], True)
        self.assertEqual(self._dispatch(), "absent")

    def test_package_name_prefix_is_not_a_match(self):
        self._agent([npm_spec(DISPATCH_PKG + "-extra")], True)
        self.assertEqual(self._dispatch(), "absent")

    def test_no_npm_match_with_git_entry_is_unknown(self):
        self._agent(["git:github.com/gotgenes/pi-subagents"], False)
        self.assertEqual(self._dispatch(), "unknown")

    def test_no_npm_match_with_url_entry_is_unknown(self):
        self._agent(["https://example.invalid/pi-subagents.tgz"], False)
        self.assertEqual(self._dispatch(), "unknown")

    def test_malformed_json_is_unknown_for_every_capability_without_crashing(self):
        write_settings(self.agent_dir, '{"packages": ["npm:pi-lean-ctx",')
        for pkg in TIER1_PACKAGES.values():
            install_on_disk(self.agent_dir, pkg)
        result = self.run_installer()
        self.assertNotIn("Traceback", result.stderr)
        self.assertEqual(
            self.harness_verdicts(result),
            {"dispatch": "unknown", "lean-ctx": "unknown", "permissions": "unknown",
             "watcher": "unknown"},
        )

    def test_unrecognised_settings_shape_is_unknown(self):
        write_settings(self.agent_dir, [npm_spec(p) for p in TIER1_PACKAGES.values()])
        for pkg in TIER1_PACKAGES.values():
            install_on_disk(self.agent_dir, pkg)
        result = self.run_installer()
        self.assertNotIn("Traceback", result.stderr)
        self.assertEqual(
            self.harness_verdicts(result),
            {"dispatch": "unknown", "lean-ctx": "unknown", "permissions": "unknown",
             "watcher": "unknown"},
        )

    def test_env_var_agent_dir_wins_over_home_default(self):
        make_provisioned_agent_dir(self.home / ".pi" / "agent")
        make_agent_dir(self.agent_dir, packages=[], on_disk=())
        result = self.run_installer()
        self.assertEqual(
            self.harness_verdicts(result),
            {"dispatch": "absent", "lean-ctx": "absent", "permissions": "absent",
             "watcher": "absent"},
            f"§S2: $PI_CODING_AGENT_DIR must be read when set; stderr={result.stderr!r}",
        )

    def test_home_pi_agent_is_read_when_env_var_unset(self):
        make_provisioned_agent_dir(self.home / ".pi" / "agent")
        result = self.run_installer(agent_dir_env=False)
        self.assertEqual(
            self.harness_verdicts(result),
            {"dispatch": "detected", "lean-ctx": "detected", "permissions": "detected",
             "watcher": "detected"},
            f"§S2: ~/.pi/agent/settings.json is the default; stderr={result.stderr!r}",
        )


# ---------------------------------------------------------------------------
# §S3 — policy per capability
# ---------------------------------------------------------------------------

class RequiredCapabilityPolicyTest(_SandboxedInstallerCase):
    """§S3 AC1: a missing ``dispatch``/``lean-ctx`` fails the pre-flight
    naming the inert asset families; ``--allow-missing-capabilities``
    proceeds and is recorded."""

    def _assert_preflight_failed_for(self, cap):
        make_provisioned_agent_dir(self.agent_dir, omit=(cap,))
        result = self.run_installer()
        axi = _decode(result.stdout)
        self.assertNotEqual(result.returncode, 0, result.stderr)
        self.assertEqual(axi.get("outcome"), "preflight_failed", f"axi={axi!r}")
        self.assertEqual(self.harness_verdicts(result).get(cap), "absent")
        for family in _row(cap)["asset_families"]:
            self.assertIn(family, result.stderr, f"§S3: must name inert family {family!r}")
        self.assertTrue(
            any(cap in w for w in axi.get("warnings", [])),
            f"§S3: the envelope warnings must name {cap}; axi={axi!r}",
        )
        self.assertFalse((self.modelb_home / "install.toml").exists())
        self.assertEqual(list(self.target_root.iterdir()), [], "§S3: nothing deployed")

    def test_missing_dispatch_fails_preflight_naming_inert_families(self):
        self._assert_preflight_failed_for("dispatch")

    def test_missing_lean_ctx_fails_preflight_naming_inert_families(self):
        self._assert_preflight_failed_for("lean-ctx")

    def test_override_flag_proceeds_and_is_recorded_in_install_toml(self):
        make_provisioned_agent_dir(self.agent_dir, omit=("dispatch",))
        result = self.run_installer("--allow-missing-capabilities")
        axi = _decode(result.stdout)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(axi.get("outcome"), "installed", f"axi={axi!r}")
        self.assertTrue(any("dispatch" in w for w in axi.get("warnings", [])), f"axi={axi!r}")
        data = self.install_toml()
        self.assertIs(data["install"].get("allow_missing_capabilities"), True)
        self.assertEqual(data.get("capabilities", {}).get("dispatch"), "absent")

    def test_override_flag_is_documented_in_help(self):
        env = dict(os.environ)
        env["PYTHONPATH"] = str(REPO_ROOT)
        result = subprocess.run(
            [sys.executable, "-m", "modelb_axi", "--help"],
            capture_output=True, text=True, timeout=30, env=env,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("--allow-missing-capabilities", result.stdout)


class RecommendedAndUnknownPolicyTest(_SandboxedInstallerCase):
    """§S3 AC2: a missing ``permissions``, or an ``unknown`` verdict, WARNs
    with its consequence and continues."""

    def test_missing_permissions_warns_with_pi_install_and_continues(self):
        make_provisioned_agent_dir(self.agent_dir, omit=("permissions",))
        result = self.run_installer()
        axi = _decode(result.stdout)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(axi.get("outcome"), "installed", f"axi={axi!r}")
        self.assertEqual(self.harness_verdicts(result).get("permissions"), "absent")
        hits = [w for w in axi.get("warnings", []) if "permissions" in w]
        self.assertEqual(len(hits), 1, f"§S3: exactly one permissions warning; got {axi!r}")
        self.assertIn(f"pi install npm:{PERMISSIONS_PKG}", hits[0])
        self.assertEqual(self.install_toml()["capabilities"].get("permissions"), "absent")

    def test_unknown_dispatch_verdict_warns_and_continues(self):
        make_agent_dir(
            self.agent_dir,
            packages=[npm_spec(LEAN_CTX_PKG), npm_spec(PERMISSIONS_PKG),
                      "git:github.com/gotgenes/pi-subagents"],
            on_disk=[LEAN_CTX_PKG, PERMISSIONS_PKG],
        )
        result = self.run_installer()
        axi = _decode(result.stdout)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(axi.get("outcome"), "installed", f"axi={axi!r}")
        self.assertEqual(self.harness_verdicts(result).get("dispatch"), "unknown")
        self.assertTrue(any("dispatch" in w for w in axi.get("warnings", [])), f"axi={axi!r}")
        self.assertEqual(self.install_toml()["capabilities"].get("dispatch"), "unknown")


class NoThirdPartyInstallUnderYesTest(_SandboxedInstallerCase):
    """§S3 AC3: ``--yes`` against an agent dir lacking every extension
    installs no THIRD-PARTY extension and leaves ``settings.json``
    byte-identical.

    CR-MDB-029 §S3 migration: ``--yes`` now runs ``pi install`` for Model
    B's OWN package (``npm:@anthill-tec/modelb-pi``, the ``watcher``
    capability) — so the invariant is separated by package: no ``pi`` run
    ever names a third-party package (``THIRD_PARTY_TIER1``), no
    ``npm``/``npx``/``pnpm`` ever runs, and the only permitted run is
    ``pi install npm:@anthill-tec/modelb-pi``. The marker ``pi`` shim
    provisions nothing, so the agent dir stays untouched."""

    def setUp(self):
        super().setUp()
        self.settings = make_agent_dir(
            self.agent_dir, packages=["npm:some-unrelated-extension"],
            on_disk=["some-unrelated-extension"],
            extra_settings={"theme": "dark"},
        ) / "settings.json"
        self.marker = self._root / "installer-ran"
        for name in ("pi", "npm", "npx", "pnpm"):
            _write_exe(self.bin_dir, name, _marker_shim(self.marker))

    def _snapshot(self):
        return {
            str(p.relative_to(self.agent_dir)): (p.read_bytes() if p.is_file() else None)
            for p in self.agent_dir.rglob("*")
        }

    def _runs(self) -> list[str]:
        """Each recorded run as ``<binary basename> <args>``."""
        if not self.marker.exists():
            return []
        runs = []
        for line in self.marker.read_text(encoding="utf-8").splitlines():
            if line.strip():
                head, _, args = line.partition(" ")
                runs.append(f"{Path(head).name} {args}".strip())
        return runs

    def _assert_no_third_party_install(self, result, before_bytes, before_tree):
        self.assertEqual(self.harness_verdicts(result), {
            "dispatch": "absent", "lean-ctx": "absent", "permissions": "absent",
            "watcher": "absent",
        })
        self.assertEqual(self.settings.read_bytes(), before_bytes, "settings.json must be byte-identical")
        self.assertEqual(self._snapshot(), before_tree, "the agent dir must be untouched")
        runs = self._runs()
        third_party = [
            r for r in runs
            if not r.startswith("pi ")
            or any(TIER1_PACKAGES[cap] in r for cap in THIRD_PARTY_TIER1)
        ]
        self.assertEqual(
            third_party, [], f"§S3: --yes never runs a third-party install; ran: {runs!r}",
        )
        own = f"pi install npm:{MODELB_PI_PACKAGE}"
        self.assertTrue(
            all(r == own for r in runs),
            f"the only run --yes may make is `{own}`; ran: {runs!r}",
        )
        return runs

    def test_yes_run_without_override_installs_nothing(self):
        before_bytes, before_tree = self.settings.read_bytes(), self._snapshot()
        result = self.run_installer()
        self.assertEqual(_decode(result.stdout).get("outcome"), "preflight_failed")
        runs = self._assert_no_third_party_install(result, before_bytes, before_tree)
        # Whether Model B's own install runs before a required-capability
        # failure is unspecified; it runs at most once either way.
        self.assertLessEqual(len(runs), 1, runs)

    def test_yes_run_with_override_installs_nothing_and_names_pi_install(self):
        before_bytes, before_tree = self.settings.read_bytes(), self._snapshot()
        result = self.run_installer("--allow-missing-capabilities")
        self.assertEqual(_decode(result.stdout).get("outcome"), "installed", result.stderr)
        runs = self._assert_no_third_party_install(result, before_bytes, before_tree)
        self.assertEqual(
            runs, [f"pi install npm:{MODELB_PI_PACKAGE}"],
            "CR-MDB-029 §S3: with pi among the harnesses and Model B's own "
            "package absent, --yes runs its pi install exactly once",
        )
        for cap in THIRD_PARTY_TIER1:
            self.assertIn(f"pi install npm:{TIER1_PACKAGES[cap]}", result.stderr)


class InteractivePiInstallOfferTest(_SandboxedInstallerCase):
    """\u00a7S3 AC3 (amended at C1): for a missing extension an INTERACTIVE run
    offers Pi's own ``pi install npm:<package>`` and runs it only after an
    explicit yes; declining is recorded and the policy then applies. Under
    ``--yes`` it is never run (see :class:`NoThirdPartyInstallUnderYesTest`).

    Driven in-process on a scripted TTY (``tests.scripted_terminal``) with
    ``HOME``, ``PATH`` and ``PI_CODING_AGENT_DIR`` pinned to the sandbox; a
    recording ``pi`` shim on PATH proves what was (not) executed, and
    ``--stacks python`` with a succeeding ``python3`` shim keeps the
    toolchain pre-flight free of other offers."""

    def setUp(self):
        super().setUp()
        self.pi_marker = self._root / "pi-ran"
        _write_exe(
            self.bin_dir, "pi",
            f'#!/bin/sh\nprintf \'%s\\n\' "$*" >> "{self.pi_marker}"\nexit 0\n',
        )
        _write_exe(self.bin_dir, "python3", "#!/bin/sh\nexit 0\n")

    def _pi_runs(self) -> list[str]:
        if not self.pi_marker.exists():
            return []
        return [ln for ln in self.pi_marker.read_text(encoding="utf-8").splitlines() if ln]

    def _run(self, missing: str, answer: str, *extra):
        from tests.scripted_terminal import make_responder, run_installer_interactive
        make_provisioned_agent_dir(self.agent_dir, omit=(missing,))
        self.settings_before = (self.agent_dir / "settings.json").read_bytes()
        needle = f"pi install npm:{TIER1_PACKAGES[missing]}"
        responder = make_responder([(lambda chunk: needle in chunk, answer)])
        argv = ["--harnesses", "pi", "--modelb-home", str(self.modelb_home),
                "--target-root", str(self.target_root), "--stacks", "python", *extra]
        env = {"HOME": str(self.home), "PATH": str(self.bin_dir),
               AGENT_DIR_ENV: str(self.agent_dir)}
        result = run_installer_interactive(argv, env, responder)
        offers = result.offers_naming(needle)
        self.assertEqual(
            len(offers), 1,
            f"\u00a7S3: an interactive run must offer `{needle}` exactly once; "
            f"reads={result.reads!r} stderr={result.stderr!r}",
        )
        self.assertEqual(
            (self.agent_dir / "settings.json").read_bytes(), self.settings_before,
            "\u00a7S3: Model B never edits settings.json",
        )
        return result

    def test_explicit_yes_runs_pi_install_for_the_missing_extension(self):
        self._run("dispatch", "y")
        self.assertEqual(self._pi_runs(), [f"install npm:{DISPATCH_PKG}"])

    def test_blank_enter_is_not_an_explicit_yes(self):
        self._run("dispatch", "")
        self.assertEqual(self._pi_runs(), [], "\u00a7S3: only an explicit yes runs pi install")

    def test_declining_is_recorded_and_the_recommended_policy_applies(self):
        result = self._run("permissions", "n")
        self.assertEqual(self._pi_runs(), [])
        axi = _decode(result.stdout)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(axi.get("outcome"), "installed", f"axi={axi!r}")
        toml_text = (self.modelb_home / "install.toml").read_text(encoding="utf-8")
        declined = any(
            "declin" in w.lower() and (PERMISSIONS_PKG in w or "permissions" in w)
            for w in axi.get("warnings", [])
        ) or ("declin" in toml_text.lower() and "permissions" in toml_text)
        self.assertTrue(declined, f"\u00a7S3: the decline must be recorded; axi={axi!r}")
        self.assertEqual(self.install_toml()["capabilities"].get("permissions"), "absent")

    def test_declining_a_required_extension_then_fails_the_preflight(self):
        result = self._run("lean-ctx", "n")
        self.assertEqual(self._pi_runs(), [])
        self.assertNotEqual(result.returncode, 0, result.stderr)
        self.assertEqual(_decode(result.stdout).get("outcome"), "preflight_failed")


class PiInstallReprobeTest(_SandboxedInstallerCase):
    """Re-probe rule (\u00a7S3): after a confirmed ``pi install`` exits 0, that
    one capability is re-probed \u2014 ``installed`` only if Pi now loads it,
    else ``absent`` with a warning naming where it was expected. The ``pi``
    shim stands in for Pi: in one case it lists and materialises the
    package (as Pi would), in the other it does nothing."""

    def setUp(self):
        super().setUp()
        self.pi_marker = self._root / "pi-ran"
        _write_exe(
            self.bin_dir, "pi",
            f'#!/bin/sh\nprintf \'%s\\n\' "$*" >> "{self.pi_marker}"\nexit 0\n',
        )
        _write_exe(self.bin_dir, "python3", "#!/bin/sh\nexit 0\n")

    def _pi_runs(self) -> list[str]:
        if not self.pi_marker.exists():
            return []
        return [ln for ln in self.pi_marker.read_text(encoding="utf-8").splitlines() if ln]

    def _pi_provisions(self):
        provisioned = make_provisioned_agent_dir(self._root / "provisioned")
        cp = shutil.which("cp")
        if cp is None:
            self.skipTest("cp not available to build the pi shim")
        _write_exe(self.bin_dir, "pi", (
            "#!/bin/sh\n"
            f'printf \'%s\\n\' "$*" >> "{self.pi_marker}"\n'
            f'{cp} -R "{provisioned}/." "{self.agent_dir}/"\n'
            "exit 0\n"
        ))

    def _run_interactive(self, missing: str):
        from tests.scripted_terminal import make_responder, run_installer_interactive
        make_provisioned_agent_dir(self.agent_dir, omit=(missing,))
        needle = f"pi install npm:{TIER1_PACKAGES[missing]}"
        argv = ["--harnesses", "pi", "--modelb-home", str(self.modelb_home),
                "--target-root", str(self.target_root), "--stacks", "python"]
        env = {"HOME": str(self.home), "PATH": str(self.bin_dir),
               AGENT_DIR_ENV: str(self.agent_dir)}
        return run_installer_interactive(
            argv, env, make_responder([(lambda chunk: needle in chunk, "y")]),
        )

    def test_pi_install_that_provides_the_extension_records_installed(self):
        self._pi_provisions()
        result = self._run_interactive("permissions")
        self.assertEqual(self._pi_runs(), [f"install npm:{PERMISSIONS_PKG}"])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.install_toml()["capabilities"].get("permissions"), "installed")
        axi = _decode(result.stdout)
        self.assertFalse(
            [w for w in axi.get("warnings", []) if w.startswith("permissions=")],
            f"an installed extension draws no policy warning; {axi!r}",
        )

    def test_pi_install_that_leaves_it_unloaded_records_absent_naming_where(self):
        result = self._run_interactive("permissions")
        self.assertEqual(self._pi_runs(), [f"install npm:{PERMISSIONS_PKG}"])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.install_toml()["capabilities"].get("permissions"), "absent")
        axi = _decode(result.stdout)
        hits = [
            w for w in axi.get("warnings", [])
            if PERMISSIONS_PKG in w and "settings.json" in w and "node_modules" in w
        ]
        self.assertTrue(hits, f"the warning names where Pi was expected to load it; {axi!r}")


class PreflightReportLinesTest(_SandboxedInstallerCase):
    """§S3 AC4: one line per group on stderr, in order — ``harness:``,
    then ``deps:``, then one ``stack <name>:`` line per selected stack —
    before any remediation."""

    def setUp(self):
        super().setUp()
        make_provisioned_agent_dir(self.agent_dir)
        make_home(self.home, crucible_manifest=True, clients=("python",))

    def test_harness_line_is_exact_and_precedes_deps_line(self):
        result = self.run_installer()
        self.assertIn(
            "harness: dispatch=detected lean-ctx=detected permissions=detected "
            "watcher=detected",
            result.stderr,
        )
        self.assertIn("deps: uv=detected sandesh=detected crucible=detected", result.stderr)
        harness_at = result.stderr.find("harness: ")
        self.assertNotEqual(harness_at, -1, result.stderr)
        self.assertLess(harness_at, result.stderr.index("deps: "))
        self.assertEqual(
            sum(1 for ln in result.stderr.splitlines() if ln.startswith("harness:")), 1,
        )
        self.assertNotIn("harness: ", result.stdout)

    def test_report_lines_precede_the_sandesh_remediation(self):
        (self.bin_dir / "sandesh").unlink()
        # CR-MDB-037 \u00a7S5 migration: `installed` needs the re-probe to find it.
        _write_exe(self.bin_dir, "uv", _fake_uv_placing_sandesh(self.bin_dir))
        result = self.run_installer()
        stderr = result.stderr
        pre = stderr.find("deps: uv=detected sandesh=absent")
        post = stderr.find("deps: uv=detected sandesh=installed")
        self.assertNotEqual(pre, -1, stderr)
        self.assertNotEqual(post, -1, stderr)
        harness_at = stderr.find("harness: ")
        self.assertNotEqual(harness_at, -1, f"no harness: line; stderr={stderr!r}")
        self.assertLess(harness_at, pre)
        stack_idx = [i for i, ln in enumerate(stderr.splitlines()) if ln.startswith("stack ")]
        lines = stderr.splitlines()
        post_line = next(i for i, ln in enumerate(lines) if "sandesh=installed" in ln)
        self.assertTrue(stack_idx, f"no `stack <name>:` lines; stderr={stderr!r}")
        self.assertLess(max(stack_idx), post_line, "stack lines precede remediation")

    def test_one_stack_line_per_selected_stack_with_client_verdict(self):
        # CR-MDB-036 C2 migration (\u00a7S7/\u00a7S8): lines follow the SELECTION,
        # not every supported stack.
        result = self.run_installer("--stacks", "python,rust")
        lines = [ln for ln in result.stderr.splitlines() if ln.startswith("stack ")]
        names = [ln.split(":", 1)[0][len("stack "):] for ln in lines]
        self.assertEqual(sorted(names), ["python", "rust"], f"stack lines: {lines}")
        deps_at = result.stderr.index("deps: ")
        self.assertTrue(all(result.stderr.index(ln) > deps_at for ln in lines))
        python = self.group(result, "stack python:")
        rust = self.group(result, "stack rust:")
        self.assertEqual(python.get("client"), "detected", lines)
        self.assertEqual(rust.get("client"), "absent", lines)


class CrucibleClientPerStackVerdictTest(_SandboxedInstallerCase):
    """§S1 ``crucible-client``, as amended by the orchestrator (2026-09-24):
    per stack, ``detected`` iff the manifest's ``clients[<key>]`` names an
    existing file; key = the stack name, except quarkus and java -> ``mvn``;
    no manifest -> ``absent``. Read from each ``stack <name>:`` line's
    ``client=`` verdict (all six stacks selected by default)."""

    def setUp(self):
        super().setUp()
        make_provisioned_agent_dir(self.agent_dir)

    def _clients(self) -> dict:
        result = self.run_installer()
        self.assertNotIn("Traceback", result.stderr)
        return {s: self.group(result, f"stack {s}:").get("client") for s in sorted(ALL_STACKS)}

    def test_existing_listed_clients_detected_dangling_and_unlisted_absent(self):
        make_home(self.home, crucible_manifest=True, clients=("python", "mvn"),
                  dangling=("rust",))
        self.assertEqual(self._clients(), {
            "python": "detected", "quarkus": "detected", "java": "detected",
            "rust": "absent", "bun": "absent", "arduino": "absent",
        })

    def test_quarkus_and_java_resolve_through_the_mvn_key_only(self):
        make_home(self.home, crucible_manifest=True, clients=("quarkus", "java", "bun"))
        clients = self._clients()
        self.assertEqual(clients["quarkus"], "absent", clients)
        self.assertEqual(clients["java"], "absent", clients)
        self.assertEqual(clients["bun"], "detected", clients)

    def test_no_manifest_means_every_client_absent_even_with_files_on_disk(self):
        make_home(self.home, crucible_manifest=False,
                  clients=("python", "mvn", "rust", "bun", "arduino"))
        self.assertEqual(set(self._clients().values()), {"absent"})


# ---------------------------------------------------------------------------
# §S4 — record the verdicts
# ---------------------------------------------------------------------------

class InstallTomlCapabilitiesRecordTest(_SandboxedInstallerCase):
    """§S4: ``[capabilities]``, ``[install].stacks`` and the override flag
    (only when used) round-trip; a pre-036 ``install.toml`` still loads."""

    def test_capabilities_and_stacks_round_trip_through_install_toml(self):
        make_provisioned_agent_dir(self.agent_dir, omit=("permissions",))
        make_home(self.home, crucible_manifest=False)
        result = self.run_installer()
        self.assertEqual(result.returncode, 0, result.stderr)
        from modelb_axi.config import load_install_toml
        data = load_install_toml(self.modelb_home)
        caps = data.get("capabilities")
        if not isinstance(caps, dict):
            self.fail(f"§S4: [capabilities] missing; got {data!r}")
        self.assertEqual(
            {k: caps.get(k) for k in TIER1_PACKAGES},
            {"dispatch": "detected", "lean-ctx": "detected", "permissions": "absent",
             "watcher": "detected"},
        )
        self.assertEqual(caps.get("uv"), "detected")
        self.assertEqual(caps.get("crucible"), "absent")
        stacks = data["install"].get("stacks")
        self.assertIsInstance(stacks, list)
        self.assertEqual(sorted(stacks), sorted(ALL_STACKS))
        self.assertEqual(len(stacks), len(ALL_STACKS))
        self.assertNotIn("allow_missing_capabilities", data["install"])

    def _write_pre036(self):
        (self.modelb_home / "install.toml").write_text(
            "[install]\n"
            'version = "0.1.0"\n'
            'harnesses = ["pi"]\n'
            f'asset_root = "{REPO_ROOT}"\n'
            f'target_root = "{self.target_root}"\n'
            f'skills_dir = "{self.target_root}/.agents/skills"\n'
            f'hooks_scripts_dir = "{self.target_root}/.agents/hooks/scripts"\n'
            f'tool_scripts_dir = "{self.target_root}/.agents/scripts"\n'
            "\n[deps]\n"
            'uv = "detected"\nsandesh = "detected"\ncrucible = "absent"\n'
            "\n[[files]]\n"
            'path = ".agents/skills/crucible/SKILL.md"\n'
            'sha256 = "' + "0" * 64 + '"\n',
            encoding="utf-8",
        )

    def test_pre036_install_toml_still_loads(self):
        self._write_pre036()
        from modelb_axi.config import load_install_toml, load_manifest_hashes
        data = load_install_toml(self.modelb_home)
        self.assertEqual(data["install"]["harnesses"], ["pi"])
        self.assertNotIn("capabilities", data)
        self.assertEqual(
            load_manifest_hashes(self.modelb_home),
            {".agents/skills/crucible/SKILL.md": "0" * 64},
        )

    def test_reinstall_over_pre036_install_toml_gains_capabilities(self):
        self._write_pre036()
        make_provisioned_agent_dir(self.agent_dir)
        result = self.run_installer("--reinstall")
        self.assertEqual(result.returncode, 0, result.stderr)
        data = self.install_toml()
        self.assertEqual(data.get("capabilities", {}).get("dispatch"), "detected")
        self.assertEqual(sorted(data["install"].get("stacks", [])), sorted(ALL_STACKS))


if __name__ == "__main__":
    unittest.main()
