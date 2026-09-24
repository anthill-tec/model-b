# Crucible — Bun / TypeScript stack (thin router)

**Authority:** the Model-B-owned bundled skill `crucible-report-bun`
(`skills-src/crucible-report-bun/`, deployed by the modelb-axi installer) —
the full verb surface (universal verbs + the plan verbs `plan-file`,
`cycle-activate`/`cycle-done`, `cr-close`), endpoint routing, and report
locations live THERE. `bun-crucible.py` is the REFERENCE IMPLEMENTATION for
the V2 client API. Read the bundle before running anything.

Model B deltas only:

- Client: `~/.crucible/clients/bun-crucible.py` — Crucible's installed
  client, listed in `~/.crucible/crucible-clients.json`; never a checkout of
  the Crucible project (see the `crucible` skill for why).
- Agent naming: `CR-<ACRONYM>-NNN-<cycle>-<PHASE>` for TDD-phase agents;
  `<agent-type>-<project>` for orchestrators. Pass `--agent` explicitly.
