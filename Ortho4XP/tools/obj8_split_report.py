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
        [--rows SUBSTR,SUBSTR] [--no-cut] [--split-tol M]
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

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "src"))

import numpy as np                                             # noqa: E402

from auto_patch_v2.airport import obj8                         # noqa: E402
from auto_patch_v2.airport import placement_plan as PP         # noqa: E402


def surface_from_graded(path: str):
    """``(sampler, pads, rims)`` from an emitted ``<ICAO>.graded.json``."""
    d = json.loads(open(path, encoding="utf-8").read())
    vs = d["vertices"]
    pts = np.asarray([[v[1], v[2]] for v in vs], dtype=float)
    zs = np.asarray([v[3] for v in vs], dtype=float)
    from scipy.interpolate import LinearNDInterpolator
    interp = LinearNDInterpolator(pts, zs)

    def sampler(lat: float, lon: float):
        z = interp(lat, lon)
        z = float(np.asarray(z).reshape(-1)[0])
        return None if not np.isfinite(z) else z

    # ONE derivation site for pads/rims (lane v2planfix): the shipped
    # engine path calls the same function, so the tool and the build
    # cannot classify differently.
    pads, rims = PP.pads_rims_from_graded_doc(d)
    return sampler, pads, rims


def census(ss: PP.SplitSet, sampler, band_m: float,
           rows_of: tuple[str, ...] = ()) -> dict:
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
    the census-wrapper defect (CLAUDE.md)."""
    bins: collections.Counter = collections.Counter()
    worst: list[tuple[float, str, float, float]] = []
    per_placement: collections.Counter = collections.Counter()
    by_class: dict[str, collections.Counter] = collections.defaultdict(
        collections.Counter)
    rows: list[dict] = []
    for s in ss.all:
        named = any(n in s.resource for n in rows_of)
        for b in s.bodies:
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


def _write_pack(a, plan, ss, sampler) -> None:
    """THE WRITE HALF into a pack COPY (11e (3)) — the same order the
    engine runs (``airport/placement_write.apply_plan``), never a second
    one."""
    import glob
    import tempfile

    from auto_patch.dsf_reader import _dsftool_path
    from auto_patch_v2.airport import dsf as _dsf
    from auto_patch_v2.airport import dsf_write as _dw
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
    counts = dict(ss.counts)
    counts["conversions"] = len(conversions)
    pl = PlacementPlan(icao=plan.icao, pack_name=os.path.basename(root),
                       pack_root=root, dsf_path=dsf_path,
                       dsf_backup_path=dsf_path + ".anchor_bak",
                       provenance=Provenance("", "", str(
                           law_tables_digest().get("sha256") or ""), counts),
                       conversions=conversions, splits=splits, kept=kept)
    files = tuple(f for s in ss.splits for f in s.files)
    res = PW.apply_plan(pl, files, tool, patch_dir=a.patch_dir or root,
                        work_dir=work)
    print(f"\nWRITE HALF into {root}:")
    print(f"  {len(res.files_written)} cut file(s) written; DSF rewritten "
          f"(backup {'created' if res.dsf.backup_created else 'reused'}: "
          f"{os.path.basename(res.dsf.backup_path)}); round trip "
          f"{'OK' if res.dsf.report.ok else 'FAILED: ' + '; '.join(res.dsf.report.findings[:3])}")
    print(f"  plan -> {res.plan_path}")
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
          f"{sum(1 for q in d2.placements if q.kind != 'OBJECT')} row(s) still carry an "
          f"elevation")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("plan", help="<ICAO>.rebake.json (or o4_v2_rebake_<ICAO>.json)")
    ap.add_argument("--graded", required=True, help="<ICAO>.graded.json")
    ap.add_argument("--write-into", default="", help="write the cut files here and "
                                                     "parse each back (scratch only)")
    ap.add_argument("--json", default="", help="write the whole report here")
    ap.add_argument("--top", type=int, default=15)
    ap.add_argument("--filter", default="", help="only placements whose resource "
                                                 "contains this")
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
    ap.add_argument("--no-cut", action="store_true",
                    help="body counts only — do not cut any OBJ8")
    a = ap.parse_args()

    from auto_patch_v2.law import Law
    _law = Law.load()
    band_m = _law.tables.structures.basin.contact_band_m
    rb0 = _law.tables.structures.rebake
    tol_m = _law.tables.structures.placement.split_tol_m if a.split_tol is None \
        else a.split_tol
    plan, abut = PP.read_plan(a.plan)
    sampler, pads, rims = surface_from_graded(a.graded)
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
    ss = PP.build_splits(plan, sampler, pads, rims, write=not a.no_cut,
                         split_tol_m=tol_m,
                         elevated_base_m=rb.elevated_base_m,
                         line_segment_m=seg_m,
                         line_stations_max=rb.line_object_stations_max,
                         line_ratio=rb.line_object_ratio,
                         line_max_h=rb.line_object_max_h,
                         foot_band_m=band_m, abutments=abut,
                         carrier_fill_min=_law.tables.structures.placement
                         .carrier_fill_min)
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
                        elevated_base_m=rb.elevated_base_m, split_tol_m=tol_m)
    for line in PC.census_v14_lines(v14, elevated_base_m=rb.elevated_base_m,
                                    split_tol_m=tol_m):
        print(line)
    # §15 (3): the residual the EYE reads — a carried body has no feet and
    # a body on its own low-side foot reads every foot of its own as
    # lawful, so neither bar above can see a roof standing 6 m over the
    # walls it belongs to.
    v15 = PC.census_v15([q.to_dict() for q in _sp] + [q.to_dict() for q in _wh],
                        fill_min=_law.tables.structures.placement.carrier_fill_min,
                        ground_tol_m=tol_m)
    for line in PC.census_v15_lines(v15):
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

    rows_of = tuple(n.strip() for n in a.rows.split(",") if n.strip())
    cen = census(ss, sampler, band_m, rows_of=rows_of)
    if rows_of:
        print(f"\nNAMED ROWS ({', '.join(rows_of)}): "
              f"{len(cen['rows'])} bodies")
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
                  f"(off-sheet {r['off_sheet']})  worst {w}  {v}")
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
