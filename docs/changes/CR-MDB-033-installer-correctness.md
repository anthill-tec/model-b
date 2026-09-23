# CR-MDB-033 — Installer correctness: one `target_root`, atomic writes, unmanaged files are never clobbered, manifest always consulted

**Status:** PENDING (filed 2026-09-21 from `audits/2026-09-21-codebase-review-modelb_axi.md` §C/§D)
**Type:** bugfix
**Priority:** P1 — in release 1.0.0, wave 2, **before CR-MDB-025 §S4**. 025's `inbox-analyst.md
byte-identical after --force-managed` AC cannot hold while `_deploy_file` overwrites any
pre-existing same-named file on a first install; and 025's sandboxed integration proof cannot be
trusted while the scaffold compiles wiring against a `[install].target_root` the installer never
writes.
**Depends on:** —
**Labels:** installer, scaffold, config, bugfix
**Phase:** Wave 5 (repo queue) · release 1.0.0 wave 2 (Crucible board)
**Design reference:** `AGENTS.md` ("writes are atomic (temp file + os.replace)"; "idempotence by
sha256 manifest comparison"; "flag > env > default") · DN §D3 ("a file absent from the manifest
is not Model B's") · DN §D9 (asset classes do not retro-deploy) · CR-MDB-014 AC4 (pre-flight
records detection truthfully before remediation) · `audits/…-modelb_axi.md` §C, §D

## Context — measured

| # | Where | Defect |
|---|---|---|
| 1 | `scaffold.py` `_hook_scripts_root` vs the `cli.py` `write_install_toml` call | Scaffold reads `[install].target_root` to locate the deployed hook scripts; the installer writes `version/harnesses/asset_root/tool_scripts_dir` and **never `target_root`**, so scaffold falls back to `Path.home()/.agents/hooks/scripts`. An install made with `--target-root /x` therefore compiles wiring pointing at the real home where nothing was deployed. Two path rules for one store. |
| 2 | `deploy._deploy_file`, the four `hooks.py` emitters, `scaffold._emit_plan` | Only `config.write_install_toml` is atomic. Every deployed asset (`shutil.copyfile`) and every compiled wiring file is written in place; a crash mid-write leaves a truncated managed file whose hash matches neither source nor manifest → permanently "hand-modified", skipped forever. Contradicts AGENTS.md. |
| 3 | `deploy._deploy_file` | Dest exists, differs from src, **not in manifest** → falls through and overwrites. On a first install a pre-existing same-named file is clobbered. Contradicts DN §D3; becomes a data-loss path once `.agents/agents` (025) is deployed beside hand-placed definitions. |
| 4 | `cli.py` deploy stage | `prior_hashes = load_manifest_hashes(home) if reinstall else {}` — manifest protection depends on a flag, not on manifest presence. `MODELB_HOME` at a fresh dir + the same `--target-root` → manifest ignored, everything rewritten. |
| 5 | `scaffold.py` module docstring vs `_emit_plan` | Docstring: "`--dry-run` (and any failure) writes NOTHING". The `--dry-run` half holds; `_emit_plan` writes each file immediately, so a failure mid-plan leaves a partial tree with an `ok:false` envelope. |
| 6 | `scaffold.resolve_harnesses` | Harness ids read from `install.toml` are not validated against the roster (the dev override is), so a stale id reaches the compiler's "not in roster" branch instead of a clear error. |
| 7 | `config._toml_string` / `_toml_value` vs scaffold's writer | Two hand-rolled TOML writers; one escapes, one does not. `_toml_string` misses C0 controls other than `\n\t\r`; `_toml_value` raises on non-strings with no schema check at the call site. |
| 8 | `cli.py` installer flow vs `scaffold.py` | Installer human progress goes to **stdout**; `init` sends it to stderr and reserves stdout for the envelope. |

## Scope

### §S1 — One source of truth for the deployed root
`config.write_install_toml` records `target_root` (the resolved `--target-root`/`MODELB_TARGET_ROOT`/
home) and one per-class dir for each asset class the installer deploys today: `skills_dir`,
`hooks_scripts_dir`, `tool_scripts_dir`. Keys for `.agents/agents` belong to CR-MDB-025, which
creates that asset class.

Scaffold reads `hooks_scripts_dir` directly. When an `install.toml` exists without that key there
is **no** fallback to `Path.home()` and no partial-key heuristic: it raises a named error naming
the missing key and `modelb-axi --reinstall`. `_hook_scripts_root`'s docstring states the new
rule; the "forward-compatible; the v1 installer does not record it" sentence is removed.

Test fixtures follow the contract rather than the contract following the fixtures:
`tests/test_scaffold.py`'s `install.toml` fixture records `hooks_scripts_dir`, as every install
after this CR does; and `tests/test_tooling_adoption.py` locates the tool-scripts dir by its key
name `tool_scripts_dir`, not by sweeping `[install]` for keys matching `/script|tool/`.

### §S2 — Atomic writes everywhere
One helper `modelb_axi/_fsutil.py::atomic_write(path, data: bytes, mode=None)` (tmp in the same
directory + `os.replace`, mode preserved from source for assets), used by `deploy._deploy_file`,
every `hooks.py` emitter, and `scaffold._emit_plan`. `install.toml` mode becomes 0644 (or
documented).

### §S3 — Unmanaged files are skipped, never clobbered
`_deploy_file`: dest exists ∧ differs ∧ not in manifest → **skip**, reported with the warning
`unmanaged: <path> — not Model B's; left untouched (no flag overwrites it)`. This vocabulary is
distinct from the managed hand-modified warning and never appears on that path.

`--force-managed` overwrites managed-but-modified files only; no flag in this CR overwrites an
unmanaged file. The manifest is loaded whenever it exists, not only with `--reinstall`.

### §S4 — Scaffold emission is honest about partial failure
`--dry-run` writes nothing, as today. A failure mid-emission may leave a partial tree; the module
docstring claims only that, and the `init` failure envelope lists exactly the files written
before the failure. Emission is not staged through a temp dir.

### §S5 — Validation and hygiene
Validate `install.toml` harness ids against the roster like the override; single TOML writer
(`config._toml_string` used by scaffold; C0/DEL escaped as `\uXXXX`; schema assertion at
`serialize_install_toml`); installer human lines to stderr; the `deps:` line keeps both its
pre-remediation and post-install emissions (CR-MDB-014 AC4); docstring citations name the DN
file; "Vercel store" → "shared store".

## Acceptance criteria

- [ ] Install to `--target-root /tmp/x` then `init` a project: the compiled `.pi/extensions/*.ts`
      reference `/tmp/x/.agents/hooks/scripts/…`, never `~/.agents` — round-trip test.
- [ ] `install.toml` carries `target_root`, `skills_dir`, `hooks_scripts_dir` and
      `tool_scripts_dir`; an `install.toml` missing `hooks_scripts_dir` makes scaffold raise an
      error naming the key and `modelb-axi --reinstall` — no home fallback, no partial-key rule.
- [ ] `tests/test_scaffold.py`'s `install.toml` fixture records `hooks_scripts_dir`, and every
      real-`init` test using it passes under the strict §S1 rule.
- [ ] `tests/test_tooling_adoption.py` asserts the tool-scripts location through the key named
      `tool_scripts_dir`; the presence of `hooks_scripts_dir` in `[install]` does not trip it.
- [ ] Killing the process between tmp-write and rename leaves the destination untouched —
      asserted by monkeypatching `os.replace` to raise and checking the prior file is intact.
- [ ] First install into a root that already holds a foreign `<target-root>/.agents/scripts/gate-lock.sh`:
      the file is byte-identical afterwards; the run reports it with the `unmanaged:` warning; a
      second run with `--force-managed` still leaves it byte-identical.
- [ ] A managed file hand-modified after install is skipped without `--force-managed` and
      overwritten with it, and neither run reports it with the `unmanaged:` wording — asserted in
      the existing `tests/test_installer.py` tests for this behaviour, not in duplicates.
- [ ] Without `--reinstall`, a second run over the same root reports every managed file
      unchanged (manifest consulted).
- [ ] `init` with a mid-plan failure: the envelope lists exactly the files written; `--dry-run`
      still writes nothing.
- [ ] `install.toml` listing a non-roster harness id fails fast with the id named.
- [ ] Every human progress line in `modelb_axi/cli.py` is written with `file=sys.stderr`;
      stdout from an installer run contains no human prose (asserted by capturing both streams).
      The `deps:` line is emitted before remediation and again after a Sandesh install.
- [ ] Both TOML serialisations go through `config._toml_string`; a value containing `\x1b`
      round-trips through `tomllib`.

## Estimated size

~150 lines across `config.py`, `deploy.py`, `scaffold.py`, `cli.py`, `hooks.py`, one new helper
module, ~12 tests. Small–medium.

## Risk

- Existing installs carry manifests without `hooks_scripts_dir`; §S1's named error points at the
  remedy. Upgrade note for the release ritual (`skills-src/git-workflow/SKILL.md` §Releases).
- Changing first-install semantics (skip unmanaged) may surprise a user who expected a takeover;
  the warning says no flag overwrites the file, and a future `--adopt <name>` is the follow-up.
- `tests/test_tooling_adoption.py` cites `modelb_axi/cli.py` by line range in its module
  docstring and a comment, and cites `config.py::_toml_value serializes only strings`; §S1 and
  §S5 move both targets. The citations are prose, not assertions, and are re-recorded once in the
  final cycle.

## Non-goals

- No asset-class additions (025), no roster change (031), no emitter logic (030).
- No `--adopt` flag.
