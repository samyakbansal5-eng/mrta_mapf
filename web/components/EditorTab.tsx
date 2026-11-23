"use client";
import { useEffect, useMemo, useState } from "react";
import MapView from "./MapView";
import { engine } from "@/lib/engine";
import { useBench } from "@/lib/useBench";
import * as E from "@/lib/planEdit";
import { Plan } from "@/lib/planEdit";

type Bench = ReturnType<typeof useBench>;

const BLANK = {
  name: "new plan",
  grid: ["##########", "#........#", "#........#", "#........#", "#........#", "##########"],
  stations: { RM: [1, 1], M1: [4, 2], FG: [8, 4] },
  robots: [{ id: "R1", start: [1, 4], step_cost: 1, payload: 10 }],
  products: [{ id: "P1", route: ["M1"], weight: 1, process_time: { M1: 3 } }],
  events: [],
};

/** Text field that only commits on blur / Enter, so renames do not fire on every keystroke. */
function NameInput({ value, onCommit, label, width = 64 }: { value: string; onCommit: (v: string) => void; label: string; width?: number }) {
  const [v, setV] = useState(value);
  useEffect(() => setV(value), [value]);
  const commit = () => { const t = v.trim(); if (t && t !== value) onCommit(t); else setV(value); };
  return <input type="text" aria-label={label} style={{ width }} value={v} onChange={(e) => setV(e.target.value)} onBlur={commit} onKeyDown={(e) => { if (e.key === "Enter") (e.target as HTMLInputElement).blur(); }} />;
}

function Num({ value, onChange, label, min = 0, step = 1, width = 64 }: { value: number | null | undefined; onChange: (v: number) => void; label: string; min?: number; step?: number; width?: number }) {
  return <input type="number" aria-label={label} style={{ width }} min={min} step={step} value={value ?? ""} onChange={(e) => onChange(e.target.value === "" ? 0 : Number(e.target.value))} />;
}

function CellInput({ value, onChange, label }: { value: E.Cell; onChange: (c: E.Cell) => void; label: string }) {
  return (
    <span className="cellin">
      <Num label={label + " x"} value={value[0]} width={48} onChange={(x) => onChange([x, value[1]])} />
      <Num label={label + " y"} value={value[1]} width={48} onChange={(y) => onChange([value[0], y])} />
    </span>
  );
}

export default function EditorTab({ bench, onUseScenario }: { bench: Bench; onUseScenario: (id: string) => void }) {
  const [sourceId, setSourceId] = useState("");
  const [editingLibId, setEditingLibId] = useState<string | null>(null);
  const [plan, setPlanRaw] = useState<Plan | null>(null);
  const [dirty, setDirty] = useState(false);
  const [issues, setIssues] = useState<{ level: string; msg: string }[]>([]);
  const [checking, setChecking] = useState(false);
  const [mode, setMode] = useState("wall");
  const [saved, setSaved] = useState<string | null>(null);
  const [jsonText, setJsonText] = useState("");
  const [jsonErr, setJsonErr] = useState("");

  useEffect(() => { if (!sourceId && bench.scenarios.length) setSourceId(bench.scenarios[0].id); }, [bench.scenarios, sourceId]);

  const setPlan = (p: Plan) => { setPlanRaw(p); setDirty(true); setSaved(null); };

  function startFrom(id: string | "blank") {
    if (dirty && !window.confirm("Discard your unsaved changes?")) return;
    const src = id === "blank" ? null : bench.scenarios.find((s) => s.id === id);
    const lib = src && id.startsWith("lib:") ? id.slice(4) : null;
    const name = src ? (lib ? src.name : src.name + " (copy)") : "new plan";
    setPlanRaw(E.normalise(src ? src.json : BLANK, name));
    setEditingLibId(lib);
    setDirty(!lib); setSaved(null); setMode("wall");
  }

  // live validation with the same Python checks the Run tab uses
  useEffect(() => {
    if (!plan) return;
    setJsonText(JSON.stringify(plan, null, 2)); setJsonErr("");
    let live = true;
    setChecking(true);
    const t = setTimeout(async () => {
      try {
        const v = await engine.validateScenario(JSON.stringify(E.toScenario(plan)));
        if (live) setIssues(v);
      } catch (e: any) { if (live) setIssues([{ level: "error", msg: "engine could not read the plan: " + String(e.message || e) }]); }
      if (live) setChecking(false);
    }, 300);
    return () => { live = false; clearTimeout(t); };
  }, [plan]);

  const errors = issues.filter((i) => i.level === "error");
  const machines = plan ? E.machineNames(plan) : [];
  const preview = useMemo(() => plan && ({ paths: Object.fromEntries(plan.robots.map((r) => [r.id, [[r.start[0], r.start[1], 0]]])) }), [plan]);

  function onCell(x: number, y: number) {
    if (!plan) return;
    if (mode === "wall") return setPlan(E.toggleWall(plan, x, y));
    const [kind, name] = mode.split(":");
    if (kind === "station") return setPlan(E.moveStation(plan, name, [x, y]));
    if (kind === "robot") { const i = plan.robots.findIndex((r) => r.id === name); if (i >= 0) setPlan(E.updateRobot(plan, i, { start: [x, y] })); }
  }

  function save(asNew: boolean) {
    if (!plan) return;
    const json = E.toScenario(plan);
    if (!asNew && editingLibId) {
      bench.updateScenario(editingLibId, { name: plan.name, json });
      setSaved("lib:" + editingLibId);
    } else {
      const id = bench.addScenario({ name: plan.name, json, origin: "edited", notes: "" });
      setEditingLibId(id.slice(4)); setSaved(id);
    }
    setDirty(false);
  }

  function download() {
    if (!plan) return;
    const url = URL.createObjectURL(new Blob([JSON.stringify(E.toScenario(plan), null, 2)], { type: "application/json" }));
    const a = document.createElement("a");
    a.href = url; a.download = (plan.name || "plan").replace(/[^\w.-]+/g, "_") + ".json"; a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  function applyJson() {
    try { setPlan(E.normalise(JSON.parse(jsonText), plan?.name)); setJsonErr(""); }
    catch (e: any) { setJsonErr(String(e.message || e)); }
  }

  return (
    <div className="layout">
      <aside className="side">
        <div className="field">
          <label>Start from</label>
          <select value={sourceId} onChange={(e) => setSourceId(e.target.value)} aria-label="Start from plan">
            {bench.scenarios.map((s) => <option key={s.id} value={s.id}>{s.name}{s.origin !== "sample" ? ` (${s.origin})` : ""}</option>)}
          </select>
          <div className="row wrap" style={{ marginTop: 6 }}>
            <button className="btn" disabled={!sourceId} onClick={() => startFrom(sourceId)}>{sourceId.startsWith("lib:") ? "Edit this plan" : "Edit a copy"}</button>
            <button className="btn" onClick={() => startFrom("blank")}>Blank plan</button>
          </div>
          <div className="hint">Samples are never changed: you edit a copy. Plans in your library can be edited in place.</div>
        </div>
        {plan && (
          <>
            <label className="param"><span>Plan name</span><input type="text" value={plan.name} onChange={(e) => setPlan({ ...plan, name: e.target.value })} /></label>
            <div className="field">
              <label>Checks {checking && <span className="muted">(checking…)</span>}</label>
              {issues.length === 0 && !checking && <div className="note ok">All checks pass. The plan can run.</div>}
              {issues.map((i, k) => <div key={k} className={"note " + (i.level === "error" ? "bad" : "warn")}>{i.level}: {i.msg}</div>)}
            </div>
            <div className="row wrap">
              {editingLibId && <button className="btn primary" disabled={errors.length > 0 || !dirty} onClick={() => save(false)}>Save changes</button>}
              <button className={"btn" + (editingLibId ? "" : " primary")} disabled={errors.length > 0} onClick={() => save(true)}>{editingLibId ? "Save as new plan" : "Save to library"}</button>
              <button className="btn" onClick={download}>Download JSON</button>
            </div>
            {errors.length > 0 && <div className="hint">Fix the errors above to save. Warnings do not block saving.</div>}
            {dirty && <div className="hint">Unsaved changes.</div>}
            {saved && <div className="note ok">Saved to your library (this browser). <button className="link" onClick={() => onUseScenario(saved)}>Run it now →</button></div>}
          </>
        )}
      </aside>

      <section className="main">
        {!plan && <div className="empty">Pick a plan and press &ldquo;Edit a copy&rdquo;, or start from a blank plan. You can then add or remove robots, machines and products, set routes and process times, and add events such as a blocked aisle or a robot failure.</div>}
        {plan && (
          <>
            <div className="panel">
              <h3>Map</h3>
              <div className="row wrap small">
                <label className="param"><span>Clicking the map will</span>
                  <select value={mode} onChange={(e) => setMode(e.target.value)} aria-label="Map click mode">
                    <option value="wall">toggle wall / floor</option>
                    {Object.keys(plan.stations).map((s) => <option key={s} value={"station:" + s}>move station {s}</option>)}
                    {plan.robots.map((r) => <option key={r.id} value={"robot:" + r.id}>move robot {r.id} (start / parking)</option>)}
                  </select></label>
                <span className="muted">size {plan.grid[0]?.length ?? 0} × {plan.grid.length}</span>
                <button className="btn small" onClick={() => setPlan(E.resize(plan, "x", 1))}>+ column</button>
                <button className="btn small" onClick={() => setPlan(E.resize(plan, "x", -1))}>− column</button>
                <button className="btn small" onClick={() => setPlan(E.resize(plan, "y", 1))}>+ row</button>
                <button className="btn small" onClick={() => setPlan(E.resize(plan, "y", -1))}>− row</button>
              </div>
              <MapView scenario={plan} result={preview} t={0} onCellClick={onCell} />
              <div className="hint">x = column, y = row, counted from 0 at the top left. Circles are robot start cells (also their parking bays).</div>
            </div>

            <div className="panel">
              <h3>Robots <span className="muted">({plan.robots.length})</span></h3>
              <div className="scrollx"><table className="table">
                <thead><tr><th>id</th><th>start x, y</th><th>steps per cell</th><th>payload</th><th>may carry</th><th /></tr></thead>
                <tbody>
                  {plan.robots.map((r, i) => (
                    <tr key={i}>
                      <td><NameInput label="robot id" value={r.id} onCommit={(v) => setPlan(E.updateRobot(plan, i, { id: v }))} /></td>
                      <td><CellInput label={"robot " + r.id + " start"} value={r.start} onChange={(c) => setPlan(E.updateRobot(plan, i, { start: c }))} /></td>
                      <td><Num label="steps per cell" min={1} value={r.step_cost} onChange={(v) => setPlan(E.updateRobot(plan, i, { step_cost: v }))} /></td>
                      <td><Num label="payload" value={r.payload} step={0.5} onChange={(v) => setPlan(E.updateRobot(plan, i, { payload: v }))} /></td>
                      <td>
                        <label className="chk"><input type="checkbox" checked={r.can_carry === null} onChange={(e) => setPlan(E.updateRobot(plan, i, { can_carry: e.target.checked ? null : plan.products.map((p) => p.id) }))} /> any product</label>
                        {r.can_carry !== null && plan.products.map((p) => (
                          <label key={p.id} className="chk"><input type="checkbox" checked={r.can_carry!.includes(p.id)}
                            onChange={(e) => setPlan(E.updateRobot(plan, i, { can_carry: e.target.checked ? [...r.can_carry!, p.id] : r.can_carry!.filter((c) => c !== p.id) }))} /> {p.id}</label>
                        ))}
                      </td>
                      <td><button className="link" onClick={() => setPlan(E.removeRobot(plan, i))}>remove</button></td>
                    </tr>
                  ))}
                </tbody>
              </table></div>
              <button className="btn small" onClick={() => setPlan(E.addRobot(plan))}>+ Add robot</button>
              <div className="hint">Steps per cell: 1 = full speed, 2 = half speed. A robot only takes a product whose weight is at most its payload and that is ticked under &ldquo;may carry&rdquo;. Removing a robot also removes its events.</div>
            </div>

            <div className="panel">
              <h3>Machines and stores <span className="muted">({machines.length} machines)</span></h3>
              <div className="scrollx"><table className="table">
                <thead><tr><th>name</th><th>cell x, y</th><th>type (label)</th><th>used by</th><th /></tr></thead>
                <tbody>
                  {Object.entries(plan.stations).map(([name, c]) => (
                    <tr key={name}>
                      <td>{E.isStore(name) ? <b>{name}</b> : <NameInput label="machine name" value={name} onCommit={(v) => setPlan(E.renameStation(plan, name, v))} />}</td>
                      <td><CellInput label={"station " + name} value={c} onChange={(v) => setPlan(E.moveStation(plan, name, v))} /></td>
                      <td>{E.isStore(name) ? <span className="muted">{name === "RM" ? "raw-material store (start of every product)" : "finished-goods store (end)"}</span>
                        : <input type="text" aria-label="machine type" style={{ width: 110 }} value={plan.machines[name]?.type ?? ""} placeholder="e.g. CNC" onChange={(e) => setPlan(E.setMachineType(plan, name, e.target.value))} />}</td>
                      <td className="muted">{plan.products.filter((p) => p.route.includes(name)).map((p) => p.id).join(", ") || "–"}</td>
                      <td>{!E.isStore(name) && <button className="link" onClick={() => setPlan(E.removeMachine(plan, name))}>remove</button>}</td>
                    </tr>
                  ))}
                </tbody>
              </table></div>
              <button className="btn small" onClick={() => setPlan(E.addMachine(plan))}>+ Add machine</button>
              <div className="hint">Each machine works on one product at a time. The type is a label only for now: the algorithms do not read it yet. Removing a machine removes it from every route.</div>
            </div>

            <div className="panel">
              <h3>Products (job profiles) <span className="muted">({plan.products.length})</span></h3>
              <div className="scrollx"><table className="table">
                <thead><tr><th>id</th><th>weight</th><th>route: machine (process time in steps)</th><th /></tr></thead>
                <tbody>
                  {plan.products.map((p, i) => (
                    <tr key={i}>
                      <td><NameInput label="product id" value={p.id} onCommit={(v) => setPlan(E.updateProduct(plan, i, { id: v }))} /></td>
                      <td><Num label="weight" step={0.5} value={p.weight} onChange={(v) => setPlan(E.updateProduct(plan, i, { weight: v }))} /></td>
                      <td>
                        <div className="route">
                          <span className="muted">RM →</span>
                          {p.route.map((m, k) => (
                            <span key={k} className="step">
                              <b>{m}</b>
                              <Num label={`process time of ${p.id} at ${m}`} width={52} value={p.process_time[m] ?? 0} onChange={(v) => setPlan(E.setProcessTime(plan, i, m, v))} />
                              <button className="link" title="move earlier" aria-label="move earlier" disabled={k === 0} onClick={() => setPlan(E.moveStep(plan, i, k, -1))}>‹</button>
                              <button className="link" title="move later" aria-label="move later" disabled={k === p.route.length - 1} onClick={() => setPlan(E.moveStep(plan, i, k, 1))}>›</button>
                              <button className="link" title="remove step" aria-label="remove step" onClick={() => setPlan(E.removeStep(plan, i, k))}>×</button>
                              <span className="muted">→</span>
                            </span>
                          ))}
                          <select aria-label={"add step to " + p.id} value="" onChange={(e) => e.target.value && setPlan(E.addStep(plan, i, e.target.value))}>
                            <option value="">+ step…</option>
                            {machines.map((m) => <option key={m} value={m}>{m}</option>)}
                          </select>
                          {"FG" in plan.stations && <span className="muted">→ FG</span>}
                        </div>
                      </td>
                      <td className="nowrap">
                        <button className="link" onClick={() => setPlan(E.duplicateProduct(plan, i))}>duplicate</button>
                        <button className="link" onClick={() => setPlan(E.removeProduct(plan, i))}>remove</button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table></div>
              <button className="btn small" onClick={() => setPlan(E.addProduct(plan))}>+ Add product</button>
              <div className="hint">Each product is one unit that travels RM → its machines in order → FG; a robot carries it between stops. To make several units of the same job, use &ldquo;duplicate&rdquo;. One machine may appear twice in a route; it then uses the same process time both times.</div>
            </div>

            <div className="panel">
              <h3>Events <span className="muted">({plan.events.length})</span></h3>
              {plan.events.length > 0 && <div className="scrollx"><table className="table">
                <thead><tr><th>time t</th><th>what</th><th>details</th><th /></tr></thead>
                <tbody>
                  {plan.events.map((ev, i) => (
                    <tr key={i}>
                      <td><Num label="event time" value={ev.t} onChange={(v) => setPlan(E.updateEvent(plan, i, { t: v }))} /></td>
                      <td>{ev.type === "block_cells" ? "aisle blocked" : ev.type === "robot_failure" ? "robot fails" : "robot recovers"}</td>
                      <td>
                        {ev.type === "block_cells" ? (
                          <span className="row wrap">
                            <label className="param"><span>cells (x,y; x,y)</span><NameInput label="blocked cells" width={150} value={E.formatCells(ev.cells)} onCommit={(v) => setPlan(E.updateEvent(plan, i, { cells: E.parseCells(v) }))} /></label>
                            <label className="param"><span>open again at (empty = never)</span>
                              <input type="number" aria-label="until" style={{ width: 72 }} min={0} value={ev.until ?? ""} onChange={(e) => setPlan(E.updateEvent(plan, i, { until: e.target.value === "" ? null : Number(e.target.value) }))} /></label>
                          </span>
                        ) : (
                          <select aria-label="robot" value={ev.robot} onChange={(e) => setPlan(E.updateEvent(plan, i, { robot: e.target.value }))}>
                            {!plan.robots.some((r) => r.id === ev.robot) && <option value={ev.robot}>{ev.robot} (missing)</option>}
                            {plan.robots.map((r) => <option key={r.id} value={r.id}>{r.id}</option>)}
                          </select>
                        )}
                      </td>
                      <td><button className="link" onClick={() => setPlan(E.removeEvent(plan, i))}>remove</button></td>
                    </tr>
                  ))}
                </tbody>
              </table></div>}
              <div className="row wrap">
                <button className="btn small" onClick={() => setPlan(E.addEvent(plan, "block_cells"))}>+ Blocked aisle</button>
                <button className="btn small" disabled={!plan.robots.length} onClick={() => setPlan(E.addEvent(plan, "robot_failure"))}>+ Robot failure</button>
                <button className="btn small" disabled={!plan.robots.length} onClick={() => setPlan(E.addEvent(plan, "robot_recovered"))}>+ Robot recovery</button>
              </div>
              <div className="hint">Times are in time steps. Events only take effect in runs that plan paths (Integrated or MAPF only).</div>
            </div>

            <details className="panel">
              <summary><b>Advanced: edit as JSON</b></summary>
              <textarea className="code mono" rows={16} value={jsonText} onChange={(e) => setJsonText(e.target.value)} aria-label="Plan JSON" />
              <div className="row"><button className="btn small" onClick={applyJson}>Apply JSON</button>{jsonErr && <span className="note bad">{jsonErr}</span>}</div>
            </details>
          </>
        )}
      </section>
    </div>
  );
}
