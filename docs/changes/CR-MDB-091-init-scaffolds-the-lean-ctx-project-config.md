# CR-MDB-091 — `init` scaffolds the project's lean-ctx config

**Status:** PENDING — **SEED, not the finished spec** (filed 2026-10-29).
Gap analysis, the spec and its pre-review happen in order when this CR starts.
**Type:** feature (scaffold, the rendered `AGENTS.md` Setup section)
**Priority:** P2.
**Depends on:** CR-MDB-088 (it decides the knowledge-store levers); the board is authoritative: read
`queue`, not this line.
**Labels:** lean-ctx, scaffold, init
**Design reference:** research note `lean-ctx-for-model-b` §S4.5, §S5, §S9 item 3; PRD D5.

## Context

lean-ctx reads a per-project `.lean-ctx.toml`. Its non-sensitive keys apply without `lean-ctx trust`;
its sensitive keys (shell allowlists, write paths) need the project trusted. Model B scaffolds none,
so every project runs on the global config. That means indexing walks build output and test reports,
and lean-ctx's own automatic captures compete with the project's facts for the 200-fact cap.

## Scope (seed)

1. **`init` writes `.lean-ctx.toml`** with non-sensitive keys only, under the ownership marker:
   - per-stack index excludes (`test-reports/`, `target/`, `node_modules/`, build directories);
   - `preserve_compact_formats = ["toon"]`;
   - a raised knowledge-store fact cap, and whether automatic consolidation is off (CR-MDB-088's
     ruling).
2. **The Setup section** tells the user to run `lean-ctx index build`. It says `lean-ctx trust .` is
   needed only if they add sensitive keys.
3. **Existing projects** get the file from `modelb-axi agents`, under the same ownership rules as the
   permission policy.

## To measure at gap analysis

- The key names and their sensitivity in lean-ctx's released config reference.
- Whether a marker comment is valid in the file, as it is for the permission policy.
- Which keys each stack needs.
- **Score:** seeded at 5.
