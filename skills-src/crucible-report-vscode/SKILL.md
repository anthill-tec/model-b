---
name: crucible-report-vscode
description: Ingest VS Code extension TypeScript test results (Vitest JUnit XML + Mocha JUnit XML + lcov) to Crucible. Use after every test run — RED, GREEN, or regression.
metadata:
  author: Crucible
  version: 0.1.0
---

# Crucible Report — VS Code Extension / TypeScript

There is no `*-crucible.py` CLI client for this stack — this skill posts
directly to the Crucible v2 API (`POST /api/v2/runs/parsed` for results,
`POST /api/v2/runs/compile` for build failures).

## Workflow context (tier + env convention)

Stamp every ingest with a `tier` (`unit` for targeted runs, `regression` for
the full-suite gate) and the workflow context, read from the environment:

| Env var | Meaning |
|---------|---------|
| `WORKFLOW_CYCLE` | Cycle label string → `context.cycle` |
| `WORKFLOW_WAVE` | Optional wave number |
| `WORKFLOW_ROLE` | Optional role/track label |

The ingest snippets below read these and attach `tier` + `context` to the
payload.

## Vitest (Unit Tests)

### Targeted Run (RED or GREEN — no coverage; tier: unit)

Vitest has a built-in JUnit reporter. Write to a file, then ingest:

```bash
# Run targeted test with JUnit output
npx vitest run src/test/unit/MY_TEST.test.ts --reporter=junit --outputFile=/tmp/vscode-junit.xml 2>&1 | tail -10
```

Then ingest via Python:

```python
import json, urllib.request, xml.etree.ElementTree as ET, os

env = {}
env_path = os.path.join(os.environ.get("PROJECT_DIR", "."), ".env")
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            if "=" in line: k, v = line.strip().split("=", 1); env[k] = v

def workflow_context():
    ctx = {}
    # No client-side cycle-id plumbing: the active cycle auto-attaches server-side.
    for var, key in [("WORKFLOW_CYCLE", "cycle"), ("WORKFLOW_WAVE", "wave"), ("WORKFLOW_ROLE", "role")]:
        if os.environ.get(var): ctx[key] = os.environ[var]
    return ctx

junit_path = "/tmp/vscode-junit.xml"
tree_nodes = []
total = passed = failed = 0
duration_ms = 0

root = ET.parse(junit_path).getroot()
for suite in root.findall(".//testsuite"):
    suite_name = suite.get("name", "Unknown")
    children = []
    for tc in suite.findall("testcase"):
        tc_name = tc.get("name", "unknown")
        tc_time = int(float(tc.get("time", 0)) * 1000)
        fail = tc.find("failure")
        err = tc.find("error")
        if fail is not None or err is not None:
            status = "fail"
            failed += 1
        else:
            status = "pass"
            passed += 1
        total += 1
        duration_ms += tc_time
        children.append({"name": tc_name, "status": status, "duration_ms": tc_time})
    suite_status = "fail" if any(c["status"] == "fail" for c in children) else "pass"
    tree_nodes.append({"name": suite_name, "status": suite_status, "children": children})

summary = {"total": total, "passed": passed, "failed": failed, "pending": 0, "duration_ms": duration_ms}
payload = {
    "projectKey": env.get("CRUCIBLE_PROJECT_KEY", ""),
    "agentId": "YOUR_AGENT_ID",
    "summary": summary,
    "tree": tree_nodes,
    "tier": "unit",
    "stack": "vscode",
    "context": workflow_context()
}

req = urllib.request.Request("http://localhost:3849/api/v2/runs/parsed",
    data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
resp = urllib.request.urlopen(req)
print(f"Ingested: {total} tests, {passed} passed, {failed} failed")
```

### Regression Run (full suite — with coverage; tier: regression)

```bash
# Run full unit suite with JUnit + coverage
npx vitest run --reporter=junit --outputFile=/tmp/vscode-junit.xml --coverage --coverage.reporter=lcov 2>&1 | tail -20
```

Then ingest with coverage — same JUnit parsing and `workflow_context()` as
above, plus the lcov block, `"tier": "regression"`, and the coverage field:

```python
# Parse lcov coverage
coverage = None
lcov_path = "coverage/lcov.info"
if os.path.exists(lcov_path):
    with open(lcov_path) as f:
        lcov_text = f.read()
    lf = lh = ff = fh = bf = bh = 0
    for line in lcov_text.splitlines():
        if line.startswith("LF:"): lf += int(line[3:])
        elif line.startswith("LH:"): lh += int(line[3:])
        elif line.startswith("FNF:"): ff += int(line[4:])
        elif line.startswith("FNH:"): fh += int(line[4:])
        elif line.startswith("BRF:"): bf += int(line[4:])
        elif line.startswith("BRH:"): bh += int(line[4:])
    coverage = {
        "lines": {"total": lf, "covered": lh, "percent": round(lh / lf * 100, 1) if lf else 0},
        "functions": {"total": ff, "covered": fh, "percent": round(fh / ff * 100, 1) if ff else 0},
        "branches": {"total": bf, "covered": bh, "percent": round(bh / bf * 100, 1) if bf else 0}
    }

payload = {
    "projectKey": env.get("CRUCIBLE_PROJECT_KEY", ""),
    "agentId": "YOUR_AGENT_ID",
    "summary": summary,
    "tree": tree_nodes,
    "tier": "regression",
    "stack": "vscode",
    "context": workflow_context()
}
if coverage:
    payload["coverage"] = coverage

req = urllib.request.Request("http://localhost:3849/api/v2/runs/parsed",
    data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
resp = urllib.request.urlopen(req)
print(f"Ingested: {total} tests, {passed} passed, {failed} failed" +
      (f", coverage: {coverage['lines']['percent']}%" if coverage else ""))
```

## Mocha (Integration Tests — @vscode/test-electron)

### Configuration

Add `mocha-junit-reporter` to devDependencies. Configure in `.vscode-test.mjs` or test runner:

```javascript
// In test runner setup
reporter: 'mocha-junit-reporter',
reporterOptions: {
    mochaFile: '/tmp/vscode-integration-junit.xml',
    outputs: true
}
```

### Ingest

Same Python ingest as above, but read from `/tmp/vscode-integration-junit.xml`.

## Compile Failure Ingest

When `npm run compile` fails (no test results generated):

```python
import json, urllib.request, subprocess, os

env = {}
env_path = os.path.join(os.environ.get("PROJECT_DIR", "."), ".env")
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            if "=" in line: k, v = line.strip().split("=", 1); env[k] = v

result = subprocess.run(["npm", "run", "compile"], capture_output=True, text=True, cwd=os.environ.get("PROJECT_DIR", "."))
errors = result.stderr or result.stdout

payload = {
    "projectKey": env.get("CRUCIBLE_PROJECT_KEY", ""),
    "agentId": "YOUR_AGENT_ID",
    "format": "tsc",
    "errors": errors
}

req = urllib.request.Request("http://localhost:3849/api/v2/runs/compile",
    data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
resp = urllib.request.urlopen(req)
print(f"Ingested compile failure")
```

## Report Locations

| Artifact | Path | Generated by |
|----------|------|-------------|
| Vitest JUnit XML | `/tmp/vscode-junit.xml` | `npx vitest run --reporter=junit` |
| Mocha JUnit XML | `/tmp/vscode-integration-junit.xml` | `mocha-junit-reporter` |
| lcov coverage | `coverage/lcov.info` | `npx vitest run --coverage` |

---

## Event Management

All GETs support compact TOON responses (`?fmt=toon` or `Accept: text/toon`);
JSON responses carry `help` hints.

```bash
# List events
curl -s "http://localhost:3849/api/v2/events?project=PROJECT_KEY_UUID&limit=20"

# Read / delete a single event
curl -s "http://localhost:3849/api/v2/events/EVENT_ID"
curl -s -X DELETE "http://localhost:3849/api/v2/events/EVENT_ID"
```

---

## API Endpoint Reference

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v2/runs` | POST | Ingest raw test data (codec + data or dataPath) |
| `/api/v2/runs/parsed` | POST | Ingest pre-parsed results (summary + tree + optional coverage; accepts tier/stack/context) |
| `/api/v2/runs/compile` | POST | Ingest compile failure (errors string + format) |
| `/api/v2/agents/register` | POST | Register/touch agent (upsert; ingest is the heartbeat afterwards) |
| `/api/v2/agents/unregister` | POST | Unregister agent (requires agentId + projectKey) |
| `/api/v2/agents` | GET | List agents (optional ?project filter) |
| `/api/v2/events` | GET | List events (optional ?project, ?limit) |
| `/api/v2/projects` | GET/POST | List / create projects |

---

## Placeholders

Replace these in all commands:

| Placeholder | Meaning | Example |
|-------------|---------|---------|
| `PROJECT_KEY_UUID` | Crucible project key | `019c9ff7-222f-7ae5-9121-2ae549e4d97a` |
| `PROJECT_DIR` | Absolute path to project root | `/home/antonyj/Documents/data_projects/nai-vscode` |
| `YOUR_AGENT_ID` | Your agent ID from the prompt | `red-vsc-072f3` |

## Rules

- **Never skip ingest** — every test run (RED, GREEN, regression) gets reported
- **Ingest RED and GREEN separately** — Crucible must show the RED→GREEN transition
- **Compile failures get ingested too** — `/api/v2/runs/compile`
- **Coverage ONLY on full green regression** — never on targeted or failed runs (the server also discards coverage on failing runs)
- **Do NOT ingest coverage as a separate call** — `/api/v2/runs/parsed` takes `coverage` in the same payload
- **Always register before first ingest, unregister when done**
- **`displayName` goes inside `identity` object** — top-level displayName is silently ignored
