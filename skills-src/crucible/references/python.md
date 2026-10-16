# Crucible — Python stack (thin router)

**Authority:** the Model-B-owned bundled skill `crucible-report-python`
(`skills-src/crucible-report-python/`, deployed by the modelb-axi installer)
— the full verb surface (`test --tests <dotted.path>`, `regression
[--coverage]`, `check`, `auto-ingest` (recovery only), gates), endpoint routing,
venv/interpreter rules, and report locations live THERE. Read it before
running anything.

Model B deltas only:

- Client: `~/.crucible/clients/python-crucible.py` — Crucible's installed
  client, listed in `~/.crucible/crucible-clients.json`; never a checkout of
  the Crucible project (see the `crucible` skill for why).
- Agent naming: `CR-<ACRONYM>-NNN-<cycle id>-<ROLE>` for TDD-role agents;
  `<agent-type>-<project>` for orchestrators. Pass `--agent` and
  `--project-dir` explicitly.
- Coverage: pass `--cov-source` to `regression --coverage` and
  `pre-merge-gate`, naming the project's own packages and directories, because
  the client's default names Crucible's own (`crucible_axi,clients`).
- Subprocesses: scripts the tests run as subprocesses are measured only with
  coverage.py 7.10 or later and `patch = ["subprocess"]` in the project's
  coverage config, and only in a child whose interpreter has coverage.py and
  inherits the environment.
- Stale data: remove the reports directory's `.coverage` and every
  `.coverage.*` before a coverage run, because a stale data file is merged into
  the next run's figures.
