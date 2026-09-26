---
name: gap-analysis
description: Pre-implementation gap and drift analysis for CR specs. Multi-dimensional check — spec vs PRD, spec vs code, code vs PRD, spec vs existing mechanisms, design-lineage, public-symbol removal, and cost (is each criterion worth what satisfying it requires building). Mandatory before any feature branch or RED phase.
---

# Gap Analysis — CR Spec Validation

You are performing a **pre-implementation analysis**. You do NOT write code. You produce a structured findings report that determines whether the CR spec is ready for implementation.

## When to Use

- Before starting ANY CR implementation
- Before creating a feature branch
- After the spec is written but before RED phase
- When a CR predates recent codebase changes

## Prerequisites

Before starting, gather:
1. The CR spec (locate via the project's AGENTS.md — e.g., `docs/changes/CR-*.md`)
2. All referenced PRDs (check project `docs/research/` AND sister projects listed in the project's AGENTS.md)
3. The current source code for all files the CR touches
4. Downstream CR specs that depend on this CR
5. **A MEASURED baseline** — see Step 0 below. Gather it by RUNNING, not by remembering.

## Step 0: BASELINE — measure before you analyse (MANDATORY)

**Recorded 2026-09-06 after this step's absence cost a cycle.** An analysis that reasons about a
tree it never ran is guessing, and a figure quoted from memory is worse than no figure: it travels
into dispatch briefs as fact.

- [ ] RUN the suites the CR touches, plus any suite that corroborates against a LIVE service or a
      real engine, and write the exact pass/fail counts into the analysis with the time of the run.
- [ ] Cut the feature branch only from a baseline you measured. A branch cut from an unmeasured
      tree inherits failures the CR will be blamed for.
- [ ] NEVER state a count in a sub-agent brief that you did not measure in this session. If it is
      older than the last merge, board write, or state change you made, it is stale — re-run it.
- [ ] Re-baseline after ANY of your own actions that a test can observe: a merge, a schedule/board
      write, activating a plan, restarting a service, changing seed data. Orchestrator actions are
      inputs to the system under test.
- [ ] A tracked design artifact (a storyboard, a mock, an approved HTML doc) may be READ BY TESTS.
      Before editing one, grep for its path in the test tree; after editing it, re-run the suites
      that read it. Treat it as code, not documentation.

**Field evidence:** an orchestrator carried "84 pass / 0 fail" into a RED brief from a run taken
before a merge, two board writes and a plan activation. The real figure at dispatch was 73/11, and
11 of those failures were caused by adding an `<img>` to a tracked design artifact that a Chromium
suite serves as a fixture — a missing asset threw as an unhandled error and took unrelated tests
down with it. The RED agent had to correct the orchestrator's own baseline.

## The Dimensions

Every gap analysis checks these dimensions. Missing any one causes design drift. The first three are the core triangle (spec ↔ PRD ↔ code); the last three guard against reinvention, mistaken retire/delete calls, and orphaned consumers.

### Dimension 1: Spec vs PRD — Is the spec complete?

- [ ] Read ALL referenced PRD sections (not just the ones the spec cites)
- [ ] Read sister project PRDs if the CR touches cross-project contracts (check the project's AGENTS.md for sister project paths and their PRD locations)
- [ ] Check: Does the PRD require something the spec doesn't mention?
- [ ] Check: Does the spec propose something the PRD doesn't support?
- [ ] Check downstream CRs — does another CR already cover a gap?

### Dimension 2: Spec vs Code — Has the code drifted from the spec?

- [ ] Read EVERY code example in the spec
- [ ] Compare each code example against the ACTUAL source file
- [ ] Check method signatures (parameter order, types, return type)
- [ ] Check enum values (do they exist? are they typed correctly?)
- [ ] Check field names (does the field exist on the entity?)
- [ ] Check constructor arguments (records have positional args — order matters)
- [ ] Check that code examples match the project's established patterns (read the project's AGENTS.md for conventions)
- [ ] Check that pseudocode matches the project's async/reactive pattern (if applicable)

### Dimension 3: Code vs PRD — Has the code drifted from the PRD design intent?

**This is where real bugs hide. Code compiles and tests pass, but violates the design contract.**

- [ ] Read the PRD design intent (not just the spec's summary of it)
- [ ] Check ALL callers of methods the CR touches — what values do they pass?
- [ ] Check parameter VALUES, not just parameter TYPES
- [ ] Check state machine transitions — does the code follow the PRD's state diagram?
- [ ] Check architectural boundaries — does the code respect the project's layer separation?
- [ ] Check naming conventions — does the code use the PRD's canonical terminology?
- [ ] Cross-reference sister project contracts — does the code match what consumers/producers expect?

**Bounded surface vs unbounded content — MOST USEFUL ON UI AND RENDERED SURFACES** (added
2026-09-06; it applies wherever a design fixes a size and the data does not — a pixel budget, a
column width, a fixed-size buffer, a log line, a filename length, a terminal column count. On a
pure back-end CR with no rendered or fixed-width surface, note it as N/A and move on.)

A design that states a SIZE and a data rule that states no LIMIT is a contradiction readable from
the two documents alone, with no test run. Find it at design time — it is cheapest there and it
never announces itself until real data arrives.

- [ ] List every surface the CR touches that carries a stated budget: px width/height, a row cap,
      a gate/column count, a character or field-count limit.
- [ ] For each, name what fills it, and ask **what the WIRE allows** — not what today's data holds.
      An array field with no declared maximum is unbounded input to a bounded box.
- [ ] Compute the WORST CASE the wire permits and compare it to the budget. If the worst case
      overflows, the gap is real NOW even though every test is green.
- [ ] Check whether the budget's original measurement predates a later feature that ADDS to the
      same slot (a marker, a badge, a second annotation). Two features that each fit can overflow
      together, and neither CR is at fault.
- [ ] Abbreviation is not a bound. Shortening each ITEM (an id, a title) leaves the COUNT
      unbounded; a cap needs a limit on how many items are stated plus a remainder that says how
      many were not.

**Field evidence (2026-09-06):** one CR set a wave box's ~300px budget; a later CR abbreviated each
dependency id to its bare number and its own comment said "this is the ONLY thing that
abbreviates" — bounding each item's LENGTH and never the COUNT. A third CR's execution then put
the `next` marker on the row that declared four dependencies, and the live board measured 333px
against the 300px budget. Every AC of all three CRs was satisfied; the contradiction was legible
from two specs months earlier, and was instead found by a RED agent mid-implementation.

### Dimension 4: Spec vs existing mechanisms — Does the spec reinvent something already built?

- [ ] List what the codebase ALREADY provides that this CR might reinvent
- [ ] Classify each as *consumed* (used as-is) or *extended* (built upon)
- [ ] READ the code of anything you'll extend — do not assume its shape from memory
- [ ] For each EXTENDED mechanism, write a 1–2 line behavioural summary from that reading into
      the analysis — the summary is the proof the code was read

### Dimension 5: Design-lineage — Is a "dead/vestigial" claim actually true?

**Before any "dead/vestigial/never-designed" or retire/delete call, trace the FULL CR + PRD/DN timeline.**

- [ ] A VERIFY note or sub-agent claim that something is unused is a LEAD, not a fact
- [ ] Trace the full lineage (originating CR, PRD/DN sections, later CRs) before retiring/deleting
- [ ] Before proposing a fix, search the code's comments and `git blame` for prior CR references
      that deferred the same issue — a deferral records a decision the fix must honour or reopen

### Dimension 6: Public-symbol removal — Are ALL consumers enumerated?

**Before removing any public symbol, grep the ENTIRE workspace.**

- [ ] Grep every crate/module, `src/` AND `tests/`
- [ ] Classify each hit
- [ ] Enumerate ALL consumers up front

### Dimension 7: Cost — Is each criterion worth what satisfying it requires?

**The other six dimensions ask whether a criterion is TRUE. This one asks whether it is WORTH IT.**
A criterion can be accurate, performable, requirement-shaped, citation-clean, and free of
shipped-artifact edits — and still be the most expensive mistake in the CR.

For EVERY acceptance criterion and scope section, answer three questions in writing:

- [ ] **What must be BUILT to satisfy it?** Name the machinery: new files, new abstractions, a
      cross-language contract, a new artifact on disk, a fixture harness, a parser, a guard.
- [ ] **What does it PROTECT, and does that thing ever actually run?** A criterion defending a code
      path that never executes in the project's real workflow has negative value: it costs
      maintenance forever and detects nothing. Measure whether the path executes — do not assume it
      does because it exists.
- [ ] **Is there a SUBTRACTIVE alternative?** Ask explicitly: what happens if this is DELETED
      instead of repaired? If deletion satisfies the CR's own problem statement, deletion is the
      answer and the criterion is the defect.

Specific smells, each of which has shipped as a defect:

- **A criterion that FORBIDS deletion.** "X is repaired, not deleted" is a design decision disguised
  as an acceptance criterion. If it was not the user's ruling, it is an invention — and it forecloses
  the cheapest correct fix before anyone evaluates it.
- **Machinery whose only purpose is to make a SECONDARY check trustworthy.** The primary guarantee is
  the one to strengthen; a corroboration that needs scaffolding to be believable should go.
- **Cost concentrated in test infrastructure rather than product behaviour.** A criterion needing a
  stamp file, mtime arithmetic, a two-channel proof and a drift guard is describing a design, not a
  requirement.
- **Volume that trips unrelated repo-wide guards.** If satisfying a criterion adds enough code or
  prose to break citation/count guards elsewhere, the size is itself the finding.

**Field evidence (CR-CRU-101, 2026-09-04):** an orchestrator-authored `AC6` read *"the corroboration
is REPAIRED, not deleted."* It passed every other dimension. It cost four cycles, five sub-agents and
~900 lines — a client-written scope stamp, an artifact binding, three-case mtime arithmetic, an
anti-vacuity skip, a two-channel fixture with its own parser, and a filename drift guard — all to
defend a check that VERIFY then measured as NEVER FIRING in any real run. The user called the KISS
violation; the CR shipped as a DELETION, net 2 files. The measurement that killed it had been in hand
for hours, filed as a P3 "worth a comment sentence". **Ask the cost question BEFORE the branch cut,
because by VERIFY the machinery exists and sunk cost argues for keeping it.**

## Output Format

### For each finding:

```
### DRIFT-N: [title]
- **Dimension**: 1 (Spec vs PRD) / 2 (Spec vs Code) / 3 (Code vs PRD) / 4 (Reinvention) / 5 (Design-lineage) / 6 (Public-symbol removal) / 7 (Cost)
- **Source**: [PRD section / file:line / code path]
- **Expected** (per PRD/spec): [what should be]
- **Actual** (in code): [what is]
- **Impact**: [what breaks if not fixed]
- **Fix scope**: SPEC_UPDATE / CODE_FIX / PREREQUISITE_CR / SPEC_SIMPLIFY (dimension 7 — cut the criterion, or replace repair with deletion)
- **Covered downstream?**: [CR that covers this, or "none"]
```

### Summary table:

| # | Dimension | Finding | Fix Scope | Blocking? |
|---|-----------|---------|-----------|-----------|
| DRIFT-1 | 3 | Example: parameter value wrong | PREREQUISITE_CR | Yes |
| DRIFT-2 | 2 | Example: method signature mismatch | SPEC_UPDATE | No |
| DRIFT-3 | 7 | Example: AC forbids deleting the thing whose deletion is the fix | SPEC_SIMPLIFY | Yes |

### Verdicts:

- **READY**: Spec is accurate, code matches PRD, proceed to feature branch
- **SPEC_UPDATE_NEEDED**: Spec has drift, update before implementation
- **PREREQUISITE_NEEDED**: Code violates PRD in ways that must be fixed before this CR can work
- **SPEC_TOO_EXPENSIVE**: Every criterion is accurate, but one or more demand machinery out of
  proportion to what they protect. Simplify — or take the subtractive option — before the branch cut.
- **BLOCKED**: Fundamental design issue, needs human decision

## Rules

1. **Never delegate this analysis to a sub-agent** — this is the orchestrator's responsibility
2. **Never trust memory or summaries** — read the actual source code and PRDs
3. **Never assume enum values exist** — check the enum file
4. **Never assume method signatures match** — check the source
5. **Never skip sister project PRDs** — cross-project contracts are where drift hides
6. **Check caller values, not just caller types** — the same method signature can be called with correct or incorrect values
7. **Flag prerequisite drifts separately** — don't bundle a fix for broken callers into a CR that depends on them working correctly
8. **Ask the cost question for every criterion** — an accurate criterion can still be the defect
9. **Never let an AC forbid deletion unless the USER ruled it** — "repaired, not deleted" is a design
   decision, and specifying it forecloses the cheapest correct fix
10. **Verify the protected path actually executes** — a guard over a path that never runs is
    negative value, and "it exists" is not "it runs"
11. **Measure the baseline before analysing, and never quote a stale count** — Step 0. A figure you
    did not run in this session is not evidence, and it becomes a lie the moment it reaches a
    dispatch brief. Re-measure after your OWN merges, board writes and plan activations.
12. **A stated budget with unbounded content is a design gap, findable now** — Dimension 3's
    bounded-surface check. Most valuable on UI and rendered surfaces; N/A is an acceptable answer
    on a back-end CR, but it must be an answered question, not an unasked one.
13. **A tracked design artifact may be a test fixture** — grep the test tree for its path before
    editing it, and re-run what reads it afterwards. A storyboard that Chromium serves is code.
14. **Every requirement lives in an AC, or it is not a requirement** — added 2026-09-07 after four
    FIX passes on one CR, all the same defect. GREEN and VERIFY are measured against ACs; scope
    prose is measured against nothing. Before the branch cut, walk EVERY sentence of every §S
    section and ask: is this discharged by a named AC? A finding recorded in prose is a finding
    deferred to a FIX round.
    **Field evidence:** the analysis itself found "AC5 says `regression`/`test` but five verbs
    ingest", wrote the enumeration into §S3's prose, and left AC5's wording untouched. GREEN wired
    two of five verbs and passed every AC. The finding was *in hand* and still cost a FIX pass,
    because it landed in the wrong document.
15. **A multi-implementation requirement must name its CALL SITES per implementation** — a fleet of
    five clients, three stacks, two renderers. "The client does X" is satisfiable by one client.
    Write the AC as "X is called from <verb> in EACH of <enumerated implementations>", and make the
    caller count itself the assertion. Same rule for envelope/warning behaviour: specify **every
    exit path** (success, failure, early return, interrupt/abandon), because an AC that says
    "carries a warning" is satisfied by the happy path alone.
    **Field evidence:** §S3 prose said "one source of truth for all five clients"; AC5 said "the
    client". The shared module was correct and exactly one of five clients called it — with a
    section header in shipped source claiming five, which the next reader would have trusted. A
    sibling miss in the same CR: the one interrupt exit dropped the warning the other exits carried.
16. **Ask what YOUR edit breaks elsewhere — the inverse blast radius** — the analysis reflexively
    checks whether the code drifted from the spec. It must also ask what this CR's own insertions
    will drift. Before the branch cut, for every file the CR will touch: grep the test tree for
    line-number citations INTO that file (citation guards, `path:line` pins, docstring references),
    and count what the CR's added prose will do to any repo-wide citation/count guard. Then plan
    the re-record ONCE, as a close-out step in the cycle plan — not as an escalation per cycle.
    **Field evidence:** one analysis re-pinned five of seven drifted citations in the spec it was
    validating, then never asked whether its own `src/store.ts` insertions would drift other files'
    pins into `src/store.ts`. They did. Separately, three `PROSE_CITATIONS` head re-records arrived
    as three mid-cycle approval round-trips, though the first one made the remaining two certain.
17. **Decide the direct refactor here, not a workaround later** — choose the direct refactor over a
    workaround or a compatibility shim during the analysis. A spec change forced mid-cycle is a
    gap-analysis miss: log it as one, and put the new scope into a patch CR, never an inline spec
    edit.
18. **Never conclude absence from a filtered grep** — a piped, filtered or truncated search that
    shows no hit proves nothing. Read the region unfiltered before claiming something is absent.
19. **Surface design forks; never self-resolve them into the spec** — a choice between designs is
    the user's. Record it as PROPOSED until the user rules; only mechanical facts are recorded as
    settled.
