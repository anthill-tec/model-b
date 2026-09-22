# CReq → Crucible — `cr-void` should take the CR off the queue; `queue` should carry `title` + `lifecycle.state`

**Status:** DRAFTED 2026-09-22, **NOT YET DELIVERED** — `Mainline - Crucible` is
registered but `inactive`, and Sandesh refuses an inactive recipient. Send this over the
#1336 lineage the next time they are listening. Do NOT start their session to deliver it
(standing rule: never run provider services).

---

Request: make `queue` readable — add `title` and `lifecycle.state` to the projection.

Two defects we hit this week, both caused by the same gap: the `queue` read verb returns
`cr, wave, status, planId` and nothing else.

1. TITLE DRIFT IS STRUCTURALLY INVISIBLE.
   CR-MDB-025's spec was rewritten on 2026-09-21 (dropped OMP, retargeted Pi) and its repo
   queue row changed in the same commit — but its BOARD title, posted 2026-09-18, still read
   "OMP as a first-class deploy target". The board is authoritative for queue status, so the
   authoritative surface contradicted the spec beside it for three days. Three more entries
   (018, 019, 024) had drifted the same way; we found all four only by re-posting every title
   and reading the echo.
   The only way to observe a stored title today is `cr-plan --full` — a WRITE. So the sole
   means of auditing the board is to mutate it. A read-only reader cannot check this at all.

2. A DEAD CR READS AS LIVE.
   `cr-supersede` and `cr-void` both record correctly in `lifecycle.state`, but the queue
   projection is blind to them. CR-MDB-012 is `state: VOID` and still renders
   `CR-MDB-012,"2",PENDING,null`. CR-MDB-007 has rendered PENDING since 2026-07-20 in the same
   way. A reader scanning the queue cannot distinguish "not started" from "will never happen",
   and `next` treats them alike — it surfaced an already-ruled CR to us for exactly this reason.

Ask: include `title` and `lifecycle.state` in the `queue` envelope's per-row tuple.
That single change makes board-vs-repo title parity checkable read-only by anyone at any time,
and makes a voided/superseded row self-evident without a second call per CR.

Not urgent and not a blocker — we have worked around both. Filing it because the workaround for
(1) is "issue a write to perform a read", which we would rather not build a habit on.

No patch attached: Model B maintains none of your client code, so this is a request, not a PR.

---

## Addendum 2026-09-22 — the better ask: make `cr-void` take the CR OFF the queue

The request above asks for *visibility* — surface `lifecycle.state` so a reader can see a row is
dead. On re-hitting this the same day, the sharper ask is that **the verb should do the job**
(user framing): voiding a CR should mark it **off the queue** while **retaining its DB entry**.
A void is not a deletion — the record and its reasoning must survive for audit — but a voided CR
is, by definition, not queued work, and every queue reader should get that for free rather than
having to know which ids are dead.

**Measured on CR-MDB-012, 2026-09-22, against prod `127.0.0.1:3849`:**

1. `cr-void --cr CR-MDB-012 --reason …` → `ok=True`, `brokenDependants=0`. The `--full` envelope
   shows the two fields disagreeing on one record:
   ```
   status: PENDING          ← what the queue projection reads
   lifecycle:
     state: VOID            ← what cr-void wrote
   ```
   `cr-void` writes `lifecycle.state` and does not touch `status`. **No client verb sets
   `status`** — it is server-owned — so from the client there is no way to make a voided CR stop
   rendering as pending work.
2. Re-authoring the wave without it does not help either. `wave-sequence --release 1.0.0
   --wave 2 --crs <19 ids, 012 omitted>` returned **`entries=20`** — the server re-appended the
   voided CR to the sequence it was explicitly left out of. The row is owned by the CR's own
   `wave` field, not by the sequence.
3. The only workaround available to us was to mutate the record: strip its `dependsOn`
   (25 → 0 — a void was still claiming dependencies on half the queue) and re-`cr-plan` it into
   a **wave 99 "void bucket"** with `VOID — ` leading its title, so wave 2 reads clean.

**That workaround is a lie we control, not a fix.** The record now says wave 99, which is not
true of anything; the title carries state because the projection will not. We would rather
revert it than keep it, and we will the moment the verb handles this — it is recorded here so a
future reader knows why a wave 99 exists in a two-wave release.

**Ask (preferred, supersedes the visibility ask):** `cr-void` — and `cr-supersede` — should
remove the CR from the queue projection and from wave sequencing, while keeping the row, its
reason, and its history queryable in the DB (e.g. a `voided`/`superseded` status the queue
filters out by default, with an opt-in flag to list them). If that is a larger change than it
looks, the `title` + `lifecycle.state` projection ask above remains the cheap mitigation.

This addendum is the user's own framing and will be raised by them directly; it is recorded here
so the evidence travels with the request.

Context: Model B release 1.0.0, wave 2. Raised under the #1336 lineage as the standing
client-contract channel.
