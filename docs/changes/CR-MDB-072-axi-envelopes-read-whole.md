# CR-MDB-072 — Every AXI envelope is read whole

**Status:** PENDING — **SEED, not the finished spec** (filed 2026-10-15 into release 1.0.0, wave 2).
Gap analysis, the spec and its pre-review happen in order when this CR starts.
**Type:** refactor (skills, references, agent templates, stack files) + a guard test
**Priority:** P1 — release 1.0.0, wave 2; after CR-MDB-059 (shared files).
**Depends on:** CR-MDB-059 (board-authoritative: read `queue`)
**Labels:** skills, orchestration, agents, axi, guard
**Design reference:** PRD D5 (AMENDED 2026-10-15: every AXI envelope is read whole);
Crucible #1451.

## Context

An AXI command prints one envelope whose `warnings[]`, `help[]` and `error` carry the guidance a
caller needs next. An agent that greps, heads, tails, filters, narrows with `jq`, redirects away
(`>/dev/null`, `2>&1 …`) or summarises the output by pattern loses that guidance silently. The
shipped text says only "never through `| head`" (the `crucible` skill) and "never `| tail`" (the
agent templates), and only about test runs.

## Scope (seed)

1. **The rule.** No agent, orchestrators included, greps, heads, tails, filters, narrows with `jq`,
   redirects away or summarises by pattern the output of an AXI call. This covers the Crucible
   clients, `sandesh`, `modelb-axi`, `worktree-flow`, `gh-axi` and any other AXI command. The whole
   envelope is read every time. A long run writes its output to a file, and that file's envelope is
   read whole.
2. **What the rule does not cover.** A runner log the client writes with `--log` is not an
   envelope. Searching it for a failure stays allowed.
3. **Where it is stated:**
   - `orchestration-common.md` and `sub-agent-procedure.md`;
   - the `crucible` skill (widening "never through `| head`");
   - `sandesh.md`;
   - the four agent templates' output-discipline lines;
   - the stack files' debugging lines;
   - the dispatch-brief rules.
4. **A guard.** A test over the shipped text fails on an AXI command shown piped to a filter, or
   redirected away, unless a prohibition governs it. It mirrors the raw-runner guard's shape:
   command positions, fenced lines judged alone, prohibition clauses.

## To measure at gap analysis

- Every surface that shows an AXI call, and each form the guard must match.
- Whether the raw-runner guard's command-position parser can be shared, so it is defined once.
- The re-render of the agent definitions (`generator/build.py build`, and Model B's own `.pi/agents`
  from the installed templates after the user redeploys).
- The re-score, and the boundary with CR-MDB-059: its files are edited after 059 merges.
