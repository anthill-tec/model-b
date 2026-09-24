# CR-MDB-026 — The wake watcher stays alive: the Model B watcher first, and the six exits Sandesh reports

**Status:** PENDING (filed 2026-09-16; rewritten at its gap-analysis 2026-09-24 — earlier text is git
history and is not to be consulted for contracts)
**Type:** bugfix
**Priority:** P1 — in release 1.0.0, wave 2. A dead watcher silently stops waking a session, and a
track that raised a blocker then holds forever — the failure the prime directive exists to prevent.
**Depends on:** — (CR-MDB-029, the Model B watcher, has shipped)
**Labels:** skills, orchestration, sandesh, bugfix
**Design reference:** CR-MDB-029 §Context (Sandesh 0.3.5's exit contract, measured) and §S2 (the
Model B watcher's behaviour) · `sandesh notify --help` §"Why the listener stopped" (Sandesh's own
statement of each reason) · DN §D18 (shared skills name capabilities and CLIs, never harness tools)
· project memory `sandesh-mcp-only-boundary`

## Context — measured

- **Every skill that launches the watcher says "in the background (`run_in_background`)"**:
  `skills-src/bootstrap/SKILL.md` Step 1 and Guardrails, `skills-src/model-b/references/sandesh.md`
  §Bootstrap step 3, and the inbox-watcher line in `orchestration-mainline.md`. `shutdown`'s final
  step stops it with `TaskStop` or a targeted `pkill`. Those are one harness's tool names, and a
  background job can be killed by a harness deadline shorter than the watcher's own timeout
  (observed once at 300 s against Sandesh's 14400 s default).
- **The Model B watcher (CR-MDB-029)** supervises `sandesh notify`, stays running at all times, and
  handles every exit itself: on mail it wakes the session once and relaunches; the same unread mail
  never wakes it twice; a timeout relaunches silently; an error or a terminal exit is surfaced and
  never relaunched. With it, a woken session **only fetches** — the watcher relaunches itself.
- **Without the Model B watcher** (the package is recommended, not required — CR-MDB-036 §S1), the
  session runs `sandesh notify` through its harness's facility for long-running background
  processes that notify it when they exit, and responds to each exit itself.
- **Sandesh 0.3.5 names the reason in its last log line** (`sandesh notify --help` lists them):

  | Reason (last log line) | Exit | The session's response without the Model B watcher |
  |---|---|---|
  | mail arrived (`✉ … unread`) | `0` | fetch, then relaunch |
  | timed out | `2` | relaunch; nothing to fetch |
  | error (usage or configuration) | `1` | fix the command, then relaunch |
  | tombstoned (project retired) | `3` | do **not** relaunch; report it |
  | evicted (another notifier took the address) | `4` | do **not** relaunch; report it |
  | already live (dedup) | `5` | do **not** relaunch — a watcher already holds the address |
  | killed by a signal | `128+n` | relaunch, unless you stopped it yourself |

  The skills today know three exits and read "the process is gone" as mail.

## Scope

### §S1 — `sandesh.md`: the launch mechanism and the exit table
§Bootstrap step 3 names the **Model B watcher** as the way to start the notifier, and states that
with it a woken session only fetches. It names, as the fallback when the Model B watcher is not
installed, running `sandesh notify --to "<your address>" --project <Project>` through the harness's
long-running background-process facility that notifies on exit — never inline (it blocks), and
never as a job with a deadline shorter than the watcher's timeout.

The PRIME DIRECTIVE section carries the table above: each reason, how to recognise it from the last
log line, and the response. It states that `sandesh notify --help` is Sandesh's authority for the
reasons, and that fetching precedes relaunching whenever mail may have arrived.

### §S2 — `bootstrap` Step 1 and Guardrails
Same mechanism, phrased for the bootstrap flow. The existing rules stay: check the addressbook first
and start a watcher only if the address is not `listening:true`; exactly one per address; never
inline; re-probe `listening:true` after starting.

### §S3 — `shutdown`'s final step
The notifier is stopped through the Model B watcher's stop, or, on the fallback path, through the
harness facility that runs it (stopping your own process only) — with the targeted kill of your own
address's `sandesh notify` as the last resort. The prohibition on machine-wide kills, and the
"kill it last, never relaunch" lifecycle, are unchanged.

### §S4 — The other watcher lines agree
`orchestration-mainline.md`'s inbox-watcher line and `orchestration-common.md`'s bracket lines name
the same mechanism as §S1, and no longer name a single harness's background-job tool.

### §S5 — Capabilities, not harness tools (DN §D18)
The rewritten text names the capability — "the Model B watcher", "a background process that
notifies you when it exits", "stop your watcher" — and the `sandesh` CLI where precision matters. It
names no harness tool: not `run_in_background`, `TaskStop`, `process`, or the Model B watcher's own
tool name. Fetching, where these lines mention it, uses the CLI form
(`sandesh fetch --project <Project> --to '<your address>'`).

## Acceptance criteria

### §S1
- [ ] `sandesh.md` §Bootstrap names the Model B watcher first, states that with it a woken session
      only fetches, and names the background-process fallback with its "never inline, no shorter
      deadline" conditions.
- [ ] `sandesh.md`'s PRIME DIRECTIVE names all seven rows of the table — each reason with its exit
      and its response — and cites `sandesh notify --help` as the authority for the reasons.
- [ ] No text under `skills-src/` tells a session to relaunch after tombstoned, evicted or already
      live, or treats any non-zero exit as proof that mail arrived.

### §S2
- [ ] `bootstrap` Step 1 and Guardrails name the §S1 mechanism; the addressbook-first check,
      exactly-one-per-address, never-inline and `listening:true` re-probe rules remain.

### §S3
- [ ] `shutdown`'s final step stops the watcher through the Model B watcher, then the harness
      facility, then a targeted kill of the session's own address, and still forbids machine-wide
      kills; the kill-last / no-relaunch sentences are unchanged.

### §S4 / §S5
- [ ] A gate over `bootstrap/SKILL.md`, `shutdown/SKILL.md`, `model-b/references/sandesh.md`,
      `orchestration-common.md` and `orchestration-mainline.md` finds none of `run_in_background`,
      `TaskStop` or `sandesh_watcher`, with a detector fixture proving it bites. (The sub-agent
      dispatch uses of `run_in_background` in `orchestration-track.md` and `crucible/SKILL.md` are
      CR-MDB-031's and outside this gate.)
- [ ] No skill instructs any direct read or write of the Sandesh data directory.
- [ ] Section headings and anchors that existing tests pin are unchanged; tests asserting the old
      launch wording are migrated and listed by id.

## Risk

- The five files move together in one change: a half-updated set gives contradictory instructions.
- The fetch-before-relaunch ordering and the exactly-one-watcher rule are load-bearing; this CR
  changes the mechanism and the exit reading, never the discipline.

## Non-goals

- No change to Sandesh (not Model B's code), the wake protocol, addressing, or the verbs.
- No general conversion of the skills' MCP verb references to the CLI (CR-MDB-031); only the lines
  this CR rewrites use the CLI fetch form.
- No change to the Model B watcher (CR-MDB-029).
