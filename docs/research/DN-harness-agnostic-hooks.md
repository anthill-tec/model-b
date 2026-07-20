# DN — Harness-agnostic hooks for the Model B ecosystem

**Author:** Antony (antonyj)
**Co-author:** vidushi-mdb (solo orchestrator — Model B)
**Date:** 2026-07-20
**Status:** DRAFT (survey complete; strategy recommended; implementation rides CR-MDB-013/015)
**Sources:** primary docs fetched 2026-07-20 — Claude Code (code.claude.com/docs/en/hooks), OpenAI Codex CLI (developers.openai.com/codex/hooks), Gemini CLI (geminicli.com/docs/hooks/), Cursor (cursor.com/docs/hooks), GitHub Copilot CLI (docs.github.com/en/copilot/reference/hooks-reference), opencode (opencode.ai/docs/plugins/), Sourcegraph Amp (ampcode.com/manual), agents.md, vercel-labs/skills.

## 1 Problem
PRD §D10.7 scopes hooks to the PROJECT (stack-specific concerns). The Model B ecosystem is harness-agnostic, but every harness implements hooks differently — and two (opencode, Amp) have no shell-hook contract at all (in-process TS plugins only). AGENTS.md and the Vercel skills standard define ZERO hook semantics, so hooks cannot ride either as a distribution vehicle. A portable design is required.

## 2 Survey summary (details in the fetched report)
- **Project-level config exists in every subprocess harness:** `.claude/settings.json` · `.codex/hooks.json` · `.gemini/settings.json` · `.cursor/hooks.json` · `.github/hooks/*.json`. opencode/Amp take project-dir TS plugins.
- **Universal event intersection (all 7):** pre-tool-use, post-tool-use, session-start, turn-stop. (+ prompt-submit, pre-compact across the 5 subprocess harnesses.)
- **Contract convergence:** stdin-JSON + exit-2-blocks is common to Claude/Codex/Gemini/Cursor/Copilot; Codex copies Claude's decision JSON verbatim; Copilot accepts Claude-style field casing natively.
- **Hard incompatibilities:** ask/defer decisions + input mutation are Claude-complete only; fail-direction diverges (Copilot preToolUse fail-closed, others fail-open); matcher regex anchored (Copilot) vs unanchored (Claude); Cursor matches shell command TEXT not tool name; timeout units s vs ms; Codex SHA-trust + Gemini fingerprints force human re-confirm on every regenerated config; cloud variants silently drop events.

## 3 Strategies considered
- **(a) Neutral schema → compiled per harness.** Scaffold emits each harness's native config (+ generated TS shim plugins for opencode/Amp). Gains native features + trust UX; costs N emitters + trust-reconfirm churn on regeneration.
- **(b) Least-common-denominator core.** Only the universal events, tool-name regex, allow/deny+reason. Fully portable, trivially testable; discards ask/mutation/subagent/file-watch richness.
- **(c) Shared script protocol + thin shims.** Hook LOGIC speaks the Claude contract (stdin JSON, exit 0/2, `hookSpecificOutput`) — near-zero shim for Claude/Codex/Copilot; field-name shims for Gemini/Cursor; spawn-wrappers for opencode/Amp. Logic written once, testable standalone; can't normalize fail-direction or timeout semantics.

## 4 Recommendation (design contract for CR-MDB-013/015)
**(a) + (c), with (b) as the guaranteed-portable core tier:**
1. A neutral hook-definition schema (event, matcher, command, decision-capability tier, timeout, fail-direction INTENT) lives in the project (scaffold-emitted, stack-derived).
2. Every `command` targets a **protocol-(c) script** (Claude-contract stdin/exit/JSON) from the shared script store — written once, unit-testable.
3. The scaffold/compiler emits per-harness native wiring; capabilities above the (b) core tier are emitted only where the harness supports them and DECLARED as degraded elsewhere (never silently lost).
4. Security-class hooks must state fail-direction intent; the compiler refuses to emit them to harnesses that cannot honor it (e.g. fail-closed impossible → emit refused + reported), because a guard that silently degrades is worse than none.
5. Trust-gate churn (Codex SHA, Gemini fingerprint) is accepted and documented as a re-confirm step in the scaffold's output.

## 5 Non-goals
- No attempt to standardize hooks INTO agents.md or the skills standard (out of our authority; revisit if those specs grow hook semantics).
- No normalization of harness-unique events (Claude FileChanged/Worktree*, Gemini BeforeModel, Cursor Tab hooks) — reachable via per-harness escape hatches in the schema, marked non-portable.
