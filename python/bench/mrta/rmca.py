INFO = {
    "name": "RMCA (regret-based marginal-cost insertion)",
    "module": "mrta",
    "description": "Inserts tasks one at a time at the cheapest place in some robot's sequence, always handling first the task that would hurt most if it lost its best place.",
    "about": "Each robot keeps an ordered sequence of tasks. For every unassigned task the method computes the marginal cost of inserting it at every position of every capable robot's sequence (cost = makespan of the resulting schedule, which already includes travel from the path model). The regret of a task is how much worse its second-best option is than its best one. The task with the largest regret is inserted first, because delaying it would cost the most. An optional improvement phase (large neighbourhood search) removes a few tasks and re-inserts them with the same rule, keeping the result if it is not worse.",
    "papers": [
        {"title": "Integrated Task Assignment and Path Planning for Capacitated Multi-Agent Pickup and Delivery", "authors": "Z. Chen, J. Alonso-Mora, X. Bai, D. D. Harabor, P. J. Stuckey", "year": 2021, "venue": "IEEE Robotics and Automation Letters 6(3)", "url": "https://arxiv.org/pdf/2110.14891"},
    ],
    "fidelity": "Regret insertion (relative regret, the variant the paper found best) and the LNS improvement loop with random and worst removal. Differences: our robots carry one product at a time (the paper allows capacity C), cost is the bench's makespan instead of total travel delay, and paths are planned afterwards by your MAPF choice rather than inside the insertion.",
    "params": {
        "regret": {"type": "choice", "options": ["relative", "absolute"], "default": "relative"},
        "lns_iterations": {"type": "int", "min": 0, "max": 500, "default": 20},
        "remove_n": {"type": "int", "min": 1, "max": 10, "default": 2},
        "max_positions": {"type": "int", "min": 1, "max": 50, "default": 6},
        "seed": {"type": "int", "min": 0, "max": 99999, "default": 1},
    },
}

from ._seq import Seq, regret_insert, INF


def allocate(scenario, travel_times, state, feedback, params, tools):
    S = Seq(tools, state)
    mp = int(params.get("max_positions", 6))
    rel = params.get("regret", "relative") == "relative"
    seqs = regret_insert(S, S.empty(), list(S.pending), mp, relative=rel)
    if seqs is None:
        return []
    cost, res = S.evaluate(seqs)
    rnd = tools.rng(int(params.get("seed", 1)))
    for it in range(int(params.get("lns_iterations", 20))):
        tools.check_time()
        n = int(params.get("remove_n", 2))
        tasks = [t for s in seqs.values() for t in s]
        if not tasks:
            break
        if it % 2 == 0 or res is None:
            pick = rnd.sample(tasks, min(n, len(tasks)))
        else:                                        # "worst": tasks that finish last
            pick = sorted(tasks, key=lambda t: -res["entries"][t]["machine"]["end"])[:n]
        part, dropped = S.remove_with_successors(seqs, pick)
        new = regret_insert(S, part, dropped, mp, relative=rel)
        if new is None:
            continue
        c, r2 = S.evaluate(new)
        if c <= cost:
            seqs, cost, res = new, c, r2
    return S.finish(seqs)
