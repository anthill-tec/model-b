# CR-MDB-059 — Orchestration rules from Crucible's wave 7

**Status:** PENDING — spec (gap analysis and pre-review 2026-10-15).
**Type:** refactor (skills, references, contracts, `AGENTS.md`, `worktree-flow.py`)
**Priority:** P1 — release 1.0.0, wave 2.
**Depends on:** none (board-authoritative: read `queue`)
**Labels:** skills, orchestration, crucible, conventions
**Design reference:** PRD D5 (AMENDED 2026-10-15: orchestration rules adopted from Crucible #1433 §B)
and D3.4 (AMENDED 2026-10-15: cycle labels and agent ids); DN-model-b-language (LOCKED — cite,
never fork).

## Context

- **Already in the text:**
  - **Patch CRs:** scope found mid-CR goes into a patch CR (`orchestration-mainline.md`,
    `orchestration-track.md`, `cr-authoring`).
  - **Fix cycles:** a VERIFY finding is fixed in its own `fix` cycle appended after VERIFY
    (`orchestration-common.md`).
  - **`cycle-skip`:** documented in the `crucible` skill.
  - **"The spec wins"** over a brief, in the four agent templates.
  - **The board is reached only through the client:** the `crucible` skill ("Never hand-roll
    `curl`; the client is the interface") and Model B's `AGENTS.md`.
- **What the shipped text says today:**
  - **Board over HTTP.** The `crucible` skill's envelope section still invites reading the board
    over HTTP: "GETs also serve compact TOON … read them".
  - **Story points.** `cr-plan --points` is documented only as a flag. No rule says when a CR is
    scored or re-scored, or what to do above 13.
  - **Cycle labels.** The form is `C<n> <label> (§S…)`, in:
    - `model-b` SKILL §4.3;
    - the `crucible` skill's `plan-file` example;
    - `contracts/crucible-envelope.md`;
    - Model B's `AGENTS.md`.

    These numbers drift whenever a cycle is added.
  - **Agent ids.** TDD-role ids carry a positional tag (`CR-MDB-003-C1-GREEN`), in:
    - the `crucible` skill's Identity section;
    - `orchestration-common.md`'s parallel-agents example;
    - `contracts/crucible-envelope.md`;
    - `AGENTS.md`.

    `crucible/references/<stack>.md` writes `CR-<ACRONYM>-NNN-<cycle>-<PHASE>`, using the
    superseded `<PHASE>` spelling. `model-b` SKILL §4.1 gives only the orchestrator form, and says
    the role is "never embedded in the id".
  - **`worktree-flow.py status`** parses `C<n>` from commit subjects into a `cycle` field.
  - **Where the gate runs.** The `crucible` skill's "Who runs what" places the orchestrator's gate
    "with the verify cycle activated … as that cycle's LAST linked run". Its binding rules tell a
    long-running orchestrator to stay unbound.
  - **Shutdown.** The `shutdown` skill always finishes the plan's active cycle.
  - **Release fixes.** `git-workflow` § Releases calls a CR run during a release "highly
    discouraged", and files the release's own verification runs under `--release`, never beside
    `--cycle`.
  - **Not stated anywhere:** test leaks, a fix found during a release, servers the gate did not
    start, the release's test-hygiene CR.

## Scope

### §S1 — The board through client verbs only

- **The `crucible` skill.**
  - The opening sentence ("Never hand-roll `curl`; the client is the interface") is widened: the
    orchestrator reads and writes the board only through client verbs, never the HTTP API; where
    no verb fits, it says so and proposes one to Crucible.
  - The envelope section's "GETs also serve compact TOON … read them" becomes a description of
    what the clients receive. It is no longer an invitation to read over HTTP.
- **`orchestration-common.md`** states the same rule.

### §S2 — Story points

- **`cr-authoring`.**
  - Its filing rules: every CR is scored when filed, with `cr-plan --points` (a CR filed by
    `plan-file --release` is scored with `cr-plan --points`; `plan-file` takes no `--points`), on the
    scale 1, 2, 3, 5, 8, 13. 13 is the cap; a CR scoring more is split before
    it is filed.
  - The legacy-filing path (a project scaffolded before the board held the queue) scores each CR
    it files.
- **The `gap-analysis` skill.** The analysis re-scores the CR with `cr-plan --points`, re-sending
  its current title, release and wave. A CR the analysis finds above 13 is split before the
  pre-review. In multi mode a Track raises the re-score or split to Mainline, which runs
  `cr-plan` and files the split CRs.
- **`orchestration-mainline.md`.** Its filing order names the score in `cr-plan`.
- **The `crucible` skill.** Its `cr-plan` write-verb example carries `--points <n>`.

### §S3 — A brief adds no proof steps

`orchestration-common.md`'s brief rules: a brief states the scope, the approved spec (the spec
wins) and the definition's standard procedure; the orchestrator adds no extra proof steps, because
VERIFY and the gate catch drift.

### §S4 — Cycle labels, agent ids and the `worktree-flow` cycle field

- **Cycle labels carry no numbering.** A label is `<label> (§S…)`, and every `plan-file` example
  shows `--cycle "<label>"`. The examples are in:
  - `model-b` SKILL §4.3;
  - the `crucible` skill's plan verbs;
  - `contracts/crucible-envelope.md`;
  - Model B's `AGENTS.md`.
- **A TDD-role agent id carries the cycle's server id:** `CR-<ACRONYM>-NNN-<cycle id>-<ROLE>`. A
  concrete example is `CR-MDB-059-237-RED`. The form appears in:
  - the `crucible` skill's Identity section;
  - all five `crucible/references/<stack>.md` together (they are kept in parity), each moving to
    `<cycle id>-<ROLE>`;
  - `orchestration-common.md`'s parallel-agents suffix example, which keeps `-1` … `-N`;
  - `contracts/crucible-envelope.md`'s example id (its `<PHASE>` supersession line stays);
  - `pi-package/extensions/worktree.ts`'s docstring example;
  - Model B's `AGENTS.md` (the agent-ids line and the test-command examples).
- **`model-b` SKILL §4.1** gains the TDD form beside the orchestrator form, on its single line. The
  role is declared with `--role`; the role suffix in a TDD id is a readability habit, never
  parsed.
- **Model B's `AGENTS.md`** uses the new forms:
  - the `stage-flip` milestone label is `"<CR> <cycle label> done"`;
  - its baseline citation reads "at CR-MDB-NNN's `<cycle label>` cycle".
- **Unchanged:** the spec pre-review id `CR-<ACRONYM>-NNN-SPEC-REVIEW` and the orchestrator ids.
- **`worktree-flow.py status`:** the `C<n>` parse and the `cycle` field are removed from the
  human board and the envelope. The board holds a CR's cycles.

### §S5 — The pre-merge gate runs inside the last cycle

**`orchestration-common.md` § Close-out.**

The CR's close-out order:

1. Merge `develop` into the feature branch until behind=0.
2. Run the pre-merge gate while the plan's last cycle is still active. That cycle is the VERIFY
   cycle, or the last `fix` cycle appended after it. The gate runs under the orchestrator's own
   id, bound to that cycle:
   - pass `--cycle <last cycle>` on the gate's first run;
   - where that verb takes no `--cycle`, first `register --role ORCHESTRATOR --cycle <last>`;
   - later runs inherit the binding.
3. `cycle-done`.
4. `unregister`, then `register`, of the orchestrator, which clears the binding.
5. The merge sign-off.
6. The spec's `**Status:**` flip, a docs-only commit and still the last commit on the branch.
7. The merge.
8. `cr-close`.

Two loops back into a fix cycle:

- **A red gate** is ingested, then `cycle-done` closes the cycle with it. A `fix` cycle is
  appended (`cycle-add --kind fix`), and the gate runs again inside that new last cycle.
- **A sign-off that sends changes back** after `cycle-done` follows the same path.

Every other orchestrator run stays unbound:

- baselines;
- the post-merge develop gate;
- the release's own verification gate, which runs under `--release` (`git-workflow` § Releases).

**The `crucible` skill.**

- Its "Who runs what" ORCHESTRATOR bullet: the gate runs in the plan's last cycle, bound with
  `--cycle`, replacing "with the verify cycle activated … LAST linked run".
- Its stale-binding bullet: the pre-merge gate is the orchestrator's one bound run, cleared after
  `cycle-done` by `unregister` then `register`.

**The `shutdown` skill.** A graceful shutdown finishes the plan's active cycle, except when that
cycle is the last one and its pre-merge gate has not run. That cycle stays active and is reported
as "awaiting the pre-merge gate".

**Model B's `AGENTS.md`** states the order.

### §S6 — Test leaks

`sub-agent-procedure.md` § Code quality and `orchestration-common.md`: a test leak (state one test
leaves for another: an environment variable, a stub, a global) is fixed at its source, never in
the tests it breaks. The text always says "test leak", because "leak" already means a write outside
the worktree.

### §S7 — Releases and the gate

**The `git-workflow` skill § Releases.**

- **A release fix is a CR.** A failure the release's own verification finds (the rehearsal, the
  regression, the gate) is fixed by a CR filed into that release, with a plan and cycle-bound
  agents. It commits directly on the release branch, never on a separate bugfix branch, and
  reaches develop at `finish`.
  - Its runs are cycle runs.
  - Its `cr-close` takes the fix's last commit on the release branch.
  - The release's own `regression` and `pre-merge-gate` stay `--release` runs from an unbound id.
- **"Running a CR during a release is HIGHLY DISCOURAGED"** is amended. It applies to new, unplanned
  work. A release fix is the rule, and needs no extra approval.
- **Unchanged:** "fix a real failure on a hotfix branch", which applies after `finish`.
- **The test-hygiene CR.** Every release carries a test-hygiene CR, sequenced last in the release's
  final wave. It sweeps:
  - the suite's analyzer findings;
  - its flaky, slow or network-bound tests;
  - its skip reasons and duplicated helpers;
  - the hygiene notes the release's CRs deferred.

  Because it is last, the wave has not drained while it is open, so the release does not start.
  No dependency edge is added; CRs stay non-gates.

**`model-b` SKILL §4.5** states the hygiene-CR rule. **`cr-authoring`'s "A release is NOT a CR"
bullet** names it as work the release needs.

**The wave-boundary gate.** The `crucible` skill's `gate-run` text, and Model B's `AGENTS.md`
wave-gate line, say the intent tells the gate not to stop any server it did not start. The
`gate-run --intent <goal> --agent <id>` examples are unchanged.

## Acceptance criteria

Every phrase gate below is proved both ways (it passes the shipped text and bites on a sample
without the phrase) once per detector kind. The gates may share one table-driven module.

- [ ] **§S1.** Gates pin:
      - the `crucible` skill's widened opening sentence and its propose-a-verb step;
      - the absence of an unqualified invitation to read the board over HTTP;
      - `orchestration-common.md`'s rule.
- [ ] **§S2.** One gate per surface, each pinning what §S2 assigns it:
      - `cr-authoring`: scored at filing; the 1–13 scale; the 13 cap and the split; the
        legacy-filing path scoring;
      - `gap-analysis`: the re-score re-sending title, release and wave; the split before the
        pre-review; the Track raising it to Mainline;
      - `orchestration-mainline.md`: the score in its filing order;
      - the `crucible` skill: `--points` on its `cr-plan` example.
- [ ] **§S3.** A gate pins `orchestration-common.md`'s no-extra-proof-steps rule.
- [ ] **§S4.**
      - **The negative gate's scope** is:
        - `skills-src/**/*.md`, minus the imported `crucible-report-*/` and `crucible-register/`;
        - `generator/templates/*.tmpl` and `generator/stacks/*.toml`;
        - `AGENTS.md`;
        - `contracts/crucible-envelope.md`.
      - **It fails on** `\bC<n>`, `--cycle\s+"C\d+`, `\bC\d+ <label>`,
        ``CR-[^\s`]*-[CF]\d+-(?:RED|GREEN|VERIFY|FIX)\b``, and, in `AGENTS.md` only,
        `\bC\d+ (?:RED|GREEN|VERIFY|FIX)\b`.
      - **It is proved both ways.**
      - **Positive gates** pin the `<cycle id>` form on each surface §S4 lists, including §4.1's
        role sentence on one line.
      - **`worktree-flow.py status`** emits no `cycle` field. A test drives `status` on a branch
        whose commit subject holds `C1`.
      - **`test_pi_worktree_isolation`** routes `CR-BAR-002-237-GREEN` to its CR's worktree.
- [ ] **§S5.**
      - **`orchestration-common.md` § Close-out** gates pin:
        - the eight-step order;
        - the binding mechanics;
        - the two loops back into a fix cycle;
        - the unbound list, including the release gate.
      - **The `crucible` skill** gates pin the rewritten ORCHESTRATOR bullet, and the absence of
        "verify cycle activated" and "LAST linked run".
      - **The stale-binding bullet** is rewritten in place.
        `test_ambient_manifest_discovery.CrucibleLifecycleRulesS5Test` and its bite test migrate
        with it.
      - **The `shutdown` skill's** exception is pinned.
      - **`AGENTS.md`'s** order is pinned.
- [ ] **§S6.** Gates pin the test-leak rule in `sub-agent-procedure.md` § Code quality and in
      `orchestration-common.md`.
- [ ] **§S7.** Gates pin:
      - in `git-workflow`: the release-fix CR, its cycle runs, its `cr-close`, the amended "highly
        discouraged" bullet, and the unchanged hotfix sentence;
      - the hygiene-CR rule, worded as the drain, in `git-workflow`, `model-b` SKILL §4.5 and
        `cr-authoring`'s release bullet;
      - the intent line in the `crucible` skill and `AGENTS.md`.
- [ ] **Runs.**
      - Every commit leaves the suite green through the client, with a real `HOME` and an empty
        one, beyond RED's own failures.
      - The skills load in Pi with no diagnostics.
      - The imported `crucible-report-*` and `crucible-register` bundles stay byte-identical.
      - `generator/build.py --check` is clean.
      - The `AGENTS.md` counts and baselines match.

## Non-goals

- **Inserting a fix cycle before VERIFY, or re-running VERIFY.**
- **Restarting a dev server after every source commit.**
- **Reading every AXI envelope whole.** CR-MDB-072 carries it.
- **Editing the imported `crucible-report-*` and `crucible-register` bundles.** Their generic
  `<cycle>` slot admits a cycle id.
- **Changing the agent templates.** They bind every agent to `sub-agent-procedure.md`.
- **The scaffolded `AGENTS.md`'s run-context note.** It is retired auto-attach wording, filed as a
  follow-up.

## Cycle plan

1. **The rules (§S1–§S3, §S5–§S7).** Red-green.
2. **Cycle labels, agent ids and the `worktree-flow` cycle field (§S4).** Red-green; it
   re-measures the baselines.
3. **Verify.**
