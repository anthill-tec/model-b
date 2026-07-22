# Crucible — Python stack (thin router)

**Authority:** the bundled skill `crucible-report-python` at
`~/Documents/data_projects/crucible/clients/skills/crucible-report-python/`
(`crucible:clients/skills/`) — the full verb surface (`test --tests
<dotted.path>`, `regression [--coverage]`, `check`, `auto-ingest`, gates),
endpoint routing, venv/interpreter rules, and report locations live THERE,
managed by Crucible. Read it before running anything.

Model B deltas only:

- Client: `~/Documents/data_projects/crucible/clients/python-crucible.py` —
  the Crucible-owned source of truth. A project-vendored `clients/` copy is
  valid ONLY while a CR in that project is changing the client itself.
- When your prompt names a per-project context wrapper (e.g.
  `/tmp/claude-1000/<project>-crucible`), run every call THROUGH it — it pins
  the project key and display context; cycle attach is server-driven.
- Agent naming: `CR-<ACRONYM>-NNN-<cycle>-<PHASE>` for TDD-phase agents;
  `<agent-type>-<project>` for orchestrators. Pass `--agent` and
  `--project-dir` explicitly.
