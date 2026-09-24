# CR-MDB-019 — The ambient hook renders the current status contract: the 2.0.0 pin, `lastClosedCr`, open plans only, and arduino projects

**Status:** PENDING (filed 2026-08; amended 2026-09-21; rewritten at its gap-analysis 2026-09-24 —
earlier text is git history and is not to be consulted for contracts)
**Type:** bugfix
**Priority:** P2 — in release 1.0.0, wave 2. The hook CR-MDB-018 made reachable now renders the live
board, and renders it wrongly.
**Depends on:** CR-MDB-018 (manifest-based feed resolution, `_STACK_MARKERS`, §S3 parity test)
**Labels:** hooks, crucible, contract, bugfix
**Design reference:** Crucible's `status` envelope contract **document**, version **2.0.0**, at its
installed, manifest-discoverable location `~/.crucible/clients/STATUS-CONTRACT.md` (the manifest's
`status` key; never a Crucible source checkout) · the arduino-cli sketch rule (a sketch is a folder
whose primary file is `<folder name>.ino`) · CR-MDB-018 §S1–§S3

## Context — measured 2026-09-24 on `develop` at `a2599ca`

Running the hook in the model-b tree against the production board prints
`Crucible board (31 open plan(s)):` followed by rows such as
`cr=CR-MB-001 wave="1" status=closed activeCycleId=null`, and no last-closed line. Four defects:

1. **A superseded pin.** `STATUS_CONTRACT_VERSION = "1.0.0"` and the docstrings cite 1.0.0; the
   document is at **2.0.0**. The number is the version of that one contract document — Crucible's
   product releases are `0.x` — and the pin exists so a degrade message names the contract in force.
2. **`lastRunCr` is gone.** The document and the live envelope carry `lastClosedCr` ("the `cr` of the
   plan with the latest `closedAt`, or `null`"). The hook still looks for `lastRunCr`, so the line
   never prints.
3. **Closed plans are shown as open.** The document says `plans` is "one uniform row per open plan",
   with `status` `open` / closed; the live `status` verb returns every plan, closed ones included
   (31 rows, most `closed`). The hook counts and lists them all under "open plan(s)".
4. **TOON quoting leaks into the output.** String cells that look numeric arrive quoted (`"1"`), and
   the hook prints the quotes (`wave="1"`).
5. **Arduino projects never resolve.** `_STACK_MARKERS` has no arduino entry. An arduino-cli sketch
   has no fixed marker file name: its marker is a primary `<folder name>.ino` in the folder. Measured
   on the real project: `sheetal-firmware/sheetal-firmware.ino`, with the native tests under
   `sheetal-firmware/tests/native/`.

Out of scope, measured: the opencode async rewrite (the old §S3) is void — opencode is not a target
(DN §D13/§D14) and CR-MDB-031 deletes `_emit_opencode`. The Pi fail-closed guard (the old §S4) was
rebuilt and tested by CR-MDB-030 (`tests/test_pi_hook_runtime.py` §S5).

## Scope

### §S1 — Pin the current contract document
`STATUS_CONTRACT_VERSION` is `"2.0.0"`; every prose citation of the version moves with it, and the
module docstring states that the number is the version of Crucible's `status` envelope contract
document, not a Crucible product release.

### §S2 — Render `lastClosedCr`
The hook reads `lastClosedCr` and prints it (for example `last closed: CR-…`) when it is a CR id,
and prints nothing for `null`. It no longer looks for `lastRunCr`.

### §S3 — Show open plans only
Rows whose `status` is `closed` are not listed and not counted as open. The heading counts the open
rows. A board with plans but none open prints a definitive "no open plan" note — distinct both from
"no plan filed" (`count: 0`, no warnings) and from the `status-unavailable` degrade. The three
contract terminal states keep rendering distinctly, and every path still exits 0.

### §S4 — Unquote cells
A table cell wrapped in double quotes is rendered without them.

### §S5 — Arduino projects resolve
A directory containing a file named `<that directory's name>.ino` is an arduino project; walking up
from the working directory, it resolves `clients["arduino"]` like every other stack, and the nearest
marker still wins. CR-MDB-018's §S3 parity test covers the arduino entry (`arduino` →
`STACK_CLIENT_KEYS["arduino"]`). A stray `.ino` whose stem is not the folder's name is not a marker.

## Acceptance criteria

### §S1
- [ ] The hook contains no `1.0.0`; `STATUS_CONTRACT_VERSION == "2.0.0"`; the docstring names the
      axis (the status envelope contract document) and claims no Crucible product version 2.0.0.

### §S2
- [ ] A feed with `lastClosedCr: CR-X-001` prints that id; a feed with `lastClosedCr: null` prints no
      last-closed line; the hook source no longer reads `lastRunCr`.

### §S3
- [ ] A feed with open and closed rows lists only the open ones and counts only them in the heading.
- [ ] A feed whose rows are all closed prints the "no open plan" note, exits 0, and prints neither the
      "no plan filed" note nor a degrade note.
- [ ] "No plan filed" and the `status-unavailable` degrade still render as before.

### §S4
- [ ] A quoted cell (`"1"`) renders unquoted (`wave=1`).

### §S5
- [ ] An arduino-shaped fixture (`<dir>/<dir>.ino`, working directory `<dir>/tests/native`) resolves
      and runs the manifest's `arduino` client.
- [ ] A directory holding only a `.ino` whose stem differs from the folder name is not a marker.
- [ ] CR-MDB-018's parity test passes with the arduino entry; all five manifest keys (`arduino`,
      `bun`, `mvn`, `python`, `rust`) are reachable from some marker.

### All
- [ ] Every test runs the real hook with a sandboxed `HOME` and fixture feed, never the real
      `~/.crucible` or a Crucible checkout; fixture envelopes come from `modelb_axi.toon`. Existing
      tests pinning the old rendering are migrated and listed by id.

### Close-out (orchestrator, before merge)
- [ ] The merged hook, run in the model-b tree against the production board, lists only open plans,
      prints the last closed CR, and shows no quoted cells.

## Risk

- The hook is still a shape reader, not an envelope rewrite: the parser keeps its table/scalar
  approach, and only the field name, row filter and cell quoting change.
- The document says `plans` holds open plans while the verb returns all of them. Filtering on the
  hook side is correct under either reading; the discrepancy is reported to Crucible (Sandesh, #1336
  lineage), and nothing here depends on their answer.

## Non-goals

- No change to the hook's feed resolution beyond the arduino marker (CR-MDB-018).
- No emitter work: the opencode emitter is retired by CR-MDB-031, and the Pi runtime is CR-MDB-030's.
- The `block-direct-*` hooks' stale discovery wording is CR-MDB-020's.
- `tests/test_hooks.py`'s load of a Crucible checkout's `toon.py` is CR-MDB-032's sweep; this CR adds
  no new such load.
