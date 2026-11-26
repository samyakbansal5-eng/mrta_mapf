# Factory Bench (MRTA + MAPF)

A test bench for a heterogeneous multi-robot factory (semester project, Prof. Pranjal Vyas).

* **MRTA** (task allocation + scheduling): decides which robot carries which product, in which order.
* **MAPF** (multi-agent path finding): plans collision-free, time-stamped `(x, y, t)` routes on the factory map.
* The bench runs both together, feeds path delays back into the schedule, and replans when a robot fails or an aisle is blocked.
* Algorithms are swappable: built-ins, or your own Python file uploaded in the browser.

One app, two deliverables: the **MRTA window** (`/mrta`) and the **MAPF window** (`/mapf`) each show one module on its own; the main page shows both together.

## Status (honest)

* Working and tested: engine (114 tests), 14 MRTA algorithms and 11 MAPF algorithms (see the table below), every one documented with how it works, its supporting papers and how close it is to the paper (shown under each algorithm in the Run window), events (blocked cells, robot failure/recovery), validators, in-browser Python (Pyodide), Run/Plan editor/Import/Compare tabs, module windows.
* The sample factory (`scenarios/small_factory.json`) uses **made-up** numbers. It is not from the professor.
* The Gemini import path (`/api/convert`) is written but **not yet tested against the real API** (no key during development). Without a key it answers 501 and the deterministic importers (`.py`, `.json`, ASCII grid) still work.
* The Sambhav prototype was never available, so the MRTA side is a fresh implementation of the same idea.
* Not decided yet: official metrics, the meaning of "Direct/Indirect" in the notes, final deliverable wording.

## Algorithms and their papers

Built in from the start: MRTA greedy, auction, genetic, tabu; MAPF independent A*, prioritized, CBS.
Added from the literature shortlist (Nov 2026). "Inspired" means the core idea is kept but parts the scenario format cannot express yet (deadlines, battery, coalitions, alternative machines) are simplified; each algorithm's `fidelity` text says exactly what.

| Module | Plug-in | Paper | Closeness |
|---|---|---|---|
| MAPF | `pibt` | Okumura et al., PIBT (IJCAI 2019 / AIJ 2022) | faithful |
| MAPF | `lacam` | Okumura, LaCAM (AAAI 2023) | core loop |
| MAPF | `lns2` | Li et al., MAPF-LNS2 (AAAI 2022) | simplified low level |
| MAPF | `eecbs` | Li, Ruml, Koenig, EECBS (AAAI 2021) | focal search only |
| MAPF | `pbs` | Ma et al., PBS (AAAI 2019) | faithful |
| MAPF | `rhcr` | Li et al., RHCR (AAAI 2021) | windowed prioritized |
| MAPF | `traffic_flow` | Chen et al., Traffic Flow Optimisation (AAAI 2024) | simplified |
| MAPF | `adg` | Hönig et al., Action Dependency Graph (RA-L 2019) | execution rule |
| MRTA | `rmca` | Chen et al., RMCA (RA-L 2021) | faithful insertion + LNS |
| MRTA | `tessi` | Nunes & Gini, TeSSI (AAAI 2015) | faithful bids |
| MRTA | `bischoff` | Bischoff et al. (SMC 2020) | no cooperative tasks |
| MRTA | `hmr_odta` | Verma et al., HMR-ODTA (arXiv 2025) | inspired |
| MRTA | `kalempa` | Kalempa et al., MRPF (Sensors 2021) | inspired |
| MRTA | `calvo` | Calvo & Capitán (T-RO 2025) | inspired |
| MRTA | `ta_hybrid` | Liu et al., TA-Hybrid (AAMAS 2019) | simplified TSP |
| MRTA | `tercio` | Gombolay et al., Tercio (T-RO 2018) | inspired |
| MRTA | `meng_ga` | Meng et al. (Sensors 2023) | faithful minus machine choice |
| MRTA | `sun_ga` | Sun et al. (Sensors 2023) | inspired |

Not implemented (read for related work): CCBS continuous-time MAPF and windowed MAPF with completeness guarantees (too large for now), and learning-based schedulers (need trained networks).

A third sample, `scenarios/busy_factory.json` (6 robots, 6 products, a blocked aisle), shows the differences between the planners better than the small sample.

## Layout

```
python/bench/core      grid, scenario, tasks, schedule, validators, orchestrator, plug-in loader
python/bench/mrta      greedy, auction, genetic, tabu + 10 from papers (_seq.py = shared sequence helpers)
python/bench/mapf      lowlevel (space-time A*), stepwise (PIBT core), independent, prioritized, cbs + 8 from papers
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

## Making Gemini work

1. Get a key: Google AI Studio (aistudio.google.com) > Get API key. The free tier is enough for a few conversions a day.
2. Pick a model id from the AI Studio model list (a current "Flash" model is fast and cheap; a "Pro" model reads long PDFs better).
3. Locally: put `GEMINI_API_KEY=...` and `GEMINI_MODEL=...` in `web/.env.local`, restart `npm run dev`. On Vercel: Project > Settings > Environment Variables, then Redeploy.
4. Check: the Import tab chip turns to "Gemini: configured (model)". Choose "Treat my upload as: Algorithm", optionally the slot, and drop the file.

Limits: PDF under 3 MB, Gemini must answer within 60 s (`maxDuration` in `web/app/api/convert/route.ts`).

## Deploy on Vercel

1. Vercel dashboard > Add New > Project > import this GitHub repo.
2. **Root Directory: `web`**. Framework: Next.js (auto-detected).
3. Add the environment variables above, then Deploy.

## Editing a factory plan

Open the **Plan editor** tab, pick a plan and press *Edit a copy* (samples are never changed) or *Blank plan*. You can:

* add / remove / rename robots, set start cell, speed (steps per cell), payload and which products each may carry;
* add / remove / rename / move machines (renames update every route), and give them a type label;
* add / remove / duplicate products (job profiles) and build each route step by step with process times;
* add events: blocked aisle (with an end time), robot failure, robot recovery;
* toggle walls, move stations and robot starts by clicking the map, and grow or shrink the map.

The same Python checks the run uses validate the plan live; errors block saving, warnings do not. Saved plans go to the browser library and appear in the Run tab. Not modelled yet: deadlines, release times, quantities, machine capacity above 1, machine types used by algorithms.

Editor helper tests: `cd web && npm run test:editor`.

## Your own algorithm

Copy a file from `plugins-examples/`, edit it, upload it in **Import**. One file = an `INFO` dict + `allocate(...)` (MRTA) or `plan(...)` (MAPF). Uploaded code runs only in a Web Worker in the visitor's browser with network access blocked by the page's CSP, under a soft time limit and a hard stop button.

## Model assumptions (to confirm)

Whole time steps; a robot with step cost `k` needs `k` steps per cell; conflicts = same cell at the same time, or swapping cells (following is allowed); a robot with no work left leaves the floor; a failed robot stays as an obstacle.
