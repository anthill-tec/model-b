# Repository Guidelines

Project-level contract for every agent/session in this repo. `CLAUDE.md` is a symlink to this file (harness compatibility — the ecosystem is harness-agnostic; never de-symlink it).

## Project Overview

**Model B (MDB)** is the *authoring and distribution repo for an agent-harness workflow system* — not an application. It produces three artifact families and one installer that deploys them:

- **Skill bundles** (`skills-src/`) — Markdown instruction packs consumed by agent harnesses.
- **Generated sub-agent definitions** (`generator/`) — 16 stack×role TDD agents rendered from templates.
- **Portable lifecycle hooks** (`hooks-src/`) — one neutral schema compiled into per-harness wiring.
- **`modelb_axi`** — the `modelb-axi` CLI: universal installer (deploys the above into a user's harness dirs) + project scaffolder (`init`).

Design contract: `docs/research/PRD-model-b-rationalization.md` (decisions **D1–D10**). Everything is authored repo-locally; nothing writes to `~/.claude` except through the installer (D9/D10).

## Architecture & Data Flow

Two flows, one CLI (`modelb_axi/cli.py:main`), selected by whether `$MODELB_HOME/install.toml` exists:

```
INSTALLER (no install.toml)
  preflight.run_preflight()      # probe uv / Crucible / Sandesh -> deps verdicts
  -> harness.detect|select()     # roster: claude-code, hermes, pi, opencode (shutil.which)
  -> deploy.deploy_assets()      # skills-src/* -> <target>/.agents/skills (store)
                                 #   + per-harness symlinks (HARNESS_SKILL_DIRS)
                                 # hooks-src/scripts/* -> <target>/.agents/hooks/scripts
  -> config.write_install_toml() # LAST, atomic (tmp + os.replace); sha256 manifest

SCAFFOLD (`modelb-axi init`, scaffold.run_init)
  validate flags -> plan_files() -> render templates (_render_env, _render_agents_md,
  _render_queue_readme, ...) -> _hook_instances(stacks, mode) -> hooks.compile_wiring()
  -> git init (+ optional commit) -> axi.envelope("init", ok, ...) on stdout
```

Key invariants:
- **Idempotence by hash.** `deploy.sha256_file` compares source/dest/prior-manifest hashes; hand-modified destinations are *skipped*, not clobbered, unless `--force-managed`.
- **Hook compilation is one-way.** Neutral instance `{event, matcher, command, tier, timeout, fail_direction}` → `hooks.validate_schema` → `hooks.compile_wiring` emits `.claude/settings.json` (claude-code), `.opencode/plugin/modelb-hooks.ts` (opencode), `.pi/extensions/*.ts` (pi), `hooks/hermes-manual.yaml` (hermes, advisory). A `fail_direction: closed` hook is **refused** on harnesses that cannot honour it; all-refused raises `AllTargetsRefusedError`.
- **Machine channel vs human channel.** AXI envelopes (`modelb_axi/axi.py:envelope`) go to **stdout**; human progress lines to **stderr**.
- **Asset root resolution.** `deploy.default_asset_root()` prefers packaged `modelb_axi/_assets/…` (wheel force-include), falls back to the repo dirs.

## Key Directories

| Path | Purpose |
|---|---|
| `modelb_axi/` | The CLI package. `cli.py` (argparse shell), `scaffold.py` (init/emit), `deploy.py` (manifest deploy), `hooks.py` (schema + per-harness compiler), `config.py` (install.toml r/w), `harness.py` (roster/detect), `preflight.py` (dep probes), `axi.py` (envelope codec) |
| `skills-src/` | 13 skill bundles. Model-B-owned: `model-b`, `crucible`, `cr-authoring`, `git-workflow`, `chezmoi`, `bootstrap`, `shutdown`. Imported from Crucible (byte-identical, see `CRUCIBLE-HANDOVER.md`): `crucible-register`, `crucible-report-{arduino,bun,java,python,rust,vscode}`. Plus `memory-templates/` |
| `generator/` | `build.py` renders `templates/{red,green,verify,fix}.md.tmpl` × `stacks/{arduino,bun,python,quarkus}.toml` → `agents/<stack>-<role>-agent.md` (16 files) |
| `hooks-src/` | `schema.md` (neutral schema v1) + `scripts/` (7 executable stdin/exit protocol scripts, no file extension) |
| `scripts/` | The tool-script asset class (7 adopted + 1 generated): `worktree-flow.py`, `schedule_db.py` (TRANSITIONAL), `skill-release-gate.py`, `rust-code-health.py`, `rust-crate-map.py`, `rust-dead-scan.py`, `gate-lock.sh`, and `toon.py` generated from `modelb_axi/toon.py`. Deployed to `~/.agents/scripts/` (`deploy.TOOL_SCRIPTS_STORE_RELDIR`) — the ONLY path a Model B surface names; never a `~/.claude` path (chezmoi-managed, so anything written there is reverted on the next apply) |
| `contracts/` | Cross-project interface contracts: `crucible-envelope.md`, `gate-lock.md`, `sandesh-cli.md`, `lean-ctx.md`, `mail-axi.md` |
| `docs/research/` | `PRD-model-b-rationalization.md` (D1–D10) + `DN-*.md` design notes |
| `docs/changes/` | `README.md` = CR queue (structure only) + `CR-MDB-NNN-*.md` specs |
| `tests/` | 19 `unittest` modules; mostly structural/contract gates |
| `archive/` | `BASELINE.md` + `wave1..3/` historical records — read-only history |
| `audits/` | Dated evidence files backing PRD decisions |

## Development Commands

```bash
# Install the CLI (uv tool; no lockfile committed)
uv tool install .                       # or: pip install -e .
modelb-axi --version

# Installer / scaffold (always sandbox with --target-root when experimenting)
modelb-axi --yes --harnesses claude-code --target-root /tmp/mdb-sandbox
modelb-axi init --name "Foo" --token foo --acronym FOO --stacks python \
  --mode solo --target /tmp/foo --dry-run     # --dry-run writes NOTHING

# Regenerate sub-agent definitions (deterministic; --check fails on drift)
python3 generator/build.py --list
python3 generator/build.py --check
python3 generator/build.py --stacks python --roles red,green

# Tests — see "Testing & QA"
python3 -m unittest discover -s tests -t .
```

There is **no** Makefile/justfile, **no** CI (`.github/` absent), and **no** linter/formatter/type-checker configured (no `[tool.ruff|black|mypy|pytest]`). Do not invent lint commands; match surrounding style by hand.

## Code Conventions & Common Patterns

- **Stdlib only.** `pyproject.toml` declares zero runtime dependencies. `argparse`, `pathlib`, `tomllib`, `hashlib`, `subprocess`, `shutil`, `string.Template`, `json`, `re`. Adding a third-party import is a design change — raise it first. There is no TOML *writer* in stdlib, hence the hand-rolled serializer in `config.py`.
- **Plain dicts, not dataclasses.** Hook instances, manifests, and compiler reports are `dict` / `list[dict]`. Type hints on signatures (`def compile_wiring(...) -> dict:`), module-level docstrings citing the governing CR section (`"""… (CR-MDB-015 §S2/§S4)."""`).
- **Typed exceptions, exit codes from `main()`.** `ScaffoldError`, `DeployError`, `UnknownHarnessError`, `AllTargetsRefusedError`. Validate everything *before* the first write; a failed run leaves no `install.toml`.
- **Atomicity.** Config writes go through a temp file + `os.replace` in the same directory.
- **No async, no DI, no globals-as-state.** State flows through function arguments and return values; subprocess calls are synchronous.
- **Naming.** Private helpers `_leading_underscore`; env/flag precedence is always *flag > env > default* (`resolve_modelb_home`, `resolve_target_root`).
- **Hook scripts** (`hooks-src/scripts/*`): python3, stdlib-only, harness-agnostic, read a JSON payload on stdin, `exit 0` = allow, `exit 2` + `{"decision":"block","reason":…}` = block. Any `block-*` script is *security-class* and MUST declare `fail_direction`. Informational hooks never block. Missing git/project root → silently allow.
- **Docs.** Sections are `§S1, §S2, …` and are cited from code, tests, and commit messages. PRD decisions are `D1–D10`. CR ids are flat `CR-MDB-NNN`.
- **Commits.** Conventional commits (`type(scope): desc`). **Never** add AI/Claude attribution of any kind. Work happens on `develop`; feature branches `feature/CR-MDB-NNN-<slug>`.

## Important Files

- `modelb_axi/cli.py` — entry point (`[project.scripts] modelb-axi = "modelb_axi.cli:main"`), also runnable as `python3 -m modelb_axi`.
- `pyproject.toml` — hatchling; `force-include` maps `skills-src`, `generator`, `contracts`, `scripts`, `hooks-src` into `modelb_axi/_assets/`. **Any new asset root must be added there or it will not ship in the wheel.**
- `.env` — static naming registry (gitignored; must exist locally): `PROJECT_NAME`, `PROJECT_TOKEN=modelb`, `PROJECT_ACRONYM=MDB`, `ORCHESTRATOR_LABEL=vidushi-mdb`, `REPO_OWNER=antojk`, `CRUCIBLE_PROJECT_KEY`.
- `hooks-src/schema.md` — the neutral hook schema v1; the compiler in `hooks.py` is its only consumer.
- `skills-src/CRUCIBLE-HANDOVER.md` — provenance + maintenance contract for the 7 imported bundles. Model B owns their content/bundling/deploy; the Crucible repo owns the client code. Keep imported bundles byte-faithful unless a doc-sync is explicitly in scope.
- `docs/changes/README.md` — the CR queue: `| CR | Title | Wave | Depends-on |` + dated Notes. **Structure only** — live status is derived on the Crucible board, never hand-maintained here.
- `contracts/*.md` — the interface you must honour when touching Crucible/Sandesh/lean-ctx integration.
- `.claude/settings.local.json` — local tool permission allowlist only.

## Runtime/Tooling Preferences

- **Python ≥ 3.11** (`tomllib`). Package manager: **uv** (`uv tool install .`); no `uv.lock`, no `requirements.txt`.
- Sibling projects referenced by path prefix: `crucible:` = `~/Documents/data_projects/crucible`. Its `clients/*-crucible.py` are the *source of truth* — never vendor a copy unless a CR is changing the client itself.
- Prefer lean-ctx reads (`ctx_read`/`ctx_search`/`ctx_shell`/`ctx_tree`) over raw file/grep/shell calls.
- Confirm destructive operations; delegate super-user ops to the user.
- Every `~/.claude` mutation follows chezmoi discipline: no-auto temp config, manual source commits, deletions via `chezmoi destroy`/`forget` (a plain `rm` resurrects on apply). Never `chezmoi apply`, never push the source repo.
- **Electronics stack is EXCLUDED** (anthill-forge dead) — never migrate, document, or generate it.

## Testing & QA

Pure **`unittest`** — no pytest, no `conftest.py`, no fixtures/markers. 19 modules in `tests/`, classes named `<Topic><Section>Test` (e.g. `ContractsS2Test`, `BlockDirectCargoTestScriptTest`), methods `test_s2_<assertion>` in the wave-1/2 modules (wave-3+ modules use `<Feature>Test` and descriptive names — CR-MDB-032 §S6 settles the convention), each file ending in `if __name__ == "__main__": unittest.main()`.

```bash
python3 -m unittest tests.test_hooks                       # one module
python3 -m unittest tests.test_contracts.ContractsS2Test   # one class
MODELB_REALHOME_GATE=1 python3 tests/test_realhome_supersede.py
```

Canonical runs go through the Crucible client so results are ingested:

```bash
# Per-project context wrapper (pins CRUCIBLE_PROJECT_KEY + WORKFLOW_CYCLE/WORKFLOW_WAVE,
# never a cycle id — attach is server-driven). Recreate it if /tmp was cleared.
/tmp/claude-1000/modelb-crucible test --tests tests.test_hooks --agent CR-MDB-NNN-C1-RED
# Direct client equivalent:
python3 ~/Documents/data_projects/crucible/clients/python-crucible.py regression --coverage \
  --agent vidushi-mdb --project-dir "$PWD"
```

- **Agent ids:** TDD phases `CR-MDB-NNN-<cycle>-<PHASE>`; orchestrator ops `vidushi-mdb`. Read the client's agent-naming header rather than improvising.
- JUnit XML lands in `test-reports/` as `TEST-<module>.<Class>-<YYYYMMDDHHMMSS>.xml` (gitignored; the client wipes it before each run). Plain `unittest` produces console output only.
- **Most tests are structural gates, so ordinary edits break them.** They assert repo layout, deployed `~/.claude`/`~/.agents` state, SKILL.md frontmatter, byte-identity of imported bundles, reference-router parity, `chezmoi diff` cleanliness, and grep-gates for retired terms (e.g. zero `WORKFLOW_CYCLE_ID`). Renaming a skill, doc, or reference file requires updating its gate.
- `tests/test_realhome_supersede.py` touches the real home directory and **skips unless `MODELB_REALHOME_GATE=1`**.
- Tests import `modelb_axi` directly — install the package (`pip install -e .`) or run from the repo root.
- Baseline for `python3 -m unittest discover -s tests -t .`: **270 tests, 7 failures, 12 skips** (measured 2026-09-21; the earlier 240/1F/12S baseline was taken when the user's chezmoi tree happened to converge). Six failures are the `chezmoi diff` gates CR-MDB-021 retires — they compare the user's dotfile source to the user's home and flap on drift that is not a Model B property. The seventh is `test_crucible_skill.py::CrucibleSkillCRMDB011Test::test_ac7_repo_agents_md_no_longer_claims_workflow_cycle_id_injection`, a gate that forbids the string `WORKFLOW_CYCLE_ID` in this file while this paragraph must spell it to describe the gate — CR-MDB-032 §S3 scopes it. Two skips are permanently dead tests waiting for a retired origin directory (CR-MDB-032 §S1). Compare against this baseline rather than expecting a fully green run; `audits/2026-09-21-codebase-review-tests.md` has the per-test diagnosis.
- TDD is mandatory: RED before GREEN, never commit failing tests, clean build before every commit.

## Workflow Rules (Model B, solo)

- Solo project; orchestrator label **`vidushi-mdb`**. Sandesh project `ModelB`, address `Mainline - ModelB`.
- **Wave** = a grouping of CRs marking an execution boundary (solo: a redesign point). Setup tasks and releases are NOT waves; a release CR bundles the final gates.
- Plans are filed at CR start via the Crucible client: `plan-file --cr <id> --title <t> --cycle "C1 <label>" --cycle-kind red-green --cycle "C2 <label>" --cycle-kind verify --wave <n> --agent vidushi-mdb`; the registered `--agent` id is the plan's orchestrator (the free-text label flag is retired) and every filed cycle declares its own kind. **Cycle ids are server-assigned — never guessed.** Cycle labels: `C<n> <label> (§S…)`.
- Post a `milestone` at every workflow moment: `--type gap-analysis` when gap analysis completes, `--type stage-flip --label "<CR> <cycle> done"` at each cycle-done; `cr-merged` fires automatically from `cr-close --commit <sha> --agent <id>`.
- Wave-boundary gate: no-mistakes via `gate-run --intent <goal> --agent vidushi-mdb --skip ci`, ingested as gate evidence. `--skip` is needed because no-mistakes' `ci` step is PR-based and a git-flow project merging directly has no PR to watch, so the gate would block until `ci_timeout`. The gate reads `REPO_OWNER` from `.env`.
- Ontology `docs/research/DN-model-b-language.md` is **LOCKED** — a frozen import of Crucible's `DN-model-b-language.md` (origin `a9a8f57`, imported 2026-09-21 by user ruling so no Model B surface reads the Crucible checkout). Cite it, never fork it; divergence goes to Crucible over Sandesh (#1336 lineage).
- Load-on-demand references: `model-b` skill (orchestration), `crucible` skill (test lifecycle), `cr-authoring` (CR/PRD/DN), `gap-analysis` (before any CR), `git-workflow`, `chezmoi`, `bootstrap`/`shutdown`.
