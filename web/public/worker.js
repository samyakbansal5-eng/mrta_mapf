/* Web Worker: runs the Python engine (Pyodide) off the page's main thread.
 * Uploaded algorithms run only in here. The page's Content-Security-Policy blocks all network
 * access except to our own origin, and the page can terminate this worker at any time. */
let api = null;
const ready = (async () => {
  importScripts("/pyodide/pyodide.js");
  const py = await loadPyodide({ indexURL: "/pyodide/" });
  const manifest = await (await fetch("/bench/manifest.json")).json();
  for (const f of manifest.files) {
    const text = await (await fetch("/bench/" + f)).text();
    const dest = "/home/pyodide/bench/" + f;
    py.FS.mkdirTree(dest.substring(0, dest.lastIndexOf("/")));
    py.FS.writeFile(dest, text);
  }
  py.runPython("import sys; sys.path.insert(0, '/home/pyodide')");
  api = py.pyimport("bench.core.api");
  return py.version;
})();

self.onmessage = async (e) => {
  const { id, type, args } = e.data;
  try {
    const version = await ready;
    let out;
    if (type === "hello") out = JSON.stringify({ pyodide: version });
    else if (type === "catalogue") out = api.catalogue_json();
    else if (type === "run") out = api.run_json(args[0]);
    else if (type === "checkPlugin") out = api.check_plugin_json(args[0], args[1], args[2]);
    else if (type === "validateScenario") out = api.validate_scenario_json(args[0]);
    else if (type === "parseAscii") out = api.parse_ascii_json(args[0], args[1] || "{}");
    else throw new Error("unknown request " + type);
    self.postMessage({ id, ok: true, data: JSON.parse(out) });
  } catch (err) {
    self.postMessage({ id, ok: false, error: String(err && err.message ? err.message : err) });
  }
};
