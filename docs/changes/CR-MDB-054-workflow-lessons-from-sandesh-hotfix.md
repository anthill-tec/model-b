# CR-MDB-054 — Workflow lessons from other projects' runs (Sandesh's 0.4.1 hotfix run, Crucible)

**Status:** PENDING — **SEED, not the finished spec** (filed 2026-10-03 into release 1.1.0, wave 3).
Gap analysis, the design record, the spec and its pre-review happen in order when this CR starts.
**Type:** refactor (skills, agent definitions)
**Priority:** P2 — release 1.1.0, wave 3.
**Depends on:** none (board-authoritative: read `queue`, not this line)
**Labels:** skills, agents, crucible, release, conventions
**Design reference:** Sandesh #1418 (Mainline - Sandesh, 2026-10-03; owner rulings and gate findings
from the Sandesh 0.4.1 hotfix run); Crucible #1538 (item 9, user 2026-11-08); Crucible #1542 (items 10 and 11, PRD D6 amendment of
2026-11-08); Crucible #1544 (item 12, PRD D6 amendment of 2026-11-08);
Crucible #1548 (item 13, user-directed 2026-11-07);
Crucible #1552 (item 14, user-directed 2026-11-08); PRD D3 and D5; DN-multi-harness-deploy-model §D18

## Context

Sandesh runs its development on Model B's skills and agent definitions. Its 0.4.1 hotfix run
produced owner rulings and gate findings that belong in the shared definitions, not only in
Sandesh's project memory. Each item below is measured against Model B's own text and suite at gap
analysis, and the ones that conflict with an existing Model B rule are brought to the user as rulings
before the spec derives from them.

## Scope (seed — the fourteen lessons)

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
13. **A design is mature before the spec is approved** (Crucible #1548, user-directed 2026-11-07: a
    question about the feature after the design phase shows an immature design). Six rules for the gap
    analysis and design phase, each set against what `gap-analysis` already says:
    - **(1) A performance or UI criterion is proven before it is locked:** its bound is set only after a
      candidate fix passed the criterion's own scenario as the AC states it (same data size, path, cold
      and warm page), in a scratch copy; a figure measured otherwise is not evidence. *New;* beside
      Step 0 (baseline) and Dimension 3's budget checks.
    - **(2) Measurements are attributed before they are believed:** a slow figure is traced to its
      source (a trace or CPU profile) before it drives a design or an AC; test-harness work on the
      measured thread is excluded. *New;* beside Rule 10 (the protected path executes).
    - **(3) Everything the change's surface loads is listed** (for a page: every stylesheet and script
      in the HTML, plus what loads lazily). *New;* a Dimension 8-style reach list for runtime loads.
    - **(4) Every caller, item kind and lifecycle path is enumerated:** all call sites (other views
      sharing the code), every kind of item it draws, every lifecycle path (open, settle, abort, two at
      once, empty), each in scope or a named non-goal. *Extends* Dimension 3's "check ALL callers",
      Rule 15 and Dimension 9's scenario matrix, whose list gains item kinds and lifecycle paths.
    - **(5) The pre-review is decided mechanically.** *Already met* by Rules 21 and 25 (CR-MDB-096): any
      trigger, a user ruling included, means a pre-review before the spec is locked; `none` is written
      only with no trigger. The CR adds only that a `none` written over a trigger is a gap-analysis miss.
    - **(6) Every design choice reaches the user in one batch, before the spec is locked;** a question
      about the feature after approval is a design-phase miss, recorded as one and added to the
      checklist. *Extends* Rule 19 (forks are the user's) and Rule 17 (a mid-cycle spec change is a
      gap-analysis miss). It sits with `orchestration-mainline.md`'s "Question economy" ("Prefer one
      focused question over a battery"): one round, each question focused.
    Source: Crucible CR-CRU-235 (a warm-page figure quoted for a cold-page AC; a runtime loaded from an
    unread `index.html`; a skipped pre-review that later found nine gaps; a test harness's own script
    taken for the app's long task). *Measure:* which rules apply to a project with no UI (Model B's own
    CLI): rules 1–3 are conditional on a performance or UI criterion. *Re-score:* with item 13 the CR may
    pass 13 points; Rule 23 then splits it before the pre-review.
14. **The gap analysis groups the ACs into behaviour units; the plan files one red-green cycle per unit**
    (Crucible #1552, user-directed 2026-11-08). `orchestration-common.md` already says "One cycle per
    coherent behaviour unit", but no gap-analysis step produces the units. The rule:
    - a unit is one mechanism or path RED can pin and GREEN can make pass on its own; the units are
      listed in dependency order, and every AC belongs to exactly one;
    - each unit lists the existing tests its change breaks (item 11), so their re-seeding is filed with
      it;
    - the plan is filed from the grouping, one red-green cycle per unit, then VERIFY; a single cycle is
      written as "one unit: <why>", never by default; a CR of 8 points or more with more than one unit is
      never filed as one cycle (the pre-review's threshold);
    - RED and GREEN briefs are scoped to their unit: RED writes only its tests, and GREEN runs the earlier
      units' tests as its regression.
    Candidate homes: `gap-analysis`, a step after Dimension 9 and before Rule 23's re-score, with a
    "Cycle units" section in the output format; `orchestration-common.md` § Cycle discipline, at the
    plan-filing step; the RED and GREEN templates. *Measure:* GREEN's regression against DN §D26 (each
    role runs the tests its phase needs) and CR-MDB-083 (phase agents run only their tests): the earlier
    units' tests are the CR's own, named in the brief. Source: Crucible CR-CRU-203 (13 points, 9 ACs, one
    cycle: RED ran 34 minutes and about 944k tokens for 89 failing tests). *Split candidate:* items 9, 11,
    13 and 14 are gap-analysis and design rules, and may form their own CR when Rule 23 splits this one.
