# CR-MDB-012 — Release 1.0.0: the verification suite, the archive mapping, and the master tag

**Status:** PENDING — **SEED, not the finished spec.** Authored 2026-09-21 because the queue row
has linked to this filename since 2026-07-20 and the file never existed, and because CR-MDB-025's
board-vs-repo title drift produced a release-gate requirement that needed a home *now* rather than
at release-open. The verification suite below is the known set; the release CR is completed at
release-open from the then-current board, per the standing rule that a release CR bundles the
final gates.
**Type:** release
**Priority:** P1 — the release itself
**Depends on:** every CR in the 1.0.0 roadmap (board-authoritative; currently 001–011, 013–033 with
007 superseded). Read the dependency set from `cr-plan`/`queue`, never from this line — it will go
stale and the board will not.
**Labels:** release, verification, archive, tag
**Phase:** Wave 5 (repo queue, historical) · release 1.0.0 wave 2, LAST (Crucible board)
**Design reference:** `docs/research/PRD-model-b-rationalization.md` §4 (the verification criteria)
· `docs/changes/README.md` (the queue and its dated footer record) · `skills-src/git-workflow/SKILL.md`
(the 10-step git-flow release) · Crucible 0.2.2's `milestone --crs --packages --released-at`
(CR-CRU-129: a milestone is a record, not an event) — the verb that closes a release

## Context

Model B's delivery ends in a standard git-flow release, not a close-out wave: the verification
suite and `archive/mapping.md` ride the release branch and `master` is tagged. This CR is that
release.

Three things make it more than a tag:

1. **PRD §4's criteria were written before most of the tree existed.** They must be re-measured
   against the shipped repo, not assumed — and at least one (criterion 2, zero `/api/ingest/`
   outside `archive/`) only became satisfiable when CR-MDB-017 landed.
2. **The suite baseline has a single owner for the first time.** Measured 2026-09-21 at 361 tests
   / 6 failures / 12 skips, and all six are the `chezmoi diff` gates CR-MDB-021 retires. The
   release gate is therefore "zero failures after 021", not "compare against a documented set of
   expected failures" — the first time that has been true.
3. **Publication is now part of the release** (DN-multi-harness §D15.2, CR-MDB-029): tag, bump the
   Pi package version, publish, and prove `pi install` resolves it on a clean profile.

## Scope

### §S1 — Re-measure PRD §4's verification criteria against the shipped tree
Each criterion is re-run and its result recorded with the command that produced it. A criterion
that no longer describes the design is amended in the PRD, not quietly skipped.

### §S2 — The suite gate
`python3 -m unittest discover -s tests -t .` reports **zero failures**. This is only reachable
after CR-MDB-021 retires the six chezmoi gates; if 021 slips, the release slips or 021's removal
rides this CR — decide explicitly, never by leaving six failures "expected".

### §S3 — `archive/mapping.md`
The old-path → new-path map for everything relocated across waves 1–5, so a reader of the archive
can find where a file went.

### §S4 — Board-vs-repo parity gate (added 2026-09-21 from the CR-MDB-025 drift)
**The defect this closes, measured:** CR-MDB-025's spec was rewritten on 2026-09-21 to drop OMP
and target Pi, and its repo queue row was updated in the same commit — but its **board title**,
posted by `cr-plan` on 2026-09-18, still read *"OMP as a first-class deploy target"*. The board is
the authority for queue status, so the authoritative surface contradicted the spec beside it for
three days. Three more entries (018, 019, 024) had drifted the same way.

It survived because **nothing can see it**: the `queue` read verb returns `cr, wave, status,
planId` and no title, so no read-only check compares them. The only echo is `cr-plan --full` on
write.

- Every CR in the release has a board title that matches its spec's H1, verified per CR via
  `cr-plan --full`'s echoed `entry.title` (a write that is idempotent when the title already
  matches).
- The sweep is recorded in the release notes with the date and the CRs corrected.
- **Raise the read-path gap with Crucible** on the #1336 lineage: a `queue` that returned titles
  would make this checkable read-only, by anyone, at any time. Model B maintains none of their
  client code, so this is a request, not a patch.

### §S5 — Release execution
The 10-step git-flow release per `skills-src/git-workflow/SKILL.md`: release branch, version bump,
verification, merge to `master`, tag, back-merge to `develop`. Then `milestone --crs --packages
--released-at` records the release on the board, and the Pi package (CR-MDB-029) is published and
smoke-installed on a clean profile.

### §S6 — Close the record
`docs/changes/README.md`'s footer gains the release entry; the deferred-items register is swept
one final time; anything still open becomes a post-1.0.0 CR rather than an unrecorded loose end.

## Acceptance criteria

- [ ] Every PRD §4 criterion is re-measured, with the command and result recorded; amendments to
      criteria that no longer describe the design are made IN the PRD.
- [ ] `python3 -m unittest discover -s tests -t .` → **zero failures**; the count is recorded in
      `AGENTS.md`'s baseline sentence.
- [ ] PRD §11 criterion 2 (`/api/ingest/`, zero outside `archive/`) passes, including `.lavish/`
      or its explicit carve-out (CR-MDB-017 §S4d).
- [ ] `archive/mapping.md` exists and every relocated path resolves.
- [ ] **§S4: every release CR's board title matches its spec H1**, proven per CR by the echoed
      `entry.title`; the sweep and its date are in the release notes.
- [ ] **§S4: the read-path gap is raised with Crucible** (a `queue` that returns titles), on the
      #1336 lineage, as a request.
- [ ] `master` carries the annotated tag; `develop` is back-merged; the board records the release
      via `milestone --crs --packages --released-at`.
- [ ] The Pi package publishes and `pi install` resolves it on a clean profile (CR-MDB-029 §S5).
- [ ] The queue's footer records the release; the deferred register is empty or every item is a
      filed post-1.0.0 CR.

## Estimated size

Verification and record-keeping, not construction — but the suite gate depends on CR-MDB-021 and
the publication step on CR-MDB-029, so the release cannot be scheduled before both.

## Risk

- **A release CR authored early rots.** This file is a SEED: its dependency line, its criteria
  list and its baseline figure are all snapshots. Re-derive each from the board and a fresh
  measurement at release-open; do not trust this document's numbers.
- **The parity gate is a write-sweep, not a read-check**, until Crucible's `queue` returns titles.
  A sweep proves parity at a moment; it cannot prevent the next drift.

## Non-goals

- No new features. A release CR ships what the wave built.
- No Crucible client changes — Model B maintains none (standing directive).
