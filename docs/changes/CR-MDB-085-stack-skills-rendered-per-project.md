# CR-MDB-085 — Stack skills: each stack's reference material, rendered into its projects

**Status:** PENDING — **SEED, not the finished spec** (filed 2026-10-28 into release 1.0.0, wave 2).
Gap analysis, the spec and its pre-review happen in order when this CR starts.
**Type:** feature (generator, scaffold, stack files, reference material)
**Priority:** P1 — release 1.0.0, wave 2, before CR-MDB-060.
**Depends on:** none known; the board is authoritative: read `queue`, not this line.
**Labels:** stacks, skills, generator, scaffold, references
**Design reference:** PRD D5, amendment of 2026-10-28 (material placed by its readers; the stack
skill) and its containment rule; DN-multi-harness-deploy-model §D21 (every test run goes through the
client) and §D25 (a stack carries what holds for every project on it); Pi's skills documentation (a
skill bundles `references/` read on demand; a project's `.agents/skills/` is discovered).

## Context

A stack's agents are pointed at reference material that lives in `docs/memory/`: `quarkus.toml` cites
`docs/memory/java-testing-practices.md`, `docs/memory/java-coding-standards.md` and the
`java-orchestration` template, and `rust.toml` cites the `rust-orchestration` template. Three more Java
references (`java-modern-syntax`, `java-maven-best-practices`, `java-quarkus-patterns`, about 3,000
lines) are cited by nothing an agent reads. CR-MDB-060 retires `docs/memory/`, so this material needs
a home that its readers load. A Pi skill fits: only its name and description reach the prompt, its
`SKILL.md` is read when a task matches, and its `references/` are read when `SKILL.md` points to them.

## Scope (seed)

1. **The mechanism, for every stack.** A stack may ship a stack skill (`SKILL.md` plus `references/`)
   from a new asset root that ships in the wheel. `init` renders it into each project of that stack
   under `.agents/skills/`, under the same ownership rules as the rendered agent definitions, and the
   path that re-renders a project's agents re-renders it. The stack's roles list it in their
   `skills`. A stack with no material ships none.
2. **The Java stack skill.** Its `SKILL.md` carries the binding rules of the coding standards and the
   testing practices, compressed, and routes by topic to `references/`: testing practices, coding
   standards, modern syntax, Maven, Quarkus patterns. The agent-facing mechanics of
   `java-orchestration` join it.
3. **The rust and arduino stack skills:** the agent-facing mechanics of `rust-orchestration` and
   `arduino-orchestration`. Their orchestrator-facing notes stay for CR-MDB-060's seeds.
4. **The test-run rule reaches the material** (§D21): no stack skill teaches a runner invocation; the
   references' runner commands (71 today) become the stack client's verbs.
5. **The stack files stop citing `docs/memory/` and template paths**; the roles list the stack skill
   instead. The generated definitions are re-rendered.
6. **The guards cover the stack skills:** Pi's skill loader reads them with no diagnostics, their
   frontmatter stays within Pi's limits, and the shipped-text guards (the raw-runner guard, the AXI
   envelope guard) read them.

## To measure at gap analysis

- Which parts of each template are agent-facing (stack skill) and which orchestrator-facing (CR-060's
  seeds), section by section.
- The asset root and its place in `pyproject.toml`'s `force-include`; the render path in `init` and
  in `modelb-axi agents`; the skill's name and description under Pi's limits and the containment rule.
- **Boundaries:** CR-MDB-060 removes `docs/memory/` after this CR; CR-MDB-082 (`migrate`) re-renders a
  governed project; CR-MDB-084 (1.1.0) makes the arduino material general to every Arduino project.
- **Score:** seeded at 8.
