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
    _validate_ids_and_values(sc, err, warn)
    _validate_events(sc, err, warn)
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


def _dupes(ids):
    seen, out = set(), []
    for i in ids:
        if i in seen and i not in out:
            out.append(i)
        seen.add(i)
    return out


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _validate_ids_and_values(sc, err, warn):
    """Checks for things a hand-edited plan (Plan editor, or raw JSON) can get wrong."""
    if not sc["robots"]:
        err("the plan has no robots")
    if not sc["products"]:
        warn("the plan has no products, so there is nothing to transport")
    for d in _dupes([r["id"] for r in sc["robots"]]):
        err(f"robot id {d} is used more than once")
    for d in _dupes([p["id"] for p in sc["products"]]):
        err(f"product id {d} is used more than once")
    cells = {}
    for name, c in sc["stations"].items():
        if c in cells:
            warn(f"stations {cells[c]} and {name} share the cell {list(c)}")
        cells.setdefault(c, name)
    if sc.get("finished_goods") not in sc["stations"]:
        warn("no finished-goods station (FG): products end at their last machine")
    product_ids = {p["id"] for p in sc["products"]}
    stores = {sc.get("raw_material"), sc.get("finished_goods")}
    for r in sc["robots"]:
        if not _num(r.get("payload")) or r["payload"] < 0:
            err(f"robot {r['id']}: payload must be a number >= 0")
        cc = r.get("can_carry")
        if cc is not None:
            if not cc:
                warn(f"robot {r['id']} may carry no product, so it will never be used")
            for pid in cc:
                if pid not in product_ids:
                    warn(f"robot {r['id']} lists unknown product {pid} in can_carry")
    for p in sc["products"]:
        if not p["route"]:
            err(f"product {p['id']} has an empty route")
        if not _num(p.get("weight")) or p["weight"] < 0:
            err(f"product {p['id']}: weight must be a number >= 0")
        for m in p["route"]:
            if m in stores:
                err(f"product {p['id']} route uses store {m}; routes list machines only (RM and FG are added automatically)")
        for m, v in p["process_time"].items():
            if not _num(v) or v < 0 or int(v) != v:
                err(f"product {p['id']}: process time at {m} must be a whole number >= 0")


def _validate_events(sc, err, warn):
    robot_ids = {r["id"] for r in sc["robots"]}
    grid = sc["grid"]
    for i, e in enumerate(sc.get("events", [])):
        label = f"event {i + 1} ({e.get('type', '?')})"
        t = e.get("t")
        if not _num(t) or t < 0 or int(t) != t:
            err(f"{label}: time t must be a whole number >= 0")
            continue
        kind = e.get("type")
        if kind in ("robot_failure", "robot_recovered"):
            if e.get("robot") not in robot_ids:
                err(f"{label}: unknown robot {e.get('robot')}")
        elif kind == "block_cells":
            cells = e.get("cells") or []
            if not cells:
                err(f"{label}: no cells to block")
            for c in cells:
                try:
                    cc = cell(c)
                except (TypeError, ValueError, IndexError):
                    err(f"{label}: {c} is not an [x, y] cell")
                    continue
                if is_wall(grid, cc):
                    warn(f"{label}: cell {list(cc)} is a wall or outside the grid")
            u = e.get("until")
            if u is not None and (not _num(u) or u <= t):
                err(f"{label}: 'until' must be later than t (or empty for permanent)")
        else:
            err(f"{label}: unknown event type (use block_cells, robot_failure or robot_recovered)")


def robot_can_carry(robot, product):
    if product.get("weight", 0) > robot.get("payload", 10 ** 6):
        return False
    cc = robot.get("can_carry")
    return cc is None or product["id"] in cc
