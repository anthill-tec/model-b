# CR-MDB-090 — A long client run is read whole, unfiltered; the shared context ledger is left alone

**Status:** PENDING — spec drafted 2026-10-29 from the gap analysis and the user's rulings (PRD D5, 2026-10-29); the spec pre-review folded in; awaiting approval.
**Type:** fix (the generated agent templates and their built-in passages, the `model-b` and
`crucible` skills, `AGENTS.md`, the scaffolded `AGENTS.md` lean-ctx section)
**Priority:** P1.
**Depends on:** none (board-authoritative: read `queue`, not this line). CR-MDB-092 depends on this
CR; CR-MDB-083 follows it.
**Labels:** agents, axi, lean-ctx, templates, skills
**Points:** 5 (re-scored at gap analysis; seeded 3).
**Design reference:**
- PRD D5: every AXI envelope is read whole, and its 2026-10-16 ruling. The rule is carried by text
  and a guard. A redirect to a file and `--log` stay allowed, because a long run's output goes to a
  file whose envelope is then read whole.
- PRD D5's 2026-10-29 ruling, at this CR's gap analysis: one sanctioned way to read a long run
  whole.
  - Every AXI command runs uncompressed.
  - A long run redirects its whole output to a file, which is read from the envelope's first line
    to its end. A search that only locates that line's number is allowed, and the envelope itself
    is never searched or filtered.
  - The harness's saved full-output file is the fallback for a run that was not redirected.
  - The context ledger is left alone, stated in the procedure and `orchestration-common` only.
  - The skills name the mode ("uncompressed", "raw mode"), never a tool. The tool form lives in the
    templates, Model B's own `AGENTS.md` and the lean-ctx section `init` scaffolds, which gains one
    bullet naming it. This covers §S1.4 and §S5.
- CR-MDB-072 (the rule, its places and its guard).
- DN-multi-harness-deploy-model §D18 (skills name capabilities; tools are named in the definitions
  and `AGENTS.md`).
- DN-multi-harness-deploy-model §D26 (each role runs the tests its phase needs). VERIFY's
  whole-suite runs are what make long runs routine, which is why this CR lands before CR-MDB-083.
- PRD D10 and CR-MDB-045 §S8 (the built-in form).
- Research note `lean-ctx-for-model-b` §S1, §S3, §S5.2 and §S9 items 1, 5 and 7.
- Gap analysis: `/tmp/mdb090/gap-analysis.md`.

## Context

- **Agents filter long runs.** At least eleven self-reports, about fifteen by 2026-10-29, describe
  the same breach of CR-MDB-072's rule, and the orchestrator breached it several times too.
  - **What they did:** piped a Crucible client run, or `check`, through grep, head or tail, or sent
    it to a file they never read.
  - **Why:** to fit under Pi's shell cap. Pi keeps the last 2000 lines or 50 KB of a run, and
    a gate's stream is about 1 MB.
  - **What worked:** a redirect to a file plus `--log`, read from the `[crucible] run log` line.
- **What the client prints.** The envelope goes to stdout near the end, first line `axi:` (the
  shared `_crucible_axi.emit_axi`). The human line and the runner stream go to stderr.
  - The human line `emit_axi` writes comes after the envelope, so the envelope sits near the end,
    not at it.
  - The runner stream can hold a line of its own that begins `axi:` at column 0, for example a
    failing assertion that prints an envelope. The envelope's first line is therefore the **last**
    line that begins `axi:`; the client's own `_suite_envelope` searches backwards for this reason.
  - Under `--format json` the envelope is one JSON line, with no `axi:`.
  - The runner stream goes to stderr, so a redirect of stdout alone still floods the console. A long
    run redirects both streams (`> /tmp/<run>.out 2>&1`).
- **`--log` does not take the stream off the console.** `run_streamed` echoes every runner line to
  stderr *and* writes it to the `--log` file. So `--log` alone does not shorten what Pi shows.
  - The `[crucible] run log → <path>` line appears only with `--log`.
  - `--log` is absent on rust `regression` and on `pre-merge-gate` for the arduino, mvn and rust
    clients.
- **`ctx_shell` without `raw` alters a long run's envelope** (lean-ctx 3.11.4 source,
  `shell/compress/engine.rs`):
  - The client is not a recognised test runner, so its output is compressible.
  - TOON detection judges the whole output. A long, mostly unindented runner stream usually fails
    it, and the pattern engine reshapes the output instead.
  - Where the output is detected as TOON, `truncate_verbatim` keeps 30 head lines, 20 tail lines and
    up to 200 safety lines. An envelope longer than about 20 lines then loses its head.
  - Without `raw`, Pi's saved full-output file holds the *compressed* output.
- **`raw=true` makes the run uncompressed.** On Pi, `ctx_shell` with `raw=true` is Pi's plain bash
  tool:
  - no `lean-ctx -c`, so no compression, no ledger entry, and none of lean-ctx's shell allowlist or
    redirect block;
  - Model B's hooks still fire, because they match `ctx_shell`.
- **Pi names its saved file on every exit path.** When Pi truncates a run, it writes the raw bytes
  to a temp file (`pi-bash-<id>.log` under the system temp directory). Its notice in the result
  text names the file and the line range shown. This holds on success, on a non-zero exit, and on a
  timeout or abort.
  - Checked at the spec pre-review in the live Pi build, `@earendil-works/pi-coding-agent` (the
    global bun install): its `dist/core/tools/bash.js` carries the
    `[Showing lines … Full output: <path>]` notices and puts them on the abort, timeout and
    non-zero-exit paths.
- **`read` reaches that file.** The project permission policy allows `external_directory_read` for
  `/tmp/*`, and the templates already send every path outside the project to the built-in `read`.
  - A redirect file belongs under `/tmp` for the same reason. A redirect into the repo dirties the
    tree, which VERIFY's clean-tree check fails, and the file would be read through `ctx_read`'s
    4096-token bridge cap.
- **The context ledger is machine-wide.** One file is shared by every lean-ctx session, sub-agent and
  project on the machine. It reports "context pressure" against a fixed window and suggests
  evicting entries.
  - Evicting writes a session-scoped exclusion for the file.
  - Resetting clears the re-read cache the daemon serves every session.
  - Nothing in Model B states this today.
- **Searches skip `.worktrees/` from the main checkout.** `.worktrees/` is gitignored, and
  lean-ctx's walkers also prune it by name and as a linked worktree (`core/walk_filter.rs`). A
  gitignore-honouring search from the main checkout therefore never sees a CR's in-flight worktree.
  An explicit path to the worktree itself is searched.
  - `rg` searches an explicitly given `.worktrees/<cr>`, and also `.worktrees` itself (checked at
    the spec pre-review). The "never `.worktrees` itself" rule in §S4 is about lean-ctx's walkers;
    for `rg` it is harmlessly conservative.

## Scope

### §S1 — The reading rule, in the skills (capability words)

1. **`skills-src/model-b/references/sub-agent-procedure.md` § "Every AXI envelope is read whole"**
   keeps its bullets and gains these:
   - **Every AXI command runs uncompressed:** through the project's compressed shell in its raw
     mode, as the agent definition or the project's `AGENTS.md` names it, so no compression step
     cuts or reshapes its envelope.
   - **A run the harness truncates names the file that holds its full output.** This is the
     fallback for a run that was not redirected. The envelope is near the end of the output, and
     its first line is the **last** line that begins `axi:` (under a JSON output format the
     envelope is one JSON line). When the output shown does not reach back to the envelope's first
     line, that file is read in windows, by line offset and limit, until the envelope has been read
     whole. It is never filtered to fit.
   - The existing "A long run writes its output to a file" bullet becomes: **a long run redirects
     both its streams to a file under `/tmp`, outside the tree, and that file is read with the
     harness's plain file read from the envelope's first line to its end; a search that only
     locates that line's number is allowed, and the envelope itself is never searched or filtered**
     (PRD D5, ruled 2026-10-29).
   - The existing `--log` bullet gains: `--log` keeps that runner log beside the run, and **does not
     take the run's output off the console**.

   § "Report EVERY run"'s bullet "If stdout is truncated, read the report file … do NOT re-run"
   becomes: if a run's output is truncated, the envelope is read whole from the file the harness
   names, and failure detail from the report file (junit / lcov / surefire) or the `--log` file. The
   run is never re-run.
2. **`skills-src/model-b/references/orchestration-common.md` § "Every AXI envelope is read whole"**
   gains the same four bullet changes.
3. **`skills-src/crucible/SKILL.md`:**
   - § "Envelope — TOON-AXI on stdout" gains the same four bullet changes.
   - In § "The 0.3.0 verb surface", the client-output bullet is corrected: a client run's output,
     both streams, goes to a file under `/tmp` through a redirect; `--log <path>`, where the verb
     takes it, keeps a runner log beside it and does not take the output off the console; the client's envelope, in the file or on stdout,
     is read whole, never filtered.
4. **`skills-src/model-b/SKILL.md`** (PRD D5, ruled 2026-10-29: the skills name the mode, never
   a tool): the "Prefer the project's cached reads and compressed shell" bullet gains: except that
   an AXI command runs uncompressed, in the shell's raw mode.

**Wording constraints.**
- The text names no lean-ctx or harness tool: no `ctx_*`, and no code span of `read`, `grep` or
  `bash`.
- It shows no AXI call piped or sent to `/dev/null`, even as a counterexample.
- It names grep, head and tail as plain words only.
- Its apostrophes are straight (`'`), so the located-line pin's `line(?:'s)?` matches.

**The guard is unchanged.** CR-MDB-072's guard still finds an AXI call shown piped or sent to
`/dev/null`, and only that. It cannot see a search over a redirect file, so the located-line rule is
carried by the text and its pin (§S7) alone.

### §S2 — The reading rule, in the generated definitions

1. **The tool-usage client clause.** Each of the four role templates
   (`generator/templates/{red,green,verify,fix}.md.tmpl`) replaces "crucible client(-calls) via
   `ctx_shell` is (are) the short-command exception" with: every AXI command — the crucible client
   included — runs through `ctx_shell` with `raw=true`, and its envelope is read as the
   output-discipline line says.
   - **The hyphen is deliberate.** `line_rule_findings` requires exactly one unit matching
     `\boutput discipline\b`. In `red` and `green` the tool-usage paragraph is a different unit from
     the "Output discipline" bullet, and `output-discipline` does not match that pattern.
   - **The registration lines gain `raw=true`.** The four templates' registration lines and their
     three `lean` passages in `generator/templates/builtin-tools.toml` read "via `ctx_shell` with
     `raw=true`": `red`'s "Run via `ctx_shell` (single short command …)", `green`'s "Via
     `ctx_shell` (short command)", and the "Via `ctx_shell` (short)" that `verify` and `fix` share.
     The rest of their wording, and their `builtin` forms, are unchanged.
2. **The built-in passages.** The four matching `lean` passages in
   `generator/templates/builtin-tools.toml` change with their templates. Their `builtin` forms use
   the same wording, hyphen included, with `bash` in `ctx_shell`'s place: every AXI command — the
   crucible client included — runs through `bash`, and its envelope is read as the
   output-discipline line says. They name no `raw`.
3. **The output-discipline line.** Each template's output-discipline line keeps its summary clause
   and its read-whole clause, and gains two tool-neutral sentences:
   - a long run redirects both streams (`> /tmp/<run>.out 2>&1`) to a file under `/tmp`, and reads
     it with `read` from the envelope's first line, the last line that begins `axi:`, to its end;
   - a run the harness truncates names its full-output file, and the envelope is read whole from it
     with `read` (`offset`/`limit`) when the output shown does not reach back to the envelope's
     first line.
   - The sentences name no lean-ctx, so they render unchanged in both forms and need no passage.
4. **Tool-usage text must not move the long-runs rules.** The new tool-usage text carries none of
   the long-runs rules that `sub-agent-procedure.md` alone holds (`FIELD_RULES`): the tool timeout,
   and never re-invoking blind.
5. **BACKFILL.** BACKFILL cycles run on these four definitions; there is no BACKFILL template.

### §S3 — The context ledger is left alone (skills)

**Where it is stated** (PRD D5, ruled 2026-10-29: here only, never in the templates):
- `sub-agent-procedure.md`, as a new section;
- `orchestration-common.md`, as a bullet.

**What it says, capability-worded:**
- The context-pressure figure that the project's cached-read and compressed-shell tools report comes
  from one context ledger. That ledger is **machine-wide**: shared by every session, sub-agent and
  project on the machine, and measured against a fixed window, not your context.
- **Ignore its hints to evict entries.** **Never evict entries or reset the ledger** during a run:
  - evicting excludes a file for the session;
  - resetting clears the re-read cache that every other session relies on.

**No shutdown step.** No ledger status line is added to the `shutdown` skill.

### §S4 — `AGENTS.md` § Runtime/Tooling (Model B's own)

Three bullets after the existing "Prefer lean-ctx reads" line. Each is one list item with no
nested list, so each is one unit for its pin (§S7).
1. **Every AXI command runs through `ctx_shell` with `raw=true`.** The bullet says, as running
   text:
   - The AXI commands are the Crucible clients, `sandesh`, `modelb-axi`, `worktree-flow.py`,
     `gh-axi`, `chrome-devtools-axi` and `lavish-axi`; compression can cut or reshape their
     envelopes.
   - A long run redirects both streams (`> /tmp/<run>.out 2>&1`) to a file under `/tmp`. That file
     is read with the built-in `read` from the envelope's first line (the last line that begins
     `axi:`) to its end; a search may only locate that line's number.
   - When Pi truncates a run, its notice names the full-output file; the envelope is read whole
     from it with `read` `offset`/`limit`.
2. **lean-ctx's context ledger is machine-wide.** Ignore its evict hints, and never evict or reset
   it during a run.
3. **A repo-wide search from the main checkout skips `.worktrees/`.** The directory is gitignored,
   and lean-ctx's walkers also prune it. Search a CR's in-flight code by passing its worktree's
   path, `.worktrees/<cr>`, never `.worktrees` itself.

Constraints:
- The section keeps its Python ≥ 3.14 line (`test_python_floor`).
- The lines `CLAUDE_HOME_EXEMPT_LINES` match by exact text are untouched.
- **The module counts move with the new module.** Cycle 2's RED adds
  `tests/test_context_ledger_rule.py`, making 113 modules. Cycle 2's GREEN, which edits this file,
  sets both module counts (§ Key Directories and § Testing & QA) to 113, because
  `AgentsMdTestingSectionS6Test` in `tests/test_suite_hygiene.py` requires every count to equal the
  real count. Only the baselines wait for close-out.

### §S5 — The scaffolded `AGENTS.md` lean-ctx section

In scope (PRD D5, ruled 2026-10-29: the lean-ctx section `init` scaffolds into each project's
`AGENTS.md` gains one bullet naming the tool form).

`modelb_axi/scaffold.py` `_render_lean_ctx_section` gains one bullet, after "Prefer lean-ctx's
cached reads and compressed shell…":
- Run AXI commands through `ctx_shell` with `raw=true`.
- When Pi truncates a run, read the envelope whole from the full-output file its notice names.
- lean-ctx's context ledger is machine-wide: ignore its evict hints, and never evict or reset it.

The section is rendered for every project, as today (CR-MDB-088). An existing project's `AGENTS.md`
is not re-rendered (a non-goal).

### §S6 — Regeneration

- `generator/agents/*.md` (20 definitions) is re-rendered with `generator/build.py build`;
  `generator/build.py --check` is clean.
- This repository's `.pi/agents/python-*.md` is re-rendered, byte-identical to
  `generator/agents/python-*`.

### §S7 — The gates

The gates match normalised text (lower-cased, `**` and backticks dropped), so `AXI` is written
`\baxi\b`. A unit is a list item with its wrapped lines, or a paragraph. `ENVELOPE_OR_OUTPUT`,
`READ_WHOLE`, `LOG_FLAG` and `FILTERED` are `tests/test_axi_envelope_read_whole.py`'s symbols.

**`tests/test_axi_envelope_read_whole.py` is extended:**
- **`RULE_PINS` gains four pins.** `ORCHESTRATION_PINS` inherits them, so they cover items 1, 2 and
  5 (orchestration-common, the procedure and the `crucible` skill). One section carries them, each
  in one unit:
  - **uncompressed:** `\buncompressed\b|\braw mode\b`, and one of `\baxi\b` or
    `ENVELOPE_OR_OUTPUT`;
  - **truncated-run file:** `\btruncat`, `\bfiles?\b`, `\b(?:offset|windows?)\b`, `READ_WHOLE`;
  - **the located line:** `\bline(?:'s)? number\b`, `\benvelope\b`,
    `\bnever\b[^.;]{0,30}\bsearch`, `FILTERED`;
  - **`--log` keeps the console stream:** `LOG_FLAG`, `\bconsole\b`, and
    `\b(?:not|never|does not)\b`.
- **The "Report EVERY run" pin** (item 2, the procedure's "Report EVERY run" section): one unit
  with `\btruncat`, `\bfile\b`, `\benvelope\b`, `READ_WHOLE` and `\breport file\b|junit`.
- **The `crucible` `--log` correction pin:** in `skills-src/crucible/SKILL.md`, at least one unit
  carries `LOG_FLAG`, `\bconsole\b`, `\b(?:not|never|does not)\b`, `\bredirect`, `\benvelope\b` and
  `READ_WHOLE`.
- **The `model-b` skill pin:** in `skills-src/model-b/SKILL.md`, at least one unit carries
  `\buncompressed\b` and `\baxi\b`.
- **`OUTPUT_DISCIPLINE_PINS` gains two pins:**
  - **truncated-run file:** `\btruncat`, `\bfiles?\b`, `\b(?:offset|limit)\b`;
  - **long-run redirect:** `\bredirect`, `2>&1`, `/tmp\b`.
- **A new class pins the client clause in both renders (the render pin).** The client-clause unit is
  the unit that matches both `-crucible\.py\b|\bcrucible[- ]client` and `\boutput-discipline line\b`,
  a marker present in both forms.
  - In each lean-ctx render, exactly one unit is the client-clause unit, and it names `\baxi\b`,
    `ctx_shell` and `raw=true`.
  - In each built-in render, exactly one unit is the client-clause unit, and it names `bash` and
    carries no `raw=true`.
  - No rendered definition, in either form, still says "short-command exception".

**A new module, `tests/test_context_ledger_rule.py`:**
- **The ledger pin.** In each of `sub-agent-procedure.md` and `orchestration-common.md`, one unit
  carries all of:
  - `\bcontext ledger\b|\bcontext[- ]pressure\b`;
  - `\bmachine-wide\b`;
  - `\bevict`;
  - `\breset`;
  - `\b(?:never|ignore)\b`.
- **The `AGENTS.md` pins** (§ Runtime/Tooling only):
  - the `raw=true` unit: `ctx_shell`, `raw=true`, `\baxi\b`, `\btruncat|\bfull[- ]output\b`;
  - the ledger unit: `\bmachine-wide\b`, `\bevict`, `\breset`, `\bnever\b`;
  - the worktree unit: `\.worktrees/`, `\bsearch`, `<cr>`.
- **§S5's bullet:** `pointer_findings` in `tests/test_project_tools_setup.py` gains
  findings for a missing `raw=true` and a missing ledger rule. `GOOD_POINTER` and `MUTATIONS` gain
  them too.

## Acceptance criteria

- [ ] **§S1, the reading rule in the skills.** `RuleInEachPlaceTest` items 1, 2 and 5 pass on the
      real files with the extended `RULE_PINS`/`ORCHESTRATION_PINS`. Item 2 also asserts that
      § "Report EVERY run" carries a unit with `\btruncat`, `\bfile\b`, `\benvelope\b`, `READ_WHOLE`
      and `\breport file\b|junit`. The located-line pin passes in all three places.
- [ ] **§S1, the `model-b` skill.** `skills-src/model-b/SKILL.md` passes the `model-b` skill pin
      (at least one unit with `\buncompressed\b` and `\baxi\b`), and
      `ModelBSkillsNameNoLeanCtxToolTest` stays green over it.
- [ ] **§S1, the `--log` correction.** The `crucible` skill has at least one unit that carries `LOG_FLAG`,
      `\bconsole\b`, a negation, `\bredirect`, `\benvelope\b` and `READ_WHOLE`.
      `tests/test_crucible_verb_surface.py` stays green with its `VERB_SURFACE_STATEMENTS` unchanged.
- [ ] **§S1, wording.** These gates stay green with no baseline change:
      - `test_client_path_anchoring` (the §S4 ratchet, `TOOL_BASELINE == {}`);
      - `ModelBSkillsNameNoLeanCtxToolTest`, and `lean_ctx_tool_findings` over orchestration-common;
      - `ModelBCommonTextNeutralTest`;
      - `AxiEnvelopeGuardedTreeTest`.
- [ ] **§S2, the templates.** For each of the four templates:
      - `output_discipline_findings` passes with the extended `OUTPUT_DISCIPLINE_PINS`;
      - `line_rule_findings` still finds exactly one unit matching `\boutput discipline\b`;
      - no template says "short-command exception";
      - `missing_rules(…, RUN_RULE)` and `manual_run_findings` in `tests/test_client_run_rule.py`
        stay green;
      - `FIELD_RULES`' written-once check in `tests/test_agent_definition_rules.py` stays green.
- [ ] **§S2, both renders.** `agents.render_definitions` over every stack, in memory:
      - In the lean-ctx form, every definition has exactly one client-clause unit (the render
        pin's marker), and it names `\baxi\b`, `ctx_shell` and `raw=true`. At least that
        tool-usage unit names the crucible client with `ctx_shell` and `raw=true`; the registration
        line also carries `raw=true`.
      - In the built-in form, every definition renders (no `AgentRenderError`), names no `ctx_`,
        lean-ctx or `raw=true`, and its one client-clause unit names `bash`.
      - Every output-discipline line carries the redirect and truncated-run sentences in both
        forms.
- [ ] **§S3, the ledger.** The ledger pin passes on `sub-agent-procedure.md` and
      `orchestration-common.md`. No file under `skills-src/shutdown/` gains a ledger step: no unit
      there matches `\bcontext ledger\b|\bledger status\b`.
- [ ] **§S4, `AGENTS.md`.** The three `AGENTS.md` pins pass. `test_python_floor` and the
      `CLAUDE_HOME_EXEMPT_LINES` check stay green. Both module counts read 113 from cycle 2's GREEN
      on, and
      `AgentsMdTestingSectionS6Test.test_s6_every_module_count_in_agents_md_is_the_real_count`
      stays green at every commit.
- [ ] **§S5, the scaffold.** A sandboxed `init` (`HOME`, `MODELB_HOME`,
      `XDG_DATA_HOME` and `PI_CODING_AGENT_DIR` at temp dirs) renders an `AGENTS.md` whose lean-ctx
      section passes the extended `pointer_findings`. Each new finding is proved by its mutation.
- [ ] **§S6.**
      - `generator/build.py --check` is clean.
      - `.pi/agents/python-*` is byte-identical to `generator/agents/python-*`.
      - `RegenerationCleanTest` is green.
- [ ] **§S7, every new detector proved both ways on synthetic text.**
      - **The new pins, by home module:**
        - `tests/test_axi_envelope_read_whole.py`: the four `RULE_PINS` pins (uncompressed,
          truncated-run file, located line, `--log` console), the "Report EVERY run" pin, the
          `crucible` `--log` correction pin, the `model-b` skill pin, the two
          `OUTPUT_DISCIPLINE_PINS` pins, and the render pin;
        - `tests/test_context_ledger_rule.py`: the ledger pin and the three `AGENTS.md` pins
          (`raw=true`, ledger, worktree);
        - `tests/test_project_tools_setup.py`: the two new `pointer_findings` findings, each
          proved by its mutation.
      - **Each new pin:**
        - a conforming sample passes;
        - one cut per pin bites that pin alone (the existing `test_each_cut_bites_its_one_pin` shape);
        - the pins split across two units or two sections do not count.
      - **Each bad sample:** it meets every pin, the new ones included, only through a shown piped
        AXI call, and the gate fails it.
      - **The ledger pin:**
        - bites today's text, which has no ledger rule (a sample with the procedure's current AXI
          section only);
        - spares the `code-health` skill's audit-ledger wording (a sample unit "Ledger mutation is
          Mainline-only" is not a ledger-rule unit);
        - bites a unit that says evict and reset without "never" or "ignore".
      - **The located-line pin** bites a unit that allows locating the line but does not say the
        envelope is never searched or filtered.
      - **The render pin:**
        - bites a lean-ctx sample whose client clause omits `raw=true`;
        - bites a built-in sample that still names `raw=true`;
        - bites a sample whose clause says `"Output discipline" says` (the unhyphenated form, a
          second `\boutput discipline\b` unit).
- [ ] **Migrations (RED).** These pins move with the changed text, each marked
      `# MIGRATED at CR-MDB-090 (§S…)`:
      - **`tests/test_axi_envelope_read_whole.py`:**
        - `RULE_SECTION_SAMPLE`, `RULE_SECTION_CUTS`, `ORCHESTRATION_SAMPLE` and
          `ORCHESTRATION_CUTS` gain the four new pins and their cuts;
        - `RULE_SECTION_BAD` and `ORCHESTRATION_BAD`'s `--note` strings gain the new pins' words;
        - `OUTPUT_DISCIPLINE_SAMPLE`, `OUTPUT_DISCIPLINE_CUTS` and `OUTPUT_DISCIPLINE_BAD` gain the
          redirect and truncated-run sentences;
        - `RulePlaceGateProofTest.test_todays_template_wording_bites`' expected `lacks` list gains
          the two new output-discipline pins;
        - `test_section_pins_split_across_two_sections_do_not_count`'s expected message is
          re-derived if the moved bullet changes;
        - all §S1–§S2.
      - **`tests/test_project_tools_setup.py`** (§S5): `GOOD_POINTER` and
        `LeanCtxPointerDetectorTest.MUTATIONS`.
      - **No other test pins the replaced wording.** "short-command exception" has no hit under
        `tests/`. RED re-greps before it commits and lists every migrated test by id.
- [ ] **A live check, before the merge.** In a Pi session on the branch, the orchestrator runs one
      Crucible client run large enough to truncate, through `ctx_shell` with `raw=true`.
      - The result text names the saved full-output file.
      - `read` opens it with no permission prompt.
      - Its last lines hold the whole envelope.

      The observed notice is recorded in the merge sign-off. No test pins Pi's file name or notice
      text, because they belong to the harness.
- [ ] **Runs.**
      - The suite is green through the client, with a real `HOME` and an empty one; the empty
        `HOME` stays empty.
      - The skills load in Pi with no diagnostics, and every touched skill's frontmatter is
        unchanged.
      - New tests use a literal `§`.
      - `AGENTS.md`'s module count (two places, 113, set in cycle 2) and its baselines (recorded
        at close-out) match the measured suite.

## Non-goals

- **A runtime hook that blocks a piped AXI call.** PRD D5's 2026-10-16 ruling and CR-MDB-072's
  non-goal stand. A hook would also miss the commonest breach seen here, a redirect to a file that is
  never read.
- **`contracts/lean-ctx.md`** (its ledger section, the 3.11.4 refresh) and the upstream request for a
  verbatim class for declared test clients. Both belong to CR-MDB-092.
- **A per-project `excluded_commands` for the clients** (CR-MDB-091's `.lean-ctx.toml`). It is a
  prefix match that `cd … &&` defeats, and it still truncates above 4000 tokens.
- **A shutdown `ledger status` line.** The CLI is not read-only (it prunes and saves when the daemon
  is down). It reports the daemon's stale copy, and it decides nothing.
- **Which tests a role runs** (CR-MDB-083's test-scope ladder), and **checking `ok=` / re-registering
  on a 409** (CR-MDB-054 item 5).
- **Pinning Pi's temp-file name or notice text.** They belong to the harness. The live build,
  `@earendil-works/pi-coding-agent`, carries them in its `dist/core/tools/bash.js`, and they may
  change with it. The live check records them.
- **`TMPDIR` set off `/tmp`.** The saved file then sits outside the policy's allowed reads, and
  reading it prompts the user, as any outside read does.
- **Re-rendering an existing project's `AGENTS.md`.** It is not re-rendered; `migrate` (CR-MDB-082)
  owns that.
- **`sandesh.md`, `chrome-ui-relay`, and `rust.toml`'s and `quarkus.toml`'s `--log` lines.** Their
  envelopes are short, or their rule is already stricter, or searching a runner log stays allowed.
- **The registration lines' wording** ("single short command"). `register` is short, and §S2's rule
  covers every client call. The lines gain only `raw=true` in their lean-ctx form (§S2.1).

## Cycle plan

No commit sits red past its own cycle: each cycle's RED migrates every test that reads the text that
cycle changes. GREEN changes the text and regenerates. Nobody runs the full suite between cycles; the
orchestrator's pre-merge gate runs it once, in the last cycle.

1. **The reading rule, in the skills and the definitions** (§S1, §S2, §S6, and §S7's
   `test_axi_envelope_read_whole.py` part). Red-green.
   - **RED:** extends and migrates `tests/test_axi_envelope_read_whole.py`, and proves each new pin
     both ways.
   - **GREEN:** edits the four skill files (the procedure, orchestration-common, the `crucible`
     skill and `model-b/SKILL.md`), the four templates, their four tool-usage passages and three
     registration passages, then runs `generator/build.py build` and re-renders
     `.pi/agents/python-*`.
   - **Modules RED and GREEN run:**
     - `tests.test_axi_envelope_read_whole`
     - `tests.test_crucible_verb_surface`
     - `tests.test_client_path_anchoring`
     - `tests.test_execution_knowledge_rules`
     - `tests.test_orchestrator_rule_triage`
     - `tests.test_harness_neutral_skills`
     - `tests.test_agent_definition_rules`
     - `tests.test_client_run_rule`
     - `tests.test_agent_generator`
     - `tests.test_project_tools_setup`
     - `tests.test_verify_spec_pre_review_mode`
     - `tests.test_raw_runner_guard`
     - `tests.test_model_b_skill`
     - `tests.test_crucible_skill`
     - `tests.test_orchestration_rules_from_crucible`
     - `tests.test_core_split`
     - `tests.test_worktree_isolation_text`
     - `tests.test_skill_frontmatter`
2. **The ledger, `AGENTS.md` and the scaffold bullet** (§S3, §S4, §S5, and §S7's
   `test_context_ledger_rule.py` and `pointer_findings` parts). Red-green.
   - **RED:** writes `tests/test_context_ledger_rule.py`, and migrates `GOOD_POINTER`/`MUTATIONS`.
   - **GREEN:** edits the procedure, orchestration-common, `AGENTS.md` (its three bullets, and both
     module counts set to 113) and `_render_lean_ctx_section`.
   - **Modules RED and GREEN run:**
     - `tests.test_context_ledger_rule`
     - `tests.test_project_tools_setup`
     - `tests.test_scaffold`
     - `tests.test_python_floor`
     - `tests.test_harness_neutral_skills`
     - `tests.test_execution_knowledge_rules`
     - `tests.test_orchestrator_rule_triage`
     - `tests.test_client_path_anchoring`
     - `tests.test_axi_envelope_read_whole`
     - `tests.test_agent_definition_rules`
     - `tests.test_raw_runner_guard`
     - `tests.test_suite_hygiene`
     - `tests.test_cite_by_symbol`
     - `tests.test_tooling_detachment`
     - `tests.test_claude_era_retirement`
     - `tests.test_prd_criteria`
     - `tests.test_worktree_layout_and_bundles`
3. **Verify.** VERIFY reads every AC and runs the live check's evidence review. The orchestrator then
   runs the pre-merge gate and records the `AGENTS.md` baselines at close-out; the module count was
   set in cycle 2.
