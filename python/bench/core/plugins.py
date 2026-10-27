"""Plug-in registry and loader.

A plug-in is a module (or source text) with an INFO dict and one function:
    MAPF:  plan(problem, state, params, tools)                               -> dict (see mapf/lowlevel.pack)
    MRTA:  allocate(scenario, travel_times, state, feedback, params, tools)  -> [{"task", "robot"}, ...]
"""
import importlib
import types

FUNCS = {"mapf": "plan", "mrta": "allocate"}
BUILTIN = {
    "mrta": ["greedy", "auction", "genetic", "tabu"],
    "mapf": ["independent", "prioritized", "cbs"],
}
CUSTOM = {"mrta": {}, "mapf": {}}


class PluginError(Exception):
    pass


def builtin(kind, name):
    return importlib.import_module(f"bench.{kind}.{name}")


def check(kind, mod, label="plug-in"):
    info = getattr(mod, "INFO", None)
    if not isinstance(info, dict) or "name" not in info:
        raise PluginError(f"{label}: needs an INFO dict with at least a 'name'")
    if info.get("module") not in (None, kind):
        raise PluginError(f"{label}: INFO['module'] is {info.get('module')!r} but this slot is for {kind!r}")
    fn = getattr(mod, FUNCS[kind], None)
    if not callable(fn):
        raise PluginError(f"{label}: needs a function {FUNCS[kind]}(...)")
    return mod


def from_source(kind, source, label="uploaded"):
    """Compile uploaded source text into a plug-in. Runs the file's top-level code (in the caller's sandbox!)."""
    mod = types.ModuleType("plugin_" + label)
    try:
        exec(compile(source, label, "exec"), mod.__dict__)
    except SyntaxError as e:
        raise PluginError(f"{label}: syntax error at line {e.lineno}: {e.msg}")
    return check(kind, mod, label)


def resolve(kind, spec):
    """spec: {"name": builtin name} or {"source": text, "label": str}."""
    if spec.get("source"):
        return from_source(kind, spec["source"], spec.get("label", "uploaded"))
    name = spec.get("name") or BUILTIN[kind][0]
    if name not in BUILTIN[kind]:
        raise PluginError(f"unknown {kind} algorithm {name!r}")
    return check(kind, builtin(kind, name), name)


def catalogue():
    out = {}
    for kind, names in BUILTIN.items():
        out[kind] = [dict(builtin(kind, n).INFO, id=n) for n in names]
    return out
