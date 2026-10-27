"""MAPF template. Copy this file, change INFO and plan(), then upload it in the Import tab.

plan() returns a dict built with L.pack(paths, arrivals, failed, conflicts, note):
  paths     {robot_id: [(x, y, t), ...]}   one cell per time step, starting at the robot's position
  arrivals  {leg_id: time the robot reaches the leg's destination}
  failed    robot ids you could not plan
  conflicts what you know is still colliding (use find_conflicts to list them)

The helpers in bench.mapf.lowlevel (st_astar, plan_chain, reserve) do the space-time search;
replace the ordering logic below with your own idea (priorities, CBS-style repair, ...).
"""
INFO = {
    "name": "Prioritized, slowest robot first (example)",
    "module": "mapf",
    "description": "Robots plan one by one; slower robots (more steps per cell) get priority.",
    "params": {},
}

from bench.mapf import lowlevel as L
from bench.core.validators import find_conflicts


def plan(problem, state, params, tools):
    L.prepare(problem)
    order = sorted(problem["legs"], key=lambda r: -problem["robots"][r]["step_cost"])
    vc, ec, paths, arrivals, failed, hcache = set(), set(), {}, {}, [], {}
    for rid in order:
        res = L.plan_chain(problem, rid, vc, ec, hcache, tools.check_time)
        if res is None:
            failed.append(rid)
            continue
        paths[rid], arr = res
        arrivals.update(arr)
        L.reserve(paths[rid], vc, ec)
    return L.pack(paths, arrivals, failed, find_conflicts(paths), "order: " + ",".join(order))
