"""Twins for RULINGS 2026-09-10l (lane ``v2padlevel``) — THE PAD TAKES
THE PAVEMENT'S EDGE LEVEL.

The owner, answering question 10k-1 with (A): "Pad takes the apron edge
level".  A building pad that FRONTS pavement (shares an edge with an
apron / taxiway / road face) is flush with that pavement's edge; the
apron never tiers down into the terminal it fronts; the pad stays flat
(≤ 1 %, 09c); and its own DEM datum (09p (3)) is for a pad that fronts
NO pavement.  Where a pad fronts two pavements at different levels it
tilts within its 1 % to meet both, and beyond 1 % it follows the SENIOR
pavement (``precedence.toml`` order) and the residual is reported.

The mechanism is ``constraints.pads.pad_frontage_level``: one FLUSH row
(cap 0) per pad vertex to the nearest vertex OF THE FRONTING PAVEMENT
ITSELF — never a shared one, which is a pad vertex too — ONE-WAY with the
pad vertex as the follower, priced at ``[design] pad_flat`` for the
senior role and at the law's own weight for a junior one.
"""
from __future__ import annotations

import numpy as np
import pytest

from auto_patch_v2.classify.roles import Cell, Classification
from auto_patch_v2.constraints import generate
from auto_patch_v2.constraints.pads import (GEN_LEVEL, LEVEL_JUNIOR_RULING,
                                            LEVEL_RULING, pad_flats,
                                            pad_frontage, pad_frontage_level,
                                            pad_shared)
from auto_patch_v2.law import Law
from auto_patch_v2.model.airport import Airport, Runway, RunwayEnd, SceneryPack
from auto_patch_v2.model.constraints import Diff
from auto_patch_v2.model.frame import Frame
from auto_patch_v2.planar.build import build
from auto_patch_v2.solve import Status, solve_design
from auto_patch_v2.solve.design import (one_way_rulings, pad_flat_rulings,
                                        pad_level_rulings)

RUN_LEN = 1600.0
HALF_W = 22.5
#: the apron band, clear of the code-3 strip
Y0, Y1 = 140.0, 260.0


def _rect(x0, y0, x1, y1):
    return ((x0, y0), (x1, y0), (x1, y1), (x0, y1))


class _Dem:
    """Terrain that DIPS under the pad band: the pad's own DEM datum is
    3 m below the apron's, so a pad that takes its ground and a pad that
    takes its frontage are far apart."""

    provenance = {"synthetic": "dip"}

    def z(self, x: float, y: float) -> float:
        return 697.0 if (-62.0 <= x <= 62.0 and 178.0 <= y <= 242.0) else 700.0

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


def _solve(law, cells, dem=None):
    airport = _airport(law, dem or _Dem())
    pm, _st = build(airport, Classification(tuple(cells), (), {}, ()), law)
    cs, _c, _w = generate(pm, law, airport)
    sol, rep = solve_design(pm, cs, law)
    assert sol.status in (Status.OPTIMAL, Status.FEASIBLE), sol.status
    return pm, np.asarray(sol.z, float), rep, cs


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


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


# ── the law register ─────────────────────────────────────────────────────

def test_the_level_rulings_are_registered_one_way_and_the_senior_is_the_pad_weight(law):
    """The heads are law-table data, never literals in the solve: both are
    ONE-WAY (the pad follows and never pulls) and both name the datum
    suppression; only the SENIOR head carries the pad's own plane weight."""
    lvl, ow, pf = pad_level_rulings(law), one_way_rulings(law), pad_flat_rulings(law)
    assert {LEVEL_RULING, LEVEL_JUNIOR_RULING} <= lvl
    assert {LEVEL_RULING, LEVEL_JUNIOR_RULING} <= ow
    assert LEVEL_RULING in pf and LEVEL_JUNIOR_RULING not in pf


# ── (1) a pad fronting an apron takes the apron's edge ───────────────────

def _fronting_cells():
    """One apron with a pad cut out of it as a hole, sharing that whole
    ring — the LEMD T4S shape: ``pav16`` and ``building16``."""
    pad = _rect(-60.0, 180.0, 60.0, 240.0)
    return [RUNWAY,
            Cell(1, "apron", "apronA", _rect(-260, Y0, 260, Y1), (pad,),
                 None, None, "airside", "apron", {}),
            Cell(2, "building", "padA", pad, (), None, None, "airside", "pad", {})]


def test_a_pad_fronting_an_apron_is_flush_with_it_and_does_not_tier_it(law):
    """The pad's ground is 3 m below the apron's; under 10l the pad takes
    the APRON'S edge level, so the apron does not step down into it and
    the pad does not sit on its own terrain."""
    pm, z, _rep, _cs = _solve(law, _fronting_cells())
    pad, apron = _verts(pm, "padA"), _verts(pm, "apronA")
    shared = pad & apron
    assert shared, "the pad shares the apron's hole ring"
    own = sorted(pad - apron)
    apron_only = sorted(apron - pad)
    lvl_pad = float(np.mean(z[own])) if own else float(np.mean(z[sorted(shared)]))
    lvl_apron = float(np.mean(z[apron_only]))
    # flush: the pad sits at the apron's level, NOT at its own 697 m ground
    assert abs(lvl_pad - lvl_apron) <= 0.30, (lvl_pad, lvl_apron)
    assert lvl_pad > 699.0, lvl_pad
    # and the plane is flat within the 1 % ceiling over its own span
    span = max(1.0, max(pm.vertices[a].xy[0] for a in pad)
               - min(pm.vertices[a].xy[0] for a in pad))
    spread = float(z[sorted(pad)].max() - z[sorted(pad)].min())
    assert spread <= 0.01 * span + 0.05, (spread, span)


def test_the_pads_own_flatness_never_prices_a_vertex_the_pavement_shares(law):
    """The tier the ruling forbids came through the flatness target: a
    cap-0 row at ``pad_flat`` footed on the apron's own edge flattens the
    APRON.  Those pairs are gone; the level rows carry the plane instead."""
    airport = _airport(law, _Dem())
    pm, _st = build(airport, Classification(tuple(_fronting_cells()), (), {}, ()), law)
    shared = pad_shared(pm, law)[_face(pm, "padA").id]
    assert shared
    for r in pad_flats(pm, law, airport):
        assert not ({r.a, r.b} & shared), r


def test_every_level_row_is_one_way_with_the_pad_as_the_follower(law):
    """"The apron never tiers down into a building it fronts": the pad is
    the follower of every level row and the leader is the PAVEMENT'S OWN
    vertex, never one the pad shares."""
    airport = _airport(law, _Dem())
    pm, _st = build(airport, Classification(tuple(_fronting_cells()), (), {}, ()), law)
    pad = _verts(pm, "padA")
    shared = pad_shared(pm, law)[_face(pm, "padA").id]
    rows = pad_frontage_level(pm, law, airport)
    assert rows
    for r in rows:
        assert isinstance(r, Diff) and r.cap == 0.0
        assert r.source.generator == GEN_LEVEL
        assert r.follows == r.a and r.a in pad
        assert r.b not in pad and r.b not in shared


# ── (2) a pad fronting nothing keeps its DEM datum ───────────────────────

def _detached_cells():
    """The same pad, moved off the apron entirely — it fronts nothing."""
    return [RUNWAY,
            Cell(1, "apron", "apronA", _rect(-260, Y0, -100, Y1), (),
                 None, None, "airside", "apron", {}),
            Cell(2, "building", "padA", _rect(60.0, 200.0, 180.0, 250.0), (),
                 None, None, "airside", "pad", {})]


def test_a_pad_fronting_nothing_mints_no_level_row_and_keeps_its_dem_datum(law):
    """09p (3) stands where 10l does not reach: the pad sits on its own
    ground (697 m here), not on the apron 160 m away."""
    airport = _airport(law, _Dem())
    pm, _st = build(airport, Classification(tuple(_detached_cells()), (), {}, ()), law)
    pad_fid = _face(pm, "padA").id
    assert pad_fid not in pad_frontage(pm, law)
    assert not [r for r in pad_frontage_level(pm, law, airport)
                if f"face:{pad_fid}" in r.source.inputs]
    pm2, z, _rep, _cs = _solve(law, _detached_cells())
    pad = sorted(_verts(pm2, "padA"))
    assert abs(float(np.mean(z[pad])) - 700.0) <= 0.6, float(np.mean(z[pad]))


# ── (3)/(4) two pavements: the pad tilts, then follows the senior ────────

def _two_pavement_cells(drop_m: float):
    """A pad between an APRON on one side and a TAXIWAY on the other, the
    taxiway's own surface ``drop_m`` below the apron's over the 120 m the
    pad spans.  The taxi family is SENIOR to the apron."""
    pad = _rect(-60.0, 180.0, 60.0, 240.0)

    class _Tilt:
        provenance = {"synthetic": "two levels"}

        def z(self, x, y):
            return 700.0 if y < 210.0 else 700.0 - drop_m

        def bounds(self):
            return (-5000.0, -5000.0, 5000.0, 5000.0)

    cells = [RUNWAY,
             Cell(1, "apron", "apronA", _rect(-260, Y0, 260, 180.0), (),
                  None, None, "airside", "apron", {}),
             Cell(2, "building", "padA", pad, (), None, None, "airside", "pad", {}),
             Cell(3, "primary_parallel", "taxiN", _rect(-260, 240.0, 260, 263.0),
                  (), None, "D", "airside", "taxi", {})]
    return cells, _Tilt()


def _pad_plane(pm, z, ref="padA"):
    vs = sorted(_verts(pm, ref))
    ys = np.array([pm.vertices[v].xy[1] for v in vs])
    zs = z[vs]
    lo = zs[ys <= ys.min() + 1.0].mean()      # the apron side
    hi = zs[ys >= ys.max() - 1.0].mean()      # the taxiway side
    return lo, hi, abs(hi - lo) / max(1.0, ys.max() - ys.min())


def test_a_pad_between_two_pavements_half_a_percent_apart_tilts(law):
    """0.3 m over the pad's 60 m of depth is 0.5 % — inside the 1 %
    ceiling, so ONE plane meets both frontages and the pad tilts."""
    cells, dem = _two_pavement_cells(0.3)
    pm, z, _rep, _cs = _solve(law, cells, dem)
    lo, hi, tilt = _pad_plane(pm, z)
    assert 0.0015 <= tilt <= 0.010 + 1e-6, (lo, hi, tilt)
    assert hi < lo, (lo, hi)                   # it falls toward the taxiway


def test_beyond_one_percent_the_pad_follows_the_senior_pavement(law):
    """1.8 m over 60 m is 3 % — no plane meets both inside the 1 %
    ceiling.  The TAXI family outranks the apron in ``precedence.toml``,
    so the pad follows the taxiway and the miss against the apron is the
    reported residual of the ``pad_level`` family."""
    cells, dem = _two_pavement_cells(1.8)
    pm, z, rep, _cs = _solve(law, cells, dem)
    lo, hi, tilt = _pad_plane(pm, z)
    assert tilt <= 0.010 + 2e-3, tilt          # the hard ceiling holds
    taxi = sorted(_verts(pm, "taxiN") - _verts(pm, "padA"))
    apron = sorted(_verts(pm, "apronA") - _verts(pm, "padA"))
    z_taxi, z_apron = float(np.mean(z[taxi])), float(np.mean(z[apron]))
    pad = float(np.mean(z[sorted(_verts(pm, "padA"))]))
    assert abs(pad - z_taxi) < abs(pad - z_apron), (pad, z_taxi, z_apron)
    fam = rep.families.get(GEN_LEVEL)
    assert fam and fam["rows"] > 0
    assert fam["missed"] > 0 and fam["max_m"] > 0.0, fam
