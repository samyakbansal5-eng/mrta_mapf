"""JSON entry points used by the web worker (and handy from Python too)."""
import json
import time

from . import scenario as S
from . import plugins as P
from .orchestrator import run as run_core
from .validators import validate_timeline  # noqa: F401  (re-exported for plug-in authors)


def catalogue_json():
    return json.dumps(P.catalogue())


def validate_scenario_json(text):
    sc = S.load(text)
    return json.dumps(S.validate(sc))


def parse_ascii_json(text, legend_json="{}"):
    d = S.parse_ascii(text, json.loads(legend_json))
    return json.dumps({"grid": d["grid"], "stations": {k: list(v) for k, v in d["stations"].items()}})


def check_plugin_json(kind, source, label):
    try:
        mod = P.from_source(kind, source, label)
        return json.dumps({"ok": True, "info": mod.INFO})
    except Exception as e:  # noqa: BLE001 - report any problem in the upload to the user
        return json.dumps({"ok": False, "error": f"{type(e).__name__}: {e}"})


def run_json(request_json):
    """request: {scenario, mode: integrated|mrta_only|mapf_only, mrta:{name|source,params}, mapf:{...}, options:{...}}"""
    req = json.loads(request_json)
    try:
        sc = S.load(req["scenario"])
        problems = [i for i in S.validate(sc) if i["level"] == "error"]
        if problems:
            return json.dumps({"ok": False, "reason": "scenario invalid: " + "; ".join(i["msg"] for i in problems), "issues": problems})
        mode = req.get("mode", "integrated")
        mrta = P.resolve("mrta", req.get("mrta", {}))
        mapf = None if mode == "mrta_only" else P.resolve("mapf", req.get("mapf", {}))
        opts = dict(req.get("options", {}))
        opts["mrta_params"] = req.get("mrta", {}).get("params", {})
        opts["mapf_params"] = req.get("mapf", {}).get("params", {})
        if mode == "mapf_only":
            opts["max_rounds"] = 1
            opts["mapf_only"] = True
            mrta = P.builtin("mrta", "greedy")           # fixed simple plan so MAPF can be shown on its own
        result = run_core(sc, mrta, mapf, opts)
        result["algorithms"] = {"mrta": mrta.INFO["name"], "mapf": mapf.INFO["name"] if mapf else None}
        return json.dumps(result, default=_default)
    except TimeoutError as e:
        return json.dumps({"ok": False, "reason": f"time limit: {e}"})
    except P.PluginError as e:
        return json.dumps({"ok": False, "reason": f"plug-in problem: {e}"})
    except Exception as e:  # noqa: BLE001 - uploaded algorithms may raise anything; show it, don't crash the page
        return json.dumps({"ok": False, "reason": f"{type(e).__name__}: {e}"})


def _default(o):
    if isinstance(o, (set, frozenset, tuple)):
        return list(o)
    raise TypeError(type(o))
