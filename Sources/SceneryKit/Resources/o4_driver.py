#!/usr/bin/env python3
"""XPScenerySmith build driver for the Ortho4XP engine.

Runs with cwd == the engine root, under whatever python the engine's own
environment provides (its venv when present). Invoked as:

    python3 o4_driver.py <job.json>

The job file describes one tile build:

    {
      "lat": 47, "lon": 11,
      "steps": ["vector", "mesh", "masks", "dsf"],   // any subset, + "overlay"
      "provider": "BI", "zl": 16,                    // optional overrides
      "build_dir": "",                               // custom base folder ("" = Tiles/)
      "tile_overrides": {"curvature_tol": 1.0},      // per-tile cfg overrides
      "app_overrides": {"verbosity": 1}              // app-level cfg overrides
    }

Machine-readable events are emitted on stdout prefixed "@@O4|":

    @@O4|engine|<version>
    @@O4|progress|<bar>|<pct>      bar 1 = mesh, 2 = download, 3 = convert
    @@O4|step|<name>|start|ok|fail|skip
    @@O4|stopping
    @@O4|exit|ok|fail|stopped
    @@O4|fatal|<message>

Everything else on stdout is the engine's own console output. Reading the
line "STOP" on stdin raises the engine's red flag (polled inside every build
step) for a graceful abort; the caller escalates to killing the process if
that doesn't take.

The driver deliberately touches only the engine surface that has been stable
across Ortho4XP releases — the O4_* module names, the four step functions,
Tile, UI.progress_bar and UI.red_flag — so a newly dropped-in engine version
keeps working without changes here.
"""
import json
import os
import sys
import threading
import traceback


def emit(*fields):
    sys.stdout.write("@@O4|" + "|".join(str(f) for f in fields) + "\n")
    sys.stdout.flush()


def main():
    if len(sys.argv) != 2:
        emit("fatal", "usage: o4_driver.py <job.json>")
        return 2
    try:
        with open(sys.argv[1]) as f:
            job = json.load(f)
    except Exception as exc:
        emit("fatal", "could not read job file: %s" % exc)
        return 2

    root = os.getcwd()
    sys.path.insert(0, os.path.join(root, "src"))

    try:
        import O4_UI_Utils as UI
        import O4_File_Names as FNAMES
        import O4_Imagery_Utils as IMG
        import O4_Vector_Map as VMAP
        import O4_Mesh_Utils as MESH
        import O4_Mask_Utils as MASK
        import O4_Tile_Utils as TILE
        import O4_Overlay_Utils as OVL
        # Last on purpose, mirroring Ortho4XP.py: importing the config module
        # executes the global-config read that overwrites the other modules'
        # variables.
        import O4_Config_Utils as CFG
    except Exception:
        emit("fatal", "engine import failed (is the python environment set up?)")
        traceback.print_exc()
        return 2

    try:
        from O4_Version import version as engine_version
    except Exception:
        engine_version = "unknown"
    emit("engine", engine_version)

    # Same bootstrap as Ortho4XP.py's __main__ guard: working dirs + the
    # provider/extent/filter dictionaries.
    for name in ("Preview_dir", "Provider_dir", "Extent_dir", "Filter_dir",
                 "OSM_dir", "Mask_dir", "Imagery_dir", "Elevation_dir",
                 "Geotiff_dir", "Patch_dir", "Tile_dir", "Tmp_dir"):
        path = getattr(FNAMES, name, None)
        if path and not os.path.isdir(path):
            os.makedirs(path, exist_ok=True)
    for name in ("initialize_extents_dict", "initialize_color_filters_dict",
                 "initialize_providers_dict", "initialize_combined_providers_dict"):
        init = getattr(IMG, name, None)
        if init:
            init()

    # Progress percentages normally go into Tk IntVars; reroute them to
    # stdout. Every engine module calls this through the UI module attribute,
    # so patching the attribute covers all call sites.
    def progress_bar(nbr, percentage, message=None):
        try:
            emit("progress", nbr, int(percentage))
        except Exception:
            pass
    UI.progress_bar = progress_bar

    # Graceful cancellation: each step polls UI.red_flag. The steps also
    # RESET the flag when they start, so remember the request ourselves and
    # never enter another step after it.
    stop_requested = threading.Event()

    def watch_stdin():
        for line in sys.stdin:
            if line.strip() == "STOP":
                stop_requested.set()
                UI.red_flag = True
                emit("stopping")
    threading.Thread(target=watch_stdin, daemon=True).start()

    try:
        lat, lon = int(job["lat"]), int(job["lon"])
    except Exception:
        emit("fatal", "job file needs integer lat and lon")
        return 2
    tile = CFG.Tile(lat, lon, job.get("build_dir", ""))
    tile_cfg = os.path.join(
        tile.build_dir, "Ortho4XP_" + FNAMES.short_latlon(lat, lon) + ".cfg")
    if os.path.isfile(tile_cfg):
        tile.read_from_config()

    # App-level overrides live in the module named by the schema; per-tile
    # overrides are plain attributes on the Tile.
    modules = {"UI": UI, "IMG": IMG, "TILE": TILE, "OVL": OVL, "CFG": CFG}
    try:
        import O4_OSM_Utils as OSM
        modules["OSM"] = OSM
    except Exception:
        pass
    app_specs = getattr(CFG, "cfg_app_vars", {})
    for name, value in (job.get("app_overrides") or {}).items():
        target = modules.get(app_specs.get(name, {}).get("module", "CFG"), CFG)
        setattr(target, name, value)
    for name, value in (job.get("tile_overrides") or {}).items():
        setattr(tile, name, value)
    if job.get("provider"):
        tile.default_website = job["provider"]
    if job.get("zl"):
        tile.default_zl = int(job["zl"])

    steps = {
        "vector":  lambda: VMAP.build_poly_file(tile),
        "mesh":    lambda: MESH.build_mesh(tile),
        "masks":   lambda: MASK.build_masks(tile),
        "dsf":     lambda: TILE.build_tile(tile),
        "overlay": lambda: OVL.build_overlay(lat, lon),
    }
    for name in job.get("steps") or ["vector", "mesh", "masks", "dsf"]:
        if name not in steps:
            emit("step", name, "skip")
            continue
        if stop_requested.is_set():
            emit("exit", "stopped")
            return 3
        emit("step", name, "start")
        try:
            ok = steps[name]()
        except Exception:
            traceback.print_exc()
            ok = 0
        if stop_requested.is_set():
            emit("step", name, "fail")
            emit("exit", "stopped")
            return 3
        if not ok:
            emit("step", name, "fail")
            emit("exit", "fail")
            return 1
        emit("step", name, "ok")
    emit("exit", "ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
