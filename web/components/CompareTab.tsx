"use client";
import { useRef, useState } from "react";
import { engine } from "@/lib/engine";
import { defaultParams, useBench } from "@/lib/useBench";

type Bench = ReturnType<typeof useBench>;
type Row = { scenario: string; mrta: string; mapf: string; seed: number; ok: boolean; makespan: number | null; collisions: number | null; violations: number | null; waits: number | null; replans: number | null; ms: number | null; note: string };

export default function CompareTab({ bench }: { bench: Bench }) {
  const [scen, setScen] = useState<Record<string, boolean>>({});
  const [mrta, setMrta] = useState<Record<string, boolean>>({});
  const [mapf, setMapf] = useState<Record<string, boolean>>({});
  const [repeats, setRepeats] = useState(1);
  const [limit, setLimit] = useState(60);
  const [rows, setRows] = useState<Row[]>([]);
  const [progress, setProgress] = useState("");
  const [running, setRunning] = useState(false);
  const stop = useRef(false);

  const mrtaList = bench.algorithms("mrta"), mapfList = bench.algorithms("mapf");
  const pick = (m: Record<string, boolean>, ids: string[]) => ids.filter((i) => m[i]);

  async function go() {
    const S = pick(scen, bench.scenarios.map((s) => s.id)), A = pick(mrta, mrtaList.map((a) => a.sel)), B = pick(mapf, mapfList.map((a) => a.sel));
    const jobs: any[] = [];
    for (const s of S) for (const a of A) for (const b of B) for (let k = 1; k <= repeats; k++) jobs.push({ s, a, b, k });
    stop.current = false; setRunning(true); setRows([]);
    const out: Row[] = [];
    for (let i = 0; i < jobs.length && !stop.current; i++) {
      const { s, a, b, k } = jobs[i];
      const sc = bench.scenarios.find((x) => x.id === s)!;
      const ai = mrtaList.find((x) => x.sel === a)!, bi = mapfList.find((x) => x.sel === b)!;
      setProgress(`${i + 1} / ${jobs.length}: ${sc.name} · ${ai.info.name} · ${bi.info.name} · seed ${k}`);
      const withSeed = (info: any) => { const p = defaultParams(info); if ("seed" in p) p.seed = k; return p; };
      let row: Row = { scenario: sc.name, mrta: ai.info.name, mapf: bi.info.name, seed: k, ok: false, makespan: null, collisions: null, violations: null, waits: null, replans: null, ms: null, note: "" };
      try {
        const r = await bench.run({ scenario: sc.json, mode: "integrated", mrta: a, mapf: b, mrtaParams: withSeed(ai.info), mapfParams: withSeed(bi.info), options: { max_rounds: 12, time_limit_s: limit, seed: k } });
        const m = r.metrics ?? {};
        row = { ...row, ok: r.ok, makespan: r.ok ? r.makespan : null, collisions: m.collisions ?? null, violations: m.rule_violations ?? null, waits: m.waits ?? null, replans: m.replans ?? null, ms: m.runtime_ms ?? null, note: r.reason || (r.warnings ?? []).join("; ") };
      } catch (e: any) { row.note = String(e.message || e); }
      out.push(row); setRows([...out]);
    }
    setRunning(false); setProgress(stop.current ? "stopped" : "done");
  }

  // averages per scenario / MRTA / MAPF over the repeats
  const groups = new Map<string, Row[]>();
  for (const r of rows) { const k = `${r.scenario}||${r.mrta}||${r.mapf}`; groups.set(k, [...(groups.get(k) ?? []), r]); }
  const summary = [...groups.entries()].map(([k, rs]) => {
    const [scenario, mrtaN, mapfN] = k.split("||");
    const ok = rs.filter((r) => r.ok);
    const avg = (f: (r: Row) => number | null) => ok.length ? ok.reduce((s, r) => s + (f(r) ?? 0), 0) / ok.length : null;
    return { scenario, mrta: mrtaN, mapf: mapfN, runs: rs.length, success: ok.length / rs.length, makespan: avg((r) => r.makespan), waits: avg((r) => r.waits), ms: avg((r) => r.ms), note: rs.find((r) => r.note)?.note ?? "" };
  });
  const maxMk = Math.max(1, ...summary.map((s) => s.makespan ?? 0));

  function csv() {
    const head = "scenario,mrta,mapf,seed,valid,makespan,collisions,rule_violations,waits,replans,runtime_ms,note";
    const body = rows.map((r) => [r.scenario, r.mrta, r.mapf, r.seed, r.ok, r.makespan, r.collisions, r.violations, r.waits, r.replans, r.ms, JSON.stringify(r.note)].join(","));
    const url = URL.createObjectURL(new Blob([head + "\n" + body.join("\n")], { type: "text/csv" }));
    const a = document.createElement("a"); a.href = url; a.download = "factory-bench-comparison.csv"; a.click(); URL.revokeObjectURL(url);
  }

  const Check = ({ items, state, set }: { items: { id: string; name: string }[]; state: Record<string, boolean>; set: (m: Record<string, boolean>) => void }) => (
    <div className="checks">{items.map((i) => <label key={i.id}><input type="checkbox" checked={!!state[i.id]} onChange={(e) => set({ ...state, [i.id]: e.target.checked })} /> {i.name}</label>)}</div>
  );

  return (
    <div className="compare">
      <div className="panel">
        <h3>Compare algorithms on the same plans</h3>
        <p className="hint">Every chosen combination runs with the same rules and validators. Algorithms with a seed are repeated with seeds 1, 2, … and averaged. Invalid runs count as failures.</p>
        <div className="three">
          <div><h4>Factory plans</h4><Check items={bench.scenarios.map((s) => ({ id: s.id, name: s.name }))} state={scen} set={setScen} /></div>
          <div><h4>MRTA (Sambhav)</h4><Check items={mrtaList.map((a) => ({ id: a.sel, name: a.info.name }))} state={mrta} set={setMrta} /></div>
          <div><h4>MAPF (Samyak)</h4><Check items={mapfList.map((a) => ({ id: a.sel, name: a.info.name }))} state={mapf} set={setMapf} /></div>
        </div>
        <div className="row wrap">
          <label className="param"><span>repeats (seeds)</span><input type="number" min={1} max={10} value={repeats} onChange={(e) => setRepeats(+e.target.value)} /></label>
          <label className="param"><span>time limit per run (s)</span><input type="number" min={1} max={600} value={limit} onChange={(e) => setLimit(+e.target.value)} /></label>
          <button className="btn primary" disabled={running || bench.engineState !== "ready"} onClick={go}>▶ Run all combinations</button>
          <button className="btn" disabled={!running} onClick={() => { stop.current = true; engine.stop("stopped by you"); }}>■ Stop</button>
          <button className="btn" disabled={!rows.length} onClick={csv}>Export CSV</button>
        </div>
        {progress && <div className="hint">{progress}</div>}
      </div>
      {summary.length > 0 && (
        <div className="panel">
          <h3>Summary</h3>
          <table className="table"><thead><tr><th>plan</th><th>MRTA</th><th>MAPF</th><th>valid runs</th><th>avg makespan</th><th></th><th>avg waits</th><th>avg ms</th><th>note</th></tr></thead>
            <tbody>{summary.map((s, i) => (
              <tr key={i}><td>{s.scenario}</td><td>{s.mrta}</td><td>{s.mapf}</td><td>{Math.round(s.success * 100)}%</td>
                <td>{s.makespan === null ? "–" : s.makespan.toFixed(1)}</td>
                <td style={{ width: 140 }}>{s.makespan !== null && <div className="bar"><div style={{ width: (s.makespan / maxMk) * 100 + "%" }} /></div>}</td>
                <td>{s.waits === null ? "–" : s.waits.toFixed(1)}</td><td>{s.ms === null ? "–" : Math.round(s.ms)}</td><td className="muted">{s.note}</td></tr>))}</tbody></table>
        </div>
      )}
    </div>
  );
}
