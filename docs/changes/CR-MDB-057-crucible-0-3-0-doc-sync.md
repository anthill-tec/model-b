# CR-MDB-057 — Crucible 0.3.0 doc-sync

**Status:** PENDING — spec locked 2026-10-13 (gap analysis and pre-review folded); awaiting approval
**Type:** refactor (skills, contract, scaffold, hook, tests)
**Priority:** P1 — release 1.0.0, wave 2.
**Depends on:** none (board-authoritative: read `queue`)
**Labels:** crucible, doc-sync, scaffold, hooks, release
**Design reference:** DN-multi-harness-deploy-model §D21; `skills-src/CRUCIBLE-HANDOVER.md` § Maintenance
contract; Crucible #1432 (0.3.0 client changes), #1436 (`history`), #1443 (status contract 3.0.0),
#1445 (`crucible.toml` `[client]` resolution); the installed 0.3.0 clients' `--help`.

## Context

Crucible 0.3.0 changed the client surface Model B documents and depends on. Measured on the installed
clients (all five carry the same surface):
- the clients no longer read `$CRUCIBLE_URL` (arduino `$CRUCIBLE_BASE`); the board is `[client] url`
  (a full base URL) read from the FIRST `crucible.toml` that exists and parses, in this order: the
  project's (at the project root — `--project-dir`, else the client's project-dir variable, else the
  git top level of the working directory), the install's (beside `clients/`), the shipped one
  (`http://localhost:3849`, the production board). `[client]` comes from that one file only;
- `gate-run` reads the steps a project never runs from `crucible.toml` `[gate] skip`; an explicit
  `--skip` replaces it, and `--skip ""` skips nothing;
- `status` follows status contract 3.0.0 (below);
- new verbs and flags on all five clients: `history`, `landings`, `project-meta`, `cycle-skip`,
  `gate-respond`, `cr-plan --points`, `queue --fields`/`--full`, and `--cycle`/`--release` on every
  run verb.

Model B carries four defects against it:
- `test_filled_env_key_resolves_through_the_installed_client`
  (`CrucibleClientResolvesScaffoldedKeyTest`, `tests/test_project_registry_schema.py`) points the
  installed client at a stub server through `$CRUCIBLE_URL`. On 0.3.0 the client ignores it: the test
  fails, and its read-only request reaches the production board with a stub key.
- The `ambient-board-status` hook reads an all-closed board as "no plan filed (an empty board is
  definitive)" and drops `last closed`.
- `AGENTS.md` runs `gate-run … --skip ci` on every call; the `crucible` skill and
  `contracts/crucible-envelope.md` say that without `--skip` the gate blocks until `ci_timeout`, which
  no longer holds once `[gate] skip` is declared. The contract's installed product facts still name
  product 0.2.2 and status contract 2.0.0.
- The skills never mention the new verbs, and give register/unregister and board-inspection examples
  as raw `curl` to a hard-coded `localhost:3849`.

## Scope

### §S1 — The connection is project configuration

- No skill, contract, scaffolded file, rendered definition, hook or test steers a Crucible client
  through `$CRUCIBLE_URL`, `$CRUCIBLE_BASE`, `$CRUCIBLE_PORT` or `$CRUCIBLE_HOST`.
- **The `crucible` skill** states the resolution: `[client] url` from the first `crucible.toml` that
  exists and parses — the project's, the install's, the shipped one (`http://localhost:3849`) — taken
  from that file only, so a project file without `[client]` sends the client to the shipped default.
  It names no fixed host or port as "the" board; its intro stops naming `localhost:3849`. Its existing
  checkout sentence stays the one sentence that states the checkout rule and its reason.
- **The stub-board test.** `CrucibleClientResolvesScaffoldedKeyTest` points the client at its stub by
  writing `[client] url = "http://127.0.0.1:<port>"` into the scaffolded project's own `crucible.toml`,
  and runs the client with `--project-dir` naming that project. No request leaves for any other board.

### §S2 — The gate's skipped steps are declared in `crucible.toml`

- **`init`** writes one `crucible.toml`, at the root, beside the root `.env`. It declares `[gate]`
  `skip = ["ci"]` and has no `[client]` table; a comment says why: no-mistakes' `ci` step is PR-based,
  and a git-flow project that merges directly has no PR for it to watch. Because the client reads
  `[client]` from the first file it finds, this file also fixes the project's board to the shipped
  default (the production board), whatever the install's `crucible.toml` declares — the board every
  Model B project uses. A monorepo sub-project gets
  none: the client resolves the project directory to the repository root, which holds the project's
  only `CRUCIBLE_PROJECT_KEY`. `plan_files` lists the file.
- **Model B's own repository** tracks a `crucible.toml` with the same `[gate]` declaration.
- **The `crucible` skill, `contracts/crucible-envelope.md` and `AGENTS.md`** (Workflow rules, the
  wave-boundary gate) run `gate-run --intent <goal> --agent <id>` with no `--skip`. They say the
  project's `[gate] skip` applies, an explicit `--skip` replaces it, and `--skip ""` skips nothing;
  the PR-based-`ci`/`ci_timeout` rationale stays stated with the declaration.

### §S3 — The project metadata map

- **The root `AGENTS.md`'s Setup section** that `init` writes gains one task, directly after the
  Crucible registration task (and before the Sandesh task in multi mode): once the key is filled,
  register the orchestrator (`register --agent <label> --role ORCHESTRATOR`), then mirror the root
  `.env`'s keys with `project-meta --set KEY=VALUE … --agent <label>`, and re-run it whenever `.env`
  changes. `<label>` is the project's rendered orchestrator label (`_orchestrator_label`), passed to
  the Setup-section renderer. `CRUCIBLE_PROJECT_KEY` is not mirrored. Where `tools` records Crucible
  absent, the task names the remediation first, as the registration task does. The task is not a
  registration task: the project's one Crucible registration task stays the only one.
- **The `crucible` skill** documents `project-meta`: a read without `--agent`; a write with
  `--set`/`--unset` and `--agent`, as a registered `ORCHESTRATOR` (an unregistered id is refused 409).

### §S4 — The session-start hook reads status contract 3.0.0

Crucible 0.3.0's `status` follows status contract **3.0.0**: `plans` holds the open plans only and
`count` counts them; `filed` is the number of plans ever filed (open, closed or aborted), and is `null`
when the board is unreachable; `lastClosedCr` is the last closed CR, or `null` when none has closed.
`ambient-board-status` pins `STATUS_CONTRACT_VERSION = "3.0.0"`, its docstring cites that version,
and it tells the states apart by `count` and `filed` alone:
- `count > 0`: the open rows;
- `count == 0` and `filed > 0`: "no open plan";
- `count == 0` and `filed == 0`: "no plan filed";
- `filed` null with a `status-unavailable` warning: the board-unavailable degrade note — null is
  unknown, never 0.

In every reachable state it adds `last closed: <id>` when `lastClosedCr` is not null; `lastClosedCr`
never decides the state (a board whose only plans were aborted has `filed > 0` and no last closed
CR). An envelope without `filed` (a 2.0.0 client) keeps today's `count`-based reading. The other
degrade paths are unchanged. The hook's tests carry a 3.0.0 envelope for each of the four states, an
aborted-only board, and a 2.0.0 envelope.

### §S5 — The verb surface in the `crucible` skill and the contract

The per-stack table and the verb sections match the installed 0.3.0 `--help`, and say these verbs
are on all five clients:
- **The run verbs** — `test`, the tier verbs (`unit`, `module`, `integration`, `e2e`, `bdd`),
  `regression` and `pre-merge-gate`; not `auto-ingest` — take `--cycle` (bind the run's agent to an
  active cycle when it did not register bound) and `--release <label>` (file the run as release
  verification under a release the roadmap declares, instead of a cycle; never beside `--cycle`), with
  the exceptions the installed `--help` shows, which the skill names: rust `regression` takes no
  `--cycle`.
- **`history`** lists past releases: a release appears once it has shipped or has a completed CR, so
  planned releases are read with `queue --fields release,seq,points,dependsOn`. `queue --full` shows
  every column, including `warning`.
- **`status`** shows the work in flight (status contract 3.0.0); `landings` lists each closed CR's
  merge commit.
- **`cr-plan --points`** takes a story-point score on the scale 1, 2, 3, 5, 8, 13. Re-sending a CR's
  current title, release and wave with `--points` changes only its points.
- **`cycle-add`.** A `fix` append needs nothing more. A `--before <cycle id>` insert, or any other
  kind, is a recorded plan change, and needs `--reason`, `--cause` (`spec-design` or `gap-analysis`)
  and `--spec-ref`.
- **`cycle-skip <cycle id>`** takes the same three flags; a skipped cycle is recorded as a failure.
- **`gate-run`** gives each run its own board identity, `<caller>·gate·<run>`, removed when the run
  ends; the decision stays the caller's (#1432). **`gate-respond`** answers a held step with
  `--action approve|fix|skip`; a decision the tool accepted is recorded even when the wait elapses.
  It has no `--release`. After a wait that elapsed while a step was still running, check `status` and
  reattach with `gate-run --intent <goal>` (#1432).
- **Client output goes to a file** — `--log <path>` where the verb takes it, a redirect otherwise —
  never through `| head`. The skill names where `--log` is absent: rust `regression`, and
  `pre-merge-gate` on the arduino, mvn and rust clients.
- **Every stack has a client.** The clause about a "clientless stack" and its "documented urllib
  procedure" is removed.

`contracts/crucible-envelope.md`'s installed product facts state product 0.3.0 and status contract
3.0.0. `skills-src/git-workflow/SKILL.md` § Releases files the release's verification runs —
`regression` and `pre-merge-gate` — with `--release <label>`.

### §S6 — Register and board-inspection examples use the client

- **`crucible-register`'s** register and unregister examples are the client's `register` and
  `unregister` verbs, not `curl` to `/api/v2/agents/…`; it joins the bundles whose register examples
  are checked as CLI flags.
- **The `crucible-report-*` skills' event examples** (`curl … /api/v2/events …`: listing by project or
  id, and `-X DELETE`) are removed — no client verb lists or deletes events; the board is read with
  `status`, `history` and `queue`.
- Every remaining example names no fixed host or port. The inline `urllib` run-and-ingest modules and
  the bundles' "direct `curl`/`fetch` against the v2 endpoints is the fallback" prose are CR-MDB-056's.

### §S7 — The gates this change moves

Each is updated in the cycle that changes the text it pins:
- `tests/test_ambient_status_contract.py`: `STATUS_CONTRACT_VERSION`, the docstring and the degrade
  note name 3.0.0.
- `tests/test_client_verb_sweep.py`: `test_s4c_envelope_contract_cites_status_contract_document_version`
  (3.0.0), `test_s4c_envelope_contract_matches_the_installed_product_facts` (0.3.0), the
  `--skip`-rationale gate asserting the declaration form, and `NORMATIVE_SURFACES` extended to
  `AGENTS.md`.
- `tests/test_skill_bundle_guards.py`: `crucible-register` moves from `HTTP_BODY_BUNDLES` to the CLI
  register-flag family (`RegisterFlagSurfaceTest`); `V2_ENDPOINTS_BY_BUNDLE` drops the routes no
  bundle documents any more.
- `tests/test_project_setup_section.py`: `setup_task_findings` still finds exactly one registration
  task with the `project-meta` task present.
- `test_s1_crucible_skill_states_the_checkout_rule_and_reason_in_one_sentence` still finds exactly
  one sentence.
- The verbs-the-released-clients-expose test (`test_client_examples_use_verbs_the_released_clients_expose`)
  is extended to the flags this CR names, rather than a parallel gate added.
- The scaffold's planned/emitted file lists (`plan_files`, the golden emission sets) include
  `crucible.toml`.

## Acceptance criteria

- [ ] **No `$CRUCIBLE_URL`, `$CRUCIBLE_BASE`, `$CRUCIBLE_PORT` or `$CRUCIBLE_HOST`** appears as a way
      to point a client in `skills-src/`, `contracts/`, `AGENTS.md`, `generator/`, `hooks-src/`,
      `modelb_axi/` or `tests/`; a grep gate asserts it, excluding its own pattern literals.
- [ ] **The `crucible` skill** names no fixed host or port as "the" board, states `[client] url`, the
      resolution order (project, install, shipped) and the first-file-only rule, and its checkout
      sentence is still the single one
      `test_s1_crucible_skill_states_the_checkout_rule_and_reason_in_one_sentence` finds.
- [ ] **`CrucibleClientResolvesScaffoldedKeyTest`** passes against the installed 0.3.0 client with
      `[client] url` naming the stub in the scaffolded project's `crucible.toml` and `--project-dir`
      naming that project; its stub records every request, and
      the test asserts the client reached the stub with the filled key.
- [ ] **`init`** (standalone and monorepo, solo and multi) writes exactly one `crucible.toml`, at the
      root, with `[gate]` `skip = ["ci"]`, the rationale comment and no `[client]`; no sub-project gets
      one; `plan_files` lists it and `emitted` matches the files on disk.
- [ ] **Model B's repository** tracks `crucible.toml` with `[gate]` `skip = ["ci"]`.
- [ ] **The `crucible` skill, `contracts/crucible-envelope.md` and `AGENTS.md`** show
      `gate-run --intent <goal> --agent <id>` with no `--skip`, and state the `[gate] skip`
      declaration, that `--skip` replaces it, `--skip ""`, and the PR-based-`ci`/`ci_timeout`
      rationale; `test_client_verb_sweep`'s `--skip`-rationale gate covers all three surfaces.
- [ ] **The Setup section `init` writes** carries the `project-meta` task directly after the
      registration task (before the Sandesh task in multi mode): `register --agent <label> --role
      ORCHESTRATOR`, then `project-meta --set` of the root `.env` keys except `CRUCIBLE_PROJECT_KEY`
      with `--agent <label>`, re-run on any `.env` change, with the project's real orchestrator label,
      and the Crucible remediation first when Crucible is absent; `setup_task_findings` still finds
      exactly one registration task.
- [ ] **`ambient-board-status`** pins `STATUS_CONTRACT_VERSION = "3.0.0"` (docstring and degrade note
      too) and prints, for 3.0.0 envelopes: the open rows when `count > 0`; "no open plan" when
      `count == 0` and `filed > 0`; "no plan filed" when `count == 0` and `filed == 0`; the
      board-unavailable degrade note when `filed` is null with `status-unavailable`. It adds
      `last closed: <id>` exactly when `lastClosedCr` is not null, including the aborted-only board
      (`filed > 0`, `lastClosedCr` null → "no open plan", no last-closed line). A 2.0.0 envelope (no
      `filed`) renders as today.
- [ ] **The `crucible` skill's per-stack table and verb sections** name, for all five clients:
      `--cycle` and `--release` on the run verbs (not `auto-ingest`) with the exception named (rust
      `regression`: no `--cycle`), `history`, `landings`,
      `project-meta`, `cr-plan --points` (scale 1–13), `cycle-add` (`fix` append; `--before` and other
      kinds with `--reason`/`--cause`/`--spec-ref`), `cycle-skip`, `gate-respond` (actions, no
      `--release`, the reattach), the gate run identity, `status` as work in flight,
      `queue --fields`/`--full`, and output to a file (`--log` where the verb takes it, else a
      redirect; the verbs without `--log` named), never `| head`. No "clientless stack" clause remains.
- [ ] **`contracts/crucible-envelope.md`** states product 0.3.0 and status contract 3.0.0.
- [ ] **Every flag the skill and the contract name** exists in the installed client's `--help` for
      that verb, checked by the extended verbs-the-released-clients-expose test, which skips naming
      the client manifest when the clients are absent.
- [ ] **`git-workflow` § Releases** files `regression` and `pre-merge-gate` release verification runs
      with `--release <label>`.
- [ ] **`crucible-register` and the `crucible-report-*` skills** contain no `curl` to `/api/v2/` and no
      hard-coded host or port in a register, unregister or event example; register/unregister are
      client verbs, and the event examples are gone.
- [ ] **Gates that hold:** every gate §S7 lists, updated as it says; the full suite with real `HOME`
      and with an empty `HOME` (the temp home empty afterwards); `generator/build.py --check`; the PRD
      gate; `HEADING_RENAMES` unchanged; `AGENTS.md`'s module count and baselines re-measured.

## Non-goals

- Changing Crucible's verbs, envelope or status contract.
- The test-run rule, the raw-runner guard, the blocking hooks, the inline `urllib` run-and-ingest
  modules and the "direct v2 fallback" prose (CR-MDB-056).
- The scoring rule and the orchestration rules (CR-MDB-059); release notes (CR-MDB-058, which follows
  this CR on `git-workflow` § Releases).
- A `[client]` table in a scaffolded project: Model B projects use the production board.
- A `crucible.toml` per monorepo sub-project, and writing one into projects scaffolded before this CR
  (CR-MDB-055, `migrate`).
- Rewriting closed specs, `archive/` or `audits/`.
