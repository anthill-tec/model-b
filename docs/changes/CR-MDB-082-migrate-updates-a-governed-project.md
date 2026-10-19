# CR-MDB-082 — `migrate` brings a governed project up to the installed Model B

**Status:** PENDING — **SEED, not the finished spec** (filed 2026-10-19 into release 1.0.0, wave 2).
Gap analysis, the spec and its pre-review happen in order when this CR starts.
**Type:** feature (CLI, scaffold, project registry, bootstrap)
**Priority:** P1 — release 1.0.0, wave 2.
**Depends on:** none known; the board is authoritative: read `queue`, not this line.
**Labels:** cli, migrate, scaffold, registry
**Design reference:** DN-scaffold-packaging §10, rulings 5 and 6 (2026-10-19); PRD D10.

## Context

A project Model B governs has no single way to catch up with a newer Model B. `modelb-axi agents`
re-renders the agent definitions and the permission policy, `modelb-axi release-workflow` the release
workflow, and nothing re-renders the hook wiring after `init`. A project does not record which Model B
version last rendered it, so nobody can tell it is behind.

## Scope (seed)

1. **`modelb-axi migrate` on a governed project** (its `.env` holds the registry): re-render every
   artifact Model B owns at the installed version — the agent definitions and permission policy, the
   hook wiring, the release workflow — under the ownership rules (a marked file is Model B's, a
   hand-modified one is skipped unless `--force-managed`, an unmarked one is never written), with
   `--dry-run`, `--force-managed` and `--modelb-home`; the project is the current directory, `--target`
   overrides it. It reports each file changed, skipped or left. A project Model B does not govern is
   refused, naming what `migrate` will do for it in a later release (CR-MDB-055).
2. **The rendered-by version.** A registry key recording the Model B version that last rendered the
   project: `init` and `migrate` write it; `migrate` reports the move from the recorded version to the
   installed one.
3. **`bootstrap` says when the installed Model B is newer** than the project's recorded version, and
   names `migrate`.
4. **The skills' older-project steps** that tell the orchestrator to run `agents` or edit by hand after
   an upgrade name `migrate`.

## To measure at gap analysis

- Every artifact `init` renders that carries an ownership marker, and which already has a re-render
  path (`agents.render_project`, `hooks.compile_wiring`, the release-workflow renderer).
- The registry key's name and schema row (`project_schema.toml`, the `NOT_REGISTRY_KEYS` and
  stale-name gates), and how a project with no recorded version is treated.
- The flags `migrate` shares with `init` and `agents`, and the `--target` alignment of DN-scaffold-packaging
  §10 ruling 4 that this CR can already deliver for the verbs it touches.
- The re-score.
