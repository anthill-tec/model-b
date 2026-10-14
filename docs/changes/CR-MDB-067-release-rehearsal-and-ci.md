# CR-MDB-067 — The release rehearsal on every release or hotfix push, and CI tests on develop

**Status:** PENDING — **SEED, not the finished spec.** Gap analysis, the spec and its pre-review
happen in order when this CR starts.
**Type:** feature (CI workflows, release workflow)
**Priority:** P1 — release 1.0.0, wave 2; after CR-MDB-058.
**Depends on:** CR-MDB-058 (board-authoritative: read `queue`)
**Labels:** release, ci
**Design reference:** `docs/research/release-automation-crucible-procedure.md` § "What Model B adopted
(2026-10-14)"; Crucible #1433 §A2; DN-multi-harness-deploy-model §D21 (CI runs outside agent
sessions).

## Context

The release rehearsal is a manual `workflow_dispatch` (`rehearse-testpypi`), and Model B has no CI test
workflow, so a red `develop` goes unnoticed until a release. TestPyPI never accepts the same file twice,
and the version is the fixed `modelb_axi.__version__`, so rehearsing every push needs a distinct version
per push.

## Scope (seed)

1. **Every push to `release/**` or `hotfix/**` is the rehearsal.** In CI's own checkout, the version is
   stamped from the branch name and the run: `X.Y.Z.devN` into `__version__` and `X.Y.Z-dev.N` into
   `pi-package/package.json`. The rehearsal uploads to TestPyPI and runs `npm publish --dry-run`. A
   manual dispatch only re-runs one. A tag still builds exactly `X.Y.Z`, and the repository's version
   source is unchanged.
2. **The rehearsal also proves the release body:** it extracts the branch version's `CHANGELOG.md`
   section the way `create-release` will (CR-MDB-058), and fails on a missing or empty one.
3. **A CI test workflow** runs the suite on Python 3.14 on every push to `develop`, `release/**` and
   `hotfix/**`, and on pull requests, in a clean home without Pi or Crucible (the empty-`HOME` shape).
   It fetches full history where a test needs it.
4. **Templates:** the stamping rule and the CI-test snippet join the `git-workflow` skill's release
   flow beside CR-MDB-058's, per stack.

## To measure at gap analysis

- The suite on a clean hosted runner: clean-runner-only failures (Crucible found four), the skips, the
  wall time, and what `build`, `pi` and `node` the checks need.
- The GitHub environments `pypi`, `testpypi` and `npm` (unchecked in the setup status) and the
  TestPyPI trusted publisher for a push-triggered job.
- Whether the version stamp belongs in a repository script (testable) or inline in the workflow.
