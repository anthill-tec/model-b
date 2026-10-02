# CR-MDB-048 — The Crucible board holds the queue and execution state; the queue README is retired

**Status:** PENDING (filed 2026-09-27; gap analysis 2026-10-02; pre-review pending)
**Type:** refactor (skills, scaffold, conventions)
**Priority:** P1 — release 1.0.0, wave 2.
**Depends on:** CR-MDB-046 (its gap-analysis dimensions and pre-review apply to this CR)
**Labels:** queue, crucible, scaffold, conventions
**Design reference:** PRD D3.2 and D10.2 (AMENDED 2026-09-27; rulings 1–6 of 2026-10-02)

## Context

`docs/changes/README.md` is Model B's queue. It holds the CR table (CR / Title / Wave / Depends-on),
four header slots (Design contract, Evidence base, Ontology, Target release) and a dated Notes log.
`modelb-axi init` scaffolds one into every project, and that one also carries the project's setup
tasks: the Crucible registration and, in multi mode, the Sandesh and direnv setup. The skills tell
the orchestrator to maintain it.

The Crucible board already carries everything the table does:
- `cr-plan` records a CR's title, release and wave;
- `cr-depends` records its dependencies, and `wave-sequence` its order;
- `plan-file` and the `cycle-*` verbs record its plan and cycles;
- `milestone` records its milestones, and `cr-close` its merge;
- `cr-supersede` and `cr-void` record what replaces or ends a CR, and `release-propose` a release.

No skill documents the queue verbs, so without the README nothing tells an orchestrator how a CR
reaches the board. Model B's own README has grown to over 1,150 lines.

## Scope

### §S1 — The skills

Every skill directs the queue and the execution state to the board, and none names `queue-file`,
a queue row or the queue README as a workflow step.

- **`crucible` skill — a queue-verbs section.** It documents `queue` (read the registered CRs),
  `next`, `cr-plan`, `cr-depends`, `wave-sequence`, `cr-supersede`, `cr-void` and `release-propose`:
  what each records, that each is an orchestrator verb taking `--agent`, and that `cr-plan` with no
  `--release` lists the live proposals instead of guessing (release membership is the user's call).
- **`cr-authoring`:**
  - The CR row in "Document types" names the spec file and the board, not a queue README.
  - **Filing a CR** (replacing "The CR queue — structure only"): write the spec, then `cr-plan`
    (title, release, wave), `cr-depends` and `wave-sequence`. Allocate the next id from the board's
    `queue` and the spec files in `docs/changes/`. Supersession and voiding use `cr-supersede` and
    `cr-void`. When a spec's H1 changes, re-post its title with `cr-plan`, so the spec and the board
    agree. Release membership, waves, the release boundary and "a release is not a CR" keep their
    rules, stated against the board.
  - **Where the rest goes:** a ruling goes to the PRD or a DN, a merge to `cr-close` and a milestone
    label, a follow-up to a CR filed on the board. This replaces "the queue (structure + dated
    footer Notes)" wherever the skill names it.
  - **Closing a CR:** where board-tracking is absent, close-out is the spec's `**Status:**` flip
    alone.
  - **"CR vs task"** and **patch CRs** name filing on the board instead of a queue row.
  - **`docs/` layout:** `docs/changes/` holds the specs only.
- **`model-b` skill:** § 1's queue idiom (item 2) states that the board holds the queue and the
  execution state, with the specs in `docs/changes/`; the description and role table say "the
  board's CR queue" or equivalent, never the README.
- **`orchestration-mainline`:** Mainline owns the board's queue (filing, `cr-depends`,
  `wave-sequence`), not a queue README; "write spec + queue row" becomes "write the spec, file it
  on the board".
- **`orchestration-common`:** the design phase's edits and the GC principle name the board, not a
  queue row.
- **`bootstrap` and `shutdown`:** an empty `CRUCIBLE_PROJECT_KEY` sends the orchestrator to the
  Setup section of the project's `AGENTS.md` — or, in a project scaffolded before this CR, to its
  queue README's setup tasks.
- **Memory templates:** `java-orchestration` stops calling `docs/changes/` the CR queue.

### §S2 — The scaffold

- **No queue README.** `init` writes no `docs/changes/README.md`. It writes `docs/changes/.gitkeep`
  so the specs' directory exists. `plan_files`, `--dry-run` and the envelope's `emitted` list match.
- **The root `AGENTS.md` gains a Setup section** carrying the README's setup tasks as they stand:
  the scaffold line, the Crucible registration (its absent-tool remediation first, CR-MDB-045), in
  multi mode the Sandesh and direnv task (CR-MDB-047), and the `REPO_OWNER` check. It sits alongside
  the envelope's `setup_required`, which is unchanged. A sub-project's `AGENTS.md` has none.
- **The header slots** become lines of the root `AGENTS.md`: Design contract and Evidence base as
  fill-in lines, and Ontology citing `~/.agents/skills/model-b/SKILL.md`. The target release is not
  scaffolded.
- **The Workflow rules** state that the Crucible board holds the queue and the execution state and
  `docs/changes/` holds the specs, and point the manual registrations to the Setup section.
- **Readers:** `init`'s stderr note after a write names `AGENTS.md`'s Setup section. The
  `project_schema.toml` `readers` and `step` entries that name the queue README name `AGENTS.md`'s
  Setup section instead.

### §S3 — Model B's own records

- **Model B's README** keeps its content and gains a header: it is read-only history, frozen at
  CR-MDB-048's merge, and the queue and execution state are on the Crucible board.
- **Model B's `AGENTS.md`:** the `docs/changes/` row and the Important-files line say the README is
  frozen history and the board holds the queue.
- **DN §D20** names `AGENTS.md`'s Setup section instead of the queue README's setup task.
- **Tests** that pin the scaffolded README move to the Setup section and the new `AGENTS.md` lines;
  each migration is listed by id. Tests that read Model B's own README as history keep passing.

## Acceptance criteria

- [ ] **`crucible` skill** has a queue-verbs section naming `queue`, `next`, `cr-plan`, `cr-depends`,
      `wave-sequence`, `cr-supersede`, `cr-void` and `release-propose`, each with what it records;
      `cr-plan` without `--release` lists proposals and never guesses.
- [ ] **`cr-authoring`** files a CR as spec → `cr-plan` → `cr-depends` → `wave-sequence`; allocates
      ids from `queue` and the spec files; supersedes and voids with the verbs; re-posts a changed
      title with `cr-plan`; sends rulings to the PRD or a DN, merges to `cr-close` plus a milestone,
      follow-ups to a filed CR; closes a board-absent CR by the `**Status:**` flip alone; lists
      `docs/changes/` as specs only.
- [ ] **No shipped skill, template, stack file or memory template** names `queue-file`,
      `docs/changes/README.md`, a queue row or the queue README as a step — except bootstrap's and
      shutdown's older-project case.
- [ ] **`model-b`, `orchestration-mainline`, `orchestration-common`** state the board as the queue's
      home, and Mainline files CRs on it.
- [ ] **`bootstrap` and `shutdown`** send an unregistered project to `AGENTS.md`'s Setup section,
      and an older project to its README's setup tasks.
- [ ] **`init`** (standalone and monorepo, solo and multi, `--dry-run` included) writes no
      `docs/changes/README.md`, writes `docs/changes/.gitkeep`, and lists exactly what it writes.
- [ ] **The root `AGENTS.md`** has one Setup section carrying every setup task the README carried,
      with the same absent-tool remediations and the multi-mode Sandesh/direnv task; no sub-project
      `AGENTS.md` has one. It carries Design contract, Evidence base and Ontology lines, the
      Ontology citing `~/.agents/skills/model-b/SKILL.md`. Its Workflow rules name the board and
      the Setup section, not the README.
- [ ] **`init`'s stderr note** and **`project_schema.toml`** name the Setup section, not the README.
- [ ] **Model B's README** keeps all its content under a frozen-history header pointing to the
      board; `AGENTS.md` and DN §D20 say the same.
- [ ] **Gates that hold:** every migrated test listed by id; the suites that read Model B's README as
      history pass; the CR-042 triage headings and `HEADING_RENAMES` unchanged; §D18 tool-name
      gates; `generator/build.py --check`; baselines re-measured in `AGENTS.md`.

## Non-goals

- Changing Crucible's verbs, or its `queue` registry.
- Requiring Crucible: a project without it keeps the board-absent close-out.
- Migrating a project scaffolded before this CR: its README stays as its own history.
- The roundhouse root's own `docs/changes/README.md` (a root session's).
- Rewriting closed specs, `archive/` or `audits/`.
