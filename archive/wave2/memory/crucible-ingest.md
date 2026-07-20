# Crucible — Test Ingestion & Agent Lifecycle

Crucible is the local test runner dashboard at `http://localhost:3849`.

The Crucible lifecycle (register → ingest-after-EVERY-run → unregister) is driven by the
stack crucible script + the `crucible-*` skill — **NEVER hand-roll curl/python.**
Routing: compile-fail → `/compile`; ran → `/ingest` (junit); coverage published ONLY on a
full-green run. Authoritative procedure: `~/.claude/skills/model-b/references/sub-agent-procedure.md` §Crucible lifecycle + the stack
orchestration file (`rust-orchestration.md` / `java-orchestration.md`).
