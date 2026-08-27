# CR-MDB-023 — Adopt the `code-health` skill as a published Model B bundle, detached from the local machine

**Status:** PENDING
**Type:** feature
**Priority:** P1 (blocks release 0.1.0 — a skill that calls itself the Model-B toolset is unpublished, hard-codes local-machine paths, and documents its tools wrongly)
**Depends on:** CR-MDB-022 (adopts the three `rust-*` tools this skill drives and establishes the deployed script path it must name)
**Labels:** skills, tooling, ownership, detachment, feature
**Phase:** Wave 5
**Design reference:** user directive 2026-08-27 ("`code-health` and `gate-lock`: adopt those skills") · user directive 2026-08-27 (detachment from the local development machine's environment; bundle with the skills we manage for release) · `audits/2026-07-20-crucible-drift.md:14-15`, `:31` (the recorded tool-vs-doc drift this CR closes) · CR-MDB-016 (the bundle-adoption + supersede pattern) · project memory `repo-local-authoring-rule`

## Context

`code-health` is a Model B workflow skill by its own text — it takes the snapshot at the
defined audit/PRE/POST/wave-boundary points, RATIFIES maintenance and cull CR completion, and
declares itself MAINLINE-only. Its tools section is titled, verbatim, "Tools (Model-B
toolset, `~/.claude/scripts/`)". Yet it is not one of Model B's published bundles: it exists
only in the user's skill tree on this machine (106 lines, chezmoi-tracked), so `skills-src/`
ships the orchestration lifecycle without the skill that performs one of its named duties.

**It is coupled to the local machine in the way the detachment directive forbids.** Every
invocation it teaches is an absolute path into `~/.claude/scripts/`:

- `:26` — `python3 ~/.claude/scripts/rust-code-health.py snapshot --phase {baseline|pre|post|adhoc} [--slice CR-XXX]`
- `:29-32` — the four `query` verbs (`trend`, `crate`, `delta`, `ledger`)
- `:41` — `python3 ~/.claude/scripts/rust-dead-scan.py inventory pub-scan deps reconcile boundaries --lift-lint`
- `:35` — `worktree-flow.py cs --cr … --type maintenance --findings …`
- `:38` — `rust-code-health.py ledger assign|sync`

CR-MDB-022 adopts those tools and establishes the deployed store path; this CR is what makes
the skill name it.

**Two documented defects come with it**, both already measured in
`audits/2026-07-20-crucible-drift.md` and left unfixed because the skill was outside the repo:

- `:15` and `:31` — `rust-dead-scan.py` implements a **`hot-path`** mode the skill's mode list
  omits, so a documented-complete list is incomplete and the mode is unreachable by anyone
  following the skill.
- `:31` — the ledger is treated as **cull-only** when the tool is multi-domain:
  `ledger assign|sync --domain {cull|temporal|<name>}` (`:14`). A maintenance domain that is
  not `cull` has no documented path.

**A third coupling must be recorded, not deepened.** The ChangeSet-filing step at `:35` runs
through `worktree-flow.py cs`, which is backed by `schedule_db.py` — the transitional
scheduling DB that Crucible supersedes when their **0.2.0** ships (unreleased; never to be
cited as available). This CR keeps that instruction working and adds nothing to it, so the
skill needs no rewrite when the storage moves.

**Bundle accounting is currently wrong in two places.** `skills-src/` holds **14** bundles
today — 7 Model B-owned (`model-b`, `crucible`, `cr-authoring`, `git-workflow`, `chezmoi`,
`bootstrap`, `shutdown`) and 7 Crucible-origin (`crucible-register` plus the six
`crucible-report-*`) — while `AGENTS.md` states "13 skill bundles". And the gate constant
`tests/test_installer_assets.py:94` is named `ALL_SEVEN_BUNDLE_NAMES` for the Model B-owned
set. Adding `code-health` makes 15 bundles and 8 Model B-owned, so the miscount and the
constant name both have to be corrected rather than incremented around.

## Scope

### §S1 — Author the bundle repo-local
`skills-src/code-health/SKILL.md`, adopted from the deployed 106-line copy, authored in the
repo per the standing repo-local rule — no `~/.claude` write anywhere in this CR. Frontmatter
`name: code-health` with the trigger-bearing description preserved, including the
MAINLINE-only restriction and the snapshot points.

### §S2 — Detach every tool invocation
Every `~/.claude/scripts/` path becomes the deployed store path CR-MDB-022 establishes, so a
session on any machine resolves the tools the installer placed. Zero absolute paths into a
developer's home remain.

### §S3 — Close the recorded drift
- The `rust-dead-scan.py` mode list includes **`hot-path`**, matching the tool's real mode set.
- The ledger is documented as multi-domain — `--domain {cull|temporal|<name>}` — and the
  cull-only phrasing is corrected wherever it appears.
- The board-reading note CR-MDB-010 called for: `worktree-flow` stdout is a TOON envelope and
  the human board is on stderr.

### §S4 — Ship it
The bundle joins the installer's asset set and deploys with the same sha256 manifest
discipline, store path and per-harness symlinks as the other bundles.
`tests/test_installer_assets.py`'s enumeration is extended, and the misnamed
`ALL_SEVEN_BUNDLE_NAMES` constant is renamed to reflect a set whose size is no longer seven.
`AGENTS.md`'s bundle inventory is corrected to the true count and lists `code-health` among
the Model B-owned bundles.

### §S5 — Record the transitional coupling
The ChangeSet-filing step states that it rides the transitional scheduling DB and that
Crucible assumes workflow plan/state storage at their 0.2.0, so the successor path is written
down where the next reader will look. No new coupling to `schedule_db.py` is introduced.

## Acceptance criteria

### §S1
- [ ] `skills-src/code-health/SKILL.md` exists with frontmatter `name: code-health` and a
      description carrying the MAINLINE-only restriction and the snapshot points.
- [ ] No file added or edited by this CR writes under `~/.claude`, and no `chezmoi` command is
      run.
- [ ] The adopted content preserves the deployed copy's substantive guidance — the snapshot
      phases, the query verbs, the ratification procedure — verified section by section, not
      by line count.

### §S2
- [ ] Zero occurrences of `~/.claude/scripts/` in `skills-src/code-health/SKILL.md`.
- [ ] Every tool invocation names the deployed store path, and that path string matches the
      one `deploy.py` writes — asserted against the deploy target, not by eyeballing both.

### §S3
- [ ] The `rust-dead-scan.py` mode list contains `hot-path`.
- [ ] The ledger is documented with `--domain` and at least the `cull` and `temporal` domains;
      no sentence describes the ledger as cull-only.
- [ ] The skill states that `worktree-flow` stdout is a TOON envelope and the human board is
      on stderr.

### §S4
- [ ] `code-health` deploys to the skill store with a per-harness symlink, idempotently — a
      second run reports it unchanged.
- [ ] `tests/test_installer_assets.py` enumerates `code-health`; the constant formerly named
      `ALL_SEVEN_BUNDLE_NAMES` no longer carries a size in its name, and no test asserts a
      Model B-owned bundle count of 7.
- [ ] `AGENTS.md` states the true bundle count and lists `code-health` as Model B-owned.
- [ ] The built wheel contains `modelb_axi/_assets/skills-src/code-health/SKILL.md` —
      asserted against a built artifact.

### §S5
- [ ] The ChangeSet-filing section names the transitional scheduling DB and Crucible's 0.2.0
      as its successor, and no Model B document presents that release as shipped.
- [ ] `grep` finds no new `schedule_db` invocation introduced by this CR beyond the existing
      `worktree-flow.py cs` instruction.

## Estimated size

1 new bundle (~110 lines), 1 asset-enumeration test extended plus one constant renamed,
`AGENTS.md` inventory corrected. No `modelb_axi/` logic change beyond the asset list.

## Risk

- **The deployed copy is the only source.** It exists on one machine and is chezmoi-tracked;
  read it before editing and adopt from it, rather than reconstructing from the description in
  this CR. Once adopted, the repo copy is authoritative and the local one is legacy.
- **Renaming `ALL_SEVEN_BUNDLE_NAMES` touches gates that other CRs also read.** Keep the
  rename mechanical and in one commit so a bisect never sees a half-renamed constant.
- **Do not deepen the `schedule_db` coupling** while documenting it — the storage moves to
  Crucible at their 0.2.0 and anything built on the interim shape is written off.
- The skill is MAINLINE-only by declaration. Adoption must not soften that into general
  availability; a track running a snapshot would corrupt the ratification record.

## Non-goals

- No change to the three `rust-*` tools themselves — CR-MDB-022 adopts them; this CR documents
  them correctly.
- No `chezmoi` operation and no deletion of the local copy.
- No new `code-health` capability, no new snapshot phase, and no change to the ratification
  procedure's substance.
- No adoption of `status-report` or `stay-within-limits`, which are also orchestration-adjacent
  skills outside `skills-src/` — they are neither named by this directive nor consumers of the
  adopted tooling.
