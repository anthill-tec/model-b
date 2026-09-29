# CR-MDB-047 — Sandesh's Pi extension is the wake loop; direnv loads the project environment

**Status:** PENDING (filed 2026-09-27; design recorded, gap analysis and pre-review pending)
**Type:** refactor (installer requirements, scaffold, schema, skills, Pi package)
**Priority:** P1 — release 1.0.0, wave 2.
**Depends on:** CR-MDB-046 (its gap-analysis dimensions and pre-review apply to this CR)
**Labels:** sandesh, wake, direnv, scaffold, installer, pi-package
**Design reference:** DN-multi-harness §D20 (2026-09-27); PRD D10 (the installer detects the tools,
the scaffold sets each project up); PRD D3.1 (the schema-driven registry)

## Context

Model B wakes an orchestrator through its own watcher: the `sandesh-watcher` extension and the
`/watcher` command in `@anthill-tec/modelb-pi`. The skills also rule that a watcher which exits is
relaunched in the same turn. `@anthill-tec/sandesh-pi` now carries its own wake loop, which re-arms
itself after every wake, stops on shutdown or when the address is unregistered, and is armed from
`$SANDESH_PROJECT` and `$SANDESH_ADDRESS` in the process environment at Pi session start.

Nothing loads a project's `.env` into that environment. The documented `set -a; . ./.env` idiom is
POSIX-only and fails on fish.

## Scope (from §D20; the gap analysis and pre-review complete it before approval)

- **§S1 — The installer.**
  - `sandesh-pi` becomes tier-1 required.
  - The `watcher` requirement row is retired.
  - `direnv` is declared a tool the installer probes, with its shell hook as the remediation.
- **§S2 — `modelb-axi init`.**
  - It writes an `.envrc` containing `dotenv` next to each `.env` it writes.
  - The schema gains `SANDESH_ADDRESS`, the Mainline address by default.
  - The queue README's setup task names installing direnv, its shell hook, `direnv allow`, and a
    Track's `env SANDESH_ADDRESS="Track <N> - <Project>" pi`.
- **§S3 — The skills.**
  - Bootstrap checks that the wake identity is in the environment and that the addressbook shows the
    address listening. When it is not, bootstrap says why: direnv not loaded, or the variables unset.
    Bootstrap launches no watcher.
  - The relaunch-on-exit rule is removed.
  - Shutdown ends by unregistering its address, which stops the loop.
  - `sandesh.md` and the orchestration rules follow.
- **§S4 — `@anthill-tec/modelb-pi`** drops the watcher extension and `/watcher`, keeping worktree
  isolation.

## Acceptance criteria

To be written with the gap analysis (CR-MDB-046's Dimensions 8–10) and the pre-review, then
approved by the user before `plan-file`.

## Non-goals

- Sandesh's diagnostic for an identity in `./.env` that is not exported: Sandesh's CR.
- Writing the user's shell configuration, or running `direnv allow` on the user's behalf.
