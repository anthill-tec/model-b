# Crucible — Rust / Cargo stack (thin router)

**Authority:** the Model-B-owned bundled skill `crucible-report-rust`
(`skills-src/crucible-report-rust/`, deployed by the modelb-axi installer) —
the full verb surface (`test --crate`, `regression-ingest`,
`workspace-regression`, `clippy`, gates), endpoint routing, and report
locations live THERE. Read it before running anything.

Model B deltas only:

- Client: `~/.crucible/clients/rust-crucible.py` — Crucible's installed
  client, listed in `~/.crucible/crucible-clients.json`; never a checkout of
  the Crucible project (see the `crucible` skill for why).
- When your prompt names a per-project context wrapper (e.g.
  `/tmp/claude-1000/<project>-crucible`), run every call THROUGH it — it pins
  the project key and display context; cycle attach is server-driven.
- Agent naming: `CR-<ACRONYM>-NNN-<cycle>-<PHASE>` for TDD-phase agents;
  `<agent-type>-<project>` for orchestrators. Pass `--agent` explicitly.
