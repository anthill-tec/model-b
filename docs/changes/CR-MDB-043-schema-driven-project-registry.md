# CR-MDB-043 — Schema-driven project registry

**Status:** PENDING (filed 2026-09-26; gap analysis 2026-09-26)
**Type:** refactor + fix
**Priority:** P1 — release 1.0.0, wave 2. CR-MDB-041's skills read project settings by schema key,
and every project `init` scaffolds today puts its Crucible project key where Crucible's client never
looks.
**Depends on:** —
**Labels:** scaffold, registry, schema
**Design reference:** PRD D3.1 (AMENDED 2026-09-26: the registry is schema-driven; values are the
project's, local and authoritative; Crucible mirror later); PRD D10 (what `init` scaffolds)

## Context

`modelb-axi init` renders a project's settings from keys hard-coded in `modelb_axi/scaffold.py`:
- `_render_env` writes `PROJECT_NAME`, `PROJECT_TOKEN`, `PROJECT_ACRONYM`, `ORCHESTRATOR_LABEL`
  (derived by `_orchestrator_label` from `--mode` and the token), `REPO_OWNER` and `PROJECT_STACKS`
  into the committed `.env`; a monorepo sub-project's `.env` gets the same keys without
  `PROJECT_STACKS`;
- `_render_env_local` writes `CRUCIBLE_PROJECT_KEY=` into the gitignored `.env.local`;
- `_REQUIRED_FLAGS` (the "missing required value(s)" check), `--dry-run`, `_render_agents_md`'s
  "Identity & naming" section and `run_agents` (`_read_env_value(..., PROJECT_STACKS)`) each restate
  part of that set.

Nothing declares the set once. Adding a key means editing each place.

**Defect.** Crucible's released client reads `CRUCIBLE_PROJECT_KEY` from `<project-dir>/.env` only
(`~/.crucible/clients/python-crucible.py:125–140`) and exits when it is missing. `init` writes it to
`.env.local`, and the queue README's setup task tells the user to fill it there, so every client
call in a freshly scaffolded project fails. PRD D3.1 already places the projectKey in `.env`.

**Readers.** Crucible's clients read the `.env` file. Sandesh reads no file: its CLI and its Pi
extension take the project from `--project` or `$SANDESH_PROJECT` (`sandesh/cli.py:33`). The
orchestrator skills therefore read `SANDESH_PROJECT` from `.env` and pass `--project` explicitly.
Exporting it into a session's environment (for the Sandesh Pi extension's own wake loop) belongs to
the later CR that adopts that extension.

## Scope

### §S1 — The schema
`modelb_axi/project_schema.toml`, package data shipped in the wheel, holds one entry per key:
- `name` and `description`;
- `required` (bool);
- `file`: `.env` (committed) or `.env.local` (gitignored);
- `scope`: `root`, or `root+sub` for keys a monorepo sub-project's `.env` also carries;
- `source`: `ask` (with its `init` flag); `derive` (a named rule and its inputs, which are keys or
  `init` inputs such as `mode`); or `capture` (a named manual or tool step, e.g. Crucible
  registration). A `derive` key may name an `override` flag;
- `validate`: a named rule;
- `readers`: the skills or tools that read the key.

It carries rules only, never a project's value.

Keys:
- today's seven;
- `CRUCIBLE_PROJECT_KEY`, moved to `file = ".env"` with `source = "capture"` (Crucible registration),
  rendered empty;
- `SANDESH_PROJECT`, `derive` from `PROJECT_NAME` with whitespace removed, `override` flag
  `--sandesh-project`, validated as non-empty with no whitespace.

### §S2 — The generator reads the schema
`init` builds these from the schema:
- its required-value check;
- the values it derives and validates;
- its `--dry-run` report;
- the rendered `.env` / `.env.local` of the root and of each sub-project.

`_render_env` and `_render_env_local` keep no key list. The derive and validate rules are named
functions the schema refers to, and an unknown rule name is a load-time error.

The CLI stays argparse: every `ask` or `override` key has its flag, and a test proves the schema and
the parser agree.

`run_agents` reads `PROJECT_STACKS` through the schema reader. The queue README's setup task
names `.env` for the project key. `AGENTS.md`'s "Identity & naming" section names `SANDESH_PROJECT`.

### §S3 — Gates
- Every registry key named in `skills-src/` (Crucible's imported bundles exempt: their keys are
  Crucible's contract), `generator/templates/` and `hooks-src/` is declared in the schema.
- No shipped skill, template or the schema carries a project value: no literal project name,
  token, acronym, Sandesh id or project key.

## Acceptance criteria

- [ ] The schema ships in the wheel and declares the nine keys with every field in §S1.
- [ ] For the same inputs, `init` output (solo and multi, standalone and monorepo, sandboxed) matches
      today's except for exactly these differences:
      - `SANDESH_PROJECT` in each `.env`, per its scope;
      - `CRUCIBLE_PROJECT_KEY=` moved from `.env.local` to the root `.env`;
      - the queue README's setup task naming `.env`;
      - `AGENTS.md` naming `SANDESH_PROJECT`.
- [ ] `SANDESH_PROJECT` behaves as specified:
      - it defaults to `PROJECT_NAME` without whitespace (`My Project` → `MyProject`);
      - `--sandesh-project` overrides it;
      - an id containing whitespace is refused before anything is written;
      - `--dry-run` shows it.
- [ ] A freshly scaffolded project, once its key is filled in `.env`, resolves through Crucible's
      released client, proven out of process with a stub server or a verb that reads only the key.
- [ ] Adding an entry to a fixture schema alone makes `init` require or derive, validate and render
      it. Proven with the generator fed a fixture schema.
- [ ] The §S3 gates exist, with detector fixtures, and pass.
- [ ] Suite baselines are re-measured in `AGENTS.md`.

## Non-goals

- No edit of any existing project's `.env`. Projects scaffolded earlier gain new keys when
  re-scaffolded, or through the skills' fallback (CR-MDB-041).
- No Crucible metadata mirror. It needs a Crucible project-metadata surface first (asked on thread
  #1399). `init --register` mirrors the values once that exists; today it remains the honest no-op.
- No exporting of registry values into a session's environment.
- No change to the `init` flag names, and no removal of `.env.local`: it stays the gitignored
  overlay, with no key from the schema today.
