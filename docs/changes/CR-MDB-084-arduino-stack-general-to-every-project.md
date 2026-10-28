# CR-MDB-084 — The arduino stack is general to every Arduino project

**Status:** PENDING — **SEED, not the finished spec** (filed 2026-10-28 into release 1.1.0, wave 3).
Gap analysis, the spec and its pre-review happen in order when this CR starts.
**Type:** refactor (generated stack file, agent definitions)
**Priority:** P2 — release 1.1.0, wave 3.
**Depends on:** none known; the board is authoritative: read `queue`, not this line.
**Labels:** stacks, arduino, generator, generality
**Design reference:** DN-multi-harness-deploy-model §D25 (a stack carries what holds for every
project on that runner; one project's architecture lives in that project); CR-MDB-079 (the same
correction for the bun stack).

## Context

`generator/stacks/arduino.toml` was written for one firmware project, and every Arduino project
that adopts Model B renders its text into its agent definitions. The stack file names that
project's directory (`sheetal-firmware`, as `--project-dir` in every client command and in the test
layout), its change requests (`CR-SHE-005` to `CR-SHE-009`, as the CRs that will bring tiers and
coverage), its design documents (`PRD-arduino-test-stack.md`, `PRD-wokwi-simulation.md`), its display
library and colour constants (`Arduino_GFX`, `RGB565_*`), and its name in the VERIFY description. None
of that holds for another Arduino project.

## Scope (seed)

1. **The stack file holds only what holds for every Arduino project:** the `arduino-crucible.py`
   client and its verbs, `arduino-cli` compile, the native host test build and the test pyramid in
   general terms. The project directory, test layout, tiers and coverage arrive through the
   project's own configuration (its registry or `crucible.toml`, as the client resolves them), never
   as a literal in the stack.
2. **One project's facts leave the stack:** its CR ids, PRDs, libraries, constants, simulator and
   name. Whatever they still teach goes to that project's own `AGENTS.md` or knowledge store, never
   to a memory template, which `init` copies into every Arduino project.
3. **The client's surface as installed:** the verbs and tiers the stack names match the installed
   `arduino-crucible.py`, including `regression` (whole native suite, optional coverage) and, from
   Crucible 0.4.0, `test`/`unit --tests` (CR-CRU-211) and the test-scope ladder (DN §D26,
   CR-MDB-083).
4. **The generated arduino definitions are re-rendered**, and every guard naming the removed text is
   updated; an Arduino project takes the change with `modelb-axi agents`.
5. **The project the text came from is told** before this CR merges, so it records its specifics in
   its own project first — asking the user who owns it and how to reach it.
