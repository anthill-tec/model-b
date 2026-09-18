# CR-MDB-017 — Client-verb contract sync: the owned bundles still teach the retired `--phase` flag

**Status:** PENDING
**Type:** maintenance
**Priority:** P1 (blocks release 0.1.0 — every `register` example we ship is non-executable against the released clients)
**Depends on:** CR-MDB-016 (Model B owns the seven bundles outright)
**Labels:** crucible, skills, contract, patch
**Phase:** Wave 5
**Design reference:** `~/.crucible/clients/STATUS-CONTRACT.md` (installed, manifest-discoverable) §"Agent identity and role" · §"The identity source is an enumeration" · §"The agent identity is declared, never fabricated" · §"The cycle binding is declared at registration" (the status-envelope contract **document**, version 2.0.0) · `skills-src/CRUCIBLE-HANDOVER.md` §Maintenance-contract · Sandesh #1357, #1373 (Crucible's independent confirmation of the `--phase` drift and the vscode auto-attach claim, 2026-09-18)

## Context

Crucible renamed the registration classification flag `--phase` → `--role` fleet-wide as a
**clean break** — no alias, no dual-key handling on the wire — and made the cycle
attachment a registration-time binding. The whole delta shipped in their **0.1.0**, their
first public release (confirmed Sandesh #1359: `git grep -- '--phase' 0.1.0 -- clients/`
has no hits, and CR-CRU-044/056/059 are contained in `0.1.0`, `0.1.1`, `0.1.2`). Their
latest release is **0.1.2**; the client-surface delta for both 0.1.1 and 0.1.2 is NONE.
**Model B's bundles have therefore been stale since Crucible's very first release.**

The released contract, verified 2026-08-27 against all five clients as PUBLISHED (now re-verified at the installed `~/.crucible/clients/`)
and confirmed by Crucible in #1359:

- `register --agent <id> --role <ROLE>` — the enumeration is case-exact:
  `RED | GREEN | FIX | VERIFY | ORCHESTRATOR | report` (five uppercase, `report`
  lowercase). The Python clients make `--role` argparse-REQUIRED, so omitting it exits
  non-zero and sends nothing; a registration that reaches the server without a valid role
  is refused **400**: `role is required and must be one of RED | GREEN | FIX | VERIFY |
  ORCHESTRATOR | report (got no role field)`.
- `--cycle <int>` is **not** argparse-required — the SERVER owns the per-role rule.
  `RED|GREEN|FIX|VERIFY` must bind an ACTIVE cycle of an OPEN plan; an unbound TDD
  registration is refused **409** with the verbatim message
  `role RED requires a cycle binding — register with --cycle <cycleId>` (em dash U+2014),
  enforced at the route boundary before any write, so no agent row is created.
  `ORCHESTRATOR` and `report` may register unbound.
- `--phase` no longer exists: zero occurrences across the five clients and
  `_crucible_axi.py`, at every released tag.
- The agentId is FREE-FORM. The role is never inferred from its shape — an id ending
  `-GREEN` registered with `--role RED` classifies as RED.
- `--source` is constrained to `claude-md | package-json | git-repo | manual`; a value
  outside the enumeration is refused server-side with 409 and nothing is stored. Absent is
  legal. It exists on the rust/mvn/arduino clients as of 0.1.0.
- Register wire keys: `projectKey`, `agentId`, `role`, `cycleId`, `status`, `message`,
  `identity{displayName, source, repoPath}`. `phase` appears nowhere in the wire contract.

**Surfaces (verified 2026-08-27).** Every bundle Model B owns still teaches the retired
flag, and none of them mentions either replacement:

- `skills-src/crucible/SKILL.md:17` — `register --agent <id> --phase <PHASE>`
- `skills-src/crucible/SKILL.md:35` — "Phase is metadata, not identity: pass it via
  `--phase` on register." A SECOND occurrence in the same file, and its substance is also
  wrong now, not just its flag name: the role is **declared** at registration, never
  "metadata" attached to an identity.
- `skills-src/crucible-report-arduino/SKILL.md:37`, `-bun/SKILL.md:36`,
  `-java/SKILL.md:32`, `-python/SKILL.md:39`, `-rust/SKILL.md:38` —
  `register --agent … --phase RED`
- `skills-src/memory-templates/java-orchestration.md:17` —
  `register --phase RED|GREEN|FIX|VERIFY|ORCHESTRATOR`
- `skills-src/model-b/SKILL.md:45` — "ONE identity; phase via `--phase`, never embedded in
  the id". The orchestration skill, not a Crucible bundle — it restates the same retired
  contract and is in scope precisely because the ACs gate all of `skills-src/`.
- **Nine surfaces total** (re-measured at gap-analysis, 2026-09-18), not the seven this
  section originally listed.
- `--role` occurs **zero** times across `skills-src/`. `--cycle` also occurs zero times **as
  a flag** — but a naive substring grep returns two hits, `--cycles` on `plan-file`
  (`crucible/SKILL.md:95`, `model-b/SKILL.md:47`). Every gate below therefore matches
  `--cycle` on a word boundary; a substring match is a false green by construction.
- `crucible-report-vscode/SKILL.md` carries **no CLI register example at all** — only the
  v2 endpoint rows (`:234-235`) and the prose rule at `:259`. It is an API-path bundle, and
  no `vscode-crucible.py` exists or will (user ruling; Sandesh #1370). Its exemption from
  every client-flag gate is therefore EXPLICIT below, never a silent skip.

These bundles are force-included into the `modelb-axi` wheel and deployed to the global
skill store, so an agent that follows them issues a command that cannot parse.

Two repo-side facts make this more than a text edit:

- `tests/test_crucible_skill.py:169` **positively requires** the literal `--phase` in
  `skills-src/crucible/SKILL.md`. Model B's own suite pins the removed flag.
- The inherited semantic guard suite could not have caught this. Its
  `scriptSubcommandPin` helper (`docs/research/crucible-clients-skills-guard.test.ts:301-304`)
  matches only the substring `"<script> <subcommand>"` and never inspects flags. The
  suite is also mis-described in the queue register as "22-test": the file carries **19
  static `test()` declarations expanding to 37 runtime cases** across 7 `describe` blocks.
- The byte-identity fidelity gates that froze the imported bundles now self-skip
  (`tests/test_skills_handover.py:190-194`, `tests/test_installer_assets.py:223-227`)
  because the origin Crucible-bundled `clients/skills/` was retired after the handover, so
  `skills-src/` is editable without violating an AC.

## Scope

### §S1 — Re-pin the assertion that requires the retired flag
`tests/test_crucible_skill.py:169` asserts the PRESENCE of `--phase` in
`skills-src/crucible/SKILL.md`. Invert it: assert the presence of `--role` and the absence
of `--phase` as a register flag. Sanctioned amendment — the pinned contract was superseded
upstream.

A second, independent re-pin belongs in the same section: the suite's ONE recorded baseline
failure, `test_ac7_repo_agents_md_no_longer_claims_workflow_cycle_id_injection`, is
self-tripping rather than measuring drift — both `AGENTS.md` occurrences of
`WORKFLOW_CYCLE_ID` it counts are META text (the grep-gate-family description and the
baseline sentence naming this very failure), while the guarantee the assertion exists to
protect is intact everywhere the variable could actually be injected. Re-point the
assertion at the CLAIM ("no sentence may say the wrapper injects `WORKFLOW_CYCLE_ID`")
rather than a bare whole-file substring count, so documenting the prohibition and violating
it are distinguishable again.

### §S2 — Sync the register contract in `skills-src/crucible/SKILL.md`
Replace the `register --agent <id> --phase <PHASE>` instruction (`:17`) with the released
surface: `--role` required and enumerated; `--cycle` mandatory for the four TDD roles and
refused (409) when absent; `ORCHESTRATOR`/`report` may register unbound; the agentId is
free-form and never parsed for role; `--source` enumerated with absent legal. Keep the
existing ingest-is-heartbeat statement intact — it is unaffected.

Rewrite the second occurrence at `:35` on its MEANING, not just its flag name: the role is
declared at registration from the case-exact enumeration, and identity (the free-form
agentId, assigned by the dispatcher, never minted by the agent) is a separate axis. The
current "phase is metadata, not identity" phrasing survives only as the identity half.

### §S3 — Sync the five per-stack bundles with a live client
`crucible-report-{arduino,bun,java,python,rust}/SKILL.md`: every `register` example
carries `--role <ROLE>`, and every example whose role is `RED|GREEN|FIX|VERIFY` also
carries `--cycle <id>`. No bundle retains `--phase`.

`crucible-report-vscode/SKILL.md` has **no `register` example to sync** — confirmed at
gap-analysis (§Surfaces, DRIFT-4) — and gets NO register-flag edit under this heading. It
stays fully in scope for §S5's flag-surface guard, which asserts its exemption BY NAME
rather than passing it by accident.

It DOES need one prose fix, independently confirmed by Crucible (Sandesh #1373, measured on
their tree 2026-09-07): `:54`'s comment reads `# No client-side cycle-id plumbing: the
active cycle auto-attaches server-side.` CR-CRU-056 deleted that mechanism — cycle
attachment is now an explicit `--cycle <id>` binding declared AT registration, which the
server then stamps onto every subsequent ingest (the same registration-time-binding fact
this CR's Context section already establishes from `STATUS-CONTRACT.md`). Rewrite the
comment to state the binding is declared at registration, not that it auto-attaches.

### §S4 — Sync the project-layer conventions that restate the contract
- `skills-src/memory-templates/java-orchestration.md:17` — `--phase` enumeration becomes
  the `--role` enumeration with the binding rule.
- `skills-src/model-b/SKILL.md:45` — the naming-registry bullet's parenthetical becomes
  "role declared via `--role`, never embedded in the id"; the ONE-identity rule and the
  `<agent-type>-<project>` readability habit stay as they are.
- `AGENTS.md` — two stale sentences. The agent-ids sentence reads as if the id encodes the
  phase: state that the id is a free-form readability habit, `--role` declares the role,
  and TDD roles bind `--cycle`. The plan-filing sentence still passes
  `--orchestrator vidushi-mdb`: **`plan-file --orchestrator` was REMOVED** — the registered
  `--agent` id IS the plan's orchestrator now (installed client `--help`, measured 2026-09-18:
  "the free-text --orchestrator label is retired"). Drop the flag, keep `--wave`, and add the
  `--cycle-kind` requirement below.
- **§S4a — the `plan-file` surface is a SECOND non-executable instruction, same defect class as
  `--phase`.** Measured against the INSTALLED PRODUCTION client (0.2.2) on 2026-09-18, not
  inferred: `--cycle` is repeatable and each occurrence REQUIRES a paired `--cycle-kind`
  (`red-green | verify | fix`, positional — the Nth kind is the Nth cycle's, a mismatch or a
  cycle left without one is refused before anything posts); the comma-split `--cycles` form is
  **REFUSED for filing**; `--agent` is REQUIRED on every workflow verb with no fallback (an
  unregistered id is refused 409); and `--release`, when given, REGISTERS the CR in the queue in
  the same call (making `--wave` and `--title` required). Four surfaces teach the refused form
  and must be corrected: `skills-src/crucible/SKILL.md:95`, `skills-src/model-b/SKILL.md:47`,
  `contracts/crucible-envelope.md:129-131`, `AGENTS.md:145` — plus PRD §D3.4 (`:39`), handled in
  §S4c. Proven in use this session: filing a plan with `--cycles` is impossible, and every CR
  planned onto the 1.0.0 roadmap went through `--cycle`/`--cycle-kind` pairs.
- `contracts/crucible-envelope.md` — record the role/cycle-binding facts, cite the
  status-envelope contract document by its DOCUMENT version (**verified still `2.0.0`** at
  `~/.crucible/clients/STATUS-CONTRACT.md`, 2026-09-18), correct the `plan-file` signature per
  §S4a, replace `gate-report` with `gate-run` per §S4b, and note `--source` on the
  rust/mvn/arduino clients plus `WORKFLOW_CYCLE_ID` gone while
  `WORKFLOW_ROLE`/`WORKFLOW_WAVE`/`WORKFLOW_CYCLE` remain.
- **§S4b — `gate-run` is the gate verb; `gate-report` is the one-shot legacy.** `gate-run`
  STREAMS and emits a `prefer-gate-run` discouragement warning from `gate-report` (Crucible
  #1369). Two surfaces still name the wrong one: `skills-src/crucible/SKILL.md:97` and
  `contracts/crucible-envelope.md:136`. Both carry two flags that matter to THIS project
  specifically (measured from the installed client): `--skip`, which exists because
  no-mistakes' `ci` step is PR-based and **a git-flow project that merges directly has no PR
  for it to watch — without `--skip` the gate blocks until `ci_timeout`**, which is exactly
  Model B's merge model; and `--release`, which names the release a gate gates (a gate naming
  one is exempt from pruning until that release records). The wave-boundary gate sentence in
  `AGENTS.md` inherits both.
- **Released-only rule — RE-MEASURED 2026-09-18, and the previous list is now WRONG.** The
  PRINCIPLE stands: no Model B doc may teach a verb absent from a Crucible RELEASE. The
  enumeration does not. Against the installed production client (0.2.2), these are all PRESENT
  and therefore legitimate to document: the `queue` read verb, `queue-file` (+ `--from-file`),
  and `milestone --released-at/--crs/--packages/--repair-provenance`, plus the whole
  declared-roadmap set (`release-propose`, `cr-plan`, `wave-sequence`, `cr-depends`,
  `cr-supersede`, `cr-void`, `next`). They were correctly develop-only when #1359 was written;
  0.2.0 has since RELEASED and production now runs 0.2.2, so the old ban would forbid
  documenting verbs this project already uses on its own board. **The develop-only item to
  forbid instead is `portRule` / the `/api/health` listener block (CR-CRU-139) — NOT in 0.2.2,
  0.3.0-bound, explicitly cautioned by Crucible in #1373.** Verified absent from every Model B
  doc today; the rule is therefore a guard against regression, not a cleanup. The banned-string
  gate must name the version actually unreleased at authoring time, never a hardcoded `0.2.0`.
- **Upstream traps — RE-MEASURED against the INSTALLED 0.2.2 client, 2026-09-18; both original
  claims have changed and one is now void.** (a) `rust-crucible.py`'s docstring register
  examples (`:71` and its sibling) are now `--role`-CORRECT but still omit `--cycle`, so they
  remain guaranteed 409s for a TDD role — the trap survives in a new shape, and any Model B text
  copying them inherits it. (b) The claim that `crucible-axi register` cannot bind a cycle is
  VOID: the installed `crucible-axi` exposes only `{install, serve, uninstall}` and has no
  `register` verb at all, so there is no TypeScript registration surface to mis-copy. Any Model
  B text naming a registration surface names the Python clients — the conclusion is unchanged,
  but it now rests on "the other CLI does not register" rather than "it registers wrongly".
- **§S4c — the design docs Model B OWNS carry the same stale surface** (user directive
  2026-09-18: the sweep includes our own PRD/DNs). `docs/research/PRD-model-b-rationalization.md`
  §D3.4 (`:39`) states the plan/cycle idiom with the refused `--cycles` form; §D7 (`:62-68`)
  records a 3-route endpoint list (`/api/v2/agents/{register,unregister}`,
  `/api/v2/runs/{parsed,compile}`, `/api/v2/plans`) that predates the queue, release-proposal,
  milestone and gate routes this project now uses, and still carries the REQUEST for a
  `vscode-crucible.py` that the user has since DECLINED (Sandesh #1370) — an open request
  contradicting a settled ruling invites a future CR to re-raise it.
  `docs/research/DN-rationalization-plan-review.md:77` records "ALL clients gain the universal
  plan/cycle verbs" as an ASK; it is delivered fleet-wide and should read as such. `:99`'s
  per-stack Crucible smoke criterion (`register → test → unregister`) is still the right gate
  but its `register` leg must carry `--role` and, for a TDD role, `--cycle`, or the smoke test
  cannot pass. Corrections are factual only; no design decision is reopened.

### §S5 — The guard that would have caught it
Port the transferable families of the inherited suite into a new stdlib `unittest` module
`tests/test_skill_bundle_guards.py` — per-bundle v2-endpoint truth, no unmarked v1 legacy,
ingest-is-heartbeat semantics, `tier` + `WORKFLOW_CYCLE` presence, and real client verbs in
examples — **strengthened with a flag-surface check** that the original lacked, and extended
to the arduino bundle the original never covered. The two agent-protocol families are NOT
ported: `heartbeat.sh` and a standalone `agent-protocol` skill are ratified out of existence
and asserted absent by `tests/test_skills_handover.py:130-137` and `:360-384`.

**The flag-surface check asserts POSITIVE facts about our own text, and reads no client.**
The original framing — "fails when a flag is absent from the corresponding client's
`--help`" — was cut at gap-analysis: it shells out to a sibling checkout, and the mitigation
it required (an allow-list of Crucible's flags maintained in OUR test module) is a second
source of truth for a surface we do not own. It rots silently, and a stale entry is
indistinguishable from a real hit. The check therefore asserts, over `skills-src/` only:
every `register` example carries `--role` with a value from the case-exact enumeration;
every example whose role is `RED|GREEN|FIX|VERIFY` also carries `--cycle` (word-boundary
match); and `--phase` appears nowhere. A fixture case carrying `--phase` proves the guard
bites. Zero coupling, same protection — and the guard stays honest when Crucible's flags
move next, because it never claimed to mirror them.

`crucible-report-vscode` is covered for endpoint/heartbeat/tier truth and **explicitly
exempted, by name, from the register-flag families** — it has no CLI register example and no
client. The exemption is an assertion in the module (the bundle is named in an
`API_PATH_BUNDLES` constant and the flag tests skip it deliberately), never an incidental
zero-match that would pass whether or not the bundle had drifted.

### §S6 — The generator emits the retired flag too
The bundle sweep above does not reach the sub-agent definitions, and they carry the same
defect at its source. `--phase` is hard-coded in all four role templates — not in the stack
data — and is appended directly after the interpolated register command:

- `generator/templates/red.md.tmpl:24` — `${register_command} --phase RED`
- `generator/templates/green.md.tmpl:29` — `${register_command} --phase GREEN`
- `generator/templates/verify.md.tmpl:26` — `${register_command} --phase VERIFY`
- `generator/templates/fix.md.tmpl:23` — `${register_command} --phase FIX`

All 16 generated definitions under `generator/agents/` therefore instruct a registration
that cannot parse, and `--role` occurs in only two files anywhere under `generator/`.
`--cycle` occurs nowhere, so even a corrected `--role` would be refused 409 for the four TDD
roles — every generated agent is currently unable to register against a released Crucible.

**Content sourced from Crucible directly (Sandesh #1364/#1366), not re-derived from their
client `--help` alone** — their team hit the assigned-vs-minted agent-id defect themselves (5
permanently mis-attributed runs) and their tier-guidance rewrite is validated against their
own six-stack fleet. One correction to the drift this section originally measured: the
deployed `~/.claude/agents/rust-*-agent.md` files are **not** Crucible's — no
`generator/stacks/rust.toml` exists in this repo, the files are plain (non-symlinked), and
Crucible confirmed their own rust set is separately located and already fixed.

**Rust is out of THIS CR's scope because CR-MDB-024 owns it — not because it is orphaned.**
The earlier "orphaned set" framing was retracted at gap-analysis: design-lineage tracing
(`DN-rationalization-plan-review.md:72`, `CR-MDB-008:24`) shows the four rust definitions
PREDATE Model B and were a deliberate wave-1 descope justified by size, and the user ruled
that rust IS a language stack and belongs in the generator. CR-MDB-024 (which depends on
this CR) creates `generator/stacks/rust.toml`. Nothing in this CR may assert that file's
absence.

**§S6a — the registration line, shared across all four templates.** Each template's register
step becomes `--role <ROLE>` with the case-exact enumeration, and the four TDD templates
additionally carry `--cycle <cycleId>`, stated as REQUIRED for the four TDD roles (the server
409s an unbound TDD registration even once the flag name is right) and absent for
`ORCHESTRATOR`/`report`. The agent id is already sourced correctly in the existing template
text ("the agentId from your dispatch prompt" — `red.md.tmpl:22` and its siblings); this is
confirmed adequate, not rewritten, since Crucible's assigned-not-minted rule is what that
phrasing already encodes.

**§S6b — the tier-guidance section is PER-STACK, never a generic block.** This is a second,
independent defect beyond `--phase`: a single generic tier-guidance paragraph is factually
wrong for three of the four stacks, because the toolchains do not share a tier mechanism.
Per Crucible's own fleet mapping — arduino has three separate build systems that ARE the
tiers (native-host `unit`, `arduino-cli` `compile`/`check`, HIL as the unreachable-from-native
integration/e2e end, with ArduinoFake as the explicitly-labelled middle ground); bun and
python have no native tier split at all and must drive a project-DECLARED target (bun:
`test:unit`/`test:integration`/`test:regression` scripts; python: a `--start-dir`/`--pattern`
declaration) rather than hand-picking files; quarkus already has the split via Maven itself
(surefire `*Test` = unit, failsafe `*IT` = integration) and the guidance's job is to forbid
renaming an `*IT` to `*Test` to dodge a slow gate.

The shared preamble names the **fleet-uniform tier vocabulary** and then leaves the judgment to
the agent. Crucible 0.2.0 (CR-CRU-111 §S1, confirmed by Sandesh #1369/#1372) collapsed the six
tier verbs into ONE shared registrar, so all five clients now carry exactly
`unit module integration e2e bdd regression` plus `test`, `pre-merge-gate` and `check` — verb
counts from each client's own `--help` at `70224d6`: bun 35, python 35, rust 43, mvn 37,
arduino 35. The preamble therefore states one vocabulary rather than per-stack run verbs, and
carries the judgment rules ("which tier a feature needs is your call; how it runs locally is
your stack's business… a tier names the DEPENDENCY a test takes, never its size… never report a
run under a tier it did not earn"). **A tier a stack cannot honour must say so explicitly**
(CR-CRU-111 §S2) — that is the per-stack half's job, and it is why the split is two halves
rather than one block: the VOCABULARY is uniform, the HONOURABILITY is not.

The preamble is identical across all stacks and renders ONCE from the template, immediately
followed by the per-stack half rendered from each stack's own `tier_guidance` TOML key — this is
the `templates × stacks/*.toml` shape the generator already uses for the existing
`mechanics`/`red`/`green`/`verify`/`fix` keys, extended with one more per-stack string, not a new
mechanism.

Regenerate all 16 definitions with `python3 generator/build.py build` and prove `--check`
clean; no generated file is hand-edited.

## Acceptance criteria

### §S1
- [ ] `tests/test_crucible_skill.py` contains no assertion requiring the substring
      `--phase`; it asserts `--role` present in `skills-src/crucible/SKILL.md`.
- [ ] `test_ac7_repo_agents_md_no_longer_claims_workflow_cycle_id_injection` no longer
      asserts a bare `AGENTS.md.count("WORKFLOW_CYCLE_ID") == 0`. Measured at gap-analysis:
      both occurrences are META — `AGENTS.md:135` describes the grep-gate family and `:138`
      is the baseline sentence naming this very failure — while the guarantee itself HOLDS
      (zero occurrences under `modelb_axi/`, `scripts/`, `generator/`, `skills-src/`; the
      only other mention, `hooks-src/schema.md:49`, likewise asserts zero). The gate as
      written forbids naming what it forbids. Re-point it at the CLAIM (no sentence may say
      the wrapper injects `WORKFLOW_CYCLE_ID`) or delete it in favour of the product-surface
      check that already passes; a second sanctioned re-pin in the same file as §S1's.
- [ ] `python3 -m unittest discover -s tests -t .` shows **zero failures** — this CR clears
      the last item in the recorded 240/1F/12S baseline, and `AGENTS.md`'s baseline sentence
      is updated to say so.

### §S2 / §S3 / §S4
- [ ] Zero occurrences of `--phase` under `skills-src/`, `contracts/`, and `AGENTS.md` —
      covering all NINE measured surfaces, explicitly including `skills-src/crucible/SKILL.md`
      lines 17 AND 35 and `skills-src/model-b/SKILL.md:45`.
- [ ] Every `register` example under `skills-src/` carries `--role` with a value from
      `{RED, GREEN, FIX, VERIFY, ORCHESTRATOR, report}`.
- [ ] Every `register` example under `skills-src/` whose `--role` is one of
      `{RED, GREEN, FIX, VERIFY}` also carries `--cycle`, matched on a WORD BOUNDARY so that
      `--cycles` (the `plan-file` flag, present at `crucible/SKILL.md:95` and
      `model-b/SKILL.md:47`) can never satisfy it.
- [ ] `skills-src/crucible/SKILL.md` states, in substance: the case-exact `--role`
      enumeration; that `--cycle` is required for `RED|GREEN|FIX|VERIFY` **by the server,
      not by argparse**, refused 409; that a missing or out-of-enum role is refused 400;
      that `ORCHESTRATOR`/`report` may register unbound; and that the agentId is free-form
      with the role never inferred from it.
- [ ] Zero occurrences of `--orchestrator` paired with `plan-file` under `skills-src/`,
      `contracts/`, `AGENTS.md` and `docs/research/` (retired; the registered `--agent` id is
      the plan's orchestrator).
- [ ] **Zero occurrences of the REFUSED `--cycles` form paired with `plan-file`** under
      `skills-src/`, `contracts/`, `AGENTS.md` and `docs/research/`; every `plan-file` example
      instead shows repeated `--cycle` each with its own `--cycle-kind` from
      `{red-green, verify, fix}`, and states that a count mismatch is refused before anything
      posts. (§S4a — measured against the installed 0.2.2 client.)
- [ ] Every documented workflow-verb invocation carries `--agent`, and the docs state that an
      unregistered id is refused 409 with no fallback.
- [ ] No Model B doc names `gate-report` as the gate verb; `gate-run` replaces it at
      `skills-src/crucible/SKILL.md:97` and `contracts/crucible-envelope.md:136`, and the
      `--skip` rationale is stated (no-mistakes' `ci` step is PR-based; a git-flow project
      merging directly has no PR, so the gate blocks until `ci_timeout` without it). (§S4b)
- [ ] **The released-only gate is re-pinned, not inherited.** `queue-file`, `--from-file`,
      `milestone --released-at/--crs/--packages/--repair-provenance` and the declared-roadmap
      verbs are NOT forbidden — all are present in the installed 0.2.2 client and this project
      uses several on its own board. The forbidden item is `portRule` / the `/api/health`
      listener block (CR-CRU-139, 0.3.0-bound): zero occurrences under `skills-src/`,
      `contracts/`, `docs/` and `AGENTS.md`. No AC hardcodes `0.2.0` as unreleased.
- [ ] `skills-src/memory-templates/java-orchestration.md` documents the `--role`
      enumeration and the binding rule; no `--phase` remains.
- [ ] `contracts/crucible-envelope.md` cites `STATUS-CONTRACT.md` **document version
      2.0.0** — verified unchanged at `~/.crucible/clients/STATUS-CONTRACT.md` on 2026-09-18 —
      and never implies a Crucible PRODUCT version of `2.0.0`. The version axis stays explicit:
      the product version is `0.2.x`, `/api/v2` is the API generation, `2.0.0` is that one
      contract document's own semver.
- [ ] Documented Crucible release facts match the INSTALLED PRODUCTION install, not #1359's
      now-superseded snapshot: product version **`0.2.2`** (per
      `~/.crucible/crucible-clients.json`'s own `version`), install entry point
      `crucible-axi install [--target-dir <dir>]` with default `~/.crucible`, run verb
      `crucible-axi serve`, and `uninstall` as the third subcommand. No doc states `0.1.2` as
      the latest release.
- [ ] §S4c: `docs/research/PRD-model-b-rationalization.md` §D3.4 no longer shows the refused
      `--cycles` form; §D7's endpoint list either covers the routes this project actually uses
      (queue, release-proposals, milestones, gates) or states that it enumerates a subset; and
      §D7's `vscode-crucible.py` REQUEST is recorded as DECLINED (user ruling, Sandesh #1370)
      rather than left open.
- [ ] §S4c: `docs/research/DN-rationalization-plan-review.md:77` reads as DELIVERED rather than
      requested, and `:99`'s per-stack smoke criterion's `register` leg carries `--role` plus
      `--cycle` for a TDD role.
- [ ] `crucible-report-vscode/SKILL.md:54`'s comment no longer claims the active cycle
      "auto-attaches server-side"; it states the binding is declared explicitly via
      `--cycle <id>` at registration (CR-CRU-056, confirmed Sandesh #1373).

### §S5
- [ ] `tests/test_skill_bundle_guards.py` exists, is stdlib `unittest`, spawns no
      subprocess and starts no server.
- [ ] It reads no client source or `--help` output, and contains no allow-list mirroring
      Crucible's flag surface — every assertion is about text under `skills-src/`.
- [ ] It covers all seven owned bundles including arduino.
- [ ] It fails when any `register` example under `skills-src/` carries `--phase`, omits
      `--role`, uses an out-of-enum role, or omits `--cycle` on a TDD role — each asserted by
      a fixture case, so the guard is proven to bite rather than assumed to.
- [ ] `crucible-report-vscode` is named in an explicit API-path exemption constant and is
      excluded from the register-flag families BY NAME; the module asserts the exemption
      exists, so the bundle can never pass those families by having no register example.
- [ ] It asserts zero `WORKFLOW_CYCLE_ID` occurrences under `skills-src/` — scoped to
      register/ingest examples and prose that CLAIMS the variable is set, not a bare
      whole-tree string count, which would false-red the moment a bundle documents the
      retired variable (the exact defect §S1 re-pins in `test_crucible_skill.py`).
- [ ] No test asserts the existence of `skills-src/agent-protocol/` or any `heartbeat.sh`.

### §S6
- [ ] Zero occurrences of `--phase` under `generator/` (templates and generated agents).
- [ ] All four role templates emit `--role` with the case-exact role for that template.
- [ ] `red`, `green`, `verify` and `fix` templates emit `--cycle` and state the binding rule
      above the command the agent will run.
- [ ] All 16 files under `generator/agents/` carry `--role` and `--cycle`, and
      `python3 generator/build.py --check` exits 0 with no drift.
- [ ] No file under `generator/agents/` is hand-edited — every change arrives via
      `build.py build` from a template or stack edit.
- [ ] The shared tier-guidance preamble renders IDENTICALLY across all four stacks'
      generated agents, from the template, once.
- [ ] The preamble names the fleet-uniform tier vocabulary exactly — `unit`, `module`,
      `integration`, `e2e`, `bdd`, `regression` — and no generated agent names a
      stack-specific run verb in its place.
- [ ] Every stack's `tier_guidance` states explicitly which tiers that stack CANNOT honour
      (CR-CRU-111 §S2); a stack whose text is silent about an unreachable tier fails this
      criterion — arduino must name HIL as unreachable from the native host.
- [ ] Each of the four `generator/stacks/*.toml` carries its own `tier_guidance` key, and no
      stack's rendered tier text is a copy of another's — arduino names its three build
      systems and the ArduinoFake caveat; bun and python name a project-DECLARED target
      (never a hand-picked file list); quarkus names the surefire/failsafe split and forbids
      renaming `*IT` to `*Test`.
- [ ] This CR neither creates nor asserts the absence of `generator/stacks/rust.toml`.
      Rust belongs to CR-MDB-024 (which depends on this CR); the user ruled rust IS a
      language stack, so an AC asserting that file's non-existence would break its own
      dependent CR on landing and would re-assert a retracted "orphaned" claim.

## Estimated size

10 documentation files edited (1 routing skill, 6 bundles — 5 register-flag-synced plus
vscode's single auto-attach comment fix, confirmed by Sandesh #1373 — 1 memory template, 1
orchestration skill (`skills-src/model-b/SKILL.md`, added at gap-analysis — a second
`--phase` occurrence lives there), `AGENTS.md`, `contracts/crucible-envelope.md`), 4 role
templates edited, 4 stack TOMLs gain a `tier_guidance` key each, 16 agent definitions
regenerated, 2 assertions re-pinned in `tests/test_crucible_skill.py` (the `--phase`
substance re-pin and the `ac7` `WORKFLOW_CYCLE_ID` self-trip, added at gap-analysis), 1 test
module added (~7 methods, widened for the vscode exemption and the flag-surface family).
Docs, templates and tests only; no `modelb_axi/` code change.

## Risk

- The flag-surface guard reads NO client: it asserts positive facts about our own bundle
  text (§S5). The rejected alternative — shelling the client `--help`, mitigated by an
  allow-list of flags maintained in our test module — was cut at gap-analysis as a second
  source of truth for a surface Model B does not own. CR-MDB-020 decides how a client is
  LOCATED; nothing in this CR needs one.
- Re-pinning `tests/test_crucible_skill.py:169` is a sanctioned amendment, not a
  convenience: the assertion is inverted, never deleted.

## Non-goals

- No change to the clients themselves — they are Crucible's.
- No re-import of `agent-protocol` and no adoption of `heartbeat.sh`.
- No anchoring of the bundles' client paths (CR-MDB-020) and no installer change
  (CR-MDB-018).
