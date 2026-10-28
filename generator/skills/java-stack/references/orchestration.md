<!-- The `java-stack` skill's orchestrator reference: the Java/Quarkus mechanics an orchestrator owns (moved into the skill by CR-MDB-060). -->

# Java/Quarkus Orchestration — Maven + Crucible + worktree-flow (orchestrator-side)

Java/Quarkus-stack embodiment of `orchestration-common.md` (workflow, approval gates,
dispatch, verify-independently — not restated here) and
`~/.agents/skills/model-b/references/sub-agent-procedure.md` (sub-agent procedure). This file is the Java mechanics: the scripts and the gate sequence.
The agent-facing material — the test tiers, the test/impl conventions, the Quarkus gotchas — lives
in the quarkus-{red,green,verify,fix}-agent definitions and the `java-stack` skill.

> The process model is the SAME as Rust (design phase on develop → execution phase on a
> feature branch; RED+GREEN cycles; VERIFY; FIX; regression+merge; CR/PRD/DN docs). Only the
> mechanics differ. Where this file is silent, the universal tier governs.
>
> **CR / PRD / DN doc conventions → the `cr-authoring` skill** (universal; CReq/CRes pattern in its `references/creq-cres.md`). Java/Quarkus projects use the same `docs/changes/` (CR specs; the queue is on the Crucible board) + `docs/research/` (PRD/DN) layout, the same `Context/Scope §S/ACs/Risk/Non-goals` CR structure, text status states, and integration-AC discipline. Legacy `Architecture.md`/`Implementation.md` remain for system overview + phase tracking.

## Tooling (the workflow is embodied here — don't hand-roll)
- **`~/.crucible/clients/mvn-crucible.py`** (Crucible's installed client, listed in `~/.crucible/crucible-clients.json`) — single entry for Maven test runs + Crucible ingest. Test tiers + lifecycle + docker. **Use the CLI, NEVER inline curl/python** — a stable signature gets one-time permission approval; per-call inline re-prompts every run. Subcommands:
  - `register --role RED|GREEN|FIX|VERIFY|ORCHESTRATOR|report [--cycle <cycleId>]` / `unregister` — agent lifecycle (heartbeat / remove; `identity.displayName` inside the payload). `--role` is required and case-exact (five uppercase, `report` lowercase); the server binds the cycle at registration — `RED|GREEN|FIX|VERIFY` must pass `--cycle` for an ACTIVE cycle of an OPEN plan or the registration is refused 409, while `ORCHESTRATOR`/`report` may register unbound.
  - `regression` — the full reactor's clean build through Maven's verify phase → surefire + failsafe + JaCoCo → `/api/v2/runs/parsed` **with coverage**. Orchestrator gate.
  - `auto-ingest [--coverage]` — ingest EXISTING reports without running mvn.
  - `docker-up`/`docker-down`, `pre-merge-gate` (docker-up → regression → docker-down).
  - No project hardcoded — defaults to the git repo of CWD; `--project-dir`/`$MVN_CRUCIBLE_PROJECT_DIR`; reads `CRUCIBLE_PROJECT_KEY` (a UUID) from `<project-dir>/.env`. Optional `.env`: `CRUCIBLE_MAVEN_DIR`, `CRUCIBLE_COMPOSE_FILE`, `CRUCIBLE_DOCKER_SERVICES`, `CRUCIBLE_BIND_MOUNT_PATHS`, `CRUCIBLE_COVERAGE_PROFILE`.
- **`~/.agents/scripts/worktree-flow.py`** — parallel-CR isolation: `start`/`status`/`sync`/`finish`/`abort`. Git-based, **stack-agnostic** — Java CRs use it unchanged. `finish` = `merge --no-ff` → `worktree remove` → `branch -d`; run from the integration tree, not inside the worktree (leave the worktree first); atomic merge lock serializes parallel finishes. Does NOT replace `git flow feature start` for sequential single-CR work.
  - **Scheduling is stack-agnostic — a Java track gets its next CR exactly like Rust.** Readiness is asked of Crucible, never of the tool: `python3 ~/.crucible/clients/python-crucible.py next --track "Track N - <Project>"` → `NEXT <cr>` | `HOLD <cr>` (deps not all COMPLETED) | `DRAINED`. Loop + HOLD/DRAINED semantics are documented in `orchestration-track.md`; the `worktree-flow` command set is in the tool's own help (`worktree-flow.py --help`).
  - **The split (CR-MDB-028, 2026-09-21):** `worktree-flow` owns what it derives from git — worktrees, ahead/behind, phase, merge; Crucible owns queue membership, release, wave, seq, dependencies and readiness. The tool's ChangeSet DB half is gone.
- **`crucible` skill, `references/java.md`** — documents the underlying surefire/JaCoCo ingest API. `mvn-crucible.py` automates it; the reference file is the API doc.

## Pre-merge gate (the regression gate)
1. `mvn-crucible.py regression --agent <orchestrator-id>` → a clean build of the whole reactor through the verify phase → parse surefire + failsafe + JaCoCo → `/api/v2/runs/parsed`.
2. **Coverage published ONLY on a zero-failure full run** — JaCoCo from a partial/failed/targeted run is incomplete; the script refuses to attach it when `failed > 0`.
3. For CRs touching docker-compose e2e: `pre-merge-gate` wraps docker-up → regression → docker-down. (Quarkus DevServices/TestContainers self-provision containers and need no compose.)
4. **Report ignored/skipped tests explicitly** — every regression. Enumerate `@Disabled`/`@DisabledIf`/skipped tests with reasons; distinguish env-gated (docker/native unavailable) from real coverage holes. A bare pass/skip count hides them.
5. Close the CR: before `git flow feature finish`, the spec's `**Status:**` flip (use the project's `check-cr-close` equivalent); after it, `cr-close --commit <merge sha> --agent <orchestrator-id>`, which takes the merge's sha and posts `cr-merged`.

## JaCoCo — read the RIGHT report
Quarkus emits two JaCoCo outputs; only one is correct for Quarkus-managed classes.
- ✅ `target/jacoco-report/jacoco.csv` (the `quarkus-jacoco` extension). `mvn-crucible.py regression` reads this, summed across the reactor (lines/methods/branches).
- ❌ `target/site/jacoco/jacoco.csv` (raw maven plugin) — shows 0% for Quarkus-managed classes; fallback only.
- exec: ✅ `target/jacoco-quarkus.exec` vs ❌ `target/jacoco.exec`. Detail in the `java-stack` skill's `references/testing-practices.md`. Target: >80% instruction on I/O-backed service classes.

## Layered enterprise architecture (Quarkus-specific — folded into the universal agents)

### Planning the layers (orchestrator — architecture + cycle planning)
When chopping a layered feature into cycles, sequence bottom-up and choose the right RED test kind per layer (the dispatch prompt tells the RED agent which):
- **Model** (entities / enums / value objects) → **pure POJO tests, plain JUnit 5, NO `@QuarkusTest`** (no CDI container needed).
- **DTO** (API request/response contracts — the layer between Service and Resource) → pure POJO / serialization tests (usually test-light; this is why the test-migration order in the `java-stack` skill's `references/testing-practices.md` lists the test-bearing layers Model→Repository→Service→Resource).
- **Repository** (Panache reactive data access) → `@QuarkusTest` + DevServices/TestContainers integration.
- **Service** (business logic + events) → `@QuarkusTest` + DevServices/TestContainers integration (`@InjectMock` only for non-I/O collaborators).
- **Resource** (REST) → REST-assured / `@RegisterRestClient` IT.

Full order: **Model → DTO → Repository → Service → Resource.**

## Disk / cache hygiene
`mvn clean` wipes `target/`. Local `~/.m2/repository` grows over time — periodic `du -sh ~/.m2` + prune is orchestrator-side, not per-cycle. Native builds + GraalVM are RAM-heavy (watch memory, not disk).
