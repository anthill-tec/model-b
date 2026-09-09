# CR-MDB-024 — Rust as a fifth generated stack: close the orphaned-artifact gap CR-CRU-042 already assigned to us

**Status:** PENDING
**Type:** feature
**Priority:** P1 (an unowned, undrift-gated agent-definition set is exactly the failure class CR-CRU-042 exists to prevent, and it is live today — all four files still carry the retired `--phase` flag)
**Depends on:** CR-MDB-017 (introduces the `tier_guidance` TOML key and the shared/per-stack template split this CR's rust fragment renders through)
**Labels:** generator, rust, ownership, feature
**Phase:** Wave 5
**Design reference:** Sandesh #1362–#1367 (the correspondence that surfaced this) · `crucible:docs/changes/CR-CRU-042-exit-skills-ownership.md` (the ownership handover: "Model B now owns the skills component in FULL — content, bundling AND deploy... Crucible does not patch either in place") · `skills-src/memory-templates/rust-orchestration.md` (existing rust footprint in this repo) · `generator/stacks/quarkus.toml` (the shape this CR follows)

## Context

Four files — `~/.claude/agents/rust-{red,green,verify,fix}-agent.md` — exist on every machine
that installs Model B's harness bundle, are hand-maintained plain files, and are rendered by
**neither** generator: `generator/stacks/` in this repo has exactly four stacks (`arduino`,
`bun`, `python`, `quarkus`), no `rust.toml`; Crucible's own dogfood copies live in a separate
tree they own (`~/.omp/agent/agents/`) and are explicitly not these files.

**This is not new territory for Model B — the footprint already exists.** CR-MDB-022 adopted
all three `rust-*` tools (`rust-code-health.py`, `rust-crate-map.py`, `rust-dead-scan.py`) into
`scripts/`, and `skills-src/memory-templates/rust-orchestration.md` already documents rust
orchestration mechanics in this repo. What is missing is only the generated agent-definition
layer that the other four stacks already have. Adding it completes a stack Model B partially
supports, rather than adopting one from nothing.

**The ownership question is already settled, in writing, on both sides.** Crucible's
CR-CRU-042 (merged `8d3e113`, 2026-07-28) records the handover verbatim:
*"CR-CRU-035's boundary: Model-B owns hook creation, per-project deploy and skill
generation... widened 2026-07-28: Model B now owns the skills component in FULL — content,
bundling AND deploy. User-ratified on both sides."* Its own Non-goals state
*"Crucible does not patch either [`~/.claude/skills/crucible` or `~/.claude/scripts/`] in
place."* CR-CRU-042's Context names the exact failure mode this CR closes: the deployed
`~/.claude/skills/crucible` once carried 12 stale `WORKFLOW_CYCLE_ID` references after
CR-CRU-036 removed the flag, "instructing them to hand-pass a variable the server no longer
accepts — the orphaned-run failure mode," because **"Nobody owned the deployed copy."** The
four rust definitions are that sentence again, with `--phase` in place of `WORKFLOW_CYCLE_ID`
— independently verified, 2026-09-09: `--phase` occurs once in each of the four deployed files
(4 total), matching Crucible's own count before their fix touched their separate tree.

**Crucible's content is battle-tested, not proposed.** They dispatched eleven cycles of their
own CR-CRU-111/112 against these agent-definition patterns this wave and found the defects by
use: `--phase` fails at argparse before reaching the server (a hard stop, not documentation
drift), and an earlier generic tier-guidance block was wrong for four of six stacks once real
agents read it to make a real choice. The fragment they sent for rust is the same content that
ran clean across their fleet.

**Scope boundary, stated because it was checked, not assumed.** This CR adds ONE stack to an
existing, working generator — it does not change the generator's shape, does not add a new
mechanism, and does not touch the other four stacks' content (their `tier_guidance` split is
CR-MDB-017's work; this CR consumes that key, it does not invent it). Sequencing: CR-017 lands
the `tier_guidance` key and the shared/per-stack template split; this CR populates a fifth
`generator/stacks/rust.toml` using it.

## Scope

### §S1 — `generator/stacks/rust.toml`
Authored in the shape `quarkus.toml` already establishes (`display_name`, `test_command` /
`register_command` / `unregister_command` / `crucible_reference`, `mechanics`,
`[description]` per role, `[frontmatter]` per role with its skill list, `[gotchas]` per role,
and — depending on CR-MDB-017 — a `tier_guidance` key). Content is sourced from three places,
reconciled rather than any one taken blind:

- **Registration and client surface** — Crucible's #1367 mapping:
  `rust-crucible.py register --agent YOUR_AGENT_ID --role RED|GREEN|VERIFY|FIX --cycle
  YOUR_CYCLE_ID` (both flags required — the server 409s an unbound TDD registration), the
  agent id sourced from the dispatch prompt (never minted by the agent, matching the pattern
  already correct in the other four templates), and the client resolved through the
  discovery contract CR-MDB-020 anchors on (`<target-dir>/clients/`, default
  `~/.crucible/clients/`) — never a personal checkout path in the generated artifact.
- **Tier guidance** — Crucible's #1367 fragment verbatim in substance: Cargo's own split is
  the tier boundary (`#[cfg(test)]` in-crate modules / `--lib` = unit; `tests/*.rs` targets /
  `--test <name>` = integration; `smoke-test` and `docker-e2e-gate` sit above both; `smoke-test
  --profile e2e` and `docker-e2e-gate` report `e2e`, the default `smoke-test` under `-P ci`
  reports `integration`, `workspace-regression` is the union) — sourced from their CR-CRU-111
  pin, not invented.
- **Mechanics, gotchas, per-role frontmatter (skills lists, effort, tools)** — reconciled
  against the deployed `~/.claude/agents/rust-*-agent.md` files (the pre-existing content this
  CR retires) and `skills-src/memory-templates/rust-orchestration.md` (the mechanics this repo
  already documents), so nothing already-correct in either source is silently dropped or
  contradicted. Where the deployed files and the memory template disagree, the memory template
  wins — it is Model B's own owned document.

### §S2 — Generate and retire the hand-maintained files
`python3 generator/build.py build` renders the four `rust-*-agent.md` files into
`generator/agents/`, joining the existing 16. `python3 generator/build.py --check` covers all
20. The deployed `~/.claude/agents/rust-*-agent.md` files — hand-maintained, ungenerated,
carrying the live `--phase` defect — are superseded the same way CR-MDB-022 §S5 superseded the
stale tooling copies: the installer's deploy becomes authoritative, and
`tests/test_realhome_supersede.py`'s pattern extends to assert no Model B surface still points
at a hand-maintained rust agent definition.

### §S3 — Tell Crucible
Once this CR ships, reply on the #1362–#1367 thread confirming Model B has taken ownership of
the rust stack, per their explicit request in #1367 ("If you take the rust stack, tell me and
I will treat those four as yours from then on, so nobody double-fixes").

## Acceptance criteria

### §S1
- [ ] `generator/stacks/rust.toml` exists with `display_name`, `test_command`,
      `register_command`, `unregister_command`, `crucible_reference`, `mechanics`,
      `[description]`, `[frontmatter]` and `[gotchas]` for all four roles, matching the shape
      of the other four stack files.
- [ ] `register_command` and every `[description]`/`[gotchas]` register example use `--role`
      and, for the four TDD roles, `--cycle` — zero occurrences of `--phase`.
- [ ] The client path resolves through the CR-MDB-020 discovery contract, never a personal
      checkout path.
- [ ] `tier_guidance` states Cargo's own unit/integration split and the `smoke-test`/
      `docker-e2e-gate` tier mapping Crucible pinned in CR-CRU-111.
- [ ] Content reconciled against `skills-src/memory-templates/rust-orchestration.md` — no
      contradiction between the generated agent definitions and that document.

### §S2
- [ ] `python3 generator/build.py --list` names all 20 stack×role targets (16 existing + 4
      rust).
- [ ] `python3 generator/build.py --check` exits 0 with no drift across all 20.
- [ ] No file under `generator/agents/rust-*.md` is hand-edited — every line arrives via
      `build.py build`.
- [ ] `tests/test_realhome_supersede.py`'s retired-referencer pattern covers the four
      hand-maintained rust agent definitions the same way it covers the CR-MDB-022 tooling,
      behind `MODELB_REALHOME_GATE=1`.
- [ ] The built wheel contains all 20 generated definitions — asserted against a built
      artifact, per the CR-MDB-014 defect class.

### §S3
- [ ] A reply is sent on the #1362–#1367 Sandesh thread confirming ownership, after §S1/§S2
      ship — not before, so the confirmation is backed by real content rather than an intent.

## Estimated size

1 new stack TOML (~120 lines, following `quarkus.toml`'s shape), 4 agent definitions generated,
1 real-home gate extended. No `modelb_axi/` code change; no change to the other four stacks.

## Risk

- **Reconciliation, not verbatim adoption.** Crucible's fragment is validated against their own
  fleet but was written for their dogfood context; the mechanics/gotchas sections must still be
  checked against Model B's own `rust-orchestration.md` rather than pasted wholesale.
- **Depends on CR-MDB-017 landing first.** The `tier_guidance` key and the shared-template
  rendering this CR's fragment relies on do not exist until 017 ships. Do not duplicate that
  mechanism here if 017 is delayed — wait for it.
- Retiring the deployed hand-maintained files touches the same real-home boundary CR-MDB-022
  established; reuse its pattern rather than inventing a second one.

## Non-goals

- No change to the other four stacks' content — only the `tier_guidance` mechanism they consume
  is shared (CR-MDB-017's scope, not this CR's).
- No change to any Crucible file.
- No adoption of a rust CI/CD pipeline, cargo workspace tooling beyond what CR-MDB-022 already
  adopted, or any rust-specific installer behavior.
