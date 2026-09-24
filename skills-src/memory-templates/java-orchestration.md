# Java/Quarkus Orchestration — Maven + Crucible + worktree-flow (orchestrator-side)

Java/Quarkus-stack embodiment of `orchestration-common.md` (workflow, approval gates,
dispatch, verify-independently — not restated here) and
`~/.agents/skills/model-b/references/sub-agent-procedure.md` (sub-agent procedure). This file is the Java mechanics: the scripts, the test tiers, the gate sequence,
the Quarkus-specific gotchas. Sub-agent test/impl conventions live in `java-testing-practices.md`
+ `java-coding-standards.md`; the quarkus-{red,green,verify,fix}-agent definitions reference all four.

> The process model is the SAME as Rust (design phase on develop → execution phase on a
> feature branch; RED+GREEN cycles; VERIFY; FIX; regression+merge; CR/PRD/DN docs). Only the
> mechanics differ. Where this file is silent, the universal tier governs.
>
> **CR / PRD / DN doc conventions → the `cr-authoring` skill** (universal; CReq/CRes pattern in its `references/creq-cres.md`). Java/Quarkus projects use the same `docs/changes/` (CR queue) + `docs/research/` (PRD/DN) layout, the same `Context/Scope §S/ACs/Risk/Non-goals` CR structure, text status states, and integration-AC discipline. Legacy `Architecture.md`/`Implementation.md` remain for system overview + phase tracking.

## Tooling (the workflow is embodied here — don't hand-roll)
- **`~/.crucible/clients/mvn-crucible.py`** (Crucible's installed client, listed in `~/.crucible/crucible-clients.json`) — single entry for Maven test runs + Crucible ingest. Four test tiers + lifecycle + docker. **Use the CLI, NEVER inline curl/python** — a stable signature gets one-time permission approval; per-call inline re-prompts every run. Subcommands:
  - `register --role RED|GREEN|FIX|VERIFY|ORCHESTRATOR|report [--cycle <cycleId>]` / `unregister` — agent lifecycle (heartbeat / remove; `identity.displayName` inside the payload). `--role` is required and case-exact (five uppercase, `report` lowercase); the server binds the cycle at registration — `RED|GREEN|FIX|VERIFY` must pass `--cycle` for an ACTIVE cycle of an OPEN plan or the registration is refused 409, while `ORCHESTRATOR`/`report` may register unbound.
  - `unit --test <Class[#method]>` — targeted surefire (RED/GREEN cycle level). `mvn clean test -Dtest=…`. No coverage.
  - `module [--module <m> --also-make]` — a whole module's surefire suite. `mvn clean test [-pl m -am]`. No coverage.
  - `compile` — `mvn clean test-compile` → `/api/v2/runs/compile` (RED-as-compile-fail path).
  - `e2e [--failsafe-only] [--native] [--with-docker]` — failsafe `*IT.java` / `@QuarkusIntegrationTest`. No coverage.
  - `regression` — full reactor `mvn clean verify` → surefire + failsafe + JaCoCo → `/api/v2/runs/parsed` **with coverage**. Orchestrator gate.
  - `auto-ingest [--coverage]` — ingest EXISTING reports without running mvn.
  - `docker-up`/`docker-down`, `pre-merge-gate` (docker-up → regression → docker-down).
  - Common flags: `--module`/`--also-make` (`-pl`/`-am`), `--native` (`-Dnative`), `--profile P` (`-P`), `--system-prop k=v` (`-Dk=v`), `--update-snapshots` (`-U`), `--maven-dir backend` (monorepo), `--coverage-profile`, `--log <file>`.
  - No project hardcoded — defaults to the git repo of CWD; `--project-dir`/`$MVN_CRUCIBLE_PROJECT_DIR`; reads `CRUCIBLE_PROJECT_KEY` (a UUID) from `<project-dir>/.env`. Optional `.env`: `CRUCIBLE_MAVEN_DIR`, `CRUCIBLE_COMPOSE_FILE`, `CRUCIBLE_DOCKER_SERVICES`, `CRUCIBLE_BIND_MOUNT_PATHS`, `CRUCIBLE_COVERAGE_PROFILE`.
- **`~/.agents/scripts/worktree-flow.py`** — parallel-CR isolation: `start`/`status`/`sync`/`finish`/`abort`. Git-based, **stack-agnostic** — Java CRs use it unchanged. `finish` = `merge --no-ff` → `worktree remove` → `branch -d`; run from the integration tree, not inside the worktree (leave the worktree first); atomic merge lock serializes parallel finishes. Does NOT replace `git flow feature start` for sequential single-CR work.
  - **Scheduling is stack-agnostic — a Java track gets its next CR exactly like Rust.** Readiness is asked of Crucible, never of the tool: `python3 ~/.crucible/clients/python-crucible.py next --track "Track N - <Project>"` → `NEXT <cr>` | `HOLD <cr>` (deps not all COMPLETED) | `DRAINED`. Loop + HOLD/DRAINED semantics are documented in `orchestration-track.md`; the `worktree-flow` command set is in `rust-orchestration.md`.
  - **The split (CR-MDB-028, 2026-09-21):** `worktree-flow` owns what it derives from git — worktrees, ahead/behind, phase, merge; Crucible owns queue membership, release, wave, seq, dependencies and readiness. The tool's ChangeSet DB half is gone.
- **`crucible` skill, `references/java.md`** — documents the underlying surefire/JaCoCo ingest API. `mvn-crucible.py` automates it; the reference file is the API doc.

## The four test tiers (the differentiation)
| Tier | When | Command | Coverage |
|---|---|---|---|
| **unit** | RED/GREEN cycle — one class/method | `mvn clean test -Dtest=<pattern>` | never |
| **module** | a module's full surefire suite (reactor `-pl`) | `mvn clean test [-pl m -am]` | never |
| **e2e** | `*IT.java` / `@QuarkusIntegrationTest`, optionally native | `mvn clean verify [-Dnative]` / `failsafe:integration-test` | never |
| **regression** | orchestrator pre-merge gate — full reactor | `mvn clean verify` + JaCoCo | **yes (full green only)** |

- **Per cycle = targeted** (`unit`/`module` on the touched class/module). **Per CR = full reactor `regression`.** Running the whole `verify` every cycle wastes minutes.
- **`clean` always** on test runs — wipes stale `target/surefire-reports/` so only the SUT's XML is ingested.

## Pre-merge gate (the regression gate)
1. `mvn-crucible.py regression --agent <orchestrator-id>` → `mvn clean verify` (whole reactor) → parse surefire + failsafe + JaCoCo → `/api/v2/runs/parsed`.
2. **Coverage published ONLY on a zero-failure full run** — JaCoCo from a partial/failed/targeted run is incomplete; the script refuses to attach it when `failed > 0`.
3. For CRs touching docker-compose e2e: `pre-merge-gate` wraps docker-up → regression → docker-down. (Quarkus DevServices/TestContainers self-provision containers and need no compose.)
4. **Report ignored/skipped tests explicitly** — every regression. Enumerate `@Disabled`/`@DisabledIf`/skipped tests with reasons; distinguish env-gated (docker/native unavailable) from real coverage holes. A bare pass/skip count hides them.
5. Close the CR + update README (status, queue, badges) **before** `git flow feature finish` — never after (use the project's `check-cr-close` equivalent).

## JaCoCo — read the RIGHT report
Quarkus emits two JaCoCo outputs; only one is correct for Quarkus-managed classes.
- ✅ `target/jacoco-report/jacoco.csv` (the `quarkus-jacoco` extension). `mvn-crucible.py regression` reads this, summed across the reactor (lines/methods/branches).
- ❌ `target/site/jacoco/jacoco.csv` (raw maven plugin) — shows 0% for Quarkus-managed classes; fallback only.
- exec: ✅ `target/jacoco-quarkus.exec` vs ❌ `target/jacoco.exec`. Detail in `java-testing-practices.md`. Target: >80% instruction on I/O-backed service classes.

## RED that won't compile
A Java RED frequently fails to **compile** (the target class/method doesn't exist yet) — that is a valid RED. Ingest via `mvn-crucible.py unit --agent <id>` (auto-falls-back to `mvn clean test-compile` → `/api/v2/runs/compile`) or `compile --agent <id>`. Never skip ingesting a compile-fail RED.

## Layered enterprise architecture (Quarkus-specific — folded into the universal agents)
Quarkus services follow **Model → Repository → Service → Resource** layering (vs Rust's crate/module split). Migration/implementation is **bottom-up, one class at a time** (see `java-testing-practices.md` "Layer Migration Order"). The agent set is the **universal RED/GREEN/VERIFY/FIX** (same as Rust) — there are NO separate layer-planner/reviewer/auditor agents. Their stack-specific knowledge is folded in: REST/Resource + E2E/smoke/load test patterns → `quarkus-red-agent` + `java-testing-practices.md`; Resource impl + REST-client conventions → `quarkus-green-agent`; per-layer review + OWASP backend security → `quarkus-verify-agent`. Planning is the **orchestrator's** job (gap analysis + cycle plan), per standard orchestration — agents execute.

### Planning the layers (orchestrator — architecture + cycle planning)
When chopping a layered feature into cycles, sequence bottom-up and choose the right RED test kind per layer (the dispatch prompt tells the RED agent which):
- **Model** (entities / enums / value objects) → **pure POJO tests, plain JUnit 5, NO `@QuarkusTest`** (no CDI container needed).
- **DTO** (API request/response contracts — the layer between Service and Resource) → pure POJO / serialization tests (usually test-light; this is why the test-migration order in `java-testing-practices.md` lists the test-bearing layers Model→Repository→Service→Resource).
- **Repository** (Panache reactive data access) → `@QuarkusTest` + DevServices/TestContainers integration.
- **Service** (business logic + events) → `@QuarkusTest` + DevServices/TestContainers integration (`@InjectMock` only for non-I/O collaborators).
- **Resource** (REST) → REST-assured / `@RegisterRestClient` IT.

Full order: **Model → DTO → Repository → Service → Resource.**

**Reuse shared-library components before creating new ones.** Check the project's AGENTS.md for the shared lib (e.g. `4pm-Store-utils`) and maximize reuse; common components live under `org.fourpm.utils.*` — `IdGenerator` (use instead of `UUID.randomUUID()`), exception types (`org.fourpm.utils.exception.*`), `ModelIdCache`, `GlobalExceptionMappers`.

**RediSearch (projects using Redis search):** TAG-field queries use uppercase values in curly braces (`@status:{AVAILABLE}`); always pass `DD=true` on index cleanup (`ftDropIndex(indexName, true)`) so the doc-hashes are dropped too.

## Quarkus build + test gotchas (orchestrator-relevant)
- **DevServices / TestContainers** auto-provision MongoDB/Redis/etc. for `@QuarkusTest`. Use `@QuarkusTestResource(..., restrictToAnnotatedClass = true)` for isolation. **Check docker is clean before native/JVM e2e cycles** (`mvn-crucible.py e2e` runs a `docker ps` clean-check) — stale containers from a prior run poison the suite.
- **`@Nested` + Quarkus continuous testing** can throw `ClassCastException` — disable continuous testing (`quarkus.test.continuous-testing=false`) or run via `mvn` rather than dev mode.
- **Native (GraalVM) builds** are RAM-heavy and slow: `mvn clean package -Dnative` then `failsafe:integration-test -Dnative` (or `mvn-crucible.py e2e --native --failsafe-only`). Budget time; don't run native on every cycle — JVM e2e for cycles, native at the gate/CI.
- **Surefire vs Failsafe:** surefire runs `*Test.java` (unit), failsafe runs `*IT.java` (integration). `mvn test` = surefire only; `mvn verify` = both + package.
- **Don't parse mvn console output for results** — read `target/surefire-reports/*.txt` / `*.xml` (and failsafe). Use `--log <file>` to capture a long run, then grep the reports — never re-run a multi-minute suite to "see" results.
- **Multi-module reactor** (`runtime`+`deployment` libs): scope with `-pl <module> -am`. **Monorepo backend** (pom not at repo root): `--maven-dir backend` or `CRUCIBLE_MAVEN_DIR=backend` in `.env`.

## Disk / cache hygiene
`mvn clean` wipes `target/`. Local `~/.m2/repository` grows over time — periodic `du -sh ~/.m2` + prune is orchestrator-side, not per-cycle. Native builds + GraalVM are RAM-heavy (watch memory, not disk).
