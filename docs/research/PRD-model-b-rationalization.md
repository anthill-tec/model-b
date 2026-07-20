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
- The universal sub-agent procedure (worktree boundary, Crucible lifecycle, exact TDD, report-every-run, scope, quality) relocates to `skills/model-b/references/sub-agent-procedure.md`; dispatched sub-agents load it from there.

### D2 — Three-tier dynamic loading with per-project containment
- Tier 0: the ≤100-line core (always loaded). Tier 1: skill descriptions (session list) — stack-neutral, workflow-scoped only. Tier 2: `SKILL.md` bodies on keyword trigger, parameterized (role, stack). Tier 3: skill `references/` + the `memory/` reference library, read on demand.
- **Containment rule: language/stack references are NOT skills.** A skill description leaks into every session of every project. Stack content lives in reference memory (global language refs per D5; project-level otherwise) and loads only via the stack-parameterized skills, generated agents, or a project's own AGENTS.md.
- **Skills are SHARED USER-SCOPE (user directive 2026-07-20): one copy, never duplicated per project.** Per-project containment comes from GATING, not relocation — a skill is called only when appropriate to the project's stack, enforced by the scaffold-emitted project-level `AGENTS.md` skill-freeze (D10.3).
- **Skills are BUNDLED per the Vercel skills standard (user directive 2026-07-20)** — the harness-neutral cross-agent store (`~/.agents/skills/`, symlinked into harness dirs like `~/.claude/skills/`) already used by `gh-axi`/`lavish`/`find-skills`. The `model-b`, `crucible`, `cr-authoring`, `git-workflow`, and `chezmoi` skills ship as such bundles; exact packaging fields/layout are verified against the standard's current docs at CR authoring time (wave 2) and the distribution flow lands in `DN-scaffold-packaging.md` (D10).

### D3 — Canonical Model B
- Canonical name: **Model B** (all "Plan B" occurrences renamed).
- One home: the `model-b` skill, role-parameterized `mainline | track | solo`. Absorbs `orchestration-common/mainline/track.md`, a rewritten Model B overview (replacing `plan_b_workflow_model.md`), the single- vs multi-track variation (a lane-label model, not a mode switch), `sandesh.md` usage, and the sub-agent procedure (D1) — as reference files.
- `bootstrap` / `shutdown` / `code-health` / `status-report` reference `model-b`; they do not restate it.
- **The skill carries the UNIVERSAL Model B conventions, parameterized per project (user directive 2026-07-20)** — every project instantiates them from its canonical token + acronym:
  1. *Naming registry:* one canonical token + one acronym per project; derived forms are fixed — CR ids `CR-<ACRONYM>-NNN`, Crucible agentIds per the client's documented agent-naming — TDD-phase agents `CR-<ACRONYM>-NNN-<cycle>-<PHASE>` (e.g. `CR-MDB-002-C1-RED`), orchestrator-level ops the orchestrator id (`vidushi-<short>`; tracks `<orchestrator>-tN`) — Sandesh `<Project>` / `Mainline - <Project>`, repo dir kebab-case. *Orchestrator labels are mode-aware:* single-orchestrator project → `vidushi-<projectshortname>` (vidushi is the solo default); multi-orchestrator/multi-track project → mainline is `Mainline-<projectshortname>` and each track orchestrator is `track<N>-<projectshortname>` (e.g. `track1-mdb`). The WORKFLOW_ROLE wire value stays per the ontology (`track-<n>`, absent in solo) — label and wire value are distinct. No other renderings may be minted. *Static initialization:* a project declares its registry ONCE in `.env` at the project root — `PROJECT_NAME`, `PROJECT_TOKEN` (canonical token), `PROJECT_ACRONYM`, `ORCHESTRATOR_LABEL` (mode-aware, derived), `REPO_OWNER` (the remote's owning account/organization — a SCAFFOLD SETUP QUERY answered by the user at init, e.g. personal / work / `anthill-tec`; user 2026-07-20) — alongside tool config like `CRUCIBLE_PROJECT_KEY`; clients, wrappers, and orchestrators read the registry from there instead of re-deriving it (the `WORKFLOW_*` family remains per-run workflow state, never static identity). *Monorepos:* when one repo hosts multiple sub-projects, EACH sub-project carries its own qualifying `.env` at its sub-project root (its own name/token/acronym/label/project-key); tools resolve the declared or nearest sub-project dir — never the repo root's registry on a sub-project's behalf. *Skill propagation:* propagation of registry keys (`REPO_OWNER` and future additions) into the deployed `model-b` skill rides CR-MDB-013 (the scaffold CR), whose spec names it explicitly.
  2. *Queue idiom:* `docs/changes/README.md` holds structure ONLY (CR / Title / Wave / Depends-on) + header (Design contract · Evidence base · Ontology · Target release) + dated footer Notes log + a release-boundary row; live status is DERIVED on the Crucible board (no plan / open plan / closed+merge).
  3. *Wave:* a grouping of CRs marking an execution boundary — redesign point (solo) / sync boundary (multi). Setup tasks and releases are NOT waves; a RELEASE CR bundles the final gates.
  3a. *Wave-boundary gate (user rule 2026-07-20):* the no-mistakes gate runs at every wave boundary and ingests as gate evidence. It requires a REMOTE — when the project has none, the ORCHESTRATOR ESCALATES to the user for permission to set one up, **explicitly asking WHICH owner to create it under (candidate set includes the user's personal account, work account, and the `anthill-tec` ORGANIZATION — never assume the owner)**; a LOCAL substitute gate (full regression + grep gates, ingested via `gate-report`) is used ONLY on the user's explicit denial. *Precedence with the registry (§1):* the gate reads `REPO_OWNER` from the project's `.env` registry; the explicit owner-ask happens at scaffold init (or whenever the registry lacks the key), and the escalation-with-owner-question applies ONLY when no registry value exists — NEVER re-ask at gate time when one does.
  4. *Plan/cycle idiom:* full plan filed at CR start (`plan-file --cr --title --cycles --wave <n> --orchestrator vidushi-<short>`); server-assigned cycle ids only; labels `C<n> <label> (§S…)`; kinds `red-green|verify|fix`; a cycle closes only on orchestrator confirm; every ingest carries `WORKFLOW_*` context (`WORKFLOW_ROLE` = `track-<n>`, ABSENT in solo).
  5. *Docs model:* `docs/changes/` + `docs/research/` everywhere; no ad-hoc folders (`plans/` etc.).
  Source ontology: `crucible:docs/research/DN-model-b-language.md` (LOCKED) — the skill cites it, never forks it.

### D4 — Skill consolidation
- `crucible` (rewrite): stack-parameterized; absorbs the five `crucible-report-*` skills, `agent-protocol`, and `memory/crucible-ingest.md`; documents the REAL per-stack CLI surfaces and the envelope contract (D7). Heartbeat is the `register` verb; the phantom endpoint and `heartbeat.sh` references are removed.
- `cr-authoring` (new): from `cr-prd-dn-conventions.md` + the CR/CReq/CRes half of `project-management.md` + the AC-precision rules.
- `git-workflow` (rewrite): single home for branch/commit/release discipline, absorbing its memory twin + `git-multi-account.md`.
- `chezmoi` (new): the add/apply cycle PLUS the previously missing **delete/rename procedure** (`chezmoi destroy` / `forget`; a deletion not mirrored to the source resurrects on `apply`).
- Removed skill entries (10): `crucible-report-{rust,java,bun,python,vscode}`, `agent-protocol`, `bun-red/green/regression-testing`, `quarkus-regression-testing`.

### D5 — Memory end-state: global = language references ONLY; the rest is project-level (user recommendation 2026-07-20, adopted)
- **Global user scope (`~/.claude/memory/`) keeps ONLY cross-project language/stack reference material**: `java-modern-syntax`, `java-coding-standards` (trimmed), `java-testing-practices` (absorbs `devops-environment`), `maven-best-practices` (trimmed), `quarkus-patterns`, `convex-client-server`.
- **Everything else migrates to PROJECT-level memory, instantiated by the scaffold (D10) at init** from the project's stack + mode inputs: stack orchestration mechanics (`rust-orchestration`, `java-orchestration`), operational command references, project-management practices — each project receives only the slices its stacks/mode need, with project-level overrides possible. Token efficiency: a session pays only for its own project's memory, never the whole corpus.
- Procedural/workflow content still consolidates into skills (D3/D4); the remaining global files merge or delete per the disposition table in the reviewed plan.

### D6 — Generated per-stack agents
- Role templates (`red/green/verify/fix`) + per-stack parameter files generate the arduino/bun/python/quarkus agent set (16 files). SE principles are written once — in the templates.
- Bespoke (not generated): rust ×4, vscode ×4, electronics ×4, `inbox-analyst` (similarity data shows templating would destroy real content).
- Every agent references `AGENTS.md` (+ the D1 procedure reference), never `memory/agent-baseline.md`.
- `build.py --check` (regenerate + diff) is the drift gate; hand-edits to generated files fail it.

### D7 — Crucible V2 client contract (AXI)
- **Ownership (corrected 2026-07-20): ALL `*-crucible.py` client implementation is the CRUCIBLE project's responsibility.** Model B requests it (Sandesh thread #1322/#1325), tracks it as an external dependency, and documents/consumes what Crucible ships. Model B implements no client code.
- The contract Model B tracks: `bun-crucible.py` is the reference implementation; its plan/cycle verbs (`plan-file`, `cycle-activate`, `cycle-done`, `cr-close`) are universal V2 API (live-verified: `/api/v2/plans` active); every client emits a TOON-AXI envelope on stdout (`{axi:{verb,ok,…,context,warnings[]}}`) with the human line on stderr, with no-cycle-id/no-wave guards, an `append-cycle` verb, and golden fixtures.
- Requested of Crucible: fleet conversion (python/rust/mvn/arduino), new `vscode-crucible.py`, arduino verb-surface extension, universal plan/cycle adoption.
- **ELECTRONICS STACK EXCLUDED (user 2026-07-20): anthill-forge is DEAD/DEPRECATED; `hw-crucible.py` (a shim to it), the four electronics agents, and the electronics skills are under revision — IGNORED in this delivery** (not migrated, not documented, not generated; revisit when their revision lands).
- Model B retains: `worktree-flow.py` AXI output migration; `contracts/crucible-envelope.md` mirroring Crucible's shipped schema; the crucible-skill rewrite documenting the shipped surfaces.
- Endpoints: `/api/v2/agents/{register,unregister}`, `/api/v2/runs/{parsed,compile}`, `/api/v2/plans` (+ cycles PATCH). TOON is served via `?fmt=toon`.

### D8 — MCP holdouts: contracts only, via the collaboration model
This effort ships AXI CLI **contracts** (specs in `contracts/`), not implementations: sandesh message verbs (send/reply/fetch/inbox/addressbook/register/unregister — wake + admin are already CLI), `mail-axi` (Fastmail/Gmail/Calendar), lean-ctx CLI preference. Implementations live in their own repos.
**Collaboration model (user directive 2026-07-20): Model B collaborates with the CRUCIBLE project (tracking: plans/cycles/gates/clients) and the SANDESH project (messaging: mailbox/wake/addressing) as the upstream providers of the tools Model B's skills and memory definitions require.** Requests and contracts flow over Sandesh cross-project channels; Model B skills reference the providers' SHIPPED surfaces (never fork them); provider-side defects found while dogfooding (e.g. the space-named-project zombie, the display-name-update gap) are filed WITH the owning project.

### D9 — The workshop pipeline (this repo)
The `model-b` repo is the permanent authoring workspace: `audits/`, `contracts/`, `generator/`, `skills-src/`, `archive/`, `scripts/`, `plans/`, `docs/`. Single-source rule: generated or contract-derived artifacts are authored here and synced into the chezmoi source (a deployment target for them); hand-authored one-offs keep the classic edit-in-place → `chezmoi add` flow. Every `~/.claude` deletion goes through `chezmoi destroy`/`forget` (D4 chezmoi skill); legacy content is archived under `archive/` with an old→new mapping before deletion.

### D10 — The Model B scaffold CLI (project initializer)
- **Deliverable:** an AXI-conventions CLI (working name `modelb-axi`; final name settled in the packaging DN) whose `init` verb scaffolds a Model B-driven project from inputs. **Going forward, EVERY Model B project — single or multi orchestrator, monorepo or not — is initialized through this tool** (correct-by-construction replaces convention-by-memory).
- **Inputs:** project name / canonical token / acronym; orchestration mode (`solo` | `multi <N tracks>`); repo shape (standalone | monorepo with named sub-projects); stack(s) per (sub-)project; repo owner — the remote's owning account/organization, a setup query per D3.1 (e.g. personal / work / `anthill-tec`); target harness — a SETUP QUERY (user 2026-07-21): per-harness support is a first-class FEATURE determining generator behavior and which files are emitted (e.g. the D10.7 hook wiring), while the scaffolded ecosystem itself stays harness-agnostic.
- **Outputs per (sub-)project:**
  1. `.env` static naming registry (D3.1) — including the Crucible `projectKey` captured from live registration.
  2. The standard docs model: `docs/changes/README.md` queue template (header slots: Design contract · Evidence base · Ontology · Target release; empty CR table; Notes footer) + `docs/research/`.
  3. **A project-level `AGENTS.md` override that FREEZES the skills accessible to the project** based on its stack(s) etc. — the per-project instrument of the D2 containment rule (context optimization: only stack-relevant skills/references are exposed; project-level overrides live here).
  4. **`CLAUDE.md` as a plain symlink to `AGENTS.md`** — Claude Code compatibility only. `AGENTS.md` is the canonical file because the **Model B ecosystem is agentic-harness agnostic**.
  5. **`git init` AND `git flow init` are REQUIRED scaffold steps (user 2026-07-20)** — every Model B project starts with both; plus Crucible project registration; for multi-orchestrator mode: Sandesh setup + `Mainline - <Project>` / track address registrations; the run-context wrapper plumbing (D7/WORKFLOW_*).
  6. **Project-level memory, instantiated from stack/mode-based templates (D5)** — the scaffold emits only the memory slices this project's stacks and orchestration mode require; global user scope contributes language references only.
  7. **Project-level HOOKS (user direction 2026-07-20): hooks are stack-specific concerns and scope to the PROJECT, not the user.** The scaffold emits the project's hook wiring (Claude Code: the project's `.claude/settings.json` — verified supported; other harnesses: their analogous per-project mechanism) selecting only the guards this project's stacks and mode need (e.g. cargo-test guard for rust, mvn-test guard for maven, worktree/CR guards for multi-track). Hook SCRIPT implementations follow the skills model — shared once, gated per project by the emitted wiring; global user-scope hooks shrink to the truly universal remainder (target: none). Migration of the existing global hooks rides CR-MDB-006/013. **Harness-agnosticism strategy (researched 2026-07-20, primary docs): neutral hook schema compiled per harness + shared Claude-contract script protocol, LCD core tier guaranteed portable — full survey, trade-offs, and the fail-direction refusal rule in `docs/research/DN-harness-agnostic-hooks.md`; implementation = CR-MDB-015.**
- **Check-in policy (REQUIRED; user 2026-07-21): which scaffold-generated files are COMMITTED to the project repo is FINALIZED in the CR-MDB-013 spec.** Candidate policy: commit `AGENTS.md` + the `CLAUDE.md` symlink, the `docs/` skeleton, `.gitignore`, and the per-harness hook wiring; decide the project-memory location; split `.env` into committable identity keys vs environment-local keys.
- **Packaging & deployment strategy (REQUIRED, undecided):** how the tool ships and updates (packaging form, install channel, version/update flow, relation to the chezmoi-managed user space) is settled in `docs/research/DN-scaffold-packaging.md` BEFORE implementation — options-considered belongs in the DN, not here.

## 3. Invariants & constraints
- `CLAUDE.md` symlink invariant (D1) — never de-symlinked.
- No AI attribution in commits; conventional commits.
- Structural waves execute with **no live Model B orchestrator sessions** (they cache old paths).
- Envelope changes must not break existing consumers (hooks parse today's output) — envelope wraps, one-line summaries retained.
- This project runs as a **single-orchestrator (solo) Model B project**, registered in Crucible (project "Model B", key `019f7eb8-8cad-7000-9838-854eca8e7c20`) — tests AND workflow (plans/cycles) tracked there. Dogfood: AC gates are executable pytest checks in this repo, run + ingested via `python-crucible.py`.

## 4. Success criteria
1. Always-loaded context: 621 → ≤100 lines, one file.
2. Zero references (outside `archive/`) to: `agent-baseline.md`, `orchestration-universal.md`, `Plan B`, `/api/ingest/`, `heartbeat.sh`, `/agents/heartbeat`.
3. `memory/` = the D5 reference library exactly; every skill/agent reference resolves.
4. `build.py --check` idempotent; 16 agents generated, 13 bespoke intact.
5. Every crucible client passes a register→test→unregister smoke against `localhost:3849` emitting a parseable envelope; plan verbs work cross-stack. (Client delivery is Crucible's, per D7 — this criterion gates Model B's DOCUMENTATION of them and closes only when Crucible ships.)
6. `chezmoi diff` clean after every wave; deleted files stay deleted after fresh `apply`.
