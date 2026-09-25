# CR-MDB-039 — Worktree isolation on Pi: a boundary that holds without a movable session directory

**Status:** PENDING (filed 2026-09-24 from CR-MDB-031 C4 VERIFY F3)
**Type:** fix
**Priority:** P1 — release 1.0.0, wave 2 (Crucible board); the workflow's write boundary is its
isolation floor
**Depends on:** CR-MDB-031 (the `.worktrees/<cr>` layout, `contracts/worktree-layout.md`, the
capability wording this CR corrects)
**Labels:** worktree, hooks, skills, pi, isolation
**Design reference:** DN §D16 (dispatch), §D18 (capability words), `contracts/worktree-layout.md`,
CR-MDB-031 §S0.1/§S0.6

## Context

CR-MDB-031 replaced `EnterWorktree`/`ExitWorktree` with capability words: "make the worktree your
session's working directory and dispatch every sub-agent with the worktree as its working directory".
Its VERIFY measured that on Pi (0.87.1, `@gotgenes/pi-subagents`) neither half is actionable:

- A Pi session's working directory is fixed at launch; the `bash` tool runs every command in the
  session cwd (`pi-coding-agent/dist/core/tools/bash.js:160`), so a `cd` does not persist.
- The installed dispatch tool has no working-directory parameter; a child runs in the parent's cwd
  (`agent-tool.ts:184-225`, `create-subagent-session.ts:208`).
- `block-write-outside-worktree` derives the worktree from the session cwd or from
  `$WF_WORKTREE_ROOT` (`:12`, `:131`). A session launched in the main tree, with no
  `WF_WORKTREE_ROOT` in its environment, gets a no-op hook.

So today the boundary is prompt discipline only: each dispatch prompt tells the agent to `cd` into the
worktree per command and check `git rev-parse --show-toplevel` (orchestration-common:56). The places
that promise more (VERIFY F3 table): orchestration-common:53, orchestration-track:19/23,
sub-agent-procedure:6/10 ("HARD-ENFORCED"), java-/rust-orchestration "leave the worktree", and
`contracts/worktree-layout.md` "Permission scope". The gap predates CR-MDB-031 — `EnterWorktree`
never existed on Pi.

## §S0 — Gap-analysis questions

- **Mechanism.** Candidates, to be measured on the installed Pi before choosing:
  (a) the Track's Pi session is launched from inside the worktree (`cd .worktrees/<cr> && pi`), so the
  session cwd, every sub-agent's cwd and the hook all agree; (b) `WF_WORKTREE_ROOT` is exported into
  the environment the session (and its children) are launched with; (c) a dispatch-level mechanism if
  pi-subagents gains or already has one (measure; do not assume); (d) the per-command `cd` + toplevel
  check as the documented floor, with the boundary claim reduced to what it is.
- **Sub-agent inheritance.** Whether a pi-subagents child inherits the parent's environment (for
  `WF_WORKTREE_ROOT`) and trust (for the extension) — measured with a real dispatch.
- **Solo vs Track.** A solo orchestrator in the main tree dispatching into a worktree is the common
  case here; the chosen mechanism must cover it or say it does not.

## Scope (to be fixed at gap analysis)

- Rewrite the F3 sites so every sentence is actionable on Pi and the boundary claim states exactly
  what enforces it (hook, allowlist, or prompt discipline).
- Wire the chosen mechanism (installer/scaffold/`worktree-flow.py` output, skills) and record it in
  `contracts/worktree-layout.md`.

## Acceptance criteria (draft)

- [ ] A measured, recorded answer to each §S0 question (a real Pi session and a real dispatch).
- [ ] With the chosen mechanism, a write outside the worktree by a dispatched sub-agent is blocked by
      the hook — proven by an end-to-end test against the installed Pi, or the skills state plainly
      that the boundary is prompt discipline and no text claims enforcement.
- [ ] No skill, template or contract instructs an action Pi cannot perform (a grep gate over the
      F3 phrases: "working directory" instructions, "root", "leave the worktree", "HARD-ENFORCED").
- [ ] Suite baselines re-measured and recorded in `AGENTS.md`.

## Non-goals

- No change to the `.worktrees/<cr>` layout itself (CR-MDB-031).
- No per-harness skill rendering (DN §D18 option C) unless §S0 shows capability words cannot be made
  actionable.
