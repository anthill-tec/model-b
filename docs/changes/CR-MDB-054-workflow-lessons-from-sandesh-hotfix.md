# CR-MDB-054 — Workflow lessons from Sandesh's 0.4.1 hotfix run

**Status:** PENDING — **SEED, not the finished spec** (filed 2026-10-03 into release 1.1.0, wave 3).
Gap analysis, the design record, the spec and its pre-review happen in order when this CR starts.
**Type:** refactor (skills, agent definitions)
**Priority:** P2 — release 1.1.0, wave 3.
**Depends on:** none (board-authoritative: read `queue`, not this line)
**Labels:** skills, agents, crucible, release, conventions
**Design reference:** Sandesh #1418 (Mainline - Sandesh, 2026-10-03; owner rulings and gate findings
from the Sandesh 0.4.1 hotfix run); PRD D3 and D5; DN-multi-harness-deploy-model §D18

## Context

Sandesh runs its development on Model B's skills and agent definitions. Its 0.4.1 hotfix run
produced owner rulings and gate findings that belong in the shared definitions, not only in
Sandesh's project memory. Each item below is measured against Model B's own text and suite at gap
analysis, and the ones that conflict with an existing Model B rule are brought to the user as rulings
before the spec derives from them.

## Scope (seed — the seven lessons)

1. **CI and release meta is a chore, never a CR.** Workflows, release scripts, release mechanics and
   version pins are release-checklist items committed as `chore(ci|release): …` — no CR, cycle or
   RED/GREEN agent. Candidate homes: `cr-authoring` (CR vs task), `orchestration-common` (workflow gates).
2. **Release and CI configuration is not a test subject.** Tests that pin branch names, version strings
   or workflow shapes change every release and detect nothing about the product. Candidate homes: the
   RED template, gap-analysis Dimension 7 (cost) as a named smell. *Measure:* Model B's own pins
   (e.g. `test_pi_package`'s package version, any `release.yml` shape tests).
3. **Caller-existence is VERIFY's grep, never a source-text test.** Behavioural tests prove the seam.
   Candidate homes: `cr-authoring`'s caller-existence AC, the RED and VERIFY templates. *Measure:*
   which of Model B's structural gates are product contracts (skill text is Model B's product) and
   which only pin implementation text.
4. **While a plan is open, every dispatch carries a cycle id, or the CR is closed first.** Candidate
   homes: the sub-agent procedure, `orchestration-mainline`. *Reconcile:* the spec pre-review registers
   as `report` with no cycle (CR-MDB-046) — it runs before `plan-file`, so no plan is open.
5. **Crucible verbs: check `ok=`; re-register on a 409; skipping a dead cycle.** A truncated output can
   hide a failed transition. The client has no skip verb; the route is
   `PATCH /api/v2/projects/<key>/plans/<plan>/cycles/<id> {"status":"skipped","agentId":…}` (Crucible
   cc'd for a `cycle-skip` verb). Candidate home: the `crucible` skill.
6. **Record the release in the same turn as `git flow release finish`.** `milestone --type release`
   follows finish immediately, not deferred until publishes are confirmed; `shutdown` treats a finished
   release with no release milestone as dangling work; `--packages` takes `registry:name:version`
   (bare entries are dropped). Candidate homes: `git-workflow` § Releases, `model-b` §4, `shutdown`.
7. **lean-ctx outside the project root.** lean-ctx refuses paths outside the project root (skills,
   `~/.crucible/clients`) unless `LEAN_CTX_EXTRA_ROOTS` covers them; agent definitions that require
   lean-ctx state it. Candidate homes: the agent templates, `contracts/lean-ctx.md`. Model B never
   writes the user's lean-ctx config.
