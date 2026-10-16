# CR-MDB-078 — Tests for the adopted tool scripts

**Status:** PENDING — **SEED, not the finished spec** (filed 2026-10-17 into release 1.0.0, wave 2).
Gap analysis, the spec and its pre-review happen in order when this CR starts.
**Type:** tests (the deployed tool scripts)
**Priority:** P1 — release 1.0.0, wave 2; after CR-MDB-073.
**Depends on:** CR-MDB-073, whose gate measures the result (board-authoritative: read `queue`).
**Labels:** tests, coverage, scripts
**Design reference:** PRD D5 (the 2026-10-17 ruling on coverage).

## Context

Measured 2026-10-17 under coverage, with subprocess measurement on, by the whole suite:

| Script | Lines covered |
|---|---|
| `scripts/rust-code-health.py` | 0/381 |
| `scripts/rust-crate-map.py` | 8/251 |
| `scripts/skill-release-gate.py` | 10/212 |
| `scripts/rust-dead-scan.py` | 51/468 |
| `scripts/worktree-flow.py` | 333/537 |
| `scripts/schedule_db.py` | 0/222 (on its way out; no new tests) |

The adopted scripts are deployed to every installation under `~/.agents/scripts/`. The tests that
touch them today check their adoption, layout and invocation, not what they compute.

## Scope (seed)

1. **The three `rust-*` health tools** (`rust-crate-map.py`, `rust-dead-scan.py`, and their
   orchestrator `rust-code-health.py`): behaviour tests on a synthetic Cargo workspace built in a
   temp dir. They exercise crate mapping, dead-code findings, the snapshot, and the ledger verbs, and
   run each tool as a subprocess so its coverage is measured.
2. **`skill-release-gate.py`:** behaviour tests for its verdicts on synthetic skill trees.
3. **`worktree-flow.py`:** the verbs and paths still unexercised, measured at gap analysis.
4. **The coverage baseline** (CR-MDB-073's `Coverage baseline:` line) rises with the result.

## To measure at gap analysis

- Whether any script needs `cargo` on `PATH`, and how a test fixture stands in for it hermetically
  (no nested builds, per the post-RED review rule).
- Each script's verbs and exit paths, and which defects the tests surface (a defect is fixed in this
  CR's GREEN or FIX cycles, never left behind a skip).
- The re-score: about 8 points; split if it exceeds 13.
