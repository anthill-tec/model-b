# CR-MDB-010 — worktree-flow.py AXI output

**Status:** COMPLETED (shipped 2026-07-21 on develop)
**Type:** feature
**Priority:** P1
**Depends on:** CR-MDB-009
**Labels:** axi, scripts, worktree-flow
**Phase:** Wave 3
**Design reference:** `contracts/crucible-envelope.md` (the envelope + stdout/stderr convention — worktree-flow ADOPTS it; the codec's source of truth is `crucible:clients/toon.py`) · PRD §D7 (worktree-flow migrates to AXI output)

## Context

`worktree-flow.py` (10 verbs, print-based) is Model B's lane/worktree tool. Per PRD §D7 it adopts the AXI output convention: TOON envelope on stdout, human lines on stderr — same shape the crucible clients converge on. The codec deploys to `~/.claude/scripts/` as a copy of the source-of-truth `crucible:clients/toon.py` (the existing repo→deployed-copy pattern), with a TRACKS header.

## Scope

### §S1 — AC gate tests
`tests/test_worktree_flow_axi.py`, wrapper-run (cycle context), RED → GREEN. Tests invoke the DEPLOYED script read-only against THIS repo (`--project-dir <repo>`): `status`, `next`, `progress` (safe verbs), asserting stdout parses as a TOON envelope and human output moved to stderr. No mutating verbs in tests.

### §S2 — codec deployment
Copy `crucible:clients/toon.py` → `~/.claude/scripts/toon.py` unchanged except a 3-line header: "DEPLOYED COPY — source of truth crucible:clients/toon.py (TRACKS Crucible); do not edit here." (chezmoi add + source commit.)

### §S3 — envelope emission
`worktree-flow.py` gains an `_emit_axi(verb, ok, payload, warnings, help_lines)` emitter (imports the deployed `toon`): stdout = `{axi:{verb, ok, project, <verb payload>, warnings[], help[]}}` TOON; human rendering → stderr. Converted verbs: `status` (worktree board + changeset lane board as structured tables), `next` (`{track, decision: NEXT|HOLD|DRAINED, cr}`), `finish` (result + next-line as help), `progress`. Remaining verbs (`start`, `sync`, `abort`, `cs`, `show`, `reconcile`) keep current output this CR (follow-up when the fleet ships — noted in the contract).
Exit codes unchanged. `--dry-run` paths emit the envelope with `dry_run: true`.

### §S4 — consumer notes
**Surfaces (gap-analysis at execution):** grep `~/.claude/skills/` for worktree-flow output parsing (`status-report`, `bootstrap`, `code-health` mention the board): add a one-line note to each that stdout is now a TOON envelope and the human board is on stderr. chezmoi add touched skills.

## Acceptance criteria

### §S1
- [ ] `tests/test_worktree_flow_axi.py` exists; RED then GREEN ingested with wave-3 cycle context.

### §S2
- [ ] `~/.claude/scripts/toon.py` exists; contains "DEPLOYED COPY" and "TRACKS"; `python3 -c "import sys; sys.path.insert(0,'<home>/.claude/scripts'); import toon"` succeeds.

### §S3
- [ ] `worktree-flow.py status --project-dir <repo>` stdout decodes via the toon codec to an object whose `axi.verb == "status"` and `axi.ok is True`; stderr is non-empty (human board).
- [ ] `next --track` (no DB row → `DRAINED` for an unknown track) stdout envelope has `axi.verb == "next"` and a `decision` field.
- [ ] `progress` stdout envelope has `axi.verb == "progress"`.
- [ ] Envelope contains `warnings` as a list (possibly empty) on all three verbs.

### §S4
- [ ] `grep -l "worktree-flow" ~/.claude/skills/*/SKILL.md` files each contain "stderr" or "TOON" within 2 lines of their worktree-flow output mention (the added note).

## Estimated size
M (one script, three verbs converted + codec deployment).

## Risk
- Consumers parsing stdout text break — mitigated: human output preserved verbatim on stderr; skills get notes (§S4); the orchestrators re-read skills at session start.
- Codec drift — the deployed copy TRACKS upstream; 011's reconciliation pass re-checks.

## Non-goals
- Converting the six remaining verbs (follow-up rides the fleet delivery).
- Any `*-crucible.py` client change (Crucible's).

## Implementation Notes
- 2026-07-21 (GREEN design choice, VERIFY-ratified): the no-schedule-DB path of `next`/`progress` changed from hard `sys.exit` to a graceful envelope (`DRAINED` / empty rows, warning "schedule_db unavailable — queue-only project", exit 0) — the ontology's graceful-degradation principle applied; `cs` keeps its error path (unconverted scope).
