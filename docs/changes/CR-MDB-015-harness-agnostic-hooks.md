# CR-MDB-015 — Harness-agnostic hooks: neutral schema + per-harness emitters + shared script protocol

**Status:** COMPLETED
**Type:** feature
**Priority:** P1 (last wave-3 CR before the release)
**Depends on:** CR-MDB-013, CR-MDB-014
**Labels:** hooks, harness, compiler, axi
**Phase:** Wave 3
**Design reference:** `DN-harness-agnostic-hooks.md` §4 (the design contract: (a)+(c) with (b) as guaranteed core) · PRD §D10.7 · CR-CRU-035 division (#1333/#1334: Model B owns hook creation+deploy; Crucible = stable tolerant `status` read-path only) · DN-scaffold-packaging (assets/installer)

## Context

Hooks become correct-by-construction: hook LOGIC is written ONCE as Claude-contract protocol scripts (stdin JSON, exit 0/2, `hookSpecificOutput`), a neutral schema declares each hook's event/matcher/tier/timeout/fail-direction INTENT, and a compiler emits per-harness native wiring — capabilities degraded only DECLARED, never silently; security-class hooks whose fail-direction a harness cannot honor are REFUSED with a report (DN §4.4).

**Roster note (routed from 013):** the DN surveyed claude/codex/gemini/cursor/copilot/opencode/amp; the settled roster is Claude Code, Hermes, pi (pi.dev), OpenCode. Hermes + pi hook contracts are UNRESEARCHED — §S4 opens with a bounded primary-doc research step whose outcome (emitter or declared degradation) amends the DN before emitter code is written.

**Binding rules:** repo-local authoring (scripts live in `hooks-src/`, ship as package assets, deploy via the installer; per-project WIRING is scaffold-emitted); zero `~/.claude` writes (importing existing Model B-owned hook scripts is READ-ONLY); no `WORKFLOW_CYCLE_ID` anywhere; crucible client paths per the client-path rule.

**Sanctioned 013-gate amendment:** `tests/test_scaffold.py` pins `hooks/README.md` containing "CR-MDB-015" (the seam placeholder); when §S5 fills the seam the gate retargets to the real emission (schema instance + wiring present).

## Scope

### §S1 — AC gate tests (RED first)
`tests/test_hooks.py` (+ the sanctioned scaffold-gate amendment). All harness-wiring output into tmp targets; protocol scripts unit-tested standalone via stdin/exit.

### §S2 — Neutral hook-definition schema
`hooks-src/schema.md` (versioned, v1) + machine format (TOML): fields `event` (universal set: pre-tool-use, post-tool-use, session-start, turn-stop, + subprocess-tier prompt-submit/pre-compact), `matcher`, `command` (targets a protocol script), `tier` (core|extended|harness-specific escape hatch), `timeout` (seconds, compiler converts units), `fail_direction` (open|closed intent — REQUIRED for security-class), optional per-harness escapes marked non-portable.

### §S3 — Shared protocol script library (`hooks-src/scripts/`)
Import (read-only baseline from the deployed tree) + normalize to the protocol the SIX Model B-owned scripts: `block-direct-cargo-test`, `block-direct-mvn-test`, `block-bad-cycle-task-name`, `block-cr-completed-without-spec-update`, `block-write-outside-worktree`, `post-regression-disk-reminder`. NEW: `ambient-board-status` SessionStart hook per the #1334 division — invokes the project stack's `<stack>-crucible.py status`, surfaces the board (queue rows, active cycle, lastRunCr) into session context; TOLERANT + BOUNDED (fast timeout, exit 0 with a degradation note when no plan/server — a session start never blocks). Provider-owned hooks (lean-ctx, mempalace, lavish-poll-guard) are OUT of scope. Zero `WORKFLOW_CYCLE_ID`; client invocation honors the discovery convention (installed location from install config; repo path in dev).

### §S4 — Compiler: neutral schema → per-harness wiring
Step 0 (research, bounded): fetch Hermes + pi primary docs; amend DN §2 with findings; outcome per harness = native emitter or DECLARED degradation. Emitters: **claude-code** — full native `.claude/settings.json` wiring (matcher/timeout/decision tiers); **opencode** — generated TS spawn-shim plugin (DN (c)); **hermes/pi** — per Step-0 outcome. Compiler rules: above-core capabilities emitted only where supported, degradations REPORTED in output; fail-closed-intent hooks REFUSED (with report) on harnesses that cannot honor fail-closed; trust-gate churn (where applicable) documented in emitted output.

### §S5 — Scaffold seam fill
`modelb-axi init` emits real hook artifacts: stack/mode-derived neutral-schema instances (e.g. cargo guard only for rust stacks; worktree/CR guards only for multi mode; ambient-board-status always) + compiled wiring for the INSTALLED harness set + an updated hooks/README (compiler report incl. degradations/refusals). The 013 placeholder emission is replaced (gate amendment sanctioned above).

### §S6 — Installer asset wiring
`hooks-src/` ships in the wheel (pyproject force-include → `modelb_axi/_assets/hooks-src`); the deploy engine deploys the protocol SCRIPTS once user-scope (manifest-tracked) per PRD D10.7; per-project wiring remains scaffold-emitted.

## Acceptance criteria

- [ ] AC1: `hooks-src/schema.md` exists (versioned v1) naming all six schema fields incl. `fail_direction`; a valid + an invalid sample TOML instance round-trip/reject in tests.
- [ ] AC2: all seven protocol scripts pass standalone stdin/exit unit tests (allow ⇒ exit 0; block ⇒ exit 2 + reason JSON); zero `WORKFLOW_CYCLE_ID`, zero `~/.claude/scripts` client paths in `hooks-src/`.
- [ ] AC3: `ambient-board-status` with a mocked `status` feed surfaces cr/cycle/lastRunCr lines; with a failing/absent feed exits 0 fast with a degradation note (never blocks, never non-zero).
- [ ] AC4: compiler emits valid claude-code `settings.json` wiring for a sample schema (matcher/timeout correct) into a tmp target; opencode emission produces a TS shim that spawns the protocol script; hermes/pi handled per the researched outcome with the compiler REPORT naming each harness's capability or declared degradation — nothing silent.
- [ ] AC5: a `fail_direction=closed` hook targeted at a harness that cannot honor it is REFUSED: not emitted, named in the report, non-zero only if refusal leaves zero emitted targets.
- [ ] AC6: scaffolded project (tmp): neutral-schema instances match `--stacks`/mode selection; wiring present for installed harnesses only; hooks/README carries the compiler report; the amended scaffold gate passes.
- [ ] AC7: wheel contains `modelb_axi/_assets/hooks-src/`; deploy engine manifests the scripts user-scope in the sandbox store; `~/.claude` byte-untouched throughout (guard).
- [ ] AC8: DN §2 amended with the Hermes + pi research findings (sources cited, dated).

## Estimated size
L. Cycles: C1 schema + script library (§S2–S3) · C2 research + compiler (§S4) · C3 scaffold seam + installer wiring (§S5–S6) · V1 verify.

## Risk
- Hermes/pi may lack any hook contract — the declared-degradation path is the designed fallback, not a failure.
- Harness config drift — emitters cite DN + source URLs (per 013 precedent).

## Non-goals
- Standardizing hooks into agents.md / the skills standard (DN §5). Harness-unique event normalization (escape hatches only). Provider-owned hooks (lean-ctx, mempalace, lavish). Live deployment to the real home (installer's runtime concern, sandbox-tested only).
