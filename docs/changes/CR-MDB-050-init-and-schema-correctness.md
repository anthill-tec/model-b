# CR-MDB-050 — `init` and the project schema: re-runs, conditional keys and readers

**Status:** PENDING — **SEED, not the finished spec** (filed 2026-10-02 into release 1.1.0, wave 3).
Every item below is re-measured at gap analysis; the spec is written then.
**Type:** fix (scaffold, project schema)
**Priority:** P2 — release 1.1.0, wave 3.
**Depends on:** none (board-authoritative: read `queue`, not this line)
**Labels:** scaffold, schema, init
**Design reference:** PRD D10 (tools detected by the installer, read by `init`); CR-MDB-043 (the
schema-driven registry, `modelb_axi/project_schema.toml`)

## Scope (seed — the follow-ups gathered here)

1. **Re-running `init` with the commit step fails** (CR-MDB-048 VERIFY F7). On an already-scaffolded
   project `init` exits 3, and in the measured run it had already committed before failing (it fails
   on `git checkout -b develop`). Decide what a re-run commits, and make a failure leave no commit.
2. **A required key with `when` is demanded when its tool is absent.** A `when`-conditional key
   (e.g. `KNOWLEDGE_CATEGORY`, `when = "lean-ctx"`) must not be required when the tool is absent.
3. **The schema readers of `CRUCIBLE_PROJECT_KEY`.** Its `readers` name
   `~/.crucible/clients/<stack>-crucible.py`, `worktree-flow.py` and the `model-b` skill; check each
   against what actually reads the key today.
4. **The token-vs-acronym label rule.** Which identifiers derive from `PROJECT_TOKEN` and which from
   `PROJECT_ACRONYM` is stated inconsistently; settle the rule and make the schema and renderers follow it.
5. **`init` silently overwrites an existing project** (measured 2026-10-03 in a `/tmp` sandbox). Run on
   a repository with a hand-written `AGENTS.md` and a `.env` carrying an extra key, `init` exited 0,
   replaced both (the extra key and the hand-written rules were lost), and committed, with no warning.
   The ownership rules (managed markers) cover only the rendered agents, hooks and permission policy.
   `init` must refuse, before any write, a target where any file it would write already exists, and
   name `modelb-axi migrate` (CR-MDB-055) in the refusal; a target holding only files `init` does not
   write (`.git`, a README, a LICENSE) is still accepted (user ruling 2026-10-03, DN-scaffold-packaging §10).
6. **The stack-neutral memory template does not fit every stack.** `operational-commands.md`, which
   `init` seeds into every project's `docs/memory/`, is a Docker/MongoDB/Redis/Quarkus command sheet;
   Model B's own `docs/memory/` (seeded 2026-10-03 for the python stack) shows it is noise outside the
   Java stack. Decide whether it is a Java-family template or gets stack-neutral content.
