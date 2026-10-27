"use client";
import { useEffect, useState } from "react";

export function usePlayback(maxT: number) {
  const [t, setT] = useState(0);
  const [playing, setPlaying] = useState(false);
  useEffect(() => { setT(0); setPlaying(false); }, [maxT]);
  useEffect(() => {
    if (!playing) return;
    const id = setInterval(() => setT((v) => { if (v >= maxT) { setPlaying(false); return v; } return v + 1; }), 160);
    return () => clearInterval(id);
  }, [playing, maxT]);
  return { t, setT, playing, setPlaying };
}

export default function Playback({ maxT, t, setT, playing, setPlaying }: { maxT: number; t: number; setT: (n: number) => void; playing: boolean; setPlaying: (b: boolean) => void }) {
  return (
    <div className="playback">
      <button className="btn small" onClick={() => setPlaying(!playing)} aria-label={playing ? "Pause" : "Play"}>{playing ? "❚❚" : "▶"}</button>
      <input type="range" min={0} max={Math.max(1, maxT)} value={t} onChange={(e) => { setPlaying(false); setT(Number(e.target.value)); }} aria-label="Time" />
      <span className="mono">t = {t} / {maxT}</span>
    </div>
  );
}
