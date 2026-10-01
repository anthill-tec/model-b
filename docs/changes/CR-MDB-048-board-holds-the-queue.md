# CR-MDB-048 — The Crucible board holds the queue and execution state; the queue README is retired

**Status:** PENDING (filed 2026-09-27; design recorded, gap analysis and pre-review pending)
**Type:** refactor (skills, scaffold, conventions)
**Priority:** P1 — release 1.0.0, wave 2.
**Depends on:** CR-MDB-046 (its gap-analysis dimensions and pre-review apply to this CR)
**Labels:** queue, crucible, scaffold, conventions
**Design reference:** PRD D3.2 and D10.2 (AMENDED 2026-09-27: the Crucible board holds the queue and
the execution state; `docs/changes/README.md` is retired as a tracker)

## Context

`docs/changes/README.md` is Model B's queue. It holds the CR table (CR / Title / Wave / Depends-on)
and a dated Notes log of rulings, merge records and follow-ups. `modelb-axi init` scaffolds one into
every project, and that one also carries the project's setup tasks: registering in Crucible, and the
Sandesh setup. The skills tell the orchestrator to maintain it.

The Crucible board already carries everything the table does:
- `cr-plan` records a CR's title, release and wave;
- `cr-depends` records its dependencies, and `wave-sequence` its order;
- `plan-file` and the `cycle-*` verbs record its plan and cycles;
- `milestone` records its milestones, and `cr-close` its merge.

Model B's own README has grown to 1,150 lines.

## Scope (from PRD D3.2; the gap analysis and pre-review complete it before approval)

- **§S1 — The skills.** They direct queue and execution state to the board, and name `queue-file` in
  no workflow step. This covers:
  - `cr-authoring`'s queue idiom;
  - `orchestration-common` and `orchestration-mainline`;
  - the `model-b` skill;
  - `bootstrap` and `shutdown`.

  Rulings go to the PRD or a DN, a merge to `cr-close` and a milestone, and a follow-up to a CR filed
  on the board.
- **§S2 — The scaffold.**
  - `init` writes no `docs/changes/README.md`.
  - Its setup tasks become a Setup section of the scaffolded `AGENTS.md`, alongside the envelope's
    `setup_required`. That section takes the README's setup tasks as they stand, including
    CR-MDB-045's absent-tool remediations and CR-MDB-047's direnv step.
  - `docs/changes/` is still created, for specs.
- **§S3 — Model B's own README** is frozen as read-only history, with a header pointing to the
  board. `AGENTS.md` and the tests that pin its rows or notes are migrated.

## Acceptance criteria

To be written with the gap analysis (CR-MDB-046's Dimensions 8–10) and the pre-review, then
approved by the user before `plan-file`.

## Non-goals

- Changing Crucible's verbs, or its `queue` registry.
- Rewriting closed specs, `archive/` or `audits/`.
