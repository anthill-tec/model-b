# CR-MDB-070 — One release workflow: the tests gate every publish, on release, hotfix and master pushes

**Status:** COMPLETED (filed 2026-10-14; gap analysis and pre-review 2026-10-14)
**Type:** fix (release workflow, git-workflow skill, `AGENTS.md`)
**Priority:** P1 — release 1.0.0, wave 2; next after CR-MDB-069.
**Depends on:** CR-MDB-069 (board-authoritative: read `queue`)
**Labels:** release, ci
**Design reference:** `docs/research/release-automation-crucible-procedure.md` § "What Model B adopted
(2026-10-14, user rulings at CR-MDB-070's gap analysis)"; Crucible's `release.yml` (CR-CRU-062 §S0–§S4:
the gate is the dependency graph).

## Context

- **Two workflows, and no gate between them.** `.github/workflows/ci.yml` runs the suite on pushes to
  `develop`, `release/**` and `hotfix/**`, on pull requests and on dispatch. `.github/workflows/release.yml`
  publishes — `rehearse` (TestPyPI upload), `create-release` (on a tag push), `publish-pypi` and
  `publish-npm` (on the `release` event) — and none of its jobs depends on a test. GitHub's `needs:` orders
  jobs only within one run, so a separate workflow cannot gate a publish: a red tree can rehearse,
  create a release and publish.
- **CI runs where it is not wanted.** Every push to `develop` and every pull request runs the suite. Model
  B merges directly (git flow); the verification that matters is on the release candidate and `master`.
- **`create-release` fires on the tag push.** `git push origin master develop --tags` sends the `master`
  push and the tag push as separate runs.
- **`rehearse` admits any branch push** (`startsWith(github.ref, 'refs/heads/')`); a `master` trigger
  would run it there and fail at the stamp.
- **GitHub's default `run` shell is `bash -e`:** an assignment from a pipeline whose last command fails
  (`grep` with no match) fails the step.
- **The skill's release-job snippet** takes the tag from `github.ref_name`, which on a `master` push is
  `master`; its gate (`SNIPPET_TERMS`) checks only `gh release create`, `--notes-file` and
  `changelog.md`.
- **Readers.** `tests/test_ci_workflow.py` reads `ci.yml` (`name_faults` wants `name: ci`, `job_faults`
  exactly `["test"]`, `trigger_faults` `develop` and `pull_request`; `CONFORMING_CI` and `MUTATIONS`
  carry that shape). `tests/test_release_rehearsal.py` pins the triggers, `CREATE_RELEASE_IF`,
  `REHEARSE_IF`, `CREATE_RELEASE_TODAY` / `PUBLISH_PYPI_TODAY` / `PUBLISH_NPM_TODAY`, the header, and the
  readers' proofs (the exact step-key set, the exact push-trigger dicts). `tests/_helpers.py`'s readers
  read no step `id:`, no step-level `if:`, and not the `release` event.
  `tests/test_changelog_release_body.py` executes `create-release`'s run block holding
  `gh release create` with `TAG` set. `tests/test_suite_hygiene.py` pins `AGENTS.md`'s `ci.yml` unit
  and forbids "the only workflow" (`AGENTS_RETIRED_CI`). `tests/test_install_guide.py` pins the skill's
  CI rule (`REHEARSAL_AND_CI_PHRASES`, its `develop` / pull-request terms), the snippet and
  `CONFORMING_RELEASES_BODY`.

## Scope

### §S1 — One workflow, `release.yml`; `ci.yml` is deleted

- **`name: release`** (unchanged); workflow `permissions: contents: read` (unchanged).
- **Triggers:** `push` to `master`, `release/**` and `hotfix/**`; `release: types: [published]`;
  `workflow_dispatch`. No tag pattern, no `develop`, no `pull_request`.
- **A `test` job with no `if:`**, so it exists in every run: `runs-on: ubuntu-latest`; steps checkout
  (`fetch-depth: 0`), `actions/setup-python` with `python-version: "3.14"`, `astral-sh/setup-uv`, then
  `python -m unittest discover -s tests -t .` with `MODELB_HOME`, `XDG_DATA_HOME` and
  `PI_CODING_AGENT_DIR` under `${{ runner.temp }}`. It runs the suite directly (DN §D21).
- **Every publish job has `needs: test`:** `rehearse`, `create-release`, `publish-pypi`, `publish-npm`;
  `test` has no `needs`.
- `.github/workflows/ci.yml` no longer exists.

### §S2 — The release is created from the `master` push

`create-release`:
- `if: github.ref == 'refs/heads/master' && (github.event_name == 'push' || github.event_name ==
  'workflow_dispatch')`; `needs: test`; `permissions: contents: write`;
- checkout with `fetch-depth: 0`;
- a step with `id: tag` and no `shell:` that collects the tags pointing at `HEAD` matching
  `^[0-9]+\.[0-9]+\.[0-9]+$`, with `|| true` so no match does not fail the step under `bash -e`, and
  writes `tag=<the tag or empty>` to `$GITHUB_OUTPUT`:
  - none → prints `::notice::no version tag at HEAD — nothing to release`, empty output, exit 0;
  - more than one → exits 1 with an `::error::` line naming every one;
  - its text holds no `gh release create`;
- the tag == `__version__` check and the release step each carry `if: steps.tag.outputs.tag != ''` and
  `TAG: ${{ steps.tag.outputs.tag }}` in their `env`; the check reads `TAG` (not `GITHUB_REF_NAME`);
  the release step's two command lines are unchanged (CR-MDB-058 §S2).
- A dispatch on `master` re-runs it: the recovery when the master run found no tag at `HEAD`.

### §S3 — The rehearsal admits only release and hotfix refs

`rehearse`: `needs: test`; `if: (startsWith(github.ref, 'refs/heads/release/') || startsWith(github.ref,
'refs/heads/hotfix/')) && (github.event_name == 'push' || github.event_name == 'workflow_dispatch')`. A
dispatch on any other ref skips it. Its steps are unchanged.

### §S4 — The registry publishes guard their ref

`publish-pypi` and `publish-npm`: `needs: test`; still `if: github.event_name == 'release'`;
`publish-pypi` gains `contents: read` beside `id-token: write`. Their steps: checkout with
`fetch-depth: 0` first, then a guard step that exits 1 with an `::error::` line unless `GITHUB_REF`
matches `^refs/tags/[0-9]+\.[0-9]+\.[0-9]+$` and `GITHUB_SHA` is an ancestor of `origin/master` (after
`git fetch --no-tags origin master`), then every existing step unchanged apart from pins.

### §S5 — The header and the pins

- The header describes one workflow: the `test` job in every run, with the warning that it carries no
  `if:` and must never be scoped — a publish that needs a skipped job is itself skipped, silently; what
  each branch class and event runs (release/hotfix → tests + rehearsal; `master` → tests +
  `create-release`; the release event → tests + the guarded registry publishes); that every publish needs
  the tests; the recovery (dispatch on `master`); the one-time setup list (unchanged — it already names
  `testpypi`'s branches and no reviewers).
- Every action stays pinned to a 40-hex SHA with a `# vX.Y.Z` comment.

### §S6 — The skill, `AGENTS.md`, the docs

- **`skills-src/git-workflow/SKILL.md` § Releases:**
  - **the CI rule** (in `### Rehearsal and CI`, plain words, no runner command): the release
    workflow's test job runs the suite in every run — each push to a release or hotfix branch, each push
    to `master`, each published release — on the stack's floor interpreter, in a clean home, with full
    history, outside any agent session, the one place the suite runs without the stack's Crucible client;
    every publish job (the rehearsal included) needs it, because a dependency gates only within one run;
    no CI on `develop` or pull requests;
  - **the release-job snippet:** checks out with full history, takes the tag from
    `git tag --points-at HEAD` filtered to `X.Y.Z` (none → exit 0, nothing to release), names
    `github.ref_name` nowhere, sits in a job that needs the test job and runs on the `master` push; the
    literal-match, missing-or-empty and `--notes-file` rules stay;
  - **the release flow:** push `master`, `develop` and the tags in one `git push origin master develop
    --tags` — the `master` push runs the tests and creates the release, the release event publishes; if
    the `master` run reports no version tag at `HEAD`, dispatch the workflow on `master`.
- **`AGENTS.md`:** one workflow, `release.yml`, in plain words: its test job runs the suite on every
  release, hotfix and `master` push and every published release, outside agent sessions; it rehearses on
  release and hotfix pushes, creates the release from the `master` push (recovery: dispatch on
  `master`) and publishes on the release event, every publish gated on the tests. `ci.yml` is named
  nowhere; "no CI test workflow" stays forbidden.
- **`docs/research/release-automation-crucible-procedure.md`:** the CR-MDB-070 rulings (recorded at gap
  analysis); dated "superseded by CR-MDB-070, 2026-10-14" notes in "What Model B adopted (2026-09-24)"
  (`create-release` moved to the `master` push) and at the CR-MDB-067 bullet that says the CI workflow
  lives in `ci.yml`.
- **`docs/changes/CR-MDB-067-release-rehearsal-and-ci.md`:** one dated line at §S2 and §S3 each —
  "superseded by CR-MDB-070, 2026-10-14".

### §S7 — The gates this moves

Migrated pins carry `# MIGRATED at CR-MDB-070 …`:
- **`tests/_helpers.py`:** the step reader gains `id` and step-level `if`; the trigger reader reports the
  `release` event; each proved both ways on sample text. The proofs that pin the exact step-key set
  (`test_release_rehearsal.py`, `test_ci_workflow.py`) and the exact push-trigger dicts
  (`WorkflowReadersProofTest`) move with them.
- **`tests/test_ci_workflow.py`** reads `release.yml`: `name_faults` → `release`; `trigger_faults` →
  `master`/`release/**`/`hotfix/**` pushes, the release event, dispatch, no `develop`, no
  `pull_request`; `job_faults` → a `test` job on `ubuntu-latest` among the jobs, with no `if:`;
  `permission_faults` unchanged; `CONFORMING_CI` and `MUTATIONS` reshaped; `ci.yml` absent.
- **`tests/test_release_rehearsal.py`:** the triggers, `CREATE_RELEASE_IF`, `REHEARSE_IF`, the
  `*_TODAY` pins, `needs`, the header.
- **`tests/test_changelog_release_body.py`:** unchanged (its reader filters on `gh release create`; the
  `TAG` it sets stands for the step `env`).
- **`tests/test_suite_hygiene.py`:** the `AGENTS.md` units; `AGENTS_RETIRED_CI` drops "the only
  workflow" and keeps "no CI test workflow".
- **`tests/test_install_guide.py`:** the CI-rule phrases (the `develop` / pull-request terms inverted
  with a negation-aware check, proved both ways), the snippet check (passes with `--points-at`, bites on
  `github.ref_name`), the flow's one-push and recovery terms, `CONFORMING_RELEASES_BODY`.
- The `AGENTS.md` baselines.

## Acceptance criteria

- [ ] **§S1.** Tests read `release.yml` and assert: `name: release`; workflow permissions exactly
      `contents: read`; the triggers exactly; the `test` job's absence of `if:` and `needs`, its runner,
      steps and env; `needs: test` on each of the four publish jobs; `ci.yml` absent. The extended
      readers are proved both ways.
- [ ] **§S2.** `create-release`'s `if:`, permissions, checkout `fetch-depth: 0` and step order; the
      `id: tag` step declares no `shell:` and holds no `gh release create`. A test runs that step's
      command lines under `bash -e` in a temp git repo with `GITHUB_OUTPUT` at a temp file:
      - one `X.Y.Z` tag at `HEAD` → exit 0, `tag=X.Y.Z`;
      - no tag, or only non-version tags → exit 0, `tag=` empty, the `::notice::` line printed;
      - two version tags → exit 1, both named.

      The version check and the release step carry the `if:` and the `TAG` env; the check reads `TAG`;
      CR-MDB-058's execution test of the release step passes unchanged.
- [ ] **§S3.** `rehearse`'s `if:` and `needs: test`; its steps unchanged.
- [ ] **§S4.** Both jobs: `needs: test`, the `release` `if:`, `publish-pypi`'s `contents: read`,
      checkout `fetch-depth: 0` first, the guard second, every later step unchanged apart from pins. A
      test runs the guard's lines under `bash -e` in a temp repo with a bare `origin`: a clean `X.Y.Z` tag
      ref on `master`'s history passes; a non-version ref, and a commit not on `master`, each exit 1 with
      an `::error::` line.
- [ ] **§S5.** The header names the never-scope warning, the branch/event map, the recovery and the
      setup list (phrases pinned); SHA pins with version comments.
- [ ] **§S6.** The skill's CI rule (all its phrases, no positive `develop`/PR mention), snippet and flow;
      `AGENTS.md`; the research notes; the CR-MDB-067 lines — each pinned, the skill gates proved both
      ways, the raw-runner guard and the skill's Pi loader check passing.
- [ ] **Runs.** Every commit leaves the suite green through the client with a real `HOME` and an empty
      one (temp home empty afterwards), beyond RED's own failures; `generator/build.py --check` clean;
      the baselines match.
- [ ] **After the merge:** the `develop` push runs no workflow (read with `gh run list`, read-only); the
      first `release/1.0.0` push runs `test` then `rehearse`; at 1.0.0, the `master` run did `test` →
      `create-release` and the release run did `test` → guard → publish.

## Non-goals

- **Per-stack templates** of this shape are CR-MDB-068 (its seed follows this shape).
- **A `build` job and artifact hand-off** (Crucible's): each publish job builds for itself, as today.
- **CI on `develop`.** A red `develop` is caught by the release branch's first push, before anything
  publishes.

## Cycle plan

1. **C1 — The workflow: one file, the test job, the gate, `create-release` on `master`, the guards, the
   readers (§S1–§S5).** Red-green.
2. **C2 — The skill, `AGENTS.md` and the docs (§S6, §S7's remaining gates).** Red-green; it re-measures
   the baselines.
3. **C3 — Verify.**
