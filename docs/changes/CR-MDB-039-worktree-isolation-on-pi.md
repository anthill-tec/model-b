# CR-MDB-039 — Worktree isolation on Pi: enter and exit a worktree from the Model B Pi package

**Status:** PENDING
**Type:** fix
**Priority:** P1 — release 1.0.0, wave 2 (Crucible board); the write boundary is the workflow's
isolation floor
**Depends on:** CR-MDB-031 (the `.worktrees/<cr>` layout, `contracts/worktree-layout.md`)
**Labels:** worktree, pi-package, hooks, skills, isolation
**Design reference:** DN-multi-harness §D16 (dispatch), §D18 (capability words);
`contracts/worktree-layout.md`; CR-MDB-029 (the Model B Pi package); PRD D11 (capability contract)

## Context

The skills tell an orchestrator to "make the worktree your session's working directory and dispatch
every sub-agent with the worktree as its working directory". On Pi neither half could be done until
now: a session's cwd is fixed at launch, and the dispatch tool has no working-directory parameter.
The write-boundary hook (`block-write-outside-worktree`) therefore enforced only for a session
launched inside the worktree or with `WF_WORKTREE_ROOT` exported before launch.

Measured 2026-09-25 on the installed Pi 0.87.1 with `@gotgenes/pi-subagents` 21.7.6:

1. **pi-subagents has a workspace seam.** `getSubagentsService()` (published on `globalThis` under
   `Symbol.for("@gotgenes/pi-subagents:service")`, `src/service/service.ts:169-179`) exposes
   `registerWorkspaceProvider(provider)`, which returns an unregister function; only one provider may
   be registered (`subagent-manager.ts:238-246`). A provider's `prepare({agentId, agentType,
   baseCwd})` returns a `Workspace` `{cwd, dispose}` — "already exists when handed back"
   (`lifecycle/workspace.ts`). `prepare` throwing fails that child's run (`subagent.ts:336-349`).
2. **A relocated child is rooted there.** The child session is created with that directory as its
   cwd and loads that directory's resources and extensions (`create-subagent-session.ts:208-266`).
   Pi's shell tool runs in the session cwd (`dist/core/tools/bash.js:160`, `ctx?.cwd || cwd`), and
   `ctx_shell` wraps it; `.pi/agents` and the project's hook extensions resolve there too.
3. **One process, one environment.** Children run in the parent's process, and the compiled hook
   extension spawns its script with the process environment (`modelb_axi/hooks.py`, `spawn(SCRIPT,
   [], …)`). `process.env.WF_WORKTREE_ROOT` set inside the Pi process therefore reaches every later
   hook run, for the orchestrator and for its children.

Design (user ruling 2026-09-25): the Model B Pi package gains enter/exit tools that use (1) and (3).

## Scope

### §S1 — The worktree tools
`pi-package/extensions/worktree.ts`, listed in `pi-package/package.json` `pi.extensions`, registers
two LLM-callable tools:

- **`modelb_worktree_enter`** `{ path: string }` — resolves `path` against the session cwd, then
  refuses (tool error, nothing changed) unless the resolved directory exists, sits under a
  `/.worktrees/<cr>` segment, and appears in `git worktree list --porcelain` of the repository
  containing it. On success it sets `process.env.WF_WORKTREE_ROOT` to the resolved path and
  registers a workspace provider whose `prepare` returns `{cwd: <root>, dispose: () => undefined}`.
  A second enter while one is active replaces the first (unregister, then register). If the
  pi-subagents service is absent, it still sets `WF_WORKTREE_ROOT`, and its result says dispatched
  agents will not be relocated.
- **`modelb_worktree_exit`** `{}` — unregisters the provider and deletes `WF_WORKTREE_ROOT`;
  idempotent.
- `prepare` **throws** a clear error when the entered root no longer exists (e.g. after
  `worktree-flow finish`), so no child silently runs in the main tree.
- Each tool's result text names the active root (or none).

Generated sub-agent definitions do not list these tools; only the orchestrator uses them.

### §S2 — The workflow text
- `scripts/worktree-flow.py start`: the line `→ enter it: cd <wt_dir>` becomes an instruction to
  enter the worktree with the Model B worktree tool (`modelb_worktree_enter` with `<wt_dir>`).
  `finish` and `abort` print a reminder to exit it.
- `skills-src/model-b/references/orchestration-common.md` (§Worktree isolation),
  `orchestration-track.md` ("Root your SESSION in the worktree", the `finish` exception) and
  `sub-agent-procedure.md` (the worktree bullets, "This is HARD-ENFORCED"): say exactly what holds.
  After `start`, the orchestrator enters the worktree. Every agent it dispatches then runs with
  the worktree as its working directory, and the hook blocks writes outside it, for the orchestrator
  and for the agents. The per-dispatch `cd` + `git rev-parse --show-toplevel` check stays as the
  check an agent makes before its first write. Exit after `finish` or `abort`.
- `contracts/worktree-layout.md` records the tools as a consumer of the layout and restates
  "Permission scope" in these terms.
- Naming the tool: `modelb_worktree_enter` is a Model B surface shipped by Model B's own package,
  not a harness tool; DN §D18 bars naming harness tools. The skills name it once where the invocation
  is load-bearing, as `skills-src/README.md` already allows.

### §S3 — Capability contract
The `watcher` capability (`modelb_axi/requirements.py`, provider `@anthill-tec/modelb-pi`) now also
provides worktree isolation. Its `asset_families` name the worktree isolation, and its `tools` list
the two new tools, so an absent package reports what is lost.

## Acceptance criteria

- [ ] `pi-package/extensions/worktree.ts` registers `modelb_worktree_enter` and
      `modelb_worktree_exit` with the §S1 parameters, and `package.json` lists the extension.
- [ ] Entering a registered `.worktrees/<cr>` worktree sets `process.env.WF_WORKTREE_ROOT` and
      registers exactly one workspace provider through the service found under
      `Symbol.for("@gotgenes/pi-subagents:service")`. Its `prepare` returns that root, and it throws
      once the root is deleted.
- [ ] Entering refuses a path that does not exist, is not under `/.worktrees/<cr>`, or is not a
      registered git worktree. A refusal changes neither the environment nor the provider.
- [ ] A second enter replaces the provider (the first is unregistered). Exit unregisters it and
      deletes the variable, and a repeated exit is a no-op. With no service present, enter sets the
      variable and says children will not be relocated.
- [ ] Integration: with the variable set by the tool, the real `block-write-outside-worktree`
      script blocks a write outside the entered worktree and allows one inside it. This runs against
      a real `/tmp` git worktree, with the payload the compiled Pi hook extension sends.
- [ ] The extension's service key equals the key in the installed pi-subagents
      (`src/service/service.ts`). The check skips, naming the path, when pi-subagents is not
      installed.
- [ ] `worktree-flow.py start` names `modelb_worktree_enter` with the worktree path; `finish` and
      `abort` remind the orchestrator to exit.
- [ ] No shipped skill, template or contract instructs making the worktree "the session's working
      directory", or says a sub-agent is dispatched "with the worktree as its working directory",
      except as the effect of entering it with the tool. `sub-agent-procedure.md` says what enforces
      the boundary: the hook, active while the orchestrator has entered the worktree.
- [ ] The `watcher` capability names worktree isolation and lists both tools.
- [ ] The generated agents list neither tool (`python3 generator/build.py --check` stays clean).
- [ ] The tests load the extension the way the existing pi-package tests do (jiti, with a fake Pi
      API and a fake service), and they skip when `pi` is not on `PATH`, as those tests do.
- [ ] `AGENTS.md`'s module count and both suite baselines (real `HOME`, empty `HOME`) are
      re-measured and recorded.

## Non-goals

- No change to the `.worktrees/<cr>` layout.
- No relocation of the orchestrator's own session cwd. Its relative paths still resolve against the
  main tree, and the hook blocks its writes outside the worktree.
- No provider for sessions that do not enter a worktree. The default, the parent's cwd, stands.
- Publishing the package stays a release step.
