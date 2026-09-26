# PRD — Model B Rationalization (memory → dynamic skill tree, AXI-complete tooling)

**Author:** Antony (antonyj)
**Co-author:** Claude Fable 5 (solo orchestrator — Model B)
**Status:** ACTIVE (design contract)
**Sources:** audits/2026-07-20-{memory-corpus,crucible-drift,skills-agents-inventory}.md · lavish-reviewed plan (plans/2026-07-20-rationalization-plan.md) · live Crucible verification 2026-07-20

## 1. Problem

The `~/.claude` user space grew organically into 24 memory files, ~50 skills, 29 agent definitions and ~20 scripts with four systemic defects:

1. **Always-loaded bloat.** `CLAUDE.md` → `AGENTS.md` is one 621-line file serving as config index AND sub-agent procedure; every session and every dispatched sub-agent ingests all of it.
2. **No canonical Model B definition.** The workflow model is scattered across `orchestration-*`, `sandesh.md`, a broken `plan_b_workflow_model.md` (verbatim mis-paste), and four skills — under two names ("Plan B" / "Model-B").
3. **Duplicated foundations.** The same SE principles are restated per stack: fix/verify agents 52–54% verbatim-identical across small stacks; per-stack TDD/crucible skills repeat one procedure five ways; skill↔memory twins (git-workflow ×2, crucible ×3, orchestration ×5).
4. **Doc↔tool drift.** The crucible skill promises a client-side TOON-AXI envelope no client emits; `agent-protocol` documents a phantom `/api/v2/agents/heartbeat` and a nonexistent `heartbeat.sh`; `java-orchestration.md` uses dead `/api/ingest/*` paths; vscode has no crucible client; arduino has only `unit`/`compile`.

## 2. Design contract

### D1 — Frugal always-loaded core
- `AGENTS.md` is THE core file: ≤100 lines. Content: the non-negotiables as one-liners (no AI attribution; import hygiene; TDD discipline; clean-build-before-commit; destructive-op confirmation; lean-ctx tool preference) + the **topic → skill/memory trigger table** + project-classification pointers.
- **Invariant: `CLAUDE.md` is ALWAYS a symlink to `AGENTS.md`.** One physical file serves both entrypoint names.
  **AMENDED 2026-09-25 (CR-MDB-035, CR-MDB-031, DN-multi-harness §D14):** Model B emits no `CLAUDE.md`; `AGENTS.md` is the only project-context file it writes. The symlink served Claude Code, which §D14 dropped; CR-MDB-031 removed it.
- The universal sub-agent procedure (worktree boundary, Crucible lifecycle, exact TDD, report-every-run, scope, quality) relocates to `skills/model-b/references/sub-agent-procedure.md`; dispatched sub-agents load it from there.

### D2 — Three-tier dynamic loading with per-project containment
- Tier 0: the ≤100-line core (always loaded). Tier 1: skill descriptions (session list) — stack-neutral, workflow-scoped only. Tier 2: `SKILL.md` bodies on keyword trigger, parameterized (role, stack). Tier 3: skill `references/` + the `memory/` reference library, read on demand.
  **AMENDED 2026-09-25 (CR-MDB-035, D5 amendment of 2026-09-21):** the reference library is `skills-src/memory-templates/`, scaffolded per stack into `<project>/docs/memory/` (§4 criterion 3); there is no `memory/` tier.
- **Containment rule: language/stack references are NOT skills.** A skill description leaks into every session of every project. Stack content lives in reference memory (global language refs per D5; project-level otherwise) and loads only via the stack-parameterized skills, generated agents, or a project's own AGENTS.md.
  **AMENDED 2026-09-25 (CR-MDB-035, D5 amendment of 2026-09-21):** there is no global memory tier; stack references are project-level memory templates (D5).
- **Skills are SHARED USER-SCOPE (user directive 2026-07-20): one copy, never duplicated per project.** Per-project containment comes from GATING, not relocation — a skill is called only when appropriate to the project's stack, enforced by the scaffold-emitted project-level `AGENTS.md` skill-freeze (D10.3).
- **Skills are BUNDLED per the Vercel skills standard (user directive 2026-07-20)** — the harness-neutral cross-agent store (`~/.agents/skills/`, symlinked into harness dirs like `~/.claude/skills/`) already used by `gh-axi`/`lavish`/`find-skills`. The `model-b`, `crucible`, `cr-authoring`, `git-workflow`, and `chezmoi` skills ship as such bundles; exact packaging fields/layout are verified against the standard's current docs at CR authoring time (wave 2) and the distribution flow lands in `DN-scaffold-packaging.md` (D10).
  **AMENDED 2026-09-25 (CR-MDB-035, CR-MDB-031, DN-multi-harness §D14):** skills live once in `~/.agents/skills/`, which Pi reads directly; the installer creates no per-harness links. The `chezmoi` bundle is no longer a Model B bundle — CR-MDB-031 retired it.

### D3 — Canonical Model B
- Canonical name: **Model B** (all "Plan B" occurrences renamed).
- One home: the `model-b` skill, role-parameterized `mainline | track | solo`. Absorbs `orchestration-common/mainline/track.md`, a rewritten Model B overview (replacing `plan_b_workflow_model.md`), the single- vs multi-track variation (a lane-label model, not a mode switch), `sandesh.md` usage, and the sub-agent procedure (D1) — as reference files.
- `bootstrap` / `shutdown` / `code-health` / `status-report` reference `model-b`; they do not restate it.
  **AMENDED 2026-09-25 (CR-MDB-035):** there is no `status-report` bundle; `bootstrap`, `shutdown` and `code-health` ship (`skills-src/`).
- **The skill carries the UNIVERSAL Model B conventions, parameterized per project (user directive 2026-07-20)** — every project instantiates them from its canonical token + acronym:
  1. *Naming registry:* one canonical token + one acronym per project; derived forms are fixed — CR ids `CR-<ACRONYM>-NNN`, Crucible agentIds per the client's documented agent-naming — TDD-phase agents `CR-<ACRONYM>-NNN-<cycle>-<PHASE>` (e.g. `CR-MDB-002-C1-RED`), orchestrator-level ops the orchestrator id (`vidushi-<short>`; tracks `<orchestrator>-tN`) — Sandesh `<Project>` / `Mainline - <Project>`, repo dir kebab-case. *Orchestrator labels are mode-aware:* single-orchestrator project → `vidushi-<projectshortname>` (vidushi is the solo default); multi-orchestrator/multi-track project → mainline is `Mainline-<projectshortname>` and each track orchestrator is `track<N>-<projectshortname>` (e.g. `track1-mdb`). The WORKFLOW_ROLE wire value stays per the ontology (`track-<n>`, absent in solo) — label and wire value are distinct. No other renderings may be minted. *Static initialization:* a project declares its registry ONCE in `.env` at the project root — `PROJECT_NAME`, `PROJECT_TOKEN` (canonical token), `PROJECT_ACRONYM`, `ORCHESTRATOR_LABEL` (mode-aware, derived), `REPO_OWNER` (the remote's owning account/organization — a SCAFFOLD SETUP QUERY answered by the user at init, e.g. personal / work / `anthill-tec`; user 2026-07-20) — alongside tool config like `CRUCIBLE_PROJECT_KEY`; clients, wrappers, and orchestrators read the registry from there instead of re-deriving it (the `WORKFLOW_*` family remains per-run workflow state, never static identity). *Monorepos:* when one repo hosts multiple sub-projects, EACH sub-project carries its own qualifying `.env` at its sub-project root (its own name/token/acronym/label/project-key); tools resolve the declared or nearest sub-project dir — never the repo root's registry on a sub-project's behalf. *Skill propagation:* propagation of registry keys (`REPO_OWNER` and future additions) into the deployed `model-b` skill rides CR-MDB-013 (the scaffold CR), whose spec names it explicitly.
     **AMENDED 2026-09-26 (user ruling, CR-MDB-041):** the registry gains `SANDESH_PROJECT` — the project's Sandesh project id, exactly as Sandesh knows it (case- and space-sensitive, so no other registry value can stand in for it). `init` writes it into the generic `.env` template every project gets (default: `PROJECT_NAME` with spaces removed; `--sandesh-project` overrides it); the orchestrator skills read it for every `sandesh` call and the addresses `Mainline - <SANDESH_PROJECT>` / `Track <N> - <SANDESH_PROJECT>`. It is the same value the Sandesh Pi extension reads from `$SANDESH_PROJECT`.
  2. *Queue idiom:* `docs/changes/README.md` holds structure ONLY (CR / Title / Wave / Depends-on) + header (Design contract · Evidence base · Ontology · Target release) + dated footer Notes log + a release-boundary row; live status is DERIVED on the Crucible board (no plan / open plan / closed+merge).
  3. *Wave:* a grouping of CRs marking an execution boundary — redesign point (solo) / sync boundary (multi). Setup tasks and releases are NOT waves; a RELEASE CR bundles the final gates.
  3a. *Wave-boundary gate (user rule 2026-07-20):* the no-mistakes gate runs at every wave boundary and ingests as gate evidence. It requires a REMOTE — when the project has none, the ORCHESTRATOR ESCALATES to the user for permission to set one up, **explicitly asking WHICH owner to create it under (candidate set includes the user's personal account, work account, and the `anthill-tec` ORGANIZATION — never assume the owner)**; a LOCAL substitute gate (full regression + grep gates, ingested via `gate-run`) is used ONLY on the user's explicit denial. *Precedence with the registry (§1):* the gate reads `REPO_OWNER` from the project's `.env` registry; the explicit owner-ask happens at scaffold init (or whenever the registry lacks the key), and the escalation-with-owner-question applies ONLY when no registry value exists — NEVER re-ask at gate time when one does.
  4. *Plan/cycle idiom:* full plan filed at CR start (`plan-file --cr <id> --title <t> --cycle "C1 <label>" --cycle-kind red-green --cycle "C2 <label>" --cycle-kind verify --wave <n> --agent <registered-id>`, the registered agent id BEING the plan's orchestrator); server-assigned cycle ids only; labels `C<n> <label> (§S…)`; kinds `red-green|verify|fix` declared once per cycle; a cycle closes only on orchestrator confirm; every ingest carries `WORKFLOW_*` context (`WORKFLOW_ROLE` = `track-<n>`, ABSENT in solo).
  5. *Docs model:* `docs/changes/` + `docs/research/` everywhere; no ad-hoc folders (`plans/` etc.).
  Source ontology: `docs/research/DN-model-b-language.md` (LOCKED; frozen import of Crucible's, origin `a9a8f57`, imported 2026-09-21) — the skill cites it, never forks it.

### D4 — Skill consolidation
- `crucible` (rewrite): stack-parameterized; absorbs the five `crucible-report-*` skills, `agent-protocol`, and `memory/crucible-ingest.md`; documents the REAL per-stack CLI surfaces and the envelope contract (D7). Heartbeat is the `register` verb; the phantom endpoint and `heartbeat.sh` references are removed. **Absorb decision REAFFIRMED at the CR-MDB-016 handover (user Option B, 2026-07-28): `agent-protocol` stays absorbed, never re-imported standalone — its since-become-real v2 touch surface (`/api/v2/agents/heartbeat`, same upsert handler as register) is documented inside the crucible skill; its `heartbeat.sh` helper is NOT adopted (the clients' `register` verb covers the status-change touch); its MDX-platform content (CodeForge/Velocity) is out of Model B scope.**
- `cr-authoring` (new): from `cr-prd-dn-conventions.md` + the CR/CReq/CRes half of `project-management.md` + the AC-precision rules.
- `git-workflow` (rewrite): single home for branch/commit/release discipline, absorbing its memory twin + `git-multi-account.md`.
- `chezmoi` (new): the add/apply cycle PLUS the previously missing **delete/rename procedure** (`chezmoi destroy` / `forget`; a deletion not mirrored to the source resurrects on `apply`).
  **AMENDED 2026-09-25 (CR-MDB-035, CR-MDB-031):** the `chezmoi` skill is retired from Model B; chezmoi discipline is the user's own.
- Removed skill entries (10): `crucible-report-{rust,java,bun,python,vscode}`, `agent-protocol`, `bun-red/green/regression-testing`, `quarkus-regression-testing`.

### D5 — Memory end-state: global = language references ONLY; the rest is project-level (user recommendation 2026-07-20, adopted)
- **Global user scope (`~/.claude/memory/`) keeps ONLY cross-project language/stack reference material**: `java-modern-syntax`, `java-coding-standards` (trimmed), `java-testing-practices` (absorbs `devops-environment`), `maven-best-practices` (trimmed), `quarkus-patterns`, `convex-client-server`.
  **AMENDED 2026-09-21 (user ruling, after DN-multi-harness §D14 dropped Claude Code):** the global tier has no Pi home. The five Java-family refs are now Model B memory templates — `skills-src/memory-templates/java-{coding-standards,testing-practices,modern-syntax,maven-best-practices,quarkus-patterns}.md` (the `java-` prefix is what the scaffold's stack filter keys on) — scaffolded into `<project>/docs/memory/` for java-stack projects, and `generator/stacks/quarkus.toml` cites those project-local paths. `convex-client-server` is not a Model B stack reference and stays the user's. There is no cross-project memory tier any more; the per-project tier below is the only one.
- **Everything else migrates to PROJECT-level memory, instantiated by the scaffold (D10) at init** from the project's stack + mode inputs: stack orchestration mechanics (`rust-orchestration`, `java-orchestration`), operational command references, project-management practices — each project receives only the slices its stacks/mode need, with project-level overrides possible. Token efficiency: a session pays only for its own project's memory, never the whole corpus.
- Procedural/workflow content still consolidates into skills (D3/D4); the remaining global files merge or delete per the disposition table in the reviewed plan.
  **AMENDED 2026-09-26 (user ruling):** the orchestrator is ONE role, defined once. Its rules, workflow role and expectations are common to every project and every stack, and live only in the `model-b` skill (`references/orchestration-{common,mainline,track}.md`, `sub-agent-procedure.md`, `sandesh.md`). What differs by stack is which skills and clients the orchestrator calls to perform that role; that lives in the stack's skills (`crucible-report-<stack>`, `code-health`) and the `<stack>-orchestration` memory template. A project keeps only facts: its identity in `.env` (D3.1) and its conventions in `AGENTS.md`. There is no per-project orchestrator note (`ORCHESTRATOR-<Project>`) and no orchestrator rules in project memory; the notes of that name are absorbed by CR-MDB-042.

### D6 — Generated per-stack agents
- Role templates (`red/green/verify/fix`) + per-stack parameter files generate the arduino/bun/python/quarkus/rust agent set (20 files). SE principles are written once — in the templates.
  **AMENDED 2026-09-25 (CR-MDB-035, DN-multi-harness §D17, CR-MDB-025):** Model B ships the generated stack × role set only, rendered per project by `init`/`agents` (D10.8); the installer deploys none, and counts are not stated (§4 criterion 4).
- Bespoke (not generated): electronics ×4, `inbox-analyst` (similarity data shows templating would destroy real content). Corrected by CR-MDB-024 §S4: rust ×4 became the fifth generated stack (2026-09-16 rust ruling), and the editor-overlay set was retired outright — an IDE is not a stack (2026-09-22 ruling).
  **AMENDED 2026-09-25 (CR-MDB-035, CR-MDB-025):** Model B ships no bespoke agents; the only agent definitions are the generated set rendered per project.
- Every agent references `AGENTS.md` (+ the D1 procedure reference), never `memory/agent-baseline.md`.
- `build.py --check` (regenerate + diff) is the drift gate; hand-edits to generated files fail it.

### D7 — Crucible V2 client contract (AXI)
- **Ownership (corrected 2026-07-20): ALL `*-crucible.py` client implementation is the CRUCIBLE project's responsibility.** Model B requests it (Sandesh thread #1322/#1325), tracks it as an external dependency, and documents/consumes what Crucible ships. Model B implements no client code.
- The contract Model B tracks: `bun-crucible.py` is the reference implementation; its plan/cycle verbs (`plan-file`, `cycle-activate`, `cycle-done`, `cr-close`) are universal V2 API (live-verified: `/api/v2/plans` active); every client emits a TOON-AXI envelope on stdout (`{axi:{verb,ok,…,context,warnings[]}}`) with the human line on stderr, with no-cycle-id/no-wave guards, an `append-cycle` verb, and golden fixtures.
- Requested of Crucible: fleet conversion (python/rust/mvn/arduino), arduino verb-surface extension, universal plan/cycle adoption. A new `vscode-crucible.py` was also requested and is DECLINED (user ruling, Sandesh #1370) — the VS Code stack reports through the clients already shipped; the request is closed, not pending, and is not to be re-raised.
- **Delivery status (#1330, adopted 2026-07-21): CR-CRU-030 MERGED — fleet-wide TOON-AXI conversion (bun/python/rust/mvn/arduino) via shared `_crucible_axi.py` + `toon.py`; bundle path `crucible:clients/`. `pre-merge-gate` STREAMS the gate run — wire the streaming gate, never a one-shot. CONTRACT CHANGE INBOUND (CR-CRU-036): `WORKFLOW_CYCLE_ID` is REMOVED — clients resolve the active cycle FROM THE SERVER (open plan's `status:active` cycle) and auto-attach; no active cycle ⇒ WARN + WITHHOLD the run (non-zero exit); the orchestrator's only cycle input becomes `cycle-activate`. 036 also closes the fleet coverage gap (rust/mvn/arduino gain `pre-merge-gate` + `regression --coverage`). ADOPTED STANCE: never bake `WORKFLOW_CYCLE_ID` into hook templates (D10.7/015) or the installer; Model B documents/bundles AFTER 036 lands (Crucible intimates on merge). DELIVERED (#1332, 2026-07-22): CR-CRU-036 MERGED at crucible develop `949a2f4` — the contract above is FINAL and live; the per-stack skill docs ship BUNDLED with the clients (`crucible:clients/skills/crucible-report-*/`), managed + updated by Crucible, and are the 015 hook-template reference. SUPERSEDED (2026-07-28, Sandesh #1336/#1337, user-ratified): the skills COMPONENT (content + bundling + deploy) is handed over WHOLLY to Model B — CR-MDB-016 imports the bundles into `skills-src/` as the new canonical source, Crucible's `clients/skills/` freezes after import, and future truth ships as the modelb-axi published artifact. Client CODE ownership is unchanged (still Crucible's).**
  **AMENDED 2026-09-25 (CR-MDB-035, D10 ruling of 2026-09-23):** Model B consumes the released clients at `~/.crucible/clients/`, never a Crucible checkout; the `crucible:clients/` bundle path is not a Model B surface.
- **ELECTRONICS STACK EXCLUDED (user 2026-07-20): anthill-forge is DEAD/DEPRECATED; `hw-crucible.py` (a shim to it), the four electronics agents, and the electronics skills are under revision — IGNORED in this delivery** (not migrated, not documented, not generated; revisit when their revision lands).
- Model B retains: `worktree-flow.py` AXI output migration; `contracts/crucible-envelope.md` mirroring Crucible's shipped schema; the crucible-skill work — **RESCOPED (user 2026-07-22): Crucible now bundles + maintains its own per-stack skill docs with the clients, so CR-MDB-011 shifts from "document the client surfaces" to "integrate + route to Crucible's bundled skill docs" (Model B never re-documents their surfaces).**
- Endpoints (the routes this project actually drives — a SUBSET of the V2 surface, not exhaustive): `/api/v2/agents/{register,unregister,heartbeat}`, `/api/v2/runs/{start,parsed,compile}`, `/api/v2/projects/<key>/plans` (+ cycles PATCH), `/api/v2/projects/<key>/queue` (+ `/queue/plan`, `/queue/sequence`, `/queue/depends`, `/queue/<cr>/<verb>`), `/api/v2/projects/<key>/release-proposals`, `/api/v2/projects/<key>/milestones`, `/api/v2/gates` and `/api/v2/events`. TOON is served via `?fmt=toon`.

### D8 — MCP holdouts: contracts only, via the collaboration model
This effort ships AXI CLI **contracts** (specs in `contracts/`), not implementations: sandesh message verbs (send/reply/fetch/inbox/addressbook/register/unregister — wake + admin are already CLI), `mail-axi` (Fastmail/Gmail/Calendar), lean-ctx CLI preference. Implementations live in their own repos.

**AMENDED 2026-09-25 (CR-MDB-035, CR-MDB-031):** `mail-axi` is not a Model B contract — CR-MDB-031 archived it to `archive/contracts/mail-axi.md`.

**Collaboration model (user directive 2026-07-20): Model B collaborates with the CRUCIBLE project (tracking: plans/cycles/gates/clients) and the SANDESH project (messaging: mailbox/wake/addressing) as the upstream providers of the tools Model B's skills and memory definitions require.** Requests and contracts flow over Sandesh cross-project channels; Model B skills reference the providers' SHIPPED surfaces (never fork them); provider-side defects found while dogfooding (e.g. the space-named-project zombie, the display-name-update gap) are filed WITH the owning project.

### D9 — The workshop pipeline (this repo)
The `model-b` repo is the permanent authoring workspace: `audits/`, `contracts/`, `generator/`, `skills-src/`, `archive/`, `scripts/`, `plans/`, `docs/`. **Single-source rule (AMENDED, user 2026-07-22): ALL Model B-owned artifacts are authored REPO-LOCAL (e.g. `skills-src/`); NOTHING in a CR writes `~/.claude` — deployment to the user space is EXCLUSIVELY the universal installer's job (014, invoking provider installers). This binds EVERY downstream CR (011/013/014/015/012): AC gates assert repo paths, never deployed paths.** The chezmoi flow is LEGACY: waves 1–2 legitimately deployed through it pre-installer and their history stands; chezmoi remains only for the user's own dotfile operations and for destroying legacy files (`chezmoi destroy`/`forget`, D4) with `archive/` + mapping — never as a CR deployment channel again.

**AMENDED 2026-09-25 (CR-MDB-035, CR-MDB-031):** there is no `plans/` directory (D3.5: `docs/changes/` + `docs/research/` only), and the `destroy`/`forget` reference points at the D4 `chezmoi` skill, which CR-MDB-031 retired; Model B deploys only through the installer.

### D10 — The Model B scaffold CLI (project initializer)

- **Deliverable:** an AXI-conventions CLI (working name `modelb-axi`; final name settled in the packaging DN) whose `init` verb scaffolds a Model B-driven project from inputs. **Going forward, EVERY Model B project — single or multi orchestrator, monorepo or not — is initialized through this tool** (correct-by-construction replaces convention-by-memory).
- **Inputs:** project name / canonical token / acronym; orchestration mode (`solo` | `multi <N tracks>`); repo shape (standalone | monorepo with named sub-projects); stack(s) per (sub-)project; repo owner — the remote's owning account/organization, a setup query per D3.1 (e.g. personal / work / `anthill-tec`); target harness — a SETUP QUERY (user 2026-07-21): per-harness support is a first-class FEATURE determining generator behavior and which files are emitted (e.g. the D10.7 hook wiring), while the scaffolded ecosystem itself stays harness-agnostic.
- **Outputs per (sub-)project:**
  1. `.env` static naming registry (D3.1) — including the Crucible `projectKey` captured from live registration.
  2. The standard docs model: `docs/changes/README.md` queue template (header slots: Design contract · Evidence base · Ontology · Target release; empty CR table; Notes footer) + `docs/research/`.
  3. **A project-level `AGENTS.md` override that FREEZES the skills accessible to the project** based on its stack(s) etc. — the per-project instrument of the D2 containment rule (context optimization: only stack-relevant skills/references are exposed; project-level overrides live here).
  4. **`CLAUDE.md` as a plain symlink to `AGENTS.md`** — Claude Code compatibility only. `AGENTS.md` is the canonical file because the **Model B ecosystem is agentic-harness agnostic**.
     **AMENDED 2026-09-25 (CR-MDB-035, CR-MDB-031, DN-multi-harness §D14):** `init` emits no `CLAUDE.md`; `AGENTS.md` is the only project-context file.
  5. **`git init` AND `git flow init` are REQUIRED scaffold steps (user 2026-07-20)** — every Model B project starts with both; plus Crucible project registration; for multi-orchestrator mode: Sandesh setup + `Mainline - <Project>` / track address registrations; the run-context wrapper plumbing (D7/WORKFLOW_*).
     **AMENDED 2026-09-25 (CR-MDB-035, CR-MDB-031):** the run-context wrapper plumbing is retired; skills call the installed Crucible client directly.
  6. **Project-level memory, instantiated from stack/mode-based templates (D5)** — the scaffold emits only the memory slices this project's stacks and orchestration mode require; global user scope contributes language references only.
  7. **Project-level HOOKS (user direction 2026-07-20): hooks are stack-specific concerns and scope to the PROJECT, not the user.** The scaffold emits the project's hook wiring (Claude Code: the project's `.claude/settings.json` — verified supported; other harnesses: their analogous per-project mechanism) selecting only the guards this project's stacks and mode need (e.g. cargo-test guard for rust, mvn-test guard for maven, worktree/CR guards for multi-track). Hook SCRIPT implementations follow the skills model — shared once, gated per project by the emitted wiring; global user-scope hooks shrink to the truly universal remainder (target: none). Migration of the existing global hooks rides CR-MDB-006/013. **Harness-agnosticism strategy (researched 2026-07-20, primary docs): neutral hook schema compiled per harness + shared Claude-contract script protocol, LCD core tier guaranteed portable — full survey, trade-offs, and the fail-direction refusal rule in `docs/research/DN-harness-agnostic-hooks.md`; implementation = CR-MDB-015.**
     **AMENDED 2026-09-25 (CR-MDB-035, CR-MDB-030, CR-MDB-031):** the only harness is Pi; the scaffold compiles the project's hook wiring into `.pi/extensions/` (`modelb_axi/hooks.py`).
  8. **Project-level AGENT DEFINITIONS (user ruling 2026-09-23): rendered per project and per harness, following item 7's hooks model.** An agent definition is harness-specific in both format (each harness supports its own frontmatter — the generator exists to tailor definitions to that) and location (each harness discovers agents in its own directories), and it carries project facts (stacks, acronym, orchestrator label, which Crucible client it runs). So the neutral stack × role definitions and one emitter per harness ship once in the installed package, and `init` renders definitions for the project's stacks into each targeted harness's project directory (Pi: `.pi/agents/`, which overrides Pi's global scope); a re-render command serves already-initialised projects. The installer deploys no agent definitions. Full rationale and the measured discovery order: `docs/research/DN-multi-harness-deploy-model.md` §D17.
- **Check-in policy (REQUIRED; user 2026-07-21): which scaffold-generated files are COMMITTED to the project repo is FINALIZED in the CR-MDB-013 spec.** Candidate policy: commit `AGENTS.md` + the `CLAUDE.md` symlink, the `docs/` skeleton, `.gitignore`, and the per-harness hook wiring; decide the project-memory location; split `.env` into committable identity keys vs environment-local keys.
  **AMENDED 2026-09-25 (CR-MDB-035, CR-MDB-031):** there is no `CLAUDE.md` to commit — CR-MDB-031 removed the symlink.
- **Packaging & deployment strategy (DECIDED 2026-07-22 — uv/pipx + adaptive TUI; see the settled-setup bullet below):** the full ship/update mechanics (version/update flow, relation to the chezmoi-managed user space) and options-considered are RECORDED in `docs/research/DN-scaffold-packaging.md` (the 014 DN) before implementation.
- **Installer vs scaffold split (user 2026-07-21): the UNIVERSAL INSTALLER (machine-level Model B setup) deploys the USER-LOCAL files — global memory (language refs), hook scripts, scripts/wrappers, skill bundles — per the TARGETED HARNESSES (harness selection lives primarily HERE; "all researched harnesses" is the installer's v1 target set). The SCAFFOLD is VERY PROJECT-SPECIFIC: targeted stack + project-level overrides and specifics only; its harness awareness is limited to emitting project-level anchor files for the harnesses the INSTALLATION declares (read from the installation config — never re-asked per project).**
  **AMENDED 2026-09-25 (CR-MDB-035, D5 amendment of 2026-09-21, DN-multi-harness §D14):** there is no global memory tier — language references ship as per-project memory templates (D5); the only harness is Pi, so the installer targets Pi alone.
- **Installer orchestration boundary (Crucible #1330, adopted 2026-07-21): CRUCIBLE owns, tests, and fixes the `*-crucible.py` client scripts AND ships its OWN installer — server + clients as one CLI-installable bundle, deployed per targeted agentic harness. The Model B UNIVERSAL INSTALLER (014) is an ORCHESTRATOR that DEPENDS ON and INVOKES Crucible's installer; it does NOT copy or mirror crucible clients into the user space (supersedes the earlier "Model B owns the installer framework" reading; no `~/.claude/scripts` mirror-sync). The CR-CRU-035 seam stands: Crucible builds the ambient-context core scripts + the status contract; Model B owns the hook templates + their generation (015).**
- **Model B consumes Crucible's RELEASED client (user ruling 2026-09-23).** Model B deliberately trails Crucible's development: every Model B surface runs the published client at `~/.crucible/clients/<stack>-crucible.py`, never a Crucible development checkout. A released client is less prone to break, and a checkout resolves its own development configuration (a different board). Adopting a newer client is a Crucible release reaching `~/.crucible/clients/`, never Model B pointing at unreleased code.
- **Setup design SETTLED (user, lavish review 2026-07-22):** (a) **Technology** — Python package installed via **uv/pipx** (`uv tool install modelb-axi`): isolated venv + globally exported bin, the model Sandesh already uses (`sandesh-relay` is a uv tool); npx rejected (no global CLI export; the tooling incl. the generators is Python). (b) **UX** — ONE adaptive **TUI** CLI (à la the Vercel skill installer): on launch it DETECTS ecosystem state — not set up ⇒ INSTALLER flow (harness targeting, dependency pre-flight, install-config write); set up ⇒ SCAFFOLD-GENERATOR flow (project deploy for the user-selected stack + harness); sensible defaults throughout; the scaffold subsystem runs off this TUI (013 and 014 converge on one binary — 013 = the scaffold flow, 014 = the installer flow + packaging). (c) **Dependency orchestration** — the installer pre-flight checks ALL dependant tooling (Crucible, Sandesh, and `uv` itself) and proactively installs what is missing via each provider's OWN bundle / package-repo install method (Model B's memory + skill extensions depend on Crucible's installed scripts/skills). (d) **Config** — the CLI keeps its own config under `$MODELB_HOME`, following Linux user-home (XDG) conventions as managed by the uv/pipx userspace-install defaults. (e) **Initial harness roster** — Claude Code, Hermes, pi (pi.dev), OpenCode; additional harnesses are future work; the agent-deployment shape is finalized PER supported harness. (f) **Sequencing** — **014 BEFORE 013** (the scaffold flow runs off the installed base); the queue dependency is flipped accordingly. (g) Skills deploy ONCE user-scope by the installer; the scaffold only references them.
  **AMENDED 2026-09-25 (CR-MDB-035, DN-multi-harness §D14, CR-MDB-031):** the harness roster in (e) is Pi alone; the other three were dropped by §D14 and their surfaces removed by CR-MDB-031.
- **Release ↔ setup ↔ init interaction (user 2026-07-21):** the Model B RELEASE (CR-MDB-012, git-flow from master) ships the scaffold CLI WITH ITS ASSETS (memory templates, generator templates+params), the skill bundles, and the contracts. **Model B SETUP is a distinct machine-level step** (install skills to shared user scope + `modelb-axi` onto PATH with packaged assets) — designed in the 014 DN whose scope is release→install→setup, not packaging format alone. **Per-project `init` consumes PACKAGED assets via the asset-root resolution `$MODELB_HOME` → package data → repo fallback (dev mode)** — the scaffold never assumes a model-b checkout.

### D11 — Capability contract and stack-scoped installation (2026-09-22, extends D10(c))

D10(c) settled that the installer pre-flight checks dependant tooling and offers to install what
is missing via each provider's own method. Measurement in wave 2 showed that principle was right
and its SCOPE was far too narrow: it named Crucible, Sandesh and `uv`, and said nothing about the
things that decide whether a deployed asset can execute **at all**.

**A deployed asset that cannot run is worse than an absent one**, because it looks installed. A
vanilla Pi accepts every file Model B writes and then silently cannot dispatch an agent, cannot
give it a shell, and cannot honour a `permission:` key. Nothing errors, because deploying is only
writing files; the failure surfaces layers away as an agent that "did nothing".

**The requirement has three tiers**, and they differ in who provides them and what absence costs:

1. **Harness capabilities** — the Pi extensions that make the assets executable: dispatch and the
   `tools:` allowlist, the `ctx_*` family (measured 2026-09-22: `ctx_shell` is the ONLY shell a
   dispatched agent has), and the permission layer that decides whether a granted tool may run.
   Absence of dispatch or the shell is **fatal to the whole installation** — no stack works. The
   permission layer is recommended, not fatal (amended 2026-09-24): without it `permission:` keys
   are ignored, but a read-only role stays read-only because its `tools:` line omits write tools.
2. **Model B's own tools** — the Sandesh CLI, the Crucible clients + manifest + server, and the
   bundled tool scripts (including one that needs `bash`, not `python3`). Absence disables a
   named capability: orchestration comms, or test ingest, or a specific script.
3. **Per-stack toolchains** — `cargo`/`nextest`, `mvn`, `bun`/`node`, `arduino-cli`/`g++`, and
   for python the **non-stdlib** `xmlrunner`/`coverage` that the Crucible client requires.
   Absence makes ONE stack's agents unable to test, and nothing else.

**Installation is stack-scoped.** The user selects stacks; selection decides both what is
**deployed** and what is **probed**. A python-only user receives neither the rust report bundle
nor a word about `cargo` (agent definitions are rendered per project, not installed — D10.8). Selection is a *choice*, never inferred from what happens to be on the
machine — having `cargo` installed is not a request for the rust agents.

**Probing is cheap; installing is the user's call.** Probes resolve binaries rather than executing
them (measured: `command -v` across five toolchains ≈ 1 ms; one `mvn -version` ≈ 227 ms, because
it spawns a JVM). Model B **never installs a language toolchain** — it names the provider's own
installer and offers to run that on explicit confirmation, exactly as D10(c) already required for
Sandesh. A missing tier-3 toolchain WARNs and continues: installing assets on a machine that is
not the build machine is legitimate.

Implementation: **CR-MDB-036**. Audit evidence: that CR's "Audit 2026-09-22" section.


## 3. Invariants & constraints
- `AGENTS.md` is the only project-context file Model B writes; it emits no `CLAUDE.md` (CR-MDB-031). *Amended 2026-09-25 (CR-MDB-035): replaces the D1 `CLAUDE.md` symlink invariant, which served Claude Code, dropped by DN-multi-harness §D14.*
- No AI attribution in commits; conventional commits.
- Structural waves execute with **no live Model B orchestrator sessions** (they cache old paths).
- Envelope changes must not break existing consumers (hooks parse today's output) — envelope wraps, one-line summaries retained.
- This project runs as a **single-orchestrator (solo) Model B project**, registered in Crucible (project "Model B", key `019f7eb8-8cad-7000-9838-854eca8e7c20`) — tests AND workflow (plans/cycles) tracked there. Dogfood: AC gates are executable `unittest` checks in this repo, run + ingested via `python-crucible.py`.

## 4. Success criteria
1. **Always-loaded context.** The project `AGENTS.md` that `init` scaffolds is ≤100 lines for any
   stack set and orchestration mode. *Amended 2026-09-25 (CR-MDB-035): the 621-line baseline was
   the pre-rationalization `~/.claude/AGENTS.md`, a user dotfile Model B no longer writes (D9,
   DN-multi-harness §D14, CR-MDB-031).* **Check:** `tests/test_prd_criteria.py`.
2. Zero references (outside `archive/`) to: `agent-baseline.md`, `orchestration-universal.md`, `Plan B`, `/api/ingest/`, `heartbeat.sh`, `/agents/heartbeat` — where the `/agents/heartbeat` pattern bans the phantom v1 form only: occurrences of the live `/api/v2/agents/heartbeat` surface (real since the Crucible v2 upsert; adopted at CR-MDB-016) are exempt. The `heartbeat.sh` ban stays absolute (the helper was not adopted — the clients' `register` verb covers the touch). **`.lavish/` is CARVED OUT explicitly (CR-MDB-017 V1):** it holds generated lavish-axi renderings of past review sessions whose `/api/ingest` occurrences NARRATE this very migration ("`java-orchestration.md` uses dead `/api/ingest/*` paths", "`/api/ingest/*` → `/api/v2/runs/*`", and the grep-gate list itself), exactly like the PRD/DN/audit hits at criterion-definition sites — a sweep there would falsify a record rather than fix an instruction. The carve-out is NAMED and asserted in `tests/test_client_verb_sweep.py`, never left to the incidental dot-directory and non-text-suffix skips that hid the directory from the scan before. **Check:** `tests/test_client_verb_sweep.py`.
3. **Reference library.** The D5 library is `skills-src/memory-templates/`, scaffolded per stack
   into `<project>/docs/memory/`; every `~/.agents/skills/<path>` citation in `skills-src/` and
   `generator/templates/` resolves to a file under `skills-src/`. *Amended 2026-09-25 (CR-MDB-035,
   after the D5 amendment of 2026-09-21): there is no `memory/` tier.* **Check:**
   `tests/test_prd_criteria.py`, `tests/test_scaffold.py`.
4. **Generated agents.** `python3 generator/build.py --check` reports clean; every generated
   definition comes from one `generator/stacks/*.toml` × one `generator/templates/*.md.tmpl`;
   `init` and `agents` render definitions per project; a hand-modified definition is skipped
   unless `--force-managed`, and an unmarked one is never written. *Amended 2026-09-25 (CR-MDB-035):
   the literal counts are retired — CR-MDB-024 made rust the fifth generated stack, and DN §D17 /
   CR-MDB-025 moved definitions to per-project rendering; the installer deploys none.* **Check:**
   `generator/build.py --check`, `tests/test_agent_generator.py`,
   `tests/test_pi_agent_definitions.py`.
5. **Crucible clients.** *Model B's half:* every Crucible client invocation in shipped skills,
   templates, stack parameters and contracts matches the released client's surface at
   `~/.crucible/clients/`. *Crucible's half:* the per-stack clients ship in a Crucible
   release (0.2.2: arduino, bun, mvn, python, rust); a register→test→unregister smoke per client is
   Crucible's release gate, not Model B's. `vscode-crucible.py` was declined (D7, Sandesh #1370):
   no VS Code client exists or is pending. *Amended 2026-09-25 (CR-MDB-035): Crucible shipped
   (0.2.x), so "closes only when Crucible ships" is discharged.* **Check:**
   `tests/test_client_path_anchoring.py` (`ClientContractS3Test`).
6. **Deployed state matches the manifest.** A redeploy removes managed files that left the
   manifest (a narrowed `--stacks`, a retired bundle) and never removes or overwrites unmanaged or
   hand-modified files. *Amended 2026-09-25 (CR-MDB-035): replaces "`chezmoi diff` clean after
   every wave", which measured the user's dotfile tree, not a Model B property (CR-MDB-021).*
   **Unmet until CR-MDB-040 merges. Check:** CR-MDB-040's gate.
