# CR-MDB-062 — Blocking hooks for python and bun, and one convention for all four runner hooks

**Status:** PENDING (filed 2026-10-08; gap analysis 2026-10-13)
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

**Measured 2026-10-13:**
- **The two existing hooks** (`hooks-src/scripts/block-direct-{cargo,mvn}-test`) tokenise the command
  with `shlex` (quote-aware, fail-open on a parse error). They find a command position at the start or
  after a control operator, step past `VAR=value` only, and miss `env … cargo test`,
  `timeout 60 mvn test`, `nice …` and `time …`. They check the project marker in the working directory
  and its ancestors.
- **Their block reasons are stale in places:** "ORCHESTRATOR-RULES.md §4", "the project's instantiated
  orchestration memory (template: … memory-templates/…)" and "re-prompts permission every run".
- **The marker rule misses real layouts.** Sandesh (`PROJECT_STACKS=python,bun`) has only
  `pyproject.toml` at its root, with its bun package in `integrations/pi/`. A Pi shell call's working
  directory is the session root, so `cd integrations/pi && bun test` is never matched by a check of the
  working directory and its ancestors.
- **`deploy._hook_scripts` deploys every file under `hooks-src/scripts/`,** so a new script ships with no
  installer change. CR-MDB-064 renders the recorded interpreter into its shebang.
- **`init` resolves the deployed store (`_hook_scripts_root`) during validation, before the first
  write,** and a dry run turns its error into a warning. Nothing checks that each emitted hook's script
  is in that store, and a `closed` hook whose script is missing blocks every shell call (Pi's shim
  blocks on every non-protocol outcome).
- **The shared test fixture `tests/_helpers.write_install_toml`** records a sandbox `hooks_scripts_dir`
  but puts no script in it. 17 modules build install fixtures.
- **`AGENTS.md`** says `hooks-src/scripts/` holds 7 scripts; it holds 6.
- **The seed named `test_scaffold` `HookSelectionTableTest`, which does not exist.** The table is pinned
  by the docstring of `HooksSeamSoloRustEmissionTest` and by `HooksSeamMultiPythonEmissionTest`.

**Baseline** (2026-10-13 22:24, `develop` `631735c`, through the client): real `HOME` 2333 tests OK,
1 skip (`PI_CODING_AGENT_DIR` sandboxed); empty `HOME` 2333 OK, 12 skips, and the temp home empty after.

## Scope

### §S1 — Three more python runner forms, in the guard

`tests/test_raw_runner_guard.py`'s runner set gains three forms, each with sample text proved both
ways:
- **an attached `-m`:** `python3 -munittest`, `-mpytest`, `-mxmlrunner`, `-mcoverage run`;
- **`uv run` before an interpreter:** `uv run python -m pytest`, `uv run python3 tests/test_x.py`;
- **a test file run directly:** an interpreter, its options, then a script whose basename matches
  `test_*.py` or `*_test.py` (`python3 tests/test_hooks.py`, `.venv/bin/python -X dev test_a.py`).

A non-test script (`python3 generator/build.py`, `python3 ~/.crucible/clients/python-crucible.py
test`) is not a runner. The guarded tree holds no instance of the three forms (measured), so the tree
scan stays clean.

### §S2 — `block-direct-python-test` and `block-direct-bun-test`

Two new scripts in `hooks-src/scripts/`, built like the cargo and mvn hooks:
- `python3`, stdlib only, self-contained (CR-MDB-015 inlined the detectors: no shared module);
- the neutral payload (`tool_name` `bash`, `tool_input.command`, `cwd`);
- exit 0 to allow, or exit 2 with `{"decision":"block","reason":…}` on stdout;
- fail-open on an unreadable payload, a non-`bash` tool or a command that does not tokenise.

The escape hatches are `ALLOW_RAW_PYTHON=(1|true)` and `ALLOW_RAW_BUN=(1|true)`, checked before any
matching.

**Detection.** A runner is a command word at a command position:
- the start, or after `&&`, `||`, `;`, `|`, `&`, `(` or a newline;
- past `VAR=value`, `env` with its options (`-i`, `-u NAME`, `-C DIR`, `--unset=…`, `--chdir=…`) and
  assignments, `timeout [options] <n>`, `nice [-n N]` and `time`.

- **Python:** the guard's python rows and §S1's three forms.
- **Bun:** the guard's bun rows — `bun test`, `bun run test…`, `npm test` / `npm run test…`,
  `bunx` / `bun x` / `npx` `playwright test`, and `playwright test`.

What is never blocked:
- a runner word inside an argument (`git commit -m "… pytest …"`, `echo pytest`);
- a client invocation (`<stack>-crucible.py …`);
- any non-runner mention (§S3 of CR-MDB-056: `pytest.ini`, `[tool.pytest]`, `pytest-cov` and so on).

### §S3 — Where a runner hook applies (all four)

A hook blocks only inside a project of its stack. That is when the git root of the payload's `cwd` (the
nearest ancestor holding `.git`, a directory or a worktree's file) or a directory under it holds one of
the stack's markers:

| Stack | Markers |
|---|---|
| python | `pyproject.toml`, `setup.py`, `setup.cfg`, `requirements*.txt` |
| bun | `package.json`, `bun.lock`, `bun.lockb`, `bunfig.toml` |
| rust (cargo) | `Cargo.toml` |
| java (mvn) | `pom.xml`, `build.gradle`, `build.gradle.kts` |

**The walk under the git root:**
- goes at most 3 directories deep (Sandesh's `integrations/pi/` is 2);
- skips hidden directories, `node_modules`, `.venv`, `venv`, `target`, `dist` and `build`;
- runs only after a runner has been detected.

Without a git root, the `cwd` and its ancestors are checked, as today.

### §S4 — Block reasons (all four)

Each hook's reason states:
- that it blocks a direct run;
- Crucible's manifest `~/.crucible/crucible-clients.json` and the stack's client
  `~/.crucible/clients/<stack>-crucible.py`, with the run verbs and flags that client's installed
  `--help` offers for a targeted run, a compile check where it has one, and a regression;
- the escape hatch, `ALLOW_RAW_<RUNNER>=1`, used only with the orchestrator's approval;
- for python and bun, the known client gaps in plain words: a pytest project, and a one-test bun run.

It carries no stale reference: no `ORCHESTRATOR-RULES.md`, no orchestration-memory or
`memory-templates` path, no "re-prompts permission".

### §S5 — The cargo and mvn hooks aligned

`block-direct-cargo-test` and `block-direct-mvn-test` take §S2's command-position rule (the wrappers),
§S3's marker rule and §S4's reason. What each blocks is unchanged otherwise:
- cargo also blocks `check` and `clippy`, and takes a `+toolchain`;
- mvn also blocks `mvnd`, and allows `package`, `install` and `compile`.

### §S6 — Parity with the guard

A test runs one corpus of commands through the guard's detector (`runner_at`) and through every runner
hook's real script, with a payload whose `cwd` is a temp project carrying all four stacks' markers. The
corpus is the guard's `RUNNER_FORMS`, `WRAPPED_FORMS`, `CLIENT_FORMS` and `NON_RUNNER_MENTIONS`, plus
§S1's forms and argument-mention cases.

- **Every command the guard flags is blocked by its stack's hook,** and by no other stack's hook.
- **Every command the guard passes is allowed by all four,** except the documented hook-only extras:
  cargo `check`, `clippy` and `+toolchain`; `mvnd`.

### §S7 — `init`

**Emission.** `init` emits each of the two new hooks for its stack: `block-direct-python-test` when
`python` is in the stacks, and `block-direct-bun-test` when `bun` is. Each is `pre-tool-use`, `bash`,
`core`, `closed`. The table comment above `_hook_instances` gains both rows.

**Refusal.** When hooks are compiled (a roster harness is selected), `init` checks during validation,
before the first write, that every hook it would emit has its script as a file in the deployed store. It
refuses (exit 2, nothing written) naming each missing script and `modelb-axi --reinstall`. A dry run
carries the refusal as a warning.

### §S8 — The gates this change moves

- **Tests that move:**
  - `tests/_helpers.write_install_toml` deploys `hooks-src/scripts/*` into its sandbox store, and so
    does every other install fixture that leads `init` to emit hooks;
  - `NOT_REGISTRY_KEYS` gains `ALLOW_RAW_PYTHON` and `ALLOW_RAW_BUN`;
  - `test_installer_assets` `HOOK_SCRIPT_NAMES`;
  - `test_hooks` `IMPORTED_SCRIPT_NAMES` and `ALL_SIX_SCRIPT_NAMES` (renamed for eight scripts);
  - `test_client_path_anchoring`'s reason checks cover all four hooks;
  - `test_pi_hook_runtime`'s cross-tool guard class covers the python and bun hooks;
  - `test_scaffold`'s hook-table docstring and `HooksSeamMultiPythonEmissionTest`.
- **Docs that move:**
  - `hooks-src/schema.md`'s security-class roster;
  - `AGENTS.md`: the hook-script count (8), the module count and the baselines.

### §S9 — After merge

**These steps are the user's and the orchestrator's; none is an acceptance criterion.**
1. The user reinstalls the tool from the tree (`uv tool install --reinstall --python 3.14 .`).
2. The user redeploys.
3. The orchestrator recompiles Model B's own wiring, which now includes `block-direct-python-test`, and
   commits it as a chore (DN §D21, first amendment).

## Acceptance criteria

- [ ] **The guard** catches §S1's three forms in every sample both ways, passes non-test scripts and
      client invocations, and stays clean on the guarded tree.
- [ ] **`block-direct-python-test` and `block-direct-bun-test`** exist, executable and stdlib-only.
      Each is proved by running the real script on payloads:
      - blocks every runner form of its stack at every command position and under every wrapper of
        §S2;
      - allows a runner word inside an argument, a client invocation, each non-runner mention, a
        non-`bash` tool, an unreadable payload and an untokenisable command;
      - allows under its escape hatch.
- [ ] **The marker rule**, in all four hooks, blocks when a marker sits at the git root or up to 3 levels
      under it. It does not block when the only marker sits deeper, sits in a skipped directory, or is
      absent. Without a git root, it checks the `cwd` and its ancestors. The Sandesh layout is a test
      case: python and bun markers in different directories, run from the root.
- [ ] **Every block reason** (four hooks) names the manifest, the client path and run verbs that the
      installed client's `--help` lists (checked against it when the client is installed), the escape
      hatch with the approval rule, and (python and bun) the two client gaps. None carries a stale
      reference of §S4.
- [ ] **The cargo and mvn hooks** block under every §S2 wrapper and keep their extras and their allowed
      goals.
- [ ] **Parity:** the §S6 corpus gives the verdicts §S6 states for all four hooks against the guard.
- [ ] **`init`** emits each new hook exactly for its stack (`pre-tool-use`, `bash`, `core`, `closed`).
      It refuses before the first write, and as a dry-run warning, when any emitted hook's script is
      missing from the store, naming it and `modelb-axi --reinstall`. It succeeds when all are present.
- [ ] **A sandboxed install** deploys both new scripts with the recorded interpreter in their shebang.
- [ ] **Gates that hold:**
      - every §S8 gate is updated as §S8 says;
      - the full suite passes through the client, with real `HOME` and with an empty `HOME` (the temp home
        empty afterwards);
      - `AGENTS.md`'s script count (8), module count and baselines are re-measured.

## Non-goals

- `make test`, `mvn install`, `vitest` and `jest`, and indented code blocks (the guard's reach).
- A shared detector module: each hook stays self-contained (CR-MDB-015), and §S6 keeps them in step.
- Re-wiring projects scaffolded before this change; re-running `init` (or a recompile) is the user's.
- The comma-separated "not" clause the guard documents as a limit.
