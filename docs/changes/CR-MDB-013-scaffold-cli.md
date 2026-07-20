# CR-MDB-013 — Model B scaffold CLI (`modelb-axi init`)

**Status:** PENDING
**Type:** feature
**Priority:** P1 (the keystone deliverable)
**Depends on:** CR-MDB-002, CR-MDB-008
**Labels:** scaffold, cli, axi
**Phase:** Wave 3
**Design reference:** PRD §D10 (all items incl. the three user-finalized decisions 2026-07-21: check-in policy = candidate as drafted; project memory IN-REPO; v1 harness set = ALL researched) · §D3.1 (registry), §D5/D10.6 (memory templates), §D6 (generator), §D7 (wrapper), `DN-harness-agnostic-hooks.md`

## Context

Every rule this project forged — the registry, docs model, skill freeze, memory instantiation, git+git-flow, registrations — is convention enforced by discipline. The scaffold makes it correct-by-construction: `modelb-axi init` interrogates the user and emits a complete Model B project. v1 emits for ALL researched harnesses (Claude Code, pi, Codex CLI, Gemini CLI, Cursor, Copilot CLI, opencode/Amp) — file/symlink/settings emission here; per-harness HOOK wiring delegates to the CR-MDB-015 compiler (plug-in seam, stub emitting a "hooks pending 015" marker until it lands).

## Scope

### §S1 — AC gate tests
`tests/test_scaffold_cli.py`, wrapper-run, RED → GREEN. Tests exercise `init` NON-INTERACTIVELY (every setup query has a `--flag`) into a temp dir (`--target <tmp>`), never touching real trees; `--dry-run` prints the plan without writing.

### §S2 — CLI skeleton (repo: `scaffold/modelb_axi.py`, stdlib-only)
Verbs: `init` (the scaffold), `plan` (alias of `init --dry-run`). Setup queries, each with a flag for non-interactive use: `--name --token --acronym` (registry), `--mode solo|multi:<N>`, `--repo-shape standalone|monorepo:<sub1,sub2,…>`, `--stacks <csv from: arduino,bun,python,quarkus,rust,vscode,java>`, `--harnesses <csv|all>` (per-harness support is a FEATURE), `--owner <REPO_OWNER>` (the owner query), `--target <dir>`. Interactive mode prompts for any missing flag. AXI conventions: TOON envelope on stdout (via the deployed `toon` codec pattern), human progress on stderr, non-interactive-safe, exit 0/1.

### §S3 — emission (per project; per sub-project in monorepo)
1. `.env` (COMMITTED): `PROJECT_NAME/TOKEN/ACRONYM/ORCHESTRATOR_LABEL` (derived mode-aware: `vidushi-<token>` solo / `Mainline-<token>` label multi) + `REPO_OWNER`. `.env.local` (GITIGNORED, created empty with comment): environment keys (`CRUCIBLE_PROJECT_KEY=` placeholder).
2. Docs model: `docs/changes/README.md` (queue template: header slots Design contract/Evidence base/Ontology/Target release; empty structure-only table; Setup-tasks checklist; Notes footer) + `docs/research/.gitkeep`.
3. `AGENTS.md` (project override: identity from registry; workflow rules; the SKILL FREEZE list derived from `--stacks` — stack-relevant skills enumerated, everything else marked out-of-scope) + per-harness canonical-file emission: `CLAUDE.md` symlink → AGENTS.md (Claude Code); pi/Codex/Gemini/Cursor/Copilot/opencode/Amp each get their researched project-config anchor pointing at AGENTS.md (from DN-harness-agnostic-hooks §2 config locations; where a harness reads AGENTS.md natively, emit nothing extra — note it).
4. IN-REPO project memory: `docs/memory/` seeded from the ASSET ROOT's memory-templates filtered by `--stacks` (+ an INDEX.md); harness dirs are private caches, not emitted. **ASSET-ROOT RESOLUTION (the release/setup seam, user 2026-07-21): `$MODELB_HOME` → installed package data dir → this-repo fallback (dev mode). The scaffold NEVER assumes a model-b checkout; packaging/install of the assets = CR-MDB-014.**
5. `git init -b master` + git-flow branch setup (develop created; REQUIRED steps) + `.gitignore` (incl. `.env.local`, harness caches).
6. Registrations (LIVE systems — only when `--register` passed; default dry notes them as manual steps): Crucible project POST (+ key → `.env.local`), Sandesh setup+register for multi-mode.
7. Hook wiring: emit the 015 seam — `hooks/README.md` stating "wiring pending CR-MDB-015 compiler" + the neutral-schema placeholder file.
8. Generator hookup: AGENTS.md notes agents regenerate via the Model B installation's generator (asset root), not a per-project copy.

### §S4 — commit policy execution
`init` ends with an initial commit on develop containing EXACTLY the committed set (AGENTS.md, harness anchors/symlinks, docs/, `.env`, `.gitignore`, `docs/memory/`, hooks seam) — `.env.local` untracked. `--no-commit` skips.

## Acceptance criteria

### §S1
- [ ] `tests/test_scaffold_cli.py` exists; RED then GREEN ingested with wave-3 cycle context.

### §S2
- [ ] `scaffold/modelb_axi.py` exists, stdlib-only (AST import scan); `init --help` exits 0 listing all nine flags; `plan`/`--dry-run` writes NOTHING to `--target` (empty-dir check) and stdout parses as TOON with `axi.verb == "init"` and `dry_run: true`.

### §S3 (asserted on a solo `--stacks python --harnesses all --target <tmp>` run)
- [ ] `.env` contains all five registry keys with the derived `ORCHESTRATOR_LABEL=vidushi-<token>`; `.env.local` exists and is gitignored.
- [ ] `docs/changes/README.md` contains the four header slots and a `| CR | Title | Wave | Depends on |` table header; `docs/research/` exists.
- [ ] `AGENTS.md` contains the token, the acronym, "skill" freeze content mentioning "python", and the wave definition phrase "grouping of CRs"; `CLAUDE.md` is a symlink resolving to AGENTS.md.
- [ ] At least 4 non-Claude harness anchor files exist (per the DN's config locations) each containing "AGENTS.md".
- [ ] `docs/memory/` contains an INDEX.md and zero non-python stack templates (a `--stacks python` run must NOT emit java/rust templates; operational-commands template IS emitted — stack-neutral).
- [ ] The temp project is a git repo on `develop` with `master` existing; `git log --oneline` shows exactly one commit; `git status --porcelain` shows ONLY `.env.local` untracked (± nothing).
- [ ] `hooks/README.md` contains "CR-MDB-015".
- [ ] A `--repo-shape monorepo:a,b` run emits per-sub-project `.env` + `AGENTS.md` under `a/` and `b/`.

### §S4
- [ ] `--no-commit` leaves the repo with zero commits and a fully staged-or-untracked tree (no partial commit).

## Estimated size
L–XL. One red-green cycle + verify; the harness-anchor matrix is the bulk.

## Risk
- Harness anchor formats drift (their configs evolve) — each anchor cites the DN + its source URL; 015's emitters own the deep per-harness config.
- Live registration paths (`--register`) touch real servers — default OFF; tests never pass it.

## Non-goals
- Hook COMPILATION (015). Vercel-standard packaging/distribution + the `modelb-axi` install story (014). Rust/vscode agent generation (bespoke). Registering anything live in tests.
