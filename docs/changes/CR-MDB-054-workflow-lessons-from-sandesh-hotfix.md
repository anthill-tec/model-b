# CR-MDB-054 — Workflow lessons from other projects' runs (Sandesh's 0.4.1 hotfix run, Crucible)

**Status:** PENDING — **SEED, not the finished spec** (filed 2026-10-03 into release 1.1.0, wave 3).
Gap analysis, the design record, the spec and its pre-review happen in order when this CR starts.
**Type:** refactor (skills, agent definitions)
**Priority:** P2 — release 1.1.0, wave 3.
**Depends on:** none (board-authoritative: read `queue`, not this line)
**Labels:** skills, agents, crucible, release, conventions
**Design reference:** Sandesh #1418 (Mainline - Sandesh, 2026-10-03; owner rulings and gate findings
from the Sandesh 0.4.1 hotfix run); Crucible #1538 (item 9, user 2026-11-08); Crucible #1542 (items 10 and 11, PRD D6 amendment of
2026-11-08); Crucible #1544 (item 12, PRD D6 amendment of 2026-11-08); PRD D3 and D5; DN-multi-harness-deploy-model §D18

## Context

Sandesh runs its development on Model B's skills and agent definitions. Its 0.4.1 hotfix run
produced owner rulings and gate findings that belong in the shared definitions, not only in
Sandesh's project memory. Each item below is measured against Model B's own text and suite at gap
analysis, and the ones that conflict with an existing Model B rule are brought to the user as rulings
before the spec derives from them.

## Scope (seed — the twelve lessons)

1. **CI and release work is not entirely a chore** (user ruling 2026-10-10, superseding Sandesh's
   "chore, never a CR"). The no-mistakes gate is comprehensive, and fixes and changes may be made
   within it. Beyond the gate, changes that are largely metadata and release scripts can be chores
   (`chore(ci|release): …`, no CR, cycle or RED/GREEN agent); larger release-process changes are CRs
   (e.g. CR-MDB-058). *Superseded in part by item 12 (user 2026-11-05): release and packaging work is a
   CR unless the user marks it a chore.* Candidate homes: `cr-authoring` (CR vs task), `orchestration-common` (workflow
   gates), `git-workflow` § Releases.
2. **Tests on release and CI configuration are added per recommendation and discussion with the
   user** (user ruling 2026-10-10) — neither forbidden nor a default. Pins that change every release
   and detect nothing about the product are the smell to raise. **The default is the Crucible
   client's AXI API, which guides the release and gate flow** (envelope `help[]`, `history`,
   `--release`, `gate-run`, `milestone`). Candidate homes: the RED template, gap-analysis Dimension 7
   (cost). *Measure:* Model B's own pins (e.g. `test_pi_package`'s package version, any `release.yml`
   shape tests).
3. **Caller-existence is VERIFY's grep, never a source-text test.** Behavioural tests prove the seam.
   Candidate homes: `cr-authoring`'s caller-existence AC, the RED and VERIFY templates. *Measure:*
   which of Model B's structural gates are product contracts (skill text is Model B's product) and
   which only pin implementation text.
4. **While a plan is open, every dispatch carries a cycle id, or the CR is closed first.** Candidate
   homes: the sub-agent procedure, `orchestration-mainline`. *Reconcile:* the spec pre-review registers
   as `report` with no cycle (CR-MDB-046) — it runs before `plan-file`, so no plan is open.
5. **Crucible verbs: check `ok=`; re-register on a 409.** A truncated output can hide a failed
   transition. Candidate home: the `crucible` skill. *(Skipping a dead cycle moved to CR-MDB-059 §B4,
   2026-10-10: Crucible 0.3.0 ships a `cycle-skip` verb, and the orchestrator never uses the HTTP
   API — the raw `PATCH …/cycles/<id>` route this item cited is retired.)*
6. **Record the release in the same turn as `git flow release finish`.** `milestone --type release`
   follows finish immediately, not deferred until publishes are confirmed; `shutdown` treats a finished
   release with no release milestone as dangling work; `--packages` takes `registry:name:version`
   (bare entries are dropped). Candidate homes: `git-workflow` § Releases, `model-b` §4, `shutdown`.
7. **lean-ctx outside the project root.** lean-ctx refuses paths outside the project root (skills,
   `~/.crucible/clients`) unless `LEAN_CTX_EXTRA_ROOTS` covers them; agent definitions that require
   lean-ctx state it. Candidate homes: the agent templates, `contracts/lean-ctx.md`. Model B never
   writes the user's lean-ctx config.
8. **A release's expected date is at least the next day.** `release-propose --target` is set to at
   least the day after the proposal, never the same day, even for a hotfix or a one-CR patch: the
   board's burn-down projection needs a day ahead to project against. Re-running `release-propose`
   with a new `--target` updates the stored date. Candidate homes: `cr-authoring` (first filing
   proposes the release), the `crucible` skill's `release-propose` entry, `git-workflow` § Releases
   (a hotfix's proposal). Source: Sandesh #1470.
9. **A question to the user is grounded in the spec, or not asked** (Crucible #1538, user-directed
   2026-11-04; placed here by the user 2026-11-08). Before asking, the orchestrator checks whether the
   user's existing rulings already answer it; if they do, it applies them and does not ask. A ruling
   still needed is asked with: the spec section or AC quoted word for word, and what it leaves open;
   what the code does today, by file and symbol; a concrete example in the project's real terms (its
   manifest, stacks, scripts), never a hypothetical; and what each option changes in behaviour. Tests,
   findings and rulings are described in the user's and the spec's words, each test as the behaviour it
   pins, in one plain sentence. Candidate homes: `gap-analysis` beside Rule 19 (which says when to ask,
   not how), `orchestration-common` (Mainline, Track, Solo), and the VERIFY and FIX sections where
   findings come back to the user. Source: CR-CRU-226's VERIFY, where a ruling was asked with no spec
   text that the user's standing rule already answered.
10. **Execution decisions are the orchestrator's; it escalates only a change to the feature** (Crucible
    #1542, user-directed 2026-11-04; PRD D6 amendment of 2026-11-08). Cycle order, re-seeding or deleting
    a test, the disposition of an agent's findings and escalations (a test defect included), and how the
    approved spec's words read are the orchestrator's to decide and record. The user sees beforehand only
    a finding that demands a change to the behaviour the approved spec states, after the orchestrator
    has checked the spec and the filed plan. **VERIFY's findings are included** (user, 2026-11-08). Text to
    change: `orchestration-mainline.md` "Mainline disposes accuracy/scope itself; escalates ONLY …"
    (narrowed: a disposition the spec and plan settle is never escalated, and a sub-agent's execution
    escalation is Mainline's to rule on); its "Agent hedge phrases … never unilaterally decide a flagged
    concern is fine" (reworded: STOP and examine the concern; surface it to the user only when it
    demands a change to the feature; rule on everything else and record the ruling);
    `orchestration-common.md` "A VERIFY finding the user approves for fixing is fixed in its own FIX
    cycle" (reworded: the orchestrator decides which findings are fixed, reports the dispositions in the
    merge sign-off). "Question economy" and the design-gap rule (the CR does not say how) stand; merge
    sign-off stays the user's. *Measure:* every other surface that routes a finding to the user (the
    VERIFY and FIX templates, `orchestration-track.md`, the `model-b` skill's sub-agent procedure).
11. **A cycle re-seeds, inside itself, the existing tests its own change breaks** (Crucible #1542,
    user-directed 2026-11-04; PRD D6 amendment of 2026-11-08). The plan is filed with each cycle's scope
    including every existing test its change breaks by design: not an earlier cycle (already closed),
    not a later one (a cycle ending red by design is a planning fault, and GREEN cannot tell its own
    breakage from the planned breakage). Candidate homes: `orchestration-common.md` § Cycle discipline,
    beside "One cycle per coherent behaviour unit" and at the setup-ordering step that files the plan;
    `gap-analysis` (the analysis lists the tests each section breaks). Source: Crucible CR-CRU-229,
    plan 232, where one section's tests were left red for a later cycle.
12. **What a chore is** (Crucible #1544, user rulings 2026-11-05; PRD D6 amendment of 2026-11-08). A
    chore is design-time work on the project's state or metadata, never a change to what the code does
    or what a test pins: no CR, plan, cycles or VERIFY; the orchestrator does it itself, as a `chore(…)`
    commit on develop or locally for an untracked artefact. Most documentation work is a chore, and a
    chore never redesigns. **Release and packaging work is a CR unless the user marks it a chore**; the
    release procedure stays a boundary event. Use cases: reconciling spec `Status` lines with the board
    (a lapsed close-out flip, one word per file, no AC box ticked); a pre-release docs sync the user marks
    a chore; documenting what exists; spec wording that settles an ambiguity the code already resolves;
    CHANGELOG and README upkeep. Candidate homes: `cr-authoring` (CR vs task, beside the
    release-is-not-a-CR rule), `orchestration-common` (beside the two-phase workflow and the commit and
    doc conventions; the close-out's `Status` flip), `git-workflow` § Releases (the docs sync as a
    pre-release step). *Measure:* Model B's own commit types for design-time docs (`docs(changes)` today
    against `chore(docs)`), and any shipped spec whose `Status` line the board contradicts.
