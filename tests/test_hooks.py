"""RED-phase tests for CR-MDB-015 cycle C1 (§S2 neutral hook-definition
schema + §S3 shared protocol script library).

Written before any of §S2/§S3's production code lands on this branch:
`hooks-src/` does not exist yet, so every structural assertion below (schema
doc, the seven protocol scripts) fails cleanly against the current tree, and
every behavioural (subprocess) test fails at the `assertTrue(path.is_file())`
guard before it ever tries to invoke a script that isn't there yet. The
`modelb_axi.hooks` module referenced by the schema-validation tests also does
not exist yet -- those imports are done INSIDE each test method (never at
module scope), mirroring the pattern already used by
`tests/test_installer_assets.py::SkillBundleDiscoveryGuardTest`, so a missing
module fails only that one test rather than killing collection of this whole
file.

PINNED CONTRACTS (RED-authored, since none of this exists in code yet):

1. Validation entry point (AC1): ``modelb_axi.hooks.validate_schema(instance:
   dict) -> list[str]``. Returns an empty list for a valid schema instance;
   otherwise one error string per problem, each prefixed ``"<field>: ..."``
   (e.g. ``"event: ..."``, ``"fail_direction: ..."``) so a test can assert
   *which* field failed without over-pinning exact wording.

   Security-class pin: the §S2 spec text requires `fail_direction` "for
   security-class" hooks, but the six schema fields (event, matcher, command,
   tier, timeout, fail_direction) carry no explicit security/class flag --
   `tier` is only core|extended|harness-specific. This RED pass pins
   "security-class" as: the hook's `command` names one of the six imported
   BLOCKING guard scripts (the `block-*` roster below) -- as opposed to a
   purely informational hook like `ambient-board-status`, which never blocks
   and so never needs a fail-direction intent. GREEN should implement
   `validate_schema` against this pin; if the eventual schema.md documents a
   different security-class signal, that is a spec amendment, not a silent
   substitution.

2. Protocol script location + naming (AC2): `hooks-src/scripts/<name>`, name
   WITHOUT a `.sh` suffix -- exactly the bare names the CR spec's §S3 lists
   (`block-direct-cargo-test`, ...). The deployed `~/.claude/hooks/*.sh`
   files are the READ-ONLY import/normalization source, not the hooks-src/
   target name.

3. `ambient-board-status` status-feed override (AC3): pins
   `MODELB_STATUS_CMD` as the env var naming an executable to invoke for the
   board status feed, instead of a hardcoded `<stack>-crucible.py status`
   discovery path -- the same dependency-injection seam already used by
   `tests/test_installer.py::_write_fake_executable` for `uv`/`sandesh`
   fixtures. When unset, absent, or failing, the hook must still exit 0 FAST
   with a degradation note (a SessionStart hook must never block a session).

   Envelope shape pin: per `STATUS-CONTRACT.md` DOCUMENT VERSION 2.0.0
   (MIGRATED CR-MDB-019 from 1.0.0 / CR-CRU-035; the number is the
   contract document's own semver, never a Crucible product release), a
   real `status` feed's stdout is a TOON-AXI envelope (`clients/toon.py`
   `encode()`) shaped
   ``axi: {verb, ok, plans[]{cr,wave,status,activeCycleId}, lastClosedCr,
   count, help[], context{...}, warnings[]{code,detail}}``. Three DISTINCT
   exit-0 terminal states matter here: (a) board present, (b) no plan filed
   -- `ok:true`, empty `plans`/`count:0`, `warnings:[]` (no signal), (c)
   tolerant degrade -- `ok:true`, empty `plans`/`count:0`, but `warnings`
   carries a `{code:"status-unavailable"}` entry (THAT is the signal
   distinguishing (b) from (c), not emptiness alone). The fake status-feed
   fixtures below emit real `toon.encode()` output (imported directly from
   the pinned `crucible:clients/toon.py` path) for exactly these three
   shapes, plus a fourth "hard-fail/absent" case (defense in depth -- the
   feed command itself is missing/broken, distinct from the feed
   CONTRACT-COMPLIANTLY reporting `status-unavailable`) that the hook must
   still degrade past on its own.

Sandbox guard: this module only ever READS `~/.claude/hooks/` (the pinned
read-only import baseline for §S3) and writes solely under `hooks-src/` (not
created by this RED pass) and `tempfile.mkdtemp()` scratch dirs. A
module-level mtime-snapshot guard (reused from
`tests/test_installer.py`'s AC7 pattern) fails loudly if anything in this
file touched the real `~/.claude/hooks/` tree.

Stdlib only: unittest + subprocess + json + os + sys + shutil + stat + time +
tempfile + tomllib + pathlib.
"""

import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import tomllib
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
HOOKS_SRC_DIR = REPO_ROOT / "hooks-src"
SCHEMA_MD = HOOKS_SRC_DIR / "schema.md"
SCRIPTS_DIR = HOOKS_SRC_DIR / "scripts"

# §S3 (CR-MDB-030, migrated this cycle): the five remaining imported
# Model-B-owned guard scripts + the new ambient-board-status (six protocol
# scripts total, AC2) -- the cycle-todo-naming guard retired under §S7
# (CR-MDB-030 C2, tests/test_hook_retirement.py owns that AC now; its
# retired identifier is spelled ONLY there, never here).
IMPORTED_SCRIPT_NAMES = [
    "block-direct-cargo-test",
    "block-direct-mvn-test",
    "block-cr-completed-without-spec-update",
    "block-write-outside-worktree",
    "post-regression-disk-reminder",
]
ALL_SIX_SCRIPT_NAMES = IMPORTED_SCRIPT_NAMES + ["ambient-board-status"]

CLAUDE_HOOKS_DIR = Path.home() / ".claude" / "hooks"

# ---------------------------------------------------------------------------
# Sandbox guard (reused pattern from tests/test_installer.py's AC7
# mtime-snapshot fixture): ~/.claude/hooks/ is a READ-ONLY import baseline
# for this CR -- nothing in this file may write to it.
# ---------------------------------------------------------------------------


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
    _guard_snapshot_before = _snapshot_mtimes([CLAUDE_HOOKS_DIR])


def tearDownModule():
    after = _snapshot_mtimes([CLAUDE_HOOKS_DIR])
    if after != _guard_snapshot_before:
        all_paths = set(_guard_snapshot_before) | set(after)
        changed = sorted(
            str(p) for p in all_paths
            if _guard_snapshot_before.get(p) != after.get(p)
        )
        raise AssertionError(
            "sandbox guard violated: the real ~/.claude/hooks tree (read-only "
            "§S3 import baseline) changed mtime while running "
            f"tests/test_hooks.py; changed paths (up to 20): {changed[:20]}"
        )


def _run_script(name, payload, env_overrides=None, timeout=5):
    """Invoke hooks-src/scripts/<name> Claude-contract style: JSON payload on
    stdin, allow => exit 0 (optionally silent), block => exit 2 with
    {"decision": "block", "reason": "..."} JSON on stdout."""
    path = SCRIPTS_DIR / name
    env = dict(os.environ)
    if env_overrides:
        env.update(env_overrides)
    return subprocess.run(
        [str(path)], input=json.dumps(payload), capture_output=True,
        text=True, timeout=timeout, env=env,
    )


class SchemaDefinitionTest(unittest.TestCase):
    """AC1 -- hooks-src/schema.md (v1, six fields) + validate_schema."""

    def test_schema_md_documents_v1_and_all_six_field_names(self):
        self.assertTrue(
            SCHEMA_MD.is_file(), f"expected §S2 schema doc at {SCHEMA_MD}"
        )
        content = SCHEMA_MD.read_text(encoding="utf-8")
        self.assertIn("v1", content, "schema.md must name its version, v1")
        for field in ("event", "matcher", "command", "tier", "timeout", "fail_direction"):
            self.assertIn(
                field, content,
                f"schema.md must document the '{field}' field (six total)",
            )

    def _validate(self, instance):
        sys.path.insert(0, str(REPO_ROOT))
        try:
            from modelb_axi import hooks as hooks_module
        finally:
            sys.path.remove(str(REPO_ROOT))
        return hooks_module.validate_schema(instance)

    def test_valid_toml_instance_round_trips_and_validates_clean(self):
        # ambient-board-status is informational (non-blocking), so it is not
        # security-class per the RED pin above -- fail_direction may be
        # omitted and the instance must still validate clean.
        toml_text = (
            'event = "session-start"\n'
            'matcher = "*"\n'
            'command = "ambient-board-status"\n'
            'tier = "core"\n'
            'timeout = 3\n'
        )
        instance = tomllib.loads(toml_text)
        errors = self._validate(instance)
        self.assertEqual(errors, [], f"expected a clean valid instance; got {errors}")

    def test_invalid_toml_instance_unknown_event_is_rejected(self):
        toml_text = (
            'event = "on-file-save"\n'  # not in the universal event set
            'matcher = "bash"\n'
            'command = "block-direct-cargo-test"\n'
            'tier = "core"\n'
            'timeout = 5\n'
            'fail_direction = "closed"\n'
        )
        instance = tomllib.loads(toml_text)
        errors = self._validate(instance)
        self.assertTrue(
            any(e.startswith("event:") for e in errors),
            f"expected an 'event:'-prefixed error for the unknown event; got {errors}",
        )

    def test_invalid_toml_instance_missing_fail_direction_on_security_class_is_rejected(self):
        # block-write-outside-worktree is a blocking guard script -> security-
        # class per the RED pin above -- fail_direction is REQUIRED.
        toml_text = (
            'event = "pre-tool-use"\n'
            'matcher = "write|edit"\n'
            'command = "block-write-outside-worktree"\n'
            'tier = "core"\n'
            'timeout = 5\n'
        )
        instance = tomllib.loads(toml_text)
        errors = self._validate(instance)
        self.assertTrue(
            any(e.startswith("fail_direction:") for e in errors),
            f"expected a 'fail_direction:'-prefixed error (required for a "
            f"security-class/blocking command); got {errors}",
        )


class ProtocolScriptLibraryStructureTest(unittest.TestCase):
    """AC2 structural pin: all six SURVIVING scripts exist, are executable,
    and are clean of the forbidden WORKFLOW_CYCLE_ID / .claude/scripts
    references. The cycle-todo-naming guard retired under \u00a7S7 (CR-MDB-030
    C2) -- its own nonexistence is tests/test_hook_retirement.py's job, not
    this structural pin's."""

    def test_all_six_protocol_scripts_exist_executable_and_clean_of_forbidden_references(self):
        failures = []
        for name in ALL_SIX_SCRIPT_NAMES:
            path = SCRIPTS_DIR / name
            if not path.is_file():
                failures.append(f"{name}: missing at {path}")
                continue
            mode = path.stat().st_mode
            if not (mode & stat.S_IXUSR):
                failures.append(f"{name}: not executable (mode={oct(mode)})")
            text = path.read_text(encoding="utf-8")
            if "WORKFLOW_CYCLE_ID" in text:
                failures.append(f"{name}: contains forbidden WORKFLOW_CYCLE_ID reference")
            if ".claude/scripts" in text:
                failures.append(f"{name}: contains forbidden .claude/scripts client path")
        # POSITIVE/EXACT -- zero failures across all six scripts.
        self.assertEqual(failures, [], "\n".join(failures))


class BlockDirectCargoTestScriptTest(unittest.TestCase):
    """AC2 behavioural -- block-direct-cargo-test: blocks a direct `cargo
    test` invocation in a Rust project; allows a rust-crucible.py wrapper
    invocation. MIGRATED (CR-MDB-030 \u00a7S3, this cycle): the stdin contract's
    `tool_name` moved from the Claude Code vocabulary (`Bash`) to the
    neutral schema's (`bash`) -- the script now gates on the neutral name
    (mirrors the deployed ~/.claude/hooks/block-direct-cargo-test.sh
    contract otherwise: tool_input.command/cwd)."""

    def setUp(self):
        self._tmp_rust = tempfile.mkdtemp(prefix="modelb-hooks-rust-")
        (Path(self._tmp_rust) / "Cargo.toml").write_text(
            "[package]\nname = \"fixture\"\n", encoding="utf-8"
        )

    def tearDown(self):
        shutil.rmtree(self._tmp_rust, ignore_errors=True)

    def test_blocks_direct_cargo_test_command_in_rust_project(self):
        path = SCRIPTS_DIR / "block-direct-cargo-test"
        self.assertTrue(path.is_file(), f"expected protocol script at {path}")
        result = _run_script(
            "block-direct-cargo-test",
            {
                "tool_name": "bash",
                "tool_input": {"command": "cargo test -p fixture"},
                "cwd": self._tmp_rust,
            },
        )
        self.assertEqual(
            result.returncode, 2,
            f"expected exit 2 (block) for a direct `cargo test`; got "
            f"{result.returncode}, stdout={result.stdout!r} stderr={result.stderr!r}",
        )
        payload = json.loads(result.stdout)
        self.assertEqual(payload.get("decision"), "block")
        self.assertIn("cargo", payload.get("reason", "").lower())

    def test_allows_wrapper_invocation(self):
        path = SCRIPTS_DIR / "block-direct-cargo-test"
        self.assertTrue(path.is_file(), f"expected protocol script at {path}")
        result = _run_script(
            "block-direct-cargo-test",
            {
                "tool_name": "bash",
                "tool_input": {
                    "command": "python3 rust-crucible.py test --crate fixture --agent x",
                },
                "cwd": self._tmp_rust,
            },
        )
        self.assertEqual(
            result.returncode, 0,
            f"expected exit 0 (allow) for the rust-crucible.py wrapper; got "
            f"{result.returncode}, stdout={result.stdout!r} stderr={result.stderr!r}",
        )


class BlockWriteOutsideWorktreeScriptTest(unittest.TestCase):
    """AC2 behavioural -- block-write-outside-worktree. MIGRATED (CR-MDB-030
    \u00a7S3, this cycle): the stdin contract's `tool_name` moved from the Claude
    Code vocabulary (`write`/`edit`/`notebookedit` predecessors) to the
    neutral schema's (`write`/`edit`), and the target path moved from
    `tool_input.file_path` to `tool_input.path` (plus `paths`, every path
    the call targets -- \u00a7S3's file-class shape); worktree root still
    resolves from $WF_WORKTREE_ROOT, the explicit dispatch-signal path (a)
    in the deployed script."""

    def setUp(self):
        self._tmp_wt = tempfile.mkdtemp(prefix="modelb-hooks-worktree-")

    def tearDown(self):
        shutil.rmtree(self._tmp_wt, ignore_errors=True)

    def test_blocks_write_outside_declared_worktree(self):
        path = SCRIPTS_DIR / "block-write-outside-worktree"
        self.assertTrue(path.is_file(), f"expected protocol script at {path}")
        outside_target = "/etc/modelb-hooks-outside-fixture.txt"
        result = _run_script(
            "block-write-outside-worktree",
            {
                "tool_name": "write",
                "tool_input": {"path": outside_target, "paths": [outside_target]},
                "cwd": self._tmp_wt,
            },
            env_overrides={"WF_WORKTREE_ROOT": self._tmp_wt},
        )
        self.assertEqual(
            result.returncode, 2,
            f"expected exit 2 (block) for a write outside the declared "
            f"worktree; got {result.returncode}, stdout={result.stdout!r} "
            f"stderr={result.stderr!r}",
        )
        payload = json.loads(result.stdout)
        self.assertEqual(payload.get("decision"), "block")
        self.assertIn("worktree", payload.get("reason", "").lower())

    def test_allows_write_inside_declared_worktree(self):
        path = SCRIPTS_DIR / "block-write-outside-worktree"
        self.assertTrue(path.is_file(), f"expected protocol script at {path}")
        inside_target = str(Path(self._tmp_wt) / "src" / "main.py")
        result = _run_script(
            "block-write-outside-worktree",
            {
                "tool_name": "write",
                "tool_input": {"path": inside_target, "paths": [inside_target]},
                "cwd": self._tmp_wt,
            },
            env_overrides={"WF_WORKTREE_ROOT": self._tmp_wt},
        )
        self.assertEqual(
            result.returncode, 0,
            f"expected exit 0 (allow) for a write inside the declared "
            f"worktree; got {result.returncode}, stdout={result.stdout!r} "
            f"stderr={result.stderr!r}",
        )


class RemainingGuardScriptsSmokeTest(unittest.TestCase):
    """AC2 smoke allow-path for the three remaining guard scripts not given a
    dedicated block/allow pair above: existence + executable (covered by
    ProtocolScriptLibraryStructureTest) + a benign payload allows (exit 0).
    MIGRATED (CR-MDB-030 \u00a7S3/\u00a7S7, this cycle): `tool_name` moved to the
    neutral vocabulary (`bash`), and the cycle-todo-naming guard's entry is
    REMOVED -- it is retired under \u00a7S7, so nothing here asserts its
    behaviour anymore; tests/test_hook_retirement.py owns its nonexistence."""

    def setUp(self):
        self._tmp_cwd = tempfile.mkdtemp(prefix="modelb-hooks-benign-cwd-")

    def tearDown(self):
        shutil.rmtree(self._tmp_cwd, ignore_errors=True)

    def _benign_payloads(self):
        return {
            "block-direct-mvn-test": {
                "tool_name": "bash",
                "tool_input": {"command": "echo hello"},
                "cwd": self._tmp_cwd,
            },
            "block-cr-completed-without-spec-update": {
                "tool_name": "bash",
                "tool_input": {"command": "echo hello"},
                "cwd": self._tmp_cwd,
            },
            "post-regression-disk-reminder": {
                "tool_name": "bash",
                "tool_input": {"command": "echo hello"},
            },
        }

    def test_three_remaining_guards_allow_benign_payload(self):
        for name, payload in self._benign_payloads().items():
            with self.subTest(script=name):
                path = SCRIPTS_DIR / name
                self.assertTrue(path.is_file(), f"expected protocol script at {path}")
                result = _run_script(name, payload)
                self.assertEqual(
                    result.returncode, 0,
                    f"{name}: expected exit 0 (allow) on a benign payload; "
                    f"got {result.returncode}, stderr={result.stderr!r}",
                )


CRUCIBLE_CLIENTS_DIR = Path("/home/antonyj/Documents/data_projects/crucible/clients")


def _toon_encode(obj):
    """Encode `obj` via the REAL crucible:clients/toon.py codec (imported by
    path -- mirrors python-crucible.py's own lazy-by-path load), so the fake
    status-feed fixtures below emit byte-faithful TOON-AXI envelopes rather
    than a hand-rolled approximation of the format."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "test_hooks_toon", str(CRUCIBLE_CLIENTS_DIR / "toon.py")
    )
    assert spec is not None and spec.loader is not None, (
        f"could not build a module spec for {CRUCIBLE_CLIENTS_DIR / 'toon.py'}"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.encode(obj)


def _fake_status_feed_script(envelope_axi_fields):
    """Build the Python source for a fake $MODELB_STATUS_CMD executable that
    prints a STATUS-CONTRACT.md 2.0.0 TOON-AXI `status` envelope built from
    `envelope_axi_fields` (the inner `axi: {...}` dict) and exits 0 -- a real
    `status` feed NEVER exits non-zero (contract-compliant tolerant degrade)."""
    encoded = _toon_encode({"axi": envelope_axi_fields})
    return (
        "#!/usr/bin/env python3\n"
        "print(" + repr(encoded) + ")\n"
    )


class AmbientBoardStatusScriptTest(unittest.TestCase):
    """AC3 -- ambient-board-status. Pins $MODELB_STATUS_CMD as the override
    naming an executable status-feed command (dependency-injection seam,
    mirrors tests/test_installer.py::_write_fake_executable). Per
    STATUS-CONTRACT.md 2.0.0 (CR-MDB-019): a real feed always exits 0 and
    reports one of THREE definitive terminal states -- board present, no
    plan filed (empty + no warning), or tolerant-degrade `status-unavailable`
    (empty + a structured warning) -- and the hook must render each
    distinctly, never blurring "no plan" into "unavailable" or vice versa.
    A fourth, hook-local defense-in-depth case (the feed command itself is
    missing/broken) must ALSO degrade to exit 0 fast."""

    def setUp(self):
        self._tmp_bin = tempfile.mkdtemp(prefix="modelb-hooks-status-")

    def tearDown(self):
        shutil.rmtree(self._tmp_bin, ignore_errors=True)

    def _write_fake_status_cmd(self, body):
        path = Path(self._tmp_bin) / "fake-status"
        path.write_text(body, encoding="utf-8")
        path.chmod(0o755)
        return path

    def test_surfaces_cr_cycle_lastclosedcr_from_board_present_v2_envelope(self):
        """MIGRATED (CR-MDB-019 \u00a7S2): was
        ``test_surfaces_cr_cycle_lastruncr_from_board_present_v1_envelope``;
        the 2.0.0 envelope carries ``lastClosedCr`` (``lastRunCr`` is gone)
        and the hook prints it as ``last closed: <id>``."""
        path = SCRIPTS_DIR / "ambient-board-status"
        self.assertTrue(path.is_file(), f"expected protocol script at {path}")
        fake = self._write_fake_status_cmd(_fake_status_feed_script({
            "verb": "status",
            "ok": True,
            "plans": [{"cr": "CR-MDB-015", "wave": 3, "status": "open", "activeCycleId": "C1"}],
            "lastClosedCr": "CR-MDB-014",
            "count": 1,
            "help": ["cr-close --commit"],
            "context": {"projectKey": "fixture-project-key"},
            "warnings": [],
        }))
        result = _run_script(
            "ambient-board-status", {},
            env_overrides={"MODELB_STATUS_CMD": str(fake)},
        )
        self.assertEqual(
            result.returncode, 0,
            f"a SessionStart hook must never block; got {result.returncode}, "
            f"stderr={result.stderr!r}",
        )
        self.assertIn("CR-MDB-015", result.stdout, "expected the cr value surfaced")
        self.assertIn("C1", result.stdout, "expected the activeCycleId value surfaced")
        self.assertIn("last closed: CR-MDB-014", result.stdout,
                      "expected the lastClosedCr value surfaced as 'last closed: <id>'")

    def test_no_plan_filed_feed_surfaces_definitive_empty_note_not_unavailable(self):
        """MIGRATED (CR-MDB-019 \u00a7S3): the fixture carries ``lastClosedCr``
        (was ``lastRunCr``), and "no open plan" is no longer an accepted
        spelling -- it is now the DISTINCT all-plans-closed note, so the
        no-plan-filed state must say "no plan filed", never "no open plan"."""
        path = SCRIPTS_DIR / "ambient-board-status"
        self.assertTrue(path.is_file(), f"expected protocol script at {path}")
        # STATUS-CONTRACT.md 2.0.0 "no plan filed" state: ok:true, empty
        # plans/count:0, warnings:[] -- NO status-unavailable signal.
        fake = self._write_fake_status_cmd(_fake_status_feed_script({
            "verb": "status",
            "ok": True,
            "plans": [],
            "lastClosedCr": None,
            "count": 0,
            "help": ["plan-file --cr <CR-ID> --wave <n>"],
            "context": {"projectKey": "fixture-project-key"},
            "warnings": [],
        }))
        result = _run_script(
            "ambient-board-status", {},
            env_overrides={"MODELB_STATUS_CMD": str(fake)},
        )
        self.assertEqual(result.returncode, 0, f"got {result.returncode}, stderr={result.stderr!r}")
        lowered = result.stdout.lower()
        self.assertIn(
            "no plan filed", lowered,
            f"expected a definitive 'no plan filed' note; got {result.stdout!r}",
        )
        self.assertNotIn(
            "no open plan", lowered,
            "the 'no plan filed' state must not be blurred with the "
            "all-plans-closed 'no open plan' note (CR-MDB-019 \u00a7S3)",
        )
        self.assertNotIn(
            "unavailable", lowered,
            "the 'no plan filed' empty state (no warning) must NOT be "
            "blurred with the 'status-unavailable' degrade state",
        )

    def test_status_unavailable_warning_feed_surfaces_degradation_note_not_no_plan(self):
        path = SCRIPTS_DIR / "ambient-board-status"
        self.assertTrue(path.is_file(), f"expected protocol script at {path}")
        # STATUS-CONTRACT.md 2.0.0 tolerant-degrade state: ok:true, empty
        # plans/count:0 (same shape as "no plan filed"), but the
        # status-unavailable warning is the signal that distinguishes it.
        # MIGRATED (CR-MDB-019): the fixture carries lastClosedCr, not lastRunCr.
        fake = self._write_fake_status_cmd(_fake_status_feed_script({
            "verb": "status",
            "ok": True,
            "plans": [],
            "lastClosedCr": None,
            "count": 0,
            "help": ["check the Crucible server is running / reachable at http://localhost:3849"],
            "context": {"projectKey": "fixture-project-key"},
            "warnings": [{"code": "status-unavailable", "detail": "could not reach the Crucible server: Connection refused"}],
        }))
        result = _run_script(
            "ambient-board-status", {},
            env_overrides={"MODELB_STATUS_CMD": str(fake)},
        )
        self.assertEqual(result.returncode, 0, f"got {result.returncode}, stderr={result.stderr!r}")
        lowered = result.stdout.lower()
        self.assertTrue(
            any(kw in lowered for kw in ("unavailable", "degrad")),
            f"expected a degradation note naming the status-unavailable "
            f"signal; got {result.stdout!r}",
        )
        self.assertTrue(
            all(kw not in lowered for kw in ("no plan filed", "no open plan", "0 plans filed")),
            "the 'status-unavailable' degrade state must NOT be blurred "
            "with a definitive 'no plan filed' claim",
        )

    def test_degrades_fast_and_exits_zero_when_status_cmd_absent(self):
        # Defense-in-depth: the feed EXECUTABLE itself is missing/broken --
        # distinct from the feed contract-compliantly reporting
        # status-unavailable above. The hook must still never hang/block.
        path = SCRIPTS_DIR / "ambient-board-status"
        self.assertTrue(path.is_file(), f"expected protocol script at {path}")
        absent_cmd = str(Path(self._tmp_bin) / "does-not-exist")
        started = time.monotonic()
        result = _run_script(
            "ambient-board-status", {},
            env_overrides={"MODELB_STATUS_CMD": absent_cmd},
            timeout=5,
        )
        elapsed = time.monotonic() - started
        self.assertEqual(
            result.returncode, 0,
            f"an absent status feed must still degrade to exit 0 (never "
            f"block); got {result.returncode}, stderr={result.stderr!r}",
        )
        self.assertLess(
            elapsed, 3.0,
            f"degradation must be FAST and bounded; took {elapsed:.2f}s",
        )
        self.assertTrue(
            any(kw in result.stdout.lower() for kw in ("degrad", "unavailable", "no plan", "no server")),
            f"expected a degradation note in stdout; got {result.stdout!r}",
        )


if __name__ == "__main__":
    unittest.main()
