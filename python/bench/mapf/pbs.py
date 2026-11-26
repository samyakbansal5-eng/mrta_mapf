INFO = {
    "name": "PBS (priority-based search)",
    "module": "mapf",
    "description": "Searches over which robot gets priority when two collide, instead of over cells and times. Fast and simple.",
    "about": "Start with every robot planned on its own. Find the first collision between robots i and j and branch into two children: 'i has priority over j' and 'j has priority over i'. In a child, the lower-priority robot (and every robot below it) is re-planned so it avoids all robots above it. The search goes depth-first, always into the cheaper child, so it finds a good collision-free plan quickly. Unlike plain prioritized planning, the priority order is not fixed in advance: PBS discovers it.",
    "papers": [
        {"title": "Searching with Consistent Prioritization for Multi-Agent Path Finding", "authors": "H. Ma, D. Harabor, P. J. Stuckey, J. Li, S. Koenig", "year": 2019, "venue": "AAAI 2019", "url": "https://arxiv.org/pdf/1812.06356"},
    ],
    "fidelity": "Follows the paper's depth-first search over pairwise priorities. The low level is our space-time A*; the node limit and the fallback to prioritized planning are our additions.",
    "params": {
        "max_nodes": {"type": "int", "min": 10, "max": 20000, "default": 800},
        "fallback": {"type": "choice", "options": ["yes", "no"], "default": "yes"},
    },
}

from ..core.validators import find_conflicts
from . import lowlevel as L


def _closure(pri, rids):
    """pri: set of (hi, lo). Returns {robot: set of robots above it}."""
    above = {r: set() for r in rids}
    changed = True
    for hi, lo in pri:
        above[lo].add(hi)
    while changed:
        changed = False
        for r in rids:
            extra = set()
            for a in above[r]:
                extra |= above[a]
            if not extra <= above[r]:
                above[r] |= extra
                changed = True
    return above


def _replan(problem, node_paths, node_arr, pri, start_robot, rids, hcache, tools):
    above = _closure(pri, rids)
    if any(r in above[r] for r in rids):
        return None
    todo = {start_robot} | {r for r in rids if start_robot in above[r]}
    # topological order: fewer robots above first
    order = sorted(todo, key=lambda r: (len(above[r]), r))
    paths, arr = dict(node_paths), dict(node_arr)
    for r in order:
        vc, ec = set(), set()
        for a in above[r]:
            if a in paths:
                L.reserve(paths[a], vc, ec)
        res = L.plan_chain(problem, r, vc, ec, hcache, tools.check_time)
        if res is None:
            return None
        paths[r], arr[r] = res
    return paths, arr


def _cost(paths):
    return sum(p[-1][2] for p in paths.values())


def plan(problem, state, params, tools):
    L.prepare(problem)
    hcache = {}
    rids = list(problem["legs"])
    paths, arr = {}, {}
    for r in rids:
        res = L.plan_chain(problem, r, set(), set(), hcache, tools.check_time)
        if res is None:
            return L.pack({}, {}, [r], [], "a robot has no route at all")
        paths[r], arr[r] = res
    stack = [(frozenset(), paths, arr)]
    expanded, limit = 0, int(params.get("max_nodes", 800))
    while stack and expanded < limit:
        tools.check_time()
        pri, paths, arr = stack.pop()
        conflicts = find_conflicts(paths)
        if not conflicts:
            flat = {}
            for a in arr.values():
                flat.update(a)
            return L.pack(paths, flat, [], [], f"PBS: {expanded} nodes, priorities found: " + (", ".join(f"{a}>{b}" for a, b in sorted(pri)) or "none needed"))
        expanded += 1
        c = conflicts[0]
        a, b = c["robots"][0], c["robots"][1]
        children = []
        for hi, lo in ((a, b), (b, a)):
            npri = pri | {(hi, lo)}
            res = _replan(problem, paths, arr, npri, lo, rids, hcache, tools)
            if res is not None:
                children.append((_cost(res[0]), npri, res[0], res[1]))
        children.sort(key=lambda x: -x[0])          # cheaper child pushed last = explored first
        for _, npri, p, ar in children:
            stack.append((npri, p, ar))
    note = f"PBS stopped after {expanded} nodes without a collision-free plan"
    if params.get("fallback", "yes") == "yes":
        from . import prioritized
        res = prioritized.plan(problem, state, {"restarts": 12}, tools)
        res["note"] = "FELL BACK to prioritized planning: " + note
        return res
    return L.pack({}, {}, rids, [], note)
