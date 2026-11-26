INFO = {
    "name": "RHCR (rolling-horizon windowed replanning)",
    "module": "mapf",
    "description": "Plans collision-free only for the next w steps, executes h of them, then replans from where the robots really are. Built for robots that keep getting new jobs.",
    "about": "Rolling-Horizon Collision Resolution splits a long-running problem into short episodes. Every h time steps it takes the robots' current positions and their next jobs and calls a MAPF solver that only resolves collisions inside a window of w steps (w >= h); anything later is ignored for now. The robots execute h steps and the process repeats. Ignoring far-away collisions makes each episode cheap, and replanning often means new tasks, delays or blocked aisles are picked up quickly. The price is that it is incomplete: robots can occasionally get stuck, which the paper's authors note themselves.",
    "papers": [
        {"title": "Lifelong Multi-Agent Path Finding in Large-Scale Warehouses", "authors": "J. Li, A. Tinka, S. Kiesel, J. W. Durham, T. K. S. Kumar, S. Koenig", "year": 2021, "venue": "AAAI 2021", "url": "https://idm-lab.org/bib/abstracts/papers/aaai21b.pdf"},
    ],
    "fidelity": "Follows the RHCR framework with windowed prioritized planning as the inner solver (the paper also tests windowed PBS and ECBS). Robots that cannot be planned in a window try other random orders; if every order fails the planner reports failure.",
    "params": {
        "window_w": {"type": "int", "min": 2, "max": 200, "default": 12},
        "replan_every_h": {"type": "int", "min": 1, "max": 200, "default": 5},
        "restarts": {"type": "int", "min": 0, "max": 30, "default": 8},
        "seed": {"type": "int", "min": 0, "max": 99999, "default": 1},
    },
}

from . import lowlevel as L
from . import stepwise as S


def _chain(problem, ctx, i, st, T, vc, ec, hcache, tools):
    pos, li, ph, _ = st
    k = ctx.k[i]
    path = [(pos[0], pos[1], T)]
    t = T
    for j in range(li, len(ctx.legs[i])):
        leg = ctx.legs[i][j]
        anchor = ctx.anchor(i, j) if j == li else pos
        seg = L.st_astar(problem, pos, t, leg["to"], leg["release"], k, vc, ec, hcache, tools.check_time,
                         anchor=anchor, phase0=ph if j == li else 0)
        if seg is None:
            return None
        path.extend(seg[1:])
        t = seg[-1][2]
        pos = tuple(leg["to"])
    return path


def plan(problem, state, params, tools):
    ctx = S.Ctx(problem, tools)
    w = int(params.get("window_w", 12))
    h = max(1, min(int(params.get("replan_every_h", 5)), w))
    rnd = tools.rng(int(params.get("seed", 1)))
    restarts = int(params.get("restarts", 8))
    hcache = {}
    states = list(ctx.initial())
    n = len(states)
    hist = {i: [(states[i][0][0], states[i][0][1], ctx.t0)] for i in range(n)}
    arrivals = {}
    # arrivals that happen right at t0
    for i in range(n):
        ctx.settle(i, (ctx.start[i], 0, 0, 0), ctx.t0, arrivals)
    T = ctx.t0
    episodes = 0
    while any(states[i][1] < len(ctx.legs[i]) for i in range(n)):
        tools.check_time()
        if T - ctx.t0 > problem["horizon"]:
            stuck = [ctx.rids[i] for i in range(n) if states[i][1] < len(ctx.legs[i])]
            return L.pack({}, {}, stuck, [], "RHCR did not finish within the horizon (robots kept blocking each other)")
        act = [i for i in range(n) if states[i][1] < len(ctx.legs[i])]
        base = sorted(act, key=lambda i: (-states[i][2], min([lg["release"] for lg in ctx.legs[i][states[i][1]:]] or [0]), i))
        orders = [base] + [rnd.sample(act, len(act)) for _ in range(restarts)]
        planned = None
        for order in orders:
            vc, ec, paths = set(), set(), {}
            ok = True
            for i in order:
                p = _chain(problem, ctx, i, states[i], T, vc, ec, hcache, tools)
                if p is None:
                    ok = False
                    break
                paths[i] = p
                L.reserve([q for q in p if q[2] <= T + w], vc, ec)
            if ok:
                planned = paths
                break
        if planned is None:
            stuck = [ctx.rids[i] for i in act]
            return L.pack({}, {}, stuck, [], f"RHCR: no window plan found at t={T}")
        episodes += 1
        for i in act:
            st = states[i]
            for (x, y, t) in planned[i][1:]:
                if t > T + h:
                    break
                hist[i].append((x, y, t))
                cool = 0 if (x, y) != st[0] else st[3] + 1
                st = ctx.settle(i, ((x, y), st[1], st[2], cool), t, arrivals)
                if st[1] >= len(ctx.legs[i]):
                    break
            states[i] = st
        T += h
    paths = {ctx.rids[i]: hist[i] for i in range(n)}
    return L.pack(paths, arrivals, [], [], f"RHCR: {episodes} episodes (w={w}, h={h})")
