# CR-MDB-019 — Hook runtime correctness: a superseded contract pin, an unreachable stack, and an `async` handler that blocks

**Status:** PENDING
**Type:** bugfix
**Priority:** P2 (release-1.0.0 hygiene — one dead stack path and one fail-closed hazard in shipped hook output)
**Depends on:** CR-MDB-015 (authored the hook + emitters), CR-MDB-018 (supplies the `clients_dir` the feed resolution needs)
**Labels:** hooks, opencode, crucible, contract, patch
**Phase:** Wave 5
**Design reference:** the status-envelope contract **document**, version **2.0.0** — cited at its INSTALLED, manifest-discoverable location `~/.crucible/clients/STATUS-CONTRACT.md` (re-verified 2026-09-18: still `**Version: 2.0.0**`; §Versioning records the 1.1.0 → 2.0.0 rationale). **Never cite a Crucible source checkout** (user directive 2026-09-18): the path is discovered from `crucible-clients.json`'s own `status` key, which CR-MDB-018 now captures, so this hook's re-pin target is resolved rather than hardcoded · `docs/research/DN-harness-agnostic-hooks.md` §2 / §4.4 (the refusal rule) · `hooks-src/schema.md`

## Amendments 2026-09-21 (from `audits/2026-09-21-codebase-review-*.md`)

- **§S3 STRUCK.** "Make the opencode handler honestly asynchronous" is withdrawn: opencode is not
  a target (DN §D13/§D14) and `_emit_opencode` is retired by CR-MDB-031. Its AC lines under
  "§S3 / §S4" that name the opencode emitter are void; §S4's fail-closed guard now applies to
  the **Pi** emitter, whose runtime is rebuilt by CR-MDB-030 (measured: no default-export
  factory, no `stdin` in `pi.exec`, `execCommand` never rejects — so today `_HONORS_FAIL_CLOSED`
  is false for `pi` too). 019 keeps §S1 (status-contract re-pin from the manifest's `status`
  key; `lastRunCr` → `lastClosedCr`) and §S2 (arduino marker). `tests/test_hooks.py:415-429`
  loads Crucible's dev-checkout `toon.py` in-process to build this hook's fixtures — out of
  bounds since 2026-09-18; use `modelb_axi.toon` (CR-MDB-032 §S1 owns the sweep; 019 must not
  add to it).
- "No change to the pi or claude-code emitters" in Non-goals now reads: no change to the pi
  emitter *here* (030), and the claude-code emitter is retained only until 031 deletes it.

## Context

Three defects in shipped hook output, none of which any current test can see.

**1 — the ambient hook pins a superseded contract document version.**
`hooks-src/scripts/ambient-board-status` was authored against the Crucible status-envelope
contract document at version **1.0.0** and hard-codes it: `:40`
(`STATUS_CONTRACT_VERSION = "1.0.0"`), `:7` (module docstring), `:81` (parser docstring),
`:150` (an inline "Contract 1.0.0" comment), `:177` (the degrade message interpolates the
constant). That document is now at **2.0.0** (`~/.crucible/clients/STATUS-CONTRACT.md:3`).

Scope of the actual breakage, measured rather than assumed: the hook invokes only the
`status` verb (`:75`, `:127-146`) and never `register`, so the clean-break flag rename that
justified the document's major bump does not break this script today, and the envelope shape
it parses — `plans[]{cr,wave,status,activeCycleId}`, `lastRunCr`, `count`, `warnings[]` — is
unchanged across 1.1.0 and 2.0.0. What IS broken is the pin's purpose: §Versioning of that
document exists so a hook can detect a shape change, and a pin frozen at a superseded
version can never do that. The user-visible symptom is the degrade message at `:177`, which
tells an operator the output failed to match a contract version that is no longer the
contract.

Naming discipline for this CR: `2.0.0` is the version of that ONE contract **document**.
Crucible's product releases are `0.1.0 / 0.1.1 / 0.1.2` (latest `0.1.2`) and "V2" is the
`/api/v2/*` API generation. Crucible confirmed in #1359 that the product release carrying
document versions 1.1.0 AND 2.0.0 is **0.1.0** — so the document's major bump never
corresponded to a product major, and the hook has been pinned to a superseded document
since before Crucible's first release. No text this CR writes may imply a Crucible product
version of `2.0.0`.

**2 — arduino can never resolve a feed.**
`_STACK_MARKERS` (`:45-51`) maps five marker files to four clients — `Cargo.toml`,
`pom.xml`, `bun.lock`, `bun.lockb`, `pyproject.toml`. There is no arduino marker, so
`arduino-crucible.py status` is unreachable, even though Model B owns
`skills-src/crucible-report-arduino/` and Crucible's discovery manifest enumerates
`arduino` among its five stacks.

**3 — the opencode emitter declares `async` and then blocks.**
`modelb_axi/hooks.py:227-271` (`_emit_opencode`) emits every handler as
`export async function …` (`:250`) over a body that is entirely synchronous: it imports
`spawnSync` (`:233`), calls it (`:253`), and never awaits anything. The `async` keyword is
untrue, and the blocking call holds the harness event loop for the whole hook timeout
budget. The pi emitter by contrast genuinely awaits (`:219`, `await pi.exec(...)`).

The hazard is precise and must not be lost: the spawn-failure predicate at `:257`,
`if (result.error || result.status === null)`, is **`spawnSync`-shaped** — `spawnSync`
reports failure by returning `{error, status: null}` rather than throwing. That predicate is
what gates the fail-closed return chosen at `:241-246`. Re-expressing it carelessly for a
promise-based call makes a fail-closed guard silently fail OPEN — the exact failure mode
`DN-harness-agnostic-hooks.md` §4.4 forbids and CR-MDB-015's F1 cycle was raised to fix.
The compile-time refusal rule is NOT affected: refusal is decided in `_partition`
(`hooks.py:166-179`) from the frozen `_HONORS_FAIL_CLOSED` (`:135`) and never consults
emitted text.

## Scope

### §S1 — Re-pin the ambient hook at the current contract document version
Move `STATUS_CONTRACT_VERSION` and all four prose references to the document's current
version, and state in the docstring which axis that number belongs to (the status-envelope
contract document, not a Crucible product release). The parser and the three terminal-state
renderings stay as they are — they already match the 2.0.0 shape.

### §S2 — Make arduino resolvable
Add the arduino marker to `_STACK_MARKERS` so an arduino project resolves
`arduino-crucible.py status`. The marker must be a file an arduino firmware project actually
carries; pick it from the arduino bundle's own documented project shape rather than
inventing one.

### §S3 — Make the opencode handler honestly asynchronous
Rewrite the emitted body in `_emit_opencode` to await a promise-based spawn, with the
failure path re-expressed for that shape: a rejected promise AND a null exit code both take
the failure branch, so the fail-closed return still fires when the script cannot be spawned
at all. The emitted contract is otherwise unchanged — exit code 2 still maps to
`{ block: true, reason }`, and the fail-open branch still returns `{}`.

### §S4 — Guard the fail-closed runtime path against the rewrite
Extend the existing opencode emitter tests so the spawn-failure branch is asserted on the
NEW shape, not just by the substring it happens to contain today: the emitted text must
contain a failure branch that returns `{ block: true` for a `closed` instance, and must not
contain a bare synchronous spawn call inside an `async` handler.

## Acceptance criteria

### §S1
- [ ] `hooks-src/scripts/ambient-board-status` contains no occurrence of `1.0.0`;
      `STATUS_CONTRACT_VERSION == "2.0.0"`.
- [ ] The module docstring names the axis explicitly — the Crucible **status-envelope
      contract document** version — and the file contains no claim of a Crucible product
      version `2.0.0`.
- [ ] The three terminal states still render distinctly (board present / no plan filed /
      `status-unavailable` tolerant degrade) and every path still returns 0.

### §S2
- [ ] `_STACK_MARKERS` resolves `arduino-crucible.py` from an arduino project marker; all
      five stacks Crucible's manifest enumerates (`bun, python, rust, mvn, arduino`) are
      reachable.
- [ ] A test asserts feed resolution for an arduino-shaped fixture directory.

### §S3 / §S4
- [ ] The emitted `.opencode/plugin/modelb-hooks.ts` contains no `spawnSync` and no
      `node:child_process` synchronous import; every emitted handler that is declared
      `async` contains at least one `await`.
- [ ] For a `fail_direction: closed` instance the emitted text still contains the
      fail-closed guard message and returns `{ block: true` on spawn failure; for a
      `fail_direction: open` instance the spawn-failure branch still returns `{}`.
- [ ] Exit code 2 still maps to `{ block: true, reason: … }`.
- [ ] `compile_wiring`'s refusal accounting is byte-unchanged: `_HONORS_FAIL_CLOSED` still
      contains exactly `pi` and `opencode`; claude-code and hermes still refuse a `closed`
      instance with a named reason; `AllTargetsRefusedError` still raises when every target
      refuses everything.

## Estimated size

2 files edited (`hooks-src/scripts/ambient-board-status`, `modelb_axi/hooks.py` —
`_emit_opencode` only), ~2 test methods extended plus 1 added. No schema change:
`hooks-src/schema.md` says nothing about the emitted TypeScript shape.

## Risk

- **§S3 is the only real hazard in this CR.** An async rewrite that drops the null-exit-code
  half of the failure predicate turns a security-class fail-closed guard into a fail-open
  one, silently. §S4 exists to pin that, and the AC is written on the branch's behaviour
  rather than on a substring that survives either implementation.
- §S1 is a pin move, not a parser change — resist widening it into an envelope rewrite. If
  the 2.0.0 shape ever does diverge from what the parser reads, that is a separate CR with
  its own RED.

## Non-goals

- No Hermes work. The Hermes emitter's declared degradation is correct, tested, and gated on
  an upstream capability that has not shipped; it stays in the deferred register.
- No change to the pi or claude-code emitters.
- No installer change (CR-MDB-018) and no bundle text change (CR-MDB-017).
