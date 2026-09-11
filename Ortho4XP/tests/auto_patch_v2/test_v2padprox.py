"""Twins for RULINGS 2026-09-10ax (1) (lane ``v2padprox``) — A PAD FRONTS
PAVEMENT BY PROXIMITY, AND ITS LEVEL ROW IS ONE-WAY IN CONSTRUCTION.

Two defects in one row, both read off the owner's 1.0.310 LEMD build:

* PROXIMITY.  ``pads.pad_frontage_leaders`` took frontage only from
  SHARED vertices, so ``building4`` (way −10936, shape 924, 66,257 m², at
  40.4603701 −3.5756711) — 1.60 m from ``pav124``, 0.58 m from ``route6``
  and sharing NOTHING with either — had no frontage row at all and kept
  its DEM datum while the apron trend lifted the pavement: the pad ended
  1.58 m BELOW the apron it faces and the building floated over the drop
  (RULINGS 2026-09-10aw).  16 of LEMD's 43 pads are in that no-contact
  class.  A pad EDGE within ``[design] pad_frontage_m`` of a pavement
  EDGE now fronts it, shared vertex or not.
* ONE-WAY IN CONSTRUCTION.  The row's ``follows`` was the whole rim, the
  shared contacts included — and a shared contact is a PAVEMENT vertex
  (09-01g: one vertex, one value), so a pad's own mean reached back into
  the pavement and MOVED it (10at: ``why`` read ``pad_frontage_level``
  +1.30 m on the T4S apron corner).  The followers are now the pad's OWN
  vertices; a shared contact enters as a LEADER, on the right-hand side
  at its previous outer-round value (``solve/design`` §9b).

09c is untouched: the pad is still ONE PLANE targeting flat, hard at 1 %.
A pad fronting nothing — by identity OR by proximity — still keeps its
own DEM datum (09p (3)).
"""
from __future__ import annotations

import numpy as np
import pytest

from auto_patch_v2.classify.roles import Cell, Classification
from auto_patch_v2.constraints import generate
from auto_patch_v2.constraints.pads import (GEN_LEVEL, frontage_radius_m,
                                            pad_datum_withdrawn, pad_frontage,
                                            pad_frontage_level, pad_shared)
from auto_patch_v2.law import Law
from auto_patch_v2.model.airport import Airport, Runway, RunwayEnd, SceneryPack
from auto_patch_v2.model.constraints import Linear
from auto_patch_v2.model.frame import Frame
from auto_patch_v2.planar.build import build
from auto_patch_v2.solve import Status, solve_design

RUN_LEN = 1600.0
HALF_W = 22.5
Y0, Y1 = 140.0, 260.0
#: how far the pad's own terrain stands below the apron's in the fixture
DIP_M = 3.0


def _rect(x0, y0, x1, y1):
    return ((x0, y0), (x1, y0), (x1, y1), (x0, y1))


class _Dem:
    """Terrain that DIPS under every pad site: a pad on its own ground and
    a pad on its frontage are ``DIP_M`` apart, so the twins can tell them
    apart by the solved level alone."""

    provenance = {"synthetic": "dip"}

    def z(self, x: float, y: float) -> float:
        return 700.0 - DIP_M if x >= -99.0 and 160.0 <= y <= 280.0 else 700.0

    def bounds(self):
        return (-5000.0, -5000.0, 5000.0, 5000.0)


def _airport(law, dem):
    frame = Frame("ZZZZ", origin=(60.5, -135.5), identity_dp=11)
    ends = (RunwayEnd("09", (-RUN_LEN / 2, 0.0), (60.5, -135.5), 0.0, 0.0,
                      700.0, "fixture"),
            RunwayEnd("27", (RUN_LEN / 2, 0.0), (60.5, -135.5), 0.0, 0.0,
                      700.0, "fixture"))
    rw = Runway("09/27", 45.0, 1, ends, 3, "D")
    pack = SceneryPack("fixture", "apt.dat", "0", (), ())
    return Airport("ZZZZ", "Synthetic", frame, 700.0, (rw,), (), (), {}, (),
                   (), (), (), (), (), (), pack, dem, law.ruleset_key)


def _map(law, cells):
    airport = _airport(law, _Dem())
    pm, _st = build(airport, Classification(tuple(cells), (), {}, ()), law)
    return airport, pm


def _solve(law, cells):
    airport, pm = _map(law, cells)
    cs, _c, _w = generate(pm, law, airport)
    sol, rep = solve_design(pm, cs, law)
    assert sol.status in (Status.OPTIMAL, Status.FEASIBLE), sol.status
    return pm, np.asarray(sol.z, float), rep


def _face(pm, ref):
    return next(f for f in pm.faces.values() if f.ref == ref)


def _verts(pm, ref):
    f = _face(pm, ref)
    out = set(pm.ring_vertices(f.ring))
    for h in (f.holes or ()):
        out |= set(pm.ring_vertices(h))
    return out


RUNWAY = Cell(0, "runway", "09/27", _rect(-RUN_LEN / 2, -HALF_W, RUN_LEN / 2, HALF_W),
              (), 3, "D", "airside", "runway", {})


def _gap_cells(gap_m: float):
    """An apron ending at x = −100 and a detached pad starting ``gap_m``
    east of it.  No ring of the two is within ``weld_spacing_m``, so the
    planar build shares NO vertex: frontage here is proximity or nothing.
    The apron's own terrain is 700 m, the pad's ``DIP_M`` below."""
    x0 = -100.0 + gap_m
    return [RUNWAY,
            Cell(1, "apron", "apronA", _rect(-260.0, Y0, -100.0, Y1), (),
                 None, None, "airside", "apron", {}),
            Cell(2, "building", "padA", _rect(x0, 180.0, x0 + 120.0, 240.0), (),
                 None, None, "airside", "pad", {})]


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


# ── the horizon is a LAW VALUE, and it has one derivation site ───────────

def test_the_proximity_horizon_is_a_law_value(law):
    r = frontage_radius_m(law)
    assert r > 0.0
    assert r == float(law.tables.emit.design.pad_frontage_m)


# ── (1) a pad NEAR an apron fronts it and follows it up ──────────────────

def test_a_pad_within_the_horizon_fronts_the_apron_it_shares_nothing_with(law):
    """``building4``'s class, synthetic: 1.5 m of gap, no shared vertex.
    Before 10ax this pad fronted NOTHING."""
    airport, pm = _map(law, _gap_cells(1.5))
    fid = _face(pm, "padA").id
    assert not (_verts(pm, "padA") & _verts(pm, "apronA")), "no shared vertex"
    assert pad_shared(pm, law).get(fid) is None
    assert "apron" in pad_frontage(pm, law).get(fid, {})
    rows = [r for r in pad_frontage_level(pm, law, airport)
            if f"face:{fid}" in r.source.inputs]
    assert rows and all(r.source.generator == GEN_LEVEL for r in rows)


def test_the_near_pad_follows_the_apron_up_off_its_own_dem(law):
    """The pad's own ground is ``DIP_M`` below the apron's.  Under 10ax it
    takes the apron's edge level, so it rises by most of that drop instead
    of sitting in its own hole."""
    pm, z, _rep = _solve(law, _gap_cells(1.5))
    pad = sorted(_verts(pm, "padA"))
    apron = sorted(_verts(pm, "apronA") - set(pad))
    lvl_pad, lvl_apron = float(np.mean(z[pad])), float(np.mean(z[apron]))
    assert lvl_pad >= 700.0 - DIP_M + 1.0, lvl_pad        # it rose over a metre
    assert abs(lvl_pad - lvl_apron) < DIP_M - 1.0, (lvl_pad, lvl_apron)


def test_a_pad_beyond_the_horizon_fronts_nothing_and_keeps_its_dem_datum(law):
    """10 m of gap is not a frontage: 09p (3) stands, the pad sits on its
    own ground and mints no level row."""
    gap = 10.0
    assert gap > frontage_radius_m(law)
    airport, pm = _map(law, _gap_cells(gap))
    fid = _face(pm, "padA").id
    assert fid not in pad_frontage(pm, law)
    assert not [r for r in pad_frontage_level(pm, law, airport)
                if f"face:{fid}" in r.source.inputs]
    assert not (pad_datum_withdrawn(pm, law) & _verts(pm, "padA"))
    pm2, z, _rep = _solve(law, _gap_cells(gap))
    pad = sorted(_verts(pm2, "padA"))
    assert abs(float(np.mean(z[pad])) - (700.0 - DIP_M)) <= 0.6, float(np.mean(z[pad]))


# ── (2) the row is ONE-WAY IN CONSTRUCTION: the pavement never follows ───

def test_no_level_row_makes_a_pavement_vertex_its_follower(law):
    """THE 10at DEFECT, structurally impossible.  ``solve/design`` §9b
    keeps a one-way row's FOLLOWER columns in the matrix and moves every
    other foot to the right-hand side, so a pavement vertex in ``follows``
    is exactly "the pad moves the pavement".  Measured on the LEMD solve
    arm before this lane: all 68 of main's pad-level rows carried one."""
    for cells in (_gap_cells(1.5), _hole_cells()):
        airport, pm = _map(law, cells)
        pav = set()
        for f in pm.faces.values():
            if f.role in ("apron", "taxiway", "runway", "service_road",
                          "parking_lot", "junction"):
                pav |= _verts(pm, f.ref)
        for r in pad_frontage_level(pm, law, airport):
            assert isinstance(r, Linear)
            assert r.follows, "a one-way row with no follower governs nothing"
            assert not (set(int(v) for v in r.follows) & pav), r.source.inputs


def _hole_cells():
    """The LEMD T4S shape — a pad cut out of the apron as a hole — with a
    MIXED rim: its western half shares the apron's hole ring, its eastern
    half stands in a notch the apron does not reach, so the pad keeps
    vertices of its own."""
    pad = _rect(-60.0, 180.0, 60.0, 240.0)
    return [RUNWAY,
            Cell(1, "apron", "apronA", _rect(-260.0, Y0, 20.0, Y1), (
                _rect(-60.0, 180.0, 20.0, 240.0),), None, None,
                "airside", "apron", {}),
            Cell(2, "building", "padA", pad, (), None, None,
                 "airside", "pad", {})]


def test_a_shared_contact_is_a_leader_never_a_follower(law):
    """09-01g: a shared vertex is ONE vertex with ONE value — the
    pavement's.  It carries the pavement's own laws into the row as a
    LEADER and is not withdrawn from the pavement body's DEM mean; the
    pad's OWN vertices are the followers, and they are withdrawn (§9b)."""
    airport, pm = _map(law, _hole_cells())
    fid = _face(pm, "padA").id
    pad, apron = _verts(pm, "padA"), _verts(pm, "apronA")
    shared = pad & apron
    assert shared and (pad - apron), "the fixture's rim must be MIXED"
    assert pad_shared(pm, law)[fid] == shared
    rows = [r for r in pad_frontage_level(pm, law, airport)
            if f"face:{fid}" in r.source.inputs]
    assert rows
    for r in rows:
        assert set(int(v) for v in r.follows) == pad - shared
    withdrawn = pad_datum_withdrawn(pm, law)
    assert pad - shared <= withdrawn
    assert not (shared & withdrawn)


def test_the_pad_stays_one_plane_within_its_one_per_cent(law):
    """09c is untouched by the proximity read: the pad the row now lifts is
    still ONE PLANE, planar to 0.01 m and inside the hard 1 % tilt."""
    pm, z, _rep = _solve(law, _gap_cells(1.5))
    vs = sorted(_verts(pm, "padA"))
    A = np.array([[1.0, *pm.vertices[v].xy] for v in vs])
    coef, *_ = np.linalg.lstsq(A, z[vs], rcond=None)
    assert float(np.abs(A @ coef - z[vs]).max()) <= 0.01
    span = max(1.0, max(pm.vertices[v].xy[0] for v in vs)
               - min(pm.vertices[v].xy[0] for v in vs))
    assert float(z[vs].max() - z[vs].min()) <= 0.01 * span + 0.05
