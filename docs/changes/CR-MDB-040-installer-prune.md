# CR-MDB-040 — A redeploy removes what it no longer deploys

**Status:** PENDING (filed 2026-09-25 at CR-MDB-035's gap analysis)
**Type:** fix
**Priority:** P1 — release 1.0.0, wave 2. PRD §4 criterion 6 (as reconciled by CR-MDB-035) is
unmet until this merges.
**Depends on:** CR-MDB-035 (states the criterion this CR satisfies)
**Labels:** installer, manifest, deploy
**Design reference:** PRD §4 criterion 6; CR-MDB-033 (manifest always consulted, unmanaged never
clobbered, `target_root` recorded); CR-MDB-036 §S7 (stack-scoped installation); CR-MDB-037 §S2
(`deploy.deployed_freshness`, the `retired` class)

## Context

The installer records every file it deploys in `install.toml` (`[[files]]` `{path, sha256}`, paths
relative to the target root) and consults that manifest on the next run: a hand-modified managed
file is skipped unless `--force-managed`, and a file absent from the manifest is unmanaged and never
written (`deploy._deploy_file`, CR-MDB-033). It never removes anything.

Measured 2026-09-25 in a sandbox: installing `--stacks python,rust`, then `--reinstall --stacks
python`, leaves `.agents/skills/crucible-report-rust/` deployed while the new `install.toml` stops
recording it. Model B wrote it, and after that run no manifest owns it.

A retired bundle behaves the same way. This machine's `install.toml` (written 2026-07, before
CR-MDB-033) records 33 files, including `.agents/skills/chezmoi/SKILL.md` (retired by CR-MDB-031) and
`.agents/skills/crucible-report-vscode/SKILL.md` (retired by CR-MDB-024). It records no
`target_root`. The `already_installed` report (CR-MDB-037 §S2) classifies such entries as `retired`
and says "remove them by hand" (`cli.py:580-581`, `docs/install-guide.md` "The `already_installed`
report").

Only the installer flow deploys and rewrites the manifest. It runs when no `install.toml` exists
or when `--reinstall` is given. A bare `modelb-axi` over an existing install reports and changes
nothing.

## Scope

### §S1 — Prune after a successful deploy
In the installer's deploy stage (`cli._deploy_stage`), after `deploy_assets` succeeds and before
`write_install_toml`, a new `deploy.prune_assets(prior_root, prior_files, new_paths)` handles every
path recorded in the prior manifest and absent from the new manifest. Paths are compared after
normalisation (`os.path.normpath`): a prior entry spelled differently from a path this run deployed
(`x/../model-b/SKILL.md`, `./…`, `//`) is that path, and is never pruned. The prior entries are
read once, through one `config` helper, and de-duplicated by normalised path before any use (the
first entry wins, for the hash and for the corrupt-entry warning).

- **Removed:** the deployed file exists and its hash equals its recorded hash. It was Model B's and
  is unchanged. After removal, each directory left empty is removed, walking up and stopping at
  the store root (`.agents/skills`, `.agents/hooks/scripts`, `.agents/scripts`). A store root is
  never removed, and the walk stops at a directory that is a symbolic link (the link is left; the
  run does not fail).
- **Kept and reported (hand-modified):** the file exists with a different hash. `--force-managed`
  does not change this; a hand-edited file is never deleted. The new manifest keeps its entry with
  the recorded hash, so every later installer run reports it again, and it is pruned once the user
  restores or deletes it.
- **Already gone:** the file does not exist. Nothing to do; not reported.
- A prior path outside the three store directories (after normalising `..`; an absolute path is
  outside) is never touched. The deploy writes only there, so such an entry is corrupt: it is
  dropped from the new manifest, is in neither `removed` nor `kept`, and gets one warning naming it.

`prior_root` is the prior manifest's recorded `target_root`. When the prior manifest records none
(written before CR-MDB-033), it is this run's target root, which the install guide already tells
the user to pass (`--reinstall --target-root`). When the recorded `target_root` differs from this
run's, nothing is pruned, and a warning names the prior root and says its files were left in place.

An `OSError` while pruning raises `DeployError` (the `OSError` as its cause), so no `install.toml`
is written and the run ends with the `deploy_failed` outcome, like any deploy failure. A later run
re-prunes, and the already-gone paths are skipped. A run that fails before the deploy completes
(pre-flight, validation, deploy error) removes nothing.

### §S2 — Reporting
- The install envelope gains `removed: [...]` (target-root-relative paths) and `kept: [...]` (the
  hand-modified leftovers). Both are always present on the installed outcome, and empty when there
  is nothing to report.
- The human channel prints one line per removed path, plus one warning per kept path naming it and
  saying it is no longer deployed and was left because it was edited.
- The `already_installed` report's `retired` hint changes from "remove them by hand" to re-running
  the printed `--reinstall` command, which removes the unchanged ones. `docs/install-guide.md` says
  the same, and `pi-package/README.md` is regenerated from it.
- The `already_installed` report judges a recorded path that the recorded `[install].stacks` no
  longer deploy (a deselected stack's bundle) by what a `--reinstall` would do with it: unchanged →
  `retired`; edited → a new list `kept`, whose hint says it is no longer deployed and was left
  because it was edited — restore or delete it, then re-run the printed `--reinstall`. Such a path
  is never `hand_modified`, and no hint offers `--force-managed` for it.
- `docs/install-guide.md` states that a `--reinstall` naming fewer stacks removes the dropped
  stacks' unchanged skills (in "Adding stacks later"), describes the installed envelope's
  `removed` and `kept` fields, and says that when the recorded target root differs from this run's,
  the old root's files are left and no longer managed.

## Acceptance criteria

- [ ] Installing `--stacks python,rust`, then `--reinstall --stacks python` (sandboxed), removes
      every `crucible-report-rust` file and the `code-health` bundle, and their directories. The
      new manifest records neither. The envelope's `removed` lists them.
- [ ] A retired bundle recorded in a prior manifest is removed on `--reinstall`. Prove it with a
      fixture manifest recording `.agents/skills/chezmoi/SKILL.md` and its deployed file.
- [ ] A prior manifest with **no** `target_root` prunes against this run's `--target-root`.
- [ ] A prior manifest whose `target_root` differs from this run's prunes nothing and warns,
      naming the prior root.
- [ ] A hand-modified leftover is kept, with or without `--force-managed`. It is listed in `kept`
      and warned about by path.
- [ ] A kept leftover stays in the new manifest with its recorded hash; the next `--reinstall` lists
      it in `kept` again, and once the file is restored to that hash it is removed.
- [ ] A corrupt prior entry (outside the stores) is dropped from the new manifest, is in neither
      list, and is warned about by path.
- [ ] A pruning `OSError` ends with outcome `deploy_failed`.
- [ ] A prior entry that normalises to a path this run deployed (`…/x/../model-b/SKILL.md`,
      `./…`, `…//…`) never removes that file; the new manifest and the disk agree.
- [ ] A bundle directory that is a symbolic link: its unchanged leftover files are removed and
      listed in `removed`, the link is left, and the run ends `installed`.
- [ ] Duplicate prior entries: the first wins for both the prune decision and the recorded hash of
      a kept entry; a duplicated corrupt entry gets one warning.
- [ ] `already_installed` over an install with an edited leftover of a deselected stack lists it in
      `kept` (not `hand_modified`) with a hint that names no `--force-managed`; an unchanged one is
      `retired`.
- [ ] The install guide covers dropping stacks, the `removed`/`kept` fields and the differing-root
      case; `pi-package/README.md` is regenerated.
- [ ] Unmanaged files (never in the manifest) and files outside the three store directories are
      never removed, even when a corrupt prior entry names them.
- [ ] Store roots are never removed; empty bundle directories are.
- [ ] A run that fails in pre-flight, validation or deploy removes nothing. A pruning `OSError`
      writes no `install.toml`, and the next run completes the prune.
- [ ] The `retired` hint and the install guide say that `--reinstall` removes unchanged retired
      files. `pi-package/README.md` is regenerated, and `generator/build.py --check` is clean.
- [ ] `AGENTS.md`'s module count (if a module is added) and both suite baselines are re-measured.

## Non-goals

- No removal of anything the prior manifest does not record. Files orphaned by an install made
  before this CR are gone from the manifest already and stay unmanaged.
- No change to project-scoped rendering (`init`/`agents`), which has its own marker ownership.
- Running the reinstall on this machine is a release step, not part of this CR.
