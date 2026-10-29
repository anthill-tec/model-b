# CR-MDB-093 — A RED phase commits its failing tests; the written rules say so

**Status:** PENDING — **SEED, not the finished spec** (filed 2026-10-29).
Gap analysis, the spec and its pre-review happen in order when this CR starts.
**Type:** fix (the sub-agent procedure, `AGENTS.md`, the generated definitions where they state it)
**Priority:** P2.
**Depends on:** none (board-authoritative: read `queue`, not this line)
**Labels:** tdd, skills, agents
**Design reference:** PRD D5, ruling of 2026-10-29 at CR-MDB-092's VERIFY (RED commits are allowed).

## Context

Every RED phase commits its failing tests on their own, and GREEN makes them pass in the same cycle — 53 such
commits in develop's last 400. The git-workflow skill allows it ("unless it's a test-only commit in a TDD
test-write step"), but two rules forbid it: `AGENTS.md` § Workflow Rules ("never commit failing tests") and
the `model-b` skill's sub-agent procedure ("GREEN before commit — never commit in RED"). CR-MDB-092's VERIFY
flagged the disagreement, and the user ruled for the practice.

## Scope (seed)

1. **The sub-agent procedure** states the rule: RED commits its failing tests test-only; GREEN commits the
   code that makes them pass, in the same cycle; nothing stays red past a cycle's GREEN or across a merge;
   a clean build is still required for every GREEN, FIX and BACKFILL commit.
2. **`AGENTS.md`** says the same in § Workflow Rules and § Testing & QA.
3. **The generated agent definitions** and the stack files, wherever they state when to commit, agree.
4. **Gates** pin the rule where the existing commit-rule gates read these files.

## To measure at gap analysis

- Every place that states when a phase commits (templates, stack files, skills, `AGENTS.md`), and the gates
  that pin the old wording.
- Whether the scaffolded `AGENTS.md` carries the rule for downstream projects.
- **Score:** seeded at 2.
