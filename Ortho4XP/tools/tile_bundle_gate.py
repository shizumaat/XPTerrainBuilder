"""THE TILE BUNDLE GATE (#1699 phase 1) — export a harness-built tile,
import it into an EMPTY installation, build its scenery file there, and
prove three things:

* the scenery file (``Earth nav data/<10°>/<tile>.dsf``) is byte-identical
  to the one the source build wrote, with the same imagery;
* the import and the build there made NO network request at all (an
  audit hook on ``socket.connect`` / ``getaddrinfo`` / ``urllib.Request``,
  ``corpus_snapshot.ReadTrace``) — so no OpenStreetMap, elevation or
  lidar fetch;
* they read NOTHING of the source machine's data or Custom Scenery
  (``corpus_snapshot.LeakWatch`` over the shared data repo, the source
  build's folders and the owner's Custom Scenery).

    venv/bin/python tools/tile_bundle_gate.py --build OUT/TAG --world DIR

``OUT/TAG`` names a ``build_airport.py --tile`` run (its ``TAG.frame.json``
and ``TAG.result.json`` in ``OUT``); ``DIR`` must not exist.  Run from
``Ortho4XP/`` in a lane worktree.

THE EMPTY INSTALLATION (``DIR/world``): a data root holding only the
global config (the lane's, its X-Plane paths pointed into the world) and
the tile's folder with its per-tile config and its imagery (the source
build's ``textures/``, cloned); an X-Plane folder whose ``Custom Scenery``
holds copy-on-write clones of the airport packs the bundle names and a
``scenery_packs.ini`` listing only them, and whose ``Global Scenery``,
``Custom Data`` and ``Resources`` are links to the real install (the
user's own X-Plane, never a download).  The import and the scenery-file
step run in a CHILD process whose data root is that world
(``ORTHO4XP_DATA_ROOT``), with pack writes stood down
(``O4_PACK_WRITES=measure_only``, as every lane build).  Nothing is
written outside ``DIR``.

Reports (``DIR/gate.json`` and stdout): the bundle's size and key, the
export and import seconds, the scenery-file step's seconds in the world,
the DSF hashes, the network events and the leaks.  rc 0 only when all
three proofs hold.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

# The console is UTF-8 before anything prints (#171, #125): ONE derivation
# site, ``src/O4_Console_Encoding.py`` (twin: tests/test_console_encoding.py).
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "src"))
import O4_Console_Encoding as _o4console  # noqa: E402

_o4console.configure_console_streams()

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools" / "harness"))

#: The harness's engine-cache redirects a build ran under, by env name.
_REDIRECT_ENVS = {"masks": "O4_MASKS_DIR",
                  "airport_mod_cache": "O4_AIRPORT_MOD_CACHE_DIR",
                  "dsf_dump_cache": "O4_DSF_CACHE_DIR",
                  "dds_cache": "O4_DDS_CACHE_DIR"}

#: The X-Plane folders the world links to (the user's own install).
_LINKED_INSTALL = ("Global Scenery", "Custom Data", "Resources")


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _dsf_path(build_dir: Path, lat: int, lon: int) -> Path:
    import O4_File_Names as FNAMES
    return (build_dir / "Earth nav data" / FNAMES.round_latlon(lat, lon)
            / (FNAMES.short_latlon(lat, lon) + ".dsf"))


def _read_build(build: str) -> dict:
    out, tag = os.path.split(build.rstrip("/"))
    frame = json.loads(Path(out, tag + ".frame.json").read_text())
    result = json.loads(Path(out, tag + ".result.json").read_text())
    return {"frame": frame, "result": result}


# ── the export (this process, in the source build's frame) ──────────────

def export(build: dict, bundle_dir: Path) -> dict:
    redirects = build["frame"].get("engine_cache_redirects") or {}
    for key, env in _REDIRECT_ENVS.items():
        if redirects.get(key):
            os.environ[env] = redirects[key]
    import build_airport as BA
    BA.apply_xplane_install_paths()
    from tile_bundle import export as EXPORT
    lat, lon = build["result"]["tile"]
    return EXPORT.export_tile(lat, lon, str(bundle_dir),
                              build["result"]["build_dir"])


# ── the empty installation ──────────────────────────────────────────────

def _cfg_with(source: Path, values: dict) -> str:
    lines = [ln for ln in source.read_text().splitlines()
             if ln.split("=", 1)[0].strip() not in values]
    return "\n".join(lines + ["%s=%s" % kv for kv in values.items()]) + "\n"


def make_world(world: Path, build: dict, manifest: dict) -> dict:
    import O4_Config_Names as CN
    import O4_File_Names as FNAMES
    lat, lon = build["result"]["tile"]
    install = Path(build["result"]["xplane_paths"]["custom_scenery_dir"]).parent
    xplane = world / "X-Plane"
    scenery = xplane / "Custom Scenery"
    scenery.mkdir(parents=True)
    for name in _LINKED_INSTALL:
        if (install / name).exists():
            os.symlink(install / name, xplane / name)
    packs = sorted({entry["pack"] for entry in manifest["airports"].values()
                    if entry.get("custom") and entry.get("pack")})
    for pack in packs:
        subprocess.run(["cp", "-cR", str(install / "Custom Scenery" / pack),
                        str(scenery / pack)], check=True)
    ini = install / "Custom Scenery" / "scenery_packs.ini"
    kept = [ln for ln in ini.read_text(errors="replace").splitlines()
            if not ln.startswith("SCENERY_PACK")
            or "*GLOBAL_AIRPORTS*" in ln
            or any(ln.rstrip("/").endswith("/" + p) for p in packs)]
    (scenery / "scenery_packs.ini").write_text("\n".join(kept) + "\n")
    data = world / "data"
    tile_dir = data / "Tiles" / FNAMES.tile_dir(lat, lon)
    tile_dir.mkdir(parents=True)
    source_build = Path(build["result"]["build_dir"])
    cfg_name = CN.tile_cfg_name(lat, lon)
    shutil.copyfile(source_build / cfg_name, tile_dir / cfg_name)
    if (source_build / "textures").is_dir():     # a geometry-only build has none
        subprocess.run(["cp", "-cR", str(source_build / "textures"),
                        str(tile_dir / "textures")], check=True)
    (data / CN.GLOBAL_CFG_NAME).write_text(_cfg_with(
        ROOT / CN.GLOBAL_CFG_NAME,
        {"custom_scenery_dir": str(scenery),
         "cifp_data_path": str(xplane / "Custom Data" / "CIFP"),
         "custom_overlay_src": str(xplane / "Global Scenery")}))
    return {"data": str(data), "scenery": str(scenery), "packs": packs,
            "tiles": str(data / "Tiles"), "tile_dir": str(tile_dir)}


# ── the child: import + the scenery-file step, in the world ─────────────

def child(args) -> int:
    import corpus_snapshot as CS
    trace = CS.ReadTrace().start()
    leaks = CS.LeakWatch(args.leak_root).start()
    import O4_File_Names as FNAMES
    import O4_UI_Utils as UI
    sys.path.append(FNAMES.Provider_dir)
    import O4_Imagery_Utils as IMG
    import O4_Tile_Utils as TILE
    from o4_engine import library as LIB
    from tile_bundle.export import load_tile
    out: dict = {"data_root": FNAMES.current_data_root()}
    trace.mark("import")
    t0 = time.time()
    out["import"] = LIB.library_import_bundle(args.bundle, args.tiles)
    out["import_seconds"] = round(time.time() - t0, 1)
    trace.mark("scenery file")
    for init in (IMG.initialize_extents_dict, IMG.initialize_color_filters_dict,
                 IMG.initialize_providers_dict,
                 IMG.initialize_combined_providers_dict):
        init()
    lat, lon = out["import"]["tile"][:3], out["import"]["tile"][3:]
    tile = load_tile(int(lat), int(lon))
    t0 = time.time()
    out["scenery_file_result"] = TILE.build_tile(tile)
    out["scenery_file_seconds"] = round(time.time() - t0, 1)
    UI.is_working = 0
    trace.mark("")
    trace.stop()
    leaks.stop()
    record = trace.record()
    out["phases"] = {name: {"network": p["network"],
                            "processes": p["processes"],
                            "reads": len(p["reads"])}
                     for name, p in record["phases"].items()}
    out["reads"] = {name: p["reads"] for name, p in record["phases"].items()}
    out["leaks"] = leaks.record()
    out["build_dir"] = tile.build_dir
    Path(args.child_out).write_text(json.dumps(out, indent=1, default=str))
    return 0


# ── the gate ────────────────────────────────────────────────────────────

def gate(args) -> int:
    world = Path(args.world)
    if world.exists():
        raise SystemExit(f"REFUSING: {world} exists; the world starts empty")
    build = _read_build(args.build)
    lat, lon = build["result"]["tile"]
    bundle_dir = world / "bundle"
    exported = export(build, bundle_dir)
    from tile_bundle.importer import read_manifest
    manifest = read_manifest(exported["path"])
    made = make_world(world / "world", build, manifest)
    import corpus_snapshot as CS
    leak_roots = [CS.SHARED_DATA_REPO_DEFAULT,
                  build["result"]["build_dir"], build["result"]["patch_dir"],
                  build["result"]["xplane_paths"]["custom_scenery_dir"],
                  str(ROOT / "OSM_data"), str(ROOT / "Elevation_data"),
                  str(ROOT / "Patches"), str(ROOT / "Tiles")]
    child_out = world / "child.json"
    env = dict(os.environ, ORTHO4XP_DATA_ROOT=made["data"],
               O4_PACK_WRITES="measure_only")
    for name in _REDIRECT_ENVS.values():
        env.pop(name, None)
    argv = [sys.executable, __file__, "--child", "--bundle", exported["path"],
            "--tiles", made["tiles"], "--child-out", str(child_out)]
    for root in leak_roots:
        argv += ["--leak-root", root]
    rc = subprocess.run(argv, env=env, cwd=str(ROOT)).returncode
    if rc != 0 or not child_out.is_file():
        raise SystemExit(f"the child (import + scenery file) failed, rc={rc}")
    got = json.loads(child_out.read_text())
    source_dsf = _dsf_path(Path(build["result"]["build_dir"]), lat, lon)
    world_dsf = _dsf_path(Path(got["build_dir"]), lat, lon)
    network = {name: p["network"] for name, p in got["phases"].items()
               if p["network"]}
    report = {
        "tile": manifest["tile"], "bundle": exported,
        "airports": manifest["airports"], "import": got["import"],
        "import_seconds": got["import_seconds"],
        "scenery_file_seconds": got["scenery_file_seconds"],
        "scenery_file_seconds_source_build":
            build["result"]["step_seconds"].get("4 tile"),
        "dsf": {"source": str(source_dsf), "source_sha256": _sha(source_dsf),
                "world": str(world_dsf),
                "world_sha256": _sha(world_dsf) if world_dsf.is_file() else None},
        "network": network, "processes": {
            name: p["processes"] for name, p in got["phases"].items()},
        "leaks": got["leaks"], "world": made}
    report["dsf"]["identical"] = (report["dsf"]["source_sha256"]
                                  == report["dsf"]["world_sha256"])
    report["pass"] = bool(report["dsf"]["identical"] and not network
                          and not got["leaks"]["count"]
                          and got["import"]["reused"]
                          == ["vector", "mesh", "masks"])
    (world / "gate.json").write_text(json.dumps(report, indent=1, default=str))
    (world / "reads.json").write_text(json.dumps(got["reads"], indent=1))
    print(json.dumps({k: report[k] for k in (
        "tile", "pass", "import_seconds", "scenery_file_seconds",
        "scenery_file_seconds_source_build", "network")}, indent=1))
    print("bundle %s bytes=%d key=%s export %.1fs; DSF identical=%s; "
          "leaks=%d" % (exported["path"], exported["bytes"], exported["key"],
                        exported["seconds"], report["dsf"]["identical"],
                        got["leaks"]["count"]))
    return 0 if report["pass"] else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--build", help="OUT/TAG of a build_airport.py --tile run")
    ap.add_argument("--world", help="the gate's folder (must not exist)")
    ap.add_argument("--child", action="store_true", help=argparse.SUPPRESS)
    ap.add_argument("--bundle", help=argparse.SUPPRESS)
    ap.add_argument("--tiles", help=argparse.SUPPRESS)
    ap.add_argument("--child-out", help=argparse.SUPPRESS)
    ap.add_argument("--leak-root", action="append", default=[],
                    help=argparse.SUPPRESS)
    args = ap.parse_args(argv)
    if args.child:
        return child(args)
    if not (args.build and args.world):
        ap.error("--build and --world are required")
    return gate(args)


if __name__ == "__main__":
    raise SystemExit(main())
