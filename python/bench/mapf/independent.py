INFO = {
    "name": "Independent A* (no avoidance)",
    "module": "mapf",
    "description": "Baseline: every robot takes its own shortest route; collisions are only reported, not avoided.",
    "about": 'Every robot plans its own fastest route with space-time A* and ignores all other robots. Collisions are reported, not avoided. It is the baseline that shows how many conflicts the other algorithms have to resolve.',
    "papers": [
        {"title": 'A Formal Basis for the Heuristic Determination of Minimum Cost Paths (A*)', "authors": 'P. E. Hart, N. J. Nilsson, B. Raphael', "year": 1968, "venue": 'IEEE Transactions on Systems Science and Cybernetics 4(2)', "url": 'https://doi.org/10.1109/TSSC.1968.300136'},
    ],
    "fidelity": 'Plain space-time A* per robot.',
    "params": {},
}

from ..core.validators import find_conflicts
from . import lowlevel as L


def plan(problem, state, params, tools):
    L.prepare(problem)
    hcache, paths, arrivals, failed = {}, {}, {}, []
    for rid in problem["legs"]:
        res = L.plan_chain(problem, rid, set(), set(), hcache, tools.check_time)
        if res is None:
            failed.append(rid)
        else:
            paths[rid], arr = res
            arrivals.update(arr)
    return L.pack(paths, arrivals, failed, find_conflicts(paths), "baseline: collisions are not avoided")
