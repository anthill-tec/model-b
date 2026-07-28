# Crucible — Arduino / firmware stack (thin router)

**Authority:** the Model-B-owned bundled skill `crucible-report-arduino`
(`skills-src/crucible-report-arduino/`, deployed by the modelb-axi installer)
— the full verb surface (`test`/`unit` (native host make junit),
`regression`, `auto-ingest`, `check`/`compile` (arduino-cli), gates),
endpoint routing, and report locations live THERE. Read it before running
anything.

Model B deltas only:

- Client: `~/Documents/data_projects/crucible/clients/arduino-crucible.py` —
  the Crucible-owned source of truth. A project-vendored `clients/` copy is
  valid ONLY while a CR in that project is changing the client itself.
- When your prompt names a per-project context wrapper (e.g.
  `/tmp/claude-1000/<project>-crucible`), run every call THROUGH it — it pins
  the project key and display context; cycle attach is server-driven.
- Agent naming: `CR-<ACRONYM>-NNN-<cycle>-<PHASE>` for TDD-phase agents;
  `<agent-type>-<project>` for orchestrators. Pass `--agent` and
  `--project-dir` explicitly.
