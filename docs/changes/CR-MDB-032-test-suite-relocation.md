# CR-MDB-032 — Test-suite relocation: no dev-checkout reach, no real-home assertions, no dead or self-defeating gates, a Pi end-to-end

**Status:** PENDING (filed 2026-09-21 from `audits/2026-09-21-codebase-review-tests.md`)
**Type:** refactor
**Priority:** P1 — in release 1.0.0, wave 2. The suite is the release gate (CR-MDB-012) and today
it is 240/7F/12S with three modules that hard-fail on any machine but this one, six that pass
only because this machine's `~/.claude` happens to match, and one gate that forbids a string
`AGENTS.md` must spell to document it.
**Depends on:** CR-MDB-021 (removes the eight chezmoi gates — this CR takes the rest) ·
CR-MDB-020 (its repo-wide "no personal-checkout path" AC; this CR is where `tests/` meets it)
**Labels:** tests, quality, refactor
**Phase:** Wave 5 (repo queue) · release 1.0.0 wave 2 (Crucible board)
**Design reference:** repo-local authoring rule 2026-07-22 ("AC gates assert repo paths") ·
standing rule 2026-09-18 (Crucible dev checkout out of bounds; installed clients at
`~/.crucible/clients/`) · DN §D14 (`~/.claude/agents` unowned legacy) · README 2026-08-27
deferred items (i)/(ii) (`test_worktree_flow_axi` drives stale copies) · `audits/…-tests.md`
§1a–§1g, §2, §3

## Context

Measured 2026-09-21 (`python3 -m unittest discover -s tests -t .`): **240 tests, 7 failures,
12 skips.** `AGENTS.md` says 240/1F/12S and 17 modules; there are 19.

| Class of defect | Sites | Audit ref |
|---|---|---|
| Dev-checkout reach (`~/Documents/data_projects/crucible/`) | 7 sites / 6 modules; `test_scaffold.py:51` and `test_hooks.py:415` load their `toon.py` in-process with **no skip guard** — hard-fail elsewhere; the CR-022 AST gate cannot see `spec_from_file_location` | §1a |
| Real-home assertions (`~/.claude`, `~/.agents`) | 8 modules, ~40 methods; wave-1/2 structural gates (001–006) assert the user's dotfiles; `test_worktree_flow_axi` runs `~/.claude/scripts/*` and never `scripts/worktree-flow.py`; `test_agent_generator` pins `~/.claude/agents` (unowned per §D14); `test_installer_assets` measures the installer's output against itself through symlinks | §1b |
| chezmoi gates | 8 — CR-021's; plus `ChezmoiSkillS3Test` pinning a retracted quirk claim in a deployed file | §1c |
| Retired-contract positive pins | `--phase`, `--orchestrator`, `no-active-cycle`/`resolve_attach_cycle` (×3 modules), STATUS-CONTRACT 1.0.0 / `lastRunCr` — block 017/019 GREEN | §1d (owned by 017/019; listed here for sequencing) |
| Vacuous / self-defeating | `AC7` `WORKFLOW_CYCLE_ID` gate (1 of the 7 failures); silent `continue` over deleted surfaces; `test_realhome_supersede` env-gated → silently green while hiding a real repo/deployed divergence; a test-of-a-test | §1e |
| Duplicated gate bodies | 6× chezmoi (021), 5–7× helper functions, 2× `build.py --list` pin, 3× `--check`, 4× claude-code e2e, 6× `WORKFLOW_CYCLE_ID == 0` | §1f |
| Dropped-target guards | 23 sites hard-wire `--harnesses claude-code`; **zero** e2e uses `pi`; roster/`CLAUDE.md`/`HARNESS_SKILL_DIRS` pins | §2 (retired by 031; this CR adds the Pi e2e first) |
| Dead tests | 2 permanent skips waiting for a retired origin dir | §3 |

Naming: 60 of ~80 classes and 112 of 240 methods ignore the `<Topic><Section>Test` /
`test_s<n>_…` convention `AGENTS.md` states. Not fixed here; `AGENTS.md` is amended to describe
the real convention (§S6).

## Scope

### §S1 — Dev-checkout removal (the three-machine test)
`test_scaffold.py` and `test_hooks.py` use `from modelb_axi import toon`. `test_toon_codec.py`'s
oracle and `test_tooling_detachment.py`'s `_gate_lock_path` read resolve through
`~/.crucible/crucible-clients.json` (CR-018's manifest) and **fail, not skip**, when absent.
`test_skills_handover.ImportedBundleByteIdentityTest` and
`test_installer_assets.CrucibleHandoverBundleFidelityTest.test_each_handover_bundle_exists…`
are deleted (dead by design). `test_realhome_supersede.py:357,366` remedy text repointed. The
CR-022 AST gate is extended to `importlib.util.spec_from_file_location` and to checkout paths
inside subprocess program strings.

### §S2 — Real-home gates → repo gates
Wave-1/2 modules (`test_core_split`, `test_model_b_skill`, `test_cr_authoring_skill`,
`test_crucible_skill`, `test_git_chezmoi_skills`, `test_memory_model`) retarget every
`Path.home()/.claude/...` assertion to `skills-src/`, `archive/`, and the repo `AGENTS.md`; the
`~/.claude/memory == 6 files` set-equality is dropped. `test_worktree_flow_axi`: delete
`WorktreeFlowCodecDeploymentTest` and `WorktreeFlowEnvelopeTest` (superseded by
`test_toon_codec`), retarget `WorktreeFlowSkillConsumerNotesTest` to `skills-src/`.
`test_agent_generator.DeployedAgentsConsumerConstraintTest` deleted (025 §S6 replaces it).
`test_installer_assets.ImportedSkillBundleFidelityTest` deleted (the sandboxed e2e in the same
file proves fidelity). Real-home mtime guards in `test_installer`/`test_scaffold`/`test_hooks`
dropped (every deploy test pins `--target-root`). `test_agent_generator:250-291`'s in-place
mutation of a tracked file moves into the tmp-repo fixture.

### §S3 — Gate correctness
`AC7` (`test_crucible_skill.py:486`) is scoped to the wrapper sentence it was written for (or
uses the split-literal idiom `test_toon_codec.py:122` already uses) so `AGENTS.md` can document
the gate. `test_cr_authoring_skill.py:281-291`'s `CONSUMER_SURFACES` drops the deleted
surfaces. `test_realhome_supersede.py` is **retired** (the installer's sha256 manifest already
guarantees deploy integrity — README 2026-08-27) together with `test_tooling_detachment.py:947-988`
which only asserts its skip guards. `ChezmoiSkillS3Test` goes with the chezmoi bundle (031) or
is retargeted to `skills-src/` if the bundle survives.

### §S4 — One gate, one place
Hoist `_split_frontmatter`, `_read`, `_files_under`, `_files_containing`,
`_archive_has_content_move`, `_run_module`, `_write_fake_executable`, the fake-uv script into
`tests/_helpers.py`. Keep one `build.py --list` pin and one `--check` pin. Replace the six
`WORKFLOW_CYCLE_ID == 0` gates with one repo-wide gate (CR-012's "permanent regression guard").

### §S5 — Pi is the exercised harness
One installer e2e and one scaffold e2e run `--harnesses pi` against a sandbox and assert:
`.agents/{skills,hooks/scripts,scripts,agents}` under the root, `.pi/extensions/*.ts` in the
scaffolded project, nothing under `<root>/.claude/`. (CR-031 later removes the claude-code
sites; this CR makes sure Pi has coverage before that.)

### §S6 — Baseline and convention truth
`AGENTS.md` Testing & QA: real module count, the measured baseline after this CR (expected:
0 environmental failures), and the naming convention as actually practised (wave-1/2
`<Topic><Section>Test`/`test_s<n>_`; wave-3+ `<Feature>Test`/descriptive) — or the rule is
dropped. The `MODELB_REALHOME_GATE` paragraph is deleted with the module.

## Acceptance criteria

- [ ] `grep -r "data_projects/crucible" tests/` → 0; the extended AST gate catches a
      `spec_from_file_location` fixture pointing outside the repo (asserted by a negative test).
- [ ] The suite passes on a machine with **no** `~/.claude` and no Crucible dev checkout
      (asserted by running it with `HOME` pointed at an empty temp dir — a CI-shaped run).
- [ ] `grep -rn "Path.home()" tests/` hits only sandbox-construction helpers, never an assertion
      target — reviewed list recorded in the close-out note.
- [ ] Failures: 0 environmental; skips: only `pi`-absent and `uv`-absent probes.
- [ ] `AC7` passes with `AGENTS.md` documenting the gate.
- [ ] No two test modules contain the same helper function body (AST-compared).
- [ ] At least one installer e2e and one scaffold e2e run with `--harnesses pi`.
- [ ] `tests/test_realhome_supersede.py` and `tests/test_worktree_flow_axi.py`'s two superseded
      classes are gone; the deferred-register items (i)/(ii) of 2026-08-27 are closed in the
      queue note.
- [ ] `AGENTS.md` Testing & QA matches the measured suite (module count, baseline, convention).

## Estimated size

~15 modules touched; mostly deletions and path retargets; one new helper module; two new e2e.
Medium. Every amendment listed by test id in the RED plan (sanctioned amendments to closed
CRs 001–006, 008, 010, 014, 016, 022).

## Risk

- Retargeting wave-1/2 gates changes what they prove (repo layout, not deployed state). That
  is the 2026-07-22 rule; the deployed-state proof is the installer's manifest.
- Some retired-contract pins (§1d) must be inverted by 017/019 *before* this CR's GREEN or
  after — the RED plan sequences against the board, never both editing the same line.

## Non-goals

- No renaming of existing tests to the naming convention.
- No new product code; the AST-gate extension and `_helpers.py` are test infrastructure.
- No removal of claude-code e2e sites beyond adding the Pi ones (CR-031).
