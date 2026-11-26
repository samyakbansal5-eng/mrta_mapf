INFO = {
    "name": "TA-Hybrid style tour splitting",
    "module": "mrta",
    "description": "Treats task assignment as one travelling-salesman tour through all tasks, then cuts the tour into one sequence per robot.",
    "about": "TA-Hybrid builds a graph whose vertices are the robots and the tasks; the cost of going from task a to task b is the empty drive from a's drop-off to b's pickup plus carrying b. A single tour through all vertices (a Hamiltonian cycle found with a TSP solver) is split into one sequence per robot, which balances work and keeps empty driving short. Paths are then planned with a MAPF solver. The paper's main objective is makespan, with release times respected at pickups.",
    "papers": [
        {"title": "Task and Path Planning for Multi-Agent Pickup and Delivery", "authors": "M. Liu, H. Ma, J. Li, S. Koenig", "year": 2019, "venue": "AAMAS 2019", "url": "https://idm-lab.org/bib/abstracts/papers/aamas19a.pdf"},
    ],
    "fidelity": "Simplified: the tour is built with a precedence-aware nearest-neighbour rule plus 2-opt (the paper uses the LKH-3 solver), and the cut points are chosen by local search on the bench's makespan. The path-planning half (ICBS and min-cost flow) is replaced by whichever MAPF algorithm you pick.",
    "params": {
        "two_opt_rounds": {"type": "int", "min": 0, "max": 50, "default": 5},
        "split_rounds": {"type": "int", "min": 0, "max": 200, "default": 40},
    },
}

from ._seq import Seq, INF


def allocate(scenario, travel_times, state, feedback, params, tools):
    S = Seq(tools, state)
    tasks = list(S.pending)
    if not tasks or not S.robots:
        return []
    pick = {t: tools.pickup_cell(S.pending[t]) for t in tasks}
    drop = {t: tools.cellof(S.pending[t]["to"]) for t in tasks}

    def c(a, b):
        start = drop[a] if a in drop else a
        return tools.dist(tuple(start), pick[b]) + tools.dist(pick[b], drop[b])

    # precedence-aware nearest neighbour tour
    tour, todo, cur = [], set(tasks), tuple(tools.robot(S.robots[0])["start"])
    while todo:
        ready = [t for t in todo if S.prev.get(t) is None or S.prev[t] in tour]
        nxt = min(ready, key=lambda t: (c(cur if not tour else tour[-1], t), t))
        tour.append(nxt)
        todo.discard(nxt)

    def ok(order):
        seen = set()
        for t in order:
            p = S.prev.get(t)
            if p is not None and p not in seen:
                return False
            seen.add(t)
        return True

    def length(order):
        return sum(c(a, b) for a, b in zip(order, order[1:]))

    for _ in range(int(params.get("two_opt_rounds", 5))):
        improved = False
        for i in range(1, len(tour) - 1):
            for j in range(i + 1, len(tour)):
                cand = tour[:i] + tour[i:j + 1][::-1] + tour[j + 1:]
                if ok(cand) and length(cand) < length(tour):
                    tour, improved = cand, True
        tools.check_time()
        if not improved:
            break

    robots = sorted(S.robots, key=lambda r: (tools.robot(r)["step_cost"], r))   # fastest robots first
    m = len(robots)

    def build(cuts):
        seqs = {r: [] for r in S.robots}
        bounds = [0] + cuts + [len(tour)]
        for j in range(m):
            for t in tour[bounds[j]:bounds[j + 1]]:
                r = robots[j]
                if r not in S.elig[t]:                       # not capable: give it to a capable robot
                    if not S.elig[t]:
                        continue
                    r = min(S.elig[t], key=lambda x: len(seqs[x]))
                seqs[r].append(t)
        return seqs

    n = len(tour)
    cuts = [round(n * (j + 1) / m) for j in range(m - 1)]
    best_seqs = build(cuts)
    best, _ = S.evaluate(best_seqs)
    for _ in range(int(params.get("split_rounds", 40))):
        tools.check_time()
        improved = False
        for j in range(len(cuts)):
            for d in (-1, 1):
                nc = list(cuts)
                nc[j] += d
                if not all(0 <= x <= n for x in nc) or nc != sorted(nc):
                    continue
                s = build(nc)
                v, _ = S.evaluate(s)
                if v < best:
                    best, best_seqs, cuts, improved = v, s, nc, True
        if not improved:
            break
    return S.finish(best_seqs)
