# CR-MDB-075 — A shutdown stops the watcher, then unregisters: never together

**Status:** PENDING — spec (gap analysis and pre-review 2026-10-16).
**Type:** fix (skills, references)
**Priority:** P1 — release 1.0.0, wave 2; next in the queue.
**Depends on:** none (board-authoritative: read `queue`)
**Labels:** skills, shutdown, sandesh
**Design reference:** PRD D5 (AMENDED 2026-10-16: the shutdown's last two acts are sequential);
Sandesh #1464.

## Context

- **What happened.** On 2026-10-16 a Mainline shutdown issued the watcher stop and the unregister
  as one parallel batch of tool calls. Neither returned, and the session had to be force-quit. The
  root cause is not proven; it is reported to the Sandesh project (#1464).
- **What was left.** The watcher was gone, but the address stayed `active`. The unregister ran while
  the dying watcher still counted as live, so Sandesh only set a tombstone.
- **How liveness works** (sandesh 0.4.2, sandesh-pi 0.4.2):
  - A stop marks the watcher stopped and aborts it; Pi sends SIGTERM, then SIGKILL 5 s later. On
    exit, the watcher deletes its liveness row.
  - An address counts as listening while that row exists with a heartbeat younger than 60 s and a
    live pid. That is normally gone within milliseconds of the stop.
  - A second stop from the same session does nothing (`stopped: 0`). Anything still listening after
    the first stop is a watcher this session does not own.
- **What `unregister` does with a live watcher.** It answers "tombstone set … re-run once
  `addressbook` shows it offline" (exit 3) and leaves the address `active`.
- **What the shipped text says.** The shutdown skill says "stop your own watcher, then unregister"
  but forbids neither issuing them together nor unregistering before the stop is confirmed. It
  says so in these places:
  - **`skills-src/shutdown/SKILL.md`:**
    - the introduction;
    - Step 2A's graceful step 5 and emergency step 4;
    - Step 2B's step 5 and its Emergency (Mainline) paragraph;
    - § The common final step;
    - the "Stop ONLY your own watcher" guardrail.
  - **`orchestration-common.md`:** its session-bracket bullet ("…stop your own watcher LAST and
    unregister your address") and its "Stopping the watcher at shutdown is the SINGLE exception"
    bullet.
  - **`orchestration-track.md`:** its graceful and emergency shutdown bullets.
- **Where projects get it.** The installer deploys `skills-src/shutdown/` to every installation.
  `init` renders no copy of it into a project.

## Scope

### §S1 — The common final step is three steps, in order

The heading becomes "## The common final step — stop, confirm, then unregister". Its section keeps
its *Why last*, *documented exception*, *never a machine-wide kill* and *Shutdown stops; bootstrap
revives* text, and reads:

1. **Stop your own watcher, by your own address,** through Sandesh's extension — or with its command,
   `/sandesh-watcher stop <your address>`.
2. **Confirm with `sandesh addressbook --project <Project> --format toon --fields address,status,listening`**
   that your address no longer shows `listening` true.
   - If it still does, read it again after a few seconds, a bounded number of times, for no longer
     than about a minute (Sandesh's heartbeat staleness): at most 6 re-reads, each its own call (a
     short `sleep`, then one addressbook read). Never a shell loop, open-ended or bounded.
   - If it is still listening after that, a watcher this session does not own holds the address.
     Check `/sandesh-watcher status`, report the address's state to the user, and do not unregister.
3. **Only then run `sandesh unregister --project <Project> --address "<your address>" --as "<your address>"`,**
   with a 30-second time bound (for example `timeout 30`, or the tool's own timeout), and confirm the
   address now shows `status` inactive.
   - An unregister that answers with a tombstone (exit 3) has not unregistered: a watcher was still
     live. Go back to step 2 once, and run it again once the address reads offline. A second
     tombstone is reported to the user, never retried again.
   - An unregister that has not returned within its time bound, or that leaves the address `active`,
     is reported to the user with the address's state. The next `/bootstrap` finds the address
     active and skips registering it.

**The two are separate calls, one after the other.** Each waits for the previous one's result. They
are never issued together: not as tool calls in one parallel batch, and not in one shell command
(the latter guards against a future `sandesh` stop verb).

### §S2 — Every place the skill names the final step

These six places each state the order — stop, confirm, then unregister, never together — and point
to § The common final step for the full form:

1. the introduction;
2. Step 2A graceful step 5;
3. Step 2A emergency step 4;
4. Step 2B step 5;
5. the **Emergency (Mainline)** paragraph, which today ends at "stop the watcher" with no unregister;
6. the "Stop ONLY your own watcher" guardrail.

Places that name only the stop and no unregister are left alone: the mode bullets, Step 1A, Step 1B
and the Solo guardrail. The frontmatter description is unchanged.

### §S3 — The references

These three reference bullets say that the unregister follows a confirmed stop and is never issued
with it:

- `orchestration-common.md`'s session-bracket bullet;
- `orchestration-common.md`'s "Stopping the watcher at shutdown is the SINGLE exception" bullet;
- `orchestration-track.md`'s graceful and emergency shutdown bullets.

## Acceptance criteria

- [ ] **§S1.** Gates pin, in § The common final step:
      - the retitled heading, still carrying "final step";
      - the three numbered steps, in order;
      - the slash-command form of the stop;
      - the bounded re-read (about a minute, at most 6 re-reads, each its own call, never a shell
        loop);
      - "report, never unregister" when the address stays listening;
      - the tombstone (exit 3) path back to step 2, once, and the report on a second tombstone;
      - the 30-second time-bounded unregister, and the report when it doesn't return or leaves the
        address active;
      - the `status` inactive check;
      - the separate-calls rule, naming both a parallel batch and one shell command.

      The section's existing gates stay green: `/sandesh-watcher stop <your address>` before
      `sandesh unregister --project <Project>`, "Sandesh's extension", "documented exception",
      "only when everything else … done", and no `sandesh_*` tool name.
- [ ] **§S2.** A gate pins each of the six places: the order, the never-together wording, and the
      pointer to § The common final step.
- [ ] **§S3.** Gates pin, in each of the three bullets, "unregister follows a confirmed stop" and
      "never issued with it".
- [ ] **The negative gate.**
      - **Unit:** one Markdown heading line, one bullet with its continuation lines, one numbered
        step, or one paragraph.
      - **Violation:** a unit in the three files that matches `\bstop\w*[^.;]{0,60}\bwatcher` (or the
        reverse order) and also `\bunregister`, but carries none of the never-together phrases:
        `never issued together`, `never together`, `never issued with it`, `only then`,
        `confirmed stop`, or a `confirm` that comes after the stop in the same unit (a bare
        `confirm` elsewhere in the unit does not spare it).
      - A numbered step is one unit together with its nested items.
      - It is proved both ways.
- [ ] **Runs.**
      - The suite is green through the client, with a real `HOME` and an empty one; the empty
        `HOME` stays empty.
      - The skills load in Pi with no diagnostics.
      - The shutdown skill's frontmatter is unchanged.
      - New tests use a literal `§`, never `\u00a7`.
      - `generator/build.py --check` is clean.
      - The `AGENTS.md` counts and baselines match.

## Non-goals

- **The cause of the hang.** It belongs to Sandesh (#1464). A Sandesh remedy that changes the order
  a consumer needs comes back as its own CR.
- **The bootstrap skill.** It already finds an address left active and skips registering it.
- **Descriptive mentions that are not instructions.** These are left alone deliberately:
  - `modelb_axi/project_schema.toml`'s reader note ("shutdown skill (stops and unregisters the
    address)");
  - `bootstrap/SKILL.md`'s "stop it at shutdown".

## Cycle plan

1. **The rule (§S1–§S3).** Red-green.
2. **Verify.**
