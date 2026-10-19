# CR-MDB-078 — Tests for the rust health tools, and the defects they find

**Status:** PENDING — spec drafted 2026-10-19 from the gap analysis, the spec pre-review folded in;
awaiting approval.
**Type:** tests + fixes (the deployed rust health tools)
**Priority:** P1 — release 1.0.0, wave 2; after CR-MDB-073.
**Depends on:** CR-MDB-073, whose gate measures the result. The board is authoritative: read `queue`.
**Labels:** tests, coverage, scripts, rust
**Design reference:** PRD D5, the coverage ruling of 2026-10-17 (the package and every script are
measured, with subprocess measurement; a no-drop ratchet); `skills-src/code-health/SKILL.md` (what
the tools are for).

## Context

`scripts/rust-crate-map.py`, `scripts/rust-dead-scan.py` and their orchestrator
`scripts/rust-code-health.py` are deployed to every installation under `~/.agents/scripts/` and
driven by the `code-health` skill. The suite checks their adoption, layout and invocation, never what
they compute. Measured 2026-10-19 on develop, by the whole suite under the `[tool.coverage]` config:

| Script | Statements covered |
|---|---|
| `scripts/rust-code-health.py` | 0/381 |
| `scripts/rust-crate-map.py` | 8/251 |
| `scripts/rust-dead-scan.py` | 51/468 |

Measured defects:

- **Workspace members.** Both scanners find `members` with a regular expression over the root
  `Cargo.toml`. Cargo's glob form (`members = ["crates/*"]`) stops each of them with a
  `FileNotFoundError` traceback; a `default-members` line before `members` silently selects the wrong
  set; a commented-out `members` line is read. A root package is never a member, and a member's
  package name is read with a regular expression too.
- **The snapshot's rules.** A snapshot copies `crate_map.toml`, `dead_code_register.toml` and
  `boundary_rules.toml` into its directory but not `hot_path_rules.toml`. Its dead-scan runs with the
  snapshot directory as `--out`, so a snapshot never applies the hot-path rules, and its totals carry
  no hot-path counts.
- **A failed snapshot blocks its retry.** The snapshot directory is created before the sub-tools run
  and is left behind when one fails; a rerun on the same commit and day is refused because it exists.
- **Snapshot order.** `health/index.json` and the post/pre pairing order snapshots by directory name,
  `<date>_<sha>_<phase>[_<slice>]`, so two snapshots made the same day order by their short sha.
- **The dead-scan report.** Hot-path results reach the JSON report only: the markdown report has no
  hot-path section. The module docstring's default modes do not match `main()`'s, and the rust memory
  template's list of modes omits `hot-path`.
- **`lift-lint`.** It copies the tree through a shell pipeline with the project path unquoted, so a
  path containing a space fails; with `cargo` absent, or in a repository with no commit, it stops with
  a traceback and leaves its scratch copy behind.
- **Missing arguments.** `query delta` without its two snapshot names stops with a `TypeError`
  traceback; `query crate` without a crate prints a report for `None`; `ledger assign` without
  `--slice` assigns its findings to no CR, closes their real lineage entry as `REASSIGNED` and
  commits; `ledger sync --slice <cr>` without `--db-state` runs the full true-up instead; and
  `--db-state` accepts any value.
- **Stale text in `rust-code-health.py`:** its `# Consuming skills:` header says the code-health
  skill is not published yet; its docstring says board transitions mirror into the ledger through
  `schedule_db.set_state` (since CR-MDB-028 the mirror is the operator's `ledger sync`), the ledger's `slice` said to be a ChangeSet-DB
  CR id; the CR filed with `python-crucible.py`, where a rust project's client is `rust-crucible.py`.

The tools call external programs: `git` (all three), `tar` (`lift-lint`), `dot` (the crate map's
render), `cargo-machete` (the `deps` mode) and `cargo` (`lift-lint`). A development machine may have
all of them; a clean runner may have none. Coverage measures a tool run as a subprocess only when the
child inherits the test process's environment, which carries the coverage configuration.

## Steps

### §S1 — `rust-crate-map.py`: tests, and the workspace manifest

1. Behaviour tests over synthetic Cargo workspaces built in temp directories, each tool run as a
   subprocess of the test interpreter.
2. They cover: per-file line classification (code, comment, blank, `#[cfg(test)]`-gated code);
   attribute signals counted only as a real attribute at the start of a code line, never inside a
   comment, with `TODO`/`FIXME` counted in comments too; workspace-internal prod, dev and build
   dependency edges; fan-in; totals; the JSON and markdown outputs; the Graphviz source with and
   without `crate_map.toml` (clusters, aggregates, `omit_edges_into`, the empty-crate and dead-code
   markers); rendering with `dot` present, `dot` absent, `dot` failing, and `--no-render`; the default
   `--out` and `--name`.
3. **The workspace manifest is parsed as TOML** (stdlib `tomllib`), root and members alike. The member
   set follows Cargo: each `[workspace] members` entry is a path or a glob pattern relative to the
   root; `[workspace] exclude` entries are removed; `default-members` does not change the set; a root
   manifest that also has a `[package]` table makes the root package a member. A member's package name
   is its manifest's `[package] name`.
4. **A malformed workspace is refused with a message, never a traceback:** no root `Cargo.toml`, a
   root manifest that is not valid TOML, no `[workspace]` table, a resolved member (a path or a glob
   match) with no `Cargo.toml`, a member manifest with no `[package] name`.
5. **A failed render is reported:** `dot` exiting non-zero leaves the JSON, markdown and Graphviz
   files written and exits non-zero with an `error:` line, never a traceback.
6. Each scanner keeps its own manifest reading: no new file is added under `scripts/`, whose set of
   deployed tool scripts is fixed.

### §S2 — `rust-dead-scan.py`: tests, its report and `lift-lint`

1. Behaviour tests for every mode, run as a subprocess:
   - `inventory`: `allow`/`expect(dead_code)` and `deprecated` sites; the reason clause and its class
     bucket; the `src-prod`, `src-testgated` and `tests-dir` contexts; comment lines skipped; the
     decorated item named as fn/struct/…, field or variant.
   - `pub-scan`: the `dead-pub`, `test-coat` and `internal-only` tiers; a cross-crate reference
     clearing a candidate; name collisions listed, never flagged; common and short names skipped and
     counted; doc-comment references counted apart.
   - `deps`: `cargo-machete` present, its output parsed into unused deps, and absent, reported as not
     installed; a feature unreferenced, referenced in code, or forwarded by another member; `default`
     ignored.
   - `reconcile`: register present and absent; unregistered `expect` marks; orphaned register entries;
     the count of bare `allow`s.
   - `boundaries`: no rules file; `forbid_deps`; `allow_deps_only`; `member_prefix`; version lockstep;
     hoisting with `min_crates` and `exempt_prefixes`.
   - `hot-path`: no rules file; a `forbid` rule's patterns on production lines; `allow_paths`; the
     boundary marker on the line or the line before; comment and `#[cfg(test)]` lines dropped;
     `require_present` reporting a sanity failure.
   - `lift-lint`: suppressions stripped and counted; the `dead_code` warnings collected from the
     compiler's JSON messages; `check_ok` from the compiler's exit; the scratch copy removed.
2. Mode selection: the default set, an explicit subset, and `--lift-lint` adding its mode.
3. Finding ids are stable: the same tree yields the same ids, and moving an item to another path
   changes its id.
4. The manifest parsing and refusals of §S1.3–§S1.4 hold here too, and both tools resolve the same
   member set from the same manifest.
5. **The markdown report carries a hot-path section** listing each violation and sanity failure, and
   saying when no rules file was found.
6. **The module docstring's default modes are `main()`'s,** with `lift-lint` named as opt-in, and the
   rust memory template (`skills-src/memory-templates/rust-orchestration.md`) lists `hot-path` among
   the modes.
7. **`lift-lint` copies the tree without a shell,** so a project path containing a space works. With
   `cargo` absent, or in a repository with no commit, it exits non-zero with an `error:` line. Its
   scratch copy is removed on every path.

### §S3 — `rust-code-health.py`: tests, the snapshot and the arguments

1. Behaviour tests, run as a subprocess against a temp git repository:
   - `snapshot`: the directory name (date, short sha, phase, slice); the manifest's fields; the
     refusal of an existing snapshot; a sub-tool failure; the config files seeded; the living copies
     refreshed; `health/index.json` rebuilt; the dirty-tree warning; the auto-commit staging only the
     snapshot's paths; a `post` snapshot paired with the same slice's latest `pre`, else the latest
     `baseline`, writing `health_delta.md` with each COMPLETED row's `RATIFIED`, `NOT-RATIFIED` or
     `MANUAL` verdict; a `post` with no pair saying so.
   - `query trend`, `query crate <pkg>`, `query delta <a> <b>`, and `query ledger` with and without a
     filter, and with no ledger.
   - `ledger assign`: only `PROPOSED`/`APPROVED` rows assigned; a reassignment closing the old lineage
     entry; unknown ids reported; the commit, and `--no-commit`; no ledger; a non-`cull` `--domain`'s
     file name.
   - `ledger sync --slice <cr> --db-state <state>` for `IN_PROGRESS`, `COMPLETED` (the merge commit
     found from the log when `--commit` is omitted), `ABORTED` and `SUPERSEDED` (findings back in the
     `APPROVED` pool); the no-argument `ledger sync` with no legacy ChangeSet DB reporting it skipped.
2. **A snapshot seeds `hot_path_rules.toml`** with the other three config files, and its totals carry
   the hot-path violation and sanity-failure counts.
3. **A failed snapshot leaves nothing behind:** when a sub-tool fails, the snapshot exits non-zero
   with the sub-tool's stderr and removes the directory it created, so a rerun is not refused.
4. **Snapshots order by creation time:** each manifest records `created`, the UTC time it was taken to
   the second; `health/index.json` and the post/pre pairing order by it, falling back to the directory
   name for a manifest without it.
5. **Missing or invalid arguments are refused with a usage error:** `query crate` without a crate;
   `query delta` without two snapshot names; `ledger assign` without `--slice` or without `--ids`;
   `ledger sync` with `--slice` but no `--db-state`, or `--db-state` but no `--slice`; a `--db-state`
   outside `IN_PROGRESS`, `COMPLETED`, `ABORTED`, `SUPERSEDED`.
6. **The header and the module docstring are current:** the `# Consuming skills:` header names the
   code-health skill as published, keeping the header's `Owner:` / `Consuming skills:` form; a board
   transition reaches the ledger only through the operator's `ledger sync`; the ledger's `slice` is the CR id on
   the Crucible board; the CR is filed with `rust-crucible.py cr-plan`. `cr-plan` and `ledger assign`
   stay within the docstring's first 40 lines, which `tests/test_worktree_flow_dbless.py` reads.

### §S4 — Hermetic, measured, isolated

1. **Every tool run inherits the test process's environment,** overriding only `PATH` and the git
   variables of §S4.3, so coverage measures it.
2. **The external programs are the test's choice, never the host's.** `cargo`, `cargo-machete` and
   `dot` are stand-ins written with `tests/_helpers.py`'s `write_executable`, present or absent per
   case. A test that needs a program absent builds a `PATH` from a directory holding links to `git`
   and `tar` alone. The `cargo-machete` stand-in replays the output shape of the real tool (0.9.2: a
   `<package> -- <path>/Cargo.toml:` line, then tab-indented dependency names, exit 1).
3. **Git is isolated.** One helper in `tests/_helpers.py` builds a real git repository in a temp
   directory: its identity and `commit.gpgsign=false` are written to the repository's own config, and
   every git call in it, the tools' own commits included, runs with the host's global and system git
   configuration excluded. It can make a `--no-ff` merge commit.
4. **No test writes into the repository.** Every tool run has a temp directory as its working
   directory, or pins `--project-dir` and `--out` to temp directories.

## Acceptance Criteria

1. **AC1 — crate map.** Each §S1.2 behaviour has a test that runs `scripts/rust-crate-map.py` as a
   subprocess and asserts its output files' content.
2. **AC2 — members.** For a root `Cargo.toml` with `[package] name = "root"`,
   `default-members = ["crates/alpha"]` on a line before `members`, a commented-out `# members = …`
   line, `members = ["crates/*"]` and `exclude = ["crates/skip"]`, over `crates/alpha`, `crates/beta`
   and `crates/skip` (each with a `Cargo.toml`), both `rust-crate-map.py` and `rust-dead-scan.py` exit
   0 and report exactly the packages `root`, `alpha` and `beta`.
3. **AC3 — malformed workspace.** For each of the five §S1.4 cases, a glob matching a directory with
   no `Cargo.toml` included, both tools exit non-zero, write a stderr line starting `error:` that names
   the file or key, and print no `Traceback`.
4. **AC4 — failed render.** With a `dot` stand-in that exits 1, `rust-crate-map.py` exits non-zero
   with an `error:` line and no `Traceback`, and its JSON, markdown and Graphviz files exist.
5. **AC5 — dead-scan modes.** Each §S2.1 case has a test that runs `scripts/rust-dead-scan.py` as a
   subprocess and asserts `dead_scan_report.json`'s content; §S2.2 and §S2.3 have their own tests.
6. **AC6 — hot-path in the markdown.** With a `hot_path_rules.toml` carrying one violated `forbid`
   rule and one unmet `require_present` rule, `dead_scan_report.md` has a hot-path section naming the
   violation's path and line and the sanity failure's rule id; without the file, the section says no
   rules file was found.
7. **AC7 — the modes, stated.** The modes `rust-dead-scan.py`'s module docstring names as its default
   equal `main()`'s default `modes` list, and it names `lift-lint` as opt-in;
   `skills-src/memory-templates/rust-orchestration.md` names `hot-path` among the modes.
8. **AC8 — `lift-lint`.** With a `cargo` stand-in reporting one `dead_code` warning, `lift-lint` on a
   project at a path containing a space exits 0 and reports that warning. With `cargo` absent, and in
   a repository with no commit, it exits non-zero with an `error:` line and no `Traceback`. In all
   three cases no `dead-scan-lift-*` scratch directory remains.
9. **AC9 — health tool.** Each §S3.1 behaviour has a test that runs `scripts/rust-code-health.py` as
   a subprocess against a temp git repository and asserts the files, ledger rows, commits or output
   it names.
10. **AC10 — snapshot rules.** A snapshot taken with `hot_path_rules.toml` in `--out` copies it into
    the snapshot directory, its dead-scan report carries that file's violations, and `snapshot.json`'s
    `totals` carry `hot_path_violations` and `hot_path_sanity_failures`.
11. **AC11 — failed snapshot.** When a sub-tool fails, `snapshot` exits non-zero with the sub-tool's
    stderr, its snapshot directory does not exist afterwards, and a rerun after the cause is fixed
    succeeds on the same commit and day.
12. **AC12 — snapshot order.** `snapshot.json` carries `created` (UTC, `YYYY-MM-DDTHH:MM:SSZ`). With
    two `pre` snapshots of one slice taken the same day, the later one's short sha sorting first by
    name, a `post` snapshot of that slice pairs with the later one, and `health/index.json` lists them
    in creation order.
13. **AC13 — arguments.** Each §S3.5 case exits 2 with an argparse usage error, prints no
    `Traceback`, and leaves the ledger file byte-identical and the repository with no new commit.
14. **AC14 — health header and docstring.** `rust-code-health.py`'s `# Consuming skills:` header
    does not say the code-health skill is unpublished; its module docstring does not name
    `schedule_db.set_state`, `ChangeSet-DB` or `python-crucible.py`; it names `ledger sync` as the way a board transition reaches the ledger and
    `rust-crucible.py cr-plan` as the filing step; `tests.test_worktree_flow_dbless` and
    `tests.test_tooling_adoption` stay green.
15. **AC15 — hermetic.** Every new test passes the same way on a host with none of `cargo`,
    `cargo-machete` and `dot` and on a host with all three: each test asserts whether its stand-in
    ran, and no test spawns a real `cargo`, `cargo-machete` or `dot`. Every tool run's environment is
    the test process's environment with only `PATH` and git's configuration variables changed. After
    the full suite, `git status --porcelain` in the repository is unchanged by the run.
16. **AC16 — git helper.** The real-git-repository helper of §S4.3 is defined once, in
    `tests/_helpers.py`; every new test that needs a repository uses it; a tool's own commit in such a
    repository succeeds on a host with no global git identity.
17. **AC17 — coverage.** Under the pre-merge gate's coverage run, each of `scripts/rust-crate-map.py`,
    `scripts/rust-dead-scan.py` and `scripts/rust-code-health.py` measures at least 85% of its
    statements, and the total count of covered lines exceeds the `Coverage baseline:` line's figure in
    `AGENTS.md`.

## Non-goals

- `scripts/schedule_db.py` gets no tests (PRD D5), and the no-argument `ledger sync` is tested only
  where no legacy ChangeSet DB exists.
- A single-package Cargo project with no `[workspace]` table: AC3 refuses it.
- Dependency tables beyond the `name = …` / `name.workspace = …` line forms (`[dependencies.name]`
  tables, target-specific dependencies) in the crate map's edges and the boundary rules.
- The test modules that build their own git repositories today keep their own builders.
- `worktree-flow.py` and `skill-release-gate.py` are CR-MDB-081's.
