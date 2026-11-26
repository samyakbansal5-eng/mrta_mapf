INFO = {
    "name": "Tabu search",
    "module": "mrta",
    "description": "Starts from the greedy plan and repeatedly tries moving a task to another robot or swapping two tasks in the order, avoiding recently tried moves.",
    "about": "Tabu search starts from the greedy plan and repeatedly applies the best small change: move one task to another robot, or swap two neighbouring tasks in the order. Recently used moves are 'tabu' for a few iterations so the search does not cycle back, unless a tabu move would beat the best plan found so far.",
    "papers": [
        {"title": 'Tabu Search Algorithms for Job-Shop Problems with a Single Transport Robot', "authors": 'J. Hurink, S. Knust', "year": 2005, "venue": 'European Journal of Operational Research 162(1)', "url": 'https://research.utwente.nl/files/5112851/1579.pdf'},
    ],
    "fidelity": 'A general tabu search with reassign and swap moves; the paper is a representative use of tabu search for transport-robot scheduling.',
    "params": {
        "iterations": {"type": "int", "min": 1, "max": 1000, "default": 80},
        "tenure": {"type": "int", "min": 1, "max": 50, "default": 7},
        "seed": {"type": "int", "min": 0, "max": 99999, "default": 1},
    },
}


def allocate(scenario, travel_times, state, feedback, params, tools):
    from . import greedy
    iters = int(params.get("iterations", 80))
    tenure = int(params.get("tenure", 7))
    cur = greedy.allocate(scenario, travel_times, state, feedback, {}, tools)
    tasks = [t["id"] for t in tools.pending_tasks()]
    if len(cur) != len(tasks):
        return cur
    elig = {tid: tools.eligible(tid) for tid in tasks}

    def cost(a):
        tools.check_time()
        res = tools.schedule(a)
        return res["makespan"] if res["ok"] else 10 ** 9

    best, best_c = cur, cost(cur)
    cur_c = best_c
    tabu = {}
    for it in range(iters):
        moves = []
        for i, a in enumerate(cur):
            for r in elig[a["task"]]:
                if r != a["robot"]:
                    moves.append((("robot", a["task"], r), [dict(x) if x is not a else {"task": a["task"], "robot": r} for x in cur]))
            if i + 1 < len(cur):
                n = [dict(x) for x in cur]
                n[i], n[i + 1] = n[i + 1], n[i]
                moves.append((("swap", cur[i]["task"], cur[i + 1]["task"]), n))
        cand = None
        for key, sol in moves:
            c = cost(sol)
            if tabu.get(key, -1) >= it and c >= best_c:     # tabu unless it beats the best
                continue
            if cand is None or c < cand[0]:
                cand = (c, key, sol)
        if cand is None:
            break
        cur_c, key, cur = cand
        tabu[key] = it + tenure
        if cur_c < best_c:
            best, best_c = cur, cur_c
    return best
