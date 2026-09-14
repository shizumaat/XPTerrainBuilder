"""``venv/bin/python -m auto_patch_v2 build ICAO --out DIR`` — the v2
build: load → classify → planar → constraints → solve → emit → verify,
counts and per-stage wall time on stdout, ``<ICAO>.report.json`` in DIR.
Inputs default to the engine tree's mounts and its ``Ortho4XP.cfg``
install paths exactly as ``auto_patch_v2.planar`` resolves them (M1); no
environment reads.

``python -m auto_patch_v2 explain ICAO --shape N [--patch P] | --at
LAT,LON`` (owner 2026-09-04j; ``--shape`` before or after the ICAO, argparse
accepts either): the classification verdict at a shipped patch's
``shapeID`` or at a coordinate — role, the evidence record, the source
polygons under it with their own records, the centrelines that touch it
(``classify/explain.py``).

THE DEFAULT PATCH (RULINGS 2026-09-13cs chip): without ``--patch`` the
shapeIDs are read from the patch the DATA-ROOT RESOLUTION lands a tile
build's product at — ``<root>/Patches/<block>/<tile>/<ICAO>_auto.patch.osm``
with ``<root>`` the first of ``--data-root``, the engine's own data root
when one is chosen (``O4_File_Names.current_data_root``: the
``ORTHO4XP_DATA_ROOT`` the app hands every engine process), the default
data root (``O4_File_Names.default_data_root``, ``~/XPTerrainBuilderData``
— the shared corpus the app's products land in) and, last, the engine
tree — that HOLDS the patch.  Before 09-13 the engine tree was the only
default, and a lane's ``Patches/`` clone is days stale (the scout read
Sep 9 shapeIDs against a Sep 13 sim).  Every run prints the patch it
resolved, where it came from and its mtime, so a shapeID is never read
off an unnamed product.
"""
from __future__ import annotations

import argparse
import os
import sys

from ..planar.__main__ import ENGINE_DIR, add_dem_frame_args, default_inputs
from ..law import Law
from ..solve import Options
from .build import Config, build


def build_parser() -> argparse.ArgumentParser:
    """The CLI's parser (a factory so the twins parse without running).
    Options and the positional ICAO may come in either order — ``explain
    --shape N ICAO`` and ``explain ICAO --shape N`` are the same call."""
    ap = argparse.ArgumentParser(prog="auto_patch_v2")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build", help="build one airport's v2 patch")
    b.add_argument("icao")
    b.add_argument("--out", required=True)
    b.add_argument("--xplane-root")
    b.add_argument("--cifp-dir")
    b.add_argument("--data-root")
    b.add_argument("--feather-m", type=float, default=60.0)
    add_dem_frame_args(b)
    b.add_argument("--law-dir", help="an ALTERNATIVE law-table directory (a "
                   "labelled measurement arm; the shipped tables are law/)")
    b.add_argument("--no-verify", action="store_true")
    b.add_argument("--no-iis", action="store_true")
    b.add_argument("--verbose", action="store_true")
    e = sub.add_parser("explain", help="the classification verdict at a shapeID or coordinate")
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
    e.add_argument("--xplane-root")
    e.add_argument("--cifp-dir")
    e.add_argument("--data-root")
    add_dem_frame_args(e)
    y = sub.add_parser("why", help="WHAT BINDS THIS SHAPE: the active rows, the chain "
                       "trace to the nearest hard pin and the relax-one-family rises")
    y.add_argument("icao")
    y.add_argument("--shape", type=int, help="face id (= shapeID of the v2 patch)")
    y.add_argument("--at", help="LAT,LON (WGS84)")
    y.add_argument("--patch", help="match --shape's ring in THIS patch to a face instead")
    y.add_argument("--relax", help="comma-separated families to relax (default: the "
                   "binding families by Σ|dual|, at most --max-relax)")
    y.add_argument("--max-relax", type=int, default=5)
    y.add_argument("--drop", help="comma-separated families dropped BEFORE the solve "
                   "(a labelled arm: 'with X relaxed, what binds next?')")
    y.add_argument("--top", type=int, default=3, help="binding rows shown per vertex")
    y.add_argument("--kml", help="ALSO write the chain trace as a KML here (one line per "
                   "binding row, coloured by family — the owner's reading surface)")
    y.add_argument("--xplane-root")
    y.add_argument("--cifp-dir")
    y.add_argument("--data-root")
    y.add_argument("--law-dir", help="an ALTERNATIVE law-table directory (a labelled arm)")
    add_dem_frame_args(y)
    return ap


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
    ap = build_parser()
    args = ap.parse_args(argv)
    os.chdir(ENGINE_DIR)   # the core's resource/data contract (production DEM frame)
    if args.cmd == "explain":
        return explain_main(args)
    if args.cmd == "why":
        return why_main(args)
    inputs = default_inputs(args.xplane_root, args.cifp_dir, args.data_root,
                            args.feather_m, args.dem_frame, args.allow_degraded_dem)
    cfg = Config(options=Options(diagnose_iis=not args.no_iis,
                                 verbose=args.verbose),
                 verify=not args.no_verify, feather_m=args.feather_m)
    law = Law.for_airport(args.icao.upper(), law_dir=args.law_dir) if args.law_dir else None
    with shared_repo_guard() as guard:
        res = build(args.icao.upper(), inputs, args.out, cfg, law)
    blocked = list(getattr(guard, "blocked", ()))
    if blocked:
        print(f"[{args.icao.upper()}] REFUSED: {len(blocked)} write(s) into the "
              f"shared data repo were blocked during the build: {blocked[:5]}")
        return 2
    return 0 if res.solution.status.value in ("optimal", "feasible") else 1


def explain_main(args) -> int:
    """``explain``: classify once (read-only, degraded DEM accepted — the
    verdict does not read elevations) and print the verdict."""
    from ..airport.load import load_with_report
    from ..classify import classify, load_rules
    from ..classify.evidence import build_evidence
    from ..classify.explain import explain_at, explain_polygon, render, shape_polygon
    if args.shape is not None and args.at is not None:
        print("explain: at most one of --shape N / --at LAT,LON")
        return 2
    if args.shape is None and args.at is None and not args.sources:
        print("explain: one of --shape N / --at LAT,LON / --sources")
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


def why_main(args) -> int:
    """``why``: the pipeline's LP rebuilt (no emit, ``pipeline/why.py``)
    and one face's binding story (``solve/why.py``)."""
    from .why import prepare, report, resolve_faces
    if (args.shape is None) == (args.at is None):
        print("why: exactly one of --shape N / --at LAT,LON")
        return 2
    icao = args.icao.upper()
    inputs = default_inputs(args.xplane_root, args.cifp_dir, args.data_root,
                            60.0, args.dem_frame, args.allow_degraded_dem)
    law = Law.for_airport(icao, law_dir=args.law_dir) if args.law_dir else None
    drop = args.drop.split(",") if args.drop else ()
    with shared_repo_guard():
        prep = prepare(icao, inputs, law, drop=drop)
    at = tuple(float(v) for v in args.at.split(",")) if args.at else None
    faces, how = resolve_faces(prep, args.shape, at, args.patch)
    print(f"[{icao}] why: {how}")
    if not faces:
        return 1
    relax = args.relax.split(",") if args.relax else None
    for fid in faces:
        print(report(prep, fid, top=args.top, relax=relax, max_relax=args.max_relax))
        if args.kml:
            from .why import chain_kml
            tr = chain_kml(prep, fid, args.kml)
            print(f"[{icao}] why: chain KML -> {args.kml} "
                  f"({0 if tr is None else len(tr.steps)} rows)")
    return 0


def shared_repo_guard():
    """THE shared-repo write guard (``tools/harness/shared_repo_guard.py``,
    the single implementation), armed in refuse mode around the build so
    the production DEM prelude can never write the corpus (RULINGS
    ``e9daef5``).  A tree without the harness (a packaged engine) runs
    unguarded — the guard is a lane instrument, and the pipeline reads no
    environment to find it."""
    harness = ENGINE_DIR / "tools" / "harness"
    if not (harness / "shared_repo_guard.py").is_file():
        import contextlib
        return contextlib.nullcontext()
    if str(harness) not in sys.path:
        sys.path.insert(0, str(harness))
    from shared_repo_guard import SharedRepoWriteGuard
    return SharedRepoWriteGuard(set(), str(ENGINE_DIR))


if __name__ == "__main__":
    sys.exit(main())
