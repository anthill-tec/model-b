# CR-MDB-058 — Release notes and the release rehearsal

**Status:** PENDING — **SEED, not the finished spec** (filed 2026-10-10 into release 1.0.0, wave 2).
Gap analysis, the design record, the spec and its pre-review happen in order when this CR starts.
**Type:** feature (release process, CI, packaging metadata, scaffold templates)
**Priority:** P1 — release 1.0.0, wave 2 (user ruling 2026-10-10: Crucible #1433 part A adopted into 1.0.0).
**Depends on:** none (board-authoritative: read `queue`, not this line)
**Labels:** release, ci, packaging, scaffold, templates
**Design reference:** Crucible #1433 §A (Mainline - Crucible, 2026-10-10), reference implementation
Crucible commit `280326a` (`CHANGELOG.md`, `RELEASING.md` step 3, `release.yml` create-release,
`pyproject.toml`, `package.json`) and the Crucible 0.3.0 release notes; PRD D10; the `git-workflow`
skill § Releases.

## Context

Model B releases with `gh release create --generate-notes` (`.github/workflows/release.yml`
create-release), which produces a bare changelog link, and its documented release flow copies the
install-guide regions into hand-written release notes. Model B has no `CHANGELOG.md`, no
`[project.urls]` in `pyproject.toml`, and `pi-package/package.json` lists no `files`. The release
rehearsal is a manual `workflow_dispatch`; the version is the static `modelb_axi.__version__`, not
hatch-vcs. Model B has no CI test workflow at all.

## Scope (seed)

1. **A1 — release notes are a release task.** `CHANGELOG.md` at the repo root in Keep a Changelog
   1.1.0 form (`## [Unreleased]`; one `## [X.Y.Z] - YYYY-MM-DD` section per release grouped
   Added/Changed/Deprecated/Removed/Fixed/Security; an **Upgrading** note first when an operator must
   act; compare links at the foot), written on the release branch before `finish`. One source, three
   readers: the release job takes the tag's section as the GitHub Release body
   (`gh release create --notes-file`), PyPI shows `[project.urls]` `Changelog` and `Release Notes`
   (PEP 753 labels), and npm ships `CHANGELOG.md` through `package.json` `files`.
2. **A1 — templates for every Model B project that releases.** A `CHANGELOG.md` skeleton, the
   release step, the release-job snippet and the two packaging entries, laid down by `init` (and by
   `migrate`, CR-MDB-055, when it lands) and named in the `git-workflow` skill's release flow.
3. **A2 — every push to `release/**` or `hotfix/**` is the rehearsal** (TestPyPI and npm dry-run),
   so a manual dispatch only re-runs one. *Measure:* the rehearsal's version under the static
   `__version__` source; whether `release-branch-semver` (a hatch-vcs scheme) applies at all, or
   the version-source change is its own decision.
4. **Model B's own 1.0.0 uses it.** The 1.0.0 release notes are the first `CHANGELOG.md` section;
   the documented release flow's "copy the install-guide regions into the release notes" step is
   reconciled with it.

## To measure at gap analysis

- The release flow text (`git-workflow` § Releases, the `release-1-0-0-on-hold` record), the
  `release.yml` jobs, `tests/test_package_publishing.py` and every test pinning release mechanics
  (CR-MDB-054 item 2 calls release/CI configuration "not a test subject" — reconcile).
- "Keep CI green on develop" presupposes a CI test workflow Model B does not have; whether adding one
  is in scope or a follow-up.
