# CR-MDB-016 — Crucible skills handover: adopt, bundle, publish, supersede deployed

**Status:** PROPOSED
**Type:** migration
**Priority:** P1 (blocks release 0.1.0 — the deployed skill actively teaches a removed API)
**Depends on:** CR-MDB-011 (skills-src/crucible routing baseline), CR-MDB-014 (installer + wheel asset pipeline)
**Labels:** crucible, skills, packaging, deploy, handover
**Phase:** Wave 4
**Design reference:** Sandesh #1336 (Crucible's handover request + stale-skill defect) · #1337 (our ratified answer) · queue note 2026-07-28 · PRD §D7/§D9 (amended)

## Context

Sandesh #1336 (Mainline - Crucible, 2026-07-27) requested confirmation of the CR-CRU-035
skills division and reported a live defect. The user's ratification (2026-07-28, relayed
in #1337) **widened the division: Model B takes FULL ownership of the skills component —
content, bundling, AND deploy.** Crucible exits the skills business entirely (they are
removing the `[skills]` stage from their installer) and their `clients/skills/` copy
freezes after we import it.

The defect: the deployed `~/.claude/skills/crucible` predates CR-CRU-036 and carries
**12 references to the removed `WORKFLOW_CYCLE_ID` variable** (SKILL.md + 5 stack
references, verified 2026-07-28) and no arduino reference. Every session on the machine
loads it, so agents are instructed to use an API the server no longer accepts (the
orphaned-run failure mode). Related: `~/.claude/scripts/` still mirrors a dead client
set incl. `hw-crucible.py` (deferred item (b) of CR-MDB-011's close-out).

Canonical source to import: `crucible:clients/skills/` — 8 bundles: `agent-protocol`
(+ `scripts/heartbeat.sh`), `crucible-register`, `crucible-report-{arduino,bun,java,
python,rust,vscode}`. All carry Vercel-Skills `metadata:` frontmatter and zero
`WORKFLOW_CYCLE_ID` references.

This CR supersedes CR-MDB-011's routing premise: the per-stack authority is no longer
"managed + updated by Crucible" — it is Model-B-owned, shipped as a published artifact.

**Repo-local authoring rule binds:** all authoring lands in `skills-src/`; the ONLY
`~/.claude` writes happen in §S4 via the installer (this CR IS the user-approved
real-home deploy activation for the skills asset class, resolving the deferral routed
forward from CR-MDB-014).

## Scope

### §S1 — Import the canonical package (handover)
Copy the 8 bundles from `crucible:clients/skills/` into `skills-src/` verbatim
(`skills-src/agent-protocol/`, `skills-src/crucible-register/`,
`skills-src/crucible-report-<stack>/` ×6). Byte-identical import; provenance
(origin repo, commit, date, ratification refs #1336/#1337) recorded in a single
`skills-src/CRUCIBLE-HANDOVER.md`, never by editing the imported files.

### §S2 — Routing + ownership sync in `skills-src/crucible/`
Rewrite the routing language in `SKILL.md` + `references/{rust,java,bun,python,vscode}.md`
(+ add `references/arduino.md` router for parity): the per-stack authority is the
Model-B-bundled `crucible-report-<stack>` skill (deployed by the modelb-axi installer),
not `crucible:clients/skills/`. Consumer constraint from 011 holds: the five existing
reference paths keep resolving; the routers stay thin (Model B deltas only).

### §S3 — Bundle + publish
Add the 8 imported bundles to the modelb-axi wheel assets (`modelb_axi/_assets`), extending
CR-MDB-014's import-fidelity gate (durable coverage-superset contract) to cover them.
The published artifact is the sole distribution channel from this CR on.

### §S4 — Deploy: supersede the stale real-home copy (installer only)
Run the installed `modelb-axi` against the real home to: (a) supersede
`~/.claude/skills/crucible` with the §S2 content; (b) install the 8 handed-over bundles;
(c) retire the stale `~/.claude/scripts/*crucible*` client mirrors and repoint their
referencers to `~/Documents/data_projects/crucible/clients/` paths (011 close-out item
(b)). All `~/.claude` deletions follow chezmoi discipline (destroy/forget, no-auto
config, manual source commits — never apply/push).

### §S5 — Intimation
Reply on Sandesh thread #1336 when the deployed copy is superseded (commitment made in
#1337), telling Crucible their `clients/skills/` copy may be frozen/retired.

## Acceptance Criteria

1. `skills-src/` contains all 8 imported bundles, byte-identical to
   `crucible:clients/skills/` at the handover commit recorded in
   `skills-src/CRUCIBLE-HANDOVER.md`.
2. Zero `WORKFLOW_CYCLE_ID` occurrences under `skills-src/` and, post-§S4, under
   `~/.claude/skills/`.
3. `skills-src/crucible/SKILL.md` routes every stack row (arduino included) to a
   Model-B-owned `crucible-report-<stack>` bundle; zero references to
   `crucible:clients/skills/` as a live authority (provenance doc excepted).
4. Wheel-installed `modelb-axi` ships the 8 bundles (installed-binary e2e, not dev-mode);
   the import-fidelity gate covers them.
5. Post-§S4: `~/.claude/skills/crucible` matches the deployed §S2 content;
   `crucible-report-arduino` present in the deployed set; no `*crucible*` client
   scripts remain under `~/.claude/scripts/`; every former referencer resolves to the
   crucible-repo client paths.
6. Chezmoi round-trip clean after §S4: retired files stay retired; no drift resurrect.
7. The five pre-existing `crucible/references/<stack>.md` consumer paths still resolve
   (22 agent definitions + 2 refactorer skills).
