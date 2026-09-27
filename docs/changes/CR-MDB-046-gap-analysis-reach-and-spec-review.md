# CR-MDB-046 — Gap analysis reaches every consumer, and a spec is reviewed before approval

**Status:** PENDING (filed 2026-09-27; gap analysis 2026-09-27)
**Type:** refactor (skills, agent templates)
**Priority:** P1 — release 1.0.0, wave 2. Every CR in this wave went to a FIX cycle on gaps the gap
analysis should have found (CR-MDB-041, -044, -045).
**Depends on:** —
**Labels:** gap-analysis, orchestration, agents, quality
**Design reference:** PRD D6 (AMENDED 2026-09-27: a spec is reviewed before it is approved); PRD D5
(the orchestrator's duties); DN-multi-harness §D18 (skills name capabilities)

## Context

The `gap-analysis` skill checks a spec along seven dimensions. Three kinds of gap got through it
this wave, each found only by VERIFY after GREEN:
- **The reach of a rule.** Only the file named in the request was checked, not every file that
  states or uses the changed rule.
  - CR-044 left `orchestration-track.md` contradicting `orchestration-common`.
  - CR-045 reached the agents, but not the permission policy or the memory slices.
- **The scenario matrix.** It was walked after RED, not before the spec. Missed that way:
  - CR-041: the quarkus/java client path, and a resumed Track;
  - CR-045: the lost shell, and a token that isn't kebab-case.
- **The project's standing invariants.** A new code path wasn't set against `AGENTS.md`'s rules:
  CR-045's render step broke "validate everything before the first write".

Dimension 6 (public-symbol removal) already enumerates consumers, but only of a removed symbol.

Nothing reviews a drafted spec before the user approves it. The stack's VERIFY agent is the natural
reviewer, but its definition registers `--role VERIFY --cycle <id>`, and no cycle exists before
`plan-file`. Crucible's client accepts `--role report` for a registration that is not exercising a TDD
role, and `report` may register unbound.

## Scope

### §S1 — The `gap-analysis` skill

Under the existing heading "The Dimensions" (no heading renamed, because the CR-042 triage gate
resolves rows under "Dimensions", "Rules", "Test tiers and agents" and "Hardware drivers"):
- **Dimension 8: rule and behaviour reach.**
  - For every rule or behaviour the CR changes, find every file that states or uses it: the skills
    and role files, the agent templates and stack files, the memory templates, and everything the
    scaffold renders.
  - List each hit, and where the spec covers it.
  - A hit the spec does not cover is a gap, not a follow-up.
- **Dimension 9: scenario matrix.**
  - Enumerate every dimension the change varies over, as applicable: stack, agent role, orchestrator
    role (Mainline, Track, Solo), a tool present, absent or unknown, repo shape, and a project created
    before the change.
  - Walk each case once against the current code, running it in a sandbox where it runs.
  - Each case is covered by an AC or named as a non-goal.
- **Dimension 10: standing invariants.**
  - Set every new code path or step against the project's `AGENTS.md` rules.
  - Any path that could break one gets an AC.

Under "Rules":
- **Re-scoping reruns the analysis.** A spec that is restructured or re-scoped gets a fresh gap
  analysis; the earlier one does not carry over.
- **Pre-review before approval.** After the spec is drafted and before it goes to the user, it is
  reviewed by the stack's VERIFY agent in its spec pre-review mode (§S3), under the id
  `CR-<ACRONYM>-NNN-SPEC-REVIEW`. The findings are folded into the spec before approval. For a
  multi-stack project, the VERIFY agent of a stack the CR touches reviews it.

The summary table and verdicts cover the new dimensions.

### §S2 — The orchestration rules

- **`orchestration-common` § "Gap-analysis discipline":**
  - The orchestrator runs the gap analysis itself.
  - The spec pre-review is a separate, dispatched review of the drafted spec, not a delegation of the
    analysis.
  - The section points to the skill for the dimensions instead of listing them.
- **`orchestration-mainline`, the design→execution gate:** gap-analysis → lock the spec →
  pre-review → present → wait for approval → the cycle plan.
- **`orchestration-track`, the setup ordering:** spec → gap-analysis → pre-review → present +
  approval → `plan-file`. The pre-review runs in the Track's worktree, like all its CR work.
- **The `crucible` skill's agent naming and Model B's `AGENTS.md` agent-id note** gain the
  spec-review form: `CR-<ACRONYM>-NNN-SPEC-REVIEW`, registered as `report` with no cycle.

### §S3 — The VERIFY agent's spec pre-review mode (`generator/templates/verify.md.tmpl`)

The VERIFY template gains a second mode, alongside verifying a branch after GREEN: **spec
pre-review**, used when the brief names a drafted spec and no cycle.
- **Registration:** it registers with `--role report` and no `--cycle`, under the id the brief gives.
  The existing VERIFY registration is unchanged.
- **What it reads:** read-only, as VERIFY always is. It reads the drafted spec against its design
  reference and the current code.
- **What it checks:** the gap-analysis dimensions, 8–10 included. It walks the scenario matrix by
  reading, or in a `/tmp` sandbox where running is needed. It runs no test suite and ingests nothing.
- **What it reports:** what it would fail the spec on. Each finding names the spec section or AC it
  needs, and whether it adds scope or corrects it.
- **Last:** it unregisters.

The rendered VERIFY agents are regenerated.

## Acceptance criteria

- [ ] `gap-analysis` carries Dimensions 8, 9 and 10 under "The Dimensions", with their rules as §S1
      states them.
      - "Rules" carries the re-scoping rule and the pre-review rule, the latter naming the review id
        form.
      - The summary table covers Dimensions 1–10.
      - Every heading the CR-042 triage gate resolves still resolves.
- [ ] `orchestration-common` § "Gap-analysis discipline" keeps "the orchestrator runs the gap analysis
      itself", states that the pre-review is a separate dispatched review of the drafted spec, and
      lists no dimensions.
- [ ] `orchestration-mainline`'s gate and `orchestration-track`'s setup ordering place the pre-review
      between the gap analysis (and locking the spec) and presenting it.
- [ ] The `crucible` skill and `AGENTS.md` name `CR-<ACRONYM>-NNN-SPEC-REVIEW`, registered as
      `report` with no cycle.
- [ ] Every rendered VERIFY agent (each stack) carries the spec pre-review mode:
      - it registers `--role report` with no `--cycle`;
      - it runs no test suite and ingests nothing;
      - it reports findings against spec sections or ACs;
      - it unregisters.

      Its branch-verification registration (`--role VERIFY --cycle`) is unchanged. The RED, GREEN and
      FIX agents are unchanged.
- [ ] The CR-044 gates hold: "Reading the CR", spec outranks brief, cite by symbol, no lean-ctx tool
      named in a skill. `generator/build.py --check` is clean, and the suite baselines are
      re-measured in `AGENTS.md`.

## Non-goals

- Delegating the gap analysis itself to an agent.
- Changing Crucible's roles or the imported `crucible-register` bundle.
- Re-analysing closed CRs.
