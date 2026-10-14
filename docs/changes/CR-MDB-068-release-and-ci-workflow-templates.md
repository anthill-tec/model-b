# CR-MDB-068 — Release and CI workflow templates for every stack

**Status:** PENDING — **SEED, not the finished spec.** Gap analysis, the spec and its pre-review
happen in order when this CR starts.
**Type:** feature (scaffold, workflow templates, git-workflow skill)
**Priority:** P1 — release 1.0.0, wave 2; after CR-MDB-067.
**Depends on:** CR-MDB-070 (board-authoritative: read `queue`)
**Labels:** release, ci, scaffold
**Design reference:** `docs/research/release-automation-crucible-procedure.md`; CR-MDB-058 (release
notes, the release-job snippet, the packaging entries); CR-MDB-067 (the rehearsal on every release or
hotfix push, the dev-version stamp, the CI test workflow).

## Context

Release notes reach every stack: `init` writes a `CHANGELOG.md` skeleton, and the `git-workflow`
skill carries a stack-neutral create-release snippet. Release automation does not. Only Model B's own
`.github/workflows/release.yml` tests and publishes, for PyPI and npm, written by hand.
A scaffolded project gets no workflow file, and the skill names no publish path for crates.io, Maven
Central or the Arduino Library Manager. Each project writes its own release and CI jobs, so nothing
checks that a project is set up for a release or hotfix run.

## Scope (seed)

1. **Workflow templates per stack.** `init` renders into `.github/workflows/` one release workflow per
   project, in CR-MDB-070's shape:
   - a test job per stack, with no event condition, runs the stack's suite on the floor toolchain, in a
     clean home, with full history, in every run: pushes to `release/**`, `hotfix/**` and `master`, and
     the published release (never `develop` or pull requests);
   - every publish job needs the test jobs; the release is created from the `master` push for the
     `X.Y.Z` tag at `HEAD`, with the tag's `CHANGELOG.md` section as its body (CR-MDB-058); every
     `release/**` or `hotfix/**` push rehearses with the stack's dev version and the notes check
     (CR-MDB-067); the registry publishes run on the release event, guarded to a bare `X.Y.Z` tag on
     `master`:

     | Stack | Registry | Rehearsal | Publish |
     |---|---|---|---|
     | `python` | PyPI | TestPyPI upload | Trusted Publishing |
     | `bun` | npm | `npm publish --dry-run` with a dist-tag | Trusted Publishing; a one-time token for a new package |
     | `rust` | crates.io | `cargo publish --dry-run` | to measure |
     | `quarkus`, `java` | Maven Central | a validated, unpublished deployment | to measure (signing and credentials) |
     | `arduino` | Arduino Library Manager | the library linter | the tag (the index reads tags) |

   Multi-stack and monorepo shapes get one workflow with a test job per stack, not one workflow per
   stack.
2. **Ownership.** Rendered workflow files are tracked by hash like `init`'s other emitted files: a
   re-run rewrites an unchanged file, leaves a hand-edited one alone and reports it.
3. **Model B renders its own workflows** from the `python` and `bun` templates, replacing the
   hand-written `release.yml`.
4. **A release-readiness check** reports, read-only, what a project lacks for a release or hotfix
   run: the workflow files, the environments, the repository secrets and the trusted publishers each
   publish job names.
5. **The `git-workflow` skill** names the templates, the per-stack dev-version forms and the
   readiness check in its release flow.

## To measure at gap analysis

- Each registry's current publishing path: crates.io trusted publishing and its action, the Maven
  Central Portal's upload and validation API, the GPG signing step, the Arduino Library Manager's
  registration and linter.
- Each stack's dev-version form and its ordering against `X.Y.Z` (Maven's qualifier ordering in
  particular).
- Where the templates live: the raw-runner guard covers `generator/templates/` and `skills-src/`, and
  a CI template shows the suite command.
- How a template is proved without a project of that stack: text checks, a workflow linter, a local
  runner.
- How the readiness check reads GitHub state (`gh`, read-only) and what it does without `gh`.
- The 13-point cap: the split (templates and rendering, the per-registry publish jobs, the readiness
  check).
