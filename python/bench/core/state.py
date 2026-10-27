"""Execution state: a snapshot of the factory at time t, used to (re)plan after events."""
from .tasks import make_tasks


def initial_state(sc):
    tasks = make_tasks(sc)
    return {
        "t": 0,
        "robots": {r["id"]: {"pos": r["start"], "status": "ok", "available": True, "on_floor": False}
                   for r in sc["robots"]},
        "tasks": {t["id"]: {"status": "pending", "robot": None, "from_cell": None} for t in tasks},
        "machine_free": {m: 0 for m in sc["stations"]},
        "product_ready": {p["id"]: 0 for p in sc["products"]},
        "blocked": set(),
    }


def copy_state(st):
    return {
        "t": st["t"],
        "robots": {k: dict(v) for k, v in st["robots"].items()},
        "tasks": {k: dict(v) for k, v in st["tasks"].items()},
        "machine_free": dict(st["machine_free"]),
        "product_ready": dict(st["product_ready"]),
        "blocked": set(st["blocked"]),
    }
