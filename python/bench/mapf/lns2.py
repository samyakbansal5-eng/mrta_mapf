INFO = {
    "name": "MAPF-LNS2 (repair by large neighbourhood search)",
    "module": "mapf",
    "description": "Makes a quick plan that may still collide, then repeatedly re-plans small groups of colliding robots until no collisions are left.",
    "about": "Step 1: plan robots one by one in a random order; a robot that cannot find a collision-free route takes its own shortest route anyway, so the plan may contain collisions. Step 2 (repair loop): pick a small group (a 'neighbourhood') of robots, remove their routes and re-plan them in a random order around everybody else. Keep the new routes if the number of colliding robot pairs did not go up. The group is chosen in one of three ways (robots in a collision cluster, robots that failed, or random robots), and the method learns which way works best on this map (adaptive LNS). It is one of the most practical ways to get a collision-free plan fast when many robots share narrow aisles.",
    "papers": [
        {"title": "MAPF-LNS2: Fast Repairing for Multi-Agent Path Finding via Large Neighborhood Search", "authors": "J. Li, Z. Chen, D. Harabor, P. J. Stuckey, S. Koenig", "year": 2022, "venue": "AAAI 2022", "url": "https://par.nsf.gov/servlets/purl/10350621"},
    ],
    "fidelity": "Follows the paper's loop (initial prioritized plan that tolerates collisions, adaptive choice of collision-based / failure-based / random neighbourhoods, accept if colliding pairs do not increase). Simplified: the paper's SIPPS low level minimises collisions; here a robot is re-planned with hard avoidance first and only takes its plain shortest route if that fails.",
    "params": {
        "neighbourhood": {"type": "int", "min": 2, "max": 16, "default": 4},
        "iterations": {"type": "int", "min": 1, "max": 5000, "default": 300},
        "fallback": {"type": "choice", "options": ["yes", "no"], "default": "yes"},
        "seed": {"type": "int", "min": 0, "max": 99999, "default": 1},
    },
}

from ..core.validators import find_conflicts
from . import lowlevel as L


def _pairs(paths):
    return {tuple(sorted(c["robots"][:2])) for c in find_conflicts(paths)}


def _plan_group(problem, group, paths, arr, hcache, tools, rnd):
    group = list(group)
    rnd.shuffle(group)
    for r in group:
        paths.pop(r, None)
        arr.pop(r, None)
    for r in group:
        vc, ec = set(), set()
        for o, p in paths.items():
            L.reserve(p, vc, ec)
        res = L.plan_chain(problem, r, vc, ec, hcache, tools.check_time)
        if res is None:                                   # soft: take the plain shortest route
            res = L.plan_chain(problem, r, set(), set(), hcache, tools.check_time)
            if res is None:
                return False
        paths[r], arr[r] = res
    return True


def plan(problem, state, params, tools):
    L.prepare(problem)
    rnd = tools.rng(int(params.get("seed", 1)))
    hcache = {}
    rids = list(problem["legs"])
    size = min(int(params.get("neighbourhood", 4)), len(rids))
    paths, arr = {}, {}
    if not _plan_group(problem, rids, paths, arr, hcache, tools, rnd):
        return L.pack({}, {}, rids, [], "a robot has no route at all")
    pairs = _pairs(paths)
    first = len(pairs)
    weights = {"collision": 1.0, "failure": 1.0, "random": 1.0}
    it = 0
    for it in range(int(params.get("iterations", 300))):
        if not pairs:
            break
        tools.check_time()
        tot = sum(weights.values())
        x, strat = rnd.random() * tot, "random"
        for s, w in weights.items():
            x -= w
            if x <= 0:
                strat = s
                break
        if strat == "collision":                          # a connected cluster of the collision graph
            adj = {}
            for a, b in pairs:
                adj.setdefault(a, set()).add(b)
                adj.setdefault(b, set()).add(a)
            seed_r = rnd.choice(sorted(adj))
            group, frontier = {seed_r}, [seed_r]
            while frontier and len(group) < size:
                n = frontier.pop(0)
                for m in sorted(adj.get(n, ())):
                    if m not in group and len(group) < size:
                        group.add(m)
                        frontier.append(m)
        elif strat == "failure":                          # the robots in the most collisions
            count = {}
            for a, b in pairs:
                count[a] = count.get(a, 0) + 1
                count[b] = count.get(b, 0) + 1
            group = set(sorted(count, key=lambda r: (-count[r], r))[:size])
        else:
            group = set(rnd.sample(rids, size))
        while len(group) < size:
            group.add(rnd.choice(rids))
        np_, na = dict(paths), dict(arr)
        if not _plan_group(problem, group, np_, na, hcache, tools, rnd):
            continue
        npairs = _pairs(np_)
        gain = len(pairs) - len(npairs)
        weights[strat] = 0.1 * max(0, gain) + 0.9 * weights[strat] + 1e-3
        if len(npairs) <= len(pairs):
            paths, arr, pairs = np_, na, npairs
    flat = {}
    for a in arr.values():
        flat.update(a)
    if not pairs:
        return L.pack(paths, flat, [], [], f"LNS2: {first} colliding pairs at start, repaired in {it} iterations")
    note = f"LNS2: {len(pairs)} colliding pairs left after {it + 1} iterations"
    if params.get("fallback", "yes") == "yes":
        from . import prioritized
        res = prioritized.plan(problem, state, {"restarts": 12}, tools)
        res["note"] = "FELL BACK to prioritized planning: " + note
        return res
    return L.pack(paths, flat, [], find_conflicts(paths), note)
