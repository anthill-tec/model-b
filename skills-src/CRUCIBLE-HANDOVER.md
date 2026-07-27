# Crucible skills handover — provenance record (CR-MDB-016 §S1)

Provenance of the seven skill bundles imported verbatim into `skills-src/`.
This document is the ONLY place under `skills-src/` allowed to cite the origin
path; the imported files themselves were never edited.

## Origin

- **Origin repo:** `~/Documents/data_projects/crucible` (the Crucible repo)
- **Origin path:** `clients/skills/` (Crucible's `crucible:clients/skills/`)
- **Origin commit at handover:** `74018ea7af6dc55e0fc878eb87890e5097c58cf2`
- **Handover date:** 2026-07-28
- **Import method:** byte-identical copy (`cp -r`, verified with `diff -r` —
  zero differences across all seven bundles)

## Bundles imported (7 of 8)

- `crucible-register`
- `crucible-report-arduino`
- `crucible-report-bun`
- `crucible-report-java`
- `crucible-report-python`
- `crucible-report-rust`
- `crucible-report-vscode`

## Ratification

- Sandesh **#1336** — Mainline - Crucible's handover request (CR-CRU-035 skills
  division confirmation + the stale-deployed-skill defect report, 2026-07-27).
- Sandesh **#1337** — Model B's ratified answer (user ratification 2026-07-28):
  Model B takes FULL ownership of the skills component — content, bundling, AND
  deploy. Crucible exits the skills business; its `clients/skills/` copy freezes
  after this import.

## Exclusion: agent-protocol (Option B)

The eighth origin bundle, `agent-protocol`, is deliberately **NOT imported**
(gap-analysis DRIFT-3, user decision **Option B** 2026-07-28, PRD §D4
reaffirmed). The Wave-2 absorb decision stands — the standalone skill stays
retired; its delta (the since-become-real `/api/v2/agents/heartbeat` touch
surface) is absorbed into `skills-src/crucible/` per CR-MDB-016 §S2(b). Its
shell helper script was NOT adopted (the clients' `register` verb covers the
rare status-change touch; the PRD §4.2 helper-script ban stays absolute). Its
MDX-platform content (CodeForge/Velocity) is out of scope.
