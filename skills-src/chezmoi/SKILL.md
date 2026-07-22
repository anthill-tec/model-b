---
name: chezmoi
description: Chezmoi discipline for the ~/.claude dotfiles tree — add/diff/apply cycle, the delete/rename procedure (destroy, never plain rm), the non-TTY agent-session no-auto workaround, multi-account source-repo pushing, drift reconciliation, and the diff-on-directory quirk. Use for chezmoi, dotfiles, deleting a managed file, or any ~/.claude edit.
---

# Chezmoi — Managed-Dotfiles Discipline

`~/.claude` (AGENTS.md/CLAUDE.md, `agents/`, `memory/`, `skills/`, settings) plus shell/SSH config are chezmoi-managed with git version control (source repo: `~/.local/share/chezmoi`). Every mutation of a managed path MUST go through the procedures below.

**Triggers:** chezmoi · dotfiles · deleting/renaming a managed file · any `~/.claude` edit.

## The add / diff / apply cycle

The live file is edited first; chezmoi's source is then synchronized FROM the live tree:

```bash
# 1. Edit the live file normally
$EDITOR ~/.claude/skills/<skill>/SKILL.md

# 2. Sync the source state from the live file (agent sessions: use the no-auto config — see below)
chezmoi add ~/.claude/skills/<skill>/SKILL.md    # or: chezmoi add -r <dir> for a directory

# 3. Review — source vs live must converge to empty
chezmoi diff ~/.claude/skills/<skill>/SKILL.md

# 4. Commit the source repo (agent sessions: manually — see below)
git -C ~/.local/share/chezmoi add -A && git -C ~/.local/share/chezmoi commit -m "<type>(<scope>): <desc>"
```

`chezmoi apply` copies source → live (restore direction). `chezmoi managed` lists managed paths; `chezmoi verify` checks convergence.

## DELETE / RENAME procedure (the resurrection hazard)

**A plain `rm` of a managed file does NOT delete it — the file will resurrect on the next `chezmoi apply`** because the source copy still exists. Proven on this machine (Model B `archive/BASELINE.md`, Wave 0 delete round-trip, 2026-07-20): scratch file → `chezmoi add` → `chezmoi destroy --force` → gone from disk AND source, unmanaged, and a subsequent `apply --dry-run --verbose` mentions it zero times. Deletions performed via `chezmoi destroy` do NOT resurrect.

- **Delete a managed file (disk + source together):**
  ```bash
  chezmoi destroy --force <path>
  ```
- **Alternative (stop managing, then remove the live file):**
  ```bash
  chezmoi forget <path> && rm <path>
  ```
- **Rename a managed file:** create/`chezmoi add` the new path, then `chezmoi destroy --force` the old path. Never just `mv`.
- **Delete an UNMANAGED file:** plain `rm` is fine — `destroy` on an unmanaged path errors.
- After any deletion, commit the source repo (it now holds the removal).

## Non-TTY agent sessions — the REQUIRED no-auto workaround (VERBATIM)

`~/.config/chezmoi/chezmoi.toml` sets `git.autoCommit = true`, `autoPush = true`, and `commitMessageTemplate = promptString` — the interactive prompt fails in non-TTY agent sessions (`could not open a new TTY`). Workaround used and REQUIRED for all agent-session mutations:

1. `sed 's/autoCommit = true/autoCommit = false/; s/autoPush = true/autoPush = false/' ~/.config/chezmoi/chezmoi.toml > /tmp/claude-1000/chezmoi-noauto.toml`
2. Run mutating ops as `chezmoi --config /tmp/claude-1000/chezmoi-noauto.toml <add|destroy|forget> ...`
3. Commit the source manually: `git -C ~/.local/share/chezmoi add -A && git -C ~/.local/share/chezmoi commit -m "<type>(<scope>): <desc>"` (conventional commit, no AI attribution)
4. Pushing the source repo stays a USER action — **never push** (and never auto-push) from an agent session.

Hard rules for agent sessions:
- **NEVER run a bare mutating `chezmoi` command** (`add`/`destroy`/`forget` without the no-auto `--config`) — autoCommit's TTY prompt will fail mid-mutation and can leave the source dirty.
- **NEVER blind `chezmoi apply`** — apply overwrites the live tree from source; combined with source-ahead drift it clobbers live edits (and resurrects rm'd files).
- Read-only chezmoi commands (`diff`, `managed`, `verify`, `apply --dry-run`) are safe without the temp config.

## Multi-account: the source repo push is a USER action

The chezmoi source repo is on the PERSONAL GitHub account (`antojk`), while work sessions usually run as the work account (`Antojk71`) — pushing requires `gh auth switch --user antojk`, pushing, then `gh auth switch --user Antojk71` back. That account dance is why agent sessions **never push** the chezmoi source repo: commit locally, leave the push to the user. (General dual-remote push discipline: `git-workflow` skill.)

## Source-ahead drift — reconcile deliberately, never blind apply

If `chezmoi diff` / `chezmoi verify` shows drift, determine WHICH side is newer before acting:

- **Live ahead** (you edited `~/.claude` but didn't `chezmoi add`): `chezmoi add` the path, commit the source.
- **Source ahead** (source repo has commits — e.g. pulled from another machine — not yet applied): review with `chezmoi diff` and apply ONLY the intended scoped paths. A blind whole-tree `chezmoi apply` overwrites live edits and resurrects deleted files.
- When in doubt: `chezmoi apply --dry-run --verbose <path>` first, and reconcile path by path.

## The `diff <dir>` silent-empty quirk

`chezmoi diff <dir>` on a DIRECTORY argument can print nothing (silently empty) even when files UNDER that directory drifted — it does not reliably recurse. Do not treat an empty `diff <dir>` as proof of convergence:

- For recursion, use a scoped dry-run apply instead: `chezmoi apply --dry-run --verbose <dir>` (lists every file it would change).
- Or diff explicit file paths, or run a full `chezmoi diff` and filter.
- A scoped multi-path `chezmoi diff <p1> <p2> ...` exiting 0 with empty output on FILE paths is a valid convergence check; for directories, back it with the dry-run apply.

## Quick reference

| Task | Command (agent session) |
|------|-------------------------|
| Sync live edit into source | `chezmoi --config /tmp/claude-1000/chezmoi-noauto.toml add <path>` |
| Delete managed file | `chezmoi --config /tmp/claude-1000/chezmoi-noauto.toml destroy --force <path>` |
| Stop managing (keep live) | `chezmoi --config /tmp/claude-1000/chezmoi-noauto.toml forget <path>` |
| Check drift (files) | `chezmoi diff <path>...` (empty + exit 0 = converged) |
| Check drift (directory) | `chezmoi apply --dry-run --verbose <dir>` |
| Commit source | `git -C ~/.local/share/chezmoi add -A && git -C ~/.local/share/chezmoi commit -m "..."` |
| Push source | USER action only — never push from an agent session |
