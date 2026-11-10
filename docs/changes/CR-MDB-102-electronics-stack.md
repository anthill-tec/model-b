# CR-MDB-102 — An electronics stack: schematic, board and perfboard design

**Status:** PENDING — **SEED, not the finished spec** (filed 2026-11-10 by the user's rulings, relayed as
P1 Extractor Fan Controller #1564). Gap analysis, the spec and its pre-review happen in order when this
CR starts. Pre-review: due (13 points; another project's surface).
**Type:** feature (a generated stack, an extra agent)
**Priority:** P1 — release 1.1.0, wave 4 (user 2026-11-10: moved out of 1.0.0, wave 2, because its
Crucible dependencies ship in Crucible 0.5.0 and 1.0.0 must not wait on them; board-authoritative: read `queue`).
Every EDA agent, skill and piece of installation support goes into release 1.1.0, starting in wave 4, and
none of it into 1.0.0 (user 2026-11-10). Gap analysis may split this CR into several in that release.
**Depends on:** off the board, Crucible's electronics test client `eda-crucible.py` (#1571), released —
Crucible release 0.5.0, wave 9: CR-CRU-242 (a pytest tier filed), CR-CRU-243 (the fleet installs, declares
and counts the client), CR-CRU-244 (gate scripts through `crucible-gate`) and CR-CRU-246 (the Perfboard
capture and its gate) (#1589). The stack's tests run through it; this CR
starts only once it ships (user 2026-11-10).
**Labels:** stacks, electronics, generator
**Design reference:** PRD D7 (the electronics exclusion, lifted 2026-11-10) and D6 (generated per-stack
agents); DN-multi-harness-deploy-model §D25 (a stack carries what holds for every project on that runner);
CR-MDB-056 (tests run only through Crucible clients); CR-MDB-085 (stack skills rendered per project).

## Context

PRD D7 excluded electronics on 2026-07-20 ("anthill-forge is DEAD/DEPRECATED … the four electronics
agents, and the electronics skills are under revision … revisit when their revision lands"). The revision
has landed: P1 Extractor Fan Controller (PFC, solo, `vidushi-p1fan`) ported the four agents to Pi and keeps
them local and untracked in its `.pi/agents/`:

| P1 Fan's file | Role |
|---|---|
| `electronics-bench-test-engineer.md` | RED: failing electrical validations |
| `electronics-board-designer.md` | GREEN: SKiDL netlist, KiCad schematic, perfboard or PCB layout |
| `electronics-quality-engineer.md` | VERIFY, with a spec pre-review mode |
| `electronics-production-engineer.md` | after VERIFY: BOM, kitting, build or fab pack |

The user ruled (2026-11-10): lift the exclusion into 1.0.0, wave 2; ship a **generated** stack; ship the
production engineer as a **stack extra agent**; and **wait for Crucible's electronics client**.

The toolchain P1 Fan reports (#1564):
- SKiDL 3.0.0 → KiCad netlist, with explicit part tags for a deterministic netlist; KiCad 10 symbols via
  `KICAD8_SYMBOL_DIR`.
- KiCad 10 `kicad-cli`: ERC, schematic PDF, PCB DRC, gerbers.
- Perfboard Studio 0.23.0 (Apache-2.0; desktop, Python package and MCP server): imports a KiCad `.net`,
  stock boards, `run_lvs`, DRC, ERC, `check_heights`, `generate_guide` (build order, wire cut list,
  multimeter checkpoints), `export_pdf`. **Python 3.12–3.13 only; it crashed on 3.14.** MCP:
  `uvx --python 3.13 --from "perfboard-studio[mcp]==0.23.0" perfboard-studio-mcp`.
- ngspice 47 for transient and signal-integrity sims (PySpice optional).
- Test levels: L0 ERC; L1 pytest netlist assertions; L1b layout gates (LVS, DRC, heights, mutation
  tests); L2 ngspice sims; L3 bench or HIL measurement.
- A desktop mechanic: on Hyprland with window swallowing, a GUI app is launched through
  `hyprctl dispatch 'hl.dsp.exec_cmd("<cmd>")'`, not from the agent shell.

Updated 2026-11-10 (P1 #1586, after Crucible's consultation #1579/#1585): P1 now uses no KiCad at all. Its
schematic comes from Perfboard Studio's own schematic sheet, `kicad-cli` and anthill-forge are dropped, and it
lays the board out through the Perfboard Studio MCP with no layout script and no `BoardSession` code. Its
project dir is `hardware/` (the declaration, a Python 3.13 `.venv`, and `.env` with the Crucible key), and its
`net_check.py`/`board_check.py` adopt the `crucible-gate` helper. The stack still serves a project with KiCad
or a PCB (`kicad-cli` gates, Konnect for design); P1 is one project, not the stack (§D25).

## Scope (seed)

1. **A sixth generated stack, `eda` (`generator/stacks/eda.toml`; the name ruled 2026-11-10, #1571),** rendered through the four role
   templates: RED (bench-test engineer), GREEN (board designer), VERIFY (quality engineer) and FIX (from
   the shared template, where the designer's fix mode would otherwise sit). The stack holds what holds for
   every electronics project (§D25); one project's board, parts and paths stay in that project.
2. **The production engineer ships with the stack as an extra agent,** which the orchestrator dispatches
   after VERIFY. It is not a new Model B role and adds no lifecycle stage for other stacks. Its Build is a
   plain dispatch with no cycle: the board records nothing for it, and its outputs are files in the
   project (PRD D7, ruled 2026-11-10, #1569). The cycle plan is the fleet's own: one red-green cycle per
   behaviour unit, then VERIFY and FIX.
3. **Tests run through Crucible's electronics client** (CR-MDB-056 stands, no exception): the stack names
   that client's verbs and tiers as released, and its pass, fail or SKIP verdict per gate. A gate that
   cannot run yet reports SKIP, never red; there is no known-red state (PRD D5, D7).
4. **A `crucible-report-eda` skill,** Model B's (#1336/#1337, `skills-src/CRUCIBLE-HANDOVER.md`), for
   `eda-crucible.py`: its tiers run pytest with JUnit output and SKIP native, and a declared PASS/FAIL
   gate-script protocol follows in a later Crucible CR (#1571). The board gains no field for the LVS
   verdict or the open, short, ERC and DRC counts: the gates assert them and a failure's message names them.
5. **The agent side of the EDA gates** (PRD D7, Model B's position 2026-11-10, #1573/#1574; open to P1
   until the three-way agreement): GREEN and FIX run Crucible's `crucible_gate.perfboard capture` after any
   layout change and commit the results beside the `.perf`; RED declares the target; VERIFY only re-runs the
   ingest. Once a layout target is declared, missing results FAIL; SKIP is only for a gate that cannot run
   yet. Project pytest gates may read the committed `.perf` and results, and may start the MCP on a `/tmp`
   copy for mutation tests (agreed three ways, #1580/#1582/#1583). The Perfboard Studio MCP is a design
   tool as well as the capture's source: the board designer places the layout through it and commits the
   `.perf` (registered project-local, `.pi/mcp.json`). For PCB design the agents use the Konnect KiCad MCP;
   the gates stay on `kicad-cli`.
6. **What only electronics needs** (the toolchain, the levels, the 3.13 interpreter for Perfboard Studio,
   the desktop launch mechanic) goes in the stack's text or a stack skill (CR-MDB-085), never in the role
   templates.
7. **Installation support for the stack** (user 2026-11-10, release 1.1.0): the installer deploys
   `crucible-report-eda`; `modelb-axi init --stacks eda` and `modelb-axi agents` render the stack's agents,
   its extra agent and its stack skill; and the stack's requirement rows name its toolchain (SKiDL, the
   Perfboard Studio MCP on a Python 3.13 venv, ngspice, and `kicad-cli` and Konnect for a PCB project).
   Whether Model B scaffolds the project-local MCP registration (`.pi/mcp.json`) is measured at gap analysis.
8. **The guards move with it:** PRD D6's bespoke list and `tests/test_agent_generator.py`'s
   `BESPOKE_AGENT_NAMES` (which still names the four electronics files), the stack-generality guard
   (CR-MDB-079), the stack roster wherever `init`, `agents` and the requirement rows enumerate stacks, and
   `tests/test_orchestrator_rule_triage.py`'s `stack:electronics` "unknown stack" case (the stack id is `eda`).
9. **P1 Fan is told when it merges,** so it re-renders with `modelb-axi agents` and drops its local copies.

## To measure at gap analysis

- Crucible's released electronics client: its verbs, levels and envelope.
- The four ported agents against the role templates: what is template text already, what becomes stack
  text, what becomes a stack skill.
- How an extra agent ships beside the four rendered roles (the generator, `init`/`agents`, the deploy
  roster) and how the orchestration skills name its dispatch.
- The requirement rows the stack declares (KiCad, SKiDL, Perfboard Studio on Python 3.13, ngspice).
- The re-score (13 points filed) and the behaviour units.
