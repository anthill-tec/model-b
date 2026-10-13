# CR-MDB-062 — Blocking hooks for python and bun, and one convention for all four runner hooks

**Status:** COMPLETED (filed 2026-10-08; gap analysis and pre-review 2026-10-13)
**Type:** feature (hook scripts, guard, scaffold, docs)
**Priority:** P1 — release 1.0.0, wave 2.
**Depends on:** CR-MDB-056 (merged; board-authoritative: read `queue`)
**Labels:** hooks, scaffold, installer, enforcement
**Design reference:** DN-multi-harness-deploy-model §D21 and its amendments (the third records this
CR's rulings); `hooks-src/schema.md` v1; CR-MDB-015 (self-contained hook scripts); CR-MDB-056 §S3 (the
raw-runner guard).

## Context

CR-MDB-056 made the rule (every test run goes through the stack's Crucible client) and guards the text.
At tool-call time only cargo and mvn are stopped (`block-direct-cargo-test`, `block-direct-mvn-test`),
and `init` emits nothing for python or bun.

**Measured 2026-10-13 (gap analysis and spec pre-review):**
- **The two existing hooks** tokenise the command with `shlex` (quote-aware, fail-open on a parse
  error). A command position is the start or a position after an operator token, past `VAR=value`
  only. So:
  - they miss `env … cargo test`, `timeout 60 mvn test`, `nice …` and `time …`;
  - **they miss any command after a line break:** shlex never yields `"\n"`, so `printf 'echo
    hi\ncargo test'` measured rc=0 in a Cargo project;
  - they never treat a heredoc body as a command.

  They check the project marker in the working directory and its parents.
- **Their block reasons are stale in places:** "ORCHESTRATOR-RULES.md §4", "the project's instantiated
  orchestration memory (template: … memory-templates/…)" and "re-prompts permission every run".
- **The marker rule misses real layouts.** Sandesh (`PROJECT_STACKS=python,bun`) has only
  `pyproject.toml` at its root and its bun package in `integrations/pi/`. A Pi shell call's working
  directory is the session root.
- **The guard** (`tests/test_raw_runner_guard.py`) keeps its runner forms in one flat, unlabelled tuple
  (`_RUNNERS`), with Maven in `_MAVEN`:
  - its separators are `&&`, `||`, `;` and `|`;
  - it takes `timeout` without options and `nice` without `-n`;
  - its `bun run test\S*` also matches `bun run tests/x.ts` and `npm run testdata`.
- **`deploy._hook_scripts` deploys every file under `hooks-src/scripts/`,** and CR-MDB-064 renders the
  recorded interpreter into the shebang.
- **`init` resolves the deployed store (`_hook_scripts_root`) during validation, before the first
  write.** A dry run turns its error into a warning and leaves the store unresolved. Nothing checks that
  each emitted hook's script is there.
- **Pi's shim spawns the script directly,** and on a `closed` hook it blocks on every non-protocol
  outcome, a spawn error included. A missing or non-executable script therefore blocks every shell call.
- **`init` always emits `ambient-board-status` and `post-regression-disk-reminder`,** so a refusal
  reaches every install fixture whose store is empty.
- **The install fixtures that drive `init` are:**
  - `_helpers.write_install_toml`, used by `test_scaffold`, `test_prd_criteria` and
    `test_project_registry_schema`;
  - `test_project_permission_policy.write_install_toml`;
  - `test_project_trust.write_install_toml`;
  - `test_pi_agent_definitions._write_install_toml_c3`;
  - `test_init_tool_verdicts._install_toml_text`, used by `test_project_setup_section`,
    `test_project_tools_setup` and `test_init_sandesh_address_and_envrc`;
  - `test_ide_overlay_retirement`'s inline fixture;
  - `test_installer_correctness._write_full_install_toml`.
- **`AGENTS.md` says `hooks-src/scripts/` holds 7 scripts; it holds 6.** The seed's `test_scaffold`
  `HookSelectionTableTest` does not exist: the table is pinned by `HooksSeamSoloRustEmissionTest`'s
  docstring and by `HooksSeamMultiPythonEmissionTest`.
- **Model B's `.git` is a file** (`gitdir: ../.git/modules/model-b`), so its git root is `model-b/`.

**Baseline** (2026-10-13 22:24, `develop` `631735c`, through the client): real `HOME` 2333 tests OK,
1 skip (`PI_CODING_AGENT_DIR` sandboxed); empty `HOME` 2333 OK, 12 skips, and the temp home empty after.

## Scope

### §S1 — The guard: per-stack runner groups, the hooks' command positions, three python forms

`tests/test_raw_runner_guard.py` changes in four ways:

1. **Per-stack groups.** The runner forms are split into named groups — `PYTHON_RUNNERS`,
   `BUN_RUNNERS`, `CARGO_RUNNERS`, the Maven rule and `MAKE_RUNNERS` (`make junit`). A
   `stack_of(command)` function returns the stack of the runner at a command position, or `None`.
   `runner_at` keeps its behaviour, apart from the changes in items 2–4.
2. **Command positions** become the hooks' set (§S2):
   - every line start outside quotes and heredoc bodies;
   - `&&`, `||`, `;`, `|`, `&`, `(`;
   - past `VAR=value`; `env` with any options and assignments; `timeout` with any options and a
     duration; `nice [-n N]`; `time`.
3. **Three python forms:**
   - **an attached `-m`:** `-munittest`, `-mpytest`, `-mxmlrunner`, `-mcoverage run`;
   - **`uv run` before an interpreter or a runner:** `uv run` with its options, then a python runner
     form. The options are stepped over, including `--with`, `--with-requirements`, `--python` / `-p`,
     `--project`, `--directory`, `--package`, `--group` and `--extra` with their values. Examples:
     `uv run python -m pytest`, `uv run --with pytest pytest`, `uv run python3 tests/test_x.py`. This
     is the reading of the DN's "`uv run python …`": `uv run` is a position, and the runner after it is
     what is caught;
   - **a test file run directly:** an interpreter, its options, then a script whose basename matches
     `test_*.py` or `*_test.py`.
4. **The bun script rows narrow** to `bun run test` and `npm run test` alone or as `test:<name>`. So
   `bun run tests/x.ts` and `npm run testdata` are not runners.

Every change is proved on sample text in both directions. The guarded tree stays clean (it holds none
of the new forms, measured). Each python runner form is:
- a python interpreter (bare, versioned or a path) with any options, then `-m unittest`, `-m pytest`,
  `-m xmlrunner` or `-m coverage run`, with the `-m` separate or attached;
- `pytest` or `py.test`, bare or a path;
- `uv run` before any python runner form;
- `coverage run [options] -m <module>`;
- a test file run directly.

### §S2 — `block-direct-python-test` and `block-direct-bun-test`

Two new scripts in `hooks-src/scripts/`, built like the cargo and mvn hooks:
- `python3`, stdlib only, and self-contained: no import of a sibling module (CR-MDB-015 inlined the
  detectors);
- the neutral payload (`tool_name` `bash`, `tool_input.command`, `cwd`);
- exit 0 to allow, or exit 2 with `{"decision":"block","reason":…}` on stdout;
- fail-open on an unreadable payload, a non-`bash` tool or a command that does not tokenise.

The escape hatches are `ALLOW_RAW_PYTHON=(1|true)` and `ALLOW_RAW_BUN=(1|true)`, matched anywhere in the
command before any detection, as the existing hooks match theirs.

**Detection** uses §S1's command positions, applied line by line:
- each line outside quotes and outside a heredoc body is a command start;
- a heredoc body (from `<<WORD` or `<<'WORD'` / `<<-WORD` to the line `WORD`) is never a command
  position. So `git commit -F - <<'EOF' … pytest … EOF` and `cat > f.md <<EOF … bun test … EOF` are
  allowed.

**What each hook blocks:**
- **python:** exactly §S1's python runner forms;
- **bun:** exactly §S1's bun runner forms — `bun test`; `bun run test` or `bun run test:<name>`;
  `npm test`; `npm run test` or `npm run test:<name>`; `bunx`, `bun x` or `npx` with `playwright test`;
  and `playwright test`.

**What is never blocked:**
- a runner word inside an argument (`git commit -m "… pytest …"`, `echo pytest`);
- a client invocation (`<stack>-crucible.py …`);
- each non-runner mention of CR-MDB-056 §S3 (`pytest.ini`, `[tool.pytest]`, `pytest-cov` …).

### §S3 — Where a runner hook applies (all four)

A hook blocks only inside a project of its stack. That is when one of the stack's markers is in one of
three places:
- the payload's `cwd`;
- a parent of it, up to and including the git root (the nearest ancestor holding any `.git` entry,
  which covers a worktree's or a submodule's `.git` file);
- a directory at most 3 levels below that git root.

Without a git root, only the `cwd` and its parents are checked.

| Stack | Markers |
|---|---|
| python | `pyproject.toml`, `setup.py`, `setup.cfg`, `requirements*.txt` |
| bun | `package.json`, `bun.lock`, `bun.lockb`, `bunfig.toml` |
| rust (cargo) | `Cargo.toml` |
| java (mvn) | `pom.xml`, `build.gradle`, `build.gradle.kts` |

**The walk below the git root:**
- follows no symlinks;
- skips hidden directories, `node_modules`, `.venv`, `venv`, `target`, `dist` and `build`;
- skips a directory it cannot read;
- stops at the first marker.

An empty or missing `cwd` makes the hook allow. No error in the walk ever escapes: the hook allows,
because an exception from a `closed` hook would block.

### §S4 — Block reasons (all four)

Each hook's reason states:
- that it blocks a direct run of its stack's tests;
- Crucible's manifest `~/.crucible/crucible-clients.json` and the client
  `~/.crucible/clients/<stack>-crucible.py` with these verbs:

  | Hook | Client | Verbs |
  |---|---|---|
  | python | `python-crucible.py` | `test`, `check`, `regression` |
  | bun | `bun-crucible.py` | `test`, `check`, the tier verbs, `regression` |
  | cargo | `rust-crucible.py` | `test`, `check`, `workspace-regression` |
  | mvn | `mvn-crucible.py` | `unit`, `module`, `compile`, `e2e`, `regression` |

  The pre-review measured each against the installed client's `--help` on 2026-10-13. A later change in
  a client is a Model B doc-sync (CRUCIBLE-HANDOVER);
- the escape hatch, `ALLOW_RAW_<RUNNER>=1` for its runner, used only with the orchestrator's approval;
- the python reason names its client gap in plain words (a pytest project);
- the bun reason names its gap (a single test selected by name).

It carries no stale reference: no `ORCHESTRATOR-RULES.md`, no orchestration-memory or
`memory-templates` path, and no "re-prompts permission".

### §S5 — The cargo and mvn hooks aligned

`block-direct-cargo-test` and `block-direct-mvn-test` take:
- §S2's command positions, including the line-and-heredoc rule;
- §S3's marker rule;
- §S4's reason.

What each blocks is otherwise unchanged. The hook-only extras, beyond the guard's rows, are:
- cargo: `check`, `clippy` and a `+toolchain`;
- mvn: `mvnd`, and a launcher invoked by path (`…/mvn`, `…/mvnw`).

Each keeps its allowed forms (mvn `package`, `install` and `compile`).

### §S6 — Parity with the guard

One corpus of commands runs through the guard (`stack_of`) and through every runner hook's real script.
The payload's `cwd` is a temp project carrying all four stacks' markers. The corpus is:
- the guard's `RUNNER_FORMS`, `WRAPPED_FORMS`, `CLIENT_FORMS` and `NON_RUNNER_MENTIONS`;
- §S1's new forms;
- the argument-mention and heredoc cases.

The guard's arduino entries (`make junit`) are left out: arduino has no runner hook. The parity test
checks three things:
- **Every command the guard assigns to a stack is blocked by that stack's hook,** and by no other.
- **Every command the guard passes is allowed by all four,** except §S5's hook-only extras.
- **Each extra is blocked by its own hook only.**

The test may run each hook once over a batch of commands.

### §S7 — `init`

**Emission.** `init` emits each of the two new hooks for its stack:
- `block-direct-python-test` when `python` is in the stacks;
- `block-direct-bun-test` when `bun` is in the stacks.

Each is `pre-tool-use`, `bash`, `core`, `closed`. The table comment above `_hook_instances` gains both
rows.

**The script check** runs once the store resolves, during validation and before the first write:
every hook `init` would emit must have its script as an **executable file** in the store.
- **When one is missing or not executable,** `init` refuses: exit 2, nothing written, the envelope
  `ok: false`, naming each script and `modelb-axi --reinstall`. A dry run carries the same text as a
  warning.
- **When the store does not resolve** (no `install.toml`, no `hooks_scripts_dir`), today's error stands
  alone.
- **With no roster harness,** no hooks are compiled, so the check does not run.

### §S8 — The gates this change moves

- **One helper, `tests/_helpers.deploy_hook_scripts(store)`,** copies `hooks-src/scripts/*` into a
  sandbox store with mode 0755. Every install fixture §Context lists calls it.
- **`NOT_REGISTRY_KEYS`** gains `ALLOW_RAW_PYTHON` and `ALLOW_RAW_BUN`, plus any env-shaped name a new
  reason carries. The existing `VAR` entry stays matched if a docstring is rewritten.
- **`test_installer_assets` `HOOK_SCRIPT_NAMES`.**
- **`test_hooks` `IMPORTED_SCRIPT_NAMES`, and `ALL_SIX_SCRIPT_NAMES`,** renamed for eight scripts.
- **`test_client_path_anchoring`'s reason checks,** now covering all four hooks.
- **`test_pi_hook_runtime`:** `PiHookCargoMvnGuardAcrossToolsTest` gains the python and bun hooks.
- **`test_scaffold`:** the hook-table docstring in `HooksSeamSoloRustEmissionTest`, and
  `HooksSeamMultiPythonEmissionTest`.
- **`PiWorktreeCarryAndClosedGuardsTest`:** its "all four block-* instances" and its `closed` list.
- **`test_installer_correctness`:** the wiring-partial docstring ("pi has exactly two instances").
- **The guard's own docstring** and its `CR-MDB-056 §S3` contract line.
- **`hooks-src/schema.md`'s security-class roster.**
- **`AGENTS.md`:** the hook-script count (8), the module count and the baselines.

### §S9 — After merge

None of these steps is an acceptance criterion.
1. The user reinstalls the tool from the tree (`uv tool install --reinstall --python 3.14 .`).
2. The user redeploys.
3. The orchestrator recompiles Model B's own wiring (now with `block-direct-python-test`) and commits it
   as a chore (DN §D21, first amendment).

## Acceptance criteria

- [ ] **The guard:**
      - is split into the per-stack groups, and `stack_of` names each corpus entry's stack;
      - takes every command position and wrapper of §S1, and the three python forms;
      - narrows the bun script rows;
      - passes non-test scripts (`python3 generator/build.py`, `python3 -c …`, `python3 - <<EOF`) and
        client invocations.

      Each point is proved on samples in both directions. The guarded tree stays clean.
- [ ] **`block-direct-python-test` and `block-direct-bun-test`** exist and are executable. An AST check
      proves each imports only the stdlib and no sibling. Running the real script on payloads proves
      that it:
      - blocks every runner form of its stack at every command position (a later line included) and
        under every wrapper;
      - allows a heredoc body, a runner word inside an argument, a client invocation, each non-runner
        mention, a non-`bash` tool, an unreadable payload and an untokenisable command;
      - allows under its escape hatch.
- [ ] **The marker rule** is proved in all four hooks. Each blocks when the marker sits in the `cwd`, in
      a parent up to the git root, or up to 3 levels below the git root (both a `.git` directory and a
      `.git` file). Each allows when the only marker sits deeper and off the `cwd`'s path, sits in a
      skipped directory or behind a symlink, or is absent. Each allows on an empty or missing `cwd`
      and on an unreadable directory, without raising. Without a git root, only the `cwd` and its
      parents count. The Sandesh layout is a test case.
- [ ] **Every block reason** (four hooks):
      - says it blocks a direct run;
      - names the manifest, the client path and exactly the verbs of §S4's table, and the escape hatch
        with the approval rule;
      - names its client gap (python and bun only);
      - carries no stale reference of §S4.
- [ ] **The cargo and mvn hooks** block on a later line and under every §S2 wrapper. They keep their
      extras and their allowed goals.
- [ ] **Parity:** the §S6 corpus gives exactly the verdicts §S6 states, for all four hooks against the
      guard.
- [ ] **`init`:**
      - emits each new hook exactly for its stack (`pre-tool-use`, `bash`, `core`, `closed`), and the
        table comment above `_hook_instances` lists both;
      - refuses — exit 2, nothing written, envelope `ok: false`; as a warning on a dry run — when any
        emitted hook's script is missing or not executable, naming it and `modelb-axi --reinstall`;
      - leaves today's error alone when the store does not resolve;
      - succeeds when every script is present.
- [ ] **A sandboxed install** deploys both new scripts, each with the recorded interpreter in its shebang
      and its rendered hash in the manifest.
- [ ] **Gates that hold:**
      - every §S8 gate is updated as §S8 says, and every fixture uses `deploy_hook_scripts`;
      - the full suite passes through the client, with real `HOME` and with an empty `HOME` (the temp
        home empty afterwards);
      - `AGENTS.md`'s script count (8), module count, baselines and skip list are re-measured.

## Non-goals

- Forms neither the guard nor the hooks catch:
  - `make test`, `mvn install`, `vitest` and `jest`, and indented code blocks;
  - `python3 -m tests.test_x` (a test module run with `-m`);
  - `bash -c '…'`, `sudo`, `xargs`, `nohup` and `exec` wrappers.
- Known over-blocks, each with the escape hatch as the remedy:
  - a non-project script named `test_*.py`;
  - `cd /tmp/x && python3 -m unittest` run from inside a project (the payload's `cwd` is the session
    root).
- The escape-hatch text matched anywhere in the command (today's behaviour, kept).
- A shared detector module: each hook stays self-contained (CR-MDB-015), and §S6 keeps them in step.
- Re-wiring projects scaffolded before this change, or a stack added later through `modelb-axi agents
  --stacks …`: re-running `init` (or a recompile) is the user's.
- A client that is not installed: the reason still names its path, which the user installs through
  Crucible.
- The comma-separated "not" clause the guard documents as a limit.

## Cycle plan

| Cycle | Kind | Content |
|---|---|---|
| C1 | red-green | The guard (§S1) |
| C2 | red-green | The cargo and mvn hooks aligned (§S3–§S5 for them), `test_client_path_anchoring` |
| C3 | red-green | The python and bun hooks (§S2–§S4) and parity (§S6). The same commits carry `HOOK_SCRIPT_NAMES`, the `test_hooks` names, `NOT_REGISTRY_KEYS`, `test_pi_hook_runtime`, the `schema.md` roster and `AGENTS.md`'s script count |
| C4 | red-green | `init` (§S7) with `deploy_hook_scripts` and every fixture, the `test_scaffold` / `PiWorktreeCarryAndClosedGuardsTest` / `test_installer_correctness` gates, and the sandboxed install |
| C5 | verify | |
