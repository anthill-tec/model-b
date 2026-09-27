# CR-MDB-045 — The scaffold sets each project up for the workflow's tools

**Status:** PENDING (filed 2026-09-27; restructured and gap-analysed 2026-09-27)
**Type:** feature (installer requirements, scaffold, schema, skills, contract)
**Priority:** P1 — release 1.0.0, wave 2.
**Depends on:** CR-MDB-044 (both edit `orchestration-common.md` and bootstrap)
**Labels:** installer, scaffold, registry, lean-ctx, sandesh, crucible, memory
**Design reference:** PRD D10 (AMENDED 2026-09-27: the installer detects the workflow's tools; the
scaffold sets each project up for them); PRD D11 (the capability contract); PRD D5 (AMENDED
2026-09-27: instruction tiers versus execution knowledge); PRD D3.1 (the schema-driven registry);
DN-multi-harness §D18 (skills name capabilities)

## Context

Model B's agents and skills rely on a set of tools to carry the workflow:
- the Pi harness;
- its extensions;
- Crucible and Sandesh;
- each stack's toolchain and Crucible client.

**The installer already checks them.** `REQUIREMENTS` (modelb_axi/requirements.py) declares them
by tier:
- tier 1, the Pi extensions `dispatch`, `lean-ctx`, `permissions` and `watcher`, judged by
  `probe_harness` from Pi's own package settings;
- tier 2, `uv`, `sandesh`, `crucible`, `crucible-client`, `python3`, `bash`, `gh` and `jq`;
- tier 3, each stack's `toolchain`.

The installer's preflight records the verdicts in `install.toml`: `[deps]` for uv, Sandesh and
Crucible, and `[capabilities]` for the rest.

**Three gaps remain:**
- Sandesh's own Pi extension, `@anthill-tec/sandesh-pi`, is not declared.
- `init` does not read any of these verdicts. It writes the same `AGENTS.md` capability contract (a
  static list rendered by `_render_capability_contract`) and the same registry whatever the machine
  has, and it gives the orchestrator no pointer for a tool beyond the identity keys.
- An `install.toml` written before `[capabilities]` existed carries no extension verdicts.

**lean-ctx is the first tool whose project setup is new.** It needs:
- the project's knowledge category;
- a pointer telling the orchestrator to keep its execution knowledge there.

`orchestration-common.md` § "Memory" sets the GC principle and forbids unilateral writes, but does
not say where execution knowledge lives. lean-ctx's knowledge store is scoped to the session's
project, and a session loads it with one call. Crucible's practice (Sandesh #1409, #1410) shows three
pitfalls: a query recall is not a full listing, facts get archived silently (restoring the category
brings them back), and `restore` ignores `dry_run`. Model B's own session showed two more:
- the store also holds lean-ctx's automatic captures (the `auto:*` and `code_health` rooms);
- the `lean-ctx knowledge` CLI run from the project's directory did not answer from the project's
  store, while the in-session knowledge capability did.

## Scope

### §S1 — The installer declares Sandesh's Pi extension (`REQUIREMENTS`)

`REQUIREMENTS` gains a tier-1 row:
- `sandesh-pi`: provider `@anthill-tec/sandesh-pi`, probe `pi-package`, policy `recommended`, with
  remediation `pi install npm:@anthill-tec/sandesh-pi`.

It is a third-party package, so `--yes` never installs it. The install guide's prerequisites,
derived from `REQUIREMENTS`, list its remediation. The installer records its verdict in
`[capabilities]` like any other tier-1 row. Crucible's Pi installer is declared the same way once
Crucible releases it (a non-goal here).

### §S2 — `init` reads the installation's verdicts (`run_init`)

Before rendering any project value, `run_init` reads the verdicts from `install.toml`:
- every tier-1 and tier-2 row;
- the tier-2 `crucible-client` row and the tier-3 `toolchain` row, for the project's own stacks.

It never probes. A verdict of `detected` or `installed` counts as present.

A missing verdict counts as unknown. This includes an `install.toml` without `[capabilities]`, and a
row the installation never probed. Nothing is set up for an unknown tool, and stderr says to re-run
the installer.

The `init` envelope gains a `tools` field. It maps each `REQUIREMENTS` row id to `present`, `absent`
or `unknown`, in real and `--dry-run` runs alike.

**How verdicts combine:**
- **A stack-scoped row** (`crucible-client`, `toolchain`) is judged over the project's stacks and
  each stack's probes. It takes the worst verdict: `absent` if any is absent, else `unknown` if any
  is unknown, else `present`. The capability contract (§S5) keeps the per-stack detail.
- **An `install.toml` without `[capabilities]`** still carries `[deps]`. `uv`, `sandesh` and
  `crucible` take their `[deps]` verdicts; only rows with no recorded verdict anywhere are
  `unknown`.

### §S3 — Keys conditional on a tool (`modelb_axi/project_schema.toml`)

A schema key may carry `when = "<requirement id>"`. It is then rendered only when that tool is
present (§S2). `load_schema` validates `when` strictly: an id not declared in `REQUIREMENTS` is
rejected.

### §S4 — lean-ctx's project setup

**The key.** `KNOWLEDGE_CATEGORY`:
- in `.env`, scope `root+sub`, `when = "lean-ctx"`;
- `source = "derive"`: `<PROJECT_TOKEN>-workflow` normalised to kebab-case (lower-cased, `_` and
  spaces turned into `-`), overridable by `--knowledge-category`. A token accepted before this CR
  never makes `init` fail. `--knowledge-category` given while lean-ctx is not present is noted on
  stderr as not applied;
- validated as a kebab-case id;
- readers: `modelb-axi init` (the AGENTS.md pointer), `orchestration-common` § "Memory", and the
  bootstrap skill.

**The pointer.** When lean-ctx is present, the scaffolded `AGENTS.md` gets a lean-ctx section for the
orchestrator working in this project. It says to:
- prefer lean-ctx's cached reads and compressed shell over the harness's built-ins;
- keep the project's execution knowledge in the knowledge store under `KNOWLEDGE_CATEGORY`, through
  the session's knowledge capability. Never the `lean-ctx knowledge` CLI, whose project does not
  follow the working directory;
- load that category, and only that category, at bootstrap: restore its archived facts, then list
  it (bootstrap's knowledge step).

A monorepo sub-project's `AGENTS.md` names its own category.

### §S5 — The capability contract shows the project's state (`_render_capability_contract`)

The `AGENTS.md` capability contract is rendered from the verdicts §S2 reads, for the project's own
stacks:
- each tool appears once: a tier-2 row and a stack toolchain probe for the same tool (e.g. `python3`)
  are merged into one line;
- a present tool is listed as present;
- an absent or unknown tool is listed with its remediation.

The existing pointers stay as they are: the identity section's Sandesh project, and the queue
README's Sandesh and Crucible setup tasks. Where Sandesh or Crucible is absent, its setup task first
names the tool's remediation.

### §S6 — The rules (`orchestration-common.md` § "Memory", `skills-src/bootstrap/SKILL.md`)

**§ "Memory" gains:**
- **Where to keep it.** Where the project's `.env` carries `KNOWLEDGE_CATEGORY`, execution knowledge
  is kept in the project's knowledge store under that category, one short fact per item, with a
  stable kebab-case key. The same key supersedes a fact.
- **What goes there.** Only execution knowledge: never an orchestrator rule, an agent definition, a
  ruling that belongs in the PRD or a DN, or a project fact that belongs in `.env` or `AGENTS.md`.
- **Who writes.** Only Mainline or Solo writes facts; a Track reads them, and raises new ones to
  Mainline.
- **The GC and no-unilateral-write rules still apply.**
- **Without the key,** nothing changes.

The section names the store as a capability, and so does every other skill: `model-b` names the
installation's knowledge-store tool, not lean-ctx.

**Bootstrap,** where `KNOWLEDGE_CATEGORY` is set:
- restores the category's archived facts;
- lists that category;
- reports that the store is in use and how many facts it loaded.

It never uses a query recall and never loads the automatic rooms. Shutdown needs no step.

### §S7 — The contract (`contracts/lean-ctx.md`)

The contract records:
- the knowledge verbs Model B relies on: remember, list a category, restore, remove;
- how a project gets lean-ctx set up (the installer's verdict, then `init`'s key and pointer);
- the five pitfalls:
  - a query recall is not a full listing;
  - facts get archived silently;
  - `restore` ignores `dry_run`;
  - the CLI's project does not follow the working directory;
  - the store holds lean-ctx's automatic captures.
- that a monorepo's sub-projects derive the same category as the root when they share its token.

### §S8 — The project's agents match its tools (`modelb_axi.agents`)

The generated agents assume lean-ctx today: each stack file's role `tools` allowlist carries the
`ctx_*` tools, and each role template has a "Tool Usage (lean-ctx …)" section. When `init` (and
`modelb-axi agents`) renders a project's agents, it reads the lean-ctx verdict (§S2):
- **present:** the agents are rendered as today;
- **absent or unknown:** the agent names no lean-ctx tool anywhere in its definition: not in the
  preamble, First Actions, the spec-reading steps, the tool-usage section, or the stack's own text.
  - Each role's allowlist replaces the `ctx_*` tools with Pi's built-in equivalents, so the agent
    keeps a shell: `bash` joins it, and the permission block allows it.
  - The tool-usage section and every instruction name the built-in read, search and shell.

The same holds for everything else `init` renders for the project:
- **The permission policy:** the project-level Pi permission policy allows `bash` and names no
  `ctx_*` tool when lean-ctx is absent or unknown.
- **The memory slices:** the stack memory templates `init` scaffolds into `docs/memory/` name no
  lean-ctx tool in that case.

**Validated before the first write.** `init` and `modelb-axi agents` render every agent in memory
during validation, in the form the verdict selects, and write only the pre-rendered text. Any render
failure is a `ScaffoldError`: exit 2, an error envelope on stdout, nothing written, and `--dry-run`
refuses it too. Render failures include a missing or unreadable built-in passages file, and a
definition that still names lean-ctx.

`generator/agents/`, the canonical committed set that `build.py --check` guards, keeps the lean-ctx
form. The hook wiring needs no change: `compile_wiring` already points the hooks at the project's own
paths.

## Acceptance criteria

- [ ] `REQUIREMENTS` declares `sandesh-pi` as a tier-1, recommended `pi-package` row. A `--yes`
      installer run in a sandbox never installs it, and records its verdict in `[capabilities]`.
- [ ] `run_init` reads the verdicts before rendering and runs no probe. The envelope's `tools` field
      maps every tier-1 and tier-2 row, plus the project's stacks' `crucible-client` and `toolchain`,
      to `present`, `absent` or `unknown`, in real and `--dry-run` runs.
- [ ] An `install.toml` without `[capabilities]` gives `unknown` for the extensions. Nothing is set up
      for them, and stderr says to re-run the installer.
- [ ] `load_schema` rejects a `when` naming an undeclared id. A `when` key is rendered only when its
      tool is present.
- [ ] **lean-ctx present:**
      - `.env` carries `KNOWLEDGE_CATEGORY=<PROJECT_TOKEN>-workflow`, or the override;
      - each monorepo sub-project carries its own;
      - `AGENTS.md` carries the lean-ctx section naming the category.
- [ ] **lean-ctx absent or unknown:** neither the key nor the section is written.
- [ ] The capability contract in `AGENTS.md` lists each of the project's tools with its state, and
      the remediation where it is not present. A Sandesh or Crucible setup task names the tool's
      remediation first when that tool is absent.
- [ ] A render failure in `init` or `modelb-axi agents`, dry run included, exits 2 with an error
      envelope and writes nothing. Render failures are a missing or unreadable built-in passages file,
      and a definition still naming lean-ctx.
- [ ] A token such as `MyProj` or `my_proj` derives a kebab-case category, and never fails `init`.
      `--knowledge-category` without lean-ctx present is noted on stderr.
- [ ] With lean-ctx absent or unknown, the project permission policy allows `bash` and names no
      `ctx_*` tool, and no scaffolded `docs/memory/` slice names a lean-ctx tool.
- [ ] Each tool appears once in the capability contract. The lean-ctx pointer says to restore, then
      list. No skill names lean-ctx as a tool.
- [ ] With lean-ctx absent or unknown, every agent `init` renders for the project names no `ctx_*`
      tool or lean-ctx instruction anywhere. Its allowlist is today's non-`ctx_*` tools plus `bash`,
      which the permission block allows. Its tool-usage section names the built-in read, search and
      shell.
      With lean-ctx present, the rendered agents are byte-identical to today's. `generator/agents/`
      is unchanged.
- [ ] `orchestration-common.md` § "Memory" and bootstrap state §S6's rules, read `KNOWLEDGE_CATEGORY`
      as a schema-declared key, and name no lean-ctx tool. The harness-neutral, retired-tool and
      registry gates stay green.
- [ ] `contracts/lean-ctx.md` records the verbs, the setup path and the five pitfalls.
- [ ] No test reads the real `install.toml`, `~/.pi` or `~/.crucible` for this. `generator/build.py
      --check` is clean, and the suite baselines are re-measured in `AGENTS.md`.

## Non-goals

- Probing tools in `init`; the installer probes.
- Declaring Crucible's Pi installer before Crucible releases it.
- Installing, configuring or re-configuring any tool: remediation is named, not run. Pi installs
  stay the installer's, as today.
- Adopting sandesh-pi's wake loop in place of Model B's watcher. That is the later sandesh-pi CR.
- Projects scaffolded before this CR, including Model B's own hand-written `.env`: they gain the key
  and pointer by re-running `init`, or by hand.
- Migrating existing memory into the store, other projects' stores, and how lean-ctx keys its stores.
