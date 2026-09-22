# CR-MDB-021 — Retire chezmoi introspection from the test suite: eight release-gating gates assert on the user's dotfile manager, not on Model B

**Status:** PENDING
**Type:** maintenance
**Priority:** P1 (blocks release 1.0.0 — eight gates in the release-verification suite are false-green and flap on unrelated user dotfile activity)
**Depends on:** —
**Labels:** tests, chezmoi, release-gate, patch
**Phase:** Wave 5
**Design reference:** user directive 2026-08-27 ("local scripts are not to be maintained by chezmoi; management would only apply to harness-installed skills, and that is not required either") · CR-MDB-016 orchestrator-approved amendment, recorded verbatim at `tests/test_agent_generator.py:35-46` ("the Model B system carries NO chezmoi dependencies — Model B tests must not introspect the user's live chezmoi tree/history") · PRD §D9/§D10 (the repo is the workshop, the installer is the only deployment channel) · project memory `repo-local-authoring-rule`

## Amendments 2026-09-21 (from `audits/2026-09-21-codebase-review-{tests,docs}.md`)

- **Baseline re-measured 2026-09-22 05:09:48Z at `b2fb822`: 361 tests / 6 failures / 12 skips.**
  All six failures are this CR's `chezmoi diff` gates (`~/.claude/AGENTS.md` mode 100600→100644
  and a removed block in the user's live file vs their chezmoi source) — the false-green→false-red
  flap this CR predicted. **Both earlier figures in this spec are superseded**: the Suite AC's
  194-based arithmetic and this amendment's own "240/7F/12S". Predicted post-CR state is derived
  in the Suite AC below; re-measure at RED rather than trusting any number written here.
- **§S4 scope: `contracts/` yes, `docs/research/` NO.** `contracts/lean-ctx.md:33` ("every
  `~/.claude` mutation in this workflow goes through chezmoi") is in scope. **PRD §4.6 is NOT —
  it belongs to CR-MDB-035**, which reconciles all six PRD §4 criteria together; amputating one
  early would leave §4 half-reconciled by two CRs. PRD §D9's legacy narrative ("chezmoi remains
  only for the user's own dotfile operations … never as a CR deployment channel again") is design
  rationale that already says what this CR enforces — it stays, in both CRs.
- **Correction to an earlier amendment:** it claimed `DN-scaffold-packaging.md:59-61` §6 describes
  the installer printing `chezmoi forget/destroy` paths, "the very message §S3 drops". Measured
  2026-09-22: **`modelb_axi/` contains zero `chezmoi` references** — that print was never built.
  The DN describes unshipped behaviour (out of scope here); the message §S3 actually rewords is in
  `tests/test_realhome_supersede.py:346,350`.
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
| `test_crucible_skill.py:392` | `test_s4_chezmoi_diff_clean_on_cr_touched_paths` | `test_s4_ten_skill_dirs_and_memory_stub_removed_with_archived_content` (`:278`) |
| `test_cr_authoring_skill.py:231` | `test_s3_chezmoi_diff_clean_on_cr_touched_paths` | `test_s3_legacy_memory_files_removed_with_archived_content` (`:199`) |
| `test_git_chezmoi_skills.py:272` | `test_s4_chezmoi_diff_clean_on_cr_touched_paths` | `test_s4_legacy_memory_files_removed_with_archived_content` (`:238`) |
| `test_memory_model.py:281` | `test_s4_chezmoi_diff_clean_on_cr_touched_paths` | `test_s3_deletion_targets_removed_with_content_preserving_archive` (`:165`) + `test_s4_global_memory_has_exactly_the_six_d5_files` |
| `test_realhome_supersede.py:392` (class; method `:400`, argv `:403`) | `ChezmoiRoundTripPreconditionTest.test_chezmoi_status_exits_zero` | none needed — it probes the user's dotfile source health, not a Model B invariant |

The removals are sanctioned amendments to CLOSED CRs (001, 002, 003, 004, 005, 006, 016):
the mechanism is retired, the acceptance criterion each gate was attached to is retained by
its sibling, and the policy authorising it is on record in-tree.

## Scope

### §S1 — The guard that makes the policy self-enforcing
Add to `tests/test_installer_assets.py` (beside the existing zero-chezmoi-refs-under-
`generator/` gate at `:446`) a repo-side gate asserting that no module under `tests/`,
`modelb_axi/`, or `hooks-src/scripts/` **invokes** the `chezmoi` binary. Static source
inspection only; the gate never runs `chezmoi` itself. This is the RED: it fails on the eight
methods that exist today.

**The matcher must detect INVOCATION, not the word.** A grep for the quoted token `"chezmoi"`
false-REDs on three lines this CR deliberately retains — `test_git_chezmoi_skills.py:169`
(`assertEqual(..., "chezmoi")` on the shipped SKILL.md's frontmatter name), `:344`
(`assertIn("chezmoi", content.lower())`), and `test_installer_assets.py:89` (`"chezmoi"` in the
Model-B-owned bundle tuple). The gate matches only:

- `shutil.which("chezmoi")`, and
- a `subprocess` argv whose FIRST element is `chezmoi` or a variable bound to `shutil.which`.

This is the same defect class as the `test_ac7` substring gate CR-MDB-017 repaired — a whole-file
substring count cannot tell naming a thing from doing it. The gate therefore ships with a
**detector-bites fixture**: a synthetic source string containing both a real invocation and each
of the three retained forms, asserting the matcher fires on the first and stays silent on the
other three.

`skills-src/chezmoi/` is explicitly exempt and stays shipped — it documents the USER's own
dotfile discipline and is not a Model B dependency on chezmoi.

### §S2 — Remove the seven `diff`/`apply` methods and their dead constants
Delete the seven methods named in the Context table, and the now-unreferenced
`CHEZMOI_SCOPE_PATHS` tuples at `test_cr_authoring_skill.py:35`, `test_crucible_skill.py:119`,
`test_git_chezmoi_skills.py:39`, `test_memory_model.py:64`, plus the inline five-path argv
lists in `test_core_split.py` and `test_model_b_skill.py`. Any `import shutil` left with no
other consumer in the module goes with them. Sibling methods are untouched.

(Measured 2026-09-22: those four tuples have exactly four consumers, each inside a method this
CR deletes — no external consumer anywhere under `tests/` or `modelb_axi/`.)

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

### §S4 — Purge the retired mechanism from the prose that INSTRUCTS Model B work
`AGENTS.md`, `contracts/lean-ctx.md`, `skills-src/memory-templates/`, `docs/changes/README.md`
and any OPEN CR must not instruct a Model B CR to perform a `chezmoi diff`/`add`/`apply` step as
part of Model B work. Measured targets: `AGENTS.md:49` (the "chezmoi-managed, so anything written
there is reverted" rationale → "not Model B-owned"), `AGENTS.md:109` (the per-mutation discipline
bullet), `AGENTS.md:135` (lists "`chezmoi diff` cleanliness" among what the gates assert), and
`contracts/lean-ctx.md:33`.

**CLOSED CRs are historical record and are NOT edited.** Twenty-two files under `docs/changes/`
mention chezmoi; most are closed specs (001–016) whose chezmoi steps *actually happened* — PRD
§D9 states waves 1–2 "legitimately deployed through it pre-installer and **their history
stands**". Rewriting them would falsify the record, the same error the `.lavish/` carve-out
exists to prevent. A closed CR describing what it did is not an instruction to do it again.

Statements about the USER's dotfile discipline (the `chezmoi` skill bundle, the project memory
note) are out of scope and stay. PRD §4.6 belongs to CR-MDB-035, not here.

**Describing ≠ instructing.** `AGENTS.md:135` and `:138` NAME these gates in order to record that
they were retired; §S4's check must not be a substring sweep, or the file becomes forbidden from
documenting its own history — precisely the `test_ac7` trap CR-MDB-017 had to repair.

## Acceptance criteria

### §S1
- [ ] `tests/test_installer_assets.py` carries a gate asserting zero `chezmoi` binary
      **invocations** under `tests/`, `modelb_axi/`, and `hooks-src/scripts/`, matched by
      static source inspection of `shutil.which("chezmoi")` and of subprocess argv heads.
- [ ] The gate ships with a **detector-bites fixture**: against a synthetic source containing
      (a) a real `chezmoi` invocation, (b) `assertEqual(..., "chezmoi")`, (c)
      `assertIn("chezmoi", ...)` and (d) `"chezmoi"` as a bundle-name list element, the matcher
      fires on (a) ONLY.
- [ ] The three retained live lines — `test_git_chezmoi_skills.py:169`, `:344`, and
      `test_installer_assets.py:89` — are present and do NOT trip the gate.
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
- [ ] Every class docstring that described its section as "(chezmoi discipline)" names what the
      class actually asserts — removal plus content-preserving archive — so no module documents a
      mechanism it no longer uses.
- [ ] Every sibling method named in the Context table still exists and still passes.
- [ ] `ChezmoiRoundTripPreconditionTest` does not exist; the `~/.claude/scripts/*crucible*`
      absence assertion at `test_realhome_supersede.py:300` survives with its assertion
      unchanged and its message free of `chezmoi`.
- [ ] `MODELB_REALHOME_GATE=1 python3 tests/test_realhome_supersede.py` exits 0 with no
      chezmoi invocation.

### §S4
- [ ] Neither `AGENTS.md`, `contracts/lean-ctx.md`, any `skills-src/memory-templates/*.md`,
      `docs/changes/README.md`, nor any OPEN CR instructs a `chezmoi` step as part of Model B CR
      work. Specifically `AGENTS.md:49`, `:109`, `:135` and `contracts/lean-ctx.md:33` no longer
      prescribe a dotfile-manager mechanism for Model B work.
- [ ] **CLOSED CR specs under `docs/changes/` are unmodified** — `git diff` touches no
      `CR-MDB-0{01..16}-*.md`. Their chezmoi steps are historical record (PRD §D9).
- [ ] The §S4 check distinguishes instructing from describing: `AGENTS.md` may still NAME the
      retired gates when recording that they were retired.

### Suite
- [ ] Re-measured at RED and again at GREEN. From the measured baseline of **361 / 6F / 12S**
      (2026-09-22 05:09:48Z, `b2fb822`), the predicted post-CR state is **354 collected
      (361 − 8 removed + 1 added), 0 failures, 11 skips** — all six failures are the removed
      gates, and skips drop by one because `test_chezmoi_status_exits_zero` is collected-but-
      skipped under the realhome gate. A deviation from 354/0F/11S is investigated, not accepted.
- [ ] `AGENTS.md`'s Testing & QA baseline sentence (`:138`) records the new figures, and `:135`
      no longer lists `chezmoi diff` cleanliness among what the gates assert. **Re-recorded ONCE,
      as a close-out step of the final cycle** — not per-cycle.
- [ ] Full regression is ingested to Crucible under the cycle's agent id.

## Estimated size

7 test modules edited (8 methods and 4 constants removed, 1 gate added, docstrings
corrected). No `modelb_axi/` change, no `skills-src/` content change, no installer change.

## Risk

- The suite's collected-test count drops by 8 and gains 1. Any consumer pinning a literal count
  must move in the same commit — `AGENTS.md:138`'s baseline sentence is the only such consumer
  (measured: no test asserts a literal collected count).
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
