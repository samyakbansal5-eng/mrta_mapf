"use client";
import { useEffect, useState } from "react";
import MapView from "./MapView";
import Gantt from "./Gantt";
import Playback, { usePlayback } from "./Playback";
import Metrics, { Issues, LogBox } from "./Metrics";
import { AlgoSelect, ScenarioSelect, useRunSettings } from "./RunTab";
import { engine } from "@/lib/engine";
import { latest, subscribe, Shared } from "@/lib/bus";
import { useBench } from "@/lib/useBench";
import { maxTime } from "@/lib/viz";

/** One deliverable shown on its own: Sambhav's MRTA window or Samyak's MAPF window. */
export default function ModuleWindow({ module }: { module: "mrta" | "mapf" }) {
  const bench = useBench();
  const s = useRunSettings(bench);
  const [own, setOwn] = useState<{ scenario: any; result: any } | null>(null);
  const [integrated, setIntegrated] = useState<Shared | null>(null);
  const [source, setSource] = useState<"own" | "integrated">("own");
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    const l = latest();
    if (l?.kind === "integrated") setIntegrated(l);
    return subscribe((m) => { if (m.kind === "integrated") setIntegrated(m); });
  }, []);
  const shown = source === "own" ? own : integrated ? { scenario: integrated.scenario, result: integrated.result } : null;
  const pb = usePlayback(maxTime(shown?.result));
  const title = module === "mrta" ? "MRTA: task allocation and scheduling" : "MAPF: factory layout and path finding";
  const who = module === "mrta" ? "Sambhav" : "Samyak";

  async function go() {
    if (!s.scenario) return;
    setRunning(true); setError("");
    try {
      const r = await bench.run({ scenario: s.scenario, mode: module === "mrta" ? "mrta_only" : "mapf_only", mrta: s.mrta, mapf: s.mapf, mrtaParams: s.mrtaParams, mapfParams: s.mapfParams, options: s.options });
      setOwn({ scenario: s.scenario, result: r }); setSource("own");
    } catch (e: any) { setError(String(e.message || e)); }
    setRunning(false);
  }

  return (
    <div className="shell">
      <header className="top"><h1>{title}</h1><span className="chip">{who}'s deliverable</span>
        <span className={"chip " + bench.engineState}>{bench.engineState === "ready" ? "engine ready" : bench.engineState === "loading" ? "loading engine…" : "engine error"}</span></header>
      <div className="layout">
        <aside className="side">
          <ScenarioSelect bench={bench} scenId={s.scenId} setScenId={s.setScenId} />
          {module === "mrta"
            ? <AlgoSelect bench={bench} kind="mrta" label="MRTA algorithm" sel={s.mrta} setSel={s.setMrta} params={s.mrtaParams} setParams={s.setMrtaParams} />
            : <AlgoSelect bench={bench} kind="mapf" label="MAPF algorithm" sel={s.mapf} setSel={s.setMapf} params={s.mapfParams} setParams={s.setMapfParams} />}
          <div className="hint">{module === "mrta"
            ? "Runs on its own: travel times come from plain shortest paths, no robot paths are planned."
            : "Runs on its own: a fixed simple task plan (greedy) is used so the path planner has something to move."}</div>
          <div className="row">
            <button className="btn primary" disabled={bench.engineState !== "ready" || running || !s.scenario} onClick={go}>{running ? "Running…" : "▶ Run this module alone"}</button>
            <button className="btn" disabled={!running} onClick={() => engine.stop("stopped by you")}>■ Stop</button>
          </div>
          <div className="field"><label>Show</label>
            <div className="radios">
              <label><input type="radio" checked={source === "own"} onChange={() => setSource("own")} /> My last run</label>
              <label><input type="radio" checked={source === "integrated"} onChange={() => setSource("integrated")} /> Integrated run (main window)</label>
            </div>
          </div>
          {error && <div className="note bad">{error}</div>}
        </aside>
        <section className="main">
          {!shown && <div className="empty">{source === "own" ? "Run this module to see its results." : "No integrated run yet. Run one in the main window."}</div>}
          {shown && (
            <>
              <Metrics result={shown.result} only={module} />
              {module === "mrta" ? (
                <>
                  <div className="panel"><h3>Schedule (Gantt)</h3><Gantt scenario={shown.scenario} result={shown.result} /></div>
                  <div className="panel"><h3>Task assignment</h3>
                    <table className="table mono">
                      <thead><tr><th>task</th><th>product</th><th>from → to</th><th>robot</th><th>drive empty</th><th>carry</th><th>machine</th></tr></thead>
                      <tbody>{(shown.result.timeline ?? []).map((e: any) => (
                        <tr key={e.task}><td>{e.task}</td><td>{e.product}</td><td>{e.from} → {e.to}</td><td>{e.robot}</td>
                          <td>{e.approach.start}–{e.approach.arrive}</td><td>{e.carry.start}–{e.carry.arrive}</td><td>{e.machine.name ? `${e.machine.name} ${e.machine.start}–${e.machine.end}` : "–"}</td></tr>))}</tbody>
                    </table></div>
                </>
              ) : (
                <>
                  <div className="panel"><h3>Map</h3><MapView scenario={shown.scenario} result={shown.result} t={pb.t} /><Playback maxT={maxTime(shown.result)} {...pb} /></div>
                  <Issues result={shown.result} />
                  <div className="panel"><h3>Routes</h3>
                    <table className="table mono"><thead><tr><th>robot run</th><th>from</th><th>to</th><th>steps</th><th>cells moved</th></tr></thead>
                      <tbody>{Object.entries<any>(shown.result.paths ?? {}).map(([k, p]) => (
                        <tr key={k}><td>{k}</td><td>t={p[0][2]}</td><td>t={p[p.length - 1][2]}</td><td>{p.length - 1}</td><td>{p.filter((q: any, i: number) => i && (q[0] !== p[i - 1][0] || q[1] !== p[i - 1][1])).length}</td></tr>))}</tbody></table></div>
                </>
              )}
              <LogBox result={shown.result} />
            </>
          )}
        </section>
      </div>
    </div>
  );
}
