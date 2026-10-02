"""ISSUE #31 — A FOOTLESS PLACEMENT RIDES WITH ITS TERMINAL UNIT
(§16 (3) NARROWED; owner RULINGS 2026-09-18s and the SPJC read of
2026-09-30y).

Owner, 09-18s: *"Do we need to recognize a jetway?  Anything that
intersects the building (and doesn't extend of hundreds of meters like a
railway) is just treated as part of that building and moves with it ...
the flat terminal area should include the jetways."*  Owner, 09-30y
(SPJC central terminal): *"the terminal floats at one end and is sunk at
the other, separating from its jetways."*

A jetway's ``.obj`` carries no foot below the contact band — the tunnel
hangs off the terminal and the rotunda stands on the terminal's own
floor — so it is a FOOTLESS body, and an animated jetway is one
kept-whole ``ANIM`` body besides.  §16 (3) wrote such a body at the
ground under its OWN footprint whenever the carrier search refused every
footed body of its unit, which a terminal on a pad always is (§16a (2):
the walls' zero is the pad's and the ground under their feet is the DEM
metres below).  The terminal then moved with its pad and the jetway
stayed on the terrain.

The twins are synthetic and hermetic: a hand-built terminal of two boxes
on a pad 10 m over flat ground, and a footless jetway box inside its
footprint.
"""
from __future__ import annotations

import io
import os

from auto_patch_v2.airport import anchor_rule as AR
from auto_patch_v2.airport import footprint_unit as FU
# ``placement_plan`` FIRST: ``placement_carrier`` <-> ``placement_census``
# is a declared cycle and only resolves when the carrier side is imported
# before the census side (auto_patch/CLAUDE.md's import-cycle gotcha).
from auto_patch_v2.airport import placement_plan as PP
from auto_patch_v2.airport import placement_census as PCEN  # noqa: E402

from test_v2objsplit import _box, _flat, _write_obj


#: the twin's law frame — the shipped values of ``[rebake]``/``[placement]``
#: the three readings below depend on, named once.
SPLIT_TOL_M = 0.3
ELEVATED_BASE_M = 0.5
TOUCH_M = 0.5                 # [placement] footprint_touch_m
BIND_GROUND_M = 0.5
COARSEN_REACH_M = 30.0
#: the terrain, and the pad the terminal unit is seated on
GROUND_Z = 100.0
PAD_Z = 110.0
#: the jetway's authored height above the terminal's floor
JETWAY_Y = 4.0

LAT0, LON0 = 40.0, -3.0
_ML, _MO = AR._m_per_deg(LAT0)


def _args(**kw):
    a = dict(split_tol_m=SPLIT_TOL_M, elevated_base_m=ELEVATED_BASE_M,
             bind_ground_m=BIND_GROUND_M, touch_m=TOUCH_M,
             coarsen_reach_m=COARSEN_REACH_M)
    a.update(kw)
    return a


def _part(pid, comp, dlat_m, dlon_m, side_m, foot_y, *, feet=True):
    """One part: a ``side_m`` square box at ``(dlat_m, dlon_m)`` metres
    from the placement row, its ground contact at authored ``foot_y``."""
    from auto_patch_v2.model.rebake import Part

    la, lo = LAT0 + dlat_m / _ML, LON0 + dlon_m / _MO
    la1, lo1 = la + side_m / _ML, lo + side_m / _MO
    return Part(pid=pid, comp=comp, lat=la, lon=lo, base_y=foot_y,
                area_m2=side_m * side_m, box=(la, lo, la1, lo1),
                feet=(((la, lo, foot_y), (la1, lo1, foot_y)) if feet else ()))


def _terminal_obj(tmp_path):
    """Two boxes 20 m apart: the terminal's own footed walls."""
    va, ta = _box(0.0, 0.0, side=16.0, h=8.0)
    vb, tb = _box(20.0, 0.0, side=16.0, h=8.0)
    tb = [(a + 8, b + 8, c + 8) for a, b, c in tb]
    return _write_obj(tmp_path / "terminal.obj", va + vb,
                      [("ATTR_LOD\t0 1000", ta + tb)])


def _jetway_obj(tmp_path, animated=False):
    """One box authored ``JETWAY_Y`` up — a jetway tunnel with no foot at
    the ground.  ``animated`` puts its whole geometry inside one
    top-level ``ANIM`` block, which the OBJ8 cut keeps WHOLE (§4.4)."""
    v, t = _box(0.0, 0.0, side=6.0, h=3.0)
    v = [(x, y + JETWAY_Y, z) for x, y, z in v]
    name = "jetway_anim.obj" if animated else "jetway.obj"
    if animated:
        return _write_obj(tmp_path / name, v, [("ATTR_LOD\t0 1000", [])],
                          anim=t)
    return _write_obj(tmp_path / name, v, [("ATTR_LOD\t0 1000", t)])


#: the terminal's own footprint reaches ``TERMINAL_SIDE_M`` north of the
#: placement row; a jetway bay set down ``FRONTAGE_GAP_M`` beyond it
#: OVERLAPS NOTHING and touches the frontage, which is the case §16 (3)
#: left on its own ground (a jetway standing OVER a terminal body is
#: already carried by §16a (2)'s unit-seat yield).
TERMINAL_SIDE_M = 16.0
FRONTAGE_GAP_M = 0.3
FAR_M = 400.0


def _plan(tmp_path, *, jetway_dlat_m=TERMINAL_SIDE_M + FRONTAGE_GAP_M,
          animated=False, icao="TEST"):
    """A one-``Unit`` plan: the terminal (two footed boxes on its pad) and
    a footless jetway ``jetway_dlat_m`` metres north of the row.  At the
    frontage gap the jetway touches the terminal's footprint and overlaps
    none of it; at ``FAR_M`` it touches nothing and is its own leaf."""
    from auto_patch_v2.model.rebake import Member, RebakePlan, Unit

    term = _terminal_obj(tmp_path)
    jet = _jetway_obj(tmp_path, animated=animated)
    t_parts = (_part(0, 0, 0.0, 0.0, TERMINAL_SIDE_M, 0.0),
               _part(1, 1, 0.0, 20.0, TERMINAL_SIDE_M, 0.0))
    # the jetway's own contact is its tunnel floor, JETWAY_Y up: no foot
    # below the contact band anywhere in the member -> FOOTLESS
    j_parts = (_part(2, 0, jetway_dlat_m, 4.0, 6.0, JETWAY_Y),)
    m_t = Member(id="dsf:obj1", resource="objects/terminal.obj",
                 authored_path=str(term), live_path=str(term),
                 heading_deg=0.0, parts=t_parts)
    m_j = Member(id="dsf:obj2", resource="objects/" + os.path.basename(str(jet)),
                 authored_path=str(jet), live_path=str(jet),
                 heading_deg=0.0, parts=j_parts)
    return RebakePlan(icao=icao, pack_name="pack",
                      pack_root=os.path.dirname(str(term)),
                      units=(Unit("u0", (LAT0, LON0), 0.0, (m_t, m_j)),),
                      skipped=(), counts={})


def _pad():
    """A ``building`` pad covering the whole plan, its own plane at
    ``PAD_Z`` — the terminal unit's datum (§16g (2))."""
    la1, lo1 = LAT0 + 200.0 / _ML, LON0 + 200.0 / _MO
    la0, lo0 = LAT0 - 50.0 / _ML, LON0 - 50.0 / _MO
    return AR.PadRing("building80", ((la0, lo0), (la0, lo1), (la1, lo1),
                                     (la1, lo0)), (PAD_Z,) * 4)


def _jetway_body(ss):
    """The one body of the jetway placement."""
    out = [b for s in ss.all if "jetway" in s.resource for b in s.bodies]
    assert len(out) == 1, [b.anchor.reason for b in out]
    return out[0]


# ── the rule ──────────────────────────────────────────────────────────────

def test_a_footless_jetway_inside_its_terminal_unit_rides_the_units_datum(
        tmp_path):
    """ISSUE #31: the jetway inside the terminal unit's footprint takes
    the UNIT's datum — the pad plane its terminal is seated on — and its
    record names the carrier.  Before this rule it took the ground under
    its own footprint (``footless_own_ground``) and stood 10 m under the
    floor it is authored against."""
    ss = PP.build_splits(_plan(tmp_path), _flat(GROUND_Z), (_pad(),),
                         write=False, **_args())
    assert ss.counts["footless"] == 1
    assert ss.counts["footless_carried"] == 1
    assert ss.counts["footless_no_carrier"] == 0
    assert ss.counts[FU.UNIT_CARRY] == 1
    assert ss.counts.get("footless_own_ground", 0) == 0
    assert ss.counts["elevated_own_files"] == 0      # §13 (1), bar 0
    b = _jetway_body(ss)
    # ONE zero plane with its terminal: the unit's datum, not the terrain
    zero = float(b.anchor.surface_z) - float(b.anchor.y_zero)
    assert abs(zero - PAD_Z) < 1e-6, (zero, b.anchor.reason)
    # the record names the carrier
    assert b.merged_into and b.merged_into.startswith("fu:")
    assert FU.UNIT_CARRY in b.anchor.reason
    assert "building80" in b.anchor.reason
    # ... and the terminal's own footed bodies sit on the same plane
    for s in ss.all:
        if "terminal" in s.resource:
            for q in s.bodies:
                if q.anchor.surface_z is not None and not q.elevated:
                    assert abs(float(q.anchor.surface_z)
                               - float(q.anchor.y_zero) - PAD_Z) < 1e-6


def test_an_animated_jetway_kept_whole_rides_the_unit_too(tmp_path):
    """ISSUE #31: an ANIMATED jetway is ONE kept-whole ``ANIM`` body the
    part cut cannot divide (§4.4) — and still footless, so it is carried
    by its unit on exactly the same reading.  The animation is why the
    class exists: no cut can give such a body feet."""
    ss = PP.build_splits(_plan(tmp_path, animated=True), _flat(GROUND_Z),
                         (_pad(),), write=False, **_args())
    assert ss.counts["footless"] == 1
    assert ss.counts["footless_carried"] == 1
    assert ss.counts[FU.UNIT_CARRY] == 1
    b = _jetway_body(ss)
    zero = float(b.anchor.surface_z) - float(b.anchor.y_zero)
    assert abs(zero - PAD_Z) < 1e-6, (zero, b.anchor.reason)


def test_a_footless_object_far_from_every_unit_keeps_its_own_ground(tmp_path):
    """§16 (3) STANDS where it is the only answer: a footless placement
    whose plan box lies inside no unit's footprint and touches no unit's
    frontage has no admissible carrier, and is written at the ground
    under its own footprint with its authored y kept."""
    ss = PP.build_splits(_plan(tmp_path, jetway_dlat_m=FAR_M),
                         _flat(GROUND_Z), (_pad(),), write=False, **_args())
    assert ss.counts["footless"] == 1
    assert ss.counts["footless_carried"] == 0
    assert ss.counts["footless_no_carrier"] == 1
    assert ss.counts[FU.UNIT_CARRY] == 0
    assert ss.counts["footless_own_ground"] == 1
    b = _jetway_body(ss)
    assert b.anchor.reason.startswith(PP.OWN_GROUND)
    # its AUTHORED y is kept, so it renders JETWAY_Y over its own ground
    assert abs(float(b.anchor.y_zero)) < 1e-9
    assert abs(float(b.anchor.surface_z) - GROUND_Z) < 1e-6


# ── the instruments ───────────────────────────────────────────────────────

def test_the_split_report_counts_move_from_no_footed_body_to_carried(tmp_path):
    """The census bars of ``tools/obj8_split_report``: the same jetway
    reads ``no footed body in the unit at all: 1`` where no unit admits
    it and ``carried`` plus the §16g (11) line where one does.  ONE
    instrument, read on both plans (CLAUDE.md: a second reading of the
    same population is the census-wrapper defect)."""
    import sys

    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__)))), "tools"))
    import obj8_split_report as R

    def _printed(ss):
        import contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            R.print_footless(ss.counts)
        return buf.getvalue()

    far = _printed(PP.build_splits(_plan(tmp_path, jetway_dlat_m=FAR_M),
                                   _flat(GROUND_Z), (_pad(),), write=False,
                                   **_args()))
    near = _printed(PP.build_splits(_plan(tmp_path), _flat(GROUND_Z),
                                    (_pad(),), write=False, **_args()))
    assert "1 with no footed body in the unit at all" in far
    assert "carried by their UNIT's datum (issue #31): 0" in far
    assert "0 with no footed body in the unit at all" in near
    assert "carried by their UNIT's datum (issue #31): 1" in near
    assert "(1 by part id" in near or "within the unit's" in near


def test_the_unit_carry_reason_is_one_string_in_both_modules():
    """The §16g (11) reason is spelled in ``footprint_unit`` and read in
    ``placement_census``, which cannot import it (the
    ``placement_carrier`` <-> ``placement_census`` cycle).  The two
    copies are pinned here — the same discipline the wire-protocol names
    are kept under (CLAUDE.md)."""
    assert PCEN.UNIT_CARRY == FU.UNIT_CARRY
    assert PCEN.OWN_GROUND == PP.OWN_GROUND


def test_a_unit_carried_body_is_not_counted_as_draped_on_the_ground(tmp_path):
    """§14's ``footless on ground`` bar (0) measures a file the writer
    DRAPED — its intended zero shifted so its own lowest vertex lands on
    the terrain.  A body on its unit's datum carries the distance from
    its own terrain to that plane in ``y_zero`` BY CONSTRUCTION, so it is
    excluded from the class and reported as ``footless_carried_by_unit``
    instead; reading it as a drape would bar the fix for the defect."""
    from auto_patch_v2.airport import placement_carrier as PC
    from auto_patch_v2.airport.placement_plan import to_placement_records

    # the unit datum BELOW the body's own ground: y_zero comes out
    # positive, which is the only shape §14's bar would have caught
    ss = PP.build_splits(_plan(tmp_path), _flat(PAD_Z + 10.0), (_pad(),),
                         write=False, **_args())
    sp, kp = to_placement_records(ss)
    c = PC.census_v14([q.to_dict() for q in sp], [q.to_dict() for q in kp],
                      elevated_base_m=ELEVATED_BASE_M,
                      split_tol_m=SPLIT_TOL_M, counts=ss.counts)
    b = _jetway_body(ss)
    assert float(b.anchor.y_zero) > ELEVATED_BASE_M, b.anchor.reason
    assert c["footless_on_ground"] == 0
    assert c["footless_at_datum"] == 0
