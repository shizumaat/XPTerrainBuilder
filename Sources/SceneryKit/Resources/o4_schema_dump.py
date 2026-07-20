#!/usr/bin/env python3
"""Dump the Ortho4XP configuration schema as JSON on stdout.

Run with cwd == the engine root:  python3 o4_schema_dump.py

Only O4_Cfg_Vars is imported. That module pulls in O4_OSM_Utils (which needs
the engine's third-party packages) solely for the overpass server list, so
when that import fails — bare python3, engine venv not set up yet — a stub
module carrying the server list parsed straight from overpass_servers.txt is
injected instead. The dump therefore works with any stock python3.
"""
import json
import os
import sys
import types

root = os.getcwd()
sys.path.insert(0, os.path.join(root, "src"))


def overpass_servers_from_file():
    servers = {}
    try:
        with open(os.path.join(root, "overpass_servers.txt")) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, url = line.partition("=")
                if key.strip() and url.strip():
                    servers[key.strip()] = url.strip()
    except OSError:
        pass
    return servers or {"random": ""}


try:
    import O4_Cfg_Vars as CV
except Exception:
    stub = types.ModuleType("O4_OSM_Utils")
    stub.overpass_servers = overpass_servers_from_file()
    sys.modules["O4_OSM_Utils"] = stub
    import O4_Cfg_Vars as CV


def engine_version():
    try:
        with open(os.path.join(root, "src", "O4_Version.py")) as f:
            for line in f:
                if "version" in line and "=" in line:
                    return line.split("=", 1)[1].strip().strip("'\"")
    except OSError:
        pass
    return ""


def encode(name, spec):
    out = {
        "name": name,
        "type": getattr(spec.get("type"), "__name__", "str"),
        "default": spec.get("default"),
        "hint": spec.get("hint", ""),
    }
    if "values" in spec:
        out["values"] = [v if isinstance(v, str) else repr(v) for v in spec["values"]]
    if "value_labels" in spec:
        out["valueLabels"] = {
            (k if isinstance(k, str) else repr(k)): str(v)
            for k, v in spec["value_labels"].items()
        }
    if "module" in spec:
        out["module"] = spec["module"]
    if "short_name" in spec:
        out["shortName"] = spec["short_name"]
    return out


groups = {}
for key, attr in (("app", "list_app_vars"), ("vector", "list_vector_vars"),
                  ("mesh", "list_mesh_vars"), ("mask", "list_mask_vars"),
                  ("dsf", "list_dsf_vars"), ("other", "list_other_vars")):
    groups[key] = list(getattr(CV, attr, []))

json.dump(
    {
        "engineVersion": engine_version(),
        "groups": groups,
        "vars": {name: encode(name, spec) for name, spec in CV.cfg_vars.items()},
    },
    sys.stdout, indent=1, sort_keys=True,
)
sys.stdout.write("\n")
