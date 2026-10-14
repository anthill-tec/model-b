# CR-MDB-059 — Orchestration rules from Crucible's wave 7

**Status:** PENDING — **SEED, not the finished spec** (filed 2026-10-10 into release 1.0.0, wave 2).
Gap analysis, the design record, the spec and its pre-review happen in order when this CR starts.
**Type:** refactor (skills, references, agent templates, `AGENTS.md`)
**Priority:** P1 — release 1.0.0, wave 2 (user ruling 2026-10-10: Crucible #1433 part B adopted into 1.0.0).
**Depends on:** none (board-authoritative: read `queue`, not this line)
**Labels:** skills, orchestration, agents, crucible, conventions
**Design reference:** Crucible #1433 §B (Mainline - Crucible, 2026-10-10: lessons from Crucible's
wave 7 and its 0.3.0 release); PRD D5; DN-model-b-language (LOCKED — cite, never fork).

## Context

Crucible runs on Model B's workflow and proposed twelve orchestration rules. Measured 2026-10-10:
B2 is CR-MDB-056 (plus CR-MDB-057 §S5, client output to a file); B3 is already in the source (#1426/#1427); B1, B5 and B6
largely match existing rules; B4, B7 and B8 conflict with current text; B9 is Crucible-specific.

## Scope (seed — the adopted rules)

1. **B1 — scope found mid-CR is a downstream patch CR,** never an edit to the running plan; only
   VERIFY findings and deviations from the CR's own approved spec are fix cycles, added with
   `cycle-add --before <verify>` so VERIFY stays last.
2. **B4 — the orchestrator reads and writes the board only through client verbs,** never the HTTP
   API; if no verb fits, say so and propose one. **Moves CR-MDB-054 item 5 here:** its raw
   `PATCH …/cycles/<id>` skip route is replaced by the 0.3.0 `cycle-skip` verb.
3. **B5 — gap analysis re-scores the CR** (`cr-plan --points`, Fibonacci 1–13); 13 is the cap and
   anything bigger is split. Every CR is scored when filed.
4. **B6 — a brief states the scope, the approved spec (the spec wins) and the definition's standard
   procedure, nothing more;** the orchestrator bolts on no extra proof steps — VERIFY and the gate
   catch drift (PRD D5).
5. **B7 — cycle labels carry no numbering** (user ruling 2026-10-10). Replaces `AGENTS.md`'s
   `C<n> <label> (§S…)` convention and every surface or gate that asserts it.
6. **B8 — the pre-merge gate runs while the last cycle is still active,** then the cycle is closed,
   so the gate's runs are filed under a cycle (user ruling 2026-10-10). Changes the documented order
   (cycle-done + verdict, then the gate).
7. **B10 — a test leak is fixed at its source,** never in the tests it breaks.
8. **B11 — release fixes go directly on the release branch,** never a separate bugfix branch, and
   reach develop at `finish`.
9. **B12 — the gate's intent line forbids stopping servers it did not start** ("do not stop any
   server you did not start"); the enforcement inside no-mistakes is no-mistakes' own.

10. **Every AXI envelope is read whole** (Crucible #1451; widens B2). No agent, orchestrators
    included, greps, heads, tails, filters, narrows with `jq`, redirects away (`>/dev/null`,
    `2>&1 …`) or summarises by pattern the output of an AXI call: the Crucible clients, `sandesh`,
    `modelb-axi`, `gh-axi` and any other. The whole envelope is read every time, because its
    `warnings[]`, `help[]` and `error` carry the guidance. A long run writes its output to a file,
    and that file's envelope is read whole. The rule reaches the skills, the agent templates and
    stack files, the orchestration references and the dispatch-brief procedure, and the scaffold's
    templates.

Not adopted: **B9** (restart the dev board after every `src/` commit) is Crucible-specific; gap
analysis decides whether a generic form ("restart any service the project itself runs") is worth a
line.

## To measure at gap analysis

- Every consumer of the changed rules: the `model-b` skill and its references (orchestration
  common/mainline/track, sub-agent procedure), `cr-authoring`, `gap-analysis`, `git-workflow`,
  `crucible`, the agent templates, `AGENTS.md` and the scaffolded `AGENTS.md` template, and the
  structural gates asserting the cycle-label shape and the gate order.
- Every surface that shows an AXI call piped, filtered or redirected (item 10), and whether a gate
  can detect the forms mechanically, as the raw-runner guard does for runner commands.
- The size: item 10 may take the CR past 13 points; split if it does.
- Boundary with CR-MDB-057 (0.3.0 doc-sync) and CR-MDB-054 (Sandesh lessons): shared files are
  sequenced, not edited twice in conflict.
