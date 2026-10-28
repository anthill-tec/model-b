# CR-MDB-086 — The Java stack skill: the Java references and mechanics, rendered into Java projects

**Status:** PENDING — **SEED, not the finished spec** (filed 2026-10-28 into release 1.0.0, wave 2).
Gap analysis, the spec and its pre-review happen in order when this CR starts.
**Type:** feature (stack skill content, stack file, scaffold seeding, reference material)
**Priority:** P1 — release 1.0.0, wave 2, after CR-MDB-085 and before CR-MDB-060.
**Depends on:** CR-MDB-085 (the stack-skill mechanism); the board is authoritative: read `queue`, not
this line.
**Labels:** stacks, skills, java, quarkus, references
**Design reference:** PRD D5, amendment of 2026-10-28 (the language references stay documents; the
stack skill; `java-stack` rendered for the `quarkus` and `java` stacks; no project named); CR-MDB-085
(the mechanism, its ownership markers, gates and triage rule); DN-multi-harness-deploy-model §D21,
§D25.

## Context

The quarkus agents are pointed at `docs/memory/java-testing-practices.md`,
`docs/memory/java-coding-standards.md` and the `java-orchestration` template; three more Java
references — `java-modern-syntax`, `java-maven-best-practices`, `java-quarkus-patterns`, about 3,000
lines — are read by no agent. A `java` project (no stack file, no agents) receives the references
through `docs/memory/` today. CR-MDB-085 builds the stack-skill mechanism; this CR gives the Java
material its skill.

## Scope (seed)

1. **`java-stack`**, declared for the `quarkus` and `java` stacks: `SKILL.md` carries the binding rules
   of the coding standards and testing practices, compressed, restating nothing `quarkus.toml` states,
   and routes by topic to `references/`: testing practices, coding standards, modern syntax, Maven,
   Quarkus patterns. Every quarkus role lists it in its `skills`.
2. **The five references move** from `skills-src/memory-templates/` (by name: `java-coding-standards`,
   `java-testing-practices`, `java-modern-syntax`, `java-maven-best-practices`, `java-quarkus-patterns`)
   verbatim apart from the rewordings below; `java-orchestration.md` stays a template. `init` stops
   seeding the five into `docs/memory/`; their reference provenance lines no longer say they are
   scaffolded into `docs/memory/`.
3. **`java-orchestration.md`'s agent-facing sections leave it,** by CR-MDB-085's rule: to the skill, to
   `quarkus.toml` (only what it does not state), or deleted where `quarkus.toml` already states them
   (measured at the second pre-review: "RED that won't compile", bottom-up layering, shared-library
   reuse, the multi-module reactor and monorepo notes, the `register` verb's role/cycle text). Text
   left in the template that names a moved file names its new home.
4. **`quarkus.toml`** cites the Java material only through `java-stack`: no `docs/memory/` path, no
   template path, no bare reference name.
5. **No project's names** (§D25): `org.fourpm.*`, `store-utils` and `4pm-Store-utils` become neutral
   examples. The remaining project-specific architecture is CR-MDB-087's (1.1.0).
6. **The test-run rule** (§D21): an agent-run form the raw-runner guard matches becomes the client's
   verb; the Maven reference's descriptive and checklist forms are reworded or dropped.
7. **The reach:** `archive/mapping.md` rows for the moved references and sections (row 57's "remains in
   `~/.claude/memory/`" wording kept); the tests keyed on the moved paths
   (`test_claude_era_retirement.MemoryTemplateFamilyTest`, `test_client_path_anchoring`,
   `test_harness_neutral_skills`, `test_memory_model`, `test_project_registry_schema`,
   `test_installer_assets`); the generated definitions re-rendered.

## To measure at gap analysis

- Each `java-orchestration.md` section and bullet against the live `quarkus.toml`, with an anchor
  phrase per row so the move is checkable.
- The runner forms in the references (19 at the second pre-review) and which are agent runs.
- **Score:** seeded at 8.
