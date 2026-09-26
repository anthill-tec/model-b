---
name: model-b
description: Model B workflow model — the canonical home. Load for orchestration roles (mainline/track/solo), waves, the CR queue, cycle plans, and the universal sub-agent procedure. Triggers: model b, orchestration, mainline, track, solo, wave, CR queue, sub-agent procedure.
---

# Model B — the canonical workflow model

## 1. The model in one sentence + Crucible

> **Model B is a flow of ACTIONS triggered by ACTORS with specific ROLES.**

Ontology (LOCKED): Model B's `docs/research/DN-model-b-language.md` (a frozen import) — cite it, never fork it. Summary (≤10 lines):
- Multi-track (parallel) and single-track (sequential) execution differ ONLY in which actor roles are present and how actions are scheduled — the model itself is uniform.
- Crucible is the TRACKING system fronting this workflow: it tracks the actors and their actions without ever being an actor in it.
- Every level is an agent to Crucible (registers, heartbeats, carries a runtime, tombstones).
- Workflow-state env vars are `WORKFLOW_*`; the `CRUCIBLE_*` prefix is reserved for the tool's own configuration — Crucible never lends its name to workflow concepts.
- A solo project and a five-track project are the same schema with different actors present; every degradation is graceful (planless = inferred pairing; `track` absent = implicit solo lane).

## 2. Role hierarchy + labels

| Role | Scope | Authority |
|---|---|---|
| **MAINLINE ORCHESTRATOR** (solo alias: **vidushi**) | whole project workflow | spawns track orchestrators; allocates CRs to lanes from the depends-on graph; launches waves; files plans (solo); wave-boundary gates |
| **ORCHESTRATOR** (track) | one lane's CR queue | files/drives the cycle plan; activates + confirms cycles; closes the CR on merge; verifies agents deliver accurately |
| **RED / GREEN / VERIFY / FIX** (phase agents) | one phase of one cycle | execute and report: test runs, compile failures, heartbeats, register/unregister |

**Orchestrator labels are mode-aware** (naming registry, no other renderings may be minted):
- Solo (single-orchestrator, the default): `vidushi-<projectshortname>`.
- Multi-track: mainline is `Mainline-<projectshortname>`; each track orchestrator is `track<N>-<projectshortname>` (e.g. `track1-mdb`).
- **Label ≠ wire value.** The `WORKFLOW_ROLE` wire value stays per the ontology: `track-<n>`, ABSENT in solo.

## 3. Containment chain + execution vocabulary

```
Project → Mainline → [Track 1..N] → CR → Cycle → runs
```
- **Cycle** — one step in a CR's execution. Kinds `red-green | verify | fix` — ALL under identical rules. A cycle's span completes ONLY when the orchestrator confirms (`done`) — a passing run alone never closes anything.
- **CR** — groups cycles; always executed within a track (implicit solo lane when no tracks). **Closes on feature merge.**
- **Track** — a numbered lane; transient within a wave; wire `track-<n>`.
- **Wave** — a grouping of CRs marking an execution boundary: redesign point (solo) / sync boundary (multi) — all lanes pause when their queues complete; the next wave launches after design review. **Setup tasks and releases are NOT waves.**
- **Plan** — the DECLARED workflow filed with Crucible (server-assigned cycle ids). **Gate** — a no-mistakes pipeline run at a wave boundary, ingested as evidence. **Milestone** — lightweight workflow event (workspace timeline only). **Run** — a test/compile event by a phase agent, linked to its cycle via context.

## 4. Universal conventions (PRD §D3 — every project instantiates these)

1. **Naming registry + static init:** one canonical token + one acronym per project; derived forms are fixed — CR ids `CR-<ACRONYM>-NNN`, Crucible agentId `<agent-type>-<project>` (ONE identity; role declared via `--role`, never embedded in the id), Sandesh `<Project>` / `Mainline - <Project>`, repo dir kebab-case. Declared ONCE in `.env` at the project root: `PROJECT_NAME`, `PROJECT_TOKEN`, `PROJECT_ACRONYM`, `ORCHESTRATOR_LABEL` (mode-aware, derived), `REPO_OWNER` (remote owner, read by wave-boundary gates) — alongside tool config like `CRUCIBLE_PROJECT_KEY` (which lives in the gitignored `.env.local` overlay). The registry's instantiation path is the scaffold — `modelb-axi init` emits `.env` (and the `.env.local` placeholder) correct-by-construction; clients, wrappers, and orchestrators READ the registry from there instead of re-deriving it. **Monorepos:** each sub-project carries its own qualifying `.env` at its sub-project root; tools resolve the nearest sub-project dir, never the repo root's registry on a sub-project's behalf.
2. **Queue idiom:** `docs/changes/README.md` holds STRUCTURE only (CR / Title / Wave / Depends-on) + header (Design contract · Evidence base · Ontology · Target release) + dated footer Notes log + a release-boundary row. Live status is DERIVED on the Crucible board (no plan / open plan / closed+merge) — never hand-maintained.
3. **Plan/cycle idiom:** full plan filed at CR start — `plan-file --cr <id> --title <t> --cycle "C1 <label>" --cycle-kind red-green --cycle "C2 <label>" --cycle-kind verify --wave <n> --agent <registered-id>`; `--cycle` repeats once per cycle and each one carries its own `--cycle-kind` (`red-green|verify|fix`), the registered `--agent` id IS the plan's orchestrator (the free-text label flag is retired); server-assigned cycle ids only; cycle labels `C<n> <label> (§S…)`; a cycle closes only on orchestrator confirm; every ingest carries `WORKFLOW_*` context.
4. **Docs model:** `docs/changes/` + `docs/research/` everywhere; no ad-hoc folders (`plans/` etc.).
5. **Release CR:** a wave is never a release — a RELEASE CR bundles the final gates as an ordinary CR in the queue with a release-boundary row.

## 5. Role routing

Load the reference for YOUR role (references/, this skill dir):
- Every orchestrator: `references/orchestration-common.md` (incl. the MODE-MAP).
- Mainline (or solo vidushi): + `references/orchestration-mainline.md`.
- Track worker: + `references/orchestration-track.md`.
- Mainline↔Track messaging: `references/sandesh.md`.
- Dispatched sub-agents (RED/GREEN/VERIFY/FIX): `references/sub-agent-procedure.md`.

## 6. Electronics stack

Electronics (anthill-forge / hw tooling / electronics agents+skills) is EXCLUDED from Model B — under revision; revisit when that revision lands.

## 7. Operating rules (every role)

- **Confirm destructive operations** before executing them; delegate super-user operations to the user.
- **Never kill a user-visible process** — describe what and why, and let the user kill it.
- **Edit files with the harness's file-edit capability or ast-grep, never `sed`**; if a bulk text edit seems to need `sed`, surface it first.
- **Prefer the lean-ctx tools inside the project** (cached reads, compressed shell, ranked search, tree) over the harness's native equivalents.
