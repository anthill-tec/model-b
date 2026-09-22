# CR-MDB-035 — Reconcile PRD §4 success criteria with the shipped tree

**Status:** PENDING
**Type:** design-reconciliation
**Priority:** P1 — one criterion currently contradicts an approved CR, so the PRD and the queue
disagree about what "done" means.
**Depends on:** CR-MDB-021 (criterion 6), CR-MDB-025 + CR-MDB-031 (criterion 4's counts)
**Labels:** prd, verification, docs
**Phase:** Wave 5 (repo queue, historical) · release 1.0.0 wave 2, late
**Origin:** the only genuinely unbuilt part of the voided CR-MDB-012 (§S1). A release is a
boundary event and cannot be a CR — but *re-measuring the design contract against the tree it
was written for* is ordinary work, and it was hiding inside the release CR.

## Context

PRD §4's six success criteria were written at the start of the rationalization, before most of
the tree existed. Measured against the shipped repo on 2026-09-22 (commands and results below),
**two hold as written, three are stale, and one contradicts an approved CR**:

| # | Criterion | Measured 2026-09-22 | Verdict |
|---|---|---|---|
| 1 | always-loaded core 621 → ≤100 lines, one file | `wc -l ~/.claude/CLAUDE.md` = **69** | holds |
| 2 | zero banned references outside `archive/` (incl. the `.lavish/` carve-out) | `python3 -m unittest tests.test_client_verb_sweep` → **25 tests OK** | holds |
| 3 | "`memory/` = the D5 reference library exactly" | there is no `memory/`; the library is `skills-src/memory-templates/` (8 files) | **stale wording** |
| 4 | "`build.py --check` idempotent; 16 agents generated, 13 bespoke intact" | `--check` → `clean: live tree matches regeneration`; 16 generated ✓; but 25 files deployed in `~/.agents/agents/`, and DN §D14 dropped claude-code while CR-MDB-025 adds Pi definitions | **counts go stale inside this wave** |
| 5 | every crucible client smoke-passes; "closes only when Crucible ships" | Crucible 0.2.x shipped; 5 stack clients installed at `~/.crucible/clients/`; `vscode-crucible.py` never shipped (Crucible mail #1369) | **needs restating** |
| 6 | "`chezmoi diff` clean after every wave; deleted files stay deleted after fresh `apply`" | **CR-MDB-021 retires the eight gates that assert this** | **contradicts an approved CR** |

Criterion 6 is the sharp one. As long as it stands, the PRD demands the property CR-021 is
approved to delete — so whichever lands second silently contradicts the first. A design contract
that disagrees with the queue is worse than a missing one, because both surfaces look
authoritative.

## Scope

### §S1 — Re-measure every criterion, record the command
Each of the six is re-run and its result recorded with the exact command that produced it. A
measurement without its command is an assertion, not evidence.

### §S2 — Amend what no longer describes the design
Criteria 3, 4, 5 and 6 are rewritten **in the PRD** to state what the design now is. Amendments
carry the date and the CR/DN that moved the design (021 for 6, D14 + 025 for 4, the D5 amendment
for 3, Crucible 0.2.x for 5). A criterion is never quietly deleted or marked "n/a" — if it no
longer applies, the PRD says why, so the reasoning survives.

### §S3 — Criterion 6's replacement
`chezmoi diff` cleanliness is not a Model B property — it measures the *user's* dotfile tree
(that is CR-021's whole argument). The criterion is replaced by what the PRD actually wanted:
deployed state matches the manifest, and a deletion stays deleted across a redeploy. Stated in
terms the installer owns, so it is testable inside this repo.

### §S4 — Criterion 4's counts become derived, not literal
"16 generated, 13 bespoke" is a snapshot that CR-025 and CR-031 will invalidate. Restate as a
property (`build.py --check` reports clean; every generated agent has a stack×role source; no
bespoke definition is clobbered) rather than two integers that rot.

## Acceptance criteria

- [ ] All six criteria are re-measured and each records the exact command and its output.
- [ ] Criteria 3, 4, 5, 6 are amended in `docs/research/PRD-model-b-rationalization.md`, each with
      the date and the CR/DN that moved the design.
- [ ] **No criterion contradicts a merged CR** — specifically, §4 no longer demands `chezmoi diff`
      cleanliness after CR-MDB-021 has landed.
- [ ] Criterion 4 is expressed as a property, not as literal counts.
- [ ] Criterion 5 states Model B's half (documentation of the clients) separately from Crucible's
      half (shipping them), and names `vscode-crucible.py` as not shipped.
- [ ] No criterion is deleted without a recorded reason.
- [ ] The suite is unchanged by this CR except where a gate cites an amended criterion.

## Estimated size

One PRD section, re-measured and rewritten. No production code.

## Non-goals

- No new criteria. This reconciles what exists; adding success criteria is a design act that
  needs its own discussion.
- No release gating. This CR does not decide when 1.0.0 ships (user ruling 2026-09-21).
