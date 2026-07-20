---
name: crucible-report-rust
description: Ingest Rust/Cargo test results (nextest JUnit XML + llvm-cov lcov) and compile errors (rustc parser) to Crucible. Use after every cargo test or check run.
---

# Crucible Report — Rust / Cargo

`clients/rust-crucible.py` is the CLI client — it runs cargo AND ingests to the
Crucible v2 API in one call under your agent id. The urllib helpers below are
the direct-call fallback. The agent MUST pass its own agent ID explicitly — no
shell env vars for identity.

> **MANDATORY for RED/GREEN/regression cycle runs:** run the tests **through
> `rust-crucible.py`** (`test` for a targeted cycle, `regression-ingest` for the
> coverage gate). Do NOT invoke `cargo nextest` directly for a cycle run and
> then hand-ingest; that's the fallback only for edge cases.

## Workflow context (env convention)

Every ingest is stamped with its `tier` (`unit` for targeted runs,
`regression` for the coverage gate) and workflow context read from the
environment — set these on every call so runs land on the right cycle:

| Env var | Meaning |
|---------|---------|
| `WORKFLOW_CYCLE_ID` | Numeric cycle id → `context.cycleId` |
| `WORKFLOW_CYCLE` | Cycle label string → `context.cycle` |
| `WORKFLOW_WAVE` | Optional wave number |
| `WORKFLOW_ROLE` | Optional role/track label |

## Usage — the client, that's it

### Lifecycle

```bash
python3 clients/rust-crucible.py register --agent red-nai-042 --phase RED
# ... work ...
python3 clients/rust-crucible.py unregister --agent red-nai-042
```

### 1. After/for any targeted run (RED / GREEN / FIX — tier: unit)

```bash
WORKFLOW_CYCLE_ID=7 WORKFLOW_CYCLE="my cycle label" \
python3 clients/rust-crucible.py test --crate nai_runtime --agent red-nai-042
```

Runs `cargo nextest run -p <crate>` and ingests the JUnit XML. If you already
ran the tests yourself, `auto-ingest` detects: JUnit XML exists → ingest as
tests; no XML → capture `cargo check` stderr → ingest as rustc compile errors:

```bash
python3 clients/rust-crucible.py auto-ingest --agent red-nai-042 --crate nai_runtime
```

RED agents with compile failures get their errors tracked correctly.

### 2. After a full regression (VERIFY / post-merge / orchestrator — tier: regression)

```bash
WORKFLOW_CYCLE_ID=7 WORKFLOW_CYCLE="my cycle label" \
python3 clients/rust-crucible.py regression-ingest --agent vd-orchestrator --crates nai_ast,nai_runtime
```

Runs: clean → `cargo llvm-cov nextest` → parse JUnit + lcov → ingest tests +
coverage in one `POST /api/v2/runs/parsed`.

### 3. Compile-only gates

```bash
python3 clients/rust-crucible.py check --crate nai_runtime --agent green-nai-017
```

Runs `cargo check` and ingests stderr as rustc compile errors when it fails.

### Quick Reference

| When | Call | What it does |
|------|------|-------------|
| RED agent wrote tests | `test` / `auto-ingest` | Compile failure → rustc ingest, else junit |
| GREEN agent made tests pass | `test` / `auto-ingest` | Finds JUnit XML → junit ingest |
| FIX agent applied fixes | `test` / `auto-ingest` | Finds JUnit XML → junit ingest |
| VERIFY / post-merge | `regression-ingest` | Clean + coverage + parsed ingest |

---

## Manual Patterns (fallback only — prefer the client above)

```python
import json, urllib.request

def _read_env(env_path="/home/antonyj/Documents/data_projects/nai/.env"):
    env = {}
    with open(env_path) as f:
        for line in f:
            if "=" in line:
                k, v = line.strip().split("=", 1)
                env[k] = v
    return env

def _post(path, payload):
    req = urllib.request.Request(f"http://localhost:3849{path}",
        data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req).read())

def crucible_register(agent_id, phase="RED"):
    """Register agent with Crucible. Call FIRST before any work."""
    env = _read_env()
    return _post("/api/v2/agents/register",
        {"agentId": agent_id, "projectKey": env["CRUCIBLE_PROJECT_KEY"],
         "status": "online", "message": f"Starting {phase} phase",
         "identity": {"displayName": f"{phase} {agent_id}", "source": "claude-code"}})

def crucible_unregister(agent_id):
    """Unregister agent from Crucible. Call LAST before session ends."""
    env = _read_env()
    return _post("/api/v2/agents/unregister",
        {"agentId": agent_id, "projectKey": env["CRUCIBLE_PROJECT_KEY"]})

def crucible_ingest_junit(agent_id, junit_path):
    """Ingest JUnit XML test results (from cargo nextest)."""
    env = _read_env()
    return _post("/api/v2/runs",
        {"projectKey": env["CRUCIBLE_PROJECT_KEY"], "codec": "junit",
         "dataPath": junit_path, "agentId": agent_id, "tier": "unit"})

def crucible_ingest_rustc(agent_id, rustc_output_path):
    """Ingest Rust compiler errors with format=rustc."""
    env = _read_env()
    with open(rustc_output_path) as f:
        errors_text = f.read()
    return _post("/api/v2/runs/compile",
        {"projectKey": env["CRUCIBLE_PROJECT_KEY"], "format": "rustc",
         "errors": errors_text, "agentId": agent_id})

def crucible_ingest_parsed(agent_id, summary, tree, coverage=None):
    """Ingest pre-parsed results with optional coverage (regression runs with lcov)."""
    env = _read_env()
    payload = {"projectKey": env["CRUCIBLE_PROJECT_KEY"], "agentId": agent_id,
               "summary": summary, "tree": tree, "tier": "regression"}
    if coverage:
        payload["coverage"] = coverage
    return _post("/api/v2/runs/parsed", payload)
```

## Report Locations

| Artifact | Path | Generated by |
|----------|------|-------------|
| JUnit XML | `target/nextest/default/junit.xml` | `cargo nextest run` |
| JUnit XML (CI) | `target/nextest/ci/junit.xml` | `cargo nextest run -P ci` |
| lcov coverage | `target/lcov.info` | `cargo llvm-cov nextest --lcov` |
| Compiler output | `/tmp/rustc-output.txt` | `cargo check 2>&1 > /tmp/rustc-output.txt` |

## Rules

- **Every test run gets ingested** — RED, GREEN, regression, compile failure
- **Register before first ingest, unregister when done** — between runs, ingest is the heartbeat; no ping loop
- **Use the client (or Python urllib) for ALL Crucible calls** — not bash curl
- **Pass agent id explicitly** — never rely on env vars for agent identity
- **Endpoint routing is mandatory — use the RIGHT endpoint for each scenario:**
  - **Tests didn't compile** → `/api/v2/runs/compile` with `format: "rustc"` and `errors` (raw stderr). Shows in the **compile panel**. No tests ran, so there are no test results to report.
  - **Tests compiled and ran** (pass or fail) → `/api/v2/runs` with `codec: "junit"` and JUnit XML. Shows in the **test results panel**. Even if all tests fail, they still ran — report them as test results, NOT compile errors.
  - **NEVER send test results to `/api/v2/runs/compile`** — that panel is for compiler errors only
  - **NEVER send compile errors to `/api/v2/runs`** — 0/N test results are logically inconsistent when tests never ran
  - `auto-ingest` handles this automatically: JUnit XML exists → `/api/v2/runs`, no XML → `/api/v2/runs/compile`
- **Coverage ONLY on full green regression** — ingest coverage ONLY when ALL tests across ALL crates pass (zero failures). Even 1 failure in 1 crate = no coverage; the server also discards coverage on failing runs as a safety net.
- **Read the responses** — every JSON reply carries `help` hints; GETs also serve compact TOON (`?fmt=toon` or `Accept: text/toon`) for cheap reads.

## API Endpoint Reference

| Endpoint | Method | When to use |
|----------|--------|-------------|
| `/api/v2/runs` | POST | Tests compiled and ran (pass or fail) — codec + data or dataPath |
| `/api/v2/runs/parsed` | POST | Pre-parsed results with optional coverage (regression runs; accepts tier/stack/context) |
| `/api/v2/runs/compile` | POST | Tests FAILED TO COMPILE — compiler errors only (format: "rustc") |
| `/api/v2/agents/register` | POST | Register/touch agent (upsert) |
| `/api/v2/agents/unregister` | POST | Unregister agent (requires agentId + projectKey) |
| `/api/v2/agents` | GET | List agents (optional ?project filter) |
| `/api/v2/events` | GET | List events (optional ?project, ?limit) |
| `/api/v2/projects` | GET/POST | List / create projects |
