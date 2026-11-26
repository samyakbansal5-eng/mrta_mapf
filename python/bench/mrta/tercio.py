INFO = {
    "name": "Tercio style assign-then-sequence",
    "module": "mrta",
    "description": "Splits the problem in two: first decide which robot gets which tasks (balancing workload), then order each robot's tasks with a fast list scheduler, and repeat with a tighter bound.",
    "about": "Tercio was designed for scheduling robot teams in manufacturing work cells in seconds. Its idea is a decomposition: an outer step assigns tasks to robots (in the paper with a mixed-integer program that minimises workload under a makespan bound), and an inner step sequences each robot's tasks with a fast, polynomial-time list scheduler that respects temporal and spatial constraints. If the resulting schedule misses the bound, the outer step is repeated with that information. This gives near-optimal schedules for large teams very quickly.",
    "papers": [
        {"title": "Fast Scheduling of Robot Teams Performing Tasks With Temporospatial Constraints", "authors": "M. C. Gombolay, R. J. Wilcox, J. A. Shah", "year": 2018, "venue": "IEEE Transactions on Robotics 34(1)", "url": "https://people.csail.mit.edu/gombolay/Publications/Gombolay_TRO_2018.pdf"},
    ],
    "fidelity": "Inspired by Tercio's decomposition, written from general knowledge of the method (the full paper was not machine-read). The outer step is a workload-balancing greedy assignment with penalties on the robot that finished last, not a mixed-integer program; the inner step is the bench's schedule builder with hop-order priorities.",
    "params": {
        "iterations": {"type": "int", "min": 1, "max": 100, "default": 15},
    },
}

from ._seq import Seq, INF


def allocate(scenario, travel_times, state, feedback, params, tools):
    S = Seq(tools, state)
    tasks = sorted(S.pending, key=lambda t: (S.pending[t]["k"], t))
    work = {}
    for t in tasks:
        tk = S.pending[t]
        work[t] = tools.dist(tools.pickup_cell(tk), tools.cellof(tk["to"])) + tk["process"]
    penalty = {r: 0.0 for r in S.robots}
    best, best_seqs = INF, None
    for _ in range(int(params.get("iterations", 15))):
        tools.check_time()
        load = {r: penalty[r] for r in S.robots}
        assign = {}
        for t in sorted(tasks, key=lambda t: (-work[t], t)):         # longest task first (LPT rule)
            if not S.elig[t]:
                continue
            r = min(S.elig[t], key=lambda r: (load[r] + work[t] * tools.robot(r)["step_cost"], r))
            assign[t] = r
            load[r] += work[t] * tools.robot(r)["step_cost"]
        seqs = {r: [t for t in tasks if assign.get(t) == r] for r in S.robots}  # list scheduler: hop order
        v, res = S.evaluate(seqs)
        if v < best:
            best, best_seqs = v, seqs
        if res is None:
            break
        last = max(res["entries"].values(), key=lambda e: e["machine"]["end"])["robot"]
        penalty[last] += max(1.0, best / (2 * max(1, len(S.robots))))     # tighten: push work away from the bottleneck robot
    return S.finish(best_seqs) if best_seqs else []
