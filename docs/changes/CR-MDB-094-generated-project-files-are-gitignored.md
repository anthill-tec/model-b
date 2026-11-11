# CR-MDB-094 — The files Model B generates into a project are gitignored

**Status:** PENDING — **SEED, not the finished spec** (filed 2026-10-30 from Sandesh's request #1507, by the
user's ruling). Gap analysis, the design record, the spec and its pre-review happen in order when this CR
starts.
**Type:** feature (scaffold, `agents`, worktree flow) — a design change
**Priority:** P1 — release 1.0.0, wave 2, after CR-MDB-079 (user 2026-10-30; board-authoritative: read
`queue`).
**Depends on:** nothing on the board.
**Labels:** scaffold, gitignore, worktrees, pi
**Design reference:** CR-MDB-030 §S6 (`.pi/` tracked so worktrees carry it — reversed here); DN §D28 (Model B's own repo too, 2026-11-11);
CR-MDB-091 (`.lean-ctx.toml`, which Model B commits in its own repo); PRD § Check-in policy;
DN-multi-harness-deploy-model (the `migrate` managed-block rule); `contracts/worktree-layout.md`.

## Context

Sandesh asked (#1507, 2026-10-30) that the local, per-project files `modelb-axi` renders be gitignored.
Today they show up as untracked files in a project that was not scaffolded by `init`, and
`worktree-flow.py status` reports `DIRTY (has WIP)` until someone ignores them by hand. Sandesh ignored
these by hand (develop `d0dd545`):

- `.pi/`: the rendered agents (`.pi/agents/*.md`) and the per-project permission policy
  (`.pi/extensions/pi-permission-system/config.json`);
- `.lean-ctx.toml`;
- `.env` (the registry `init` emits), which carries the session identity.

Model B's design does the opposite today: CR-MDB-030 §S6 stopped ignoring `.pi/` so that
`.pi/extensions/` (the compiled hook shims) and `.pi/agents/` are tracked, and every `git worktree add`
checks them out; the scaffold's `_render_gitignore` says so. Model B commits its own `.lean-ctx.toml`.

**The user ruled (2026-10-30): in a project that consumes Model B, ignore all of them, and redesign how
worktrees get them. Model B's own repo, which dogfoods the workflow, keeps committing its own.**

## Scope (seed)

1. **`init` and `agents` keep the project's `.gitignore` covering every file Model B renders into a
   project** — `.pi/` (agents, hook shims, the permission policy, `subagents.json`), `.lean-ctx.toml`,
   `.env`, and any other rendered file the gap analysis finds (the stack skills under `.agents/skills/`,
   the release workflow?). Shape, after DN-multi-harness-deploy-model's `migrate` rule: a marked managed
   block, created when the file is absent; one entry per path, never duplicated; the project's own lines
   never touched.
2. **An opt-out** for a project that deliberately tracks one of these files.
3. **Worktrees still get them.** Today `worktree-flow.py start` copies the gitignored `.env` into a new
   worktree (best effort); CR-MDB-052 item 13 adds `crucible.toml`. The redesign decides how a
   `.worktrees/<cr>` checkout gets the agents, the hook shims, the permission policy and
   `.lean-ctx.toml` — a copy at `start`, a link, or reading them from the main tree — and what keeps
   them fresh when `agents` re-renders.
4. **No exception for Model B's own repo** (user 2026-11-11, reversing the 2026-10-30 exception; DN §D28):
   `.pi/` and `.lean-ctx.toml` are machine-specific, so Model B's repository gitignores them like every
   project. **This CR moves the tests that depend on the tracked copies** (user 2026-11-11), so the suite
   passes on a checkout without them, rendering into a sandbox instead of reading the repository's copy:
   - **fail without the files:** `tests/test_axi_envelope_read_whole.py` (reads `.pi/agents/*.md` byte for
     byte), `tests/test_client_run_rule.py` (the exact set, byte-identical to `generator/agents/`),
     `tests/test_harness_neutral_skills.py` (a fresh render diffed against the repository's `.pi/agents`),
     `tests/test_pi_agent_definitions.py` (`.pi/agents/*.md` against the expected render),
     `tests/test_verify_spec_pre_review_mode.py` (reads `.pi/agents/python-verify-agent.md`), and
     `tests/test_lean_ctx_project_config.py` `ModelBOwnLeanCtxConfigTest` (asserts `.lean-ctx.toml` is tracked
     and equal to the render);
   - **pass vacuously without them** (they glob `.pi/agents` among their surfaces):
     `tests/test_orchestrator_references.py`, `tests/test_stack_reference_material.py`,
     `tests/test_pi_agent_definitions.py`, `tests/test_skill_frontmatter.py`, and the text gates of
     `tests/test_harness_neutral_skills.py` and `tests/test_raw_runner_guard.py`.
   Gap analysis measures the full set again. **After this CR closes, a chore** (user 2026-11-11) adds `.pi/`
   and `.lean-ctx.toml` to Model B's `.gitignore` and untracks them (`git rm -r --cached`, the files kept on
   disk), and `AGENTS.md`'s SoL-Pi config line drops its interim sentence.
5. **Every surface that states the old rule** moves with it: `_render_gitignore`'s comment, CR-MDB-030
   §S6's record (a DN amendment, not a spec edit), the install guide, the worktree-layout contract and the
   skills that describe the worktree flow.
6. **`.envrc`** stays tracked (it holds only `dotenv`).

## To measure at gap analysis

- Where Pi reads `.pi/extensions/`, `.pi/agents/` and the permission policy from for a sub-agent in a
  `.worktrees/<cr>` checkout (pi-subagents' worktree isolation, CR-MDB-039): the worktree's tree, or the
  session root's. If the session root's, ignoring `.pi/` may cost worktrees nothing.
- Every file `init`, `agents` and `release-workflow` write, and which of them a project should still
  commit (the release workflow under `.github/` must be committed to run).
- The tests that pin `_render_gitignore`, the committed-set check, and CR-MDB-030 §S6's tracked `.pi/`.
- Existing projects: what a re-run of `agents` does to a project that already tracks `.pi/` (Crucible,
  Model B) — `git rm --cached`, or leave it to the project.
- The re-score.
