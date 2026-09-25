# Crucible — Python stack (thin router)

**Authority:** the Model-B-owned bundled skill `crucible-report-python`
(`skills-src/crucible-report-python/`, deployed by the modelb-axi installer)
— the full verb surface (`test --tests <dotted.path>`, `regression
[--coverage]`, `check`, `auto-ingest`, gates), endpoint routing,
venv/interpreter rules, and report locations live THERE. Read it before
running anything.

Model B deltas only:

- Client: `~/.crucible/clients/python-crucible.py` — Crucible's installed
  client, listed in `~/.crucible/crucible-clients.json`; never a checkout of
  the Crucible project (see the `crucible` skill for why).
- Agent naming: `CR-<ACRONYM>-NNN-<cycle>-<PHASE>` for TDD-phase agents;
  `<agent-type>-<project>` for orchestrators. Pass `--agent` and
  `--project-dir` explicitly.
