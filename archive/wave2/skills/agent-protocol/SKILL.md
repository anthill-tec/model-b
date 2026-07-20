---
name: agent-protocol
description: Standard protocol for AI coding agents working in the Plan B  dev platform Crucible.
 Covers agent registration, liveness through run ingests, identity, and service discovery. Use when an 
 agent starts work on any registered project, connects to platform services, or needs to maintain liveness with Crucible.
---

## Core Principle

Our Agentic environment has a hierachical set of roles

1. Orchestrator: The - **[Orchestration](~/.claude/skills/model-b/references/orchestration-common.md)**  agent responsible for guiding other implementation sub agents 
through a Plan B workflow model
2. Agent: The agent that actually has role specific scope in implementation sequences like RED, GREEN , VERIFY and FIX.
RED and GREEN agents are TDD partners in a Cycle. A cycle is a single sequence between a RED Agent who owns the testing and 
the GREEN agent who implements the SUT (System Under Test). VERIFY agent

**If you're registered with a service, keep it alive by reporting real work.**
For Crucible, ingest is the heartbeat: every run you post (`/api/v2/runs`,
`/api/v2/runs/parsed`, `/api/v2/runs/compile`) touches your agent. A TDD agent
that ingests every RED/GREEN/regression run never needs a dedicated ping.

## Agent Identity

On first contact with any service specifically Crucible, identify yourself from project context. Priority order:

1. **User prompt** - For mainline (Apex) orchestrators, you can prompt user for a name at start of project often defaults to vidushi 
2. **CLAUDE.md** — look for `agent_id` or project name → `source: "claude-md"`
2. **package.json** — `name` field → `source: "package-json"`
3. **git remote / directory name** → `source: "git-repo"`
4. **Manual** — hardcoded or configured → `source: "manual"`

Identity payload (send once inside `identity` on register, preserved across touches):
```json
{
  "agentId": "<unique-id>",
  "displayName": "<human-readable-name>",
  "source": "claude-md|package-json|git-repo|manual",
  "repoPath": "<absolute-path-to-project>"
}
```

**Naming convention:** `<agent-type>-<project-key>` e.g. `vidushi-CFU`, `Vidushi-NAI`

## Liveness Protocol

### How liveness works
- **Register once** at session start (`POST /api/v2/agents/register` — an upsert).
- **During work** — every run ingest counts as the heartbeat; there is nothing
  extra to send.
- **Status change** (idle → busy, busy → idle) — touch
  `POST /api/v2/agents/heartbeat` (same handler as register) with the new
  `status` + `message`. This is the only time a manual touch is warranted.

### When to stop
- Told to unregister
- Work on the project is complete
- Session ending

### Touch Payload (register and heartbeat are the same upsert)
```json
{
  "agentId": "<id>",
  "projectKey": "<key>",
  "status": "online|busy",
  "message": "<what you're doing right now>"
}
```

### Status Values
| Status | Meaning | When to use |
|--------|---------|-------------|
| `online` | Active, available | Default — idle or light work |
| `busy` | Actively executing | Running tests, building, deploying |

### Liveness Thresholds (service-side decay — information, not a ping schedule)
| State | After | Visual |
|-------|-------|--------|
| Online | Run ingested / agent touched | 🟢 Green |
| Stale | 60s no activity | 🟡 Yellow |
| Offline | 300s no activity | ⚪ Grey |
| Removed | 1h offline | Gone |

These describe how the dashboard decays idle agents; they are configurable per
service. Do not build a ping loop around them — a normally-ingesting agent
stays green by doing its job.

## Service Registry

| Service | Port | Agent Endpoint | Purpose |
|---------|------|----------------|---------|
| **Crucible** | 3849 | `POST /api/v2/agents/heartbeat` | Test dashboard |

## Helper Script

Use `scripts/heartbeat.sh` for any service:

```bash
scripts/heartbeat.sh <agent-id> <project-key> [status] [message] [service-url]
```

It targets the Crucible v2 agent touch by default; the touch upserts, so it
also serves as a one-shot registration.

## Workflow

1. **Start of session** → Identify yourself, register with identity
2. **During work** → run ingests ARE the liveness signal; nothing extra to send
3. **Status changes** → update status + message via the agent touch
4. **End of session** → unregister (`POST /api/v2/agents/unregister`); otherwise the service decays you to stale → offline
