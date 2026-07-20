# CR-MDB-009 — contracts/: the AXI evolution interface

**Status:** PENDING
**Type:** docs
**Priority:** P1 (unblocks 010; anchors 011)
**Depends on:** —
**Labels:** contracts, axi
**Phase:** Wave 3
**Design reference:** `docs/research/PRD-model-b-rationalization.md` §D7 (envelope contract), §D8 (collaboration model — contracts only) · Sandesh threads #1322/#1326/#1328 · `docs/research/DN-harness-agnostic-hooks.md` (protocol precedent)

## Context

PRD §D8 commits this project to shipping AXI CLI **contracts** — the evolution interface between Model B and its upstream tool providers — without implementing them. `contracts/` holds only `.gitkeep`. Four contracts are due; each states owner, current state, required surface, and the requests already filed with the owner.

## Scope

### §S1 — AC gate tests
`tests/test_contracts.py`, wrapper-run (cycle context), RED → GREEN. Repo-only CR — no `~/.claude` writes, no chezmoi ops.

### §S2 — `contracts/crucible-envelope.md`
Owner: CRUCIBLE. Mirrors the incoming CR-CRU-030 client contract (never forks it): the `{axi:{verb,ok,…,context,warnings[]}}` stdout envelope + stderr human line; MANDATORY classification context (`wave`, `cycleId`, `cr`, `track` via `WORKFLOW_*`); the unknown-cycleId REFUSAL (400) rule (their CR-024); universal plan verbs (`plan-file --wave --orchestrator`, `cycle-activate`, `cycle-done`, `cr-close`, `milestone`, `gate-report`); agent-naming header (`CR-<PROJ>-NNN-<cycle>-<PHASE>` phase agents / orchestrator id). Status header: "TRACKS CR-CRU-030 — ships upstream; per-delivery intimations thread #1322".

### §S3 — `contracts/sandesh-cli.md`
Owner: SANDESH project. Required CLI surface replacing the MCP-only message verbs: send/reply/fetch/inbox/addressbook/register/unregister (wake `notify` + admin `grant/revoke/tombstone/archive` are already CLI). PLUS the defect/gap register found while dogfooding: (a) space-named project zombie (setup accepts ids the address grammar rejects → unarchivable/untombstonable; fix S1 validate-at-setup + S2 admin tombstone of zero-address projects, tolerant of missing store dirs — the full AC'd request drafted 2026-07-20); (b) no display-name update path for an active address; (c) `init --check` prints the admin name to any local caller (harden). Routing note: files with the SANDESH project when its mainline registers.

### §S4 — `contracts/mail-axi.md`
Owner: TBD (new tool). Required surface consolidating the mail MCP dependencies (consumers: `mail-tracking-core` + 6 downstream skills + `inbox-analyst`): Fastmail search/read/folders, Gmail threads/labels, Calendar event creation — as an AXI CLI (TOON output, combined operations, non-interactive), enabling the D8 migration off `mcp__FastmailMCP__*` / `mcp__claude_ai_Gmail__*` / Calendar MCP.

### §S5 — `contracts/lean-ctx.md`
Owner: LEAN-CTX project. CLI-preference contract (already dual MCP/CLI): document the preference order, plus operational findings filed: shell-allowlist friction for project tooling (blocked `chezmoi`, blocked project wrappers — additive allow flow), the file-write redirect block interplay with orchestration scripts.

## Acceptance criteria

### §S1
- [ ] `tests/test_contracts.py` exists; RED then GREEN ingested with wave-3 cycle context.

### §S2
- [ ] `contracts/crucible-envelope.md` exists; contains `{axi:` and `warnings[]` and `WORKFLOW_` and "REFUSED" or "400" and `plan-file` and `CR-CRU-030` and the phase-agent id form `CR-<PROJ>-NNN-<cycle>-<PHASE>`; contains "TRACKS" (ownership status header).

### §S3
- [ ] `contracts/sandesh-cli.md` exists; contains all seven message verbs (`send`, `reply`, `fetch`, `inbox`, `addressbook`, `register`, `unregister`), "zombie" (defect a), "display" (gap b), "admin name" (gap c), and "SANDESH" ownership.

### §S4
- [ ] `contracts/mail-axi.md` exists; contains "Fastmail" AND "Gmail" AND "Calendar" AND "mail-tracking-core" AND "TOON".

### §S5
- [ ] `contracts/lean-ctx.md` exists; contains "allowlist" and "dual" (or "MCP + CLI").

## Estimated size
S–M (pure authoring; all source material verified in-session).

## Risk
- The crucible-envelope mirror must not drift from CR-CRU-030 when it ships — the TRACKS header + 011's doc pass own reconciliation.

## Non-goals
- Any implementation of the four surfaces (owners implement; PRD §D8).
- Sending the sandesh register to anyone (routing waits for the Sandesh project's mainline; user routes).
