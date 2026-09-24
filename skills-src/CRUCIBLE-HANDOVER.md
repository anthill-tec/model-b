# Crucible skills handover — provenance record (CR-MDB-016 §S1)

Provenance of the skill bundles imported verbatim into `skills-src/` — seven at
handover, six since CR-MDB-024 §S3 (see *Retirement* below).
This document is the ONLY place under `skills-src/` allowed to cite the origin
path; the bundles were imported byte-identical and have since been maintained as
Model B doc-syncs (CR-MDB-017, CR-MDB-020).

## Origin

- **Origin repo:** `~/Documents/data_projects/crucible` (the Crucible repo)
- **Origin path:** `clients/skills/` (Crucible's `crucible:clients/skills/`)
- **Origin commit at handover:** `74018ea7af6dc55e0fc878eb87890e5097c58cf2`
- **Handover date:** 2026-07-28
- **Import method:** byte-identical copy (`cp -r`, verified with `diff -r` —
  zero differences across all seven bundles)

## Bundles imported (6 of 8)

- `crucible-register`
- `crucible-report-arduino`
- `crucible-report-bun`
- `crucible-report-java`
- `crucible-report-python`
- `crucible-report-rust`

## Retirement: the editor-overlay bundle (CR-MDB-024 §S3)

The seventh bundle imported at handover — the crucible-report bundle for the
VS Code editor overlay — was deleted outright by CR-MDB-024 §S3 (user ruling
2026-09-22): an IDE is not a stack. Extension work in TypeScript is served by
the bun stack; there is no separate editor-overlay agent set to report for.
The roster above is therefore six of the eight origin bundles.

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

## Maintenance contract — the ongoing coupling (user, 2026-07-28)

Ownership of these skill DOCS is Model B's, but the CLIENT SCRIPTS they
document remain Crucible-owned and keep evolving. That is a standing coupling:

- **Every Crucible client-surface change (verbs, flags, envelope, endpoints)
  obligates a Model B doc-sync** of the affected bundle(s) here — integrated
  INDEPENDENTLY into this copy (Crucible's `clients/skills/` is frozen and is
  never re-imported wholesale after the handover commit above).
- **Coordination channel: Sandesh** (Mainline - Crucible ⟷ Mainline - ModelB).
  Crucible intimates client changes on the #1336 thread; Model B syncs the
  bundle content, republishes the artifact, and redeploys via `modelb-axi`.
- Drift check at every wave boundary: bundle docs vs the live client
  `--help`/behavior for each stack.
- **Pre-release ask (matter of principle, user 2026-07-28): before EVERY Model B
  release, ask Crucible over Sandesh whether any client changes have shipped
  since the last sync — never rely on their intimations alone. A release goes
  out only against a confirmed-current doc set. (Release-CR checklist step,
  starting with CR-MDB-012.)
