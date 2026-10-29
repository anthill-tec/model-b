# Contract — lean-ctx on Pi: tool preference + operational findings

**Owner:** LEAN-CTX project (upstream tool provider; `lean-ctx` engine and the `pi-lean-ctx`
Pi extension).
**Status:** FINDINGS — (a) and (b) closed by lean-ctx 3.11.4's answers; the others are recorded
under § Filed requests / gaps for filing (§S3).

## Current state

- **Engine.** `lean-ctx` 3.11.4 (read in its source) is **dual** MCP + CLI, with 79 MCP tools:
  - MCP server: the `ctx_*` tools (read / search / shell / tree / overview / knowledge / …),
    several read modes, tree-sitter AST extraction, compression patterns, and a session
    cache held by the long-running server process;
  - CLI: `lean-ctx -c "<command>"` (compressed shell), `lean-ctx read <file>`,
    `lean-ctx grep <pattern>`, plus management verbs (`doctor`, `gain`, `tools <profile>`,
    `allow`, `verify-cache`, …).
- **Pi extension.** Pi reaches the engine through the `pi-lean-ctx` package (3.11.4; installed
  with `pi install npm:pi-lean-ctx`, a user-level Pi package that Model B neither ships nor
  installs). It registers seven tools itself, in every profile: `ctx_read`, `ctx_shell`,
  `ctx_grep`, `ctx_find`, `ctx_ls`, `ctx_edit` and `lean_ctx`. `ctx_read` and `ctx_edit` go
  through the bridge when it is connected, and `ctx_edit` fails without it.
  - The CLI-backed tools — `ctx_shell`, `ctx_grep`, `ctx_find`, `ctx_ls` — are each a
    `lean-ctx` CLI invocation with compression on.
  - The embedded MCP bridge (on by default; `LEAN_CTX_PI_ENABLE_MCP=0` forces the CLI-only
    path) runs `lean-ctx` as an MCP server over stdio, routes `ctx_read` and `ctx_edit` through
    it so unchanged re-reads hit the session cache, and registers the server's other advertised
    tools as Pi tools.
- **The served tool surface.** The engine resolves it: `LEAN_CTX_TOOL_PROFILE`, then the global
  `tool_profile`, then `tools_enabled` (`ToolProfile::from_config`, `rust/src/core/tool_profiles.rs`).
  - Unpinned, the bridge serves the lazy core, twelve names (`ctx_read`, `ctx_shell`, `ctx_search`,
    `ctx_glob`, `ctx_tree`, `ctx_session`, `ctx_compose`, `ctx_callgraph`, `ctx_patch`, `ctx_call`,
    `ctx_expand` and the `shell` alias, `ShellAliasTool`; `CORE_TOOL_NAMES`,
    `rust/src/tool_defs/mod.rs`) and reaches the rest through `ctx_call`; lean-ctx's own setup
    leaves the profile unpinned.
  - Pinned `standard`, it serves 17 tools plus `ctx_call`; this machine pins `standard`.
  - `pi-lean-ctx`'s `toolProfile` (default `lean`) forwards nothing for `lean`, so the global
    config decides.
  - `tool_profile` applies from a project `.lean-ctx.toml` only once it is trusted.
  - The generated agents' `ctx_callgraph` is served in the lazy core, `standard` and `power`, never
    in `minimal` (or `auto` before it escalates); VERIFY's `ctx_graph` and `ctx_explore` only in
    `standard`, `power` or a `tools_enabled` list naming them (the dependency PRD D5 has this
    contract record).
- **Mode.** The extension's default is **additive**: Pi's own built-in read / shell / search /
  listing tools stay available beside the `ctx_*` tools, and `routeShell` hides `bash` alone.
  `LEAN_CTX_PI_MODE=replace` hides the replaceable built-ins. Pi's native file edit and file
  write are unchanged in every mode.
- **The read cache.** On Pi, `ctx_read` with `mode=full` (or `fresh=true`) is always a fresh disk
  read, never the ~13-token stub; only the other modes re-read an unchanged file cheaply. A read
  without a mode gets the extension's size-based choice, never `auto`.
- **The response budgets.**
  - Every bridged response is cut at `turn_fresh_limit` (4096 tokens), and at
    `turn_fresh_limit_verbatim` (32768) for a `ctx_read` with `mode=raw`; on Pi no other tool
    reaches the verbatim budget. The cut keeps the line that names the recovery path.
  - The CLI-backed `ctx_shell` and `ctx_grep` are not under it.
  - Cited: `enforce_turn_budget`, `rust/src/core/budget.rs`.
- **Governing guidance.** The user's home `AGENTS.md` carries the lean-ctx section Pi loads as
  project context for every project under it: prefer the `ctx_*` tools, because only they are
  compressed and cached — in additive mode the built-ins are not routed through lean-ctx.
- **Checks.** `/lean-ctx` in Pi reports the binary and the bridge state; its `Tool profile:` line
  reports `pi-lean-ctx`'s own setting, and the served set is the bridge's tool list.
  `lean-ctx verify-cache` proves (or disproves) that the session cache engages.

## Preference order (as ruled)

1. `ctx_read` over the built-in file read (modes: `full` for a file you will edit,
   `signatures` for API context, `map` for large files, `diff` after an edit, `lines:N-M` for
   a known region; `anchored` when the edit goes through `ctx_patch`); `full` is always fresh
   on Pi; `raw` for exact bytes.
2. `ctx_shell` over the built-in shell for commands with side effects (build, test, git);
   `ctx_search` / `ctx_grep` over the built-in content search; `ctx_tree` / `ctx_ls` /
   `ctx_find` over the built-in listing and file finding.
3. File edits and new files stay on Pi's native edit and write; `ctx_patch` (anchored by line
   and hash from `ctx_read mode=anchored`) or `ctx_edit` (an extension tool in every profile; it
   needs the bridge) when cache coherence or race protection matters.
4. Compression bypass ladder (only when compressed output hides needed detail):
   `lines:N-M` → `full` → `raw=true` (`ctx_read` `mode=raw` for a file, up to 32768 tokens;
   `ctx_shell` `raw=true` for a command), then return to compressed defaults.

Model B's skills name capabilities, not these tools (DN §D18); this order is the local
practice for a Pi session that has `pi-lean-ctx` loaded, never a dependency a skill assumes.

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
  generated definitions carry their own `tools:`; a `general-purpose.md` in `.pi/agents/` or
  `$PI_CODING_AGENT_DIR/agents/` overrides the built-in type by name (`loadCustomAgents`).
  Model B ships no such override.

## Knowledge store

Model B keeps a project's execution knowledge in lean-ctx's knowledge store, under the
category the project's `.env` names in `KNOWLEDGE_CATEGORY`. The skills name this only as a
capability — "the project's knowledge store" (DN §D18); what follows is what that capability
resolves to on lean-ctx, and what a session must know when using it.

### Knowledge verbs Model B relies on

Model B relies on five knowledge verbs, and no others, each with its `ctx_knowledge` form:
- remember (`remember`) — record one short fact under the category with a stable kebab-case
  key; the same key supersedes the earlier fact;
- list a category (`recall` + `category`): at most the listing limit, with `showing <n>/<total>`;
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
  `showing <n>/<total>`, and only the listed facts are retrieved. Source: `handle_recall`,
  `rust/src/tools/ctx_knowledge/remember.rs`.
- **Decay.** A fact retrieved or confirmed within the last day does not decay. Every other fact
  decays on every lifecycle run, compounding, and every `remember` and `remove` runs the
  lifecycle. A restore runs none. Source: `apply_confidence_decay`,
  `rust/src/core/memory_lifecycle.rs`.
- **Restore.** (`CtxKnowledgeTool`, `rust/src/tools/registered/ctx_knowledge.rs`)
  - It selects its store with `store` (default: all four) and ignores a `category` argument.
  - Unscoped, it restores every store, and other projects' archived facts from the shared legacy
    facts archive.
  - It returns at most 50 items, scoped or not, so it is repeated until it restores nothing.
  - It keeps each fact's archived confidence.
  - The next write re-archives a fact below 0.3.
- **The restore's scope is a substring.** `query` is a case-insensitive substring match over each
  archived fact's category, key and value (`restore_facts`,
  `rust/src/tools/ctx_knowledge/restore.rs`), through the archive root shared by
  every unprotected project. `query=<category>` therefore also restores another project's facts
  under the same category, a category whose name contains it, and any fact whose key or value
  mentions it. Model B removes such a fact at reconciliation and reports it.
- **Removed facts come back.** `remove` deletes only the live fact (`remove_fact`,
  `rust/src/core/knowledge/core.rs`), and the
  archive keeps its copy, so the next restore brings back a fact removed at reconciliation, until
  its archive file is pruned. Model B removes it again and reports it.
- **The archive is bounded and shared.** It keeps 16 files (`DEFAULT_MAX_ARCHIVE_FILES`,
  `rust/src/core/memory_archive.rs`) in the
  root shared by every unprotected project, and each archiving lifecycle run adds one, so other
  projects' activity can prune this project's archived facts. A restore is best-effort; the
  one-listing bound is the prevention.
- **Re-confirmation.** A same-key rewrite re-confirms (the confidence goes to the midpoint).
  `feedback` does not change confidence. Source: `handle_feedback`,
  `rust/src/tools/ctx_knowledge/mod.rs`.
- **Export.** It writes a JSON file of the whole store, and retrieves nothing. Source:
  `handle_export`, `rust/src/tools/ctx_knowledge/mod.rs`.
- **The cap.** The 200-fact cap is shared with automatic captures. `auto_capture` is global-only.
  Source: `KnowledgePolicy`, `rust/src/core/memory_policy.rs`.
- **Rehydration.** A category listing that finds no current fact rehydrates at most 3 archived
  facts at ≥0.6, through `remember` (`rehydrate_from_archives`,
  `rust/src/tools/ctx_knowledge/remember.rs`). So a listing can write: a
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

Where the levers are set, and what the project file does:
- `modelb-axi init` writes the levers to the project root's `.lean-ctx.toml`, under a first-line
  `#` ownership marker, and `modelb-axi agents` re-renders it for an existing project. The file
  raises lean-ctx's default 200-fact cap to 500.
- lean-ctx merges `response_shaping`, `compression_level`, `compression_aggressiveness`,
  `terse_agent` and `behavior_nudges` when the file's text merely contains their name, so no
  comment in the file names one (`Config::merge_local`, `rust/src/core/config/merge.rs`).
- A re-render changes the content hash `lean-ctx trust` pins, so a trusted file is untrusted
  again. An intact file carries no sensitive key, so nothing it sets is lost (`is_trusted_for`,
  `rust/src/core/workspace_trust.rs`).
- Any project file sets `autonomy.silent_preload` (default `true`) over the global value, even
  one that does not name it (`Config::merge_local`, `rust/src/core/config/merge.rs`).

## Filed requests / gaps (operational findings)

### (a) Shell-allowlist friction for project tooling
lean-ctx enforces a restricted shell command allowlist in its MCP tools (233 commands
permitted in the observed configuration — the built-in list plus the extras — configured in
`~/.config/lean-ctx/config.toml`). Project tools that are not on the built-in list are
blocked there — the per-stack Crucible clients (`~/.crucible/clients/<stack>-crucible.py`)
are the recurring case — which pushes those runs off the compressed channel.

History: the additive `lean-ctx allow <cmd>` flow appends to `shell_allowlist_extra` WITHOUT
replacing the built-in list (the extras included `sandesh`, `opensrc`, `python-crucible.py`).
Finding filed: project-tool friction recurred per tool; requested a smoother path (e.g. a
per-project allowlist file, or trusting a declared project-tool directory).

**Closed.** lean-ctx 3.11.4's answer: a trusted project `.lean-ctx.toml` may carry
`shell_allowlist_extra`, merged additively (`Config::merge_local`). Measured in source: the CLI
`-c` path enforces the allowlist for a non-terminal caller (`allowlist_gate`), which is Pi's case.
Model B's AXI commands run with `raw=true` (CR-MDB-090) and so never meet it. The key is the
user's to add, after `lean-ctx trust` (CR-MDB-091 Non-goals).

### (b) File-write redirect block × orchestration scripts
The `ctx_shell` file-write redirect block (guarding against uncontrolled writes) collides
with orchestration scripts whose normal operation writes files (test-report generation,
script-managed logs). The block cannot distinguish a sanctioned orchestration write from an
uncontrolled one, so those invocations must leave the compressed channel entirely. Finding
filed: an escape for declared write targets so orchestration scripts can stay on
`ctx_shell`. Observed before Model B moved to Pi.

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
when the ledger write is skipped (PRD D5, ruled 2026-10-29). Ask: merge under the lock.
Status: to file.

### (k) The status command's profile line
`/lean-ctx` reports the extension's `toolProfile`, not the served surface (PRD D5, ruled
2026-10-29). Ask: report the bridge's tool list. Status: to file.

### (l) The read-mode description
`pi-lean-ctx`'s `readModeSchema` describes `full` as "≤turn budget; raw=true beyond", but its
`ctx_read` has no `raw` parameter (`readSchema`, `extensions/index.ts`): only `mode=raw` works.
Ask: correct the description or add the parameter. Status: to file.
