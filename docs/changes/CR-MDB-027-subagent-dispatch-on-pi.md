# CR-MDB-027 — Sub-agent dispatch on Pi: the workflow's foundation is not in the harness

**Status:** PENDING (design decision required before any Pi re-spec can proceed)
**Type:** design
**Priority:** P1 — **in release 1.0.0, wave 2** (user ruling 2026-09-21, moved in from post-1.0.0).
It is a DECISION CR, not a build: it costs one measurement and one recorded ruling, which is why
it fits inside the release. The implementation that follows is a separate CR and is NOT in 1.0.0.
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

## The decision

| | Route | What it costs | What it risks |
|---|---|---|---|
| **i** | **Adopt `pi-mono-team-mode`** | Cheapest by far: a package install plus an emitter for `.pi/teammates/<role>.md`. Its frontmatter already carries `needsWorktree`, `modelTier`, `thinkingLevel`, `tools` — a close match to what our definitions need. | The core of Model B's workflow rests on a third-party package we do not control, whose maintenance status, release cadence and API stability are **unmeasured**. If it lags Pi, the whole fleet stops. |
| **ii** | **Build dispatch as a Model B Pi extension** | Materially bigger than the §D15.3 watcher extension: session spawning, per-agent tool grants, model selection, prompt assembly, result capture, and failure semantics. Pi's extension API and SDK mode are the levers (`pi` exposes an SDK for embedding). | We own an agent-runtime component forever. This is the piece most likely to break on a Pi upgrade, and it is squarely the "build our own harness" cost §D11 declared a non-goal — in miniature. |
| **iii** | Collapse the roles; drop multi-agent | Near-zero build. | Rejected by default: it discards PRD §D6, the Crucible RED→GREEN evidence chain, the write boundary and VERIFY's independence. It is a different methodology, not an implementation choice. |

**No recommendation is recorded here deliberately.** Routes (i) and (ii) trade control against
build, and that is the user's call — the same axis as §D12's consume-vs-fork, one layer down. What
this CR does assert is that (iii) is not on the table without abandoning the workflow the project
exists to run.

## Scope

### §S1 — Measure `pi-mono-team-mode` before choosing (prerequisite, cheap)
Route (i) cannot be evaluated on its name. Establish, from published sources only: last release
date and cadence; whether it is authored/endorsed by Pi's maintainers or unaffiliated; its declared
Pi version compatibility; whether `.pi/teammates` dispatch supports per-agent tool grants and model
selection at the granularity our definitions need; and whether a dispatched teammate can run its own
Crucible register/ingest/unregister lifecycle (i.e. get its own identity, not the parent's).
**A route (i) decision taken without this is a bet, not a choice.**

### §S2 — Record the ruling and its consequences
Whichever route is chosen, record it as a DN decision (§D16) with the evidence, so the
implementation CRs cite it rather than re-deriving it.

### §S3 — The neutral source is unchanged either way
DN §D1's neutral agent-definition source stays the authority. This CR changes only the **emitter**
target: `.pi/teammates/<role>.md` frontmatter for route (i), or our extension's own format for
route (ii). The `generator/stacks/*.toml` × `templates/` shape and `build.py --check` drift gate are
untouched — the point of §D1 was to make exactly this substitution affordable, and this is it being
spent for the second time.

### §S4 — Preserve the three properties, whichever route wins
The chosen mechanism must demonstrably provide: a distinct Crucible identity per dispatched phase
(own agent id, `--role`, and `--cycle` for the four TDD roles); an enforceable worktree write
boundary with VERIFY read-only; and context isolation between phases. These are acceptance
conditions on the ROUTE, not implementation details to be discovered later.

## Acceptance criteria

- [ ] §S1's measurement of `pi-mono-team-mode` is recorded with dates and sources — maintenance
      status, affiliation, Pi-version compatibility, tool-grant and model-selection granularity, and
      whether a teammate can hold its own Crucible identity.
- [ ] A route is chosen and recorded as a DN decision citing that measurement.
- [ ] The ruling states explicitly how each of §S4's three properties is provided, per route.
- [ ] `docs/research/DN-multi-harness-deploy-model.md` §D15.4's three-route table is updated to name
      the chosen route and the date.
- [ ] No implementation is started before the ruling — this CR is the decision, not the build.
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
- **1.0.0 now CARRIES this decision** (user ruling 2026-09-21). That is affordable precisely
  because this is a decision CR — one measurement, one recorded ruling — and it is bounded that
  way deliberately. The IMPLEMENTATION that follows the ruling is a separate CR and is explicitly
  **not** in 1.0.0. If the chosen route is (ii), build-your-own-dispatch, that build must not be
  quietly pulled into the release on the grounds that its parent decision was.

## Non-goals

- No harness re-litigation. The Pi target is ruled (DN §D13/§D14).
- No change to the sub-agent procedure, the Crucible lifecycle, or the role split itself.
- No implementation, in this CR.
