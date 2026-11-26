"""Step-by-step machinery shared by PIBT, LaCAM and the traffic-flow planner.

These algorithms do not plan a whole route per robot. They decide, one time step at a time,
where every robot goes next. This module turns our problem format (legs with release times,
robots that need k steps per cell, blocked cells) into that step-by-step world:

* A robot works through its legs in order. Before a leg's release time it must stand on the
  leg's pickup cell (the "anchor"); once it is there at time >= release, the product is on board
  (phase 1) and it heads for the leg's destination. That is exactly the rule st_astar uses.
* A robot with step_cost k may move only after it has stood still for k-1 steps
  ("cool" counts the steps since its last move).
* When a robot reaches the destination of its last leg it leaves the map (the bench treats a
  robot as absent after its path ends), so it no longer blocks anyone.

Agent state = (pos, leg_index, phase, cool). pos is None once the robot has left the map.
"""
from ..core import grid as G
from . import lowlevel as L


class Ctx:
    def __init__(self, problem, tools, heuristic=None):
        L.prepare(problem)
        self.p = problem
        self.tools = tools
        self.rids = list(problem["legs"])
        self.k = [problem["robots"][r]["step_cost"] for r in self.rids]
        self.legs = [problem["legs"][r] for r in self.rids]
        self.start = [tuple(problem["robots"][r]["start"]) for r in self.rids]
        self.hcache = {}
        self.heuristic = heuristic          # optional f(i, li, phase, goal) -> {cell: value}
        self.grid = problem["grid"]
        self.blocked = problem["blocked_set"]
        self.exempt = problem["exempt_set"]
        self.t0 = problem["t0"]
        self.max_release = max([lg["release"] for ls in self.legs for lg in ls] + [self.t0])

    # --- legs
    def anchor(self, i, li):
        return self.start[i] if li == 0 else tuple(self.legs[i][li - 1]["to"])

    def goal(self, i, st):
        pos, li, ph, _ = st
        if li >= len(self.legs[i]):
            return None
        return tuple(self.legs[i][li]["to"]) if ph == 1 else self.anchor(i, li)

    def hmap(self, i, st):
        g = self.goal(i, st)
        if g is None:
            return {}
        if self.heuristic is not None:
            h = self.heuristic(i, st[1], st[2], g)
            if h is not None:
                return h
        h = L.hmap_for(self.p, g, self.hcache)
        if st[0] is not None and st[0] not in h:
            L._with_start(h, st[0], self.grid, self.blocked)
        return h

    def settle(self, i, st, t, arrivals=None):
        """Apply pickups and arrivals that happen at time t on the robot's current cell."""
        pos, li, ph, cool = st
        n = len(self.legs[i])
        while li < n:
            leg = self.legs[i][li]
            if ph == 0 and pos == self.anchor(i, li) and t >= leg["release"]:
                ph = 1
            if ph == 1 and pos == tuple(leg["to"]):
                if arrivals is not None:
                    arrivals[leg["id"]] = t
                li, ph = li + 1, 0
                continue
            break
        return (pos, li, ph, cool)

    def initial(self):
        return tuple(self.settle(i, (self.start[i], 0, 0, 0), self.t0) for i in range(len(self.rids)))

    def done(self, states):
        return all(s[1] >= len(self.legs[i]) for i, s in enumerate(states))

    # --- moves
    def candidates(self, i, st, h):
        """Cells robot i may be on next step (stay first in the list), with their heuristic value."""
        pos = st[0]
        goal = self.goal(i, st)
        out = [pos]
        if st[3] >= self.k[i] - 1:
            for n in G.neighbours(self.grid, pos):
                if n in self.blocked and not (n == goal and n in self.exempt):
                    continue
                if n in h:
                    out.append(n)
        return out


def step(ctx, states, t, order, rng, fixed=None):
    """One PIBT step from time t to t+1.

    states: tuple of agent states at time t; order: agent indices, highest priority first.
    fixed: optional {agent: cell} the robots MUST take (LaCAM's constraints).
    Returns (new_states, arrivals_at_t+1) or (None, None) if the fixed cells cannot be honoured.
    """
    n = len(states)
    active = [i for i in range(n) if states[i][1] < len(ctx.legs[i])]
    pos = {i: states[i][0] for i in active}
    occupant = {pos[i]: i for i in active}
    nxt = {}
    taken = {}
    hmaps = {i: ctx.hmap(i, states[i]) for i in active}
    tie = {i: rng.random() for i in active}

    def reserve(i, c):
        nxt[i] = c
        taken[c] = i

    # robots that cannot move this step (still covering a cell slowly) stay put
    for i in active:
        if states[i][3] < ctx.k[i] - 1:
            if pos[i] in taken:
                return None, None
            reserve(i, pos[i])
    if fixed:
        for i, c in fixed.items():
            if i not in pos:
                continue
            if i in nxt and nxt[i] != c:
                return None, None
            if c in taken and taken[c] != i:
                return None, None
            if c != pos[i] and c not in ctx.candidates(i, states[i], hmaps[i]):
                return None, None
            j = occupant.get(c)
            if j is not None and j != i and j in nxt and nxt[j] == pos[i]:
                return None, None          # would swap
            reserve(i, c)

    def pibt(i, parent):
        h = hmaps[i]
        cands = ctx.candidates(i, states[i], h)
        cands.sort(key=lambda c: (h.get(c, G.INF), c != pos[i], tie[i] if c == pos[i] else rng.random()))
        for c in cands:
            if c in taken:
                continue
            if parent is not None and c == pos[parent]:
                continue
            j = occupant.get(c)
            if j is not None and j != i and j in nxt and nxt[j] == pos[i]:
                continue                     # j is moving into my cell: no swapping
            reserve(i, c)
            if j is not None and j != i and j not in nxt:
                if not pibt(j, i):
                    nxt.pop(i, None)          # j could not leave and stays on c
                    continue
            return True
        reserve(i, pos[i])                    # stay put (overrides a parent's claim on this cell)
        return False

    for i in list(order) + active:
        if i in active and i not in nxt:
            pibt(i, None)
    # sanity: no two robots on one cell
    if len(set(nxt.values())) != len(nxt):
        return None, None
    arrivals = {}
    new = list(states)
    for i in range(n):
        if i not in pos:
            new[i] = (None, states[i][1], 0, 0)
            continue
        c = nxt[i]
        cool = 0 if c != pos[i] else states[i][3] + 1
        new[i] = ctx.settle(i, (c, states[i][1], states[i][2], cool), t + 1, arrivals)
    return tuple(new), arrivals


def to_paths(ctx, configs):
    """configs[j] = states at time t0 + j. Rebuild paths (until each robot leaves) and arrivals."""
    paths, arrivals = {}, {}
    for i, rid in enumerate(ctx.rids):
        p = []
        for j, cfg in enumerate(configs):
            st = cfg[i]
            prev_done = j > 0 and configs[j - 1][i][1] >= len(ctx.legs[i])
            if st[0] is None or prev_done:
                break
            p.append((st[0][0], st[0][1], ctx.t0 + j))
        paths[rid] = p
    # replay arrivals
    for i in range(len(ctx.rids)):
        st = ctx.settle(i, (ctx.start[i], 0, 0, 0), ctx.t0, arrivals)
        for j in range(1, len(configs)):
            if st[1] >= len(ctx.legs[i]):
                break
            c = configs[j][i][0]
            st = ctx.settle(i, (c, st[1], st[2], 0), ctx.t0 + j, arrivals)
    return paths, arrivals


def priority_order(ctx, states, prio):
    act = [i for i in range(len(states)) if states[i][1] < len(ctx.legs[i])]
    return sorted(act, key=lambda i: (-prio[i], i))


def update_priorities(ctx, old, new, prio, rng):
    """PIBT rule: priority grows while a robot is away from its goal; reset when it is on it."""
    for i in range(len(new)):
        if new[i][1] >= len(ctx.legs[i]):
            continue
        if new[i][1] != old[i][1] or new[i][2] != old[i][2] or new[i][0] == ctx.goal(i, new[i]):
            prio[i] = rng.random() * 0.01
        else:
            prio[i] += 1


def simulate(ctx, rng, max_steps):
    """Plain PIBT: step until every robot has finished, or give up after max_steps."""
    states = ctx.initial()
    configs = [states]
    prio = [0.0] * len(states)
    for i in range(len(states)):
        prio[i] = rng.random() * 0.01
    t = ctx.t0
    while not ctx.done(states) and t - ctx.t0 < max_steps:
        ctx.tools.check_time()
        order = priority_order(ctx, states, prio)
        new, arr = step(ctx, states, t, order, rng)
        if new is None:                       # cannot happen without constraints; be safe
            break
        update_priorities(ctx, states, new, prio, rng)
        states = new
        configs.append(states)
        t += 1
    return configs, ctx.done(states)


def unfinished(ctx, states):
    return [ctx.rids[i] for i, s in enumerate(states) if s[1] < len(ctx.legs[i])]
