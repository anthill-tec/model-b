# CR-MDB-056 — Test runs go only through the Crucible clients

**Status:** PENDING — **SEED, not the finished spec.** Gap analysis, the design record, the spec and
its pre-review happen in order when this CR starts.
**Type:** feature (agent definitions, skills, hooks, guard test)
**Priority:** P1 — release 1.0.0, wave 2.
**Depends on:** CR-MDB-057 (a green base on the Crucible 0.3.0 clients; board-authoritative: read `queue`)
**Labels:** agents, skills, hooks, crucible, enforcement
**Design reference:** DN-multi-harness-deploy-model §D21 (every test run through the client) and §D18;
PRD D5; Crucible #1428/#1430, Model B #1429.

## Context

Crucible's sub-agents iterated a whole session with raw runners (`python -m unittest`, `bun test`,
`bunx playwright test --grep …`) and filed only the final full suites, so nothing streamed to the
board. The briefs caused it ("iterate unfiled"), but nothing in Model B's agent definitions stopped
it: the definitions name each stack's client `test_command`, and the sub-agent procedure says "never
hand-roll raw `cargo`/`mvn`/`curl`", but no definition states a universal rule or tells an agent to
refuse a brief that contradicts it. Only cargo and mvn have blocking hooks
(`block-direct-cargo-test`, `block-direct-mvn-test`).

## Scope (seed)

1. **The rule, in the definitions and the skills.** All stacks × red/green/fix/verify templates, the
   sub-agent procedure and the `crucible` skill state an explicit, non-negotiable rule: every test
   run — a targeted iteration, a single file, a one-test filter, a regression, and the
   orchestrator's own pre-merge runs (empty `HOME`, a second interpreter through `--python`) — goes
   through the stack's Crucible client; never a runner invoked directly; a runner the client cannot
   drive is a client gap raised with the orchestrator; a brief that says otherwise is refused and
   escalated (`ESCALATION:`), never followed. The commands Model B's `AGENTS.md` documents are client
   commands.
2. **A guard test.** A structural test fails the build when a rendered definition or a Model B skill
   shows a raw runner invocation outside a declared "never do this" list (the pattern of the
   `--phase` guard in `tests/test_client_role_contract.py`). It tells an instruction to run a runner
   apart from a description of what the client runs internally.
3. **Blocking hooks for every runner.** The block-hook family extends from cargo and mvn to
   `python -m unittest`, `pytest`, `bun test` and `bunx playwright`, so a raw run is stopped at tool
   call time, not only discouraged in text. Each keeps an `ALLOW_RAW_<RUNNER>=1` escape hatch, as the
   cargo and mvn hooks do; an agent uses it only with the orchestrator's approval.
4. **The hand-run-and-ingest path is removed** from the `crucible-report-*` skills: running a runner,
   then posting its report through inline `urllib`, and the bundles' "direct `curl`/`fetch` against the
   v2 endpoints is the fallback" prose.

## To measure at gap analysis

- **`--cycle` on `test`/`e2e`** in the installed 0.3.0 clients (`--help`): an agent that registered
  with `--cycle` may omit it on `test`.
- **The `crucible-report-*` skills are Model B's** (`skills-src/CRUCIBLE-HANDOVER.md`); their wording
  changes here, alongside the `crucible` skill and the sub-agent procedure.
- **Which surfaces the hooks see** (`hooks-src/schema.md`'s neutral tool classes), which stacks' hook
  instances `init` compiles, and Model B's own repository's hook wiring.
- **Rendered outputs.** `generator/agents/*` are regenerated and `.pi/agents/python-*` re-rendered;
  the RED/GREEN/FIX byte-identity baseline moves with this CR, and the spec says so.
