# CR-MDB-013 — Model B scaffold flow (`modelb-axi` TUI)

**Status:** PENDING
**Type:** feature
**Priority:** P1 (the keystone deliverable)
**Depends on:** CR-MDB-002, CR-MDB-008, CR-MDB-014
**Labels:** scaffold, tui, axi
**Phase:** Wave 3
**Design reference:** PRD §D10 (settled-setup bullet 2026-07-22 + the three 2026-07-21 decisions: check-in policy as drafted; project memory IN-REPO; harness anchors now for the INSTALLED set) · §D3.1 (registry + skill propagation) · §D5/D10.6 (memory templates) · §D6 (generator) · `DN-scaffold-packaging.md` · `DN-harness-agnostic-hooks.md`

## Context

Every rule this project forged — registry, docs model, skill freeze, memory instantiation, git+git-flow, registrations — becomes correct-by-construction. **AMENDED to the settled design (2026-07-22):** the scaffold is the SCAFFOLD FLOW of the ONE `modelb-axi` binary shipped by CR-MDB-014 — entered when the adaptive TUI detects `install.toml` (it replaces 014's C1 scaffold-mode stub). It is PROJECT-SPECIFIC: stack + overrides. Harness awareness: emit project anchors for the harnesses the INSTALLATION declares (read from `install.toml` per the Q1 seam — never re-asked per project); `--harnesses` is a DEV-ONLY override. Initial roster: Claude Code, Hermes, pi (pi.dev), OpenCode. Hook wiring delegates to the CR-MDB-015 compiler (seam stub). **Repo-local rule binds:** no writes to `~/.claude`/`~/.agents`; scaffold targets are the USER'S PROJECT dir (in tests: tmp sandboxes only).

**Sanctioned 014-gate amendment:** `tests/test_installer.py::test_valid_install_toml_enters_scaffold_mode_naming_cr_mdb_013` pins the C1 stub (names CR-MDB-013, exits 0); when the real flow lands it retargets to the real scaffold-mode entry contract (banner + non-interactive behavior below).

## Scope

### §S1 — AC gate tests
`tests/test_scaffold.py`, wrapper-run, RED → GREEN. Non-interactive throughout (every setup query has a flag) into `--target <tmp>`; `--dry-run` writes nothing. Amend the 014 stub gate per the sanction above.

### §S2 — scaffold flow entry + flags (in the `modelb_axi` package, stdlib-only)
`modelb-axi init` subcommand = the scaffold (works in both states; in scaffold mode the bare TUI proposes it). Flags: `--name --token --acronym` (registry), `--mode solo|multi:<N>`, `--repo-shape standalone|monorepo:<sub1,sub2,…>`, `--stacks <csv: arduino,bun,python,quarkus,rust,vscode,java>`, `--harnesses <csv>` (DEV-ONLY override of the installed set; normal path reads `install.toml`), `--owner <REPO_OWNER>`, `--target <dir>`, `--dry-run`, `--no-commit`, `--register` (default OFF). Interactive prompts (TUI, detected defaults) for missing values; `--yes`-style non-interactive completeness. Stdout: TOON envelope (`axi.verb == "init"`; non-client-adopter shape per `contracts/crucible-envelope.md` — flattened context); human progress on stderr.

### §S3 — emission (per project; per sub-project in monorepo)
1. `.env` (COMMITTED): `PROJECT_NAME/TOKEN/ACRONYM/ORCHESTRATOR_LABEL` (mode-aware: `vidushi-<token>` solo / `Mainline-<token>` multi) + `REPO_OWNER`. `.env.local` (GITIGNORED, seeded with `CRUCIBLE_PROJECT_KEY=` placeholder).
2. Docs model: `docs/changes/README.md` (queue template: four header slots, empty structure-only table, Setup-tasks checklist, Notes footer) + `docs/research/.gitkeep`.
3. `AGENTS.md` (project override: identity from registry; workflow rules incl. the post-036 run-context note — NO `WORKFLOW_CYCLE_ID` anywhere; SKILL FREEZE derived from `--stacks`) + per-harness anchors for the INSTALLED set only — Claude Code: `CLAUDE.md` symlink → AGENTS.md; Hermes / pi / OpenCode: their researched project-config anchor pointing at AGENTS.md (DN-harness-agnostic-hooks §2; where a harness reads AGENTS.md natively, emit nothing and note it).
4. IN-REPO project memory: `docs/memory/` seeded from the asset root's `memory-templates/` filtered by `--stacks` (+ INDEX.md). **Asset-root resolution (now concrete, matching shipped 014 code): `install.toml [install].asset_root` → packaged `modelb_axi/_assets` → repo checkout fallback (dev).**
5. `git init -b master` + git-flow branch setup (develop) + `.gitignore` (incl. `.env.local`, harness caches).
6. Registrations only under `--register` (Crucible project POST + key → `.env.local`; Sandesh setup+register for multi-mode); default emits them as manual-step notes.
7. Hooks seam: `hooks/README.md` ("wiring pending CR-MDB-015 compiler") + neutral-schema placeholder.
8. Generator note in AGENTS.md: agents regenerate from the INSTALLATION's generator assets, never a per-project copy.

### §S4 — commit policy execution
`init` ends with ONE initial commit on develop containing exactly the committed set (AGENTS.md, anchors, docs/, `.env`, `.gitignore`, `docs/memory/`, hooks seam); `.env.local` untracked; `--no-commit` skips cleanly.

### §S5 — registry-key propagation (PRD §D3.1 names this CR)
`skills-src/model-b/SKILL.md` (repo-local authored copy) documents the full `.env` registry key set incl. `REPO_OWNER` and the scaffold as its instantiation path — deployment rides the installer.

## Acceptance criteria

### §S1
- [ ] `tests/test_scaffold.py` exists; RED then GREEN ingested with wave-3 cycle context; the 014 stub gate amended per the sanction (real scaffold-entry contract pinned).

### §S2
- [ ] `modelb-axi init --help` exits 0 listing the flags above; with `install.toml` present and no args, scaffold mode banners and proposes `init` (non-interactive: exits 0); `--dry-run` writes NOTHING to `--target` (empty-dir check) and stdout parses as TOON with `axi.verb == "init"`, `dry_run: true`. Stdlib-only (AST import scan over the new modules).

### §S3 (solo `--stacks python --target <tmp>` run, installed set = claude-code in the test's install.toml fixture)
- [ ] `.env` has all five registry keys, `ORCHESTRATOR_LABEL=vidushi-<token>`; `.env.local` exists, gitignored, carries the `CRUCIBLE_PROJECT_KEY=` placeholder.
- [ ] Queue README has the four header slots + `| CR | Title | Wave | Depends on |` header; `docs/research/` exists.
- [ ] `AGENTS.md` contains token, acronym, python skill-freeze content, the "grouping of CRs" wave phrase, and zero `WORKFLOW_CYCLE_ID` occurrences; `CLAUDE.md` symlink resolves to AGENTS.md.
- [ ] With a multi-harness install.toml fixture (all four roster ids), each installed harness gets its anchor (or a documented native-AGENTS.md note); with the claude-only fixture, NO hermes/pi/opencode anchors are emitted.
- [ ] `docs/memory/` has INDEX.md and zero non-python stack templates (stack-neutral templates ARE emitted).
- [ ] Temp project: git repo on `develop`, `master` exists, exactly one commit, `git status --porcelain` shows only `.env.local` untracked.
- [ ] `hooks/README.md` contains "CR-MDB-015".
- [ ] `--repo-shape monorepo:a,b` emits per-sub-project `.env` + `AGENTS.md` under `a/` and `b/`.

### §S4
- [ ] `--no-commit` leaves zero commits, no partial commit.

### §S5
- [ ] `skills-src/model-b/SKILL.md` names `REPO_OWNER` and the scaffold instantiation path; zero writes to `~/.claude` anywhere (sandbox guard).

## Estimated size
L. Two red-green cycles (C1 flow+flags+dry-run · C2 emission+commit-policy+propagation) + verify; the anchor matrix shrank to the installed roster.

## Risk
- Harness anchor formats drift — anchors cite the DN + source URL; 015's emitters own deep config.
- Live registration paths (`--register`) — default OFF; tests never pass it.

## Non-goals
- Hook COMPILATION (015). Real-home deploy activation (deferred at 014 close). Rust/vscode agent generation (bespoke). Live registrations in tests.
