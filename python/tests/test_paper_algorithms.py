"""The algorithms added from the literature shortlist: every one runs, covers every task, and
produces collision-free, rule-abiding paths on the sample factories."""
import json

import pytest

from conftest import load_scenario
from bench.core import api, plugins as P
from bench.core import scenario as S
from bench.core.state import initial_state
from bench.core.tools import Tools
from bench.core.orchestrator import build_problem
from bench.core.validators import find_conflicts

NEW_MAPF = ["pibt", "lacam", "lns2", "eecbs", "pbs", "rhcr", "traffic_flow", "adg"]
NEW_MRTA = ["rmca", "tessi", "bischoff", "hmr_odta", "kalempa", "calvo", "ta_hybrid", "tercio", "meng_ga", "sun_ga"]
SCENARIOS = ["small_factory", "small_factory_events", "busy_factory"]


def run(scn, mrta="greedy", mapf="prioritized", mapf_params=None):
    req = {"scenario": load_scenario(scn), "mode": "integrated", "mrta": {"name": mrta},
           "mapf": {"name": mapf, "params": mapf_params or {}}, "options": {"time_limit_s": 60}}
    return json.loads(api.run_json(json.dumps(req)))


def test_every_builtin_documents_its_papers():
    for kind, infos in P.catalogue().items():
        for info in infos:
            assert info["about"] and info["fidelity"], info["id"]
            assert info["papers"], info["id"]
            for p in info["papers"]:
                assert p["title"] and p["url"].startswith("https://"), (info["id"], p)


@pytest.mark.parametrize("name", NEW_MAPF)
@pytest.mark.parametrize("scn", SCENARIOS)
def test_new_mapf_algorithms_are_valid(name, scn):
    r = run(scn, mapf=name)
    assert r["ok"], r.get("reason")
    assert r["metrics"]["collisions"] == 0 and r["metrics"]["rule_violations"] == 0


@pytest.mark.parametrize("name", ["pibt", "lacam", "pbs", "eecbs", "lns2", "rhcr"])
def test_new_mapf_without_fallback_on_small_factory(name):
    r = run("small_factory", mapf=name, mapf_params={"fallback": "no"})
    assert r["ok"], r.get("reason")
    assert not any("FELL BACK" in w for w in r["warnings"])


@pytest.mark.parametrize("name", NEW_MRTA)
@pytest.mark.parametrize("scn", SCENARIOS)
def test_new_mrta_algorithms_cover_every_task(name, scn):
    sc = S.load(load_scenario(scn))
    st = initial_state(sc)
    tools = Tools(sc, st, None, 1)
    mod = P.builtin("mrta", name)
    a = mod.allocate(sc, tools.travel_table(), st, {}, {}, tools)
    assert sorted(x["task"] for x in a) == sorted(t["id"] for t in tools.pending_tasks())
    for x in a:
        assert x["robot"] in tools.eligible(x["task"])
    assert tools.schedule(a)["ok"]


@pytest.mark.parametrize("name", NEW_MRTA)
def test_new_mrta_runs_end_to_end(name):
    r = run("small_factory", mrta=name, mapf="pbs")
    assert r["ok"], r.get("reason")


def test_rmca_beats_or_matches_greedy_on_sample():
    assert run("small_factory", mrta="rmca")["makespan"] <= run("small_factory", mrta="greedy")["makespan"]


def test_adg_without_delays_keeps_the_plan_and_with_delays_stays_collision_free():
    sc = S.load(load_scenario("busy_factory"))
    st = initial_state(sc)
    tools = Tools(sc, st, None, 1)
    a = P.builtin("mrta", "greedy").allocate(sc, tools.travel_table(), st, {}, {}, tools)
    prob = build_problem(sc, st, tools.schedule(a))
    base = P.builtin("mapf", "prioritized").plan(json.loads(json.dumps(prob)), st, {}, tools)
    adg = P.builtin("mapf", "adg")
    same = adg.plan(json.loads(json.dumps(prob)), st, {"delay_probability": 0.0}, tools)
    assert same["arrivals"] == base["arrivals"]
    late = adg.plan(json.loads(json.dumps(prob)), st, {"delay_probability": 0.4, "seed": 3}, tools)
    paths = {r: [tuple(p) for p in v] for r, v in late["paths"].items()}
    assert find_conflicts(paths) == []
    assert all(late["arrivals"][k] >= v for k, v in base["arrivals"].items())
    assert sum(late["arrivals"].values()) > sum(base["arrivals"].values())
