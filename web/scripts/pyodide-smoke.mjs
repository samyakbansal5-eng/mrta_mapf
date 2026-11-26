// Runs the Python engine inside Pyodide (the same runtime the browser uses) and checks the results.
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { loadPyodide } from "pyodide";

const here = path.dirname(fileURLToPath(import.meta.url));
const pub = path.join(here, "..", "public");
const t0 = Date.now();
const py = await loadPyodide();
console.log(`pyodide ${py.version} loaded in ${Date.now() - t0} ms`);
const manifest = JSON.parse(fs.readFileSync(path.join(pub, "bench", "manifest.json"), "utf8"));
for (const f of manifest.files) {
  const dest = "/home/pyodide/bench/" + f;
  py.FS.mkdirTree(path.posix.dirname(dest));
  py.FS.writeFile(dest, fs.readFileSync(path.join(pub, "bench", f), "utf8"));
}
py.runPython("import sys; sys.path.insert(0, '/home/pyodide')");
const api = py.pyimport("bench.core.api");
const scen = (n) => JSON.parse(fs.readFileSync(path.join(pub, "scenarios", n + ".json"), "utf8"));
let failed = 0;
function check(name, cond, extra = "") { console.log((cond ? "PASS " : "FAIL ") + name + " " + extra); if (!cond) failed++; }

for (const [sc, mrta, mapf] of [["small_factory", "greedy", "prioritized"], ["small_factory", "genetic", "cbs"],
                                ["small_factory_events", "tabu", "prioritized"], ["small_factory", "greedy", "independent"]]) {
  const t = Date.now();
  const r = JSON.parse(api.run_json(JSON.stringify({ scenario: scen(sc), mrta: { name: mrta }, mapf: { name: mapf }, options: { time_limit_s: 120 } })));
  const expectOk = mapf !== "independent";
  check(`${sc} ${mrta}+${mapf}`, r.ok === expectOk && (expectOk ? r.metrics.collisions === 0 : r.metrics.collisions > 0),
        `ok=${r.ok} makespan=${r.makespan} collisions=${r.metrics?.collisions} ${Date.now() - t} ms`);
}
// algorithms added from the literature shortlist, on the busier sample factory
for (const mapf of ["pibt", "lacam", "lns2", "eecbs", "pbs", "rhcr", "traffic_flow", "adg"]) {
  const t = Date.now();
  const r = JSON.parse(api.run_json(JSON.stringify({ scenario: scen("busy_factory"), mrta: { name: "greedy" }, mapf: { name: mapf }, options: { time_limit_s: 120 } })));
  check(`busy_factory greedy+${mapf}`, r.ok && r.metrics.collisions === 0, `makespan=${r.makespan} ${Date.now() - t} ms ${r.reason ?? ""}`);
}
for (const mrta of ["rmca", "tessi", "bischoff", "hmr_odta", "kalempa", "calvo", "ta_hybrid", "tercio", "meng_ga", "sun_ga"]) {
  const t = Date.now();
  const r = JSON.parse(api.run_json(JSON.stringify({ scenario: scen("busy_factory"), mrta: { name: mrta }, mapf: { name: "pbs" }, options: { time_limit_s: 120 } })));
  check(`busy_factory ${mrta}+pbs`, r.ok && r.metrics.collisions === 0, `makespan=${r.makespan} ${Date.now() - t} ms ${r.reason ?? ""}`);
}
const cat = JSON.parse(api.catalogue_json());
check("catalogue", cat.mrta.length === 14 && cat.mapf.length === 11 && [...cat.mrta, ...cat.mapf].every((i) => i.papers?.length && i.about));
process.exit(failed ? 1 : 0);
