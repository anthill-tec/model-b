# CR-MDB-081 — worktree-flow merges, never rebases; tests for it and the skill release gate

**Status:** PENDING — **SEED, not the finished spec** (filed 2026-10-19 into release 1.0.0, wave 2,
split from CR-MDB-078). Gap analysis, the spec and its pre-review happen in order when this CR starts.
**Type:** feature + tests (the deployed `worktree-flow.py` and `skill-release-gate.py`)
**Priority:** P1 — release 1.0.0, wave 2; after CR-MDB-078.
**Depends on:** CR-MDB-078 (its shared git-repository helper). The board is authoritative: read
`queue`, not this line.
**Labels:** tests, coverage, scripts, worktree
**Design reference:** PRD D5 (coverage of every script); `contracts/worktree-layout.md`;
`skills-src/model-b/references/orchestration-common.md` § Worktree isolation (basics).

## Context

Measured 2026-10-19 on develop, by the whole suite under the `[tool.coverage]` config:
`scripts/worktree-flow.py` 333/537 statements, `scripts/skill-release-gate.py` 10/212.

`worktree-flow.py sync` brings a CR's branch up to date by rebasing it onto develop, and `finish`
does the same when the branch is behind. A rebase rewrites the commits the board and VERIFY have
recorded, so the orchestration rules forbid `sync` and tell the orchestrator to merge develop in by
hand until the branch is level. `abort`'s dry run says it will record the CR's state on Crucible's
queue; the real run records nothing there.

`skill-release-gate.py` has one consumer, outside this repo: a skill-bundle project that runs it
before `git flow release finish`. Its skill discovery looks in `skills/` and `.claude/skills/`, while
Pi's skill roots are `.pi/skills/` and `.agents/skills/`.

## Scope (seed)

1. **`sync` merges.** `sync --cr <cr>` merges develop into the feature branch in its worktree and
   never rebases; a conflicting merge is aborted and reported, leaving the branch unchanged, as the
   rebase is today. `finish` brings a branch that is behind up to date the same way, or with
   `--no-auto-sync` refuses. The verb and its flags stay.
2. **The rule follows the tool.** The orchestration references, the rust memory template and the
   script's docstring tell the orchestrator to run `sync` before `finish` instead of forbidding it.
3. **`abort`'s dry run promises nothing it does not do.** `--reason` and `--superseded` stay.
4. **`worktree-flow.py` tests** for every path the suite leaves unexercised: `start`'s refusals and
   its track label; `status` with a held, live or stale lock; `sync`; every `finish` refusal, its
   catch-up merge and conflict, a partial worktree removal, a failed branch delete, and `--push`
   succeeding and failing; every `abort` path, `--release-lock` included.
5. **`skill-release-gate.py`:** skill discovery in `skills/`, `.agents/skills/` and `.pi/skills/`,
   with `.claude/skills/` dropped; tests for config discovery (`pyproject.toml`, the standalone file,
   `--config` nested or top-level, none), every phase's verdicts, the teardown command, and the exit
   codes. No test reaches a package index.
6. **The coverage baseline** rises with the result.

## To measure at gap analysis

- The scheduler-note board in `status` (`$WF_REQUEST_DIR`, `reschedule-request-*.md`,
  `directive-*.md`): no shipped skill, template or script names it, and the one project that sets the
  variable keeps an empty directory. Delete it, or test it: the user's call.
- Every surface that describes `sync` or the merge-before-finish rule, and the tests that pin them.
- How the skill release gate's build, install and check phases are exercised with no network.
- The re-score: about 5 points.
