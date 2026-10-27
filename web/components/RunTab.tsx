"use client";
import { useEffect, useMemo, useState } from "react";
import MapView from "./MapView";
import Gantt from "./Gantt";
import Playback, { usePlayback } from "./Playback";
import Params from "./Params";
import Metrics, { Issues, LogBox } from "./Metrics";
import { engine } from "@/lib/engine";
import { defaultParams, RunOptions, useBench } from "@/lib/useBench";
import { maxTime } from "@/lib/viz";

type Bench = ReturnType<typeof useBench>;

export function AlgoSelect({ bench, kind, sel, setSel, params, setParams, label }: { bench: Bench; kind: "mrta" | "mapf"; sel: string; setSel: (s: string) => void; params: any; setParams: (p: any) => void; label: string }) {
  const list = bench.algorithms(kind);
  const cur = list.find((a) => a.sel === sel) ?? list[0];
  return (
    <div className="field">
      <label>{label}</label>
      <select value={cur?.sel ?? ""} onChange={(e) => { setSel(e.target.value); const n = list.find((a) => a.sel === e.target.value); setParams(defaultParams(n?.info)); }} aria-label={label}>
        {list.map((a) => <option key={a.sel} value={a.sel}>{a.info.name}{a.origin !== "built-in" ? ` (${a.origin})` : ""}</option>)}
      </select>
      {cur?.info.description && <div className="hint">{cur.info.description}</div>}
      <Params info={cur?.info} values={params} onChange={setParams} />
    </div>
  );
}

export function useRunSettings(bench: Bench, initialScenarioId?: string) {
  const [scenId, setScenId] = useState<string>(initialScenarioId ?? "");
  const [mrta, setMrta] = useState("builtin:greedy");
  const [mapf, setMapf] = useState("builtin:prioritized");
  const [mrtaParams, setMrtaParams] = useState<any>({});
  const [mapfParams, setMapfParams] = useState<any>({});
  const [options, setOptions] = useState<RunOptions>({ max_rounds: 12, time_limit_s: 60, seed: 1 });
  useEffect(() => {
    if (!scenId && bench.scenarios.length) setScenId(bench.scenarios[0].id);
  }, [bench.scenarios, scenId]);
  useEffect(() => {
    if (bench.catalogue) {
      setMrtaParams(defaultParams(bench.catalogue.mrta.find((i: any) => "builtin:" + i.id === mrta)));
      setMapfParams(defaultParams(bench.catalogue.mapf.find((i: any) => "builtin:" + i.id === mapf)));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [bench.catalogue]);
  const scenario = useMemo(() => bench.scenarios.find((s) => s.id === scenId)?.json ?? null, [bench.scenarios, scenId]);
  return { scenId, setScenId, mrta, setMrta, mapf, setMapf, mrtaParams, setMrtaParams, mapfParams, setMapfParams, options, setOptions, scenario };
}

export function ScenarioSelect({ bench, scenId, setScenId }: { bench: Bench; scenId: string; setScenId: (s: string) => void }) {
  return (
    <div className="field">
      <label>Factory plan</label>
      <select value={scenId} onChange={(e) => setScenId(e.target.value)} aria-label="Factory plan">
        {bench.scenarios.map((s) => <option key={s.id} value={s.id}>{s.name}{s.origin !== "sample" ? ` (${s.origin})` : ""}</option>)}
      </select>
    </div>
  );
}

export default function RunTab({ bench, settings }: { bench: Bench; settings: ReturnType<typeof useRunSettings> }) {
  const s = settings;
  const [mode, setMode] = useState<"integrated" | "mrta_only" | "mapf_only">("integrated");
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [runScenario, setRunScenario] = useState<any>(null);
  const [error, setError] = useState("");
  const pb = usePlayback(maxTime(result));

  async function go() {
    if (!s.scenario) return;
    setRunning(true); setError("");
    try {
      const r = await bench.run({ scenario: s.scenario, mode, mrta: s.mrta, mapf: s.mapf, mrtaParams: s.mrtaParams, mapfParams: s.mapfParams, options: s.options });
      setResult(r); setRunScenario(s.scenario);
    } catch (e: any) { setError(String(e.message || e)); }
    setRunning(false);
  }

  const ready = bench.engineState === "ready";
  return (
    <div className="layout">
      <aside className="side">
        <ScenarioSelect bench={bench} scenId={s.scenId} setScenId={s.setScenId} />
        <AlgoSelect bench={bench} kind="mrta" label="MRTA algorithm (Sambhav)" sel={s.mrta} setSel={s.setMrta} params={s.mrtaParams} setParams={s.setMrtaParams} />
        <AlgoSelect bench={bench} kind="mapf" label="MAPF algorithm (Samyak)" sel={s.mapf} setSel={s.setMapf} params={s.mapfParams} setParams={s.setMapfParams} />
        <div className="field">
          <label>Mode</label>
          <div className="radios">
            {([["integrated", "Integrated"], ["mrta_only", "MRTA only"], ["mapf_only", "MAPF only"]] as const).map(([v, l]) => (
              <label key={v}><input type="radio" name="mode" checked={mode === v} onChange={() => setMode(v)} /> {l}</label>
            ))}
          </div>
        </div>
        <details className="field"><summary>Options</summary>
          <label className="param"><span>max rounds</span><input type="number" min={1} max={40} value={s.options.max_rounds} onChange={(e) => s.setOptions({ ...s.options, max_rounds: +e.target.value })} /></label>
          <label className="param"><span>time limit (s)</span><input type="number" min={1} max={600} value={s.options.time_limit_s} onChange={(e) => s.setOptions({ ...s.options, time_limit_s: +e.target.value })} /></label>
          <label className="param"><span>seed</span><input type="number" min={0} value={s.options.seed} onChange={(e) => s.setOptions({ ...s.options, seed: +e.target.value })} /></label>
        </details>
        <div className="row">
          <button className="btn primary" disabled={!ready || running || !s.scenario} onClick={go}>{running ? "Running…" : "▶ Run"}</button>
          <button className="btn" disabled={!running} onClick={() => { engine.stop("stopped by you"); }}>■ Stop</button>
        </div>
        <div className="row">
          <button className="btn small" onClick={() => window.open("/mrta", "factory-bench-mrta", "width=1150,height=850")}>Open MRTA window ⧉</button>
          <button className="btn small" onClick={() => window.open("/mapf", "factory-bench-mapf", "width=1150,height=850")}>Open MAPF window ⧉</button>
        </div>
        {error && <div className="note bad">{error}</div>}
      </aside>
      <section className="main">
        {!result && !running && <div className="empty">Pick a plan and algorithms, then press Run. Uploaded algorithms appear in the dropdowns after you add them in the Import tab.</div>}
        {running && <div className="empty">Planning… (the Python engine runs in a background worker; Stop ends it)</div>}
        {result && runScenario && (
          <>
            <Metrics result={result} />
            {Object.keys(result.paths ?? {}).length > 0 && (
              <div className="panel"><h3>Map</h3><MapView scenario={runScenario} result={result} t={pb.t} /><Playback maxT={maxTime(result)} {...pb} /></div>
            )}
            <div className="panel"><h3>Schedule (Gantt)</h3><Gantt scenario={runScenario} result={result} t={Object.keys(result.paths ?? {}).length ? pb.t : undefined} />
              <div className="legend"><span><i className="sw idle" /> robot driving empty / parking</span><span><i className="sw" style={{ background: "#2563eb" }} /> carrying (colour = product)</span><span>machine rows show processing</span></div></div>
            <Issues result={result} />
            <LogBox result={result} />
          </>
        )}
      </section>
    </div>
  );
}
