# Contract — Crucible client AXI envelope

**Owner:** CRUCIBLE project (upstream tool provider).
**Status:** DELIVERED — TRACKS CR-CRU-030 + CR-CRU-036, shipped upstream (crucible
develop `949a2f4`; per-delivery intimations thread #1330/#1332). This document MIRRORS
the delivered client contract; it never forks it. Reconciliation on each upstream
delivery is owned by the TRACKS header here plus CR-MDB-011's doc pass.

## Current state

- The envelope is the SHIPPED, fleet-wide current state: every client verb on every
  stack client (`bun-crucible.py`, `python-crucible.py`, `mvn-crucible.py`,
  `rust-crucible.py`, `arduino-crucible.py`) emits it via the shared
  `crucible:clients/_crucible_axi.py`.
- The TOON codec is `crucible:clients/toon.py` (`encode(dict) -> str` /
  `decode(str) -> dict`; strict subset — no delimiter variants, no key-path expansion,
  no inline primitive-array short form). GETs additionally serve compact TOON via
  `?fmt=toon` / `Accept: text/toon`; JSON replies carry `help` hints.

## Required surface

### Envelope (stdout = AXI channel, stderr = human channel)
Every client verb emits exactly one TOON envelope on stdout:

```
{axi: {verb, ok, …result fields…, context, warnings[]}}
```

- `verb` — the client action (`register`, `unregister`, `test`, `regression`,
  `auto-ingest`, `plan-file`, …); `ok` — boolean outcome; result fields are verb-specific
  (e.g. `agent`, `cr`, run summary).
- `context` — `{projectKey, agentId?, cycleId?, wave?, cr?, track?}`. Absent keys are
  OMITTED. `cycleId` is SERVER-RESOLVED (below), never supplied by the caller.
- `warnings[]` — always present, empty when clean.
- The human-readable line is interactive-only and goes to stderr; the machine channel is
  the stdout envelope. Test-run output itself is passed through on stderr.
  `pre-merge-gate` STREAMS its progress.

### Classification context
Runs and plan verbs are classified by the surviving `WORKFLOW_*` env carriers
(DN-model-b-language §2, LOCKED): `WORKFLOW_ROLE` (track), `WORKFLOW_WAVE` (wave),
`WORKFLOW_CYCLE` (cycle label — display). Model B pins these via the per-project context
wrapper (`/tmp/claude-1000/modelb-crucible`). No env var carries a cycle id.

### Server-resolved cycle attach + no-active-cycle withhold (CR-CRU-036)
`context.cycleId` is resolved by the client from the server via
`resolve_attach_cycle` (shared `_crucible_axi.py`): the open plan's single
`status:"active"` cycle is auto-attached. The contract returns
`(cycle_id, warnings, withhold)`:

- plans-fetch failure → `(None, [], False)`: tolerant, the verb PROCEEDS.
- no open plan at all → `(None, [], False)`: tolerant, PROCEEDS unattached.
- open plan with an active cycle → `(id, [], False)`: attaches.
- open plan but NO active cycle → `(None, [no-active-cycle], True)`: the definitive
  WITHHOLD — the client emits `ok:false` with the `no-active-cycle` warning, prints the
  withhold line to stderr, SKIPS the POST (nothing is posted — no orphan ever reaches
  the server) and exits non-zero.

The orchestrator's only cycle input is `cycle-activate`; agents never pass a cycle id.

### Universal plan verbs (fleet-wide)
Filed by the orchestrator, on ALL stack clients:

- `plan-file --cr <id> --title <t> --cycles <n> [--wave <w>] [--orchestrator <id>]`
  — wave resolves `--wave` > `$WORKFLOW_WAVE`; track from `$WORKFLOW_ROLE`; orchestrator
  from `--orchestrator` / `$WORKFLOW_ORCHESTRATOR`. Cycle ids are SERVER-ASSIGNED.
- `cycle-activate` / `cycle-done` — legal transitions planned → active → done.
- `cr-close --commit <sha>` — closes the CR on feature merge.
- `milestone` — workflow timeline events (`gap-analysis | design-review | stage-flip |
  custom`); `cr-merged` fires automatically from cr-close.
- `gate-report` — wave-boundary no-mistakes gate evidence (`kind:"gate"`).

### Agent-naming header (bundled agent-naming skill)
- TDD-phase agents: `CR-<PROJ>-NNN-<cycle>-<PHASE>` (e.g. `CR-MDB-009-C1-GREEN`).
- Orchestrator ops: `<agent-type>-<project>` (Model B solo: `vidushi-mdb`).

## Filed requests / gaps

- CR-CRU-030 + CR-CRU-036 delivery intimated on Sandesh (#1330, #1332); this mirror is
  updated on each intimation (never ahead of it).
- No divergent requests filed: Model B consumes the contract as specified; drift found
  during reconciliation goes upstream as a Crucible CR, not a local fork.

## Non-client adopters

Tools that adopt this envelope convention without being Crucible clients (e.g. `worktree-flow.py`) MAY flatten `context` to a minimal shape (e.g. a flat `project` field) — they perform no run ingestion, so the classification object does not apply. Reconciliation passes must not read this as drift.
