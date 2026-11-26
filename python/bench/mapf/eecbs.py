INFO = {
    "name": "EECBS-style bounded-suboptimal CBS",
    "module": "mapf",
    "description": "CBS that accepts plans up to w times the best cost, and among those first expands the node with the fewest collisions. Much faster than exact CBS.",
    "about": "Conflict-Based Search keeps a tree of constraint sets and always expands the cheapest node, which is optimal but slow when there are many collisions. The bounded-suboptimal family (ECBS, EECBS) keeps a FOCAL list: every node whose cost is at most w x the cheapest known lower bound. From FOCAL it picks the node with the fewest collisions, because that node is probably closest to a collision-free plan. The result is guaranteed to cost at most w times the optimum. EECBS adds explicit estimation (an online-learned guess of each node's final cost) to choose between the cheapest node, the FOCAL node and the best-estimate node.",
    "papers": [
        {"title": "EECBS: A Bounded-Suboptimal Search for Multi-Agent Path Finding", "authors": "J. Li, W. Ruml, S. Koenig", "year": 2021, "venue": "AAAI 2021", "url": "https://arxiv.org/pdf/2010.01367"},
        {"title": "Suboptimal Variants of the Conflict-Based Search Algorithm for the Multi-Agent Pathfinding Problem (ECBS)", "authors": "M. Barer, G. Sharon, R. Stern, A. Felner", "year": 2014, "venue": "SoCS 2014", "url": "https://people.engr.tamu.edu/guni/pistar/Papers/SOCS14-BCBS.pdf"},
    ],
    "fidelity": "Simplified: the high level uses FOCAL search with the w bound (the ECBS/EECBS core idea); the low level stays our optimal space-time A*, so the bound holds. The explicit-estimation part of EECBS and its extra speed-ups are not implemented.",
    "params": {
        "w": {"type": "float", "min": 1.0, "max": 3.0, "default": 1.2},
        "max_nodes": {"type": "int", "min": 10, "max": 20000, "default": 1500},
        "fallback": {"type": "choice", "options": ["yes", "no"], "default": "yes"},
    },
}

from ..core.validators import find_conflicts
from . import lowlevel as L


def _cost(paths):
    return sum(p[-1][2] for p in paths.values())


def plan(problem, state, params, tools):
    L.prepare(problem)
    hcache = {}
    w = float(params.get("w", 1.2))
    limit = int(params.get("max_nodes", 1500))
    rids = list(problem["legs"])
    paths, arr = {}, {}
    for r in rids:
        res = L.plan_chain(problem, r, set(), set(), hcache, tools.check_time)
        if res is None:
            return L.pack({}, {}, [r], [], "a robot has no route at all")
        paths[r], arr[r] = res
    cons = {r: (frozenset(), frozenset()) for r in rids}
    nodes = [(_cost(paths), len(find_conflicts(paths)), 0, cons, paths, arr)]
    counter, expanded = 0, 0
    while nodes and expanded < limit:
        tools.check_time()
        lb = min(n[0] for n in nodes)
        focal = [n for n in nodes if n[0] <= w * lb]
        node = min(focal, key=lambda n: (n[1], n[0], n[2]))
        nodes.remove(node)
        cost, _, _, cons, paths, arr = node
        conflicts = find_conflicts(paths)
        if not conflicts:
            flat = {}
            for a in arr.values():
                flat.update(a)
            return L.pack(paths, flat, [], [], f"bounded CBS (w={w}): {expanded} nodes, cost {cost} (lower bound {lb})")
        expanded += 1
        c = conflicts[0]
        for who in c["robots"][:2]:
            v, e = set(cons[who][0]), set(cons[who][1])
            if c["type"] == "vertex":
                v.add((tuple(c["cell"]), c["t"]))
            else:
                p = paths[who]
                idx = next(i for i, q in enumerate(p) if q[2] == c["t"])
                e.add(((p[idx - 1][0], p[idx - 1][1]), (p[idx][0], p[idx][1]), c["t"]))
            res = L.plan_chain(problem, who, v, e, hcache, tools.check_time)
            if res is None:
                continue
            np_, na = dict(paths), dict(arr)
            np_[who], na[who] = res
            nc = dict(cons)
            nc[who] = (frozenset(v), frozenset(e))
            counter += 1
            nodes.append((_cost(np_), len(find_conflicts(np_)), counter, nc, np_, na))
    note = f"bounded CBS stopped after {expanded} nodes without a collision-free plan"
    if params.get("fallback", "yes") == "yes":
        from . import prioritized
        res = prioritized.plan(problem, state, {"restarts": 12}, tools)
        res["note"] = "FELL BACK to prioritized planning: " + note
        return res
    return L.pack({}, {}, rids, [], note)
