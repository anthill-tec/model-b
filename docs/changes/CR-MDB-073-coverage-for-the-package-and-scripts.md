# CR-MDB-073 — Coverage for the package and every script

**Status:** PENDING — **SEED, not the finished spec** (filed 2026-10-15 into release 1.0.0, wave 2).
Gap analysis, the spec and its pre-review happen in order when this CR starts.
**Type:** feature (test configuration, the pre-merge gate, `AGENTS.md`)
**Priority:** P1 — release 1.0.0, wave 2; before the release's test-hygiene CR (CR-MDB-052).
**Depends on:** CR-MDB-059, which defines the pre-merge gate's order (board-authoritative: read
`queue`).
**Labels:** tests, coverage, gate
**Design reference:** PRD D5 (the pre-merge gate, AMENDED 2026-10-15).

## Context

Measured 2026-10-15:

- **No gate measures coverage.** Every gate Model B runs is `python-crucible.py test`, with a real
  `HOME`, with an empty `HOME`, and on the clean runner. `regression --coverage` appears only as an
  example command in `AGENTS.md`. The only coverage data on disk is a gitignored `.coverage` from
  2026-10-13 that measured 18 files, all in `modelb_axi/`.
- **The client's default source is Crucible's own.** `regression` and `pre-merge-gate` default
  `--cov-source` to `crucible_axi,clients`, so a bare `--coverage` run on Model B measures nothing
  of Model B.
- **No coverage config.** Model B has no `[tool.coverage]` and no `.coveragerc`.
- **The scripts have never been measured:**
  - `scripts/`: seven Python tool scripts, plus `gate-lock.sh`;
  - `hooks-src/scripts/`: eight extensionless Python hooks with a `/usr/bin/python3` shebang;
  - `workflows-src/`: `stamp_version.py` and `changelog_section.py`.
- **Most script tests run the scripts as subprocesses** (38 modules exercise the scripts). coverage.py
  traces only the process it started, unless subprocess measurement is on (coverage 7.10+
  `[run] patch = ["subprocess"]`; 7.16.2 is installed). About ten modules load a script
  in-process.

## Scope (seed)

1. **A coverage config in `pyproject.toml`.**
   - Sources: `modelb_axi`, `scripts`, `hooks-src/scripts` and `workflows-src`.
   - Subprocess measurement, and parallel data files combined after the run.
   - The extensionless hooks included by path.
   - Excluded: `__pycache__`, generated code (`modelb_axi/toon.py`'s generated twin
     `scripts/toon.py`; decide which one counts) and the packaged `_assets` copy.
2. **The pre-merge gate measures coverage.**
   - Its full-suite run is `regression --coverage --cov-source <the sources>`, filed under the last
     cycle (CR-MDB-059 §S5).
   - The empty-`HOME` and clean-runner runs stay as they are.
   - The run's per-file coverage, and its total, are read from the board.
3. **What the gate requires: decide at gap analysis.** Report-only, or a floor. A floor needs a
   measured baseline first, and the subprocess tests must actually be traced, so the figure is real.
4. **The non-Python script.** `gate-lock.sh` is outside coverage.py; it is listed as unmeasured,
   never silently dropped.
5. **`AGENTS.md` and the `crucible` skill** name the coverage run, and that `--cov-source` is passed
   explicitly, because the client's default fits only Crucible.

## To measure at gap analysis

- Whether the subprocess patch reaches the hooks (`/usr/bin/python3` must import coverage in the
  child) and the tests that run scripts through `sys.executable`. Measure it in a `/tmp` sandbox
  first.
- The run's cost: time and disk for the parallel data files. A full coverage regression is a heavy
  gate.
- Whether the client ingests per-file coverage for paths outside a package (the scripts
  directories).
- Crucible's answer to the `--cov-source` default (Model B note sent 2026-10-15); if the default
  becomes project config (`crucible.toml`), use it.
- The re-score.
