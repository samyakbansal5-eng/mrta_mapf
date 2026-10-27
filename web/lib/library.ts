// Per-browser library of uploaded algorithms and factory plans (localStorage; may be unavailable).
export type LibAlgo = { id: string; kind: "mrta" | "mapf"; name: string; label: string; source: string; origin: string; addedAt: number; notes?: string; paramsSpec?: any };
export type LibScenario = { id: string; name: string; json: any; origin: string; addedAt: number; notes?: string };
export type Library = { algorithms: LibAlgo[]; scenarios: LibScenario[] };

const KEY = "factory-bench:library:v1";

export function loadLibrary(): Library {
  try {
    const raw = localStorage.getItem(KEY);
    if (raw) {
      const d = JSON.parse(raw);
      return { algorithms: d.algorithms ?? [], scenarios: d.scenarios ?? [] };
    }
  } catch { /* storage blocked or corrupt: start empty */ }
  return { algorithms: [], scenarios: [] };
}

export function saveLibrary(lib: Library): boolean {
  try { localStorage.setItem(KEY, JSON.stringify(lib)); return true; } catch { return false; }
}

export function uid() { return Math.random().toString(36).slice(2, 10); }
