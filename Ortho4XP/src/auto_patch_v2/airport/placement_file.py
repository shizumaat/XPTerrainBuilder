"""THE AUTHORED FRAME AND THE FILING OF ONE PLACEMENT'S BODIES.

:func:`authored_offset` (§4.3 / §6, the offset subtracted from every
vertex) and the helpers that decide WHICH FILE a formed body goes in —
the group's bodies (:func:`_group_bodies`), the carried file
(:func:`_carried_file`), §16 (3)'s own-ground residual
(:data:`OWN_GROUND`, :func:`_own_ground_file`), §16g (11)'s unit carry
(:func:`_unit_carried_file`), the cut-and-file path
(:func:`_cut_and_file`) and the per-unit split (:func:`_split_by_unit`).

Split out of ``airport/placement_plan`` (issue #303: that file passed the
1,500-line split point) along the seam the module already splits on —
``placement_record``, ``placement_cut``, ``placement_carrier``,
``placement_contact``.  ``build_splits`` stays next door and calls these.

No cycle, so no lazy import: filing reads the records, the cut and the
unit seats and never reads ``placement_plan`` back.  Every name keeps its
import path — ``placement_plan`` re-exports all of them.
"""
from __future__ import annotations

import dataclasses as _dc
import math
import typing as _t

from ..model.rebake import Member, Unit
from . import anchor_rule as _ar
from . import bridge_family as _bf
from . import footprint_unit as _fu
from . import obj8_split as _split
from . import placement_carrier as _pc
from .placement_cut import GEOM_PTS_MAX, _Raw, pristine_path, thin_points
from .placement_record import Body, Kept, Split

__all__ = ["OWN_GROUND", "authored_offset"]


# ── the authored frame ───────────────────────────────────────────────────

def authored_offset(anchor_lat: float, anchor_lon: float, y_zero: float,
                    placement_lat: float, placement_lon: float,
                    heading_deg: float) -> tuple[float, float, float]:
    """§4.3 / §6: the offset SUBTRACTED from every vertex — the anchor
    point's AUTHORED ``(x, z)`` and the body's intended zero ``y``.

    OBJ8 is x east, y up, z SOUTH, rotated by the heading (clockwise from
    north) about y — ``obj8.placement_affine``'s own convention:
    ``east = x·cos h − z·sin h``, ``north = −(x·sin h + z·cos h)``.  This
    is that map inverted."""
    ml, mo = _ar._m_per_deg(placement_lat)
    e = (anchor_lon - placement_lon) * mo
    n = (anchor_lat - placement_lat) * ml
    h = math.radians(heading_deg)
    s, c = math.sin(h), math.cos(h)
    return (e * c - n * s, y_zero, -e * s - n * c)


def _geom_pts(raw: _t.Sequence[_Raw], grp: _t.Sequence[int]
              ) -> tuple[tuple[float, float, float], ...]:
    """§16b (4): the WRITTEN GEOMETRY of a file — every raw body in it,
    thinned once more so a file made of many pieces publishes no more
    samples than one body does."""
    return thin_points(tuple(p for i in grp for p in raw[i][6]), GEOM_PTS_MAX)


def _geom_hull(grp: _t.Sequence[int],
               part_boxes: _t.Sequence[_t.Sequence[tuple]],
               geom_boxes: _t.Sequence = ()) -> "tuple | None":
    """§16d (1): THE HULL OF WHAT THE FILE WILL CONTAIN.

    A body's ``geom_box`` was the hull of its PART boxes, and a body the
    cut made carries its part box from its FEET (11f (2)) — so a line
    segment, a terrain group, a basin arc or a carrier piece published a
    box drawn round its feet while the writer put its whole triangle set
    in the file.  ``Staged.geom_boxes`` carries the triangle hull where a
    cut gave the raw body one; this hulls both."""
    bs = [b for i in grp for b in part_boxes[i]]
    bs += [geom_boxes[i] for i in grp
           if i < len(geom_boxes) and geom_boxes[i]]
    return _pc.hull_of(bs)


def _group_bodies(raw: _t.Sequence[_Raw], merged: _t.Sequence[_t.Sequence[int]],
                  m: Member, u: Unit, counts: dict[str, int],
                  by_class: dict[str, int],
                  part_boxes: _t.Sequence[_t.Sequence[tuple]] = (),
                  ground_off: _t.Sequence["float | None"] = (),
                  bridge: _t.Sequence[str] = (),
                  geom_boxes: _t.Sequence = ()) -> list[Body]:
    """The groups of one member as :class:`Body` records, each on its
    SENIOR body's anchor (:func:`placement_carrier.senior_of`)."""
    bodies: list[Body] = []
    for k, grp in enumerate(merged):
        senior = _pc.senior_of(raw, grp)
        parts = [p for i in grp for p in raw[i][0]]
        a = raw[senior][2]
        off = authored_offset(a.lat, a.lon, a.y_zero, u.anchor[0], u.anchor[1],
                              m.heading_deg)
        a = _dc.replace(a, offset=off)
        by_class[a.body_class] = by_class.get(a.body_class, 0) + 1
        # §13 (3): an elevated member's vertices are NOT feet — they never
        # stood on the ground, and counting them is what made the 218
        # census green while the sim was broken
        # §16d (1): an ORPHAN component carries no parts — it is not an
        # elevated MEMBER of the placement, only geometry the file must
        # contain, and counting it as one inflates every §13 number
        _mem = [i for i in grp if raw[i][0]]
        n_elev = sum(1 for i in _mem if raw[i][4])
        if n_elev:
            counts["bodies_elevated_carried"] = \
                counts.get("bodies_elevated_carried", 0) + n_elev
        if _mem and n_elev == len(_mem):
            counts["elevated_own_files"] = counts.get("elevated_own_files", 0) + 1
        feet = tuple(f for i in grp if not raw[i][4] for f in raw[i][3])
        if a.reason.startswith("low-side foot ("):
            counts["anchor_residual"] = counts.get("anchor_residual", 0) + 1
        elif a.surface_z is None:
            counts["anchor_off_surface"] = counts.get("anchor_off_surface", 0) + 1
        # a SEGMENT is cut by TRIANGLE; its parent component must NOT also
        # be handed to the cutter as a whole component, or this file would
        # claim the whole fence (11f (2))
        tris = tuple(t for i in grp for t in raw[i][5])
        cut_comps = tuple(sorted({p.comp for i in grp if not raw[i][5]
                                  for p in raw[i][0]}))
        bodies.append(Body(k, a.body_class, tuple(sorted(p.comp for p in parts)),
                           a, _split.body_resource_name(m.resource, k, off),
                           tuple(sorted(p.pid for p in parts)), feet=feet,
                           cut_components=cut_comps, tris=tris,
                           elevated=n_elev == len(grp),
                           elevated_members=n_elev,
                           # THE GROUND FOOTPRINT (§15 (3)): a carried
                           # roof does not widen what its file STANDS ON,
                           # and the §15 (1) search read the group before
                           # any roof joined it — one box, one relation
                           plan_box=_pc.hull_of(
                               b for i in grp if not raw[i][4]
                               for b in part_boxes[i])
                           or _pc.hull_of(b for i in grp for b in part_boxes[i])
                           if part_boxes else _pc.box_of(feet, parts),
                           # §16 (2)/(3): the body's OWN geometry, and the
                           # bounded footprint the stands-over relation reads
                           geom_box=(_geom_hull(grp, part_boxes, geom_boxes)
                                     if part_boxes else _pc.box_of(feet, parts)),
                           foot_boxes=(_pc.foot_boxes(
                               [b for i in grp if not raw[i][4]
                                for b in part_boxes[i]]
                               or [b for i in grp for b in part_boxes[i]])
                               if part_boxes else ()),
                           # §16a (2): what the law would ask of this body
                           # before letting it carry anything — the census
                           # asks the same before calling it "beneath"
                           ground_off=(ground_off[k]
                                       if k < len(ground_off) else None),
                           fill=(_pc.fill_of(
                               _pc.hull_of(b for i in grp if not raw[i][4]
                                           for b in part_boxes[i])
                               or _pc.hull_of(b for i in grp
                                              for b in part_boxes[i]),
                               [b for i in grp if not raw[i][4]
                                for b in part_boxes[i]]
                               or [b for i in grp for b in part_boxes[i]])
                               if part_boxes else 1.0),
                           bridge_of=_bf.body_bridge(bridge, grp),
                           geom_pts=_geom_pts(raw, grp)))
    return bodies


def _carried_file(raw: _t.Sequence[_Raw], grp: _t.Sequence[int], m: Member,
                  u: Unit, c: _pc.Candidate, why: str, carrier_res: str,
                  written: bool, body_id: int, counts: dict[str, int],
                  by_class: dict[str, int],
                  part_boxes: _t.Sequence[_t.Sequence[tuple]] = (),
                  bridge: _t.Sequence[str] = (),
                  geom_boxes: _t.Sequence = ()) -> Body:
    """§14 (1) / §15 (1): the bodies of ``grp`` as ONE file written at
    their CARRIER's anchor with the carrier's ``y_zero``.

    One zero plane for the two of them — which is what "the roof stays
    on its walls" means when the walls are the only thing either of them
    can read.  The translation is computed in THIS member's own authored
    frame (the offset every body file already carries), so the carried
    file lands exactly where the unit authored it relative to the
    carrier; with one unit, one row and one heading that is numerically
    the carrier's own :func:`authored_offset`.

    Bodies sharing a carrier share a file: one carrier, one zero, one
    cut.  §15 (1) is why the carrier may belong to ANOTHER RESOURCE of
    the unit — this pack names its roofs as their own resources, and the
    walls a roof stands over are almost never its own file."""
    parts = [p for i in grp for p in raw[i][0]]
    cls = raw[max(grp, key=lambda i: len(raw[i][0]))][1]
    off = authored_offset(c.anchor.lat, c.anchor.lon, c.anchor.y_zero,
                          u.anchor[0], u.anchor[1], m.heading_deg)
    a = _dc.replace(c.anchor, body_class=cls, offset=off,
                    reason=f"carried by {carrier_res} ({why})"
                    + ("" if written else " [carrier kept whole on its "
                       "authored row]"))
    by_class[cls] = by_class.get(cls, 0) + 1
    # §16d (1): the orphan components in this file are not carried MEMBERS
    _mem = [i for i in grp if raw[i][0]] or list(grp)
    counts["bodies_elevated_carried"] = \
        counts.get("bodies_elevated_carried", 0) + len(_mem)
    tris = tuple(t for i in grp for t in raw[i][5])
    cut_comps = tuple(sorted({p.comp for i in grp if not raw[i][5]
                              for p in raw[i][0]}))
    return Body(body_id, cls, tuple(sorted(p.comp for p in parts)), a,
                _split.body_resource_name(m.resource, body_id, off),
                tuple(sorted(p.pid for p in parts)), feet=(),
                merged_into=carrier_res, merged_into_written=written,
                cut_components=cut_comps, tris=tris, elevated=True,
                elevated_members=len(_mem),
                plan_box=_pc.hull_of(b for i in _mem for b in part_boxes[i])
                if part_boxes else _pc.box_of((), parts),
                geom_box=(_geom_hull(grp, part_boxes, geom_boxes)
                          if part_boxes else _pc.box_of((), parts)),
                foot_boxes=(_pc.foot_boxes([b for i in grp for b in part_boxes[i]])
                            if part_boxes else ()),
                fill=(_pc.fill_of(_pc.hull_of(b for i in grp
                                              for b in part_boxes[i]),
                                  [b for i in grp for b in part_boxes[i]])
                      if part_boxes else 1.0),
                bridge_of=_bf.body_bridge(bridge, grp),
                geom_pts=_geom_pts(raw, grp))


#: §16 (3)'s named residual: a body with no carrier the law will accept,
#: anchored on the ground under its own footprint with its authored y
#: kept.  Never at the datum, never dropped from the plan.
OWN_GROUND = "footless_own_ground"


def _own_ground_file(raw: _t.Sequence[_Raw], grp: _t.Sequence[int], m: Member,
                     u: Unit, surface: _ar.Surface, body_id: int,
                     counts: dict[str, int], by_class: dict[str, int],
                     part_boxes: _t.Sequence[_t.Sequence[tuple]] = (),
                     bridge: _t.Sequence[str] = (),
                     geom_boxes: _t.Sequence = ()) -> Body:
    """§16 (3): the body written at the GROUND UNDER ITS OWN FOOTPRINT.

    §14 (1) left a footless placement whose unit held no footed body on
    its authored row (``footless_no_carrier``), and §15's search silently
    dropped an elevated body it could find no carrier for — its geometry
    was in no file at all.  §16 (3) gives both the same answer: the file
    is anchored at its footprint centroid, where the design surface is
    read like any other body's, and its AUTHORED y is kept (``y_zero``
    0), so a roof authored 12 m up renders 12 m over the ground it stands
    on instead of on it."""
    parts = [p for i in grp for p in raw[i][0]]
    cls = raw[max(grp, key=lambda i: len(raw[i][0]))][1]
    box = (_pc.hull_of(b for i in grp for b in part_boxes[i]) if part_boxes
           else _pc.box_of((), parts))
    clat, clon = 0.5 * (box[0] + box[2]), 0.5 * (box[1] + box[3])
    z = _pc.ground_under(surface, _pc.foot_boxes(
        [b for i in grp for b in part_boxes[i]]) if part_boxes else (), box)
    off = authored_offset(clat, clon, 0.0, u.anchor[0], u.anchor[1], m.heading_deg)
    a = _ar.Anchor(cls, clat, clon, 0.0,
                   f"{OWN_GROUND}: no carrier the law accepts — the ground "
                   f"under its own footprint, authored y kept", z, off)
    by_class[cls] = by_class.get(cls, 0) + 1
    counts["footless_own_ground"] = counts.get("footless_own_ground", 0) + 1
    tris = tuple(t for i in grp for t in raw[i][5])
    cut_comps = tuple(sorted({p.comp for i in grp if not raw[i][5]
                              for p in raw[i][0]}))
    return Body(body_id, cls, tuple(sorted(p.comp for p in parts)), a,
                _split.body_resource_name(m.resource, body_id, off),
                tuple(sorted(p.pid for p in parts)), feet=(),
                cut_components=cut_comps, tris=tris, elevated=True,
                elevated_members=len(grp), plan_box=box,
                geom_box=(_geom_hull(grp, part_boxes, geom_boxes)
                          if part_boxes else box) or box,
                foot_boxes=(_pc.foot_boxes([b for i in grp for b in part_boxes[i]])
                            if part_boxes else ()),
                fill=(_pc.fill_of(_pc.hull_of(b for i in grp
                                              for b in part_boxes[i]),
                                  [b for i in grp for b in part_boxes[i]])
                      if part_boxes else 1.0),
                bridge_of=_bf.body_bridge(bridge, grp),
                geom_pts=_geom_pts(raw, grp))


def _unit_carried_file(raw: _t.Sequence[_Raw], grp: _t.Sequence[int],
                       m: Member, u: Unit, surface: _ar.Surface,
                       uc: _t.Any, body_id: int, counts: dict[str, int],
                       by_class: dict[str, int],
                       part_boxes: _t.Sequence[_t.Sequence[tuple]] = (),
                       bridge: _t.Sequence[str] = (),
                       geom_boxes: _t.Sequence = ()) -> Body:
    """issue #31 (§16 (3) NARROWED): the bodies of ``grp`` as ONE file on
    their FOOTPRINT UNIT's datum — the terminal's seat, not the ground
    under the jetway.

    THE DEFECT (owner RULINGS 2026-09-30y, the SPJC central-terminal
    read: "the terminal floats at one end and is sunk at the other,
    separating from its jetways"): a jetway's ``.obj`` carries no foot
    below the contact band, and an animated jetway is one kept-whole
    ``ANIM`` body the part cut cannot divide — either way a FOOTLESS
    body.  A terminal seated on its pad then refuses to carry it (§16a
    (2): the walls' own zero is the pad's and the ground under their feet
    is the DEM metres below), every fallback is refused by the
    carried-side test for the same reason, and §16 (3) wrote the jetway
    at the ground under its OWN footprint.  The terminal moved with its
    pad and the jetway stayed on the terrain.

    THE FILE IS THE UNIT'S SEAT.  ``y_zero`` is set so the body's zero
    plane is exactly the unit's datum ``uc.zero_z`` (the plane
    :func:`footprint_unit.bind_footprint_units` gave every footed member
    of the unit, ``p0`` of the composed unit after #174/#182), and the
    AUTHORED y is kept — a tunnel authored 4 m up renders 4 m over the
    terminal's floor, which is where the pack authored it.  The anchor's
    ``surface_z`` is still the ground under the body's own footprint, so
    the census can read how far the unit holds it off its own terrain;
    nothing is derived from it.

    ``merged_into`` names THE UNIT, because that is the carrier the law
    chose.  It is not a body resource, so the §15 (3) float instrument —
    which resolves ``merged_into`` to a body and measures the two zeros —
    finds no body beneath and leaves these files out of that class.  That
    is the honest reading (a datum has no zero of its own to disagree
    with, and the float against the unit plane is 0 by construction) and
    the count ``footless_carried_by_unit`` is what reports them instead.
    REPORTED, not decided: whether the instrument should grow a class of
    its own for a unit-carried body is the spec author's."""
    parts = [p for i in grp for p in raw[i][0]]
    cls = raw[max(grp, key=lambda i: len(raw[i][0]))][1]
    box = (_pc.hull_of(b for i in grp for b in part_boxes[i]) if part_boxes
           else _pc.box_of((), parts))
    clat, clon = 0.5 * (box[0] + box[2]), 0.5 * (box[1] + box[3])
    zg = _pc.ground_under(surface, _pc.foot_boxes(
        [b for i in grp for b in part_boxes[i]]) if part_boxes else (), box)
    # issue #10: the row is draped at the surface AT THE ANCHOR, so the
    # zero is read there — ``zero = surface(anchor) - y_zero`` — never at
    # the median ground under the footprint, which put the written zero
    # ``surface(anchor) - median`` off the unit's datum.  The median stays
    # the fallback for an anchor off the sheet.
    za = surface(clat, clon)
    z = za if za is not None else zg
    # the zero plane IS the unit's datum: ``zero = surface_z - y_zero``
    y_zero = (float(z) - float(uc.zero_z)) if z is not None else 0.0
    off = authored_offset(clat, clon, y_zero, u.anchor[0], u.anchor[1],
                          m.heading_deg)
    a = _ar.Anchor(cls, clat, clon, y_zero,
                   f"{uc.why} on "
                   + (f"pad {uc.where}" if uc.source in ("pad", "cluster_pad")
                      else (f"deck {uc.where}" if uc.source == "deck"
                            else "its median ground"))
                   + f" at {float(uc.zero_z):.2f}"
                   + ("" if zg is None
                      else f" (own ground {float(zg) - float(uc.zero_z):+.2f} m)"),
                   z, off)
    by_class[cls] = by_class.get(cls, 0) + 1
    counts[_fu.UNIT_CARRY] = counts.get(_fu.UNIT_CARRY, 0) + 1
    tris = tuple(t for i in grp for t in raw[i][5])
    cut_comps = tuple(sorted({p.comp for i in grp if not raw[i][5]
                              for p in raw[i][0]}))
    return Body(body_id, cls, tuple(sorted(p.comp for p in parts)), a,
                _split.body_resource_name(m.resource, body_id, off),
                tuple(sorted(p.pid for p in parts)), feet=(),
                merged_into=uc.unit, merged_into_written=True,
                cut_components=cut_comps, tris=tris, elevated=True,
                elevated_members=len(grp), plan_box=box,
                geom_box=(_geom_hull(grp, part_boxes, geom_boxes)
                          if part_boxes else box) or box,
                foot_boxes=(_pc.foot_boxes([b for i in grp for b in part_boxes[i]])
                            if part_boxes else ()),
                fill=(_pc.fill_of(_pc.hull_of(b for i in grp
                                              for b in part_boxes[i]),
                                  [b for i in grp for b in part_boxes[i]])
                      if part_boxes else 1.0),
                bridge_of=_bf.body_bridge(bridge, grp),
                geom_pts=_geom_pts(raw, grp))


def _note_tilted_kept_whole(m: Member, counts: dict[str, int],
                            refs: list[tuple[int, str, tuple[str, ...]]],
                            index: int) -> None:
    """#232, REPORTED NOT DECIDED: a placement kept WHOLE keeps its
    authored file, seat directives and all, because the stage does not
    write it.  Census it here — the one place a placement goes either
    SPLIT (written, and the writer strips them) or KEPT — so the owner's
    rule for a TILTED kept-whole object on a graded pad is read off
    numbers.  Nothing is changed."""
    found = _split.seat_owned_in_file(pristine_path(m))
    if found:
        counts["tilted_kept_whole"] = counts.get("tilted_kept_whole", 0) + 1
        refs.append((index, m.resource, found))


def _cut_and_file(record: Split, m: Member, write: bool, counts: dict[str, int],
                  splits: list[Split], kept: list[Kept], whole: list[Split],
                  *, always_write: bool,
                  tilted_whole: list[tuple[int, str, tuple[str, ...]]]) -> None:
    """The OBJ8 cut for one member's bodies, and where the record lands.

    ``always_write`` is §14 (1)'s change: a CARRIED footless placement is
    written even when it is one body, because its row must MOVE to the
    carrier's anchor — where the pre-§14 reading left a one-body placement
    exactly as authored (``one_body``), which for a shared-datum unit is
    the datum point 15.7 m under the building."""
    bodies = record.bodies
    index = record.index
    if len(bodies) < 2 and not always_write:
        counts["kept"] += 1
        counts["one_body"] += 1
        kept.append(Kept(index, m.id, m.resource, "one_body"))
        _note_tilted_kept_whole(m, counts, tilted_whole, index)
        whole.append(record)
        return
    files: tuple[_split.SplitFile, ...] = ()
    err = ""
    if write:
        cuts = [_split.BodyCut(b.body_id, b.cut_components, b.anchor.offset,
                               b.tris,
                               # 10-01k Q1: the seat tilt the writer bakes
                               (b.seat.grad if b.seat is not None
                                else _split.NO_TILT))
                for b in bodies]
        try:
            res = _split.split_obj8(pristine_path(m), cuts, m.resource,
                                    allow_single=always_write)
        except (OSError, ValueError, IndexError) as exc:
            counts["write_error"] += 1
            err = f"{type(exc).__name__}: {exc}"
        else:
            if res.kept_whole:
                counts["kept"] += 1
                counts[res.kept_whole] = counts.get(res.kept_whole, 0) + 1
                kept.append(Kept(index, m.id, m.resource, res.kept_whole))
                _note_tilted_kept_whole(m, counts, tilted_whole, index)
                whole.append(record)
                return
            files = res.files
    if err:
        kept.append(Kept(index, m.id, m.resource, err))
        counts["kept"] += 1
        _note_tilted_kept_whole(m, counts, tilted_whole, index)
        whole.append(record)
        return
    counts["split"] += 1
    counts["files"] += len(files) or len(bodies)
    # 10-01k Q1 (#162), REPORTED: a CARRIED body takes its carrier's
    # ANCHOR (§14) but not its seat ROTATION — it is written level on a
    # tilted carrier, so the pair separates by the tilt over the rider's
    # own reach.  Counted here, where a member's riders and its tilted
    # bodies are in hand together; the cross-member case is named in
    # ``placement_seat_tilt``'s doc and is not decided by this lane.
    _tilted = {b.new_resource for b in bodies
               if b.seat is not None and b.seat.applied}
    if _tilted:
        _riders = sum(1 for b in bodies if b.merged_into in _tilted)
        if _riders:
            counts["seat_tilt_level_rider"] = \
                counts.get("seat_tilt_level_rider", 0) + _riders
    if files and len(files) < len(bodies):
        # §16d (1): a body the cut left with NO TRIANGLE has no file, so
        # it has no DSF row either — a row on a name nothing wrote is an
        # OBJECT_DEF X-Plane cannot resolve.  Counted and dropped, never
        # silently carried (its geometry is inside an ANIM block another
        # body of the same placement owns).
        live = {f.body_id for f in files}
        counts["bodies_without_a_file"] = \
            counts.get("bodies_without_a_file", 0) + len(bodies) - len(files)
        record = _dc.replace(record,
                             bodies=tuple(b for b in bodies
                                          if b.body_id in live))
    splits.append(_dc.replace(record, files=files))



def _deck_rider(deck: "_bf.DeckPrint | None", parts: _t.Sequence[_t.Any],
                band_m: float, edge_m: float = 0.0) -> bool:
    """Issue #290: is a carried piece its DECK's own furniture — a
    railing, a lamp post, a sign gantry STANDING ON the road surface?

    True when at least half of the piece's parts stand over the deck's
    model footprint or within ``edge_m`` of it (``[deck] edge_m``: a
    parapet stands on the deck's edge), and the piece's LOWEST part is
    one of them, its base within ``band_m`` (``[basin]
    contact_band_m``) of the deck's authored surface there
    (:meth:`DeckPrint.top_at` — a ramp is read where the part stands).
    A terminal's facade glass beside a departures viaduct reaches down
    metres below the deck surface: not a rider.  MEASURED (HECA control
    ``hecaobjects_ctl``): T3's departures floor slabs at y 17.08 stand
    more than 6 m from ``T23/T3_road`` and stay with the terminal; the
    railings (y 16.93) stand 1-3 m off its edge."""
    if deck is None or not parts:
        return False
    tops = [deck.top_at(float(p.lat), float(p.lon), edge_m) for p in parts]
    n_over = sum(1 for y in tops if y is not None)
    if 2 * n_over < len(parts):
        return False
    k = min(range(len(parts)), key=lambda i: float(parts[i].base_y))
    return (tops[k] is not None
            and abs(float(parts[k].base_y) - tops[k]) <= band_m)


def _split_by_unit(groups: _t.Sequence[_t.Sequence[int]],
                   raw: _t.Sequence[_t.Any],
                   plan_wide: _t.Mapping[int, tuple],
                   welded: "_t.Mapping[int, _t.Iterable[int]] | None" = None,
                   pads: _t.Sequence[_ar.PadRing] = (),
                   counts: "dict | None" = None, name: str = ""
                   ) -> "tuple[list[list[int]], int]":
    """S6 (#30 / #10): cut every ground group along its bodies' §16g
    UNITS.  A body's unit is the unit most of its parts belong to
    (``plan_wide`` is the part-id join :func:`footprint_unit.
    plan_wide_seats` publishes); a body in no unit stays with the
    group's largest unit piece (it has no unit to disagree with).  A group
    whose bodies name one unit, or none, is returned unchanged — so a
    plan with no unit is byte-identical.  Returns the groups and how many
    extra groups the cut made.  A body standing on two or more flat
    BLOCKS of one cut unit takes ``pad_block_seat.seat_unit``'s block
    (the majority of its WELDED parts, issue #126)."""
    from .pad_block_seat import seat_unit as _seat_unit
    out: list[list[int]] = []
    n = 0
    for g in groups:
        # §14 (2): a basin is ONE rigid object — never cut by unit
        if any(raw[i][1] == _ar.BASIN for i in g):
            out.append(list(g))
            continue
        by: dict[str, list[int]] = {}
        free: list[int] = []
        for i in g:
            u = _seat_unit([p.pid for p in raw[i][0]], plan_wide, welded,
                           raw[i][3] if welded and len(raw[i]) > 3 else (),
                           pads, counts, name)
            if u is not None:
                by.setdefault(u, []).append(i)
            else:
                free.append(i)
        if len(by) < 2:
            out.append(list(g))
            continue
        pieces = sorted(by.values(), key=lambda q: (-len(q), q[0]))
        pieces[0] = sorted(pieces[0] + free)
        out.extend(sorted(q) for q in pieces)
        n += len(pieces) - 1
    return out, n
