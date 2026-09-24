# CR-MDB-038 — Publish `modelb-axi` to PyPI, and replace the stale local install

**Status:** PENDING (filed 2026-09-24, user approval; gap-analysis pending)
**Type:** release-readiness
**Priority:** P1 — in release 1.0.0, wave 2; a maintenance step before the 1.0.0 release
**Depends on:** CR-MDB-037 (its install guide names `uv tool install modelb-axi` as the install
command)
**Labels:** packaging, pypi, installer, release-readiness
**Phase:** Wave 5 (repo queue) · release 1.0.0 wave 2 (Crucible board)
**Design reference:** `pyproject.toml` (hatchling, `force-include` asset map) · `docs/install-guide.md`
(CR-MDB-037 §S1) · `skills-src/git-workflow/SKILL.md` §Releases · PRD D10 (the installer)

## Context — measured 2026-09-24

- The install guide tells a fresh reader to install with `uv tool install modelb-axi` (user ruling,
  CR-MDB-037 C5 VERIFY finding 2). The name `modelb-axi` is **free on PyPI** (both spellings return
  404) and is already `[project].name` in `pyproject.toml`; the version is `0.1.0.dev0`.
- The source repository is private, so PyPI is the only channel a fresh reader can use. The Pi
  package (CR-MDB-029) carries extensions and skills only and cannot carry the Python CLI.
- This machine's installed `modelb-axi` is the July `0.1.0.dev0` claude-code install
  (`~/.local/share/uv/tools/modelb-axi`, `~/.local/share/modelb/install.toml`): stale, and to be
  replaced by the published package as part of this maintenance.

## Scope

### §S1 — The package is publishable
`pyproject.toml` carries the metadata PyPI shows: description, `readme`, license, `requires-python`,
classifiers, and project URLs that do not require access to the private repository. A built wheel
and sdist include every asset root the installer and `init` need (the `force-include` map), and
nothing from `tests/`, `archive/` or `audits/`.

### §S2 — The built artifact works when installed from the artifact, not the checkout
An install of the built wheel into an isolated tool directory runs the installer into a sandbox and
`init` into a sandbox, and both succeed with the assets the wheel carries.

### §S3 — Publishing is a release step, run by the user
Publishing uploads the release's artifacts with a PyPI token held by the user, never stored in the
repository; a TestPyPI upload and install is the rehearsal before the real upload.
`skills-src/git-workflow/SKILL.md` §Releases names the publish step for a Python project, after the
version is set on the release branch.

### §S4 — The stale local install is replaced
At the release's maintenance step, the machine's July install is replaced by the published package
(`uv tool install modelb-axi`, then a re-run of the installer with `--reinstall --target-root ~
--harnesses pi --stacks <chosen>`), and the resulting `install.toml` records `pi`, the stacks and a
`target_root`. This is the user's action on their own home, recorded at close-out.

### §S5 — Retire the global workflow policy in favour of project-level trust (user ruling 2026-09-24)
Once the published package is installed, the workflow allow-list is removed from the user's global
permission config (`~/.pi/agent/extensions/pi-permission-system/config.json`): workflow permissions
come only from each project's rendered policy (CR-MDB-037 §S3), loaded when the project is trusted
(`/trust`, CR-MDB-037 §S4). The installer's global-policy report changes meaning accordingly: a
global config without the workflow tools is the expected state, not a finding. Removing the entries
is the user's action on their own config; Model B never writes it.

## Acceptance criteria

- [ ] `pyproject.toml` carries description, `readme`, license, `requires-python`, classifiers and
      project URLs; a gate asserts each.
- [ ] A wheel and sdist built from the tree contain every `force-include` asset root and no file under
      `tests/`, `archive/` or `audits/` — asserted by listing the built archives.
- [ ] An isolated install of the built wheel runs the installer (`--modelb-home`, `--target-root`
      and `HOME` all sandboxed) to outcome `installed`, and `init` into a sandbox succeeds, rendering
      the Pi agents and policy from the wheel's assets.
- [ ] Once published, the install guide's interim source-copy note is removed, and
      `tests/test_install_guide.py`'s `check_installer_source` stops requiring it (it would
      otherwise be copied into the release notes after it stopped being true).
- [ ] `skills-src/git-workflow/SKILL.md` §Releases names the TestPyPI rehearsal and the PyPI upload
      for a Python project, with the token supplied by the user at upload time.
- [ ] **Close-out (user action, recorded):** `uv tool install modelb-axi` from PyPI succeeds on this
      machine, and the re-run installer's `install.toml` records `harnesses = ["pi"]`, the chosen
      stacks and a `target_root`.

- [ ] The installer's global-policy report no longer reports a global config lacking the workflow
      tools as a problem (it reports whether a project policy will be needed, or is removed — settled
      at this CR's gap-analysis); the install guide says workflow permissions are per project.
- [ ] **Close-out (user action, recorded):** the global config no longer carries the workflow
      allow-list, and a dispatched agent in a trusted, `init`-scaffolded project still runs
      `ctx_shell` and reads `~/.agents/skills/` without a prompt.

## Non-goals

- No credentials in the repository or in any agent brief.
- No publishing from an unreleased version; the upload happens only on the approved release.
