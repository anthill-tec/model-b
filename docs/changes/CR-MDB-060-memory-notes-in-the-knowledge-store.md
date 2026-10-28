# CR-MDB-060 — `docs/memory/` is retired: the orchestrator's stack notes move into the stack skills

**Status:** PENDING — spec drafted 2026-10-28 from the gap analysis; awaiting the spec pre-review and
approval.
**Type:** refactor (scaffold, stack skills, skills, reference material)
**Priority:** P1 — release 1.0.0, wave 2, after CR-MDB-086 and before CR-MDB-088.
**Depends on:** CR-MDB-085 and CR-MDB-086 (the stack-skill mechanism and the Java skill); the board is
authoritative: read `queue`, not this line.
**Labels:** memory, scaffold, stack-skills, skills
**Design reference:** PRD D5, amendments of 2026-10-10 (the knowledge store is the one home;
`docs/memory/` retired), 2026-10-28 (material placed by its readers; the stack skill) and its
2026-10-28 rulings at this CR's gap analysis (the orchestrator's stack notes are a stack-skill
reference, not facts; `operational-commands.md` dropped); CR-MDB-085 (the mechanism, its markers and
gates); DN-multi-harness-deploy-model §D21 and §D25; `orchestration-common` § "Memory".

## Context

`init` still lays down `docs/memory/` from `skills-src/memory-templates/`: the stack orchestration
templates `java-orchestration.md`, `rust-orchestration.md` and `arduino-orchestration.md` (157 lines
left after CR-MDB-085 and CR-MDB-086 took their agent-facing parts) and `operational-commands.md`
(373 lines, a generic command cheat-sheet no skill or definition reads), plus an `INDEX.md` that the
bootstrap and shutdown skills read. What is left in the stack templates is orchestrator-facing stack
mechanics — instructions, which the knowledge store's rules keep out of facts. PRD D5 gives them the
stack skill: each becomes its stack skill's `references/orchestration.md`, and `docs/memory/` goes.
CR-MDB-088 then makes the knowledge store the unconditional home of execution knowledge.

## §S1 — The orchestrator's notes become stack-skill references

1. Each stack template moves, with `git mv`, to its stack skill:

   | Template | Becomes |
   |---|---|
   | `skills-src/memory-templates/java-orchestration.md` | `generator/skills/java-stack/references/orchestration.md` |
   | `skills-src/memory-templates/rust-orchestration.md` | `generator/skills/rust-stack/references/orchestration.md` |
   | `skills-src/memory-templates/arduino-orchestration.md` | `generator/skills/arduino-stack/references/orchestration.md` |

   Its headings and rules move as they are, apart from §S1.4's rewordings; its title and preamble name
   it as the stack skill's orchestrator reference, not a memory template.
2. **`arduino-stack`** is declared in `generator/stack-skills.toml` for `arduino`. Its `SKILL.md` routes
   to `references/orchestration.md`. No arduino role lists it: its only reader is the orchestrator.
3. `java-stack`'s and `rust-stack`'s `SKILL.md` each gain a routing row for the orchestrator to
   `references/orchestration.md`.
4. **Rewordings the move requires:** a runner form the raw-runner guard matches (`mvn clean verify` in
   the Java notes, twice; `cargo llvm-cov nextest …` in the Rust notes, once) is reworded to the stack
   client's verb or as a description (§D21); the notes name no `ctx_*` or lean-ctx tool.
5. `rust.toml`'s provenance header no longer names "the Rust orchestration memory template".

## §S2 — `operational-commands.md` is dropped

`skills-src/memory-templates/operational-commands.md` is deleted. Its Quarkus-specific sections —
"Quarkus-Specific Commands" (health, metrics, OpenAPI, container-image builds), "Apicurio/Confluent
Schema Registry (Quarkus)" and the RediSearch commands — move into `java-stack`'s
`references/quarkus-patterns.md`, under §S1.4's rewordings and §D25 (no project named).

## §S3 — `init` writes no `docs/memory/`

1. `init` writes no `docs/memory/` directory, no template copy and no `INDEX.md`, for any stack; the
   memory-template machinery in `modelb_axi/scaffold.py` (the template directory's resolution, the
   template families and their selection, the index's rendering and its place in the planned files) is
   removed. `skills-src/memory-templates/` no longer exists.
2. `modelb_axi/deploy.py` no longer names `memory-templates` as scaffold material.
3. A project scaffolded before this CR keeps its `docs/memory/` untouched; `modelb-axi agents` renders
   its stack skills, orchestration references included.

## §S4 — The skills read the stack skills

1. **`bootstrap` and `shutdown`, Step 0.5, item 3,** read the orchestrator references of the project's
   rendered stack skills — `references/orchestration.md` in each `.agents/skills/<name>/` that has one
   — where they read `docs/memory/INDEX.md` and its slices. A project with none notes it and skips; the
   fallback paragraph says so instead of naming `INDEX.md`.
2. **`gap-analysis`**, Dimension 8, names the stack skills and their references where it names "the
   memory templates".
3. No shipped skill, template or stack file names `docs/memory/` or a memory template.

## §S5 — The gates and the reach

1. **The guards over the moved text:** `generator/skills/` is already in every gate's roots
   (CR-MDB-085); the guards' exclusions of `skills-src/memory-templates/` go with the directory, and
   the raw-runner guard's tests that pin that exclusion are removed or repointed.
2. **The orchestrator-rule triage stays frozen.** `test_orchestrator_rule_triage` resolves a
   destination in a moved template to the file it became — same heading — through a file-move map
   beside its moved-rules map; its class rule for a `stack:<t>` row accepts the stack's
   `generator/skills/<t>-stack/references/orchestration.md`; `audits/2026-09-26-orchestrator-rule-triage.md`
   is not edited.
3. **`archive/mapping.md`:** a `moved` row for each moved template (Now its reference); a `retired` row
   for `skills-src/memory-templates/operational-commands.md`; the rows whose Now is
   `skills-src/memory-templates/` (the Claude-era orchestration family row) name the new location;
   `tests/test_archive_mapping.py`'s required old paths include the four.
4. **Every test that reads `skills-src/memory-templates/`, a moved or deleted template, `docs/memory/`
   or `INDEX.md`** is repointed to the new path or the new behaviour, keeping its intent:
   `test_archive_mapping`, `test_board_holds_the_queue`, `test_bootstrap_shutdown_registry`,
   `test_claude_era_retirement`, `test_client_path_anchoring`, `test_code_health_skill`,
   `test_core_split`, `test_cr_authoring_skill`, `test_execution_knowledge_rules`,
   `test_harness_neutral_skills`, `test_installer_assets`, `test_memory_model`,
   `test_orchestrator_rule_triage`, `test_pi_agent_definitions`, `test_prd_criteria`,
   `test_project_registry_schema`, `test_project_tools_setup`, `test_raw_runner_guard`,
   `test_rust_dead_scan`, `test_rust_stack_generator`, `test_scaffold`, `test_skill_bundle_guards`,
   `test_stack_reference_material`, `test_stack_skills`, `test_tooling_detachment`,
   `test_worktree_flow`, `test_worktree_flow_surfaces`, `test_worktree_layout_and_bundles`.
5. `AGENTS.md` names no `memory-templates/` and no `docs/memory/` (its `skills-src/` row included); the
   generated definitions are re-rendered.

## Acceptance criteria

- [ ] **AC1 (§S1.1, §S1.5).** Each §S1.1 template exists only at its new path, its title naming it as
      the stack skill's orchestrator reference; `rust.toml` names no orchestration memory template.
- [ ] **AC2 (§S1.2–3).** `generator/stack-skills.toml` declares `arduino-stack` for `arduino`; its
      `SKILL.md` and those of `java-stack` and `rust-stack` each route to `references/orchestration.md`;
      no arduino definition's skills line names `arduino-stack`; `init --stacks arduino` (sandboxed,
      Pi harness) renders `.agents/skills/arduino-stack/`.
- [ ] **AC3 (§S1.4, §S2).** The raw-runner guard over `generator/skills/` finds nothing; no `ctx_` tool
      or lean-ctx is named there; `operational-commands.md` does not exist; `references/quarkus-patterns.md`
      carries its Quarkus health, metrics, OpenAPI, container-image, Apicurio and RediSearch commands,
      and `generator/skills/` names no `org.fourpm`, `fourpm`, `store-utils` or `4pm-Store-utils`.
- [ ] **AC4 (§S3).** `init` (sandboxed) for each stack writes no `docs/memory/`; `skills-src/memory-templates/`
      does not exist; `modelb_axi/` names no `memory-templates`, `docs/memory` or memory-template
      family.
- [ ] **AC5 (§S4).** `bootstrap` and `shutdown` Step 0.5 name the stack skills' `references/orchestration.md`
      and neither names `docs/memory/` or `INDEX.md`; `gap-analysis` Dimension 8 names the stack skills
      and no memory templates; no file under `skills-src/`, `generator/` or `AGENTS.md` names
      `docs/memory/` or a memory template.
- [ ] **AC6 (§S5.2–3).** `test_orchestrator_rule_triage` passes with the audit file unchanged, every
      row whose destination was a moved template resolving to its reference; `archive/mapping.md`
      carries the §S5.3 rows and its gate passes.
- [ ] **AC7.** The skill-frontmatter and Pi skill-loader checks pass over `generator/skills/` and a
      rendered `arduino-stack`; `generator/build.py --check` is clean; this repository's `.pi/agents`
      matches the regeneration; `ruff check` exits 0; the full suite passes through the Crucible client.

## Non-goals

- Making the knowledge store the unconditional home of execution knowledge, and reconciling facts
  automatically — CR-MDB-088.
- Removing an existing project's `docs/memory/` — `migrate` (CR-MDB-082, CR-MDB-055).
- The arduino material's generality to every Arduino project — CR-MDB-084 (1.1.0).
