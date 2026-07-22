# Crucible — VS Code extension / TypeScript stack (thin router)

There is **no client** for this stack yet — no `*-crucible.py` CLI exists;
the future client is CRUCIBLE's deliverable (thread #1322).

**Authority:** the bundled skill `crucible-report-vscode` at
`~/Documents/data_projects/crucible/clients/skills/crucible-report-vscode/`
(`crucible:clients/skills/`) — the documented interim inline urllib ingest
procedure (parse JUnit → `POST /api/v2/runs/parsed`, build failures →
`/api/v2/runs/compile`) lives THERE, managed by Crucible. Do not build a
client ad hoc; when Crucible ships one, the interim procedure dies and the
client becomes mandatory, as on every other stack.

Model B deltas only:

- When your prompt names a per-project context wrapper (e.g.
  `/tmp/claude-1000/<project>-crucible`), source its pinned project key and
  display context; cycle attach is server-driven.
- Agent naming: `CR-<ACRONYM>-NNN-<cycle>-<PHASE>` for TDD-phase agents;
  `<agent-type>-<project>` for orchestrators. Pass the agent id explicitly in
  every payload.
