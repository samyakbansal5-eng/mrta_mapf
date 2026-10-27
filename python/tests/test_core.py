import pytest

from conftest import load_scenario, TINY
from bench.core import scenario as S, grid as G, validators as V
from bench.core.tools import Tools
from bench.core.tasks import make_tasks
from bench.mapf import lowlevel as L


def test_sample_scenarios_are_valid():
    for name in ("small_factory", "small_factory_events"):
        assert S.validate(S.load(load_scenario(name))) == []


def test_validate_catches_problems():
    sc = load_scenario("small_factory")
    bad = S.load(sc)
    bad["robots"][1]["start"] = bad["robots"][0]["start"]
    assert any("same cell" in i["msg"] for i in S.validate(bad))
    bad = S.load(sc)
    bad["products"][0]["weight"] = 99
    assert any("no robot can carry" in i["msg"] for i in S.validate(bad))
    bad = S.load(sc)
    bad["products"][0]["route"] = ["M9"]
    assert any("unknown station" in i["msg"] for i in S.validate(bad))
    walled = S.load(TINY)
    walled["grid"] = ["#######", "#.#...#", "#######"]
    walled["robots"][0]["start"] = (3, 1)
    assert any("not reachable" in i["msg"] for i in S.validate(walled))


def test_parse_ascii():
    d = S.parse_ascii("#####\n#R.1#\n#..F#\n#####")
    assert d["stations"] == {"RM": (1, 1), "M1": (3, 1), "FG": (3, 2)}
    assert d["grid"][1] == "#...#"


def test_tasks_follow_routes():
    sc = S.load(load_scenario("small_factory"))
    t = make_tasks(sc)
    assert len(t) == 9
    p1 = [x for x in t if x["product"] == "P1"]
    assert [(x["from"], x["to"]) for x in p1] == [("RM", "M1"), ("M1", "M2"), ("M2", "M4"), ("M4", "FG")]
    assert p1[-1]["last"] and p1[-1]["process"] == 0


def test_distance_and_blocked_source():
    sc = S.load(TINY)
    tl = Tools(sc)
    assert tl.dist("RM", "M1") == 2
    tl.state["blocked"] = {(2, 1)}
    assert tl.dist("RM", "M1") == G.INF               # corridor is cut
    tl.state["blocked"] = {(3, 1)}                    # robot standing on a just-blocked cell may leave
    assert tl.dist((3, 1), "FG") == 2


def test_conflict_detection():
    vertex = {"A": [(0, 0, 0), (1, 0, 1)], "B": [(2, 0, 0), (1, 0, 1)]}
    assert [c["type"] for c in V.find_conflicts(vertex)] == ["vertex"]
    swap = {"A": [(0, 0, 0), (1, 0, 1)], "B": [(1, 0, 0), (0, 0, 1)]}
    assert [c["type"] for c in V.find_conflicts(swap)] == ["edge"]
    follow = {"A": [(1, 0, 0), (2, 0, 1)], "B": [(0, 0, 0), (1, 0, 1)]}
    assert V.find_conflicts(follow) == []


def prob(sc, legs, robots, blocked=()):
    p = {"grid": sc["grid"], "t0": 0, "blocked": [list(b) for b in blocked], "robots": robots, "legs": legs, "horizon": 200}
    return L.prepare(p)


def test_st_astar_shortest_and_speed():
    sc = S.load(TINY)
    p = prob(sc, {}, {})
    assert L.st_astar(p, (1, 1), 0, (5, 1), 0, 1, set(), set(), {})[-1] == (5, 1, 4)
    assert L.st_astar(p, (1, 1), 0, (5, 1), 0, 2, set(), set(), {})[-1] == (5, 1, 8)   # half speed


def test_st_astar_waits_for_constraint_and_reports_unreachable():
    sc = S.load(TINY)
    p = prob(sc, {}, {})
    path = L.st_astar(p, (1, 1), 0, (3, 1), 0, 1, {((2, 1), 1)}, set(), {})
    assert path[-1][2] == 3 and (1, 1, 1) in path       # waited one step
    p2 = prob(sc, {}, {}, blocked=[(2, 1)])
    assert L.st_astar(p2, (1, 1), 0, (5, 1), 0, 1, set(), set(), {}) is None


def test_st_astar_release_lets_a_waiting_robot_step_aside():
    sc = S.load({**TINY, "grid": ["#####", "#...#", "#.#.#", "#####"], "stations": {"RM": [1, 1], "M1": [3, 1], "FG": [3, 2]}})
    p = prob(sc, {}, {})
    # robot must lift at its start cell at t>=6 but cell (1,1) is taken at t=3..4: it must dodge to (2,1)/(1,2)
    vc = {((1, 1), 3), ((1, 1), 4)}
    path = L.st_astar(p, (1, 1), 0, (3, 1), 6, 1, vc, set(), {})
    assert path is not None
    assert not any((x, y, t) in [(1, 1, 3), (1, 1, 4)] for x, y, t in path)
    assert (1, 1, 6) in path or any((x, y) == (1, 1) and t >= 6 for x, y, t in path)


def test_tiny_schedule_by_hand():
    from bench.mrta import greedy
    sc = S.load(TINY)
    tl = Tools(sc)
    a = greedy.allocate(sc, None, tl.state, {}, {}, tl)
    res = tl.schedule(a)
    # approach RM 1 step, carry to M1 2 steps (arrive 3), machine 3..7, carry to FG 2 steps -> 9
    assert res["ok"] and res["makespan"] == 9
    e = res["entries"]
    assert (e["T1"]["carry"]["start"], e["T1"]["carry"]["arrive"]) == (1, 3)
    assert (e["T1"]["machine"]["start"], e["T1"]["machine"]["end"]) == (3, 7)
    assert (e["T2"]["carry"]["start"], e["T2"]["carry"]["arrive"]) == (7, 9)


def test_path_validator_catches_illegal_paths():
    sc = S.load(TINY)
    bad = {"A": [(1, 1, 0), (3, 1, 1)]}                                  # jumps two cells
    assert "jump" in {i["type"] for i in V.validate_paths(sc, bad)}
    bad = {"A": [(1, 1, 0), (0, 1, 1)]}                                  # into a wall
    assert "wall" in {i["type"] for i in V.validate_paths(sc, bad)}
    sc2 = S.load({**TINY, "robots": [{"id": "A", "start": [1, 1], "step_cost": 2}]})
    fast = {"A": [(1, 1, 0), (2, 1, 1), (3, 1, 2)]}                      # half-speed robot moving every step
    assert "too_fast" in {i["type"] for i in V.validate_paths(sc2, fast)}
    ok = {"A": [(1, 1, 0), (1, 1, 1), (2, 1, 2), (2, 1, 3), (3, 1, 4)]}
    assert V.validate_paths(sc2, ok) == []
    blocked = [{"cells": [[3, 1]], "from": 0, "until": 10}]
    enter = {"A": [(2, 1, 0), (3, 1, 1)]}
    assert "blocked_cell" in {i["type"] for i in V.validate_paths(sc, enter, blocked)}
    failed = {"X": {"cell": [3, 1], "from": 0}}
    assert "failed_robot_cell" in {i["type"] for i in V.validate_paths(sc, {"A": [(2, 1, 0), (3, 1, 1)]}, (), failed)}
