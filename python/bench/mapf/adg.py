INFO = {
    "name": "Robust execution with an Action Dependency Graph",
    "module": "mapf",
    "description": "Plans with a chosen solver, then executes the plan with random robot delays while keeping the plan's order at every cell, so delays never cause collisions.",
    "about": "A MAPF plan assumes every robot moves exactly on time, which real robots do not. The Action Dependency Graph (ADG) keeps only what matters: each robot's own sequence of moves, and, for every cell, the order in which robots pass through it. During execution a robot may enter a cell only after every robot planned to use that cell before it has left. A late robot therefore makes the others wait instead of crashing into them. Here the bench plans with the solver you pick, then simulates execution in which each robot is randomly delayed with the given probability per step, and returns the paths the robots actually drove. Set the delay to 0 to see the original plan.",
    "papers": [
        {"title": "Persistent and Robust Execution of MAPF Schedules in Warehouses", "authors": "W. Hönig, S. Kiesel, A. Tinka, J. W. Durham, N. Ayanian", "year": 2019, "venue": "IEEE Robotics and Automation Letters 4(2)", "url": "https://act.usc.edu/publications/Hoenig_RAL2019.pdf"},
    ],
    "fidelity": "Implements the ADG execution rule (type-1 edges: a robot's own order; type-2 edges: who passes a cell first) on our grid paths. The paper's overlapped replanning (commit cut) is not implemented; the bench's own replanning handles events instead.",
    "params": {
        "base_solver": {"type": "choice", "options": ["prioritized", "pbs", "eecbs", "lns2"], "default": "prioritized"},
        "delay_probability": {"type": "float", "min": 0.0, "max": 0.9, "default": 0.15},
        "seed": {"type": "int", "min": 0, "max": 99999, "default": 1},
    },
}

import importlib

from ..core.validators import find_conflicts
from . import lowlevel as L


def _visits(path):
    """Compress a path into visits: (cell, first index, last index)."""
    out = []
    for i, (x, y, _) in enumerate(path):
        if out and out[-1][0] == (x, y):
            out[-1][2] = i
        else:
            out.append([(x, y), i, i])
    return out


def plan(problem, state, params, tools):
    base = params.get("base_solver", "prioritized")
    mod = importlib.import_module(f"bench.mapf.{base}")
    res = mod.plan(problem, state, {}, tools)
    if res.get("failed") or res.get("conflicts"):
        res["note"] = f"ADG: base solver {base} gave no clean plan | " + res.get("note", "")
        return res
    p = float(params.get("delay_probability", 0.15))
    rnd = tools.rng(int(params.get("seed", 1)))
    t0 = problem["t0"]
    plans = {r: [tuple(q) for q in pts] for r, pts in res["paths"].items()}
    # type-2 dependencies: for each cell, the planned order of visits (robot, visit index)
    visits = {r: _visits(pts) for r, pts in plans.items()}
    by_cell = {}
    for r, vs in visits.items():
        for vi, (c, a, b) in enumerate(vs):
            by_cell.setdefault(c, []).append((plans[r][a][2], r, vi))
    for c in by_cell:
        by_cell[c].sort()
    visit_of = {r: [None] * len(plans[r]) for r in plans}
    for r, vs in visits.items():
        for vi, (c, a, b) in enumerate(vs):
            for i in range(a, b + 1):
                visit_of[r][i] = vi
    idx = {r: 0 for r in plans}                     # executed position in the robot's plan
    done = {r: False for r in plans}
    out = {r: [(plans[r][0][0], plans[r][0][1], t0)] for r in plans}
    when = {r: {0: t0} for r in plans}
    t = t0
    limit = t0 + 20 * (max(len(v) for v in plans.values()) + 10)

    def visit_finished(r, vi):
        if done[r]:
            return True
        cur = visit_of[r][idx[r]]
        return cur > vi

    delayed_steps = 0
    while not all(done.values()) and t < limit:
        tools.check_time()
        t += 1
        moved = set()
        stalled = {r for r in plans if not done[r] and rnd.random() < p}
        delayed_steps += len(stalled)
        progress = True
        while progress:                              # repeat so a robot can follow one that just left
            progress = False
            for r in sorted(plans):
                if done[r] or r in moved or r in stalled:
                    continue
                if idx[r] == len(plans[r]) - 1:      # reached the end of its plan: leaves the map
                    done[r] = True
                    moved.add(r)
                    progress = True
                    continue
                ni = idx[r] + 1
                cur_v, next_v = visit_of[r][idx[r]], visit_of[r][ni]
                if next_v != cur_v:                  # entering a new cell: earlier visitors must have left
                    c = visits[r][next_v][0]
                    me = (plans[r][visits[r][next_v][1]][2], r, next_v)
                    ok = all(visit_finished(o, ovi) for (pt, o, ovi) in by_cell[c] if (pt, o, ovi) < me and o != r)
                    if not ok:
                        continue
                idx[r] = ni
                moved.add(r)
                progress = True
        for r in plans:
            if r in moved and done[r]:
                continue
            if not done[r]:
                x, y, _ = plans[r][idx[r]]
                out[r].append((x, y, t))
                when[r].setdefault(idx[r], t)
    if not all(done.values()):
        return L.pack({}, {}, [r for r in done if not done[r]], [], "ADG execution deadlocked (should not happen)")
    arrivals = {}
    for leg_id, ta in res["arrivals"].items():
        rid = next(r for r, ls in problem["legs"].items() if any(lg["id"] == leg_id for lg in ls))
        arrivals[leg_id] = when[rid].get(ta - t0, ta)
    late = sum(out[r][-1][2] - plans[r][-1][2] for r in plans)
    return L.pack(out, arrivals, [], find_conflicts(out),
                  f"ADG over {base}: {delayed_steps} random delays absorbed, robots finished {late} steps later in total, plan order kept at every cell")
