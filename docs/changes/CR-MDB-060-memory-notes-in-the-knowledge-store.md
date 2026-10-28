# CR-MDB-060 — Memory notes live in the knowledge store

**Status:** PENDING — **SEED, not the finished spec** (filed 2026-10-10 into release 1.0.0, wave 2).
Gap analysis, the design record, the spec and its pre-review happen in order when this CR starts.
**Type:** feature (scaffold, project schema, skills, memory templates, installer preflight)
**Priority:** P1 — release 1.0.0, wave 2.
**Depends on:** CR-MDB-085 (the stack skills take the reference material out of `docs/memory/` first);
the board is authoritative: read `queue`, not this line.
**Labels:** memory, knowledge-store, lean-ctx, scaffold, skills
**Design reference:** CR-MDB-045 (execution knowledge store, `KNOWLEDGE_CATEGORY`); PRD D10;
`contracts/lean-ctx.md`; `orchestration-common` § "Memory"; PRD D5, amendments of 2026-10-10 (the
knowledge store is the one home; lean-ctx required), 2026-10-14 (facts reconciled automatically) and
2026-10-28 (material placed by its readers; the stack skill).

## Context

Model B keeps two memory systems side by side. Execution knowledge goes to the lean-ctx knowledge
store under `KNOWLEDGE_CATEGORY` (CR-MDB-045) — but only where the installer found lean-ctx
(`project_schema.toml`: `when = "lean-ctx"`). Separately, `init` lays down Markdown notes in
`docs/memory/` from `skills-src/memory-templates/` (`operational-commands.md`,
`<stack>-orchestration.md` for arduino/java/rust, five long `java-*.md` language references) plus an
`INDEX.md`, which the bootstrap and shutdown skills read. The knowledge store is more efficient and
searchable, and PRD D5 makes it the one home for a Model B project's memory notes.

## Scope (seed)

1. **The key is unconditional.** `KNOWLEDGE_CATEGORY` loses `when = "lean-ctx"`, and `init` drops its
   branches that render a project without a category. The installer already requires lean-ctx
   (`policy: "required"`); what an install made with `--allow-missing-capabilities` does without it is
   measured here.
2. **`init` ships knowledge, not Markdown notes.** The orchestrator-facing notes — those parts of the
   stack orchestration templates, and `operational-commands.md` — become importable knowledge seeds
   (keyed facts, per stack); `init` writes no `docs/memory/` and no `INDEX.md`. The reference material
   and the agent-facing mechanics are the stack skills' (CR-MDB-085).
3. **The import path.** CR-MDB-045 forbids writing through the `lean-ctx knowledge` CLI, so the seeds
   are imported through the session's knowledge capability: an OKF bundle (one Markdown file per fact,
   with YAML frontmatter), imported with skip-existing merge, idempotent on re-runs.
4. **The test-run rule reaches the facts** (DN-multi-harness-deploy-model §D21): no seed teaches a
   runner invocation; a test run is the stack client's.
5. **The store keeps its facts.** A restore brings archived facts back at low confidence, and the next
   write can archive them again; the bootstrap step that restores the category also re-confirms each
   current fact it brings back, so nothing current stays archived.
6. **The skills.** Bootstrap and shutdown stop reading `docs/memory/INDEX.md`;
   `orchestration-common` § "Memory" names the knowledge store as the one home, and drops "Without the
   key, nothing changes"; every skill naming `docs/memory/` is updated.
7. **Facts are reconciled automatically, never on request.** The GC principle (a fact the repo or
   the board comes to track is removed; a fact the run has overtaken is rewritten under its key) runs
   at fixed workflow moments, without asking the user:
   - **bootstrap**, right after it loads the category: each fact is checked against the board
     (`queue`, `next`, `plans`) and the repo, then rewritten or removed, and the report names what
     changed;
   - **close-out**, after `cr-close`: every fact naming the closed CR is rewritten or removed;
   - **shutdown**, before the watcher stops: facts this run overtook are brought current.

   A fact is never only flagged for the user to approve; the rule and these three moments land in
   the bootstrap, shutdown and `model-b` skills and in `orchestration-common` § "Memory".

## To measure at gap analysis

- Every consumer: `modelb_axi/scaffold.py` (`docs/memory/` writes, `memory-templates/` resolution),
  `project_schema.toml`, `requirements.py`, preflight and the installer's verdicts, `deploy.py`
  (`memory-templates` is scaffold material), the skills above, `AGENTS.md` (repo and scaffolded),
  `contracts/lean-ctx.md`, `archive/mapping.md` rows, and the structural gates asserting
  `docs/memory/` or the conditional key.
- **Boundary with CR-MDB-055 (`migrate`, 1.1.0):** existing projects' `docs/memory/` and Claude-era
  user-scope memory notes migrate through `migrate`; this CR covers new projects and Model B itself.
- **Score:** seeded at 13; re-scored at gap analysis now that the reference material is CR-MDB-085's.
