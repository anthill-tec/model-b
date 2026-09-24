# CR-MDB-023 — Adopt the `code-health` skill as a published Model B bundle, detached from the local machine and current with the Crucible board

**Status:** PENDING (filed 2026-08-27; amended 2026-09-21; rewritten at its gap-analysis 2026-09-24 —
earlier text is git history and is not to be consulted for contracts)
**Type:** feature
**Priority:** P1 — in release 1.0.0, wave 2. A skill that calls itself the Model B toolset is
unpublished, names local-machine paths, and teaches a ledger mechanism that no longer runs.
**Depends on:** CR-MDB-022 (adopted the `rust-*` tools; store `~/.agents/scripts/`), CR-MDB-028
(retired the ChangeSet DB path), CR-MDB-036 (stack-scoped bundle deploy)
**Labels:** skills, tooling, detachment, installer, feature
**Design reference:** user directive 2026-08-27 (adopt `code-health`; detach from the local machine) ·
`audits/2026-07-20-crucible-drift.md:14-15`, `:31` · `modelb_axi/deploy.py`
`TOOL_SCRIPTS_STORE_RELDIR` and `_skill_bundles` (CR-MDB-036 §S7) · DN §D18 (skills name capabilities
and CLIs, not harness tools) · project memory `repo-local-authoring-rule`

## Context — measured 2026-09-24 on `develop` at `415a9e7`

- **The only source** is the deployed, 106-line `~/.claude/skills/code-health/SKILL.md` (July). It is
  Model B workflow by content: Mainline-only snapshots at defined points (baseline, PRE/POST of each
  cull slice, wave boundaries, ad hoc), a report template, and maintenance-CR ratification.
- **Local paths.** Every invocation is `python3 ~/.claude/scripts/…`. The tools ship to
  `~/.agents/scripts/` (`deploy.TOOL_SCRIPTS_STORE_RELDIR`, CR-MDB-022).
- **The ledger no longer mirrors itself.** The skill says filing is "normally AUTOMATIC via
  worktree-flow" (`worktree-flow.py cs --type maintenance --findings …`) and that
  "`schedule_db.set_state` auto-mirrors IN_PROGRESS/COMPLETED/ABORTED". CR-MDB-028 removed `cs` and
  `worktree-flow`'s DB half: nothing calls `set_state` any more (measured: no caller outside
  `schedule_db.py`), and `rust-code-health.py ledger sync` without `--slice/--db-state` prints
  "no ChangeSet DB / schedule_db — full sync skipped" on a project without the legacy DB. The tool's
  explicit forms still work: `ledger assign --slice <CR> --ids …` and
  `ledger sync --slice <CR> --db-state {IN_PROGRESS|COMPLETED|ABORTED|SUPERSEDED} [--commit <sha>]`.
- **Recorded drift.** `rust-dead-scan.py`'s modes are
  `inventory pub-scan deps reconcile boundaries hot-path lift-lint`; the skill omits `hot-path`.
  The ledger is multi-domain (`--domain cull|temporal|<name>`); the skill treats it as cull-only.
- **The board.** Filing a CR is `cr-plan` on the project's Crucible client. `code-health` works on
  Cargo workspaces, so the client is `rust-crucible.py` (measured: it carries `cr-plan` and
  `cr-close`), at the path Crucible's manifest names.
- **Bundle accounting.** `skills-src/` holds 13 bundles: 7 Model B-owned (`model-b`, `crucible`,
  `cr-authoring`, `git-workflow`, `chezmoi`, `bootstrap`, `shutdown`) and 6 imported from Crucible
  (`crucible-register`, `crucible-report-{arduino,bun,java,python,rust}`, after CR-MDB-024 retired the
  editor bundle). `AGENTS.md`'s inventory row is right, but its Important Files entry still says
  "the 7 imported bundles". `tests/test_installer_assets.py` names the Model B-owned set
  `ALL_SEVEN_BUNDLE_NAMES`. Adding `code-health` makes 14 bundles, 8 Model B-owned.
- **Deploy scoping.** Since CR-MDB-036 the installer deploys `crucible-report-<stack>` only for
  selected stacks. `code-health` drives Rust-only tools, so it belongs to the same rule.

## Scope

### §S1 — Author the bundle in the repo
`skills-src/code-health/SKILL.md`, adopted from the deployed copy (read it; do not reconstruct it),
with frontmatter `name: code-health` and the trigger-bearing description, including the
Mainline-only restriction and the snapshot points. No write under `~/.claude`, no `chezmoi` command.

### §S2 — Detach every invocation
Every tool invocation names `~/.agents/scripts/<tool>`. No `~/.claude/` path remains. Crucible
clients are named as `rust-crucible.py` at the path in Crucible's client manifest
(`~/.crucible/clients/` by default), never a Crucible source checkout.

### §S3 — Teach the ledger as it now works
- **Filing a maintenance CR** is two explicit steps: `rust-crucible.py cr-plan …` files the CR, then
  `rust-code-health.py ledger assign --slice <CR> --ids F-…,DS-…` stamps its findings.
- **Transitions are mirrored by hand** at each board transition: `ledger sync --slice <CR>
  --db-state IN_PROGRESS` when the CR's first cycle activates, and `--db-state COMPLETED --commit
  <merge sha>` after `cr-close` (`ABORTED`/`SUPERSEDED` likewise). The skill no longer says the ledger
  mirrors automatically, and states that the no-argument full sync only works where a legacy
  ChangeSet DB exists.
- **Ratification** runs after the COMPLETED sync: `snapshot --phase post --slice <CR>` then
  `health_delta.md`, with the RATIFIED / NOT-RATIFIED / MANUAL verdicts and "any NOT-RATIFIED blocks
  sign-off" unchanged.
- **The recorded drift:** the `rust-dead-scan.py` mode list includes `hot-path`; the ledger is
  documented as multi-domain (`--domain cull|temporal|<name>`), and no sentence calls it cull-only.
- **No `worktree-flow.py cs`, no `schedule_db` instruction, no claim that Crucible's scheduling is
  unreleased.**

### §S4 — Ship it, scoped to Rust
The bundle joins the installer's asset set (store, per-harness symlinks, sha256 manifest), and is
deployed when `rust` is among the selected stacks or no stack filter is given — the CR-MDB-036 §S7
rule the `crucible-report-*` bundles follow. The wheel carries it.
`tests/test_installer_assets.py`'s Model B-owned set includes `code-health` under a name that carries
no size. `AGENTS.md` states 14 bundles, lists `code-health` as Model B-owned, and says 6 imported
bundles wherever it counts them.

## Acceptance criteria

### §S1
- [ ] `skills-src/code-health/SKILL.md` exists with `name: code-health` and a description carrying
      the Mainline-only restriction and the snapshot points.
- [ ] The adopted text keeps the deployed copy's substance section by section: ownership and
      snapshot points, the snapshot and query verbs, the dataset description, the procedure, the
      report template, ratification, and the caveats.
- [ ] Nothing in this CR writes under `~/.claude` or runs `chezmoi`.

### §S2
- [ ] Zero `~/.claude/` occurrences in the bundle; every `rust-*` invocation names
      `~/.agents/scripts/`, asserted against `deploy.TOOL_SCRIPTS_STORE_RELDIR`, not a literal.
- [ ] No path to a Crucible source checkout (`data_projects`) in the bundle.

### §S3
- [ ] The filing step shows `cr-plan` on `rust-crucible.py` followed by `ledger assign --slice
      … --ids …`.
- [ ] The bundle shows `ledger sync --slice … --db-state IN_PROGRESS` and `--db-state COMPLETED`
      with `--commit`, tied to cycle activation and `cr-close`; it contains no "AUTOMATIC" /
      "auto-mirror" claim about the ledger.
- [ ] Ratification follows the COMPLETED sync, and the three verdicts and the NOT-RATIFIED block are
      stated.
- [ ] The `rust-dead-scan.py` mode list names all seven modes including `hot-path`, checked against
      the tool's own `--help`.
- [ ] `--domain` with `cull` and `temporal` is documented; no sentence describes the ledger as
      cull-only.
- [ ] Zero occurrences of `worktree-flow.py cs`, `set_state`, or `schedule_db` as an instruction;
      no statement that Crucible's scheduling is unreleased. Across `skills-src/` and `scripts/`,
      `worktree-flow.py cs` appears nowhere as an instruction.
- [ ] The bundle names no harness tool (DN §D18).

### §S4
- [ ] A sandboxed install with `--stacks rust` (and one with no stack filter) deploys `code-health`
      to the store with its per-harness link; a second run reports it unchanged; `--stacks python`
      does not deploy it.
- [ ] The built wheel contains `modelb_axi/_assets/skills-src/code-health/SKILL.md`, asserted against
      a built artifact.
- [ ] `tests/test_installer_assets.py`'s Model B-owned set includes `code-health`; no constant name
      carries a bundle count, and no test asserts 7 Model B-owned bundles.
- [ ] `AGENTS.md` states 14 bundles, lists `code-health` as Model B-owned, and counts 6 imported
      bundles.

## Risk

- The deployed copy is the only source: adopt from it. Once adopted, the repo copy is authoritative.
- The skill is Mainline-only; adoption must not soften that — a track taking a snapshot corrupts the
  ratification record.
- Manual ledger syncs can be forgotten. Tying each to a named board event (cycle activation,
  `cr-close`) is the mitigation; automating it is out of scope.

## Non-goals

- No change to the `rust-*` tools or `schedule_db.py` (its retirement is separate). The stale
  "mirrors via `schedule_db.set_state`" sentence in `rust-code-health.py`'s docstring is noted in the
  queue, not fixed here.
- No `chezmoi` operation and no deletion of the local copy.
- No new `code-health` capability, snapshot phase, or change to the ratification substance.
- No adoption of other local skills (`status-report`, `stay-within-limits`).
