# CR-MDB-052 — Test hygiene: a flaky oracle, a dead branch, the ledger query and worktree-flow's status in a submodule

**Status:** PENDING — **SEED, not the finished spec** (filed 2026-10-02).
Every item below is re-measured at gap analysis; the spec is written then.
**Type:** test/skill hygiene + a tool fix (`scripts/worktree-flow.py`)
**Priority:** P2 — release 1.0.0, wave 2: the release's test-hygiene CR, the last CR before the
release starts.
**Depends on:** none (board-authoritative: read `queue`, not this line)
**Labels:** tests, hygiene, code-health, worktree-flow
**Design reference:** AGENTS.md § Testing & QA (the suite is green and hermetic; a failure is a
regression); CR-MDB-032 (suite relocation and hermeticity); `scripts/worktree-flow.py`'s model (the
main checkout is the integration tree) and `contracts/worktree-layout.md`

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
   its home-resolution lines (~820–834) and an insecure temp-file call (~189). The production
   modules' import blocks are covered by CR-MDB-053's pinned `ruff check` (clean under its `py314`
   target); the unguarded call near `scaffold.py`'s hook-scripts check is re-measured here.
7. **A sweep of the suite's own health** at gap analysis: every analyzer finding in `tests/`, slow or
   network-bound tests, skip reasons, and helpers defined in more than one module, each fixed or
   recorded with a reason.
8. **Names that outgrew their scope.** `tests/test_install_guide.py`'s `RELEASE_WORKFLOW_COMMANDS_RE`
   and `test_the_project_name_gate_spares_the_release_workflow_commands_only` now also spare
   `modelb-axi agents`, which is not a release-workflow command; rename both to what they cover.
9. **`AGENTS.md`'s stale agent and stack counts.** It says "16 stack×role agents" and names four stack
   files (`stacks/{arduino,bun,python,quarkus}`), but `generator/agents` holds 20 definitions,
   rust included.
10. **No gate pins the plain-word rule for head and tail** (CR-MDB-072 VERIFY F1). The AXI-envelope
    rule states grep, head and tail as plain words, never code spans; `test_client_path_anchoring`
    catches only a `grep` span. Add a check over the rule's places in
    `tests/test_axi_envelope_read_whole.py`. Its detector also spares a no-space pipe
    (`status|head`) and masks `< file > /dev/null` as a placeholder; both are accepted blind spots,
    worth a comment.
11. **Coverage-gate follow-ups (CR-MDB-073 VERIFY).**
    - `tools/coverage-check.py` counts `hooks-src/scripts/` files as expected only when an area covers
      that directory; no test pins it.
    - No test pins that `tools/` stays out of the sdist's `only-include`.
    - `AGENTS.md`'s skip list ("Nothing else skips") leaves out the skips when neither `develop` nor
      `origin/develop` resolves (`ClosedCrSpecsUntouchedTest` and CR-MDB-073's two §S4 gates).
12. **`worktree-flow.py status` in a submodule.** Inside a git submodule — Model B itself, and any
    project checked out as one — `git worktree list` names the main checkout by its git directory
    (`<superproject>/.git/modules/<name>`, reached through `core.worktree`), not its working tree.
    `status` compares that path with the resolved main checkout, misses, and reports the integration
    tree as a CR worktree named after the git directory (`model-b`, phase "started — RED pending"),
    with no integration row, both on the stderr board and in the envelope's `worktrees[]`; a dirty
    develop then reads "DIRTY (commit first)" on a worktree. `status` must report the main checkout
    as the integration tree in a submodule and list no CR it does not have. A CR worktree under
    `.worktrees/<cr>` in a submodule is still listed, and `sync`, `finish` and `abort` still find it.
    Tested with a submodule fixture.
13. **`worktree-flow.py start` copies the project's gitignored `crucible.toml`** (Crucible #1494, user
    ruling 2026-10-29: folded into this CR). `start` copies the gitignored `.env` into a new worktree, but
    not `crucible.toml`, whose `[client] url` names the board the project's clients post to (Crucible
    0.3.0). Without it, a client in the worktree falls back to the default board and is refused with
    `404 unknown project`. `start` copies `crucible.toml` from the main tree when it exists, never
    committed, and reports it on its `env:` line; a project without one is unaffected. Tested in
    `tests/test_worktree_flow.py`.
14. **Markdown lint findings in the shipped skills** (found 2026-10-29). pi-lens's markdownlint reports
    MD032 (lists not surrounded by blank lines) in `skills-src/model-b/references/sub-agent-procedure.md`,
    where § "Code quality" starts its list directly under the heading. The shipped skills and references
    are swept for markdownlint findings and fixed as text-only edits, with each fix checked against the
    gates that read those files.
