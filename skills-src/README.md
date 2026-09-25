# skills-src — authoring rule

Source tree for the skill bundles the installer deploys to `~/.agents/skills/` (each
subdirectory with a `SKILL.md`). This README is not a bundle and is never deployed.

**One rule governs the text of every bundle here (DN §D18, `docs/research/DN-multi-harness-deploy-model.md`):
a shared skill names capabilities and harness-neutral CLIs, never a harness's own tools.**

Write the capability ("record it in your task list", "ask the user", "read the file by its
explicit path"); where the exact invocation is load-bearing, name the
CLI with its flags (`sandesh send --project … --from … --to …`,
`~/.crucible/clients/<stack>-crucible.py <verb> --agent …`, `worktree-flow.py start`).

The rule is gated by CR-MDB-020 §S4's harness-tool ratchet in
`tests/test_client_path_anchoring.py` (`TOOL_BASELINE` is empty, so any harness tool name in
this tree fails it) and by CR-MDB-031's `tests/test_harness_neutral_skills.py`.
