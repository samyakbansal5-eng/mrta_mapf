INFO = {
    "name": "Prioritized planning",
    "module": "mapf",
    "description": "Robots plan one after another; each avoids the (cell, time) slots already reserved by earlier robots.",
    "params": {
        "order": {"type": "choice", "options": ["by_release", "longest_first"], "default": "by_release"},
        "restarts": {"type": "int", "min": 0, "max": 50, "default": 8},
        "seed": {"type": "int", "min": 0, "max": 99999, "default": 1},
    },
}

from . import lowlevel as L


def _try(problem, order, hcache, tools):
    vc, ec, paths, arrivals = set(), set(), {}, {}
    for rid in order:
        res = L.plan_chain(problem, rid, vc, ec, hcache, tools.check_time)
        if res is None:
            return None, rid
        paths[rid], arr = res
        arrivals.update(arr)
        L.reserve(paths[rid], vc, ec)
    return (paths, arrivals), None


def plan(problem, state, params, tools):
    L.prepare(problem)
    rids = list(problem["legs"])
    mode = params.get("order", "by_release")
    if mode == "longest_first":
        rids.sort(key=lambda r: -sum(abs(l["to"][0] - l["from"][0]) + abs(l["to"][1] - l["from"][1]) for l in problem["legs"][r]))
    else:
        rids.sort(key=lambda r: min((l["release"] for l in problem["legs"][r]), default=0))
    rnd = tools.rng(int(params.get("seed", 1)))
    hcache = {}
    orders = [rids] + [rnd.sample(rids, len(rids)) for _ in range(int(params.get("restarts", 8)))]
    culprit = None
    for i, order in enumerate(orders):
        ok, culprit = _try(problem, order, hcache, tools)
        if ok:
            return L.pack(ok[0], ok[1], [], [], f"order {i + 1} of {len(orders)}: " + ",".join(order))
    return L.pack({}, {}, [culprit] if culprit else rids, [], "no collision-free plan found with the tried orders")
