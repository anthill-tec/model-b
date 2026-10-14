# CR-MDB-058 — Release notes: `CHANGELOG.md` as a release task, in every project

**Status:** PENDING (filed 2026-10-10; gap analysis and pre-review 2026-10-14) — **locked**
**Type:** feature (release workflow, packaging metadata, scaffold, git-workflow skill, install guide)
**Priority:** P1 — release 1.0.0, wave 2.
**Depends on:** none (board-authoritative: read `queue`)
**Labels:** release, packaging, scaffold, skills
**Design reference:** `docs/research/release-automation-crucible-procedure.md` § "What Model B adopted
(2026-10-14)"; Crucible #1433 §A1 (reference commit `280326a`); PRD D10; the `git-workflow` skill
§ Releases. The release rehearsal and CI tests are CR-MDB-067, which lands before 1.0.0's release starts.

## Context

- **The GitHub Release body is a bare link.** The release job (`.github/workflows/release.yml`,
  `create-release`) runs `gh release create --generate-notes`, which gives only a changelog link.
- **There is nowhere to write release notes.** Model B has no `CHANGELOG.md`.
  - The `git-workflow` skill's release flow says to copy the install guide's marked regions verbatim
    into hand-written release notes.
  - The install guide's `## Marked regions` says the regions are copied into the release notes at
    release time.
- **PyPI shows no links.** `pyproject.toml` has no `[project.urls]`. A test still pins "no Project-URL
  while the repository is private", but `anthill-tec/model-b` is public (measured 2026-10-14).
- **The npm package can't ship the changelog.** The Pi package is `pi-package/`, and a root
  `CHANGELOG.md` sits outside it, so npm cannot ship it. `pi-package/package.json` has no `files`
  allow-list, so everything in the folder ships.
- **`init` lays down nothing for releasing.** Its plan writes no `CHANGELOG.md`, and the skill names no
  release-notes step, release-job snippet or packaging entries.

## Scope

### §S1 — Model B's `CHANGELOG.md`

`CHANGELOG.md` at the repository root, in Keep a Changelog 1.1.0 form:

1. a `# Changelog` title;
2. one sentence linking `https://keepachangelog.com/en/1.1.0/` and
   `https://semver.org/spec/v2.0.0.html`;
3. an `## [Unreleased]` section, the first `##` heading;
4. one `## [X.Y.Z] - YYYY-MM-DD` section per release, newest first:
   - grouped under `### Added`, `### Changed`, `### Deprecated`, `### Removed`, `### Fixed` and
     `### Security`;
   - an `### Upgrading` note first whenever an operator must act;
   - no group heading without an entry;
5. compare links at the foot, one per section, in `[label]: url` form. They are added at the first
   release: with no tag yet, there is no compare base.

The file starts with a title, the sentence, and an `## [Unreleased]` section with no release section
and no compare link. 1.0.0's section is written at the release, on the release branch, before
`finish`.

**The form checker** lives once in `tests/_helpers.py`, since §S1 and §S5 both use it. It checks:

- the two URLs;
- `## [Unreleased]` as the first `##` heading;
- every later `##` heading reading `## [X.Y.Z] - YYYY-MM-DD`, versions descending;
- group headings drawn only from the six names and `### Upgrading`, with `### Upgrading` first when
  present, and none empty.

### §S2 — The release body is the tag's section

**`.github/scripts/changelog_section.py`** is a repo-only script, never in the wheel or the sdist. It
is stdlib only and uses no syntax newer than Python 3.12, the hosted runner's default.

- **It is called as** `python3 .github/scripts/changelog_section.py <changelog> <tag>`.
- **It prints the section's body:** the lines after the heading whose bracketed label equals the tag
  exactly, up to the next `## ` heading, the first line matching `^\[[^\]]+\]: `, or the end of the
  file, trimmed. The match is literal: `1.0.1` never matches `1.0.10`, and `1.0.0` never matches
  `1.0.0-rc1`. A SemVer prerelease label such as `1.0.0-rc1` is matched like any other.
- **It exits 1, naming the tag on stderr, when:**
  - no section has that label;
  - the body is empty, meaning nothing but whitespace and `###` headings.

**`create-release`** runs it every time, before the existing "release already exists" guard, writing
the body to a file. It then runs `gh release create "$TAG" --notes-file <that file> --verify-tag`
instead of `--generate-notes`. An existing release's body is not rewritten. The tag == `__version__`
check is unchanged.

### §S3 — PyPI links

`pyproject.toml` gains `[project.urls]` with the PEP 753 well-known labels:

- `Changelog` = `https://github.com/anthill-tec/model-b/blob/master/CHANGELOG.md`;
- `Release Notes` = `https://github.com/anthill-tec/model-b/releases`.

`master` is deliberate: it holds the released copy, while the default branch is `develop`. The built
wheel carries exactly these two `Project-URL` lines, and `Home-page` stays absent.

### §S4 — The npm package ships `CHANGELOG.md`, copied at publish time

- `pi-package/package.json` gains `files`: `["extensions", "CHANGELOG.md"]`. npm adds `package.json`
  and `README.md` on its own.
- `publish-npm` copies the root `CHANGELOG.md` into `pi-package/` before `npm publish`.
- Nothing is committed under `pi-package/` for it: `.gitignore` gains `pi-package/CHANGELOG.md`.

### §S5 — `init` writes a `CHANGELOG.md` skeleton

- **Where:** `init` adds `CHANGELOG.md` to the root project's plan, for every stack, solo and multi,
  standalone and monorepo.
- **What:** the skeleton is §S1's starting form.
- **Sub-projects** (`--repo-shape monorepo:<subs>`) get none.
- **An existing `CHANGELOG.md`** at the root is never overwritten. It is left as it is and reported as
  unmanaged, as `.envrc` is.

### §S6 — The `git-workflow` skill's release flow

`skills-src/git-workflow/SKILL.md` § Releases:

- **The copy step is retired.** "Install text from its single source … copy those marked regions
  verbatim into the release notes" goes. Release notes link to the install guide instead; the marked
  regions still feed generated surfaces such as a package README.
- **The documentation-review step stays.**
- **A release-notes step**, on the release branch before `finish`, says to:
  - write the release's `CHANGELOG.md` section: move `[Unreleased]` under `## [X.Y.Z] - YYYY-MM-DD`,
    or write it from the release's CRs (the Crucible client's `history` and `landings`);
  - add an `### Upgrading` note first when an operator must act;
  - update the compare links;
  - commit.
- **A release-job snippet:** a stack-neutral create-release step that extracts the tag's section
  (literal match, failing on a missing or empty one) and passes it as `--notes-file`.
- **The packaging entries per stack:**
  - `python`: `[project.urls]` `Changelog` and `Release Notes`;
  - `bun`: `CHANGELOG.md` in `package.json` `files`, copied into the package directory at publish
    time when the package is not at the repository root;
  - `arduino`, `quarkus`, `java`, `rust`: the release body only.
- **Text rules for the section** (gates in `tests/test_install_guide.py`):
  - it names no project (no `modelb`, `model b`, `model-b`), so examples use placeholders;
  - new text keeps the first-occurrence order of the existing python and Pi release steps;
  - no runner invocation appears in a code span;
  - the release-step phrase gate (`RELEASE_STEP_PHRASES`, `check_release_steps`) is migrated to the
    new steps, never duplicated.

### §S7 — The install guide, the docs, and the gates this change moves

- **`docs/install-guide.md` `## Marked regions`** no longer says the regions are copied into the
  release notes. It says release notes link to the guide, and that the regions feed the generated
  package README.
  - The edit stays outside every marked region, so `pi-package/README.md` does not change.
  - `check_pypi_surface`'s sentence about the PyPI page stays.
- **`docs/research/release-automation-crucible-procedure.md`:**
  - "The shape" keeps its sourced record of Crucible, with a dated note that Model B's `create-release`
    now uses `--notes-file`;
  - the stale "Model B has **no** `release.yml`" paragraph is corrected.
- **Gates that move, per cycle:**

  | Cycle | Gates |
  |---|---|
  | **C1** | the §S1 checker (new) and §S2's script tests (new) |
  | **C2** | `tests/test_package_publishing.py`: the private-repository URL pin, renamed and moved to §S3's two lines |
  | **C3** | `tests/test_project_registry_schema.py` `test_the_emitted_file_set_is_todays` (all three `InitAgainstToday` shapes); `tests/test_install_guide.py`: `RELEASE_STEP_PHRASES` / `check_release_steps`, the module docstring's item (F), and the `## Marked regions` wording; the `AGENTS.md` baselines |

## Acceptance criteria

- [ ] **§S1.** `CHANGELOG.md` holds §S1's starting form. The `tests/_helpers.py` checker is proved in
      both directions on sample text (each rule broken once) and passes on the real file.
- [ ] **§S2 — the script.** Loaded by path in a test, it gives the expected body or exit 1 on sample
      changelogs:
      - a middle section;
      - the last section before the compare links;
      - the last section at end of file with no links;
      - `1.0.1` beside `1.0.10`;
      - `1.0.0` beside `1.0.0-rc1`;
      - a tag `1.0.0-rc1`;
      - a missing tag (exit 1);
      - an empty section, and one holding only `###` headings (exit 1).

      It parses under `ast.parse(..., feature_version=(3, 12))`, and it is in neither the sdist nor
      the wheel.
- [ ] **§S2 — the workflow.** A test reads `release.yml`'s `create-release` step as text and asserts:
      - one command line running `.github/scripts/changelog_section.py` on `CHANGELOG.md` and
        `"$TAG"` into a file, placed before the guard;
      - `gh release create "$TAG" --notes-file <that file> --verify-tag`;
      - no `--generate-notes`.

      The test executes that extracted command line in a temp dir against a sample `CHANGELOG.md`
      with `TAG` set, and compares the file it writes to the expected body.
- [ ] **§S3.** The wheel built from the sdist carries exactly
      `Project-URL: Changelog, https://github.com/anthill-tec/model-b/blob/master/CHANGELOG.md` and
      `Project-URL: Release Notes, https://github.com/anthill-tec/model-b/releases`, and no
      `Home-page`. The test that pinned "no Project-URL" is renamed.
- [ ] **§S4.**
      - `package.json` `files` is `["extensions", "CHANGELOG.md"]`.
      - `release.yml`'s `publish-npm` copies the root `CHANGELOG.md` into `pi-package/` before
        `npm publish` (read as text).
      - `.gitignore` lists `pi-package/CHANGELOG.md`.
      - No `pi-package/CHANGELOG.md` is tracked.
- [ ] **§S5.** Each case is proved through the real `run_init` in a sandbox:
      - **Solo, `multi:2` and `monorepo:a,b`:** `CHANGELOG.md` appears once in the envelope's
        `planned`, and in `emitted` when not a dry run. It passes the §S1 checker and is never
        written as `<sub>/CHANGELOG.md`.
      - **A target holding a `CHANGELOG.md`:** the file is unchanged byte for byte and reported
        `unmanaged`.
- [ ] **§S6.**
      - **The skill names:** the release-notes step and its four parts, the release-job snippet
        (`--notes-file`, literal match, failing on missing or empty), and the packaging entries for
        each of the six stacks.
      - **It no longer:** says to copy the marked regions into the release notes.
      - **It keeps:** the documentation-review step.
      - **Proof:** each point is pinned by a check proved in both directions; the migrated
        `check_release_steps` and the project-name and order gates pass; the skill loads in Pi's own
        loader with no diagnostics; and the raw-runner guard stays clean.
- [ ] **§S7.**
      - The guide's `## Marked regions` no longer says the regions are copied into release notes, and
        `pi-package/README.md` is unchanged.
      - The research doc carries the dated note and the corrected paragraph.
      - Every gate in §S7's table moves in its cycle.
      - Every cycle's commit leaves the suite green through the client with a real `HOME` and with an
        empty one, beyond RED's own failures, and the temp home is empty afterwards.
      - `generator/build.py --check` is clean, and the `AGENTS.md` baselines match the measured counts.

## Non-goals

- **CR-MDB-067** covers the rehearsal and CI: the dev-version stamp, rehearsal on every release or
  hotfix push (which also runs §S2's script on the branch version and §S4's copy with
  `npm publish --dry-run`), and the CI test workflow.
- **1.0.0's own release notes** are written at the release, on the release branch.
- **A Crucible verb drafting the notes from the board** is requested from Crucible (#1449); it is not
  built here.
- **The version source** stays the fixed `modelb_axi.__version__`; hatch-vcs is declined (see the
  research doc).
- **Release workflows in scaffolded projects.** `init` writes no workflow file; a project's publish
  jobs are its own.
- **`migrate` (CR-MDB-055)** lays the skeleton down for existing projects when it lands.
- **Release history already on GitHub.** An existing release's body is not rewritten.

## Cycle plan

1. **C1 — Model B's `CHANGELOG.md`, its checker, and the release body (§S1, §S2).** Red-green.
2. **C2 — PyPI links and the npm package (§S3, §S4).** Red-green.
3. **C3 — `init`'s skeleton, the skill's release flow, the guide and the docs (§S5–§S7).** Red-green;
   it re-measures the baselines.
4. **C4 — VERIFY.**

**After merge:** the `git-workflow` skill changes, so the user reinstalls and redeploys.
