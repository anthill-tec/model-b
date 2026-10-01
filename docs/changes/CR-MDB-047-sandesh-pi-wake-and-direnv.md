# CR-MDB-047 — Sandesh's Pi extension is the wake loop; direnv loads the project environment

**Status:** PENDING (filed 2026-09-27; re-scoped for Sandesh 0.4.0; gap analysis and pre-review pending)
**Type:** refactor (installer requirements, scaffold, schema, skills, Pi package)
**Priority:** P1 — release 1.0.0, wave 2.
**Depends on:** — (sequenced first in the remaining wave: the wake path is used every run)
**Labels:** sandesh, wake, direnv, scaffold, installer, pi-package
**Design reference:** DN-multi-harness §D20 (2026-09-27, amended for Sandesh 0.4.0); PRD D10 (the installer detects the tools,
the scaffold sets each project up); PRD D3.1 (the schema-driven registry)

## Context

Model B wakes an orchestrator through its own watcher: the `sandesh-watcher` extension and the
`/watcher` command in `@anthill-tec/modelb-pi`. The skills also rule that a watcher which exits is
relaunched in the same turn. `@anthill-tec/sandesh-pi` 0.4.0 (with the `sandesh` CLI 0.4.0)
carries a supervised wake watcher. A tool call starts it, defaulting to `$SANDESH_ADDRESS` and
`$SANDESH_PROJECT` from the process environment. It relaunches itself after every wake and stops at
session shutdown, on a terminal exit, or when stopped by address.

Nothing loads a project's `.env` into that environment. The documented `set -a; . ./.env` idiom is
POSIX-only and fails on fish.

## Scope (from §D20; the gap analysis and pre-review complete it before approval)

- **§S1 — The installer.**
  - `sandesh-pi` becomes tier-1 required.
  - The `sandesh` probe carries a ≥ 0.4.0 version floor.
  - The `watcher` requirement row is retired.
  - `direnv` is declared a tool the installer probes, with its shell hook as the remediation.
- **§S2 — `modelb-axi init`.**
  - It writes an `.envrc` containing `dotenv` next to each `.env` it writes.
  - The schema gains `SANDESH_ADDRESS`, the Mainline address by default.
  - The setup task names (in the queue README until CR-MDB-048 moves it to the scaffolded
    `AGENTS.md`) installing direnv, its shell
    hook, `direnv allow`, and a Track's `env SANDESH_ADDRESS="Track <N> - <Project>" pi`.
- **§S3 — The skills.**
  - Bootstrap checks that the wake identity is in the environment, and says why when it is not:
    direnv not loaded, or the variables unset. It registers the role's address, starts Sandesh's wake
    watcher for it, and confirms with `sandesh status`. It reads the Tracks' liveness from
    `addressbook --format toon`.
  - The orchestrator only fetches after a wake. On a stop notice it checks `status`, and either
    restarts the watcher or reports why it can't.
  - The relaunch-on-exit rule is removed.
  - Shutdown stops its watcher by address, then unregisters it.
  - `sandesh.md` and the orchestration rules follow.
- **§S4 — `@anthill-tec/modelb-pi`** drops the watcher extension and `/watcher`, keeping worktree
  isolation.

## Acceptance criteria

To be written with the gap analysis (CR-MDB-046's Dimensions 8–10) and the pre-review, then
approved by the user before `plan-file`.

## Non-goals

- Sandesh's diagnostic for an identity in `./.env` that is not exported: Sandesh's CR.
- Writing the user's shell configuration, or running `direnv allow` on the user's behalf.
