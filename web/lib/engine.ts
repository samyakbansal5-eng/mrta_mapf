// Client for the Python engine running in a Web Worker. One request at a time is typical;
// Stop (or a time-out) terminates the worker, which is the hard limit for uploaded code.

type Pending = { resolve: (v: any) => void; reject: (e: Error) => void; timer?: ReturnType<typeof setTimeout> };

class Engine {
  private worker: Worker | null = null;
  private pending = new Map<number, Pending>();
  private nextId = 1;
  private helloPromise: Promise<any> | null = null;

  private start() {
    const w = new Worker("/worker.js");
    w.onmessage = (e: MessageEvent) => {
      const p = this.pending.get(e.data.id);
      if (!p) return;
      this.pending.delete(e.data.id);
      if (p.timer) clearTimeout(p.timer);
      e.data.ok ? p.resolve(e.data.data) : p.reject(new Error(e.data.error));
    };
    w.onerror = (e) => this.failAll(new Error("engine crashed: " + (e.message || "unknown error")));
    this.worker = w;
    return w;
  }

  private failAll(err: Error) {
    for (const p of this.pending.values()) { if (p.timer) clearTimeout(p.timer); p.reject(err); }
    this.pending.clear();
    this.worker?.terminate();
    this.worker = null;
    this.helloPromise = null;
  }

  /** Kill whatever is running (the Stop button, or a time limit). The next call starts a fresh worker. */
  stop(reason = "stopped") { this.failAll(new Error(reason)); }

  call<T = any>(type: string, args: any[] = [], timeoutMs?: number): Promise<T> {
    const w = this.worker ?? this.start();
    const id = this.nextId++;
    return new Promise<T>((resolve, reject) => {
      const p: Pending = { resolve, reject };
      if (timeoutMs) p.timer = setTimeout(() => this.failAll(new Error(`stopped: ran longer than ${Math.round(timeoutMs / 1000)} s`)), timeoutMs);
      this.pending.set(id, p);
      w.postMessage({ id, type, args });
    });
  }

  hello() { return (this.helloPromise ??= this.call("hello")); }
  catalogue() { return this.call("catalogue"); }
  validateScenario(text: string) { return this.call("validateScenario", [text]); }
  parseAscii(text: string, legend = "{}") { return this.call("parseAscii", [text, legend]); }
  checkPlugin(kind: string, source: string, label: string) { return this.call("checkPlugin", [kind, source, label], 30000); }

  /** Run a scenario. The worker is killed after hardLimitS (default: soft limit + 15 s grace). */
  run(req: any) {
    const soft = req.options?.time_limit_s ?? 60;
    return this.call("run", [JSON.stringify(req)], (soft + 15) * 1000);
  }
}

export const engine = new Engine();
