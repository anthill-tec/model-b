# AGENTS

**For dispatched sub-agents only (RED / GREEN / VERIFY / FIX), any stack. Orchestrators read orchestration-*.** Stack-specific mechanics (exact test command, coverage tool, gotchas) live in the stack file + your agent definition.

## Worktree boundary (NON-NEGOTIABLE)
- **If spawned in a worktree, that worktree is your ONLY writable root.** A dispatch naming a CR runs rooted in that CR's worktree. Establish it FIRST: `git rev-parse --show-toplevel` from cwd — it MUST equal `…/.worktrees/<cr>/`, not the main tree. (Not spawned in a worktree — e.g. a non-Model-B project? This section does not apply; write normally.)
- **The main repo tree is READ-ONLY to you. You have NO permission to write anywhere outside your worktree** — not the repo root, not a parent, not a sibling worktree (a cross-worktree write corrupts another track's tree; a main-tree write leaks your CR onto develop).
- **Absolute paths are the usual leak — cwd discipline does NOT protect an absolute path.** Before EVERY write, confirm the target's absolute path resolves UNDER your worktree root; re-derive it from `git rev-parse --show-toplevel`, never from a remembered/guessed main-tree path. A typo (`.claire/`, wrong `<cr>`) or a stale absolute path is a cross-boundary write. `pwd` before any write; if a computed target falls outside your root, STOP.
- **NEVER "recover" a leak by copying files between trees** (`cp` / disk-copy / cross-root `git checkout` gymnastics) — that is itself a forbidden cross-boundary operation. If you wrote, or were about to write, outside your root: STOP and report to the orchestrator. Do not self-repair across trees.
- **This is HARD-ENFORCED while the orchestrator has entered the worktree** (`modelb_worktree_enter`): the `block-write-outside-worktree` hook blocks file-tool writes outside your worktree, for the orchestrator and for every agent it dispatches. It governs file-tool writes, not writes a shell command makes — the boundary still binds a shell command's writes, and only your discipline holds them. Also holding: your agent definition's `tools` allowlist, always; the hook runs when the project is trusted — a worktree inside the repo inherits the project's trust. If you hit that block, your path was wrong — fix it to stay inside the worktree; do NOT try to bypass it (no sandbox override, no shell workaround). The `ALLOW_WRITE_OUTSIDE_WORKTREE=1` escape hatch is for ORCHESTRATORS only — never a sub-agent.
- **Verify each edit landed on disk** (`git diff`, grep) — a cached read is advisory. On any inconsistency, STOP and report.
- Throwaway / scratch / probe code → `/tmp/…` (absolute), never the worktree or repo.

## Third-party sources
- Run `opensrc fetch` from a neutral cwd outside the repo, then verify the fetched source (no stray `.git` of our own origin).

## Crucible lifecycle — register FIRST, unregister LAST
- Register immediately on startup (before reading/running anything) with the `agentId` + `projectKey` from your prompt.
- Heartbeat ~every 2 min. Unregister as your LAST action. Skipping any leaves a ghost agent.
- Run tests + ingest through your stack's crucible script / `crucible-*` skill — never hand-roll raw `cargo`/`mvn`/`curl`.

## TDD — exact procedure, no shortcuts
1. Write ONLY the test (no production code, not even the target type).
2. Run → MUST fail (RED). Ingest the RED run. **A compile failure IS a RED** — ingest it as a compile error, never skip.
3. HARD STOP — Crucible must show a FAILING run before any passing run. Test+impl passing first try = TDD skipped = work worthless.
4. Only now write production code.
5. Run → GREEN. Ingest.
6. STOP — do NOT run the full suite (that's the orchestrator's regression gate).
- **Refactor (inverted TDD):** refactor → tests go RED → ingest → update tests → GREEN → ingest. Multiple cycles is normal; same ingest discipline.

## Report EVERY run
- RED and GREEN, every single one — no exceptions. An unreported RED reads as "skipped TDD."
- If stdout is truncated, read the report file (junit / lcov / surefire) — do NOT re-run.

## Scope discipline
- ONE class/module/file at a time; test after each; GREEN before moving on.
- Never big-bang across layers; never "migrate many, fix tests later"; never advance while tests fail.
- Test only YOUR dispatched SUT — don't author beyond your scope. Full-suite + coverage is orchestrator-owned.

## Code quality
- Remove ALL unused imports; import instead of fully-qualified inline names; rename an unused lambda/closure parameter to `_`.
- Key a guard's allowlist to an annotation marker at the site, never a line number — an unrelated edit shifts lines and re-breaks it.
- Clean build before commit; GREEN before commit — never commit in RED.
- Conventional commits (`type(scope): desc`); no AI attribution.
- No empty catch blocks, no unjustified suppressed warnings, no dead/commented-out code.
- Language-specific rules → your stack standards file.

## Consequences
Violations → work reverted (`git checkout -- .`), agent terminated, task re-spawned. Do it right, small, tested.
