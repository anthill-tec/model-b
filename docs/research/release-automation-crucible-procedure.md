# Release automation — how Crucible publishes, and what Model B needs (reference, 2026-09-24)

Source: Crucible Mainline, Sandesh #1388 (reply to #1387), taken from Crucible's `release.yml` and
`RELEASING.md` as of 2026-09-24. No token values appear here or anywhere in the repository.

## The shape

A git-flow release pushes the tag from a workstation. A GitHub Actions workflow, `release.yml`, then:

1. **`create-release`** — `gh release create "$TAG" --generate-notes`, guarded by `gh release view` so a
   re-run does not fail, with `GH_TOKEN: ${{ secrets.RELEASE_PAT }}`.
2. **`publish-pypi`** and **`publish-npm`** — gated on `github.event_name == 'release'`.

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
  environments `pypi`, `testpypi`, `npm` (add required reviewers once public); pending Trusted
  Publishers on pypi.org and test.pypi.org (owner `anthill-tec`, repository `model-b`, workflow
  `release.yml`); `NPM_TOKEN` for the first npm publish, then the npm trusted publisher, then delete
  `NPM_TOKEN`.

### Setup status (user, 2026-09-24)

- [x] `anthill-tec/model-b` public (verified: `visibility: public`, license detected as MIT)
- [x] Pending Trusted Publishers for `modelb-axi` on pypi.org and test.pypi.org
- [x] npm account in the `anthill-tec` organisation
- [ ] Repository secret `RELEASE_PAT`
- [ ] Environments `pypi`, `testpypi`, `npm` (required reviewers now available)
- [ ] One-time `NPM_TOKEN` for the first publish of `@anthill-tec/modelb-pi`, then the npm trusted
      publisher, then delete the token

## What this means for Model B

Model B has **no** `release.yml`. CR-MDB-038 and CR-MDB-029 wrote the release steps as **manual**
uploads with credentials the user supplies at publish time. Adopting Crucible's shape replaces those
steps with a workflow (`create-release` → `publish-pypi` via Trusted Publishing, `publish-npm` via a
one-time `NPM_TOKEN` then Trusted Publishing), plus the `RELEASE_PAT` repository secret, the three
environments, and the pending PyPI publisher — a CR of its own.
