"use client";
import { useCallback, useEffect, useMemo, useState } from "react";
import { engine } from "./engine";
import { loadLibrary, saveLibrary, uid, Library, LibAlgo, LibScenario } from "./library";
import { publish } from "./bus";

export type Sel = string;            // "builtin:greedy" | "lib:<id>"
export type Catalogue = { mrta: any[]; mapf: any[] };
export type RunOptions = { max_rounds: number; time_limit_s: number; seed: number };

export function useBench() {
  const [catalogue, setCatalogue] = useState<Catalogue | null>(null);
  const [engineState, setEngineState] = useState<"loading" | "ready" | "error">("loading");
  const [engineMsg, setEngineMsg] = useState("");
  const [library, setLibrary] = useState<Library>({ algorithms: [], scenarios: [] });
  const [samples, setSamples] = useState<{ id: string; name: string; json: any; origin: string }[]>([]);

  useEffect(() => {
    setLibrary(loadLibrary());
    (async () => {
      try {
        const names: string[] = await (await fetch("/scenarios/index.json")).json();
        const loaded = await Promise.all(names.map(async (n) => ({ id: "sample:" + n, name: n.replace(/\.json$/, ""), json: await (await fetch("/scenarios/" + n)).json(), origin: "sample" })));
        setSamples(loaded);
      } catch { /* no samples */ }
    })();
    (async () => {
      try {
        const h = await engine.hello();
        setCatalogue(await engine.catalogue());
        setEngineState("ready");
        setEngineMsg("Python " + (h.pyodide ? "(Pyodide " + h.pyodide + ")" : ""));
      } catch (e: any) { setEngineState("error"); setEngineMsg(String(e.message || e)); }
    })();
  }, []);

  const persist = useCallback((lib: Library) => { setLibrary(lib); if (!saveLibrary(lib)) console.warn("library not saved (storage blocked)"); }, []);

  const addAlgorithm = useCallback((a: Omit<LibAlgo, "id" | "addedAt">) => {
    persist({ ...library, algorithms: [...library.algorithms, { ...a, id: uid(), addedAt: Date.now() }] });
  }, [library, persist]);
  const removeAlgorithm = useCallback((id: string) => persist({ ...library, algorithms: library.algorithms.filter((a) => a.id !== id) }), [library, persist]);
  const addScenario = useCallback((s: Omit<LibScenario, "id" | "addedAt">) => {
    const id = uid();
    persist({ ...library, scenarios: [...library.scenarios, { ...s, id, addedAt: Date.now() }] });
    return "lib:" + id;
  }, [library, persist]);
  const removeScenario = useCallback((id: string) => persist({ ...library, scenarios: library.scenarios.filter((s) => s.id !== id) }), [library, persist]);

  const scenarios = useMemo(() => [
    ...samples,
    ...library.scenarios.map((s) => ({ id: "lib:" + s.id, name: s.name, json: s.json, origin: s.origin })),
  ], [samples, library]);

  const algorithms = useCallback((kind: "mrta" | "mapf") => [
    ...((catalogue?.[kind] ?? []).map((i: any) => ({ sel: "builtin:" + i.id, info: i, origin: "built-in" }))),
    ...library.algorithms.filter((a) => a.kind === kind).map((a) => ({ sel: "lib:" + a.id, info: { name: a.name, description: a.notes ?? "", params: a.paramsSpec ?? {} }, origin: a.origin })),
  ], [catalogue, library]);

  /** Build the {name|source, params} spec the Python side wants. */
  const spec = useCallback((kind: "mrta" | "mapf", sel: Sel, params: any) => {
    if (sel.startsWith("lib:")) {
      const a = library.algorithms.find((x) => x.id === sel.slice(4));
      if (a) return { source: a.source, label: a.label, params };
    }
    return { name: sel.replace("builtin:", ""), params };
  }, [library]);

  const run = useCallback(async (o: { scenario: any; mode: "integrated" | "mrta_only" | "mapf_only"; mrta: Sel; mapf: Sel; mrtaParams: any; mapfParams: any; options: RunOptions }) => {
    const req = {
      scenario: o.scenario, mode: o.mode,
      mrta: spec("mrta", o.mrta, o.mrtaParams), mapf: spec("mapf", o.mapf, o.mapfParams),
      options: { max_rounds: o.options.max_rounds, time_limit_s: o.options.time_limit_s, seed: o.options.seed },
    };
    const result = await engine.run(req);
    publish({ kind: o.mode, scenario: o.scenario, result, at: Date.now() });
    return result;
  }, [spec]);

  return { catalogue, engineState, engineMsg, library, scenarios, algorithms, addAlgorithm, removeAlgorithm, addScenario, removeScenario, run, spec };
}

export function defaultParams(info: any) {
  const out: any = {};
  for (const [k, p] of Object.entries<any>(info?.params ?? {})) out[k] = p.default;
  return out;
}
