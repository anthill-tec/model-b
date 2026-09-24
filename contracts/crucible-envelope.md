# Contract — Crucible client AXI envelope

**Owner:** CRUCIBLE project (upstream tool provider).
**Status:** DELIVERED — TRACKS CR-CRU-030 + CR-CRU-036, shipped upstream (crucible
develop `949a2f4`; per-delivery intimations thread #1330/#1332). This document MIRRORS
the delivered client contract; it never forks it. Reconciliation on each upstream
delivery is owned by the TRACKS header here plus CR-MDB-011's doc pass.

## Installed product facts (measured, never inferred)

Measured against the production Crucible installed on this machine:

- **Product version `0.2.2`** — the release Model B documents against.
- The installer is `crucible-axi install`, which stages the client fleet + manifest.
- `--target-dir` chooses where that fleet is laid down.
- The default target is `~/.crucible`, so the clients live at `~/.crucible/clients/`.
- The run verb is `crucible-axi serve` — the provisioned server, in the foreground.
- `crucible-axi uninstall` reverses the install (the exact inverse of `install`).
- This document tracks `STATUS-CONTRACT.md` at its **document version 2.0.0** (verified at `~/.crucible/clients/STATUS-CONTRACT.md`).

**Three version axes, never conflated:** the PRODUCT version is `0.2.x`
(installed `0.2.2`); `/api/v2` is the API GENERATION the clients speak; and `2.0.0`
is the semver of one document only — `STATUS-CONTRACT.md`. It is not a Crucible
product or release number and must never be read as one.

## Current state

- The envelope is the SHIPPED, fleet-wide current state: every client verb on every
  stack client (`bun-crucible.py`, `python-crucible.py`, `mvn-crucible.py`,
  `rust-crucible.py`, `arduino-crucible.py`) emits it via the shared
  `~/.crucible/clients/_crucible_axi.py`.
- The client-side TOON codec is `~/.crucible/clients/toon.py` (`encode(dict) -> str` /
  `decode(str) -> dict`) — Crucible's spec-conformant port of the official grammar,
  validated upstream against the first-party reference library. It DOES emit the inline
  primitive-array short form (`help[2]: cycle-done <id>,status`); an earlier "strict
  subset, no inline short form" description here was measured wrong and is corrected
  below. GETs additionally serve compact TOON via `?fmt=toon` / `Accept: text/toon`;
  JSON replies carry `help` hints.

## TOON wire contract

**The wire contract is the OFFICIAL TOON spec** — toonformat.dev and the `toon-format`
GitHub org. Crucible's `DN-crucible-toon-subset.md` is **RETIRED** (their
CR-CRU-046, 2026-08-01) and survives only as a pointer at that spec. It is NOT a live
contract, no Model B file may treat it as one, and there is no private four-construct
subset to be pinned against.

**Model B does not implement the spec** — an official multi-language ecosystem already
does. `modelb_axi/toon.py` is the one HAND-MAINTAINED codec in this repo; `scripts/toon.py`
is GENERATED from it by `generator/build.py` (a real self-contained module, never a
re-export, so a deployed `worktree-flow.py` running under a bare `python3` resolves it
from beside itself) and held byte-identical by `generator/build.py --check`. The codec
ENCODES a documented valid SUBSET and DECODES what Model B's own tools emit.

Conformance is PROVEN, not asserted: `tests/test_toon_codec.py` round-trips the encoder's
output through `~/.crucible/clients/toon.py` **out of process** — subprocess only, never an
import, so no Crucible module is ever forked into a Model B process. That port is an
ORACLE and nothing else; Model B holds no copy of it and maintains none of their clients.

### The subset Model B emits

| Construct | Wire form |
|---|---|
| Scalar line | `key: <scalar>` |
| Nested object | `key:` + 2-space-indented child lines |
| Empty array | `key[0]:` |
| Scalar array | `key[N]: <item>,<item>` — the canonical INLINE form |
| Uniform object table | `key[N]{col,…}:` + one comma-joined row per item |

**Empty arrays.** `key: []` is the spec-canonical empty form and `key[0]:` is equally
valid. Model B emits `key[0]:` — the form its tooling has always written, which
`worktree-flow.py status` has always decoded — and its decoder accepts both. `key[0]: []`
is INVALID and nothing here emits it.

**Non-empty arrays go out INLINE.** A `[N]` header followed by BARE indented items is
INVALID: a conformant decoder counts an item line only when it starts with `- `, so bare
items read as zero items against a declared count of N. That was a live defect on
`worktree-flow.py`'s `next` and `progress` degrade path (`schedule_db unavailable —
queue-only project`; both verbs removed by CR-MDB-028) and is fixed in the codec, not per
call site. The hyphenated
`- <item>` form is the spec's other accepted shape: Model B decodes it and does not emit
it. A BARE indented item is also still decoded, so an older deployed copy's output stays
readable; it is never written.

### The quoting rule

A string is written BARE only when it is non-empty, has no leading or trailing space, is
not `true`/`false`/`null`, is not numeric-looking, holds none of `:` `"` `\` `[` `]` `{`
`}`, carries no control character, does not contain the `,` delimiter, and does not start
with `-` or `#`. Otherwise it is JSON-quoted, escaping only `\ " \n \r \t` and C0 controls
— an em dash is not special and stays an em dash.

That single rule is simultaneously the wire rule and the TYPE-PRESERVATION guarantee.
`"4"`, `"42"`, `"true"`, `"null"`, `""` and `"  indented  "` are therefore all quoted and
round-trip as the strings they were, and the decoder never re-types a quoted scalar. The
live instance: a Model B envelope carries `context.wave` as the STRING `"4"` (the shape a
`$WORKFLOW_WAVE` value takes), and it now goes out as `wave: "4"`.

A `key:` line with an empty tail is a NESTED OBJECT on BOTH sides of the wire — which is
exactly why an intentional empty string is emitted as `key: ""`. Model B does not diverge
from the reference port on that reading; it sidesteps the ambiguity on emit.

## Required surface

### Register surface — the role/cycle binding (CR-CRU-044 §S1 + CR-CRU-056 §S1/§S4)

This is the flag surface four consumers mirror (`skills-src/crucible/SKILL.md`, the six
`crucible-report-*` bundles, `generator/templates/*.tmpl`, and `AGENTS.md`); a consumer
that drifts from it teaches a registration the released server rejects. Measured against
the installed `0.2.2` fleet, 2026-09-21.

```
register --agent <id> --role <ROLE> [--cycle <cycleId>] [--display-name <n>]
         [--source <src>] [--message <m>] [--project-dir <dir>]
```

- **`--role` is required and CASE-EXACT**, from `{RED, GREEN, FIX, VERIFY, ORCHESTRATOR,
  report}` — five uppercase, `report` lowercase. It is the ONLY role channel. A missing
  role, or one outside that set, is refused 400 by the server; `red` is not `RED`.
  `report` is the role for a registration that is not exercising a TDD role.
- **`--cycle` binds the agent to a cycle, and the SERVER — not argparse — requires it for
  the four TDD roles** `RED|GREEN|FIX|VERIFY`: an unbound TDD registration is refused 409.
  The flag is optional in the parser, so the omission surfaces as a server error, never a
  usage message. `ORCHESTRATOR` and `report` may legally register UNBOUND. The id must name
  an ACTIVE cycle of an OPEN plan, it is server-assigned (never guessed), and once bound the
  server stamps every subsequent ingest by that agent with it.
- **The agentId is FREE-FORM** and assigned by the dispatcher, never minted by the agent.
  The role is NEVER inferred from its shape: an id ending `-GREEN` registered with
  `--role RED` classifies as RED. Any `<type>-<project>` or `CR-<PROJ>-NNN-<cycle>-<ROLE>`
  spelling is a readability habit only.
- **`--source` is enumerated** — `{claude-md, package-json, git-repo, manual}`, default
  `claude-md` — and is carried by the whole fleet, `rust-crucible.py`, `mvn-crucible.py`
  and `arduino-crucible.py` included, not just the bun/python pair.
- Registration is an UPSERT: registering an already-known agent touches it.
- The env carriers are unchanged by this surface — see *Classification context* below.
  `WORKFLOW_ROLE`, `WORKFLOW_WAVE` and `WORKFLOW_CYCLE` survive; the per-run cycle-id
  carrier is GONE, and no env var carries a cycle id. The cycle arrives through `--cycle`
  at registration and nowhere else.

**Wire body** — `POST /api/v2/agents/register`, the equivalent of the flags above.
`role` is omitted only when none was declared (which the server then refuses), and
`cycleId` is present only for a bound registration:

```json
{
  "agentId": "<id>",
  "projectKey": "<uuid>",
  "role": "<ROLE>",
  "cycleId": "<cycleId>",
  "status": "online",
  "message": "<status message>",
  "identity": {
    "displayName": "<name>",
    "source": "<src>",
    "repoPath": "<project dir>"
  }
}
```

`displayName`, `source` and `repoPath` go INSIDE `identity` — top-level copies are ignored
by v2. `unregister` takes `agentId` + `projectKey` only.

### Envelope (stdout = AXI channel, stderr = human channel)
Every client verb emits exactly one TOON envelope on stdout:

```
{axi: {verb, ok, …result fields…, context, warnings[]}}
```

- `verb` — the client action (`register`, `unregister`, `test`, `regression`,
  `auto-ingest`, `plan-file`, …); `ok` — boolean outcome; result fields are verb-specific
  (e.g. `agent`, `cr`, run summary).
- `context` — `{projectKey, agentId?, cycleId?, wave?, cr?, track?}`. Absent keys are
  OMITTED. `context.cycleId` ECHOES the attachment the SERVER reported, which since
  CR-CRU-056 is the binding the agent declared at registration via `register --cycle`
  (see *Register surface* above, and the retired auto-attach note below).
- `warnings[]` — always present, empty when clean.
- The human-readable line is interactive-only and goes to stderr; the machine channel is
  the stdout envelope. Test-run output itself is passed through on stderr.
  `pre-merge-gate` STREAMS its progress.

### Classification context
Runs and plan verbs are classified by the surviving `WORKFLOW_*` env carriers
(DN-model-b-language §2, LOCKED): `WORKFLOW_ROLE` (track), `WORKFLOW_WAVE` (wave),
`WORKFLOW_CYCLE` (cycle label — display). Model B pins these via the per-project context
wrapper (`/tmp/claude-1000/modelb-crucible`). No env var carries a cycle id.

### Server-resolved cycle attach + no-active-cycle withhold (CR-CRU-036) — RETIRED

> **RETIRED 2026-09-21 by CR-CRU-056 §S1/§S4.** Cycle attachment is no longer discovered
> by the client at ingest time. It is an EXPLICIT binding declared at registration with
> `register --cycle <cycleId>` (see *Register surface* above), which the server then stamps
> onto every subsequent ingest by that agent. The mechanism described in this subsection is
> kept verbatim as the superseded contract Model B mirrored between CR-CRU-036 and
> CR-CRU-056 — read it as history, never as an instruction. Where it and the register
> surface disagree, the register surface wins.

`context.cycleId` was resolved by the client from the server via
`resolve_attach_cycle` (shared `_crucible_axi.py`): the open plan's single
`status:"active"` cycle was auto-attached. The contract returned
`(cycle_id, warnings, withhold)`:

- plans-fetch failure → `(None, [], False)`: tolerant, the verb PROCEEDS.
- no open plan at all → `(None, [], False)`: tolerant, PROCEEDS unattached.
- open plan with an active cycle → `(id, [], False)`: attaches.
- open plan but NO active cycle → `(None, [no-active-cycle], True)`: the definitive
  WITHHOLD — the client emits `ok:false` with the `no-active-cycle` warning, prints the
  withhold line to stderr, SKIPS the POST (nothing is posted — no orphan ever reaches
  the server) and exits non-zero.

Under THAT mechanism the orchestrator's only cycle input was `cycle-activate` and agents
never passed a cycle id. Under the current one the orchestrator still drives
`cycle-activate`, and the agent additionally declares the binding ONCE, at registration.

### Universal plan verbs (fleet-wide)
Filed by the orchestrator, on ALL stack clients:

- `plan-file --cr <id> --title <t> --cycle "C1 <label>" --cycle-kind red-green --cycle "C2 <label>" --cycle-kind verify --wave <w> --agent <id>`
  — wave resolves `--wave` > `$WORKFLOW_WAVE`; track from `$WORKFLOW_ROLE`. Cycle ids are
  SERVER-ASSIGNED.
- `--cycle` is repeatable and each occurrence REQUIRES its own `--cycle-kind`
  (`red-green | verify | fix`), paired positionally: the Nth kind is the Nth cycle's. A
  kind count that does not match the cycle count, or a cycle left without one, is refused
  **before anything posts** — nothing partial is filed. The legacy comma-split `--cycles`
  form is refused for filing.
- `--agent` is REQUIRED on every workflow verb, with no fallback: the identity is declared
  or the verb fails, and an unregistered id is refused by the server with 409 — there is no
  silent downgrade. The free-text `--orchestrator` label is retired; the registered
  `--agent` id IS the plan's orchestrator.
- `--release <label>` at filing also REGISTERS the CR in the queue in the same call (which
  makes `--wave` and `--title` required); omitted, nothing is claimed on the roadmap.
- `cycle-activate <cycle-id> --agent <id>` / `cycle-done <cycle-id> --agent <id>` — legal
  transitions planned → active → done.
- `cr-close --commit <sha> --agent <id>` — closes the CR on feature merge.
- `milestone --type <t> --agent <id>` — workflow timeline events (`gap-analysis |
  design-review | stage-flip | custom`); `cr-merged` fires automatically from cr-close.
- `gate-run --intent <goal> --agent <id>` — wave-boundary no-mistakes gate evidence
  (`kind:"gate"`), STREAMED. It replaces `gate-report`, which survives only as the retired
  one-shot and emits a `prefer-gate-run` discouragement warning (Crucible #1369).
- `--skip <steps>` on the gate verb is forwarded VERBATIM to `no-mistakes axi run --skip`.
  It exists because no-mistakes' `ci` step is PR-based: a git-flow project that merges
  directly has no PR for it to watch, so without `--skip` the gate blocks until
  `ci_timeout`. `--release <label>` names the release a gate gates (exempt from pruning
  until that release records) — omit it unless the gate really gates a release.

### Agent-naming header (bundled agent-naming skill)
- TDD-ROLE agents: `CR-<PROJ>-NNN-<cycle>-<ROLE>` (e.g. `CR-MDB-009-C1-GREEN`) — a
  readability habit, never a parsed key. The role itself is declared with `--role` at
  registration and is never inferred from the id (see *Register surface*).
- Orchestrator ops: `<agent-type>-<project>` (Model B solo: `vidushi-mdb`).
- The older spelling of the same habit, `CR-<PROJ>-NNN-<cycle>-<PHASE>`, named the retired
  per-phase register flag that Crucible removed in 0.1.0 with no alias. It is superseded by
  the `<ROLE>` form above and survives here only so the supersession is legible.

## Filed requests / gaps

- CR-CRU-030 + CR-CRU-036 delivery intimated on Sandesh (#1330, #1332); this mirror is
  updated on each intimation (never ahead of it).
- No divergent requests filed: Model B consumes the contract as specified; drift found
  during reconciliation goes upstream as a Crucible CR, not a local fork.

## Non-client adopters

Tools that adopt this envelope convention without being Crucible clients (e.g. `worktree-flow.py`) MAY flatten `context` to a minimal shape (e.g. a flat `project` field) — they perform no run ingestion, so the classification object does not apply. Reconciliation passes must not read this as drift.
