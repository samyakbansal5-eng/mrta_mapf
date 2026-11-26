INFO = {
    "name": "Auction (sequential single-item)",
    "module": "mrta",
    "description": "Market-based: each round every robot bids its own route cost for every open task; the cheapest bid wins.",
    "about": 'A market-based method. In each round every robot computes a bid for every open task: the time at which it would finish that task if it were added to the end of its queue. The single cheapest bid over all tasks and robots wins, the winner adds the task, and the next round starts. Sequential single-item auctions are simple, can run decentralised, and have proven quality bounds for some objectives.',
    "papers": [
        {"title": 'The Power of Sequential Single-Item Auctions for Agent Coordination', "authors": 'S. Koenig et al.', "year": 2006, "venue": 'AAAI 2006', "url": 'https://cdn.aaai.org/AAAI/2006/AAAI06-266.pdf'},
        {"title": 'Market-Based Multirobot Coordination: A Survey and Analysis', "authors": 'M. B. Dias, R. Zlot, N. Kalra, A. Stentz', "year": 2006, "venue": 'Proceedings of the IEEE 94(7)', "url": 'https://publications.ri.cmu.edu/storage/publications/pub_files/2006/7/01677943-1.pdf'},
    ],
    "fidelity": "Standard sequential single-item auction with finish-time bids; tasks are appended to the end of a robot's queue (see TeSSI for insertion bids).",
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
