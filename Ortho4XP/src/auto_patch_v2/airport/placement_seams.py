"""THE CENSUSES THAT OPEN THE WRITTEN FILES (spec
``object-placement-spec.md`` §16c / §16d; owner RULINGS 2026-09-12b/12d,
2026-09-13h).

Every other placement census reads the plan's own rows.  These two read
the OBJ8s the writer actually wrote, which is the only frame in which
the plan can be caught disagreeing with the writer:

* §16c (5) THE TORN-SEAM CENSUS — two sibling files of one placement that
  share an AUTHORED VERTEX are two halves of one connected solid written
  at two zeros;
* §16d (1) THE OUTSIDE-BOX CENSUS — a body whose WRITTEN triangles reach
  beyond its own ``geom_box``.  The box is what every instrument reads
  (§15, §16a, §16b); geometry outside it rides a zero the body chose
  somewhere else and NO instrument sees it.

They live apart from ``placement_census`` for the 1,000-line law only;
both tools import them through that module, which re-exports them.

NO LAW CONSTANT LIVES HERE except the two tolerances the reports print
their histograms against.
"""
from __future__ import annotations

import math as _math
import typing as _t

from . import anchor_rule as _ar

__all__ = ["census_torn_seams", "census_torn_seams_lines", "SEAM_STEP_TOL_M",
           "census_outside_box", "census_outside_box_lines", "OUTSIDE_TOL_M"]


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
                       ) -> "set[tuple[float, float, float]]":
    """The AUTHORED vertex keys of one written body file: its ``VT`` rows
    with ``authored_offset`` added back, to the millimetre — the same key
    ``obj8.solid_components`` welds on, so two files of one component
    meet on it."""
    out: set[tuple[float, float, float]] = set()
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
                # THE WELD'S OWN KEY, to the millimetre — ``round(x, 3)``
                # exactly as ``obj8.solid_components`` spells it
                # (``np.round(vertices, 3)``).  Keying on ``round(x *
                # 1000)`` instead disagrees on the half-millimetre
                # boundary and reads two genuinely separate components as
                # one torn solid (measured: OTHH's
                # ``OTHH_Fuel_02_LOD0_007``, the airport's last seam).
                out.add((round(float(t[1]) + offset[0], 3),
                         round(float(t[2]) + offset[1], 3),
                         round(float(t[3]) + offset[2], 3)))
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
                # §15 (5): a body whose anchor stands on NO graded face
                # reads no surface here.  The SEAM is still a seam — the
                # solid is torn either way — but its step is not a
                # number this instrument may quote, so it is counted
                # and left out of the histogram and the worst list.
                sa, sb = a.get("surface_z"), b.get("surface_z")
                step = (None if sa is None or sb is None else
                        (float(sa) - float(a.get("y_zero") or 0.0))
                        - (float(sb) - float(b.get("y_zero") or 0.0)))
                seams.append({"resource": res, "a": a.get("body_id"),
                              "b": b.get("body_id"), "shared": len(shared),
                              "step": step, "kind": _seam_kind(a, b)})
    # §16c (5)'s SECOND BAR, read on the written files like the first:
    # a resource whose whole object is ONE connected component written
    # as two or more files.  A partition of a connected solid always
    # leaves a shared authored vertex, so the placements carrying a
    # RIGID seam ARE that class — read from the plan's `components`
    # field instead it is a false positive, because a member the plan
    # records as one PART is written as the whole object (§16b (1)) and
    # its many components all read `components=[0]`.
    station = [x for x in seams if x["kind"] in ("line", "arc")]
    rigid = [x for x in seams if x["kind"] not in ("line", "arc")]
    def _hist(rows):
        h: dict[str, int] = {}
        for x in rows:
            if x["step"] is None:
                h["off-sheet"] = h.get("off-sheet", 0) + 1
                continue
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
        "single_component_multi_file": len({x["resource"] for x in rigid}),
        "station_seams": len(station),
        "rigid_seams_gt": sum(1 for x in rigid if x["step"] is not None
                              and abs(x["step"]) > step_tol_m),
        "station_seams_gt": sum(1 for x in station if x["step"] is not None
                                and abs(x["step"]) > step_tol_m),
        "off_sheet_seams": sum(1 for x in seams if x["step"] is None),
        "step_tol_m": step_tol_m,
        # §17 (the COCKPIT frame): every rigid seam's own step, worst
        # first — the block prices these at [cockpit] visual_m, which is
        # a different number from this census's own ``step_tol_m``, and a
        # count taken at the wrong tolerance is the two-instruments trap.
        "rigid_steps": sorted((abs(x["step"]) for x in rigid
                               if x["step"] is not None), reverse=True),
        "bodies_on_a_torn_seam": len(torn_bodies),
        "hist": _hist(rigid), "station_hist": _hist(station),
        "by_class": by_class,
        "worst": [(x["step"], x["resource"], x["a"], x["b"], x["shared"])
                  for x in sorted((q for q in rigid if q["step"] is not None),
                                  key=lambda y: -abs(y["step"]))[:worst]],
        "station_worst": [(x["step"], x["resource"], x["a"], x["b"], x["shared"])
                          for x in sorted(
                              (q for q in station if q["step"] is not None),
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
           f"{c['bodies_on_a_torn_seam']} body(ies) on one; "
           f"{c.get('off_sheet_seams', 0)} seam(s) off-sheet, step not read)"
           + ("" if not n else "   *** §16c (1) VIOLATED (bar 0) ***"),
           f"   §16c single-component resources in >= 2 files: "
           f"{c.get('single_component_multi_file', 0)} (bar 0)"
           + ("" if not c.get("single_component_multi_file")
              else "   *** §16c (1) VIOLATED (bar 0) ***"),
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


# ── §16d (1): the written triangles against the body's own box ───────────

#: §16d (1): how far outside its own ``geom_box``, in PLAN METRES, a
#: body's written geometry may reach before the box is not a description
#: of the file.  A reporting tolerance, not a law: the box is the hull of
#: the body's own parts to the emitted precision, so a few centimetres of
#: rounding is not a finding and a metre is.
OUTSIDE_TOL_M = 1.0


def _written_latlon(path: str, offset: _t.Sequence[float],
                    lat: float, lon: float, heading_deg: float
                    ) -> "list[tuple[float, float]] | None":
    """Every ``VT`` row of one written body file as ``(lat, lon)``.

    The writer SUBTRACTED ``authored_offset`` from each vertex, so adding
    it back gives the AUTHORED ``(x, y, z)`` the pack's own frame is in,
    and ``placement_cut.authored_latlon`` maps that to the placement's
    ground — the same two lines ``placement_plan.authored_offset``
    inverts, and the same key ``_authored_vertices`` welds on.

    ``None`` where the file carries an ANIM BLOCK.  ``obj8_split`` does
    NOT subtract the offset from a vertex emitted inside one — the block
    is compensated by its own ``ANIM_trans`` instead (rule 4) — so such a
    file's vertex table mixes two frames and no single map reads it.  The
    census counts those bodies apart and NAMES them rather than quoting a
    number it cannot take (KCLT's `-vidrios_paredes_5_charlotte_lit__b0`
    read 604 m of "outside the box" that was the double-counted offset).
    """
    from .placement_cut import authored_latlon
    out: list[tuple[float, float]] = []
    try:
        fh = open(path, encoding="latin-1", errors="replace")
    except OSError:
        return out
    with fh:
        for line in fh:
            if line.startswith("ANIM_begin"):
                return None
            if not line.startswith("VT"):
                continue
            t = line.split()
            if len(t) < 4:
                continue
            try:
                x = float(t[1]) + offset[0]
                z = float(t[3]) + offset[2]
            except (ValueError, IndexError):
                continue
            out.append(authored_latlon(x, z, lat, lon, heading_deg))
    return out


def _outside_m(box: _t.Sequence[float], pts: _t.Sequence[tuple[float, float]],
               ) -> float:
    """The farthest any of ``pts`` lies OUTSIDE ``box``, in plan metres
    (0 where every point is inside).  ``box`` is ``(lat0, lon0, lat1,
    lon1)``, the spelling every plan box carries."""
    if not pts or not box or len(box) < 4:
        return 0.0
    ml, mo = _ar._m_per_deg(0.5 * (float(box[0]) + float(box[2])))
    worst = 0.0
    for la, lo in pts:
        dla = max(float(box[0]) - la, la - float(box[2]), 0.0) * ml
        dlo = max(float(box[1]) - lo, lo - float(box[3]), 0.0) * mo
        d = _math.hypot(dla, dlo)
        if d > worst:
            worst = d
    return worst


def census_outside_box(splits: _t.Sequence[_t.Mapping[str, _t.Any]],
                       pack_root: str, *, tol_m: float = OUTSIDE_TOL_M,
                       worst: int = 12) -> dict:
    """§16d (1): THE WRITTEN GEOMETRY AGAINST THE BODY'S OWN BOX.

    ``geom_box`` was the hull of the ADMITTED PARTS while the writer
    emitted the source object's triangles regardless (RULINGS
    2026-09-13h): a zero-thickness one-sided quad is not admitted, a roof
    plate over another hangar was never boxed, and the geometry then
    rides a zero the body chose somewhere else while §15, §16a and §16b —
    all of which read the BOX — see nothing at all.  At LEMD 1.0.325, 397
    of 2,109 bodies carried geometry more than a metre outside their own
    box, 8 of them over a kilometre.

    This opens the written files and asks the one question that catches
    it: is every written vertex inside the box the plan published for
    this body?  Bar 0 at ``tol_m``.

    Returns the counts, the distance histogram and the worst bodies;
    ``census_outside_box_lines`` prints them."""
    import os as _os
    rows: list[tuple[float, str, str, str]] = []
    files = 0
    missing = 0
    anim = 0
    for s in splits:
        p = s.get("placement") or {}
        lat, lon = p.get("lat"), p.get("lon")
        if lat is None or lon is None:
            continue
        head = float(p.get("heading") or 0.0)
        for b in s.get("bodies", ()) or ():
            res = b.get("new_resource")
            box = b.get("geom_box")
            if not res or not box:
                continue
            path = _os.path.join(pack_root, res)
            if not _os.path.isfile(path):
                missing += 1
                continue
            pts = _written_latlon(path, b.get("authored_offset")
                                  or (0.0, 0.0, 0.0),
                                  float(lat), float(lon), head)
            if pts is None:
                anim += 1
                continue
            files += 1
            d = _outside_m(box, pts)
            if d > 0.01:
                rows.append((d, str(res), str(b.get("class") or "?"),
                             str(b.get("anchor_reason") or "")))
    rows.sort(reverse=True)
    over = [r for r in rows if r[0] > tol_m]
    hist: dict[str, int] = {}
    by_class: dict[str, int] = {}
    for d, _res, cls, _why in over:
        k = ("1-10" if d < 10.0 else "10-100" if d < 100.0
             else "100-1000" if d < 1000.0 else ">1000")
        hist[k] = hist.get(k, 0) + 1
        by_class[cls] = by_class.get(cls, 0) + 1
    return {"files_read": files, "files_missing": missing,
            "files_with_anim": anim,
            "tol_m": tol_m,
            "bodies_outside_box": len(over),
            "bodies_outside_any": len(rows),
            "worst_m": (round(rows[0][0], 3) if rows else 0.0),
            "worst_name": (rows[0][1] if rows else None),
            "hist": hist, "by_class": by_class,
            "worst": [(round(d, 2), res, cls, why[:70])
                      for d, res, cls, why in rows[:worst]]}


def census_outside_box_lines(c: _t.Mapping[str, _t.Any]) -> list[str]:
    """:func:`census_outside_box`'s bar as the lines both tools print."""
    n = int(c.get("bodies_outside_box", 0))
    out = [f"   §16d (1) WRITTEN GEOMETRY OUTSIDE ITS OWN BOX "
           f"({c['files_read']} written file(s)"
           + (f", {c['files_missing']} not written" if c["files_missing"] else "")
           + (f", {c['files_with_anim']} with an ANIM block NOT READ "
              "(two vertex frames in one table)" if c.get("files_with_anim")
              else "")
           + "):",
           f"   §16d bodies with written geometry > {c['tol_m']:g} m outside "
           f"their geom_box: {n} (bar 0; {c.get('bodies_outside_any', 0)} over "
           f"1 cm; worst {c.get('worst_m', 0.0):.2f} m "
           f"{c.get('worst_name') or '-'})"
           + ("" if not n else "   *** §16d (1) VIOLATED (bar 0) ***"),
           "      distance histogram (m): "
           + (", ".join(f"{k} {v}" for k, v in sorted(c["hist"].items())) or "-")
           + "; by class: "
           + (", ".join(f"{k} {v}" for k, v in sorted(c["by_class"].items()))
              or "-")]
    for d, res, cls, why in c.get("worst", ()):
        out.append(f"      {d:9.2f} m  [{cls}] {res}  {why}")
    return out
