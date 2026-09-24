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
- Dispatched sub-agents: the Model B sub-agent procedure (`~/.agents/skills/model-b/references/sub-agent-procedure.md`) §TDD is authoritative — a compile failure IS a RED state (ingest it); do NOT run the full suite (that's the orchestrator's pre-merge gate)

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

**A release is a BOUNDARY EVENT, not a work item.** It is not a CR, it is never gated by one,
and it never starts automatically. The trigger is two things together: the wave carrying the
release has **drained its queue**, and a **human has approved starting the release**. A queue
that empties is a signal, not a decision.

- **CRs are not release gates.** A CR describes work; a release describes a boundary. Expressing
  "the wave must finish" as dependency edges on a release CR duplicates what the draining queue
  already says, and it hands a decision that is the human's to a row on a board.
- **Running a CR during a release is possible and HIGHLY DISCOURAGED.** The release branch exists
  to be verified and tagged; putting unreviewed work on it defeats that. Every dependency lands
  before the release starts. Taking the exception needs explicit approval and a recorded reason.
- **The record comes after the fact**, never before: the release is proposed (a label and a
  target), approved by a human, executed, and only then recorded — a milestone is a record, not
  an event.

**ALL releases MUST use `git flow release` commands.** Never manually tag, never bump version directly on develop/main. **Ask before releasing** — version bumps and releases require human approval.

**Two documentation steps belong to every release** (on the release branch, before finishing):

1. **Install text from its single source.** If the project keeps an install guide with marked
   regions, copy those marked regions verbatim into the release notes (and into any other
   surface that takes them, such as a package README) — never rewrite install text by hand.
2. **A documentation review** over the doc set: the install guide, the README and any other
   user-facing docs are read against the code being released, and every inaccuracy is fixed
   before the tag.

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

### Python package releases (PyPI)

1. **Build** — on the release branch, set the version in its single source (the one place the
   package reads it from), commit, then build the sdist and wheel with `uv build`.
2. **Rehearse on TestPyPI** — upload the release candidate to TestPyPI and install it into an
   isolated tool directory (`UV_TOOL_DIR` / `UV_TOOL_BIN_DIR` pointed at a scratch path) from
   TestPyPI, with PyPI kept only for dependencies:
   `--index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/`; then
   run it there before anything reaches the real index.
3. **Upload to PyPI** — only after `git flow release finish`, build from the tagged commit and
   upload with a token the user supplies at upload time; never store the token in the repository
   or in agent-readable config.
4. **Post-release maintenance** — on the maintainer's machine: install the released version from
   PyPI; replace the prior installation with
   `--reinstall --target-root ~ --harnesses <harnesses> --stacks <stacks>`; remove workflow
   entries from any global permission config in favour of per-project policies; and confirm a
   dispatched agent in a trusted project runs without a permission prompt.

### Pi package releases (npm)

1. **Publish** — after the version is set, publish the Pi package with `npm publish` (a scoped
   package with `npm publish --access public`), using credentials the user supplies at publish
   time; never store them in the repository or in agent-readable config.
2. **Verify the published version** — install the published version with `pi install` into an
   isolated Pi agent directory (`PI_CODING_AGENT_DIR` pointed at a temp dir) and confirm the
   extension loads there.
3. **Post-release live check** — as part of the post-release maintenance, once the published
   package is installed into the maintainer's real Pi configuration, start the watcher there and
   confirm a Sandesh message wakes the session.

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
