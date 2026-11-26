INFO = {
    "name": "Lexicographic queue builder (Calvo & Capitán)",
    "module": "mrta",
    "description": "Builds each robot's queue greedily, ranking candidate tasks lexicographically by makespan, then waiting time, then travel; robots are filtered by capability first.",
    "about": "In every iteration the heuristic computes the current makespan, selects the robots capable of each remaining task, and ranks all (task, robot) options with a lexicographic key: resulting makespan first, then deadline delay, then the robot's waiting time, then travel. The best option is appended to that robot's queue. When the mission changes (a new task, a robot failure) the paper repairs the plan first by reducing waiting times and only reassigns if needed. Designed for heterogeneous robots with different capabilities and long missions with battery limits.",
    "papers": [
        {"title": "Heterogeneous Multi-robot Task Allocation for Long-Endurance Missions in Dynamic Scenarios", "authors": "Á. Calvo, J. Capitán", "year": 2025, "venue": "IEEE Transactions on Robotics 41 (arXiv 2024)", "url": "https://arxiv.org/pdf/2411.02062"},
    ],
    "fidelity": "Inspired by the paper's heuristic planner. Kept: capability filter (our can_carry and payload), lexicographic ranking. Not modelled: batteries and recharging, deadlines (no due dates in our scenarios), coalitions and the repair-first replanning (the bench replans from scratch after events).",
    "params": {},
}

from ._seq import Seq, INF


def allocate(scenario, travel_times, state, feedback, params, tools):
    S = Seq(tools, state)
    seqs, todo = S.empty(), set(S.pending)
    while todo:
        best = None
        for tid in sorted(S.executable(seqs, todo)):
            for r in S.elig[tid]:
                cand = S.insert(seqs, r, len(seqs[r]), tid)
                c, res = S.evaluate(cand)
                if c >= INF:
                    continue
                e = res["entries"][tid]
                wait = max(0, e["carry"]["start"] - e["approach"]["arrive"])
                travel = (e["approach"]["arrive"] - e["approach"]["start"]) + (e["carry"]["arrive"] - e["carry"]["start"])
                key = (round(c), wait, travel, tid, r)
                if best is None or key < best[0]:
                    best = (key, cand, tid)
        if best is None:
            break
        seqs = best[1]
        todo.discard(best[2])
    return S.finish(seqs)
