# CR-MDB-020 — Anchor every client-path reference on Crucible's published contract; Model B maintains none of their client scripts

**Status:** PENDING
**Type:** maintenance
**Priority:** P1 (blocks release 1.0.0 — 53 shipped references resolve to a path Model B does not own, or to a mirror CR-MDB-016 retired)
**Depends on:** CR-MDB-017 (rewrites the same bundle SKILL.mds for the `--role`/`--cycle` surface), CR-MDB-022 (repoints the same two memory templates for tooling paths, and runs FIRST in the wave) — both edges exist to serialize shared files, not to sequence logic; CR-MDB-036 (§S5's tool contract checks against the harness capability declaration 036 §S1 introduces)
**Labels:** crucible, skills, generator, contract, patch
**Phase:** Wave 5
**Design reference:** **`docs/research/DN-multi-harness-deploy-model.md` §D8 (external tools are orchestrated and verified, never vendored — and never a personal checkout) — the governing design note, user-ruled 2026-09-18** · Sandesh #1358/#1360 (the discovery-manifest contract and Crucible's confirmation of their own then-un-materialised stage, since SHIPPED) · the PUBLISHED manifest, measured at `~/.crucible/crucible-clients.json` 2026-09-18 (`version: "0.2.2"`, SIX keys — `clients`/`version`/`status` plus `config`/`server_config`/`shipped_config`) · CR-MDB-016 (the `~/.claude/scripts` client mirrors were retired) · user directive 2026-08-27 ("Model B will not maintain any client scripts of Crucible — that is the Crucible project's job; Model B only manages and updates the skills with reference to changes in Crucible") · user directive 2026-09-18 (Model B has nothing to do with the local Crucible PROJECT at any layer; only the production server and the published installed clients) · CR-MDB-017 §Risk and §Non-goals, which designated this CR

## Amendments 2026-09-21 (from `audits/2026-09-21-codebase-review-{assets,docs}.md`)

- **§S0's repo-wide AC ("zero occurrences of a personal-checkout client path anywhere in the
  repo outside `archive/`") is unchanged, but the SCOPE and size estimate now name every surface
  it reaches:** `AGENTS.md:106,126-130,148` (teaches `~/Documents/data_projects/crucible` as the
  source of truth and the `/tmp/claude-1000/modelb-crucible` wrapper as the canonical run);
  `contracts/crucible-envelope.md:13-15,26,39-41` and `contracts/gate-lock.md:4-5,38-40` (the
  contracts *mandate* the dev-checkout oracle); `hooks-src/scripts/block-direct-cargo-test:29-31,
  43-44` and `hooks-src/schema.md:54-56` ("the crucible repo `clients/` dir in dev");
  `docs/research/PRD-model-b-rationalization.md:41,65`. The two TEST sites
  (`tests/test_toon_codec.py:99`, `tests/test_tooling_detachment.py:375`) are repointed by
  **CR-MDB-032 §S1** against the same manifest anchor; 020's gate must cover `tests/` so 032
  cannot regress it.
- **Gate exemption, explicit:** `skills-src/CRUCIBLE-HANDOVER.md:9-10` (provenance) and
  `archive/` are the only sanctioned occurrences; the gate whitelists them by path.
- **`crucible_reference` (§S2) and the template bodies' `~/.claude/skills/...` citations are NOT
  this CR's** — CR-MDB-031 §S2 repoints them to `~/.agents/skills/` after 017/020/025 regenerate,
  so the fleet is regenerated once more, last. 020 regenerates for the client-path change only.
- **Open conflict — RESOLVED 2026-09-21 (user ruling):** the LOCKED ontology is now a frozen import at
  `docs/research/DN-model-b-language.md` (origin `a9a8f57`, byte-identical body, provenance header);
  `AGENTS.md`, the PRD and the queue header cite it there. The remaining `crucible:` citations in
  `modelb_axi/scaffold.py:201` and `skills-src/model-b/SKILL.md:12` are CR-MDB-031 §S2's. No CReq
  to Crucible is needed; divergence from origin is raised on the #1336 lineage.

## Context

CR-MDB-017 named this CR twice — at `:182` ("let the CR-MDB-020 anchoring work decide how
the client is located") and in its Non-goals at `:190` — but it was never filed. The
standing directive makes its boundary sharper than "anchor some paths", so the scope below
is written to that boundary rather than to the original one-line placeholder.

**The boundary.** Crucible owns its client scripts absolutely: their content, their
packaging, their installation, and the location they install to. Model B owns the SKILLS
that reference them, and updates those skills when Crucible's surface changes. Model B
therefore never vendors a client, never mirrors one into the harness, never ships a
substitute, and never compensates for a client that is not installed. It cites the
contract and, when the contract is unsatisfied, says so and points at Crucible's installer.

**Two reference forms are shipped today, and both violate that boundary.**

*Form 1 — unanchored relative paths: 41 occurrences across 10 files.* The bundles say
`clients/<stack>-crucible.py` with no root:

| File | Occurrences |
|---|---|
| `skills-src/crucible-report-arduino/SKILL.md` | 8 |
| `skills-src/crucible-report-java/SKILL.md` | 8 |
| `skills-src/crucible-report-bun/SKILL.md` | 7 |
| `skills-src/crucible-report-rust/SKILL.md` | 7 |
| `skills-src/crucible-report-python/SKILL.md` | 6 |
| `skills-src/crucible/references/{arduino,bun,java,python,rust}.md` | 1 each |

These resolve only by accident — inside a Model B project whose `AGENTS.md` happens to bind
a client path. In a global-skill session, or on another machine, they resolve to nothing.
The earlier queue note recorded this as "36 across 5 bundle SKILL.mds"; the measured figure
is **41 across 10 files** — the five `crucible/references/*.md` were missed. This CR is
filed against the measured set.

*Form 2 — references to a retired Model B-maintained mirror: 12 occurrences.*
`generator/stacks/*.toml` still builds its three command strings from
`~/.claude/scripts/<stack>-crucible.py`:

- `arduino.toml:5-7`, `bun.toml:5-7`, `python.toml:5-7`, `quarkus.toml:5-7`
  (`test_command`, `register_command`, `unregister_command`)

and those strings are interpolated into all 16 generated agent definitions under
`generator/agents/`. That mirror was retired by CR-MDB-016 — `test_realhome_supersede.py`
asserts its absence — so every generated agent instructs a path that does not exist. It is
also precisely the arrangement the directive forbids: a Model B-maintained copy of a
Crucible client. Two further occurrences sit in
`skills-src/memory-templates/{java,rust}-orchestration.md`.

**The anchor — RE-MEASURED 2026-09-18, and it is now REAL rather than aspirational.** Crucible
confirmed (#1360) the contract is `<target-dir>/clients/<stack>-crucible.py`, default
`~/.crucible/clients/`, discovered through `crucible-clients.json`, and that Model B should
anchor on the manifest's `clients` values. At authoring time no install stage materialised that
directory. **It does now:** `~/.crucible/crucible-clients.json` exists (`version: "0.2.2"`) and
all five clients are present at `~/.crucible/clients/`, with the manifest carrying six keys
(the three original plus `config`, `server_config`, `shipped_config` — CR-CRU-143). So this CR
no longer documents a location that does not exist; it documents one an agent can run today.

**§S0 — the measured defect that makes this CR P1 rather than hygiene (user directive,
2026-09-18).** `skills-src/crucible/SKILL.md:51` currently instructs agents to invoke clients
from a PERSONAL CHECKOUT of the Crucible project (`~/Documents/data_projects/crucible/clients/`).
That is not merely unanchored — it is actively harmful, proven by this orchestrator hitting it:
such a checkout carries its own operator `crucible.toml` declaring a DEVELOPMENT board, and
`_crucible_axi.py` resolves config `project → install → shipped`, deriving "install" from the
client file's own location. A client invoked from that checkout therefore binds to the
development board while its envelope still prints the project key, so **following our own
published skill silently routes a project's workflow writes to the wrong server.** The user
ruled the boundary explicitly: Model B has nothing to do with the local Crucible project at any
layer — not its dev server, not the client scripts inside it, not its docs — and the only
sanctioned surfaces are the production server and the PUBLISHED, INSTALLED clients under
`~/.crucible/clients/`. Every reference this CR repoints must land there, and no Model B doc may
name a personal-checkout path for any stack.

Under the directive, nothing about the upstream install is Model B's to paper over in prose.
The skills state the contract and name `crucible-axi install` as the way to satisfy it. They
do not document a packaged-copy path, a site-packages path, or any Model B-provided
substitute: a site-packages location is Crucible's internal resolution detail that moves
with the interpreter, and documenting it would teach agents to reach inside another
project's installation.

`archive/wave2/` and `archive/wave3/` carry the same retired strings in 44 places. Archive
is immutable history and is out of scope; the §S4 gate is scoped to exclude it.

## Scope

### §S1 — Anchor the six bundles and the five stack references
Every `clients/<stack>-crucible.py` occurrence across the 10 files above becomes a rooted
reference to Crucible's contract location — `~/.crucible/clients/<stack>-crucible.py` as the
default instance of `<target-dir>/clients/`, identified as Crucible's published contract and
discoverable from `crucible-clients.json`. Each bundle states once, near its first client
invocation, that the client is installed by `crucible-axi install [--target-dir <dir>]` and
is not shipped by Model B.

The vscode bundle is included if it carries the form; it has no live client, and its
documented surface must still name the contract rather than a bare relative path.

`skills-src/memory-templates/java-testing-practices.md` names the same Crucible development
checkout (`~/Documents/data_projects/crucible/clients/mvn-crucible.py`) and is anchored the same
way. Model B consumes Crucible's RELEASED client only (PRD, installer-orchestration boundary,
2026-09-23).

### §S2 — Retire the mirror from the generator inputs
`generator/stacks/*.toml`: `test_command`, `register_command` and `unregister_command` for
all four stacks resolve to Crucible's contract location instead of
`~/.claude/scripts/<stack>-crucible.py`. `crucible_reference` continues to point at the
Model B-owned skill under the deployed skill store — that is a Model B artifact and is not
affected by this boundary.

`skills-src/memory-templates/{java,rust}-orchestration.md`: the same two occurrences.

### §S3 — Regenerate and prove determinism
Regenerate all 16 agent definitions with `python3 generator/build.py build`, then prove
`python3 generator/build.py --check` is clean. No generated file is hand-edited.

### §S4 — The gate that keeps it anchored
A stdlib `unittest` gate asserting, over `skills-src/` and `generator/` and excluding
`archive/`: zero `~/.claude/scripts/*-crucible.py` references, and zero unrooted
`clients/<stack>-crucible.py` references. The gate names the permitted anchored form so a
future edit that regresses either way fails.

### §S5 — Contract tests against the released client and the target harness
Every gate above checks Model B's text against a snapshot Model B wrote. This section checks it
against the things the text instructs, so a Crucible release or a harness change surfaces as a
failing test that names the line, rather than as an agent that cannot register.

- **Client contract.** Every Crucible client invocation (`<stack>-crucible.py <verb> [flags]`)
  under `generator/templates/`, `generator/stacks/`, `skills-src/` and `contracts/` is checked
  against the RELEASED client: `~/.crucible/clients/<stack>-crucible.py <verb> --help` must
  list the verb and every flag used. When the released client is absent the test SKIPS,
  naming the missing file; it never passes vacuously. The existing hermetic guards are
  unchanged — this lives in its own module.
- **Tool contract.** Every tool name those same surfaces instruct an agent or orchestrator to
  call must be a tool the target harness has, per the capability declaration of CR-MDB-036 §S1.
  A skill written for one harness's tool set is exactly how `TaskUpdate` and the `sandesh_*`
  MCP verbs reached a harness that has neither.

## Acceptance criteria

### §S1
- [ ] Zero occurrences of an unrooted `clients/<stack>-crucible.py` under `skills-src/`.
- [ ] All five per-stack bundles and all five `skills-src/crucible/references/*.md` name the
      anchored contract location, with `~/.crucible/clients/` given as the default instance
      of `<target-dir>/clients/`.
- [ ] Each of the five per-stack bundles states that the client is installed by
      `crucible-axi install` and is not shipped, vendored, or maintained by Model B.
- [ ] No file under `skills-src/` documents a site-packages path, a
      `crucible_axi/clients` package-internal path, or any Model B-provided client copy.
- [ ] No file under `skills-src/` instructs the reader to copy, mirror, patch, or edit a
      Crucible client.
- [ ] **§S0 — zero occurrences of a PERSONAL-CHECKOUT client path anywhere in the repo outside
      `archive/`**: no `~/Documents/data_projects/crucible/`, no `$HOME`-relative or
      absolute path into a Crucible source checkout, for any stack. `skills-src/crucible/SKILL.md:51`
      specifically names `~/.crucible/clients/<stack>-crucible.py` (the installed, published
      location) instead.
- [ ] §S0 — the bundles state WHY, in one sentence an agent can act on: a Crucible source
      checkout carries its own `crucible.toml`, and because a client resolves config
      `project → install → shipped` with "install" derived from the client file's own location,
      running a client out of a checkout binds it to that checkout's board — so a run can post
      to a development server while reporting the right project key.
- [ ] §S0 — no Model B doc names the Crucible development server, and none instructs reading
      Crucible's own repository (source, clients, or docs) for any purpose; the sanctioned
      surfaces are the production server and the installed clients.

- [ ] `skills-src/memory-templates/java-testing-practices.md` carries no Crucible
      development-checkout path; it names the released client.

### §S2 / §S3
- [ ] Zero occurrences of `~/.claude/scripts/` paired with `-crucible.py` under
      `generator/` and `skills-src/`.
- [ ] All four `generator/stacks/*.toml` resolve their three command strings to the anchored
      contract location; `crucible_reference` still names the Model B-owned skill path.
- [ ] All 16 files under `generator/agents/` carry the anchored form, and
      `python3 generator/build.py --check` exits 0 with no drift reported.
- [ ] `skills-src/memory-templates/{java,rust}-orchestration.md` carry no retired-mirror
      reference.

### §S4
- [ ] A stdlib `unittest` gate fails on a fixture carrying `~/.claude/scripts/rust-crucible.py`
      and on a fixture carrying an unrooted `clients/rust-crucible.py`, and passes on the
      anchored form.
- [ ] The gate excludes `archive/` explicitly and asserts that exclusion, so archived
      history is never rewritten to satisfy it.

### §S5
- [ ] Every client invocation in the four named trees is checked against the released
      client's `<verb> --help`; a fixture using a flag the client lacks fails naming the file,
      line and flag; with no released client installed the module SKIPS with the missing path
      in its reason.
- [ ] Every tool name those trees instruct is checked against CR-MDB-036's declaration for the
      target harness; a fixture instructing `TaskUpdate` fails for Pi, and one instructing
      `todo` passes.

## Estimated size

10 documentation files, 4 stack TOMLs, 2 memory templates, 16 regenerated agent definitions,
1 test gate added. No `modelb_axi/` change.

## Risk

- **File overlap with CR-MDB-017.** Both CRs rewrite the same five per-stack bundle
  SKILL.mds. The `Depends on: 017` edge exists solely to serialize them; do not run them
  concurrently even though this is a solo project with no worktree contention.
- **Upstream reality still lags the contract.** After this CR the skills will name a path
  that does not exist on any current install until Crucible's materialisation fix ships.
  That is the honest state and the intended outcome of the directive — the alternative is
  Model B documenting a workaround for another project's unshipped stage. Re-check at
  gap-analysis whether their fix has landed.
- The 16 regenerated agent definitions also carry the retired `--phase` flag, which is
  CR-MDB-017's subject. Running 017 first means one regeneration settles both; running this
  CR first would require a second regeneration.

## Non-goals

- No change to any Crucible client script, and no vendoring, mirroring, or packaging of one.
- No installer or `install.toml` change — the `[install].clients_dir` capture the ambient
  hook consumes is CR-MDB-018's, and this CR does not depend on it.
- No rewrite of `archive/`.
- No `--phase` → `--role` verb work (CR-MDB-017).
