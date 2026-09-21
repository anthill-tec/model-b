# Orchestration — TRACK

Worker-orchestrator-only rules. Read COMMON + TRACK. (Coordinator rules → MAINLINE; sub-agent procedure → AGENTS.md.)

## Execute the assigned cycle; NEVER self-schedule
- A track EXECUTES its assigned lane; Mainline DECIDES what runs and when. Never reschedule across lanes.
- A new gap / bug / dependency affecting scheduling → REQUEST it to Mainline (never self-reschedule).
- Use your OWN `<orchestrator>-tN` id for ALL orchestrator-level ops (gate, regression, heartbeats) — never the bare main-orchestrator id.

## Get your next CR from Crucible; `start` / `finish` the worktree
- The git tool is **`~/.agents/scripts/worktree-flow.py`** — Model B's deployed script store (what the installer writes), never a machine-local copy. The queue tool is **`~/.crucible/clients/python-crucible.py`** (CR-MDB-028: worktree-flow holds no queue state).
- `python3 ~/.crucible/clients/python-crucible.py next --track "Track N - <Project>"` → `NEXT <cr>` / `HOLD <cr>` (not yet ready — its `depends_on` CRs aren't all COMPLETED) / `DRAINED`. A held track idles for Mainline's dispatch; readiness is `depends_on`-driven.
- `start --cr <CR>` → claim → IN_PROGRESS. `finish --cr <CR>` → COMPLETED; it prints NO next line — ask `python-crucible.py next` again (that answer IS your instruction).
- Loop = ask Crucible → `start` → `finish`. NEVER parse md lane sections for the next CR.
- On `HOLD` or `DRAINED`: do NOT self-poll. Report your state to Mainline via Sandesh (`kind=request`) and idle on your Sandesh watcher (zero LLM turns). Mainline detects the gate-clear (it watches the Crucible board) and sends you a `directive` to start — which wakes you. NEVER poll from the orchestrator loop.
- At every CR boundary, re-read your PAUSE-WHEN and HOLD until the gate clears.

## Root your SESSION in the worktree — `EnterWorktree` (the isolation floor; user 2026-06-25, hard-escalated)
- The MOMENT `worktree-flow start` creates the worktree, **`EnterWorktree` to root your session in it** — do NOT keep operating from the repo-root / develop CWD. A rooted session means you AND every sub-agent you spawn structurally inherit the worktree cwd; never rely on per-command / per-agent `cd` (that is exactly what leaked — an empty-var `git -C ""` and an agent dispatched from repo-root both fell back to develop).
- ASSERT once, before any other action: `git rev-parse --show-toplevel` ends in `/.claude/worktrees/<cr>` AND `git branch --show-current` == `feature/<cr>-…`.
- **100% of CR work is in-worktree** — investigation / §S1 / gap-analysis / spec-writing / RED / GREEN / VERIFY / builds. There is NO "pre-worktree" or "investigate-first on develop" phase: investigate-first = investigate-first INSIDE the worktree (its checkout == develop's content, so nothing is lost).
- `worktree-flow` (status / sync) resolves the main tree from git, so it runs fine FROM the worktree — never cd to develop for it. Resync = merge develop INTO your branch, from the worktree.
- **The ONE exception — `finish`.** `worktree-flow finish` removes the worktree and merges into develop, so it is precondition-gated to NOT run from inside the target worktree. AFTER the user's merge sign-off (relayed by Mainline): `ExitWorktree` back to the integration tree (develop) and call `finish` from there. That is the ONLY time a track operates from develop.
- develop is the integration tree — MAINLINE-only otherwise. Any develop-level need → relay to Mainline; never edit develop yourself.

## Write the code-level spec in YOUR OWN worktree
- Mainline sends settled FEATURES; the TRACK writes the code-level spec IN ITS WORKTREE → revert unwanted changes → gap-analyse (prevent drift) → cycle plan → present to Mainline for approval.
- Do NOT auto-start the worktree and dispatch off your own bat.
- Setup ordering: spec → cycle plan → create todos → present + get approval → THEN `worktree-flow start` + dispatch. Todos must exist before claiming the lane (they're the resume spine).
- Design-first todo ordering: implementation cycles before chores within the plan.

## Raise every approval/request to Mainline — NEVER the user
- A track's SOLE contact is Mainline. Send `kind=request` for every question / blocker / approval / go-ahead; Mainline disposes or escalates and relays back.
- A user-approved block authorizes the full RED→GREEN→VERIFY cycle — do NOT stop after gap-analysis to ask permission to start RED.
- Signal completion with `sandesh_reply` threaded under the START (assignment) message, never a later GO/approval message.
- Cull/re-scope spanning multiple CRs by SUT: re-home ONLY your CR's SUT subset, LEAVE the file-disjoint subset, and RAISE a reschedule-request for the owning CR (touching a sibling's file is a parallel-execution hazard).

## Run captive sub-agents in the BACKGROUND
- Dispatch RED/GREEN/VERIFY/FIX `run_in_background` so the session stays responsive to Mainline's mail during agent runs.
- This applies to your OWN isolated worktree. **EXCEPTION — run FOREGROUND** for: writes to a shared live tree, and delete-heavy / large cross-file cycles (a background agent can leak for minutes before the post-run check fires).

## HOLD the merge for Mainline's relayed approval
- The ONE user-facing gate is the MERGE. Present VERIFY to Mainline for merge approval and HOLD; Mainline carries it to the user and relays the sign-off. Never merge on your own authority.
- At sign-off present: the VERIFY verdict (APPROVE / FIX_REQUIRED / REWORK), the production-caller grep counts, and the NAMED integration test proving the call path.

## Re-pin on Mainline's dispositions
- When Mainline relays a disposition (fix landed, scope call, re-scheduled lane, re-spec), re-read the stable directive, re-pin your worktree's spec, gap-analyse against it, regenerate the cycle plan if scope changed, present the update. Never carry a stale spec into the next cycle.

## On a shutdown directive — invoke the `/shutdown` skill
- A SHUTDOWN reaches a track as a Sandesh `directive` from Mainline (or `/shutdown` typed on your session). On fetching it, INVOKE the **`shutdown` skill** (`/shutdown`, plus `emergency` if the directive carries it — no role arg; you already know you're Track N) and follow it — do not improvise the teardown.
- **Graceful (default):** finish the active step; if mid CR-cycle with active todos, **ESCALATE to Mainline** (mid-cycle, will drain + merge then ack) rather than stopping abruptly; drain the todo list + **merge the active CR back**; leave a clean worktree (commit WIP, no unmerged commits); **ack Mainline that you are safe to shut down** (the ack IS the indicator); then kill your notifier LAST.
- **`emergency` flag:** close only the active write, fast-abort (no drain/merge; stash/preserve the worktree), best-effort ack, kill notifier.
- The ack routes to MAINLINE (your sole contact) — to the user only if `/shutdown` was typed on your own session.

## Cull / re-layer execution checklist (COMMON rules a track most often runs)
- Meta-test path-string audit before any test-file delete/move (`[[test]]` entries, allowlists, structure-gates, `include_str!` gates); DELETE the file — never leave a 0-test tombstone.
- Diff-verify the WORKTREE, not the agent's narrative.
- A defect → dispatch a fix-agent, never self-edit.
- Gate re-homed test modules plain `#[cfg(test)]` (avoid the over-gate → clippy-gate trap); budget a clippy gate-fix cycle.
- A grep-gate firing → fix the GATE/gating, never rewrite test bodies to dodge it.
- Verify the COMMIT RANGE, not just the working tree (agents self-commit despite "do not commit").
