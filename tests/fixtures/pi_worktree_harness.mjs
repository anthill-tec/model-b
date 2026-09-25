#!/usr/bin/env node
// Test-only fixture (CR-MDB-039 §S1) — NOT production code. It loads
// `pi-package/extensions/worktree.ts` with the jiti mechanism Pi's own
// loader uses (`jiti.import(path, { default: true })`, the same module
// aliases as tests/fixtures/pi_watcher_harness.mjs), calls the factory with a
// recording fake `pi`, and runs a JSON step script from stdin.
//
// The fake pi-subagents service mirrors the installed
// `@gotgenes/pi-subagents` (src/service/service.ts, subagent-manager.ts):
// published on `globalThis[Symbol.for(serviceKey)]`, it offers
// `registerWorkspaceProvider(provider)` — records every call, refuses a
// second provider while one is active (as the real manager throws), and
// returns an unregister function — and `getRecord(agentId)` returning the
// record the `prepare` step registered BEFORE calling the provider (the real
// manager registers the child's record before `prepare` runs).
//
// argv: <extensionPath> <jitiMjsPath> <piPackageRoot>
// stdin: JSON {
//   "serviceKey": string,       // the Symbol.for() key of the fake service
//   "serviceAtLoad": bool,      // publish the fake service BEFORE the factory
//   "sessionCwd": string,       // ctx.cwd handed to tools and events
//   "steps": [ {op: ...}, ... ]
// }
// ops (every step records `env` = process.env.WF_WORKTREE_ROOT ?? null
// AFTER it ran, and `registrations` = provider registrations so far):
//   {"op":"installService"}                     // publish the fake service now
//   {"op":"replaceService"}                     // publish a DIFFERENT service instance
//        // under the key, as a child session's pi-subagents does
//        // (src/index.ts): it holds none of the parent's records and
//        // counts its own provider registrations (`otherRegistrations`)
//   {"op":"deleteService"}                      // delete the global entry, as a child's
//        // shutdown does (handlers/lifecycle.ts)
//   {"op":"event", "name":"session_start"}      // fire that event's handlers
//   {"op":"tool", "name":N, "params":{...}}     // execute a registered tool
//   {"op":"prepare", "label":L, "agentId":A, "description":D, "baseCwd":B}
//        // a dispatch: fires the extension's `tool_call` handlers with the
//        // pi-subagents `subagent` tool call (the dispatch itself — "first
//        // use"), registers the record, then calls the ACTIVE provider's
//        // prepare({agentId, agentType, baseCwd}); records the returned
//        // workspace's cwd, whether it was undefined, what dispose returned,
//        // or the thrown message
//   {"op":"rmrf", "path":P}                     // delete a directory tree
//   {"op":"hook", "extPath":E, "event":{...}, "ctx":{...}, "cwdFrom":L?}
//        // load a COMPILED Model B hook extension (jiti, same process, same
//        // process.env) and drive its handler for event.type; `cwdFrom`
//        // substitutes ctx.cwd with the cwd prepare step L returned
// stdout: one JSON object, always; every path reaches process.exit().

import { readFileSync, rmSync } from "node:fs";
import { createRequire } from "node:module";
import path from "node:path";
import { pathToFileURL } from "node:url";

const out = {
  defaultIsFunction: false,
  importError: null,
  tools: [],
  toolParameters: {},
  events: [],
  providerRegistrations: 0,
  providerUnregistrations: 0,
  otherRegistrations: 0,
  steps: [],
  harnessError: null,
};

function emit(code = 0) {
  process.stdout.write(JSON.stringify(out));
  process.exit(code);
}

function textOf(content) {
  if (typeof content === "string") return content;
  if (Array.isArray(content)) {
    return content.map((p) => (p && typeof p.text === "string" ? p.text : JSON.stringify(p))).join("\n");
  }
  return JSON.stringify(content);
}

function noopProxy(target) {
  return new Proxy(target, {
    get(t, k) {
      if (k in t) return t[k];
      if (k === "then") return undefined;
      return () => undefined;
    },
  });
}

function errText(err) {
  return err instanceof Error ? err.message : String(err);
}

async function withTimeout(promiseFactory, ms) {
  let timer;
  const timeout = new Promise((resolve) => {
    timer = setTimeout(() => resolve({ timedOut: true }), ms);
  });
  const run = (async () => {
    try {
      return { value: await promiseFactory() };
    } catch (err) {
      return { threw: errText(err) };
    }
  })();
  const res = await Promise.race([run, timeout]);
  clearTimeout(timer);
  return res;
}

async function main() {
  const [, , extPath, jitiMjsPath, piPkgRoot] = process.argv;
  if (!extPath || !jitiMjsPath || !piPkgRoot) {
    process.stderr.write("usage: pi_worktree_harness.mjs <extensionPath> <jitiMjsPath> <piPackageRoot>\n");
    process.exit(2);
  }
  const scenario = JSON.parse(readFileSync(0, "utf-8") || "{}");

  // --- the fake pi-subagents service -----------------------------------
  const records = new Map();
  let activeProvider;
  const service = noopProxy({
    registerWorkspaceProvider(provider) {
      out.providerRegistrations += 1;
      if (activeProvider) {
        throw new Error("A WorkspaceProvider is already registered; only one is supported.");
      }
      activeProvider = provider;
      return () => {
        out.providerUnregistrations += 1;
        if (activeProvider === provider) activeProvider = undefined;
      };
    },
    getRecord(id) {
      return records.get(id);
    },
  });
  const serviceKey = Symbol.for(scenario.serviceKey);
  const installService = () => { globalThis[serviceKey] = service; };
  // A child session's own pi-subagents service: a separate manager with its
  // own (here: empty) record store. The parent's records are not in it.
  const otherService = noopProxy({
    registerWorkspaceProvider() {
      out.otherRegistrations += 1;
      return () => undefined;
    },
    getRecord() {
      return undefined;
    },
  });
  if (scenario.serviceAtLoad) installService();

  // --- load the extension as Pi does -----------------------------------
  const req = createRequire(path.join(piPkgRoot, "package.json"));
  const alias = { "@earendil-works/pi-coding-agent": path.join(piPkgRoot, "dist", "index.js") };
  for (const spec of ["typebox", "typebox/compile", "typebox/value"]) {
    try {
      const resolved = req.resolve(spec);
      alias[spec] = resolved;
      alias[spec.replace(/^typebox/, "@sinclair/typebox")] = resolved;
    } catch { /* not resolvable: the extension import will say so */ }
  }
  const { createJiti } = await import(pathToFileURL(jitiMjsPath).href);
  const jiti = createJiti(import.meta.url, { moduleCache: false, alias });

  let factory;
  try {
    factory = await jiti.import(extPath, { default: true });
  } catch (err) {
    out.importError = err instanceof Error ? (err.stack || err.message) : String(err);
    emit();
    return;
  }
  out.defaultIsFunction = typeof factory === "function";
  if (!out.defaultIsFunction) { emit(); return; }

  const tools = new Map();
  const handlers = [];
  const pi = noopProxy({
    on(event, handler) { handlers.push({ event, handler }); return () => {}; },
    registerTool(tool) { tools.set(tool.name, tool); },
  });
  const ui = noopProxy({});
  const ctx = noopProxy({ cwd: scenario.sessionCwd ?? process.cwd(), hasUI: false, mode: "print", ui, signal: undefined });

  try {
    await factory(pi);
  } catch (err) {
    out.importError = "factory threw: " + (err instanceof Error ? (err.stack || err.message) : String(err));
    emit();
    return;
  }
  out.tools = [...tools.keys()];
  out.events = handlers.map((h) => h.event);
  for (const [name, tool] of tools) {
    out.toolParameters[name] = JSON.stringify(tool.parameters ?? null);
  }

  async function fire(eventName, event) {
    const results = [];
    for (const h of handlers.filter((x) => x.event === eventName)) {
      const res = await withTimeout(() => h.handler(event, ctx), 8000);
      results.push(res.threw ? { threw: res.threw } : (res.value ?? null));
    }
    return results;
  }

  const hookCache = new Map();
  async function hookHandlers(hookPath) {
    if (!hookCache.has(hookPath)) {
      const hookFactory = await jiti.import(hookPath, { default: true });
      const registered = [];
      await hookFactory({ on(event, handler) { registered.push({ event, handler }); return () => {}; } });
      hookCache.set(hookPath, registered);
    }
    return hookCache.get(hookPath);
  }

  const prepared = new Map();
  let callN = 0;
  for (const step of scenario.steps ?? []) {
    const rec = { op: step.op };
    if (step.op === "installService") {
      installService();
    } else if (step.op === "replaceService") {
      globalThis[serviceKey] = otherService;
    } else if (step.op === "deleteService") {
      delete globalThis[serviceKey];
    } else if (step.op === "event") {
      rec.results = await fire(step.name, { type: step.name });
    } else if (step.op === "tool") {
      rec.name = step.name;
      const tool = tools.get(step.name);
      if (!tool) {
        rec.missing = true;
      } else {
        callN += 1;
        const res = await withTimeout(
          () => tool.execute(`call-${callN}`, step.params ?? {}, undefined, undefined, ctx),
          step.timeoutMs ?? 8000,
        );
        rec.timedOut = !!res.timedOut;
        rec.threw = res.threw ?? null;
        rec.text = res.value ? textOf(res.value.content) : null;
      }
    } else if (step.op === "prepare") {
      rec.label = step.label ?? null;
      callN += 1;
      rec.dispatchResults = await fire("tool_call", {
        type: "tool_call",
        toolCallId: `dispatch-${callN}`,
        toolName: "subagent",
        input: { subagent_type: "general-purpose", description: step.description, prompt: step.description },
      });
      records.set(step.agentId, {
        id: step.agentId, type: "general-purpose", description: step.description,
        status: "running", isBackground: true, toolUses: 0, turnCount: 1, startedAt: Date.now(),
        compactionCount: 0,
      });
      if (!activeProvider) {
        rec.noProvider = true;
      } else {
        const res = await withTimeout(
          () => activeProvider.prepare({ agentId: step.agentId, agentType: "general-purpose", baseCwd: step.baseCwd }),
          step.timeoutMs ?? 8000,
        );
        rec.timedOut = !!res.timedOut;
        rec.threw = res.threw ?? null;
        const ws = res.value;
        rec.returnedUndefined = !res.threw && !res.timedOut && ws === undefined;
        rec.cwd = ws && typeof ws.cwd === "string" ? ws.cwd : null;
        if (ws && typeof ws.dispose === "function") {
          const d = await withTimeout(() => ws.dispose({ status: "completed", description: step.description }), 4000);
          rec.disposeReturn = d.threw ? { threw: d.threw } : (d.value === undefined ? "<undefined>" : d.value);
        }
        if (rec.label) prepared.set(rec.label, rec.cwd);
      }
    } else if (step.op === "rmrf") {
      rmSync(step.path, { recursive: true, force: true });
    } else if (step.op === "hook") {
      const hookCtx = { ...(step.ctx ?? {}) };
      if (step.cwdFrom) hookCtx.cwd = prepared.get(step.cwdFrom) ?? null;
      rec.ctxCwd = hookCtx.cwd ?? null;
      try {
        const registered = await hookHandlers(step.extPath);
        const entry = registered.find((r) => r.event === step.event.type);
        if (!entry) {
          rec.missing = true;
        } else {
          const res = await withTimeout(() => entry.handler(step.event, hookCtx), 15000);
          rec.timedOut = !!res.timedOut;
          rec.threw = res.threw ?? null;
          rec.result = res.value ?? null;
        }
      } catch (err) {
        rec.threw = errText(err);
      }
    }
    rec.env = process.env.WF_WORKTREE_ROOT ?? null;
    rec.registrations = out.providerRegistrations;
    out.steps.push(rec);
  }
  emit();
}

main().catch((err) => {
  out.harnessError = String((err && err.stack) || err);
  emit(0);
});
