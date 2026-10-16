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
  - the four agent templates' output-discipline lines: "never `| tail`" (red: "Never hide failures
    behind `| tail -N`"), about test runs only;
  - `generator/stacks/rust.toml`'s debugging line: "never `| tail`";
  - the `model-b` skill: "Never pipe user feedback or poll output through head, tail or grep";
  - the `chrome-ui-relay` skill: every `chrome-devtools-axi` envelope is read whole, with its own
    gate (`tests/test_chrome_ui_relay_skill.py`).

  Nothing states the rule for every AXI command, and nothing tells a dispatch brief to carry it.
- **No regressions to clear.** No guarded file shows an AXI call piped or redirected away. The
  `>` in placeholders such as `<cycleId>` is not a redirect.
- **What exists to reuse.** `tests/test_chrome_ui_relay_skill.py`'s `shown` yields each code span
  and each fenced line of a text, built on the raw-runner guard's `_blocks` and `_code_spans`, which
  it imports. It already joins a fenced line ending in `\` with the lines it continues. Importing
  from another test module is the established pattern.
- **Gates the new text must pass.** `test_client_path_anchoring`'s §S4 ratchet counts a code span of
  a plain-word Pi tool name (`grep`, `read`, …) as a harness-tool name, and
  `test_orchestrator_rule_triage.ModelBCommonTextNeutralTest` bans that vocabulary and every
  `sandesh_*` name in the `model-b` skill and its references.

## Scope

### §S1 — The rule

- **What it covers:** the output of an AXI command. The AXI commands are:
  - the Crucible clients (`<stack>-crucible.py`, and `<client>` where the text names it so);
  - `sandesh`;
  - `modelb-axi`;
  - `worktree-flow.py`;
  - `gh-axi`, `chrome-devtools-axi` and `lavish-axi`.

  The list is closed.
- **What it forbids:** grepping, heading, tailing or otherwise filtering the output, narrowing it
  with `jq`, redirecting it away (its output, stdout or stderr, never goes to `/dev/null`), or
  summarising it by pattern. It binds every agent, orchestrators included.
- **What it requires:** the whole envelope is read every time. A long run writes its output to a
  file, and that file's envelope is read whole.
- **What it does not cover:** a runner log a client writes with `--log`. That is not an envelope,
  and searching it for a failure stays allowed.

The rule's text states it in prose. It never shows a piped or redirected AXI call as code, even as a
counterexample. It names grep, head and tail as plain words, never as code spans, and names no
harness tool and no `sandesh_*` tool; `jq` may be a code span.

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
   filtered or redirected away. Each line keeps its summary clause (counts, failing names, assertion
   lines). The adjacent `generator/templates/builtin-tools.toml` `lean` passages stay byte-identical,
   and the new text names no `ctx_*` tool and no lean-ctx, so the built-in render still renders.
7. **`generator/stacks/rust.toml`'s debugging line:** "never `| tail`" widens the same way. The
   `--log` file stays searchable (`rg` in it).
8. **The generated agents:** `generator/agents/*.md` is re-rendered with `generator/build.py build`,
   and this repository's `.pi/agents` matches it.

### §S3 — The guard

A test module, `tests/test_axi_envelope_read_whole.py`, fails on any guarded file that shows an AXI
command piped or redirected away:

- **Guarded files:** the raw-runner guard's guarded set (`GUARDED_ROOTS` minus `GUARD_EXCLUDED` in
  `tests/test_raw_runner_guard.py`).
- **What it reads:** each code span, and each fenced line judged alone (continued lines joined, as
  `shown` already does), through `shown` imported from `tests/test_chrome_ui_relay_skill.py`. No
  reading helper is copied. It never applies `_governed`.
- **An AXI command:** a name from §S1's list as a whole word, not adjacent to a letter, digit, `_` or
  `-` (a leading path such as `~/.agents/scripts/` is allowed; `sandesh-pi` and `/sandesh-watcher`
  are not `sandesh`). `<stack>-crucible.py` and `<client>` count.
- **A finding:** an AXI command followed later in the same span or line, before any `&&`, `||` or
  `;`, by either:
  - a pipe: a single `|` (never `||`), which covers `|&` and `2>&1 |`;
  - a redirect whose target is `/dev/null` (`>`, `>>`, `N>`, `&>`, with or without a space).
- **Not a finding:**
  - a redirect to a file, and `--log <path>`;
  - a `|` inside a `<…>`, `{…}` or `[…]` placeholder, or one joining option values with no space on
    either side (`approve|fix|skip`);
  - a pipe before the AXI command, or after a `&&`, `||` or `;` that follows it.

  A `|` inside a quoted argument (`--body "a | b"`) is a finding.
- **No prohibition exemption:** a governing "never" does not spare a shown form.

## Acceptance criteria

- [ ] **§S1–§S2, the rule in each place.** A gate per place in §S2 items 1–7 pins:
      - **items 1, 2 and 5:** that the envelope or output is read whole; at least two of the words
        grep, head, tail, `jq` and `filter`; redirecting away, with `/dev/null`; that a long run's
        output goes to a file whose envelope is read whole; and the `--log` runner-log exception;
      - **item 1, also:** the §S1 command list; "orchestrators included" (or "every agent"); summarising
        by pattern; and the brief bullet naming the rule;
      - **items 3 and 4:** that the envelope or output is read whole, and each of "piped" (or "pipe"),
        "filtered" (or "filter") and "redirected away";
      - **item 6:** in each template's output-discipline line, the same three words and the summary
        clause;
      - **item 7:** the same three words, `--log`, and searching the log.

      Each gate also fails when its place's text has a §S3 finding. Each gate is proved both ways on
      synthetic text, including one bad sample that meets every pin only through a shown piped AXI
      call, which the gate fails.
- [ ] **§S2, the new text passes the existing gates.** `test_client_path_anchoring` and
      `ModelBCommonTextNeutralTest` stay green with no baseline change.
- [ ] **§S2, item 8.** `generator/build.py --check` is clean. This repository's `.pi/agents/python-*`
      are byte-identical to `generator/agents/python-*`. The rendered output-discipline lines carry
      the rule, in both the lean-ctx and the built-in renders.
- [ ] **§S3, the guard on the real tree.** No guarded file has a finding.
- [ ] **§S3, the detector both ways.** On synthetic text, it finds:
      - `<client> test --agent x | tail -5`;
      - `` `sandesh status | grep listening` ``;
      - `` `~/.crucible/clients/<stack>-crucible.py plans | head` ``;
      - `python3 ~/.crucible/clients/python-crucible.py plans 2>&1 | head`;
      - `` `modelb-axi agents |& head` ``;
      - `lavish-axi poll | jq .`;
      - `` `sandesh fetch --body "a | b"` ``;
      - `modelb-axi agents > /dev/null`;
      - `` `sandesh status >> /dev/null` ``;
      - `worktree-flow.py status 2>/dev/null`;
      - `gh-axi run list &>/dev/null` and `gh-axi run list &> /dev/null`;
      - a fenced line `sandesh inbox \` continued by an indented line `--project P | tail`;
      - a governed form: ``Never run `sandesh status | head`.``

      It does not find:
      - `<client> test --agent x --log /tmp/run.log`;
      - `<client> regression --agent x > /tmp/run.out 2>&1`;
      - `` `sandesh fetch --to '<your address>'` ``;
      - `` `python3 <client> plan-file --cycle-kind <red-green|verify>` ``;
      - `` `<client> gate-respond --action approve|fix|skip` ``;
      - `sandesh status || true`, `sandesh status && git log | head` and
        `sandesh status; git log | head`;
      - `echo x | sandesh send --project P`;
      - `` `sandesh-pi x | y` `` and `` `/sandesh-watcher stop | y` ``;
      - `git log | head`, with no AXI command;
      - a prose sentence naming sandesh and head.
- [ ] **Registry keys.** The new rule text adds no `KEY=` or `$NAME` in code in the guarded set, so
      `NOT_REGISTRY_KEYS` is unchanged.
- [ ] **Migrations (RED).** These pins move with the replaced wording, each marked
      `# MIGRATED at CR-MDB-072 (§S2)`: in `tests/test_crucible_verb_surface.py`, the "never through
      | head" statement and its pattern in `VERB_SURFACE_STATEMENTS`, the `GOOD_SKILL` sample and its
      `GOOD_SKILL_CUTS` entry (where "a redirect otherwise" survives). No other test pins the
      replaced wording.
- [ ] **Runs.**
      - The suite is green through the client, with a real `HOME` and an empty one; the empty `HOME`
        stays empty.
      - The skills load in Pi with no diagnostics, and every touched skill's frontmatter is
        unchanged.
      - New tests use a literal `§`, never `\u00a7`.
      - `AGENTS.md`'s test-module count (two places) and its two Testing & QA baselines match the
        measured suite.

## Non-goals

- **The `chrome-ui-relay` skill.** It already states the rule for its envelopes, and its stricter
  gate (no redirect at all, no `$(…)` capture) stays as it is.
- **Skills that show AXI calls without pipes** (`bootstrap`, `shutdown`, `orchestration-track.md`,
  the `crucible-report-*` imports). The guard covers them, and they need no new text.
- **The memory templates.** They are outside the guarded set, and CR-MDB-060 retires them.
- **`workflows-src`, the install guide and the package README.** CI scripts call `gh`, not
  `gh-axi`, and the guide is written for people. Neither is in the guarded set.
- **A runtime hook that blocks a piped AXI call.** The rule is carried by the text and its guard.
- **Other AXI-shaped tools** (`crucible-axi`, `no-mistakes`). §S1's list is closed.
- **`AGENTS.md`'s stale agent and stack counts** ("16 stack×role agents", four stack files). The
  release's hygiene CR, CR-MDB-052, carries them.

## Cycle plan

1. **The rule in every place, and the guard (§S1–§S3).** Red-green.
2. **Verify.**
