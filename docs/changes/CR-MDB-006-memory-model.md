# CR-MDB-006 — memory model: global→project-level migration

**Status:** PENDING
**Type:** maintenance
**Priority:** P1 (wave-2 closer with 007)
**Depends on:** CR-MDB-002, 003, 004, 005
**Labels:** memory, migration, templates
**Phase:** Wave 2
**Design reference:** `docs/research/PRD-model-b-rationalization.md` §D5 (global = language refs only), §D10.6 (scaffold instantiates project memory)

## Context

After 002–005, global memory holds 13 files. Per D5 only cross-project LANGUAGE references stay global; stack orchestration mechanics and operational references become scaffold-instantiated project-level memory (templates live in this repo per D10.6). Also alive: the broken `plan_b_workflow_model.md` (mis-paste; canonical content shipped in the model-b skill) and two stale orphans.

## Scope

### §S1 — AC gate tests
`tests/test_memory_model.py`, wrapper-run (cycle context), RED → GREEN.

### §S2 — devops merge + orphan wiring
Merge the UNIQUE content of `memory/devops-environment.md` into `memory/java-testing-practices.md` (TestContainers patterns, DevServices MongoDB/Redis, @Nested continuous-testing gotcha, container-runtime/Podman, CI considerations — skip what java-testing already carries; audit mapped the overlap as heavy). Wire `java-modern-syntax.md` into the AGENTS.md Java stack-reference row (orphan since the audit).

### §S3 — deletions (chezmoi discipline; archive to `<repo>/archive/wave2/memory/`)
`QUICK_REFERENCE.md` (superseded by the trigger table), `stack-detection.md` (routing superseded by the crucible skill), `plan_b_workflow_model.md` (broken mis-paste; canonical = model-b skill — gap-analysis stowaway, never assigned before), `devops-environment.md` (after §S2 merge).

### §S4 — relocations to scaffold-template scope
Move `java-orchestration.md`, `rust-orchestration.md`, `operational-commands.md` → `<repo>/skills-src/memory-templates/` (the D10.6 source material; scaffold instantiates per project stack/mode). During the move, fix `rust-orchestration.md`'s dangling `memory/sandesh.md` reference (VERIFY-routed from 002) → `~/.claude/skills/model-b/references/sandesh.md`. Then delete the three from `~/.claude/memory/` (chezmoi discipline).
Global memory end state: EXACTLY 6 files — `convex-client-server.md`, `java-coding-standards.md`, `java-modern-syntax.md`, `java-testing-practices.md`, `maven-best-practices.md`, `quarkus-patterns.md`.

### §S5 — repoint consumers
**Surfaces (gap-analysis verified 2026-07-20):** `~/.claude/AGENTS.md` — Java row adds `java-modern-syntax.md` and drops `java-orchestration.md`; Rust-stack row and Operational-commands row REPLACED by one row "Stack orchestration + operational mechanics → project-level memory (scaffold-instantiated; templates: model-b repo `skills-src/memory-templates/`)". The 4 quarkus agent defs' `java-orchestration.md` citations → "the project's instantiated orchestration memory (template: model-b repo)".

## Acceptance criteria

### §S1
- [ ] `tests/test_memory_model.py` exists; RED then GREEN ingested with wave-2 cycle context.

### §S2
- [ ] `~/.claude/memory/java-testing-practices.md` contains "TestContainers" AND "DevServices" AND "@Nested" AND ("Podman" or "container runtime").
- [ ] AGENTS.md Java stack row contains `java-modern-syntax.md`.

### §S3
- [ ] `QUICK_REFERENCE.md`, `stack-detection.md`, `plan_b_workflow_model.md`, `devops-environment.md` do not exist under `~/.claude/memory/`; content-preserving archive copies exist under `<repo>/archive/wave2/`.

### §S4
- [ ] `<repo>/skills-src/memory-templates/{java-orchestration,rust-orchestration,operational-commands}.md` exist; rust-orchestration template contains `skills/model-b/references/sandesh.md` and zero `memory/sandesh.md`.
- [ ] `ls ~/.claude/memory/ | wc -l` == 6 with exactly the six D5 files.
- [ ] Scoped `chezmoi diff` (5 standard paths) exits 0 empty.

### §S5
- [ ] `grep -rl "QUICK_REFERENCE\|stack-detection\|plan_b_workflow\|devops-environment\|memory/java-orchestration\|memory/rust-orchestration\|memory/operational-commands" ~/.claude/memory/ ~/.claude/skills/ ~/.claude/AGENTS.md ~/.claude/agents/` returns 0 files.
- [ ] AGENTS.md contains "scaffold-instantiated" (the project-level row) and zero occurrences of `memory/rust-orchestration.md`.

## Estimated size
M.

## Risk
- The quarkus agents lose their global java-orchestration pointer before the scaffold exists — interim wording must make clear the project's OWN memory carries it (NAI/quarkus projects already have project docs). Templates in this repo keep the content reachable.

## Non-goals
- The scaffold itself (013); the "Plan B"→"Model B" text sweep in remaining files (007 — §S3 only DELETES the plan_b file); template parameterization format (013 design).
