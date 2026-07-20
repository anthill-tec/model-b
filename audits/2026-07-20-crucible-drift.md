# Audit — Crucible/worktree tooling doc-vs-code drift (2026-07-20)

Scope: 13 scripts in `~/.claude/scripts/` vs 19 doc files (crucible + report skills, agent-protocol, code-health, bootstrap/shutdown, orchestration memory).
Live-verified 2026-07-20 against Crucible on `localhost:3849`: `/api/v2/plans` 200 (TOON via `?fmt=toon`), `/api/v2/agents` 200, `/api/v2/agents/heartbeat` 404, `/api/ingest/parsed` 404, GET `/api/v2/runs` 404 (POST-only).

## Actual CLI surfaces
- **rust-crucible.py** — register/unregister, auto-ingest, regression-ingest --crates, test --crate/--test/--filter/--profile/--no-fail-fast, check --crate, clippy [--deny-warnings], workspace-clippy, workspace-regression [--all-features], smoke-test, docker-up/down, pre-merge-gate, docker-e2e-gate. Endpoints /api/v2/{agents/register|unregister, runs, runs/parsed, runs/compile(rustc)}. Owns gate-lock file. Plain-text one-liners; NO envelope.
- **mvn-crucible.py** — register/unregister, unit --test/--module, module, compile, e2e, regression, auto-ingest, docker-up/down, pre-merge-gate. Same v2 endpoints (compile format `java`). Plain text.
- **bun-crucible.py** — register/unregister, test --tests, regression [--coverage], auto-ingest, check (tsc), pre-merge-gate, PLUS plan verbs unique to bun: plan-file --cr/--title/--cycles, cycle-activate, cycle-done, cr-close --commit → Crucible plans/cycles API (GET/POST /plans, PATCH /plans/<id>/cycles/<id>). Plain text. **REFERENCE IMPLEMENTATION for V2 client API (decision 11).**
- **python-crucible.py** — register/unregister, test --tests (dotted), regression [--coverage --cov-source], auto-ingest, check (py_compile), pre-merge-gate. Plain text.
- **arduino-crucible.py** — ONLY unit, compile, register, unregister. `CRUCIBLE_URL` (legacy alias `CRUCIBLE_BASE`).
- **hw-crucible.py** — 21-line shim → `anthill_forge.shared.crucible.main` (`forge crucible unit|ingest|register|unregister`).
- **worktree-flow.py** — start, status, sync, finish, abort, cs, show, progress, next, reconcile. State git-derived + optional schedule_db ChangeSet DB. Plain-text boards; finish/next print next-step lines.
- **rust-code-health.py** — snapshot --phase {baseline|pre|post|adhoc} [--slice]; query {trend|crate|delta|ledger}; ledger {assign|sync} --domain {cull|temporal|<name>}.
- **rust-dead-scan.py** — modes: inventory pub-scan deps reconcile boundaries **hot-path** (hot-path undocumented in code-health skill).
- **gate-lock.sh** — acquire, wait-acquire, wait-free, release, status, check, force-release; --cr --track --freq --max --reason; exit 5 = timeout.
- **schedule_db.py** — NOT a CLI; SQLite ChangeSet library imported by worktree-flow. States DRAFT|PENDING|IN_PROGRESS|COMPLETED|ABORTED|SUPERSEDED.
- **vscode** — NO client exists; `crucible-report-vscode` skill hand-rolls inline urllib ingest (violates the "never hand-roll" rule).

## Drift table (doc → claim → actual)
| Doc | Claim | Actual | Severity |
|---|---|---|---|
| skills/crucible | clients print TOON-AXI envelope `{axi:{verb,ok,…,warnings[]}}` with `help` | clients print plain text; TOON/`help` exist only server-side (GET `?fmt=toon`) | HEADLINE — resolved by upgrading clients (decision 7/11) |
| skills/crucible | universal verbs register · test --tests · regression --coverage · check · auto-ingest | rust: regression-ingest/workspace-regression, test --crate; java: unit/module/compile/e2e, no --coverage; arduino: unit/compile only | wrong/renamed |
| skills/crucible | plan verbs general | bun-only today | wrong scope (now: promote to all, decision 11) |
| skills/agent-protocol | POST /api/v2/agents/heartbeat | endpoint 404 (verified live); heartbeat = the register verb | phantom endpoint |
| skills/agent-protocol | scripts/heartbeat.sh | does not exist | missing |
| memory/java-orchestration | /api/ingest/parsed, /api/ingest/compile (×4) | /api/v2/runs/parsed, /api/v2/runs/compile (old paths 404 verified) | stale endpoints |
| crucible-report-rust | — | omits clippy/workspace-clippy/smoke-test/workspace-regression/docker-*/gates | undocumented |
| crucible-report-bun | — | plan/cycle verbs + plans API undocumented | undocumented |
| code-health skill | dead-scan modes list | omits `hot-path`; ledger treated cull-only (multi-domain exists) | undocumented |

## worktree-flow single- vs multi-track
No hard mode switch. A "track" is a lane label (`--track` / `$WF_TRACK`) stamped at `start`, mirrored to the ChangeSet DB `track` field with per-lane `seq`. No-track = queue-only. `next` → NEXT/HOLD/DRAINED. `status` renders two boards (git worktrees + DB lane plan). DB optional — degrades to pure-git. Docs (orchestration-track/mainline, bootstrap, code-health, sandesh) all consistent with this.

## AXI conformance today
- Clients: non-interactive, deterministic (AXI-adjacent) but NOT AXI-output.
- worktree-flow: closest to next-step behavior; plain text → migrate to envelope (decision 11).
- gate-lock.sh: exit-code contract + guidance; AXI-ish.
- health trio: structured JSON, no envelope.
- TOON exists only server-side; report skills document that correctly — top-level crucible skill is the drift source.
