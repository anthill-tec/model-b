# CR-MDB-043 — Schema-driven project registry

**Status:** PENDING (filed 2026-09-26)
**Type:** refactor
**Priority:** P1 — release 1.0.0, wave 2. CR-MDB-041's skills read project settings by schema key.
**Depends on:** —
**Labels:** scaffold, registry, schema
**Design reference:** PRD D3.1 (AMENDED 2026-09-26: the registry is schema-driven; values are the
project's, local and authoritative; Crucible mirror later); PRD D10 (what `init` scaffolds)

## Context

`modelb-axi init` renders a project's settings from keys hard-coded in `modelb_axi/scaffold.py`:
`_render_env` writes `PROJECT_NAME`, `PROJECT_TOKEN`, `PROJECT_ACRONYM`, `ORCHESTRATOR_LABEL`
(derived by `_orchestrator_label`), `REPO_OWNER` and `PROJECT_STACKS`; `_render_env_local` writes
`CRUCIBLE_PROJECT_KEY=`; the `init` flags (`--name`, `--token`, `--acronym`, `--mode`, `--owner`,
`--stacks`, …), the "missing required value(s)" check and `--dry-run` each restate that key set.
Nothing declares the set once, nothing says which skill reads which key, and adding a key (the
Sandesh project id, which no current key yields because Sandesh ids are case- and space-sensitive)
means editing each of those places.

## Scope

### §S1 — The schema
A project-settings schema ships with Model B (a TOML asset under `skills-src/` or beside the
generator; it must ship in the wheel — `pyproject.toml` force-include). One entry per key:
`name`, `description`, `required` (bool), `file` (`.env` committed / `.env.local` gitignored),
`source` (`ask` with its `init` flag; `derive` with a named rule and its input keys; `capture` —
filled by a named step such as Crucible registration), `validate` (a named rule), `readers` (the
skills or tools that read it). The schema carries no project value, only rules. Keys: today's seven
plus `SANDESH_PROJECT` (`derive`: `PROJECT_NAME` with whitespace removed; overridable by an `ask`
flag `--sandesh-project`; `validate`: non-empty, no whitespace).

### §S2 — The generator reads the schema
`init` builds its required-value check, its `--dry-run` report and the rendered `.env` /
`.env.local` from the schema; `_render_env`/`_render_env_local` keep no key list of their own, and
the derive rules (`ORCHESTRATOR_LABEL`'s mode-aware rule, `SANDESH_PROJECT`) are named functions the
schema refers to. The `init` flags stay as they are (argparse remains the CLI); a test proves every
`ask` key has its flag and every flag that sets a key is in the schema. `modelb-axi agents` reads
`PROJECT_STACKS` through the same schema reader. `AGENTS.md`'s "Identity & naming" section lists the
keys from the schema.

### §S3 — Gates
- Every registry key named in `skills-src/`, `generator/templates/` and `hooks-src/` exists in the
  schema (Crucible's imported bundles are exempt: their keys are Crucible's contract).
- No shipped skill, template or schema entry carries a project value (a project name, token, acronym,
  Sandesh id or project key literal).

## Acceptance criteria

- [ ] The schema asset exists, ships in the wheel, and lists the eight keys with every field above.
- [ ] `init` output for the same inputs is byte-identical to today's except for the added
      `SANDESH_PROJECT` line (proven on sandboxed `init` runs, solo and multi).
- [ ] `SANDESH_PROJECT` defaults to `PROJECT_NAME` without whitespace (`My Project` → `MyProject`),
      `--sandesh-project` overrides it, and an id with whitespace is refused before anything is
      written; `--dry-run` shows it.
- [ ] Adding a key to the schema alone makes `init` require/derive and render it — proven by a test
      that feeds the generator a fixture schema with an extra key.
- [ ] The §S3 gates exist, with detector fixtures, and pass.
- [ ] Suite baselines re-measured in `AGENTS.md`.

## Non-goals

- No edit of any existing project's `.env`: projects scaffolded earlier gain new keys on re-scaffold
  or through the skills' fallback (CR-MDB-041).
- No Crucible metadata mirror in this CR: it needs a Crucible project-metadata surface first (requested
  over Sandesh); `init --register` mirrors the values once that exists.
- No change to the `init` flag names or to the committed/gitignored split of the two files.
