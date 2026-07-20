# Operational Commands Reference

Cross-project CLI commands for development, testing, and debugging.

---

## Docker Commands (Generic)

### Container Management
```bash
# List running containers
docker ps

# List all containers (including stopped)
docker ps -a

# View container logs
docker logs <container-id>
docker logs -f <container-id>  # Follow logs

# Stop container
docker stop <container-id>

# Remove container
docker rm <container-id>

# Remove all stopped containers
docker container prune
```

### Image Management
```bash
# List images
docker images

# Remove image
docker rmi <image-name>

# Remove all unused images
docker image prune

# Full cleanup (containers, images, networks, cache)
docker system prune -a
```

### Build Commands
```bash
# Build JVM Docker image
docker build -f src/main/docker/Dockerfile.jvm -t <org>/<name>:latest .

# Build native Docker image
docker build -f src/main/docker/Dockerfile.native -t <org>/<name>:native .

# Run container
docker run -i --rm -p 8080:8080 <org>/<name>:latest

# Run with environment variables
docker run -i --rm -p 8080:8080 \
  -e SOME_ENV_VAR=value \
  <org>/<name>:latest

# Run in background (daemon mode)
docker run -d --name <name> -p 8080:8080 <org>/<name>:latest
```

---

## MongoDB CLI Commands (Generic)

### Connection
```bash
# Connect to MongoDB
mongosh mongodb://localhost:27017/<database>

# Connect with authentication
mongosh mongodb://user:password@localhost:27017/<database>
```

### Database Operations
```bash
# List databases
mongosh --eval 'show dbs'

# List collections in database
mongosh mongodb://localhost:27017/<database> --eval 'db.getCollectionNames()'

# Query collection
mongosh mongodb://localhost:27017/<database> --eval 'db.<collection>.find().pretty()'

# Count documents
mongosh mongodb://localhost:27017/<database> --eval 'db.<collection>.countDocuments()'

# Count with filter
mongosh mongodb://localhost:27017/<database> --eval 'db.<collection>.countDocuments({field: "value"})'

# Test connection
mongosh mongodb://localhost:27017 --eval 'db.runCommand({ping:1})'
```

---

## Redis CLI Commands (Generic)

### Connection
```bash
# Connect to Redis
redis-cli -h localhost -p 6379

# Connect with password
redis-cli -h localhost -p 6379 -a <password>
```

### Key Operations
```bash
# List all keys (use cautiously in production)
redis-cli KEYS "*"

# List keys matching pattern
redis-cli KEYS "prefix:*"

# Count keys matching pattern
redis-cli KEYS "prefix:*" | wc -l

# Get key value
redis-cli GET "key"

# Delete key
redis-cli DEL "key"

# Check if key exists
redis-cli EXISTS "key"

# Get key TTL
redis-cli TTL "key"

# Set key with TTL
redis-cli SET "key" "value" EX 3600  # 1 hour
```

### Database Info
```bash
# Database size (key count)
redis-cli DBSIZE

# Memory usage
redis-cli INFO memory

# Server stats
redis-cli INFO stats

# Monitor commands in real-time (debugging)
redis-cli MONITOR
```

### RediSearch Commands
```bash
# List all indexes
redis-cli FT._LIST

# Get index info
redis-cli FT.INFO <index-name>

# Search index
redis-cli FT.SEARCH <index-name> "@field:{value}"

# Search with pagination
redis-cli FT.SEARCH <index-name> "*" LIMIT 0 10

# Drop index (with hash documents)
redis-cli FT.DROPINDEX <index-name> DD
```

---

## SSE Testing Commands (Generic)

### Curl for Server-Sent Events
```bash
# Stream SSE endpoint
curl -N -H "Accept: text/event-stream" http://localhost:8080/path/to/stream

# Stream with timeout
curl -N -m 30 -H "Accept: text/event-stream" http://localhost:8080/path/to/stream

# Stream and save to file
curl -N -H "Accept: text/event-stream" http://localhost:8080/path/to/stream > events.txt
```

**SSE Output Format:**
```
data: {"eventId":"1","type":"CREATE","timestamp":"2025-01-01T00:00:00Z"}
data: {"eventId":"2","type":"UPDATE","timestamp":"2025-01-01T00:01:00Z"}
```

---

## HTTPie Commands (Generic)

### Basic CRUD
```bash
# GET request
http GET localhost:8080/api/resource

# POST with JSON body
http POST localhost:8080/api/resource \
  field1="value1" \
  field2:=123  # :=for non-string types

# PUT request
http PUT localhost:8080/api/resource/{id} \
  field1="updated"

# DELETE request
http DELETE localhost:8080/api/resource/{id}
```

### Headers and Authentication
```bash
# Custom headers
http GET localhost:8080/api/resource \
  Authorization:"Bearer token" \
  Accept:application/json

# SSE streaming
http --stream GET localhost:8080/api/stream \
  Accept:text/event-stream
```

---

## Performance Testing (Generic)

### Apache Bench (ab)
```bash
# Simple GET test (100 requests, 10 concurrent)
ab -n 100 -c 10 http://localhost:8080/api/resource

# POST test with JSON body
ab -n 100 -c 10 -T "application/json" \
  -p request-body.json \
  http://localhost:8080/api/resource

# GET test (1000 requests, 50 concurrent)
ab -n 1000 -c 50 http://localhost:8080/api/resource/{id}
```

### Key Metrics
- **Requests per second**: Throughput
- **Time per request**: Latency (mean)
- **Failed requests**: Error rate
- **50%/95%/99% percentiles**: Tail latency

---

## Port Troubleshooting (Generic)

### Find Process Using Port
```bash
# Find what's using port 8080
lsof -i :8080

# Alternative (Linux)
ss -tlnp | grep 8080

# Kill process on port
kill -9 $(lsof -t -i:8080)
```

---

## Quarkus-Specific Commands

### Health Check Endpoints
```bash
# Comprehensive health check
curl http://localhost:8080/q/health | jq

# Liveness probe
curl http://localhost:8080/q/health/live | jq

# Readiness probe
curl http://localhost:8080/q/health/ready | jq

# Startup probe
curl http://localhost:8080/q/health/started | jq
```

**Expected Healthy Response:**
```json
{
  "status": "UP",
  "checks": [
    {"name": "MongoDB connection health check", "status": "UP"},
    {"name": "Redis connection health check", "status": "UP"}
  ]
}
```

### Metrics & Observability
```bash
# Prometheus metrics (all)
curl http://localhost:8080/q/metrics

# Application metrics only
curl http://localhost:8080/q/metrics/application

# JVM/base metrics
curl http://localhost:8080/q/metrics/base
```

### OpenAPI & Swagger
```bash
# OpenAPI specification (JSON)
curl http://localhost:8080/q/openapi

# OpenAPI specification (YAML)
curl http://localhost:8080/q/openapi?format=yaml

# Swagger UI (browser)
open http://localhost:8080/q/swagger-ui
```

### Build with Container Image
```bash
# Build with Quarkus container image extension
./mvnw clean package -Dquarkus.container-image.build=true

# Build native with container
./mvnw clean package -Dnative -Dquarkus.container-image.build=true
```

---

## Apicurio/Confluent Schema Registry (Quarkus)

### Schema Registry Operations
```bash
# List schema subjects
curl http://localhost:8082/apis/ccompat/v7/subjects

# Get schema versions for subject
curl http://localhost:8082/apis/ccompat/v7/subjects/<subject>/versions

# Get specific schema version
curl http://localhost:8082/apis/ccompat/v7/subjects/<subject>/versions/<version>

# Get latest schema
curl http://localhost:8082/apis/ccompat/v7/subjects/<subject>/versions/latest

# Delete schema version
curl -X DELETE http://localhost:8082/apis/ccompat/v7/subjects/<subject>/versions/<version>
```

---

## Summary: Command Categories

| Category | Type | Examples |
|----------|------|----------|
| Docker | Generic | `docker ps`, `docker build`, `docker logs` |
| MongoDB | Generic | `mongosh`, collection queries |
| Redis | Generic | `redis-cli`, key operations, RediSearch |
| SSE Testing | Generic | `curl -N` with `text/event-stream` |
| HTTPie | Generic | `http GET/POST/PUT/DELETE` |
| Performance | Generic | `ab` (Apache Bench) |
| Health/Metrics | Quarkus | `/q/health`, `/q/metrics` |
| OpenAPI | Quarkus | `/q/openapi`, `/q/swagger-ui` |
| Schema Registry | Quarkus | Apicurio/Confluent REST API |

---

**Version**: 1.0.0
**Last Updated**: 2025-12-13
**Related**: devops-environment.md, quarkus-patterns.md
