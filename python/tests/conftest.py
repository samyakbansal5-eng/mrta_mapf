import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
ROOT = os.path.join(os.path.dirname(__file__), "..", "..")


def load_scenario(name):
    with open(os.path.join(ROOT, "scenarios", name + ".json")) as f:
        return json.load(f)


TINY = {
    "grid": ["#######", "#.....#", "#######"],
    "stations": {"RM": [1, 1], "M1": [3, 1], "FG": [5, 1]},
    "robots": [{"id": "R1", "start": [2, 1], "step_cost": 1}],
    "products": [{"id": "P1", "route": ["M1"], "process_time": {"M1": 4}}],
}
