"use client";
import { useEffect, useRef } from "react";
import { positionsAt, robotColor } from "@/lib/viz";

type Props = {
  scenario: any;
  result?: any;
  t?: number;
  onCellClick?: (x: number, y: number) => void;   // grid editing (import review)
};

export default function MapView({ scenario, result, t = 0, onCellClick }: Props) {
  const ref = useRef<HTMLCanvasElement>(null);
  const grid: string[] = scenario?.grid ?? [];
  const W = grid[0]?.length ?? 0;
  const H = grid.length;
  const CELL = 34;

  useEffect(() => {
    const c = ref.current;
    if (!c || !W || !H) return;
    const dpr = window.devicePixelRatio || 1;
    c.width = W * CELL * dpr; c.height = H * CELL * dpr;
    const g = c.getContext("2d")!;
    g.setTransform(dpr, 0, 0, dpr, 0, 0);
    const css = getComputedStyle(document.documentElement);
    const col = (n: string, d: string) => css.getPropertyValue(n).trim() || d;
    const floor = col("--map-floor", "#f4f1ea"), wall = col("--map-wall", "#3b3f46"), ink = col("--ink", "#111");
    g.clearRect(0, 0, W * CELL, H * CELL);
    for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) {
      g.fillStyle = grid[y][x] === "#" ? wall : floor;
      g.fillRect(x * CELL, y * CELL, CELL, CELL);
      g.strokeStyle = "rgba(0,0,0,0.07)"; g.strokeRect(x * CELL, y * CELL, CELL, CELL);
    }
    // blocked aisles at time t
    for (const b of result?.events?.blocked ?? []) {
      if (t >= b.from && (b.until == null || t < b.until)) for (const [x, y] of b.cells) {
        g.fillStyle = "rgba(220,38,38,0.35)"; g.fillRect(x * CELL, y * CELL, CELL, CELL);
        g.strokeStyle = "#dc2626"; g.lineWidth = 2;
        g.beginPath(); g.moveTo(x * CELL + 4, y * CELL + 4); g.lineTo((x + 1) * CELL - 4, (y + 1) * CELL - 4);
        g.moveTo((x + 1) * CELL - 4, y * CELL + 4); g.lineTo(x * CELL + 4, (y + 1) * CELL - 4); g.stroke(); g.lineWidth = 1;
      }
    }
    // stations
    g.font = "bold 11px system-ui, sans-serif"; g.textAlign = "center"; g.textBaseline = "middle";
    for (const [name, [x, y]] of Object.entries<any>(scenario.stations ?? {})) {
      g.fillStyle = name === "RM" ? "#0f766e" : name === "FG" ? "#4338ca" : "#b45309";
      g.globalAlpha = 0.9; g.fillRect(x * CELL + 3, y * CELL + 3, CELL - 6, CELL - 6); g.globalAlpha = 1;
      g.fillStyle = "#fff"; g.fillText(name, x * CELL + CELL / 2, y * CELL + CELL / 2);
    }
    // trails and robots
    for (const [key, pts] of Object.entries<any>(result?.paths ?? {})) {
      const id = key.split("#")[0];
      g.strokeStyle = robotColor(scenario, id); g.globalAlpha = 0.45; g.lineWidth = 3; g.beginPath();
      let started = false;
      for (const [x, y, tt] of pts) {
        if (tt > t) break;
        const px = x * CELL + CELL / 2 + (robotOffset(scenario, id)), py = y * CELL + CELL / 2 + robotOffset(scenario, id);
        if (!started) { g.moveTo(px, py); started = true; } else g.lineTo(px, py);
      }
      g.stroke(); g.globalAlpha = 1; g.lineWidth = 1;
    }
    for (const [rid, f] of Object.entries<any>(result?.events?.failed ?? {})) {
      if (t >= f.from && (f.until == null || t < f.until)) {
        const [x, y] = f.cell;
        g.fillStyle = "#111"; g.beginPath(); g.arc(x * CELL + CELL / 2, y * CELL + CELL / 2, CELL / 2 - 4, 0, 7); g.fill();
        g.fillStyle = "#fca5a5"; g.fillText("✕ " + rid, x * CELL + CELL / 2, y * CELL + CELL / 2);
      }
    }
    for (const r of positionsAt(result, t)) {
      g.fillStyle = robotColor(scenario, r.id);
      g.beginPath(); g.arc(r.x * CELL + CELL / 2, r.y * CELL + CELL / 2, CELL / 2 - 5, 0, 7); g.fill();
      g.strokeStyle = "#fff"; g.lineWidth = 2; g.stroke(); g.lineWidth = 1;
      g.fillStyle = "#fff"; g.fillText(r.id, r.x * CELL + CELL / 2, r.y * CELL + CELL / 2);
    }
    void ink;
  }, [scenario, result, t, W, H, grid]);

  if (!W || !H) return <div className="empty">No map loaded.</div>;
  return (
    <canvas
      ref={ref}
      className="map"
      style={{ width: "100%", maxWidth: W * CELL, aspectRatio: `${W} / ${H}`, cursor: onCellClick ? "crosshair" : "default" }}
      onClick={(e) => {
        if (!onCellClick) return;
        const r = e.currentTarget.getBoundingClientRect();
        const x = Math.floor(((e.clientX - r.left) / r.width) * W), y = Math.floor(((e.clientY - r.top) / r.height) * H);
        onCellClick(x, y);
      }}
      role="img"
      aria-label="Factory map"
    />
  );
}

function robotOffset(scenario: any, id: string) {
  const i = Math.max(0, (scenario?.robots ?? []).findIndex((r: any) => r.id === id));
  return (i - 1) * 3;
}
