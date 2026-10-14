# CR-MDB-069 — The built-wheel checks build in isolation, so CI needs no `build` frontend

**Status:** PENDING — spec (gap analysis 2026-10-14).
**Type:** fix (tests, CI workflow, `AGENTS.md`)
**Priority:** P1 — release 1.0.0, wave 2; next after CR-MDB-067.
**Depends on:** CR-MDB-067 (board-authoritative: read `queue`)
**Labels:** ci, tests, packaging
**Design reference:** CR-MDB-067 §S3; `pyproject.toml` `[build-system]` (hatchling, which reads the fixed
`modelb_axi.__version__` through `[tool.hatch.version]`).

## Context

- **CI is red on `develop`.** The first `ci.yml` run (38543466699, after CR-MDB-067's merge) ran 2732
  tests: 2 failures, 26 skips. Both failures are `ERROR Backend 'hatchling.build' is not available.`:
  - `test_tooling_detachment.AssetSlotGatesS7Test.test_s7_built_wheel_carries_all_eight_tool_assets`;
  - `test_project_registry_schema.ProjectSchemaWheelTest.test_built_wheel_ships_the_schema_with_the_registry_keys`.
- **Why.** Those two checks alone build with `python -m build --wheel --no-isolation`, which needs the
  build backend already installed in the interpreter. They skip only when the `build` frontend is absent.
  CI installs `build` (CR-MDB-067 §S3 step 4) but not `hatchling`. They pass locally only because the
  system interpreter carries hatchling.
- **Every other wheel check builds in isolation.** `tests/test_package_publishing.py`'s `build_wheel`
  and `build_sdist` run `uv build`, which installs the backend into a throwaway build environment; those
  checks (and the release workflow's `uv build`) pass on the hosted runner. They fail, guarded and not
  skipped, when `uv` is absent.
- **The skip has a reader.** `AGENTS.md`'s skip list names "an interpreter without the `build`
  frontend", and `tests/test_python_floor.py`'s `agents_md_floor_faults` (CR-MDB-064 §S5) requires that
  example to exist and to name no interpreter below the floor.

## Scope

### §S1 — The two checks build through the shared isolated helper

`test_s7_built_wheel_carries_all_eight_tool_assets` and
`test_built_wheel_ships_the_schema_with_the_registry_keys` build their wheel with
`build_wheel(REPO_ROOT, <temp dir>)` from `tests/test_package_publishing.py` (imported, as
`tests/test_code_health_skill.py` already does). They no longer import `build`, skip when it is absent,
or pass `--no-isolation`; like every other built-artifact check, they fail (guarded) when `uv` is absent.
What each asserts about the built wheel is unchanged.

### §S2 — CI installs no `build` frontend

`.github/workflows/ci.yml` drops the `python -m pip install build` step: the job has four steps —
checkout (`fetch-depth: 0`), `setup-python` 3.14, `setup-uv`, the suite. `tests/test_ci_workflow.py`'s
step order and its build-step check move with it (its sample `ci.yml` and mutations too). No step
installs `build` or `hatchling`.

### §S3 — The skip is retired from `AGENTS.md`

- The skip list no longer names an interpreter without the `build` frontend, in either place (the
  bolded list and its sentence).
- `agents_md_floor_faults` no longer requires the `build`-frontend example; its floor and pre-merge
  sentence rules are unchanged, and its sample-text proofs move with it.
- The baselines are re-measured; the counts may move only as §S1 moves them.

## Acceptance criteria

- [ ] **§S1.** Both checks call `build_wheel` from `tests/test_package_publishing.py`; neither module
      names `--no-isolation`, `find_spec("build")` or `"-m", "build"`; their wheel assertions are
      unchanged. No helper body is duplicated.
- [ ] **§S2.** `ci.yml` has exactly the four steps in that order; no step installs `build` or
      `hatchling`; `tests/test_ci_workflow.py`'s checks and their sample-text proofs pass and bite on
      a re-added build step.
- [ ] **§S3.** `AGENTS.md`'s skip list names no `build`-frontend skip; `agents_md_floor_faults` passes
      on it and its proofs pass both ways; the baselines match the measured counts.
- [ ] **Runs.** Every commit leaves the suite green through the client with a real `HOME` and an empty
      one (temp home empty afterwards), beyond RED's own failures; `generator/build.py --check` is
      clean. The orchestrator re-measures the hosted-runner image (with no `build` installed): 0
      failures.
- [ ] **After the merge:** the push of `develop` runs `ci.yml` green on GitHub (read with `gh run
      list` / `gh run view`, read-only).

## Non-goals

- **The build backend stays hatchling.** It reads the fixed `__version__`; hatch-vcs stays declined.
- **The rehearsal job** (`release.yml`) already builds with `uv build`; it is unchanged.

## Cycle plan

1. **C1 — Isolated wheel builds, the CI step and the skip (§S1–§S3).** Red-green.
2. **C2 — Verify.**
