# Factory Bench (MRTA + MAPF)

A test bench for a heterogeneous multi-robot factory (semester project, Prof. Pranjal Vyas).

* **MRTA** (task allocation + scheduling): decides which robot carries which product, in which order.
* **MAPF** (multi-agent path finding): plans collision-free, time-stamped `(x, y, t)` routes on the factory map.
* The bench runs both together, feeds path delays back into the schedule, and replans when a robot fails or an aisle is blocked.
* Algorithms are swappable: built-ins, or your own Python file uploaded in the browser.

One app, two deliverables: the **MRTA window** (`/mrta`) and the **MAPF window** (`/mapf`) each show one module on its own; the main page shows both together.

## Status (honest)

* Working and tested: engine (33 tests), 4 MRTA algorithms (greedy, auction, genetic, tabu), 3 MAPF algorithms (independent baseline, prioritized, CBS with fallback), events (blocked cells, robot failure/recovery), validators, in-browser Python (Pyodide), Run/Import/Compare tabs, module windows.
* The sample factory (`scenarios/small_factory.json`) uses **made-up** numbers. It is not from the professor.
* The Gemini import path (`/api/convert`) is written but **not yet tested against the real API** (no key during development). Without a key it answers 501 and the deterministic importers (`.py`, `.json`, ASCII grid) still work.
* The Sambhav prototype was never available, so the MRTA side is a fresh implementation of the same idea.
* Not decided yet: official metrics, the meaning of "Direct/Indirect" in the notes, final deliverable wording.

## Layout

```
python/bench/core      grid, scenario, tasks, schedule, validators, orchestrator, plug-in loader
python/bench/mrta      greedy, auction, genetic, tabu
python/bench/mapf      lowlevel (space-time A*), independent, prioritized, cbs
python/tests           pytest suite
scenarios/             sample factory + events
plugins-examples/      templates to copy for your own MRTA / MAPF algorithm
web/                   Next.js app (UI, Gemini route, Pyodide worker)
```

## Run locally

```bash
cd python && python3 -m pip install pytest && python3 -m pytest -q   # engine tests
cd ../web && npm install && cp .env.example .env.local
npm run dev                                                          # http://localhost:3000
```

`npm run dev/build` first copies the Python engine and the Pyodide runtime into `web/public/` (git-ignored), so the browser loads everything from your own domain.

## Environment variables (set in Vercel, never in the repo)

| name | purpose |
|---|---|
| `GEMINI_API_KEY` | your Gemini key (server only) |
| `GEMINI_MODEL` | model id you want to use, e.g. the one shown in Google AI Studio |
| `APP_ACCESS_CODE` | optional; if set, converting uploads needs this code |

## Deploy on Vercel

1. Vercel dashboard > Add New > Project > import this GitHub repo.
2. **Root Directory: `web`**. Framework: Next.js (auto-detected).
3. Add the environment variables above, then Deploy.

## Your own algorithm

Copy a file from `plugins-examples/`, edit it, upload it in **Import**. One file = an `INFO` dict + `allocate(...)` (MRTA) or `plan(...)` (MAPF). Uploaded code runs only in a Web Worker in the visitor's browser with network access blocked by the page's CSP, under a soft time limit and a hard stop button.

## Model assumptions (to confirm)

Whole time steps; a robot with step cost `k` needs `k` steps per cell; conflicts = same cell at the same time, or swapping cells (following is allowed); a robot with no work left leaves the floor; a failed robot stays as an obstacle.
