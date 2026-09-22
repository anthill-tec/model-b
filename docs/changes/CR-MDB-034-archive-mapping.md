# CR-MDB-034 — `archive/mapping.md`: where every relocated file went

**Status:** PENDING
**Type:** maintenance
**Priority:** P2 — wanted before 1.0.0 ships because the archive is largest at a release boundary,
but it gates nothing. **This CR does not gate the release** (user ruling 2026-09-21: a release is
a boundary event, not a work item — see `skills-src/cr-authoring/SKILL.md` §queue and
`skills-src/git-workflow/SKILL.md` §Releases).
**Supersedes:** CR-MDB-012 — the "Release 1.0.0" CR, whose only genuine deliverable this is. The
rest of 012 was release *procedure* (which belongs to the `git-workflow` skill, loaded at release
time) and release *gating* (which belongs to nobody — the wave draining plus a human's approval
is the trigger).
**Depends on:** — (it maps whatever has moved by the time it runs; the later it runs the more it
covers, which is why it sits late in the wave, not because anything blocks it)
**Labels:** archive, docs, maintenance
**Phase:** Wave 5 (repo queue, historical) · release 1.0.0 wave 2 (Crucible board)
**Design reference:** `archive/BASELINE.md` (the wave-1 baseline record) · `archive/wave1..3/`
(the relocation history) · PRD §4 (the verification criteria that expect a findable archive)

## Context

Waves 1–5 moved a great deal: a 621-line `AGENTS.md` split into a frugal core plus skill
references (CR-MDB-001), the memory corpus rehomed from global to project scope (006), the
generator's output retargeted (008/014), seven skill bundles imported and eight tool scripts
adopted (016/022), and — most recently — five Java language references moved out of the user's
global memory into `skills-src/memory-templates/` under the PRD §D5 amendment.

`archive/` holds the history, but there is **no index from an old path to where its content now
lives**. A reader who finds a reference to a file that no longer exists — in a closed CR, an old
audit, a commit message, or another project — has to reconstruct the move from git history.
`archive/BASELINE.md` records the starting state; nothing records the mapping.

This is the one piece of the retired CR-MDB-012 that is actual work rather than procedure, so it
is filed as what it is: a documentation deliverable with a name that says what it builds.

## Scope

### §S1 — The map
`archive/mapping.md`: for every path that moved or was deleted across waves 1–5, the old path,
the new path (or "deleted, content absorbed into X"), and the CR that moved it. Derived from
`archive/wave1..3/`, the queue's dated footer record, and git history — not from memory.

### §S2 — Entries that have no new path
A file that was deleted without a successor says so explicitly, with the CR and the reason. An
entry that reads "gone" is more useful than a missing entry, which is indistinguishable from an
oversight.

### §S3 — The cross-project cases
Paths that left this repo entirely — the Crucible-origin bundles (CR-MDB-016), the retired
`~/.claude/scripts` mirrors (022), the `~/.claude/agents` set that DN §D14 made unowned legacy —
are recorded with where authority now sits, not just where bytes went. A reader following an old
`~/.claude/scripts/python-crucible.py` reference needs to learn that Crucible owns it and it
installs to `~/.crucible/clients/`, not merely that Model B stopped shipping it.

## Acceptance criteria

- [ ] `archive/mapping.md` exists and every `old → new` entry's new path resolves in the tree
      (or is explicitly marked deleted/absorbed with its CR).
- [ ] Every relocation recorded in the queue's dated footer for waves 1–5 appears in the map.
- [ ] Deleted-without-successor entries are present and labelled, not omitted.
- [ ] The three cross-project cases (§S3) name where authority sits, not only where files went.
- [ ] No entry is derived from memory — each cites its CR or the commit that moved it.
- [ ] The suite is unchanged by this CR (documentation only; no gate reads `archive/mapping.md`).

## Estimated size

One document, derived. No code, no tests, no board mechanics.

## Risk

- **It is a snapshot.** A map written at wave 5 describes wave 5; later moves will not add
  themselves. Say so in the document's own header, so a future reader knows its horizon.

## Non-goals

- No re-organisation of `archive/` — this describes the moves, it does not make new ones.
- No release gating. Nothing waits on this CR.
