<!--
FROZEN IMPORT — reference copy, not a fork.
Origin: Crucible project, docs/research/DN-model-b-language.md, last changed at origin commit
a9a8f573e3b6577eafe495d5f5cdada6912499c2 (2026-07-16). Imported 2026-09-21 by user ruling so the
LOCKED ontology has a published home inside Model B and no Model B surface needs to read the
Crucible checkout (standing rule 2026-09-18). Crucible remains the owner: any divergence is raised
on the #1336 Sandesh lineage, never edited here. The `crucible:` citations in AGENTS.md and the
PRD resolve to THIS file.
-->

# DN — The Model-B Language: actors, actions, and Crucible

**Author:** Antony John (design review board) · scribed by claude (orchestrator — crucible)
**Date:** 2026-07-15
**Status:** LOCKED — distilled from design-iteration rounds 10–30 (board ledger is the provenance)
**Consumers:** PRD-crucible-v2 §1/§4.11, CR-CRU-007/008/011/012/013/014, the orchestration memory tier

## 0 The model in one sentence

> **Model B is a flow of ACTIONS triggered by ACTORS with specific ROLES.**

Multi-track (parallel) and single-track (sequential) execution differ ONLY in
which actor roles are present and how the actions are scheduled — the model
itself is uniform. (Round 29.)

> **Crucible is a tracking system that works with this Model-B
> code-development workflow.** (Round 30.)

It tracks the actors and their actions, front-ending the whole execution
without ever being an actor in it. MAINLINE ORCHESTRATOR and ORCHESTRATOR are
workflow roles; Crucible never lends its name to workflow concepts —
workflow-state env vars are `WORKFLOW_*`, the `CRUCIBLE_*` prefix is reserved
for the tool's own configuration. (Round 25.)

## 1 Actors and the role hierarchy (rounds 18, 25, 27)

Roles nest by **scope**; authority follows scope. Every level is an agent to
Crucible (registers, heartbeats, carries a runtime, tombstones).

| Role | Scope | Authority (actions it triggers) |
|---|---|---|
| **MAINLINE ORCHESTRATOR** (solo alias: **vidushi**) | the whole project workflow | spawns track orchestrators; allocates CRs to lanes from the depends-on graph; launches waves; files plans (solo mode); runs the no-mistakes gate at wave boundaries |
| **ORCHESTRATOR** (track) | one lane's CR queue | registers its `track` with the CR; files/drives the cycle plan; activates cycles; **confirms** cycles (`done`); closes the CR on merge; enforces workflow rules; verifies agents deliver accurately |
| **RED / GREEN / VERIFY / FIX** | one phase of one cycle | execute and report: test runs, compile/reference failures (any agent may report a compile; RED is the default reporter — TDD), heartbeats, register/unregister |

**Containment ("spawned / classified under"):**
```
Project
└─ Mainline orchestrator            ── special agent: coordinator/manager
   ├─ Track-1..N orchestrator       ── multi-orchestrator Model B (spawned)
   │   └─ CR                        ── always executed WITHIN a track
   │       └─ Cycle                 ── red-green | verify | fix
   │           └─ runs              ── by ⌁ phase agents
   └─ CR (implicit solo track)      ── single-orchestrator: mainline is the only one
```

## 2 The execution vocabulary

| Term | Definition | Locked |
|---|---|---|
| **Cycle** | one step in a CR's execution. Kinds `red-green \| verify \| fix` — ALL under identical rules. Labeled by the orchestrator todo's description (`context.cycle` / plan cycle label). A cycle's span **completes only when the orchestrator confirms** (`done` = GREEN-confirm / report-acceptance / fix-batch-green) — a passing run alone never closes anything. | r10, r15, r16 |
| **CR** | groups cycles; the **vehicle** on the highway. Always executed within a track. **Closes on feature merge** (`closed` + merge commit). | r10, r15, r17 |
| **Track** | a **numbered lane** (Track 1, 2, 3…; wire `track-<n>` = `WORKFLOW_ROLE`). The mainline allocates CRs to lanes from their depends-on graph: independent CRs ride parallel lanes, dependents queue. Transient within a wave — **no dedicated UI surface** (conditional Track level + badges in the lens). | r17, r19, r20 |
| **Wave** | groups CRs; the **synchronization boundary** — all lanes pause when their individual queues complete; the next wave launches after design reviews/corrections. States (INFERRED, no wave-control API): `running → lanes complete · awaiting review → gated → superseded`. | r10, r20, r21 |
| **Plan** | the DECLARED workflow: the orchestrator files its cycle plan (todo list) with Crucible — server-assigned numeric cycle ids, `track`, `wave`, `cr`. Declared-plan-first everywhere, inferred RED→GREEN pairing as fallback; planless projects behave exactly as before (graceful degradation is sacred). `plans.cr` verbatim = the stable join key (roadmap forward-compat). | r14–15, r24 |
| **Gate** | a no-mistakes pipeline run at a wave boundary, ingested as evidence (`kind:"gate"`, codec `no-mistakes`): intent, outcome, step ladder + findings/fix rounds, fixes, pushed commit/PR. A no-mistakes push is categorically distinct from an ordinary push (which never reaches Crucible). | r21 |
| **Milestone** | lightweight workflow event (`gap-analysis \| design-review \| stage-flip \| custom`) — **project workspace timeline only**. | r23–24 |
| **Run** | a test/compile event by a phase agent; links to its cycle via `context.cycleId` (tolerant). | r10, r15 |

**Action taxonomy (everything Crucible tracks is an actor acting):**
registrations/unregistrations (lifecycle events preserve runtimes), heartbeats
(implicit on every call), runs (test/compile), plan verbs (`plan-file`,
`cycle-activate`, `cycle-done`, `cr-close`), milestones, gates
(`gate-report`). Env carriers: `WORKFLOW_ROLE`, `WORKFLOW_WAVE`,
`WORKFLOW_CYCLE`, `WORKFLOW_CYCLE_ID`.

## 3 How Crucible fronts the model (surfaces)

| Concept | Crucible surface |
|---|---|
| Actors + liveness + runtimes | projects row badges (active/inactive, activity-ordered) · workspace Project pane (⌁ nested agents, ticking/sealed runtimes) |
| Cycle / plan (live) | **Workflow tab** live section: per-CR todo view, active cycle = open span collecting runs; no-mistakes gate pane beside it |
| Wave → [Track] → CR → Cycle (history) | Workflow tab history lens; Track level only when a wave spans >1 lane; per-lane completion chips; wave states |
| Runs | home collective timeline (runs only) · workspace timeline (runs + milestones + 🛡 gate boundary cards) |
| Gate detail | drill-in with the axi-mirrored body (step ladder, findings, fixes, outcome) |
| Roadmap (0.2.0) | **Roadmap workspace tab** (user-elevated 2026-07-16; sixth tab — Workflow · Runs · Coverage · Compile · Roadmap · BDD), deep-linked `/p/<key>/roadmap`, Project-pane 🗺 chip as shortcut: Wave → CR table + graph, statuses DERIVED (PENDING = no plan · IN_PROGRESS = open plan · COMPLETED = closed + merge); empty state carries the queue-registration imperative |

Navigation: two routed pages (home L1, workspace L2), the in-pane run detail
(CR-016 pane state, `←` back chip = Esc/back), and one slide-over (/manage,
`←` back chip = Esc/scrim/back). The Roadmap is a workspace TAB (0.2.0).

## 4 Why one data model suffices

A solo vidushi project and a five-track Model-B project are **the same
schema with different actors present**: `track` absent = implicit solo lane
(no UI noise, byte-identical lens output); plans absent = inferred pairing;
context absent = plain run cards. Every degradation is graceful because the
model is uniform (round 29) — the difference is never structural.

## 5 CR mapping (where the language lands in code)

| CR | Carries |
|---|---|
| CR-CRU-007 | shell final form; run cards + inferred markers; `context.cycle` field |
| CR-CRU-011 | plan API (cycles/kinds/track), lifecycle events + runtimes, Workflow tab (live todo + history lens), wave states |
| CR-CRU-008 | fleet verbs: plan-file / cycle-activate / cycle-done / cr-close + `WORKFLOW_*` plumbing |
| CR-CRU-012 | projects manager (add/edit/archive) |
| CR-CRU-013 | workflow events: gates (no-mistakes) + milestones, gate pane, `gated` wave state |
| CR-CRU-014 (0.2.0) | queue registration + Roadmap workspace tab (forward-compat contract binds 0.1.0) |
