# CR-MDB-099 — Every project verb declares the project's test tools to Crucible, per modality

**Status:** PENDING — **SEED, not the finished spec** (filed 2026-11-04 by the user's rulings, DN §D29; the
user's suggestion relayed by Crucible #1528; widened 2026-11-08 by Crucible #1546 and the user's answers,
DN §D29 amendment). Gap analysis, the spec and its pre-review happen in order when
this CR starts.
**Type:** feature (`init`, `agents`, `migrate`; stack data)
**Priority:** P1 — release 1.0.0, wave 2 (user 2026-11-04; board-authoritative: read `queue`).
**Depends on:** CR-MDB-082 (`migrate` for a governed project, which this step joins) on the board; off the
board, Crucible 0.4.0 released and installed in production (CR-CRU-225/226, the `crucible.targets`
contract; CR-CRU-202/233, rust's `[targets.*]`), and Crucible's installer shipping the shared declaration
schema (DN §D29 amendment; Crucible's work, not on Model B's board).
**Labels:** scaffold, migrate, crucible, stacks, bun, rust, contract
**Design reference:** DN-multi-harness-deploy-model §D29 (this CR's rulings); Crucible #1521, #1525, #1528, #1530, #1546;
CR-MDB-055 (adoption inherits the step).

## Context

From Crucible 0.4.0, a bun project declares its tests in `package.json`'s `crucible.targets`, which the
client reads on every run (#1521, corrected by #1528):

- the table is keyed by script name; the tier verbs and the gate see only `test:<tier>` scripts (a tier is
  the script name, not an entry field);
- each entry has a `framework` (`bun-test`, `vitest`, `playwright`, `playwright-bdd`) and exactly one of
  `junit` (`"flag"`, bun-test only, or `"env:<VAR>"`) or `stream` (`{"codec": "crucible-events", "path":
  "env:CRUCIBLE_STREAM"}`, with Crucible's shipped reporters under `$CRUCIBLE_REPORTERS`);
- `console` is optional (never with `stream`); `coverage` is optional and today only `lcov`, on a `bun-test`
  entry with `junit: "flag"`;
- `"test": true` marks at most one entry: the script `test` runs;
- CR-CRU-226 refuses the older `crucible.testScript`, `reportPath` and `rawReport`, with no fallback.

For a vitest project (#1525): key the entry `test:<tier>`, use the stream form, and add
`${CRUCIBLE_REPORTERS}/vitest-crucible.ts` to `vitest.config.ts` when `CRUCIBLE_REPORTERS` is set.

Model B writes no `crucible.*` key into a project today; only the bun stack file and its agent renders cite
the older keys (the 0.4.0 doc-sync moves those).

## Scope (seed)

1. **The step:** for each of the project's stacks with a declaration, the tool per modality — unit,
   regression, BDD where needed, coverage — asked without `--yes`, detected and defaulted with it; never a
   prompt under `--yes`.
2. **`init`** writes the declaration fresh (`crucible.targets` on bun), with the framework's wiring where it
   needs one (the vitest reporter in `vitest.config.ts`).
3. **`migrate`** (CR-MDB-082) detects the tools and the existing declaration, older keys included, proposes
   the table and asks.
4. **`agents`** brings an older declaration up to the current shape.
5. **The schema is Crucible's, read at run time** (user 2026-11-08, superseding 2026-11-04's "the
   vocabulary lives in Model B"; DN §D29 amendment). The writer reads the machine-readable schema
   Crucible's installer ships beside the clients (listed in `~/.crucible/crucible-clients.json`); when it
   is absent, the step refuses with Crucible's install command and keeps the verb's `ok`. Crucible's
   installer writes through the same schema, so the two cannot drift. A new contract,
   `contracts/crucible-declaration.md`, records the interface (which triggers the pre-review). The "Stack
   declaration changes" section of each Crucible release's notes (#1530) still tells Model B what changed.
5a. **Bun and rust in this CR** (user 2026-11-08): bun's `package.json` `crucible.targets` and rust's
   `crucible.toml` `[targets.<profile>]` (`framework = "nextest"`), so nai is upgraded through the scaffold.
   Arduino (CR-CRU-203), maven (CR-CRU-237), python and go each get one small Model B CR, filed when their
   Crucible release notes arrive.
6. **The project's own lines are kept:** the step changes only the declaration's keys, never the project's
   scripts or other `package.json` content without asking.

## To measure at gap analysis

- 0.4.0's "Stack declaration changes" section against this seed (fields, the `test:` keying, the
  reporters' paths).
- Where a project's existing test tools can be detected (scripts, dev dependencies, config files) and what
  a `--yes` default is when nothing is detected.
- How the step writes `package.json` without disturbing its formatting, with the stdlib only.
- CR-MDB-094 (generated files gitignored): the declaration is the project's own committed file, not a
  generated one.
- The schema file Crucible's installer ships: its path, format (stdlib-readable: JSON or TOML) and version
  field, and how Model B reports a schema newer than it can write.
- How the step edits `crucible.toml` with the stdlib only (no TOML writer: `config.py`'s hand-rolled
  serializer, or a table-scoped text edit that keeps the `[client]`, `[gate]` and `[limits.*]` tables
  and the project's comments).
- The re-score (8 points before the widening; 13 after, user 2026-11-08).
