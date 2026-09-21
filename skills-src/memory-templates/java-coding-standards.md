<!-- Model B memory template (cross-project Java language reference). Imported 2026-09-21 from the user's global memory (java-coding-standards.md) by ruling: PRD §D5's global tier has no Pi home, so language refs ride the stack's memory templates and are scaffolded into <project>/docs/memory/. -->

# Java Coding Standards

## Code Formatting Rules (NON-NEGOTIABLE - HIGH PRIORITY)

### Import Usage (CRITICAL)
**NEVER use full namespace declarations in Java code**

```java
// ❌ WRONG - Full namespace
org.fourpm.entitystore.dto.BusinessEntityDto dto;

// ✅ CORRECT - Import and use short name
import org.fourpm.entitystore.dto.BusinessEntityDto;
...
BusinessEntityDto dto;
```

**Applies to:**
- Field declarations
- Variable declarations
- Method parameters
- Return types
- Generic types

**NO EXCEPTIONS** - This is a code quality standard

### Unused Imports (CRITICAL - BEFORE EVERY COMMIT)

**Workflow:**
1. Complete TDD RED/GREEN cycle
2. **Remove ALL unused imports** from modified classes
3. **Run tests AGAIN** to catch any mistakes
4. Check compiler warnings and IDE diagnostics
5. Git commit (only if tests still GREEN)

**NO EXCEPTIONS** - This is a code quality standard

### Lambda Parameters

**Rule:** Rename unused lambda parameters to `_` (underscore)

**Rationale:**
- Java compiler warns about unused variables, accepts `_` as intentional placeholder
- Signals "parameter exists for signature matching but is intentionally unused"
- Java 21+ JEP 443 (Unnamed Patterns and Variables) officially supports `_`

**Examples:**

```java
// ❌ BAD - Unused parameter triggers compiler warning
connectorInfoService.deleteVersion(id)
    .map(deleted -> Response.noContent().build());

// ✅ GOOD - Underscore signals intentional non-use
connectorInfoService.deleteVersion(id)
    .map(_ -> Response.noContent().build());

// ❌ BAD - Unused 'throwable' parameter
.onFailure().recoverWithItem(throwable ->
    Response.status(500).entity("Error").build()
);

// ✅ GOOD - Only if throwable is truly unused
.onFailure().recoverWithItem(_ ->
    Response.status(500).entity("Generic error").build()
);

// ✅ BEST - Use the parameter if it provides value
.onFailure().recoverWithItem(throwable ->
    Response.status(500).entity(throwable.getMessage()).build()
);
```

**When to Apply:**
- Lambda returns constant value (e.g., `_ -> Response.noContent().build()`)
- Signature requires parameter but logic doesn't need it (e.g., `forEach(_ -> counter++)`)
- Stream operations where element is unused (e.g., `stream.filter(_ -> condition)`)

**When NOT to Apply:**
- Parameter is actually used in lambda body
- Parameter provides debugging/logging value (keep meaningful name)

## Java Version and Features

### Required Version
- Use **Java 21+** features in all codebases
- Use **Java 23** syntax and features for better readability
- Ensure Maven compiler and JDK set to correct Java version in every project

### Modern Java Features to Use
- Records for simple DTO objects
- Pattern matching
- Switch expressions
- Text blocks
- Sealed classes where appropriate

## Data Transfer Objects (DTOs)

### Use Java Records
```java
// ✅ CORRECT - Use record for simple DTOs
public record EntityDto(
    Long id,
    String name,
    String description
) {}

// ❌ AVOID - Traditional class for simple DTOs
public class EntityDto {
    private Long id;
    private String name;
    // ... getters, setters, equals, hashCode
}
```

## Code Organization

### Field Declarations
Never use full namespace in field declarations:

```java
// ❌ WRONG
private org.example.service.UserService userService;

// ✅ CORRECT
import org.example.service.UserService;
...
private UserService userService;
```

### Generic Types
```java
// ❌ WRONG
List<org.example.dto.UserDto> users;

// ✅ CORRECT
import org.example.dto.UserDto;
...
List<UserDto> users;
```

## Logging Best Practices

### Use Appropriate Log Levels
Use specific logging methods instead of generic `log()`:
- `debug()` - Detailed diagnostic information
- `info()` - General informational messages
- `warn()` - Warning messages for potentially harmful situations
- `error()` - Error events that might still allow app to continue

Easier to filter on browser side in JavaScript/TypeScript Bun/Node.js apps.

## Error Handling & Warnings (NON-NEGOTIABLE)

- **No empty catch blocks.** A swallowed exception hides failures — at minimum log it; preferably handle or rethrow.
- **No suppressed warnings without justification.** `@SuppressWarnings(...)` requires a comment stating why; never blanket-suppress to silence the compiler.
- **No dead code / commented-out code.** Delete it — git history is the archive.

## Naming Conventions

- Follow Java naming strictly: **`camelCase` methods/fields, `PascalCase` classes/records/enums, `UPPER_SNAKE_CASE` constants.**
- Meaningful variable names — no single-letter names outside tight loop indices/lambda params.
- Test method names are descriptive: `methodName_scenario_expectedResult` (or equivalent). Vague names (`test1`, `testIt`) are not acceptable — see java-testing-practices.md "Reviewer checklist".

## MongoDB Entity Annotations

### @BsonProperty Safety
**NEVER use empty `@BsonProperty()`** - causes `NullPointerException` in `BasePanacheMongoResourceProcessor`

```java
// ❌ WRONG - Empty annotation causes NPE
@BsonProperty()
private String fieldName;

// ✅ CORRECT - Explicit field name
@BsonProperty("FieldName")
private String fieldName;

// ✅ CORRECT - Remove annotation if not needed
private String fieldName;
```

## Compilation and Build

### Maven Clean Build
**CRITICAL:** Always run `./mvnw clean compile` before committing

**Why:**
- Incremental builds with "Nothing to compile" can hide breaking changes
- Uses stale cached class files
- Clean build exposes compilation errors from removed/refactored methods

**Workflow:**
1. Make code changes
2. Run `./mvnw clean compile` (not just `compile`)
3. Verify no compilation errors
4. Run tests
5. Commit if GREEN

### Occasional Clean Compile
Run `./mvnw clean compile` periodically during development - Maven compiler caching can become stale

## Never Commit Failed State

### TDD Discipline
**NEVER commit in RED state:**
1. ✅ Run test → verify GREEN
2. ✅ Remove unused imports
3. ✅ Run test AGAIN → verify still GREEN
4. ✅ Git commit

**Rationale:**
- Breaks project development flow in multi-developer environment
- CI/CD pipelines fail
- Wastes other developers' time

### Compilation Check
Always verify compilation success before committing:
```bash
./mvnw clean compile
# Verify exit code 0 before git commit
```
