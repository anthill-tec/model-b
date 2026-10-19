# CR-MDB-081 — worktree-flow merges, never rebases; tests for it and the skill release gate

**Status:** PENDING — spec drafted 2026-10-19 from the gap analysis; spec pre-review next.
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
  by hand (`orchestration-common.md`, `orchestration-track.md`, the `shutdown` skill's Step 2A).
- **`status` reads the newest commit.** Its phase is inferred from the newest subject in
  `develop..<branch>`, and its count of commits ahead counts every commit there; once develop is merged
  into a branch, the newest is the merge commit. A branch that is behind shows `REBASE NEEDED`.
- **`abort`'s dry run promises a board write.** It prints that it will record the CR's state on
  Crucible's queue; neither run writes to the board. `--reason` and `--superseded` only shape that line.
- **A scheduler-note board nothing uses.** `status` lists `reschedule-request-*.md` and
  `directive-*.md` notes from `$WF_REQUEST_DIR` (or that key in the project's `.env`), for a
  `request-poll.py` watcher Model B does not ship. No shipped skill, template or script names it;
  Sandesh carries track requests.
- **The skill release gate's discovery and teardown.** With no configured skill paths it looks in
  `skills/` and `.claude/skills/`; Pi's project skill roots are `.agents/skills/` and `.pi/skills/`. Its
  teardown has a Mongo-drop step reading `VIDUSHI_MONGO_URI`, one consumer project's database: a
  project's dependency service hoisted into a shared tool (§D25). Its generic `[teardown] cmd` runs a
  project's own command.

## Steps

### §S1 — `sync` merges develop in

`sync --cr <cr>` brings the feature branch level with develop by merging develop into it, in the CR's
worktree, and never rebases:
- a branch already level reports so and changes nothing;
- a worktree with uncommitted changes is refused before anything runs;
- a conflicting merge is aborted (`git merge --abort`), the branch is left as it was, the conflict is
  reported and the run exits non-zero;
- `--dry-run` prints the merge it would run and changes nothing.

### §S2 — `finish` catches up the same way

A branch that is behind develop is brought level by the same merge, inside the merge lock, before the
`--no-ff` merge into develop; with `--no-auto-sync` it is refused, naming `sync --cr <cr>`. A
conflicting catch-up is aborted, nothing is merged into develop, the lock is released and the run exits
non-zero. `finish` never rebases.

### §S3 — `status` after a merge

A branch that is behind shows that it needs a `sync` (no `REBASE` wording). The phase and the count of
commits ahead come from the branch's own commits, merge commits excluded, so a synced branch reports
the phase of its newest own commit.

### §S4 — The rules follow the tool

Every surface that forbids `sync` or merges develop in by hand names `worktree-flow.py sync --cr <cr>`
instead, as the way a CR's branch is brought level before `finish`:
- `skills-src/model-b/references/orchestration-common.md` (§ Worktree isolation (basics));
- `skills-src/model-b/references/orchestration-track.md`;
- the `shutdown` skill's Step 2A;
- `skills-src/memory-templates/rust-orchestration.md`'s `worktree-flow.py` entry (`sync`, `finish`,
  `status`);
- `scripts/worktree-flow.py`'s docstring and its `sync` and `finish` help.

The close-out's first step ("merge develop into the feature branch until behind=0") keeps its wording.

### §S5 — `abort` promises nothing it does not do

`abort`'s dry run and real run describe only what they do. Both end by naming the state (`ABORTED`, or
`SUPERSEDED` with `--superseded`) and the `--reason` as what the orchestrator records on the board with
the Crucible client. `--reason` stays required (except with `--release-lock`).

### §S6 — The scheduler-note board is removed

`status` no longer reads `$WF_REQUEST_DIR` or the project's `.env`, and lists no scheduler notes; its
envelope and human board are otherwise unchanged.

### §S7 — The skill release gate names no project

- With no configured skill paths, phase 1 discovers `skills/<name>/SKILL.md`,
  `.agents/skills/<name>/SKILL.md` and `.pi/skills/<name>/SKILL.md`; `.claude/skills/` is no longer read.
- The teardown's Mongo-drop step and its `VIDUSHI_MONGO_URI` are removed; `[teardown] cmd` stays. A
  configuration that still carries `[teardown] drop_mongo_db` fails the gate with a check naming
  `[teardown] cmd` as its replacement, so a lost teardown is never silent.

### §S8 — Tests for every path

Behaviour tests, each running the script as a subprocess, for:
- **`worktree-flow.py`:** project resolution (`--project-dir`, `$WORKTREE_FLOW_PROJECT_DIR`, the
  current directory's repository, not a repository); `start` (each refusal, the local-develop note, the
  `.env` copy, the track label from `--track` and `$WF_TRACK`, `--dry-run`); `status` (the merge lock,
  detached and dirty worktrees, the track label, the phase); `sync` (§S1); `finish` (each refusal, the
  lock held by another finish, the catch-up merge and its conflict, a worktree removal that needs
  `--force`, a partial removal, a failed branch delete, `--push` succeeding and failing, `--dry-run`);
  `abort` (each refusal, `--force`, `--delete-branch`, no worktree, `--release-lock` real and dry,
  `--dry-run`).
- **`skill-release-gate.py`:** configuration discovery (`pyproject.toml`'s `[tool.skill-release]`, the
  standalone `.skill-release.toml`, `--config` nested or top-level, none); phase 1 (discovery, an
  `agentskills` that passes and one that fails); phase 2 (the wheel built or not, the entry point, a
  forbidden entry point, glob counts and globs); phase 3 (the console installed or not, the import
  check); phase 4 (every check field: `expect`, `expect_re`, `reject`, `json_type`, `allow_nonzero`,
  `combine_stderr`, the substitutions); the teardown; the exit codes.

### §S9 — Hermetic

The CR-MDB-078 harness binds every test (§S4 of that CR): the test process's environment with only
`PATH`, git's configuration variables and a private temp directory changed; stand-ins for external
programs; real git repositories in temp directories; nothing written into this repository. No test
reaches a package index, and no test lets a real `pip` or `build` run.

## Acceptance Criteria

1. **AC1 — `sync`.** On a CR worktree behind develop, `sync --cr <cr>` exits 0 and the branch then
   contains develop's head; every commit the branch held before has the same sha afterwards; the
   branch's newest commit is a merge commit; behind is 0. A conflicting `sync` exits non-zero, leaves
   the branch head and the worktree as they were (`git status --porcelain` empty, no merge in
   progress), and names the conflict. A level branch, a dirty worktree and `--dry-run` behave as §S1
   states.
2. **AC2 — `finish`'s catch-up.** A branch behind develop is merged into develop by `finish` with every
   pre-existing branch commit keeping its sha; with `--no-auto-sync` it exits non-zero naming
   `sync --cr <cr>` and changes nothing; a conflicting catch-up exits non-zero, leaves develop's head
   unchanged and the merge lock released.
3. **AC3 — no rebase.** `scripts/worktree-flow.py` runs no `git rebase` on any path.
4. **AC4 — `status`.** For a CR branch with own commits followed by a `sync` merge, `status`'s envelope
   reports the phase of the newest own commit and a `commits_ahead` that excludes the merge commit; a
   branch that is behind has a `state` containing `sync` and none containing `REBASE`.
5. **AC5 — the rules.** None of the §S4 surfaces tells the orchestrator not to use `sync` or to merge
   develop in by hand; each names `worktree-flow.py sync --cr <cr>` as the step before `finish`; the
   docstring and the `sync`/`finish` help do not say `rebase`. `tests.test_bootstrap_shutdown_registry`'s
   check of the shutdown skill's develop merge asserts the `sync` form.
6. **AC6 — `abort`.** Neither `abort`'s dry run nor its real run says it records anything on the board
   or Crucible's queue; both name the state and the reason as the orchestrator's to record with the
   Crucible client; `abort --cr <cr>` without `--reason` still exits non-zero.
7. **AC7 — no scheduler notes.** `scripts/worktree-flow.py` contains neither `WF_REQUEST_DIR` nor
   `reschedule-request`; with `$WF_REQUEST_DIR` pointing at a directory holding a
   `reschedule-request-x.md`, `status`'s stdout and stderr name no note.
8. **AC8 — the gate's discovery.** With no configured paths and an `agentskills` stand-in, phase 1
   validates exactly the skills under `skills/`, `.agents/skills/` and `.pi/skills/`, and not one under
   `.claude/skills/`.
9. **AC9 — the gate's teardown.** `scripts/skill-release-gate.py` contains neither `drop_mongo_db` nor
   `VIDUSHI_MONGO_URI`; `[teardown] cmd` runs with the substitutions applied; a configuration carrying
   `[teardown] drop_mongo_db` makes the gate exit non-zero with a failed check naming `[teardown] cmd`.
10. **AC10 — every path.** Each §S8 case has a test that runs the script as a subprocess, or drives the
    gate's `Gate` through its venv seam where the case needs a built wheel, and asserts the files,
    refs, exit code and output it names.
11. **AC11 — hermetic.** Every new test passes with no network and no `agentskills` on the host; no test
    runs a real `pip install` or `python -m build`; no new test skips; after the full suite,
    `git status --porcelain` in this repository is unchanged by the run.
12. **AC12 — coverage.** Under the pre-merge gate's coverage run, each of `scripts/worktree-flow.py`
    and `scripts/skill-release-gate.py` measures at least 85% of its statements, and the total count of
    covered lines exceeds the `Coverage baseline:` line's figure in `AGENTS.md`.

## Non-goals

- `worktree-flow.py`'s lint (CR-MDB-053) and `finish --note`, which stays accepted.
- Declared project services and the tool that runs them (DN §D25, CR-MDB-074).
- The consumer project's `.skill-release.toml` (it is that project's to change).
