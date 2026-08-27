# CR-MDB-022 — Tooling adoption: eight workflow scripts into the repo, one Model B-owned TOON codec, every reference detached from the local machine

**Status:** PENDING
**Type:** feature
**Priority:** P0 — **the FIRST CR of Wave 5**, implemented before 017/018/019/020/021/023 (user directive: detaching from the local development machine's environment is the precondition for the rest of the wave; while it is outstanding, published skills instruct tooling this repo does not contain and the wheel ships an empty asset slot for it)
**Depends on:** —
**Labels:** tooling, installer, axi, toon, ownership, detachment, feature
**Phase:** Wave 5
**Design reference:** user directives 2026-08-27 — (a) "all Model B scripts are owned inside the model-b subproject and repo-managed here; the same-named scripts in the Claude global directories are NOT managed by Model B", (b) "we are detaching from the local development machine's environment; any reference to these scripts should be for using them from our owned `scripts/` folder under Model B; we bundle these along with the skills we manage for release, thus publishing and overwriting the local machine environment — that is the pattern; chezmoi ownership on the local machine is not our problem", (c) "`code-health` and `gate-lock`: adopt those", (d) "`schedule_db.py` was a transitional workflow planning and scheduling DB, superseded by Crucible when its 0.2.0 is released — Crucible will own storing the workflow plan and state; this approach will be deprecated" · **PRD §D9** (`scripts/` is a permanent workspace directory of this repo; the single-source repo-local rule; AC gates assert repo paths, never deployed paths) · **PRD §D10** (the installer deploys the user-local file classes — "global memory (language refs), hook scripts, **scripts/wrappers**, skill bundles"; the scaffold stays project-specific) · `CR-MDB-014:23` (wired `scripts` into the package data as an asset root; never populated it) · CR-MDB-015 §S6 (the `.agents/hooks/scripts` deploy precedent this CR follows) · CR-MDB-016 §C2 (the store-authoritative deploy + supersede pattern) · CR-MDB-010 (the worktree-flow AXI envelope) · **the OFFICIAL TOON spec** (toonformat.dev / github.com/toon-format) — the wire contract, with `crucible:clients/toon.py` as Crucible's spec-conformant port used only as an out-of-process oracle · `crucible:docs/research/DN-crucible-toon-subset.md` — **RETIRED pointer document** (their CR-CRU-046, 2026-08-01); cited for lineage only, never as a live contract, never edited · `contracts/crucible-envelope.md` (the Model B-owned surface recording what Model B emits)

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

**This is an unimplemented PRD requirement, not a new concept** (established at gap-analysis,
2026-08-27). PRD §D9 lists `scripts/` among the permanent workspace directories of this repo,
and §D10's installer-vs-scaffold split names the installer's user-local file classes
explicitly: "global memory (language refs), hook scripts, **scripts/wrappers**, skill
bundles". CR-MDB-014 acted on it halfway — its §S2 wired `scripts` into the package data as an
asset root (`CR-MDB-014:23`) — and nothing ever populated it. So the slot is UNFINISHED, not
vestigial: no Dimension-5 retire/delete judgement is involved, and this CR closes a gap the
design contract has carried since Wave 3.

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

The failure is the collision, and its shape was mis-stated until C2 RED measured it — see §S3
for the correction and the evidence. In short: the 254-line encoder emits a NON-EMPTY list
header with bare indented items (`warnings[1]:` then `    schedule_db unavailable — queue-only
project`) which Crucible's port rejects at `clients/toon.py:1243`, because it counts an item
line only when it begins with `- `. Empty headers like `rows[0]:`/`help[0]:` are VALID and are
not the defect. Three of the six tests in `tests/test_worktree_flow_axi.py` fail on the
non-empty case and are part of the recorded 7-failure baseline; `status`, whose envelope is
entirely empty headers, has always decoded cleanly. The defect stayed latent because the tool
lived outside the repo, where no gate ever ran against it. A script that self-describes as a
copy of a Crucible file also cannot be adopted as Model B's own without contradicting the
standing no-client-maintenance directive.

**The governing document is RETIRED, which changes what "conformance" means here.**
`modelb_axi/axi.py:10-12` claims wire-compatibility with a "pinned 4-construct TOON subset"
declared in `DN-crucible-toon-subset.md`. That document was retired by Crucible's CR-CRU-046
(2026-08-01) and now says only that Crucible speaks TOON per the OFFICIAL spec
(toonformat.dev / github.com/toon-format), with `clients/toon.py` as their spec-conformant
port. So there is no private subset to honour, no bespoke contract to mirror, and `axi.py`'s
claim is stale. Model B does not implement the spec — it emits a documented valid SUBSET and
proves conformance by round-tripping through their port out of process. §S3 carries the
decision.

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

### §S3 — Fix the real wire defect and pin the round trip
**Corrected 2026-08-27 at C2 RED, against measured evidence. The diagnosis this section
originally carried was wrong and is retained nowhere.** What was claimed: empty list headers
`rows[0]:`/`help[0]:` are refused. What is true: they are VALID. `worktree-flow.py status`
emits `lanes[0]:`, `warnings[0]:` and `help[0]:` and decodes cleanly against Crucible's
spec-conformant port. `key: []` is the canonical empty form and `key[0]:` is also accepted;
only `key[0]: []` is rejected. The original error message pointed at a line number that was
read as the empty header and was in fact the line below it.

**The real defect is a NON-EMPTY list header followed by BARE indented items.**
`worktree-flow.py` emits `  warnings[1]:` then `    schedule_db unavailable — queue-only
project`. `crucible:clients/toon.py:1243` counts a line as an item only when it starts with
`- ` or equals `-`, so bare items yield zero recognized items against a declared count of
one: `Expected 1 list-form items, but got 0`. Measured at `next` line 8 and `progress`
line 7 — always the `[1]` header, never a `[0]` header.

Two wire forms are accepted and either fixes it: **INLINE** — `warnings[1]: <text>`, which is
what their encoder itself emits and is therefore the canonical choice — or **hyphenated
list-form**, `warnings[1]:` followed by `    - <text>`. Inline carries one rule that must be
preserved: an item containing `,`, `:`, `[` or `]` is JSON-quoted. A plain em dash is not
quoted.

**The governing document is not what this CR first assumed.**
`crucible:docs/research/DN-crucible-toon-subset.md` is **RETIRED** (their CR-CRU-046,
2026-08-01) and survives only as a pointer: "Crucible speaks TOON per the OFFICIAL spec —
toonformat.dev / the toon-format GitHub org. The spec, not this document, is the wire"
contract, with `clients/toon.py` as their spec-conformant port validated by a round-trip
oracle against the official library. There is therefore **no private 4-construct subset to
record**, and `modelb_axi/axi.py:10-12`'s claim of wire-compatibility with a "pinned
4-construct TOON subset" is stale.

**Conformance stance (decided here, deliberately conservative).** Model B does NOT implement
the TOON spec — an 8-language official ecosystem already does. Model B's encoder emits a
documented, valid SUBSET of TOON, and its decoder accepts what Model B's own tools emit.
Conformance is PROVEN, not asserted: the encoder's output is round-tripped through Crucible's
spec-conformant port **out of process** (subprocess only — never an import, per §S2), so the
oracle is real without forking their code into ours.

Deliverables: every verb that can emit a list — `status`, `next`, `progress` — round-trips
through Model B's own decoder, including on a project with no ChangeSet DB (the
`schedule_db unavailable — queue-only project` path, which is where the defect lives).
`tests/test_worktree_flow_axi.py` decodes with Model B's codec and imports nothing from
outside the repo. `contracts/crucible-envelope.md` records the subset Model B emits, names
the OFFICIAL spec as the wire contract, and marks the DN as a retired pointer. `axi.py`'s
stale subset claim is corrected. No Crucible file is edited, and any divergence found in
their port is raised on the #1336 lineage rather than forked.

### §S4 — Ship them through the installer
`modelb_axi/deploy.py` treats `scripts/` as a deployed asset class under the same sha256
manifest discipline, idempotence and hand-modification skip rule as the skills and hook
scripts. The shape is EXTENDED from the existing hook-scripts path, not invented: `deploy.py`
already carries `STORE_RELDIR = .agents/skills` and
`HOOKS_SCRIPTS_STORE_RELDIR = .agents/hooks/scripts` (CR-MDB-015 §S6), with `_hook_scripts()`
enumerating a flat asset directory. This CR adds the analogous constant
`.agents/scripts` and a `_tool_scripts()` enumerator beside them.

**The tooling deploys ONCE user-scope with NO per-harness symlink**, following the hook
scripts rather than the skill bundles: `HARNESS_SKILL_DIRS` exists because a harness must
discover skills in its own directory, whereas a script is invoked by the path a skill names.
Adding scripts to the symlink map would create harness-specific tool paths and defeat the
detachment.

`install.toml` records the deployed location as a `[install]` STRING key —
`config.py::_toml_value` serializes only strings and lists of strings by design, so anything
richer is out of contract. CR-MDB-018 later adds `clients_dir` to the same table; the keys are
disjoint and the two CRs do not conflict.

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
- [ ] Zero `sys.path` inserts naming a path outside this repo under `scripts/`,
      `modelb_axi/` or `tests/`, and no repo file IMPORTS a Python module from Crucible's
      checkout (no `import toon` / `import _crucible_axi` resolved outside this repo).
- [ ] **Sanctioned exception, asserted as permitted rather than forbidden:** INVOKING
      Crucible's client as a subprocess from `~/Documents/data_projects/crucible/clients/`
      remains correct and must not be swept. Model B dogfoods Crucible as a consumer and
      this machine drives Crucible's DEV server, so the checkout — not the installed
      `crucible-axi` package and not any local script store — is the live client source.
      The gate distinguishes IMPORT (forbidden: it forks another project's code into our
      process) from INVOCATION (required: it is how a consumer uses their tool).
- [ ] The phrase "copy of crucible:" does not appear anywhere in the repo.

### §S3
- [ ] `decode(encode(x)) == x` on Model B's codec for: an envelope with an EMPTY list, one
      with a NON-EMPTY scalar list, a populated uniform table, and a scalar-only envelope.
- [ ] The non-empty scalar list is emitted in a form Crucible's spec-conformant port
      accepts, proven by round-tripping the output through that port **as a subprocess**;
      the inline form preserves JSON-quoting for items containing `,`, `:`, `[` or `]`.
- [ ] Empty list headers are left ALONE — `status`, whose envelope is entirely `[0]` headers,
      decodes both before and after this cycle. A change there would be churn, not a fix.
- [ ] `worktree-flow.py status`, `next` and `progress` each emit stdout Model B's decoder
      accepts, on a project with no ChangeSet DB.
- [ ] `tests/test_worktree_flow_axi.py` passes all six tests and imports no module from
      outside this repo.
- [ ] `contracts/crucible-envelope.md` names the official TOON spec (toonformat.dev /
      github.com/toon-format) as the wire contract, records the subset Model B emits, and
      records that `DN-crucible-toon-subset.md` is a RETIRED pointer document (their
      CR-CRU-046) — not a live contract.
- [ ] No repo file treats the retired DN as the wire contract; `modelb_axi/axi.py`'s
      "pinned 4-construct TOON subset" claim is gone.
- [ ] No file in Crucible's repo is modified.

### §S4
- [ ] `deploy.py` deploys `scripts/` with sha256 manifest comparison; a second run reports
      every file unchanged; a hand-modified destination is SKIPPED unless `--force-managed`.
- [ ] The store path is `.agents/scripts`, declared as a module-level constant beside
      `STORE_RELDIR` and `HOOKS_SCRIPTS_STORE_RELDIR` — not a string literal at a call site.
- [ ] `HARNESS_SKILL_DIRS` is UNCHANGED: no per-harness symlink is created for the scripts
      asset class, asserted negatively.
- [ ] `install.toml` records the deployed scripts location as a string key under `[install]`;
      a dry-run writes nothing; a failed deploy leaves no `install.toml`.
- [ ] An integration test drives the real installer entry point against a sandboxed
      `--target-root` and then EXECUTES a deployed script (`worktree-flow.py --help`),
      asserting exit 0 — the wire-the-call-path gate for this CR.
- [ ] **Test-boundary rule (PRD §D9):** AC gates assert REPO paths, never real deployed
      paths. Deployment behaviour is proven against a sandboxed `--target-root`; the only
      real-home assertion permitted is the existing `MODELB_REALHOME_GATE=1`-gated module.
      No test in this CR reads or writes the real `~/.claude` outside that gate.

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
