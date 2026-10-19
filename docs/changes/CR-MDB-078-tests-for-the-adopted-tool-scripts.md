# CR-MDB-078 — Tests for the rust health tools, and the defects they find

**Status:** PENDING — spec drafted 2026-10-19 from the gap analysis; spec pre-review next.
**Type:** tests + fixes (the deployed rust health tools)
**Priority:** P1 — release 1.0.0, wave 2; after CR-MDB-073.
**Depends on:** CR-MDB-073, whose gate measures the result. The board is authoritative: read `queue`.
**Labels:** tests, coverage, scripts, rust
**Design reference:** PRD D5 (coverage of the package and every script, a no-drop ratchet);
`skills-src/code-health/SKILL.md` (what the tools are for).

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

- Both scanners read `[workspace] members` literally. Cargo's glob form (`members = ["crates/*"]`)
  makes each of them stop with a `FileNotFoundError` traceback.
- A snapshot copies `crate_map.toml`, `dead_code_register.toml` and `boundary_rules.toml` into its
  directory but not `hot_path_rules.toml`. Its dead-scan runs with the snapshot directory as `--out`,
  so a snapshot never applies the hot-path rules, and its totals carry no hot-path counts.
- `rust-dead-scan.py` writes hot-path results to the JSON report only: the markdown report has no
  hot-path section. Its docstring lists the default modes as four; `main()` runs six.
- `rust-dead-scan.py --lift-lint` copies the tree through a shell pipeline with the project path
  unquoted, so a project path containing a space fails.
- `rust-code-health.py query delta` without its two snapshot names stops with a `TypeError`
  traceback; `query crate` without a crate name prints a report for `None`.
- `rust-code-health.py`'s docstring still says every board transition mirrors into the ledger through
  `schedule_db.set_state`; since CR-MDB-028 the mirror is the operator's `ledger sync`.

Each tool calls external programs: `git` (all three), `dot` (crate map), `cargo-machete` (the `deps`
mode) and `cargo` (the `lift-lint` mode). A development machine may have all of them; a clean runner
may have none.

## Steps

### §S1 — `rust-crate-map.py`: tests, and member resolution

1. Behaviour tests over synthetic Cargo workspaces built in temp directories, each tool run as a
   subprocess of the test interpreter so subprocess coverage measures it.
2. They cover: per-file line classification (code, comment, blank, `#[cfg(test)]`-gated code);
   attribute signals counted only as a real attribute at the start of a code line, never inside a
   comment, with `TODO`/`FIXME` counted in comments too; workspace-internal prod, dev and build
   dependency edges; fan-in; totals; the JSON and markdown outputs; the Graphviz source with and
   without `crate_map.toml` (clusters, aggregates, `omit_edges_into`, the empty-crate and dead-code
   markers); rendering with `dot` present, `dot` absent, and `--no-render`; the default `--out` and
   `--name`.
3. **Member resolution follows Cargo:** a `members` entry may be a glob pattern, matched against
   directories under the workspace root that hold a `Cargo.toml`; `exclude` entries are removed from
   the result.
4. **A malformed workspace is refused with a message, never a traceback:** no root `Cargo.toml`, no
   `[workspace] members`, a member directory with no `Cargo.toml`, a member `Cargo.toml` with no
   `[package]` `name`.

### §S2 — `rust-dead-scan.py`: tests, and its report

1. Behaviour tests for every mode, run as a subprocess:
   - `inventory`: `allow`/`expect(dead_code)` and `deprecated` sites; the reason clause and its
     class bucket; the `src-prod`, `src-testgated` and `tests-dir` contexts; comment lines skipped;
     the decorated item named as fn/struct/…, field or variant.
   - `pub-scan`: the `dead-pub`, `test-coat` and `internal-only` tiers; a cross-crate reference
     clearing a candidate; name collisions listed, never flagged; common and short names skipped and
     counted; doc-comment references counted apart.
   - `deps`: `cargo-machete` present (its output parsed into unused deps) and absent (reported as not
     installed); a feature unreferenced, referenced in code, or forwarded by another member; `default`
     ignored.
   - `reconcile`: register present and absent; unregistered `expect` marks; orphaned register
     entries; the count of bare `allow`s.
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
4. The member resolution and malformed-workspace refusal of §S1.3–§S1.4 hold here too, and both
   tools resolve the same member set from the same manifest.
5. **The markdown report carries a hot-path section** listing each violation and sanity failure, and
   "no rules file" when there is none. The module docstring names the six default modes.
6. **`lift-lint` copies the tree without a shell,** so a project path containing a space works.

### §S3 — `rust-code-health.py`: tests, and the snapshot's rules

1. Behaviour tests, run as a subprocess against a temp git repository:
   - `snapshot`: the directory name (date, short sha, phase, slice); the manifest's fields; the
     refusal of an existing snapshot; a sub-tool failure exiting non-zero with the sub-tool's stderr;
     the config files seeded; the living copies refreshed; `health/index.json` rebuilt; the dirty-tree
     warning; the auto-commit staging only the snapshot's paths; a `post` snapshot paired with the
     same slice's `pre`, else the latest `baseline`, writing `health_delta.md` with each COMPLETED
     row's `RATIFIED`, `NOT-RATIFIED` or `MANUAL` verdict; a `post` with no pair saying so.
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
3. **`query crate` and `query delta` refuse missing arguments** with a usage error, never a traceback
   or a report for `None`.
4. The module docstring states that a board transition reaches the ledger only through the
   operator's `ledger sync`.

### §S4 — Hermetic, fast, shared

1. Every external program the tools call except `git` is a test stand-in on a `PATH` the test builds:
   `cargo`, `cargo-machete` and `dot`, present or absent per case. No test depends on what the host
   has installed, starts a real build, or reaches a network.
2. Real `git` repositories are built in temp directories by one shared helper in `tests/_helpers.py`,
   which the two modules that already build their own adopt.
3. The synthetic-workspace builder lives in `tests/_helpers.py` too, if more than one module uses it.

## Acceptance Criteria

1. **AC1 — crate map.** Each §S1.2 behaviour has a test that runs `scripts/rust-crate-map.py` as a
   subprocess and asserts its output files' content.
2. **AC2 — member globs.** For a workspace whose root `Cargo.toml` declares
   `members = ["crates/*"]` and `exclude = ["crates/skip"]` over `crates/alpha`, `crates/beta` and
   `crates/skip`, both `rust-crate-map.py` and `rust-dead-scan.py` exit 0 and report exactly the
   packages of `crates/alpha` and `crates/beta`.
3. **AC3 — malformed workspace.** For each of the four §S1.4 cases, both tools exit non-zero, write a
   single stderr line starting `error:` that names the missing file or key, and print no
   `Traceback`.
4. **AC4 — dead-scan modes.** Each §S2.1 case has a test that runs `scripts/rust-dead-scan.py` as a
   subprocess and asserts `dead_scan_report.json`'s content; §S2.2 and §S2.3 have their own tests.
5. **AC5 — hot-path in the markdown.** With a `hot_path_rules.toml` carrying one violated `forbid`
   rule and one unmet `require_present` rule, `dead_scan_report.md` has a hot-path section naming the
   violation's path and line and the sanity failure's rule id; without the file, the section says no
   rules file was found.
6. **AC6 — docstring modes.** `rust-dead-scan.py`'s module docstring names exactly the six modes
   `main()` runs by default.
7. **AC7 — lift-lint path.** `rust-dead-scan.py lift-lint` on a project at a path containing a space,
   with a `cargo` stand-in reporting one `dead_code` warning, exits 0 and reports that warning.
8. **AC8 — health tool.** Each §S3.1 behaviour has a test that runs `scripts/rust-code-health.py` as
   a subprocess against a temp git repository and asserts the files, ledger rows, commits or output
   it names.
9. **AC9 — snapshot rules.** A snapshot taken with `hot_path_rules.toml` in `--out` copies it into the
   snapshot directory, its dead-scan report carries that file's violations, and `snapshot.json`'s
   `totals` carry `hot_path_violations` and `hot_path_sanity_failures`.
10. **AC10 — query arguments.** `query crate` with no crate and `query delta` with fewer than two
    snapshot names exit 2 with an argparse-style usage error and print no `Traceback`.
11. **AC11 — health docstring.** `rust-code-health.py`'s module docstring no longer names
    `schedule_db.set_state`, and names `ledger sync` as the way a board transition reaches the ledger.
12. **AC12 — hermetic.** Every new test passes on a host with none of `cargo`, `cargo-machete` and
    `dot` installed and on a host with all three, with the same results; no test spawns a real
    `cargo` or `dot`; the suite's hermeticity gates (`tests/test_suite_hermeticity.py`) stay green.
13. **AC13 — shared helpers.** The real-git-repository helper is defined once, in `tests/_helpers.py`,
    and `tests/test_worktree_flow_dbless.py` and `tests/test_toon_codec.py` use it instead of their
    own copies.
14. **AC14 — coverage.** Under the pre-merge gate's coverage run, each of `scripts/rust-crate-map.py`,
    `scripts/rust-dead-scan.py` and `scripts/rust-code-health.py` measures at least 85% of its
    statements, and the total rises above the `Coverage baseline:` line in `AGENTS.md`.

## Non-goals

- `scripts/schedule_db.py` gets no tests (PRD D5), and the no-argument `ledger sync` is tested only
  where no legacy ChangeSet DB exists.
- A single-package Cargo project with no `[workspace]` table stays out of scope: AC3 refuses it.
- `worktree-flow.py` and `skill-release-gate.py` are CR-MDB-081's.
