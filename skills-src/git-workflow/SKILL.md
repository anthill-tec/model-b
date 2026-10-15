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
- Hotfixes: `git flow hotfix start X.Y.Z` (from master) → `git flow hotfix finish X.Y.Z` (merges to master AND develop, tags master). A hotfix starts from main's state; if the fix needs develop-only commits, cut a release branch off develop instead — and abandon a mis-cut hotfix branch with `git branch -D`, never `git flow hotfix finish`.

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
- **Stage what you changed, by path** (`git add <path> …`) — never `git add -A`; another agent's or the user's work may share the tree. Don't leave your own changes unstaged
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
- **The release's verification runs are filed under the release.** The `regression` and the
  `pre-merge-gate` run on the release branch are filed with `--release <label>` — the release
  the roadmap declares — as release verification instead of a cycle's runs, and never beside
  `--cycle`.

**Read release readiness with `modelb-axi release-check`**: run it from the project root before
`git flow release start`, and fix what it reports missing. It reads the rendered workflow, the
version sources and, through `gh`, the repository's environments and secrets; it writes nothing.
An `unknown` item names what to check by hand.

**ALL releases MUST use `git flow release` commands.** Never manually tag, never bump version directly on develop/main. **Ask before releasing** — version bumps and releases require human approval.

**Two documentation steps belong to every release** (on the release branch, before finishing):

1. **Release notes link to the install guide** when the project keeps one; they never repeat
   install text. The guide's marked regions feed generated surfaces only, such as a package
   README — never rewrite install text by hand.
2. **A documentation review** over the doc set: the install guide, the README and any other
   user-facing docs are read against the code being released, and every inaccuracy is fixed
   before the tag.

**Publishing the branch.** After `git flow release start X.Y.Z` (or `git flow hotfix start
X.Y.Z`), commit the version bump in every version source and the release's `CHANGELOG.md`
section, then publish the branch (`git flow release publish X.Y.Z`, or `git flow hotfix publish
X.Y.Z` for a hotfix). Every push of the branch is the rehearsal; `finish` deletes the remote
branch.

**Pushing the release.** After `git flow release finish X.Y.Z`, push `master`, `develop` and the
tags in one `git push origin master develop --tags`: the `master` push runs the tests and creates
the release, and the release event publishes. If the `master` run reports no version tag at
`HEAD`, dispatch the workflow on `master`. When the `master` run or the release run fails its
tests, nothing publishes: re-run the failed jobs, and fix a real failure on a hotfix branch.

**The release workflow is rendered, never hand-written.**

- `modelb-axi init` renders the release workflow from the project's stacks and its
  `RELEASE_TARGETS`.
- `modelb-axi release-workflow` re-renders it whenever the stacks or the targets change.

What each release target adds to the rendered workflow:

| Target | Rehearsal | Publish | Environment / secret |
|---|---|---|---|
| `pypi` | the upload of the stamped dev version to the test index | PyPI through Trusted Publishing | the environments `pypi` and `testpypi`; no secret |
| `npm` | the package manager's dry-run publish with a dist-tag | npm, with provenance | the environment `npm` and the repository secret `NPM_TOKEN` |
| `crates` | the dry-run publish of the crate | crates.io through Trusted Publishing | the environment `crates` and the repository secret `CARGO_REGISTRY_TOKEN` |
| `maven-central` | the signed Central bundle, uploading nothing | Maven Central through the Central Portal | the environment `maven-central` and the repository secrets `MAVEN_CENTRAL_USERNAME`, `MAVEN_CENTRAL_PASSWORD`, `MAVEN_GPG_PRIVATE_KEY` and `MAVEN_GPG_PASSPHRASE` |
| `github-assets` | the project's `build-assets` script, its `dist-assets/` output checked non-empty | an upload of `dist-assets/` to the release | no environment, no secret |

### Release notes (`CHANGELOG.md`)

The release notes are the release's `CHANGELOG.md` section. On the release branch, before the
branch is first published:

1. Write the release's section: move `[Unreleased]` under `## [X.Y.Z] - YYYY-MM-DD`.
2. Or, when `[Unreleased]` was not kept, write it from the release's CRs, read with the Crucible
   client's `history` and `landings` verbs.
3. Add an `### Upgrading` note first in the section whenever an operator must act.
4. Update the compare links at the foot of the file.
5. Commit the `CHANGELOG.md` section on the release branch.

The rendered workflow's `create-release` job publishes the tag's section as the release body:

- `create-release` runs on the `master` push and needs the test jobs, so the release is only
  created after the tests pass.
- It checks out with full history and takes the `X.Y.Z` tag at `HEAD`; when there is none it
  exits cleanly with nothing to release.
- When there is more than one version tag at `HEAD`, it fails, naming them.
- It matches the section's heading literally, so `1.0.1` never matches `1.0.10`.
- It fails on a missing section.
- It fails on an empty section (one holding only `###` headings counts as empty).
- It passes the section to the release as `--notes-file`, never generated notes.

`GH_TOKEN` is a personal access token kept as a repository secret, never the default
`github.token`: a release made with the default token triggers no `on: release` publish job, so
a project publishing on `on: release` would never publish. A release that already exists is left
as it is, so a re-run of the job does not fail.

The packaging entries, per stack:

| Stack | Packaging entry |
|---|---|
| `python` | `[project.urls]` carries `Changelog` (the `CHANGELOG.md` file) and `Release Notes` (the releases page) |
| `bun` | `CHANGELOG.md` in `package.json` `files`; copied into the package directory at publish time when the package is not at the repository root |
| `arduino` | the release body only |
| `quarkus` | the release body only |
| `java` | the release body only |
| `rust` | the release body only |

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

# 6. Build from master (CRITICAL — a local install builds ONLY from master)
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
git checkout master && ./mvnw clean install   # ✅ a local install, from master only
# NEVER ./mvnw clean install locally from develop or release/* — artifact version must match the git tag
```

A project with the `maven-central` target is published by the release event's publish job, never
from a local machine. The rehearsal's `deploy` uploads nothing: it runs on `release/*` in CI, not
as a local install.

After building: switch back to develop for continued work. Bump develop to the next `-SNAPSHOT` after a release, and update consumer `pom.xml`s that depend on the released library.

### Python package releases (PyPI)

1. **Build** — on the release branch, set the version in its single source (the one place the
   package reads it from), commit, then build the sdist and wheel with `uv build`.
2. **Rehearse on TestPyPI** — each release-branch push (and each hotfix-branch push) uploads the
   stamped dev version to TestPyPI through Trusted Publishing, before anything reaches the real
   index.
3. **Publish to PyPI** — after `git flow release finish`, the release event's publish job builds
   from the tagged commit and uploads to PyPI after the tests and the ref guard, through Trusted
   Publishing, with no token anywhere.
4. **Post-release maintenance** — on the maintainer's machine: install the released version from
   PyPI; replace the prior installation with
   `--reinstall --target-root ~ --harnesses <harnesses> --stacks <stacks>`; remove workflow
   entries from any global permission config in favour of per-project policies; and confirm a
   dispatched agent in a trusted project runs without a permission prompt.

### Pi package releases (npm)

1. **Publish** — after the version is set, the release event's publish job publishes the Pi
   package with `npm publish` (a scoped package with `npm publish --access public`) after the tests and
   the ref guard, through Trusted Publishing. The first publish of a new package uses a one-time granular token kept as a
   repository secret; then the trusted publisher is added, 2FA is required and the token
   deleted.
2. **Verify the published version** — install the published version with `pi install` into an
   isolated Pi agent directory (`PI_CODING_AGENT_DIR` pointed at a temp dir) and confirm the
   extension loads there.
3. **Post-release live check** — as part of the post-release maintenance, once the published
   package is installed into the maintainer's real Pi configuration, confirm Pi loads the
   worktree extension there.

### Rehearsal and CI

Each push to `release/X.Y.Z` or `hotfix/X.Y.Z` builds `X.Y.Z`, refuses a committed version other
than `X.Y.Z`, and fails when the release's notes section is missing or empty. `pypi` and `npm`
stamp a dev marker and the CI run number in each target's own form; `crates` and `maven-central`
upload nothing and keep `X.Y.Z`.

| Target | Version | Rehearsal |
|---|---|---|
| `pypi` | `X.Y.Z.devN` | the upload to the test index |
| `npm` | `X.Y.Z-dev.N` | the package manager's dry-run publish with a dist-tag |
| `crates` | `X.Y.Z` | the crate's dry-run publish |
| `maven-central` | `X.Y.Z` | the signed Central bundle, which uploads nothing |
| `github-assets` | — | the project's `build-assets` script, its `dist-assets/` output checked not empty |
| no target | — | the notes check only |

The release workflow's test jobs run the suite in every run: each push to a release or hotfix
branch, each push to `master`, each published release. They run on the stack's floor
interpreter, on a fresh runner, with full history. They run outside any agent session, the one
place the suite runs without the stack's Crucible client. Every publish job (the rehearsal
included) needs the test jobs, because a dependency gates only within one run. No CI on
`develop` or pull requests.

## Multi-Account Pushing (dual remote: origin + mirror)

Some repos carry two remotes on two GitHub accounts: `origin` (work account, e.g. `<work-account>`, host alias `github.com-<work-alias>`) and `mirror` (personal account, e.g. `<personal-account>`, host alias `github.com-<personal-alias>`). SSH host aliases in `~/.ssh/config` select the key; the **gh CLI account must be switched around each push**.

**If a `mirror` remote is detected (`git remote | grep -q '^mirror$'`), ALWAYS push to BOTH remotes, switching accounts around each push:**

```bash
gh auth switch --user <personal-account>   # personal account
git push mirror <branch>                   # (and: git push mirror --tags)
gh auth switch --user <work-account>       # work account
git push origin <branch>                   # (and: git push origin --tags)
```

- Single-remote repos: ensure the correct account is active (`gh auth status`), then `git push origin <branch>`
- Releases: push tags to BOTH remotes with the same account-switch dance
- Troubleshooting a wrong-account push: `gh auth switch --user <correct-account>`, and verify the remote URL uses the right host alias (`git remote get-url origin|mirror`)

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
