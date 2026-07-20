# Git Workflow and Release Management

## Git Commit Guidelines (NON-NEGOTIABLE)

### CRITICAL RULE - NO Claude Attribution
**NEVER add Claude tags to commit messages:**
- ❌ "🤖 Generated with Claude"
- ❌ "Co-Authored-By: Claude"
- ❌ Any AI attribution

User has repeatedly emphasized this rule - it is **non-negotiable**.

### Commit Message Best Practices
- Keep messages clean and professional
- Focus on technical changes and business value
- Use conventional commit format when appropriate
- Be descriptive but concise

### Never Commit RED State
**ALWAYS achieve GREEN (passing tests) before committing**

**TDD Discipline:**
1. Write test (RED)
2. Implement code (GREEN)
3. Clean up (remove unused imports)
4. Run tests AGAIN (verify still GREEN)
5. Commit

(Dispatched sub-agents: the Model B sub-agent procedure (`~/.claude/skills/model-b/references/sub-agent-procedure.md`) §TDD is authoritative — a compile failure IS a RED state (ingest it); do NOT run the full suite, that's the orchestrator's pre-merge gate.)

**Never commit:**
- Failing tests
- Compilation errors
- Code that breaks the build

## Versioning Strategy (CRITICAL)

### Semantic Versioning Format
**MAJOR.MINOR.PATCH** (e.g., `1.2.3`)

**NO 'v' PREFIX** for our versions/tags:
- ✅ Correct: `1.0.0`, `1.0.0-rc1`, `2.1.3-SNAPSHOT`
- ❌ Wrong: `v1.0.0`, `v1.0.0-rc1`, `v2.1.3-SNAPSHOT`

**'v' prefix ONLY for external dependencies** if required by the external tool.

### Pre-Release Suffixes

**Quarkus Projects (Maven):**
- Use `-SNAPSHOT` suffix for development versions
- Example: `1.1.0-SNAPSHOT` → `1.1.0` → `1.2.0-SNAPSHOT`
- Maven convention for unpublished development versions

**All Other Projects (Helm Charts, GitOps):**
- Use `-rc` suffix for release candidates (testing releases)
- Example: `0.1.0-rc1` → `0.1.0-rc2` → `0.1.0` → `0.2.0-rc1`
- Never use `-SNAPSHOT` for Helm charts or GitOps versions

### Examples

**StateStore (Quarkus Microservice):**
```
1.0.0-SNAPSHOT → 1.0.0 → 1.1.0-SNAPSHOT → 1.1.0 → 2.0.0-SNAPSHOT
```

**common-app-quarkus (Helm Library Chart):**
```
0.1.0-rc1 → 0.1.0-rc2 → 0.1.0 → 0.2.0-rc1 → 0.2.0
```

**GitOps versions.yaml (GitOps Version Keys):**
```yaml
1.0.0-rc1:  # Release candidate for testing
  charts:
    common-app-quarkus: "0.1.0-rc1"

1.0.0:  # Stable release
  charts:
    common-app-quarkus: "0.1.0"
```
**Git Tags:**
```bash
# Correct (no 'v' prefix)
git tag 1.0.0
git tag 1.0.0-rc1
git tag 2.1.3-SNAPSHOT

# Wrong (has 'v' prefix)
git tag v1.0.0  # ❌ DO NOT USE
```

## Git Flow Release Pattern (Java Maven Projects)

### 10-Step Perfect Release Workflow

**Applies to:** All Java Maven projects using git flow (libraries, microservices, applications)

#### Step-by-Step Process

**1. Start Release Branch**
```bash
git flow release start X.X.X
# Creates release/X.X.X from develop
```

**2. Update Version**
```bash
# Update pom.xml version to X.X.X
# Commit to release branch
git add pom.xml
git commit -m "Bump version to X.X.X"
```

**3. TDD RED: Write Test First**
```bash
# Write failing test
# Verify compilation error or test failure
git add .
git commit -m "Add test for feature Y"
```

**4. TDD GREEN: Implement Code**
```bash
# Implement feature
# Run tests - verify they pass
# Remove ALL unused imports
# Run tests AGAIN - verify still pass
git add .
git commit -m "Implement feature Y"
```

**5. Finish Release**
```bash
git flow release finish X.X.X
# This does:
# - Merges release/X.X.X into master
# - Tags master with X.X.X
# - Merges master back into develop
# - Deletes release/X.X.X branch
```

**6. Build from Master (CRITICAL)**
```bash
git checkout master
./mvnw clean install
# Build JAR and install to local Maven repository
# ONLY build from master branch for releases!
```

**7. Push Everything**
```bash
git push origin master develop --tags
# Push both branches and all tags
```

**8. Update Migration.md**
```bash
git checkout develop
# Edit Migration.md
# Add simple status: "Version X.X.X Status: ✅ Complete"
git add Migration.md
git commit -m "Update Migration.md for version X.X.X"
```

**9. Update Implementation.md**
```bash
# Edit Implementation.md
# Add Phase N detailed completion tracking
# Add integration guides
# Add code examples
git add Implementation.md
git commit -m "Update Implementation.md with Phase N details"
```

**10. Push Documentation**
```bash
git push origin develop
```

### Critical Rules

**Branch Management:**
- ❌ NEVER commit to master directly (only via `git flow release finish`)
- ❌ NEVER build/install from release or develop branch (master ONLY)
- ❌ NEVER make changes after `git flow release finish` - ALL changes go on release branch BEFORE finishing
- ✅ ALWAYS push tags after release
- ✅ ALWAYS follow TDD (RED → GREEN → commit)
- ✅ ALWAYS remove unused imports before final commit

**CRITICAL: ALL Release Changes Go on Release Branch BEFORE Finishing**

ALL changes (code, docs, README) are PART OF THE RELEASE - commit them BEFORE `git flow release finish`:

**For Quarkus Library Projects (with INBOX/OUTBOX pattern):**
```bash
git flow release start X.X.X
# 1. Publish release branch to remote (required for CI)
git flow release publish X.X.X
# 2. Update pom.xml version (remove -SNAPSHOT for production release)
# 3. Update Migration.md (CReq status → ✅ Complete)  # Docs FIRST
# 4. Update Implementation.md (CRes details)          # Docs FIRST
# 5. Commit docs changes
# 6. Make code changes (TDD) - LAST COMMIT must be code/config, not docs
# 7. Commit code changes
# 8. Push release branch to remote (triggers CI, updates badge)
git push origin release/X.X.X
# 9. Wait for CI to complete (badge update commits to release branch)
# 10. Pull CI's badge update before finishing release
git pull --rebase origin release/X.X.X
# 11. NOW finish release (includes CI's badge updates)
git flow release finish X.X.X
```

**CRITICAL: Pull CI Badge Updates Before Finishing Release**
- Publish release branch first (`git flow release publish`)
- CI runs on release branch when version is NOT SNAPSHOT (production version)
- CI commits badge updates to the release branch
- You MUST `git pull --rebase` before `git flow release finish`
- Otherwise badge updates are lost (not merged to master)

**For Mainline Quarkus Projects (microservices, applications):**
- CI automatically updates README (badges, etc.)
- CI jobs SKIP if last commit is docs-only (paths-ignore)
- Docs changes should come BEFORE code/config changes
- **Last commit must be code/config to ensure CI runs on master after merge**

```bash
git flow release start X.X.X
# 1. Update pom.xml version
# 2. Make any manual doc changes FIRST (if needed)
# 3. Commit docs
# 4. Make code/config changes - THIS MUST BE LAST
# 5. Commit code changes (triggers CI on release branch AND master after merge)
git flow release finish X.X.X
```

**Wrong Sequence (NEVER DO THIS):**
```bash
git flow release finish X.X.X
git checkout master
# Edit anything here ← WRONG! Master should only receive merges!
git commit -m "..."  # ← VIOLATES GIT FLOW
```

**Version Management:**
- Update pom.xml version at start of release branch
- Tag is created automatically by `git flow release finish`
- Version in develop should be next SNAPSHOT after release

### Example: Version 0.3.0 (Spotless Execution)

**Timeline:** October 27, 2025

**What was done:**
1. Created EntityNotFoundException
2. Followed all 10 steps exactly
3. Result: Clean release with tag 0.3.0 on GitHub
4. 17 tests GREEN
5. JAR installed to Maven local repository

**Clean Execution Indicators:**
- All tests passed before commit
- No unused imports
- Proper version tagging
- Documentation updated
- Pushed to remote successfully

## Branch Protection Rules

### Master Branch (Production)
- No direct commits allowed
- Only merge via `git flow release finish`
- Only branch to build/install Maven artifacts
- Always tagged with version number

### Develop Branch (Active Development)
- Main development branch
- Feature branches merge here
- Never build release artifacts from here
- Documentation updates happen here

### Release Branches
- Temporary branches for release preparation
- Version bumps happen here
- Final testing before release
- Deleted after `git flow release finish`

## Maven Install/Deploy Rules

### CRITICAL: Master Branch Only

**For Maven install or deploy goals:**
```bash
# ✅ CORRECT
git checkout master
./mvnw clean install

# ❌ WRONG - NEVER from other branches
git checkout develop
./mvnw clean install  # DON'T DO THIS

git checkout release/1.0.0
./mvnw clean install  # DON'T DO THIS
```

**Why:**
- Master is production branch
- Tagged versions must be built from master
- Ensures artifact version matches git tag
- Prevents accidental snapshot deployments

**Workflow:**
1. Finish release (creates tag on master)
2. Checkout master
3. Build and install
4. Switch back to develop for continued work

## Feature Branch Workflow

### Creating Feature Branches
```bash
git flow feature start feature-name
# Creates feature/feature-name from develop
```

### Working on Features
```bash
# Make changes
# Follow TDD cycle
git add .
git commit -m "Descriptive message"
```

### Finishing Features
```bash
git flow feature finish feature-name
# Merges feature into develop
# Deletes feature branch
```

## Hotfix Workflow

### Creating Hotfixes
```bash
git flow hotfix start X.X.X
# Creates hotfix/X.X.X from master
```

### Finishing Hotfixes
```bash
git flow hotfix finish X.X.X
# Merges into both master and develop
# Tags master
# Deletes hotfix branch
```

## Best Practices Summary

1. **Never commit Claude attribution tags** (non-negotiable)
2. **Always achieve GREEN before committing** (TDD discipline)
3. **Only build from master** for releases
4. **Always push tags** after release
5. **Follow 10-step release process** exactly
6. **Update documentation** after each release
7. **Never commit to master directly** (use git flow)
8. **Remove unused imports** before commit
9. **Clean build before commit** to catch breaking changes
