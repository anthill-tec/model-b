# CR-MDB-066 — Runner-hook follow-ups: shell grammar, package-manager and Vitest forms, hardened block hooks

**Status:** PENDING — spec drafted 2026-10-30 from the gap analysis; the spec pre-review's findings
(`CR-MDB-066-SPEC-REVIEW`, FIX_REQUIRED) folded in 2026-10-30
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
and empty `HOME`), and recorded here with its time.

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
   - **The enclosing segment is unchanged:** it still runs to its own end, the substitution included, so
     its words after the closing backquote stay its arguments (``mvn -Drevision=`git describe` test``
     blocks, as it does today). The substitution adds one segment of its own, from just after the opening
     backquote to just before the closing one.
   - **An unclosed backquote** is read as an unclosed quote: the hooks allow, and no corpus entry holds
     one.
5. **Arithmetic.** An unquoted `$((` or `((`, wherever it stands, up to the `))` that brings its
   parenthesis depth back to zero, is skipped whole: nothing inside is a position, and no `<<` inside opens
   a heredoc (`while ((n<<1)); do` swallows no later line). An unclosed one runs to the end of the text.

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
   `requirements*.txt` (`fnmatch.fnmatchcase`) — and which `os.path.isfile(entry.path)` accepts (a stat,
   symlinks followed, any error read as not a file — `Path.is_file`'s answer). Never
   `DirEntry.is_file()`: it answers from `d_type` in a directory that can be listed but not searched, and
   raises on a marker-named symlink loop. Python's `Path.glob` goes.
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
   - the payload must be a dict, `tool_input` a dict, `command` a string (bash hooks) and `cwd` a string
     where the hook reads it (the two block hooks; `post-regression-disk-reminder` never reads `cwd`), or
     the hook allows (`post-regression-disk-reminder` stays silent). `block-write-outside-worktree` keeps its
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

1. **The DN** — recorded by the orchestrator before the branch, a docs-only commit on `develop` with its
   doc gates run; landed in `a9f375d`: a new §D21 amendment records this gap analysis's rulings (§S1's
   positions; §S2's forms; Q2–Q9 as ruled 2026-10-30), and the third amendment's "`vitest` and `jest` …
   stay outside it" gains "(`vitest`: §D25 brings it in for bun projects; CR-MDB-066)". CR-MDB-062's spec
   is history and is not edited. The amendment's arithmetic clause names `$((…))` and §S1.5's bare `((…))`
   (the second recorded with this spec, as the same ruling's arithmetic skip).
2. **The guard's module docstring** ("**The runner**" paragraph and the `BUN_RUNNERS` bullet) and each
   runner hook's module docstring ("Command positions"; the bun hook's form list; "Where it applies" for
   §S4) state the new rules, each citing `CR-MDB-066 §S<n>`.
3. **The three §S5 hooks' docstrings** name the prelude.

### §S8 — The gates this change moves (named migrations)

1. **`tests/test_raw_runner_guard.py`:** new corpora `GRAMMAR_FORMS` (labelled), `GRAMMAR_NON_RUNNERS`,
   `PACKAGE_MANAGER_FORMS`, `FILTER_FORMS`, `VITEST_FORMS` (labelled `bun`) and `BUN_NON_RUNNERS`; each
   joins `test_every_corpus_entry_is_labelled_with_one_of_the_stacks_and_appears_once`'s lists;
   `OPTION_RUNS` gains a long `--filter` run that names a runner and one that does not. The
   `GRAMMAR_FORMS` and `GRAMMAR_NON_RUNNERS` checks place each entry in a code span delimited by a backtick
   run longer than any run the entry holds, padded with a space on each side (AC1).
2. **`tests/test_runner_hooks.py`:**
   - `_SINGLE_LINE_CORPORA` gains `PACKAGE_MANAGER_FORMS`, `FILTER_FORMS` and `VITEST_FORMS`;
     `_PLACED_CORPORA` gains `GRAMMAR_FORMS`; `_parity_corpus` gains every new corpus (`labelled` or
     `plain`); `NEVER_BLOCKED["bun"]` gains `BUN_NON_RUNNERS`;
   - `BLOCKED_POSITIONS` gains `"{{ {run}; }}"` (formats to `{ <run>; }`), `"if {run}; then :; fi"`, `"if true; then {run}; fi"`,
     `"if false; then :; else {run}; fi"`, `"while {run}; do :; done"`, `"for f in a; do {run}; done"`,
     `"! {run}"`, `"command {run}"`, `"command -p {run}"`, `"time -p {run}"`, ``"echo `{run}`"``,
     ``"out=`{run}`"``, `"echo $((1<<2))\n{run}"`, `"((n<<2))\n{run}"` and
     `"while ((n<<1)); do\n{run}\ndone"`;
   - `PARITY_FORMS` gains ``("mvn -Drevision=`git describe` test", "mvn")`` (blocked today; §S1.4's
     unchanged enclosing segment keeps it blocked);
   - `ALLOWED_MENTIONS` gains `"command -v {run}"`, `"command -V {run}"`, ``"echo `date` {run}"``,
     `"echo $((1<<2)) {run}"` and ``'git commit -m "fix `{run}`"'`` and
     ``"cat <<EOF\n`{run}`\nEOF"``;
   - a new class for §S4 (AC5), its in-process loader living once in `tests/_helpers.py` (CR-MDB-032
     §S3);
   - the source-identity check (AC10), added in cycle 1.
3. **`tests/test_client_path_anchoring.py`:** the bun reason's §S3 pins with their detector; the
   CR-completion reason's §S5.2 pins with their detector, reusing `STALE_REASON_REFERENCES` (AC7).
4. **`tests/test_hooks.py`:** a hostile-payload class for the three §S5 hooks.
5. **`tests/test_installer_stack_selection.py`** **(§S6)**: MIGRATED
   `Python3OfferRemediationTest.test_an_accepted_offer_runs_once_and_is_reprobed_for_every_stack` (its
   "each stack its own warning" loop asserted `stack bun: python3=absent` after the accept);
   `test_a_declined_offer_is_made_once_and_runs_nothing` (the decline names both stacks);
   `Python3OfferOnAUvOnlyMachineTest.test_an_accepted_offer_runs_uv_once_and_records_installed_for_every_stack`
   (the envelope's warnings).

No test module is added: `AGENTS.md`'s module count is unchanged. No new skip.

### §S9 — VERIFY's findings (cycle 318, approved by the user 2026-10-30)

1. **A `tool_name` that is not a string allows** in `block-write-outside-worktree`. Today a list or dict
   `tool_name` raises `TypeError` on the `_GATED_TOOLS` set lookup, and the hook is `closed`, so the raise
   blocks the call — the class §S5.1 removes. The check reads `tool_name` as a string before the lookup.
2. **A staged path git prints in bytes that are not UTF-8 allows** in
   `block-cr-completed-without-spec-update`: `_staged_paths` catches `ValueError` (with `OSError` and
   `TimeoutExpired`) and returns no paths, so the hook allows. Today `text=True` raises
   `UnicodeDecodeError` under `core.quotepath=false`, in a `closed` hook.
3. **The unclosed backquote's divergence is pinned as deliberate.** On `echo hi; pytest \`` the guard names
   `python` (it reads up to the line's end) while the four hooks allow (they read an unclosed backquote as
   an unclosed quote, §S1.4, and bash refuses the line). A named corpus, `UNCLOSED_BACKQUOTE_DIVERGENCE`,
   holds the forms with both verdicts; the parity test reads it as the only sanctioned divergence.
4. **Nested escaped backquotes are a non-goal** (`` echo `echo \`pytest\`` `` runs `pytest`; neither the guard
   nor the hooks re-parse an escaped backquote inside a substitution).

## Acceptance criteria

Every corpus check runs the guard's `stack_of` / `runner_findings` and the REAL hook scripts
(`tests._helpers.run_hook`) in `/tmp` trees (`tests._helpers.build_tree`); a traceback on stderr fails a
check. "Both ways" means a sample that must be caught is caught and a sample that must pass passes.

- [ ] **AC1 — §S1 in the guard.** Each `GRAMMAR_FORMS` entry gets its stack from `stack_of`; each
      single-line one is caught by `runner_findings` in a code span — delimited by a backtick run longer
      than any run the entry holds, padded with a space on each side (``` `` echo `pytest` `` ```) — and
      on a fenced line. Each `GRAMMAR_NON_RUNNERS` entry (`command -v pytest`, `command -V cargo`,
      ``echo `date` pytest``, `echo $((1<<2)) pytest`, `if [ -f pytest.ini ]; then echo y; fi`, `ifconfig`,
      and ``git commit -m "fix `pytest`"``) gives `None` and no finding, in both placements.
      `GRAMMAR_FORMS` holds at least one entry per §S1 item for each of `python`, `bun`, `cargo` and `mvn`,
      and `{ make junit; }` for `make`.
      `GuardedTreeHasNoRawRunnerTest` passes.
- [ ] **AC2 — §S1 in the hooks.** For each of the four hooks, in a project holding its marker: every
      `BLOCKED_POSITIONS` entry above, formatted with the hook's plain runner, blocks; every new
      `ALLOWED_MENTIONS` entry allows. `RunnerHookGuardParityTest` passes on the grown corpus: each
      command the guard assigns to a stack is blocked by that stack's hook only, each it passes is allowed
      by all four.
- [ ] **AC3 — §S2.** `stack_of` names `bun` for every `PACKAGE_MANAGER_FORMS`, `FILTER_FORMS` and
      `VITEST_FORMS` entry and `None` for every `BUN_NON_RUNNERS` entry. The bun hook blocks each form in a
      project holding each of the four bun markers alone, and re-placed by `FORM_PLACEMENTS`; allows each
      in a project with only `pyproject.toml`; allows every `BUN_NON_RUNNERS` entry. The python, cargo and mvn hooks allow
      every form. The two new `OPTION_RUNS` entries are judged by the guard and by all four hooks within
      `OPTION_RUN_BUDGET`, with the expected verdict.
- [ ] **AC4 — §S3.** The real bun reason (blocking `bun test` in a project with `package.json`):
      - keeps `_reason_contract_failures(reason, RUNNER_HOOK_REASONS["block-direct-bun-test"]) == []`;
      - its first line names `vitest`, `pnpm`, `yarn` and `--filter`;
      - carries no "same `bun test`";
      - has one line (one physical line of the reason) naming `test:<tier>`, `declares` and `refuses`;
      - has one line naming `regression`, `bun test`, `Vitest` and the words `tier verbs`.

      A detector `bun_reason_findings(reason)` returns one finding per broken point; proved both ways on
      synthetic reasons: a conforming one passes, and each point cut alone yields exactly its finding.
- [ ] **AC5 — §S4.** For each of the four hooks, loaded in process with
      `importlib.machinery.SourceFileLoader` with bytecode writing off (`sys.dont_write_bytecode` set for
      the load and restored after it, so no `__pycache__` lands under `hooks-src/scripts/`; the loader
      lives once in `tests/_helpers.py`, CR-MDB-032 §S3), `_in_project` on a `/tmp` tree with a `.git`
      directory, no marker, directories `a/b/c/d`, `e/f`, `node_modules/x`, `.hidden/y` and a directory
      symlink `link -> a`, run from the root and from `e/f`:
      - `os.scandir` (wrapped, recording each listed path after `os.path.realpath`) lists root, `a`, `a/b`,
        `a/b/c`, `e` and `e/f` exactly once each, and never `a/b/c/d`, `node_modules`, `.hidden` or `link`;
      - `pathlib.Path.glob` (wrapped, recording each call and raising nothing, since `_in_project` reads an
        `OSError` or `ValueError` as "not a project") is called zero times.

      The recorder is proved both ways on a synthetic walk: a second listing of one directory and a glob
      call are each reported. Through the real scripts, each chmod restored in `tearDown`:
      - an execute-only directory (chmod 0o111): a literal marker inside it blocks, a marker only below it
        allows, and (python) a `requirements.txt` inside it allows;
      - a read-only directory (chmod 0o444) one level below the git root, holding the stack's marker, run
        from the root: allows, as today (`os.path.isfile` cannot stat inside it).

      Every existing `_MarkerRule`, `_MarkerVariants`, `_SandeshStack` and `_NotASandeshStack` check passes
      unchanged.
- [ ] **AC6 — §S5.1.** Each of the three §S5 hooks, run as a subprocess, exits 0 with empty stdout and no
      `Traceback` on:
      - the four payloads of `_FailOpen.test_allows_a_hostile_payload_without_a_traceback` (open array,
        closed array, nested object, 5000-digit number);
      - the bytes `b"\xff\xfe{"` with `PYTHONIOENCODING=utf-8:strict`;
      - `tool_input` `["x"]` and `"x"` (truthy, so no `or {}` hides them);
      - `command` `5` (the two bash hooks);
      - `cwd` `5`, with a command or path that reaches it: `git commit -m "COMPLETED CR-X-1"` for the CR
        hook; a `write` to `x` for the worktree hook, with `WF_WORKTREE_ROOT` and
        `ALLOW_WRITE_OUTSIDE_WORKTREE` both removed from the environment.

      Both ways: the same harness, run on a temp script whose `main` has the pre-change catch
      (`except (json.JSONDecodeError, OSError)`) and then, untyped, calls `.get` on `tool_input`,
      `re.search` on `command` and `Path(cwd)`, reports a traceback for every case.
      `BlockWriteOutsideWorktreeScriptTest` and `RemainingGuardScriptsSmokeTest` pass unchanged.
- [ ] **AC7 — §S5.2.** The source of `block-cr-completed-without-spec-update` matches none of
      `STALE_REASON_REFERENCES` and carries no "TWO files". The reason is read from a real run: in a `/tmp`
      git repository holding `docs/changes/`, with a staged file outside it, the payload's command
      `git commit -m "COMPLETED CR-X-1"` exits 2, and the `reason` on its stdout is the one checked. A
      detector `cr_completion_reason_findings(reason)` returns one finding per broken point (a
      `STALE_REASON_REFERENCES` match; "TWO files"; a missing `orchestration-common.md`, `Close-out`,
      `**Status:**` or `COMPLETED`) and none on the real reason. Proved both ways on strings: the current
      reason sentence ("Per ORCHESTRATOR-RULES.md §5 …") yields findings, §S5.2's text yields none.
- [ ] **AC8 — §S6** (ruled 2026-10-30). Through the real `remediate_toolchains`, `run_on_terminal` and
      `shutil.which` stubbed, rust and bun with `python3=absent`:
      - **one prompt:** it names `uv python install --default 3.14`, `python3`, `rust` and `bun`;
      - **accept, found:** the installer runs once; both verdicts are `installed`; the warnings hold
        exactly one `stack rust: python3=absent` and none beginning `stack bun: python3=`;
      - **accept, not found** (the re-probe's `which` returns `None`): both verdicts are `absent`; the
        warnings hold exactly two re-probe warnings (one per stack; the re-probe warning names no stack:
        ``` `uv python install --default 3.14` exited 0 but python3 is still not found ``` …), and bun
        keeps its own `stack bun: python3=absent`;
      - **decline:** nothing runs; both verdicts are `absent`; one decline warning names `rust` and `bun`;
        each stack keeps its own `absent` warning;
      - **one stack** (rust only): the prompt reads `… to install python3 for stack rust?`.

      Through the real installer on a uv-only machine (`Python3OfferOnAUvOnlyMachineTest`), an accepted
      offer leaves no `stack bun: python3=absent` in the envelope's warnings and records both keys
      `installed`. `--yes` behaviour is unchanged (`test_yes_never_runs_it_and_names_it_for_every_stack`
      passes).
- [ ] **AC9 — §S7.** Each edited docstring cites `CR-MDB-066 §S<n>` and states the rule it implements;
      `test_s1_block_hook_docstrings_name_the_manifest_listed_client` passes.
- [ ] **AC10 — source identity.** In the four runner hooks, a definition is a top-level `def` or the
      value of a top-level assignment, compared by `ast.unparse`:
      - the named definitions `_SEPARATOR`, `_HEREDOC`, `_ENV_OPTION`, `_TIMEOUT_OPTION`, `_WRAPPER`,
        `_skip_heredoc_bodies`, `_segments`, `_commands`, `_shell_words`, `_marker_below` and `_in_project`
        exist in each hook (a missing one is reported by name) and have the same source;
      - so has every other top-level name all four hooks define, except the per-stack `MARKERS`, `REASON`,
        `_has_marker` and `main` (a helper a cycle adds to the shared parser or walk is covered with no
        list edit; a per-stack helper lives inside `_has_marker` or under a name not all four define).

      Added in cycle 1's RED and labelled as passing on arrival (all eleven names are identical today);
      it guards cycles 1–3's edits to the hooks' copies. Proved both ways on synthetic sources: identical
      copies pass; one changed named copy, one missing named definition, and one shared extra helper
      changed in one copy are each reported by name.
- [ ] **AC11 — Gates.**
      - `ruff check` exits 0;
      - every module named in the cycle plan passes through the client;
      - `RunnerHookScriptsSelfContainedTest` passes (stdlib only, no sibling, no loader);
      - no test module is added and no skip is added;
      - `NOT_REGISTRY_KEYS` gains any env-shaped name a new reason or docstring carries;
      - VERIFY runs the full suite through the client with a real `HOME` and an empty one, and the empty
        `HOME` stays empty.

- [ ] **AC12 — §S9.**
      - `BlockHookHostilePayloadTest`'s cases for `block-write-outside-worktree` gain `tool_name` `["write"]`
        and `{"a": 1}`; each allows with no traceback, and the pre-change proof shows the pre-§S9 lookup
        raising on both;
      - a real run of `block-cr-completed-without-spec-update` in a temp git repo with
        `core.quotepath=false`, a CR spec staged as `COMPLETED` beside a staged file whose name is not
        UTF-8 (`b"\xff.txt"`), exits 0 with no traceback; the same run on the pre-§S9 `_staged_paths`
        raises (proof both ways);
      - `UNCLOSED_BACKQUOTE_DIVERGENCE` holds at least `echo hi; pytest \`` and one form per hooked stack;
        the guard names each form's stack and every hook allows it; a form added to it that the guard and
        the hooks agree on fails the corpus's own check, and the parity test skips exactly these forms;
      - the non-goals name nested escaped backquotes.

## Non-goals

- **Forms still outside the guard and the hooks:**
  - `case` arms, function bodies (`f() { pytest; }`, `function f { … }`), `let x=1<<2`, `$[…]`;
  - command substitution inside double quotes or an unquoted heredoc body (the user ruled unquoted
    backquotes only);
  - an assignment or argument whose value is a substitution before the runner
    (``VAR=`mktemp -d` cargo test``, `VAR=$(mktemp -d) cargo test`) — an existing miss, as with `$(`
    today;
  - an escaped backquote nested inside a backquote substitution (`` echo `echo \`pytest\`` ``): no
    re-parse (§S9.4);
  - `command --` (`command -- pytest`): only `-p` is stepped over; the lookups `command -v` / `-V` (and
    `-pv`) already run nothing;
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
3. The orchestrator raises with Crucible, over Sandesh, the bun client's `regression` gap for projects
   whose runner is not `bun test` (§D21, amended 2026-10-30).

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
`tests.test_worktree_flow_surfaces`, `tests.test_orchestrator_references`, `tests.test_toon_codec`,
`tests.test_python_floor`, `tests.test_package_publishing`, `tests.test_installer_correctness`,
`tests.test_installer_stack_selection`, `tests.test_ambient_manifest_discovery`,
`tests.test_ambient_status_contract`.

**The guard importers** (every cycle that edits `tests/test_raw_runner_guard.py`'s detector):
`tests.test_stack_reference_material` (`runner_findings`), `tests.test_workflow_render`
(`GUARDED_ROOTS`), `tests.test_chrome_ui_relay_skill` (`_blocks`, `_code_spans`).

0. **Before the branch (orchestrator, not a cycle):** the DN amendment of §S7.1, a docs-only commit on
   `develop`, its doc gates plus `tests.test_board_holds_the_queue` and
   `tests.test_ide_overlay_retirement` (DN readers). Landed in `a9f375d`; the bare `((…))` was added to its arithmetic clause
   with the locked spec.
1. **Command positions** (§S1, §S7.2 for positions, §S8.1–§S8.2 positions part). Red-green.
   - **RED:** `GRAMMAR_FORMS`, `GRAMMAR_NON_RUNNERS`, the new `BLOCKED_POSITIONS` / `ALLOWED_MENTIONS`,
     the corpus wiring. Two additions pass on arrival and are labelled so: the `PARITY_FORMS` entry
     ``("mvn -Drevision=`git describe` test", "mvn")`` (it pins today's block) and the source-identity
     check (AC10), which guards cycles 1–3's edits to the hooks' copies.
   - **GREEN:** `_WRAPPER` and `_segments` in the guard and the four hooks; docstrings.
   - **Modules:** the docs gates, the hook-script readers and the guard importers.
2. **The bun forms and the bun reason** (§S2, §S3, §S7.2 for the bun hook, §S8.1–§S8.3 bun part).
   Red-green.
   - **RED:** the four bun corpora, `OPTION_RUNS`, `NEVER_BLOCKED["bun"]`, `bun_reason_findings` and its
     proofs.
   - **GREEN:** `BUN_RUNNERS` in the guard and the bun hook; `REASON`; docstrings.
   - **Modules:** as cycle 1.
3. **The marker walk** (§S4; §S8.2's walk class). Red-green.
   - **RED:** the in-process loader in `tests/_helpers.py`; the listing test and its recorder proof; the
     execute-only and read-only (0o444) cases.
   - **GREEN:** `_has_marker` / `_marker_below` / `_in_project` in the four hooks; their docstrings.
   - **Modules:** the docs gates and the hook-script readers.
4. **The other block hooks** (§S5, §S7.3, §S8.3–§S8.4). Red-green.
   - **RED:** the hostile-payload class and its pre-change proof; the CR-completion reason pins,
     `cr_completion_reason_findings` and its proofs.
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
7. **VERIFY's findings** (§S9; cycle 319, kind fix). Red-green.
   - **RED:** the two `tool_name` cases and their pre-change proof; the non-UTF-8 staged-path run and its
     proof; `UNCLOSED_BACKQUOTE_DIVERGENCE`, its own check and the parity test's reading of it.
   - **FIX:** `block-write-outside-worktree`'s `tool_name` check; `_staged_paths`'s catch.
   - **Modules:** the docs gates, the hook-script readers, the worktree hook's readers and the guard
     importers.
