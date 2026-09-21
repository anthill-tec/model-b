---
name: bootstrap
description: Start-of-run bootstrap for a Model-B orchestrator session (Mainline or Track). Sets up and launches the Sandesh notify watcher, recovers any incomplete todo/task list left over from the previous run, and loads the last-held implementation-queue status. A Mainline session reads the implementation queue from Crucible and reports to the USER; a Track session just enables its notifier, reloads any in-flight cycle, informs MAINLINE of its status, and waits for instructions. The orchestrator ROLE is passed as the argument — `/bootstrap mainline` (the single per-project coordinator) or `/bootstrap track <N>` (a numbered worker, N = 1, 2, 3, …). Use when the user types "/bootstrap", or says "bootstrap", "new run starting", "start of day", or "boot the orchestrator".
---

# Bootstrap — start-of-run orchestrator setup

A new run (or a new day) is starting. This skill brings ONE orchestrator session
back online: its Sandesh notifier, its carried-over work, and — role-dependent —
either the implementation-queue board (Mainline) or a wait-for-instructions hold (Track).

The **role is passed as the invocation verb** — `/bootstrap mainline` or
`/bootstrap track <N>` (Mainline is the singleton per project; tracks are numbered
1, 2, 3, …). See Step 0 for the full grammar and the omitted-argument fallbacks.

**Role asymmetry is the point of this skill:**
- **Mainline** loads the queue, **checks which Tracks are up and running**, and reports
  status to the **USER**.
- **Track** enables its notifier, **checks that Mainline is up**, reports status to
  **MAINLINE**, never the user.

Each role probes the other's liveness via the same `sandesh_addressbook` (`listening:true`
= up + wake-reachable) — Mainline scans the tracks, a track scans Mainline.

**Read the memory that binds your role before acting.** Once Step 0 fixes your role,
**Step 0.5 loads the rule set you must execute by** (`orchestration-common.md` + your
role file + the project `ORCHESTRATOR-<Project>` note + the project memory index +
`sandesh.md`). This is mandatory, not optional reading — every later step is performed
the way YOUR role is supposed to perform it. The role rules are authoritative: if any
later step conflicts with them, the role rule wins.

---

## Step 0 — Resolve identity (role + project) BEFORE anything else

1. **Project** — derive `<Project>` from the repo's CLAUDE.md / `ORCHESTRATOR-<Project>`
   note. **Casing is load-bearing for Sandesh** (NAI = `Nai`, capital). Every Sandesh
   MCP call passes `project_id="<Project>"`; the `sandesh notify` CLI passes
   `--project <Project>`.
2. **Role — read it from the invocation argument FIRST (the "verb").** The role is
   passed as the `/bootstrap` argument (`$ARGUMENTS`); this is the AUTHORITATIVE source.
   When present, use it directly — do NOT second-guess it with the heuristics below.

   | Argument (`$ARGUMENTS`) | Resolved role | Notes |
   |---|---|---|
   | `mainline` (or `main`) | **Mainline** | The SINGLE coordinator per project — there is exactly one, and it takes NO number. |
   | `track <N>` (e.g. `track 2`) | **Track N** | A worker orchestrator, identified by the numeric index `N` ∈ {1, 2, 3, …}. The number is REQUIRED. |
   | bare integer `<N>` (e.g. `2`) | **Track N** | Shorthand for `track <N>`. |

   The number distinguishes tracks (`Track 1`, `Track 2`, …); Mainline is the singleton
   and never numbered. The resolved role fixes your Sandesh address in step 3 below
   (`Mainline - <Project>` or `Track <N> - <Project>`).

   Only if the argument is **omitted/empty**, fall back — in this order — to:
   1. Carried session context (a resumed/compacted session almost always states its
      role — e.g. "Mainline coordinator", "Track 2").
   2. Working-tree heuristic: `git rev-parse --show-toplevel` ending in
      `/.claude/worktrees/<cr>` ⟹ a Track currently inside a worktree.
   3. If still genuinely ambiguous, **ask the user** (Mainline vs Track N) — one
      question — before proceeding. Never assume a role.

   A **malformed verb** (e.g. `track` with no number, or an unrecognised word) is NOT a
   guess point — ask the user to restate it as `mainline` or `track <N>`.
3. **Addresses / ids** from the resolved role:
   - Sandesh address: `Mainline - <Project>` or `Track <N> - <Project>`.
   - Crucible own-run id (from `ORCHESTRATOR-<Project>` §Identity; NAI):
     Mainline `vidushi`, Track `vidushi-t<N>`. (Never used for sub-agents — those are
     CR-scoped.)

---

## Step 0.5 — Read your role's rules from memory, understand your role (BOTH roles)

Resolving identity (Step 0) is not enough — **before you execute anything, load and read
the memory that binds your resolved role**, and confirm you understand both what that role
may and may not do **and how it fits into the project team**. Model-B is a TEAM: Mainline
is the single coordinator and sole user-facing channel that schedules work and merges;
Tracks are workers that execute assigned CRs and report only to Mainline; Sandesh is the
team channel between them. Understand your place in that structure so that every later step
(notifier, recovery, queue-load vs hold, reporting target, dispatch discipline) — and every
task you take on afterward — is carried out according to your role in the team. This is
mandatory reading, not a skim.

Per the role mode-map, read — in this order:
1. **`~/.claude/skills/model-b/references/orchestration-common.md`** — universal orchestrator rules (EVERY role).
2. **Your role file:** Mainline → `~/.claude/skills/model-b/references/orchestration-mainline.md` ·
   Track → `~/.claude/skills/model-b/references/orchestration-track.md`. (A Solo orchestrator follows Mainline.)
3. **The project `ORCHESTRATOR-<Project>` note** — project-specific deltas that override the
   generic tiers (NAI: `~/.claude/projects/-home-antonyj-Documents-data-projects-nai/memory/ORCHESTRATOR-NAI.md`).
4. **The project memory index `MEMORY.md`** — standing feedback + un-CR'd surfaces; open the
   linked topic files relevant to what you are about to do
   (NAI: `~/.claude/projects/-home-antonyj-Documents-data-projects-nai/memory/MEMORY.md`).
5. **`~/.claude/skills/model-b/references/sandesh.md`** — the cross-session channel mechanics you rely on in Step 1+.

Do NOT proceed to Step 1 until you have read the common file **and** your role file **and**
the project `ORCHESTRATOR-<Project>` note. If a later action would conflict with a role rule,
the **role rule wins** — re-read rather than guess. (Sub-agents are out of scope here; their
procedure lives in `~/.claude/skills/model-b/references/sub-agent-procedure.md`, loaded at dispatch, not at bootstrap.)

---

## Step 1 — Bring up the notifier (BOTH roles) — CHECK before setup/register

Setup and registration are **persistent** — do NOT re-run them blindly each run. The
only thing that reliably dies between runs is the watcher. So **check state first** and
do the minimum:

1. **Check** `sandesh_addressbook(project_id="<Project>")`:
   - Project resolves AND your address is present with `active:true` → already set up and
     registered. **SKIP `sandesh_setup` + `sandesh_register`**; go straight to the watcher.
   - Project unknown / "not set up" error → `sandesh_setup(project_id="<Project>")`, then
     re-check.
   - Your address absent / `active:false` → `sandesh_register(addr="<your address>")`.

   (Both calls are idempotent, but the point is to avoid needless churn — only call them
   when the check shows they're missing.)
2. **Launch the watcher ONLY if not already `listening:true`.** If the addressbook already
   shows your address `listening:true`, a live watcher exists — do NOT spawn a duplicate.
   Otherwise launch it in the BACKGROUND (Bash `run_in_background`), PLAIN — no
   `while`/retry wrapper, exactly ONE per address:
   ```
   sandesh notify --to "<your address>" --project <Project>
   ```
   It blocks until To-addressed mail arrives, then exits; on that exit you `sandesh_fetch`
   AND relaunch in the same turn (the PRIME DIRECTIVE — never leave the watcher dead).
3. **Re-confirm** `sandesh_addressbook` shows your address `listening:true`. A bare
   `sandesh notify` without `--project` silently never listens — if `listening:false`,
   fix the command and relaunch.

> Crucible "online" heartbeat is optional here and covered by the `crucible`
> skill; orchestrators register per-gate, not necessarily at bootstrap.

---

## Step 2 — Recover incomplete work from the last run (BOTH roles)

1. `TaskList` — surface any tasks left `pending` / `in_progress` from the previous run.
   These ARE your carried todo list (the resume spine), not a fresh board.
2. If the task panel reads blank after resume/compact, do one `TaskUpdate` write to
   repaint it (known resume-bug; see `reference-task-panel-resume-bug`).
3. If there is no task list, that simply means no mid-cycle work was carried — note it
   and continue. Do NOT invent tasks.

The difference between roles is **who you report this status to** (Step 3), not whether
you recover it — both roles recover.

---

## Step 3A — MAINLINE: load the queue, report to the USER

1. **Load the last-held implementation-queue status** from the two boards that own it
   (never raw `sqlite3`, never the README):
   - `~/.agents/scripts/worktree-flow.py status` — the git-derived board: per-CR
     worktrees (ahead/behind, latest committed phase) + the merge lock.
   - `python3 ~/.crucible/clients/python-crucible.py next [--track "Track N - <Project>"]`
     — readiness: `NEXT <cr>` / `HOLD <cr>` (`depends_on` not all COMPLETED) / `DRAINED`.
     Queue membership, release, wave, seq and dependencies live in Crucible (CR-MDB-028).
   (worktree-flow now emits a TOON envelope on stdout; the human board is on stderr.)
2. **Check which Tracks are up and running** — `sandesh_addressbook(project_id="<Project>")`
   is Mainline's track-liveness probe. Read the flags per track:
   - `listening:true` → notifier live: the track is **up and wake-reachable** (a directive
     will fire). This is "running".
   - `active:true, listening:false` → registered but its **watcher is down** — NOT reachable
     for a wake until it relaunches; treat as "up but not listening".
   - absent → never joined this project.
   How many tracks exist and which are online comes from the addressbook, never assumption.
   Carry this up/running-vs-down roster into the user report (step 4).
3. **Pending mail** — `sandesh_inbox(...)` for any Track requests waiting from before
   the break; drain + plan dispositions (but act only after reporting).
4. **Report to the USER** — a concise status, then WAIT for direction:
   - queue state: IN_PROGRESS CRs, what's READY (deps clear) vs BLOCKED/HELD;
   - the live Track roster (who's online);
   - any incomplete Mainline tasks reloaded in Step 2;
   - any pending Track requests in the inbox.
5. **Do NOT auto-dispatch, auto-schedule, or merge.** Mainline surfaces the board and
   waits for the user's go. Relaunch the Mainline inbox watcher after any fetch.

---

## Step 3B — TRACK: check for Mainline, enable notifier, inform MAINLINE, wait

1. The notifier is already up (Step 1). A Track does **not** read the queue board for
   scheduling and does **not** contact the user.
2. **Check that Mainline is up** — `sandesh_addressbook(project_id="<Project>")` and read
   the `Mainline - <Project>` row (the reciprocal of Mainline's track-liveness probe):
   - `listening:true` → Mainline is online and will **wake** on your report. Normal path.
   - `active:true, listening:false` → Mainline is registered but its watcher is down: your
     report still **sends** (sending needs no listener) but won't wake it — it will pick the
     message up on its next fetch/bootstrap. Note "Mainline appears offline" in the body.
   - absent → Mainline hasn't joined this project yet; still send your status (it queues)
     and HOLD.
   Mainline is your SOLE contact — never escalate to the user just because Mainline looks
   offline; send + hold regardless.
3. **Report status to MAINLINE** via `sandesh_send(... kind="request", to=["Mainline - <Project>"])`:
   - If Step 2 found an **incomplete in-flight cycle** (a CR mid RED/GREEN/VERIFY):
     reload it as the resume spine and tell Mainline — e.g.
     *"Track N online; resuming CR-XXX at <phase/step>, status <pass/fail counts>,
     awaiting confirmation to continue."*
   - If **no carried work** (idle): *"Track N online, idle, awaiting assignment."*
4. **Then HOLD** — idle on the Sandesh watcher, **zero LLM turns, never self-poll**.
   Mainline disposes and sends a `directive` that wakes you. Do not poll any board
   (`python-crucible.py next` included) in a loop; do not self-schedule.
5. A Track's SOLE contact is Mainline. Escalations, questions, status — all go to
   Mainline, never the user directly.

---

## Guardrails

- **Never** start CR work, dispatch sub-agents, or merge as part of bootstrap — this is
  setup + status only. Mainline waits for the user; a Track waits for Mainline.
- Watcher is launched PLAIN via `run_in_background`, exactly one per address; never a
  `while … sleep` retry wrapper.
- Never machine-wide process kills to "clean up" a stale watcher — `sandesh_addressbook`
  confirms liveness; a duplicate watcher exits benign on the lock.
- Mainline reports to the USER; a Track reports to MAINLINE. Do not cross these.
- If you are a Solo orchestrator (no tracks, no worktrees), follow the MAINLINE branch
  for queue + user reporting; the Sandesh/Track machinery is inert.
