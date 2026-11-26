INFO = {
    "name": "TeSSI (temporal sequential single-item auction)",
    "module": "mrta",
    "description": "Auction in rounds: each robot bids its new makespan after fitting the task into the best slot of its timetable; the lowest bid wins.",
    "about": "An auctioneer offers all unassigned tasks. Every robot tries each task at every position of its own timetable (a temporal network of travel and processing times) and bids the makespan it would have after the insertion. The single lowest bid over all tasks and robots wins; the winner inserts the task, and the next round starts. TeSSIduo bids a mix of makespan and travel distance instead. Compared with a plain sequential auction that only appends tasks, inserting into the timetable lets robots fill idle gaps, which matters when products wait for machines.",
    "papers": [
        {"title": "Multi-robot Auctions for Allocation of Tasks with Temporal Constraints", "authors": "E. Nunes, M. Gini", "year": 2015, "venue": "AAAI 2015", "url": "https://www-users.cs.umn.edu/~gini/papers/Nunes2015aaai.pdf"},
        {"title": "The Power of Sequential Single-Item Auctions for Agent Coordination", "authors": "S. Koenig et al.", "year": 2006, "venue": "AAAI 2006", "url": "https://cdn.aaai.org/AAAI/2006/AAAI06-266.pdf"},
    ],
    "fidelity": "Auction rounds and insertion-based bids as in the paper's Algorithms 1-3. The robot's timetable is evaluated with the bench's schedule builder (machines, product order) instead of a Floyd-Warshall temporal network; our tasks have no time windows, so the window checks are not needed.",
    "params": {
        "bid": {"type": "choice", "options": ["makespan (TeSSI)", "makespan+distance (TeSSIduo)"], "default": "makespan (TeSSI)"},
        "alpha": {"type": "float", "min": 0.0, "max": 1.0, "default": 0.5},
        "max_positions": {"type": "int", "min": 1, "max": 50, "default": 6},
    },
}

from ._seq import Seq, regret_insert


def allocate(scenario, travel_times, state, feedback, params, tools):
    S = Seq(tools, state)
    duo = params.get("bid", "").startswith("makespan+")
    a = float(params.get("alpha", 0.5))

    def bid(seqs, r, i, tid, cost):
        if not duo:
            return cost
        t = S.pending[tid]
        robot = tools.robot(r)
        prev_cell = robot["start"] if i == 0 else tools.cellof(S.pending[seqs[r][i - 1]]["to"])
        d = tools.dist(tuple(prev_cell), tools.pickup_cell(t)) + tools.dist(tools.pickup_cell(t), tools.cellof(t["to"]))
        return a * cost + (1 - a) * d * robot["step_cost"]

    seqs = regret_insert(S, S.empty(), list(S.pending), int(params.get("max_positions", 6)), use_regret=False, bid=bid)
    return S.finish(seqs) if seqs else []
