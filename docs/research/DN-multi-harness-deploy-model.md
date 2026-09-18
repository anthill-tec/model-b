# DN — The multi-harness deploy model: one neutral source, per-harness targets

**Status:** ADOPTED (user-ruled 2026-09-18)
**Drives:** CR-MDB-025 (OMP target), CR-MDB-020 (client-path anchoring), CR-MDB-018 (discovery
capture), CR-MDB-014 (universal installer — the flow this extends), CR-MDB-019 (hook runtime)
**Supersedes in part:** CR-MDB-025's claim that "skills already work on OMP — no work required"
(user correction 2026-09-18; see §D2)
**Measurement date:** 2026-09-18, this workstation, all figures measured not recalled

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
Agent definitions become an installer asset class with the same shape hooks already use: a
neutral declaration is authored once, and per-harness emitters render it into each harness's own
frontmatter contract. Claude Code and OMP are both emitters; neither is the source. **Claude Code
output must stay byte-identical** across this change — it is the only currently-working target,
so any diff there is a regression, not an improvement.

### D2 — OMP is served by its OWN copies, never by `~/.agents/`
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
`~/.omp/agent` is only the default. `omp --profile <name>` moves it to
`~/.omp/profiles/<name>/agent/`, and `PI_CODING_AGENT_DIR` overrides it outright. Every OMP path
this model writes — agents, skills, tools, hooks — resolves the active agent directory first. A
hardcoded `~/.omp/agent` is a defect that silently deploys into an inactive profile.

### D7 — `config.yml` is the USER's file: verify, never write
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

## Consequences per CR

| CR | What this DN changes |
|---|---|
| **025** (OMP) | Reshaped by §D10: delivery becomes "publish a PLUGIN", not "write files into `~/.omp/agent/`". Withdraws "skills need no work" (§D2). Adds the adoption census and ownership boundary (§D3), agent-dir resolution (§D6), `config.yml` verify-not-write (§D7), and TS factory adapters over the python hook scripts (§D5). Claude Code output stays byte-identical (§D1). |
| **020** (client paths) | §D8's never-a-checkout rule is its §S0; the anchor is now real, not aspirational. |
| **018** (discovery) | The manifest exists with six keys; resolution SUCCEEDS, so the unresolved degrade is no longer the expected outcome. |
| **019** (hook runtime) | OMP joins the emitter set; `fail_direction: closed` is honourable there, unlike opencode. Hooks are OMP's legacy surface — extensions are the unified one (§D10). |
| **024** (rust) | Its four definitions are emitted to BOTH harnesses, not just Claude Code. |
| **014** (installer) | Gains the agent-definition asset class and the per-harness emitter dispatch. Per §D10 the OMP path is publication, so the installer orchestrates a plugin install rather than owning OMP's directories. |
| **012** (release) | The release gate must prove BOTH harnesses resolve an emitted definition by name. §D10 adds a publication step: tag, catalog version + source pin, then `omp plugin marketplace update` / `omp plugin upgrade`. A session RESTART is required for tools/hooks/extensions — `/reload-plugins` is insufficient. |
| **NEW CR needed** | Authoring the marketplace + plugin package itself (dual catalogs, `omp.extensions` manifest, TS factory adapters, dev-loop via `omp plugin link`). This is not inside 025's current scope and should be filed at the next SCRUM. |

## Open, deliberately not decided here

- Whether the four `pi`/`hermes`/`opencode` harnesses should also receive agent definitions.
  They are present on this machine but Model B has never emitted definitions for them, and
  nothing yet establishes their frontmatter contracts. Out of scope until a CR needs it.
- Whether the OMP-local skills copy should be a copy or a symlink farm. Copy is assumed (D2 says
  correctness must not depend on shared-store resolution); a symlink would reintroduce exactly
  the dependency the ruling removed.
