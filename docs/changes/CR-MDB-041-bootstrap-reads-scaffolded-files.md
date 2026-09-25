# CR-MDB-041 — Bootstrap and shutdown read the files `init` scaffolds

**Status:** PENDING (filed 2026-09-25 from Crucible Mainline's question, Sandesh #1392/#1393)
**Type:** fix
**Priority:** P1 — release 1.0.0, wave 2. Every Pi orchestrator runs these two skills at the start
and end of every session, and today they send it looking for files that do not exist.
**Depends on:** —
**Labels:** skills, bootstrap, shutdown, scaffold
**Design reference:** DN-multi-harness §D19 (session model); PRD D3.1 (the `.env` naming registry), D10 (what `init` scaffolds), D5 (the
project memory tier); DN-multi-harness §D14 (Pi only)

## Context

`bootstrap` (Step 0, Step 0.5) and `shutdown` (Step 0, Step 0.5) instruct the orchestrator to read
a project **`ORCHESTRATOR-<Project>` note** and a project memory index **`MEMORY.md`**, and to take
its Crucible own-run id "from `ORCHESTRATOR-<Project>` §Identity". Both names come from the Claude
Code era, where they lived under `~/.claude/projects/<slug>/memory/`. No Model B tool creates
either file, and no location is defined for a Pi project.

What `modelb-axi init` actually scaffolds (measured 2026-09-25, `--stacks python --mode solo`):
- `.env` — the naming registry: `PROJECT_NAME`, `PROJECT_TOKEN`, `PROJECT_ACRONYM`,
  `ORCHESTRATOR_LABEL`, `REPO_OWNER`, `CRUCIBLE_PROJECT_KEY` (D3.1);
- `AGENTS.md` — sections "Identity & naming (registry: `.env` at the project root)" and "Workflow
  rules", the project's deltas over the generic tiers;
- `docs/memory/INDEX.md` — "project memory index", listing the project-level memory slices (D5).

Crucible Mainline, bootstrapping under Pi, found no `ORCHESTRATOR-Crucible` note anywhere and asked
where the definitions live (#1392). The interim answer (#1393) was: read the project `AGENTS.md` +
`.env` as the note, and the project memory index as `MEMORY.md`.

Occurrences (skills-src, 2026-09-25): `bootstrap/SKILL.md:27,36,65,87,89,94`;
`shutdown/SKILL.md:55,75,76`; `memory-templates/rust-orchestration.md:7` (names the NAI project's
`ORCHESTRATOR-NAI` note).

## Scope

### §S1 — Name the scaffolded files
In `skills-src/bootstrap/SKILL.md` and `skills-src/shutdown/SKILL.md`:
- the "project `ORCHESTRATOR-<Project>` note" becomes the project `AGENTS.md` (its "Identity &
  naming" and "Workflow rules" sections) and `.env`;
- the "project memory index `MEMORY.md`" becomes `docs/memory/INDEX.md`, the project memory index;
- the project and ids are resolved from `.env`: `<Project>` from `PROJECT_NAME`, the orchestrator's
  Crucible own-run id from `ORCHESTRATOR_LABEL` (replacing "from `ORCHESTRATOR-<Project>`
  §Identity; NAI");
- a project that predates `init` (no `.env` / no `docs/memory/INDEX.md`) is told what to read
  instead in one sentence: its `AGENTS.md`; nothing is an error.

`memory-templates/rust-orchestration.md:7` stops naming another project's private note; it points
at the project's own `AGENTS.md`.

**Track detection.** `bootstrap` (Step 0, role fallback 2) and `shutdown` (Step 0.1) recognise a
Track by `git rev-parse --show-toplevel` ending in `/.worktrees/<cr>`. Since CR-MDB-039 (DN
§D19) a Track's session cwd stays in the main tree, so that never matches. The fallback becomes the
session's Sandesh address (`Track <N> - <Project>`) or the carried context. A worktree path is not a
role signal.

### §S2 — The gate
A test asserts, over `skills-src/`:
- no `ORCHESTRATOR-<` / `ORCHESTRATOR-NAI` note and no `MEMORY.md` is named;
- every project file `bootstrap` and `shutdown` tell the orchestrator to read (`AGENTS.md`, `.env`,
  `docs/memory/INDEX.md`) is one that `modelb-axi init` scaffolds — proven by a sandboxed `init`;
- `bootstrap` names `PROJECT_NAME` and `ORCHESTRATOR_LABEL` as the sources of the project and the
  own-run id.

## Acceptance criteria

- [ ] `bootstrap` and `shutdown` name `AGENTS.md`, `.env` and `docs/memory/INDEX.md` where they
      named `ORCHESTRATOR-<Project>` and `MEMORY.md`; no shipped skill or memory template names
      either old file.
- [ ] `bootstrap` resolves `<Project>` from `PROJECT_NAME` and the own-run id from
      `ORCHESTRATOR_LABEL` in `.env`.
- [ ] The pre-`init` fallback is stated and treats a missing file as non-fatal.
- [ ] Neither skill infers the Track role from the working directory or a `/.worktrees/` toplevel;
      the fallback is the Sandesh address or the carried context.
- [ ] The §S2 gate exists, with detector fixtures, and fails on today's `skills-src/`.
- [ ] Suite baselines re-measured and recorded in `AGENTS.md`.
- [ ] Crucible Mainline is told on thread #1392 when this merges (a release step for the deployed
      copy: the new text reaches `~/.agents/skills/` at the next reinstall).

## Non-goals

- No new scaffolded file. The content already exists in `AGENTS.md`, `.env` and
  `docs/memory/INDEX.md`.
- No ruling on where a harness keeps its own agent memory (Crucible's user ruled lean-ctx knowledge
  for theirs); the skills name project files only.
