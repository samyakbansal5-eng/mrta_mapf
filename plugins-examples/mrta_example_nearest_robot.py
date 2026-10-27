"""MRTA template. Copy this file, change INFO and allocate(), then upload it in the Import tab.

allocate() returns an ORDERED list of {"task": id, "robot": id}. The bench works out the times
itself (tools.schedule), so you only decide WHO does WHAT and in which order.

Useful tools (all read-only):
  tools.pending_tasks()            tasks still to do (dicts with id, product, k, from, to, process)
  tools.eligible(task_id)          robot ids that can carry this task (payload, reach)
  tools.schedule(assignment)       try an assignment -> {"ok", "makespan", "entries": {task: {...}}}
  tools.dist(a, b)                 shortest walking distance in cells between two cells
  tools.robot(robot_id)            robot data (start, step_cost, payload, ...)
  tools.rng(seed)                  seeded random.Random
  tools.check_time()               call inside long loops so the time limit can stop you cleanly
"""
INFO = {
    "name": "Nearest robot (example)",
    "module": "mrta",
    "description": "Gives each task to the eligible robot whose start cell is closest to the pickup point.",
    "params": {},
}


def allocate(scenario, travel_times, state, feedback, params, tools):
    assignment = []
    for t in sorted(tools.pending_tasks(), key=lambda t: (t["k"], t["id"])):
        tools.check_time()
        options = tools.eligible(t["id"])
        if not options:
            continue
        pick = tools.pickup_cell(t)
        best = min(options, key=lambda r: (tools.dist(tuple(tools.robot(r)["start"]), pick), r))
        assignment.append({"task": t["id"], "robot": best})
    return assignment
