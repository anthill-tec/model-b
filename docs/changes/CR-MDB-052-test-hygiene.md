# CR-MDB-052 — Test hygiene: a flaky oracle, a dead branch and the ledger query

**Status:** PENDING — **SEED, not the finished spec** (filed 2026-10-02).
Every item below is re-measured at gap analysis; the spec is written then.
**Type:** test/skill hygiene
**Priority:** P2 — release 1.0.0, wave 2: the release's test-hygiene CR, the last CR before the
release starts.
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
4. **The empty-`HOME` run relies on `XDG_CACHE_HOME` sitting outside `HOME`.** `tests/test_package_publishing.py`'s
   `_run_uv_build` (behind `build_wheel` and `build_sdist`) lets `uv build` write its cache; with
   `XDG_CACHE_HOME` unset, an empty-`HOME` run would leave `~/.cache/uv` in the temp home. Pass a temp
   `UV_CACHE_DIR`, or state the dependency beside the empty-`HOME` baseline.
5. **The isolated-wheel gate** (`IsolatedWheelBuildGateTest`) matches its non-isolated markers as
   literal strings and catches only a `def build_wheel` redefinition (not another quoting or spacing of
   `-m build`, an `async def`, an assignment or a shadowing import).
6. **Analyzer findings in the test tree:** `tests/test_package_publishing.py`'s import block is unsorted
   under `ruff --isolated` (I001); `tests/test_tooling_detachment.py` carries Optional-typing faults at
   its home-resolution lines (~820–834) and an insecure temp-file call (~189). Production modules
   carry the same kinds of finding: unsorted import blocks in `modelb_axi/agents.py`, `scaffold.py` and
   `cli.py` (I001) and an unguarded call near `scaffold.py`'s hook-scripts check; each is fixed here or
   named for CR-MDB-053 (tool-script and module lint).
7. **A sweep of the suite's own health** at gap analysis: every analyzer finding in `tests/`, slow or
   network-bound tests, skip reasons, and helpers defined in more than one module, each fixed or
   recorded with a reason.
8. **Names that outgrew their scope.** `tests/test_install_guide.py`'s `RELEASE_WORKFLOW_COMMANDS_RE`
   and `test_the_project_name_gate_spares_the_release_workflow_commands_only` now also spare
   `modelb-axi agents`, which is not a release-workflow command; rename both to what they cover.
9. **`AGENTS.md`'s stale agent and stack counts.** It says "16 stack×role agents" and names four stack
   files (`stacks/{arduino,bun,python,quarkus}`), but `generator/agents` holds 20 definitions,
   rust included.
