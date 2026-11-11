# CR-MDB-105 — The policy allows SoL-Pi's tools, codemode and Pi's own MCP tools

**Status:** PENDING — **SEED, not the finished spec** (filed 2026-11-11 by the user's rulings,
DN-multi-harness-deploy-model §D27, the second 2026-11-11 ruling). Gap analysis and the spec happen in order
when this CR starts. Pre-review: due (the user's rulings were needed).
**Type:** feature (the generated permission policy)
**Priority:** P1 — release 1.0.0, wave 2, right after CR-MDB-095 (user 2026-11-11; board-authoritative: read
`queue`).
**Depends on:** none on the board; placed after CR-MDB-095, which changes the same policy.
**Labels:** permission-policy, pi, sol-pi, mcp, codemode
**Design reference:** DN-multi-harness-deploy-model §D27 (this CR's ruling), §D24 (tools from requirement
rows), §D28 (SoL-Pi); CR-MDB-095 §S1 (the workflow tools and pi-lens); CR-MDB-098 item 3 (moved here);
CR-MDB-102 (the eda stack's own MCP servers).

## Context

Model B's generated policy (`modelb_axi/permission_policy.py`, rendered into a project's
`.pi/extensions/pi-permission-system/config.json`) has `"*": "ask"` and allows the workflow tools by name.
Tools that every Model B session now uses are missing from it, so they prompt:

- **SoL-Pi** (a Model B prerequisite, §D28; 0.1.0 published 2026-11-11) registers `update_plan` and
  `obs_recall`. Its `edit` and `write` replace Pi's own and keep their existing entries. CR-MDB-098 item 3
  allowed the two tools; the user moved that here so they land in 1.0.0.
- **Pi 1.5.2's `codemode`** runs a script that calls other tools. Pi's MCP documentation says each call a
  script makes passes through the tool pipeline, permission gates included (`docs/mcp.md` § Permissions),
  with the codemode call's id as `parentToolCallId`.
- **Pi 1.5.2's built-in MCP** reads `~/.pi/agent/mcp.json` and a trusted project's `.pi/mcp.json`. It adds
  `tool_search` (for a server with `deferred` exposure) and the resource tools `list_mcp_resources`,
  `list_mcp_resource_templates` and `read_mcp_resource`. A server's own tools are named
  `mcp__<server>__<tool>` and may write. (pi-mcp-extension, which replaced the built-in support, is removed.)

## Scope (seed)

1. **The policy allows `update_plan` and `obs_recall`,** taken from the `sol-pi` requirement row as other
   tools are taken from theirs (§D24), or fixed where the row does not exist yet. Which, is measured.
2. **The policy allows `codemode`,** and a nested call is still checked against the policy: a tool the
   policy asks for, called from a script, still asks (or is refused where nobody can answer). Gap analysis
   measures this under pi-permission-system before RED; if it does not hold, the orchestrator reports it to
   the user before GREEN.
3. **The policy allows `tool_search`, `list_mcp_resources`, `list_mcp_resource_templates` and
   `read_mcp_resource`.**
4. **A server's own tools (`mcp__<server>__*`) stay on ask** — no entry. An eda project's own servers are
   CR-MDB-102's (§D27, 2026-11-11).
5. **CR-MDB-098 item 3 points here;** its `edit`/`write` statement stays there.
6. **The guards that pin the policy move with it** (`tests/test_project_permission_policy.py`, the agents
   verb's policy test, Model B's own rendered policy).

## Non-goals

- pi-add-dir's and pi-studio's tools (user 2026-11-11: not required).
- The user's global policy (§D27, CR-MDB-038 §S3).

## To measure at gap analysis

- Whether pi-permission-system checks codemode's nested calls, and how a refusal surfaces in a script.
- How `codemode` and `tool_search` are named in the gate (a built-in, not an extension tool).
- The re-score (5 points filed) and the behaviour units.
