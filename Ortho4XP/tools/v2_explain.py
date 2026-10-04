"""``venv/bin/python tools/v2_explain.py ICAO --shape N [--patch P] | --at
LAT,LON [--sources] [--roles]`` — EXPLAIN a classification verdict (owner
2026-09-04j, deliverable 6): for a coordinate or a shipped patch's
``shapeID``, the v2 cell(s) there with the role, the evidence record the
verdict used, the source polygons under it with their own records
(``classify/sources.py``), and the centrelines that touch it.  Pure
reporting over ``Classification``: production never calls it, so it lives
here and not in the engine package (RULINGS 2026-10-04c (4); it was
``auto_patch_v2/classify/explain.py`` + the ``explain`` subcommand of
``python -m auto_patch_v2``).

THE DEFAULT PATCH (RULINGS 2026-09-13cs chip): without ``--patch`` the
shapeIDs are read from the patch the DATA-ROOT RESOLUTION lands a tile
build's product at — ``<root>/Patches/<block>/<tile>/<ICAO>_auto.patch.osm``
with ``<root>`` the first of ``--data-root``, the engine's own data root
when one is chosen (``O4_File_Names.current_data_root``: the
``ORTHO4XP_DATA_ROOT`` the app hands every engine process), the default
data root (``O4_File_Names.default_data_root``) and, last, the engine
tree — that HOLDS the patch.  Before 09-13 the engine tree was the only
default, and a lane's ``Patches/`` clone is days stale.  Every run prints
the patch it resolved, where it came from and its mtime, so a shapeID is
never read off an unnamed product.
"""
from __future__ import annotations

# The console is UTF-8 before anything prints (#171, #125): ONE derivation
# site, ``src/O4_Console_Encoding.py``.  Twin: ``tests/test_console_encoding.py``.
import os as _o4os, sys as _o4sys                                    # noqa: E402
_o4sys.path.insert(0, _o4os.path.join(_o4os.path.dirname(_o4os.path.dirname(
    _o4os.path.abspath(__file__))), "src"))
import O4_Console_Encoding as _o4console                             # noqa: E402
_o4console.configure_console_streams()
_o4sys.path.insert(0, _o4os.path.dirname(_o4os.path.abspath(__file__)))

import argparse
import os
import sys
import typing as _t
import xml.etree.ElementTree as ET

from shapely.geometry import Point, Polygon

from auto_patch_v2.model.airport import Airport
from auto_patch_v2.classify.evidence import Evidence
from auto_patch_v2.classify.roles import Cell, Classification
from auto_patch_v2.planar.__main__ import (ENGINE_DIR, add_dem_frame_args,
                                           default_inputs)

__all__ = ["shape_polygon", "explain_at", "explain_polygon", "render",
           "role_census", "build_parser", "resolve_default_patch",
           "default_patch_candidates", "patch_provenance_line", "main"]

#: Evidence keys that mark a cell a rule RE-KINDED away from the verdict
#: the ladder would otherwise have given it — the census names each one
#: with the number the rule read (§40 (1) / (2), owner RULINGS
#: 2026-09-13co items 1 and 6).  A rule that re-kinds without leaving a
#: mark here is invisible to the before/after read, which is the whole
#: instrument: add the key with the rule.
REKIND_MARKS: tuple[tuple[str, str], ...] = (
    ("shoulder_shared_m", "runway shoulder (§40 (1))"),
    ("apron_cover_refused_corridor", "apron cover refused the corridor (§40 (2))"),
    ("startup_refused_corridor", "a 1300 startup inside refused the corridor (#262)"),
    ("airside_edge_flip", "airside edge (§27)"),
    ("taxi_name", "taxi by name (04z-1)"),
    ("open_default", "open default (04u)"),
    ("neck_cut", "apron cut at a neck: the neck (§43 (1))"),
    ("neck_new_apron", "apron cut at a neck: the apron beyond (§43 (1))"),
    ("demoted", "touch-chain demotion"),
)


def role_census(cl: Classification, airport: Airport | None = None,
                marks: bool = True) -> list[str]:
    """THE ROLE CENSUS of one classification: cells and area per role,
    then every RE-KINDED cell named with the evidence its rule read.

    The dry before/after read a role-law change is accepted on (§40's
    BARS): it counts nothing and prices no law — every number is the
    classification's own."""
    by_role: dict[str, list[float]] = {}
    for c in cl.cells:
        by_role.setdefault(c.role, []).append(Polygon(c.ring, c.holes).area)
    out = [f"{'role':<22} {'cells':>6} {'area_m2':>12}"]
    for role in sorted(by_role, key=lambda r: (-sum(by_role[r]), r)):
        a = by_role[role]
        out.append(f"{role:<22} {len(a):>6} {sum(a):>12,.0f}")
    out.append(f"{'TOTAL':<22} {len(cl.cells):>6} "
               f"{sum(sum(v) for v in by_role.values()):>12,.0f}")
    if not marks:
        return out
    to_ll = airport.frame.transformers()[1] if airport is not None else None
    for key, label in REKIND_MARKS:
        rows = [c for c in cl.cells if c.evidence.get(key)]
        out.append(f"-- {label}: {len(rows)} cell(s)")
        for c in sorted(rows, key=lambda c: -Polygon(c.ring, c.holes).area):
            p = Polygon(c.ring, c.holes)
            lat_lon = ""
            if to_ll is not None:
                lat, lon = to_ll(p.centroid.x, p.centroid.y)
                lat_lon = f" at {lat:.7f},{lon:.7f}"
            out.append(f"   cell {c.id} role={c.role} kind={c.kind} ref={c.ref} "
                       f"area={p.area:,.0f} m2{lat_lon}: "
                       + ", ".join(f"{k}={_fmt(v)}" for k, v in c.evidence.items()))
    return out


def shape_polygon(patch_path: str, shape_id: int, airport: Airport
                  ) -> tuple[Polygon, dict[str, str]] | None:
    """The ring of way ``shapeID=N`` in a shipped patch (the role-carrying
    way, not its interior rings), in the airport frame, with its tags."""
    root = ET.parse(patch_path).getroot()
    nodes = {n.get("id"): (float(n.get("lat")), float(n.get("lon")))
             for n in root.iter("node")}
    to_xy, _to_ll = airport.frame.transformers()
    for w in root.iter("way"):
        tags = {t.get("k"): t.get("v") for t in w.findall("tag")}
        if tags.get("shapeID") != str(shape_id) or "role" not in tags:
            continue
        pts = [nodes[nd.get("ref")] for nd in w.findall("nd")]
        xy = [to_xy(lon, lat) for lat, lon in pts]
        if len(xy) < 3:
            continue
        poly = Polygon(xy)
        if not poly.is_valid:
            poly = poly.buffer(0)
        return poly, tags
    return None


def _fmt(v: object) -> str:
    if isinstance(v, float):
        return f"{v:.3g}" if abs(v) < 1000 else f"{v:,.0f}"
    return str(v)


def _cell_lines(c: Cell, poly: Polygon, overlap: float | None, cl: Classification,
                ev: Evidence, airport: Airport) -> list[str]:
    out = [f"cell {c.id}: role={c.role} side={c.side} kind={c.kind} ref={c.ref} "
           f"area={poly.area:,.0f} m2" + (f" overlap={overlap:,.0f} m2" if overlap else "")
           + (f" letter={c.code_letter}" if c.code_letter else "")]
    out.append("  evidence: " + ", ".join(f"{k}={_fmt(v)}" for k, v in c.evidence.items()))
    src = {r.id: r for r in cl.sources}
    seen: list[str] = []
    for sid, g in ev.pavement_polys:
        a = g.intersection(poly).area
        if a < 1.0:
            continue
        r = src.get(sid)
        seen.append(sid)
        if r is None:
            out.append(f"  source {sid}: overlap {a:,.0f} m2")
            continue
        out.append(f"  source {sid} [{r.cls}]: overlap {a:,.0f}/{r.area_m2:,.0f} m2, "
                   f"width {r.width_m:.1f} m, road {r.road_m:.0f} m (osm {r.osm_road_m:.0f}, "
                   f"through {r.through_m:.0f}, pieces {r.road_pieces}, aisle {r.aisle_m:.0f}), "
                   f"taxi {r.taxi_m:.0f} m, startups {r.startups}, parking cover "
                   f"{r.parking_cover:.0%}, apron cover {r.apron_cover:.0%}"
                   + (f", desc {r.description!r}" if r.description else "")
                   + (f", TAXI NAME {r.taxi_name!r}"
                      + (f" designator {r.taxi_designator}" if r.taxi_designator else "")
                      + " (04z-1)" if r.taxi_name else ""))
        out.append(f"      -> {r.reason}")
    probe = poly.buffer(1.0)
    taxi = [f"taxi{ch.id}" + ("(network)" if ch.runway_network else "")
            + (f"/{','.join(sorted(ch.names))}" if ch.names else "")
            for ch in ev.taxi_chains if ch.line.intersects(probe)]
    roads = [f"route{ch.id}" for ch in ev.truck_chains if ch.line.intersects(probe)]
    osm = [f"osm{ch.id}" + ("(aisle)" if ch.aisle else "")
           for ch in ev.road_chains if ch.line.intersects(probe)]
    starts = [s.name for s in airport.startups if poly.contains(Point(s.xy))]
    out.append(f"  centrelines: taxi {taxi or '-'}; 1206 {roads or '-'}; OSM roads {osm or '-'}; "
               f"startups inside {starts or '-'}")
    return out


def explain_polygon(poly: Polygon, cl: Classification, ev: Evidence, airport: Airport,
                    min_overlap_m2: float = 25.0) -> list[str]:
    """Every cell overlapping ``poly`` by at least ``min_overlap_m2``."""
    out: list[str] = []
    for c in cl.cells:
        cp = Polygon(c.ring, c.holes)
        if not cp.intersects(poly):
            continue
        a = cp.intersection(poly).area
        if a >= min_overlap_m2:
            out += _cell_lines(c, cp, a, cl, ev, airport)
    return out or ["no cell overlaps the shape by >= %g m2" % min_overlap_m2]


def explain_at(xy: tuple[float, float], cl: Classification, ev: Evidence,
               airport: Airport) -> list[str]:
    """The cell containing ``xy`` (or the nearest one)."""
    p = Point(xy)
    best: tuple[float, Cell, Polygon] | None = None
    for c in cl.cells:
        cp = Polygon(c.ring, c.holes)
        d = cp.distance(p)
        if best is None or d < best[0]:
            best = (d, c, cp)
        if d == 0.0:
            break
    if best is None:
        return ["no cells"]
    d, c, cp = best
    head = [] if d == 0.0 else [f"(no cell contains the point; nearest is {d:.1f} m away)"]
    return head + _cell_lines(c, cp, None, cl, ev, airport)


def render(lines: _t.Iterable[str]) -> str:
    return "\n".join(lines)


# ── the CLI ──────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    """The CLI's parser (a factory so the twins parse without running).
    Options and the positional ICAO may come in either order."""
    e = argparse.ArgumentParser(
        prog="v2_explain",
        description="the classification verdict at a shapeID or coordinate")
    e.add_argument("icao")
    e.add_argument("--shape", type=int, help="shapeID of a way in the shipped patch")
    e.add_argument("--at", help="LAT,LON (WGS84)")
    e.add_argument("--patch", help="the patch to read --shape from (default: "
                   "<root>/Patches/<block>/<tile>/<ICAO>_auto.patch.osm for the "
                   "first of --data-root, the engine's chosen data root "
                   "(ORTHO4XP_DATA_ROOT), the default data root and the engine "
                   "tree that holds it; the resolved path and its mtime are "
                   "printed on every run)")
    e.add_argument("--sources", action="store_true",
                   help="ALSO list every source polygon's record (id, class, the "
                        "reason, width, road/taxi metres, OSM apron and parking "
                        "cover, startups) — the airport-wide census behind one "
                        "shape's verdict, so a rule change's collateral is read "
                        "in ONE classification instead of one run per shape")
    e.add_argument("--roles", action="store_true",
                   help="ALSO print the ROLE CENSUS of the whole airport — cells "
                        "and area per role, then every RE-KINDED cell (a runway "
                        "shoulder, an apron-cover corridor refusal, a §27 flip, a "
                        "taxi name, the open default, a demotion) named with its "
                        "centroid and the evidence its rule read: the dry "
                        "before/after read a ROLE-LAW change is accepted on")
    e.add_argument("--xplane-root")
    e.add_argument("--cifp-dir")
    e.add_argument("--data-root")
    add_dem_frame_args(e)
    return e


def _patch_rel(icao: str, blat: int, blon: int) -> str:
    """``Patches/<block>/<tile>/<ICAO>_auto.patch.osm`` — the tile build's
    own spelling (``O4_File_Names.patch_dir`` / ``long_latlon``)."""
    from O4_File_Names import long_latlon
    return os.path.join("Patches", long_latlon(blat, blon), f"{icao.upper()}_auto.patch.osm")


def default_patch_candidates(icao: str, blat: int, blon: int,
                             data_root: str | None = None
                             ) -> list[tuple[str, str]]:
    """``[(source, path), …]`` in precedence order — the roots a tile
    build's product can land under, most specific instruction first
    (the accessor's own rule: an explicitly chosen root beats the
    implicit one).  An explicit ``--data-root`` is the ONLY candidate."""
    import O4_File_Names as FNAMES
    rel = _patch_rel(icao.upper(), blat, blon)
    engine = os.path.realpath(str(ENGINE_DIR))
    if data_root:
        return [("--data-root", os.path.join(os.path.abspath(data_root), rel))]
    out: list[tuple[str, str]] = []
    cur = os.path.realpath(FNAMES.current_data_root())
    if cur != engine:
        out.append(("the engine's data root (O4_File_Names.current_data_root: ORTHO4XP_DATA_ROOT)",
                    os.path.join(cur, rel)))
    default = os.path.realpath(FNAMES.default_data_root())
    if default not in (cur, engine):
        out.append(("the default data root (O4_File_Names.default_data_root)",
                    os.path.join(default, rel)))
    out.append(("the engine tree", os.path.join(engine, rel)))
    return out


def resolve_default_patch(icao: str, blat: int, blon: int,
                          data_root: str | None = None
                          ) -> tuple[str, str, bool]:
    """``(path, source, exists)``: the first candidate that HOLDS the
    patch; when none does, the first candidate with ``exists=False``."""
    cands = default_patch_candidates(icao, blat, blon, data_root)
    for source, path in cands:
        if os.path.isfile(path):
            return path, source, True
    return cands[0][1], cands[0][0], False


def patch_provenance_line(path: str, source: str) -> str:
    """One line naming the patch a shapeID is read from and how old it is."""
    import datetime as _dt
    if not os.path.isfile(path):
        return f"explain: patch {path} (from {source}) — DOES NOT EXIST"
    mtime = os.path.getmtime(path)
    when = _dt.datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S")
    age_h = (_dt.datetime.now().timestamp() - mtime) / 3600.0
    age = f"{age_h * 60:.0f} min" if age_h < 1 else (
        f"{age_h:.1f} h" if age_h < 48 else f"{age_h / 24:.1f} days")
    return f"explain: patch {path} (from {source}; modified {when}, {age} ago)"


def main(argv: list[str] | None = None) -> int:
    """Classify once (read-only, degraded DEM accepted — the verdict does
    not read elevations) and print the verdict."""
    from auto_patch_v2.airport.load import load_with_report
    from auto_patch_v2.classify import classify, load_rules
    from auto_patch_v2.classify.evidence import build_evidence
    from auto_patch_v2.law import Law
    args = build_parser().parse_args(argv)
    os.chdir(ENGINE_DIR)   # the core's resource/data contract
    if args.shape is not None and args.at is not None:
        print("explain: at most one of --shape N / --at LAT,LON")
        return 2
    if args.shape is None and args.at is None and not (args.sources or args.roles):
        print("explain: one of --shape N / --at LAT,LON / --sources / --roles")
        return 2
    icao = args.icao.upper()
    inputs = default_inputs(args.xplane_root, args.cifp_dir, args.data_root,
                            60.0, args.dem_frame, True)
    law = Law.for_airport(icao)
    airport, load_rep = load_with_report(icao, inputs, law)
    rules = load_rules()
    cl = classify(airport, law, rules)
    ev = build_evidence(airport, rules, law.tables.structures.building_pad.min_area_m2,
                        law)
    print(f"[{icao}] {len(cl.cells)} cells; sources: "
          + ", ".join(f"{k} {v}" for k, v in sorted(
              {c: sum(1 for r in cl.sources if r.cls == c) for c in ("strip", "lot", "open")}.items())))
    print(f"[{icao}] OSM relations (spec 25): {load_rep.osm_relations}")
    # THE PATCH THE SHAPE IDS BELONG TO — resolved and named on EVERY run
    # (RULINGS 2026-09-13cs chip), whether or not --shape reads it.
    import math
    lat0, lon0 = airport.frame.origin
    blat, blon = int(math.floor(lat0)), int(math.floor(lon0))
    if args.patch is not None:
        patch, patch_src = str(args.patch), "--patch"
    else:
        patch, patch_src, _exists = resolve_default_patch(
            icao, blat, blon, args.data_root)
    print(patch_provenance_line(patch, patch_src))
    if args.sources:
        print(f"{'source':<12} {'cls':<5} {'area_m2':>9} {'width':>6} {'road':>7} "
              f"{'osm':>7} {'taxi':>6} {'strt':>4} {'apron%':>6} {'park%':>6}  "
              f"description / reason")
        for r in sorted(cl.sources, key=lambda s: (s.cls, -s.area_m2)):
            print(f"{r.id:<12} {r.cls:<5} {r.area_m2:>9,.0f} {r.width_m:>6.1f} "
                  f"{r.road_m:>7.0f} {r.osm_road_m:>7.0f} {r.taxi_m:>6.0f} "
                  f"{r.startups:>4d} {r.apron_cover:>6.0%} {r.parking_cover:>6.0%}  "
                  f"{r.description!r} -> {r.reason}")
    if args.roles:
        print(render(role_census(cl, airport)))
    if args.at is not None:
        lat, lon = (float(v) for v in args.at.split(","))
        to_xy, _ = airport.frame.transformers()
        print(render(explain_at(to_xy(lon, lat), cl, ev, airport)))
        return 0
    if args.shape is None:
        return 0
    if not os.path.isfile(patch):
        print(f"explain: no patch to read shapeID={args.shape} from — none of "
              + "; ".join(f"{p} ({s})" for s, p in
                          default_patch_candidates(icao, blat, blon, args.data_root))
              + " exists (build the tile, or name one with --patch)")
        return 1
    found = shape_polygon(patch, args.shape, airport)
    if found is None:
        print(f"explain: no way with shapeID={args.shape} and a role in {patch}")
        return 1
    poly, tags = found
    print(f"shape {args.shape} in {patch}: shipped role={tags.get('role')} "
          f"class={tags.get('class', '-')} ref={tags.get('ref')} area={poly.area:,.0f} m2")
    print(render(explain_polygon(poly, cl, ev, airport)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
