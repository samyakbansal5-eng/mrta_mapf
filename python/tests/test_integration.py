import json
import pytest

from conftest import load_scenario, TINY
from bench.core import api, plugins as P

MRTA = ["greedy", "auction", "genetic", "tabu"]
STATIC = load_scenario("small_factory")
EVENTS = load_scenario("small_factory_events")


def run(sc, mrta="greedy", mapf="prioritized", mode="integrated", **kw):
    req = {"scenario": sc, "mode": mode, "mrta": {"name": mrta}, "mapf": {"name": mapf}, "options": kw}
    return json.loads(api.run_json(json.dumps(req)))


def test_tiny_integrated_matches_hand_calculation():
    r = run(TINY)
    assert r["ok"] and r["makespan"] == 9 and r["metrics"]["collisions"] == 0


@pytest.mark.parametrize("mrta", MRTA)
@pytest.mark.parametrize("mapf", ["prioritized", "cbs"])
def test_collision_free_on_static_factory(mrta, mapf):
    r = run(STATIC, mrta, mapf, time_limit_s=120)
    assert r["ok"], r["reason"] or r["issues"][:3]
    assert r["metrics"]["collisions"] == 0 and r["metrics"]["tasks_done"] == 9
    assert r["issues"] == []


def test_independent_baseline_reports_collisions():
    r = run(STATIC, "greedy", "independent")
    assert not r["ok"] and r["metrics"]["collisions"] > 0


@pytest.mark.parametrize("mrta", MRTA)
def test_failure_and_blocked_aisle(mrta):
    r = run(EVENTS, mrta, "prioritized", time_limit_s=120)
    assert r["ok"], r["reason"] or r["issues"][:3]
    assert r["metrics"]["replans"] >= 1 and r["metrics"]["collisions"] == 0
    # R2 failed at t=16: it does no work after that and never moves again
    assert r["events"]["failed"]["R2"]["from"] == 16
    for e in r["timeline"]:
        if e["robot"] == "R2":
            assert e["carry"]["arrive"] <= 16 or e["carry"]["start"] <= 16
    for key, pts in r["paths"].items():
        if key.split("#")[0] == "R2":
            assert pts[-1][2] <= 16 or len({(x, y) for x, y, t in pts if t >= 16}) == 1
    # the blocked cell (9,4) is not entered between t=12 and t=40
    for pts in r["paths"].values():
        assert not any((x, y) == (9, 4) and 12 < t < 40 for x, y, t in pts)
    assert len(r["timeline"]) == 9


def test_mrta_only_and_mapf_only_modes():
    a = run(STATIC, mode="mrta_only")
    assert a["ok"] and a["paths"] == {} and a["makespan"] > 0
    b = run(STATIC, mode="mapf_only")
    assert b["ok"] and b["metrics"]["collisions"] == 0 and b["paths"]


def test_genetic_never_worse_than_greedy():
    g = run(STATIC, "greedy", mode="mrta_only")["makespan"]
    ga = run(STATIC, "genetic", mode="mrta_only")["makespan"]
    assert ga <= g


def test_unreachable_station_is_reported_not_crashed():
    sc = json.loads(json.dumps(TINY))
    sc["grid"] = ["#######", "#.#...#", "#######"]
    sc["robots"][0]["start"] = [3, 1]
    r = run(sc)
    assert not r["ok"] and "not reachable" in r["reason"]


PLUGIN_OK = '''
INFO = {"name": "My nearest robot", "module": "mrta", "params": {}}
def allocate(scenario, travel_times, state, feedback, params, tools):
    out = []
    for t in sorted(tools.pending_tasks(), key=lambda t: (t["k"], t["id"])):
        out.append({"task": t["id"], "robot": tools.eligible(t["id"])[0]})
    return out
'''


def test_uploaded_plugin_runs_and_is_validated():
    req = {"scenario": STATIC, "mrta": {"source": PLUGIN_OK, "label": "mine.py"}, "mapf": {"name": "prioritized"}}
    r = json.loads(api.run_json(json.dumps(req)))
    assert r["ok"] and r["algorithms"]["mrta"] == "My nearest robot"


def test_bad_plugins_are_rejected_with_clear_messages():
    assert "needs a function allocate" in json.loads(api.check_plugin_json("mrta", 'INFO={"name":"x"}', "a.py"))["error"]
    assert "INFO" in json.loads(api.check_plugin_json("mrta", "def allocate(*a): pass", "a.py"))["error"]
    assert "syntax error" in json.loads(api.check_plugin_json("mrta", "def (", "a.py"))["error"]
    assert "slot is for" in json.loads(api.check_plugin_json("mapf", PLUGIN_OK, "a.py"))["error"]


def test_plugin_returning_wrong_answers_is_caught():
    lazy = 'INFO={"name":"skips tasks","module":"mrta"}\ndef allocate(*a, **k):\n    return []\n'
    r = json.loads(api.run_json(json.dumps({"scenario": STATIC, "mrta": {"source": lazy}, "mapf": {"name": "prioritized"}})))
    assert not r["ok"] and "no eligible working robot" in r["reason"]
    crashy = 'INFO={"name":"crashes","module":"mrta"}\ndef allocate(*a, **k):\n    raise ValueError("boom")\n'
    r = json.loads(api.run_json(json.dumps({"scenario": STATIC, "mrta": {"source": crashy}})))
    assert not r["ok"] and "boom" in r["reason"]


def test_soft_time_limit():
    slow = 'INFO={"name":"slow","module":"mrta"}\ndef allocate(scenario, tt, state, fb, params, tools):\n    while True:\n        tools.check_time()\n'
    r = json.loads(api.run_json(json.dumps({"scenario": STATIC, "mrta": {"source": slow}, "options": {"time_limit_s": 0.2}})))
    assert not r["ok"] and "time limit" in r["reason"]


def test_catalogue_lists_all_builtins():
    c = json.loads(api.catalogue_json())
    assert {x["id"] for x in c["mrta"]} == set(MRTA)
    assert {x["id"] for x in c["mapf"]} == {"independent", "prioritized", "cbs"}
