# CR-MDB-035 — Reconcile the PRD with the shipped tree: success criteria, invariants and design sections

**Status:** PENDING
**Type:** design-reconciliation
**Priority:** P1 — the PRD's invariants and one criterion contradict merged CRs, so the design
contract and the queue disagree about what the design is.
**Depends on:** CR-MDB-021 (criterion 6), CR-MDB-025 + CR-MDB-031 (criterion 4; the CLAUDE.md,
chezmoi and roster sites)
**Labels:** prd, verification, docs
**Phase:** Wave 5 (repo queue, historical) · release 1.0.0 wave 2
**Origin:** the only genuinely unbuilt part of the voided CR-MDB-012 (§S1). A release is a
boundary event and cannot be a CR — but *re-measuring the design contract against the tree it
was written for* is ordinary work.

## Context

`docs/research/PRD-model-b-rationalization.md` was written before most of the tree existed.
Since then DN-multi-harness §D14 dropped every harness but Pi, §D17 moved agent definitions to
per-project rendering, and CR-MDB-021/-025/-031 merged. Measured on 2026-09-25 at develop
`b237b63` (suite 1138 OK):

| # | §4 criterion | Measured | Verdict |
|---|---|---|---|
| 1 | always-loaded context 621 → ≤100 lines, one file | the 621 lines were `~/.claude/AGENTS.md`, a user dotfile Model B no longer writes (D9, §D14). Model B's always-loaded file is the scaffolded project `AGENTS.md`: **38** lines (python+rust, solo), **47** (all five stacks, `multi:3`). No gate. | holds, **measured against the wrong file** |
| 2 | zero banned references outside `archive/` | `python3 -m unittest tests.test_client_verb_sweep` → 24 OK | holds |
| 3 | "`memory/` = the D5 reference library exactly; every skill/agent reference resolves" | no `memory/`; the library is `skills-src/memory-templates/` (8 files), scaffolded per stack into `docs/memory/`. Every `~/.agents/skills/…` citation in `skills-src/` and `generator/templates/` resolves to a shipped file — **no gate asserts it**. | stale wording, ungated |
| 4 | "`build.py --check` idempotent; 16 agents generated, 13 bespoke intact" | `--check` clean; **20** generated (5 stacks × 4 roles, CR-MDB-024); definitions are rendered per project (§D17); a re-render skips a hand-modified file and never writes an unmarked one (`test_pi_agent_definitions` `test_s6_ownership_*`). | counts stale |
| 5 | every client smoke-passes; "closes only when Crucible ships" | Crucible 0.2.2 released; five clients (arduino, bun, mvn, python, rust) in `~/.crucible/crucible-clients.json`. `vscode-crucible.py` was **declined** (D7, Sandesh #1370). Model B's half is gated by `test_client_path_anchoring.ClientContractS3Test`. | needs restating |
| 6 | "`chezmoi diff` clean after every wave; deleted files stay deleted after fresh `apply`" | contradicts CR-MDB-021. Its intended replacement is **false today**: installing `--stacks python,rust` then reinstalling `--stacks python` leaves `crucible-report-rust` deployed while `install.toml` stops recording it. | contradicts a merged CR; replacement unmet → **CR-MDB-040** |

The same defect sits outside §4. §3 invariant 1, D1 and D10.4 require a `CLAUDE.md` symlink that
CR-MDB-031 removed; D2, D4 and D9 describe the retired chezmoi bundle, per-harness skill links and
a `plans/` directory that does not exist; D10(e) lists four harnesses and D10.7 names
`.claude/settings.json`. A design contract that disagrees with the queue is worse than a missing
one, because both surfaces look authoritative.

## Scope

### §S1 — §4 success criteria, rewritten
§4 becomes exactly the six criteria below. Each carries a dated amendment note naming the CR/DN
that moved it, and a **Check:** naming the executable check that measures it — so a criterion is
re-measurable at any time instead of carrying a result that rots. Measured outputs belong in the
merge note, not the PRD.

1. **Always-loaded context.** The project `AGENTS.md` that `init` scaffolds is ≤100 lines for any
   stack set and orchestration mode. *Amended 2026-09-25 (CR-MDB-035): the 621-line baseline was
   the pre-rationalization `~/.claude/AGENTS.md`, a user dotfile Model B no longer writes (D9,
   DN-multi-harness §D14, CR-MDB-031).* **Check:** `tests/test_prd_criteria.py`.
2. *(unchanged text)* **Check:** `tests/test_client_verb_sweep.py`.
3. **Reference library.** The D5 library is `skills-src/memory-templates/`, scaffolded per stack
   into `<project>/docs/memory/`; every `~/.agents/skills/<path>` citation in `skills-src/` and
   `generator/templates/` resolves to a file under `skills-src/`. *Amended 2026-09-25 (CR-MDB-035,
   after the D5 amendment of 2026-09-21): there is no `memory/` tier.* **Check:**
   `tests/test_prd_criteria.py`, `tests/test_scaffold.py`.
4. **Generated agents.** `python3 generator/build.py --check` reports clean; every generated
   definition comes from one `generator/stacks/*.toml` × one `generator/templates/*.md.tmpl`;
   `init` and `agents` render definitions per project; a hand-modified definition is skipped
   unless `--force-managed`, and an unmarked one is never written. *Amended 2026-09-25 (CR-MDB-035):
   the literal counts are retired — CR-MDB-024 made rust the fifth generated stack, and DN §D17 /
   CR-MDB-025 moved definitions to per-project rendering; the installer deploys none.* **Check:**
   `generator/build.py --check`, `tests/test_agent_generator.py`,
   `tests/test_pi_agent_definitions.py`.
5. **Crucible clients.** *Model B's half:* every Crucible client invocation in shipped skills,
   templates, stack parameters and contracts matches the released client's surface at
   `~/.crucible/clients/`. *Crucible's half:* the per-stack clients ship in a Crucible
   release (0.2.2: arduino, bun, mvn, python, rust); a register→test→unregister smoke per client is
   Crucible's release gate, not Model B's. `vscode-crucible.py` was declined (D7, Sandesh #1370):
   no VS Code client exists or is pending. *Amended 2026-09-25 (CR-MDB-035): Crucible shipped
   (0.2.x), so "closes only when Crucible ships" is discharged.* **Check:**
   `tests/test_client_path_anchoring.py` (`ClientContractS3Test`).
6. **Deployed state matches the manifest.** A redeploy removes managed files that left the
   manifest (a narrowed `--stacks`, a retired bundle) and never removes or overwrites unmanaged or
   hand-modified files. *Amended 2026-09-25 (CR-MDB-035): replaces "`chezmoi diff` clean after
   every wave", which measured the user's dotfile tree, not a Model B property (CR-MDB-021).*
   **Unmet until CR-MDB-040 merges. Check:** CR-MDB-040's gate.

### §S2 — §3 invariants
- Invariant 1 becomes: "`AGENTS.md` is the only project-context file Model B writes; it emits no
  `CLAUDE.md` (CR-MDB-031)", with a dated note recording that it replaces the D1 symlink
  invariant, which served Claude Code (dropped, DN §D14).
- "AC gates are executable pytest checks" becomes "executable `unittest` checks" (the suite has
  never used pytest).

### §S3 — Design sections that contradict a merged CR or DN
Each site keeps its original sentence and gains a dated **AMENDED 2026-09-25 (CR-MDB-035, …)**
line — the pattern D5 already uses — stating the current design and the CR/DN that moved it:

| Site | Current design to state |
|---|---|
| D1, the `CLAUDE.md`-symlink invariant | no `CLAUDE.md` (CR-MDB-031, §D14) |
| D2, "symlinked into harness dirs like `~/.claude/skills/`" and the `chezmoi` bundle | skills live once in `~/.agents/skills/`, which Pi reads directly; no per-harness links; `chezmoi` is not a bundle (CR-MDB-031) |
| D4, the `chezmoi` skill | retired by CR-MDB-031; chezmoi discipline is the user's own |
| D9, the workshop directory list and the chezmoi sentence | no `plans/` directory (D3.5); the `destroy`/`forget` reference to D4 points at a retired skill |
| D10.4 and the check-in-policy bullet, `CLAUDE.md` symlink | no `CLAUDE.md` (CR-MDB-031) |
| D10.7, "Claude Code: the project's `.claude/settings.json`" | Pi: the project's `.pi/extensions/` (CR-MDB-030/-031) |
| D10 installer-vs-scaffold bullet, "global memory (language refs) … per the targeted harnesses" | no global memory tier (D5 amendment); the only harness is Pi |
| D10(e), the four-harness roster | Pi only (DN §D14; CR-MDB-031) |
| D2, Tier 3 "the `memory/` reference library" | the library is `skills-src/memory-templates/`, scaffolded into `<project>/docs/memory/` (D5 amendment; criterion 3) |
| D2, "global language refs per D5" | there is no global memory tier (D5 amendment) |
| D3, the `status-report` skill | no `status-report` bundle exists; `bootstrap`, `shutdown` and `code-health` ship |
| D6, "(20 files)" and the bespoke list | Model B ships the generated stack × role set only, rendered per project (DN §D17, CR-MDB-025); it ships no bespoke agents; counts are not stated (criterion 4) |
| D7, "bundle path `crucible:clients/`" | Model B consumes the released clients at `~/.crucible/clients/`, never a checkout (D10, ruling 2026-09-23) |
| D8, the `mail-axi` contract | archived to `archive/contracts/mail-axi.md` by CR-MDB-031; not a Model B contract |
| D10.5, "the run-context wrapper plumbing" | retired by CR-MDB-031; skills call the installed Crucible client directly |

§1 Problem and the header's Sources line are history and stay as written.

### §S4 — Gates
A new module `tests/test_prd_criteria.py` asserts:
- every `~/.agents/skills/<path>` citation in `skills-src/**/*.md` and `generator/templates/*`
  resolves to a file under `skills-src/` (criterion 3), with a detector fixture proving an
  unresolved citation fails;
- the `AGENTS.md` scaffolded for all five stacks in `multi:3` mode, in a sandbox, is ≤100 lines
  (criterion 1);
- PRD §3 and §4 name no `CLAUDE.md`, `chezmoi`, `Claude Code`, `Hermes` or `OpenCode` (matched
  case-insensitively, including `$HOME/.claude/` paths) except
  inside a dated amendment note or as a stated absence (a term directly preceded by "no", as in
  §S2's "emits no `CLAUDE.md`"); every §4 criterion carries a **Check:**, every `tests/…py`
  path it names exists, and every repo script a Check invokes (e.g. `generator/build.py`) exists.

`tests/test_client_verb_sweep.py:96` and `:689` cite "PRD §11 criterion 2"; they become "PRD §4
criterion 2". `tests/test_installer_assets.py:920-921` says CR-MDB-007 has a queue row; that row
was removed (`b237b63`), so the docstring points at the README's 2026-07-20 note instead.

## Acceptance criteria

- [ ] PRD §4 is exactly the six criteria of §S1, each with its dated amendment note (where
      amended) and a **Check:** naming an existing test module or command.
- [ ] No §4 criterion states a literal agent count; criterion 4 is the §S1 property.
- [ ] Criterion 5 separates Model B's half from Crucible's half and states `vscode-crucible.py` as
      declined (D7, Sandesh #1370), not pending.
- [ ] Criterion 6 is the §S1 manifest property, states "unmet until CR-MDB-040 merges", and names
      CR-MDB-021 as the reason `chezmoi diff` left the PRD.
- [ ] §3 is amended per §S2.
- [ ] Every §S3 site carries a dated AMENDED line stating the current design and its CR/DN; no
      original sentence is deleted.
- [ ] No PRD sentence outside §1 Problem, the header, and dated amendment notes requires a
      `CLAUDE.md`, a chezmoi bundle, a `~/.claude` path Model B writes, or a harness other than Pi.
- [ ] `tests/test_prd_criteria.py` exists with the §S4 assertions and detector fixtures, and fails
      on today's PRD.
- [ ] The two `test_client_verb_sweep.py` citations and the `test_installer_assets.py` docstring
      are corrected per §S4.
- [ ] `AGENTS.md`'s module count and both suite baselines (real `HOME`, empty `HOME`) are
      re-measured and recorded.
- [ ] The merge note records each criterion's measured result with the command that produced it.

## Estimated size

One PRD reconciled, one new test module, three citation fixes. No production code.

## Non-goals

- No new success criteria. This reconciles what exists.
- No installer pruning — that is CR-MDB-040.
- No edits to DN-multi-harness, closed CRs, `archive/` or `audits/`.
- No release gating. This CR does not decide when 1.0.0 ships (user ruling 2026-09-21).
