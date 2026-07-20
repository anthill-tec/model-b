# Wave 0 baseline — 2026-07-20

## Chezmoi source baseline
- Source repo: `~/.local/share/chezmoi`, HEAD at baseline: `cab102932cece324b7807d8e34d6f8afcf90fbac` (clean tree).
- Proof commits added during Wave 0 (local only, NOT pushed): `test(wave0): add scratch delete-proof file`, `test(wave0): destroy scratch delete-proof file`.

## Delete round-trip proof (PASSED)
Scratch file `~/.claude/wave0-scratch-proof.md`: `chezmoi add` → managed; `chezmoi destroy --force` → file gone from disk AND source, unmanaged; `chezmoi apply --dry-run --verbose` mentions it zero times; file stays absent. **Conclusion: deletions performed via `chezmoi destroy` do NOT resurrect on `apply`. All wave deletions must use `chezmoi destroy` (or `forget` + rm).**

## Operational gotcha (record in the chezmoi skill, Wave 2)
`~/.config/chezmoi/chezmoi.toml` sets `git.autoCommit = true`, `autoPush = true`, and `commitMessageTemplate = promptString` — the interactive prompt fails in non-TTY agent sessions (`could not open a new TTY`). Workaround used and REQUIRED for all waves:
1. `sed 's/autoCommit = true/autoCommit = false/; s/autoPush = true/autoPush = false/' ~/.config/chezmoi/chezmoi.toml > /tmp/claude-1000/chezmoi-noauto.toml`
2. Run mutating ops as `chezmoi --config /tmp/claude-1000/chezmoi-noauto.toml <add|destroy|forget> ...`
3. Commit the source manually: `git -C ~/.local/share/chezmoi add -A && git -C ~/.local/share/chezmoi commit -m "<type>(<scope>): <desc>"`
4. Pushing the source repo stays a USER action (multi-account `gh auth switch` involved) — never auto-push from an agent session.

## ~/.claude inventory at baseline
24 memory files · ~50 skills · 29 agents · ~20 scripts · AGENTS.md 621 lines (CLAUDE.md symlink). Audit snapshots: `audits/2026-07-20-*.md`.
