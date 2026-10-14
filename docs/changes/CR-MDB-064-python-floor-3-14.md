# CR-MDB-064 — The published Python floor is 3.14

**Status:** COMPLETED (filed 2026-10-13; gap analysis and pre-review 2026-10-13)
**Type:** feature (packaging metadata, installer preflight, deploy, docs, tests)
**Priority:** P1 — release 1.0.0, wave 2.
**Depends on:** none (board-authoritative: read `queue`)
**Labels:** packaging, python, installer, deploy, release
**Design reference:** DN-multi-harness-deploy-model §D22 (with its recorded-interpreter rulings); PRD D10
(the installer detects and records, `init` only reads).

## Context

`modelb-axi` declares `requires-python = ">=3.11"`, with the classifiers 3.11, 3.12 and 3.13 and none
for 3.14 (`pyproject.toml`). Development runs on 3.14; no code uses or needs a feature newer than 3.11.
The floor becomes 3.14 from release 1.0.0.

The hook scripts (`hooks-src/scripts/*`) and the python tool scripts (`scripts/*` with a shebang)
start `#!/usr/bin/env python3`. The Pi hook shim (`hooks.py`) spawns the deployed script directly, and
the skills run the deployed copies directly (`~/.agents/scripts/worktree-flow.py status`) — except the
`code-health` skill and `skill-release-gate.py`'s usage, which run them through `python3`. So the
scripts run on whatever `python3` comes first on `PATH`, not on `modelb-axi`'s interpreter.

The installer's `python3` row (`requirements.REQUIREMENTS`) is `recommended`, probed for presence
only (`probe: "path"`), and `run_preflight` returns `(exit, deps, capabilities)`. Sandesh's probe
already carries a version floor (`SANDESH_VERSION_FLOOR`, verdict `outdated` with a remediation).
`init` reads verdicts in the vocabulary `detected`, `installed`, `absent`, `outdated`
(`scaffold._tool_state`); anything else renders `unknown`.

The deploy step (`deploy._deploy_file`) deploys a script byte-for-byte and records the source's hash;
`deploy.deployed_freshness` (behind the `already_installed` envelope) calls a file `stale` when its
source's hash differs from the recorded one. Measured: `uv python find 3.14` returns an active or
local virtual environment (with or without `--no-project`); only `--system` skips it; and `3.14`
matches 3.14.x only.

## Scope

### §S1 — The floor in the published metadata

`pyproject.toml` declares `requires-python = ">=3.14"`; its version classifiers are
`Programming Language :: Python :: 3`, `… :: 3 :: Only` and `… :: 3.14`, and none below 3.14.

### §S2 — The installer finds and records an interpreter that meets the floor

**The probe.** The `python3` row of `REQUIREMENTS` becomes `required`, with a new probe kind,
`interpreter`, and the remediation `uv python install 3.14`. It runs after the `uv` dependency check.
Candidates, in order:
1. `python3` on `PATH`;
2. the interpreter `uv python find --system '>=3.14'` reports.

A candidate is accepted when it is an existing executable that reports a version ≥ 3.14 and is not a
virtual environment (`sys.prefix == sys.base_prefix`), all read by running it. The path recorded is
the candidate's absolute path as found (`which`, or uv's report), not its link resolved. A path
containing whitespace, or longer than the kernel's shebang limit, is rejected.

**The verdict.** `[capabilities].python3` keeps the four-value vocabulary: `detected` when a candidate
is accepted; `outdated` when `python3` exists below the floor and no candidate is accepted; `absent`
when no `python3` and no candidate exist. A named stderr line reports the result —
`python3: <path> (<version>)` when accepted, or `python3=outdated|absent — <reason>; install it with:
uv python install 3.14`.

**The refusal.** With no accepted candidate, preflight fails before any write, whatever the flags:
`--allow-missing-capabilities` does not override it. A run with no `--target-root` (no deploy, no
`install.toml`) still probes and still refuses.

**The record.** `run_preflight` returns the accepted interpreter alongside its existing results, and
`install.toml` records it as `[install] python = "<absolute path>"`; it round-trips through
`serialize_install_toml` / `load_install_toml`. A re-run probes and records it again.

`init` needs no interpreter: the hooks run the deployed copies, and `init` reads only the verdict.
The `stack python: python3=` probe and its `xmlrunner`/`coverage` import checks stay on the `PATH`
`python3` (the test interpreter is CR-MDB-063's; it consumes the recorded `[install] python`).

### §S3 — Rendering: the recorded interpreter in the deployed scripts

One rendering function produces a script's deployed bytes: for a hook or tool script whose first line
is `#!/usr/bin/env python3`, the first line becomes `#!<recorded interpreter>` and every other byte is
the source's; any other script (`gate-lock.sh`, `toon.py`, `schedule_db.py`) renders to its source
bytes. Both `deploy_assets` and `deployed_freshness` use it:
- **Deploy.** The manifest records the hash of the rendered bytes; the unchanged / hand-modified /
  unmanaged decisions and the prune compare against them; each deployed script keeps its source's
  mode. The first run after this CR finds each script identical to its recorded source hash, so it is
  managed and is re-rendered. A re-run with the same interpreter writes nothing; one with a different
  interpreter re-renders every managed script not detected as hand-modified. With no `install.toml`, a
  script is adopted only when it equals the bytes rendered with the current interpreter — otherwise it
  is reported `unmanaged`, as intended.
- **Freshness.** `deployed_freshness` compares the recorded hash with the source rendered with the
  recorded interpreter, so a fresh install reports every list empty. An install with no recorded
  interpreter (made before this CR) reports its python-shebang scripts `stale`. A recorded interpreter
  that no longer exists or reports a version below the floor is reported, naming the re-install
  command.

### §S4 — Deployed scripts are run directly

"Deployed script" means Model B's hook and tool scripts in `~/.agents/hooks/scripts/` and
`~/.agents/scripts/`; Crucible's clients are not. The `code-health` skill's invocations of
`rust-code-health.py` and `rust-dead-scan.py`, and `skill-release-gate.py`'s own usage line, run the
deployed script directly (`~/.agents/scripts/<script> …`). The texts that say a deployed
`worktree-flow.py` runs "under a bare `python3`" — `contracts/crucible-envelope.md` and the docstring of
`modelb_axi/toon.py` (and its generated copy `scripts/toon.py`, regenerated) — state that it runs on the
recorded interpreter. The fixture strings in `test_skill_bundle_guards` and `test_client_role_contract`
that use `python3 ~/.agents/scripts/rust-code-health.py` as input to a flag detector stay.

### §S5 — Docs

- **`AGENTS.md`:** Python ≥ 3.14 (Runtime/Tooling); a sentence that the pre-merge gate runs one
  interpreter, the floor; the skip list's "interpreter without the `build` frontend" example names no
  `python3.11`. The `build`-frontend example rule was retired by CR-MDB-069 §S3, 2026-10-14.
- **`docs/install-guide.md`:** the `python3` requirement reads as a Python 3.14 interpreter — `python3` on
  `PATH`, else one uv provides — with `uv python install 3.14` as the remediation; `python3` leaves the
  list of tools needing elevated privileges; its sample preflight lines match §S2's stderr line.

### §S6 — Code and text kept only for older interpreters

- The `< 3.11` import fallbacks are removed: `tomli` in `scripts/skill-release-gate.py`; `tomllib = None`
  and every branch on it in `scripts/rust-crate-map.py` and `scripts/rust-dead-scan.py`
  (`mode_boundaries`, its hot-path rule checker, `mode_reconcile`).
- The comments describing 3.11/3.12 behaviour (`tests/test_ambient_manifest_discovery.py`,
  `hooks-src/scripts/ambient-board-status`) state the behaviour on the floor; the defensive code and
  the hardening tests stay.
- `tests/test_suite_hygiene.py`'s note that `tomllib` is stdlib names the 3.14 floor.

### §S7 — The gates this change moves

Each is updated in the cycle that changes what it pins:
- `tests/test_package_publishing.py`: `Requires-Python` is `>=3.14`; `classifier_faults` requires the
  3.14 classifier and refuses any below 3.14; the sample classifier sets.
- **A shared installer fixture** in `tests/_helpers.py`: a `python3` stub reporting 3.14 that is not a
  virtual environment, and a `uv` stub that answers `python find --system '>=3.14'`. The installer test
  modules run on it: `test_harness_capability_contract` (its `_TABLE`,
  `test_only_dispatch_lean_ctx_sandesh_pi_uv_and_sandesh_are_required`,
  `test_path_probed_rows_are_declared_by_their_probe_kind`), `test_installer_stack_selection`,
  `test_installer_sandesh_requirements`, `test_modelb_pi_worktree_capability`, `test_init_tool_verdicts`,
  `test_installer_prune`, `test_installer_correctness`, `test_installer_assets`, `test_tooling_adoption`,
  `test_sandesh_install`, `test_installer`, and every other module that runs the installer with a
  sandboxed `PATH`. `PathToolsRecordAndWarnTest` follows `python3`'s new `required` policy.
- `tests/test_deployed_asset_freshness.py`: a fresh install reports every list empty with rendered
  scripts.
- The deploy tests that assume a deployed script is byte-identical to its source.
- `tests/test_code_health_skill.py` and every other test string that pins a `python3 ~/.agents/scripts/…`
  invocation in shipped text.
- `generator/build.py --check` (the regenerated `scripts/toon.py`).
- `AGENTS.md`'s module count and baselines are re-measured.

## Acceptance criteria

- [ ] **The built wheel's metadata** has `Requires-Python: >=3.14` and the classifiers of §S1, no version
      classifier below 3.14.
- [ ] **Preflight**, each case proved with stubbed `python3` and `uv` in a sandbox:
      `python3` ≥ 3.14 → `detected`, that path recorded; `python3` below the floor and uv's system 3.14
      found → `detected`, uv's path recorded; `python3` below and none found → `outdated`, refusal;
      no `python3` and none found → `absent`, refusal; a virtual-environment candidate rejected; a
      candidate with whitespace in its path rejected; a 3.15-only machine accepted; the refusal holds
      with `--allow-missing-capabilities` and with no `--target-root`; the stderr line matches §S2.
- [ ] **`install.toml`** has `[install] python = "<absolute path>"`, round-tripping through
      `serialize_install_toml` / `load_install_toml`; `[capabilities].python3` is one of the four
      verdicts; `init`'s capability contract renders `python3` with no `unknown`.
- [ ] **Every deployed python-shebang hook and tool script** starts `#!<recorded interpreter>` and is
      otherwise byte-identical to its source; `gate-lock.sh`, `toon.py` and `schedule_db.py` are
      byte-identical; each keeps its source's mode.
- [ ] **The manifest** records the rendered bytes' hash; the first run after this CR re-renders the
      managed scripts; a re-run with the same interpreter writes nothing; a re-run with a different
      interpreter re-renders them; a hand-edited deployed script is detected and skipped without
      `--force-managed`; the prune still removes a script no longer shipped.
- [ ] **`deployed_freshness`** reports every list empty right after a fresh install; reports
      python-shebang scripts `stale` for an install with no recorded interpreter; reports a recorded
      interpreter that is missing or below the floor, naming the re-install command.
- [ ] **No skill, contract, template, tool script or hook script** runs a deployed script through
      `python3`; a grep gate over `skills-src/`, `contracts/`, `generator/templates/`, `scripts/` and
      `hooks-src/` asserts it; the `code-health` and `skill-release-gate.py` invocations run the script
      directly; `contracts/crucible-envelope.md` and `toon.py` name the recorded interpreter.
- [ ] **`AGENTS.md`** and **`docs/install-guide.md`** state the 3.14 floor, the interpreter and its
      remediation as §S5 says.
- [ ] **`scripts/skill-release-gate.py`** has no `tomli` fallback; **`scripts/rust-crate-map.py`** and
      **`scripts/rust-dead-scan.py`** have no `tomllib = None` fallback or branch; the 3.11/3.12 comments
      state the floor's behaviour.
- [ ] **Gates that hold:** every gate §S7 lists, updated as it says, the installer modules on the
      shared fixture; the full suite through the client with real `HOME` and with an empty `HOME` (the
      temp home empty afterwards); `generator/build.py --check`; `AGENTS.md`'s module count and
      baselines re-measured.

## Non-goals

- The python client's test interpreter and its `xmlrunner`/`coverage` checks (CR-MDB-063).
- The check that a hook's script exists in the deployed store (CR-MDB-062); it says nothing about the
  interpreter.
- Rewriting the shebang of a project's own scripts.
- Model B's own redeploy: the user re-runs the installer after this CR merges (DN §D21 amendment).
- Rewriting closed specs, `archive/` or `audits/`.
