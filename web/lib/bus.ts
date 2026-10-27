// Shares the latest result between the main page and the pop-out MRTA / MAPF windows.
const KEY = "factory-bench:last-result:v1";
const CH = "factory-bench";

export type Shared = { kind: "integrated" | "mrta_only" | "mapf_only"; scenario: any; result: any; at: number };

export function publish(s: Shared) {
  try { localStorage.setItem(KEY, JSON.stringify(s)); } catch { /* too large or blocked */ }
  try { const ch = new BroadcastChannel(CH); ch.postMessage(s); ch.close(); } catch { /* unsupported */ }
}

export function latest(): Shared | null {
  try { const raw = localStorage.getItem(KEY); return raw ? JSON.parse(raw) : null; } catch { return null; }
}

export function subscribe(cb: (s: Shared) => void) {
  let ch: BroadcastChannel | null = null;
  try { ch = new BroadcastChannel(CH); ch.onmessage = (e) => cb(e.data); } catch { /* ignore */ }
  const onStorage = (e: StorageEvent) => { if (e.key === KEY && e.newValue) { try { cb(JSON.parse(e.newValue)); } catch { /* ignore */ } } };
  window.addEventListener("storage", onStorage);
  return () => { ch?.close(); window.removeEventListener("storage", onStorage); };
}
