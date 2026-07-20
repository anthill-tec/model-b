# Stack Detection — Project → Technology Mapping

When working on a project, detect the technology stack and apply the correct patterns.

## Detection Rules

| Indicator | Stack | Memory to Load |
|-----------|-------|----------------|
| `pom.xml` + `quarkus` in pom | **Quarkus/Java** | `quarkus-patterns.md`, `java-testing-practices.md`, `java-coding-standards.md` |
| `package.json` + `bun` in scripts/deps | **Bun/TypeScript** | (TypeScript patterns — TBD) |
| `build.gradle` + `quarkus` in deps | **Quarkus/Java** (Gradle) | Same as Maven Quarkus |

## Stack-Specific Commands

### Quarkus/Java
```bash
# Targeted test (RED or GREEN)
mvn clean test -pl backend -Dtest=TestClassName

# Single method
mvn clean test -pl backend -Dtest=TestClassName#methodName

# Full regression
mvn clean test -pl backend

# Note: Use `mvn` not `./mvnw` — wrapper doesn't exist in all projects
```

### Bun/TypeScript
```bash
# Targeted test
bun test src/path/to/test.test.ts

# Full regression with coverage
bun test --coverage

# With JUnit output for Crucible
bun test --reporter=junit --reporter-outfile=/tmp/junit.xml
```

## Stack-Specific Test Patterns

### Quarkus/Java

| Test Type | Annotation | When |
|-----------|-----------|------|
| POJO/enum/utility | Plain `@Test` | No CDI needed |
| Service with DI | `@QuarkusTest` | Needs CDI container |
| REST endpoint | `@QuarkusTest` + RestAssured | HTTP-level testing |
| Reactive chain | `@QuarkusTest` + `@RunOnVertxContext` + `UniAsserter` | Async assertions |
| Integration | `*IT.java` naming | Real infrastructure |

**Prohibited:** `Thread.sleep()`, `UUID.randomUUID()` (use `UuidV7Generator`), `@Mock`+`@InjectMocks` (use `@InjectMock`), `new Service()` in `@QuarkusTest`

### Bun/TypeScript

| Test Type | Pattern | When |
|-----------|---------|------|
| Unit | `describe`/`test` blocks | Pure functions, utilities |
| Integration | `describe` with setup/teardown | Service interactions |
| Mock | `mock()` from bun:test | External dependencies |

## Stack-Specific Crucible Ingest

### Quarkus/Java
```bash
# Test results (surefire XML directory)
curl -s -X POST http://localhost:3849/api/ingest \
  -H 'Content-Type: application/json' \
  -d '{"projectKey":"PROJECT_KEY","format":"junit","dataPath":"/absolute/path/backend/target/surefire-reports","agentId":"AGENT_ID"}'

# Compile failure
mvn clean test -pl backend -Dtest=TestClass 2>&1 | tee /tmp/build-output.txt
curl -s -X POST http://localhost:3849/api/ingest/compile \
  -H 'Content-Type: application/json' \
  -d "{\"projectKey\":\"PROJECT_KEY\",\"agentId\":\"AGENT_ID\",\"errors\":$(cat /tmp/build-output.txt | python3 -c 'import sys,json; print(json.dumps(sys.stdin.read()))')}"
```

### Bun/TypeScript
```bash
# Test results (JUnit XML file)
bun test src/path/test.test.ts --reporter=junit --reporter-outfile=/tmp/junit.xml
# Then the client ingests via /api/v2/runs/parsed (see the `crucible` skill, references/bun.md)
```

## Known Project Mappings

| Project | Path | Stack | Crucible Key |
|---------|------|-------|-------------|
| ah-codeforge (backend) | `~/Documents/data_projects/ah-codeforge` | Quarkus/Java | `019c9ff7-222f-7ae5-9121-2ae549e4d97a` |
| ah-codeforge-mcp | `~/Documents/data_projects/ah-codeforge-mcp` | Bun/TypeScript | (check Crucible) |
| ah-codeforge-plugin | `~/Documents/data_projects/ah-codeforge-plugin` | Bun/TypeScript | (check Crucible) |
| ah-rewrite-recipes | `~/Documents/data_projects/ah-rewrite-recipes` | Java (Maven) | `019c9ff7-231a-74e0-ab24-8c31a01146b5` |
