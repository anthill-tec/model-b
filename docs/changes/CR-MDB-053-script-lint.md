# CR-MDB-053 — Tool-script lint and stale references

**Status:** PENDING — **SEED, not the finished spec** (filed 2026-10-02; moved 2026-10-16 into release 1.0.0, wave 2).
Every item below is re-measured at gap analysis; the spec is written then.
**Type:** refactor (tool scripts)
**Priority:** P2 — release 1.0.0, wave 2; before the release's test-hygiene CR (CR-MDB-052).
**Depends on:** none (board-authoritative: read `queue`, not this line)
**Labels:** scripts, lint, hygiene
**Design reference:** AGENTS.md § Key Directories (`scripts/`, deployed to `~/.agents/scripts/`);
`audits/2026-09-21-codebase-review-assets.md`

## Scope (seed)

1. **`scripts/rust-code-health.py`'s module docstring** still says board transitions mirror via
   `schedule_db.set_state` (CR-MDB-023 routing); align it with `schedule_db.py`'s TRANSITIONAL status.
2. **`scripts/skill-release-gate.py`'s `phase_skills`** auto-discovers `skills/` and `.claude/skills/`;
   Pi's roots are `.pi/skills/` and `.agents/skills/` (audit assets #28).
3. **`scripts/worktree-flow.py` lint** — measured 2026-10-02 with `ruff --target-version py311`:
   BLE001, F401, PIE810, PLW1510, RUF059, SIM102 (one each).
4. **PIE810 repeated `startswith`/`endswith`** — re-sweep `scripts/` and `tests/` (the earlier
   `test_toon_codec` and `test_watcher_launch_supervision` sites measured clean on 2026-10-02).
5. **Measured again 2026-10-16** (`ruff --isolated`, unchanged by CR-MDB-059): `scripts/worktree-flow.py`
   also carries SIM105 (`try`-`except FileNotFoundError`-`pass`), and `modelb_axi/cli.py` an I001 import
   order (`tomllib` placement) that the project's own config accepts but the default profile flags.
   Decide which profile the lint gate uses before fixing.
