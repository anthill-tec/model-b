#!/bin/bash
# Universal agent heartbeat for any MDX platform service (Crucible v2 API).
# Usage: heartbeat.sh <agent-id> <project-key> [status] [message] [service-url]
#
# Examples:
#   heartbeat.sh vidushi codeforge-ui                              # Crucible (default)
#   heartbeat.sh vidushi codeforge-ui busy "Running BDD tests"     # Crucible, busy
#   heartbeat.sh vidushi codeforge-ui online "Idle" http://localhost:3849
#
# The v2 heartbeat upserts: an unknown agent is registered on first touch
# (POST /api/v2/agents/heartbeat shares its handler with /api/v2/agents/register).
# Prefer ingesting runs over pinging — ingest is the heartbeat; this script is
# for the rare long gap with no runs to report.
#
# Silent on failure — never blocks agent work.

AGENT_ID="${1:?Usage: heartbeat.sh <agent-id> <project-key> [status] [message] [service-url]}"
PROJECT_KEY="${2:?Usage: heartbeat.sh <agent-id> <project-key> [status] [message] [service-url]}"
STATUS="${3:-online}"
MESSAGE="${4:-Heartbeat}"
SERVICE_URL="${5:-http://localhost:3849}"

curl -sf -X POST "$SERVICE_URL/api/v2/agents/heartbeat" \
  -H 'Content-Type: application/json' \
  -d "{\"agentId\":\"$AGENT_ID\",\"projectKey\":\"$PROJECT_KEY\",\"status\":\"$STATUS\",\"message\":\"$MESSAGE\"}" \
  > /dev/null 2>&1 || true
