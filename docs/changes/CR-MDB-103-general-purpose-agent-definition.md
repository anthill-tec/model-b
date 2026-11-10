# CR-MDB-103 — A general-purpose agent definition with the approved tools

**Status:** PENDING — **SEED, not the finished spec** (filed 2026-11-10 by the user's rulings, relayed as
Crucible #1572). Gap analysis, the spec and its pre-review happen in order when this CR starts.
Pre-review: due (it supersedes a ruling, touches the lean-ctx contract and answers another project).
**Type:** feature (an agent definition)
**Priority:** P1 — release 1.0.0, wave 2 (user 2026-11-10; board-authoritative: read `queue`).
**Depends on:** none on the board.
**Labels:** agents, generator, scaffold, lean-ctx
**Design reference:** PRD D10 item 8 (project-level agent definitions; the 2026-11-10 ruling beneath it);
DN-multi-harness-deploy-model §D17 (discovery order); CR-MDB-092 (lean-ctx contract refresh and role
tools, whose out-of-scope item this supersedes); `contracts/lean-ctx.md`.

## Context

pi-subagents' built-in `general-purpose` type has no agent file, and its default definition declares no
tools. The extension admits a capability tool only through an agent file's `tools:` frontmatter, so a
`general-purpose` child gets Pi's built-ins and no lean-ctx `ctx_*` tool, no SoL-Pi tool and no pi-lens
tool. The permission policy denies raw `bash`, so the child falls back to the built-in `read`/`grep`/`find`.
Crucible's research and drafting agents hit it on 2026-11-10 ("Bash denied … no ctx_* tools exposed").

CR-MDB-092 recorded the gap and kept the override out of scope (ruled 2026-10-29): Model B's workflow
dispatches its typed definitions. `AGENTS.md` says so ("a dispatch type with none (`general-purpose`)
gets Pi's built-ins and no `ctx_*` tool"). The user ruled on 2026-11-10 to ship the override.

## Scope (seed)

1. **A `general-purpose.md` definition, rendered per project into `.pi/agents/`** by `modelb-axi init` and
   `modelb-axi agents`, beside the phase agents. It is stack-independent: one file per project, not one
   per stack. The installer deploys no agent definitions (PRD D10 item 8 stands).
2. **Its `tools:`, each one also allowed under its `permission:`:**
   - lean-ctx: `ctx_shell`, `ctx_read`, `ctx_grep`, `ctx_glob`, `ctx_find`, `ctx_ls`, `ctx_patch`,
     `ctx_search`, `ctx_tree`, `ctx_edit`, `ctx_compose`, `ctx_explore`, `ctx_graph`, `ctx_callgraph`,
     `ctx_delta`, `ctx_expand`, `ctx_execute`, `ctx_knowledge`, `ctx_session`, `ctx_overview`,
     `ctx_url_read`, `ctx_call`, `lean_ctx`;
   - SoL-Pi: `update_plan`, `obs_recall`;
   - pi-lens: `lens_diagnostics`, `symbol_search`, `module_report`, `read_symbol`, `read_enclosing`,
     `project_report`, `effective_config`;
   - the built-ins `read`, `write`, `edit`, `grep`, `find`, `ls`, for paths outside the project only,
     under the same note the phase agents carry;
   - `web_search`, `web_fetch`;
   - `process` and `todo` (user 2026-11-10);
   - never raw `bash`, and no user-interactive tool (`ask_user_question`): the definition always runs as
     a sub-agent, with no user to answer it (user 2026-11-10).
3. **Its body rules:** inside the project, the `ctx_*` tools (`ctx_read` with `lines:N-M`;
   `ctx_grep`/`ctx_find`/`ctx_ls`), never `sed`/`cat`/`head`/`tail`/`grep`/`ls` through `ctx_shell`; AXI
   and board envelopes read whole, one verb per call, never piped; `update_plan` for multi-step work and
   `obs_recall` for large results; long runs through `process`; never a GUI application launched from
   the shell, not even with `--help`; the caller's brief binds (write boundaries, no board contact
   unless the brief says so).
4. **The texts that state the gap change with it:** `AGENTS.md`'s reach-tools line, the lean-ctx contract's
   `sub-agents` section, the orchestration references, and the guards that pin them
   (`tests.test_context_ledger_rule`, `tests.test_project_tools_setup`, `tests.test_contracts`).
5. **Crucible is told when it merges,** with the version or commit, so it switches its research and
   drafting dispatches back to `general-purpose` (#1572).

## To measure at gap analysis

- pi-subagents' released source: how a project's `general-purpose.md` overrides the built-in, which
  frontmatter keys it honours, and whether `permission:` is the policy's or the extension's.
- Which approved tools each extension actually registers on the installed versions (lean-ctx's tool
  profile decides whether `ctx_graph`/`ctx_explore` exist; CR-MDB-092).
- Where the rendering lives: the generator, a fixed template, or `init`/`agents`' file plan.
- The re-score (5 points filed) and the behaviour units.
