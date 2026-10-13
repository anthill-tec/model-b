# CR-MDB-056 — Test runs go only through the Crucible clients

**Status:** PENDING (filed 2026-10-08; gap analysis and pre-review 2026-10-13)
**Type:** feature (agent definitions, stack files, skills, guard test)
**Priority:** P1 — release 1.0.0, wave 2.
**Depends on:** CR-MDB-057 (board-authoritative: read `queue`)
**Labels:** agents, skills, crucible, enforcement
**Design reference:** DN-multi-harness-deploy-model §D21 and its 2026-10-13 amendments, §D18; PRD D5;
Crucible #1428/#1430/#1432.

## Context

Crucible's sub-agents iterated a whole session with raw runners (`python -m unittest`, `bun test`,
`bunx playwright test --grep …`) and filed only the final suites, so nothing streamed to the board.
Model B's definitions did not stop it:
- the GREEN template says "If running manually, parse the report…", and the RED template calls the
  client the "best path";
- the stack files allow raw runners by name: `python.toml` ("ALLOWED — `python -m unittest`/`pytest`",
  "run `python3 tests/test_*.py` directly", "if you ever run xmlrunner by hand"), `bun.toml` ("ALLOWED —
  `bun test`"; tier guidance "Run the declared script for the tier"), `quarkus.toml` ("ALLOWED — `mvn
  test`/`verify`", "`mvn -q clean test-compile`"), `arduino.toml` (`make junit` from `tests/native/`);
- `crucible-report-python` §B teaches `.venv/bin/pytest … --junitxml` and a hand ingest through an inline
  `urllib` module; `crucible-report-rust` carries a "Manual Patterns (fallback only)" module; the arduino,
  bun and java bundles call "direct `curl`/`fetch` against the v2 endpoints" the fallback;
- `auto-ingest` is offered for "if you already ran the tests yourself" (`crucible-report-rust`, the RED
  template's "+ auto-ingest", per-role table rows) — a raw run followed by `auto-ingest` is the incident;
- some bundles describe what the client runs in code spans ("Runs `bun test` with a JUnit reporter");
- `AGENTS.md`'s Testing and Development Commands sections show raw `python3 -m unittest` commands.

## Scope

### §S1 — The rule

Every test run goes through the stack's Crucible client: a targeted iteration, a single file, a
one-test filter, a regression, and the orchestrator's own runs (a baseline, the pre-merge gate's
empty-`HOME` run, a run under another interpreter through the client's `--python`). Never a runner
invoked directly. A runner the client cannot drive is a client gap, raised with the orchestrator, who
raises it with Crucible. A brief that says otherwise is refused and escalated (`ESCALATION:`), never
followed. A blocking hook's escape hatch (`ALLOW_RAW_<RUNNER>=1`) is used only with the orchestrator's
approval. Two client gaps are known and named where the rule is stated: the python client drives
`unittest` only (a pytest project), and `bun-crucible.py test` takes no test-name filter (a one-test
bun run).

It is stated in:
- **the four role templates** (`generator/templates/{red,green,fix,verify}.md.tmpl`), with "If running
  manually…", "best path" and the RED step's "+ auto-ingest" removed;
- **the five stack files** (`generator/stacks/*.toml`): every "ALLOWED" list names client verbs only;
  python's stdlib-only check is `test --python <interpreter>`; the "run xmlrunner by hand" sentence is
  removed; bun's tier guidance names the client's tier verbs; quarkus's compile check is the client's
  `compile`; arduino's native suite runs through the arduino client;
- **the sub-agent procedure** and **`orchestration-common`** (the orchestrator's own runs);
- **the `crucible` skill** (its lifecycle, its verb table and "Who runs what");
- **the `gap-analysis` skill's Step 0** (the baseline is measured through the client);
- **`AGENTS.md`** (Testing and Development Commands): only client commands — the full suite, `--tests`
  for a module or class, the empty-`HOME` run, and `--python` for another interpreter.

### §S2 — The hand-run-and-ingest path is removed; `auto-ingest` is for recovery only

- `crucible-report-python`: §B and the inline `urllib` helper module go, with every pointer to them.
- `crucible-report-rust`: the "Manual Patterns (fallback only)" module goes, with its pointers.
- The arduino, bun and java bundles: the "direct `curl`/`fetch` … is the fallback" sentences go.
- **`auto-ingest`'s only sanctioned use** is re-ingesting a report that a client run produced when that
  run's own ingest failed. Every "if you already ran the tests yourself" sentence and every per-role row
  offering `auto-ingest` as a run path goes; the `crucible` skill and the bundles state the recovery use.
- A description of what the client runs says so in plain words, not in a code span.
- The bundles' "API Endpoint Reference" tables stay, as reference.

### §S3 — The guard test

A structural test fails when a guarded file shows a runner invocation in a code span or on a
fenced-block line, unless a prohibition governs it: a whole-word, case-insensitive "never", "do not",
"must not" or "not" appearing earlier in the same sentence as the runner span. A fenced-block line is
judged on its own; prose around a fence never exempts it.

The runner is matched as a whole command word at a command position — the start of the span or line,
or after `&&`, `||`, `;`, `|`, a leading `VAR=value`, or one of `env`, `timeout <n>`, `nice`, `time`:
- a python interpreter (bare, versioned or a path, e.g. `.venv/bin/python`), with any options, then
  `-m unittest`, `-m pytest`, `-m xmlrunner` or `-m coverage run`;
- `pytest` or `py.test` (bare or a path), `uv run pytest`, `coverage run -m <runner>`;
- `bun test`, `bun run test…`, `npm test`, `npm run test…`, `bunx`/`bun x`/`npx` `playwright test`,
  `playwright test`;
- `cargo test`, `cargo nextest`, `cargo llvm-cov`;
- `mvn`/`mvnw`/`./mvnw` with the goal `test`, `verify`, `integration-test` or `test-compile`, or a
  `surefire:`/`failsafe:` goal (exact goals);
- `make junit`.

A client invocation (`<stack>-crucible.py …`) and a non-runner mention (`[tool.pytest]`, `pytest.ini`,
`pytest-cov`, `/tmp/pytest-collect.txt`, `mvn package`) are never runner invocations.

Guarded: `skills-src/` except `skills-src/memory-templates/`, `contracts/`, `AGENTS.md`,
`generator/templates/`, `generator/stacks/`, `generator/agents/` and `.pi/agents/`.

### §S4 — Rendered definitions

`generator/agents/*` (all four roles, all five stacks) are regenerated with `generator/build.py build`;
Model B's `.pi/agents/python-*` are re-rendered through `modelb_axi.agents` (the library, in a sandbox —
never the `modelb-axi` CLI against the real installation), and a test keeps each `.pi/agents/python-*`
byte-identical to its `generator/agents/` counterpart.

### §S5 — The gates this change moves

Each is updated in the cycle that changes what it pins:
- `tests/test_agent_generator.py`: `STACK_ANCHORS` (its `"bun test"` and `"mvn"` anchors) name the
  client invocations the stack files now carry.
- `tests/test_generator_role_contract.py`: the `tier_guidance` checks follow bun's new tier guidance.
- `tests/test_skill_bundle_guards.py`: `HTTP_BODY_BUNDLES` becomes empty and its test asserts that; the
  `urllib`-block exemption of the raw-HTTP retirement test is removed; `V2_ENDPOINTS_BY_BUNDLE` and the
  bundle-floor test hold with the endpoint tables kept.
- `tests/test_suite_hygiene.py` `AgentsMdTestingSectionS6Test`: the Testing section's anchors follow the
  client commands.
- `generator/build.py --check`; the rendered RED, GREEN, FIX and VERIFY definitions move with the
  templates and stack files.
- `AGENTS.md`'s module count and baselines are re-measured.

## Acceptance criteria

- [ ] **Each role template** states the rule of §S1 — every run through the client, never a runner
      directly, a client gap raised, a contrary brief refused and escalated, the escape hatch only with
      the orchestrator's approval, the two known client gaps — and none admits a manual run ("If running
      manually", "best path", "+ auto-ingest" gone).
- [ ] **Each stack file** names only client verbs where it lists allowed runs, and carries no direct
      runner instruction (python's stdlib-only check via `test --python`; bun's tier guidance via the
      client's tier verbs; quarkus's compile via the client; arduino's native suite via the client).
- [ ] **Every rendered definition** in `generator/agents/` (4 roles × 5 stacks) carries the rule;
      `generator/build.py --check` is clean; each `.pi/agents/python-*` is byte-identical to its
      `generator/agents/` counterpart, asserted by a test.
- [ ] **The sub-agent procedure, `orchestration-common`, the `crucible` skill and `gap-analysis`'s Step
      0** each state the rule as §S1 assigns it, the orchestrator's own runs included.
- [ ] **`AGENTS.md`** (Testing and Development Commands) shows only client commands: the full suite,
      `--tests` for a module or class, the empty-`HOME` run, `--python` for another interpreter.
- [ ] **`crucible-report-python`** has no §B, no `urllib` helper module and no pointer to either;
      **`crucible-report-rust`** has no "Manual Patterns" module and no pointer to it; the **arduino, bun
      and java** bundles have no "direct `curl`/`fetch` … fallback" sentence; the endpoint tables remain.
- [ ] **`auto-ingest`** appears in the skills, bundles and templates only as recovery — re-ingesting a
      report a client run produced when its ingest failed; no text offers it after a run made outside
      the client, and no per-role row lists it as a run path.
- [ ] **No guarded file** names a runner in a code span outside a governed prohibition.
- [ ] **The guard test** covers exactly §S3's guarded set and runner set, passes on the tree, and proves
      its detector on sample text: each runner form of §S3 (each wrapper too) is caught as an
      instruction; a line where "not" sits in an unrelated clause is caught; a governed prohibition, a
      plain-words description, a `<stack>-crucible.py` invocation and each non-runner mention of §S3 are
      not; a fenced line is not exempted by prose above the fence.
- [ ] **Gates that hold:** every gate §S5 lists, updated as it says; the full suite through the client
      with real `HOME` and with an empty `HOME` (the temp home empty afterwards); `AGENTS.md`'s module
      count and baselines re-measured.

## Non-goals

- The blocking hooks (CR-MDB-062), the test-interpreter probe (CR-MDB-063) and the Python floor
  (CR-MDB-064).
- A CI workflow (CR-MDB-058) and the no-mistakes gate's own test step: they run outside any agent
  session.
- Closing the two client gaps: they are raised with Crucible.
- The memory templates (CR-MDB-060 carries the rule into the facts).
- The Roundhouse root `AGENTS.md` (a root-session CR).
- Rewriting closed specs, `archive/` or `audits/`.
