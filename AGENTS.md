# Repository Guidelines

Project-level contract for every agent/session in this repo. `CLAUDE.md` is a symlink to this file (harness compatibility — the ecosystem is harness-agnostic; never de-symlink it).

## Project Overview

**Model B (MDB)** is the *authoring and distribution repo for an agent-harness workflow system* — not an application. It produces three artifact families and one installer that deploys them:

- **Skill bundles** (`skills-src/`) — Markdown instruction packs consumed by agent harnesses.
- **Generated sub-agent definitions** (`generator/`) — 16 stack×role TDD agents rendered from templates.
- **Portable lifecycle hooks** (`hooks-src/`) — one neutral schema compiled into per-harness wiring.
- **`modelb_axi`** — the `modelb-axi` CLI: universal installer (deploys the above into a user's harness dirs) + project scaffolder (`init`), and `modelb-axi release-check`, a read-only verb that reports a project's release readiness (its rendered workflow, version sources, prerequisites and, through `gh`, its environments and secrets).

Design contract: `docs/research/PRD-model-b-rationalization.md` (decisions **D1–D10**). Evidence base: `audits/2026-07-20-*.md` + `docs/research/DN-rationalization-plan-review.md`. Ontology: `docs/research/DN-model-b-language.md` (LOCKED, see Workflow Rules). Everything is authored repo-locally and reaches a user's machine only through the installer (D9/D10), which writes under `~/.agents`.

## Architecture & Data Flow

Two flows, one CLI (`modelb_axi/cli.py:main`), selected by whether `$MODELB_HOME/install.toml` exists:

```
INSTALLER (no install.toml)
  preflight.run_preflight()      # probe uv / Crucible / Sandesh -> deps verdicts
  -> harness.detect|select()     # roster: pi alone (shutil.which("pi"))
  -> deploy.deploy_assets()      # skills-src/* -> <target>/.agents/skills (store; no per-harness links)
                                 # hooks-src/scripts/* -> <target>/.agents/hooks/scripts
  -> config.write_install_toml() # LAST, atomic (tmp + os.replace); sha256 manifest

SCAFFOLD (`modelb-axi init`, scaffold.run_init)
  validate flags -> plan_files() -> render templates (_render_env, _render_agents_md incl. its
  Setup section, ...) -> docs/changes/.gitkeep  # the Crucible board holds the queue; no queue README
  -> _hook_instances(stacks, mode) -> hooks.compile_wiring()
  -> git init (+ optional commit) -> axi.envelope("init", ok, ...) on stdout
  # Model B's own docs/changes/README.md is read-only history, frozen at CR-MDB-048's merge
```

Key invariants:
- **Idempotence by hash.** `deploy.sha256_file` compares source/dest/prior-manifest hashes; hand-modified destinations are *skipped*, not clobbered, unless `--force-managed`.
- **Hook compilation is one-way.** Neutral instance `{event, matcher, command, tier, timeout, fail_direction}` → `hooks.validate_schema` → `hooks.compile_wiring` emits `.pi/extensions/*.ts` for Pi, the only harness. Pi honours `fail_direction`, so a `closed` hook is emitted like any other — there is no refusal path; a harness id outside the roster raises `UnknownHarnessError` before anything is written.
- **Machine channel vs human channel.** AXI envelopes (`modelb_axi/axi.py:envelope`) go to **stdout**; human progress lines to **stderr**.
- **Asset root resolution.** `deploy.default_asset_root()` prefers packaged `modelb_axi/_assets/…` (wheel force-include), falls back to the repo dirs.

## Key Directories

| Path | Purpose |
|---|---|
| `modelb_axi/` | The CLI package. `cli.py` (argparse shell), `scaffold.py` (init/emit), `deploy.py` (manifest deploy), `hooks.py` (schema + per-harness compiler), `config.py` (install.toml r/w), `harness.py` (roster/detect), `preflight.py` (dep probes), `axi.py` (envelope codec) |
| `skills-src/` | 15 skill bundles. Model-B-owned: `model-b`, `crucible`, `cr-authoring`, `git-workflow`, `gap-analysis`, `bootstrap`, `shutdown`, `chrome-ui-relay`, `code-health` (deployed with the rust stack). Imported from Crucible (byte-identical, see `CRUCIBLE-HANDOVER.md`): `crucible-register`, `crucible-report-{arduino,bun,java,python,rust}`. Plus `memory-templates/` |
| `generator/` | `build.py` renders `templates/{red,green,verify,fix}.md.tmpl` × `stacks/{arduino,bun,python,quarkus}.toml` → `agents/<stack>-<role>-agent.md` (16 files) |
| `hooks-src/` | `schema.md` (neutral schema v1) + `scripts/` (8 executable stdin/exit protocol scripts, no file extension) |
| `scripts/` | The tool-script asset class (7 adopted + 1 generated): `worktree-flow.py`, `schedule_db.py` (TRANSITIONAL), `skill-release-gate.py`, `rust-code-health.py`, `rust-crate-map.py`, `rust-dead-scan.py`, `gate-lock.sh`, and `toon.py` generated from `modelb_axi/toon.py`. Deployed to `~/.agents/scripts/` (`deploy.TOOL_SCRIPTS_STORE_RELDIR`) — the ONLY path a Model B surface names; never a `~/.claude` path (not Model B-owned) |
| `tools/` | Repo-only tools, never deployed (not in the wheel, unlike `scripts/`): `coverage-check.py`, the pre-merge gate's coverage check (CR-MDB-073 §S2), run from the repo root |
| `workflows-src/` | The release workflow's parts (`release/*.yml`) and its two scripts (`stamp_version.py`, `changelog_section.py`), rendered into a project's `.github/` by `modelb_axi/workflows.py` — at `init` and by `modelb-axi release-workflow` |
| `contracts/` | Interface contracts: `crucible-envelope.md`, `gate-lock.md`, `sandesh-cli.md`, `lean-ctx.md` (cross-project), `worktree-layout.md` (the `.worktrees/<cr>` string and its six consumers). Repo-only — not shipped in the wheel |
| `docs/research/` | `PRD-model-b-rationalization.md` (D1–D10) + `DN-*.md` design notes |
| `docs/changes/` | `CR-MDB-NNN-*.md` specs; `README.md` is read-only history frozen at CR-MDB-048's merge — the Crucible board holds the queue and the execution state |
| `tests/` | 109 `unittest` modules; mostly structural/contract gates |
| `archive/` | Read-only history: `BASELINE.md` (the wave-0 baseline), `wave1..3/` and `contracts/` (archived files), and `mapping.md` — the living map from every relocated path to where it lives now, gated by `tests/test_archive_mapping.py` (a CR that moves a mapped path updates its row) |
| `audits/` | Dated evidence files backing PRD decisions |

## Development Commands

```bash
# Install the CLI (uv tool; no lockfile committed)
uv tool install --python 3.14 .
modelb-axi --version

# Installer / scaffold (always sandbox with --target-root when experimenting)
modelb-axi --yes --harnesses pi --target-root /tmp/mdb-sandbox
modelb-axi init --name "Foo" --token foo --acronym FOO --stacks python \
  --mode solo --target /tmp/foo --dry-run     # --dry-run writes NOTHING

# Regenerate sub-agent definitions (deterministic; --check fails on drift)
python3 generator/build.py --list
python3 generator/build.py --check
python3 generator/build.py --stacks python --roles red,green

# Tests — see "Testing & QA" (every run goes through the Crucible client)
python3 ~/.crucible/clients/python-crucible.py test --agent <agent-id> --log /tmp/full.log

# The pre-merge gate's coverage check (stdlib; writes nothing; exit 0 pass, 1 drop, 2 error)
python3 tools/coverage-check.py test-reports/vidushi-mdb/coverage.lcov   # [--baseline <path>], default ./AGENTS.md

# Lint (CR-MDB-053): the rule set lives in pyproject.toml's [tool.ruff]; run from the repo root
uv tool install ruff                 # get ruff, a development tool (never a runtime dependency)
ruff check                           # exit 0 = clean; the pre-merge gate's first step
```

There is **no** Makefile/justfile. Ruff is configured, as a development tool, with the rule set pinned in `pyproject.toml`; no formatter or type checker is. `ruff check` is the only lint command; beyond its rules, match surrounding style by hand. One workflow runs on GitHub, `.github/workflows/release.yml`:

- its test job runs the suite on every release, hotfix and `master` push and every published release, on a clean runner, outside any agent session;
- it rehearses the release on release and hotfix pushes (the stamped dev version to TestPyPI, the npm dry-run publish, the notes check);
- it creates the release from the `master` push (recovery: dispatch the workflow on `master`);
- it publishes to PyPI and npm on the release event, every publish gated on the tests;
- the workflow is rendered from `workflows-src/`, never hand-edited: `modelb-axi release-workflow` renders it again.

A brief that may run `modelb-axi` pins `--modelb-home` / `--target-root` and exports `MODELB_HOME`, `XDG_DATA_HOME`, `HOME` and `PI_CODING_AGENT_DIR` to sandbox dirs, so no run touches the real installation.

## Code Conventions & Common Patterns

- **Stdlib only.** `pyproject.toml` declares zero runtime dependencies. `argparse`, `pathlib`, `tomllib`, `hashlib`, `subprocess`, `shutil`, `string.Template`, `json`, `re`. Adding a third-party import is a design change — raise it first. There is no TOML *writer* in stdlib, hence the hand-rolled serializer in `config.py`.
- **Plain dicts, not dataclasses.** Hook instances, manifests, and compiler reports are `dict` / `list[dict]`. Type hints on signatures (`def compile_wiring(...) -> dict:`), module-level docstrings citing the governing CR section (`"""… (CR-MDB-015 §S2/§S4)."""`).
- **Typed exceptions, exit codes from `main()`.** `ScaffoldError`, `DeployError`, `UnknownHarnessError`. Validate everything *before* the first write; a failed run leaves no `install.toml`.
- **Atomicity.** Config writes go through a temp file + `os.replace` in the same directory.
- **No async, no DI, no globals-as-state.** State flows through function arguments and return values; subprocess calls are synchronous.
- **Naming.** Private helpers `_leading_underscore`; env/flag precedence is always *flag > env > default* (`resolve_modelb_home`, `resolve_target_root`).
- **Hook scripts** (`hooks-src/scripts/*`): python3, stdlib-only, harness-agnostic, read a JSON payload on stdin, `exit 0` = allow, `exit 2` + `{"decision":"block","reason":…}` = block. Any `block-*` script is *security-class* and MUST declare `fail_direction`. Informational hooks never block. Missing git/project root → silently allow.
- **Fix the source, never the output.** Never hand-edit a rendered agent definition or a deployed skill — fix `generator/` or `skills-src/`, then re-render (`generator/build.py build`) or redeploy. An emergency live fix is recorded, and carried back to the source, in the same session.
- **Docs.** Sections are `§S1, §S2, …` and are cited from code, tests, and commit messages. PRD decisions are `D1–D10`. CR ids are flat `CR-MDB-NNN`.
- **Commits.** Conventional commits (`type(scope): desc`). **Never** add AI/Claude attribution of any kind. Work happens on `develop`; feature branches `feature/CR-MDB-NNN-<slug>`.

## Important Files

- `modelb_axi/cli.py` — entry point (`[project.scripts] modelb-axi = "modelb_axi.cli:main"`), also runnable as `python3 -m modelb_axi`.
- `pyproject.toml` — hatchling; `force-include` maps `skills-src`, `generator`, `scripts`, `hooks-src`, `workflows-src` into `modelb_axi/_assets/` (`contracts/` is repo-only: no runtime consumer, not in the wheel or the sdist). **Any new asset root must be added there or it will not ship in the wheel.**
- `pyproject.toml`'s `[tool.coverage.run]` (`source`, `patch = ["subprocess"]`) and `[tool.coverage.report]` (`omit` of the generated `scripts/toon.py`) — the config every coverage run measures under (CR-MDB-073 §S1); `source`, comma-joined in order, is the `--cov-source` every coverage command names and the areas `tools/coverage-check.py` reports.
- `pyproject.toml`'s `[tool.ruff]` (`required-version`, `target-version`, `extend-include` of the extensionless hook scripts, `extend-exclude` of the generated and non-shipped trees) and `[tool.ruff.lint]` (`select`) — Model B's pinned lint rule set (CR-MDB-053 §S1), beside the coverage tables; `ruff check` from the repository root runs it.
- `.env` — static naming registry (gitignored; must exist locally): `PROJECT_NAME`, `PROJECT_TOKEN=modelb`, `PROJECT_ACRONYM=MDB`, `ORCHESTRATOR_LABEL=vidushi-mdb`, `REPO_OWNER=antojk`, `CRUCIBLE_PROJECT_KEY`.
- `hooks-src/schema.md` — the neutral hook schema v1; the compiler in `hooks.py` is its only consumer.
- `skills-src/CRUCIBLE-HANDOVER.md` — provenance + maintenance contract for the 6 imported bundles. Model B owns their content/bundling/deploy; the Crucible repo owns the client code. Keep imported bundles byte-faithful unless a doc-sync is explicitly in scope.
- `docs/changes/README.md` — read-only history, frozen at CR-MDB-048's merge: the queue and the execution state are on the Crucible board (filed with `cr-plan`/`cr-depends`/`wave-sequence`). Never run `queue-file` against it — it would replace the board's queue with its rows.
- `contracts/*.md` — the interface you must honour when touching Crucible/Sandesh/lean-ctx integration.
- `.claude/settings.local.json` — local tool permission allowlist only.

## Runtime/Tooling Preferences

- **Python ≥ 3.14** (`tomllib`); the published floor, `requires-python = ">=3.14"`. Package manager: **uv** (`uv tool install --python 3.14 .`); no `uv.lock`, no `requirements.txt`.
- Crucible's installed clients, `~/.crucible/clients/<stack>-crucible.py` (listed in `~/.crucible/crucible-clients.json`, installed by Crucible's own installer), are the only sanctioned client surface — never a checkout of the Crucible project. Model B ships, vendors and maintains none of them.
- Prefer lean-ctx reads (`ctx_read`/`ctx_search`/`ctx_shell`/`ctx_tree`) over raw file/grep/shell calls.
- Confirm destructive operations; delegate super-user ops to the user.
- Crucible: the **production** board only (`127.0.0.1:3849`), reached through the released client's API — never its database, never a dev instance.
- Model B never mutates `~/.claude` directly — the `modelb-axi` installer is the only deployment channel (PRD §D9/§D10), and the repo-local authoring rule means no CR writes there at all. The user's own dotfile-manager discipline is out of scope for this file.
- **Electronics stack is EXCLUDED** (anthill-forge dead) — never migrate, document, or generate it.

## Testing & QA

Pure **`unittest`** — no pytest, no `conftest.py`, no fixtures/markers. 109 modules in `tests/` (`tests/test_*.py`), each file ending in `if __name__ == "__main__": unittest.main()`. Naming as practised: the wave-1/2 modules use `<Topic><Section>Test` classes (e.g. `ContractsS2Test`) with `test_s<n>_<assertion>` methods; later modules use `<Feature>Test` classes (e.g. `BlockDirectCargoTestScriptTest`) with descriptive method names. A helper more than one module needs lives once in `tests/_helpers.py` and is imported (CR-MDB-032 §S3 gates a module-level helper body defined in two modules).

Every test run goes through the Crucible client, which runs the suite and ingests the result — never a test runner invoked directly. A runner the client cannot drive is a client gap, raised with Crucible.

```bash
python3 ~/.crucible/clients/python-crucible.py test --tests tests.test_hooks --agent CR-MDB-NNN-<cycle id>-RED  # one module
python3 ~/.crucible/clients/python-crucible.py test --tests tests.test_contracts.ContractsS2Test --agent CR-MDB-059-237-RED  # one class
python3 ~/.crucible/clients/python-crucible.py test --agent vidushi-mdb --log /tmp/full.log  # full suite
env HOME="$(mktemp -d)" PYTHONUSERBASE="$HOME/.local" python3 ~/.crucible/clients/python-crucible.py test --agent vidushi-mdb  # empty HOME
python3 ~/.crucible/clients/python-crucible.py test --python python3.14 --agent vidushi-mdb  # another interpreter
python3 ~/.crucible/clients/python-crucible.py regression --coverage --cov-source modelb_axi,scripts,hooks-src/scripts,workflows-src,tools \
  --agent vidushi-mdb --project-dir "$PWD"
```

Coverage baseline: 5840/6391 lines (91.4%), the total measured under `pyproject.toml`'s `[tool.coverage]` config (the report omitting `scripts/toon.py`) by CR-MDB-081's pre-merge gate, 2026-10-19.

Model B's pre-merge gate lints Model B's own Python (CR-MDB-053 §S5), then measures the coverage of the package and every script (CR-MDB-073 §S3), in order:

1. **Lint.** `ruff check` from the repository root exits 0, before the gate run; a finding is fixed on the branch before the gate runs.
2. **Clear the stale data.** Remove `test-reports/vidushi-mdb/.coverage` and every `.coverage.*` beside it. The lcov step merges a run into any data file already there, so a stale one would inflate the figure.
3. **The real-`HOME` run:** `env MODELB_HOME="$(mktemp -d)" XDG_DATA_HOME="$(mktemp -d)" PI_CODING_AGENT_DIR="$(mktemp -d)" python3 ~/.crucible/clients/python-crucible.py pre-merge-gate --cov-source modelb_axi,scripts,hooks-src/scripts,workflows-src,tools --agent vidushi-mdb --cycle <last cycle> --log /tmp/gate.log`.
4. **The other two runs:** the empty-`HOME` run and the clean-runner run stay `test` runs.
5. **The check:** `python3 tools/coverage-check.py test-reports/vidushi-mdb/coverage.lcov` runs against the branch's `AGENTS.md`. Close-out step 1 has merged develop in, so that file carries develop's baseline. The tool's table goes into the merge sign-off.
6. **A drop** (exit 1) needs the user's explicit approval at sign-off.
7. **The orchestrator records the new total** on the `Coverage baseline:` line, in the close-out's docs-only status-flip commit. That includes a drop the user approved.

- **The first figure.** The `Coverage baseline:` line was added in CR-MDB-073's first cycle, from a measurement under the `[tool.coverage]` config. CR-MDB-073's own gate checks against it, and its status flip records the gate's figure.
- **When develop moves before the merge,** the post-merge develop gate is a coverage run, run as steps 2–3, and a changed total is recorded on develop in a docs-only commit.
- **A `pre-merge-gate` run does not replace the full-suite `test` command** shown above; the `regression --coverage` example names the same `--cov-source`.

- **Agent ids:** free-form, and a READABILITY habit rather than a parsed key — TDD-role agents by convention `CR-MDB-NNN-<cycle id>-<ROLE>`, the cycle's server id (e.g. `CR-MDB-059-237-RED`), the spec pre-review `CR-MDB-NNN-SPEC-REVIEW` (a VERIFY agent registered as `report` with no cycle, before `plan-file`), orchestrator ops `vidushi-mdb`. The id is assigned by the dispatcher and never minted by the agent; the ROLE is declared at registration via `--role` from the case-exact set `{RED, GREEN, FIX, VERIFY, ORCHESTRATOR, report}` and is never inferred from the id's shape, and the four TDD roles must additionally bind their cycle with `--cycle <id>` (the server refuses an unbound TDD registration 409). Read the client's agent-naming header rather than improvising.
- JUnit XML lands in `test-reports/<agent>/` — the client's per-agent reports directory for `test --agent <agent>` — as `TEST-<module>.<Class>-<YYYYMMDDHHMMSS>.xml` (gitignored; the client wipes it before each run).
- **Most tests are structural gates, so ordinary edits break them.** They assert repo layout, the state a sandboxed install deploys, SKILL.md frontmatter, byte-identity of imported bundles, reference-router parity, and grep-gates for retired terms (e.g. zero `WORKFLOW_CYCLE_ID`). Renaming a skill, doc, or reference file requires updating its gate.
- Tests import `modelb_axi` directly — run them from the repo root.
- **The suite is expected to be GREEN, and hermetic** — no test writes to or depends on the real home, except to read Crucible's installed clients (CR-MDB-032 §S1/§S2) and one installed Pi package's released source — the pi-subagents service key, under `$PI_CODING_AGENT_DIR`, else `~/.pi/agent` (CR-MDB-039). Baselines for the full suite through the client (`python-crucible.py test`), measured 2026-10-19 by the pre-merge gate at CR-MDB-081's `The resync rule on its own line, so the retired-verb gate passes (§S4)` cycle through the Crucible client, with `MODELB_HOME`/`XDG_DATA_HOME` pointed at temp dirs:
  - real `HOME` (Crucible clients installed): **4028 tests, 0 failures, 0 errors, 1 skip** with `PI_CODING_AGENT_DIR` also pointed at a temp dir — the pi-subagents service-key check, its package absent there (with it unset and pi-subagents installed, that check runs: 0 skips).
  - empty `HOME` (a fresh temp dir; `PYTHONUSERBASE` keeps user site-packages; `PI_CODING_AGENT_DIR` at a temp dir): **4028 tests, 0 failures, 0 errors, 12 skips**; the temp dir is still empty afterwards.
- **Every skip is an absent installed Crucible client, an absent `pi` CLI, an absent `sandesh` CLI, an absent installed pi-subagents, or a shallow clone.** A test that reads Crucible's released surface resolves it through `~/.crucible/crucible-clients.json` and skips, naming that manifest, when the manifest, its entry or the file is missing — the toon conformance oracle (2), the gate-lock read (1), the present-manifest half of `ManifestResolvedOracleS1Test` (1), the scaffolded-key resolution in `test_project_registry_schema` (1), the installed clients' `--help` flag check in `test_skill_bundle_guards` and its bite proof (2) — and `ClientContractS3Test` skips its four checks when the released client files under `~/.crucible/clients/` are absent. The `pi` CLI (with `node` and the jiti it ships) must be on `PATH`: without it the loader-driven classes skip in `setUpClass`, seven in `test_pi_hook_runtime`, four in `test_pi_worktree_isolation` and three in `test_skill_frontmatter` (its Pi skill-loader class, plus the two missing-export proofs that need a real `node`; one with `node` present). Without an installed pi-subagents, `test_pi_worktree_isolation`'s service-key contract check (1) skips, naming the path it looked for (`npm/node_modules/@gotgenes/pi-subagents/src/service/service.ts` under `$PI_CODING_AGENT_DIR`, else `~/.pi/agent`). Without `sandesh` on `PATH`, `test_sandesh_cli_forms`'s `--help` conformance class skips its three checks in `setUpClass`. A shallow clone or an absent `git` skips `test_archive_mapping`'s real-map row check (1) after every other row rule has run, because its Moved-by shas cannot be resolved. Nothing else skips. **A failure is a regression, not a known-bad** — investigate it; `audits/2026-09-21-codebase-review-tests.md` diagnoses the pre-CR-MDB-021 state.
- The pre-merge gate runs one interpreter, the 3.14 floor: the suite is not run across a matrix of Python versions.
- TDD is mandatory: RED before GREEN, never commit failing tests, clean build before every commit.

## Workflow Rules (Model B, solo)

- Solo project; orchestrator label **`vidushi-mdb`**. Sandesh project `ModelB`, address `Mainline - ModelB`.
- **Wave** = a grouping of CRs marking an execution boundary (solo: a redesign point). Setup tasks and releases are NOT waves; a release is a boundary event, not a CR.
- Plans are filed at CR start via the Crucible client: `plan-file --cr <id> --title <t> --cycle "<label>" --cycle-kind red-green --cycle "<label>" --cycle-kind verify --wave <n> --agent vidushi-mdb`; the registered `--agent` id is the plan's orchestrator (the free-text label flag is retired) and every filed cycle declares its own kind. **Cycle ids are server-assigned — never guessed.** Cycle labels: `<label> (§S…)`.
- Post a `milestone` at every workflow moment: `--type gap-analysis` when gap analysis completes, `--type design-review` when the orchestrator has folded a spec pre-review's findings into the spec, `--type stage-flip --label "<CR> <cycle label> done"` at each cycle-done; `cr-merged` fires automatically from `cr-close --commit <sha> --agent <id>`.
- Close-out order (`orchestration-common.md` § Close-out): merge `develop` into the feature branch until behind=0; run the pre-merge gate while the plan's last cycle is still active, bound to it with `--cycle`; `cycle-done`; `unregister`, then `register`, which clears the binding; the merge sign-off; the spec's `**Status:**` flip and the `Coverage baseline:` line together, the branch's last commit; the merge; `cr-close`.
- Wave-boundary gate: no-mistakes via `gate-run --intent <goal> --agent vidushi-mdb`, ingested as gate evidence. The repository's `crucible.toml` declares `[gate] skip = ["ci"]`, which the gate applies: no-mistakes' `ci` step is PR-based and a git-flow project merging directly has no PR to watch, so a gate that ran it would block until `ci_timeout`. An explicit `--skip` replaces that declaration, and `--skip ""` skips nothing. The gate reads `REPO_OWNER` from `.env`. The intent tells the gate not to stop any server it did not start.
- Ontology `docs/research/DN-model-b-language.md` is **LOCKED** — a frozen import of Crucible's `DN-model-b-language.md` (origin `a9a8f57`, imported 2026-09-21 by user ruling so no Model B surface reads the Crucible checkout). Cite it, never fork it; divergence goes to Crucible over Sandesh (#1336 lineage).
- Load-on-demand references: `model-b` skill (orchestration), `crucible` skill (test lifecycle), `cr-authoring` (CR/PRD/DN), `gap-analysis` (before any CR), `git-workflow`, `bootstrap`/`shutdown`.
