# CR-MDB-096 — The spec pre-review runs where it pays, and looks only for what would fail the CR

**Status:** PENDING — **SEED, not the finished spec** (filed 2026-10-30 from the user's ruling).
Gap analysis and the spec happen in order when this CR starts.
**Type:** feature (workflow rules, VERIFY agent template)
**Priority:** P1 — release 1.0.0, wave 2, after CR-MDB-079 (user 2026-10-30; board-authoritative: read
`queue`).
**Depends on:** nothing on the board.
**Labels:** workflow, gap-analysis, verify, templates
**Design reference:** PRD D6, amended 2026-10-30 (the pre-review runs where it pays); PRD D6's
2026-09-27 amendment (a spec is reviewed before it is approved); CR-MDB-046.

## Context

Every spec gets a pre-review today: after the orchestrator's gap analysis, the stack's VERIFY agent, in
its spec pre-review mode, applies the `gap-analysis` skill's Dimensions 1–10 to the drafted spec, and its
findings are folded in before approval (`gap-analysis` Rules 20–22, `verify.md.tmpl` § Spec pre-review
mode). Every pre-review since 2026-10-14 changed its spec, often rewriting close to half of it; much of
each fold was wording and naming, and VERIFY still found gaps after it (CR-MDB-066). The user ruled
(2026-10-30, PRD D6) that the pre-review runs only where it pays and looks only for what would fail the CR.

## Scope (seed)

1. **When a pre-review runs.** A spec gets one when at least one holds: the CR scores 8 points or more; it
   touches a contract, a hook or another project's surface; or its gap analysis needed a ruling from the
   user. Any other spec goes from the gap analysis to the user's approval. The skills' setup orderings
   (`gap-analysis → pre-review → approval → plan-file`) name the pre-review as conditional, and the
   `design-review` milestone is posted only when one ran.
2. **What it looks for.** The VERIFY template's spec pre-review mode replaces "Dimensions 1–10" with a
   fixed checklist: an acceptance criterion no test can meet or check; a missing failure path or edge
   case; a gap in scope or design; a conflict with the PRD or a DN. Wording and naming are not findings,
   and the orchestrator folds in nothing outside the checklist.
3. **The agent is unchanged:** the stack's VERIFY agent in its spec pre-review mode, its `report`
   registration, its main-tree routing and its read-only bounds stay as they are. The 20 generated
   definitions are re-rendered (`generator/build.py build`) and Model B's own `.pi/agents/` re-rendered.
4. **Existing projects** take the change with `modelb-axi agents` and the installer's skill redeploy.

## To measure at gap analysis

- The reach of the rule, measured 2026-10-30: `skills-src/gap-analysis/SKILL.md` (§ When to Use, the
  READY verdict, Rules 1 and 20–22), `skills-src/model-b/SKILL.md` (the role table),
  `references/orchestration-common.md`, `orchestration-mainline.md`, `orchestration-track.md`,
  `sub-agent-procedure.md`, `skills-src/cr-authoring/SKILL.md`, `skills-src/crucible/SKILL.md`,
  `generator/templates/verify.md.tmpl`, `modelb_axi/scaffold.py`; the DN's main-tree routing and VERIFY
  bullets (DN-multi-harness-deploy-model, the spec pre-review and test-scope bullets).
- The tests that pin the pre-review's text: `test_verify_spec_pre_review_mode`,
  `test_gap_analysis_reach_and_pre_review`, `test_generator_role_contract`,
  `test_orchestration_rules_from_crucible`, `test_pi_worktree_isolation`, `test_project_tools_setup`,
  `test_context_ledger_rule`.
- How the orchestrator records which trigger applied (or that none did) where the user sees it, so the
  skipped pre-review is visible at approval.
- The re-score.
