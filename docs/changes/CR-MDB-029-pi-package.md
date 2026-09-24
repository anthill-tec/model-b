# CR-MDB-029 — The Model B Pi package: extensions + skills as one `pi install`-able unit

**Status:** PENDING (filed 2026-09-21 from DN-multi-harness-deploy-model §D15.2/§D15.3 and its
Consequences row "NEW CR"; the number 027 first reserved for this was consumed by the dispatch
decision CR)
**Type:** feature
**Priority:** P1 — in release 1.0.0, wave 2 (the CR-MDB-026 watcher supervisor has no Pi home
without it — DN §D15.3)
**Depends on:** CR-MDB-030 (the hook runtime the package's extensions ship must work first) ·
CR-MDB-025 (agent definitions are NOT in this package; their asset class must exist so the split
below is real). **Not** CR-MDB-026: this CR *implements* 026's three-exit taxonomy, and 026's
instruction-level edits then cite the extension — the edge runs 026 → 029 (the board refused the
reverse as a cycle, 2026-09-21).
**Labels:** pi, packaging, extensions, skills, distribution, feature
**Phase:** Wave 5 (repo queue) · release 1.0.0 wave 2 (Crucible board)
**Design reference:** DN §D15.2 (Pi package system: `package.json` `pi` manifest, `npm:`/`git:`/
local-path install, `skills/` discovered recursively, core packages as `peerDependencies "*"`) ·
DN §D15.3 (user ruling: the supervised watcher is a Model-B-built Pi extension) · DN §D16(1)
(agent definitions go through the installer, not a package) · CR-MDB-015 (hook wiring emitted
per project today) · `pi-archimedes/package.json` (a measured, working Pi package manifest —
`"keywords": ["pi-package"]`, `"pi": {"extensions": [...]}`, `peerDependencies` on
`@earendil-works/pi-coding-agent >=0.1.0`)

## Context

DN §D15.2 measured that Pi has a first-class package system and that it is *better* than the
OMP marketplace §D10 had adopted: npm sources are installable, packages bundle **extensions,
skills, prompts, themes**, project entries auto-install after trust, and `pi config` toggles
individual resources. Nothing in this repo uses it yet. Today the Pi surface is:

- skills: read from `~/.agents/skills/` after the installer copies them there (works — §D15.1);
- hooks: emitted **per project** into `.pi/extensions/*.ts` by `hooks.py::_emit_pi` (broken —
  CR-MDB-030);
- the Sandesh wake watcher: a backgrounded shell job (broken — CR-MDB-026), with no supervisor
  on Pi because Pi has no `hub` (DN §D13 (3), §D15.3).

**The split, ruled by DN §D16(1) and the package contract:** a Pi package carries only
extensions/skills/prompts/themes, so **agent definitions cannot ride it** — they are the
installer's asset class (CR-025 §S4). Tool scripts stay installer-deployed to `~/.agents/scripts/`
(CR-022). The package therefore holds exactly: `extensions/` and `skills/`.

**This repo stays stdlib-only Python.** Pi imports `.ts` extensions directly (no build step);
`@earendil-works/pi-coding-agent` is a peer/dev dependency of the *package directory*, not of
`modelb_axi`. The package is an asset, authored in this repo and published from it.

## Scope

### §S0 — Gap-analysis questions
- Whether the per-project hook extensions (015) should *move* into the package (one global
  `extensions/` set reading project config) or stay per-project. Package-shipped means every Pi
  session gets them without scaffold; per-project means worktrees need `.pi/extensions/` tracked
  (CR-030 §S6). Decide once; the answer shapes 030's emitter.
  **DECIDED 2026-09-23 (user, at CR-MDB-030 gap-analysis): per-project.** Hooks are wired per
  project as PRD D10.7 and DN §D17 settle; `.pi/` is tracked so worktrees carry them (CR-030 §S6).
  This package ships no hook extensions.
- Publication location: this repo via a subdirectory published to npm, or a git-source install
  (`pi install git:github.com/antojk/model-b#<tag>` with a subpath) — DN Consequences named the
  choice as the user's, with release-process consequences for CR-012.
- Whether `skills/` in the package duplicates the installer's `~/.agents/skills` deploy, or
  replaces it for Pi. Both work (§D15.1); pick one to avoid two copies drifting.

### §S1 — Package layout and manifest
`pi-package/` (name to be settled at §S0) with `package.json`: `"name"`, `"version"` (tracks the
Model B release), `"keywords": ["pi-package"]`, `"pi": {"extensions": [...], "skills": "skills/"}`
(or convention directories), `peerDependencies` on the Pi core packages at `"*"`/`>=0.1.0`,
**no** bundled Pi core. `pi install <local path>` is the dev loop (added to settings without
copying).

**The package README** (CR-MDB-037 §S1): the package's `README.md` carries no install text of its
own — it is the marked regions of `docs/install-guide.md`, copied verbatim at publish time.

### §S2 — The watcher supervisor extension (CR-026 on Pi)
`extensions/sandesh-watcher.ts`: spawns `sandesh notify --to <addr> --project <p>` as a supervised
child, restarts on exit code ≠ 0 with backoff, and reports 026's **three-exit taxonomy** — mail
(exit 0 → wake the session), timeout (exit 2 → restart silently), lock-conflict (exit per 026 →
surface, do not restart). Readiness is gated on the watcher's own `watching <address>` banner.
Exposes a command (`/watcher status|stop`) and a tool the bootstrap/shutdown skills can call.

### §S3 — Skills in the package
`skills/` holds the Model B-owned bundles (the same `skills-src/` content, or a build step in
`generator/build.py` that copies them — drift-gated by `--check`). Crucible-imported bundles ride
too; their byte-faithfulness gate extends to the package copy.

### §S4 — Installer integration
`modelb-axi` learns `pi install` orchestration for the `pi` harness (DN §D8: external tools
orchestrated, never vendored): after deploying `.agents/*`, run `pi install <source>` if `pi` is
on PATH and the package is not already listed in `~/.pi/agent/settings.json` `packages[]`;
`--dry-run`/`--yes` semantics as for uv/Crucible/Sandesh in `preflight.py`. Never edit
`settings.json` directly.

### §S5 — Release step
CR-MDB-012 gains: tag → package version bump → publish (npm or git tag) → `pi install …@<version>`
smoke on a fresh Pi profile. Recorded here so 012's spec inherits it.

## Acceptance criteria

- [ ] The install guide's install step (`docs/install-guide.md`, the marked region that tells a
      fresh reader how to obtain the installer) names this package's concrete install command,
      replacing the interim note CR-MDB-037 left there (user ruling 2026-09-24: the guide points at
      the Pi package, not at a clone of the private repository).

- [ ] `package.json` validates as a Pi package (`keywords` contains `pi-package`, `pi.extensions`
      lists every extension file, no Pi core package in `dependencies`).
- [ ] `pi install <local path>` on a fresh profile loads the package; the watcher command is
      available; the Model B skills resolve by name from the package.
- [ ] The watcher extension distinguishes the three exits with a test that fakes `sandesh notify`
      exiting 0 / 2 / lock-conflict and asserts wake / restart / surface respectively.
- [ ] A Pi session with the package installed and NO `~/.agents/skills` still finds the Model B
      skills (or, if §S0 chooses installer-only skills, the package ships no `skills/` — one or
      the other, asserted).
- [ ] `modelb-axi --harnesses pi` runs `pi install` at most once (idempotent by `packages[]`
      inspection) and never modifies `settings.json` itself.
- [ ] No `~/.claude`, `~/.omp` path anywhere in the package.
- [ ] `build.py --check` covers whatever the package copies from `skills-src/`.

## Estimated size

One extension (~150 lines TS) + manifest + skills copy step + installer orchestration (~60 lines
Python) + tests. Medium.

## Risk

- Pi's package contract is measured from docs at 0.86.1 and one working package
  (`pi-archimedes`); a Pi change to the manifest schema surfaces at the next upgrade.
- ~~If §S0 chooses package-shipped hooks, 030 and 029 must land together or the hooks exist twice.~~
  Moot: §S0 chose per-project hooks (2026-09-23).
- Publishing adds an npm (or git-tag) step to the release; 012 must not be authored without §S5.

## Non-goals

- No agent definitions in the package (DN §D16(1)).
- No tool scripts in the package (they stay installer-deployed).
- No fix to `_emit_pi` here — that is CR-MDB-030.
- No OMP/Claude Code anything.
