# CR-MDB-044 — Agent definitions carry the how; the brief carries the what

**Status:** PENDING (filed 2026-09-27; gap analysis 2026-09-27)
**Type:** refactor (skills, agent templates, conventions)
**Priority:** P1 — release 1.0.0, wave 2. The orchestrator rules and the agent definitions
contradict the user's 2026-09-27 rulings on who guarantees accuracy.
**Depends on:** —
**Labels:** agents, orchestration, templates, conventions
**Design reference:** PRD D5 (AMENDED 2026-09-27: the brief is the accuracy lever; agents commit;
gates, not per-phase verification; parallel agents in one tree); PRD D6 (AMENDED 2026-09-27: agent
definitions carry the stack how and the role's reading of a CR)

## Context

Crucible reported eight measured agent failure modes (Sandesh #1405) and rules for several agents
working in one tree (#1406). The user ruled on them (PRD D5, D6, 2026-09-27). Today's text contradicts
those rulings in three places:

- `orchestration-common.md` § "Never author code — always dispatch + diff-verify" tells the
  orchestrator to diff-verify every cycle, and to reset and recommit agents' commits into its own
  boundaries. § "Workflow gates" tells it to validate an agent's work at module level. § "Cycle
  discipline" puts all parallelism in Track orchestrators.
- Every role template's § "Prompt Precedence" gives the dispatch prompt's exact names, values and
  patterns "ABSOLUTE precedence", while the same template's AC cross-check makes the AC the source of
  truth. A brief that over-specifies therefore wins.
- The RED, GREEN and FIX templates commit with `git add -A`, which in a shared tree sweeps up other
  agents' edits. `git-workflow` says "Always `git add -A`".

Nothing covers long runs killed by a tool timeout, private report directories, attributing a failure
before calling it unrelated, dead-code evidence, or checker tests on synthetic fixtures. Model B cites
code by `path:line`: the shipped skills, templates, `modelb_axi`, `pi-package` and `scripts` carry
none, the tests carry 129.

## Scope

### §S1 — The orchestrator's acceptance model (`orchestration-common.md`)

The section now headed "Never author code — always dispatch + diff-verify" is retitled
"Never author code — dispatch with an accurate brief" and says:

- **The brief is the orchestrator's paramount duty.** It must not compromise the workflow rules or
  the CR spec. It names the spec and the cycle's scope, points to the rules that bind the phase and
  states the phase's boundaries. It guides and does not over-specify: no dictated mechanisms, test
  names or code, because the agent definition carries the how (PRD D6).
- **Agents commit the code they write.** The orchestrator never resets and recommits an agent's
  commits.
- **A phase is accepted from the agent's report, its ingested run on the board, and the phase's
  commit range.** The orchestrator re-runs no suites and re-checks no work between phases. The
  correctness gates are the CR's VERIFY cycle, the FIX cycles it opens, and the pre-merge gate.
- **Work the orchestrator sees break the spec is reverted, or sent to a FIX agent,** never edited by
  the orchestrator.

`orchestration-track.md` agrees: its checklist carries no rule to diff-verify the worktree or the
commit range, and does not assume agents are told not to commit.

Rules that the model replaces are removed:
- "diff-verify EVERY cycle against ground truth";
- "verify the COMMIT RANGE …, reset+recommit cleanly to collapse into orchestrator-controlled
  boundaries";
- in § "Workflow gates", "Validate an agent's work at module level first …".

Rules that stay: never author code; the first action after approval is the RED dispatch; the Identity
block and the register command; the post-RED rejection of nested builds; a fix round goes to a FIX
agent; salvaging a crashed agent's complete diff; refactor-not-revert for a wrong pattern; unverified
beyond-mandate findings; checking `git status` after an interrupted agent; stopping a stalled agent.

§ "Cycle discipline" keeps "a VERIFY finding the user approves for fixing is fixed in its own FIX
cycle", and adds what applying it has taught (Crucible #1407):
- the VERIFY cycle closes with its findings before the FIX cycle is added and activated. The switch
  happens between agents, never under one: an agent bound to a closed cycle has its runs refused;
- a new contract VERIFY finds still goes AC → RED → FIX. The RED agent runs in the FIX cycle,
  alongside the FIX agent.

The CR-MDB-042 triage audit is frozen and names the old heading. The triage gate therefore resolves
a renamed destination heading through a rename map held in the test module. The map has exactly
this one entry.

### §S2 — Parallel agents in one tree (`orchestration-common.md`)

A new section, "Parallel agents in one tree":
- only with the user's explicit go; otherwise one agent per phase;
- the work is split by file, never within a file, and each brief lists that agent's files;
- each agent commits only its own files, and never stages everything, stashes, resets or restores;
- each agent's test runs use a private reports directory where its stack's client takes one
  (`--reports`); a stack whose client does not runs its agents' tests one at a time;
- ids are suffixed `-1` … `-N`;
- the split is sized to the harness's concurrency cap (Pi's pi-subagents `maxConcurrent`, default 4);
- no agent's output is verified on its own; the CR's VERIFY cycle covers the combined result;
- a follow-up to an agent whose session expired goes to a fresh agent under the same id.

§ "Cycle discipline" keeps "one active cycle at a time per orchestrator", and says that a phase may
be split across agents only under this section. Parallel CRs still belong to Track orchestrators.

### §S3 — The agent definitions (`generator/templates/*.md.tmpl`, `sub-agent-procedure.md`)

**Reading the CR.** Each role template gains a "Reading the CR" section that explains the spec's
parts and which of them bind that role:
- the parts: `§S` scope sections, acceptance criteria, non-goals, the design reference;
- which bind the role:
  - RED: the ACs in its scope sections, asserted exactly;
  - GREEN: those ACs through the RED tests;
  - VERIFY: every AC, the non-goals and the design reference;
  - FIX: the findings it was given, read against the ACs they cite.
- The spec outranks the brief. A brief narrows the work to a cycle's scope and may add boundaries. A
  brief that contradicts the spec is escalated, never followed.

§ "Prompt Precedence" is replaced to match: the brief's scope and boundaries bind; where it
contradicts the spec, escalate.

**Cycles.** The FIX template says its agent binds to a `fix`-kind cycle opened after VERIFY
closed. The VERIFY template says its report ends the VERIFY cycle's work; no fix round runs inside
it.

VERIFY's "Reading the CR" opens with what binds VERIFY (the whole spec), not with a cycle's scope.

**Committing.** RED, GREEN and FIX stage the files they changed by path, never `git add -A`. Their
report names the commit range they produced (`<base>..<head>`). `git-workflow`'s "Always
`git add -A`" becomes "stage what you changed, by path".

**Field rules,** written once:
- **Long runs** (`sub-agent-procedure.md`). A run longer than a minute or two gets a tool timeout
  longer than the run. A run that times out is never re-invoked blind: the agent first checks the
  board for its own open run.
- **An unrelated failure needs evidence** (the VERIFY template). Before calling a failure unrelated,
  trace every consumer of the behaviour the branch changed (scripts, CLIs, other clients). The report
  says how the attribution was established.
- **Dead code needs no reference anywhere** (the GREEN and FIX templates, where they delete). No
  reference counts from its own file, dynamic lookups (`getattr`, string names) or mock and patch
  targets.
- **A revert is scoped to the agent's own files** (`sub-agent-procedure.md` § "Consequences"), never
  the whole tree, which in a shared tree holds other agents' edits.
- **Checkers are proved on synthetic fixtures** (`sub-agent-procedure.md` § "Code quality", beside the
  existing content-anchor rule). A test never pins live repo violations.

The stack files keep carrying the stack's activity and tools. Every rendered agent carries its stack's
test command and Crucible client, and the "Reading the CR" section.

### §S4 — Cite code by symbol

- **Rules.** `cr-authoring` gains the rule: code is cited by symbol and file
  (`` `handleCrPlan` (src/v2.ts) ``), never by `path:line`. The role templates carry the same rule for
  comments, docstrings and reports.
- **Guard.** A guard test fails on any `path:line` citation (`<file>.<ext>:<digits>`) in
  `skills-src/`, `generator/templates/`, `generator/stacks/`, `modelb_axi/`, `pi-package/`
  (sources, not `node_modules`), `scripts/`, `AGENTS.md` and `tests/`. The guard's own fixtures are
  built at run time, so it never trips on itself.
- **Migration.** The citations in `tests/` are rewritten to symbol form, naming a symbol wherever
  the citation pointed at one, and never attributing to a symbol code it no longer holds. The meta
  test `test_skill_bundle_guards_meta` requires the deferred properties' owning test names instead
  of the audit's line numbers (`DEFERRED_LINE_REFS` is retired), so the guard module's docstring
  carries no line numbers.
- **Out of the guard.** Specs and research docs follow the rule from now on, unguarded. Closed specs,
  `archive/` and `audits/` stay untouched.

## Acceptance criteria

- [ ] `orchestration-common.md` has a heading "Never author code — dispatch with an accurate brief"
      and no heading "Never author code — always dispatch + diff-verify". Its body states:
      - the brief's duty, and that the brief does not over-specify;
      - that agents commit the code they write;
      - acceptance from the report, the ingested run and the commit range, with no re-runs between
        phases;
      - that VERIFY, FIX and the pre-merge gate are the correctness gates;
      - revert or FIX agent for spec-breaking work.
- [ ] `orchestration-track.md` carries no rule to diff-verify the worktree or the commit range.
- [ ] No line of `orchestration-common.md` says "diff-verify EVERY cycle", "reset+recommit" or
      "Validate an agent's work at module level first". Every rule §S1 lists as staying is still
      present.
- [ ] The triage gate resolves the renamed heading through a one-entry rename map. Every other
      triage destination still resolves unaided.
- [ ] `orchestration-common.md` has a section "Parallel agents in one tree" carrying each of §S2's
      eight rules. § "Cycle discipline" refers to it and keeps "one active cycle at a time".
- [ ] § "Cycle discipline" states that VERIFY closes before its FIX cycle opens, that the switch
      happens between agents, and that a new contract VERIFY finds runs RED in the FIX cycle. The FIX
      template binds to a `fix`-kind cycle, and the VERIFY template ends the VERIFY cycle's work.
- [ ] Every rendered agent (each stack × role) has a "Reading the CR" section naming its role's
      binding parts and stating that the spec outranks the brief. No template says "ABSOLUTE
      precedence".
- [ ] No template or skill instructs `git add -A`. RED, GREEN and FIX stage by path and report
      `<base>..<head>`.
- [ ] The four field rules and the scoped revert are present, each in the file §S3 names. VERIFY's
      "Reading the CR" does not tell it to read only the parts a cycle's scope touches.
- [ ] `cr-authoring` and the role templates carry the cite-by-symbol rule. The guard fails on a
      synthetic `path:line` and passes on the tree. `tests/` carries no `path:line` citation, and no bare
      line-number reference into an audit (`DEFERRED_LINE_REFS` retired).
- [ ] `generator/build.py --check` is clean, and the suite baselines are re-measured in `AGENTS.md`.

## Non-goals

- The orchestrator's own brief text for past CRs, closed specs, `archive/`, `audits/`.
- Guarding `docs/`: specs and research docs follow the citation rule unguarded.
- Changing the stack files' tool allowlists or skills lists.
- Crucible's per-run report isolation (CR-CRU-155); Model B only names the `--reports` interim.
