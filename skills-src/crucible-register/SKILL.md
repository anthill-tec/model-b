---
name: crucible-register
description: Register agent with Crucible on start, keep liveness through run ingests, unregister on completion.
metadata:
  author: Crucible
  version: 0.1.0
---

# Crucible Register — Agent Lifecycle

Register and unregister are verbs of your stack's installed client,
`~/.crucible/clients/<stack>-crucible.py`. The client reads the project key from
the project's registry and the board from `[client] url` in `crucible.toml` (the
`crucible` skill states the resolution), so no example here names either.

## Register (first action, before any code work)

```bash
python3 ~/.crucible/clients/<stack>-crucible.py register --agent YOUR_AGENT_ID --role RED --cycle YOUR_CYCLE_ID
```

`--role` is REQUIRED and case-exact, one of `RED`, `GREEN`, `FIX`, `VERIFY`,
`ORCHESTRATOR`, `report` — a missing or out-of-enumeration role is rejected 400.
`--cycle` binds the agent to an ACTIVE cycle of an OPEN plan and is REQUIRED by
the server for the four TDD roles (`RED`/`GREEN`/`FIX`/`VERIFY`): an unbound TDD
registration is rejected 409. `ORCHESTRATOR` and `report` may register unbound —
omit `--cycle` entirely for those two:

```bash
python3 ~/.crucible/clients/<stack>-crucible.py register --agent YOUR_AGENT_ID --role ORCHESTRATOR
```

Once bound, the server stamps that cycle onto every run you ingest, so nothing
downstream passes a cycle id again.

The agentId is free-form and assigned by whoever dispatched you; the role is
NEVER inferred from its shape, so an id ending `-GREEN` registered with
`--role RED` classifies as RED.

Registration is an upsert: registering an already-known agent just touches it.

## Liveness — ingest is the heartbeat

There is no dedicated ping loop. Every run you ingest (`/api/v2/runs`,
`/api/v2/runs/parsed`, `/api/v2/runs/compile`) touches your agent and keeps it
live — a working TDD agent ingests far more often than any liveness threshold.
The dashboard decays agents that stop reporting (stale → offline → removed);
those thresholds are information about decay, not an instruction to ping.
If you must update your status between runs (rare), re-run the client's
`register` verb — same upsert semantics. Where your client takes `--message`
(every client but arduino's; see its `register --help`), give a fresh one:

Good: `"RED: 3/5 tests failing"`, `"GREEN: implementing AgentStreamResource"`
Bad: `"working"`, `"in progress"`

## Unregister (last action, on completion)

```bash
python3 ~/.crucible/clients/<stack>-crucible.py unregister --agent YOUR_AGENT_ID
```

The client supplies the project key with the agent id.

## API Endpoint Reference

The endpoints the clients speak, for reference. Read the board with the client's
`status`, `history` and `queue` verbs, not with raw requests. All GET endpoints
also serve compact TOON (`?fmt=toon` or `Accept: text/toon`); JSON responses
carry `help` hints for the next step.

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v2/runs` | POST | Ingest a raw test run (codec + data or dataPath) |
| `/api/v2/runs/parsed` | POST | Ingest pre-parsed results (summary + tree + optional coverage) |
| `/api/v2/runs/compile` | POST | Ingest compile failure (errors string + format) |
| `/api/v2/agents/register` | POST | Register/touch agent (upsert) — the client's `register` |
| `/api/v2/agents/heartbeat` | POST | Same handler as register — rarely needed; ingest is the heartbeat |
| `/api/v2/agents/unregister` | POST | Unregister agent (agentId + projectKey) — the client's `unregister` |
| `/api/v2/agents` | GET | List agents (optional ?project filter) |
| `/api/v2/events` | GET | List events (optional ?project, ?limit) |
| `/api/v2/projects` | GET | List projects |
| `/api/v2/projects` | POST | Create a project (name) |
