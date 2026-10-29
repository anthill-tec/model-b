# CR-MDB-066 — Runner-hook follow-ups: shell grammar, package-manager and Vitest forms, hardened block hooks

**Status:** PENDING — spec drafted 2026-10-30 from the gap analysis; spec pre-review to follow
**Type:** fix (hook scripts, the raw-runner guard, and the installer's shared offer)
**Priority:** P3 — release 1.0.0, wave 2; last in the wave, after its P1 CRs.
**Depends on:** CR-MDB-062 (merged `282eaa7`); CR-MDB-063 (merged; item 5). Board-authoritative: read
`queue`, not this line.
**Labels:** hooks, guard, enforcement, installer
**Points:** 13 (scored at gap analysis; seed unscored; the user ruled no split, 2026-10-30).
**Design reference:** DN-multi-harness-deploy-model §D21 (third amendment) and §D25; CR-MDB-062 §S1–§S6
and its non-goals; CR-MDB-015 (self-contained hook scripts); CR-MDB-063 §S1 (the shared `python3`
offer); PRD D5, ruling of 2026-10-29 (RED commits its failing tests).

## Context

CR-MDB-062's VERIFY (C5) found no defect in its scope and recorded five points outside it; CR-MDB-063's
VERIFY (F2) recorded the fifth. Read at gap analysis (2026-10-30, by reading the parsers; no run):

- **The guard and the four runner hooks share no code.** Each of `tests/test_raw_runner_guard.py` and the
  four `hooks-src/scripts/block-direct-*-test` holds its own `_SEPARATOR`, `_HEREDOC`, `_WRAPPER`,
  `_segments` and `_shell_words`; parity is kept by `RunnerHookGuardParityTest` on verdicts over one
  corpus. Every runner regex is anchored at the start of a command segment.
- **Forms they all miss** (guard and the hook of the runner's stack alike):
  - `{ pytest; }`, `if pytest;`, `do pytest`, `! pytest`, `command pytest`: the leading word is neither a
    separator nor a `_WRAPPER` alternative;
  - `time -p pytest`: `_WRAPPER`'s `time` takes no option;
  - ``echo `pytest` ``: an unquoted backquote is an ordinary character to `_segments`;
  - any line after `$((1<<2))`: `_HEREDOC` reads `<<2` as a heredoc, and `_skip_heredoc_bodies` swallows
    the lines up to a line `2`;
  - `npm t`, `npm run-script test`, `pnpm test`, `yarn test`, `bun run --filter <pkg> test`,
    `bun run --filter '*' test`, `vitest run`, `bunx vitest run`, `bun x vitest`: no `BUN_RUNNERS` row.
- **The bun hook's project test** is the marker rule (`package.json`, `bun.lock`, `bun.lockb`,
  `bunfig.toml`) and its wiring (`init` emits it only for a `bun` stack). §D25 (2026-10-18) brings
  `vitest` out of CR-MDB-062's non-goals for bun projects; `jest` stays out.
- **The bun reason presumes `bun test`:** "it runs the same `bun test`". Crucible's `bun-crucible.py`
  runs `bun test` for `test` and `regression`, and runs a declared `test:<tier>` script by name for a tier
  verb, refusing a tier the project declares no script for.
- **The other `block-*` hooks:** `block-cr-completed-without-spec-update`'s reason cites
  "ORCHESTRATOR-RULES.md §5 (Closing a CR — TWO files …)"; the rule lives in the model-b skill's
  `references/orchestration-common.md` § Close-out, step 6. It, `block-write-outside-worktree` and
  `post-regression-disk-reminder` catch only `JSONDecodeError`/`OSError` on the payload and check no field
  type, so nesting past the recursion limit, a number past the digit limit, non-UTF-8 stdin, a non-dict
  `tool_input`, a non-string `command` or `cwd` raise. The first two are emitted `closed` in multi mode, so
  a raise blocks the call.
- **The marker walk** lists each directory with `os.scandir` for its children and checks its markers by
  name; python's `_has_marker` also globs `requirements*.txt`, listing each directory a second time.
- **The shared installer offer** (`modelb_axi/toolchains.py` `remediate_toolchains`): per stack, the
  warning is emitted before the offer check, and the offer names the first stack only, so with
  `--stacks rust,bun` and no `python3` on `PATH` the prompt names `rust`, and after an accepted run bun's
  warning still reads `python3=absent` while `install.toml` records `installed`.

**Baseline:** to be measured by the orchestrator through the client before the branch cut (real `HOME`
and empty `HOME`), and recorded here with its time. (Measured by the orchestrator before the branch cut.)

## Scope

### §S1 — Command positions (the guard and all four runner hooks)

The same change lands in the guard and in each of the four hooks, in `_WRAPPER` and `_segments`:

1. **Reserved words.** `!`, `{`, `if`, `then`, `else`, `elif`, `while`, `until` and `do`, each a whole word
   followed by whitespace, are stepped over like a wrapper — any number of them, in any order with the
   other wrappers.
2. **`command`,** with an optional `-p`, is stepped over. `command -v <word>` and `command -V <word>` look
   a command up and run nothing: they stay allowed with no special case, since what follows `command` is
   then `-v …`, which no runner matches.
3. **`time`** takes an optional `-p`.
4. **Backquotes.** An unquoted backquote opens a command substitution: the text after it is a command
   position, up to the closing backquote. The text after the closing backquote continues the enclosing
   command and is no position. A backquote inside single or double quotes, or in a heredoc body, opens
   nothing (DN-multi-harness-deploy-model §D21, ruled 2026-10-30).
5. **Arithmetic.** `$((` up to its matching `))`, and a `((` … `))` at a command position, are skipped
   whole: nothing inside is a position, and no `<<` inside opens a heredoc. An unclosed one runs to the end
   of the text.

### §S2 — The bun forms (the guard's `BUN_RUNNERS` and the bun hook's)

Each is a runner of the `bun` stack, matched at a command position after §S1's wrappers, read in the
words the shell passes (quotes removed):

1. **The package managers' test script** (DN-multi-harness-deploy-model §D21, ruled 2026-10-30): `npm test`, `npm tst`, `npm t`;
   `pnpm test`; `yarn test`; and `run` / `run-script` before `test` or `test:<name>` for `bun`, `npm`,
   `pnpm` and `yarn` (`npm run-script test`, `pnpm run test:unit`, `yarn run test`).
2. **The workspace filter** (DN-multi-harness-deploy-model §D21, ruled 2026-10-30): between `run` and the script, any number of
   `--filter <pattern>` or `--filter=<pattern>` options (`bun run --filter <pkg> test`,
   `bun run --filter '*' test:unit`).
3. **Vitest** (DN-multi-harness-deploy-model §D21, ruled 2026-10-30): `vitest`, bare or by path (`node_modules/.bin/vitest`), with any
   arguments; and after `bunx`, `bun x` or `npx`, with `--bun` allowed after `bunx` or `bun x`
   (`bunx vitest run`, `bun x vitest`, `bunx --bun vitest run`, `npx vitest`).

**Never a runner:** `vitest.config.ts`, `@vitest/coverage-v8`, `bun add -d vitest`, `npm i vitest`,
`bunx vitest-preview`, `pnpm install`, `yarn install`, `yarn add -D jest`, `npm run testdata`,
`bun run --filter <pkg> build`, `npm run-script build`.

Only the bun hook blocks these; the python, cargo and mvn hooks allow them.

### §S3 — The bun reason

`block-direct-bun-test`'s `REASON`:
1. Its first line names the forms it blocks: `bun test`, `bun run test[:<name>]` (a `--filter` included),
   the `npm` / `pnpm` / `yarn` test-script forms, `playwright test` and `vitest`.
2. "it runs the same `bun test`" goes. The client runs the project's tests and ingests the results under
   the agent's id; the reason presumes no runner.
3. The tier line reads: a tier verb runs the `test:<tier>` script the project declares in `package.json`,
   by name, and the client refuses a tier the project declares no script for.
4. (DN-multi-harness-deploy-model §D21, ruled 2026-10-30) One more line: `test` and `regression` run `bun test`; a project whose runner
   is another (Vitest under Bun) runs its suites with the tier verbs.

It keeps CR-MDB-062 §S4's contract: the manifest, the client path, exactly the verbs `test`, `check`,
`unit`, `module`, `integration`, `e2e`, `bdd`, `regression`, the gap "a single test selected by name",
and `ALLOW_RAW_BUN=1` with the orchestrator's approval.

### §S4 — The marker walk (all four runner hooks) (DN-multi-harness-deploy-model §D21, ruled 2026-10-30)

1. **One listing per directory.** A run lists a directory at most once, with `os.scandir` (a per-run memo
   of listings), and that listing serves both its markers and its child directories. A marker is a
   listed entry whose name is one of the stack's marker names — or, for python, matches
   `requirements*.txt` (`fnmatch.fnmatchcase`) — and which is a file, following a symlink as
   `Path.is_file` did. Python's `Path.glob` goes.
2. **A directory that cannot be listed** is checked by name for its literal markers and its `.git` entry,
   as today, and is not descended. So an execute-only directory still counts a literal marker it holds,
   and a `requirements*.txt` in it is not found — as today.
3. **Unchanged:** where the walk looks (the `cwd`, its parents up to and including the git root, ≤3
   levels below the git root; without a git root, the `cwd` and its parents), what it skips (hidden
   directories, `node_modules`, `.venv`, `venv`, `target`, `dist`, `build`, directory symlinks), sorted
   order, first-marker stop, and the allow on any filesystem error.

### §S5 — The other `block-*` hooks

1. **The payload prelude.** `block-cr-completed-without-spec-update`, `block-write-outside-worktree` and
   `post-regression-disk-reminder` take the runner hooks' prelude:
   - the read catches `(ValueError, OSError, RecursionError)`, with the runner hooks' comment (bad JSON or
     UTF-8, a number past the digit limit, nesting past the recursion limit);
   - the payload must be a dict, `tool_input` a dict, and `command` (bash hooks) and `cwd` strings, or the
     hook allows (`post-regression-disk-reminder` stays silent). `block-write-outside-worktree` keeps its
     `os.getcwd()` fallback for an absent `cwd` and allows on a present non-string one.
2. **The close-out reference.** `block-cr-completed-without-spec-update`'s reason drops
   "ORCHESTRATOR-RULES.md §5" and "TWO files must be updated, always", and names the model-b skill's
   `orchestration-common.md` § Close-out: the spec's `**Status:**` flip is a docs-only commit on the
   feature branch before the merge. The fix instruction and the bypass sentence stay. Proposed text:

   > ⛔ BLOCKED: the commit message says COMPLETED for CR(s) [{crs}] but the staged diff does not include
   > the CR spec file(s) under docs/changes/. The close-out's `**Status:**` flip (the model-b skill's
   > orchestration-common.md § Close-out, step 6) is a docs-only commit on the feature branch before the
   > merge: flip the spec's `**Status:**` field to COMPLETED, `git add` the spec, then retry. To bypass
   > (rare — a docs-only commit that does not close the CR): remove the COMPLETED keyword from the commit
   > message.

### §S6 — The shared installer's offer (ruled 2026-10-30: stays in this CR; Q8 shape)

In `modelb_axi/toolchains.py` `remediate_toolchains`:
1. **Before any offer,** each installer argv is mapped to the stacks it covers: those, in selection order,
   with a not-`detected` tool that the argv installs.
2. **The prompt** names the tool and every stack it covers: `Run `<display>`<with env> to install
   <tool> for stack <s>?` with one stack, `… for stacks <s1>, <s2>?` with more.
3. **After an accepted run that exits 0,** each covered stack is re-probed, as today. A later covered
   stack whose re-probe finds the tool gets no `<tool>=absent` warning; one whose re-probe does not keeps
   its own warning beside the re-probe's.
4. **A decline** is recorded once, naming every covered stack (`declined `<display>` — <tool> stays
   absent for stacks rust, bun`); each stack keeps its own `absent` warning.
5. **Unchanged:** the first covered stack's warning precedes the offer; one offer per installer per run;
   `--yes`, a non-TTY run and an unresolved runner make no offer and leave every stack its own warning; a
   failed installer records `absent`; the `[capabilities]` keys.

The function and module docstrings say so ("each tool its own warning" gains the covered-and-installed
exception).

### §S7 — Records and docstrings

1. **The DN** — recorded by the orchestrator with the locked spec, before the branch (a docs-only commit
   on `develop`, its doc gates run): a new §D21 amendment records this gap analysis's rulings (§S1's
   positions; §S2's forms; Q2–Q9 as ruled 2026-10-30), and the third amendment's "`vitest` and `jest` … stay outside
   it" gains "(`vitest`: §D25 brings it in for bun projects)". CR-MDB-062's spec is history and is not
   edited.
2. **The guard's module docstring** ("**The runner**" paragraph and the `BUN_RUNNERS` bullet) and each
   runner hook's module docstring ("Command positions"; the bun hook's form list; "Where it applies" for
   §S4) state the new rules, each citing `CR-MDB-066 §S<n>`.
3. **The three §S5 hooks' docstrings** name the prelude.

### §S8 — The gates this change moves (named migrations)

1. **`tests/test_raw_runner_guard.py`:** new corpora `GRAMMAR_FORMS` (labelled), `GRAMMAR_NON_RUNNERS`,
   `PACKAGE_MANAGER_FORMS`, `FILTER_FORMS`, `VITEST_FORMS` (labelled `bun`) and `BUN_NON_RUNNERS`; each
   joins `test_every_corpus_entry_is_labelled_with_one_of_the_stacks_and_appears_once`'s lists;
   `OPTION_RUNS` gains a long `--filter` run that names a runner and one that does not.
2. **`tests/test_runner_hooks.py`:**
   - `_SINGLE_LINE_CORPORA` gains `PACKAGE_MANAGER_FORMS`, `FILTER_FORMS` and `VITEST_FORMS`;
     `_PLACED_CORPORA` gains `GRAMMAR_FORMS`; `_parity_corpus` gains every new corpus (`labelled` or
     `plain`); `NEVER_BLOCKED["bun"]` gains `BUN_NON_RUNNERS`;
   - `BLOCKED_POSITIONS` gains `"{ {run}; }"`, `"if {run}; then :; fi"`, `"if true; then {run}; fi"`,
     `"if false; then :; else {run}; fi"`, `"while {run}; do :; done"`, `"for f in a; do {run}; done"`,
     `"! {run}"`, `"command {run}"`, `"command -p {run}"`, `"time -p {run}"`, ``"echo `{run}`"``,
     ``"out=`{run}`"``, `"echo $((1<<2))\n{run}"` and `"((n<<2))\n{run}"`;
   - `ALLOWED_MENTIONS` gains `"command -v {run}"`, `"command -V {run}"`, ``"echo `date` {run}"``,
     `"echo $((1<<2)) {run}"` and ``'git commit -m "fix `{run}`"'`` and
     ``"cat <<EOF\n`{run}`\nEOF"``;
   - a new class for §S4 (below) and the source-identity check.
3. **`tests/test_client_path_anchoring.py`:** the bun reason's §S3 pins with their detector; the
   CR-completion reason's §S5.2 pins, reusing `STALE_REASON_REFERENCES`.
4. **`tests/test_hooks.py`:** a hostile-payload class for the three §S5 hooks.
5. **`tests/test_installer_stack_selection.py`** **(§S6)**: MIGRATED
   `Python3OfferRemediationTest.test_an_accepted_offer_runs_once_and_is_reprobed_for_every_stack` (its
   "each stack its own warning" loop asserted `stack bun: python3=absent` after the accept);
   `test_a_declined_offer_is_made_once_and_runs_nothing` (the decline names both stacks);
   `Python3OfferOnAUvOnlyMachineTest.test_an_accepted_offer_runs_uv_once_and_records_installed_for_every_stack`
   (the envelope's warnings).

No test module is added: `AGENTS.md`'s module count is unchanged. No new skip.

## Acceptance criteria

Every corpus check runs the guard's `stack_of` / `runner_findings` and the REAL hook scripts
(`tests._helpers.run_hook`) in `/tmp` trees (`tests._helpers.build_tree`); a traceback on stderr fails a
check. "Both ways" means a sample that must be caught is caught and a sample that must pass passes.

- [ ] **AC1 — §S1 in the guard.** Each `GRAMMAR_FORMS` entry gets its stack from `stack_of`; each
      single-line one is caught by `runner_findings` in a code span and on a fenced line. Each
      `GRAMMAR_NON_RUNNERS` entry (`command -v pytest`, `command -V cargo`, ``echo `date` pytest``,
      `echo $((1<<2)) pytest`, `if [ -f pytest.ini ]; then echo y; fi`, `ifconfig`, and
      ``git commit -m "fix `pytest`"``) gives `None` and no finding. `GRAMMAR_FORMS` holds at least one
      entry per §S1 item for each of `python`, `bun`, `cargo` and `mvn`, and `{ make junit; }` for `make`.
      `GuardedTreeHasNoRawRunnerTest` passes.
- [ ] **AC2 — §S1 in the hooks.** For each of the four hooks, in a project holding its marker: every
      `BLOCKED_POSITIONS` entry above, formatted with the hook's plain runner, blocks; every new
      `ALLOWED_MENTIONS` entry allows. `RunnerHookGuardParityTest` passes on the grown corpus: each
      command the guard assigns to a stack is blocked by that stack's hook only, each it passes is allowed
      by all four.
- [ ] **AC3 — §S2.** `stack_of` names `bun` for every `PACKAGE_MANAGER_FORMS`, `FILTER_FORMS` and
      `VITEST_FORMS` entry and `None` for every `BUN_NON_RUNNERS` entry. The bun hook blocks each form in a
      project holding any one bun marker, and re-placed by `FORM_PLACEMENTS`; allows each in a project with
      only `pyproject.toml`; allows every `BUN_NON_RUNNERS` entry. The python, cargo and mvn hooks allow
      every form. The two new `OPTION_RUNS` entries are judged by the guard and by all four hooks within
      `OPTION_RUN_BUDGET`, with the expected verdict.
- [ ] **AC4 — §S3.** The real bun reason (blocking `bun test` in a project with `package.json`):
      - keeps `_reason_contract_failures(reason, RUNNER_HOOK_REASONS["block-direct-bun-test"]) == []`;
      - its first line names `vitest`, `pnpm`, `yarn` and `--filter`;
      - carries no "same `bun test`";
      - has one paragraph naming `test:<tier>`, `declares` and `refuses`;
      - has one paragraph naming `regression`, `bun test`, `Vitest` and the tier verbs.

      A detector `bun_reason_findings(reason)` returns one finding per broken point; proved both ways on
      synthetic reasons: a conforming one passes, and each point cut alone yields exactly its finding.
- [ ] **AC5 — §S4.** For each of the four hooks, loaded in process with
      `importlib.machinery.SourceFileLoader`, `_in_project` on a `/tmp` tree with a `.git` directory, no
      marker, directories `a/b/c/d`, `e/f`, `node_modules/x`, `.hidden/y` and a directory symlink
      `link -> a`, run from the root and from `e/f`:
      - `os.scandir` (wrapped, recording) lists root, `a`, `a/b`, `a/b/c`, `e` and `e/f` exactly once each,
        and never `a/b/c/d`, `node_modules`, `.hidden` or `link`;
      - `pathlib.Path.glob` is never called (patched to raise).

      The recorder is proved both ways on a synthetic walk: a second listing of one directory and a glob
      call are each reported. Execute-only directory (chmod 0o111, restored in `tearDown`), through the real
      scripts: a literal marker inside it blocks, a marker only below it allows, and (python) a
      `requirements.txt` inside it allows. Every existing `_MarkerRule`, `_MarkerVariants`,
      `_SandeshStack` and `_NotASandeshStack` check passes unchanged.
- [ ] **AC6 — §S5.1.** Each of the three §S5 hooks, run as a subprocess, exits 0 with empty stdout and no
      `Traceback` on:
      - the four payloads of `_FailOpen.test_allows_a_hostile_payload_without_a_traceback` (open array,
        closed array, nested object, 5000-digit number);
      - the bytes `b"\xff\xfe{"` with `PYTHONIOENCODING=utf-8:strict`;
      - `tool_input` a list and a string;
      - `command` an integer (the two bash hooks);
      - `cwd` an integer, with a command or path that reaches it: `git commit -m "COMPLETED CR-X-1"` for
        the CR hook, a `write` to `x` with `WF_WORKTREE_ROOT` unset for the worktree hook.

      Both ways: the same harness, run on a temp script holding the pre-change prelude
      (`except (json.JSONDecodeError, OSError)`, no type checks), reports a traceback for every case.
      `BlockWriteOutsideWorktreeScriptTest` and `RemainingGuardScriptsSmokeTest` pass unchanged.
- [ ] **AC7 — §S5.2.** The source of `block-cr-completed-without-spec-update` matches none of
      `STALE_REASON_REFERENCES` and carries no "TWO files"; its reason string names
      `orchestration-common.md`, `Close-out`, `**Status:**` and `COMPLETED`. The check is proved both ways:
      the current reason sentence ("Per ORCHESTRATOR-RULES.md §5 …") fails it, §S5.2's text passes.
- [ ] **AC8 — §S6** (ruled 2026-10-30). Through the real `remediate_toolchains`, `run_on_terminal` and
      `shutil.which` stubbed, rust and bun with `python3=absent`:
      - **one prompt:** it names `uv python install --default 3.14`, `python3`, `rust` and `bun`;
      - **accept, found:** the installer runs once; both verdicts are `installed`; the warnings hold
        exactly one `stack rust: python3=absent` and none beginning `stack bun: python3=`;
      - **accept, not found** (the re-probe's `which` returns `None`): both verdicts are `absent`; each
        stack has its re-probe warning, and bun keeps its own `stack bun: python3=absent`;
      - **decline:** nothing runs; both verdicts are `absent`; one decline warning names `rust` and `bun`;
        each stack keeps its own `absent` warning;
      - **one stack** (rust only): the prompt reads `… to install python3 for stack rust?`.

      Through the real installer on a uv-only machine (`Python3OfferOnAUvOnlyMachineTest`), an accepted
      offer leaves no `stack bun: python3=absent` in the envelope's warnings and records both keys
      `installed`. `--yes` behaviour is unchanged (`test_yes_never_runs_it_and_names_it_for_every_stack`
      passes).
- [ ] **AC9 — §S7.** Each edited docstring cites `CR-MDB-066 §S<n>` and states the rule it implements;
      `test_s1_block_hook_docstrings_name_the_manifest_listed_client` passes.
- [ ] **AC10 — source identity.** The definitions `_SEPARATOR`, `_HEREDOC`, `_ENV_OPTION`,
      `_TIMEOUT_OPTION`, `_WRAPPER`, `_skip_heredoc_bodies`, `_segments`, `_commands`, `_shell_words`,
      `_marker_below` and `_in_project` have the same source (`ast.unparse`) in the four runner hooks. The
      check is proved both ways on synthetic sources: identical copies pass, one changed copy is reported
      by name.
- [ ] **AC11 — Gates.**
      - `ruff check` exits 0;
      - every module named in the cycle plan passes through the client;
      - `RunnerHookScriptsSelfContainedTest` passes (stdlib only, no sibling, no loader);
      - no test module is added and no skip is added;
      - `NOT_REGISTRY_KEYS` gains any env-shaped name a new reason or docstring carries;
      - VERIFY runs the full suite through the client with a real `HOME` and an empty one, and the empty
        `HOME` stays empty.

## Non-goals

- **Forms still outside the guard and the hooks:**
  - `case` arms, function bodies (`f() { pytest; }`, `function f { … }`), `let x=1<<2`, `$[…]`;
  - command substitution inside double quotes or an unquoted heredoc body (the user ruled unquoted backquotes only);
  - CR-MDB-062's remaining non-goals: `make test`, `mvn install`, `jest`, `python3 -m tests.test_x`,
    `bash -c`, `sudo`, `xargs`, `nohup`, `exec`;
  - package-manager selectors other than §S2.2's `--filter` (`npm -w`, `pnpm -r` / `--filter`,
    `yarn workspace(s)`), `bun --filter <p> test`, and `bun run vitest`, `pnpm exec vitest`,
    `yarn vitest`.
- **A shared detector module.** Each hook stays self-contained (CR-MDB-015, §D21); parity and source
  identity keep them in step.
- **A timing criterion for §S4.** The walk's cost is not asserted; listings are.
- **NUL bytes in a path** reaching `block-write-outside-worktree`'s `os.path.realpath`: no file can carry
  one, and the `closed` block on such a write blocks nothing real.
- **`ambient-board-status`:** it already catches every exception.
- **`generator/stacks/bun.toml`'s `bun test` default and Sandesh default** — CR-MDB-079's.
- **`docs/install-guide.md` § Install offers and its copy in `pi-package/README.md`:** "offered once for all
  the stacks you choose" stays true; no edit.
- **CR-MDB-062's spec:** history, not edited.
- **Re-wiring existing projects:** the Pi shim runs the deployed store's script by path, so a reinstall
  updates them.

## After merge

None of these steps is an acceptance criterion.
1. The user reinstalls the tool from the tree (`uv tool install --reinstall --python 3.14 .`) and
   redeploys (`modelb-axi --reinstall`).
2. The orchestrator recompiles Model B's own wiring and commits it as a chore (§D21, first amendment), if
   the recompiled wiring differs.

## Cycle plan

Nothing stays red past a cycle's GREEN: RED commits its failing tests on their own (test-only), and GREEN
makes them pass in the same cycle, once `ruff check` exits 0 (PRD D5, ruled 2026-10-29). A test that reads
a file a cycle changes is migrated in that cycle. Nobody runs the full suite between cycles; VERIFY runs it
once. Each cycle runs, through the client, the modules named below, plus the docs gates of `AGENTS.md`
(`tests.test_client_path_anchoring`, `tests.test_project_registry_schema`, `tests.test_suite_hygiene`,
`tests.test_archive_mapping`, `tests.test_cite_by_symbol`, `tests.test_harness_neutral_skills`,
`tests.test_axi_envelope_read_whole`, `tests.test_orchestration_rules_from_crucible`,
`tests.test_raw_runner_guard`, `tests.test_tooling_detachment`, `tests.test_claude_era_retirement`,
`tests.test_prd_criteria`). A module found reading an edited file and not named is run too, and named in
the cycle's report.

**The hook-script readers** (every cycle that edits `hooks-src/scripts/`): `tests.test_runner_hooks`,
`tests.test_hooks`, `tests.test_pi_hook_runtime`, `tests.test_bootstrap_shutdown_registry`,
`tests.test_installer_assets`, `tests.test_deployed_script_rendering`, `tests.test_hooks_compiler`,
`tests.test_init_hook_script_check`, `tests.test_hook_retirement`, `tests.test_coverage_gate`,
`tests.test_lint_rule_set`, `tests.test_crucible_project_config`, `tests.test_deployed_script_invocation`,
`tests.test_worktree_flow_surfaces`, `tests.test_orchestrator_references`, `tests.test_toon_codec`.

0. **Before the branch (orchestrator, not a cycle):** the DN amendment of §S7.1, a docs-only commit on
   `develop`, its doc gates plus `tests.test_board_holds_the_queue` and
   `tests.test_ide_overlay_retirement` (DN readers).
1. **Command positions** (§S1, §S7.2 for positions, §S8.1–§S8.2 positions part). Red-green.
   - **RED:** `GRAMMAR_FORMS`, `GRAMMAR_NON_RUNNERS`, the new `BLOCKED_POSITIONS` / `ALLOWED_MENTIONS`,
     the corpus wiring.
   - **GREEN:** `_WRAPPER` and `_segments` in the guard and the four hooks; docstrings.
   - **Modules:** the docs gates and the hook-script readers.
2. **The bun forms and the bun reason** (§S2, §S3, §S7.2 for the bun hook, §S8.1–§S8.3 bun part).
   Red-green.
   - **RED:** the four bun corpora, `OPTION_RUNS`, `NEVER_BLOCKED["bun"]`, `bun_reason_findings` and its
     proofs.
   - **GREEN:** `BUN_RUNNERS` in the guard and the bun hook; `REASON`; docstrings.
   - **Modules:** as cycle 1.
3. **The marker walk** (§S4; §S8.2's walk class). Red-green.
   - **RED:** the in-process listing test and its recorder proof; the execute-only cases.
   - **GREEN:** `_has_marker` / `_marker_below` / `_in_project` in the four hooks; their docstrings; —
     the source-identity check lands here, after the last edit to the shared helpers.
   - **Modules:** as cycle 1.
4. **The other block hooks** (§S5, §S7.3, §S8.3–§S8.4). Red-green.
   - **RED:** the hostile-payload class and its pre-change proof; the CR-completion reason pins.
   - **GREEN:** the three hooks' preludes and the reason.
   - **Modules:** the docs gates and the hook-script readers, plus the worktree hook's readers:
     `tests.test_worktree_layout_and_bundles`, `tests.test_pi_worktree_isolation`,
     `tests.test_worktree_isolation_text`, `tests.test_scaffold`.
5. **The shared installer's offer** (§S6, §S8.5).
   Red-green.
   - **RED:** the migrated and new `test_installer_stack_selection` checks.
   - **GREEN:** `remediate_toolchains` and its docstrings.
   - **Modules:** the docs gates, the package-wide gates (`tests.test_installer_correctness`,
     `tests.test_claude_era_retirement`, `tests.test_installer_stack_selection`), and
     `tests.test_harness_capability_contract`, `tests.test_install_guide`, `tests.test_project_tools_setup`,
     `tests.test_init_tool_verdicts`, `tests.test_installer_interpreter_probe`, `tests.test_installer`,
     `tests.test_installer_sandesh_requirements`, `tests.test_sandesh_install`.
6. **Verify.** VERIFY runs the full suite once, without coverage, through the client (§D26), and reads every
   AC. The orchestrator then runs the pre-merge gate and records the `AGENTS.md` baselines at close-out.
