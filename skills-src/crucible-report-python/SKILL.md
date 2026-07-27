---
name: crucible-report-python
description: Ingest Python test results (pytest/unittest → JUnit XML + coverage.py) and import/syntax errors to Crucible. Use after every Python test run — RED, GREEN, or regression.
metadata:
  author: Crucible
  version: 0.1.0
---

# Crucible Report — Python

Python parallel of `crucible-report-rust` / `crucible-report-bun`. Tests run via **pytest** (or
unittest) producing **JUnit XML**; coverage via **coverage.py**. `clients/python-crucible.py`
is the CLI client (modelled on `rust-crucible.py`); the urllib helpers below are the direct-call
fallback. All Crucible calls use Python `urllib`. Pass the agent ID and the project `.env` path
explicitly — no shell env vars for identity.

> **MANDATORY for RED/GREEN/regression cycle runs:** run the tests **through
> `python-crucible.py`** (`test` for a targeted cycle, `regression` for the gate) — it runs the
> tests AND ingests in ONE call under your agent id. Do NOT invoke `pytest`/`unittest` directly
> for a cycle run and then hand-ingest; that's the fallback (§B) only for edge cases.

## Workflow context (env convention)

Every ingest is stamped with its `tier` (`unit` for `test`, `regression` for the gate) and
workflow context read from the environment:

| Env var | Meaning |
|---------|---------|
| `WORKFLOW_CYCLE` | Cycle label string → `context.cycle` |
| `WORKFLOW_WAVE` | Optional wave number |
| `WORKFLOW_ROLE` | Optional role/track label |

## Two ways to run + ingest

### A. `python-crucible.py` (preferred — handles register + JUnit XML + ingest in one call)
```bash
VENV=$PWD/.venv/bin/python
# register / unregister the agent
python3 clients/python-crucible.py register --agent CR-OA-002-A-RED --phase RED --project-dir $PWD
# targeted RED/GREEN run + ingest (dotted test path; tier: unit)
WORKFLOW_CYCLE="my cycle label" PY_CRUCIBLE_PYTHON=$VENV \
python3 clients/python-crucible.py test --tests tests.test_mongo_connection --agent CR-OA-002-A-RED --project-dir $PWD
# full regression + coverage.py (orchestrator gate; tier: regression)
WORKFLOW_CYCLE="my cycle label" PY_CRUCIBLE_PYTHON=$VENV \
python3 clients/python-crucible.py regression --coverage --agent verify-office-assistant --project-dir $PWD
# syntax gate (py_compile → /api/v2/runs/compile)
python3 clients/python-crucible.py check
# ingest an already-produced reports dir
python3 clients/python-crucible.py auto-ingest --agent CR-OA-002-A-RED --project-dir $PWD
```
The script reads `CRUCIBLE_PROJECT_KEY` from `<project-dir>/.env`.

### B. pytest → JUnit XML → ingest (when you want pytest explicitly)
```bash
.venv/bin/pytest tests/test_x.py --junitxml=test-reports/junit.xml -q
# then ingest (helper below):  crucible_ingest_junit("CR-OA-002-A-RED", ENV, "test-reports/junit.xml")
```

## Helper functions (urllib — copy into one Python call)

```python
import json, os, urllib.request

def _read_env(env_path):
    env = {}
    with open(env_path) as f:
        for line in f:
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.strip().split("=", 1); env[k] = v
    return env

def _post(path, payload):
    req = urllib.request.Request(f"http://localhost:3849{path}",
        data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req).read())

def crucible_register(agent_id, env_path, phase="RED"):
    env = _read_env(env_path)
    return _post("/api/v2/agents/register",
        {"agentId": agent_id, "projectKey": env["CRUCIBLE_PROJECT_KEY"], "status": "online",
         "message": f"Starting {phase}",
         "identity": {"displayName": f"{phase} {agent_id}", "source": "claude-code"}})

def crucible_unregister(agent_id, env_path):
    env = _read_env(env_path)
    return _post("/api/v2/agents/unregister",
        {"agentId": agent_id, "projectKey": env["CRUCIBLE_PROJECT_KEY"]})

def crucible_ingest_junit(agent_id, env_path, junit_path):
    """Tests RAN (pass or fail) → /api/v2/runs, codec junit."""
    env = _read_env(env_path)
    resp = _post("/api/v2/runs",
        {"projectKey": env["CRUCIBLE_PROJECT_KEY"], "codec": "junit",
         "dataPath": os.path.abspath(junit_path), "agentId": agent_id, "tier": "unit"})
    s = resp.get("summary", {})
    print(f"ingest junit: ok={resp.get('ok')} passed={s.get('passed')} failed={s.get('failed')} total={s.get('total')}")
    return resp

def crucible_ingest_compile(agent_id, env_path, errors_text):
    """Tests FAILED TO IMPORT/COMPILE (no tests ran) → /api/v2/runs/compile, format python."""
    env = _read_env(env_path)
    return _post("/api/v2/runs/compile",
        {"projectKey": env["CRUCIBLE_PROJECT_KEY"], "format": "python",
         "errors": errors_text, "agentId": agent_id})

def crucible_ingest_parsed(agent_id, env_path, summary, tree, coverage=None):
    env = _read_env(env_path)
    payload = {"projectKey": env["CRUCIBLE_PROJECT_KEY"], "agentId": agent_id,
               "summary": summary, "tree": tree}
    if coverage: payload["coverage"] = coverage
    return _post("/api/v2/runs/parsed", payload)

def crucible_auto_ingest(agent_id, env_path, junit_path="test-reports/junit.xml"):
    """RED/GREEN/FIX: fresh JUnit XML → ingest junit; else the run never produced XML
    (collection/import error) → ingest the captured stderr as a python compile error."""
    if os.path.exists(junit_path) and os.path.getsize(junit_path) > 0:
        return crucible_ingest_junit(agent_id, env_path, junit_path)
    err = ""
    if os.path.exists("/tmp/pytest-collect.txt"):
        err = open("/tmp/pytest-collect.txt").read()
    return crucible_ingest_compile(agent_id, env_path, err or "no JUnit XML produced (collection error)")
```

## Endpoint routing (same discipline as the rust skill)
- **Tests ran** (pass OR fail) → `/api/v2/runs` `codec:"junit"` + `dataPath`. Test panel. Even an all-fail RED that *ran* is junit, not compile.
- **Import / syntax failure** (no tests ran) → `/api/v2/runs/compile` `format:"python"` + `errors` (py_compile / pytest collection stderr). Compile panel. In Python most RED import errors still surface as junit `<error>` entries at collection time → those are junit.
- **NEVER** send test results to `/api/v2/runs/compile`, or compile errors to `/api/v2/runs`.
- **Coverage ONLY on a full green regression** — `coverage run -m pytest … && coverage lcov -o test-reports/coverage.lcov`, parse LF/LH/FNF/FNH, ingest via `/api/v2/runs/parsed` with `coverage`. Any failure ⇒ no coverage (the server also discards it as a safety net).

## RED / GREEN / regression usage
```python
ENV = "/home/antonyj/Documents/side_projects/office_assistant/.env"
crucible_register("CR-OA-002-A-RED", ENV, "RED")
# ... run: .venv/bin/pytest tests/test_x.py --junitxml=test-reports/junit.xml (RED must fail)
crucible_auto_ingest("CR-OA-002-A-RED", ENV)          # ingest the RED run
# GREEN agent implements; re-run pytest → junit.xml; crucible_auto_ingest("CR-OA-002-A-GREEN", ENV)
crucible_unregister("CR-OA-002-A-RED", ENV)
```

## Rules
- **Every run ingested** — RED, GREEN, regression, import error. An unreported RED reads as "skipped TDD".
- **Register before first ingest, unregister when done.** Between runs, ingest is the heartbeat — no ping loop.
- **urllib for all Crucible calls** (never bash `curl`); pass `agent_id` + `.env` path explicitly.
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
