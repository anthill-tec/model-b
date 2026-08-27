# CR-MDB-022 — Tooling adoption: eight workflow scripts into the repo, one Model B-owned TOON codec, every reference detached from the local machine

**Status:** PENDING
**Type:** feature
**Priority:** P0 — **the FIRST CR of Wave 5**, implemented before 017/018/019/020/021/023 (user directive: detaching from the local development machine's environment is the precondition for the rest of the wave; while it is outstanding, published skills instruct tooling this repo does not contain and the wheel ships an empty asset slot for it)
**Depends on:** —
**Labels:** tooling, installer, axi, toon, ownership, detachment, feature
**Phase:** Wave 5
**Design reference:** user directives 2026-08-27 — (a) "all Model B scripts are owned inside the model-b subproject and repo-managed here; the same-named scripts in the Claude global directories are NOT managed by Model B", (b) "we are detaching from the local development machine's environment; any reference to these scripts should be for using them from our owned `scripts/` folder under Model B; we bundle these along with the skills we manage for release, thus publishing and overwriting the local machine environment — that is the pattern; chezmoi ownership on the local machine is not our problem", (c) "`code-health` and `gate-lock`: adopt those", (d) "`schedule_db.py` was a transitional workflow planning and scheduling DB, superseded by Crucible when its 0.2.0 is released — Crucible will own storing the workflow plan and state; this approach will be deprecated" · `crucible:docs/research/DN-crucible-toon-subset.md` (**Crucible-owned** — cited, never edited) · `contracts/crucible-envelope.md` · PRD §D9/§D10 · CR-MDB-010 (the worktree-flow AXI envelope) · CR-MDB-016 §C2 (the store-authoritative deploy + supersede pattern this CR reuses)

## Context

Eight scripts drive the Model B workflow and are named or described by the skills Model B
publishes. The intended arrangement is that they are owned here, bundled with the skills, and
published — with every reference resolving to Model B's own folder rather than to a path on a
particular development machine. **That is not the current state.** Measured 2026-08-27:

- `toon.py`, `worktree-flow.py`, `schedule_db.py`, `skill-release-gate.py`,
  `rust-code-health.py`, `rust-crate-map.py`, `rust-dead-scan.py`, `gate-lock.sh` —
  **none exists anywhere in this repo**. `git ls-files scripts/` returns exactly one path:
  `scripts/.gitkeep`.
- The only live copies are in `~/.claude/scripts/` on this machine.
- `pyproject.toml:26` force-includes `"scripts" = "modelb_axi/_assets/scripts"`, so **every
  wheel built since CR-MDB-014 has shipped an empty tooling directory** — undetected, because
  no gate asserts the asset class has content.

**Published surfaces already instruct the missing tooling.** `worktree-flow` is cited by
`skills-src/bootstrap/SKILL.md`, `skills-src/shutdown/SKILL.md`,
`skills-src/model-b/references/orchestration-common.md`,
`skills-src/model-b/references/orchestration-track.md`,
`skills-src/memory-templates/{java,rust}-orchestration.md` and `AGENTS.md`; `schedule_db` and
the three `rust-*` tools by `skills-src/memory-templates/rust-orchestration.md`. A user who
installs Model B receives the skills and none of the tools they name.

**`gate-lock.sh` is worse than unshipped — it is unnamed.**
`skills-src/model-b/references/orchestration-common.md:63` specifies the whole
serialize-heavy-gates protocol — the track's WAIT-FOR-FREE pre-flight, the gate-runner's
ownership of the lock file lifecycle, the coordinator's stale-lock arbitration — and **never
names the tool that implements it**. A track following the published rule cannot find the
binary. The tool exists (156 lines; verbs `acquire`, `wait-acquire`, `wait-free`, `release`,
`status`, `check`, `force-release`; exit 5 = timeout) and only this machine has it.

**The lock filename is a cross-project wire contract, not a defect to fix here.**
`gate-lock.sh` computes `<git-common-dir>/nai-gate.lock`, falling back to `/tmp/nai-gate.lock`
(`:12`, `:41`, `:46`) — a project-specific NAI name inside a generically published tool. The
obvious cleanup is forbidden: Crucible's `rust-crucible.py` is the GATE-RUNNER half of the
same protocol, owns the lock file (`_acquire_gate_lock`, 2h abandonment rule at `:111-113`)
and names our script in its own help text at `:363` ("wait for the in-flight gate to finish
(gate-lock.sh wait-free)"). Renaming the file on one side desynchronises the mutex: each tool
would wait on a path the other never writes, both would conclude the gate is free, and two
heavy regressions would run concurrently — precisely the environment-kill the rule exists to
prevent. This CR RECORDS the contract and raises any rename with Crucible on the #1336
lineage. It changes nothing about it.

**`schedule_db.py` is adopted as TRANSITIONAL, with its sunset written down.** It is the
interim workflow planning/scheduling DB behind `worktree-flow.py`'s lane plan. Crucible takes
over storing the workflow plan and state when their **0.2.0** ships, at which point this
approach is deprecated and `worktree-flow.py`'s DB half retires in favour of Crucible's
storage. Two consequences for this CR: the script is adopted so the tooling bundle is
complete and usable today, and **no investment goes into it** — no DB fixture, no new verbs,
no schema work, no widened tests. Its tested path stays the `schedule_db unavailable →
warn, queue-only` degrade, which is also the path a post-0.2.0 world makes permanent. The
sunset is recorded in `contracts/`, alongside the existing rule that Crucible **0.2.0 is not
released** (#1359) and must never be cited as available; the retirement itself is a future CR
gated on that release, not this one.

**Adoption forces one design decision: which TOON implementation Model B owns.** Three
exist, and the disagreement between two of them already costs three test failures:

| Implementation | Size | Role today |
|---|---|---|
| `crucible:clients/toon.py` | 1356 lines | Crucible's own. `tests/test_worktree_flow_axi.py:39-45` inserts `~/Documents/data_projects/crucible/clients` on `sys.path` and imports it as the decoder ORACLE |
| `~/.claude/scripts/toon.py` | 254 lines | encoder + decoder, described at `worktree-flow.py:117` as "copy of `crucible:clients/toon.py` sitting beside this script"; loaded by `sys.path.insert` at `:93`, imported at `:136` |
| `modelb_axi/axi.py` | 95 lines | Model B's OWN encode-only 4-construct subset, whose docstring at `:10-12` states it "deliberately NEVER imports Crucible's `clients/toon.py`" |

The failure is the collision. `worktree-flow.py` emits empty-list headers — measured verbatim,
`rows[0]:` and `help[0]:` with no items — which the 254-line encoder produces happily and
Crucible's 1356-line decoder refuses with
`ToonDecodeError: Line 7: Expected 1 list-form items, but got 0`. Three of the six tests in
`tests/test_worktree_flow_axi.py` fail on exactly this and are part of the recorded 7-failure
baseline. The defect stayed latent because the tool lived outside the repo, where no gate ever
ran against it. A script that self-describes as a copy of a Crucible file also cannot be
adopted as Model B's own without contradicting the standing no-client-maintenance directive.

**The subset's governing document is not ours either.** The subset `modelb_axi/axi.py`
implements is declared in `DN-crucible-toon-subset.md`, which lives in **Crucible's** repo,
and `axi.py:12` cites it by bare filename with no anchor — the same unanchored cross-project
reference CR-MDB-020 fixes for client paths, here in code. Model B may not edit it, so the
subset Model B honours is recorded on the Model B-owned `contracts/crucible-envelope.md`.

**Where the deployed copy lives, and why not the old path.** CR-MDB-016 §C2 established the
shape: deploy into Model B's store, let the harness resolve from there, repoint every
referencer, hold it with `tests/test_realhome_supersede.py`. This CR reuses it for the scripts
asset class, and the skills name the store path.

One mechanical fact decides this rather than taste: `~/.claude/scripts/` is chezmoi-managed on
this machine, so a file written there by another tool is reverted on the next `chezmoi apply`.
Deploying into that path would give Model B a deployment that silently disappears, presenting
as the tool "randomly reverting". Routing every reference to Model B's own store sidesteps it
and is what detachment means. Chezmoi's claim on the local machine is not Model B's problem to
resolve, and this CR does not try to: it neither writes nor deletes under `~/.claude`, and
takes no position on what the user does with the stale copies.

`~/.claude/scripts/` also holds electronics tooling (`elk_*`, `sch-*`, `skidl_*`,
`layout-clip-probe.*`), EXCLUDED by standing rule (anthill-forge dead), and `gh-run-watch.sh`,
which no Model B surface references. Neither is in scope. The `code-health` skill that consumes
the three `rust-*` tools is adopted by CR-MDB-023, which depends on this CR for the deployed
tool path.

## Scope

### §S1 — Adopt the eight scripts into `scripts/`
The eight land under `scripts/`, the already-force-included asset root, replacing `.gitkeep`.
Each gains a header recording that Model B owns it and which published skills consume it.
Executable bits are preserved. Content is adopted as-is apart from §S2, §S3 and §S5; this is
an ownership move, not a rewrite.

`schedule_db.py` additionally carries a TRANSITIONAL banner: what supersedes it (Crucible
owning workflow plan/state storage), the release that triggers it (their 0.2.0, unreleased),
and the instruction not to extend it.

### §S2 — One TOON codec, owned by Model B
No file in this repo is a copy of a Crucible file. Model B's codec lives in `modelb_axi/` as
the single implementation: `axi.py`'s existing 4-construct encoder gains the decoder the tools
and tests need, and `scripts/toon.py` becomes a thin re-export so a directly-invoked script
still works. No repo file imports `crucible:clients/toon.py`.

`worktree-flow.py`'s `sys.path.insert` + bare `import toon` (`:93`, `:136`) resolves to the
adopted module, as does its `schedule_db` import (`:95`); the existing "unavailable → warn,
queue-only" degrade path is preserved unchanged.

### §S3 — Fix the empty-array defect and pin the round trip
Establish by test which empty-list form the documented subset decodes, and make the encoder
emit it. Every verb that can produce a zero-row table — `status`, `next`, `progress` —
round-trips through Model B's own decoder. `tests/test_worktree_flow_axi.py` drops the
absolute-path insert into the Crucible checkout and decodes with Model B's codec; its three
failures resolve for the right reason — the encoder was wrong, not the oracle.
`contracts/crucible-envelope.md` records the 4-construct subset including the empty-array
form, since a construct that cannot round-trip is not in the subset whatever any document
says. `axi.py`'s citation is anchored `crucible:docs/research/DN-crucible-toon-subset.md`;
Crucible's note is cited, never edited, and no divergence is introduced without raising it on
the #1336 lineage.

### §S4 — Ship them through the installer
`modelb_axi/deploy.py` treats `scripts/` as a deployed asset class under the same sha256
manifest discipline, idempotence and hand-modification skip rule as the skills and hook
scripts, into a store path beside them. `install.toml` records the deployed location.

### §S5 — Name the gate tool and record its contract
`skills-src/model-b/references/orchestration-common.md:63` names `gate-lock.sh` as the
gate-coordination tool implementing the WAIT-FOR-FREE pre-flight it already specifies, and
names its verb and exit-code surface so a track can actually use it.

A new `contracts/gate-lock.md` records the protocol as a cross-project contract: the lock path
derivation (`<git-common-dir>/nai-gate.lock`, `/tmp` fallback), the verb set, the exit codes
(0 acquired, 1 held by another track, 2 resources loaded, 5 timeout), and the division of
ownership — Model B's `gate-lock.sh` is the WAITER and never creates the lock; Crucible's
`rust-crucible.py` is the gate-runner that creates, deletes and reclaims it. The contract
states explicitly that the filename cannot change on one side alone.

The `nai-` prefix is preserved verbatim. Renaming it is a CReq to Crucible, filed as a
follow-up, not an edit in this CR.

### §S6 — Detach every reference from the local machine
The deployed copy in Model B's store is the only path any Model B surface names. No file under
`skills-src/`, `modelb_axi/`, `scripts/`, `contracts/`, `hooks-src/` or `AGENTS.md` may
reference `~/.claude/scripts/<tool>` for any of the eight, and
`tests/test_realhome_supersede.py`'s retired-referencer gate — which already asserts the
absence of the CR-MDB-016-retired `*crucible*` mirrors — is extended to the eight names.

The adopted scripts must be RELOCATABLE: `worktree-flow.py`, `schedule_db.py` and `toon` must
resolve each other from their own deployed directory with no `~/.claude` path on `sys.path`,
so the bundle works wherever the installer puts it.

### §S7 — Gates that keep the slot full
The asset class is asserted non-empty and complete: the eight names are enumerated in a test,
so no future wheel can ship an empty `scripts/`, and a script added without a consuming-skill
reference, or removed while still referenced, fails.

## Acceptance criteria

### §S1
- [ ] All eight files exist under `scripts/` and `scripts/.gitkeep` is gone.
- [ ] Each carries a header naming Model B as owner and listing its consuming skills.
- [ ] Files that were executable are executable in the repo.
- [ ] `scripts/schedule_db.py` carries a TRANSITIONAL banner naming Crucible's ownership of
      workflow plan/state storage as its successor and their 0.2.0 as the trigger, and stating
      that it must not be extended.
- [ ] No Model B document presents Crucible 0.2.0 as released.
- [ ] No module or test added by this CR writes under `~/.claude` or invokes `chezmoi`.

### §S2
- [ ] Exactly one TOON implementation exists in the repo, in `modelb_axi/`, exposing `encode`
      and `decode`.
- [ ] `scripts/toon.py` re-exports it and holds no second implementation — asserted by
      identity of the encode/decode callables, not by line count.
- [ ] Zero `sys.path` inserts naming a path outside this repo under `scripts/`, `modelb_axi/`
      or `tests/`, and zero occurrences of `data_projects/crucible/clients`.
- [ ] The phrase "copy of crucible:" does not appear anywhere in the repo.

### §S3
- [ ] `decode(encode(x)) == x` for an envelope carrying an empty list, asserted directly on
      the codec.
- [ ] `worktree-flow.py status`, `next` and `progress` each emit stdout Model B's decoder
      accepts, including on a project with no ChangeSet DB (the
      `schedule_db unavailable — queue-only project` path).
- [ ] `tests/test_worktree_flow_axi.py` passes all six tests and imports no module from
      outside this repo.
- [ ] `contracts/crucible-envelope.md` states the 4-construct subset and the empty-array form;
      no file in Crucible's repo is modified.
- [ ] No repo file cites `DN-crucible-toon-subset.md` by bare filename — every citation
      carries the `crucible:` anchor.

### §S4
- [ ] `deploy.py` deploys `scripts/` with sha256 manifest comparison; a second run reports
      every file unchanged; a hand-modified destination is SKIPPED unless `--force-managed`.
- [ ] `install.toml` records the deployed scripts location; a dry-run writes nothing.
- [ ] An integration test drives the real installer entry point against a sandboxed
      `--target-root` and then EXECUTES a deployed script (`worktree-flow.py --help`),
      asserting exit 0 — the wire-the-call-path gate for this CR.

### §S5
- [ ] `orchestration-common.md` names `gate-lock.sh`, its seven verbs and its four exit codes;
      the WAIT-FOR-FREE rule it already carries is unchanged in substance.
- [ ] `contracts/gate-lock.md` exists and states the lock path derivation, the verb set, the
      exit codes, and that Model B waits while Crucible's `rust-crucible.py` owns the lock
      file's creation, deletion and stale reclamation.
- [ ] The adopted `gate-lock.sh` computes a lock path byte-identical to the one
      `rust-crucible.py` derives — asserted by comparing the two derivations, not by reading
      one of them.
- [ ] The string `nai-gate.lock` is unchanged in `scripts/gate-lock.sh`, and the contract
      records that a rename requires agreement from both projects.

### §S6
- [ ] Zero occurrences of `~/.claude/scripts/` paired with any of the eight names anywhere
      under `skills-src/`, `modelb_axi/`, `scripts/`, `contracts/`, `hooks-src/`,
      `docs/changes/` or `AGENTS.md`.
- [ ] Every consuming document names the deployed store path, and that path is the one
      `deploy.py` actually writes — asserted by comparing the documented string against the
      deploy target, not by eyeballing both.
- [ ] `tests/test_realhome_supersede.py` asserts no Model B surface references the eight under
      `~/.claude/scripts/`, in the same shape as its existing `*crucible*` mirror gate, and
      remains behind `MODELB_REALHOME_GATE=1`.
- [ ] Relocatability: copied to an arbitrary directory outside the repo,
      `worktree-flow.py --help` exits 0 and resolves `toon`/`schedule_db` from beside itself,
      with no `~/.claude` entry on `sys.path`.
- [ ] No code path added by this CR writes, deletes, moves or rewrites anything under
      `~/.claude`.

### §S7
- [ ] A gate enumerates the eight expected names under `scripts/` and fails on absence, on an
      unlisted addition, and on an empty asset root.
- [ ] The built wheel contains all eight under `modelb_axi/_assets/scripts/` — asserted
      against a built artifact, not the source tree.

## Estimated size

8 scripts adopted, `modelb_axi/axi.py` extended with a decoder, `deploy.py` + `config.py` gain
an asset class, 1 test module fixed and 2 added, 1 real-home gate extended, 7 consuming
documents repointed, `orchestration-common.md` given the tool's name, 1 new contract, 1
existing contract updated. No Crucible file touched.

## Risk

- **The wheel-content AC needs a real build.** CR-MDB-014's VERIFY caught exactly this class
  (assets absent from the wheel while dev-mode tests passed). Assert against a built artifact.
- **`axi.py` gains a decoder it did not have.** It is encode-only by design and three tests
  pin it. The encoder's output must stay byte-identical for every currently-tested input.
- **Do not deploy into `~/.claude/scripts/`.** It is chezmoi-managed, so anything written
  there is reverted on the next `chezmoi apply` — a deployment that vanishes later reads as a
  tool defect and is unfixable from this repo. Deploy to Model B's store and point references
  there.
- **Do not "fix" the lock filename.** It is a shared mutex path with Crucible's rust client; a
  one-sided rename makes both tools believe the gate is free and permits two concurrent heavy
  regressions. Record it, raise it, leave it.
- **Do not invest in `schedule_db.py`.** It is superseded by Crucible 0.2.0 owning workflow
  plan/state. Adopt it, banner it, leave its surface exactly as found; every hour spent
  hardening it is written off on their release. The temptation during GREEN will be to add a
  DB fixture to strengthen a test — refuse it.
- **Shared files with CR-MDB-020.** Both repoint the two memory templates. Because this CR now
  runs FIRST, the edge moved: CR-MDB-020 gained `Depends on: 022` and this CR has no
  dependency on it. 020 must not revert the tooling anchors while fixing client paths.

## Non-goals

- No change to any Crucible file and no import of one.
- No chezmoi operation, and no write or delete under `~/.claude`.
- No rename of the gate lock file (a CReq to Crucible instead).
- No `schedule_db.py` schema, verb, or feature work, and no retirement of it either — the
  retirement is a future CR gated on Crucible 0.2.0 actually shipping.
- No adoption of the electronics tooling (`elk_*`, `sch-*`, `skidl_*`,
  `layout-clip-probe.*`) — excluded by standing rule — nor of `gh-run-watch.sh`, which no
  Model B surface references.
- No adoption of the `code-health` skill bundle — that is CR-MDB-023, which depends on this CR
  for the deployed tool path.
- No rewrite of `worktree-flow.py`'s verb surface or lane logic beyond what §S2/§S3 require.
