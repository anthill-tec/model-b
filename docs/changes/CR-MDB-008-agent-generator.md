# CR-MDB-008 — agent generator: templates + stack params + drift gate

**Status:** PENDING
**Type:** feature
**Priority:** P1 (scaffold gatekeeper — 013 depends)
**Depends on:** CR-MDB-002, CR-MDB-006
**Labels:** generator, agents
**Phase:** Wave 3
**Design reference:** PRD §D6 (generated agents; similarity evidence: fix/verify 52–54% cross-stack, red/green 19–30%) · `audits/2026-07-20-skills-agents-inventory.md` · gap notes below

## Context

The 16 small-stack agent defs (arduino/bun/python/quarkus × red/green/verify/fix) restate the same SE principles with per-stack divergence maintained by hand. Per D6 they become GENERATED: role templates carry the principles once; stack parameter files carry only mechanics. Gap reconciliations (ride this branch): (1) stdlib-only ⇒ stack params are **TOML** (`tomllib`), not YAML; (2) `build.py` writes the LIVE `~/.claude/agents/` files and the runner chezmoi-ADDs them — never `chezmoi apply` (D6 wording aligned to the standing discipline).

## Scope

### §S1 — AC gate tests
`tests/test_agent_generator.py`, wrapper-run, RED → GREEN.

### §S2 — generator sources (repo)
`generator/templates/{red,green,verify,fix}.md.tmpl` — `string.Template` markdown: frontmatter (name/description from params), the universal role procedure (CITES `~/.claude/skills/model-b/references/sub-agent-procedure.md` + the `crucible` skill — never restates them at length), placeholders for stack mechanics. `generator/stacks/{arduino,bun,python,quarkus}.toml` — per-stack: display name, test framework + commands, crucible client/reference, report locations, per-role gotcha blocks (distilled from the CURRENT agent bodies — no content invented, no still-true mechanic dropped).

### §S3 — build.py
`generator/build.py` (stdlib only): `build` renders the 16 files into `~/.claude/agents/` (in-place overwrite); `--check` re-renders to memory and DIFFS against live — exit 0 clean / exit 1 listing drifted files; `--stacks`/`--roles` filters. Deterministic output (stable ordering; no timestamps). The 13 bespoke defs (rust×4, vscode×4, electronics×4, inbox-analyst) are NEVER in the target list.

### §S4 — regeneration + sync
Archive the 16 current agent files to `<repo>/archive/wave3/agents/` (pre-generation originals); run `build.py build`; chezmoi-add the 16; ALSO bring the previously-unmanaged `inbox-analyst.md` under chezmoi management (add, ZERO content change — RED-surfaced gap: the bespoke-diff gate needs it managed); source commit. Generated content requirements: valid frontmatter (`name:` matches filename stem, non-empty `description:` with stack + role); contains the sub-agent-procedure path and the `crucible` skill reference; per-stack mechanic anchors survive — python: `--tests`, bun: `bun test`, quarkus: `mvn`, arduino: `arduino-cli`; zero references to retired artifacts (`agent-baseline`, `crucible-report`, `orchestration-universal`, `bun-red-testing`, `quarkus-regression-testing`).

## Acceptance criteria

### §S1
- [ ] `tests/test_agent_generator.py` exists; RED then GREEN ingested with wave-3 cycle context.

### §S2
- [ ] All 4 templates + all 4 stack TOMLs exist; each TOML parses via `tomllib` and contains keys `display_name`, `test_command`, `crucible_reference`.

### §S3
- [ ] `python3 generator/build.py --check` exits 0 (post-§S4 live tree matches regeneration — idempotence).
- [ ] Mutating one generated live file then `--check` exits 1 naming that file (test restores the file afterwards from the rendered content).
- [ ] `build.py` target list is exactly the 16 small-stack files (grep of `--list` output or module constant): zero bespoke names present.

### §S4
- [ ] All 16 pre-generation originals exist under `<repo>/archive/wave3/agents/`.
- [ ] Each of the 16 live files: frontmatter `name:` == filename stem; `description:` non-empty; contains `sub-agent-procedure` and `crucible`; contains its stack anchor (python `--tests` / bun `bun test` / quarkus `mvn` / arduino `arduino-cli`).
- [ ] `grep -rl "agent-baseline\|crucible-report\|orchestration-universal\|bun-red-testing\|quarkus-regression-testing" ~/.claude/agents/` returns 0 files.
- [ ] The 13 bespoke defs byte-unchanged (compare vs pre-CR state: `chezmoi diff` on each is empty AND none appears in the chezmoi source commit's file list).
- [ ] Scoped `chezmoi diff` (5 standard paths) exits 0 empty.

## Estimated size
L. One red-green cycle (template distillation is the bulk) + verify with per-agent equivalence review.

## Risk
- Distillation loses a stack nuance — mitigated: originals archived; VERIFY does a per-agent CONTENT-COVERAGE review (every still-true instruction from the original is present or deliberately superseded — superseded items listed).
- Generated wording churns agent behavior — the dispatch-prompt override block (project AGENTS.md) remains the binding convention layer regardless.

## Non-goals
- rust/vscode/electronics/inbox-analyst (bespoke; electronics excluded entirely).
- The scaffold's invocation of the generator (013); Vercel-standard packaging (014).
