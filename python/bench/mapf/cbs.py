INFO = {
    "name": "Conflict-Based Search (CBS)",
    "module": "mapf",
    "description": "Plans every robot alone, finds the first collision, then branches: forbid the cell/time for one robot or the other. Finds minimum-total-time plans.",
    "params": {
        "max_nodes": {"type": "int", "min": 10, "max": 20000, "default": 1500},
        "fallback": {"type": "choice", "options": ["yes", "no"], "default": "yes"},
    },
}

import heapq

from ..core.validators import find_conflicts
from . import lowlevel as L


def _cost(paths):
    return sum(p[-1][2] for p in paths.values())


def plan(problem, state, params, tools):
    L.prepare(problem)
    hcache = {}
    max_nodes = int(params.get("max_nodes", 1500))
    rids = list(problem["legs"])
    cons = {r: {"v": set(), "e": set()} for r in rids}
    paths, arrivals = {}, {}
    for r in rids:
        res = L.plan_chain(problem, r, set(), set(), hcache, tools.check_time)
        if res is None:
            return L.pack({}, {}, [r], [], "a robot has no route at all")
        paths[r], arr = res
        arrivals[r] = arr
    counter = 0
    open_ = [(_cost(paths), len(find_conflicts(paths)), counter, cons, paths, arrivals)]
    expanded = 0
    while open_:
        tools.check_time()
        _, _, _, cons, paths, arrivals = heapq.heappop(open_)
        conflicts = find_conflicts(paths)
        if not conflicts:
            flat = {}
            for a in arrivals.values():
                flat.update(a)
            return L.pack(paths, flat, [], [], f"{expanded} CBS nodes expanded")
        expanded += 1
        if expanded > max_nodes:
            break
        c = conflicts[0]
        r1, r2 = c["robots"][0], c["robots"][1]
        for who, other in ((r1, r2), (r2, r1)):
            nc = {r: {"v": set(v["v"]), "e": set(v["e"])} for r, v in cons.items()}
            if c["type"] == "vertex":
                nc[who]["v"].add((tuple(c["cell"]), c["t"]))
            else:
                a, b = tuple(c["cell"][0]), tuple(c["cell"][1])
                # who moves a->b or b->a: find which direction this robot moved at time t
                p = paths[who]
                idx = next(i for i, q in enumerate(p) if q[2] == c["t"])
                frm, to = (p[idx - 1][0], p[idx - 1][1]), (p[idx][0], p[idx][1])
                nc[who]["e"].add((frm, to, c["t"]))
            res = L.plan_chain(problem, who, nc[who]["v"], nc[who]["e"], hcache, tools.check_time)
            if res is None:
                continue
            np_, na = dict(paths), dict(arrivals)
            np_[who], na[who] = res
            counter += 1
            heapq.heappush(open_, (_cost(np_), len(find_conflicts(np_)), counter, nc, np_, na))
    note = f"CBS stopped after {expanded} nodes without a collision-free plan"
    if params.get("fallback", "yes") == "yes":
        from . import prioritized
        res = prioritized.plan(problem, state, {"restarts": 12}, tools)
        res["note"] = "FELL BACK to prioritized planning: " + note
        return res
    return L.pack({}, {}, rids, [], note)
