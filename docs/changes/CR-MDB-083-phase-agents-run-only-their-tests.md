# CR-MDB-083 — Phase agents run only their own tests: one test-scope ladder for every adopting project

**Status:** PENDING — **SEED, not the finished spec** (filed 2026-10-28 into release 1.0.0, wave 2).
Gap analysis, the spec and its pre-review happen in order when this CR starts.
**Type:** workflow (generated agent definitions, stack files, skills, orchestration rules)
**Priority:** P1 — release 1.0.0, wave 2, after Crucible 0.4.0 is installed: written once against the
0.4.0 clients' verbs.
**Depends on:** the Crucible 0.4.0 doc-sync CR, once filed; the board is authoritative: read `queue`,
not this line.
**Labels:** agents, generator, stacks, skills, crucible, test-scope
**Design reference:** `skills-src/model-b/references/sub-agent-procedure.md` § TDD (step 6: the full
suite is the orchestrator's); `skills-src/crucible/SKILL.md` § Who runs what; PRD D3 (the canonical
definition and its procedure); DN-multi-harness-deploy-model §D26 (the test-scope ladder).

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

The Crucible 0.4.0 clients give each rung one form. The narrow rung keeps each stack's native
filter: python `test --tests`, bun `test --tests`/`--name`, rust `test --crate`/`--test`/`--filter`,
mvn `unit --test`/`--module`, arduino `test`/`unit --tests`. The whole-suite rung is the same verb on
every stack: `regression` without `--coverage`, which runs the whole suite as the `regression` tier
with no coverage. Each `pre-merge-gate` still measures coverage. The final flag names are those of
0.4.0's release notes.

## Scope (seed)

1. **One test-scope ladder, stated once,** in the sub-agent procedure; the definitions, the stack files
   and the `crucible` skill point to it rather than restating it:
   - RED, GREEN and FIX run their own tests: the cycle's RED tests and the tests of the files they
     changed, with the stack's narrowest filter; never the whole suite, with or without coverage, and
     never a whole crate, module or package.
   - VERIFY runs the whole suite without coverage (`regression`, no `--coverage`), in branch
     verification only; its spec pre-review runs nothing.
   - The orchestrator's pre-merge gate is the only coverage run.
2. **The templates' wording** (`generator/templates/{red,green,fix,verify}.md.tmpl`): "affected" becomes
   the ladder's defined term; FIX's "targeted regression" goes, since `regression` names a tier;
   VERIFY's "targeted regression" and "NO full-suite" become its whole-suite run, and the `crucible`
   skill's "Does NOT run the regression" agrees. The tests pinning VERIFY's old wording
   (`tests/test_verify_spec_pre_review_mode.py`) are migrated in RED.
3. **The stack files** (`generator/stacks/*.toml`): each stack's run commands and gates follow the
   ladder — quarkus GREEN runs `--test` rather than a module regression; arduino GREEN and FIX run
   `--tests` rather than the full native suite; rust's `smoke-test` stays the orchestrator's, with
   VERIFY on `regression`; every stack's test_command and VERIFY gates are re-checked.
4. **An orchestrator rule** in `orchestration-common.md`, on the rule that a brief adds no extra proof
   steps: a wider test run is one, so a brief never widens a phase agent's runs and names no test
   list.
5. **The generated definitions are re-rendered** (`generator/build.py build`), this repository's
   `.pi/agents` matches them, and every guard over the changed text is updated; adopting projects
   take the change with `modelb-axi agents`.
