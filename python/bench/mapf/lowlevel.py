"""Space-time A* and helpers shared by the MAPF algorithms."""
import heapq

from ..core import grid as G


def hmap_for(problem, goal, cache):
    key = tuple(goal)
    if key not in cache:
        cache[key] = G.bfs_dist(problem["grid"], goal, problem["blocked_set"])
    return cache[key]


def _with_start(h, start, grid, blocked):
    """A robot standing on a cell that was blocked under it may still leave it."""
    if start in h:
        return True
    ds = [h[n] for n in G.neighbours(grid, start, blocked) if n in h]
    if not ds:
        return False
    h[start] = 1 + min(ds)
    return True


def st_astar(problem, start, t_start, goal, release, k, vcons, econs, hcache, check_time=None):
    """Cheapest-arrival path in (cell, time) for one leg: start -> goal.

    * A robot with step_cost k needs k time steps per cell: it waits k-1 steps on the cell it
      leaves, then arrives on the next cell.
    * The leg's product is picked up on the START cell at time >= release. Before that the
      robot may move around (e.g. step aside to let others pass) but must be back on the
      start cell at time >= release before it heads for the goal.
    vcons: forbidden (cell, t); econs: forbidden (from, to, t_arrival).
    Returns [(x, y, t), ...] from t_start through arrival, or None.
    """
    grid = problem["grid"]
    blocked = problem["blocked_set"]
    exempt = problem["exempt_set"]
    start, goal = tuple(start), tuple(goal)
    if start == goal:
        return [(start[0], start[1], t_start)]
    hg = hmap_for(problem, goal, hcache)
    if not _with_start(hg, start, grid, blocked):
        return None
    hf = hmap_for(problem, start, hcache)
    t_max = t_start + problem["horizon"]
    dgo = hg[start]

    def phase(c, t, ph):
        return 1 if ph == 1 or (c == start and t >= release) else 0

    def heur(c, t, ph):
        if ph == 1:
            return hg[c] * k
        return max(hf.get(c, 0) * k + dgo * k, (release - t) + dgo * k)

    ph0 = phase(start, t_start, 0)
    s0 = (start, t_start, ph0)
    parent = {s0: None}
    open_ = [(heur(*s0), 0, s0)]
    counter = 0
    while open_:
        if check_time and counter % 256 == 0:
            check_time()
        _, _, s = heapq.heappop(open_)
        c, t, ph = s
        if c == goal and ph == 1:
            out = []
            while True:
                out.append((s[0][0], s[0][1], s[1]))
                p = parent[s]
                if p is None:
                    break
                ps, extra = p
                out.extend(reversed(extra))
                s = ps
            out.reverse()
            return out
        if t >= t_max:
            continue
        # wait one step
        if (c, t + 1) not in vcons:
            ns = (c, t + 1, phase(c, t + 1, ph))
            if ns not in parent:
                parent[ns] = (s, [])
                counter += 1
                heapq.heappush(open_, (t + 1 - t_start + heur(*ns), counter, ns))
        x, y = c
        for dx, dy in G.DIRS:
            n = (x + dx, y + dy)
            if G.is_wall(grid, n):
                continue
            if n in blocked and not (n == goal and n in exempt):
                continue
            if n not in hg or n not in hf:
                continue
            ta = t + k
            if ta > t_max or (n, ta) in vcons or (c, n, ta) in econs:
                continue
            ns = (n, ta, phase(n, ta, ph))
            if ns in parent:
                continue
            extra = []
            ok = True
            for i in range(1, k):
                if (c, t + i) in vcons:
                    ok = False
                    break
                extra.append((x, y, t + i))
            if not ok:
                continue
            parent[ns] = (s, extra)
            counter += 1
            heapq.heappush(open_, (ta - t_start + heur(*ns), counter, ns))
    return None


def plan_chain(problem, rid, vcons, econs, hcache, check_time=None):
    """Plan all legs of one robot back to back. Returns (path, arrivals) or None."""
    r = problem["robots"][rid]
    pos, t = tuple(r["start"]), problem["t0"]
    path = [(pos[0], pos[1], t)]
    arrivals = {}
    for leg in problem["legs"][rid]:
        seg = st_astar(problem, pos, t, leg["to"], leg["release"], r["step_cost"], vcons, econs, hcache, check_time)
        if seg is None:
            return None
        path.extend(seg[1:])
        t = seg[-1][2]
        pos = tuple(leg["to"])
        arrivals[leg["id"]] = t
    return path, arrivals


def reserve(path, vcons, econs):
    """Add one robot's path to a reservation table (other robots must avoid it)."""
    for i, (x, y, t) in enumerate(path):
        vcons.add(((x, y), t))
        if i > 0:
            px, py, _ = path[i - 1]
            if (px, py) != (x, y):
                econs.add(((x, y), (px, py), t))


def prepare(problem):
    problem["blocked_set"] = {tuple(c) for c in problem["blocked"]}
    problem["exempt_set"] = {tuple(c) for c in problem.get("goal_exempt", [])}
    return problem


def pack(paths, arrivals, failed, conflicts=None, note=""):
    return {
        "paths": {rid: [list(p) for p in path] for rid, path in paths.items()},
        "arrivals": arrivals, "failed": failed, "note": note,
        "conflicts": conflicts or [],
    }
