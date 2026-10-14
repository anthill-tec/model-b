# CR-MDB-071 — Release targets crates.io and Maven Central, and the release-readiness check

**Status:** PENDING — spec (gap analysis and pre-review 2026-10-15).
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
  `publish-<target>.yml`, `setup-<target>.yml`) filled by `@@NAME@@` placeholders; actions are pinned in
  `workflows.ACTION_PINS`.
- **`stamp_version.py`** (`stamp`, `check`) reads `pyproject.toml` and `package.json`. Model B's
  `.github/scripts/stamp_version.py` is a marked render of it.
- **Measured (2026-10-15):**
  - crates.io trusted publishing: `rust-lang/crates-io-auth-action` v1.0.5
    (`c6f97d42243bad5fab37ca0427f495c86d5b1a18`, lightweight tag; one output, `token`); it cannot publish
    a crate's first version.
  - `cargo publish --dry-run --allow-dirty` packages and builds, uploading nothing; stamping a dev version
    into a workspace version breaks it for every crate whose siblings pin `version = "X.Y.Z"`.
  - Maven orders an unknown qualifier after the release (`1.0.0-dev.5` > `1.0.0`).
  - `central-publishing-maven-plugin` 0.12.0: user properties `skipUpload`, `autoPublish`, `waitUntil`
    (`VALIDATED` default, `UPLOADED`, `PUBLISHED`); with `skipUpload` it never builds its upload client or
    reads credentials; it validates nothing locally (the Portal does, on upload); `waitMaxTime` defaults to
    1800 s.
  - `actions/setup-java` v6.0.1: `server-id`, `server-username-env-var`, `server-password-env-var`,
    `gpg-private-key`, `gpg-passphrase-env-var` (`server-username`/`server-password`/`gpg-passphrase` are
    deprecated aliases); its GPG support needs `maven-gpg-plugin` 3.2.0 or newer.
- **Nothing tells a project what it lacks** before a release.

## Scope

### §S1 — Two new targets

- `workflows.RELEASE_TARGETS` becomes `("pypi", "npm", "crates", "maven-central", "github-assets")`, the
  canonical order; `crates` and `maven-central` take an optional `:dir` and carry a version source;
  `parse_target` and `release_targets_csv` accept them under every existing rule.
- The surfaces naming the supported targets list all five: the `--release-targets` help of `init` and
  `release-workflow` (`cli.py`), the schema entry's description, `stamp_version.py`'s docstring and its
  refusal text.
- The schema entry's readers gain `modelb-axi release-check`.

### §S2 — The version sources

`stamp_version.py` learns, under its existing rules (one stderr line per refusal, nothing written, bytes,
CRLF and trailing comments kept):

- **`crates:<dir>`** — `<dir>/Cargo.toml`'s `[package] version = "…"`; or, with `version.workspace = true`
  (or `version = { workspace = true }`) there, the repository root `Cargo.toml`'s
  `[workspace.package] version = "…"` (the same file when `<dir>` is `.`). Refused: no `[package]` table,
  no version line, a workspace version with no `[workspace.package] version`.
- **`maven-central:<dir>`** — `<dir>/pom.xml`'s own `<version>` (the child of `<project>`, never the
  `<parent>`'s). Refused: no own `<version>` (an inherited one), a property reference (`${…}`).
- **Neither is stamped.** Their rehearsals upload nothing (a dev version would break a Cargo workspace and
  sort after the release in Maven): `stamp` leaves both unchanged but refuses a version other than
  `X.Y.Z`; `check` compares both to the tag.
- **`read <target>...`,** a new read-only subcommand: prints `target<TAB>version` per target, exit 1 with
  each refusal's line otherwise. It is the one reader of version sources; `release-check` runs it.

### §S3 — The rendered jobs

Each new target adds, in canonical order:

- **`rehearse` steps:**
  - `crates:<dir>` — `cargo publish --dry-run --allow-dirty` in `<dir>`;
  - `maven-central:<dir>` — `actions/setup-java` (`distribution: temurin`, `java-version: "21"`,
    `gpg-private-key: ${{ secrets.MAVEN_GPG_PRIVATE_KEY }}`, `gpg-passphrase-env-var: MAVEN_GPG_PASSPHRASE`);
    `./mvnw -B -ntp -f <dir>/pom.xml deploy -DskipTests -DskipUpload=true` from the repository root with
    `MAVEN_GPG_PASSPHRASE: ${{ secrets.MAVEN_GPG_PASSPHRASE }}` (no Portal credentials); then a check that
    `<dir>/target/central-publishing/central-bundle.zip` holds an `.asc` signature for every artifact, a
    `-sources.jar` and a `-javadoc.jar`.
- **Publish jobs** on the release event, `needs:` every test job, checkout with `fetch-depth: 0` and the ref
  guard first:
  - `publish-crates` — environment `crates`, `contents: read` + `id-token: write`; job `env`
    `CARGO_FIRST_TOKEN: ${{ secrets.CARGO_REGISTRY_TOKEN }}`; `rust-lang/crates-io-auth-action` with
    `id: auth` and `if: env.CARGO_FIRST_TOKEN == ''`; `cargo publish` in `<dir>` with
    `CARGO_REGISTRY_TOKEN: ${{ steps.auth.outputs.token || secrets.CARGO_REGISTRY_TOKEN }}`;
  - `publish-maven-central` — environment `maven-central`, `contents: read`; `actions/setup-java` with
    `server-id: central`, `server-username-env-var: MAVEN_CENTRAL_USERNAME`,
    `server-password-env-var: MAVEN_CENTRAL_PASSWORD` and the rehearsal's GPG inputs; `./mvnw -B -ntp -f
    <dir>/pom.xml deploy -DskipTests -DautoPublish=true -DwaitUntil=PUBLISHED` from the root, with the four
    `MAVEN_*` env from repository secrets.
- **`create-release`'s check step** names the `crates` and `maven-central` targets with the others.
- **The header's setup list:**
  - `crates` — the environment `crates` admitting the version tags; the repository secret
    `CARGO_REGISTRY_TOKEN` for the first publish, then add the crates.io trusted publisher (repository,
    `release.yml`, environment `crates`) and delete the token;
  - `maven-central` — the environment `maven-central` admitting the version tags; the namespace verified on
    the Central Portal; the repository secrets `MAVEN_CENTRAL_USERNAME` and `MAVEN_CENTRAL_PASSWORD` (a
    Portal user token), `MAVEN_GPG_PRIVATE_KEY` and `MAVEN_GPG_PASSPHRASE`; the POM carrying
    `central-publishing-maven-plugin` with `<extensions>true</extensions>`, the sources and javadoc jars,
    and `maven-gpg-plugin` 3.2.0 or newer; one `mvnw` at the repository root.
- `ACTION_PINS` gains `rust-lang/crates-io-auth-action`.

### §S4 — Setup tasks

`init`'s `release_setup` and the `AGENTS.md` Setup section gain each new target's tasks (the header's items,
as tasks, in CR-MDB-068's form and order wording).

### §S5 — `modelb-axi release-check`

A read-only verb: `_add_release_check_parser` and its `main` dispatch in `cli.py`, run by
`scaffold.run_release_check`.

- **Where:** the project root — the directory holding `.env`; refused (exit 2, naming the directory to run
  it from) when the current directory has no `.env`. Target `dir`s are relative to it.
- **Reads** `PROJECT_STACKS` and `RELEASE_TARGETS` (refused, exit 2, when absent or invalid, as
  `release-workflow` refuses).
- **Local items:**
  - each rendered file: ready when it equals `workflows.render` for the current `.env` (a third caller,
    named in the callers gate); missing with "run `modelb-axi release-workflow`" when it differs or is
    absent; ready with a note when `hand_modified`;
  - each versioned target's version: ready when `python3 .github/scripts/stamp_version.py read …` reads it;
    missing with the script's line otherwise;
  - each stack's and target's prerequisite (`tests/`, `bun.lock`, `Cargo.lock` for the `rust` stack,
    `mvnw`, an executable `ci-test` or `build-assets`);
  - a target with no test job building it — `crates` without the `rust` stack, `maven-central` without
    `java` or `quarkus` — missing;
  - `CHANGELOG.md`: missing when absent; ready otherwise (an absent `[Unreleased]` is a note).
- **GitHub items:**
  - The repository comes from `git remote get-url origin`. The forms `https://github.com/o/r[.git]`,
    `git@github.com:o/r[.git]` and `ssh://git@github.com/o/r[.git]` are parsed by one helper. Any other
    host, or no remote, makes every GitHub item `unknown`.
  - `gh` is found with `shutil.which`; the argv is `gh api --method GET --paginate <path>`. The paths:
    - `repos/{o}/{r}/environments`;
    - `repos/{o}/{r}/environments/{e}/deployment-branch-policies`;
    - `repos/{o}/{r}/actions/secrets`.
  - No `gh`, a non-zero exit (unauthenticated, 403, network) or unparseable output makes the items it
    covers `unknown`, with the error in the detail.
  - Each target's environment must exist:
    - `testpypi` admitting `release/**` and `hotfix/**`;
    - each publish environment admitting the version tags. A null `deployment_branch_policy` is ready;
      `protected_branches: true` is missing; otherwise a `type: tag` policy must be present (ready, its
      patterns in the detail, not evaluated).
  - Each repository secret the rendered jobs name must exist, `RELEASE_PAT` always. `NPM_TOKEN` and
    `CARGO_REGISTRY_TOKEN` are `unknown` when absent (not needed once the trusted publisher exists).
  - Organisation and environment secrets are not read, and the detail says so.
- **Registry items:** each target's publisher (the PyPI and TestPyPI publisher, the npm and crates.io
  trusted publisher, the Central namespace) is `unknown`, its detail naming the exact fields to check.
- **Output:** one AXI envelope (verb `release-check`) with `items` (`area`, `item`, `state`, `detail`) and
  the counts `ready`, `missing`, `unknown`.
- **Exit codes:** 0 when nothing is missing; 1 when anything is; 2 on a refusal.
- **It never writes.** Its only subprocesses are `git remote get-url origin`, `gh api --method GET …` and
  `python3 .github/scripts/stamp_version.py read …`.

### §S6 — Model B, the skill and the docs

- **Model B:** its `.github/scripts/stamp_version.py` is re-rendered in C1 (the script changed); its
  `release.yml` and `changelog_section.py` are unchanged (its targets stay `pypi,npm:pi-package`); the
  byte-equality test holds after the re-render.
- **`skills-src/git-workflow/SKILL.md` § Releases:**
  - The targets table gains `crates` and `maven-central` rows, giving all four cells: rehearsal, publish,
    environment, secret.
  - `### Rehearsal and CI`'s dev-marker rule is amended: `pypi` and `npm` stamp a dev version; `crates`
    and `maven-central` upload nothing and keep `X.Y.Z`. Its rows gain both targets, and its phrase gate
    is migrated.
  - The release flow runs `modelb-axi release-check` before `git flow release start`, and fixes what it
    reports missing.
  - "Read release readiness from … `gh`" points at `release-check`.
  - The Maven sections are reconciled. The Java project's manual `./mvnw clean install` from `master`
    stays for a local install. A project with the `maven-central` target publishes through the release
    event's job, and the rehearsal's `deploy` uploads nothing.
- **`AGENTS.md`** names `modelb-axi release-check`.
- **`docs/install-guide.md`** names `crates[:<dir>]` and `maven-central[:<dir>]` in its `--release-targets`
  sentence, and `release-check` beside `release-workflow` (`pi-package/README.md` regenerated).
- **Gates that move** (each `# MIGRATED at CR-MDB-071 …`):
  - `test_release_targets` — `SUPPORTED`, `REFUSED` (unknown names become `cargo` and `maven`), the
    unknown-name and the key-and-flag refusal tests, the two-readers pin;
  - `test_workflow_render` — `RELEASE_TARGET_ORDER`, the bad-part refusal cases, the render-callers gate
    (three callers);
  - `test_release_workflow_verb`, `test_init_release_workflow` — the refusal and warning cases naming
    `crates`/`maven-central`;
  - `test_rendered_release_workflow` — `versioned()`, `ACTIONS`, `FULL_TARGETS`/`TARGET_SETS`,
    `SETUP_TARGET_SETS`, the tag-admission and first-publish-token readers extended to the new items;
  - `test_install_guide` — `RELEASE_TARGET_FORMS`, `TARGET_COLUMNS` (two new entries), the "renderer does
    not render" case, `REHEARSAL_AND_CI_PHRASES`;
  - `test_project_registry_schema` — `NOT_REGISTRY_KEYS` and `WORKFLOW_RUNTIME_NAMES` gain
    `CARGO_FIRST_TOKEN` and `CARGO_REGISTRY_TOKEN` (the detector flags them through "REGISTRY"); no
    `MAVEN_*` name, which it never matches;
  - the `AGENTS.md` counts and baselines.

## Acceptance criteria

- [ ] **§S1.** The new names in the canonical order; each accepted form and each refusal for them; one
      definition of the order; the five-target surfaces (help, schema description and readers,
      docstring, refusal text) pinned.
- [ ] **§S2.** `stamp`, `check` and `read` in temp trees: `crates` with a package version, `crates:.` as both
      workspace and package, `version = { workspace = true }`, a sub-directory, CRLF, `Cargo.lock` absent;
      `maven-central` with an own version beside a `<parent>` version; refused: no `[package]`, a
      workspace version without `[workspace.package] version`, a `<parent>`-only pom, `${revision}`;
      `stamp` leaves both unchanged and refuses a version other than `X.Y.Z`; `read` prints each version or
      exits 1; one stderr line per refusal; nothing written.
- [ ] **§S3.** For the target sets `crates`, `maven-central`, `crates:a,maven-central:b` and all five,
      tests read the rendered workflow:
      - each rehearsal step (the bundle check included);
      - each publish job: id, `if:`, `needs:`, environment, permissions, checkout and guard first, steps,
        the `with:` inputs and env names, and the auth step's `if:`;
      - the check step's targets, the header's lines, the pins.

      A test runs the bundle-check step's lines under `bash -e` on sample zips (complete, missing `.asc`,
      missing sources or javadoc). Model B's byte-equality test passes after the C1 re-render.
- [ ] **§S4.** `init` with each new target: the tasks in `release_setup` and the Setup section, once each.
- [ ] **§S5.** In sandbox projects, with a stub `gh` on `PATH` (never the real `gh`) and a stub origin:
      - every local item ready and missing (including the stale render and a target with no test job);
      - the three URL forms parsed, and a non-GitHub remote and no remote both `unknown`;
      - each GitHub item ready and missing, and `unknown` for: no `gh`, `gh` exit 1 (unauthenticated), a 403
        on the secrets list, and unparseable output;
      - the policy semantics: null, `protected_branches`, a tag policy;
      - the registry checklist;
      - the envelope fields and counts;
      - exit codes 0, 1 and 2 (no `.env`, the absent key, an invalid value);
      - nothing written (the tree unchanged byte for byte);
      - only the three subprocesses, `gh` with `--method GET`.
- [ ] **§S6.** The skill's rows, dev-marker rule, flow step and Maven reconciliation pinned and proved both
      ways; `AGENTS.md` and the install guide pinned; every gate in §S6's list migrated; the raw-runner,
      registry-key and project-name gates passing; the skill loading in Pi with no diagnostics;
      `pi-package/README.md` regenerated.
- [ ] **Runs.** Every commit leaves the suite green through the client with a real `HOME` and an empty one
      (temp home empty afterwards), beyond RED's own failures; `generator/build.py --check` clean; the
      `AGENTS.md` counts and baselines match.

## Non-goals

- **Several crates or Maven modules under one target** (a workspace publishing many crates).
- **Running the `crates` or `maven-central` jobs on a real runner** before a project uses them: the rendered
  jobs are read and their commands checked, not executed.
- **Organisation or environment secrets,** branch-pattern evaluation, and writing to GitHub or a registry
  from `release-check`.

## Cycle plan

1. **C1 — The targets, the version sources, the rendered jobs and Model B's re-rendered script (§S1–§S4).**
   Red-green.
2. **C2 — `modelb-axi release-check` (§S5).** Red-green.
3. **C3 — The skill and the docs (§S6).** Red-green; it re-measures the baselines.
4. **C4 — Verify.**
