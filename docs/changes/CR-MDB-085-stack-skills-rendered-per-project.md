# CR-MDB-085 — Stack skills: each stack's reference material, rendered into its projects

**Status:** PENDING — spec drafted 2026-10-28 from the gap analysis; awaiting the spec pre-review and
approval.
**Type:** feature (generator, scaffold, stack files, reference material)
**Priority:** P1 — release 1.0.0, wave 2, before CR-MDB-060.
**Depends on:** none known; the board is authoritative: read `queue`, not this line.
**Labels:** stacks, skills, generator, scaffold, references
**Design reference:** PRD D5, amendment of 2026-10-28 (material placed by its readers; the stack
skill) and its containment rule; DN-multi-harness-deploy-model §D17 (agents rendered per project),
§D21 (every test run goes through the client) and §D25 (a stack carries what holds for every project
on it); Pi's skills documentation (a skill's `references/` are read when `SKILL.md` points to them; a
project's `.agents/skills/` is discovered from the working directory up to the repository root);
pi-subagents (a child builds its skills catalogue from its own directory).

## Context

A stack's agents are pointed at reference material in `docs/memory/`. `quarkus.toml`'s "Companion
memory" bullet cites `docs/memory/java-testing-practices.md`, `docs/memory/java-coding-standards.md`
and the `java-orchestration` template; `rust.toml` cites the `rust-orchestration` template. Three Java
references — `java-modern-syntax`, `java-maven-best-practices`, `java-quarkus-patterns`, about 3,000
lines — are cited by nothing an agent reads. CR-MDB-060 retires `docs/memory/`.

A Pi skill gives this material a home its readers load. Only a skill's name and description reach the
prompt; its `SKILL.md` is read when a task matches; its `references/` are read when `SKILL.md` points
to them. A skill rendered into a project's `.agents/skills/` reaches only that project's sessions, and a
sub-agent's catalogue, built from its own directory, includes it. A definition already tells its agent
which skills to load: a role's `skills` list in the stack file renders as the body line "Load these
skills first: …".

## §S1 — The mechanism

1. A stack skill's source is `generator/skills/<stack>/`: a `SKILL.md` and a `references/` directory.
   `generator/` already ships in the wheel; the installer deploys nothing from it.
2. The stack skill's name is `<stack>-stack` (`quarkus-stack`, `rust-stack`, `arduino-stack`).
3. `modelb-axi init` renders the stack skill of each stack in `--stacks` that has one into the
   project's `.agents/skills/<stack>-stack/`, at the project root, under the ownership rules of the
   rendered agent definitions: each file carries Model B's generated marker; a hand-modified file is
   skipped and reported; an unmarked file is never written. `--dry-run` writes nothing. The rendered
   files are tracked, so every worktree carries them.
4. `modelb-axi agents` re-renders the stack skills with the agent definitions, by the same rules.
5. A stack with no source ships no stack skill; an empty skill is never rendered.

## §S2 — The definitions load it

Every role of a stack with a stack skill lists it in its `skills`, so its definition's body line names
it, e.g. "Load these skills first: crucible, quarkus-stack." A definition never restates what its stack
skill carries, and a stack skill never restates what the definition carries inline.

## §S3 — The Java stack skill (`quarkus`)

1. `SKILL.md` carries the binding rules of the coding standards and the testing practices, compressed,
   and routes by topic to `references/`: testing practices, coding standards, modern syntax, Maven,
   Quarkus patterns, and the agent-facing Maven mechanics.
2. The five `java-*.md` references move from `skills-src/memory-templates/` into the skill's
   `references/`; they are not kept in both places.
3. From `java-orchestration.md`, the agent-facing sections join the skill: the four test tiers, "RED
   that won't compile", the Quarkus build and test gotchas, and the client tooling an agent runs. The
   orchestrator-facing sections stay in the template for CR-MDB-060: planning the layers, the pre-merge
   gate, the JaCoCo report, disk and cache hygiene.
4. `quarkus.toml`'s "Companion memory" bullet cites no `docs/memory/` path and no template path.

## §S4 — The rust and arduino stack skills

1. **rust:** from `rust-orchestration.md`, the RED/GREEN/VERIFY additions, the e2e, docker and
   nextest gotchas, the flaky-test principle and test naming join the skill. The tooling, test scope,
   pre-merge gate, disk hygiene and `CARGO_BUILD_JOBS` sections stay in the template. `rust.toml`
   cites no template path.
2. **arduino:** from `arduino-orchestration.md`, the hardware-driver rules join the skill; the note on
   raising a new tier to Model B stays in the template.

## §S5 — The test-run rule reaches the skills

No stack skill teaches a runner invocation (DN-multi-harness-deploy-model §D21): every form the
raw-runner guard's rules match — a Maven `test`, `verify`, `integration-test` or `test-compile` goal,
`cargo test`/`nextest`/`llvm-cov`, and the others it lists — becomes the stack client's verb. Build
tooling the guard does not match (`compile`, `install`, `dependency:tree`, `versions:*`) stays.

## §S6 — The guards and the docs

1. The raw-runner guard and the AXI envelope guard read `generator/skills/`.
2. The skill-frontmatter checks and the Pi skill-loader check read `generator/skills/`: no
   diagnostics, one skill per stack directory, the name and description within Pi's limits, and no
   name shared with a bundle in `skills-src/`.
3. `AGENTS.md` § Key Directories names `generator/skills/`; `archive/mapping.md` carries a row for every
   moved path it maps.

## Acceptance criteria

- [ ] **AC1 (§S1).** `generator/skills/` holds exactly `quarkus/`, `rust/` and `arduino/`, each with a
      `SKILL.md` whose frontmatter `name` is `<stack>-stack`, and a `references/` directory. `init
      --stacks quarkus` (sandboxed) writes `.agents/skills/quarkus-stack/SKILL.md` and its references,
      each carrying the generated marker; `init --stacks python` and `--stacks bun` write no
      `.agents/skills/`; `--dry-run` writes nothing; a hand-modified rendered file is skipped and
      reported by both `init` and `modelb-axi agents`.
- [ ] **AC2 (§S1.4).** `modelb-axi agents` in a project scaffolded with `--stacks quarkus,rust` renders
      both stack skills, and a second run changes nothing.
- [ ] **AC3 (§S2).** Every rendered quarkus, rust and arduino definition's body line names
      `<stack>-stack` among the skills to load; no python or bun definition names a stack skill.
- [ ] **AC4 (§S3).** `skills-src/memory-templates/` holds no `java-coding-standards.md`,
      `java-testing-practices.md`, `java-modern-syntax.md`, `java-maven-best-practices.md` or
      `java-quarkus-patterns.md`; `generator/skills/quarkus/references/` holds each, and `SKILL.md`
      routes to each by name. `quarkus.toml` and `rust.toml` contain no `docs/memory/` and no
      `memory-templates/` path.
- [ ] **AC5 (§S3.3, §S4).** Each section §S3.3 and §S4 move is in its stack skill and no longer in its
      template; each section they keep is still in its template.
- [ ] **AC6 (§S5).** The raw-runner guard, with `generator/skills` in its guarded roots, finds nothing.
- [ ] **AC7 (§S6).** The AXI envelope guard reads `generator/skills/`; the skill-frontmatter and Pi
      skill-loader checks over it pass with no diagnostics; `AGENTS.md` names `generator/skills/`.
- [ ] **AC8.** `generator/build.py --check` is clean, this repository's `.pi/agents` matches the
      regeneration, and the full suite passes through the Crucible client.

## Non-goals

- Retiring `docs/memory/`, the knowledge seeds and the skills that read `INDEX.md` — CR-MDB-060.
- Re-rendering existing projects — `modelb-axi agents` re-renders on demand; `migrate` is CR-MDB-082.
- The arduino material's generality to every Arduino project — CR-MDB-084 (1.1.0).
- Python and bun stack skills — neither has material for one.
