// Copies the Python engine, sample scenarios, plug-in examples and the Pyodide runtime into public/
// so the browser can load everything from our own domain (no third-party CDN).
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const web = path.join(here, "..");
const repo = path.join(web, "..");
const pub = path.join(web, "public");

function rmrf(p) { fs.rmSync(p, { recursive: true, force: true }); }
function walk(dir, base = dir, out = []) {
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, e.name);
    if (e.isDirectory()) { if (e.name !== "__pycache__") walk(full, base, out); }
    else if (e.name.endsWith(".py")) out.push(path.relative(base, full).split(path.sep).join("/"));
  }
  return out.sort();
}

// Python engine
const src = path.join(repo, "python", "bench");
const dst = path.join(pub, "bench");
rmrf(dst);
const files = walk(src);
for (const f of files) {
  fs.mkdirSync(path.dirname(path.join(dst, f)), { recursive: true });
  fs.copyFileSync(path.join(src, f), path.join(dst, f));
}
fs.writeFileSync(path.join(dst, "manifest.json"), JSON.stringify({ files }, null, 1));

// Scenarios and examples
for (const [dirName, ext] of [["scenarios", ".json"], ["plugins-examples", ".py"]]) {
  const from = path.join(repo, dirName);
  const to = path.join(pub, dirName);
  rmrf(to);
  fs.mkdirSync(to, { recursive: true });
  const names = fs.existsSync(from) ? fs.readdirSync(from).filter((n) => n.endsWith(ext)).sort() : [];
  for (const n of names) fs.copyFileSync(path.join(from, n), path.join(to, n));
  fs.writeFileSync(path.join(to, "index.json"), JSON.stringify(names));
}

// Pyodide runtime (self-hosted)
const py = path.join(web, "node_modules", "pyodide");
const pyDst = path.join(pub, "pyodide");
rmrf(pyDst);
fs.mkdirSync(pyDst, { recursive: true });
for (const f of ["pyodide.js", "pyodide.asm.mjs", "pyodide.asm.wasm", "python_stdlib.zip", "pyodide-lock.json"]) {
  fs.copyFileSync(path.join(py, f), path.join(pyDst, f));
}
console.log(`synced ${files.length} python files, pyodide ${JSON.parse(fs.readFileSync(path.join(py, "package.json"))).version}`);
