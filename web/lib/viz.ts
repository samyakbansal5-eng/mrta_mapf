export const PALETTE = ["#2563eb", "#d97706", "#059669", "#9333ea", "#dc2626", "#0891b2", "#be185d", "#4d7c0f"];

export function productColor(scenario: any, product: string) {
  const i = Math.max(0, (scenario?.products ?? []).findIndex((p: any) => p.id === product));
  return PALETTE[i % PALETTE.length];
}

export function robotColor(scenario: any, rid: string) {
  const i = Math.max(0, (scenario?.robots ?? []).findIndex((r: any) => r.id === rid));
  return PALETTE[(i + 3) % PALETTE.length];
}

/** Position of every robot run (R1, R1#2 ...) at time t, or absent when it is off the floor. */
export function positionsAt(result: any, t: number): { id: string; x: number; y: number }[] {
  const out: { id: string; x: number; y: number }[] = [];
  for (const [key, pts] of Object.entries<any>(result?.paths ?? {})) {
    if (!pts.length) continue;
    const t0 = pts[0][2];
    const last = pts[pts.length - 1][2];
    if (t >= t0 && t <= last) {
      const p = pts[t - t0];
      out.push({ id: key.split("#")[0], x: p[0], y: p[1] });
    }
  }
  return out;
}

export function maxTime(result: any): number {
  let m = result?.makespan ?? 0;
  for (const pts of Object.values<any>(result?.paths ?? {})) if (pts.length) m = Math.max(m, pts[pts.length - 1][2]);
  return m;
}

export function fmt(n: number | undefined | null) {
  return n === undefined || n === null ? "–" : String(n);
}
