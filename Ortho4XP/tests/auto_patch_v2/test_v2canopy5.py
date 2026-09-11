"""THE FEET PAD ON BARE GROUND — round 5's twins (owner RULINGS
2026-09-11p (1)/(2)/(3); spec ``object-placement-spec.md`` §11a (3)).

Round 4 measured §11a (3)'s clause as a NO-OP at the owner's own site:
none of the 24 bodies of ``OldTerminal_FSX-LEMD38 / -LEMD84 / -LEMD60``
stood on a ``building`` face, so the relief target had no pad to be a
target of.  Round 5 attributed it — two refusals, both inside
``classify/evidence._body_pads``, and both pinned here:

1. THE FEET'S CONVEX HULL IS NOT A FOOTPRINT.  A colonnade's feet are a
   LINE of column bases; LEMD38's modules hulled to 5–21 m² over 22–114 m
   spans (a 0.18 m ribbon), and ``building_pad.min_area_m2`` folded
   1,101 of the 1,116 candidates.  The pad is the BODY's own plan
   footprint — ``airport/skirt.component_footprint`` over the body's
   components — and then the fold law needs no exemption.
2. THE OSM PADS' LOCATION GATE DOES NOT BIND A PACK BODY.  It screens the
   surrounding CITY's mapped buildings, a population a pack does not
   have; applied to bodies it refused 130 of LEMD38's 150 canopy modules,
   because Aerosoft's old terminal stands outside LEMD's apt.dat 130
   boundary and more than 200 m from graded apt.dat pavement.

Plus (2) the NEGATIVE relief offsets — measured as the CROSS-PLACEMENT
group's own law, not the skirt rule's — and (3) the ``_stand_in_dsftool``
isolation.

Hermetic: one hand-written OBJ8, hand-built groups, no pack, no mesh, no
environment.
"""
from __future__ import annotations

import subprocess

import pytest
from shapely.geometry import Polygon

from auto_patch_v2.airport import obj8 as O
from auto_patch_v2.airport import skirt as SK
from auto_patch_v2.classify import evidence as EV
from auto_patch_v2.law import Law
from auto_patch_v2.airport.pack_partition import PackPartition
from auto_patch_v2.model.rebake import Member, Part, Unit
from auto_patch_v2.planar import group as G

LAT, LON = 40.48, -3.56
DLAT = 1.0 / 111_132.0
DLON = 1.0 / (111_132.0 * 0.76)

#: the module: a roof 60 m x 8 m on nine columns 0.4 m square, the
#: columns authored on ONE LINE (z = 0) — LEMD38's shape
_PITCH, _ROOF_L, _ROOF_W, _COL = 7.0, 60.0, 8.0, 0.4


def _box(vt, tris, x0, x1, z0, z1, y0, y1):
    base = len(vt)
    for x, z in ((x0, z0), (x1, z0), (x1, z1), (x0, z1)):
        vt.append((x, y0, z))
        vt.append((x, y1, z))
    for i in range(4):
        a, b = base + 2 * i, base + 2 * ((i + 1) % 4)
        tris += [(a, a + 1, b), (a + 1, b + 1, b)]
    tris += [(base + 1, base + 3, base + 5), (base + 1, base + 5, base + 7)]


def _canopy_obj(path, rise: float = 2.4):
    """Nine columns on a line plus a roof slab — ONE file, one body."""
    vt: list = []
    tris: list = []
    for i in range(9):
        x = i * _PITCH
        y = i * rise / 8.0                      # the authored relief
        _box(vt, tris, x, x + _COL, -_COL / 2, _COL / 2, y, y + 5.0)
    _box(vt, tris, -1.0, _ROOF_L, -_ROOF_W / 2, _ROOF_W / 2, 5.0, 5.6)
    lines = ["A", "800", "OBJ", "", "TEXTURE none",
             f"POINT_COUNTS {len(vt)} 0 0 {3 * len(tris)}"]
    lines += [f"VT {x:.3f} {y:.3f} {z:.3f} 0 1 0 0 0" for x, y, z in vt]
    idx = [i for t in tris for i in t]
    for k in range(0, len(idx), 10):
        chunk = idx[k:k + 10]
        lines.append(("IDX10 " if len(chunk) == 10 else "IDX ")
                     + " ".join(str(i) for i in chunk))
    lines.append(f"TRIS 0 {len(idx)}")
    path.write_text("\n".join(lines) + "\n")
    return str(path)


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


@pytest.fixture(scope="module")
def canopy(tmp_path_factory, law):
    """``(path, cache, roof index, column indices)`` — the component order
    is ``solid_components``' own, so the roof is found by AREA, never by a
    guessed index."""
    p = _canopy_obj(tmp_path_factory.mktemp("v2canopy5") / "canopy.obj")
    cache = O.ResourceCache(law.tables.structures.basin.min_solid_thickness_m)
    areas = [SK.component_footprint(cache, p, (i,)).area
             for i in range(len(cache.components(p)))]
    roof = max(range(len(areas)), key=lambda i: areas[i])
    return p, cache, roof, tuple(i for i in range(len(areas)) if i != roof)


# ── the fake airport the pad law reads ──────────────────────────────────

class _Frame:
    def transformers(self):
        def to_xy(lon, lat):
            return ((lon - LON) / DLON, (lat - LAT) / DLAT)

        def to_ll(x, y):
            return (LON + x * DLON, LAT + y * DLAT)
        return to_xy, to_ll


class _Obj:
    def __init__(self, path):
        self.id = "dsf:obj0"
        self.resolved_path = path
        self.xy = (0.0, 0.0)
        self.heading_deg = 0.0


class _Partition:
    def __init__(self):
        self.member_object = {(0, 0): ("dsf:obj0", "objects/canopy.obj")}


class _Airport:
    def __init__(self, groups, path):
        self.groups = groups
        self.frame = _Frame()
        self.partition = _Partition()
        self.dsf_objects = [_Obj(path)]


def _group(path, comps, rise: float = 2.4, dz: float = 0.0):
    """A one-body group over ``ncomps`` components with the column feet on
    a line (the authored frame's ``(x, z)`` reaches the frame through
    ``placement_affine`` at heading 0: ``(x, -z)``)."""
    feet = tuple(G.Foot(LAT + (-dz) * DLAT, LON + (i * _PITCH) * DLON,
                        i * rise / 8.0) for i in range(9))
    return G.GroupSet(
        (G.Group(gid="canopy#b0", bodies=((0, 0, 0),), senior=(0, 0, 0),
                 y_zero=0.0, feet=feet, span_m=_PITCH * 8, cross_placement=False,
                 long_span=False, body_comps=((0, 0, tuple(comps)),)),),
        {(0, 0, 0): 0}, {})


def _pads(airport, law, pavement=None, runway=None):
    from shapely.geometry import Polygon as _P
    pav = pavement if pavement is not None else _P()
    rwy = runway if runway is not None else _P()
    return EV._body_pads(airport, law, [], 0, pav, rwy,
                         law.tables.structures.building_pad.min_area_m2,
                         airport._cache)


# ── 1. THE FOOTPRINT IS THE BODY'S, NOT ITS FEET' HULL ──────────────────

def test_component_footprint_is_only_the_named_components(canopy, law):
    """``component_footprint`` reads ONE body out of a file that holds
    many — which is the whole reason it exists (Aerosoft LEMD authors 150
    canopy modules into one ``.obj``)."""
    path, cache, roof_i, cols = canopy
    assert len(cache.components(path)) == 10     # nine columns + the roof
    whole = SK.footprint(cache, path)
    one_column = SK.component_footprint(cache, path, (cols[0],))
    roof = SK.component_footprint(cache, path, (roof_i,))
    assert one_column.area == pytest.approx(_COL * _COL, rel=1e-6)
    assert roof.area == pytest.approx((_ROOF_L + 1.0) * _ROOF_W, rel=1e-6)
    assert whole.area == pytest.approx(roof.area, rel=1e-6)   # the roof covers
    assert SK.component_footprint(cache, path, ()) is None



# ── 2/3 WITHDRAWN (owner RULINGS 2026-09-11q; spec §11b (1)) ────────────
#
# Round 5's bare-ground BODY PAD is withdrawn: the three owner rows got
# WORSE with it (worst body 1.94 -> 3.33 m, ``pad_flat`` 39 -> 98, HECA's
# released T3 bodies +1.5 -> +8.7 m), because a rigid plane cut into
# sloping ground STEPS where an unpadded neighbour straddles its edge.
# The twins that pinned the minting (the colonnade's pad, the min-area
# fold of a plan-arealess body, the pavement refusal, the location gate)
# are DELETED with the mechanism — a refuted mechanism is deleted, not
# kept gated.  What SURVIVES is the attribution the round bought and the
# round-6 law rests on:
#
#   * the body's own plan footprint is readable and is not its feet's
#     hull (:func:`test_component_footprint_is_only_the_named_components`
#     above) — ``airport/skirt.component_footprint`` and
#     ``Group.body_comps`` stand;
#   * a PACK body carries no OSM location gate (measured: the gate
#     refused 130 of LEMD38's 150 modules) — recorded in §11a "Measured
#     (round 5)", and nothing mints a body pad to apply it to;
#   * the NEGATIVE relief offsets are the cross-placement group's own
#     law, pinned below.
#
# Bodies on bare ground now take FOOT ROWS: ``test_v2canopy6.py``.


# ── 4. THE NEGATIVE RELIEF OFFSET IS THE CROSS-PLACEMENT GROUP'S ────────

def _part(pid, comp, feet, area=100.0):
    ff = tuple((LAT + b * DLAT, LON + a * DLON, float(y)) for a, b, y in feet)
    lat, lon = ff[0][0], ff[0][1]
    return Part(pid, comp, lat, lon, min(f[2] for f in ff), area,
                (lat, lon, lat, lon), ff, False)


def _member(mid, parts, deck=False):
    return Member(mid, f"objects/{mid}.obj", f"/p/objects/{mid}.obj",
                  f"/p/objects/{mid}.obj", 0.0, tuple(parts), elevated_deck=deck)


def _plan(members, abutments=((1, 2),)):
    unit = Unit("unit:0", (LAT, LON), 0.0, tuple(members))
    counts = {"members": len(members),
              "parts": sum(len(m.parts) for m in members),
              "contacts": 0, "abutments": len(abutments)}
    return PackPartition("ZZZZ", "pack", "/p", (unit,), (), counts, (),
                         tuple(abutments),
                         {(0, i): (m.id, m.resource) for i, m in enumerate(members)})


def test_a_negative_offset_needs_a_cross_placement_group(law):
    """MEASURED (11p (2)): all 12 of LEMD's negative-offset groups are
    CROSS-PLACEMENT.  ``y_zero`` is the SENIOR body's lowest ground
    contact (``Group.y_zero``), so a junior deck standing below it reads
    negative — and a single-body group cannot, its zero being the minimum
    over its own feet.  Not the skirt rule's class: 10 of the 12 carry no
    skirt reading anywhere in the group."""
    building = _member("TERM", [_part(1, 0, [(-10, -10, 0.0), (10, -10, 0.0),
                                             (10, 10, 0.0), (-10, 10, 0.0)],
                                      area=400.0)])
    # the canopy's feet stand 3 m BELOW the building's own low side
    canopy_m = _member("CANOPY", [_part(2, 0, [(30, 0, -3.0), (60, 0, -3.0)],
                                        area=90.0)], deck=True)
    gs = G.derive(_plan([building, canopy_m]), 0.0, 0.0)
    joined = next(g for g in gs.groups if len(g.bodies) == 2)
    offs = [f.y - joined.y_zero for f in joined.feet]
    assert min(offs) == pytest.approx(-3.0, abs=1e-9)
    assert joined.cross_placement
    # ... and every SINGLE-body group's offsets are non-negative by
    # construction, whatever its feet were authored at
    alone = G.derive(_plan([canopy_m], abutments=()), 0.0, 0.0).groups[0]
    assert min(f.y - alone.y_zero for f in alone.feet) >= 0.0


# ── 5. THE DSFTool STAND-IN IS ISOLATED (11p (3)) ───────────────────────

def test_the_dsftool_stand_in_restores_subprocess_run(tmp_path):
    """The order-dependent red: the helper patches an attribute of the
    STDLIB ``subprocess`` module, so nothing but ``monkeypatch`` can be
    trusted to put it back — the old restore captured the PREVIOUS test's
    fake and the next run shelled out to a deleted tmpdir's stand-in."""
    import sys
    sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
    from test_v2objsplit import _stand_in_dsftool
    from auto_patch_v2.airport import dsf_write as DW

    real = DW.subprocess.run
    with pytest.MonkeyPatch.context() as mp:
        _stand_in_dsftool(tmp_path, DW, mp)
        assert DW.subprocess.run is not real
    assert DW.subprocess.run is real
    assert subprocess.run is real
