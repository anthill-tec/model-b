<!-- The `arduino-stack` skill's orchestrator reference: the Arduino firmware mechanics an orchestrator owns (moved into the skill by CR-MDB-060). -->

# Arduino Orchestration — firmware tiers + Crucible (orchestrator-side)

Arduino-stack embodiment of `orchestration-common.md` (workflow, approval gates,
dispatch, verify-independently — not restated here) and
`~/.agents/skills/model-b/references/sub-agent-procedure.md` (sub-agent procedure). This file is
the Arduino firmware mechanics an orchestrator owns: keeping the agents' toolset current. The
hardware-driver rules live in the arduino agent definitions' GREEN and FIX gotchas.

> CR / PRD / DN doc conventions → the `cr-authoring` skill (universal). Test runs and ingest go
> through `~/.crucible/clients/arduino-crucible.py` (the `crucible` skill, `references/arduino.md`).
> Electronics design (boards, schematics, EDA) is EXCLUDED from Model B — never here.

## Test tiers and agents
- **When an Arduino test tier or tool lands, raise it to Model B so its arduino stack definition is
  updated; update this project's test-stack PRDs in the same change.** An agent definition must
  never describe a stale toolset.
