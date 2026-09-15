#!/usr/bin/env python3
"""THE OBJ8 SPLIT, DRY-RUN (spec ``object-placement-spec.md`` §4 / §6 / §7).

What a pack's object stage would look like after the switch to AGL
placement with split objects and placed anchors — computed from a build's
own two products and NOTHING ELSE: the re-seat plan
(``<ICAO>.rebake.json`` — the pack read once, its welded parts and the
ε-contact graph) and the emitted DESIGN SURFACE
(``<ICAO>.graded.json``), which is the terrain X-Plane will drape onto.

    venv/bin/python tools/obj8_split_report.py PLAN.json --graded SURFACE.json
        [--write-into DIR] [--json OUT.json] [--top N] [--filter SUBSTR]
        [--rows SUBSTR,SUBSTR] [--rows-near LAT,LON[,R]]
        [--no-cut] [--split-tol M]
    venv/bin/python tools/obj8_split_report.py PLAN.json --graded SURFACE.json
        --write-pack PACK_COPY [--patch-dir DIR] [--dsftool BIN]

``--write-pack`` runs THE WHOLE WRITE HALF (owner RULINGS 2026-09-11e (3),
``airport/placement_write.apply_plan``) into a pack COPY: the cut files
into its ``objects/``, the DSF edited / encoded / VERIFIED with its
``.anchor_bak`` backup and provenance, the text-dump cache refreshed and
``o4_v2_placement_<ICAO>.json`` written into ``--patch-dir``.  It REFUSES
a pack under a live X-Plane install — a lane copies the pack, and only
the app writes the real one.

Per placement it reports the bodies, their §6 CLASSES, each body's anchor
and authored offset, the files that would be written, and the
placements KEPT WHOLE with the reason (§2 ``kept``).  With
``--write-into`` the cut files are written into a scratch directory and
each is parsed back through ``airport/obj8.parse_obj8`` — the proof that
what the writer emits is an OBJ8 the readers accept.  THE PACK IS NEVER
TOUCHED: nothing here opens a file for writing inside the scenery pack,
and the DSF is not read at all (§3 is the other lane's half).

It also prints §7's CENSUS from the plan: per body, the design surface at
its ANCHOR against the surface under every ground-contact FOOT, which is
what the placement law makes of the float —

    float(foot) = surface(foot) - (surface(anchor) + y_foot - y_zero)

— the same |Δ| histogram ``seat_feet_census.py`` prints from a mesh and a
seat RESULT, read instead from the plan and the design surface, so the
bars of §7 (LEMD feet > 0.3 m 284 -> <= 60) are comparable.  A foot or an
anchor standing outside every graded face reads NO surface and is counted
as ``off-sheet`` (§15 (5)), never guessed at: the DEM governs there, and this
tool does not open the DEM.

The design surface is sampled by linear interpolation over the emitted
surface's own vertices (``scipy.spatial.Delaunay`` over the graded
vertices, ``None`` outside their hull) — the surface as a continuous
field, which is what a drape reads.
"""
from __future__ import annotations

import argparse
import collections
import dataclasses as _dc
import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "src"))
# THE SHARED-REPO WRITE LAW (CLAUDE.md; owner ruling e9daef5), ONE
# implementation — ``tools/harness/shared_repo_guard.py``, the same module
# ``harness/build_airport.py`` and ``run_tile_mesh_only.py`` arm.  A lane
# replay of a plan is a MEASUREMENT: it must cost the shared corpus zero
# writes, and until 2026-09-12 this entry armed nothing — an OTHH
# ``--admit-skipped`` run created
# ``Airport_mod_cache/Global Airports/+25+051.dsf.e0518fe0.text`` (3.25 MB)
# and rewrote ``o4_dsf_object_positions_+25+051.cache`` in the shared repo
# with BOTH lane-local cache env vars exported (measured, lane v2atom
# round 2; RULINGS 2026-09-12j).
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "harness"))

import numpy as np                                             # noqa: E402

from auto_patch_v2.airport import anchor_rule as _ar           # noqa: E402
from auto_patch_v2.airport import obj8                         # noqa: E402
from auto_patch_v2.airport import placement_boxes as PB        # noqa: E402
from auto_patch_v2.airport import placement_plan as PP         # noqa: E402


def surface_from_graded(path: str, split_tol_m: float = 0.3):
    """``(sampler, pads, rims)`` from an emitted ``<ICAO>.graded.json``."""
    d = json.loads(open(path, encoding="utf-8").read())
    vs = d["vertices"]
    pts = np.asarray([[v[1], v[2]] for v in vs], dtype=float)
    zs = np.asarray([v[3] for v in vs], dtype=float)
    from scipy.interpolate import LinearNDInterpolator
    interp = LinearNDInterpolator(pts, zs)

    # §17 (owner RULINGS 2026-09-12am (2)): THE FACE ROLE UNDER A POINT,
    # off the SAME parsed document — the sampler answers how HIGH the
    # design surface is there and this answers WHAT IT IS, which is what
    # says whether a foot standing on it is judged at the motion
    # threshold or the visual one.  Carried on the sampler beside
    # ``many`` so no caller's tuple changes.
    from auto_patch_v2.law import tables as _T
    _law = _T.load_default()
    roles = PB.graded_roles_from_doc(
        d, rank=lambda r: _T.authority_rank(_law, r))

    # (E), owner RULINGS 2026-09-12ap: THE SAMPLER HONOURS GRADED HOLES.
    # The design surface is a set of FACES, and a face with a HOLE is
    # saying, in the document itself, that the ground inside that ring is
    # not its own.  LEMD's apron ``pav16`` is cut by such a ring standing
    # at 597.7-599.5 with the ``tunnel_trench`` floor (590.8-594.5)
    # inside it.  A Delaunay over the emitted VERTICES knows none of
    # that: it spans the ring with triangles reaching from an apron
    # vertex to a trench vertex, and the design surface then reads
    # **592.22 m at a point whose ROLE is apron** — 6.4 m of cliff served
    # as a ramp, six metres OUTSIDE the hole, which is where 12ap's two
    # worst pavement feet came from (`LEMDblast__b1`'s own anchor sat in
    # one of those triangles).
    #
    # A SIMPLEX THAT CROSSES A HOLE RING IS THEREFORE STRUCK, and the
    # points inside it read OFF-SHEET (§15 (5)) — never a height nothing
    # published.  Crossing is read on the VERTICES (one inside the ring,
    # one outside), because that is what "interpolated across the hole"
    # means; a triangle wholly inside the trench, or wholly out on the
    # apron, is untouched.
    #
    # TWO NARROWINGS THE MEASUREMENT FORCED, both on this frame:
    #   * "centroid on NO FACE" instead of the ring test struck 8,689 of
    #     LEMD's 47,287 simplices and took the pack from 2,107 written
    #     files to 1,686 with 435 bodies off-sheet — the emitted faces do
    #     not TILE the field (a graded strip stops where the next begins
    #     and the mesh carries the join), so "on no face" is not "no
    #     ground";
    #   * a crossing whose z-span is within ``[placement] split_tol_m``
    #     is a hole ring and its filler drawn at the SAME height with a
    #     seam of triangles between them (451 of LEMD's first 1,085):
    #     no cliff to invent, and no reading worth losing.
    # The shipped plan samples the MESH, which has the wall in it; this
    # is the replay instrument's own repair.
    _tri = getattr(interp, "tri", None)
    _bad = None
    _holes = [h for f in d.get("faces", ()) or ()
              for h in (f.get("holes", ()) or ())]
    if _tri is not None and _holes and len(getattr(_tri, "simplices", ())):
        _by = {v[0]: (v[1], v[2]) for v in vs}
        _hr = [(str(k), "", r, ()) for k, r in enumerate(
            tuple(_by[i] for i in hh if i in _by) for hh in _holes)
            if len(r) >= 3]
        _in = PB.GradedRoles(_hr).roles_many(
            pts[:, 0].tolist(), pts[:, 1].tolist())
        _hid = np.asarray([-1 if q is None else int(q) for q in _in],
                          dtype=np.int64)
        _sim = np.asarray(_tri.simplices)
        _h3 = _hid[_sim]
        _cross = (_h3.max(axis=1) != _h3.min(axis=1))
        _span = (zs[_sim].max(axis=1) - zs[_sim].min(axis=1)
                 > float(split_tol_m))
        _bad = _cross & _span
        if not _bad.any():
            _bad = None
        else:
            _hrx = PB.GradedRoles(_hr)

    def _mask(las, los, z):
        """``z``, with every reading taken ACROSS a hole ring replaced.

        A point in a struck simplex is not interpolated at all: it reads
        the nearest of that simplex's vertices standing on ITS OWN SIDE
        of the ring — the trench floor for a point in the trench, the
        apron for a point on the apron — and OFF-SHEET when the simplex
        has no vertex on its side.  Nothing is invented: every value is a
        vertex the surface published."""
        if _bad is None:
            return z
        la = np.asarray(las, dtype=float)
        lo = np.asarray(los, dtype=float)
        s = _tri.find_simplex(np.column_stack((la, lo)))
        out = np.asarray(z, dtype=float).copy()
        hit = np.nonzero((s >= 0) & _bad[np.maximum(s, 0)])[0]
        if not hit.size:
            return out
        vi = np.asarray(_tri.simplices)[s[hit]]                   # (n, 3)
        q = np.column_stack((la[hit], lo[hit]))
        side = np.asarray(
            [-1 if r is None else int(r) for r in
             _hrx.roles_many(q[:, 0].tolist(), q[:, 1].tolist())],
            dtype=np.int64)
        same = _hid[vi] == side[:, None]
        dv = np.hypot(*( (pts[vi] - q[:, None, :]).T ))           # (3, n)
        dv = np.where(same.T, dv, np.inf).T
        j = dv.argmin(axis=1)
        ok = np.isfinite(dv[np.arange(hit.size), j])
        out[hit] = np.where(ok, zs[vi[np.arange(hit.size), j]], np.nan)
        return out

    def sampler(lat: float, lon: float):
        z = _mask([lat], [lon], np.asarray(interp(lat, lon)).reshape(-1))
        z = float(np.asarray(z).reshape(-1)[0])
        return None if not np.isfinite(z) else z

    def many(las, los):
        """§16b: the VECTORISED read (``placement_cut.surface_many``).
        The cut and the census both read a body's whole written geometry,
        and a Delaunay interpolator's per-call overhead dwarfs the
        interpolation — one call per body instead of one per point."""
        z = np.asarray(interp(np.asarray(las, dtype=float),
                              np.asarray(los, dtype=float))).reshape(-1)
        z = _mask(las, los, z)
        return [None if not np.isfinite(q) else float(q) for q in z]

    sampler.many = many                       # type: ignore[attr-defined]
    sampler.roles = roles                     # type: ignore[attr-defined]
    sampler.rolled_on = frozenset(_T.rolled_on_roles(_law))   # type: ignore[attr-defined]
    sampler.holes_struck = (0 if _bad is None      # type: ignore[attr-defined]
                            else int(_bad.sum()))

    # ONE derivation site for pads/rims (lane v2planfix): the shipped
    # engine path calls the same function, so the tool and the build
    # cannot classify differently.
    pads, rims = PP.pads_rims_from_graded_doc(d)
    return sampler, pads, rims


def _near_m(lat0: float, lon0: float, lat: float, lon: float) -> float:
    """Plan distance in metres at this latitude — the same small-angle
    frame every per-site read in this tool uses."""
    import math
    return math.hypot((lat - lat0) * 110_540.0,
                      (lon - lon0) * 111_320.0 * math.cos(math.radians(lat0)))


def census(ss: PP.SplitSet, sampler, band_m: float,
           rows_of: tuple[str, ...] = (),
           near: "tuple[float, float, float] | None" = None) -> dict:
    """§7: the float per ground-contact foot under the placement law.

    §15 (5) THE INSTRUMENT: this tool samples the GRADED SURFACE; the
    shipped plan samples the MESH.  An anchor or a foot standing on no
    graded face is marked OFF-SHEET and excluded from every comparison
    and every bar — it reads no surface here, the DEM governs there, and
    this tool does not open the DEM.  A body's dry-run number is evidence
    only on-sheet.

    A foot counts when it is a ground-contact foot OF THE BODY: within
    ``band_m`` (``[basin] contact_band_m``, the same band the plan itself
    picks a PART's feet with) of the body's own lowest foot.  The plan's
    ground verdict was taken per part against its contact STRUCTURE, and
    a structure is not a body — at LEMD ``Munoza-LEMD79`` body 0 carries
    a part founded at -1.36 and one at +26.9, and counting the upper
    one's feet censused a rooftop 28 m "off its ground".  Re-judging at
    body level is 10i's own rule one level up, with 10i's own band.

    Every body counts — the bodies of a placement that would be SPLIT and
    the single body of one that stays whole alike, because the law is the
    same for both: the placement is AGL, its origin lands on the surface
    at its anchor, and the foot floats by whatever the surface does
    between the two points.

    ``rows_of`` names placements (resource substrings — the owner's three
    LEMD rows, ``OldTerminal_FSX-LEMD38`` and friends) whose PER-BODY
    rows come back under ``"rows"``: the body's anchor, the feet counted,
    the worst foot signed and |Δ|, and the 0.3 m verdict.  They are read
    off THIS SAME pass — a second instrument over the same population is
    the census-wrapper defect (CLAUDE.md).

    ``near`` — ``(lat, lon, radius_m)`` — selects the SAME rows BY PLACE
    instead of by resource (lane ``v2padcluster``, 2026-09-14, promoted
    from the `v2heca331` scout's scratchpad `site.py` on its second use:
    the 14g attribution, then §16g (10)'s per-site bars).  The owner
    names a defect by coordinate, never by resource, and the resource a
    coordinate belongs to is exactly what an attribution does not know
    yet; the shapeIDs in a report go stale between builds while a
    coordinate does not.  The distance is the body's ANCHOR to the point
    (the anchor IS what the seat is written at), and the rows come back
    nearest first.  ``osm_site --at/--contains`` answers the other half
    of the same question — which emitted FACES cover the point — and is
    not re-spelled here."""
    bins: collections.Counter = collections.Counter()
    worst: list[tuple[float, str, float, float]] = []
    per_placement: collections.Counter = collections.Counter()
    by_class: dict[str, collections.Counter] = collections.defaultdict(
        collections.Counter)
    rows: list[dict] = []
    for s in ss.all:
        by_name = any(n in s.resource for n in rows_of)
        for b in s.bodies:
            named = by_name or (
                near is not None
                and _near_m(near[0], near[1], b.anchor.lat, b.anchor.lon)
                <= near[2])
            za = b.anchor.surface_z
            if not b.feet:
                if named:
                    rows.append({"resource": s.resource, "body": b.body_id,
                                 "body_class": b.body_class,
                                 "anchor": (b.anchor.lat, b.anchor.lon),
                                 "anchor_z": za, "y_zero": b.anchor.y_zero,
                                 "reason": b.anchor.reason, "feet": 0,
                                 "off_sheet": 0, "worst": None,
                                 "worst_abs": None, "within_0_3": None})
                continue
            row = {"resource": s.resource, "body": b.body_id,
                   "body_class": b.body_class,
                   "anchor": (b.anchor.lat, b.anchor.lon),
                   "anchor_z": za, "y_zero": b.anchor.y_zero,
                   "reason": b.anchor.reason, "feet": 0, "off_sheet": 0,
                   "worst": None, "worst_abs": None, "within_0_3": None}
            floor = min(f[2] for f in b.feet)
            for lat, lon, y in [f for f in b.feet if f[2] - floor <= band_m]:
                row["feet"] += 1
                if za is None:
                    bins["off-sheet"] += 1
                    by_class[b.body_class]["off-sheet"] += 1
                    row["off_sheet"] += 1
                    continue
                zf = sampler(lat, lon)
                if zf is None:
                    bins["off-sheet"] += 1
                    by_class[b.body_class]["off-sheet"] += 1
                    row["off_sheet"] += 1
                    continue
                signed = zf - (za + y - b.anchor.y_zero)
                d = abs(signed)
                key = ("<0.3" if d < 0.3 else "0.3-1" if d < 1.0
                       else "1-3" if d < 3.0 else ">3")
                bins[key] += 1
                # THE DIRECTION IS THE READ (memory band-lawful-displacement /
                # the skirt law): a foot the ground stands OVER is BURIED —
                # lawful, invisible; a foot ABOVE its ground FLOATS, and that
                # is the defect the eye reads.  The low-side anchor of 11e (2)
                # trades float for burial by construction, so a census that
                # only takes |Δ| cannot tell the two arms apart.
                if d >= 0.3:
                    bins["buried" if signed > 0 else "floating"] += 1
                by_class[b.body_class][key] += 1
                if d >= 0.3:
                    per_placement[s.resource] += 1
                worst.append((d, f"{s.resource} b{b.body_id} [{b.body_class}]", lat, lon))
                if row["worst_abs"] is None or d > row["worst_abs"]:
                    row["worst_abs"] = d
                    row["worst"] = signed
            if named:
                if row["worst_abs"] is not None:
                    row["within_0_3"] = row["worst_abs"] < 0.3
                rows.append(row)
    worst.sort(reverse=True)
    if near is not None:
        for r in rows:
            r["site_m"] = round(_near_m(near[0], near[1], *r["anchor"]), 2)
        rows.sort(key=lambda r: (r["site_m"], r["resource"], r["body"]))
    else:
        rows.sort(key=lambda r: (r["resource"], r["body"]))
    return {"bins": dict(bins), "worst": worst[:20], "rows": rows,
            "feet": sum(v for k, v in bins.items()
                        if k not in ("buried", "floating")),
            "placements_over_0_3": len(per_placement),
            "by_class": {k: dict(v) for k, v in by_class.items()}}



def admit_skipped(plan, pack_root: str, dsftool: str | None,
                  elevated_base_m: float, foot_band_m: float,
                  thickness_m: float):
    """§16 (1) OFFLINE: put the resources the plan SKIPPED for the seat-era
    thickness gate back into the population, so a dry run can measure the
    switch the engine makes at LOAD.

    The engine needs nothing like this — ``pack_partition._build_member``
    admits the member when ``[rebake] placement = "agl"``, and the plan a
    build writes already carries it.  But a plan ALREADY WRITTEN (the
    app's ``o4_v2_rebake_<ICAO>.json``) dropped those resources before the
    units were built, and no replay can invent what the partition never
    read.  So the rows are read back from the pack's own DSF and each
    resource's components become a member's parts — one part per
    component, the plan's own frame, no contact graph (these resources
    touch nothing: that is why the gate caught them).  The CONTACT-based
    carrier path is therefore unavailable to them here and the plan
    OVERLAP path, which §15 (1) ranks first, is not.

    Returns ``(plan, rows admitted, resources admitted)``."""
    import dataclasses as dcls
    import tempfile

    from auto_patch.dsf_reader import _dsftool_path
    from auto_patch_v2.airport import dsf as _dsf
    from auto_patch_v2.airport import dsf_write as _dw
    from auto_patch_v2.airport import line_object as _lo
    from auto_patch_v2.airport import placement_carrier as PC
    from auto_patch_v2.law import Law as _Law
    from auto_patch_v2.model.rebake import Member, Part, Unit
    _rb = _Law.load().tables.structures.rebake

    want = {res for res, why in plan.skipped if why.startswith(PC.THICKNESS_SKIP)}
    if not want:
        return plan, 0, 0
    import glob
    dsfs = sorted(glob.glob(os.path.join(pack_root, "Earth nav data", "*", "*.dsf"))
                  + glob.glob(os.path.join(pack_root, "Earth nav data", "*.dsf")))
    if not dsfs:
        raise SystemExit(f"--admit-skipped: no DSF under {pack_root}/Earth nav data")
    work = tempfile.mkdtemp(prefix="o4_admit_")
    text = os.path.join(work, "pristine.text")
    _dw.dump(_dw.pristine_dsf_path(dsfs[0]), text, dsftool or _dsftool_path())
    dump = _dsf.read_dump(text)
    cache = obj8.ResourceCache(thickness_m)
    units = {(round(u.anchor[0], 9), round(u.anchor[1], 9)): [ui, list(u.members)]
             for ui, u in enumerate(plan.units)}
    extra: dict[tuple, list] = {}
    pid = 10_000_000
    rows = res_n = 0
    seen: set[tuple] = set()
    for row_ix, q in enumerate(dump.placements):
        if q.def_path not in want:
            continue
        rows += 1
        key = (round(q.lat, 9), round(q.lon, 9))
        if (key, q.def_path) in seen:
            continue                    # one bake per resource per anchor
        seen.add((key, q.def_path))
        path = os.path.join(pack_root, q.def_path.replace("\\", "/"))
        if not os.path.isfile(path):
            continue
        try:
            geom = obj8.parse_obj8(path)
            comps = cache.components(path)
        except (OSError, ValueError):
            continue
        if not comps:
            continue
        v = geom.vertices
        parts = []
        for ci, comp in enumerate(comps):
            ids = np.unique(np.asarray(comp.tris).reshape(-1))
            xs, ys, zs = v[ids, 0], v[ids, 1], v[ids, 2]
            lls = [PP.authored_latlon(float(x), float(z), q.lat, q.lon,
                                      q.heading_deg) for x, z in zip(xs, zs)]
            las = [c[0] for c in lls]
            los = [c[1] for c in lls]
            cla, clo = PP.authored_latlon(float(comp.cx), float(comp.cz),
                                          q.lat, q.lon, q.heading_deg)
            lo_y = float(ys.min())
            # §16 (1): these resources have NO genuine solid, so they are
            # FOOTLESS by construction — their thin panels are not ground
            # contacts (the engine strips the same feet at load)
            feet: tuple = ()
            pid += 1
            # 10bb's LINE verdict, per component — the partition runs it
            # at load and the admission must too, or a 50 m VOR marker
            # pole reads as a solid body with three feet 50 m down
            try:
                is_line = _lo.is_line_shaped(geom, comp, _rb)
            except Exception:
                is_line = False
            parts.append(Part(pid=pid, comp=ci, line=is_line,
                              lat=cla, lon=clo, base_y=lo_y,
                              area_m2=PC.box_area_m2((min(las), min(los),
                                                      max(las), max(los))),
                              box=(min(las), min(los), max(las), max(los)),
                              feet=feet))
        if not parts:
            continue
        res_n += 1
        # the member id IS the DSF ROW INDEX (``placement_plan._index_of``
        # reads it, and the writer matches the plan's index against the
        # dump's row): a synthetic id collides with a real placement and
        # the DSF edit refuses
        m = Member(id=f"dsf:obj{row_ix}", resource=q.def_path, authored_path=path,
                   live_path=path, heading_deg=q.heading_deg, parts=tuple(parts))
        if key in units:
            units[key][1].append(m)
        else:
            extra.setdefault(key, []).append(m)
    new_units = []
    for ui, u in enumerate(plan.units):
        key = (round(u.anchor[0], 9), round(u.anchor[1], 9))
        ms = units.get(key, [ui, list(u.members)])[1] if key in units else list(u.members)
        new_units.append(dcls.replace(u, members=tuple(ms)))
    for key, ms in sorted(extra.items()):
        new_units.append(Unit(f"unit:{len(new_units)}", key, 0.0, tuple(ms)))
    admitted = {r for r, _w in plan.skipped if r in want and r in
                {m.resource for u in new_units for m in u.members}}
    skipped = tuple((r, w) for r, w in plan.skipped if r not in admitted)
    return dcls.replace(plan, units=tuple(new_units),
                        skipped=skipped), rows, res_n


def msl_census_rows(dump, plan, ss, sampler, tol_m: float):
    """§16g (5) as amended (owner RULINGS 2026-09-14bo), read DRY: the
    per-placement ``OBJECT_MSL`` seats the writer would emit, and how far
    each one stands off the DESIGN SURFACE AT ITS OWN FEET.

    Returns ``(seats, counts, offs)`` — ``offs`` being ``elevation −
    surface(lat, lon)`` per seat, which is the number 14bo's bar is stated
    in (677 rows over 0.5 m at LEMD 1.0.336).  It is NOT zero by
    construction even under the amended law: a row standing on the unit's
    pad, on a deck, or carrying an authored offset is lawfully off its own
    feet by exactly that offset."""
    from auto_patch_v2.airport import footprint_unit as _fu
    from auto_patch_v2.law import Law as _L2
    _flat = getattr(plan, "flat", None)
    counts: dict = {}
    seats = _fu.msl_seats_for_dump(
        dump, plan, ss.unit_seats, sampler, "", frozenset(),
        tol_m=tol_m, authored_ground=(None if _flat is None else _flat.z0_m),
        counts=counts)
    offs = []
    for m in seats:
        z = sampler(m.lat, m.lon)
        offs.append(None if z is None else float(m.elevation) - float(z))
    counts.update(_fu.multi_anchor_census(dump, plan, seats, frozenset(),
                                          ss.unit_seats))
    return seats, counts, offs


def _msl_census(a, plan, ss, sampler) -> None:
    from auto_patch_v2.airport import dsf as _dsf
    from auto_patch_v2.law import Law as _L2
    dump = _dsf.read_dump(a.dsf_dump)
    tol = float(_L2.load().tables.emit.design.hard_tol_m)
    seats, counts, offs = msl_census_rows(dump, plan, ss, sampler, tol)
    print("\n§16g (5) PER-PLACEMENT OBJECT_MSL (RULINGS 2026-09-14bo), "
          f"from {os.path.basename(a.dsf_dump)}")
    print(f"  rows written: {len(seats)}")
    for k in sorted(counts):
        print(f"    {k}: {counts[k]}")
    have = [o for o in offs if o is not None]
    if have:
        over = [(abs(o), s) for o, s in zip(offs, seats) if o is not None
                and abs(o) > 0.5]
        over.sort(key=lambda t: -t[0])
        print(f"  |elevation − the surface at its own feet| > 0.5 m: "
              f"{len(over)} of {len(have)} (> 1 m: "
              f"{sum(1 for o in have if abs(o) > 1.0)})")
        for d, s in over[:15]:
            print(f"    {d:+7.2f} m  {s.resource.split('/')[-1][:46]:46s} "
                  f"{s.lat:.7f},{s.lon:.7f}  why={s.why}")


def _write_pack(a, plan, ss, sampler) -> None:
    """THE WRITE HALF into a pack COPY (11e (3)) — the same order the
    engine runs (``airport/placement_write.apply_plan``), never a second
    one."""
    import glob
    import tempfile

    from auto_patch.dsf_reader import _dsftool_path
    from auto_patch_v2.airport import dsf as _dsf
    from auto_patch_v2.airport import dsf_write as _dw
    from auto_patch_v2.airport import placement_carrier as PC
    from auto_patch_v2.airport import placement_write as PW
    from auto_patch_v2.law.tables import law_tables_digest

    root = os.path.abspath(a.write_pack)
    dsfs = sorted(glob.glob(os.path.join(root, "Earth nav data", "*", "*.dsf"))
                  + glob.glob(os.path.join(root, "Earth nav data", "*.dsf")))
    if not dsfs:
        raise SystemExit(f"no DSF under {root}/Earth nav data")
    dsf_path = dsfs[0]
    tool = a.dsftool or _dsftool_path()
    work = tempfile.mkdtemp(prefix="o4_split_write_")
    src = _dw.pristine_dsf_path(dsf_path)          # the ONE resolver (11m)
    dump_text = os.path.join(work, os.path.basename(dsf_path) + ".text")
    _dw.dump(src, dump_text, tool)
    dump = _dsf.read_dump(dump_text)
    splits, kept = PP.to_placement_records(ss)
    from auto_patch_v2.model.placement import PlacementPlan, Provenance
    conversions, _k = _dw.conversions_for_dump(dump, root)
    split_idx = frozenset(s.placement.index for s in splits)
    conversions = tuple(c for c in conversions if c.index not in split_idx)
    # §16g (5) (owner RULINGS 2026-09-13cb): the placements seated by
    # their DSF ROW, from the SAME call ``placement_write.build_plan``
    # makes — this tool builds its own ``PlacementPlan`` and without it
    # the write half would silently drop every one of them (measured:
    # "0 rows still carry an elevation" on a run that owed 4,846).
    from auto_patch_v2.airport import footprint_unit as _fu
    from auto_patch_v2.law import Law as _L2
    _flat = getattr(plan, "flat", None)
    _msl_counts: dict = {}
    msl = _fu.msl_seats_for_dump(
        dump, plan, ss.unit_seats, sampler, root, split_idx,
        tol_m=float(_L2.load().tables.emit.design.hard_tol_m),
        authored_ground=(None if _flat is None else _flat.z0_m),
        counts=_msl_counts)
    _mi = frozenset(m.index for m in msl)
    conversions = tuple(c for c in conversions if c.index not in _mi)
    counts = dict(ss.counts)
    counts["conversions"] = len(conversions)
    counts.update(_msl_counts)
    counts.update(_fu.multi_anchor_census(dump, plan, msl, split_idx,
                                          ss.unit_seats))
    pl = PlacementPlan(icao=plan.icao, pack_name=os.path.basename(root),
                       pack_root=root, dsf_path=dsf_path,
                       dsf_backup_path=dsf_path + ".anchor_bak",
                       provenance=Provenance("", "", str(
                           law_tables_digest().get("sha256") or ""), counts),
                       conversions=conversions, splits=splits, kept=kept,
                       msl_seats=msl)
    files = tuple(f for s in ss.splits for f in s.files)
    res = PW.apply_plan(pl, files, tool, patch_dir=a.patch_dir or root,
                        work_dir=work)
    print(f"\nWRITE HALF into {root}:")
    print(f"  {len(res.files_written)} cut file(s) written; DSF rewritten "
          f"(backup {'created' if res.dsf.backup_created else 'reused'}: "
          f"{os.path.basename(res.dsf.backup_path)}); round trip "
          f"{'OK' if res.dsf.report.ok else 'FAILED: ' + '; '.join(res.dsf.report.findings[:3])}")
    print(f"  plan -> {res.plan_path}")
    # §16c (5): THE BAR INSTRUMENT IS THE WRITTEN FRAME — the same
    # census ``--torn-seams`` prints, on the pack this call just wrote.
    _torn = PC.census_torn_seams([q.to_dict() for q in splits], root)
    for line in PC.cockpit_block_lines(PC.cockpit_block(
            splits=[q.to_dict() for q in splits], torn=_torn)):
        print(line)
    for line in PC.census_torn_seams_lines(_torn):
        print(line)
    # §16d (1): AND THE OTHER WRITTEN-FRAME BAR — is every written
    # triangle inside the box the plan published for its body?
    for line in PC.census_outside_box_lines(
            PC.census_outside_box([q.to_dict() for q in splits], root)):
        print(line)
    # THE READ-BACK: the written DSF dumped again must carry every new
    # placement, on its own new OBJECT_DEF
    back = os.path.join(work, "readback.text")
    _dw.dump(dsf_path, back, tool)
    d2 = _dsf.read_dump(back)
    want = set(pl.new_resources())
    have = set(d2.object_defs)
    rows = sum(1 for q in d2.placements if q.def_path in want)
    # §15 (4): the DUPLICATE ROWS.  A resource whose pristine DSF carries
    # two identical rows is ONE placement to the split; before this lane
    # one of them survived, drawing the whole un-split object at the
    # datum (LEMD: 19 `Airport_Cargo` resources).  Read on the WRITTEN
    # DSF, against the pristine rows the plan replaced.
    with open(dump_text, encoding="latin-1", errors="replace") as fh:
        pri = fh.read().splitlines(keepends=True)
    dups = _dw.duplicate_rows(pri, {s.placement.index for s in splits})
    n_before = sum(len(v) for v in dups.values())
    want_gone = {(s.placement.resource, round(s.placement.lon, 7),
                  round(s.placement.lat, 7)) for s in splits}
    survive = sum(1 for q in d2.placements
                  if (q.def_path, round(q.lon, 7), round(q.lat, 7)) in want_gone)
    print(f"  §15 (4) duplicate rows of a SPLIT placement: {n_before} in the "
          f"pristine DSF; surviving after the write: {survive} (bar 0)"
          + ("" if not survive else "   *** §15 (4) VIOLATED ***"))
    print(f"  read back: {len(d2.placements)} placement(s), "
          f"{len(want & have)}/{len(want)} new OBJECT_DEF(s) present, "
          f"{rows} row(s) on them; "
          f"{sum(1 for q in d2.placements if q.kind != 'OBJECT')} row(s) carry an "
          f"elevation ({len(pl.msl_seats)} of them written by §16g (5) — a "
          f"placement whose unit datum is not the terrain at its anchor; the "
          f"rest are a defect)")


def main() -> int:
    """The entry, under the SHARED-REPO WRITE GUARD (see the import
    block): nothing this tool does is authorised to write the shared
    data repo, so the guard refuses at the call site and the before /
    after snapshot backstops what no Python-level guard can see."""
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
        # the audit runs even when the run raised: a replay that died
        # halfway has still changed the corpus every other lane reads
        changes = snapshot_diff(before, shared_repo_snapshot())
        offenders = report_unauthorised_writes(changes, set(), None)
    if guard.blocked:
        print(f"\n  shared-repo writes REFUSED at the call site: "
              f"{len(guard.blocked)}")
        for b in list(guard.blocked)[:10]:
            print(f"    {b}")
    require_no_unauthorised_writes(offenders, entry="obj8_split_report")
    return rc


def _main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("plan", help="<ICAO>.rebake.json (or o4_v2_rebake_<ICAO>.json)")
    ap.add_argument("--graded", default="", help="<ICAO>.graded.json "
                    "(required unless --torn-seams)")
    ap.add_argument("--write-into", default="", help="write the cut files here and "
                                                     "parse each back (scratch only)")
    ap.add_argument("--json", default="", help="write the whole report here")
    ap.add_argument("--top", type=int, default=15)
    ap.add_argument("--filter", default="", help="only placements whose resource "
                                                 "contains this")
    ap.add_argument("--rows-near", default="", metavar="LAT,LON[,R]",
                    help="the SAME per-body rows as --rows, selected by "
                         "PLACE: every body whose ANCHOR is within R "
                         "metres (default 40) of LAT,LON, nearest first. "
                         "The owner names a site by coordinate and the "
                         "shapeIDs go stale between builds")
    ap.add_argument("--rows", default="", help="comma-separated resource "
                    "substrings whose PER-BODY census rows are printed by "
                    "name (anchor, feet, worst foot, the 0.3 m verdict) — "
                    "the owner's named sites, e.g. "
                    "'OldTerminal_FSX-LEMD38,OldTerminal_FSX-LEMD84'")
    ap.add_argument("--split-tol", type=float, default=None,
                    help="override [placement] split_tol_m (the body-coarsening "
                         "and anchor-admission tolerance, 11e)")
    ap.add_argument("--write-pack", default="", help="a pack COPY to apply the whole "
                                                     "write half into (11e (3))")
    ap.add_argument("--patch-dir", default="", help="where o4_v2_placement_<ICAO>.json "
                                                    "lands (default: --write-pack)")
    ap.add_argument("--dsftool", default=None, help="DSFTool binary (default: the "
                                                    "bundled one v1 resolves)")
    ap.add_argument("--line-segment", type=float, default=None,
                    help="override [placement] line_segment_m (the line-object "
                         "segment station span, 11f (2); 0 disarms the cut)")
    ap.add_argument("--admit-skipped", default="", help="a pack ROOT: put the "
                    "resources this plan skipped for the SEAT-era thickness "
                    "gate back into the population (§16 (1)) by reading their "
                    "rows from the pack's own DSF — what a build's plan now "
                    "carries by itself, for a plan written before §16")
    ap.add_argument("--coarsen-reach", type=float, default=None,
                    help="override [placement] coarsen_reach_m (§16b (1)'s "
                         "PLAN CONTIGUITY: two bodies of one placement join "
                         "one file only within this; 0 disarms it)")
    ap.add_argument("--torn-seams", default="", help="a pack ROOT whose "
                    "WRITTEN files this plan describes: print §16c (5)'s "
                    "TORN-SEAM CENSUS over them and exit.  The plan "
                    "argument is then the WRITTEN plan "
                    "(o4_v2_placement_<ICAO>.json), not the rebake plan, "
                    "and --graded is not read")
    ap.add_argument("--contact-eps", type=float, default=None,
                    help="override [placement] contact_eps_m (§16c (6): "
                         "components of one resource within this bind into "
                         "ONE rigid body; 0 disarms the distance test)")
    ap.add_argument("--rigid-reach", type=float, default=None,
                    help="override [placement] rigid_reach_m (§16c (7): "
                         "SOLID components of one resource within this chain "
                         "into ONE rigid cluster; 0 disarms the reach)")
    ap.add_argument("--motion-rows", default="", help="write §17's per-body "
                    "projection here as JSON ((E), RULINGS 2026-09-12ap): one "
                    "row per WRITTEN body with its anchor, class, anchor "
                    "reason and every ground-contact foot (lat/lon/authored "
                    "y/surface z/face role/on-pavement/float) — the rows "
                    "``census_motion`` itself reads, never a second census")
    ap.add_argument("--dsf-dump", default="", help="an EXISTING DSFTool text "
                    "dump of the pack's DSF: print §16g (5)'s per-placement "
                    "OBJECT_MSL census (RULINGS 2026-09-14bo) from the same "
                    "``footprint_unit.msl_seats_for_dump`` call the writer "
                    "makes — where each row's base came from and how far its "
                    "elevation stands off the design surface at its own feet. "
                    "READ-ONLY: nothing is written and no DSF is decoded")
    ap.add_argument("--no-cut", action="store_true",
                    help="body counts only — do not cut any OBJ8")
    a = ap.parse_args()

    if a.torn_seams:
        from auto_patch_v2.airport import placement_carrier as PC
        # §16c (5): the WRITTEN frame, read on the files themselves —
        # no surface, no cut, no law: the pack and the plan that wrote it.
        written = json.loads(open(a.plan, encoding="utf-8").read())
        root = os.path.abspath(a.torn_seams)
        c = PC.census_torn_seams(written.get("splits", ()), root)
        ob = PC.census_outside_box(written.get("splits", ()), root)
        print(f"written-frame census of {written.get('icao', '?')} over {root}")
        for line in PC.cockpit_block_lines(PC.cockpit_block(
                splits=written.get("splits", ()), torn=c)):
            print(line)
        for line in PC.census_torn_seams_lines(c):
            print(line)
        for line in PC.census_outside_box_lines(ob):
            print(line)
        if a.json:
            with open(a.json, "w", encoding="utf-8") as fh:
                json.dump({"torn": c, "outside_box": ob}, fh, indent=1)
        return 0

    from auto_patch_v2.law import Law
    _law = Law.load()
    band_m = _law.tables.structures.basin.contact_band_m
    rb0 = _law.tables.structures.rebake
    tol_m = _law.tables.structures.placement.split_tol_m if a.split_tol is None \
        else a.split_tol
    if not a.graded:
        ap.error("--graded is required")
    plan, abut = PP.read_plan(a.plan)
    sampler, pads, rims = surface_from_graded(a.graded, tol_m)
    if a.admit_skipped:
        plan, n_rows, n_res = admit_skipped(
            plan, os.path.abspath(a.admit_skipped), a.dsftool,
            rb0.elevated_base_m, band_m,
            _law.tables.structures.basin.min_solid_thickness_m)
        print(f"  §16 (1) ADMITTED {n_res} resource(s) the plan skipped for the "
              f"thickness gate ({n_rows} DSF row(s)) — the population a build's "
              f"own plan now carries")
    print(f"plan {plan.icao}  pack {plan.pack_name}\n"
          f"  units {len(plan.units)}  members {sum(len(u.members) for u in plan.units)}"
          f"  parts {plan.counts.get('parts')}  contacts {len(plan.contacts)}"
          f"  abutments {len(abut)}\n"
          f"  surface: {len(pads)} object pads, {len(rims)} structure rims")
    print(f"  coarsening: [placement] split_tol_m {tol_m:g} m")
    rb = _law.tables.structures.rebake
    seg_m = (_law.tables.structures.placement.line_segment_m
             if a.line_segment is None else a.line_segment)
    print(f"  line segments: [placement] line_segment_m {seg_m:g} m "
          f"(cap {rb.line_object_stations_max} stations)")
    _t0 = time.perf_counter()
    ss = PP.build_splits(plan, sampler, pads, rims, write=not a.no_cut,
                         split_tol_m=tol_m,
                         elevated_base_m=rb.elevated_base_m,
                         line_segment_m=seg_m,
                         line_stations_max=rb.line_object_stations_max,
                         line_ratio=rb.line_object_ratio,
                         line_max_h=rb.line_object_max_h,
                         foot_band_m=band_m, abutments=abut,
                         # §16g (10) (4): only a WALLED body links a unit
                         chain_min_height_m=(_law.tables.structures.placement
                                             .chain_min_height_m),
                         coarsen_reach_m=(_law.tables.structures.placement
                                          .coarsen_reach_m
                                          if a.coarsen_reach is None
                                          else a.coarsen_reach),
                         contact_eps_m=(_law.tables.structures.placement
                                        .contact_eps_m
                                        if a.contact_eps is None
                                        else a.contact_eps),
                         rigid_reach_m=(_law.tables.structures.placement
                                        .rigid_reach_m
                                        if a.rigid_reach is None
                                        else a.rigid_reach),
                         # (A), RULINGS 2026-09-12ap
                         bind_ground_m=_law.tables.emit.cockpit.visual_m,
                         cluster_min_m2=_law.tables.structures.placement
                         .cluster_pad_min_m2,
                         touch_m=_law.tables.structures.placement
                         .footprint_touch_m,
                         connector_span_m=_law.tables.structures.placement
                         .connector_span_m)
    # THE PLAN STAGE, timed where the shipped engine's own call is: this
    # is the number the round budgets quote, and it must not include the
    # graded parse, the Delaunay or the census the tool wraps it in.
    print(f"  plan stage: {time.perf_counter() - _t0:.2f} s"
          + ("" if a.no_cut else " (with the OBJ8 cut)"))
    c = ss.counts
    print(f"\nSPLIT  placements {c['placements']}  split {c['split']} into "
          f"{c['files']} files  kept whole {c['kept']}")
    print(f"  bodies {c['bodies']} (uncoarsened {c.get('bodies_uncoarsened')}; "
          f"{c.get('placements_coarsened', 0)} placement(s) coarsened); anchors: "
          f"{c.get('anchor_residual', 0)} low-side with a residual, "
          f"{c.get('anchor_off_surface', 0)} off-sheet; "
          f"{c.get('bodies_elevated', 0)} elevated bodies joined a ground group; "
          f"files per placement {c['files'] / max(1, c['placements']):.2f}")
    # §13 (3): the two classes the owner's 11r read turns on.  The first
    # bar is ZERO — a file whose whole content is elevated is the defect
    # (a roof, a deck, a tower part set on the ground); the second is the
    # lawful answer for a placement that has no ground body at all.
    own = c.get("elevated_own_files", 0)
    print(f"  footless placements: {c.get('footless', 0)} "
          f"({c.get('footless_carried', 0)} carried by a footed body of their "
          f"unit, {c.get('footless_no_carrier', 0)} with no footed body in the "
          f"unit at all, {c.get('footless_carrier_kept_whole', 0)} onto a "
          f"carrier still on its authored row); plan-overlap bound "
          f"{c.get('bodies_plan_bound', 0)} "
          f"body group(s), {c.get('basin_bodies_bound', 0)} basin resource(s) "
          f"made one file (§14)")
    # (A), owner RULINGS 2026-09-12ap: the binds the ground REFUSED.
    print(f"  §16c (7) bound by contact: "
          f"{c.get('bodies_bound_by_unit_contact', 0)} footed body(ies) "
          f"re-anchored, {c.get('bodies_bound_to_cluster_by_contact', 0)} "
          f"elevated body group(s) ridden; bound refused for ground "
          f"{c.get('bind_refused_for_ground', 0)} (worst own-ground "
          f"disagreement refused {c.get('bind_refused_worst_m', 0.0):.2f} m; "
          f"widest retained cluster zero-plane span "
          f"{c.get('bind_zero_span_worst_m', 0.0):.2f} m)")
    if c.get("line_bodies_segmented"):
        print(f"  §10 (2) line bodies segmented: {c['line_bodies_segmented']} "
              f"into {c.get('line_segments', 0)} file(s)")
    print(f"  elevated bodies as own files: {own}"
          f"{'' if own == 0 else '   *** §13 (1) VIOLATED (bar 0) ***'}; "
          f"footless placements on their OWN ground (§16 (3), no carrier "
          f"the law accepts): {c.get('footless_no_carrier', 0)}; "
          f"elevated bodies carried by a ground body's file: "
          f"{c.get('bodies_elevated_carried', 0)}")
    # §14 (4): ONE implementation of the four bars, shared with
    # ``seat_feet_census --placement-plan`` (a second reading of the same
    # population is the census-wrapper defect, CLAUDE.md).
    from auto_patch_v2.airport import placement_carrier as PC
    _sp, _kp = PP.to_placement_records(ss)
    _wh, _ = PP.to_placement_records(_dc.replace(ss, splits=ss.whole))
    v14 = PC.census_v14([q.to_dict() for q in _sp], [q.to_dict() for q in _kp],
                        elevated_base_m=rb.elevated_base_m, split_tol_m=tol_m,
                        rims=rims, arc_cap=rb.line_object_stations_max,
                        counts=ss.counts)
    # §15 (3) / §16b (4) are computed HERE, before anything is printed, so
    # the COCKPIT block can be printed FIRST (§31 (6): "Every spec's
    # MEASURED block from now on quotes the cockpit block first").  Their
    # own lines still print below, in their own order and unchanged.
    _plan_rows = [q.to_dict() for q in _sp] + [q.to_dict() for q in _wh]
    v15 = PC.census_v15(_plan_rows, ground_tol_m=tol_m)
    v16b = PC.census_v16b(_plan_rows, sampler, split_tol_m=tol_m)
    # §17's MOTION reading (owner RULINGS 2026-09-12am (2)): every
    # WRITTEN body's ground-contact feet, the graded face ROLE under each
    # of them, and §7's own float there — read on the SplitSet, which is
    # where the feet are (the plan publishes their COUNT, not their
    # points).  The projection is the record's own fields; the reading is
    # the library's.
    # the MOTION reading is ``placement_census``'s own (the census front
    # door); ``PC`` above is the carrier module's re-export surface, which
    # this lane does not extend.
    from auto_patch_v2.airport import placement_census as PCM
    motion = PCM.census_motion(
        [{"res": b.new_resource or s.resource, "cls": b.body_class,
          "anchor_lat": b.anchor.lat, "anchor_lon": b.anchor.lon,
          "anchor_z": b.anchor.surface_z, "y_zero": b.anchor.y_zero,
          "reason": b.anchor.reason, "feet": b.feet}
         for s in ss.all for b in s.bodies],
        sampler, sampler.roles, rolled_on=sampler.rolled_on,
        motion_step_m=_law.tables.emit.cockpit.motion_step_m,
        visual_m=_law.tables.emit.cockpit.visual_m,
        band_m=band_m, contact_tol_m=tol_m,
        want_rows=bool(a.motion_rows),
        exempt_classes=frozenset({_ar.BASIN}))
    # (E)/12ap: the per-body projection of §17's population, promoted out
    # of the scout's scratchpad on its SECOND use (CLAUDE.md tool
    # discipline).  ONE reading — the rows come out of ``census_motion``
    # itself, so the projection and the printed census cannot be two
    # populations.
    if a.motion_rows:
        with open(a.motion_rows, "w", encoding="utf-8") as fh:
            json.dump({"ruling": "2026-09-12ap", "icao": plan.icao,
                       "band_m": motion["band_m"],
                       "contact_tol_m": motion["contact_tol_m"],
                       "rolled_on": list(motion["rolled_on"]),
                       "rows": list(motion["rows"])}, fh)
        print(f"   §17 motion rows -> {a.motion_rows} "
              f"({len(motion['rows'])} body(ies))")
    for line in PC.cockpit_block_lines(PC.cockpit_block(
            splits=_plan_rows, v15=v15, v16b=v16b, motion=motion,
            units=ss.counts)):
        print(line)
    for line in PCM.census_motion_lines(motion):
        print(line)
    for line in PC.census_v14_lines(v14, elevated_base_m=rb.elevated_base_m,
                                    split_tol_m=tol_m):
        print(line)
    # §14a (2): the members the ring sent to the FLOOR (the plan's own count)
    if ss.counts.get("basin_floor_members") or ss.counts.get("basin_bodies_arc_cut"):
        print(f"   §14a basin FLOOR members (inside the ring, on the ground "
              f"under their own footprint, never on the rim): "
              f"{ss.counts.get('basin_floor_members', 0)}; basin bodies cut by "
              f"the ring's ARCS: {ss.counts.get('basin_bodies_arc_cut', 0)} "
              f"into {ss.counts.get('basin_arc_pieces', 0)} piece(s)")
    # §15 (3): the residual the EYE reads — a carried body has no feet and
    # a body on its own low-side foot reads every foot of its own as
    # lawful, so neither bar above can see a roof standing 6 m over the
    # walls it belongs to.
    for line in PC.census_v15_lines(v15):
        print(line)
    # §16f (3): THE OBJECT FAMILY (RULINGS 2026-09-13af) — the derived
    # relation the plan publishes per body (``family_of``), its one zero
    # plane, its spread and the members cut apart.  The same call
    # ``seat_feet_census`` makes over the same plan shape.
    for line in PC.census_families_lines(PC.census_families(
            [q.to_dict() for q in _sp] + [q.to_dict() for q in _wh],
            sampler)):
        print(line)
    # §16 (1): THE POPULATION — every OBJECT row of the pack is in the
    # plan; the seat-era thickness skip is not applied under ``agl``.
    for line in PC.census_population_lines(PC.census_population(plan.skipped)):
        print(line)
    # §16 (2): the float read on the body's OWN GEOMETRY, which is the
    # only reading that sees a body standing over no body at all.
    v16 = PC.census_v16([q.to_dict() for q in _sp] + [q.to_dict() for q in _wh],
                        sampler)
    for line in PC.census_v16_lines(v16):
        print(line)
    # §16b (4): the two bars read on the WRITTEN GEOMETRY — never on
    # ``geom_box``, which for a carried body the cut left whole is the
    # patch its CARRIER covers (11ap).
    for line in PC.census_v16b_lines(v16b):
        print(line)
    print(f"  §16 re-cut by terrain: {c.get('bodies_re_cut_by_terrain', 0)} "
          f"body(ies) into {c.get('terrain_body_groups', 0)} terrain group(s), "
          f"by TRIANGLE {c.get('bodies_re_cut_by_triangle', 0)} into "
          f"{c.get('terrain_triangle_groups', 0)}, by FOOT (11ak (2)) "
          f"{c.get('bodies_re_cut_by_foot', 0)} into "
          f"{c.get('terrain_foot_groups', 0)}; "
          f"§16a carried bodies left uncut by the ground "
          f"{c.get('carried_bodies_uncut', 0)}, cut by their CARRIER "
          f"{c.get('carried_bodies_cut_by_carrier', 0)} into "
          f"{c.get('carrier_pieces', 0)} piece(s); "
          f"own-ground files {c.get('footless_own_ground', 0)}; carriers "
          f"refused: " + (", ".join(f"{k[16:]} {v}" for k, v in sorted(c.items())
                                    if k.startswith("carrier_refused_")) or "none"))
    if c.get("line_segments"):
        print(f"  line segments: {c['line_segments']} from "
              f"{c.get('line_bodies_segmented', 0)} one-line bodies (11f (2))")
    print("  kept-whole reasons: " + ", ".join(
        f"{k} {v}" for k, v in sorted(collections.Counter(
            k.reason for k in ss.kept).items(), key=lambda kv: -kv[1])))
    print("  body classes: " + ", ".join(f"{k[6:]} {v}" for k, v in sorted(c.items())
                                         if k.startswith("class_")))

    # THE KEPT-WHOLE PLACEMENTS (11e): they keep their AUTHORED anchor, so
    # what the drape puts on the ground is their authored y = 0 — the
    # generic rule's y_zero for their single body says how far that is
    # from the body's own zero, and that IS their residual class.
    wh = [(b.anchor.y_zero, s.resource) for s in ss.whole for b in s.bodies]
    if wh:
        ok = sum(1 for y, _r in wh if abs(y) <= tol_m)
        wh.sort(key=lambda q: -abs(q[0]))
        print(f"\nKEPT WHOLE {len(wh)}: {ok} whose authored origin is within "
              f"{tol_m:g} m of the body's own zero; worst: "
              + ", ".join(f"{os.path.basename(r)[:34]} {y:+.1f}" for y, r in wh[:5]))

    rows = [s for s in ss.splits if a.filter in s.resource]
    rows.sort(key=lambda s: -len(s.bodies))
    print(f"\nthe {min(a.top, len(rows))} placements with the most bodies:")
    for s in rows[:a.top]:
        print(f"  #{s.index} {s.resource}  {len(s.bodies)} bodies -> "
              f"{len(s.files)} files")
        for b in s.bodies[:6]:
            print(f"      b{b.body_id} [{b.body_class}] {b.anchor.lat:.7f},"
                  f"{b.anchor.lon:.7f}  y0 {b.anchor.y_zero:+.2f}  "
                  f"offset {b.anchor.offset[0]:+.1f},{b.anchor.offset[1]:+.1f},"
                  f"{b.anchor.offset[2]:+.1f}  {b.anchor.reason}")
        if len(s.bodies) > 6:
            print(f"      ... {len(s.bodies) - 6} more")

    wrote = parsed = 0
    if a.write_into:
        os.makedirs(a.write_into, exist_ok=True)
        for s in ss.splits:
            for f in s.files:
                p = os.path.join(a.write_into, f.resource.replace("/", "__"))
                with open(p, "w", encoding="latin-1") as fh:
                    fh.write(f.text)
                wrote += 1
                g = obj8.parse_obj8(p)
                if g.solid.shape[0] + g.draped.shape[0] == f.tris:
                    parsed += 1
                else:
                    print(f"  MISMATCH {f.resource}: wrote {f.tris} tris, "
                          f"parse_obj8 reads {g.solid.shape[0] + g.draped.shape[0]}")
        print(f"\nwrote {wrote} files into {a.write_into}; "
              f"{parsed} parse back with the written triangle count")

    if a.write_pack:
        _write_pack(a, plan, ss, sampler)

    if a.dsf_dump:
        _msl_census(a, plan, ss, sampler)

    rows_of = tuple(n.strip() for n in a.rows.split(",") if n.strip())
    near = None
    if a.rows_near:
        q = [float(v) for v in a.rows_near.split(",")]
        if len(q) not in (2, 3):
            raise SystemExit("--rows-near takes LAT,LON or LAT,LON,RADIUS_M")
        near = (q[0], q[1], q[2] if len(q) == 3 else 40.0)
    cen = census(ss, sampler, band_m, rows_of=rows_of, near=near)
    if rows_of or near:
        what = (f"within {near[2]:.0f} m of {near[0]:.7f},{near[1]:.7f}"
                if near else ", ".join(rows_of))
        print(f"\nNAMED ROWS ({what}): {len(cen['rows'])} bodies")
        for r in cen["rows"]:
            az = "OFF-SHEET" if r["anchor_z"] is None else f"{r['anchor_z']:.2f}"
            w = ("no foot" if r["worst_abs"] is None
                 else f"{r['worst']:+.2f} (|{r['worst_abs']:.2f}|)")
            v = ("-" if r["within_0_3"] is None
                 else "WITHIN 0.3" if r["within_0_3"] else "OVER 0.3")
            print(f"  {os.path.basename(r['resource'])[:40]:<40} b{r['body']} "
                  f"[{r['body_class']}] anchor {r['anchor'][0]:.7f},"
                  f"{r['anchor'][1]:.7f} z {az} y0 {r['y_zero']:+.2f} "
                  f"({r['reason']})  feet {r['feet']} "
                  f"(off-sheet {r['off_sheet']})  worst {w}  {v}"
                  + (f"  site {r['site_m']:.1f} m" if "site_m" in r else ""))
    print(f"\nCENSUS (§7) over {cen['feet']} ground-contact feet of "
          f"{sum(len(s.bodies) for s in ss.all)} bodies:")
    print("  " + "  ".join(f"{k} {v}" for k, v in sorted(cen["bins"].items())))
    print(f"  placements with any foot > 0.3 m: {cen['placements_over_0_3']}")
    for k, v in sorted(cen["by_class"].items()):
        print(f"    {k:<13} " + "  ".join(f"{kk} {vv}" for kk, vv in sorted(v.items())))
    print("  worst feet:")
    for d, who, lat, lon in cen["worst"][:8]:
        print(f"    {d:7.2f} m  {who}  {lat:.6f},{lon:.6f}")

    if a.json:
        out = ss.to_dict()
        out["wrote"] = wrote
        out["parsed"] = parsed
        out["census"] = {"bins": cen["bins"], "feet": cen["feet"],
                         "placements_over_0_3": cen["placements_over_0_3"],
                         "rows": cen["rows"]}
        json.dump(out, open(a.json, "w", encoding="utf-8"))
        print(f"report -> {a.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
