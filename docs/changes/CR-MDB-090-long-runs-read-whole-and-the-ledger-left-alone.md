# CR-MDB-090 — A long client run is read whole, unfiltered; the shared context ledger is left alone

**Status:** PENDING — **SEED, not the finished spec** (filed 2026-10-29).
Gap analysis, the spec and its pre-review happen in order when this CR starts.
**Type:** fix (generated agent templates, the sub-agent procedure, `AGENTS.md`)
**Priority:** P1.
**Depends on:** none (board-authoritative: read `queue`, not this line)
**Labels:** agents, axi, lean-ctx, templates
**Design reference:** research note `lean-ctx-for-model-b` §S1, §S3, §S9 items 1, 5 and 7;
CR-MDB-072 (AXI envelopes read whole); `contracts/lean-ctx.md`.

## Context

- **Agents filter long runs.** Eleven self-reported breaches of the read-whole rule (CR-MDB-072) piped
  a Crucible client run through `grep -v`, `head` or `tail`, or sent it to a file they never read. The
  motive is always the same: Pi's shell tool keeps the last 2000 lines or 50 KB of a long run.
- **`ctx_shell` can alter an envelope** (lean-ctx 3.11.4, read in its source). The Crucible client
  is not a recognised test runner, so its output is compressible:
  - a TOON envelope survives byte-for-byte only up to about 4000 tokens, then is cut to its head,
    its tail and its "safety" lines;
  - a non-TOON envelope can be reshaped above 120 tokens.

  With `raw=true`, Pi's `ctx_shell` does not invoke lean-ctx at all.
- **The sanctioned path exists.** When Pi truncates a run, it saves the full output to a file and
  names it. Reading that file in windows is lossless, and the agent never chooses what to drop.
- **The context ledger is machine-wide.** One file, shared by every session, sub-agent and project,
  reports "context pressure" against a fixed 200000-token window. It suggests evicting entries.
  Evicting blocks a file for the session, and resetting clears the re-read dedup of every other
  session.

## Scope (seed)

1. **Client runs.** The generated RED, GREEN, VERIFY, FIX and BACKFILL definitions, and the sub-agent
   procedure, say: run the Crucible client through `ctx_shell` with `raw=true`; when the output is
   truncated, read the saved full-output file in windows until the envelope has been read whole;
   never pipe or filter it.
2. **The ledger.** The same surfaces say: the context-pressure figure is machine-wide; ignore its
   evict hints, and never evict or reset the ledger during a run.
3. **`AGENTS.md`** § Runtime/Tooling records both, and notes that a repo-wide search from the main
   checkout skips `.worktrees/` unless it is given a path.

## To measure at gap analysis

- How Pi names the saved file in the truncation notice, and whether `read` reaches it under the
  project's permission policy (CR-MDB-089).
- The overlap with CR-MDB-054 (a blocking hook on piped AXI output) and CR-MDB-083 (the test-scope
  ladder in the same templates); the order of the three.
- Whether any gate pins today's wording of the read-whole rule in the templates.
- **Score:** seeded at 3.
