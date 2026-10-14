# CR-MDB-063 — Test interpreters: the project `.venv`, `python3` for every client, a bootstrap check

**Status:** COMPLETED (filed 2026-10-08; gap analysis and pre-review 2026-10-14)
**Type:** feature (installer preflight, scaffold, bootstrap skill, install guide)
**Priority:** P1 — release 1.0.0, wave 2.
**Depends on:** CR-MDB-064 (merged; board-authoritative: read `queue`)
**Labels:** installer, preflight, scaffold, python, skills
**Design reference:** DN-multi-harness-deploy-model §D21 (amended 2026-10-14 for this CR) and §D22;
PRD D10 (the installer detects, `init` reads the verdicts); each Crucible client's `--help`
(`--python`: "default: $PY_CRUCIBLE_PYTHON, else <project>/.venv/bin/python if present, else this
interpreter. Must have xmlrunner (and coverage.py for --coverage)"; `--project-dir`: "default:
$PY_CRUCIBLE_PROJECT_DIR, else the git repo containing the current directory").

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
- **The module warnings say the wrong thing.** They read "python tests cannot run on this machine",
  though a project with a `.venv` runs its tests there.
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
  - Its install and update commands do not name `--python 3.14`.
    - `uv tool install --reinstall .` reuses the tool environment's interpreter and refuses when that
      is below 3.14.
    - A fresh install takes uv's preferred interpreter.
    - `uv tool upgrade` keeps an environment built under the old `>=3.11` floor.

## Scope

### §S1 — `python3` on `PATH` for every stack's client

- Every stack's toolchain probes (`requirements.STACK_TOOLCHAINS`) begin with a `python3` probe, so
  every `stack <name>:` pre-flight line begins `python3=<verdict>`. The six stacks are `arduino`,
  `bun`, `python`, `quarkus`, `rust` and `java`.
  - The probe is a `PATH` presence check.
  - It is resolved once per run, whatever the number of stacks, when no offer is accepted (an
    accepted offer re-probes it, as today).
  - It is distinct from the §D22 interpreter check (`python3:` line, `[install] python`), which is
    unchanged.
- **Its remediation** is ``put python3 on PATH with uv: `uv python install --default 3.14` ``, and its
  install argv is that command.
  - It is offered at most once per run, whatever the number of stacks, and re-probed for every stack
    it covers.
  - Its `expected` text is "in uv's executable directory (~/.local/bin, unless UV_PYTHON_BIN_DIR or
    XDG_BIN_HOME names another), which must be on PATH".
- **The recorded keys** are `<stack>.python3` for each selected stack.
  - A project scaffolded from an install that predates this change reads them as unrecorded, as any
    unrecorded key reads today.
  - That install reports `outdated` (its deployed bootstrap skill is `stale`) and names the
    `--reinstall` run that records them.

### §S2 — `xmlrunner` and `coverage`: the project `.venv` route

- The two module probes stay import checks in the `PATH` `python3`. They report the interpreter the
  client falls back to when a project has no `.venv`.
- **Why no installer is offered is declared as data.** A probe without an install argv states its
  reason: `elevated` (needs elevated privileges) or `per-project` (its route runs in each project).
  - `_ELEVATED_NOTE` is appended only for `elevated`.
  - The `STACK_TOOLCHAINS` docstring states both.
  - `mvn`, `java`, `node` and `g++` are `elevated`; `xmlrunner` and `coverage` are `per-project`.
- **The route's commands are declared once,** in `modelb_axi.requirements`, as data:
  - `uv venv --python 3.14`;
  - `uv pip install unittest-xml-reporting coverage`.

  The module probes' remediation and §S4's task are built from that data. A warning's backticked
  span is either an install argv's display or one of these route commands.
- **The module warning reads exactly:**

  ``stack python: <name>=<verdict> — the PATH python3 cannot run python tests; a python project's
  tests run under its own .venv: in the project, run `uv venv --python 3.14`, then
  `uv pip install unittest-xml-reporting coverage` ``

  Neither module is offered anything.

### §S3 — The capability contract's `python3` line

The rendered contract keeps one `python3` line: the §D22 requirement row merged with every selected
stack's `python3` probe, at the worse state.

- **Its remediation:**
  - `uv python install --default 3.14` when any selected stack's `<stack>.python3` state is
    non-present and ranks at least as bad as the row's own state (ties included);
  - the row's `uv python install 3.14` otherwise.
- **Its label** is `required; <stacks> toolchain`, where `<stacks>` lists the selected stacks
  comma-separated in selection order, e.g. `required; python, rust toolchain`.

### §S4 — `init`'s Setup section for a python project

When the project's stacks include `python`, the `## Setup` section carries one unchecked task. It is
placed after the `project-meta` task and the Sandesh task (when present), before the `REPO_OWNER`
check. Its commands come from §S2's route data. It reads:

``- [ ] Create the python test interpreter: from the project root, run `uv venv --python 3.14`, then
`uv pip install unittest-xml-reporting coverage` — the python client runs the tests under
`.venv/bin/python` when it exists; `coverage` is needed for `regression --coverage` ``

A project without the python stack gets no such task.

### §S5 — `freshness` with a dead recorded interpreter

In the `already_installed` envelope, when `install.toml` records a `target_root` and an interpreter
that `interpreter_rejection` now rejects:

- `freshness` is `outdated`, whatever the file lists hold;
- the envelope carries `interpreter`, an object with `path` (the recorded path) and `reason` (the
  rejection);
- the existing warning stays.

The other cases:

- **The recorded interpreter is accepted, or none is recorded:** there is no `interpreter` field and
  `freshness` is judged as today.
- **No recorded `target_root`, or an unreadable `install.toml`:** `freshness` stays `unknown` and the
  interpreter is not judged.

Findings never change `ok` or the exit code.

### §S6 — Bootstrap checks a python project's test interpreter

`skills-src/bootstrap/SKILL.md` gains **Step 0.7 — Check the python test interpreter (BOTH roles,
only where `PROJECT_STACKS` includes `python`)**, after Step 0.6. A project without the python stack
skips it.

1. **The project root** is `$PY_CRUCIBLE_PROJECT_DIR`, else the git repo containing the working
   directory.
2. **Resolve the interpreter as the client does:**
   - `$PY_CRUCIBLE_PYTHON` when set, even if it does not exist (a missing path is reported, never
     fallen through);
   - else `<root>/.venv/bin/python` when it exists;
   - else the `python3` on `PATH`.
3. **Check it** with `<interpreter> -c "import xmlrunner, coverage"`.
4. **Fold the result into the role's report:**
   - Mainline's Step 3A report to the user;
   - a Track's Step 3B status to Mainline.

   A missing interpreter or module is reported with §S2's route.

The step names the client's `--help` as the authority for the resolution order.

### §S7 — The install guide, `AGENTS.md`, and the gates this change moves

**`docs/install-guide.md`** (and the regions `pi-package/README.md` mirrors from it):

- **Install commands:**
  - `uv tool install --python 3.14 modelb-axi`;
  - `uv tool upgrade --python 3.14 modelb-axi`;
  - from a source copy, `uv tool install --python 3.14 .`, and to update,
    `uv tool install --reinstall --python 3.14 .`.
- **Prerequisites, `python3` item:**
  - names both `uv python install 3.14` and `uv python install --default 3.14`;
  - says every stack's Crucible client runs on the `python3` on `PATH`.
- **Reading the pre-flight:**
  - The guide says `stack <name>: python3=` is a `PATH` presence check for that stack's client,
    distinct from the `python3:` line (the interpreter the deployed scripts run on). On a uv-only
    machine the two lines can disagree.
  - The per-stack tool list names `python3` for every stack.
  - The `xmlrunner`/`coverage` sentence says they are checked in the `PATH` `python3`, and that a
    python project's tests run under its `.venv` (§S2).
- **Warnings table:** the `toolchain` row says an absent `xmlrunner`/`coverage` means the `PATH`
  `python3` cannot run python tests, and that a python project runs them under its `.venv`.
- **Choosing stacks and Install offers:**
  - `uv python install --default 3.14` is named as an offer;
  - the `pip install` parenthetical is gone;
  - both sections say `xmlrunner` and `coverage` are never offered, because their route runs in each
    python project;
  - the elevated-privileges list stays `mvn`, `java`, `node`, `g++`.
- **The `already_installed` report paragraph** names the dead-interpreter case: `freshness`
  `outdated` with an `interpreter` object (`path`, `reason`).

**`check_python_interpreter`** inspects every fenced line that, after an optional
`modelb-axi: error: ` prefix, begins `python3=`. The guide's refusal sample conforms.

**Model B's `AGENTS.md`:**

- every `uv tool install .` reads `uv tool install --python 3.14 .`;
- the two `pip install -e .` alternatives are removed, since PEP 668 refuses them; tests still run
  from the repo root;
- the suite baselines are re-measured at the last red-green cycle.

**Gates that move, per cycle:**

| Cycle | Gates |
|---|---|
| **C1** | `WarningCommandShapeTest` (its invariant widened to §S2's route commands); `SharedInstallCommandWarningTest` and `test_absent_python_modules_name_the_install_command` (rewritten for the route); the exact per-stack group and `stack <name>:` line pins (each now leads with `python3`); every interactive fixture that answers yes and would now meet a `uv python install --default` offer (the sandbox's `python3`/`uv` set so the offer is either absent or answered on purpose); `tests/test_scaffold.py`'s `_contract_remediation` and contract-line pins |
| **C2** | `test_agents_md_follows_the_requirements_data_not_a_copy` (the route data is the requirements data, never a copy); the `already_installed` freshness tests |
| **C3** | `check_python_interpreter`; `INSTALLER_INSTALL`, `SOURCE_COPY_INSTALL` and `check_installer_source`; the README mirror gate; the bootstrap skill gates; the `AGENTS.md` baselines |

## Acceptance criteria

- [ ] **§S1 — `python3` for every stack.**
      - `STACK_TOOLCHAINS` gives each of the six stacks a first probe named `python3`, with §S1's
        exact remediation, install argv `("uv", "python", "install", "--default", "3.14")` and
        `expected` text.
      - A pre-flight with all six stacks prints six `stack <name>:` lines, each beginning
        `python3=`.
      - With no offer accepted, `python3` is resolved once.
      - The offer is made once per run and re-probed for every stack it covers.
      - `[capabilities]` records `<stack>.python3` for each selected stack.

      Each point is proved by a test driving the real `run_preflight` and `remediate_toolchains`.
      The §D22 `python3:` line and its refusal are unchanged, and their tests stay green.
- [ ] **§S2 — the module route.**
      - Every probe without an install argv declares `elevated` or `per-project`.
        `_ELEVATED_NOTE` appears only on `elevated` warnings, proved for `node` and for `xmlrunner`.
      - The route commands are declared once in `modelb_axi.requirements`.
      - With both modules absent, `remediate_toolchains` with a recording `offer` makes zero prompts
        for them, and emits §S2's exact warning for each.
      - `WarningCommandShapeTest` accepts a backticked span only when it is an install argv's display
        or a declared route command, and still fails on any other.
- [ ] **§S3 — the contract line.** `_render_capability_contract` renders exactly one `python3` line
      for every stack selection, with §S3's label. The remediation follows §S3's rule, proved for:
      - a python-only selection;
      - a rust-only selection;
      - a mixed selection;
      - a tie of two `unknown` states (`--default` named);
      - an absent row with present probes (`uv python install 3.14` named).
- [ ] **§S4 — the Setup task.**
      - `init --stacks python`, and a selection including python, writes §S4's exact task in §S4's
        position.
      - `init --stacks rust` writes none.
      - The task's commands equal the requirements route data.

      Each is proved through the real `run_init` in a sandbox.
- [ ] **§S5 — `freshness` and `interpreter`.** Each case is proved through the real CLI in a
      sandbox, `ok` true and exit 0 throughout:
      - **Recorded interpreter missing, file lists empty:** a bare `modelb-axi` reports `freshness`
        `outdated` and `interpreter` = `{"path": <recorded>, "reason": <rejection>}`.
      - **Recorded interpreter below the floor:** the same.
      - **Recorded interpreter accepted:** no `interpreter` key, and `freshness` `current`.
      - **No `target_root` recorded:** `freshness` `unknown` and no `interpreter` key.
- [ ] **§S6 — the bootstrap step.**
      - `skills-src/bootstrap/SKILL.md` holds Step 0.7 under §S6's heading, after Step 0.6. It names,
        in order:
        1. the project root rule;
        2. `$PY_CRUCIBLE_PYTHON` (used when set, a missing path reported);
        3. `<root>/.venv/bin/python`;
        4. the `python3` on `PATH`;
        5. the import check;
        6. §S2's two commands;
        7. the client's `--help` as the authority.
      - Steps 3A and 3B each fold the result into their report.
      - The raw-runner guard and `block-direct-python-test` both allow the step's exact import-check
        command.
      - A structural test pins each named element, and the skill still loads in Pi's own loader with
        no diagnostics.
- [ ] **§S7 — guide, `AGENTS.md` and gates.**
      - `check_python_interpreter` judges fenced lines carrying the `modelb-axi: error: ` prefix: a
        non-conforming one is reported, and the guide's own refusal sample passes.
      - A check fails when any `uv tool install` or `uv tool upgrade` of `modelb-axi` or `.` in the
        guide or in `pi-package/README.md` lacks `--python 3.14`.
      - The guide states each §S7 point: prerequisite, pre-flight, warnings table, choosing stacks
        and offers, and the `already_installed` paragraph. Each is pinned by a check proved in both
        directions on sample text.
      - The README mirror gate stays green.
      - Model B's `AGENTS.md` carries no `uv tool install .` without `--python 3.14`, and no
        `pip install -e .`.
- [ ] **Whole suite.**
      - Each cycle's commit leaves the suite green through the client with a real `HOME` and with an
        empty one, and the temp home is empty afterwards.
      - `generator/build.py --check` is clean.
      - The `AGENTS.md` baselines match the measured counts.

## Non-goals

- **Making the venv.** Neither `init` nor the installer creates or populates a project `.venv`;
  they name the route.
- **A worktree's `.venv`.** A fresh CR worktree lacks the gitignored `.venv`, like any other
  gitignored dependency. The existing orchestration rule (populate a worktree's dependencies before
  running tests there) covers it.
- **Projects scaffolded before this change, or a project that adds python later** (`modelb-axi agents
  --stacks`). Their Setup section is not rewritten (CR-MDB-055's `migrate`); the bootstrap step still
  checks their interpreter.
- **Re-probing the modules after an accepted `python3` install.** A fresh uv interpreter has no
  modules; the route covers it.
- **Crucible's own floor, and uv's version.** The `python3` that runs a client is checked for
  presence on `PATH`, and uv's version is not judged. `--default` was measured on uv 0.11.8.
- **`init`'s "re-run the installer" note for unrecorded keys.** Its wording predates this CR.
- **`crucible-report-python`.** The bundle is a byte-faithful Crucible import and is not edited.
- **pytest projects.** The python client drives unittest only, a known client gap.

## Cycle plan

1. **C1 — the installer (§S1–§S3).** Red-green; it moves the C1 gates.
2. **C2 — `init`'s Setup task and `freshness` (§S4, §S5).** Red-green; it moves the C2 gates.
3. **C3 — the bootstrap step, the guide, `AGENTS.md` (§S6, §S7).** Red-green; it moves the C3 gates
   and re-measures the baselines.
4. **C4 — VERIFY.**

**After merge:**

- The bootstrap skill changes, so the user reinstalls and redeploys
  (`uv tool install --reinstall --python 3.14 .`, then
  `modelb-axi --reinstall --yes --harnesses pi --target-root /home/antonyj
  --allow-missing-capabilities`).
- Model B's own hook wiring is unchanged.
