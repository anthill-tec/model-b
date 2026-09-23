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

The hook-scripts dir is resolved during `init`'s validation, **before its first write** — a
failure `init` can know in advance never leaves a partial tree. The two failure cases carry
distinct messages: an `install.toml` that lacks the key (remedy: `--reinstall`), and no
`install.toml` at all, which is the `--harnesses` dev-override path (remedy: run the installer,
since no hook scripts have been deployed anywhere). `--dry-run` runs the same check: it still
writes nothing and exits 0, and it carries the error text as an envelope warning, so a plan real
`init` cannot emit is never previewed as clean.

Test fixtures follow the contract rather than the contract following the fixtures:
`tests/test_scaffold.py`'s `install.toml` fixture records `hooks_scripts_dir`, as every install
after this CR does; and `tests/test_tooling_adoption.py` locates the tool-scripts dir by its key
name `tool_scripts_dir`, not by sweeping `[install]` for keys matching `/script|tool/`.

### §S2 — Atomic writes everywhere
One helper `modelb_axi/_fsutil.py::atomic_write(path, data: bytes, mode=None)` (tmp in the same
directory + `os.replace`; the tmp file is removed if the replace fails; mode preserved from source
for assets). It replaces every in-place write in the package — six call sites:
`deploy._deploy_file`, `hooks._emit_claude_code`, `hooks._emit_opencode`, `hooks._emit_pi`,
`hooks._emit_hermes_advisory`, and `scaffold._emit_plan`'s writer. `install.toml` is written
with mode 0644; it holds no secrets, and its current 0600 is `mkstemp`'s default rather than a
decision.

### §S3 — Unmanaged files are skipped, never clobbered
`_deploy_file`: dest exists ∧ differs ∧ not in manifest → **skip**, reported with the warning
`unmanaged: <path> — not Model B's; left untouched (no flag overwrites it)`. This vocabulary is
distinct from the managed hand-modified warning and never appears on that path.

`--force-managed` overwrites managed-but-modified files only; no flag in this CR overwrites an
unmanaged file. The manifest is loaded whenever it exists, not only with `--reinstall`.

### §S4 — Scaffold emission is honest about partial failure
`--dry-run` writes nothing, as today. A failure mid-emission may leave a partial tree; the module
docstring claims only that, and the `init` failure envelope carries `emitted` — the same field
the success envelope uses — listing exactly the files written before the failure. Emission is not
staged through a temp dir.

### §S5 — Validation and hygiene
- Harness ids read from `install.toml` are validated against the roster exactly like the
  `--harnesses` override: the same `UnknownHarnessError`, naming the id, with the same exit code,
  raised in `init`'s validation phase before any write — on `--dry-run` too.
- One TOML string writer: `scaffold._render_instance_toml` writes its string values through
  `config._toml_string`, which escapes every C0 control (U+0000–U+001F) and DEL (U+007F) not
  already given a short escape, as `\uXXXX`.
- Every `DN §` citation in `modelb_axi/` names its DN file; "Vercel store" becomes "shared
  store".

### §S6 — The installer's result is one AXI envelope on stdout
Every bare `modelb-axi` invocation — the installer flow and the already-installed notice —
writes exactly one AXI envelope to stdout through `modelb_axi.axi.envelope`, verb `install`, as
`init` does. Every human line — banners, stage lines, `harnesses selected:`, warnings, and both
`deps:` lines (the pre-remediation report and the post-install update, CR-MDB-014 AC4) — goes to
stderr, from `cli.py` and `preflight.py` alike.

| Exit path | `outcome` | `ok` | exit |
|---|---|---|---|
| `install.toml` already present (scaffold-mode notice) | `already_installed` | true | 0 |
| user declines "Proceed?" | `aborted` | false | 1 |
| pre-flight fails (e.g. `uv` absent) | `preflight_failed` | false | 1 |
| unknown harness id | `harness_rejected` | false | 1 |
| user declines the detected harness set | `aborted` | false | 1 |
| deploy fails (no `install.toml` written) | `deploy_failed` | false | 1 |
| no target root given — deploy skipped | `deploy_skipped` | true | 0 |
| complete | `installed` | true | 0 |

Fields beside `outcome`: `deps` — the `{uv, sandesh, crucible}` verdicts as recorded in
`install.toml [deps]`, present once pre-flight has run; `harnesses` — the selected ids, present
once targeting succeeded; `target_root`, `install_toml`, `managed_files` (the count of `[[files]]`
entries), `skipped` and `unmanaged` (relative paths) — present when `install.toml` was written;
`warnings` — every warning the run printed to stderr. Exit codes are unchanged. Argparse usage
errors are argparse's own and outside this contract.

## Acceptance criteria

- [ ] Install to `--target-root /tmp/x` then `init` a project: the compiled `.pi/extensions/*.ts`
      reference `/tmp/x/.agents/hooks/scripts/…`, never `~/.agents` — round-trip test.
- [ ] `install.toml` carries `target_root`, `skills_dir`, `hooks_scripts_dir` and
      `tool_scripts_dir`; an `install.toml` missing `hooks_scripts_dir` makes scaffold raise an
      error naming the key and `modelb-axi --reinstall` — no home fallback, no partial-key rule.
- [ ] With an `install.toml` lacking `hooks_scripts_dir`, a real `init` exits non-zero and leaves
      **no file** under `--target`.
- [ ] With no `install.toml` at all (the `--harnesses` dev override), a real `init` exits
      non-zero and leaves no file under `--target`; the error states that no `install.toml`
      exists at the resolved home and names the installer — it never says the file "does not
      record" a key.
- [ ] In both cases `--dry-run` writes nothing, exits 0, and its envelope carries the same error
      text as a warning.
- [ ] `tests/test_scaffold.py`'s `install.toml` fixture records `hooks_scripts_dir`, and every
      real-`init` test using it passes under the strict §S1 rule.
- [ ] `tests/test_tooling_adoption.py` asserts the tool-scripts location through the key named
      `tool_scripts_dir`; the presence of `hooks_scripts_dir` in `[install]` does not trip it.
- [ ] Each of the six write sites — `deploy._deploy_file`, `hooks._emit_claude_code`,
      `hooks._emit_opencode`, `hooks._emit_pi`, `hooks._emit_hermes_advisory`,
      `scaffold._emit_plan` — writes through `_fsutil.atomic_write`: with `os.replace`
      monkeypatched to raise, re-running that site over an existing destination leaves the prior
      file byte-identical and leaves no temp file in its directory. Asserted per site, six
      subtests; a site not asserted is a site not wired.
- [ ] No `shutil.copyfile`, `.write_text(` or `.write_bytes(` remains in `modelb_axi/` outside
      `_fsutil.py` — a grep gate.
- [ ] Atomic writes change no file's permissions: `atomic_write(..., mode=None)` produces the
      mode a plain write would (`0o666 & ~umask`), not `mkstemp`'s 0600 — asserted on a compiled
      `.pi/extensions/*.ts` and a scaffolded `AGENTS.md`; a deployed hook script keeps its
      source's executable bit.
- [ ] `install.toml` is written with mode 0644.
- [ ] First install into a root that already holds a foreign `<target-root>/.agents/scripts/gate-lock.sh`:
      the file is byte-identical afterwards; the run reports it with the `unmanaged:` warning; a
      second run with `--force-managed` still leaves it byte-identical.
- [ ] A managed file hand-modified after install is skipped without `--force-managed` and
      overwritten with it, and neither run reports it with the `unmanaged:` wording — asserted in
      the existing `tests/test_installer.py` tests for this behaviour, not in duplicates.
- [ ] Without `--reinstall`, a second run over the same root reports every managed file
      unchanged (manifest consulted).
- [ ] `init` with a mid-emission failure (an `OSError` injected after some files are written)
      exits non-zero, and its failure envelope's `emitted` lists exactly the files present under
      `--target`; `--dry-run` still writes nothing. The module docstring no longer claims a
      failure writes nothing.
- [ ] An `install.toml` listing a non-roster harness id makes `init` fail with the same
      `UnknownHarnessError` and exit code as the `--harnesses` override, naming the id, before any
      file is written under `--target` — and on `--dry-run` too.
- [ ] Each of the eight exit paths in §S6's table writes exactly one envelope to stdout that
      decodes with `modelb_axi.toon`, with verb `install` and that path's `outcome`, `ok` and exit
      code — asserted per path, eight subtests.
- [ ] On every path stdout carries nothing but that envelope, and every human line from `cli.py`
      and `preflight.py` is on stderr — including both `deps:` lines on a run that installs
      Sandesh.
- [ ] On `installed`, the envelope's `deps` equals `install.toml [deps]`, `managed_files` equals
      the number of `[[files]]` entries, and a foreign `<target-root>/.agents/scripts/gate-lock.sh`
      appears in `unmanaged`.
- [ ] Existing tests that read installer FACTS from stdout text (in `tests/test_installer.py`: the
      `deps:` verdicts, `_extract_selected_harnesses`, the already-installed notice) read them from
      the envelope; tests asserting prose or ordering read stderr; and the absence checks that
      guard against a fabricated `deps:` report or a re-entered installer flow assert against
      stderr, so they still fail when that happens.
- [ ] `config._toml_string` round-trips every character U+0000–U+001F and U+007F through
      `tomllib`, and `scaffold._render_instance_toml` writes its strings through it.
- [ ] Every `DN §` citation in `modelb_axi/*.py` names its DN file, and "Vercel" appears nowhere
      in `modelb_axi/` — a grep gate.
- [ ] `tests/test_tooling_adoption.py` cites `modelb_axi/cli.py` by function, never by line range.

## Estimated size

~150 lines across `config.py`, `deploy.py`, `scaffold.py`, `cli.py`, `hooks.py`, one new helper
module, ~12 tests. Small–medium.

## Risk

- Existing installs carry manifests without `hooks_scripts_dir`; §S1's named error points at the
  remedy. Upgrade note for the release ritual (`skills-src/git-workflow/SKILL.md` §Releases).
- Changing first-install semantics (skip unmanaged) may surprise a user who expected a takeover;
  the warning says no flag overwrites the file, and a future `--adopt <name>` is the follow-up.
- §S6 moves every installer line off stdout; anything reading the installer's text output —
  inside this repo, the `tests/test_installer.py` assertions named in the ACs — must read the
  envelope or stderr instead. CR-MDB-036's `doctor` and CR-MDB-029's package consume the
  envelope rather than text.

## Non-goals

- No asset-class additions (025), no roster change (031), no emitter logic (030).
- No `--adopt` flag.
