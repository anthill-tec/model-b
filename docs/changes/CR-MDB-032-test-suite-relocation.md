# CR-MDB-032 — The test suite runs on any machine: no Crucible checkout, no real-home assertions, one copy of each helper, and the hygiene backlog cleared

**Status:** PENDING (filed 2026-09-21 from `audits/2026-09-21-codebase-review-tests.md`; notes added
2026-09-22/23/24; rewritten at its gap-analysis 2026-09-24 — earlier text is git history and is not
to be consulted for contracts)
**Type:** refactor
**Priority:** P1 — in release 1.0.0, wave 2. The suite is the release gate; today it passes only on
this machine.
**Depends on:** CR-MDB-020 (the anchoring gate this CR extends to `tests/`), CR-MDB-021 — both merged
**Labels:** tests, quality, refactor
**Design reference:** repo-local authoring rule 2026-07-22 (gates assert repo paths) · standing rule
2026-09-18 (the Crucible checkout is out of bounds; installed clients at `~/.crucible/clients/`) ·
DN §D14 (`~/.claude` is unowned legacy) · `audits/2026-09-21-codebase-review-tests.md` §1–§3

## Context — measured 2026-09-24 on `develop` at `7a853be`

- **Suite:** 51 modules, 1021 tests, 0 failures, 11 skips (sandboxed `MODELB_HOME`/`XDG_DATA_HOME`,
  real `HOME`). `AGENTS.md` still says 19 modules and 359 tests.
- **Empty `HOME`** (`HOME` → an empty temp dir, user site-packages kept): **32 failures, 6 errors,
  18 skips.** By module: `test_core_split` 9, `test_model_b_skill` 7, `test_git_chezmoi_skills` 6,
  `test_cr_authoring_skill` 4, `test_memory_model` 4, `test_worktree_flow_axi` 3, `test_scaffold` 3
  (errors: `InitDryRunTest`, `InitEmissionSoloRunTest`), and one each in
  `test_installer_assets.ImportedSkillBundleFidelityTest` and
  `test_agent_generator.DeployedAgentsConsumerConstraintTest`. These assert the user's deployed
  `~/.claude` / `~/.agents`, or stat real-home paths.
- **Crucible checkout reach in `tests/`:** `test_scaffold.py:60` and `test_hooks.py:434` load the
  checkout's `toon.py` (the latter by an absolute `/home/antonyj/…` path, no skip guard);
  `test_toon_codec.py:99` uses the checkout's clients as an oracle; `test_tooling_detachment.py:375`
  reads the checkout's `rust-crucible.py`; `test_skills_handover.py:49` and
  `test_installer_assets.py:95` compare against a retired origin tree (the two permanent skips);
  `test_realhome_supersede.py:365,374` name it in remedy text. The checkout strings in
  `test_ambient_manifest_discovery`, `test_client_path_anchoring` and `test_skill_bundle_guards_meta`
  are detector fixtures.
- **`test_realhome_supersede.py`** is env-gated (`MODELB_REALHOME_GATE`) and silently green; its one
  retained assertion (no `~/.claude/scripts/*crucible*` in the real home) is superseded by CR-MDB-020's
  anchoring gate, which fails on any Model B text naming that mirror.
- **`test_worktree_flow_axi.py`:** `WorktreeFlowCodecDeploymentTest` and `WorktreeFlowEnvelopeTest`
  drive `~/.claude/scripts/*` copies (superseded by `test_toon_codec`);
  `WorktreeFlowSkillConsumerNotesTest` reads the deployed skill.
- **Duplicated helpers:** 16 module-level helpers exist in more than one module, 45 extra copies in
  all (`_read` ×15, `_files_under` ×6, `_write_exe` ×5, `_decode` ×5, `_archive_has_content_move` ×4,
  `_split_frontmatter`, `_write_fake_executable`, `decode_axi` ×3, and others).
- **Pi coverage exists:** `test_deployed_asset_freshness` and `test_harness_capability_contract` run
  real sandboxed installs with `--harnesses pi`; scaffold coverage with `pi` exists through
  `test_pi_agent_definitions` / `test_project_permission_policy`. What is missing is an assertion that
  a Pi-only install writes nothing under `<root>/.claude/`.
- **Hygiene backlog (pi-lens, collected from earlier CRs' notes; no behaviour defect):**
  - unsorted import blocks: `test_package_publishing.py:39`, `test_hooks.py:80`,
    `test_agent_generator.py:103`, `test_rust_stack_generator.py:43`,
    `test_installer_correctness.py:44`, `test_installer.py:1022`, `generator/build.py:27`;
  - unnarrowed `Optional` values: `test_installer_assets.py:147-149,1237`,
    `test_installer_correctness.py:918,974,1015,1042`, `test_installer.py:1026,1053`,
    `test_scaffold.py:153`, `generator/build.py`'s `__doc__.splitlines()` (~line 221);
  - style: `test_client_verb_sweep.py:554` (`str.format`), `test_installer_correctness.py:1046`
    (unannotated `**kwargs`), `:1182`, `:1233` (nested `with`), loop string concatenation,
    `test_scaffold.py:1678` (repeated `.endswith`);
  - false positive, no change: `test_scaffold.py:1679` (the "hardcoded password" is `init`'s project
    `token`).
  Line numbers drift; the implementer re-locates each by content.
- **Not hermetic:** many `_run_module` calls in `test_installer.py` leave `HOME`/`PATH` unpinned
  and read the real `~/.crucible` manifest and PATH `python3`.

## Scope

### §S1 — No Crucible checkout in `tests/`
`test_scaffold.py` and `test_hooks.py` use `modelb_axi.toon`. `test_toon_codec.py`'s oracle and
`test_tooling_detachment.py`'s gate-lock read resolve the installed client through
`~/.crucible/crucible-clients.json` and **skip, naming the manifest path, when it is absent**. The
two dead origin-tree tests (`ImportedBundleByteIdentityTest`,
`CrucibleHandoverBundleFidelityTest.test_each_handover_bundle_exists_and_covers_origin_file_set`) are
deleted. Detector fixtures that must contain a checkout path build it from split literals. CR-MDB-020's
§S2 anchoring gate drops `tests/` from its exemptions. The CR-MDB-022 AST gate also catches
`importlib.util.spec_from_file_location` and subprocess program strings pointing outside the repo.

### §S2 — Real-home gates become repo gates
The wave-1/2 modules (`test_core_split`, `test_model_b_skill`, `test_cr_authoring_skill`,
`test_crucible_skill`, `test_git_chezmoi_skills`, `test_memory_model`) assert `skills-src/`,
`archive/` and the repo `AGENTS.md`, never `~/.claude` or `~/.agents`; the `~/.claude/memory` set
equality is dropped. `test_worktree_flow_axi`'s two superseded classes are deleted and
`WorktreeFlowSkillConsumerNotesTest` reads `skills-src/`. `DeployedAgentsConsumerConstraintTest` and
`ImportedSkillBundleFidelityTest` are deleted (CR-MDB-025's rendering tests and the sandboxed
installer e2e prove the same). Real-home mtime guards in `test_installer`, `test_scaffold` and
`test_hooks` are dropped (every deploy test pins `--target-root`). `test_realhome_supersede.py` is
deleted, with `test_tooling_detachment.py`'s tests of its skip guards; its retained mirror-absence
assertion is covered by CR-MDB-020's gate. `test_agent_generator`'s in-place mutation of a tracked
file moves into a temp copy. `test_installer.py`'s `_run_module` calls pin `HOME` and `PATH` to the
sandbox.

### §S3 — One copy of each helper
Helpers duplicated across modules move to `tests/_helpers.py` and are imported. A gate AST-compares
module-level function bodies across `tests/*.py` and fails on a duplicate, excluding unittest hooks
(`setUpModule`, `tearDownModule`, `load_tests`); a detector fixture proves it bites.

### §S4 — Pi-only install writes nothing Claude-shaped
The existing Pi-only sandboxed install e2e additionally asserts that nothing is written under
`<target-root>/.claude/`.

### §S5 — Hygiene backlog
Every item in the backlog above is fixed, except the recorded false positive. No behaviour change.

### §S6 — `AGENTS.md` Testing & QA tells the truth
The module count, the measured baseline after this CR, the skip causes, and the naming convention as
practised (wave-1/2 `<Topic><Section>Test` / `test_s<n>_…`; later modules `<Feature>Test` with
descriptive names). The `MODELB_REALHOME_GATE` paragraph is deleted. The Crucible run command stays
as CR-MDB-020 left it.

## Acceptance criteria

### §S1
- [ ] No literal `data_projects/crucible` (or `/home/<user>/Documents/…crucible`) string in `tests/`;
      CR-MDB-020's anchoring gate covers `tests/` with no `tests/` exemption, and its exemption
      assertion is updated.
- [ ] No test loads code from outside the repo or the installed clients; the extended AST gate fails
      on a `spec_from_file_location` fixture pointing outside the repo and on a subprocess string
      naming a checkout (negative tests).
- [ ] The toon oracle and the gate-lock read skip with the manifest path in the reason when
      `~/.crucible/crucible-clients.json` is absent, and run when it is present.

### §S2
- [ ] With `HOME` pointed at an empty temp dir (user site-packages available), the full suite has
      **0 failures and 0 errors**. The run is recorded in the merge note.
- [ ] No test asserts a path under `Path.home()` except sandbox construction; the reviewed list of
      remaining `Path.home()` uses is recorded in the merge note.
- [ ] `tests/test_realhome_supersede.py` and `test_worktree_flow_axi`'s two superseded classes are
      gone; the 2026-08-27 deferred-register items (i)/(ii) are closed in the queue note.

### §S3
- [ ] No module-level function body (unittest hooks excepted) appears in two test modules; the gate
      and its detector fixture exist.

### §S4
- [ ] A Pi-only sandboxed install asserts nothing exists under `<target-root>/.claude/`.

### §S5
- [ ] Each backlog item is fixed (the false positive is recorded, unchanged); no test's behaviour
      changes — the suite count changes only by §S1–§S4's deliberate additions and deletions.

### §S6
- [ ] `AGENTS.md` Testing & QA states the real module count, the post-CR baseline (real `HOME` and
      empty `HOME`), what the remaining skips are, and the naming convention as practised; no
      `MODELB_REALHOME_GATE`.

### All
- [ ] Every deleted or migrated test is listed by id in the RED/FIX commit bodies.

## Risk

- Retargeting the wave-1/2 gates changes what they prove — repo layout, not deployed state. That is
  the 2026-07-22 rule; the installer's sha256 manifest and freshness report prove deployed state.
- Hoisting helpers touches many modules; one mechanical commit per helper family keeps a bisect
  readable.

## Non-goals

- No renaming of existing tests.
- No product-code change beyond `generator/build.py`'s import order and docstring narrowing.
- No removal of claude-code e2e sites or of the `chezmoi` bundle (CR-MDB-031).
