# CR-MDB-048 — The Crucible board holds the queue and execution state; the queue README is retired

**Status:** PENDING (filed 2026-09-27; gap analysis and pre-review 2026-10-02)
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
- `cr-depends` records its dependencies, and `wave-sequence` its order and lane;
- `plan-file` and the `cycle-*` verbs record its plan and cycles;
- `milestone` records its milestones, and `cr-close` its merge;
- `cr-supersede` and `cr-void` record what replaces or ends a CR, and `release-propose` a release.

No skill documents the queue verbs, so without the README nothing tells an orchestrator how a CR
reaches the board. Model B's own README has grown to over 1,150 lines.

## Scope

### §S1 — The skills

Every skill directs the queue and the execution state to the board, and none names `queue-file`,
a queue row, the Notes log or the queue README as a workflow step. **Every CR-042 triage heading in
a file this CR edits is kept verbatim; only bodies change** — among them `cr-authoring`'s "The CR
queue — structure only (queue idiom, 2026-07-20)", `orchestration-mainline`'s "Ownership — queue,
CR-gen, scheduling" and "Filing/assigning a CR — COMMIT docs FIRST, schedule write LAST", and
`bootstrap`'s "Step 3A — MAINLINE: load the queue, report to the USER".

- **`crucible` skill — a queue-verbs section.** As the installed client's `--help` states them:
  - **Read verbs, no `--agent`:** `queue` (the registered CRs) and `next` (what is actionable:
    NEXT, HOLD or DRAINED; `--track` is required once more than one track is declared).
  - **Write verbs, orchestrator only, each with `--agent` on the same line:**
    - `cr-plan --cr --title --release --wave` records title, release and wave. Without `--release` or
      `--wave` it lists the live proposals or planned waves and exits 2; it never guesses.
    - `cr-depends --cr --on` and `wave-sequence --release --wave --crs [--track]` each **replace the
      whole set**: adding a CR to a wave re-sends the wave's full order. `--track` assigns the wave's
      CRs to a lane.
    - `cr-supersede --cr --by`, `cr-void --cr --reason`, and `release-propose --label --target`.
  - **`plan-file --release`** is the same registration as `cr-plan`, made at filing; the two are
    not rival filing paths.
  - **`queue-file`** is retired from the workflow. It replaces the whole board queue from a README,
    so it is never run.
- **`cr-authoring`:**
  - The CR row in "Document types" names the spec file and the board, not a queue README.
  - **Under its kept heading, the queue idiom becomes filing a CR on the board:**
    - write the spec, then `cr-plan` (title, release, wave), `cr-depends`, and `wave-sequence` with
      the wave's full order;
    - allocate the next id from the board's `queue` and the spec files in `docs/changes/`;
    - supersede and void with `cr-supersede` and `cr-void`;
    - when a spec's H1 changes, re-post its title with `cr-plan`, so the spec and the board agree;
    - release membership stays the user's call. The first filing in a project with no release asks
      the user for a label and a target date and records it with `release-propose`;
    - the header slots now live in the project's `AGENTS.md`, the target release on the board;
    - waves, the release boundary and "a release is not a CR" keep their rules, stated against the
      board;
    - **Crucible absent:** filing is the spec file alone, ids from the spec files. **Unregistered**
      (empty `CRUCIBLE_PROJECT_KEY`): do the root `AGENTS.md`'s Setup section first, or in a project
      scaffolded before this CR its README's setup tasks;
    - **a project scaffolded before this CR:** the trigger is the board's `queue` missing a CR whose
      spec exists in `docs/changes/` with no merge recorded (no `cr-close`, spec `**Status:**` not
      `COMPLETED`). Only those CRs are filed, with `cr-plan`; a CR `queue` already lists is never
      re-filed, and a wave's order is re-sent in full. The release is the user's call, with the
      README's Target release slot as the proposed default. The README then stays as history.
  - **Where the rest goes:** a ruling to the PRD or a DN, a merge to `cr-close` (which posts the
    `cr-merged` milestone itself; a descriptive milestone is optional, never a second merge record),
    a follow-up to a CR filed on the board. This replaces "the queue (structure + dated footer
    Notes)", "queue/PRD/DN/memory edits", "the TRACKING docs (queue + board)" and "the queue
    default" wherever the skill names them.
  - **Closing a CR:** where board-tracking is absent, close-out is the spec's `**Status:**` flip
    alone.
  - **"CR vs task"** and **patch CRs** name filing on the board instead of a queue row.
  - **`docs/` layout:** `docs/changes/` holds the specs only.
- **`model-b` skill:** § 4 item 2 (the queue idiom) states that the board holds the queue and the
  execution state, with the specs in `docs/changes/`; item 5 drops the release-boundary row and says
  a release is a boundary event, not a CR; the description names the board. The role table's "CR
  queue" is the locked ontology's term and stays.
- **`orchestration-mainline`:** Mainline owns the board's queue (filing, `cr-depends`,
  `wave-sequence` with `--track` in multi mode), not a queue README. "Write spec + queue row"
  becomes "write the spec, file it on the board". A filed CR's process-state is on the board. The
  merge gate's "two-file close-out diff" becomes: before the merge, the spec's `**Status:**` flip;
  after the merge, `cr-close --commit <merge sha>`, which posts `cr-merged`. `cr-close` is never run
  before the merge commit exists.
- **`orchestration-common`:** the design phase's edits, "PRD → CRs → queue up front" and the GC
  principle name the board, not a queue row.
- **`bootstrap` and `shutdown`:** an empty `CRUCIBLE_PROJECT_KEY` sends the orchestrator to the Setup
  section of the **root** project's `AGENTS.md` when it has one, and otherwise (a project scaffolded
  before this CR) to its README's setup tasks.
- **Memory templates:** `java-orchestration` stops calling `docs/changes/` the CR queue, and its
  close-out names the spec's `**Status:**` flip before the merge and `cr-close` with the merge's sha
  after it, instead of updating a README.

### §S2 — The scaffold

- **No queue README.** `init` writes no `docs/changes/README.md` and writes `docs/changes/.gitkeep`
  so the specs' directory exists. `plan_files` (and so the envelope's `planned`) lists `.gitkeep`
  and not the README; on a real run `emitted` includes `.gitkeep` and not the README. A
  mid-emission failure keeps CR-MDB-033's rule that `emitted` is exactly what is on disk.
- **The root `AGENTS.md` gains a `## Setup` section** carrying the README's setup tasks as they
  stand: the dated scaffold line, the Crucible registration (its absent-tool remediation first,
  CR-MDB-045), in multi mode the Sandesh and direnv task (CR-MDB-047), and the `REPO_OWNER` check.
  A sub-project's `AGENTS.md` has none. The envelope's `setup_required` keeps its shape and keys;
  its note names the Setup section.
- **The header slots** become lines of the root `AGENTS.md`: Design contract and Evidence base as
  fill-in lines, and Ontology citing `~/.agents/skills/model-b/SKILL.md`. No target release is
  scaffolded.
- **The Workflow rules** state that the Crucible board holds the queue and the execution state and
  `docs/changes/` holds the specs, and point the manual registrations to the Setup section.
- **Readers:** `init`'s stderr note after a write names `AGENTS.md`'s Setup section. The
  `project_schema.toml` `readers` and `step` entries that name the queue README name it instead.

### §S3 — Model B's own records

- **Model B's README** keeps its content and gains a header: read-only history frozen at
  CR-MDB-048's merge; the queue and execution state are on the Crucible board; `queue-file` is never
  run against it, since it would replace the board's queue with these rows.
- **Model B's `AGENTS.md`:** the `docs/changes/` row, the Important-files line and the architecture
  flow say the README is frozen history and the board holds the queue. It carries the Design
  contract, Evidence base and Ontology lines from the README's header. Its Workflow Rules say a
  release is a boundary event, not a CR.
- **DN §D20** names `AGENTS.md`'s Setup section instead of the queue README's setup task.
- **Tests,** each migration listed by id:
  - the scaffold pins: `test_scaffold`'s `test_docs_model_queue_readme_and_research_dir`;
    `test_claude_era_retirement`'s `test_queue_readme_ontology_line_has_no_crucible_prefix`;
    `test_init_sandesh_address_and_envrc`'s Setup-tasks test; `test_project_tools_setup`'s three
    remediation tests; `test_project_registry_schema`'s golden README and `AGENTS.md` renders (the
    scaffold date moves into `AGENTS.md`); the `test_installer_correctness` docstring;
  - the skill-text pins: `CrAuthoringSkillS2Test`'s queue-idiom anchors (`test_cr_authoring_skill`);
    `test_bootstrap_shutdown_registry`'s not-registered regex.
  - Tests that read Model B's README as history keep passing.

## Acceptance criteria

- [ ] **`crucible` skill** has a queue-verbs section: `queue` and `next` as read verbs without
      `--agent`; `cr-plan`, `cr-depends`, `wave-sequence`, `cr-supersede`, `cr-void` and
      `release-propose` with their required flags and `--agent`; `cr-plan` exits 2 and never
      guesses; `cr-depends` and `wave-sequence` replace the whole set; `--track` for multi mode;
      `plan-file --release` as the same registration; `queue-file` never run.
- [ ] **`cr-authoring`** files a CR as spec → `cr-plan` → `cr-depends` → `wave-sequence` (full
      order); allocates ids from `queue` and the spec files; supersedes and voids with the verbs;
      re-posts a changed title; records a first release with `release-propose` after asking the
      user; covers Crucible absent (spec alone), unregistered (Setup section first, or an older
      project's README setup tasks) and an older project (file only the CRs with a spec, no merge
      and no `queue` entry; never re-file; release asked, README's Target release proposed); sends rulings to the PRD or a DN, a merge to `cr-close` alone
      (it posts `cr-merged`), follow-ups to a filed CR; closes a board-absent CR by the `**Status:**` flip
      alone; lists `docs/changes/` as specs only.
- [ ] **No shipped skill, reference, template, stack file or memory template** names `queue-file`
      (except as never run), `docs/changes/README.md`, a queue row, the Notes log or the queue
      README as a step — except bootstrap's and shutdown's older-project case and cr-authoring's
      older-project filing.
- [ ] **`model-b`** (§ 4 items 2 and 5, description), **`orchestration-mainline`** (ownership,
      filing with `--track`, process-state, merge-gate close-out) and **`orchestration-common`**
      state the board as the queue's home; the role table's ontology term is unchanged. Every
      close-out names the `**Status:**` flip before the merge and `cr-close` with the merge's sha
      after it; none runs `cr-close` before the merge or posts a second merge milestone.
- [ ] **`bootstrap` and `shutdown`** send an unregistered project to the root `AGENTS.md`'s Setup
      section when it has one, and otherwise to its README's setup tasks.
- [ ] **`init`** (standalone and monorepo, solo and multi) writes no `docs/changes/README.md` and
      writes `docs/changes/.gitkeep`; `planned` lists `.gitkeep` and not the README; `emitted`
      matches the files on disk.
- [ ] **The root `AGENTS.md`** has one `## Setup` section carrying every setup task the README
      carried, with the same absent-tool remediations and the multi-mode Sandesh/direnv task; no
      sub-project `AGENTS.md` has one. It carries Design contract, Evidence base and Ontology lines,
      the Ontology citing `~/.agents/skills/model-b/SKILL.md`. Its Workflow rules name the board and
      the Setup section, not the README.
- [ ] **`init`'s stderr note**, **`setup_required`'s note** and **`project_schema.toml`** name the
      Setup section, not the README; `setup_required` keeps its shape and keys.
- [ ] **Model B's README** keeps all its content under a frozen-history header pointing to the board
      and warning off `queue-file`; Model B's `AGENTS.md` (incl. the header-slot lines, and a release
      as a boundary event, not a CR) and DN §D20 say the same.
- [ ] **Gates that hold:** every migrated test listed by id; the suites that read Model B's README as
      history pass; the CR-042 triage headings resolve with `HEADING_RENAMES` unchanged; the
      verb-sweep `--agent` gate (`test_client_verb_sweep`); §D18 tool-name gates;
      `generator/build.py --check`; baselines re-measured in `AGENTS.md`.

## Non-goals

- Changing Crucible's verbs, or its `queue` registry.
- Requiring Crucible: a project without it keeps the board-absent close-out.
- Migrating an older project's README: its open rows are filed on the board once, by the
  orchestrator, and the README stays as history.
- Changing the locked ontology's terms.
- The roundhouse root's own `docs/changes/README.md` (a root session's).
- Rewriting closed specs, `archive/` or `audits/`.
