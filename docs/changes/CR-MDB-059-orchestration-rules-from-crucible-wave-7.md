# CR-MDB-059 — Orchestration rules from Crucible's wave 7

**Status:** PENDING — spec (gap analysis 2026-10-15).
**Type:** refactor (skills, references, `AGENTS.md`)
**Priority:** P1 — release 1.0.0, wave 2.
**Depends on:** none (board-authoritative: read `queue`)
**Labels:** skills, orchestration, crucible, conventions
**Design reference:** PRD D5 (AMENDED 2026-10-15: orchestration rules adopted from Crucible #1433 §B)
and D3.4 (AMENDED 2026-10-15: cycle labels and agent ids); DN-model-b-language (LOCKED — cite,
never fork).

## Context

- **Rules already in the text:**
  - a patch CR for scope found mid-CR: `orchestration-mainline.md`, `orchestration-track.md`,
    `cr-authoring`;
  - a VERIFY finding fixed in its own `fix` cycle appended after VERIFY: `orchestration-common.md`;
  - the `cycle-skip` verb: the `crucible` skill;
  - "the spec wins" over a brief: the four agent templates.
- **What the shipped text says today:**
  - **Board through verbs:** no rule forbids reading the board through its HTTP API.
  - **Story points:** no rule says when a CR is scored or re-scored, or what to do above 13. The
    `crucible` skill documents `cr-plan --points` only as a flag.
  - **Cycle labels:** `C<n> <label> (§S…)`, in `model-b` SKILL §4.3, the `crucible` skill's
    `plan-file` example and Model B's `AGENTS.md`. These numbers drift whenever a cycle is added.
  - **Agent ids:** `CR-<ACRONYM>-NNN-<cycle>-<ROLE>` with a positional tag such as `C1`, in the
    `crucible` skill's Identity section, `crucible/references/<stack>.md`,
    `orchestration-common.md`'s parallel-agents example and `AGENTS.md`. `model-b` SKILL §4.1 gives
    only `<agent-type>-<project>`, the orchestrator form.
  - **The pre-merge gate's place:** not stated. The `crucible` skill tells a long-running
    orchestrator to stay unbound.
  - **Test leaks, release fixes, servers the gate did not start, the release's test-hygiene CR:**
    no rule.

## Scope

### §S1 — The board through client verbs only

- **`orchestration-common.md`:** the orchestrator reads and writes the Crucible board only
  through client verbs, never the HTTP API; where no verb fits, it says so and proposes one to
  Crucible.
- **The `crucible` skill** states the same rule beside its plan verbs.

### §S2 — Story points

- **`cr-authoring`:** every CR is scored when filed (`cr-plan --points`, scale 1, 2, 3, 5, 8, 13);
  13 is the cap, and a CR scoring more is split before it is filed.
- **The `gap-analysis` skill:** the analysis re-scores the CR with `cr-plan --points`, re-sending
  its current title, release and wave; a CR the analysis finds above 13 is split before the
  pre-review.
- **`orchestration-mainline.md`'s filing order** names the score in `cr-plan`.

### §S3 — A brief adds no proof steps

`orchestration-common.md`'s brief rules: a brief states the scope, the approved spec (the spec
wins) and the definition's standard procedure; the orchestrator adds no extra proof steps, because
VERIFY and the gate catch drift.

### §S4 — Cycle labels and agent ids

- **Cycle labels carry no numbering:** `<label> (§S…)`. Every `plan-file` example shows
  `--cycle "<label>"` with no `C<n>`:
  - `model-b` SKILL §4.3;
  - the `crucible` skill's plan verbs;
  - Model B's `AGENTS.md`.
- **A TDD-role agent id carries the cycle's server id:** `CR-<ACRONYM>-NNN-<cycle id>-<ROLE>`, for
  example `CR-MDB-071-237-RED`. Stated in:
  - the `crucible` skill's Identity section;
  - `crucible/references/<stack>.md` (all five);
  - `orchestration-common.md`'s parallel-agents suffix example;
  - `model-b` SKILL §4.1, beside the orchestrator form;
  - Model B's `AGENTS.md`: the agent-ids line, the test-command examples, and the `stage-flip`
    milestone label.
- The spec pre-review id `CR-<ACRONYM>-NNN-SPEC-REVIEW` and the orchestrator ids are unchanged.

### §S5 — The pre-merge gate runs inside the last cycle

**`orchestration-common.md`:** the pre-merge gate runs while the plan's last cycle is still active,
under the orchestrator's own id with `--cycle <that cycle>`. The order is:

1. the gate;
2. `cycle-done`;
3. `unregister` then `register` of the orchestrator, which clears the binding;
4. the merge sign-off, the merge and `cr-close`.

Every other orchestrator run, such as a baseline, stays unbound.

**The `crucible` skill:** "a long-running orchestrator should register unbound" is amended to the
same rule, with the pre-merge gate as the one bound run.

**Model B's `AGENTS.md`** states the order.

### §S6 — Test leaks

`sub-agent-procedure.md` and `orchestration-common.md`: a test leak (state one test leaves for
another: an environment variable, a stub, a global) is fixed at its source, never in the tests it
breaks.

### §S7 — Releases and the gate

- **The `git-workflow` skill § Releases:**
  - **Release fixes:** a fix found during a release goes directly on the release branch, never
    on a separate bugfix branch, and reaches develop at `finish`.
  - **The test-hygiene CR:** every release carries a test-hygiene CR, sequenced last in the
    release's final wave. It sweeps the suite's analyzer findings, its flaky, slow or
    network-bound tests, its skip reasons and duplicated helpers, and the hygiene notes the
    release's CRs deferred. A release does not start while its hygiene CR is open.
- **The test-hygiene CR, elsewhere:**
  - `model-b` SKILL §4.5 states the same rule;
  - `cr-authoring` adds it to filing a release's scope.
- **The wave-boundary gate:**
  - the `crucible` skill's `gate-run` text says the intent tells the gate not to stop any server
    it did not start;
  - Model B's `AGENTS.md` wave-gate line says the same.

## Acceptance criteria

- [ ] **§S1.** `orchestration-common.md` and the `crucible` skill each state the verbs-only rule
      and the propose-a-verb step. A gate pins each, and is proved both ways.
- [ ] **§S2.** The rule is stated in each of `cr-authoring`, the `gap-analysis` skill and
      `orchestration-mainline.md`:
      - scored at filing;
      - re-scored at gap analysis by re-sending title, release and wave;
      - the 1–13 scale;
      - the 13 cap and the split.

      A gate pins each, and is proved both ways.
- [ ] **§S3.** `orchestration-common.md` states the no-extra-proof-steps rule; a gate pins it.
- [ ] **§S4.**
      - No `C<n>` label form remains in a shipped surface (the skills, references, templates and
        `AGENTS.md`). A gate fails on `C<n> <label>` and on `--cycle "C1`, and is proved both ways.
      - Each surface §S4 lists carries the `<cycle id>` agent-id form.
      - The migrated gates that pin the old forms are listed in RED's report.
- [ ] **§S5.**
      - `orchestration-common.md` states the gate, `cycle-done`, re-register and merge order.
      - The `crucible` skill states the one bound run.
      - `AGENTS.md` states the order.

      Gates pin each.
- [ ] **§S6.** Both files state the leak rule; gates pin each.
- [ ] **§S7.**
      - The release-fix rule is in `git-workflow`.
      - The hygiene-CR rule is in `git-workflow`, `model-b` SKILL §4.5 and `cr-authoring`.
      - The intent line is in the `crucible` skill and `AGENTS.md`.

      Gates pin each.
- [ ] **Runs.** Every commit leaves the suite green through the client, with a real `HOME` and an
      empty one, beyond RED's own failures. The skills load in Pi with no diagnostics. The
      imported `crucible-report-*` bundles stay byte-identical. `generator/build.py --check` is
      clean. The `AGENTS.md` counts and baselines match.

## Non-goals

- **Inserting a fix cycle before VERIFY, or re-running VERIFY.** A fix cycle is appended after
  VERIFY.
- **Restarting a dev server after every source commit.** It is Crucible-specific.
- **Reading every AXI envelope whole.** It is carried by its own CR.
- **Editing the imported `crucible-report-*` bundles.** Their generic `<cycle>` slot already admits
  a cycle id, and they are Crucible's.
- **Changing the agent templates.** They bind every agent to `sub-agent-procedure.md`, which
  carries §S6.

## Cycle plan

1. **The rules (§S1–§S3, §S5–§S7).** Red-green.
2. **Cycle labels and agent ids (§S4).** Red-green; it re-measures the baselines.
3. **Verify.**
