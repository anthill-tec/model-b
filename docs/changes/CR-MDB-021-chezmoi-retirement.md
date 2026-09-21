# CR-MDB-021 — Retire chezmoi introspection from the test suite: eight release-gating gates assert on the user's dotfile manager, not on Model B

**Status:** PENDING
**Type:** maintenance
**Priority:** P1 (blocks release 1.0.0 — eight gates in the release-verification suite are false-green and flap on unrelated user dotfile activity)
**Depends on:** —
**Labels:** tests, chezmoi, release-gate, patch
**Phase:** Wave 5
**Design reference:** user directive 2026-08-27 ("local scripts are not to be maintained by chezmoi; management would only apply to harness-installed skills, and that is not required either") · CR-MDB-016 orchestrator-approved amendment, recorded verbatim at `tests/test_agent_generator.py:35-46` ("the Model B system carries NO chezmoi dependencies — Model B tests must not introspect the user's live chezmoi tree/history") · PRD §D9/§D10 (the repo is the workshop, the installer is the only deployment channel) · project memory `repo-local-authoring-rule`

## Amendments 2026-09-21 (from `audits/2026-09-21-codebase-review-{tests,docs}.md`)

- **Measured today: all six `chezmoi diff` gates FAIL** (`~/.claude/AGENTS.md` mode 100600→100644
  and a removed block in the user's live file vs their chezmoi source) — the false-green→false-red
  flap this CR predicted. The suite is 240/7F/12S, not the 194-based arithmetic in the Suite AC
  (`:139-142`); re-measure at RED against 240 and record the post-removal baseline.
- **§S4 scope extended to `docs/research/` and `contracts/`:** PRD §4.6 ("`chezmoi diff` clean
  after every wave" as a success criterion), PRD §D9 ("chezmoi remains … for destroying legacy
  files"), `DN-scaffold-packaging.md:59-61` §6 (installer prints `chezmoi forget/destroy` paths —
  the very message §S3 drops), `contracts/lean-ctx.md:33-34`, and `AGENTS.md:49` (the "chezmoi-
  managed, so anything written there is reverted" rationale → "not Model B-owned").
- **The `chezmoi` skill BUNDLE is not this CR's** — its retirement is CR-MDB-031 §S4 (§S0
  question). This CR only removes chezmoi from the tests and the prose. `ChezmoiSkillS3Test`
  (`tests/test_git_chezmoi_skills.py:151-233`, pins a retracted quirk claim in a *deployed* file)
  goes with the bundle or is retargeted to `skills-src/` by CR-MDB-032.
- **`test_realhome_supersede.py:391-419`'s `chezmoi status` probe** is removed here (§S3); the
  module itself is retired by CR-MDB-032 §S3.

## Context

Eight test methods across seven modules shell out to the user's `chezmoi` binary and assert
on the state of the user's dotfile source repo. They are the last holdouts of a policy that
was already decided and half-executed: CR-MDB-016 re-mechanized `BespokeUntouchedS4Test`
repo-side for exactly this reason, and its docstring records the directive as
orchestrator-approved. The sweep never reached the other seven modules.

**These gates prove almost nothing today — measured, not assumed (2026-08-27).**

Each `chezmoi diff` gate passes five path arguments — `~/.claude/AGENTS.md`,
`~/.claude/CLAUDE.md`, `~/.claude/agents`, `~/.claude/memory`, `~/.claude/skills` — and
asserts empty stdout plus exit 0. Three of the five are inert:

- `chezmoi diff` defaults to `--recursive=false` (unlike `chezmoi status`, which defaults
  true). The three DIRECTORY arguments therefore compare the directory entries themselves,
  never their children — 30 managed files under `agents/` and 6 under `memory/` are outside
  the comparison the gate claims to make.
- The `skills/` argument cannot see the surfaces it exists to protect. `chezmoi managed`
  reports only the user's own unrelated bundles under `.claude/skills` (`ci-monitor`,
  `code-health`, `gap-analysis`, `git-flow-develop-gitops`, `git-flow-release`,
  `refactorer-java`, `refactorer-rust`, `reviewer`, `status-report`). Every Model B-owned
  bundle is unmanaged — CR-MDB-016 de-chezmoi'd the skills tree — so no drift in a Model B
  skill can ever register in this diff. The gate is structurally incapable of failing for
  the reason it was written.

Only the two file arguments are live comparisons, and what they compare is whether the
USER's dotfile source matches the USER's home directory — a property Model B neither owns
nor can fix. All eight methods currently pass, which is worse than failing: the release
suite reports coverage it does not have.

**The user directive settles the disposition.** Model B's local scripts and skills are not
chezmoi-maintained; deployment is the `modelb-axi` installer's job, which already guarantees
integrity by sha256 manifest comparison (`modelb_axi/deploy.py`), and chezmoi management of
the installed copies is not required either. There is no version of this gate worth
repairing: adding `--recursive` would deepen a dependency the system is specified not to
have, and would make the release suite fail on unrelated `.bashrc` activity.

**No coverage is lost by removal.** Every one of the seven `diff`/`apply` methods sits
beside a sibling that carries the actual acceptance criterion against the live tree and the
repo archive — verified per module:

| Module | Method removed | Sibling that carries the AC |
|---|---|---|
| `test_core_split.py:254`, `:296` | `test_s5_chezmoi_diff_clean_on_cr_touched_paths`, `test_s5_chezmoi_apply_dry_run_no_shim_mentions` | the `§S5` shim-removal + archive assertions (`:207-252`) |
| `test_model_b_skill.py:232` | `test_s4_chezmoi_diff_clean_on_cr_touched_paths` | `test_s4_memory_shim_files_removed_and_archived_under_wave2_with_preserved_content` (`:212`) |
| `test_crucible_skill.py:329` | `test_s4_chezmoi_diff_clean_on_cr_touched_paths` | `test_s4_ten_skill_dirs_and_memory_stub_removed_with_archived_content` (`:278`) |
| `test_cr_authoring_skill.py:231` | `test_s3_chezmoi_diff_clean_on_cr_touched_paths` | `test_s3_legacy_memory_files_removed_with_archived_content` (`:199`) |
| `test_git_chezmoi_skills.py:272` | `test_s4_chezmoi_diff_clean_on_cr_touched_paths` | `test_s4_legacy_memory_files_removed_with_archived_content` (`:238`) |
| `test_memory_model.py:281` | `test_s4_chezmoi_diff_clean_on_cr_touched_paths` | `test_s3_deletion_targets_removed_with_content_preserving_archive` (`:165`) + `test_s4_global_memory_has_exactly_the_six_d5_files` |
| `test_realhome_supersede.py:335` | `ChezmoiRoundTripPreconditionTest.test_chezmoi_status_exits_zero` | none needed — it probes the user's dotfile source health, not a Model B invariant |

The removals are sanctioned amendments to CLOSED CRs (001, 002, 003, 004, 005, 006, 016):
the mechanism is retired, the acceptance criterion each gate was attached to is retained by
its sibling, and the policy authorising it is on record in-tree.

## Scope

### §S1 — The guard that makes the policy self-enforcing
Add to `tests/test_installer_assets.py` (beside the existing zero-chezmoi-refs-under-
`generator/` gate at `:370`) a repo-side grep gate asserting that no module under `tests/`,
`modelb_axi/`, or `hooks-src/scripts/` invokes the `chezmoi` binary — no `"chezmoi"` in a
`subprocess` argv, no `shutil.which("chezmoi")`. Static source inspection only; the gate
never runs `chezmoi` itself. This is the RED: it fails on the eight methods that exist
today.

`skills-src/chezmoi/` is explicitly exempt and stays shipped — it documents the USER's own
dotfile discipline and is not a Model B dependency on chezmoi.

### §S2 — Remove the seven `diff`/`apply` methods and their dead constants
Delete the seven methods named in the Context table, and the now-unreferenced
`CHEZMOI_SCOPE_PATHS` tuples at `test_cr_authoring_skill.py:35`, `test_crucible_skill.py:62`,
`test_git_chezmoi_skills.py:39`, `test_memory_model.py:64`, plus the inline five-path argv
lists in `test_core_split.py` and `test_model_b_skill.py`. Any `import shutil` left with no
other consumer in the module goes with them. Sibling methods are untouched.

Class docstrings that describe the section as "(chezmoi discipline)" are corrected to name
what the class actually asserts — removal plus content-preserving archive — so the module
does not document a mechanism it no longer uses.

### §S3 — Remove the real-home chezmoi probe
Delete `ChezmoiRoundTripPreconditionTest` from `tests/test_realhome_supersede.py`. Its AC6
subject is the health of the user's chezmoi source, not a Model B invariant, and the CR that
introduced it (016) is closed with its retirement work done.

Retain the retired-mirror assertion at `:300` — under the standing directive that Model B
maintains none of Crucible's client scripts it is now doubly load-bearing — but reword its
failure message to drop the `chezmoi destroy/forget` instruction, since Model B no longer
prescribes a dotfile-manager mechanism for a tree it does not own.

### §S4 — Purge the retired mechanism from the prose that gates the release
`docs/changes/`, `AGENTS.md` and `skills-src/memory-templates/` must not instruct a Model B
CR to perform a `chezmoi diff`/`add`/`apply` step as part of Model B work. Statements about
the USER's dotfile discipline (the `chezmoi` skill, and the project memory note) are out of
scope and stay.

## Acceptance criteria

### §S1
- [ ] `tests/test_installer_assets.py` carries a gate asserting zero `chezmoi` binary
      invocations under `tests/`, `modelb_axi/`, and `hooks-src/scripts/`, matched by
      static source inspection.
- [ ] That gate invokes no subprocess named `chezmoi` and reads nothing under `$HOME`.
- [ ] The gate FAILS against the pre-§S2 tree (demonstrated at RED) and passes after.
- [ ] `skills-src/chezmoi/SKILL.md` still exists and is still deployed by the installer's
      asset set — the exemption is asserted, not implied.

### §S2 / §S3
- [ ] Zero occurrences of the string `chezmoi` under `tests/` other than: the exemption
      assertion in `test_installer_assets.py`, the `skills-src/chezmoi` bundle-name
      references in the deploy/asset tests, and `test_git_chezmoi_skills.py`'s assertions
      about the CONTENT of the shipped `chezmoi` SKILL.md (`§S3` — frontmatter name,
      `chezmoi destroy`, `resurrect`, `autoCommit`), which test a Model B artifact and are
      retained unchanged.
- [ ] No test module calls `shutil.which("chezmoi")`.
- [ ] `CHEZMOI_SCOPE_PATHS` does not appear anywhere under `tests/`.
- [ ] Every sibling method named in the Context table still exists and still passes.
- [ ] `ChezmoiRoundTripPreconditionTest` does not exist; the `~/.claude/scripts/*crucible*`
      absence assertion at `test_realhome_supersede.py:300` survives with its assertion
      unchanged and its message free of `chezmoi`.
- [ ] `MODELB_REALHOME_GATE=1 python3 tests/test_realhome_supersede.py` exits 0 with no
      chezmoi invocation.

### §S4
- [ ] No file under `docs/changes/`, and neither `AGENTS.md` nor any
      `skills-src/memory-templates/*.md`, instructs a `chezmoi` step as part of Model B CR
      work.

### Suite
- [ ] `python3 -m unittest discover -s tests -t .` collects 194 − 8 = **186 tests** plus the
      one gate added by §S1 = **187**, with failures and skips no worse than the recorded
      baseline of 7 and 11 minus any that were chezmoi-dependent.
- [ ] Full regression is ingested to Crucible under the cycle's agent id.

## Estimated size

7 test modules edited (8 methods and 4 constants removed, 1 gate added, docstrings
corrected). No `modelb_axi/` change, no `skills-src/` content change, no installer change.

## Risk

- The suite's collected-test count drops by 8. Any consumer pinning the literal 194 must
  move to the new number in the same commit — `AGENTS.md`'s Testing & QA baseline sentence
  is one such consumer and is in scope for the update.
- Removing a method from a CLOSED CR's gate set is a sanctioned amendment, justified by the
  in-tree 016 precedent. It must be recorded in the queue footer, not left implicit.
- `test_git_chezmoi_skills.py` is the trap: its `§S3` class legitimately tests the CONTENT
  of the shipped `chezmoi` skill and must survive intact. Only its `§S4` `chezmoi diff`
  method is removed.

## Non-goals

- No deletion or de-scoping of the `skills-src/chezmoi/` bundle.
- No change to the user's chezmoi source repo, and no `chezmoi` command run by this CR.
- No decision about whether the user's `~/.claude/scripts/` tooling stays chezmoi-managed —
  that is the user's dotfile business, outside this repo.
- No `--recursive` repair of the removed gates.
