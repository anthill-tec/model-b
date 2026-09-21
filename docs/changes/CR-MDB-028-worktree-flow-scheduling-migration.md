# CR-MDB-028 — Retire `worktree-flow.py`'s DB half: scheduling moves to Crucible's API

**Status:** PENDING
**Type:** maintenance / migration
**Priority:** **P0 for wave 1** (user ruling 2026-09-21: this ranks ABOVE the Roundhouse routing
strategy and the LLM auto-routing work). Rationale the user gave, and it is the right one: the
scheduling backend is *infrastructure the orchestrator uses every run*, while routing is *strategy
not yet gated open* — Phase 0 has seven unmeasured probes and CR-RND-001/002 are unresolved. Fixing
a live dual-source-of-truth defect in a shipped tool beats advancing a design that cannot be
validated yet.
**Depends on:** nothing in this repo. Its only gate — "Crucible 0.2.0 actually shipping" — is
**OPEN**: production runs **0.2.2** and the roadmap verbs are live and in use.
**Labels:** scripts, worktree-flow, crucible, scheduling, migration
**Phase:** Wave 1 (proposed)
**Design reference:** CR-MDB-022 §Context ("the retirement itself is a future CR gated on that
release, not this one") · user directive 2026-08-27 (`schedule_db.py` is transitional; Crucible
assumes responsibility for storing the workflow plan and state from 0.2.0) · `docs/changes/README.md`
footer 2026-08-27 and 2026-09-18 · measured client surface of the INSTALLED production client
(`~/.crucible/clients/python-crucible.py`, 0.2.2)

## Context

**This CR is the one CR-MDB-022 promised and deferred.** 022 adopted `schedule_db.py` as
TRANSITIONAL, banner and all, and wrote its sunset down explicitly: *"the retirement itself is a
future CR gated on that release, not this one."* The gate was Crucible 0.2.0 shipping. It shipped;
production is on 0.2.2; this session used the replacement verbs directly to put all 26 CRs on a
1.0.0 roadmap. **The gate is open and the CR was never filed.**

### The defect, observed rather than argued

At this session's bootstrap (2026-09-21) both boards were asked the same question and **disagreed**:

```text
worktree-flow.py next  →  DRAINED   "schedule_db unavailable — queue-only project"
python-crucible.py next →  NEXT cr=CR-MDB-017 seq=2001 wave=2 waveCompleted=1
```

Crucible knows the answer. `worktree-flow` cannot, because its backing store was never populated
and — by the standing directive — never will be. Two tools answering one question differently is
the exact failure class this project has repeatedly paid for (the 18-vs-11 dependency count, the
`models.yml` contract row). Here it is inside our own primary script.

### The coupling is 5 of 10 verbs, and the split is clean

Measured in `scripts/worktree-flow.py`:

| Verb | schedule_db use | Behaviour when absent | Crucible replacement (0.2.2, measured) |
| --- | --- | --- | --- |
| `cs` | write a ChangeSet row | hard `sys.exit` | `cr-plan --cr --title --release --wave`, `cr-depends --cr --on`, `wave-sequence --release --wave --crs` |
| `show` | read one CR's metadata | hard `sys.exit` | `queue` (registered CR rows) / `status` (plans + cycles) |
| `reconcile` | validate DB vs git | hard `sys.exit` | **no replacement — the verb dies with the DB** (there is no local index left to reconcile) |
| `next` | readiness | degrade → `DRAINED` + warning | `next` — and it answers the SAME vocabulary, `NEXT / HOLD / DRAINED` |
| `progress` | weighted task progress | degrade + warning | **no clean 1:1** — see §S4; this is the one open question, not a fill-in |

`start`, `status`, `sync`, `finish`, `abort` derive everything from **git** and are untouched by
this CR. That is the architectural line this CR draws and should be stated once, plainly:

> **`worktree-flow` owns what it can derive from git** (worktrees, ahead/behind, phase, merge).
> **Crucible owns what used to live in the DB** (queue membership, release, wave, seq, dependencies,
> readiness).

### Published instructions currently point at the wrong board

`skills-src/bootstrap/SKILL.md` Step 3A tells Mainline: *"the live git-derived board IS the source
of truth — never raw `sqlite3`, never the README"*, and routes scheduling questions through
`worktree-flow.py status` / `next`. Post-migration that is **half right and half wrong**: git-derived
worktree state, yes; scheduling truth, no. Left uncorrected, every future orchestrator reads the
board that cannot answer.

## Scope

### §S1 — Remove the `schedule_db` backend from `worktree-flow.py`

Drop the `import schedule_db as _sdb` seam and the five verbs' DB paths. `cs`, `show` and
`reconcile` are **removed**, not stubbed — a verb that exits non-zero with "unavailable" is worse
than an absent verb, because it reads as a broken tool rather than a moved responsibility. Their
help text names the Crucible verb that replaces them.

### §S2 — `next` delegates to Crucible, or is removed

Two acceptable outcomes, and the CR must choose one at implementation with the reason recorded:
either `worktree-flow next` shells the installed client and relays its envelope (one board, one
answer, callers unchanged), or it is **removed** and every caller is repointed at
`python-crucible.py next`. Delegation keeps existing muscle memory; removal keeps Model B out of
the business of proxying another project's API. **Do not keep a local answer.**

### §S3 — Repoint every published instruction

`skills-src/bootstrap/SKILL.md` §Step-3A, `skills-src/model-b/` orchestration references, and
`AGENTS.md` where they name `worktree-flow` for scheduling. State the git-vs-Crucible split above
verbatim, so the next reader does not have to infer it.

### §S4 — Decide `progress` deliberately (the one genuine gap)

`cmd_progress` reports weighted task progress against a ChangeSet row. Crucible has `milestone`,
`cycle-activate`/`cycle-done` and `checkpoint`, but none is a drop-in for per-task weighted
progress. Three options, to be settled in the CR rather than improvised: map it onto `checkpoint`;
drop the verb as unused (measure first — is anything actually calling it?); or keep it as the one
local-state exception with its own justification. **Measure usage before choosing.**

### §S5 — `schedule_db.py` itself

Once nothing imports it, decide whether it stays in `scripts/` as a deployed asset. It should not:
shipping a tool whose own banner says it is superseded teaches the wrong thing. Removal also
shrinks the installer's tool-script asset class by one. Any test that drives it retires with it.

## Acceptance criteria

- [ ] No `import schedule_db` (or `_sdb` reference) remains in `scripts/worktree-flow.py`.
- [ ] `cs`, `show` and `reconcile` are removed, and their absence is documented with the Crucible
      verb that replaces each.
- [ ] `next` either delegates to the installed client or is removed; **no code path produces a
      local scheduling answer**, and the chosen option's reason is recorded in the CR.
- [ ] Running `worktree-flow next` and `python-crucible.py next` in the same repo cannot return
      contradictory answers — asserted by there being only one source, not by comparing outputs.
- [ ] The git-derived verbs (`start`, `status`, `sync`, `finish`, `abort`) are unchanged in
      behaviour, proven by their existing tests still passing untouched.
- [ ] Every published surface naming `worktree-flow` for scheduling states the git-vs-Crucible
      split; zero surfaces route a scheduling question at `worktree-flow`.
- [ ] `progress` has a recorded decision backed by a usage measurement, not a guess.
- [ ] If `schedule_db.py` is retired, it is gone from `scripts/`, from the installer's tool-script
      list, and from any test that drives it — with no dangling reference anywhere.
- [ ] The suite's recorded baseline is re-measured and `AGENTS.md`'s baseline sentence updated if
      the count moves.

## Wave placement — SETTLED by user ruling

**Wave 1, P0, ahead of the routing/strategy work.** The earlier draft proposed wave 1 while noting
the counter-argument that 1.0.0 was scoped to ten CRs. The user ruled on 2026-09-21 that this CR
takes priority over the Roundhouse strategy and LLM auto-routing work, which settles it: 1.0.0
becomes eleven CRs.

The reasoning holds up against the record. Every run of this orchestrator reads a board that
structurally cannot answer, while the routing work it would displace is blocked on measurements
nobody has taken — PRD §11's seven open Phase-0 probes, `CR-RND-001`'s `reasoning_effort`
passthrough probe, and `CR-RND-002`'s billing-premise check. Shipping a fix for a defect we can
see, ahead of a strategy we cannot yet validate, is the correct ordering.

**User's call.** Filed at wave 1; move it with one line if you prefer the tighter release.

## Estimated size

One script edited (five verbs removed or delegated), one module possibly deleted, three published
surfaces repointed, tests retired with the code they cover. No new abstractions, no new asset class.

## Risk

- **`reconcile` has no successor.** It validated the local index against git; with the index gone
  the guarantee it enforced also goes. That is correct — there is nothing left to drift — but it
  should be recorded, not silently dropped.
- Delegating `next` couples our script to the installed client's presence. Use the manifest-anchored
  location (CR-MDB-020, `~/.crucible/clients/`), never a checkout path, and degrade with a clear
  message when the client is absent.
- Removing verbs is a published-surface change; anything scripted against `cs`/`show`/`reconcile`
  breaks loudly. Grep the repo and the bundles before removal, per CR-MDB-020's pattern.

## Non-goals

- No change to the git-derived verbs or their output contract (CR-MDB-010's TOON envelope stands).
- No new Crucible client code — Model B maintains none (standing directive).
- No re-litigation of whether Crucible owns scheduling; that is settled by user directive and by
  022's recorded sunset.
