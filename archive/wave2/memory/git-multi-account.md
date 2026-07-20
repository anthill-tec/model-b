# Git Multi-Account Strategy

## Dual Remote Pattern: origin + mirror

### Account Division

**Work Account (Antojk71)**
- Organization: `4property`
- Email: antonyjohn@ippi.io
- SSH Key: `~/.ssh/id_ed_4pm_github`
- Remote name: `origin`
- Use for: Professional/work projects

**Personal Account (antojk)**
- Organization: `anthill-tec` (personal projects)
- Email: antojk@gmail.com
- SSH Key: `~/.ssh/id_github_personal`
- Remote name: `mirror`
- Use for: Personal backups, open source contributions

### SSH Configuration

Multi-account SSH access configured via `~/.ssh/config`:

```ssh
# GitHub - antojk personal account (anthill-tec organization)
Host github.com-antojk
   Hostname github.com
   User git
   PreferredAuthentications publickey
   IdentityFile ~/.ssh/id_github_personal
   IdentitiesOnly yes

# GitHub - 4property organization (Antojk71 account)
Host github.com-4property
   Hostname github.com
   User git
   PreferredAuthentications publickey
   IdentityFile ~/.ssh/id_ed_4pm_github
   IdentitiesOnly yes

# GitHub - default (tries both keys)
Host github.com
   Hostname github.com
   User git
   PreferredAuthentications publickey
   IdentityFile ~/.ssh/id_ed_4pm_github
   IdentityFile ~/.ssh/id_github_personal
```

### Git Remote URLs

**Work Repository (origin)**
- URL format: `git@github.com-4property:<org>/<repo>.git`
- Example: `git@github.com-4property:4property/4pm-MDX-gitops.git`
- Account: Antojk71

**Personal Mirror (mirror)**
- URL format: `git@github.com-antojk:<org>/<repo>.git`
- Example: `git@github.com-antojk:anthill-tec/4pm-MDX-gitops.git`
- Account: antojk

### Claude Automation Rules

**CRITICAL**: When `mirror` remote is detected, ALWAYS push to BOTH remotes.

#### Detection

```bash
# Check if mirror remote exists
if git remote | grep -q "^mirror$"; then
    PUSH_TO_BOTH=true
fi
```

#### Push Strategy

**If mirror detected:**
1. Switch to antojk account: `gh auth switch --user antojk`
2. Push to mirror: `git push mirror <branch>`
3. Switch to Antojk71 account: `gh auth switch --user Antojk71`
4. Push to origin: `git push origin <branch>`

**If only origin exists:**
1. Ensure correct account active (usually Antojk71)
2. Push to origin: `git push origin <branch>`

#### Example Implementation

```bash
#!/bin/bash

BRANCH=$(git branch --show-current)

# Check for mirror remote
if git remote | grep -q "^mirror$"; then
    echo "📦 Dual remote detected - pushing to both origin and mirror"
    echo ""

    # Push to mirror (personal account)
    echo "🔄 Pushing to mirror (antojk account)..."
    gh auth switch --user antojk
    git push mirror "$BRANCH"

    # Push to origin (work account)
    echo "🔄 Pushing to origin (Antojk71 account)..."
    gh auth switch --user Antojk71
    git push origin "$BRANCH"

    echo ""
    echo "✅ Pushed to both remotes successfully"
else
    echo "📦 Single remote detected - pushing to origin only"
    gh auth switch --user Antojk71
    git push origin "$BRANCH"
fi
```

### Common Operations

#### Setup New Repository with Dual Remotes

```bash
# Clone from work account
git clone git@github.com-4property:4property/<repo>.git
cd <repo>

# Add personal mirror
git remote add mirror git@github.com-antojk:anthill-tec/<repo>.git

# Verify
git remote -v
```

#### Verify Remote Access

```bash
# Test work remote
git ls-remote origin HEAD

# Test personal mirror
git ls-remote mirror HEAD
```

#### Push Tags to Both Remotes

```bash
gh auth switch --user antojk
git push mirror --tags

gh auth switch --user Antojk71
git push origin --tags
```

### Why Dual Remotes?

**Benefits:**
1. **Redundancy** - Personal backup of work projects
2. **Portability** - Access from personal account if needed
3. **Continuity** - Projects survive organizational changes
4. **Separation** - Clear work/personal boundary

**Use Cases:**
- Critical infrastructure projects (GitOps, IaC)
- Open source projects maintained through work
- Projects that may transition to personal ownership
- Disaster recovery scenarios

### Account Switching

**gh CLI Integration:**

```bash
# Switch to personal account
gh auth switch --user antojk

# Switch to work account
gh auth switch --user Antojk71

# Check current account
gh auth status
```

**SSH Agent:**

SSH keys are auto-loaded via fish shell config:
- Both keys loaded on shell startup
- No manual `ssh-add` required
- Keys persist across sessions

### Troubleshooting

**Issue: "Repository not found" error**

```bash
# Check which account is active
gh auth status

# Verify SSH key selection
ssh -T git@github.com-antojk
ssh -T git@github.com-4property

# Test remote connectivity
git ls-remote origin HEAD
git ls-remote mirror HEAD
```

**Issue: Wrong account pushing**

```bash
# Explicitly switch before push
gh auth switch --user <correct-account>

# Verify remote URL uses correct host alias
git remote get-url origin  # Should have github.com-4property
git remote get-url mirror  # Should have github.com-antojk
```

**Issue: Authentication fails**

```bash
# Check SSH keys are loaded
ssh-add -l | grep "id_ed_4pm_github\|id_github_personal"

# Re-source fish config if needed
source ~/.config/fish/config.fish
```

### Git Config Considerations

**Global Config (Default)**
```bash
git config --global user.name "Antony John"
git config --global user.email "antonyjohn@ippi.io"
```

**Repository-Specific Override (if needed)**
```bash
# For personal projects
git config user.email "antojk@gmail.com"
```

### Integration with Skills

**git-flow-release skill:**
- Should detect mirror remote
- Push tags to both remotes after release
- Verify both remotes before starting release

**git-flow-develop-gitops skill:**
- Should detect mirror remote
- Push to both after local validation
- Monitor CI on origin (primary)

### Notes

- Mirror is **optional** - not all projects need it
- Mirror is typically for **infrastructure/critical** projects
- Mirror repos should be **private** to match origin
- Mirror should be kept **in sync** with origin
- Use mirror for **backup**, origin for **collaboration**

---

**Version**: 1.0.0
**Last Updated**: 2025-11-11
**Related**: git-workflow.md, git-flow-release.md, git-flow-develop-gitops.md
