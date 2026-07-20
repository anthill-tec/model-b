---
name: bun-green-testing
description: TDD GREEN phase for Bun/TypeScript — implement production code, run targeted test, verify pass. Use after RED phase when implementing to make a failing test pass.
---

# Bun GREEN Testing

Implement production code → run targeted test → verify pass → ingest GREEN (see `crucible-report` skill).

## Test Command

```bash
bun test src/tools/__tests__/MY_TEST.test.ts
```

- Run ONLY the test file from the RED phase — same scope
- Use `--filter "pattern"` to narrow further if needed

## Expected Outcome

- **Test MUST PASS** — if it fails, fix implementation (not the test)
- All assertions green, no errors

## Implementation Patterns

### Module Exports

```typescript
export function myFunction(input: string): Result {
  // minimal implementation to pass the test
  return { status: "ok", data: input };
}
```

### Class-Based

```typescript
export class MyService {
  constructor(private readonly dep: Dependency) {}

  process(input: string): Output {
    const raw = this.dep.fetch(input);
    return this.transform(raw);
  }

  private transform(raw: RawData): Output {
    // ...
  }
}
```

### Zod Schemas (for MCP tools)

```typescript
import { z } from "zod";

export const MyInputSchema = z.object({
  name: z.string().describe("Human-readable name"),
  count: z.number().int().positive().describe("Item count"),
}).describe("Input for my tool");
```

## Rules

- **Don't modify the test** — if it fails, the implementation is wrong
- **Never skip ingest** — read the `crucible-report` skill for Bun ingest commands
- **Minimal implementation** — write just enough to make the test pass, no more
