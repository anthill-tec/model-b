# CR-MDB-056 — Test runs go only through the Crucible clients

**Status:** PENDING — **SEED, not the finished spec** (filed 2026-10-08 into release 1.0.0, wave 2).
Gap analysis, the design record, the spec and its pre-review happen in order when this CR starts.
**Type:** feature (agent definitions, skills, hooks, guard test)
**Priority:** P1 — release 1.0.0, wave 2 (user ruling 2026-10-08: folded into 1.0.0, not 1.1.0).
**Depends on:** CR-MDB-057 (green base on the 0.3.0 clients; board-authoritative: read `queue`)
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

## User rulings (2026-10-13, at gap analysis)

1. **CR-MDB-057 runs first.** On the 0.3.0 clients `develop` is red (one test steers the client
   through the retired `$CRUCIBLE_URL`; CR-057 owns its fix), so CR-056 branches from CR-057's green
   base. Board: re-sequenced (057 at 2032, 056 at 2033) and `cr-depends --on CR-MDB-057`.
2. **The rule binds agents AND the orchestrator.** The orchestrator's own runs — the pre-merge
   gate's empty-HOME and `python3.11` passes, and the commands `AGENTS.md` documents — go through the
   client too (`--python` for 3.11; the user installs `xmlrunner` for 3.11).
3. **The escape hatch stays,** as on the cargo/mvn hooks (`ALLOW_RAW_<RUNNER>=1`); the definitions
   say an agent uses it only with the orchestrator's approval.

## Gap analysis — paused at Step 0 + first reach pass (2026-10-13), resumes after CR-057 merges

- **Step 0 (develop `665187e`, clients 0.3.0, through the client, unfiled):** real HOME 2077 tests,
  1 failure (`CrucibleClientResolvesScaffoldedKeyTest.test_filled_env_key_resolves_through_the_installed_client`
  — the client ignored `$CRUCIBLE_URL` and reached the production board with a stub key, read-only);
  empty HOME 2077 OK, 10 skips, temp home left empty. **Re-measure on CR-057's merge.**
- **The hooks already see `ctx_shell`:** the Pi runtime maps `bash`, `ctx_shell` (raw or not) and
  shell-language `ctx_execute` to the neutral `bash` class (`hooks-src/schema.md` v1). Not seen:
  `lean_ctx` (arbitrary CLI), `ctx_call`, `ctx_execute` in a non-shell language — the hooks are a
  deterrent, not a boundary (the permission side is CR-MDB-049).
- **Model B's own repo compiles no hooks:** `.pi/extensions/` holds only the permission config, so
  no guard runs in Model B itself today.
- **`init` emits block hooks per stack** (`scaffold._hook_instances`: rust → cargo, java/quarkus →
  mvn, `fail_direction = "closed"`); python and bun get none.
- **Reach (raw-runner text):** `crucible-report-python` §B instructs `.venv/bin/pytest … --junitxml`
  then hand-ingest (a direct contradiction); the other report skills describe what the client runs
  internally ("Runs `bun test` …") — the guard must tell description from instruction; the Java
  memory templates teach `./mvnw test` (CR-MDB-060 rewrites them); `AGENTS.md` Testing lists raw
  `python3 -m unittest` commands; the generator templates and stack files carry none.
- **`python3.11` has no `xmlrunner`** (measured), so the 3.11 gate pass cannot go through the client
  until it is installed.
## To measure at gap analysis

- **`--cycle` on `test`/`e2e`.** The installed 0.2.x client's `test` has no `--cycle` (measured
  2026-10-08). Crucible #1430: Crucible 0.3.0 (CR-CRU-171) adds `--cycle` to `test` in all five
  clients, to `bun-crucible.py e2e`, to mvn's unit/module/integration/e2e/bdd and to rust's
  smoke-test/workspace-regression/pre-merge-gate; an agent that registered with `--cycle` may omit
  it on `test`. Model B cites only flags the installed client carries, so the wording is taken from
  the 0.3.0 `--help` once 0.3.0 is installed (it releases before Model B 1.0.0).
- **The `crucible-report-*` skills are Model B's.** `skills-src/CRUCIBLE-HANDOVER.md` records full
  ownership (#1336/#1337, ratified 2026-07-28); Crucible's `clients/skills/` is frozen, and Crucible
  confirmed it in #1430. Their wording changes here, as a Model B doc-sync, alongside the `crucible`
  skill and the sub-agent procedure. (The Roundhouse umbrella `AGENTS.md` line calling them
  "byte-faithful imports from Crucible" is stale — a root-session fix, not this CR.)
- **Pre-release ask.** Per the handover's maintenance contract, Crucible confirms the client changes
  shipped since the last doc-sync before 1.0.0 is released; CR-CRU-171 is already one.
- **Rendered outputs.** `generator/agents/*` are regenerated and `.pi/agents/python-*` re-rendered;
  the RED/GREEN/FIX byte-identity baseline (`git diff 52f5b72 -- generator/agents/*-{red,green,fix}-agent.md`)
  moves with this CR by design, and the spec says so.
