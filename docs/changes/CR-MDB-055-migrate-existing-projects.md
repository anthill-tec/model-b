# CR-MDB-055 — `modelb-axi migrate`: bring an existing project under Model B

**Status:** PENDING — **SEED, not the finished spec** (filed 2026-10-03 into release 1.1.0, wave 3).
The design is discussed with the user at this CR's gap analysis; the spec is written then.
**Type:** feature (CLI, scaffold)
**Priority:** P2 — release 1.1.0, wave 3.
**Depends on:** CR-MDB-050 (both change `init`'s handling of an existing target), CR-MDB-068 (the
release workflow templates) and CR-MDB-082 (`migrate` on a governed project); board-authoritative: read `queue`, not this line
**Labels:** cli, scaffold, migration, schema
**Design reference:** PRD D9/D10 (D10 amended 2026-10-03); `DN-scaffold-packaging.md` §10;
DN-multi-harness-deploy-model §D25;
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

`migrate` exists after CR-MDB-082 for a project Model B already governs, which it brings up to the
installed Model B by re-rendering what Model B owns. This CR adds its other half — a project Model B
does not yet govern — bringing it up to what `init` would have produced, losing nothing, and ending
with CR-MDB-082's renders:
1. **Inventory** the project against the schema (`project_schema.toml`) and the files `init` scaffolds,
   and report what is present, missing, or differs.
2. **Plan, then write.** `--dry-run` prints the full plan and writes nothing; the real run validates
   everything before the first write, writes atomically, and commits only what it wrote.
3. **Add, never replace — incrementally, for every file it touches** (`.env`, `.envrc`, `.gitignore`,
   `AGENTS.md`): Model B's lines sit in a marked managed block that a re-run updates and nothing else;
   the project's own lines are never altered or removed. An `.envrc` that loads the project's own
   environment keeps it, with `dotenv` added only when missing. A key present with a different value is
   reported, never overwritten. A secret already in `.env` stays where it is, with a note that Model B
   keeps secrets in `.env.local`. The `AGENTS.md` sections `init` renders (Setup, design references,
   lean-ctx) go into the managed block without touching hand-written text;
   `docs/memory/` seeded where absent; agents, hooks and the permission policy rendered under the
   existing ownership rules.
4. **What it cannot move, it lists:** `~/.claude` memory notes and `ORCHESTRATOR-` notes to fold into
   `docs/memory/` or the knowledge store, README queue rows to file on the board (never `queue-file`),
   Claude-era hook wiring to retire. Model B never writes `~/.claude`.
5. **Dogfood:** Model B is the first project migrated; its hand-made additions are the acceptance check.
6. **Release files, so every Model B project releases the same way:** the `CHANGELOG.md` skeleton
   (CR-MDB-058) where none exists, and `.github/workflows/release.yml` rendered from the project's
   stacks by CR-MDB-068's templates, under the same ownership rules as `init`. A project with its own
   release or CI workflow keeps it; `migrate` reports it beside what the template would render.
7. **The skills' older-project paths point at `migrate`.** The by-hand steps the skills describe for a
   project scaffolded before a feature existed (bootstrap Step 1's `SANDESH_ADDRESS`/`.envrc`, which today
   warns that re-running `init` overwrites the project; orchestration-common's older-project notes) name
   `migrate` instead.
8. **The dependency-services scripts** (DN §D25, CR-MDB-074): `migrate` drops Model B's service
   scripts into the project's own folder and adds the empty services section to its configuration, as
   `init` does at scaffold time, never touching services the project has already declared. A project
   that brings its services up by hand-written skills or scripts keeps them; `migrate` reports them as
   candidates to declare.

Ruled 2026-10-03 (`DN-scaffold-packaging.md` §10, PRD D10 amended): `migrate` takes `init`'s identity
and shape flags, only for values the project does not record, and `init`'s `--dry-run`, `--no-commit`,
`--yes`, `--force-managed` and `--modelb-home`; the project is the current directory, `--target DIR`
overrides it, for `init`, `migrate` and `agents` alike (aligning all three is in this CR's scope).

Open design questions for the gap analysis: the managed block's marker for each file's syntax; the
monorepo shape; how a project's existing release or CI workflow
is brought to the template (reported only, replaced on confirmation, or adopted as hand-edited).
