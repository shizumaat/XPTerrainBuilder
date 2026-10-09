"""surfspec probe — WHAT THE SURFACE GATE ADMITS BEYOND THE NAME GATE, AND
WHAT THE GAP MINT WOULD MAKE OF IT.  Dry, off a registered capture; reads
the capture, the pack's cached DSF text dump and the ``.pol`` files; writes
nothing but ``--json``.

    venv/bin/python docs/briefs/surfspec/admit_probe.py ICAO=CAP.pkl [...]
        [--json OUT] [--site LAT,LON ...]

Per airport:
  * every ``.pol`` polygon of the dump, judged by MAIN's gate
    (``airport/dsf.pavement_gate``, this tree) and by the surface337 gate
    (ported verbatim from ``claude/surface337`` 3936fd94 below) — the
    SURFACE-ONLY set is what the branch admits and main does not;
  * that set clipped to the classify gate (boundary + 50 m), per def: n,
    m2, m2 on every pavement source, on apt.dat pavement, on runway /
    taxi-family / apron cells, on every standing cell, on existing gap
    sheets;
  * the gap mint (``classify/gap_mint.mint_gap_pieces``, the real one) run
    twice over the capture's own standing cells — with today's sheets
    (control) and with the SURFACE-only polygons added as sheets (arm) —
    pieces, m2, size distribution, apron-touching, unminted-airside;
  * the #333 population: ground that a NAME-admitted ``dsf:pol`` cell owns
    on top of apt.dat pavement, by role (page-over-apt.dat fusing);
  * ``--site``: the cell under each site.
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import pickle
import re
import sys
import time
import types
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3] / "Ortho4XP"
sys.path.insert(0, str(ROOT / "src"))

from shapely.geometry import Point, Polygon            # noqa: E402
from shapely.ops import unary_union                    # noqa: E402

SHARED_MOD_CACHE = "/Users/noah/XPTerrainBuilderData/Airport_mod_cache"
PIECES_OUT: str | None = None

# ── the surface337 gate, verbatim (3936fd94 airport/dsf.py) ─────────────
PAVEMENT_PREFIXES = ("lib/airport/pavement/", "lib/airport/ground/pavement/")
PAVEMENT_SKIP = ("/lines/", "/markings/", "/lights/", "/decals/", "dirsigns")
MATERIAL_TOKENS = ("asphalt", "concrete", "asphalte", "beton", "béton",
                   "hormigon", "hormigón", "asfalto", "cemento", "calcestruzzo",
                   "betão", "concreto")
SOFT_NAME_TOKENS = ("grass", "terrain", "dirt", "gravel", "soil", "mud", "snow")
DECORATIVE_TOKENS = ("paint", "line", "marking", "light", "decal", "sign",
                     "logo", "grunge", "stain", "skid", "crack_line")
ABBREV_TOKEN_RE = re.compile(r"(?<![a-z])conc(?![a-z])")
HARD_SURFACES = ("asphalt", "concrete")
PAINT_LAYER_GROUPS = ("markings",)
PAINT = "paint"


def pol_declaration(physical_path):
    if not physical_path:
        return (None, None)
    surface = layer = None
    try:
        with open(physical_path, "r", errors="ignore") as fh:
            for line in fh:
                toks = line.split()
                if len(toks) < 2:
                    continue
                kw = toks[0].upper()
                if kw == "SURFACE" and surface is None:
                    surface = toks[1].lower()
                elif kw == "LAYER_GROUP":
                    if toks[1].lower() in PAINT_LAYER_GROUPS:
                        layer = PAINT
                    elif layer is None:
                        layer = toks[1].lower()
    except OSError:
        return (None, None)
    return (surface, layer)


def branch_is_pavement(path, decl):
    p = path.lower()
    if p.startswith(PAVEMENT_PREFIXES):
        return not any(s in p for s in PAVEMENT_SKIP)
    if not p.endswith(".pol") or any(s in p for s in PAVEMENT_SKIP + SOFT_NAME_TOKENS):
        return False
    decorative = any(s in p for s in DECORATIVE_TOKENS)
    if not decorative and any(t in p for t in MATERIAL_TOKENS):
        return True
    if decl is not None:
        surface, layer = decl
        if layer == PAINT:
            return False
        if surface is not None:
            return surface in HARD_SURFACES and (layer is not None or not decorative)
    return not decorative and bool(ABBREV_TOKEN_RE.search(p))


# ── helpers ───────────────────────────────────────────────────────────────
def _poly(outer, holes=()):
    try:
        p = Polygon(list(outer), [list(h) for h in holes if len(h) >= 3])
    except (ValueError, TypeError):
        return None
    if not p.is_valid:
        p = p.buffer(0)
    return None if p.is_empty else p


def _union(polys):
    ps = [p for p in polys if p is not None and not p.is_empty]
    return unary_union(ps) if ps else Polygon()


def _parts(g):
    if g.is_empty:
        return []
    if g.geom_type == "Polygon":
        return [g]
    return [q for q in getattr(g, "geoms", ()) if q.geom_type == "Polygon" and q.area > 0]


def _dump_path(a):
    """The shared mod cache's content-keyed dump of the pack's tile DSF."""
    from auto_patch_v2.airport import dsf as D
    for p in a.pack.dsf_paths:
        base = os.path.basename(p)                     # +60-136.dsf
        lat, lon = int(base[:3]), int(base[3:7])
        got = D.find_text_dump(SHARED_MOD_CACHE, a.pack.name, lat, lon,
                               dsf_path=p if os.path.isfile(p) else None)
        if got:
            return got
    return None


def _quant(vals):
    v = sorted(vals)
    if not v:
        return {}
    q = lambda f: v[min(len(v) - 1, int(f * len(v)))]       # noqa: E731
    return {"n": len(v), "min": round(v[0]), "p25": round(q(0.25)), "median": round(q(0.5)),
            "p75": round(q(0.75)), "max": round(v[-1]), "sum": round(sum(v))}


def probe(icao, pkl, sites):
    from auto_patch_v2.airport import dsf as D, obj8 as O
    from auto_patch_v2.classify import load_rules
    from auto_patch_v2.classify.gap_mint import mint_gap_pieces
    from auto_patch_v2.law import Law
    from auto_patch_v2.model.airport import Pavement

    t0 = time.perf_counter()
    with open(pkl, "rb") as fh:
        cap = pickle.load(fh)
    a, cl = cap["airport"], cap["cl"]
    inp = cap["inputs"]
    print(f"\n== {icao} {pkl}  (loaded {time.perf_counter() - t0:.0f} s; "
          f"pavements {len(a.pavements)}, gap_sheets {len(getattr(a, 'gap_sheets', ()) or ())}, "
          f"cells {len(cl.cells)})")
    to_xy, to_ll = a.frame.transformers()
    law = Law.for_airport(icao)
    rules = load_rules()
    root = os.path.dirname(os.path.dirname(a.pack.apt_dat_path))
    index = O.read_library_index(O.library_index_path(SHARED_MOD_CACHE, inp.xplane_root))
    resolve = lambda p: O.resolve_resource(p, root, index)          # noqa: E731
    main_gate = D.pavement_gate(resolve)
    dump_path = _dump_path(a)
    if dump_path is None:
        print("  NO DUMP in the shared cache for", a.pack.name, a.pack.dsf_paths)
        return {"icao": icao, "error": "no dump"}
    dump = D.read_dump(dump_path, lambda p: p.lower().endswith(".pol"))

    # the regions
    bnd = _union([_poly(b.outer) for b in a.boundaries])
    apt_pav = _union([_poly(p.outer, p.holes) for p in a.pavements if not p.id.startswith("dsf:")])
    all_pav = _union([_poly(p.outer, p.holes) for p in a.pavements])
    gate = bnd.buffer(float(rules.dsf_pavement.boundary_buffer_m)) if not bnd.is_empty \
        else all_pav.buffer(60.0)
    sheets_today = [_poly(g.outer, g.holes) for g in (getattr(a, "gap_sheets", ()) or ())]
    sheet_u = _union(sheets_today)
    prec = law.tables.precedence
    rw_roles = set(prec.runway_family.members)
    tx_roles = set(prec.taxi_family.members)
    std = [(c, _poly(c.ring, c.holes)) for c in cl.cells if not str(c.ref).startswith("gap:")]
    std = [(c, q) for c, q in std if q is not None]
    rw_u = _union([q for c, q in std if c.role in rw_roles])
    tx_u = _union([q for c, q in std if c.role in tx_roles])
    ap_u = _union([q for c, q in std if c.role == "apron"])
    std_u = _union([q for c, q in std if c.role != "building"])
    pad_u = _union([q for c, q in std if c.role == "building"])

    # ── the gates over the dump ────────────────────────────────────
    decls = {}
    by_def = collections.defaultdict(lambda: {"n": 0, "m2": 0.0, "clipped_n": 0, "clipped_m2": 0.0,
                                              "on_all_pav": 0.0, "on_apt_pav": 0.0, "on_runway": 0.0,
                                              "on_taxi": 0.0, "on_apron": 0.0, "on_standing": 0.0,
                                              "on_pads": 0.0, "on_sheets_today": 0.0, "free": 0.0})
    admitted_polys = []
    counts = collections.Counter()
    for pg in dump.polygons:
        d = pg.def_path
        if d not in decls:
            decls[d] = pol_declaration(resolve(d))
        m_adm = main_gate(d)[0]
        b_adm = branch_is_pavement(d, decls[d])
        cls = "name" if m_adm else ("surface_only" if b_adm else "refused")
        counts[cls] += 1
        if cls != "surface_only":
            continue
        rings = [[to_xy(lon, lat) for lon, lat in w] for w in pg.windings]
        poly = _poly(rings[0], rings[1:])
        if poly is None:
            continue
        r = by_def[d]
        r["n"] += 1
        r["m2"] += poly.area
        parts = _parts(poly.intersection(gate))
        if not parts:
            continue
        poly = max(parts, key=lambda g: g.area)
        if poly.area < float(rules.dsf_pavement.min_area_m2):
            continue
        r["clipped_n"] += 1
        r["clipped_m2"] += poly.area
        r["on_all_pav"] += poly.intersection(all_pav).area
        r["on_apt_pav"] += poly.intersection(apt_pav).area
        r["on_runway"] += poly.intersection(rw_u).area
        r["on_taxi"] += poly.intersection(tx_u).area
        r["on_apron"] += poly.intersection(ap_u).area
        r["on_standing"] += poly.intersection(std_u).area
        r["on_pads"] += poly.intersection(pad_u).area
        r["on_sheets_today"] += poly.intersection(sheet_u).area
        r["free"] += poly.difference(std_u).difference(pad_u).area
        admitted_polys.append((d, poly))
    print(f"  dump .pol polygons by gate: {dict(counts)}")
    # the refused defs that DECLARE a hard surface: why each stays out
    ref_hard = collections.Counter()
    for pg in dump.polygons:
        d = pg.def_path
        if main_gate(d)[0] or branch_is_pavement(d, decls[d]):
            continue
        if decls[d][0] in HARD_SURFACES:
            ref_hard[d] += 1
    for d, n in ref_hard.most_common():
        p = d.lower()
        why = ("paint layer" if decls[d][1] == PAINT else
               "soft name word" if any(s in p for s in SOFT_NAME_TOKENS) else
               "stock skip namespace" if any(s in p for s in PAVEMENT_SKIP) else
               "decorative name word, no layer" if any(s in p for s in DECORATIVE_TOKENS) else "?")
        print(f"  refused though {decls[d][0]}: {d[-60:]:60s} n={n:4d}  {why} ({decls[d][1]})")
    out_refused = {d: {"n": n, "surface": decls[d][0], "layer": decls[d][1]} for d, n in ref_hard.items()}
    print(f"  {'def':60s} {'n':>4s} {'m2':>9s} {'clip':>9s} {'allpav':>8s} {'aptpav':>8s} "
          f"{'rwy':>7s} {'taxi':>8s} {'apron':>8s} {'stand':>9s} {'pads':>7s} {'sheets':>8s} {'free':>9s}  SURFACE/LAYER")
    tot = collections.Counter()
    for d, r in sorted(by_def.items(), key=lambda kv: -kv[1]["clipped_m2"]):
        print(f"  {d[-60:]:60s} {r['n']:4d} {r['m2']:9.0f} {r['clipped_m2']:9.0f} {r['on_all_pav']:8.0f} "
              f"{r['on_apt_pav']:8.0f} {r['on_runway']:7.0f} {r['on_taxi']:8.0f} {r['on_apron']:8.0f} "
              f"{r['on_standing']:9.0f} {r['on_pads']:7.0f} {r['on_sheets_today']:8.0f} {r['free']:9.0f}  "
              f"{decls[d][0]}/{decls[d][1]}")
        for k, v in r.items():
            tot[k] += v
    print(f"  {'TOTAL':60s} {tot['n']:4d} {tot['m2']:9.0f} {tot['clipped_m2']:9.0f} {tot['on_all_pav']:8.0f} "
          f"{tot['on_apt_pav']:8.0f} {tot['on_runway']:7.0f} {tot['on_taxi']:8.0f} {tot['on_apron']:8.0f} "
          f"{tot['on_standing']:9.0f} {tot['on_pads']:7.0f} {tot['on_sheets_today']:8.0f} {tot['free']:9.0f}")
    out = {"icao": icao, "capture": str(pkl), "dump": dump_path, "gate_counts": dict(counts),
           "surface_only_by_def": {d: dict(r, surface=decls[d][0], layer=decls[d][1])
                                   for d, r in by_def.items()},
           "surface_only_total": dict(tot), "sheets_today_m2": round(sheet_u.area),
           "refused_hard_surface": out_refused}

    # ── the mint, control and arm ──────────────────────────────────
    def run_mint(extra):
        cells = [c for c, _q in std]
        got = []

        def add(role, ref, poly, kind, cn=None, cl_=None, ev=None):
            rp = poly.representative_point()
            lat, lon = to_ll(rp.x, rp.y)
            got.append({"ref": ref, "role": role, "m2": round(poly.area),
                        "touches_apron": bool(ev and ev.get("touches_apron")),
                        "apron_shared_m": round(float(ev.get("apron_shared_m", 0.0)), 1) if ev else 0.0,
                        "perimeter_m": round(poly.length), "on_sheets_today_m2": round(poly.intersection(sheet_u).area),
                        "lat": round(lat, 7), "lon": round(lon, 7), "_poly": poly})
        sheets = tuple(getattr(a, "gap_sheets", ()) or ()) + tuple(
            Pavement(f"dsf:gapsheet{k + 1000}", None,
                     tuple((float(x), float(y)) for x, y in p.exterior.coords[:-1]),
                     tuple(tuple((float(x), float(y)) for x, y in r.coords[:-1]) for r in p.interiors),
                     d) for k, (d, p) in enumerate(extra))
        proxy = types.SimpleNamespace(gap_sheets=sheets, frame=a.frame)
        notes = []
        t = time.perf_counter()
        stats = mint_gap_pieces(proxy, cells, law, rules, add, notes)
        return got, stats, notes, time.perf_counter() - t

    ctl, ctl_stats, _n0, t_ctl = run_mint([])
    arm, arm_stats, notes, t_arm = run_mint(admitted_polys)
    ctl_m2 = sum(p["m2"] for p in ctl)
    arm_m2 = sum(p["m2"] for p in arm)
    print(f"  MINT control: {len(ctl)} pieces {ctl_m2:,.0f} m2 ({t_ctl:.1f} s) {ctl_stats}")
    print(f"  MINT arm:     {len(arm)} pieces {arm_m2:,.0f} m2 ({t_arm:.1f} s) {arm_stats}")
    print(f"  arm size distribution: {_quant([p['m2'] for p in arm])}")
    print(f"  arm apron-touching: {sum(p['touches_apron'] for p in arm)} pieces "
          f"{sum(p['m2'] for p in arm if p['touches_apron']):,.0f} m2")
    # per-piece diff: an arm piece is NEW when no control piece covers its point,
    # GROWN when the control piece there is smaller by > 1 m2
    ctl_polys = [(p, p["_poly"]) for p in ctl]
    new_p, grown = [], []
    for p in arm:
        pt = p["_poly"].representative_point()
        host = [c for c, q in ctl_polys if q.contains(pt)]
        if not host:
            new_p.append(p)
        elif p["m2"] - host[0]["m2"] > 1:
            grown.append((p, host[0]))
    print(f"  arm vs control: NEW pieces {len(new_p)} / {sum(p['m2'] for p in new_p):,.0f} m2; "
          f"GROWN {len(grown)} / +{sum(p['m2'] - h['m2'] for p, h in grown):,.0f} m2; "
          f"rim total arm {sum(p['perimeter_m'] for p in arm):,.0f} m (control {sum(p['perimeter_m'] for p in ctl):,.0f} m)")
    for p, h in grown[:10]:
        print(f"    grown {p['ref']:8s} {h['m2']:9,d} -> {p['m2']:9,d} m2  {p['lat']}, {p['lon']}")
    for p in sorted(new_p, key=lambda p: -p["m2"])[:10]:
        print(f"    new   {p['ref']:8s} {p['m2']:9,d} m2  {p['lat']}, {p['lon']}")
    # APPROXIMATE §59 road evidence per apron-touching arm piece (scratch read,
    # NOT the §59 readers: OSM highway way inside, 1206 route inside, road face
    # within the stand-off + weld; the §37 (2) lateral share = apron_shared / rim)
    from shapely.geometry import LineString
    from shapely.strtree import STRtree
    hw = [LineString(w.points) for w in getattr(a, "osm_ways", ()) or ()
          if w.tags.get("highway") and len(w.points) >= 2]
    hw_t = STRtree(hw) if hw else None
    rt = [LineString([n for n in r.points]) for r in getattr(a, "routes", ()) or ()
          if len(getattr(r, "points", ())) >= 2]
    rt_t = STRtree(rt) if rt else None
    road_faces = [q for c, q in std if c.role in ("service_road", "parking_lot")]
    rf_t = STRtree(road_faces) if road_faces else None
    stand = float(law.tables.structures.building_pad.groundside_cutback_m) + 0.0
    from auto_patch_v2.classify.gap_mint import standoff_m
    reach = standoff_m(law) + float(law.tables.emit.identity.weld_spacing_m)
    cls = collections.Counter()
    cls_m2 = collections.Counter()
    for p in arm:
        if not p["touches_apron"]:
            p["class_est"] = "road (no apron)"
            continue
        q = p["_poly"]
        ev_hw = bool(hw_t is not None and len(hw_t.query(q, predicate="intersects")))
        ev_rt = bool(rt_t is not None and len(rt_t.query(q.buffer(1.0), predicate="intersects")))
        ev_rf = bool(rf_t is not None and len(rf_t.query(q.buffer(reach), predicate="intersects")))
        share = p["apron_shared_m"] / max(p["perimeter_m"], 1.0)
        evid = ev_hw or ev_rt or ev_rf
        p["class_est"] = ("apron: no road evidence" if not evid else
                          "apron: share >= 20 %" if share >= 0.2 else "road by evidence")
        p["evidence"] = {"osm_highway": ev_hw, "route": ev_rt, "road_face": ev_rf, "share": round(share, 2)}
        cls[p["class_est"]] += 1
        cls_m2[p["class_est"]] += p["m2"]
    print(f"  apron-touching class ESTIMATE (§59 readers approximated): "
          + "; ".join(f"{k} {cls[k]} / {cls_m2[k]:,.0f} m2" for k in cls))
    for p in sorted(arm, key=lambda p: -p["m2"])[:12]:
        print(f"    {p['ref']:8s} {p['m2']:9,d} m2 rim {p['perimeter_m']:6,d} m apron_shared {p['apron_shared_m']:7.1f} m "
              f"{p.get('class_est', ''):26s} {p['lat']}, {p['lon']}")
    for n in notes[:8]:
        print("    note:", n)
    if PIECES_OUT:
        rings = [{"ref": p["ref"], "m2": p["m2"], "class_est": p.get("class_est"),
                  "touches_apron": p["touches_apron"],
                  "ring_ll": [list(to_ll(x, y)) for x, y in p["_poly"].exterior.coords]}
                 for p in arm]
        Path(PIECES_OUT).write_text(json.dumps(rings), encoding="utf-8")
    for p in ctl + arm:
        p.pop("_poly", None)
    out.update({"mint_control": {"pieces": len(ctl), "m2": round(ctl_m2), "stats": ctl_stats, "s": round(t_ctl, 1)},
                "mint_arm": {"pieces": len(arm), "m2": round(arm_m2), "stats": arm_stats, "s": round(t_arm, 1),
                             "dist": _quant([p["m2"] for p in arm]),
                             "apron_touching": sum(p["touches_apron"] for p in arm),
                             "apron_touching_m2": round(sum(p["m2"] for p in arm if p["touches_apron"])),
                             "pieces_list": sorted(arm, key=lambda p: -p["m2"])},
                "mint_notes": notes})

    # ── the #333 population: page cells over apt.dat pavement ──────
    over = collections.Counter()
    over_ex = collections.defaultdict(list)
    if not apt_pav.is_empty:
        for c, q in std:
            if str(c.ref).startswith("dsf:pol") and c.role != "building":
                x = q.intersection(apt_pav).area
                if x > 1.0:
                    over[c.role] += x
                    over_ex[c.role].append((str(c.ref), round(x)))
    print(f"  #333 population — name-admitted dsf:pol cells standing ON apt.dat pavement: "
          f"{sum(over.values()):,.0f} m2 " + ", ".join(f"{k} {v:,.0f}" for k, v in over.most_common()))
    for k in over:
        print(f"    {k}: {sorted(over_ex[k], key=lambda t: -t[1])[:5]}")
    out["page_over_aptdat_m2"] = {k: round(v) for k, v in over.items()}
    out["page_over_aptdat_examples"] = {k: sorted(v, key=lambda t: -t[1])[:8] for k, v in over_ex.items()}

    # ── sites ─────────────────────────────────────────────────────
    out["sites"] = []
    for lat, lon in sites:
        pt = Point(to_xy(lon, lat))
        hits = [(str(c.ref), c.role, c.side, round(q.area)) for c, q in std if q.contains(pt)]
        print(f"  site {lat}, {lon}: {hits or 'no cell'}")
        out["sites"].append({"lat": lat, "lon": lon, "cells": hits})
    return out


def main():
    warnings.filterwarnings("ignore")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pairs", nargs="+", metavar="ICAO=CAP.pkl")
    ap.add_argument("--json", type=Path)
    ap.add_argument("--site", action="append", default=[])
    ap.add_argument("--pieces-out", type=Path, help="write the arm pieces as lat/lon rings (one airport)")
    args = ap.parse_args()
    global PIECES_OUT
    PIECES_OUT = str(args.pieces_out) if args.pieces_out else None
    sites = [tuple(float(x) for x in s.split(",")) for s in args.site]
    res = {}
    for pair in args.pairs:
        icao, pkl = pair.split("=", 1)
        res[icao] = probe(icao, pkl, sites)
    if args.json:
        args.json.write_text(json.dumps(res, indent=1, default=str), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
