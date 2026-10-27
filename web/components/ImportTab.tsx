"use client";
import { useEffect, useRef, useState } from "react";
import MapView from "./MapView";
import { engine } from "@/lib/engine";
import { readFile, Payload } from "@/lib/files";
import { useBench } from "@/lib/useBench";

type Bench = ReturnType<typeof useBench>;
type Draft = {
  kind: "scenario" | "algorithm";
  source: "file" | "gemini";
  payload: Payload;
  notes: string[]; missing: string[]; assumed: string[];
  scenario?: any; scenarioText?: string;
  code?: string; algoKind?: "mrta" | "mapf"; faithful?: boolean;
};

const ACCESS_KEY = "factory-bench:access-code";

export default function ImportTab({ bench, onUseScenario }: { bench: Bench; onUseScenario: (id: string) => void }) {
  const [draft, setDraft] = useState<Draft | null>(null);
  const [msg, setMsg] = useState<{ tone: "ok" | "bad" | "warn"; text: string } | null>(null);
  const [busy, setBusy] = useState("");
  const [gem, setGem] = useState<{ configured: boolean; model: string | null; accessCodeRequired: boolean } | null>(null);
  const [access, setAccess] = useState("");
  const [hint, setHint] = useState("");
  const input = useRef<HTMLInputElement>(null);

  useEffect(() => {
    fetch("/api/convert").then((r) => r.json()).then(setGem).catch(() => setGem(null));
    try { setAccess(sessionStorage.getItem(ACCESS_KEY) ?? ""); } catch { /* ignore */ }
  }, []);

  async function onFiles(files: FileList | null) {
    const f = files?.[0];
    if (!f) return;
    setMsg(null); setDraft(null); setBusy("Reading file…");
    try {
      const p = await readFile(f);
      await route(p);
    } catch (e: any) { setMsg({ tone: "bad", text: String(e.message || e) }); }
    setBusy("");
  }

  /** Deterministic parsers first (no LLM); anything else goes to Gemini. */
  async function route(p: Payload) {
    if (p.kind === "text") {
      const t = p.text!;
      if (/\.py$/i.test(p.filename)) {
        const kind = /["']module["']\s*:\s*["']mapf["']/.test(t) || /def\s+plan\s*\(/.test(t) ? "mapf" : "mrta";
        const chk = await engine.checkPlugin(kind, t, p.filename);
        if (chk.ok) { setDraft({ kind: "algorithm", source: "file", payload: p, code: t, algoKind: kind, notes: ["Follows the plug-in contract."], missing: [], assumed: [] }); return; }
        setMsg({ tone: "warn", text: "This Python file does not follow the contract (" + chk.error + "). You can ask Gemini to adapt it." });
        setDraft({ kind: "algorithm", source: "file", payload: p, code: t, algoKind: kind, notes: [], missing: [], assumed: [] });
        return;
      }
      if (/\.json$/i.test(p.filename)) {
        try {
          const j = JSON.parse(t);
          if (j.grid && j.stations) { setDraft({ kind: "scenario", source: "file", payload: p, scenario: j, scenarioText: JSON.stringify(j, null, 2), notes: ["Loaded as a factory plan."], missing: [], assumed: [] }); return; }
        } catch { /* fall through to Gemini */ }
      }
      if ((t.match(/#/g) ?? []).length > 6 && t.split("\n").filter((l) => l.trim()).length >= 3 && !/[a-z]{4,}/i.test(t.replace(/\s/g, "").slice(0, 400).replace(/[R F0-9#.]/g, ""))) {
        const parsed = await engine.parseAscii(t);
        const base = bench.scenarios[0]?.json;
        const sc = { name: p.filename.replace(/\.[^.]+$/, ""), ...parsed, robots: base?.robots ?? [], products: base?.products ?? [], machines: {}, events: [] };
        setDraft({ kind: "scenario", source: "file", payload: p, scenario: sc, scenarioText: JSON.stringify(sc, null, 2),
          notes: ["Map and stations read from the text drawing (# wall, . floor, R raw material, F finished goods, digits = machines)."],
          missing: ["robots", "products"], assumed: ["Robots and products were copied from the first sample plan. Edit them below."] });
        return;
      }
    }
    await convert(p, "auto");
  }

  async function convert(p: Payload, target: "auto" | "scenario" | "algorithm") {
    setBusy("Asking Gemini… (this can take a while)");
    try {
      const headers: any = { "content-type": "application/json" };
      if (access) headers["x-access-code"] = access;
      const r = await fetch("/api/convert", { method: "POST", headers, body: JSON.stringify({ target, filename: p.filename, mime: p.mime, text: p.text, imageBase64: p.imageBase64, hint }) });
      const d = await r.json();
      if (!r.ok) throw new Error(d.error || "Conversion failed.");
      if (d.kind === "scenario") setDraft({ kind: "scenario", source: "gemini", payload: p, scenario: d.scenario, scenarioText: JSON.stringify(d.scenario, null, 2), notes: d.notes, missing: d.missing, assumed: d.assumed });
      else if (d.kind === "algorithm") setDraft({ kind: "algorithm", source: "gemini", payload: p, code: d.code, algoKind: d.algorithm_kind, faithful: d.faithful, notes: d.notes, missing: d.missing, assumed: d.assumed });
      else setMsg({ tone: "warn", text: (d.notes ?? []).join(" ") || "Nothing could be converted." });
    } catch (e: any) { setMsg({ tone: "bad", text: String(e.message || e) }); }
    setBusy("");
  }

  const libs = bench.library;
  return (
    <div className="import">
      <div className="panel">
        <h3>Import an algorithm or a factory plan</h3>
        <p className="hint">Drop a file: Python, JSON, a text drawing of the map, pseudocode, or a screenshot / photo. Clean formats are read directly. Everything else is converted by Gemini, and <b>you review the result before anything is saved</b>.</p>
        <div className="drop" onDragOver={(e) => e.preventDefault()} onDrop={(e) => { e.preventDefault(); onFiles(e.dataTransfer.files); }} onClick={() => input.current?.click()} role="button" tabIndex={0}
          onKeyDown={(e) => { if (e.key === "Enter") input.current?.click(); }}>
          Drop a file here or click to choose
          <input ref={input} type="file" hidden onChange={(e) => onFiles(e.target.files)} aria-label="Upload file" />
        </div>
        <div className="row wrap">
          <label className="param grow"><span>Hint for the converter (optional)</span><input type="text" value={hint} placeholder="e.g. this is the factory floor, grid cell = 1 m" onChange={(e) => setHint(e.target.value)} /></label>
        </div>
        <div className="row wrap small">
          <span className={"chip " + (gem?.configured ? "ready" : "loading")}>Gemini: {gem === null ? "unknown" : gem.configured ? "configured (" + gem.model + ")" : "not configured"}</span>
          {gem?.accessCodeRequired && <label className="param"><span>access code</span><input type="password" value={access} onChange={(e) => { setAccess(e.target.value); try { sessionStorage.setItem(ACCESS_KEY, e.target.value); } catch { /* ignore */ } }} /></label>}
          {gem && !gem.configured && <span className="hint">Set GEMINI_API_KEY and GEMINI_MODEL on the server. Python, JSON and text maps still work without it.</span>}
        </div>
        {busy && <div className="note">{busy}</div>}
        {msg && <div className={"note " + msg.tone}>{msg.text}</div>}
      </div>

      {draft && <Review bench={bench} draft={draft} setDraft={setDraft} convert={convert} onDone={(id) => { setDraft(null); if (id) onUseScenario(id); setMsg({ tone: "ok", text: "Saved to your library." }); }} />}

      <div className="panel">
        <h3>Your library <span className="muted">(stored in this browser only)</span></h3>
        {libs.scenarios.length + libs.algorithms.length === 0 && <div className="hint">Nothing imported yet.</div>}
        <ul className="list">
          {libs.scenarios.map((s) => <li key={s.id}>🗺 {s.name} <span className="muted">· plan · {s.origin}</span> <button className="link" onClick={() => bench.removeScenario(s.id)}>remove</button></li>)}
          {libs.algorithms.map((a) => <li key={a.id}>⚙ {a.name} <span className="muted">· {a.kind.toUpperCase()} · {a.origin}</span> <button className="link" onClick={() => bench.removeAlgorithm(a.id)}>remove</button></li>)}
        </ul>
      </div>
    </div>
  );
}

function Review({ bench, draft, setDraft, convert, onDone }: { bench: Bench; draft: Draft; setDraft: (d: Draft | null) => void; convert: (p: Payload, t: "auto" | "scenario" | "algorithm") => void; onDone: (scenarioId?: string) => void }) {
  const [issues, setIssues] = useState<any[]>([]);
  const [name, setName] = useState("");
  const [check, setCheck] = useState<any>(null);
  const [dry, setDry] = useState<any>(null);
  const [busy, setBusy] = useState(false);

  // validate the plan draft on every change
  useEffect(() => {
    if (draft.kind !== "scenario") return;
    let live = true;
    const id = setTimeout(async () => {
      try {
        const sc = JSON.parse(draft.scenarioText ?? "{}");
        const v = await engine.validateScenario(JSON.stringify(sc));
        if (live) setIssues(v);
      } catch (e: any) { if (live) setIssues([{ level: "error", msg: "JSON problem: " + e.message }]); }
    }, 300);
    return () => { live = false; clearTimeout(id); };
  }, [draft.scenarioText, draft.kind]);
  useEffect(() => { setName(draft.scenario?.name ?? draft.payload.filename.replace(/\.[^.]+$/, "")); setCheck(null); setDry(null); }, [draft.payload.filename]);

  let sc: any = null;
  if (draft.kind === "scenario") { try { sc = JSON.parse(draft.scenarioText ?? "null"); } catch { sc = null; } }

  function toggle(x: number, y: number) {
    if (!sc?.grid) return;
    const rows = sc.grid.map((r: string) => r.split(""));
    if (!rows[y]?.[x]) return;
    rows[y][x] = rows[y][x] === "#" ? "." : "#";
    const next = { ...sc, grid: rows.map((r: string[]) => r.join("")) };
    setDraft({ ...draft, scenario: next, scenarioText: JSON.stringify(next, null, 2) });
  }

  async function checkAndTry() {
    setBusy(true); setCheck(null); setDry(null);
    const label = draft.payload.filename;
    const chk = await engine.checkPlugin(draft.algoKind!, draft.code!, label);
    setCheck(chk);
    if (chk.ok) {
      try {
        const base = bench.scenarios[0]?.json;
        const req: any = { scenario: base, mode: draft.algoKind === "mrta" ? "integrated" : "integrated",
          mrta: draft.algoKind === "mrta" ? { source: draft.code, label } : { name: "greedy" },
          mapf: draft.algoKind === "mapf" ? { source: draft.code, label } : { name: "prioritized" }, options: { time_limit_s: 20 } };
        setDry(await engine.run(req));
      } catch (e: any) { setDry({ ok: false, reason: String(e.message || e) }); }
    }
    setBusy(false);
  }

  const errors = issues.filter((i) => i.level === "error");
  const origin = draft.source === "gemini" ? (draft.kind === "algorithm" && draft.faithful === false ? "LLM-generated from description" : "converted by Gemini") : "uploaded";
  return (
    <div className="panel review">
      <h3>Review: {draft.payload.filename}</h3>
      <div className="two">
        <div>
          <h4>Original</h4>
          {draft.payload.previewUrl && <img className="orig" src={draft.payload.previewUrl} alt="uploaded file" />}
          {draft.payload.text !== undefined && <pre className="orig mono">{draft.payload.text.slice(0, 6000)}</pre>}
          {draft.payload.kind === "pdf" && <div className="hint">PDF (preview not shown)</div>}
        </div>
        <div>
          <h4>{draft.kind === "scenario" ? "Factory plan draft" : "Algorithm draft"}</h4>
          {draft.notes.map((n, i) => <div key={i} className="note">{n}</div>)}
          {draft.missing.length > 0 && <div className="note warn"><b>Missing (fill in or confirm as is):</b> {draft.missing.join(", ")}</div>}
          {draft.assumed.map((n, i) => <div key={i} className="note warn">Assumed: {n}</div>)}
          {draft.kind === "algorithm" && draft.faithful === false && <div className="note warn">Gemini wrote this from a description; it may not match what the author meant. It will be labelled "LLM-generated" everywhere.</div>}

          {draft.kind === "scenario" ? (
            <>
              {sc?.grid && <><div className="hint">Click a cell to toggle wall / floor.</div><MapView scenario={sc} onCellClick={toggle} /></>}
              <textarea className="code mono" rows={14} value={draft.scenarioText} onChange={(e) => setDraft({ ...draft, scenarioText: e.target.value })} aria-label="Scenario JSON" />
              {issues.map((i, k) => <div key={k} className={"note " + (i.level === "error" ? "bad" : "warn")}>{i.level}: {i.msg}</div>)}
              {issues.length === 0 && <div className="note ok">Checks passed: stations reachable, robots valid, every product can be carried.</div>}
              <label className="param"><span>Save as</span><input type="text" value={name} onChange={(e) => setName(e.target.value)} /></label>
              <div className="row">
                <button className="btn primary" disabled={errors.length > 0 || !sc} onClick={() => { const id = bench.addScenario({ name, json: { ...sc, name }, origin, notes: draft.assumed.join(" ") }); onDone(id); }}>Confirm and save</button>
                <button className="btn" onClick={() => setDraft(null)}>Discard</button>
              </div>
            </>
          ) : (
            <>
              <label className="param"><span>Slot</span>
                <select value={draft.algoKind} onChange={(e) => setDraft({ ...draft, algoKind: e.target.value as any })}><option value="mrta">MRTA (Sambhav)</option><option value="mapf">MAPF (Samyak)</option></select></label>
              <textarea className="code mono" rows={16} value={draft.code} onChange={(e) => setDraft({ ...draft, code: e.target.value })} aria-label="Algorithm source" />
              <div className="row">
                <button className="btn" disabled={busy} onClick={checkAndTry}>{busy ? "Checking…" : "Check contract + dry run"}</button>
                {draft.source === "file" && draft.payload.text !== undefined && <button className="btn" onClick={() => convert(draft.payload, "algorithm")}>Adapt with Gemini</button>}
              </div>
              {check && <div className={"note " + (check.ok ? "ok" : "bad")}>{check.ok ? "Contract OK: " + check.info.name : check.error}</div>}
              {dry && <div className={"note " + (dry.ok ? "ok" : "bad")}>{dry.ok ? `Dry run on the first sample plan: valid, makespan ${dry.makespan}, collisions ${dry.metrics?.collisions}.` : "Dry run failed: " + (dry.reason || (dry.issues?.[0] && dry.issues[0].type) || "invalid result")}</div>}
              <div className="note warn">This code runs only inside a background worker in your browser, with no network access. Still, read it before you confirm.</div>
              <div className="row">
                <button className="btn primary" disabled={!check?.ok || !dry} onClick={() => { bench.addAlgorithm({ kind: draft.algoKind!, name: check.info.name, label: draft.payload.filename, source: draft.code!, origin, notes: check.info.description, paramsSpec: check.info.params }); onDone(); }}>Confirm and save</button>
                <button className="btn" onClick={() => setDraft(null)}>Discard</button>
              </div>
              {check?.ok && dry && !dry.ok && <div className="hint">You can still save an algorithm whose dry run was invalid: the bench will mark its results as invalid.</div>}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
