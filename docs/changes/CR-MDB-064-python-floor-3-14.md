# CR-MDB-064 — The published Python floor is 3.14

**Status:** PENDING — **SEED, not the finished spec.** Gap analysis, the design record, the spec and
its pre-review happen in order when this CR starts.
**Type:** refactor (packaging metadata, installer preflight, docs, tests)
**Priority:** P1 — release 1.0.0, wave 2.
**Depends on:** none (board-authoritative: read `queue`)
**Labels:** packaging, python, installer, release
**Design reference:** DN-multi-harness-deploy-model §D22.

## Context

`modelb-axi` declares `requires-python = ">=3.11"` with a 3.11 classifier (`pyproject.toml`), set for
`tomllib`. Development runs on 3.14, and the pre-merge gate needed a second run under a 3.11
interpreter to keep that promise true. The floor becomes 3.14 from release 1.0.0.

## Scope (seed)

1. **`pyproject.toml`:** `requires-python = ">=3.14"` and the classifiers to match.
2. **The installer's preflight** requires the `python3` the hook scripts run under to meet the floor,
   with a remediation — a `closed` hook run by an older interpreter must never block every shell call.
3. **`AGENTS.md`** (Runtime/Tooling, Testing): Python ≥ 3.14; the pre-merge gate has no
   second-interpreter run.
4. **Text and code that exist only for older interpreters:** comments describing 3.11/3.12 behaviour
   (`tests/test_ambient_manifest_discovery.py`, `hooks-src/scripts/ambient-board-status`) and the
   `< 3.11` import fallbacks in `scripts/rust-crate-map.py` and `scripts/skill-release-gate.py` —
   measure each: kept, simplified or removed.
5. **The gates that move:** `tests/test_package_publishing.py` (`Requires-Python`, the classifier
   checks), `tests/test_suite_hygiene.py` (its stdlib note), the installer's python probe tests.

## To measure at gap analysis

- Every consumer of the floor (the generated agents' python mechanics, the install guide, the
  preflight, the published metadata), and whether a 3.14-only feature is already in use.
