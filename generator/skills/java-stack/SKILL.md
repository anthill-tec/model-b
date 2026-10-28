---
name: java-stack
description: Java/Quarkus reference material for a project's RED, GREEN, VERIFY and FIX agents — the coding standards, testing practices, modern Java syntax, Maven and Quarkus patterns, plus the debugging, DevServices, native-build and client-flag rules. Use when a task needs a Java convention, a Quarkus or Maven pattern, a test that hangs or fails in an unexpected layer, a native or e2e cycle, or a client flag beyond a targeted run.
---

# Java stack

Reference material a quarkus or java agent loads when its task needs it. The agent definition
states what every phase needs; this skill holds what only some tasks need.

## References — read the one your task needs

| Topic | Read |
|---|---|
| Imports, naming, error handling, DTO records, MongoDB entity annotations | `references/coding-standards.md` |
| TDD layering, Quarkus test patterns, DevServices, JaCoCo, E2E kinds, the reviewer checklist | `references/testing-practices.md` |
| Records, sealed types, pattern matching, virtual threads (JDK 8-25) | `references/modern-syntax.md` |
| The Maven build lifecycle, plugins, dependency and release management | `references/maven.md` |
| Quarkus configuration, reactive and SSE patterns, Redis, the failsafe plugin; the health, metrics, OpenAPI and container-image build commands, the schema registry's and RediSearch's commands | `references/quarkus-patterns.md` |
| The orchestrator's Maven and Crucible mechanics: the client's verbs, the pre-merge gate, JaCoCo, planning the layers, disk hygiene | `references/orchestration.md` |

## Test-First Problem Isolation

Before touching code that has passing tests, run those tests first. When an endpoint fails while
its service-layer tests pass, the fault is in the resource, path mapping, serialization, DI or HTTP
layer — not the service logic. Never comment out working code or add speculative changes to "see"
an error. Detail: `references/testing-practices.md`, "Debugging Principles".

## A hanging test is not cured by disabling DevServices globally

A hang during class loading is the DevServices/TestContainers conflict; isolate the test resource
per class. Turning DevServices off for the whole build hides the conflict and removes the
infrastructure the integration tests need.

## Removing a method

Check both its unit tests AND integration tests before and after: a green surefire run says
nothing about the failsafe `*IT` classes that still call it.

## Native (GraalVM) builds

Native builds are RAM-heavy and slow. Run them at the gate or in CI, not every cycle — JVM e2e for
the cycles, native last: `e2e --native` through the client, one step that runs `clean verify -Dnative`,
building the native package and running failsafe against it. `e2e --native --failsafe-only` runs
only the two failsafe goals against a native package already built, so it follows a build of the
native package and never replaces one. Budget the time and watch memory, not disk.

## Before a native or JVM e2e cycle

Check docker is clean first: a stale container from an earlier run poisons the suite. The client's
`e2e` verb performs a `docker ps` clean-check; read its verdict before trusting the result.

## The client's task-specific flags

`mvn-crucible.py` takes these beyond a targeted run, each mapped to its Maven switch:

- `unit --test <Class>#<method>` — one test method instead of the whole class.
- `--module <m> --also-make` — one reactor module and the modules it depends on (`-pl` / `-am`).
- `--native` — the native profile (`-Dnative`), for e2e cycles.
- `--profile <P>` — a Maven profile (`-P`).
- `--system-prop <k>=<v>` — a system property (`-D<k>=<v>`).
- `--update-snapshots` — force a snapshot refresh (`-U`).
- `--coverage-profile` — the profile that turns JaCoCo on.

A monorepo whose Maven project sits in a sub-directory names it with `--maven-dir`, or once in the
project's `.env` as `CRUCIBLE_MAVEN_DIR`.
