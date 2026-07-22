# Crucible — Bun / TypeScript stack (thin router)

**Authority:** the bundled skill `crucible-report-bun` at
`~/Documents/data_projects/crucible/clients/skills/crucible-report-bun/`
(`crucible:clients/skills/`) — the full verb surface (universal verbs + the
plan verbs `plan-file`, `cycle-activate`/`cycle-done`, `cr-close`), endpoint
routing, and report locations live THERE, managed by Crucible.
`bun-crucible.py` is the REFERENCE IMPLEMENTATION for the V2 client API. Read
the bundle before running anything.

Model B deltas only:

- Client: `~/Documents/data_projects/crucible/clients/bun-crucible.py` — the
  Crucible-owned source of truth. A project-vendored `clients/` copy is valid
  ONLY while a CR in that project is changing the client itself.
- When your prompt names a per-project context wrapper (e.g.
  `/tmp/claude-1000/<project>-crucible`), run every call THROUGH it — it pins
  the project key and display context; cycle attach is server-driven.
- Agent naming: `CR-<ACRONYM>-NNN-<cycle>-<PHASE>` for TDD-phase agents;
  `<agent-type>-<project>` for orchestrators. Pass `--agent` explicitly.
