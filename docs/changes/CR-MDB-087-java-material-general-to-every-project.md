# CR-MDB-087 — The Java material is general to every Java project

**Status:** PENDING — **SEED, not the finished spec** (filed 2026-10-28 into release 1.1.0, wave 3).
Gap analysis, the spec and its pre-review happen in order when this CR starts.
**Type:** refactor (stack skill content, stack file)
**Priority:** P1 — release 1.0.0, wave 2, after CR-MDB-084 (moved from 1.1.0 by the user, 2026-10-30: CR-MDB-079's
generality guard covers every stack file, with this stack a named exception until this CR removes it).
**Depends on:** CR-MDB-086 (the Java stack skill); the board is authoritative: read `queue`, not this
line.
**Labels:** stacks, java, quarkus, generality
**Design reference:** DN-multi-harness-deploy-model §D25 (a stack carries what holds for every project
on it; one project's architecture lives in that project); PRD D5, amendment of 2026-10-28 (a stack
skill carries only what holds for every project on its stack); CR-MDB-079 and CR-MDB-084 (the same
correction for the bun and arduino stacks).

## Context

The Java references and `quarkus.toml` were written around one project's architecture. CR-MDB-086
replaces that project's package and library names; about 35 more terms describe its architecture
rather than Java or Quarkus in general — measured at CR-MDB-086's second spec pre-review:
`entitystore`, `UuidV7Generator`, `ServerEvent` and `eventBus.emit`, `ModelIdCache`,
`GlobalExceptionMappers`, `BusinessEntityDto`, RediSearch conventions.

## Scope (seed)

1. **`java-stack` and `quarkus.toml` hold only what holds for every Java or Quarkus project.** One
   project's components, conventions and services leave them; what they still teach goes to that
   project's own `AGENTS.md` or knowledge store.
2. **The generated quarkus definitions are re-rendered**, and every guard naming the removed text is
   updated.
3. **The project the text came from is told** before this CR merges, so it records its specifics in
   its own project first — asking the user who owns it and how to reach it.
