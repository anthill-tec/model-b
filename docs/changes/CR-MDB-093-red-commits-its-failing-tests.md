# CR-MDB-093 — A RED phase commits its failing tests; the written rules say so

**Status:** PENDING — spec drafted 2026-10-30 from the gap analysis, the spec pre-review folded in; awaiting
approval.
**Type:** fix (the sub-agent procedure, the git-workflow skill, the java-stack references, `AGENTS.md`)
**Priority:** P2 — release 1.0.0, wave 2.
**Depends on:** none (board-authoritative: read `queue`, not this line)
**Labels:** tdd, skills
**Points:** 3 (re-scored at pre-review; seeded 2).
**Design reference:** PRD D5, ruling of 2026-10-29 at CR-MDB-092's VERIFY: RED commits are allowed — a
test-only commit, made green by GREEN in the same cycle; nothing stays red past a cycle's GREEN, and never
across a merge. DN-multi-harness-deploy-model §D18 (shipped skills name no tool).

## Context

- **The practice.** Every RED phase commits its failing tests on their own, and GREEN commits the code that
  makes them pass in the same cycle. The generated agent definitions already say so:
  - the RED template's close-out commits the test files and reports the commit range
    (`generator/templates/red.md.tmpl`);
  - GREEN never commits before its tests pass, FIX commits one fix at a time once green, VERIFY commits
    nothing;
  - `orchestration-common.md` already calls a RED commit test-only.
- **Written rules that disagree with it:**
  - `skills-src/model-b/references/sub-agent-procedure.md` § "Code quality": "Clean build before commit;
    GREEN before commit — never commit in RED."
  - `skills-src/git-workflow/SKILL.md` § Commit Timing: the first bullet allows a test-only RED commit only
    as a parenthetical exception ("Commit after GREEN — never commit RED state (unless it's a test-only
    commit in a TDD test-write step)"), and the second bullet ("TDD discipline before every commit: RED →
    GREEN → clean up → run tests AGAIN (still GREEN) → commit") still makes every commit come after GREEN.
  - `AGENTS.md` § Testing & QA: "TDD is mandatory: RED before GREEN, never commit failing tests, clean
    build before every commit."
  - The java-stack skill's references, rendered into java and quarkus projects and loaded by Quarkus RED
    agents (`quarkus.toml` RED `skills = ["crucible", "java-stack"]`):
    - `generator/skills/java-stack/references/coding-standards.md` § "Never Commit Failed State": "NEVER
      commit in RED state:", followed by a GREEN-first sequence;
    - `generator/skills/java-stack/references/testing-practices.md`, the "Testing Guidelines Summary"
      item "Never commit RED: Always achieve GREEN before committing", and the refactor "NEVER:" list item
      "Commit in RED state" (a refactor context: a refactor starts and ends GREEN);
    - `generator/skills/java-stack/references/maven.md`, "BEFORE committing": "Are tests GREEN? → Never
      commit RED state".
- **No test pins any of these sentences** (measured at gap analysis and pre-review). The modules that read
  these sections — `tests/test_agent_definition_rules.py` (procedure § "Code quality", git-workflow
  § Commit Timing), `tests/test_suite_hygiene.py` (`AGENTS.md` § Testing & QA),
  `tests/test_stack_reference_material.py` (titles and provenance only) — pin other rules there.
- **The scaffolded `AGENTS.md`** states no commit-timing rule; downstream projects read the rule from the
  deployed skills.

## Scope

### §S1 — The sub-agent procedure

In § "Code quality", "Clean build before commit; GREEN before commit — never commit in RED." becomes one
bullet:

> RED commits its failing tests on their own, a test-only commit; GREEN, FIX and a BACKFILL cycle's agent
> commit only on a clean build with their tests passing. Nothing stays red past the cycle's GREEN, and never
> across a merge.

### §S2 — The git-workflow skill

§ Commit Timing:
- The first bullet states the rule as its main clause: a test-only RED commit is allowed; every other commit
  is on a clean build with no failing tests, no compilation errors and nothing that breaks the build; nothing
  stays red past the cycle's GREEN, and never across a merge.
- The TDD-discipline bullet applies to every commit but RED's test-only commit (RED → GREEN → clean up →
  tests again → commit).

### §S3 — `AGENTS.md`

§ Testing & QA's TDD bullet becomes: "TDD is mandatory: RED before GREEN. RED commits its failing tests on
their own (a test-only commit); every other commit is on a clean build with its tests passing, and nothing
stays red past the cycle's GREEN or across a merge."

### §S4 — The java-stack references

- `coding-standards.md` § "Never Commit Failed State" states the ruling: a RED commit holds failing tests
  only; every other commit is on a clean build with its tests passing. The section may be retitled to match
  (for example "Never Commit a Broken Build"); its GREEN-first sequence applies to every commit but RED's.
- `testing-practices.md`: the summary item states the ruling in the same terms; the refactor "NEVER:" item
  becomes "Commit with a failing test" (a refactor starts and ends GREEN).
- `maven.md`: the "BEFORE committing" item asks whether the tests are GREEN for every commit but RED's
  test-only commit.
- Each reference keeps its title line and provenance line (`tests/test_stack_reference_material.py`).

## Acceptance criteria

Detectors use the repo's case-insensitive rule matcher (`missing_rules` / `rule_blocks` in
`tests/test_agent_definition_rules.py`); a unit is one `rule_blocks` block (a list item with its wrapped
lines). Each pattern below is independent under that matcher: cutting it alone makes it bite.

- [ ] **§S1, the procedure.** One block of § "Code quality" carries `\bRED commits\b`, `test-only`,
      `\bGREEN, FIX and a BACKFILL cycle's agent commit\b`, `clean build`, `past the cycle's GREEN` and
      `across a merge`. The phrase "never commit in RED" appears nowhere in the file.
- [ ] **§S2, git-workflow.** One block of § Commit Timing carries `test-only RED commit`, `failing tests`,
      `past the cycle's GREEN` and `across a merge`; the TDD-discipline block carries
      `but RED's test-only commit`; no block of § Commit Timing requires GREEN before every commit without
      that exception. The phrase "never commit RED state" appears nowhere in the file.
- [ ] **§S3, `AGENTS.md`.** One block of § Testing & QA carries `TDD is mandatory`, `test-only`,
      `clean build` and `past the cycle's GREEN`. The phrase "never commit failing tests" appears nowhere in
      the file.
- [ ] **§S4, the java-stack references.** None of "NEVER commit in RED state", "Never commit RED",
      "Commit in RED state" or "Never commit RED state" appears in `generator/skills/java-stack/references/*.md`;
      each edited reference keeps its title and provenance line.
- [ ] **Proofs.** Every detector is proved both ways on synthetic text: a conforming sample passes; each
      pattern cut alone bites; each retired phrase bites; a rule split across two blocks bites. The
      synthetic proofs pass at RED by design — only the checks against the real files fail there.
- [ ] **Skill frontmatter and loaders.** `tests.test_skill_frontmatter` and the Pi skill-loader checks stay
      green; the edited skills name no tool (DN-multi-harness-deploy-model §D18).
- [ ] **Runs.** The suite is green through the client with a real `HOME` and an empty one; the empty `HOME`
      stays empty. The `AGENTS.md` counts and baselines match; a new test module, if any, raises the module
      counts in the same cycle.

## Non-goals

- **The generated agent definitions (templates and stack files).** They already agree with the ruling; no
  template or stack file changes, and no regeneration.
- **The scaffolded `AGENTS.md`.** It states no commit-timing rule.
- **Copies outside Model B's write boundary,** handled outside this CR: the Roundhouse root `AGENTS.md`
  ("never commit failing tests"; a root-session edit) and the user's global `AGENTS.md`.
- **Squashing or rewriting past RED commits.** History stays.

## Cycle plan

1. **The rule in the procedure, git-workflow, `AGENTS.md` and the java-stack references** (§S1–§S4).
   Red-green. Runs `tests.test_agent_definition_rules` (§S1, §S2 detectors), `tests.test_suite_hygiene`
   (§S3 detector), `tests.test_stack_reference_material` (§S4 detector), `tests.test_stack_skills`,
   `tests.test_orchestration_rules_from_crucible`, `tests.test_core_split`, `tests.test_git_chezmoi_skills`,
   `tests.test_skill_frontmatter`, `tests.test_harness_neutral_skills` and `tests.test_coverage_gate`. RED
   commits its failing tests on their own; GREEN makes them pass in the same cycle (PRD D5, 2026-10-29).
2. **Verify.**
