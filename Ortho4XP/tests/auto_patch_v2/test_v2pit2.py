"""Twins for RULINGS 2026-09-10an (lane ``v2pit`` round 2) — A STRUCTURE'S
RIM IS FLUSH WITH THE PAVEMENT IT SITS IN.

The ruling: a basin's rim / retaining-wall CREST is flush with the pavement
it sits in — the rim vertices are members of that apron body (its affine
datum and its within-shape rows) and carry NO LOWER TARGET of their own;
the wall's DROP is the FLOOR ring's business.

What round 1 (10k) established and these twins keep: a rim vertex the
pavement shares is pinned by NOTHING (``basins``' ``shared_with_ground``
skips it; the DEM-by-station pin is for a BARE rim only).  What round 2
found at LEMD's T4S pit corner is that "the ground's value carries the rim"
was a premise, not a row: ``why`` on ``v21779`` (apron ``pav16`` shared with
``tunnel_wall`` face 912) reported "FREE — no binding row blocks it, held by
bending alone", and EVERY row naming it is a one-sided CAP (``apron``
preferred tier / ring edge / body chord, ``pavement_ceiling``, ``no_step``
rate).  The per-body datum's three AFFINE rows say only where the body sits
and how it leans, so the pavement's hole edge is a FREE EDGE of the bending
sheet and the crest sat 0.45 m under the pavement beside it.

``constraints.structures.rim_level`` states the missing sentence as ONE
ONE-WAY row per (wall face, pavement role): the MEAN of the rim's contacts
against THE PAVEMENT'S OWN VALUE beside them, read through
``pads.frontage_leaders`` — ONE derivation of "where does the pavement stand
beside this vertex", shared with the pad frontage level of 10l/10y.  The rim
FOLLOWS: it rises to the pavement and never pulls the pavement down into the
pit, and it takes no target of its own, so the floor ring's pins are
untouched.
"""
from __future__ import annotations

import dataclasses as _dc

import numpy as np
import pytest
from shapely.geometry import Polygon

from auto_patch_v2.classify.roles import Cell, Classification
from auto_patch_v2.constraints import generate
from auto_patch_v2.constraints.structures import (GEN_RIM_LEVEL,
                                                  RIM_LEVEL_RULING)
from auto_patch_v2.constraints.structures import basins as basin_rows
from auto_patch_v2.constraints.structures import rim_contacts, rim_level
from auto_patch_v2.law import Law
from auto_patch_v2.model.airport import Airport, Runway, RunwayEnd, SceneryPack
from auto_patch_v2.model.constraints import Linear, Pin
from auto_patch_v2.model.frame import Frame
from auto_patch_v2.model.structures import Basin
from auto_patch_v2.planar.build import build
from auto_patch_v2.solve import Status, solve_design
from auto_patch_v2.solve.design import one_way_rulings, pad_level_rulings

RUN_LEN, HALF_W = 1200.0, 22.5
Y0, Y1 = 120.0, 220.0          # the apron band, clear of the code-3 strip
#: the rim ring cut out of the apron, and the basin's floor plate inside it
RIM = ((-40.0, 140.0), (40.0, 140.0), (40.0, 200.0), (-40.0, 200.0))
FLOOR = ((-30.0, 150.0), (30.0, 150.0), (30.0, 190.0), (-30.0, 190.0))
FLOOR_Z = 688.0


def _rect(x0, y0, x1, y1):
    return ((x0, y0), (x1, y0), (x1, y1), (x0, y1))


class _Slope:
    """A 1 % PLANE falling east, EXCAVATED inside the rim — the LEMD frame.

    The production DEM already contains the pit (Aerosoft's terminal
    basement is in the spain5m inset), so the rim vertices' own DEM samples
    stand metres UNDER the ground the apron sits on: at LEMD's T4S corner
    ``v21779``'s DEM reads 594.02 against an apron at 599.2.  Those samples
    are members of the apron body's affine datum, and with no row of its own
    the pavement's hole edge is a free edge that follows them down.  A
    fixture on a clean plane does not reproduce the defect."""

    provenance = {"synthetic": "1 % plane, excavated inside the rim"}

    def z(self, x: float, y: float) -> float:
        if -44.0 <= x <= 44.0 and 136.0 <= y <= 204.0:
            return FLOOR_Z
        return 700.0 + 0.01 * x

    def bounds(self):
        return (-5000.0, -5000.0, 5000.0, 5000.0)


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


RUNWAY = Cell(0, "runway", "09/27", _rect(-RUN_LEN / 2, -HALF_W, RUN_LEN / 2, HALF_W),
              (), 3, "D", "airside", "runway", {})


def _cells(wall_ref: str, floor_ref: str):
    """The LEMD shape: an apron whose HOLE is the structure's rim, the void
    (``retaining_wall``) between rim and floor, and the floor plate."""
    return [RUNWAY,
            Cell(1, "apron", "apronA", _rect(-200, Y0, 200, Y1), (RIM,),
                 None, None, "airside", "apron", {}),
            Cell(2, "retaining_wall", wall_ref, RIM, (FLOOR,),
                 None, None, "airside", "structure", {}),
            Cell(3, "tunnel_trench", floor_ref, FLOOR, (),
                 None, None, "airside", "structure", {})]


def _airport(law, cells, basins=()):
    frame = Frame("ZZZZ", origin=(60.5, -135.5), identity_dp=11)
    ends = (RunwayEnd("09", (-RUN_LEN / 2, 0.0), (60.5, -135.5), 0.0, 0.0, 700.0, "fixture"),
            RunwayEnd("27", (RUN_LEN / 2, 0.0), (60.5, -135.5), 0.0, 0.0, 706.0, "fixture"))
    rw = Runway("09/27", 45.0, 1, ends, 3, "D")
    pack = SceneryPack("fixture", "apt.dat", "0", (), ())
    airport = Airport("ZZZZ", "Synthetic", frame, 700.0, (rw,), (), (), {},
                      (), (), (), (), (), (), (), pack, _Slope(), law.ruleset_key)
    pm, _st = build(airport, Classification(tuple(cells), (), {}, ()), law)
    if basins:
        pm = _dc.replace(pm, basins=tuple(basins))
    return airport, pm


def _basin(wall_ref: str, floor_ref: str):
    return Basin("basin:0", ("obj:fixture",), FLOOR_Z, floor_ref, wall_ref,
                 tuple(FLOOR), wall_path=tuple(RIM), rim_estimate_m=699.0,
                 solid_min_z=FLOOR_Z, area_m2=4800.0)


def _face(pm, ref):
    return next(f for f in pm.faces.values() if f.ref == ref)


def _ring_and_holes(pm, ref):
    f = _face(pm, ref)
    out = set(pm.ring_vertices(f.ring))
    for h in (f.holes or ()):
        out |= set(pm.ring_vertices(h))
    return out


def _solved(law, wall_ref="basin_wall:0", floor_ref="basin_floor:0"):
    cells = _cells(wall_ref, floor_ref)
    airport, pm = _airport(law, cells, basins=[_basin(wall_ref, floor_ref)])
    cs, _counts, _walls = generate(pm, law, airport)
    sol, rep = solve_design(pm, cs, law)
    assert sol.status in (Status.OPTIMAL, Status.FEASIBLE), sol.status
    return pm, np.asarray(sol.z, float), cs, rep


def _apron_plane(pm, z):
    """The least-squares plane of the apron's OWN vertices (the rim's
    excluded) — "the apron's plane" the rim must lie on."""
    apron = _ring_and_holes(pm, "apronA")
    rim = set(pm.ring_vertices(_face(pm, "basin_wall:0").ring)) if any(
        f.ref == "basin_wall:0" for f in pm.faces.values()) else set()
    for f in pm.faces.values():
        if f.role == "retaining_wall":
            rim |= set(pm.ring_vertices(f.ring))
    own = sorted(apron - rim)
    P = np.array([[*pm.vertices[v].xy, 1.0] for v in own], float)
    y = np.array([float(z[v]) for v in own], float)
    coef, *_ = np.linalg.lstsq(P, y, rcond=None)
    return lambda v: float(coef[0] * pm.vertices[v].xy[0]
                           + coef[1] * pm.vertices[v].xy[1] + coef[2])


def _contacts(pm, wall_ref="basin_wall:0"):
    wall = _face(pm, wall_ref)
    apron = _ring_and_holes(pm, "apronA")
    return sorted(set(pm.ring_vertices(wall.ring)) & apron)


# ── the law register ─────────────────────────────────────────────────────

def test_the_rim_level_ruling_is_one_way_and_keeps_the_rim_in_its_bodys_datum(law):
    """The head is law-table data, never a literal in the solve.  ONE-WAY:
    the rim follows the pavement and never pulls it down.  NOT a
    ``pad_level`` head: 10an keeps the rim a MEMBER of its apron body's
    affine datum, where 10l withdraws a fronting pad from it."""
    assert RIM_LEVEL_RULING in one_way_rulings(law)
    assert RIM_LEVEL_RULING not in pad_level_rulings(law)


def test_the_flush_row_reaches_the_solve_through_the_generator_register(law):
    """Registered in ``constraints.GENERATORS``, so the row the ruling names
    is in every build's constraint set — not only in a direct call."""
    from auto_patch_v2.constraints import GENERATORS
    assert GEN_RIM_LEVEL in {name for name, _fn in GENERATORS}
    _pm, _z, cs, _rep = _solved(law)
    assert any(r.source.generator == GEN_RIM_LEVEL for r in cs.linears)


# ── (1) a basin rim in an apron ──────────────────────────────────────────

def test_the_rim_of_a_basin_in_an_apron_lies_on_the_aprons_plane(law):
    """The site's shape on a 1 % plane: the apron's hole ring IS the basin's
    rim (10k), and under 10an every rim vertex comes out on the apron's own
    plane — the pavement does not tier down into the pit."""
    pm, z, _cs, _rep = _solved(law)
    plane = _apron_plane(pm, z)
    contacts = _contacts(pm)
    assert contacts, "the rim IS the apron's hole ring — one vertex, one value"
    worst = max(abs(float(z[v]) - plane(v)) for v in contacts)
    assert worst <= 0.05, f"the rim stands {worst:.3f} m off the apron's plane"


def test_the_floor_ring_keeps_its_own_pins_at_the_basins_floor(law):
    """The wall's DROP is the floor ring's business (10an): the floor stays
    pinned at ``Basin.floor_z`` and the rim's flush row changes nothing
    about it."""
    cells = _cells("basin_wall:0", "basin_floor:0")
    airport, pm = _airport(law, cells, basins=[_basin("basin_wall:0", "basin_floor:0")])
    pins = {r.v: r for r in basin_rows(pm, law, airport) if isinstance(r, Pin)}
    floor_vs = set(pm.ring_vertices(_face(pm, "basin_floor:0").ring))
    assert floor_vs and all(pins[v].z == pytest.approx(FLOOR_Z) for v in floor_vs)
    pm2, z, _cs, _rep = _solved(law)
    floor2 = set(pm2.ring_vertices(_face(pm2, "basin_floor:0").ring))
    for v in floor2:
        assert float(z[v]) == pytest.approx(FLOOR_Z, abs=0.05)


def test_a_shared_rim_vertex_carries_no_lower_target_of_its_own(law):
    """10an, keeping 10k: no ``Pin`` on a shared rim vertex, and the only
    row the new generator mints on it is the ONE-WAY level row that FOLLOWS
    the pavement — never a target below it."""
    cells = _cells("basin_wall:0", "basin_floor:0")
    airport, pm = _airport(law, cells, basins=[_basin("basin_wall:0", "basin_floor:0")])
    contacts = set(_contacts(pm))
    pins = {r.v for r in basin_rows(pm, law, airport) if isinstance(r, Pin)}
    assert not (contacts & pins)
    rows = rim_level(pm, law, airport)
    assert rows, "the rim shares the apron: the flush row exists"
    for r in rows:
        assert isinstance(r, Linear)
        assert r.source.generator == GEN_RIM_LEVEL
        assert set(r.follows) <= contacts, "the RIM follows; the pavement leads"


# ── (2) the same rim shared with a retaining wall of a tunnel ────────────

def test_a_tunnel_walls_rim_in_an_apron_takes_the_same_flush_row(law):
    """LEMD's T4S corner is a ``tunnel_wall`` face, not ``basin_wall:<k>``
    — the SAME class (``retaining_wall``, 09-06b (1)), read by ONE reader,
    so the crest is flush there too."""
    pm, z, _cs, _rep = _solved(law, wall_ref="tunnel_wall", floor_ref="basin_floor:0")
    plane = _apron_plane(pm, z)
    contacts = _contacts(pm, "tunnel_wall")
    assert contacts
    worst = max(abs(float(z[v]) - plane(v)) for v in contacts)
    assert worst <= 0.05, f"the crest stands {worst:.3f} m off the apron's plane"


def test_rim_contacts_name_the_wall_the_pavement_and_the_pavements_own(law):
    """The reader is data: one group per (wall face, pavement face) with a
    shared vertex, the pavement's OWN vertices (off the rim) as leaders."""
    cells = _cells("basin_wall:0", "basin_floor:0")
    _airport_, pm = _airport(law, cells, basins=[_basin("basin_wall:0", "basin_floor:0")])
    groups = rim_contacts(pm, law)
    assert groups, "the apron shares the rim"
    for _fid, ref, role, contacts, own in groups:
        assert ref.split("#")[0] in ("basin_wall:0", "tunnel_wall")
        assert role == "apron"
        assert contacts and own and not (set(contacts) & own)


def test_a_rim_no_pavement_shares_mints_nothing(law):
    """A structure standing in bare ground keeps the DEM-by-station crest of
    09-03b L1 and this generator says nothing about it."""
    rim_far = _rect(-40.0, 400.0, 40.0, 460.0)
    floor_far = _rect(-30.0, 410.0, 30.0, 450.0)
    cells = [RUNWAY,
             Cell(1, "apron", "apronA", _rect(-200, Y0, Y1 and 200, Y1), (),
                  None, None, "airside", "apron", {}),
             Cell(2, "retaining_wall", "basin_wall:0", rim_far, (floor_far,),
                  None, None, "airside", "structure", {}),
             Cell(3, "tunnel_trench", "basin_floor:0", floor_far, (),
                  None, None, "airside", "structure", {})]
    airport, pm = _airport(law, cells)
    assert not any(g[1].split("#")[0] == "basin_wall:0" for g in rim_contacts(pm, law))
    assert rim_level(pm, law, airport) == []


def test_the_flush_row_reads_the_pavement_in_the_shared_band(law):
    """The row is stated in METRES OF SURFACE: the contact coefficients sum
    to +1 and the leaders' to −1, so its residual IS the rim's height under
    the pavement beside it."""
    cells = _cells("basin_wall:0", "basin_floor:0")
    airport, pm = _airport(law, cells, basins=[_basin("basin_wall:0", "basin_floor:0")])
    contacts = set(_contacts(pm))
    row = next(iter(rim_level(pm, law, airport)))
    assert sum(c for v, c in row.terms if v in contacts) == pytest.approx(-1.0)
    assert sum(c for v, c in row.terms if v not in contacts) == pytest.approx(1.0)
    assert row.hi == 0.0 and row.lo is None, "ONE-SIDED: only the rim UNDER the pavement is priced"
