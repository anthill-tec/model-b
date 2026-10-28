# CR-MDB-086 — The Java stack skill: the Java references and mechanics, rendered into Java projects

**Status:** PENDING — spec drafted 2026-10-28 from the gap analysis; awaiting the spec pre-review and
approval.
**Type:** feature (stack skill content, stack file, scaffold seeding, reference material)
**Priority:** P1 — release 1.0.0, wave 2, after CR-MDB-085 and before CR-MDB-060.
**Depends on:** CR-MDB-085 (the stack-skill mechanism); the board is authoritative: read `queue`, not
this line.
**Labels:** stacks, skills, java, quarkus, references
**Design reference:** PRD D5, amendment of 2026-10-28 (the language references stay documents;
material placed by its readers; `java-stack` rendered for the `quarkus` and `java` stacks; no project
named); CR-MDB-085 (the mechanism: `generator/stack-skills.toml`, `generator/skills/<name>/`, the
ownership markers, the render paths, the gates over `generator/skills/`); DN-multi-harness-deploy-model
§D21 and §D25.

## Context

The quarkus agents are pointed at the Java references in `docs/memory/`: `quarkus.toml`'s "Companion
memory" bullet cites `docs/memory/java-testing-practices.md`, `docs/memory/java-coding-standards.md` and
the `java-orchestration` template, and four more lines cite a reference by bare name. Three references
— `java-modern-syntax`, `java-maven-best-practices`, `java-quarkus-patterns`, about 3,000 lines — are
read by no agent. A `java` project (no stack file, no agents) receives the references through
`docs/memory/` today. CR-MDB-085 built the stack-skill mechanism; this CR gives the Java material its
skill. CR-MDB-060 then retires `docs/memory/`.

## §S1 — The Java stack skill

1. `generator/stack-skills.toml` declares `[skills.java-stack]` with `stacks = ["quarkus", "java"]`.
2. Its source is `generator/skills/java-stack/`: a `SKILL.md` and five references, moved from
   `skills-src/memory-templates/` (§S2):

   | Reference | From |
   |---|---|
   | `references/coding-standards.md` | `java-coding-standards.md` |
   | `references/testing-practices.md` | `java-testing-practices.md` |
   | `references/modern-syntax.md` | `java-modern-syntax.md` |
   | `references/maven.md` | `java-maven-best-practices.md` |
   | `references/quarkus-patterns.md` | `java-quarkus-patterns.md` |

3. **`SKILL.md`** routes by topic to each reference by its path, and carries the binding rules the
   agents need that `quarkus.toml` does not state. The references mark their binding sections
   (NON-NEGOTIABLE, CRITICAL, MANDATORY); of the ten in the coding standards and testing practices,
   eight are stated in `quarkus.toml` (code formatting and imports, unused imports, error handling and
   warnings, the Java TDD cycle, the MongoDB TestContainers isolation, the surefire and failsafe reports,
   `@TempDir` with `@QuarkusTest`) and one by the sub-agent procedure every definition carries (the TDD
   workflow). `SKILL.md` carries the rest, each as a compressed rule:
   - test-first problem isolation (from testing practices, "CRITICAL: Test-First Problem Isolation");
   - the MongoDB TestContainers isolation's "not the solution": never disable DevServices globally;
   - native (GraalVM) builds (from `java-orchestration.md`, §S3).

   It restates nothing `quarkus.toml` states.
4. Every role of the `quarkus` stack lists `java-stack` in its `skills`.

## §S2 — The references move

1. The five files move verbatim into the skill's references, apart from §S4's rewordings; none stays in
   `skills-src/memory-templates/`. Each one's opening provenance line no longer says it is scaffolded
   into `docs/memory/`.
2. `init` seeds none of the five into `docs/memory/` and writes no index line for one, for either the
   `quarkus` or the `java` stack; it still seeds `java-orchestration.md` (CR-MDB-060's).
3. Every cross-reference among the moved files and the templates names the reference's new home.

## §S3 — `java-orchestration.md`: every agent-facing section leaves it

By CR-MDB-085's rule: to the skill when only some tasks need it, into `quarkus.toml` when every phase
needs it and it is not stated there, or deleted when `quarkus.toml` already states it. Each row's
anchor phrase is how its move is checked.

| Section or bullet | Anchor | Goes to |
|---|---|---|
| "Tooling": the `mvn-crucible.py` bullet's agent verbs, common flags and project resolution | `` `unit --test <Class[#method]>` ``, `Common flags:`, `No project hardcoded` | deleted (stated in `quarkus.toml`'s test command and mechanics) |
| "The four test tiers" | — (the heading) | deleted (stated in `quarkus.toml`) |
| "RED that won't compile" | `A Java RED frequently fails to **compile**` | deleted (stated in `quarkus.toml`) |
| "Layered enterprise architecture": its intro | `Migration/implementation is **bottom-up` | deleted (stated in `quarkus.toml`'s GREEN gotchas) |
| The shared-library reuse paragraph | `Reuse shared-library components` | deleted (stated in `quarkus.toml`'s GREEN gotchas) |
| The RediSearch paragraph | `TAG-field queries` | `references/quarkus-patterns.md` |
| "Quarkus build + test gotchas": native builds | `RAM-heavy and slow` | `SKILL.md` |
| …: DevServices isolation, `@Nested`, surefire versus failsafe, the console, the reactor | ``restrictToAnnotatedClass = true)` for isolation``, `` can throw `ClassCastException` ``, `` surefire runs `*Test.java` ``, `Don't parse mvn console output`, `**Multi-module reactor**` | deleted (stated in `quarkus.toml`) |
| Preamble, "Tooling" (the orchestrator's verbs, `worktree-flow.py`, scheduling, the split, the `crucible` skill), "Pre-merge gate", "JaCoCo — read the RIGHT report", "Planning the layers", "Disk / cache hygiene" | — | stays |

A heading left with no body is removed. The preamble names where the agent-facing material went (the
quarkus agent definitions and the `java-stack` skill), never a `generator/` path, and no longer says
the quarkus definitions reference all four files.

## §S4 — Rewordings the move requires

1. **No project named (§D25):** `org.fourpm` (any package under it), `fourpm`, `store-utils` and
   `4pm-Store-utils` become neutral examples. The rest of one project's architecture stays as written
   for CR-MDB-087.
2. **The test-run rule (§D21):** a form the raw-runner guard's rules match that an agent runs becomes
   the stack client's verb; a descriptive or checklist form is reworded or dropped.
3. No reference names a `ctx_*` or lean-ctx tool.

## §S5 — `quarkus.toml`

1. "Companion memory" names the `java-stack` skill and no `docs/memory/` or template path.
2. The four bare citations — `@TempDir` (`java-testing-practices.md`), the code-quality rule
   (`java-coding-standards.md`), the test-quality checks and the fix table's test-quality row
   (`java-testing-practices.md`) — name the skill's reference instead.
3. Its provenance header names no template path.

## §S6 — The reach

1. **Tests keyed on the moved files**, repointed: `test_claude_era_retirement` (`MemoryTemplateFamilyTest`),
   `test_client_path_anchoring`, `test_harness_neutral_skills`, `test_memory_model`,
   `test_project_registry_schema` (its seeded templates), `test_installer_assets`, `test_scaffold`,
   `test_cr_authoring_skill`, `test_board_holds_the_queue`, `test_tooling_detachment`,
   `test_worktree_flow_surfaces` and `test_orchestrator_rule_triage`, each where it reads a moved file
   or section.
2. **`archive/mapping.md`:** the five-Java-references row and the `devops-environment.md` row name the
   new location (row 57's "remains in `~/.claude/memory/`" wording kept), and a row maps each old
   `skills-src/memory-templates/java-*.md` path to its reference.
3. The generated quarkus definitions are re-rendered; this repository's `.pi/agents` (python) is
   unchanged.

## Acceptance criteria

- [ ] **AC1 (§S1.1–2, §S2.1).** `generator/stack-skills.toml` declares `java-stack` for `quarkus` and
      `java`; `generator/skills/java-stack/` holds `SKILL.md` and exactly the five references §S1.2
      names; `skills-src/memory-templates/` holds none of the five source files; no moved reference's
      provenance line names `docs/memory/`.
- [ ] **AC2 (§S1.3).** `SKILL.md` names each of the five references by its path; it carries the three
      rules §S1.3 lists (anchors `Test-First Problem Isolation` or its rule, `DevServices globally`,
      native builds); none of the eight §S1.3 inline items is restated in it.
- [ ] **AC3 (§S1.4, §S5).** Every rendered quarkus definition's skills line names `java-stack`;
      `quarkus.toml` contains no `docs/memory/` path, no `memory-templates/` path, and no bare
      `java-testing-practices.md`, `java-coding-standards.md` or `java-orchestration` name.
- [ ] **AC4 (§S2.2).** `init --stacks quarkus` and `init --stacks java` (sandboxed) each write
      `.agents/skills/java-stack/` with its five references, seed no `docs/memory/java-*.md` reference
      and no index line for one, and still seed `docs/memory/java-orchestration.md`.
- [ ] **AC5 (§S3).** Each §S3 row holds by its anchor phrase: present in its destination and absent
      from `java-orchestration.md` where it moves or is deleted; present where it stays. No heading in
      the template is left without a body; its preamble names no `generator/` path.
- [ ] **AC6 (§S2.3, §S4).** No moved file or template names a moved reference by its old path or bare
      old name; `generator/skills/` contains no `org.fourpm`, `fourpm`, `store-utils` or
      `4pm-Store-utils`; the raw-runner guard over `generator/skills/` finds nothing; no `ctx_` tool or
      lean-ctx is named there.
- [ ] **AC7 (§S6).** `archive/mapping.md` carries the §S6.2 rows and its gate passes; each §S6.1 test
      passes against the moved files.
- [ ] **AC8.** The skill-frontmatter and Pi skill-loader checks pass over `generator/skills/java-stack/`
      and a rendered `.agents/skills/java-stack/`; `generator/build.py --check` is clean; this
      repository's `.pi/agents` matches the regeneration; the full suite passes through the Crucible
      client.

## Non-goals

- The rest of one project's architecture in the Java material — CR-MDB-087 (1.1.0).
- Retiring `docs/memory/`, `java-orchestration.md`'s orchestrator-facing notes as facts, and the skills
  that read `INDEX.md` — CR-MDB-060.
- Re-rendering existing projects, and their `docs/memory/java-*.md` copies — `modelb-axi agents`
  re-renders on demand; `migrate` is CR-MDB-082.
