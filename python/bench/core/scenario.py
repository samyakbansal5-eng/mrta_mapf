"""Scenario model: plain dicts (JSON-friendly) plus loading, ASCII import and validation."""
import json
from .grid import cell, is_wall, bfs_dist, size

DEFAULTS = {"time_step_seconds": 1, "raw_material": "RM", "finished_goods": "FG"}


def load(data):
    """Accept a dict or a JSON string; return a normalised scenario dict."""
    sc = json.loads(data) if isinstance(data, str) else json.loads(json.dumps(data))
    for k, v in DEFAULTS.items():
        sc.setdefault(k, v)
    sc.setdefault("events", [])
    sc.setdefault("machines", {})
    sc["grid"] = [str(r) for r in sc["grid"]]
    sc["stations"] = {k: cell(v) for k, v in sc["stations"].items()}
    for r in sc["robots"]:
        r.setdefault("step_cost", 1)
        r.setdefault("payload", 10 ** 6)
        r.setdefault("can_carry", None)
        s = r["start"]
        r["start"] = sc["stations"][s] if isinstance(s, str) else cell(s)
    for p in sc["products"]:
        p.setdefault("weight", 0)
        p.setdefault("process_time", {})
    return sc


def station_cell(sc, name):
    return sc["stations"][name]


def parse_ascii(text, legend=None):
    """Turn an ASCII drawing into grid + stations.

    '#' wall, '.' free, 'R' raw material (RM), 'F' finished goods (FG), digits 1-9 = M1..M9.
    `legend` maps extra characters to station names. Everything else is free floor.
    """
    legend = dict(legend or {})
    rows = [ln.rstrip("\n") for ln in text.splitlines() if ln.strip()]
    width = max(len(r) for r in rows)
    grid, stations = [], {}
    for y, row in enumerate(rows):
        out = []
        for x, ch in enumerate(row.ljust(width, "#")):
            if ch == "#":
                out.append("#")
                continue
            name = legend.get(ch) or {"R": "RM", "F": "FG"}.get(ch) or (f"M{ch}" if ch.isdigit() and ch != "0" else None)
            if name:
                stations[name] = (x, y)
            out.append(".")
        grid.append("".join(out))
    return {"grid": grid, "stations": stations}


def validate(sc):
    """Return a list of {'level': 'error'|'warning', 'msg': str}."""
    issues = []

    def err(m):
        issues.append({"level": "error", "msg": m})

    def warn(m):
        issues.append({"level": "warning", "msg": m})

    grid = sc["grid"]
    if len({len(r) for r in grid}) != 1:
        err("grid rows have different lengths")
        return issues
    w, h = size(grid)
    for name, c in sc["stations"].items():
        if is_wall(grid, c):
            err(f"station {name} at {c} is on a wall or outside the grid")
    names = set(sc["stations"])
    for p in sc["products"]:
        for m in p["route"]:
            if m not in names:
                err(f"product {p['id']} route uses unknown station {m}")
            if m not in p["process_time"]:
                warn(f"product {p['id']} has no process time at {m} (0 assumed)")
    if sc["raw_material"] not in names:
        err("raw-material station missing")
    starts = [r["start"] for r in sc["robots"]]
    if len(set(starts)) != len(starts):
        err("two robots start on the same cell")
    for r in sc["robots"]:
        if is_wall(grid, r["start"]):
            err(f"robot {r['id']} starts on a wall")
        if r["step_cost"] < 1 or int(r["step_cost"]) != r["step_cost"]:
            err(f"robot {r['id']}: step_cost must be a whole number >= 1")
    for p in sc["products"]:
        if not any(robot_can_carry(r, p) for r in sc["robots"]):
            err(f"no robot can carry product {p['id']}")
    if not any(e for e in issues if e["level"] == "error"):
        base = sc["stations"][sc["raw_material"]]
        reach = bfs_dist(grid, base)
        for name, c in sc["stations"].items():
            if c not in reach:
                err(f"station {name} is not reachable from {sc['raw_material']}")
        for r in sc["robots"]:
            if r["start"] not in reach:
                err(f"robot {r['id']} start is not connected to the factory floor")
    return issues


def robot_can_carry(robot, product):
    if product.get("weight", 0) > robot.get("payload", 10 ** 6):
        return False
    cc = robot.get("can_carry")
    return cc is None or product["id"] in cc
