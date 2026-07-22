---
name: crucible
description: One skill for the whole Crucible test-reporting lifecycle, any stack — register → ingest every run → unregister via the per-stack `<stack>-crucible.py` client, which runs the tests AND ingests under your agent id. Covers the true per-stack client surfaces, workflow/cycle context, plan verbs, and who-runs-what (agent vs orchestrator). Use for every RED/GREEN/VERIFY/regression run and for agent lifecycle.
---

# Crucible — agent lifecycle + test ingest

Crucible (`localhost:3849`) is the test-outcome and Model B workflow reporting
and tracking dashboard. The LIFECYCLE is universal — register first, ingest
every run, unregister last — but the VERB SURFACE differs per stack: read your
stack's reference file before running anything. The client runs the tests AND
ingests in one call under your agent id. Never hand-roll `curl`; the client
(or, on a clientless stack, the documented urllib procedure) is the interface.

## Lifecycle (every agent)

- `register --agent <id> --phase <PHASE>` FIRST — before reading or running
  anything. Registering IS the heartbeat: register/touch is one upsert, every
  run ingest touches your agent, and there is NO separate heartbeat endpoint,
  ping loop, or helper script. A normally-ingesting agent stays green by
  doing its job; re-run `register` only on a genuine status change.
- Ingest EVERY run — RED and GREEN separately (Crucible must show the
  RED→GREEN transition); compile/import failures route to the compile panel;
  coverage ONLY on a full-green regression, in the same parsed payload.
- `unregister --agent <id>` LAST — skipping it leaves a ghost agent.
  **Unregister a run before you kill it, or it ghosts.**

## Identity — ONE agent id for the whole session

- Orchestrators: `<agent-type>-<project>` (e.g. `vidushi-NAI`, `mainline-MDB`).
- TDD-phase agents: `CR-<ACRONYM>-NNN-<cycle>-<PHASE>` (e.g.
  `CR-MDB-003-C1-GREEN`) — the CR id + cycle + phase IS the identity.
- Phase is metadata, not identity: pass it via `--phase` on register. Never
  mint a second agent id mid-session.

## Per-stack client surfaces (they are NOT uniform — read the reference)

| Stack | Client | Key verbs beyond register/unregister | Reference |
|-------|--------|--------------------------------------|-----------|
| rust | `rust-crucible.py` | `test --crate`, `check --crate`, `auto-ingest`, `regression-ingest --crates`, `workspace-regression`, `clippy`/`workspace-clippy`, `smoke-test`, `docker-up/down`, `pre-merge-gate`, `docker-e2e-gate` + the plan verbs | `references/rust.md` → bundled `crucible-report-rust` |
| java | `mvn-crucible.py` | `unit --test <Class> [--module <m>]`, `module`, `compile`, `e2e`, `regression`, `auto-ingest`, `docker-up/down`, `pre-merge-gate` + the plan verbs | `references/java.md` → bundled `crucible-report-java` |
| bun | `bun-crucible.py` | universal verbs (`test --tests <file>`, `regression [--coverage]`, `check`, `auto-ingest`, `pre-merge-gate`) + the plan verbs — **REFERENCE IMPLEMENTATION** for the V2 client API | `references/bun.md` → bundled `crucible-report-bun` |
| python | `python-crucible.py` | `test --tests <dotted.path>`, `regression [--coverage --cov-source]`, `check`, `auto-ingest`, `pre-merge-gate` + the plan verbs | `references/python.md` → bundled `crucible-report-python` |
| arduino | `arduino-crucible.py` | `test`/`unit` (native host make junit), `regression`, `auto-ingest`, `check`/`compile` (arduino-cli), `pre-merge-gate` + the plan verbs | bundled-docs route note below (no local reference file) |
| vscode | NO client yet | interim inline urllib ingest, documented as-is; the future client is CRUCIBLE's deliverable (thread #1322) | `references/vscode.md` → bundled `crucible-report-vscode` |
| electronics/hardware | excluded — under revision | — | — |

Clients live in the CRUCIBLE project's own `clients/` directory —
`~/Documents/data_projects/crucible/clients/<stack>-crucible.py` — the source
of truth Crucible owns, tests, and fixes; run any client with `-h` for its own
help. A project-vendored `clients/<stack>-crucible.py` copy is valid ONLY
while a CR in that project is changing the client itself. Any other deployed
placement arrives only with Crucible's own installer.

## Bundled per-stack docs — the authority (routing note)

The per-stack skill docs are BUNDLED with the clients at
`crucible:clients/skills/crucible-report-*/`
(`~/Documents/data_projects/crucible/clients/skills/`). They are the per-stack
AUTHORITY — managed and updated by Crucible with the **CR-CRU-030** client
contract they document; deployed placement arrives with Crucible's own
installer (invoked by the Model B universal installer). The local
`references/*.md` files are THIN ROUTERS: Model B workflow deltas only, then
route to the bundle.

## Workflow classification — server-driven cycle attach + display context

Cycle attach is SERVER-DRIVEN (CR-CRU-036): every run/plan verb reads the
open plan and auto-attaches to its single `status:"active"` cycle
(`resolve_attach_cycle` in shared `_crucible_axi.py`). No env var carries a
cycle id — clients resolve it from the server.

- OPEN plan but NO active cycle → the client emits the `no-active-cycle`
  warning and WITHHOLDS the run: `ok:false`, non-zero exit, nothing posted
  (no orphan ever reaches the server).
- No open plan at all, or a plans-fetch hiccup → tolerant: the run proceeds
  unattached, no warning, no withhold.
- The orchestrator's ONLY cycle input is `cycle-activate` (one active cycle
  at a time); agents never pass a cycle id.

Display/classification context survives as env vars:

| Env var | Meaning |
|---------|---------|
| `WORKFLOW_CYCLE` | Cycle label string → `context.cycle` (display) |
| `WORKFLOW_WAVE` | Wave number |
| `WORKFLOW_ROLE` | Role / track label |

- **Per-project wrapper pattern:** projects ship a context wrapper (e.g.
  `/tmp/claude-1000/<project>-crucible`) that pins the project key/dir and the
  `WORKFLOW_CYCLE` label + `WORKFLOW_WAVE` only — it never injects a cycle id
  (attach is server-driven). When your prompt names a wrapper, use it.
- **Plan verbs (universal — fleet-wide on all five clients):**
  `plan-file --cr <id> --title <t> --cycles <n> [--wave <w>] [--orchestrator <id>]`,
  `cycle-activate` / `cycle-done` (legal transitions planned → active → done),
  `cr-close --commit <sha>`, `milestone`, `gate-report`.

## Envelope — TOON-AXI on stdout (shipped fleet-wide)

The client contract shipped via Crucible **CR-CRU-030**: every client verb
emits exactly one TOON envelope on stdout — `{axi:{verb, ok, …result fields…,
context, warnings[]}}` — through the shared `_crucible_axi.py`. The human
line AND the test output go to stderr; `warnings[]` is always present (empty
when clean); `pre-merge-gate` STREAMS its progress. Parse stdout as the
machine channel. GETs also serve compact TOON (`?fmt=toon` /
`Accept: text/toon`), and JSON replies carry `help` hints — read them; they
name the next step.

## Who runs what (roles — the boundary the output can't tell you)

- **RED / GREEN / FIX agents** — run ONLY their TARGETED tests (`test`/`unit`
  scoped to their SUT), FOREGROUND (400000 ms timeout); never the full suite,
  never `run_in_background` / Monitor. RED ingests the failing run (a compile
  failure IS a RED); GREEN ingests the passing run.
- **VERIFY agent** — registers + REVIEWS (ACs, wiring, coverage adequacy,
  quality). Does NOT run the regression.
- **ORCHESTRATOR** — runs the close-out gate itself: `regression` (with
  coverage) PLUS the e2e suite, under its OWN identity, with the verify cycle
  activated (`cycle-activate`) so the gate attaches as that cycle's LAST
  linked run — then the user-gated merge. (sub-agent procedure —
  `~/.claude/skills/model-b/references/sub-agent-procedure.md` — TDD step 6:
  the full suite is orchestrator-owned.)
