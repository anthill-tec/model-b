# Orchestration — COMMON

Universal rules for ANY orchestrator, ANY project/stack. Verbose detail + failure-case archive lives separately (REFERENCE) — this is the crisp rule set.

**MODE-MAP — read what your role needs:**
- **Solo** (one orchestrator, no worktrees, no tracks) → COMMON + MAINLINE (you ARE the main orchestrator; the track-coordination rules in MAINLINE are inert without tracks, and you run the cycles yourself per COMMON's loop). The worktree / Sandesh / TRACK-file machinery does not apply.
- **Mainline** (coordinator) → COMMON + MAINLINE.
- **Track** (worker orchestrator) → COMMON + TRACK.
- **Dispatched sub-agents** (RED/GREEN/VERIFY/FIX) → AGENTS.md.

## Session lifecycle — bootstrap ↔ shutdown
- Every orchestrator session is BRACKETED by two skills: **`/bootstrap <role>`** at start (register + start the Sandesh notifier through the Model B watcher — or, without it, as a background process that notifies you when it exits — recover carried todos, load queue/hold per role) and **`/shutdown`** at end (finish the active step, drain todos + merge the active CR, leave no dangling/uncommitted work, ack, then kill the notifier LAST).
- **Asymmetry:** `/bootstrap` takes the role as its verb because it ESTABLISHES identity at start; **`/shutdown` takes no role arg** — a running session already knows its role, and a Sandesh shutdown directive is already addressed to one orchestrator. Only `/shutdown`'s optional `emergency` flag matters.
- `/shutdown` is **graceful by default**; an **`emergency`** flag (power-failure-class) switches to immediate fast-abort (close the active write, stash/preserve, best-effort ack). Fast-abort is permitted ONLY under the flag.
- **The notifier-kill at shutdown is the SINGLE override of the relaunch-on-exit prime directive** — everywhere else a stopped watcher is relaunched the same turn (never left dead), by the Model B watcher itself or by you on the fallback path — except after an error or a terminal exit on the Model B watcher, or a terminal exit (`3`/`4`/`5`: tombstoned, evicted, already live) on the fallback path, which is never relaunched; ONLY at a confirmed shutdown's final step is it killed and not relaunched. Keep it alive through the whole teardown (to receive acks / a late emergency-stop).
- Roles differ at shutdown: a **Track** acks **Mainline** that it is safe to stop; **Mainline** (shut down by the USER) dispatches to the tracks and tears down LAST — only after every active track has acked / shows down. Full procedure → the `shutdown` skill.

## Two-phase workflow
- **Design phase → `develop`.** Gap-analysis, spec/PRD/DN/queue edits. No feature branch.
- **Execution phase → feature branch.** RED+GREEN cycles, VERIFY, FIX, regression, merge.
- `VERIFY` is an EXECUTION-phase word ONLY — design-phase validation is **gap-analysis**; never call it "verify".
- **Design is BATCHED per wave** (PRD → CRs → queue up front); **gap-analysis is NOT batched** — re-run per-CR immediately before THAT CR (the tree evolved; design→implementation is a closed loop).

## Gap-analysis discipline (gap-analysis FIRST, before any branch/RED)
- **The orchestrator runs gap-analysis itself** (never delegate to a sub-agent), per-CR immediately before THAT CR's branch/RED.
- **The dimensions are the single authority in the `gap-analysis` skill** — read it for the full check (spec↔PRD↔code + spec-vs-existing-mechanisms + design-lineage + public-symbol-removal). Do NOT re-list them here.
- Verdict: READY / SPEC_UPDATE_NEEDED / PREREQUISITE_NEEDED / BLOCKED.
- **Gap-analysis output ≠ spec.** Findings/rationale go to the user + commit message; the spec just BECOMES the corrected contract. No DRIFT-N tags, no "gap-analysis resolutions", no file:line breadcrumbs in the spec.

## Cycle discipline
- **Cycle = ONE todo = RED→GREEN together** (never split RED and GREEN into two todos).
- Todo list holds IMPLEMENTATION cycles + VERIFY + conditional FIX only — NOT design/admin work. Generate each todo when you reach it, not upfront.
- Setup ordering: cycle plan → create todos → THEN claim the lane / start the worktree.
- Intra-cycle: once approved, flow RED→GREEN→next without pausing between phases; pause only on drift or escalation.

## Never author code — always dispatch + diff-verify
- The orchestrator NEVER authors RED/GREEN/FIX edits — dispatch the stack's sub-agent regardless of how trivial. No size threshold.
- **Agents confabulate — diff-verify EVERY cycle against ground truth** (`git diff`, grep, the artifact), not the agent's narrative or green-claim.
- When diff-verify finds a defect, DISPATCH a fix-agent — do NOT self-edit.
- Agents self-commit despite "do not commit" — verify the COMMIT RANGE (`git diff <prev>..HEAD`), reset+recommit cleanly to collapse into orchestrator-controlled boundaries.
- A crashed agent that left a COMPLETE uncommitted diff is salvaged (assess gates + commit), not re-run.

## Integration / wire-the-call-path GATE (EVERY CR)
- Every feature must be WIRED into the call path and proven by an INTEGRATION test exercising the real caller→new-code→result seam — not unit-only, not E2E-only.
- Integration tests drive PRODUCTION wiring (real boot/entry point), never hand-wired struct-literal fixtures.
- Merge sign-off NAMES the integration test that proves the call path; unwired/unit-in-disguise → FIX_REQUIRED.

## Sessions
- One Pi session per orchestrator — Mainline and each Track — launched however the user likes: separate terminals, or panes of a multiplexer such as tmux (optional, a convenience for watching them side by side).
- Mainline follows the Tracks through Crucible (board, plans, cycles, runs) and Sandesh (requests, directives, replies), never through a shared process.

## Worktree isolation (basics)
- **`worktree-flow` owns what it derives from git** (worktrees, ahead/behind, phase, merge). **Crucible owns what used to live in the DB** (queue membership, release, wave, seq, dependencies, readiness) — CR-MDB-028.
- Readiness is `~/.crucible/clients/python-crucible.py next`'s answer (`NEXT` / `HOLD` / `DRAINED`) — never a local board, never a schedule md.
- Each parallel CR gets its own working folder via the worktree tool; the merge is a serialized critical section.
- Once your worktree exists, the MAIN tree is HANDS-OFF — all CR-coupled edits land in the worktree.
- **Enter the worktree right after `start`** with the Model B worktree tool `modelb_worktree_enter` and the path `start` prints. Every agent you dispatch for the CR then runs rooted in its worktree, and the `block-write-outside-worktree` hook blocks file-tool writes outside it — yours and the agents' (not writes a shell command makes). Your session cwd never changes: reads, `git -C` and test runs in the worktree are unaffected.
- **Exit after `finish` or `abort`** with `modelb_worktree_exit`. Both remove the worktree and run from the main tree, where the session already is; `status`/`sync` resolve the main tree from git and run from anywhere.
- The worktree's files stay readable from your session by path: `.worktrees/` is gitignored, so a gitignore-aware listing does not show it — read `.worktrees/<cr>/…` by explicit path.
- You own ONLY your CR — never run another CR's finish/merge or edit its tree.
- Name the CR id in every dispatch description (that routes the agent into the CR's worktree). The dispatch prompt still makes the agent `cd` + assert `git rev-parse --show-toplevel` == worktree before its first write — the agent's own first check; use absolute worktree paths; re-check the main tree is clean after each agent returns.
- Throwaway/scratch/probe files → `/tmp` via `mktemp` (absolute), NEVER the repo or any worktree.
- No detached poll-loops (`until … sleep … done`) — the test/build wrapper returns synchronously; wait on that.
- Keep `Depends on:` metadata CURRENT on every CR (parallel ordering derives from it; a stale dep is a hazard). Allocate the next-free CR id against CURRENT integration HEAD, never a stale tree/worktree. Resync a stale branch by merging `develop` INTO the feature branch (not a long re-conflicting rebase).

## Workflow gates
- Never skip RED — even for chores/lint (RED = a real failing test; a compile failure IS a RED).
- Never merge without explicit approval — present VERIFY findings and WAIT.
- Answer-then-wait on questions — never implement in response to a question.
- Always use the proper git-flow / worktree commands; never hand-roll the merge dance.
- **Serialize heavy gates across parallel tracks** — never run heavy regression / pre-merge gates concurrently (compile + resource starvation env-KILLS them). SELF-SERVICE, split into two roles: (1) the track's PRE-FLIGHT is a WAIT-FOR-FREE + resource-headroom check (RAM/CPU/disk) via the gate-coordination tool — if a gate is already running it WAITS (poll ~5s) and ESCALATES to the coordinator after ~10min; it does NOT create the lock. (2) the GATE-RUNNER tool itself OWNS the lock FILE lifecycle — CREATE it on start with its own REAL run pid, DELETE on finish + on a catchable kill (signal handler), REFUSE to start if a lock is already present (no double-runs in the same CR/track), and reclaim a STALE lock whose holder pid is dead. The coordinator (Mainline) is the RARE stale-lock ARBITER — verify the holder's REAL run pid (🚨 NEVER conclude a run is dead from a proxy signal; ask the holder before telling it to abandon) + interrogate the holder, then force-release only a genuinely forgotten lock. Per-cycle RED/GREEN runs are exempt (light, concurrent). The tool is **`~/.agents/scripts/gate-lock.sh`** (cross-project contract: `contracts/gate-lock.md`) — verbs `wait-free` (the PRE-FLIGHT above) · `wait-acquire` · `acquire` · `release` · `force-release` (Mainline-only, a genuinely stale lock) · `status` · `check`; exit codes 0 = acquired / free → run the gate, 1 = held by another track, 2 = resources loaded, 5 = timed out → ESCALATE (never force-release yourself).

## Commit + doc conventions
- CR/PRD/DN: CR = implementation contract (Context, Steps §S1.., Acceptance Criteria); PRD/DN = design rationale. No design narrative or process meta in a CR.
- ACs are precise testable gates: exact field names/types/numbers, enum variants, signatures.
- Conventional commits (`type(scope): desc`); no AI attribution.
- CR-coupled doc edits ride the feature branch; standalone docs commit to `develop`.

## Close-out
- Close-out = transition the CR's TRACKING STATE to COMPLETED via the stack's finish/close tool (the ChangeSet-DB / queue row) — that IS the close-out. Where tracking is DB-based, it is the ONLY step: do NOT hand-edit a deprecated spec `Status:` field (scripts read the DB, not the spec), and do NOT touch the README — README updates are RELEASE-branch only (version + CI badges) per the project's rules, NEVER a per-CR delivery entry in develop, and NEVER a track's job (parallel tracks editing the shared README collide). Never a `## Close-out` section in the CR spec. Run the stack's `check-cr-close` gate.

## Memory
- **GC principle:** memory holds ONLY what the repo doesn't yet track. The moment a note becomes a repo artifact (CR / queue row / PRD / DN / README) or is abandoned, DELETE it (keep ≤ a one-line pointer). Duplicated notes rot + burn context every recall.
- **No unilateral writes:** do not write/update shared memory or rules files unilaterally — raise the learning to the coordinator (Mainline), who records it centrally. (Solo: record only with user awareness.)
