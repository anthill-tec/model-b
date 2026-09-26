---
name: bootstrap
description: Start-of-run bootstrap for a Model-B orchestrator session (Mainline or Track). Sets up and launches the Sandesh notify watcher, reloads the in-flight work from the Crucible board (the plan, its active cycle, `next`), and loads the last-held implementation-queue status. A Mainline session reads the implementation queue from Crucible and reports to the USER; a Track session just enables its notifier, reloads any in-flight cycle, informs MAINLINE of its status, and waits for instructions. The orchestrator ROLE is passed as the argument — `/bootstrap mainline` (the single per-project coordinator) or `/bootstrap track <N>` (a numbered worker, N = 1, 2, 3, …). Use when the user types "/bootstrap", or says "bootstrap", "new run starting", "start of day", or "boot the orchestrator".
---

# Bootstrap — start-of-run orchestrator setup

A new run (or a new day) is starting. This skill brings ONE orchestrator session
back online: its Sandesh notifier, its in-flight work on the board, and — role-dependent —
either the implementation-queue board (Mainline) or a wait-for-instructions hold (Track).

The **role is passed as the invocation verb** — `/bootstrap mainline` or
`/bootstrap track <N>` (Mainline is the singleton per project; tracks are numbered
1, 2, 3, …). See Step 0 for the full grammar and the omitted-argument fallbacks.

**Role asymmetry is the point of this skill:**
- **Mainline** loads the queue, **checks which Tracks are up and running**, and reports
  status to the **USER**.
- **Track** enables its notifier, **checks that Mainline is up**, reports status to
  **MAINLINE**, never the user.

Each role probes the other's liveness via the same `sandesh addressbook --project <Project>` (`listening:true`
= up + wake-reachable) — Mainline scans the tracks, a track scans Mainline.

**Read the rules that bind your role before acting.** Once Step 0 fixes your role,
**Step 0.5 loads the rule set you must execute by** (the `model-b` references, then the
project's conventions and identity, then its memory index). This is mandatory, not optional
reading — every later step is performed the way YOUR role is supposed to perform it. The
role rules are authoritative: if any later step conflicts with them, the role rule wins.

---

## Step 0 — Resolve the role BEFORE anything else

1. **Role — read it from the invocation argument FIRST (the "verb").** The role is
   passed as the `/bootstrap` argument (`$ARGUMENTS`); this is the AUTHORITATIVE source.
   When present, use it directly — do NOT second-guess it with the fallbacks below.

   | Argument (`$ARGUMENTS`) | Resolved role | Notes |
   |---|---|---|
   | `mainline` (or `main`) | **Mainline** | The SINGLE coordinator per project — there is exactly one, and it takes NO number. |
   | `track <N>` (e.g. `track 2`) | **Track N** | A worker orchestrator, identified by the numeric index `N` ∈ {1, 2, 3, …}. The number is REQUIRED. |
   | bare integer `<N>` (e.g. `2`) | **Track N** | Shorthand for `track <N>`. |

   The number distinguishes tracks (`Track 1`, `Track 2`, …); Mainline is the singleton
   and never numbered. The resolved role fixes your Sandesh address (Step 0.5).

   Only if the argument is **omitted/empty**, fall back — in this order — to:
   1. Carried session context (a resumed/compacted session almost always states its
      role — e.g. "Mainline coordinator", "Track 2").
   2. The session's Sandesh address, when the carried context names one: a
      `Track <N> - <Project>` address ⟹ Track N; `Mainline - <Project>` ⟹ Mainline.
   3. If still genuinely ambiguous, **ask the user** (Mainline vs Track N) — one
      question — before proceeding. Never assume a role.

   A **malformed verb** (e.g. `track` with no number, or an unrecognised word) is NOT a
   guess point — ask the user to restate it as `mainline` or `track <N>`.

---

## Step 0.5 — Read your role's rules, understand your role (BOTH roles)

Resolving the role (Step 0) is not enough — **before you execute anything, load and read
the rules that bind your resolved role**, and confirm you understand both what that role
may and may not do **and how it fits into the project team**. Model-B is a TEAM: Mainline
is the single coordinator and sole user-facing channel that schedules work and merges;
Tracks are workers that execute assigned CRs and report only to Mainline; Sandesh is the
team channel between them. Understand your place in that structure so that every later step
(notifier, board reload, queue-load vs hold, reporting target, dispatch discipline) — and every
task you take on afterward — is carried out according to your role in the team. This is
mandatory reading, not a skim.

Read — in this order:
1. **The `model-b` references:**
   1. `~/.agents/skills/model-b/references/orchestration-common.md` — universal orchestrator rules (EVERY role).
   2. **Your role file:** Mainline → `~/.agents/skills/model-b/references/orchestration-mainline.md` ·
      Track → `~/.agents/skills/model-b/references/orchestration-track.md`. (A Solo orchestrator follows Mainline.)
   3. `~/.agents/skills/model-b/references/sandesh.md` — the cross-session channel mechanics you rely on in Step 1+.
2. **The project's `AGENTS.md`** (its conventions) **and `.env`** (its identity — the naming
   registry). Take the identity from the registry keys, by name:
   - **Sandesh project** — `SANDESH_PROJECT`. `<Project>` in this skill is the value of `SANDESH_PROJECT`, exactly as written (case- and space-sensitive).
     Your address is `Mainline - <Project>` or `Track <N> - <Project>`, and every `sandesh`
     CLI call (`addressbook`, `notify`, `fetch`, `send`, …) passes `--project <Project>`.
   - **Crucible own-run id** — Mainline (or Solo): `ORCHESTRATOR_LABEL`; Track N:
     `track<N>-<PROJECT_TOKEN>`. (Never used for sub-agents — those are CR-scoped.)
   - **Crucible client** — the project's stack client, resolved through Crucible's installed
     manifest `~/.crucible/crucible-clients.json`: its `clients` entry for a stack in
     `PROJECT_STACKS` (any one: every stack client carries the plan verbs `plans`, `next`) names
     the client file. The entry key is the stack name, except quarkus and java, which share the
     `mvn` entry (`mvn-crucible.py`). `<client>` below is that path.
   - **Crucible project key** — `CRUCIBLE_PROJECT_KEY`. An empty value means the project is not
     yet registered in Crucible: do the queue README's setup task, and never read the empty
     board `plans` then returns as idle.
3. **`docs/memory/INDEX.md`** — the project memory index — and the slices it lists (among
   them the orchestration template for a stack that has one,
   `docs/memory/<stack>-orchestration.md`); open
   the ones relevant to what you are about to do.

**Fallback** — a project with no `.env` registry, or a missing key: take the same value from
the project's `AGENTS.md`; a value found in neither, ask the user once. A missing
`docs/memory/INDEX.md` is noted and skipped. Nothing here is an error.

Do NOT proceed to Step 1 until you have read the common file **and** your role file **and**
the project's `AGENTS.md`. If a later action would conflict with a role rule, the **role
rule wins** — re-read rather than guess. (Sub-agents are out of scope here; their procedure
lives in `~/.agents/skills/model-b/references/sub-agent-procedure.md`, loaded at dispatch, not at bootstrap.)

---

## Step 1 — Bring up the notifier (BOTH roles) — CHECK before setup/register

Setup and registration are **persistent** — do NOT re-run them blindly each run. The
only thing that reliably dies between runs is the watcher. So **check state first** and
do the minimum:

1. **Check** `sandesh addressbook --project <Project>`:
   - Project resolves AND your address is present with `active:true` → already set up and
     registered. **SKIP `sandesh setup` + `sandesh register`**; go straight to the watcher.
   - Project unknown / "not set up" error → `sandesh setup --project <Project>`, then
     re-check.
   - Your address absent / `active:false` →
     `sandesh register --project <Project> --address "<your address>"`.

   (Both calls are idempotent, but the point is to avoid needless churn — only call them
   when the check shows they're missing.)
2. **Launch the watcher ONLY if not already `listening:true`.** If the addressbook already
   shows your address `listening:true`, a live watcher exists — do NOT spawn a duplicate.
   Otherwise start it with the **Model B watcher** — it supervises `sandesh notify`, stays
   running and relaunches itself; when it wakes you, you only fetch:
   `sandesh fetch --project <Project> --to '<your address>'`. If the Model B watcher is not
   installed, run the notifier as a background process that notifies you when it exits —
   PLAIN, no `while`/retry wrapper, exactly ONE per address, never inline (it blocks), and
   never as a job with a deadline shorter than the watcher's own timeout:
   ```
   sandesh notify --to "<your address>" --project <Project>
   ```
   It blocks until To-addressed mail arrives, then exits. Read the reason from its last log
   line and respond per the PRIME DIRECTIVE table in `sandesh.md`: exit `0` (mail) → fetch,
   then relaunch in the same turn; exit `3`/`4`/`5` (tombstoned / evicted / already live) →
   do not relaunch, report it. Never leave the watcher dead otherwise.
3. **Re-confirm** `sandesh addressbook --project <Project>` shows your address `listening:true`. A bare
   `sandesh notify` without `--project` silently never listens — if `listening:false`,
   fix the command and relaunch.

> Crucible "online" heartbeat is optional here and covered by the `crucible`
> skill; orchestrators register per-gate, not necessarily at bootstrap.

---

## Step 2 — Reload the in-flight work from the board (BOTH roles)

The Crucible board is the resume spine. Reload the in-flight work from the board, in order: `<client> plans` — each plan's active cycle, its id and label (none on a closed or pending plan) — then `<client> next` for what is ready. Never reload it from a todo list, and never invent work the board does not show.

A Track's active CR lives in its worktree, `.worktrees/<cr>`. A Track resuming an in-flight CR
re-enters that worktree before any write: `modelb_worktree_enter` with `.worktrees/<cr>` (the
entered worktree is per-session state, so a new session starts outside it). Check it with
`~/.agents/scripts/worktree-flow.py status` (latest committed phase, ahead/behind). If the
board shows no active cycle, no mid-cycle work was carried — note it and continue.

The difference between roles is **who you report this status to** (Step 3), not whether
you reload it — both roles reload.

---

## Step 3A — MAINLINE: load the queue, report to the USER

1. **Load the last-held implementation-queue status** from the two boards that own it
   (never raw `sqlite3`, never the README):
   - `~/.agents/scripts/worktree-flow.py status` — the git-derived board: per-CR
     worktrees (ahead/behind, latest committed phase) + the merge lock.
   - the Crucible client, `python3 <client> next [--track "Track <N> - <Project>"]`
     — readiness: `NEXT <cr>` / `HOLD <cr>` (`depends_on` not all COMPLETED) / `DRAINED`.
     Queue membership, release, wave, seq and dependencies live in Crucible (CR-MDB-028).
   (worktree-flow now emits a TOON envelope on stdout; the human board is on stderr.)
   - **Reconcile deferred/future-feature notes against the board** — cross-check each
     against the Crucible board (and the code when in doubt) and reconcile any drift.
2. **Check which Tracks are up and running** — `sandesh addressbook --project <Project>`
   is Mainline's track-liveness probe. Read the flags per track:
   - `listening:true` → notifier live: the track is **up and wake-reachable** (a directive
     will fire). This is "running".
   - `active:true, listening:false` → registered but its **watcher is down** — NOT reachable
     for a wake until it relaunches; treat as "up but not listening".
   - absent → never joined this project.
   How many tracks exist and which are online comes from the addressbook, never assumption.
   Carry this up/running-vs-down roster into the user report (step 4).
3. **Pending mail** — `sandesh inbox --project <Project> --to "Mainline - <Project>"` for any Track requests waiting from before
   the break; drain + plan dispositions (but act only after reporting).
4. **Report to the USER** — a concise status, then WAIT for direction:
   - queue state: IN_PROGRESS CRs, what's READY (deps clear) vs BLOCKED/HELD;
   - the live Track roster (who's online);
   - any in-flight Mainline cycle reloaded from the board in Step 2;
   - any pending Track requests in the inbox.
5. **Do NOT auto-dispatch, auto-schedule, or merge.** Mainline surfaces the board and
   waits for the user's go. Relaunch the Mainline inbox watcher after any fetch (fallback
   path only — the Model B watcher relaunches itself).

---

## Step 3B — TRACK: check for Mainline, enable notifier, inform MAINLINE, wait

1. The notifier is already up (Step 1). A Track does **not** read the queue board for
   scheduling and does **not** contact the user.
2. **Check that Mainline is up** — `sandesh addressbook --project <Project>` and read
   the `Mainline - <Project>` row (the reciprocal of Mainline's track-liveness probe):
   - `listening:true` → Mainline is online and will **wake** on your report. Normal path.
   - `active:true, listening:false` → Mainline is registered but its watcher is down: your
     report still **sends** (sending needs no listener) but won't wake it — it will pick the
     message up on its next fetch/bootstrap. Note "Mainline appears offline" in the body.
   - absent → Mainline hasn't joined this project yet; still send your status (it queues)
     and HOLD.
   Mainline is your SOLE contact — never escalate to the user just because Mainline looks
   offline; send + hold regardless.
3. **Report status to MAINLINE** via
   `sandesh send --project <Project> --from "<your address>" --to "Mainline - <Project>" --kind request --subject "…" --body "…"`:
   - If Step 2 found an **in-flight cycle** on the board (a CR's active cycle):
     re-enter its worktree (Step 2), resume it from the board and tell Mainline — e.g.
     *"Track N online; resuming CR-XXX, active cycle <label>,
     awaiting confirmation to continue."*
   - If **no carried work** (idle): *"Track N online, idle, awaiting assignment."*
4. **Then HOLD** — idle on the Sandesh watcher, **zero LLM turns, never self-poll**.
   Mainline disposes and sends a `directive` that wakes you. Do not poll any board
   (`<client> next` included) in a loop; do not self-schedule.
5. A Track's SOLE contact is Mainline. Escalations, questions, status — all go to
   Mainline, never the user directly.

---

## Guardrails

- **Never** start CR work, dispatch sub-agents, or merge as part of bootstrap — this is
  setup + status only. Mainline waits for the user; a Track waits for Mainline.
- The watcher runs through the Model B watcher or, when it is not installed, as a PLAIN
  background process that notifies you when it exits; exactly one per address; never
  inline, never a `while … sleep` retry wrapper.
- Never machine-wide process kills to "clean up" a stale watcher — `sandesh addressbook --project <Project>`
  confirms liveness; a duplicate watcher exits `5` (already live), which is benign.
- Mainline reports to the USER; a Track reports to MAINLINE. Do not cross these.
- If you are a Solo orchestrator (no tracks, no worktrees), follow the MAINLINE branch
  for queue + user reporting; the Sandesh/Track machinery is inert.
