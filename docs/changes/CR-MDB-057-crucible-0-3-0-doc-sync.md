# CR-MDB-057 — Crucible 0.3.0 doc-sync

**Status:** PENDING (filed 2026-10-10; gap analysis 2026-10-13)
**Type:** refactor (skills, contract, scaffold, hook, tests)
**Priority:** P1 — release 1.0.0, wave 2.
**Depends on:** none (board-authoritative: read `queue`)
**Labels:** crucible, doc-sync, scaffold, hooks, release
**Design reference:** DN-multi-harness-deploy-model §D21; `skills-src/CRUCIBLE-HANDOVER.md` § Maintenance
contract; Crucible #1432 (0.3.0 client changes) and #1436 (`history`); the installed 0.3.0 clients'
`--help` (`~/.crucible/clients/<stack>-crucible.py`).

## Context

Crucible 0.3.0 changed the client surface Model B documents and depends on. Measured on the installed
clients (all five carry the same surface):
- the clients no longer read `$CRUCIBLE_URL` (arduino `$CRUCIBLE_BASE`); the board comes from the
  project's `crucible.toml` `[client]`, else the production default `127.0.0.1:3849`;
- `gate-run` reads the steps a project never runs from `crucible.toml` `[gate] skip`; `--skip` replaces it;
- `status` lists only work in flight: `plans` holds open plans, `count` counts them, `filed` counts every
  plan filed, and `lastClosedCr` names the last closed CR;
- new verbs and flags: `history`, `landings`, `project-meta`, `cycle-skip`, `gate-respond`,
  `cr-plan --points`, `queue --fields`/`--full`, and `--cycle`/`--release` on `test`.

Three defects follow on Model B's side:
- `test_filled_env_key_resolves_through_the_installed_client`
  (`CrucibleClientResolvesScaffoldedKeyTest`, `tests/test_project_registry_schema.py`) points the
  installed client at a stub server through `$CRUCIBLE_URL`. On 0.3.0 the client ignores it, so the
  test fails and its read-only request reaches the production board with a stub key.
- The `ambient-board-status` hook reads an all-closed board as "no plan filed (an empty board is
  definitive)" and drops `last closed`, because it tells the two apart by `count`.
- The skills, the contract and `AGENTS.md` name `gate-run --skip ci` on every call, never mention the
  new verbs, and give register/unregister and board-inspection examples as raw `curl` to a hard-coded
  `localhost:3849`.

## Scope

### §S1 — The connection is project configuration

- No skill, contract, scaffolded file or test steers a Crucible client through `$CRUCIBLE_URL`,
  `$CRUCIBLE_BASE`, `$CRUCIBLE_PORT` or `$CRUCIBLE_HOST`.
- **The `crucible` skill** says the client takes its board from the project's `crucible.toml`
  `[client]`, else the production default. It names no fixed host or port as "the" board.
- **The stub-board test.** `CrucibleClientResolvesScaffoldedKeyTest` points the client at its stub by
  writing the stub's address into the scaffolded project's `crucible.toml` `[client]`. No request
  leaves for any other board.

### §S2 — The gate's skipped steps are declared in `crucible.toml`

- **`init`** writes a `crucible.toml` beside every `.env` it writes: the root, and each monorepo
  sub-project. It declares `[gate]` `skip = ["ci"]` and has no `[client]` table. `plan_files` lists it.
  A comment in the file says why: no-mistakes' `ci` step is PR-based, and a git-flow project that
  merges directly has no PR for it to watch.
- **Model B's own repository** tracks a `crucible.toml` with the same `[gate]` declaration.
- **The `crucible` skill, `contracts/crucible-envelope.md` and `AGENTS.md`** (Workflow rules, the
  wave-boundary gate) run `gate-run --intent <goal> --agent <id>` with no `--skip`. They say the
  project's `[gate] skip` applies, and that an explicit `--skip` replaces it (`--skip ""` skips
  nothing). The PR-based-`ci` rationale stays stated with the declaration.

### §S3 — The project metadata map

- **The root `AGENTS.md`'s Setup section** that `init` writes gains a task, after the Crucible
  registration task: mirror the `.env` registry keys onto the board with
  `project-meta --set KEY=VALUE … --agent <orchestrator label>`, and re-run it whenever `.env` changes.
  `CRUCIBLE_PROJECT_KEY` itself is not mirrored. Where `tools` records Crucible absent, the task names
  the remediation first, as the registration task does.
- **The `crucible` skill** documents `project-meta`: a read without `--agent`, and a write with
  `--set`/`--unset` and `--agent`.

### §S4 — The session-start hook reads 0.3.0's `status`

`ambient-board-status` renders the three definitive states from the 0.3.0 envelope:
- open plans present: the open rows, plus `last closed: <id>` when `lastClosedCr` is set;
- no open plan but `filed > 0`: "no open plan", plus `last closed: <id>`;
- `filed == 0`: "no plan filed".

An envelope without `filed` (a pre-0.3.0 client) keeps today's `count`-based reading. The degrade
paths are unchanged. `STATUS_CONTRACT_VERSION` names the status-contract version Crucible confirms
for 0.3.0. The hook's tests carry the measured 0.3.0 envelope for all three states, and a 0.2.x
envelope.

### §S5 — The verb surface in the `crucible` skill and the contract

The per-stack table and the verb sections match the installed 0.3.0 `--help`, and say these verbs
are on all five clients:
- **`test`/`e2e`** take `--cycle` (bind the run's agent to an active cycle when it did not register
  bound) and `--release <label>` (file the run as release verification under a release the roadmap
  declares, instead of a cycle; never beside `--cycle`).
- **`history`** lists past releases: a release appears once it has shipped or has a completed CR, so
  planned releases are read with `queue --fields release,seq,points,dependsOn`. `queue --full` shows
  every column, including `warning`.
- **`status`** shows the work in flight; `landings` lists each closed CR's merge commit.
- **`cr-plan --points`** takes a story-point score on the scale 1, 2, 3, 5, 8, 13. Re-sending a CR's
  current title, release and wave with `--points` changes only its points.
- **`cycle-add`.** A `fix` append needs nothing more. A `--before <cycle id>` insert, or any other
  kind, is a recorded plan change, and needs `--reason`, `--cause` (`spec-design` or `gap-analysis`)
  and `--spec-ref`.
- **`cycle-skip <cycle id>`** takes the same three flags; a skipped cycle is recorded as a failure.
- **`gate-run`** gives each run its own board identity, `<caller>·gate·<run>`, removed when the run
  ends; the decision stays the caller's. **`gate-respond`** answers a held step with
  `--action approve|fix|skip`. It has no `--release`. When its wait elapses while a step is still
  running, the decision was recorded: check `status` and reattach with `gate-run --intent <goal>`.
- **Client output goes to a file** (`--log <path>`, or a redirect), never through `| head`.
- **Every stack has a client.** The clause about a "clientless stack" and its "documented urllib
  procedure" is removed.

`skills-src/git-workflow/SKILL.md` § Releases says the release's verification runs are filed with
`--release <label>`.

### §S6 — Register and board-inspection examples use the client

- **`crucible-register`'s** register and unregister examples are the client's `register` and
  `unregister` verbs, not `curl` to `/api/v2/agents/…`.
- **The `crucible-report-*` skills'** board-inspection examples (`curl … /api/v2/events …`) become
  client read verbs (`status`, `history`, `queue`).
- Every example names no fixed host or port. The inline `urllib` run-and-ingest modules are out of
  scope here (CR-MDB-056).

## Acceptance criteria

- [ ] **No `$CRUCIBLE_URL`, `$CRUCIBLE_BASE`, `$CRUCIBLE_PORT` or `$CRUCIBLE_HOST`** appears as a way
      to point a client in `skills-src/`, `contracts/`, `AGENTS.md`, `modelb_axi/` or `tests/`; a
      grep gate asserts it.
- [ ] **`CrucibleClientResolvesScaffoldedKeyTest`** passes against the installed 0.3.0 client, with
      the stub's address in the scaffolded `crucible.toml` `[client]`. Its stub records every
      request, and the test asserts that the client reached the stub with the filled key.
- [ ] **`init`** (standalone and monorepo, solo and multi) writes `crucible.toml` at the root and
      beside each sub-project `.env`, each with `[gate]` `skip = ["ci"]`, the rationale comment, and no
      `[client]`; `plan_files` lists every one; `emitted` matches the files on disk.
- [ ] **Model B's repository** tracks `crucible.toml` with `[gate]` `skip = ["ci"]`.
- [ ] **The `crucible` skill, `contracts/crucible-envelope.md` and `AGENTS.md`** show
      `gate-run --intent <goal> --agent <id>` with no `--skip`. They state that the project's
      `[gate] skip` applies, that `--skip` replaces it, and the PR-based-`ci`/`ci_timeout` rationale.
      `test_client_verb_sweep`'s `--skip`-rationale gate asserts the declaration form.
- [ ] **The Setup section `init` writes** carries the `project-meta --set` task after the
      registration task, re-run on any `.env` change, excluding `CRUCIBLE_PROJECT_KEY`, with the
      Crucible remediation first when Crucible is absent.
- [ ] **`ambient-board-status`** prints, for the 0.3.0 envelopes: the open rows plus `last closed`;
      "no open plan" plus `last closed` when `count == 0` and `filed > 0`; "no plan filed" when
      `filed == 0`. A 0.2.x envelope renders as today. `STATUS_CONTRACT_VERSION` holds the version
      Crucible confirms.
- [ ] **The `crucible` skill's per-stack table and verb sections** name, for all five clients:
      `test`/`e2e --cycle` and `--release`, `history`, `landings`, `project-meta`, `cr-plan --points`
      (scale 1–13), `cycle-add` (`fix` append; `--before` and other kinds with
      `--reason`/`--cause`/`--spec-ref`), `cycle-skip`, `gate-respond` (actions, no `--release`, the
      timeout reattach), the gate run identity, `status` as work in flight, `queue --fields`/`--full`,
      and output to a file, never `| head`. No "clientless stack" clause remains.
- [ ] **Every flag the skill and the contract name** exists in the installed client's `--help` for
      that verb; a gate reads `--help` and skips, naming the client manifest, when the clients are
      absent.
- [ ] **`git-workflow` § Releases** files the release's verification runs with `--release <label>`.
- [ ] **`crucible-register` and the `crucible-report-*` skills** contain no `curl` to `/api/v2/` and
      no hard-coded host or port in a register, unregister or board-inspection example; those
      examples are client verbs.
- [ ] **Gates that hold:** the full suite with real `HOME` and with an empty `HOME` (the temp home
      empty afterwards); `generator/build.py --check`; the PRD gate; `HEADING_RENAMES` unchanged;
      `AGENTS.md`'s module count and baselines re-measured.

## Non-goals

- Changing Crucible's verbs, envelope or status contract.
- The test-run rule, the raw-runner guard, the blocking hooks and the inline `urllib`
  run-and-ingest modules (CR-MDB-056).
- The scoring rule and the orchestration rules (CR-MDB-059); release notes (CR-MDB-058).
- A `[client]` table in a scaffolded project: Model B projects use the production board.
- Writing `crucible.toml` into projects scaffolded before this CR (CR-MDB-055, `migrate`).
- Rewriting closed specs, `archive/` or `audits/`.
