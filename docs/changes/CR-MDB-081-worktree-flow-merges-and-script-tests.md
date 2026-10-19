# CR-MDB-081 — worktree-flow merges, never rebases; tests for it and the skill release gate

**Status:** PENDING — spec drafted 2026-10-19 from the gap analysis, the spec pre-review folded in;
awaiting approval.
**Type:** feature + tests (the deployed `worktree-flow.py` and `skill-release-gate.py`, and the rules
that name `sync`)
**Priority:** P1 — release 1.0.0, wave 2; after CR-MDB-078.
**Depends on:** CR-MDB-078 (its shared test harness). The board is authoritative: read `queue`.
**Labels:** tests, coverage, scripts, worktree
**Design reference:** PRD D5, the coverage ruling of 2026-10-17; DN-multi-harness-deploy-model §D25 (a
project's dependency services are its own and are never named in a shared tool);
`contracts/worktree-layout.md`.

## Context

Measured 2026-10-19 on develop by the whole suite under the `[tool.coverage]` config:
`scripts/worktree-flow.py` 333/537 statements, `scripts/skill-release-gate.py` 10/212. Every
`worktree-flow.py` path below is unexercised today: `sync`; `finish`'s catch-up, its refusals, its
partial worktree removal, a failed branch delete and `--push`; most of `abort`; `start`'s refusals; the
merge lock. `skill-release-gate.py` is exercised only for its usage line.

- **`sync` and `finish` rebase.** `sync --cr <cr>` rebases a CR's feature branch onto develop, and
  `finish` does the same when the branch is behind. A rebase rewrites the commits the board and VERIFY
  have recorded, so the orchestration rules forbid `sync` and tell the orchestrator to merge develop in
  by hand. The script's help, messages and docstrings describe rebasing throughout.
- **`status` reads the newest commit.** Its phase is inferred from the newest subject in
  `develop..<branch>`; once develop is merged into a branch, that is the merge commit. A branch that is
  behind shows `REBASE NEEDED`.
- **`abort` promises a board write.** Its dry run, its missing-`--reason` refusal and its `--reason`
  help say the cause is recorded on the CR in Crucible's queue; neither run writes to the board. The
  board records a dropped CR with the client's `cr-void --cr <id> --reason <why>` and a superseded one
  with `cr-supersede --cr <id> --by <successor>`.
- **A scheduler-note board nothing uses.** `status` lists `reschedule-request-*.md` and
  `directive-*.md` notes from `$WF_REQUEST_DIR` (or that key in the project's `.env`), for a
  `request-poll.py` watcher Model B does not ship. No shipped skill, template or script reads it;
  Sandesh carries track requests.
- **The skill release gate's discovery and teardown.** With no configured skill paths it looks in
  `skills/` and `.claude/skills/`; Pi's project skill roots are `.agents/skills/` and `.pi/skills/`. Its
  teardown carries a Mongo-drop step reading `VIDUSHI_MONGO_URI` — one project's dependency service
  inside a shared tool (§D25). Its generic `[teardown] cmd` runs a project's own command. Its phases 2
  and 3 build a wheel and install it into virtual environments that `Gate.make_venv` creates with pip,
  so they reach a package index.

## Steps

### §S1 — `sync` merges develop in

`sync --cr <cr>` brings the CR's feature branch level with develop by `git merge --no-edit <develop>`
in its worktree — a fast-forward where the branch has no commits of its own, a merge commit otherwise —
and never rebases:
- a branch already level reports so and runs nothing, clean or not;
- a branch that is behind, with uncommitted changes in its worktree, is refused before anything runs;
- a CR with no worktree, or a detached one, is refused naming the cause;
- a conflicting merge is aborted (`git merge --abort`), the branch and worktree are left as they were,
  the conflicting paths are named on stderr and the run exits non-zero;
- `--dry-run` prints the merge it would run and changes nothing.

### §S2 — `finish` catches up the same way

A branch that is behind develop is brought level by the same merge, inside the merge lock, before the
`--no-ff` merge into develop; with `--no-auto-sync` it is refused, naming `sync --cr <cr>`; with
`--dry-run` the catch-up merge is part of the printed plan. A conflicting catch-up is aborted, nothing
is merged into develop, the branch and worktree are left as they were, the lock is released and the run
exits non-zero. `finish` never rebases.

### §S3 — `status` after a merge

A branch that is behind shows the state `SYNC NEEDED (develop moved <n>)`. The phase and the envelope's
`commits_ahead` come from the branch's own commits, merge commits excluded, so a synced branch reports
the phase of its newest own commit. The envelope's `ahead` stays git's count of commits not on develop,
merge commits included.

### §S4 — The rules follow the tool

Each of these names `worktree-flow.py sync --cr <cr>` as the way a CR's worktree branch is brought level
before `finish`, and none forbids `sync` or tells the orchestrator to merge develop into a worktree
branch by hand:
- `skills-src/model-b/references/orchestration-common.md`, § Worktree isolation (basics);
- `skills-src/model-b/references/orchestration-track.md`;
- the `shutdown` skill's Step 2A;
- `skills-src/memory-templates/rust-orchestration.md`'s `worktree-flow.py` entry (`sync`, `finish`,
  `status`);
- `scripts/worktree-flow.py`'s module docstring, its five verbs' help, its function docstrings and its
  messages.

A CR worked on a feature branch in the main tree, with no worktree, still merges develop in by hand:
`sync` needs `.worktrees/<cr>`. The close-out's first step ("merge develop into the feature branch until
behind=0") keeps its wording.

### §S5 — `abort` promises nothing it does not do

`abort`'s dry run, its real run, its missing-`--reason` refusal and its `--reason` and `--superseded`
help describe only what `abort` does. Every `--cr` run that reaches its end — the dry run, a removal, and
a run that finds no worktree — closes with the board step the orchestrator takes next: for a dropped CR,
`cr-void --cr <cr> --reason "<reason>"`; with `--superseded`, `cr-supersede --cr <cr> --by <successor>`,
with the reason given as the cause. `--reason` stays required except with `--release-lock`, which prints
no board step. `--delete-branch` on a CR with no worktree deletes the branch when one exists.

### §S6 — The scheduler-note board is removed

`status` no longer reads `$WF_REQUEST_DIR` or the project's `.env`, and lists no scheduler notes; its
envelope and human board are otherwise unchanged. `orchestration-track.md`'s instruction to "raise a
reschedule-request" names a Sandesh request to Mainline instead.

### §S7 — The skill release gate names no project

- With no configured skill paths, phase 1 discovers `skills/<name>/SKILL.md`,
  `.agents/skills/<name>/SKILL.md` and `.pi/skills/<name>/SKILL.md`; `.claude/skills/` is no longer read.
- The teardown's Mongo-drop step and its `VIDUSHI_MONGO_URI` are removed; `[teardown] cmd` stays. A
  configuration carrying `[teardown] drop_mongo_db` is refused when the configuration loads, before any
  phase: the gate exits non-zero naming `[teardown] cmd` as the replacement.

### §S8 — Tests for every path

- **`worktree-flow.py`**, each case run as a subprocess: project resolution (`--project-dir`,
  `$WORKTREE_FLOW_PROJECT_DIR`, the current directory's repository, not a repository); `start` (each
  refusal, the local-develop note, the `.env` copy, the track label from `--track` and `$WF_TRACK`,
  `--dry-run`); `status` (the merge lock, detached and dirty worktrees, the track label, the phase,
  `SYNC NEEDED`); `sync` (every §S1 case, a branch with no own commits); `finish` (each refusal, the lock
  held by another finish, the catch-up merge and its conflict, `--dry-run` on a branch that is behind, a
  worktree removal that needs `--force`, a partial removal, a failed branch delete, `--push` succeeding
  and failing); `abort` (each refusal, `--force`, `--delete-branch` with and without a worktree, no
  worktree, `--superseded`, `--release-lock` real and dry, `--dry-run`).
- **`skill-release-gate.py`:** configuration discovery (`pyproject.toml`'s `[tool.skill-release]`, the
  standalone `.skill-release.toml`, `--config` nested or top-level, none) and the §S7 refusal, as
  subprocesses; phase 1 (discovery, an `agentskills` stand-in that passes and one that fails) as a
  subprocess. Phase 1 with `agentskills` absent, phase 2 (the wheel built or not, the entry point, a
  forbidden entry point, glob counts and globs), phase 3 (the console installed or not, the import
  check), phase 4 (every check field: `expect`, `expect_re`, `reject`, `json_type`, `allow_nonzero`,
  `combine_stderr`, the substitutions), the teardown and the exit codes run in process: the script
  loaded as a module, `Gate.make_venv` replaced by a stand-in returning a stand-in interpreter that
  writes a wheel or a console script, and `PATH` set in the test process for the stand-ins it calls.

### §S9 — Hermetic

The CR-MDB-078 harness binds every test: real git repositories in temp directories, stand-ins for
external programs, nothing written into this repository. A tool run's environment is the test process's
with only these changed: `PATH`; git's configuration variables; `TMPDIR`, a private directory set in the
test process; and the tools' own variables — `WORKTREE_FLOW_PROJECT_DIR`, `WF_TRACK`, `WF_REQUEST_DIR`,
`SKILLGATE_SOON` — each set or cleared by the test, never inherited from the session. No test reaches a
package index, and no test runs a real `pip`, `python -m build` or `ensurepip`.

## Acceptance Criteria

1. **AC1 — `sync`.** On a CR worktree whose branch has commits of its own and is behind develop,
   `sync --cr <cr>` exits 0; the branch then contains develop's head, its newest commit is a merge
   commit, every commit it held before keeps its sha, and behind is 0. On a branch with no commits of its
   own, `sync` fast-forwards it to develop's head. A conflicting `sync` exits non-zero, names each
   conflicting path on stderr, and leaves the branch head unchanged, the worktree's
   `git status --porcelain` empty and no merge in progress. A level branch, a dirty worktree that is
   behind, a missing or detached worktree and `--dry-run` behave as §S1 states.
2. **AC2 — `finish`'s catch-up.** A branch behind develop is merged into develop by `finish` with every
   pre-existing branch commit keeping its sha; `--dry-run` on it prints the catch-up merge and changes
   nothing; with `--no-auto-sync` it exits non-zero naming `sync --cr <cr>` and changes nothing; a
   conflicting catch-up exits non-zero, leaves develop's head and the branch head unchanged, the
   worktree's `git status --porcelain` empty with no merge in progress, and the merge lock released.
3. **AC3 — no rebase.** No string literal in `scripts/worktree-flow.py` passed as a git argument is
   `rebase`.
4. **AC4 — `status`.** For a CR branch with own commits followed by a `sync` merge, `status`'s envelope
   reports the phase of the newest own commit and a `commits_ahead` that excludes the merge commit, and
   an `ahead` that includes it. A branch that is behind has the `state`
   `SYNC NEEDED (develop moved <n>)`; no `state` contains `REBASE`.
5. **AC5 — the rules.** In each §S4 surface — `orchestration-common.md`'s § Worktree isolation (basics),
   `orchestration-track.md`, the `shutdown` skill's Step 2A, the rust template's `worktree-flow.py` entry
   — no sentence tells the orchestrator not to use `sync` or to merge develop into a worktree branch by
   hand, and `worktree-flow.py sync --cr <cr>` is named as the step before `finish`.
   `orchestration-common.md`'s close-out step 1 keeps its wording. In `scripts/worktree-flow.py`, no help
   text, message or docstring describes the tool as rebasing.
   `tests.test_bootstrap_shutdown_registry`'s check of the shutdown skill's develop merge asserts the
   `sync` form.
6. **AC6 — `abort`.** No `abort` output, refusal or help says it records anything on the board or
   Crucible's queue. A dry run, a removal and a no-worktree run each end with
   `cr-void --cr <cr> --reason "<reason>"`, or with `--superseded`
   `cr-supersede --cr <cr> --by <successor>`, as the orchestrator's next step; `--release-lock` prints
   neither. `abort --cr <cr>` without `--reason` exits non-zero. `--delete-branch` with no worktree
   deletes an existing branch.
7. **AC7 — no scheduler notes.** `scripts/worktree-flow.py` contains neither `WF_REQUEST_DIR` nor
   `reschedule-request`; with `$WF_REQUEST_DIR` pointing at a directory holding a
   `reschedule-request-x.md`, `status`'s stdout and stderr name no note. `orchestration-track.md` contains
   no `reschedule-request`.
8. **AC8 — the gate's discovery.** With no configured paths and an `agentskills` stand-in, phase 1
   validates exactly the skills under `skills/`, `.agents/skills/` and `.pi/skills/`, and not one under
   `.claude/skills/`.
9. **AC9 — the gate's teardown.** `scripts/skill-release-gate.py` contains neither `drop_mongo_db` as a
   step nor `VIDUSHI_MONGO_URI`; `[teardown] cmd` runs with the substitutions applied; a configuration
   carrying `[teardown] drop_mongo_db`, with no engine or checks, makes the gate exit non-zero before any
   phase, naming `[teardown] cmd`.
10. **AC10 — every path.** Each §S8 case has a test, run as §S8 states, that asserts the files, refs,
    exit code and output it names.
11. **AC11 — hermetic.** Every new test passes with no network, no `agentskills` on the host, and with
    `WORKTREE_FLOW_PROJECT_DIR`, `WF_TRACK`, `WF_REQUEST_DIR` and `SKILLGATE_SOON` set in the session; no
    test runs a real `pip`, `python -m build` or `ensurepip`; no new test skips; after the full suite,
    `git status --porcelain` in this repository is unchanged by the run.
12. **AC12 — coverage.** Under the pre-merge gate's coverage run, each of `scripts/worktree-flow.py`
    and `scripts/skill-release-gate.py` measures at least 85% of its statements, and the total count of
    covered lines exceeds the `Coverage baseline:` line's figure in `AGENTS.md`.

## Non-goals

- `worktree-flow.py`'s lint (CR-MDB-053) and `finish --note`, which stays accepted.
- Declared project services and the scripts that run them (DN §D25, CR-MDB-074).
- Bringing projects scaffolded before this CR up to the new rust template (CR-MDB-082's `migrate`).
