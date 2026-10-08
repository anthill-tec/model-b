# CR-MDB-056 — Test runs go only through the Crucible clients

**Status:** PENDING — **SEED, not the finished spec** (filed 2026-10-08 into release 1.0.0, wave 2).
Gap analysis, the design record, the spec and its pre-review happen in order when this CR starts.
**Type:** feature (agent definitions, skills, hooks, guard test)
**Priority:** P1 — release 1.0.0, wave 2 (user ruling 2026-10-08: folded into 1.0.0, not 1.1.0).
**Depends on:** none (board-authoritative: read `queue`, not this line)
**Labels:** agents, skills, hooks, crucible, enforcement
**Design reference:** Crucible #1428 (Mainline - Crucible, 2026-10-08), Model B reply #1429; pairs
with #1426 / #1427 (register first — already in the source). PRD D5; DN-multi-harness-deploy-model §D18.

## Context

Crucible's sub-agents iterated a whole session with raw runners (`python -m unittest`, `bun test`,
`bunx playwright test --grep …`) and filed only the final full suites, so nothing streamed to the
board. The briefs caused it ("iterate unfiled"), but nothing in Model B's agent definitions stopped
it: the definitions name each stack's client `test_command`, and the sub-agent procedure says "never
hand-roll raw `cargo`/`mvn`/`curl`", but no definition states a universal rule or tells an agent to
refuse a brief that contradicts it. Only cargo and mvn have blocking hooks
(`block-direct-cargo-test`, `block-direct-mvn-test`).

## Scope (seed — the three enforcement layers, user ruling 2026-10-08)

1. **The rule, in the definitions and the skills.** All stacks × red/green/fix/verify templates, the
   sub-agent procedure and the `crucible` skill state an explicit, non-negotiable rule: every test
   run — a targeted iteration, a single file, a one-test filter, a regression — goes through the
   stack's Crucible client under the dispatched agent id; never a runner invoked directly; a runner
   the client cannot drive is a client gap raised with the orchestrator; a brief that says otherwise
   is refused and escalated (`ESCALATION:`), never followed.
2. **A guard test.** A structural test fails the build when a rendered definition or a Model B skill
   shows a raw runner invocation outside a declared "never do this" list (the pattern of the
   `--phase` guard in `tests/test_client_role_contract.py`).
3. **Blocking hooks for every runner.** The block-hook family extends from cargo and mvn to
   `python -m unittest`, `pytest`, `bun test` and `bunx playwright`, so a raw run is stopped at tool
   call time, not only discouraged in text. *Measure:* how the existing two hooks match, their
   `fail_direction`, how the client's own runner subprocess is told apart from a direct call, and
   which stacks' instances `init` compiles.

## To measure at gap analysis

- **`--cycle` on `test`/`e2e`.** The installed client's `test` has no `--cycle` (measured
  2026-10-08). Model B cites only flags the installed client carries; Crucible was asked (#1429)
  whether the 0.3.0 clients (CR-CRU-147) add it. The rule cites the agent id either way.
- **The `crucible-report-*` skills are Crucible's.** They are byte-faithful imports
  (`skills-src/CRUCIBLE-HANDOVER.md`); their wording changes on Crucible's side and is re-imported.
  Model B's own `crucible` skill and the sub-agent procedure change here.
- **Rendered outputs.** `generator/agents/*` are regenerated and `.pi/agents/python-*` re-rendered;
  the RED/GREEN/FIX byte-identity baseline (`git diff 52f5b72 -- generator/agents/*-{red,green,fix}-agent.md`)
  moves with this CR by design, and the spec says so.
