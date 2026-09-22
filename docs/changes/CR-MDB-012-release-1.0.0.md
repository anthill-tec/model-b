# CR-MDB-012 — Release 1.0.0 (SUPERSEDED — a release is not a CR)

**Status:** **VOID** 2026-09-22 (board `state: VOID`), after being superseded by **CR-MDB-034**.
**Do not execute this document.** It is retained only so the reasoning that retired it stays on
the record.

A re-read on 2026-09-22 found ONE part of it was real unbuilt work rather than release ritual:
**§S1's re-measurement of PRD §4**. Measured that day, two criteria hold, three are stale and
criterion 6 (`chezmoi diff` clean) *contradicts approved CR-MDB-021*. That work is now
**CR-MDB-035**. The board cannot un-supersede an entry, so 012 could not simply be renamed —
it was voided and the work refiled under its own id.

**Why it was wrong.** This CR treated the release as a work item: 25 dependency edges expressing
"the wave must finish", acceptance criteria firing at release time, and — worst — the release
PROCEDURE copied into the spec. All three are errors, ruled by the user on 2026-09-21:

- **A release is a BOUNDARY EVENT, not a CR.** It happens when the wave carrying it drains its
  queue AND a human approves starting it. A draining queue is a signal; the decision is the
  human's. Dependency edges on a release CR duplicate the first and usurp the second.
- **CRs do not gate releases.** A CR describes work. Nothing in the queue may claim the authority
  to say a release may proceed.
- **The procedure belongs to memory**, not a spec: `skills-src/git-workflow/SKILL.md` §Releases,
  loaded at release time. A procedure with two homes drifts — the exact defect this document's
  own §S4 was written to gate, committed by the document that gated it.

**Where its content went:**

| Content | New home |
|---|---|
| Release boundary rules, the 10-step `git flow release`, build-from-master, ask-before-releasing | `skills-src/git-workflow/SKILL.md` §Releases (memory) |
| "A release is not a CR"; work a release needs is an ordinary CR | `skills-src/cr-authoring/SKILL.md` §queue (memory) |
| Board-vs-repo title parity (the drift that exposed it) | `skills-src/cr-authoring/SKILL.md` §queue, as a standing rule checked when a spec's subject changes — plus a request to Crucible for a `queue` that returns titles |
| `archive/mapping.md` | **CR-MDB-034** |
| §S1 — re-measure PRD §4, amend what no longer describes the design | **CR-MDB-035** (the other genuine deliverable, found on the 2026-09-22 re-read) |
| PRD §4 re-measurement, the zero-failure suite, closing the record | the release ritual in memory; the suite is simply expected to be green when a release is proposed |

The original text follows, unedited below this banner, as the record of what was retired.

---


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

**Governed by the `git-workflow` skill (§Releases) — memory, not this document.** The 10-step
`git flow release` is non-negotiable and is NOT restated here; a procedure with two homes drifts,
and the skill is the one that is loaded at release time. Read it then.

Only the project deltas the skill cannot know belong in this CR:

- **The version lives in two files** — `pyproject.toml` `[project] version` and
  `modelb_axi/__init__.py` `__version__` (both `0.1.0.dev0` today), plus the Pi package's
  `package.json` if CR-MDB-029 has landed.
- **Model B is a submodule.** The released pointer must reach the Roundhouse root, or the tag is
  unreachable from a fresh clone — `scripts/stack-doctor.fish` gates on exactly that.
- **The board and the package** — `milestone --crs --packages --released-at` records the release
  (CR-CRU-129: a milestone is a record, not an event); CR-MDB-029 §S5 publishes the Pi package
  and smoke-installs it on a clean profile.

**Every dependency CR lands BEFORE the release starts.** Running a CR during a release is
possible and is **highly discouraged** — it puts unreviewed work on a branch whose only job is
to be verified and tagged. In particular §S2's zero-failure gate depends on CR-MDB-021 having
already retired the six chezmoi gates: if 021 has not landed when the release is proposed, the
release waits. Taking the exception at all requires explicit approval and a recorded reason; it
is never the plan.

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
- [ ] **§S5: the release followed the `git-workflow` skill** — the `1.0.0` tag exists, `master`
      carries only the merge, and the built artifact reports `1.0.0`. HOW that is achieved is the
      skill's to say; this CR gates only that it was.
- [ ] §S5: the released submodule pointer is committed and pushed at the Roundhouse root, and
      `fish scripts/stack-doctor.fish --section submodules` reports HEALTHY.
- [ ] §S5: the second remote is either pushed or its omission is recorded in the release notes.
- [ ] §S5: **no CR was executed during the release** — or, if one was, the exception carries an
      explicit approval and a recorded reason. Every dependency, CR-MDB-021 included, landed on
      `develop` before the release started.
- [ ] The board records the release via `milestone --crs --packages --released-at`.
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
