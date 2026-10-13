# CR-MDB-060 — Memory notes live in the knowledge store

**Status:** PENDING — **SEED, not the finished spec** (filed 2026-10-10 into release 1.0.0, wave 2).
Gap analysis, the design record, the spec and its pre-review happen in order when this CR starts.
**Type:** feature (scaffold, project schema, skills, memory templates, installer preflight)
**Priority:** P1 — release 1.0.0, wave 2 (user ruling 2026-10-10).
**Depends on:** none (board-authoritative: read `queue`, not this line)
**Labels:** memory, knowledge-store, lean-ctx, scaffold, skills
**Design reference:** CR-MDB-045 (execution knowledge store, `KNOWLEDGE_CATEGORY`); PRD D10;
`contracts/lean-ctx.md`; `orchestration-common` § "Memory"; user rulings 2026-10-10 (below).

## Context

Model B keeps two memory systems side by side. Execution knowledge goes to the lean-ctx knowledge
store under `KNOWLEDGE_CATEGORY` (CR-MDB-045) — but only where the installer found lean-ctx
(`project_schema.toml`: `when = "lean-ctx"`). Separately, `init` lays down Markdown notes in
`docs/memory/` from `skills-src/memory-templates/` (`operational-commands.md`,
`<stack>-orchestration.md` for arduino/java/rust, five long `java-*.md` language references) plus an
`INDEX.md`, which the bootstrap and shutdown skills read. The knowledge store is more efficient and
searchable; the user rules it the one home for a Model B project's memory notes.

## User rulings (2026-10-10)

1. **Release 1.0.0,** a new CR in wave 2.
2. **lean-ctx is required by default:** every Model B project has a `KNOWLEDGE_CATEGORY`;
   `docs/memory/` is retired. A machine without lean-ctx is a preflight failure with remediation,
   not a silent fallback to Markdown.
3. **The language references are split into facts** — short, keyed, searchable facts, not documents.
4. **Model B's own notes are migrated as a chore, outside this CR** (user ruling 2026-10-10: the CR
   covers only the definitions Model B manages). Done 2026-10-10: the Claude-era user-scope notes'
   untracked execution knowledge went into `modelb-workflow` by hand, and `docs/memory/` (only the
   generic `operational-commands.md` template) was removed in a `chore(memory)` commit.

## Scope (seed)

1. **The key is unconditional.** `KNOWLEDGE_CATEGORY` loses `when = "lean-ctx"`; lean-ctx moves from
   an optional to a required tool in the installer's verdicts and preflight, with its remediation.
2. **`init` ships knowledge, not Markdown.** The memory templates become importable knowledge seeds
   (keyed facts, per stack); `init` writes no `docs/memory/` and no `INDEX.md`.
3. **The import path.** CR-MDB-045 forbids writing through the `lean-ctx knowledge` CLI (its project
   does not follow the working directory), so the seeds are imported through the session's knowledge
   capability — *measure:* bootstrap's first run importing with skip-existing merge, the bundle format
   (lean-ctx's import/export, e.g. its Markdown bundle), and idempotence on re-runs.
4. **The test-run rule reaches the facts** (DN-multi-harness-deploy-model §D21): no fact teaches a
   runner invocation (`./mvnw test` in the java references today); a test run is the stack client's.
5. **The language references as facts:** the five `java-*.md` templates, the stack orchestration
   templates and `operational-commands.md` are split into keyed facts under the project's category
   (or a stack-scoped one — a gap-analysis decision).
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
- **Score:** seeded at 13 — the cap; split at gap analysis if it measures larger.
