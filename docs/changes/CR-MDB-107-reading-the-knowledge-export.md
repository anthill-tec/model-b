# CR-MDB-107 — How the knowledge-store export is read

**Status:** PENDING — **SEED, not the finished spec** (filed 2026-11-14 by the user's ruling, answering
Crucible #1617). Gap analysis and the spec happen in order when this CR starts. Pre-review: due (it changes
`contracts/lean-ctx.md`, and the user's ruling was needed).
**Type:** fix (the knowledge-load rules)
**Priority:** P2 — release 1.0.0, wave 2 (board-authoritative: read `queue`).
**Depends on:** none.
**Labels:** knowledge-store, lean-ctx, bootstrap, shutdown
**Design reference:** PRD-model-b-rationalization D5 (2026-10-29: one listing holds the category; restored
facts re-confirmed); `orchestration-common` § Memory; `contracts/lean-ctx.md` § Knowledge store and its
request (g) (filed upstream as yvgude/lean-ctx#2248, 2026-11-14); CR-MDB-088 (execution knowledge always in
the store).

## Context

The rule stands: a category is kept within what one listing of it shows (PRD D5), and the store's export is
the fallback when a listing shows fewer facts than the category holds. Mainline or Solo then reconciles the
category down to the limit.

Crucible's Mainline hit the fallback at its 2026-11-14 bootstrap (#1617): its `crucible-workflow` category
held 41 live facts and listed as `showing 10/41`. The rules say to "read the rest from the store's complete
export" but not how to read it. On lean-ctx 3.11.4:

- **The export holds history, not the live set.** It wrote 84 rows in that category for 41 keys: every
  superseded revision is its own row under the same key. Crucible de-duplicated by key in a script of its own.
- **Nothing gives the low-confidence view.** Bootstrap Step 0.6's "the restored facts are those the listing
  (or the export) shows below 30% confidence" has to be computed from the export's rows.
- **A restore by category reports matches, not a count.** "All 13 matching archived item(s) are already live"
  gives nothing to reconcile against the category's size.

The user ruled (2026-11-14): keep the rule, state how the export is read, and file lean-ctx request (g) (a
per-call or per-project listing limit, or paging) upstream. Model B's `modelb-workflow` category holds exactly
10 facts, so its own loads have not needed the fallback.

## Scope (seed)

1. **The export's live set is stated:** one current fact per key in the category, the revision whose
   `valid_until` is empty; superseded rows are history and are never loaded or reconciled.
2. **The restored facts are read from that live set** by their confidence (below 30%), where the listing does
   not show them.
3. **The surfaces that state the fallback say both:** `orchestration-common` § Memory ("One listing holds the
   category"), the `bootstrap` skill's Step 0.6 (items 3 and 4), and `contracts/lean-ctx.md`'s export verb
   and pitfalls; the shutdown skill wherever it names the load.
4. **The contract's request (g) reads as filed:** its `Status: to file.` becomes filed as yvgude/lean-ctx#2248
   (2026-11-14). `tests/test_contracts.py` pins "to file" for (g) (`LeanCtxContractRefreshTest`, the `(g)`
   pin ~L99), so the status moves here rather than in a docs-only commit.
5. **The guards move with the text** (`tests/test_execution_knowledge_rules.py`'s fallback and verb
   statements; `tests/test_contracts.py`'s (g) pin).

## To measure at gap analysis

- The export's JSON shape on the installed lean-ctx (field names: `category`, `key`, `valid_until`,
  `confidence`), and whether the bridge's `ctx_knowledge action=export` and the CLI's `knowledge export`
  write the same file.
- Whether a stated reading belongs in the skills (capability words only, DN §D18) or only in
  `contracts/lean-ctx.md`, with the skills naming "the export's current facts".
- lean-ctx#2248's answer, if any has arrived: a full listing would retire the fallback, not reword it.
- The score (2 points filed) and the behaviour units.
