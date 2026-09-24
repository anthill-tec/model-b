/**
 * Sandesh watcher supervisor (CR-MDB-029 §S2).
 *
 * Runs `sandesh notify --to <address> --project <project>` as a child and
 * follows its exit contract (Sandesh 0.3.5):
 *
 *   0      mail is waiting   -> wake the session naming the unread ids, relaunch at
 *                               once; a relaunch with the same ids wakes nothing
 *                               and retries every 30 s; new ids wake again
 *   2      timeout, no mail  -> relaunch silently; three within a minute surface
 *   1/3/4/5, signal          -> stop, surface the code and its meaning
 *
 * The watcher runs at all times: only `stop` or a terminal exit ends it.
 * One watcher per address. Nothing starts at load time; the `sandesh_watcher`
 * tool (start/status/stop) and the `/watcher status|stop` command drive it.
 */

import { type ChildProcess, spawn } from "node:child_process";
import { constants } from "node:os";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";

const MAIL_EXIT = 0;
const TIMEOUT_EXIT = 2;
const TIMEOUT_CAP = 3;
const TIMEOUT_WINDOW_MS = 60_000;
const RETRY_MS = 30_000;
const KILL_GRACE_MS = 3_000;
const STDOUT_KEEP = 8_000;
/** Sandesh 0.3.5: `[notify] <time> \u2709 N unread 'to' message(s): [12, 13]`. */
const UNREAD_RE = /unread 'to' message\(s\): \[([^\]]*)\]/g;
/** Sandesh 0.3.5 polled and found nothing: `[notify] <time> no 'to' mail \u2014 next check in Ns`. */
const NO_MAIL = "no 'to' mail";

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
	/** Unread ids the session has already been woken for. */
	wokenIds: Set<string>;
	/** The last wake named no ids (Sandesh printed none we could read). */
	wokeUnnamed: boolean;
	/** A pending same-ids relaunch. */
	retryTimer?: ReturnType<typeof setTimeout>;
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

/** POSIX shell quoting: bare when safe, else single-quoted. */
function shellQuote(s: string): string {
	return /^[A-Za-z0-9_./:@%+=,-]+$/.test(s) ? s : `'${s.replace(/'/g, `'\\''`)}'`;
}

/** The unread ids on Sandesh's last `unread 'to' message(s): [...]` line. */
function unreadIds(stdout: string): string[] {
	let last: RegExpMatchArray | undefined;
	for (const m of stdout.matchAll(UNREAD_RE)) last = m;
	if (!last) return [];
	return last[1]
		.split(",")
		.map((s) => s.trim().replace(/^['"]|['"]$/g, ""))
		.filter(Boolean);
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

	function wake(watcher: Watcher, ids: string[]): void {
		const which = ids.length ? `unread message id(s) ${ids.join(", ")}` : "unread message ids not reported";
		pi.sendUserMessage(
			`Sandesh mail is waiting for "${watcher.address}" (${which}). ` +
				`Run \`sandesh fetch --project ${shellQuote(watcher.project)} --to ${shellQuote(watcher.address)}\` to read it. ` +
				"The watcher keeps running and wakes the session again for new mail.",
			{ deliverAs: "followUp" },
		);
	}

	/** The mail was fetched (no mail reported, or a timeout): later mail wakes again (\u00a7S2, amended at C6). */
	function clearSuppression(watcher: Watcher): void {
		watcher.wokenIds.clear();
		watcher.wokeUnnamed = false;
	}

	/** Exit 0: wake for ids not yet woken for and relaunch at once; else retry in 30 s. */
	function onMail(watcher: Watcher, stdout: string): void {
		const ids = unreadIds(stdout);
		const fresh = ids.length ? ids.some((id) => !watcher.wokenIds.has(id)) : !watcher.wokeUnnamed;
		if (fresh) {
			for (const id of ids) watcher.wokenIds.add(id);
			watcher.wokeUnnamed = ids.length === 0;
			wake(watcher, ids);
			launch(watcher);
			return;
		}
		watcher.retryTimer = setTimeout(() => {
			watcher.retryTimer = undefined;
			if (!watcher.stopping) launch(watcher);
		}, RETRY_MS);
	}

	/** Called when a launch that already printed its banner (or a relaunch) ends. */
	function onExit(watcher: Watcher, code: number | null, signal: NodeJS.Signals | null, stdout: string): void {
		if (watcher.stopping) return;
		if (code === MAIL_EXIT && !signal) {
			onMail(watcher, stdout);
			return;
		}
		if (code === TIMEOUT_EXIT && !signal) {
			clearSuppression(watcher);
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
		surface(watcher, describeExit(code, signal));
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
			let bannerSeen = false;
			let noMailSeen = false;
			const banner = `watching ${watcher.address}`;
			child.stdout?.on("data", (chunk: Buffer) => {
				stdout = (stdout + chunk.toString()).slice(-STDOUT_KEEP);
				if (!noMailSeen && stdout.includes(NO_MAIL)) {
					noMailSeen = true;
					clearSuppression(watcher);
				}
				if (!bannerSeen && stdout.includes(banner)) {
					bannerSeen = true;
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
				onExit(watcher, code, signal, stdout);
			};
			child.on("error", (err) => finish(null, null, err));
			child.on("close", (code, signal) => finish(code, signal));
		});
	}

	async function start(address: string, project: string): Promise<string> {
		const running = watchers.get(address);
		if (running) return `A Sandesh watcher is already running for "${address}" (pid ${running.child?.pid}).`;
		const watcher: Watcher = {
			address,
			project,
			ready: false,
			stopping: false,
			timeouts: [],
			wokenIds: new Set(),
			wokeUnnamed: false,
		};
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
			if (w.retryTimer) clearTimeout(w.retryTimer);
			w.retryTimer = undefined;
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
			.map((w) => {
				const state = w.retryTimer ? "mail waiting, rechecking" : w.ready ? "watching" : "starting";
				return `"${w.address}" in ${w.project}: ${state} (pid ${w.child?.pid})`;
			})
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
