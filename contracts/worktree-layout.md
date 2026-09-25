# Contract — worktree layout

**Owner:** Model B. **Status:** LIVE (CR-MDB-031 §S0.1, §S3).

This file declares the one path string at which a CR's git worktree lives. Nothing
enforces agreement between the consumers below mechanically except
`tests/test_worktree_layout_and_bundles.py`, which parses every consumer and fails when
one spells the worktree any other way.

## The string

A CR's worktree is `.worktrees/<cr>` — relative to the MAIN checkout's root, i.e. inside
the repository, one directory per CR id (`<cr>` = the CR id, e.g. `CR-MDB-031`). The
worktree's branch is `feature/<cr>[-<slug>]`.

- `scripts/worktree-flow.py start` creates it (`git worktree add -b feature/<cr>[-<slug>]`
  into that directory) and `finish`/`abort` remove it.
- The directory segment `/.worktrees/` is the ONLY worktree segment. A path under any
  other segment is not a Model B worktree: the write-boundary hook treats it as no
  worktree context and stays a no-op there.
- The repository's `.gitignore` lists `.worktrees/` (this repository's own, and the one
  `modelb-axi init` scaffolds), so a worktree never shows up as untracked content of the
  main checkout.

## Why inside the repository

A worktree placed inside the project directory inherits the project's context; a sibling
directory outside it would inherit none of it:

- **Project trust.** Pi resolves a directory's saved trust decision from the entry for
  that directory or its CLOSEST ancestor (`modelb_axi/project_trust.py` mirrors that
  resolution). A worktree inside a trusted project is therefore trusted too, so Pi loads
  the project's hook extension there — including the write-boundary hook — without a
  separate trust decision per worktree.
- **Permission scope.** The project's permission policy is scoped to the project
  directory; a worktree inside it falls under the same policy. After the orchestrator enters
  the worktree with `modelb_worktree_enter`, the agents it dispatches for the CR run rooted in
  it, with the project's permissions, not a foreign directory's.

## Consumers

Seven files carry the string; a change to it changes all seven in ONE commit (a worktree
mid-flight under the old string is stranded otherwise):

| Consumer | How it carries the string |
|---|---|
| `hooks-src/scripts/block-write-outside-worktree` | `_WORKTREES_SEGMENT = "/.worktrees/"` — derives the worktree root from the cwd and confirms it against `git worktree list` |
| `scripts/worktree-flow.py` | `WORKTREE_SUBDIR = ".worktrees"` — the directory `start` creates under the main checkout; its docstring's `start` usage line |
| `skills-src/bootstrap/SKILL.md` | a cwd under `/.worktrees/` means a Track inside a worktree |
| `skills-src/shutdown/SKILL.md` | the same role-detection rule at teardown |
| `skills-src/model-b/references/orchestration-track.md` | a Track asserts its toplevel ends in the declared worktree directory |
| `skills-src/model-b/references/sub-agent-procedure.md` | a dispatched sub-agent asserts its toplevel is its worktree, its only writable root |
| `pi-package/extensions/worktree.ts` | routes each dispatch naming a CR to its registered `.worktrees/<cr>`; `modelb_worktree_enter` accepts only such a registered worktree |

The scaffolded `.gitignore` line (`modelb_axi/scaffold.py`) follows the string but does not
spell the `<cr>` form, so it is not a parsed consumer.
