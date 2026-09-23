# CR-MDB-030 — Pi hook runtime: make the only target's hooks actually load, receive the payload, match, and fail closed

**Status:** PENDING (filed 2026-09-21 from `audits/2026-09-21-codebase-review-modelb_axi.md` §A
and `-assets.md` §1)
**Type:** bugfix
**Priority:** P0 — in release 1.0.0, wave 2, **ahead of CR-MDB-025 §S6 and CR-MDB-029**. Every
"HARD-ENFORCED" guarantee the published skills make (`sub-agent-procedure.md:10`: a hook denies
out-of-worktree writes) is fiction on Pi today: no emitted hook loads, none receives its payload,
and none would match the tools Model B's agents actually call if it did.
**Depends on:** — (CR-MDB-015 is the shipped baseline being corrected)
**Labels:** hooks, pi, security, bugfix, runtime
**Phase:** Wave 5 (repo queue) · release 1.0.0 wave 2 (Crucible board)
**Design reference:** the Pi that runs — `@earendil-works/pi-coding-agent` **0.87.1**
(`docs/extensions.md:22` default-export factory; `dist/core/extensions/loader.js:414-416` a module
whose default export is not a function is dropped; `dist/core/exec.d.ts` `ExecOptions =
{signal?, timeout?, cwd?}` — no `stdin`; `dist/core/extensions/types.d.ts` `ToolCallEvent` is a
union of the built-in tools plus `CustomToolCallEvent {toolName: string; input: Record<string,
unknown>}`, `ToolCallEventResult {block?, reason?}`, events include `session_before_compact`;
`docs/extensions.md:201` a failing `tool_call` handler blocks the tool) · `hooks-src/schema.md`
(neutral schema v1) · PRD D10.7 and DN §D17 (hooks and agents are wired per project) · DN §D18
(shared assets name capabilities, not a harness's own tools) · DN §D5's "silent
ineffectiveness" rule

## Context — measured against the installed harness, not inferred

Three independent defects, each sufficient to make every hook a no-op:

| # | Where | What the code does | What Pi does |
|---|---|---|---|
| 1 | `hooks._emit_pi` | writes `pi.on("<event>", async (payload) => {…})` at module top level | the loader drops a module whose default export is not a function; if evaluated, `pi` is undefined |
| 2 | `hooks._emit_pi`'s shim | `pi.exec(script, [], { stdin: JSON.stringify(payload) })` | `ExecOptions` has no `stdin`; the protocol script's `json.load(sys.stdin)` sees EOF and allows |
| 3 | 6 of 7 `hooks-src/scripts/*` | test `payload["tool_name"]` against Claude Code names (`Bash`, `Write`, `Edit`, `NotebookEdit`, `TaskCreate`) and read `tool_input["file_path"]` | Pi events carry lowercase `toolName` and `input.path` — every guard's predicate is false, so it allows |

And five that make a fix incomplete if left:

| # | Where | Defect |
|---|---|---|
| 4 | `hooks._HONORS_FAIL_CLOSED` | includes `pi` because "the shim blocks on spawn failure" — but `execCommand` never rejects; a missing script resolves `{code: 1}` → allowed. `closed` is not honoured. |
| 5 | `hooks._emit_pi` | ignores `matcher`; every hook fires on every `tool_call`. Scaffold matchers are Claude Code vocabulary (`TaskCreate`, `Bash`, `Write\|Edit\|NotebookEdit`). |
| 6 | `hooks.py` event map | declares `pre-compact` has "NO documented pi counterpart" — Pi has `session_before_compact`. |
| 7 | `scaffold.py` `.gitignore` + hook instances | ignores `.pi/` wholesale, so no worktree checkout carries the project's extensions (or, since DN §D17, its agents); every `block-*` guard is emitted `fail_direction: open` for a Claude Code refusal-rule reason §D14 retired. |
| 8 | the tools Model B's agents use | Model B's agents shell through **`ctx_shell`** (measured 2026-09-22: the only shell a dispatched child has) and edit through **`ctx_patch`** / **`ctx_edit`**. Pi fires `tool_call` for them as `CustomToolCallEvent`s with their own names. A guard matching only `bash` or `write\|edit` never sees the calls the agents actually make. |

**Measured 2026-09-23 — project hooks reach dispatched agents.** A throwaway extension placed in
this repo's `.pi/extensions/` and one `@gotgenes/pi-subagents` dispatch showed the child running
the extension's factory, its `session_start`, and a `tool_call` for each built-in tool it used
(`ls` with input `{path}`, `read` with `{limit, offset, path}`), all in the parent's working
directory. The dispatcher runs children in-process with the parent's extensions, so the `pi -p`
project-trust caveat of the retired `pi-archimedes` design (DN §D16 consequence 4) does not apply
to dispatch.

## Scope

### §S1 — Default-export factory
`_emit_pi` emits `export default function (pi) { pi.on("<event>", async (event, ctx) => { … }); }`
with the 0.87.1 handler signature. The script path and every interpolated string go through
`json.dumps`, so no raw `"` reaches a TypeScript literal.

### §S2 — Payload transport: a piped child process
The shim spawns the protocol script with `node:child_process` (extensions run unsandboxed) with
`stdin` piped, writes the neutral payload as JSON, closes stdin, and collects exit code, stdout
and whether it was killed. The instance's `timeout` is enforced by killing the child; an instance
that declares none gets **60 seconds**, so a hung script can never stall a tool call
indefinitely. The seven
scripts' stdin/exit protocol is unchanged. `pi.exec` is not used.

### §S3 — Payload contract: neutral in, harness-native out
`hooks-src/schema.md` declares the **neutral payload** every script reads: `tool_name` (a neutral
tool class), `tool_input` (`command` for a shell class; `path` plus `paths`, every path the call
targets, for a file class), `cwd`, `session_id`, and `harness_tool` (the harness's own tool name,
for audit only — no script branches on it). The Pi shim maps the event into that shape:

| Pi `toolName` | neutral `tool_name` | `tool_input` from |
|---|---|---|
| `bash`, `ctx_shell` | `bash` | `input.command` |
| `ctx_execute` with a shell language (`shell`, `bash`, `sh`) | `bash` | `input.code` as `command` |
| `write` | `write` | `input.path` |
| `edit`, `ctx_edit`, `ctx_patch` | `edit` | `input.path`, and every per-operation `path` a `ctx_patch` call carries, into `paths` |
| `read`, `grep`, `find`, `ls` | same name | `input.path` |
| any other tool | passed through under its own name | `input` unchanged |

An event that is not a tool call (`session-start`, `pre-compact`, …) carries the same keys, with
`tool_name` and `harness_tool` null and `tool_input` `{}`; a matcher does not filter such events.

The six remaining scripts are ported to the neutral names (`Bash`→`bash`, `Write|Edit|NotebookEdit`
→`write|edit`, `file_path`→`path`/`paths`). A file guard checks every entry of `paths`.

**Known limit, stated not hidden:** the write boundary governs the file tools. A write performed
by a shell command (`cat > file`, `rm`) is not path-gated by a hook predicate — the same limit the
Claude Code `Bash` tool had. `sub-agent-procedure.md` is not to claim otherwise (CR-MDB-031 owns
that text).

### §S4 — Matcher honoured, on the neutral name
`schema.md`'s `matcher` is a pattern over the **neutral** `tool_name` (`bash`, `write|edit`, …).
`_emit_pi` compiles it into a guard that returns before spawning when the mapped name does not
match, so `write|edit` also covers `ctx_patch` and `ctx_edit`, and `bash` covers `ctx_shell`.
`scaffold._hook_instances` uses the neutral vocabulary.

**Every emitter translates the neutral matcher into its own harness's tool names** — the neutral
name is the schema's, never a harness's. `_emit_pi` does it through §S3's table. `_emit_claude_code`
writes Claude Code's names into `settings.json`: `bash`→`Bash`, `write`→`Write`,
`edit`→`Edit|MultiEdit|NotebookEdit`, `read`→`Read`, `grep`→`Grep`, `find`→`Glob`, `ls`→`LS`, an
alternation translated per member; a name with no Claude Code equivalent passes through unchanged.
(Claude Code is retiring under CR-MDB-031, but until it is removed its emitted wiring must work.)

### §S5 — Fail-closed that is real
For `fail_direction: closed`, the shim blocks with a reason on any outcome other than exit 0
(allow) or exit 2 with a parseable `{"decision":"block"}` (block): spawn error, any other exit
code, kill on timeout, unparseable output. For `open`, those outcomes allow. `_HONORS_FAIL_CLOSED`
keeps `pi`, proven by §S8. `pre-compact` maps to `session_before_compact`, and the "no documented
pi counterpart" note is deleted.

### §S6 — Hooks stay per project, and worktrees carry them
Hooks are wired per project, as PRD D10.7 and DN §D17 settle: the protocol scripts ship once, and
each project's `.pi/extensions/` is compiled by `init`. The Pi package (CR-MDB-029) does not ship
hook extensions — this answers CR-029 §S0. The scaffold's `.gitignore` stops ignoring `.pi/`
wholesale, so `.pi/extensions/` and `.pi/agents/` are tracked and every `git worktree add`
checks them out. Scaffold `block-*` guards flip to `fail_direction: closed`, and the obsolete
Claude-refusal rationale comment is deleted.

### §S7 — Retire `block-bad-cycle-task-name`
The hook blocks Claude Code `TaskCreate` calls whose subject breaks the cycle-todo naming rule.
Model B no longer keeps a local todo list (the Crucible board is the task list), and DN §D18 bars
a shared asset from naming a harness's todo tool, so the practice it polices is gone. It is
deleted, not retargeted: the script, its `schema.md` entry, its scaffold instance and its tests.
The installer's hook-script set becomes six. Closed specs (CR-MDB-015) and `audits/` are history
and are not edited.

### §S8 — Runtime proof through Pi's own loader
A test imports each emitted `.pi/extensions/*.ts` with the **`jiti` package** the installed Pi
depends on (`createJiti(…).import(path, { default: true })`, exactly as Pi's loader calls it) —
not Pi's own `jiti-loader.js` module, which keeps Node's event loop alive. The harness ends in an
explicit `process.exit`, and every invocation of it carries a timeout, so a hang fails the test
instead of stalling the run. It invokes the factory with a recording `pi`
object, and drives the registered handlers with events shaped as 0.87.1 defines them. No model
is involved, so it is deterministic. The test SKIPS, naming what is missing, when `pi`, its jiti
or `node` is absent; it never passes without running. Whether project hooks reach dispatched
agents is not re-tested per run: it was measured on 2026-09-23 (Context).

## Acceptance criteria

- [ ] Every emitted `.pi/extensions/*.ts` default-exports a function that Pi's jiti imports with
      `{ default: true }`, and calling it registers a handler for the instance's event.
- [ ] A hook script receives exactly the neutral payload the shim built, for each row of §S3's
      mapping table — asserted by a script that echoes its stdin back, one subtest per row.
- [ ] Zero `"Bash"`, `"Write"`, `"Edit"`, `"NotebookEdit"`, `"TaskCreate"`, `"MultiEdit"` and
      `file_path` in `hooks-src/scripts/*` — grep gate; `schema.md` documents the neutral payload
      and §S3's mapping.
- [ ] `block-write-outside-worktree` blocks a call outside the worktree root through each of
      `write`, `edit`, `ctx_edit` and `ctx_patch` (including a `ctx_patch` whose second operation
      targets the outside path), and allows a `read` there — through the emitted shim.
- [ ] `block-direct-cargo-test` blocks `cargo test` through `bash`, `ctx_shell` and a shell
      `ctx_execute`; `block-direct-mvn-test` blocks `mvn test` through the same three.
- [ ] A `closed` hook blocks, with a reason, when its script is missing, exits 1, exceeds its
      timeout (the declared one, or 60 s when none is declared), or prints unparseable output; an `open` hook allows in each of those four cases —
      asserted through the emitted shim, eight subtests.
- [ ] `matcher` filters on the neutral name: a `write|edit` hook does not spawn for `bash` or
      `ctx_shell`, and does spawn for `ctx_patch` — asserted by a counting fake script.
- [ ] `.claude/settings.json` carries Claude Code's own tool names for every neutral matcher —
      `bash`→`Bash`, `write|edit`→`Write|Edit|MultiEdit|NotebookEdit`, and each other class in
      §S4's list — never the neutral name.
- [ ] `session_before_compact` is emitted for `pre-compact`; no "no documented pi counterpart"
      note remains.
- [ ] A fresh `git worktree add` of a scaffolded project contains its `.pi/extensions/` and
      `.pi/agents/`; the scaffold `.gitignore` has no line ignoring `.pi/` as a whole.
- [ ] Every scaffold `block-*` instance is `closed`; the Claude-refusal comment is gone.
- [ ] `block-bad-cycle-task-name` exists nowhere under `hooks-src/`, `modelb_axi/` or `tests/`,
      and a sandbox install deploys six hook scripts.
- [ ] The existing tests that assert Claude Code matcher vocabulary, `open` guards or the retired
      hook are migrated to this contract, and the migrated set is listed by test id in the RED
      report.
- [ ] §S8's loader test runs on a machine with Pi installed and SKIPS, naming what is missing, on
      one without.

## Estimated size

`hooks._emit_pi` rewrite (~150 lines of emitted TypeScript template), the mapping table, six
scripts (mechanical rename), one retirement, `schema.md`, `scaffold.py` (gitignore, guards,
matchers), and tests including the loader harness. Medium; security-class.

## Risk

- Pi extension API drift: the contract is measured at 0.87.1; §S8's loader test is the early
  warning.
- A tool Model B's agents start using that §S3's table does not map passes through unmatched —
  a guard silently stops applying. The table is the one place to extend.

## Non-goals

- No new hooks. No change to the neutral schema's event set beyond the `pre-compact` mapping.
- No gating of shell-command writes by path (§S3's known limit).
- **No workload-identity stamping through hooks** (CR-SY-003's routing `user` field): the
  six-field schema cannot express it, and CR-025 §S0 carries the question.
- No retirement of non-Pi emitters — CR-MDB-031.
- No package shipping — CR-MDB-029.
- No wiring of this repository's own `.pi/extensions/` — the scaffold's output is the product;
  dog-fooding hooks in `model-b` is a separate decision.
