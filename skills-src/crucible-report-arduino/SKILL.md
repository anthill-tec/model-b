---
name: crucible-report-arduino
description: Ingest Arduino-firmware test results (native host g++ JUnit XML) and arduino-cli compile failures to Crucible. Use after every native firmware test run — RED, GREEN, or regression.
metadata:
  author: Crucible
  version: 0.1.0
---

# Crucible Report — Arduino firmware

`clients/arduino-crucible.py` is the CLI client — it runs the native host tests
(`make junit`) AND ingests to the Crucible v2 API in one call under your agent
id. Direct `curl`/`fetch` against the v2 endpoints is the fallback for edge
cases only.

> **MANDATORY for RED/GREEN/regression cycle runs:** run the tests **through
> the client** (`test`/`unit` for a targeted cycle, `regression` for the gate).
> Do NOT invoke `make junit` directly for a cycle run and then hand-ingest.

## Workflow context (env convention)

The client stamps every ingest with a `tier` (`unit` for targeted runs,
`regression` for the gate) and forwards workflow context read from the
environment — set these on every call so runs land on the right cycle:

| Env var | Meaning |
|---------|---------|
| `WORKFLOW_CYCLE` | Cycle label string → `context.cycle` |
| `WORKFLOW_WAVE` | Optional wave number |
| `WORKFLOW_ROLE` | Optional role/track label |

## Arduino firmware

### Lifecycle

```bash
python3 clients/arduino-crucible.py register --agent AGENT_ID --phase RED
# ... work ...
python3 clients/arduino-crucible.py unregister --agent AGENT_ID
```

### Targeted Run (RED or GREEN — no coverage; tier: unit)

```bash
WORKFLOW_CYCLE="my cycle label" \
python3 clients/arduino-crucible.py test --agent AGENT_ID
```

Runs the native host suite (`make junit`), parses the JUnit XML, and POSTs
`/api/v2/runs/parsed` (or `/api/v2/runs/compile` when the suite fails to build).
Use `--dir tests/native-mock` to target the ArduinoFake L2 tier instead of the
default `tests/native`.

### Regression Run (full native suite; tier: regression)

```bash
WORKFLOW_CYCLE="my cycle label" \
python3 clients/arduino-crucible.py regression --coverage --agent AGENT_ID
```

The server discards coverage on failing runs.

### Compile gate (arduino-cli)

```bash
python3 clients/arduino-crucible.py check --agent AGENT_ID    # arduino-cli compile → /api/v2/runs/compile on failure
python3 clients/arduino-crucible.py auto-ingest --agent AGENT_ID  # ingest a PRE-EXISTING native reports dir
```

### Pre-merge gate

```bash
python3 clients/arduino-crucible.py pre-merge-gate --agent AGENT_ID  # fail-fast compile → regression --coverage
```

## Rules

- **Never skip ingest** — every test run (RED, GREEN, regression) gets reported
- **Ingest RED and GREEN separately** — Crucible must show the RED→GREEN transition
- **Compile failures get ingested too** — `arduino-cli` compile → `/api/v2/runs/compile`
- **Coverage ONLY on full green regression** — targeted/partial/failing runs produce misleading coverage; the server discards coverage on failing runs
- **Always register before first ingest, unregister when done** — both require `agentId` + `projectKey`
- **Native tests cover PURE modules only** — hardware modules go to the ArduinoFake (`tests/native-mock`) or HIL tiers
- **Read error responses and `help` hints** — they tell you exactly what's wrong and what to do next

## Placeholders

| Placeholder | Meaning | Example |
|-------------|---------|---------|
| `AGENT_ID` | Your agent ID from the prompt | `CR-SH-012-RED` |
