# CR-MDB-053 — Tool-script lint

**Status:** PENDING — **SEED, not the finished spec** (filed 2026-10-02; moved 2026-10-16 into release 1.0.0, wave 2).
Every item below is re-measured at gap analysis; the spec is written then.
**Type:** refactor (tool scripts)
**Priority:** P2 — release 1.0.0, wave 2; before the release's test-hygiene CR (CR-MDB-052).
**Depends on:** none (board-authoritative: read `queue`, not this line)
**Labels:** scripts, lint, hygiene
**Design reference:** AGENTS.md § Key Directories (`scripts/`, deployed to `~/.agents/scripts/`);
`audits/2026-09-21-codebase-review-assets.md`

## Scope (seed)

1. **`scripts/worktree-flow.py` lint** — measured 2026-10-02 with `ruff --target-version py311`:
   BLE001, F401, PIE810, PLW1510, RUF059, SIM102 (one each).
2. **PIE810 repeated `startswith`/`endswith`** — re-sweep `scripts/` and `tests/` (the earlier
   `test_toon_codec` and `test_watcher_launch_supervision` sites measured clean on 2026-10-02).
3. **Measured again 2026-10-16** (`ruff --isolated`, unchanged by CR-MDB-059): `scripts/worktree-flow.py`
   also carries SIM105 (`try`-`except FileNotFoundError`-`pass`), and `modelb_axi/cli.py` an I001 import
   order (`tomllib` placement) that the project's own config accepts but the default profile flags.
   Decide which profile the lint gate uses before fixing.

The stale references this seed once carried moved into the CRs that test their scripts:
`rust-code-health.py`'s docstring into CR-MDB-078, `skill-release-gate.py`'s skill roots into
CR-MDB-081. CR-MDB-081 also rewrites `worktree-flow.py`'s `sync`, so the lint is measured again after it.
