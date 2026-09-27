# CR-MDB-046 — Gap analysis reaches every consumer, and a spec is reviewed before approval

**Status:** PENDING (filed 2026-09-27; gap analysis and pre-review 2026-09-27)
**Type:** refactor (skills, agent templates, stack files, scaffold text)
**Priority:** P1 — release 1.0.0, wave 2. Every CR in this wave went to a FIX cycle on gaps the gap
analysis should have found (CR-MDB-041, -044, -045).
**Depends on:** —
**Labels:** gap-analysis, orchestration, agents, quality
**Design reference:** PRD D6 (AMENDED 2026-09-27: a spec is reviewed before it is approved;
re-scoping reruns the analysis and the pre-review; the pre-review proceeds unregistered when
Crucible is down); PRD D5 (the orchestrator's duties); DN-multi-harness §D18 (skills name
capabilities); `docs/research/DN-model-b-language.md` (the locked ontology: roles, milestone types)

## Context

The `gap-analysis` skill checks a spec along seven dimensions. Three kinds of gap got past it this
wave, and VERIFY found each one only after GREEN:
- **The reach of a rule.** Only the file named in the request was checked, not every file that states
  or uses the rule.
- **The scenario matrix.** It was walked after RED, not before the spec.
- **The project's standing invariants.** No new code path was set against `AGENTS.md`'s rules.

Dimension 6 enumerates consumers, but only of a removed public symbol.

Nothing reviews a drafted spec before the user approves it. The stack's VERIFY agent is the natural
reviewer, but its definition is written for branch verification after GREEN. The VERIFY template
(`generator/templates/verify.md.tmpl`) requires `--role VERIFY --cycle`, a targeted regression,
ingest, gate criteria and a regression line in its output. Each stack file's `[gotchas].verify`
mandates gate runs; arduino's, for example, runs the full native suite. No cycle exists before
`plan-file`. Crucible's client accepts `--role report`, unbound, for a registration that is not
exercising a TDD role.

The orchestration rules state the design→execution ordering in several places:
- `orchestration-common` § "Two-phase workflow", § "Gap-analysis discipline" and § "Cycle
  discipline";
- `orchestration-mainline`'s gate;
- `orchestration-track`'s setup ordering.

A Track's worktree does not exist until after `plan-file`, and only Mainline edits develop, where a
spec lives until then.

## Scope

### §S1 — The `gap-analysis` skill (`skills-src/gap-analysis/SKILL.md`)

The skill gains three dimensions, under its existing dimension headings:

- **Dimension 8: rule and behaviour reach.** For every rule or behaviour the CR changes, find every
  file that states or uses it:
  - the skills and role references;
  - the agent templates, `builtin-tools.toml` and the stack files;
  - the memory templates, and everything the scaffold renders;
  - the tests that pin any of it.

  List each hit and where the spec covers it. A hit the spec does not cover is a gap, not a follow-up.
- **Dimension 9: scenario matrix.** Enumerate every case the change varies over, as applicable:
  - the stack and the agent role;
  - the orchestrator role (Mainline, Track, Solo);
  - a tool that is present, absent or unknown;
  - the repo shape;
  - a project scaffolded before the change;
  - an upstream provider that is down.

  Walk each case once against the current code, by reading. Run it in a `/tmp` sandbox only where
  reading cannot settle it. Each case is covered by an AC, or named as a non-goal.
- **Dimension 10: standing invariants.** Set every new code path or step against the project's
  `AGENTS.md` rules and its existing gates. Any path that could break one gets an AC.

The skill's frontmatter `description`, its intro sentence on how the dimensions group, and its
finding format's "Dimension:" field all cover Dimensions 1–10.

Under "Rules":
- **Re-scoping reruns both steps.** A spec that is restructured or re-scoped gets a fresh gap
  analysis and a fresh pre-review.
- **The pre-review comes after the analysis, before approval.** The orchestrator dispatches it after
  its own analysis and before it locks and presents the spec. The findings are folded in before
  locking.
- **Who and where:**
  - **Id:** `CR-<ACRONYM>-NNN-SPEC-REVIEW`, the acronym taken from the nearest registry.
  - **Reviewer:** the VERIFY agent of a stack in that registry's `PROJECT_STACKS`.
  - **Where it runs:** read-only in the main tree.
- **Rule 1 ("never delegate this analysis") stands.** It says the pre-review is a separate review of
  the drafted spec.

### §S2 — The orchestration rules and the role descriptions

- **`orchestration-common`:**
  - **§ "Two-phase workflow":**
    - the design phase lists gap analysis, then the spec pre-review;
    - "VERIFY is an execution-phase word only" is narrowed: the VERIFY *agent* may run in the design
      phase in its spec pre-review mode, and that step is called the pre-review, never "verify".
  - **§ "Gap-analysis discipline":**
    - it keeps "the orchestrator runs the gap analysis itself";
    - it adds that the pre-review is a separate, dispatched review of the drafted spec;
    - it points to the skill for the dimensions and the verdicts, listing neither.
  - **§ "Cycle discipline":** the setup ordering is gap-analysis → pre-review → approval →
    `plan-file` → the branch or worktree.
  - **A pre-review is a workflow moment:** it posts a `design-review` milestone.
  - **Older projects:** a project scaffolded before this CR re-renders its agents with `modelb-axi
    agents` before its first pre-review. A definition left alone as hand-modified is reported to the
    user.
- **`orchestration-mainline`, the design→execution gate:** gap-analysis → pre-review → fold its
  findings → lock the spec → present → wait for approval → the cycle plan.
- **`orchestration-track`:**
  - the setup ordering matches;
  - the pre-review runs in the main tree, read-only;
  - a Track raises its pre-review findings to Mainline, which folds them into the spec on develop;
  - the "100% of CR work is in-worktree" bullet is reconciled: design-phase steps (the gap analysis,
    the pre-review) happen before the worktree exists, and everything from `worktree-flow start` on
    happens in it.
- **The `crucible` skill:**
  - § "Identity" names `CR-<ACRONYM>-NNN-SPEC-REVIEW`, registered as `report` with no cycle;
  - its "who runs what" lists the pre-review as a VERIFY-agent duty with no runs and no ingest.
- **The `model-b` skill § 2:** the pre-review is a `report` actor on the board, outside any cycle.
- **`sub-agent-procedure.md`:** a run-less `report` registration needs no heartbeat, and no run to
  report.
- **Model B's `AGENTS.md` agent-id note** names the spec-review form.
- **`_render_agents_md` (modelb_axi/scaffold.py):** the scaffolded agent-naming line also points to
  the `crucible` skill's Identity section.

### §S3 — The VERIFY agent's spec pre-review mode

- **`generator/templates/verify.md.tmpl`:** one "Spec pre-review mode" section, placed after First
  Actions:
  - **Trigger.** Branch verification stays the default. The mode applies only when the brief
    declares it explicitly; it is never inferred from a missing cycle or from the agent id.
  - **Registration.** It registers `--role report` with no `--cycle`, under the id the brief gives.
    This command comes after the branch-mode register command. If Crucible is down or absent, it
    proceeds unregistered and says so in its report.
  - **What it reads.** It reads the whole spec, its design reference and the current code, and
    applies the `gap-analysis` skill's Dimensions 1–10 read-only. It cites the skill as it cites
    `sub-agent-procedure.md`. The skill's Step 0 (running the suites) and Rule 1 do not apply to it.
  - **What it does not do.** It runs no test suite, ingests nothing, edits nothing and commits
    nothing. It may run a `/tmp` sandbox where reading cannot settle a case.
  - **Its output format.** Findings F1…Fn, each naming the spec section or AC it needs, and whether
    it adds scope or corrects it.
  - **Last.** It unregisters when registered.

  The branch-mode non-negotiables are scoped to branch verification, and each says so: First Actions'
  cycle requirement, targeted regression and ingest; Gate Criteria; the output format's regression
  line; and the report ending the VERIFY cycle's work.
- **The stack files' `[gotchas].verify`** are rendered as branch-verification specifics. Their
  mandated runs do not apply in the pre-review mode.
- **The built-in form.** Any lean-ctx wording the new section adds has a `builtin-tools.toml`
  passage, so the built-in form renders.

The rendered agents are regenerated.

## Acceptance criteria

- [ ] **`gap-analysis` carries:**
      - Dimension 8, naming its file classes;
      - Dimension 9, listing its cases (stack, agent role, orchestrator role, tool present/absent/
        unknown, repo shape, a project scaffolded before the change, an upstream provider down) and
        "by reading; a sandbox only where reading cannot settle it";
      - Dimension 10, naming `AGENTS.md` rules and existing gates;
      - in its frontmatter `description`, its intro and its finding format's Dimension field, all
        ten dimensions;
      - under "Rules", the re-scoping rule, the pre-review rule (id form, nearest registry, a
        `PROJECT_STACKS` stack, main tree, read-only, fold before locking), and Rule 1's pointer to
        the pre-review.
- [ ] **`orchestration-common`:**
      - § "Two-phase workflow" lists the pre-review in the design phase, and scopes the "VERIFY"
        word rule to the phase, not the agent;
      - § "Gap-analysis discipline" keeps "the orchestrator runs the gap analysis itself", states that
        the pre-review is separate, and names none of "spec↔PRD", "design-lineage",
        "public-symbol", "READY" or "SPEC_UPDATE_NEEDED";
      - § "Cycle discipline"'s setup ordering names the pre-review before approval;
      - the `design-review` milestone and the re-render rule for older projects are stated.
- [ ] **`orchestration-mainline`'s gate** reads gap-analysis → pre-review → fold → lock → present →
      approval → plan.
- [ ] **`orchestration-track`:**
      - the setup ordering names the pre-review;
      - the pre-review runs in the main tree;
      - a Track's findings go to Mainline;
      - the in-worktree bullet no longer claims the gap analysis or spec writing.
- [ ] **The `crucible` skill, the `model-b` skill § 2, `sub-agent-procedure.md` and Model B's
      `AGENTS.md`** state what §S2 gives each.
      - The scaffolded `AGENTS.md` naming line points to the `crucible` skill's Identity section, and
        its pinned test is migrated.
- [ ] **Every rendered VERIFY agent** (each stack, lean-ctx and built-in form) has exactly one "Spec
      pre-review mode" section, placed after First Actions:
      - explicit trigger, never inferred;
      - `--role report` with no `--cycle`, after the branch-mode register command;
      - proceeds unregistered when Crucible is down;
      - cites the `gap-analysis` skill (Dimensions 1–10; not Step 0, not Rule 1);
      - no test suite, ingest, edit or commit;
      - findings name a spec section or AC, and adds or corrects;
      - unregisters when registered.
- [ ] **Branch-mode scoping.** Every branch-mode non-negotiable (cycle requirement, regression,
      ingest, Gate Criteria, regression line, "ends the VERIFY cycle's work") and every stack's
      `[gotchas].verify` are stated as branch-verification only.
- [ ] **Other agents unchanged.** The rendered RED, GREEN and FIX agents are byte-identical to HEAD,
      in both forms.
- [ ] **Migrated gates.** The CR-017 role-flag gate (`GeneratorRoleContractS6aTest`) accepts
      VERIFY's `report` pre-review line as well as its `VERIFY` line. The cycle-binding anchor still
      reads the branch-mode command. Both are listed as migrated.
- [ ] **Gates that hold:**
      - the CR-044 gates: one "Reading the CR", spec outranks brief, cite by symbol, `CYCLE_RULES`;
      - the CR-045 gates: built-in form, no lean-ctx tool in a skill;
      - the CR-042 triage headings in every file this CR edits, with `HEADING_RENAMES` unchanged;
      - `ModelBCommonTextNeutralTest` and the retired harness-tool gate;
      - `generator/build.py --check`.

      The suite baselines are re-measured in `AGENTS.md`.

## Non-goals

- Delegating the gap analysis itself to an agent.
- Changing Crucible's roles, its client's agent-naming header, or the imported `crucible-register`
  bundle.
- Re-analysing closed CRs.
