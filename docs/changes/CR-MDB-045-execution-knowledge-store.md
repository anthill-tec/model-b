# CR-MDB-045 — The scaffold detects lean-ctx and sets it up for the project

**Status:** PENDING (filed 2026-09-27; restructured and gap-analysed 2026-09-27)
**Type:** feature (scaffold, schema, skills, contract)
**Priority:** P1 — release 1.0.0, wave 2.
**Depends on:** CR-MDB-044 (both edit `orchestration-common.md` and bootstrap)
**Labels:** scaffold, registry, lean-ctx, memory, orchestration
**Design reference:** PRD D10 (AMENDED 2026-09-27: the scaffold detects and sets up the project's
tools); PRD D5 (AMENDED 2026-09-27: instruction tiers versus execution knowledge); PRD D3.1 (the
schema-driven registry); DN-multi-harness §D18 (skills name capabilities); `contracts/lean-ctx.md`

## Context

lean-ctx works alongside Model B's agent and skill definitions. Model B already declares it a tier-1
capability: `REQUIREMENTS` (modelb_axi/requirements.py) has the row `lean-ctx`, with provider
`pi-lean-ctx` and probe `pi-package`. `probe_harness` (modelb_axi/capabilities.py) judges it from
Pi's own `settings.json` and its installed package as DETECTED, ABSENT or UNKNOWN. The installer's
preflight runs that probe. `init` does not: it scaffolds the same project whether or not lean-ctx is
there. It also gives no pointer to where the orchestrator should keep what it learns while running
the project.

`orchestration-common.md` § "Memory" sets the GC principle and forbids unilateral writes. It does not
say where execution knowledge lives. lean-ctx's knowledge store is scoped to the session's project,
and a session loads it with one call. Crucible's practice (Sandesh #1409, #1410) shows three
pitfalls:
- a query recall is not a full listing;
- facts get archived silently, and restoring the category brings them back;
- `restore` ignores `dry_run`.

Model B's own session showed two more things:
- the project's store also holds lean-ctx's own automatic captures (its `auto:*` and `code_health`
  rooms);
- the `lean-ctx knowledge` CLI run from the project's directory did not answer from the project's
  store, while the in-session knowledge capability did.

## Scope

### §S1 — `init` asks Pi before it renders (modelb_axi/scaffold.py)

`run_init` probes lean-ctx through `probe_harness`, using the provider `REQUIREMENTS` declares for
`lean-ctx`, before it renders any project value. The verdict decides what §S2 and §S3 write:
- DETECTED: the key and the section are written;
- ABSENT or UNKNOWN: neither is written.

The `init` envelope gains a `tools` field, `{"lean-ctx": "<verdict>"}`, in both real and `--dry-run`
runs. A real run's human progress on stderr says what was set up, or that lean-ctx was not found, with
the capability's remediation.

### §S2 — The project's knowledge category (`modelb_axi/project_schema.toml`)

The schema gains a way to make a key conditional on a capability: a `when` field naming a
capability id from `REQUIREMENTS`. A key with `when` is rendered only when that capability's verdict
is DETECTED. `load_schema` validates `when` strictly, as it does every other field.

A new key:
- `KNOWLEDGE_CATEGORY`, in `.env`, scope `root+sub`, `when = "lean-ctx"`;
- `source = "derive"`, rule `<PROJECT_TOKEN>-workflow`, overridable by `--knowledge-category`;
- validated as a kebab-case id;
- `readers`: `modelb-axi init` (the AGENTS.md section), `orchestration-common` § "Memory", and the
  bootstrap skill.

### §S3 — The orchestrator's pointer (`_render_agents_md`)

When lean-ctx is DETECTED, the scaffolded `AGENTS.md` gains a "lean-ctx" section for the
orchestrator working in this project. The section:
- prefers lean-ctx's cached reads and compressed shell over the harness's built-ins;
- keeps the project's execution knowledge in lean-ctx's knowledge store under `KNOWLEDGE_CATEGORY`,
  through the session's knowledge capability. It never uses the `lean-ctx knowledge` CLI, whose
  project does not follow the working directory;
- loads that category, and only that category, at bootstrap.

A monorepo sub-project's `AGENTS.md` names its own category.

### §S4 — The rules (`orchestration-common.md` § "Memory", `skills-src/bootstrap/SKILL.md`)

§ "Memory" gains:
- Where the project's `.env` carries `KNOWLEDGE_CATEGORY`, execution knowledge is kept in the
  project's knowledge store under that category:
  - one short fact per item, with a stable kebab-case key;
  - the same key supersedes a fact.
- Only execution knowledge goes there: never an orchestrator rule, an agent definition, a ruling
  that belongs in the PRD or a DN, or a project fact that belongs in `.env` or `AGENTS.md`.
- Only Mainline or Solo writes facts. A Track reads them, and raises new ones to Mainline, as the
  no-unilateral-writes rule already says.
- The GC and no-unilateral-write rules still apply: a fact is stored only after the user has seen
  its wording, and is removed once it becomes a repo artifact.
- Without the key, nothing changes.

The store is named as a capability (DN §D18).

Bootstrap, where `KNOWLEDGE_CATEGORY` is set:
- restores the category's archived facts;
- lists the category;
- reports that the store is in use and how many facts it loaded.

It never uses a query recall, and never loads the automatic rooms. Shutdown needs no step: facts are
written when they are learned.

### §S5 — The contract (`contracts/lean-ctx.md`)

The contract records:
- the knowledge verbs Model B relies on: remember, list a category, restore, remove;
- how `init` detects lean-ctx and what it sets up;
- the pitfalls:
  - a query recall is not a full listing;
  - facts get archived silently;
  - `restore` ignores `dry_run`;
  - the CLI's project does not follow the working directory;
  - the store also holds lean-ctx's automatic captures.

## Acceptance criteria

- [ ] `run_init` probes lean-ctx before rendering. The envelope's `tools` field carries the verdict in
      real and `--dry-run` runs. The probe runs against a sandboxed Pi agent dir in the tests; no test
      reads the real `~/.pi`.
- [ ] The schema's `when` field is validated by `load_schema`: an unknown capability id is rejected.
      A `when` key is rendered only on DETECTED.
- [ ] With lean-ctx DETECTED:
      - `.env` carries `KNOWLEDGE_CATEGORY=<PROJECT_TOKEN>-workflow`, or the `--knowledge-category`
        override, and a monorepo sub-project's `.env` carries its own;
      - `AGENTS.md` carries the lean-ctx section naming that category.
- [ ] With lean-ctx ABSENT or UNKNOWN, neither the key nor the section is written, and stderr names
      the remediation.
- [ ] `orchestration-common.md` § "Memory" and bootstrap state §S4's rules, read `KNOWLEDGE_CATEGORY`
      as a schema-declared key, and name no lean-ctx tool. The harness-neutral, retired-tool and
      registry gates stay green.
- [ ] `contracts/lean-ctx.md` records the verbs, the detection, and the five pitfalls.
- [ ] `generator/build.py --check` is clean. The suite baselines are re-measured in `AGENTS.md`.

## Non-goals

- Installing or configuring lean-ctx; its remediation is only named.
- Changing lean-ctx's shell allowlist or any other lean-ctx setting.
- Projects scaffolded before this CR, Model B's own hand-written `.env` included: they gain the key by
  re-running `init` or by adding it.
- Migrating existing memory into the store.
- Other projects' stores, or how lean-ctx keys its stores.
