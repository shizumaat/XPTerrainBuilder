#!/usr/bin/env python3
"""THE RIDER CENSUS (jetway-strip spec ``docs/specs/jetway-strip-spec.md``
§4 / §5 bar 4; issue #31) — what the object stage makes of every RIDER,
read from a build's own products and NOTHING ELSE.

    venv/bin/python tools/jetway_rider_census.py --graded G.json
        (--dsf-dump TEXT | --pack PACK_ROOT --tile LAT LON)
        [--rebake PLAN.json] [--names jetway] [--strip]
        [--rows-near LAT,LON[,R]] [--json OUT.json] [--src BASE/src]

A RIDER (§1 (1)) is a placement the plan holds no geometry for (``.agp``,
``lib/``, a partition-skipped resource) standing within its own reach of a
cluster pad's outline.  The DESIGN side names the population (the graded
surface's ``provenance.jetway_strips[*].riders``); the WRITE side seats
each one (``airport/riders.riders_for_dump``: on ground where the terrain
at its anchor is its unit's datum, ``OBJECT_MSL`` only on a clamped gate,
never for an ``.agp``).  This tool calls THAT function — the one the
engine's ``placement_write.build_plan`` calls — over:

* the build's ``<ICAO>.graded.json`` (the strips, the pads, and the design
  surface as the continuous field a drape reads — the SAME sampler
  ``tools/obj8_split_report.py`` builds, imported, never copied);
* the pack's PRISTINE DSF text dump (``--dsf-dump``, or resolved READ-ONLY
  from the mod cache by ``--pack``/``--tile`` through the engine's own
  ``pristine_dsf_path`` + content-keyed cache name; a missing dump is
  REFUSED, never generated).

It prints, numbers first:

1. the §4 (2) census (riders / in a strip / on ground / MSL written / no
   host / on datum) — ``riders_for_dump`` + ``rider_census``, the counts
   the plan carries;
2. per strip (``--strip``): pad, level, gated (level ``None``), clamps and
   worst clamp, riders by ``seat_why``, the worst |terrain − datum|;
3. the MEASUREMENT population (``--names``, default ``jetway``: a
   substring of the resource path — names pick the population MEASURED,
   never the one seated, spec §1): per placement, whether the design side
   hosted it, its pad, anchor gap, ``seat_why``, the terrain at its anchor
   against the pad datum (the pad ring's median, ``riders_for_dump``'s
   datum) and against the pad EDGE nearest it; an unhosted one reads
   ``no_host`` with its nearest pad and distance;
4. ``--rows-near``: every rider within R m (default 60) of a site.

The join: a strip's rider is ``[lat, lon, path, reach]`` at 9 dp; the
write side joins it to the dump at 7 dp.  A published rider no dump row
joined is counted (``unjoined``) — a rider lost between the two halves.

Promoted from the jetway-strip lanes' scratchpad measurement on its
second use (lane ``ridercensus``, issue #31).  Writes nothing; runs under
the shared-repo write guard like every replay entry.
Twin: ``tests/auto_patch_v2/test_v2ridercensus.py``.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import typing as _t

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "src"))
sys.path.insert(0, os.path.join(HERE, "harness"))
sys.path.insert(0, HERE)


def _ll_dist_m(lat0: float, lon0: float, lat1: float, lon1: float) -> float:
    ky = 111_320.0
    kx = ky * math.cos(math.radians(lat0))
    return math.hypot((lon1 - lon0) * kx, (lat1 - lat0) * ky)


def resolve_dump(pack_root: str, lat: int, lon: int) -> str:
    """The PRISTINE dump's cache path, read-only: the engine's own
    resolver chain (``pristine_dsf_path`` → the content-keyed name in the
    pack's mod cache).  Refuses when the dump is absent — generating one
    is a write this census is not authorised to make."""
    from auto_patch import dsf_reader as R
    from auto_patch_v2.airport import dsf as D
    from auto_patch_v2.airport.dsf_write import pristine_dsf_path
    import O4_File_Names as F
    dsf = D.dsf_path_in_pack(pack_root, lat, lon)
    src = pristine_dsf_path(dsf)
    cache = D.mod_cache_dir(F.airport_mod_cache_root(),
                            os.path.basename(os.path.normpath(pack_root)))
    path = R._default_pack_text_cache_path(cache, src)
    if not os.path.isfile(path):
        raise SystemExit(f"REFUSING: no cached text dump of {src} at {path}; "
                         f"a build (or --dsf-dump) supplies it — this census "
                         f"never generates one")
    return path


def census(doc: _t.Mapping[str, _t.Any], dump: _t.Any, surface: _t.Callable,
           *, tol_m: float, names: str = "jetway",
           authored_ground: float | None = None,
           gate_m: float | None = None) -> dict[str, _t.Any]:
    """The whole report as a dict (the twin's entry): ``counts`` (§4 (2)),
    ``strips``, ``population`` (the ``names`` measurement rows),
    ``riders`` (every seat record) and ``unjoined``."""
    from auto_patch_v2.airport import riders as RD
    from auto_patch_v2.airport.placement_read import pads_rims_from_graded_doc
    strips = list((doc.get("provenance") or {}).get("jetway_strips") or ())
    pads, _rims = pads_rims_from_graded_doc(doc)
    import inspect
    kw: dict[str, _t.Any] = {"tol_m": tol_m, "authored_ground": authored_ground}
    # SIG-DIFF (the v2_rebake_replay discipline): a --src that predates
    # the gate radius is still read by the same instrument
    if "gate_m" in inspect.signature(RD.riders_for_dump).parameters:
        kw["gate_m"] = gate_m
    riders = RD.riders_for_dump(dump, strips, pads, surface, frozenset(), **kw)
    counts = RD.rider_census(riders)
    rows = list(getattr(dump, "placements", ()) or ())
    by_idx = {r.index: r for r in riders}
    # every face of a ref as ONE pad (RULINGS 2026-09-17t, fix C) — the
    # fold the write side and the unit seat read the datum through
    from auto_patch_v2.airport.anchor_rule import fold_pad_ref
    pad_by_ref: dict[str, _t.Any] = {}
    for p in pads:
        if p.ref not in pad_by_ref:
            pad_by_ref[p.ref] = fold_pad_ref(pads, p.ref) or p

    def _datum(ref: str) -> float | None:
        p = pad_by_ref.get(ref)
        if p is None or not p.z:
            return None
        zs = sorted(float(z) for z in p.z)
        return zs[len(zs) // 2]

    def _edge_z(ref: str, lat: float, lon: float) -> tuple[float | None, float]:
        """The pad ring vertex nearest the anchor: its z and distance."""
        p = pad_by_ref.get(ref)
        if p is None or not p.z:
            return None, math.inf
        best = (None, math.inf)
        rings = tuple(getattr(p, "rings", ()) or ()) or (p.ring,)
        for (a, b), z in zip([v for rg in rings for v in rg], p.z):
            d = _ll_dist_m(lat, lon, a, b)
            if d < best[1]:
                best = (float(z), d)
        return best

    # published riders the write side never joined (7-dp key + path)
    keys = {(round(float(p.lat), 7), round(float(p.lon), 7), p.def_path)
            for p in rows}
    unjoined = []
    for s in strips:
        for r in s.get("riders", ()) or ():
            k = (round(float(r[0]), 7), round(float(r[1]), 7), str(r[2]))
            if k not in keys:
                unjoined.append({"strip": s.get("id"), "lat": r[0], "lon": r[1],
                                 "resource": r[2]})
    counts["riders_published"] = sum(len(s.get("riders") or ()) for s in strips)
    counts["riders_unjoined"] = len(unjoined)

    def _row(r: _t.Any) -> dict[str, _t.Any]:
        dat = _datum(r.host_pid)
        ez, ed = _edge_z(r.host_pid, r.lat, r.lon)
        tz = r.terrain_z
        return {"index": r.index, "resource": r.resource, "lat": r.lat,
                "lon": r.lon, "host": r.host_pid, "strip": r.strip_id,
                "gap_m": r.anchor_gap_m, "reach_m": r.reach_m,
                "seat_why": r.seat_why, "seat_z": r.seat_z, "terrain_z": tz,
                "datum": dat,
                "terrain_minus_datum": (None if tz is None or dat is None
                                        else round(tz - dat, 3)),
                "edge_z": ez, "edge_dist_m": (None if ez is None
                                              else round(ed, 2)),
                "terrain_minus_edge": (None if tz is None or ez is None
                                       else round(tz - ez, 3))}

    rider_rows = [_row(r) for r in riders]

    # per strip
    strip_rows = []
    for s in strips:
        mine = [x for x in rider_rows if x["strip"] == str(s.get("id", ""))]
        cl = s.get("clamps") or ()
        dev = [abs(x["terrain_minus_datum"]) for x in mine
               if x["terrain_minus_datum"] is not None]
        why: dict[str, int] = {}
        for x in mine:
            why[x["seat_why"]] = why.get(x["seat_why"], 0) + 1
        strip_rows.append({
            "id": s.get("id"), "pad_ref": s.get("pad_ref"),
            "level": s.get("level"), "gated": s.get("level") is None,
            "riders": len(s.get("riders") or ()), "seated": len(mine),
            "seat_why": why, "clamps": len(cl),
            "clamp_worst_m": max((float(c[3]) for c in cl), default=0.0),
            "worst_terrain_minus_datum": max(dev, default=None)})

    # the MEASUREMENT population, by name
    pop = []
    if names:
        needle = names.lower()
        for i, p in enumerate(rows):
            if needle not in p.def_path.lower():
                continue
            r = by_idx.get(i)
            if r is not None:
                pop.append(_row(r))
                continue
            near_ref, near_d = "", math.inf
            for pd in pads:
                if len(pd.ring) < 3:
                    continue
                d = min(_ll_dist_m(p.lat, p.lon, a, b) for a, b in pd.ring)
                if d < near_d:
                    near_ref, near_d = pd.ref, d
            z = surface(p.lat, p.lon)
            pop.append({"index": i, "resource": p.def_path, "lat": p.lat,
                        "lon": p.lon, "host": "", "strip": "",
                        "seat_why": "no_host", "nearest_pad": near_ref,
                        "nearest_pad_vertex_m": (None if near_d == math.inf
                                                 else round(near_d, 2)),
                        "terrain_z": None if z is None else round(float(z), 3)})
    pc = {"population": len(pop),
          "hosted": sum(1 for x in pop if x["seat_why"] != "no_host"),
          "no_host": sum(1 for x in pop if x["seat_why"] == "no_host"),
          "on_ground": sum(1 for x in pop if x["seat_why"] == "on_ground"),
          "msl_written": sum(1 for x in pop if x["seat_why"] == "msl_written"),
          "agp_msl_written": sum(1 for x in pop if x["seat_why"] == "msl_written"
                                 and x["resource"].lower().endswith(".agp")),
          "on_datum_0p05": sum(1 for x in pop
                               if x.get("terrain_minus_datum") is not None
                               and abs(x["terrain_minus_datum"]) <= 0.05)}
    counts["riders_agp_msl_written"] = sum(
        1 for x in rider_rows if x["seat_why"] == "msl_written"
        and x["resource"].lower().endswith(".agp"))
    return {"counts": counts, "strips": strip_rows, "population": pop,
            "population_counts": pc, "riders": rider_rows,
            "unjoined": unjoined}


def _fmt(v: _t.Any, spec: str = "+.2f") -> str:
    return "—" if v is None else format(v, spec)


def print_report(rep: _t.Mapping[str, _t.Any], *, names: str, strip: bool,
                 near: tuple[float, float, float] | None) -> None:
    c = rep["counts"]
    print(f"RIDER CENSUS (§4 (2)): riders {c['riders']} (published "
          f"{c['riders_published']}, unjoined {c['riders_unjoined']}); in a "
          f"strip {c['riders_in_a_strip']}; on ground {c['riders_on_ground']}; "
          f"MSL written {c['riders_msl_written']} (.agp {c['riders_agp_msl_written']}"
          f", bar 0); no host {c['riders_no_host']}; on datum ±0.05 "
          f"{c['riders_on_datum']}")
    if names:
        p = rep["population_counts"]
        print(f"MEASUREMENT population '{names}': {p['population']} placement(s): "
              f"hosted {p['hosted']}, NO HOST {p['no_host']}; on ground "
              f"{p['on_ground']}, MSL written {p['msl_written']} (.agp "
              f"{p['agp_msl_written']}); terrain on the pad datum ±0.05 m "
              f"{p['on_datum_0p05']}")
    if strip:
        print("\nper strip: pad  level  riders/seated  seat_why  clamps (worst)  "
              "worst |terrain − datum|")
        for s in rep["strips"]:
            print(f"  {s['pad_ref']:<12} {_fmt(s['level'], '.2f'):>8}"
                  f"{'  GATED' if s['gated'] else ''}  {s['riders']}/{s['seated']}"
                  f"  {s['seat_why']}  {s['clamps']} ({s['clamp_worst_m']:.2f} m)"
                  f"  {_fmt(s['worst_terrain_minus_datum'], '.2f')}")
    if names:
        print(f"\n'{names}' rows: resource  host  gap  seat_why  terrain  "
              f"terrain−datum  terrain−edge (edge dist)")
        for x in sorted(rep["population"], key=lambda x: (x["host"], x["lat"])):
            if x["seat_why"] == "no_host":
                print(f"  {x['resource'].split('/')[-1][:32]:<32} NO HOST  "
                      f"nearest pad {x['nearest_pad']} vertex "
                      f"{_fmt(x['nearest_pad_vertex_m'], '.1f')} m  "
                      f"{x['lat']:.7f},{x['lon']:.7f}")
                continue
            print(f"  {x['resource'].split('/')[-1][:32]:<32} {x['host']:<11}"
                  f" {x['gap_m']:5.2f} {x['seat_why']:<11}"
                  f" {_fmt(x['terrain_z'], '.2f'):>7}"
                  f" {_fmt(x['terrain_minus_datum']):>7}"
                  f" {_fmt(x['terrain_minus_edge']):>7}"
                  f" ({_fmt(x['edge_dist_m'], '.1f')} m)")
    if near is not None:
        la, lo, R = near
        rows = [(round(_ll_dist_m(la, lo, x["lat"], x["lon"]), 1), x)
                for x in rep["riders"]]
        rows = sorted((d, x) for d, x in rows if d <= R)
        print(f"\nriders within {R:g} m of {la},{lo}: {len(rows)} — on ground "
              f"{sum(1 for _d, x in rows if x['seat_why'] == 'on_ground')}, "
              f"on their pad datum ±0.05 "
              f"{sum(1 for _d, x in rows if x['terrain_minus_datum'] is not None and abs(x['terrain_minus_datum']) <= 0.05)}")
        for d, x in rows:
            print(f"  {d:6.1f} m  {x['resource'].split('/')[-1][:34]:<34} "
                  f"{x['host']:<11} {x['seat_why']:<11} terrain "
                  f"{_fmt(x['terrain_z'], '.2f')} datum {_fmt(x['datum'], '.2f')}"
                  f" (Δ {_fmt(x['terrain_minus_datum'])})")


def _main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--graded", required=True, help="<ICAO>.graded.json")
    ap.add_argument("--dsf-dump", default="", help="the PRISTINE DSF text dump")
    ap.add_argument("--pack", default="", help="pack root (resolves the dump "
                    "read-only from the mod cache with --tile)")
    ap.add_argument("--tile", nargs=2, type=int, metavar=("LAT", "LON"))
    ap.add_argument("--rebake", default="", help="<ICAO>.rebake.json — its "
                    "flat z0 is the authored ground (optional)")
    ap.add_argument("--names", default="jetway", help="measurement population "
                    "substring ('' for none)")
    ap.add_argument("--strip", action="store_true", help="per-strip table")
    ap.add_argument("--rows-near", default="", metavar="LAT,LON[,R]")
    ap.add_argument("--json", default="", help="write the whole report here")
    ap.add_argument("--src", default="", help="read the WRITE side "
                    "(riders_for_dump) from another checkout's src — a base "
                    "arm cut with `git archive <sha> src`, never a live tree")
    a = ap.parse_args()
    if a.src:
        sys.path.insert(0, os.path.abspath(a.src))
        for m in [m for m in sys.modules if m.startswith("auto_patch")]:
            del sys.modules[m]

    from auto_patch_v2.airport import dsf as D
    from auto_patch_v2.law import Law
    from obj8_split_report import surface_from_graded
    if a.dsf_dump:
        dump_path = a.dsf_dump
    elif a.pack and a.tile:
        dump_path = resolve_dump(a.pack, a.tile[0], a.tile[1])
    else:
        ap.error("--dsf-dump or --pack with --tile is required")
    law = Law.load()
    with open(a.graded, encoding="utf-8") as fh:
        doc = json.loads(fh.read())
    sampler, _pads, _rims = surface_from_graded(
        a.graded, law.tables.structures.placement.split_tol_m)
    ground = None
    if a.rebake:
        with open(a.rebake, encoding="utf-8") as fh:
            flat = (json.loads(fh.read()).get("flat") or {})
        ground = flat.get("z0_m") if isinstance(flat, dict) else None
    rep = census(doc, D.read_dump(dump_path), sampler,
                 tol_m=float(law.tables.emit.design.hard_tol_m),
                 names=a.names, authored_ground=ground,
                 gate_m=float(law.tables.emit.design.jetway_strip_m))
    near = None
    if a.rows_near:
        v = [float(x) for x in a.rows_near.split(",")]
        near = (v[0], v[1], v[2] if len(v) > 2 else 60.0)
    import auto_patch_v2.airport.riders as _RD
    print(f"graded {a.graded}\ndump   {dump_path}\nwrite side {_RD.__file__}")
    print_report(rep, names=a.names, strip=a.strip, near=near)
    if a.json:
        with open(a.json, "w", encoding="utf-8") as fh:
            json.dump(rep, fh, indent=1)
    return 0


def main() -> int:
    """The entry, under the SHARED-REPO WRITE GUARD (a census writes
    nothing; the guard refuses at the call and the snapshot backstops)."""
    from shared_repo_guard import (SharedRepoWriteGuard,  # noqa: E402
                                   report_unauthorised_writes,
                                   require_no_unauthorised_writes,
                                   shared_repo_snapshot, snapshot_diff)
    before = shared_repo_snapshot()
    guard = SharedRepoWriteGuard(set(), os.getcwd())
    try:
        with guard:
            rc = _main()
    finally:
        changes = snapshot_diff(before, shared_repo_snapshot())
        offenders = report_unauthorised_writes(changes, set(), None)
    require_no_unauthorised_writes(offenders, entry="jetway_rider_census")
    return rc


if __name__ == "__main__":
    sys.exit(main())
