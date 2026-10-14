# CR-MDB-071 — Release targets crates.io and Maven Central, and the release-readiness check

**Status:** PENDING — spec (gap analysis 2026-10-15).
**Type:** feature (release workflow templates, CLI)
**Priority:** P1 — release 1.0.0, wave 2; after CR-MDB-068.
**Depends on:** CR-MDB-068 (board-authoritative: read `queue`)
**Labels:** release, ci, scaffold
**Design reference:** `docs/research/release-automation-crucible-procedure.md` § "The crates and Maven
Central targets and the readiness check (user rulings, 2026-10-15…)" and § "Release workflow templates
(…2026-10-14…)"; CR-MDB-068 (the renderer, `RELEASE_TARGETS`, `parse_target`, the shipped scripts, the
setup tasks); CR-MDB-070 (the workflow's shape: tests gate every publish, the ref guard).

## Context

- **`RELEASE_TARGETS` knows `pypi`, `npm` and `github-assets`** (`workflows.RELEASE_TARGETS`, one parser
  `workflows.parse_target`, `_VERSIONED = ("pypi", "npm")`). A Rust crate or a Java library has no target.
- **The renderer is built from parts** under `workflows-src/release/` (`rehearse-<target>.yml`,
  `publish-<target>.yml`, `setup-<target>.yml`), filled by `@@NAME@@` placeholders; actions are pinned in
  `workflows.ACTION_PINS`.
- **`stamp_version.py`** reads `pyproject.toml` (static or hatch-dynamic) and `package.json`.
- **Measured 2026-10-15:**
  - crates.io trusted publishing works through `rust-lang/crates-io-auth-action` (v1.0.5,
    `c6f97d42243bad5fab37ca0427f495c86d5b1a18`), and cannot publish a crate's first version;
    `cargo publish --dry-run` packages and builds without uploading, and accepts a semver prerelease.
  - Maven orders an unknown qualifier after the release (`1.0.0-dev.5` > `1.0.0`).
  - Sonatype's `central-publishing-maven-plugin` 0.12.0 has `skipUpload` (stage, sign and bundle, no
    upload), `autoPublish` and `waitUntil`; credentials are a Portal user token in `settings.xml` under
    `publishingServerId` (`central`); signing needs GPG; `actions/setup-java` writes `settings.xml` and
    imports a GPG key from its inputs.
- **Nothing tells a project what it lacks** before a release: the workflow and scripts, version sources,
  GitHub environments and secrets, registry publishers.

## Scope

### §S1 — Two new targets

- `workflows.RELEASE_TARGETS` becomes `("pypi", "npm", "crates", "maven-central", "github-assets")` (the
  canonical order); `crates` and `maven-central` take an optional `:dir` like `pypi` and `npm` and carry a
  version source; `release_targets_csv` and `parse_target` accept them under every existing rule.

### §S2 — The version sources

`stamp_version.py` learns, under its existing rules (one stderr line per refusal, nothing written, bytes
preserved, CRLF and trailing comments kept):

- **`crates:<dir>`** — `<dir>/Cargo.toml`'s `[package] version = "…"`; or, with `version.workspace =
  true` there, the repository root `Cargo.toml`'s `[workspace.package] version = "…"`. `stamp` writes
  `X.Y.Z-dev.N`. Refused: no `[package]` table, no version line, a workspace version with no
  `[workspace.package] version`.
- **`maven-central:<dir>`** — `<dir>/pom.xml`'s project `<version>` (the child of `<project>`, never the
  `<parent>`'s). **`stamp` leaves it unchanged** (the rehearsal uploads nothing; Maven would order a dev
  qualifier after the release) but still refuses a version other than `X.Y.Z`; `check` compares it.
  Refused: no project `<version>`, a property reference (`${…}`).

### §S3 — The rendered jobs

Each new target adds, in canonical order:

- **`rehearse` steps:**
  - `crates:<dir>` — `cargo publish --dry-run --allow-dirty` in `<dir>` (the stamp has edited
    `Cargo.toml`);
  - `maven-central:<dir>` — `actions/setup-java` (`temurin`, `"21"`, `server-id: central`, the server
    username/password env names, `gpg-private-key: ${{ secrets.MAVEN_GPG_PRIVATE_KEY }}`), then
    `./mvnw -B -ntp deploy -DskipTests` in `<dir>` with the plugin's skip-upload property set, its
    `MAVEN_CENTRAL_USERNAME`/`MAVEN_CENTRAL_PASSWORD`/`MAVEN_GPG_PASSPHRASE` env from repository secrets.
    The property names (`skipUpload`, `autoPublish`) are measured from the plugin in C1 and pinned.
- **Publish jobs** on the release event, `needs:` every test job, checkout `fetch-depth: 0` and the ref
  guard first:
  - `publish-crates` — environment `crates`, `contents: read` + `id-token: write`; job env
    `CARGO_FIRST_TOKEN: ${{ secrets.CARGO_REGISTRY_TOKEN }}`; `rust-lang/crates-io-auth-action` with
    `id: auth` and `if: env.CARGO_FIRST_TOKEN == ''`; `cargo publish` in `<dir>` with
    `CARGO_REGISTRY_TOKEN: ${{ steps.auth.outputs.token || secrets.CARGO_REGISTRY_TOKEN }}`;
  - `publish-maven-central` — environment `maven-central`, `contents: read`; `actions/setup-java` as in
    the rehearsal; `./mvnw -B -ntp deploy -DskipTests` in `<dir>` with auto-publish on and the wait until
    published.
- **`create-release`'s check step** names the `crates` and `maven-central` targets with the others.
- **The header's setup list:**
  - `crates` — the environment `crates` admitting the version tags; the repository secret
    `CARGO_REGISTRY_TOKEN` for the first publish, then add the crates.io trusted publisher (repository,
    `release.yml`, environment `crates`) and delete the token;
  - `maven-central` — the environment `maven-central` admitting the version tags; the namespace verified on
    the Central Portal; the repository secrets `MAVEN_CENTRAL_USERNAME`, `MAVEN_CENTRAL_PASSWORD` (a Portal
    user token), `MAVEN_GPG_PRIVATE_KEY` and `MAVEN_GPG_PASSPHRASE`; the POM carrying the plugin, the
    sources and javadoc jars, and the signing plugin.
- `ACTION_PINS` gains `rust-lang/crates-io-auth-action`.

### §S4 — Setup tasks

`init`'s `release_setup` and the `AGENTS.md` Setup section gain each new target's tasks (the header's list,
as tasks), in the same form as CR-MDB-068's.

### §S5 — `modelb-axi release-check`

A read-only verb, beside `release-workflow`, run from the project root:

- **Reads** `PROJECT_STACKS` and `RELEASE_TARGETS` from `.env` (refused, exit 2, when absent or invalid, as
  `release-workflow` refuses).
- **Checks, each item `ready`, `missing` or `unknown` with a one-line detail:**
  - **local:** each rendered file present and its ownership state (`intact` ready; `hand-modified`
    ready, noted; `unmanaged` or absent missing); each versioned target's version source readable by
    `stamp_version.py`'s rules; each stack's and target's prerequisite (`tests/`, the lockfile, `mvnw`,
    an executable `ci-test` or `build-assets`); `CHANGELOG.md` with an `## [Unreleased]` section;
  - **GitHub** (the `origin` remote's owner/repository, through read-only `gh api`): each target's
    environment exists, `testpypi` admitting `release/**` and `hotfix/**`, each publish environment
    admitting the version tags or carrying no branch rule; each repository secret the rendered jobs name
    exists, `RELEASE_PAT` always (the first-publish tokens `NPM_TOKEN` and `CARGO_REGISTRY_TOKEN` reported
    `unknown` when absent: not needed once the trusted publisher exists). No `gh`, no remote, an API error
    or no network → `unknown`;
  - **registries:** each target's publisher (PyPI and TestPyPI pending or trusted publisher, the npm and
    crates.io trusted publisher, the Central namespace) is `unknown`, its detail naming the exact fields to
    check.
- **One AXI envelope** (verb `release-check`): `items` (`area`, `item`, `state`, `detail`), and the counts
  `ready`, `missing`, `unknown`. **Exit 0** when nothing is missing, **1** when anything is, **2** on a
  refusal.
- **Never writes**, never runs `gh` other than `gh api` GET requests.

### §S6 — The skill and the docs

- **`skills-src/git-workflow/SKILL.md` § Releases:** the targets table gains `crates` and `maven-central`;
  `### Rehearsal and CI`'s per-target rows gain `crates` (`X.Y.Z-dev.N`, `cargo publish --dry-run`) and
  `maven-central` (no dev version; the bundle signed, nothing uploaded); the release flow runs
  `modelb-axi release-check` before `git flow release start` and fixes what it reports missing.
- **`AGENTS.md`** names `modelb-axi release-check`; **`docs/install-guide.md`** names the new targets in its
  `--release-targets` sentence and `release-check` beside `release-workflow` (`pi-package/README.md`
  regenerated).
- Model B's own files are unchanged (its targets are `pypi,npm:pi-package`); the byte-equality test holds.

## Acceptance criteria

- [ ] **§S1.** The new names in the canonical order; each accepted form and each refusal of
      `release_targets_csv` and `parse_target` for them; one definition of the order (CR-MDB-068's gate).
- [ ] **§S2.** `stamp` and `check` in temp trees: `crates` with a package version, a workspace version, a
      sub-directory, CRLF; `maven-central` with a project version (a `<parent>` version present and
      ignored), unchanged by `stamp`, refused when not `X.Y.Z`, compared by `check`; every new refusal, one
      stderr line, nothing written.
- [ ] **§S3.** For the target sets `crates`, `maven-central`, `crates:a,maven-central:b`, and all five,
      tests read the rendered workflow: each rehearsal step, each publish job (id, `if:`, `needs:`,
      environment, permissions, checkout and guard first, steps, env names, the auth step's `if:`), the
      check step's targets, the header lines, the pins; the measured plugin property names pinned. Model
      B's byte-equality test still passes.
- [ ] **§S4.** `init` with each new target: the tasks in `release_setup` and the Setup section, once
      each.
- [ ] **§S5.** In sandbox projects, with `gh` replaced by a stub on `PATH` (never the real `gh`): every
      local item ready and missing; every GitHub item ready, missing and `unknown` (no `gh`, a failing
      `gh`, no remote); the registry checklist; the envelope fields and counts; exit 0, 1 and 2; nothing
      written (the tree unchanged byte for byte); only `gh api` with GET.
- [ ] **§S6.** The skill's rows and flow step, `AGENTS.md`, the install guide pinned (proved both ways);
      the raw-runner, registry-key and project-name gates passing; the skill loading in Pi with no
      diagnostics; `pi-package/README.md` regenerated.
- [ ] **Runs.** Every commit leaves the suite green through the client with a real `HOME` and an empty one
      (temp home empty afterwards), beyond RED's own failures; `generator/build.py --check` clean; the
      `AGENTS.md` counts and baselines match.

## Non-goals

- **Several crates or Maven modules under one target** (a workspace publishing many crates); one crate or
  one module per target `dir`.
- **Running the rehearsal of `crates` or `maven-central` on a real runner** before a project uses them: the
  rendered jobs are read and their commands checked, not executed.
- **Writing to GitHub or a registry** from `release-check`.

## Cycle plan

1. **C1 — The targets, the version sources and the rendered jobs (§S1–§S4).** Red-green.
2. **C2 — `modelb-axi release-check` (§S5).** Red-green.
3. **C3 — The skill and the docs (§S6).** Red-green; it re-measures the baselines.
4. **C4 — Verify.**
