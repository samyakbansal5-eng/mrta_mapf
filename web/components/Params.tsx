"use client";

export default function Params({ info, values, onChange }: { info: any; values: any; onChange: (v: any) => void }) {
  const spec = info?.params ?? {};
  const keys = Object.keys(spec);
  if (!keys.length) return null;
  return (
    <div className="params">
      {keys.map((k) => {
        const p = spec[k];
        const v = values?.[k] ?? p.default;
        return (
          <label key={k} className="param">
            <span>{k.replace(/_/g, " ")}</span>
            {p.type === "choice" ? (
              <select value={v} onChange={(e) => onChange({ ...values, [k]: e.target.value })}>
                {p.options.map((o: string) => <option key={o}>{o}</option>)}
              </select>
            ) : (
              <input type="number" value={v} min={p.min} max={p.max} step={p.type === "float" ? 0.05 : 1}
                onChange={(e) => onChange({ ...values, [k]: p.type === "float" ? parseFloat(e.target.value) : parseInt(e.target.value || "0", 10) })} />
            )}
          </label>
        );
      })}
    </div>
  );
}
