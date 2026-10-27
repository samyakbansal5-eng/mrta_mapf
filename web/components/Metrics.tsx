"use client";
import { fmt } from "@/lib/viz";

export default function Metrics({ result, only }: { result: any; only?: "mrta" | "mapf" }) {
  if (!result) return null;
  const m = result.metrics ?? {};
  const cards: [string, any, string?][] = only === "mrta"
    ? [["Makespan", m.makespan], ["Tasks done", `${fmt(m.tasks_done)} / ${fmt(m.tasks_total)}`], ["Runtime", fmt(m.runtime_ms) + " ms"]]
    : only === "mapf"
      ? [["Collisions", m.collisions, m.collisions ? "bad" : "good"], ["Rule violations", m.rule_violations, m.rule_violations ? "bad" : "good"], ["Moves", m.moves], ["Waits", m.waits], ["Replans", m.replans], ["Runtime", fmt(m.runtime_ms) + " ms"]]
      : [["Makespan", m.makespan], ["Tasks done", `${fmt(m.tasks_done)} / ${fmt(m.tasks_total)}`], ["Collisions", m.collisions, m.collisions ? "bad" : "good"], ["Waits", m.waits], ["Replans", m.replans], ["Rounds", m.rounds], ["Runtime", fmt(m.runtime_ms) + " ms"]];
  return (
    <div>
      <div className={"status " + (result.ok ? "ok" : "bad")}>
        {result.ok ? "✓ Valid plan" : "✗ Not a valid plan"}{result.reason ? ": " + result.reason : ""}
        {result.algorithms && <span className="muted"> · MRTA: {result.algorithms.mrta}{result.algorithms.mapf ? " · MAPF: " + result.algorithms.mapf : ""}</span>}
      </div>
      <div className="cards">
        {cards.map(([k, v, tone]) => (
          <div key={k} className={"card " + (tone ?? "")}><div className="k">{k}</div><div className="v">{fmt(v)}</div></div>
        ))}
      </div>
      {(result.warnings ?? []).map((w: string) => <div key={w} className="note warn">⚠ {w}</div>)}
    </div>
  );
}

export function Issues({ result }: { result: any }) {
  const issues: any[] = result?.issues ?? [];
  if (!issues.length) return null;
  return (
    <details open className="box">
      <summary>{issues.length} rule violation(s)</summary>
      <ul className="list mono">
        {issues.slice(0, 40).map((i, k) => <li key={k}>{i.type}{i.robots ? " " + i.robots.join("/") : ""}{i.task ? " " + i.task : ""}{i.t !== undefined ? " at t=" + i.t : ""}{i.cell ? " " + JSON.stringify(i.cell) : ""}</li>)}
      </ul>
    </details>
  );
}

export function LogBox({ result }: { result: any }) {
  const log: string[] = result?.log ?? [];
  const rounds: any[] = result?.rounds ?? [];
  if (!log.length && !rounds.length) return null;
  return (
    <details className="box">
      <summary>Event log and planning rounds</summary>
      {log.length > 0 && <ul className="list">{log.map((l, i) => <li key={i}>{l}</li>)}</ul>}
      {rounds.length > 0 && (
        <table className="table mono">
          <thead><tr><th>segment</th><th>round</th><th>planned</th><th>actual</th><th>collisions</th><th>early departures</th><th>MAPF note</th></tr></thead>
          <tbody>{rounds.map((r, i) => <tr key={i}><td>{r.segment}</td><td>{r.round}</td><td>{fmt(r.planned_makespan)}</td><td>{fmt(r.actual_makespan)}</td><td>{fmt(r.collisions)}</td><td>{fmt(r.early_departures)}</td><td>{r.note}</td></tr>)}</tbody>
        </table>
      )}
    </details>
  );
}
