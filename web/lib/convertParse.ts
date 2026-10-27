// Parsing of Gemini's answer (kept out of the route file: Next.js routes may only export handlers).
export function parseModelJson(raw: string): any | null {
  const cleaned = raw.replace(/^```(?:json)?\s*/i, "").replace(/\s*```$/, "");
  try { const v = JSON.parse(cleaned); return v && typeof v === "object" ? v : null; } catch { return null; }
}

function list(v: any): string[] { return Array.isArray(v) ? v.map(String).slice(0, 50) : []; }

export function normalize(p: any) {
  const base = { missing: list(p.missing), assumed: list(p.assumed), notes: list(p.notes) };
  if (p.kind === "algorithm" && typeof p.code === "string") {
    return { kind: "algorithm", algorithm_kind: p.algorithm_kind === "mapf" ? "mapf" : "mrta", code: p.code, faithful: p.faithful !== false, ...base };
  }
  if (p.kind === "scenario" && p.scenario && typeof p.scenario === "object") return { kind: "scenario", scenario: p.scenario, ...base };
  return { kind: "none", ...base, notes: [...base.notes, "Gemini found nothing it could convert."] };
}
