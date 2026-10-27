INFO = {
    "name": "Independent A* (no avoidance)",
    "module": "mapf",
    "description": "Baseline: every robot takes its own shortest route; collisions are only reported, not avoided.",
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
