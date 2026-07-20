# Contract — mail-axi consolidated mail CLI

**Owner:** TBD — a NEW tool; no upstream project owns this surface yet. This contract is
the requirements statement that seeds it (PRD §D8 evolution interface; enables the D8
migration off the mail MCP servers).

## Current state

- Mail work runs on THREE separate MCP dependencies, observed in
  `~/.claude/skills/mail-tracking-core/SKILL.md`:
  - Fastmail: `mcp__FastmailMCP__search_email`, `mcp__FastmailMCP__read_email`,
    `mcp__FastmailMCP__list_folders` (+ `create_event` for calendar reminders on the
    default calendar `C0F`, timeZone Asia/Kolkata);
  - Gmail: `mcp__claude_ai_Gmail__search_threads`, `mcp__claude_ai_Gmail__get_thread`,
    `mcp__claude_ai_Gmail__list_labels`;
  - Calendar event creation rides the Fastmail MCP today (Google Calendar MCP tools also
    exist in the harness).
- Every operation is a separate MCP round-trip; tool schemas are deferred and must be
  ToolSearch-loaded per session; output is verbose JSON; no combined cross-mailbox
  operation exists — the dual-mailbox merge is done by the consuming skill each time.

## Required surface

A single consolidated AXI CLI — **TOON output** on stdout (compact, machine-parseable),
**combined operations**, **non-interactive** (no prompts; credentials from config/env,
never arguments) — covering:

- **Fastmail**: search (query + folder + date-window), read (message by id, safe text
  extraction), folders (list, including "Shipping" / "Purchases" / "Subscriptions").
- **Gmail**: thread search, thread read, label listing/filtering.
- **Calendar**: event creation (reminder-style: title, date/time, timezone, description)
  on a named default calendar.
- **Combined ops**: one invocation searching BOTH mailboxes and returning a merged,
  deduplicated, date-sorted result set — the operation every consumer currently
  hand-assembles from per-provider calls.

Read-only on mail except calendar-event creation; no send/delete/move verbs in v1.

## Consumers (who this migrates)

- `mail-tracking-core` (the shared conventions skill) plus its 6 downstream skills:
  `subscription-watch`, `purchase-tracker`, `invoice-tracker`, `warranty-tracker`,
  `support-case-manager`, `product-catalogue`;
- the `inbox-analyst` agent (heavy read-only dual-mailbox sweeps).

All currently call `mcp__FastmailMCP__*` / `mcp__claude_ai_Gmail__*` / Calendar MCP
directly; this CLI replaces those bindings without changing skill semantics.

## Filed requests / gaps

- None filed — no owner exists to file with. First action when an owner is designated:
  hand over this contract as the v1 requirements baseline.
