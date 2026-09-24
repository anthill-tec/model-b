<!-- Model B memory template (cross-project Java language reference). Imported 2026-09-21 from the user's global memory (java-testing-practices.md) by ruling: PRD §D5's global tier has no Pi home, so language refs ride the stack's memory templates and are scaffolded into <project>/docs/memory/. -->

# Java Testing Practices

## TDD Workflow (MANDATORY)

### Standard TDD Cycle
1. **Write test** (RED - should fail)
2. **Implement code** (GREEN - make test pass)
3. **Git commit** (only if tests GREEN)

### Java-Specific TDD Cycle (MANDATORY)
1. **Write test** (RED)
2. **Implement code** (GREEN)
3. **Clean up: Remove unused imports** from all modified files
4. **Run tests AGAIN** to verify import removal didn't break anything
5. **Git commit** (only if tests still GREEN)

(Dispatched sub-agents: the Model B sub-agent procedure (`~/.claude/skills/model-b/references/sub-agent-procedure.md`) §TDD is authoritative — a compile failure IS a RED state (ingest it); do NOT run the full suite, that's the orchestrator's pre-merge gate.)

### Refactoring with TDD
**ALWAYS read the TESTS FIRST** before refactoring:

1. **READ THE TESTS** - Understand current behavior
2. **Update tests** if behavior changes (e.g., 200 → 204 for DELETE)
3. **Refactor implementation** to match updated tests
4. **Run tests** to verify GREEN
5. **Commit** only when GREEN

**NEVER:**
- Refactor implementation without reading tests first
- Change return types without checking test expectations
- Commit in RED state

### Layer Migration Order (bottom-up)
When migrating or refactoring across layers, go **bottom-up — ONE class at a time, test after each, GREEN before moving on:**
1. **Model** (entity) + its tests
2. **Repository** + its tests
3. **Service** + its **integration** tests (NOT mock tests — see "Service-layer review gates" below)
4. **Resource** + its tests

Never big-bang across layers ("migrate 10 files then fix tests later") — each class lands GREEN before the next starts.

## Test Suite Organization

### Unit Tests vs Integration Tests

**Unit Tests (`*Test.java`)**
- Run with `./mvnw test`
- Use mocking for external dependencies
- Fast execution
- Test business logic in isolation

**Integration Tests (`*IT.java`)**
- Run with `./mvnw verify` (NOT `./mvnw test`)
- Use real infrastructure (TestContainers, DevServices)
- Slower execution
- Test actual integration with databases, message queues, etc.

**CRITICAL:** When removing methods, check BOTH unit tests AND integration tests. Unit tests passing doesn't mean integration tests aren't broken.

### Test Coverage Guidelines
- Write comprehensive tests covering all public interface methods
- Not just basic functionality
- Include edge cases and error scenarios

### Service Layer Testing Strategy

**Complex Integration Services** (e.g., EntityCacheService with Redis+MongoDB):
- **Primary:** Integration tests with TestContainers
- **Minimal:** Unit tests for pure logic only

**Business Logic Services** (e.g., BusinessEntityService):
- **Primary:** Unit tests with mocked dependencies
- **Secondary:** Integration tests for critical workflows

**Simple Repository/Data Services:**
- **Primary:** Integration tests
- **Minimal:** Unit tests for complex queries only

## Test Utilities Pattern

### ❌ Anti-Pattern: Direct Infrastructure Access in Tests

```java
// DON'T: Direct MongoDB client usage with hardcoded values
@Test
void testIndex() {
    MongoClient mongoClient = ...;
    MongoCollection<Document> collection = mongoClient
        .getDatabase("EntityStoreTest")  // Hardcoded!
        .getCollection("EntityStateSnapshots");
    // ... direct operations
}
```

**Problems:**
- Hardcoded database names
- Duplicated MongoDB boilerplate
- Breaks when configuration changes
- Violates DRY principle

### ✅ Recommended Pattern: Test Utilities + Config Injection

```java
// DO: Utility class + injected config
@ApplicationScoped
public class CacheIntegrationTestUtils {
    public boolean verifyEntityStateSnapshotIndex(
            MongoClient mongoClient,
            String databaseName) {
        // Reusable utility logic
    }
}

// In test:
@Inject
CacheIntegrationTestUtils testUtils;

@ConfigProperty(name = "quarkus.mongodb.database")
String databaseName;

@Test
void testIndex() {
    boolean exists = testUtils.verifyEntityStateSnapshotIndex(
        mongoClient,
        databaseName  // From config!
    );
}
```

**Benefits:**
- Reusable across all tests
- Uses actual configuration values
- Single source of truth
- Easier to maintain

**Best Practices:**
1. Create test utilities in `src/test/java/.../util/`
2. Inject configuration with `@ConfigProperty`
3. Never hardcode values that exist in `application.properties`
4. Follow existing utility patterns

## Quarkus Testing Patterns

### Basic Test Structure

```java
@QuarkusTest
public class MyServiceTest {
    
    @Inject
    MyService service;
    
    @Test
    public void testBusinessLogic() {
        // Arrange
        // Act
        // Assert
    }
}
```

### PanacheMock for Unit Tests

**What PanacheMock CAN Mock:**
- Static query methods: `findById()`, `find()`, `list()`, `count()`, etc.

**What PanacheMock CANNOT Mock:**
- Instance methods: `persist()`, `update()`, `delete()`
- This is a known Quarkus limitation (issues #16182, #17697)

**Solution:** Move persistence operation tests to Integration Test suite with real database.

**Example Unit Test with PanacheMock:**
```java
@QuarkusTest
public class BusinessEntityServiceTest {
    
    @Inject
    BusinessEntityService service;
    
    @Test
    public void testFetchById() {
        // Mock static query method
        PanacheMock.mock(BusinessEntity.class);
        BusinessEntity mockEntity = new BusinessEntity();
        when(BusinessEntity.findById(1L)).thenReturn(mockEntity);
        
        // Test business logic
        BusinessEntity result = service.fetchById(1L);
        assertNotNull(result);
    }
}
```

## Reactive Testing with Mutiny

### @RunOnVertxContext Pattern

**Use UniAsserter** for proper reactive testing:

```java
@Test
@RunOnVertxContext
public void testReactive(UniAsserter asserter) {
    asserter.execute(() -> {
        return idGenerator.getNextIdFor("Entity", Long.class)
            .chain(id -> EntityClass.getEntity(dto, id));
    });
    
    asserter.assertThat(() -> repository.findById(id), entity -> {
        assertNotNull(entity);
        assertEquals("expected", entity.field);
    });
}
```

**Why UniAsserter:**
- Correct pattern for Quarkus reactive testing
- Handles Vert.x context properly
- Avoids `.await().indefinitely()` blocking issues
- More idiomatic for reactive code

**Import:** `io.quarkus.test.vertx.UniAsserter`

**Avoid:** `.await().indefinitely()` in test logic - can cause blocking and test failures

### Mockito Reactive Mocking

When mocking methods returning `Uni<T>`, wrap return values:

```java
// ✅ CORRECT
when(mockService.getData()).thenReturn(Uni.createFrom().item(value));

// ❌ WRONG - Don't return unwrapped values
when(mockService.getData()).thenReturn(value);
```

## State Machine Testing

### Testing Intermediate State Transitions

**Context:** Testing state machines with multiple transitions (e.g., PENDING → HISTORICAL_FETCH → LIVE)

#### ❌ Incomplete Pattern: Only Test Final State
```java
// INCOMPLETE: Ignores intermediate HISTORICAL_FETCH state
@Test
void testRegisterStream_IncrementalMode() {
    StreamSubscription subscription = orchestrationService.registerStream(request)
        .await().indefinitely();

    Awaitility.await()
        .atMost(10, TimeUnit.SECONDS)
        .untilAsserted(() -> {
            StreamSubscription updated = subscriptionService.getSubscription(streamId)
                .await().indefinitely();
            assertEquals(StreamStatus.LIVE, updated.status);
        });
}
```

**Problem:** If `updateStatus(HISTORICAL_FETCH)` silently fails, subscription stays PENDING forever, but test times out with unhelpful error.

**Missing Coverage:**
- Is HISTORICAL_FETCH status ever set?
- Does PENDING → HISTORICAL_FETCH transition happen?
- How long does HISTORICAL_FETCH last?

#### ✅ Complete Pattern: Test Full Lifecycle
```java
// COMPLETE: Verifies intermediate transitions
@Test
void testRegisterStream_FullMode_VerifiesAllStatusTransitions() {
    // Create 50+ entities (slow fetch to observe intermediate state)
    createTestEntities(50);

    StreamSubscription subscription = orchestrationService.registerStream(request)
        .await().indefinitely();

    assertEquals(StreamStatus.PENDING, subscription.status);

    // 1. Wait for HISTORICAL_FETCH status (intermediate state)
    AtomicBoolean historicalFetchObserved = new AtomicBoolean(false);

    Awaitility.await()
        .atMost(5, TimeUnit.SECONDS)
        .pollInterval(100, TimeUnit.MILLISECONDS)
        .until(() -> {
            StreamSubscription current = subscriptionService.getSubscription(streamId)
                .await().indefinitely();

            if (current.status == StreamStatus.HISTORICAL_FETCH) {
                historicalFetchObserved.set(true);
            }

            return current.status == StreamStatus.HISTORICAL_FETCH ||
                   current.status == StreamStatus.LIVE;
        });

    assertTrue(historicalFetchObserved.get(),
        "HISTORICAL_FETCH status should be observed");

    // 2. Wait for final LIVE status
    Awaitility.await()
        .atMost(10, TimeUnit.SECONDS)
        .pollInterval(500, TimeUnit.MILLISECONDS)
        .untilAsserted(() -> {
            StreamSubscription finalState = subscriptionService.getSubscription(streamId)
                .await().indefinitely();
            assertEquals(StreamStatus.LIVE, finalState.status);
            assertTrue(finalState.historicalFetchCount >= 50);
        });
}
```

**What This Tests:**
1. ✅ Initial PENDING status set
2. ✅ Transition to HISTORICAL_FETCH happens
3. ✅ HISTORICAL_FETCH visible during fetch
4. ✅ Transition to LIVE after completion
5. ✅ Final metadata (historicalFetchCount) populated

**Critical Insight:** "We were only testing LIVE fetch mode and ignoring the automatic transition from HISTORICAL to LIVE fetch."

### Test Strategy for State Machines

1. **Unit tests:** Test each transition directly
   - `testExecuteFull_VerifiesHistoricalFetchTransition`
   - `testExecuteIncremental_VerifiesHistoricalFetchTransition`

2. **Integration tests:** Test full lifecycle via orchestration
   - `testRegisterStream_FullMode_VerifiesAllStatusTransitions`
   - `testRegisterStream_IncrementalMode_VerifiesHistoricalFetchStatus`

3. **Edge cases:** Test boundary conditions
   - `testExecuteFull_HistoricalFetchTransitionEvenWhenEmpty` (empty result)
   - `testUnregisterStream_HistoricalFetchInProgress` (cancel during transition)

**Test Count Impact:**
- **Before:** 2 tests (only final state)
- **After:** 5 tests (full lifecycle + edge cases)
- **Coverage improvement:** Catches silent transition failures

## Integration Testing with TestContainers

### MongoDB TestContainers Pattern (CRITICAL)

**ALWAYS use this annotation for MongoDB integration tests:**

```java
@QuarkusTest
@QuarkusTestResource(value = MongoTestResource.class, restrictToAnnotatedClass = true)
public class BusinessEntityRepositoryIT {
    // Test implementation
}
```

**Why `restrictToAnnotatedClass = true`:**
- Prevents Quarkus DevServices class loading conflicts
- Critical for preventing test hanging during class loading
- Isolates container management per test class

### Test Hanging Root Cause
- Quarkus DevServices + TestContainers conflict causes test hanging during class loading
- **Solution:** Use `restrictToAnnotatedClass = true` isolation
- **NOT the solution:** Disabling DevServices globally

### Hybrid Testing for Services with Active Record

**Write BOTH:**

1. **Unit tests** with PanacheMock:
   - Mock static query methods (`findById`, `find`, etc.)
   - Validate business logic and query delegation
   
2. **Integration tests** with TestContainers:
   - Test actual database operations
   - Validate persistence operations (`persist`, `update`, `delete`)

## DevServices Configuration

### MongoDB DevServices

**Use `%prod.` prefix** for production config to enable DevServices in dev/test:

```properties
# Production config
%prod.quarkus.mongodb.connection-string=mongodb://production-host:27017

# NO connection string needed for dev/test
# DevServices automatically provides it
```

**DevServices requirements:**
- NO explicit connection string in non-production profiles
- Authentication automatically handled by DevServices containers

### Redis DevServices

Use `@QuarkusTest` with Redis DevServices for caching layer testing:
- Automatic Redis instance provisioning
- No manual container management
- Fresh instance per test class (test isolation)

## Debugging Principles

### CRITICAL: Test-First Problem Isolation

**Context:** Debugging HTTP 500 error from REST endpoint

#### ❌ The Mistake

When encountering HTTP 500 from `CDCStreamResource.registerStream()`:
1. Modified working service layer code (commented out validation)
2. Added debug logging to try to "see" the error
3. Made multiple speculative changes without verifying impact

#### ✅ The Correct Approach

**ALWAYS run existing tests FIRST to narrow the problem vector:**

```bash
# 1. Find tests for the method being called
find src/test -name "*StreamSubscription*IT.java"

# 2. Check if service layer method has tests
grep "createSubscription" StreamSubscriptionServiceIT.java

# 3. Run those tests
./mvnw test -Dtest=StreamSubscriptionServiceIT
# Result: 16/16 tests GREEN ✅
```

**Result:** Immediately identified problem is NOT in service layer → Must be in REST layer (resource, serialization, DI, HTTP layer).

### The Rule

**NEVER modify code that has passing tests without running those tests first.**

If a REST endpoint fails but the service layer tests pass:
- ✅ Problem is in: Resource class, path mapping, serialization, DI, HTTP layer
- ❌ Problem is NOT in: Service logic, validation, database operations

**Problem Vector Narrowing:**
- Without tests: 100% of codebase suspect
- With service tests GREEN: Only ~10% of code suspect (REST layer only)

This saves hours of debugging wrong code.

## Container Runtime Compatibility

### TestContainers with Docker vs Podman

**Docker:** Better TestContainers compatibility (recommended)

**Podman Issues:**
- TestContainers caches Docker environment detection failures
- Refuses to retry within same JVM session
- Socket detection issues even with correct configuration
- Version-independent issues (persists across Quarkus versions)

**Migration Decision:** Podman → Docker resolves persistent compatibility issues

### CI/CD Consideration
Integration tests work correctly in fresh CI/CD environments, making them production-ready despite local development issues.

## Continuous Testing Issues

### @Nested Classes + Quarkus Dev Mode

**Problem:** ClassCastException in `quarkus dev` continuous testing mode

**Root Cause:** Known Quarkus bug (#47671) - @Nested classes loaded by different classloaders during hot-reload

**When It Occurs:**
- Only in `quarkus dev` continuous testing mode
- NOT in `./mvnw test`

**Solution:**
```properties
quarkus.test.continuous-testing=false
```

**Alternative:** Press 's' in quarkus dev terminal to stop continuous testing manually

## Test Execution and Reporting

### CRITICAL: Always Use Surefire/Failsafe Reports (HIGH PRIORITY)

**NEVER parse Maven console output to check test results.** Always use the report files:

```bash
# Check surefire reports (unit + integration tests)
cat target/surefire-reports/*.txt | grep -E "(Tests run:|Failures:|Errors:)"

# Check specific test class result
cat target/surefire-reports/org.fourpm.entitystore.service.MyServiceIT.txt

# Check failsafe reports (if used separately)
cat target/failsafe-reports/*.txt | grep -E "(Tests run:|Failures:|Errors:)"

# Get accurate total count
cat target/surefire-reports/*.txt | grep "^Tests run:" | awk -F'[,:]+' '{t+=$2; f+=$4; e+=$6} END {print "Total:", t, "Failures:", f, "Errors:", e}'
```

**Why This Is Critical:**
- Maven console output is verbose and unreliable for parsing
- Console may be truncated or interleaved with container logs
- Surefire reports are structured and always accurate
- Saves significant time vs re-running tests or parsing logs

**Report File Locations:**
- `target/surefire-reports/*.txt` - Summary per test class
- `target/surefire-reports/*.xml` - Detailed XML reports
- `target/failsafe-reports/*.txt` - Failsafe summaries (if used)

### Maven Test Count Accuracy

**Warning:** Maven summary "Tests run: N" often undercounts actual tests

**Why:** @Nested JUnit classes reported separately but not summed correctly

**Get Accurate Count:**
```bash
cat target/surefire-reports/*.txt | grep "^Tests run:" | awk '{tests+=$3} END {print tests}'
```

**Faster Alternative:** Read and grep surefire text reports instead of running tests again

### Surefire vs Failsafe
- **Surefire:** Runs `*Test.java` (unit tests)
- **Failsafe:** Runs `*IT.java` (integration tests)
- Some projects run ALL tests via surefire only (check for `*IT.txt` in `target/surefire-reports/`)

### Coverage — JaCoCo (Quarkus): read the RIGHT report
Quarkus produces TWO JaCoCo outputs; only one is correct for Quarkus-managed classes.
- ✅ **`target/jacoco-report/jacoco.csv`** — from the `quarkus-jacoco` extension. This is the REAL coverage data.
- ❌ **`target/site/jacoco/`** — from the raw maven jacoco plugin. Shows **0% for Quarkus-managed classes**. IGNORE IT.
- exec files: ✅ `target/jacoco-quarkus.exec` (Quarkus, correct) vs ❌ `target/jacoco.exec` (maven plugin, incomplete).
- Check a class after the FULL suite: `grep YourClassName target/jacoco-report/jacoco.csv`
- CSV columns: `GROUP,PACKAGE,CLASS,INSTRUCTION_MISSED,INSTRUCTION_COVERED,BRANCH_MISSED,BRANCH_COVERED,LINE_MISSED,LINE_COVERED,COMPLEXITY_MISSED,COMPLEXITY_COVERED,METHOD_MISSED,METHOD_COVERED`
- **Target: >80% instruction coverage on service classes.** A service class at 0% instruction coverage = bad tests (mocked-out, no real exercise) OR you're reading the wrong report.
- **JaCoCo version:** ≥ 0.8.13 for Java 24 support; use 0.8.14 (aligned with `quarkus-jacoco`).

## Test Execution Strategy

### Focused Testing First
1. Test current SUT (System Under Test) first
2. Verify it's clean (all tests GREEN)
3. Run entire suite for regression checks

### Test Suite Commands
```bash
# Unit tests only
./mvnw test

# Integration tests only (includes unit tests)
./mvnw verify

# Clean build + all tests
./mvnw clean verify
```

## Mockito Configuration

### Java 21+ Compatibility
Use `-javaagent:mockito-agent.jar` for:
- Static mocking
- Final class mocking
- Java 21+ compatibility

## Test Isolation Best Practices

### @QuarkusTestResource Isolation

Prevent container conflicts:
```java
@QuarkusTestResource(value = MongoTestResource.class, restrictToAnnotatedClass = true)
```

### Test Data Cleanup
- Each test class gets fresh DevServices instance
- Ensures test independence
- No manual cleanup needed between tests

### @TempDir with @QuarkusTest (CRITICAL)
- **NEVER use field-level `@TempDir`** with `@QuarkusTest` — CDI proxy injection causes an NPE.
- **ALWAYS use a method-parameter `@TempDir`:** `void myTest(@TempDir Path tmpDir) { ... }`.
- Or use a `TempProjectResource` (`QuarkusTestResourceLifecycleManager`) for configurable temp paths.
- This mistake has been repeated by nearly every agent — check for it in review.

## Exception Handling Tests

Always test both success and failure paths:
```java
@Test
public void testDelete_Success() {
    // Test successful deletion
}

@Test
public void testDelete_NotFound() {
    // Test deletion of non-existent entity
    assertThrows(InvalidDataFetchException.class, () -> {
        service.deleteById(999L);
    });
}
```

## E2E Black-Box Testing (@QuarkusIntegrationTest)

### Bootstrap Mode for Test Data Setup

**Problem:** E2E tests run against native Docker containers where `@Startup` beans (like `TestSchemaRegistration`) don't execute. Schema Registry is empty, causing 500 errors.

**Solution:** Use **bootstrap mode** — include `avroSchema` field in `EntityTypeRegistrationRequest` to push schema TO the registry from the test side.

```java
// Use TestDataFactory for schema JSON (single source of truth)
String propertySchema = TestDataFactory.getPropertySchemaJson(
    "org.fourpm.entitystore.entity", "Property");

Map<String, Object> requestBody = new LinkedHashMap<>();
requestBody.put("typeName", "org.fourpm.entitystore.entity.Property");
requestBody.put("indexedFieldNames", List.of("id", "status", "address.city"));
requestBody.put("defaultTTL", "PT168H");
requestBody.put("ttlRefreshPolicy", "PRESERVE");
requestBody.put("authorizedFeeds", List.of(1, 2));
requestBody.put("avroSchema", propertySchema);  // ← ENABLES BOOTSTRAP MODE

given()
    .contentType(ContentType.JSON)
    .body(requestBody)
.when()
    .post("/store/entity-types/register")
.then()
    .statusCode(anyOf(equalTo(201), equalTo(200), equalTo(409)));  // NO MORE 500!
```

**Key Points:**
- `avroSchema` field triggers bootstrap mode in `BusinessEntityServiceImpl.registerEntityType()`
- Schema is registered TO Schema Registry (not fetched FROM it)
- 59 integration tests validate this code path (`BusinessEntityServiceSchemaBootstrapIT`)
- `TestDataFactory.getPropertySchemaJson()` generates valid Avro schemas matching POJOs

### SSE Testing with Vert.x WebClient (E2E)

**Problem:** REST-assured has limitations with chunked transfer encoding for SSE streams.

**Solution:** Use standalone Vert.x WebClient (`SseTestClient`) for SSE-specific tests.

```java
// Create standalone client (no CDI required)
private static SseTestClient sseClient;

@BeforeAll
static void setup() {
    sseClient = SseTestClient.create("localhost", RestAssured.port);
}

@Test
void shouldListStreamsViaSSE() {
    var response = sseClient.sendGet("/store/streams", Duration.ofSeconds(10));
    assertEquals(200, response.statusCode());
    assertTrue(response.getHeader("content-type").contains("text/event-stream"));
}

@Test
void shouldCollectSSEEvents() {
    List<String> events = sseClient.collectEvents("/store/streams", Duration.ofSeconds(10));
    // events = list of "data:" payloads
}
```

**When to use which tool:**
- **REST-assured:** HTTP status codes, JSON responses, basic SSE content-type
- **Vert.x WebClient (SseTestClient):** SSE protocol verification, event collection, streaming behavior
- **Typed REST client:** Integration tests (NOT E2E) where CDI context is available

### TestDataFactory as Schema Source of Truth

**Rule:** Always use `TestDataFactory.get*SchemaJson()` for schema generation — never inline raw schema JSON in tests.

Available generators:
- `getPropertySchemaJson(namespace, name)` — Property with Address, Pricing, enums
- `getContactSchemaJson(namespace, name)` — Contact with ContactType, ContactStatus
- `getTenancySchemaJson(namespace, name)` — Tenancy with TenancyType, dates
- `getPropertySchemaV2Json(namespace, name)` — V2 with "description" field (evolution)

### E2E test kinds (smoke / black-box / load / flow-based)
| Kind | What | How |
|---|---|---|
| **Smoke** | the deployed app boots and core endpoints answer | `@QuarkusIntegrationTest` + RestAssured against the packaged app; assert 2xx on health + a few key routes |
| **Black-box** | exercise the running service ONLY through its HTTP surface (no CDI/internal access) | RestAssured `given()...when()...then()`; treat the app as opaque |
| **Flow-based** | a multi-step business scenario across endpoints (create → read → mutate → verify) | sequence RestAssured calls; assert state transitions and final persisted state |
| **Load** | throughput/latency under concurrency | a load harness (e.g. parallel RestAssured / a load tool) against a deployed instance; assert p95/error-rate bounds — keep OFF the per-cycle path, run at the gate/CI |

- **External resources via DevServices/TestContainers.** Let Quarkus DevServices spin up Mongo/Redis/Kafka for `@QuarkusTest`; for `@QuarkusIntegrationTest` against a packaged/native app, drive containers through a `QuarkusTestResourceLifecycleManager`. **Check docker is clean before native/JVM e2e cycles.**
- **Test-data state management.** Use a reusable utility (injected, config-driven — never hardcoded DB names) to set up and tear down DB/Redis/external state per test; `@BeforeEach`/`@AfterEach` cleanup keeps tests independent. See "Test Utilities Pattern" above.

### REST client integration test pattern (Resource layer)
For Resource-layer integration tests, drive the endpoint through a type-safe declarative client rather than hand-built HTTP:
```java
@RegisterRestClient(configKey = "entity-api")
@Path("/api/v1/entities")
public interface EntityRestClient {
    @POST Uni<EntityDTO> create(EntityDTO dto);
    @GET @Path("/{id}") Uni<EntityDTO> get(@PathParam("id") String id);
}

@QuarkusTest
class EntityResourceIT {
    @Inject @RestClient EntityRestClient client;

    @Test @RunOnVertxContext
    void createThenFetch(UniAsserter asserter) {
        var dto = new EntityDTO(/* … */);
        asserter.execute(() -> client.create(dto));
        asserter.assertThat(() -> client.get(dto.id()), e -> assertEquals(dto.name(), e.name()));
    }
}
```
RestAssured remains the right tool for raw HTTP status/body/SSE assertions; the `@RestClient` form is for type-safe contract tests where CDI is available (`*IT.java`, failsafe).

## Crucible reporting — `mvn-crucible.py` (use the CLI, not inline curl/python)

Route every Maven test run + Crucible ingest through `~/.crucible/clients/mvn-crucible.py` (Crucible's installed client, listed in `~/.crucible/crucible-clients.json`; the Java sibling of `rust-crucible.py`). A stable command signature gets one-time permission approval; inline `curl`/python re-prompts every run. The script embodies the four test tiers and the ingest routing below — don't hand-roll the surefire/JaCoCo parsing.

**Subcommands by tier** (all take `--agent <id>`; project key read from `<project-dir>/.env` `CRUCIBLE_PROJECT_KEY`, a UUID):

| Tier | Command | Maven goal | Ingest |
|---|---|---|---|
| **unit** (RED/GREEN cycle) | `unit --test <Class[#method]>` | `clean test -Dtest=…` | surefire → `/api/v2/runs` junit; compile-fail → `/api/v2/runs/compile` |
| **module** | `module --module <m> [--also-make]` | `clean test -pl <m> [-am]` | surefire (parsed if multi-module) |
| **e2e** | `e2e [--failsafe-only] [--native] [--with-docker]` | `clean verify` / `failsafe:integration-test` | failsafe + surefire (parsed, **no coverage**) |
| **regression** (orchestrator gate) | `regression` | `clean verify` (whole reactor) | surefire + failsafe + JaCoCo → `/api/v2/runs/parsed` **with coverage** |
| compile-only | `compile` | `clean test-compile` | `/api/v2/runs/compile` |

- `register --role RED\|GREEN\|FIX\|VERIFY\|ORCHESTRATOR\|report [--cycle <cycleId>]` first; `unregister` last. `--role` is required and case-exact (five uppercase, `report` lowercase); `RED\|GREEN\|FIX\|VERIFY` must bind an ACTIVE cycle of an OPEN plan with `--cycle` or the server refuses the registration 409 — `ORCHESTRATOR`/`report` may register unbound.
- Common flags: `--module`/`--also-make` (reactor `-pl`/`-am`), `--native` (`-Dnative`), `--profile P` (`-P`), `--system-prop k=v` (`-Dk=v`, e.g. `api.version=1.4.2`), `--update-snapshots` (`-U`), `--log <file>` (capture full run for later grep — never re-run a long suite).
- **Coverage is published ONLY by `regression` on a zero-failure run** — JaCoCo from a partial/failed/targeted run is incomplete; the script refuses to attach it when `failed > 0`.
- Monorepo backend / non-root pom → `--maven-dir backend` or `CRUCIBLE_MAVEN_DIR=backend` in `.env`. Compose-based e2e → `CRUCIBLE_COMPOSE_FILE` / `CRUCIBLE_DOCKER_SERVICES` in `.env`; JaCoCo behind a profile → `--coverage-profile` / `CRUCIBLE_COVERAGE_PROFILE`.
- `pre-merge-gate` = docker-up → regression → docker-down (always). The `crucible` skill's `references/java.md` documents the underlying API; the script automates it.

## Review Gates & Test Quality

### Test Quality Checklist — every test class must cover
1. **Happy path** — normal operations work correctly
2. **Error / failure paths** — 404s, 400s, 409s, validation failures
3. **Edge cases** — empty collections, null inputs, boundary values
4. **Idempotency** — repeated operations behave correctly
5. **State transitions** — data actually changes in the database
6. **Concurrency concerns** — where applicable

### What makes a BAD test
- ❌ Only tests the happy path
- ❌ Uses `@InjectMock` on an I/O-backed service (yields ~0% real coverage — see service-layer gate below)
- ❌ Doesn't verify data was actually persisted/updated
- ❌ Doesn't test error conditions
- ❌ Doesn't clean up test data (`@BeforeEach` cleanup)
- ❌ Asserts only that "no exception was thrown"

### Service-layer review gates
- **Services that do real I/O** (DB / cache / message queues — e.g. EntityCacheService, repository-backed services) MUST have **integration tests** (`@QuarkusTest` + real infra via DevServices/TestContainers, `@Inject` the real service, `@BeforeEach` cleanup). A `@InjectMock` on such a service tests Mockito, not your code → ~0% real coverage = FAIL.
- This refines, not replaces, the nuanced **Service Layer Testing Strategy** above: pure business-logic services with no I/O may still be primarily unit-tested with mocks; the integration-test mandate applies to I/O-backed services.

### Reviewer checklist — FAIL the review if any are violated
1. **Coverage:** run JaCoCo, read `target/jacoco-report/jacoco.csv` (not `target/site/jacoco/`). I/O-backed service classes < 80% instruction = FAIL.
2. **Test type:** I/O-backed service tests using `@InjectMock` = FAIL (must be integration).
3. **Test breadth:** only happy path = FAIL. Thin IT coverage (missing error paths, edge cases, validation scenarios) = MAJOR, not MINOR.
4. **Corner cases:** no edge-case / error-path tests = FAIL.
5. **Coding standards:** unused imports, wrong naming, empty catch blocks = FAIL (see java-coding-standards.md).
6. **Test naming:** descriptive pattern (`testMethodName_scenario_expectedResult` or equivalent). Vague names (`test1`, `testIt`, `testCreate`) = FAIL.
7. **SSE events:** all mutation operations emit SSE events (where the service exposes SSE).
8. **Deduplication:** repeated operations are idempotent or properly guarded.
9. **Reactive correctness:** all DB operations return `Uni<T>` / `Multi<T>`; no blocking calls.
10. **Validation:** inputs validated, proper HTTP status codes on errors.
11. **Clean code:** no dead/commented-out code, meaningful variable names.

## DevOps Environment (DevServices & Container Runtime)

Unique DevServices / container-runtime operational detail not covered by the sections above (merged in from the retired global devops memory file).

### DevServices Port Allocation

**Problem:** "Port already allocated" errors when restarting `quarkus dev` — DevServices containers persist across restarts and new sessions try to bind already-allocated ports (common with fixed port assignments, e.g. 8082 for Apicurio Registry).

**Solution 1 — container reuse (recommended):**
```properties
quarkus.mongodb.devservices.shared=true
quarkus.redis.devservices.shared=true
quarkus.apicurio-registry.devservices.shared=true
```

**Solution 2 — dynamic ports:**
```properties
quarkus.apicurio-registry.devservices.port=0
```

**Best practice:** combine both — `shared=true` for faster restarts, `port=0` for conflict-prone services (Apicurio etc.). Tests remain unaffected: they always get isolated containers (`shared=true` applies to dev mode only).

### Redis DevServices Configuration Detail

```properties
# DevServices enabled by default when the Redis dependency is present —
# no manual configuration needed for dev/test.
%prod.quarkus.redis.hosts=redis://production-host:6379

# Database number goes IN the connection string
quarkus.redis.hosts=redis://localhost:6379/0
```

**Deprecated in Quarkus 3.x:**
```properties
# ❌ REMOVED — use the connection string instead
quarkus.redis.database=0
```

### Configuration Property Deprecations & Typos

**Removed in Quarkus 3.x (enabled by default, no longer needed):**
```properties
quarkus.smallrye-openapi.enable
quarkus.swagger-ui.enable
quarkus.smallrye-openapi.auto-add-servers
```

**Common typo to watch:** `quarkus.mongodb.heath.enabled` → must be `quarkus.mongodb.health.enabled`.

### Docker 29.x API Version Compatibility (TestContainers)

**Problem:** Docker 29.x (November 2025+) requires minimum API version 1.44, but TestContainers defaults to 1.32:
```
IllegalStateException: Previous attempts to find a Docker environment failed.
BadRequestException (Status 400: {"message":"client version 1.32 is too old. Minimum supported API version is 1.44"})
```

**Solution:** create `~/.docker-java.properties`:
```properties
api.version=1.44
```
Verification: test logs show `GET /v1.44/info` instead of `/v1.32/info`. Alternatives: `System.setProperty("api.version", "1.44");` in test code, or a Surefire `<systemPropertyVariables>` entry. Reference: [TestContainers Issue #11212](https://github.com/testcontainers/testcontainers-java/issues/11212).

### Podman Configuration (For Reference)

Docker remains the recommended container runtime (see "Container Runtime Compatibility" above). If you must use Podman:

```bash
sudo apt install podman podman-docker
loginctl enable-linger $USER
systemctl --user enable --now podman.socket
export DOCKER_HOST=unix:///run/user/1000/podman/podman.sock
export TESTCONTAINERS_RYUK_DISABLED=true
```

`~/.testcontainers.properties`:
```properties
docker.host=unix:///run/user/1000/podman/podman.sock
ryuk.disabled=true
docker.client.strategy=org.testcontainers.dockerclient.UnixSocketClientProviderStrategy
```

**Note:** despite proper configuration, Podman may still have detection issues.

### Environment Detection Caching

TestContainers caches Docker environment detection FAILURES and refuses to retry within the same JVM session — the failure persists across test runs until a JVM restart. Workaround: switch to Docker from Podman and/or restart the IDE/test runner. (This is also why integration tests work correctly in fresh CI/CD environments — no cached detection failures.)

### DevServices Container Cleanup & Port Management

```bash
# List running DevServices containers
docker ps | grep testcontainers

# Stop / remove all DevServices containers
docker stop $(docker ps -q --filter "label=org.testcontainers")
docker rm $(docker ps -aq --filter "label=org.testcontainers")

# Find what's using a port / kill it
lsof -i :8082
kill -9 $(lsof -t -i :8082)
```

### Troubleshooting Quick Table

| Symptom | First checks |
|---|---|
| Port already allocated | `shared=true`? try `port=0`; manually stop containers; restart dev mode |
| Tests hanging | `restrictToAnnotatedClass = true`? Docker running? prefer Docker over Podman |
| Container detection failures | Docker installed/running? `DOCKER_HOST` set? restart IDE/test runner; migrate Podman → Docker |
| "client version 1.32 is too old" | Docker 29.x: `~/.docker-java.properties` with `api.version=1.44` |
| ClassCastException in dev mode | disable continuous testing (`quarkus.test.continuous-testing=false`) or press `s`; run `./mvnw test` |

## Testing Guidelines Summary

1. **ALWAYS follow TDD:** Write test first (RED) → Implement (GREEN) → Commit
2. **Unit tests:** Use PanacheMock for static query methods only
3. **Integration tests:** Use TestContainers with `restrictToAnnotatedClass = true`
4. **Reactive tests:** Use `@RunOnVertxContext` with `UniAsserter`
5. **State machines:** Test intermediate transitions, not just final states
6. **Test utilities:** Use config injection, never hardcode values
7. **Problem isolation:** Run existing tests FIRST to narrow debugging scope
8. **Both suites:** Write unit AND integration tests for comprehensive coverage
9. **Clean imports:** Remove unused imports before final commit
10. **Never commit RED:** Always achieve GREEN before committing
