#!/usr/bin/env python3
"""ARM SITE READ — the same named sites, read across two arms.

    venv/bin/python tools/arm_site_read.py CTL.osm ARM.osm \\
        [--site NAME=LAT,LON ...] [--radius M] \\
        [--rows CTL.rows.json ARM.rows.json] [--seats] [--welds] \\
        [--profile [--profile-roles ROLE,ROLE]] \\
        [--line NAME=LAT,LON:LAT,LON [--line-corridor-m M]] [--json OUT]

Run it from ``Ortho4XP/``.

THE QUESTION an A/B leaves open.  `harness/census.py --rows-json` itemises a
patch's law-true rows and `census_rows_diff.py` joins two dumps class by
class — but neither can be asked about a PLACE, and a round's acceptance is
written in places ("the wall at 35.2077303,-80.9290869", "the ramp corridor's
three coordinates").  `osm_site.py` answers what geometry is at a coordinate;
it does not carry law rows or pad seats.  This tool is the join: per named
site, per arm, the law-true rows within a radius and their worst grade — and,
with ``--seats``, the BUILDING PAD seats that moved between the two arms,
which is the channel this repo's HECA airside attribution ran through (a pad
seat welds into the apron ring, so a seat that moves moves airside).

**IT MEASURES NO LAW AND COUNTS NO DEFECTS.**  Rows are read verbatim out of
`census.py --rows-json` dumps — the census remains the only instrument that
produces defect counts (the census-wrapper precedent, RULINGS `7e90032`) —
and geometry/altitudes are read through the harness library's own parser
(`check_grade._parse_osm`), so this tool and the census read one file the
same way.  A missing input is reported as SKIPPED, never as zero.

``--welds`` answers the OTHER acceptance question a place can be asked —
IS THIS SEAM JOINED?  (corridor-joins round, spec ruling 4(a): "count of
shared node refs between road-family and airside ways per mouth, with the
max |Δalt| across each seam".)  Row absence cannot answer it: a census row
exists only BETWEEN PAIRED GEOMETRY, so an UNWELDED road↔taxiway seam is
SILENT in every census — which is exactly how two acceptance claims passed
on a 0.999 m gap that no node could bridge.  Per site, per arm, this reports
the node ids shared between the two families, the worst altitude difference
carried at a shared node, the nearest unwelded approach when there are none,
and the retaining walls standing at the site.

``--profile`` / ``--line`` answer the THIRD question a place can be asked —
WHAT SHAPE IS THE SURFACE HERE?  A round whose acceptance is written as "no
unlawful step along the owner line" or "the ripple is faired, report the
amplitude before and after" (docs/specs/heca-apron-round2-spec.md) needs the
emitted elevation itself, and neither a row count nor a weld table carries
it.  ``--profile`` walks every ring of ``--profile-roles`` reaching a site
and reports its worst consecutive EDGE and its RIPPLE AMPLITUDE — the
peak-to-peak inside a 50 m run along the ring, the same window
``apron_drape_read`` calls ``amp50``.  ``--line`` orders every emitted
vertex in a corridor about an owner-named segment by its station along that
segment, with the step between consecutive stations: the reading that shows
an unlawful step AND the reading that shows a NODELESS VOID, because there
an empty station list is itself the finding.  Neither prices a law — the
census remains the only defect instrument — so quote them ARM TO ARM on
identical options, never as a verdict.

THE FRAMES, both stated on the report:
* rows are located by the census's own row lat/lon, which for a within-shape
  pair is the PAIR's position — a long chord's row can therefore sit far from
  either endpoint's geometry (measured: 400 m+ apron chords at HECA), so a
  site radius selects rows NEAR THE PAIR, not rows whose shape touches the
  site;
* seats join by the building's ``ref`` tag across the two arms — way ids and
  shapeIDs are arm-dependent and are never joined on.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import math
import sys
from pathlib import Path

__all__ = ["rows_near", "seat_moves", "seam_welds", "load_rows",
           "station_profiles", "line_profile",
           "SiteReadRefusal", "ROAD_FAMILY_ROLES", "AIRSIDE_SEAM_ROLES",
           "PROFILE_ROLES", "AMP_WINDOW_M"]

#: ``--profile`` default role scope: the surfaces the 2026-08-25 HECA
#: apron round is written about — the apron itself and the graded strip
#: that carries its back edge.
PROFILE_ROLES = ("apron", "graded_strip")

#: The window the ripple AMPLITUDE is measured in, along the ring.  Same
#: 50 m ``apron_drape_read`` uses for its ``amp50`` — one spelling of
#: "the local uneven hills and valleys" reading across the two tools.
AMP_WINDOW_M = 50.0

#: The two families a corridor MOUTH joins.  Road side: the census's own
#: ``check_grade._ROAD_FAMILY_ROLES``, read from it at call time (never a
#: second literal).  Airside: every role the census treats as airside that a
#: road can physically meet — the aircraft movement area.
ROAD_FAMILY_ROLES = ("service_road", "service_junction")
AIRSIDE_SEAM_ROLES = ("apron", "junction", "primary_parallel",
                      "secondary_parallel", "stub", "cross_connector",
                      "runway", "runway_crossing")

_ROOT = Path(__file__).resolve().parents[1]
_M_PER_DEG = 111320.0


class SiteReadRefusal(RuntimeError):
    """A question this tool will not answer with a guess."""


def _check_grade():
    sys.path.insert(0, str(_ROOT / "src"))
    spec = importlib.util.spec_from_file_location(
        "arm_site_read_check_grade", _ROOT / "tools" / "check_grade.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _dist_m(lat_a, lon_a, lat_b, lon_b) -> float:
    return math.hypot((lat_a - lat_b) * _M_PER_DEG,
                      (lon_a - lon_b) * _M_PER_DEG
                      * math.cos(math.radians(lat_a)))


def load_rows(path) -> list:
    """A census ``--rows-json`` dump's row list, verbatim."""
    try:
        data = json.loads(Path(path).read_text())
    except (OSError, ValueError) as exc:
        raise SiteReadRefusal(f"cannot read rows dump {path}: {exc}") from exc
    rows = data.get("rows")
    if not isinstance(rows, list):
        raise SiteReadRefusal(
            f"{path} is not a census --rows-json dump (no 'rows' key)")
    return rows


def rows_near(rows, lat, lon, radius_m: float) -> dict:
    """Law-true rows within ``radius_m`` of a site, and their worst grade."""
    hits = []
    for r in rows:
        rlat, rlon = r.get("lat"), r.get("lon")
        if rlat is None or rlon is None:
            continue
        d = _dist_m(rlat, rlon, lat, lon)
        if d <= radius_m:
            hits.append((round(d, 1), r))
    hits.sort(key=lambda t: t[0])
    return {
        "n_rows": len(hits),
        "worst_grade_pct": max((h[1].get("grade_pct") or 0.0 for h in hits),
                               default=0.0),
        "worst_magnitude_m": max((h[1].get("magnitude_m") or 0.0
                                  for h in hits), default=0.0),
        "families": sorted({f'{h[1]["family"]}::{h[1]["roles"]}'
                            for h in hits}),
        "worst": [{"d_m": d, "family": r["family"], "roles": r["roles"],
                   "magnitude_m": r["magnitude_m"],
                   "grade_pct": r["grade_pct"], "way_a": r.get("way_a")}
                  for (d, r) in sorted(
                      hits, key=lambda t: -(t[1].get("magnitude_m") or 0))[:3]],
    }


def _seats(cg, patch) -> dict:
    """``{building ref: flat seat}`` read verbatim from the patch."""
    nodes, ways = cg._parse_osm(Path(patch))
    out = {}
    for w in ways:
        if w.role != "building" or not w.ref:
            continue
        alts = [a for a in (w.elevs or []) if a is not None]
        if not alts:
            tag = (w.tags or {}).get("altitude")
            if tag:
                alts = [float(tag)]
        if alts:
            pts = [nodes[n] for n in w.nids if n in nodes]
            out[w.ref] = (min(alts),
                          sum(p[0] for p in pts) / len(pts) if pts else None,
                          sum(p[1] for p in pts) / len(pts) if pts else None)
    return out


def seat_moves(cg, ctl_patch, arm_patch, *, floor_m: float = 0.01) -> dict:
    """Building pad seats that moved between the two arms, joined by ``ref``."""
    ctl, arm = _seats(cg, ctl_patch), _seats(cg, arm_patch)
    common = sorted(set(ctl) & set(arm))
    moved = [{"ref": r, "ctl_m": ctl[r][0], "arm_m": arm[r][0],
              "delta_m": round(arm[r][0] - ctl[r][0], 3),
              "lat": arm[r][1], "lon": arm[r][2]}
             for r in common if abs(arm[r][0] - ctl[r][0]) > floor_m]
    moved.sort(key=lambda d: -abs(d["delta_m"]))
    mags = sorted(abs(m["delta_m"]) for m in moved)
    return {
        "pads_joined": len(common),
        "pads_moved": len(moved),
        "floor_m": floor_m,
        "median_abs_delta_m": (mags[len(mags) // 2] if mags else 0.0),
        "max_abs_delta_m": (mags[-1] if mags else 0.0),
        "worst": moved[:10],
    }


#: Two shared nodes belong to the same MOUTH when they lie within this of
#: each other — one corridor width (``config.SERVICE_ROAD_WIDTH_M`` = 6 m)
#: with margin, i.e. "the same crossing", not "the same airport".  A
#: reporting choice, printed with every table: two runs at two windows are
#: two populations.
MOUTH_CLUSTER_M = 12.0


def seam_welds(cg, patch, lat=None, lon=None, radius_m=None) -> dict:
    """The SEAM-WELD table at one site: is the road↔airside seam JOINED?

    Reads the patch through the harness library's own parser, so this tool
    and the census read one file one way.  Reported, all within
    ``radius_m`` of the site:

    * ``shared_nodes`` — node ids carried by BOTH a road-family way and an
      airside way.  A shared node IS the weld: one node, one position, and
      (with per-way altitudes) one value per way at it.
    * ``max_seam_dalt_m`` — the worst altitude difference two ways carry at
      a SHARED node.  0.00 is the construction the ruling demands (the
      solver grades one node); anything else is a torn weld.
    * ``nearest_unwelded_m`` — when nothing is shared, the closest approach
      between the two families' nodes.  This is the number that says
      "unweldable" (0.999 m at the KCLT sites, against a 0.5 m weld
      tolerance) where a census reports silence.
    * ``walls`` — ``retaining_wall`` ways at the site, with their refs: the
      "wall gone both sides" half of the same acceptance claim.
    * ``mouths`` — the shared nodes clustered at ``MOUTH_CLUSTER_M``, so
      "≥2 shared nodes PER MOUTH" is answerable rather than a patch total.

    ``lat``/``lon``/``radius_m`` omitted ⇒ the WHOLE PATCH (the reading for
    an airport with no owner-named site).

    Pure read: no law, no defect counts (those are the census's alone).
    """
    nodes, ways = cg._parse_osm(Path(patch))
    road_roles = set(getattr(cg, "_ROAD_FAMILY_ROLES", ROAD_FAMILY_ROLES))
    air_roles = set(AIRSIDE_SEAM_ROLES)
    whole = lat is None or lon is None or radius_m is None

    def _near(w):
        if whole:
            return True
        for nid in w.nids:
            p = nodes.get(nid)
            if p is not None and _dist_m(p[0], p[1], lat, lon) <= radius_m:
                return True
        return False

    road_ways = [w for w in ways if w.role in road_roles and _near(w)]
    air_ways = [w for w in ways if w.role in air_roles and _near(w)]
    walls = [w for w in ways if w.role == "retaining_wall" and _near(w)]

    def _alts(group):
        out: dict = {}
        for w in group:
            for nid, a in zip(w.nids, (w.elevs or [])):
                if a is not None:
                    out.setdefault(nid, []).append((w.wid, float(a)))
        return out

    road_alt, air_alt = _alts(road_ways), _alts(air_ways)
    road_nids = {nid for w in road_ways for nid in w.nids}
    air_nids = {nid for w in air_ways for nid in w.nids}
    shared = sorted(nid for nid in (road_nids & air_nids)
                    if nid in nodes
                    and (whole or _dist_m(nodes[nid][0], nodes[nid][1],
                                          lat, lon) <= radius_m))
    worst = 0.0
    worst_nid = None
    for nid in shared:
        vals = [v for (_w, v) in road_alt.get(nid, [])
                + air_alt.get(nid, [])]
        if len(vals) >= 2 and (max(vals) - min(vals)) > worst:
            worst, worst_nid = max(vals) - min(vals), nid
    nearest = None
    if not shared and road_nids and air_nids:
        nearest = min(
            (_dist_m(nodes[a][0], nodes[a][1], nodes[b][0], nodes[b][1])
             for a in road_nids if a in nodes
             for b in air_nids if b in nodes),
            default=None)
    # MOUTH CLUSTERS: shared nodes within ``MOUTH_CLUSTER_M`` of one another
    # are one crossing (single-link, the same connected-components rule the
    # census's site clustering uses, at this tool's own stated window).
    pts = [(nid, nodes[nid][0], nodes[nid][1]) for nid in shared]
    parent = {nid: nid for (nid, _la, _lo) in pts}

    def _find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for i, (na, la, lo) in enumerate(pts):
        for (nb, lb, ob) in pts[i + 1:]:
            if _dist_m(la, lo, lb, ob) <= MOUTH_CLUSTER_M:
                ra, rb = _find(na), _find(nb)
                if ra != rb:
                    parent[rb] = ra
    groups: dict = {}
    for (nid, la, lo) in pts:
        groups.setdefault(_find(nid), []).append((la, lo))
    mouths = sorted(
        ({"lat": round(sum(p[0] for p in g) / len(g), 7),
          "lon": round(sum(p[1] for p in g) / len(g), 7),
          "shared_nodes": len(g)} for g in groups.values()),
        key=lambda d: -d["shared_nodes"])
    return {
        "road_ways": len(road_ways), "airside_ways": len(air_ways),
        "shared_nodes": len(shared),
        "shared_nids": shared[:20],
        "mouths": len(mouths),
        "mouths_ge2_nodes": sum(1 for m in mouths if m["shared_nodes"] >= 2),
        "mouth_cluster_m": MOUTH_CLUSTER_M,
        "mouth_list": mouths[:12],
        "max_seam_dalt_m": round(worst, 4),
        "max_seam_dalt_nid": worst_nid,
        "nearest_unwelded_m": (round(nearest, 4)
                               if nearest is not None else None),
        "walls": len(walls),
        "wall_refs": sorted({w.ref for w in walls if w.ref})[:8],
        "wall_wids": sorted(w.wid for w in walls)[:8],
    }


def _fmt(v, nd=2):
    """A missing reading prints as ``—``, never as 0.00."""
    return "—" if v is None else f"{v:.{nd}f}"


def _patch_frame(cg, patch):
    """``(nodes, ways, to_m)`` — the harness library's own parser and the
    metre frame about the SIDECAR ANCHOR (the builder's own projection
    origin; the node-mean fallback differs from it in x-scale by
    ``cos(lat0)``, which is millimetres over a chord and enough to move a
    contact predicate).  A patch with no sidecar falls back to the node
    mean, which ``_ll_to_m_factory`` already implements."""
    feats: dict = {}
    nodes, ways = cg._parse_osm(Path(patch), feature_out=feats)
    # OPEN CONSTRAINED BREAKLINES are not rings, so ``_parse_osm`` routes
    # them to ``feature_out`` and they never appear in ``ways``.  They
    # carry REAL EMITTED STATIONS all the same — the apron interior
    # lattice is exactly that — and a profile that could not see them
    # would report a void the patch no longer has.  Their role tag is
    # empty by design, so they are addressed by their ``o4_feature``
    # class name (``--profile-roles apron_lattice``).
    for _cls, _fways in (feats or {}).items():
        for _w in _fways:
            try:
                _w.role = _w.role or _cls
            except Exception:                             # pragma: no cover
                continue
        ways = list(ways) + list(_fways)
    anchor = None
    side = Path(str(patch) + ".axes.json")
    if side.exists():
        try:
            anchor = json.loads(side.read_text()).get("anchor")
        except Exception:
            anchor = None
    return nodes, ways, cg._ll_to_m_factory(nodes, anchor)


def _ring_geometry(cg, patch, roles):
    """``[(way, [(x, y)], [alt])]`` for every ring of the named roles, in
    the sidecar's own metre frame — the same parser and the same frame
    the census reads the file with."""
    nodes, ways, to_m = _patch_frame(cg, patch)
    out = []
    for w in ways:
        if w.role not in roles:
            continue
        pts, elevs = [], []
        for nid, a in zip(w.nids, (w.elevs or [None] * len(w.nids))):
            p = nodes.get(nid)
            if p is None:
                continue
            pts.append(to_m(p[0], p[1]))
            elevs.append(None if a is None else float(a))
        if len(pts) >= 2:
            out.append((w, pts, elevs))
    return out


def _amp_in_window(cum, alts, window_m):
    """Max peak-to-peak elevation inside any ``window_m`` run of the
    station sequence — the RIPPLE amplitude.  ``None`` when the run is
    shorter than the window (a reading a window cannot support is not a
    reading)."""
    best = None
    n = len(cum)
    for i in range(n):
        j = i
        while j + 1 < n and cum[j + 1] - cum[i] <= window_m:
            j += 1
        if cum[j] - cum[i] < window_m * 0.5:
            continue
        vals = [a for a in alts[i:j + 1] if a is not None]
        if len(vals) < 2:
            continue
        amp = max(vals) - min(vals)
        if best is None or amp > best:
            best = amp
    return best


def station_profiles(cg, patch, lat, lon, radius_m, *, roles=PROFILE_ROLES,
                     window_m=AMP_WINDOW_M, max_rings=6):
    """The STATION PROFILE of every ring of ``roles`` reaching within
    ``radius_m`` of one site.

    Per ring: the worst consecutive EDGE inside the neighbourhood
    (``|dz|``, its length, its grade) and the ripple AMPLITUDE — the
    peak-to-peak elevation inside a ``window_m`` run ALONG THE RING.
    Both are STATEMENTS ABOUT A SURFACE, not defect counts: the census
    remains the only instrument that prices a law.
    """
    _n, _w, to_m = _patch_frame(cg, patch)
    sx, sy = to_m(lat, lon)
    out = []
    for (w, pts, elevs) in _ring_geometry(cg, patch, set(roles)):
        near = [k for k, (x, y) in enumerate(pts)
                if math.hypot(x - sx, y - sy) <= radius_m]
        if not near:
            continue
        lo, hi = min(near), max(near)
        seg_pts, seg_alts = pts[lo:hi + 1], elevs[lo:hi + 1]
        if len(seg_pts) < 2:
            continue
        cum = [0.0]
        for k in range(len(seg_pts) - 1):
            cum.append(cum[-1] + math.hypot(seg_pts[k + 1][0]
                                            - seg_pts[k][0],
                                            seg_pts[k + 1][1]
                                            - seg_pts[k][1]))
        worst = None
        for k in range(len(seg_pts) - 1):
            a, b = seg_alts[k], seg_alts[k + 1]
            L = cum[k + 1] - cum[k]
            if a is None or b is None or L <= 1e-9:
                continue
            dz = abs(b - a)
            if worst is None or dz / L > worst[2]:
                worst = (dz, L, dz / L)
        vals = [a for a in seg_alts if a is not None]
        out.append({
            "way": w.wid, "role": w.role, "ref": getattr(w, "ref", "") or "",
            "n_stations": len(seg_pts),
            "run_m": round(cum[-1], 2),
            "alt_min": round(min(vals), 3) if vals else None,
            "alt_max": round(max(vals), 3) if vals else None,
            "worst_step_m": None if worst is None else round(worst[0], 3),
            "worst_step_len_m": None if worst is None else round(worst[1], 2),
            "worst_step_pct": (None if worst is None
                               else round(100.0 * worst[2], 2)),
            "amp_window_m": window_m,
            "amp_m": (lambda v: None if v is None else round(v, 3))(
                _amp_in_window(cum, seg_alts, window_m)),
            "stations": [[round(c, 2), a]
                         for c, a in zip(cum, seg_alts)][:60],
        })
    out.sort(key=lambda r: -(r["amp_m"] or 0.0))
    return out[:max_rings]


def line_profile(cg, patch, a_ll, b_ll, *, corridor_m=15.0,
                 roles=PROFILE_ROLES):
    """The emitted elevation ALONG an owner-named LINE.

    Every emitted vertex of ``roles`` within ``corridor_m`` of the
    segment ``a_ll``→``b_ll``, ordered by its station along that
    segment, with the step between consecutive stations.  This is the
    reading the cliff acceptance is written in — "the emitted elevation
    along the owner line has no step > the local law" — and it is also
    the only reading that shows whether INTERIOR VERTICES EXIST in a
    former void at all: an empty station list IS the finding.
    """
    _n, _w, to_m = _patch_frame(cg, patch)
    ax, ay = to_m(*a_ll)
    bx, by = to_m(*b_ll)
    dx, dy = bx - ax, by - ay
    L = math.hypot(dx, dy)
    if L <= 1e-6:
        raise SiteReadRefusal("--line wants two distinct coordinates")
    ux, uy = dx / L, dy / L
    seen: set = set()
    hits: list = []
    for (w, pts, elevs) in _ring_geometry(cg, patch, set(roles)):
        for (x, y), alt in zip(pts, elevs):
            s = (x - ax) * ux + (y - ay) * uy
            q = abs((x - ax) * uy - (y - ay) * ux)
            if s < -corridor_m or s > L + corridor_m or q > corridor_m:
                continue
            key = (round(x, 3), round(y, 3))
            if key in seen:
                continue
            seen.add(key)
            hits.append((round(s, 2), alt, round(q, 2), w.wid, w.role))
    hits.sort()
    steps = []
    for k in range(len(hits) - 1):
        s0, a0 = hits[k][0], hits[k][1]
        s1, a1 = hits[k + 1][0], hits[k + 1][1]
        ds = s1 - s0
        if a0 is None or a1 is None or ds <= 1e-6:
            continue
        steps.append((abs(a1 - a0), ds, abs(a1 - a0) / ds, s0))
    worst = max(steps, key=lambda t: t[2]) if steps else None
    vals = [h[1] for h in hits if h[1] is not None]
    return {
        "line_m": round(L, 2), "corridor_m": corridor_m,
        "n_stations": len(hits),
        "alt_min": round(min(vals), 3) if vals else None,
        "alt_max": round(max(vals), 3) if vals else None,
        "worst_step_m": None if worst is None else round(worst[0], 3),
        "worst_step_len_m": None if worst is None else round(worst[1], 2),
        "worst_step_pct": (None if worst is None
                           else round(100.0 * worst[2], 2)),
        "worst_step_at_m": None if worst is None else worst[3],
        "stations": [[h[0], h[1], h[2], h[3], h[4]] for h in hits][:120],
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("control", help="control arm patch .osm")
    ap.add_argument("arm", help="the arm under test, patch .osm")
    ap.add_argument("--site", action="append", default=[],
                    metavar="NAME=LAT,LON")
    ap.add_argument("--radius", type=float, default=25.0)
    ap.add_argument("--rows", nargs=2, metavar=("CTL.rows.json",
                                                "ARM.rows.json"))
    ap.add_argument("--seats", action="store_true")
    ap.add_argument("--welds", action="store_true",
                    help="per site, the road↔airside seam-weld table "
                         "(shared nodes, max seam |Δalt|, walls)")
    ap.add_argument("--profile", action="store_true",
                    help="per site, the emitted STATION PROFILE of the "
                         "rings reaching it (worst edge + ripple "
                         "amplitude in a 50 m window along the ring)")
    ap.add_argument("--profile-roles", default=",".join(PROFILE_ROLES),
                    metavar="ROLE[,ROLE]",
                    help="roles the profile walks (default "
                         f"{','.join(PROFILE_ROLES)})")
    ap.add_argument("--line", action="append", default=[],
                    metavar="NAME=LAT,LON:LAT,LON",
                    help="the emitted elevation ALONG an owner line — "
                         "every vertex in the corridor, by station, with "
                         "the step; an EMPTY station list is the finding")
    ap.add_argument("--line-corridor-m", type=float, default=15.0)
    ap.add_argument("--json", dest="json_out")
    args = ap.parse_args(argv)

    sites = {}
    try:
        for spec in args.site:
            name, coord = spec.split("=", 1)
            lat, lon = (float(v) for v in coord.split(","))
            sites[name] = (lat, lon)
    except ValueError:
        print("REFUSED: --site wants NAME=LAT,LON", file=sys.stderr)
        return 2

    out: dict = {"control": args.control, "arm": args.arm,
                 "radius_m": args.radius}
    print(f"=== arm site read\n  control {args.control}\n  arm     {args.arm}")
    print(f"  frame: rows are located by the CENSUS's own row lat/lon (a "
          f"within-shape pair's position, which for a long chord is far from "
          f"either endpoint); seats join by building ref, never by way id")
    if args.rows:
        try:
            ctl_rows, arm_rows = (load_rows(args.rows[0]),
                                  load_rows(args.rows[1]))
        except SiteReadRefusal as exc:
            print(f"REFUSED: {exc}", file=sys.stderr)
            return 2
        out["sites"] = {}
        for name, (lat, lon) in sites.items():
            c = rows_near(ctl_rows, lat, lon, args.radius)
            a = rows_near(arm_rows, lat, lon, args.radius)
            out["sites"][name] = {"control": c, "arm": a}
            print(f"  {name:24s} rows {c['n_rows']:4d} → {a['n_rows']:4d}   "
                  f"worst grade {c['worst_grade_pct']:7.2f}% → "
                  f"{a['worst_grade_pct']:7.2f}%   worst |de| "
                  f"{c['worst_magnitude_m']:6.2f} → "
                  f"{a['worst_magnitude_m']:6.2f} m")
    elif sites:
        print("  SKIPPED site rows: no --rows dumps given (a census "
              "--rows-json dump per arm is this read's only row source)")
    if args.welds:
        cg = _check_grade()
        out["welds"] = {}
        scope = (sites if sites
                 else {"WHOLE PATCH": (None, None)})
        print(f"  SEAM WELDS (road family {'/'.join(ROAD_FAMILY_ROLES)} ↔ "
              f"airside; a shared NODE is the weld, row absence is not "
              f"evidence; mouth cluster {MOUTH_CLUSTER_M:g} m"
              + (f", r={args.radius:g} m" if sites else ", whole patch")
              + ")")
        for name, (lat, lon) in scope.items():
            rad = args.radius if sites else None
            c = seam_welds(cg, args.control, lat, lon, rad)
            a = seam_welds(cg, args.arm, lat, lon, rad)
            out["welds"][name] = {"control": c, "arm": a}
            for label, r in (("ctl", c), ("arm", a)):
                gap = ("—" if r["nearest_unwelded_m"] is None
                       else f"{r['nearest_unwelded_m']:.3f} m")
                print(f"    {name:22s} {label}  shared "
                      f"{r['shared_nodes']:4d}  mouths {r['mouths']:3d} "
                      f"({r['mouths_ge2_nodes']} with ≥2)  max seam |Δalt| "
                      f"{r['max_seam_dalt_m']:6.3f} m  nearest unwelded "
                      f"{gap:>9s}  walls {r['walls']:3d}")
    if args.profile and sites:
        cg = _check_grade()
        roles = tuple(r.strip() for r in args.profile_roles.split(",")
                      if r.strip())
        out["profiles"] = {}
        print(f"  STATION PROFILES (roles {'/'.join(roles)}, r="
              f"{args.radius:g} m, amplitude window {AMP_WINDOW_M:g} m "
              f"along the ring).  NOT defect counts — arm to arm only.")
        for name, (lat, lon) in sites.items():
            c = station_profiles(cg, args.control, lat, lon, args.radius,
                                 roles=roles)
            a = station_profiles(cg, args.arm, lat, lon, args.radius,
                                 roles=roles)
            out["profiles"][name] = {"control": c, "arm": a}
            print(f"    {name}")
            if not c and not a:
                print("      (no ring of these roles reaches this site "
                      "in EITHER arm)")
            for label, rows in (("ctl", c), ("arm", a)):
                if not rows:
                    print(f"      {label}  (no ring reaches the site)")
                for r in rows:
                    print(f"      {label}  way {r['way']:<9} "
                          f"{r['role']:<13} n={r['n_stations']:<4} "
                          f"run {r['run_m']:7.1f} m  worst edge "
                          f"{_fmt(r['worst_step_m'])} m over "
                          f"{_fmt(r['worst_step_len_m'])} m = "
                          f"{_fmt(r['worst_step_pct'])} %  amp"
                          f"{AMP_WINDOW_M:g} {_fmt(r['amp_m'])} m")
    elif args.profile:
        print("  SKIPPED profiles: --profile needs at least one --site")
    if args.line:
        cg = _check_grade()
        roles = tuple(r.strip() for r in args.profile_roles.split(",")
                      if r.strip())
        out["lines"] = {}
        print(f"  OWNER LINES (roles {'/'.join(roles)}, corridor ±"
              f"{args.line_corridor_m:g} m).  An EMPTY station list is "
              f"the finding: no emitted vertex lies along the line.")
        for spec in args.line:
            try:
                name, coords = spec.split("=", 1)
                p, q = coords.split(":", 1)
                a_ll = tuple(float(v) for v in p.split(","))
                b_ll = tuple(float(v) for v in q.split(","))
            except ValueError:
                print("REFUSED: --line wants NAME=LAT,LON:LAT,LON",
                      file=sys.stderr)
                return 2
            c = line_profile(cg, args.control, a_ll, b_ll,
                             corridor_m=args.line_corridor_m, roles=roles)
            a = line_profile(cg, args.arm, a_ll, b_ll,
                             corridor_m=args.line_corridor_m, roles=roles)
            out["lines"][name] = {"control": c, "arm": a}
            print(f"    {name}  ({c['line_m']:.1f} m)")
            for label, r in (("ctl", c), ("arm", a)):
                print(f"      {label}  stations {r['n_stations']:4d}  alt "
                      f"{_fmt(r['alt_min'])}..{_fmt(r['alt_max'])} m  "
                      f"worst step {_fmt(r['worst_step_m'])} m over "
                      f"{_fmt(r['worst_step_len_m'])} m = "
                      f"{_fmt(r['worst_step_pct'])} %  at station "
                      f"{_fmt(r['worst_step_at_m'])} m")
    if args.seats:
        cg = _check_grade()
        out["seats"] = seat_moves(cg, args.control, args.arm)
        s = out["seats"]
        print(f"  PAD SEATS: {s['pads_moved']} of {s['pads_joined']} moved "
              f"> {s['floor_m']} m; median |Δ| {s['median_abs_delta_m']:.2f} m,"
              f" max {s['max_abs_delta_m']:.2f} m")
        for m in s["worst"][:5]:
            print(f"      {m['ref']:16s} {m['ctl_m']:8.2f} → {m['arm_m']:8.2f}"
                  f"  Δ{m['delta_m']:+.2f} m")
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(out, indent=2))
        print(f"  -> {args.json_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
