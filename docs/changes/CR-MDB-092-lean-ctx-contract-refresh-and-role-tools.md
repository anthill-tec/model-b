# CR-MDB-092 — The lean-ctx contract refreshed; each role gets the lean-ctx tools that serve it

**Status:** PENDING — **SEED, not the finished spec** (filed 2026-10-29).
Gap analysis, the spec and its pre-review happen in order when this CR starts.
**Type:** feature (contract, stack files, generated agents) + upstream findings
**Priority:** P2.
**Depends on:** CR-MDB-090 (same templates); the board is authoritative: read `queue`, not this line.
**Labels:** lean-ctx, contracts, agents, generator
**Design reference:** research note `lean-ctx-for-model-b` §S2, §S5.1, §S7, §S9 items 4, 6 and 8;
`contracts/lean-ctx.md`.

## Context

- **The contract is stale.** `contracts/lean-ctx.md` records lean-ctx 3.10.2 and the `lean` tool
  profile. The engine is 3.11.4 and serves `standard`. On Pi, a `mode=full` read is always fresh, so
  it is never a cheap cache hit. Upstream has since answered the contract's two filed findings: a
  per-project shell allowlist in a trusted `.lean-ctx.toml`, and `write_allow_paths`.
- **Role tools.** The generated agents' `tools:` lists carry the basic `ctx_*` read, search and shell
  tools. They lack the ones the study found useful per role: `ctx_graph` (impact, `diff since=`) and
  `ctx_callgraph` for blast radius in gap analysis, VERIFY and close-out; `ctx_explore`; and
  `ctx_delta`, which replaces re-reading a file after an edit. A dispatch type with no `tools:` line
  has none of the lean-ctx tools in a sub-agent session.

## Scope (seed)

1. **The contract** is refreshed to 3.11.4:
   - the served profile;
   - fresh full reads on Pi;
   - the MCP response budgets;
   - `ctx_grep`'s ledger entries;
   - the ledger as machine-wide state never mutated in a run;
   - its two findings closed with the upstream answers.
2. **The role tools.** The stack files grant the tools above to the roles that gain from them.
   `ctx_compose` goes to the orchestrator only. Tools that are not worth their schema cost stay out.
   The definitions are regenerated, and the permission gates follow.
3. **Upstream findings,** filed with lean-ctx through the contract's channel:
   - per-agent or per-project ledger scoping;
   - auto-pinning's uncapped weight in pressure;
   - the daemon and file ledgers disagreeing;
   - decay compounding per lifecycle run;
   - category recall silently capped at 10;
   - a verbatim class for declared test clients.

## To measure at gap analysis

- Why a `general-purpose` sub-agent had no `ctx_*` tool (2026-10-29), and whether Model B can or
  should change it.
- Each tool's schema cost against its use per role.
- **Score:** seeded at 5.
