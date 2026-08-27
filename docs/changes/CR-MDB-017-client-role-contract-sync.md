# CR-MDB-017 — Client-verb contract sync: the owned bundles still teach the retired `--phase` flag

**Status:** PENDING
**Type:** maintenance
**Priority:** P1 (blocks release 0.1.0 — every `register` example we ship is non-executable against the released clients)
**Depends on:** CR-MDB-016 (Model B owns the seven bundles outright)
**Labels:** crucible, skills, contract, patch
**Phase:** Wave 5
**Design reference:** `crucible:clients/STATUS-CONTRACT.md` §"Agent identity and role" · §"The identity source is an enumeration" · §"The agent identity is declared, never fabricated" · §"The cycle binding is declared at registration" (the status-envelope contract **document**, version 2.0.0) · `skills-src/CRUCIBLE-HANDOVER.md` §Maintenance-contract · Sandesh #1357

## Context

Crucible renamed the registration classification flag `--phase` → `--role` fleet-wide as a
**clean break** — no alias, no dual-key handling on the wire — and made the cycle
attachment a registration-time binding. The released client surface, verified 2026-08-27
against all five clients in `crucible:clients/`:

- `register --agent <id> --role {RED,GREEN,FIX,VERIFY,ORCHESTRATOR,report}` — `--role` is
  REQUIRED; omitting it fails argument parsing with a non-zero exit and sends no
  registration.
- `--cycle <id>` is MANDATORY for the TDD roles `RED|GREEN|FIX|VERIFY`, bound to an ACTIVE
  cycle of an open plan; an unbound TDD registration is refused with HTTP 409 and no agent
  row is created. `ORCHESTRATOR` and `report` may register unbound.
- `--phase` no longer exists: zero occurrences across the five clients and
  `_crucible_axi.py`.
- The agentId is FREE-FORM. The role is never inferred from its shape — an id ending
  `-GREEN` registered with `--role RED` classifies as RED.
- `--source` is constrained to `claude-md | package-json | git-repo | manual`; a value
  outside the enumeration is refused server-side with 409 and nothing is stored. Absent is
  legal.

**Surfaces (verified 2026-08-27).** Every bundle Model B owns still teaches the retired
flag, and none of them mentions either replacement:

- `skills-src/crucible/SKILL.md:17` — `register --agent <id> --phase <PHASE>`
- `skills-src/crucible-report-arduino/SKILL.md:37`, `-bun/SKILL.md:36`,
  `-java/SKILL.md:32`, `-python/SKILL.md:39`, `-rust/SKILL.md:38` —
  `register --agent … --phase RED`
- `skills-src/memory-templates/java-orchestration.md:17` —
  `register --phase RED|GREEN|FIX|VERIFY|ORCHESTRATOR`
- `--role` and `--cycle` occur **zero** times across all seven bundles.

These bundles are force-included into the `modelb-axi` wheel and deployed to the global
skill store, so an agent that follows them issues a command that cannot parse.

Two repo-side facts make this more than a text edit:

- `tests/test_crucible_skill.py:169` **positively requires** the literal `--phase` in
  `skills-src/crucible/SKILL.md`. Model B's own suite pins the removed flag.
- The inherited semantic guard suite could not have caught this. Its
  `scriptSubcommandPin` helper (`docs/research/crucible-clients-skills-guard.test.ts:301-304`)
  matches only the substring `"<script> <subcommand>"` and never inspects flags. The
  suite is also mis-described in the queue register as "22-test": the file carries **19
  static `test()` declarations expanding to 37 runtime cases** across 7 `describe` blocks.
- The byte-identity fidelity gates that froze the imported bundles now self-skip
  (`tests/test_skills_handover.py:190-194`, `tests/test_installer_assets.py:223-227`)
  because the origin `crucible:clients/skills/` was retired after the handover, so
  `skills-src/` is editable without violating an AC.

## Scope

### §S1 — Re-pin the assertion that requires the retired flag
`tests/test_crucible_skill.py:169` asserts the PRESENCE of `--phase` in
`skills-src/crucible/SKILL.md`. Invert it: assert the presence of `--role` and the absence
of `--phase` as a register flag. Sanctioned amendment — the pinned contract was superseded
upstream.

### §S2 — Sync the register contract in `skills-src/crucible/SKILL.md`
Replace the `register --agent <id> --phase <PHASE>` instruction with the released surface:
`--role` required and enumerated; `--cycle` mandatory for the four TDD roles and refused
(409) when absent; `ORCHESTRATOR`/`report` may register unbound; the agentId is free-form
and never parsed for role; `--source` enumerated with absent legal. Keep the existing
ingest-is-heartbeat statement intact — it is unaffected.

### §S3 — Sync the six per-stack bundles
`crucible-report-{arduino,bun,java,python,rust,vscode}/SKILL.md`: every `register` example
carries `--role <ROLE>`, and every example whose role is `RED|GREEN|FIX|VERIFY` also
carries `--cycle <id>`. No bundle retains `--phase`. The vscode bundle is included even
though it has no live client (its documented surface must not teach a retired flag).

### §S4 — Sync the project-layer conventions that restate the contract
- `skills-src/memory-templates/java-orchestration.md:17` — `--phase` enumeration becomes
  the `--role` enumeration with the binding rule.
- `AGENTS.md` — the agent-ids sentence currently reads as if the id encodes the phase.
  State the contract: the id is a free-form readability habit, `--role` declares the role,
  and TDD roles bind `--cycle`.
- `contracts/crucible-envelope.md` — record the role/cycle-binding facts and cite the
  status-envelope contract document by its document version.

### §S5 — The guard that would have caught it
Port the transferable families of the inherited suite into a new stdlib `unittest` module
`tests/test_skill_bundle_guards.py` — per-bundle v2-endpoint truth, no unmarked v1 legacy,
ingest-is-heartbeat semantics, `tier` + `WORKFLOW_CYCLE` presence with zero
`WORKFLOW_CYCLE_ID`, and real client verbs in examples — **strengthened with a flag-surface
check** that the original lacked, and extended to the arduino bundle the original never
covered. The two agent-protocol families are NOT ported: `heartbeat.sh` and a standalone
`agent-protocol` skill are ratified out of existence and asserted absent by
`tests/test_skills_handover.py:130-137` and `:360-384`.

## Acceptance criteria

### §S1
- [ ] `tests/test_crucible_skill.py` contains no assertion requiring the substring
      `--phase`; it asserts `--role` present in `skills-src/crucible/SKILL.md`.

### §S2 / §S3 / §S4
- [ ] Zero occurrences of `--phase` under `skills-src/`, `contracts/`, and `AGENTS.md`.
- [ ] Every `register` example under `skills-src/` carries `--role` with a value from
      `{RED, GREEN, FIX, VERIFY, ORCHESTRATOR, report}`.
- [ ] Every `register` example under `skills-src/` whose `--role` is one of
      `{RED, GREEN, FIX, VERIFY}` also carries `--cycle`.
- [ ] `skills-src/crucible/SKILL.md` states all four rules verbatim in substance:
      `--role` required and enumerated; `--cycle` mandatory for the four TDD roles with a
      409 on omission; `ORCHESTRATOR`/`report` unbound-legal; agentId free-form with the
      role never inferred from it.
- [ ] `skills-src/memory-templates/java-orchestration.md` documents the `--role`
      enumeration and the binding rule; no `--phase` remains.
- [ ] `contracts/crucible-envelope.md` cites `STATUS-CONTRACT.md` **document version
      2.0.0** and never implies a Crucible product version of 2.0.0.

### §S5
- [ ] `tests/test_skill_bundle_guards.py` exists, is stdlib `unittest`, spawns no
      subprocess and starts no server.
- [ ] It covers all seven owned bundles including arduino.
- [ ] It fails when any `register` example under `skills-src/` names a flag absent from the
      corresponding client's `--help` surface — asserted by a fixture case carrying
      `--phase`.
- [ ] It asserts zero `WORKFLOW_CYCLE_ID` occurrences under `skills-src/` (the guard the
      origin suite called mandatory).
- [ ] No test asserts the existence of `skills-src/agent-protocol/` or any `heartbeat.sh`.

## Estimated size

9 files edited (1 routing skill, 6 bundles, 1 memory template, `AGENTS.md`,
`contracts/crucible-envelope.md`), 1 test re-pinned, 1 test module added (~5 methods).
Docs + tests only; no `modelb_axi/` code change.

## Risk

- The flag-surface guard must read the client `--help` surface without invoking a server.
  Shelling `--help` is safe (no network) but couples the suite to a sibling checkout —
  scope the guard to a declared allow-list of flags maintained in the test module, and let
  the CR-MDB-020 anchoring work decide how the client is located.
- Re-pinning `tests/test_crucible_skill.py:169` is a sanctioned amendment, not a
  convenience: the assertion is inverted, never deleted.

## Non-goals

- No change to the clients themselves — they are Crucible's.
- No re-import of `agent-protocol` and no adoption of `heartbeat.sh`.
- No anchoring of the bundles' client paths (CR-MDB-020) and no installer change
  (CR-MDB-018).
