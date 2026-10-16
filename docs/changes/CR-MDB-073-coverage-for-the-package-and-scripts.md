# CR-MDB-073 — The pre-merge gate measures coverage of the package and every script

**Status:** PENDING — spec (gap analysis 2026-10-17).
**Type:** feature (coverage config, the pre-merge gate, a check tool, `AGENTS.md`, the `crucible`
skill)
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
- **The client's default source is Crucible's own.** `regression` and `pre-merge-gate` default
  `--cov-source` to `crucible_axi,clients`, which measures nothing of Model B. The client always
  passes `--source`, so a project's own `source` setting is overridden.
- **No coverage config.** Model B has no `[tool.coverage]` and no `.coveragerc`.
- **Subprocess measurement works on 0.3.0.**
  - Setup: `--cov-source modelb_axi,scripts,hooks-src/scripts,workflows-src`, plus a config with
    `[run] patch = subprocess`.
  - The scripts the tests run as subprocesses are traced, the extensionless `/usr/bin/python3`
    hooks included. Without the patch the hooks are absent: 28 files measured instead of 36.
  - coverage.py combines the parallel data when it writes the lcov, and leaves no `.coverage.*`
    file behind.
- **The full suite under coverage, with the patch:**
  - `regression --coverage`: 3630 tests, 0 failed, 1 skip, in 392 s. The plain `test` run takes
    about 200 s.
  - `pre-merge-gate` (a `py_compile` check, then `regression --coverage`): the same counts, in
    385 s.
  - The output lands in `test-reports/<agent>/coverage.lcov`.
- **The figures:**

  | Area | Lines |
  |---|---|
  | `modelb_axi` | 2668/2803, 95.2% |
  | `workflows-src` | 205/217, 94.5% |
  | `hooks-src/scripts` | 913/1030, 88.6% |
  | `scripts` | 478/2257, 21.2% |
  | Total | 4264/6307, 67.6% |

  `scripts/toon.py` (76/186) is generated from `modelb_axi/toon.py` (`generator/build.py`), so it
  counts the same code twice.
- **What the board gets.** The client posts the run's total coverage with the run. It enforces no
  floor and reports nothing per file.
- **The non-Python script.** `scripts/gate-lock.sh` is outside coverage.py.

## Scope

### §S1 — The coverage config

`pyproject.toml` gains `[tool.coverage.run]`:

- `source`: `modelb_axi`, `scripts`, `hooks-src/scripts`, `workflows-src` and `tools`;
- `patch = ["subprocess"]`;
- `omit`: `scripts/toon.py`, the generated twin of `modelb_axi/toon.py`.

The `--cov-source` that Model B passes names exactly the `source` list, comma-joined. A test pins
the two as equal, so they cannot drift apart.

### §S2 — The coverage check tool

`tools/coverage-check.py`, a stdlib-only Python script:

- **Input:** an lcov file (`coverage.lcov`) and a baseline file (an `AGENTS.md`).
- **Output:** a table of lines covered (hit/found and percent) for each area and the total:
  - the areas are the top-level `source` entries, with `hooks-src/scripts` as one area;
  - a final line names each source file the lcov lacks, and `scripts/gate-lock.sh` as unmeasured.
- **The baseline:** read from the `AGENTS.md` line that starts `Coverage baseline:`, which carries a
  total as `<hit>/<found>`.
- **Exit codes:**
  - 0 when the measured total's ratio is at least the baseline's;
  - 1 when it is lower, naming both figures;
  - 2 on an unreadable lcov or a missing baseline line, with the reason.

It writes nothing. It is not a deployed tool script (`scripts/`): it serves this repository's gate
only.

### §S3 — The pre-merge gate measures coverage

`AGENTS.md`'s Testing & QA states Model B's pre-merge gate:

1. **The real-`HOME` run** is
   `python3 ~/.crucible/clients/python-crucible.py pre-merge-gate --cov-source <the §S1 list> --agent vidushi-mdb --cycle <last cycle> --log <file>`.
   It is sandboxed as the other runs are.
2. **The empty-`HOME` and clean-runner runs** stay `test` runs.
3. **After the real-`HOME` run,** `tools/coverage-check.py test-reports/vidushi-mdb/coverage.lcov`
   runs against develop's `AGENTS.md` (the last merged baseline). Its table goes into the merge
   sign-off.
4. **A drop** (exit 1) needs the user's explicit approval at sign-off.
5. **A changed total** is recorded on the `Coverage baseline:` line by the close-out's docs-only
   status-flip commit. That includes a drop the user approved.

Also:

- The `Coverage baseline:` line is added with the first figure measured under §S1's config.
- The example coverage command passes `--cov-source`.
- The note that a run killed mid-way can leave `.coverage.*` files is stated, with its remedy:
  remove them before the next coverage run.

### §S4 — The `crucible` skill

In the python row's guidance, the skill states that a project measuring coverage passes
`--cov-source` naming its own packages and directories, because the client's default names
Crucible's own. It also states that scripts run as subprocesses are measured only with coverage.py's
`patch = ["subprocess"]` in the project's config.

### §S5 — `AGENTS.md`'s map

- Key Directories gains `tools/`.
- Development Commands gains the check tool's invocation.
- Important Files names `[tool.coverage.run]` in `pyproject.toml`.

## Acceptance criteria

- [ ] **§S1.** `pyproject.toml` parses (`tomllib`) and its `[tool.coverage.run]` has exactly the
      `source`, `patch` and `omit` values of §S1. A test pins `AGENTS.md`'s `--cov-source`
      argument, split on `,`, as equal to `source`. The wheel and sdist checks stay green.
- [ ] **§S2, the tool.** Tests drive `tools/coverage-check.py` as a subprocess on synthetic lcov and
      `AGENTS.md` files in a temp dir, and pin:
      - the per-area hit/found and percent for a known lcov, including an extensionless
        `hooks-src/scripts/<name>` record;
      - the missing-file line, and `scripts/gate-lock.sh` named as unmeasured;
      - exit 0 for an equal total and a higher one;
      - exit 1 for a lower total, naming both figures;
      - exit 2 for a missing lcov, an lcov with no records, and an `AGENTS.md` with no
        `Coverage baseline:` line;
      - that the tool writes nothing: the temp dir's file list is unchanged.
- [ ] **§S2, stdlib.** The tool imports only the standard library, and its first line is
      `#!/usr/bin/env python3`.
- [ ] **§S3.** Gates pin in `AGENTS.md`'s Testing & QA:
      - the gate's real-`HOME` command, with `pre-merge-gate`, `--cov-source` and `--cycle`;
      - the check tool's invocation against develop's `AGENTS.md`;
      - "a drop needs the user's explicit approval";
      - the baseline recorded by the status-flip commit;
      - the `.coverage.*` remedy;
      - a `Coverage baseline:` line whose `<hit>/<found>` the tool parses;
      - the empty-`HOME` and clean-runner runs still named as `test` runs.
- [ ] **§S3, the first figure.** The `Coverage baseline:` line carries the total of a
      `pre-merge-gate` run measured on the branch under §S1's config (the twin omitted), from
      `tools/coverage-check.py`'s table. VERIFY re-measures it.
- [ ] **§S4.** A gate pins, in the `crucible` skill, `--cov-source` naming the project's own sources
      beside the client's default being Crucible's, and `patch = ["subprocess"]` for subprocess
      scripts. The skill's frontmatter is unchanged, and the skills load in Pi with no diagnostics.
- [ ] **§S5.** `AGENTS.md`'s Key Directories names `tools/`, and its Development Commands show the
      check tool. The structural gates on `AGENTS.md` stay green, migrated where they pin a list.
- [ ] **The guards stay green.** The raw-runner guard, the AXI-envelope guard and the registry-key
      detector stay green on the new text. A `KEY=` or `$NAME` it adds in code is listed in
      `NOT_REGISTRY_KEYS` as a RED migration.
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
- **Per-file figures on the board** (Crucible's CR-CRU-193), and the project-declared source of
  Crucible 0.4.0 (CR-CRU-192). Model B passes `--cov-source` until a later doc-sync.
- **Coverage for other projects' gates,** and `init`'s scaffolded config. This CR changes Model B's
  own gate. The `crucible` skill's guidance (§S4) is all a project gets.
- **`scripts/gate-lock.sh`.** It is named as unmeasured and never silently dropped.

## Cycle plan

1. **The config, the check tool and the gate (§S1–§S3, §S5).** Red-green.
2. **The `crucible` skill (§S4).** Red-green.
3. **Verify.**
