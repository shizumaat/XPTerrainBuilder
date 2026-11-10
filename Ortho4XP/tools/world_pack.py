"""World pack kit: ONE Custom Scenery pack with a placeholder DSF for every
tile, real tiles swapped in while X-Plane flies (owner idea 2026-11-10;
module ``src/O4_World_Pack.py``).

Run from the engine checkout (``cd Ortho4XP && venv/bin/python
tools/world_pack.py --kit KIT ...``) or from a kit's own copy
(``python KIT/world.py ...``: the kit's ``kit.json`` names the engine
checkout).  Subcommands:

  make-kit --kit DIR --center +53-061 --radius 2 --skip +53-061
      the pack folder with round-trip-checked placeholder DSFs, kit.json
  stage TILE --tile-dir DIR    a built zOrtho4XP_<tile> laid out for the
                               pack (per-tile terrain/textures folders) + verify
  verify                       every placeholder and staged tile, by DSFTool
  install / restore            Custom Scenery link + scenery_packs.ini row
                               (X-Plane closed; backup kept in the kit)
  swapin TILE [--force]        staged tile -> pack, one rename of the DSF;
                               refused when the aircraft is within 1 tile
  swapout TILE                 placeholder back over the DSF
  onthefly TILE                build TILE now (light settings, kit data
                               root), stage, verify, swap in; Ctrl-C safe
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
    """O4_World_Pack from the kit's copy (kit mode) or the engine's src; the
    rest from the engine's src."""
    for path in (os.path.join(engine, "src"),
                 HERE if KIT_MODE else os.path.join(REPO_ENGINE, "src")):
        if path not in sys.path:
            sys.path.insert(0, path)
    import O4_World_Pack as WP
    import O4_Scenery_Packs as PACKS
    import O4_XPlane_WebAPI as API
    return WP, PACKS, API


def now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")


class Kit:
    """Paths of one kit (``kit.json``) and its log."""

    def __init__(self, root: str):
        self.root = os.path.abspath(root)
        with open(os.path.join(self.root, "kit.json"), encoding="utf-8") as h:
            self.cfg = json.load(h)
        self.engine = _engine_dir(self.cfg)
        self.WP, self.PACKS, self.API = _imports(self.engine)
        self.pack = os.path.join(self.root, self.cfg["pack_name"])
        self.staged = os.path.join(self.root, "staged")
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
        out["reach"] = kit.WP.tile_reach(lat, lon, *tile)
        out["window"] = kit.WP.xp_window(clat, clon, *tile)
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
    WP, _, _ = _imports(engine)
    os.makedirs(root, exist_ok=True)
    cfg = {"pack_name": WP.PACK_NAME, "engine_dir": engine,
           "xplane_dir": a.xplane, "center": a.center, "radius": a.radius,
           "skip": a.skip, "extra": a.extra, "made": now()}
    with open(os.path.join(root, "kit.json"), "w", encoding="utf-8") as h:
        json.dump(cfg, h, indent=1)
    kit = Kit(root)
    made = [WP.tile_name(*t) for t in kit_tiles(kit)]
    for t in kit_tiles(kit):
        WP.write_placeholder(kit.pack, *t, kit.tool)
    if KIT_MODE is False:                 # copy the two files the kit runs
        shutil.copy2(os.path.abspath(__file__), os.path.join(root, "world.py"))
        shutil.copy2(WP.__file__, root)
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
    counts = kit.WP.relayout_tile(tile_dir, work, lat, lon, kit.tool)
    check = kit.WP.verify_tile(work, lat, lon, kit.tool)
    if check["problems"] or check["overlay"] or not check["pack_defs"]:
        raise SystemExit(f"staged {tile} failed its check: {check}")
    shutil.rmtree(final, ignore_errors=True)
    os.rename(work, final)
    return kit.log({"event": "stage", "tile": tile, "tile_dir": tile_dir,
                    **counts, "verify": check})


def cmd_stage(a) -> int:
    stage(Kit(a.kit), a.tile, os.path.abspath(a.tile_dir))
    return 0


def cmd_verify(a) -> int:
    kit = Kit(a.kit)
    WP, bad = kit.WP, 0
    for t in kit_tiles(kit):
        path = os.path.join(kit.pack, WP.dsf_relpath(*t))
        state = "placeholder" if WP.is_placeholder(path) else "real"
        res = WP.verify_tile(kit.pack, *t, kit.tool)
        head = WP.dsf_header(path)
        ok = (res["overlay"] and not res["defs"]) if state == "placeholder" \
            else (not res["problems"] and not res["overlay"])
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
            res = WP.verify_tile(root, *WP.parse_tile(name), kit.tool)
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
def swapin(kit: Kit, tile: str, force: bool, webapi: bool) -> dict:
    lat, lon = kit.WP.parse_tile(tile)
    staged = os.path.join(kit.staged, tile)
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
    swapin(Kit(a.kit), a.tile, a.force, not a.no_webapi)
    return 0


def cmd_swapout(a) -> int:
    kit = Kit(a.kit)
    lat, lon = kit.WP.parse_tile(a.tile)
    path = kit.WP.swap_out(kit.pack, lat, lon, kit.tool)
    kit.log({"event": "swapout", "tile": a.tile, "dsf": path,
             **aircraft(kit, (lat, lon))})
    return 0


# ---------------------------------------------------------------- onthefly
def run_build(kit: Kit, tile: str, minutes: float, nice: int,
              webapi: bool) -> tuple[int, str]:
    """The engine's headless tile build (``tools/run_tile_build.py``) into
    the kit's data root; status every 30 s; Ctrl-C or the deadline kills
    the whole build process group.  Returns (exit code, log path)."""
    lat, lon = kit.WP.parse_tile(tile)
    log = os.path.join(kit.build_root, f"build_{tile}.log")
    env = dict(os.environ, ORTHO4XP_DATA_ROOT=kit.build_root)
    py = os.path.join(kit.engine, "venv", "bin", "python")
    with open(log, "w", encoding="utf-8") as out:
        proc = subprocess.Popen(
            [py, "tools/run_tile_build.py", str(lat), str(lon)],
            cwd=kit.engine, env=env, stdout=out, stderr=subprocess.STDOUT,
            start_new_session=True, preexec_fn=lambda: os.nice(nice))
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
                print(f"{now()} building {tile}: {step} | aircraft "
                      f"{pos.get('reach', pos.get('webapi', '-'))}", flush=True)
            time.sleep(2)
    except KeyboardInterrupt:
        os.killpg(proc.pid, signal.SIGTERM)
        proc.wait(30)
        kit.log({"event": "onthefly_aborted", "tile": tile})
        raise SystemExit("aborted: the pack was not touched") from None
    return proc.returncode, log


def _last_step(log: str) -> str:
    try:
        with open(log, encoding="utf-8", errors="replace") as h:
            steps = [ln.strip() for ln in h if ln.startswith("=== step")]
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
        state = "placeholder" if WP.is_placeholder(path) else "REAL"
        staged = os.path.isdir(os.path.join(kit.staged, name))
        reach = (WP.tile_reach(pos["lat"], pos["lon"], *t),
                 WP.xp_window(pos["cam_lat"], pos["cam_lon"], *t)) \
            if "lat" in pos else ""
        print(f"  {name}  {state:11s} staged={staged}  {reach}")
    return 0


def cmd_reload(a) -> int:
    kit = Kit(a.kit)
    sent = kit.API.reload_scenery()
    kit.log({"event": "reload_scenery", "sent": sent, **aircraft(kit, None)})
    return 0 if sent else 1


def main(argv=None) -> int:
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
    s = sub.add_parser("status")
    s.add_argument("--no-webapi", action="store_true")
    s.set_defaults(fn=cmd_status)
    a = p.parse_args(argv)
    if not a.kit:
        p.error("--kit DIR is required outside a kit")
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
