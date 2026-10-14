# CR-MDB-071 — Release targets crates.io and Maven Central, and the release-readiness check

**Status:** PENDING — **SEED, not the finished spec.** Gap analysis, the spec and its pre-review
happen in order when this CR starts.
**Type:** feature (release workflow templates, CLI)
**Priority:** P1 — release 1.0.0, wave 2; after CR-MDB-068.
**Depends on:** CR-MDB-068 (board-authoritative: read `queue`)
**Labels:** release, ci, scaffold
**Design reference:** `docs/research/release-automation-crucible-procedure.md` § "Release workflow
templates (user rulings, 2026-10-14, at CR-MDB-068's gap analysis)"; CR-MDB-068 (the renderer, the
`RELEASE_TARGETS` key, the shipped scripts); CR-MDB-070 (the workflow's shape).

## Context

CR-MDB-068 renders a project's release workflow for the targets `pypi`, `npm` and `github-assets`. A Rust
crate and a Java library have no target, and nothing tells a project what it still lacks before its
first release or hotfix run.

## Scope (seed)

1. **The `crates` target:** the rehearsal (`cargo publish --dry-run` with the stamped `X.Y.Z-dev.N`) on
   every release or hotfix push; the publish on the release event through crates.io trusted publishing
   (`rust-lang/crates-io-auth-action`), guarded as CR-MDB-070's publishes are. A crate's first publish
   needs an API token; the setup says so.
2. **The `maven-central` target:** the rehearsal uploads a validated deployment and drops it; the
   publish on the release event uploads and publishes, with the Portal user token and the GPG key as
   repository secrets. The dev-version form for Maven is measured (Maven orders an unknown qualifier
   such as `-dev.N` after the release).
3. **The stamp script** learns `Cargo.toml` and `pom.xml`.
4. **A release-readiness check** (a `modelb-axi` verb, read-only) reports what the project lacks for a
   release or hotfix run: the rendered workflow and scripts (and their ownership state), each target's
   version source, the GitHub environments and their deployment rules, the repository secrets each job
   names; and, for what it cannot read (a registry's pending or trusted publisher), a checklist naming
   the exact fields.

## To measure at gap analysis

- crates.io trusted publishing's current action version, its environment field, and the dry-run with a
  prerelease version.
- The Central Portal's validate-and-drop behaviour and the plugin version; GPG signing in CI
  (`actions/setup-java` with `gpg-private-key`, or an import step).
- Maven's version ordering for each dev-version candidate.
- How the readiness check reads GitHub (`gh`, read-only) and what it reports without `gh` or without
  network.
- The 13-point cap.
