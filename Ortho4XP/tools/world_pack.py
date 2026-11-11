"""World pack kit: ONE Custom Scenery pack with a placeholder DSF for every
tile, real tiles swapped in while X-Plane flies (owner idea 2026-11-10;
module ``src/O4_World_Pack.py``).

Run from the engine checkout (``cd Ortho4XP && venv/bin/python
tools/world_pack.py --kit KIT ...``) or from a kit's own copy
(``python KIT/world.py ...``: the kit's ``kit.json`` names the engine
checkout).  Subcommands:

  make-kit --kit DIR --center +53-061 --radius 2 --skip +53-061
      the pack folder with placeholder DSFs (pure Python), kit.json
  stage TILE --tile-dir DIR    a built zOrtho4XP_<tile> laid out for the
                               pack (per-tile terrain/textures folders) + verify
  verify                       every placeholder and staged tile (binary reads)
  install / restore            Custom Scenery link + scenery_packs.ini row
                               (X-Plane closed; backup kept in the kit)
  swapin TILE [--force]        staged tile -> pack, one rename of the DSF;
                               refused when the aircraft is within 1 tile
  swapout TILE                 placeholder back over the DSF
  onthefly TILE                build TILE now (light settings, kit data
                               root), stage, verify, swap in; Ctrl-C safe
  drape TILE [--exclude for] [--water-alpha [--water-layer G]]
                               DRAPED tile: the tile's orthophotos laid over
                               X-Plane's default mesh by an overlay DSF (one
                               .pol per texture square), no OSM/DEM/mesh;
                               fetch, write, verify, swap in (O4_World_Drape);
                               --water-alpha adds the regular build's water
                               mask as a translucent photo layer over water
                               (O4_World_Drape_Water), staged in drapes/water
  status                       each tile's state and the aircraft's distance
  reload                       X-Plane's sim/operation/reload_scenery (Web API)

Every action appends a JSON line to ``KIT/world_log.jsonl``.  Never writes
X-Plane's install except ``install`` / ``restore``.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import shutil
import signal
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
KIT_MODE = os.path.isfile(os.path.join(HERE, "kit.json"))
REPO_ENGINE = os.path.dirname(HERE)


def _engine_dir(kit_cfg: dict | None) -> str:
    return (kit_cfg or {}).get("engine_dir") or REPO_ENGINE


def _imports(engine: str):
    """O4_World_Pack and O4_World_Drape from the kit's copy (kit mode) or
    the engine's src; the rest (O4_World_Window among them) from the
    engine's src."""
    for path in (os.path.join(engine, "src"),
                 HERE if KIT_MODE else os.path.join(REPO_ENGINE, "src")):
        if path in sys.path:          # HERE is already sys.path[0]: move it
            sys.path.remove(path)     # in front of the engine's src, or the
        sys.path.insert(0, path)      # engine's copies win over the kit's
    import O4_Scenery_Packs as PACKS
    import O4_World_Drape as DRAPE
    import O4_World_Pack as WP
    import O4_World_Window as WIN
    import O4_XPlane_WebAPI as API
    return WP, DRAPE, PACKS, API, WIN


def now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")


class Kit:
    """Paths of one kit (``kit.json``) and its log."""

    def __init__(self, root: str):
        self.root = os.path.abspath(root)
        with open(os.path.join(self.root, "kit.json"), encoding="utf-8") as h:
            self.cfg = json.load(h)
        self.engine = _engine_dir(self.cfg)
        self.WP, self.DRAPE, self.PACKS, self.API, self.WIN = _imports(self.engine)
        self.pack = os.path.join(self.root, self.cfg["pack_name"])
        self.staged = os.path.join(self.root, "staged")
        self.drapes = os.path.join(self.root, "drapes")
        self.drapes_water = os.path.join(self.drapes, "water")
        self.build_root = os.path.join(self.root, "build_root")
        self.tool = self.WP.dsftool_path(self.engine)

    @property
    def custom_scenery(self) -> str:
        return os.path.join(self.cfg["xplane_dir"], "Custom Scenery")

    def log(self, rec: dict) -> dict:
        rec = {"utc": now(), **rec}
        with open(os.path.join(self.root, "world_log.jsonl"), "a",
                  encoding="utf-8") as h:
            h.write(json.dumps(rec) + "\n")
        print(json.dumps(rec))
        return rec


def xplane_running() -> bool:
    done = subprocess.run(["pgrep", "-x", "X-Plane"], capture_output=True)
    return done.returncode == 0


def aircraft(kit: Kit, tile: tuple[int, int] | None) -> dict:
    """The aircraft's and camera's position from the Web API, and their
    distance to ``tile``; ``{"webapi": "down: ..."}`` when unreachable."""
    reader = kit.API.PositionReader(timeout=2.0)
    rec = reader.read()
    if rec is None:
        return {"webapi": "down: " + reader.error[:120]}
    lat, lon = float(rec["lat"]), float(rec["lon"])
    clat, clon = kit.API.camera_position(rec)
    out = {"webapi": "ok", "lat": round(lat, 5), "lon": round(lon, 5),
           "cam_lat": round(clat, 5), "cam_lon": round(clon, 5),
           "elev_m": rec.get("elev"), "gs_ms": rec.get("gs_ms")}
    if tile:
        out["window"] = kit.WIN.reach(clat, clon, *tile)
    return out


def kit_tiles(kit: Kit) -> list[tuple[int, int]]:
    """The kit's placeholder tiles: the block minus ``skip``, plus ``extra``."""
    WP = kit.WP
    lat, lon = WP.parse_tile(kit.cfg["center"])
    skip = [WP.parse_tile(s) for s in kit.cfg["skip"]]
    tiles = WP.block_tiles(lat, lon, kit.cfg["radius"], skip)
    return tiles + [WP.parse_tile(s) for s in kit.cfg.get("extra", [])
                    if WP.parse_tile(s) not in tiles]


# ---------------------------------------------------------------- make-kit
def cmd_make_kit(a) -> int:
    root = os.path.abspath(a.kit)
    engine = os.path.abspath(a.engine or REPO_ENGINE)
    WP, DRAPE, _, _, _ = _imports(engine)
    os.makedirs(root, exist_ok=True)
    cfg = {"pack_name": WP.PACK_NAME, "engine_dir": engine,
           "xplane_dir": a.xplane, "center": a.center, "radius": a.radius,
           "skip": a.skip, "extra": a.extra, "made": now()}
    with open(os.path.join(root, "kit.json"), "w", encoding="utf-8") as h:
        json.dump(cfg, h, indent=1)
    kit = Kit(root)
    made = [WP.tile_name(*t) for t in kit_tiles(kit)]
    for t in kit_tiles(kit):
        WP.write_placeholder(kit.pack, *t)
    if KIT_MODE is False:                 # copy the files the kit runs
        shutil.copy2(os.path.abspath(__file__), os.path.join(root, "world.py"))
        for module in (WP.__file__, DRAPE.__file__, WP.DSFB.__file__,
                       _fetch_script(), _water_module()):
            shutil.copy2(module, root)
    kit.log({"event": "make_kit", "placeholders": made, "skip": a.skip})
    return 0


# ---------------------------------------------------------------- stage/verify
def stage(kit: Kit, tile: str, tile_dir: str) -> dict:
    """Lay a built tile out under ``staged/<tile>`` (via ``.new``, renamed
    only once verified)."""
    lat, lon = kit.WP.parse_tile(tile)
    final = os.path.join(kit.staged, tile)
    work = final + ".new"
    shutil.rmtree(work, ignore_errors=True)
    counts = kit.WP.relayout_tile(tile_dir, work, lat, lon)
    check = kit.WP.verify_tile(work, lat, lon)
    if check["problems"] or check["overlay"] or not check["pack_defs"]:
        raise SystemExit(f"staged {tile} failed its check: {check}")
    shutil.rmtree(final, ignore_errors=True)
    os.rename(work, final)
    return kit.log({"event": "stage", "tile": tile, "tile_dir": tile_dir,
                    **counts, "verify": check})


def cmd_stage(a) -> int:
    stage(Kit(a.kit), a.tile, os.path.abspath(a.tile_dir))
    return 0


def tile_state(kit: Kit, path: str) -> str:
    """``placeholder`` / ``drape`` / ``real`` of the DSF at ``path``."""
    if kit.WP.is_placeholder(path):
        return "placeholder"
    return "drape" if kit.DRAPE.is_drape(path) else "real"


def _drape_ok(res: dict) -> bool:
    return bool(res["overlay"] and res["agent"] and res["defs"]
                and not res["problems"])


def cmd_verify(a) -> int:
    kit = Kit(a.kit)
    WP, bad = kit.WP, 0
    for t in kit_tiles(kit):
        path = os.path.join(kit.pack, WP.dsf_relpath(*t))
        state = tile_state(kit, path)
        if state == "drape":
            res = kit.DRAPE.verify_drape(kit.pack, *t, kit.tool)
            ok = _drape_ok(res)
        else:
            res = WP.verify_tile(kit.pack, *t)
            ok = (res["overlay"] and not res["defs"]) \
                if state == "placeholder" \
                else (not res["problems"] and not res["overlay"])
        head = WP.dsf_header(path)
        ok = ok and head["magic_ok"] and head["md5_ok"]
        bad += not ok
        print(f"pack   {WP.tile_name(*t)} {state:11s} overlay={res['overlay']}"
              f" defs={res['defs']} md5={head['md5_ok']} problems="
              f"{len(res['problems'])} {'OK' if ok else 'BAD'}")
    if os.path.isdir(kit.staged):
        for name in sorted(os.listdir(kit.staged)):
            if name.endswith(".new"):
                continue
            root = os.path.join(kit.staged, name)
            res = WP.verify_tile(root, *WP.parse_tile(name))
            head = WP.dsf_header(os.path.join(
                root, WP.dsf_relpath(*WP.parse_tile(name))))
            ok = (not res["problems"] and not res["overlay"]
                  and head["magic_ok"] and head["md5_ok"]
                  and "DEMS" in head["atoms"])
            bad += not ok
            print(f"staged {name} defs={res['defs']} pack_defs="
                  f"{res['pack_defs']} ters={res['ters_checked']} tex_refs="
                  f"{res['tex_refs']} problems={res['problems'][:3]} "
                  f"{'OK' if ok else 'BAD'}")
    for root in (kit.drapes, kit.drapes_water):
        for name in sorted(os.listdir(root)) if os.path.isdir(root) else ():
            if not os.path.isdir(os.path.join(root, name, "Earth nav data")):
                continue                     # work dirs, .new, water/
            res = kit.DRAPE.verify_drape(os.path.join(root, name),
                                        *WP.parse_tile(name), kit.tool)
            ok = _drape_ok(res)
            bad += not ok
            kind = "water" if root == kit.drapes_water else "drape"
            print(f"{kind:6s} {name} polygons={res['polygons']} pols="
                  f"{res['pols_checked']} excludes={res['excludes']} "
                  f"problems={res['problems'][:3]} {'OK' if ok else 'BAD'}")
    print("verify:", "OK" if not bad else f"{bad} BAD")
    return 1 if bad else 0


# ---------------------------------------------------------------- install
def cmd_install(a) -> int:
    kit = Kit(a.kit)
    if xplane_running() and not a.force:
        raise SystemExit("X-Plane is running: quit it first")
    cs, name = kit.custom_scenery, kit.cfg["pack_name"]
    ini = os.path.join(cs, "scenery_packs.ini")
    link = os.path.join(cs, name)
    if os.path.lexists(link) and os.path.realpath(link) != kit.pack:
        raise SystemExit(f"{link} exists and is not this kit's link")
    os.makedirs(os.path.join(kit.root, "backups"), exist_ok=True)
    backup = os.path.join(kit.root, "backups", "scenery_packs.ini."
                          + now().replace(":", ""))
    shutil.copy2(ini, backup)
    lines, newline = kit.PACKS.read_ini_lines(ini)
    added = kit.WP.ini_install(lines, name)
    row = next(i for i, line in enumerate(lines) if name in line)
    kit.PACKS.write_ini_lines(ini, lines, newline)
    if not os.path.lexists(link):
        os.symlink(kit.pack, link)
    kit.log({"event": "install", "ini": ini, "backup": backup,
             "row_added": added, "row_line": row + 1, "link": link})
    return 0


def cmd_restore(a) -> int:
    kit = Kit(a.kit)
    if xplane_running() and not a.force:
        raise SystemExit("X-Plane is running: quit it first")
    cs, name = kit.custom_scenery, kit.cfg["pack_name"]
    ini = os.path.join(cs, "scenery_packs.ini")
    lines, newline = kit.PACKS.read_ini_lines(ini)
    gone = kit.WP.ini_remove(lines, name)
    if gone:
        kit.PACKS.write_ini_lines(ini, lines, newline)
    link = os.path.join(cs, name)
    unlinked = os.path.islink(link) and os.path.realpath(link) == kit.pack
    if unlinked:
        os.remove(link)
    kit.log({"event": "restore", "ini_rows_removed": gone,
             "link_removed": unlinked})
    return 0


# ---------------------------------------------------------------- swaps
def swapin(kit: Kit, tile: str, force: bool, webapi: bool,
           staged_root: str | None = None) -> dict:
    lat, lon = kit.WP.parse_tile(tile)
    staged = os.path.join(staged_root or kit.staged, tile)
    if not os.path.isfile(os.path.join(staged, kit.WP.dsf_relpath(lat, lon))):
        raise SystemExit(f"nothing staged for {tile}: run stage or onthefly")
    pos = aircraft(kit, (lat, lon)) if webapi else {"webapi": "skipped"}
    reach = (pos.get("reach") or {}).get("tiles")
    window = pos.get("window") or {}
    if not force and ((reach is not None and reach <= 1)
                      or window.get("in_window")):
        kit.log({"event": "swapin_refused", "tile": tile, **pos})
        raise SystemExit(f"aircraft too close to {tile} (tiles away "
                         f"{reach}, X-Plane window {window}): X-Plane has "
                         "probably read its placeholder already; --force "
                         "to swap anyway")
    t0 = time.time()
    res = kit.WP.swap_in(kit.pack, staged, lat, lon)
    return kit.log({"event": "swapin", **res, "seconds": round(
        time.time() - t0, 3), "forced": force, **pos})


def cmd_swapin(a) -> int:
    kit = Kit(a.kit)
    root = {"staged": kit.staged, "drape": kit.drapes,
            "water": kit.drapes_water}[a.source]
    swapin(kit, a.tile, a.force, not a.no_webapi, staged_root=root)
    return 0


def cmd_swapout(a) -> int:
    kit = Kit(a.kit)
    lat, lon = kit.WP.parse_tile(a.tile)
    path = kit.WP.swap_out(kit.pack, lat, lon)
    kit.log({"event": "swapout", "tile": a.tile, "dsf": path,
             **aircraft(kit, (lat, lon))})
    return 0


# ---------------------------------------------------------------- onthefly
def run_build(kit: Kit, tile: str, minutes: float, nice: int,
              webapi: bool) -> tuple[int, str]:
    """The engine's headless tile build (``tools/run_tile_build.py``) into
    the kit's data root.  Returns (exit code, log path)."""
    lat, lon = kit.WP.parse_tile(tile)
    return run_engine(kit, tile, ["tools/run_tile_build.py", str(lat),
                                  str(lon)], f"build_{tile}.log", minutes,
                      nice, webapi)


def run_engine(kit: Kit, tile: str, argv: list, log_name: str,
               minutes: float, nice: int, webapi: bool,
               label: str = "building") -> tuple[int, str]:
    """One engine process (``venv/bin/python ARGV`` in the engine checkout)
    on the kit's data root; status every 30 s; Ctrl-C or the deadline
    kills the whole process group.  Returns (exit code, log path)."""
    lat, lon = kit.WP.parse_tile(tile)
    log = os.path.join(kit.build_root, log_name)
    os.makedirs(kit.build_root, exist_ok=True)
    env = dict(os.environ, ORTHO4XP_DATA_ROOT=kit.build_root)
    py = os.path.join(kit.engine, "venv", "bin", "python")
    with open(log, "w", encoding="utf-8") as out:
        proc = subprocess.Popen(
            [py, *argv], cwd=kit.engine, env=env, stdout=out,
            stderr=subprocess.STDOUT, start_new_session=True,
            preexec_fn=lambda: os.nice(nice))
    deadline, last = time.time() + 60 * minutes, 0.0
    try:
        while proc.poll() is None:
            if time.time() > deadline:
                os.killpg(proc.pid, signal.SIGTERM)
                proc.wait(30)
                print("TIMED_OUT")
                return 124, log
            if time.time() - last >= 30:
                last = time.time()
                step = _last_step(log)
                pos = aircraft(kit, (lat, lon)) if webapi else {}
                print(f"{now()} {label} {tile}: {step} | aircraft "
                      f"{pos.get('reach', pos.get('webapi', '-'))}", flush=True)
            time.sleep(2)
    except KeyboardInterrupt:
        os.killpg(proc.pid, signal.SIGTERM)
        proc.wait(30)
        kit.log({"event": f"{label}_aborted", "tile": tile})
        raise SystemExit("aborted: the pack was not touched") from None
    return proc.returncode, log


def _last_step(log: str) -> str:
    try:
        with open(log, encoding="utf-8", errors="replace") as h:
            steps = [line.strip() for line in h if line.startswith("=== step")]
        return steps[-1] if steps else "starting"
    except OSError:
        return "?"


def cmd_onthefly(a) -> int:
    kit = Kit(a.kit)
    lat, lon = kit.WP.parse_tile(a.tile)
    webapi = not a.no_webapi
    start = kit.log({"event": "onthefly_start", "tile": a.tile,
                     **(aircraft(kit, (lat, lon)) if webapi else {})})
    t0 = time.time()
    rc, log = run_build(kit, a.tile, a.max_minutes, a.nice, webapi)
    built = time.time() - t0
    if rc != 0:
        kit.log({"event": "onthefly_build_failed", "tile": a.tile, "rc": rc,
                 "log": log, "build_s": round(built)})
        return 1
    tile_dir = os.path.join(kit.build_root, "Tiles", f"zOrtho4XP_{a.tile}")
    stage(kit, a.tile, tile_dir)
    if a.no_swap:
        kit.log({"event": "onthefly_staged", "tile": a.tile,
                 "build_s": round(built), "start": start["utc"]})
        return 0
    res = swapin(kit, a.tile, force=True, webapi=webapi)
    kit.log({"event": "onthefly_done", "tile": a.tile, "start": start["utc"],
             "build_s": round(built), "total_s": round(time.time() - t0),
             "late_in_window": (res.get("window") or {}).get("in_window")})
    return 0


# ---------------------------------------------------------------- drape
def _fetch_script() -> str:
    """``O4_World_Drape_Fetch.py``: the kit's copy, else the engine's."""
    return os.path.join(HERE if KIT_MODE else os.path.join(REPO_ENGINE, "src"),
                        "O4_World_Drape_Fetch.py")


def _water_module() -> str:
    """``O4_World_Drape_Water.py`` beside the fetch script (the kit runs
    its own copy, ``--water-alpha``)."""
    return os.path.join(os.path.dirname(_fetch_script()),
                        "O4_World_Drape_Water.py")


def _last_json(log: str) -> dict | None:
    try:
        with open(log, encoding="utf-8", errors="replace") as h:
            lines = [line for line in h if line.startswith("{")]
        return json.loads(lines[-1]) if lines else None
    except (OSError, ValueError):
        return None


def cmd_drape(a) -> int:
    """Fetch the tile's imagery (placeholder tier), write the draped
    overlay, verify it with DSFTool, swap it in (always: a tile already in
    X-Plane's window shows only after ``reload``, which the log says)."""
    kit = Kit(a.kit)
    WP, DRAPE = kit.WP, kit.DRAPE
    lat, lon = WP.parse_tile(a.tile)
    webapi = not a.no_webapi
    exclude = tuple(x for x in (a.exclude or "").split(",") if x)
    water = (a.water_layer or DRAPE.WATER_LAYER_GROUP) if a.water_alpha else None
    start = kit.log({"event": "drape_start", "tile": a.tile,
                     "exclude": exclude, "water_layer": water,
                     **(aircraft(kit, (lat, lon)) if webapi else {})})
    t0 = time.time()
    work = os.path.join(kit.drapes, "work-water" if water else "work")
    rc, log = run_engine(
        kit, a.tile, [_fetch_script(), str(lat), str(lon), work, "--zl",
                      str(a.zl), "--provider", a.provider, "--drop",
                      str(a.drop), "--engine", kit.engine,
                      *(["--water-alpha"] if water else [])],
        f"drape_{a.tile}.log", a.max_minutes, a.nice, webapi, "draping")
    fetched = _last_json(log)
    t1 = time.time()
    if not fetched or not fetched.get("dds"):
        kit.log({"event": "drape_fetch_failed", "tile": a.tile, "rc": rc,
                 "log": log, "fetch": fetched})
        return 1
    staged_root = kit.drapes_water if water else kit.drapes
    final = os.path.join(staged_root, a.tile)
    shutil.rmtree(final + ".new", ignore_errors=True)
    os.makedirs(staged_root, exist_ok=True)
    counts = DRAPE.write_drape(lat, lon, a.zl, a.provider,
                               fetched["textures"], final + ".new", kit.tool,
                               exclude, water_layer=water)
    check = DRAPE.verify_drape(final + ".new", lat, lon, kit.tool)
    head = WP.dsf_header(os.path.join(final + ".new", WP.dsf_relpath(lat, lon)))
    if not _drape_ok(check) or not (head["magic_ok"] and head["md5_ok"]):
        raise SystemExit(f"drape {a.tile} failed its check: {check} {head}")
    shutil.rmtree(final, ignore_errors=True)
    os.rename(final + ".new", final)
    t2 = time.time()
    rec = {"event": "drape_staged", "tile": a.tile, "fetch": fetched,
           **counts, "verify": {k: check[k] for k in (
               "polygons", "pols_checked", "points", "excludes")},
           "fetch_s": round(t1 - t0, 1), "write_verify_s": round(t2 - t1, 1)}
    kit.log(rec)
    if a.no_swap:
        return 0
    res = swapin(kit, a.tile, force=True, webapi=webapi,
                 staged_root=staged_root)
    late = (res.get("window") or {}).get("in_window")
    kit.log({"event": "drape_done", "tile": a.tile, "start": start["utc"],
             "total_s": round(time.time() - t0, 1), "late_in_window": late,
             "next": "run `world.py reload` to see it now" if late else
             "X-Plane opens it when its column enters the window"})
    return 0


# ---------------------------------------------------------------- status
def cmd_status(a) -> int:
    kit = Kit(a.kit)
    WP = kit.WP
    pos = aircraft(kit, None) if not a.no_webapi else {}
    print("aircraft:", pos or "not read")
    link = os.path.join(kit.custom_scenery, kit.cfg["pack_name"])
    print("installed link:", os.path.islink(link)
          and os.path.realpath(link) == kit.pack)
    for t in kit_tiles(kit):
        name = WP.tile_name(*t)
        path = os.path.join(kit.pack, WP.dsf_relpath(*t))
        state = tile_state(kit, path).upper().replace("PLACEHOLDER",
                                                       "placeholder")
        staged = os.path.isdir(os.path.join(kit.staged, name))
        staged = (f"{staged} drape={os.path.isdir(os.path.join(kit.drapes, name))}"
                  f" water={os.path.isdir(os.path.join(kit.drapes_water, name))}")
        reach = (kit.WIN.reach(pos["cam_lat"], pos["cam_lon"], *t)
                 if "lat" in pos else "")
        print(f"  {name}  {state:11s} staged={staged}  {reach}")
    return 0


def cmd_reload(a) -> int:
    kit = Kit(a.kit)
    sent = kit.API.reload_scenery()
    kit.log({"event": "reload_scenery", "sent": sent, **aircraft(kit, None)})
    return 0 if sent else 1


def _console():
    """``O4_Console_Encoding`` from the engine checkout (the kit's
    ``engine_dir`` in kit mode)."""
    engine = REPO_ENGINE
    if KIT_MODE:
        with open(os.path.join(HERE, "kit.json"), encoding="utf-8") as h:
            engine = _engine_dir(json.load(h))
    src = os.path.join(engine, "src")
    if src not in sys.path:
        sys.path.insert(0, src)
    import O4_Console_Encoding
    return O4_Console_Encoding


def main(argv=None) -> int:
    _console().configure_console_streams()
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--kit", default=HERE if KIT_MODE else None)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("make-kit")
    s.add_argument("--center", required=True)
    s.add_argument("--radius", type=int, default=2)
    s.add_argument("--skip", action="append", default=[])
    s.add_argument("--extra", action="append", default=[],
                   help="a placeholder tile outside the block")
    s.add_argument("--xplane", default=os.path.expanduser("~/X-Plane 12"))
    s.add_argument("--engine", default=None)
    s.set_defaults(fn=cmd_make_kit)
    s = sub.add_parser("stage")
    s.add_argument("tile")
    s.add_argument("--tile-dir", required=True)
    s.set_defaults(fn=cmd_stage)
    for name, fn in (("verify", cmd_verify), ("reload", cmd_reload)):
        sub.add_parser(name).set_defaults(fn=fn)
    for name, fn in (("install", cmd_install), ("restore", cmd_restore)):
        s = sub.add_parser(name)
        s.add_argument("--force", action="store_true",
                       help="even while X-Plane runs (tests only)")
        s.set_defaults(fn=fn)
    s = sub.add_parser("swapin")
    s.add_argument("tile")
    s.add_argument("--from", dest="source", default="staged",
                   choices=("staged", "drape", "water"),
                   help="staged (built tile), drape or water (drapes/water)")
    s.add_argument("--force", action="store_true")
    s.add_argument("--no-webapi", action="store_true")
    s.set_defaults(fn=cmd_swapin)
    s = sub.add_parser("swapout")
    s.add_argument("tile")
    s.set_defaults(fn=cmd_swapout)
    s = sub.add_parser("onthefly")
    s.add_argument("tile")
    s.add_argument("--max-minutes", type=float, default=60)
    s.add_argument("--nice", type=int, default=10)
    s.add_argument("--no-swap", action="store_true")
    s.add_argument("--no-webapi", action="store_true")
    s.set_defaults(fn=cmd_onthefly)
    s = sub.add_parser("drape")
    s.add_argument("tile")
    s.add_argument("--exclude", default="",
                   help="default-scenery classes to hide under the tile, "
                        "comma-separated: for (forests), obj (objects/"
                        "autogen), net (roads), ...; default none")
    s.add_argument("--water-alpha", action="store_true",
                   help="also lay the photo with the regular build's water "
                        "mask as alpha over water (staged in drapes/water)")
    s.add_argument("--water-layer", default=None,
                   help="layer group of the water copy (default "
                        "O4_World_Drape.WATER_LAYER_GROUP)")
    s.add_argument("--zl", type=int, default=16)
    s.add_argument("--provider", default="BI")
    s.add_argument("--drop", type=int, default=3,
                   help="zoom levels below --zl fetched (3 = 512 px)")
    s.add_argument("--max-minutes", type=float, default=15)
    s.add_argument("--nice", type=int, default=10)
    s.add_argument("--no-swap", action="store_true")
    s.add_argument("--no-webapi", action="store_true")
    s.set_defaults(fn=cmd_drape)
    s = sub.add_parser("status")
    s.add_argument("--no-webapi", action="store_true")
    s.set_defaults(fn=cmd_status)
    a = p.parse_args(argv)
    if not a.kit:
        p.error("--kit DIR is required outside a kit")
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
