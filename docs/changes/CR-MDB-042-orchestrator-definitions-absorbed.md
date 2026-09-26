# CR-MDB-042 — Orchestrator definitions absorbed into the common skill

**Status:** PENDING (filed 2026-09-26)
**Type:** refactor
**Priority:** P1 — release 1.0.0, wave 2. CR-MDB-041 repoints `bootstrap`/`shutdown` away from the
per-project orchestrator note, and the rules that note carries must have a home first.
**Depends on:** —
**Labels:** skills, orchestration, memory
**Design reference:** PRD D5 (AMENDED 2026-09-26: one orchestrator definition; stack differences in
stack skills; project facts in `.env` + `AGENTS.md`); PRD D3/D4 (procedural content consolidates
into skills); DN-multi-harness §D18 (skills name capabilities and CLIs, never harness tools)

## Context

The orchestrator rules exist in two places. The `model-b` skill ships them to every project
(`skills-src/model-b/references/orchestration-{common,mainline,track}.md`, `sub-agent-procedure.md`,
`sandesh.md`). Per-project notes from the Claude Code era hold more of them, in the user's home and
outside any repository:

| Source | Lines | Content |
|---|---|---|
| `~/.claude/projects/<nai>/memory/ORCHESTRATOR-RULES.md` | 945 | Tier map; two-phase workflow; worktree isolation; cycle discipline; dispatch; approval gates; escalation; cargo/Crucible knobs; CR spec discipline; code quality; tools; e2e; question economy (§1–§13) |
| `~/.claude/projects/<nai>/memory/ORCHESTRATOR-NAI.md` | 29 | Identity (Crucible agent-id tiers); gap-analysis; conventions pointers; stack pointer; Sandesh |
| `~/.claude/projects/<roundhouse>/memory/ORCHESTRATOR-Roundhouse.md` | 78 | Identity; Sandesh; Crucible; queue-only board; Git |
| `~/.claude/projects/<model-b>/memory/` | `MEMORY.md` + 14 topic files | Orchestrator supervision, briefs, Crucible prod-only, register-first, fix-the-source, provider services, comms discipline; plus Model B project facts |

`orchestration-common.md` was distilled from `ORCHESTRATOR-RULES.md`, so much of that file is
already common, sometimes verbatim. The rest mixes three kinds of content (PRD D5, amended):
rules common to every orchestrator, stack-specific execution (which skill or client performs a
role step), and project facts.

The five Java references copied into `skills-src/memory-templates/` (CR-MDB-006) are still present
in `~/.claude/memory/`; `archive/mapping.md` records them as `moved` without saying so.

## Scope

### §S1 — Triage
Every rule-bearing section of the four sources above is classified once, in
`audits/<date>-orchestrator-note-triage.md`, one row per section (heading or topic file):

| Column | Values |
|---|---|
| Source | file + heading |
| Class | `common` · `stack:<stack>` · `project:<project>` · `duplicate` · `stale` |
| Destination | file + section it now lives in (`common`, `stack`, `duplicate`); the project's `AGENTS.md` (`project`); `—` (`stale`) |
| Note | for `duplicate`, the existing section it matches; for `stale`, why (retired mechanism, Claude Code tool, superseded rule) |

A rule naming a Claude Code tool or a retired mechanism is rewritten against today's mechanism or
classified `stale`, never copied as written (DN §D18).

### §S2 — Common rules absorbed
Every `common` row lands in the `model-b` skill references, in the section its topic belongs to.
The common text names no project (no `NAI`, `Roundhouse`, `ModelB` or project-specific CR id as a
rule's subject; a CR id may remain as a dated provenance citation) and no harness tool.

### §S3 — Stack rules absorbed
Every `stack:<stack>` row lands in that stack's skill or `<stack>-orchestration` memory template.

### §S4 — Project facts
Model B's own `project:model-b` rows land in `model-b/AGENTS.md`. Rows for other projects stay
listed in the triage for those projects' own sessions (non-goal).

### §S5 — Mapping
`archive/mapping.md` gains one row per source (the three notes and the Model B project-memory
directory), kind `absorbed`, destination the triage file. The five Java-reference rows state that
the original remains in `~/.claude/memory/` until the user removes it.

## Acceptance criteria

- [ ] The triage file exists, covers every `##`/`###` heading of the three notes and every Model B
      topic file, and every row carries one of the five classes.
- [ ] Every `common`, `stack` and `project:model-b` destination exists: the named file contains the
      named section — checked by a test reading the triage table.
- [ ] No `skills-src/model-b/references/*.md` line names `NAI`, `Roundhouse` or `ORCHESTRATOR-` as a
      rule's subject, and none names a harness tool retired by CR-MDB-031 — checked by a test.
- [ ] `archive/mapping.md` carries the four new rows and the corrected Java-reference rows; the
      mapping gate passes.
- [ ] The suite is green on real `HOME`, empty `HOME` and Python 3.11; baselines re-measured in
      `AGENTS.md` if the counts change.

## Non-goals

- No write to `~/.claude`. Deleting the absorbed notes and the Java-reference originals is a
  release step the user performs.
- No edit to another project's repository; NAI and Roundhouse move their `project:` rows into their
  own `AGENTS.md` in their own sessions.
- No change to `bootstrap`/`shutdown` reading order — CR-MDB-041.
