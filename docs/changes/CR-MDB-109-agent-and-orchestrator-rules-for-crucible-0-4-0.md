# CR-MDB-109 — Agent and orchestrator rules for Crucible 0.4.0: test tiers, the pyramid, and orchestration

**Status:** PENDING — **SEED, not the finished spec** (filed 2026-11-21 by the user's rulings of 2026-11-20
and 2026-11-21, on Crucible #1619 and #1622). Gap analysis and the spec happen in order when this CR starts.
Pre-review: due (8 points, and the user's rulings were needed).
**Type:** feature (the generated agents' and the orchestrator's rules)
**Priority:** P1 — release 1.0.0, wave 2, right after CR-MDB-108 (board-authoritative: read `queue`).
**Depends on:** CR-MDB-108 (the same templates and stack files; its doc-sync lands first).
**Labels:** agents, templates, orchestration, testing
**Design reference:** PRD-model-b-rationalization D5 and D6 (amended 2026-11-20: a refactor of existing tests
runs as a refactor cycle without RED, on the user's grant); DN-multi-harness-deploy-model §D25 (stack- and
tool-oriented, no project names) and §D26; Crucible #1619 (CR-CRU-259..264), #1620 (Model B's mapping), #1621
and #1622.

## Context

Crucible's 0.4.0 test-isolation work produced rules for every project's agents and orchestrators (#1619
B4–B10, C11–C15), shipped as stated in 0.4.0 (#1622). Model B owns the agent templates, the orchestration
references and the stack skills, so the wording is Model B's. The user ruled (2026-11-20) that they go into one
new CR, filed at the release notes.

## Scope (seed)

1. **Test tiers and the pyramid** — the RED, GREEN, FIX and VERIFY templates for every stack, the stack files
   and the stack skills:
   - B4 tiers are declared by directory, in each stack's idiom;
   - B5 unit means no process, no socket (a loopback fake included) and no real wait; everything heavier is
     integration, and a module importing an integration module is integration;
   - B6 tests are self-contained and non-leaky, and never read operator state;
   - B7 the pyramid: unit tests use mocks or in-process fakes; a live test-only board is for feature-level
     integration tests only, one module per feature, stating why no fake can prove it;
   - B8 no tests that test the tests;
   - B9 demoting a live-board test (the fake answers in the server's own shapes; the server half pinned first);
   - B10 bun route tests reach a board in process; a socket only where the test needs one.
2. **Orchestrator rules** — `orchestration-common`, and the bootstrap and shutdown skills where they apply:
   - C11 one sub-agent at a time, never idle beside a background process;
   - C12 scratch never holds copies of test files inside the repository tree;
   - C13 the refactor cycle without RED, on the user's grant before `plan-file` (PRD D6, 2026-11-20);
   - C14 a census-style placement measures modules alone too;
   - C15 after a harness crash, orphaned services are found by cwd and torn down, then restarted supervised;
     production is never touched.
3. **The generated definitions are re-rendered** and the guards move with the text.

## User rulings to take at gap analysis

- **B8 and Model B's own suite** (user, 2026-11-20: decided at this CR's gap analysis): whether "no tests that
  test the tests" binds Model B's own structural gates (for example `tests/test_suite_hygiene.py`'s
  duplicate-helper scan, CR-MDB-032 §S3) or only the agents Model B renders for projects.

## Non-goals

- **Hermetic CI runs for adopting projects** (#1619 D, CR-CRU-263): Crucible's own CI only in 0.4.0; a client
  switch in 0.5.0, requested separately for `workflows-src/` (#1621).
- **Client surface wording** is CR-MDB-108's; `--cycle` on every run is CR-MDB-083's.

## To measure at gap analysis

- Every template, stack file and skill line the rules touch, per stack.
- Whether each rule is stack-general (the sub-agent procedure, stated once) or per stack (the stack files).
- The score (8 points filed) and the behaviour units.
