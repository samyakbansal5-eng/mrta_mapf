"""Validation of hand-edited plans (Plan editor / raw JSON)."""
from conftest import load_scenario, TINY
from bench.core import scenario as S


def msgs(sc, level=None):
    return [i["msg"] for i in S.validate(S.load(sc)) if level is None or i["level"] == level]


def edited(**changes):
    sc = S.load(load_scenario("small_factory_events"))
    for k, v in changes.items():
        sc[k] = v
    return sc


def has(sc, text, level="error"):
    return any(text in m for m in msgs(sc, level))


def test_bigger_plan_from_editor_is_valid():
    sc = load_scenario("small_factory")
    sc["robots"].append({"id": "R4", "start": [12, 1], "step_cost": 1, "payload": 10, "can_carry": ["P1", "P4"]})
    sc["products"].append({"id": "P4", "route": ["M4", "M1"], "weight": 2, "process_time": {"M4": 2, "M1": 3}})
    sc["events"] = [{"t": 5, "type": "robot_failure", "robot": "R4"}, {"t": 9, "type": "robot_recovered", "robot": "R4"}]
    assert S.validate(S.load(sc)) == []


def test_duplicate_ids():
    sc = load_scenario("small_factory")
    sc["robots"][1]["id"] = "R1"
    assert has(sc, "robot id R1 is used more than once")
    sc = load_scenario("small_factory")
    sc["products"][1]["id"] = "P1"
    assert has(sc, "product id P1 is used more than once")


def test_empty_plan_parts():
    sc = load_scenario("small_factory")
    sc["robots"] = []
    assert has(sc, "no robots")
    sc = load_scenario("small_factory")
    sc["products"] = []
    assert has(sc, "nothing to transport", "warning")
    assert not msgs(sc, "error")
    sc = load_scenario("small_factory")
    sc["products"][0]["route"] = []
    assert has(sc, "empty route")


def test_bad_numbers():
    sc = load_scenario("small_factory")
    sc["robots"][0]["payload"] = -1
    assert has(sc, "payload must be a number")
    sc = load_scenario("small_factory")
    sc["products"][0]["weight"] = -3
    assert has(sc, "weight must be a number")
    sc = load_scenario("small_factory")
    sc["products"][0]["process_time"]["M1"] = 2.5
    assert has(sc, "process time at M1 must be a whole number")


def test_route_must_not_use_stores():
    sc = load_scenario("small_factory")
    sc["products"][0]["route"] = ["RM", "M1"]
    assert has(sc, "route uses store RM")


def test_can_carry_checks():
    sc = load_scenario("small_factory")
    sc["robots"][0]["can_carry"] = ["P9", "P1", "P2", "P3"]
    assert has(sc, "unknown product P9", "warning")
    sc = load_scenario("small_factory")
    sc["robots"][2]["can_carry"] = []
    assert has(sc, "will never be used", "warning")
    sc = load_scenario("small_factory")
    for r in sc["robots"]:
        r["can_carry"] = ["P2"]
    assert has(sc, "no robot can carry product P1")


def test_shared_station_cell_and_missing_fg():
    sc = load_scenario("small_factory")
    sc["stations"]["M3"] = sc["stations"]["M1"]
    assert has(sc, "share the cell", "warning")
    sc = dict(TINY, stations={"RM": [1, 1], "M1": [3, 1]})
    assert has(sc, "no finished-goods station", "warning")
    assert not msgs(sc, "error")


def test_event_checks():
    assert has(edited(events=[{"t": 3, "type": "robot_failure", "robot": "R9"}]), "unknown robot R9")
    assert has(edited(events=[{"t": -1, "type": "robot_failure", "robot": "R1"}]), "whole number >= 0")
    assert has(edited(events=[{"t": 10, "type": "block_cells", "cells": [[4, 4]], "until": 10}]), "'until' must be later")
    assert has(edited(events=[{"t": 10, "type": "block_cells", "cells": []}]), "no cells to block")
    assert has(edited(events=[{"t": 10, "type": "block_cells", "cells": [[0, 0]]}]), "is a wall", "warning")
    assert has(edited(events=[{"t": 1, "type": "earthquake"}]), "unknown event type")
    assert not msgs(edited(events=[{"t": 10, "type": "block_cells", "cells": [[4, 4]], "until": None}]))
