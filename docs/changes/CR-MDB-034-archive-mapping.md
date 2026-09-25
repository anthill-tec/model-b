# CR-MDB-034 — `archive/mapping.md`: a living map of where every relocated path went

**Status:** PENDING
**Type:** maintenance
**Priority:** P2 — wanted before 1.0.0 ships because the archive is largest at a release boundary,
but it gates nothing. **This CR does not gate the release** (user ruling 2026-09-21: a release is
a boundary event, not a work item — see `skills-src/cr-authoring/SKILL.md` §queue and
`skills-src/git-workflow/SKILL.md` §Releases).
**Supersedes:** CR-MDB-012 (voided) — the "Release 1.0.0" CR, whose only genuine deliverable this
is.
**Depends on:** —
**Labels:** archive, docs, maintenance
**Phase:** Wave 5 (repo queue, historical) · release 1.0.0 wave 2 (Crucible board)
**Design reference:** `archive/BASELINE.md` (the wave-0 baseline) · `archive/wave1..3/` and
`archive/contracts/` (what was archived) · `audits/2026-07-20-*.md` (the starting inventory) · the
CR specs in `docs/changes/` and the queue's dated footer notes (what moved, and why)

## Context

Since the 2026-07-20 baseline (24 memory files, ~50 skills, 29 agents, ~20 scripts, a 621-line
`~/.claude/AGENTS.md`) almost everything Model B owns has moved: into skill bundles (CR-MDB-002 to
-006), into the agent generator (-008, -024), into `skills-src/` from Crucible (-016), into
`scripts/` from `~/.claude/scripts/` (-022, -023), into Crucible's API (-028), into per-project
rendering (-025), into `skills-src/memory-templates/` (the PRD D5 amendment of 2026-09-21), and out
of the Claude Code era altogether (-031: the `chezmoi` bundle, the `.claude/skills` links,
`CLAUDE.md` emission, the run-context wrapper, `contracts/mail-axi.md`, `.claude/worktrees/`).

There is no index from an old path to where its content now lives. A reader who meets a path that
no longer exists — in a closed CR, an audit, a commit message or another project — has to rebuild
the move from git history.

The map is **living** (user ruling 2026-09-25): a test gates it, so a later CR that moves a mapped
path must update its row, and the map never silently rots.

## Scope

### §S1 — The map
`archive/mapping.md` holds one Markdown table with the columns
`| Old path | Kind | Now | Authority | Moved by |`:

- **Old path** — the path as it was written at the time (`~/.claude/…`, a repo path, or a pattern
  such as `~/.claude/skills/crucible-report-<stack>/`), in backticks.
- **Kind** — exactly one of `moved`, `absorbed`, `deleted`, `external`:
  - `moved` — the content lives on at **Now**, a path in this repo.
  - `absorbed` — the content was merged into **Now**, a path in this repo.
  - `deleted` — no successor; **Now** is `—` and **Authority** states the reason.
  - `external` — authority left Model B; **Now** is where it installs or lives (e.g.
    `~/.crucible/clients/`) and **Authority** names the owner (Crucible, Sandesh, the user).
- **Now** — for `moved`/`absorbed`, a repo-relative path (optionally with `#anchor`).
- **Authority** — who owns the content now (`Model B`, `Crucible`, `Sandesh`, `the user`), plus
  the deployed location where one exists (e.g. `Model B; deployed to ~/.agents/skills/`).
- **Moved by** — the CR id (`CR-MDB-NNN`) or a short commit sha that moved it.

The entries cover every relocation made by CR-MDB-001 to CR-MDB-035, derived from the CR specs,
the queue's dated footer notes, `archive/`, the 2026-07-20 audits and git history — never from
memory. A pattern row may stand for a family (e.g. the five `crucible-report-*` skills) when every
member went to the same place by the same CR. The document's header states that the map is gated
by `tests/test_archive_mapping.py` and must be updated by any CR that moves a mapped path.

### §S2 — Entries that have no new path
A path deleted without a successor has a `deleted` row with its CR and reason. A "gone" row is
more useful than a missing one, which is indistinguishable from an oversight.

### §S3 — The cross-project cases
Paths whose authority left this repo are `external` rows naming the owner, not just where bytes
went. At minimum: the Crucible clients and their bundled skill docs (`~/.claude/scripts/*crucible*`
→ Crucible, installed at `~/.crucible/clients/`; CR-MDB-016, -020, -032); the scheduling half of
`worktree-flow.py` (→ Crucible's plan/queue API; CR-MDB-028); the chezmoi discipline (→ the user;
CR-MDB-021, -031); and the `~/.claude/agents/` set (→ Model B renders per project into
`.pi/agents/`, the rest is the user's; CR-MDB-025, DN-multi-harness §D17).

### §S4 — The gate
`tests/test_archive_mapping.py` asserts:
- the table parses, each row has the five columns, and **Kind** is one of the four values;
- every `moved`/`absorbed` **Now** path (anchor stripped) exists in the repo;
- every **Moved by** is a `CR-MDB-NNN` whose spec exists in `docs/changes/` (or is CR-MDB-007,
  superseded with no spec) or a commit sha that `git cat-file -e` resolves;
- every `external` row's **Authority** names one of `Crucible`, `Sandesh`, `the user`;
- rows exist for these retired or moved paths, each asserted by old path: every archived file
  under `archive/wave1/`, `archive/wave2/`, `archive/wave3/` and `archive/contracts/` (a row whose
  Old path is its original location); `skills-src/chezmoi/`; `contracts/mail-axi.md`;
  `.claude/worktrees/<cr>`; `CLAUDE.md` (the emitted symlink); `~/.claude/AGENTS.md`;
  `~/.claude/scripts/worktree-flow.py`; and the five Java references under `~/.claude/memory/`;
- detector fixtures: a bad **Kind**, an unresolved **Now**, an unknown CR id, and a missing
  required row each fail.

`AGENTS.md` §Key Directories describes `archive/` as "`BASELINE.md` + `wave1..3/` historical
records"; it names `contracts/` and `mapping.md` too.

## Acceptance criteria

- [ ] `archive/mapping.md` exists with the §S1 table and a header naming its gate and the
      update-on-move rule.
- [ ] Every `moved`/`absorbed` row's **Now** resolves in the repo; every `deleted` row states a
      reason; every `external` row names its owner.
- [ ] Every row cites a CR with a spec in `docs/changes/` (or CR-MDB-007) or a resolvable commit.
- [ ] Every archived file under `archive/wave1..3/` and `archive/contracts/` has a row.
- [ ] Every relocation named in a CR-MDB-001..035 spec or in the queue's dated footer notes has a
      row (a family row may cover several).
- [ ] The four §S3 cross-project cases are `external` rows naming their owner.
- [ ] `tests/test_archive_mapping.py` implements §S4 with its detector fixtures, and fails before
      `archive/mapping.md` exists.
- [ ] `AGENTS.md`'s `archive/` row, module count and both suite baselines (real `HOME`, empty
      `HOME`) are updated and re-measured.

## Estimated size

One derived document, one gate module, one `AGENTS.md` row.

## Non-goals

- No re-organisation of `archive/` — this describes the moves, it does not make new ones.
- No edits to closed CR specs, `audits/` or existing `archive/` files.
- No release gating. Nothing waits on this CR.
