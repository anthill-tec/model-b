# CR-MDB-069 — The built-wheel checks build in isolation, so CI needs no `build` frontend

**Status:** PENDING — spec (gap analysis and pre-review 2026-10-14).
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
  CI installs `build` (CR-MDB-067 §S3 step 4) but not `hatchling`. Locally both pass: every local
  interpreter carries `build` and `hatchling`.
- **Every other wheel check builds in isolation.** `tests/test_package_publishing.py`'s `build_wheel`
  (a source tree or an sdist) and `build_sdist` run `uv build`, which installs the backend into a
  throwaway build environment; `tests/test_code_health_skill.py` and
  `tests/test_worktree_layout_and_bundles.py` import them. Those checks, and the release workflow's
  `uv build`, pass on the hosted runner. They fail, guarded and not skipped, when `uv` is absent, and
  they need PyPI or the uv cache to fetch hatchling; the two checks take on the same property.
- **The skip has a reader.** `AGENTS.md`'s skip list names "an interpreter without the `build`
  frontend", and `tests/test_python_floor.py`'s `agents_md_floor_faults` (CR-MDB-064 §S5) requires that
  example to exist and to name no interpreter below the floor.

## Scope

### §S1 — The two checks build through the shared isolated helper

- `test_s7_built_wheel_carries_all_eight_tool_assets` and
  `test_built_wheel_ships_the_schema_with_the_registry_keys` build their wheel with
  `build_wheel(REPO_ROOT, <temp dir>)`, imported as `from tests.test_package_publishing import
  build_wheel` (no `TestCase` and no `*` import), as `tests/test_code_health_skill.py` already does.
- They no longer look for `build`, skip, or pass `--no-isolation`; like every other built-artifact
  check, they fail (guarded) when `uv` is absent. What each asserts about the built wheel is unchanged.
- The now-unused `importlib.util` import goes from both modules, and `test_tooling_detachment.py`'s
  docstring import list moves with it.
- **A structural gate** reads both modules' source and fails if either names `--no-isolation`,
  `find_spec("build")` or `"-m", "build"`, if either check does not call `build_wheel`, or if either
  check calls `skipTest`.

### §S2 — CI installs no `build` frontend

- `.github/workflows/ci.yml` drops the `python -m pip install build` step. The job has four steps:
  checkout (`fetch-depth: 0`), `setup-python` 3.14, `setup-uv`, the suite.
- `tests/test_ci_workflow.py` moves with it:
  - `STEP_ORDER` has the four steps;
  - `build_faults` is inverted: a fault for every step whose run line holds `install` and a
    whole-word `build` or `hatchling` (so `uv build` never matches);
  - the sample `ci.yml` loses the step; the "bare pip" mutation is replaced by "a re-added
    `python -m pip install build` step" and "a `pip install hatchling` step", each one fault from
    `build_faults`;
  - `test_the_five_steps_run_in_order` and `test_the_build_frontend_is_installed` are renamed for four
    steps and no build frontend or backend installed;
  - the module docstring cites CR-MDB-069 §S2 as amending CR-MDB-067 §S3.

### §S3 — The skip is retired from `AGENTS.md`

- The skip list no longer names an interpreter without the `build` frontend, in either place (the
  bolded list and its sentence, including "(1 each)").
- `agents_md_floor_faults` is inverted for the example: it reports
  ``the skip list still names an interpreter without the `build` frontend`` for any line containing it.
  The python3.11-in-the-example rule retires; the floor and pre-merge sentence rules are unchanged.
- Its proofs move: `_CONFORMING_AGENTS_MD` drops the example; `test_bites_when_the_skip_example_is_gone`
  becomes "re-adding the example bites exactly once"; `test_bites_on_python3_11_in_the_skip_example`
  goes; the module docstring moves with it.
- The test count moves only by the proofs §S2 and §S3 add or retire; the skip counts stay 1 (real
  `HOME`) and 12 (empty `HOME`).

### §S4 — The specs this amends

One dated line each: `CR-MDB-067-release-rehearsal-and-ci.md` §S3 step 4 ("retired by CR-MDB-069
§S2, 2026-10-14"), and `CR-MDB-064-python-floor-3-14.md` at its `build`-frontend example rule ("retired
by CR-MDB-069 §S3, 2026-10-14").

## Acceptance criteria

- [ ] **§S1.** The structural gate (named in its module and class) passes on the changed modules and is
      proved on sample source both ways: each forbidden string, a missing `build_wheel` call and a
      `skipTest` bite once. Neither module imports `importlib.util` unused. No helper body is
      duplicated.
- [ ] **§S2.** `ci.yml` has exactly the four steps in order; `build_faults` passes on it; the two
      mutations each give exactly one fault; the renamed tests and the docstring are as §S2.
- [ ] **§S3.** `AGENTS.md` names no `build`-frontend skip; `agents_md_floor_faults` passes on it; the
      moved proofs pass, and re-adding the example bites exactly once.
- [ ] **§S4.** Both spec lines are present.
- [ ] **Runs.**
      - Every commit leaves the suite green through the client with a real `HOME` and an empty one
        (temp home empty afterwards), beyond RED's own failures; the skip counts are 1 and 12;
        `generator/build.py --check` is clean; the `AGENTS.md` baselines match.
      - **The no-backend measurement** (orchestrator): the two checks, run through the client with
        `--python` pointed at a temp venv (`uv venv --python 3.14`) holding only
        `unittest-xml-reporting` — no `build`, no `hatchling` — skip on the pre-change tree and both
        pass after the change.
- [ ] **After the merge:** the push of `develop` runs `ci.yml` green on GitHub (read with `gh run
      list` / `gh run view`, read-only).

## Non-goals

- **The build backend stays hatchling.** It reads the fixed `__version__`; hatch-vcs stays declined.
- **The rehearsal job** (`release.yml`) already builds with `uv build`; it is unchanged.
- **`scripts/skill-release-gate.py`**, a shipped tool script, keeps its own `python -m build --wheel`.
- **Moving `build_wheel` into `tests/_helpers.py`.** Three modules already import it from
  `tests/test_package_publishing.py`; this CR follows that.

## Cycle plan

1. **C1 — Isolated wheel builds, the CI step, the skip and the spec notes (§S1–§S4).** Red-green.
2. **C2 — Verify.**
