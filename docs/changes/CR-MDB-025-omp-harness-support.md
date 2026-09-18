# CR-MDB-025 — OMP as a first-class deploy target: agent definitions, hooks, and the harness roster

**Status:** PENDING
**Type:** feature
**Priority:** P1 (blocks release 0.1.0 — OMP is the harness the orchestrator now runs on, and
Model B's generated agent definitions are **structurally invisible** to it: OMP deliberately
refuses to read `.claude/agents`, so every generated definition is unreachable on the harness
we actually use)
**Depends on:** CR-MDB-017 (the `--role`/`--cycle` + `tier_guidance` template work lands in the
same frontmatter/template surface this CR re-emits; sequencing after it avoids two rewrites of
the same generated files)
**Labels:** generator, installer, harness, agent-definitions, hooks, omp, feature
**Phase:** Wave 5
**Design reference:** **`docs/research/DN-multi-harness-deploy-model.md` — the governing design
note (user-ruled 2026-09-18); this CR implements its §D1–§D10 and must not re-decide them** ·
user directive 2026-09-16 ("I want our definitions etc be targeting for deploy to OMP") · user
directive 2026-09-09 (OMP preferred over Claude Code, tied to the Roundhouse migration) · user
directive 2026-09-18 (OMP does NOT consume the shared `~/.agents` store; and "bundling our Model
B definitions and tools as extensions may be useful") · `omp://task-agent-discovery.md` ·
`omp://skills.md` · `omp://hooks.md` · `omp://extensions.md` · `omp://extension-loading.md` ·
`omp://marketplace.md` · PRD §D10 (per-harness support is a first-class feature; the ecosystem
stays harness-agnostic) · `modelb_axi/hooks.py::compile_wiring()` (the neutral-schema +
per-harness-emitter precedent) · Roundhouse PRD §D4 (Tier-1 route map)

**RESHAPED 2026-09-18 by the DN — read it before this spec's older sections.** Three of this
CR's premises changed and the delivery vehicle changed with them:

1. **"Skills already work on OMP — no work required" is WITHDRAWN** (DN §D2, user ruling). OMP
   is the one harness that does not consume `~/.agents`; it needs its own skills, tools and
   agent definitions. The earlier "verified empirically" claim rested on this session's skill
   injections resolving from `~/.agents/skills` while OMP's own skill dirs measured EMPTY —
   treated now as incidental and not to be relied on.
2. **Delivery is a PLUGIN, not a directory copy** (DN §D10). OMP's marketplace plugin is
   literally "a directory containing skills, commands, agents, rules, hooks, tools" — Model B's
   whole payload in one versioned unit — and its catalog format is Claude-Code-compatible, so
   ONE repo with dual catalogs (`.omp-plugin/` + `.claude-plugin/`) serves both harnesses.
   Crucially it needs **no build toolchain**: OMP imports `.ts` directly through Bun, so factory
   adapters ship as source and `@oh-my-pi/pi-coding-agent` is a dev-only types dependency —
   which keeps this repo stdlib-only-Python with no JS build.
3. **The ownership boundary is explicit** (DN §D3): of the 29 hand-modelled definitions per
   harness, Model B generates 20 (24 with vscode as a bun/TS editor overlay, DN §D4) and must
   NEVER write or delete electronics ×4 or `inbox-analyst`. The census also found the
   hand-modelled set is NOT a safe copy source: `effort` appears in 10 files (Claude-Code key)
   against `thinking-level` in 9; `skills` in 10 with `autoloadSkills` in ZERO, so those ten
   silently autoload nothing; `color`/`maxTurns` in 16 each are in no OMP contract; and 19 of 29
   bodies still cite the stale `~/.claude/skills` store. Owning them means REGENERATING them
   correctly, which repairs all of that — not importing them.

Authoring the marketplace/plugin package itself is a SEPARATE CR (DN §Consequences) to be filed
at the next SCRUM; this CR owns the neutral schema, the emitters, and the asset class.

## Context

**Everything factual below is read from OMP's own documentation (`omp://…`) at omp/18.2.1 and
verified against the local install — not inferred from one sampled file.** An earlier draft of
this CR guessed the contract from a single agent file and got it wrong in both directions; the
corrections are recorded in §S0 so the wrong shape cannot be reintroduced.

### The blocking fact: OMP will never read our agent definitions

`omp://task-agent-discovery.md`, on discovery inputs:

> Direct cross-harness roots such as `.claude/agents`, `.codex/agents`, and `.gemini/agents` are
> **intentionally skipped** — their frontmatter schema is not the OMP task-agent contract
> (`TASK_AGENT_CONFIG_SOURCE = ".omp"` filters the native config-dir lists).

This is a deliberate refusal, not an oversight, and no toggle opens it. OMP reads agent
definitions from exactly two filesystem roots:

- **user:** `~/.omp/agent/agents/*.md`
- **project:** `.omp/agents/*.md` (nearest project `.omp` dir only)

with precedence project → user → extension roots → Claude marketplace plugins → bundled, and
first-wins dedup on exact case-sensitive `name`.

**Second blocking fact, found while verifying the first:** `modelb_axi/deploy.py` has **no
agent-definition asset class at all**. It deploys skill bundles (`STORE_RELDIR`), hook scripts
(`HOOKS_SCRIPTS_STORE_RELDIR`) and tool scripts (`TOOL_SCRIPTS_STORE_RELDIR`) — the generated
definitions under `generator/agents/` are never deployed by the installer at all. So this CR
adds an asset class; it does not retarget an existing one.

### Skills on OMP — the earlier "no work required" finding is WITHDRAWN (user ruling 2026-09-18)

**This section previously concluded that skills needed no work, and it was wrong. Kept, corrected
in place, because the reasoning error is instructive and must not recur.**

What the docs say is still true as written: `omp://skills.md` registers `agents` (priority 70)
for `.agent[s]/skills` and calls it "the canonical OMP-native location". What was WRONG was
inferring from that, plus one observation, that Model B therefore had nothing to do.

The observation: this orchestrator session is an OMP session, and the `bootstrap`/`shutdown`
skills it executed were stamped `[Skill directory: /home/antonyj/.agents/skills/<name>]` — i.e.
resolved out of the shared store. The measurement that should have been taken beside it:
`~/.omp/agent/skills/` and `~/.omp/agent/managed-skills/` both exist and are **EMPTY (0
entries)**, and OMP's `config.yml` references `~/.agents` nowhere.

**The user's ruling is decisive: OMP is the one harness that does NOT work with the shared
`~/.agents` set — it has its own agents and skills definitions.** Whatever produced those
resolved paths is treated as incidental and MUST NOT be relied on. Skills are therefore **in
scope for the OMP target**, delivered per DN §D2 (its own copy) or, preferably, per DN §D10
(inside the plugin, where `skills/` is a first-class plugin content type).

**The transferable lesson, recorded so it cannot recur:** "I observed it working" is not
evidence about WHICH mechanism made it work. One confounded observation was promoted to a
verified non-goal, which would have shipped an OMP target with no skills of its own. The same
failure mode as this CR's §S0 frontmatter error — inferring a contract from a sample instead of
measuring the contract and the alternatives together.

### The real frontmatter contract, and the corrections it forces

Per `parseAgentFields()` (`omp://task-agent-discovery.md`):

| Field | Status in OMP | Our generated definitions emit |
|---|---|---|
| `name` | **required** | ✅ `python-red-agent` |
| `description` | **required** | ✅ |
| body → `systemPrompt` | **required** | ✅ |
| `tools` | optional; CSV **or** array; `yield` auto-added | ✅ but Claude-Code tool NAMES |
| `model` | optional; one selector, CSV, or array tried in order; `@role` aliases expand via `modelRoles` | ⚠️ `sonnet` / `inherit` |
| `thinking-level` / `thinking` | optional; the effort surface | ❌ we emit `effort` |
| `autoloadSkills` | optional; injects named parent-session skills | ❌ we emit `skills` |
| `spawns` | optional; `*`, CSV, array | ❌ absent |
| `output`, `blocking`, `read-summarize`, `prewalk`, `advisor` | optional | ❌ absent |
| `color` | **not in the contract** | ⚠️ we emit it |
| `maxTurns` | **not in the contract** | ⚠️ we emit it |

Unknown keys are *preserved as unknown metadata*, so `color`/`maxTurns` are inert rather than
fatal — but they are noise, and `effort`/`skills` are **silently ineffective**, which is worse:
the definition looks configured and is not.

### §S0 — corrections to this CR's own earlier draft (recorded so they cannot recur)

The first draft sampled `~/.omp/agent/agents/arduino-fix-agent.md` and concluded "OMP drops
`effort`, `tools` and `skills`; OMP has `color` and `maxTurns`." Both halves are wrong:

- **OMP does have `tools`** — and an equivalent for each supposed drop: `effort` → `thinking-level`,
  `skills` → `autoloadSkills`. They are renames, not removals.
- **`color` and `maxTurns` are not OMP fields at all** — they appeared in the sample because that
  tree is a mix of provenances. Measured across its 30 files: 16 carry `maxTurns`, 16 `color`,
  10 `skills`, 10 `effort`, 9 `thinking-level`, 24 an `authority` key that is in no contract.
  Sampling one file from a mixed directory produced a confident wrong answer.

**Method rule for this CR: the contract comes from `omp://` docs plus the parser's documented
behavior, never from sampling deployed files.**

## Scope

### §S1 — Neutral agent-definition schema + per-harness emitters
Restructure `generator/build.py` so rendering produces a **neutral definition** (name,
description, body, tool intent, model/role, effort, autoload skills, spawn policy) which
per-harness emitters serialize — the exact shape `hooks.py::compile_wiring()` already proves for
hooks, including its refusal semantics.

- `_emit_claude_code()` — current output, **byte-identical** to today's 20 files.
- `_emit_omp()` — OMP's contract: `name`, `description`, `tools`, `model`, `thinking-level`,
  `autoloadSkills`; `effort`/`skills` renamed; `color`/`maxTurns` dropped.

### §S2 — Tool-name translation (not passthrough)
Our definitions name Claude Code tools (`Read, Grep, Glob, Bash`). OMP's are lowercase with a
different surface (`read`, `grep`, `glob`, `bash`, plus `ast_edit`, `lsp`, `hub`, `eval`,
`todo`, `task`). A copied `tools:` line grants nothing it names. The emitter translates through
an explicit map, and a tool with no OMP equivalent is **dropped with a recorded reason** —
never silently renamed to something plausible. `yield` is auto-added by OMP and must not be
emitted.

### §S3 — Model selector: role aliases, not hardcoded names
`model: sonnet` is a Claude Code alias. OMP resolves `@role` aliases through `modelRoles` in
`~/.omp/agent/config.yml` (the local install defines `task`, `plan`, `smol`, `advisor`,
`designer`, `default`, …). The OMP emitter emits a role alias, which is also what **Roundhouse
PRD §D4** wants — the Tier-1 route map living in `generator/stacks/*.toml` `model:`. `inherit`
maps to omission (OMP falls back to the parent's active model by documented precedence).

### §S4 — Agent definitions become an installer asset class
Add the missing class to `deploy.py` with the same sha256-manifest idempotence the other three
use: `AGENT_DEFS_*` reldirs per harness — `.omp/agent/agents/` for OMP, and Claude Code's
existing path for that harness — deployed per selected harness, hand-modified destinations
skipped unless `--force-managed`.

### §S5 — `omp` in the harness roster
`HARNESS_ROSTER` gains `("omp", "omp")` (binary confirmed: `omp --version` → `omp/18.2.1`).
`HARNESS_SKILL_DIRS` gets **no** OMP entry — OMP reads the neutral `.agents/skills` store
directly, so a symlink would be redundant (and `HARNESS_SKILL_DIRS` is documented as
symlink-only).

### §S6 — OMP hook emitter
`omp://hooks.md`: native user hooks load from `~/.omp/agent/hooks/pre/*.{ts,js}` and
`.../post/*.{ts,js}` (project: `<cwd>/.omp/hooks/pre|post/`); a factory placed directly in
`hooks/` is silently ignored. A module default-exports `(pi: HookAPI) => void` registering
`pi.on("tool_call", …)` → `{ block, reason }` / `pi.on("tool_result", …)`. `~/.omp/agent/hooks`
does not currently exist, so no Model B hooks reach OMP at all.

Add `_emit_omp()` to `hooks.py` beside the existing emitters. **`fail_direction: closed` is
honourable on OMP** — `tool_call` blocks on `{block:true}` and `HookToolWrapper` fails closed on
a handler throw — so security-class hooks must NOT be refused here. The existing `_emit_pi`
emitter is the closest precedent (OMP descends from pi — `omp://porting-from-pi-mono.md`) and
should be read before writing a new one, not copied blindly.

## Acceptance criteria

### §S1
- [ ] All 20 existing Claude Code definitions are **byte-identical** before/after — asserted by
      diffing rendered output; any change is a blocking defect.
- [ ] A documented neutral schema exists naming which fields are universal vs harness-specific.
- [ ] `build.py --check` covers both harnesses' rendered output and fails on drift in either.

### §S2
- [ ] No emitted OMP definition contains a Claude Code tool name (no `Read`/`Grep`/`Glob`/`Bash`
      capitalised forms) — asserted by grep over emitted files.
- [ ] The translation map is explicit in code, and every source tool resolves to an OMP tool or
      is dropped with a reason recorded in the commit message.
- [ ] No emitted OMP definition contains `yield` in `tools`.

### §S3
- [ ] Every emitted OMP definition's `model` is either a `@role` alias or absent; no literal
      `sonnet`/`inherit` survives.
- [ ] Each emitted alias exists in the documented `modelRoles` set, or the CR records why a new
      role is required.

### §S4
- [ ] A sandboxed `--target-root` install with `--harnesses omp` writes definitions to
      `<root>/.omp/agent/agents/*.md` and nothing outside the sandbox.
- [ ] Re-running reports them unchanged (hash idempotence), and a hand-modified destination is
      skipped without `--force-managed`.
- [ ] Deploying `--harnesses claude-code` alone writes no `.omp` path, and vice versa.

### §S5
- [ ] `HARNESS_ROSTER` contains `omp`; `detect_harnesses()` finds it via `shutil.which("omp")`.
- [ ] `HARNESS_SKILL_DIRS` has no `omp` key, with a comment recording why.

### §S6
- [ ] `_emit_omp()` writes `pre/`/`post/` subdirectories — never a factory directly in `hooks/`.
- [ ] Emitted modules default-export a function taking the hook API and register via `pi.on`.
- [ ] A `fail_direction: closed` instance targeting OMP is **accepted**, not refused; a test
      asserts OMP is not in the refusal path for security-class hooks.
- [ ] `AllTargetsRefusedError` still raises when every *other* selected harness refuses.

### Integration (wire-the-call-path gate)
- [ ] An integration test drives the real installer entry point with `--harnesses omp` against a
      temp root and asserts the deployed definition files parse as valid OMP frontmatter
      (required `name` + `description` present, no non-contract keys).
- [ ] **Runtime proof, not frontmatter inspection:** one emitted definition is placed in a real
      OMP-discoverable root and OMP resolves it by name (e.g. an agent lookup succeeds rather
      than failing preflight with `Unknown agent`). A definition that parses but does not
      resolve is not done.

## Estimated size

`generator/build.py` restructured to neutral + 2 emitters; `hooks.py` +1 emitter; `deploy.py`
+1 asset class (2 harness paths); `harness.py` +1 roster entry; 1 schema doc; tests for
emitters, deploy idempotence, and the runtime-resolution gate. The 20 generated Claude Code
files must not change.

## Risk

- **The byte-identity requirement on Claude Code output is the main regression risk.** Refactor
  to neutral + emitters without touching rendered bytes; if they move, the refactor is wrong.
- **Sequencing after CR-MDB-017 is deliberate** — 017 edits the same templates/frontmatter this
  CR re-emits. Doing 025 first means rewriting both.
- **Silent ineffectiveness is the failure mode to fear, not a crash.** OMP preserves unknown
  keys, so a wrong field name produces a definition that looks configured and does nothing.
  Every field must be asserted against the documented contract, not "it loaded fine".
- **Do not infer OMP behavior from sampled files** (see §S0). Use `omp://` docs.
- `~/.omp/agent/agents/` already holds 30 files of mixed provenance including another project's.
  Deploying there must be additive and name-scoped; a collision silently wins by first-wins
  dedup, so emitted names must stay `<stack>-<role>-agent`.

## Non-goals

- **No skills work** — already OMP-correct via the neutral `.agents/skills` store, verified live
  this session. Accounting only.
- No change to the other harness emitters' behavior (`hermes`, `pi`, `opencode`).
- No change to which stacks exist (CR-MDB-024's rust adoption is separate) and no vscode work.
- No OMP extension/marketplace packaging, MCP config, or `modelRoles` authoring on the user's
  behalf — we emit aliases and document the roles required.
- No decision on whether OMP becomes the *default* harness for new scaffolds (PRD §D10, separate).
