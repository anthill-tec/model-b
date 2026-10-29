# CR-MDB-092 — The lean-ctx contract refreshed; each role gets the lean-ctx tools that serve it

**Status:** PENDING — spec drafted 2026-10-29 from the gap analysis and the user's rulings (PRD D5, 2026-10-29); spec pre-review to follow.
**Type:** feature (the contract; the stack files' `tools:`, one template paragraph and its built-in
passage, the generated agents; Model B's `AGENTS.md` and the scaffolded lean-ctx section) + upstream
findings recorded
**Priority:** P2.
**Depends on:** CR-MDB-090 (same templates; merged). Board-authoritative: read `queue`, not this line.
**Labels:** lean-ctx, contracts, agents, generator
**Points:** 5 (re-scored at gap analysis; seeded 5).
**Design reference:**
- `contracts/lean-ctx.md` (the interface this CR refreshes); PRD § Scope ("This effort ships AXI CLI
  **contracts** … not implementations … Implementations live in their own repos").
- PRD D5, amendment of 2026-10-29 (CR-MDB-090's ruling): the tool form lives in the agent templates, Model
  B's own `AGENTS.md` and the lean-ctx section `init` scaffolds; the skills name capabilities.
- PRD D10 and CR-MDB-045 §S8: the built-in form (`builtin_form`, `generator/templates/builtin-tools.toml`).
- DN-multi-harness-deploy-model §D17 (definitions rendered per harness carry the tool names) and §D18
  (a shared skill names capabilities, never a harness's tools).
- CR-MDB-089 Non-goals (hands this CR "whether the generated agents should have `process` or more lean-ctx
  tools"); CR-MDB-088 and CR-MDB-091 Non-goals (the rest of the contract, findings (a) and (b)); CR-MDB-090
  Non-goals (the contract's ledger section, the verbatim-class request).
- Research note `lean-ctx-for-model-b` §S2, §S5.1, §S7, §S9 items 4, 6 and 8.
- Gap analysis: `/tmp/mdb092/gap-analysis.md` (2026-10-29).

## Context

Every fact below is read in lean-ctx 3.11.4's source (`rust/src/…`, upstream `10a74ea`), the installed
`pi-lean-ctx` 3.11.4 (`extensions/index.ts`, `extensions/config.ts`) or the installed
`@gotgenes/pi-subagents`, and cited by path and symbol.

- **The contract records 3.10.2 and a `lean` default.** The engine and the extension are 3.11.4
  (`rust/Cargo.toml`, `pi-lean-ctx/package.json`).
- **The engine, not the extension, decides the served tools.** `ToolProfile::from_config`
  (`rust/src/core/tool_profiles.rs`) reads `LEAN_CTX_TOOL_PROFILE`, then the global config's
  `tool_profile`, then `tools_enabled`.
  - **Unpinned** (lean-ctx's setup default, `clear_profile_in_config`): the bridge advertises the lazy core,
    `CORE_TOOL_NAMES` (`rust/src/tool_defs/mod.rs`): `ctx_read`, `ctx_shell`, `ctx_search`, `ctx_glob`,
    `ctx_tree`, `ctx_session`, `ctx_compose`, `ctx_callgraph`, `ctx_patch`, `ctx_call`, `ctx_expand`. The
    rest is reached through `ctx_call` (`candidate_set`, `explicit_profile`,
    `rust/src/server/tool_visibility.rs`).
  - **Pinned `standard`:** `STANDARD_TOOLS`, 17 tools, plus `ctx_call`. This machine pins it
    (`~/.config/lean-ctx/config.toml`).
  - `pi-lean-ctx`'s `toolProfile` defaults to `lean`, which forwards no `LEAN_CTX_TOOL_PROFILE`
    (`resolveToolProfile`, `config.ts`), so the global config decides. `tool_profile` is a sensitive key: a
    project `.lean-ctx.toml` sets it only once trusted (`strip_sensitive_overrides`,
    `rust/src/core/config/loader.rs`).
  - The extension registers `ctx_read`, `ctx_shell`, `ctx_grep`, `ctx_find`, `ctx_ls`, `ctx_edit` and
    `lean_ctx` itself, in every profile; `ctx_edit` is never "reached through `ctx_call`" on Pi.
  - `/lean-ctx`'s `Tool profile:` line prints the extension's `toolProfile`, not what the engine serves.
- **A `mode=full` read is always fresh on Pi.** The extension's `ctx_read` sets `wantsFresh` for an
  explicit `full`, so the "~13-token unchanged re-read" holds only for the other modes.
- **MCP responses are budgeted.** `enforce_turn_budget` (`rust/src/core/budget.rs`) caps every bridged
  response at `turn_fresh_limit` (4096 tokens), or `turn_fresh_limit_verbatim` (32768) when `raw` is
  requested (`verbatim_requested`, `rust/src/server/call_tool/pipeline_triage.rs`), keeping the recovery
  line. The CLI-backed `ctx_shell` and `ctx_grep` are not under it.
- **`ctx_grep` writes the ledger.** It runs `lean-ctx -c rg …`; `exec_buffered`
  (`rust/src/shell/pipeline.rs`) calls `record_shell_command_named` (`rust/src/core/tool_lifecycle.rs`),
  which loads, records and saves the one machine-wide ledger. So does every non-raw `ctx_shell`; a
  `raw=true` `ctx_shell` is Pi's plain bash (`rawBash`) and writes nothing.
- **The two filed findings are answered.**
  - (a) A trusted project `.lean-ctx.toml` may carry `shell_allowlist_extra`, merged additively
    (`Config::merge_local`, `rust/src/core/config/merge.rs`). The CLI `-c` path enforces the allowlist when
    stderr is not a terminal (`allowlist_gate`, `allowlist_must_enforce_inner`,
    `rust/src/shell/exec/execution.rs`), which is Pi's case.
  - (b) `write_allow_paths`, global or trusted-project, widens where `ctx_shell` may redirect. Empty means
    the OS temp directories, and the session's project is always allowed (`capture_roots`). The check runs
    only in the MCP `CtxShellTool::handle` (`rust/src/tools/registered/ctx_shell.rs`), never on Pi's CLI
    path.
  - Since CR-MDB-090, Model B's AXI commands run with `raw=true` and never reach lean-ctx.
- **Role tools.** The generated agents grant `ctx_shell ctx_read ctx_grep ctx_glob ctx_find ctx_ls
  ctx_search ctx_tree`, plus `ctx_patch ctx_edit` for the writing roles.
  - `ctx_callgraph` (callers and callees of one symbol, about 147 schema tokens) is served on every profile.
  - `ctx_graph` (`impact`; `diff since=<ref>`; about 300 tokens) and `ctx_explore` are served only under
    `standard` or `power`.
  - **`ctx_delta` adds nothing:** `ctx_delta::handle` (`rust/src/tools/ctx_delta.rs`) delegates to
    `ctx_read` `mode=diff`, which every role already has.
  - **`ctx_compose` needs no grant:** the orchestrator is the main Pi session, which already has every
    served tool, and the project policy already allows it (`_LEAN_CTX_TOOLS`).
  - A tool intent outside `PI_TOOL_NAMES` (`modelb_axi/agents.py`) is dropped by `translate_tools`, so a new
    grant needs its entry.
- **Why a `general-purpose` sub-agent had no `ctx_*` tool (2026-10-29).**
  - pi-subagents' built-in `general-purpose` declares no `toolNames` (`DEFAULT_AGENTS`,
    `src/config/default-agents.ts`), and `AgentTypeRegistry.getToolNamesForType`
    (`src/config/agent-types.ts`) then returns `BUILTIN_TOOL_NAMES`: `read bash edit write grep find ls`.
    `Explore` and `Plan` get `read bash grep find ls`.
  - The `subagent` tool takes no tools parameter, and no settings key may name a capability tool (README
    § Non-goals): only an agent file's `tools:` admits one.
  - A `general-purpose.md` in `.pi/agents/` or `$PI_CODING_AGENT_DIR/agents/` overrides the built-in by name
    (`loadCustomAgents`). Model B's workflow dispatches its own typed definitions, which carry `tools:`.

## Scope

### §S1 — The contract's current state

`contracts/lean-ctx.md`:

1. **The header.** `**Status:**` reads: "FINDINGS — (a) and (b) closed by lean-ctx 3.11.4's answers; the
   others are recorded under § Filed requests / gaps for filing (§S3)."
2. **§ Current state, Engine.** "`lean-ctx` 3.11.4 (read in its source) is **dual** MCP + CLI", with 79 MCP
   tools. The CLI bullet is kept.
3. **§ Current state, Pi extension.**
   - It names `pi-lean-ctx` 3.11.4.
   - It names the seven tools the extension registers itself, in every profile: `ctx_read`, `ctx_shell`,
     `ctx_grep`, `ctx_find`, `ctx_ls`, `ctx_edit`, `lean_ctx`. `ctx_read` and `ctx_edit` go through the
     bridge when it is connected, and `ctx_edit` fails without it.
4. **A new bullet, "The served tool surface"**, states in one unit:
   - the engine resolves it: `LEAN_CTX_TOOL_PROFILE`, then the global `tool_profile`, then `tools_enabled`;
   - unpinned, the bridge serves the lazy core (the eleven names in Context) and the rest through `ctx_call`;
   - pinned `standard`, it serves 17 tools plus `ctx_call`;
   - `pi-lean-ctx`'s `toolProfile` (default `lean`) forwards nothing for `lean`, so the global config decides;
   - lean-ctx's own setup leaves the profile unpinned;
   - `tool_profile` applies from a project file only once it is trusted;
   - this machine pins `standard`.
   The old "(`lean` default, `standard`, `power`); tools outside it (e.g. `ctx_edit` under `lean`) stay
   reachable through `ctx_call`" is removed.
5. **§ Current state, Mode.** In additive mode, `routeShell` hides `bash` alone.
6. **A new bullet, the read cache.** On Pi, `ctx_read` with `mode=full` (or `fresh=true`) is always a fresh
   disk read, never the ~13-token stub; only the other modes re-read an unchanged file cheaply. A read
   without a mode gets the extension's size-based choice, never `auto`.
7. **A new bullet, the response budgets.**
   - Every bridged response is cut at `turn_fresh_limit` (4096 tokens), and at `turn_fresh_limit_verbatim`
     (32768) when `raw=true` or `mode=raw` is requested; the cut keeps the line that names the recovery path.
   - The CLI-backed `ctx_shell` and `ctx_grep` are not under it.
   - Cited: `enforce_turn_budget`, `rust/src/core/budget.rs`.
8. **§ Current state, Checks.** `/lean-ctx`'s `Tool profile:` line reports `pi-lean-ctx`'s own setting; the
   served set is the bridge's tool list.
9. **§ Preference order.**
   - Item 1 gains: "`full` is always fresh on Pi; `raw` for exact bytes."
   - Item 3's "`ctx_edit` (through `ctx_call` under the `lean` profile)" becomes "`ctx_edit` (an extension
     tool in every profile; it needs the bridge)".
   - Item 4's ladder ends "… → `raw=true` (`ctx_read` `mode=raw` for a file, up to 32768 tokens; `ctx_shell`
     `raw=true` for a command)".

### §S2 — Two new sections

Both are `##` sections, placed after § Preference order and before § Knowledge store, so
`knowledge_store_section` still reads § Knowledge store whole.

1. **`## Context ledger`.** It states, in units of its own:
   - One file, machine-wide: `$XDG_STATE_HOME/lean-ctx/context_ledger.json` (`ledger_path`,
     `rust/src/core/context_ledger/helpers.rs`). The per-agent path has no caller: `load_for_agent` is only
     called with `"default"`.
   - Who writes it:
     - bridged reads (`persist_read`);
     - every `lean-ctx -c`, which on Pi means every non-raw `ctx_shell` and every `ctx_grep`
       (`record_shell_command_named`);
     - the daemon.
     A `raw=true` `ctx_shell` writes nothing.
   - What "pressure" is: tokens sent over a fixed window, plus a pinned/stale boost capped at 0.20
     (`pressure`, `rust/src/core/context_ledger/ledger.rs`). It measures no model's context. Auto-pinned
     one-off shell entries alone can saturate the boost (`ignite_high_salience`).
   - Model B's rule, cited to CR-MDB-090: ignore its evict hints, and never evict or reset it during a run.
     A `lean-ctx ledger status` can write the file when the daemon does not answer.
2. **`## Sub-agents`.** It states, in one unit:
   - a pi-subagents dispatch type with no `tools:` (`general-purpose`) gets Pi's built-ins only
     (`read bash edit write grep find ls`); `Explore` and `Plan` get `read bash grep find ls`
     (`getToolNamesForType`);
   - only an agent file's `tools:` admits a `ctx_*` tool;
   - a `general-purpose.md` in `.pi/agents/` or `$PI_CODING_AGENT_DIR/agents/` overrides the built-in by name;
   - Model B's generated definitions carry their own `tools:`.

### §S3 — Filed requests / gaps

1. **(a) closed.** The finding keeps its history line, and gains:
   - the upstream answer: `shell_allowlist_extra` in a trusted `.lean-ctx.toml`, merged additively
     (`Config::merge_local`);
   - the measured fact that the CLI `-c` path enforces the allowlist for a non-terminal caller
     (`allowlist_gate`);
   - that Model B's AXI commands run `raw=true` (CR-MDB-090) and so never meet it;
   - that the key is the user's to add, after `lean-ctx trust` (CR-MDB-091 Non-goals).
   The sentence "whether that path applies the same allowlist has not been measured here" is removed.
2. **(b) closed.** It gains:
   - the answer, `write_allow_paths`, global or trusted-project;
   - its default: the OS temp directories, and the session's project is always allowed;
   - `shell_allow_writes`;
   - that the check runs only in the MCP `ctx_shell` (`CtxShellTool::handle`), never on Pi's CLI path.
   "Not re-measured under `pi-lean-ctx`" is removed.
3. **New findings, recorded for filing (PRD D5, ruled 2026-10-29).** Each finding is one unit. Each carries:
   - what it is;
   - its source path and symbol;
   - the ask;
   - the status word "to file".
   The findings:
   - **(c)** per-agent or per-project ledger scoping: `load_for_agent` is only called with `"default"`;
   - **(d)** auto-pinning one-off shell labels (`ignite_high_salience`) saturates the 0.20 pinned/stale boost
     (`pressure`); the ask is to exclude shell labels from ignition;
   - **(e)** the daemon's in-memory ledger disagrees with the file (`ledger status` asks the daemon first);
   - **(f)** decay compounds per lifecycle run (`apply_confidence_decay`,
     `rust/src/core/memory_lifecycle.rs`);
   - **(g)** a category listing is capped by the global-only `recall_facts_limit`, with no per-call or
     per-project limit, though it reports `showing <n>/<total>` (`handle_recall`,
     `rust/src/tools/ctx_knowledge/remember.rs`); only the listed facts are protected from decay;
   - **(h)** a verbatim class for declared test clients: the Crucible clients are not in
     `is_test_runner_command`, and `excluded_commands` is a prefix match;
   - **(i)** the CLI shell path rewrites the whole ledger file (`ContextLedger::load`/`save` in
     `record_shell_command_named`, not the locked merge of `persist_read`), and consolidates the machine's
     latest session's project (`SessionState::load_latest`) (PRD D5, ruled 2026-10-29);
   - **(j)** `pi-lean-ctx` calls `ctx_session` `action=invalidate` after a native edit, an action
     `ctx_session` does not have (`rust/src/tools/ctx_session.rs`); the effect is still to be checked live
     (PRD D5, ruled 2026-10-29);
   - **(k)** `/lean-ctx` reports the extension's `toolProfile`, not the served surface (PRD D5, ruled 2026-10-29).
4. **Filing** is the user's act (PRD D5, ruled 2026-10-29). No AC depends on it. When an issue is opened, its URL is
   added to the finding in a docs-only commit.

### §S4 — The role tools (PRD D5, ruled 2026-10-29)

1. **`PI_TOOL_NAMES`** (`modelb_axi/agents.py`) gains `"ctx_callgraph"`, `"ctx_graph"` and `"ctx_explore"`,
   each mapped to itself.
2. **Every stack file** (`generator/stacks/{arduino,bun,python,quarkus,rust}.toml`):
   - `[roles.red]`, `[roles.green]` and `[roles.fix]` `tools` gain `"ctx_callgraph"` after `"ctx_tree"`;
   - `[roles.verify]` `tools` gains `"ctx_callgraph", "ctx_graph", "ctx_explore"` after `"ctx_tree"`.
3. **No role gets** `ctx_delta` (it is `ctx_read` `mode=diff`), `ctx_compose` (the main session already has
   it), `ctx_call` (it would open every registered tool, writers included), `ctx_session`, `ctx_execute`,
   `ctx_expand`, `ctx_overview`, `ctx_url_read`, `ctx_knowledge` or `process`.
4. **No change** to `_LEAN_CTX_TOOLS`, `workflow_tools` or the project permission policy: they already allow
   all three. Each definition's `permission:` block follows its `tools:` line (`_emit_pi`).
5. **The built-in form** drops the three new tools with every other `ctx_*` tool (`builtin_form`); no code
   changes.

### §S5 — VERIFY's reach paragraph

`generator/templates/verify.md.tmpl` § "Tool Usage" gains one paragraph after the existing one, exactly:

> **Blast radius (read-only).** For each new public symbol, `ctx_callgraph` (`action=callers`) lists its call
> sites; `ctx_graph` (`action=diff`, `since=<base>`) shows the files the branch reaches, and `action=impact`
> what depends on a changed file; `ctx_explore` (`citation=true`) locates where a behaviour lives. Where
> lean-ctx does not serve one of them (its default tool profile serves `ctx_callgraph` alone), `grep` for the
> callers and run `git diff <base>..HEAD --stat` for the files.

`generator/templates/builtin-tools.toml` gains one `[[passage]]` whose `lean` is that paragraph's text and
whose `builtin` is:

> **Blast radius (read-only).** For each new public symbol, `grep` its name for its callers;
> `git diff <base>..HEAD --stat` shows the files the branch reaches.

The paragraph:
- is its own unit;
- names no crucible client and does not contain `output discipline` or `output-discipline`, so CR-MDB-090's
  render pin and `line_rule_findings` are untouched;
- restates no `FIELD_RULES` rule.

RED, GREEN and FIX get no body text: `ctx_callgraph`'s description is its instruction.

### §S6 — Regeneration

- `generator/agents/*.md` (20) is re-rendered with `generator/build.py build`, and `--check` is clean.
- `.pi/agents/python-*.md` is re-rendered, byte-identical to `generator/agents/python-*`.

### §S7 — The orchestrator's text (PRD D5, ruled 2026-10-29)

1. **`AGENTS.md` § Runtime/Tooling** gains one bullet, one list item with no nested list:
   > **Reach tools** for gap analysis, the spec pre-review and close-out: `ctx_graph` (`action=impact`;
   > `action=diff`, `since=develop`), `ctx_callgraph` (`action=callers`), `ctx_explore` and `ctx_compose`.
   > lean-ctx serves `ctx_graph` and `ctx_explore` only under its `standard` or `power` tool profile. A
   > sub-agent has only the tools its definition's `tools:` lists; a dispatch type with none
   > (`general-purpose`) gets Pi's built-ins and no `ctx_*` tool.
2. **`modelb_axi/scaffold.py` `_render_lean_ctx_section`** gains the same bullet, after the CR-MDB-090
   bullet, with `since=develop` written `since=<base>`. The section is still rendered for every project
   whatever the verdict (CR-MDB-088), and an existing project's `AGENTS.md` is not re-rendered.

Constraints:
- `test_python_floor` stays green;
- the lines `CLAUDE_HOME_EXEMPT_LINES` match are untouched;
- no module is added, so `AGENTS.md`'s two module counts (114) stay.

### §S8 — The gates

The gates match normalised text (lower-cased, `**` and backticks dropped), unit by unit (`rule_units`,
imported from `tests/test_execution_knowledge_rules.py`). A unit is a list item with its nested items, or a
paragraph.

1. **`tests/test_contracts.py` gains `LeanCtxContractRefreshTest`** and two module-level detectors.
   - **`contract_refresh_findings(text) -> list[str]`** returns the name of each pin no single unit of its
     section satisfies:
     - § Current state:
       - `version`: `\blean-ctx 3\.11\.4\b`;
       - `extension version`: `\bpi-lean-ctx\b` and `\b3\.11\.4\b`;
       - `served surface`: `\btool_profile\b`, `\blean_ctx_tool_profile\b`, `\btoolprofile\b`,
         `\blazy core\b`, `\bstandard\b`, `\bctx_call\b`, `\btrust`;
       - `ctx_edit`: `\bctx_edit\b`, `\bevery profile\b`, `\bbridge\b`;
       - `fresh full`: `mode=full`, `\bfresh\b`, `\b13\b|\bstub\b`;
       - `budgets`: `\b4096\b`, `\b32768\b`, `\braw\b`, `turn_fresh_limit`;
       - `routeShell`: `\brouteshell\b`, `\bbash\b`;
       - `profile line`: `/lean-ctx`, `\btool profile\b`, `\bserved\b`.
     - § Context ledger:
       - `ledger writers`: `\bctx_grep\b`, `lean-ctx -c`, `raw=true`, `\bnothing\b|\bno entry\b`;
       - `machine-wide`: `\bmachine-wide\b`, `\bevict`, `\breset`, `\bnever\b`;
       - `pressure`: `\bpressure\b`, `\bwindow\b`, `0\.20`.
     - § Sub-agents:
       - `sub-agents`: `\bgeneral-purpose\b`, `tools:`, `\bbuilt-?ins?\b`, `general-purpose\.md`.
     - § Filed requests / gaps:
       - `(a) closed`: `\bshell_allowlist_extra\b`, `\.lean-ctx\.toml`, `lean-ctx trust`, `\bclosed\b`,
         `\ballowlist_gate\b`;
       - `(b) closed`: `\bwrite_allow_paths\b`, `lean-ctx trust`, `\bclosed\b`, `\bctxshelltool\b`;
       - `(c)`: `\bload_for_agent\b`, `\bto file\b`;
       - `(d)`: `\bignite_high_salience\b`, `0\.20`, `\bto file\b`;
       - `(e)`: `\bdaemon\b`, `\bdisagree`, `\bto file\b`;
       - `(f)`: `\bapply_confidence_decay\b`, `\bcompound`, `\bto file\b`;
       - `(g)`: `\brecall_facts_limit\b`, `\bshowing\b`, `\bglobal-only\b`, `\bto file\b`;
       - `(h)`: `\bis_test_runner_command\b`, `\bverbatim\b`, `\bto file\b`;
       - (PRD D5, ruled 2026-10-29) `(i)`: `\brecord_shell_command_named\b`, `\bload_latest\b`; `(j)`:
         `\bctx_session\b`, `\binvalidate\b`, `\blive\b`; `(k)`: `/lean-ctx`, `\btoolprofile\b`,
         `\bto file\b`.
   - **`contract_retired_findings(text) -> list[str]`** returns the name of each retired phrase present
     anywhere in the contract:
     - `\b3\.10\.2\b`;
     - `\blean default\b`;
     - `\bunder the lean profile\b`;
     - `\bhas not been measured here\b`;
     - `\bnot re-measured\b`;
     - `\bsilently capped\b`;
     - `\buncapped\b`.
2. **`tests/test_pi_agent_definitions.py` gains `RoleLeanCtxToolsTest`** and
   `reach_paragraph_findings(body, *, lean) -> list[str]`, which needs exactly one unit beginning
   `blast radius`:
   - **lean form:** the unit carries `\bctx_callgraph\b`, `action=callers`, `\bctx_graph\b`, `action=diff`,
     `since=<base>`, `action=impact`, `\bctx_explore\b`, `\bgrep\b` and `git diff <base>\.\.head --stat`;
   - **built-in form:** it carries `\bgrep\b` and `git diff <base>\.\.head --stat`, and no `ctx_`;
   - **both forms:** the unit matches neither `\boutput[- ]discipline\b` nor `-crucible\.py\b|\bcrucible[- ]client`.
3. **`tests/test_context_ledger_rule.py`'s `AGENTS.md` pins** gain the reach unit (PRD D5, ruled 2026-10-29):
   `\bctx_graph\b`, `\bctx_callgraph\b`, `\bstandard\b`, `\bgeneral-purpose\b`, `tools:`.
4. **`tests/test_project_tools_setup.py` `pointer_findings`** gains a finding for a missing reach bullet, with
   the same five patterns (PRD D5, ruled 2026-10-29).

## Acceptance criteria

New tests live in the modules §S8 names; no module is added. No test reads `~/.config/lean-ctx`, `~/.pi`,
`/tmp/leanctx-study` or runs `lean-ctx`: lean-ctx's and pi-subagents' facts are cited in the contract's text,
never asserted against an installed copy.

- [ ] **§S1–§S3, the contract.**
      - `contract_refresh_findings(contracts/lean-ctx.md)` is `[]`;
      - `contract_retired_findings(contracts/lean-ctx.md)` is `[]`.
      - These stay green unmigrated:
        - `ContractsS5Test` (`allowlist`, `dual`);
        - `tests/test_execution_knowledge_rules.py`'s contract checks (`CONTRACT_VERBS`, `CONTRACT_SETUP`,
          `CONTRACT_SOURCE_VERSION`, `CONTRACT_LEVERS`, `CONTRACT_NOT_STOPPED`, `CONTRACT_LEVERS_ROOT`,
          `CONTRACT_LARGER_CATEGORY`, `pitfall_citation_findings`, `retired_verb_wording_findings`);
        - `tests/test_lean_ctx_project_config.py`'s §S5 pins;
        - `test_lean_ctx_contract_names_no_harness_tool` and its Pi / `pi-lean-ctx` check
          (`tests/test_worktree_layout_and_bundles.py`);
        - the chezmoi gate (`tests/test_installer_assets.py`).
      - § Knowledge store's text is byte-identical to `develop`'s: the test compares the
        `knowledge_store_section` of the file with that of `git show develop:contracts/lean-ctx.md`, and
        skips, naming the reason, in a shallow clone.
- [ ] **§S8.1, each contract detector proved both ways on synthetic text.**
      - **Pass:** a conforming sample, `GOOD_LEAN_CTX_CONTRACT`, passes both detectors.
      - **One cut per pin:** removing one pin's distinguishing word from its unit returns exactly that pin's
        name.
      - **Split units:** a pin split across two units bites, and so does a pin's unit moved into another
        section (`served surface` moved into § Filed requests).
      - **Retired phrases:** each retired phrase inserted into the sample returns exactly its name.
      - **Today's text:** today's contract, as committed on `develop` before §S1, makes
        `contract_refresh_findings` return at least `version`, `served surface`, `budgets`, `machine-wide`,
        `sub-agents`, `(a) closed` and `(b) closed`, and `contract_retired_findings` return at least the
        `3.10.2`, `lean default` and `has not been measured here` phrases.
- [ ] **§S4, the tools lines.** For every stack, `agents.render_definitions` in memory, in the lean-ctx form:
      - RED, GREEN and FIX's `tools:` is exactly today's 16 names plus `ctx_callgraph`, in TOML order;
      - VERIFY's is today's 12 plus `ctx_callgraph`, `ctx_graph` and `ctx_explore`;
      - VERIFY carries none of `write`, `edit`, `ctx_patch`, `ctx_edit`, `ctx_call`, `ctx_delta`,
        `ctx_compose`;
      - no definition carries `ctx_delta`, `ctx_compose`, `ctx_call` or `process`;
      - each `permission:` block allows exactly the `tools:` names (`PermissionPolicyS4Test`, unmigrated);
      - `build.py`'s drop report is empty: no intent is dropped;
      - `_pi_tool_violations` over the real stack files is `[]`.
      The tool-set check is proved both ways on fixture lines: it bites a VERIFY line without `ctx_graph`, a
      GREEN line carrying `ctx_delta`, and a VERIFY line carrying `ctx_call`; it spares the conforming lines.
- [ ] **§S4, the built-in form.** For every stack and role, rendered with `lean_ctx=False`:
      - no `ctx_*` tool is in `tools:`;
      - `tools:` is today's non-`ctx_*` names plus `bash` (`assert_builtin_form`, unmigrated);
      - no `AgentRenderError` is raised.
- [ ] **§S4, unchanged policy.** `requirements._LEAN_CTX_TOOLS` and `permission_policy.render_policy()` are
      byte-identical to `develop`'s (`tests/test_installer_sandesh_requirements.py` and
      `tests/test_project_permission_policy.py`, unmigrated).
- [ ] **§S5, VERIFY's paragraph.** For every stack:
      - `reach_paragraph_findings(verify body, lean=True)` is `[]` in the lean-ctx form, and
        `reach_paragraph_findings(…, lean=False)` is `[]` in the built-in form;
      - RED, GREEN and FIX bodies have no unit beginning `blast radius`;
      - CR-MDB-090's render pin, `line_rule_findings` and `FIELD_RULES`' written-once check stay green
        unmigrated;
      - `test_s5_no_body_instructs_a_tool_absent_from_its_own_tools_line` stays green unmigrated.
      `reach_paragraph_findings` is proved both ways:
      - it bites a lean sample without the fallback clause, a lean sample without `ctx_graph`, a built-in
        sample still naming `ctx_callgraph`, two blast-radius units, and a sample whose unit also says
        `output discipline`;
      - it spares both conforming samples.
- [ ] **§S6.**
      - `generator/build.py --check` is clean;
      - `.pi/agents/python-*` is byte-identical to `generator/agents/python-*`;
      - `RegenerationCleanTest` and `test_s9_pi_agents_equal_the_agents_render_for_python` are green.
- [ ] **§S7, the orchestrator's text (PRD D5, ruled 2026-10-29).**
      - The `AGENTS.md` reach pin passes on § Runtime/Tooling.
      - A sandboxed `init` (`HOME`, `MODELB_HOME`, `XDG_DATA_HOME` and `PI_CODING_AGENT_DIR` at temp dirs)
        renders a lean-ctx section that passes the extended `pointer_findings`.
      - Each new pin is proved by a cut, and its mutation bites.
      - `test_python_floor`, the `CLAUDE_HOME_EXEMPT_LINES` check, and both module counts (114) stay green.
- [ ] **D18 holds.**
      - `skills-src/` is unchanged, so `git diff develop -- skills-src` is empty.
      - `TOOL_BASELINE == {}` stays green with the widened `PI_TOOL_NAMES` vocabulary.
- [ ] **Migrations (RED).** These pins move with the change, each marked `# MIGRATED at CR-MDB-092 (§S…)`:
      - **`tests/test_pi_agent_definitions.py`** (§S4):
        - `WRITE_CAPABLE_TOOLS` gains `"ctx_callgraph"`;
        - `READ_ONLY_TOOLS` gains `"ctx_callgraph", "ctx_graph", "ctx_explore"`;
        - the failure messages' "16 write-capable" and "12-name read-only" become 17 and 15.
        `UnknownIntentDropS2Test`'s fixture reads `WRITE_CAPABLE_TOOLS` and needs no edit.
      - **`tests/test_project_tools_setup.py`** (§S7): `GOOD_POINTER` and
        `LeanCtxPointerDetectorTest.MUTATIONS`.
      - **`tests/test_context_ledger_rule.py`** (§S7): its conforming `AGENTS.md`
        Runtime/Tooling sample gains the reach bullet.
      Before committing, RED greps `tests/` for `ctx_tree"`, `READ_ONLY_TOOLS`, `WRITE_CAPABLE_TOOLS`,
      `3.10.2` and the retired contract phrases, and lists every further pin it moved, by id.
- [ ] **A live check, before the merge.** In a Pi session on the branch, the orchestrator dispatches the
      python VERIFY agent in spec pre-review mode on this CR's spec (a read-only dispatch). Its report states
      which of `ctx_callgraph`, `ctx_graph` and `ctx_explore` its session had, and the result of one
      `ctx_callgraph` `action=callers` call on `render_policy`. The observation goes into the merge sign-off;
      no test pins lean-ctx's output.
- [ ] **Runs.**
      - The suite is green through the client, with a real `HOME` and with an empty one; the empty `HOME`
        stays empty.
      - `ruff check` exits 0.
      - New tests use a literal `§`.
      - `AGENTS.md`'s baselines match the measured suite.

## Non-goals

- **Filing the upstream issues** (PRD D5, ruled 2026-10-29). It is a public act under the user's account. The CR
  records each finding with its evidence; issue URLs are added later in a docs-only commit.
- **A `general-purpose.md` override** in `.pi/agents/` or under `$PI_CODING_AGENT_DIR` (PRD D5, ruled 2026-10-29).
  It would own a third-party default type for every dispatch in the project. Model B's workflow dispatches its
  typed definitions, and the fact is recorded in the contract and `AGENTS.md`.
- **Setting the user's lean-ctx tool profile** (PRD D5, ruled 2026-10-29): no `config set`, no `lean-ctx profile`, no
  `pi-lean-ctx` `toolProfile`, and no `tool_profile` in the scaffolded `.lean-ctx.toml`, where it is a
  sensitive key. The contract records the dependency; VERIFY's paragraph carries a fallback.
- **`ctx_delta`, `ctx_compose`, `ctx_call` and the rest of `standard`** for sub-agents (§S4.3).
- **`process` for sub-agents** (CR-MDB-089's hand-off). CR-MDB-090's long-run rule already
  covers a long client run. CR-MDB-083, which widens VERIFY's runs, is where it is revisited if a run
  outgrows Pi's tool timeout.
- **The web tools** (`web_fetch`, `web_search`) for VERIFY's spec pre-review. CR-MDB-089 did not hand them
  here; they need their own ruling.
- **Removing `ctx_grep`** from the definitions, though it writes ledger entries: the ledger is advisory, and
  its rule is to ignore it.
- **`~/AGENTS.md`** (the user's), whose "`ctx_patch` reachable through `ctx_call` in the default `lean`
  profile" is stale. It is raised with the user.
- **Re-rendering existing projects' definitions or `AGENTS.md`.** `modelb-axi agents` re-renders the
  definitions on request; `migrate` (CR-MDB-082) owns the rest.
- **pi-subagents' comment/code mismatch** ("toolNames omitted — means all available tools"). It is
  pi-subagents' matter, not lean-ctx's.
- **Correcting the research note.** It is a dated record; the corrections live in the gap analysis.
- **Changing § Knowledge store or § Project-scoped levers** (CR-MDB-088's and CR-MDB-091's).

## Cycle plan

No commit sits red: each cycle commits after its GREEN, with its migrations, once `ruff check` exits 0. The
full suite is not run between cycles; each cycle runs only the modules it names, through the client. Every
cycle that edits `modelb_axi/` also runs the package-wide gates `tests.test_installer_correctness`,
`tests.test_claude_era_retirement` and `tests.test_installer_stack_selection`.

1. **The contract** (§S1, §S2, §S3, §S8.1). Red-green.
   - **RED:** writes `LeanCtxContractRefreshTest` and its two detectors, and proves each pin both ways.
   - **GREEN:** edits `contracts/lean-ctx.md` only.
   - **Modules:**
     - `tests.test_contracts`
     - `tests.test_execution_knowledge_rules`
     - `tests.test_lean_ctx_project_config`
     - `tests.test_worktree_layout_and_bundles`
     - `tests.test_harness_neutral_skills`
     - `tests.test_installer_assets`
     - `tests.test_tooling_detachment`
     - `tests.test_cite_by_symbol`
     - `tests.test_client_path_anchoring`
     - `tests.test_suite_hygiene`
2. **The role tools and VERIFY's paragraph** (§S4, §S5, §S6, §S8.2). Red-green.
   - **RED:** migrates `WRITE_CAPABLE_TOOLS`/`READ_ONLY_TOOLS`, and writes `RoleLeanCtxToolsTest` with
     `reach_paragraph_findings`, proved both ways.
   - **GREEN:** edits `PI_TOOL_NAMES`, the five stack files, `verify.md.tmpl` and `builtin-tools.toml`, runs
     `generator/build.py build`, and re-renders `.pi/agents/python-*`.
   - **Modules:**
     - `tests.test_pi_agent_definitions`
     - `tests.test_client_path_anchoring`
     - `tests.test_project_tools_setup`
     - `tests.test_verify_spec_pre_review_mode`
     - `tests.test_axi_envelope_read_whole`
     - `tests.test_agent_definition_rules`
     - `tests.test_client_run_rule`
     - `tests.test_agent_generator`
     - `tests.test_generator_role_contract`
     - `tests.test_rust_stack_generator`
     - `tests.test_stack_skills`
     - `tests.test_worktree_isolation_text`
     - `tests.test_harness_neutral_skills`
     - `tests.test_installer_sandesh_requirements`
     - `tests.test_harness_capability_contract`
     - `tests.test_project_permission_policy`
     - `tests.test_agents_verb_permission_policy`
     - the package-wide gates
3. **The orchestrator's text** (§S7, §S8.3–§S8.4). Red-green.
   - **RED:** extends the `AGENTS.md` pins and `pointer_findings`, and migrates `GOOD_POINTER`/`MUTATIONS` and
     the conforming Runtime/Tooling sample.
   - **GREEN:** edits `AGENTS.md` § Runtime/Tooling and `_render_lean_ctx_section`.
   - **Modules:**
     - `tests.test_context_ledger_rule`
     - `tests.test_project_tools_setup`
     - `tests.test_scaffold`
     - `tests.test_project_registry_schema`
     - `tests.test_project_setup_section`
     - `tests.test_python_floor`
     - `tests.test_suite_hygiene`
     - `tests.test_cite_by_symbol`
     - `tests.test_tooling_detachment`
     - `tests.test_prd_criteria`
     - `tests.test_harness_neutral_skills`
     - the package-wide gates
4. **Verify.**
   - VERIFY runs the full suite without coverage, as its branch check (DN §D26), and reads every AC.
   - The orchestrator runs the live check, then the pre-merge gate, and records the `AGENTS.md` baselines at
     close-out.
