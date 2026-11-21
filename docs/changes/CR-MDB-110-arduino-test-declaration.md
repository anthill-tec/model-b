# CR-MDB-110 — The declaration step writes an Arduino project's native test targets

**Status:** PENDING — **SEED, not the finished spec** (filed 2026-11-21 by the user's ruling, keeping
CR-MDB-099's item 5a: each stack's declaration gets one small CR when its Crucible release notes arrive; they
arrived with Crucible 0.4.0, #1622). Gap analysis and the spec happen in order when this CR starts. Pre-review:
none due unless gap analysis finds a trigger.
**Type:** feature (`init`, `agents`, `migrate`; stack data)
**Priority:** P2 — release 1.0.0, wave 2, after CR-MDB-099 (board-authoritative: read `queue`).
**Depends on:** CR-MDB-099 (the declaration step, the schema reader and `contracts/crucible-declaration.md`).
**Labels:** scaffold, migrate, crucible, stacks, arduino
**Design reference:** CR-MDB-099; DN-multi-harness-deploy-model §D29; Crucible 0.4.0 `CHANGELOG.md` § Stack
declaration changes (arduino; CR-CRU-203); Crucible #1550.

## Scope (seed)

1. **The declaration:** an Arduino project's own `crucible.toml` gains `[targets."<native dir>/<make target>"]`
   (the native dir relative to the project dir, joined by `/` to the make target) with
   `framework = "arduino-native"` and `stream = { codec = "crucible-events", path = "env:CRUCIBLE_STREAM" }`;
   every field required; `junit`, `console` and `coverage` never written.
2. **`init`, `migrate` and `agents`** write or bring it up to date through CR-MDB-099's step, read from the
   installed schema.
3. **The native harness template** adopts the `CRUCIBLE_STREAM` make contract (one `test-end` line per test,
   written and flushed as each ends; no `run-start`, no `run-end`; nothing when the variable is unset), where
   CR-MDB-084 has not already done it.

## To measure at gap analysis

- What CR-MDB-084 (the arduino stack made general) already moves, so the two do not overlap.
- How the native dir and make target are detected, and the `--yes` default.
- The score (3 points filed) and the behaviour units.
