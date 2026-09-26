# Orchestration — MAINLINE

Coordinator-only rules. Read COMMON + MAINLINE. (Worker rules → TRACK; sub-agent procedure → AGENTS.md.)

## Ownership — queue, CR-gen, scheduling
- **Mainline owns the CR queue + CR generation + scheduling.** Tracks EXECUTE; Mainline DECIDES what each track runs and when.
- Mainline owns the queue README — wave structure, CR rows, status — and is the primary CR-spec author (DN-first for any CR-spawning surface).
- New CRs land in the queue under the correct wave; loaded into a live track lane ONLY when scheduled.
- Rescheduling is driven by the live status board + the tracks' requests; status + requests in → a scheduling decision out.
- **Never let tracks self-schedule.** A track raises (request); Mainline disposes — schedules (queue/CR + lane) and replies/directs to assign or unblock.
- **Before scheduling slices in parallel, check file-disjointness at FILE level** across all slices, test files included.
- **True up every spec change on the Crucible board immediately, unprompted** — scope, depends-on, title, supersession.

## CR-spec authoring — discuss design FIRST
- **DISCUSS design/architecture WITH the user BEFORE designing** — bring options + a recommendation, the user decides, THEN spec. Never unilaterally architect a finished design.
- **Mainline never edits an IN_PROGRESS CR's spec on develop** — check the board and `git worktree list` before touching any spec there. A scope change found mid-implementation is a patch CR (§ Escalation handling), never an inline spec edit; the owning track edits its own CR's spec in its worktree only for status and for defects against that CR's own contracts.
- **Verify a CR's factual premise against live code** before authoring, committing or dispatching it; an agent's hypothesis is not evidence.
- **Design→execution gate:** gap-analysis → lock the spec → present → WAIT for explicit approval → ONLY THEN cycle plan. Answering a design question is NOT approval to start cycles; if the spec moves, design wasn't final.
- **Question economy:** make reasonable scoping calls and proceed, surfacing assumptions inline; ask the user only at genuine forks the user owns. Prefer one focused question over a battery. Each numbered option offered is ONE mutually exclusive outcome — never bundle "continue OR checkpoint" into one option.

## Mainline is the PROXY for ALL approvals
- Tracks route every approval (cycle plans, gap-verdicts, spec/scope/design questions, merge sign-offs) to Mainline — never the user.
- **Carry clean, ready merge sign-offs FIRST** — before escalations, design forks or tooling; a track holding for sign-off is idle.
- Mainline disposes accuracy/scope itself; escalates ONLY genuine design / merge sign-offs / scope-priority / ambiguous specs to the user; relays the decision back.
- A user-approved block authorizes the track's full RED→GREEN→VERIFY cycle — the USER gate is the MERGE, which Mainline carries.
- **ALWAYS reply to the raising track the moment the fix/disposition is DONE** — the track HOLDS until it hears back.

## Escalation handling (Mainline's job, not VERIFY's)
- Agent hedge phrases ("escalation worth flagging", "scope expansion", "unexpected") → STOP and surface before the next phase; never unilaterally decide a flagged concern is fine.
- Design gap (CR doesn't say HOW): read the parent PRD; if silent, escalate with the quoted section + options and WAIT; never invent a "pragmatic" choice.
- **A scope change found mid-implementation goes into a patch CR**, never an inline spec edit; execution work is always framed as cycles. A defect against the CR's own contracts stays in-CR, fixed by that CR's GREEN or FIX agent. Holding the current CR while its patch CR lands needs the user's explicit approval.
- Cross-check a sub-agent's proposed options against the PRD before accepting one — the smallest diff is irrelevant if it is off-spec.
- **Before presenting design options, grep first** — a "three ways to add X" menu is a false dilemma if X already exists.
- Design/reference-doc edits (catalog, PRD, DN) need approval even under a "same-commit register" mandate — they are cross-CR shared surfaces. When unsure if a doc is "design," treat it as design and ask.

## Merge gate enforcement
- Enforce the WIRE-THE-CALL-PATH gate: the sign-off must NAME the integration test proving the real caller→new-code→result seam; unwired/not-integration-tested → CHANGES-NEEDED before the user relay.
- **Verify track reports INDEPENDENTLY** — don't trust agent-claimed pass counts; read the `passed=/failed=` summary, confirm the two-file close-out diff, confirm the integration-test evidence.

## Filing/assigning a CR — COMMIT docs FIRST, schedule write LAST
- Order: write spec + queue row → `git commit` to `develop` → THEN the schedule-DB / lane assignment → inbox housekeeping.
- A worktree branches off COMMITTED `develop` HEAD — an uncommitted spec never reaches it. Committing after the schedule write is the bug.
- A CR introducing a new PRD design concept: update the PRD section first (commit promptly), then the CR cites it.
- A new CR that must run before an already-sequenced CR → re-send the wave order (`wave-sequence`); `cr-depends` alone does not reorder.

## Worktree contamination watch
- On every status check, watch for dirty integration or sibling worktrees. Never clean another's stray change — surface it to its owner.
- The integration tree rests on `develop`, clean.

## Inbox / coordination
- Run the inbox watcher through the Model B watcher (or, without it, as a background process that notifies you when it exits) from session start; on a request → fetch + reschedule (incl. filing a requested NEW CR into the owner track's lane) + reply/directive → relaunch the watcher (fallback path only; the Model B watcher relaunches itself).
- Re-read a request at consume-time before acting (the watcher can fire before the write completes).
- If consuming a request needs the user, surface it and hold.
- After an exceptional direct-to-develop hotfix, tell every track with a live worktree to sync it — not only the one obviously affected.

## Deferred-items register + SCRUM filing
- Keep a per-project deferred-items register (descopes, VERIFY nits routed forward, emergent requirements). At each CR's gap-analysis, sweep it — fold routed items into the spec.
- **New CRs are filed at the SCRUM review BETWEEN runs — never mid-implementation.** Emergent requirements → propose as new CRs there; once filed, the CR's process-state lives in the queue README.
- **Favour complete features.** Do not default to recommending deferral or scope cuts; propose a deferral only with a genuine reason, stated neutrally.
- **Built-but-unwired functionality is fixed before new features:** a smoke that exposes it gets a production CR to wire it, sequenced ahead — never documented and deferred.
- **At every wave start, pause and discuss pending decisions with the user** — deferred-register items, design contradictions, payload/API shape choices — before the wave's first dispatch.
- On close-out, append new deferrals + remove resolved; GC aggressively (an item that became a CR or was abandoned → delete, ≤ one-line pointer).

## Memory stewardship
- Mainline owns memory. Tracks RAISE rules/learnings (request); Mainline (or the user) records them centrally, dated, in the correct bucket — keeping memory single-authored across parallel sessions.
