# Project Management and Documentation

## Documentation Structure

### Required Documentation Files

Every project should have:
1. **Architecture.md** - Conceptual design and architecture
2. **Implementation.md** - Phased implementation tracking with code examples

### Documentation Location
```
project-root/
  docs/
    Architecture.md
    Implementation.md
```

### Architecture.md Guidelines

**Purpose:** High-level conceptual explanation of system design

**Content:**
- System architecture overview
- Design decisions and rationale
- Component interactions
- Data flow diagrams
- Technology choices
- Minimal code snippets (only for illustration)

**What to AVOID:**
- Detailed code implementations
- Copy-pasting large code blocks
- Implementation-specific details (those go in Implementation.md)
- Duplication of content from Implementation.md

**Example Sections:**
```markdown
# Architecture

## System Overview
High-level description of the system

## Core Components
- Component A: Purpose and responsibility
- Component B: Purpose and responsibility

## Design Decisions
### Why Technology X?
Rationale for choosing technology

## Data Flow
Conceptual flow of data through system
```

### Implementation.md Guidelines

**Purpose:** Active development tracking with detailed implementation guides

**Content:**
- Phased implementation status
- Feature completion tracking
- Detailed code snippets
- Integration guides
- API usage examples
- Migration steps
- Version history

**What to INCLUDE:**
- Code examples for each phase
- Technical implementation details
- Integration instructions
- API documentation
- Troubleshooting guides

**Example Sections:**
```markdown
# Implementation

## Phase 1: Core Infrastructure
**Status:** ✅ Complete
**Completion Date:** October 27, 2025

### Components Implemented
- Entity repository with Panache
- Redis caching layer
- Basic CRUD operations

### Code Example
\```java
@ApplicationScoped
public class EntityService {
    // Implementation
}
\```

### Integration Guide
1. Add dependency to pom.xml
2. Configure application.properties
3. Inject service into your resource

## Phase 2: Advanced Features
**Status:** 🔄 In Progress

### Planned Components
- Complex querying
- Batch operations
```

### Documentation Maintenance

**Update Frequency:**
- **Architecture.md:** Update when design changes
- **Implementation.md:** Update after each completed phase/feature

**Keep Documentation Synchronized:**
- Review docs after major code changes
- Ensure examples match current implementation
- Update integration guides when APIs change

## Intra or Inter Project Communication Pattern


**For shared library projects** (e.g., Store-utils):

This pattern establishes clear ownership and communication channels between library maintainers and dependent projects.

### Message Structure Specification

**Message Delimiter:**
```
----------------------------------
```

**CReq (Change Request) Structure:**
```markdown
----------------------------------
## CReq <number>: <brief title>

**CRef**: <sequential number>
**Subject**: <brief change topic>
**From**: <Microservice name>
**Affects**: <version affected, e.g., "2.0.0">
**ChangeType**: RELEASE | SNAPSHOT

### Body

<Technical details of changes requested>
- Keep concise and to the point
- Include code examples
- Explain rationale and use cases
- Provide actionable information for library implementation

----------------------------------
```

**CRes (Change Response) Structure:**
```markdown
----------------------------------
## CRes <number>: <brief title>

**CRef**: <same as related CReq>
**Subject**: <brief logical answer>
**RequestRef**: CReq <number>
**From**: <Microservice that raised CReq>
**ChangeType**: RELEASE | SNAPSHOT
**Target Version**: <version for this implementation>

### Body

<Implementation summary and integration guide>
- Implementation details
- Code usage examples
- Integration steps
- API documentation
- Migration notes (if breaking changes)

----------------------------------
```

**ChangeType Values:**
- **RELEASE**: Triggers version bump and full release process (git flow release)
- **SNAPSHOT**: Rapid iteration, no version bump, no git tag

**Target Version Determination (Library Responsibility):**
- **SNAPSHOT**: Current active version + "-SNAPSHOT" (e.g., "2.0.0-SNAPSHOT")
- **RELEASE**: Library determines increment using semantic versioning:
  - **MAJOR**: Breaking changes (incompatible API changes)
  - **MINOR**: New features (backward-compatible functionality)
  - **PATCH**: Bug fixes (backward-compatible fixes)

### Terminology: Documents vs Messages

**Two distinct concepts work together:**

1. **INBOX/OUTBOX** - Indicates **which document** to update and **who can modify** it
   - **INBOX = Migration.md** - Where consumers write TO the library
   - **OUTBOX = Implementation.md** - Where library writes FOR consumers

2. **CReq/CRes** - Indicates **message type** within those documents
   - **CReq = Change Request** (full form) - Consumer requesting feature/fix
   - **CRes = Change Response** (full form) - Library providing solution/implementation

**How they work together:**
```
Consumer writes CReq in INBOX    →  Library reads CReq from INBOX
Library writes CRes in OUTBOX     →  Consumer reads CRes from OUTBOX
```

**Example:**
- Consumer writes **"CReq 5: Add caching support"** in Migration.md (INBOX)
- Library implements feature
- Library writes **"CRes 5: Caching implementation guide"** in Implementation.md (OUTBOX)
- Consumer reads CRes 5 to integrate the feature

**Typical Context:**
- **Consumers** are often Java/Quarkus microservices (e.g., StateStore, EntityStore)
- **Library** is often a shared utility library (e.g., Store-utils)
- Documentation may use **`<Microservice>`** as placeholder for consumer
- Documentation may use **`<Library>`** as placeholder for library maintainer

#### Migration.md = INBOX
**Purpose:** Dependent projects write requests TO library

**Who writes:** Dependent project agents (consumers of the library)

**Content includes:**
- Technical details of requested features
- Sample code showing desired API
- Class definitions to migrate from dependent project to library
- Integration requirements
- Use cases and rationale

**Who reads:** Library agent (maintainer)

✅ Dependent projects **WRITE** to Migration.md when requesting features
✅ Library maintainer **READS** Migration.md to understand requests

**Message Separation:**

Messages are visually demarcated by:
```
----------------------------------
```

**Example Entry (CReq format):**
```markdown
----------------------------------
## CReq 3: Add EntityNotFoundException to <Library>

**CRef**: 3
**Subject**: Add EntityNotFoundException
**From**: <Microservice>
**Affects**: 2.0.0
**ChangeType**: RELEASE

### Body

Multiple dependent microservices need a standard exception for "entity not found" scenarios.

**Proposed API:**
\```java
public class EntityNotFoundException extends RuntimeException {
    public EntityNotFoundException(String message) {
        super(message);
    }
}
\```

**Integration Need:**
- <Microservice> will use this in service layer
- Other microservices will migrate their custom versions to use this

**Rationale:**
Centralizing exception handling improves consistency across all microservices and reduces code duplication.

----------------------------------
```

**CReq Header Fields:**
- **CRef**: Sequential number incremented by consumer based on order in INBOX
- **Subject**: Brief change topic (short, descriptive)
- **From**: Name of the microservice project raising the request
- **Affects**: Release version affected (e.g., "2.0.0")
- **ChangeType**: Either `RELEASE` or `SNAPSHOT`
  - `RELEASE`: Triggers version bump and full release process
  - `SNAPSHOT`: Rapid iteration, no version bump, no git tag

**CReq Body Guidelines:**
- Keep technical details concise and to the point
- Include support information useful for library implementation
- Provide code examples showing desired API
- Explain rationale and use cases
- Avoid verbose explanations; focus on actionable information

#### Implementation.md = OUTBOX
**Purpose:** Library writes instructions FOR dependent projects

**Who writes:** Library agent (maintainer only)

**Content includes:**
- What's available in each version
- How to use new features
- Version history and release notes
- Integration steps with code examples
- API documentation
- Migration guides for breaking changes

**Who reads:** Dependent projects

✅ Dependent projects **READ** Implementation.md to learn integration
❌ Dependent projects **MUST NEVER MODIFY** Implementation.md

**Example Entry (CRes format):**
```markdown
----------------------------------
## CRes 3: EntityNotFoundException Implementation

**CRef**: 3
**Subject**: EntityNotFoundException Implementation
**RequestRef**: CReq 3
**From**: <Microservice>
**ChangeType**: RELEASE
**Target Version**: 0.3.0

### Body

Added EntityNotFoundException to <Library> for consistent entity-not-found handling across dependent microservices.

**Location:** `org.<library>.exceptions.EntityNotFoundException`

**Usage:**
\```java
// Throw when entity not found
throw new EntityNotFoundException("User not found: " + userId);

// In service layer
public Uni<User> fetchById(Long id) {
    return User.<User>findById(id)
        .onItem().ifNull().failWith(() ->
            new EntityNotFoundException("User not found: " + id)
        );
}
\```

**Integration Steps:**
1. Update dependency to 0.3.0 in pom.xml
2. Replace custom exceptions with EntityNotFoundException
3. Update exception handling if needed
4. Remove old custom exception classes from your project

----------------------------------
```

**CRes Header Fields:**
- **CRef**: Same as the related CReq (ensures pairing)
- **Subject**: Brief logical answer to the request
- **RequestRef**: The CReq reference number (e.g., "CReq 3")
- **From**: Name of the microservice project that raised the CReq
- **ChangeType**: Same as the related CReq (`RELEASE` or `SNAPSHOT`)
- **Target Version**:
  - For `SNAPSHOT`: Current active release version + "-SNAPSHOT" (e.g., "2.0.0-SNAPSHOT")
  - For `RELEASE`: Library determines version increment (Major/Minor/Patch) based on changes

**CRes Body Guidelines:**
- Provide implementation summary
- Include code usage examples
- Document integration steps clearly
- Reference specific classes/packages
- Note any breaking changes or migration requirements

### Workflow

**1. Request Phase (CReq in INBOX):**
- Dependent project identifies common functionality needed
- Writes **CReq** (Change Request) in library's Migration.md (INBOX)
- Assigns sequential **CRef** number based on order in INBOX (e.g., CRef 17)
- Sets **ChangeType**: `RELEASE` (for production release) or `SNAPSHOT` (for rapid iteration)
- Includes header with: CRef, Subject, From, Affects, ChangeType
- Body contains: use cases, proposed API, integration needs, rationale

**2. Implementation Phase:**
- Library maintainer reads **CReq** from Migration.md (INBOX)
- Reviews and approves request
- Implements feature following TDD
- Follows 10-step Git Flow release process (see git-workflow.md)

**3. Response Phase (CRes in OUTBOX):**
- Library maintainer writes **CRes** (Change Response) in Implementation.md (OUTBOX)
- Uses same **CRef** as the related CReq (e.g., CRef 17)
- Includes header with: CRef, Subject, RequestRef, From, ChangeType, Target Version
- **Target Version** determination:
  - For `SNAPSHOT`: Keep current version + "-SNAPSHOT" (e.g., "2.0.0-SNAPSHOT")
  - For `RELEASE`: Library determines Major/Minor/Patch increment based on change impact
- Body includes: implementation summary, code examples, integration steps
- Documents new features and API changes
- Provides migration guides for breaking changes

**4. Integration Phase:**
- Dependent projects read **CRes** from Implementation.md (OUTBOX)
- Follow integration instructions step-by-step
- Update their own code to use library features
- Remove duplicated code from their projects
- Mark CReq as ✅ Complete in INBOX if desired

### Numbering Convention

**CRef Pairing:**
- Each CReq has a unique **CRef** number (incremented by consumer)
- Corresponding CRes uses the **same CRef** number
- **RequestRef** in CRes explicitly references the CReq (e.g., "CReq 17")

**Example Pairing:**
```
CReq 17 (CRef: 17) → CRes 17 (CRef: 17, RequestRef: CReq 17)
CReq 18 (CRef: 18) → CRes 18 (CRef: 18, RequestRef: CReq 18)
```

**Benefits:**
- Easy to track which CRes responds to which CReq
- Clear conversation thread via CRef matching
- Simple validation workflow
- Explicit reference via RequestRef field

**Example Flow:**
```
INBOX (Migration.md):                    OUTBOX (Implementation.md):
- CReq 15 (CRef: 15) ⏳ Pending      →  - CRes 15 (CRef: 15) ✅ Implemented
- CReq 16 (CRef: 16) ⏳ Pending      →  - CRes 16 (CRef: 16) ✅ Implemented
- CReq 17 (CRef: 17) ⏳ Pending      →  - CRes 17 (CRef: 17) ⏳ In Progress
```

### Example: Library-Microservice Pattern

**<Library>** (library project):
- **Migration.md = INBOX** - Microservices write CReqs (feature requests) here
- **Implementation.md = OUTBOX** - <Library> writes CRes (implementation guides) here

**<Microservice-A>** (dependent project):
- Writes **CReq** in <Library>/Migration.md (INBOX)
- Reads **CRes** from <Library>/Implementation.md (OUTBOX)
- Never modifies <Library>/Implementation.md (OUTBOX)
- Updates <Microservice-A> code to use new library features

**<Microservice-B>** (dependent project):
- Writes **CReq** in <Library>/Migration.md (INBOX)
- Reads **CRes** from <Library>/Implementation.md (OUTBOX)
- Never modifies <Library>/Implementation.md (OUTBOX)
- Updates <Microservice-B> code to use new library features

**Real-World Example:** Store-utils (library) ← StateStore, EntityStore (microservices)

### Critical Rules

**Prevents ownership conflicts** between library maintainers and consumers:

❌ **Dependent projects NEVER:**
- Modify Implementation.md (OUTBOX) in library projects
- Write CRes (Change Response) entries
- Update OUTBOX documentation
- Write release notes in library

✅ **Dependent projects ALWAYS:**
- Write CReq (Change Request) in Migration.md (INBOX)
- Read CRes (Change Response) from Implementation.md (OUTBOX)
- Follow integration guides exactly
- Mark CReq status in INBOX (⏳ Pending, ✅ Complete, etc.)

✅ **Library maintainer EXCLUSIVELY:**
- Writes CRes (Change Response) in Implementation.md (OUTBOX)
- Owns Implementation.md (OUTBOX)
- Writes integration instructions
- Controls release documentation
- Uses same CRef as related CReq (CRef 17 in both CReq and CRes)
- Determines **Target Version** based on ChangeType and change impact:
  - `SNAPSHOT`: No version bump, keep current version + "-SNAPSHOT"
  - `RELEASE`: Increment Major/Minor/Patch based on semantic versioning rules

### Benefits

**Clear Communication:**
- Single channel for feature requests (INBOX)
- Single source of truth for integration (OUTBOX)
- No confusion about who writes what

**Ownership Clarity:**
- Library maintainer controls OUTBOX
- Dependent projects control their requests in INBOX
- No merge conflicts on documentation

**Efficient Workflow:**
- Asynchronous communication pattern
- Batch processing of requests during releases
- Clear tracking of requested vs implemented features

**Documentation Quality:**
- Library maintainer ensures consistency
- Integration guides written by expert
- Examples match actual implementation

## Change Request (CR) Workflow (MANDATORY)

**Canonical CR / PRD / DN conventions live in [`cr-prd-dn-conventions.md`](cr-prd-dn-conventions.md)** — the universal (cross-stack) standard evolved in the NAI project. Read that file; it is authoritative. Do not duplicate its structure here.

In brief:
- **PRD** (`docs/research/PRD-*.md`) = WHY/WHAT, the authoritative design contract.
- **DN** (`docs/research/DN-*.md`) = a design note/decision/spike larger than one CR (design rationale, options-considered, open questions — NOT in the CR).
- **CR** (`docs/changes/CR-<PROJ>-NNN-*.md` + a flat `docs/changes/README.md` queue) = the implementation contract (Context → Scope §S → ACs → Estimated size → Risk → Non-goals). CRs implement; PRDs/DNs justify.
- ACs are precise testing gates; **integration ACs are mandatory** for any API-additive CR (a named production caller + an auditable caller-existence grep). See the universal file.
- Canonical status (text, not emoji): `PENDING` / `IN_PROGRESS` / `COMPLETED` / `SUPERSEDED` / `DEFERRED`.
- **Read the source PRD section completely before implementing a CR.** Surface gaps/assumptions/deviations — never silently deviate.

## Development Best Practices

### Always Test Components
- Test UI components after implementation
- Test backend components after implementation
- Commit after each successful test cycle

### Incremental Changes Philosophy
**Avoid sweeping changes** - use git commit friendly approach:

1. Implement small, focused change
2. Test the change
3. Commit if tests pass
4. Move to next change

**Benefits:**
- Easier to review
- Easier to revert if needed
- Better git history
- Cleaner pull requests

**Example of Good Incremental Changes:**
- Commit 1: Add entity class
- Commit 2: Add repository
- Commit 3: Add service layer
- Commit 4: Add REST endpoint
- Commit 5: Add tests

## Critical Documentation Files

### IMPORTANT: Always Check Documentation Before Implementation

When implementing features, **ALWAYS check these documentation files FIRST** to understand requirements, architecture, and implementation patterns.

#### Feature Implementation Documentation

1. **PRD Document** (e.g., `docs/EntityStoreStreamsPRD.md`) - PRIMARY requirements document
   - Complete technical specifications for the feature
   - Fetch modes, operational patterns, API specifications
   - Test strategy with test counts
   - Implementation phases with code examples
   - Dependencies between services

2. **Technical Research** (e.g., `docs/RedisStreamsCDC-Research.md`)
   - Third-party API research and examples
   - Performance benchmarks and considerations
   - Technology-specific patterns and best practices
   - Quarkus/framework-specific API usage

3. **Implementation.md** - Active implementation tracking
   - Test count tracking per phase
   - Feature completion status
   - Code patterns and insights discovered during implementation
   - Integration guides and examples

4. **Architecture.md** - High-level system design
   - System architecture diagrams
   - Data flow patterns between components
   - Integration patterns and protocols
   - Design decisions and rationale

### Critical Rule: READ THE ENTIRE PRD SECTION

**CRITICAL:** When implementing a service, **READ THE ENTIRE PRD SECTION** for that service FIRST to understand:

1. **Dependencies:** Which services it injects and uses
2. **Data flow:** How it orchestrates other services
3. **Implementation patterns:** Code examples showing exact patterns to follow
4. **Test strategy:** What tests are needed and why

**Example - HistoricalFetchService Architecture** (from PRD):

HistoricalFetchService is an **orchestrator service** that coordinates:
1. **EntityCacheService** - Executes RediSearch queries to fetch entities
2. **CDCEventPublisher** - Publishes CDCEvents to Redis Streams (XADD)
3. **StreamSubscriptionService** - Updates subscription status/metadata
4. **EntityStateSnapshot** (INCREMENTAL mode) - Queries MongoDB for changed entity IDs

**Without reading the PRD:** Developer might assume HistoricalFetchService directly interacts with Redis/MongoDB for entity data.

**After reading the PRD:** Developer understands it orchestrates existing services that already have those capabilities.

### Documentation Location Reference

**Typical Project Structure:**
```
project-root/
  docs/
    Architecture.md              # High-level system design
    Implementation.md            # Phase tracking & integration guides
    [Feature]PRD.md             # Feature requirements (e.g., EntityStoreStreamsPRD.md)
    [Technology]-Research.md    # Technical research docs
```

### When to Consult Each Document

**Before starting implementation:**
1. Read Architecture.md - Understand overall system
2. Read specific PRD section - Understand service requirements
3. Check Implementation.md - See what's already done

**During implementation:**
1. Refer to PRD for code examples
2. Check Technical Research for API usage
3. Update Implementation.md with progress

**After implementation:**
1. Update Implementation.md with completion status
2. Add integration guides and code examples
3. Document any deviations from PRD

### Memory Trigger

**BEFORE implementing ANY service:**
"Does this service have a PRD section? READ IT COMPLETELY FIRST."

**Example Quote from Discovery:**
"The streams PRD is there in docs! It is called EntityStoreStreamsPRD! Make a note of it in your local memory! Don't skip it!"

### TODO Management

**CRITICAL:** Do not ignore TODO tags in code

**When to Address TODOs:**
1. Before marking feature as complete
2. During code review
3. When refactoring related code

**TODO Best Practices:**
```java
// ✅ GOOD - Specific and actionable
// TODO: Implement caching for this query - tracked in issue #123

// ❌ BAD - Vague and forgotten
// TODO: Optimize this
```

**TODO Tracking:**
- Keep list of TODOs in Implementation.md
- Link TODOs to issues in bug tracker
- Clean up TODOs regularly

### Refactoring vs Rewriting

**CRITICAL:** Always refactor, never rewrite tested methods

**Why:**
- Tested methods are robust
- Tests validate refactoring correctness
- Rewriting risks introducing bugs

**Proper Refactoring Workflow:**
1. Read existing implementation
2. Read existing tests first
3. Understand current behavior
4. Update tests if behavior changes
5. Refactor implementation
6. Verify tests still pass
7. Commit

**When to Read Tests First:**
- Before refactoring existing code
- When fixing bugs
- When adding features to existing components

### Rationalize Designs

**Before implementing:**
1. Check if functionality already exists in Service Layer
2. Review existing patterns
3. Avoid duplication
4. Consider reusing existing components

**Questions to Ask:**
- Does this functionality already exist?
- Can I extend existing code instead of duplicating?
- Is this the right layer for this logic?

## Project Structure Guidelines

### Tasks vs Phases

**Understanding the Difference:**
- **Phases:** Enterprise-level architectural feature implementation
- **Tasks:** Individual work items within a phase
- **Sub-tasks:** Smaller units within tasks

**Most work is tasks and sub-tasks, NOT phases**

**Example:**
- **Phase:** "Implement Event-Driven Architecture"
  - **Task 1:** Set up message broker
    - Sub-task 1.1: Install RabbitMQ
    - Sub-task 1.2: Configure connections
  - **Task 2:** Implement event publishers
  - **Task 3:** Implement event subscribers

### Convex Database Projects

**Reference File:** `convex_rules.txt` (in project root)

**Purpose:** Technical reference for Convex reactive database

**When to Read:**
- Starting new Convex project
- Implementing Convex queries
- Setting up Convex functions
- Troubleshooting Convex issues

## Logging Best Practices

### Use Appropriate Log Levels

Replace generic `log()` with specific methods:

```javascript
// ❌ AVOID - Generic logging
console.log("Something happened");

// ✅ GOOD - Specific log levels
console.debug("Detailed diagnostic info");
console.info("General informational message");
console.warn("Warning: potential issue");
console.error("Error occurred", error);
```

**Benefits:**
- Easier filtering on browser side
- Better debugging in JavaScript/TypeScript apps
- Clearer log severity
- Better production log analysis

### Log Level Guidelines

- **debug:** Detailed diagnostic information for developers
- **info:** General informational messages about app operation
- **warn:** Potentially harmful situations that need attention
- **error:** Error events that might allow app to continue
- **fatal:** Severe errors causing application termination

## Web Search Guidelines

### When to Search the Web

**ALWAYS search when:**
- Uncertain about third-party API implementations
- Need to verify current best practices
- Technology/library documentation unclear

**NEVER assume or infer:**
- API method signatures
- Configuration options
- Framework behavior

**Example:**
```
// ❌ WRONG - Assuming API
// I think the method is probably redis.get(key)...

// ✅ CORRECT - Search first
// Let me search for the Redis API documentation...
```

### Search Best Practices

**Do NOT use year in searches** unless specifically needed:
```
// ❌ WRONG - Restricts results
"Quarkus Redis 2025"

// ✅ CORRECT - Gets all relevant results
"Quarkus Redis integration"
```

**Exception:** Use year when specifically asking about version:
```
// ✅ OK - When year is relevant
"Quarkus 3.x new features 2024"
```

## Reading Before Implementing

### Critical Pattern: Read First, Then Act

**Before updating existing code:**
1. **Read the current implementation**
2. Understand the logic
3. Read the tests
4. Then make design changes

**Why this matters:**
- Tested methods are robust
- Prevents breaking working code
- Helps understand context
- Enables proper refactoring

### Understanding Existing Tests

**Before refactoring:**
```
Step 1: Read the test
Step 2: Understand what behavior is expected
Step 3: Update test if behavior should change
Step 4: Refactor implementation
Step 5: Verify test still passes
```

## Compilation Checks

### Always Verify Compilation

**Before committing to git:**
```bash
# Java projects
./mvnw clean compile

# Verify exit code
echo $?  # Should be 0
```

**Why:**
- Prevents breaking project for other developers
- CI/CD won't fail
- Maintains project stability

**Multi-developer Environment:**
- Never commit broken code
- Always verify compilation
- Run full test suite before push

## Architecture and Implementation Separation

### Clear Separation of Concerns

**Architecture.md:**
- Minimal code snippets
- Focus on concepts
- Explain "why" decisions were made
- High-level component interactions

**Implementation.md:**
- Detailed code examples
- Focus on "how" to implement
- Phase-by-phase completion tracking
- Integration instructions

**Don't Duplicate:**
- Keep concepts in Architecture.md
- Keep implementation details in Implementation.md
- Reference between documents when needed

## Memory Triggers

**BEFORE starting implementation:**
1. "Does Architecture.md exist?" → Create it first
2. "Does Implementation.md exist?" → Create it for tracking
3. "Is there existing functionality?" → Search Service Layer first
4. "Are there TODOs?" → Address before marking complete
5. "Do I understand existing code?" → Read implementation and tests first

**BEFORE committing:**
1. "Does everything compile?" → Run clean compile
2. "Are tests GREEN?" → Run full test suite
3. "Are there unused imports?" → Clean them up
4. "Is documentation updated?" → Update Implementation.md if needed
