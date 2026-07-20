# Chezmoi Integration for Claude Memory Management

## Overview

**chezmoi** is used to manage Claude Code user-level and global-level configuration files with git version control. This provides safety, backup, and synchronization of Claude's memory and skills across systems.

**Purpose**:
- Version control for Claude configuration
- Backup of user memory and skills
- Synchronization across multiple machines
- Recovery from accidental deletions or changes

---

## What's Stored in Chezmoi

### User-Level Files (Global - Cross-Project)

**Location**: `~/.claude/`

#### CLAUDE.md (Main Configuration)
```
~/.claude/CLAUDE.md
```
**Content**:
- Project classification system (Quarkus, Library, GitOps)
- Essential rules (Git commits, Java quality, TDD discipline)
- Quick reference to memory files
- Context management guidelines

**Managed**: ✅ Yes - Core configuration, frequently updated

#### Memory Files
```
~/.claude/memory/
├── java-coding-standards.md
├── java-testing-practices.md
├── maven-best-practices.md
├── quarkus-patterns.md
├── convex-client-server.md
├── git-workflow.md
├── devops-environment.md
├── git-multi-account.md
└── chezmoi-integration.md (this file)
```

**Content**:
- Language/framework-specific guidelines
- Testing practices and TDD workflow
- Build tool best practices
- Git workflow and multi-account strategy
- DevOps environment setup

**Managed**: ✅ Yes - Knowledge base, updated as practices evolve

#### Skills
```
~/.claude/skills/
├── git-flow-release/
│   └── SKILL.md
├── git-flow-develop-gitops/
│   └── SKILL.md
└── (other skills)/
    └── SKILL.md
```

**Content**:
- Automated workflows for complex tasks
- Git flow automation (release, develop)
- Project-specific skills

**Managed**: ✅ Yes - Reusable automation, periodically enhanced

#### Settings
```
~/.claude/settings.json
```

**Content**:
- Claude Code application settings
- Tool configurations
- User preferences

**Managed**: ✅ Yes - Preserves Claude Code configuration

### Shell Configuration

#### Fish Shell Config
```
~/.config/fish/config.fish
```

**Content**:
- SSH agent auto-start
- GitHub SSH key auto-loading
- Interactive session configuration

**Managed**: ✅ Yes - Critical for SSH/gh authentication

#### SSH Configuration
```
~/.ssh/config
```

**Content**:
- Multi-account GitHub access (host aliases)
- SSH key mappings for work/personal accounts
- Server configurations (GitLab, OCI, etc.)

**Managed**: ✅ Yes - Required for dual remote git strategy

---

## What's NOT Stored in Chezmoi

**Excluded Files** (intentionally not tracked):

### Temporary/Cache Files
```
~/.claude/history.jsonl           # Command history
~/.claude/debug/                  # Debug logs
~/.claude/file-history/           # File change history
~/.claude/session-env/            # Session environment variables
~/.claude/todos/                  # Project-specific todos
```

**Reason**: Ephemeral data, constantly changing, not useful for backup

### Credentials/Secrets
```
~/.claude/credentials/            # API keys, tokens
~/.ssh/id_*                       # SSH private keys (only config tracked)
~/.ssh/*.pub                      # SSH public keys
```

**Reason**: Security - secrets should NEVER be committed to git

### Project-Specific Files
```
<project>/CLAUDE.md               # Project-level instructions
<project>/docs/                   # Project documentation
```

**Reason**: Managed in project repositories, not user-level config

---

## Chezmoi Usage

### Initial Setup

**One-time configuration**:
```bash
# Initialize chezmoi with git repository
chezmoi init https://github.com/<your-account>/<dotfiles-repo>.git

# Or create new repository
chezmoi init
cd $(chezmoi source-path)
git init
git remote add origin git@github.com:<your-account>/<dotfiles-repo>.git
```

**Current Setup**:
- Repository: User-specific (different git account than work projects)
- Authentication: SSH with appropriate account

### Adding Files to Chezmoi

**Add new file**:
```bash
# Add single file
chezmoi add ~/.claude/memory/new-memory.md

# Add directory recursively (careful!)
chezmoi add -r ~/.claude/memory/

# Add with template (for system-specific configs)
chezmoi add --template ~/.ssh/config
```

**Current tracked files**:
- `~/.claude/CLAUDE.md`
- `~/.claude/memory/*.md` (all memory files)
- `~/.claude/skills/**/*.md` (all skill files)
- `~/.claude/settings.json`
- `~/.config/fish/config.fish`
- `~/.ssh/config`

### Updating Files

**Workflow**:
```bash
# 1. Edit file normally (in ~/.claude/...)
vi ~/.claude/memory/java-coding-standards.md

# 2. Update chezmoi's source
chezmoi add ~/.claude/memory/java-coding-standards.md

# 3. Review changes
chezmoi diff

# 4. Commit to git
cd $(chezmoi source-path)
git add .
git commit -m "docs: update Java coding standards"
git push
```

**Shortcut** (commit from chezmoi):
```bash
# Edit file
vi ~/.claude/memory/java-coding-standards.md

# Add and commit in one step
chezmoi cd
git add .
git commit -m "docs: update Java coding standards"
git push
exit
```

### Reviewing Changes

**Check what's different**:
```bash
# See all differences between filesystem and chezmoi
chezmoi diff

# See specific file diff
chezmoi diff ~/.claude/CLAUDE.md

# List managed files
chezmoi managed

# Verify state
chezmoi verify
```

### Applying Changes (Restore from Chezmoi)

**Restore files**:
```bash
# Dry run - see what would change
chezmoi apply --dry-run --verbose

# Apply all changes
chezmoi apply

# Apply specific file
chezmoi apply ~/.claude/memory/git-workflow.md
```

### Git Operations

**Commit changes**:
```bash
cd $(chezmoi source-path)
git add .
git commit -m "feat: add GitOps project classification"
git push
```

**Pull latest from remote**:
```bash
cd $(chezmoi source-path)
git pull
exit

# Apply to filesystem
chezmoi apply
```

### Synchronization Across Systems

**On new system**:
```bash
# Initialize and pull from remote
chezmoi init https://github.com/<your-account>/<dotfiles-repo>.git

# Apply to filesystem
chezmoi apply

# Verify
chezmoi verify
```

**On existing system**:
```bash
# Pull latest changes
chezmoi update

# Or manually
cd $(chezmoi source-path)
git pull
exit
chezmoi apply
```

---

## Multi-Account Git Integration

### Current Setup

**Work Account** (primary terminal session):
- User: Antojk71
- Email: antonyjohn@ippi.io
- Used for: 4property organization projects

**Personal Account** (chezmoi repository):
- User: antojk (or different account)
- Email: antojk@gmail.com
- Used for: Personal dotfiles repository

### Account Detection

**Check active account**:
```bash
gh auth status
```

**Switch accounts** (if needed):
```bash
# Switch to personal account (for chezmoi commits)
gh auth switch --user <personal-username>

# Switch back to work account
gh auth switch --user Antojk71
```

### Committing Chezmoi Changes

**Workflow**:
```bash
# 1. Ensure correct git account active
gh auth status

# 2. Switch if needed
gh auth switch --user <personal-username>

# 3. Commit chezmoi changes
cd $(chezmoi source-path)
git add .
git commit -m "docs: update Claude memory"
git push
exit

# 4. Switch back to work account
gh auth switch --user Antojk71
```

---

## Benefits

### 1. Safety and Backup
- All Claude configuration version-controlled
- Recovery from accidental deletions
- History of changes with git log

### 2. Synchronization
- Multiple machines stay in sync
- Easy setup on new systems
- Consistent Claude behavior across environments

### 3. Knowledge Preservation
- User memory survives system reinstalls
- Skills and workflows preserved
- Git history shows evolution of practices

### 4. Collaboration (Optional)
- Share skills with team members
- Contribute improvements back
- Learn from others' configurations

---

## Common Operations

### Adding New Memory File

```bash
# Create memory file
vi ~/.claude/memory/new-topic.md

# Add to chezmoi
chezmoi add ~/.claude/memory/new-topic.md

# Commit
chezmoi cd
git add memory/new-topic.md
git commit -m "docs: add new-topic memory"
git push
exit
```

### Updating Existing Memory

```bash
# Edit file
vi ~/.claude/memory/java-coding-standards.md

# Update in chezmoi
chezmoi add ~/.claude/memory/java-coding-standards.md

# Commit
chezmoi cd
git add memory/java-coding-standards.md
git commit -m "docs: update Java coding standards"
git push
exit
```

### Adding New Skill

```bash
# Create skill directory and file
mkdir -p ~/.claude/skills/my-new-skill
vi ~/.claude/skills/my-new-skill/SKILL.md

# Add to chezmoi recursively
chezmoi add -r ~/.claude/skills/my-new-skill/

# Commit
chezmoi cd
git add skills/my-new-skill/
git commit -m "feat: add my-new-skill"
git push
exit
```

### Updating Shell Configuration

```bash
# Edit fish config
vi ~/.config/fish/config.fish

# Update in chezmoi
chezmoi add ~/.config/fish/config.fish

# Commit
chezmoi cd
git add fish/config.fish
git commit -m "chore: update fish shell config"
git push
exit
```

### Updating SSH Configuration

```bash
# Edit SSH config
vi ~/.ssh/config

# Update in chezmoi
chezmoi add ~/.ssh/config

# Commit
chezmoi cd
git add ssh/config
git commit -m "chore: update SSH configuration"
git push
exit
```

---

## Troubleshooting

### Issue: Files Out of Sync

**Symptom**: `chezmoi verify` reports differences

**Solution**:
```bash
# See what's different
chezmoi diff

# Option 1: Update chezmoi from filesystem
chezmoi add <file>

# Option 2: Update filesystem from chezmoi
chezmoi apply
```

### Issue: Wrong Git Account

**Symptom**: Push fails with authentication error

**Solution**:
```bash
# Check active account
gh auth status

# Switch to correct account
gh auth switch --user <correct-username>

# Retry push
cd $(chezmoi source-path)
git push
```

### Issue: Merge Conflicts

**Symptom**: `git pull` reports conflicts in chezmoi source

**Solution**:
```bash
cd $(chezmoi source-path)

# View conflicts
git status

# Resolve manually
vi <conflicted-file>

# Commit resolution
git add <conflicted-file>
git commit -m "chore: resolve merge conflict"
git push
exit

# Apply to filesystem
chezmoi apply
```

---

## Best Practices

### 1. Regular Commits
- Commit changes after significant updates
- Use descriptive commit messages
- Follow conventional commit format (feat:, docs:, chore:, etc.)

### 2. Review Before Apply
- Always run `chezmoi diff` before `chezmoi apply`
- Understand what will change
- Backup important files before major changes

### 3. Account Awareness
- Check `gh auth status` before committing
- Use correct account for chezmoi vs work repositories
- Document account usage in commit messages if needed

### 4. Selective Tracking
- **DO** track: Configuration, memory, skills, settings
- **DON'T** track: Credentials, cache, temporary files, project-specific files

### 5. Synchronization Discipline
- Pull before making changes on multiple systems
- Push after making changes
- Resolve conflicts promptly

---

## Integration with Claude Workflow

### Memory Updates
When Claude creates or updates memory files:
1. Files are created in `~/.claude/memory/`
2. Claude commits to chezmoi automatically (if configured)
3. User manually pushes to remote (or automates)

### Skill Updates
When Claude updates skills:
1. Skill files updated in `~/.claude/skills/`
2. Version bumped in SKILL.md
3. Claude commits to chezmoi
4. User pushes to remote

### Settings Changes
When Claude Code settings change:
1. `~/.claude/settings.json` updated
2. User manually adds to chezmoi
3. Commit and push

---

## Notes

- Chezmoi uses a **different git account** than work projects (personal vs work)
- SSH keys are **NOT** tracked (only `~/.ssh/config`)
- Project-specific CLAUDE.md files are **NOT** in chezmoi (managed in project repos)
- Project-specific documentation is **NOT** in chezmoi (managed in project repos)
- Total tracked files: ~15 files (CLAUDE.md + 10 memory files + 2 skills + settings.json + fish config + SSH config)

---

**Version**: 1.0.0
**Last Updated**: 2025-11-11
**Related**: git-multi-account.md, git-workflow.md
