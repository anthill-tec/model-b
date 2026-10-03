# CR-MDB-052 — Test hygiene: a flaky oracle, a dead branch and the ledger query

**Status:** PENDING — **SEED, not the finished spec** (filed 2026-10-02 into release 1.1.0, wave 3).
Every item below is re-measured at gap analysis; the spec is written then.
**Type:** test/skill hygiene
**Priority:** P3 — release 1.1.0, wave 3.
**Depends on:** none (board-authoritative: read `queue`, not this line)
**Labels:** tests, hygiene, code-health
**Design reference:** AGENTS.md § Testing & QA (the suite is green and hermetic; a failure is a
regression); CR-MDB-032 (suite relocation and hermeticity)

## Scope (seed)

1. **The flaky toon-oracle test in `tests/test_suite_hermeticity.py`.** It has failed intermittently;
   reproduce it, find the nondeterminism, and make it deterministic without weakening it.
2. **A dead branch in `tests/test_installer_prune.py`.** The `prune` helper accepts a dict return
   from `modelb_axi.deploy.prune_assets`, which the merged tuple shape makes dead (CR-MDB-040 nit).
3. **The `code-health` skill's `query ledger OPEN`** (CR-MDB-023 VERIFY F7) matches no status the
   tools produce (PROPOSED / APPROVED / IN_PROGRESS / COMPLETED / STRUCK).
