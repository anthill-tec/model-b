# CR-MDB-022 — Adopt the workflow tooling Model B publishes skills for: seven scripts into the repo, one TOON codec, and supersede of the global copies

**Status:** PENDING
**Type:** feature
**Priority:** P1 (blocks release 0.1.0 — seven published skills instruct tooling this repo does not contain, the wheel ships an empty asset slot for it, and the suite imports another project's source by absolute path)
**Depends on:** CR-MDB-018 (`config.py`/`preflight.py` seam), CR-MDB-020 (shares the two memory templates)
**Labels:** tooling, installer, axi, toon, ownership, supersede, feature
**Phase:** Wave 5
**Design reference:** user directive 2026-08-27 ("all Model B scripts are owned inside the model-b subproject and repo-managed here; the same-named scripts in the Claude global directories are NOT managed by Model B — the repo version REPLACES them") · user directive 2026-08-27 (`toon.py`, `worktree-flow.py`, `schedule_db.py`, `skill-release-gate.py`, `rust-{code-health,crate-map,dead-scan}.py` support Model B coding workflows and provide tooling support for the skills Model B publishes) · `crucible:docs/research/DN-crucible-toon-subset.md` (**Crucible-owned** — cited, never edited) · `contracts/crucible-envelope.md` (the Model B-owned mirror where this CR records the subset) · PRD §D9/§D10 · CR-MDB-010 (the worktree-flow AXI envelope) · CR-MDB-016 §C2 (the real-home supersede pattern this CR reuses)

## Context

Seven scripts drive the Model B workflow and are named by the skills Model B publishes. The
intended arrangement is that they are owned here, repo-managed, and deployed by the
installer, with the copies in the user's global Claude directories superseded by this repo's
version. **That is not the current state.** Measured 2026-08-27:

- `toon.py`, `worktree-flow.py`, `schedule_db.py`, `skill-release-gate.py`,
  `rust-code-health.py`, `rust-crate-map.py`, `rust-dead-scan.py` — **none exists anywhere in
  this repo**. `git ls-files scripts/` returns exactly one path: `scripts/.gitkeep`.
- The only live copies are in `~/.claude/scripts/`, tracked by the user's chezmoi — the
  arrangement the same-day directives retire.
- `pyproject.toml:26` force-includes `"scripts" = "modelb_axi/_assets/scripts"`, so **every
  wheel built since CR-MDB-014 has shipped an empty tooling directory**. No gate asserts the
  asset class has content, which is why an empty slot survived two releases' worth of work.

**Seven published surfaces already instruct the missing tooling.** `worktree-flow` is cited
by `skills-src/bootstrap/SKILL.md`, `skills-src/shutdown/SKILL.md`,
`skills-src/model-b/references/orchestration-common.md`,
`skills-src/model-b/references/orchestration-track.md`,
`skills-src/memory-templates/{java,rust}-orchestration.md` and `AGENTS.md`; `schedule_db` and
the three `rust-*` tools are cited by `skills-src/memory-templates/rust-orchestration.md`. A
user who installs Model B today receives the skills and none of the tools they name. It is
the dangling-edge class CR-MDB-020 closes for Crucible's clients, except here the missing
artifact is Model B's own and the fix is ownership, not anchoring.

**Adoption forces one design decision: which TOON implementation Model B owns.** Three
exist, and the disagreement between two of them already costs three test failures:

| Implementation | Size | Role today |
|---|---|---|
| `crucible:clients/toon.py` | 1356 lines | Crucible's own. `tests/test_worktree_flow_axi.py:39-45` inserts `~/Documents/data_projects/crucible/clients` on `sys.path` and imports it as the decoder ORACLE |
| `~/.claude/scripts/toon.py` | 254 lines | encoder + decoder, described at `worktree-flow.py:117` as "copy of `crucible:clients/toon.py` sitting beside this script"; loaded by `sys.path.insert` at `:93`, imported at `:136` |
| `modelb_axi/axi.py` | 95 lines | Model B's OWN encode-only 4-construct subset, whose docstring at `:10-12` states it "deliberately NEVER imports Crucible's `clients/toon.py`" |

The failure is the collision. `worktree-flow.py` emits empty-list headers — measured
verbatim, `rows[0]:` and `help[0]:` with no items — which the 254-line encoder produces
happily and Crucible's 1356-line decoder refuses with
`ToonDecodeError: Line 7: Expected 1 list-form items, but got 0`. Three of the six tests in
`tests/test_worktree_flow_axi.py` fail on precisely this, and they are part of the recorded
7-failure baseline. The defect stayed latent because the tool lives outside the repo, where
no gate ever ran against it.

Two things are therefore wrong beyond the missing files. A script that self-describes as a
copy of a Crucible file cannot be adopted as Model B's own without contradicting the
directive that Model B maintains none of Crucible's client scripts. And a suite that reaches
into a sibling checkout by absolute path to borrow another project's codec has no business
doing so once Model B owns the format it emits.

**The empty-array question is a real contract question, not a typo — and its governing
document is not ours.** Model B's envelopes are consumed by Model B (the orchestrator, the
ambient hook), but the subset `modelb_axi/axi.py` implements is declared in
`DN-crucible-toon-subset.md`, which lives in **Crucible's** repo
(`crucible:docs/research/`), not this one. `axi.py:12` cites it by bare filename with no
anchor — the same unanchored-cross-project-reference defect CR-MDB-020 fixes for the client
paths, and under the standing directive Model B may not edit it. So the subset Model B
actually honours must be recorded on a Model B-owned surface:
`contracts/crucible-envelope.md`, which already exists for exactly this purpose. The
resolution must be the form a subset-conformant decoder accepts, established by test, so an
envelope Model B emits is never undecodable to a reader following the documented subset.

**Supersede, not coexistence.** Once the installer deploys this repo's version, the
same-named copies under `~/.claude/scripts/` are stale duplicates of an artifact Model B now
owns, and a session that runs the old path runs unversioned code. CR-MDB-016 §C2 solved this
exact problem for the skills tree — store plus symlinks live, stale mirrors retired,
referencers repointed — and `tests/test_realhome_supersede.py` is the gate that holds it.
This CR reuses that pattern. One boundary applies: the leftovers are chezmoi-managed, and a
plain `rm` of a chezmoi-managed file resurrects it on the next apply, so the physical removal
is a `chezmoi destroy`/`forget` in the USER's dotfile tree. Model B runs no chezmoi
operation. The CR makes its own copy authoritative, proves no Model B surface references the
old location, and REPORTS the exact leftover paths for the user to destroy.

`~/.claude/scripts/` also holds electronics tooling (`elk_*`, `sch-*`, `skidl_*`,
`layout-clip-probe.*`), EXCLUDED by standing rule (anthill-forge dead), plus `gate-lock.sh`
and `gh-run-watch.sh`, which are unmanaged by chezmoi and outside the seven named. None are
in scope.

## Scope

### §S1 — Adopt the seven scripts into `scripts/`
The seven land under `scripts/`, the already-force-included asset root, replacing
`.gitkeep`. Each gains a header recording that Model B owns it and which published skills
consume it. Executable bits are preserved for the five that carry them. Content is adopted
as-is apart from §S2 and §S3; this is an ownership move, not a rewrite.

### §S2 — One TOON codec, owned by Model B
No file in this repo is a copy of a Crucible file. Model B's codec lives in `modelb_axi/` as
the single implementation: `axi.py`'s existing 4-construct encoder gains the decoder the
tools and tests need, and `scripts/toon.py` becomes a thin re-export so a directly-invoked
script still works. No repo file imports `crucible:clients/toon.py`.

`worktree-flow.py`'s `sys.path.insert` + bare `import toon` (`:93`, `:136`) resolves to the
adopted module, as does its `schedule_db` import (`:95`); the existing "unavailable → warn,
queue-only" degrade path is preserved unchanged.

### §S3 — Fix the empty-array defect and pin the round trip
Establish by test which empty-list form the documented subset decodes, and make the encoder
emit it. Every verb that can produce a zero-row table — `status`, `next`, `progress` —
round-trips through Model B's own decoder. `tests/test_worktree_flow_axi.py` drops the
absolute-path insert into the Crucible checkout and decodes with Model B's codec; its three
failures resolve for the right reason — the encoder was wrong, not the oracle.
`contracts/crucible-envelope.md` — the Model B-owned surface — records the 4-construct
subset including the empty-array form, since a construct that cannot round-trip is not in
the subset whatever any document says. `axi.py`'s bare citation is anchored as
`crucible:docs/research/DN-crucible-toon-subset.md` and pointed at the Model B contract for
the binding version; Crucible's note is cited, never edited, and no divergence from it is
introduced without raising it to them on the #1336 lineage.

### §S4 — Ship them through the installer
`modelb_axi/deploy.py` treats `scripts/` as a deployed asset class under the same sha256
manifest discipline, idempotence, and hand-modification skip rule as the skills and hook
scripts, into a store path beside them. `install.toml` records the deployed location, and the
seven consuming documents are repointed at it.

### §S5 — Supersede the global copies
The deployed copy is authoritative. No Model B surface may reference
`~/.claude/scripts/<tool>` for any of the seven, and `tests/test_realhome_supersede.py`'s
retired-referencer gate — which already asserts the absence of the CR-MDB-016-retired
`*crucible*` mirrors — is extended to the seven names, so a resurrected or re-referenced
global copy fails the gate.

The installer REPORTS any surviving global copy as a stale leftover, naming the exact paths
and the `chezmoi destroy` the user must run, and exits 0. It never deletes a file it does not
own, never runs chezmoi, and never writes into the user's dotfile source.

### §S6 — Gates that keep the slot full
The asset class is asserted non-empty and complete: the seven names are enumerated in a test,
so no future wheel can ship an empty `scripts/`, and a script added without a consuming-skill
reference, or removed while still referenced, fails.

## Acceptance criteria

### §S1
- [ ] All seven files exist under `scripts/` and `scripts/.gitkeep` is gone.
- [ ] Each carries a header naming Model B as owner and listing its consuming skills.
- [ ] The five that were executable are executable in the repo.
- [ ] No module or test added by this CR writes under `~/.claude` or invokes `chezmoi`.

### §S2
- [ ] Exactly one TOON implementation exists in the repo, in `modelb_axi/`, exposing
      `encode` and `decode`.
- [ ] `scripts/toon.py` re-exports it and holds no second implementation — asserted by
      identity of the encode/decode callables, not by line count.
- [ ] Zero `sys.path` inserts naming a path outside this repo under `scripts/`,
      `modelb_axi/` or `tests/`, and zero occurrences of `data_projects/crucible/clients`.
- [ ] The phrase "copy of crucible:" does not appear anywhere in the repo.
- [ ] `worktree-flow.py` runs from the repo checkout and resolves `toon` and `schedule_db`
      with no `~/.claude` path on `sys.path`.

### §S3
- [ ] `decode(encode(x)) == x` for an envelope carrying an empty list, asserted directly on
      the codec.
- [ ] `worktree-flow.py status`, `next` and `progress` each emit stdout Model B's decoder
      accepts, including on a project with no ChangeSet DB (the
      `schedule_db unavailable — queue-only project` path).
- [ ] `tests/test_worktree_flow_axi.py` passes all six tests and imports no module from
      outside this repo.
- [ ] `contracts/crucible-envelope.md` states the 4-construct subset and the empty-array
      form; no file in Crucible's repo is modified by this CR.
- [ ] No repo file cites `DN-crucible-toon-subset.md` by bare filename — every citation
      carries the `crucible:` anchor.

### §S4
- [ ] `deploy.py` deploys `scripts/` with sha256 manifest comparison; a second run reports
      every file unchanged; a hand-modified destination is SKIPPED unless `--force-managed`.
- [ ] `install.toml` records the deployed scripts location; a dry-run writes nothing.
- [ ] `bootstrap/SKILL.md`, `shutdown/SKILL.md`, `orchestration-common.md`,
      `orchestration-track.md`, both memory templates and `AGENTS.md` name the deployed
      location — zero references to a path this CR did not create.
- [ ] An integration test drives the real installer entry point against a sandboxed
      `--target-root` and then EXECUTES a deployed script (`worktree-flow.py --help`),
      asserting exit 0 — the wire-the-call-path gate for this CR.

### §S5
- [ ] Zero occurrences of `~/.claude/scripts/` paired with any of the seven names anywhere
      under `skills-src/`, `modelb_axi/`, `scripts/`, `contracts/`, `docs/changes/` or
      `AGENTS.md`.
- [ ] `tests/test_realhome_supersede.py` asserts the seven names are absent from
      `~/.claude/scripts/`, in the same shape as its existing `*crucible*` mirror gate, and
      remains behind `MODELB_REALHOME_GATE=1`.
- [ ] With a stale global copy present, the installer names the exact leftover paths and the
      `chezmoi destroy` remedy on stderr and exits 0 — asserted against a sandboxed fixture,
      never the real home.
- [ ] No code path added by this CR deletes, moves, or rewrites a file under `~/.claude`.

### §S6
- [ ] A gate enumerates the seven expected names under `scripts/` and fails on absence, on
      an unlisted addition, and on an empty asset root.
- [ ] The built wheel contains all seven under `modelb_axi/_assets/scripts/` — asserted
      against a built artifact, not the source tree.

## Estimated size

7 scripts adopted, `modelb_axi/axi.py` extended with a decoder, `deploy.py` + `config.py`
gain an asset class, 1 test module fixed and 2 added, 1 real-home gate extended, 7 consuming
documents repointed, 1 Model B-owned contract updated. No Crucible file touched.

## Risk

- **The wheel-content AC needs a real build.** CR-MDB-014's VERIFY caught exactly this class
  (assets absent from the wheel while dev-mode tests passed). Assert against a built
  artifact.
- **`axi.py` gains a decoder it did not have.** It is encode-only by design and three tests
  pin it. The encoder's output must stay byte-identical for every currently-tested input.
- **Supersede must not become deletion.** The leftovers are chezmoi-managed; a plain `rm`
  resurrects on apply and would also mean Model B mutating the user's dotfile tree, which two
  standing rules forbid. Report-and-name is the deliberate ceiling.
- **Shared files with CR-MDB-020** — both repoint the two memory templates; the dependency
  edge exists to serialize them.
- **`schedule_db.py` reads a database this repo has no fixture for.** Keep its
  unavailable-degrade path as the tested path rather than introducing a DB fixture.

## Non-goals

- No change to any Crucible file and no import of one.
- No chezmoi operation, and no deletion of anything under `~/.claude`.
- No adoption of the electronics tooling (`elk_*`, `sch-*`, `skidl_*`,
  `layout-clip-probe.*`) — excluded by standing rule — nor of `gate-lock.sh` /
  `gh-run-watch.sh`, outside the seven named.
- **No adoption of the `code-health` skill.** It is a Model-B-workflow skill by content — it
  speaks of MAINLINE, cull-CR ratification and snapshot points — and it consumes the three
  `rust-*` tools this CR adopts, yet it is not one of Model B's 13 published bundles and
  lives only in the user's skill tree. Adopting the tools without their consuming skill is
  deliberate scope control; whether that skill becomes a published bundle is a separate
  decision.
- No rewrite of `worktree-flow.py`'s verb surface or lane logic beyond what §S2/§S3 require.
