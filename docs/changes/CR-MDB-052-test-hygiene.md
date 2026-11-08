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
13. **Dropped 2026-11-04 (user ruling): `worktree-flow.py start` copying the project's gitignored
    `crucible.toml`.** Crucible, which asked for it (#1494), withdrew the need (#1519): it is a Solo project
    and works on its feature branch in the main tree, never in a worktree. Only a project whose
    `crucible.toml` names a board other than the installed default would need the copy; a Track's worktree
    falls back to the installed default board, which is the one a project reports to.
14. **Markdown lint findings in the shipped skills** (found 2026-10-29). pi-lens's markdownlint reports
    MD032 (lists not surrounded by blank lines) in `skills-src/model-b/references/sub-agent-procedure.md`,
    where § "Code quality" starts its list directly under the heading. The shipped skills and references
    are swept for markdownlint findings and fixed as text-only edits, with each fix checked against the
    gates that read those files.
15. **The dead older-git branch in the gate lock** (Crucible #1496, user ruling 2026-10-29: folded into
    this CR). `scripts/gate-lock.sh`'s `lock_path()` falls back to resolving a relative `--git-common-dir`
    when `--path-format=absolute` prints nothing, and `contracts/gate-lock.md` § "Lock path derivation"
    keeps an "Older-git fallback" row for it. Git older than 2.31 echoes the unknown option and exits 0, so
    that branch never runs where it was meant to; Crucible removes its twin in `_gate_lock_path`
    (CR-CRU-217). Drop the branch and the row. Decide at gap analysis whether a run outside git keeps the
    shared `/tmp/nai-gate.lock` or runs unlocked, as Crucible's does after CR-CRU-217, and state it in the
    contract. The self-contained comparison in `tests/test_tooling_detachment.py` stays.
16. **The project's `.env` is read with the harness's plain file read** (found 2026-10-30, user ruling
    2026-10-30: folded into this CR). lean-ctx's default `coder` role refuses `ctx_read` on a secret-like
    path, a `.env` file included ("[I/O BOUNDARY] Secret-like path detected"), while `/bootstrap` and
    `/shutdown` tell the orchestrator to read the project's `.env` and the lean-ctx guidance prefers
    `ctx_read` over the plain read. The shipped skills that read `.env` say it is read with the plain
    file read (in Pi, `read`), and `contracts/lean-ctx.md` records the boundary, so lean-ctx's guard
    stays on for real secret files. Gap analysis finds every shipped surface that tells an agent to read
    `.env`, scaffolded and generated text included.
17. **`init`'s default Sandesh project id is not one Sandesh accepts** (found 2026-11-04, scaffolding
    SoL-Pi). `--sandesh-project` defaults to `--name` without whitespace, so `--name "SoL-Pi"` gives `SoL-Pi`,
    and `sandesh setup` refuses it (a project id matches `[A-Za-z][A-Za-z0-9_]*`). `init` validates the
    value, its default included, against that rule before the first write, naming `--sandesh-project`;
    the default drops every character outside it. Gap analysis checks `SANDESH_ADDRESS`, which follows from
    it, and the schema entry's rule.
18. **`init` overwrites a project's existing files** (SoL-Pi #1534, 2026-11-04). Scaffolding an existing
    repository replaced its own `.gitignore` and `AGENTS.md`; only an existing `CHANGELOG.md` is protected
    today. `init` refuses, before the first write, a target where any file it would emit already exists
    and is not Model B's own (no generated marker), naming each such file and pointing at `migrate` as the
    route for an existing project; `--dry-run` reports the same. Gap analysis decides the files a re-run
    on a Model B project may still rewrite (CR-MDB-050 owns re-runs) and the flag, if any, that overrides.
19. **The scaffolded release workflow triggers on `master`** (SoL-Pi #1534). A project whose production
    branch is `main` never fires it. The workflow names the project's production branch: git-flow's
    configured `gitflow.branch.master`, else the repository's default branch, else `master`; gap analysis
    checks every rendered branch reference (`workflows-src/`, `modelb-axi release-workflow`, the release
    rehearsal and the readiness checks of `release-check`).
20. **The scaffolded `test-bun` step runs `bun test` without `--timeout 30000`** (SoL-Pi #1534), the limit
    the bun client applies; the rendered step passes it, as the client does.
21. **The scaffolded `test-python` job runs the tests without installing the project** (SoL-Pi #1554,
    2026-11-08). `workflows-src/release/test-python.yml` runs `python -m unittest discover -s tests -t .`
    straight after `setup-uv`, so a package with runtime dependencies (SoL-Pi's `toon-format`) fails to
    import on the clean runner. The job installs the project first (e.g. `uv pip install --system
    '.[dev]'`; Crucible's `release.yml` uses `pip install '.[dev]'`); gap analysis decides the form for a
    project with no `dev` extra, and checks Model B's own rendering (zero runtime dependencies, so it
    passes today).
