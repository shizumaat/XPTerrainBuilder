#!/usr/bin/env python3
"""THE TERRAIN SHELLS' SKIRT SEAT, REPLAYED ON A DRAWN MESH (#2272 round 3).

Where would ``auto_patch_v2.airport.shell_seat`` seat a pack's kept small
terrain shells, and what would show?  Offline, on a BUILT tile DSF (a
control build's drawn mesh: the seat leaves our ground untouched, so the
arm draws the same mesh): the pack's shells from
``tools/terrain_model_census`` (or its ``--census`` JSON) as
``terrain_model.seat_records`` writes them, then the production seat
(``shell_seat.seat_shells``) on that mesh.  Per shell the seat's report
(``dz``, the skirt's depth, the land / wet stations, the 5th percentile of
the rim's need: the seat that would close 95 % of the land rim) and, for
two seats -- AUTHOR (its frame zero ``z0``) and SKIRT (``z0 + dz``):

* RIM GAP -- the largest gap under the rim over the land stations
  (``shell_seat.rim_need``: the drawn instrument's station);
* THROUGH -- the drawn ground over the shell's top by more than
  :data:`OVER_M` deeper than ``terrain_cut.BAND_M`` from its edge (1 m
  samples; ground at the sea datum not judged): area and worst.

A ROCK (``terrain_rock``, RULINGS 2026-11-25j; census verdict ``rock``)
is seated by the same skirt seat and replayed with the shells.  ``--dem``
replays on the census's own RAW rasters (``terrain_model_census.rasters``:
the tile ``.hgt`` under its cached insets) instead of a built tile's
drawn mesh -- the lane's synthetic-first arm, no tile build: the seat it
prints differs from a build's by the bake (smoothing, flattening).

Read-only (DSF dumps in a temp dir).

    venv/bin/python tools/shell_seat_replay.py ICAO (--tile-dsf DSF | --dem)
        --pack DIR [--census JSON] [--json OUT]
"""
from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import sys
import tempfile

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (os.path.join(HERE, "..", "src"), HERE, os.path.join(HERE, "harness")):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import O4_Console_Encoding as _o4console  # noqa: E402

_o4console.configure_console_streams()

__all__ = ["OVER_M", "SEATED_VERDICTS", "shell_records", "surface_of", "dem_surface",
           "through", "measure", "run", "main"]

#: drawn ground this far over the shell's top pokes through it
OVER_M = 0.05
#: the census verdicts the skirt seat seats (a small shell and a rock)
SEATED_VERDICTS = ("terrain shell", "rock")


def shell_records(rows: list[dict], pack_root: str) -> list[dict]:
    """The seat records ``terrain_model.seat_records`` writes for the
    census rows a kept shell reads as (``verdict`` ``terrain shell``)."""
    from auto_patch_v2.airport import terrain_model as TM
    out = []
    for k, r in enumerate(rows):
        if r.get("verdict") not in SEATED_VERDICTS:
            continue
        out.append({"id": f"shell{k}", "model": f"shell{k}", "resource": r["resource"],
                    "seat": TM.SEAT, "elevation": float(r["z0"]),
                    "shell": {"file": os.path.join(pack_root, r["resource"]),
                              "lat": float(r["lat"]), "lon": float(r["lon"]),
                              "heading": float(r["heading"])}})
    return out


def surface_of(mesh):
    """A drawn mesh (``drawn_site.DrawnMesh``) as the placement write's
    surface: ``(lat, lon) -> z | None`` with ``.many``."""
    def many(lats, lons):
        return [None if not np.isfinite(z) else float(z) for z in mesh.z(lats, lons)]

    def one(lat, lon):
        return many([lat], [lon])[0]
    one.many = many
    return one


def dem_surface(lats: list, lons: list):
    """The ``--dem`` arm's surface (module doc): the census's raw rasters
    of the tile holding the first shell, as :func:`surface_of` answers."""
    import terrain_model_census as TMC
    lat0, lon0 = float(lats[0]), float(lons[0])
    dems = TMC.rasters(TMC.DEFAULT_ELEVATION, math.floor(lat0), math.floor(lon0))
    read = TMC.sampler(dems, lon0, lat0)
    m_lon = 111_320.0 * math.cos(math.radians(lat0))

    def many(la, lo):
        xs = (np.asarray(lo, float) - lon0) * m_lon
        ys = (np.asarray(la, float) - lat0) * 111_320.0
        return [None if not np.isfinite(z) else float(z) for z in read(xs, ys)]

    def one(lat, lon):
        return many([lat], [lon])[0]
    one.many = many
    return one


def through(pl, base: float, surface) -> dict:
    """THROUGH (module doc) of the shell ``pl`` seated with its zero at
    ``base``."""
    from auto_patch_v2.airport import shell_seat as SS
    from auto_patch_v2.airport.terrain_cut import BAND_M
    r = pl.raster
    ij = np.argwhere(SS.edge_depth(r) > BAND_M)
    if not len(ij):
        return {"body_m2": 0.0, "through_m2": 0.0, "worst_m": None}
    e, n = r.centres(ij)
    lons, lats = pl.to_ll(e, n)
    z = np.array([np.nan if v is None else v for v in surface.many(list(lats), list(lons))],
                 float)
    d = z - (base + r.top[ij[:, 0], ij[:, 1]])
    judged = np.isfinite(d) & (z > SS.WATER_TOL_M)
    over = judged & (d > OVER_M)
    cell = r.step * r.step
    return {"body_m2": round(float(len(ij) * cell), 1),
            "through_m2": round(float(over.sum() * cell), 1),
            "through_pct": round(100.0 * float(over.sum()) / max(int(judged.sum()), 1), 1),
            "worst_m": round(float(np.nanmax(np.where(judged, d, np.nan))), 2)
            if judged.any() else None}


def measure(records: list[dict], surface) -> list[dict]:
    """Per shell the seat report and the two seats' RIM GAP and THROUGH."""
    from auto_patch_v2.airport import shell_seat as SS
    shells = [p for p in (SS.placed(r) for r in records) if p is not None]
    _recs, reps = SS.seat_shells(records, surface)
    by = {r["model"]: r for r in reps}
    out = []
    for pl in shells:
        rep = dict(by[pl.model])
        st = SS.rim_need(pl, [o for o in shells if o is not pl], surface)
        need = st["need"][st["land"]]
        rep["need_p5_m"] = round(float(np.percentile(need, 5.0)), 2) if len(need) else None
        seats = {"author": pl.z0, "skirt": pl.z0 + rep["dz"]}
        for name, base in seats.items():
            gap = float(max(0.0, -(need - (base - pl.z0)).min())) if len(need) else 0.0
            rep[name] = {"base_m": round(base, 2), "rim_gap_m": round(gap, 2),
                         **through(pl, base, surface)}
        out.append(rep)
    return out


def run(args) -> dict:
    import drawn_site as DS
    if args.census and os.path.isfile(args.census):
        with open(args.census, encoding="utf-8") as fh:
            rows = json.load(fh)[0]["rows"]
    else:
        import terrain_model_census as TMC
        rows = TMC.census(args.pack, TMC.DEFAULT_ELEVATION, DS.dsftool())["rows"]
    records = shell_records(rows, args.pack)
    if not records:
        raise SystemExit(f"NOT MEASURED: no terrain shell in {args.pack}")
    lats = [r["shell"]["lat"] for r in records]
    lons = [r["shell"]["lon"] for r in records]
    pad = 600.0 / DS.K_LAT
    box = (min(lons) - pad / math.cos(math.radians(lats[0])), min(lats) - pad,
           max(lons) + pad / math.cos(math.radians(lats[0])), max(lats) + pad)
    if args.dem:
        return {"icao": args.icao, "tile_dsf": "raw DEM", "pack": args.pack,
                "shells": measure(records, dem_surface(lats, lons))}
    work = tempfile.mkdtemp(prefix="shell_seat_replay_")
    try:
        mesh = DS.DrawnMesh(box, "", DS.dsftool(), args.tile_dsf, work)
        shells = measure(records, surface_of(mesh))
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return {"icao": args.icao, "tile_dsf": args.tile_dsf, "pack": args.pack, "shells": shells}


def print_report(rep: dict) -> None:
    print(f"{rep['icao']}: {len(rep['shells'])} shell(s) on {rep['tile_dsf']}")
    print(f"  {'shell':<34} {'dz':>6} {'depth':>6} {'land':>5} {'wet':>5} "
          f"{'p5 need':>7} {'gap author/skirt':>17} {'through m2 (worst) author / skirt'}")
    for s in rep["shells"]:
        name = os.path.basename(s["resource"])[:34]
        gaps = "/".join(f"{s[k]['rim_gap_m']:.2f}" for k in ("author", "skirt"))
        thr = " / ".join(f"{s[k]['through_m2']:.0f} ({s[k]['worst_m']})"
                         for k in ("author", "skirt"))
        p5 = "-" if s["need_p5_m"] is None else f"{s['need_p5_m']:+.2f}"
        flag = "" if s["fixed"] else "  REPORTED"
        print(f"  {name:<34} {s['dz']:+6.2f} {s['depth_m']:6.2f} {s['land']:5d} {s['wet']:5d} "
              f"{p5:>7} {gaps:>17} {thr}{flag}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("icao")
    where = ap.add_mutually_exclusive_group(required=True)
    where.add_argument("--tile-dsf", help="a built tile DSF (the drawn mesh)")
    where.add_argument("--dem", action="store_true",
                       help="the census's raw rasters instead of a drawn mesh (module doc)")
    ap.add_argument("--pack", required=True, help="the pack root carrying the shells")
    ap.add_argument("--census", help="a tools/terrain_model_census --json output")
    ap.add_argument("--json", help="write the report here")
    args = ap.parse_args(argv)
    rep = run(args)
    print_report(rep)
    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(rep, fh, indent=1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
