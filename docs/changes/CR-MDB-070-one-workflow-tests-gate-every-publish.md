# CR-MDB-070 — One release workflow: the tests gate every publish, on release, hotfix and master pushes

**Status:** PENDING — spec (gap analysis 2026-10-14).
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
  B merges directly (git flow), and the verification that matters is on the release candidate and on
  `master`.
- **`create-release` fires on the tag push.** `git push origin master develop --tags` sends the `master`
  push and the tag push as separate runs.
- **`rehearse` admits any branch push** (`startsWith(github.ref, 'refs/heads/')`); a `master` trigger
  would run it there and fail at the stamp.
- **Readers.** `tests/test_ci_workflow.py` reads `ci.yml`; `tests/test_release_rehearsal.py` pins the
  triggers, `create-release`'s and `rehearse`'s `if:`, and "unchanged apart from" regressions;
  `tests/test_changelog_release_body.py` executes `create-release`'s two command lines with `TAG` set;
  `tests/test_suite_hygiene.py` pins `AGENTS.md`'s `ci.yml` and rehearsal units; `tests/test_install_guide.py`
  pins the skill's CI rule, the release flow and the release-job snippet.

## Scope

### §S1 — One workflow, `release.yml`; `ci.yml` is deleted

- **Triggers:** `push` to `master`, `release/**` and `hotfix/**`; `release: [published]`;
  `workflow_dispatch`. No tag pattern, no `develop`, no `pull_request`. Workflow `permissions: contents:
  read`.
- **A `test` job with no `if:`**, so it exists in every run: `runs-on: ubuntu-latest`; steps checkout
  (`fetch-depth: 0`), `actions/setup-python` with `python-version: "3.14"`, `astral-sh/setup-uv`, then
  `python -m unittest discover -s tests -t .` with `MODELB_HOME`, `XDG_DATA_HOME` and
  `PI_CODING_AGENT_DIR` under `${{ runner.temp }}`. It runs the suite directly (DN §D21).
- **Every publish job has `needs: test`:** `rehearse`, `create-release`, `publish-pypi` and
  `publish-npm`. No job other than `test` lacks it.
- `.github/workflows/ci.yml` no longer exists.

### §S2 — The release is created from the `master` push

`create-release`:
- `if: github.ref == 'refs/heads/master' && (github.event_name == 'push' || github.event_name ==
  'workflow_dispatch')`; `needs: test`; `contents: write`;
- checkout with `fetch-depth: 0`;
- a step with `id: tag` that finds the `X.Y.Z` tag (`^[0-9]+\.[0-9]+\.[0-9]+$`) pointing at `HEAD` and
  writes it as the step output `tag`: none → a notice "no version tag at HEAD — nothing to release" and
  an empty output; more than one → the job fails naming them;
- the tag == `__version__` check and the release step run only when `steps.tag.outputs.tag` is
  non-empty, each with `TAG: ${{ steps.tag.outputs.tag }}` in its `env`; the check reads `TAG`
  instead of `GITHUB_REF_NAME`; the release step's two command lines are unchanged (CR-MDB-058 §S2).
- A dispatch on `master` re-runs it (recovery when the tag reached the remote after the push's run).

### §S3 — The rehearsal admits only release and hotfix refs

`rehearse`: `needs: test`; `if: (startsWith(github.ref, 'refs/heads/release/') || startsWith(github.ref,
'refs/heads/hotfix/')) && (github.event_name == 'push' || github.event_name == 'workflow_dispatch')`. A
dispatch on any other ref skips it (it no longer fails at the stamp). Its steps are unchanged.

### §S4 — The registry publishes guard their ref

`publish-pypi` and `publish-npm`: `needs: test`; still `if: github.event_name == 'release'`; and, before
building or publishing, checkout with `fetch-depth: 0` and a guard step that refuses (exit 1 with an
`::error::` line) unless `GITHUB_REF` matches `^refs/tags/[0-9]+\.[0-9]+\.[0-9]+$` and `GITHUB_SHA` is an
ancestor of `origin/master` (after `git fetch --no-tags origin master`). Their other steps are unchanged.

### §S5 — The header and the pins

- The header comment describes one workflow: the `test` job in every run; what each branch class and
  event runs (release/hotfix → tests + rehearsal; `master` → tests + `create-release`; the `release`
  event → tests + the guarded registry publishes); that every publish needs the tests; the one-time setup
  list (unchanged, plus: `testpypi` admits `release/**` and `hotfix/**`, no required reviewers).
- Every action stays pinned to a 40-hex SHA with a `# vX.Y.Z` comment.

### §S6 — The skill, `AGENTS.md`, the docs

- **`skills-src/git-workflow/SKILL.md` § Releases:**
  - **the CI rule** (in `### Rehearsal and CI`, plain words, no runner command): the release workflow's
    test job runs the suite in every run — each push to a release or hotfix branch, each push to
    `master`, each published release — on the stack's floor interpreter, in a clean home, with full
    history, outside any agent session; every publish job (the rehearsal included) needs it, because a
    dependency gates only within one run. No CI on `develop` or pull requests;
  - **the release-job snippet:** the release is created from the `master` push for the `X.Y.Z` tag at
    `HEAD` (none → nothing to release), in a job that needs the test job; the literal-match,
    missing-or-empty and `--notes-file` rules stay;
  - **the release flow:** `git push origin master develop --tags` — the `master` push runs the tests and
    creates the release; the release event publishes.
- **`AGENTS.md`:** one workflow, `release.yml`, in plain words: its test job runs the suite on every
  release, hotfix and `master` push and every published release, outside agent sessions; it rehearses on
  release and hotfix pushes, creates the release from the `master` push and publishes on the release
  event, every publish gated on the tests. `ci.yml` is named nowhere.
- **`docs/research/release-automation-crucible-procedure.md`:** the CR-MDB-070 rulings (recorded at gap
  analysis) and a dated note in "What Model B adopted (2026-09-24)" that `create-release` moved to the
  `master` push.
- **`docs/changes/CR-MDB-067-release-rehearsal-and-ci.md`:** one dated line at §S2 and §S3 each —
  "superseded by CR-MDB-070, 2026-10-14".

### §S7 — The gates this moves

`tests/test_ci_workflow.py` reads `release.yml`'s `test` job (and asserts `ci.yml` is absent);
`tests/test_release_rehearsal.py` (triggers, both `if:`, the "unchanged apart from" pins, `needs`, the
header); `tests/test_changelog_release_body.py` (only if its step reader needs the `TAG` env); the
`AGENTS.md` units in `tests/test_suite_hygiene.py`; the skill gates in `tests/test_install_guide.py`;
the `AGENTS.md` baselines. Migrated pins carry `# MIGRATED at CR-MDB-070 …`.

## Acceptance criteria

- [ ] **§S1.** Tests read `release.yml` (stdlib readers in `tests/_helpers.py`, extended and proved on
      sample text if needed) and assert the triggers exactly; the `test` job's absence of `if:`, its
      steps and env; `needs: test` on each of the four publish jobs and on no other; `ci.yml` absent.
- [ ] **§S2.** The `if:`, permissions and step order of `create-release`. A test runs the `id: tag`
      step's command lines under `bash -e` in a temp git repo: a single `X.Y.Z` tag at `HEAD` → that
      output; none (or only non-version tags) → empty output and exit 0; two version tags → non-zero.
      The version check and the release step are conditioned on the output and take `TAG` from it;
      the release step's command lines still pass CR-MDB-058's execution test.
- [ ] **§S3.** `rehearse`'s `if:` and `needs: test`; its steps unchanged.
- [ ] **§S4.** Both guards: a test runs the guard's command lines under `bash -e` in a temp repo with a
      bare `origin`: a clean `X.Y.Z` tag ref on `master`'s history passes; a non-version ref, and a
      commit not on `master`, each exit 1 with an `::error::` line.
- [ ] **§S5.** The header text and the SHA pins with version comments.
- [ ] **§S6.** The skill's CI rule, snippet and flow; `AGENTS.md`; the research doc; the CR-MDB-067
      lines — each pinned, the skill gates proved both ways, the raw-runner guard and the skill's Pi
      loader check passing.
- [ ] **Runs.** Every commit leaves the suite green through the client with a real `HOME` and an empty
      one (temp home empty afterwards), beyond RED's own failures; `generator/build.py --check` clean;
      the baselines match.
- [ ] **After the merge:** nothing runs on the `develop` push (read with `gh run list`, read-only); the
      first `release/1.0.0` push runs `test` then `rehearse`.

## Non-goals

- **Per-stack templates** of this shape are CR-MDB-068 (its seed follows this shape).
- **A `build` job and artifact hand-off** (Crucible's): each publish job builds for itself, as today.
- **CI on `develop`.** A red `develop` is caught by the release branch's first push, before anything
  publishes.

## Cycle plan

1. **C1 — The workflow: one file, the test job, the gate, `create-release` on `master`, the guards
   (§S1–§S5).** Red-green.
2. **C2 — The skill, `AGENTS.md` and the docs (§S6, §S7).** Red-green; it re-measures the baselines.
3. **C3 — Verify.**
