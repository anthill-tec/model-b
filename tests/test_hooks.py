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
   real `status` feed's stdout is a TOON-AXI envelope (a TOON `encode()`)
   shaped
   ``axi: {verb, ok, plans[]{cr,wave,status,activeCycleId}, lastClosedCr,
   count, help[], context{...}, warnings[]{code,detail}}``. Three DISTINCT
   exit-0 terminal states matter here: (a) board present, (b) no plan filed
   -- `ok:true`, empty `plans`/`count:0`, `warnings:[]` (no signal), (c)
   tolerant degrade -- `ok:true`, empty `plans`/`count:0`, but `warnings`
   carries a `{code:"status-unavailable"}` entry (THAT is the signal
   distinguishing (b) from (c), not emptiness alone). The fake status-feed
   fixtures below emit real `toon.encode()` output (Model B's own codec,
   `modelb_axi.toon`, CR-MDB-032 §S1) for exactly these three
   shapes, plus a fourth "hard-fail/absent" case (defense in depth -- the
   feed command itself is missing/broken, distinct from the feed
   CONTRACT-COMPLIANTLY reporting `status-unavailable`) that the hook must
   still degrade past on its own.

Sandbox: this module writes solely under `tempfile.mkdtemp()` scratch dirs and
never reads the real home. CR-MDB-032 §S2 dropped the module-level mtime
guard over the real `~/.claude/hooks/` tree: nothing here names that tree.

Stdlib only: unittest + subprocess + json + os + sys + shutil + stat + time +
tempfile + tomllib + pathlib.
"""

import ast
import io
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import tokenize
import tomllib
import unittest
from pathlib import Path

from tests._helpers import GIT_ISOLATION_ENV

REPO_ROOT = Path(__file__).resolve().parent.parent
HOOKS_SRC_DIR = REPO_ROOT / "hooks-src"
SCHEMA_MD = HOOKS_SRC_DIR / "schema.md"
SCRIPTS_DIR = HOOKS_SRC_DIR / "scripts"
AGENTS_MD = REPO_ROOT / "AGENTS.md"

# §S3 (CR-MDB-030, migrated this cycle): the five remaining imported
# Model-B-owned guard scripts + the new ambient-board-status (six protocol
# scripts total, AC2) -- the cycle-todo-naming guard retired under §S7
# (CR-MDB-030 C2, tests/test_hook_retirement.py owns that AC now; its
# retired identifier is spelled ONLY there, never here).
# MIGRATED (CR-MDB-062 §S2/§S8): the two new runner hooks join the roster --
# eight protocol scripts in all.
IMPORTED_SCRIPT_NAMES = [
    "block-direct-cargo-test",
    "block-direct-mvn-test",
    "block-direct-python-test",
    "block-direct-bun-test",
    "block-cr-completed-without-spec-update",
    "block-write-outside-worktree",
    "post-regression-disk-reminder",
]
ALL_SCRIPT_NAMES = IMPORTED_SCRIPT_NAMES + ["ambient-board-status"]


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

    def test_all_eight_protocol_scripts_exist_executable_and_clean_of_forbidden_references(self):
        self.assertEqual(len(ALL_SCRIPT_NAMES), 8)
        failures = []
        for name in ALL_SCRIPT_NAMES:
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
        # POSITIVE/EXACT -- zero failures across all eight scripts.
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


# ------------------------------------------- CR-MDB-066 §S5: the hardened payload prelude ----

#: CR-MDB-066 §S5 — the three hooks that take the runner hooks' payload prelude.
PRELUDE_HOOKS = (
    "block-cr-completed-without-spec-update",
    "block-write-outside-worktree",
    "post-regression-disk-reminder",
)
#: The worktree hook's dispatch signal and escape hatch: a hook run never inherits either, so
#: neither can allow a call before the payload is read (CR-MDB-066 AC6).
_WORKTREE_ENV = ("WF_WORKTREE_ROOT", "ALLOW_WRITE_OUTSIDE_WORKTREE")
#: The runner hooks' catch on the payload read (CR-MDB-066 §S5.1), as ``ast.unparse`` writes it.
_PRELUDE_CATCH = "(ValueError, OSError, RecursionError)"
#: The runner hooks' comment on that catch, whitespace-normalised across its comment lines.
_PRELUDE_COMMENT = ("bad JSON or UTF-8, a number past the digit limit, nesting past the "
                    "recursion limit")
#: The CR hook's command that reaches ``cwd`` (CR-MDB-066 AC6).
_COMPLETED_COMMIT = 'git commit -m "COMPLETED CR-X-1"'

#: A hook whose ``main`` has the pre-change catch and then, untyped, calls ``.get`` on
#: ``tool_input``, ``re.search`` on ``command`` and ``Path(cwd)`` (CR-MDB-066 AC6's proof).
_PRE_CHANGE_SCRIPT = '''\
import json
import re
import sys
from pathlib import Path


def main():
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, OSError):
        return 0  # unreadable payload -> fail open
    if not isinstance(payload, dict):
        return 0
    tool_input = payload.get("tool_input") or {}
    target = tool_input.get("command") or tool_input.get("path") or ""
    if payload.get("tool_name") == "bash":
        re.search(r"\\bgit\\s+commit\\b", target)
    cwd = payload.get("cwd")
    if cwd is not None:
        Path(cwd)
    return 0


sys.exit(main())
'''

#: The same hook with CR-MDB-066 §S5.1's prelude: the proof that a correct hook passes.
_HARDENED_SCRIPT = '''\
import json
import re
import sys
from pathlib import Path


def main():
    try:
        payload = json.load(sys.stdin)
    except (ValueError, OSError, RecursionError):
        # unreadable payload (bad JSON or UTF-8, a number past the digit limit, nesting past
        # the recursion limit) -> fail open
        return 0
    if not isinstance(payload, dict):
        return 0
    tool_input = payload.get("tool_input") or {}
    if not isinstance(tool_input, dict):
        return 0
    target = tool_input.get("command") or tool_input.get("path") or ""
    cwd = payload.get("cwd")
    if not isinstance(target, str) or (cwd is not None and not isinstance(cwd, str)):
        return 0
    if payload.get("tool_name") == "bash":
        re.search(r"\\bgit\\s+commit\\b", target)
    if cwd is not None:
        Path(cwd)
    return 0


sys.exit(main())
'''


def _hostile_payload_cases(hook, cwd):
    """CR-MDB-066 AC6's cases for ``hook``, as ``(label, stdin bytes, extra env)``: the four
    payloads of the runner hooks' ``_FailOpen.test_allows_a_hostile_payload_without_a_traceback``,
    non-UTF-8 stdin, a truthy non-dict ``tool_input``, a non-string ``command`` (the two bash
    hooks) and a non-string ``cwd`` reached by a command or path (the two block hooks)."""
    depth = 100_000
    cases = [
        ("open array", ("[" * depth).encode(), {}),
        ("closed array", ("[" * depth + "]" * depth).encode(), {}),
        ("nested object", ('{"a":' * depth + "1" + "}" * depth).encode(), {}),
        ("long number", ("1" * 5000).encode(), {}),
        ("non-UTF-8 stdin", b"\xff\xfe{", {"PYTHONIOENCODING": "utf-8:strict"}),
    ]
    tool = "write" if hook == "block-write-outside-worktree" else "bash"

    def payload(**fields):
        return json.dumps({"tool_name": tool, **fields}).encode()

    for value in (["x"], "x"):
        cases.append((f"tool_input {value!r}", payload(tool_input=value, cwd=str(cwd)), {}))
    if tool == "bash":
        cases.append(("command 5", payload(tool_input={"command": 5}, cwd=str(cwd)), {}))
    if hook == "block-cr-completed-without-spec-update":
        cases.append(("cwd 5", payload(tool_input={"command": _COMPLETED_COMMIT}, cwd=5), {}))
    elif hook == "block-write-outside-worktree":
        cases.append(("cwd 5", payload(tool_input={"path": "x"}, cwd=5), {}))
    return cases


def _run_hook_bytes(script, data, env_extra=None, proc_cwd=None):
    """Run ``script`` on the test's interpreter with the raw bytes ``data`` on stdin, the
    worktree hook's ``_WORKTREE_ENV`` variables removed from its environment, git's configuration
    isolated and ``env_extra`` set; stdout and stderr come back as bytes."""
    env = {k: v for k, v in os.environ.items() if k not in _WORKTREE_ENV}
    env.update(GIT_ISOLATION_ENV)
    env.update(env_extra or {})
    return subprocess.run([sys.executable, str(script)], input=data, capture_output=True,
                          timeout=30, env=env, cwd=proc_cwd)


def _hostile_payload_failures(script, cases, proc_cwd):
    """``{label: [problem, …]}`` for every case on which ``script`` does not allow cleanly (exit
    0, empty stdout, no ``Traceback`` on stderr); ``{}`` when it allows each one."""
    failures = {}
    for label, data, env in cases:
        res = _run_hook_bytes(script, data, env, proc_cwd)
        stdout = res.stdout.decode("utf-8", errors="replace")
        stderr = res.stderr.decode("utf-8", errors="replace")
        problems = []
        if "Traceback" in stderr:
            last = stderr.strip().splitlines()[-1] if stderr.strip() else ""
            problems.append(f"a traceback ({last})")
        if res.returncode != 0:
            problems.append(f"exit {res.returncode}")
        if stdout:
            problems.append(f"stdout {stdout[:200]!r}")
        if problems:
            failures[label] = problems
    return failures


def _prelude_findings(source):
    """Every way ``source`` misses CR-MDB-066 §S5.1's payload read, one finding per point; ``[]``
    when it keeps it: its top-level ``main`` reads the payload with ``json.load`` in one ``try``
    whose handler catches ``_PRELUDE_CATCH``, and its comments carry ``_PRELUDE_COMMENT``."""
    tree = ast.parse(source)
    mains = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "main"]
    if not mains:
        return ["no top-level main"]

    def reads_payload(node):
        return any(isinstance(c, ast.Call) and ast.unparse(c.func) == "json.load"
                   for stmt in node.body for c in ast.walk(stmt))

    reads = [t for t in ast.walk(mains[0]) if isinstance(t, ast.Try) and reads_payload(t)]
    findings = []
    if len(reads) != 1:
        findings.append(f"main reads the payload in {len(reads)} try statements, not one")
    else:
        catches = [ast.unparse(h.type) for h in reads[0].handlers if h.type is not None]
        if _PRELUDE_CATCH not in catches:
            findings.append(f"the payload read catches {catches}, not {_PRELUDE_CATCH}")
    comments = [tok.string.lstrip("#").strip()
                for tok in tokenize.generate_tokens(io.StringIO(source).readline)
                if tok.type == tokenize.COMMENT]
    if _PRELUDE_COMMENT not in " ".join(" ".join(comments).split()):
        findings.append("no runner-hook comment on the catch")
    return findings


class BlockHookHostilePayloadTest(unittest.TestCase):
    """CR-MDB-066 §S5.1 (AC6) — the three §S5 hooks take the runner hooks' payload prelude: run as
    a subprocess, each allows a hostile or type-confused payload (exit 0, empty stdout, no
    ``Traceback``). The harness is proved both ways on two temp scripts: the pre-change catch
    with untyped field reads raises on every case, the hardened prelude on none. §S7.3: each
    hook's docstring names the prelude."""

    maxDiff = None

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="modelb-hooks-hostile-")).resolve()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def _synthetic(self, name, body):
        path = self.tmp / name
        path.write_text(body, encoding="utf-8")
        return path

    def test_each_section_s5_hook_allows_every_hostile_payload_without_a_traceback(self):
        failures = {}
        for hook in PRELUDE_HOOKS:
            got = _hostile_payload_failures(SCRIPTS_DIR / hook,
                                            _hostile_payload_cases(hook, self.tmp), self.tmp)
            failures.update({f"{hook}: {label}": problems for label, problems in got.items()})
        self.assertEqual(failures, {}, "CR-MDB-066 §S5.1: a hook raised or did not allow")

    def test_the_harness_reports_a_traceback_for_every_case_on_the_pre_change_prelude(self):
        # Proof the harness bites: the pre-change catch raises on every case of every hook.
        script = self._synthetic("pre-change-hook", _PRE_CHANGE_SCRIPT)
        for hook in PRELUDE_HOOKS:
            cases = _hostile_payload_cases(hook, self.tmp)
            with self.subTest(hook=hook):
                got = _hostile_payload_failures(script, cases, self.tmp)
                self.assertEqual(sorted(got), sorted(label for label, _, _ in cases))
                untraced = [label for label, problems in got.items()
                            if not any(p.startswith("a traceback") for p in problems)]
                self.assertEqual(untraced, [], got)

    def test_the_harness_reports_nothing_on_the_hardened_prelude(self):
        # Proof a correct hook can pass: the hardened prelude allows every case of every hook.
        script = self._synthetic("hardened-hook", _HARDENED_SCRIPT)
        for hook in PRELUDE_HOOKS:
            with self.subTest(hook=hook):
                self.assertEqual(_hostile_payload_failures(
                    script, _hostile_payload_cases(hook, self.tmp), self.tmp), {})

    def test_the_case_list_is_exactly_the_specs_for_each_hook(self):
        # CR-MDB-066 AC6: `command` 5 for the two bash hooks, `cwd` 5 for the two block hooks.
        common = ["open array", "closed array", "nested object", "long number",
                  "non-UTF-8 stdin", "tool_input ['x']", "tool_input 'x'"]
        expected = {
            "block-cr-completed-without-spec-update": common + ["command 5", "cwd 5"],
            "block-write-outside-worktree": common + ["cwd 5"],
            "post-regression-disk-reminder": common + ["command 5"],
        }
        got = {hook: [label for label, _, _ in _hostile_payload_cases(hook, self.tmp)]
               for hook in PRELUDE_HOOKS}
        self.assertEqual(got, expected)

    def test_each_section_s5_hook_reads_the_payload_with_the_runner_hooks_catch_and_comment(self):
        failures = {hook: _prelude_findings((SCRIPTS_DIR / hook).read_text(encoding="utf-8"))
                    for hook in PRELUDE_HOOKS}
        self.assertEqual({h: f for h, f in failures.items() if f}, {},
                         "CR-MDB-066 §S5.1: the payload read is not the runner hooks'")

    def test_the_prelude_detector_passes_a_runner_hook_and_the_hardened_prelude(self):
        # Proof a correct source can pass: the runner hook the prelude comes from, and the
        # hardened synthetic hook.
        runner = (SCRIPTS_DIR / "block-direct-python-test").read_text(encoding="utf-8")
        self.assertEqual(_prelude_findings(runner), [])
        self.assertEqual(_prelude_findings(_HARDENED_SCRIPT), [])

    def test_the_prelude_detector_reports_the_pre_change_catch_and_comment(self):
        self.assertEqual(_prelude_findings(_PRE_CHANGE_SCRIPT), [
            "the payload read catches ['(json.JSONDecodeError, OSError)'], not "
            "(ValueError, OSError, RecursionError)",
            "no runner-hook comment on the catch",
        ])
        self.assertEqual(_prelude_findings("def other():\n    pass\n"), ["no top-level main"])

    def test_each_section_s5_hook_docstring_names_the_prelude_and_cites_the_section(self):
        # CR-MDB-066 §S7.3 (AC9): each docstring cites CR-MDB-066 §S5 and names the prelude.
        failures = []
        for hook in PRELUDE_HOOKS:
            doc = ast.get_docstring(ast.parse(
                (SCRIPTS_DIR / hook).read_text(encoding="utf-8"))) or ""
            flat = " ".join(doc.split())
            if "CR-MDB-066 §S5" not in flat:
                failures.append(f"{hook}: does not cite CR-MDB-066 §S5")
            if "prelude" not in flat.lower():
                failures.append(f"{hook}: does not name the payload prelude")
        self.assertEqual(failures, [])


class WorktreeHookCwdFallbackTest(unittest.TestCase):
    """CR-MDB-066 §S5.1 — ``block-write-outside-worktree`` keeps its ``os.getcwd()`` fallback for
    an absent ``cwd`` and allows on a present non-string one, run as a subprocess whose own
    working directory is a real registered worktree ``<repo>/.worktrees/CR-X-1``, with the
    dispatch signal and the escape hatch removed from its environment."""

    OUTSIDE = "/etc/modelb-hooks-outside-fixture.txt"

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="modelb-hooks-cwd-")).resolve()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        repo = self.tmp / "repo"
        repo.mkdir()
        env = {**os.environ, **GIT_ISOLATION_ENV}
        for args in (("init", "-q", "-b", "main"),
                     ("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                      "commit", "-q", "--allow-empty", "-m", "init"),
                     ("worktree", "add", "-q", "-b", "cr", ".worktrees/CR-X-1", "main")):
            res = subprocess.run(["git", *args], cwd=repo, env=env, capture_output=True,
                                 text=True, timeout=30)
            self.assertEqual(res.returncode, 0, f"precondition: git {args[0]}: {res.stderr}")
        self.worktree = (repo / ".worktrees" / "CR-X-1").resolve()

    def _run(self, payload):
        return _run_hook_bytes(SCRIPTS_DIR / "block-write-outside-worktree",
                               json.dumps(payload).encode(), proc_cwd=self.worktree)

    def test_an_absent_cwd_falls_back_to_the_process_cwd_and_blocks_a_write_outside(self):
        # Passes on arrival: it pins the fallback §S5.1 keeps.
        res = self._run({"tool_name": "write", "tool_input": {"path": self.OUTSIDE}})
        self.assertNotIn(b"Traceback", res.stderr, res.stderr)
        self.assertEqual(res.returncode, 2, res.stderr)
        self.assertEqual(json.loads(res.stdout).get("decision"), "block")

    def test_a_present_non_string_cwd_allows_and_never_falls_back(self):
        for cwd in (5, ["x"], {"a": 1}):
            with self.subTest(cwd=cwd):
                res = self._run({"tool_name": "write", "tool_input": {"path": self.OUTSIDE},
                                 "cwd": cwd})
                self.assertNotIn(b"Traceback", res.stderr, res.stderr)
                self.assertEqual((res.returncode, res.stdout), (0, b""), res.stderr)


def _toon_encode(obj):
    """Encode `obj` via Model B's own TOON codec (`modelb_axi.toon`, the one
    hand-maintained codec since CR-MDB-022), so the fake status-feed fixtures
    below emit real TOON-AXI envelopes rather than a hand-rolled approximation
    of the format. No Crucible checkout is loaded (CR-MDB-032 \u00a7S1)."""
    from modelb_axi import toon
    return toon.encode(obj)


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



# CR-MDB-062 §S8 -- the two documents that state the script roster: schema.md's
# security-class roster names every block-* script, and AGENTS.md's Key
# Directories row states the real hook-script count.

#: AGENTS.md's ``hooks-src/`` row: "``scripts/`` (N executable stdin/exit protocol scripts".
AGENTS_HOOK_SCRIPT_COUNT = re.compile(r"`scripts/` \((\d+) executable stdin/exit protocol scripts")
#: schema.md's normative section holding the security-class roster.
SECURITY_CLASS_HEADING = "## Security-class definition"


def _security_class_roster(schema_text):
    """The ``block-*`` script names written as code spans in schema.md's security-class
    section (from its heading to the next ``## `` heading)."""
    start = schema_text.find(SECURITY_CLASS_HEADING)
    if start < 0:
        return []
    end = schema_text.find("\n## ", start + len(SECURITY_CLASS_HEADING))
    section = schema_text[start:] if end < 0 else schema_text[start:end]
    return sorted(set(re.findall(r"`(block-[a-z0-9-]+)`", section)))


class HookScriptRosterDocsTest(unittest.TestCase):
    """CR-MDB-062 §S8: schema.md's security-class roster and AGENTS.md's script count."""

    def test_the_roster_reader_reads_only_the_security_class_section(self):
        sample = ("# Schema\n\n`block-outside` here.\n\n## Security-class definition (v1)\n\n"
                  "The roster: `block-a-test`,\n`block-b`, and `ambient-x`.\n\n"
                  "## Neutral payload\n\n`block-after` there.\n")
        self.assertEqual(_security_class_roster(sample), ["block-a-test", "block-b"])
        self.assertEqual(_security_class_roster("## Other\n`block-a`\n"), [])

    def test_schema_security_class_roster_names_all_six_block_scripts(self):
        expected = sorted(name for name in ALL_SCRIPT_NAMES if name.startswith("block-"))
        self.assertEqual(len(expected), 6, "precondition: six block-* scripts in the roster")
        roster = _security_class_roster(SCHEMA_MD.read_text(encoding="utf-8"))
        self.assertEqual(roster, expected,
                         "schema.md's security-class roster must name every block-* script")

    def test_the_count_reader_reads_the_agents_md_row(self):
        row = ("| `hooks-src/` | `schema.md` (neutral schema v1) + `scripts/` (8 executable "
               "stdin/exit protocol scripts, no file extension) |")
        self.assertEqual(AGENTS_HOOK_SCRIPT_COUNT.findall(row), ["8"])
        self.assertEqual(AGENTS_HOOK_SCRIPT_COUNT.findall(row.replace("8 executable", "eight")), [])

    def test_agents_md_states_the_real_hook_script_count(self):
        on_disk = sorted(p.name for p in SCRIPTS_DIR.iterdir() if p.is_file())
        self.assertEqual(on_disk, sorted(ALL_SCRIPT_NAMES),
                         "hooks-src/scripts/ must hold exactly the eight protocol scripts")
        counts = AGENTS_HOOK_SCRIPT_COUNT.findall(AGENTS_MD.read_text(encoding="utf-8"))
        self.assertEqual(counts, [str(len(ALL_SCRIPT_NAMES))],
                         "AGENTS.md must state the hook-script count exactly once, as 8")


if __name__ == "__main__":
    unittest.main()
