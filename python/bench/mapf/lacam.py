INFO = {
    "name": "LaCAM (lazy constraints addition search)",
    "module": "mapf",
    "description": "A search over whole-team positions in which PIBT proposes each next step; remembered positions stop it from going round in circles.",
    "about": "LaCAM searches in the space of configurations (where every robot is at one moment). It never lists all successors of a configuration, which would be impossible for many robots. Instead it asks PIBT for one successor. If that configuration was seen before, LaCAM goes back and lazily adds a constraint ('robot j must go to cell v') and asks PIBT again, so over time it tries every option. This makes it complete on finite maps (it finds a solution if one exists) while staying almost as fast as PIBT. It is the current state of the art for planning hundreds of robots quickly.",
    "papers": [
        {"title": "LaCAM: Search-Based Algorithm for Quick Multi-Agent Pathfinding", "authors": "K. Okumura", "year": 2023, "venue": "AAAI 2023", "url": "https://arxiv.org/pdf/2211.13432"},
        {"title": "Engineering LaCAM*: Towards Real-Time, Large-Scale, and Near-Optimal Multi-Agent Pathfinding", "authors": "K. Okumura", "year": 2024, "venue": "AAMAS 2024", "url": "https://arxiv.org/pdf/2308.04292"},
    ],
    "fidelity": "Core LaCAM loop (depth-first high level, lazy low-level constraint tree, PIBT as the successor generator, re-insertion of revisited configurations). Adapted to legs with release times: the configuration key includes the time until the last release has passed. Not implemented: LaCAM* anytime refinement. A node limit and fallback to PIBT/prioritized keep it inside the time limit.",
    "params": {
        "max_nodes": {"type": "int", "min": 100, "max": 200000, "default": 20000},
        "fallback": {"type": "choice", "options": ["yes", "no"], "default": "yes"},
        "seed": {"type": "int", "min": 0, "max": 99999, "default": 1},
    },
}

from collections import deque

from . import lowlevel as L
from . import stepwise as S


class _Node:
    __slots__ = ("states", "t", "parent", "order", "prio", "tree")

    def __init__(self, states, t, parent, order, prio):
        self.states, self.t, self.parent, self.order, self.prio = states, t, parent, order, prio
        self.tree = deque([()])            # low-level nodes: tuples of (agent, cell) constraints


def plan(problem, state, params, tools):
    ctx = S.Ctx(problem, tools)
    rng = tools.rng(int(params.get("seed", 1)))
    limit = int(params.get("max_nodes", 20000))
    horizon = problem["horizon"]

    def key(states, t):
        return (t if t < ctx.max_release else -1, states)

    s0 = ctx.initial()
    prio0 = [rng.random() * 0.01 for _ in s0]
    root = _Node(s0, ctx.t0, None, S.priority_order(ctx, s0, prio0), prio0)
    open_ = [root]
    explored = {key(s0, ctx.t0): root}
    generated = 0
    goal = None
    while open_:
        tools.check_time()
        node = open_[-1]
        if ctx.done(node.states):
            goal = node
            break
        if not node.tree or node.t - ctx.t0 >= horizon:
            open_.pop()
            continue
        cons = node.tree.popleft()
        depth = len(cons)
        if depth < len(node.order):
            i = node.order[depth]
            st = node.states[i]
            cands = ctx.candidates(i, st, ctx.hmap(i, st))
            rng.shuffle(cands)
            for c in cands:
                node.tree.append(cons + ((i, c),))
        new, _ = S.step(ctx, node.states, node.t, node.order, rng, dict(cons) if cons else None)
        if new is None:
            continue
        generated += 1
        if generated > limit:
            break
        k = key(new, node.t + 1)
        if k in explored:
            open_.append(explored[k])        # re-insert (keeps LaCAM complete)
            continue
        prio = list(node.prio)
        S.update_priorities(ctx, node.states, new, prio, rng)
        child = _Node(new, node.t + 1, node, S.priority_order(ctx, new, prio), prio)
        explored[k] = child
        open_.append(child)
    if goal is not None:
        chain = []
        n = goal
        while n is not None:
            chain.append(n.states)
            n = n.parent
        chain.reverse()
        paths, arrivals = S.to_paths(ctx, chain)
        return L.pack(paths, arrivals, [], [], f"LaCAM: {generated} configurations generated, {len(explored)} distinct, plan length {len(chain) - 1} steps")
    note = f"LaCAM gave up after {generated} configurations"
    if params.get("fallback", "yes") == "yes":
        from . import pibt
        res = pibt.plan(problem, state, {"fallback": "yes", "seed": params.get("seed", 1)}, tools)
        res["note"] = "FELL BACK to PIBT: " + note + " | " + res.get("note", "")
        return res
    return L.pack({}, {}, ctx.rids, [], note)
