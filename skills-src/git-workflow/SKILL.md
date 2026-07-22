---
name: git-workflow
description: Git branch discipline, commit conventions, versioning strategy, the 10-step git flow release, multi-account push switching, and worktree rules — universal for all projects and stacks.
---

# Git Workflow — Branch, Commit & Release Discipline

Single home for git conventions (absorbed the former `memory` twins for git workflow and the git side of multi-account switching).

## Branch Rules

- **NEVER commit directly to `develop`, `main`, or `master`** — always use a feature branch
- Feature branches: `feature/cr-cf-XXX` (created before you start); `git flow feature start <name>` creates from develop, `git flow feature finish` merges back
- Dispatched agents: the branch is already created for you — just work on it
- Hotfixes: `git flow hotfix start X.Y.Z` (from master) → `git flow hotfix finish X.Y.Z` (merges to master AND develop, tags master)

### Branch protection

- **master/main (production):** no direct commits; only receives merges via `git flow release finish`; the ONLY branch to build/install release artifacts from; always tagged
- **develop:** active development; feature branches merge here; never build release artifacts from here; documentation updates land here
- **release/X.Y.Z:** temporary; version bumps and final testing happen here; deleted by `git flow release finish`

## Commit Conventions

| Prefix | When |
|--------|------|
| `test:` | Adding or fixing tests (RED state) |
| `feat:` | New feature or implementation (GREEN state) |
| `fix:` | Bug fix |
| `refactor:` | Code restructuring (no behavior change) |
| `docs:` | Documentation only |
| `chore:`/`build:` | Version bumps, config, tooling |

### Commit Message Format
```
<prefix>: CR-CF-XXX <short description>
```

Example:
```
feat: CR-CF-050 step 2 — AgentStreamResource with SSE filtering
test: CR-CF-050 step 2 — AgentStreamResource tests (RED)
fix: CR-CF-049 deduplicate imports + add @NotNull validation
```

- Keep messages clean and professional; focus on technical change and business value; descriptive but concise.

### CRITICAL RULE — NO AI attribution (NON-NEGOTIABLE)

**NEVER add Claude/AI attribution tags to commit messages:**
- No "🤖 Generated with Claude"
- No "Co-Authored-By: Claude"
- No AI attribution of any kind

## Commit Timing

- **One commit per step** — don't split a step across multiple commits
- **Commit after GREEN — never commit RED state** (unless it's a test-only commit in a TDD test-write step): no failing tests, no compilation errors, nothing that breaks the build
- TDD discipline before every commit: RED → GREEN → clean up (remove unused imports) → run tests AGAIN (still GREEN) → commit
- **Always `git add -A`** before commit — don't leave unstaged changes
- Dispatched sub-agents: the Model B sub-agent procedure (`~/.claude/skills/model-b/references/sub-agent-procedure.md`) §TDD is authoritative — a compile failure IS a RED state (ingest it); do NOT run the full suite (that's the orchestrator's pre-merge gate)

## Working Directory

- Always verify you're on the correct branch: `git branch --show-current`
- Always verify clean state before starting: `git status --short`
- If you see uncommitted changes that aren't yours, STOP and report

## Worktrees

If you're given a worktree path, work ONLY in that directory. Never switch branches in a worktree — it was created for a specific branch.

## Versioning Strategy (CRITICAL)

Semantic versioning **MAJOR.MINOR.PATCH** — and **NO `v` prefix** for our versions/tags:

- Correct: `1.0.0`, `1.0.0-rc1`, `2.1.3-SNAPSHOT` · Wrong: `v1.0.0` (a `v` prefix is only ever for external tools that require it)
- **Maven/Quarkus projects:** `-SNAPSHOT` suffix for dev versions — `1.1.0-SNAPSHOT` → `1.1.0` → `1.2.0-SNAPSHOT`
- **Helm charts / GitOps:** `-rc` suffix for release candidates — `0.1.0-rc1` → `0.1.0-rc2` → `0.1.0` → `0.2.0-rc1`; never `-SNAPSHOT` here
- Tags: `git tag 1.0.0` (created automatically by `git flow release finish` — never tag by hand)

## Releases (NON-NEGOTIABLE)

**ALL releases MUST use `git flow release` commands.** Never manually tag, never bump version directly on develop/main. **Ask before releasing** — version bumps and releases require human approval.

### The 10-step git flow release (Java Maven projects)

```bash
# 1. Start release branch (creates release/X.X.X from develop)
git flow release start X.X.X

# 2. Update version in pom.xml, commit to the release branch
git add pom.xml && git commit -m "chore: bump version to X.X.X"

# 3. TDD RED — write failing test first, commit
# 4. TDD GREEN — implement, tests pass, remove unused imports, tests AGAIN, commit

# 5. Finish release (merges to master, tags X.X.X, back-merges to develop, deletes branch)
git flow release finish X.X.X

# 6. Build from master (CRITICAL — releases build ONLY from master)
git checkout master && ./mvnw clean install

# 7. Push everything
git push origin master develop --tags

# 8. Update Migration.md on develop ("Version X.X.X Status: ✅ Complete"), commit
# 9. Update Implementation.md (phase details, integration guides), commit
# 10. Push documentation
git push origin develop
```

### ALL release changes go on the release branch BEFORE finishing

```bash
# WRONG sequence (violates git flow):
git flow release finish X.X.X
git checkout master
# edit anything here ← master only ever receives merges!
```

**Library projects (INBOX/OUTBOX pattern):** publish the release branch (`git flow release publish X.X.X`) so CI runs; docs (Migration.md/Implementation.md) FIRST, code changes LAST (CI has `paths-ignore` for docs — the last commit must be code/config to trigger CI); after CI's badge-update commit lands on the release branch, `git pull --rebase origin release/X.X.X` BEFORE `git flow release finish` or the badge update is lost.

**Mainline microservices:** CI auto-updates README badges; same rule — docs before code, last commit must be code/config so CI runs on master after the merge.

### Maven install/deploy — master only

```bash
git checkout master && ./mvnw clean install   # ✅ the only correct branch
# NEVER ./mvnw clean install from develop or release/* — artifact version must match the git tag
```

After building: switch back to develop for continued work. Bump develop to the next `-SNAPSHOT` after a release, and update consumer `pom.xml`s that depend on the released library.

## Multi-Account Pushing (dual remote: origin + mirror)

Some repos carry two remotes on two GitHub accounts: `origin` (work account, e.g. `Antojk71`, host alias `github.com-4property`) and `mirror` (personal account, e.g. `antojk`, host alias `github.com-antojk`). SSH host aliases in `~/.ssh/config` select the key; the **gh CLI account must be switched around each push**.

**If a `mirror` remote is detected (`git remote | grep -q '^mirror$'`), ALWAYS push to BOTH remotes, switching accounts around each push:**

```bash
gh auth switch --user antojk       # personal account
git push mirror <branch>           # (and: git push mirror --tags)
gh auth switch --user Antojk71     # work account
git push origin <branch>           # (and: git push origin --tags)
```

- Single-remote repos: ensure the correct account is active (`gh auth status`), then `git push origin <branch>`
- Releases: push tags to BOTH remotes with the same account-switch dance
- Troubleshooting a wrong-account push: `gh auth switch --user <correct-account>`, and verify the remote URL uses the right host alias (`git remote get-url origin|mirror`)
- The chezmoi dotfiles source repo uses the personal account — its push discipline lives in the `chezmoi` skill

## What NOT To Do

- **NEVER** run `git checkout develop` or `git checkout main` as a dispatched agent
- **NEVER** run `git merge` — that's done by the orchestrator after review
- **NEVER** run `git flow feature finish` as a dispatched agent — that's done by the orchestrator
- **NEVER** force push
- **NEVER** rebase without being told to
- **NEVER** tag or release without `git flow release` commands
- **NEVER** bump versions directly on develop or main
- **NEVER** commit to master directly — only merges via `git flow release finish`
- **NEVER** add AI attribution to a commit message
