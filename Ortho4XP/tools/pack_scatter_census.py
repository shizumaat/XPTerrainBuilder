#!/usr/bin/env python3
"""THE SCATTER CENSUS — DRY (spec ``pack-read-once-fast-spec.md`` §B.2,
slice S5a).  Run from ``Ortho4XP/``::

    venv/bin/python tools/pack_scatter_census.py TNCM TFFG LEMD [--json OUT.json]

WHAT IT IS.  For each airport it resolves the pack the build would read
(``airport/pack.select_pack``), the DSF text dump the build would read
(``airport/dsf.find_text_dump`` — the CACHED dump only; it never runs
DSFTool and never writes), the placements inside the SAME window the
loader uses (``load.Inputs.radius_deg``, default 0.05 deg), and the
resource each one resolves to (``obj8.resolve_resource`` +
``pack.authored_source`` — the pristine ``.anchor_bak`` where one
exists, exactly as ``restore_before_read`` does).  Then it parses each
resource ONCE through an ``obj8.ResourceCache`` and asks
``airport/scatter.read``.

READ-ONLY, PARSE-ONLY.  No DEM, no OSM, no solve, no build, no capture,
no write anywhere — least of all the owner's X-Plane install.  Its cost
is the pack parse (2.5 % of a pack stage) and one pass of plan boxes.

WHAT IT REPORTS, per airport:

 1. every resource classed SCATTER: name, genuine components,
    placements, largest component plan-box diagonal, and the share of
    the window's placed components the class holds;
 2. (a) the LP FOOT-ROW exposure of the class — an UPPER BOUND, stated
    as one: today every non-line scatter member is an eligible group
    and each of its ground parts states up to ``[rebake]
    foot_samples_max`` target rows.  The MEASURED count needs the
    planar group + ``constraints/foot_rows`` stage, which this tool
    does not run (see NOT MEASURED);
 3. (b) the CLUSTER-PAD exposure — the placed plan-box area of scatter
    components that comes within ``[placement] footprint_touch_m`` of a
    NON-scatter COMPONENT's plan box, and how many non-scatter
    placements are touched.  A BOX-level proxy for "which pad outlines would change":
    conservative in both directions and named as a proxy, because the
    cluster works on rings;
 4. (c) the STRUCTURE-READ screen — for every would-be-scatter
    resource, the per-RESOURCE gates each structure reader passes
    through: authored depth below its own zero against ``[basin]
    admission_depth_m`` (the floor-witness / shell / door-well /
    sunken-road / wall-corridor population), ``skirt.is_skirt``,
    ``deck_signature.elevated_deck``, ``HARD``/``HARD_DECK`` triangles,
    ``line_object.is_line_object``.  Any resource reading true on one
    of those is listed BY NAME as a would-be false positive;
 5. (d) NEAR-THRESHOLD resources, so the two thresholds can be judged:
    components within [0.75, 1.5] x ``components_min``, or a component
    diagonal within [0.8, 1.2] x ``component_diag_max_m``.

NOT MEASURED HERE (stated so no reader mistakes the screen for the
pair): the ``structures.json`` DRY PAIR with the gate skipping scatter
vs not, the MEASURED foot-row count, and the MEASURED pad-outline
delta.  All three need a planar stage run per airport (LEMD 378 s /
4.8 GB) and, for the pair, the S5b wiring that does not exist yet.  The
screen in 4 is the static half: it is decisive about which resources
COULD reach a structure reader at all, because every reader is gated by
one of those per-resource readings.

Twin: ``tests/auto_patch_v2/test_v2packscatter.py``.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "src"))

import numpy as np                                             # noqa: E402

from auto_patch_v2.airport import apt_dat as _apt              # noqa: E402
from auto_patch_v2.airport import deck_signature as _deck      # noqa: E402
from auto_patch_v2.airport import dsf as _dsf                  # noqa: E402
from auto_patch_v2.airport import line_object as _line         # noqa: E402
from auto_patch_v2.airport import obj8 as _obj8                # noqa: E402
from auto_patch_v2.airport import pack as _pack                # noqa: E402
from auto_patch_v2.airport import scatter as _scatter          # noqa: E402
from auto_patch_v2.airport import skirt as _skirt              # noqa: E402
from auto_patch_v2.law import Law                              # noqa: E402

__all__ = ["census", "resolve_window", "Placement", "main"]


class Placement:
    """One placed ``.obj`` of the window: its resolved pristine path,
    its plan position in a LOCAL metric frame (metres east / north of
    the airport reference point) and its heading."""

    __slots__ = ("def_path", "resolved", "x", "y", "heading_deg")

    def __init__(self, def_path: str, resolved: str, x: float, y: float,
                 heading_deg: float) -> None:
        self.def_path, self.resolved = def_path, resolved
        self.x, self.y, self.heading_deg = x, y, heading_deg


def resolve_window(icao: str, xplane_root: str, mod_cache_root: str,
                   radius_deg: float = 0.05
                   ) -> tuple[list[Placement], dict]:
    """The window's placements and a provenance dict, or ``([], info)``
    with ``info['skip']`` naming what is not on disk."""
    info: dict = {"icao": icao}
    sel = _pack.select_pack(xplane_root, icao)
    if sel is None:
        info["skip"] = f"no apt.dat for {icao} under {xplane_root}"
        return [], info
    info["pack"] = sel.name
    info["pack_root"] = sel.root
    block = _apt.read_airport_block(sel.apt_dat_path, icao)
    if not block:
        info["skip"] = f"{icao} not in {sel.apt_dat_path}"
        return [], info
    lat0, lon0 = _apt.parse_airport_block(block).reference_point()
    info["reference_point"] = [lat0, lon0]
    tile = (int(math.floor(lat0)), int(math.floor(lon0)))
    dsf_path = _pack.tile_dsf_path(sel.root, tile[0], tile[1])
    if dsf_path is None:
        info["skip"] = f"no tile DSF {tile} in pack {sel.name}"
        return [], info
    dump = _dsf.find_text_dump(mod_cache_root, sel.name, tile[0], tile[1],
                               dsf_path=_pack.authored_source(dsf_path, sel.root)[0])
    if dump is None:
        dump = _dsf.find_text_dump(mod_cache_root, sel.name, tile[0], tile[1],
                                   dsf_path=dsf_path)
    if dump is None:
        info["skip"] = (f"no cached DSF text dump for {sel.name} {tile} under "
                        f"{mod_cache_root} (this tool never runs DSFTool)")
        return [], info
    info["dsf_dump"] = dump
    d = _dsf.read_dump(dump, accept_polygon=lambda p: False)
    index = _obj8.read_library_index(
        _obj8.library_index_path(mod_cache_root, xplane_root))
    # the loader's own metres-per-degree is the frame's projection; a plan
    # BOX census needs no more than the local flat scaling
    ml = 111_132.954
    mo = 111_412.84 * math.cos(math.radians(lat0))
    out: list[Placement] = []
    n_far = n_unresolved = 0
    for pl in d.placements:
        if not pl.def_path.lower().endswith(".obj"):
            continue
        if abs(pl.lat - lat0) > radius_deg or abs(pl.lon - lon0) > radius_deg:
            n_far += 1
            continue
        res = _obj8.resolve_resource(pl.def_path, sel.root, index)
        if res is None:
            n_unresolved += 1
            continue
        res, _restored = _pack.authored_source(res, sel.root)
        out.append(Placement(pl.def_path, res, (pl.lon - lon0) * mo,
                             (pl.lat - lat0) * ml, pl.heading_deg))
    info.update(placements=len(out), placements_outside_window=n_far,
                unresolved=n_unresolved, radius_deg=radius_deg)
    return out, info


def _placed_boxes(geom, comps, p: Placement) -> np.ndarray:
    """``(n, 4)`` plan boxes ``(x0, y0, x1, y1)`` in the local frame, one
    per component: the authored box's four corners rotated by the
    placement heading (``obj8._to_frame``) and re-bounded.  Conservative
    — a rotated box's bound contains the component."""
    v = geom.vertices
    rows = np.empty((len(comps), 4))
    h = math.radians(p.heading_deg)
    s, c = math.sin(h), math.cos(h)
    for k, cm in enumerate(comps):
        pts = v[cm.tris.reshape(-1)]
        x0, x1 = float(pts[:, 0].min()), float(pts[:, 0].max())
        z0, z1 = float(pts[:, 2].min()), float(pts[:, 2].max())
        cx = np.array([x0, x1, x0, x1])
        cz = np.array([z0, z0, z1, z1])
        X = p.x + cx * c - cz * s
        Y = p.y - (cx * s + cz * c)
        rows[k] = (X.min(), Y.min(), X.max(), Y.max())
    return rows


def census(icao: str, xplane_root: str, mod_cache_root: str,
           radius_deg: float = 0.05, law: "Law | None" = None,
           progress=None) -> dict:
    """One airport's census (module doc).  Returns the report dict the
    CLI prints and dumps."""
    t0 = time.time()
    law = law or Law.for_airport(icao)
    st = law.tables.structures
    sc, bl, rb = st.scatter, st.basin, st.rebake
    rep: dict = {"icao": icao,
                 "law": {"components_min": sc.components_min,
                         "component_diag_max_m": sc.component_diag_max_m,
                         "footprint_touch_m": st.placement.footprint_touch_m,
                         "foot_samples_max": rb.foot_samples_max,
                         "basin_admission_depth_m": bl.admission_depth_m,
                         "min_solid_thickness_m": bl.min_solid_thickness_m}}
    places, info = resolve_window(icao, xplane_root, mod_cache_root, radius_deg)
    rep["window"] = info
    if info.get("skip"):
        rep["skipped"] = info["skip"]
        return rep
    cache = _obj8.ResourceCache(bl.min_solid_thickness_m)
    by_res: dict[str, list[Placement]] = {}
    for p in places:
        by_res.setdefault(p.resolved, []).append(p)

    rows: list[dict] = []
    scatter_boxes: list[np.ndarray] = []
    other_boxes: list[np.ndarray] = []
    other_owner: list[np.ndarray] = []
    n_other_pl = 0
    tot_comp = tot_scatter_comp = 0
    for i, (res, pls) in enumerate(sorted(by_res.items())):
        if progress:
            progress(f"  [{i + 1}/{len(by_res)}] {os.path.basename(res)}")
        geom = cache.geometry(res)
        if geom is None or geom.solid.shape[0] == 0:
            continue
        comps = cache.genuine(res)
        if not comps:
            continue
        reading = _scatter.read(cache, res, law)
        placed_comps = len(comps) * len(pls)
        tot_comp += placed_comps
        # the per-RESOURCE structure gates (module doc item 4)
        min_y = min(float(c.min_y) for c in comps)
        deep = bool(min_y <= -bl.admission_depth_m)
        skirted = bool(_skirt.is_skirt(cache, res, law))
        deck = bool(_deck.elevated_deck(cache, res, law).deck)
        row = {"resource": os.path.relpath(res, info["pack_root"])
               if info.get("pack_root") else res,
               "scatter": reading.scatter, "reason": reading.reason,
               "components": reading.components,
               "components_small": reading.components_small,
               "components_line_shaped": reading.components_line,
               "max_diag_m": round(reading.max_diag_m, 3),
               "max_oversize_diag_m": round(reading.max_oversize_diag_m, 3),
               "hard_triangles": reading.hard_triangles,
               "line_object": reading.line_object,
               "placements": len(pls),
               "placed_components": placed_comps,
               "stock_library": any(_obj8.is_stock_library_resource(q.def_path)
                                    for q in pls),
               "min_authored_y_m": round(min_y, 3),
               "below_admission_depth": deep,
               "skirt": skirted, "elevated_deck": deck}
        rows.append(row)
        boxes = np.concatenate([_placed_boxes(geom, comps, p) for p in pls])
        if reading.scatter:
            tot_scatter_comp += placed_comps
            scatter_boxes.append(boxes)
        else:
            # the non-scatter side is read per COMPONENT, not per placement
            # BOUND: a terminal's or a ground object's whole bound swallows
            # the apron, and every bush standing on it would read "touching"
            other_boxes.append(boxes)
            other_owner.append(np.repeat(
                np.arange(n_other_pl, n_other_pl + len(pls)), len(comps)))
            n_other_pl += len(pls)
        cache._geom.pop(res, None)          # stream: one resource at a time
        cache._comps.pop(res, None)

    rep["resources"] = len(rows)
    rep["placed_components"] = tot_comp
    rep["scatter_placed_components"] = tot_scatter_comp
    rep["scatter_component_share"] = (round(tot_scatter_comp / tot_comp, 5)
                                      if tot_comp else 0.0)
    scat = [r for r in rows if r["scatter"]]
    rep["scatter_resources"] = len(scat)
    rep["rows"] = sorted(rows, key=lambda r: -r["placed_components"])

    # (a) the LP foot-row exposure — an UPPER BOUND
    bound_bodies = sum(r["placed_components"] for r in scat if not r["line_object"])
    rep["foot_rows"] = {
        "kind": "UPPER BOUND (not the measured LP row count)",
        "scatter_placements": sum(r["placements"] for r in scat),
        "scatter_parts": bound_bodies,
        "rows_upper_bound": bound_bodies * int(rb.foot_samples_max),
        "note": ("every part of a non-line scatter member is an eligible "
                 "group's ground part today and states up to foot_samples_max "
                 "target rows; the measured count needs the planar group + "
                 "constraints/foot_rows stage, which this tool does not run")}

    # (b) the cluster-pad exposure — a BOX proxy
    rep["cluster_pads"] = _pad_proxy(scatter_boxes, other_boxes, other_owner,
                                     n_other_pl, st.placement.footprint_touch_m)

    # (c) the structure-read screen
    fp = [{"resource": r["resource"],
           "why": ",".join(w for w, on in (
               ("below_admission_depth", r["below_admission_depth"]),
               ("skirt", r["skirt"]), ("elevated_deck", r["elevated_deck"]),
               ("hard", bool(r["hard_triangles"])),
               ("line_object", r["line_object"])) if on),
           "components": r["components"], "placements": r["placements"]}
          for r in scat
          if r["below_admission_depth"] or r["skirt"] or r["elevated_deck"]
          or r["hard_triangles"] or r["line_object"]]
    rep["structure_read_false_positives"] = fp

    # (d) near-threshold
    lo_n, hi_n = 0.75 * sc.components_min, 1.5 * sc.components_min
    lo_d, hi_d = 0.8 * sc.component_diag_max_m, 1.2 * sc.component_diag_max_m
    near = [r for r in rows
            if (lo_n <= r["components"] <= hi_n)
            or (lo_d <= r["max_diag_m"] <= hi_d)
            or (lo_d <= r["max_oversize_diag_m"] <= hi_d)]
    rep["near_threshold"] = sorted(near, key=lambda r: -r["placed_components"])
    rep["wall_s"] = round(time.time() - t0, 1)
    return rep


def _pad_proxy(scatter_boxes, other_boxes, other_owner, n_other_pl: int,
               touch_m: float) -> dict:
    """(b): the placed plan-box area of scatter components within
    ``touch_m`` of a NON-scatter COMPONENT's plan box, and how many
    non-scatter placements are touched.  A PROXY, named as one: the
    cluster and the pad work on rings, and a component's box contains
    its ring."""
    out = {"kind": "BOX PROXY (the cluster works on rings, not boxes)",
           "touch_m": touch_m, "scatter_boxes": 0, "scatter_box_area_m2": 0.0,
           "touching_boxes": 0, "touching_box_area_m2": 0.0,
           "non_scatter_placements": 0, "non_scatter_placements_touched": 0}
    out["non_scatter_placements"] = int(n_other_pl)
    if not scatter_boxes or not other_boxes:
        if scatter_boxes:
            S = np.concatenate(scatter_boxes)
            out["scatter_boxes"] = int(S.shape[0])
            out["scatter_box_area_m2"] = round(float(
                ((S[:, 2] - S[:, 0]) * (S[:, 3] - S[:, 1])).sum()), 1)
        return out
    import shapely
    S = np.concatenate(scatter_boxes)
    O = np.concatenate(other_boxes)
    own = np.concatenate(other_owner)
    area = (S[:, 2] - S[:, 0]) * (S[:, 3] - S[:, 1])
    out["scatter_boxes"] = int(S.shape[0])
    out["scatter_box_area_m2"] = round(float(area.sum()), 1)
    out["non_scatter_component_boxes"] = int(O.shape[0])
    tree = shapely.STRtree(shapely.box(O[:, 0] - touch_m, O[:, 1] - touch_m,
                                       O[:, 2] + touch_m, O[:, 3] + touch_m))
    qi, ti = tree.query(shapely.box(S[:, 0], S[:, 1], S[:, 2], S[:, 3]))
    hit = np.unique(qi)
    out["touching_boxes"] = int(hit.shape[0])
    out["touching_box_area_m2"] = round(float(area[hit].sum()), 1)
    out["non_scatter_placements_touched"] = int(np.unique(own[ti]).shape[0])
    return out


def _print(rep: dict) -> None:
    icao = rep["icao"]
    if rep.get("skipped"):
        print(f"\n{icao}: SKIPPED — {rep['skipped']}")
        return
    w = rep["window"]
    print(f"\n{icao}  pack {w.get('pack')}  placements {w.get('placements')} "
          f"in +/-{w.get('radius_deg')} deg  resources {rep['resources']}  "
          f"({rep['wall_s']} s)")
    print(f"  SCATTER: {rep['scatter_resources']} resources, "
          f"{rep['scatter_placed_components']} of {rep['placed_components']} "
          f"placed components ({100 * rep['scatter_component_share']:.1f} %)  "
          f"[N >= {rep['law']['components_min']}, "
          f"D <= {rep['law']['component_diag_max_m']} m]")
    scat = [r for r in rep["rows"] if r["scatter"]]
    if scat:
        print(f"  {'placed':>9} {'comps':>7} {'pl':>4} {'dmax':>7}  resource")
        for r in scat[:25]:
            print(f"  {r['placed_components']:9d} {r['components']:7d} "
                  f"{r['placements']:4d} {r['max_diag_m']:7.2f}  "
                  f"{'lib ' if r['stock_library'] else ''}{r['resource']}")
        if len(scat) > 25:
            print(f"  ... and {len(scat) - 25} more")
    fr = rep["foot_rows"]
    print(f"  (a) foot rows: {fr['scatter_parts']} scatter parts over "
          f"{fr['scatter_placements']} placements -> <= {fr['rows_upper_bound']} "
          f"LP rows ({fr['kind']})")
    cp = rep["cluster_pads"]
    print(f"  (b) cluster pads: {cp['touching_boxes']} of {cp['scatter_boxes']} "
          f"scatter boxes touch a non-scatter placement "
          f"({cp['touching_box_area_m2']} of {cp['scatter_box_area_m2']} m2 of "
          f"box area); {cp['non_scatter_placements_touched']} of "
          f"{cp['non_scatter_placements']} placements touched — {cp['kind']}")
    fp = rep["structure_read_false_positives"]
    print(f"  (c) structure-read screen: {len(fp)} would-be-scatter resource(s) "
          f"pass a structure reader's per-resource gate")
    for r in fp:
        print(f"      {r['why']:28s} {r['components']:6d} comps  {r['resource']}")
    nt = rep["near_threshold"]
    print(f"  (d) near threshold: {len(nt)}")
    for r in nt[:15]:
        print(f"      comps {r['components']:6d}  dmax {r['max_diag_m']:7.2f}  "
              f"{'SCATTER' if r['scatter'] else 'no':>7}  {r['resource']}")
    if len(nt) > 15:
        print(f"      ... and {len(nt) - 15} more")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("icao", nargs="+")
    ap.add_argument("--xplane-root", default=None)
    ap.add_argument("--mod-cache-root", default=None)
    ap.add_argument("--radius-deg", type=float, default=0.05)
    ap.add_argument("--json", default=None, help="write the full report here")
    ap.add_argument("--quiet", action="store_true", help="no per-resource progress")
    a = ap.parse_args(argv)
    if a.xplane_root is None or a.mod_cache_root is None:
        from auto_patch_v2.planar.__main__ import default_inputs
        inp = default_inputs()
        a.xplane_root = a.xplane_root or inp.xplane_root
        a.mod_cache_root = a.mod_cache_root or inp.mod_cache_root
    print(f"X-Plane root : {a.xplane_root}  (READ-ONLY)")
    print(f"mod cache    : {a.mod_cache_root}")
    out = []
    for icao in a.icao:
        rep = census(icao.upper(), a.xplane_root, a.mod_cache_root, a.radius_deg,
                     progress=None if a.quiet else lambda s: print(s, flush=True))
        _print(rep)
        out.append(rep)
    if a.json:
        with open(a.json, "w") as fh:
            json.dump(out, fh, indent=1)
        print(f"\nwrote {a.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
