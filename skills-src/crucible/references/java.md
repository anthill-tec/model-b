# Crucible — Quarkus / Java stack (thin router)

**Authority:** the Model-B-owned bundled skill `crucible-report-java`
(`skills-src/crucible-report-java/`, deployed by the modelb-axi installer) —
the full verb surface (`unit --test`, `module`, `regression` with JaCoCo,
gates), endpoint routing, and report locations live THERE. Read it before
running anything.

Model B deltas only:

- Client: `~/.crucible/clients/mvn-crucible.py` — Crucible's installed
  client, listed in `~/.crucible/crucible-clients.json`; never a checkout of
  the Crucible project (see the `crucible` skill for why).
- Agent naming: `CR-<ACRONYM>-NNN-<cycle>-<PHASE>` for TDD-phase agents;
  `<agent-type>-<project>` for orchestrators. Pass `--agent` explicitly.
