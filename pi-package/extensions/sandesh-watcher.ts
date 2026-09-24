/**
 * Sandesh watcher supervisor (CR-MDB-029 §S2).
 *
 * Runs `sandesh notify --to <address> --project <project>` as a child and
 * follows its exit contract (Sandesh 0.3.5):
 *
 *   0      mail is waiting   -> wake the session once, leave the watcher stopped
 *   2      timeout, no mail  -> relaunch silently; three within a minute surface
 *   1/3/4/5, signal          -> stop, surface the code and its meaning
 *
 * One watcher per address. Nothing starts at load time; the `sandesh_watcher`
 * tool (start/status/stop) and the `/watcher status|stop` command drive it.
 */

import { type ChildProcess, spawn } from "node:child_process";
import { constants } from "node:os";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";

const TIMEOUT_EXIT = 2;
const TIMEOUT_CAP = 3;
const TIMEOUT_WINDOW_MS = 60_000;
const KILL_GRACE_MS = 3_000;

const EXIT_MEANINGS: Record<number, string> = {
	1: "usage or configuration error",
	3: "the project was tombstoned",
	4: "evicted: another notifier took the address over",
	5: "a notifier was already live for the address (dedup)",
};

interface Watcher {
	address: string;
	project: string;
	child?: ChildProcess;
	ready: boolean;
	stopping: boolean;
	timeouts: number[];
}

const WatcherParams = Type.Object({
	action: Type.Unsafe<"start" | "status" | "stop">({
		type: "string",
		enum: ["start", "status", "stop"],
		description: "start a watcher, report running watchers, or stop one (all when no address)",
	}),
	address: Type.Optional(Type.String({ description: "Sandesh address to watch, e.g. 'Mainline - ModelB'" })),
	project: Type.Optional(Type.String({ description: "Sandesh project of the address (start only)" })),
});

function signalName(signal: NodeJS.Signals | null, code: number | null): string | undefined {
	if (signal) return `${signal} (${constants.signals[signal] ?? "?"})`;
	if (code !== null && code > 128) {
		const n = code - 128;
		const name = Object.entries(constants.signals).find(([, v]) => v === n)?.[0];
		return `${name ?? "signal"} (${n}), exit ${code}`;
	}
	return undefined;
}

function describeExit(code: number | null, signal: NodeJS.Signals | null): string {
	const sig = signalName(signal, code);
	if (sig) return `killed by signal ${sig}`;
	const meaning = code !== null ? EXIT_MEANINGS[code] : undefined;
	return `exit ${code}: ${meaning ?? "unexpected exit code"}`;
}

function text(t: string) {
	return { content: [{ type: "text" as const, text: t }], details: undefined };
}

export default function sandeshWatcher(pi: ExtensionAPI) {
	const watchers = new Map<string, Watcher>();

	function forget(watcher: Watcher): void {
		if (watchers.get(watcher.address) === watcher) watchers.delete(watcher.address);
	}

	function surface(watcher: Watcher, what: string): void {
		pi.sendMessage(
			{
				customType: "sandesh-watcher",
				content: `Sandesh watcher for "${watcher.address}" stopped (${what}). It will not be relaunched.`,
				display: true,
			},
			{ triggerTurn: true, deliverAs: "followUp" },
		);
	}

	function wake(watcher: Watcher): void {
		pi.sendUserMessage(
			`Sandesh mail is waiting for "${watcher.address}". ` +
				`Run \`sandesh fetch --project ${watcher.project} --to ${watcher.address}\` to read it, ` +
				"then start the notifier again.",
			{ deliverAs: "followUp" },
		);
	}

	/** Called when a launch that already printed its banner (or a relaunch) ends. */
	function onExit(watcher: Watcher, code: number | null, signal: NodeJS.Signals | null): void {
		if (watcher.stopping) return;
		if (code === TIMEOUT_EXIT && !signal) {
			const now = Date.now();
			watcher.timeouts = [...watcher.timeouts.filter((t) => now - t < TIMEOUT_WINDOW_MS), now];
			if (watcher.timeouts.length < TIMEOUT_CAP) {
				launch(watcher);
				return;
			}
			watchers.delete(watcher.address);
			surface(watcher, `exit 2: timed out ${TIMEOUT_CAP} times within one minute`);
			return;
		}
		forget(watcher);
		if (code === 0 && !signal) wake(watcher);
		else surface(watcher, describeExit(code, signal));
	}

	/** Spawn one `sandesh notify`; resolves with null on the banner, or the reason it ended first. */
	function launch(watcher: Watcher): Promise<string | null> {
		return new Promise((resolve) => {
			const child = spawn("sandesh", ["notify", "--to", watcher.address, "--project", watcher.project], {
				// Sandesh prints its banner with an unflushed print(); piped, it would
				// be held until exit without this (CR-MDB-029 §S2, amended at C5).
				env: { ...process.env, PYTHONUNBUFFERED: "1" },
				stdio: ["ignore", "pipe", "pipe"],
			});
			watcher.child = child;
			let stdout = "";
			let stderr = "";
			let ended = false;
			const banner = `watching ${watcher.address}`;
			child.stdout?.on("data", (chunk: Buffer) => {
				if (watcher.ready && watcher.child === child) return;
				stdout += chunk.toString();
				if (stdout.includes(banner)) {
					watcher.ready = true;
					resolve(null);
				}
			});
			child.stderr?.on("data", (chunk: Buffer) => {
				stderr = (stderr + chunk.toString()).slice(-2000);
			});
			const finish = (code: number | null, signal: NodeJS.Signals | null, error?: Error) => {
				if (ended) return;
				ended = true;
				if (!watcher.ready) {
					// The first launch ended before its banner: report it to `start`, never relaunch.
					forget(watcher);
					const why = error ? `could not run sandesh: ${error.message}` : describeExit(code, signal);
					resolve(`${why}${stderr.trim() ? `\n${stderr.trim()}` : ""}`);
					return;
				}
				onExit(watcher, code, signal);
			};
			child.on("error", (err) => finish(null, null, err));
			child.on("close", (code, signal) => finish(code, signal));
		});
	}

	async function start(address: string, project: string): Promise<string> {
		const running = watchers.get(address);
		if (running) return `A Sandesh watcher is already running for "${address}" (pid ${running.child?.pid}).`;
		const watcher: Watcher = { address, project, ready: false, stopping: false, timeouts: [] };
		watchers.set(address, watcher);
		const failure = await launch(watcher);
		if (failure !== null) return `The Sandesh watcher for "${address}" did not start: ${failure}`;
		return `Sandesh watcher ready: watching "${address}" in ${project} (pid ${watcher.child?.pid}).`;
	}

	function stop(address?: string): string {
		const targets = address ? [watchers.get(address)].filter((w): w is Watcher => !!w) : [...watchers.values()];
		if (targets.length === 0) return address ? `No Sandesh watcher is running for "${address}".` : "No Sandesh watcher is running.";
		for (const w of targets) {
			w.stopping = true;
			watchers.delete(w.address);
			const child = w.child;
			if (child && child.exitCode === null && child.signalCode === null) {
				child.kill("SIGTERM");
				setTimeout(() => {
					if (child.exitCode === null && child.signalCode === null) child.kill("SIGKILL");
				}, KILL_GRACE_MS).unref();
			}
		}
		return `Stopped the Sandesh watcher for ${targets.map((w) => `"${w.address}"`).join(", ")}.`;
	}

	function status(): string {
		if (watchers.size === 0) return "No Sandesh watcher is running.";
		return [...watchers.values()]
			.map((w) => `"${w.address}" in ${w.project}: ${w.ready ? "watching" : "starting"} (pid ${w.child?.pid})`)
			.join("\n");
	}

	pi.registerTool({
		name: "sandesh_watcher",
		label: "Sandesh watcher",
		description:
			"Supervise a `sandesh notify` watcher: `start` (address, project) runs it and wakes the session when mail " +
			"arrives, `status` lists running watchers, `stop` ends one (or all when no address is given).",
		parameters: WatcherParams,
		async execute(_toolCallId, params) {
			if (params.action === "status") return text(status());
			if (params.action === "stop") return text(stop(params.address));
			if (params.action === "start") {
				if (!params.address || !params.project) throw new Error("start needs both address and project");
				return text(await start(params.address, params.project));
			}
			throw new Error(`unknown action ${JSON.stringify(params.action)}; use start, status or stop`);
		},
	});

	pi.registerCommand("watcher", {
		description: "Sandesh watcher: /watcher status | /watcher stop [address]",
		handler: async (args, ctx) => {
			const [sub, ...rest] = args.trim().split(/\s+/);
			if (sub === "stop") ctx.ui.notify(stop(rest.join(" ") || undefined), "info");
			else if (!sub || sub === "status") ctx.ui.notify(status(), "info");
			else ctx.ui.notify(`Unknown /watcher subcommand "${sub}"; use status or stop.`, "warning");
		},
	});

	pi.on("session_shutdown", async () => {
		stop();
	});
}
