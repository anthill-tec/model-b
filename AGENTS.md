# Model B (MDB) — project AGENTS.md

Project-level conventions for every session/agent working this repo. `CLAUDE.md` is a symlink to this file (harness compatibility; the ecosystem is harness-agnostic).

## Identity & naming (registry: `.env` at repo root)
- Project **Model B** · token `modelb` · acronym `MDB` · repo `model-b`.
- Solo Model B project; orchestrator **`vidushi-mdb`** (label AND Crucible id for orchestrator-level ops: gates, regression). Multi-track projects would use `Mainline-<short>` / `track<N>-<short>` labels.
- CR ids: `CR-MDB-NNN`.
- **Crucible agentIds (per python-crucible.py's agent-naming header — READ IT, don't improvise): TDD-phase agents = `CR-MDB-NNN-<cycle>-<PHASE>`** (e.g. `CR-MDB-002-C1-RED`); orchestrator ops = `vidushi-mdb`.
- Sandesh: project `ModelB`, address `Mainline - ModelB`.

## Workflow rules (this project)
- **Wave** = a grouping of CRs marking an execution boundary (solo: redesign point between groups). Setup tasks and the release are NOT waves; a release CR bundles the final gates.
- Queue (`docs/changes/README.md`) holds STRUCTURE only (CR/Title/Wave/Depends-on + dated Notes); live status is DERIVED on the Crucible board (plans/cycles/milestones; close via `cr-close --commit`).
- Plans: filed at CR start via the source-of-truth client (`crucible:clients/bun-crucible.py`) with `--wave <n> --orchestrator vidushi-mdb`; cycle ids are SERVER-ASSIGNED — never guessed; cycle labels `C<n> <label> (§S…)`.
- **Test runs go ONLY through the context wrapper `/tmp/claude-1000/modelb-crucible`** (injects `WORKFLOW_CYCLE_ID/CYCLE/WAVE`; `WORKFLOW_ROLE` absent in solo). Recreate it at session start if `/tmp` was cleared (see project memory).
- Chezmoi discipline for every `~/.claude` mutation: no-auto temp config + manual source commits; deletions via `chezmoi destroy`/`forget` (plain `rm` resurrects); NEVER `apply`, NEVER push the source repo.
- Structural waves run with NO other live Model B orchestrator sessions.
- **Electronics stack is EXCLUDED** (anthill-forge dead; agents/skills under revision) — never migrate/document/generate it.

## Authoritative docs
- Design contract: `docs/research/PRD-model-b-rationalization.md` (D1–D10).
- Queue: `docs/changes/README.md` · Specs: `docs/changes/CR-MDB-NNN-*.md`.
- Ontology (LOCKED, cite never fork): `crucible:docs/research/DN-model-b-language.md`.
- Hooks strategy: `docs/research/DN-harness-agnostic-hooks.md` · Audit evidence: `audits/`.
- Upstream tool providers: Crucible (tracking) + Sandesh (messaging) — requests via Sandesh cross-project.
