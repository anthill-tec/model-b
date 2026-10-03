# CR-MDB-051 — Reference hygiene: client paths and bare line references

**Status:** PENDING — **SEED, not the finished spec** (filed 2026-10-02 into release 1.1.0, wave 3).
Every item below is re-measured at gap analysis; the spec is written then.
**Type:** docs/test hygiene
**Priority:** P3 — release 1.1.0, wave 3.
**Depends on:** none (board-authoritative: read `queue`, not this line)
**Labels:** docs, tests, hygiene
**Design reference:** AGENTS.md (Crucible's installed clients, listed in
`~/.crucible/crucible-clients.json`, are the only client surface); CR-MDB-020 (client-path anchoring)

## Scope (seed)

1. **`<stack>-crucible.py` placeholders.** `skills-src/crucible/SKILL.md` (its description and the
   installed-clients paragraph) and `skills-src/README.md` still show the generic
   `~/.crucible/clients/<stack>-crucible.py`. Decide whether the placeholder stays (with the
   manifest as the resolver) or names the manifest lookup.
2. **Bare line references in tests** (CR-MDB-044 follow-up). `tests/test_tooling_adoption.py` and
   `tests/test_tooling_detachment.py` cite specs and scripts by line number in forms the line-ref
   guard's `<file>.<ext>:<digits>` pattern does not catch. Cite by symbol or section, and widen the
   guard if it should catch them.
