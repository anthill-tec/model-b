# Memory Files Quick Reference

## When to Load Which Files

### Common Scenarios

#### 🔨 Java Backend Development
```
ALWAYS: CLAUDE.md
LOAD:   java-coding-standards.md
        java-testing-practices.md
        maven-best-practices.md
        quarkus-patterns.md
```

#### 🎨 Frontend/UI Development
```
ALWAYS: CLAUDE.md
LOAD:   tailwind-ui-reference.md
```

#### 📦 Release/Deployment
```
ALWAYS: CLAUDE.md
LOAD:   git-workflow.md
        maven-best-practices.md
        (+ relevant tech stack files)
```

#### 📝 Documentation Work
```
ALWAYS: CLAUDE.md
LOAD:   (use the `cr-authoring` skill for doc conventions)
```

#### 🔧 Environment Setup
```
ALWAYS: CLAUDE.md
LOAD:   devops-environment.md
```

#### 🏗️ Full Stack Project
```
ALWAYS: CLAUDE.md
LOAD:   java-coding-standards.md
        java-testing-practices.md
        maven-best-practices.md
        quarkus-patterns.md
        tailwind-ui-reference.md
        git-workflow.md
```

## File Lookup by Topic

### Need Information About...

**Code Formatting?**
→ `java-coding-standards.md`

**Testing Strategy?**
→ `java-testing-practices.md`

**REST API Patterns?**
→ `quarkus-patterns.md` (REST Resource Layer section)

**MongoDB Queries?**
→ `quarkus-patterns.md` (MongoDB Panache section)

**Git Commits?**
→ `git-workflow.md`

**Maven Builds?**
→ `maven-best-practices.md`

**Dependency Management?**
→ `maven-best-practices.md` (Dependency Management section)

**Plugin Configuration?**
→ `maven-best-practices.md` (Plugin Configuration section)

**Release Process?**
→ `git-workflow.md` (10-step workflow)

**Documentation Structure (CR / PRD / DN)?**
→ `cr-authoring` skill

**Library Projects (INBOX/OUTBOX Pattern)?**
→ `cr-authoring` skill, `references/creq-cres.md` (CReq/CRes communication pattern)

**Tailwind Components?**
→ `tailwind-ui-reference.md`

**DevServices Setup?**
→ `devops-environment.md`

**TestContainers?**
→ `devops-environment.md` + `java-testing-practices.md`

**Exception Handling?**
→ `quarkus-patterns.md` (GlobalExceptionMappers section)

**TDD Workflow?**
→ `java-testing-practices.md`

**Reactive Programming?**
→ `quarkus-patterns.md` (Mutiny section)

## Critical Rules Location

### Where to Find Non-Negotiable Rules

| Rule | Location |
|------|----------|
| NO Claude attribution in git commits | `git-workflow.md` |
| NEVER use full namespace declarations | `java-coding-standards.md` |
| Remove unused imports before commit | `java-coding-standards.md` |
| TDD: RED → GREEN → commit | `java-testing-practices.md` |
| MongoDB queries use MongoDB field names | `quarkus-patterns.md` |
| REST Resources use GlobalExceptionMappers | `quarkus-patterns.md` |
| Maven build only from master branch | `maven-best-practices.md` |
| Always run clean before important builds | `maven-best-practices.md` |
| Always read tests before refactoring | `java-testing-practices.md` |
| @BsonProperty never empty | `java-coding-standards.md` |
| TestContainers with restrictToAnnotatedClass | `java-testing-practices.md` |

## Task-Based Loading

### Task: "Fix bug in Java service"
```
1. Load: java-coding-standards.md (for import rules)
2. Load: java-testing-practices.md (for TDD workflow)
3. If Quarkus: quarkus-patterns.md
4. When done: git-workflow.md (for commit)
```

### Task: "Create new REST endpoint"
```
1. Load: quarkus-patterns.md (REST Resource Layer section)
2. Load: java-coding-standards.md (import rules)
3. Load: java-testing-practices.md (write tests first)
4. When done: git-workflow.md (commit rules)
```

### Task: "Add MongoDB entity"
```
1. Load: java-coding-standards.md (@BsonProperty rules)
2. Load: quarkus-patterns.md (MongoDB Panache patterns)
3. Load: java-testing-practices.md (integration tests)
4. When done: git-workflow.md (commit)
```

### Task: "Build UI component"
```
1. Load: tailwind-ui-reference.md (component catalog)
2. Find relevant template
3. Adapt for project
4. When done: git-workflow.md (commit)
```

### Task: "Prepare release"
```
1. Load: git-workflow.md (10-step release process)
2. Load: maven-best-practices.md (build from master, version management)
3. Ensure all tests pass (java-testing-practices.md)
4. Update documentation (`cr-authoring` skill conventions)
5. Follow release workflow exactly
```

### Task: "Create Java library project"
```
1. Load: maven-best-practices.md (library project standards)
2. Load: java-coding-standards.md (code quality rules)
3. Use: `cr-authoring` skill (documentation structure, CReq/CRes pattern)
4. Setup: proper pom.xml with sources/javadoc plugins
5. Follow: minimal dependencies, semantic versioning
```

### Task: "Configure Maven build"
```
1. Load: maven-best-practices.md (plugin configuration)
2. Setup: compiler plugin with Java 21
3. Setup: surefire for unit tests, failsafe for integration tests
4. Configure: source and javadoc plugins for libraries
5. Test: clean build workflow
```

### Task: "Troubleshoot Maven build failure"
```
1. Load: maven-best-practices.md (Common Issues section)
2. Run: ./mvnw clean compile (force clean build)
3. Check: dependency:tree for conflicts
4. Verify: Java version matches pom.xml
5. Check: build logs for specific errors
```

### Task: "Set up development environment"
```
1. Load: devops-environment.md (DevServices setup)
2. Configure TestContainers (if applicable)
3. Set up continuous testing
4. Verify port allocations
```

### Task: "Write integration test"
```
1. Load: java-testing-practices.md (integration test patterns)
2. Load: devops-environment.md (TestContainers config)
3. If Quarkus: quarkus-patterns.md (reactive testing)
4. Write test, verify GREEN, commit
```

### Task: "Refactor existing code"
```
1. Load: java-testing-practices.md (read tests FIRST rule)
2. Load: java-coding-standards.md (import cleanup)
3. Read tests → Update tests → Refactor → Verify GREEN → Commit
```

## Memory Optimization Tips

### Minimal Loading Strategy
1. Always load CLAUDE.md (it's tiny)
2. Load ONLY files relevant to current task
3. Don't pre-load "just in case" files

### Typical Combinations (by token count)

**Lightweight (~2,000 tokens):**
- CLAUDE.md + git-workflow.md

**Medium (~3,500 tokens):**
- CLAUDE.md + java-coding-standards.md + git-workflow.md

**Heavy (~6,000 tokens):**
- CLAUDE.md + java-coding-standards.md + java-testing-practices.md + quarkus-patterns.md

**Full Stack (~8,000 tokens):**
- All files loaded

### When to Reload

**Reload files when:**
- Switching between tasks requiring different knowledge
- Need to verify specific rule or pattern
- Troubleshooting issue in specific area

**Don't reload if:**
- Already in context and still relevant
- Working on same type of task
- Just need general coding assistance

## Quick Command Reference

### Load Main Configuration
```
Read: /mnt/project/CLAUDE.md
```

### Load Specific Memory File
```
Read: /mnt/project/memory/java-coding-standards.md
Read: /mnt/project/memory/java-testing-practices.md
Read: /mnt/project/memory/quarkus-patterns.md
Read: /mnt/project/skills/git-workflow/SKILL.md
Read: /mnt/project/memory/tailwind-ui-reference.md
Read: /mnt/project/memory/devops-environment.md
```

### Check Available Files
```bash
ls /mnt/project/memory/
```

## Integration with Your Workflow

### Option 1: Manual Loading
Load files as needed based on this quick reference guide

### Option 2: Automated Loading
Configure your tooling to load appropriate files based on:
- File type being edited
- Git branch
- Project type
- Task context

### Option 3: Hybrid Approach
- Always load CLAUDE.md automatically
- Manually load memory files as tasks require
- Keep frequently used files in context

## Summary

**Always Load:** CLAUDE.md (essential rules + references)
**Load as Needed:** Relevant memory files per task
**Result:** 60-75% reduction in context usage while maintaining full access to all guidelines
