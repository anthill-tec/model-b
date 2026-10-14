# Release automation — how Crucible publishes, and what Model B needs (reference, 2026-09-24)

Source: Crucible Mainline, Sandesh #1388 (reply to #1387), taken from Crucible's `release.yml` and
`RELEASING.md` as of 2026-09-24. No token values appear here or anywhere in the repository.

## The shape

A git-flow release pushes the tag from a workstation. A GitHub Actions workflow, `release.yml`, then:

1. **`create-release`** — `gh release create "$TAG" --generate-notes`, guarded by `gh release view` so a
   re-run does not fail, with `GH_TOKEN: ${{ secrets.RELEASE_PAT }}`.
2. **`publish-pypi`** and **`publish-npm`** — gated on `github.event_name == 'release'`.

**Note (2026-10-14, CR-MDB-058):** Model B's `create-release` now passes the tag's `CHANGELOG.md` section
with `--notes-file` instead of `--generate-notes`; the record above is Crucible's, as sourced.

**Why `RELEASE_PAT` and not the default `GITHUB_TOKEN`:** a Release created with the default token does
not fire `on: release` workflows, so the publish jobs never run — silently, with no error. That is the
secret's only purpose; it is not used for tagging, protected-branch pushes or publishing.

## `RELEASE_PAT`

- **Fine-grained** PAT; **resource owner `anthill-tec`** (not a personal account); repository access
  **only the release repository**; permission **Contents: read & write**.
- Stored as a **repository secret** named `RELEASE_PAT` (not an org secret, not in an environment).
- If `anthill-tec` requires approval for fine-grained PATs, the token stays pending and
  `gh release create` returns 403 until an org owner approves it.

## Workflow permissions

Default `permissions: contents: read`; each publish job raises its own to `id-token: write`.

## PyPI — OIDC Trusted Publishing (no PyPI token anywhere)

- Before the first release, register a **pending** Trusted Publisher on pypi.org (and test.pypi.org for a
  rehearsal): project name, owner `anthill-tec`, repository, workflow `release.yml`, environment `pypi`
  (`testpypi`). It becomes a normal publisher on the first upload.
- Step: `pypa/gh-action-pypi-publish@release/v1`.

## npm — OIDC, but the first publish needs a token

npm has no pending publisher, so the **first** publish of a new package needs a token:

- **Granular** token, scoped to the **`@anthill-tec` scope, Read and write**; **Organizations: No
  access**; **Allowed IP ranges: empty**; **short expiry**; **Bypass two-factor authentication:
  checked** (unchecked, CI fails with `EOTP` even when the account is set to "authorization only").
- Stored as the repository secret `NPM_TOKEN` for that first publish only.
- After it succeeds: add the trusted publisher on npmjs.com (repository, `release.yml`, environment
  `npm`); switch the step to token-free `npm publish --provenance --access public` (npm ≥ 11.5.1); set
  the package's publishing access to "Require 2FA and disallow bypass-2fa tokens"; **delete
  `NPM_TOKEN`**.

## Environments

`pypi`, `testpypi` and `npm` under Settings → Environments; their names must match `release.yml` and
the trusted-publisher configurations exactly.

## Traps Crucible hit

1. **npm 2FA** — see the bypass checkbox above; it cost a failed release-day publish.
2. **Private repositories** — on a free-plan private repository, environment protection rules
   (required reviewers) do not exist, so there is no human gate; and `npm publish --provenance` did
   not work until the repository was public. Model B's repositories are private: check both before
   release day, or plan the first release without provenance.
3. **The default-token trap** — the Release appears and nothing publishes.

## What Model B adopted (2026-09-24, user rulings)

- **Automate like Crucible, no CR:** `.github/workflows/release.yml` runs `create-release`
  (`RELEASE_PAT`), `publish-pypi` (Trusted Publishing), `publish-npm` (provenance; the one-time
  `NPM_TOKEN` for the first publish) and a manual `rehearse-testpypi`, inside the existing git-flow
  release and no-mistakes gate. `create-release` refuses a tag that differs from
  `modelb_axi.__version__`. Every action is pinned to a commit SHA.
- **`anthill-tec/model-b` becomes public** under the MIT license (CR-MDB-038), so `--provenance` and
  environment reviewers are available.
- **Maintainer's one-time setup** (none of it is automatable from here): the `RELEASE_PAT` secret;
  environments `pypi`, `testpypi`, `npm` (add required reviewers to `pypi` and `npm` once public;
  `testpypi` carries none); pending Trusted
  Publishers on pypi.org and test.pypi.org (owner `anthill-tec`, repository `model-b`, workflow
  `release.yml`); `NPM_TOKEN` for the first npm publish, then the npm trusted publisher, then delete
  `NPM_TOKEN`.
- **Note (2026-10-14, CR-MDB-067):** the manual `rehearse-testpypi` became the `rehearse` job,
  run on every release or hotfix push.
- **Note (superseded by CR-MDB-070, 2026-10-14):** `create-release` moved to the `master` push:
  it releases the `X.Y.Z` tag at `HEAD` after the test job, and the tag-push trigger is dropped.

### Setup status (user, 2026-09-24)

- [x] `anthill-tec/model-b` public (verified: `visibility: public`, license detected as MIT)
- [x] Pending Trusted Publishers for `modelb-axi` on pypi.org and test.pypi.org (re-checked by the
      user 2026-10-14: owner `anthill-tec`, repository `model-b`, workflow `release.yml`,
      environment `pypi` / `testpypi`)
- [x] npm account in the `anthill-tec` organisation
- [x] Repository secret `RELEASE_PAT` (verified by name, 2026-09-24). User ruling: one fine-grained
      token owned by `antojk` (owner of `anthill-tec`) is reused across the anthill-tec projects;
      its **Repository access must include `model-b`** (Contents read/write), or `create-release`
      fails at the first tag. Expires 2027-09-25 (user, 2026-10-14)
- [x] Environments `pypi`, `testpypi`, `npm` (verified 2026-10-14): `pypi` and `npm` admit tags
      `*.*.*` only, required reviewer `antojk`, self-review allowed
- [x] The `testpypi` environment admits `release/**` and `hotfix/**` and carries no required
      reviewers (CR-MDB-067; verified 2026-10-14)
- [x] One-time `NPM_TOKEN` (granular, `@anthill-tec` scope, read/write, 2FA bypass) stored as a
      repository secret (verified by name, 2026-09-24). Expires 2026-10-24 (user, 2026-10-14):
      renew it, same scope and 2FA bypass, and update the repository secret, if it expires before
      the first npm publish
- [ ] After the first publish: the npm trusted publisher (`model-b`, `release.yml`, environment
      `npm`), "require 2FA and disallow tokens", then delete `NPM_TOKEN` from npm and the repository

## What Model B adopted (2026-10-14, user rulings at CR-MDB-058's gap analysis)

Crucible #1433 §A (release notes as a release task; every release-branch push is the rehearsal),
adopted for 1.0.0 and split by the 13-point cap:

- **Release notes (CR-MDB-058).** `CHANGELOG.md` at the repository root, in Keep a Changelog 1.1.0
  form, written on the release branch before `finish`. The tag's section is the GitHub Release body
  (`gh release create --notes-file`, replacing `--generate-notes`). PyPI links it through
  `[project.urls]` `Changelog` and `Release Notes`; the npm package ships it through `package.json`
  `files`. The repository is public, so the earlier "no project URL while the repository is private"
  rule no longer holds.
- **Templates (CR-MDB-058).** `init` writes a `CHANGELOG.md` skeleton for every project. The
  `git-workflow` skill's release flow carries the release step, the release-job snippet and each
  stack's packaging entries; no workflow file is written into a project.
- **Install text in the release notes is retired.** Release notes link to the install guide instead
  of copying its marked regions; the regions still feed the generated package README, and PyPI shows
  the whole guide. The documentation-review step stays.
- **The version stays a fixed `__version__`.** hatch-vcs was measured and declined: it is a
  Python-only mechanism, `release-branch-semver` numbers a rehearsal on `release/1.0.0` as
  `0.1.0.devN` (no tags) or `0.10.0.devN` (it treats a branch as a release branch only when it matches
  the last tag's major.minor), its `+g<sha>` local part is refused by PyPI and TestPyPI, and a
  shallow CI clone versions wrongly. The stack-neutral rule is: a tag `X.Y.Z` builds exactly
  `X.Y.Z`; a push to `release/X.Y.Z` or `hotfix/X.Y.Z` builds `X.Y.Z` with a dev marker and the CI
  run number, written in each stack's own form (PEP 440 `X.Y.Z.devN`, npm `X.Y.Z-dev.N`).
- **Rehearsal on every release or hotfix push, and CI on develop (CR-MDB-067).** Each such push
  rehearses with the version stamped in CI's own checkout (TestPyPI upload and `npm publish
  --dry-run`), so a manual dispatch only re-runs one. A CI test workflow runs the suite on develop,
  release and hotfix pushes and pull requests; CI runs outside any agent session (DN-multi-harness-
  deploy-model §D21), so it may run the suite directly.
- **Drafting the notes from the board is Crucible's.** A client verb that drafts a release's
  Keep a Changelog section from the CRs it landed is requested from Crucible (it owns its clients);
  until it ships, the section is written from `history` and `landings`.

## What Model B adopted (2026-10-14, user rulings at CR-MDB-067's gap analysis)

- **A missing or empty notes section fails the rehearsal**, exactly as it fails `create-release`.
  The release flow therefore writes the version bump and the `CHANGELOG.md` section before the
  release branch is first pushed (`git flow release publish`); every later push re-rehearses.
- **The version stamp is a repository script** (`.github/scripts/stamp_version.py`), tested like
  `changelog_section.py`. It refuses a ref that is not `release/X.Y.Z` or `hotfix/X.Y.Z`, and refuses
  when the committed `__version__` or `pi-package/package.json` version is not `X.Y.Z`, so a forgotten
  bump fails on the first push instead of at the tag.
- **The skill carries the CI rule in plain words.** The raw-runner guard keeps test-runner commands
  out of `skills-src/` and `AGENTS.md`; the concrete CI workflow lives only in Model B's own
  `.github/workflows/ci.yml` (superseded by CR-MDB-070, 2026-10-14: the tests are a job of
  `release.yml`). No per-stack CI snippet.
- **The skill's Python and npm release steps describe the CI path only:** the rehearsal is the
  release-branch push (TestPyPI upload, `npm publish --dry-run`, the notes check) and publishing is
  the tag's release jobs through Trusted Publishing (a one-time token for a new npm package). The
  manual install from TestPyPI is dropped: the suite proves a built wheel installs in isolation, and
  the upload proves the index accepts it.
- **Release and CI workflow templates for every stack are CR-MDB-068**, in release 1.0.0 after
  CR-MDB-067. It reverses CR-MDB-058's "no workflow file is written into a project": `init` renders a
  CI and a release workflow per stack (PyPI, npm, crates.io, Maven Central, the Arduino Library
  Manager), Model B renders its own from the templates, and a read-only check reports what a project
  lacks for a release or hotfix run.
- **Setup note:** the `testpypi` environment carries no required reviewers, or every release push
  waits for an approval before it rehearses.

## What Model B adopted (2026-10-14, user rulings at CR-MDB-070's gap analysis)

Crucible's `release.yml` shape (CR-CRU-062 "the gate is the dependency graph"), adopted after CR-MDB-067's
separate `ci.yml` ran on every `develop` push and pull request and gated no publish:

- **One workflow.** The tests are a job inside `release.yml` with no event condition, so they exist in
  every run, and every publish job — the TestPyPI rehearsal included — `needs:` them. `needs:` orders
  jobs only within one run, so a separate CI workflow cannot gate a publish. `ci.yml` is retired.
- **CI runs only on release candidates and production:** pushes to `release/**`, `hotfix/**` and
  `master`, and the published release. Not on `develop`, not on pull requests: a red `develop` is caught
  by the release branch's first push, before anything publishes.
- **The release is created from the `master` push** for the `X.Y.Z` tag at `HEAD` (none → nothing to
  release), so one run tests and releases; the tag-push trigger is dropped.
- **The registry publishes guard their ref:** a bare `X.Y.Z` tag whose commit is an ancestor of
  `origin/master`, beside `needs:` on the tests.
- **Per-stack workflow templates (CR-MDB-068) take this shape.**

## Release workflow templates (user rulings, 2026-10-14, at CR-MDB-068's gap analysis)

- **A project's publish targets are a registry key, asked at `init`** (`RELEASE_TARGETS`), not
  inferred from its stacks: a stack decides the test job; the targets decide the rehearsal and publish
  jobs. An app, a service or firmware may publish to no registry, so no target means tests and
  `create-release` only.
- **A verb re-renders the workflow in an existing project,** as `modelb-axi agents` re-renders the
  agent definitions, under the same ownership rules; `init` and `migrate` (CR-MDB-055) call the same
  renderer, and Model B renders its own in 1.0.0.
- **Version stamping and the notes extraction are shipped scripts,** stdlib Python written into each
  project and owned by hash, not inline shell: tested once, in Model B, whose own scripts become them.
- **The split:** CR-MDB-068 carries the key, the templates and renderer, `init` and the verb, the
  scripts, a test job per stack, the targets `pypi`, `npm` and `github-assets`, and Model B rendering
  its own; CR-MDB-071 carries the `crates` and `maven-central` targets and the release-readiness check.
  Both are in 1.0.0.
- **Measured at gap analysis:** the Arduino stack is firmware, which ships built files, not through the
  Arduino Library Manager (libraries only); crates.io has trusted publishing
  (`rust-lang/crates-io-auth-action`) but a crate's first publish needs an API token; Maven Central has
  no OIDC (a Portal user token and GPG signing; the plugin can validate a deployment and drop it, a
  rehearsal); npm caps write tokens at 90 days and removes direct publishing with bypass-2FA tokens in
  January 2027, so trusted publishing is the durable path.

## A test-hygiene CR in every release (user ruling, 2026-10-14)

Every release carries a test-hygiene CR, sequenced last in the release's final wave, so the suite is
swept before the release steps begin: analyzer findings in the test tree, flaky, slow or network-bound
tests, skip reasons, duplicated helpers, and the hygiene notes its CRs deferred. For 1.0.0 that CR is
CR-MDB-052 (moved from 1.1.0). The rule reaches the skills through CR-MDB-059.

## What this means for Model B

Model B runs Crucible's shape in its own `release.yml` since 2026-09-24: `create-release` →
`publish-pypi` via Trusted Publishing, `publish-npm` via a one-time `NPM_TOKEN` then Trusted
Publishing, with the `RELEASE_PAT` repository secret and the three environments. It replaced the
**manual** uploads CR-MDB-038 and CR-MDB-029 wrote, with credentials the user supplies at publish
time. Since CR-MDB-058 its release body is the tag's `CHANGELOG.md` section (`--notes-file`).
