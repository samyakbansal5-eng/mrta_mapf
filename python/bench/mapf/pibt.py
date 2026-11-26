INFO = {
    "name": "PIBT (priority inheritance with backtracking)",
    "module": "mapf",
    "description": "Decides one time step at a time: robots pick their next cell in priority order, and a robot in the way is asked to move first.",
    "about": "Every time step each robot ranks its neighbouring cells by distance to its goal. The robot with the highest priority picks first; if the cell it wants is occupied, the robot sitting there inherits the priority and must move out of the way (recursively). If that robot cannot move, the first robot backtracks and tries its next cell. Priority grows while a robot has not reached its goal, so nobody waits forever on well-connected maps. Very fast (one pass per step) and reacts instantly to changes, but it does not look ahead, so on narrow dead-end corridors it can stall.",
    "papers": [
        {"title": "Priority Inheritance with Backtracking for Iterative Multi-agent Path Finding", "authors": "K. Okumura, M. Machida, X. Défago, Y. Tamura", "year": 2019, "venue": "IJCAI 2019; journal version Artificial Intelligence 2022", "url": "https://arxiv.org/pdf/1901.11282v4"},
    ],
    "fidelity": "Faithful to Algorithm 1 of the paper. Adapted to our model: a robot with k steps per cell may move only after standing still k-1 steps, and robots leave the map after their last delivery. If PIBT stalls within the time horizon it falls back to prioritized planning (switchable).",
    "params": {
        "fallback": {"type": "choice", "options": ["yes", "no"], "default": "yes"},
        "seed": {"type": "int", "min": 0, "max": 99999, "default": 1},
    },
}

from . import lowlevel as L
from . import stepwise as S


def plan(problem, state, params, tools):
    ctx = S.Ctx(problem, tools)
    rng = tools.rng(int(params.get("seed", 1)))
    configs, ok = S.simulate(ctx, rng, problem["horizon"])
    if ok:
        paths, arrivals = S.to_paths(ctx, configs)
        return L.pack(paths, arrivals, [], [], f"PIBT finished in {len(configs) - 1} steps")
    stuck = S.unfinished(ctx, configs[-1])
    note = "PIBT stalled (robots " + ",".join(stuck) + " did not finish within the horizon)"
    if params.get("fallback", "yes") == "yes":
        from . import prioritized
        res = prioritized.plan(problem, state, {"restarts": 12}, tools)
        res["note"] = "FELL BACK to prioritized planning: " + note
        return res
    return L.pack({}, {}, stuck, [], note)
