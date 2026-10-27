"""Transport tasks: one per hop of a product's route (raw material -> M.. -> finished goods)."""
from .scenario import robot_can_carry


def make_tasks(sc):
    """Return the ordered list of transport tasks for all products.

    Each task: id, product, k (hop index), from/to station names, process = time spent on the
    destination machine (0 for finished goods). Task k of a product needs task k-1 done first.
    """
    tasks = []
    fg = sc.get("finished_goods")
    n = 0
    for p in sc["products"]:
        stops = [sc["raw_material"]] + list(p["route"])
        if fg and fg in sc["stations"]:
            stops.append(fg)
        for k in range(len(stops) - 1):
            n += 1
            dest = stops[k + 1]
            tasks.append({
                "id": f"T{n}", "product": p["id"], "k": k, "from": stops[k], "to": dest,
                "process": 0 if dest == fg else p["process_time"].get(dest, 0),
                "last": k == len(stops) - 2,
            })
    return tasks


def eligible_robots(sc, task, state=None):
    prod = next(p for p in sc["products"] if p["id"] == task["product"])
    out = []
    for r in sc["robots"]:
        if state is not None and state["robots"][r["id"]]["status"] != "ok":
            continue
        if state is not None and not state["robots"][r["id"]].get("available", True):
            continue
        if robot_can_carry(r, prod):
            out.append(r["id"])
    return out
