# CR-MDB-033 — Installer correctness: one `target_root`, atomic writes, unmanaged files are never clobbered, manifest always consulted

**Status:** PENDING (filed 2026-09-21 from `audits/2026-09-21-codebase-review-modelb_axi.md` §C/§D)
**Type:** bugfix
**Priority:** P1 — in release 1.0.0, wave 2, **before CR-MDB-025 §S4**. 025's `inbox-analyst.md
byte-identical after --force-managed` AC cannot hold while `deploy.py:123-131` overwrites any
pre-existing same-named file on a first install; and 025's sandboxed integration proof cannot be
trusted while the scaffold compiles wiring against a `[install].target_root` the installer never
writes.
**Depends on:** — (small, self-contained; sequenced first in the wave-2 tail)
**Gap-analysis:** 2026-09-22, orchestrator-run — verdict **SPEC_UPDATE_NEEDED**, corrections
applied in place and marked inline. Baseline measured at analysis time: **359 tests / 0 failures
/ 11 skips** on `develop` @ `9f512eb`, clean tree. All 8 measured defects re-verified against
current source and CONFIRMED; DN §D3 confirms defect 3 is a design-contract violation
("a file absent from the manifest is not Model B's").
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
home) and per-class dirs for the asset classes that EXIST today (`skills_dir`,
`hooks_scripts_dir`, `tool_scripts_dir`). Scaffold reads `hooks_scripts_dir` directly; no
fallback to `Path.home()` when a manifest exists — a manifest without the key is a
versioned-upgrade case handled with a clear error naming `modelb-axi --reinstall`.
`scaffold._hook_scripts_dir`'s docstring ("forward-compatible; the v1 installer does not record
it") is corrected in the same change, or it contradicts the new behaviour.

**Gap-analysis 2026-09-22 — `agent_defs_dir` REMOVED from this section.** It was listed as
"025's `agent_defs_dir`", but `.agents/agents` is not an asset class until CR-MDB-025 creates it
(`deploy.py` defines only `STORE_RELDIR`, `HOOKS_SCRIPTS_STORE_RELDIR`,
`TOOL_SCRIPTS_STORE_RELDIR`), and 033 is sequenced BEFORE 025. A key naming a directory nothing
deploys to is a claim the installer cannot honour. **025 adds its own key** through the seam this
CR builds.

### §S2 — Atomic writes everywhere
One helper `modelb_axi/_fsutil.py::atomic_write(path, data: bytes, mode=None)` (tmp in the same
directory + `os.replace`, mode preserved from source for assets), used by `deploy._deploy_file`,
every `hooks.py` emitter, and `scaffold._emit_plan`. `install.toml` mode becomes 0644 (or
documented).

### §S3 — Unmanaged files are skipped, never clobbered
`_deploy_file`: dest exists ∧ differs ∧ not in manifest → **skip** with a distinct warning.

**Warning text (corrected 2026-09-22, post-gap-analysis):**
`unmanaged: <path> — not Model B's; left untouched (no flag overwrites it)`.
The original spec text read `… --force-managed to overwrite`, which **contradicts the very next
sentence and AC3**: `--force-managed` overwrites managed-but-modified files ONLY, so the warning
would have told the user to run a flag that does nothing to their file. Gap-analysis did not
catch this; it was caught at GREEN dispatch. If a takeover path is ever wanted it is the
`--adopt <name>` flag recorded in Risk as a follow-up — **not** in this CR.

`--force-managed` overwrites managed-but-modified files only; unmanaged files are overwritten by
nothing short of a future explicit `--adopt <name>` (out of scope — the gap is recorded). The
manifest is loaded whenever it exists, not only with `--reinstall`.

### §S4 — Scaffold emission is honest about partial failure (DECIDED at gap-analysis)
**Decision 2026-09-22: take the HONEST option, not the transactional one.** Measured:
`scaffold.py:686` gates the whole emission behind `if not dry_run:`, so the `--dry-run` half of
the docstring claim is TRUE — only the "(and any failure) writes NOTHING" half is false. Staging
an entire scaffold tree through a temp dir to make that second clause true is machinery out of
proportion to what it protects: `init` targets a NEW project directory, and a failed run leaves a
partial tree the user deletes. Amend the docstring to claim only what holds, and make the `init`
envelope list exactly the files written before the failure. (Dimension 7 — reversible: if you
want true transactionality, say so and it becomes its own CR.)

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
- [ ] First install into a root that already holds a foreign file **at a path Model B actually
      deploys to** — `<target-root>/.agents/scripts/gate-lock.sh` with foreign content (gap-analysis
      2026-09-22: the original AC named `.agents/agents/inbox-analyst.md`, which nothing deploys to
      until CR-MDB-025, so it would have passed VACUOUSLY without the fix): the file is
      byte-identical afterwards; the run reports it as unmanaged; a second run with
      `--force-managed` still leaves it byte-identical.
- [ ] A managed file hand-modified after install is skipped without `--force-managed` and
      overwritten with it — **already covered by `tests/test_installer.py:1046` and `:1081`;
      re-assert by extending those, do not write duplicates** (gap-analysis, Dimension 4).
- [ ] Without `--reinstall`, a second run over the same root reports every managed file
      unchanged (manifest consulted) — `test_installer.py:1012` covers the `--reinstall` path
      only; the new assertion is the NO-flag path.
- [ ] `init` with a mid-plan failure: the envelope lists exactly the files written (§S4's honest
      option), and `--dry-run` still writes nothing.
- [ ] `install.toml` listing a non-roster harness id fails fast with the id named.
- [ ] Every human progress line in `modelb_axi/cli.py` is written with `file=sys.stderr`;
      stdout from an installer run contains no human prose (asserted by capturing both streams,
      not by `grep -c`). The `deps:` line keeps BOTH of its emissions — the pre-remediation
      report and the post-install update are deliberate under CR-MDB-014 AC4 ("records detection
      truthfully ... before any remediation mutates the picture"); gap-analysis 2026-09-22
      reversed the original "exactly one `deps:` line" AC, which would have destroyed that
      truthfulness to fix a channel bug.
- [ ] Both TOML serialisations go through `config._toml_string`; a value containing `\x1b`
      round-trips through `tomllib`.

## Estimated size

~150 lines across `config.py`, `deploy.py`, `scaffold.py`, `cli.py`, `hooks.py`, one new helper
module, ~12 tests. Small–medium.

## Risk

- Existing installs carry manifests without `target_root`; §S1's named error must point at the
  remedy. Recorded as an upgrade note for the **release ritual**
  (`skills-src/git-workflow/SKILL.md` §Releases) — gap-analysis 2026-09-22: the original text
  said "for CR-012", which is VOID (a release is not a CR).
- Changing first-install semantics (skip unmanaged) may surprise a user who expected a takeover;
  the warning text names the flag that does not exist (`--adopt`) so the gap is visible, and
  the queue note records it as a follow-up.
- **Inverse blast radius (gap-analysis 2026-09-22, Dimension 16).** `tests/test_tooling_adoption.py`
  pins `modelb_axi/cli.py:233-237` in TWO places (`:16` docstring, `:157` comment). That pin has
  ALREADY drifted — 233-237 is now the skip-warning tail and the `[install]` table sits at
  238-245 — and §S1 moves the block again. Both are prose, not asserted, so nothing fails; they
  are re-recorded ONCE as a close-out step of the final cycle, not as a per-cycle escalation.
  `tests/test_tooling_adoption.py:627` also pins `config.py::_toml_value serializes only strings`,
  which §S5's schema assertion changes.

## Interrupted run — resume state (EMERGENCY shutdown 2026-09-22)

An emergency power-outage shutdown stopped cycle C1 mid-GREEN. Cycle **69** (plan 96) is still
ACTIVE. WIP committed and pushed at **`b9da107`**; `develop` untouched at `9f512eb`.

**Verified state:** RED is real — **364 / 5F / 11S at `8feffab`**, the 5 failures being the new
tests. GREEN is **UNVERIFIED**: the suite was never run against `b9da107` and nothing was
ingested. The GREEN agent's own final check confirmed the failed edit never applied and both
touched files parse; the orchestrator re-confirmed with `ast.parse`.

**Done in `b9da107`:** §S3 whole (`deploy.py` `_deploy_file` returns `None` for unmanaged and
collects them; `cli.py` loads the manifest unconditionally and prints the corrected
`unmanaged: … left untouched (no flag overwrites it)` warning) and §S1's installer half
(`target_root`, `skills_dir`, `hooks_scripts_dir` recorded).

**NOT done:** §S1's scaffold half. `scaffold.py:421 _hook_scripts_root` still reads
`[install].target_root` with a `Path.home()` fallback and still carries the false
"the v1 installer does not record it" docstring.

### Two conflicts requiring an ORCHESTRATOR RULING before GREEN resumes

Both are test-vs-test and cannot be fixed by production code alone.

1. **`tests/test_tooling_adoption.py:601` is ALREADY FAILING in `b9da107`.** Its
   `INSTALL_KEY_HINT = /script|tool/i` sweep over `[install]` keys outside
   `{version, harnesses, asset_root}` now catches `hooks_scripts_dir` and asserts its value is
   `…/.agents/scripts` — but the value is `.agents/hooks/scripts`. The key name is pinned
   verbatim by the RED test, so no production rename escapes it. **The branch therefore has a
   6th failure that is NOT one of the five RED tests** — do not mistake it for a regression
   introduced on resume. Ruling needed: widen that test's exclusion set (it predates this CR's
   schema) versus any production change.
2. **`tests/test_scaffold.py:111 `_write_install_toml`** writes a fixture carrying only
   `version/harnesses/asset_root`. §S1 as literally written ("no fallback when a manifest
   exists") would make all ten real-`init` tests using it raise. The GREEN agent proposed
   narrowing the rule — fall back to the documented home default only when NO deployment-location
   key (`target_root`/`hooks_scripts_dir`/`tool_scripts_dir`) is present, error otherwise — and
   flagged it as possibly fitted to the tests. **It is: that rule is shaped by the fixtures, so
   it needs a deliberate decision, not a GREEN-phase improvisation.** Cheaper and more honest
   alternative to weigh first: update the `test_scaffold.py` fixture to record
   `hooks_scripts_dir`, since every real install after this CR will.

**Resume order:** rule on both conflicts → finish `_hook_scripts_root` → register
`CR-MDB-033-C1-GREEN` (nothing to unregister; the bracket was never opened) → run the suite.

## Non-goals

- No asset-class additions (025), no roster change (031), no emitter logic (030).
- No `--adopt` flag.
