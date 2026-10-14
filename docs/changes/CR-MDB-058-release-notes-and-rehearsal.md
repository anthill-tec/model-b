# CR-MDB-058 — Release notes: `CHANGELOG.md` as a release task, in every project

**Status:** PENDING (filed 2026-10-10; gap analysis 2026-10-14)
**Type:** feature (release workflow, packaging metadata, scaffold, git-workflow skill)
**Priority:** P1 — release 1.0.0, wave 2.
**Depends on:** none (board-authoritative: read `queue`)
**Labels:** release, packaging, scaffold, skills
**Design reference:** `docs/research/release-automation-crucible-procedure.md` § "What Model B adopted
(2026-10-14)"; Crucible #1433 §A1 (reference commit `280326a`); PRD D10; the `git-workflow` skill
§ Releases. The release rehearsal and CI tests are CR-MDB-067.

## Context

- **The GitHub Release body is a bare link.** The release job (`.github/workflows/release.yml`,
  `create-release`) runs `gh release create --generate-notes`, which gives only a changelog link.
- **Model B has nowhere to write release notes.** It has no `CHANGELOG.md`. The `git-workflow` skill's
  release flow says to copy the install guide's marked regions verbatim into hand-written release notes.
- **PyPI shows no links.** `pyproject.toml` has no `[project.urls]`. A test still pins "no Project-URL
  while the repository is private", but `anthill-tec/model-b` is public (measured 2026-10-14).
- **The npm package can't ship a root `CHANGELOG.md`.** `pi-package/package.json` lists no `files`. The
  Pi package lives in `pi-package/`, so a root `CHANGELOG.md` is outside it: npm ships only files under
  the package directory.
- **`init` lays down nothing for releasing.** Its plan writes no `CHANGELOG.md`, and the skill names no
  release-notes step, release-job snippet or packaging entries.

## Scope

### §S1 — Model B's `CHANGELOG.md`

`CHANGELOG.md` at the repository root, in Keep a Changelog 1.1.0 form:

1. a `# Changelog` title;
2. one sentence naming Keep a Changelog 1.1.0 and Semantic Versioning;
3. an `## [Unreleased]` section first;
4. then one `## [X.Y.Z] - YYYY-MM-DD` section per release, newest first:
   - grouped under `### Added`, `### Changed`, `### Deprecated`, `### Removed`, `### Fixed`,
     `### Security`, each only when it has entries;
   - an `### Upgrading` note first whenever an operator must act;
5. compare links at the foot.

The file starts with `## [Unreleased]` and no release section. 1.0.0's section is written at the
release, on the release branch, before `finish`.

### §S2 — The release body is the tag's section

`create-release` takes the tag's `CHANGELOG.md` section as the GitHub Release body
(`gh release create "$TAG" --notes-file <file> --verify-tag`), instead of `--generate-notes`.

- **The body:** the lines after `## [<tag>] - <date>` up to the next `## [` heading or the compare-link
  block, trimmed.
- **When the job fails, before creating a release:** the section is missing, or it is empty.
- **Unchanged:** the existing guard (a release that exists is not re-created) and the tag ==
  `__version__` check.

### §S3 — PyPI links

`pyproject.toml` gains `[project.urls]` with the PEP 753 well-known labels:

- `Changelog` = `https://github.com/anthill-tec/model-b/blob/master/CHANGELOG.md` (the released copy);
- `Release Notes` = `https://github.com/anthill-tec/model-b/releases`.

The built wheel's metadata carries both as `Project-URL`. The test pin "no Project-URL while the
repository is private" is replaced by one pinning exactly these two. `Home-page` stays absent.

### §S4 — The npm package ships `CHANGELOG.md`

`pi-package/package.json` gains `files`: `["extensions", "CHANGELOG.md"]`. npm adds `package.json`
and `README.md` on its own.

`pi-package/CHANGELOG.md` is a generated, byte-identical copy of the root `CHANGELOG.md`:

- `generator/build.py` writes it on every invocation, as it writes `pi-package/README.md`;
- `--check` fails on drift;
- `--list` prints its path.

### §S5 — `init` writes a `CHANGELOG.md` skeleton

`init` adds `CHANGELOG.md` to the root project's plan, for every stack. The skeleton is §S1's form
with an empty `## [Unreleased]` section and no release sections or compare links. Sub-projects get
none.

### §S6 — The `git-workflow` skill's release flow

`skills-src/git-workflow/SKILL.md` § Releases:

- **The copy step is retired.** "Install text from its single source … copy those marked regions
  verbatim into the release notes" goes. Release notes link to the install guide instead; the marked
  regions still feed generated surfaces such as a package README.
- **The documentation-review step stays.**
- **A release-notes step**, on the release branch before `finish`, says to:
  - write the release's `CHANGELOG.md` section: move `[Unreleased]` under `## [X.Y.Z] - YYYY-MM-DD`,
    or write the section from the release's CRs (`history`, `landings`);
  - add an `### Upgrading` note when an operator must act;
  - update the compare links;
  - commit.
- **A release-job snippet:** a stack-neutral create-release step taking the tag's section as
  `--notes-file`, failing on a missing or empty section.
- **The packaging entries per stack:**
  - python: `[project.urls]` `Changelog` and `Release Notes`;
  - bun/npm: `CHANGELOG.md` in `package.json` `files`, plus a copy into the package directory when
    the package is not at the repository root;
  - other stacks: the release body only.

### §S7 — The docs and gates this change moves

- **`docs/research/release-automation-crucible-procedure.md`:** "The shape" names `--notes-file` from
  `CHANGELOG.md`.
- **`tests/test_package_publishing.py`:** the private-repository URL pin moves to §S3's pin.
- **The `plan_files` and scaffold-emission pins** that list `init`'s files gain `CHANGELOG.md`.
- **The `git-workflow` skill gates:** any pin on the retired copy step moves.
- **`generator/build.py` targets and `--list` pins** gain `pi-package/CHANGELOG.md`.

## Acceptance criteria

- [ ] **§S1.**
      - `CHANGELOG.md` exists and holds §S1's form: title, sentence, `## [Unreleased]` first.
      - A checker pins the form: every `## [` heading after `[Unreleased]` reads
        `## [X.Y.Z] - YYYY-MM-DD`, newest first; the group headings come only from the six names
        and `### Upgrading`; `### Upgrading` comes first in its section when present.
      - The checker is proved in both directions on sample text and passes on the real file.
- [ ] **§S2.**
      - `create-release` in `release.yml` passes `--notes-file` and no longer `--generate-notes`.
      - The section extraction is a function that a test drives on sample changelogs:
        - a middle section;
        - the last section before the compare links;
        - a missing tag (fails);
        - an empty section (fails).
      - The workflow calls that same function, not a copy.
- [ ] **§S3.** The wheel built from the sdist (`test_package_publishing`'s real build) carries exactly
      the two `Project-URL` entries, and no `Home-page`.
- [ ] **§S4.**
      - `package.json` `files` is `["extensions", "CHANGELOG.md"]`.
      - `pi-package/CHANGELOG.md` is byte-identical to the root file.
      - `build.py --check` fails when they differ, proved by mutating a temp copy, and `--list`
        names the path.
      - `npm pack --dry-run` in `pi-package/` lists `CHANGELOG.md`, `README.md`, `package.json` and
        the extensions, and nothing else (skipped when `npm` is absent).
- [ ] **§S5.**
      - `init` (solo and multi; python and rust) writes `CHANGELOG.md` at the root, with an empty
        `## [Unreleased]`, passing §S1's checker.
      - `--dry-run` lists it.
      - Sub-projects get none.

      Each is proved through the real `run_init` in a sandbox.
- [ ] **§S6.**
      - The skill names the release-notes step, the release-job snippet (`--notes-file`) and the
        packaging entries per stack.
      - It no longer tells the reader to copy the install guide's marked regions into the release
        notes, and it keeps the documentation-review step.

      Each is pinned by a check proved in both directions. The skill still loads in Pi's own loader
      with no diagnostics. The raw-runner guard stays clean.
- [ ] **§S7.**
      - The research doc names `--notes-file`.
      - Every moved pin is migrated.
      - The suite is green through the client with a real `HOME` and with an empty one, and the
        temp home is empty afterwards.
      - `generator/build.py --check` is clean.
      - The `AGENTS.md` baselines match the measured counts.

## Non-goals

- **The rehearsal and CI** are CR-MDB-067: the dev-version stamp, rehearsal on every release or hotfix
  push, and the CI test workflow.
- **1.0.0's own release notes** are written at the release, on the release branch.
- **A Crucible verb drafting the notes from the board** is requested from Crucible; it is not built
  here.
- **The version source** stays the fixed `modelb_axi.__version__`; hatch-vcs is declined (see the
  research doc).
- **Release workflows in scaffolded projects.** `init` writes no workflow file; a project's own
  publish jobs are its own.
- **`migrate` (CR-MDB-055)** lays the skeleton down for existing projects when it lands.

## Cycle plan

1. **C1 — Model B's `CHANGELOG.md`, its checker, and the release body (§S1, §S2).** Red-green.
2. **C2 — PyPI links and the npm package (§S3, §S4).** Red-green.
3. **C3 — `init`'s skeleton, the skill's release flow and the docs (§S5–§S7).** Red-green; it
   re-measures the baselines.
4. **C4 — VERIFY.**

**After merge:** the `git-workflow` skill changes, so the user reinstalls and redeploys.
