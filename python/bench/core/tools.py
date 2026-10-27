"""Shared helper library handed to every plug-in, so algorithm files contain only the idea."""
import random
import time

from . import grid as G
from .tasks import make_tasks, eligible_robots
from .schedule import build_schedule
from .state import initial_state


class Tools:
    def __init__(self, sc, state=None, deadline=None, seed=0):
        self.sc = sc
        self.state = state or initial_state(sc)
        self.tasks = make_tasks(sc)
        self.tasks_by_id = {t["id"]: t for t in self.tasks}
        self.grid = sc["grid"]
        self.deadline = deadline          # absolute time.monotonic() value, or None
        self.seed = seed
        self._dist = {}
        self.observed = {}
        self.floors = {}
        self.homes = {r["id"]: r["start"] for r in sc["robots"]}

    # ---- time limit (soft; the browser worker also hard-kills) ----
    def check_time(self):
        if self.deadline is not None and time.monotonic() > self.deadline:
            raise TimeoutError("algorithm exceeded its time limit")

    def rng(self, salt=0):
        return random.Random(self.seed * 1000003 + salt)

    # ---- map ----
    def cellof(self, x):
        return self.sc["stations"][x] if isinstance(x, str) else G.cell(x)

    def neighbours(self, c):
        return G.neighbours(self.grid, c, self.state["blocked"])

    def _dist_map(self, goal):
        key = (goal, frozenset(self.state["blocked"]))
        if key not in self._dist:
            self._dist[key] = G.bfs_dist(self.grid, goal, self.state["blocked"])
        return self._dist[key]

    def dist(self, a, b):
        """Shortest path length in cells between two cells or station names (INF if unreachable).

        A robot standing on a cell that is blocked (it was blocked while the robot was on it) may leave.
        """
        a, m = self.cellof(a), self._dist_map(self.cellof(b))
        if a in m:
            return m[a]
        if a in self.state["blocked"]:
            ds = [m[n] for n in G.neighbours(self.grid, a, self.state["blocked"]) if n in m]
            if ds:
                return 1 + min(ds)
        return G.INF

    def travel_table(self):
        names = list(self.sc["stations"])
        return {a: {b: self.dist(a, b) for b in names} for a in names}

    # ---- tasks and robots ----
    def pending_tasks(self):
        return [t for t in self.tasks if self.state["tasks"][t["id"]]["status"] == "pending"]

    def prev_task(self, task):
        return next(t for t in self.tasks if t["product"] == task["product"] and t["k"] == task["k"] - 1)

    def pickup_cell(self, task):
        s = self.state["tasks"][task["id"]]
        return G.cell(s["from_cell"]) if s.get("from_cell") else self.cellof(task["from"])

    def eligible(self, task_id):
        return eligible_robots(self.sc, self.tasks_by_id[task_id], self.state)

    def robot(self, rid):
        return next(r for r in self.sc["robots"] if r["id"] == rid)

    # ---- scheduling ----
    def schedule(self, assignment, observed=None):
        return build_schedule(self, assignment, observed if observed is not None else self.observed)
