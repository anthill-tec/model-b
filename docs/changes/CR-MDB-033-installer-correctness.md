# CR-MDB-033 — Installer correctness: one `target_root`, atomic writes, unmanaged files are never clobbered, manifest always consulted

**Status:** PENDING (filed 2026-09-21 from `audits/2026-09-21-codebase-review-modelb_axi.md` §C/§D)
**Type:** bugfix
**Priority:** P1 — in release 1.0.0, wave 2, **before CR-MDB-025 §S4**. 025's `inbox-analyst.md
byte-identical after --force-managed` AC cannot hold while `deploy.py:123-131` overwrites any
pre-existing same-named file on a first install; and 025's sandboxed integration proof cannot be
trusted while the scaffold compiles wiring against a `[install].target_root` the installer never
writes.
**Depends on:** — (small, self-contained; sequenced first in the wave-2 tail)
**Labels:** installer, scaffold, config, bugfix
**Phase:** Wave 5 (repo queue) · release 1.0.0 wave 2 (Crucible board)
**Design reference:** `AGENTS.md` ("writes are atomic (temp file + os.replace)"; "idempotence by
sha256 manifest comparison"; "flag > env > default") · DN §D3 ("a file absent from the manifest
is not Model B's") · DN §D9 (asset classes do not retro-deploy) · `audits/…-modelb_axi.md` §C, §D

## Context — measured

| # | Where | Defect |
|---|---|---|
| 1 | `scaffold.py:433-435` vs `cli.py:238-245` | Scaffold reads `[install].target_root` to locate the deployed hook scripts; the installer writes `version/harnesses/asset_root/tool_scripts_dir` and **never `target_root`**, so scaffold falls back to `Path.home()/.agents/hooks/scripts`. An install made with `--target-root /x` therefore compiles wiring pointing at the real home where nothing was deployed. Two path rules for one store. |
| 2 | `deploy.py:113-134`, `hooks.py:198,270,315,348`, `scaffold.py:573` | Only `config.write_install_toml` is atomic. Every deployed asset (`shutil.copyfile`) and every compiled wiring file is written in place; a crash mid-write leaves a truncated managed file whose hash matches neither source nor manifest → permanently "hand-modified", skipped forever. Contradicts AGENTS.md. |
| 3 | `deploy.py:123-131` | `_deploy_file`: dest exists, differs from src, **not in manifest** → falls through and overwrites. On a first install a pre-existing same-named file is clobbered. Contradicts DN §D3; becomes a data-loss path once `.agents/agents` (025) is deployed beside hand-placed definitions. |
| 4 | `cli.py:221` | `prior_hashes = load_manifest_hashes(home) if reinstall else {}` — manifest protection depends on a flag, not on manifest presence. `MODELB_HOME` at a fresh dir + the same `--target-root` → manifest ignored, everything rewritten. |
| 5 | `scaffold.py:19-21` vs `:569-574` | Docstring: "`--dry-run` (and any failure) writes NOTHING". `_emit_plan` writes each file immediately; a failure mid-plan leaves a partial tree with an `ok:false` envelope. |
| 6 | `scaffold.py:466-470`, `resolve_harnesses:70-72` | Harness ids read from `install.toml` are not validated against the roster (the dev override is), so a stale id reaches the compiler's "not in roster" branch instead of a clear error. |
| 7 | `config.py:26-38` vs `scaffold.py:403-418` | Two hand-rolled TOML writers; one escapes, one does not. `_toml_string` misses C0 controls other than `\n\t\r`; `_toml_value` raises on non-strings with no schema check at the call site. |
| 8 | `cli.py:262-305` vs `scaffold.py` | Installer human progress goes to **stdout**; `init` sends it to stderr and reserves stdout for the envelope. `preflight.py:85,93` prints `deps:` twice on the sandesh-install path. |

## Scope

### §S1 — One source of truth for the deployed root
`config.write_install_toml` records `target_root` (the resolved `--target-root`/`MODELB_TARGET_ROOT`/
home) and per-class dirs (`skills_dir`, `hooks_scripts_dir`, `tool_scripts_dir`, and 025's
`agent_defs_dir`). Scaffold reads `hooks_scripts_dir` directly; no fallback to `Path.home()`
when a manifest exists — a manifest without the key is a versioned-upgrade case handled with a
clear error naming `modelb-axi --reinstall`.

### §S2 — Atomic writes everywhere
One helper `modelb_axi/_fsutil.py::atomic_write(path, data: bytes, mode=None)` (tmp in the same
directory + `os.replace`, mode preserved from source for assets), used by `deploy._deploy_file`,
every `hooks.py` emitter, and `scaffold._emit_plan`. `install.toml` mode becomes 0644 (or
documented).

### §S3 — Unmanaged files are skipped, never clobbered
`_deploy_file`: dest exists ∧ differs ∧ not in manifest → **skip** with a distinct warning
(`unmanaged: <path> — not Model B's; --force-managed to overwrite`). `--force-managed` overwrites
managed-but-modified files only; unmanaged files are overwritten by nothing short of a new
explicit `--adopt <name>` (out of scope — record the gap). The manifest is loaded whenever it
exists, not only with `--reinstall`.

### §S4 — Scaffold emission is transactional or honest
Either stage the plan into a temp dir and rename into place at the end, or amend the docstring
and the `init` envelope to say a failed emission may leave a partial tree with the list of files
written. Decide at gap-analysis; the AC below covers both.

### §S5 — Validation and hygiene
Validate `install.toml` harness ids against the roster like the override; single TOML writer
(`config._toml_string` used by scaffold; C0/DEL escaped as `\uXXXX`; schema assertion at
`serialize_install_toml`); installer human lines to stderr, `deps:` printed once; docstring
citations name the DN file; "Vercel store" → "shared store".

## Acceptance criteria

- [ ] Install to `--target-root /tmp/x` then `init` a project: the compiled `.pi/extensions/*.ts`
      reference `/tmp/x/.agents/hooks/scripts/…`, never `~/.agents` — round-trip test.
- [ ] `install.toml` carries `target_root` and every per-class dir; a manifest missing them
      produces a named error, not a home fallback.
- [ ] Killing the process between tmp-write and rename leaves the destination untouched —
      asserted by monkeypatching `os.replace` to raise and checking the prior file is intact.
- [ ] First install into a root that already holds `.agents/agents/inbox-analyst.md` (foreign
      content): the file is byte-identical afterwards; the run reports it as unmanaged; a second
      run with `--force-managed` still leaves it byte-identical.
- [ ] A managed file hand-modified after install is skipped without `--force-managed` and
      overwritten with it (existing behaviour, re-asserted).
- [ ] Without `--reinstall`, a second run over the same root reports every managed file
      unchanged (manifest consulted).
- [ ] `init` with a mid-plan failure: either no file exists under `--target` (transactional) or
      the envelope lists exactly the files written (honest) — one asserted.
- [ ] `install.toml` listing a non-roster harness id fails fast with the id named.
- [ ] `grep -c "print(" modelb_axi/cli.py` human lines route to stderr; exactly one `deps:` line
      on stdout per run.
- [ ] Both TOML serialisations go through `config._toml_string`; a value containing `\x1b`
      round-trips through `tomllib`.

## Estimated size

~150 lines across `config.py`, `deploy.py`, `scaffold.py`, `cli.py`, `hooks.py`, one new helper
module, ~12 tests. Small–medium.

## Risk

- Existing installs carry manifests without `target_root`; §S1's named error must point at the
  remedy. Recorded as an upgrade note for CR-012.
- Changing first-install semantics (skip unmanaged) may surprise a user who expected a takeover;
  the warning text names the flag that does not exist (`--adopt`) so the gap is visible, and
  the queue note records it as a follow-up.

## Non-goals

- No asset-class additions (025), no roster change (031), no emitter logic (030).
- No `--adopt` flag.
