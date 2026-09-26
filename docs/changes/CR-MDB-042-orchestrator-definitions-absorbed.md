# CR-MDB-042 — Orchestrator definitions absorbed into the common skills

**Status:** PENDING (filed 2026-09-26; gap analysis 2026-09-26)
**Type:** refactor
**Priority:** P1 — release 1.0.0, wave 2. CR-MDB-041 repoints `bootstrap`/`shutdown` away from the
per-project orchestrator note, and the rules that note carries must have a home first.
**Depends on:** —
**Labels:** skills, orchestration, memory
**Design reference:** PRD D5 (AMENDED 2026-09-26: one orchestrator definition; stack differences in
stack skills; project facts in `.env` + `AGENTS.md`); PRD D3/D4 (procedural content consolidates
into skills); DN-multi-harness §D18 (skills name capabilities and CLIs, never harness tools)

## Context

Model B ships the orchestrator definition as skills: `model-b` (`references/orchestration-
{common,mainline,track}.md`, `sub-agent-procedure.md`, `sandesh.md`), `cr-authoring`,
`git-workflow`, `crucible`, `bootstrap`, `shutdown`, and the stack material (`code-health`,
`memory-templates/<stack>-orchestration.md`). The rules learned while running it were written, in
the Claude Code era, to per-project memory under `~/.claude/projects/<slug>/memory/`, outside any
repository:

| Source | Items | Nature |
|---|---|---|
| `<nai>/memory/ORCHESTRATOR-RULES.md` | 945 lines, §1–§13 | orchestrator rules with NAI and rust overrides |
| `<nai>/memory/ORCHESTRATOR-NAI.md` | 29 lines | NAI identity, Sandesh, pointers |
| `<roundhouse>/memory/ORCHESTRATOR-Roundhouse.md` | 78 lines | Roundhouse identity, Sandesh, Crucible, board, git |
| `~/.claude/AGENTS.md` "Non-negotiables" | 7 rules | global agent rules; Pi has no equivalent file |
| `type: feedback` memories of NAI, Crucible, Sandesh, Model B, Arduino-Valmik, Arduino-PumpControl | 47, 38, 7, 10, 17, 10 files | rules learned per project; most are about the orchestrator's role |

(`<nai>` = `-home-antonyj-Documents-data-projects-nai`, and so on. Roundhouse's memory holds no
feedback files; `ah-codeforge` and `sys-toolbox` are not Model B projects and are out of scope.)

`orchestration-common.md` was distilled from `ORCHESTRATOR-RULES.md`, so part of that file is
already common, sometimes verbatim. The same rule often appears in several projects (for example
"gap analysis needs user approval" in both Arduino projects).

`orchestration-common.md` makes the `gap-analysis` skill "the single authority" for gap-analysis
dimensions, but Model B does not ship it: it exists only as `~/.agents/skills/gap-analysis/SKILL.md`
(258 lines), outside `skills-src/`, so a fresh install leaves that reference dangling. It still
tells the reader to locate the spec and sister projects through `CLAUDE.md` (lines 20, 21, 58, 71).

The five Java references copied into `skills-src/memory-templates/` (CR-MDB-006) are still present
in `~/.claude/memory/`; `archive/mapping.md` records them as `moved` without saying so.

## Scope

### §S1 — Inventory and triage
`audits/2026-09-26-orchestrator-rule-triage.md` holds two tables.

**Inventory**, one row per source file (`| Source | sha256 |`): the home-relative path and its
sha256 at triage time. The items are enumerated in the triage's Source cells: the three notes per
rule-bearing heading (`##`/`###`, as `` `<path>` § <heading> ``), `~/.claude/AGENTS.md` per
Non-negotiables bullet (`§ Non-negotiables (<n>)`), and a feedback topic file as one item (or per
its own headings).

**Triage**, one row per inventory item (heading or topic file):

| Column | Values |
|---|---|
| Source | inventory file + heading (or topic file name) |
| Class | `common` · `stack:<stack>` · `project:<project>` · `duplicate` · `stale` |
| Destination | skill file + section (`common`, `stack`); the project's `AGENTS.md` (`project`); the existing section it repeats (`duplicate`); `—` (`stale`) |
| Note | for `stale`, why: a retired mechanism, a Claude Code tool with no Pi equivalent, a superseded rule, or the excluded electronics stack |

`common` means the rule applies to every orchestrator whatever the project and stack; its
destination is the Model B skill that owns the topic (`model-b` references, `gap-analysis`,
`cr-authoring`, `git-workflow`, `crucible`, `bootstrap`, `shutdown`). `stack:<stack>` is a rule
about which skill or client performs a role step for that stack (`code-health`,
`memory-templates/<stack>-orchestration.md`); a stack without a template gets one only when a rule
needs it. The imported bundles (`crucible-register`, `crucible-report-*`) are Crucible's and are no
destination; a rule for them is `stale` with the note "route to Crucible" and is listed in the
merge note.

A rule naming a Claude Code tool or a retired mechanism is rewritten against today's mechanism or
classified `stale`, never copied as written (DN §D18).

**User gate.** The triage is reviewed and approved by the user before anything is absorbed.

### §S2 — Absorb
Every `common` and `stack` row lands at its destination, as a rule plus, where needed, a one-line
reason; no case histories. A rule already present is not repeated (its row is `duplicate`). The
common text names no project (`NAI`, `Roundhouse`, `ModelB`, `Crucible project`) and no
`ORCHESTRATOR-` note as a rule's subject; a CR id may remain as a dated provenance citation. It
names no harness tool retired by CR-MDB-031.

**Rulings that bind the absorbed text** (user, 2026-09-26):
- A scope change found mid-implementation goes into a patch CR, never an inline spec edit. A track
  edits its own CR's spec in its worktree only for status and for defects against that CR's own
  contracts; Mainline never edits an IN_PROGRESS CR's spec on develop.
- A VERIFY finding the user approves for fixing is fixed in its own FIX cycle (`cycle-add --kind fix`),
  never inside the VERIFY cycle.
- The Crucible board is the task list; there is no separate todo list.
- Model B reaches Sandesh through the `sandesh` CLI; it never uses Sandesh's MCP server.
- A rule inside a triaged item that its row does not carry is not dropped silently: the row's Note
  names it with its class, or it is absorbed.

### §S3 — Project facts
Model B's own `project:model-b` rows land in `model-b/AGENTS.md`. Rows for other projects stay in
the triage for those projects' own sessions (non-goal).

### §S4 — `gap-analysis` becomes a Model B bundle
`~/.agents/skills/gap-analysis/SKILL.md` is adopted as `skills-src/gap-analysis/SKILL.md`, with its
`CLAUDE.md` references replaced by the project's `AGENTS.md`. The installer deploys it like every
other bundle (no stack scope). Its absorbed rules (§S2) land here.

### §S5 — Mapping
`archive/mapping.md` gains one row per inventory source group (the three notes, `~/.claude/AGENTS.md`,
each project's feedback memories) of kind `absorbed` with the triage file as destination, and a row
for `~/.agents/skills/gap-analysis/` of kind `moved` to `skills-src/gap-analysis/`. The five
Java-reference rows state that the original remains in `~/.claude/memory/` until the user removes
it.

## Acceptance criteria

- [ ] The triage file's inventory lists every source above with its sha256; every inventory source
      has triage rows, no item has two, and every row carries one of the five classes — checked by
      a test reading the file (`tests/test_orchestrator_rule_triage.py`). The orchestrator and
      VERIFY re-derive the sources, their sha256 and the notes' headings from the real files
      (read-only) and they match.
- [ ] Every `common`, `stack` and `project:model-b` destination exists: the named file contains the
      named section — checked by a test reading the triage table.
- [ ] No line of a Model B-owned `skills-src/` file names `NAI`, `Roundhouse` or `ORCHESTRATOR-`
      other than inside a dated provenance citation (a CR id and a date on the same line), and none
      names a harness tool retired by CR-MDB-031 — checked by a test. `bootstrap/` and `shutdown/`
      are exempt until CR-MDB-041 (their reading order is its scope); the Crucible-imported bundles
      (`crucible-register`, `crucible-report-*`) are exempt (byte-faithful).
- [ ] The shipped skills state the rulings above and nothing contradicts them — the mainline and
      track references and `cr-authoring` agree on the patch-CR rule.
- [ ] `skills-src/gap-analysis/SKILL.md` exists, names no `CLAUDE.md`, and a sandboxed install
      deploys it to `.agents/skills/gap-analysis/SKILL.md`; the `orchestration-common.md` reference
      to it resolves.
- [ ] `archive/mapping.md` carries the new rows and the corrected Java-reference rows; the mapping
      gate passes.
- [ ] The suite is green on real `HOME`, empty `HOME` and Python 3.11; `AGENTS.md` module count and
      baselines re-measured.

## Non-goals

- No write to `~/.claude` or `~/.agents`. Deleting the absorbed notes and memories, the Java-reference
  originals and the unmanaged `~/.agents/skills/gap-analysis/` (the installer will not overwrite an
  unmanaged file) is a release step the user performs, before the reinstall.
- No edit to another project's repository; each project moves its `project:` rows into its own
  `AGENTS.md` in its own session.
- No change to `bootstrap`/`shutdown` reading order — CR-MDB-041.
- `project`, `reference` and `user` memories are project facts, not rules, and are not triaged.
