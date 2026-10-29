# CR-MDB-088 — Execution knowledge always lives in the knowledge store, reconciled automatically

**Status:** PENDING — spec drafted 2026-10-29 from the gap analysis and the user's rulings (PRD D5, 2026-10-29); spec pre-review to follow.
**Type:** feature (project schema, scaffold, skills, contract)
**Priority:** P1 — release 1.0.0, wave 2, after CR-MDB-060.
**Depends on:** CR-MDB-060 (COMPLETED; both edit bootstrap and shutdown). The board is authoritative: read
`queue`, not this line.
**Labels:** memory, knowledge-store, lean-ctx, skills
**Points:** 8 (re-scored at gap analysis; seeded 5).
**Design reference:**
- PRD D5, amendments of:
  - 2026-10-10: the knowledge store is the one home, and lean-ctx is required;
  - 2026-10-14: facts are reconciled automatically, never on request;
  - 2026-10-28: the store starts empty, and `init` seeds no facts.
- PRD D10, 2026-09-27: tool pointers live in the per-project tier.
- DN-multi-harness-deploy-model §D18: skills name capabilities.
- CR-MDB-045 §S3, §S4, §S6, §S7.
- Research note `lean-ctx-for-model-b` §S4 and §S5, corrected by the gap analysis's measured facts F1–F19
  (lean-ctx 3.11.4 source).

## Context

- **The key is still conditional.** `modelb_axi/project_schema.toml`'s `KNOWLEDGE_CATEGORY` carries
  `when = "lean-ctx"`, so `scaffold.run_init` renders it only when `install.toml` records lean-ctx
  `detected` or `installed`. No key and no `AGENTS.md` lean-ctx section are written in four cases:
  - an install made with `--allow-missing-capabilities` and no lean-ctx;
  - a lean-ctx verdict of `unknown` (the pre-flight only warns, with no flag needed);
  - an `install.toml` that predates the row;
  - no `install.toml` at all.

  The skills match:
  - `orchestration-common` § "Memory" ends "Without the key, nothing changes";
  - bootstrap Step 0.6 runs "only where `KNOWLEDGE_CATEGORY` is set".

  PRD D5 (2026-10-10) says every Model B project has the key, and that there is never a silent fallback.
- **Nothing reconciles facts.** PRD D5 (2026-10-14) sets three moments. No skill states them, and
  `tests/test_execution_knowledge_rules.py` pins that shutdown has *no* knowledge step.
- **The store loses facts, measured in lean-ctx 3.11.4's source:**
  - **A listing is bounded.** A category listing returns at most `memory.knowledge.recall_facts_limit`
    facts (10, a global-only key). It says so (`showing <n>/<total>`), and it retrieves only those it shows.
  - **Retrieval is the only decay protection.** A fact retrieved within the last day does not decay.
    Every other fact decays, compounding, on every lifecycle run.
  - **Every write runs the lifecycle.** Each `remember` and each `remove` runs it, and the lifecycle
    archives any fact below 0.3.
  - **A restore sets the fact up to be lost again.** It brings a fact back at its archived confidence
    (≈0.25 after a quality archive), and the next write archives it again.
  - **Re-confirmation.** A same-key rewrite re-confirms a fact (the confidence goes to the midpoint, ≥0.5).
    Positive feedback does not: it leaves the confidence unchanged.
  - **Restore has no category scope.** `ctx_knowledge`'s restore reads its `category` argument as the
    *store*, so today's "restore the category" answers `Unknown store`. Unscoped, it restores up to 50
    items from all four stores. Facts archive under a root shared by every unprotected project, so it can
    also bring in another project's archived facts. Only a `query` substring scopes it to a category.
  - **Export is a file, not a listing.** It writes the whole store to a JSON file under lean-ctx's data
    directory, and retrieves nothing.
  - **The cap is shared.** The 200-fact cap holds lean-ctx's automatic captures too (`auto_capture`,
    global-only).
- **A Track writes the store.** Bootstrap has both roles restore, which is a store write, although
  § "Memory" lets only Mainline or Solo write.

## Scope

### §S1 — The key is unconditional

1. **The schema.** `project_schema.toml`'s `KNOWLEDGE_CATEGORY` loses `when = "lean-ctx"`. Its `readers`
   gain the shutdown skill (it reconciles at shutdown), next to `modelb-axi init`, `orchestration-common`
   and the bootstrap skill. Its other fields are unchanged:
   - `file = ".env"`;
   - `scope = "root+sub"`;
   - `source = "derive"`, rule `knowledge_category`, override `--knowledge-category`;
   - validated as `kebab_id`.
2. **`init` writes the key and the section on every verdict.** For every lean-ctx verdict (`detected`,
   `installed`, `absent`, `unknown`, unrecorded) and with no `install.toml`, `init` writes:
   - `KNOWLEDGE_CATEGORY` into the root `.env` and each sub-project's `.env`;
   - the lean-ctx section (§S2) into the root `AGENTS.md` and each sub-project's `AGENTS.md`.

   `--knowledge-category` is always applied, and no "not applied" note is printed for it.
3. **The renderers.** `scaffold._render_agents_md` and `scaffold._render_sub_agents_md` take
   `knowledge_category: str` as a required argument, and render the lean-ctx section unconditionally.
   `_emit_plan` passes `registry["KNOWLEDGE_CATEGORY"]`. The docstrings that cite CR-MDB-045 §S4's
   condition are updated.
4. **The `when` mechanism stays** (ruled 2026-10-29, PRD D5): `_active_schema`, `_check_when`,
   `_overrides_not_applied`, the schema header's `when` doc, and `S1_FIELDS`' `when`. No packaged key
   carries `when` after this CR. The not-applied note keeps a test on `ConditionalSchemaKeyTest`'s fixture
   key, which gains an override flag (§S8).
5. **Unchanged by the verdict.** The agents' lean-ctx form (CR-MDB-045 §S8) and the permission policy
   still follow the lean-ctx verdict. When lean-ctx is not present, the capability contract's `lean-ctx`
   line still reports its state and remediation. `init` adds no new note (ruled 2026-10-29, PRD D5).
6. **The two texts that say "written only when".** Both say instead that every project carries the key:
   - `modelb_axi/cli.py`'s `--knowledge-category` help;
   - `skills-src/model-b/SKILL.md` §4.1's `KNOWLEDGE_CATEGORY` entry, which names the knowledge-store
     capability and no lean-ctx tool.

### §S2 — The `AGENTS.md` lean-ctx pointer names the store's verbs

`_render_lean_ctx_section(category)` renders `## lean-ctx (for the orchestrator working this project)`
with these bullets, in this order. This is the per-project tier, so it may name `ctx_knowledge` (PRD D10;
DN §D18):

1. Prefer lean-ctx's cached reads and compressed shell over the harness's built-in read and shell tools.
   This bullet is unchanged.
2. Keep this project's execution knowledge in lean-ctx's knowledge store under the category `<category>`
   (`KNOWLEDGE_CATEGORY` in `.env`), through the session's `ctx_knowledge` tool. Never use the
   `lean-ctx knowledge` CLI: its project does not follow the working directory. Only the "never" clause
   names the CLI.
3. **Restore.** At bootstrap, Mainline or Solo restores the category's archived facts with `ctx_knowledge`
   `action=restore`, `category=facts` (the store, not the category) and `query=<category>`. Never restore
   unscoped: that restores every store, and other projects' archived facts.
4. **List.** List the category with `action=recall` and `category=<category>`. The answer says
   `showing <n>/<total>`. When `<n>` is less than `<total>`, the listing is incomplete: `action=export`
   writes the whole store to a file it names, and the rest is read from there. A Track only lists.
5. **Rewrite first.** After a restore, before any other write, rewrite each restored fact that is kept with
   `action=remember` under its key. Every `remember` and `remove` archives each fact still below the
   store's 0.3 archive threshold, and `action=feedback` does not lift a fact over it.

### §S3 — `orchestration-common` § "Memory" (the rules)

**Removed bullets:**
- "**Where to keep execution knowledge:** where the project's `.env` carries `KNOWLEDGE_CATEGORY`…";
- "**Without the key,** nothing changes…".

**Added bullets.** Each states its rule in one bullet, and none names a lean-ctx tool:
- **The one home.** Execution knowledge is kept in the project's knowledge store, under the category its
  `.env` names in `KNOWLEDGE_CATEGORY`, and nowhere else:
  - one short fact per item, each with a stable kebab-case key;
  - the same key supersedes;
  - a fact about a CR names its id;
  - the store starts empty.
- **A missing key or store is reported, never worked around.**
  - A project whose `.env` lacks `KNOWLEDGE_CATEGORY` takes the category from its `AGENTS.md` and reports
    that the key is missing from `.env`.
  - A session without the knowledge-store capability reports it, with the remediation the project's
    `AGENTS.md` capability contract names.
  - Execution knowledge never falls back to a file.
- **Reconciled automatically, never on request.** There are three moments:
  - at bootstrap, right after the category is loaded;
  - after every `cr-close`, for each fact naming the closed CR. For a Track's `cr-close`, this happens once
    Mainline confirms it;
  - at shutdown, for each fact the run overtook.

  At each moment, Mainline or Solo checks every fact concerned against the board and the repo. It
  rewrites an overtaken fact under its key, removes one the repo or the board now tracks, and reports
  what changed. A fact is never only flagged for the user's approval. A Track raises the facts it finds
  overtaken to Mainline.
- **One listing holds the category** (ruled 2026-10-29, PRD D5).
  - The category is kept within what one listing of it shows. Every load lists it before the run's first
    write, because a listed fact is the only kind the store keeps from decaying.
  - A listing names how many facts it shows of how many. One that shows fewer than all is reported, the
    rest is read from the store's complete export, and the category is reconciled down to the limit.
- **Restored facts are re-confirmed** (ruled 2026-10-29, PRD D5).
  - Why it is needed: a restore brings a fact back at the confidence it was archived with, often below the
    store's archive threshold, and every write archives each fact below that threshold again.
  - So, after a restore and before any other write, each restored fact the reconciliation keeps is
    rewritten under its key.
  - When a rewrite leaves another restored fact archived again, that fact is restored by its key and
    rewritten at once.
  - Positive feedback does not re-confirm a fact.
- **The store's limits.**
  - Its fact cap is shared with the store's automatic captures.
  - Decay compounds on every write.
  - A restore has no dry run.

The GC, no-unilateral-write, "What goes there" and "Who writes" bullets are unchanged.

### §S4 — Bootstrap loads, completes, reconciles and re-confirms

`skills-src/bootstrap/SKILL.md`:

1. **Step 0.5's fallback paragraph** loses its `KNOWLEDGE_CATEGORY` exception ("has no fallback … skipped,
   never asked about"). The key follows the general fallback: `AGENTS.md`'s lean-ctx section names the
   category.
2. **Step 0.6** keeps its `## Step 0.6 ` heading prefix, and becomes "Load the execution knowledge (BOTH
   roles)". It states:
   - **Mainline or Solo**, in order:
     1. restore the category's archived facts, that category's only (never another store's or another
        project's);
     2. then list that category;
     3. when the listing shows fewer facts than the category holds, report it and read the rest from the
        store's complete export;
     4. reconcile every fact (§ "Memory"), and re-confirm each restored fact it keeps before any other
        write;
     5. report that the knowledge store is in use, how many facts it loaded, and what the reconciliation
        changed. Mainline and Solo report to the user.
   - **A Track** lists the category only, and makes no write. It reports the count to Mainline in its
     status, and raises the facts it finds overtaken.
   - **Unchanged:** never a query recall to load, and never the automatic rooms.
   - **A missing key or knowledge-store capability** is reported (§ "Memory"), and bootstrap continues.
   - The step names no lean-ctx tool.

### §S5 — Shutdown reconciles the facts the run overtook

`skills-src/shutdown/SKILL.md`. No numbered step is added or renumbered (`FinalStepPlacesTest` pins
Step 2A's 5, its emergency 4, and Step 2B's 5):

1. **Step 2B, item 4 (Mainline or Solo, graceful).** Before the report, list the category and reconcile
   each fact the run overtook (`orchestration-common` § "Memory"). The report to the user names what
   changed.
2. **Step 2A, item 4 (a Track's ack).** The ack names the facts the Track found overtaken, raised to
   Mainline. A Track writes no fact.
3. **Step 1B (emergency).** No reconciliation: the fast-abort skips it.
4. The text says no "finish the active cycle" beyond what is there today
   (`unexcepted_finish_findings`), and names no lean-ctx tool.

### §S6 — Close-out: the after-`cr-close` moment

`orchestration-common.md` § "Close-out" gains one bullet in "The rest of the close-out" list (never a
numbered step: the eight-step order and "steps 2–5 and 8" stay):

> **After `cr-close`,** Mainline or Solo lists the category and reconciles each fact naming the closed CR
> (§ "Memory").

### §S7 — The contract's knowledge-store section

`contracts/lean-ctx.md` § "Knowledge store (CR-MDB-045 §S7)" is rewritten. It is retitled without the
CR reference, and records the following.

**The verbs** Model B relies on, each with its `ctx_knowledge` form:
- remember;
- list a category (`recall` + `category`);
- restore (`restore`, `category=facts`, `query=<category>`);
- remove;
- export (the fallback for an incomplete listing).

**The setup path.** The installer records lean-ctx's verdict. `init` then writes `KNOWLEDGE_CATEGORY` and
the pointer **whatever the verdict**. The sentence "Absent or unknown, neither is written" is removed.

**The kept pitfalls,** reworded where needed so their pins still match:
- a query recall is not a full listing;
- facts get archived silently;
- `restore` ignores `dry_run`;
- the CLI's project does not follow the working directory;
- the store holds lean-ctx's automatic captures.

**The new pitfalls,** each citing its lean-ctx 3.11.4 source path and symbol:
- **The listing limit.** A listing shows at most `memory.knowledge.recall_facts_limit` facts (10). The key
  is global-only, not settable in a project's `.lean-ctx.toml`. The listing says `showing <n>/<total>`, and
  only the listed facts are retrieved.
- **Decay.** A fact retrieved within the last day does not decay. Every other fact decays on every
  lifecycle run, compounding, and every `remember` and `remove` runs the lifecycle.
- **Restore.**
  - Its `category` argument is the store.
  - Unscoped, it restores every store, and other projects' archived facts from the shared legacy facts
    archive.
  - It keeps each fact's archived confidence.
  - The next write re-archives a fact below 0.3.
- **Re-confirmation.** A same-key rewrite re-confirms (the confidence goes to the midpoint). `feedback`
  does not change confidence.
- **Export.** It writes a JSON file of the whole store, and retrieves nothing.
- **The cap.** The 200-fact cap is shared with automatic captures. `auto_capture` is global-only.
- **Rehydration.** A category listing that finds no current fact rehydrates at most 3 archived facts at
  ≥0.6.

**The project-scoped levers** (no trust needed), and which ones Model B sets through CR-MDB-091 (pending
ruling, Q4):
- `memory.knowledge.max_facts` raised to 500;
- `autonomy.auto_consolidate = false`.

The section also records what `auto_consolidate = false` does not stop: consolidation on MCP shutdown and
on compaction, and automatic captures. It records that the levers apply through the bridge process's
resolved project root (the git top level, so a monorepo's root file), and that a user who wants a larger
category raises the global `recall_facts_limit` themselves.

The rest of the contract is CR-MDB-092's.

### §S8 — The migrations

These pins move with the change. Each is marked `# MIGRATED at CR-MDB-088 (§S…)`, and each moves in the
cycle that changes what it reads.

**`tests/test_project_tools_setup.py` (§S1, §S2):**
- `KnowledgeCategorySchemaEntryTest.test_it_is_a_root_and_sub_env_key_rendered_only_when_lean_ctx_is_present`:
  no `when`; the readers include the shutdown skill.
- `KnowledgeCategoryRenderedTest.test_absent_unknown_or_unrecorded_lean_ctx_writes_no_key`: the key is
  written, with the override applied, for every verdict, in the root and sub `.env`; `.env.local` gets
  none.
- `KnowledgeCategoryRenderedTest.test_a_pre_capabilities_install_toml_writes_no_key`: the key is written.
- `KnowledgeCategoryNotAppliedNoteTest`, both methods: no note on any verdict.
- `LeanCtxPointerTest.test_absent_or_unknown_lean_ctx_writes_no_section`: one section for every verdict,
  root and sub.
- `LeanCtxPointerTest.test_the_bootstrap_instruction_says_restore_then_list`: §S2's bullets 3–5.
- The module docstring.

**`tests/test_project_registry_schema.py` (§S1, §S2), `_Shared.InitAgainstToday`** (solo, multi and
monorepo):
- `test_root_env_is_todays_plus_sandesh_project_and_the_project_key`: asserts the
  `KNOWLEDGE_CATEGORY=myproj-workflow` line, and strips it from the golden comparison.
- `test_agents_md_differs_only_in_identity_setup_header_lines_and_workflow_rules`: strips the `## lean-ctx`
  section with `_outside_section` before comparing.
- `test_every_other_emitted_file_is_byte_identical_to_today`: `_golden_sub_agents_md` gains the rendered
  lean-ctx section.
- `SoloMonorepoInitAgainstTodayTest.test_sub_project_envs_are_todays_plus_keys_scoped_to_sub_projects`:
  the sub `.env` key, as for the root.

**`tests/test_init_tool_verdicts.py` (§S1.4):** `ConditionalSchemaKeyTest`'s fixture key `TOOL_CHANNEL`
gains `override = "--tool-channel"`, plus one test. Given `tool_channel` while lean-ctx is not present,
`init` prints one `--tool-channel … not applied` note; with lean-ctx present it prints none.

**`tests/test_execution_knowledge_rules.py` (§S3–§S5, §S7):**
- `MEMORY_WHERE`'s `(where|when|if)…knowledge_category` conditional;
- `MEMORY_WITHOUT_KEY` and `test_without_the_key_nothing_changes`, inverted: no unit says nothing changes
  without the key;
- `BOOTSTRAP_RESTORE_THEN_LIST`'s conditional;
- `test_shutdown_needs_no_knowledge_step`, inverted (§S5);
- `GOOD_MEMORY`, `GOOD_BOOTSTRAP` and `GOOD_CONTRACT`, and the mutation tables' "condition" and "without"
  entries;
- the module docstring.

**Any other pin** the RED full-suite run finds reading an `init`-rendered `.env` or `AGENTS.md` (the shared
fixture `tests/_helpers.write_install_toml` records no lean-ctx verdict, so every such run gains the key and
the section). It is listed in the RED report and migrated the same way.

## Acceptance criteria

- [ ] **AC-S1, the schema.**
      - The packaged schema's `KNOWLEDGE_CATEGORY` entry has no `when`.
      - It keeps `file`, `scope`, `source`, `rule`, `inputs`, `override` and `validate` as §S1.1 lists them.
      - Its `readers` name `modelb-axi init`, `orchestration-common`, `bootstrap` and `shutdown`.
      - `scaffold.load_schema` loads it.
- [ ] **AC-S1, `init` on every verdict** (in-process `scaffold.run_init`, through `_InitSandboxCase`'s
      sandbox, with `HOME`, `MODELB_HOME` and `PI_CODING_AGENT_DIR` under a temp dir).
      - **The runs:** lean-ctx `detected`, `installed`, `absent`, `unknown` and unrecorded; an
        `install.toml` without `[capabilities]`; and no `install.toml`. Each with
        `repo_shape="monorepo:a"` and no override, and again with `knowledge_category="shared-kb"`.
      - **The root `.env` and `a/.env`** each carry exactly one `KNOWLEDGE_CATEGORY=` line: the derived
        `<token>-workflow`, or `shared-kb`.
      - **`.env.local`** names no `KNOWLEDGE_CATEGORY`.
      - **The envelope's `registry`** carries the value.
      - **No stderr line** names `--knowledge-category` with "not applied".
      - **`--dry-run`** reports the value and writes nothing.
- [ ] **AC-S1, the `when` mechanism.**
      - `load_schema` still rejects an undeclared `when`.
      - A fixture `when` key is still rendered only when its tool is present.
      - `--tool-channel` on the fixture key, given while lean-ctx is not present, prints exactly one
        not-applied note, and none when lean-ctx is present.
- [ ] **AC-S1, the texts.**
      - `modelb-axi init --help`'s `--knowledge-category` text contains no "only when".
      - `skills-src/model-b/SKILL.md`'s `KNOWLEDGE_CATEGORY` entry says no "only when", and names no
        lean-ctx tool.
      - `scaffold._render_agents_md` and `scaffold._render_sub_agents_md` have no default for
        `knowledge_category`.
- [ ] **AC-S2, the pointer** (the same sandboxed runs as AC-S1).
      - **Where:** the root `AGENTS.md` and `a/AGENTS.md` each carry exactly one section whose heading
        names lean-ctx, apart from the capability contract, on every verdict. It names the category,
        and `KNOWLEDGE_CATEGORY`, and still carries "read", "shell", "knowledge" and "bootstrap"
        (`test_the_section_carries_the_three_instructions`, unmigrated).
      - **What it carries:** `ctx_knowledge`; `action=restore` with `category=facts` and
        `query=<category>`, in one line; `action=recall`; `showing`; `action=export`; `action=remember`;
        and a line saying `feedback` does not lift a fact over the threshold.
      - **Order:** restore comes before the listing.
      - **Roles:** a line says a Track only lists.
      - **The CLI:** every line naming `lean-ctx knowledge` also says "never".
- [ ] **AC-S3, § "Memory"** (phrase-level, one unit per rule, through `rule_units`). Each detector is
      proved both ways on synthetic text.
      - **The one home:** the knowledge store; the category its `.env` names in `KNOWLEDGE_CATEGORY`; one
        short fact per item; a stable kebab-case key; the same key supersedes; a fact about a CR names its
        id; the store starts empty.
      - **Missing key or store:** a missing `.env` key is taken from `AGENTS.md` and reported. A session
        without the knowledge-store capability is reported with the remediation the capability contract
        names. There is never a file fallback.
      - **Reconciliation:** automatic, never on request. It names the three moments (bootstrap after the
        load; after every `cr-close`, the facts naming the closed CR; at shutdown, the facts the run
        overtook). It names the board and the repo; rewrite under its key; remove; report what changed;
        never only flagged. A Track's `cr-close` is reconciled by Mainline once it confirms it. A Track
        raises overtaken facts to Mainline.
      - **One listing:** the category is kept within one listing. A listing names how many it shows of
        how many. Fewer than all is reported, and the rest is read from the export.
      - **Re-confirmation:** after a restore, before any other write, rewrite each restored fact kept.
        A re-archived one is restored by its key and rewritten at once. Feedback does not re-confirm.
      - **The limits:** the cap is shared with automatic captures; decay compounds on every write;
        restore has no dry run.
      - **What stays:** the section still satisfies `MEMORY_WHAT`, `MEMORY_WHO`,
        `MEMORY_GC_STILL_APPLIES`, `MEMORY_GC_PRINCIPLE` and `MEMORY_NO_UNILATERAL`. No unit says nothing
        changes without the key, and no unit makes the store conditional on the key
        (`(where|when|if)…knowledge_category` as a condition).
- [ ] **AC-S4, bootstrap.**
      - **The heading:** Step 0.6's heading starts `## Step 0.6 `, carries "BOTH roles", and has no
        "only where".
      - **Mainline or Solo:** an enumeration with its lead-in restores the category's archived facts
        (scoped to that category), **then** lists the category, then reconciles, then re-confirms
        restored facts before any other write, then reports the facts loaded and what changed.
        Restore-then-list is enforced as order.
      - **A Track:** a unit says a Track only lists, makes no write, and raises overtaken facts to
        Mainline.
      - **Unchanged:** `BOOTSTRAP_NEVER_RECALL` and `BOOTSTRAP_NEVER_AUTOMATIC` still hold. A unit
        reports a missing key or capability.
      - **Step 0.5:** it no longer says `KNOWLEDGE_CATEGORY` has no fallback.
      - **Gates:** `lean_ctx_tool_findings` over the file is empty.
- [ ] **AC-S5, shutdown.**
      - **Step 2B, item 4:** reconciles each fact the run overtook, and names what changed in the report.
      - **Step 2A, item 4:** the ack names the overtaken facts the Track raises to Mainline, and the Track
        writes no fact.
      - **Step 1B:** says the emergency skips the reconciliation.
      - **Unchanged:** `FinalStepPlacesTest` and every `test_orchestration_rules_from_crucible` shutdown
        pin pass unmigrated. `lean_ctx_tool_findings` over the file is empty.
- [ ] **AC-S6, close-out.**
      - § "Close-out" has a bullet stating that after `cr-close` Mainline or Solo reconciles each fact
        naming the closed CR.
      - `test_orchestration_common_close_out_states_the_eight_step_order` passes unmigrated: eight
        numbered steps, `CLOSE_OUT_ORDER`.
- [ ] **AC-S7, the contract.**
      - **The verbs:** they include export, and restore's `category=facts` and `query` form.
      - **The setup path:** says `init` writes the key and pointer whatever the verdict, and the sentence
        "Absent or unknown, neither is written" is gone.
      - **The pitfalls:** the five existing ones keep satisfying `PITFALLS`. Each new pitfall in §S7 is
        one unit, pinned by a detector and proved both ways on synthetic text: the listing limit (with
        `recall_facts_limit` and "global"); decay on every write; restore's store argument, cross-project
        reach and kept confidence; feedback not re-confirming; export as a file; the shared cap with
        global `auto_capture`; rehydration.
      - **The levers:** they name `memory.knowledge.max_facts` and `autonomy.auto_consolidate` as
        project-scoped with no trust needed, and the values CR-MDB-091 sets.
      - **No skill names a tool:** `SkillsNameTheKnowledgeStoreCapabilityTest` and
        `ModelBSkillsNameNoLeanCtxToolTest` pass.
- [ ] **Migrations (RED).** Every §S8 pin moves in its cycle, marked `# MIGRATED at CR-MDB-088 (§S…)`.
      The RED report lists any further pin the full-suite run found.
- [ ] **Runs.**
      - The suite is green through the client, with a real `HOME` and with an empty one; the empty `HOME`
        stays empty.
      - No test reads the real `install.toml`, `~/.pi` or `~/.crucible` for this CR.
      - `ruff check` exits 0, and `generator/build.py --check` is clean.
      - New tests use a literal `§`.
      - The `AGENTS.md` baselines are re-measured.

## Non-goals

- **The project's `.lean-ctx.toml`.** CR-MDB-091 writes it. This CR only records, in the contract, which
  levers it sets and their values (Q4).
- **The rest of the contract refresh, and upstream findings.** The version, the profile, the ledger, and
  findings (a) and (b) are CR-MDB-092's. CR-092's "category recall silently capped at 10" is inaccurate
  (the listing says `showing n/total`), which its gap analysis corrects.
- **The agents' lean-ctx form and the permission policy.** Both still follow the lean-ctx verdict
  (CR-MDB-045 §S8, CR-MDB-037). `init` refusing without lean-ctx is not done (Q5).
- **The install guide and `pi-package/README.md`.** `missing-capabilities` already says the dependent assets
  stay inert until the package is installed, and each project's capability contract names lean-ctx's state.
- **Changing lean-ctx's global config** (`recall_facts_limit`, `auto_capture`). The user's call.
- **Seeding facts at `init`, and any test of it.** It is already true (PRD D5 2026-10-28); nothing in
  `modelb_axi/` writes the store.
- **Existing projects without the key.** They take it from `AGENTS.md`, or add it by hand. `migrate` is
  CR-MDB-082.
- **Correcting the research note `lean-ctx-for-model-b`.** It is a dated record; the corrections live in
  this CR's gap analysis.

## Cycle plan

No commit sits red, and every test that reads a changed text moves in the same cycle.

1. **The key and the pointer** (§S1, §S2; §S8's `test_project_tools_setup`, `test_project_registry_schema`
   and `test_init_tool_verdicts` pins, plus any further `init`-output pin the RED run finds). Red-green.
   - The schema, the scaffold, the help and the `model-b` SKILL.md registry entry move here, because the
     scaffold goldens read them.
2. **The rules** (§S3–§S6; §S8's `test_execution_knowledge_rules` memory, bootstrap and shutdown pins).
   Red-green.
   - § "Memory", bootstrap, shutdown and § "Close-out" move together, because one module's detectors read
     all four.
3. **The contract** (§S7; §S8's `GOOD_CONTRACT` and the contract pins). Red-green.
4. **Verify.**
