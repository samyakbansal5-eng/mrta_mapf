INFO = {
    "name": "Greedy earliest-finish",
    "module": "mrta",
    "description": "Takes tasks hop by hop and gives each one to the eligible robot that would finish it earliest.",
    "about": 'Tasks are taken hop by hop (first hops of all products, then second hops, and so on). Each task goes to the capable robot that would finish carrying it earliest, given the tasks it already has. Simple, fast and a good baseline; it never reconsiders an earlier choice.',
    "papers": [
        {"title": 'A Formal Analysis and Taxonomy of Task Allocation in Multi-Robot Systems', "authors": 'B. P. Gerkey, M. J. Matarić', "year": 2004, "venue": 'International Journal of Robotics Research 23(9)', "url": 'https://cse-robotics.engr.tamu.edu/dshell/cs689/papers/gerkey04formal.pdf'},
    ],
    "fidelity": 'A textbook greedy rule; the paper is the standard reference for how MRTA problems are classified (this one is single-task robots, single-robot tasks, time-extended assignment).',
    "params": {},
}


def allocate(scenario, travel_times, state, feedback, params, tools):
    assignment = []
    for t in sorted(tools.pending_tasks(), key=lambda t: (t["k"], t["id"])):
        best = None
        for r in tools.eligible(t["id"]):
            res = tools.schedule(assignment + [{"task": t["id"], "robot": r}])
            if not res["ok"]:
                continue
            key = (res["entries"][t["id"]]["carry"]["arrive"], res["makespan"])
            if best is None or key < best[0]:
                best = (key, r)
        if best:
            assignment.append({"task": t["id"], "robot": best[1]})
    return assignment
