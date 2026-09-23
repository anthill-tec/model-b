# CR-MDB-025 — Pi as the deploy target for agent definitions: neutral schema, `_emit_pi()`, and the agent-definition asset class

**Status:** PENDING (re-specced 2026-09-21 for Pi; the OMP version of this spec is git history —
`git log --follow docs/changes/CR-MDB-025-*` — and is NOT to be consulted for contracts)
**Type:** feature
**Priority:** P1 — **in release 1.0.0, wave 2** (user ruling 2026-09-21, together with CR-MDB-027)
**Depends on:** CR-MDB-027 (the dispatch ruling this CR implements — DN §D16) · CR-MDB-017 (its §S6
rewrites the same four templates and regenerates the fleet; sequencing after it avoids two
rewrites of the same files) · CR-MDB-024 lands its rust stack in the same generator surface and
should precede this CR so one regeneration settles the whole fleet · **CR-MDB-033** (added
2026-09-21: `deploy.py:123-131` overwrites an unmanaged same-named file on first install, so
§S4's `inbox-analyst.md` AC cannot hold until 033 §S3 lands; and the scaffold compiles wiring
against a `[install].target_root` the installer never writes, so §S6's sandbox proof is untrusted
until 033 §S1) · **CR-MDB-030** (§S6.2's dispatch proof presumes the emitted `.pi/extensions/`
load at all — they do not today; 030 fixes the runtime and owns the `-p` trust-gate measurement)
**Labels:** generator, installer, harness, agent-definitions, pi, feature
**Phase:** Wave 5 (repo queue) · release 1.0.0 wave 2 (Crucible board)

## Amendment 2026-09-22 — measured during CR-MDB-021, from four live dispatches

Four sub-agents were dispatched during CR-MDB-021 (RED ×2, GREEN ×2, FIX, VERIFY). **Every one
of them could author files and none of them could execute anything.** The orchestrator ran every
test and carried every Crucible registration. This is §S2's prediction confirmed in the field,
plus three facts this spec currently gets wrong.

**1. The dispatch provider named in §D16/CR-MDB-027 is NOT what is running.**
`~/.pi/agent/npm/node_modules/@pi-archimedes/` is an **empty directory**, and `pi-archimedes` is
absent from `settings.json` `packages[]`. The live dispatcher is **`@gotgenes/pi-subagents`
v21.7.5**. Every contract in this CR sourced from "the archimedes contract" must be re-derived
from `@gotgenes/pi-subagents/docs/configuration.md`, which is authoritative and installed
locally. CR-MDB-027's ruling needs the same correction — it is a dispatch-provider ruling naming
a package that provides no dispatch.

**2. The `tools` contract, read from the live docs (`docs/configuration.md:190-233`):**

- `tools` is the agent's **complete allowlist of capability tools, not a filter over built-ins**.
- The seven built-ins are lowercase: **`read`, `bash`, `edit`, `write`, `grep`, `find`, `ls`**.
- **Omitting `tools` gives all seven built-ins and NO extension tools** — so a generated agent
  with no `tools:` line gets no `ctx_*` tool at all, and lean-ctx is unreachable from it.
- **Naming an extension's tool is the only way to admit it.** The child loads the parent's
  extensions and their `registerTool` does run, but the allowlist is applied *before* the child's
  registry is built, so an unlisted tool is silently dropped — "the registration reports no
  error; the tool simply is not there."
- `subagent`/`get_subagent_result`/`steer_subagent` are always removed (recursion guard);
  `ask_parent`/`notify_parent` are always added.
- Accepted forms: comma string, flow sequence, block sequence, or `tools: none`.

**3. Capitalised Claude-era names are the measured cause of a ZERO-tool agent.**
`~/.agents/agents/python-verify-agent.md` carries `tools: Read, Grep, Glob, Bash`. Dispatched, it
reported **no tools whatsoever — not even read** — and correctly refused to produce a review
rather than fabricate one. `inbox-analyst.md` carries `tools: '*'` and works. That is a control
and an experiment: the allowlist is matched literally, so four names that match no registered
tool admit nothing. §S2 called this exactly ("a `--tools` allowlist that grants **none**"); it is
no longer a prediction.

**4. RESIDUAL RESOLVED 2026-09-22 by direct probe — `ctx_shell` is the ONLY shell a child has.**
A throwaway probe agent (`tools: read, bash, grep, find, ls, ctx_shell, ctx_read`) was dispatched
and asked to report its own callable schema. Measured:

- **The allowlist works, and it admits extension tools by name.** `ctx_shell` was granted and
  successfully ran `echo PROBE_CTXSHELL_OK`. Naming a `ctx_*` tool is sufficient and effective.
- **There is NO native shell tool in this Pi install.** A second probe listing
  `bash, Bash, shell, Shell, exec, run, terminal, sh, command` resolved **none** of them; only
  `read` and `ctx_shell` appeared in the callable schema. The docs' "seven built-ins" list
  includes `bash`, but no tool by that name exists here — so a child with no `tools:` key gets no
  extension tools AND no shell, which is exactly why RED/GREEN/FIX could author but never execute.
- **Therefore `ctx_shell` is not a preference for dispatched agents; it is the only shell.** An
  emitted definition that omits `ctx_shell` produces an agent that cannot run a test, full stop.
- **The child's advertised tool list is the PARENT's** (`@gotgenes/pi-subagents` #901). The probe
  saw ~45 tools named in its prompt prose against 8 real schemas. This is why three agents tried
  `ctx_shell`, were told "Tool not found", and spent turns diagnosing the harness instead of
  working. The prose lies; only the schema is real.

This closes the residual: the cause is not `effort`/`color`/`skills`/`model: inherit`. It is the
combination of no `tools:` key (⇒ no extension tools) with no native shell existing at all.

**5. `@gotgenes/pi-permission-system` was installed 2026-09-22 — it CHANGES this CR's contract.**
Measured immediately after install, same probe method:

- **It fixes the #901 prompt lie, partially.** The child now carries a second, ACCURATE
  `Available tools:` block (8 entries, matching its real schema) alongside the inherited 45-entry
  prose list. A dispatched agent can now tell what it really has — the misdiagnosis that cost
  turns in CR-MDB-021 is less likely to repeat.
- **It BLOCKS `ctx_shell` by default in a non-interactive child.** First probe after install:
  `[pi-permission-system] This 'ctx_shell' call for agent 'mdb-tool-probe' requires approval, but
  no interactive UI is available.` The tool was in the schema and still did not run. **Granting a
  tool via `tools:` is no longer sufficient** — an unlisted policy defaults to `ask`, and `ask`
  in a background sub-agent is a hard stop.
- **`permission:` frontmatter resolves it.** With
  `permission:\n  ctx_shell: allow\n  read: allow\n  ctx_read: allow`, the same probe ran
  `echo PROBE_OK && python3 -c "print(2+2)"` and returned `PROBE_OK / 4`, exit 0, no prompt.
- Surfaces are named per tool (`read: allow`, `write: deny`, `bash: {git *: ask}`), and
  `permission:` is read **exclusively** by this extension — `@gotgenes/pi-subagents` ignores it.

**Consequence for §S7: the emitter must write BOTH keys.** `tools:` decides what exists;
`permission:` decides whether it may run. A generated agent with `tools: ... ctx_shell` and no
`permission:` block is a fully-equipped agent that stalls on its first command with no human
there to approve it — indistinguishable, from the orchestrator's side, from an agent that did
nothing.

### §S7 (ADDED) — the emitter grants tools, and grants lean-ctx

The emitter MUST write an explicit `tools:` line. Omission is not "use the default" — it is
"no extension tools", which silently removes lean-ctx from every dispatched agent.

- **Tool names are lowercase Pi names**, never Claude-era capitalised ones. A capitalised name is
  not a portability wart; it is a measured zero-tool agent.
- **lean-ctx is named explicitly, and its shell wrapper is the shell of record** —
  `ctx_shell`, `ctx_read`, `ctx_grep`, `ctx_glob`, `ctx_find`, `ctx_ls`, `ctx_patch`. **Measured
  2026-09-22: `ctx_shell` is the ONLY shell available to a dispatched child** — no `bash` or any
  other native shell name resolves in this install — so this is not a style preference but the
  difference between an agent that can run a test and one that cannot. `bash` may still be listed
  for portability to installs that have it, but `ctx_shell` is mandatory.
- **Per-role grants**, not one list for all four:
  - RED / GREEN / FIX — read+write+execute: `read, write, edit, grep, find, ls, bash` plus the
    `ctx_*` set.
  - VERIFY — read-only: `read, grep, find, ls, bash` plus `ctx_read, ctx_grep, ctx_glob,
    ctx_find, ctx_ls, ctx_shell`, and **no `write`/`edit`/`ctx_patch`**. A VERIFY agent that
    cannot write is enforced by the allowlist rather than by asking it nicely in prose.
- **A `permission:` block is emitted beside `tools:`** (required since the permission system was
  installed 2026-09-22 — see amendment point 5). Every tool the role is granted carries an
  explicit `allow`, because an unstated policy defaults to `ask` and `ask` cannot be answered in
  a background child. For VERIFY, `write: deny` and `edit: deny` are stated as well, so the
  read-only property is enforced twice — once by absence from the allowlist, once by policy.
- **`skills:` is dead frontmatter** under v21 and must not be emitted; children inherit the
  parent's skills. Emitting it is harmless only until it is not — and it currently documents a
  capability the agent does not get that way.
- The stack TOML carries intent names; the emitter translates. A role with no `tools` key emits
  no `tools:` line **only if that is deliberate** — and the default for the four TDD roles is
  never that.
- **The RED template requires every test to be proved both ways** (user-approved 2026-09-23,
  already applied by hand to the five live `*-red-agent.md` definitions, which the next build
  overwrites). `generator/templates/red.md.tmpl` gains, after its "Self-check per test" rule, a
  NON-NEGOTIABLE rule that the RED agent proves each test (1) FAILS for the right reason on
  current code and (2) is PASSABLE by an implementation the spec permits, with a regression pin
  proved by showing it fails against the regression it guards, and reports both proofs. The
  orchestrator then accepts the phase from those proofs and its Crucible ingest instead of
  re-running it.

**§S7 acceptance criteria**

- [ ] Every emitted agent definition carries an explicit `tools:` line; zero emitted files omit it.
- [ ] Zero emitted `tools:` values contain a capitalised name (`Read`, `Grep`, `Glob`, `Bash`,
      `Write`, `Edit`) — asserted by a gate over the generated fleet, with a detector fixture that
      proves the gate bites on a capitalised value.
- [ ] Every emitted RED/GREEN/FIX definition names `ctx_shell` and at least `ctx_read`,
      `ctx_grep`; every emitted VERIFY definition names the read-only `ctx_*` subset and omits
      `write`, `edit` and `ctx_patch`.
- [ ] Every emitted `*-red-agent.md` contains the "Prove every test BOTH ways" rule (fails for
      the right reason; passable by a spec-permitted implementation; pins proved against their
      regression) — asserted by a gate over the generated fleet.
- [ ] No emitted definition carries a `skills:` key (removed from the schema in v21).
- [ ] **Measured, not assumed:** a dispatched generated agent of each role reports that it can run
      `ctx_shell`, recorded with the transcript reference.
- [ ] Every emitted definition names `ctx_shell` — asserted by a gate over the generated fleet.
      An agent without it cannot execute anything in this install.
- [ ] Every emitted definition carries a `permission:` block granting `allow` to every tool its
      own `tools:` line admits; zero emitted files grant a tool without a matching policy.
      Asserted by a gate that cross-checks the two frontmatter keys against each other.
- [ ] Emitted VERIFY definitions state `write: deny` and `edit: deny` explicitly, in addition to
      omitting them from `tools:`.
- [ ] **Measured end-to-end:** a dispatched generated agent of each role runs a real command via
      `ctx_shell` and returns its output — not merely "has the tool". Recorded with the transcript
      reference. A tool present but policy-blocked looks identical to a working agent until it
      stalls.
- [ ] The generated agent BODIES stop instructing `Bash` and stop citing `~/.claude/scripts/` for
      the Crucible client (CR-MDB-020 owns the path; this CR owns the tool name). A body that
      tells an agent to use a tool its own frontmatter does not grant is a self-inflicted
      zero-tool report.
- [ ] `docs/research/DN-multi-harness-deploy-model.md` §D16 and CR-MDB-027 are corrected to name
      `@gotgenes/pi-subagents` as the dispatch provider, with the empty `@pi-archimedes/`
      directory recorded as the evidence.

**Design reference:** `docs/research/DN-multi-harness-deploy-model.md` — **§D13** (target is Pi),
**§D14** (Claude Code dropped; byte-identical constraint RETIRED), **§D15** (the five Pi
measurements), **§D16** (dispatch = `pi-archimedes`; emitter target `~/.agents/agents/`), §D1
(neutral source), §D3 (ownership boundary), §D9 (no retro-deploy) · CR-MDB-027 §S1.1 (the
measured archimedes contract) · PRD §D6 (role templates × stack params) · PRD §D10 (per-harness
support is a first-class installer feature) · Roundhouse PRD §D4 (`generator/stacks/*.toml`
`model:` is the Tier-1 seam) · `modelb_axi/hooks.py::compile_wiring()` (the neutral-schema +
emitter precedent)

**Target set, ruled:** **Pi only.** OMP is not a target — not primary, not transitional (user
ruling 2026-09-21). Claude Code is not a target (§D14). Nothing in this CR emits to, reads from,
or verifies against `~/.omp/` or `~/.claude/`.

## Context

### What is broken today

1. **Agent definitions have never been an installer asset class.** `modelb_axi/deploy.py`
   deploys skills (`STORE_RELDIR`), hook scripts (`HOOKS_SCRIPTS_STORE_RELDIR`) and tool scripts
   (`TOOL_SCRIPTS_STORE_RELDIR`). `generator/agents/*.md` ships in the wheel (`pyproject.toml`
   force-include) and is deployed **nowhere**. The 25 files in `~/.agents/agents/` today are
   hand-placed.
2. **The generated frontmatter is Claude Code's, and on Pi half of it is inert or wrong.**
   `generator/stacks/*.toml` `[frontmatter]` emits `model: sonnet|inherit`, `effort`, `color`,
   `maxTurns`, `skills: [...]`, `tools: Read, Grep, Glob, Bash`. Against the archimedes contract
   (CR-027 §S1.1): `model` is passed **literally** as `--model`, so `sonnet` and `inherit`
   resolve to nothing and fall through to the parent's model by accident; `effort` is not read
   (`thinking` is); `color`/`maxTurns`/`skills` are preserved as unknown keys and do nothing;
   `Read, Grep, Glob, Bash` are Claude Code tool names — a `--tools` allowlist that grants **none
   of them** (Pi's are `read`, `grep`, `find`, `bash`, …). The definitions look configured and
   are not — the silent-ineffectiveness failure mode, which is worse than a crash.
3. **The templates' bodies cite the retired `~/.claude/skills/...` store** (DN §D3 census: 19 of
   29 bodies). Whether that repoint belongs here or to CR-MDB-020 is settled at gap-analysis
   (§S0), not assumed.

### The contract (measured, CR-027 §S1.1 — from the package's source, not from sampled files)

| Field | archimedes | This CR emits |
|---|---|---|
| `name` | **required**; skipped if absent | `<stack>-<role>-agent` (unchanged) |
| `description` | **required** | from `[description]` (unchanged) |
| body | system prompt (`--system-prompt`) | rendered template body |
| `tools` | **comma-separated string** → `--tools` allowlist | translated Pi core names (§S2) |
| `model` | literal `--model`; agent → per-call → parent | `switchyard/<route-id>` or **omitted** (§S3) |
| `thinking` | literal `--thinking`; NOT inherited from parent | from `effort` (§S1) |
| anything else | preserved, never interpreted | **nothing else** |

Discovery scopes: project `<repo>/.pi/agents/` → user `~/.pi/agent/agents/` → global
`.agents/agents/` (nearest ancestor of cwd) or `~/.agents/agents/`. The installer targets the
last: it is the shared store Pi already uses for skills (§D15.1) and tool scripts (CR-022).

**Method rule (kept from the OMP-era spec because it was earned twice):** the contract comes from
the provider's documentation and source, never from sampling deployed files. `~/.agents/agents/`
is a mixed-provenance directory and proves nothing about what the reader accepts.

## Scope

### §S0 — Gap-analysis questions to settle before RED (recorded so they are not skipped)

**Answered 2026-09-21 by the review filings:**

- Body citations `~/.claude/skills/<name>/...` in templates and `crucible_reference`: **CR-MDB-031
  §S2** owns them, running after 017/020/025 so the fleet is regenerated once more, last. This CR
  leaves the bodies untouched.
- `skills:` replacement: settled at this CR's gap-analysis (unchanged).
- Test pins that are §D14 amendments (from `audits/2026-09-21-codebase-review-tests.md` §1d):
  `tests/test_agent_generator.py:365-447,603-625` and `tests/test_installer_assets.py:323-360`
  freeze `render()` output and pin `~/.claude/agents`; listed by id in the RED plan.

**Still open:**

- **Reconciled with the independent root review (2026-09-21):**
  - `contracts/switchyard-routes.md` v0.1 names Model B's consumer surface as `[frontmatter] model:`;
    §S1 replaces it with `[roles.<role>] model`. **CReq to root:** the contract's Pi consumer row
    (item 5 of the review) must cite `generator/stacks/*.toml` `[roles.<role>] model` and
    `~/.agents/agents/` (DN §D16). Model B consumes the contract; this CR never edits it.
  - **Not blocked by the Tier-1 map.** The review calls the Tier-1 map "now blocking because
    pi-archimedes cannot resolve `model: sonnet`/`inherit`". Measured (CR-027 §S1.1): an agent file
    with NO `model:` falls through to the per-call override, then the parent's active model. §S3
    emits no `model:` line until the `CR-RND` sets route ids, so every definition is valid and
    dispatchable before that CR exists. The Tier-1 map blocks the routing *assessment*, not this CR.
  - **`user`-field workload identity (review items 6/20/21) — gated on CR-SY-003 §S1.** CR-SY-003
    defers "harness-side change to stamp agentId into `user`" until its probe says `user recorded`.
    On Pi the dispatched process receives only `--model` from archimedes; the agent id
    (`CR-<ACRONYM>-NNN-<cycle>-<PHASE>`) lives in the task prompt. The review's constraint — role in
    `user`, NOT via the hook compiler and NOT via a Pi-specific extension — leaves only a Pi
    provider-config mechanism, which is **unmeasured**. If §S1 returns `user recorded`, the Pi
    stamping mechanism is measured first and raised at root if the constraint cannot be met; this
    CR's emitter carries nothing for it until then.
- Which CR owns repointing the template bodies' `~/.claude/skills/<name>/...` citations to the
  deployed store (`~/.agents/skills/<name>/...`): CR-MDB-020 (path anchoring) or this one. If
  020 has shipped and left them, this CR takes them; if 020 is pending, its scope is amended.
- Whether `tests/test_agent_generator.py` / `tests/test_installer_assets.py` pin any Claude Code
  frontmatter key (`effort`, `color`, `maxTurns`, `skills`, capitalised tools). Every such pin is
  a sanctioned amendment under §D14, listed in the RED plan by test id.
- Whether `skills:` (autoload on Claude Code) has a body-level replacement: archimedes has no
  autoload, and Pi loads skills on demand from `~/.agents/skills`. Proposed: a single "Load these
  skills first:" line in the body, sourced from the same TOML list. Confirm or drop.

### §S1 — Neutral definition + one emitter
`generator/build.py` renders each stack × role into a **neutral definition** — a plain dict:
`name`, `description`, `body`, `tools` (list of Claude-era intent names as authored),
`model` (route id or `None`), `thinking`, `skills` (list) — then `_emit_pi(defn) -> str`
serialises it. **One emitter.** No `_emit_claude_code()` is written (§D14 retired it; YAGNI); the
neutral dict is what keeps a future emitter a one-function change (§D1).

`generator/stacks/*.toml` `[frontmatter]` free-text blocks are replaced by structured per-role
tables so the emitter never parses YAML it wrote:

```toml
[roles.verify]
model = ""                 # empty → omitted (inherit parent); else a switchyard/<route-id>
thinking = "medium"
tools = ["Read", "Grep", "Glob", "Bash"]   # intent names; translated by the emitter
skills = ["reviewer", "reviewer-coverage", …]
```

`build.py --check` keeps its drift-gate semantics over the regenerated fleet.

### §S2 — Tool-name translation (explicit map, drop-with-reason)
Intent names → Pi core names through one explicit dict in `build.py`:
`Read→read`, `Grep→grep`, `Glob→find`, `Bash→bash`, `Edit→edit`, `Write→write`, `LS→ls`.
A name with no Pi equivalent is **dropped and the drop recorded** (in the emitter's report and
the commit message) — never renamed to something plausible. Emitted form is the CSV string
archimedes requires (`tools: read, grep, find, bash`). A role with no `tools` key emits no
`tools:` line (Pi's normal selection applies).

### §S3 — `model:` is the Tier-1 seam; no alias, no Claude Code names
Per DN §D15.5 Pi has no role-alias layer; a definition's model is a concrete provider/model id.
The emitter writes `model: <value>` **verbatim from the TOML** when non-empty and omits the key
when empty. This CR sets every role's value to **empty** (inherit the orchestrator's active
model) — the route-id values are Roundhouse PRD §D4's Tier-1 map and change only through a
`CR-RND` that updates `contracts/switchyard-routes.md` and this TOML in one wave. No literal
`sonnet`, `inherit`, `opus`, `haiku` survives anywhere under `generator/`.

### §S4 — Agent definitions become an installer asset class
`deploy.py` gains the fourth class with the same sha256-manifest idempotence as the other three:
`AGENT_DEFS_STORE_RELDIR = ".agents/agents"`, `_agent_defs()` sourcing
`generator/agents/*.md` from the packaged asset root, `[install].agent_defs_dir` written to
`install.toml`. Deployed **once, user-scope, no per-harness symlink** — the `.agents/scripts`
shape from CR-022 — because the reader is the shared store itself. Hand-modified destinations
are skipped unless `--force-managed`. **§D3 ownership:** the installer writes only the names it
generates (20; 24 with the vscode overlay once §D4 lands) and never writes, renames or deletes
any other file in that directory — `inbox-analyst.md` is the standing example.

### §S5 — Nothing else changes in the installer
`pi` is already in `HARNESS_ROSTER`. `_emit_pi()` in `hooks.py` already exists (CR-015) and its
runtime correctness is CR-019's. No roster change, no hook emitter, no `HARNESS_SKILL_DIRS`
change. `~/.claude/agents/` is unowned legacy (§D14): never written, never deleted.

### §S6 — Runtime proof and the trust caveat
The integration gate proves the **reader** accepts the output, not merely that a YAML parser
does. Two proofs:
1. **Discovery:** from a cwd whose nearest `.agents/agents/` is the sandbox root, archimedes'
   discovery lists every emitted definition by name and none is skipped for a missing
   required field.
2. **Dispatch into a fresh worktree (measures DN §D16 consequence 4):** one emitted VERIFY
   definition is dispatched with `cwd` = a fresh git worktree carrying CR-015's emitted
   `.pi/extensions/` **as rebuilt by CR-MDB-030** (today's emitted extensions do not load: no
   default-export factory, no payload transport — 030 §S8 owns the primary trust-gate
   measurement; this proof re-runs it end-to-end through archimedes). Record whether `-p` mode loaded the project extensions (the write-boundary
   block fires on an attempted `write`) or skipped them at the trust gate. Either answer is
   recorded in the CR close-out note; if skipped, the `tools` allowlist is the only boundary on
   Pi and `sub-agent-procedure.md` must say so.

## Acceptance criteria

### §S1
- [ ] `build.py` produces a neutral dict per stack × role and `_emit_pi()` is the only serialiser;
      a test asserts the emitted frontmatter key set is exactly ⊆ {`name`, `description`,
      `tools`, `model`, `thinking`}.
- [ ] `generator/stacks/*.toml` carry structured `[roles.<role>]` tables; no `[frontmatter]`
      free-text block remains.
- [ ] `build.py --check` is clean after regeneration and fails on a one-byte drift.

### §S2
- [ ] No emitted definition contains a capitalised Claude Code tool name — grep gate over
      `generator/agents/`.
- [ ] The translation map is a module-level dict; a test feeds an unknown intent name and
      asserts it is dropped with a recorded reason, not passed through.
- [ ] Emitted `tools:` is a single CSV string, never a YAML list.

### §S3
- [ ] Zero occurrences of `model: sonnet|inherit|opus|haiku` under `generator/` — grep gate.
- [ ] A TOML role with `model = ""` emits no `model:` line; one with `model = "switchyard/x"`
      emits it verbatim.

### §S4
- [ ] A sandboxed `--target-root` install writes `<root>/.agents/agents/<name>.md` for every
      generated definition and nothing outside the sandbox.
- [ ] Re-running reports every definition unchanged (hash idempotence); a hand-modified
      destination is skipped without `--force-managed` and overwritten with it.
- [ ] A pre-existing foreign file in the sandbox's `.agents/agents/` (e.g. `inbox-analyst.md`)
      is byte-identical after install and after `--force-managed`.
- [ ] `install.toml` records `agent_defs_dir` and the per-file hashes.
- [ ] A built wheel contains `generator/agents/*.md` and an installed-binary run deploys them
      (the CR-MDB-014/022 defect class: assets missing from the wheel).

### §S5
- [ ] `HARNESS_ROSTER`, `HARNESS_SKILL_DIRS` and `hooks.py` are unchanged by this CR — diff gate.
- [ ] No path under `~/.omp/` or `~/.claude/` appears anywhere in `modelb_axi/` or `generator/`
      after this CR — grep gate (`archive/` excluded).

### §S6 (integration)
- [ ] Discovery proof recorded: every emitted name listed by archimedes from the sandbox cwd.
- [ ] Dispatch proof recorded with the trust-gate answer, and `sub-agent-procedure.md` amended
      if the extension half of the boundary is absent in `-p` mode.

## Estimated size

`generator/build.py`: neutral render + `_emit_pi` + tool map (~150 lines); 5 stack TOMLs
restructured; `deploy.py` +1 asset class (mirrors `_tool_scripts()`); `config.py` +1 key;
tests: generator (amend pins + new emitter tests), installer assets (+1 class), one integration
test driving the real entry point against a temp root. Two manual runtime proofs (§S6) recorded
in the close-out note.

## Risk

- **Single third-party reader.** The contract is four frontmatter keys and one directory;
  accepted and bounded in DN §D16 (5).
- **Trust gate in `-p` mode is unmeasured** until §S6.2 runs. If extensions are skipped, VERIFY's
  read-only guarantee on Pi rests on the `tools` allowlist alone — still harness-enforced, still
  stronger than the Claude Code baseline, but the procedure doc must not overclaim.
- **Sequencing:** if this CR runs before 017 §S6 or 024, the fleet is regenerated twice. The
  dependency edges prevent it; do not reorder on the board.
- **Model omission is deliberate, not a gap.** Every agent inherits the orchestrator's model until
  the Tier-1 `CR-RND` sets route ids. Dispatch-time `model` overrides remain available per call.

## Non-goals

- No OMP anything. No Claude Code emitter. No `~/.claude` or `~/.omp` reads or writes.
- No Pi package (extensions + skills) — that is CR-MDB-029 (DN Consequences).
- No change to the sub-agent procedure, the Crucible lifecycle, or the role split.
- No Tier-1 route-id values — Roundhouse `CR-RND` territory (`contracts/switchyard-routes.md`).
- No vscode overlay definitions (DN §D4) — they enter the generated set through their own CR.
