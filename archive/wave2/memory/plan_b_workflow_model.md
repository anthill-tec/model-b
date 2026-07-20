# Plan B Project Model

The Plan B project model is a structural framework for executing projects in the agentic
environment without loosing engineering rigour and specification driven accuracy usable for 
real life applications.

It is software stack agnostic and has close relation to the SCRUM and XP programming. Plan B
is designed for an agentic ecosystem with agents having their specific roles and responsibilities.
Refer [Agentic Protocol]{}


A Plan B model has two broad classifcations for workflows it defines
1. Design Time Worfklow
2. Implementation Time Workflow

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
