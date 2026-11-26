"""Helpers for MRTA algorithms that build one task sequence per robot.

A solution is {robot_id: [task_id, ...]}. The bench's schedule builder takes one ordered list,
so `to_assignment` merges the robot sequences while respecting product order (hop k needs hop
k-1 done). If two robots' sequences wait for each other (a cycle), the merge fails and the
solution is infeasible, which is the acyclicity check used by Bischoff et al.
"""
INF = 10 ** 9


class Seq:
    def __init__(self, tools, state, robots=None):
        self.tools = tools
        self.pending = {t["id"]: t for t in tools.pending_tasks()}
        self.robots = robots or [r["id"] for r in tools.sc["robots"]
                                 if state["robots"][r["id"]]["status"] == "ok" and state["robots"][r["id"]].get("available", True)]
        self.elig = {tid: [r for r in tools.eligible(tid) if r in self.robots] for tid in self.pending}
        self.prev = {}
        for tid, t in self.pending.items():
            if t["k"] > 0:
                p = tools.prev_task(t)["id"]
                if p in self.pending:
                    self.prev[tid] = p

    def empty(self):
        return {r: [] for r in self.robots}

    def to_assignment(self, seqs):
        heads = {r: 0 for r in seqs}
        out, placed = [], set()
        total = sum(len(s) for s in seqs.values())
        while len(out) < total:
            best = None
            for r, s in seqs.items():
                i = heads[r]
                if i >= len(s):
                    continue
                tid = s[i]
                p = self.prev.get(tid)
                if p is not None and p not in placed:
                    continue
                key = (i, self.pending[tid]["k"], r)
                if best is None or key < best[0]:
                    best = (key, r, tid)
            if best is None:
                return None                          # sequences wait for each other: infeasible
            _, r, tid = best
            out.append({"task": tid, "robot": r})
            placed.add(tid)
            heads[r] += 1
        return out

    def evaluate(self, seqs, objective="makespan"):
        """(cost, schedule) for a (possibly partial but precedence-closed) solution."""
        self.tools.check_time()
        a = self.to_assignment(seqs)
        if a is None:
            return INF, None
        res = self.tools.schedule(a)
        if not res["ok"]:
            return INF, None
        if objective == "average":
            ends = [e["machine"]["end"] for e in res["entries"].values()]
            return (sum(ends) / len(ends) if ends else 0), res
        if objective == "travel":
            tr = sum((e["carry"]["arrive"] - e["carry"]["start"]) + (e["approach"]["arrive"] - e["approach"]["start"])
                     for e in res["entries"].values())
            return res["makespan"] + tr / 1000.0, res
        ends = [e["machine"]["end"] for e in res["entries"].values()]
        return res["makespan"] + (sum(ends) / 1e6 if ends else 0), res   # tiny tie-break on total finish

    def executable(self, seqs, unassigned):
        assigned = {t for s in seqs.values() for t in s}
        return [t for t in unassigned if self.prev.get(t) is None or self.prev[t] in assigned]

    def positions(self, seqs, r, tid, max_positions=None):
        """Insertion positions for tid in robot r's sequence (never before its predecessor on r)."""
        s = seqs[r]
        lo = 0
        p = self.prev.get(tid)
        if p in s:
            lo = s.index(p) + 1
        pos = list(range(lo, len(s) + 1))
        if max_positions and len(pos) > max_positions:
            pos = pos[-max_positions:]
        return pos

    @staticmethod
    def insert(seqs, r, i, tid):
        n = {k: list(v) for k, v in seqs.items()}
        n[r].insert(i, tid)
        return n

    def remove_with_successors(self, seqs, tids):
        """Remove tasks and, so the rest stays precedence-closed, every later hop of the same product."""
        drop = set(tids)
        changed = True
        while changed:
            changed = False
            for t, p in self.prev.items():
                if p in drop and t not in drop:
                    drop.add(t)
                    changed = True
        return {r: [t for t in s if t not in drop] for r, s in seqs.items()}, drop

    def finish(self, seqs):
        a = self.to_assignment(seqs)
        return a if a is not None else []


def regret_insert(S, seqs, unassigned, max_positions, relative=True, use_regret=True, bid=None):
    """Insert all unassigned tasks one at a time.

    use_regret=True: RMCA rule (task with the largest regret first). False: cheapest bid first (SSI/TeSSI).
    bid(seqs, r, i, tid, cost) can change the bid value (e.g. TeSSIduo mixes in distance).
    Returns the new seqs, or None if some task cannot be placed.
    """
    unassigned = set(unassigned)
    while unassigned:
        S.tools.check_time()
        best_choice = None
        for tid in sorted(S.executable(seqs, unassigned)):
            opts = []
            for r in S.elig[tid]:
                for i in S.positions(seqs, r, tid, max_positions):
                    cand = S.insert(seqs, r, i, tid)
                    c, _ = S.evaluate(cand)
                    if c >= INF:
                        continue
                    v = bid(seqs, r, i, tid, c) if bid else c
                    opts.append((v, r, i))
            if not opts:
                continue
            opts.sort()
            b = opts[0][0]
            if use_regret:
                second = opts[1][0] if len(opts) > 1 else b + 10 ** 6
                regret = (second - b) / max(b, 1e-9) if relative else (second - b)
                key = (-regret, b, tid)
            else:
                key = (b, tid)
            if best_choice is None or key < best_choice[0]:
                best_choice = (key, tid, opts[0][1], opts[0][2])
        if best_choice is None:
            return None
        _, tid, r, i = best_choice
        seqs = S.insert(seqs, r, i, tid)
        unassigned.discard(tid)
    return seqs
