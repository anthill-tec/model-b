# CR-MDB-072 — Every AXI envelope is read whole

**Status:** PENDING — spec (gap analysis 2026-10-16).
**Type:** refactor (skills, references, agent templates, a stack file) + a guard test
**Priority:** P1 — release 1.0.0, wave 2.
**Depends on:** CR-MDB-059 (board-authoritative: read `queue`)
**Labels:** skills, orchestration, agents, axi, guard
**Design reference:** PRD D5 (every AXI envelope is read whole, and its 2026-10-16 ruling on the
guard); Crucible #1451.

## Context

- **What an envelope carries.** An AXI command prints one envelope on stdout. Its `warnings[]`,
  `help[]` and `error` carry the guidance a caller needs next. An agent that greps, heads, tails,
  filters, narrows with `jq`, redirects away or summarises the output by pattern loses that guidance
  silently.
- **What the shipped text says today:**
  - the `crucible` skill: client output goes to a file, "and never through `| head`";
  - the four agent templates' output-discipline lines: "never `| tail`", about test runs only;
  - `generator/stacks/rust.toml`'s debugging line: "never `| tail`";
  - the `model-b` skill: "Never pipe user feedback or poll output through head, tail or grep";
  - the `chrome-ui-relay` skill: every `chrome-devtools-axi` envelope is read whole, with its own
    gate (`tests/test_chrome_ui_relay_skill.py`).

  Nothing states the rule for every AXI command, and nothing tells a dispatch brief to carry it.
- **No regressions to clear.** No guarded file shows an AXI call piped or redirected away. The
  `>` in placeholders such as `<cycleId>` is not a redirect.
- **What exists to reuse.** `tests/test_chrome_ui_relay_skill.py`'s `shown` yields each code span
  and each fenced line of a text, built on the raw-runner guard's `_blocks` and `_code_spans`, which
  it imports.

## Scope

### §S1 — The rule

- **What it covers:** the output of an AXI command. The AXI commands are:
  - the Crucible clients (`<stack>-crucible.py`, and `<client>` where the text names it so);
  - `sandesh`;
  - `modelb-axi`;
  - `worktree-flow.py`;
  - `gh-axi`, `chrome-devtools-axi` and `lavish-axi`.
- **What it forbids:** grepping, heading, tailing or otherwise filtering the output, narrowing it
  with `jq`, redirecting it away (to `/dev/null`), or summarising it by pattern. It binds every
  agent, orchestrators included.
- **What it requires:** the whole envelope is read every time. A long run writes its output to a
  file, and that file's envelope is read whole.
- **What it does not cover:** a runner log a client writes with `--log`. That is not an envelope,
  and searching it for a failure stays allowed.

The rule's text states it in prose. It never shows a piped or redirected AXI call as code, even as a
counterexample.

### §S2 — Where it is stated

1. **`skills-src/model-b/references/orchestration-common.md`:**
   - a section stating §S1 whole;
   - in § "Never author code — dispatch with an accurate brief", a bullet: every dispatch brief
     carries the rule.
2. **`skills-src/model-b/references/sub-agent-procedure.md`:** §S1, for the dispatched agent.
3. **`skills-src/model-b/references/sandesh.md`:** every `sandesh` envelope is read whole.
4. **`skills-src/model-b/SKILL.md`:** the existing "Never pipe user feedback or poll output…" bullet
   gains AXI output.
5. **`skills-src/crucible/SKILL.md`:** "never through `| head`" widens to the rule: the client's
   envelope, in the file or on stdout, is read whole, never filtered.
6. **The four agent templates** (`generator/templates/{red,green,verify,fix}.md.tmpl`): each
   output-discipline line states that the client's envelope is read whole and is never piped,
   filtered or redirected away. The line keeps what it says today about printing summaries, never
   raw logs.
7. **`generator/stacks/rust.toml`'s debugging line:** "never `| tail`" widens the same way. The
   `--log` file stays searchable.
8. **The generated agents:** `generator/agents/*.md` is re-rendered with `generator/build.py build`,
   and this repository's `.pi/agents` matches it.

### §S3 — The guard

A test fails on any guarded file that shows an AXI command piped or redirected away:

- **Guarded files:** the raw-runner guard's guarded set (`GUARDED_ROOTS` minus `GUARD_EXCLUDED` in
  `tests/test_raw_runner_guard.py`).
- **What it reads:** each code span, and each fenced line judged alone, through the existing `shown`
  reading, imported and never copied. A fenced line ending in `\` is joined with the line it
  continues.
- **A finding:** an AXI command (§S1's list, as a whole word) followed later in the same span or
  line by either:
  - a single `|` (never `||`), which covers `|&` and a `2>&1 |`;
  - a redirect whose target is `/dev/null` (`>`, `>>`, `N>`, `&>`, with or without a space).
- **Not a finding:**
  - a redirect to a file;
  - `--log <path>`;
  - a `<…>` placeholder;
  - a pipe that belongs to a different command after `&&`, `||` or `;`.
- **No prohibition exemption:** a governing "never" does not spare a shown form.

## Acceptance criteria

- [ ] **§S1–§S2, the rule in each place.** A gate per place in §S2 items 1–7 pins:
      - **items 1, 2 and 5:** that the envelope or output is read whole; at least two of grep, head,
        tail, `jq` or a filter; redirecting away; that a long run's output goes to a file whose
        envelope is read whole; and the `--log` runner-log exception;
      - **item 1:** the brief bullet, naming the rule;
      - **item 1:** the list of AXI commands in §S1;
      - **items 3, 4, 6 and 7:** that the envelope or output is read whole and is never piped,
        filtered or redirected away.

      Each gate is proved both ways on synthetic text. No gate passes on a statement that shows a
      piped or redirected AXI call as code.
- [ ] **§S2, item 8.** `generator/build.py --check` is clean. This repository's `.pi/agents/python-*`
      are byte-identical to `generator/agents/python-*`. The rendered output-discipline lines carry
      the rule.
- [ ] **§S3, the guard on the real tree.** No guarded file has a finding.
- [ ] **§S3, the detector both ways.** On synthetic text, it finds:
      - `<client> test --agent x | tail -5`;
      - `` `sandesh status | grep listening` ``;
      - `modelb-axi agents > /dev/null`;
      - `worktree-flow.py status 2>/dev/null`;
      - `gh-axi run list &> /dev/null`;
      - `python3 ~/.crucible/clients/python-crucible.py plans 2>&1 | head`;
      - `lavish-axi poll | jq .`;
      - a fenced line `sandesh inbox \` continued by an indented line `--project P | tail`.

      It does not find:
      - `<client> test --agent x --log /tmp/run.log`;
      - `<client> regression --agent x > /tmp/run.out 2>&1`;
      - `register --cycle <cycleId>`;
      - `sandesh status || true`;
      - `sandesh status && git log | head`;
      - `git log | head` with no AXI command;
      - a prose sentence naming `sandesh` and `head`.

      The detector imports `shown` and copies no reading helper (the one-copy rule).
- [ ] **Registry keys.** The new rule text adds no `KEY=` or `$NAME` in code in the guarded set, so
      `NOT_REGISTRY_KEYS` is unchanged.
- [ ] **Migrations (RED).** Pins on the replaced wording move with it, each marked
      `# MIGRATED at CR-MDB-072 (§S2)`:
      - `tests/test_crucible_verb_surface.py`'s "never through | head" statement, the real-skill
        pattern and its `GOOD_SKILL` sample;
      - any template or stack-file pin on "never `| tail`" that the suite shows failing after the
        change, named in the RED report.
- [ ] **Runs.**
      - The suite is green through the client, with a real `HOME` and an empty one; the empty `HOME`
        stays empty.
      - The skills load in Pi with no diagnostics, and every touched skill's frontmatter is
        unchanged.
      - New tests use a literal `§`, never `\u00a7`.
      - The `AGENTS.md` counts and baselines match.

## Non-goals

- **The `chrome-ui-relay` skill.** It already states the rule for its envelopes, and its stricter
  gate (no redirect at all, no `$(…)` capture) stays as it is.
- **Skills that show AXI calls without pipes** (`bootstrap`, `shutdown`, `orchestration-track.md`,
  the `crucible-report-*` imports). The guard covers them, and they need no new text.
- **The memory templates.** They are outside the guarded set, and CR-MDB-060 retires them.
- **`workflows-src`, the install guide and the package README.** CI scripts call `gh`, not
  `gh-axi`, and the guide is written for people. Neither is in the guarded set.
- **A runtime hook that blocks a piped AXI call.** The rule is carried by the text and its guard.

## Cycle plan

1. **The rule in every place, and the guard (§S1–§S3).** Red-green.
2. **Verify.**
