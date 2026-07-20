# Contract — Crucible client AXI envelope

**Owner:** CRUCIBLE project (upstream tool provider).
**Status:** TRACKS CR-CRU-030 — ships upstream; per-delivery intimations thread #1322. This
document MIRRORS the incoming client contract; it never forks it. Reconciliation on each
upstream delivery is owned by the TRACKS header here plus CR-MDB-011's doc pass.

## Current state

- TODAY the shipped clients print plain-text one-liners on stdout; TOON lives server-side
  only (GETs serve compact TOON via `?fmt=toon` / `Accept: text/toon`; JSON replies carry
  `help` hints). Consumers must NOT expect stdout envelopes until CR-CRU-030 lands.
- The reference slice already exists in `crucible:clients/bun-crucible.py`: `_emit_axi()`
  writes the TOON envelope to stdout and the optional human line to stderr;
  `_axi_context()` assembles the classification context; `_cycle_id_and_warnings()`
  implements the orphan-signal warning. The TOON codec is `crucible:clients/toon.py`
  (`encode(dict) -> str` / `decode(str) -> dict`; strict subset — no delimiter variants,
  no key-path expansion, no inline primitive-array short form).
- Other stack clients (`python-crucible.py`, `mvn-crucible.py`, `rust-crucible.py`) are
  pre-envelope; they adopt this contract as CR-CRU-030 promotes it.

## Required surface

### Envelope (stdout = AXI channel, stderr = human channel)
Every client verb emits exactly one TOON envelope on stdout:

```
{axi: {verb, ok, …result fields…, context, warnings[]}}
```

- `verb` — the client action (`register`, `unregister`, `test`, `regression`,
  `auto-ingest`, `plan-file`, …); `ok` — boolean outcome; result fields are verb-specific
  (e.g. `agent`, `cr`, run summary).
- `context` — `{projectKey, agentId?, cycleId?, wave?, cr?, track?}`. Absent env keys are
  OMITTED; a supplied `cycleId` of `None` is kept as an EXPLICIT null (the orphan signal),
  paired with a single `no-cycle-id` warning naming the open plan's active cycle.
- `warnings[]` — always present, empty when clean.
- The human-readable ingest line is interactive-only and goes to stderr; the machine
  channel is the stdout envelope. Test-run output itself is passed through on stderr.

### Mandatory classification context
Runs and plan verbs are classified by the `WORKFLOW_*` env carriers (DN-model-b-language
§2, LOCKED): `WORKFLOW_ROLE` (track), `WORKFLOW_WAVE` (wave), `WORKFLOW_CYCLE` (cycle
label), `WORKFLOW_CYCLE_ID` (numeric id → `context.cycleId`, int-coerced, invalid →
omitted). Model B injects these via the per-project context wrapper
(`/tmp/claude-1000/modelb-crucible`) so no run can orphan.

### Unknown-cycleId REFUSAL (their CR-024)
When Crucible CR-024 ships, a run whose `cycleId` is unknown to the plans API is REFUSED
(400) at ingest. Clients must stamp real cycle context; orphaned runs become rejected
runs. The client-side guard (explicit-null + `no-cycle-id` warning) is the transition aid,
not an exemption.

### Universal plan verbs
Filed by the orchestrator (bun client today, promoting to all clients):

- `plan-file --cr <id> --title <t> --cycles <n> [--wave <w>] [--orchestrator <id>]`
  — wave resolves `--wave` > `$WORKFLOW_WAVE`; track from `$WORKFLOW_ROLE`; orchestrator
  from `--orchestrator` / `$WORKFLOW_ORCHESTRATOR`. Cycle ids are SERVER-ASSIGNED.
- `cycle-activate` / `cycle-done` — legal transitions planned → active → done.
- `cr-close --commit <sha>` — closes the CR on feature merge.
- `milestone` — workflow timeline events (`gap-analysis | design-review | stage-flip |
  custom`); `cr-merged` fires automatically from cr-close.
- `gate-report` — wave-boundary no-mistakes gate evidence (`kind:"gate"`).

### Agent-naming header (agent-protocol)
- TDD-phase agents: `CR-<PROJ>-NNN-<cycle>-<PHASE>` (e.g. `CR-MDB-009-C1-GREEN`).
- Orchestrator ops: `<agent-type>-<project>` (Model B solo: `vidushi-mdb`).

## Filed requests / gaps

- Per-delivery intimation of CR-CRU-030 slices requested on Sandesh thread #1322; this
  mirror is updated on each intimation (never ahead of it).
- No divergent requests filed: Model B consumes the contract as specified; drift found
  during reconciliation goes upstream as a Crucible CR, not a local fork.
