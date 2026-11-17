"""THE ROLE-FLIP CENSUS of a dry reclassify (#2134; helper of
``v2_solve_replay.py --reclassify --roles-out / --roles-against``).

A classify change moves pavement between roles.  The question a lane and
the owner ask is WHAT MOVED, WHERE: which cells left ``apron`` (or became
it), by how much area, into which role, and on which minting rule.  The
classification of two trees cannot live in one process, so the census is
two halves:

* :func:`dump` writes the cells of one run (role, ref, letter, ring and
  holes in the frame, evidence) with the frame's lat/lon of a point on
  each — run on the BASE tree first;
* :func:`report` reads that dump against the cells of the current run and
  prints the apron table: base apron area, how much of it now carries each
  other role (an AREA overlay, so a cell cut differently is still read),
  the flips by the base cell's minting rule, the largest flips by area
  with their lat, lon, and the cells that BECAME apron.

``protect`` names refs that must stay apron (an owner-ruled apron): any of
their base area that leaves ``apron`` is printed as a PROTECTED FLIP.
Writes nothing but the dump and the ``--json`` the caller asks for.
"""
from __future__ import annotations

import pickle
import typing as _t
from pathlib import Path

__all__ = ["dump", "report", "minting_rule"]

#: the evidence keys a cell's minting rule is read from, first match wins
_RULES = (
    ("user_role", "user override"),
    ("startup_refused_corridor", "1300 startup on the cell"),
    ("apron_cover_refused_corridor", "§40 (2) OSM cover"),
    ("airside_edge_flip", "§27 airside edge"),
    ("gap_apron", "§59 gap apron"),
    ("neck_new_apron", "§43 beyond a neck"),
)


def minting_rule(evid: _t.Mapping[str, object]) -> str:
    """The rule that made an apron cell apron, read off its evidence."""
    for key, name in _RULES:
        if evid.get(key):
            return name
    why = evid.get("apron_witness") or evid.get("apron_evidence")
    if why:
        return f"04u: {why}"
    return "kind default"


def _rows(cells, to_ll) -> list[dict]:
    from shapely.geometry import Polygon
    out = []
    for c in cells:
        poly = Polygon(c.ring, c.holes)
        if poly.is_empty:
            continue
        p = poly.representative_point()
        lat, lon = to_ll(p.x, p.y)
        out.append({"role": c.role, "ref": c.ref, "letter": c.code_letter,
                    "kind": c.kind, "ring": tuple(c.ring), "holes": tuple(c.holes),
                    "area": poly.area, "lat": lat, "lon": lon,
                    "evidence": dict(c.evidence)})
    return out


def dump(cells, to_ll, path: Path) -> None:
    """Write the cells of one classify run to ``path`` (a pickle)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as fh:
        pickle.dump(_rows(cells, to_ll), fh)


def _polys(rows):
    from shapely.geometry import Polygon
    from shapely.strtree import STRtree
    polys = [Polygon(r["ring"], r["holes"]).buffer(0) for r in rows]
    return polys, STRtree(polys)


def _overlay(poly, tree, polys, rows) -> dict[str, float]:
    """The area of ``poly`` each role of ``rows`` covers."""
    got: dict[str, float] = {}
    for j in tree.query(poly, predicate="intersects"):
        a = poly.intersection(polys[int(j)]).area
        if a > 0.0:
            role = rows[int(j)]["role"]
            got[role] = got.get(role, 0.0) + a
    return got


def _verdict(rows, tree, polys, poly) -> str:
    """The verdict key the largest cell of ``rows`` over ``poly`` carries."""
    best, area = None, 0.0
    for j in tree.query(poly, predicate="intersects"):
        a = poly.intersection(polys[int(j)]).area
        if a > area:
            best, area = rows[int(j)], a
    if best is None:
        return ""
    ev = best["evidence"]
    return str(ev.get("apron_verdict") or ev.get("unclassified_default")
               or ev.get("kind") or "")


def _moves(src_rows, src_polys, dst_rows, dst_tree, dst_polys, role):
    """Per ``role`` row of ``src_rows``, the area of it ``dst_rows`` gives
    another role: ``(row, poly, {role: m2})`` where any moved."""
    out = []
    for r, poly in zip(src_rows, src_polys, strict=True):
        if r["role"] != role:
            continue
        moved = {k: v for k, v in _overlay(poly, dst_tree, dst_polys, dst_rows).items()
                 if k != role}
        if moved:
            out.append((r, poly, moved))
    return out


def report(base_path: Path, cells, to_ll, *, role: str = "apron", top: int = 10,
           protect: _t.Iterable[str] = ()) -> dict:
    """Print and return the flip table of ``role`` between the dump at
    ``base_path`` and ``cells`` (this run)."""
    with base_path.open("rb") as fh:
        base = pickle.load(fh)
    new = _rows(cells, to_ll)
    bpolys, btree = _polys(base)
    npolys, ntree = _polys(new)
    flips, by_role, by_rule = [], {}, {}
    for r, poly, moved in _moves(base, bpolys, new, ntree, npolys, role):
        m = sum(moved.values())
        rule = minting_rule(r["evidence"])
        for k, v in moved.items():
            by_role[k] = by_role.get(k, 0.0) + v
        cnt, area = by_rule.get(rule, (0, 0.0))
        by_rule[rule] = (cnt + int(m >= 0.5 * r["area"]), area + m)
        flips.append({"ref": r["ref"], "lat": round(r["lat"], 6), "lon": round(r["lon"], 6),
                      "m2": round(m), "cell_m2": round(r["area"]),
                      "to": max(moved, key=moved.get), "rule": rule,
                      "why_new": _verdict(new, ntree, npolys, poly)})
    flips.sort(key=lambda f: -f["m2"])
    gains = [{"ref": r["ref"], "lat": round(r["lat"], 6), "lon": round(r["lon"], 6),
              "m2": round(sum(moved.values())), "from": max(moved, key=moved.get),
              "why_new": str(r["evidence"].get("apron_verdict", ""))}
             for r, _p, moved in _moves(new, npolys, base, btree, bpolys, role)]
    gains.sort(key=lambda f: -f["m2"])
    prot = set(protect)
    brole = [r for r in base if r["role"] == role]
    nrole = [r for r in new if r["role"] == role]
    res = {"base_cells": len(brole), "base_m2": round(sum(r["area"] for r in brole)),
           "new_cells": len(nrole), "new_m2": round(sum(r["area"] for r in nrole)),
           "flipped_cells": sum(1 for f in flips if f["m2"] >= 0.5 * f["cell_m2"]),
           "flipped_m2": round(sum(f["m2"] for f in flips)),
           "flipped_by_role": {k: round(v) for k, v in sorted(by_role.items(),
                                                              key=lambda kv: -kv[1])},
           "flipped_by_rule": {k: {"cells": c, "m2": round(a)} for k, (c, a) in
                               sorted(by_rule.items(), key=lambda kv: -kv[1][1])},
           "gained_m2": round(sum(g["m2"] for g in gains)),
           "flips": flips, "gains": gains,
           "protected_flips": [f for f in flips if f["ref"] in prot],
           "protected_kept": sorted({r["ref"] for r in nrole} & prot)}
    print(f"  {role}: base {res['base_cells']} cells {res['base_m2']:,} m2 -> "
          f"{res['new_cells']} cells {res['new_m2']:,} m2; left {role} "
          f"{res['flipped_m2']:,} m2 ({res['flipped_cells']} cells >= half), "
          f"gained {res['gained_m2']:,} m2")
    print("  left to: " + ", ".join(f"{k} {v:,}" for k, v in res["flipped_by_role"].items()))
    print("  by base rule: " + "; ".join(f"{k} {v['cells']}/{v['m2']:,}"
                                         for k, v in res["flipped_by_rule"].items()))
    for f in flips[:top]:
        print(f"    {f['lat']:.6f}, {f['lon']:.6f}  {f['ref']:<16} {f['m2']:>9,} m2 "
              f"of {f['cell_m2']:>9,} -> {f['to']:<20} [{f['rule']}] {f['why_new']}")
    for g in gains[:top]:
        print(f"    GAINED {g['lat']:.6f}, {g['lon']:.6f}  {g['ref']:<16} "
              f"{g['m2']:>9,} m2 from {g['from']} {g['why_new']}")
    for f in res["protected_flips"]:
        print(f"    PROTECTED FLIP {f['ref']} {f['m2']:,} m2 -> {f['to']}")
    return res
