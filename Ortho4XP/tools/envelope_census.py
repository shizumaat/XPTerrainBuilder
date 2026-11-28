"""THE BUILDING CENSUS (library of ``tools/underside_census.py --buildings``;
spec ``docs/specs/building-envelope-20261127.md`` §10 stop 0, owner RULINGS
2026-11-27h): the separately seated buildings of
``auto_patch_v2/airport/building_split`` read off one capture pickle --
from the placed TRIANGLES of every solid piece (``unit_underside._Placer``)
-- against today's population: walled clusters, bodies, groups and the
partition's contact edges.  Per cell choice (``footprint_touch_m`` 0.5 m,
8-linked; 0.25 m with a two-cell link) the spec §1 table rows, and every
today's walled cluster that does not map one-to-one onto a building, with
its coordinates and the NAMED reason (different anchors / stacked floors
of one plan / joined by a roofed enclosure, a spanning sheet or one
placement's touching pieces / walls within the lattice band / today's
outline rings touch where the triangles do not / joined today through a
leaf).  Reads only; builds nothing."""
from __future__ import annotations

import collections
import math
import pickle
import time
import typing as _t

import numpy as np

#: today's walled cluster pieces less than this apart in their rings
TOUCH_M = 0.5


def piece_table(airport, law, cache):
    """``(PieceTable, info)`` of every solid piece of ``airport``'s
    partition (line and scatter out), its triangles placed by
    ``unit_underside._Placer`` and lifted to one vertical frame by the DEM
    at the unit's anchor; ``info`` per table row ``(unit index, member
    index, Part)``."""
    from auto_patch_v2.airport.building_split import PieceTable
    from auto_patch_v2.airport.placement_family import member_is_bridge_deck, member_is_deck
    from auto_patch_v2.airport.underside_composite import dem_many
    from auto_patch_v2.airport.unit_underside import _law, _Placer
    ny, band, _storey, _wall = _law(law)
    to_xy = airport.frame.entry()
    placer = _Placer(cache, to_xy, ny, band)
    part = airport.partition
    many = dem_many(airport.dem)
    ax = np.array([to_xy(u.anchor[1], u.anchor[0]) for u in part.units], dtype=float)
    gz = np.asarray(many(ax[:, 0], ax[:, 1]), dtype=float) if len(ax) else np.zeros(0)
    gz = np.where(np.isfinite(gz), gz, 0.0)
    rows, tx, tt, to, info = [], [], [], [], []
    mix = 0
    for ui, u in enumerate(part.units):
        off = float(gz[ui]) + float(u.agl_m or 0.0)
        for mi, m in enumerate(u.members):
            deck, bridge = member_is_deck(m), member_is_bridge_deck(u, m)
            for p in m.parts:
                if p.line or p.scatter:
                    continue
                got = placer.placed(m, p)
                k = len(rows)
                if got is not None and len(got[0]):
                    tr = got[0]
                    tx.append(tr[:, :, :2])
                    tt.append(tr[:, :, 2].max(1) + off)
                    to.append(np.full(len(tr), k, dtype=np.int64))
                    ytop, ylo = float(tr[:, :, 2].max()), float(tr[:, :, 2].min())
                else:
                    ytop = ylo = float(p.base_y)
                rows.append((p.pid, mix, ui, float(p.height_m or 0.0), deck, bridge,
                             bool(p.feet), ytop, ylo + off))
                info.append((ui, mi, p))
            mix += 1
    a = list(zip(*rows)) if rows else [()] * 9
    t = PieceTable(np.asarray(a[0], np.int64), np.asarray(a[1], np.int64),
                   np.asarray(a[2], np.int64), np.asarray(a[3], float),
                   np.asarray(a[4], bool), np.asarray(a[5], bool), np.asarray(a[6], bool),
                   np.asarray(a[7], float), np.asarray(a[8], float),
                   np.concatenate(tx) if tx else np.zeros((0, 3, 2)),
                   np.concatenate(tt) if tt else np.zeros(0),
                   np.concatenate(to) if to else np.zeros(0, np.int64))
    return t, info


def _ll(airport, e: float, n: float) -> tuple[float, float]:
    la, lo = airport.frame.transformers()[1](e, n)
    return round(float(la), 6), round(float(lo), 6)


def _shape(p, ml: float, mo: float):
    """One piece's plan as today's chain reads it: its outline rings as
    raw LINEWORK (a self-intersecting ring's every edge counts, as
    ``placement_contact.rings_touch`` reads it) with the area they close;
    its box where it has none."""
    import shapely
    from shapely.geometry import LineString, box as _box
    from auto_patch_v2.airport.contents import _poly
    gs = [LineString([(b * mo, a * ml) for a, b in list(r) + [r[0]]])
          for r in p.rings or () if len(r) >= 3]
    a = _poly(p.rings or (), [p.box], ml, mo)
    if a is not None:
        gs.append(a)
    if not gs:
        b = p.box
        gs = [_box(b[1] * mo, b[0] * ml, b[3] * mo, b[2] * ml)]
    return shapely.union_all(gs)


def _rings_apart(info_of: dict, pa: list, pb: list, ml: float, mo: float) -> float:
    """The least plan distance (m) between the pieces ``pa`` and ``pb`` as
    today's chain reads them (:func:`_shape`)."""
    import shapely
    ga = [_shape(info_of[q], ml, mo) for q in pa if q in info_of]
    gb = [_shape(info_of[q], ml, mo) for q in pb if q in info_of]
    if not ga or not gb:
        return math.inf
    return float(shapely.union_all(ga).distance(shapely.union_all(gb)))


def _gap(cs, info_of: dict, ml: float, mo: float) -> float:
    """The widest gap (m) that joins the clusters ``cs`` into one, as
    today's chain reads their pieces (:func:`_shape`): the largest of each
    cluster's least distance to the others."""
    import shapely
    gs = [shapely.union_all([_shape(info_of[q], ml, mo) for q in c.pids if q in info_of])
          for c in cs]
    worst = 0.0
    for k, g in enumerate(gs):
        rest = shapely.union_all(gs[:k] + gs[k + 1:])
        worst = max(worst, float(g.distance(rest)))
    return worst


def _leaf_why(c, s, table) -> str:
    """Why a cluster today joined through a leaf is two buildings here:
    its leaf with the most cells in two buildings, what it is and the
    share of the smaller (itself or the building) it holds over each."""
    from auto_patch_v2.airport.building_split import _intervals
    from auto_patch_v2.geom import plan_lattice as _pl
    t, row_of = table
    bcells = {b.id: b.cells for b in s.buildings}
    best = None
    for q in c.pids:
        k = row_of.get(q)
        if k is None or s.kind.get(q) == "wall":
            continue
        sel = np.zeros(len(t), dtype=bool)
        sel[k] = True
        _p, i, a, b, _tp = _intervals(t, sel, s.params.cell_m)
        _g, i, a, b = _pl.merge_runs(np.zeros(len(i), np.int64), i, a, b)
        qq, r, n = _pl.overlaps(i, a, b, s.runs[:, 0], s.runs[:, 1], s.runs[:, 2])
        tot = int((b - a + 1).sum())
        per = collections.Counter()
        for bid, m in zip(s.runs[r, 3].tolist(), n.tolist()):
            per[bid] += m
        if len(per) < 2:
            continue
        two = per.most_common(2)
        fr = [m / max(min(tot, bcells.get(bid, 1)), 1) for bid, m in two]
        key = min(fr)
        if best is None or key > best[0]:
            what = ("deck" if t.deck[k] else "footed" if t.footed[k]
                    else "below grade" if t.top_authored[k] < -s.params.below_m else "sheet")
            best = (key, f"leaf {q} ({what}, {tot} cells) holds {fr[0]:.2f}/{fr[1]:.2f} "
                         f"of the smaller over two buildings")
    return ("joined today through a leaf over two walled BODIES: " + best[1]) if best else ""


def _body_touch(c, s, info_of, ml: float, mo: float) -> str:
    """The closest pair of today's cluster pieces on the two sides of the
    split (the first building's pieces against the rest), as today's chain
    reads them (:func:`_shape`), and what each is here."""
    import shapely
    bs = sorted({s.of[q] for q in c.pids if s.kind.get(q) == "wall"})
    ga = {q: _shape(info_of[q], ml, mo) for q in c.pids
          if q in info_of and s.of.get(q) == bs[0]}
    gb = {q: _shape(info_of[q], ml, mo) for q in c.pids
          if q in info_of and s.of.get(q) != bs[0]}
    if not ga or not gb:
        return ""
    keys = list(gb)
    tree = shapely.STRtree([gb[k] for k in keys])
    best = None
    for q, g in ga.items():
        j = int(tree.nearest(g))
        d = float(g.distance(gb[keys[j]]))
        if best is None or d < best[0]:
            best = (d, q, keys[j])
    d, a, b = best
    return (f"pieces {a} ({s.kind.get(a, 'exterior')}) and {b} ({s.kind.get(b, 'exterior')}) "
            f"are {d:.2f} m apart by rings")


def mapping(airport, s, law, info, table=None) -> dict:
    """Today's walled clusters against the buildings (module doc): the
    clusters split over buildings and the buildings holding several, each
    with coordinates and a named reason."""
    pl = law.tables.structures.placement
    floor_split = float(getattr(pl, "floor_split_m", 0.5) or 0.5)
    tr = s.counts.get("trace", {})
    wreg = tr.get("wall_region", {})
    rr = tr.get("region_root", [])
    kinds_at = collections.defaultdict(set)
    for kind, a, _b in tr.get("joins", ()):
        kinds_at[rr[a]].add(kind)
    info_of = {p.pid: p for _u, _m, p in info}
    lat0 = airport.frame.origin[0]
    ml, mo = 111320.0, 111320.0 * math.cos(math.radians(lat0))
    walled = [c for c in airport.clusters or () if c.walled and c.pids]
    by_b = collections.defaultdict(list)
    split_rows = []
    for c in walled:
        wp = [q for q in c.pids if s.kind.get(q) == "wall"]
        bs = sorted({s.of[q] for q in wp})
        for b in bs:
            by_b[b].append(c)
        if len(bs) > 1:
            pa = [q for q in wp if s.of[q] == bs[0]]
            pb = [q for q in wp if s.of[q] != bs[0]]
            d = _rings_apart(info_of, pa, pb, ml, mo)
            bare = [q for q in c.pids if q in info_of and not info_of[q].rings]
            why = ("today's outline rings touch where the triangles do not"
                   if d <= TOUCH_M else _leaf_why(c, s, table)
                   or (f"today a piece with no outline ring chains by its lat/lon box "
                       f"(pieces {bare[:3]})" if bare else
                       "today a walled BODY chains on its thin pieces' rings; only walls "
                       "link here (14ah (4)): " + _body_touch(c, s, info_of, ml, mo)))
            la, lo = (c.hull[0] + c.hull[2]) / 2, (c.hull[1] + c.hull[3]) / 2
            split_rows.append({"cluster": c.id, "unit": c.unit, "buildings": bs,
                               "rings_apart_m": round(d, 2), "why": why,
                               "lat": round(la, 6), "lon": round(lo, 6),
                               "area_m2": round(c.area_m2)})
    merged_rows = []
    bmap = {b.id: b for b in s.buildings}
    for b, cs in sorted(by_b.items()):
        if len(cs) < 2:
            continue
        units = {c.unit for c in cs}
        regs = sorted({wreg[q] for c in cs for q in c.pids if q in wreg and s.of.get(q) == b})
        kinds = kinds_at.get(rr[regs[0]], set()) if regs else set()
        floors = [f for c in cs for f in (c.floors or ())]
        gap = _gap(cs, info_of, ml, mo)
        if len(units) > 1:
            why = "different anchors (today's clusters are per anchor)"
        elif len(regs) > 1:
            why = "joined by " + "/".join(sorted(kinds) or ["?"])
        elif floors and max(floors) - min(floors) >= floor_split and _stacked(cs):
            why = "stacked floors of one plan (14x floor split)"
        elif gap > TOUCH_M:
            why = "walls within the lattice band (0.5-1.41 m)"
        else:
            why = ("rings within 0.5 m: one building by footprint_touch_m (14j); today's "
                   "chain left them apart (not traced)")
        bb = bmap[b]
        la, lo = _ll(airport, (bb.box[0] + bb.box[2]) / 2, (bb.box[1] + bb.box[3]) / 2)
        merged_rows.append({"building": b, "clusters": len(cs), "units": len(units),
                            "why": why, "gap_m": round(gap, 2), "area_m2": round(bb.area_m2),
                            "lat": la, "lon": lo,
                            "floors": [round(min(floors), 2), round(max(floors), 2)]
                            if floors else None,
                            "members": sorted({m for c in cs for m in c.members})[:4]})
    return {"split": split_rows, "merged": merged_rows}


def _stacked(cs) -> bool:
    """Do two of these clusters' hulls overlap in plan (one footprint)?"""
    hs = [c.hull for c in cs]
    for a in range(len(hs)):
        for b in range(a + 1, len(hs)):
            p, q = hs[a], hs[b]
            if p[0] < q[2] and q[0] < p[2] and p[1] < q[3] and q[1] < p[3]:
                return True
    return False


def folded(airport, s) -> dict:
    """Today's bodies, groups and clusters whose every part is in a
    building; the contact edges inside one building."""
    from auto_patch_v2.airport.placement_family import bodies_of_plan
    part = airport.partition
    bodies, _of = bodies_of_plan(part)
    inb = s.of
    out = {"bodies": len(bodies),
           "bodies_folded": sum(1 for ps in bodies.values() if ps and all(q in inb for q in ps))}
    grp = getattr(airport, "groups", None)
    if grp is not None:
        gs = list(getattr(grp, "groups", ()) or ())
        out["groups"] = len(gs)
        out["groups_folded"] = sum(
            1 for g in gs if (ps := [q for b in g.bodies for q in bodies.get(tuple(b), ())])
            and all(q in inb for q in ps))
    cl = list(airport.clusters or ())
    out["clusters"] = len(cl)
    out["clusters_folded"] = sum(1 for c in cl if c.pids and all(q in inb for q in c.pids))
    c = np.asarray(part.contacts or (), dtype=np.int64).reshape(-1, 2)
    ba = np.array([inb.get(int(a), -1) for a in c[:, 0]]) if len(c) else np.zeros(0)
    bb = np.array([inb.get(int(b), -1) for b in c[:, 1]]) if len(c) else np.zeros(0)
    out["contacts"] = int(len(c))
    out["contacts_in_one_building"] = int(((ba >= 0) & (ba == bb)).sum())
    out["contacts_between_buildings"] = int(((ba >= 0) & (bb >= 0) & (ba != bb)).sum())
    return out


def census_one(airport, law, cache, fine: bool = False) -> dict:
    """One capture's census at one cell choice (module doc)."""
    from auto_patch_v2.airport.building_split import Params, split
    t0 = time.perf_counter()
    t, info = piece_table(airport, law, cache)
    t_place = time.perf_counter() - t0
    s = split(t, Params.from_law(law, fine=fine), contacts=airport.partition.contacts,
              trace=True)
    part = airport.partition
    allp = [p for u in part.units for m in u.members for p in m.parts]
    area = np.array([b.area_m2 for b in s.buildings])
    kinds = collections.Counter(s.kind.values())
    n_solid = len(t)
    held = set(s.of)
    ext = n_solid - len(held)
    row = {"cell_m": s.params.cell_m, "link": s.params.link,
           "pieces": len(allp), "line": sum(1 for p in allp if p.line),
           "scatter": sum(1 for p in allp if p.scatter and not p.line),
           "solid": n_solid, "wall": kinds.get("wall", 0),
           "interior": kinds.get("interior", 0), "sheet": kinds.get("sheet", 0),
           "attached": kinds.get("attached", 0), "exterior": ext,
           "buildings": len(s.buildings), "buildings_100m2": int((area >= 100).sum()),
           "buildings_5000m2": int((area >= 5000).sum()),
           "buildings_multi_anchor": sum(1 for b in s.buildings if len(b.anchors) > 1),
           "triangles": int(len(t.tri_owner)),
           "seconds_place": round(t_place, 1), "seconds_split": s.counts["seconds"],
           "counts": {k: v for k, v in s.counts.items() if k != "trace"}}
    row.update(folded(airport, s))
    row.update(mapping(airport, s, law, info, (t, {int(p): k for k, p in enumerate(t.pid)})))
    big = sorted(s.buildings, key=lambda b: -b.area_m2)[:5]
    row["largest"] = [{"building": b.id, "area_m2": round(b.area_m2), "anchors": len(b.anchors),
                       "members": len(b.members),
                       "at": _ll(airport, (b.box[0] + b.box[2]) / 2, (b.box[1] + b.box[3]) / 2)}
                      for b in big]
    return row


def from_capture(path: str, fine_too: bool = True) -> dict:
    """:func:`census_one` of one capture at both cell choices."""
    from auto_patch_v2.airport import frame_entry as _fe
    from auto_patch_v2.airport.obj8 import ResourceCache
    from auto_patch_v2.law import Law
    with open(path, "rb") as fh:
        cap = pickle.load(fh)
    icao, airport = cap["icao"], cap["airport"]
    del cap
    law = Law.for_airport(icao)
    cache = ResourceCache(law.tables.structures.basin.min_solid_thickness_m, _fe.quantum(law))
    rows = [census_one(airport, law, cache)]
    if fine_too:
        rows.append(census_one(airport, law, cache, fine=True))
    return {"icao": icao, "path": path, "rows": rows}


_TABLE = ("pieces", "line", "scatter", "solid", "wall", "interior", "sheet", "attached",
          "exterior", "buildings", "buildings_100m2", "buildings_5000m2",
          "buildings_multi_anchor", "bodies", "bodies_folded", "groups", "groups_folded",
          "clusters", "clusters_folded", "contacts", "contacts_in_one_building",
          "contacts_between_buildings", "seconds_place", "seconds_split")


def lines(results: list[dict], certified: _t.Collection[str] = ()) -> list[str]:
    """The §1 table (one column per capture and cell) and, for the
    ``certified`` ICAOs, every non-one-to-one cluster with its reason."""
    cols = [(r["icao"], x) for r in results for x in r["rows"]]
    out = [f"{'':28}" + "".join(f"{i + '@' + str(x['cell_m']):>13}" for i, x in cols)]
    for k in _TABLE:
        out.append(f"{k:28}" + "".join(f"{x.get(k, ''):>13}" for _i, x in cols))
    out.append(f"{'today split over buildings':28}"
               + "".join(f"{len(x['split']):>13}" for _i, x in cols))
    out.append(f"{'buildings holding 2+':28}"
               + "".join(f"{len(x['merged']):>13}" for _i, x in cols))
    for i, x in cols:
        why = collections.Counter(r["why"].split(":")[0].split(" (pieces")[0]
                                  for r in x["merged"] + x["split"])
        out.append(f"  {i}@{x['cell_m']} reasons: " + "; ".join(f"{w} {n}" for w, n in
                                                            sorted(why.items())))
        out.append(f"  {i}@{x['cell_m']} largest: " + "; ".join(
            f"b{b['building']} {b['area_m2']} m2 anchors {b['anchors']} @{b['at'][0]},{b['at'][1]}"
            for b in x["largest"]))
        if i not in certified:
            continue
        for r in x["split"]:
            out.append(f"    SPLIT {r['cluster']} ({r['unit']}) into {r['buildings']} "
                       f"rings {r['rings_apart_m']} m: {r['why']} @{r['lat']},{r['lon']}")
        for r in x["merged"]:
            out.append(f"    MERGED b{r['building']} holds {r['clusters']} clusters of "
                       f"{r['units']} unit(s), {r['area_m2']} m2, floors {r['floors']}, "
                       f"gap {r['gap_m']} m: {r['why']} @{r['lat']},{r['lon']} "
                       f"{','.join(r['members'])[:70]}")
    return out
