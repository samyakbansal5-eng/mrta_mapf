INFO = {
    "name": "Constructive + relocate heuristic (Bischoff et al.)",
    "module": "mrta",
    "description": "Builds a plan by repeatedly adding the executable task that raises the cost least, then improves it by moving single tasks to better places.",
    "about": "Constructive phase: a task is executable once its predecessor (the previous hop of the same product) is planned. In every step the heuristic tries each executable task at the end of each capable robot's sequence and keeps the cheapest increase of the objective. Improvement phase: the relocate neighbourhood moves one task to any position in any capable robot's sequence; the best move is taken if it improves the plan and keeps the precedence graph acyclic (no two robots waiting for each other). Built for heterogeneous robots (different speeds) and precedence constraints, and very fast (hundredths of a second in the paper).",
    "papers": [
        {"title": "Multi-Robot Task Allocation and Scheduling Considering Cooperative Tasks and Precedence Constraints", "authors": "E. Bischoff, F. Meyer, J. Inga, S. Hohmann", "year": 2020, "venue": "IEEE SMC 2020", "url": "https://arxiv.org/pdf/2005.03902"},
    ],
    "fidelity": "Algorithm 1 (constructive) and Algorithm 2 (relocate improvement) with objectives J1 (makespan) and J2 (average finish time). Not modelled: cooperative tasks that need two robots at once, because our scenario format has no such tasks yet.",
    "params": {
        "objective": {"type": "choice", "options": ["makespan", "average"], "default": "makespan"},
        "improve_iterations": {"type": "int", "min": 0, "max": 200, "default": 30},
    },
}

from ._seq import Seq, INF


def allocate(scenario, travel_times, state, feedback, params, tools):
    S = Seq(tools, state)
    obj = params.get("objective", "makespan")
    seqs, todo = S.empty(), set(S.pending)
    while todo:
        best = None
        for tid in sorted(S.executable(seqs, todo)):
            for r in S.elig[tid]:
                cand = S.insert(seqs, r, len(seqs[r]), tid)
                c, _ = S.evaluate(cand, obj)
                if c < INF and (best is None or (c, tid, r) < best[0]):
                    best = ((c, tid, r), cand, tid)
        if best is None:
            break
        seqs = best[1]
        todo.discard(best[2])
    cost, _ = S.evaluate(seqs, obj)
    for _ in range(int(params.get("improve_iterations", 30))):
        best = None
        for r0, s in seqs.items():
            for tid in s:
                base = {k: [t for t in v if t != tid] for k, v in seqs.items()}
                for r in S.elig[tid]:
                    for i in range(len(base[r]) + 1):
                        if r == r0 and i == s.index(tid):
                            continue
                        cand = S.insert(base, r, i, tid)
                        c, _ = S.evaluate(cand, obj)
                        if c < cost and (best is None or c < best[0]):
                            best = (c, cand)
        if best is None:
            break
        cost, seqs = best
    return S.finish(seqs)
