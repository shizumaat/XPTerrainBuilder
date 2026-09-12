"""§16c (5): THE TORN-SEAM CENSUS (spec ``object-placement-spec.md``
§16c; owner RULINGS 2026-09-12b/12d).

The instrument the §16c bar is read on, and the only census that opens
the WRITTEN files rather than the plan's own rows: two sibling files of
one placement that share an AUTHORED VERTEX are two halves of one
connected solid, written at two zeros.  It lives apart from
``placement_census`` for the 1,000-line law only; both tools import it
through that module, which re-exports it.

NO LAW CONSTANT LIVES HERE except the seam step tolerance the report
prints its histogram against.
"""
from __future__ import annotations

import typing as _t

from . import anchor_rule as _ar

__all__ = ["census_torn_seams", "census_torn_seams_lines", "SEAM_STEP_TOL_M"]


#: §16c (5): a seam whose base step exceeds this is counted apart — the
#: step the eye reads as a break in a continuous surface.
SEAM_STEP_TOL_M = 0.30

#: §16c (1): the ONLY station cuts, and so the only sibling files allowed
#: to share an authored vertex.  A line segment is classed
#: ``anchor_rule.LINE_SEGMENT``; a basin arc piece names its arc in the
#: anchor reason (``basin_ring.arc_anchor``).
_ARC_REASON = "basin rim arc"


def _seam_kind(a: _t.Mapping[str, _t.Any], b: _t.Mapping[str, _t.Any]) -> str:
    """The CLASS of one seam: ``arc`` / ``line`` where §10's or §14a's
    station cut made the pair (lawful, reported apart), else the two
    bodies' own §6 class, or ``mixed``."""
    for r in (a, b):
        if (r.get("anchor_reason") or "").startswith(_ARC_REASON):
            return "arc"
    for r in (a, b):
        if r.get("class") == _ar.LINE_SEGMENT:
            return "line"
    ca, cb = a.get("class") or "?", b.get("class") or "?"
    return ca if ca == cb else "mixed"


def _authored_vertices(path: str, offset: _t.Sequence[float]
                       ) -> "set[tuple[int, int, int]]":
    """The AUTHORED vertex keys of one written body file: its ``VT`` rows
    with ``authored_offset`` added back, to the millimetre — the same key
    ``obj8.solid_components`` welds on, so two files of one component
    meet on it."""
    out: set[tuple[int, int, int]] = set()
    try:
        fh = open(path, encoding="latin-1", errors="replace")
    except OSError:
        return out
    with fh:
        for line in fh:
            if not line.startswith("VT"):
                continue
            t = line.split()
            if len(t) < 4:
                continue
            try:
                out.add((int(round((float(t[1]) + offset[0]) * 1000.0)),
                         int(round((float(t[2]) + offset[1]) * 1000.0)),
                         int(round((float(t[3]) + offset[2]) * 1000.0))))
            except ValueError:
                continue
    return out


def census_torn_seams(splits: _t.Sequence[_t.Mapping[str, _t.Any]],
                      pack_root: str, *,
                      step_tol_m: float = SEAM_STEP_TOL_M,
                      worst: int = 12) -> dict:
    """§16c (5): THE TORN-SEAM CENSUS, over the WRITTEN FILES.

    Two sibling files of ONE placement that share an AUTHORED VERTEX are
    two halves of one connected solid (``obj8.solid_components`` welds on
    exactly that key), written at two zeros: the seam the owner's read of
    1.0.320 found in the `HANG3` vault, in `Bridge2`'s deck and across
    `green-STRT4`'s approach slabs (RULINGS 2026-09-12b/12d).  §16c (1)
    makes the COMPONENT the atom of every group, so the only pairs left
    sharing a vertex are §10's line segments and §14a's basin arcs —
    drape-class by ruling, counted apart here and never in the bar.

    The instrument is the scout `v2lemd320`'s ``tear.py``, promoted on
    its second use (CLAUDE.md tool discipline).  It reads the written
    pack, never the plan's boxes: a file's base plane is
    ``surface_z - y_zero``, so the STEP between two halves of one solid
    is the difference of those, which is what renders.

    Returns the counts, the step histogram, the worst seams and the
    per-class breakdown; ``census_torn_seams_lines`` prints them."""
    import os as _os
    seams: list[dict] = []
    files = 0
    placements = 0
    missing = 0
    for s in splits:
        bodies = [b for b in s.get("bodies", ()) if b.get("new_resource")]
        if len(bodies) < 2:
            files += len(bodies)
            continue
        placements += 1
        verts: list[tuple[_t.Mapping[str, _t.Any], set]] = []
        for b in bodies:
            p = _os.path.join(pack_root, b["new_resource"])
            if not _os.path.isfile(p):
                missing += 1
                continue
            verts.append((b, _authored_vertices(p, b.get("authored_offset")
                                                or (0.0, 0.0, 0.0))))
        files += len(verts)
        res = (s.get("placement") or {}).get("resource", "?")
        for i in range(len(verts)):
            for j in range(i + 1, len(verts)):
                a, va = verts[i]
                b, vb = verts[j]
                shared = va & vb
                if not shared:
                    continue
                za = float(a.get("surface_z") or 0.0) - float(a.get("y_zero") or 0.0)
                zb = float(b.get("surface_z") or 0.0) - float(b.get("y_zero") or 0.0)
                seams.append({"resource": res, "a": a.get("body_id"),
                              "b": b.get("body_id"), "shared": len(shared),
                              "step": za - zb, "kind": _seam_kind(a, b)})
    station = [x for x in seams if x["kind"] in ("line", "arc")]
    rigid = [x for x in seams if x["kind"] not in ("line", "arc")]
    def _hist(rows):
        h: dict[str, int] = {}
        for x in rows:
            d = abs(x["step"])
            k = ("0.00-0.05" if d < 0.05 else "0.05-0.30" if d < 0.30
                 else "0.30-1.00" if d < 1.0 else "1.00-3.00" if d < 3.0
                 else ">3.00")
            h[k] = h.get(k, 0) + 1
        return h
    by_class: dict[str, int] = {}
    for x in rigid:
        by_class[x["kind"]] = by_class.get(x["kind"], 0) + 1
    torn_bodies = {(x["resource"], x["a"]) for x in rigid} | \
                  {(x["resource"], x["b"]) for x in rigid}
    return {
        "files_read": files, "placements_read": placements,
        "files_missing": missing,
        "seams": len(seams), "rigid_seams": len(rigid),
        "station_seams": len(station),
        "rigid_seams_gt": sum(1 for x in rigid if abs(x["step"]) > step_tol_m),
        "station_seams_gt": sum(1 for x in station
                                if abs(x["step"]) > step_tol_m),
        "step_tol_m": step_tol_m,
        "bodies_on_a_torn_seam": len(torn_bodies),
        "hist": _hist(rigid), "station_hist": _hist(station),
        "by_class": by_class,
        "worst": [(x["step"], x["resource"], x["a"], x["b"], x["shared"])
                  for x in sorted(rigid, key=lambda y: -abs(y["step"]))[:worst]],
        "station_worst": [(x["step"], x["resource"], x["a"], x["b"], x["shared"])
                          for x in sorted(station,
                                          key=lambda y: -abs(y["step"]))[:4]],
    }


def census_torn_seams_lines(c: _t.Mapping[str, _t.Any]) -> list[str]:
    """:func:`census_torn_seams`'s bar as the lines both tools print."""
    n = c["rigid_seams"]
    out = [f"   §16c (5) TORN SEAMS on the WRITTEN files "
           f"({c['files_read']} file(s) of {c['placements_read']} multi-body "
           f"placement(s)"
           + (f", {c['files_missing']} not written" if c["files_missing"] else "")
           + "):",
           f"   §16c torn seams OUTSIDE line/arc pieces: {n} (bar 0; "
           f"{c['rigid_seams_gt']} with a step > {c['step_tol_m']:g} m; "
           f"{c['bodies_on_a_torn_seam']} body(ies) on one)"
           + ("" if not n else "   *** §16c (1) VIOLATED (bar 0) ***"),
           "      step histogram: "
           + (", ".join(f"{k} {v}" for k, v in sorted(c["hist"].items())) or "-")
           + "; by class: "
           + (", ".join(f"{k} {v}" for k, v in sorted(c["by_class"].items())) or "-"),
           f"   §16c line/arc station pieces (§10 / §14a, LAWFUL, counted "
           f"apart): {c['station_seams']} seam(s), {c['station_seams_gt']} over "
           f"{c['step_tol_m']:g} m; "
           + (", ".join(f"{k} {v}" for k, v
                        in sorted(c["station_hist"].items())) or "-")]
    for st, res, a, b, sh in c.get("worst", ()):
        out.append(f"      {st:+8.2f} m  {a}<->{b} ({sh} shared)  {res}")
    return out
