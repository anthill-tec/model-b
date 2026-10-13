---
name: crucible-report-python
description: Ingest Python test results (pytest/unittest → JUnit XML + coverage.py) and import/syntax errors to Crucible. Use after every Python test run — RED, GREEN, or regression.
metadata:
  author: Crucible
  version: 0.1.0
---

# Crucible Report — Python

Python parallel of `crucible-report-rust` / `crucible-report-bun`. Tests run via **pytest** (or
unittest) producing **JUnit XML**; coverage via **coverage.py**. `~/.crucible/clients/python-crucible.py`
is the CLI client (modelled on `rust-crucible.py`); every Crucible call goes through it. Pass the
agent ID and the project `.env` path explicitly — no shell env vars for identity.

That path is the default location of Crucible's installed clients: the client
is listed in `~/.crucible/crucible-clients.json` and installed by Crucible's own
installer, and it is not shipped, vendored or maintained by Model B.

> **MANDATORY for RED/GREEN/regression cycle runs:** run the tests **through
> `python-crucible.py`** (`test` for a targeted cycle, `regression` for the gate) — it runs the
> tests AND ingests in ONE call under your agent id. Do NOT invoke `pytest`/`unittest` directly
> for a cycle run and then hand-ingest.

## Workflow context (env convention)

Every ingest is stamped with its `tier` (`unit` for `test`, `regression` for the gate) and
workflow context read from the environment:

| Env var | Meaning |
|---------|---------|
| `WORKFLOW_CYCLE` | Cycle label string → `context.cycle` |
| `WORKFLOW_WAVE` | Optional wave number |
| `WORKFLOW_ROLE` | Optional role/track label |

## Run + ingest through `python-crucible.py`

The client handles register + JUnit XML + ingest in one call.
```bash
VENV=$PWD/.venv/bin/python
# register / unregister the agent
python3 ~/.crucible/clients/python-crucible.py register --agent CR-OA-002-A-RED --role RED --cycle <cycleId> --project-dir $PWD
# targeted RED/GREEN run + ingest (dotted test path; tier: unit)
WORKFLOW_CYCLE="my cycle label" PY_CRUCIBLE_PYTHON=$VENV \
python3 ~/.crucible/clients/python-crucible.py test --tests tests.test_mongo_connection --agent CR-OA-002-A-RED --project-dir $PWD
# full regression + coverage.py (orchestrator gate; tier: regression)
WORKFLOW_CYCLE="my cycle label" PY_CRUCIBLE_PYTHON=$VENV \
python3 ~/.crucible/clients/python-crucible.py regression --coverage --agent verify-office-assistant --project-dir $PWD
# syntax gate (py_compile → /api/v2/runs/compile)
python3 ~/.crucible/clients/python-crucible.py check
# recovery only: re-ingest the report a client run produced when that run's ingest failed
python3 ~/.crucible/clients/python-crucible.py auto-ingest --agent CR-OA-002-A-RED --project-dir $PWD
```
The script reads `CRUCIBLE_PROJECT_KEY` from `<project-dir>/.env`.

`auto-ingest` is recovery only: it re-ingests the report a client run produced when that run's
own ingest failed. It is not a run path.

## Endpoint routing (same discipline as the rust skill)
- **Tests ran** (pass OR fail) → `/api/v2/runs` `codec:"junit"` + `dataPath`. Test panel. Even an all-fail RED that *ran* is junit, not compile.
- **Import / syntax failure** (no tests ran) → `/api/v2/runs/compile` `format:"python"` + `errors` (py_compile / pytest collection stderr). Compile panel. In Python most RED import errors still surface as junit `<error>` entries at collection time → those are junit.
- **NEVER** send test results to `/api/v2/runs/compile`, or compile errors to `/api/v2/runs`.
- **Coverage ONLY on a full green regression** — `regression --coverage` measures it and ingests it via `/api/v2/runs/parsed` with `coverage`. Any failure ⇒ no coverage (the server also discards it as a safety net).

## Rules
- **Every run ingested** — RED, GREEN, regression, import error. An unreported RED reads as "skipped TDD".
- **Register before first ingest, unregister when done.** Between runs, ingest is the heartbeat — no ping loop.
- **The client for all Crucible calls** (never a hand-made HTTP call); pass the agent id + `--project-dir` explicitly.
- Agent naming: `CR-<PROJ>-NNN-<cycle>-<PHASE>` (e.g. `CR-OA-002-A-RED`) for phase agents; `<type>-<project>` for the orchestrator.
- Responses carry `help` hints; GETs also serve compact TOON (`?fmt=toon`).

## API endpoint reference
| Endpoint | Method | When |
|---|---|---|
| `/api/v2/runs` | POST | tests ran (pass/fail) — `codec:junit` + `dataPath` |
| `/api/v2/runs/parsed` | POST | pre-parsed results + optional coverage (regression) |
| `/api/v2/runs/compile` | POST | import/syntax failure — `format:python` + `errors` |
| `/api/v2/agents/register` | POST | register/touch (upsert; ingest is the heartbeat afterwards) |
| `/api/v2/agents/unregister` | POST | unregister |
| `/api/v2/projects` | GET/POST | list projects / create one (POST with `name`) |
