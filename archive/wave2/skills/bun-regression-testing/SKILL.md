---
name: bun-regression-testing
description: Full regression gate for Bun/TypeScript — run entire test suite with coverage, verify zero failures. Use as final gate before merge or after all implementation steps complete.
---

# Bun Regression Testing

Run full suite with coverage → verify all green → ingest with coverage (see `crucible-report` skill).

## Test Command

```bash
bun test --coverage 2>&1 | tail -20
```

## Expected Outcome

- **ALL tests pass** — zero failures, zero errors
- **Test count ≥ previous** — no tests deleted
- **No skipped tests** introduced
- **Coverage generated** at `coverage/lcov.info`

## What To Check

### Test Output

```
XX pass
0 fail
```

- Any failure = STOP, do not merge
- Report the total test count in your completion message

### Common Regression Issues

| Symptom | Likely Cause |
|---------|-------------|
| Port already in use | Another test instance running — wait or kill it |
| Module not found | Missing import or build artifact |
| Flaky timeout | Increase timeout in test, check async handling |
| Snapshot mismatch | Update snapshots if change is intentional: `bun test --update-snapshots` |

## Ingest

Read the `crucible-report` skill → Bun → Regression Run section for the exact ingest commands (test results + lcov coverage).

## Gate Criteria

- All tests pass — any failure = STOP, do not merge
- Coverage ingested to Crucible
- No new warnings in build output
- Report total test count in your completion message

## Prohibited

- Merging with any test failure
- Deleting or skipping tests to make regression pass
- Skipping coverage ingest
