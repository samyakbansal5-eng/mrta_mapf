"use client";
import { useState } from "react";
import RunTab, { useRunSettings } from "@/components/RunTab";
import ImportTab from "@/components/ImportTab";
import CompareTab from "@/components/CompareTab";
import { useBench } from "@/lib/useBench";

const TABS = [["run", "Run"], ["import", "Import"], ["compare", "Compare"], ["about", "About"]] as const;

export default function Home() {
  const [tab, setTab] = useState<(typeof TABS)[number][0]>("run");
  const bench = useBench();
  const settings = useRunSettings(bench);
  return (
    <div className="shell">
      <header className="top">
        <h1>Factory Bench</h1>
        <nav role="tablist">
          {TABS.map(([id, label]) => <button key={id} role="tab" aria-selected={tab === id} className={"tab " + (tab === id ? "on" : "")} onClick={() => setTab(id)}>{label}</button>)}
        </nav>
        <span className={"chip " + bench.engineState}>{bench.engineState === "ready" ? "engine ready · " + bench.engineMsg : bench.engineState === "loading" ? "loading Python engine…" : "engine error: " + bench.engineMsg}</span>
      </header>
      {tab === "run" && <RunTab bench={bench} settings={settings} />}
      {tab === "import" && <ImportTab bench={bench} onUseScenario={(id) => { settings.setScenId(id); setTab("run"); }} />}
      {tab === "compare" && <CompareTab bench={bench} />}
      {tab === "about" && <About />}
    </div>
  );
}

function About() {
  return (
    <div className="about panel">
      <h3>What this is</h3>
      <p>A test bench for a heterogeneous multi-robot factory. <b>MRTA</b> (Sambhav) decides which robot carries which product and when. <b>MAPF</b> (Samyak) plans collision-free robot routes on the factory map. The bench runs them together, feeds delays from the paths back into the schedule, and replans when a robot fails or an aisle is blocked.</p>
      <h3>Two deliverables, one bench</h3>
      <p>Open the <b>MRTA window</b> or the <b>MAPF window</b> from the Run tab: each shows one module on its own, with its own algorithm picker and metrics. The Run tab shows both together.</p>
      <h3>Your own algorithms</h3>
      <p>An algorithm is one Python file with an <code>INFO</code> dict and one function (see <code>plugins-examples/</code>). Upload it in the Import tab, then pick it in the dropdowns. Uploaded code runs only inside a background Web Worker in your browser, with the page's network access blocked, and can be stopped at any time. Files that are not in the right shape (pseudocode, a screenshot, a different function signature) can be converted by Gemini; you review the result first.</p>
      <h3>Model assumptions (to confirm with the professor)</h3>
      <ul className="list">
        <li>Time moves in whole steps; a robot with step cost k needs k steps per cell.</li>
        <li>Conflicts checked: two robots on one cell at one time, and two robots swapping cells. Following is allowed.</li>
        <li>A robot with no remaining work leaves the floor. Idle robots wait in their parking bay (their start cell).</li>
        <li>A failed robot stays on its cell as an obstacle; a product it carried can be taken over from that cell.</li>
        <li>The sample factory, speeds, payloads and process times are made-up sample values, not given by the professor.</li>
      </ul>
    </div>
  );
}
