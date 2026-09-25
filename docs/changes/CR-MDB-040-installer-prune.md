# CR-MDB-040 — A redeploy removes what it no longer deploys

**Status:** PENDING (filed 2026-09-25 at CR-MDB-035's gap analysis)
**Type:** fix
**Priority:** P1 — release 1.0.0, wave 2. PRD §4 criterion 6 (as reconciled by CR-MDB-035) is
unmet until this merges.
**Depends on:** CR-MDB-035 (states the criterion this CR satisfies)
**Labels:** installer, manifest, deploy
**Design reference:** PRD §4 criterion 6; CR-MDB-033 (manifest always consulted, unmanaged never
clobbered); CR-MDB-036 (stack-scoped installation); CR-MDB-037 §S2 (`deployed_freshness`)

## Context

The installer records every file it deploys in `install.toml` and consults that manifest on the
next run, so a hand-modified file is skipped and an unmanaged one is never written (CR-MDB-033).
It never removes anything. Measured 2026-09-25 in a sandbox (`--target-root`, `--modelb-home`,
`HOME` all under `/tmp`): installing `--stacks python,rust` then `--reinstall --stacks python`
leaves `.agents/skills/crucible-report-rust/` deployed, while the new `install.toml` no longer
records it. The file is now unmanaged by accident: Model B wrote it, no manifest owns it, and no
later run will touch it.

The same happens to a bundle Model B retires. CR-MDB-031 retired `chezmoi`; a machine installed
before that keeps `~/.agents/skills/chezmoi/` forever, and Pi keeps loading it. `modelb-axi`'s
freshness report (CR-MDB-037 §S2, `deploy.deployed_freshness`) already classifies such entries as
`retired` and tells the user to "remove them by hand" (`cli.py:580-581`).

## §S0 — Gap-analysis questions

- Which runs prune: a `--reinstall` only, or every installer run that rewrites the manifest.
- What "managed" means at removal time: a prior-manifest entry whose deployed hash still equals
  its recorded hash. A hand-modified or unmanaged file is never removed — confirm against
  CR-MDB-033's rules and the `--force-managed` semantics.
- Empty bundle directories left after removal.
- Whether the `retired` hint in the freshness report becomes an action or stays a report.
- The real machine's pre-CR-031 manifest records `harnesses = ["claude-code"]`, which is refused
  until a `--reinstall --harnesses pi`; that reinstall is where pruning first runs for real.

## Acceptance criteria (draft)

- [ ] A redeploy removes every file recorded in the prior manifest, absent from the new one, whose
      deployed hash equals its recorded hash — proven for a narrowed `--stacks` and for a retired
      bundle.
- [ ] A hand-modified or unmanaged file is never removed; it is reported.
- [ ] The envelope reports removed paths; the human report names them.
- [ ] A failed run removes nothing (validation before the first write, as today).
- [ ] Suite baselines re-measured and recorded in `AGENTS.md`.

## Non-goals

- No removal of anything outside the manifest.
- No change to project-scoped rendering (`init`/`agents`), which has its own marker ownership.
