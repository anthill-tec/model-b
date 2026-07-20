# CR-MDB-002 — model-b skill body: canonical definition + universal conventions

**Status:** PENDING
**Type:** feature
**Priority:** P1 (wave-2 keystone — 006/007 depend on it)
**Depends on:** CR-MDB-001
**Labels:** skills, model-b, memory
**Phase:** Wave 2
**Design reference:** `docs/research/PRD-model-b-rationalization.md` §D3 (canonical Model B + universal conventions) · `crucible:docs/research/DN-model-b-language.md` (LOCKED ontology — cite, never fork)

## Context

CR-MDB-001 seeded `~/.claude/skills/model-b/` with a stub SKILL.md and the relocated sub-agent procedure. The canonical Model B definition still lives scattered in `memory/orchestration-{common,mainline,track}.md` + `memory/sandesh.md`, and the universal conventions locked in PRD §D3 have no loadable home. This CR makes the skill the single canonical home.

## Scope

### §S1 — AC gate tests
`tests/test_model_b_skill.py` (unittest-style, stdlib) asserting the §S2–§S5 ACs against the live `~/.claude` tree; run + ingested via the context wrapper (`/tmp/claude-1000/modelb-crucible`), RED before §S2 lands, GREEN after.

### §S2 — SKILL.md full body (replaces the stub)
Frontmatter: `name: model-b`, rewritten description (workflow-scoped triggers: model b, orchestration, mainline, track, solo, wave, CR queue, sub-agent procedure). Body sections:
1. The model in one sentence + Crucible relationship (cite the ontology DN — do not restate beyond a summary ≤10 lines).
2. Role hierarchy + labels: MAINLINE/track/phase-agent roles; orchestrator labels `vidushi-<short>` (solo default) / `Mainline-<short>` + `track<N>-<short>` (multi); label ≠ `WORKFLOW_ROLE` wire (`track-<n>`, absent solo).
3. Containment chain Project→Mainline→[Track]→CR→Cycle→runs; execution vocabulary (Cycle kinds `red-green|verify|fix`, orchestrator-confirm closure; CR closes on merge; Wave = CR grouping/sync boundary — setup tasks and releases are NOT waves; Plan/Gate/Milestone/Run).
4. Universal conventions (PRD §D3 verbatim intent): naming registry + `.env` static init (`PROJECT_NAME/TOKEN/ACRONYM/ORCHESTRATOR_LABEL`) + monorepo per-sub-project qualifier; structure-only queue idiom + derived statuses; plan/cycle idiom (`plan-file --cr --title --cycles --wave --orchestrator`, server-assigned ids, labels `C<n> <label> (§S…)`); standard docs model; release CR (no close-out wave).
5. Role routing: `mainline`/`track`/`solo` → the §S3 references.
6. Electronics stack: excluded/under revision (one line).

### §S3 — references/ population
Move (content-preserving; "Plan B"→"Model B"; shim refs already gone): `orchestration-common.md`, `orchestration-mainline.md`, `orchestration-track.md`, `sandesh.md` → `~/.claude/skills/model-b/references/` (same basenames). `sub-agent-procedure.md` stays.

### §S4 — memory deletions (chezmoi discipline)
Copy the four §S3 source files to `<repo>/archive/wave2/`, then delete from `~/.claude/memory/` — managed files via `chezmoi destroy --force` (no-auto config), unmanaged via `rm`; `chezmoi add` the new references; manual source commit.

### §S5 — repoint consumers
**Surfaces (gap-analysis verified 2026-07-20):** `skills/bootstrap/SKILL.md`, `skills/shutdown/SKILL.md`, `skills/agent-protocol/SKILL.md` (transitional — deleted by CR-MDB-003, repointed here so this CR's grep gate holds) references to `memory/orchestration-*` / `memory/sandesh.md` → the model-b references paths; the model-b stub's own mention is replaced wholesale by §S2; `~/.claude/AGENTS.md` trigger-table row drops the "until Wave 2" caveat and points solely at the `model-b` skill.

## Acceptance criteria

### §S1
- [ ] `tests/test_model_b_skill.py` exists; RED run then GREEN run ingested to project Model B with wave-2 cycle context.

### §S2
- [ ] `~/.claude/skills/model-b/SKILL.md` frontmatter has `name: model-b` and a description containing "orchestration" and "sub-agent".
- [ ] Body contains: `vidushi-` AND `Mainline-<` AND `track<N>-<` (label rule); `track-<n>` (wire rule); `red-green` AND `verify` AND `fix` (cycle kinds); "sync boundary" (wave); `plan-file` AND `--wave` AND `--orchestrator` (plan idiom); `PROJECT_ACRONYM` (registry); "release" AND zero occurrences of "close-out wave".
- [ ] Body contains zero occurrences of "Plan B" and zero of "orchestration-universal".

### §S3
- [ ] All four files exist under `~/.claude/skills/model-b/references/`; each retains its distinctive anchor (gap-analysis verified): common → "MODE-MAP", mainline → "shutdown", track → "NEVER self-schedule", sandesh → "PRIME DIRECTIVE".
- [ ] Zero occurrences of "Plan B" across `~/.claude/skills/model-b/`.

### §S4
- [ ] `~/.claude/memory/orchestration-common.md`, `orchestration-mainline.md`, `orchestration-track.md`, `sandesh.md` do not exist; copies exist under `<repo>/archive/wave2/`.
- [ ] `chezmoi diff ~/.claude/AGENTS.md ~/.claude/CLAUDE.md ~/.claude/agents ~/.claude/memory ~/.claude/skills` exits 0 with empty output.

### §S5
- [ ] `grep -rl "memory/orchestration-\|memory/sandesh" ~/.claude/skills/ ~/.claude/AGENTS.md` returns 0 files.
- [ ] AGENTS.md trigger table's model-b row contains no "until Wave 2".

## Estimated size
M. One red-green cycle + verify.

## Risk
- bootstrap/shutdown are load-bearing for other live orchestrator sessions — execute with no other Model B sessions active (standing wave rule).
- Ontology drift: the skill cites the Crucible DN; if that DN moves, the pointer breaks — accepted (single-source rule).

## Non-goals
- Rewriting crucible/cr-authoring/git-workflow content (CR-MDB-003/004/005).
- The global→project memory migration mechanics (CR-MDB-006) and naming sweep (CR-MDB-007).
- Vercel-standard registry packaging/distribution (CR-MDB-014) — this CR keeps the on-disk skill dir shape (SKILL.md + references/), which is bundle-compatible.
