# CR-MDB-096 — The spec pre-review runs where it pays, and looks only for what would fail the CR

**Status:** COMPLETED (gap analysis, spec and pre-review 2026-10-30; plan 252, cycles 324–327; VERIFY
approved with three suggestions, fixed in the `VERIFY findings (§S5)` cycle by the user's ruling; pre-merge
gate 4808 tests, 0 failed, 1 skip; empty `HOME` 4808/0/12; clean runner 4761/0/26; coverage 6144/6641,
92.5%, unchanged). Spec drafted 2026-10-30 from the gap analysis and the user's rulings (PRD D6,
amended 2026-10-30, with the rulings of CR-MDB-096's gap analysis). Pre-review: ran — the gap analysis
needed the user's rulings; its findings F1–F9 folded in 2026-10-30.
**Type:** feature (workflow rules, the VERIFY agent template)
**Priority:** P1 — release 1.0.0, wave 2, after CR-MDB-079 (board-authoritative: read `queue`).
**Depends on:** nothing on the board.
**Labels:** workflow, gap-analysis, verify, templates
**Points:** 5 (seeded 8; re-scored at gap analysis: text in seven skill and reference files, one template
section and its renders, three test modules migrated; no new code).
**Design reference:** PRD D6, amended 2026-10-30 (the pre-review runs where it pays; its three rulings at
CR-MDB-096's gap analysis); PRD D6's 2026-09-27 amendment (a spec is reviewed before it is approved);
CR-MDB-046 (the pre-review and its pins).

## Context

Every spec gets a pre-review today. After the orchestrator's gap analysis, the stack's VERIFY agent, in
its spec pre-review mode, applies the `gap-analysis` skill's Dimensions 1–10 to the drafted spec, and its
findings are folded in before approval. Every pre-review since 2026-10-14 changed its spec, often close to
half of it; much of each fold was wording and naming, and VERIFY still found gaps after it (CR-MDB-066).

The user ruled (PRD D6, 2026-10-30):

- a pre-review runs only when the CR scores 8 points or more, touches a contract, a hook or another
  project's surface, or its gap analysis needed a ruling from the user;
- it looks only for an acceptance criterion no test can meet or check, a missing failure path or edge
  case, a gap in scope or design, and a conflict with the PRD or a DN; wording and naming are not findings,
  and nothing outside that list is folded in;
- the agent is unchanged: the stack's VERIFY agent in its spec pre-review mode;
- the checklist has one home, the `gap-analysis` skill, which the VERIFY template cites;
- the surface trigger is defined by file kind;
- the decision is recorded on the spec's `**Status:**` line and repeated at approval.

Model B already applies the rule to its own CRs (PRD D6); this CR carries it into what every project gets.

Read at gap analysis (2026-10-30, by reading). The rule is stated in:
- `skills-src/gap-analysis/SKILL.md`: § When to Use, the `READY` verdict, Rule 1, Rules 20–22;
- `skills-src/model-b/SKILL.md`: the role table's pre-review row;
- `skills-src/model-b/references/orchestration-common.md`: § Two-phase workflow (design phase), §
  Gap-analysis discipline (separate review, `design-review` milestone, older projects), § Cycle discipline
  (setup ordering);
- `skills-src/model-b/references/orchestration-mainline.md`: the design→execution gate;
- `skills-src/model-b/references/orchestration-track.md`: the design-phase steps, the findings raised to
  Mainline, the setup ordering;
- `skills-src/cr-authoring/SKILL.md`: the design phase; the front matter's `**Status:**`;
- `skills-src/crucible/SKILL.md`: the VERIFY agent's pre-review duty;
- `generator/templates/verify.md.tmpl` § Spec pre-review mode, rendered into the 5
  `generator/agents/*-verify-agent.md` (one per stack) (by `generator/build.py`, which renders every role) and into
  Model B's own `.pi/agents/python-verify-agent.md`.

Unchanged by the rule, read and left alone: the pre-review's id, registration and main-tree routing
(`sub-agent-procedure.md`, `orchestration-common.md`'s dispatch bullet, `contracts/worktree-layout.md`,
DN-multi-harness-deploy-model's main-tree and test-scope bullets, `pi-package/extensions/worktree.ts`);
the reach-tools bullet (`AGENTS.md`, `modelb_axi/scaffold.py`); Model B's `AGENTS.md` milestone and
agent-id lines; Rule 23 (re-score, split before the pre-review).

Pinned by: `tests/test_gap_analysis_reach_and_pre_review.py` (the skill and references),
`tests/test_verify_spec_pre_review_mode.py` (the template's section),
`tests/test_orchestration_rules_from_crucible.py` (Rule 23; unchanged).

**Baseline:** CR-MDB-079's pre-merge gate, 2026-10-30 (the tree since moved only by its docs-only status
flip, whose modules passed): 4766 tests, 4765 passed, 0 failed, 1 skip; 114 modules.

## Scope

### §S1 — The `gap-analysis` skill states the rule once

In `skills-src/gap-analysis/SKILL.md`. Rule numbers 1–23 keep their numbers; two rules are appended.
Each rule is one block, with no blank line inside it (its nested list and its closing sentences included),
so each is one unit to the tests' `units` helper.

1. **§ When to Use**, first bullet: the ordering is "this analysis → the spec pre-review, when a trigger
   applies (Rule 21) → approval → `plan-file` → the feature branch or worktree → RED".
2. **The `READY` verdict:** proceed to the spec pre-review when a trigger applies (Rule 21), else to
   approval.
3. **Rule 1:** its pointer reads "The spec pre-review (Rules 21, 22, 24 and 25)".
4. **Rule 20, re-scoping:** a re-scoped spec gets a fresh gap analysis, which decides the triggers again,
   and a fresh pre-review when a trigger applies.
5. **Rule 21, the triggers:** the orchestrator dispatches the pre-review after its own analysis and before
   it locks and presents the spec, when at least one trigger applies:
   - the CR scores 8 points or more (the re-score of Rule 23);
   - it touches a contract, a hook or another project's surface — a *contract* is a file under the
     project's `contracts/` or an interface its `AGENTS.md` names as a contract; a *hook* is a hook script,
     the hook schema or compiled hook wiring; *another project's surface* is a file, CLI, API or message
     format another project consumes or provides;
   - its gap analysis needed a ruling from the user.

   Any other spec goes from the analysis to approval — stated in prose, never as an arrow chain without
   the pre-review. The findings a pre-review reports are folded in before locking.
6. **Rule 22** (who and where) and **Rule 23** (re-score; a CR above 13 is split before the pre-review)
   are unchanged. Rule 23 needs no conditional: a CR above 13 always meets the 8-point trigger.
7. **Rule 24, the checklist (new):** a pre-review looks only for:
   - an acceptance criterion no test can meet or check;
   - a missing failure path or edge case;
   - a gap in scope or design;
   - a conflict with the PRD or a DN.

   Wording and naming are not findings, and the orchestrator folds in nothing outside this list.
8. **Rule 25, the record (new):** the spec's `**Status:**` line carries one of three forms:
   `Pre-review: due — <trigger>` (decided, not yet run), `Pre-review: ran — <trigger>` or
   `Pre-review: none — no trigger`. The orchestrator writes it when the analysis decides the triggers,
   moves `due` to `ran` when it folds the findings, and repeats it when it presents the spec for approval.
   A re-scoping (Rule 20) rewrites it. The close-out's `COMPLETED` flip keeps it. In multi mode a Track
   reports its decision to Mainline with its re-score, and Mainline records it on the spec.

### §S2 — The orchestration references, `cr-authoring` and `crucible` follow it

Each names the pre-review as conditional, and points to `gap-analysis` Rule 21 where its item below
says so; none restates the triggers or the checklist (§S5.1).

1. `skills-src/model-b/SKILL.md`, the role table's pre-review row: "one drafted spec, before approval,
   when a trigger applies (`gap-analysis` Rule 21)".
2. `orchestration-common.md`:
   - § Two-phase workflow, the design phase: "Gap-analysis, then the spec pre-review when a trigger
     applies";
   - § Gap-analysis discipline, the separate review: dispatched when a trigger applies (`gap-analysis`
     Rule 21);
   - the `design-review` milestone is posted when a pre-review ran;
   - older projects: the bullet reads that a project scaffolded before the spec pre-review existed, or
     whose agents were rendered before the pre-review's checklist, first upgrades Model B to a release
     carrying the checklist, then re-renders its agents with `modelb-axi agents` before its next
     pre-review; a definition left alone as hand-modified is reported to the user;
   - § Cycle discipline, the setup ordering: "gap-analysis → pre-review (when a trigger applies) →
     approval → `plan-file` → THEN the branch / worktree".
3. `orchestration-mainline.md`, the design→execution gate: "gap-analysis → pre-review when a trigger
   applies → fold its findings → lock the spec → present, with the pre-review record → WAIT for explicit
   approval → ONLY THEN cycle plan".
4. `orchestration-track.md`:
   - the design-phase steps: the gap analysis and, when a trigger applies, the spec pre-review;
   - findings to Mainline: a Track raises its trigger decision and its pre-review findings to Mainline;
   - the setup ordering: "spec → gap-analysis → pre-review (when a trigger applies) → present + get
     approval → `plan-file` → THEN `worktree-flow start` + dispatch".
5. `skills-src/cr-authoring/SKILL.md`: the design phase names the pre-review "when a trigger applies";
   the front matter's `**Status:**` item says it carries the pre-review record (`gap-analysis` Rule 25).
6. `skills-src/crucible/SKILL.md`: the VERIFY agent's pre-review duty is "when the CR meets a trigger
   (`gap-analysis` Rule 21)".

### §S3 — The VERIFY template's pre-review mode applies the checklist

In `generator/templates/verify.md.tmpl` § Spec pre-review mode:

1. **Its opening paragraph:** the pre-review runs when the CR meets a trigger (`gap-analysis` Rule 21).
2. **How you review:** apply the `gap-analysis` skill's pre-review checklist (Rule 24), read-only, cited by
   its installed path `~/.agents/skills/gap-analysis/SKILL.md`; report only what the checklist lists;
   wording and naming are not findings.
3. **What does not bind you:** the skill's Dimensions 1–10 (the orchestrator's analysis) join Step 0 and
   Rule 1.
4. **Output:** each finding F1…Fn names its checklist item, the spec section or AC it needs, and whether it
   adds scope or corrects it; the one-line verdict stays.
5. Every other rule of the section stays: the trigger (only when the brief declares it), the `report`
   registration with no cycle, Crucible down, the whole spec read, no suite, no ingest, no edit, no
   commit, the `/tmp` sandbox, unregister last.
6. **Renders:** `python3 generator/build.py build` regenerates the 5 `generator/agents/*-verify-agent.md`
   (no other render changes); Model B's own `.pi/agents/python-verify-agent.md` is re-rendered from the
   tree and committed. The render runs `python3 -m modelb_axi agents` from the repository root with
   `MODELB_HOME` at a temp dir holding a copy of the real `$MODELB_HOME/install.toml` with its
   `asset_root` line removed — so the tree's templates are read and the recorded `harnesses` and
   `lean-ctx` verdict hold — and `XDG_DATA_HOME` and `PI_CODING_AGENT_DIR` at temp dirs. Only
   `python-verify-agent.md` changes; the other managed files report unchanged.

### §S4 — The gates this change moves (named migrations)

1. **`tests/test_gap_analysis_reach_and_pre_review.py`** (§S1, §S2):
   - MIGRATED, each requiring its conditional in the same unit:
     - `ORDER_TO_PLAN_FILE`, `MAINLINE_GATE`, `TRACK_SETUP_ORDER`, `TWO_PHASE_DESIGN`,
       `RULE_PRE_REVIEW_ORDER`, `RULE_RESCOPING`, `GA_DISCIPLINE_SEPARATE`: `when a trigger applies`
       (`RULE_PRE_REVIEW_ORDER` also keeps "fold … before locking" in the same unit);
     - `DESIGN_REVIEW_MILESTONE`: `when a pre-review ran`;
     - `RE_RENDER_OLDER`: `before its next pre-review` and `checklist`;
     - `COMMON_UPGRADE_FIRST` (the same bullet): `before its next pre-review` in place of
       `before (?:its|the) first pre-review`, and the release carrying the checklist;
     - `TRACK_FINDINGS_TO_MAINLINE`: `trigger decision`;
   - NEW pins for Rule 21's three triggers and three definitions, Rule 24's four items with "wording and
     naming are not findings" and "folds in nothing outside", Rule 25's three record forms, its writing,
     `due` → `ran`, the repeat at approval, the rewrite on re-scoping, the `COMPLETED` flip keeping it and
     the Track's report to Mainline; the role table row, `cr-authoring`'s two items and `crucible`'s duty;
   - NEW the ordering guard (AC3) and the restatement detector (AC2);
   - KEPT `OLD_ORDERING` (`test_no_shipped_file_states_the_old_ordering`): no shipped file states
     `gap-analysis → approval|lock|present|plan-file`; the no-trigger path is prose only (§S1.5).
2. **`tests/test_verify_spec_pre_review_mode.py`** (§S3): MIGRATED `PRE_REVIEW_RULES`' "applies the
   gap-analysis skill's Dimensions 1–10 read-only" to the checklist rule (Rule 24, the skill's path,
   read-only, wording and naming not findings); NEW rules for the opening paragraph's trigger, the
   dimensions in "what does not bind you" and the output's checklist item.
3. **`tests/test_orchestration_rules_from_crucible.py`**: unchanged (Rule 23 keeps its number and text).

No test module is added. No skip is added. No floor is lowered.

### §S5 — VERIFY findings (cycle 326; the user's ruling of 2026-10-30: a short fix cycle)

1. **F1 — §S2's lead.** It said every reference points to Rule 21; the items of
   `orchestration-mainline.md`, `orchestration-track.md` and `cr-authoring` (which points to Rule 25)
   carry no Rule 21 pointer, and AC2 pins the items. The lead now says "where its item below says so".
   Spec only.
2. **F3 — AC3's accepted forms.** The guard accepts Rule 21's own wording, `when at least one trigger
   applies`, beside the two forms AC3 named; AC3 now names all three. Spec only; the guard already does so.
3. **F2 — the checklist rule's "report only".** The template's "How you review" says "Report only what the
   checklist lists"; nothing pinned it. `PRE_REVIEW_RULES`' checklist rule also requires it, in the same
   unit, proved both ways (a cut yields exactly that finding). The text is already there, so the pin passes
   on arrival; no FIX phase follows.

## Acceptance criteria

"Both ways" means a sample that must be caught is caught and a sample that must pass passes. Every check
reads text.

- [ ] **AC1 — the skill (§S1).** `skills-src/gap-analysis/SKILL.md` states, each in one unit: § When to
      Use's ordering with the conditional; `READY` → the pre-review when a trigger applies, else approval;
      Rule 1's pointer to Rules 21, 22, 24 and 25; Rule 20's fresh pre-review when a trigger applies;
      Rule 21's three triggers (`8 points or more`, a contract/hook/another project's surface, a ruling
      from the user), its three definitions (`contracts/`, an interface `AGENTS.md` names; a hook script,
      the hook schema, compiled hook wiring; a file, CLI, API or message format another project consumes
      or provides) and "any other spec goes from the analysis to approval"; Rule 24's four items,
      "wording and naming are not findings" and "folds in nothing outside"; Rule 25's three record forms
      (`Pre-review: due — <trigger>`, `Pre-review: ran — <trigger>`, `Pre-review: none — no trigger`),
      `due` → `ran` at the fold, the repeat at approval, the rewrite on re-scoping, the `COMPLETED` flip
      keeping it and the Track's report to Mainline. Each of Rules 21, 24 and 25 is one unit (no blank line
      inside it). Rules 22 and 23 are unchanged. Each pin is proved both ways on
      synthetic text (one cut → exactly its finding).
- [ ] **AC2 — the references (§S2).** Each item of §S2 holds in its file, one unit each, proved both ways.
      None of the §S2 files restates the rule: the restatement detector reports a unit holding two or more
      of Rule 21's trigger phrases (`8 points or more`; `a contract, a hook or another project's surface`;
      `a ruling from the user`) or two or more of Rule 24's item phrases (`no test can meet or check`;
      `missing failure path or edge case`; `gap in scope or design`; `conflict with the PRD or a DN`).
      Proved both ways: a unit holding two trigger phrases yields exactly one finding; the real units
      holding one phrase alone pass — the scoring scale `1, 2, 3, 5, 8, 13` in `cr-authoring` and
      `crucible`, and "another project's working tree" in `model-b/SKILL.md`.
- [ ] **AC3 — the ordering guard (§S4.1).** In the files §S1–§S2 list, a unit in which the pre-review is
      a link of an arrow chain (`→` before or after `pre-review`), or the object of "dispatches the (spec)
      pre-review" or "proceed to the (spec) pre-review", carries `when a trigger applies`,
      `when at least one trigger applies` (Rule 21's own form, §S1.5) or `when the CR meets a trigger`, or
      it is a finding naming its file (§S5.2). Proved both ways: an ordering with
      the conditional passes; the same ordering without it yields exactly one finding; and these real
      units, left alone by this CR, pass: Rule 23 ("split before the pre-review"), the dispatch-description
      bullet ("Name the CR id in every dispatch description … except a spec pre-review"), the VERIFY-word
      bullet ("may run in the design phase in its spec pre-review mode") and `crucible`'s identity
      bullet ("reviewing a drafted spec before approval").
- [ ] **AC4 — the template (§S3).** The template's pre-review section states, one unit each: the trigger
      in its opening paragraph; the checklist rule (Rule 24, the skill's installed path, read-only, wording
      and naming not findings); Dimensions 1–10 among what does not bind; the output's checklist item.
      `PRE_REVIEW_RULES`' other rules and the placement, registration and branch-mode checks pass
      unchanged. Every rendered VERIFY definition (the 5 in `generator/agents/` and Model B's
      `.pi/agents/python-verify-agent.md`) carries the same section.
- [ ] **AC5 — regeneration.** `python3 generator/build.py --check` is clean; the 5 VERIFY renders are
      the build's output and no other render changes; `.pi/agents/python-verify-agent.md` carries the
      generated header with its current hash.
- [ ] **AC6 — the scenario matrix.** The text covers, each in a unit AC1 or AC2 pins: Mainline or Solo
      records the decision on the spec; a Track reports it to Mainline, which records it; a CR with no
      trigger posts no `design-review` milestone; a re-scoped spec decides the triggers again; a project
      whose agents predate the checklist re-renders them before its next pre-review; a pre-review decided but
      not yet run is recorded `due`.
- [ ] **AC7 — standing gates.** `ruff check` exits 0; no test module and no skip is added; every module
      the cycle plan names passes through the client; `tests.test_orchestration_rules_from_crucible`
      passes unchanged; VERIFY runs the full suite through the client with a real `HOME` and an empty
      one, and the empty `HOME` stays empty.
- [ ] **AC8 — VERIFY findings (§S5).** §S2's lead and AC3 read as §S5.1–§S5.2 say; the checklist rule in
      `PRE_REVIEW_RULES` requires "report only what the checklist lists" in its unit, the template and every
      VERIFY render meet it, and a cut of that phrase yields exactly the checklist rule's finding.

## Non-goals

- **The orchestrator's analysis** keeps all ten dimensions; only the pre-review narrows.
- **The pre-review's agent, id, registration and main-tree routing** are unchanged (`contracts/`,
  `pi-package/extensions/worktree.ts`, the DN's routing bullet, `sub-agent-procedure.md`).
- **No code enforces the triggers or the checklist:** they are workflow rules in text, as the pre-review
  itself is.
- **Model B's own `AGENTS.md`:** its milestone and agent-id lines hold as written.
- **CR-MDB-096's own pre-review** runs under the rule this CR states (PRD D6: Model B applies it now).

## After merge

None of these steps is an acceptance criterion.
1. The user reinstalls the tool and redeploys (`uv tool install --reinstall --python 3.14 .`, then
   `modelb-axi --reinstall`): the skills changed.
2. Each project re-renders its agents with `modelb-axi agents` before its next pre-review (§S2.2).

## Cycle plan

RED commits its failing tests on their own (test-only), and GREEN makes them pass in the same cycle, once
`ruff check` exits 0 (PRD D5, 2026-10-29). Nobody runs the full suite between cycles; VERIFY runs it once.
Each cycle runs, through the client, the modules it names plus the docs gates of `AGENTS.md`
(`tests.test_client_path_anchoring`, `tests.test_project_registry_schema`, `tests.test_suite_hygiene`,
`tests.test_archive_mapping`, `tests.test_cite_by_symbol`, `tests.test_harness_neutral_skills`,
`tests.test_axi_envelope_read_whole`, `tests.test_orchestration_rules_from_crucible`,
`tests.test_raw_runner_guard`, `tests.test_tooling_detachment`, `tests.test_claude_era_retirement`,
`tests.test_prd_criteria`). A module found reading an edited file and not named is run too, and named in
the cycle's report.

1. **The rule in the skill and the references** (§S1, §S2, §S4.1). Red-green.
   - **RED:** §S4.1's migrations, new pins and guard (AC1–AC3, AC6); they fail on today's text.
   - **GREEN:** the text of §S1 and §S2.
   - **Modules:** the docs gates, plus `tests.test_gap_analysis_reach_and_pre_review`,
     `tests.test_skill_frontmatter`, `tests.test_crucible_skill`, `tests.test_cr_authoring_skill`,
     `tests.test_orchestrator_references`, `tests.test_board_holds_the_queue`,
     `tests.test_context_ledger_rule`, `tests.test_installer_assets`.
2. **The VERIFY template's checklist** (§S3, §S4.2). Red-green.
   - **RED:** §S4.2's migration and new rules (AC4); they fail on today's template.
   - **GREEN:** the template section; `python3 generator/build.py build`; Model B's own
     `.pi/agents/python-verify-agent.md` re-rendered; renders committed with it.
   - **Modules:** the docs gates, plus `tests.test_verify_spec_pre_review_mode`,
     `tests.test_generator_role_contract`, `tests.test_agent_generator`, `tests.test_pi_agent_definitions`,
     `tests.test_agent_definition_rules`, `tests.test_project_tools_setup`,
     `tests.test_stack_reference_material`, `tests.test_worktree_layout_and_bundles`.
3. **Verify.** VERIFY runs the full suite once, without coverage, through the client, with a real `HOME`
   and an empty one, and reads every AC.
4. **VERIFY findings (§S5, AC8).** Fix, appended after the VERIFY cycle closed with three suggestions.
   - §S5.1–§S5.2 are the spec's own corrections, made by the orchestrator with §S5.
   - **RED:** §S5.3's pin and its cut, in `tests/test_verify_spec_pre_review_mode.py`; it passes on arrival,
     labelled so; no FIX phase.
   - **Modules:** the docs gates, plus `tests.test_verify_spec_pre_review_mode`.
   - The orchestrator then runs the pre-merge gate bound to this cycle and records the `AGENTS.md`
     baselines at close-out.
