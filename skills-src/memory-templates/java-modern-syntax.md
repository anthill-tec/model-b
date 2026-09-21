<!-- Model B memory template (cross-project Java language reference). Imported 2026-09-21 from the user's global memory (java-modern-syntax.md) by ruling: PRD §D5's global tier has no Pi home, so language refs ride the stack's memory templates and are scaffolded into <project>/docs/memory/. -->

# Java Modern Syntax & Features (JDK 8-25)

**Purpose**: Reference guide for writing idiomatic modern Java code. Use these patterns when generating new code.

**Last Updated**: December 2025

---

## IMPORTANT: Version Targeting Rules

**Always check the project's Maven POM for the target Java version before writing code:**

```xml
<!-- Look for these in pom.xml -->
<maven.compiler.source>21</maven.compiler.source>
<maven.compiler.target>21</maven.compiler.target>
<!-- OR -->
<java.version>21</java.version>
<!-- OR -->
<release>21</release>
```

### Version Selection Guidelines

1. **Use ONLY features available in the target version** specified in the POM
2. **When in doubt, default to the nearest LTS edition patterns:**
   - Target 8-10 → Use **Java 8 LTS** patterns
   - Target 11-16 → Use **Java 11 LTS** patterns
   - Target 17-20 → Use **Java 17 LTS** patterns
   - Target 21-24 → Use **Java 21 LTS** patterns
   - Target 25+ → Use **Java 25 LTS** patterns

3. **Preview features require explicit enable** - avoid unless project explicitly enables them:
   ```xml
   <compilerArgs>--enable-preview</compilerArgs>
   ```

4. **Safe defaults by LTS:**

   | LTS | Safe to Use |
   |-----|-------------|
   | 8 | Lambdas, Streams, Optional, method references |
   | 11 | + `var`, `isBlank()`, `lines()`, `strip()`, HttpClient |
   | 17 | + Records, Sealed classes, Text blocks, Pattern matching instanceof, Switch expressions |
   | 21 | + Pattern matching switch, Record patterns, Virtual threads, Sequenced collections |
   | 25 | + Unnamed variables `_`, Stream Gatherers, Scoped Values, Flexible constructors |

---

## Quick Reference: Feature Availability by LTS

| Feature | Introduced | Finalized | LTS Available |
|---------|------------|-----------|---------------|
| Lambdas & Streams | 8 | 8 | 8, 11, 17, 21, 25 |
| `var` keyword | 10 | 10 | 11, 17, 21, 25 |
| Text Blocks (`"""`) | 13 preview | 15 | 17, 21, 25 |
| Records | 14 preview | 16 | 17, 21, 25 |
| Sealed Classes | 15 preview | 17 | 17, 21, 25 |
| Pattern Matching instanceof | 14 preview | 16 | 17, 21, 25 |
| Switch Expressions | 12 preview | 14 | 17, 21, 25 |
| Pattern Matching switch | 17 preview | 21 | 21, 25 |
| Record Patterns | 19 preview | 21 | 21, 25 |
| Virtual Threads | 19 preview | 21 | 21, 25 |
| Sequenced Collections | 21 | 21 | 21, 25 |
| Unnamed Variables (`_`) | 21 preview | 22 | 25 |
| Stream Gatherers | 22 preview | 25 | 25 |
| Flexible Constructor Bodies | 22 preview | 25 | 25 |
| Scoped Values | 20 preview | 25 | 25 |
| Primitive Patterns | 23 preview | 25+ | 25+ |

---

## 1. Lambda Expressions (Java 8+)

### Basic Syntax
```java
// Single parameter - parentheses optional
list.forEach(item -> process(item));

// Multiple parameters
map.forEach((key, value) -> System.out.println(key + ": " + value));

// Method reference - prefer when lambda just calls a method
list.forEach(System.out::println);
list.stream().map(String::toUpperCase);
users.stream().map(User::getName);

// Constructor reference
Supplier<List<String>> listFactory = ArrayList::new;
Function<String, User> userFactory = User::new;
```

### Unused Lambda Parameters (Java 22+)
```java
// Use underscore for unused parameters
map.forEach((_, value) -> process(value));
biFunction.apply((_, _) -> result);

// Before Java 22 - use descriptive name with underscore prefix
map.forEach((_key, value) -> process(value));  // Java 21 and earlier
```

---

## 2. Stream API (Java 8+)

### Collection Operations
```java
// Filtering and mapping
List<String> names = users.stream()
    .filter(user -> user.isActive())
    .map(User::getName)
    .toList();  // Java 16+ - prefer over .collect(Collectors.toList())

// Collecting to specific types
Set<String> nameSet = users.stream()
    .map(User::getName)
    .collect(Collectors.toSet());

Map<Long, User> userMap = users.stream()
    .collect(Collectors.toMap(User::getId, Function.identity()));

// Grouping
Map<String, List<User>> byDepartment = users.stream()
    .collect(Collectors.groupingBy(User::getDepartment));
```

### Stream Enhancements (Java 9+)
```java
// takeWhile/dropWhile (Java 9)
List<Integer> result = Stream.iterate(1, n -> n + 1)
    .takeWhile(n -> n < 10)
    .toList();

// ofNullable (Java 9) - creates 0 or 1 element stream
Stream.ofNullable(nullableValue)
    .forEach(this::process);

// iterate with predicate (Java 9)
Stream.iterate(1, n -> n < 100, n -> n * 2)
    .toList();  // [1, 2, 4, 8, 16, 32, 64]
```

### Stream with Optional (Java 9+)
```java
// flatMap with Optional.stream() - filter out empty optionals
List<User> validUsers = userIds.stream()
    .map(this::findUserById)      // Stream<Optional<User>>
    .flatMap(Optional::stream)     // Stream<User> - empties removed
    .toList();
```

### Stream Gatherers (Java 25+)
```java
// Custom intermediate operations
import java.util.stream.Gatherers;

// Fixed window batching
List<List<Integer>> batches = numbers.stream()
    .gather(Gatherers.windowFixed(100))
    .toList();

// Concurrent mapping (for IO-bound operations)
List<Result> results = ids.stream()
    .gather(Gatherers.mapConcurrent(10, this::fetchFromApi))
    .toList();

// Sliding window
List<List<Integer>> windows = numbers.stream()
    .gather(Gatherers.windowSliding(3))
    .toList();
```

---

## 3. Local Variable Type Inference - `var` (Java 10+)

### When to Use
```java
// Good - obvious type from right side
var users = new ArrayList<User>();
var map = new HashMap<String, List<Integer>>();
var response = client.send(request);
var stream = Files.lines(path);

// Good - with try-with-resources
try (var reader = new BufferedReader(new FileReader(file))) {
    var line = reader.readLine();
}

// Good - in for loops
for (var entry : map.entrySet()) {
    var key = entry.getKey();
    var value = entry.getValue();
}
```

### When NOT to Use
```java
// Bad - type not obvious
var result = process(data);  // What type is result?
var x = getSomething();      // Unclear

// Bad - primitive type promotion issues
var value = 1;               // int, not long
var number = 1.0;            // double, not float

// Cannot use with
var x;                       // No initializer
var x = null;                // Cannot infer type
var x = () -> {};            // Lambda needs target type
var x = {1, 2, 3};           // Array initializer needs type
```

---

## 4. Text Blocks (Java 15+)

### Basic Usage
```java
// Multi-line strings - no escaping needed
String json = """
    {
        "name": "John",
        "age": 30,
        "active": true
    }
    """;

String html = """
    <html>
        <body>
            <h1>Hello World</h1>
        </body>
    </html>
    """;

String sql = """
    SELECT id, name, email
    FROM users
    WHERE status = 'ACTIVE'
    ORDER BY name
    """;
```

### String Interpolation with `formatted()`
```java
String template = """
    {
        "userId": "%s",
        "name": "%s",
        "email": "%s"
    }
    """.formatted(user.getId(), user.getName(), user.getEmail());

// With numbered placeholders
String message = """
    Dear %1$s,
    Your order #%2$d has been shipped.
    Expected delivery: %3$s
    """.formatted(name, orderId, deliveryDate);
```

### Controlling Whitespace
```java
// Trailing backslash joins lines
String singleLine = """
    This is a very long line that we want to \
    break in the source but not in the output\
    """;

// \s preserves trailing whitespace
String preserved = """
    Column1    \s
    Column2    \s
    """;

// Indentation controlled by closing delimiter position
String indented = """
        Indented content
        More content
    """;  // 4-space indent preserved
```

---

## 5. Records (Java 16+)

### Basic Record
```java
// Immutable data carrier - generates constructor, getters, equals, hashCode, toString
public record User(String id, String name, String email) {}

// Usage
var user = new User("123", "John", "john@example.com");
String name = user.name();  // Accessor methods (not getName())
```

### Records with Validation
```java
public record User(String id, String name, String email) {
    // Compact constructor for validation
    public User {
        Objects.requireNonNull(id, "id cannot be null");
        Objects.requireNonNull(name, "name cannot be null");
        if (email != null && !email.contains("@")) {
            throw new IllegalArgumentException("Invalid email");
        }
    }
}
```

### Records with Additional Methods
```java
public record Point(int x, int y) {
    // Static factory method
    public static Point origin() {
        return new Point(0, 0);
    }

    // Instance method
    public double distanceFromOrigin() {
        return Math.sqrt(x * x + y * y);
    }

    // Derived accessor
    public Point translated(int dx, int dy) {
        return new Point(x + dx, y + dy);
    }
}
```

### Local Records (Java 16+)
```java
public List<String> processData(List<User> users) {
    // Define record locally for intermediate processing
    record UserSummary(String name, int orderCount) {}

    return users.stream()
        .map(u -> new UserSummary(u.name(), u.orders().size()))
        .filter(s -> s.orderCount() > 5)
        .map(UserSummary::name)
        .toList();
}
```

---

## 6. Sealed Classes (Java 17+)

### Declaration
```java
// Sealed interface - only these can implement
public sealed interface Shape
    permits Circle, Rectangle, Triangle {
    double area();
}

// Final - cannot be extended further
public final class Circle implements Shape {
    private final double radius;
    public Circle(double radius) { this.radius = radius; }
    public double area() { return Math.PI * radius * radius; }
}

// Sealed - can define its own permitted subtypes
public sealed class Rectangle implements Shape
    permits Square {
    protected final double width, height;
    public Rectangle(double width, double height) {
        this.width = width;
        this.height = height;
    }
    public double area() { return width * height; }
}

// Non-sealed - open for extension
public non-sealed class Triangle implements Shape {
    // Can be extended by any class
}
```

### With Records (Common Pattern)
```java
public sealed interface Result<T> {
    record Success<T>(T value) implements Result<T> {}
    record Failure<T>(String error) implements Result<T> {}
}

// Usage with pattern matching
return switch (result) {
    case Success(var value) -> process(value);
    case Failure(var error) -> handleError(error);
};
```

---

## 7. Pattern Matching

### instanceof Pattern (Java 16+)
```java
// Old way
if (obj instanceof String) {
    String s = (String) obj;
    return s.length();
}

// New way - binding variable in scope when true
if (obj instanceof String s) {
    return s.length();
}

// With logical operators
if (obj instanceof String s && s.length() > 5) {
    return s.toUpperCase();
}
```

### Switch Pattern Matching (Java 21+)
```java
// Type patterns in switch
String describe(Object obj) {
    return switch (obj) {
        case Integer i -> "Integer: " + i;
        case Long l    -> "Long: " + l;
        case String s  -> "String: " + s;
        case null      -> "null value";
        default        -> "Unknown: " + obj.getClass();
    };
}

// Guarded patterns (when clause)
String categorize(Object obj) {
    return switch (obj) {
        case Integer i when i < 0  -> "negative";
        case Integer i when i == 0 -> "zero";
        case Integer i             -> "positive";
        case String s when s.isEmpty() -> "empty string";
        case String s              -> "string: " + s;
        default                    -> "other";
    };
}
```

### Record Patterns (Java 21+)
```java
// Deconstruct records in patterns
record Point(int x, int y) {}
record Line(Point start, Point end) {}

// Simple record pattern
if (obj instanceof Point(int x, int y)) {
    return x + y;
}

// Nested record patterns
String describe(Object obj) {
    return switch (obj) {
        case Line(Point(int x1, int y1), Point(int x2, int y2))
            -> "Line from (%d,%d) to (%d,%d)".formatted(x1, y1, x2, y2);
        case Point(int x, int y)
            -> "Point at (%d,%d)".formatted(x, y);
        default
            -> "Unknown";
    };
}

// With var for type inference
if (obj instanceof Point(var x, var y)) {
    // x and y are inferred as int
}
```

### Unnamed Patterns (Java 22+)
```java
// Use _ when you don't need the value
record Box<T>(T value, String label) {}

String getLabel(Object obj) {
    return switch (obj) {
        case Box(_, String label) -> label;  // Don't need the value
        default -> "no label";
    };
}

// Multiple unnamed
if (obj instanceof Point(_, var y)) {
    return y;  // Only care about y
}
```

---

## 8. Switch Expressions (Java 14+)

### Arrow Syntax (Preferred)
```java
// Expression form - returns value, no fall-through
int numDays = switch (month) {
    case JANUARY, MARCH, MAY, JULY, AUGUST, OCTOBER, DECEMBER -> 31;
    case APRIL, JUNE, SEPTEMBER, NOVEMBER -> 30;
    case FEBRUARY -> isLeapYear ? 29 : 28;
};

// With block and yield
String description = switch (status) {
    case PENDING -> "Waiting for processing";
    case ACTIVE -> {
        logAccess();
        yield "Currently active";
    }
    case COMPLETED -> "Finished";
};
```

### Exhaustiveness
```java
// With sealed types - no default needed
sealed interface Shape permits Circle, Rectangle {}

double area(Shape shape) {
    return switch (shape) {
        case Circle c    -> Math.PI * c.radius() * c.radius();
        case Rectangle r -> r.width() * r.height();
        // No default needed - compiler knows all cases covered
    };
}

// With enums - no default recommended (catches future additions)
String describe(DayOfWeek day) {
    return switch (day) {
        case MONDAY, TUESDAY, WEDNESDAY, THURSDAY, FRIDAY -> "weekday";
        case SATURDAY, SUNDAY -> "weekend";
        // No default - compiler error if enum expanded
    };
}
```

### Null Handling (Java 21+)
```java
String process(String input) {
    return switch (input) {
        case null -> "null input";
        case String s when s.isEmpty() -> "empty";
        case String s -> s.toUpperCase();
    };
}
```

---

## 9. Collection Factory Methods (Java 9+)

### Immutable Collections
```java
// List.of() - immutable, null-disallowed
List<String> list = List.of("a", "b", "c");

// Set.of() - immutable, no duplicates, null-disallowed
Set<Integer> set = Set.of(1, 2, 3);

// Map.of() - up to 10 entries
Map<String, Integer> map = Map.of(
    "one", 1,
    "two", 2,
    "three", 3
);

// Map.ofEntries() - for more than 10 entries
Map<String, Integer> largeMap = Map.ofEntries(
    Map.entry("one", 1),
    Map.entry("two", 2),
    // ... more entries
);
```

### Copying Collections (Java 10+)
```java
// Create immutable copy
List<String> immutableCopy = List.copyOf(mutableList);
Set<String> setCopy = Set.copyOf(mutableSet);
Map<K, V> mapCopy = Map.copyOf(mutableMap);

// Note: if source is already immutable, returns same reference
```

### Sequenced Collections (Java 21+)
```java
// New interfaces: SequencedCollection, SequencedSet, SequencedMap

// First/last element access
SequencedCollection<String> seq = new LinkedHashSet<>();
String first = seq.getFirst();
String last = seq.getLast();

// Add at beginning/end
seq.addFirst("new first");
seq.addLast("new last");

// Reversed view
SequencedCollection<String> reversed = seq.reversed();

// Works with List, LinkedHashSet, TreeSet, LinkedHashMap, TreeMap
List<String> list = List.of("a", "b", "c");
String first = list.getFirst();  // "a"
String last = list.getLast();    // "c"
```

---

## 10. Optional Best Practices (Java 8+)

### Creating Optional
```java
Optional<String> present = Optional.of(value);           // value must not be null
Optional<String> nullable = Optional.ofNullable(value);  // handles null
Optional<String> empty = Optional.empty();
```

### Consuming Optional
```java
// Prefer functional methods over isPresent() + get()

// Get with default
String result = optional.orElse("default");

// Get with lazy default
String result = optional.orElseGet(() -> computeDefault());

// Get or throw
User user = findUser(id).orElseThrow();  // NoSuchElementException
User user = findUser(id).orElseThrow(() -> new UserNotFoundException(id));

// Conditional execution (Java 9+)
optional.ifPresentOrElse(
    value -> process(value),
    () -> handleAbsent()
);

// Transform
Optional<String> name = findUser(id).map(User::getName);

// Chain optionals
Optional<String> city = findUser(id)
    .flatMap(User::getAddress)
    .flatMap(Address::getCity);
```

### Optional in Streams (Java 9+)
```java
// Convert Optional to Stream (0 or 1 element)
List<User> users = userIds.stream()
    .map(this::findUser)          // Stream<Optional<User>>
    .flatMap(Optional::stream)     // Stream<User>
    .toList();
```

---

## 11. Virtual Threads (Java 21+)

### Creating Virtual Threads
```java
// Simple creation
Thread vThread = Thread.startVirtualThread(() -> {
    // This runs on a virtual thread
    performBlockingIO();
});

// Using builder
Thread vThread = Thread.ofVirtual()
    .name("worker-", 1)
    .start(() -> process());

// ExecutorService with virtual threads
try (var executor = Executors.newVirtualThreadPerTaskExecutor()) {
    // Each task gets its own virtual thread
    Future<String> future = executor.submit(() -> fetchData());
}
```

### When to Use
```java
// Good - IO-bound tasks with lots of waiting
try (var executor = Executors.newVirtualThreadPerTaskExecutor()) {
    List<Future<Result>> futures = urls.stream()
        .map(url -> executor.submit(() -> fetchUrl(url)))
        .toList();
}

// Bad - CPU-bound tasks (use platform threads)
// Virtual threads don't make CPU work faster
```

---

## 12. Flexible Constructor Bodies (Java 22+ Preview, Java 25+ Final)

### Statements Before super()
```java
public class ValidatedUser extends User {
    public ValidatedUser(String id, String name, String email) {
        // Validation BEFORE calling super (Java 22+)
        Objects.requireNonNull(id, "id cannot be null");
        Objects.requireNonNull(name, "name cannot be null");
        if (!isValidEmail(email)) {
            throw new IllegalArgumentException("Invalid email: " + email);
        }

        // Now call super with validated values
        super(id, name, email);

        // Post-initialization
        this.createdAt = Instant.now();
    }
}

// Before Java 22 - required factory methods or workarounds
public class ValidatedUser extends User {
    public ValidatedUser(String id, String name, String email) {
        super(validate(id, name, email), name, email);  // Awkward
    }

    private static String validate(String id, String name, String email) {
        Objects.requireNonNull(id);
        return id;
    }
}
```

---

## 13. Modern API Improvements

### String Methods
```java
// Java 11+
"  hello  ".strip();           // "hello" (Unicode-aware trim)
"  hello  ".stripLeading();    // "hello  "
"  hello  ".stripTrailing();   // "  hello"
"   ".isBlank();               // true (whitespace only)
"ab\ncd".lines();              // Stream of "ab", "cd"
"x".repeat(3);                 // "xxx"

// Java 12+
"  hello  ".indent(4);         // Adds 4 spaces to each line
"AbCd".transform(String::toLowerCase);  // "abcd"

// Java 15+
"""
multi
line
""".stripIndent();             // Removes common leading whitespace
"formatted: %s".formatted(value);  // Like String.format()
```

### Files Methods (Java 11+)
```java
// Read/write strings directly
String content = Files.readString(path);
Files.writeString(path, content);

// With charset
String content = Files.readString(path, StandardCharsets.UTF_8);
Files.writeString(path, content, StandardCharsets.UTF_8,
    StandardOpenOption.CREATE, StandardOpenOption.TRUNCATE_EXISTING);
```

### HttpClient (Java 11+)
```java
HttpClient client = HttpClient.newHttpClient();

HttpRequest request = HttpRequest.newBuilder()
    .uri(URI.create("https://api.example.com/users"))
    .header("Content-Type", "application/json")
    .POST(HttpRequest.BodyPublishers.ofString(jsonBody))
    .build();

// Synchronous
HttpResponse<String> response = client.send(request,
    HttpResponse.BodyHandlers.ofString());

// Asynchronous
CompletableFuture<HttpResponse<String>> future = client.sendAsync(request,
    HttpResponse.BodyHandlers.ofString());
```

---

## 14. Scoped Values (Java 25+)

### Thread-Safe Value Sharing
```java
// Define scoped value (immutable, thread-safe alternative to ThreadLocal)
private static final ScopedValue<User> CURRENT_USER = ScopedValue.newInstance();

// Bind and run
ScopedValue.where(CURRENT_USER, authenticatedUser)
    .run(() -> {
        // Code here can access CURRENT_USER.get()
        processRequest();
    });

// Access in nested code
void processRequest() {
    User user = CURRENT_USER.get();  // Gets bound value
    // ...
}

// With return value
String result = ScopedValue.where(CURRENT_USER, user)
    .call(() -> {
        return processAndReturn();
    });
```

---

## 15. Code Style Guidelines

### Prefer Modern Constructs
```java
// Instead of                          // Use
Collections.unmodifiableList(list)  -> List.copyOf(list)
Arrays.asList(a, b, c)              -> List.of(a, b, c)
stream.collect(Collectors.toList()) -> stream.toList()
obj instanceof Type ? ((Type)obj)   -> obj instanceof Type t ? t
                                    -> switch expression

// String concatenation in loops
StringBuilder sb = new StringBuilder();
for (String s : list) sb.append(s); -> String.join("", list)
                                    -> list.stream().collect(joining())
```

### Null Safety
```java
// Use Optional for return types that might be absent
Optional<User> findUser(String id);

// Use Objects.requireNonNull for mandatory parameters
public void process(User user) {
    this.user = Objects.requireNonNull(user, "user cannot be null");
}

// Use @Nullable/@NonNull annotations where appropriate
```

### Record vs Class Decision
```java
// Use Record when:
// - Data is immutable
// - Identity is based on data (equals/hashCode)
// - No need for inheritance
// - Simple data carrier

// Use Class when:
// - Mutability needed
// - Complex initialization
// - Inheritance required
// - Custom equals/hashCode logic
```

---

## Sources

- [Oracle Java Documentation](https://docs.oracle.com/en/java/javase/)
- [OpenJDK JEPs](https://openjdk.org/jeps/)
- [Java 21 Features](https://www.happycoders.eu/java/java-21-features/)
- [Java 24 Features](https://www.happycoders.eu/java/java-24-features/)
- [Java 25 Features](https://www.baeldung.com/java-25-features)
- [InfoQ Java Coverage](https://www.infoq.com/java/)
- [Baeldung Java Tutorials](https://www.baeldung.com/)
