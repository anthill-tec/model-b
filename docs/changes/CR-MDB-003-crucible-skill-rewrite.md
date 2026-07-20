# CR-MDB-003 — crucible skill rewrite: real surfaces, absorb report skills + agent-protocol

**Status:** PENDING
**Type:** feature
**Priority:** P1
**Depends on:** CR-MDB-001
**Labels:** skills, crucible, memory
**Phase:** Wave 2
**Design reference:** `docs/research/PRD-model-b-rationalization.md` §D4, §D7 · `audits/2026-07-20-crucible-drift.md` (verified surfaces) · Crucible thread #1322/#1326/#1328 (client-work ownership + incoming contracts)

## Context

The `crucible` skill promises a client-side TOON-AXI envelope no client emits, documents a phantom `/api/v2/agents/heartbeat` endpoint, and claims universal verbs the clients don't share. Five per-stack `crucible-report-*` skills and the `agent-protocol` skill duplicate its territory; `memory/crucible-ingest.md` is a subsumed stub. This CR makes the skill match reality and become the single Crucible-lifecycle home.

## Scope

### §S1 — AC gate tests
`tests/test_crucible_skill.py`, run + ingested via the context wrapper; RED → GREEN.

### §S2 — SKILL.md rewrite
1. Lifecycle: register-first / ingest-every-run / unregister-last; **heartbeat IS the register verb** (no separate endpoint); agentId standard `<agent-type>-<project>`, ONE identity, phase via `--phase`.
2. TRUE per-stack client surfaces (from the drift audit, re-verified at gap-analysis): rust (`test --crate`, `regression-ingest --crates`, `workspace-regression`, clippy/smoke/docker gates), java/mvn (`unit --test/--module`, `module`, `compile`, `e2e`, `regression`), bun (universal verbs + plan verbs — REFERENCE IMPLEMENTATION), python (`test --tests` dotted, `regression --coverage`, `check`), vscode (NO client yet — interim inline ingest documented as-is; future client is CRUCIBLE's deliverable, thread #1322). Electronics: excluded/under revision (one line).
3. Workflow classification: `WORKFLOW_CYCLE_ID/CYCLE/WAVE/ROLE` context on EVERY ingest; the per-project wrapper pattern; plan verbs (`plan-file --cr --title --cycles --wave --orchestrator`, `cycle-activate/done` legal transitions, `cr-close --commit`); INCOMING contract: unknown-cycleId runs will be REFUSED (400) when Crucible CR-024 ships.
4. Envelope: server-side TOON today (`?fmt=toon`); the client `{axi:{verb,ok,…,context,warnings[]}}` stdout envelope is the CONTRACT that ships via Crucible CR-CRU-030 — documented as INCOMING, not current.
5. Who-runs-what (agent vs orchestrator) retained.

### §S3 — references/ per stack
`references/{rust,java,bun,python,vscode}.md` absorbing each `crucible-report-*` skill's still-true content, corrected against the audit (e.g. rust's undocumented gates, bun's plan verbs, vscode's interim procedure).

### §S4 — deletions
Skills `crucible-report-{rust,java,bun,python,vscode}` (5 dirs) + `agent-protocol` (dir) + `memory/crucible-ingest.md`: archive copies to `<repo>/archive/wave2/`, then delete (chezmoi discipline: managed → destroy, unmanaged → rm; add new references; source commit).

### §S5 — repoint consumers
**Surfaces (verified at gap-analysis):** references to `crucible-report-*` / `agent-protocol` / `crucible-ingest` in `~/.claude/memory/rust-orchestration.md`, `java-orchestration.md`, remaining skills, and `~/.claude/AGENTS.md` → the `crucible` skill (+ stack reference file where specific).

## Acceptance criteria

### §S1
- [ ] `tests/test_crucible_skill.py` exists; RED then GREEN ingested with wave-2 cycle context.

### §S2
- [ ] `~/.claude/skills/crucible/SKILL.md` contains "heartbeat" within 3 lines of "register" and ZERO occurrences of "/agents/heartbeat" and "heartbeat.sh".
- [ ] Contains `<agent-type>-<project>` and `--phase`; contains `regression-ingest` (rust), `unit --test` (java), `plan-file` (bun), `--tests` (python); contains "REFUSED" or "400" (incoming cycleId contract); contains "CR-CRU-030" (envelope contract marked incoming).
- [ ] ZERO occurrences of: "Plan B", "same across stacks" (the old false-universality claim).

### §S3
- [ ] All five `references/{rust,java,bun,python,vscode}.md` exist; rust contains "workspace-regression"; bun contains "cycle-activate"; vscode contains "no client" (or equivalent) and "interim".

### §S4
- [ ] The 6 skill dirs + `memory/crucible-ingest.md` do not exist; archive copies exist under `<repo>/archive/wave2/`.
- [ ] Scoped `chezmoi diff` (the 5 standard paths) exits 0 empty.

### §S5
- [ ] `grep -rl "crucible-report\|agent-protocol\|crucible-ingest" ~/.claude/memory/ ~/.claude/skills/ ~/.claude/AGENTS.md ~/.claude/agents/` returns 0 files.

## Estimated size
M–L (five absorptions + rewrite).

## Risk
- The report skills are referenced by live agent definitions' habits — §S5's grep gate must include `~/.claude/agents/` (generated-agent rewrite is CR-MDB-008; if any agent hard-references a report skill, repoint the line here).
- Envelope section must not read as "already shipped" — mark INCOMING clearly or agents will expect envelopes that don't exist.

## Non-goals
- Any `*-crucible.py` client implementation (Crucible's, thread #1322).
- The model-b skill body (002), naming sweep (007), generator (008).
