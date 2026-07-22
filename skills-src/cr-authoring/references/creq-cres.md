# CReq / CRes — Intra/Inter Project Communication Pattern

**For shared library projects** (e.g., Store-utils) and their dependent consumers
(e.g., StateStore, EntityStore). Establishes clear ownership and communication
channels between library maintainers and dependent projects.

## Terminology: documents vs messages

Two distinct concepts work together:

1. **INBOX/OUTBOX** — indicates **which document** to update and **who can modify** it:
   - **INBOX = Migration.md** — where consumers write TO the library.
   - **OUTBOX = Implementation.md** — where the library writes FOR consumers.
2. **CReq/CRes** — indicates **message type** within those documents:
   - **CReq = Change Request** — consumer requesting a feature/fix.
   - **CRes = Change Response** — library providing the solution/implementation.

```
Consumer writes CReq in INBOX   →  Library reads CReq from INBOX
Library writes CRes in OUTBOX   →  Consumer reads CRes from OUTBOX
```

Messages within a document are visually demarcated by a `---` delimiter line.

## CReq (Change Request) structure

```markdown
---
## CReq <number>: <brief title>

**CRef**: <sequential number>
**Subject**: <brief change topic>
**From**: <Microservice name>
**Affects**: <version affected, e.g., "2.0.0">
**ChangeType**: RELEASE | SNAPSHOT

### Body

<Technical details of changes requested>
- Keep concise and to the point
- Include code examples showing the desired API
- Explain rationale and use cases
- Provide actionable information for library implementation
---
```

**Header fields:**
- **CRef**: sequential number incremented by the consumer based on order in the INBOX.
- **Subject**: brief change topic (short, descriptive).
- **From**: name of the microservice project raising the request.
- **Affects**: release version affected (e.g., "2.0.0").
- **ChangeType**: `RELEASE` (triggers version bump + full git-flow release) or
  `SNAPSHOT` (rapid iteration, no version bump, no git tag).

## CRes (Change Response) structure

```markdown
---
## CRes <number>: <brief title>

**CRef**: <same as related CReq>
**Subject**: <brief logical answer>
**RequestRef**: CReq <number>
**From**: <Microservice that raised the CReq>
**ChangeType**: RELEASE | SNAPSHOT
**Target Version**: <version for this implementation>

### Body

<Implementation summary and integration guide>
- Implementation details + code usage examples
- Integration steps
- API documentation
- Migration notes (if breaking changes)
---
```

**Header fields:** **CRef** same as the related CReq (ensures pairing); **RequestRef**
explicitly references the CReq (e.g., "CReq 3"); **ChangeType** same as the related CReq.

**Target Version determination (library responsibility):**
- **SNAPSHOT**: current active version + `-SNAPSHOT` (e.g., "2.0.0-SNAPSHOT").
- **RELEASE**: library determines the increment by semantic versioning —
  **MAJOR** breaking changes / **MINOR** new backward-compatible features / **PATCH** fixes.

## Workflow

1. **Request (CReq in INBOX):** the dependent project writes a CReq in the library's
   `Migration.md`, assigns the next sequential CRef, sets ChangeType, fills the header,
   and gives use cases + proposed API + rationale in the body.
2. **Implementation:** the library maintainer reads the CReq, reviews/approves,
   implements following TDD, and follows the git-flow release process (git-workflow.md).
3. **Response (CRes in OUTBOX):** the library maintainer writes a CRes in
   `Implementation.md` with the SAME CRef, determines Target Version, and documents
   the implementation, usage examples, integration steps, and migration guides.
4. **Integration:** dependent projects read the CRes, follow the integration steps,
   update their code, remove duplicated code, and may mark the CReq ✅ Complete in the INBOX.

## Numbering convention

Each CReq has a unique **CRef** (incremented by the consumer); the corresponding CRes
uses the **same CRef**, plus an explicit **RequestRef**:

```
CReq 17 (CRef: 17) → CRes 17 (CRef: 17, RequestRef: CReq 17)
CReq 18 (CRef: 18) → CRes 18 (CRef: 18, RequestRef: CReq 18)
```

This gives a clear conversation thread and simple validation of requested vs implemented.

## Condensed example pair

```markdown
---
## CReq 3: Add EntityNotFoundException to <Library>

**CRef**: 3
**Subject**: Add EntityNotFoundException
**From**: <Microservice>
**Affects**: 2.0.0
**ChangeType**: RELEASE

### Body
Multiple dependent microservices need a standard exception for "entity not found"
scenarios. Proposed API: `public class EntityNotFoundException extends RuntimeException`
with a `String message` constructor. Centralizing it improves consistency and removes
per-service duplicates.
---
```

```markdown
---
## CRes 3: EntityNotFoundException Implementation

**CRef**: 3
**Subject**: EntityNotFoundException Implementation
**RequestRef**: CReq 3
**From**: <Microservice>
**ChangeType**: RELEASE
**Target Version**: 0.3.0

### Body
Added `org.<library>.exceptions.EntityNotFoundException`. Throw in the service layer
(`.onItem().ifNull().failWith(() -> new EntityNotFoundException("User not found: " + id))`).
Integration: bump the dependency to 0.3.0, replace custom exceptions, delete the old
per-service classes.
---
```

(The full-length example bodies live only in the project archive.)

## Critical rules — ownership

❌ **Dependent projects NEVER:** modify `Implementation.md` (OUTBOX), write CRes
entries, update OUTBOX documentation, or write release notes in the library.

✅ **Dependent projects ALWAYS:** write CReq in `Migration.md` (INBOX), read CRes from
`Implementation.md` (OUTBOX), follow integration guides exactly, and mark CReq status
in the INBOX (⏳ Pending, ✅ Complete).

✅ **Library maintainer EXCLUSIVELY:** writes CRes in and owns `Implementation.md`
(OUTBOX), writes integration instructions, controls release documentation, uses the
same CRef as the related CReq, and determines **Target Version** from the ChangeType.

**Benefits:** single request channel (INBOX) + single integration source of truth
(OUTBOX); no ownership conflicts or doc merge conflicts; asynchronous batch-friendly
workflow; integration guides written by the expert, matching the actual implementation.
