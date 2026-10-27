INFO = {
    "name": "Greedy earliest-finish",
    "module": "mrta",
    "description": "Takes tasks hop by hop and gives each one to the eligible robot that would finish it earliest.",
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
