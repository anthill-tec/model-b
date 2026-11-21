# CR-MDB-112 — The declaration step writes a Python project's test runner

**Status:** PENDING — **SEED, not the finished spec** (filed 2026-11-21 by the user's ruling, keeping
CR-MDB-099's item 5a: each stack's declaration gets one small CR when its Crucible release notes arrive; they
arrived with Crucible 0.4.0, #1622). Gap analysis and the spec happen in order when this CR starts. Pre-review:
none due unless gap analysis finds a trigger.
**Type:** feature (`init`, `agents`, `migrate`; stack data)
**Priority:** P2 — release 1.0.0, wave 2, after CR-MDB-099 (board-authoritative: read `queue`).
**Depends on:** CR-MDB-099 (the declaration step, the schema reader and `contracts/crucible-declaration.md`).
**Labels:** scaffold, migrate, crucible, stacks, python
**Design reference:** CR-MDB-099; DN-multi-harness-deploy-model §D29; Crucible 0.4.0 `CHANGELOG.md` § Stack
declaration changes (python) and § Added (the python client runs a pytest project).

## Scope (seed)

1. **The declaration:** a Python project's own `crucible.toml` gains `[python] runner = "pytest"` when the
   project's tests are pytest's; a unittest project declares nothing (the client's default) or
   `runner = "unittest"`, as gap analysis decides. No other value is written.
2. **`init`, `migrate` and `agents`** write or bring it up to date through CR-MDB-099's step, read from the
   installed schema.

## To measure at gap analysis

- How a pytest project is detected (configuration files, dev dependencies), and the `--yes` default.
- The score (2 points filed) and the behaviour units.
