# CR-MDB-053 — Tool-script lint and stale references

**Status:** PENDING — **SEED, not the finished spec** (filed 2026-10-02 into release 1.1.0, wave 3).
Every item below is re-measured at gap analysis; the spec is written then.
**Type:** refactor (tool scripts)
**Priority:** P3 — release 1.1.0, wave 3.
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
