# DevOps Environment Configuration

## Quarkus DevServices

### Overview
DevServices automatically provisions development services (databases, message brokers, etc.) for Quarkus applications during development and testing.

### Port Allocation Issues

**Problem:** "Port already allocated" errors when restarting `quarkus dev`

**Root Cause:**
- DevServices containers persist across restarts
- New sessions try to bind to already-allocated ports
- Particularly common with fixed port assignments (e.g., 8082 for Apicurio Registry)

**Solution 1: Container Reuse (Recommended)**
```properties
# Enable container sharing across dev sessions
quarkus.mongodb.devservices.shared=true
quarkus.redis.devservices.shared=true
quarkus.apicurio-registry.devservices.shared=true
```

**Solution 2: Dynamic Ports**
```properties
# Let Docker assign random available ports
quarkus.apicurio-registry.devservices.port=0
```

**Best Practice:** Combine both approaches
- `shared=true` for faster restarts
- `port=0` for Apicurio and other services to prevent conflicts

**Note:** Tests remain unaffected - they always get isolated containers

### MongoDB DevServices Configuration

**Production Config Pattern:**
```properties
# Use %prod. prefix to enable DevServices in dev/test
%prod.quarkus.mongodb.connection-string=mongodb://production-host:27017

# NO connection string needed for dev/test profiles
# DevServices automatically provides it
```

**Requirements:**
- NO explicit connection string in non-production profiles
- Authentication automatically handled by DevServices containers
- Database name configured separately

**Common Mistakes:**
```properties
# ❌ WRONG - Blocks DevServices
quarkus.mongodb.connection-string=mongodb://localhost:27017

# ✅ CORRECT - Only production
%prod.quarkus.mongodb.connection-string=mongodb://production-host:27017
```

### Redis DevServices Configuration

**Basic Setup:**
```properties
# DevServices enabled by default when dependency present
# No manual configuration needed for dev/test

# Production config
%prod.quarkus.redis.hosts=redis://production-host:6379
```

**Connection String Format:**
```properties
# Specify database number in connection string
quarkus.redis.hosts=redis://localhost:6379/0
```

**Deprecated Properties (Quarkus 3.x):**
```properties
# ❌ REMOVED - Use connection string instead
quarkus.redis.database=0

# ✅ CORRECT - Include in connection string
quarkus.redis.hosts=redis://localhost:6379/0
```

### Configuration Property Deprecations

**Removed in Quarkus 3.x:**
```properties
# ❌ No longer needed - enabled by default
quarkus.smallrye-openapi.enable
quarkus.swagger-ui.enable
quarkus.smallrye-openapi.auto-add-servers
```

**Common Typos to Watch:**
```properties
# ❌ TYPO - Should be "health" not "heath"
quarkus.mongodb.heath.enabled

# ✅ CORRECT
quarkus.mongodb.health.enabled
```

## Continuous Testing

### Quarkus Dev Mode Continuous Testing

**Enable/Disable:**
```properties
# Enable (default)
quarkus.test.continuous-testing=true

# Disable if experiencing issues
quarkus.test.continuous-testing=false
```

**Manual Control:**
- Press `r` in terminal to run tests
- Press `s` to stop continuous testing

### @Nested Classes Compatibility Issue

**Problem:** ClassCastException with @Nested JUnit 5 classes in continuous testing

**Error Pattern:**
```
java.lang.ClassCastException: Cannot cast org.example.TestClass to org.example.TestClass
```

**Root Cause:**
- Known Quarkus bug (#47671)
- @Nested classes loaded by different classloaders during hot-reload
- Issue present in Quarkus 3.28.1

**When It Occurs:**
- ONLY in `quarkus dev` continuous testing mode
- NOT in `./mvnw test`

**Solution:**
```properties
# Disable continuous testing
quarkus.test.continuous-testing=false
```

**Alternative:** Press 's' in terminal to stop continuous testing

**Impact:** Tests work perfectly via `./mvnw test` - purely a dev mode issue

### Test Count Reporting

**Maven Summary Issue:**
- Final "Tests run: N" often undercounts actual tests
- @Nested classes reported separately but not summed correctly

**Get Accurate Count:**
```bash
cat target/surefire-reports/*.txt | grep "^Tests run:" | awk '{tests+=$3} END {print tests}'
```

**Example Discrepancy:**
- Maven reported: "278 tests"
- Actual count: 427 tests

**Faster Verification:**
- Read surefire text reports instead of re-running tests
- Grep reports for quick count

## Container Runtime

### Docker vs Podman for TestContainers

**Docker (Recommended):**
- ✅ Better TestContainers compatibility
- ✅ Reliable environment detection
- ✅ No socket detection issues
- ✅ Works across all Quarkus versions

**Podman (Has Issues):**
- ❌ TestContainers caches environment detection failures
- ❌ Refuses to retry within same JVM session
- ❌ Socket detection problems even with correct config
- ❌ Version-independent issues

**Migration Decision:**
Podman → Docker resolves persistent TestContainers compatibility issues

### Podman Configuration (For Reference)

**If you must use Podman:**

#### Required Packages
```bash
sudo apt install podman podman-docker
```

#### User Lingering
```bash
loginctl enable-linger $USER
```

#### Socket Service
```bash
systemctl --user enable --now podman.socket
```

#### Environment Variables
```bash
export DOCKER_HOST=unix:///run/user/1000/podman/podman.sock
export TESTCONTAINERS_RYUK_DISABLED=true
```

#### TestContainers Configuration
Create `~/.testcontainers.properties`:
```properties
docker.host=unix:///run/user/1000/podman/podman.sock
ryuk.disabled=true
docker.client.strategy=org.testcontainers.dockerclient.UnixSocketClientProviderStrategy
```

**Note:** Despite proper configuration, Podman may still have detection issues

### CI/CD Consideration

**Important:** Integration tests work correctly in fresh CI/CD environments

**Why:**
- Fresh environment each run
- No cached detection failures
- Proper container runtime detection

**Implication:** Tests are production-ready despite local development issues

## TestContainers Integration

### Docker 29.x API Version Compatibility

**Problem:** Docker 29.x (November 2025+) requires minimum API version 1.44, but TestContainers defaults to 1.32.

**Error Pattern:**
```
IllegalStateException: Previous attempts to find a Docker environment failed.
BadRequestException (Status 400: {"message":"client version 1.32 is too old. Minimum supported API version is 1.44"})
```

**Solution:** Create `~/.docker-java.properties`:
```properties
api.version=1.44
```

**Verification:** Test logs should show:
```
GET /v1.44/info HTTP/1.1
```
Instead of `/v1.32/info`

**Alternative Solutions:**
1. System property in test code: `System.setProperty("api.version", "1.44");`
2. Maven Surefire systemPropertyVariables: `<api.version>1.44</api.version>`

**Reference:** [TestContainers Issue #11212](https://github.com/testcontainers/testcontainers-java/issues/11212)

### MongoDB TestContainers Pattern

**Critical Annotation:**
```java
@QuarkusTest
@QuarkusTestResource(value = MongoTestResource.class, restrictToAnnotatedClass = true)
public class MyRepositoryIT {
    // Integration test implementation
}
```

**Why `restrictToAnnotatedClass = true`:**
- Prevents DevServices + TestContainers class loading conflicts
- Isolates container management per test class
- Prevents test hanging during class loading

### Test Hanging Root Cause

**Problem:** Tests hang during class loading

**Root Cause:**
- Quarkus DevServices conflicts with TestContainers
- Class loading deadlock during container initialization

**Solution:**
- Use `restrictToAnnotatedClass = true` (NOT disabling DevServices globally)

### Container Lifecycle

**Per Test Class:**
- Fresh container instance
- Automatic cleanup
- Test isolation guaranteed

**Shared Containers:**
- Enabled via DevServices `shared=true`
- Only for dev mode, not tests
- Tests always get isolated containers

## Environment Detection

### TestContainers Caching

**Problem:** TestContainers caches Docker environment detection failures

**Impact:**
- Refuses to retry within same JVM session
- Persists across test runs
- Requires JVM restart to retry

**Workaround:**
- Switch to Docker from Podman
- Restart IDE/test runner

### Socket Detection

**Podman Issues:**
- May fail to detect Podman's Docker API emulation socket
- Even with correct configuration
- Inconsistent behavior

**Docker Advantages:**
- Native Docker API support
- No emulation layer
- Consistent detection

## Development Workflow

### Starting Quarkus Dev Mode

```bash
# Start with continuous testing
./mvnw quarkus:dev

# Start without continuous testing
./mvnw quarkus:dev -Dquarkus.test.continuous-testing=false
```

### DevServices Management

**Container Cleanup:**
```bash
# List running DevServices containers
docker ps | grep testcontainers

# Stop all DevServices containers
docker stop $(docker ps -q --filter "label=org.testcontainers")

# Remove all DevServices containers
docker rm $(docker ps -aq --filter "label=org.testcontainers")
```

### Port Management

**Check Port Allocation:**
```bash
# Find what's using a port
lsof -i :8082

# Kill process on port
kill -9 $(lsof -t -i :8082)
```

## Configuration Best Practices

### Profile-Based Configuration

**Pattern:**
```properties
# Default (dev/test) - DevServices active
# No connection strings needed

# Production - explicit configuration
%prod.quarkus.mongodb.connection-string=mongodb://prod-host:27017
%prod.quarkus.redis.hosts=redis://prod-host:6379
```

### Shared Containers

**When to Use:**
```properties
# ✅ Use shared=true for faster dev restarts
quarkus.mongodb.devservices.shared=true
quarkus.redis.devservices.shared=true

# ❌ Don't use for testing - always isolated
```

### Dynamic Port Assignment

**When to Use:**
```properties
# ✅ For services prone to conflicts
quarkus.apicurio-registry.devservices.port=0

# Default behavior - usually fine
quarkus.mongodb.devservices.port=0
quarkus.redis.devservices.port=0
```

## Troubleshooting Guide

### Port Already Allocated
1. Check if using `shared=true`
2. Try dynamic ports with `port=0`
3. Manually stop containers
4. Restart dev mode

### Tests Hanging
1. Check for `restrictToAnnotatedClass = true`
2. Verify Docker is running
3. Check container runtime (prefer Docker)
4. Review test logs for ClassCastException

### Container Detection Failures
1. Verify Docker is installed and running
2. Check `DOCKER_HOST` environment variable
3. Try restarting IDE/test runner
4. Consider migration from Podman to Docker

### Docker 29.x "API version too old" Error
1. Check Docker version: `docker version` (29.x+ requires API 1.44)
2. Create `~/.docker-java.properties` with `api.version=1.44`
3. Re-run tests - should now use `/v1.44/info` instead of `/v1.32/info`

### ClassCastException in Dev Mode
1. Disable continuous testing
2. Press 's' to stop tests
3. Run tests with `./mvnw test` instead
4. Remove @Nested classes if necessary

## Memory Triggers

**BEFORE starting dev mode:**
1. "Is Docker running?" → Check `docker ps`
2. "Do I need DevServices?" → Check `shared=true` config
3. "Having port conflicts?" → Use `port=0`

**WHEN tests hang:**
1. "Using TestContainers?" → Check `restrictToAnnotatedClass = true`
2. "Using Podman?" → Consider Docker migration
3. "Using @Nested classes?" → Disable continuous testing

**FOR production deployment:**
1. "Are connection strings configured?" → Use `%prod.` prefix
2. "Is DevServices disabled?" → Happens automatically in prod
3. "Are ports configured?" → Check production properties
