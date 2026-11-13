# CR-MDB-106 — `init --register` registers the project on the board

**Status:** PENDING — **SEED, not the finished spec** (filed 2026-11-13 by the user's ruling, answering
Crucible #1611). Gap analysis and the spec happen in order when this CR starts. Pre-review: due (it builds on
another project's surface, Crucible's `project-create`).
**Type:** feature (`modelb-axi init`)
**Priority:** P1 — release 1.0.0, wave 2 (user 2026-11-13; board-authoritative: read `queue`).
**Depends on:** Crucible 0.4.0 in production (CR-CRU-230, `project-create`); held, like CR-MDB-083 and
CR-MDB-099, until it is installed.
**Labels:** init, scaffold, crucible, registry
**Design reference:** PRD-model-b-rationalization D3.1 (the registry, amended by CR-MDB-043); CR-MDB-043
§S2 (`CRUCIBLE_PROJECT_KEY` empty until the project is registered); CR-MDB-057 §S3 (the `project-meta`
Setup task); Model B's request #1517 and Crucible's answer #1611.

## Context

A new project cannot add itself to the board through Model B today:

- `modelb-axi init --register` parses but refuses before any write: `run_init` raises `ScaffoldError`
  ("live registration is not implemented in scaffold v1"), pinned by `tests/test_scaffold.py`'s VERIFY F1
  test (~L1379–1421).
- The scaffolded `AGENTS.md` Setup section (`_render_agents_md`'s setup text, `scaffold.py` ~L785–850)
  tells the user to register the project in Crucible and paste the key into `.env` by hand, then register
  the orchestrator and mirror `.env` with `project-meta --set`.

Model B asked Crucible for a client verb (#1517, 2026-11-07) and promised a CR implementing
`init --register` on it. Crucible answered (#1611, 2026-11-13): CR-CRU-230 is merged to Crucible's develop
(`36ac255c`) and ships in 0.4.0. Every client gains:

```text
<stack>-crucible.py project-create --project-dir <root> --name <display name> --token <token> \
  --agent <ORCHESTRATOR_LABEL> [--acronym <ACRO>] [--type backend|frontend] [--set KEY=VALUE ...] [--write-env]
```

- It creates the project and returns `projectKey` (with `created`, `source: token|env`, `name`, `metadata`,
  `envWritten`).
- It is idempotent by token: the key is uuid5 of the token, so a re-run returns the same project. If
  `<root>/.env` already holds a key the board knows, that project is used; a different stored
  `PROJECT_TOKEN` is refused (`project-token-mismatch`).
- `--write-env` writes `CRUCIBLE_PROJECT_KEY` only into an empty or missing line, byte-preserving.
- It seeds `PROJECT_TOKEN`, `PROJECT_ACRONYM` (with `--acronym`) and each `--set` in the same call.
- It registers `--agent` as the project's `ORCHESTRATOR`; an agent already there under another role, or
  bound to a cycle, is refused.
- Errors are `ok: false` envelopes (exit 1, with `error`, `help` and a warning code); an unreachable board
  is one, so `init` can warn and carry on.
- `--project-dir` is required (never resolved from the working directory); the project's `crucible.toml`
  picks the board. The token must match `^[a-z0-9][a-z0-9-]*$`, the acronym `^[A-Z][A-Z0-9]*$`.

## Scope (seed)

1. **`init --register` creates the project on the board,** through the client the project's stack resolves
   in Crucible's installed manifest, with `project-create --project-dir <target> --name --token --acronym
   --agent <ORCHESTRATOR_LABEL> --write-env`, and seeds the registry's non-secret keys (`--set`) in the
   same call, so the orchestrator's later `register` and `project-meta` steps are not needed for a new
   project.
2. **A board that is down or refuses is a warning, not a failure.** `init` reports the envelope's `error`
   and `help`, leaves `CRUCIBLE_PROJECT_KEY` empty, and the Setup section keeps its manual step as the
   fallback.
3. **The Setup section follows the outcome:** with the key written, the registration and `project-meta`
   tasks are rendered done (or left out); without it, the manual steps stay, with `project-create` as the
   route instead of pasting a key by hand.
4. **The guards move with the behaviour:** the VERIFY F1 test (the refusal) is replaced by tests of the
   new behaviour, and the `--register` help text says what it does.

## To measure at gap analysis

- Crucible 0.4.0's released `project-create` against #1611 (flags, envelope fields, warning codes).
- What `--register`'s help promises today ("Crucible/Sandesh registrations"): whether Sandesh's
  `setup` and `register` belong here is a question for the user, not scope.
- How `init` orders the call: after the `.env` and `crucible.toml` are written (the verb reads both),
  before or after the initial commit, and under `--dry-run` (which writes nothing and calls nothing).
- How the tests reach the client without a board: a stub client in the sandbox, as the other client-reading
  tests do.
- Which tests pin the Setup section's registration wording, and `test_project_registry_schema`'s flag list.
- The score (5 points filed) and the behaviour units.
