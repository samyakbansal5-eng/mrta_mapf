INFO = {
    "name": "Improved GA for multi-AGV job shops (Meng et al.)",
    "module": "mrta",
    "description": "Genetic algorithm on the operation sequence; the transport robot for each job is chosen while decoding as the one that can reach it earliest; near-duplicate individuals are replaced to keep diversity.",
    "about": "The chromosome is an operation-sequence string (each product appears once per remaining hop, so the j-th appearance of P2 means P2's j-th transport). Decoding walks the string and gives each transport to the robot that can arrive at the pickup earliest. Crossover is POX (keep the positions of a random subset of products from one parent, fill the rest in the other parent's order), mutation swaps two genes, and every few generations a diversity check regenerates individuals that are near-copies of another with the same makespan. The paper reports new best-known results on 34 benchmark instances.",
    "papers": [
        {"title": "An Improved Genetic Algorithm for Solving the Multi-AGV Flexible Job Shop Scheduling Problem", "authors": "L. Meng, W. Cheng, B. Zhang, W. Zou, W. Fang, P. Duan", "year": 2023, "venue": "Sensors 23(8)", "url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC10144946/"},
    ],
    "fidelity": "Operation-sequence encoding, earliest-arrival robot decoding, POX crossover, swap mutation and the diversity check, as in the paper. The machine-selection string is left out because our products have fixed machines (no alternatives yet). Fitness is makespan. Defaults are smaller than the paper's (population 200, 200 generations) so it runs in the browser.",
    "params": {
        "population": {"type": "int", "min": 6, "max": 200, "default": 30},
        "generations": {"type": "int", "min": 1, "max": 500, "default": 40},
        "crossover": {"type": "float", "min": 0.0, "max": 1.0, "default": 0.8},
        "mutation": {"type": "float", "min": 0.0, "max": 1.0, "default": 0.1},
        "seed": {"type": "int", "min": 0, "max": 99999, "default": 1},
    },
}

from ._seq import INF


def allocate(scenario, travel_times, state, feedback, params, tools):
    rnd = tools.rng(int(params.get("seed", 1)))
    pend = sorted(tools.pending_tasks(), key=lambda t: (t["product"], t["k"]))
    if not pend:
        return []
    hops = {}
    for t in pend:
        hops.setdefault(t["product"], []).append(t)
    genes0 = [p for p, ts in hops.items() for _ in ts]
    elig = {t["id"]: tools.eligible(t["id"]) for t in pend}
    if any(not v for v in elig.values()):
        return []
    rinfo = {r["id"]: r for r in scenario["robots"] if r["id"] in {x for v in elig.values() for x in v}}

    def decode(genes):
        seen, out = {}, []
        free = {r: state["t"] for r in rinfo}
        loc = {r: tuple(state["robots"][r]["pos"]) for r in rinfo}
        for p in genes:
            j = seen.get(p, 0)
            seen[p] = j + 1
            t = hops[p][j]
            pick, dropc = tools.pickup_cell(t), tools.cellof(t["to"])
            best = min(elig[t["id"]], key=lambda r: (free[r] + tools.dist(loc[r], pick) * rinfo[r]["step_cost"], r))
            free[best] += (tools.dist(loc[best], pick) + tools.dist(pick, dropc)) * rinfo[best]["step_cost"]
            loc[best] = dropc
            out.append({"task": t["id"], "robot": best})
        return out

    def fit(genes):
        tools.check_time()
        res = tools.schedule(decode(genes))
        return res["makespan"] if res["ok"] else INF

    def pox(a, b):
        keep = set(rnd.sample(sorted(hops), max(1, len(hops) // 2)))
        fill = [g for g in b if g not in keep]
        child, k = [], 0
        for g in a:
            if g in keep:
                child.append(g)
            else:
                child.append(fill[k])
                k += 1
        return child

    n = int(params.get("population", 30))
    pc, pm = float(params.get("crossover", 0.8)), float(params.get("mutation", 0.1))
    pop = [genes0[:]] + [rnd.sample(genes0, len(genes0)) for _ in range(n - 1)]
    scored = sorted(((fit(g), i, g) for i, g in enumerate(pop)))
    for gen in range(int(params.get("generations", 40))):
        elite = [g for _, _, g in scored[: max(2, n // 5)]]
        nxt = [g[:] for g in elite]
        while len(nxt) < n:
            a, b = rnd.sample(elite, 2)
            c = pox(a, b) if rnd.random() < pc else a[:]
            if rnd.random() < pm and len(c) > 1:
                i, j = rnd.sample(range(len(c)), 2)
                c[i], c[j] = c[j], c[i]
            nxt.append(c)
        scored = sorted(((fit(g), i, g) for i, g in enumerate(nxt)))
        if gen % 5 == 4:                                  # diversity check
            seen = []
            for k, (f, i, g) in enumerate(scored):
                for f2, g2 in seen:
                    same = sum(1 for x, y in zip(g, g2) if x == y) / len(g)
                    if f == f2 and same >= 0.8:
                        ng = rnd.sample(genes0, len(genes0))
                        scored[k] = (fit(ng), i, ng)
                        break
                seen.append((scored[k][0], scored[k][2]))
            scored.sort()
    return decode(scored[0][2])
