---
name: bootstrap
description: Start-of-run bootstrap for a Model-B orchestrator session (Mainline or Track). Registers the session's Sandesh address and starts Sandesh's wake watcher through the harness's Sandesh extension, reloads the in-flight work from the Crucible board (the plan, its active cycle, `next`), and loads the last-held implementation-queue status. A Mainline session reads the implementation queue from Crucible and reports to the USER; a Track session just enables its notifier, reloads any in-flight cycle, informs MAINLINE of its status, and waits for instructions. The orchestrator ROLE is passed as the argument — `/bootstrap mainline` (the single per-project coordinator) or `/bootstrap track <N>` (a numbered worker, N = 1, 2, 3, …). Use when the user types "/bootstrap", or says "bootstrap", "new run starting", "start of day", or "boot the orchestrator".
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

Each role probes the other's liveness the same way, from the machine-readable addressbook —
`sandesh addressbook --project <Project> --format toon --fields address,status,listening`
(`listening` true = up and wake-reachable) — Mainline scans the tracks, a track scans Mainline.

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
`docs/memory/INDEX.md` is noted and skipped. Nothing here is an error. `KNOWLEDGE_CATEGORY`
has no fallback: without it, Step 0.6 is skipped, never asked about.

Do NOT proceed to Step 1 until you have read the common file **and** your role file **and**
the project's `AGENTS.md`. If a later action would conflict with a role rule, the **role
rule wins** — re-read rather than guess. (Sub-agents are out of scope here; their procedure
lives in `~/.agents/skills/model-b/references/sub-agent-procedure.md`, loaded at dispatch, not at bootstrap.)

---

## Step 0.6 — Load the execution knowledge (BOTH roles, only where `KNOWLEDGE_CATEGORY` is set)

The project's execution knowledge — the short facts `orchestration-common.md` § "Memory" keeps
in the project's knowledge store — is loaded once, here, so every later step runs with it.

Where the project's `.env` sets `KNOWLEDGE_CATEGORY`, load that category, in order:
1. restore the category's archived facts, so none the store set aside is missed;
2. then list that category — every fact under it;
3. report that the knowledge store is in use and how many facts it loaded (Mainline in its
   report to the user, a Track in its status to Mainline).

Load that category and nothing else: never a query recall, which returns matches rather than
the full listing, and never the store's automatic rooms, which hold captures rather than this
project's facts.

Without `KNOWLEDGE_CATEGORY`, this step is skipped and never asked about — nothing changes.

---

## Step 1 — Bring up the wake (BOTH roles) — CHECK before setup/register

Setup and registration are **persistent** — do NOT re-run them blindly each run. The
wake is Sandesh's wake watcher, started through the harness's Sandesh extension; Model B
reaches Sandesh itself only through the `sandesh` CLI. **Check state first** and do the
minimum:

1. **Your identity.** Your address is the role's: `Mainline - <Project>` or
   `Track <N> - <Project>`, where `<Project>` is `SANDESH_PROJECT`, from `.env` or the
   environment. Every call below passes that address and project explicitly.
   - **When the environment disagrees** — `$SANDESH_ADDRESS` is unset, or names another
     address than your role's — say so in your status.
   - For a Track this usually means the session was launched without its
     `env SANDESH_ADDRESS="<your Track address>" pi` override: direnv exports the Mainline
     address in every session started from the project directory.
   - The remediation: load direnv (`direnv allow` where the `.envrc` is), or relaunch the
     session with the override. A project scaffolded without `SANDESH_ADDRESS` or `.envrc`
     adds them by hand: a `SANDESH_ADDRESS` line in `.env` holding `Mainline - <Project>` in
     double quotes, and an `.envrc` holding `dotenv` beside it — never by re-running `modelb-axi init`, which overwrites the
     project's existing files.
   - Do not stop on it: carry on with your role's address passed explicitly.
2. **Check** `sandesh addressbook --project <Project> --format toon --fields address,status,listening`.
   It lists one record per address: `status` is `active` for a registered address, and
   `listening` is true while a watcher holds it. Read these fields, never the human table.
   - Project resolves AND your address is present and `active` → already set up and
     registered. **SKIP `sandesh setup` + `sandesh register`**; go straight to the watcher.
   - Project unknown / "not set up" error → `sandesh setup --project <Project>`, then
     re-check.
   - Your address absent or inactive →
     `sandesh register --project <Project> --address "<your address>"`.

   (Both calls are idempotent, but the point is to avoid needless churn — only call them
   when the check shows they're missing.)
3. **Start Sandesh's wake watcher** through the harness's Sandesh extension, for your
   address and `<Project>`, both passed explicitly. Always start it: the start is
   idempotent. An address the addressbook already shows listening may be held by a stale
   watcher or another session, so start it anyway.
   The extension supervises it: after every wake it starts again by itself and hands you a
   turn naming the unread ids. Check the in-session watcher with `/sandesh-watcher status`.
4. **The extension is missing?** If the harness's Sandesh extension is not installed, the
   wake is unavailable: say so, name the remediation (install `sandesh-pi`, which needs the
   `sandesh` CLI 0.4.0 or later), and carry on without a wake.
5. **Confirm** with
   `sandesh addressbook --project <Project> --format toon --fields address,status,listening`:
   your address `active` and listening. If it is not listening, check the address and project
   you passed to the extension, then start the watcher again.
6. **After a wake** you only fetch the named ids —
   `sandesh fetch --project <Project> --to '<your address>'` — and never relaunch anything.
   On a stop notice, follow `sandesh.md`: re-check your liveness, start the watcher again
   once for exit 1 or a signal, and report a tombstone (3) or an eviction (4).

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
2. **Check which Tracks are up and running** —
   `sandesh addressbook --project <Project> --format toon --fields address,status,listening`
   is Mainline's track-liveness probe. Read the fields per track:
   - `listening` true → watcher live: the track is **up and wake-reachable** (a directive
     will fire). This is "running".
   - `status` `active`, `listening` false → registered but its **watcher is down** — NOT
     reachable for a wake until its watcher is started again; treat as "up but not listening".
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
   waits for the user's go. Sandesh's wake watcher keeps itself running: after a fetch,
   nothing is restarted.

---

## Step 3B — TRACK: check for Mainline, enable notifier, inform MAINLINE, wait

1. The notifier is already up (Step 1). A Track does **not** read the queue board for
   scheduling and does **not** contact the user.
2. **Check that Mainline is up** —
   `sandesh addressbook --project <Project> --format toon --fields address,status,listening`,
   reading the `Mainline - <Project>` record (the reciprocal of Mainline's track-liveness probe):
   - `listening` true → Mainline is online and will **wake** on your report. Normal path.
   - `status` `active`, `listening` false → Mainline is registered but its watcher is down: your
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
- Sandesh's wake watcher runs through the harness's Sandesh extension — exactly one per
  address, started at bootstrap; you never launch `sandesh notify` yourself, and never wrap
  anything in a `while … sleep` retry loop.
- Never machine-wide process kills to "clean up" a stale watcher — the toon addressbook
  confirms liveness, and the extension itself retries once when the address is already live
  elsewhere, then stops with a notice.
- Mainline reports to the USER; a Track reports to MAINLINE. Do not cross these.
- If you are a Solo orchestrator (no tracks, no worktrees), follow the MAINLINE branch
  for queue + user reporting, wake included: register your address and start your own
  watcher in Step 1 as Mainline does, and stop it at shutdown. Only the Track machinery is
  inert: dispatching to Tracks and collecting their acks.
