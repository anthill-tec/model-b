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

## Knowledge store

Model B keeps a project's execution knowledge in lean-ctx's knowledge store, under the
category the project's `.env` names in `KNOWLEDGE_CATEGORY`. The skills name this only as a
capability — "the project's knowledge store" (DN §D18); what follows is what that capability
resolves to on lean-ctx, and what a session must know when using it.

### Knowledge verbs Model B relies on

Model B relies on five knowledge verbs, and no others, each with its `ctx_knowledge` form:
- remember (`remember`) — record one short fact under the category with a stable kebab-case
  key; the same key supersedes the earlier fact;
- list a category (`recall` + `category`) — every fact in the category (bootstrap's load);
- restore (`restore`, `store=facts`, `query=<category>`, repeated until it restores nothing)
  — bring the category's archived facts back (bootstrap runs it before listing), and restore by
  key (`restore`, `store=facts`, `query="<category> <key>"`);
- remove (`remove`) — delete a fact once the repo tracks it (the GC rule);
- export (`export`) — the fallback for an incomplete listing.

### Setup path

How a project gets lean-ctx set up, in order:
- the installer probes lean-ctx and records its verdict in `install.toml` `[capabilities]`;
- then `modelb-axi init` reads that verdict, and runs no probe of its own. It writes
  `KNOWLEDGE_CATEGORY` to `.env` (`<PROJECT_TOKEN>-workflow` in kebab-case, or the
  `--knowledge-category` override; each monorepo sub-project carries its own) and the lean-ctx
  pointer section to the scaffolded `AGENTS.md` whatever the verdict.

A monorepo's sub-projects derive the same category as the root when they share its token, so
the root and its sub-projects keep their execution knowledge together.

### Pitfalls

- A query recall is not a full listing: it returns what matches the query, so loading a
  category is always a listing.
- Facts get archived silently: the store moves facts out of the category's listing on its own,
  without notice. Restore the category before listing it.
- `restore` ignores `dry_run`: a dry run restores for real.
- The CLI's project does not follow the working directory: `lean-ctx knowledge` run from a
  sub-project may read or write another project's store. A session uses its knowledge
  capability, never that CLI.
- The store holds lean-ctx's automatic captures in their own rooms beside the project's
  category; they are not the project's facts and are never loaded.

The new pitfalls, each citing its lean-ctx 3.11.4 source path and symbol:
- **The listing limit.** A listing shows at most `memory.knowledge.recall_facts_limit` facts (10).
  The key is global-only, not settable in a project's `.lean-ctx.toml`. The listing says
  `showing <n>/<total>`, and only the listed facts are retrieved.
- **Decay.** A fact retrieved or confirmed within the last day does not decay. Every other fact
  decays on every lifecycle run, compounding, and every `remember` and `remove` runs the
  lifecycle. A restore runs none.
- **Restore.**
  - It selects its store with `store` (default: all four) and ignores a `category` argument.
  - Unscoped, it restores every store, and other projects' archived facts from the shared legacy
    facts archive.
  - It returns at most 50 items, scoped or not, so it is repeated until it restores nothing.
  - It keeps each fact's archived confidence.
  - The next write re-archives a fact below 0.3.
- **The restore's scope is a substring.** `query` is a case-insensitive substring match over each
  archived fact's category, key and value (`restore_facts`), through the archive root shared by
  every unprotected project. `query=<category>` therefore also restores another project's facts
  under the same category, a category whose name contains it, and any fact whose key or value
  mentions it. Model B removes such a fact at reconciliation and reports it.
- **Removed facts come back.** `remove` deletes only the live fact (`remove_fact`), and the
  archive keeps its copy, so the next restore brings back a fact removed at reconciliation, until
  its archive file is pruned. Model B removes it again and reports it.
- **The archive is bounded and shared.** It keeps 16 files (`DEFAULT_MAX_ARCHIVE_FILES`) in the
  root shared by every unprotected project, and each archiving lifecycle run adds one, so other
  projects' activity can prune this project's archived facts. A restore is best-effort; the
  one-listing bound is the prevention.
- **Re-confirmation.** A same-key rewrite re-confirms (the confidence goes to the midpoint).
  `feedback` does not change confidence.
- **Export.** It writes a JSON file of the whole store, and retrieves nothing.
- **The cap.** The 200-fact cap is shared with automatic captures. `auto_capture` is global-only.
- **Rehydration.** A category listing that finds no current fact rehydrates at most 3 archived
  facts at ≥0.6, through `remember` (`rehydrate_from_archives`). So a listing can write: a
  Track that only lists makes no write of its own, but its listing may.

### Project-scoped levers

**The project-scoped levers** (no trust needed), and the values Model B sets through CR-MDB-091
(PRD D5, 2026-10-29: a cap of 500, automatic consolidation off):
- `memory.knowledge.max_facts` raised to 500;
- `autonomy.auto_consolidate = false`.

`auto_consolidate = false` does not stop consolidation on MCP shutdown and on compaction, nor
automatic captures.

The levers apply through the bridge process's resolved project root (normally the git top
level, so a monorepo's root file). A user who wants a larger category raises the global
`recall_facts_limit` themselves.

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
