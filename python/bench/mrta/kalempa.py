INFO = {
    "name": "Priority dispatch with fault recovery (MRPF)",
    "module": "mrta",
    "description": "Serves the most critical job first and gives it to the nearest available robot; a failed robot's job goes to the nearest healthy robot.",
    "about": "Jobs get a priority class (Minor, Normal, Major, Critical). Whenever a robot becomes free, the highest-priority waiting job is dispatched to the nearest available robot. A higher-priority job may preempt a lower one at the end of its current stage. When a robot fails it is sent to maintenance and the nearest available robot takes over its job. The method was demonstrated on a real small warehouse with three robots and compared with CBS-TA and ECBS-TA.",
    "papers": [
        {"title": "Multi-Robot Preemptive Task Scheduling with Fault Recovery: A Novel Approach to Automatic Logistics of Smart Factories", "authors": "V. C. Kalempa, L. Piardi, M. Limeira, A. S. de Oliveira", "year": 2021, "venue": "Sensors 21(19)", "url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC8512959"},
    ],
    "fidelity": "Inspired by the paper. Priority = remaining processing work of the product (Critical = most work left), since our scenarios have no priority field. Fault recovery uses the bench's own replanning: after a robot_failure event the plug-in is called again without the failed robot. Preemption inside a running transport is not modelled.",
    "params": {},
}

from ._seq import Seq, INF


def allocate(scenario, travel_times, state, feedback, params, tools):
    S = Seq(tools, state)
    prods = {p["id"]: p for p in scenario["products"]}

    def remaining(t):
        p = prods[t["product"]]
        rest = p["route"][t["k"]:]
        return sum(p.get("process_time", {}).get(m, 0) for m in rest)

    seqs, todo = S.empty(), set(S.pending)
    while todo:
        tools.check_time()
        ready = S.executable(seqs, todo)
        if not ready:
            break
        tid = max(ready, key=lambda t: (remaining(S.pending[t]), -S.pending[t]["k"], t))
        best = None
        for r in S.elig[tid]:
            cand = S.insert(seqs, r, len(seqs[r]), tid)
            c, res = S.evaluate(cand)
            if c >= INF:
                continue
            e = res["entries"][tid]
            key = (e["carry"]["start"], e["approach"]["arrive"] - e["approach"]["start"], r)   # nearest available
            if best is None or key < best[0]:
                best = (key, cand)
        todo.discard(tid)
        if best:
            seqs = best[1]
    return S.finish(seqs)
