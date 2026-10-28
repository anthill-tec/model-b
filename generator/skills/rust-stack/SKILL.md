---
name: rust-stack
description: Rust/Cargo reference material for a project's RED, GREEN, VERIFY and FIX agents — the flaky-test investigation principle, and the e2e, docker and nextest-concurrency gotchas. Use when a test fails only under timing or parallel load, or before work that touches a docker-compose file or adds an e2e test binary.
---

# Rust stack

Reference material a rust agent loads when its task needs it. The agent definition states what
every phase needs; this skill holds what only some tasks need.

## Flaky-test investigation principle (timing/parallel-load failures)

Logical sequence + data integrity preserved = OK to serialize; otherwise fix the root cause. Ask whether the failure means (a) the SYSTEM produces wrong results (data lost/reordered/duplicated/corrupted, invalid state transitions) → real bug, fix the code; or (b) the TEST asserts wall-clock timing for its own sake while the system still completes correctly with eventual consistency → flawed test: rewrite to assert semantic correctness (data integrity, ordering), or — only if the timing observation is genuinely the sole detection path — accept a `#[serial]` / nextest serial-group with explicit justification naming the preserved invariant. `#[serial]` without root-cause investigation accrues debt.

## E2E / docker / nextest-concurrency gotchas

Read `references/e2e-docker-nextest.md` before any task touching `deploy/docker-compose.*` or
adding a `tests/e2e_*.rs` binary, or a docker-dependent test.
