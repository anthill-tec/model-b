---
name: shutdown
description: End-of-run teardown for a Model-B orchestrator session (Mainline or Track). Brings ONE orchestrator down cleanly — finishes its active step, finishes its plan's active cycle on the Crucible board, leaves no dangling commits, acks, and KILLS ITS OWN NOTIFIER LAST. Graceful by default; an `emergency` flag (power-failure-class) switches to immediate fast-abort. A Track is normally shut down by a Sandesh `directive` from Mainline (or `/shutdown` typed by the user) and acks back to MAINLINE that it is safe to stop; Mainline is shut down by the USER directly and tears itself down ONLY after every active Track has acked / shows down. `/shutdown` takes NO role argument — a shutdown is contextual (the running session already knows its role from its bootstrap, its carried context and its Sandesh address, and a Sandesh shutdown directive is already addressed to one orchestrator); the only optional argument is `emergency`. Use when the user types "/shutdown", says "shut down", "stand down", "end of day, close out", "wind down the orchestrators", or when a Track receives a shutdown directive from Mainline.
---

# Shutdown — end-of-run orchestrator teardown

A run (or a day) is ending. This skill brings ONE orchestrator session down **cleanly**:
it finishes whatever it is mid-doing, settles its working folder (no dangling/uncommitted
work), tells the rest of the team it is safe to stop, and — as the **final** act —
kills the Sandesh notifier it owns.

**Two modes, chosen by the `emergency` flag:**
- **Graceful (default)** — finish the active step, finish the plan's active cycle, merge the active
  CR back, commit so nothing dangles, ack, then kill the notifier. Nothing is abandoned.
- **Emergency** (`emergency` in the command/directive — power failure, host going down) —
  close only the active write so nothing is left half-written, **fast-abort** the rest
  (skip finishing the active cycle, no merge), best-effort ack, then kill the notifier. Fast-abort is
  permitted **only** here.

**Role asymmetry is the point of this skill:**
- **Mainline** is shut down by the **USER**. It dispatches the shutdown to the Tracks and
  tears *itself* down **only after every active Track has acked / shows down**. It is the
  LAST orchestrator to go.
- **Track** is normally shut down by **MAINLINE** (a Sandesh `directive`) and **acks back to
  MAINLINE** that it is safe to stop (or to the USER if the command came on its own session).
  A Track never tears down before its active CR is settled, unless told to emergency-stop.

**The one overridden rule:** everywhere else, a stopped watcher is relaunched in the
same turn — by the Model B watcher itself, or by you on the fallback path — except after an
error or a terminal exit on the Model B watcher, or a terminal exit (`3`/`4`/`5`, per the
PRIME DIRECTIVE table in `sandesh.md`) on the fallback path, which is never
relaunched (the relaunch-on-exit PRIME DIRECTIVE). **Shutdown is the single exception** —
its final step kills the notifier and does **not** relaunch. Keep the notifier ALIVE
through the whole teardown (you need it to receive acks and a possible late emergency-stop);
kill it only once everything else is done.

---

## Step 0 — Resolve context (role + project) + the emergency flag, BEFORE anything else

Unlike `/bootstrap` — which ESTABLISHES identity at session start and so takes the role as its
verb — `/shutdown` runs on an **already-running** session whose role is **already known**, so it
takes **no role argument**. A shutdown is always contextual:
- typed on the orchestrator's own command line ⟹ this session already knows whether it is
  Mainline or Track N (from its bootstrap, carried context, and Sandesh address);
- delivered as a Sandesh `directive` ⟹ it was addressed to one specific orchestrator — the one
  now acting on it.

1. **Role — resolve from this session's established identity, NOT an argument.** Use the role
   fixed at bootstrap or stated in the carried context; failing that, your Sandesh address
   (`Mainline - <Project>` ⟹ Mainline, `Track <N> - <Project>` ⟹ Track N). It selects your
   branch below (2A Track / 2B Mainline). A running orchestrator always knows this; only if one
   genuinely cannot, ask.
2. **Project** — `<Project>` is the Sandesh project, read in Step 0.5 from `SANDESH_PROJECT`.
3. **Emergency flag — the only argument that matters.** Scan the command/directive for
   `emergency` (or `--emergency`). Present ⟹ **EMERGENCY** (Step 1B); absent ⟹ **GRACEFUL**
   (Step 1A). A Mainline-dispatched directive carries the flag in its subject/body; the Track
   inherits it.
4. **Who issued it** — the User (on this session) or Mainline (a Sandesh `directive`). Fixes your
   **ack target** (Step 2/3): Mainline-issued ⟹ ack Mainline; User-issued on your own session ⟹
   ack the user.

---

## Step 0.5 — Read your role's rules (BOTH roles)

Before tearing anything down, **load and read the rules that bind your resolved role** —
exactly as bootstrap requires — so the teardown is performed the way YOUR role must perform
it. Mandatory, not a skim. In order:
1. The `model-b` references:
   1. `~/.agents/skills/model-b/references/orchestration-common.md` — universal orchestrator rules (EVERY role).
   2. Your role file: Mainline → `~/.agents/skills/model-b/references/orchestration-mainline.md` ·
      Track → `~/.agents/skills/model-b/references/orchestration-track.md`. (A Solo orchestrator follows Mainline.)
   3. `~/.agents/skills/model-b/references/sandesh.md` — the channel mechanics for the ack + (Mainline) the
      collect-acks loop.
2. The project's `AGENTS.md` (its conventions) and `.env` (its identity — the naming registry).
   Take the identity from the registry keys, by name:
   - **Sandesh project** — `SANDESH_PROJECT`. `<Project>` in this skill is the value of `SANDESH_PROJECT`, exactly as written (case- and space-sensitive).
     Your address is `Mainline - <Project>` or `Track <N> - <Project>`, and every `sandesh`
     CLI call (`addressbook`, `notify`, `send`, `reply`, `unregister`, …) passes `--project <Project>`.
   - **Crucible own-run id** — Mainline (or Solo): `ORCHESTRATOR_LABEL`; Track N:
     `track<N>-<PROJECT_TOKEN>`.
   - **Crucible client** — the project's stack client, resolved through Crucible's installed
     manifest `~/.crucible/crucible-clients.json`: its `clients` entry for a stack in
     `PROJECT_STACKS` (any one: every stack client carries the plan verbs) names the client
     file. The entry key is the stack name, except quarkus and java, which share the `mvn`
     entry (`mvn-crucible.py`). `<client>` below is that path.
     `<client> plans` shows your plan's active cycle (its id and label); `<client> next` shows
     what is ready.
3. `docs/memory/INDEX.md` — the project memory index — and the slices it lists (the stack's
   orchestration template, `docs/memory/<stack>-orchestration.md`, among them): standing
   feedback this teardown obeys.

**Fallback** — a project with no `.env` registry, or a missing key: take the same value from
the project's `AGENTS.md`; a value found in neither, ask the user once. A missing
`docs/memory/INDEX.md` is noted and skipped. Nothing here is an error.

If a later step conflicts with a role rule, the **role rule wins** — re-read rather than guess.

---

## Step 1 — Classify the shutdown (BOTH roles)

The active-step rule applies to **both** modes and comes first, always:

- **Close the active step.** If a tool thread is mid-flight — a file write/edit, a commit,
  an in-progress agent — let it finish so nothing is left half-written or a repo half-mutated.
  Never begin teardown on top of an open write. This holds even in an emergency (a corrupt
  half-written file helps no one).

Then branch:

### Step 1A — GRACEFUL (default)
Nothing is abandoned. You will finish the plan's active cycle, settle the repo, ack, and only then kill the
notifier. Proceed to your role branch (2A Track / 2B Mainline).

### Step 1B — EMERGENCY (`emergency` flag set)
Host is going down (power failure, forced stop). After closing the active write:
- **Fast-abort** the rest — do NOT finish the active cycle, do NOT attempt a CR merge.
- Preserve in-progress work where cheap: leave the worktree intact or `git stash` it (so the
  next run can resume); do NOT force a merge.
- Best-effort ack (Step 2/3) naming what was left mid-flight.
- Then the common final step (kill notifier). Speed over completeness — but never skip
  closing the active write, and never machine-wide-kill.

---

## Step 2A — TRACK shutdown

**Graceful (1A):**
1. **Finish the active step** (Step 1) — wait for any in-flight write/tool thread to close.
2. **Mid-CR with an active cycle on the plan? ESCALATE first, do NOT abruptly stop.** Tell Mainline
   you are mid-cycle —
   `sandesh send --project <Project> --from "<your address>" --to "Mainline - <Project>" --kind request --subject "…" --body "…"`:
   *"Track N got a shutdown; mid CR-XXX, active cycle <label>. Non-emergency → I'll
   finish the active cycle + merge, then ack. Say `emergency` if you need an immediate stop."*
   - **Non-emergency (default):** keep working — finish the plan's active cycle and get
     the active CR **merged back** (`git merge develop --no-edit` to behind=0, then
     `~/.agents/scripts/worktree-flow.py finish` — merge-not-rebase). The active CR landing is part of a clean
     graceful shutdown. (worktree-flow now emits a TOON envelope on stdout; the human
     board is on stderr.)
   - If Mainline/User replies with an emergency/immediate-stop → switch to the **Emergency**
     path below.
3. **No dangling work.** Ensure your working folder (the CR's worktree, `.worktrees/<cr>`) is clean: **commit any
   uncommitted changes** (never leave WIP on disk) and confirm the active CR is merged (no
   unmerged commits left stranded on the feature branch). `git status --porcelain` empty.
4. **ACK that you are safe to shut down** — to **Mainline** (`sandesh reply --project <Project>
   --from "<your address>" --to-msg <id> …` threaded under the shutdown directive, or
   `sandesh send --project <Project> --from "<your address>" --to "Mainline - <Project>" …`),
   or to the **user** if the command came on this session:
   *"Track N safe to shut down — CR-XXX merged @ <HEAD>, lane drained, worktree clean / no
   carried work."* The ack IS the shutdown indicator.
5. **LAST — kill your own notifier** (see § The common final step). Do not relaunch.

**Emergency (1B):**
1. Close the active write only.
2. Fast-abort — leave the worktree as-is or `git stash`; no finishing of the active cycle, no merge.
3. Best-effort ack to Mainline: *"Track N EMERGENCY-stopped — CR-XXX left at <state>, worktree
   preserved/stashed for resume."*
4. **LAST — kill your own notifier.**

---

## Step 2B — MAINLINE shutdown

The command is issued **directly by the User**. Mainline orchestrates the team's teardown
and goes **last**.

1. **Dispatch the shutdown to ALL active Tracks — propagating the `emergency` flag.** A Mainline
   shutdown is NEVER just Mainline. From `sandesh addressbook --project <Project>` take every
   active track and send a directive (`sandesh send --project <Project> --from "<your address>"
   --kind directive --to all-tracks …`, or `--to` each) telling them to shut
   down so each runs its own Step 2A. **If the User's shutdown carried `emergency`, the directive
   to EVERY track MUST carry `emergency` too** — the host is going down and takes the tracks with
   it, so they fast-abort rather than drain. A graceful Mainline shutdown dispatches a graceful
   track shutdown. State per-track context (CR status, queue for next run).
2. **WAIT for every active Track to ACK safe-to-shutdown — keep your notifier ALIVE for this.**
   Acks arrive as Sandesh mail; your watcher wakes on them (fetch — and, on the fallback path,
   relaunch — as normal; the notifier stays up until *your* final step). Two convergent signals, use both:
   - the explicit **ack** from each track, AND
   - the Sandesh **active-state**: a track that has shut down shows `active:false` /
     `listening:false` in the addressbook. Cross-check acks against the roster.
   **Do not proceed to your own teardown until every active track has acked AND/OR shows down.**
   A track that escalated "mid-cycle, draining" is not done — wait for its final ack (or, if
   the User declared emergency, dispatch the emergency flag and accept best-effort).
3. **No dangling work on the integration tree.** `git status --porcelain` on develop must be
   empty — **commit** any uncommitted design-doc/spec work (commit-design-docs-promptly).
   Push is the User's call — ask, or follow the standing rule. (Emergency: commit if safe;
   only true power-failure justifies skipping.)
4. **Report to the USER** — all tracks confirmed down (ack + active-state), develop HEAD +
   ahead/behind, and what is queued/locked for the next run.
5. **LAST — kill Mainline's OWN notifier** (see § The common final step). Mainline is the
   final orchestrator down.

**Emergency (Mainline):** dispatch the emergency directive to all tracks immediately;
collect best-effort acks / confirm via active-state within a short bound rather than waiting
on a full graceful drain; commit develop if safe (else fast-abort); then kill the notifier.

---

## The common final step — kill your notifier LAST

For **every** orchestrator, the final action is killing the notifier it owns, with **no
relaunch** — the single documented override of the relaunch-on-exit prime directive, applying
ONLY here, at a confirmed shutdown's last step.

- **Why last:** you need the notifier alive throughout the teardown — a Track to receive a
  late emergency-stop, Mainline to receive every track's ack. Kill it only when everything
  else (drain, merge, commit, ack/report) is done.
- **How:** stop your watcher, in this order:
  - through the **Model B watcher**'s stop, when it runs your notifier; **or**
  - on the fallback path, through the harness facility that runs your background process,
    stopping your own process only; **or**
  - as the last resort, a targeted kill of *your own* address's notifier only:
    `pkill -f "sandesh notify --to '<your exact address>'"`.
  - **Never** a machine-wide `pkill sandesh` / broad kill — that would take down OTHER
    orchestrators' watchers. Kill only the one you own.
  - Then `sandesh unregister --project <Project> --address "<your address>" --as "<your address>"` for a clean
    addressbook (`active:false`), so the roster reflects you are down.
- Next run, `/bootstrap` brings you back (re-register + relaunch the watcher). Shutdown
  kills; bootstrap revives.

---

## Guardrails

- **Never tear down mid-write.** Close the active step first — graceful AND emergency.
- **Fast-abort (skip finishing the active cycle + CR merge) is permitted ONLY under the `emergency` flag.**
  A normal shutdown ALWAYS finishes the plan's active cycle, merges the active CR back, and commits a clean tree.
- **No dangling work at shutdown** — `git status --porcelain` empty; the active CR merged;
  WIP committed (or, emergency-only, stashed/preserved).
- **Acks route by role** — a Track acks MAINLINE (or the user if the command came on its own
  session); Mainline reports the USER. Do not cross these.
- **Mainline goes last** — it shuts down ONLY after every active Track has acked / shows down.
  Never abandon a track mid-cycle in a non-emergency.
- **Kill ONLY your own notifier**, as the LAST step, and do NOT relaunch it. This is the sole
  place the relaunch-on-exit directive is overridden — everywhere else, a dead watcher is a bug.
- A **Solo** orchestrator (no tracks) follows the MAINLINE branch with the Track-dispatch +
  wait-for-acks steps inert: settle develop, report to the user, kill its notifier.
