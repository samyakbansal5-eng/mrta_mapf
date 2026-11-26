INFO = {
    "name": "Traffic-flow guided PIBT",
    "module": "mapf",
    "description": "First gives every robot a guide route that avoids congested and head-on aisles, then lets PIBT follow those guide routes step by step.",
    "about": "Plain PIBT sends every robot along its own shortest route, so popular aisles jam and robots meet head-on. This method first plans a guide route for each robot on a cost map that counts traffic: an aisle already used in the opposite direction (contraflow) and cells many robots pass through become expensive. Routes are then refined by re-planning a few robots at a time. During execution PIBT ranks a robot's next cells by 'distance along its guide route' instead of straight distance, so robots spread over parallel aisles and flow in consistent directions.",
    "papers": [
        {"title": "Traffic Flow Optimisation for Lifelong Multi-Agent Path Finding", "authors": "Z. Chen, D. Harabor, J. Li, P. J. Stuckey", "year": 2024, "venue": "AAAI 2024", "url": "https://arxiv.org/pdf/2308.11234v4"},
    ],
    "fidelity": "Follows the idea of the paper: congestion-aware guide paths (contraflow and vertex load costs), a refinement pass, and PIBT guided by distance-to-guide-path. Simplified: plain Dijkstra with weighted costs instead of the paper's FOCAL search, and guide paths are computed once per planning call instead of every time step.",
    "params": {
        "contraflow_cost": {"type": "float", "min": 0.0, "max": 10.0, "default": 2.0},
        "vertex_cost": {"type": "float", "min": 0.0, "max": 10.0, "default": 0.5},
        "refine_rounds": {"type": "int", "min": 0, "max": 20, "default": 2},
        "fallback": {"type": "choice", "options": ["yes", "no"], "default": "yes"},
        "seed": {"type": "int", "min": 0, "max": 99999, "default": 1},
    },
}

import heapq

from ..core import grid as G
from . import lowlevel as L
from . import stepwise as S


def _neigh(problem, c, goal):
    out = []
    for n in G.neighbours(problem["grid"], c):
        if n in problem["blocked_set"] and not (n == goal and n in problem["exempt_set"]):
            continue
        out.append(n)
    return out


def _guide(problem, src, dst, flow, vload, cf, vc):
    dist, prev = {src: 0.0}, {}
    pq = [(0.0, src)]
    while pq:
        d, c = heapq.heappop(pq)
        if c == dst:
            break
        if d > dist[c]:
            continue
        for n in _neigh(problem, c, dst):
            nd = d + 1 + cf * flow.get((n, c), 0) + vc * vload.get(n, 0)
            if nd < dist.get(n, 1e18):
                dist[n], prev[n] = nd, c
                heapq.heappush(pq, (nd, n))
    if dst not in dist:
        return None
    path = [dst]
    while path[-1] != src:
        path.append(prev[path[-1]])
    return path[::-1]


def _add(path, flow, vload, sign):
    for a, b in zip(path, path[1:]):
        flow[(a, b)] = flow.get((a, b), 0) + sign
        vload[b] = vload.get(b, 0) + sign


def _hmap_from_guide(problem, path, goal):
    """h(v) = min over guide cells g of (cells from v to g) + (guide cells left after g)."""
    h = {}
    pq = []
    n = len(path)
    for j, c in enumerate(path):
        v = n - 1 - j
        if v < h.get(c, 1e18):
            h[c] = v
            heapq.heappush(pq, (v, c))
    while pq:
        d, c = heapq.heappop(pq)
        if d > h[c]:
            continue
        for m in _neigh(problem, c, goal):
            if d + 1 < h.get(m, 1e18):
                h[m] = d + 1
                heapq.heappush(pq, (d + 1, m))
    return h


def plan(problem, state, params, tools):
    L.prepare(problem)
    cf = float(params.get("contraflow_cost", 2.0))
    vc = float(params.get("vertex_cost", 0.5))
    rnd = tools.rng(int(params.get("seed", 1)))
    # one guide path per carrying/approach leg (from its pickup cell to its destination)
    legs = []
    for rid, ls in problem["legs"].items():
        pos = tuple(problem["robots"][rid]["start"])
        for li, lg in enumerate(ls):
            legs.append((rid, li, pos, tuple(lg["to"])))
            pos = tuple(lg["to"])
    flow, vload, guides = {}, {}, {}
    for key in legs:
        g = _guide(problem, key[2], key[3], flow, vload, cf, vc)
        if g:
            guides[key[:2]] = g
            _add(g, flow, vload, 1)
    for _ in range(int(params.get("refine_rounds", 2))):
        tools.check_time()
        order = list(guides)
        rnd.shuffle(order)
        for key in order:
            _add(guides[key], flow, vload, -1)
            src, dst = guides[key][0], guides[key][-1]
            g = _guide(problem, src, dst, flow, vload, cf, vc) or guides[key]
            guides[key] = g
            _add(g, flow, vload, 1)
    cache = {}

    def heuristic(i, li, phase, goal):
        if phase != 1:
            return None
        key = (ctx.rids[i], li)
        if key not in guides:
            return None
        if key not in cache:
            cache[key] = _hmap_from_guide(problem, guides[key], goal)
        return cache[key]

    ctx = S.Ctx(problem, tools, heuristic=heuristic)
    configs, ok = S.simulate(ctx, rnd, problem["horizon"])
    if ok:
        paths, arrivals = S.to_paths(ctx, configs)
        return L.pack(paths, arrivals, [], [], f"guided PIBT finished in {len(configs) - 1} steps using {len(guides)} congestion-aware guide routes")
    stuck = S.unfinished(ctx, configs[-1])
    note = "guided PIBT stalled (robots " + ",".join(stuck) + ")"
    if params.get("fallback", "yes") == "yes":
        from . import prioritized
        res = prioritized.plan(problem, state, {"restarts": 12}, tools)
        res["note"] = "FELL BACK to prioritized planning: " + note
        return res
    return L.pack({}, {}, stuck, [], note)
