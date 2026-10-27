INFO = {
    "name": "Genetic algorithm",
    "module": "mrta",
    "description": "Evolves a priority order of tasks plus a robot for each task, minimising makespan.",
    "params": {
        "population": {"type": "int", "min": 6, "max": 200, "default": 30},
        "generations": {"type": "int", "min": 1, "max": 500, "default": 40},
        "mutation": {"type": "float", "min": 0.0, "max": 1.0, "default": 0.2},
        "seed": {"type": "int", "min": 0, "max": 99999, "default": 1},
    },
}


def allocate(scenario, travel_times, state, feedback, params, tools):
    rnd = tools.rng(params.get("seed", 1))
    pop_n = int(params.get("population", 30))
    gens = int(params.get("generations", 40))
    pm = float(params.get("mutation", 0.2))
    tasks = [t["id"] for t in tools.pending_tasks()]
    if not tasks:
        return []
    elig = {tid: tools.eligible(tid) for tid in tasks}
    if any(not v for v in elig.values()):
        return []

    def decode(g):
        return [{"task": tid, "robot": g["robot"][tid]} for tid in g["order"]]

    def fitness(g):
        tools.check_time()
        res = tools.schedule(decode(g))
        return res["makespan"] if res["ok"] else 10 ** 9

    def random_ind():
        order = tasks[:]
        rnd.shuffle(order)
        return {"order": order, "robot": {tid: rnd.choice(elig[tid]) for tid in tasks}}

    def crossover(a, b):
        cut = rnd.randint(1, max(1, len(tasks) - 1))
        head = a["order"][:cut]
        order = head + [t for t in b["order"] if t not in head]
        robot = {tid: (a if rnd.random() < 0.5 else b)["robot"][tid] for tid in tasks}
        return {"order": order, "robot": robot}

    def mutate(g):
        if rnd.random() < pm and len(tasks) > 1:
            i, j = rnd.sample(range(len(tasks)), 2)
            g["order"][i], g["order"][j] = g["order"][j], g["order"][i]
        if rnd.random() < pm:
            tid = rnd.choice(tasks)
            g["robot"][tid] = rnd.choice(elig[tid])

    # seed the population with the greedy solution so the result is never worse than greedy
    from . import greedy
    seed_assign = greedy.allocate(scenario, travel_times, state, feedback, {}, tools)
    pop = [random_ind() for _ in range(pop_n - 1)]
    if len(seed_assign) == len(tasks):
        pop.append({"order": [a["task"] for a in seed_assign], "robot": {a["task"]: a["robot"] for a in seed_assign}})
    else:
        pop.append(random_ind())
    scored = sorted(((fitness(g), i, g) for i, g in enumerate(pop)), key=lambda x: (x[0], x[1]))
    for _ in range(gens):
        elite = [g for _, _, g in scored[: max(2, pop_n // 5)]]
        nxt = [{"order": g["order"][:], "robot": dict(g["robot"])} for g in elite]
        while len(nxt) < pop_n:
            a, b = rnd.sample(elite, 2) if len(elite) > 1 else (elite[0], elite[0])
            c = crossover(a, b)
            mutate(c)
            nxt.append(c)
        scored = sorted(((fitness(g), i, g) for i, g in enumerate(nxt)), key=lambda x: (x[0], x[1]))
    return decode(scored[0][2])
