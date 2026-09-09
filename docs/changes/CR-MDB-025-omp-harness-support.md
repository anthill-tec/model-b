# CR-MDB-025 — OMP as a fifth harness: neutral agent-definition schema + per-harness emitters

**Status:** PENDING
**Type:** feature
**Priority:** P2 (not release-blocking for 0.1.0; user directive to adopt OMP as the preferred harness for the parent Roundhouse project makes it high-value for the NEXT wave)
**Depends on:** —
**Labels:** harness, generator, omp, agent-definitions, feature
**Phase:** Wave 6 (post-0.1.0; filed now, scoped explicitly to NOT block wave 5)
**Design reference:** user directive 2026-09-09 ("we have a new agentic harness called OMP; it has a different format for agent definitions though it is capable of reusing Claude's skill definitions; I am more inclined to use OMP over Claude given we are also migrating to the Roundhouse, your parent project's requirements") · `modelb_axi/hooks.py::compile_wiring()` (the existing neutral-schema + per-harness-emitter pattern this CR mirrors) · `modelb_axi/harness.py` (the roster this CR extends) · PRD §D10 ("target harness — a SETUP QUERY... per-harness support is a first-class FEATURE... the scaffolded ecosystem itself stays harness-agnostic")

## Context

Model B's harness roster (`modelb_axi/harness.py::HARNESS_ROSTER`) is four ids:
`claude-code`, `hermes`, `pi`, `opencode`. OMP — the harness this very orchestrator session
runs under — is not among them, and the gap is not merely a missing roster entry: agent
DEFINITIONS have a real, measured format divergence between Claude Code and OMP that skills do
not.

**Skills are already largely harness-agnostic** — `~/.agents/skills/` is the Vercel-Skills-
standard neutral store CR-MDB-002/014 already built, and `~/.claude/skills/model-b` is a
symlink into it (`deploy.py::HARNESS_SKILL_DIRS`). OMP additionally carries its own
`~/.omp/agent/managed-skills/` for session-local skill authoring, but per the user's own
statement it is "capable of reusing Claude's skill definitions" — confirmed: this session's own
managed skills coexist with, and do not replace, the shared store. **No change needed for
skills.**

**Agent definitions are not harness-agnostic, and the divergence is measured, not assumed.**
Compared directly, 2026-09-09, `~/.omp/agent/agents/arduino-fix-agent.md` (a real OMP agent
definition — this happens to be Crucible's own dogfood copy, visible because `~/.omp/agent/`
is a machine-wide, not per-project, directory) against this repo's own generated Claude Code
shape (`generator/stacks/quarkus.toml`'s frontmatter pattern):

| Field | Claude Code (this repo's generator output) | OMP (measured) |
|---|---|---|
| `name` | yes | yes |
| `description` | yes | yes |
| `model` | yes | yes |
| `effort` | yes (`high`/`medium`) | **absent** |
| `color` | yes | yes |
| `tools` | yes (explicit allow-list, e.g. `Read, Grep, Glob, Bash`) | **absent** |
| `maxTurns` | yes | yes |
| `skills` | yes (declared array) | **absent** |

OMP drops `effort`, `tools`, and the declared `skills:` array entirely — presumably resolved by
the harness at runtime rather than declared per-agent, which is a real behavioral difference,
not a naming one. `generator/build.py` today renders exactly one shape, directly to
`generator/agents/*.md`, deployed as literal `~/.claude/agents/*.md`. There is no neutral
intermediate and no per-harness compiler for agent definitions the way `hooks.py` already has
for hooks.

**The precedent to mirror already exists in this repo.** `modelb_axi/hooks.py::compile_wiring()`
takes a neutral schema instance (`{event, matcher, command, tier, timeout, fail_direction}`),
partitions per harness (`_partition()`), and fans out to `_emit_claude_code()`,
`_emit_opencode()`, `_emit_pi()`, `_emit_hermes_advisory()` — each harness gets exactly the
wiring shape it can honour, and a hook a harness cannot honour is REFUSED rather than
silently degraded (`AllTargetsRefusedError`). Agent-definition emission needs the identical
shape: one neutral generator output (already close to what `generator/templates/*.tmpl` +
`generator/stacks/*.toml` produce today), fanned out per harness by a compiler that knows what
each harness's frontmatter actually supports.

**Scope discipline, stated because it was checked, not assumed.** This CR does NOT touch
CR-MDB-017 or CR-MDB-024, which ship this wave targeting Claude Code only — by explicit user
scoping decision, 2026-09-09, made precisely so this CR would not block or reshape in-flight
work. Nor does it redesign `generator/build.py`'s current single-target-per-file rendering
before 017/024/012 ship; it adds a parallel emission path once they have.

## Scope

### §S1 — Add `omp` to the harness roster
`modelb_axi/harness.py::HARNESS_ROSTER` gains `("omp", "omp")` (binary name to be confirmed
against the real OMP CLI entry point at gap-analysis — `which omp` resolved to `~/.bun/bin/omp`
on this machine, which is a `shutil.which`-visible name and should probe correctly, but the
exact packaged binary name must be verified, not assumed from one developer machine).
`HARNESS_SKILL_DIRS` gains an OMP entry if OMP's skill-discovery directory differs from
`~/.claude/skills`'s symlink-target shape — to be confirmed against OMP's actual skill-loading
convention rather than guessed from `~/.omp/agent/managed-skills/`'s existence alone.

### §S2 — Neutral agent-definition schema
A schema analogous to the hooks neutral schema: the fields every harness needs
(`name`, `description`, `model`, `color`, `maxTurns`) versus the fields only some harnesses
consume (`effort`, `tools`, `skills`). Documented in `generator/` alongside the existing
templates, in the same spirit as `hooks-src/schema.md` documents the hooks schema.

### §S3 — Per-harness agent-definition compiler
A `_emit_claude_code()`/`_emit_omp()` fan-out mirroring `hooks.py::compile_wiring()`'s shape:
`_emit_claude_code()` renders the full frontmatter (current behavior, unchanged — this is a
strictly additive CR); `_emit_omp()` renders OMP's measured subset (`name`, `description`,
`model`, `color`, `maxTurns`), dropping `effort`/`tools`/`skills` rather than emitting fields
OMP does not read. Both emit from the SAME rendered body content — the frontmatter is what
diverges, not the instructions.

### §S4 — Deploy path
`deploy.py` gains an OMP target analogous to the existing `HARNESS_SKILL_DIRS`/agent-deploy
pattern, writing to wherever OMP's own agent-discovery path resolves (`~/.omp/agent/agents/`
observed on this machine; the resolution rule — fixed path vs. `$OMP_HOME`-relative vs.
something else — must be confirmed against OMP's own documented convention, not this one
developer machine's layout).

## Acceptance criteria

### §S1
- [ ] `HARNESS_ROSTER` includes `omp`; `detect_harnesses()` finds it when the real OMP binary
      is on `PATH`, verified against OMP's actual packaged entry point name (not assumed from
      one machine's `~/.bun/bin/omp`).
- [ ] `select_harnesses(["omp"], ...)` resolves correctly and rejects unknown ids as before.

### §S2
- [ ] A documented neutral agent-definition schema exists, naming which fields are
      universal vs. harness-specific, with OMP's measured absence of `effort`/`tools`/`skills`
      recorded as a confirmed fact (this CR's own measurement), not a guess.

### §S3
- [ ] Claude Code output is BYTE-IDENTICAL to current `generator/build.py` output — this CR is
      additive, and a regression in the existing 20 (16 + CR-MDB-024's rust set) generated
      definitions is a blocking defect.
- [ ] OMP output omits `effort`, `tools`, and `skills` from frontmatter and is a real,
      parseable OMP agent definition — verified by OMP actually loading and using one in a
      sandboxed session, not by frontmatter inspection alone.
- [ ] The two emitters render from one shared body-content source; the instructional text is
      not duplicated or hand-forked between them.

### §S4
- [ ] A sandboxed `--target-root` install with `--harnesses omp` deploys agent definitions to
      OMP's real discovery path and OMP can load at least one of them.
- [ ] No write occurs outside the sandboxed target in any test.

## Estimated size

Unknown until gap-analysis confirms OMP's real binary name, skill-directory convention, and
agent-discovery path — all three are measured from one developer machine today and must be
confirmed against OMP's own documentation or a second machine before this CR's Scope is
finalized. Rough shape: `harness.py` (+1 roster entry), `hooks.py`-sized new compiler module or
extension to `generator/build.py`, `deploy.py` (+1 target), 1 new schema doc, tests for all
three.

## Risk

- **Everything about OMP's conventions in this CR is measured from ONE machine.** The binary
  name, the skill-reuse mechanism, and the agent-discovery path all need independent
  confirmation (OMP's own docs, or a second install) before GREEN — do not generalize from
  `~/.omp/agent/` on this developer's home directory alone.
- **Do not let this CR touch CR-MDB-017/024's in-flight Claude-Code-only work.** The explicit
  user scoping decision (2026-09-09) was to keep them unblocked; a later gap-analysis that finds
  overlap routes the overlap forward to this CR, never backward into 017/024.
- Frontmatter field dropping (`effort`/`tools`/`skills`) must not silently change agent
  BEHAVIOR under OMP if OMP resolves those concerns some other way (e.g. tool access via a
  different mechanism) — that resolution must be confirmed, not assumed equivalent.

## Non-goals

- No change to CR-MDB-017 or CR-MDB-024's scope, content, or sequencing.
- No redesign of `generator/build.py`'s current template×stack rendering mechanism before this
  CR's own gap-analysis confirms the shape a neutral intermediate should take.
- No decision here about whether OMP becomes the DEFAULT harness for new Model B scaffolds —
  that is a PRD §D10 discussion for whenever this CR is scheduled, not a decision made in this
  spec.
