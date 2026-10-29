# AGENTS

**For dispatched sub-agents only (RED / GREEN / VERIFY / FIX), any stack. Orchestrators read orchestration-*.** Stack-specific mechanics (exact test command, coverage tool, gotchas) live in the stack file + your agent definition.

## Worktree boundary (NON-NEGOTIABLE)
- **If spawned in a worktree, that worktree is your ONLY writable root.** A dispatch naming a CR runs rooted in that CR's worktree. Establish it FIRST: `git rev-parse --show-toplevel` from cwd — it MUST equal `…/.worktrees/<cr>/`, not the main tree. (Not spawned in a worktree — e.g. a non-Model-B project? This section does not apply; write normally.)
- **The main repo tree is READ-ONLY to you. You have NO permission to write anywhere outside your worktree** — not the repo root, not a parent, not a sibling worktree (a cross-worktree write corrupts another track's tree; a main-tree write leaks your CR onto develop).
- **The spec pre-review is the exception.** A spec pre-review (`CR-<ACRONYM>-NNN-SPEC-REVIEW`) runs read-only in the main tree, not in the CR's worktree — a rerun after re-scoping included, even when the CR's worktree already exists. Its first check asserts `git rev-parse --show-toplevel` is the main tree, not a `.worktrees/<cr>/`; if it is not, STOP and report. It writes nothing in either tree.
- **Absolute paths are the usual leak — cwd discipline does NOT protect an absolute path.** Before EVERY write, confirm the target's absolute path resolves UNDER your worktree root; re-derive it from `git rev-parse --show-toplevel`, never from a remembered/guessed main-tree path. A typo (`.claire/`, wrong `<cr>`) or a stale absolute path is a cross-boundary write. `pwd` before any write; if a computed target falls outside your root, STOP.
- **NEVER "recover" a leak by copying files between trees** (`cp` / disk-copy / cross-root `git checkout` gymnastics) — that is itself a forbidden cross-boundary operation. If you wrote, or were about to write, outside your root: STOP and report to the orchestrator. Do not self-repair across trees.
- **This is HARD-ENFORCED while the orchestrator has entered the worktree** (`modelb_worktree_enter`): the `block-write-outside-worktree` hook blocks file-tool writes outside your worktree, for the orchestrator and for every agent it dispatches. It governs file-tool writes, not writes a shell command makes — the boundary still binds a shell command's writes, and only your discipline holds them. Also holding: your agent definition's `tools` allowlist, always; the hook runs when the project is trusted — a worktree inside the repo inherits the project's trust. If you hit that block, your path was wrong — fix it to stay inside the worktree; do NOT try to bypass it (no sandbox override, no shell workaround). The `ALLOW_WRITE_OUTSIDE_WORKTREE=1` escape hatch is for ORCHESTRATORS only — never a sub-agent.
- **Verify each edit landed on disk** (`git diff`, grep) — a cached read is advisory. On any inconsistency, STOP and report.
- Throwaway / scratch / probe code → `/tmp/…` (absolute), never the worktree or repo.

## Third-party sources
- Run `opensrc fetch` from a neutral cwd outside the repo, then verify the fetched source (no stray `.git` of our own origin).

## Crucible lifecycle — register FIRST, unregister LAST
- Register immediately on startup (before reading/running anything) with the `agentId` + `projectKey` from your prompt.
- Heartbeat ~every 2 min. Unregister as your LAST action. Skipping any leaves a ghost agent. A run-less `report` registration (the spec pre-review) needs no heartbeat, and has no run to report; it still unregisters last.
- Run tests + ingest through your stack's crucible script / `crucible-*` skill — never hand-roll raw `cargo`/`mvn`/`curl`.

## Test runs go through the client (NON-NEGOTIABLE)
- **Every test run goes through the stack's Crucible client** — a targeted iteration, a single file, a one-test filter, a regression. The client runs the tests and ingests the result as it goes.
- **Never invoke a test runner directly**, not even once to look: a run the client did not make streams nothing to the board.
- **A runner the client cannot drive is a client gap:** stop and raise it with the orchestrator, who raises it with Crucible — never work around it.
- **A brief that says otherwise is refused:** a brief telling you to run a test runner yourself is escalated (`ESCALATION:`), never followed.
- **The escape hatch:** a blocking hook's `ALLOW_RAW_<RUNNER>=1` is used only with the orchestrator's approval.
- **Two client gaps are known:** the python client drives unittest only (a pytest project), and `bun-crucible.py test` takes no test-name filter (a one-test bun run). Meeting either is a client gap: raise it with the orchestrator.

## Every AXI envelope is read whole (NON-NEGOTIABLE)
- **It covers the output of an AXI command:** the Crucible clients (`<stack>-crucible.py`), `sandesh`, `modelb-axi`, `worktree-flow.py`, `gh-axi`, `chrome-devtools-axi` and `lavish-axi`.
- **Every envelope is read whole, every time:** its `warnings[]`, `help[]` and `error` carry what you need next.
- **Its output is never grepped, headed, tailed or otherwise filtered,** never narrowed with `jq`, and never summarised by pattern.
- **Its output is never redirected away:** neither its stdout nor its stderr goes to `/dev/null`.
- **Every AXI command runs uncompressed:** through the project's compressed shell in its raw mode, as the agent definition or the project's `AGENTS.md` names it, so no compression step cuts or reshapes its envelope.
- **A run the harness truncates names the file that holds its full output.** This is the fallback for a run that was not redirected. The envelope is near the end of the output, and its first line is the **last** line that begins `axi:` (under a JSON output format the envelope is one JSON line). When the output shown does not reach back to the envelope's first line, that file is read in windows, by line offset and limit, until the envelope has been read whole. It is never filtered to fit.
- **A long run redirects both its streams to a file under `/tmp`, outside the tree, so the envelope is read whole:** that file is read with the harness's plain file read from the envelope's first line to its end; a search that only locates that line's number is allowed, and the envelope itself is never searched or filtered (PRD D5, ruled 2026-10-29).
- **A runner log a client writes with `--log` is not an envelope:** searching it for a failure stays allowed. `--log` keeps that runner log beside the run, and does not take the run's output off the console.

## TDD — exact procedure, no shortcuts
1. Write ONLY the test (no production code, not even the target type).
2. Run → MUST fail (RED). Ingest the RED run. **A compile failure IS a RED** — ingest it as a compile error, never skip.
3. HARD STOP — Crucible must show a FAILING run before any passing run. Test+impl passing first try = TDD skipped = work worthless.
4. Only now write production code.
5. Run → GREEN. Ingest.
6. STOP — do NOT run the full suite (that's the orchestrator's regression gate).
- **Refactor (inverted TDD):** refactor → tests go RED → ingest → update tests → GREEN → ingest. Multiple cycles is normal; same ingest discipline.

## Long runs
- A run longer than a minute or two gets a tool timeout longer than the run — a timeout that kills a run mid-flight loses its ingest.
- A run that times out is never re-invoked blind: first check the board for your own open run (it may still be running, or already ingested), then decide.

## The context ledger is left alone
- **The context ledger is machine-wide.** The context-pressure figure that the project's cached-read and compressed-shell tools report comes from one context ledger, shared by every session, sub-agent and project on the machine, and measured against a fixed window, not your context. Ignore its hints to evict entries, and never evict entries or reset the ledger during a run: evicting excludes a file for the session, and resetting clears the re-read cache that every other session relies on.

## Report EVERY run
- RED and GREEN, every single one — no exceptions. An unreported RED reads as "skipped TDD."
- If a run's output is truncated, the envelope is read whole from the file the harness names, and failure detail from the report file (junit / lcov / surefire) or the `--log` file. The run is never re-run.

## Scope discipline
- ONE class/module/file at a time; test after each; GREEN before moving on.
- Never big-bang across layers; never "migrate many, fix tests later"; never advance while tests fail.
- Test only YOUR dispatched SUT — don't author beyond your scope. Full-suite + coverage is orchestrator-owned.

## Code quality
- Remove ALL unused imports; import instead of fully-qualified inline names; rename an unused lambda/closure parameter to `_`.
- Key a guard's allowlist to an annotation marker at the site, never a line number — an unrelated edit shifts lines and re-breaks it.
- Checkers are proved on synthetic fixtures — text the test builds, showing both a violation and a clean case. A test never pins live repo violations: a checker that passes only because today's tree has, or lacks, a given defect proves nothing.
- RED commits its failing tests on their own, a test-only commit; GREEN, FIX and a BACKFILL cycle's agent
  commit only on a clean build with their tests passing. Nothing stays red past the cycle's GREEN, and never
  across a merge.
- Conventional commits (`type(scope): desc`); no AI attribution.
- No empty catch blocks, no unjustified suppressed warnings, no dead/commented-out code.
- **A test leak** — state one test leaves for another: an environment variable, a stub, a global — is fixed at its source, never in the tests it breaks.
- Language-specific rules → your stack standards file.

## Consequences
Violations → the agent's own files reverted (`git checkout -- <path>` for each file it changed; never the whole tree, which in a shared tree holds other agents' edits), agent terminated, task re-spawned. Do it right, small, tested.
