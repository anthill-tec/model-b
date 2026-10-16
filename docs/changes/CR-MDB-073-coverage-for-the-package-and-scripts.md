# CR-MDB-073 — The pre-merge gate measures coverage of the package and every script

**Status:** PENDING — spec (gap analysis and pre-review 2026-10-17).
**Type:** feature (coverage config, the pre-merge gate, a check tool, `AGENTS.md`, the `crucible`
skill's python reference)
**Priority:** P1 — release 1.0.0, wave 2.
**Depends on:** CR-MDB-059, which defines the pre-merge gate's order (board-authoritative: read
`queue`).
**Labels:** tests, coverage, gate
**Design reference:** PRD D5 (the pre-merge gate, and its 2026-10-17 ruling on coverage);
`docs/research/release-automation-crucible-procedure.md` (release 1.0.0 no longer waits for
Crucible 0.4.0).

## Context

Measured 2026-10-17, on develop, with the installed Crucible 0.3.0 python client and coverage.py
7.16.2:

- **No gate measures coverage.** Model B's gate runs are `python-crucible.py test`, with a real
  `HOME`, with an empty `HOME`, and on the clean runner. `AGENTS.md` shows a
  `regression --coverage` example without `--cov-source`.
- **How the client runs coverage.**
  - `regression --coverage` and `pre-merge-gate` run
    `coverage run --source <cov_source> --data-file=test-reports/<agent>/.coverage …`, and then
    `coverage lcov`, both from the project root.
  - `--cov-source` defaults to `crucible_axi,clients`, which measures nothing of Model B. A
    `--source` on the command line overrides a config file's `source`.
  - coverage.py reads the project root's `pyproject.toml`.
  - `pre-merge-gate`'s first step compiles only `tests/` in Model B, whose layout has no `app`.
- **No coverage config.** Model B has no `[tool.coverage]` and no `.coveragerc`.
- **Subprocess measurement works on 0.3.0.**
  - With `[run] patch = subprocess`, the scripts the tests run as subprocesses are traced, the
    extensionless `/usr/bin/python3` hooks included. Without the patch the hooks are absent.
  - A child is measured when its interpreter has coverage.py installed and it inherits the
    environment. Here `/usr/bin/python3` is `sys.executable`, with no `.venv`.
- **Data from earlier runs is merged in.**
  - With the patch, each process writes its own data file. When the client writes the lcov,
    coverage.py combines them into `test-reports/<agent>/.coverage`.
  - Nothing erases that file between runs. The client clears only the JUnit XML.
  - So a later run's lcov includes every earlier run in the same directory. A 16-test run after a
    full run reported the full run's figure.
- **The generated twin.** `scripts/toon.py` is generated from `modelb_axi/toon.py`
  (`generator/build.py`), so it counts the same code twice.
  - `[run] omit` does not remove it, because subprocesses in temp directories still record it.
  - `[report] omit` does: the lcov step applies it.
- **The full suite under coverage, with the patch and the twin omitted:** 3630 tests, 0 failed,
  1 skip.
  - `regression --coverage` took 392 s; `pre-merge-gate` took 385 s. The plain `test` run takes
    about 200 s.
  - The output lands in `test-reports/<agent>/coverage.lcov`.

  | Area | Lines |
  |---|---|
  | `modelb_axi` | 2668/2803, 95.2% |
  | `workflows-src` | 205/217, 94.5% |
  | `hooks-src/scripts` | 913/1030, 88.6% |
  | `scripts` | 402/2071, 19.4% |
  | Total | 4188/6121, 68.4% |

- **Which tests skip depends on the environment:** `PI_CODING_AGENT_DIR`, and whether Crucible's
  clients, `pi` and `sandesh` are installed. So a figure is comparable only under the same sandbox.
- **What the board gets.** The client posts the run's total coverage with the run. It enforces no
  floor and reports nothing per file. Its total is inflated by stale data in the same way.
- **The non-Python script.** `scripts/gate-lock.sh` is outside coverage.py.

## Scope

### §S1 — The coverage config

`pyproject.toml` gains:

- `[tool.coverage.run]`:
  - `source = ["modelb_axi", "scripts", "hooks-src/scripts", "workflows-src", "tools"]`;
  - `patch = ["subprocess"]`.
- `[tool.coverage.report]`: `omit = ["scripts/toon.py"]`.

`source` is what the check tool's areas come from (§S2). The `--cov-source` that `AGENTS.md` names
is `source`, comma-joined, in the same order.

### §S2 — The coverage check tool

`tools/coverage-check.py` is a stdlib-only Python script, run from the project root. It is
repo-only: it is never deployed, unlike the tool scripts in `scripts/`.

- **Invocation:** `python3 tools/coverage-check.py <lcov> [--baseline <path>]`. The baseline
  defaults to `./AGENTS.md`.
- **The areas:** the entries of `[tool.coverage.run] source`, read from `./pyproject.toml` with
  `tomllib`. A record belongs to the area its path starts with.
- **Output on stdout:**
  - a table with one line per area and one for the total, each with lines hit/found and the
    percent to one decimal place;
  - a line naming each expected source file that has no record in the lcov. The expected files
    are the `*.py` files under each area, plus every regular file in `hooks-src/scripts/`, minus
    `[tool.coverage.report] omit` and anything under `__pycache__`;
  - a line naming `scripts/gate-lock.sh` as unmeasured.
- **The baseline:** the one line of the baseline file that starts with `Coverage baseline:`. It
  carries the total as `<hit>/<found>`.
- **The comparison:** exact, by cross-multiplying, so rounding never changes a verdict.
- **Exit codes, with any reason printed on stderr:**
  - 0 when the measured total's ratio is at least the baseline's;
  - 1 when it is lower, naming both figures;
  - 2 when the lcov is missing or has no records, a record lies outside every area, or the baseline
    file has zero or several `Coverage baseline:` lines.
- **It writes nothing.**

### §S3 — The pre-merge gate measures coverage

`AGENTS.md`'s Testing & QA states Model B's pre-merge gate as these steps:

1. **Clear the stale data.** Remove `test-reports/vidushi-mdb/.coverage` and every `.coverage.*`
   beside it. The lcov step merges a run into any data file already there, so a stale one would
   inflate the figure.
2. **The real-`HOME` run:**
   `python3 ~/.crucible/clients/python-crucible.py pre-merge-gate --cov-source <the §S1 list> --agent vidushi-mdb --cycle <last cycle> --log <file>`,
   with `MODELB_HOME`, `XDG_DATA_HOME` and `PI_CODING_AGENT_DIR` each pointed at a temp dir.
3. **The other two runs:** the empty-`HOME` run and the clean-runner run stay `test` runs.
4. **The check:** `python3 tools/coverage-check.py test-reports/vidushi-mdb/coverage.lcov` runs
   against the branch's `AGENTS.md`. Close-out step 1 has merged develop in, so that file carries
   develop's baseline. The tool's table goes into the merge sign-off.
5. **A drop** (exit 1) needs the user's explicit approval at sign-off.
6. **The orchestrator records the new total** on the `Coverage baseline:` line, in the close-out's
   docs-only status-flip commit. That includes a drop the user approved.

Also in Testing & QA:

- **The first figure.** The `Coverage baseline:` line is added in this CR's first cycle, from a
  measurement under §S1's config. This CR's own gate checks against it, and its status flip records
  the gate's figure.
- **When develop moves before the merge,** the post-merge develop gate is a coverage run, run as
  steps 1–2, and a changed total is recorded on develop in a docs-only commit.
- **The example.** The full-suite coverage example keeps
  `python-crucible.py regression --coverage`, with `--cov-source` added after `--coverage`.
- **A full-suite `test` command stays shown.** A `pre-merge-gate` run does not replace it.

`AGENTS.md`'s Workflow Rules close-out bullet names the status flip and the `Coverage baseline:`
line together, as the branch's last commit.

### §S4 — The `crucible` skill's python reference

`skills-src/crucible/references/python.md`'s "Model B deltas" section states, for a project
measuring coverage through the python client:

- pass `--cov-source` naming the project's own packages and directories, because the client's
  default names Crucible's own;
- scripts run as subprocesses are measured only with coverage.py 7.10 or later and
  `patch = ["subprocess"]` in the project's config, and only in a child whose interpreter has
  coverage.py and inherits the environment;
- remove the reports directory's `.coverage` and `.coverage.*` before a coverage run, because a
  stale data file is merged into the next run's figures.

`crucible-report-python` is a byte-faithful import and is not changed.

### §S5 — `AGENTS.md`'s map

- **Key Directories:** a `tools/` row, stating that it holds repo-only tools that are never
  deployed.
- **Development Commands:** the check tool's invocation.
- **Important Files:** `pyproject.toml`'s `[tool.coverage.run]` and `[tool.coverage.report]`. The
  force-include sentence stays as it is.

## Acceptance criteria

- [ ] **§S1, the config.** `pyproject.toml` parses (`tomllib`). Its `[tool.coverage.run]` has
      exactly §S1's `source` (in order) and `patch`, and its `[tool.coverage.report]` has exactly
      §S1's `omit`. A test pins the `--cov-source` value of every coverage command in `AGENTS.md`,
      split on `,`, as equal to `source` in order. The wheel and sdist checks stay green.
- [ ] **§S2, the tool.** Tests drive `tools/coverage-check.py` as a subprocess, on synthetic
      `pyproject.toml`, lcov and baseline files in a temp project root. They pin:
      - the per-area hit/found and the one-decimal percent for a known lcov, including an
        extensionless `hooks-src/scripts/<name>` record;
      - the missing-file line, with its expected-file rule (a `*.yml` under an area is not
        expected; a `report.omit` path is not expected), and `scripts/gate-lock.sh` named as
        unmeasured;
      - exit 0 for an equal total and for a higher one, including a case where the rounded
        percents are equal but the exact ratio is lower, which exits 1;
      - exit 1 for a lower total, naming both figures on stderr;
      - exit 2, with its reason on stderr, for: a missing lcov; an lcov with no records; a record
        outside every area; a baseline file with no `Coverage baseline:` line; and one with two;
      - `--baseline` naming a file other than `./AGENTS.md`;
      - that the tool writes nothing: the temp root's file list is unchanged.
- [ ] **§S2, stdlib.** The tool imports only the standard library, and its first line is
      `#!/usr/bin/env python3`.
- [ ] **§S3, the steps.** Gates pin in `AGENTS.md`'s Testing & QA:
      - step 1's removal of `.coverage` and `.coverage.*`, before the run;
      - step 2's command, with `pre-merge-gate`, `--cov-source`, `--cycle`, `--log` and the three
        sandbox variables;
      - the empty-`HOME` and clean-runner runs as `test` runs;
      - step 4's invocation, naming the existing `tools/coverage-check.py` in the argument form the
        §S2 tests drive, against the branch's `AGENTS.md`;
      - "a drop needs the user's explicit approval";
      - the orchestrator recording the total in the status-flip commit;
      - the post-merge develop gate as a coverage run;
      - a `Coverage baseline:` line that the tool parses;
      - the `regression --coverage` example with `--cov-source`;
      - a full-suite `test` command still shown.
- [ ] **§S3, Workflow Rules.** A gate pins the close-out bullet naming the status flip and the
      `Coverage baseline:` line together, as the branch's last commit. The existing close-out order
      gates stay green.
- [ ] **§S3, the first figure.** The `Coverage baseline:` line carries a total measured under §S1's
      config.
      - The orchestrator's pre-merge gate re-measures it: the tool exits 0 against the branch's
        `AGENTS.md`.
      - The gate's `coverage.lcov` has no `SF:scripts/toon.py` record.
      - VERIFY checks the line's format, and the arithmetic of a table the tool prints for a
        branch run.
- [ ] **§S4.** A gate pins, in `references/python.md`'s "Model B deltas":
      - `--cov-source` naming the project's own sources, beside the client's default being
        Crucible's;
      - coverage.py 7.10 or later with `patch = ["subprocess"]`, and the child's interpreter
        having coverage.py and inheriting the environment;
      - removing `.coverage` and `.coverage.*` before a coverage run.

      `crucible-report-python` is unchanged, byte for byte. The skills load in Pi with no
      diagnostics, and the `crucible` skill's frontmatter is unchanged.
- [ ] **§S5.** `AGENTS.md`'s Key Directories names `tools/` as repo-only and never deployed. Its
      Development Commands show the check tool, and its Important Files name the two coverage
      tables. The force-include sentence is unchanged.
- [ ] **Migrations (RED).** Each is marked `# MIGRATED at CR-MDB-073 (§S…)`:
      - `tests/test_suite_hygiene.py`'s run-command pin
        (`test_s6_the_crucible_run_command_stays_as_cr_mdb_020_left_it`), if `--cov-source` breaks
        its literal;
      - any `AGENTS.md` structure pin that a new row or line breaks, named in the RED report.

      The module count and the baselines are GREEN's to update.
- [ ] **The guards stay green.** These stay green on the new text:
      - `ClientContractS3Test` (the gate command's flags);
      - the raw-runner guard (no `coverage run` shown);
      - the AXI-envelope guard;
      - the client-path anchoring gate;
      - the registry-key detector.

      A `KEY=` or `$NAME` the new text adds in code is listed in `NOT_REGISTRY_KEYS` as a RED
      migration.
- [ ] **Runs.**
      - The suite is green through the client with a real `HOME`, an empty one (which stays empty)
        and on the clean runner.
      - The pre-merge gate runs as §S3 states, and its check-tool table is in the sign-off.
      - New tests use a literal `§`, never `\u00a7`.
      - `AGENTS.md`'s module count and test baselines match the measured suite.

## Non-goals

- **Raising the scripts' coverage.** Tests for `rust-code-health.py`, `rust-crate-map.py`,
  `rust-dead-scan.py` and `skill-release-gate.py` are CR-MDB-078. `schedule_db.py` stays measured
  and gets no new tests.
- **A fixed floor per area.** The gate is a no-drop ratchet on the total.
- **The client's own handling of stale data, its per-file figures and its project-declared source.**
  These are Crucible's: a request goes to Crucible for the client to clear the data file before a
  coverage run, and CR-CRU-192 and CR-CRU-193 come with 0.4.0. Model B passes `--cov-source` until
  a later doc-sync.
- **Coverage for other projects' gates,** and `init`'s scaffolded config. This CR changes Model B's
  own gate. The python reference's guidance (§S4) is all a project gets.
- **`scripts/gate-lock.sh`.** It is named as unmeasured and never silently dropped.

## Cycle plan

1. **The config, the check tool and the gate (§S1–§S3, §S5).** Red-green.
2. **The python reference (§S4).** Red-green.
3. **Verify.**
