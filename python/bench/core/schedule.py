"""Schedule builder: turns an ordered robot assignment into start/finish times.

Model (all times in time steps):
  * a robot first drives EMPTY from where it is to the pickup (approach), waits there until the
    product is ready, then CARRIES it to the destination;
  * a machine processes one product at a time, starting when the product has arrived and the
    machine is free;
  * the next hop of a product can start only when the previous machine has finished it.
Leg duration = cells * robot.step_cost, unless an observed (longer) duration from the path
planner is supplied.
"""
from .grid import INF


def build_schedule(ctx, assignment, observed=None):
    """ctx: Tools-like object with .sc, .state, .tasks, .dist(a, b), .cellof(x).

    assignment: ordered list of {"task": id, "robot": id}; locked (already carrying) tasks are
    scheduled first automatically. Order is a priority list: a task whose predecessor is not yet
    scheduled is deferred, so any permutation is decodable.
    Returns dict: ok, makespan, entries (per task), reason.
    """
    observed = observed or {}
    sc, st = ctx.sc, ctx.state
    step = {r["id"]: r["step_cost"] for r in sc["robots"]}
    robot_t = {rid: st["t"] for rid in step}
    robot_loc = {rid: st["robots"][rid]["pos"] for rid in step}
    mfree = dict(st["machine_free"])
    pready = dict(st["product_ready"])
    entries = {}
    by_id = ctx.tasks_by_id
    done_tasks = {tid for tid, s in st["tasks"].items() if s["status"] == "done"}
    scheduled = set(done_tasks)

    def dur(rid, a, b, key):
        d = ctx.dist(a, b)
        if d >= INF:
            return INF
        base = d * step[rid]
        return max(base, observed.get(key, 0))

    def run_task(task, rid, loc_from, locked):
        pickup = loc_from
        park = None
        ap_from = list(robot_loc[rid])
        dest = ctx.cellof(task["to"])
        if locked:
            ap_start = ap_arr = robot_t[rid]
            carry_start = robot_t[rid]
        else:
            floor = getattr(ctx, "floors", {}).get((task["id"], "carry"), 0)
            need = max(pready[task["product"]], floor)          # earliest the product can be lifted
            loc = robot_loc[rid]
            ad = dur(rid, loc, pickup, (task["id"], "approach"))
            if ad >= INF:
                return "unreachable pickup for " + task["id"]
            home = ctx.homes[rid]
            # Idle for a long time? Go to the parking bay and come back just in time, so the
            # robot does not sit on a dock or aisle that others need.
            if need - ad - robot_t[rid] > 0 and loc != home:
                d1 = dur(rid, loc, home, (task["id"], "park"))
                d2 = dur(rid, home, pickup, (task["id"], "approach"))
                if d1 < INF and d2 < INF and need - d2 - (robot_t[rid] + d1) >= 4:
                    park = {"start": robot_t[rid], "arrive": robot_t[rid] + d1, "from": list(loc), "to": list(home)}
                    loc = home
                    ad = d2
                    robot_t[rid] = park["arrive"]
            # just-in-time: do not arrive long before the product is ready
            ap_start = max(robot_t[rid], need - ad)
            ap_arr = ap_start + ad
            ap_from = list(loc)
            carry_start = max(ap_arr, need)
        cd = dur(rid, pickup if not locked else robot_loc[rid], dest, (task["id"], "carry"))
        if cd >= INF:
            return "unreachable destination for " + task["id"]
        carry_arr = carry_start + cd
        m = task["to"]
        if task["last"] and task["process"] == 0:
            m_start = m_end = carry_arr
            machine = None
        else:
            m_start = max(carry_arr, mfree.get(m, 0))
            m_end = m_start + task["process"]
            mfree[m] = m_end
            machine = m
        pready[task["product"]] = m_end
        entries[task["id"]] = {
            "task": task["id"], "product": task["product"], "robot": rid,
            "from": task["from"], "to": task["to"], "locked": locked,
            "approach": {"start": ap_start, "arrive": ap_arr, "from": ap_from, "to": list(pickup)}, "park": park,
            "carry": {"start": carry_start, "arrive": carry_arr, "from": list(pickup if not locked else robot_loc[rid]), "to": list(dest)},
            "machine": {"name": machine, "start": m_start, "end": m_end},
        }
        robot_t[rid] = carry_arr
        robot_loc[rid] = dest
        scheduled.add(task["id"])
        return None

    # tasks already being carried by a healthy robot continue first
    for tid, s in st["tasks"].items():
        if s["status"] == "carrying" and st["robots"][s["robot"]]["status"] == "ok":
            reason = run_task(by_id[tid], s["robot"], robot_loc[s["robot"]], True)
            if reason:
                return {"ok": False, "reason": reason, "makespan": INF, "entries": entries}

    queue = list(assignment)
    while queue:
        progressed = False
        for i, a in enumerate(queue):
            task = by_id[a["task"]]
            if task["k"] > 0:
                prev = ctx.prev_task(task)
                if prev["id"] not in scheduled:
                    continue
            pickup = ctx.pickup_cell(task)
            reason = run_task(task, a["robot"], pickup, False)
            if reason:
                return {"ok": False, "reason": reason, "makespan": INF, "entries": entries}
            queue.pop(i)
            progressed = True
            break
        if not progressed:
            return {"ok": False, "reason": "assignment misses a predecessor task", "makespan": INF, "entries": entries}
    ends = [e["machine"]["end"] for e in entries.values()]
    ends += [pready[p] for p in pready]
    return {"ok": True, "makespan": max(ends) if ends else st["t"], "entries": entries, "reason": ""}
