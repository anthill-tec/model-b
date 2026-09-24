# CR-MDB-038 — Make `modelb-axi` publishable on PyPI, and retire the global permission report

**Status:** PENDING (filed 2026-09-24; rewritten at its gap-analysis the same day, user rulings —
earlier text is git history and is not to be consulted for contracts)
**Type:** release-readiness
**Priority:** P1 — in release 1.0.0, wave 2; a maintenance step before the 1.0.0 release
**Depends on:** CR-MDB-037 (merged: the install guide, the per-project permission policy)
**Labels:** packaging, pypi, license, installer, release-readiness
**Phase:** Wave 5 (repo queue) · release 1.0.0 wave 2 (Crucible board)
**Design reference:** `pyproject.toml` (hatchling, `force-include` asset map) · `docs/install-guide.md`
(CR-MDB-037 §S1, its derived-surfaces table) · CR-MDB-037 §S3 (the per-project policy and the global
report this CR removes) · `skills-src/git-workflow/SKILL.md` §Releases

## Context — measured 2026-09-24

- `modelb-axi` is free on PyPI and TestPyPI. A build (`uv build`) already produces a wheel and sdist
  carrying every `force-include` asset root and nothing from `tests/`, `archive/` or `audits/`.
- **Publishing makes the code public:** the wheel and sdist carry all of `modelb_axi/` and every asset
  root, while the repository stays private. There is no `LICENSE` file (user ruling: MIT).
- The metadata has no `readme`, no license and no classifiers, and its description reads "(adaptive
  TUI), per DN-scaffold-packaging" — internal vocabulary. The repository `README.md`'s relative link
  to the guide cannot resolve on PyPI, and any repository URL would 404 for the public.
- The version is written twice: `pyproject.toml` `version` and `modelb_axi/__init__.py`
  `__version__`, so a release bump can leave them disagreeing.
- `skills-src/git-workflow/SKILL.md` §Releases describes a Maven release and names no step for
  building or publishing a Python package.
- Uploading happens at the release, and every CR merges before a release starts. So installing the
  published package, replacing this machine's July `0.1.0.dev0` install, and removing the global
  permission allow-list cannot be acceptance criteria of a CR (user ruling: they become release
  steps).
- With workflow permissions per project (CR-MDB-037 §S3, trusted with `/trust`), the installer's
  global-policy report (`global_permission_policy` in the install envelope) defends an approach the
  user is retiring (user ruling: delete it).

## Scope

### §S1 — Publishable metadata, one version
- `LICENSE` at the repository root: the MIT license, `Copyright (c) 2026 Antony John`.
- `pyproject.toml`: a plain-language description of what the package does; `readme =
  "docs/install-guide.md"` (the PyPI page shows the single-source guide — user ruling); `license =
  "MIT"` with `license-files = ["LICENSE"]`; classifiers for the MIT license, Python 3.11+, and a
  console tool; no project URLs while the repository is private.
- The version has one source: `modelb_axi/__init__.py` `__version__`, read by the build (a dynamic
  version); `pyproject.toml` carries no literal version.
- The sdist includes `LICENSE` and `docs/install-guide.md`; the wheel's metadata carries the license
  and the readme.
- CR-MDB-037's derived-surfaces table in the guide gains the PyPI project page (the whole guide, as
  the package readme).

### §S2 — The built artifacts install and work
A wheel built from the sdist (the path PyPI users take) installs into an isolated tool directory, and
that install runs the installer and `init` into sandboxes successfully with the assets it carries.

### §S3 — The global permission report is removed (user ruling 2026-09-24)
The install envelope no longer carries `global_permission_policy` or
`global_permission_missing_tools`, and the installer no longer reads the global permission config.
The install guide says workflow permissions come from each project's policy, loaded when the project
is trusted. `init`'s per-project policy and trust report are unchanged.

### §S4 — The interim install note becomes always true
The guide's note about installing before the first PyPI release is reworded as the source-copy path
that stays true after publishing ("from a source copy, `uv tool install .`"), so nothing in the guide
needs editing after the upload.

### §S5 — The release ritual publishes, then finishes the maintenance
`skills-src/git-workflow/SKILL.md` §Releases gains the steps for a Python package, project-neutral:

1. On the release branch: set the version in its single source, then build (`uv build`).
2. Rehearse: upload the release candidate to TestPyPI and install it into an isolated tool directory.
3. After `git flow release finish`: upload to PyPI with a token the user supplies at upload time.
4. Post-release, on the maintainer's machine: install from PyPI, replace the previous installation
   (`--reinstall --target-root ~ --harnesses <harnesses> --stacks <stacks>`), remove workflow
   entries from any global permission config in favour of per-project policies, and confirm a
   dispatched agent in a trusted project runs without a permission prompt.

## Acceptance criteria

### §S1
- [ ] `LICENSE` is the MIT license text with `Copyright (c) 2026 Antony John`.
- [ ] The built wheel's metadata carries the description (no `DN-`, `CR-` or `§`), `License-Expression:
      MIT`, the three classifier families, `Requires-Python: >=3.11`, no `Project-URL`, and the
      install guide as its description body — asserted by reading `METADATA` from a wheel built in
      the test.
- [ ] `pyproject.toml` has no literal `version`; the built wheel's version equals
      `modelb_axi.__version__`.
- [ ] The sdist contains `LICENSE` and `docs/install-guide.md`; neither artifact contains any file
      under `tests/`, `archive/` or `audits/`, and the wheel contains every `force-include` root.
- [ ] The guide's derived-surfaces table names the PyPI project page.

### §S2
- [ ] A wheel built from the sdist installs into an isolated `UV_TOOL_DIR`/`UV_TOOL_BIN_DIR`; the
      installed binary's installer run (`--modelb-home`, `--target-root`, `HOME`,
      `PI_CODING_AGENT_DIR` all sandboxed) reaches `installed`, and its `init` into a sandbox renders
      the Pi agents and the project policy.

### §S3
- [ ] No install outcome's envelope carries `global_permission_policy` or
      `global_permission_missing_tools`; a run with a global config present leaves it unread (an
      audit-hook test, as CR-MDB-037's freshness test does).
- [ ] The guide no longer describes a global-policy report, and states that workflow permissions come
      from each project's policy under `/trust`.

### §S4
- [ ] The guide's source-copy note contains no "until", "interim" or "first release" wording, and the
      `check_installer_source` gate is migrated to require the always-true source-copy path.

### §S5
- [ ] `skills-src/git-workflow/SKILL.md` §Releases names the four steps: version in its single source
      and build; TestPyPI rehearsal with an isolated install; PyPI upload with a user-supplied token
      after the release finishes; the post-release maintenance (install from PyPI, replace the prior
      installation, remove global workflow entries, confirm a prompt-free dispatch in a trusted
      project).

### Migration
- [ ] Tests asserting `global_permission_policy`, the interim-note wording, the package metadata or the
      literal version — and tests depending on them without naming them — are migrated and listed by id
      in the RED report. Starting set: `test_project_permission_policy`, `test_install_guide`,
      `test_installer_assets`, `test_pi_agent_definitions`.

## Non-goals

- No upload in this CR, and no credentials in the repository or any brief.
- No change to the per-project policy or the trust report.
- Removing the user's global allow-list, and replacing this machine's install, are release steps
  performed by the user.
