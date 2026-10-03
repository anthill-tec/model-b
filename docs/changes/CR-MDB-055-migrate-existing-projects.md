# CR-MDB-055 — `modelb-axi migrate`: bring an existing project under Model B

**Status:** PENDING — **SEED, not the finished spec** (filed 2026-10-03 into release 1.1.0, wave 3).
The design is discussed with the user at this CR's gap analysis; the spec is written then.
**Type:** feature (CLI, scaffold)
**Priority:** P2 — release 1.1.0, wave 3.
**Depends on:** CR-MDB-050 (both change `init`'s handling of an existing target; board-authoritative:
read `queue`, not this line)
**Labels:** cli, scaffold, migration, schema
**Design reference:** PRD D9/D10 (D10 amended 2026-10-03); `DN-scaffold-packaging.md` §10;
CR-MDB-043 (schema-driven registry); CR-MDB-041, CR-MDB-045, CR-MDB-047, CR-MDB-048
(the files `init` scaffolds and their readers)

## Context

`init` scaffolds a new project. It cannot take an existing one: run on a repository that already has an
`AGENTS.md` and a `.env`, it replaces both and commits (CR-MDB-050 item 5). Projects that predate
Model B's generated setup — the Claude-era manual setup (a `CLAUDE.md`, `~/.claude/projects/<slug>/memory/`
notes and an `ORCHESTRATOR-<Project>` note, a README queue) or a project scaffolded by an older
`init` — have to be brought in by hand. Model B itself is one: on 2026-10-03 its `docs/memory/INDEX.md`
and `KNOWLEDGE_CATEGORY` were added by hand, the "older projects" path the skills describe.

## Scope (seed)

A `migrate` verb that brings an existing project up to what `init` would have produced, losing nothing:
1. **Inventory** the project against the schema (`project_schema.toml`) and the files `init` scaffolds,
   and report what is present, missing, or differs.
2. **Plan, then write.** `--dry-run` prints the full plan and writes nothing; the real run validates
   everything before the first write, writes atomically, and commits only what it wrote.
3. **Add, never replace:** missing `.env` keys appended (existing keys and lines kept); the `AGENTS.md`
   sections `init` renders (Setup, design references, lean-ctx) added without touching hand-written text;
   `docs/memory/` seeded where absent; agents, hooks and the permission policy rendered under the
   existing ownership rules.
4. **What it cannot move, it lists:** `~/.claude` memory notes and `ORCHESTRATOR-` notes to fold into
   `docs/memory/` or the knowledge store, README queue rows to file on the board (never `queue-file`),
   Claude-era hook wiring to retire. Model B never writes `~/.claude`.
5. **Dogfood:** Model B is the first project migrated; its hand-made additions are the acceptance check.
6. **The skills' older-project paths point at `migrate`.** The by-hand steps the skills describe for a
   project scaffolded before a feature existed (bootstrap Step 1's `SANDESH_ADDRESS`/`.envrc`, which today
   warns that re-running `init` overwrites the project; orchestration-common's older-project notes) name
   `migrate` instead.

Ruled 2026-10-03 (`DN-scaffold-packaging.md` §10, PRD D10 amended): `migrate` takes `init`'s identity
and shape flags, only for values the project does not record, and `init`'s `--dry-run`, `--no-commit`,
`--yes`, `--force-managed` and `--modelb-home`; the project is the current directory, `--target DIR`
overrides it, for `init`, `migrate` and `agents` alike (aligning all three is in this CR's scope).

Open design questions for the gap analysis: how a hand-written `AGENTS.md` takes rendered sections
(markers or a managed region); the monorepo shape.
