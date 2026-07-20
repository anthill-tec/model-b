# CR-MDB-004 — cr-authoring skill: doc model + project-management split

**Status:** PENDING
**Type:** feature
**Priority:** P2
**Depends on:** CR-MDB-001
**Labels:** skills, docs-model, memory
**Phase:** Wave 2
**Design reference:** `docs/research/PRD-model-b-rationalization.md` §D4 · queue-idiom rules (structure-only queue, wave definition, release CR — user directives 2026-07-20)

## Context

The CR/PRD/DN doc model lives in `memory/cr-prd-dn-conventions.md` (120 lines, loaded ad hoc) while `memory/project-management.md` (877 lines) mixes the CReq/CRes INBOX/OUTBOX pattern with legacy Architecture/Implementation practices and content duplicated elsewhere. Authoring guidance should be a triggered skill, not passive memory.

## Scope

### §S1 — AC gate tests
`tests/test_cr_authoring_skill.py`, wrapper-run, RED → GREEN.

### §S2 — NEW skill `~/.claude/skills/cr-authoring/`
SKILL.md (triggers: CR, PRD, DN, acceptance criteria, spec, queue, CReq, CRes): the full doc model from `cr-prd-dn-conventions.md` restructured, PLUS the 2026-07-20 queue-idiom rules (structure-only queue columns CR/Title/Wave/Depends-on; statuses DERIVED on the Crucible board; header slots Design contract/Evidence base/Ontology/Target release; dated footer Notes; release-boundary row; wave definition; release CR — no close-out wave; AC precision rules; two-file close-out where board-tracking absent, board-only where present).
`references/creq-cres.md`: the CReq/CRes INBOX/OUTBOX library-communication pattern extracted from `project-management.md`.

### §S3 — project-management.md split + deletion
Extract into §S2's references what is still true and unique (CReq/CRes; any surviving practice not already in AGENTS.md/PRD/other skills — enumerate at gap-analysis); archive the whole file to `<repo>/archive/wave2/`; delete `memory/cr-prd-dn-conventions.md` AND `memory/project-management.md` (chezmoi discipline).

### §S4 — repoint consumers
**Surfaces (verified at gap-analysis):** `~/.claude/AGENTS.md` trigger row (cr-prd-dn-conventions → `cr-authoring` skill); references inside `skills/gap-analysis/SKILL.md`, `skills/check-cr-close/`, `skills/git-flow-release/SKILL.md`, and any memory file citing either deleted file.

## Acceptance criteria

### §S1
- [ ] `tests/test_cr_authoring_skill.py` exists; RED then GREEN ingested with wave-2 cycle context.

### §S2
- [ ] `~/.claude/skills/cr-authoring/SKILL.md` exists, frontmatter `name: cr-authoring`, description containing "CR" and "PRD".
- [ ] Contains: "Design reference" (front-matter rule), "§S" (scope-section rule), "Depends on", "structure only" or "structure-only", "DERIVED", "release CR", the wave definition phrase "grouping of CRs", and the AC test: "Can I write the assertion directly from this AC?" (or verbatim-equivalent line).
- [ ] `references/creq-cres.md` exists and contains both "CReq" and "CRes".

### §S3
- [ ] `~/.claude/memory/cr-prd-dn-conventions.md` and `~/.claude/memory/project-management.md` do not exist; archive copies exist under `<repo>/archive/wave2/`.
- [ ] Scoped `chezmoi diff` (5 standard paths) exits 0 empty.

### §S4
- [ ] `grep -rl "cr-prd-dn-conventions\|project-management.md" ~/.claude/skills/ ~/.claude/memory/ ~/.claude/AGENTS.md ~/.claude/agents/` returns 0 files.

## Estimated size
M (877-line split is the bulk).

## Risk
- `project-management.md` content triage is judgment-heavy — gap-analysis enumerates keep/drop line ranges BEFORE dispatch so the GREEN agent executes a list, not a judgment call.

## Non-goals
- Changing the conventions themselves (content moves; rules only gain the already-locked 2026-07-20 user directives).
- gap-analysis / check-cr-close skill rewrites (they only get repoints).
