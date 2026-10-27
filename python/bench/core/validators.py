"""Checks run on every result, built-in or uploaded: collisions, path legality, schedule legality."""
from .grid import is_wall, cell


def find_conflicts(paths):
    """paths: {robot: [(x, y, t), ...]} with consecutive t. A robot is absent outside its listed times.

    Vertex conflict: two robots on the same cell at the same time.
    Edge (swap) conflict: two robots exchange cells in one step.
    Following (one robot enters a cell another just left) is allowed.
    """
    occ, moves, out = {}, {}, []
    for rid, p in paths.items():
        for i, (x, y, t) in enumerate(p):
            occ.setdefault(((x, y), t), []).append(rid)
            if i > 0:
                px, py, _ = p[i - 1]
                if (px, py) != (x, y):
                    moves.setdefault(((px, py), (x, y), t), []).append(rid)
    for (c, t), rs in occ.items():
        if len(rs) > 1:
            out.append({"type": "vertex", "robots": sorted(rs), "cell": list(c), "t": t})
    for (a, b, t), rs in moves.items():
        other = moves.get((b, a, t))
        if other and a < b:
            out.append({"type": "edge", "robots": sorted(set(rs + other)), "cell": [list(a), list(b)], "t": t})
    out.sort(key=lambda c: (c["t"], c["type"]))
    return out


def validate_paths(sc, paths, blocked_intervals=(), failed=None):
    """Legality of each path on its own (walls, steps, speed, blocked cells) + collisions.

    blocked_intervals: [{"cells": [[x, y]], "from": t, "until": t}]  (until may be None)
    failed: {robot: {"cell": [x, y], "from": t}} failed robots act as obstacles from time `from`.
    Returns list of issue dicts; empty list = valid.
    """
    issues = []
    step = {r["id"]: r["step_cost"] for r in sc["robots"]}
    for rid, p in paths.items():
        last_move = None
        for i, (x, y, t) in enumerate(p):
            if is_wall(sc["grid"], (x, y)):
                issues.append({"type": "wall", "robots": [rid], "cell": [x, y], "t": t})
            if i == 0:
                continue
            px, py, pt = p[i - 1]
            if t != pt + 1:
                issues.append({"type": "time_gap", "robots": [rid], "t": t})
            d = abs(x - px) + abs(y - py)
            if d > 1:
                issues.append({"type": "jump", "robots": [rid], "t": t})
            if d == 1:
                if last_move is not None and i - last_move < step[rid]:
                    issues.append({"type": "too_fast", "robots": [rid], "t": t})
                last_move = i
        for b in blocked_intervals:
            cells = {cell(c) for c in b["cells"]}
            for (x, y, t) in p:
                if (x, y) in cells and t >= b["from"] and (b.get("until") is None or t < b["until"]):
                    # a robot already standing there when it was blocked may leave
                    if t == b["from"] or (p[0][2] <= b["from"] and _stood_at(p, (x, y), b["from"])):
                        continue
                    issues.append({"type": "blocked_cell", "robots": [rid], "cell": [x, y], "t": t})
    for rid, f in (failed or {}).items():
        fc = cell(f["cell"])
        for other, p in paths.items():
            if other == rid:
                continue
            for (x, y, t) in p:
                if (x, y) == fc and t >= f["from"] and not f.get("allow_cell_for", {}).get(other):
                    issues.append({"type": "failed_robot_cell", "robots": [other, rid], "cell": [x, y], "t": t})
    issues.extend(find_conflicts(paths))
    return issues


def _stood_at(p, c, t0):
    """True if the path is on cell c continuously from time t0 up to the point it first leaves."""
    for (x, y, t) in p:
        if t == t0:
            return (x, y) == c
    return False


def validate_timeline(sc, entries, tasks_by_id):
    """Schedule-level legality on a finished timeline (dict task id -> entry)."""
    issues = []
    by_robot, by_machine = {}, {}
    for e in entries.values():
        by_robot.setdefault(e["robot"], []).append(e)
        m = e["machine"]
        if m["name"]:
            by_machine.setdefault(m["name"], []).append(m)
        t = tasks_by_id[e["task"]]
        if t["k"] > 0:
            prev = next((x for x in entries.values() if x["product"] == e["product"] and tasks_by_id[x["task"]]["k"] == t["k"] - 1), None)
            if prev and e["carry"]["start"] < prev["machine"]["end"]:
                issues.append({"type": "product_not_ready", "task": e["task"]})
    for rid, es in by_robot.items():
        es.sort(key=lambda e: (e["park"] or e["approach"])["start"])
        for a, b in zip(es, es[1:]):
            if (b["park"] or b["approach"])["start"] < a["carry"]["arrive"]:
                issues.append({"type": "robot_overlap", "robot": rid, "tasks": [a["task"], b["task"]]})
    for m, ms in by_machine.items():
        ms.sort(key=lambda x: x["start"])
        for a, b in zip(ms, ms[1:]):
            if b["start"] < a["end"]:
                issues.append({"type": "machine_overlap", "machine": m})
    return issues
