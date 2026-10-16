# CR-MDB-077 — The generated permission policy allows the Sandesh tools

**Status:** PENDING — **SEED, not the finished spec** (filed 2026-10-16 into release 1.0.0, wave 2).
Gap analysis, the spec and its pre-review happen in order when this CR starts.
**Type:** fix (`modelb_axi`, the generated per-project policy)
**Priority:** P1 — release 1.0.0, wave 2.
**Depends on:** none (board-authoritative: read `queue`)
**Labels:** permissions, sandesh, scaffold
**Design reference:** DN-multi-harness-deploy-model §D24; CR-MDB-037 §S3 (the per-project policy);
Sandesh #1472.

## Context

- **What hung.** On 2026-10-16 a shutdown hung for 15 minutes. pi-permission-system's review log shows
  `permission_request.waiting` on `sandesh_notify_stop` at 00:13:28 UTC and `denied` ("the session
  ended before this permission request was answered") at 00:28:11.
- **Why.** Model B's generated policy (`.pi/extensions/pi-permission-system/config.json`, from
  `modelb_axi/permission_policy.py`) has `"*": "ask"`, and its allow set holds no Sandesh tool. So each
  first use of a Sandesh tool in a session prompts.
- **Why the second call never ran.** Pi prepares parallel tool calls one after another, so the
  `sandesh_unregister` beside it never reached its own prompt.
- **How the allow set is built today.** `workflow_tools()` derives it from the `tools` of the
  `dispatch` and `lean-ctx` requirement rows (`_TOOL_REQUIREMENTS`). The `sandesh-pi` row
  (`@anthill-tec/sandesh-pi`, tier 1) has an empty `tools` tuple.

## Scope (seed)

1. **The `sandesh-pi` requirement row lists the extension's tools:**
   - `sandesh_setup`, `sandesh_register`, `sandesh_unregister`;
   - `sandesh_send`, `sandesh_reply`;
   - `sandesh_addressbook`, `sandesh_fetch`, `sandesh_inbox`, `sandesh_thread`, `sandesh_search`,
     `sandesh_status`;
   - `sandesh_notify_start`, `sandesh_notify_stop`, `sandesh_notify_status`.

   `sandesh_archive` and `sandesh_unarchive` are not listed, so they keep asking.
2. **`_TOOL_REQUIREMENTS` gains `sandesh-pi`,** so `workflow_tools()` allows those names. Decide at gap
   analysis whether the Sandesh tools leave the set when sandesh-pi is absent, as the lean-ctx tools
   do.
3. **Model B's own `.pi` policy** is re-rendered, with the user re-running the installer's policy step
   or `modelb-axi init`'s policy path, and a project's re-render path is documented.
4. **The gates move with it:** the policy's allow-set tests, the requirements table tests, and the
   install guide if it lists the allowed tools.

## To measure at gap analysis

- The installed sandesh-pi 0.4.3 tool names (`src/index.ts` `registerTool`), so the list matches the
  shipped extension exactly.
- How a project re-renders its policy today (`modelb-axi agents`, `init`, or the installer), and
  whether a hand-modified policy is left alone (the ownership marker).
- Whether the user's global pi-permission-system config needs a note. Model B never writes it.
- The re-score.
