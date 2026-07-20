---
name: sandesh
description: "GENERIC Sandesh (MCP) usage for the Model-B agentic workflow — a Mainline coordinator + Track worker orchestrators that cannot message each other directly. Bootstrap (setup→register→background notify watcher), the watcher PRIME-DIRECTIVE (never leave it dead; fetch+relaunch same turn; exactly one), addressing (`Mainline - <Project>` / `Track N - <Project>`), verbs (request/directive/reply; to=wakes, cc=silent, all-tracks=broadcast; fetch=received/acting, reply=done), roster/liveness via sandesh_addressbook (read it, never guess; dispatch only to listening:true), and the Mainline inbox-watcher loop. Each project supplies its own project_id + address suffix in its own Sandesh note."
metadata:
  type: reference
---

Sandesh (MCP) is the addressed/threaded mailbox that lets Model-B orchestrators coordinate — a **Mainline** coordinator session + parallel **Track** worker sessions that cannot message each other directly. **Generic mechanics live here; each project supplies its own `project_id` + address suffix** in its project Sandesh note.

## Two channels, one boundary
The MCP server carries the VERBS (send/reply/fetch/inbox/register/addressbook). The **WAKE is out-of-band** — an MCP server cannot re-invoke a sleeping agent. The standalone `sandesh notify` watcher exits when To-addressed mail arrives → the host re-invokes the session → it `sandesh_fetch`es → **relaunches the watcher**.

## Bootstrap — at SESSION START, every session (do NOT defer to first dispatch)
1. `sandesh_setup(project_id="<Project>")` (idempotent)
2. `sandesh_register(addr="<your address>")`
3. Launch the wake watcher **in the background** (`run_in_background`): `sandesh notify --to "<your address>" --project <Project>`. NEVER run it inline — it blocks.
4. Confirm `sandesh_addressbook` shows your address `listening:true`.

The CLI REQUIRES `--project <Project>`; a bare `sandesh notify --to …` exits 1 and silently never listens (`listening:false`). Every Sandesh MCP call must pass `project_id` explicitly (the server env may default it wrong, which mismatches the addresses).

## 🚨 PRIME DIRECTIVE — never leave your watcher dead during a session
The instant the watcher fires/exits (you get the task-notification), `sandesh_fetch` **AND relaunch in the SAME turn**. Keep **exactly ONE** watcher per address (a duplicate exits non-zero on a lock conflict — benign, means the prior is alive). Whenever you find it stopped or are unsure: `sandesh_fetch` FIRST (drain gap mail), THEN relaunch — a fresh watcher only fires on mail arriving AFTER it starts, so relaunching blind can MISS gap messages. At any uncertainty, `sandesh_addressbook` to confirm your own `listening:true`.

## Addressing + verbs
- Addresses: `Mainline - <Project>` / `Track N - <Project>`.
- `kind="request"` — a track raises a question/blocker/approval to Mainline. `kind="directive"` — Mainline assigns/unblocks a track. `sandesh_reply` — answers a request; **reply = the requested work is DONE** ("you're unblocked, proceed").
- **`to=` WAKES** the recipient; **`cc=` is SILENT** (awareness only, no wake — saves turns); `to=["all-tracks"]` broadcasts to every active address minus the sender.
- Lifecycle has no status field: `fetch` = received/being-acted-on (the waiting sender can observe read-state); `reply` = done.

## Roster / liveness — READ it, never guess
`sandesh_addressbook(project_id="<Project>")` lists every registered address with `active` + `listening`. **How many tracks exist + whether they're alive comes from the addressbook, never assumption** ("N tracks" is not a given). Dispatch a `to=` directive ONLY to a `listening:true` address; if a needed track isn't alive, surface it (the human must launch that session) — don't dispatch into the void.

## Roles
- **Track**: raises `kind=request` to Mainline for anything needing a decision; then **HOLDS** until Mainline replies/directs — idle on the watcher, **zero LLM turns, never self-poll**. Signals cycle completion with `sandesh_reply` threaded under the assignment message.
- **Mainline**: runs its own inbox watcher (`sandesh notify --to "Mainline - <Project>"`); on a To-addressed request → re-invoked → fetch + decide/schedule + reply/directive → **relaunch the watcher**. **ALWAYS reply the moment a disposition is done** — the raising track HOLDS until it hears back. If consuming a request needs the human, surface it and hold (don't busy-relaunch).
