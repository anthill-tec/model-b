# CReq → Crucible — queue projection should carry `title` + `lifecycle.state`

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

Context: Model B release 1.0.0, wave 2. Raised under the #1336 lineage as the standing
client-contract channel.
