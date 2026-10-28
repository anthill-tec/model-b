# CR-MDB-085 — Stack skills: each stack's reference material, rendered into its projects

**Status:** PENDING — spec drafted 2026-10-28 from the gap analysis, the spec pre-review folded in;
awaiting approval.
**Type:** feature (generator, scaffold, stack files, reference material, gates)
**Priority:** P1 — release 1.0.0, wave 2, before CR-MDB-060.
**Depends on:** none known; the board is authoritative: read `queue`, not this line.
**Labels:** stacks, skills, generator, scaffold, references
**Design reference:** PRD D5, amendment of 2026-10-28 (material placed by its readers; the stack
skill) and its containment rule; DN-multi-harness-deploy-model §D17 (agents rendered per project),
§D21 (every test run goes through the client) and §D25 (shipped material names no project); Pi's
skills documentation (a skill's `references/` are read when `SKILL.md` points to them; a project's
`.agents/skills/` is discovered from the working directory up to the repository root, once the
project is trusted); pi-subagents (a child builds its skills catalogue from its own directory).

## Context

A stack's agents are pointed at reference material in `docs/memory/`. `quarkus.toml` cites
`docs/memory/java-testing-practices.md`, `docs/memory/java-coding-standards.md` and the
`java-orchestration` template; `rust.toml` cites the `rust-orchestration` template. Three Java
references — `java-modern-syntax`, `java-maven-best-practices`, `java-quarkus-patterns`, about 3,000
lines — are cited by nothing an agent reads. CR-MDB-060 retires `docs/memory/`.

A Pi skill gives this material a home its readers load. Only a skill's name and description reach the
prompt; its `SKILL.md` is read when a task matches; its `references/` are read when `SKILL.md` points
to them. A skill rendered into a project's `.agents/skills/` reaches only that project's sessions, and
a sub-agent's catalogue, built from its own directory, includes it (a worktree child finds the tracked
copy in its worktree). A definition already tells its agent which skills to load: a role's `skills`
list in the stack file renders as the body line "Load these skills first: …".

## §S1 — The mechanism

1. A stack skill's source is `generator/skills/<name>/`, its directory named as its frontmatter
   `name`: a `SKILL.md`, and a `references/` directory only when the skill has references.
   `generator/` ships in the wheel; the installer deploys nothing from it. The source resolves through
   the same asset-root chain as the agent sources (packaged first, then the repository).
2. **Two stack skills now:** `java-stack`, rendered for the `quarkus` and the `java` stacks, and
   `rust-stack`, rendered for the `rust` stack. No other stack has one (§S4).
3. `modelb-axi init` renders the stack skill of each stack in `--stacks` that has one into
   `.agents/skills/<name>/` at the project root — never in a sub-project — under the ownership rules of
   the rendered agent definitions: `SKILL.md` carries Model B's generated marker inside its frontmatter;
   each reference carries it as its first line (the first-line form CR-MDB-068 introduced); a
   hand-modified file is skipped and reported; an unmarked file is never written. `--dry-run` writes
   nothing. The rendered files are tracked, so every worktree carries them.
4. `modelb-axi agents` re-renders the stack skills with the agent definitions, by the same rules and
   at the project root, from any working directory in the project. A re-render writes and never
   deletes: a stack skill for a stack the project no longer lists stays where it is.
5. A stack with no source ships no stack skill; an empty skill is never rendered.
6. `AGENTS.md`'s rendered stack line names the stack's skill (`java-stack`, `rust-stack`), and the
   project-trust warning names the stack skills among what an untrusted project does not load.

## §S2 — The definitions load it, and nothing is said twice

1. Every role of the `quarkus` stack lists `java-stack`, and every role of the `rust` stack lists
   `rust-stack`, in its `skills`, so each definition's body line names it, e.g. "Load these skills
   first: crucible, java-stack."
2. What every phase always needs stays inline in the stack file (PRD D5). A moved section carries only
   what its stack file does not already state; a sentence the stack file states is dropped from the
   moved text, never restated. Already inline in `quarkus.toml`, so not moved: the four test tiers,
   `clean` on every test run, not parsing the console, DevServices with `restrictToAnnotatedClass`,
   `@Nested` with continuous testing, surefire versus failsafe, test naming.

## §S3 — The Java stack skill

1. **`SKILL.md`** carries the binding rules of the coding standards and the testing practices,
   compressed, and routes by topic to its references, each named: `references/testing-practices.md`,
   `references/coding-standards.md`, `references/modern-syntax.md`, `references/maven.md`,
   `references/quarkus-patterns.md`.
2. **The five `java-*.md` references move** from `skills-src/memory-templates/` into those files; they
   are not kept in both places. `init` then seeds no `java-*.md` into `docs/memory/` and no index line
   for one.
3. **From `java-orchestration.md`** (every heading named; a split heading names its bullets):

   | Section or bullet | Goes to |
   |---|---|
   | Preamble, "Tooling" bullets on `worktree-flow.py`, scheduling, the split, and the `crucible` skill | stays (orchestrator) |
   | "Tooling": the `mvn-crucible.py` bullet's `register`, `unit`, `module`, `compile`, `e2e` verbs, common flags and project resolution | `SKILL.md`, less what §S2.2 keeps inline |
   | "Tooling": the `regression`, `auto-ingest`, docker and `pre-merge-gate` verbs | stays |
   | "The four test tiers" | not moved (inline, §S2.2) |
   | "Pre-merge gate", "JaCoCo — read the RIGHT report", "Disk / cache hygiene" | stays |
   | "RED that won't compile" | `SKILL.md` |
   | "Layered enterprise architecture": its intro (bottom-up, one class at a time), the shared-library reuse rule and RediSearch | `SKILL.md` |
   | "Planning the layers" (the layer list and full order) | stays |
   | "Quarkus build + test gotchas": native builds, multi-module reactor and monorepo backend | `SKILL.md`, under a heading that does not call it orchestrator-side |

4. **No project is named** (§D25): the moved text names no project's packages, libraries or services —
   `org.fourpm.*`, `store-utils` and `4pm-Store-utils` become neutral examples.
5. `quarkus.toml` cites `java-testing-practices.md`, `java-coding-standards.md` and `java-orchestration`
   by no path or bare name; each citation names the `java-stack` skill or its reference.

## §S4 — rust and arduino

1. **The rust stack skill, `rust-stack`,** holds what only some tasks need: `SKILL.md` routes to
   `references/e2e-docker-nextest.md` (the "E2E / docker / nextest-concurrency gotchas", with the
   pre-merge gate's bullet that a new docker-dependent test joins both nextest default-filters) and
   carries the flaky-test investigation principle.
2. **Into `rust.toml` inline** (the RED, GREEN, FIX or VERIFY gotchas each fits), from
   `rust-orchestration.md`: the "RED/GREEN/VERIFY additions", the "Crucible ingest routing" paragraph
   and "Test naming" — less what `rust.toml` already states (compile-fail RED, skipped feature-gated
   tests, the `#[ignore]` ban, CR-named tests, `check --tests`). Everything else stays in the template.
   `rust.toml` cites no template path.
3. **arduino:** the two hardware-driver rules join `arduino.toml`'s GREEN and FIX gotchas inline; the
   note on raising a new tier to Model B stays in the template. No `arduino-stack` skill is rendered.

## §S5 — The test-run rule reaches the skill

No stack skill teaches a runner invocation (§D21): every form the raw-runner guard's rules match
becomes the stack client's verb. Build tooling the guard does not match (`compile`, `install`,
`dependency:tree`, `versions:*`) stays. A stack skill names no `ctx_*` or lean-ctx tool, because it
is not rendered in a built-in form as the definitions are.

## §S6 — The guards, the gates and the docs

1. **Gates whose roots gain `generator/skills/`:** the raw-runner guard, the AXI envelope guard, the
   skill-frontmatter checks and the Pi skill-loader check (no diagnostics, one skill per directory,
   name and description within Pi's limits, no name shared with a `skills-src/` bundle), and the
   shipped-text gates `test_tooling_detachment`, `test_deployed_script_invocation`,
   `test_project_registry_schema`, `test_worktree_flow_surfaces` and `test_board_holds_the_queue`.
2. **Path-keyed tests repointed** to the moved files: `test_client_path_anchoring`,
   `test_harness_neutral_skills`, `test_memory_model`, `test_project_registry_schema` (its seeded
   templates) and `test_installer_assets`.
3. **The orchestrator-rule triage:** the five rows of `audits/2026-09-26-orchestrator-rule-triage.md`
   whose destinations move (`rust-orchestration.md § RED/GREEN/VERIFY additions`, three rows;
   `arduino-orchestration.md § Hardware drivers`, two rows) name the new destinations under a dated
   amendment note, and `test_orchestrator_rule_triage`'s destination rule accepts `generator/stacks/`.
4. **`archive/mapping.md`:** the five-Java-references row, the `devops-environment.md` row and the
   orchestration-templates row name the new locations, and a row maps each old
   `skills-src/memory-templates/java-*.md` path to its reference.
5. `AGENTS.md` § Key Directories names `generator/skills/`.

## Acceptance criteria

- [ ] **AC1 (§S1.1–3).** `generator/skills/` holds exactly `java-stack/` and `rust-stack/`, each with a
      `SKILL.md` whose frontmatter `name` is its directory's and a `references/` directory.
      `init --stacks quarkus` and `init --stacks java` (sandboxed) each write
      `.agents/skills/java-stack/SKILL.md` with the marker in its frontmatter and the five references,
      each with the marker as its first line; `init --stacks rust` writes `.agents/skills/rust-stack/`
      likewise; `--stacks python`, `bun` and `arduino` write no `.agents/skills/`; `--dry-run` writes
      nothing; a hand-modified rendered file is skipped and reported, and an unmarked file at a
      rendered path is left untouched, by both `init` and `modelb-axi agents`.
- [ ] **AC2 (§S1.4–5).** `modelb-axi agents` in a `--stacks quarkus,rust` project re-renders
      `java-stack` and `rust-stack` at the project root, from the root
      and from a sub-directory; a second run changes nothing; with `--stacks python` it deletes nothing.
      A synthetic empty stack-skill source renders nothing.
- [ ] **AC3 (§S1.6).** A scaffolded quarkus project's `AGENTS.md` stack line names `java-stack`, and a
      rust project's names `rust-stack`; the untrusted-project warning names the stack skills.
- [ ] **AC4 (§S2.1).** Every rendered quarkus definition's skills line names `java-stack` and every
      rust definition's names `rust-stack`; no other stack's definition names a stack skill.
- [ ] **AC5 (§S2.2, §S3.3, §S4).** Each section or bullet the §S3.3 table and §S4.1–3 move is in its
      destination and no longer in its template; each one they keep is still in its template; none of
      the §S2.2 and §S4.2 inline items is restated in a stack skill.
- [ ] **AC6 (§S3.1–2, §S3.5).** `skills-src/memory-templates/` holds no `java-*.md` reference;
      `generator/skills/java-stack/references/` holds the five named files, and `SKILL.md` routes to
      each by name. `init --stacks quarkus` seeds no `docs/memory/java-*.md`. `quarkus.toml` and
      `rust.toml` contain no `docs/memory/` path, no `memory-templates/` path and no bare
      `java-testing-practices.md`, `java-coding-standards.md` or `-orchestration.md` name.
- [ ] **AC7 (§S3.4).** `generator/skills/` contains no `org.fourpm`, `fourpm`, `store-utils` or
      `4pm-Store-utils`.
- [ ] **AC8 (§S5).** The raw-runner guard over `generator/skills/` finds nothing; `generator/skills/`
      names no `ctx_` tool and no lean-ctx.
- [ ] **AC9 (§S6.1).** Each gate §S6.1 names reads `generator/skills/`; the skill-frontmatter and Pi
      skill-loader checks over it pass with no diagnostics.
- [ ] **AC10 (§S6.3–5).** The five triage rows name their new destinations and
      `test_orchestrator_rule_triage` passes; `archive/mapping.md` carries the §S6.4 rows and its gate
      passes; `AGENTS.md` names `generator/skills/`.
- [ ] **AC11.** `generator/build.py --check` is clean, this repository's `.pi/agents` matches the
      regeneration, and the full suite passes through the Crucible client.

## Non-goals

- Retiring `docs/memory/`, the knowledge seeds and the skills that read `INDEX.md` — CR-MDB-060.
- Re-rendering existing projects — `modelb-axi agents` re-renders on demand; `migrate` is CR-MDB-082.
- The arduino material's generality to every Arduino project — CR-MDB-084 (1.1.0).
- Python, bun and arduino stack skills — python and bun have no material for one; arduino's fits inline.
