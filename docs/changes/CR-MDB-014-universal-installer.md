# CR-MDB-014 — Universal installer flow + packaging (`modelb-axi`)

**Status:** COMPLETED
**Type:** feature
**Priority:** P1 (heads the setup arc: 014 → 013 → 015)
**Depends on:** CR-MDB-002, CR-MDB-008
**Labels:** installer, packaging, tui, uv
**Phase:** Wave 3
**Design reference:** PRD §D10 (settled-setup bullet 2026-07-22 + installer orchestration boundary) · `docs/research/DN-scaffold-packaging.md` (the authoritative design record — read FIRST)

## Context

The DN records the user-settled setup design: uv/pipx-installed Python package `modelb-axi`, ONE adaptive TUI (installer flow ⟷ scaffold flow by detected state), dependency orchestration (uv/Sandesh/Crucible via their own installers), `$MODELB_HOME/install.toml` config seam, initial harness roster (Claude Code, Hermes, pi, OpenCode), manifest-driven idempotent upgrade. This CR builds the PACKAGE + INSTALLER FLOW; the scaffold flow is CR-MDB-013 (depends on this CR); hook content is the 015 seam.

**Binding rules:** repo-local authoring (PRD D9 as amended — no writes to `~/.claude`; tests deploy only into sandbox roots via `$MODELB_HOME`/target overrides); Crucible clients/assets are NEVER mirrored — their installer is invoked (or its absence warned) per the #1330 boundary.

## Scope

### §S1 — AC gate tests (RED first)
`tests/test_installer.py` (+ extensions to existing gates where they overlap). All deploy targets are tmp sandboxes.

### §S2 — Package skeleton
`pyproject.toml` (package `modelb-axi`, module `modelb_axi/`, console script `modelb-axi`); `uv tool install <repo-path>` produces a working global `modelb-axi` bin. Package data wires in the asset roots (skills-src/, generator/, contracts/, scripts).

### §S3 — State detection + adaptive TUI shell
On launch: resolve `$MODELB_HOME` (XDG default) → `install.toml` present ⇒ scaffold mode (v1: a stub that names 013 and exits 0); absent ⇒ installer flow. TUI prompts with sensible defaults + non-interactive flags (`--yes`, `--harnesses`, `--modelb-home`) for CI/tests.

### §S4 — Dependency pre-flight
Checks in order: `uv` (bootstrap instructions if absent), Sandesh (`sandesh` bin / `uv tool list`; install via `uv tool install sandesh-relay` on confirm), Crucible (invoke THEIR installer CLI when present; absent ⇒ WARN with instructions and record `"absent"` — never hand-deploy their assets). Results recorded under `[deps]`.

### §S5 — Harness targeting
Probe the roster binaries (`claude`, `hermes`, `pi`, `opencode`), propose detected set, user confirms/edits; selection recorded under `[install].harnesses`.

### §S6 — Deploy engine + config write
Manifest-driven copy of package assets into the selected harnesses' user-local locations (per-harness mapping table; Claude Code mapping complete in v1, other roster harnesses at least anchor-file mapping). Skills deploy per the PRD §D2 Vercel skills standard: ONE copy into the harness-neutral store (`~/.agents/skills/` — sandboxed in tests), symlinked into each selected harness's skills dir; every deployed path + hash recorded under `[files]`; `install.toml` written last (atomic). Re-run = idempotent upgrade per DN §5 (hash-check, confirm-before-overwrite of user-modified managed files, non-manifest files untouched).

### §S7 — Skill-source imports + generator retarget
Import the remaining Model B-owned skills (`model-b`, `cr-authoring`, `git-workflow`, `chezmoi`, `bootstrap`, `shutdown`) into `skills-src/` as package assets (read-only copy FROM the deployed state — reading `~/.claude` allowed, writing never). Retarget `generator/build.py` output from the chezmoi source to repo/package assets (`--check` drift gate preserved); regenerated agents ship as assets at `generator/agents/`. **Sanctioned test amendment:** CR-MDB-008's gates (`tests/test_agent_generator.py`) pin the superseded `~/.claude/agents/` output target — they retarget to `generator/agents/`, keeping a read-only consumer-constraint check that the DEPLOYED `~/.claude/agents/*.md` files still exist untouched (agents remain live from there until this installer deploys).

## Acceptance criteria

- [ ] AC1: `uv tool install <repo>` (in a tmp `UV_TOOL_DIR`/`UV_TOOL_BIN_DIR` sandbox) exposes a runnable `modelb-axi` that exits 0 on `--version`.
- [ ] AC2: with `MODELB_HOME=<tmp>` and no `install.toml`, `modelb-axi --yes --harnesses claude-code` runs the installer flow end-to-end into sandbox targets and writes `install.toml` with `[install]` (version/harnesses/asset_root), `[deps]`, `[files]` (≥1 entry per deployed file, path+hash).
- [ ] AC3: with `install.toml` present, launch enters scaffold mode (v1 stub naming CR-MDB-013) — state detection proven both ways.
- [ ] AC4: pre-flight records `uv` and Sandesh detection truthfully; Crucible absent ⇒ `[deps].crucible = "absent"` + a warning naming their installer — zero Crucible files deployed by us (grep the sandbox: no `*-crucible.py`, no `_crucible_axi.py`, no `toon.py`).
- [ ] AC5: second identical run (upgrade) is a no-op on unchanged files (hashes stable) and NEVER touches paths outside the manifest; a hand-modified managed file is detected (hash mismatch surfaced, not silently clobbered in `--yes` mode without an explicit `--force-managed`).
- [ ] AC6: `skills-src/` contains the six imported skill bundles; `skills-src/crucible/` (011) ships as an asset unchanged; `build.py --check` passes against repo/package assets with zero chezmoi-source references (grep gate on `generator/`).
- [ ] AC7: zero writes to the real `~/.claude` in the entire test suite (guard fixture asserts `~/.claude` mtimes/`chezmoi diff` unaffected); zero `WORKFLOW_CYCLE_ID` and zero `.claude/scripts` client paths in everything newly authored.
- [ ] AC8: the TUI is skippable end-to-end via flags (CI-safe), and interactive prompts default to the detected values.
