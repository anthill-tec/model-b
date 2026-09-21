<!-- Model B memory template (cross-project Java language reference). Imported 2026-09-21 from the user's global memory (quarkus-patterns.md) by ruling: PRD §D5's global tier has no Pi home, so language refs ride the stack's memory templates and are scaffolded into <project>/docs/memory/. -->

# Quarkus Patterns and Best Practices

## Configuration Management

### @ConfigMapping Pattern

**Use interfaces with @ConfigMapping, not records with validation**

#### ❌ Anti-Pattern: Records with Validation
```java
// DON'T: Record with compact constructor validation
@ConfigMapping(prefix = "entitystore.cache")
public record CursorConfig(
    @WithDefault("300s")
    Duration cursorIdleTimeout
) {
    public CursorConfig {
        if (cursorIdleTimeout.toSeconds() < 60) {
            throw new IllegalArgumentException("...");
        }
    }
}
```

**Problem:** SmallRye Config cannot generate implementation for records with compact constructors.  
**Error:** `java.lang.NoSuchMethodException: CursorConfig.<init>()`

#### ✅ Recommended Pattern: Interfaces
```java
// DO: Interface with annotations
@ConfigMapping(prefix = "entitystore.cache")
public interface CursorConfig {
    @WithName("cursor-idle-timeout")
    @WithDefault("300s")
    Duration cursorIdleTimeout();
}
```

**Benefits:**
- SmallRye Config generates implementation at build time
- Validation happens at startup (fail-fast)
- No unit tests needed (validated by Quarkus config system)
- Cleaner, more idiomatic Quarkus code

**When to use:**
- All @ConfigMapping classes should be interfaces
- Let Quarkus handle validation at startup
- Test via integration tests, not unit tests

### Configuration Injection Best Practices

**❌ Anti-Pattern:**
```java
private static final String DATABASE_NAME = "EntityStoreTest";
```

**✅ Pattern:**
```java
@ConfigProperty(name = "quarkus.mongodb.database")
String databaseName;
```

**Why:**
- Single source of truth (application.properties)
- Works across all environments (dev/test/prod)
- Configuration changes don't require code changes
- Respects profile-specific overrides (%test, %prod)

**Example:**
```properties
# application.properties
%prod.quarkus.mongodb.database=EntityStateStore
%test.quarkus.mongodb.database=EntityStoreTest
```

## Reactive Programming with Mutiny

### Uni and Multi Patterns
- **Always use** `Uni<T>` and `Multi<T>` for reactive operations
- **Avoid** blocking calls in reactive chains
- Use `onFailure().transform()` for custom exception mapping

### Exception Handling in Reactive Chains
```java
return service.fetchData()
    .onFailure().transform(ex ->
        new CustomException("Failed to fetch data", ex)
    );
```

### Continuous Streaming with Multi.repeating() (Advanced Pattern)

**Use Case:** Server-Sent Events (SSE) streaming where service layer owns the continuous loop

#### Pattern: Stateful Continuous Streaming
```java
private Multi<CDCEventDto> streamFromRedis(String streamKey, String startId) {
    ReactiveStreamCommands<String, String, String> streamCommands = redisDataSource.stream(String.class);
    AtomicReference<String> currentId = new AtomicReference<>(startId);

    // Create repeating Multi that produces batches until termination condition
    Multi<List<StreamMessage<String, String, String>>> batchStream = Multi.createBy().repeating()
        .uni(() -> {
            XReadArgs args = new XReadArgs()
                .count(READ_COUNT)
                .block(READ_BLOCK);

            String readId = currentId.get();

            return streamCommands.xread(streamKey, readId, args)
                .onItem().invoke(messages -> {
                    if (!messages.isEmpty()) {
                        // Update state for next iteration
                        String newLastId = messages.get(messages.size() - 1).id();
                        currentId.set(newLastId);
                    }
                });
        })
        .until(messages -> messages.isEmpty());  // Stop when empty

    // Flatten batches and add lifecycle handlers
    return batchStream
        .onItem().transformToMulti(messages ->
            Multi.createFrom().iterable(messages)  // Flatten List to Multi
        )
        .concatenate()  // CRITICAL: Merge MultiFlatten back to Multi
        .onItem().transform(this::parseToDto)
        .onCancellation().invoke(() ->
            logger.info("SSE client disconnected")
        )
        .onFailure().invoke(throwable ->
            logger.error("Stream error: {}", streamKey, throwable)
        );
}
```

#### Key Components Explained

**1. Multi.createBy().repeating().uni()** - Creates loop that produces items repeatedly
```java
Multi.createBy().repeating().uni(() -> {
    return someUniOperation();  // Executes repeatedly
})
```

**2. AtomicReference for State Tracking** - Maintains state across loop iterations
```java
AtomicReference<String> currentId = new AtomicReference<>(startId);
// Update in .invoke() callback
currentId.set(newValue);
// Read in next iteration
String value = currentId.get();
```

**3. .until() Termination Condition** - Stops loop when predicate returns true
```java
.until(result -> result.isEmpty())  // Stop on empty result
```

**4. .concatenate() for Flattening** - CRITICAL operator after .transformToMulti()
```java
.onItem().transformToMulti(batch ->
    Multi.createFrom().iterable(batch)  // Returns MultiFlatten
)
.concatenate()  // Merges all Multi streams into single Multi
.onItem().transform(...)  // Now can chain further operators
```

**Without .concatenate():** Type is `MultiFlatten<T, R>` which doesn't support `.onItem()` chaining

**Alternative:** Use `.merge()` for concurrent processing or `.onItem().disjoint()` in some patterns

**5. Lifecycle Handlers Placement** - MUST be after full Multi construction
```java
// ✅ CORRECT
return batchStream
    .onItem().transformToMulti(...)
    .concatenate()
    .onCancellation().invoke(...)  // After full Multi chain
    .onFailure().invoke(...);

// ❌ WRONG - Compile error
return batchStream
    .onCancellation().invoke(...)  // Before transformToMulti
    .onItem().transformToMulti(...);
```

#### SSE Integration Pattern

**Resource Layer (Endpoint):**
```java
@GET
@Path("/{streamId}/events")
@Produces(MediaType.SERVER_SENT_EVENTS)
@org.jboss.resteasy.reactive.RestStreamElementType(MediaType.APPLICATION_JSON)
public Multi<CDCEventDto> streamEvents(
        @PathParam("streamId") String streamId,
        @HeaderParam("Last-Event-ID") String lastEventId) {

    return cdcStreamService.streamEvents(streamId, lastEventId);
}
```

**Service Layer (Continuous Loop):**
- Service owns the continuous streaming logic
- Multi loops until termination condition (stream drained, error, cancellation)
- Resource just delegates - clean separation of concerns

#### Benefits of This Pattern

1. **Stateful Streaming** - Track last processed ID across iterations
2. **Graceful Termination** - Stops when condition met (empty result)
3. **Client Disconnect Handling** - `.onCancellation()` called when SSE closes
4. **Reconnection Support** - Client sends Last-Event-ID, new Multi starts from there
5. **No Server State** - All state in AtomicReference within Multi scope
6. **Batching** - Process results in batches (READ_COUNT) for efficiency
7. **Backpressure Aware** - Mutiny handles flow control automatically

#### Common Pitfalls

**❌ Missing .concatenate():**
```java
.onItem().transformToMulti(...)
.onItem().transform(...)  // COMPILE ERROR: MultiFlatten has no onItem()
```

**❌ Lifecycle handlers before Multi construction:**
```java
.onCancellation().invoke(...)
.onItem().transformToMulti(...)  // May not work as expected
```

**❌ Not updating state in AtomicReference:**
```java
AtomicReference<String> currentId = new AtomicReference<>(startId);
// Forgot to call currentId.set(newValue) - loop reads same ID repeatedly
```

**❌ Blocking in reactive chain:**
```java
.onItem().invoke(item -> {
    Thread.sleep(1000);  // Blocks event loop!
})
```

### Reactive CRUD Helpers Pattern

**Avoid `.onFailure().recoverWithItem()` anti-pattern in service layer**

Create reusable utility methods for common reactive operations:

```java
// Utility class
public class ReactiveHelpers {
    public static <T> Uni<T> fetchOrNotFound(
            Uni<T> fetchOperation,
            String errorMessage) {
        return fetchOperation.onItem().ifNull()
            .failWith(() -> new InvalidDataFetchException(errorMessage));
    }

    public static Uni<Void> deleteOrNotFound(
            Uni<Boolean> deleteOperation,
            String errorMessage) {
        return deleteOperation.flatMap(deleted -> {
            if (!deleted) {
                return Uni.createFrom().failure(
                    new InvalidDataFetchException(errorMessage)
                );
            }
            return Uni.createFrom().voidItem();
        });
    }
}

// In service layer
public Uni<StreamSubscription> getSubscription(String streamId) {
    return ReactiveHelpers.fetchOrNotFound(
        StreamSubscription.findById(streamId),
        "Stream not found: " + streamId
    );
}
```

**Benefits:**
- Services delegate exception handling to GlobalExceptionMappers
- No manual HTTP response construction in services
- Reusable patterns across all services
- Cleaner separation: Services throw exceptions, Resources catch nothing

## Redis API Compatibility (Quarkus 3.28.1+)

### ReactiveKeyCommands
```java
// exists(key) returns Uni<Boolean> - direct use
Uni<Boolean> exists = commands.exists(key);

// del(keys...) returns Uni<Integer> - map to boolean for success checking
Uni<Boolean> deleted = commands.del(key1, key2)
    .map(count -> count > 0);
```

### ReactiveValueCommands
```java
// mget(keys...) returns Uni<Map<K,V>> - iterate .values() for results
Uni<List<String>> values = commands.mget(key1, key2)
    .map(map -> new ArrayList<>(map.values()));
```

## Vert.x Context Management (CRITICAL)

### Hybrid Operations (Redis + MongoDB)

**Problem:** "Access to Context.putLocal() forbidden from root context" errors

**Solution:** Use `ContextInternal.duplicate()` to create proper contexts for MongoDB operations

```java
// Requires: SmallRye Context Propagation extension
<dependency>
    <groupId>io.quarkus</groupId>
    <artifactId>quarkus-smallrye-context-propagation</artifactId>
</dependency>

// Pattern for hybrid operations
return redisOperation()
    .chain(result -> {
        ContextInternal ctx = ContextInternal.current();
        ContextInternal duplicated = ctx.duplicate();
        return mongoOperation().runOn(duplicated);
    });
```

## Startup Initialization Pattern

### Use @Observes StartupEvent for Database Index Creation

**Pattern for ensuring indexes exist before application starts:**

```java
@ApplicationScoped
public class EntityStateSnapshotIndexInitializer {
    @Inject
    MongoClient mongoClient;

    @ConfigProperty(name = "quarkus.mongodb.database")
    String databaseName;

    void onStart(@Observes StartupEvent ev) {
        // Check if index exists
        // Create if missing
        // Fail-fast if creation fails
    }
}
```

**Why This Pattern:**
- Ensures indexes exist before application starts accepting requests
- Fail-fast behavior prevents runtime errors
- Idempotent (checks existence before creating)
- Uses dependency injection for configuration

**Key Design Decisions:**
1. Use `@Observes StartupEvent` for guaranteed execution
2. Inject `MongoClient` and config (don't hardcode)
3. Check existence before creating (idempotent)
4. Log clearly (✅/❌ emojis for visibility)
5. Throw exception on failure (fail-fast)

## MongoDB Panache Patterns

### Field Naming in Queries (CRITICAL - ALWAYS FOLLOW)

**RULE:** Panache MongoDB queries require **MongoDB field names** (PascalCase from @BsonProperty), NOT Java field names (camelCase)

#### Sort Parameters
```java
// ✅ CORRECT - MongoDB field name
Sort.descending("UpdatedOn")  // matches @BsonProperty("UpdatedOn")

// ❌ WRONG - Java field name (MongoDB ignores sort silently!)
Sort.descending("updatedOn")
```

#### Query Filters
```java
// ✅ CORRECT - MongoDB field name
find("OwnerId = :ownerId", sort, params)

// ❌ WRONG - Java field name (returns wrong results)
find("ownerId = :ownerId", sort, params)
```

#### PanacheQL Limitations
**CANNOT handle multiple conditions on same field:**

```java
// ❌ WRONG - Creates duplicate JSON keys, only applies one condition
"UpdatedOn >= :from and UpdatedOn <= :to"

// ✅ CORRECT - Use native MongoDB syntax
"{'UpdatedOn': {$gte: :from, $lte: :to}}"
```

### Query Best Practices

**Simple queries:** Use PanacheQL with MongoDB field names
```java
find("AssetType = :type", params)
```

**Complex queries:** Use native MongoDB syntax with JSON
```java
find("{'UpdatedOn': {$gte: :from}, 'AssetType': :type}", params)
```

**Range queries:** ALWAYS use native syntax
```java
find("{'field': {$gte: :min, $lte: :max}}", params)
```

### Debugging Queries

Enable MongoDB command logging:
```properties
%test.quarkus.log.category."org.mongodb.driver.protocol.command".level=DEBUG
%test.quarkus.log.category."io.quarkus.mongodb.panache.common.reactive.runtime".level=DEBUG
```

**Common Pitfall:** Tests passing with wrong field names because MongoDB silently ignores unknown fields

**Verification:** Always check MongoDB query logs during development

### Entity Annotations

```java
@MongoEntity(collection = "entities")
public class MyEntity extends ReactivePanacheMongoEntity {
    
    // ✅ CORRECT - Explicit field name
    @BsonProperty("FieldName")
    private String fieldName;
    
    // ✅ CORRECT - No annotation if not needed
    private String anotherField;
    
    // ❌ WRONG - Empty annotation causes NPE
    @BsonProperty()
    private String badField;
}
```

### Reactive Repositories
```java
@ApplicationScoped
public class MyEntityRepository implements ReactivePanacheMongoRepository<MyEntity, ObjectId> {
    
    public Uni<MyEntity> findByBusinessKey(String key) {
        return find("BusinessKey", key).firstResult();
    }
}
```

## SSE (Server-Sent Events) Exception Handling

### Problem
Validation errors in SSE endpoints returning `Multi<T>` get wrapped in 500 Internal Server Error instead of proper HTTP status codes (400, 404, etc.)

### Root Cause
Once SSE stream starts, HTTP headers are already sent - exceptions during streaming cannot change status code

### Solution 1: GlobalStreamExceptionMapper (Typed SSE Error Events — PREFERRED)

**From store-utils `org.fourpm.utils.sse`** — converts exceptions into typed error DTOs that flow through the SSE stream itself.

**Architecture:**
```
Server: Exception → GlobalStreamExceptionMapper.withErrorRecovery()
            → SseErrorDetail(error, errorType, statusCode)
            → DTO.ofError(error, errorType, statusCode)  // Error travels AS a normal SSE event
            → Client receives typed DTO with error fields populated

Client: Multi<T extends SseErrorCarrier> → SseErrorExtractor.isErrorEvent()
            → SseErrorExtractor.toException()  // Reconstructs original exception
```

**Three Components:**

1. **`GlobalStreamExceptionMapper`** (server-side) — wraps Multi with error recovery
```java
// Resource layer — wrap every SSE endpoint
return GlobalStreamExceptionMapper.withErrorRecovery(
    cdcStreamService.streamEvents(streamId, lastEventId),
    detail -> CDCEventDto.ofError(detail.error(), detail.errorType(), detail.statusCode()));
```

2. **`SseErrorCarrier`** (shared interface) — DTOs implement to carry error fields
```java
// Every SSE DTO must implement SseErrorCarrier
public interface SseErrorCarrier {
    String error();          // Error message
    String errorType();      // Exception class name (e.g., "EntityNotFoundException")
    Integer errorStatusCode(); // HTTP status code (e.g., 404)
    default boolean isStreamError(); // true when error fields are populated
}
```

3. **`SseErrorExtractor`** (client-side) — reconstructs exceptions from error events
```java
// Test client wraps Multi with error detection
static <T extends SseErrorCarrier> Multi<T> withErrorDetection(Multi<T> stream) {
    return stream.onItem().invoke(event -> {
        if (SseErrorExtractor.isErrorEvent(event)) {
            throw SseErrorExtractor.toException(event);  // Reconstructs original exception
        }
    });
}
```

**DTO Pattern — every SSE DTO needs `ofError()` factory:**
```java
public record FullEntityCDCEventDto(...) implements SseErrorCarrier {
    // Normal constructor for data events
    // Error factory for error events
    public static FullEntityCDCEventDto ofError(String error, String errorType, int statusCode) {
        return new FullEntityCDCEventDto(null, null, null, null, null, null, null, null, 0, null, null,
            error, errorType, statusCode);
    }
}
```

**Status Code Mapping** (in `GlobalStreamExceptionMapper.resolveStatusCode()`):
- `EntityNotFoundException` → 404
- `IllegalArgumentException` → 400
- `IllegalStateException` → 409 (if contains "conflict"/"duplicate") or 400
- Other → 500

**Why this is preferred over @ServerExceptionMapper for SSE:**
- HTTP headers already sent when stream starts — can't change status code
- Error travels as a typed DTO event, not an HTTP error response
- Client-side can reconstruct the original exception type
- Works with typed REST clients (not just REST-assured)

### Solution 2: @ServerExceptionMapper (HTTP Endpoints — Non-SSE)

For standard REST endpoints (non-SSE) that return `Uni<T>` or synchronous responses.

#### Global Exception Mappers (Recommended)
Create dedicated class for handling exceptions across ALL resources:

```java
@ApplicationScoped
public class GlobalExceptionMappers {
    
    @ServerExceptionMapper
    public Response handleWebApplicationException(WebApplicationException ex) {
        return Response.status(ex.getResponse().getStatus())
            .entity(Map.of("error", ex.getMessage()))
            .build();
    }
    
    @ServerExceptionMapper
    public Response handleInvalidDataFetch(InvalidDataFetchException ex) {
        return Response.status(Response.Status.NOT_FOUND)
            .entity(Map.of("error", ex.getMessage()))
            .build();
    }
    
    @ServerExceptionMapper
    public Response handleMongoWriteException(MongoWriteException ex) {
        if (ex.getError().getCode() == 11000) {  // Duplicate key
            return Response.status(Response.Status.CONFLICT)
                .entity(Map.of("error", "Duplicate key error"))
                .build();
        }
        return Response.status(Response.Status.INTERNAL_SERVER_ERROR)
            .entity(Map.of("error", "Database error"))
            .build();
    }
    
    @ServerExceptionMapper
    public Response handleIllegalArgument(IllegalArgumentException ex) {
        return Response.status(Response.Status.BAD_REQUEST)
            .entity(Map.of("error", ex.getMessage()))
            .build();
    }
}
```

#### Local Exception Mappers (Not Recommended)
`@ServerExceptionMapper` methods INSIDE a Resource class only handle exceptions from THAT class

**Best Practice:** Use global mappers for common exception types, local mappers only for resource-specific exceptions

### Status Code Mapping
- `InvalidDataFetchException` → 404 NOT FOUND
- `MongoWriteException` (duplicate key code 11000) → 409 CONFLICT
- `WebApplicationException` → Use status from exception response
- `IllegalArgumentException` → 400 BAD REQUEST
- Generic `Exception` → 500 INTERNAL SERVER ERROR

### Validation Pattern
Perform validation by throwing exceptions BEFORE SSE stream starts:

```java
@GET
@Path("/stream")
@Produces(MediaType.SERVER_SENT_EVENTS)
public Multi<String> streamData(@QueryParam("id") Long id) {
    // Validation throws exception - intercepted by GlobalExceptionMappers
    if (id == null) {
        throw new WebApplicationException(
            "ID is required",
            Response.Status.BAD_REQUEST
        );
    }
    
    return service.streamData(id);
}
```

**CRITICAL:** Do NOT create both global and local mappers for the same exception type

**Inheritance Limitation:** `@ServerExceptionMapper` in base classes has CDI injection issues - global mappers are recommended

## SSE Endpoint Pattern (Complete Implementation)

### Complete Pattern with Client Instructions

```java
@GET
@Path("/stream/{streamId}")
@Produces(MediaType.SERVER_SENT_EVENTS)
public Multi<String> streamChanges(
        @PathParam("streamId") String streamId,
        @Context SseEventSink eventSink,
        @Context Sse sse) {

    // Validation - throws exceptions caught by GlobalExceptionMappers
    StreamSubscription subscription = subscriptionService
        .getSubscription(streamId)
        .await().indefinitely();

    // Send initial connection confirmation
    OutboundSseEvent connectEvent = sse.newEventBuilder()
        .name("connected")
        .data(String.class, formatMessage("connected", streamId, "Stream active"))
        .build();
    eventSink.send(connectEvent);

    // Return reactive stream
    return cdcEventPublisher.consumeEvents(streamId)
        .map(event -> formatEvent(event));
}

private String formatEvent(CDCEvent event) {
    return String.format(
        "event: cdc\ndata: {\"id\":\"%s\",\"type\":\"%s\",...}\n\n",
        event.eventId(),
        event.eventType()
    );
}
```

### Client-Side Usage Documentation

**JavaScript EventSource:**
```javascript
const eventSource = new EventSource('/api/cdc/stream/stream-123');

// Listen for connection confirmation
eventSource.addEventListener('connected', (e) => {
    console.log('Stream connected:', JSON.parse(e.data));
});

// Listen for CDC events
eventSource.addEventListener('cdc', (e) => {
    const event = JSON.parse(e.data);
    console.log('CDC event:', event);
});

// Handle errors
eventSource.onerror = (error) => {
    console.error('Stream error:', error);
    // Browser automatically retries
};

// Clean up
eventSource.close();
```

### Testing SSE Endpoints

Use REST-assured for blackbox testing:
```java
@Test
void testStreamChanges_ReceivesMultipleEvents() {
    createTestEntities(5);

    given()
        .contentType(ContentType.JSON)
        .accept(MediaType.SERVER_SENT_EVENTS)
    .when()
        .get("/api/cdc/stream/" + streamId)
    .then()
        .statusCode(200)
        .contentType(MediaType.SERVER_SENT_EVENTS)
        .body(containsString("event: connected"))
        .body(containsString("event: cdc"));
}
```

## REST Resource Layer Design Principles (MANDATORY)

### 1. GlobalExceptionMappers Pattern (NEVER VIOLATE)

**RULE:** REST Resources NEVER manually handle exceptions with try-catch or `.onFailure().recoverWithItem()`

#### Correct Pattern
```java
// ✅ CORRECT - Return DTO directly, throw exceptions
@GET
@Path("/{id}")
public Uni<EntityDto> getEntity(@PathParam("id") Long id) {
    return service.fetchById(id)
        .map(entity -> entity.toDto());
    // GlobalExceptionMappers automatically converts exceptions
}

@DELETE
@Path("/{id}")
public Uni<Void> deleteEntity(@PathParam("id") Long id) {
    return service.deleteById(id)
        .onItem().transform(deleted -> {
            if (!deleted) {
                throw new InvalidDataFetchException("Entity not found: " + id);
            }
            return null;
        });
}

@POST
@Path("/")
@org.jboss.resteasy.reactive.ResponseStatus(201)
public Uni<EntityDto> createEntity(EntityDto dto) {
    if (dto.id() != null) {
        throw new jakarta.ws.rs.WebApplicationException(
            "ID must be null for creation",
            Response.Status.BAD_REQUEST
        );
    }
    return service.create(dto)
        .map(entity -> entity.toDto());
}
```

#### Wrong Pattern (NEVER DO THIS)
```java
// ❌ WRONG - Manual exception handling
@GET
@Path("/{id}")
public Uni<Response> getEntity(@PathParam("id") Long id) {
    return service.fetchById(id)
        .onItem().transform(entity -> Response.ok(entity.toDto()).build())
        .onFailure(InvalidDataFetchException.class).recoverWithItem(failure ->
            Response.status(404).entity(Map.of("error", failure.getMessage())).build()
        );
}
```

### 2. Return Types in REST Resources

**RULE:** Return DTOs or Void, NEVER Response objects (except SSE streams)

- `Uni<EntityDto>` for GET/POST/PUT returning data
- `Uni<Void>` for DELETE/POST/PUT with no response body (204 No Content)
- `Multi<String>` for SSE streams only
- Use `@org.jboss.resteasy.reactive.ResponseStatus(201)` for 201 Created responses

### 3. Service Layer Exception Policy

**Services throw domain exceptions, Resources catch NOTHING**

```java
// Service Layer
public Uni<Entity> fetchById(Long id) {
    return Entity.<Entity>findById(id)
        .onItem().ifNull().failWith(() ->
            new InvalidDataFetchException("Entity not found: " + id)
        );
}

public Uni<Void> addRelationship(Long parentId, Long childId) {
    if (alreadyLinked) {
        throw new IllegalStateException("Child already linked to parent");
    }
    // GlobalExceptionMappers converts IllegalStateException → 409
}

// Resource Layer
public Uni<EntityDto> getEntity(@PathParam("id") Long id) {
    return service.fetchById(id).map(e -> e.toDto());
    // Exceptions propagate automatically to GlobalExceptionMappers
}
```

## REST Client Error Handling (For Client Projects)

### Default Behavior (Already Works!)

MicroProfile REST Client automatically throws exceptions for HTTP status >= 400:
- Returns `jakarta.ws.rs.WebApplicationException` or subclasses
- No configuration needed
- Can be disabled with `quarkus.rest-client.{api-name}.disable-default-mapper=true`

### 1. @ClientExceptionMapper (Recommended)

Map specific HTTP status codes to custom exceptions per API interface:

```java
@Path("/store/connector")
@RegisterRestClient
public interface ConnectorApi {

    @DELETE
    @Path("/{id}")
    Uni<Void> deleteConnector(@PathParam("id") Long id);

    @GET
    @Path("/{id}")
    Uni<ConnectorDto> getConnectorById(@PathParam("id") Long id);

    @ClientExceptionMapper
    static RuntimeException toException(Response response) {
        int status = response.getStatus();

        if (status == 404) {
            return new InvalidDataFetchException("Connector not found");
        }
        if (status == 409) {
            String errorMsg = response.readEntity(String.class);
            return new IllegalStateException(extractMessage(errorMsg));
        }
        return null; // Let other mappers handle it
    }

    private static String extractMessage(String json) {
        // Parse {"error": "message"} response
        if (json != null && json.contains("\"error\"")) {
            return json.replaceAll(".*\"error\"\\s*:\\s*\"([^\"]+)\".*", "$1");
        }
        return json;
    }
}
```

**Benefits:**
- Clean, declarative syntax
- Defined inline with API interface
- No separate @Provider classes
- Can access Response body and Method parameter

### 2. ResponseExceptionMapper (Global)

Apply same error handling across ALL REST clients:

```java
@Provider  // Available to ALL REST clients
public class GlobalClientExceptionMapper implements ResponseExceptionMapper<RuntimeException> {

    @Override
    public RuntimeException toThrowable(Response response) {
        int status = response.getStatus();
        String errorMsg = response.readEntity(String.class);

        if (status == 404) {
            return new InvalidDataFetchException(extractMessage(errorMsg));
        }
        if (status == 409) {
            return new IllegalStateException(extractMessage(errorMsg));
        }
        return null;
    }

    @Override
    public int getPriority() {
        return 100; // Lower values execute first
    }
}
```

### 3. Blocking Operations in Exception Mappers

**CRITICAL for Reactive Clients:** Reading Response entity on event loop throws `BlockingNotAllowedException`

**Solution:**
```java
@Provider
@Blocking  // Execute on worker thread, not event loop
public class MyResponseExceptionMapper implements ResponseExceptionMapper<RuntimeException> {
    @Override
    public RuntimeException toThrowable(Response response) {
        response.readEntity(String.class); // Now allowed
        return new RuntimeException("Error: " + response.getStatus());
    }
}
```

### 4. Reactive Client Exception Wrapping

**Known Issue:** Quarkus reactive REST client wraps `WebApplicationException` in `ClientWebApplicationException` with original as cause

**Test Pattern:**
```java
@Test
void testDeleteConnector_LinkedToTopology_Returns409() {
    try {
        connectorClient.deleteConnector(connectorId)
            .await().indefinitely();
        fail("Should have thrown exception");
    } catch (Exception e) {
        // Check BOTH direct exception AND cause
        assertTrue(
            e instanceof IllegalStateException ||
            e.getCause() instanceof IllegalStateException,
            "Expected IllegalStateException but got: " + e
        );
        assertTrue(e.getMessage().contains("linked to topology"));
    }
}
```

### 5. Testing Strategy - Typed Client vs REST-assured

**Hybrid Approach (Recommended):**
- **Success tests:** Use typed client for clean, type-safe assertions
- **Error tests:** Use REST-assured for simpler HTTP status validation
- **SSE tests (TYPED DTO):** Use typed client when server returns `Multi<DtoClass>` ✅
- **SSE tests (RAW STRING):** Use REST-assured only for low-level SSE protocol testing

```java
// Success test - Typed client
@Test
void testGetConnector_Success() {
    ConnectorDto result = connectorClient.getConnectorById(connectorId)
        .await().indefinitely();
    assertNotNull(result);
    assertEquals(connectorId, result.id());
}

// Error test - REST-assured
@Test
void testDeleteConnector_LinkedToTopology_Returns409() {
    given()
        .contentType(ContentType.JSON)
    .when()
        .delete(BASE_PATH + "/" + connectorId)
    .then()
        .statusCode(409)
        .body("error", containsString("linked to topology"));
}
```

### 6. Typed REST Client SSE Streaming Pattern ⭐ CRITICAL

**Rule:** When server endpoint returns `Multi<DtoClass>`, the typed client MUST match the signature exactly.

**Server Endpoint:**
```java
@GET
@Path("/{streamId}/events")
@Produces(MediaType.SERVER_SENT_EVENTS)
@RestStreamElementType(MediaType.APPLICATION_JSON)
public Multi<CDCEventDto> streamEvents(
    @PathParam("streamId") String streamId,
    @HeaderParam("Last-Event-ID") String lastEventId) {

    return cdcStreamService.streamEvents(streamId, lastEventId);
}
```

**Typed REST Client (MUST match):**
```java
@Path("/store/streams")
@RegisterRestClient
public interface CDCStreamApi {

    @GET
    @Path("/{streamId}/events")
    @Produces(MediaType.SERVER_SENT_EVENTS)
    @RestStreamElementType(MediaType.APPLICATION_JSON)  // CRITICAL!
    Multi<CDCEventDto> streamEvents(@PathParam("streamId") String streamId);
}
```

**Integration Test Pattern:**
```java
@Test
void testStreamEvents_BasicSSE_StreamsEvents() {
    // Arrange: Register stream
    StreamSubscriptionDto subscription = cdcClient.registerStream(request)
        .await().indefinitely();

    // Publish events to Redis
    for (int i = 1; i <= 3; i++) {
        BusinessEntity entity = TestDataFactory.createPropertyBusinessEntity("Property_" + i, avroSchemaService);
        CDCEvent event = CDCEvent.change(subscription.streamId(), entity, ChangeType.CREATED);
        eventPublisher.publishEvent(event).await().atMost(Duration.ofSeconds(5));
    }

    // Act: Stream events via SSE using typed client (Multi<CDCEventDto>)
    List<CDCEventDto> sseEvents = cdcClient.streamEvents(subscription.streamId())
        .collect().asList()
        .await().atMost(Duration.ofSeconds(3));

    // Assert: Verify typed DTO objects (NOT JSON strings!)
    assertEquals(3, sseEvents.size(), "Should receive exactly 3 SSE events");

    for (CDCEventDto event : sseEvents) {
        assertEquals(subscription.streamId(), event.streamId());
        assertEquals("CREATED", event.changeType());
        assertNotNull(event.payload(), "Should have AVRO payload");
        assertNotNull(event.eventId(), "Should have Redis message ID");
        assertTrue(event.timestamp() > 0, "Should have valid timestamp");
    }
}
```

**Full Round-Trip Validation Pattern:**
```java
@Test
void testStreamEvents_FullRoundTrip_DeserializesAVRO() {
    // Stream events
    List<CDCEventDto> sseEvents = cdcClient.streamEvents(streamId)
        .collect().asList()
        .await().atMost(Duration.ofSeconds(3));

    // Get metadata for AVRO deserialization
    EntityTypeMetadata metadata = (EntityTypeMetadata)
        EntityTypeMetadata.findById(PROPERTY_TYPE).await().indefinitely();

    // Full round-trip: CDCEventDto → Base64 decode → AVRO bytes → Property POJO
    CDCEventDto firstEvent = sseEvents.get(0);
    byte[] payloadBytes = Base64.getDecoder().decode(firstEvent.payload());
    Property property = avroSchemaService.deserializeEntityData(
        payloadBytes,
        metadata.schemaRegistryId,
        Property.class
    );

    // Verify actual domain object
    assertNotNull(property);
    assertTrue(property.id.startsWith("Property_"));
    assertEquals(PropertyStatus.AVAILABLE, property.status);
}
```

**Key Points:**
1. **@RestStreamElementType(APPLICATION_JSON)** - CRITICAL annotation for JSON deserialization
2. **Server/Client signature match** - Both must return `Multi<DtoClass>`
3. **Automatic JSON handling** - Quarkus handles SSE protocol + JSON serialization
4. **DO NOT use REST-assured** - When server returns typed DTOs, use typed client
5. **Property field access** - Test model classes use public fields (`.id` not `.getId()`)
6. **Panache findById() casting** - Must cast: `(EntityTypeMetadata) EntityTypeMetadata.findById(...)`

**Common Mistakes:**
```java
// ❌ WRONG - Client returns Multi<String> when server returns Multi<DtoClass>
Multi<String> streamEvents(@PathParam("streamId") String streamId);

// ❌ WRONG - Missing @RestStreamElementType annotation
@Produces(MediaType.SERVER_SENT_EVENTS)
Multi<CDCEventDto> streamEvents(...);  // Will fail to deserialize!

// ❌ WRONG - Using REST-assured for typed DTO streams
Response response = given()
    .accept(MediaType.SERVER_SENT_EVENTS)
.when()
    .get("/streams/" + streamId + "/events")
.then()
    .statusCode(200)
    .extract().response();
String body = response.getBody().asString();  // Manual JSON parsing - anti-pattern!

// ✅ CORRECT - Use typed client directly
List<CDCEventDto> events = cdcClient.streamEvents(streamId)
    .collect().asList()
    .await().atMost(Duration.ofSeconds(3));
```

### 7. E2E SSE Testing with Standalone Vert.x WebClient

**Context:** E2E tests (`@QuarkusIntegrationTest`) run against Docker containers where CDI context is unavailable. Typed REST clients cannot be used.

**Solution:** Use standalone Vert.x WebClient (`SseTestClient`) — creates its own Vert.x instance.

```java
// SseTestClient.java - standalone, no CDI
public class SseTestClient implements AutoCloseable {
    public static SseTestClient create(String host, int port);
    public List<String> collectEvents(String path, Duration timeout);  // SSE "data:" lines
    public HttpResponse<Buffer> sendGet(String path, Duration timeout); // Raw response
}
```

**Why Vert.x WebClient works for E2E SSE:**
- Finite SSE streams (list endpoints) drain and complete → `.send()` resolves
- Creates standalone Vert.x instance (no Quarkus CDI required)
- Supports timeout-based collection for streams that may not complete

**Decision Matrix — SSE Testing Tool Selection:**

| Context | CDI Available | Tool | Why |
|---------|--------------|------|-----|
| Integration test (`@QuarkusTest`) | Yes | Typed REST client | Type-safe, auto-deserializes DTOs |
| E2E test (`@QuarkusIntegrationTest`) | No | SseTestClient (Vert.x) | Standalone, SSE protocol verification |
| E2E basic check | No | REST-assured | Status codes, content-type only |

### 8. Bootstrap Mode Entity Type Registration (E2E Pattern)

**Problem:** In E2E tests, Schema Registry DevService starts empty — `TestSchemaRegistration` `@Startup` bean doesn't run in native Docker containers.

**Solution:** Use `EntityTypeRegistrationRequest.avroSchema` field for bootstrap mode.

```java
// E2E test sends avroSchema inline — schema registered TO registry
Map<String, Object> request = new LinkedHashMap<>();
request.put("typeName", "org.fourpm.entitystore.entity.Property");
request.put("avroSchema", TestDataFactory.getPropertySchemaJson(
    "org.fourpm.entitystore.entity", "Property"));
// ... other fields

// POST /store/entity-types/register → 201 (not 500!)
```

**Before bootstrap:** Tests accepted 500 (empty registry) and 404 (no entity type) — testing nothing meaningful.

**After bootstrap:** Tests verify the actual registration → stream → unregister workflow end-to-end.

## Entity Design Patterns

### Dual Versioning
Implement both:
1. **Schema versioning** - Structure evolution
2. **Optimistic locking** - Concurrent access control

### Cache Patterns
Use write-through caching for high-performance access with persistence backing

### UUID Strategy
Design stable, deterministic IDs based on business keys rather than random generation

## RediSearch Module Best Practices

### Indexing is Synchronous
- RediSearch indexing is **synchronous** for new writes and modifications
- No delays or waits needed after HSET operations
- Avoid unnecessary `Thread.sleep()` waits

### FT.DROPINDEX DD Option
**Always use DD=true** to delete underlying hash documents:

```java
// ✅ CORRECT
ftDropIndex(indexName, true)  // Deletes index AND documents

// ❌ WRONG - Documents persist and pollute tests
ftDropIndex(indexName, false)
```

**Test Isolation:** Without DD option, hash documents persist after index drop and get re-indexed when new indexes are created

### Background Re-indexing
Only bulk re-indexing of **existing** documents is asynchronous, not new writes

### Verify Documentation
Always check official Redis documentation instead of assuming timing behavior

## Maven Failsafe Plugin (E2E Tests)

### Plugin-Level vs Execution-Level Configuration (CRITICAL)

**Problem:** `<configuration>` nested inside `<execution>` only applies during lifecycle runs (`mvn verify`). Direct goal invocation (`mvn failsafe:integration-test`) ignores execution-scoped config.

**Fix:** Place shared configuration (`<includes>`, `<argLine>`, `<systemPropertyVariables>`) at the **plugin level**, not inside `<execution>`.

```xml
<!-- ✅ CORRECT - Plugin-level config applies to ALL invocations -->
<plugin>
    <artifactId>maven-failsafe-plugin</artifactId>
    <configuration>
        <includes>
            <include>**/*E2EIT.java</include>
        </includes>
    </configuration>
    <executions>
        <execution>
            <goals>
                <goal>integration-test</goal>
                <goal>verify</goal>
            </goals>
        </execution>
    </executions>
</plugin>

<!-- ❌ WRONG - Execution-scoped config ignored by direct invocation -->
<plugin>
    <artifactId>maven-failsafe-plugin</artifactId>
    <executions>
        <execution>
            <goals>...</goals>
            <configuration>
                <includes>...</includes>  <!-- Only applies via mvn verify -->
            </configuration>
        </execution>
    </executions>
</plugin>
```

### Two Goals Required: integration-test + verify

Both goals are needed for a complete run:
- **`failsafe:integration-test`** — actually runs the tests
- **`failsafe:verify`** — reads reports and fails the build on test failures

Without `verify`, test failures are silently swallowed (written to report but build succeeds).
Without `integration-test`, `verify` has nothing to check.

```bash
# Correct E2E-only command (no lifecycle overhead)
./mvnw failsafe:integration-test failsafe:verify -Dnative -Dquarkus.container-image.build=false
```

### NEVER Run clean Before E2E Tests

Running `./mvnw clean compile` wipes `target/` including `quarkus-artifact.properties` — the metadata file that E2E tests need to locate the native Docker image. If wiped, you must rebuild: `./mvnw package -DskipTests -Dnative -Dquarkus.container-image.build=true`

## Memory Triggers for Development

**BEFORE writing REST endpoint code:**
1. "Am I manually handling exceptions?" → Use GlobalExceptionMappers
2. "Am I returning Response objects?" → Return DTOs/Void
3. "Have I read the tests first?" → Read tests before refactoring
4. "Have I checked existing patterns?" → Check FeedResource/GlobalExceptionMappers
5. "Using MongoDB Panache queries?" → Use MongoDB field names (PascalCase)

**BEFORE creating REST client:**
1. "Need custom exceptions?" → Use @ClientExceptionMapper
2. "Need global error handling?" → Use ResponseExceptionMapper with @Provider
3. "Using reactive client (Uni/Multi)?" → Use @Blocking in mappers
4. "Testing error cases?" → Use REST-assured for simpler assertions
5. "Testing SSE endpoint?" → Use typed client if server returns Multi<DtoClass>, NOT REST-assured
6. "Server returns Multi<DtoClass>?" → Client MUST match signature with @RestStreamElementType
