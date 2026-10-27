"""Runs MRTA and MAPF together: allocate -> schedule -> plan paths -> check -> feed delays back,
with rolling replanning when events (robot failure, blocked aisle) occur."""
import time

from .grid import INF, cell
from .state import initial_state, copy_state
from .tools import Tools
from .tasks import make_tasks
from .validators import find_conflicts, validate_paths, validate_timeline


class RunError(Exception):
    pass


# ----------------------------------------------------------------------------- events
def expand_events(sc):
    evs = []
    for e in sc.get("events", []):
        evs.append(dict(e))
        if e["type"] == "block_cells" and e.get("until") is not None:
            evs.append({"t": e["until"], "type": "unblock_cells", "cells": e["cells"]})
    evs.sort(key=lambda e: e["t"])
    return evs


# ----------------------------------------------------------------------------- one planning round-trip
def build_problem(sc, state, sched):
    legs = {}
    for e in sched["entries"].values():
        rl = legs.setdefault(e["robot"], [])
        tid = e["task"]
        if e.get("park"):
            rl.append({"id": tid + "/park", "task": tid, "kind": "park",
                       "from": e["park"]["from"], "to": e["park"]["to"], "release": e["park"]["start"]})
        if not e["locked"] and e["approach"]["from"] != e["approach"]["to"]:
            rl.append({"id": tid + "/approach", "task": tid, "kind": "approach",
                       "from": e["approach"]["from"], "to": e["approach"]["to"], "release": e["approach"]["start"]})
        rl.append({"id": tid + "/carry", "task": tid, "kind": "carry",
                   "from": e["carry"]["from"], "to": e["carry"]["to"], "release": e["carry"]["start"]})
    blocked = {tuple(c) for c in state["blocked"]}
    exempt = set()
    for rid, r in state["robots"].items():
        if r["status"] == "failed" and r.get("on_floor"):
            blocked.add(tuple(r["pos"]))
    for tid, s in state["tasks"].items():
        if s["status"] == "pending" and s.get("from_cell"):
            exempt.add(tuple(s["from_cell"]))
    gw, gh = len(sc["grid"][0]), len(sc["grid"])
    kmax = max(r["step_cost"] for r in sc["robots"])
    span = max([l["release"] for rl in legs.values() for l in rl] + [state["t"]]) - state["t"]
    return {
        "grid": sc["grid"], "t0": state["t"],
        "blocked": sorted(list(c) for c in blocked), "goal_exempt": sorted(list(c) for c in exempt),
        "robots": {rid: {"start": list(state["robots"][rid]["pos"]),
                         "step_cost": next(r["step_cost"] for r in sc["robots"] if r["id"] == rid)}
                   for rid in legs},
        "legs": legs, "horizon": span + gw * gh * kmax + 20,
    }


def evaluate(sc, state, sched, res, problem):
    """Replay the planner's answer: actual leg times, machine times, delays versus the schedule."""
    arrivals = res["arrivals"]
    act = {}
    for rid, legs in problem["legs"].items():
        t_prev = problem["t0"]
        for leg in legs:
            arr = arrivals[leg["id"]]
            start = max(leg["release"], t_prev)
            act.setdefault(leg["task"], {})[leg["kind"]] = {"start": start, "arrive": arr, "t_prev": t_prev}
            t_prev = arr
    entries = {}
    for tid, e in sched["entries"].items():
        e = {**e, "approach": dict(e["approach"]), "carry": dict(e["carry"]), "machine": dict(e["machine"]),
             "park": dict(e["park"]) if e.get("park") else None}
        a = act[tid]
        if "park" in a and e["park"]:
            e["park"]["start"], e["park"]["arrive"] = a["park"]["start"], a["park"]["arrive"]
        if "approach" in a:
            e["approach"]["start"], e["approach"]["arrive"] = a["approach"]["start"], a["approach"]["arrive"]
        elif not e["locked"]:
            tp = a["carry"]["t_prev"]
            e["approach"]["start"] = e["approach"]["arrive"] = tp
        e["carry"]["start"], e["carry"]["arrive"] = a["carry"]["start"], a["carry"]["arrive"]
        entries[tid] = e
    mfree = dict(state["machine_free"])
    for tid in sorted(entries, key=lambda t: (sched["entries"][t]["machine"]["start"], t)):
        e = entries[tid]
        m = e["machine"]
        task_proc = sched["entries"][tid]["machine"]["end"] - sched["entries"][tid]["machine"]["start"]
        if m["name"]:
            m["start"] = max(e["carry"]["arrive"], mfree.get(m["name"], 0))
            m["end"] = m["start"] + task_proc
            mfree[m["name"]] = m["end"]
        else:
            m["start"] = m["end"] = e["carry"]["arrive"]
    delayed = False
    observed = {}
    floors = {}
    ends = {tid: e["machine"]["end"] for tid, e in entries.items()}
    tasks = sc_tasks(sc)
    prev_of = {t["id"]: next(x["id"] for x in tasks if x["product"] == t["product"] and x["k"] == t["k"] - 1)
               for t in tasks if t["k"] > 0}
    for tid, e in entries.items():
        pt = prev_of.get(tid)
        if pt is not None:
            prev_end = ends[pt] if pt in ends else state["product_ready"][e["product"]]
            if e["carry"]["start"] < prev_end:
                floors[(tid, "carry")] = prev_end
    for tid, e in entries.items():
        p = sched["entries"][tid]
        if (e["carry"]["arrive"] > p["carry"]["arrive"] or e["approach"]["arrive"] > p["approach"]["arrive"]
                or e["machine"]["end"] > p["machine"]["end"]):
            delayed = True
        if "approach" in act[tid]:
            observed[(tid, "approach")] = e["approach"]["arrive"] - e["approach"]["start"]
        if "park" in act[tid]:
            observed[(tid, "park")] = act[tid]["park"]["arrive"] - act[tid]["park"]["start"]
        observed[(tid, "carry")] = e["carry"]["arrive"] - e["carry"]["start"]
    return entries, delayed, observed, floors


_TASK_CACHE = {}


def sc_tasks(sc):
    key = id(sc)
    if key not in _TASK_CACHE or _TASK_CACHE[key][0] is not sc:
        _TASK_CACHE.clear()
        _TASK_CACHE[key] = (sc, make_tasks(sc))
    return _TASK_CACHE[key][1]


def plan_segment(sc, state, mrta, mapf, opts, deadline):
    tools = Tools(sc, state, deadline, opts.get("seed", 0))
    pend = tools.pending_tasks()
    carrying = [t for t, s in state["tasks"].items() if s["status"] == "carrying"
                and state["robots"][s["robot"]]["status"] == "ok"]
    if not pend and not carrying:
        return {"ok": True, "empty": True, "entries": {}, "paths": {}, "rounds": []}
    observed, feedback, rounds = {}, {}, []
    last = None
    assignment = None
    for rd in range(int(opts.get("max_rounds", 12))):
        tools.observed = observed
        if assignment is None or rd < int(opts.get("mrta_rounds", 2)):
            assignment = mrta.allocate(sc, tools.travel_table(), state, feedback, opts.get("mrta_params", {}), tools)
        missing = {t["id"] for t in pend} - {a["task"] for a in assignment}
        if missing:
            return {"ok": False, "reason": "no eligible working robot for task(s) " + ", ".join(sorted(missing)), "rounds": rounds}
        sched = tools.schedule(assignment)
        if not sched["ok"]:
            return {"ok": False, "reason": "schedule infeasible: " + sched["reason"], "rounds": rounds}
        if mapf is None:                                            # MRTA-only mode
            return {"ok": True, "entries": sched["entries"], "paths": {}, "rounds": [{"round": rd + 1, "planned_makespan": sched["makespan"]}],
                    "assignment": assignment, "converged": True, "collisions": 0, "mapf_note": "MRTA only (no paths)"}
        problem = build_problem(sc, state, sched)
        res = mapf.plan(problem, state, opts.get("mapf_params", {}), tools)
        if res.get("failed") and last is not None:                  # keep the last working plan, flag it
            last["converged"] = False
            rounds.append({"round": rd + 1, "planned_makespan": sched["makespan"],
                           "note": "MAPF failed on the revised schedule; kept the previous round's paths"})
            break
        if res.get("failed"):
            return {"ok": False, "reason": "MAPF could not plan: " + ", ".join(res["failed"]) + " (" + res.get("note", "") + ")",
                    "rounds": rounds + [{"round": rd + 1, "planned_makespan": sched["makespan"], "note": res.get("note", "")}]}
        paths = {rid: [tuple(p) for p in pts] for rid, pts in res["paths"].items()}
        conflicts = find_conflicts(paths)
        entries, delayed, obs, floors = evaluate(sc, state, sched, res, problem)
        actual_mk = max([e["machine"]["end"] for e in entries.values()] or [state["t"]])
        rounds.append({"round": rd + 1, "planned_makespan": sched["makespan"], "actual_makespan": actual_mk,
                       "collisions": len(conflicts), "delayed": delayed, "note": res.get("note", "")})
        last = {"ok": True, "entries": entries, "paths": paths, "assignment": assignment,
                "collisions": len(conflicts), "mapf_note": res.get("note", ""), "problem": problem}
        rounds[-1]["early_departures"] = len(floors)
        # settled = no robot leaves a pickup before the product is really ready, and MRTA has had
        # its rounds to react to the delays the paths caused
        if not floors and (not delayed or rd + 1 >= int(opts.get("mrta_rounds", 2))):
            last["converged"] = True
            break
        feedback = {"round": rd + 1, "delays": {f"{k[0]}/{k[1]}": v for k, v in obs.items()}}
        for k, v in obs.items():
            observed[k] = max(observed.get(k, 0), v)
        for k, v in floors.items():
            tools.floors[k] = max(tools.floors.get(k, 0), v)
        last["converged"] = False
    last["rounds"] = rounds
    return last


# ----------------------------------------------------------------------------- state advance
def advance(sc, state, seg, te):
    new = copy_state(state)
    new["t"] = te
    pos = {rid: {p[2]: (p[0], p[1]) for p in pts} for rid, pts in seg["paths"].items()}
    done_entries = {}
    for tid, e in seg["entries"].items():
        s = new["tasks"][tid]
        if e["carry"]["arrive"] <= te:
            s.update(status="done", robot=e["robot"], from_cell=None)
            done_entries[tid] = e
            if e["machine"]["name"]:
                new["machine_free"][e["machine"]["name"]] = max(new["machine_free"][e["machine"]["name"]], e["machine"]["end"])
            new["product_ready"][e["product"]] = e["machine"]["end"]
        elif e["carry"]["start"] <= te:
            s.update(status="carrying", robot=e["robot"], from_cell=None, at=pos[e["robot"]].get(te))
        else:
            s.update(status="pending", robot=None)
    occupied = set()
    for rid, r in new["robots"].items():
        if r["status"] == "failed":
            continue
        p = pos.get(rid, {}).get(te)
        if p is not None:
            r["pos"] = p
            r["on_floor"] = True
            occupied.add(p)
        else:
            r["on_floor"] = False
    for rid, r in new["robots"].items():
        if not r["on_floor"] and r["status"] == "ok":
            home = next(x["start"] for x in sc["robots"] if x["id"] == rid)
            r["pos"] = home
            r["available"] = home not in occupied and home not in new["blocked"]
    return new, done_entries


def apply_event(sc, state, ev, failed_log, blocked_log):
    t = ev["t"]
    kind = ev["type"]
    msg = ""
    if kind == "robot_failure":
        r = state["robots"].get(ev["robot"])
        if r is None:
            return "ignored failure of unknown robot " + str(ev["robot"])
        r["status"] = "failed"
        r["available"] = False
        msg = f"{ev['robot']} failed at t={t}" + (f" on cell {list(r['pos'])}" if r["on_floor"] else " (off the floor)")
        for tid, s in state["tasks"].items():
            if s["status"] == "carrying" and s["robot"] == ev["robot"]:
                s.update(status="pending", robot=None, from_cell=s.get("at") or r["pos"])
                msg += f"; its product of {tid} is left on the cell"
        if r["on_floor"]:
            failed_log[ev["robot"]] = {"cell": list(r["pos"]), "from": t}
    elif kind == "robot_recovered":
        r = state["robots"].get(ev["robot"])
        if r and r["status"] == "failed":
            r["status"] = "ok"
            r["available"] = True
            msg = f"{ev['robot']} recovered at t={t}"
            if ev["robot"] in failed_log:
                failed_log[ev["robot"]]["until"] = t
    elif kind == "block_cells":
        for c in ev["cells"]:
            state["blocked"].add(cell(c))
        blocked_log.append({"cells": ev["cells"], "from": t, "until": ev.get("until")})
        msg = f"cells {ev['cells']} blocked at t={t}"
    elif kind == "unblock_cells":
        for c in ev["cells"]:
            state["blocked"].discard(cell(c))
        msg = f"cells {ev['cells']} open again at t={t}"
    else:
        msg = "unknown event " + str(kind)
    return msg


# ----------------------------------------------------------------------------- full run
def run(sc, mrta, mapf, opts=None):
    """mapf=None runs MRTA only. Returns a JSON-friendly result dict."""
    opts = dict(opts or {})
    started = time.monotonic()
    limit = opts.get("time_limit_s")
    deadline = started + limit if limit else None
    tasks = make_tasks(sc)
    by_id = {t["id"]: t for t in tasks}
    state = initial_state(sc)
    events = expand_events(sc) if mapf is not None else []
    history = {}
    records, log, rounds_all = {}, [], []
    failed_log, blocked_log = {}, []
    failure_reason = ""
    seg_no = 0
    collisions = 0
    converged = True
    while True:
        while events and events[0]["t"] <= state["t"]:
            log.append(apply_event(sc, state, events.pop(0), failed_log, blocked_log))
        seg_no += 1
        seg = plan_segment(sc, state, mrta, mapf, opts, deadline)
        for r in seg.get("rounds", []):
            rounds_all.append(dict(r, segment=seg_no))
        if not seg["ok"]:
            failure_reason = seg["reason"]
            log.append(f"planning failed at t={state['t']}: {failure_reason}")
            break
        if seg.get("empty"):
            break
        converged = converged and seg.get("converged", True)
        collisions = seg.get("collisions", 0)
        seg_end = max([e["machine"]["end"] for e in seg["entries"].values()] +
                      [p[-1][2] for p in seg["paths"].values()] + [state["t"]])
        te = events[0]["t"] if events else None
        final = te is None or seg_end <= te
        limit_t = None if final else te
        for rid, pts in seg["paths"].items():
            _commit(history, rid, [p for p in pts if limit_t is None or p[2] <= limit_t])
        if final:
            records.update(seg["entries"])
            break
        state, done = advance(sc, state, seg, te)
        records.update(done)
        log.append(f"t={te}: replanning; {sum(1 for s in state['tasks'].values() if s['status'] == 'done')} of {len(tasks)} tasks done")
    # ---- assemble result
    paths = {k: [list(p) for p in v] for k, v in history.items()}
    issues = []
    if mapf is not None:
        flat = {k: [tuple(p) for p in v] for k, v in history.items()}
        fl = {}
        for rid, f in failed_log.items():
            fl[rid] = dict(f, allow_cell_for={o: True for o in [r["id"] for r in sc["robots"]] if o != rid})
        issues = validate_paths(sc, flat, blocked_log, fl)
    t_issues = validate_timeline(sc, records, by_id) if records and not opts.get("mapf_only") else []
    missing = [t["id"] for t in tasks if t["id"] not in records]
    ok = not failure_reason and not missing and not issues and not t_issues
    moves = waits = 0
    for pts in paths.values():
        for a, b in zip(pts, pts[1:]):
            if (a[0], a[1]) == (b[0], b[1]):
                waits += 1
            else:
                moves += 1
    makespan = max([e["machine"]["end"] for e in records.values()] or [0])
    return {
        "ok": ok, "reason": failure_reason or ("tasks not completed: " + ", ".join(missing) if missing else ""),
        "makespan": makespan, "mode": "integrated" if mapf is not None else "mrta_only",
        "timeline": sorted(records.values(), key=lambda e: e["task"]),
        "paths": paths, "issues": issues + t_issues, "log": log, "rounds": rounds_all,
        "converged": converged,
        "warnings": sorted({r["note"] for r in rounds_all if "FELL BACK" in r.get("note", "")}),
        "events": {"failed": failed_log, "blocked": blocked_log},
        "metrics": {"makespan": makespan, "tasks_done": len(records), "tasks_total": len(tasks),
                    "collisions": len([i for i in issues if i["type"] in ("vertex", "edge")]),
                    "rule_violations": len(issues), "moves": moves, "waits": waits,
                    "replans": max(0, seg_no - 1), "rounds": len(rounds_all),
                    "runtime_ms": int((time.monotonic() - started) * 1000)},
        "tasks": tasks,
    }


def _commit(history, rid, pts):
    """Append executed points to a robot's history; start a new run (rid#2, ...) when it re-enters later."""
    if not pts:
        return
    runs = [k for k in history if k == rid or k.startswith(rid + "#")]
    if runs and history[runs[-1]][-1][2] == pts[0][2]:
        history[runs[-1]].extend(pts[1:])
    else:
        history[rid if not runs else f"{rid}#{len(runs) + 1}"] = list(pts)
