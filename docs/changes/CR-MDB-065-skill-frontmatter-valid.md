# CR-MDB-065 — Skill frontmatter parses, and stays within Pi's limits

**Status:** PENDING (filed 2026-10-13; gap analysis 2026-10-13)
**Type:** fix (skill metadata, guard test)
**Priority:** P1 — release 1.0.0, wave 2.
**Depends on:** CR-MDB-056 (merged; board-authoritative: read `queue`)
**Labels:** skills, frontmatter, pi, guard
**Design reference:** Pi's skill loader (`@earendil-works/pi-coding-agent` 1.2.0, `dist/core/skills.js`);
pi-subagents' agent loader (`src/config/custom-agents.ts`); DN-multi-harness-deploy-model §D18 (skills
are the shared surface).

## Context

Pi reported three of Model B's deployed skills as conflicts (2026-10-13). The deployed copies equal
`skills-src/`, so the defects are in the source. Measured with Pi 1.2.0's own exported loader
(`loadSkillsFromDir` over `skills-src/`), which loads 12 skills and emits exactly three diagnostics:

| Skill | Diagnostic | Effect in Pi |
|---|---|---|
| `cr-authoring` | "Nested mappings are not allowed in compact mappings at line 2, column 14" | **not loaded** — a parse failure drops the skill |
| `model-b` | the same | **not loaded** |
| `shutdown` | "description exceeds 1024 characters (1206)" | loaded, with a warning |

Both parse failures come from an unquoted YAML plain scalar containing `: ` (`… Triggers: CR, PRD …`).

**Pi's rules, read from its loader:**
- Frontmatter is parsed with the npm `yaml` package (2.9.0); a throw on a `SKILL.md` is a warning and
  the skill is not loaded.
- `description` must be a non-empty string; longer than 1024 characters (`MAX_DESCRIPTION_LENGTH`) is a
  warning.
- `name` is at most 64 characters (`MAX_NAME_LENGTH`), matches `^[a-z0-9-]+$`, does not start or end with
  `-` and has no `--`; when absent, the directory name is used. Name errors are warnings.
- Other keys are ignored except `disable-model-invocation` (the imported bundles' `metadata` key is
  harmless).

**Agents are exposed to the same parser.** pi-subagents reads each agent file with Pi's exported
`parseFrontmatter`, with no `try` around it, so a frontmatter that does not parse can stop the agents
of its directory from loading. Model B renders agent frontmatter in `modelb_axi.agents._emit_pi`
(`description: {defn['description']}`, unquoted, from `generator/stacks/*.toml` `[description]`).
All 20 `generator/agents/*.md` and the 4 `.pi/agents/*.md` parse today; `generator/agents/` is the
full render of every stack and role, so a guard over it covers every frontmatter the emitter produces.

**Baseline** (2026-10-13 21:22, `develop` `f2bd3c2`, through the client): real `HOME` 2285 tests OK,
1 skip (`PI_CODING_AGENT_DIR` sandboxed); empty `HOME` 2285 OK, 12 skips, the temp home empty after.

## Scope

### §S1 — The two descriptions parse

`cr-authoring`'s and `model-b`'s `description` stay one-line plain scalars, reworded so they contain
no `: ` (for example "Triggers: a, b" becomes "Use for a, b"). They keep the words the existing gates
read: `cr-authoring` "CR" and "PRD" (`tests/test_cr_authoring_skill.py`); `model-b` "orchestration",
"sub-agent" (`tests/test_model_b_skill.py`, `tests/test_core_split.py`) and "board"
(`tests/test_board_holds_the_queue.py` `test_description_names_the_board`).

### §S2 — `shutdown`'s description is at most 1024 characters

The description keeps what decides loading: the trigger phrases ("/shutdown", "shut down", "stand
down", "end of day, close out", "wind down the orchestrators", a Track receiving a shutdown directive
from Mainline); that it brings ONE orchestrator down cleanly and stops its own wake watcher last;
graceful by default with the `emergency` flag; and the sign-off (`test_shutdowns_description_names_
the_sign_off`). Detail it drops (the Mainline-after-every-Track ordering, the no-role-argument
reasoning) is already stated in the body, and stays there. No todo or task-list wording
(`test_frontmatter_descriptions_name_no_todo_or_task_list`).

### §S3 — The guard

A new test module. Its file set is every `skills-src/*/SKILL.md`, `generator/agents/*.md` and
`.pi/agents/*.md`.

1. **The stdlib rule, always run.** Each file has a well-formed `---` frontmatter with exactly one
   top-level `name:` line and one `description:` line. Each value is a one-line plain scalar that YAML
   can only read as one string: non-empty; not starting with a YAML indicator (`- ? : , [ ] { } # & * !
   | > ' " % @` or a backtick); containing no `: ` and no ` #`; not ending with `:`. A quoted or block
   scalar is refused (the message says to reword). `description` is at most 1024 characters. A
   skill's `name` follows Pi's rules (at most 64 characters, `^[a-z0-9-]+$`, no leading or trailing
   `-`, no `--`) and equals its directory name. The rule is proved on sample text both ways: each
   indicator, `: `, ` #`, a trailing `:`, a quoted value, a 1025-character description and each
   name-rule breach are caught; a clean value and a 1024-character description pass.
2. **Pi's own loader, when it is installed.** The test finds Pi's package root from the resolved `pi`
   binary and runs `node` on Pi's exported API (`dist/index.js`):
   - `loadSkillsFromDir` over `skills-src/` returns **no diagnostics** and loads exactly one skill per
     `skills-src/*/SKILL.md`, named as its directory;
   - `parseFrontmatter` on each `generator/agents/*.md` and `.pi/agents/*.md` does not throw, and
     returns string `name` and `description`.

   Without `node`, `pi` or Pi's package root, it skips, naming what is missing. The package-root finder
   is the one `tests/test_pi_hook_runtime.py` already has (`_find_pi_package_root`); it moves to
   `tests/_helpers.py` and both modules import it (one copy of a shared helper).

### §S4 — The gates this change moves

`AGENTS.md`: the module count (81 → 82) in both places, the baselines re-measured through the client,
and the skip list re-stated if the oracle adds a skip (for example under an empty `HOME`).
`tests/test_pi_hook_runtime.py` imports the moved finder, and its skip tests still patch it where
`_require_loader_env` looks it up.

### §S5 — After merge

The user redeploys (`modelb-axi --reinstall …`). Pi then loads all 14 of Model B's skills with no
diagnostics. This is the user's step, not an acceptance criterion.

## Acceptance criteria

- [ ] **`cr-authoring` and `model-b`** have one-line plain-scalar descriptions without `: `, carrying
      the words §S1 lists; their existing gates pass.
- [ ] **`shutdown`'s description** is at most 1024 characters and carries every element §S2 lists;
      the existing shutdown gates pass.
- [ ] **The stdlib rule** passes on every file of §S3's set and is proved on sample text both ways for
      every case §S3.1 lists.
- [ ] **The Pi loader check**, with Pi installed, reports no diagnostics and exactly one loaded skill
      per `skills-src/*/SKILL.md` named as its directory, and parses every rendered agent's frontmatter
      to string `name` and `description`; it fails on the pre-change tree (three diagnostics, 12 of 14
      skills) and skips, naming the gap, when `node`, `pi` or Pi's package root is absent (proved by
      patching, as `test_pi_hook_runtime` does).
- [ ] **One finder:** `_find_pi_package_root` is defined once, in `tests/_helpers.py`, and both modules
      use it.
- [ ] **Gates that hold:** `generator/build.py --check` clean; the full suite through the client with
      real `HOME` and with an empty `HOME` (the temp home empty afterwards); `AGENTS.md`'s module count,
      baselines and skip list re-measured.

## Non-goals

- Quoting in `modelb_axi.agents._emit_pi`: the guard over the full render catches any stack
  description that would not parse.
- Skills Model B does not author (`chrome-devtools-axi`, `find-skills`, `gh-axi`, `lavish`,
  `no-mistakes`, `vidushi-oa`).
- The imported bundles' `metadata` key (Pi ignores it).
- `archive/` frontmatter.
