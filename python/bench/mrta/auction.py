INFO = {
    "name": "Auction (sequential single-item)",
    "module": "mrta",
    "description": "Market-based: each round every robot bids its own route cost for every open task; the cheapest bid wins.",
    "params": {},
}


def allocate(scenario, travel_times, state, feedback, params, tools):
    pending = {t["id"]: t for t in tools.pending_tasks()}
    robots = {r["id"]: r for r in scenario["robots"] if state["robots"][r["id"]]["status"] == "ok"}
    load = {rid: state["t"] for rid in robots}                 # time at which the robot's queue ends
    loc = {rid: state["robots"][rid]["pos"] for rid in robots}
    assignment = []
    while pending:
        tools.check_time()
        best = None
        for tid, t in pending.items():
            pick = tools.pickup_cell(t)
            drop = tools.cellof(t["to"])
            for rid in tools.eligible(tid):
                step = robots[rid]["step_cost"]
                cost = step * (tools.dist(loc[rid], pick) + tools.dist(pick, drop))
                bid = load[rid] + cost                           # the robot's own finishing time
                key = (bid, t["k"], tid)
                if best is None or key < best[0]:
                    best = (key, tid, rid, cost, drop)
        if best is None:
            break
        _, tid, rid, cost, drop = best
        assignment.append({"task": tid, "robot": rid})
        load[rid] += cost
        loc[rid] = drop
        del pending[tid]
    return assignment
