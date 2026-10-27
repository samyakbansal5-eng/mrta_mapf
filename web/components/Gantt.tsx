"use client";
import { maxTime, productColor } from "@/lib/viz";

export default function Gantt({ scenario, result, t }: { scenario: any; result: any; t?: number }) {
  const tl: any[] = result?.timeline ?? [];
  if (!tl.length) return <div className="empty">No schedule yet. Run something.</div>;
  const robots: string[] = scenario.robots.map((r: any) => r.id);
  const machines: string[] = Object.keys(scenario.stations).filter((s) => tl.some((e) => e.machine?.name === s));
  const rows = [...robots.map((r) => ({ id: r, kind: "robot" })), ...machines.map((m) => ({ id: m, kind: "machine" }))];
  const T = Math.max(1, maxTime(result));
  const LEFT = 52, ROW = 26, TOP = 22, WIDTH = 900;
  const x = (v: number) => LEFT + (v / T) * (WIDTH - LEFT - 10);
  const H = TOP + rows.length * ROW + 8;
  const step = T > 120 ? 20 : T > 60 ? 10 : 5;
  const ticks: number[] = [];
  for (let v = 0; v <= T; v += step) ticks.push(v);
  const bar = (key: string, row: number, a: number, b: number, fill: string, label?: string, extra: any = {}) => (
    <g key={key}>
      <rect x={x(a)} y={TOP + row * ROW + 3} width={Math.max(1.5, x(b) - x(a))} height={ROW - 6} rx={3} fill={fill} {...extra} />
      {label && x(b) - x(a) > 22 && <text x={x(a) + 3} y={TOP + row * ROW + ROW / 2 + 4} fontSize="10" fill="#fff">{label}</text>}
    </g>
  );
  return (
    <svg viewBox={`0 0 ${WIDTH} ${H}`} className="gantt" role="img" aria-label="Gantt chart">
      {ticks.map((v) => (
        <g key={v}>
          <line x1={x(v)} x2={x(v)} y1={TOP - 4} y2={H - 6} stroke="var(--line)" />
          <text x={x(v)} y={12} fontSize="10" textAnchor="middle" fill="var(--muted)">{v}</text>
        </g>
      ))}
      {rows.map((r, i) => (
        <g key={r.id}>
          <text x={4} y={TOP + i * ROW + ROW / 2 + 4} fontSize="11" fontWeight={600} fill="var(--ink)">{r.id}</text>
          <line x1={LEFT} x2={WIDTH - 10} y1={TOP + (i + 1) * ROW} y2={TOP + (i + 1) * ROW} stroke="var(--line)" />
        </g>
      ))}
      {tl.flatMap((e) => {
        const color = productColor(scenario, e.product);
        const out: any[] = [];
        const ri = robots.indexOf(e.robot);
        if (ri >= 0) {
          if (e.park) out.push(bar(e.task + "p", ri, e.park.start, e.park.arrive, "var(--idle)", undefined));
          if (e.approach && e.approach.arrive > e.approach.start) out.push(bar(e.task + "a", ri, e.approach.start, e.approach.arrive, "var(--idle)", undefined));
          out.push(bar(e.task + "c", ri, e.carry.start, e.carry.arrive, color, e.task));
        }
        const mi = machines.indexOf(e.machine?.name);
        if (mi >= 0 && e.machine.end > e.machine.start) out.push(bar(e.task + "m", robots.length + mi, e.machine.start, e.machine.end, color, e.product, { opacity: 0.85 }));
        return out;
      })}
      {t !== undefined && <line x1={x(t)} x2={x(t)} y1={TOP - 4} y2={H - 6} stroke="#dc2626" strokeWidth={2} />}
    </svg>
  );
}
