# CR-MDB-045 — Execution knowledge in lean-ctx's knowledge store

**Status:** PENDING (filed 2026-09-27)
**Type:** feature (skills, contract)
**Priority:** P2 — release 1.0.0, wave 2.
**Depends on:** CR-MDB-044 (both edit `orchestration-common.md`)
**Labels:** memory, lean-ctx, orchestration
**Design reference:** PRD D5 (AMENDED 2026-09-27: instruction tiers versus execution knowledge);
`contracts/lean-ctx.md`; Crucible's measured practice (Sandesh #1409, #1410)

## Context

`orchestration-common.md` § "Memory" governs what an orchestrator picks up while running a project,
before the repo tracks it. It sets the GC principle (hold only what the repo doesn't yet track, and
delete a note once it becomes a repo artifact) and forbids unilateral writes. It doesn't say where
such knowledge is kept.

Crucible keeps this knowledge in lean-ctx's project-scoped knowledge store and loads it with one call
at bootstrap, which spends far fewer tokens than re-reading memory files. It measured three pitfalls:
- `recall` with a query returns only the facts that match;
- facts get archived silently;
- `restore` ignores `dry_run`.

The rules and the per-project context (PRD D5's two instruction tiers) are out of scope: they are
never memory.

## Scope

### §S1 — Where execution knowledge lives (`orchestration-common.md` § "Memory")

§ "Memory" gains:
- **Where lean-ctx is installed,** execution knowledge is kept in its knowledge store, which is
  project-scoped:
  - one short fact per item, with the project's category and a stable kebab-case key;
  - `remember` with the same key supersedes a fact.
- **Only execution knowledge goes there:** never an orchestrator rule, an agent definition, a ruling
  that belongs in the PRD or a DN, or a project fact that belongs in `.env` or `AGENTS.md`.
- **The existing rules still apply:** a fact is stored only after the user has seen its wording, and
  it is removed once it becomes a repo artifact.
- **Where lean-ctx is not installed,** nothing changes.

The section names lean-ctx's knowledge store as a capability, not a tool (DN §D18).

### §S2 — Loading it at bootstrap (`skills-src/bootstrap/SKILL.md`)

Where lean-ctx is installed, bootstrap:
- loads the project's category with a full listing, never a query recall;
- counts the facts against the number last recorded, and restores any that are missing;
- states in its report that the knowledge store is in use, and how many facts it loaded.

Shutdown needs no step: facts are written when they are learned.

### §S3 — The contract (`contracts/lean-ctx.md`)

The contract gains the knowledge store:
- the verbs Model B relies on: remember, search by category, restore, remove;
- the three measured pitfalls:
  - a query recall is not a full listing;
  - facts get archived silently;
  - `restore` ignores `dry_run`, so never rely on its preview.

## Acceptance criteria

- [ ] `orchestration-common.md` § "Memory" says that, where lean-ctx is installed, execution knowledge
      is kept in its project-scoped knowledge store, one fact per item under the project's category
      and a stable key. It also says that only execution knowledge goes there, and it keeps the GC and
      no-unilateral-write rules.
- [ ] § "Memory" names no rule, agent-definition or project-fact content as knowledge-store content,
      and names the store as a capability.
- [ ] `bootstrap` loads the category with a full listing, counts against the last recorded number,
      restores what is missing, and reports the store's use and the count. It says none of this
      applies where lean-ctx is not installed.
- [ ] `contracts/lean-ctx.md` records the knowledge verbs and the three pitfalls.
- [ ] Existing gates stay green, including the harness-neutral and retired-tool gates over the
      skills. The suite baselines are re-measured in `AGENTS.md`.

## Non-goals

- Where rules, rulings or project facts live (PRD D5, CR-MDB-042, CR-MDB-043).
- A fallback store where lean-ctx is absent.
- Migrating any existing memory into the store.
- Model B installing or configuring lean-ctx.
