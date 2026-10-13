# CR-MDB-063 — The python client's test interpreter is probed where the client will use it

**Status:** PENDING — **SEED, not the finished spec.** Gap analysis, the design record, the spec and
its pre-review happen in order when this CR starts.
**Type:** feature (installer preflight, scaffold capability contract and Setup section)
**Priority:** P1 — release 1.0.0, wave 2.
**Depends on:** CR-MDB-064 (the Python floor it probes against; board-authoritative: read `queue`)
**Labels:** installer, preflight, scaffold, python
**Design reference:** DN-multi-harness-deploy-model §D21 (amended 2026-10-13) and §D22; PRD D10 (the
installer detects, `init` reads the verdicts); the python client's `test --help` (`--python`: "Must
have xmlrunner (and coverage.py for --coverage)").

## Context

The python client runs tests under `$PY_CRUCIBLE_PYTHON`, else `<project>/.venv/bin/python` if present,
else its own interpreter, and that interpreter must have `xmlrunner` (and `coverage` for `--coverage`).
The installer's python-stack probe (`modelb_axi/requirements.py`, `modelb_axi/toolchains.py`) checks
`xmlrunner` and `coverage` only in the default `python3`. A project whose `.venv`, or whose
`$PY_CRUCIBLE_PYTHON`, lacks them passes the install and fails at its first client run. Measured on
this machine: a uv-managed interpreter refuses `uv pip install` ("externally managed"); the route is a
virtual environment.

## Scope (seed)

1. **The installer** also probes `$PY_CRUCIBLE_PYTHON` when set, and reports its verdict with the
   remediation.
2. **`init`'s capability contract and Setup section** say the project's test interpreter (its
   `.venv/bin/python` when present, else `python3`) needs `xmlrunner` and `coverage`, and give the
   install command and the `uv venv` route for a uv-managed interpreter.
3. **Measure:** whether `init` can probe the project's `.venv` at scaffold time (it usually does not
   exist yet), and the cost of re-probing at bootstrap instead.
