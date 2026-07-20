# CR-MDB-005 — git-workflow + chezmoi skills: memory-twin merges + delete procedure

**Status:** COMPLETED (shipped 2026-07-20 on develop)
**Type:** feature
**Priority:** P2
**Depends on:** CR-MDB-001
**Labels:** skills, git, chezmoi, memory
**Phase:** Wave 2
**Design reference:** `docs/research/PRD-model-b-rationalization.md` §D4, §D9 · `archive/BASELINE.md` (delete-proof + non-TTY gotcha, verified 2026-07-20)

## Context

`skills/git-workflow` and `memory/git-workflow.md` are near-twins (three-way redundancy with `git-flow-release` citing the memory file); `memory/git-multi-account.md` overlaps `memory/chezmoi-integration.md` §Multi-Account; chezmoi guidance documents add/apply but not deletion — the resurrection hazard this project already proved and solved (BASELINE.md).

## Scope

### §S1 — AC gate tests
`tests/test_git_chezmoi_skills.py`, wrapper-run, RED → GREEN.

### §S2 — git-workflow skill rewrite
`~/.claude/skills/git-workflow/SKILL.md` absorbs `memory/git-workflow.md` (branch discipline, commit conventions incl. no-AI-attribution, versioning, 10-step release) + the git parts of `memory/git-multi-account.md` (account switching around push). Single home; `git-flow-release` keeps only its own procedure and cites the skill.

### §S3 — NEW chezmoi skill
`~/.claude/skills/chezmoi/SKILL.md` (triggers: chezmoi, dotfiles, ~/.claude edits, delete a managed file): the add/diff/apply cycle; **the DELETE/RENAME procedure** (`chezmoi destroy --force` managed / `forget`+rm; plain rm resurrects — cite the BASELINE proof); **the non-TTY agent-session workaround** (no-auto temp config via sed, manual source commits, NEVER auto-push, NEVER bare mutating chezmoi, NEVER blind `apply`); the chezmoi side of multi-account; the source-ahead-drift reconciliation warning; the `diff <dir>` silent-empty quirk.

### §S4 — deletions
`memory/git-workflow.md`, `memory/git-multi-account.md`, `memory/chezmoi-integration.md`: archive to `<repo>/archive/wave2/`, delete via chezmoi discipline.

### §S5 — repoint consumers
**Surfaces (gap-analysis verified 2026-07-20):** `skills/git-flow-release/SKILL.md` citations of `memory/git-workflow.md` → the skill; `memory/QUICK_REFERENCE.md` (dies in 006 — repoint for the gate); `~/.claude/AGENTS.md` chezmoi trigger row → `chezmoi` skill, dropping "until Wave 2" (git row already points at the skill — verified). All three memory files chezmoi-managed → destroy path.

## Acceptance criteria

### §S1
- [ ] `tests/test_git_chezmoi_skills.py` exists; RED then GREEN ingested with wave-2 cycle context.

### §S2
- [ ] `~/.claude/skills/git-workflow/SKILL.md` contains: "attribution" (the never-attribute rule), "git flow release", and a multi-account/account-switch line ("gh auth switch" or equivalent).

### §S3
- [ ] `~/.claude/skills/chezmoi/SKILL.md` exists, frontmatter `name: chezmoi`, non-empty description.
- [ ] Contains: `chezmoi destroy`, "resurrect", "autoCommit", "no-auto" (or the sed workaround verbatim), "never push" (case-insensitive), and the `diff <dir>` quirk mention.

### §S4
- [ ] `memory/git-workflow.md`, `memory/git-multi-account.md`, `memory/chezmoi-integration.md` do not exist; archive copies under `<repo>/archive/wave2/`.
- [ ] Scoped `chezmoi diff` (5 standard paths) exits 0 empty.

### §S5
- [ ] `grep -rl "memory/git-workflow\|git-multi-account\|chezmoi-integration" ~/.claude/skills/ ~/.claude/memory/ ~/.claude/AGENTS.md ~/.claude/agents/` returns 0 files.

## Estimated size
M.

## Risk
- The chezmoi skill documents the exact procedure THIS project's waves depend on — errors here propagate into every later wave's chezmoi ops; VERIFY must exercise the documented commands against a scratch file (read-only variants) rather than trusting prose.

## Non-goals
- `git-flow-develop-gitops`, `ci-monitor` (untouched).
- The global→project memory migration (006) — this CR only merges the twins into skills.
