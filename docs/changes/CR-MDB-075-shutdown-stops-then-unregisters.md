# CR-MDB-075 — A shutdown stops the watcher, then unregisters: never together

**Status:** PENDING — spec (gap analysis 2026-10-16).
**Type:** fix (skills, references)
**Priority:** P1 — release 1.0.0, wave 2; next in the queue.
**Depends on:** none (board-authoritative: read `queue`)
**Labels:** skills, shutdown, sandesh
**Design reference:** PRD D5 (AMENDED 2026-10-16: the shutdown's last two acts are sequential);
Sandesh #1464.

## Context

- **What happened.** On 2026-10-16 a Mainline shutdown issued the watcher stop and the
  unregister as one parallel batch of tool calls. Neither returned, and the session had to be
  force-quit.
- **What was left behind.** The watcher was gone, but the address stayed `active`: the unregister
  ran while the dying watcher still counted as live.
- **Root cause.** Not proven. It is reported to the Sandesh project (#1464).
- **What the shipped text says.** The shutdown skill says "stop your own watcher, then
  unregister", but does not forbid issuing the two together. Neither does it say to confirm the
  stop first.
- **Where it is stated:**
  - `skills-src/shutdown/SKILL.md`: the introduction, Step 2A's graceful step 5 and emergency
    step 4, Step 2B's step 5, § The common final step, and the guardrails;
  - `orchestration-common.md`'s session-lifecycle bullet;
  - `orchestration-track.md`'s shutdown bullets.
- **Where projects get it.** The installer deploys `skills-src/shutdown/` to every installation.
  `init` renders no copy of it into a project.

## Scope

### §S1 — The common final step is three steps, in order

`skills-src/shutdown/SKILL.md` § The common final step:

1. Stop your own watcher, by your own address, through Sandesh's extension.
2. Confirm with `sandesh addressbook --project <Project> --format toon --fields address,status,listening`
   that your address no longer shows `listening` true. If it still does, stop it once more and
   check again. Never unregister an address that is still listening.
3. Only then `sandesh unregister --project <Project> --address "<your address>" --as "<your address>"`,
   and confirm the address no longer shows `status` `active`.

**The two are separate calls, one after the other.** Each waits for the previous one's result. They
are never issued together, neither as tool calls in one parallel batch nor in one shell command.

**An unregister that does not return,** or leaves the address `active`, is reported to the user
with the address's state. The next `/bootstrap` finds the address active and skips registering
it.

### §S2 — Every place the skill names the final step

- **The same order everywhere.** The introduction, Step 2A (graceful step 5 and emergency step 4),
  Step 2B step 5 and the "Stop ONLY your own watcher" guardrail all say: stop, confirm, then
  unregister, never together.
- **Pointing at the full form.** Each points to § The common final step for it.
- **Unchanged:** the frontmatter description.

### §S3 — The references

- **`orchestration-common.md`'s session-lifecycle bullet** ("Stopping the watcher at shutdown is
  the SINGLE exception…") says the unregister follows a confirmed stop and is never issued with
  it.
- **`orchestration-track.md`'s graceful and emergency shutdown bullets** say the same.

## Acceptance criteria

- [ ] **§S1.** Gates pin, in § The common final step:
      - the three numbered steps, in order (stop, confirm not listening, unregister);
      - the retry-once and never-unregister-while-listening rule;
      - the separate-calls rule naming both a parallel batch and one command;
      - the unregister-that-does-not-return report.
- [ ] **§S2.** A gate pins each of the five named places: the stop-confirm-unregister order and its
      never-together wording.
- [ ] **§S3.** Gates pin both reference bullets.
- [ ] **Every gate** is proved both ways.
- [ ] **A negative gate** fails on any unit in the three files that tells the reader to stop the
      watcher and unregister in the same step without the never-together wording.
- [ ] **Runs.**
      - The suite is green through the client, with a real `HOME` and an empty one.
      - The skills load in Pi with no diagnostics.
      - The shutdown skill's frontmatter is unchanged.
      - `generator/build.py --check` is clean.
      - The `AGENTS.md` counts and baselines match.

## Non-goals

- **The cause of the hang.** It belongs to Sandesh (#1464). A Sandesh remedy that changes the
  order a consumer needs comes back as its own CR.
- **The bootstrap skill.** It already finds an address left active and skips registering it.

## Cycle plan

1. **The rule (§S1–§S3).** Red-green.
2. **Verify.**
