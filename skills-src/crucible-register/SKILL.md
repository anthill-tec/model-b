---
name: crucible-register
description: Register agent with Crucible on start, keep liveness through run ingests, unregister on completion.
metadata:
  author: Crucible
  version: 0.1.0
---

# Crucible Register — Agent Lifecycle

## Register (first action, before any code work)

```bash
curl -s -X POST http://localhost:3849/api/v2/agents/register \
  -H 'Content-Type: application/json' \
  -d '{"agentId":"YOUR_AGENT_ID","projectKey":"YOUR_PROJECT_KEY","role":"RED","cycleId":"YOUR_CYCLE_ID","status":"online","message":"Starting: TASK_DESCRIPTION","identity":{"displayName":"YOUR_DISPLAY_NAME","source":"claude-md"}}'
```

`role` is REQUIRED and case-exact, one of `RED`, `GREEN`, `FIX`, `VERIFY`,
`ORCHESTRATOR`, `report` — a missing or out-of-enumeration role is rejected 400.
`cycleId` binds the agent to an ACTIVE cycle of an OPEN plan and is REQUIRED by
the server for the four TDD roles (`RED`/`GREEN`/`FIX`/`VERIFY`): an unbound TDD
registration is rejected 409. `ORCHESTRATOR` and `report` may register unbound —
omit `cycleId` entirely for those two. Once bound, the server stamps that cycle
onto every run you ingest, so nothing downstream passes a cycle id again.

The agentId is free-form and assigned by whoever dispatched you; the role is
NEVER inferred from its shape, so an id ending `-GREEN` registered with
`"role":"RED"` classifies as RED.

`displayName` and `source` go inside the `identity` object — top-level values are
ignored. Registration is an upsert: registering an already-known agent just
touches it.

## Liveness — ingest is the heartbeat

There is no dedicated ping loop. Every run you ingest (`/api/v2/runs`,
`/api/v2/runs/parsed`, `/api/v2/runs/compile`) touches your agent and keeps it
live — a working TDD agent ingests far more often than any liveness threshold.
The dashboard decays agents that stop reporting (stale → offline → removed);
those thresholds are information about decay, not an instruction to ping.
If you must update your status message between runs (rare), POST the register
payload again with a fresh `message` — same endpoint, same upsert semantics:

Good: `"RED: 3/5 tests failing"`, `"GREEN: implementing AgentStreamResource"`
Bad: `"working"`, `"in progress"`

## Unregister (last action, on completion)

```bash
curl -s -X POST http://localhost:3849/api/v2/agents/unregister \
  -H 'Content-Type: application/json' \
  -d '{"agentId":"YOUR_AGENT_ID","projectKey":"YOUR_PROJECT_KEY"}'
```

Requires BOTH `agentId` and `projectKey`.

## API Endpoint Reference

All GET endpoints also serve compact TOON (`?fmt=toon` or `Accept: text/toon`)
for cheap agent reads; JSON responses carry `help` hints for the next step.

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v2/runs` | POST | Ingest a raw test run (codec + data or dataPath) |
| `/api/v2/runs/parsed` | POST | Ingest pre-parsed results (summary + tree + optional coverage) |
| `/api/v2/runs/compile` | POST | Ingest compile failure (errors string + format) |
| `/api/v2/agents/register` | POST | Register/touch agent (upsert) |
| `/api/v2/agents/heartbeat` | POST | Same handler as register — rarely needed; ingest is the heartbeat |
| `/api/v2/agents/unregister` | POST | Unregister agent (requires agentId + projectKey) |
| `/api/v2/agents` | GET | List agents (optional ?project filter) |
| `/api/v2/events` | GET | List events (optional ?project, ?limit) |
| `/api/v2/projects` | GET | List projects |
| `/api/v2/projects` | POST | Create a project (name) |
