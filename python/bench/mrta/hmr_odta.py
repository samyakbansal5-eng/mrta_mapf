INFO = {
    "name": "HMR-ODTA style online auction (heterogeneous classes)",
    "module": "mrta",
    "description": "Tasks arrive in order and are auctioned one by one; robots are grouped into classes by speed and payload, bids are lateness penalties with efficiency and energy as tie-breaks.",
    "about": "Requests enter a global queue in the order they become available. Each request is auctioned by a round-robin auctioneer (classes of robots take turns, then robots within a class). Every capable robot bids by appending the request to its own timetable: the bid is the lateness penalty max(0, completion - due date), then lower efficiency loss, then less energy used so far. The winning robot updates its timetable. The method was designed for a team with several robot classes that differ in speed, capacity and energy, which is exactly the heterogeneous case.",
    "papers": [
        {"title": "HMR-ODTA: Online Diverse Task Allocation for a Team of Heterogeneous Mobile Robots", "authors": "A. Verma, A. Gautam, T. Duhan, V. S. Shekhawat, S. Mohan", "year": 2025, "venue": "arXiv preprint", "url": "https://arxiv.org/pdf/2505.08419"},
    ],
    "fidelity": "Inspired by the paper. Our scenarios have no due dates, so a due date is derived for each task as its earliest possible finish times (1 + slack). Energy is approximated by distance driven so far. Charging and the paper's temporal-network repair are not modelled.",
    "params": {
        "slack": {"type": "float", "min": 0.0, "max": 5.0, "default": 0.5},
    },
}

from ._seq import Seq, INF


def allocate(scenario, travel_times, state, feedback, params, tools):
    S = Seq(tools, state)
    slack = float(params.get("slack", 0.5))
    classes = {}
    for r in S.robots:
        rb = tools.robot(r)
        classes.setdefault((rb["step_cost"], rb.get("payload")), []).append(r)
    class_keys = sorted(classes)
    seqs = S.empty()
    driven = {r: 0 for r in S.robots}
    queue = sorted(S.pending, key=lambda t: (S.pending[t]["k"], S.pending[t]["product"], t))
    log = []
    for j, tid in enumerate(queue):
        tools.check_time()
        cls = class_keys[j % len(class_keys)] if class_keys else None
        auctioneer = classes[cls][(j // max(1, len(class_keys))) % len(classes[cls])] if cls else None
        bids = []
        for r in S.elig[tid]:
            cand = S.insert(seqs, r, len(seqs[r]), tid)
            c, res = S.evaluate(cand)
            if c >= INF:
                continue
            e = res["entries"][tid]
            bids.append((r, e["machine"]["end"], e))
        if not bids:
            continue
        due = min(b[1] for b in bids) * (1 + slack)
        ranked = []
        for r, done, e in bids:
            penalty = max(0, done - due)
            busy = (e["carry"]["arrive"] - e["carry"]["start"])
            span = max(1, e["carry"]["arrive"] - e["approach"]["start"])
            eta = 1 - busy / span                    # share of the job spent not carrying
            ranked.append(((penalty, round(eta, 3), driven[r], r), r, e))
        ranked.sort()
        _, win, e = ranked[0]
        seqs = S.insert(seqs, win, len(seqs[win]), tid)
        driven[win] += (e["carry"]["arrive"] - e["carry"]["start"]) + (e["approach"]["arrive"] - e["approach"]["start"])
        log.append((tid, auctioneer, win))
    return S.finish(seqs)
