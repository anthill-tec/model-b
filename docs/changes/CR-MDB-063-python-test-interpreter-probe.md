# CR-MDB-063 — Test interpreters: the project `.venv`, `python3` for every client, a bootstrap check

**Status:** PENDING (filed 2026-10-08; gap analysis 2026-10-14)
**Type:** feature (installer preflight, scaffold, bootstrap skill, install guide)
**Priority:** P1 — release 1.0.0, wave 2.
**Depends on:** CR-MDB-064 (merged; board-authoritative: read `queue`)
**Labels:** installer, preflight, scaffold, python, skills
**Design reference:** DN-multi-harness-deploy-model §D21 (amended 2026-10-14 for this CR) and §D22;
PRD D10 (the installer detects, `init` reads the verdicts); each Crucible client's `--help`
(`--python`: "default: $PY_CRUCIBLE_PYTHON, else <project>/.venv/bin/python if present, else this
interpreter. Must have xmlrunner (and coverage.py for --coverage)").

## Context

The python client runs a project's tests under `$PY_CRUCIBLE_PYTHON`, else
`<project>/.venv/bin/python`, else the `python3` running it. That interpreter needs `xmlrunner`
(`unittest-xml-reporting`) and, for `--coverage`, `coverage`. The python agent definitions already
require the project venv (`generator/stacks/python.toml`: "use the project venv
(`<project>/.venv/bin/python`)").

Today:

- **The installer offers a command that fails.** For an absent `xmlrunner` or `coverage` it offers
  `python3 -m pip install unittest-xml-reporting coverage`. A PEP 668 interpreter refuses it, `--user`
  included, and so does every uv-managed interpreter (`uv pip install` too). Measured 2026-10-14 on
  Arch's `/usr/bin/python3` 3.14.7 and uv's 3.13. The route that works is a virtual environment in the
  project: `uv venv --python 3.14`, then `uv pip install unittest-xml-reporting coverage`.
- **Nothing tells a python project to make that venv.** `init`'s Setup section has no task for it,
  and no step checks the interpreter the client will actually use, so a missing module first shows as
  a failed run.
- **Only the python stack checks `python3` on `PATH`,** though every stack's client is a Python
  script (`#!/usr/bin/env python3`) run as `python3 ~/.crucible/clients/<key>-crucible.py`. A machine
  whose only 3.14 is uv's passes the §D22 interpreter check and then runs no client.
  `uv python install 3.14` adds only `python3.14` to `PATH`; `uv python install --default 3.14` adds
  `python`, `python3` and `python3.14` (measured with uv 0.11.8).
- **The `python3` probe's remediation is wrong.** It reads "install python3 with the OS package
  manager" and is reported as needing elevated privileges.
- **A dead recorded interpreter reads `current`.** When the interpreter `install.toml` records is
  missing or below the floor, `_freshness_fields` warns but the envelope's `freshness` stays
  `current`.
- **The install guide has two gaps.**
  - Its interpreter refusal sample begins `modelb-axi: error: `, which `check_python_interpreter`
    never inspects (it reads only lines starting `python3=`).
  - Its install commands do not name `--python 3.14`. `uv tool install --reinstall .` reuses the tool
    environment's interpreter and refuses when that is below 3.14, and a fresh install takes uv's
    preferred interpreter.

## Scope

### §S1 — `python3` on `PATH` for every stack's client

- Every stack's toolchain probes (`requirements.STACK_TOOLCHAINS`) begin with a `python3` probe, so
  every `stack <name>:` pre-flight line begins `python3=<verdict>`.
  - The probe is a `PATH` presence check, made once per run whatever the number of stacks (the
    existing resolution cache).
  - It is distinct from the §D22 interpreter check (`python3:` line, `[install] python`), which is
    unchanged.
- Its remediation is `uv python install --default 3.14`. It is offered (not elevated), at most once
  per run whatever the number of stacks, and only when `uv` resolves. After the offer it is re-probed
  as any offered tool is. The location it expects is uv's executable directory (`~/.local/bin`), which
  must be on `PATH`.
- The recorded keys are `<stack>.python3` for each selected stack. A project scaffolded from an
  install that predates this change reads them as unrecorded, as any unrecorded key reads today.

### §S2 — `xmlrunner` and `coverage`: the project `.venv` route

- The two module probes stay import checks in the `PATH` `python3`: they judge the interpreter the
  client falls back to when a project has no `.venv`.
- Neither is offered an installer any more. Their remediation names the route: in the python
  project, `uv venv --python 3.14`, then `uv pip install unittest-xml-reporting coverage`.
- Their warning does not say "needs elevated privileges". It says the remediation is run in each
  python project.

### §S3 — The capability contract's `python3` line

The rendered contract keeps one `python3` line: the §D22 requirement row merged with every selected
stack's `python3` probe, at the worse state.

- **Which remediation it names:**
  - `uv python install --default 3.14` when a stack's `python3` probe is the worse, non-present state;
  - the row's `uv python install 3.14` otherwise.
- **Its label** names the merged stacks.

### §S4 — `init`'s Setup section for a python project

When the project's stacks include `python`, the `## Setup` section carries one unchecked task naming:

- the test interpreter (the project's `.venv`, which the python client uses when present);
- the commands: `uv venv --python 3.14`, then `uv pip install unittest-xml-reporting coverage`, run
  from the project root;
- that `coverage` is needed for `regression --coverage`.

A project without the python stack gets no such task. The task follows the existing setup tasks'
form (an unchecked `- [ ]` line).

### §S5 — `freshness` with a dead recorded interpreter

In the `already_installed` envelope, when `install.toml` records an interpreter that
`interpreter_rejection` now rejects:

- `freshness` is `outdated`, whatever the file lists hold;
- the envelope carries `interpreter`, an object with `path` (the recorded path) and `reason` (the
  rejection);
- the existing warning stays.

When the recorded interpreter is accepted, or none is recorded, there is no `interpreter` field and
`freshness` is judged as today. Findings still never change `ok` or the exit code.

### §S6 — Bootstrap checks a python project's test interpreter

`skills-src/bootstrap/SKILL.md` gains a step for both roles. Where the project's `PROJECT_STACKS`
includes `python`:

1. **Resolve the interpreter the way the client does:** `$PY_CRUCIBLE_PYTHON`, else
   `<project>/.venv/bin/python` when it exists, else the `python3` on `PATH`.
2. **Check it** imports `xmlrunner` and `coverage`. A `python3 -c` import is not a test run, so the
   python runner hook allows it.
3. **Report a missing interpreter or module** with §S2's route: Mainline reports to the user, a Track
   reports to Mainline.

A project without the python stack skips the step. The step names the client's `--help` as the
authority for the resolution order.

### §S7 — The install guide and the gates this change moves

**`docs/install-guide.md`** (and the regions `pi-package/README.md` mirrors from it):

- **Install commands:**
  - the PyPI install reads `uv tool install --python 3.14 modelb-axi`;
  - the source-copy install reads `uv tool install --python 3.14 .`;
  - the update reads `uv tool install --reinstall --python 3.14 .`;
  - `uv tool upgrade modelb-axi` is unchanged: it reuses the environment's interpreter.
- **Prerequisites, `python3` item:** says every stack's Crucible client runs on the `python3` on
  `PATH`, and names `uv python install --default 3.14` for a machine with none.
- **Reading the pre-flight:**
  - the sample `stack python:` line begins `python3=`;
  - the per-stack tool list names `python3` for every stack;
  - the `xmlrunner`/`coverage` sentence says they are checked in the `PATH` `python3` and that a
    python project's tests run under its `.venv` (§S2).
- **Install offers:** `uv python install --default 3.14` is named as an offer. The `pip install`
  parenthetical is gone. The elevated-privileges list stays `mvn`, `java`, `node`, `g++`.

**`check_python_interpreter`** inspects every fenced line that, after an optional
`modelb-axi: error: ` prefix, begins `python3=`. The guide's refusal sample conforms.

**Model B's own `AGENTS.md`:** its development install command reads `uv tool install --python 3.14 .`.

**The gates that pin the old forms move with the change:**

- the guide's install constants in `tests/test_install_guide.py`;
- the per-stack probe lists and offers in the installer, scaffold and contract tests;
- the bootstrap skill gates.

## Acceptance criteria

- [ ] **§S1 — `python3` for every stack.**
      - `STACK_TOOLCHAINS` gives each of the six stacks (`arduino`, `bun`, `python`, `quarkus`,
        `rust`, `java`) a first probe named `python3`, with remediation
        `uv python install --default 3.14` and an install argv equal to that command.
      - A pre-flight with all six stacks prints six `stack <name>:` lines, each beginning
        `python3=`.
      - `python3` is resolved once.
      - Its offer is made once and re-probed for every stack it covers.
      - `[capabilities]` records `<stack>.python3` for each selected stack.

      Each point is proved by a test driving the real `run_preflight` and `remediate_toolchains`. The
      §D22 `python3:` line and its refusal are unchanged; the existing interpreter tests stay green.
- [ ] **§S2 — the module route.**
      - The `xmlrunner` and `coverage` probes have no install argv, and the installer offers nothing
        for them.
      - Each warning names `uv venv --python 3.14` and `uv pip install unittest-xml-reporting coverage`
        and says it is run in the python project.
      - Neither warning contains "elevated privileges".

      A test drives `remediate_toolchains` with both modules absent and an `offer` that records its
      prompts: it asserts zero prompts for them and the warning text.
- [ ] **§S3 — the contract line.** `_render_capability_contract` renders exactly one `python3` line
      for any stack selection. It names `uv python install --default 3.14` when a selected stack's
      `<stack>.python3` state is the worse, non-present one, and `uv python install 3.14` otherwise.
      This is proved for a python-only, a rust-only and a mixed selection.
- [ ] **§S4 — the Setup task.** `init --stacks python` (and a selection including python) writes a
      `## Setup` section with one unchecked task naming `.venv`, `uv venv --python 3.14`,
      `uv pip install unittest-xml-reporting coverage` and `regression --coverage`.
      `init --stacks rust` writes no such task. Each is proved through the real `run_init` in a
      sandbox.
- [ ] **§S5 — `freshness` and `interpreter`.**
      - A bare `modelb-axi` on an install whose recorded interpreter is missing reports `freshness`
        `outdated` and `interpreter` = `{"path": <recorded>, "reason": <rejection>}`, even with every
        file list empty, and keeps `ok` true and exit 0.
      - The same holds for a recorded interpreter below the floor.
      - On an install whose recorded interpreter is accepted there is no `interpreter` key and
        `freshness` is `current`.

      Each is proved through the real CLI in a sandbox.
- [ ] **§S6 — the bootstrap step.**
      - `skills-src/bootstrap/SKILL.md` holds a step, for both roles, conditional on `python` in
        `PROJECT_STACKS`.
      - The step names, in order, `$PY_CRUCIBLE_PYTHON`, `<project>/.venv/bin/python` and the
        `python3` on `PATH`.
      - It names the import check of `xmlrunner` and `coverage`, §S2's two commands, the reporting
        target per role, and the client's `--help` as the authority.

      A structural test pins each named element. The skill still loads in Pi's own loader with no
      diagnostics.
- [ ] **§S7 — guide and gates.**
      - `check_python_interpreter` judges a fenced line with the `modelb-axi: error: ` prefix: a
        non-conforming one is reported, and the guide's own refusal sample passes.
      - A check fails when any `uv tool install` of `modelb-axi` or `.` in the guide or in
        `pi-package/README.md` lacks `--python 3.14`.
      - The guide states §S7's prerequisite, pre-flight and offers points, each pinned by a check
        proved in both directions on sample text.
      - The README mirror gate stays green.
      - Model B's `AGENTS.md` names `uv tool install --python 3.14 .`.
- [ ] **Whole suite.** It is green through the client with a real `HOME` and with an empty one. The
      temp home is empty afterwards, and `generator/build.py --check` is clean.

## Non-goals

- **Making the venv.** Neither `init` nor the installer creates or populates a project `.venv`;
  they name the route.
- **A worktree's `.venv`.** A fresh CR worktree lacks the gitignored `.venv`, like any other
  gitignored dependency. The existing orchestration rule (populate a worktree's dependencies before
  running tests there) covers it.
- **Projects scaffolded before this change.** Their Setup section is not rewritten (CR-MDB-055's
  `migrate`).
- **Crucible's own floor.** The `python3` that runs a client is checked for presence on `PATH`. Its
  version is Crucible's requirement, not judged here.
- **`crucible-report-python`.** The bundle is a byte-faithful Crucible import and is not edited.
- **pytest projects.** The python client drives unittest only, a known client gap.

## Cycle plan

1. **C1 — the installer (§S1–§S3).** Red-green.
2. **C2 — `init`'s Setup task and `freshness` (§S4, §S5).** Red-green.
3. **C3 — the bootstrap step, the guide and the gates (§S6, §S7).** Red-green.
4. **C4 — VERIFY.**

**After merge:**

- The bootstrap skill changes, so the user reinstalls and redeploys
  (`uv tool install --reinstall --python 3.14 .`, then
  `modelb-axi --reinstall --yes --harnesses pi --target-root /home/antonyj
  --allow-missing-capabilities`).
- Model B's own hook wiring is unchanged.
