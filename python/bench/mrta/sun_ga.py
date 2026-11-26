INFO = {
    "name": "Hybrid GA with conflict-free routing (Sun et al.)",
    "module": "mrta",
    "description": "A genetic algorithm decides which robot carries each job; collision-free routes are then found on a time-window map. Pair it with a collision-avoiding MAPF algorithm.",
    "about": "The paper integrates machine scheduling and AGV scheduling in a flexible job shop and adds conflict-free routing: a genetic algorithm searches the AGV assignment, and a time-window Dijkstra plans routes that avoid head-on and node conflicts while minimising waiting. Makespan is the objective. It was tested on 82 benchmark problems and a real lab job shop with three AGVs and four machines. In this bench the split is natural: this plug-in is the GA part and your MAPF choice (for example CBS, PBS or prioritized) is the routing part, with the bench's feedback loop passing route delays back into the schedule.",
    "papers": [
        {"title": "An Approach to Integrated Scheduling of Flexible Job-Shop Considering Conflict-Free Routing Problems", "authors": "J. Sun, Z. Xu, Z. Yan, L. Liu, Y. Zhang", "year": 2023, "venue": "Sensors 23(9)", "url": "https://www.mdpi.com/1424-8220/23/9/4526"},
    ],
    "fidelity": "Inspired by the paper: GA over the robot-assignment genes with a fixed hop-order job sequence, uniform crossover and reassignment mutation. The paper's exact GA operators were not in the part of the paper that could be read, and its time-window routing is replaced by the MAPF module.",
    "params": {
        "population": {"type": "int", "min": 6, "max": 200, "default": 24},
        "generations": {"type": "int", "min": 1, "max": 500, "default": 30},
        "mutation": {"type": "float", "min": 0.0, "max": 1.0, "default": 0.15},
        "seed": {"type": "int", "min": 0, "max": 99999, "default": 1},
    },
}

from ._seq import INF


def allocate(scenario, travel_times, state, feedback, params, tools):
    rnd = tools.rng(int(params.get("seed", 1)))
    tasks = [t["id"] for t in sorted(tools.pending_tasks(), key=lambda t: (t["k"], t["id"]))]
    if not tasks:
        return []
    elig = {t: tools.eligible(t) for t in tasks}
    if any(not v for v in elig.values()):
        return []

    def decode(g):
        return [{"task": t, "robot": g[t]} for t in tasks]

    def fit(g):
        tools.check_time()
        res = tools.schedule(decode(g))
        return res["makespan"] if res["ok"] else INF

    from . import greedy
    seed = {a["task"]: a["robot"] for a in greedy.allocate(scenario, travel_times, state, feedback, {}, tools)}
    n = int(params.get("population", 24))
    pop = [{t: seed.get(t, elig[t][0]) for t in tasks}] + [{t: rnd.choice(elig[t]) for t in tasks} for _ in range(n - 1)]
    scored = sorted(((fit(g), i, g) for i, g in enumerate(pop)), key=lambda x: (x[0], x[1]))
    pm = float(params.get("mutation", 0.15))
    for _ in range(int(params.get("generations", 30))):
        elite = [g for _, _, g in scored[: max(2, n // 4)]]
        nxt = [dict(g) for g in elite]
        while len(nxt) < n:
            a, b = rnd.sample(elite, 2)
            c = {t: (a if rnd.random() < 0.5 else b)[t] for t in tasks}
            for t in tasks:
                if rnd.random() < pm:
                    c[t] = rnd.choice(elig[t])
            nxt.append(c)
        scored = sorted(((fit(g), i, g) for i, g in enumerate(nxt)), key=lambda x: (x[0], x[1]))
    return decode(scored[0][2])
