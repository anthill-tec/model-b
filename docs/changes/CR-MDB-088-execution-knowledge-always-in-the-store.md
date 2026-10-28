# CR-MDB-088 — Execution knowledge always lives in the knowledge store, reconciled automatically

**Status:** PENDING — **SEED, not the finished spec** (filed 2026-10-28 into release 1.0.0, wave 2).
Gap analysis, the spec and its pre-review happen in order when this CR starts.
**Type:** feature (project schema, scaffold, skills)
**Priority:** P1 — release 1.0.0, wave 2, after CR-MDB-060.
**Depends on:** CR-MDB-060 (both edit the bootstrap and shutdown skills); the board is authoritative:
read `queue`, not this line.
**Labels:** memory, knowledge-store, lean-ctx, skills
**Design reference:** PRD D5, amendments of 2026-10-10 (the knowledge store is the one home; lean-ctx
required), 2026-10-14 (facts reconciled automatically) and 2026-10-28 (the store starts empty: no seeded
facts); CR-MDB-045 (the knowledge store, `KNOWLEDGE_CATEGORY`); `contracts/lean-ctx.md`;
`orchestration-common` § "Memory".

## Context

A Model B project keeps its execution knowledge in lean-ctx's knowledge store under
`KNOWLEDGE_CATEGORY` — but only where the installation recorded lean-ctx present
(`project_schema.toml`: `when = "lean-ctx"`), and the skills carry "Without the key, nothing
changes". The installer already requires lean-ctx (`policy: "required"`). Facts are reconciled against
the board and the repo by a bridging fact, not by the skills. And the store archives current facts on
its own: a `restore` brings them back at low confidence, and the next write can archive them again
(measured 2026-10-28).

## Scope (seed)

1. **The key is unconditional.** `KNOWLEDGE_CATEGORY` loses `when = "lean-ctx"`; `init` drops its
   branches that render a project without a category; what an install made with
   `--allow-missing-capabilities` without lean-ctx does is measured.
2. **The skills.** `orchestration-common` § "Memory" names the knowledge store as the one home of
   execution knowledge and drops "Without the key, nothing changes"; the bootstrap skill's Step 0.6
   always runs; the store starts empty — `init` seeds no facts.
3. **Facts are reconciled automatically, never on request** (PRD D5, 2026-10-14): at bootstrap right
   after the category is loaded, after every `cr-close` (each fact naming the closed CR) and at
   shutdown (the facts the run overtook), each fact is checked against the board and the repo, then
   rewritten under its key or removed, and the report names what changed. The rule and its three
   moments land in the bootstrap, shutdown and `model-b` skills and in `orchestration-common`.
4. **The store keeps its facts** (research note `lean-ctx-for-model-b` §S4, lean-ctx 3.11.4):
   - **The category is loaded from a complete source.** A bare category recall returns only 10 facts,
     and only those get the retrieval that slows their decay, so bootstrap reads the whole category
     (an export, or a recall with a raised limit).
   - **Restored facts are re-confirmed.** A `restore` brings a fact back at about 0.25 confidence,
     below the 0.3 archive threshold, so each current fact it brings back is re-confirmed (rewritten
     under its key, or given positive feedback) or the next lifecycle run archives it again.
   - **The limits are stated.** The 200-fact cap is shared with lean-ctx's own automatic captures,
     decay compounds on every lifecycle run, and `restore` has no dry run.
5. **The reach:** `project_schema.toml`, `modelb_axi/scaffold.py`, the rendered `AGENTS.md` lean-ctx
   section, `contracts/lean-ctx.md`, and the tests that pin the conditional key or the "without the
   key" rule.

## To measure at gap analysis

- Whether the reconciliation and re-confirmation can be stated as checkable rules in the skills, and
  how the knowledge-store tools' behaviour (archive on write, restore confidence) is stated without
  naming a lean-ctx tool where the built-in form forbids it.
- Which of the store's levers (a raised `max_facts`, automatic consolidation off) are project-scoped
  and need no `lean-ctx trust`; the project config file itself is CR-MDB-091's.
- **Score:** seeded at 5; item 4's widening (2026-10-29, from the lean-ctx study) may raise it.
