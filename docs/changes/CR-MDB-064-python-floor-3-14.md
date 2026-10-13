# CR-MDB-064 — The published Python floor is 3.14

**Status:** PENDING (filed 2026-10-13; gap analysis 2026-10-13)
**Type:** feature (packaging metadata, installer preflight, deploy, docs, tests)
**Priority:** P1 — release 1.0.0, wave 2.
**Depends on:** none (board-authoritative: read `queue`)
**Labels:** packaging, python, installer, deploy, release
**Design reference:** DN-multi-harness-deploy-model §D22 (with its recorded-interpreter ruling); PRD D10
(the installer detects and records, `init` only reads).

## Context

`modelb-axi` declares `requires-python = ">=3.11"`, with the classifiers 3.11, 3.12 and 3.13 and none
for 3.14 (`pyproject.toml`). Development runs on 3.14. The floor becomes 3.14 from release 1.0.0.

The hook scripts (`hooks-src/scripts/*`) and the python tool scripts (`scripts/*.py` with a shebang)
start `#!/usr/bin/env python3`. The Pi hook shim and the skills run the deployed copies directly
(`~/.agents/scripts/worktree-flow.py status`), so they run on whatever `python3` comes first on `PATH`,
not on `modelb-axi`'s interpreter (uv runs the package on an interpreter that meets
`requires-python`). On a long-term-support distribution that `python3` is often 3.11 or 3.12. The
installer probes `python3` for presence only (`modelb_axi/requirements.py`, `modelb_axi/toolchains.py`);
nothing checks its version. Sandesh's probe already carries a version floor (`SANDESH_VERSION_FLOOR`,
reported as `outdated` with a remediation), the pattern this CR follows.

The deploy step (`deploy._deploy_file`) deploys a script byte-for-byte and records the source's hash:
a deployed file that differs from its source reads as hand-modified on the next run.

## Scope

### §S1 — The floor in the published metadata

`pyproject.toml` declares `requires-python = ">=3.14"`; its version classifiers are
`Programming Language :: Python :: 3`, `… :: 3 :: Only` and `… :: 3.14`, and none below 3.14.

### §S2 — The installer records an interpreter that meets the floor

Preflight finds the interpreter the scripts will run on:
- `python3` on `PATH`, when its version is 3.14 or newer;
- else the interpreter `uv python find 3.14` reports;
- else none: preflight fails before any write, naming `uv python install 3.14` as the remediation.

The `python3` capability's verdict reports the interpreter found and its version (or, below the
floor with no 3.14 available, `outdated` with the remediation, as Sandesh's probe does). The interpreter's
absolute path is recorded in `install.toml`, and a re-run probes and records it again.

### §S3 — The deploy step writes the recorded interpreter into the scripts

For every deployed hook script and tool script whose first line is `#!/usr/bin/env python3`, the
deployed copy's first line is `#!<recorded interpreter>`; every other byte is the source's. A script
without that shebang (`gate-lock.sh`, `toon.py`, `schedule_db.py`) deploys byte-for-byte as today. The
manifest records the hash of the bytes actually deployed, and the unchanged / hand-modified /
unmanaged decisions and the prune compare against those bytes: a re-run with the same interpreter
writes nothing; a re-run that records a different interpreter re-renders every managed script it has
not detected as hand-modified.

### §S4 — Every documented invocation runs a deployed script directly

The `code-health` skill's invocations of `rust-code-health.py` and `rust-dead-scan.py`, and
`skill-release-gate.py`'s own usage line, run the deployed script directly
(`~/.agents/scripts/<script> …`), never through `python3`. No skill, contract, template or script
invokes a deployed script through `python3`.

### §S5 — Docs

- **`AGENTS.md`:** Python ≥ 3.14 (Runtime/Tooling); the pre-merge gate has no second-interpreter run;
  the skip list's example of "an interpreter without the `build` frontend" no longer names
  `python3.11`.
- **`docs/install-guide.md`:** the `python3` requirement reads as a Python 3.14 interpreter — `python3`
  on `PATH`, else one uv provides — with `uv python install 3.14` as the remediation; its sample
  preflight lines match §S2's verdict.

### §S6 — Code and text kept only for older interpreters

- The `< 3.11` import fallbacks are removed: `tomli` in `scripts/skill-release-gate.py`,
  `tomllib = None` and its branch in `scripts/rust-crate-map.py`.
- The comments that describe 3.11/3.12 behaviour (`tests/test_ambient_manifest_discovery.py`,
  `hooks-src/scripts/ambient-board-status`) state the behaviour on the floor; the defensive code and the
  hardening tests stay.
- `tests/test_suite_hygiene.py`'s note that `tomllib` is stdlib names the 3.14 floor.

### §S7 — The gates this change moves

Each is updated in the cycle that changes what it pins:
- `tests/test_package_publishing.py`: `Requires-Python` is `>=3.14`; the classifier rule requires the
  3.14 classifier and refuses any below 3.14 (`classifier_faults`, `PYTHON_311_CLASSIFIER`, the sample
  classifier sets).
- The installer and deploy tests that assume a deployed script is byte-identical to its source.
- The preflight tests of the `python3` probe, and the `install.toml` serialization tests.
- `tests/test_code_health_skill.py` and every test string that pins `python3 ~/.agents/scripts/…`.
- `AGENTS.md`'s module count and baselines are re-measured.

## Acceptance criteria

- [ ] **The built wheel's metadata** has `Requires-Python: >=3.14` and the classifiers of §S1, no
      version classifier below 3.14.
- [ ] **Preflight** records `python3` on `PATH` when it is ≥ 3.14; else the `uv python find 3.14`
      interpreter; else fails before any write, naming `uv python install 3.14`. Each case is proved
      with a stubbed `python3` and `uv` in a sandbox; the verdict names the interpreter and version.
- [ ] **`install.toml`** records the interpreter's absolute path; a second run records it again.
- [ ] **Every deployed python-shebang hook and tool script** starts `#!<recorded interpreter>` and is
      otherwise byte-identical to its source; `gate-lock.sh`, `toon.py` and `schedule_db.py` are
      byte-identical; each deployed script keeps its mode.
- [ ] **The manifest** records the deployed bytes' hash; a re-run with the same interpreter writes
      nothing; a re-run with a different interpreter re-renders the managed scripts; a hand-edited
      deployed script is still detected and skipped without `--force-managed`; the prune still removes
      a script no longer shipped.
- [ ] **No skill, contract, template or script** invokes a deployed script through `python3`; the
      `code-health` and `skill-release-gate.py` invocations run the script directly.
- [ ] **`AGENTS.md`** and **`docs/install-guide.md`** state the 3.14 floor, the interpreter and its
      remediation as §S5 says, with no second-interpreter run and no `python3.11` example.
- [ ] **`scripts/skill-release-gate.py`** has no `tomli` fallback; **`scripts/rust-crate-map.py`** has
      no `tomllib = None` fallback or branch; the 3.11/3.12 comments state the floor's behaviour.
- [ ] **Gates that hold:** every gate §S7 lists, updated as it says; the full suite through the client
      with real `HOME` and with an empty `HOME` (the temp home empty afterwards); `generator/build.py
      --check`; `AGENTS.md`'s module count and baselines re-measured.

## Non-goals

- The Crucible clients' interpreter (CR-MDB-063 probes the python client's test interpreter).
- Rewriting the shebang of a project's own scripts.
- Model B's own redeploy: the user re-runs the installer after this CR merges, as after any CR that
  changes deployed scripts (DN §D21 amendment).
- Rewriting closed specs, `archive/` or `audits/`.
