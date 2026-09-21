# CR-MDB-030 — Pi hook runtime: make the only target's hooks actually load, receive the payload, match, and fail closed

**Status:** PENDING (filed 2026-09-21 from `audits/2026-09-21-codebase-review-modelb_axi.md` §A
and `-assets.md` §1)
**Type:** bugfix
**Priority:** P0 — in release 1.0.0, wave 2, **ahead of CR-MDB-025 §S6 and CR-MDB-029**. Every
"HARD-ENFORCED" guarantee the published skills make (`sub-agent-procedure.md:10`: a `PreToolUse`
hook denies out-of-worktree writes) is fiction on Pi today: no emitted hook loads, none receives
its payload, and none would match a Pi tool name if it did. The write boundary, the cargo/mvn
test guards and the ambient board are all silently absent on the only target.
**Depends on:** — (CR-MDB-019 is re-scoped by this CR, see §S7; CR-MDB-015 is the shipped baseline
being corrected)
**Labels:** hooks, pi, security, bugfix, runtime
**Phase:** Wave 5 (repo queue) · release 1.0.0 wave 2 (Crucible board)
**Design reference:** installed Pi 0.86.1 — `@mariozechner/pi-coding-agent/docs/extensions.md`
(`:63` default-export factory; `:408-413` `session_before_compact`), `dist/core/exec.d.ts`
(`ExecOptions = {signal?, timeout?, cwd?}` — no `stdin`; `execCommand` never rejects, spawn
failure resolves `{code: 1}`), `dist/core/extensions/loader.js:279-281` (a module without a
default-export function is dropped), `dist/core/types.d.ts:586-596` (`ToolCallEvent` carries
`toolName` and `input`) · `hooks-src/schema.md` (neutral schema v1) · DN §D5's "silent
ineffectiveness" rule · DN §D16 consequence 4 (the `-p` trust caveat)

## Context — measured against the installed harness, not inferred

Three independent defects, each sufficient to make every hook a no-op:

| # | Where | What the code does | What Pi does |
|---|---|---|---|
| 1 | `hooks.py:308-312` `_emit_pi` | writes `pi.on("<event>", async (payload) => {…})` at module top level | the loader `jiti.import(path, {default:true})` → `typeof factory !== "function" ? undefined` — module dropped; if evaluated, `ReferenceError: pi is not defined` |
| 2 | `hooks.py:215-216` | `pi.exec(script, [], { stdin: JSON.stringify(payload) })` | `ExecOptions` has no `stdin`; child spawns with `stdio: ["ignore", …]`; the protocol script's `json.load(sys.stdin)` sees EOF → allows |
| 3 | 6 of 7 `hooks-src/scripts/*` | `payload.get("tool_name") in {"Bash","Write","Edit","NotebookEdit","TaskCreate"}`, `tool_input["file_path"]` (35 occurrences) | events carry `toolName` ∈ `{bash, read, write, edit, grep, find, ls}` and `input` with `path` — every guard's predicate is false → allows |

And four that make the fix incomplete if left:

| # | Where | Defect |
|---|---|---|
| 4 | `hooks.py:135`, `:216-220` | `_HONORS_FAIL_CLOSED` includes `pi` because "the shim blocks on spawn failure" — but `execCommand` never rejects; a missing script resolves `{code: 1}` → `return {}` → **allowed**. `closed` is not honoured. |
| 5 | `hooks.py:287-323` | `_emit_pi` ignores `matcher`; every hook fires on every `tool_call` and relies on the (Claude-named) script predicate. Scaffold matchers are `TaskCreate` / `Bash` / `Write\|Edit\|NotebookEdit` — Claude vocabulary; `TaskCreate` has no Pi equivalent. |
| 6 | `hooks.py:259-266` | `pre-compact` declared "NO documented pi counterpart" — Pi has `session_before_compact`. |
| 7 | `scaffold.py:164-178` + `:320-336` | The scaffold `.gitignore`s `.pi/`, so **no worktree ever has the extensions** (`git worktree add` checks out tracked files only); and every `block-*` guard is emitted `fail_direction: open` for a Claude Code refusal-rule reason §D14 retired. |

CR-MDB-015 shipped this with a VERIFY that inspected emitted text, not a loader. CR-MDB-019's
VERIFY-derived fixes target the opencode emitter — a non-target — while excluding `_emit_pi`
("No change to the pi emitter"). This CR is where the Pi emitter gets a runtime proof.

## Scope

### §S1 — Default-export factory
`_emit_pi` emits `export default function (pi) { pi.on("<event>", async (event, ctx) => { … }); }`
with the Pi event/handler signatures as documented at 0.86.1. Script path and every interpolated
string go through `json.dumps` (no raw `"` in a TS literal).

### §S2 — Payload transport
The payload reaches the script. Preferred: spawn via `node:child_process` inside the extension
(extensions are unsandboxed) with `stdin` piped, so the seven scripts' stdin/exit protocol is
unchanged. Alternative if rejected at gap-analysis: temp-file handoff via `pi.exec` with the path
as `argv[1]`, and the scripts accept either. One mechanism, chosen and recorded.

### §S3 — Payload field contract: neutral in, harness-native out
`hooks-src/schema.md` declares the **neutral payload** the scripts read: `tool_name` (lowercase
Pi vocabulary: `bash`, `write`, `edit`, `read`, `grep`, `find`, `ls`), `tool_input` with
`command` / `path`, `cwd`, `session_id`. The Pi shim maps `event.toolName`/`event.input` into
that shape before spawning. The seven scripts are ported to the neutral names (`Bash`→`bash`,
`Write|Edit|NotebookEdit`→`write|edit`, `file_path`→`path`). `TaskCreate` has no Pi tool: the
`block-bad-cycle-task-name` hook is retargeted to the Pi `todo` tool's input shape if archimedes
exposes it, else retired with a recorded reason.

### §S4 — Matcher honoured
`schema.md`'s `matcher` becomes a harness-neutral tool-name pattern (`bash`, `write|edit`, …);
`_emit_pi` compiles it into an `if (!/^(write|edit)$/.test(event.toolName)) return;` guard.
`scaffold._hook_instances` re-vocabularies its matchers accordingly.

### §S5 — Fail-closed that is real
For `fail_direction: closed`, the shim treats any outcome other than `code 0` (allow) or `code 2`
+ a parseable `{"decision":"block"}` (block) as a failure and **blocks with a reason**: spawn
error, `code 1`, `killed`, timeout, unparseable output. `_HONORS_FAIL_CLOSED` keeps `pi` only
once this is proven by a test that points a `closed` hook at a non-existent script and asserts
the block. `session_before_compact` is mapped; the false `pre-compact` degrade note is deleted.

### §S6 — Worktrees get the extensions
Either the scaffold tracks `.pi/extensions/` (ignore only `.pi/` state: sessions, cache), or
`worktree-flow.py` recompiles wiring into each new worktree. Decided at gap-analysis together
with CR-029 §S0 (package-shipped vs per-project hooks). Scaffold guards flip to
`fail_direction: closed` and the obsolete Claude-refusal rationale comment is deleted.

### §S7 — Re-scope CR-MDB-019
019 §S3 ("honestly-async opencode emitter") is **struck**: opencode is not a target and the
emitter is retired by CR-MDB-031. 019 keeps §S1 (status-contract re-pin) and §S2 (arduino
marker). Recorded in 019's spec by this CR's filing.

### §S8 — Runtime proof
A test spawns a real `pi -p` (skipped when `pi` is absent — never silently green on a machine
that has it) in a temp project with the emitted `.pi/extensions/`, invokes a write outside the
worktree root, and asserts the block. This is also DN §D16 consequence 4's trust-gate
measurement: the test records whether `-p` loaded project extensions at all.

## Acceptance criteria

- [ ] Every emitted `.pi/extensions/*.ts` default-exports a function; a loader-level test
      (jiti/tsx import, or `pi -p` when present) confirms registration.
- [ ] A hook script receives the exact JSON payload the shim built — asserted by a script that
      echoes it back.
- [ ] Zero `"Bash"`/`"Write"`/`"Edit"`/`"NotebookEdit"`/`"TaskCreate"`/`file_path` in
      `hooks-src/scripts/*` — grep gate; `schema.md` documents the neutral vocabulary.
- [ ] A `write` outside the worktree root is blocked by `block-write-outside-worktree` on Pi
      (§S8), and a `read` is not.
- [ ] A `closed` hook whose script is missing **blocks**; an `open` one allows — both asserted
      through the emitted shim, not by reading its text.
- [ ] `matcher` filters: a `write|edit` hook does not spawn on `bash` — asserted by a counting
      fake script.
- [ ] `session_before_compact` is emitted for `pre-compact`; no "declared gap" note remains.
- [ ] A fresh `git worktree add` of a scaffolded project contains `.pi/extensions/` (or the
      recompile path runs) — asserted.
- [ ] Scaffold `block-*` guards are `closed`; the Claude-refusal comment is gone.
- [ ] CR-019's spec no longer contains §S3.
- [ ] 015's existing hook tests still pass or are amended with the amendment listed by id.

## Estimated size

`hooks.py` `_emit_pi` rewrite (~120 lines), 7 scripts (mechanical rename + one retarget),
`schema.md`, `scaffold.py` (gitignore + guards + matchers), tests incl. one real-`pi` spawn.
Medium; security-class.

## Risk

- Pi extension API drift: the contract is measured at 0.86.1; the runtime test in §S8 is the
  early-warning.
- If `-p` mode skips project trust, §S8 records it and the extension half of the write boundary
  is absent in dispatched sub-agents — then the `tools` allowlist (DN §D16) is the only boundary
  and `sub-agent-procedure.md` must be amended by CR-031 to say so. Either way the answer is
  measured here, not assumed.
- `block-bad-cycle-task-name` may have no Pi home; retirement with reason is an accepted outcome.

## Non-goals

- No new hooks. No change to the neutral schema's *event* set beyond the `pre-compact` mapping.
- No retirement of non-Pi emitters here — CR-MDB-031.
- No package shipping — CR-MDB-029.
