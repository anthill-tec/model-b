# CR-MDB-065 — Skill frontmatter parses, and stays within Pi's limits

**Status:** COMPLETED (filed 2026-10-13; gap analysis and pre-review 2026-10-13)
**Type:** fix (skill metadata, guard test)
**Priority:** P1 — release 1.0.0, wave 2.
**Depends on:** CR-MDB-056 (merged; board-authoritative: read `queue`)
**Labels:** skills, frontmatter, pi, guard
**Design reference:** Pi's skill loader (`@earendil-works/pi-coding-agent` 1.2.0, `dist/core/skills.js`);
pi-subagents' (23.4.0) agent loader (`src/config/custom-agents.ts`); DN-multi-harness-deploy-model §D18
(skills are the shared surface).

## Context

Pi reported warnings on three of Model B's deployed skills (2026-10-13). The deployed copies equal
`skills-src/`, so the defects are in the source. Measured with Pi 1.2.0's own exported loader
(`loadSkillsFromDir` over `skills-src/`), which loads 12 skills and emits exactly three diagnostics:

| Skill | Diagnostic | Effect in Pi |
|---|---|---|
| `cr-authoring` | "Nested mappings are not allowed in compact mappings at line 2, column 14" | **not loaded**: a parse failure drops the skill |
| `model-b` | the same | **not loaded** |
| `shutdown` | "description exceeds 1024 characters (1206)" | loaded, with a warning |

Both parse failures come from an unquoted YAML plain scalar containing `: ` (`… Triggers: CR, PRD …`).

**Pi's rules, read from its loader:**
- Frontmatter is parsed with the npm `yaml` package (2.9.0). A throw on a `SKILL.md` is a warning, and
  the skill is not loaded.
- `description` must be a non-empty string. Longer than 1024 (`MAX_DESCRIPTION_LENGTH`, counted as
  JavaScript `length`, i.e. UTF-16 code units) is a warning.
- `name` is at most 64 characters (`MAX_NAME_LENGTH`), matches `^[a-z0-9-]+$`, does not start or end with
  `-`, and has no `--`. When `name` is absent or not a string, the directory name is used. Name errors are
  warnings.
- Other keys are ignored except `disable-model-invocation` (the imported bundles' `metadata` key is
  harmless).
- The loader stops descending into a directory once it finds a `SKILL.md`, so `references/*.md` is never
  read. `skills-src/`'s root `README.md` and `CRUCIBLE-HANDOVER.md` have no frontmatter and are dropped
  silently. `memory-templates/` loads nothing.

**Agents are exposed to the same parser.** pi-subagents reads each agent file with Pi's exported
`parseFrontmatter`, and nothing catches a throw there. It escapes `loadCustomAgents`, which loads the
global and project agents together, and then `AgentTypeRegistry.reload()`. So **one** agent file that
does not parse can stop every custom agent from loading. Model B renders agent frontmatter in
`modelb_axi.agents._emit_pi`, unquoted: `name`, `description` (from `generator/stacks/*.toml`
`[description]`), `tools`, `thinking`, a `permission:` mapping and an optional `model:`. All 20
`generator/agents/*.md` (5 stacks × 4 roles) and the 4 `.pi/agents/*.md` parse today. `generator/agents/`
is the full render, so a check over it covers everything the emitter produces.

**Baseline** (2026-10-13 21:22, `develop` `f2bd3c2`, through the client): real `HOME`, 2285 tests OK,
1 skip (`PI_CODING_AGENT_DIR` sandboxed); empty `HOME`, 2285 OK, 12 skips, and the temp home empty after.

## Scope

### §S1 — The two descriptions parse

`cr-authoring`'s and `model-b`'s `description` stay one-line plain scalars, reworded so they contain
no `: ` (for example "Triggers: a, b" becomes "Use for a, b"). They keep the words the existing gates
read:
- `cr-authoring`: "CR" and "PRD" (`tests/test_cr_authoring_skill.py`);
- `model-b`: "orchestration" and "sub-agent" (`tests/test_model_b_skill.py`, `tests/test_core_split.py`),
  and "board" (`tests/test_board_holds_the_queue.py` `test_description_names_the_board`).

### §S2 — `shutdown`'s description is at most 1024 characters

The description keeps what decides loading:
- the trigger phrases: "/shutdown", "shut down", "stand down", "end of day, close out", "wind down the
  orchestrators", and a Track receiving a shutdown directive from Mainline;
- that it brings ONE orchestrator down cleanly and stops its own wake watcher last;
- graceful by default, with the `emergency` flag;
- the sign-off (`test_shutdowns_description_names_the_sign_off`).

The detail it drops (the Mainline-after-every-Track ordering, the no-role-argument reasoning) is already
in the body and stays there. It has no todo or task-list wording
(`test_frontmatter_descriptions_name_no_todo_or_task_list`).

### §S3 — The guard

A new test module. Its file set is every `skills-src/*/SKILL.md`, `generator/agents/*.md` and
`.pi/agents/*.md`. It has two halves.

**§S3.1 — The stdlib rule, always run.** It covers `name` and `description` only. The other agent keys
(`tools`, `thinking`, `permission`, `model`) and the bundles' `metadata` are covered by §S3.2 alone.

Each file has a well-formed `---` frontmatter with exactly one top-level `name:` line and one
`description:` line. Each value is a one-line plain scalar that YAML can read only as one string:
- not empty;
- no tab and no other control character (U+0000–U+001F, U+007F);
- does not start with a YAML indicator: `- ? : , [ ] { } # & * ! | > ' " % @` or a backtick;
- contains no `: ` and no ` #`, and does not end with `:`;
- is not a YAML core-schema null, boolean or number. A full-value match refuses each of these forms,
  case-insensitively:
  - null: `null`, `~`;
  - boolean: `true`, `false`;
  - integer: decimal, `0x…`, `0o…`;
  - float: decimal, exponent, `.inf`, `.nan`;
  - each with an optional sign;
- is followed by a line that is a top-level key, a comment or the closing `---`. An indented
  continuation line would be folded into the value, so it is refused.

A quoted or block scalar is refused, with a message saying to reword it.

The limits:
- `description` is at most 1024 UTF-16 code units (`len(s.encode("utf-16-le")) // 2`, the unit Pi
  counts).
- A skill's `name` follows Pi's rules (at most 64 characters, `^[a-z0-9-]+$`, no leading or trailing
  `-`, no `--`) and equals its directory name.

The rule is proved on sample text in both directions. Each of these is caught:
- each indicator;
- `: `, and ` #`;
- a tab, including `a\t# b` and `a:\tb`;
- another control character;
- a trailing `:`;
- each null, boolean and number form;
- a quoted value, and a block scalar;
- an indented continuation line;
- a description of 1025 code units, including one where a non-BMP character makes Python's `len`
  1024 or less;
- each name-rule breach.

A clean value, and a description of exactly 1024 code units, pass.

**§S3.2 — Pi's own loader, when it is installed.** The test finds Pi's package root from the resolved
`pi` binary. It runs `node` on Pi's exported API (`dist/index.js`) in a child process. The child's
`HOME` and `PI_CODING_AGENT_DIR` point at temp dirs, and the child writes nothing. It checks:
- `loadSkillsFromDir` over `skills-src/` returns **no diagnostics**, and loads exactly one skill per
  `skills-src/*/SKILL.md`, named as its directory;
- `parseFrontmatter` on each `generator/agents/*.md` and `.pi/agents/*.md` does not throw, and returns
  string `name` and `description`;
- **a standing proof that it can catch a defect:** the same `loadSkillsFromDir` call over a temp dir
  holding one `SKILL.md` that does not parse reports exactly one diagnostic and loads no skill.

When the check cannot run:
- **Skip**, naming what is missing, when `node`, `pi`, Pi's package root or `dist/index.js` is absent.
- **Fail**, naming the export, when `dist/index.js` exists but lacks `loadSkillsFromDir` or
  `parseFrontmatter`. That is a contract break, not an absent tool.

The package-root finder is the one `tests/test_pi_hook_runtime.py` already has (`_find_pi_package_root`).
It moves to `tests/_helpers.py`, and both modules import it. A shared helper has one copy, and
`test_suite_hygiene`'s duplicate gate requires it.

### §S4 — The gates this change moves

- **`AGENTS.md`:**
  - the module count, 81 → 82, at both places (lines 54 and 119 today);
  - the baselines, re-measured through the client;
  - the pi/node skip sentence ("seven in `test_pi_hook_runtime` and four in
    `test_pi_worktree_isolation`") gains the new module's count.
- **`tests/test_pi_hook_runtime.py`** imports the moved finder. Its skip tests still patch it where
  `_require_loader_env` looks it up. In both modules, the skip tests assert that the patched finder was
  called, so a wrong patch target fails.

### §S5 — After merge

The user redeploys (`modelb-axi --reinstall …`). Pi then loads all 14 of Model B's skills with no
diagnostics. This is the user's step, not an acceptance criterion.

## Acceptance criteria

- [ ] **`cr-authoring` and `model-b`** have one-line plain-scalar descriptions without `: `, carrying
      the words §S1 lists. Their existing gates pass.
- [ ] **`shutdown`'s description** is at most 1024 characters and carries every element §S2 lists. The
      existing shutdown gates pass.
- [ ] **The stdlib rule** passes on every file of §S3's set, and is proved on sample text in both
      directions for every case §S3.1 lists: the tab cases, the null/boolean/number forms, the
      continuation line and the UTF-16 count included.
- [ ] **The Pi loader check**, with Pi installed:
      - reports no diagnostics and exactly one loaded skill per `skills-src/*/SKILL.md`, named as its
        directory;
      - parses every rendered agent's frontmatter to string `name` and `description`;
      - catches the unparseable temp `SKILL.md` on every run;
      - leaves its temp `HOME` and agent dir empty;
      - fails on the pre-change tree (three diagnostics, 12 of 14 skills).

      It skips, naming the gap, when `node`, `pi`, Pi's package root or `dist/index.js` is absent, and
      fails, naming it, when an export is missing. Each case is proved by patching, as
      `test_pi_hook_runtime` does.
- [ ] **One finder:** `_find_pi_package_root` is defined once, in `tests/_helpers.py`, and both modules
      use it. Their skip tests assert the patched finder was called.
- [ ] **Gates that hold:**
      - `generator/build.py --check` is clean;
      - the full suite passes through the client with real `HOME` and with an empty `HOME`, and the temp
        home is empty afterwards;
      - `AGENTS.md`'s module count, baselines and pi/node skip sentence are re-measured.

## Non-goals

- Quoting in `modelb_axi.agents._emit_pi`. §S3.1 checks every rendered `name` and `description`, and
  §S3.2 (when Pi is installed) checks every other rendered key.
- Skills Model B does not author (`chrome-devtools-axi`, `find-skills`, `gh-axi`, `lavish`,
  `no-mistakes`, `vidushi-oa`).
- The imported bundles' `metadata` key (Pi ignores it).
- `references/*.md` and `archive/` frontmatter: Pi never parses them.
