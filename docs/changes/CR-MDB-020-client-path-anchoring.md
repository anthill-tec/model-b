# CR-MDB-020 — Anchor every Crucible client reference on the installed, published clients, and check the text against the released client

**Status:** PENDING (filed 2026-09-16; amended 2026-09-21 and 2026-09-23; rewritten at its
gap-analysis 2026-09-24 — earlier text is git history and is not to be consulted for contracts)
**Type:** maintenance
**Priority:** P1 — in release 1.0.0, wave 2. The published skills tell agents to run Crucible clients
from a personal checkout of the Crucible project, which binds a run to that checkout's development
board while it reports the right project key.
**Depends on:** CR-MDB-017, CR-MDB-022, CR-MDB-025 (took the generator half, §S8), CR-MDB-036 — all
merged
**Labels:** crucible, skills, hooks, contract, maintenance
**Design reference:** `docs/research/DN-multi-harness-deploy-model.md` §D8 (external tools are
orchestrated and verified, never vendored, never a personal checkout) and §D18 (skills name
capabilities and CLIs, never a harness's tools; this CR's tool contract keeps harness names from
returning, CR-MDB-031 applies the rule) · Crucible's published manifest
`~/.crucible/crucible-clients.json` (0.2.2; `clients` maps each stack to
`~/.crucible/clients/<stack>-crucible.py`) · user directives 2026-08-27 (Model B maintains none of
Crucible's client scripts) and 2026-09-18 (only the production server and the installed clients)

## Context — measured 2026-09-24 on `develop` at `33fecfc`

The anchor exists: `~/.crucible/clients/` holds all five clients, the manifest names them, and
pre-flight (CR-MDB-036) and the ambient hook (CR-MDB-018) already resolve through it. What remains is
the text:

| Defect | Where (measured) |
|---|---|
| **Personal-checkout client paths** (`~/Documents/data_projects/crucible/clients/…`) | `skills-src/crucible/SKILL.md:65`; `skills-src/crucible/references/{arduino,bun,java,python,rust}.md` (one each); `skills-src/memory-templates/java-testing-practices.md:730`; `AGENTS.md:106` (the `crucible:` path prefix called "the source of truth") and `:129` (the canonical run command) |
| **Unrooted `clients/<stack>-crucible.py`** | 36, in the five `crucible-report-*` bundles (arduino 8, java 8, bun 7, rust 7, python 6) |
| **The retired `~/.claude/scripts/` mirror** | `skills-src/memory-templates/java-orchestration.md:16`, `rust-orchestration.md:10` |
| **Stale discovery wording in the block reasons agents read** | `hooks-src/scripts/block-direct-cargo-test:14,32-33,48` and `block-direct-mvn-test:15,37` ("installed location per install config; the crucible repo `clients/` dir in dev") |
| **A reviewer sentence CR-MDB-036 §S9 made false** | `skills-src/memory-templates/java-orchestration.md:60` names the `reviewer-quarkus`, `reviewer-architecture` and `reviewer-security` skills, which Model B does not ship |

Already clean, measured: `docs/research/` apart from one verbatim record (below), `generator/`
(CR-MDB-025 §S8), no reference to the development server's port. Not clean, found by RED
2026-09-24: `contracts/gate-lock.md:5,31,77` cite the client unrooted (`crucible:clients/…`,
`clients/rust-crucible.py::…`) and are rooted here. Sanctioned and exempt: the provenance line in
`skills-src/CRUCIBLE-HANDOVER.md`; `docs/research/crucible-clients-skills-guard.test.ts`, a verbatim
secured record of Crucible's guard suite (a historical artifact, not instructions; orchestrator
ruling 2026-09-24); `archive/`; and the dated records in `audits/` and `docs/changes/`.
`tests/` still names the checkout in several modules; CR-MDB-032 §S1 repoints them and then extends
this CR's gate to `tests/`.

**The tool contract cannot start at zero.** `skills-src/` still names harness tools (for example
`TaskUpdate`, `EnterWorktree`, `sandesh_fetch`) that CR-MDB-031 removes, and 031's acceptance names
this CR's contract as its gate. So the contract here records today's occurrences as a baseline that
may only shrink; 031 drains it to zero without adding exemptions.

## Scope

### §S1 — Every client reference names the installed client
Each defect row above resolves to `~/.crucible/clients/<stack>-crucible.py`, described once per
bundle as the default location of Crucible's installed clients, named by `crucible-clients.json`,
installed by Crucible's own installer, and not shipped, vendored or maintained by Model B. The
`crucible` skill states why a checkout is never used: a checkout carries its own `crucible.toml`,
and a client resolves its configuration from its own location, so a run from a checkout posts to
that checkout's board while reporting the right project key. `AGENTS.md` drops the `crucible:` path
prefix and runs the client from `~/.crucible/clients/`. The two `block-direct-*` hooks name the
manifest-listed client in their block reasons and docstrings. The quarkus reviewer sentence names
only skills Model B ships.

### §S2 — The anchoring gate
A stdlib `unittest` gate over `skills-src/`, `generator/`, `hooks-src/`, `contracts/`, `modelb_axi/`,
`scripts/`, `docs/research/`, `docs/install-guide.md`, `README.md` and `AGENTS.md`: zero personal-
checkout Crucible paths, zero unrooted `clients/<stack>-crucible.py`, zero
`~/.claude/scripts/*-crucible.py`. The exemptions (the handover provenance line; the verbatim
`docs/research/crucible-clients-skills-guard.test.ts`; `archive/`, `audits/`, `docs/changes/`,
`tests/`) are listed in the gate and asserted, so none widens silently.

### §S3 — Client contract against the released client
Every Crucible client invocation (`<stack>-crucible.py <verb> [--flags]`) under `skills-src/`,
`generator/templates/`, `generator/stacks/` and `contracts/` is checked against
`~/.crucible/clients/<stack>-crucible.py <verb> --help`: the verb exists and every flag used is
listed. A mismatch fails naming file, line, verb and flag. With the released client absent the
module skips, naming the missing path. Placeholders (`<…>`, `{…}`) are not flags.

### §S4 — Tool contract, as a ratchet
A declared vocabulary of harness-specific tool names — Claude Code's (`TaskList`, `TaskUpdate`,
`TaskStop`, `EnterWorktree`, `ExitWorktree`, `run_in_background`, the `sandesh_*` MCP verbs, and the
like) and Pi's (`modelb_axi.agents.PI_TOOL_NAMES`) — is scanned over `skills-src/`. Today's
occurrences are recorded as a baseline (file → count); the gate fails when any count rises or a new
file appears, and names the file and tool. Separately, every tool an agent definition template under
`generator/` lists for Pi must be a key of `PI_TOOL_NAMES`.

## Acceptance criteria

### §S1
- [ ] Zero personal-checkout Crucible paths and zero unrooted `clients/<stack>-crucible.py` in the
      gated trees; each `crucible-report-*` bundle and each `crucible/references/*.md` names
      `~/.crucible/clients/<stack>-crucible.py`.
- [ ] Each of the five `crucible-report-*` bundles states once that the client is installed by
      Crucible's installer, listed in `crucible-clients.json`, and not shipped or maintained by Model B.
- [ ] `skills-src/crucible/SKILL.md` states the checkout rule and its reason in one actionable
      sentence (own `crucible.toml`; configuration resolved from the client's location; a run posts
      to the checkout's board while reporting the right project key).
- [ ] No file in the gated trees documents a site-packages or package-internal client path, a Model B
      copy of a client, or an instruction to copy, patch or edit a Crucible client.
- [ ] `AGENTS.md` has no `crucible:` path prefix to a checkout, and its canonical run command uses
      `~/.crucible/clients/python-crucible.py`.
- [ ] Both `block-direct-*` hooks' block reasons and docstrings name the client listed in Crucible's
      manifest and no "install config" or "crucible repo `clients/` dir"; their block/allow
      behaviour is unchanged (existing hook tests pass).
- [ ] `java-orchestration.md` names no `reviewer-*` skill.

### §S2
- [ ] The gate fails on fixtures carrying `~/Documents/data_projects/crucible/clients/rust-crucible.py`,
      an unrooted `clients/rust-crucible.py`, and `~/.claude/scripts/rust-crucible.py`, and passes on
      `~/.crucible/clients/rust-crucible.py`.
- [ ] Its exemption list is exact and asserted.

### §S3
- [ ] The client contract runs over the four trees; a fixture using a flag the client lacks fails
      naming file, line and flag; a fixture using an unknown verb fails; with no released client the
      module skips with the missing path in its reason. It never passes vacuously (it asserts it
      found invocations).
- [ ] It passes against the installed 0.2.2 clients, or every mismatch it finds is fixed in this CR.

### §S4
- [ ] The baseline is committed with this CR; a fixture adding `TaskUpdate` to a bundle fails naming
      the file and tool; lowering a count passes.
- [ ] Every Pi tool listed by a `generator/` agent template is a `PI_TOOL_NAMES` key; a fixture
      listing an unknown tool fails.

## Risk

- **Imported bundles.** The `crucible-report-*` and `crucible-register` bundles were imported from
  Crucible; Model B owns their content since the handover (`CRUCIBLE-HANDOVER.md`), and the origin
  tree is gone, so no byte-identity check can run. Edits here are Model B's doc-sync of that content.
- **The client contract reads the real installed clients.** It runs only `--help` and skips when
  they are absent; it never runs a mutating verb.
- **The ratchet is a baseline, not a pass.** It prevents regression now; CR-MDB-031 is what takes it
  to zero.

## Non-goals

- No change to any Crucible client, and no vendoring, mirroring or packaging of one.
- No generator change (CR-MDB-025 §S8 did it) and no regeneration.
- No `tests/` repoint (CR-MDB-032 §S1, which extends the §S2 gate to `tests/`).
- No removal of harness tool names from the skills (CR-MDB-031), and no `~/.claude/skills/…` citation
  repoint (CR-MDB-031 §S2).
- The roundhouse root's own `AGENTS.md` checkout reference belongs to a root CR-RND, not this layer.
- No rewrite of `archive/`, `audits/` or closed CR records.
