# CR-MDB-024 — Rust as a fifth generated stack: close the orphaned-artifact gap CR-CRU-042 already assigned to us

**Status:** PENDING
**Type:** feature
**Priority:** P1 (an unowned, undrift-gated agent-definition set is exactly the failure class CR-CRU-042 exists to prevent, and it is live today — all four files still carry the retired `--phase` flag)
**Depends on:** CR-MDB-017 (introduces the `tier_guidance` TOML key and the shared/per-stack template split this CR's rust fragment renders through)
**Labels:** generator, rust, ownership, feature
**Phase:** Wave 5
**Design reference:** Sandesh #1362–#1367 (the correspondence that surfaced this) · Crucible's CR-CRU-042 as QUOTED TO US over Sandesh #1367 (the ownership handover: "Model B now owns the skills component in FULL — content, bundling AND deploy... Crucible does not patch either in place") · `skills-src/memory-templates/rust-orchestration.md` (existing rust footprint in this repo) · `generator/stacks/quarkus.toml` (the shape this CR follows)

## Amendments 2026-09-21 (from `audits/2026-09-21-codebase-review-docs.md`)

- **§S2 and its AC (`:86-91`, `:119-121`) are RE-SCOPED:** "the deployed `~/.claude/agents/rust-*-
  agent.md` files are superseded … the installer's deploy becomes authoritative, and
  `test_realhome_supersede.py`'s pattern extends" contradicts DN §D14/§D3 ("the 29 `~/.claude/agents/`
  files become unowned legacy: never written, never deleted"). This CR generates rust into
  `generator/agents/` only; deployment is CR-MDB-025 §S4's `.agents/agents` class; nothing under
  `~/.claude` is superseded, asserted, or touched.
- **§S1's `[frontmatter]` block is TRANSITIONAL:** it matches today's four stack files so one
  regeneration settles 017+024, and CR-MDB-025 §S1 then restructures all five into
  `[roles.<role>]` tables (`effort`→`thinking`, `skills` dropped, tools translated). Accepted
  double-regeneration per 025's Risk.
- **Doc-update AC (`:127`) gains** `docs/research/PRD-model-b-rationalization.md` §D6 ("Bespoke:
  rust ×4, vscode ×4 …") and §4.4 ("16 agents generated, 13 bespoke") — 20 generated after this CR,
  5 bespoke (electronics ×4 + `inbox-analyst`); `generator/build.py:21-23` docstring likewise.
  The "vscode ×4 remain excluded" line reads "untouched by this CR" (DN §D4 makes vscode a
  generated overlay via its own CR).
- Census pins to amend, by id: `tests/test_agent_generator.py:96-116,334-338,574-600` and
  `tests/test_installer_assets.py:97-98,363-429` (4-stack / 13-bespoke / "exactly 17 written
  files"). Keep ONE `--list` pin (032 §S4 dedups the other).

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

**Also tell them vscode is retired (§S4)** — they own `crucible-report-vscode`'s origin, and
#1369 already recorded that `vscode-crucible.py` never shipped. Retiring it on our side closes
the loop rather than leaving them maintaining an import nobody consumes.

### §S4 (ADDED 2026-09-22, user ruling) — retire the vscode agents: an IDE is not a stack

**The taxonomy is the reason, not the broken client.** Model B's agents are per **stack** — a
language, its runtime, and its test framework, which is what determines how a RED/GREEN cycle is
run and ingested. **VS Code is an editor.** A VS Code extension is TypeScript tested with
vitest/mocha; that is the bun/TypeScript stack, not a stack of its own. The four `vscode-*`
agents were a category error, and the symptoms follow from it: the generator never owned them,
`generator/stacks/` has no vscode entry, no `vscode-crucible.py` was ever shipped (Crucible
#1369), and the deployed definitions cite no client at all — they name `vitest` only. They could
not have ingested a test run if asked.

The live deployed copies were deleted 2026-09-22 (a session-level operational fix — the fleet
went from 24 definitions to 20). This section removes the repo-side substrate, which is gated and
therefore cannot be done by hand:

- `skills-src/crucible-report-vscode/` — deleted. It is a Crucible-origin import, so
  `skills-src/CRUCIBLE-HANDOVER.md`'s bundle roster drops from 7 to 6, and the byte-identity /
  coverage gates in `tests/test_skills_handover.py` move with it.
- `skills-src/crucible/references/vscode.md` and the vscode rows in `skills-src/crucible/SKILL.md`
  — deleted; the `crucible` skill must not document a client that does not exist.
- `generator/build.py`'s BESPOKE list and `tests/test_agent_generator.py:101-111` lose the four
  `vscode-*` names (the same list §S2 edits for rust, so the two land together or the list is
  wrong twice).
- `modelb_axi/scaffold.py` and `modelb_axi/cli.py` drop `vscode` from the selectable stacks.
- `tests/test_client_role_contract.py`'s `API_PATH_BUNDLES = ("crucible-report-vscode",)`
  exemption and its `test_s3_api_path_exemption_constant_names_vscode_bundle` gate are deleted
  outright — an exemption whose only member is gone is dead weight, and leaving it would make the
  next reader hunt for a bundle that no longer exists.
- `AGENTS.md`'s `crucible-report-{arduino,bun,java,python,rust,vscode}` enumeration and the
  13-bundle count are corrected; `docs/changes/README.md` records the retirement with its reason.

**§S4 acceptance criteria**

- [ ] Zero `vscode` references under `skills-src/`, `generator/`, `modelb_axi/` and `tests/`,
      other than historical mentions in closed CR specs and `archive/`.
- [ ] `skills-src/` carries **12** bundles and `CRUCIBLE-HANDOVER.md` documents **6** imported
      ones; the handover gates assert the new counts rather than being deleted.
- [ ] `generator/build.py --check` is clean, and the BESPOKE list names only definitions that
      still exist.
- [ ] `modelb-axi init --stacks vscode` is rejected with a message naming the supported stacks.
- [ ] The suite is green at its then-current baseline; no gate is deleted merely because it
      failed — each is re-pointed or removed with its subject.
- [ ] The retirement and its taxonomic reason (an IDE is not a stack) are recorded in the queue
      footer, so the category error is not re-made by a future reader who sees TypeScript
      extension work and reaches for a vscode agent.

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
- [ ] **A written content triage covers all 2460 lines of the four bespoke definitions**, each
      line in exactly one bucket — universal-procedure-dropped (template cites it),
      rust-specific-moved-to-`rust.toml`, or dropped-with-reason. Filed in the CR's commit
      message or a `docs/research/` note, not asserted in aggregate.
- [ ] Every section heading present in a bespoke definition is either reproduced in the rendered
      output, present in `rust.toml`, or named in the triage as deliberately dropped — checked
      heading by heading against the rendered files, so no section vanishes silently.
- [ ] `docs/research/DN-rationalization-plan-review.md:72` and CR-MDB-008's bespoke-exclusion
      list no longer state that rust agents are never generated; both cite the 2026-09-16 user
      ruling. `vscode ×4`, `electronics ×4` and `inbox-analyst` remain excluded and are
      untouched by this CR.

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
- **The four bespoke files are 5.5x the size of a generated definition, and the CONTENT TRIAGE
  is this CR's real work.** Measured 2026-09-16: deployed rust definitions are 471/702/814/473 =
  **2460 lines**; the generated four-role set for a comparable stack is ~130-150 each (python
  1113 total). The gap is NOT mostly rust knowledge — it is the **universal procedure restated
  inline**, which generated agents instead CITE (`python-red-agent.md:12` reads "Universal
  procedure — READ FIRST (cited, not restated)", where `rust-red-agent.md` restates the worktree
  boundary, tool usage and output discipline across ~130 lines). Removing that duplication is the
  whole point of CR-MDB-001's core split, so generating rust CLOSES a known defect rather than
  degrading the definitions.
  **Every one of the 2460 lines must be classified into exactly one of three buckets, in writing,
  before GREEN:** (a) universal procedure -> DROPPED from the definition because the template
  cites it; (b) genuinely rust-specific -> moved into a `stacks/rust.toml` key (measured
  candidates: Rust Build Caveats, `opensrc` dependency-source/crate-API verification,
  async-tests-runtime-crate, timing-dependent test rules, mock-usage rules, refactoring-tools);
  (c) neither -> dropped with the reason recorded. An unclassified line is a migration defect,
  and "the template covers it" is a claim to verify against rendered output, never an assumption.
- **This CR overturns a prior classification deliberately, on the user's ruling.**
  `docs/research/DN-rationalization-plan-review.md:72` lists rust x4 under "Bespoke kept" and
  CR-MDB-008 excludes the 13 bespoke defs from the generator target list "NEVER". That was a
  wave-1 DESCOPE justified by the size outlier (`DN:11` — "rust (470-814 lines) and vscode agents
  are bespoke outliers"), not a principle about language stacks. User ruling 2026-09-16: **rust is
  a language stack, so its agents are generated like any other stack's.** The DN line and
  CR-MDB-008's exclusion list MUST be updated in this CR's commit so the superseded
  classification does not read as authoritative afterwards — a stale "NEVER generated" line is
  exactly the half-true record that sent this CR's own analysis down the wrong path once already.

## Non-goals

- No change to the other four stacks' content — only the `tier_guidance` mechanism they consume
  is shared (CR-MDB-017's scope, not this CR's).
- No change to any Crucible file.
- No adoption of a rust CI/CD pipeline, cargo workspace tooling beyond what CR-MDB-022 already
  adopted, or any rust-specific installer behavior.
