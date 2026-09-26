# CR-MDB-041 — Bootstrap and shutdown read the files `init` scaffolds

**Status:** PENDING (filed 2026-09-25 from Crucible Mainline's question, Sandesh #1392/#1393; gap
analysis 2026-09-26)
**Type:** fix
**Priority:** P1 — release 1.0.0, wave 2. Every Pi orchestrator runs these two skills at the start
and end of every session, and today they send it looking for files that do not exist.
**Depends on:** CR-MDB-042 (merged: the orchestrator rules live in the common skills)
**Labels:** skills, bootstrap, shutdown, scaffold, registry
**Design reference:** PRD D5 (AMENDED 2026-09-26: one orchestrator definition, no per-project
orchestrator note); PRD D3.1 (the `.env` naming registry; AMENDED 2026-09-26: `SANDESH_PROJECT`);
PRD D10 (what `init` scaffolds); DN-multi-harness §D19 (session model), §D14 (Pi only), §D18
(capabilities and CLIs, not harness tools)

## Context

`bootstrap` and `shutdown` send the orchestrator to a project **`ORCHESTRATOR-<Project>` note** and
a memory index **`MEMORY.md`**, both from the Claude Code era, where they lived under
`~/.claude/projects/<slug>/memory/`. No Model B tool creates either file. Since CR-MDB-042 there is
no per-project orchestrator note at all: the orchestrator's rules are in the `model-b` skill, stack
rules in the stack skills and memory templates, and a project keeps only its identity (`.env`) and
conventions (`AGENTS.md`) (PRD D5, amended).

What `modelb-axi init` scaffolds (measured 2026-09-26, sandboxed, `--stacks python --mode solo`):
- `.env` — `PROJECT_NAME`, `PROJECT_TOKEN`, `PROJECT_ACRONYM`, `ORCHESTRATOR_LABEL`, `REPO_OWNER`,
  `PROJECT_STACKS`;
- `AGENTS.md` — "Identity & naming (registry: `.env` at the project root)", "Workflow rules", "Skill
  freeze", "Harness anchors", "Harness capability contract", "Generator note";
- `docs/memory/INDEX.md` — the project memory index, listing the memory slices seeded from
  `memory-templates/` for the project's stacks (e.g. `operational-commands.md`, and
  `<stack>-orchestration.md` for a stack that has one).

The registry does not carry the Sandesh project id, and none of its values yields it: Sandesh ids
are case- and space-sensitive, while `PROJECT_NAME` may contain spaces and `PROJECT_TOKEN` is
lower-case. PRD D3.1 (amended) adds `SANDESH_PROJECT` to the generic registry template.

Most live projects predate `init`: NAI, Crucible, Sandesh and Valmik have no registry values in a
`.env`. For them the fallback is the common path, not an edge case.

Also stale in the two skills (2026-09-26):
- Track detection by `git rev-parse --show-toplevel` ending in `/.worktrees/<cr>` (bootstrap Step 0
  fallback 2, shutdown Step 0.1). Since CR-MDB-039 a Track's session stays in the main tree.
- A todo/task list recovered, repainted, drained or escalated (`bootstrap/SKILL.md:3, 142–146`;
  `shutdown/SKILL.md:14, 18, 102, 115, 118, 120, 140, 211, 212`). The Crucible board is the task
  list (CR-MDB-042).
- `bootstrap` names `python-crucible.py next` for every project; a project uses its own stack
  client, and every stack client carries the plan verbs (`plans`, `next`).
- The own-run id example `vidushi` / `vidushi-t<N>` and "NAI = `Nai`" casing note.

## Scope

### §S1 — Registry: `SANDESH_PROJECT`
The generic `.env` template that `init` renders for every project (`modelb_axi/scaffold.py`,
`_render_env`) gains `SANDESH_PROJECT=<id>`, after `ORCHESTRATOR_LABEL`. The
default is `PROJECT_NAME` with all whitespace removed; a new `init` flag `--sandesh-project <id>`
overrides it (validated: non-empty, no whitespace). `--dry-run` reports it like the other keys.
`AGENTS.md`'s "Identity & naming" section names the key. Nothing else changes in `init`.

### §S2 — Reading order and identity
In `skills-src/bootstrap/SKILL.md` and `skills-src/shutdown/SKILL.md`, "read your role's rules"
becomes, in order:
1. `model-b` references `orchestration-common.md`, then the role file (Mainline or Track; Solo
   follows Mainline), then `sandesh.md`;
2. the project's `AGENTS.md` (its conventions) and `.env` (its identity);
3. `docs/memory/INDEX.md` and the slices it lists (the stack's orchestration template among them).
No per-project orchestrator note and no `MEMORY.md` is named. Identity comes from `.env`:
- the Sandesh project from `SANDESH_PROJECT`, so the addresses are `Mainline - <SANDESH_PROJECT>` and
  `Track <N> - <SANDESH_PROJECT>`, and every `sandesh` call passes `--project <SANDESH_PROJECT>`;
- the Crucible own-run id from `ORCHESTRATOR_LABEL` (Mainline or Solo); a Track's is
  `track<N>-<PROJECT_TOKEN>` (PRD D3.1's mode-aware rule);
- the Crucible client is the project's stack client, `~/.crucible/clients/<stack>-crucible.py` for a
  stack in `PROJECT_STACKS` (any one: the plan verbs are universal).

**Fallback** (a project without a `.env` registry, or a missing key): the same values are taken from
the project's `AGENTS.md`; a value found in neither is asked of the user once. A missing
`docs/memory/INDEX.md` is noted and skipped. Nothing is an error.

### §S3 — Role, board, todo list
- Role comes from the invocation argument, then the carried context, then the session's Sandesh
  address (`Track <N> - …` ⟹ Track N); otherwise ask. No working-directory or `/.worktrees/`
  heuristic.
- `bootstrap` Step 2 reloads the in-flight work from the board (`plans`, then the active cycle,
  `next`), never from a todo list; `shutdown` drains the plan's open cycles, and its Track escalation
  names the open cycles, not "active todos".
- The descriptions (frontmatter) say the same.

### §S4 — Leftovers
The two skills drop project-specific examples (`NAI`/`Nai`, `vidushi`/`vidushi-t<N>` as literal ids)
and satisfy the name/retired-tool gate CR-MDB-042 exempted them from: the exemption is removed.

## Acceptance criteria

- [ ] `init` writes `SANDESH_PROJECT` into `.env`: `PROJECT_NAME` with whitespace removed by default
      (`My Project` → `MyProject`), `--sandesh-project` overrides it, an id with whitespace is refused
      before anything is written; `--dry-run` shows it; `AGENTS.md`'s Identity section names it —
      proven by sandboxed `init` runs.
- [ ] `bootstrap` and `shutdown` read, in order, the `model-b` references, the project's `AGENTS.md`
      and `.env`, and `docs/memory/INDEX.md`; neither names an `ORCHESTRATOR-` note or `MEMORY.md`, and
      every project file they name is one a sandboxed `init` produces.
- [ ] Both take the Sandesh project from `SANDESH_PROJECT`, the own-run id from `ORCHESTRATOR_LABEL`
      (Track: `track<N>-<PROJECT_TOKEN>`), and the Crucible client from `PROJECT_STACKS`; neither names
      `python-crucible.py` as the client for every project.
- [ ] The fallback (no registry / missing key → `AGENTS.md` → ask once; missing index → skip) is
      stated and non-fatal.
- [ ] Neither infers the Track role from the working directory or a `/.worktrees/` toplevel.
- [ ] Neither recovers, repaints, drains or escalates a todo/task list; bootstrap reloads from the
      board, shutdown drains the plan's open cycles.
- [ ] The CR-MDB-042 name/retired-tool gate covers `bootstrap/` and `shutdown/` (exemption removed)
      and passes.
- [ ] Suite baselines re-measured and recorded in `AGENTS.md`.

## Non-goals

- No new scaffolded file.
- No hand-edit of any project's `.env`. Only the generic template changes; a project scaffolded
  before this CR gets the key from `init`'s template when it is re-scaffolded, or relies on the
  fallback (§S2).
- No ruling on where a harness keeps its own agent memory; the skills name project files only.
- Telling Crucible Mainline on thread #1392 happens at merge (a notification, not an AC); the new
  text reaches `~/.agents/skills/` at the next reinstall (release step).
