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
prints differs from a build's by the bake (smoothing, flattening).  A rock
whose skirt runs out (census ``fill_z0``, ``terrain_rock.fill_seat``) has
its RUN-OUT FILL replayed first (:func:`filled_surface`: our ground raised
to its rim on a ``--posting-m`` raster, frozen inside ``--patch``).

Read-only (DSF dumps in a temp dir).

    venv/bin/python tools/shell_seat_replay.py ICAO (--tile-dsf DSF | --dem
        [--patch OSM] [--posting-m M]) --pack DIR [--census JSON] [--json OUT]
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

__all__ = ["OVER_M", "SEATED_VERDICTS", "shell_records", "patch_area", "filled_surface", "floating",
           "surface_of", "dem_surface", "through", "measure", "run", "main"]

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
                              "heading": float(r["heading"])},
                    **({"fill_z0": float(r["fill_z0"])} if r.get("fill_z0") is not None
                       else {})})
    return out


def patch_area(path: str):
    """The union of a patch ``.osm``'s valid closed ways (``lon, lat``;
    ``O4_Vector_Map.include_patches``' ``patches_area`` inputs), or
    ``None`` without one -- the ``--patch`` arm's frozen postings."""
    if not path:
        return None
    import xml.etree.ElementTree as ET

    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    root = ET.parse(path).getroot()
    nodes = {n.get("id"): (float(n.get("lon")), float(n.get("lat"))) for n in root.iter("node")}
    polys = []
    for w in root.iter("way"):
        refs = [nd.get("ref") for nd in w.iter("nd")]
        if len(refs) > 3 and refs[0] == refs[-1] and all(r in nodes for r in refs):
            poly = Polygon([nodes[r] for r in refs])
            if poly.is_valid:
                polys.append(poly)
    return unary_union(polys) if polys else None


def filled_surface(records: list[dict], surface, patch, posting_m: float):
    """THE RUN-OUT FILL replayed (``terrain_cut_stage.run_out_fill``): per
    record carrying ``fill_z0`` a raster of ``surface`` at ``posting_m``
    around it, frozen inside ``patch``, filled; ``(surface with the fills'
    change, {model: fill report})`` -- the report counts the seat's land
    stations inside the patch (``in_patch``: reported unserved there,
    RULINGS 2026-11-25l (3))."""
    import shapely
    from auto_patch import terrain_cut_stage as TCS
    from auto_patch_v2.airport import shell_seat as SS
    from auto_patch_v2.airport import terrain_fill as TF
    from auto_patch_v2.airport.terrain_model import MIN_PLAN_M
    deltas, reps = [], {}
    for rec in records:
        if rec.get("fill_z0") is None:
            continue
        lat, lon = rec["shell"]["lat"], rec["shell"]["lon"]
        half = 0.5 * MIN_PLAN_M + TF.REACH_M + 2.0 * posting_m
        dlat = posting_m / 111_320.0
        dlon = dlat / math.cos(math.radians(lat))
        n = int(math.ceil(half / posting_m))
        lons = lon + dlon * np.arange(-n, n + 1)
        lats = lat + dlat * np.arange(n, -n - 1, -1)
        glon, glat = np.meshgrid(lons, lats)
        alt = np.array([np.nan if z is None else z for z in
                        surface.many(glat.ravel().tolist(), glon.ravel().tolist())],
                       float).reshape(glon.shape)
        frozen = None
        if patch is not None:
            def frozen(rows, cols, plons, plats):
                return shapely.contains_xy(patch, plons, plats)
        raster = TF.Raster(alt.copy(), float(lons[0]), float(lats[0]), dlon, dlat, frozen)
        rep = dict(TCS.run_out_fill(raster, rec))
        pl = SS.placed(rec)
        st = SS.rim_need(pl, [], surface)
        rep["stations"] = int(st["land"].sum())
        rep["in_patch"] = 0 if patch is None else int(shapely.contains_xy(
            patch, st["lons"][st["land"]], st["lats"][st["land"]]).sum())
        reps[rec["model"]] = rep
        deltas.append(TF.Raster(raster.alt - alt, float(lons[0]), float(lats[0]), dlon, dlat))

    def many(la, lo):
        base = surface.many(la, lo)
        add = np.zeros(len(base))
        for d in deltas:
            v = d.sample(np.asarray(lo, float), np.asarray(la, float))
            add += np.where(np.isfinite(v), v, 0.0)
        return [None if z is None else float(z) + float(a) for z, a in zip(base, add, strict=True)]

    def one(lat, lon):
        return many([lat], [lon])[0]
    one.many = many
    return one, reps


def floating(rec: dict, dz: float, surface, patch, posting_m: float) -> dict:
    """Where the rim still FLOATS after the run-out fill: the land stations
    left more than ``terrain_fill.SERVED_M`` over our ground at the seat
    ``dz`` -- inside the patch (reported unserved, RULINGS 2026-11-25l
    (3)), within ``posting_m`` of it (its frozen postings hold the
    raster there) and elsewhere -- and the worst left elsewhere."""
    import shapely
    from auto_patch_v2.airport import shell_seat as SS
    from auto_patch_v2.airport.terrain_fill import SERVED_M
    st = SS.rim_need(SS.placed(rec), [], surface)
    land = st["land"]
    gap = np.maximum(0.0, dz - st["need"][land])
    lo, la = st["lons"][land], st["lats"][land]
    inside = near = np.zeros(len(gap), bool)
    if patch is not None:
        inside = shapely.contains_xy(patch, lo, la)
        near = ~inside & (shapely.distance(shapely.points(np.c_[lo, la]), patch)
                          * 111_320.0 <= posting_m / max(math.cos(math.radians(la[0])), 0.1))
    free = ~inside & ~near
    over = gap > SERVED_M
    return {"floating_in_patch": int((over & inside).sum()),
            "floating_at_patch": int((over & near).sum()),
            "floating_free": int((over & free).sum()),
            "worst_free_m": round(float(gap[free].max()), 2) if free.any() else 0.0}


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
        patch = patch_area(args.patch)
        surface, fills = filled_surface(records, dem_surface(lats, lons), patch, args.posting_m)
        shells = measure(records, surface)
        for s in shells:
            if s["model"] in fills:
                s["fill"] = dict(fills[s["model"]], **floating(
                    [r for r in records if r["model"] == s["model"]][0], s["dz"], surface,
                    patch, args.posting_m))
        return {"icao": args.icao, "tile_dsf": "raw DEM", "pack": args.pack, "shells": shells}
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
        if "fill" in s:
            f = s["fill"]
            print(f"    run-out fill: {f.get('raised', 0)} posting(s) raised from "
                  f"{f.get('supports', 0)} support(s), {f.get('unserved', 0)} unserved; "
                  f"{f['in_patch']} of {f['stations']} land station(s) inside the patch")
            print(f"    still floating > SERVED_M: {f['floating_in_patch']} in the patch, "
                  f"{f['floating_at_patch']} within a posting of it, {f['floating_free']} "
                  f"elsewhere (worst elsewhere {f['worst_free_m']:.2f} m)")


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
    ap.add_argument("--patch", help="--dem: the airport's patch .osm (its postings frozen)")
    ap.add_argument("--posting-m", type=float, default=10.0,
                    help="--dem: the run-out fill's raster posting (m)")
    args = ap.parse_args(argv)
    rep = run(args)
    print_report(rep)
    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(rep, fh, indent=1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
