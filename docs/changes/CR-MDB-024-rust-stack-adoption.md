# CR-MDB-024 — Rust as a fifth generated stack, and retire the vscode agents

**Status:** PENDING
**Type:** feature
**Priority:** P1 — an unowned, undrift-gated agent-definition set is the failure class CR-CRU-042
exists to prevent, and it is live today.
**Depends on:** CR-MDB-017 (the `tier_guidance` key and the shared/per-stack template split — shipped)
**Labels:** generator, rust, vscode, ownership, feature
**Phase:** Wave 5 (repo queue) · release 1.0.0 wave 2 (Crucible board)
**Design reference:** Sandesh #1362–#1367 · Crucible's CR-CRU-042 as quoted over Sandesh #1367
("Model B now owns the skills component in FULL — content, bundling AND deploy") · PRD D10.8 and
DN §D17 (agents are rendered per project from `generator/`) · PRD, installer-orchestration
boundary (Model B runs Crucible's RELEASED client, `~/.crucible/clients/`) · DN §D18 (shared
assets name capabilities and CLIs) · `skills-src/memory-templates/rust-orchestration.md` ·
`generator/stacks/quarkus.toml` (the shape followed)

## Context

The four rust agent definitions are hand-maintained and rendered by nothing. They live today in
Pi's global scope, `~/.pi/agent/agents/rust-{red,green,verify,fix}-agent.md` (2535 lines; the
copies formerly in `~/.agents/agents/` were removed 2026-09-23, backup in `~/.cache/`).
`generator/stacks/` has four stacks — `arduino`, `bun`, `python`, `quarkus` — and no `rust.toml`.
Model B already supports rust elsewhere: CR-MDB-022 adopted the three `rust-*` tool scripts, and
`skills-src/memory-templates/rust-orchestration.md` documents rust orchestration. Only the
generated agent layer is missing.

Ownership is settled on both sides (CR-CRU-042: Model B owns the skills component in full;
Crucible does not patch Model B's copies). The released rust client exists at
`~/.crucible/clients/rust-crucible.py`, and its `register` takes `--role` and `--cycle`.

The four `vscode-*` definitions were a category error: VS Code is an editor, not a stack (user
ruling 2026-09-22). A VS Code extension is TypeScript tested with vitest/mocha — the bun stack. The
live copies were deleted 2026-09-22; the repo still carries their substrate.

## Scope

### §S1 — `generator/stacks/rust.toml`
In the shape `quarkus.toml` establishes: `display_name`, `test_command`, `register_command`,
`unregister_command`, `crucible_reference`, `mechanics`, `tier_guidance`, and `[description]`,
`[frontmatter]` and `[gotchas]` for all four roles. `[frontmatter]` follows the other four stacks'
current shape; CR-MDB-025 §S1 restructures all five together.

- **Client.** Every client invocation names the released client
  `~/.crucible/clients/rust-crucible.py`; `register` carries `--agent`, `--role` and `--cycle`, the
  agent id and cycle coming from the dispatch prompt. `crucible_reference` names
  `~/.agents/skills/crucible/references/rust.md`. (The other four stacks still name
  `~/.claude/scripts/`; CR-MDB-020 moves them. This stack is not authored stale.)
- **Tier guidance.** Cargo's own split is the tier boundary: `#[cfg(test)]` modules / `--lib` are
  unit; `tests/*.rs` targets / `--test <name>` are integration; `smoke-test --profile e2e` and
  `docker-e2e-gate` report `e2e`; the default `smoke-test` under `-P ci` reports `integration`;
  `workspace-regression` is the union (Crucible CR-CRU-111, via #1367).
- **Mechanics and gotchas** are reconciled from the live rust definitions and
  `rust-orchestration.md`. Where they disagree, the memory template wins — except where it carries
  something a PRD/DN rule has since retired (a `~/.claude` path, a Crucible development checkout,
  `--phase`); those are never imported.

### §S2 — Generate the four, and account for every section of the old ones
`generator/build.py build` renders `generator/agents/rust-{red,green,verify,fix}-agent.md`, and
`--check` covers all 20. The generated files are reference output: agents reach a project by
per-project rendering (CR-MDB-025 §S4), not by deployment from this CR.

The old definitions are not copied — they are triaged **by section**: every heading in the four
live rust definitions lands in exactly one bucket — reproduced by the shared template, carried in
`rust.toml`, or dropped with a stated reason. The triage table is filed in the GREEN commit
message.

### §S3 — Retire the vscode agents: an IDE is not a stack
- `skills-src/crucible-report-vscode/` is deleted; `skills-src/CRUCIBLE-HANDOVER.md`'s imported
  roster drops from 7 to 6, and the handover gates move with it.
- `skills-src/crucible/references/vscode.md` and the vscode rows of `skills-src/crucible/SKILL.md`
  are deleted.
- `generator/build.py`'s bespoke list and docstring lose `rust ×4` and `vscode ×4`: bespoke becomes
  electronics ×4 and `inbox-analyst`.
- `modelb_axi/scaffold.py` and `modelb_axi/cli.py` drop `vscode` from the selectable stacks.
- `tests/test_client_role_contract.py`'s `API_PATH_BUNDLES = ("crucible-report-vscode",)` exemption
  and the gate asserting it are deleted — an exemption whose only member is gone.
- `AGENTS.md`'s `crucible-report-*` enumeration and bundle count are corrected.
- DN §D4 ("VS Code is owned as an editor overlay … generated from the bun/TypeScript stack") is
  marked superseded by the 2026-09-22 ruling.

### §S4 — Records
PRD §D6's bespoke enumeration, `docs/research/DN-rationalization-plan-review.md`'s "rust agents are
never generated" are corrected to cite the 2026-09-16 rust ruling and the 2026-09-22 vscode
ruling. CR-MDB-008 is a closed spec and is not edited (PRD D9; `ClosedCrSpecsUntouchedTest`): its
exclusion list is superseded by `generator/build.py`'s bespoke list, which this CR corrects. PRD §4.4's counts are left to CR-MDB-035, which owns
§4. The queue footer records the vscode retirement and its reason, so the category error is not
re-made by a future reader who sees TypeScript extension work.

### §S5 — Tell Crucible
After §S1–§S3 are merged, confirm to Crucible on the #1362–#1367 thread that Model B owns the rust
stack (their #1367: "tell me and I will treat those four as yours"), and that vscode is retired on
Model B's side (they own `crucible-report-vscode`'s origin; #1369 recorded that
`vscode-crucible.py` never shipped). Sandesh refuses an inactive recipient: if `Mainline - Crucible`
is inactive, the message is appended to `docs/research/CREQ-crucible-queue-projection.md` as a
pending outbound item and sent the next time they are listening.

## Acceptance criteria

### §S1
- [ ] `generator/stacks/rust.toml` exists with every key and per-role table `quarkus.toml` has,
      including `tier_guidance`.
- [ ] Every client invocation in `rust.toml` names `~/.crucible/clients/rust-crucible.py`; every
      `register` example carries `--role`, and for the four TDD roles `--cycle`; zero `--phase`,
      zero `~/.claude`, zero `data_projects` anywhere in `rust.toml`.
- [ ] `tier_guidance` states Cargo's unit/integration split and the `smoke-test`/`docker-e2e-gate`
      mapping of §S1.
- [ ] No statement in the rendered rust definitions contradicts `rust-orchestration.md`, except
      where §S1 names the retired item it declines to import.

### §S2
- [ ] `python3 generator/build.py --list` names 20 targets (16 + 4 rust).
- [ ] `python3 generator/build.py --check` exits 0 across all 20.
- [ ] Every `generator/agents/rust-*.md` line arrives via `build.py build` (the `--check` drift gate
      proves it).
- [ ] The GREEN commit message carries the section triage: every heading of the four live rust
      definitions, each in exactly one bucket, with a reason for each drop.

### §S3
- [ ] Zero `vscode` references under `skills-src/`, `generator/`, `modelb_axi/` and `tests/`
      (compiled caches excluded) — grep gate.
- [ ] `skills-src/` carries 13 bundles (7 Model B-owned + 6 imported; it carried 14 before this CR)
      and `CRUCIBLE-HANDOVER.md` documents 6 imported ones; the
      handover gates assert the new counts rather than being deleted.
- [ ] The bespoke list names only definitions that still exist: electronics ×4 and `inbox-analyst`.
- [ ] `modelb-axi init --stacks vscode` is rejected with a message naming the supported stacks.
- [ ] DN §D4 carries a superseded marker citing the 2026-09-22 ruling.
- [ ] The existing tests affected by §S1–§S3 — both those asserting the old census (four stacks,
      16 generated, 13 bespoke, vscode bundles) and those depending on vscode or on the bespoke
      rust set without naming the count — are migrated to this contract and listed by id in the
      RED report.

### §S4
- [ ] PRD §D6 and `DN-rationalization-plan-review.md` no longer state
      rust agents are never generated or that vscode agents exist, and cite the two rulings.
- [ ] The queue footer records the vscode retirement and its reason.

### §S5
- [ ] After merge, the confirmation is sent on the #1362–#1367 thread, or — if `Mainline -
      Crucible` is inactive — recorded as a pending outbound item in
      `docs/research/CREQ-crucible-queue-projection.md`.

## Estimated size

One new stack TOML (~150 lines), four generated definitions, the vscode substrate removed across
`skills-src/`, `generator/build.py`, `modelb_axi/scaffold.py`, `modelb_axi/cli.py` and `AGENTS.md`,
test census migrations, and record corrections. Small–medium.

## Risk

- **Reconciliation, not verbatim adoption.** Crucible's fragment was validated in their dogfood
  context; mechanics and gotchas are checked against `rust-orchestration.md` rather than pasted.
- The live rust definitions in `~/.pi/agent/agents/` stay in place (Pi's global scope is legacy but
  still read by other projects, DN §D17); a project gets the generated ones when it renders.

## Non-goals

- No change to the other four stacks' content, and no restructure of any `[frontmatter]` — CR-MDB-025.
- No re-anchoring of the other four stacks' client paths — CR-MDB-020.
- No deployment of agent definitions by the installer (DN §D17).
- Nothing under `~/.claude` is written, deleted or asserted.
- Electronics ×4 and `inbox-analyst` are untouched.
