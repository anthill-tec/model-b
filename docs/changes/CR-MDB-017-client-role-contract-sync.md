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
attachment a registration-time binding. The whole delta shipped in their **0.1.0**, their
first public release (confirmed Sandesh #1359: `git grep -- '--phase' 0.1.0 -- clients/`
has no hits, and CR-CRU-044/056/059 are contained in `0.1.0`, `0.1.1`, `0.1.2`). Their
latest release is **0.1.2**; the client-surface delta for both 0.1.1 and 0.1.2 is NONE.
**Model B's bundles have therefore been stale since Crucible's very first release.**

The released contract, verified 2026-08-27 against all five clients in `crucible:clients/`
and confirmed by Crucible in #1359:

- `register --agent <id> --role <ROLE>` — the enumeration is case-exact:
  `RED | GREEN | FIX | VERIFY | ORCHESTRATOR | report` (five uppercase, `report`
  lowercase). The Python clients make `--role` argparse-REQUIRED, so omitting it exits
  non-zero and sends nothing; a registration that reaches the server without a valid role
  is refused **400**: `role is required and must be one of RED | GREEN | FIX | VERIFY |
  ORCHESTRATOR | report (got no role field)`.
- `--cycle <int>` is **not** argparse-required — the SERVER owns the per-role rule.
  `RED|GREEN|FIX|VERIFY` must bind an ACTIVE cycle of an OPEN plan; an unbound TDD
  registration is refused **409** with the verbatim message
  `role RED requires a cycle binding — register with --cycle <cycleId>` (em dash U+2014),
  enforced at the route boundary before any write, so no agent row is created.
  `ORCHESTRATOR` and `report` may register unbound.
- `--phase` no longer exists: zero occurrences across the five clients and
  `_crucible_axi.py`, at every released tag.
- The agentId is FREE-FORM. The role is never inferred from its shape — an id ending
  `-GREEN` registered with `--role RED` classifies as RED.
- `--source` is constrained to `claude-md | package-json | git-repo | manual`; a value
  outside the enumeration is refused server-side with 409 and nothing is stored. Absent is
  legal. It exists on the rust/mvn/arduino clients as of 0.1.0.
- Register wire keys: `projectKey`, `agentId`, `role`, `cycleId`, `status`, `message`,
  `identity{displayName, source, repoPath}`. `phase` appears nowhere in the wire contract.

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
- `AGENTS.md` — two stale sentences. The agent-ids sentence reads as if the id encodes the
  phase: state that the id is a free-form readability habit, `--role` declares the role,
  and TDD roles bind `--cycle`. The plan-filing sentence still passes
  `--orchestrator vidushi-mdb`: **`plan-file --orchestrator` was REMOVED** in 0.1.0
  (#1359) — drop the flag, keep `--wave`.
- `contracts/crucible-envelope.md` — record the role/cycle-binding facts, cite the
  status-envelope contract document by its DOCUMENT version, and note the remaining 0.1.0
  deltas: `gate-run --skip` added, `--source` on the rust/mvn/arduino clients,
  `WORKFLOW_CYCLE_ID` gone while `WORKFLOW_ROLE`/`WORKFLOW_WAVE`/`WORKFLOW_CYCLE` remain.
- **Released-only rule.** No Model B doc may teach a verb that is not in a Crucible
  RELEASE. Per #1359 these are develop-only and 0.2.0-bound: the `queue` read verb,
  `queue-file` (+ `--from-file`), `milestone --released-at/--crs/--packages/`
  `--repair-provenance`, bun `--no-lifecycle`, and the routes `POST /api/v2/runs/start`,
  `GET|POST /api/v2/projects/<key>/queue`, `GET /api/v2/projects/<key>/releases`. 0.2.0 is
  NOT released and must never be cited as shipped.
- **Two upstream traps not to copy** (#1359): `clients/rust-crucible.py`'s docstring
  register examples (lines 70-71) omit `--cycle` and are guaranteed 409s; and
  `cli/crucible-axi.ts register` ships without `--cycle` at all, so the released
  TypeScript CLI cannot register a TDD role. Any Model B text that mentions a
  registration surface names the Python clients.

### §S5 — The guard that would have caught it
Port the transferable families of the inherited suite into a new stdlib `unittest` module
`tests/test_skill_bundle_guards.py` — per-bundle v2-endpoint truth, no unmarked v1 legacy,
ingest-is-heartbeat semantics, `tier` + `WORKFLOW_CYCLE` presence with zero
`WORKFLOW_CYCLE_ID`, and real client verbs in examples — **strengthened with a flag-surface
check** that the original lacked, and extended to the arduino bundle the original never
covered. The two agent-protocol families are NOT ported: `heartbeat.sh` and a standalone
`agent-protocol` skill are ratified out of existence and asserted absent by
`tests/test_skills_handover.py:130-137` and `:360-384`.

### §S6 — The generator emits the retired flag too
The bundle sweep above does not reach the sub-agent definitions, and they carry the same
defect at its source. `--phase` is hard-coded in all four role templates — not in the stack
data — and is appended directly after the interpolated register command:

- `generator/templates/red.md.tmpl:24` — `${register_command} --phase RED`
- `generator/templates/green.md.tmpl:29` — `${register_command} --phase GREEN`
- `generator/templates/verify.md.tmpl:26` — `${register_command} --phase VERIFY`
- `generator/templates/fix.md.tmpl:23` — `${register_command} --phase FIX`

All 16 generated definitions under `generator/agents/` therefore instruct a registration
that cannot parse, and `--role` occurs in only two files anywhere under `generator/`.
`--cycle` occurs nowhere, so even a corrected `--role` would be refused 409 for the four TDD
roles — every generated agent is currently unable to register against a released Crucible.

Each template's register step becomes `--role <ROLE>` with the case-exact enumeration, and
the four TDD templates additionally carry `--cycle <cycleId>` with the binding rule stated
where the agent will read it before running the command. Regenerate all 16 definitions with
`python3 generator/build.py build` and prove `--check` clean; no generated file is
hand-edited.

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
- [ ] `skills-src/crucible/SKILL.md` states, in substance: the case-exact `--role`
      enumeration; that `--cycle` is required for `RED|GREEN|FIX|VERIFY` **by the server,
      not by argparse**, refused 409; that a missing or out-of-enum role is refused 400;
      that `ORCHESTRATOR`/`report` may register unbound; and that the agentId is free-form
      with the role never inferred from it.
- [ ] Zero occurrences of `--orchestrator` paired with `plan-file` under `skills-src/`,
      `contracts/`, and `AGENTS.md` (the flag was removed in 0.1.0).
- [ ] Zero occurrences of the develop-only verbs `queue-file`, `--from-file`,
      `--released-at`, `--repair-provenance`, `--no-lifecycle` and of the string `0.2.0`
      presented as released, anywhere under `skills-src/` or `contracts/`.
- [ ] `skills-src/memory-templates/java-orchestration.md` documents the `--role`
      enumeration and the binding rule; no `--phase` remains.
- [ ] `contracts/crucible-envelope.md` cites `STATUS-CONTRACT.md` **document version
      2.0.0**, records that the product release carrying it is `0.1.0`, and never implies a
      Crucible product version of `2.0.0`.
- [ ] Documented Crucible release facts match #1359 exactly where stated: latest release
      `0.1.2`; install entry point `crucible-axi install [--target-dir <dir>]` with default
      `~/.crucible`; run verb `crucible-axi serve`.

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

### §S6
- [ ] Zero occurrences of `--phase` under `generator/` (templates and generated agents).
- [ ] All four role templates emit `--role` with the case-exact role for that template.
- [ ] `red`, `green`, `verify` and `fix` templates emit `--cycle` and state the binding rule
      above the command the agent will run.
- [ ] All 16 files under `generator/agents/` carry `--role` and `--cycle`, and
      `python3 generator/build.py --check` exits 0 with no drift.
- [ ] No file under `generator/agents/` is hand-edited — every change arrives via
      `build.py build` from a template or stack edit.

## Estimated size

9 documentation files edited (1 routing skill, 6 bundles, 1 memory template, `AGENTS.md`,
`contracts/crucible-envelope.md`), 4 role templates edited, 16 agent definitions
regenerated, 1 test re-pinned, 1 test module added (~5 methods). Docs, templates and tests
only; no `modelb_axi/` code change.

## Risk

- The flag-surface guard must read the client `--help` surface without invoking a server.
  Shelling `--help` is safe (no network) but couples the suite to a sibling checkout —
  scope the guard to a declared allow-list of flags maintained in the test module, and let
  the CR-MDB-020 anchoring work (now filed) decide how the client is located.
- Re-pinning `tests/test_crucible_skill.py:169` is a sanctioned amendment, not a
  convenience: the assertion is inverted, never deleted.

## Non-goals

- No change to the clients themselves — they are Crucible's.
- No re-import of `agent-protocol` and no adoption of `heartbeat.sh`.
- No anchoring of the bundles' client paths (CR-MDB-020) and no installer change
  (CR-MDB-018).
