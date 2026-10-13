# CR-MDB-056 — Test runs go only through the Crucible clients

**Status:** PENDING (filed 2026-10-08; gap analysis 2026-10-13)
**Type:** feature (agent definitions, skills, hooks, scaffold, guard test)
**Priority:** P1 — release 1.0.0, wave 2.
**Depends on:** CR-MDB-057 (board-authoritative: read `queue`)
**Labels:** agents, skills, hooks, crucible, enforcement
**Design reference:** DN-multi-harness-deploy-model §D21 (and its 2026-10-13 amendment) and §D18; PRD D5;
`hooks-src/schema.md` v1; Crucible #1428/#1430/#1432.

## Context

Crucible's sub-agents iterated a whole session with raw runners (`python -m unittest`, `bun test`,
`bunx playwright test --grep …`) and filed only the final suites, so nothing streamed to the board.
Model B's definitions did not stop it:
- the GREEN template says "If running manually, parse the report…", and the RED template calls the
  client the "best path" — both admit a raw run;
- no template states a universal rule or tells an agent to refuse a brief that says otherwise;
- `crucible-report-python` §B teaches `.venv/bin/pytest … --junitxml` followed by a hand ingest through
  an inline `urllib` module; `crucible-report-rust` carries a "Manual Patterns (fallback only)" module;
  the arduino, bun and java bundles call "direct `curl`/`fetch` against the v2 endpoints" the fallback;
- some bundles describe what the client runs in code spans ("Runs `bun test` with a JUnit reporter"),
  indistinguishable from an instruction;
- `AGENTS.md` documents raw `python3 -m unittest` commands for the suite, a module, a class and the
  empty-`HOME` run;
- only cargo and mvn have blocking hooks; `init` emits none for python or bun.

The hooks see what an agent runs: the Pi runtime maps `bash`, `ctx_shell` (raw or not) and a
shell-language `ctx_execute` to the neutral `bash` class (`hooks-src/schema.md`). A client's own runner
subprocess is never a tool call, so a hook never sees it.

## Scope

### §S1 — The rule

Every test run goes through the stack's Crucible client: a targeted iteration, a single file, a
one-test filter, a regression, and the orchestrator's own runs (a baseline, the pre-merge gate's
empty-`HOME` run, a second interpreter through the client's `--python`). Never a runner invoked
directly. A runner the client cannot drive is a client gap, raised with the orchestrator. A brief that
says otherwise is refused and escalated (`ESCALATION:`), never followed. The escape hatch of a blocking
hook (`ALLOW_RAW_<RUNNER>=1`) is used only with the orchestrator's approval.

It is stated in:
- **each of the four role templates** (`generator/templates/{red,green,fix,verify}.md.tmpl`), with the
  "If running manually…" and "best path" wording removed; the rendered definitions
  (`generator/agents/*`, all stacks) and Model B's `.pi/agents/python-*` are regenerated from them;
- **the sub-agent procedure** (`skills-src/model-b/references/sub-agent-procedure.md`) and
  **`orchestration-common`** (the orchestrator's own runs);
- **the `crucible` skill** (its lifecycle and "Who runs what" sections);
- **the `gap-analysis` skill's Step 0** (the baseline is measured through the client);
- **`AGENTS.md`'s Testing section**, whose commands become client commands: the full suite, one
  module or class (`--tests`), the empty-`HOME` run, and the second-interpreter run (`--python`).

### §S2 — The hand-run-and-ingest path is removed

From the `crucible-report-*` bundles:
- `crucible-report-python`: §B (pytest → JUnit XML → hand ingest) and the inline `urllib` helper
  module, with every sentence that points at them;
- `crucible-report-rust`: the "Manual Patterns (fallback only)" module and its pointers;
- the arduino, bun and java bundles: the "direct `curl`/`fetch` against the v2 endpoints is the
  fallback" sentences;
- every bundle: a description of what the client runs says so in plain words, not in a code span.

### §S3 — The guard test

A structural test fails when a guarded file shows a runner invocation in a code span or a fenced
block, except on a line that states a prohibition (it contains "never", "do not" or "not"). The runner
set is: `python[3[.N]] -m unittest`, `python[3[.N]] -m pytest`, `pytest` (bare or as a path such as
`.venv/bin/pytest`), `uv run pytest`, `bun test`, `bunx playwright test`, `npx playwright test`,
`cargo test`, `cargo nextest`, `cargo llvm-cov`, `mvn`/`mvnw`/`./mvnw` with `test` or `verify`, and
`make junit`. A client invocation (`<stack>-crucible.py …`) is never a runner invocation.

Guarded: `skills-src/` except `skills-src/memory-templates/`, `contracts/`, `AGENTS.md`,
`generator/templates/`, `generator/stacks/`, `generator/agents/` and `.pi/agents/`. The test proves its
detector both ways on sample text: an instruction is caught, a prohibition line and a client
invocation are not.

### §S4 — Blocking hooks for python and bun

Two protocol scripts in `hooks-src/scripts/`, built like `block-direct-cargo-test` and
`block-direct-mvn-test` (python3, stdlib only, the neutral `bash` payload, exit 0 allow / exit 2 +
`{"decision":"block","reason":…}` block, a command-position detector, fail-open on an unparseable
payload or command):
- **`block-direct-python-test`** blocks `python[3[.N]] -m unittest`, `python[3[.N]] -m pytest`,
  `pytest`/`py.test` (bare or as a path) and `uv run pytest`, in a python project (`pyproject.toml`,
  `setup.py` or `setup.cfg` in the working directory or an ancestor). Escape hatch:
  `ALLOW_RAW_PYTHON=1`.
- **`block-direct-bun-test`** blocks `bun test`, `bunx playwright test`, `npx playwright test` and
  `playwright test`, in a bun project (`package.json` in the working directory or an ancestor).
  Escape hatch: `ALLOW_RAW_BUN=1`.

Each block reason names the stack's installed client and its `test` invocation, and the escape hatch.
A client invocation is never blocked.

**`init`** (`scaffold._hook_instances`) emits `block-direct-python-test` for a python stack and
`block-direct-bun-test` for a bun stack, `pre-tool-use`, `matcher = "bash"`, `fail_direction =
"closed"`, as it does for cargo and mvn. The installer deploys both scripts with the others.

### §S5 — The gates this change moves

Each is updated in the cycle that changes what it pins:
- `tests/test_skill_bundle_guards.py`: `HTTP_BODY_BUNDLES` becomes empty (no bundle carries an HTTP
  register body any more) and the `urllib`-block exemption of the raw-HTTP retirement test is removed;
  `V2_ENDPOINTS_BY_BUNDLE` drops the routes no bundle documents any more.
- `tests/test_hooks.py`: the hook-script set includes the two new scripts.
- `tests/test_scaffold.py`: the per-stack hook emission table gains the python and bun rows.
- The installer's deployed-asset sets include the two new scripts.
- `generator/build.py --check` and the RED/GREEN/FIX rendered definitions move with the templates.
- `AGENTS.md`'s module count and baselines are re-measured.

## Acceptance criteria

- [ ] **Each of `red`, `green`, `fix` and `verify.md.tmpl`** states the rule of §S1 — every run
      through the client, never a runner directly, a client gap raised, a contrary brief refused and
      escalated, the escape hatch only with the orchestrator's approval — and none admits a manual
      run ("If running manually", "best path" gone). Every rendered definition in `generator/agents/`
      and Model B's `.pi/agents/python-*` carries it; `generator/build.py --check` is clean.
- [ ] **The sub-agent procedure, `orchestration-common`, the `crucible` skill and `gap-analysis`'s
      Step 0** each state the rule as §S1 assigns it, the orchestrator's own runs included.
- [ ] **`AGENTS.md`'s Testing section** shows only client commands: the full suite, `--tests` for a
      module or class, the empty-`HOME` run, and `--python` for a second interpreter.
- [ ] **`crucible-report-python`** has no §B, no `urllib` helper module and no pointer to either;
      **`crucible-report-rust`** has no "Manual Patterns" module and no pointer to it; the **arduino,
      bun and java** bundles have no "direct `curl`/`fetch` … fallback" sentence; no bundle names a
      runner in a code span outside a prohibition line.
- [ ] **The guard test** covers exactly the guarded set of §S3 with the runner set of §S3, passes on
      the tree, and proves its detector on sample text: each runner form is caught as an instruction;
      a prohibition line, a plain-words description and a `<stack>-crucible.py` invocation are not.
- [ ] **`block-direct-python-test`** blocks, in a python project, each of: `python -m unittest`,
      `python3 -m unittest discover`, `python3.11 -m pytest`, `pytest`, `.venv/bin/pytest x`,
      `uv run pytest`, and one after `&&`; allows each of: `python3 ~/.crucible/clients/python-crucible.py
      test …`, a runner named inside an argument (`echo "pytest"`), any command outside a python project,
      and any command carrying `ALLOW_RAW_PYTHON=1`; fails open on a malformed payload.
- [ ] **`block-direct-bun-test`** blocks, in a bun project, `bun test`, `bun test x.test.ts`,
      `bunx playwright test`, `npx playwright test --grep t` and `playwright test`; allows
      `python3 ~/.crucible/clients/bun-crucible.py test …`, `bun run build`, any command outside a bun
      project and any command carrying `ALLOW_RAW_BUN=1`; fails open on a malformed payload.
- [ ] **Both block reasons** name the stack's installed client, its `test` invocation and the escape
      hatch.
- [ ] **`init`** emits `block-direct-python-test` for `--stacks python` and `block-direct-bun-test` for
      `--stacks bun` (`pre-tool-use`, `bash`, `closed`), alone and beside other stacks, and neither
      for a project without that stack; the compiled Pi wiring carries each.
- [ ] **The installer** deploys both scripts into the hook-scripts store, executable, recorded in the
      manifest.
- [ ] **Gates that hold:** every gate §S5 lists, updated as it says; the full suite through the client
      with real `HOME` and with an empty `HOME` (the temp home empty afterwards); `HEADING_RENAMES`
      unchanged; the PRD gate; `AGENTS.md`'s module count and baselines re-measured.

## Non-goals

- A boundary against every way to run a command: `lean_ctx`, `ctx_call` and a non-shell `ctx_execute`
  are not seen by the hooks — the hooks deter, the permission policy (CR-MDB-049) bounds.
- An arduino blocking hook (host builds run by hand are only covered by the rule and the guard).
- The memory templates (CR-MDB-060 carries the rule into the facts).
- Wiring Model B's own repository: its wiring is recompiled after this CR merges and the user
  redeploys (DN §D21 amendment).
- Changing Crucible's clients.
- Rewriting closed specs, `archive/` or `audits/`.
