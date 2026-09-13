"""§36 TWINS — THE END-AROUND TAXIWAY CEILING, PORTED (owner RULINGS
2026-09-13j item 2, ruled 13q item 2; ``constraints/eat.py``).

What these pin:

* THE VALUE is the law's, ``end_z + max(0, D - setback) * slope - tail``,
  with the AUTHORITY's slope / setback and the aircraft's tail — and it is
  normally NEGATIVE relative to the runway end (the depression is the
  point, never clamped);
* RECOGNITION starts at ``min_crossing_m``: pavement closer in is an
  ordinary runway-end connector and is not pinned at all;
* the FAR BOUND is the stricter of the regulation's own ``D_clear`` and
  the recognition cap;
* the ROUTED WRAP is required — an apron lying under a projected
  centreline with no taxi route crossing it is not an end-around taxiway
  (LEMD's 149 false pins);
* the pin is CUT-ONLY: a rect whose regulation value sits above the
  pavement's DEM everywhere lifts pavement into the air and pins nothing;
* the rect YIELDS to every senior pin and to a rigid group;
* the RAMP either side is the taxi family's own law — the EAT mints no
  ramp row of its own, and the pinned vertices keep the taxi ``Diff``
  rows that grade to them.
"""
from __future__ import annotations

import math

import pytest

from auto_patch_v2.constraints import eat
from auto_patch_v2.law import Law
from auto_patch_v2.model.airport import (Airport, Runway, RunwayEnd,
                                         SceneryPack, TaxiEdge, TaxiNode)
from auto_patch_v2.model.constraints import Flat, Pin, Source
from auto_patch_v2.model.frame import Frame
from auto_patch_v2.model.planar import Edge, EdgeKind, Face, PlanarMap, Vertex


class _FlatDem:
    provenance = {"synthetic": "flat"}

    def z(self, x: float, y: float) -> float:
        return 100.0

    def bounds(self):
        return (-40000.0, -40000.0, 40000.0, 40000.0)


@pytest.fixture(scope="module")
def law():
    """KCLT's own authority: FAA (40:1 from the end, no setback)."""
    return Law.for_airport("KCLT")


# the fixture runway 18/36: 2,000 m along +y, 45 m wide, code 4 / letter E
RWY_A = (0.0, 0.0)          # the 36 end
RWY_B = (0.0, 2000.0)       # the 18 end (outward = +y)
DEM_Z = 100.0


def _airport(law, *, width=45.0, code=4, letter="E", routes=True,
             cross_x=0.0) -> Airport:
    frame = Frame("KCLT", origin=(35.2, -80.95), identity_dp=11)
    ends = (RunwayEnd("36", RWY_A, (35.2, -80.95), 0.0, 0.0, None, "fixture"),
            RunwayEnd("18", RWY_B, (35.2, -80.95), 0.0, 0.0, None, "fixture"))
    rw = Runway("18/36", width, 1, ends, code, letter)
    pack = SceneryPack("fixture", "apt.dat", "0", (), ())
    nodes: dict[int, TaxiNode] = {}
    edges: tuple[TaxiEdge, ...] = ()
    if routes:
        # a taxi route crossing the extended centreline 400 m beyond the
        # 18 end: the ROUTED WRAP clause 1 asks for
        nodes = {1: TaxiNode(1, (cross_x - 50.0, 2400.0), "taxi"),
                 2: TaxiNode(2, (cross_x + 50.0, 2400.0), "taxi")}
        edges = (TaxiEdge(1, 2, "EAT", False, False, "E"),)
    return Airport("KCLT", "Synthetic", frame, DEM_Z, (rw,), (), (),
                   nodes, edges, (), (), (), (), (), (), pack, _FlatDem(),
                   law.ruleset_key)


def _map(faces_spec, *, dem_z=None) -> PlanarMap:
    """A map of disjoint quads: ``faces_spec`` is
    ``[(role, ((x, y), ...)), ...]``.  Every vertex is its own; no face
    shares one, which is all these twins need (the rect law reads rings).

    THE RUNWAY FACE IS ALWAYS THERE: without two CIFP thresholds the
    ceiling's anchor is the DEM at the runway-family vertex nearest the
    end (``_ends``), so a map with no runway face carries no readable end
    — which is itself the behaviour ``test_an_end_with_no_runway_face_...``
    pins."""
    faces_spec = [("runway", _quad(-22.5, 0.0, 22.5, 2000.0))] + list(faces_spec)
    verts: dict[int, Vertex] = {}
    edges: dict[int, Edge] = {}
    faces: dict[int, Face] = {}
    vid = eid = 0
    for fid, (role, pts) in enumerate(faces_spec):
        ids = []
        for (x, y) in pts:
            # ``dem_z`` is the PAVEMENT's DEM only: the runway keeps its
            # own, so the cut test moves without moving the anchor
            verts[vid] = Vertex(vid, (x, y),
                                (35.0 + vid * 1e-6, -80.0 - vid * 1e-6),
                                DEM_Z if (dem_z is None or role == "runway")
                                else dem_z, (fid,))
            ids.append(vid)
            vid += 1
        cyc = []
        for a, b in zip(ids, ids[1:] + ids[:1]):
            edges[eid] = Edge(eid, a, b, fid, None, EdgeKind.BOUNDARY)
            cyc.append(eid)
            eid += 1
        faces[fid] = Face(fid, role, f"pav{fid}", tuple(cyc), (), 4, "E")
    return PlanarMap("KCLT", verts, edges, faces, {})


def _quad(x0, y0, x1, y1):
    return ((x0, y0), (x1, y0), (x1, y1), (x0, y1))


def _crossing(d0=400.0, d1=430.0, half=20.0, role="cross_connector"):
    """A crossing face straddling the extended centreline at D d0..d1."""
    return (role, _quad(-half, 2000.0 + d0, half, 2000.0 + d1))


# ── THE VALUE ────────────────────────────────────────────────────────────

def test_the_value_is_the_law_and_is_not_clamped(law):
    """``ceiling(D) = max(0, D - setback) * slope - tail`` — normally
    NEGATIVE, and only the SURFACE's own rise is floored."""
    rs = law.ruleset.eat
    tail = law.tables.common.eat.tail_height_m.value(code_letter="E")
    got = eat.eat_ceiling_offset(400.0, rs.slope, rs.setback_m, tail)
    assert got == pytest.approx(400.0 * rs.slope - tail)
    assert got < 0.0                        # the depression IS the law
    # inside the setback the surface reads its inner-edge height, never a
    # fictitious below-end surface
    assert eat.eat_ceiling_offset(-10.0, 0.02, 60.0, 20.1) == pytest.approx(-20.1)


def test_d_clear_is_the_root_of_the_ceiling(law):
    """``D_clear = setback + tail/slope`` — the regulation's own geometry,
    not a tunable: the ceiling is exactly zero there."""
    for slope, setback, tail in ((0.025, 0.0, 20.1), (0.02, 60.0, 24.4)):
        d = eat.eat_clear_distance(slope, setback, tail)
        assert eat.eat_ceiling_offset(d, slope, setback, tail) == pytest.approx(0.0)
    assert eat.eat_clear_distance(0.0, 0.0, 20.1) == float("inf")


def test_the_pin_is_the_law_at_the_rect_mid_distance(law):
    ap = _airport(law)
    pm = _map([_crossing()])
    rows = eat.eat_pins(pm, law, ap)
    rs = law.ruleset.eat
    tail = law.tables.common.eat.tail_height_m.value(code_letter="E")
    want = DEM_Z + eat.eat_ceiling_offset(415.0, rs.slope, rs.setback_m, tail)
    assert rows and all(isinstance(r, Pin) for r in rows)
    assert {round(r.z, 6) for r in rows} == {round(want, 6)}
    assert eat.STATS["eat_pins"]["rects_accepted"] == 1


# ── RECOGNITION ──────────────────────────────────────────────────────────

def test_pavement_inside_the_minimum_crossing_distance_is_not_an_eat(law):
    """Closer than ``min_crossing_m`` the pavement is an ordinary
    runway-end connector; the ceiling there would be violently
    infeasible."""
    d = float(law.tables.common.eat.min_crossing_m)
    ap = _airport(law)
    pm = _map([_crossing(d - 60.0, d - 30.0)])
    assert eat.eat_pins(pm, law, ap) == []
    # ... and just beyond it, the same face IS recognised
    pm2 = _map([_crossing(d + 10.0, d + 40.0)])
    assert eat.eat_pins(pm2, law, ap)


def test_a_rect_beyond_the_far_bound_is_refused_by_name(law):
    """The stricter of the regulation's ``D_clear`` and the recognition
    cap; the refusal names which fired."""
    cap = float(law.tables.common.eat.max_crossing_m)
    ap = _airport(law)
    pm = _map([_crossing(cap + 50.0, cap + 80.0)])
    assert eat.eat_pins(pm, law, ap) == []
    assert eat.STATS["eat_pins"]["refused_far_bound"] == 1
    assert any("max_crossing_m" in r["reason"] or "D_clear" in r["reason"]
               for r in eat.RECTS if not r["accepted"])


def test_without_a_routed_wrap_nothing_is_pinned(law):
    """LEMD's 149 false pins: an apron under a projected centreline is not
    an end-around taxiway.  The route set is the aircraft network."""
    pm = _map([_crossing(role="apron")])
    assert eat.eat_pins(pm, law, _airport(law, routes=False)) == []
    assert eat.STATS["eat_pins"]["refused_no_wrap"] == 1
    # the same geometry WITH a taxi route crossing it is recognised
    assert eat.eat_pins(pm, law, _airport(law))


def test_pavement_running_along_the_corridor_is_another_facility(law):
    """CYXY's 327 m apron smear: a rect longer than ``rect_max_along_m``
    along ``s`` runs ALONG the extended centreline and is refused whole."""
    along = float(law.tables.common.eat.rect_max_along_m)
    ap = _airport(law)
    pm = _map([_crossing(350.0, 350.0 + along + 50.0)])
    assert eat.eat_pins(pm, law, ap) == []
    assert eat.STATS["eat_pins"]["refused_along_corridor"] >= 1


def test_a_small_runway_carries_no_eat(law):
    """End-around taxiways exist at transport-category runways only (CYXY
    02/20 aimed its corridor across the GA apron)."""
    ap = _airport(law, code=2)
    assert eat.eat_pins(_map([_crossing()]), law, ap) == []
    assert eat.STATS["eat_pins"]["runways_below_code"] == 1


def test_the_pin_is_cut_only(law):
    """A rect whose regulation value sits ABOVE the pavement's own DEM
    everywhere would LIFT pavement into the air: it pins nothing."""
    ap = _airport(law)
    rs = law.ruleset.eat
    tail = law.tables.common.eat.tail_height_m.value(code_letter="E")
    # the value at D 415 is end_z - 9.7 m; put the pavement's DEM well
    # under it and the rect stops cutting
    low = DEM_Z + eat.eat_ceiling_offset(415.0, rs.slope, rs.setback_m, tail) - 5.0
    pm = _map([_crossing()], dem_z=low)
    assert eat.eat_pins(pm, law, ap) == []
    assert eat.STATS["eat_pins"]["refused_no_cut"] == 1


# ── PRECEDENCE AND THE RAMP ──────────────────────────────────────────────

def test_a_node_that_is_already_hard_is_never_overridden(law):
    """The runway profile, the seam law, a water datum and a rigid group
    all outrank the rect (v1's own rule; v2's reduction would otherwise
    resolve two pins on one vertex by generator ORDER)."""
    ap = _airport(law)
    pm = _map([_crossing()])
    rows = list(eat.eat_pins(pm, law, ap))
    assert rows
    src = Source("seam_pin", "synthetic", ())
    senior = Pin(rows[0].v, 999.0, src)
    kept, n = eat.withdraw_against_senior(rows + [senior])
    assert n == 1
    assert senior in kept
    assert all(r.v != senior.v for r in kept
               if isinstance(r, Pin) and r.source.generator == eat.GEN)
    # a rigid group member is withdrawn for the same reason
    grp = Flat(tuple(r.v for r in rows[:2]), src)
    kept2, n2 = eat.withdraw_against_senior(rows + [grp])
    assert n2 == 2


def test_the_generator_mints_pins_only(law):
    """The EAT states an ANCHOR, never a law edge (v1's reach-envelope
    blow-up): the ramps either side are the taxi family's own rows."""
    rows = eat.eat_pins(_map([_crossing()]), law, _airport(law))
    assert rows and all(isinstance(r, Pin) for r in rows)


def test_the_rects_published_for_the_census_are_the_final_pins(law):
    """``eat_rects`` is read off the FINAL constraint set, so a vertex the
    withdrawal dropped is never reported by the census (lockstep)."""
    class _CS:
        def __init__(self, pins):
            self.pins = tuple(pins)

    pm = _map([_crossing()])
    rows = list(eat.eat_pins(pm, law, _airport(law)))
    full = eat.eat_rects(pm, _CS(rows))
    assert len(full) == 1
    assert len(full[0]["vertices"]) == len(rows)
    assert full[0]["end"] == "18" and full[0]["runway"] == "18/36"
    kept, _n = eat.withdraw_against_senior(
        rows + [Pin(rows[0].v, 1.0, Source("seam_pin", "x", ()))])
    trimmed = eat.eat_rects(pm, _CS([r for r in kept if isinstance(r, Pin)]))
    assert len(trimmed[0]["vertices"]) == len(rows) - 1


def test_an_authority_with_no_surface_is_a_no_op(law, monkeypatch):
    """An authority stating no EAT surface makes the family vacuous — the
    ``[icao.drainage]`` precedent, never an invented default."""
    import dataclasses as _dc
    rs = _dc.replace(law.tables.rulesets[law.ruleset_key], eat=None)
    tables = _dc.replace(law.tables,
                         rulesets={**law.tables.rulesets, law.ruleset_key: rs})
    silent = _dc.replace(law, tables=tables)
    assert eat.eat_pins(_map([_crossing()]), silent, _airport(law)) == []


def test_an_end_with_no_readable_anchor_pins_nothing(law):
    """v1: "a pin at a guessed datum would masquerade as regulation" — an
    end whose elevation cannot be read (no CIFP chord AND no runway face
    to sample) is counted and skipped, never anchored at a guess."""
    verts: dict[int, Vertex] = {}
    edges: dict[int, Edge] = {}
    faces: dict[int, Face] = {}
    role, pts = _crossing()
    ids = []
    for vid, (x, y) in enumerate(pts):
        verts[vid] = Vertex(vid, (x, y), (35.0 + vid * 1e-6, -80.0 - vid * 1e-6),
                            DEM_Z, (0,))
        ids.append(vid)
    cyc = []
    for eid, (a, b) in enumerate(zip(ids, ids[1:] + ids[:1])):
        edges[eid] = Edge(eid, a, b, 0, None, EdgeKind.BOUNDARY)
        cyc.append(eid)
    faces[0] = Face(0, role, "pav0", tuple(cyc), (), 4, "E")
    pm = PlanarMap("KCLT", verts, edges, faces, {})
    assert eat.eat_pins(pm, law, _airport(law)) == []
    assert eat.STATS["eat_pins"]["ends_without_anchor"] == 2
