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
- **Mode.** The extension's default is **additive**: Pi's own built-in read / shell / search /
  listing tools stay available beside the `ctx_*` tools. `LEAN_CTX_PI_MODE=replace` hides the
  replaceable built-ins. Pi's native file edit and file write are unchanged in every mode.
- **Governing guidance.** The user's home `AGENTS.md` carries the lean-ctx section Pi loads as
  project context for every project under it: prefer the `ctx_*` tools, because only they are
  compressed and cached — in additive mode the built-ins are not routed through lean-ctx.
- **Checks.** `/lean-ctx` in Pi reports the binary, the bridge state and the active `ctx_*`
  tool names; `lean-ctx verify-cache` proves (or disproves) that the session cache engages.

## Preference order (as ruled)

1. `ctx_read` over the built-in file read (modes: `full` for a file you will edit,
   `signatures` for API context, `map` for large files, `diff` after an edit, `lines:N-M` for
   a known region; `anchored` when the edit goes through `ctx_patch`).
2. `ctx_shell` over the built-in shell for commands with side effects (build, test, git);
   `ctx_search` / `ctx_grep` over the built-in content search; `ctx_tree` / `ctx_ls` /
   `ctx_find` over the built-in listing and file finding.
3. File edits and new files stay on Pi's native edit and write; `ctx_patch` (anchored by line
   and hash from `ctx_read mode=anchored`) or `ctx_edit` (through `ctx_call` under the `lean`
   profile) when cache coherence or race protection matters.
4. Compression bypass ladder (only when compressed output hides needed detail):
   `lines:N-M` → `full` → `ctx_shell` with `raw=true`, then return to compressed defaults.

Model B's skills name capabilities, not these tools (DN §D18); this order is the local
practice for a Pi session that has `pi-lean-ctx` loaded, never a dependency a skill assumes.

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
