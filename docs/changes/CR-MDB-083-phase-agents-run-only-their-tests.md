# CR-MDB-083 — Phase agents run only their own tests: one test-scope ladder for every adopting project

**Status:** PENDING — **SEED, not the finished spec** (filed 2026-10-28 into release 1.0.0, wave 2).
Gap analysis, the spec and its pre-review happen in order when this CR starts.
**Type:** workflow (generated agent definitions, stack files, skills, orchestration rules)
**Priority:** P1 — release 1.0.0, wave 2, before CR-MDB-060.
**Depends on:** none known; the board is authoritative: read `queue`, not this line.
**Labels:** agents, generator, stacks, skills, crucible, test-scope
**Design reference:** `skills-src/model-b/references/sub-agent-procedure.md` § TDD (step 6: the full
suite is the orchestrator's); `skills-src/crucible/SKILL.md` § Who runs what; PRD D3 (the canonical
definition and its procedure).

## Context

Every project that adopts Model B runs its RED, GREEN, FIX and VERIFY agents from the generated
definitions, and those agents run far wider test runs than their phase needs. Each wide run is time a
GREEN or FIX agent spends waiting, and adds no safety: the orchestrator's pre-merge gate runs the
whole suite with coverage before any merge.

The shipped surfaces disagree on how wide a phase agent's runs are:

- The `crucible` skill and the sub-agent procedure say RED, GREEN and FIX run only their targeted
  tests, never the full suite, and that VERIFY runs no regression.
- The generated definitions say GREEN's final step runs "the affected test target(s)", without
  defining "affected". FIX's final step runs a "targeted regression on the affected target(s)", and
  `regression` is a Crucible tier name: the python stack file defines it as full discovery. VERIFY's
  definition runs a targeted regression of the affected targets.
- Only the coverage gate is forbidden to phase agents; a full run without coverage reads as allowed.
- Stack files widen it further. The arduino stack's GREEN and FIX end on the full native suite, because
  `arduino-crucible.py` has no per-test filter. The quarkus stack's GREEN ends on a module regression
  (`mvn-crucible.py module`), although `--test <Class>#<method>` exists.
- Nothing tells an orchestrator how to scope a brief's test runs, so orchestrators widen them to be
  safe.

The clients mostly allow a narrow run: python `--tests` down to one method, rust `--crate` with
`--test` and `--filter`, mvn `--test` and `--module`, bun `--tests` per file (a name filter arrives
with Crucible 0.4.0). Arduino is the one client with no filter below the tier directory.

## Scope (seed)

1. **One test-scope ladder, stated once,** in the sub-agent procedure; the definitions, the stack files
   and the `crucible` skill point to it rather than restating it:
   - RED, GREEN and FIX run their own tests by name: the cycle's RED tests and the tests of the files
     they changed; never the full suite, with or without coverage.
   - VERIFY runs the wider net (see open question 1).
   - The orchestrator's pre-merge gate is the only full run.
2. **The templates' wording** (`generator/templates/{red,green,fix,verify}.md.tmpl`): "affected" becomes
   the ladder's defined term; FIX's "targeted regression" goes, since `regression` names a tier; the
   VERIFY definition and the `crucible` skill agree.
3. **The stack files** (`generator/stacks/*.toml`): each stack's run commands and gates follow the
   ladder — quarkus GREEN runs `--test` rather than a module regression; arduino GREEN and FIX keep
   the full native suite only while its client has no filter, marked as a client gap; rust and the
   others are re-checked against the ladder.
4. **An orchestrator rule** in `orchestration-common.md` (and wherever a brief's contents are named):
   a brief lists the cycle's tests by name and never asks GREEN or FIX for a full run or an
   "every module that reads a changed file" run; that wider list belongs in VERIFY's brief.
5. **A Crucible request:** a per-suite or per-test filter for `arduino-crucible.py`. When it ships, the
   arduino stack drops its full-suite final step (a later doc-sync, not this CR).
6. **The generated definitions are re-rendered** (`generator/build.py build`), and every guard over the
   changed text is updated; adopting projects take the change with `modelb-axi agents`.

## Open questions (for gap analysis)

1. **VERIFY's rung:** the affected targets (the tests of everything the branch changed, plus what reads
   it), or the full suite without coverage, leaving coverage to the orchestrator's gate.
2. **Quarkus `module` and rust per-crate runs:** whether a whole module or crate is ever GREEN's own
   scope (a cross-module change), or always VERIFY's.
