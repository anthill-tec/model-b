# CR-MDB-027 — Sub-agent dispatch on Pi: the workflow's foundation is not in the harness

**Status:** RULED 2026-09-21 — route **(i′) adopt `pi-archimedes`** (user ruling; measurement §S1.1;
recorded DN §D16). Implementation follows in the CR-MDB-025 rewrite (OMP → Pi).
**Type:** design
**Priority:** P1 — **in release 1.0.0, wave 2** (user ruling 2026-09-21, moved in from post-1.0.0).
It is a DECISION CR, not a build: it costs one measurement and one recorded ruling, which is why
it fits inside the release. **Its implementation — the CR-MDB-025 rewrite — is ALSO in 1.0.0** (user
ruling 2026-09-21, restated emphatically the same day): the decision and its build ship together.
**Depends on:** `docs/research/DN-multi-harness-deploy-model.md` §D13/§D14/§D15 (the Pi ruling and
the measurements). No code dependency.
**Blocks:** the CR-MDB-025 rewrite (OMP → Pi), and any emission of agent definitions to Pi. It is
sequenced immediately before 025 on the board for that reason.
**Labels:** generator, harness, agent-definitions, pi, design, workflow
**Phase:** Wave 5 (repo queue) · release 1.0.0 wave 2 (Crucible board)
**Design reference:** DN §D15.4 (measured: Pi core has no sub-agent dispatch) · PRD §D6 (role
templates × per-stack params generate the agent set — the design this CR must preserve) ·
`skills-src/model-b/references/sub-agent-procedure.md` (the binding procedure every dispatched
agent follows) · `contracts/crucible-envelope.md` (each agent registers under its own id/role/cycle)

## Context

**Measured 2026-09-18 against Pi's own docs, twice over:** Pi core has **no sub-agent dispatch.**

1. `packages/coding-agent/docs/packages.md` enumerates exactly four package resource types —
   `extensions`, `skills`, `prompts`, `themes`. There is **no agents/teammates resource type**.
2. `packages/coding-agent/docs/settings.md`'s `defaultTools` lists the available built-ins as
   `read`, `bash`, `powershell`, `edit`, `write`, `grep`, `find`, `ls`. There is **no `task` tool**.

Sub-agents exist for Pi only through **`pi-mono-team-mode`**, a separate community npm package that
reads `.pi/teammates/<role>.md` (or `.claude/teammates/<role>.md`) with frontmatter
`name`/`description`/`needsWorktree`/`hasMemory`/`modelTier`/`thinkingLevel`/`tools`.

**Why this is foundational rather than inconvenient.** Model B is not a harness-agnostic pile of
skills that happens to dispatch agents; the dispatch IS the workflow. PRD §D6 generates role
templates × per-stack params into 16 (soon 20+) definitions precisely so that RED, GREEN, VERIFY and
FIX run as *separate agents with separate identities*. Three properties depend on that separation
and none of them survive collapsing the roles into one session:

- **Crucible identity.** Each phase registers under its own agent id and `--role`, and (for the four
  TDD roles) binds a `--cycle`. The RED→GREEN transition Crucible displays exists because two
  different agents ingested two different runs. One session cannot produce it.
- **The write boundary.** `sub-agent-procedure.md` binds each agent to a worktree write boundary;
  VERIFY is read-only by construction. A single session has no boundary to enforce.
- **Context isolation.** VERIFY reviewing GREEN's work in GREEN's own context is not a review.

So this CR is not "port the dispatcher". It is: **decide what provides dispatch on Pi, given that
the harness does not.**

**Measured 2026-09-21, superseding the survey above:** `pi-mono-team-mode` is NOT the only
provider. **`pi-archimedes`** (`npm:pi-archimedes`, component `@pi-archimedes/subagent`) is a
second, independent Pi package providing named-agent dispatch — and it is the one **installed on
this machine** (`~/.pi/agent/settings.json` `packages[]`), already resolving all 20 Model B
definitions plus the 4 vscode overlays from `~/.agents/agents/`. The 2026-09-18 survey missed it
because it searched for "teammates", not "subagent". It is a fourth route, measured in §S1.1.

## The decision

| | Route | What it costs | What it risks |
|---|---|---|---|
| **i′** | **Adopt `pi-archimedes` (`@pi-archimedes/subagent`)** — **CHOSEN 2026-09-21** | Cheapest of all: already installed; its global scope IS the shared `~/.agents/` store Pi skills already use (DN §D15.1), so the emitter target is `~/.agents/agents/<name>.md` and the installer asset class from CR-025 §S4 delivers it with no per-harness copy. Frontmatter is Claude-Code-adjacent (`name`/`description`/`model`/`tools` CSV/`thinking`); unknown keys preserved, not interpreted. | Same class as (i): a third-party package, single unaffiliated maintainer. Mitigated by the measured cadence (§S1.1) and by DN §D1 — the neutral source makes a provider swap an emitter swap. |
| **i** | **Adopt `pi-mono-team-mode`** | Cheapest by far: a package install plus an emitter for `.pi/teammates/<role>.md`. Its frontmatter already carries `needsWorktree`, `modelTier`, `thinkingLevel`, `tools` — a close match to what our definitions need. | The core of Model B's workflow rests on a third-party package we do not control, whose maintenance status, release cadence and API stability are **unmeasured**. If it lags Pi, the whole fleet stops. |
| **ii** | **Build dispatch as a Model B Pi extension** | Materially bigger than the §D15.3 watcher extension: session spawning, per-agent tool grants, model selection, prompt assembly, result capture, and failure semantics. Pi's extension API and SDK mode are the levers (`pi` exposes an SDK for embedding). | We own an agent-runtime component forever. This is the piece most likely to break on a Pi upgrade, and it is squarely the "build our own harness" cost §D11 declared a non-goal — in miniature. |
| **iii** | Collapse the roles; drop multi-agent | Near-zero build. | Rejected by default: it discards PRD §D6, the Crucible RED→GREEN evidence chain, the write boundary and VERIFY's independence. It is a different methodology, not an implementation choice. |

**No recommendation was recorded here at filing** — routes (i) and (ii) trade control against
build, the same axis as §D12's consume-vs-fork one layer down. **Ruled 2026-09-21 by the user:
route (i′).** What this CR asserts unchanged is that (iii) is not on the table without abandoning
the workflow the project exists to run.

## Scope

### §S1 — Measure `pi-mono-team-mode` before choosing (prerequisite, cheap)
Route (i) cannot be evaluated on its name. Establish, from published sources only: last release
date and cadence; whether it is authored/endorsed by Pi's maintainers or unaffiliated; its declared
Pi version compatibility; whether `.pi/teammates` dispatch supports per-agent tool grants and model
selection at the granularity our definitions need; and whether a dispatched teammate can run its own
Crucible register/ingest/unregister lifecycle (i.e. get its own identity, not the parent's).
**A route (i) decision taken without this is a bet, not a choice.**

#### §S1.1 — Measurement of `pi-archimedes`, run 2026-09-21 (the route actually chosen)

Sources: the installed package at `~/.pi/agent/npm/node_modules/{pi-archimedes,@pi-archimedes/subagent}/`
(`package.json`, `README.md`, `src/spawn.ts`, `src/agents.ts`) and `npm view pi-archimedes`. Not
inferred from observing this session work — the mechanism is read from source.

| Question (§S1) | Answer | Evidence |
|---|---|---|
| Affiliation | **Unaffiliated** with Pi's maintainers (`earendil-works`). Single maintainer `danmademe` (Daniel Cherubini), repo `github.com/danielcherubini/pi-archimedes`, pnpm monorepo, 11 components. | `package.json` `repository`/`maintainers` |
| Release cadence | **23 releases 2026-07-04 → 2026-09-21**, ~weekly; 1.6.0 → 2.8.0; latest **2.8.0 published 2026-09-21** (today). | `npm view pi-archimedes time` |
| Pi version compatibility | `peerDependencies` `@earendil-works/pi-coding-agent >=0.1.0` (no upper bound); `devDependencies` `^0.85.1`; local Pi is **0.86.1** and this session runs it. Compatibility is therefore by convention, not pin — a Pi breaking change surfaces at the next `pi` upgrade. | `package.json`; `~/.pi/agent/settings.json` `lastChangelogVersion` |
| Dispatch mechanism | **A separate `pi` OS process per task**: `pi --mode json --no-session -p [--model M] [--thinking T] [--tools a,b] --exclude-tools subagent [--system-prompt BODY] <task>`, with `cwd` = per-call `cwd` or the parent's. Blocking; the schema's `async` is documented as ignored. Parallel via a `tasks[]` array. A worker cannot spawn workers. | `src/spawn.ts:204-252`; README "The dispatch waits" |
| Per-agent tool grants | **Yes, harness-enforced**: frontmatter `tools` (CSV) → `--tools` allowlist on the child. Pi core names: `read`, `bash`, `edit`, `write`, `grep`, `find`, `ls` (+ `powershell`). | `spawn.ts:218-221` |
| Per-agent model selection | **Yes**: `agent.model` → per-call `model` → parent's active model; passed literally as `--model`, so it must be a real Pi `provider/model` id — `sonnet`/`inherit` (today's generated files) are NOT resolvable and fall through by accident. `thinking` per agent file; NOT inherited from the parent. `~/.pi/agent/agents.local.json` (machine-local TUI picks) overrides frontmatter. | `spawn.ts:207-215`; README "Model and thinking resolution" |
| Agent file contract | `.md` + YAML frontmatter; `name` + `description` **required** (else skipped); `tools` CSV; body = system prompt; unknown keys preserved on edit, never interpreted. | README "Agent files" |
| Discovery scopes | project `<repo>/.pi/agents/` → user `~/.pi/agent/agents/` → **global `.agents/agents/` (nearest ancestor) or `~/.agents/agents/`**. | `src/agents.ts:92-190`; README |
| Own Crucible identity (§S4-a) | **Provided by construction**: the child is its own process with its own `bash`, inherits the parent env, and the agent id / `--role` / `--cycle` arrive in the task prompt exactly as `sub-agent-procedure.md` already specifies for Claude Code's `Task` tool. Register/ingest/unregister run inside the child. Nothing in archimedes reads or forges identity. | `spawn.ts:247-251` (`env: {...process.env}`) |
| Write boundary + VERIFY read-only (§S4-b) | **Provided twice**: (1) `tools` allowlist — VERIFY emits `tools: read, grep, find, ls` and the harness refuses `edit`/`write`; (2) a full `pi` process in `cwd` loads project `.pi/extensions/*.ts`, so CR-015's emitted `block-write-outside-worktree` extension applies inside the worktree the orchestrator passes as `cwd`. **Caveat, unmeasured:** whether `-p` mode honours or skips the project-trust prompt for a fresh worktree's `.pi/` (hooks.py:320 records the trust gate) — must be measured in the 025 rewrite's integration gate, not assumed. | `spawn.ts:247`; `modelb_axi/hooks.py:290-320` |
| Context isolation (§S4-c) | **Total**: separate process, `--no-session`, own `childSessionId`; the parent sees only the returned output. | `spawn.ts:204`; README |
| What it does NOT offer | No `needsWorktree` (the orchestrator creates the worktree via `worktree-flow.py` and passes `cwd`); no fire-and-forget; no nested dispatch; no `modelTier`/role-alias layer (consistent with DN §D15.5 — the model is a concrete `switchyard/<route-id>`). | README |

**Verdict:** every §S4 property is provided, two of them by harness enforcement rather than prompt
discipline — which is stronger than the Claude Code baseline. The residual risk is the one named
for route (i): a single unaffiliated maintainer. It is accepted because (a) the cadence is live,
(b) the contract Model B depends on is four frontmatter keys plus a directory, and (c) DN §D1 makes
the provider an emitter target, so a swap to route (i) or (ii) later costs one emitter.

### §S2 — Record the ruling and its consequences
Whichever route is chosen, record it as a DN decision (§D16) with the evidence, so the
implementation CRs cite it rather than re-deriving it.

### §S3 — The neutral source is unchanged either way
DN §D1's neutral agent-definition source stays the authority. This CR changes only the **emitter**
target: `~/.agents/agents/<name>.md` with archimedes frontmatter for route (i′),
`.pi/teammates/<role>.md` for route (i), or our extension's own format for route (ii). The
`generator/stacks/*.toml` × `templates/` shape and `build.py --check` drift gate are
untouched — the point of §D1 was to make exactly this substitution affordable, and this is it being
spent for the second time.

### §S4 — Preserve the three properties, whichever route wins
The chosen mechanism must demonstrably provide: a distinct Crucible identity per dispatched phase
(own agent id, `--role`, and `--cycle` for the four TDD roles); an enforceable worktree write
boundary with VERIFY read-only; and context isolation between phases. These are acceptance
conditions on the ROUTE, not implementation details to be discovered later.

## Acceptance criteria

- [x] §S1's measurement is recorded with dates and sources — maintenance status, affiliation,
      Pi-version compatibility, tool-grant and model-selection granularity, and whether an agent
      can hold its own Crucible identity. (Run against `pi-archimedes`, the route chosen, §S1.1;
      `pi-mono-team-mode` was not measured because it is no longer a candidate.)
- [x] A route is chosen and recorded as a DN decision citing that measurement (DN §D16).
- [x] The ruling states explicitly how each of §S4's three properties is provided (§S1.1 rows
      §S4-a/b/c).
- [x] `docs/research/DN-multi-harness-deploy-model.md` §D15.4's three-route table is updated to name
      the chosen route and the date.
- [x] No implementation is started before the ruling — this CR is the decision, not the build.
- [ ] The CR-MDB-025 rewrite cites this ruling rather than assuming a dispatch mechanism.

## Estimated size

Decision-only: one measurement pass and one DN decision. The implementation that follows is a
separate CR whose size is route-dependent and differs by an order of magnitude between (i) and (ii).

## Risk

- **This is the single point of failure for the whole Pi migration.** Skills, tools, hooks and
  distribution all measured CHEAPER on Pi (DN §D15.1/§D15.2/§D15.5). Dispatch is the one that got
  harder, and it is the one the workflow cannot do without.
- Choosing route (i) without §S1 makes an unmeasured third-party package load-bearing for every CR
  the project will ever run. Choosing route (ii) without scoping makes Model B the owner of an
  agent runtime, which §D11 called a non-goal for good reasons.
- **1.0.0 CARRIES this decision AND its implementation** (user ruling 2026-09-21). The decision
  half is bounded — one measurement, one recorded ruling. The implementation half is the
  CR-MDB-025 rewrite, already on CR-MDB-012's dependency list; route (i′) keeps it to one emitter
  plus one asset class, which is why carrying it in the release is affordable. Had route (ii)
  been chosen, the build-your-own-dispatch cost would have had to be re-scoped against the release
  explicitly — it was not chosen.

## Non-goals

- No harness re-litigation. The Pi target is ruled (DN §D13/§D14).
- No change to the sub-agent procedure, the Crucible lifecycle, or the role split itself.
- No implementation, in this CR.

## Consequences for the CR-MDB-025 rewrite (recorded here so 025 cites, not re-derives)

- Emitter `_emit_pi()`: `name`, `description`, `tools` (CSV, Pi core names via an explicit
  translation map, drop-with-reason), `model` (concrete `switchyard/<route-id>` per DN §D15.5, or
  omitted for `inherit`), `thinking` (from `effort`); `color`/`maxTurns`/`skills` dropped.
- Asset class destination: `~/.agents/agents/` — the archimedes global scope and the same
  user-scope-once, no-symlink shape as `.agents/skills` and `.agents/scripts`. Ownership boundary
  DN §D3 applies to that directory (never write/delete `inbox-analyst`).
- 025 §S5/§S6 fall away: `pi` is already in `HARNESS_ROSTER`; `_emit_pi` hooks exist since 015.
- Integration gate must measure the `-p`-mode trust caveat (§S1.1) with a real dispatch into a
  fresh worktree, asserting the write-boundary block fires.
- **Release scope, ruled:** 027 and the 025 rewrite are both in 1.0.0; 025 stays on 012's
  dependency list. No conflict remains.
