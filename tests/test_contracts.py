"""RED-phase tests for CR-MDB-009 (contracts/: the AXI evolution interface).

These tests assert the acceptance criteria of CR-MDB-009 SS2-SS5 against the
LIVE repo tree: each of the four `contracts/*.md` files must exist and carry
the exact anchor strings its AC bullet names, proving the doc was actually
authored (not stubbed) with the required content. CR-MDB-031 SS4 moved
`contracts/mail-axi.md` to `archive/contracts/` and retired its SS4 class;
tests/test_worktree_layout_and_bundles.py pins the archived copy.

Repo-only CR (per SS1: "no ~/.claude writes, no chezmoi ops") -- these tests
assert repo-relative paths only, no ~/.claude / chezmoi checks (unlike
tests/test_memory_model.py, whose CR touched the global memory tree).

At RED time `contracts/` holds only `.gitkeep`, so all four tests below are
expected to FAIL on the `is_file()` existence assertion.

Stdlib only (unittest + pathlib). No SUT import: this CR's deliverable is
markdown contract content, not Python modules.

CR-MDB-092 §S1–§S3, §S8.1 — ``contracts/lean-ctx.md`` refreshed to lean-ctx 3.11.4: § Current
state's stale claims replaced, two new sections (§ Context ledger, § Sub-agents), findings (a)
and (b) closed with their upstream answers, and the new upstream findings (c)–(i), (k), (l)
recorded "to file" (the suspected invalidate finding is held back, so it has no pin). Two
module-level detectors read the contract the way the spec does: normalised text, unit by unit
(``rule_units``), each pin inside one unit of its own section (``contract_refresh_findings``),
and the retired phrases anywhere (``contract_retired_findings``). Each detector is proved both
ways on synthetic text in ``LeanCtxContractRefreshTest``.
"""

import re
import unittest
from pathlib import Path

from tests._helpers import read_text_lenient as _read
from tests.test_bootstrap_shutdown_registry import normalise
from tests.test_execution_knowledge_rules import rule_units, section_starting
from tests.test_orchestrator_rule_triage import markdown_headings
from tests.test_watcher_launch_supervision import _blocks, _names_exit

REPO_ROOT = Path(__file__).resolve().parent.parent
CONTRACTS_DIR = REPO_ROOT / "contracts"

CRUCIBLE_ENVELOPE_MD = CONTRACTS_DIR / "crucible-envelope.md"
SANDESH_CLI_MD = CONTRACTS_DIR / "sandesh-cli.md"
LEAN_CTX_MD = CONTRACTS_DIR / "lean-ctx.md"

# The exact phase-agent id form cited verbatim in the SS2 AC bullet.
PHASE_AGENT_ID_FORM = "CR-<PROJ>-NNN-<cycle>-<PHASE>"

# The seven sandesh-cli message verbs the SS3 AC bullet names verbatim.
SANDESH_MESSAGE_VERBS = (
    "send",
    "reply",
    "fetch",
    "inbox",
    "addressbook",
    "register",
    "unregister",
)

# ------------------------------------------------- CR-MDB-092 §S8.1 the lean-ctx refresh ----

#: CR-MDB-092 §S8.1: each pin, by section heading prefix, is a tuple of regexes every one of which
#: must match inside ONE normalised unit of that section. The suspected ``ctx_session``
#: ``action=invalidate`` finding (the gap analysis's (j)) is held back, so it has no pin.
CONTRACT_REFRESH_PINS = {
    "Current state": {
        "version": (r"\blean-ctx 3\.11\.4\b",),
        "extension version": (r"\bpi-lean-ctx\b", r"\b3\.11\.4\b"),
        "served surface": (r"\btool_profile\b", r"\blean_ctx_tool_profile\b", r"\btoolprofile\b",
                           r"\blazy core\b", r"\bstandard\b", r"\bctx_call\b", r"\btrust",
                           r"\bctx_graph\b", r"\bctx_explore\b"),
        "ctx_edit": (r"\bctx_edit\b", r"\bevery profile\b", r"\bbridge\b"),
        "fresh full": (r"mode=full", r"\bfresh\b", r"\b13\b|\bstub\b"),
        "budgets": (r"\b4096\b", r"\b32768\b", r"\braw\b", r"turn_fresh_limit"),
        "routeShell": (r"\brouteshell\b", r"\bbash\b"),
        "profile line": (r"/lean-ctx", r"\btool profile\b", r"\bserved\b"),
    },
    "Context ledger": {
        "ledger writers": (r"\bctx_grep\b", r"lean-ctx -c", r"raw=true", r"\bnothing\b|\bno entry\b"),
        "machine-wide": (r"\bmachine-wide\b", r"\bevict", r"\breset", r"\bnever\b"),
        "pressure": (r"\bpressure\b", r"\bwindow\b", r"0\.20"),
    },
    "Sub-agents": {
        "sub-agents": (r"\bgeneral-purpose\b", r"tools:", r"\bbuilt-?ins?\b", r"general-purpose\.md"),
    },
    "Filed requests / gaps": {
        "(a) closed": (r"\bshell_allowlist_extra\b", r"\.lean-ctx\.toml", r"lean-ctx trust",
                       r"\bclosed\b", r"\ballowlist_gate\b"),
        "(b) closed": (r"\bwrite_allow_paths\b", r"lean-ctx trust", r"\bclosed\b",
                       r"\bctxshelltool\b"),
        "(c)": (r"\bload_for_agent\b", r"\bto file\b"),
        "(d)": (r"\bignite_high_salience\b", r"0\.20", r"\bto file\b"),
        "(e)": (r"\bdaemon\b", r"\bdisagree", r"\bto file\b"),
        "(f)": (r"\bapply_confidence_decay\b", r"\bcompound", r"\bto file\b"),
        "(g)": (r"\brecall_facts_limit\b", r"\bshowing\b", r"\bglobal-only\b", r"\bto file\b"),
        "(h)": (r"\bis_test_runner_command\b", r"\bverbatim\b", r"\bto file\b"),
        "(i)": (r"\brecord_shell_command_named\b", r"\bload_latest\b", r"\bto file\b"),
        "(k)": (r"/lean-ctx", r"\btoolprofile\b", r"\bto file\b"),
        "(l)": (r"\breadmodeschema\b", r"raw=true", r"mode=raw", r"\bto file\b"),
    },
}

#: CR-MDB-092 §S8.1: each retired phrase, by name, matched anywhere in the normalised contract.
CONTRACT_RETIRED_PHRASES = {
    "3.10.2": r"\b3\.10\.2\b",
    "lean default": r"\blean default\b",
    "under the lean profile": r"\bunder the lean profile\b",
    "has not been measured here": r"\bhas not been measured here\b",
    "not re-measured": r"\bnot re-measured\b",
    "silently capped": r"\bsilently capped\b",
    "uncapped": r"\buncapped\b",
}

#: CR-MDB-092 §S2: the two new sections sit after § Preference order and before § Knowledge store.
NEW_CONTRACT_SECTIONS = ("Context ledger", "Sub-agents")


def contract_refresh_findings(text: str) -> list[str]:
    """CR-MDB-092 §S8.1: the name of each :data:`CONTRACT_REFRESH_PINS` pin that no single
    normalised unit of its section satisfies (a missing section fails every pin it holds)."""
    out = []
    for heading, pins in CONTRACT_REFRESH_PINS.items():
        body = section_starting(text, heading)
        units = rule_units(body) if body is not None else []
        for name, rule in pins.items():
            if not any(all(re.search(p, u) for p in rule) for u in units):
                out.append(name)
    return out


def contract_retired_findings(text: str) -> list[str]:
    """CR-MDB-092 §S8.1: the name of each :data:`CONTRACT_RETIRED_PHRASES` phrase present
    anywhere in the normalised contract."""
    flat = normalise(text)
    return [name for name, pattern in CONTRACT_RETIRED_PHRASES.items() if re.search(pattern, flat)]


#: CR-MDB-092 §S8.1: § Current state's served-surface bullet of the conforming sample, kept apart so
#: a test can move it into another section.
_GOOD_SERVED_SURFACE = """\
- **The served tool surface.** The engine resolves it: `LEAN_CTX_TOOL_PROFILE`, then the global
  `tool_profile`, then `tools_enabled` (`ToolProfile::from_config`, `rust/src/core/tool_profiles.rs`).
  - Unpinned, the bridge serves the lazy core (`ctx_read`, `ctx_shell`, `ctx_search`, `ctx_glob`,
    `ctx_tree`, `ctx_session`, `ctx_compose`, `ctx_callgraph`, `ctx_patch`, `ctx_call`,
    `ctx_expand`) and reaches the rest through `ctx_call`; lean-ctx's own setup leaves the
    profile unpinned.
  - Pinned `standard`, it serves 17 tools plus `ctx_call`; this machine pins `standard`.
  - `pi-lean-ctx`'s `toolProfile` (default `lean`) forwards nothing for `lean`, so the global
    config decides.
  - `tool_profile` applies from a project `.lean-ctx.toml` only once it is trusted.
  - The generated agents' `ctx_callgraph` is served in the lazy core, `standard` and `power`, never
    in `minimal` (or `auto` before it escalates); VERIFY's `ctx_graph` and `ctx_explore` only in
    `standard`, `power` or a `tools_enabled` list naming them.
"""

#: CR-MDB-092 §S8.1: a conforming contract, built from the text §S1–§S3 prescribe; it passes both
#: detectors.
GOOD_LEAN_CTX_CONTRACT = """\
# Contract — lean-ctx on Pi: tool preference + operational findings

**Owner:** LEAN-CTX project (upstream tool provider; `lean-ctx` engine and the `pi-lean-ctx`
Pi extension).
**Status:** FINDINGS — (a) and (b) closed by lean-ctx 3.11.4's answers; the others are recorded
under § Filed requests / gaps for filing (§S3).

## Current state

- **Engine.** `lean-ctx` 3.11.4 (read in its source) is **dual** MCP + CLI, with 79 MCP tools:
  - MCP server: the `ctx_*` tools, several read modes and a session cache;
  - CLI: `lean-ctx -c "<command>"` (compressed shell), plus management verbs.
- **Pi extension.** Pi reaches the engine through the `pi-lean-ctx` package (3.11.4, a user-level
  Pi package Model B neither ships nor installs). It registers seven tools itself,
  in every profile: `ctx_read`, `ctx_shell`, `ctx_grep`, `ctx_find`, `ctx_ls`, `ctx_edit` and
  `lean_ctx`. `ctx_read` and `ctx_edit` go through the bridge when it is connected, and
  `ctx_edit` fails without it.
""" + _GOOD_SERVED_SURFACE + """\
- **Mode.** The extension's default is **additive**: Pi's own built-in tools stay available beside
  the `ctx_*` tools, and `routeShell` hides `bash` alone. `LEAN_CTX_PI_MODE=replace` hides the
  replaceable built-ins.
- **The read cache.** On Pi, `ctx_read` with `mode=full` (or `fresh=true`) is always a fresh disk
  read, never the ~13-token stub; only the other modes re-read an unchanged file cheaply. A read
  without a mode gets the extension's size-based choice, never `auto`.
- **The response budgets.**
  - Every bridged response is cut at `turn_fresh_limit` (4096 tokens), and at
    `turn_fresh_limit_verbatim` (32768) for a `ctx_read` with `mode=raw`; on Pi no other tool
    reaches the verbatim budget. The cut keeps the line that names the recovery path.
  - The CLI-backed `ctx_shell` and `ctx_grep` are not under it.
  - Cited: `enforce_turn_budget`, `rust/src/core/budget.rs`.
- **Checks.** `/lean-ctx`'s `Tool profile:` line reports `pi-lean-ctx`'s own setting; the served
  set is the bridge's tool list. `lean-ctx verify-cache` proves (or disproves) that the session
  cache engages.

## Preference order (as ruled)

1. `ctx_read` over the built-in file read; `full` is always fresh on Pi; `raw` for exact bytes.
2. `ctx_shell` over the built-in shell for commands with side effects.
3. File edits and new files stay on Pi's native edit and write; `ctx_patch` or `ctx_edit` (an
   extension tool in every profile; it needs the bridge) when cache coherence matters.
4. Compression bypass ladder: `lines:N-M` → `full` → `raw=true` (`ctx_read` `mode=raw` for a file,
   up to 32768 tokens; `ctx_shell` `raw=true` for a command).

## Context ledger

- One file, machine-wide: `$XDG_STATE_HOME/lean-ctx/context_ledger.json` (`ledger_path`,
  `rust/src/core/context_ledger/helpers.rs`). The per-agent path has no caller: `load_for_agent`
  is only called with `"default"`.
- Who writes it:
  - bridged reads (`persist_read`);
  - every compressed `lean-ctx -c` run with output — on Pi, a non-raw `ctx_shell` or a `ctx_grep`
    (`record_shell_command_named`) — except a passthrough- or verbatim-class command or one that
    redirects to a file (`execute_shell_post_gate`), which writes no entry;
  - the daemon;
  - and a `raw=true` `ctx_shell` writes nothing.
- What "pressure" is: tokens sent over a fixed window, plus a pinned/stale boost capped at 0.20
  (`pressure`, `rust/src/core/context_ledger/ledger.rs`). It measures no model's context.
  Auto-pinned one-off shell entries alone can saturate the boost (`ignite_high_salience`).
- Model B's rule (CR-MDB-090): because the ledger is machine-wide, ignore its evict hints,
  and never evict or reset it during a run. A `lean-ctx ledger status` can write the file when
  the daemon does not answer.

## Sub-agents

- A pi-subagents dispatch type with no `tools:` (`general-purpose`) gets Pi's built-ins only
  (`read bash edit write grep find ls`); `Explore` and `Plan` get `read bash grep find ls`
  (`getToolNamesForType`). Only an agent file's `tools:` admits a `ctx_*` tool, and Model B's
  generated definitions carry their own `tools:`;
  a `general-purpose.md` in `.pi/agents/` or `$PI_CODING_AGENT_DIR/agents/` overrides the
  default type by name.

## Knowledge store

The store's rules, unchanged by this refresh.

## Filed requests / gaps (operational findings)

### (a) Shell-allowlist friction for project tooling
lean-ctx enforces a restricted shell command allowlist in its MCP tools. Project tools that are
not on the built-in list are blocked there, which pushes those runs off the compressed channel.

**Closed.** lean-ctx 3.11.4's answer: a trusted project `.lean-ctx.toml` may carry
`shell_allowlist_extra`, merged additively (`Config::merge_local`). Measured in source: the CLI
`-c` path enforces the allowlist for a non-terminal caller (`allowlist_gate`), which is Pi's case.
Model B's AXI commands run with `raw=true` (CR-MDB-090) and so never meet it. The key is the
user's to add, after `lean-ctx trust` (CR-MDB-091 Non-goals).

### (b) File-write redirect block × orchestration scripts
The `ctx_shell` file-write redirect block collides with orchestration scripts whose normal
operation writes files, so those invocations must leave the compressed channel entirely.

**Closed.** lean-ctx 3.11.4's answer: `write_allow_paths`, global, or in a project
`.lean-ctx.toml` once `lean-ctx trust` pins it, widens where `ctx_shell` may redirect. Its default
is the OS temp directories, and the session's project is always allowed; `shell_allow_writes`
sits beside it. The check runs only in the MCP `ctx_shell` (`CtxShellTool::handle`), never on
Pi's CLI path.

### (c) Per-agent or per-project ledger scoping
`load_for_agent` (`rust/src/core/context_ledger/ledger.rs`) is only called with `"default"`, so
every agent and project shares one ledger. Ask: scope the ledger per agent or per project.
Status: to file.

### (d) Auto-pinned shell labels saturate the boost
Auto-pinning one-off shell labels (`ignite_high_salience`, `rust/src/core/context_ledger/ledger.rs`)
saturates the 0.20 pinned/stale boost (`pressure`). Ask: exclude shell labels from ignition.
Status: to file.

### (e) The daemon's in-memory ledger
The daemon's in-memory ledger disagrees with the file, and `ledger status` asks the daemon first.
Ask: one ledger state for the daemon and the file. Status: to file.

### (f) Decay per lifecycle run
Decay compounds on every lifecycle run (`apply_confidence_decay`,
`rust/src/core/memory_lifecycle.rs`). Ask: decay once per interval. Status: to file.

### (g) The listing limit
A category listing is capped by the global-only `recall_facts_limit`, with no per-call or
per-project limit, though it reports `showing <n>/<total>` (`handle_recall`,
`rust/src/tools/ctx_knowledge/remember.rs`); only the listed facts are protected from decay.
Ask: a per-call or per-project limit. Status: to file.

### (h) Declared test clients
The Crucible clients are not in `is_test_runner_command`, and `excluded_commands` is a prefix
match. Ask: a verbatim class for declared test clients. Status: to file.

### (i) The CLI shell path's ledger write
The CLI shell path rewrites the whole ledger file (`ContextLedger::load`/`save` in
`record_shell_command_named`, not the locked merge of `persist_read`), and consolidates the
machine's latest session's project (`SessionState::load_latest`), a session save that runs even
when the ledger write is skipped. Ask: merge under the lock. Status: to file.

### (k) The status command's profile line
`/lean-ctx` reports the extension's `toolProfile`, not the served surface. Ask: report the
bridge's tool list. Status: to file.

### (l) The read-mode description
`pi-lean-ctx`'s `readModeSchema` describes `full` as "≤turn budget; raw=true beyond", but its
`ctx_read` has no `raw` parameter (`readSchema`, `extensions/index.ts`): only `mode=raw` works.
Ask: correct the description or add the parameter. Status: to file.
"""

#: CR-MDB-092 §S8.1: one cut per pin — ``(old, new)`` removes that pin's distinguishing word from
#: its unit in :data:`GOOD_LEAN_CTX_CONTRACT` (``old`` occurs exactly once).
CONTRACT_REFRESH_CUTS = {
    "version": ("`lean-ctx` 3.11.4 (read in its source)", "`lean-ctx` (read in its source)"),
    "extension version": ("package (3.11.4, a user-level", "package (a user-level"),
    "served surface": ("VERIFY's `ctx_graph` and `ctx_explore` only", "VERIFY's `ctx_graph` only"),
    "ctx_edit": ("in every profile: `ctx_read`", "in each mode: `ctx_read`"),
    "fresh full": ("with `mode=full` (or", "with a full read (or"),
    "budgets": ("(4096 tokens)", "(a few thousand tokens)"),
    "routeShell": ("`routeShell` hides `bash` alone", "the extension hides `bash` alone"),
    "profile line": ("`Tool profile:` line reports", "status line reports"),
    "ledger writers": ("a non-raw `ctx_shell` or a `ctx_grep`", "a non-raw `ctx_shell`"),
    "machine-wide": ("and never evict or reset it during a run", "and leave it alone during a run"),
    "pressure": ("capped at 0.20", "capped at a fifth"),
    "sub-agents": ("a `general-purpose.md` in", "an override file in"),
    "(a) closed": ("**Closed.** lean-ctx 3.11.4's answer: a trusted", "lean-ctx 3.11.4's answer: a trusted"),
    "(b) closed": ("**Closed.** lean-ctx 3.11.4's answer: `write_allow_paths`",
                   "lean-ctx 3.11.4's answer: `write_allow_paths`"),
    "(c)": ("Ask: scope the ledger per agent or per project.\nStatus: to file.",
            "Ask: scope the ledger per agent or per project.\nStatus: recorded."),
    "(d)": ("shell labels (`ignite_high_salience`, ", "shell labels ("),
    "(e)": ("ledger disagrees with the file, and", "ledger differs from the file, and"),
    "(f)": ("Decay compounds on every", "Decay applies on every"),
    "(g)": ("the global-only `recall_facts_limit`", "the global `recall_facts_limit`"),
    "(h)": ("Ask: a verbatim class for declared", "Ask: a class for declared"),
    "(i)": ("(`SessionState::load_latest`)", "(the latest session)"),
    "(k)": ("reports the extension's `toolProfile`, not", "reports the extension's setting, not"),
    "(l)": ("only `mode=raw` works", "only the mode works"),
}

#: CR-MDB-092 §S8.1: a literal excerpt of the contract as it stood before the refresh (its header,
#: § Current state, § Preference order and § Filed requests / gaps, trimmed to the units the
#: expected findings come from) — kept here, never read through ``git``.
TODAYS_LEAN_CTX_CONTRACT = """\
# Contract — lean-ctx on Pi: tool preference + operational findings

**Owner:** LEAN-CTX project (upstream tool provider; `lean-ctx` engine and the `pi-lean-ctx`
Pi extension).
**Status:** FILED FINDINGS — the surface already exists, dual MCP + CLI; this contract
documents how it reaches Pi, the preference order Model B relies on, and the operational
findings raised.

## Current state

- **Engine.** `lean-ctx` (3.10.2 observed) is **dual** MCP + CLI:
  - MCP server: the `ctx_*` tools (read / search / shell / tree / overview / knowledge / …),
    several read modes, tree-sitter AST extraction, compression patterns, and a session
    cache held by the long-running server process;
  - CLI: `lean-ctx -c "<command>"` (compressed shell), `lean-ctx read <file>`,
    `lean-ctx grep <pattern>`, plus management verbs (`doctor`, `gain`, `tools <profile>`,
    `allow`, `verify-cache`, …).
- **Pi extension.** Pi reaches the engine through the `pi-lean-ctx` package (3.10.2
  observed; installed with `pi install npm:pi-lean-ctx`, a user-level Pi package that Model B
  neither ships nor installs). It registers two kinds of `ctx_*` tool in Pi:
  - CLI-backed tools — `ctx_read`, `ctx_shell`, `ctx_grep`, `ctx_find`, `ctx_ls` — each a
    `lean-ctx` CLI invocation with compression on;
  - an embedded MCP bridge (on by default; `LEAN_CTX_PI_ENABLE_MCP=0` forces the CLI-only
    path) that runs `lean-ctx` as an MCP server over stdio, routes `ctx_read` through it so
    unchanged re-reads hit the session cache, and registers the server's other advertised
    tools (`ctx_search`, `ctx_tree`, `ctx_overview`, `ctx_patch`, `ctx_call`, …) as Pi tools.
    The tool surface follows a profile (`lean` default, `standard`, `power`); tools outside it
    (e.g. `ctx_edit` under `lean`) stay reachable through `ctx_call`.

## Preference order (as ruled)

3. File edits and new files stay on Pi's native edit and write; `ctx_patch` (anchored by line
   and hash from `ctx_read mode=anchored`) or `ctx_edit` (through `ctx_call` under the `lean`
   profile) when cache coherence or race protection matters.

## Filed requests / gaps (operational findings)

### (a) Shell-allowlist friction for project tooling
lean-ctx enforces a restricted shell command allowlist in its MCP tools (233 commands
permitted in the observed configuration — the built-in list plus the extras — configured in
`~/.config/lean-ctx/config.toml`). Project tools that are not on the built-in list are
blocked there — the per-stack Crucible clients (`~/.crucible/clients/<stack>-crucible.py`)
are the recurring case — which pushes those runs off the compressed channel. On Pi,
`ctx_shell` is served by the CLI-backed path; whether that path applies the same allowlist has
not been measured here.

Mitigation in place: the additive `lean-ctx allow <cmd>` flow appends to
`shell_allowlist_extra` WITHOUT replacing the built-in list (currently extra includes
`sandesh`, `opensrc`, `python-crucible.py`). Finding filed: project-tool friction recurs per
tool; requested a smoother path (e.g. a per-project allowlist file, or trusting a declared
project-tool directory).

### (b) File-write redirect block × orchestration scripts
The `ctx_shell` file-write redirect block (guarding against uncontrolled writes) collides
with orchestration scripts whose normal operation writes files (test-report generation,
script-managed logs). The block cannot distinguish a sanctioned orchestration write from an
uncontrolled one, so those invocations must leave the compressed channel entirely. Finding
filed: an escape for declared write targets so orchestration scripts can stay on
`ctx_shell`. Observed before Model B moved to Pi; not re-measured under `pi-lean-ctx`.
"""


class ContractsS2Test(unittest.TestCase):
    """SS2 -- contracts/crucible-envelope.md: the CRUCIBLE-owned contract
    mirroring the incoming CR-CRU-030 client contract."""

    def test_s2_crucible_envelope_exists_with_required_anchors(self):
        self.assertTrue(
            CRUCIBLE_ENVELOPE_MD.is_file(),
            f"{CRUCIBLE_ENVELOPE_MD} must exist",
        )
        content = _read(CRUCIBLE_ENVELOPE_MD)

        # POSITIVE -- the AC's conjunction of literal required terms.
        required_terms = [
            "{axi:",
            "warnings[]",
            "WORKFLOW_",
            "plan-file",
            "CR-CRU-030",
            PHASE_AGENT_ID_FORM,
            "TRACKS",
        ]
        missing = [term for term in required_terms if term not in content]
        self.assertEqual(
            missing, [],
            f"{CRUCIBLE_ENVELOPE_MD} missing required anchor terms: {missing}",
        )

        # NEGATIVE -- the final contract has NO refusal rule; the
        # unknown-cycleId REFUSED/(400) anchor is gone.
        self.assertNotIn(
            "REFUSED", content,
            f"{CRUCIBLE_ENVELOPE_MD} must not contain 'REFUSED' -- the refusal rule is gone",
        )
        self.assertNotIn(
            "(400)", content,
            f"{CRUCIBLE_ENVELOPE_MD} must not reference the '(400)' refusal status",
        )

        # POSITIVE -- server-resolved cycle-attach + no-active-cycle
        # withhold semantics, and DELIVERED status.
        self.assertIn(
            "resolve_attach_cycle", content,
            f"{CRUCIBLE_ENVELOPE_MD} must contain 'resolve_attach_cycle'",
        )
        self.assertIn(
            "no-active-cycle", content,
            f"{CRUCIBLE_ENVELOPE_MD} must contain 'no-active-cycle'",
        )
        self.assertIn(
            "DELIVERED", content,
            f"{CRUCIBLE_ENVELOPE_MD} must contain 'DELIVERED' (status)",
        )

        # NEGATIVE/bound -- not a stub: the file must carry real content,
        # not just an empty or near-empty placeholder.
        self.assertGreater(
            len(content.strip()), 0,
            f"{CRUCIBLE_ENVELOPE_MD} must not be empty",
        )

    def test_ac1_zero_workflow_cycle_id_occurrences_in_crucible_envelope(self):
        self.assertTrue(
            CRUCIBLE_ENVELOPE_MD.is_file(),
            f"{CRUCIBLE_ENVELOPE_MD} must exist",
        )
        content = _read(CRUCIBLE_ENVELOPE_MD)
        count = content.count("WORKFLOW_CYCLE_ID")
        # EXACT bound -- zero occurrences of the retired env carrier.
        self.assertEqual(
            count, 0,
            f"expected zero 'WORKFLOW_CYCLE_ID' occurrences in {CRUCIBLE_ENVELOPE_MD}, "
            f"found {count}",
        )


class ContractsS3Test(unittest.TestCase):
    """SS3 -- contracts/sandesh-cli.md: the SANDESH-owned contract for the
    CLI surface replacing the MCP-only message verbs, plus the dogfooding
    defect/gap register (zombie project, display-name update, admin-name
    leak)."""

    def test_s3_sandesh_cli_exists_with_required_anchors(self):
        self.assertTrue(
            SANDESH_CLI_MD.is_file(),
            f"{SANDESH_CLI_MD} must exist",
        )
        content = _read(SANDESH_CLI_MD)

        # POSITIVE -- all seven message verbs the AC names verbatim.
        missing_verbs = [v for v in SANDESH_MESSAGE_VERBS if v not in content]
        self.assertEqual(
            missing_verbs, [],
            f"{SANDESH_CLI_MD} missing required message verbs: {missing_verbs}",
        )

        # POSITIVE -- the defect/gap register anchors (a) zombie, (b)
        # display-name update, (c) admin-name leak -- and SANDESH ownership.
        required_terms = ["zombie", "display", "admin name", "SANDESH"]
        missing_terms = [term for term in required_terms if term not in content]
        self.assertEqual(
            missing_terms, [],
            f"{SANDESH_CLI_MD} missing required anchor terms: {missing_terms}",
        )

        # NEGATIVE/bound -- not a stub.
        self.assertGreater(
            len(content.strip()), 0,
            f"{SANDESH_CLI_MD} must not be empty",
        )


class ContractsS5Test(unittest.TestCase):
    """SS5 -- contracts/lean-ctx.md: the LEAN-CTX-owned CLI-preference
    contract documenting preference order plus operational findings
    (shell-allowlist friction, file-write redirect block interplay)."""

    def test_s5_lean_ctx_exists_with_required_anchors(self):
        self.assertTrue(
            LEAN_CTX_MD.is_file(),
            f"{LEAN_CTX_MD} must exist",
        )
        content = _read(LEAN_CTX_MD)

        # POSITIVE -- "allowlist" is a required literal term.
        self.assertIn(
            "allowlist", content,
            f"{LEAN_CTX_MD} must contain 'allowlist'",
        )

        # POSITIVE -- "dual" OR "MCP + CLI" per the AC's own tolerant
        # alternative describing the dual MCP/CLI preference.
        dual_variants = ("dual", "MCP + CLI")
        has_dual_marker = any(v in content for v in dual_variants)
        self.assertTrue(
            has_dual_marker,
            f"{LEAN_CTX_MD} must contain 'dual' or 'MCP + CLI', tried {dual_variants}",
        )

        # NEGATIVE/bound -- not a stub.
        self.assertGreater(
            len(content.strip()), 0,
            f"{LEAN_CTX_MD} must not be empty",
        )


def _all_refresh_pin_names() -> list[str]:
    return [name for pins in CONTRACT_REFRESH_PINS.values() for name in pins]


def _section_order_findings(text: str) -> list[str]:
    """Each §S2 section that is not a level-2 heading after § Preference order and before
    § Knowledge store (a missing anchor is a finding too)."""
    level_two = [h for _, level, h in markdown_headings(text) if level == 2]

    def index(prefix):
        return next((i for i, h in enumerate(level_two) if h.startswith(prefix)), None)

    after, before = index("Preference order"), index("Knowledge store")
    out = []
    for name in NEW_CONTRACT_SECTIONS:
        at = index(name)
        if at is None or after is None or before is None or not after < at < before:
            out.append(name)
    return out


class LeanCtxContractRefreshTest(unittest.TestCase):
    """CR-MDB-092 §S1–§S3, §S8.1 — ``contracts/lean-ctx.md`` records lean-ctx 3.11.4 as Model B
    relies on it: each refresh pin is met inside one unit of its section, no retired phrase is
    left, and the two new sections sit between § Preference order and § Knowledge store. Both
    detectors are proved both ways on synthetic text."""

    def cut(self, old: str, new: str) -> str:
        self.assertEqual(GOOD_LEAN_CTX_CONTRACT.count(old), 1, f"cut anchor {old!r}")
        return GOOD_LEAN_CTX_CONTRACT.replace(old, new)

    # -- the real contract ------------------------------------------------------------

    def test_the_contract_meets_every_refresh_pin_in_one_unit_of_its_section(self):
        found = contract_refresh_findings(_read(LEAN_CTX_MD))
        self.assertEqual(found, [], f"§S1–§S3: {LEAN_CTX_MD} lacks these pins: {found!r}")

    def test_the_contract_carries_no_retired_phrase(self):
        found = contract_retired_findings(_read(LEAN_CTX_MD))
        self.assertEqual(found, [], f"§S1–§S3: {LEAN_CTX_MD} still carries: {found!r}")

    def test_the_two_new_sections_sit_after_preference_order_and_before_knowledge_store(self):
        found = _section_order_findings(_read(LEAN_CTX_MD))
        self.assertEqual(found, [], f"§S2: {LEAN_CTX_MD} misplaces or lacks: {found!r}")

    # -- the detectors, proved on synthetic text -----------------------------------------

    def test_the_pin_set_is_the_specs_and_holds_no_invalidate_finding(self):
        self.assertEqual(_all_refresh_pin_names(), [
            "version", "extension version", "served surface", "ctx_edit", "fresh full", "budgets",
            "routeShell", "profile line", "ledger writers", "machine-wide", "pressure",
            "sub-agents", "(a) closed", "(b) closed", "(c)", "(d)", "(e)", "(f)", "(g)", "(h)",
            "(i)", "(k)", "(l)"])
        self.assertNotIn("(j)", _all_refresh_pin_names())

    def test_the_conforming_sample_passes_both_detectors(self):
        self.assertEqual(contract_refresh_findings(GOOD_LEAN_CTX_CONTRACT), [])
        self.assertEqual(contract_retired_findings(GOOD_LEAN_CTX_CONTRACT), [])
        self.assertEqual(_section_order_findings(GOOD_LEAN_CTX_CONTRACT), [])

    def test_every_pin_has_one_cut(self):
        self.assertEqual(list(CONTRACT_REFRESH_CUTS), _all_refresh_pin_names())

    def test_each_cut_returns_exactly_that_pins_name(self):
        for name, (old, new) in CONTRACT_REFRESH_CUTS.items():
            with self.subTest(pin=name):
                self.assertEqual(contract_refresh_findings(self.cut(old, new)), [name])

    def test_a_pin_split_across_two_units_bites(self):
        splits = {
            "(a) closed": ("(`Config::merge_local`). Measured in source: the CLI",
                           "(`Config::merge_local`).\n\nMeasured in source: the CLI"),
            "served surface": ("  - The generated agents' `ctx_callgraph` is served",
                               "- The generated agents' `ctx_callgraph` is served"),
            "sub-agents": ("carry their own `tools:`;\n  a `general-purpose.md`",
                           "carry their own `tools:`;\n- a `general-purpose.md`"),
        }
        for name, (old, new) in splits.items():
            with self.subTest(pin=name):
                self.assertEqual(contract_refresh_findings(self.cut(old, new)), [name])

    def test_a_pin_unit_moved_into_another_section_bites(self):
        moved = self.cut(_GOOD_SERVED_SURFACE, "") + "\n" + _GOOD_SERVED_SURFACE
        self.assertIn("\n## Filed requests / gaps", moved.partition(_GOOD_SERVED_SURFACE)[0])
        self.assertEqual(contract_refresh_findings(moved), ["served surface"])

    def test_a_section_under_another_heading_fails_its_pins(self):
        renamed = self.cut("## Sub-agents\n", "## Dispatch\n")
        self.assertEqual(contract_refresh_findings(renamed), ["sub-agents"])
        self.assertEqual(_section_order_findings(renamed), ["Sub-agents"])

    def test_a_new_section_after_knowledge_store_is_misplaced(self):
        ledger_start = GOOD_LEAN_CTX_CONTRACT.index("## Context ledger\n")
        ledger_end = GOOD_LEAN_CTX_CONTRACT.index("## Sub-agents\n")
        ledger = GOOD_LEAN_CTX_CONTRACT[ledger_start:ledger_end]
        moved = self.cut(ledger, "").replace(
            "## Filed requests / gaps", ledger + "## Filed requests / gaps")
        self.assertEqual(_section_order_findings(moved), ["Context ledger"])
        self.assertEqual(contract_refresh_findings(moved), [], "the pins still hold in the moved section")

    def test_each_retired_phrase_inserted_returns_exactly_its_name(self):
        for name in CONTRACT_RETIRED_PHRASES:
            with self.subTest(phrase=name):
                text = GOOD_LEAN_CTX_CONTRACT + f"\nThe old text read: {name}.\n"
                self.assertEqual(contract_retired_findings(text), [name])

    def test_a_retired_phrase_wrapped_and_marked_up_is_still_found(self):
        text = GOOD_LEAN_CTX_CONTRACT + "\nThe edit tool, through it under the `lean`\nprofile.\n"
        self.assertEqual(contract_retired_findings(text), ["under the lean profile"])

    def test_todays_text_fails_the_refresh_and_carries_the_retired_phrases(self):
        refresh = contract_refresh_findings(TODAYS_LEAN_CTX_CONTRACT)
        for name in ("version", "served surface", "budgets", "machine-wide", "sub-agents",
                     "(a) closed", "(b) closed"):
            with self.subTest(pin=name):
                self.assertIn(name, refresh)
        retired = contract_retired_findings(TODAYS_LEAN_CTX_CONTRACT)
        for name in ("3.10.2", "lean default", "has not been measured here"):
            with self.subTest(phrase=name):
                self.assertIn(name, retired)
        self.assertNotIn("silently capped", retired)
        self.assertNotIn("uncapped", retired)


class SandeshCliRelease040Test(unittest.TestCase):
    """CR-MDB-047 \u00a7S5 -- contracts/sandesh-cli.md records Sandesh 0.4.0 as Model B
    relies on it: the version floor; ``status`` and ``--format toon``; the notify exit
    table as sandesh-pi's supervision treats it (after mail it injects a turn and
    relaunches; it retries once when the address is already live; it stops with a
    notice on exit 1, 3 or 4); and that only the extension starts the supervised
    watcher. Each rule is checked inside one bullet, paragraph or table row."""

    def setUp(self):
        self.content = _read(SANDESH_CLI_MD)
        self.blocks = [b for _, b in _blocks(self.content)]

    def _blocks_with(self, *patterns):
        return [b for b in self.blocks if all(re.search(p, b, re.IGNORECASE) for p in patterns)]

    def _exit_rows(self, code):
        return [b for b in self.blocks if b.startswith("|") and _names_exit(b, code)]

    def test_records_the_sandesh_0_4_0_version_floor(self):
        self.assertTrue(
            self._blocks_with(r"\b0\.4\.0\b", r"floor|or later|at least|minimum|older", r"sandesh"),
            "sandesh-cli.md must record the floor: the `sandesh` CLI 0.4.0 or later",
        )

    def test_records_the_status_home_view_and_toon_output(self):
        self.assertTrue(self._blocks_with(r"sandesh status\b"), "sandesh-cli.md must record `sandesh status`")
        self.assertTrue(self._blocks_with(r"--format toon"), "sandesh-cli.md must record `--format toon`")

    def test_exit_table_records_mail_as_a_turn_and_a_relaunch_by_the_extension(self):
        rows = [r for r in self._exit_rows("0") if re.search(r"mail", r, re.IGNORECASE)
                and re.search(r"\bturn\b|inject", r, re.IGNORECASE)]
        self.assertTrue(rows, "the exit table's 0 row: mail arrived -> sandesh-pi injects a turn naming the ids")

    def test_exit_table_stops_with_a_notice_on_exits_1_3_and_4(self):
        reasons = {"1": r"error|usage|config", "3": r"tombston", "4": r"evict"}
        for code, reason in reasons.items():
            with self.subTest(exit=code):
                rows = [r for r in self._exit_rows(code)
                        if re.search(reason, r, re.IGNORECASE)
                        and re.search(r"\bstops?\b", r, re.IGNORECASE)
                        and re.search(r"\bnotice\b", r, re.IGNORECASE)]
                self.assertEqual(len(rows), 1, f"exactly one exit-{code} row: {reason} -> stops with a notice")

    def test_exit_table_retries_once_when_already_live(self):
        rows = [r for r in self._exit_rows("5") if re.search(r"already[- ]live|dedup", r, re.IGNORECASE)
                and re.search(r"\bretr(?:y|ies)\b[^|]{0,20}\bonce\b", r, re.IGNORECASE)]
        self.assertTrue(rows, "the exit table's 5 row: already live -> sandesh-pi retries once")

    def test_exit_table_relaunches_silently_on_exit_2(self):
        # CR-MDB-047 §S5 amended at 5dd8a36 (VERIFY F10): every exit, 2 included.
        rows = [r for r in self._exit_rows("2") if re.search(r"timeout|timed out", r, re.IGNORECASE)
                and re.search(r"relaunch", r, re.IGNORECASE)
                and re.search(r"silent", r, re.IGNORECASE)]
        self.assertEqual(len(rows), 1, "exactly one exit-2 row: timeout -> relaunched silently")

    def test_exit_table_stops_with_a_notice_on_a_signal(self):
        # CR-MDB-047 §S5 amended at 5dd8a36 (VERIFY F10): a signal included.
        rows = [r for r in self.blocks if r.startswith("|") and re.search(r"\bsignal\b", r, re.IGNORECASE)
                and re.search(r"128\s*\+\s*n", r)
                and re.search(r"\bstops?\b", r, re.IGNORECASE)
                and re.search(r"\bnotice\b", r, re.IGNORECASE)]
        self.assertEqual(len(rows), 1, "exactly one signal row: 128+n -> stops with a notice")

    def test_exit_table_is_attributed_to_sandesh_pi_supervision(self):
        self.assertTrue(
            self._blocks_with(r"sandesh-pi", r"supervis", r"exit"),
            "the exit table is recorded as sandesh-pi's supervision treats it",
        )

    def test_only_the_extension_starts_the_supervised_watcher(self):
        self.assertTrue(
            self._blocks_with(r"\bonly\b", r"extension|sandesh-pi", r"\bstart", r"supervised watcher"),
            "sandesh-cli.md must record that only the extension starts the supervised watcher",
        )

    def test_rule_detectors_read_one_block_or_row(self):
        synthetic = (
            "Model B relies on the `sandesh` CLI **0.4.0 or later**.\n\n"
            "| Exit | Reason | sandesh-pi |\n|---|---|---|\n"
            "| `1` | usage or configuration error | stops with a notice |\n"
            "| `3` | tombstoned | relaunches |\n"
        )
        blocks = [b for _, b in _blocks(synthetic)]
        self.assertEqual(blocks[0], "Model B relies on the sandesh CLI 0.4.0 or later.")
        rows_1 = [b for b in blocks if b.startswith("|") and _names_exit(b, "1")]
        rows_3 = [b for b in blocks if b.startswith("|") and _names_exit(b, "3")]
        self.assertEqual(rows_1, ["| 1 | usage or configuration error | stops with a notice |"])
        self.assertFalse(re.search(r"\bnotice\b", rows_3[0]), "a row is judged alone, never with its neighbour")


if __name__ == "__main__":
    unittest.main()
