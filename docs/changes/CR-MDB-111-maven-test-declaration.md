# CR-MDB-111 — The declaration step writes a Maven project's test tiers

**Status:** PENDING — **SEED, not the finished spec** (filed 2026-11-21 by the user's ruling, keeping
CR-MDB-099's item 5a: each stack's declaration gets one small CR when its Crucible release notes arrive; they
arrived with Crucible 0.4.0, #1622). Gap analysis and the spec happen in order when this CR starts. Pre-review:
none due unless gap analysis finds a trigger.
**Type:** feature (`init`, `agents`, `migrate`; stack data)
**Priority:** P2 — release 1.0.0, wave 2, after CR-MDB-099 (board-authoritative: read `queue`).
**Depends on:** CR-MDB-099 (the declaration step, the schema reader and `contracts/crucible-declaration.md`).
**Labels:** scaffold, migrate, crucible, stacks, quarkus
**Design reference:** CR-MDB-099; DN-multi-harness-deploy-model §D29; Crucible 0.4.0 `CHANGELOG.md` § Stack
declaration changes (maven; CR-CRU-237).

## Scope (seed)

1. **The declaration:** a Maven project's own `crucible.toml` gains `[targets.<tier>]` per declared tier, keyed
   by the client's tier vocabulary (`unit`, `module`, `integration`, `e2e`, `bdd`, `regression`), with
   `framework = "surefire"` and `console = "surefire-console"`; both fields required; `junit`, `stream` and
   `coverage` never written.
2. **`init`, `migrate` and `agents`** write or bring it up to date through CR-MDB-099's step, read from the
   installed schema.

## To measure at gap analysis

- Which tiers a project declares by default, and what `--yes` writes when none is detected.
- The score (3 points filed) and the behaviour units.
