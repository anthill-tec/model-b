# DN — The multi-harness deploy model: one neutral source, per-harness targets

**Status:** ADOPTED (user-ruled 2026-09-18; §D16 added 2026-09-21)
**Drives:** CR-MDB-025 (Pi agent definitions), CR-MDB-020 (client-path anchoring), CR-MDB-018 (discovery
capture), CR-MDB-014 (universal installer — the flow this extends), CR-MDB-019 (hook runtime)
**Supersedes in part:** CR-MDB-025's claim that "skills already work on OMP — no work required"
(user correction 2026-09-18; see §D2)
**Measurement date:** 2026-09-18, this workstation, all figures measured not recalled

> **Reading order (added 2026-09-21).** The decisions below are a dated record and are kept in
> full so an overruled position is never re-derived. Rulings on 2026-09-18 (§D13, §D14) and
> 2026-09-21 (§D16; OMP not a target at all) supersede the earlier OMP/Claude-Code plan:
> **§D2, §D5, §D6, §D7, §D10, §D11, §D12 are SUPERSEDED in full; §D1 (byte-identity clause) and
> §D8 (OMP clause) in part.** Read §D13–§D16 first; the Consequences table below is current.
> Still binding unchanged: §D1 (neutral source + emitters), §D3, §D4, §D8 (except the OMP
> clause), §D9.

## Why this note exists

Model B ships three artifact families — skill bundles, generated agent definitions, tool
scripts — plus portable hooks, and it deploys them through one installer. Until now the deploy
model was implicit and assumed a single shared user-scope store. Two things broke that
assumption in the same session:

1. **OMP does not consume the shared store.** It has its own agent-definition format, its own
   skills location, and a plugin/extension-based hook subsystem in TypeScript — where Model B's
   hooks are python scripts.
2. **Agent definitions were never an installer asset class at all**, on ANY harness. Both
   `~/.claude/agents/` and `~/.omp/agent/agents/` hold hand-placed files today.

A deploy decision spanning five harnesses and four CRs does not belong inside one CR's scope,
which is why this is a DN and the CRs cite it.

## Measured topology

| Surface | Measured state (2026-09-18) |
|---|---|
| Harnesses present locally | **five** — `~/.claude`, `~/.omp/agent`, `~/.pi`, `~/.hermes`, `~/.config/opencode` |
| Shared store `~/.agents/` | `skills/` 21 bundles · `hooks/` 7 files · `.skill-lock.json` · **no `scripts/`** |
| `~/.claude/agents/` | 29 files — **0 symlinks, 29 real hand-placed files** (not installer-managed) |
| `~/.omp/agent/agents/` | 29 hand-modelled files |
| `~/.omp/agent/skills/` | exists, **0 entries** |
| `~/.omp/agent/managed-skills/` | exists, **0 entries** |
| `~/.omp/agent/hooks/` | **absent** — no Model B hook reaches OMP today |
| OMP deploy config | `~/.omp/agent/config.yml` — carries `modelRoles` (10 aliases) plus theme, browser, providers, astEdit, symbolPreset… i.e. the user's whole harness config |
| `install.toml` | `~/.local/share/modelb/install.toml`, version `0.1.0.dev0`, 41 managed files: 26 `agents/skills` + 7 `agents/hooks/scripts` + **0 `agents/scripts`** |

**The 29 definitions, by ownership** (identical roster on both harnesses):

| Set | Count | Owner |
|---|---|---|
| arduino/bun/python/quarkus × {red,green,verify,fix} | 16 | **Model B — generated** |
| rust × 4 | 4 | **Model B — generated** (CR-MDB-024) |
| vscode × 4 | 4 | **Model B — generated** as an editor overlay (§D4) |
| electronics × 4 | 4 | **NOT Model B** — PRD §D7 excludes them (anthill-forge dead) |
| `inbox-analyst` | 1 | **NOT Model B** — personal office-assistant agent |

So the installer will own **20 of 29** (24 once vscode lands) and must leave **5** strictly alone.

## Decisions

### D1 — One neutral agent-definition source, per-harness emitters
> *2026-09-21: the "Claude Code output must stay byte-identical" clause is RETIRED by §D14; with
> one target there is ONE emitter, `_emit_pi()` (§D16). The neutral-source principle stands.*

Agent definitions become an installer asset class with the same shape hooks already use: a
neutral declaration is authored once, and per-harness emitters render it into each harness's own
frontmatter contract. Claude Code and OMP are both emitters; neither is the source. **Claude Code
output must stay byte-identical** across this change — it is the only currently-working target,
so any diff there is a regression, not an improvement.

### D2 — OMP is served by its OWN copies, never by `~/.agents/`
> *SUPERSEDED 2026-09-21 — OMP is not a target. Pi reads the shared `~/.agents/` store natively
> (§D15.1, §D16); no per-harness copy exists.*
User ruling 2026-09-18: **OMP is the one harness that does not work with the shared `~/.agents`
set — it has its own agents and skills definitions.** Therefore OMP receives:

- agent definitions → `<agentDir>/agents/*.md`, OMP frontmatter
- skill bundles → `<agentDir>/skills/<name>/` as an **OMP-local copy**, installer-owned
- tool scripts → an **OMP-local copy**, not a reference into `~/.agents/scripts`
- hooks → TS/JS factories per §D5

This note records honestly that a measurement pointed the other way: this session's own skill
injections were stamped `[Skill directory: /home/antonyj/.agents/skills/<name>]` while both
OMP-local skill directories were empty, which is why CR-MDB-025 had recorded "skills already work
on OMP, no work required". That conclusion is WITHDRAWN by user ruling. Whatever resolution
produced those paths is treated as incidental and **must not be relied on**; the deploy model
gives OMP its own copies so correctness does not depend on it.

The other four harnesses (claude-code, pi, hermes, opencode) continue to consume the shared
`~/.agents/` store, wired the way each prefers — Claude via per-skill symlinks (19 measured).

### D3 — The installer owns ONLY what it generates, by name
Per-file ownership, recorded in the `install.toml` sha256 manifest, which already skips
hand-modified destinations rather than clobbering them. Consequences, stated so no implementer
"improves" on them:

- electronics × 4 and `inbox-analyst` are **never written and never deleted** on any harness.
- A file absent from the manifest is not Model B's, regardless of its name or location.
- "Clean up the agents directory" is not a licence to delete; removal is only ever of a file this
  installer itself previously wrote, and only when the manifest says so.

### D4 — VS Code is owned as an editor overlay, not a stack
User ruling: VS Code is an **editor**, not a language stack. The four `vscode-*` definitions are
generated from the **bun/TypeScript** stack plus an editor-overlay layer (npm, vitest,
`@vscode/test-electron`). **No `generator/stacks/vscode.toml` is created** — that would re-assert
it as a stack. This closes the drift those four currently carry (the retired `--phase` flag and
`~/.claude` skill paths) by regenerating them rather than hand-patching.

### D5 — OMP hooks are plugin/extension modules in TypeScript, and the layout is load-bearing
> *SUPERSEDED 2026-09-21 — no OMP target. The Pi hook runtime is CR-MDB-030; the "silent
> ineffectiveness" failure mode named here remains the rule to design against.*
Measured from `omp://hooks.md` and `omp://extension-loading.md`:

- A hook module **default-exports a factory** `(pi: HookAPI) => void`, registering handlers via
  `pi.on("tool_call" | "tool_result" | "session_start" | …)`.
- Native discovery scans **only** `<agentDir>/hooks/pre/*.{ts,js}` and `…/hooks/post/*.{ts,js}`
  (project: `<cwd>/.omp/hooks/pre|post/`). **A factory placed directly in `hooks/` loads nothing
  and reports no error** — silent ineffectiveness, the failure mode to fear.
- Load order is: native extension modules → JS/TS hook factories → **installed plugin entries**
  (package `omp.extensions` / legacy `pi.extensions`) → explicitly configured paths. Dedupe is by
  absolute path, first-seen wins. A non-empty declared manifest array is **authoritative** and
  suppresses index/scan fallback.
- Only `.ts`/`.js` are auto-discovered; plugin manifest entries additionally accept `.mjs`/`.cjs`.
- **`fail_direction: closed` IS honourable**: a `tool_call` handler returning `{block: true}`
  stops execution, and a handler that THROWS makes the wrapper fail closed. So security-class
  hooks must NOT be refused for OMP (contrast: the opencode emitter's refusal rule).
- Extensions are **not sandboxed** — same process, one shared `EventBus`.

Model B's seven hooks are **python3 stdin/exit-code scripts** (`exit 0` allow, `exit 2` +
`{"decision":"block","reason":…}` block). They therefore cannot be dropped in as-is. The OMP
emitter writes a thin **TS factory per hook** into `hooks/pre|post/` that invokes the python
script (`pi.exec`), maps exit 2 + the block payload onto `{block: true, reason}`, and lets a
non-zero-other or a throw fail closed for security-class hooks. The python scripts stay the
single implementation; the factory is a per-harness adapter, exactly as the neutral hook schema
already intends.

### D6 — The OMP agent directory is RESOLVED, never hardcoded
> *SUPERSEDED 2026-09-21 — no OMP target. The Pi target directory is `~/.agents/agents/` (§D16).*
`~/.omp/agent` is only the default. `omp --profile <name>` moves it to
`~/.omp/profiles/<name>/agent/`, and `PI_CODING_AGENT_DIR` overrides it outright. Every OMP path
this model writes — agents, skills, tools, hooks — resolves the active agent directory first. A
hardcoded `~/.omp/agent` is a defect that silently deploys into an inactive profile.

### D7 — `config.yml` is the USER's file: verify, never write
> *SUPERSEDED 2026-09-21 — no OMP target. The equivalent Pi rule: `~/.pi/agent/settings.json` is
> the user's file; the installer never edits it (CR-MDB-029 §S4 uses `pi install`).*
`~/.omp/agent/config.yml` carries `modelRoles` **and** the user's whole harness configuration
(theme, browser relay, provider search order, astEdit, symbolPreset, composer shape…).
Overwriting or rewriting it would destroy unrelated user state. The installer therefore:

- **never writes `config.yml`**;
- **verifies** that every `@role` alias the emitted definitions reference exists in `modelRoles`
  (measured aliases: `designer`, `smol`, `plan`, `task`, `vision`, `slow`, `advisor`, `tiny`,
  `commit`, `default`; the hand-modelled definitions use `model: "@task"`);
- **reports** a missing alias as a warning naming the alias and the file to edit, and proceeds.

This is the same "orchestrate and verify, never own another tool's config" rule §D8 applies to
Crucible and Sandesh.

### D8 — External tools are orchestrated and verified, never vendored
Unchanged from PRD §D10, restated because the tool surface grew:

- **Crucible clients** live at the install's own `clients/` directory, default
  `~/.crucible/clients/`, discovered through `crucible-clients.json` (measured six keys:
  `clients`, `version`, `status`, `config`, `server_config`, `shipped_config`). Installed by
  `crucible-axi install`. Model B reads the manifest and reports unresolved; it never vendors,
  copies, patches, or invokes their installer. **Never a personal checkout of the Crucible
  project** — a checkout carries its own `crucible.toml` and will bind a client to a development
  board (CR-MDB-020 §S0).
- **Sandesh** is a uv-installed tool on PATH, used through its CLI verbs only.
- Model B's OWN tools (`worktree-flow.py`, `toon.py`, `gate-lock.sh`, `schedule_db.py`,
  `skill-release-gate.py`, `rust-{code-health,crate-map,dead-scan}.py`) are Model B's to deploy:
  shared store for the four sharing harnesses, OMP-local copy for OMP (§D2).

### D9 — Adding an asset class does not retro-deploy; a re-run is required
Measured: this machine's `install.toml` records 41 managed files with **zero** `agents/scripts`
entries, although the current code deploys all eight tool scripts correctly (verified by a
sandboxed `MODELB_HOME=… modelb-axi --target-root …` run). The install simply predates
CR-MDB-022. So a newly added asset class reaches a machine only when the installer runs again —
and the installer flow is selected by whether `$MODELB_HOME/install.toml` exists, so
`--target-root` alone does **not** force installer mode. Any CR adding an asset class states this
rather than assuming existing installs gain it.

### D10 — OMP's plugin/marketplace system is the RIGHT distribution vehicle, and it is cheap
> *SUPERSEDED by §D15.2 — the Pi package system (CR-MDB-029) replaces the OMP marketplace.*

User direction 2026-09-18: *"OMP has an extensions and plugin API… bundling our Model B
definitions and tools as extensions may be useful."* Researched from `omp://extensions.md`,
`omp://marketplace.md`, `omp://extension-loading.md` plus public sources (upstream
`can1357/oh-my-pi`, `omp.sh/docs/extension-authoring`, and a live third-party example,
`erikh3/omp-marketplace`). The conclusion is stronger than "may be useful":

**A marketplace plugin is exactly Model B's payload.** Per `omp://marketplace.md`, a plugin is
"a directory containing Claude/OMP plugin content such as **skills, commands, agents, rules,
hooks, tools**, MCP servers, or LSP servers" — every artifact family this project ships, in one
installable, versioned unit.

**And the format is Claude-Code-compatible, which collapses two targets into one.** The catalog
lives at `.omp-plugin/marketplace.json` (preferred) or `.claude-plugin/marketplace.json`
(Claude Code fallback), and **a repository may ship BOTH — omp reads the `.omp-plugin/` copy,
Claude Code reads the `.claude-plugin/` copy, same catalog format either way.** So one Model B
marketplace repo can serve BOTH harnesses that matter, by publication rather than by file-copying
into two private directories.

**No build toolchain is required — the decisive cost finding.** OMP imports `.ts` directly
through Bun (`loadLegacyPiModule`, with an `?mtime` cache-buster), so hook/extension factories
ship as SOURCE. There is no bundler, no compile step, and no npm publish in the loop. The
`@oh-my-pi/pi-coding-agent` dependency is a **dev-only** dep for types and editor completion
(`bun add --dev`), not a runtime requirement. This matters because Model B is stdlib-only Python
with zero runtime dependencies and no JS toolchain; a plugin that needed a build would be a
genuine architectural change, and it does not.

**What this buys over copying files:** versioned installs (`omp plugin install
name@marketplace`), upgrades (`omp plugin marketplace update` → `omp plugin upgrade`),
enable/disable per scope, user-vs-project scoping, and a dev loop (`omp plugin link`) that
symlinks `~/.omp/plugins/node_modules/<name>` at a working checkout so edits load live.

**Constraints recorded so nobody designs against them:**

- **npm sources are NOT installable.** The installer rejects them: "npm plugin sources are not
  yet supported". Distribution must be GitHub shorthand, URL, git-subdir, or a relative path.
  Model B's PyPI wheel does not help here, and a `git-subdir` source is the natural fit for
  publishing out of this repo (or the Roundhouse umbrella) without a second repository.
- **A session restart is required** for newly installed tools, hooks, or extension modules.
  `/reload-plugins` refreshes only skills, slash commands and MCP servers. A release note that
  says "run `/reload-plugins`" would be wrong for our payload.
- **Naming is constrained:** lowercase alphanumerics, hyphens and dots, start/end alphanumeric,
  ≤64 chars; the `name@marketplace` id ≤128. `model-b` is valid; `Model_B` is not.
- **Extensions are not sandboxed** and share one `EventBus`; a raw `setInterval`/detached
  promise that throws is a process-level `uncaughtException` that **tears down the whole
  session**. Any periodic work must use `ctx.setInterval`/`ctx.setTimeout`, which contain the
  throw and are cleared on `session_shutdown`.
- **Hooks are the LEGACY surface.** `omp://extensions.md` is explicit: extensions are the
  unified system, and "if you need one package that owns policy, tools, command UX, and
  rendering together, use extensions." Our python hook scripts remain the implementation; the
  `.ts` factory is the adapter (§D5), and it may equally register as an extension module.

**Adopted position.** The OMP target is delivered as a **plugin**, not as a directory copy: one
Model B marketplace carrying skills, agent definitions, tool scripts and hook/extension
factories, with dual catalogs so Claude Code can consume the same repo. §D2's OMP-local copies
remain the fallback contract for a machine that installs nothing — but the plugin is the
intended path, and it changes CR-MDB-025 from "write files into `~/.omp/agent/`" to "publish a
plugin and let the harness install it". §D3's ownership rule survives unchanged and gets easier:
a plugin only ever owns its own package tree, so electronics and `inbox-analyst` are untouchable
by construction rather than by manifest discipline.

**Deliberately still open:** whether the marketplace lives in this repo (`git-subdir` source),
in the Roundhouse umbrella, or in a dedicated `model-b-marketplace` repo. Publication location
is a user decision with release-process consequences, not a technical one.

### D11 — Stay on OMP; neutralize its decision layer by configuration; "our own harness" is a NON-GOAL
> *SUPERSEDED by §D13 (target = Pi). The NON-GOAL half — never build our own harness — stands.*

Raised 2026-09-18: since Roundhouse exists to build routing on switchyard + lemonade, would
targeting **Pi** (which OMP extends) be better, given OMP's own model-switching layer convolutes
the requirement? **The problem is real; the remedy is not a harness change.**

**The problem, measured and sharper than first stated.** OMP does not merely indirect models — it
runs a per-request classifier of its own. `defaultThinkingLevel: auto` is set here, and per
`omp://models.md` the `tiny` role drives "`auto`-thinking difficulty classification". Switchyard's
`[routes.smart]` is `type = "llm_classifier"`, `classifier_target = "weak"` — a small model
inspecting each request. **Two classifiers, one layer apart, no shared signal**, deciding different
dimensions (effort vs target) that can contradict silently. That question is escalated to the root
as a design CR (drafted: `CR-RND-001`, the effort-vs-route dimension), because it is PRD/contract
territory and no layer owns it.

**Why not Pi.** Three measured objections. (1) **Pi is not installed** — no `pi` on PATH, only
`omp` (18.2.5, which moved from 18.2.1 *during this session*); `~/.pi` is legacy-compat residue
(`agent/` 10 entries, `skills/` 1). Targeting it means adopting a harness we neither run nor have
verified. (2) **OMP IS Pi plus the parts we just chose to depend on** — the compat layer is
pervasive (`legacy-pi-compat.ts`, `@mariozechner/*`/`@earendil-works/*` specifier rewrites, the
legacy `pi.extensions` manifest key, `PI_CODING_AGENT_DIR`), and dropping to base Pi most likely
forfeits the plugin/marketplace vehicle §D10 just established as the cheapest distribution path.
(3) **Owning the harness buys nothing for routing.** PRD D1 already makes Switchyard the only
endpoint harnesses talk to, and it is OpenAI-compatible; `omp://models.md` documents our exact
case as first-class config (`baseUrl` + `auth: none` + `api: openai-completions` +
`discovery.type: openai-models-list`). Routing is won by configuration, on any harness.

**The convolution is disableable, not inherent.** Three config moves collapse OMP's layer to a
passthrough: set `defaultThinkingLevel` explicit rather than `auto` (kills the second classifier);
point every `modelRoles` alias at the one switchyard route; scope `enabledModels` to that provider
so discovery and `contextPromotionTarget` cannot reach around it. A config edit, versus a harness
migration.

**"Build our own harness" is a NON-GOAL.** Switchyard + Lemonade are the differentiated parts;
the harness is commodity. OMP's documentation alone runs to 132 files covering provider
transports, per-model-family tool conversion (`toolconv/` × 13), compaction, session trees,
RPC/ACP, natives, approval and TUI — and it ships several patch versions a day. Reimplementing
that means owning the churn forever in exchange for capability the base-URL seam already gives.
Revisit only if something proves that seam insufficient — the same falsifiable-test discipline
`contracts/switchyard-routes.md` applies to merging the trees.

**What this decision buys:** the harness choice stays REVERSIBLE. §D1's neutral source plus
per-harness emitters means a future harness is a new emitter, not a rewrite — which is the real
hedge, and the reason not to couple the workflow to any one harness's execution model.

### D12 — The real axis is CONSUME vs FORK, not OMP vs Pi. Consume for 1.0.0; fork stays costed and live.
> *SUPERSEDED by §D13 as to the harness. The consume-vs-fork axis is reused by CR-MDB-027 for
> the dispatch provider (§D16 (5)).*

Raised 2026-09-18, after D11 was (rightly) challenged for answering "is Pi installed" when the
question was "what should we target going forward". Installation is reversible and irrelevant; the
strategy is not. Restated properly, with evidence from OMP's own backport guide
(`omp://porting-from-pi-mono.md`).

**OMP is a FORK of pi-mono, and it enumerates what it added.** Upstream is `@mariozechner/*` /
`@earendil-works/*` pi-mono; last recorded sync `b21b42d`, 2026-03-22. §15 "Features We Added
(Preserve These)" therefore doubles as a list of what upstream pi LACKS:

- **Capability-based discovery** — `defineCapability`, `registerProvider`, `loadCapability`,
  **`skillCapability`**
- Multi-credential auth with session affinity + round-robin (`agent.db`/bun:sqlite, vs upstream's
  `auth.json` + `proper-lockfile`)
- MCP / Exa / SSH integrations, LSP writethrough, bash interception
- Native Bun `import()` for TS extension loading (upstream uses `jiti`); `pkg.omp` manifest
  preferred over `pkg.pi`

The first bullet is decisive for this DN: **capability-based discovery is the machinery this whole
deploy model targets** — the `agents` skills provider at priority 70 (§D2), the `hookCapability`
`pre|post` discovery (§D5), and the plugin/extension load pipeline (§D10). If it is an OMP
addition, targeting upstream pi means §D2/§D5/§D10's contracts may not exist there at all, and the
plugin/marketplace vehicle almost certainly does not. On features the direction is unambiguous:
**OMP ⊇ pi.**

**So the four real strategies, costed:**

| | Strategy | Gets | Pays |
|---|---|---|---|
| **A** | Consume OMP via extensions/plugins | Everything; zero maintenance; this DN as written | OMP's decision layer exists — neutralized by config (§D11) |
| **B** | Consume upstream Pi | Fewer features; may lack the discovery contracts specified here | A migration cost AND keeps the convolution — the only option that pays twice |
| **C** | **Fork OMP into Roundhouse** | Full control: DELETE the competing decision layer instead of configuring around it, keeping every capability | The merge treadmill — OMP's own §11 "regression trap list" and §12 "detect and handle reworked code" exist because blind backporting silently loses features |
| **D** | Build from scratch | Total control | 132 docs of surface: provider transports, 13 `toolconv/` families, compaction, session trees, RPC/ACP, natives, approval, TUI. NON-GOAL (§D11) |

**C is the honest path to "our own dedicated agentic harness", and it is not exotic — it is
precisely what OMP did to pi.** Its cost is measurable rather than theoretical: OMP shipped
**18.2.1 → 18.2.5 during a single working session** on 2026-09-18.

**Adopted position: A for 1.0.0; C stays live and costed, gated on ONE measurement.**
`CR-RND-001`'s probe decides it. If Switchyard forwards `reasoning_effort` verbatim, the two
decision layers compose and there is nothing to fork away from. If it strips or rejects the field,
there is a concrete measured reason to own the harness — and the move would be to fork OMP, never
to adopt a less-featured upstream. **Deciding to fork BEFORE that probe would pay the treadmill
cost for a problem that may not exist.** B is rejected on current evidence.

**Deliberately unmeasured, and flagged rather than assumed:** upstream pi's own skills/agents/
plugin surface. The backport guide establishes what OMP added, which is evidence pi lacks those
specific things, but NOT that pi has no story of its own in a different shape. Any move toward B
requires that measurement first — recorded here because this session twice reasoned from partial
observation and twice had to retract.

### D13 — SUPERSEDES §D11/§D12's adopted position: the target harness is PI, by user ruling

**User ruling 2026-09-18, made against a contrary recommendation and with the measurement in
hand.** Strategy A (consume OMP) was adopted in §D12 and is now WITHDRAWN. The target is upstream
**Pi** (`earendil-works/pi`, formerly `badlogic/pi-mono`; npm `@mariozechner/pi-coding-agent`).
The stated driver is "reasons beyond the switching layer" — recorded as such rather than guessed;
§D14 is reserved for it once stated, because the spec should optimise for the real driver.

**This section exists so the ruling is not "corrected" back by a later session that re-derives
§D12.** It was overruled deliberately, after the following was put in writing.

**What the measurement established, and what it did NOT.** Pi's own docs show the effort layer is
Pi's in origin, not OMP's: a unified **`ThinkingLevel`**, `defaultThinkingLevel` over the
*identical* seven values (`off|minimal|low|medium|high|xhigh|max`), per-role `thinkingLevel` and
`modelTier` in team-mode role frontmatter, and a six-step resolution order whose fifth step is
"a **legacy** `:<thinking>` model suffix such as `gpt-5.4:high`" — i.e. OMP's
`anthropic/claude-opus-5:xhigh` is an inherited Pi convention. **So the move does not remove
harness-side model/effort switching; it relocates it into a deeper resolution chain.** The
double-classifier conflict is fixed by one setting (`defaultThinkingLevel` explicit rather than
`auto`), available in BOTH harnesses. That objection was raised, considered and overruled; it is
not re-openable without new evidence.

**Measured consequences the re-spec must absorb:**

| Surface | OMP (previous target) | Pi (new target) |
|---|---|---|
| Core tools | large set incl. `hub`, `task`, `lsp`, `ast_edit` | **four**: `read`, `write`, `edit`, `bash` |
| Sub-agent definitions | task agents, `~/.omp/agent/agents/*.md` | **not core** — a separate package; `pi-mono-team-mode` was the one found on 2026-09-18; **→ §D16: `pi-archimedes`, `~/.agents/agents/`** |
| Skills | capability discovery, `agents` provider @70 | implements the **Agent Skills standard** ("warns about most violations but remains lenient"); roots to be measured |
| Extensions | unified extension API + plugin/marketplace | extensions register commands/skills; **plugin/marketplace presence UNMEASURED** |
| Distribution | dual-catalog plugin (§D10) | **unknown — §D10's vehicle may not exist**, in which case distribution reverts to installer file-deploy |
| Modes | interactive/RPC/ACP/print | interactive, print/JSON, RPC, SDK |

**Three consequences that are not cosmetic:**

1. **§D10 (the plugin/marketplace distribution decision) is provisionally void.** It rested on
   OMP's marketplace and its Claude-Code-compatible dual catalogs. Whether Pi has an equivalent
   is unmeasured. If it does not, distribution falls back to the installer writing files — which
   is what §D2/§D3's ownership boundary already describes, so nothing is lost except the cheap
   versioned-install story.
2. **The emitter count goes from two to THREE.** Pi's teammate contract
   (`modelTier`/`thinkingLevel`/`needsWorktree`/`hasMemory`) is a third shape beside Claude Code's
   agent frontmatter and OMP's task-agent fields. §D1's neutral-source design is what makes this
   affordable — this is exactly the reversibility it was adopted for, now being spent.
3. **CR-MDB-026's watcher mechanism needs a Pi equivalent.** It standardised the Sandesh wake
   watcher on a supervised named process with `restart: on-failure` — delivered by OMP's `hub`,
   which Pi does not have among its four tools. Pi's supervised-process story must be measured
   before 026 can be implemented, or the watcher regresses to the backgrounded-shell-job defect
   026 exists to fix.

**Required before CR-MDB-025 can be rewritten (measure, do not infer — this DN has twice recorded
the cost of inferring):** *— ANSWERED: all five in §D15.1–§D15.5 and §D16 (2026-09-18/21).*

- Pi's skill discovery roots, and whether `~/.agents/skills` is among them.
- Whether Pi has a plugin/marketplace mechanism, or only extension entry points.
- Pi's supervised-process / background-job facility, for the CR-026 watcher.
- Whether `pi-mono-team-mode` is the sanctioned sub-agent path or an unofficial package, since the
  whole Model B fleet depends on it.
- Pi's own model-role/tier vocabulary, to map Tier-1 route ids onto (PRD §D4 named
  `generator/stacks/*.toml` `model:` as the seam; the seam survives, the target vocabulary changes).

**Unchanged by this ruling:** §D1 (neutral source + per-harness emitters), §D3 (own only what you
generate; never touch electronics ×4 or `inbox-analyst`), §D4 (vscode as a bun/TS editor overlay),
§D8 (external tools orchestrated, never vendored), §D9 (asset classes do not retro-deploy). §D11's
"build our own harness is a NON-GOAL" also stands — this is a change of which upstream to consume,
not a decision to write one.

### D14 — Claude Code is DROPPED as a target; local + cloud mix; the Max subscription is retained

**User ruling 2026-09-18:** move away from Claude Code because it is a closed garden, use LOCAL
models for specific coding tasks alongside cloud providers, and keep using the owned Claude Max
subscription. This is the driver §D13 reserved space for, and it reframes the harness decision:
the move is not OMP→Pi for its own sake, it is **away from vendor-locked harnesses toward one
that can mix local and cloud lanes** — which is the same thesis Roundhouse itself is built on
(switchyard routing + lemonade serving).

**Consequence for this DN: the emitter count DROPS rather than rises.** §D13 worried about a third
emitter. With Claude Code dropped, the target set is Pi alone. (This section first read "OMP
transitional, since the orchestrator runs on it today" — **overtaken 2026-09-21 by user ruling:
OMP is NOT a target, not even transitional**; the orchestrator now runs on Pi 0.86.1 with
`pi-archimedes`.) §D1's "Claude Code output must stay byte-identical" constraint is
RETIRED — it existed because Claude Code was the only working target. The 29 `~/.claude/agents/`
files become unowned legacy under §D3: never written, never deleted.

**The Max requirement is satisfiable on Pi — measured, not assumed.** Pi's quickstart documents
built-in subscription logins via `/login` including **Claude Pro/Max** (also ChatGPT Plus/Pro,
GitHub Copilot, Gemini CLI), with tokens in `~/.pi/agent/auth.json` and auto-refresh. Independently
confirmed by the user for OMP, and corroborated locally: `~/.omp/agent/agent.db` holds exactly one
credential, `provider=anthropic`, `credential_type=oauth`, not disabled, with usage windows
labelled "Claude 5 Hour" / "Claude 7 Day". So the subscription is ALREADY decoupled from Claude
Code today.

**RISK, flagged and unresolved — it is the user's billing and ToS exposure, not ours to decide.**
Two sources disagree with the assumption that Max is free in a third-party harness:

1. Pi's own `providers.md`: "Anthropic subscription auth is active for Claude Pro/Max accounts.
   **Third-party harness usage draws from extra usage and is billed per token, not against Claude
   plan limits.**"
2. An Anthropic policy change prohibiting subscription OAuth for third-party products — banning
   Free/Pro/Max OAuth tokens outside Claude Code and Claude.ai. Pi carries a matching open issue
   (#3372, "`pi` can apparently no longer work with Claude subscription").

These contradict the local measurement (5-hour / 7-day window labels look like PLAN limits, not
per-token extra usage), and this session cannot tell which is actually billing. **Escalated to the
user to verify against their Anthropic usage page.**

**Why it matters beyond Model B — it hits the PRD's cost premise.** `switchyard/routes.toml` and
PRD D2 state: "keep 'strong' a NON-Claude model. Claude is already free via your Max, so paying
for Claude through OpenRouter here would just duplicate what Max gives you." If Max via a
third-party harness bills per token as extra usage — or is disallowed — then **"Claude is already
free via Max" is false and the assessment's economics change**, including which target belongs in
`[targets.strong]`. That is a ROOT finding for the PRD, not a layer one, and it belongs beside
`CR-RND-001` as a second thing to settle before the routing assessment is trusted.

### D15 — The five Pi measurements, run 2026-09-18. Four answers change the plan.

Run against Pi's own published docs (`earendil-works/pi`, `packages/coding-agent/docs/*`), not
inferred. Item 3 was answered by user ruling ("we can create an extension") rather than measured.

**1. Skills — ANSWERED, and it REVERSES §D2's cost.** Pi loads skills from `~/.pi/agent/skills/`
**and `~/.agents/skills/`** (global), plus `.pi/skills/` and **`.agents/skills/`** in cwd and
ancestors (project, after trust), plus package `skills/` dirs, plus a settings `skills` array, plus
`--skill`. Directories containing `SKILL.md` are discovered **recursively**, so Model B's
`<name>/SKILL.md` bundles work unmodified. Pi even relaxes the Agent-Skills name-matching rule
explicitly because it "is suboptimal for **shared skill directories used across multiple agent
harnesses**". **Pi is designed for the shared store that OMP refused** — so the per-harness skill
copies §D2 was forced into are NOT needed on Pi, and that cost disappears. (Caveat to honour: under
`~/.agents/skills/`, root `.md` files are IGNORED; only `SKILL.md` dirs and nested declared `.md`
are found. Our layout complies.)

**2. Packages/plugins — ANSWERED, and BETTER than OMP's marketplace.** Pi has a first-class
package system: `pi install npm:@scope/pkg@1.2.3`, `git:github.com/user/repo@v1` (pinned tag or
commit), plain `https://`/`ssh://`, and local absolute/relative paths (added to settings WITHOUT
copying — the dev loop). A package bundles **extensions, skills, prompts, themes** via a
`package.json` `pi` manifest or convention directories, where `skills/` recursively finds
`SKILL.md` folders. `pi config` enables/disables individual resources; project entries override
global; project packages auto-install on startup after trust; `pi-package` keyword lists in the
gallery at `pi.dev/packages`. Crucially **npm sources ARE installable**, which OMP's marketplace
refuses ("npm plugin sources are not yet supported"). **§D10 is NOT void — it is better served.**
Pi core packages must be `peerDependencies` at `"*"` and not bundled (`@earendil-works/pi-ai`,
`-pi-agent-core`, `-pi-coding-agent`, `-pi-tui`, `typebox`).

**3. Supervised process for the CR-026 watcher — USER RULING: we build it as a Pi extension.**
Not measured; decided. Pi has no `hub` equivalent among its built-ins, so the supervised named
process with `restart: on-failure` that CR-MDB-026 standardised becomes Model-B-owned code shipped
in our Pi package's `extensions/`. This is now a deliverable, not a dependency — and it must
preserve 026's three-exit taxonomy (mail / timeout / lock-conflict) or the watcher regresses to the
very defect 026 exists to fix.

**4. Sub-agents — ANSWERED, and it is the BIGGEST RISK in the whole move.** **Pi core has no
sub-agent dispatch.** Two independent confirmations: `packages.md` lists exactly four package
resource types (extensions, skills, prompts, themes) with **no agents/teammates**; and
`settings.md`'s `defaultTools` enumerates the available built-ins as `read`, `bash`, `powershell`,
`edit`, `write`, `grep`, `find`, `ls` — **no `task` tool**. Sub-agents exist only in
`pi-mono-team-mode`, a SEPARATE community npm package reading `.pi/teammates/<role>.md` (or
`.claude/teammates/<role>.md`) with frontmatter `name`/`description`/`needsWorktree`/`hasMemory`/
`modelTier`/`thinkingLevel`/`tools`.

Model B's entire workflow IS dispatched sub-agents (RED→GREEN→VERIFY→FIX, each registering with
Crucible under its own agent id). So this is the foundation, not a convenience. Three routes were
tabled here; a fourth was found and chosen on 2026-09-21 (§D16):

| | Route | Consequence |
|---|---|---|
| i | Depend on `pi-mono-team-mode` | The core of our workflow rests on a third-party package we do not control and whose maintenance status is unmeasured |
| **i′** | **Depend on `pi-archimedes` (`@pi-archimedes/subagent`) — CHOSEN 2026-09-21** | Same third-party class as (i), but already installed, measured (CR-MDB-027 §S1.1), and reading the shared `~/.agents/agents/` store — so the emitter target is one directory, not a per-harness copy |
| ii | Build dispatch as a Model B Pi extension | Consistent with the §D15.3 ruling; full control; materially bigger than the watcher extension — it needs session spawning, per-agent tool grants, model selection and result capture |
| iii | Change the workflow | Rejected by default: the sub-agent split IS Model B's design (PRD §D6), not an implementation detail |

**5. Model roles / Tier-1 seam — ANSWERED, and it HELPS D4.** Pi core has **no `modelRoles` alias
indirection**: the settings are `defaultProvider`, `defaultModel`, `defaultThinkingLevel`,
`modelThinkingLevels` (per-model, keyed `provider/modelId`) and `thinkingBudgets`. The role-alias
layer the user objected to in OMP therefore **does not exist in Pi core** — it lives in team-mode's
`modelTier`/`roleTiers`. So PRD §D4's seam gets SIMPLER, not harder: declare Switchyard as a custom
provider (Pi supports custom providers and llama.cpp natively, with `models.json` + `baseUrl`), and
a definition's model becomes a concrete **`switchyard/<route-id>`** — no alias to resolve, no second
vocabulary. `generator/stacks/*.toml` `model:` remains the physical seam exactly as D4 says.

**BILLING/ToS — now settled from Pi's own docs, and it falsifies a PRD premise.** Pi ships
`warnings.anthropicExtraUsage` (default **`true`**): "Show a warning when Anthropic subscription
auth **may use paid extra usage**", and `providers.md` states third-party harness usage "draws from
extra usage and is billed per token, **not against Claude plan limits**". Pi builds a warning in for
precisely this. Therefore PRD D2 / `routes.toml`'s "Claude is already free via your Max" is **FALSE
for any third-party harness**, which changes what belongs in `[targets.strong]` and the whole
assessment's economics. Escalated to the user (verify at `claude.ai/settings/usage`) and to the root
PRD beside `CR-RND-001`.

**What this ruling does NOT change:** the local lane was always the point (PRD D16's right-sized
local serving model, Lemonade on `127.0.0.1:13305`), so "local models for specific coding tasks"
is the existing design rather than a new requirement. What changes is that the HARNESS must reach
both lanes — which any OpenAI-compatible-capable harness does through switchyard (PRD D1), and
which is exactly why owning the harness remains a NON-GOAL (§D11).

### D16 — Sub-agent dispatch on Pi is provided by `pi-archimedes`; the emitter target is `~/.agents/agents/`

**User ruling 2026-09-21**, closing CR-MDB-027. Measurement in CR-MDB-027 §S1.1 (sources: the
installed package's `package.json`/`README.md`/`src/spawn.ts`/`src/agents.ts` and the npm
registry — mechanism read from source, not inferred from this session working).

**What was measured, in one line each.** `pi-archimedes` 2.8.0, unaffiliated single maintainer,
23 releases in 11 weeks, peer-dep `pi-coding-agent >=0.1.0` (no upper bound; runs on the local
0.86.1). Its `@pi-archimedes/subagent` component dispatches each task as a **separate `pi`
process** — `pi --mode json --no-session -p --model … --thinking … --tools <csv> --exclude-tools
subagent --system-prompt <body> <task>` in a per-call `cwd` — blocking, parallel via `tasks[]`, no
nested dispatch. Agent files: `.md` + frontmatter `name`/`description` (required), `model`,
`tools` (CSV), `thinking`; unknown keys preserved. Scopes: project `.pi/agents/` → user
`~/.pi/agent/agents/` → **global `~/.agents/agents/`**.

**How the three CR-027 §S4 properties are provided:**

| Property | Mechanism | Strength vs Claude Code baseline |
|---|---|---|
| Own Crucible identity per phase | Own process + own `bash`; agent id/`--role`/`--cycle` arrive in the task prompt exactly as `sub-agent-procedure.md` already specifies | Equal (prompt-carried, as today) |
| Worktree write boundary, VERIFY read-only | (1) `tools` allowlist is **harness-enforced** via `--tools`; (2) the child is a full `pi` in `cwd`, so CR-015's `.pi/extensions/block-write-outside-worktree` applies | Stronger — (1) has no Claude Code equivalent |
| Context isolation | Separate process, `--no-session`, own `childSessionId` | Stronger |

**Consequences.**

1. **The emitter target is `~/.agents/agents/<name>.md`** — archimedes' global scope and the same
   shared store §D15.1 credits Pi for on skills. The per-harness agent-definition copy §D2/§D6
   forced for OMP is NOT needed on Pi; the installer asset class CR-MDB-025 §S4 introduces
   deploys once, user-scope, no symlink (the `.agents/skills` and `.agents/scripts` shape).
2. **`_emit_pi()` is the ONE emitter in the CR-025 re-spec** (no `_emit_omp()`, no
   `_emit_claude_code()` — §D14 retired byte-identity): `tools` CSV of Pi core names
   through an explicit translation map (drop-with-reason, never a plausible rename); `model` is a
   concrete `switchyard/<route-id>` per §D15.5 or omitted for `inherit` (archimedes passes it
   literally as `--model`, so `sonnet` today resolves to nothing); `effort` → `thinking`;
   `color`/`maxTurns`/`skills` dropped as inert.
3. **The ownership boundary §D3 now applies to `~/.agents/agents/`**: 25 hand-placed files today;
   Model B generates 20 (24 with the vscode overlay §D4) and never writes or deletes
   `inbox-analyst`.
4. **One caveat is carried, not closed:** whether `-p` mode honours or skips the project-trust
   prompt for a fresh worktree's `.pi/` (`modelb_axi/hooks.py:320`). If it skips silently, the
   extension half of the write boundary is absent and only the `tools` allowlist holds. The 025
   rewrite's integration gate measures it with a real dispatch into a fresh worktree.
5. **Risk accepted and bounded:** a single unaffiliated maintainer, the same class as route (i).
   Accepted because the dependency surface is four frontmatter keys plus one directory, and
   §D1 makes the provider an emitter target — a later swap to route (i) or (ii) is one emitter.

**Release scope, ruled 2026-09-21:** CR-MDB-027 and its implementation (the CR-MDB-025 re-spec)
are both in release 1.0.0; 025 stays on CR-MDB-012's dependency list.

## Consequences per CR

| CR | What this DN changes |
|---|---|
| **025** (Pi agent definitions) | Re-specced 2026-09-21 as `CR-MDB-025-pi-agent-definitions.md` against §D13/§D14/§D16; the OMP spec is git history. Delivery: one neutral dict, `_emit_pi()`, structured `[roles.<role>]` TOML, explicit tool map, `model:` verbatim-or-omitted (values empty until the Tier-1 `CR-RND`), asset class `.agents/agents` once user-scope. On Pi skills need no work for the MEASURED reason §D15.1 gives. §D3 boundary applies to `~/.agents/agents/`. No Claude Code emitter (§D14). Roster and hooks unchanged (`pi` present; `_emit_pi` hooks since 015). |
| **020** (client paths) | §D8's never-a-checkout rule is its §S0; the anchor is now real, not aspirational. |
| **018** (discovery) | The manifest exists with six keys; resolution SUCCEEDS, so the unresolved degrade is no longer the expected outcome. |
| **019** (hook runtime) | Re-scoped 2026-09-21: §S3 (opencode emitter) struck; keeps the status-contract re-pin and the arduino marker. The Pi emitter's runtime is CR-MDB-030. |
| **024** (rust) | Its four definitions are generated into `generator/agents/` and reach Pi through CR-025's `.agents/agents` class; nothing under `~/.claude/agents/` is superseded (§D14). |
| **014** (installer) | Gains the agent-definition asset class (CR-025 §S4) and `pi install` orchestration for the package (CR-029 §S4). CR-033 fixes `target_root`, atomic writes and the unmanaged-file clobber first. |
| **012** (release) | The release gate must prove Pi resolves an emitted definition by name (`list_agents` via archimedes). §D15.2 adds a publication step for the Pi package (extensions + skills): tag, `pi install …@<version>` (CR-029 §S5). No byte-identity gate (§D14). |
| **NEW CR — CR-MDB-029** | Authoring the Pi package itself per §D15.2: `package.json` `pi` manifest, `extensions/` (the CR-026 watcher per §D15.3; hooks currently emitted per-project by 015), `skills/`. **Agent definitions cannot ride it** — Pi packages carry only extensions/skills/prompts/themes — so the split is: package = extensions + skills; installer = agents + tool scripts. (The number 027 this row once reserved was consumed by the dispatch decision CR.) |

## Open, deliberately not decided here

- Whether `hermes`/`opencode` should also receive agent definitions. (`pi` is now decided — §D16.)
  They are present on this machine but Model B has never emitted definitions for them, and
  nothing yet establishes their frontmatter contracts. Out of scope until a CR needs it — and
  CR-MDB-031 removes them from the roster until one does.
