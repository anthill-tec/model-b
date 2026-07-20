---
name: bun-red-testing
description: TDD RED phase for Bun/TypeScript — write a failing test, run it targeted, verify failure. Use after writing a new test that should fail before implementation.
---

# Bun RED Testing

Write a failing test → run targeted → verify failure → ingest RED (see `crucible-report` skill).

## Test Command

```bash
bun test src/tools/__tests__/MY_TEST.test.ts
```

- Run ONLY the test file you wrote/changed — never the full suite
- Use `--filter "pattern"` to narrow further if needed

## Expected Outcome

- **Test MUST FAIL** — if it passes, the test is wrong (not testing new behavior)
- Verify the failure message matches what you expect

## Test Patterns

### Basic Test Structure

```typescript
import { describe, it, expect, beforeEach } from "bun:test";

describe("MyModule", () => {
  let sut: MyModule;

  beforeEach(() => {
    sut = new MyModule();
  });

  it("should do something specific", () => {
    const result = sut.doSomething("input");
    expect(result).toEqual("expected");
  });
});
```

### Async Tests

```typescript
it("should handle async operations", async () => {
  const result = await sut.fetchData();
  expect(result).toBeDefined();
  expect(result.status).toBe("ok");
});
```

### Error Assertions

```typescript
it("should throw on invalid input", () => {
  expect(() => sut.process(null)).toThrow("Input required");
});
```

## Rules

- **No implementation yet** — RED phase is test-only
- **Never skip ingest** — read the `crucible-report` skill for Bun ingest commands
- **One behavior per test** — don't bundle multiple assertions testing different behaviors
