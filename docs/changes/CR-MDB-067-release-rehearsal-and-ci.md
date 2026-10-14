# CR-MDB-067 — The release rehearsal on every release or hotfix push, and CI tests on develop

**Status:** COMPLETED (filed 2026-10-14; gap analysis and pre-review 2026-10-14)
**Type:** feature (CI workflows, release workflow, git-workflow skill)
**Priority:** P1 — release 1.0.0, wave 2; lands before 1.0.0's release starts.
**Depends on:** CR-MDB-058 (board-authoritative: read `queue`)
**Labels:** release, ci
**Design reference:** `docs/research/release-automation-crucible-procedure.md` § "What Model B adopted
(2026-10-14, user rulings at CR-MDB-058's gap analysis)" and § "… at CR-MDB-067's gap analysis";
Crucible #1433 §A2; DN-multi-harness-deploy-model §D21 (a CI workflow runs outside any agent session).

## Context

- **The rehearsal is manual.** `.github/workflows/release.yml`'s `rehearse-testpypi` runs only on
  `workflow_dispatch`, and it has never run: the repository has no Actions run at all.
- **Nothing tests `develop`.** Model B has no CI test workflow, so a red `develop` goes unnoticed until
  a release.
- **A distinct version per push is needed.** TestPyPI never accepts the same file twice, and the version
  is the fixed `modelb_axi.__version__` (`pyproject.toml` reads it at build time).
- **The release branch is never pushed.** The release flow runs `git flow release start`, commits,
  `finish`, then pushes `master`, `develop` and the tags, so a rehearsal triggered by a release-branch
  push would never run. `git flow release finish` (gitflow-avh 1.12.3) deletes the remote release
  branch when one exists; `git flow hotfix publish` exists beside `git flow release publish`.
- **npm refuses a prerelease without a dist-tag.** `npm publish` of `X.Y.Z-dev.N` stops with "You must
  specify a tag using --tag when publishing a prerelease version", in a dry run too (npm 12.2.0). With
  `id-token: write`, a dry run still performs npm's OIDC token exchange; it publishes nothing.
- **`create-release` runs on every push event**, so a branch trigger in the same workflow would run it.
- **The suite fails on a clean runner.** Measured in the hosted-runner image
  (`catthehacker/ubuntu:act-latest`, as uid 1000, Python 3.14.4, no `pi`, `sandesh` or Crucible
  install):
  - with `uv` on `PATH`: 2641 tests, **3 failures**, 28 skips;
  - without `uv`: 14 failures — 11 more tests fail by design when `uv` is absent.

  The 3 are `test_pi_agent_definitions`'s `InstalledWheelInitRendersAgentsS6Test` and both
  `InstallerWritesNoAgentsS6Test` tests. Their installer runs need `sandesh` on `PATH`; without it the
  pre-flight runs a real `uv tool install sandesh-relay` and then refuses. They pass on a machine with
  `sandesh`.
- **Stale text.** The `git-workflow` skill's Python and Pi release steps describe a manual TestPyPI
  rehearsal into an isolated tool directory and user-supplied upload credentials; `AGENTS.md` says
  Model B has no CI test workflow.

## Scope

### §S1 — The version stamp

**`.github/scripts/stamp_version.py`** is a repo-only script, never in the wheel or the sdist. It is
stdlib only and uses no syntax newer than Python 3.12, the hosted runner's default.

- **It is called as** `python3 .github/scripts/stamp_version.py <ref> <run-number>` from the repository
  root.
- **It accepts** a ref `release/X.Y.Z` or `hotfix/X.Y.Z`, each of `X`, `Y`, `Z` matching
  `0|[1-9][0-9]*`, and a run number `N` matching `[1-9][0-9]*`.
- **It refuses, exiting 1 with one line on stderr and writing nothing, when:**
  - the ref has another form — the line names the ref;
  - the run number has another form — the line names it;
  - `modelb_axi/__init__.py`'s `__version__` or `pi-package/package.json`'s `version` is not `X.Y.Z` —
    the line names the file, the version found and `X.Y.Z`.
- **Otherwise it writes** `__version__ = "X.Y.Z.devN"` into `modelb_axi/__init__.py` and
  `"version": "X.Y.Z-dev.N"` into `pi-package/package.json`, changing only those two values (every
  other byte of both files unchanged), and prints `X.Y.Z` on stdout.
- **The npm form** equals the tests' `npm_semver` of the PEP 440 form.

### §S2 — The rehearsal job

Superseded by CR-MDB-070, 2026-10-14.

`.github/workflows/release.yml`:

- **Triggers.** `on.push` keeps the tag pattern and gains `branches: ["release/**", "hotfix/**"]`;
  `workflow_dispatch` stays.
- **`create-release`** has `if: github.event_name == 'push' && startsWith(github.ref, 'refs/tags/')`.
  Its steps are unchanged. `publish-pypi` and `publish-npm` are unchanged.
- **`rehearse` replaces `rehearse-testpypi`**:
  - `if: github.event_name == 'workflow_dispatch' || (github.event_name == 'push' &&
    startsWith(github.ref, 'refs/heads/'))`;
  - `runs-on: ubuntu-latest`, `environment: testpypi`, permissions `contents: read` and
    `id-token: write`;
  - no job-level `defaults.run`, and no `shell:` on any step;
  - its steps, in order:
    1. checkout;
    2. one `run` step whose command lines are, in order,
       `version=$(python3 .github/scripts/stamp_version.py "$GITHUB_REF_NAME" "$GITHUB_RUN_NUMBER")`
       standing alone, then `python3 .github/scripts/changelog_section.py CHANGELOG.md "$version"`
       with stdout sent to `/dev/null`. A refusing stamp fails the step before the notes check; a
       missing or empty section fails it after. A dispatch on any other ref fails here;
    3. `setup-uv`, then `uv build`;
    4. `pypa/gh-action-pypi-publish` with `repository-url: https://test.pypi.org/legacy/` and
       `skip-existing: true`, so a re-run of the same run number succeeds;
    5. `setup-node` with `node-version: "22"`, then `npm install -g npm@latest`, as `publish-npm` does;
    6. with step-level `working-directory: pi-package`: `cp ../CHANGELOG.md .`, then
       `npm publish --dry-run --access public --tag dev`.
- **Every action** in `release.yml` is pinned to a 40-hex commit SHA with its release version in a
  `# vX.Y.Z` comment; `pypa/gh-action-pypi-publish` is re-pinned from the `release/v1` branch to a
  tagged release.
- **The header comment** says every release or hotfix push rehearses (TestPyPI upload, the notes check,
  the npm dry run) and a dispatch re-runs one on a release or hotfix ref. Its one-time setup list adds:
  the `testpypi` environment admits `release/**` and `hotfix/**` and carries no required reviewers.

### §S3 — The CI test workflow

Superseded by CR-MDB-070, 2026-10-14.

`.github/workflows/ci.yml`, `name: ci`, workflow `permissions: contents: read`, one job `test` with
`runs-on: ubuntu-latest`:

- **Triggers:** `push` to `develop`, `release/**` and `hotfix/**`; `pull_request`; `workflow_dispatch`.
- **Steps, in order:**
  1. checkout with `fetch-depth: 0` (the archive-mapping check resolves real commits);
  2. `actions/setup-python` with `python-version: "3.14"`;
  3. `setup-uv` (`uv` on `PATH`: the build and isolated-install checks fail without it, by design);
  4. `python -m pip install build`, so the built-wheel checks run;
     Step 4 was retired by CR-MDB-069 §S2, 2026-10-14.
  5. the suite, run directly (DN §D21: CI runs outside any agent session):
     `python -m unittest discover -s tests -t .`, with `MODELB_HOME`, `XDG_DATA_HOME` and
     `PI_CODING_AGENT_DIR` set under `${{ runner.temp }}`.
- **Every action** is pinned as §S2 pins them.

### §S4 — The suite passes on a clean runner

`InstalledWheelInitRendersAgentsS6Test` and both `InstallerWritesNoAgentsS6Test` tests give their
installer runs a temp bin directory, first on `PATH`, holding a `sandesh` whose body is
`fake_sandesh(log=…)` (`tests/pi_capability_sandbox.py`), written with `write_executable`
(`tests/_helpers.py`). No new fake or helper is added. The seams are `run_env["PATH"]` in
`InstalledWheelInitRendersAgentsS6Test` and `env_overrides={"PATH": …}` in
`InstallerWritesNoAgentsS6Test`; `_run_module_c3`, which other classes share, is unchanged.

### §S5 — The `git-workflow` skill's release flow

`skills-src/git-workflow/SKILL.md` § Releases:

- **Publishing the branch.** After `git flow release start X.Y.Z` (or `git flow hotfix start X.Y.Z`),
  the version bump in every version source and the release's `CHANGELOG.md` section are committed,
  then the branch is published (`git flow release publish X.Y.Z`, `git flow hotfix publish X.Y.Z`).
  Every push of the branch is the rehearsal; `finish` deletes the remote branch.
- **The release-notes step** is written before the branch is first published (it was "before
  `finish`").
- **A `### Rehearsal and CI` subsection, after `### Pi package releases`,** holds:
  - **the rehearsal rule**, stack-neutral: each push to `release/X.Y.Z` or `hotfix/X.Y.Z` builds
    `X.Y.Z` with a dev marker and the CI run number in the stack's form, refuses a committed version
    other than `X.Y.Z`, and fails on a missing or empty notes section;
  - **the forms table:**

    | Stack | Dev version | Rehearsal |
    |---|---|---|
    | `python` | `X.Y.Z.devN` | the upload to the test index |
    | `bun` | `X.Y.Z-dev.N` | the package manager's dry-run publish with a dist-tag |
    | `arduino`, `quarkus`, `java`, `rust` | — | the notes check only |

  - **the CI rule**, in plain words with no runner command shown: a CI workflow runs the suite on every
    push to `develop`, release and hotfix branches and on pull requests, on the stack's floor
    interpreter, in a clean home, with full history; it runs outside any agent session, the one place
    the suite runs without the stack's Crucible client.

  The subsection names neither the Python steps' anchors nor the Pi step's, so each checker's
  first-occurrence order is unchanged.
- **The Python steps** read: build (the version in its single source, `uv build`); rehearse (each
  release-branch push uploads the stamped dev version to TestPyPI through Trusted Publishing); publish
  (after `git flow release finish`, the tag's release job uploads to PyPI through Trusted Publishing,
  with no token anywhere); post-release maintenance (unchanged).
- **The Pi package steps** read: publish (after the version is set, the tag's release job runs
  `npm publish --access public` through Trusted Publishing; the first publish of a new package uses a
  one-time granular token kept as a repository secret, then the trusted publisher is added, 2FA is
  required and the token deleted); the isolated `PI_CODING_AGENT_DIR` install and the live check
  (unchanged).
- **CR-MDB-058's text rules hold:** no project named, the steps' first-occurrence order kept, no runner
  invocation in a code span, the phrase gates migrated, never duplicated.

### §S6 — The docs and the gates this change moves

- **`AGENTS.md`:** the "no CI test workflow" sentence goes; the text names `ci.yml` (the suite on
  `develop`, release and hotfix pushes and pull requests, on a clean runner, outside agent sessions) and
  `release.yml`'s rehearsal on every release or hotfix push, in plain words with no runner command in a
  code span. The module counts move with each new test module, in the cycle that adds it.
- **`docs/research/release-automation-crucible-procedure.md`:** "What Model B adopted (2026-09-24)"
  gains a dated note (2026-10-14) that the manual `rehearse-testpypi` became the `rehearse` job on every
  release or hotfix push; the setup status notes that the `testpypi` environment admits `release/**`
  and `hotfix/**` and carries no required reviewers.
- **The workflow readers** in `tests/_helpers.py` grow, proved on sample text, existing callers
  unchanged: `_workflow_step` also returns `uses` and `with` (the step's `with:` scalars as a dict);
  new `workflow_job_key(job, key)` (a job's scalar key such as `if`, `runs-on`, `environment`),
  `workflow_job_permissions(job)` and `workflow_push_triggers(text)` (the `on.push` tag and branch
  patterns, and whether `pull_request` and `workflow_dispatch` are present).
- **Gates that move, per cycle:**

  | Cycle | Gates |
  |---|---|
  | **C1** | `tests/test_release_rehearsal.py` (new: §S1, §S2); the readers; `AGENTS.md`'s module counts |
  | **C2** | `tests/test_ci_workflow.py` (new: §S3); the three §S4 tests; `AGENTS.md`'s module counts |
  | **C3** | `tests/test_install_guide.py`: `PYTHON_RELEASE_STEPS`, `PI_PACKAGE_RELEASE_STEPS`, their sample-text proofs, `CONFORMING_RELEASES` (the notes step before the first publish), new groups for the publish step and the `### Rehearsal and CI` subsection, a retired-phrase gate, and the module docstring's item (F); the `AGENTS.md` text and baselines |

  The C3 gate content:
  - **Python, build:** unchanged.
  - **Python, rehearse:** anchor `testpypi`; terms `each release-branch push`, `stamped dev version`,
    `trusted publishing`.
  - **Python, publish:** anchor `no token anywhere`; term `git flow release finish`.
  - **Python, post-release maintenance:** unchanged.
  - **Pi, npm publish:** the terms `credentials the user supplies` and `at publish time` go; the terms
    `trusted publishing`, `repository secret` and `2fa` join.
  - **Retired phrases**, none anywhere in `## Releases`: `isolated tool directory`, `uv_tool_dir`,
    `test.pypi.org/simple`, `token the user supplies`, `user-supplied token`,
    `credentials the user supplies`, `user-supplied credentials`.
- **Comments** moved or added in tests use a literal `§`, never a `\uXXXX` escape.

## Acceptance criteria

- [ ] **§S1 — the script.** Loaded by path in a test, run in a temp tree holding copies of both version
      files:
      - `release/1.2.3` with run `7` writes `1.2.3.dev7` and `1.2.3-dev.7`, prints `1.2.3`, and leaves
        every other byte of both files unchanged;
      - `hotfix/1.2.4` stamps the same way;
      - each refusal exits 1 with exactly one stderr line naming what §S1 says, and leaves both files
        byte-identical: refs `develop`, `feature/x`, `release/1.2`, `release/v1.2.3`,
        `release/01.2.3`, a tag `1.2.3`; run numbers `0`, `-1`, `x`, `07`; a `__version__` other than
        `X.Y.Z`; a `package.json` `version` other than `X.Y.Z`;
      - the npm form equals `npm_semver` of the PEP 440 form for runs 1, 7 and 123.

      It imports only stdlib modules, parses under `ast.parse(..., feature_version=(3, 12))`, and is in
      neither the sdist nor the wheel.
- [ ] **§S2 — the workflow.** Tests read `release.yml` with the §S6 readers and assert:
      - the push triggers are the tag pattern and exactly `release/**` and `hotfix/**`;
        `workflow_dispatch` is present;
      - `create-release`'s and `rehearse`'s `if:` are §S2's expressions; `publish-pypi` and
        `publish-npm` are unchanged;
      - there is no `rehearse-testpypi`; `rehearse`'s `runs-on`, environment, permissions, absent
        `defaults.run`, and step order are §S2's;
      - the upload's `repository-url` and `skip-existing: true`; `node-version: "22"`; step 6's
        `working-directory: pi-package`, the copy before `npm publish --dry-run --access public --tag
        dev`;
      - every `uses:` is pinned to a 40-hex SHA with a `# vX.Y.Z` comment;
      - the header names release and hotfix pushes, no longer says a manual run rehearses the Python
        upload, and lists the `testpypi` setup note.

      A test runs step 2's command lines under `bash -e` in a temp tree with `GITHUB_REF_NAME` and
      `GITHUB_RUN_NUMBER` set:
      - a good ref and section: exit 0 and both files stamped;
      - a refused ref: non-zero, stderr carries the stamp's line naming the ref and not
        `no section for tag`;
      - a missing section and an empty section: non-zero, stderr names the changelog.
- [ ] **§S3.** Tests read `ci.yml` with the §S6 readers and assert: `name: ci`; the push branches
      exactly `develop`, `release/**` and `hotfix/**`; `pull_request` and `workflow_dispatch`; workflow
      permissions `contents: read`; job `test` on `ubuntu-latest`; the step order; `fetch-depth: 0`;
      `python-version: "3.14"`; the `setup-uv` step; `python -m pip install build`; the three sandbox
      variables under `runner.temp`; the command `python -m unittest discover -s tests -t .`; and the
      SHA pins with version comments.
- [ ] **§S4.** Each of the three tests writes its fake with `fake_sandesh(log=…)` and asserts the log
      holds a `--version` line — the pre-flight found the fake, so no install path ran. The
      orchestrator measures the suite through the client in the hosted-runner image (no `pi`, `sandesh`
      or Crucible install, `uv` on `PATH`): 0 failures.
- [ ] **§S5.** The skill names the publish step, the notes step before the first publish, the
      `### Rehearsal and CI` subsection with its rule, table and CI rule, and the rewritten Python and
      Pi steps. The migrated and new gates pass, each proved on sample text in both directions; the
      retired-phrase gate passes; the raw-runner guard and the project-name and order gates pass; the
      skill loads in Pi's own loader with no diagnostics.
- [ ] **§S6.**
      - Tests pin `AGENTS.md`: it names `ci.yml` and the rehearsal, no longer says "no CI test
        workflow", and shows no runner in a code span; and the research doc's dated note and setup
        note.
      - The readers are proved on sample text, and existing callers pass unchanged.
      - Every gate in §S6's table moves in its cycle.
      - Every cycle's commit leaves the suite green through the client with a real `HOME` and with an
        empty one, beyond RED's own failures, and the temp home is empty afterwards.
      - `generator/build.py --check` is clean, the `AGENTS.md` counts and baselines match the measured
        ones, and no new `\uXXXX` escape appears.
- [ ] **After the merge:** the push of `develop` runs `ci.yml` green on GitHub (read with `gh run list`
      / `gh run view`, read-only).

## Non-goals

- **Release and CI workflow templates for every stack** are CR-MDB-068.
- **The first real rehearsal** is the 1.0.0 release branch's first push; a fault found there is fixed on
  the release branch.
- **Gating the rehearsal on the CI tests.** The two workflows run side by side on a release push.
- **Provenance in the dry run**, and required reviewers on the `testpypi` environment.
- **The root `AGENTS.md`** ("no CI") is a Roundhouse root-session follow-up.

## Cycle plan

1. **C1 — The version stamp, the rehearsal job and the readers (§S1, §S2).** Red-green.
2. **C2 — The CI workflow and the clean-runner tests (§S3, §S4).** Red-green; the orchestrator measures
   the hosted-runner image.
3. **C3 — The skill, the docs and the gates (§S5, §S6).** Red-green; it re-measures the baselines.
4. **C4 — Verify.**
