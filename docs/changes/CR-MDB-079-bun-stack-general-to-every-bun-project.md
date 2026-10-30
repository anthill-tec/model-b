# CR-MDB-079 — The bun stack is general to every Bun project

**Status:** PENDING — spec drafted 2026-10-30 from the gap analysis and the user's rulings
(DN-multi-harness-deploy-model §D25, amended 2026-10-30); the spec pre-review's findings folded in
2026-10-30 (S1–S8 and its suggestions), with the user's rulings of 2026-10-30 that the workflow's own tools
(Sandesh, Crucible, lean-ctx) and the Pi extensions that provide its functionality are workflow vocabulary,
named in any stack and never a term of the generality guard.
**Type:** fix (generator stack content; a generality guard over every stack file; one hook reason line)
**Priority:** P1 — release 1.0.0, wave 2; before CR-MDB-052. CR-MDB-084 and CR-MDB-087 follow it in the
wave, each removing its own exception from §S5's guard.
**Depends on:** nothing on the board (board-authoritative: read `queue`, not this line).
**Labels:** generator, stacks, bun, hooks, generality
**Points:** 8 (scored 5 at gap analysis; re-scored 8 when the generality guard widened from `bun.toml` to
every `generator/stacks/*.toml`: two term tiers, an exception list with its stale rule and its own proofs,
and five stack files read instead of one; the spec pre-review found 8 right). No split: the guard's tree
check fails on today's `bun.toml`, so it and the rewrite land in one cycle.
**Design reference:** DN-multi-harness-deploy-model §D25 and its amendment of 2026-10-30 (user rulings at
CR-MDB-079's gap analysis: no stack file names one project, with `arduino.toml` and `quarkus.toml` named
exceptions; the bun stack runner-neutral on the client's 0.4.0 surface; the bun hook's interim line;
the workflow's own tools and the Pi extensions that provide its functionality named in any stack and never
flagged);
§D21 (no client steered through the environment), its 2026-10-13 amendment (runner names in plain words
in guarded text) and its 2026-10-30 amendment (the bun reason's tier-verb redirect); §D26 (a client gap is
stated in the stack file); CR-MDB-066 §S3 (the bun reason) and its non-goal handing this CR
the `bun test` and Sandesh defaults; PRD D5, ruling of 2026-10-29 (RED commits its failing tests); `docs/research/PROPOSAL-go-stack-and-bun-frontend-generality.md`
§4/§4.1 (as ruled by §D25).
**Merge precondition:** Sandesh's reply to #1502 — **MET** (Sandesh #1503, 2026-10-30: its bun and
Pi-extension specifics are in its own `AGENTS.md`, Sandesh `develop` @ `93fe2f4`; CR-MDB-079 cleared to
merge).
**Merge precondition (Crucible):** **MET** — Crucible #1510 (2026-10-30, read from its develop client,
`bun-crucible.py`) answered the four questions of the cycle plan's step 4: (a) and (b) yes, so §S1.1 and
§S1.6 stand; (c) and (d) go to the 0.4.0 doc-sync CR (§S1's lead paragraph).

## Context

`generator/stacks/bun.toml` was distilled from the Sandesh Pi-extension agents
(`archive/wave3/agents/bun-*`) and never made general. About 30 of its 99 lines describe one project:
a thin TypeScript shim that shells to the `sandesh` CLI, `pi.exec` and `registerTool` mocks, exact
`sandesh` argv, the tool-parameter → CLI-flag mapping table, TypeBox schemas, Sandesh-core's purity, the
Pi extension API sources, and `integrations/pi/` as the default package dir. They sit in `mechanics` and in
every role's `gotchas`. Every project with `bun` in `PROJECT_STACKS` gets the four bun agents rendered from
it: Crucible (`bun,python`) runs them today, and Arduino App Lab (`go,bun`, Vitest under Bun) would get the
same.

Read at gap analysis (2026-10-30, by reading; no run):

- **Sandesh reported that the old text had also drifted from its live shim** (#1503); the specifics are
  Sandesh's, in its `AGENTS.md` @ `93fe2f4`, and none of them enters Model B. Sandesh now passes its
  package dir explicitly.
- **The stack presumes Bun's own runner:** "Bun's test runner" (header, `mechanics`, the RED description)
  and `bun:test` imports.
- **The bun hook's runner line is half wrong** (Crucible #1500): CR-MDB-066 §S3.4 wrote "`test` and
  `regression` run `bun test`". Since CR-CRU-194, `test` runs the project's declared test script
  (`crucible.testScript` in `package.json`), else `bun test`.
- **Two more stack files name one project.** `arduino.toml` names the Sheetal firmware (`Sheetal`,
  `sheetal-firmware` in its commands and layout, `CR-SHE-005` to `CR-SHE-009`); `quarkus.toml` names one
  service's architecture (`UuidV7Generator`, `ServerEvent`, `eventBus.emit`). CR-MDB-084 and CR-MDB-087
  make them general; until then they are §S5's named exceptions.
- **What leaves is one project's design:** the Sandesh Pi extension's own. The workflow's own tools and the
  Pi extensions that provide its functionality stay named wherever the workflow needs them, in any stack
  (DN-multi-harness-deploy-model §D25, amended 2026-10-30).
- **The released client** (`~/.crucible/clients/bun-crucible.py`, 0.3.0, read in its source) and Crucible
  0.4.0, which Model B 1.0.0 ships against, differ in five places (the fifth, the report path on a `test` run,
  confirmed by Crucible #1510); the tier verbs are unchanged as far as Crucible has stated. The shipped text states 0.4.0:

  | Surface | 0.3.0 (installed) | 0.4.0 (Crucible's statement) |
  |---|---|---|
  | `test` | always Bun's own runner (`cmd_test`) | `crucible.testScript`, else Bun's own runner (CR-CRU-194) |
  | `test --tests <file>` | Bun's own runner on the file | the declared script on the file(s) (CR-CRU-194): appended after the client's report flags with no `--` by default, after a `--` when the script declares `env:<VAR>` (Crucible #1510) |
  | package dir | `--package-dir` > `$BUN_CRUCIBLE_PACKAGE_DIR` > `<project>/integrations/pi` > root | `--package-dir` > `BUN_CRUCIBLE_PACKAGE_DIR` > the project `crucible.toml` > root |
  | `regression` | full Bun run, lcov with `--coverage` | changed by CR-CRU-222 (shape not yet stated) |
  | tier verbs | the declared `test:<tier>` by name; `--` passthrough; refused when undeclared; report path by `crucible.reportPath.<target>` | unchanged as stated |
  | report path on a `test` run | `crucible.reportPath.<target>` read only for a declared tier target | `crucible.reportPath.<script>`, the target being `crucible.testScript`'s own name (Crucible #1510) |

- **Guarded text names runners in plain words** (§D21, 2026-10-13): `bun.toml` and `generator/agents/` are
  in the raw-runner guard's `GUARDED_ROOTS`, so a code span holding `bun test`, `vitest` or `bun run test`
  is a finding there unless a prohibition governs it; the hook (`hooks-src/`) is not guarded.
- **No test pins the Sandesh text.** The gates the new text meets: the raw-runner guard; the client contract
  against the installed client's `--help` and the `generator/stacks` invocation floor (28; ≈ 36 today, bun 8);
  the `test_s6b_*` tier checks; `ReleasedClientPathS8Test`; the built-in form (`builtin_form` raises on a
  `ctx_` or lean-ctx mention), one client clause per render, harness tool names; `generator/build.py --check`.
  The registry-key detector does not read `generator/stacks/` (`GATE_ROOTS`), and §S6's line names no
  key-shaped name, so `NOT_REGISTRY_KEYS` is unchanged.

**Baseline:** measured by the orchestrator through the client before the branch cut, 2026-10-30
06:33–06:42 UTC, develop `cd77a22`, `MODELB_HOME`/`XDG_DATA_HOME`/`PI_CODING_AGENT_DIR` at temp dirs:
real `HOME` 4714 tests, 4713 passed, 0 failed, 1 skip (the pi-subagents service-key check, its package
absent under the temp `PI_CODING_AGENT_DIR`); empty `HOME` 4714 tests, 4702 passed, 0 failed, 12 skips (the
absent installed Crucible clients, `pi` and `sandesh`, as `AGENTS.md` lists), the temp `HOME` empty
afterwards. 114 modules.

## Scope

### §S1 — What `bun.toml` carries (what holds for every Bun project)

`generator/stacks/bun.toml` is rewritten to Appendix A. Its 0.4.0 statements (what `test` and
`test --tests <file>` run, the report path, the gap, the package dir in `crucible.toml`) are Crucible's,
confirmed by Crucible #1510 (2026-10-30) — all but the gap: 0.4.0's `test` takes `--name`, which reaches a
declared script as `-t <PATTERN>`. The shipped text keeps the gap, which is true of the installed client its
contract check reads, and the 0.4.0 doc-sync CR drops it, with the package dir's `crucible.toml` key
(Crucible #1510 (d)). It carries:

1. **The client** — its verbs (`register`, `test`, `check`, the tier verbs, `unregister`); that `test`
   runs the project's declared test script (`crucible.testScript` in `package.json`), else Bun's own runner
   (named in plain words); the stale report wiped; the ingest line confirmed; the known gap (no test-name
   filter).
2. **The package dir** — runs happen in the package dir of a Bun workspace. The dir is the project's,
   passed on each run (`--package-dir <dir>`) or declared in the project's `crucible.toml`; the text names
   the file, not its key, which is Crucible's (§D25, amended 2026-10-30). No default dir is named.
   `$BUN_CRUCIBLE_PACKAGE_DIR` is not named: Model B never steers a client through the environment (§D21).
3. **The `check` typecheck gate.**
4. **Tiers from the scripts the project declares** — the five declared cells `test:unit`, `test:module`,
   `test:integration`, `test:e2e`, `test:bdd` (not `test:regression`, which is not a declared cell);
   the client's tier verb, with `--` passing a target to the declared script; an undeclared tier is refused.
5. **A workspace package as the `module` tier** — a `module` run with `--package-dir <package>` runs that
   package's declared `test:module` (§D25, amended 2026-10-30).
6. **Report path for another runner** — a target run by a runner other than Bun's own declares how it is told
   its report path, `crucible.reportPath.<target>`, named in `mechanics`; the default appends Bun's own
   report flags (§D25, amended 2026-10-30).
7. **Third-party sources** — the installed package under the package's `node_modules/`, at the version
   `bun.lock` pins. (The four templates point at this bullet: "this stack's sources are listed in 'Stack
   mechanics' below".)
8. **Generated files are never hand-edited**; regenerated with the project's own command.
9. **The runner-neutral quality rules** — `strict`, no `any`, no swallowed errors, no `.only`/`.skip`/
   `.todo`, the test count moves, exact-value / negative / error / mock-received assertions, no floating
   promises.

### §S2 — Runner-neutral

1. Tests import from the runner the project declares (Bun's own runner, or another such as Vitest on the
   Bun runtime); the text names neither module in a code span and presumes neither.
2. The header comment and `[description].red` say "the project's declared runner on the Bun runtime", not
   "Bun's test runner". `[description].green` drops "/tool".
3. Assertion patterns use the `expect` matchers Bun's own runner and Vitest share.

### §S3 — The Bun runtime facts

1. **`bunfig.toml` is read from the current directory only:** a root `[run] bun = true` does not reach a run
   in a package dir; confirm a package's runs execute on Bun, not on a system Node — in `mechanics` and in
   `gotchas.verify`.
2. **Strict ESM linking:** a named import the module does not export fails at link time (other runtimes
   yield `undefined`); such a failure is a real defect, not a runner quirk — in `gotchas.verify` and
   `gotchas.fix`.

### §S4 — What leaves `bun.toml`

1. **The Sandesh Pi extension's own design:** the thin TS shim, `pi.exec` mocks and `registerTool` spies,
   `ExtensionAPI`, `AgentToolResult`, TypeBox and `StringEnum`, the tool-parameter to CLI-flag mapping
   table and exact-argv assertions, Sandesh-core and PE3, `@earendil-works/pi-coding-agent` as test-API
   guidance, `integrations/pi/` as a default dir, the shim's environment fallback, and with it everything
   #1503 lists. It leaves as one project's design, not because it names Sandesh: the workflow's own tools
   stay named wherever the workflow needs them (see the Context). It goes into no memory template and no
   other shipped Model B file; Sandesh holds it.
2. **Never enters:** framework, test-library or project-architecture text — React, a DOM environment
   (jsdom, happy-dom), Testing Library, MSW, Wails, VanJS, TanStack, `fake-indexeddb` — and Bun's
   process-wide module-mock leak, a fact about one runner (§D25, amended 2026-10-30).

### §S5 — The generality guard: no stack file names one project

In `tests/test_stack_reference_material.py`, beside `QUARKUS_TOML_FORBIDDEN` and `rewording_findings`
(DN-multi-harness-deploy-model §D25, amended 2026-10-30):

1. **The terms.** A term is matched in one of four ways: a *word* (case-insensitive, between
   non-alphanumerics or the text's ends; the boundary class is `[A-Za-z0-9]`, so `_` is a boundary and
   `Sheetal` matches in `SHEETAL_PORT`, unlike the `(?<![A-Za-z0-9_])` of the precedent
   `rewording_findings`), a *case word* (the same, case-sensitive), a *substring*
   (case-sensitive) or a *pattern* (a regular expression). `STACK_GENERALITY_TERMS` maps a stack to its
   terms, with `"*"` for the terms every stack is checked against:
   - **`"*"` (every stack)** — the project identifiers measured in today's stack files: words `Sheetal`
     (it also covers `sheetal-firmware`), `UuidV7Generator`, `ServerEvent`, `eventBus.emit`, `PE3`;
     substrings `CR-SHE-` and
     `integrations/`; and the Java project's names, taken from `PROJECT_NAMES` (CR-MDB-086 §S4.1, read, not
     edited) as substrings: `fourpm` (it also covers `org.fourpm`, which is therefore not a second term),
     `store-utils` and `4pm-Store-utils`.
   - **`"bun"`** — the Sandesh Pi extension's test design (none of these terms
     matches inside `sandesh`, `$SANDESH_…` or
     `sandesh-relay`, nor inside any name of Pi's own extension API, which is workflow vocabulary too):
     words `typebox`, `StringEnum`, `Sandesh-core`, `thin TS shim`, `CLI-flag mapping`,
     `exact argv`; and, from the gap analysis, words `jsdom`, `happy-dom`, `testing-library`,
     `Testing Library`, `msw`, `Wails`, `VanJS`, `TanStack`, `fake-indexeddb`; case words `React`, `DOM`;
     substrings `from "bun:test"` and `Bun's test runner`; the pattern for a named default package dir,
     `` package dir\W*\(default\s+`[^`]+`\) `` (a default stated for anything but a package dir,
     such as "(default `crucible.toml`)", is no match).

   No two terms of one stack's list overlap, so a sample holding one term yields one finding.

   **The workflow's own vocabulary is never a term** (DN-multi-harness-deploy-model §D25, amended
   2026-10-30). The workflow's own tools and the Pi extensions that provide its functionality (Sandesh,
   Crucible, lean-ctx, Pi itself (`@earendil-works/pi-coding-agent`), pi-subagents for sub-agent dispatch and worktree isolation, the `process` tool,
   sandesh-pi for the wake path, pi-permission-system, pi-lens and web search) are named in any stack: their
   names, CLIs, env vars and tools (`sandesh`, `SANDESH_PROJECT`, `crucible`, `*-crucible.py`,
   `crucible.toml`, `crucible.testScript`, `lean-ctx`, `ctx_*`, `pi-*`, `process`, `subagent`, and Pi's own
   extension API: `pi.exec`, `registerTool`, `ExtensionAPI`, `AgentToolResult`). No term
   is one of them, and no substring or pattern term matches inside one. The guard flags one project's own
   architecture only: the Sandesh Pi extension's test design, Sheetal's specifics, one Quarkus service's.
2. **Per stack:** `stack_generality_findings(stack, text)` returns one finding per term of `"*"` and of
   `stack`'s own list found in `text`, in list order, each naming the stack and the term. It reads the whole
   file (the `ctx_*` tool intents in `[roles]` match no term).
3. **The exceptions.** `STACK_GENERALITY_EXCEPTIONS = {"arduino": "CR-MDB-084", "quarkus": "CR-MDB-087"}`:
   each stack that may still carry flagged terms, with the CR that makes it general and removes its entry.
4. **Over the tree:** `stack_tree_generality_findings(stacks, exceptions)`, given each stack's text by name,
   returns:
   - for a stack not in `exceptions`, each of its findings;
   - for a stack in `exceptions` that yields no finding, one stale finding naming the stack and its CR
     ("`arduino.toml` carries no flagged term: remove its exception (CR-MDB-084)");
   - for an exception naming no stack file, one stale finding naming it and its CR.

   So the list cannot go stale: when CR-MDB-084 or CR-MDB-087 lands, its own exception fails the guard until
   it removes the entry.
5. **Reach:** every `generator/stacks/*.toml`, and the four rendered `generator/agents/bun-*-agent.md`
   through `stack_generality_findings("bun", …)`; the other renders follow their stack files through
   `--check`.

### §S6 — The bun hook names what the client runs (seed item 6; Crucible #1500)

1. In `hooks-src/scripts/block-direct-bun-test`'s `REASON`, the line
   "`test` and `regression` run `bun test`; a project whose runner is another (Vitest under Bun) runs its
   suites with the tier verbs." becomes, on **one physical line**, Crucible's interim wording
   (§D25, amended 2026-10-30):
   "`test` runs the project's declared test script (`crucible.testScript`), else `bun test`; `regression`
   runs `bun test`. A project whose runner is another runs its suites with the tier verbs."
2. The docstring's last paragraph becomes, word for word (wrapped as the docstring wraps):
   "It presumes no runner (CR-MDB-066 §S3): its first line names every form it blocks; a tier verb runs
   the `test:<tier>` script the project declares in `package.json`, by name, and the client refuses a tier
   the project declares no script for. `test` runs the project's declared test script
   (`crucible.testScript`), else `bun test`; `regression` runs `bun test`. A project whose runner is
   another runs its suites with the tier verbs (CR-MDB-079 §S6)."
3. Unchanged: the first line (it still names `vitest`, `pnpm`, `yarn`, `--filter`), the tier line, the
   CR-MDB-062 §S4 contract (manifest, client, verbs, the gap "a single test selected by name",
   `ALLOW_RAW_BUN=1` with the orchestrator's approval).
4. Where the bun stack names the client's runs, it names `crucible.testScript` too (§S1.1).
5. The `regression` half is reworded by the 0.4.0 doc-sync CR once CR-CRU-222 ships; that CR is filed when
   Crucible 0.4.0's release notes arrive (§D25, amended 2026-10-30), not by this CR.

### §S7 — The gates this change moves (named migrations)

1. **`tests/test_client_path_anchoring.py`** (§S6):
   - MIGRATED `BUN_REASON_RUNNER_LINE_WORDS`: was (`regression`, `bun test`, `Vitest`, `tier verbs`); becomes
     (`` `test` runs``, `crucible.testScript`, `` else `bun test` ``, `` `regression` runs `bun test` ``,
     `tier verbs`). "Vitest" stays pinned through `BUN_REASON_FIRST_LINE_WORDS` (`vitest`).
   - NEW `_STALE_RUNNER_LINE` (`` `test` and `regression` run ``, case-insensitive, whitespace-tolerant);
     `bun_reason_findings` gains the finding "it still says `test` and `regression` run `bun test`".
   - MIGRATED `_SYNTHETIC_RUNNER_LINE` to §S6.1's text; `_SYNTHETIC_BUN_REASON` follows.
   - MIGRATED `test_s1_bun_reason_detector_reports_each_point_cut_alone`: the cuts "regression off",
     "bun test off" and "Vitest off" are replaced by "`test` runs off", "crucible.testScript off",
     "else bun test off" and "regression half off"; "tier verbs off" and "split over two lines" (now
     split at ". A project") stay; a new cut appends the stale line to a conforming reason → exactly the
     stale finding.
   - NEW `bun_docstring_findings(doc)` and a test: the real docstring
     (`ast.get_docstring`) names `crucible.testScript` and carries no `_STALE_RUNNER_LINE` match.
2. **`tests/test_stack_reference_material.py`** (§S1–§S5): NEW `STACK_GENERALITY_TERMS`,
   `STACK_GENERALITY_EXCEPTIONS`, `stack_generality_findings`, `stack_tree_generality_findings`,
   `BUN_TOML_RULES` (rule, key, anchor), `bun_toml_findings(text)` (AC2's three checks, one finding each)
   and their test classes; one of them also holds AC7's count of `bun.toml`'s parsed invocations, read
   through `test_client_path_anchoring`'s `_parse_invocations`. `QUARKUS_TOML_FORBIDDEN` and
   `PROJECT_NAMES` are unchanged (`STACK_GENERALITY_TERMS` reads `PROJECT_NAMES`).
3. **`generator/agents/bun-{red,green,verify,fix}-agent.md`:** regenerated with
   `python3 generator/build.py build --stacks bun`, never hand-edited.

No test module is added (`AGENTS.md`'s count is unchanged). No skip is added. No floor is lowered. No stack
file other than `bun.toml` is edited.

## Acceptance criteria

"Both ways" means a sample that must be caught is caught and a sample that must pass passes. Every check
reads text; nothing runs a runner.

- [ ] **AC1 — §S1/§S2/§S3 content.** `BUN_TOML_RULES` holds one (rule, key, anchor) row per rule below;
      each anchor appears in that key of the real `bun.toml` (one finding per missing row):

      | Rule | Key | Anchor |
      |---|---|---|
      | §S1.1 declared test script | `mechanics` | `` `crucible.testScript` `` |
      | §S1.1 the gap | `mechanics` | `takes no test-name filter` |
      | §S1.2 the package dir | `mechanics` | `` `--package-dir <dir>` `` |
      | §S1.2 the project's file | `mechanics` | `` the project's `crucible.toml` `` |
      | §S1.3 typecheck | `mechanics` | `` `bun-crucible.py check` `` |
      | §S1.4 declared tiers | `tier_guidance` | `` `test:<tier>` `` |
      | §S1.4 passthrough | `tier_guidance` | `` -- <file>` `` |
      | §S1.5 module | `tier_guidance` | `workspace package` |
      | §S1.6 report path | `mechanics` | `` `crucible.reportPath.<target>` `` |
      | §S1.7 sources | `mechanics` | `` `node_modules/<pkg>/` `` |
      | §S1.8 generated files | `mechanics` | `never hand-edited` |
      | §S1.9 strict | `gotchas.green` | `` `strict` TypeScript `` |
      | §S1.9 count | `gotchas.red` | `test COUNT increased` |
      | §S1.9 `.only` | `gotchas.red` | `` `.only` `` |
      | §S2.1 runner-neutral | `mechanics` | `the runner the project declares` |
      | §S3.1 bunfig | `mechanics` | `` reads `bunfig.toml` from the current directory only `` |
      | §S3.1 runtime check | `gotchas.verify` | `system Node` |
      | §S3.2 linking (VERIFY) | `gotchas.verify` | `link time` |
      | §S3.2 linking (FIX) | `gotchas.fix` | `link time` |

      Both ways: Appendix A's text yields no finding; that text with every occurrence of one row's anchor
      removed from that row's key yields exactly that row's finding, for each row.
- [ ] **AC2 — §S1.2/§S1.4/§S2 on the real file.** The real `bun.toml` names no `BUN_CRUCIBLE_PACKAGE_DIR`
      and its `tier_guidance` no `test:regression`; it carries neither `from "bun:test"` nor
      `Bun's test runner` (through `stack_generality_findings`, AC4); its `[description].red` and header
      comment name "the project's declared runner on the Bun runtime". Its other three checks run
      through `bun_toml_findings` (§S7.2), proved both ways: Appendix A's text yields none; that text
      with `BUN_CRUCIBLE_PACKAGE_DIR` added to `mechanics`, with `test:regression` added to
      `tier_guidance`, with the phrase removed from the header comment, or with it removed from
      `[description].red`, yields exactly that one finding.
- [ ] **AC3 — the guard, proved both ways** (§S5), on synthetic text:
      - **each term alone:** every term of `"*"` and of `"bun"`, placed alone in a neutral sentence and read
        as stack `bun`, yields exactly its own finding; the pattern's sample is
        `` the package dir (default `pkg/`) ``, and `integrations/pi/` alone yields exactly the
        `integrations/` finding; each `"*"` term read as stack
        `python` yields exactly its finding, and a `"bun"`-only term read as `python` yields none;
        `sheetal-firmware/` and `SHEETAL_PORT` each yield exactly the `Sheetal` finding;
      - **near misses:** a neutral sample holding "reactive", "react to", "domain", "api.exec",
        "a sheet", "server events", "UUID.randomUUID()", "Vitest on the Bun runtime",
        "Bun's own test runner", "the package dir (`--package-dir <dir>`)" and `ctx_shell` yields none, as
        stack `bun` and as stack `python`;
      - **the workflow's own vocabulary:** a sample holding `sandesh`, `$SANDESH_PROJECT`,
        `$SANDESH_ADDRESS`, `sandesh-relay`, sandesh-pi, "the Sandesh tools", `crucible`, `bun-crucible.py`,
        `python-crucible.py`, `crucible.toml`,
        "(default `crucible.toml`)", `crucible.testScript`, `crucible.reportPath.<target>`, `lean-ctx`,
        `ctx_read`, `ctx_shell`, pi-subagents, `subagent`, the `process` tool, pi-processes,
        pi-permission-system, pi-lens, web search and Pi's own extension API (`@earendil-works/pi-coding-agent`,
        `pi.exec`, `registerTool`, `ExtensionAPI`, `AgentToolResult`) yields none, as every stack in `STACK_GENERALITY_TERMS`
        and as stack `python`; so no term, substring or pattern of any list matches inside one of them;
      - **the tree:** `stack_tree_generality_findings` on a clean synthetic stack with no exceptions yields
        none; on a synthetic stack carrying one term, not excepted, yields exactly that finding; on a
        synthetic excepted stack carrying a term, yields none; on a clean synthetic excepted stack, yields
        exactly the stale finding naming its CR; on an exception naming no stack, exactly that stale
        finding.
- [ ] **AC4 — the guard on the tree** (§S5):
      - every `generator/stacks/*.toml` is read, and `STACK_GENERALITY_EXCEPTIONS` names only stacks among
        them or yields their stale finding;
      - `stack_tree_generality_findings` over today's tree yields `bun.toml`'s findings (cycle 2's RED
        evidence); after GREEN it yields none;
      - the exceptions bite, data-driven: each stack in `STACK_GENERALITY_EXCEPTIONS` yields at least one
        `stack_generality_findings` on its real file (the stale rule's other half); no term is pinned to
        either file, so CR-MDB-084 and CR-MDB-087 remove only their own entry;
      - each exception's CR has a spec under `docs/changes/` (`CR-MDB-084-*.md`, `CR-MDB-087-*.md`);
      - after GREEN, each of the four rendered `generator/agents/bun-*-agent.md` yields no
        `stack_generality_findings("bun", …)`.
- [ ] **AC5 — regeneration.** `python3 generator/build.py --check` is clean; the four bun agents are the
      build's output; `agents.render_definitions(["bun"], ["pi"], …, lean_ctx=False)` raises no
      `AgentRenderError` (the built-in form); `ClientClauseInTemplatesAndRendersTest`,
      `RegenerationCleanTest` and the harness tool-name and `~/.claude` gates pass.
- [ ] **AC6 — §S6.** Read from a real run (blocking `bun test` in a `/tmp` project with `package.json`):
      - the reason keeps `_reason_contract_failures(reason, RUNNER_HOOK_REASONS["block-direct-bun-test"]) == []`;
      - `bun_reason_findings(reason) == []` under the migrated words;
      - one physical line holds §S6.1's two sentences.

      Both ways on synthetic reasons: a conforming one passes, and each cut of §S7.1 alone yields exactly
      its finding (the stale-line cut yields exactly the stale finding). The real docstring yields no
      `bun_docstring_findings`; CR-MDB-066 §S3.4's sentence yields two (no `crucible.testScript`; the
      stale phrase); §S6.1's text yields none.
- [ ] **AC7 — standing gates.**
      - `GuardedTreeHasNoRawRunnerTest` passes (runners named in plain words in `bun.toml` and the renders);
      - `ClientContractS3Test` passes on the installed client: every `bun-crucible.py` invocation in
        `bun.toml` uses only `--tests`, `--agent` and `--package-dir`; the `generator/stacks` floor (28) and
        the per-source floors hold with no edit, and `bun.toml` carries at least 8 parsed invocations (the
        count is held by a §S7.2 class in `tests/test_stack_reference_material.py`);
      - `ReleasedClientPathS8Test`, `CRUCIBLE_REFERENCE_PINNED`, `CURRENT_SKILLS`
        (`tests/test_pi_agent_definitions.py`) pass unchanged (the three commands, `crucible_reference`
        and `[roles]` are untouched);
      - every `test_s6b_*` check in `tests/test_generator_role_contract.py` passes unchanged;
      - `RegistryKeysDeclaredGateTest` passes and `NOT_REGISTRY_KEYS` is unchanged;
      - `ruff check` exits 0; no test module and no skip is added; every module named in the cycle plan
        passes through the client;
      - VERIFY runs the full suite through the client with a real `HOME` and an empty one, and the empty
        `HOME` stays empty.

## Non-goals

- **`arduino.toml`'s and `quarkus.toml`'s project text:** CR-MDB-084 and CR-MDB-087 (release 1.0.0, wave 2,
  after this CR); here they are §S5's named exceptions, and each CR removes its own.
- **Flagging the workflow's own tools** (§S5.1, its closing paragraph) — Sandesh, Crucible, lean-ctx and the
  Pi extensions that provide the workflow's functionality are named in any stack, and no term flags them.
- **The templates' known-gap line** ("`bun-crucible.py test` takes no test-name filter"): still true;
  the 0.4.0 doc-sync CR re-checks it.
- **The `regression` half of §S6.1:** the 0.4.0 doc-sync CR's, filed when Crucible 0.4.0's release notes
  arrive and worded once CR-CRU-222 ships.
- **`skills-src/crucible-report-bun/`:** Crucible's, byte-faithful.
- **`skills-src/crucible/references/bun.md`:** read; clean; unchanged.
- **The bun hook's forms, markers and tier line:** CR-MDB-066's; unchanged.
- **The 0.3.0 client's `integrations/pi` fallback:** Crucible's code; gone in 0.4.0.
- **Frontend guidance** (DOM environment, Testing Library, MSW, `fake-indexeddb`, the jsdom `Worker`
  stub): §D25 rules frameworks out; the proposal's §4 frontend half is superseded.
- **Bun's process-wide module-mock leak:** a fact about one runner (§D25, amended 2026-10-30).
- **A bun stack skill** under `generator/skills/`: none exists and none is added.
- **`QUARKUS_TOML_FORBIDDEN` and `PROJECT_NAMES`:** CR-MDB-086's; unchanged.
- **`jest`:** outside the hook and the stack text, as CR-MDB-066 left it.
- **The `go` stack:** CR-MDB-080.
- **Re-rendering other projects' agents:** After merge.

## After merge

None of these steps is an acceptance criterion.
1. The user reinstalls the tool from the tree (`uv tool install --reinstall --python 3.14 .`) and
   redeploys (`modelb-axi --reinstall`): the bun hook script changed.
2. The orchestrator recompiles Model B's own wiring and commits it as a chore (§D21, first amendment), if
   the recompiled wiring differs.
3. **After the 1.0.0 release,** each project with `bun` in `PROJECT_STACKS` re-renders its bun agents with
   `modelb-axi agents`: Crucible (`bun,python`) and Sandesh (`bun,python`, restored 2026-10-30). A definition the
   project hand-modified is skipped and reported; `--force-managed` replaces it.
4. The 0.4.0 doc-sync CR, filed when Crucible 0.4.0's release notes arrive, carries the `regression` half
   and re-checks the templates' gap line against 0.4.0's `--help`.
5. CR-MDB-084 and CR-MDB-087 each remove their own `STACK_GENERALITY_EXCEPTIONS` entry when they land;
   §S5.4's stale rule fails their gates until they do. AC4's real-file bite is data-driven, so no other check of
   this CR names their terms. Each should add its own stack's terms to `STACK_GENERALITY_TERMS` as it removes
   its exception: `arduino.toml`'s `docs/research/PRD-arduino-test-stack.md` path, for one, is in no list here.

## Cycle plan

Nothing stays red past a cycle's GREEN: RED commits its failing tests on their own (test-only), and GREEN
makes them pass in the same cycle, once `ruff check` exits 0 (PRD D5, ruled 2026-10-29). A test that reads
a file a cycle changes is migrated in that cycle. Nobody runs the full suite between cycles; VERIFY runs it
once. Each cycle runs, through the client, the modules it names, plus the docs gates of `AGENTS.md`
(`tests.test_client_path_anchoring`, `tests.test_project_registry_schema`, `tests.test_suite_hygiene`,
`tests.test_archive_mapping`, `tests.test_cite_by_symbol`, `tests.test_harness_neutral_skills`,
`tests.test_axi_envelope_read_whole`, `tests.test_orchestration_rules_from_crucible`,
`tests.test_raw_runner_guard`, `tests.test_tooling_detachment`, `tests.test_claude_era_retirement`,
`tests.test_prd_criteria`). A module found reading an edited file and not named is run too, and named in
the cycle's report.

0. **Before the branch (orchestrator, not a cycle):**
   - the baseline, through the client, with real and empty `HOME`, recorded above;
   - the DN record: done — the user's rulings, the bun hook's interim line among them, landed as
     DN-multi-harness-deploy-model §D25's amendment of 2026-10-30;
   - `cr-plan --points 8`, re-sending the title, release 1.0.0 and wave 2.
1. **The bun hook's runner line** (§S6, §S7.1). Red-green.
   - **RED:** the migrated words, synthetic line and cuts; `_STALE_RUNNER_LINE`; `bun_docstring_findings`
     and its test. The real reason and docstring fail them.
   - **GREEN:** `REASON` and the docstring of `hooks-src/scripts/block-direct-bun-test`.
   - **Modules:** the docs gates, plus the hook-script readers: `tests.test_runner_hooks`, `tests.test_hooks`,
     `tests.test_pi_hook_runtime`, `tests.test_bootstrap_shutdown_registry`, `tests.test_installer_assets`,
     `tests.test_deployed_script_rendering`, `tests.test_hooks_compiler`, `tests.test_init_hook_script_check`,
     `tests.test_hook_retirement`, `tests.test_coverage_gate`, `tests.test_lint_rule_set`,
     `tests.test_crucible_project_config`, `tests.test_deployed_script_invocation`,
     `tests.test_worktree_flow_surfaces`, `tests.test_orchestrator_references`, `tests.test_toon_codec`,
     `tests.test_python_floor`, `tests.test_package_publishing`, `tests.test_installer_correctness`,
     `tests.test_installer_stack_selection`, `tests.test_ambient_manifest_discovery`,
     `tests.test_ambient_status_contract`, `tests.test_scaffold` (it names `block-direct-bun-test`).
2. **The general bun stack and the generality guard** (§S1–§S5, §S7.2–§S7.3). Red-green.
   - **RED:** `STACK_GENERALITY_TERMS`, `STACK_GENERALITY_EXCEPTIONS`, `stack_generality_findings`,
     `stack_tree_generality_findings` and their synthetic proofs (AC3); `BUN_TOML_RULES` and its bite
     proof (AC1); `bun_toml_findings` and its bite proof (AC2); the tree checks (AC2, AC4); the count of
     `bun.toml`'s parsed invocations (AC7). The tree checks fail on today's `bun.toml`; the synthetic
     proofs, the exceptions' data-driven bite, their CR-spec check and the invocation count pass on
     arrival and are labelled so.
   - **GREEN:** `bun.toml` per Appendix A; `python3 generator/build.py build --stacks bun`; the four
     renders committed with it. `GuardedTreeHasNoRawRunnerTest` and `ClientContractS3Test` pass on the new
     `bun.toml` and renders in this cycle.
   - **Modules:** the docs gates, plus the generator readers: `tests.test_stack_reference_material`,
     `tests.test_generator_role_contract`, `tests.test_agent_generator`, `tests.test_pi_agent_definitions`,
     `tests.test_agent_definition_rules`, `tests.test_project_tools_setup`,
     `tests.test_gap_analysis_reach_and_pre_review`, `tests.test_installer_assets`,
     `tests.test_worktree_layout_and_bundles`, `tests.test_client_run_rule`, `tests.test_skill_frontmatter`,
     `tests.test_verify_spec_pre_review_mode`, `tests.test_crucible_skill`,
     `tests.test_board_holds_the_queue`, `tests.test_client_verb_sweep`, `tests.test_rust_stack_generator`,
     `tests.test_stack_skills`, `tests.test_orchestrator_rule_triage`; `tests.test_raw_runner_guard` and
     `tests.test_client_path_anchoring` (docs gates) carry the two cross-stack readers above.
3. **Verify.** VERIFY runs the full suite once, without coverage, through the client (§D26), with a real
   `HOME` and an empty one, and reads every AC. The orchestrator then runs the pre-merge gate and records
   the `AGENTS.md` baselines at close-out.
4. **Before the merge (orchestrator, not a cycle; the Crucible merge precondition):** the orchestrator
   tells Crucible over Sandesh (seed item 7) that the bun stack is general and what its re-rendered agents
   lose, and asks Crucible:
   - (a) how 0.4.0's `test --tests <file>` hands the files to `crucible.testScript`;
   - (b) whether a `crucible.testScript` run honours `crucible.reportPath.<target>`, and under which
     target name;
   - (c) whether 0.4.0's `test` still takes no test-name filter;
   - (d) that the project's `crucible.toml` declares the package dir.

   A "no" to (a) or (b) re-opens §S1.1/§S1.6 before the merge; the other answers go to the 0.4.0
   doc-sync CR. Sandesh is already told (#1502/#1503).

## Appendix A — proposed `bun.toml` text

Runner names appear in plain words (§D21); code spans hold only the client, flags, files and keys. The
text carries 9 parsed client invocations (3 `toml`, 6 `span`). `[roles.*]`, `test_command`,
`register_command`, `unregister_command`, `crucible_reference` and `display_name` are unchanged, and so are
`[description].verify` and `[description].fix` (shown as "(unchanged)").

```toml
# Stack parameters — Bun/TypeScript (the project's declared runner on the Bun runtime, via bun-crucible.py)
# Distilled from the pre-CR-MDB-008 agent originals (archive/wave3/agents/bun-*); generalised to every
# Bun project by CR-MDB-079 (DN-multi-harness-deploy-model §D25).

mechanics = '''
- **Framework/client:** the test runner the project declares, on the Bun runtime, driven through `bun-crucible.py` (`register` / `test` / `check` / the tier verbs / `unregister`). `bun-crucible.py test --tests <file>` runs the project's declared test script (`crucible.testScript` in `package.json`) on the given file(s), else Bun's own test runner; it wipes the stale JUnit report so only THIS run ingests, parses + ingests it, and prints `ingest: ok=True ... failed=N` — confirm it. `bun-crucible.py test` takes no test-name filter: a one-test run is a known client gap — target the file, and raise the gap with the orchestrator when one test must run alone.
- **Run in the package dir of the Bun workspace,** not the repository root unless the root is the package. The dir is the project's: pass it on every run (`--package-dir <dir>`) or declare it in the project's `crucible.toml`. A wrong cwd gives "0 tests" or phantom missing-module errors. Read the package's `package.json`/`tsconfig.json`; the test files are the ones the declared runner collects.
- **Bun reads `bunfig.toml` from the current directory only,** so a root `[run] bun = true` does not reach a script run in a package dir. Confirm the package's runs execute on Bun, not on a system Node (each package carries its own `bunfig.toml`, or the project's equivalent); a run on the wrong runtime proves nothing about Bun.
- **A target run by a runner other than Bun's own** declares how it is told where to write its JUnit report — `crucible.reportPath.<target>` in `package.json`, as `env:<VAR>` — since the default appends Bun's own report flags. A target that writes no report is a starved run, never a pass.
- **Imports:** import the test API from the runner the project declares — Bun's own runner, or another such as Vitest on the Bun runtime; match the imports sibling tests already use, and keep one runner's API per file. Import the code under test by its real relative path. If a test errors for a PATH/typing reason (not a missing SUT symbol), fix the import — that is not a real RED.
- **Quick typecheck gate:** `bun-crucible.py check` (tsc) after each file change.
- **Third-party API sources:** read the installed package under the package's `node_modules/<pkg>/` (its `.d.ts` types and its source), at the version `bun.lock` pins; confirm the declared range in `package.json`. Never assume a signature from memory.
- **Generated files are never hand-edited** — whatever the project's build or code generator writes (its `package.json` scripts and `AGENTS.md` name them); regenerate them with the project's own command.
'''

tier_guidance = '''
- **Bun has no native tier split — the PROJECT declares one.** A runner on Bun knows files and filters, not tiers; the boundary lives in the `package.json` scripts the project declares: `test:unit`, `test:module`, `test:integration`, `test:e2e`, `test:bdd`. Run a tier with the client's tier verb — `bun-crucible.py <tier> --agent YOUR_AGENT_ID` (e.g. `bun-crucible.py integration --agent YOUR_AGENT_ID`) runs the `test:<tier>` script the project declares, by name, and ingests it; what follows `--` reaches that script (`bun-crucible.py unit --agent YOUR_AGENT_ID -- <file>`). Name the script in your report so the next agent can reproduce exactly the same set.
- **Never hand-pick a file list and call it a tier.** Passing `--tests a.test.ts b.test.ts` and ingesting the result as `integration` records a tier the project never defined: the next "same" run selects different files and the two are no longer comparable. A hand-picked list is a TARGETED run — report it as `unit`, and only when every file in it is genuinely dependency-free.
- **A tier with no declared script cannot be honoured here.** With no `test:integration` in `package.json` this stack has no `integration` tier, and the client refuses it — report the tier you actually ran and raise the missing script as a finding. The same holds for `e2e` and `bdd`: Bun ships neither a driver nor a convention for either, so both are unavailable until the project declares one.
- **In a Bun workspace a workspace package is the `module` unit:** a `module` run in a package dir (`--package-dir <package>`) runs that package's declared `test:module`; a workspace that declares no package boundaries has no `module` tier.
- **`regression` means the whole declared suite**, coverage on, not "the tests I happened to touch". A subset rerun after a fix is not a `regression` run whatever its size — and the full sweep is the orchestrator's merge gate, not yours.
'''

[description]
red = "RED phase agent — test specialist for Bun/TypeScript projects (the project's declared runner on the Bun runtime, through bun-crucible.py). Two modes. (1) Write NEW failing tests for a CR spec. (2) Fix BROKEN test compilation/imports so existing tests can run. Does NOT write production code."
green = "GREEN phase agent — implements production TypeScript code to make failing Bun tests pass. Works step-by-step, one module at a time. Does NOT modify tests unless explicitly approved by the orchestrator. Used after RED tests are committed."
verify = "(unchanged)"
fix = "(unchanged)"

[gotchas]
red = '''
- A `TypeError`/missing-export/compile error from a not-yet-existing SUT symbol counts as RED (the client's run surfaces it in the JUnit XML).
- **Verify the test COUNT increased.** N new tests but the total didn't move = silently skipped (wrong file glob, compile error). Never trust a 0-failure result without checking the count.
- **No `.only`/`.skip`/`.todo` left on new tests** — they vacuously "pass".
- **Assertion patterns** (the `expect` matchers Bun's own runner and Vitest share): POSITIVE with the exact value — `expect(result).toEqual(expected)`, never `toBeTruthy()`; NEGATIVE — what must NOT happen (`not.toHaveBeenCalled()`, an absent key); ERROR path — the exact error (`expect(() => f()).toThrow(...)`, `await expect(p).rejects.toThrow(...)`); MOCK — what the mock RECEIVED (`toHaveBeenCalledWith(...)` with the exact arguments).
- **Mocks** come from the declared runner's own API, at the seam the unit crosses (a process call, the network, the clock, the filesystem) — never the unit under test itself; reset them between tests.
- **Conventions:** `describe("<feature>")` + `test("<behaviour> <scenario>")`; async test bodies as `async () =>` (the runner awaits them).
- **Prohibited:** a real network call or a real external process in a `unit` test — that run is `integration`, and its tier is the one the project declares.
'''
green = '''
**TypeScript Code Quality Rules (NON-NEGOTIABLE):**
1. **`strict` TypeScript.** No implicit `any`; type params + returns. No `// @ts-ignore`/`as any` to silence real errors — fix the type.
2. **No swallowed errors.** Don't `catch {}` and drop it; surface the failure in the shape the tests assert, or rethrow.
3. **No unused imports/vars** (TS `noUnusedLocals`); no leftover `console.log`.
4. **Self-check before commit:** swallowed errors? `any` leaks? a value the spec does not state? unused imports? Fix first.

**Implementation conventions:**
- **Module organization:** imports (runtime builtins, then packages, then local) → exports → helpers.
- **Async:** await every promise; pass an `AbortSignal` through where the API takes one; no floating promises.
- **Boundaries:** keep to the module and package boundaries the project declares; a workspace package is reached through its declared entry, never by a path into its sources.
- **Generated files:** regenerate them with the project's command; never edit one by hand.
'''
verify = '''
- **Stack read-only tool lists:** ALLOWED — `bun-crucible.py test` / `check` (run-only; `check` is the `tsc --noEmit` typecheck), `eslint`/`biome` in CHECK mode. FORBIDDEN — a test runner invoked directly, `prettier -w`, `eslint --fix`, `biome ... --write`, or any writer.
- **Wiring checks (stack flavour):** each export, handler or entry the CR lists is actually wired — exported from the package entry, registered where the project registers it, reachable from its caller; count them against the AC.
- **Boundaries:** dependency changes confined to the packages the CR names (`bun.lock` changes only with a dependency change; a type-only package stays a devDependency; no stray runtime dependency); no hand edit to a generated file — regenerate it and compare.
- **Runtime:** the runs executed on Bun, not on a system Node — Bun reads `bunfig.toml` from the current directory only, so check each package's runs, not the root's.
- **Strict ESM linking:** Bun refuses at link time a named import the module does not export (other runtimes yield `undefined`). Such a failure is a real defect in the importing or the exporting module, never a runner quirk — report it as a finding.
- **Quality checklist:** `strict`, no implicit `any`, no `@ts-ignore`/`as any` masking real errors, `tsc --noEmit` clean; no swallowed `catch {}`; camelCase funcs/vars, PascalCase types; no unused imports / stray `console.log`; every promise awaited, no floating promises.
- **Test quality:** one behaviour per test; descriptive names; positive + bound + error + mock-received (exact arguments) assertions; test files named after the feature, never CR/cycle-named.
'''
fix = '''
**Common Bun/TS fixes:**
- **Swallowed error** (`catch {}`) → surface it in the shape the tests assert, or rethrow.
- **`any`/`@ts-ignore` masking a real error** → fix the type.
- **A named import the module does not export** (Bun fails it at link time) → export it or fix the import; it is a real defect, never a runner quirk — never stub it to `undefined`.
- **Unused import/var** → remove (or `_`-prefix). Stray `console.log` → remove.
- **Floating promise / missing `await`** → await it; pass an `AbortSignal` through where the API takes one.
- **A hand-edited generated file** → regenerate it with the project's command.
Fix only the listed findings; keep to the package boundaries the project declares.
'''
```
