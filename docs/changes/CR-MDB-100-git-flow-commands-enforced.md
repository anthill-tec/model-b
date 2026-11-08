# CR-MDB-100 — Flow branches are made, merged and tagged only by the git flow commands, and a hook enforces it

**Status:** PENDING — **SEED, not the finished spec** (filed 2026-11-08 by the user's rulings, PRD D6 amendment
of 2026-11-08). Gap analysis, the spec and its pre-review happen in order when this CR starts. Pre-review: due
— it adds a hook.
**Type:** feature (skills, a blocking hook)
**Priority:** P1 — release 1.0.0, wave 2 (user 2026-11-08; board-authoritative: read `queue`).
**Depends on:** none (board-authoritative: read `queue`, not this line)
**Labels:** skills, hooks, git-flow, solo
**Design reference:** PRD D6 amendment of 2026-11-08; `hooks-src/schema.md` (security-class hooks declare
`fail_direction`); the `block-direct-*-test` hooks (CR-MDB-062, CR-MDB-066) as the pattern.

## Context

The user reports that projects keep failing to use the git flow commands in solo mode. Model B's text leaves
the gap open:

- `orchestration-common.md`'s only general rule is one line under Workflow gates: "Always use the proper
  git-flow / worktree commands; never hand-roll the merge dance."
- `git-workflow`'s Branch Rules say `git flow feature start <name>` creates a feature branch, but forbid no raw
  form (`git checkout -b feature/…`, `git merge` into develop, `git tag`).
- `orchestration-common.md` § Worktree isolation is written unconditionally ("Enter the worktree right after
  `start`"), although its MODE-MAP says a Solo orchestrator has no worktrees; and it says a main-tree feature
  branch "merges develop in by hand".
- `git-workflow` tells a mis-cut hotfix branch to be abandoned "with `git branch -D`".
- `git-workflow` says "NEVER commit directly to `develop`", while `orchestration-common.md` commits standalone
  docs to develop and the chore rule (PRD D6, 2026-11-08) commits chores there.

Nothing enforces the rule: the hook roster blocks raw test runners and writes outside a worktree, nothing
for git.

## Scope (seed)

1. **Worktrees are multi-track only** (user 2026-11-08). § Worktree isolation, the Track reference and the
   bootstrap and shutdown skills say so where they name `worktree-flow` or `modelb_worktree_enter`; a Solo
   orchestrator works in the main tree on the branch git flow creates.
2. **git flow is initialised before it is used** (user 2026-11-08). The skill tells the orchestrator to
   check first (`git config --get gitflow.branch.develop`) and, when it is unset, to run `git flow init`
   before any flow command or flow branch, naming the project's production branch (`main` or `master`, as
   the repository has it) and `develop`; `-d` takes git flow's defaults only when they match.
2a. **One command per moment,** in `git-workflow` and pointed to from `orchestration-common.md`: start
   (`git flow feature start <CR-id>-<slug>`), level with develop (merge develop into the feature branch,
   never a rebase), finish (`git flow feature finish`), abandon (`git flow feature delete`), release and
   hotfix (`git flow release|hotfix start|finish`, `delete` to abandon). In a multi-track project the Track's
   CR uses `worktree-flow`'s verbs instead.
3. **The forbidden raw forms,** named: creating a flow branch with `git checkout -b`/`git switch -c`/`git
   branch`; `git merge` while on develop or the production branch; `git tag`; deleting a flow branch with
   `git branch -d|-D`.
4. **A `block-raw-git-flow` hook** (shell class, security class, its `fail_direction` declared), compiled
   into every Model B project: in a repository where git flow is initialised (`gitflow.branch.develop` set),
   a shell command doing a forbidden form is blocked, naming the git flow command to use. Missing git or no
   repository: allow. git flow not initialised: the gap analysis decides between allowing and blocking a
   flow-shaped raw form with the message "run `git flow init` first" (item 2).
5. **The texts reconciled:** "NEVER commit directly to `develop`" gains its exceptions (chores, standalone
   docs); `git branch -D` for a mis-cut hotfix becomes `git flow hotfix delete`; "merges develop in by
   hand" names the merge.
6. **Model B's own repository** follows it: solo, main tree, git flow commands.

## To measure at gap analysis

- The branch prefixes and production branch a project configures (`gitflow.prefix.*`,
  `gitflow.branch.master`), which the hook reads rather than assumes.
- How the hook parses a compound shell command (`&&`, `;`, `cd … &&`), and `git -C <dir>` forms.
- Commands that run git flow's work through another tool (`worktree-flow.py`, the release workflow on the
  CI runner) and stay allowed.
- `then_run` (CR-MDB-098 item 7): the hook applies to it once the shim checks it as a shell call.
- Whether a project without git flow installed needs a requirement row (`git flow` on `PATH`), and whether
  `modelb-axi init` runs `git flow init` itself for a new project (it runs `git init` today), so item 2's
  check is met from the start.
- Every surface that states a git rule (Dimension 8): the skills, the agent templates (dispatched agents
  never merge), the scaffolded `AGENTS.md`, and the tests that pin them.
- The re-score (5 points filed).
