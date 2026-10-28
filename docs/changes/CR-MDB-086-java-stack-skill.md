# CR-MDB-086 — The Java stack skill: the Java references and mechanics, rendered into Java projects

**Status:** PENDING — spec drafted 2026-10-28 from the gap analysis, the spec pre-review folded in;
awaiting approval.
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
the `java-orchestration` template, and five more lines cite a reference by bare name. Three references
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

3. **`SKILL.md`** routes by topic to each reference by its path, and carries the rules the agents need
   that `quarkus.toml` does not state. The references mark their binding sections (NON-NEGOTIABLE,
   CRITICAL, MANDATORY). Of the ten in the coding standards and testing practices, eight are stated in
   `quarkus.toml` — code formatting, import usage, unused imports, error handling and warnings, the Java
   TDD cycle, the MongoDB TestContainers isolation, the surefire and failsafe reports, `@TempDir` with
   `@QuarkusTest` (the formatting and import rules in the GREEN, VERIFY and FIX gotchas) — and one by the
   sub-agent procedure every definition carries (the TDD workflow). `SKILL.md` carries, each as a
   compressed rule under its anchor:

   | Rule | From | Anchor in `SKILL.md` |
   |---|---|---|
   | Test-first problem isolation | testing practices, "CRITICAL: Test-First Problem Isolation" | `Test-First Problem Isolation` |
   | Never disable DevServices globally to cure a hang | testing practices, "Test Hanging Root Cause" | `DevServices globally` |
   | Removing a method: check its unit and integration tests | testing practices' inline CRITICAL | `unit tests AND integration tests` |
   | Native (GraalVM) builds, the native package built before a failsafe-only run | `java-orchestration.md` (§S3) | `RAM-heavy and slow` |
   | Check docker is clean before native or JVM e2e cycles | `java-orchestration.md` (§S3) | `docker is clean` |
   | The client's task-specific flags: `unit --test <Class>#<method>`, `--also-make`, `--native`, `--profile`, `--system-prop`, `--update-snapshots`, `--coverage-profile`; the monorepo backend's `CRUCIBLE_MAVEN_DIR` | `java-orchestration.md` (§S3) | `--also-make` |

   Nothing `quarkus.toml` states is restated: no line of 40 or more characters from `quarkus.toml`
   appears verbatim in `SKILL.md`.
4. Every role of the `quarkus` stack lists `java-stack` in its `skills`.

## §S2 — The references move

1. The five files move verbatim into the skill's references, apart from §S4's rewordings; none stays in
   `skills-src/memory-templates/`. Each one's opening provenance line names it as a `java-stack`
   reference, not a memory template scaffolded into `docs/memory/`.
2. `init` seeds none of the five into `docs/memory/` and writes no index line for one, for either the
   `quarkus` or the `java` stack; it still seeds `java-orchestration.md` (CR-MDB-060's). The
   memory-template families' comment in `modelb_axi/scaffold.py` no longer says the quarkus definitions
   read the `java-*` templates. The references reach a project only where Pi renders its agents — the
   harness roster is Pi alone, so a Java project receives them wherever it receives agents.
3. Every cross-reference among the moved files and the templates names the reference's new home. The
   stack-neutral `operational-commands.md`, seeded into every project, drops its "Related" line naming
   two Java references.

## §S3 — `java-orchestration.md`: every agent-facing section leaves it

By CR-MDB-085's rule: to the skill when only some tasks need it, into `quarkus.toml` when every phase
needs it and it is not stated there, or deleted when `quarkus.toml` already states it. Each row's
anchor phrase is how its move is checked.

| Section or bullet | Anchor | Goes to |
|---|---|---|
| "Tooling": the `mvn-crucible.py` bullet's `unit`, `module`, `compile` and `e2e` verbs | `` `unit --test <Class[#method]>` ``, `` `module [--module <m> --also-make]` ``, `` `compile` — `mvn clean test-compile` ``, `` `e2e [--failsafe-only] `` | deleted (stated in `quarkus.toml`'s test command, mechanics and tiers) |
| "Tooling": its common flags | `Common flags:` | the task-specific ones to `SKILL.md` (§S1.3), the line deleted |
| "Tooling": its `register` verb, project resolution and optional `.env` keys | `` `register --role ``, `No project hardcoded` | stays (orchestrator) |
| "The four test tiers" | — (the heading) | deleted (stated in `quarkus.toml`) |
| "RED that won't compile" | `A Java RED frequently fails to **compile**` | deleted (stated in `quarkus.toml`) |
| "Layered enterprise architecture": its intro | `Migration/implementation is **bottom-up` | deleted (stated in `quarkus.toml`'s GREEN gotchas) |
| The shared-library reuse paragraph | `Reuse shared-library components` | deleted (stated in `quarkus.toml`'s GREEN gotchas) |
| The RediSearch paragraph | `TAG-field queries` | `references/quarkus-patterns.md` |
| "Quarkus build + test gotchas": native builds | `RAM-heavy and slow` | `SKILL.md` |
| …: the DevServices bullet's docker-clean check | `Check docker is clean before native/JVM e2e cycles` | `SKILL.md` |
| …: the DevServices isolation itself, `@Nested`, surefire versus failsafe, the console, the reactor | ``restrictToAnnotatedClass = true)` for isolation``, `` can throw `ClassCastException` ``, `` surefire runs `*Test.java` ``, `Don't parse mvn console output`, `**Multi-module reactor**` | deleted (stated in `quarkus.toml`) |
| Preamble, "Tooling" (the orchestrator's verbs, `worktree-flow.py`, scheduling, the split, the `crucible` skill), "Pre-merge gate", "JaCoCo — read the RIGHT report", "Planning the layers", "Disk / cache hygiene" | — | stays |

A heading is left without a body when it has neither text nor a sub-heading under it, and is then
removed: "Layered enterprise architecture" keeps "Planning the layers" as its sub-heading and stays;
"Quarkus build + test gotchas" and "The four test tiers" go. The preamble names where the
agent-facing material went (the quarkus agent definitions and the `java-stack` skill), never a
`generator/` path, and no longer says the quarkus definitions reference all four files. No count of
test tiers is left in the template.

## §S4 — Rewordings the move requires

1. **No project named (§D25):** `org.fourpm` (any package under it), `fourpm`, `store-utils` and
   `4pm-Store-utils` become neutral examples, in the moved references and in `quarkus.toml` (its GREEN
   shared-libraries gotcha). The rest of one project's architecture stays as written for CR-MDB-087.
2. **The test-run rule (§D21):** a form the raw-runner guard's rules match that an agent runs becomes
   the stack client's verb; a descriptive or checklist form is reworded or dropped. A failsafe `*IT`
   run names the client's `integration` verb, as `quarkus.toml`'s tiers do; a reworded form keeps
   what the original ran (a `verify` runs surefire and failsafe both, never "failsafe only").
3. No reference names a `ctx_*` or lean-ctx tool.

## §S5 — `quarkus.toml`

1. "Companion memory" names the `java-stack` skill and no `docs/memory/` or template path.
2. The five bare citations — RED's `@TempDir` and resource-layer/IT-tests bullets
   (`java-testing-practices.md`), the code-quality rule (`java-coding-standards.md`), VERIFY's
   test-quality checks and FIX's test-quality row (`java-testing-practices.md`) — each name the skill's
   reference by its path (`references/testing-practices.md`, `references/coding-standards.md`).

## §S6 — The reach

1. **Tests keyed on the moved files**, repointed: `test_claude_era_retirement` (`MemoryTemplateFamilyTest`),
   `test_client_path_anchoring`, `test_harness_neutral_skills`, `test_memory_model`,
   `test_project_registry_schema` (its seeded templates), `test_installer_assets`, `test_scaffold`,
   `test_cr_authoring_skill`, `test_board_holds_the_queue`, `test_tooling_detachment`,
   `test_worktree_flow_surfaces` and `test_orchestrator_rule_triage`, each where it reads a moved file
   or section; `test_stack_reference_material` (its declaration, its quarkus render, its "no other
   stack names a stack skill" check and its project-name examples generalised to take `java-stack`,
   not cloned) and `test_pi_agent_definitions` (its quarkus skills rows); `test_skill_frontmatter`
   renders `java-stack` beside `rust-stack` for its rendered-skill checks;
   `test_project_registry_schema`'s registry-key allowlist drops a name no shipped text uses any more.
2. **`archive/mapping.md`:**
   - one row per old path, `` `skills-src/memory-templates/java-<name>.md` ``, kind `moved`, Now the
     reference file it became, Moved-by `CR-MDB-086`;
   - the `~/.claude/memory/devops-environment.md` row and the five-Java-references family row each gain
     `CR-MDB-086` in Moved-by and name the new location in Now and Authority (the family row keeping its
     "remain in `~/.claude/memory/`" wording; the `devops-environment.md` row no longer saying the file
     became a memory template);
   - `tests/test_archive_mapping.py`'s required old paths include the five.
3. The generated quarkus definitions are re-rendered; this repository's `.pi/agents` (python) is
   unchanged.

## Acceptance criteria

- [ ] **AC1 (§S1.1–2, §S2.1).** `generator/stack-skills.toml` declares `java-stack` for `quarkus` and
      `java`; `generator/skills/java-stack/` holds `SKILL.md` and exactly the five references §S1.2
      names; `skills-src/memory-templates/` holds none of the five source files; no moved reference's
      provenance line names `docs/memory/` or calls it a memory template.
- [ ] **AC2 (§S1.3).** `SKILL.md` names each of the five references by its path; it carries each
      §S1.3 table row by its anchor; its native-build rule names the native package built before a
      `--failsafe-only` run, or uses the one-step `e2e --native`; no line of 40 or more characters from
      `quarkus.toml` appears verbatim in it.
- [ ] **AC3 (§S1.4, §S4.1, §S5).** Every rendered quarkus definition's skills line names `java-stack`;
      `quarkus.toml`'s "Companion memory" bullet names `java-stack`, and each of the five §S5.2 places
      names `references/testing-practices.md` or `references/coding-standards.md`; `quarkus.toml`
      contains no `docs/memory/` path, no `memory-templates/` path, no bare `java-testing-practices.md`,
      `java-coding-standards.md` or `java-orchestration` name, and no `store-utils`.
- [ ] **AC4 (§S2.2).** `init --stacks quarkus` and `init --stacks java` (sandboxed, with the Pi harness) each write
      `.agents/skills/java-stack/` with its five references, seed no `docs/memory/java-*.md` reference
      and no index line for one, and still seed `docs/memory/java-orchestration.md`.
- [ ] **AC5 (§S3).** Each §S3 row holds by its anchor phrase: present in its destination and absent
      from `java-orchestration.md` where it moves or is deleted; present where it stays. No heading in
      the template is left with neither text nor a sub-heading; "Layered enterprise architecture"
      stays with "Planning the layers" under it; the preamble names the `java-stack` skill, names no
      `generator/` path, and no longer says the quarkus definitions reference all four files; no count
      of test tiers is left in it.
- [ ] **AC6 (§S2.3, §S4).** No moved file or template names a moved reference by its old path or bare
      old name; `operational-commands.md` names no Java reference; `generator/skills/` contains no `org.fourpm`, `fourpm`, `store-utils` or
      `4pm-Store-utils`; the raw-runner guard over `generator/skills/` finds nothing; no `ctx_` tool or
      lean-ctx is named there; no reference sends a failsafe `*IT` run to `e2e` or calls a `verify` run
      "failsafe only".
- [ ] **AC7 (§S6).** `archive/mapping.md` carries the §S6.2 rows, its required old paths include the
      five, and its gate passes; each §S6.1 test passes against the moved files, the registry-key
      allowlist names no `DD`, `scaffold.py`'s
      memory-template families' comment names no quarkus reading of the `java-*` templates.
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
