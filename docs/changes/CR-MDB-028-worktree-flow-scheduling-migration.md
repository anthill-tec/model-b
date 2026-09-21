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

**RECONCILED 2026-09-21 (user directive: "reconcile your local db and the new Crucible V2 based
tracking… migrate fully to Crucible V2"). The result changes this CR's nature: there is NO DATA TO
MIGRATE, so this is a DELETION, not a migration.**

Measured on both sides:

| Side | State |
| --- | --- |
| Crucible production board | Exactly ONE project — `Model B`, key `019f7eb8-8cad-7000-9838-854eca8e7c20`, `sutRoot` correct, active. 27 queue entries, 16 plans, 47 cycles, the 1.0.0 release with waves and sequences. No duplicate project to merge. |
| Local `schedule_db` for Model B | **Does not exist.** Neither `.wf-schedule.db` nor the legacy `.nai-schedule.db` exists anywhere in the Roundhouse tree or under `$HOME`. It was never created. |

So `worktree-flow next`'s `schedule_db unavailable — queue-only project` is not a degraded state;
it is the ONLY state this project has ever had. **Model B's scheduling truth has always lived in
Crucible.** The V2 data migration is therefore already complete, and what remains is code and
published instructions pointing at a backend that holds nothing.

That reframes the work: every §S below is subtractive — delete the dead path, repoint the docs.
Nothing is copied, transformed or backfilled.

**⚠ CROSS-PROJECT BLAST RADIUS, found by this reconciliation and NOT previously known.** The only
live schedule DB on this machine belongs to **NAI**:
`/home/antonyj/Documents/data_projects/nai/.wf-schedule.db` — 225 KB, **334 changeset rows**
(`CR-NAI-280/281/282/309/311`, …), with three `Track N - Nai` watchers running. NAI is **not** on
this Crucible install (the board lists only `Model B`). **Model B ships the tool NAI depends on**
(`scripts/schedule_db.py`, deployed through the `.agents/scripts` asset class). §S5's proposal to
retire it would pull the backing library out from under an active project holding live state.
§S5 is rewritten accordingly.

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
| `cs` | write a ChangeSet row **and** stamp finding→CR ownership in one act | hard `sys.exit` | **Splits into two commands**: `cr-plan --cr --title --release --wave` files the CR; `rust-code-health.py ledger assign --slice <CR> --ids F-…,DS-…` stamps the findings. See §S6 — the ledger half was NOT lost, it was always a separate tool |
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

### §S2 — `next` is REMOVED, not delegated (decided at gap-analysis)

The earlier draft deferred this binary to implementation. Deferring a costed choice past the
branch cut is how it gets made by whoever picks up GREEN, so it is settled here: **remove**.

Reasons, in order of weight: delegation would have Model B shell another project's client and
inherit its absence as a runtime failure mode, which contradicts the standing "Model B maintains
no client code" directive in spirit if not in letter; it keeps a second name for one answer alive
indefinitely; and the callers are few and already enumerated (§S7 — three files, four references).
Removal costs one repoint each and leaves exactly one board.

`worktree-flow next` is deleted. Every caller names `python-crucible.py next` directly.

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

### §S5 — `schedule_db.py` STAYS SHIPPED — it is NAI's, not dead code

**Rewritten 2026-09-21 after reconciliation.** The original §S5 proposed retiring `schedule_db.py`
from `scripts/` and from the installer's tool-script asset class, reasoning that shipping a tool
whose banner says it is superseded teaches the wrong thing. **That reasoning was right about Model
B and wrong about the machine.** `schedule_db.py` has a live consumer: NAI holds 334 changeset
rows in `.wf-schedule.db` and is not tracked on this Crucible install at all. Removing the module
from the deployed tool bundle would break an active project mid-flight.

So the disposition splits:

- **`worktree-flow.py` drops its `schedule_db` dependency** (§S1–§S4). That is Model B's call to
  make, and it is what "migrate fully to Crucible V2" means for *this* project.
- **`scripts/schedule_db.py` REMAINS** in the repo and in the `.agents/scripts` asset class, with
  its TRANSITIONAL banner intact. It is no longer Model B's backend; it is a tool Model B
  publishes that another project still depends on.
- **Its banner is corrected** to say exactly that, because the current wording implies an imminent
  removal that must not happen while NAI relies on it: the successor for *Model B* is Crucible's
  queue; retirement of the module itself is gated on its remaining consumers migrating, which is
  NOT this CR's business and NOT Model B's decision alone.
- **Any test that drives `schedule_db.py` stays** — it still ships, so it still needs coverage.
  Only tests asserting `worktree-flow`'s DB *coupling* retire.

**Do not "finish the job" by deleting the module.** A cross-project dependency discovered late is
exactly the kind of thing this project has repeatedly paid for; it is recorded here so the next
reader does not re-derive the tidier, wrong conclusion.

### §S6 — The audit-cull ledger: what `cs` actually coupled, measured

**Added at gap-analysis 2026-09-21, and it CORRECTS an overstatement made earlier in that same
analysis.** The first reading claimed removing `cs` would "silently sever the code-health ledger's
board mirror". Reading the code rather than the call site shows that is wrong, and the accurate
version matters because it decides whether `cs` is removable at all.

**What the ledger is.** A git-committed JSONL file at `docs/research/assets/audit-cull-ledger.jsonl`
(`<domain>-audit-ledger.jsonl` for any non-cull domain — the mechanism is domain-generic since
2026-07-06). One row per FINDING (`F-*`, `DS-*`) discovered by `rust-dead-scan.py` /
`rust-code-health.py`, carrying `id`, `status` (`PROPOSED`/`APPROVED`/…), `slice` (the CR that
currently owns it) and `slice_history[]` of `{cr, assigned, outcome, closed}` — the finding's CR
lineage across time, with a single-active-owner invariant enforced by `_close_hist`/`_open_hist`
(`rust-code-health.py:249-265`, `:299-318`).

**What Crucible V2 does not have.** A *finding* is sub-CR. V2's atoms are CRs, plans, cycles, runs,
gates and milestones; there is no row for an individual defect, therefore no finding→CR assignment,
and no across-time finding lineage. `cr-supersede` records CR→CR succession, not this. That gap is
real but it is **not created by this CR** — the ledger has always lived in a Model B tool, never in
the board.

**What `cs` actually did, and why removal is still safe.** `worktree-flow cs --type maintenance
--findings …` was a CONVENIENCE that performed two independent acts in one call: file the CR, and
stamp the findings. Measured facts that make the split harmless:

- `rust-code-health.py ledger assign --slice <CR> --ids …` performs the stamping **standalone**
  and does not call `worktree-flow` at all.
- `rust-code-health.py:341-359`'s full-sync path imports `schedule_db` **directly** (`:345`) to
  read board state; it never invokes `worktree-flow`. §S5 keeps that module, so this path is
  untouched by this CR.
- `ledger sync --slice X --db-state STATE` works with no DB whatsoever.

So the only thing lost is the two-in-one convenience, and the only thing degraded is the automatic
board→ledger fan-out — which for Model B fans out from a DB that has always been empty.

**Consequence for §S1:** `cs` IS removable, conditional on the code-health skill's ChangeSet-filing
step being rewritten as the explicit two-step. That rewrite is CR-MDB-023's, not this CR's — see
the coordination requirement in the ACs.

### §S7 — Measured consumer list (the pre-removal grep, performed at gap-analysis)

§Risk said "grep the repo and the bundles before removal". Done 2026-09-21; recording the result
here so it is discharged by an AC rather than repeated:

| Consumer | Verb(s) | Disposition |
| --- | --- | --- |
| `skills-src/bootstrap/SKILL.md:156,201` | `next` | repoint at Crucible (§S3) |
| `skills-src/model-b/references/orchestration-track.md:10` | `next` | repoint (§S3) |
| `skills-src/memory-templates/rust-orchestration.md:14,18,20` | `next`, `reconcile`, `cs` | repoint `next`; delete the `reconcile` and `cs` lines (§S3) |
| `scripts/rust-code-health.py:30` (docstring) | `cs` | rewrite as the two-step (§S6) |
| **CR-MDB-023** (`:26`, `:42-46`, `:125-126`) | `cs` | **cross-CR — see ACs.** 023 adopts a skill whose `:35` instructs `cs` |
| `archive/wave2/**` | all | immutable history; excluded |

## Acceptance criteria

- [ ] **§S7: every consumer in the measured table is dispositioned** — `bootstrap/SKILL.md` ×2,
      `orchestration-track.md` ×1, `rust-orchestration.md` ×3, `rust-code-health.py:30` ×1. The
      assertion names the files and the count (7 live references), so fixing one cannot satisfy it.
- [ ] **§S6: `rust-code-health.py:30`'s docstring teaches the TWO-STEP** — `cr-plan` to file the
      CR, `ledger assign` to stamp the findings — and no longer cites `worktree-flow.py cs`.
- [ ] **§S6: the ledger itself is untouched.** `ledger assign`, `ledger sync --slice X --db-state
      STATE`, and the JSONL schema (`id`/`status`/`slice`/`slice_history[]`) are unchanged, proven
      by their existing tests passing untouched. This CR removes a convenience, not a capability.
- [ ] **CROSS-CR: CR-MDB-023 must not adopt a skill instructing a removed verb.** 023's `:35`
      ChangeSet-filing step is rewritten as the two-step BEFORE either CR merges, and 023's claim
      that "the skill needs no rewrite when the storage moves" is corrected. Whichever CR merges
      second verifies the other's text; neither may land assuming the other's wording.

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
- [ ] `schedule_db.py` is **still present** in `scripts/` and still in the installer's tool-script
      asset class — its removal is explicitly NOT part of this CR (§S5). Asserted positively, so a
      later tidy-up cannot silently drop it.
- [ ] `scripts/schedule_db.py`'s banner names Crucible's queue as *Model B's* successor and states
      that the module itself persists for other consumers, with no implied removal date.
- [ ] Tests covering `schedule_db.py` itself still pass unchanged; only tests asserting
      `worktree-flow`'s coupling to it retire.
- [ ] Nothing in this CR touches `/home/antonyj/Documents/data_projects/nai/` or any other
      project's state.
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
