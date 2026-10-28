# CR-MDB-060 — `docs/memory/` is retired: the orchestrator's stack notes move into the stack skills

**Status:** COMPLETED (filed 2026-10-10, gap analysis and pre-review 2026-10-28).
**Type:** refactor (scaffold, stack skills, skills, scripts, reference material, gates)
**Priority:** P1 — release 1.0.0, wave 2, after CR-MDB-086 and before CR-MDB-088.
**Depends on:** CR-MDB-085 and CR-MDB-086 (the stack-skill mechanism and the Java skill); the board is
authoritative: read `queue`, not this line.
**Labels:** memory, scaffold, stack-skills, skills
**Design reference:** PRD D5, amendments of 2026-10-10 (the knowledge store is the one home;
`docs/memory/` retired), 2026-10-28 (material placed by its readers; the stack skill) and the
2026-10-28 rulings at this CR's gap analysis (the orchestrator's stack notes are a stack-skill
reference, not facts; `operational-commands.md` dropped); CR-MDB-085 (the mechanism, its markers and
gates; its "no `arduino-stack`" ruling is reversed here, under the PRD amendment); DN-multi-harness-
deploy-model §D21 and §D25; `orchestration-common` § "Memory".

## Context

`init` still lays down `docs/memory/` from `skills-src/memory-templates/`: the stack orchestration
templates `java-orchestration.md`, `rust-orchestration.md` and `arduino-orchestration.md` (53, 88 and
16 lines after CR-MDB-085 and CR-MDB-086 took their agent-facing parts) and `operational-commands.md`
(373 lines, a command cheat-sheet no skill or definition reads), plus an `INDEX.md` that the bootstrap
and shutdown skills read. What is left in the stack templates is orchestrator-facing stack mechanics —
instructions, which the knowledge store's rules keep out of facts. PRD D5 gives them the stack skill:
each becomes its stack skill's `references/orchestration.md`, and `docs/memory/` goes. CR-MDB-088 then
makes the knowledge store the unconditional home of execution knowledge; between the two, a project
without `KNOWLEDGE_CATEGORY` keeps no execution knowledge, as `orchestration-common` already says.

## §S1 — The orchestrator's notes become stack-skill references

1. Each stack template moves, with `git mv`, to its stack skill:

   | Template | Becomes |
   |---|---|
   | `skills-src/memory-templates/java-orchestration.md` | `generator/skills/java-stack/references/orchestration.md` |
   | `skills-src/memory-templates/rust-orchestration.md` | `generator/skills/rust-stack/references/orchestration.md` |
   | `skills-src/memory-templates/arduino-orchestration.md` | `generator/skills/arduino-stack/references/orchestration.md` |

   Its headings and rules move as they are, apart from §S1.4 and §S1.5. Each opens with a provenance
   line naming it `the <stack>-stack skill's orchestrator reference` (that phrase), not a memory
   template.
2. **`arduino-stack`** is declared in `generator/stack-skills.toml` for `arduino`. Its `SKILL.md` routes
   to `references/orchestration.md`. No arduino role lists it: its only reader is the orchestrator.
3. `java-stack`'s and `rust-stack`'s `SKILL.md` each gain a routing row for the orchestrator to
   `references/orchestration.md`.
4. **Rewordings the move requires (§D21):** a runner form the raw-runner guard matches (`mvn clean
   verify` in the Java notes, twice; `cargo llvm-cov nextest …` in the Rust notes, once) is reworded to
   the stack client's verb or as a description; the notes name no `ctx_*` or lean-ctx tool. The Java
   notes' pointer to the `worktree-flow` command set in `rust-orchestration.md` names the
   `worktree-flow` tool's own help instead, since a Java project has no Rust skill.
5. **No project named in the Rust notes (§D25).** Each of these becomes a neutral, general statement,
   the rule it carries kept:

   | One project's detail | Anchor |
   |---|---|
   | The full-boot app names | `NaiApp`, `DevApp` |
   | The docker-infra set's test names | `kafka connector e2e`, `Bridge`, `kafka-e2e-serial` |
   | A dated incident on one machine | `librocksdb`, `observed 2026-07-03` |
   | One machine's size | `24-core`, `31 GiB` |
   | A legacy database name | `.nai-schedule.db` |
   | A hook that no longer exists | `post-test-crucible-reminder` (the live hook is `post-regression-disk-reminder`) |
   | A pointer to notes this CR retires | `project's orchestration notes` |

   The last also leaves `rust.toml`'s workspace-layout mechanics: per-crate feature flags come from the
   dispatch prompt or the project's `AGENTS.md`.

## §S2 — `operational-commands.md` is dropped

`skills-src/memory-templates/operational-commands.md` is deleted. Its "Quarkus-Specific Commands"
(health, metrics, OpenAPI, container-image builds) and "Apicurio/Confluent Schema Registry (Quarkus)"
sections move into `java-stack`'s `references/quarkus-patterns.md`, and its RediSearch commands move
beside that reference's existing RediSearch section; `java-stack`'s routing row for
`quarkus-patterns.md` names them. The rest — generic Docker, Mongo, Redis, HTTPie, load-test and
port commands, and the summary table — goes. The moved text is checked by its anchors `/q/health`,
`/q/openapi`, `quarkus.container-image.build`, `ccompat` and `FT._LIST`.

## §S3 — `init` writes no `docs/memory/`

1. `init` writes no `docs/memory/` directory, no template copy and no `INDEX.md`, for any stack, and
   its help names no project memory.
   `modelb_axi/scaffold.py` loses `_memory_templates_dir`, `MEMORY_TEMPLATE_FAMILIES`,
   `_select_memory_templates`, `_render_memory_index`, the `docs/memory/INDEX.md` entry in
   `plan_files`, the emission of `docs/memory/` and the `_agent_sources` docstring's reference to the
   template directory. `skills-src/memory-templates/` no longer exists.
2. `modelb_axi/deploy.py`'s docstring no longer names `memory-templates` as scaffold material.
3. A project scaffolded before this CR keeps its `docs/memory/` untouched; `modelb-axi agents`, run at
   its root, renders its stack skills, orchestration references included.

## §S4 — The skills and the other surfaces read the stack skills

1. **`bootstrap` and `shutdown`, Step 0.5, item 3,** read the orchestrator references of the root
   project's rendered stack skills — `references/orchestration.md` in each `.agents/skills/<name>/`
   that has one, whatever the skill's name — where they read `docs/memory/INDEX.md` and its slices. A
   project with none notes it and skips. Where it has none but still has a `docs/memory/` and one of
   its stacks declares a stack skill, the skill says to run `modelb-axi agents` at the project root
   to render its stack skills; a project none of whose stacks declares a stack skill (python, bun) is
   not pointed there. Nothing is read from `docs/memory/`.
2. **`gap-analysis`**, Dimension 8, names the stack skills and their references where it names "the
   memory templates".
3. **The stack files:** `quarkus.toml`'s and `rust.toml`'s "Companion memory" bullets name the stack
   skill's `references/orchestration.md` where they say "the project's orchestration memory"; `rust.toml`'s
   provenance header drops its "memory template wins" precedence rule and names no memory template.
4. **The scripts and hooks:** the `# Consuming skills:` headers of `scripts/rust-code-health.py`,
   `rust-crate-map.py`, `rust-dead-scan.py`, `schedule_db.py` and `worktree-flow.py` (and
   `worktree-flow.py`'s other mentions) name the `rust-stack` skill where they name
   `rust-orchestration.md`; `hooks-src/scripts/post-regression-disk-reminder`'s message names the
   `rust-stack` skill's disk-hygiene section.
5. No shipped file — under `skills-src/`, `generator/`, `scripts/`, `hooks-src/`, or `AGENTS.md` —
   names `docs/memory/`, a memory template or "orchestration memory", except §S4.1's pointer for older
   projects.

## §S5 — The gates and the reach

1. **The guards over the moved text:** `generator/skills/` is already in every gate's roots
   (CR-MDB-085); the guards' exclusions of `skills-src/memory-templates/` go with the directory, and the
   tests pinning that exclusion are removed or repointed. `ModelBCommonTextNeutralTest`'s neutrality and
   retired-tool checks widen from `skills-src/` to `generator/skills/`.
2. **The orchestrator-rule triage stays frozen.** The audit's Destination strings and its class rules
   are left as they are. Where `test_orchestrator_rule_triage` reads a destination file — the
   destination and new-section-body checks, the moved-rules departure check, the arduino template check,
   `CapabilityWordingTest` and the pinned bundle set — a file-move map (old template → its reference,
   headings unchanged) beside its moved-rules map resolves the file; `audits/2026-09-26-orchestrator-rule-triage.md`
   is not edited.
3. **`archive/mapping.md`:** the `~/.claude/memory/{java-orchestration,rust-orchestration,operational-commands}.md`
   family row splits into one row per member — java and rust `moved`, Now their reference;
   `operational-commands.md` `deleted` — each with `CR-MDB-060` in Moved-by; a `moved` row for each
   `skills-src/memory-templates/<stack>-orchestration.md` (Now its reference) and a `deleted` row for
   `skills-src/memory-templates/operational-commands.md`; `tests/test_archive_mapping.py`'s required old
   paths include the four.
4. **Every test that reads `skills-src/memory-templates/`, a moved or deleted template, `docs/memory/`,
   `INDEX.md` or a pinned stack-skill or Dimension-8 list** is repointed to the new path or behaviour,
   keeping its intent: `test_archive_mapping`, `test_board_holds_the_queue`,
   `test_bootstrap_shutdown_registry`, `test_claude_era_retirement`, `test_client_path_anchoring`,
   `test_code_health_skill`, `test_core_split`, `test_cr_authoring_skill`,
   `test_execution_knowledge_rules`, `test_gap_analysis_reach_and_pre_review`,
   `test_harness_neutral_skills`, `test_installer_assets`, `test_memory_model`,
   `test_orchestrator_rule_triage`, `test_pi_agent_definitions`, `test_prd_criteria`,
   `test_project_registry_schema`, `test_project_tools_setup`, `test_raw_runner_guard`,
   `test_rust_dead_scan`, `test_rust_stack_generator`, `test_scaffold`, `test_skill_bundle_guards`,
   `test_skill_frontmatter`, `test_stack_reference_material`, `test_stack_skills`,
   `test_tooling_adoption`, `test_tooling_detachment`, `test_worktree_flow`,
   `test_worktree_flow_surfaces`, `test_worktree_layout_and_bundles`.
5. `AGENTS.md` names no `memory-templates/` and no `docs/memory/` (its `skills-src/` row included); the
   generated definitions are re-rendered.

## Acceptance criteria

- [ ] **AC1 (§S1.1).** Each §S1.1 template exists only at its new path, and its first line names it
      `the <stack>-stack skill's orchestrator reference`.
- [ ] **AC2 (§S1.2–3).** `generator/stack-skills.toml` declares `arduino-stack` for `arduino`; its
      `SKILL.md` and those of `java-stack` and `rust-stack` each route to `references/orchestration.md`;
      no arduino definition's skills line names `arduino-stack`; `init --stacks arduino` (sandboxed, Pi
      harness) renders `.agents/skills/arduino-stack/`, and its `AGENTS.md` stack line names it.
- [ ] **AC3 (§S1.4–5, §S2).** The raw-runner guard over `generator/skills/` finds nothing; no `ctx_`
      tool or lean-ctx is named there; `generator/skills/` contains none of §S1.5's anchors, and the
      Java orchestration reference names no `rust-orchestration.md`; `rust.toml` names no
      `project's orchestration notes`; `operational-commands.md` does not exist; `references/quarkus-patterns.md`
      carries §S2's anchors and `java-stack`'s routing row for it names the moved commands.
- [ ] **AC4 (§S3).** `init` (sandboxed) for each stack writes no `docs/memory/`, and its `planned` and
      `emitted` lists name none; `skills-src/memory-templates/` does not exist; `modelb_axi/` defines
      none of §S3.1's symbols and names no `memory-templates` or `docs/memory`; `init`'s help names no
      project memory.
- [ ] **AC5 (§S4).** `bootstrap` and `shutdown` Step 0.5 name the stack skills' `references/orchestration.md`
      in any rendered skill (no `<stack>-stack` name assumed), read nothing from `docs/memory/`, and
      name it only in the pointer to `modelb-axi agents`, which is limited to a project one of whose
      stacks declares a stack skill; `gap-analysis` Dimension 8 names the stack skills and no
      memory templates; `quarkus.toml`'s and `rust.toml`'s "Companion memory" bullets name
      `references/orchestration.md` and neither names "orchestration memory"; `rust.toml` names no
      memory template; no shipped file §S4.5 lists names `docs/memory/`, a memory template,
      "orchestration memory" or `rust-orchestration.md`, apart from that pointer.
- [ ] **AC6 (§S5.1–3).** `ModelBCommonTextNeutralTest` reads `generator/skills/`;
      `test_orchestrator_rule_triage` passes with the audit file unchanged and every row whose
      destination was a moved template resolving to its reference; `archive/mapping.md` carries the
      §S5.3 rows and its gate passes.
- [ ] **AC7 (§S3.3, §S5.4–5).** Every §S5.4 module passes against the moved files; `AGENTS.md` names no
      `memory-templates/` or `docs/memory/`; the skill-frontmatter and Pi skill-loader checks pass over
      `generator/skills/` and a rendered `arduino-stack`; a project scaffolded with a `docs/memory/`
      keeps it after `modelb-axi agents`, which renders its stack skills; `generator/build.py --check`
      is clean; this repository's `.pi/agents` matches the regeneration; `ruff check` exits 0; the full
      suite passes through the Crucible client.

## Non-goals

- Making the knowledge store the unconditional home of execution knowledge, and reconciling facts
  automatically — CR-MDB-088.
- Removing an existing project's `docs/memory/` — `migrate` (CR-MDB-082, CR-MDB-055).
- The arduino material's generality to every Arduino project — CR-MDB-084 (1.1.0); the Java material's
  remaining project architecture — CR-MDB-087 (1.1.0).
