# Research note — lean-ctx for Model B: context pressure, the tool catalog, AXI envelopes, the knowledge store, per-project setup

**Status:** Research note, 2026-10-29. Its candidate changes (§S9) are filed as CR seeds; nothing here is a ruling.
**Versions:**
- lean-ctx 3.11.4: the `lean-ctx --version` binary, the `pi-lean-ctx` package.json, and `rust/Cargo.toml` at upstream `10a74ea` (2026-10-27).
- Model B: `develop`, as read on 2026-10-29.

**Evidence base:**
- **Upstream source:** `yvgude/lean-ctx` at `10a74ea`, cloned for the study. `src:` paths below are relative to `rust/src/`, and `docs:` paths to the repo's `docs/`.
- **Pi extension:** installed at `~/.pi/agent/npm/node_modules/pi-lean-ctx/extensions/`.
- **Local config and state:** `~/.config/lean-ctx/config.toml`, `~/.local/state/lean-ctx/`, `~/.pi/agent/extensions/pi-lean-ctx/config.json`.
- **Commands run before the tool restriction:** `lean-ctx --version`, `help all`, `ledger status` (twice), `config` (show), `status`, `tools show`, `tools list`.

**Evidence tags**
- **[VL]** verified locally: read in the 3.11.4 source or the installed extension, or seen in a local file or a command already run.
- **[DOC]** as documented in the repo's own docs. This stands in for leanctx.com, which was not fetched.
- **[NC]** not checked live: an inference, or a claim that needs a run this session could not make.

The website pages in the brief were not fetched (`/docs/tools/`, `/docs/configuration/`, `/docs/cli-reference/`, `/docs/concepts/read-modes/`, `/docs/observatory/`, `/docs/cortex/`, `/docs/indexing/`, `/docs/concepts/multi-agent/`, `/docs/journeys/`, `/docs/capabilities/`, `/docs/status/`). Their counterparts in the repo were used: `docs/reference/*.md`, `docs/reference/generated/*.md`, `docs/guides/pi.md`. See §S8 for the list of open items.

---

## §S1 Context pressure and the ledger

### §S1.1 What the ledger counts

The ledger is one JSON file, `ContextLedger { window_size, entries[], total_tokens_sent, total_tokens_saved }`. **[VL]** `src/core/context_ledger/types.rs`

Each entry describes one *source*:
- a file path, or for shell, a label holding the truncated command (`kind = file|shell`);
- `mode`, `original_tokens`, `sent_tokens`, `timestamp`, `state`, `phi` (salience), `view_costs`, `access_count`.

An entry records the **last delivery of that source**, not a history of what is in any conversation:
- A re-read of the same path overwrites the entry. It replaces `sent_tokens` and increments `access_count`. **[VL]** `ledger.rs: record_with_task`, `persistence.rs: persist_entry_at`
- `total_tokens_sent` is the sum of `sent_tokens` over the entries. **[VL]** `persistence.rs`

What writes into the ledger:
- **Reads** through the MCP server. The bridge's `ctx_read` merges each completed read into the file under a lock. **[VL]** `persistence.rs: persist_read`
- **Every shell command run through `lean-ctx -c`.** This covers Pi's `ctx_shell` and **`ctx_grep`**: the latter runs `lean-ctx -c rg --line-number --color=never … -M400 --max-columns-preview <pattern> <path>`, so every search becomes a ledger entry. **[VL]** `pi-lean-ctx/extensions/index.ts` (ctx_grep), `src/core/tool_lifecycle.rs: record_shell_command_named`
- The CLI shell path does `ContextLedger::load()` → `record_shell` → `save()`. That is a whole-file rewrite, not the locked merge the MCP read path uses. **[VL]** source; concurrent lost updates are **[NC]**.

The local file confirms this. It held 198 entries, 133 of them `kind=shell` and 143 with `mode=shell`, most of them `$ rg --line-number …` labels from `ctx_grep`. **[VL]** `~/.local/state/lean-ctx/context_ledger.json`, read 2026-10-29 04:30.

### §S1.2 How pressure is computed

`pressure()` works in three steps. **[VL]** `src/core/context_ledger/ledger.rs`
1. `utilization = total_tokens_sent / window_size`.
2. `effective = min(1.0, utilization + min(0.20, 0.02 × pinned + 0.01 × stale))`.
3. The recommendation follows from `effective`:
   - above 0.90: `EvictLeastRelevant`;
   - above 0.75: `ForceCompression`;
   - above 0.50: `SuggestCompression`;
   - otherwise: `NoAction`.

`remaining_tokens = window_size − total_tokens_sent`, without the boost.

**"Pinned" is mostly automatic.** `ignite_high_salience()` promotes any entry whose phi z-score exceeds 1.5 (once at least 4 entries exist) to `Pinned` on each recorded read. **[VL]** `ledger.rs`, `helpers.rs` (`GWT_IGNITION_Z = 1.5`)

So 10 or more auto-pinned entries add the full 20 points. Locally there were 31 pinned entries, most of them one-off `rg` labels with `access_count = 1`. **[VL]** local file.

### §S1.3 Scope: machine-wide, not per session or project

- `ledger_path("default")` is `$XDG_STATE_HOME/lean-ctx/context_ledger.json`. **[VL]** `helpers.rs`
- A per-agent path (`ledger/<agent>.json`) exists in code but has **no caller**: `load_for_agent` and `save_for_agent` are only ever called with `"default"`. **[VL]** grep over `src/`

Every lean-ctx process on the machine writes the one file: each Pi MCP bridge, every `lean-ctx -c`, and the daemon. The local file held Model B, Crucible, the leanctx.com fetch from this study, and other sessions' work. It held 47 Crucible paths, 63 Model B paths and 88 "other". **[VL]**

So **pressure measures no model's real context window.** It is a machine-wide, recency-pruned tally of "last delivery per source".

### §S1.4 `window_size`

- It is **not a config key.** A new ledger starts at 128 000 (`DEFAULT_CONTEXT_WINDOW`). **[VL]** `helpers.rs`
- On every load it is overwritten from `detected_model.json`, but only if that file is less than 2 hours old. **[VL]** `ledger.rs: load_for_agent`; `src/hook_handlers/observe.rs: load_detected_model`
- `detected_model.json` is written by the **observe hook**, which skips background models (any name containing mini/haiku/flash/…). The window comes from `[model_context_windows]` in config.toml (a name → window table), then a `[1m]` suffix in the name, then the registry, then 200 000. **[VL]** `observe.rs: persist_detected_model`; `src/core/model_registry.rs: context_window_for_model`
- The local `detected_model.json` says `claude-opus-5-5`, `window_size 200000`, `detected_at` 1792648144. That is weeks old, so it is ignored, and the ledger keeps the 200 000 already stored in the file. **[VL]**
- Pi is not known to write `detected_model.json`; no Pi observe hook was found in pi-lean-ctx. **[NC]**

**Answer:** Model B cannot set the window to match its model. `[model_context_windows]` only takes effect when an observe hook has reported a model name within the last 2 hours.

### §S1.5 `included` / `pinned` / `stale`; prune, evict, reset

`ContextState` values in use:
- `Included`: delivered.
- `Pinned`: by salience ignition, or by `ctx_control pin`.
- `Stale`: the `source_hash` changed.
- `Excluded`: set by an overlay.

**[VL]** `ledger.rs`, `src/server/context_gate.rs`, `docs/reference/07-context-engineering.md` **[DOC]**

**Prune** runs automatically on *every* `ContextLedger::load()`. **[VL]** `ledger.rs: prune`, `load_for_agent`
- It decays phi by 0.95 per hour.
- It drops error rows.
- It drops entries older than 7 days with phi below 0.1.
- It dedups by normalised path.
- It caps the ledger at 200 entries by phi.
- If anything was pruned, the ledger is saved.

The file therefore self-limits: nothing survives past about 7 days, and there are never more than 200 entries. **Even `lean-ctx ledger status` can write the file:** when the daemon does not answer, the CLI falls back to `ContextLedger::load()`, which prunes and saves. **[VL]** `src/cli/ledger_cmd.rs`

**Evict** (`ctx_ledger action=evict targets=…`) does two things. **[VL]** `src/tools/registered/ctx_ledger.rs`
- It removes the entries.
- It writes a **session-scoped `Exclude` overlay** into the project's overlay store, so the evicted file is "excluded from re-accumulation until session reset".

From then on, recording a read of that file returns the hint "File '…' is excluded by overlay". **[VL]** `context_gate.rs: post_dispatch_record_with_task`. Whether the content itself is withheld is **[NC]**. Either way, evicting a file you still need is costly.

**Reset** (`ctx_ledger action=reset`) clears every entry, including pinned ones. In the MCP server it also calls `cache.reset_delivery_flags()`. **[VL]** `ctx_ledger.rs`

The cost is the loss of re-read dedup: the next read of every file returns full content instead of the ~13-token "unchanged" stub. **[VL]** source; size of the effect **[NC]**. A CLI `ledger reset` goes to the daemon's ledger and cache, not to an individual Pi bridge's cache. **[VL]** `ledger_cmd.rs` → `try_daemon_tool_call_blocking_text`

### §S1.6 What `ForceCompression` actually changes

`pressure_downgrade()` maps the recommendation to a mode:
- `ForceCompression`: `full`→`map`, `auto`/`map`→`signatures`.
- `EvictLeastRelevant`: also `signatures`→`reference`.

**[VL]** `src/core/auto_mode_resolver.rs`. Its only callers are:
- `intent_router::route_v1`, used by `ctx_intent` and `ctx_plan` recommendations;
- `context_deficit` suggestions;
- `ctx_preload`.

**[VL]** grep for `.pressure()` and `pressure_downgrade`.

In the read path, `apply_reinjection_plan` rewrites the *ledger entry's* `mode` label from `full` to `map` for non-pinned entries. It does not change `sent_tokens` or what the agent received. **[VL]** `context_gate.rs`

Above 0.90, every recorded read appends a nudge, `Context pressure N%. Evict: ctx_ledger(action="evict", targets="…")`. Elicitation hints also fire above a threshold. **[VL]** `context_gate.rs`, `src/server/elicitation.rs`

**Answer:** an explicit `ctx_read mode=…` is **not** downgraded by pressure. The visible effects are:
- bookkeeping in the ledger;
- downgraded *recommendations* from the plan/intent/preload tools;
- eviction nudges, which a Model B agent must not follow (see §S1.8).

### §S1.7 Concurrent sessions and sub-agents

- All sessions and sub-agents share the one file. **[VL]**
- Each Pi process has its own MCP bridge (its own session cache), but writes into the shared ledger. **[VL]** `persistence.rs`, pi-lean-ctx `mcp-bridge.ts`
- The daemon keeps an **in-memory** copy that goes stale against the file. `lean-ctx ledger status` asks the daemon first. **[VL]**
  - Local run: the daemon reported "88% (136780/200000), 164 entries, ForceCompression".
  - The file held 198 entries summing to 160 442 tokens. Computed with 31 pinned entries, that is 0.80 + 0.20 = **100% → EvictLeastRelevant**.
  - The file kept moving during the study (mtime 04:28 → 04:34) because other sessions were writing it. **[VL]**
- `SessionState::load_latest()` on the CLI shell path picks the machine's *latest* session. It then calls `maybe_consolidate(project_root)` on that session's project, so a `ctx_shell` in project A can trigger knowledge consolidation for project B. **[VL]** `tool_lifecycle.rs: record_shell_command_named`; whether this happens in practice is **[NC]**. It matches the contract pitfall "the CLI's project does not follow the working directory".
- Upstream's multi-agent docs are marked "Historical / Research": lean-ctx makes **no** cross-agent coordination or cache contract. **[DOC]** `docs/reference/08-multi-agent.md`

### §S1.8 The documented practice, and what Model B should do

The documented practice is "status → evict → reset (reset only if budget needs full flush)", with the pipeline radar → plan → compile → control/ledger. **[DOC]** `ctx_ledger` tool description; `docs/reference/07-context-engineering.md`

That practice assumes one agent per ledger. Given §S1.3–§S1.7, the recommendation for Model B is:
- **Never evict, prune or reset as routine, and never mid-cycle.**
  - Eviction excludes files.
  - Reset kills dedup for the daemon's cache.
  - Either one affects concurrent sessions, Crucible included.
  - Auto-prune already bounds the file (7 days, 200 entries).
- **Treat pressure nudges as advisory noise.** A sub-agent should not act on an "Evict:" hint appended to a tool result. Templates should say so in one line.
- **Bootstrap / shutdown / CR boundary:** at most a read-only `ledger status` line in the shutdown report. No mutation step anywhere in a Model B run. A user-run `lean-ctx ledger reset` stays the user's call when no other session is live; it is not a workflow step. **[NC]**: this is a recommendation, not a documented lean-ctx rule.
- **The pressure that does matter for a Pi agent** is the per-response turn budget (§S3.3) and Pi's own tool-output cap, not the ledger.

---

## §S2 The tool catalog and Model B roles

### §S2.1 Inventory and profiles

The binary says "79 MCP tools". **[VL]** `lean-ctx --help`; `docs/reference/generated/mcp-tools.md` also says 79 **[DOC]**. The brief cites 78 for the website (not fetched). **[NC]**

`tools list` shows: **[VL]**

| Profile | Tools | What it is |
|---|---|---|
| `lean` | 12 | lazy core + `ctx_call`; the upstream default |
| `minimal` | 5 | |
| `standard` | 17 | |
| `power` | 79 | |
| `auto` | 5→all | |

The `standard` set is `ctx_read ctx_shell ctx_search ctx_glob ctx_tree ctx_compose ctx_explore ctx_knowledge ctx_session ctx_callgraph ctx_graph ctx_delta ctx_execute ctx_expand ctx_overview ctx_url_read ctx_patch`. **[VL]** `src/core/tool_profiles.rs`

**Locally the global config pins `tool_profile = "standard"`.** **[VL]** `config.toml`, `tools show`
- pi-lean-ctx's `toolProfile` defaults to `lean`, but `lean` sets no `LEAN_CTX_TOOL_PROFILE`, so the engine uses the config's `standard`. **[VL]** `pi-lean-ctx/extensions/config.ts: resolveToolProfile`, and the comment at line 316
- The Pi bridge's cached schema lists exactly those 17 + `ctx_call`. **[VL]** `~/.pi/agent/extensions/pi-lean-ctx/mcp-schema-cache.json`
- Pi registers `ctx_read`, `ctx_shell`, `ctx_grep`, `ctx_find`, `ctx_ls`, `ctx_edit` and `lean_ctx` locally. The bridge's same-named `ctx_read`/`ctx_shell` are dropped in favour of the local ones. **[VL]** `index.ts`
- `~/AGENTS.md` and `contracts/lean-ctx.md` both describe the `lean` default ("ctx_patch reachable through ctx_call"). **Locally that is wrong:** `ctx_patch` is first-class.

**This sub-agent session had no `ctx_*` tools at all,** only Read/Write/Edit/Grep/find/ls/Bash. **[VL]** this session's tool list. A sub-agent harness may not forward extension tools unless they are listed. Model B's generated agents do list them in `tools:`.

### §S2.2 Groups

Groups follow `docs/reference/generated/mcp-tools.md`. **[DOC]**

- **Read / search core:**
  - `ctx_read` (modes: auto, full, anchored, raw, map, signatures, diff, `lines:N-M`, `-N` tail, multi-range, reference, task, aggressive, entropy);
  - `ctx_search` (regex | semantic | symbol | find_related; the `queries` batch; `anchored=true`);
  - `ctx_glob`, `ctx_tree`, `ctx_outline`, `ctx_multi_read` and `ctx_smart_read` (folded aliases), `ctx_retrieve`.
- **Understanding:** `ctx_compose` (ranked files + inline source for a task), `ctx_explore` (multi-turn BM25 + graph → `path:start-end` citations), `ctx_overview`, `ctx_repomap`, `ctx_preload`, `ctx_prefetch`.
- **Structure / blast radius:**
  - `ctx_graph`: symbol, neighbors, `impact` (reverse-dependency blast radius), `diff since=<ref>` (git change impact), `path`, `diagram`;
  - `ctx_callgraph`: callers, callees, trace;
  - `ctx_impact`, `ctx_architecture`, `ctx_routes`, `ctx_review`, `ctx_smells`, `ctx_quality`, `ctx_optimize`, `ctx_refactor`.
- **Edit:** `ctx_patch` (hash-anchored, CONFLICT means re-read; `replace_unique`; cross-file `ops[]`), `ctx_edit`, `ctx_delta` (the changed lines since your last read of a file).
- **Shell / exec:** `ctx_shell` (`raw`, `inline`, background jobs), `ctx_execute` (sandbox, 11 languages, shares the shell allowlist), `ctx_expand` (archives, tee handles, `head`/`tail`/`search`/`json_path`).
- **Memory:** `ctx_knowledge`, `ctx_session`, `ctx_summary`, `ctx_memory`, `ctx_handoff`, `ctx_package`, `ctx_pack`, `ctx_checkpoint` (shadow git).
- **Context engineering / observability:** `ctx_ledger`, `ctx_control`, `ctx_plan`, `ctx_compile`, `ctx_fill`, `ctx_compress`, `ctx_context`, `ctx_radar`, `ctx_metrics`, `ctx_heatmap`, `ctx_cache`, `ctx_dedup`, `ctx_live_zone`, `ctx_intent`.
- **Measurement / meta:** `ctx_gain`, `ctx_cost`, `ctx_feedback`, `ctx_benchmark`, `ctx_compare`, `ctx_quality_lab`, `ctx_proof`, `ctx_verify`, `ctx_perf`, `ctx_cognitive`, `ctx_analyze`.
- **Gateways / external:** `ctx_call`, `ctx_discover_tools`, `ctx_load_tools`, `ctx_tools`, `ctx_provider`, `ctx_url_read`, `ctx_git_read`, `ctx_multi_repo`, `ctx_index`, `ctx_artifacts`.
- **Governance / research:** `ctx_rules`, `ctx_skillify`, `ctx_work_graph`, `ctx_transcript_compact`, `ctx_response`, `ctx_crush`, `ctx_compress_memory`, `shell` (an alias).

### §S2.3 Per role

Read-mode facts that matter on Pi (all **[VL]** from `index.ts` and `src/core/budget.rs`):
- **Pi's `ctx_read` never sends `auto`.** Without a mode, the extension picks its own mode by size:
  - config/markdown files: full;
  - code under 8 KB: full; 8–96 KB: `map`; over 96 KB: `signatures`;
  - other files: full under 48 KB, else `map`.
- **`mode=full` in Pi always sets `fresh: true`.** It bypasses the cache stub, so "unchanged re-reads ~13 tokens" applies only to *non-full* modes.
- **Every MCP-bridged response is capped at `turn_fresh_limit = 4096` tokens.** It is truncated with a recovery line. `raw=true`/`mode=raw` raises the cap to `turn_fresh_limit_verbatim = 32768`.
- `offset`/`limit` reads become `lines:N-M` through the bridge. They are cached and bounded, which makes them the right tool for long specs and large files.

| Role | Useful | What for |
|---|---|---|
| Orchestrator: gap analysis | `ctx_explore` (citation=true), `ctx_compose`, `ctx_graph impact` / `ctx_callgraph callers`, `ctx_search action=symbol` | Locating where behaviour lives cheaply; the "rule and behaviour reach" and "public-symbol removal" dimensions of gap analysis (blast radius of a symbol) |
| Orchestrator: spec pre-review | `ctx_read lines:N-M` over the spec, `ctx_search queries=[…]` batched | Reading the spec in bounded windows; checking each AC term against the code |
| Orchestrator: close-out | `ctx_graph action=diff since=develop`, `ctx_shell raw=true` for the gate client | Blast radius of the branch for the sign-off; the gate envelope read whole (§S3) |
| RED / GREEN / FIX / BACKFILL | `ctx_read mode=anchored` → `ctx_patch`; `ctx_delta` after an edit; `ctx_read signatures`/`map` for context; `ctx_search` | Anchored edits never echo old text and CONFLICT on a stale anchor; `ctx_delta` confirms an edit without a full re-read |
| VERIFY | `ctx_graph diff since=<base>` and `impact`, `ctx_callgraph`, `ctx_search action=find_related`, `ctx_read lines:` / `raw` | Checking the change's reach against the spec; reading exact bytes when an AC quotes text |

All of the above are in the local `standard` surface except `ctx_impact`/`ctx_review`/`ctx_outline`, which need `ctx_call`. The generated templates currently grant only `ctx_shell ctx_read ctx_grep ctx_glob ctx_find ctx_ls ctx_patch ctx_edit ctx_search ctx_tree`; VERIFY gets no edit tools. **[VL]** `generator/stacks/*.toml`

None of `ctx_compose`, `ctx_explore`, `ctx_graph`, `ctx_callgraph`, `ctx_delta` or `ctx_expand` is granted.

### §S2.4 Not worth their schema cost for Model B

These are judgement calls, **[NC]**, based on the tool descriptions **[DOC]**:
- **`ctx_session`.** It duplicates the Crucible board and Sandesh as Model B's session state.
- **`ctx_execute`.** It overlaps `ctx_shell`, and Model B forbids ad-hoc script runners.
- **`ctx_overview`.** Its wake-up briefing mixes in other agents' state; `enable_wakeup_ctx = false` locally.
- **`ctx_url_read`.** Fine for the orchestrator, not for TDD agents.
- In `power` only, and conflicting with Model B rules:
  - `ctx_checkpoint` and `ctx_compress_memory`: the first is a shadow git, the second rewrites AGENTS/CLAUDE files and leaves `.original.md` backups;
  - `ctx_rules` and `ctx_skillify`: write rules files;
  - `ctx_memory`: a second fact store.
- The whole measurement/meta and governance groups.

Keep the engine at `standard`. Don't adopt `power`.

---

## §S3 The AXI read-whole rule and `ctx_shell`

### §S3.1 Does `ctx_shell` alter output? Yes, under several conditions

On Pi, `ctx_shell` without `raw` runs `lean-ctx -c '<cmd>'` inside Pi's bash tool, with `LEAN_CTX_COMPRESS=1`. **[VL]** `index.ts: leanCtxSpawnHook`

The CLI path classifies, then compresses. **[VL]** `src/shell/pipeline.rs: exec_buffered`, `src/shell/compress/engine.rs`, `src/shell/output_policy.rs`

1. **Non-zero exit.** Output up to 2000 tokens stays verbatim. Above that, it is compressed if that helps, else head/tail-truncated. **[VL]** `compress_for_outcome_for`
2. **The Crucible client** (`python3 ~/.crucible/clients/python-crucible.py …`) is *not* a recognised test runner: that list holds pytest, cargo test, mvn test, bun test, …. So the client is classified **Compressible**. **[VL]** `is_test_runner_command`, `classify`
3. Outputs under 120 tokens are returned as-is. **[VL]** `min_compression_tokens`
4. **TOON is preserved.** With `preserve_compact_formats = ["toon"]` (the default, and set locally), output that looks like TOON is kept verbatim. "Looks like TOON" means at least one `key[N]{f,…}:` or `key[N]:` header. **[VL]** `looks_like_toon`, `config.toml`
5. **The verbatim path still caps size.** Above 4000 tokens and 60 lines, `truncate_verbatim` keeps the **first 30 and last 20 lines plus up to 200 "safety" lines** from the middle, and drops the rest. **[VL]** `MAX_VERBATIM_TOKENS = 4000`
6. **An envelope without array headers** (a plain `key: value` envelope) goes through the pattern engine, the terse dictionary pipeline (`compression_level`; Pi forwards `lite` locally), `lightweight_cleanup`, and, above 30 lines, `truncate_with_safety_scan`. That last step keeps 5 head lines, 5 tail lines and up to 80 safety lines. **[VL]**
7. **Secret/PII redaction.** The MCP `ctx_shell` redacts secrets *even with `raw=true`*, and `[context_gateway] secrets/pii = "redact"` is on locally. **[VL]** `src/tools/registered/ctx_shell.rs`, `config.toml`. Whether the CLI `-c` path redacts the inline output (as opposed to the tee copy) was not traced. **[NC]**
8. **Pi's own cap.** Pi's bash tool keeps the *last* 2000 lines or 50 KB and saves the full output to a temp file. **[VL]** this harness's bash tool contract. That is the 50 KB cap agents are working around; lean-ctx's caps sit before it.

**Answer:**
- An AXI/TOON envelope under about 4000 tokens normally survives `ctx_shell` byte-for-byte. A larger one is cut down to its head, its tail and its safety lines.
- A non-TOON envelope can be reshaped at any size above 120 tokens.
- **`raw=true` is required for any run whose envelope Model B must read whole.** On Pi, `raw=true` does not invoke lean-ctx at all: it is Pi's plain bash tool, so there is no compression, no lean-ctx redaction and no ledger entry. **[VL]** `index.ts`, `rawBash`

### §S3.2 Is there a sanctioned way to read a long run without filtering?

- **Tee files.**
  - With `tee_mode = "highcompression"` (the default, and set locally), the full pre-compression output is saved when the inline output was elided *and* either the exit code was non-zero or more than 70% was saved. **[VL]** `src/shell/tee_policy.rs`
  - The file goes to `$XDG_STATE_HOME/lean-ctx/tee/<first 40 chars of the command, slugged>_<blake3[:8]>.log`. It is redacted, has a 24-hour TTL, and is overwritten each time the same command runs. **[VL]** `src/shell/redact.rs`. Files exist locally, mostly `cd__home_antonyj_Documents_configuration_*.log`, because agents prefix commands with `cd <dir> &&`. **[VL]**
  - The CLI path prints the path on **stderr**: `[lean-ctx: full output -> PATH (redacted, 24h TTL)]`. **[VL]** `pipeline.rs`
  - Caveats: the tee is *redacted*, so it is not byte-exact. Under the default `home` path jail, `~/.local` is a protected zone, so `ctx_read` on the tee path is likely refused **[DOC]** `docs/reference/appendix-paths-and-config.md` §5; **[NC]** live. Native `read` can read it, and the MCP `ctx_shell` names `ctx_expand(id=<path>)` for this case. **[VL]** `ctx_shell.rs`
- **Archives and `ctx_expand`.** `[archive] enabled` (threshold 800 chars, 48 h, `inline_max_bytes` 32768) applies to the MCP tool pipeline. `ctx_expand id=… head|tail|search|start_line/end_line|json_path` retrieves losslessly. **[VL]** config; **[DOC]** `ctx_expand` description. On Pi, `ctx_shell` is the CLI path, so it produces tee files, not `[Archived:ID]` handles. **[VL]**
- **Pi's temp file.** When Pi's bash tool truncates (raw or not), it saves the full output to a temp file and names it. Reading that file with `read offset/limit` is lossless and involves no agent-side filtering. **[VL]** harness contract.

**Recommendation.** Instead of `| grep -v` / `| head`:
- run the client with **`ctx_shell raw=true`**;
- if Pi truncates, read the named temp file in windows with `read offset=… limit=…` until the envelope is seen whole.

That is lossless, and the agent never chooses what to drop. The client's own output discipline (counts, failing names, assertion lines) is what keeps the envelope small.

Two further options:
- **Exclude the client.** `excluded_commands = ["python3 ~/.crucible/clients/python-crucible.py"]` (the expanded home path, in practice) is a non-sensitive project key, so it needs no trust. But it is a *prefix* match, defeated by `cd … &&` prefixes, and it still ends in `truncate_verbatim`. **[VL]** `classification.rs: is_excluded_command`, `engine.rs`
- **Upstream request.** Ask for the Crucible clients to be classed as test runners, or for a `verbatim_commands` key.

### §S3.3 Output budgets

- `turn_fresh_limit = 4096` and `turn_fresh_limit_verbatim = 32768` apply to **MCP responses only**: the bridge's `ctx_read` and the bridged tools. **[VL]** `src/server/call_tool/pipeline.rs`, `budget.rs`
- `session_token_limit = 200000` (progressive compression at 50/75/90%) exists in config. Its runtime effect on Pi was not traced. **[NC]**

---

## §S4 The knowledge store (feeds CR-MDB-088)

### §S4.1 Storage and lifecycle

Facts are per project (keyed by a hash of `project_root`). Each fact carries:
- `confidence` (a `remember` without a value gets **0.8**);
- `confirmation_count`, `retrieval_count`, `last_retrieved`, feedback;
- validity (`valid_until`).

**[VL]** `src/tools/ctx_knowledge/remember.rs`, `src/core/knowledge/*`

**The capacity is `memory.knowledge.max_facts = 200` per project store.** That is the policy default and the local effective value. **[VL]** `lean-ctx config`; **[DOC]** `appendix-paths-and-config.md` ("source of doctor's 'facts at capacity' warning")

This budget is shared by Model B's category **and lean-ctx's automatic captures**:
- a scheduled consolidation imports up to 5 decisions at 0.9 and 8 findings at 0.75 per pass from the session. **[VL]** `src/core/consolidation_engine.rs: scheduled`
- it fires every 25 tool calls (cooldown 120 s, `autonomy.auto_consolidate = true`). **[VL]** config

`run_lifecycle` runs whenever the store exceeds `max_facts`, and on every scheduled or manual consolidate. **[VL]** `src/core/knowledge/core.rs: enforce_capacity`; `memory_lifecycle.rs`. It has four steps:
1. **Decay (Ebbinghaus).**
   - `confidence ← confidence × exp(−Δt / S)`, where Δt = days since last confirmed *or* retrieved, S = 90 d × (1 + 0.5 × retrievals) × feedback, with a floor of 0.05.
   - It **compounds**: every lifecycle run multiplies again by the retention for the *total* elapsed time, not the time since the last run. **[VL]** `apply_confidence_decay`, `ebbinghaus_confidence`
   - So a fact confirmed 10 days ago and never retrieved falls from 0.8 below 0.3 after about 9 lifecycle runs. Each auto-consolidate is a run. **[VL]** arithmetic from source; observed frequency **[NC]**
2. **Consolidate.** Facts with word similarity of 0.85 or more are merged. **[VL]**
3. **Compact (quality).** **[VL]** `compact`
   - Facts with confidence below `low_confidence_threshold = 0.3` are archived.
   - So are facts older than 30 days with at most 1 confirmation, confidence below 0.5, not retrieved in 14 days and retrieved fewer than 5 times.
   - Optionally, never-retrieved facts are archived after N days. This is off by default.
4. **Capacity reclaim.** When the store is over its cap, it is cut to 75% (`reclaim_headroom_pct = 0.25`), archiving the lowest-sorted tail. **[VL]** `run_lifecycle`

On top of that, **cluster compaction** runs hourly in the cognition loop. It collapses 4 or more mutually similar facts (similarity 0.5, confidence up to 0.5, at most 1 confirmation) into a digest and archives the originals. **[VL]** `core.rs: compact_low_value_clusters`; config `[memory.compaction]`

**Archiving is silent and lossless.** Archived facts go to `memory/archive/<store>/`. Facts use the legacy *global* archive root (scope `None`), with source admission filtering on restore. **[VL]** `memory_lifecycle.rs: archive_facts`, `restore.rs`

### §S4.2 `restore` and the 0.25 confidence

- `restore` (`store`, `query`, `limit`, default 50) merges archived facts back. It **keeps each fact's archived confidence** and skips any key a live fact still owns. **[VL]** `src/tools/ctx_knowledge/restore.rs`
- A fact archived for quality has confidence below 0.3 by definition, so it returns at about 0.25 and **is re-archived on the next lifecycle run**. **[VL]** source logic; matches the CR-MDB-088 observation.
- A restore only sticks if the fact is re-confirmed: a `remember` with the same key, an explicit `confidence`, or `feedback up`.
- `restore` has no dry run. The `dry_run` flag applies to `consolidate` only. **[VL]** `ctx_knowledge.rs`; matches the contract pitfall.
- **Recall-miss rehydration:** a category recall that finds nothing rehydrates from the archives automatically. **[VL]** `remember.rs: handle_recall` → `rehydrate_from_archives`

### §S4.3 Listing a category returns 10, not "every fact"

`ctx_knowledge action=recall category=X` (no query) calls `recall_by_category_for_output(cat, policy.knowledge.recall_facts_limit)`. **[VL]** `remember.rs`, `src/core/knowledge/query.rs`
- **`recall_facts_limit = 10`** locally. **[VL]** config
- Only those 10 get `retrieval_count += 1` / `last_retrieved = now`.
- **The rest of the category keeps decaying.** Retrieval is what slows the decay and blocks compaction (14-day / 5-retrieval guards).

So Model B's bootstrap "list a category" is likely both **incomplete** and **the cause of the silent archiving** for categories over 10 facts. Whether the output says "10 of N" was not checked. **[NC]** `format_facts_with_annotations` takes `total`.

`recall_facts_limit` is **not** in the project-local merge list. It is global-only. **[VL]** `src/core/config/merge.rs`

### §S4.4 The other verbs

- `consolidate`: imports the latest session, runs the lifecycle, then reclaims about 25% across facts/history/procedures. `dry_run=true` previews it. **[VL]**
- `policy`: read-only. `show`/`validate` print the effective `max_facts`, the limits, `decay_rate` and `stale_days`. **[VL]** `mod.rs: handle_policy`
- `health`: read-only. Reports total/current/archived counts, quality buckets, stale candidates, never-retrieved counts and per-room counts. **[VL]** `mod.rs: handle_health`
- `lifecycle_report`, `status`, `timeline`, `rooms`.
- `feedback up|down`: changes stability and does not reset confidence. **[VL]**
- `export` (json, or `format=okf` for a portable Markdown bundle) and `import` (`merge=replace|append|skip-existing`; paths are jailed). `export` is the way to get a **complete** listing. **[VL]** `ctx_knowledge.rs`; output format **[NC]**

### §S4.5 Levers available per project

A project `.lean-ctx.toml` may set these without trust (they are not sensitive): **[VL]** `merge.rs`, `loader.rs: strip_sensitive_overrides`
- `memory.knowledge.max_facts`;
- `memory.lifecycle.decay_rate`, `low_confidence_threshold`, `stale_days`, `similarity_threshold`, `reclaim_headroom_pct`, `reclaim_enabled`;
- `autonomy.auto_consolidate`, `autonomy.consolidate_every_calls`, `autonomy.cognition_loop_enabled`.

`[memory.compaction]` and `recall_facts_limit` are global-only. **[VL]**

Whether the knowledge lifecycle reads the *project-merged* config rather than the global one was not traced. **[NC]**: `load_policy_or_error` was not followed through.

---

## §S5 Per-project setup by stack

### §S5.1 Global config vs project config, and trust

- **Global:** `$XDG_CONFIG_HOME/lean-ctx/config.toml`. Locally that is `~/.config/lean-ctx/config.toml`; **`~/.lean-ctx/` does not exist**. **[VL]**
- **Project:** `<repo>/.lean-ctx.toml`, merged over the global config, with the project winning. Project data lives in `.lean-ctx-id` and `.lean-ctx/`. **[DOC]** `appendix-paths-and-config.md` §1/§3; **[VL]** `loader.rs`, `merge.rs`

**Trust.** `lean-ctx trust [path]` gates the *security-sensitive* project keys. Untrusted workspaces have them stripped, with a warning naming them. **[VL]** `strip_sensitive_overrides`, `merge.rs`
- **Sensitive keys:** `shell_allowlist`, `shell_allowlist_extra`, `allow_paths`, `extra_roots`, `allow_symlink_roots`, `write_allow_paths`, `custom_aliases`, `passthrough_urls`, `redirect_exclude`, `proxy.*_upstream`, `semantic_mode = eager`, `rules_scope`/`rules_injection`, `permission_inheritance`, `disabled_tools`, `tool_profile`, `tools_enabled`, `default_tool_categories`, `index.respect_gitignore = false`, `shell_allowlist_subcommand_scoping = false`.
- **Not sensitive (apply untrusted):** `excluded_commands`, `extra_ignore_patterns`, `index.exclude`/`include`, `tee_mode`, `preserve_compact_formats`, `compression_level`, `archive.*`, `memory.*` (the subset in §S4.5), `autonomy.*`.

**Both filed contract findings have upstream answers.** **[VL]** source; **[NC]** live
- Finding (a) is shell-allowlist friction. A **per-project `shell_allowlist_extra` in `.lean-ctx.toml`** is merged additively once the user runs `lean-ctx trust`.
- Finding (b) is the write-redirect block. **`write_allow_paths`** ("destinations ctx_shell redirects and downloads may write to") exists, global or trusted-project.

On Pi, `ctx_shell` uses the CLI `-c` path. Whether that path enforces the MCP allowlist is still unmeasured, as the contract says. **[NC]**

### §S5.2 Indexing and excludes

- Every walker (graph/BM25 index, `ctx_search`, `ctx_tree`, `ctx_glob`) respects `.gitignore` (`[index] respect_gitignore = true`). **[VL]** config; `src/core/walk_filter.rs`
- They always skip `node_modules`, `__pycache__`, `bower_components`, real virtualenvs (`.venv`/`venv` with `pyvenv.cfg`) and VCS metadata.
- They also skip agent copy directories **`.worktrees`, `.codex-worktrees`, `.claude`, `.cursor`**.
- **`target/`, `build/`, `dist/` are deliberately left to `.gitignore`.** **[VL]** `walk_filter.rs` comment
- Model B's `.worktrees/<cr>` layout is therefore invisible to repo-wide scans from the main root. A `ctx_search` from the main checkout will not see a CR's in-flight worktree code. An explicit `path=` into the worktree still works (depth-0 roots are kept). **[VL]** `walk_filter.rs`; behaviour of a Pi agent whose cwd is the worktree **[NC]**
- Further knobs: `extra_ignore_patterns`, `[index] exclude`/`include`, `graph_index_max_files = 15000`, `bm25_max_files = 5000`. `lean-ctx index status|build|build-full|why <file>` (`why` names the rule that dropped a path). **[VL]** `help all`, config, `ctx_index` description **[DOC]**

What to exclude per stack. Most of this is already covered by a correct `.gitignore`, and `index.exclude` is belt-and-braces. **[NC]**:

| Stack | `index.exclude` / `extra_ignore_patterns` |
|---|---|
| rust | `target/`, `test-reports/`, `*.profraw`, `lcov.info` |
| quarkus / java | `target/`, `.mvn/wrapper/`, `build/`, `.gradle/`, `test-reports/` |
| python | `.venv/` (auto if `pyvenv.cfg`), `*.egg-info/`, `.pytest_cache/`, `.ruff_cache/`, `htmlcov/`, `.coverage*`, `test-reports/`, `dist/` |
| bun | `node_modules/` (auto), `dist/`, `coverage/`, `.turbo/`, `test-reports/` |
| arduino | `build/`, `.pio/`, `.arduino-*`, `test-reports/` |

### §S5.3 What `modelb-axi init` could scaffold, and what a skill should tell the user to run

- **Scaffold a `.lean-ctx.toml`** next to `AGENTS.md` when the installer verdict says lean-ctx is present. Use only non-sensitive keys, so no trust step is needed:
  - per-stack `index.exclude`;
  - `preserve_compact_formats = ["toon"]` (the default; stated explicitly as a contract);
  - knowledge-store settings for CR-MDB-088 (a raised `memory.knowledge.max_facts`, possibly `autonomy.auto_consolidate = false` so lean-ctx's own captures stop consuming the project budget).
- **Tell the user** (in the scaffold's Setup section, not as an automated step):
  - `lean-ctx trust .` only if they add sensitive keys (the crucible client in `shell_allowlist_extra`, report dirs in `write_allow_paths`);
  - `lean-ctx index build` once;
  - `lean-ctx doctor` to confirm.
- Model B must never run `config set`, `trust`, `allow`, `tools <profile>` or `doctor --fix` itself. Those mutate user state.

---

## §S6 Model B's current lean-ctx surfaces (read-only survey)

- **`contracts/lean-ctx.md`.** **[VL]**
  - It describes 3.10.2 and the `lean` profile default; locally it is 3.11.4 and `standard`.
  - It states the preference order and the bypass ladder `lines:N-M` → `full` → `raw=true`.
  - It lists the knowledge verbs (remember, list, restore, remove) and their pitfalls.
  - Its two findings (allowlist friction, write-redirect block) are filed as open.
- **Templates and agents.** **[VL]** `generator/templates/{red,green,verify,fix}.md.tmpl`; `generator/stacks/*.toml`
  - The `tools:` lists grant `ctx_shell ctx_read ctx_grep ctx_glob ctx_find ctx_ls ctx_search ctx_tree`, plus `ctx_patch ctx_edit` for the writing roles. VERIFY gets no edit tools.
  - The text says to prefer lean-ctx for output over 20 lines, to read docs with `ctx_read` (`map`) then `ctx_search` then `lines:N-M`, and that the crucible client via `ctx_shell` is "the short-command exception".
  - It also says "the client's envelope is read whole and is never piped, filtered or redirected away". Nothing says `raw=true`.
  - The arduino stack mentions `ctx_read mode:"signatures"`.
- **`skills-src/`:** no `ctx_` or lean-ctx mentions. Skills name capabilities only (DN §D18). **[VL]** grep
- **`AGENTS.md` § Runtime/Tooling:** "Prefer lean-ctx reads (`ctx_read`/`ctx_search`/`ctx_shell`/`ctx_tree`) over raw file/grep/shell calls." **[VL]**
- **`~/AGENTS.md`:** the preference table, `raw=true` "when exact output matters", `mode=anchored` + `ctx_patch` "reachable through `ctx_call` in the default `lean` profile" (stale locally), and the bridge notes. **[VL]**
- **Local Pi config:** `~/.pi/agent/extensions/pi-lean-ctx/config.json` holds `routeShell: true` (native `bash` hidden for the main agent), `LEAN_CTX_COMPRESSION_LEVEL=lite` and `LEAN_CTX_SAVINGS_FOOTER=never`. **[VL]**

---

## §S7 Docs vs local behaviour: disagreements

1. **Ledger status vs file.**
   - Daemon `ledger status`: 88%, 164 entries, ForceCompression.
   - On-disk file: 198 entries, 160 442 tokens, which works out to 100% / EvictLeastRelevant.
   - Cause: the daemon's in-memory copy is stale against the file. **[VL]**
2. **Tool count.** The brief cites 78 for the website; the binary and generated docs say 79. **[VL]**/**[NC]**
3. **Tool profile.** The docs say pi-lean-ctx defaults to `lean`, and `ctx_patch` is reachable via `ctx_call`. Locally the engine serves `standard` (17 + `ctx_call`) because config.toml pins it. **[VL]**
4. **`compression_level`.** The docs give a default of `lite` (`appendix-paths-and-config.md`). The local global value is `standard`; Pi forwards `lite`. **[VL]**/**[DOC]**
5. **`ForceCompression`.** The docs present it as pressure management. In code it only relabels ledger entries and steers the plan/intent/preload recommendations; explicit reads are unaffected. **[VL]**
6. **Window size.** The ledger is described as "context pressure", but the window is not configurable without a detected model, and the ledger is machine-wide. **[VL]**
7. **"Unchanged re-reads cost ~13 tokens"** (pi-lean-ctx `ctx_read` description). In Pi, `mode=full` always forces `fresh`, so the claim holds only for non-full modes. **[VL]**
8. **"List a category"** (contract). The engine returns `recall_facts_limit = 10` facts, not every fact. **[VL]**
9. **"Passthrough output … ZERO modification"** (`output_policy.rs` doc comment). The compress path still runs `truncate_verbatim` for Passthrough/Verbatim output above 4000 tokens. **[VL]** `engine.rs`. The exec-level handling of Passthrough was not traced. **[NC]**
10. **"Read-only" CLI verbs can write.** `ledger status` falls back to load+prune+save when the daemon is down. **[VL]**

---

## §S8 Open items (not run in this session)

- **CLI commands:** `lean-ctx doctor` (no `--fix`), `cache stats`, `knowledge status`, `gain --by-tool`, `verify-cache`, `index status`, `security status`, `safety-levels`.
- **Website pages** in the brief, not fetched: `/docs/tools/`, `/docs/configuration/`, `/docs/cli-reference/`, `/docs/concepts/read-modes/`, `/docs/observatory/`, `/docs/cortex/`, `/docs/indexing/`, `/docs/concepts/multi-agent/`, `/docs/journeys/`, `/docs/capabilities/`, `/docs/status/`.
- **Live checks still needed:**
  - Whether the CLI `-c` path redacts inline output. Run `ctx_shell` on a command printing a fake token, with and without `raw`.
  - Whether a crucible-client envelope over 4000 tokens is head/tail-cut.
  - Whether `ctx_read` on a tee path is refused by the path jail.
  - Whether `recall category=` reports "10 of N".
  - Whether the knowledge lifecycle honours project `.lean-ctx.toml` `memory.*`.
  - Whether Pi writes `detected_model.json`.
  - Whether the CLI shell path's load/save loses concurrent ledger entries.

---

## §S9 Candidate Model B changes (ranked)

| # | Surface | Change | Why | Size |
|---|---|---|---|---|
| 1 | Generated agent templates (`red`, `green`, `verify`, `fix`, plus BACKFILL wherever it is rendered) and the matching gates | Crucible-client runs go through **`ctx_shell` with `raw=true`**. If Pi reports truncation, read the named full-output file with `read offset/limit` until the envelope is seen whole. Never `| grep`/`| head`/`| tail`. | §S3.1: compression can cut or reshape an envelope (4000-token head/tail cap, non-TOON reshaping, redaction); `raw=true` on Pi bypasses lean-ctx entirely. §S3.2: Pi's saved temp file gives a lossless way past the 50 KB cap with no agent-side filtering. | S (template text, then `build.py build` for 20 agents, plus the anchor/grep gates) |
| 2 | Skill (`bootstrap` Step 0.6), `contracts/lean-ctx.md` knowledge section, CR-MDB-088 spec | Load a category from a complete source (`export`, or recall with a raised `recall_facts_limit`), not a bare category recall. After `restore`, **re-confirm** each restored fact (same-key remember or `feedback up`), or it is re-archived. Document `max_facts = 200` shared with auto-captures, compounding decay, cluster compaction, and that `restore` has no dry run. | §S4.2–§S4.3: the 10-fact recall leaves the rest decaying; restored facts come back at about 0.25, below the 0.3 archive threshold. | M |
| 3 | `modelb-axi init` (+ installer verdict) | Scaffold a non-sensitive `.lean-ctx.toml`: per-stack `index.exclude`, `preserve_compact_formats = ["toon"]`, a raised `memory.knowledge.max_facts`, optionally `autonomy.auto_consolidate = false`. Add a Setup line telling the user to `lean-ctx trust .` only if they add sensitive keys, and to run `lean-ctx index build`. | §S4.5, §S5.1–§S5.3: these levers are project-scoped and need no trust; the auto-captures compete for the fact budget. | M (template + tests; stdlib TOML text only) |
| 4 | `contracts/lean-ctx.md` | Refresh to 3.11.4. Correct the profile to the local `standard` and explain the `lean` vs config interaction. Note that `mode=full` is always fresh on Pi, the 4096/32768 turn budgets, and that `ctx_grep` writes ledger entries. Close findings (a) and (b) with the upstream answers (`shell_allowlist_extra` in a trusted `.lean-ctx.toml`; `write_allow_paths`). Add a "ledger is machine-wide; never mutate it in a run" section. | §S1, §S2.1, §S5.1, §S7 | S |
| 5 | Generated templates (all roles) + `model-b` sub-agent procedure reference | One line: ignore "Context pressure … Evict: ctx_ledger(…)" hints, and never call `ctx_ledger evict/reset`. Shutdown may report a read-only `ledger status` line; no bootstrap or CR-boundary ledger step. | §S1.3–§S1.8: one shared ledger; eviction excludes files, reset kills dedup for other sessions; the nudge fires constantly with 10 or more auto-pinned entries. | S |
| 6 | Stack TOML `tools:` (orchestrator brief / VERIFY / GREEN) | Grant `ctx_graph` (impact, `diff since=`), `ctx_callgraph`, `ctx_explore`, `ctx_delta` to the roles in §S2.3; `ctx_compose` to the orchestrator only. Keep `ctx_session`, `ctx_execute` and `power`-only tools out. | §S2.3: blast radius for gap analysis, VERIFY and close-out; `ctx_delta` replaces post-edit re-reads. | S–M (TOML + regenerate + permission gates) |
| 7 | `AGENTS.md` § Runtime/Tooling (Model B) | Add the read-whole exception (`raw=true` for envelopes), the worktree note (repo-wide `ctx_search` from the main checkout skips `.worktrees/`; pass an explicit `path=`), and "the ledger is machine-wide". | §S3, §S5.2, §S1.3 | S |
| 8 | Upstream (LEAN-CTX, via the contract's findings) | File these: per-agent or per-project ledger scoping, or at least excluding shell/grep labels from pressure; the uncapped influence of auto-pinning (20 points from 10 one-off `rg` calls); daemon/file divergence; compounding decay per lifecycle run; category recall silently capped at 10; CLI shell-path load/save race and latest-session consolidation; a verbatim class for declared test clients. | §S1, §S4, §S3 | S (writing) |
| 9 | `~/AGENTS.md` (user-owned, outside Model B; raise with the user) | Correct "default `lean` profile" to what is actually served, and note that `mode=full` is never a cache hit on Pi. | §S2.1, §S7 | XS |
