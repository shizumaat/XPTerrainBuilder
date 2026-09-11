"""THE LINE OBJECT (owner RULINGS 2026-09-10bb, lane `v2fence`; spec
``othh-seat-artefacts-spec.md`` §16).

The LEMD read: body 1626 is 38 parts of 5 resources over 1,406 m with ONE
ground part — a `LEMDzaun` fence component — and its single foot seated
`Terminal4_green-LEMD50` 6.86 m under its own ground.  A fence, a kerb, a
jet-blast line, a light string forms NO rigid body with what it touches,
founds NO foot for one, and DRAPES on the design surface.

Seven twins, hermetic and v2-pure:

1. the READER on authored geometry: a 500 m fence sheet is a line object,
   a 30 m wall 3 m thick is not (10bb's "ratio < 20 still joins");
2. the reader is per RESOURCE: a file with one ribbon and one blob is not
   a line object (what keeps the terminals' own walls out of the class);
3. a 500 m fence touching two buildings 300 m apart on ground 4 m
   different: two building bodies, each at ITS own ground, the fence
   draped between them;
4. the fence's own seat is per SEGMENT — its stations carry their own
   deltas and the body is marked ``line_object``;
5. a 2.5 m kerb string drapes the same way;
6. the WRITER applies the drape per vertex: the vertices at the low end
   move by the low station's delta, those at the high end by the high's;
7. a structure-seated member (a deck / plate) is never a line object.
"""
from __future__ import annotations

import numpy as np
import pytest

from auto_patch_v2.airport import line_object as LO
from auto_patch_v2.airport import obj8 as O
from auto_patch_v2.emit import rebake as R
from auto_patch_v2.law import Law


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


# ── authored geometry ────────────────────────────────────────────────────

def _obj(path, tris_xyz):
    """An OBJ8 of the given triangles ``[( (x,y,z), (x,y,z), (x,y,z) )]``."""
    vt: list[tuple[float, float, float]] = []
    idx: list[int] = []
    for t in tris_xyz:
        for p in t:
            idx.append(len(vt))
            vt.append(p)
    lines = ["A", "800", "OBJ", "", "TEXTURE none",
             f"POINT_COUNTS {len(vt)} 0 0 {len(idx)}"]
    lines += [f"VT {x:.3f} {y:.3f} {z:.3f} 0 1 0 0 0" for x, y, z in vt]
    for k in range(0, len(idx), 10):
        chunk = idx[k:k + 10]
        lines.append(("IDX10 " if len(chunk) == 10 else "IDX ")
                     + " ".join(str(i) for i in chunk))
    lines.append(f"TRIS 0 {len(idx)}")
    path.write_text("\n".join(lines) + "\n")
    return str(path)


def _sheet(x0, x1, z, y0, y1):
    """A vertical sheet from ``x0`` to ``x1`` at plan ``z`` — a fence."""
    return [((x0, y0, z), (x1, y0, z), (x1, y1, z)),
            ((x0, y0, z), (x1, y1, z), (x0, y1, z))]


def _slab(x0, x1, z0, z1, y0, y1):
    """A closed-ish box: four walls and a lid — a building."""
    c = [(x0, z0), (x1, z0), (x1, z1), (x0, z1)]
    out = []
    for i in range(4):
        (ax, az), (bx, bz) = c[i], c[(i + 1) % 4]
        out += [((ax, y0, az), (bx, y0, bz), (bx, y1, bz)),
                ((ax, y0, az), (bx, y1, bz), (ax, y1, az))]
    out += [((x0, y1, z0), (x1, y1, z0), (x1, y1, z1)),
            ((x0, y1, z0), (x1, y1, z1), (x0, y1, z1))]
    return out


def test_the_reader_takes_the_fence_and_leaves_the_wall(tmp_path, law):
    """16.1 rule 1.  A 500 m fence sheet 2 m high: plan-box diagonal 500 m
    over a plan-area width of 0 — a line object.  A 30 m wall 3 m thick
    and 2 m high: ratio 10, under ``line_object_ratio`` 20 — NOT one, so
    it still joins the building it touches (10bb's own example)."""
    rb = law.tables.structures.rebake
    assert rb.line_object_ratio == pytest.approx(20.0)
    cache = O.ResourceCache(0.05)
    fence = _obj(tmp_path / "fence.obj", _sheet(-250.0, 250.0, 0.0, 0.0, 2.0))
    wall = _obj(tmp_path / "wall.obj", _slab(-15.0, 15.0, -1.5, 1.5, 0.0, 2.0))
    assert LO.is_line_object(cache, fence, rb)
    length, width, height = LO.component_shape(cache.geometry(fence),
                                               cache.components(fence)[0])
    assert (length, width, height) == pytest.approx((500.0, 0.0, 2.0))
    assert not LO.is_line_object(cache, wall, rb)
    lw, ww, _h = LO.component_shape(cache.geometry(wall), cache.components(wall)[0])
    assert lw / ww < rb.line_object_ratio


def test_the_verdict_is_per_resource_not_per_component(tmp_path, law):
    """16.1 rule 1, the measured deviation: per COMPONENT the class
    swallows building walls (at LEMD 4,207 of 9,423 ground parts).  A file
    holding one ribbon AND one blob is not a line object."""
    rb = law.tables.structures.rebake
    cache = O.ResourceCache(0.05)
    mixed = _obj(tmp_path / "mixed.obj",
                 _sheet(-250.0, 250.0, 0.0, 0.0, 2.0)
                 + _slab(1000.0, 1030.0, -15.0, 15.0, 0.0, 2.0))
    comps = cache.components(mixed)
    assert len(comps) == 2
    assert sum(LO.is_line_shaped(cache.geometry(mixed), c, rb) for c in comps) == 1
    assert not LO.is_line_object(cache, mixed, rb)


def test_a_tall_wall_is_not_low_enough(tmp_path, law):
    """16.1 rule 1: the height gate.  LEMD's fences stand 3.07–5.90 m, so
    ``line_object_max_h`` is 6.0 — a 9 m curtain wall is out of the class
    however thin it is in plan."""
    rb = law.tables.structures.rebake
    assert rb.line_object_max_h == pytest.approx(6.0)
    cache = O.ResourceCache(0.05)
    curtain = _obj(tmp_path / "curtain.obj", _sheet(-100.0, 100.0, 0.0, 0.0, 9.0))
    assert not LO.is_line_object(cache, curtain, rb)


# ── the seat ─────────────────────────────────────────────────────────────

def _part(pid, comp, lat, lon, base_y, feet, line=False, half=1e-5):
    return R.Part(pid, comp, lat, lon, base_y, 100.0,
                  (lat - half, lon - half, lat + half, lon + half),
                  tuple(feet), line)


def _member(name, parts):
    return R.Member(name, f"objects/{name}.obj", name, name, 0.0, tuple(parts))


def _plan(units, contacts):
    return R.RebakePlan("ZZZZ", "p", "/p", tuple(units), (), {}, tuple(contacts))


def _surface(table):
    """``{lat: z}`` with linear-ish lookup by the nearest key."""
    def f(lat, _lon):
        k = min(table, key=lambda t: abs(t - lat))
        return (table[k], False)
    return f


#: 300 m apart in latitude; the fence runs the whole way and 100 m past.
#: The ANCHOR sits mid-way, so its rendered y = 0 plane is 702 and each
#: building's own correction clears ``min_delta_m``.
_ANCHOR = 0.00135
_A, _B = 0.0, 0.0027
_FENCE_FEET = [(-0.0009, 0.0, 0.0), (_A, 0.0, 0.0), (_ANCHOR, 0.0, 0.0),
               (_B, 0.0, 0.0), (0.0036, 0.0, 0.0)]
_GROUND = {-0.0009: 700.0, _A: 700.0, _ANCHOR: 702.0, _B: 704.0, 0.0036: 704.0}


def _fence_plan():
    """A 500 m fence (one line part, five stations) touching a building at
    each end; the buildings are 300 m apart and their ground differs by
    4 m.  The buildings' own parts carry no feet — LEMD50 stands 0.67 m
    over the pack datum — so only rule 4 can seat them."""
    fence = _member("LEMDzaun", [_part(0, 0, 0.00135, 0.0, 0.0, _FENCE_FEET,
                                       line=True, half=0.0019)])
    a = _member("LEMD50", [_part(1, 0, _A, 0.0, 0.67, ())])
    b = _member("LEMD49", [_part(2, 0, _B, 0.0, 0.67, ())])
    return _plan([R.Unit("unit:0", (_ANCHOR, 0.0), 0.0, (fence, a, b))], [(0, 1), (0, 2)])


def test_the_fence_founds_neither_building(law):
    """16.1 rules 2 + 4 — the LEMD site in miniature.  Before 10bb the two
    buildings joined the fence's body and took its ONE foot; now the fence
    binds nothing, and each building is its own ORPHAN body seated on the
    design surface under itself."""
    res = R.seat(_fence_plan(), _surface(_GROUND), law)
    c = res.counts()
    assert res.line_bodies == 1 and res.line_edges_dropped == 2
    assert res.orphan_bodies_seated == 2 and c["orphan_bodies"] == 2
    by = {m.resource: m for m in res.units[0].members}
    # each building seats on ITS OWN ground, not on the fence's one foot
    assert by["objects/LEMD50.obj"].delta_m == pytest.approx(-2.67, abs=1e-6)
    assert by["objects/LEMD49.obj"].delta_m == pytest.approx(1.33, abs=1e-6)
    # three bodies: the fence and one per building, none of them shared
    ks = [sorted({k for _c, k, _d in by[r].part_deltas})
          for r in ("objects/LEMDzaun.obj", "objects/LEMD50.obj", "objects/LEMD49.obj")]
    assert len({k[0] for k in ks}) == 3


def test_the_fence_drapes_on_its_own_stations(law):
    """16.1 rule 3: the fence is seated PER SEGMENT — one delta per
    station, the low end at 700 and the high end at 704, and the body is
    recorded as a line object."""
    res = R.seat(_fence_plan(), _surface(_GROUND), law)
    m = {x.resource: x for x in res.units[0].members}["objects/LEMDzaun.obj"]
    assert len(m.line_stations) == len(_FENCE_FEET)
    assert {c for c, *_x in m.line_stations} == {0}
    # the anchor's ground is 702, so the stations run −2 … +2 m
    ds = sorted(d for *_x, d in m.line_stations)
    assert ds[0] == pytest.approx(-2.0) and ds[-1] == pytest.approx(2.0)
    assert "LINE OBJECT" in m.note
    k = next(k for k in res.clusters if k.line_object)
    assert k.n_parts == 1 and not k.orphan
    assert res.counts()["line_stations"] == len(_FENCE_FEET)


def test_a_kerb_string_drapes_too(law):
    """16.1 rule 1/3: a 2.5 m kerb string is a line object by the same
    reader and drapes by the same segment seat — no special case."""
    rb = law.tables.structures.rebake
    cache = O.ResourceCache(0.05)
    import tempfile
    import pathlib
    with tempfile.TemporaryDirectory() as d:
        kerb = _obj(pathlib.Path(d) / "kerb.obj", _sheet(-120.0, 120.0, 0.0, 0.0, 2.5))
        assert LO.is_line_object(cache, kerb, rb)
    feet = [(-0.0009, 0.0, 0.0), (0.0, 0.0, 0.0), (0.0009, 0.0, 0.0)]
    k = _member("KERB", [_part(0, 0, 0.0, 0.0, 0.0, feet, line=True, half=0.001)])
    pl = _plan([R.Unit("u", (0.0, 0.0), 0.0, (k,))], [])
    res = R.seat(pl, _surface({-0.0009: 700.0, 0.0: 702.0, 0.0009: 705.0}), law)
    st = res.units[0].members[0].line_stations
    # deltas are measured from the member's rendered y = 0 plane (the
    # anchor's ground, 702), so the kerb falls 2 m at one end and
    # rises 3 m at the other — it is not one number
    assert sorted(round(d, 3) for *_x, d in st) == [-2.0, 0.0, 3.0]


def test_the_writer_drapes_the_vertices(tmp_path, law):
    """16.1 rule 3 at the WRITE half: each vertex takes the delta of the
    station nearest it in plan, so the fence's low end moves by the low
    station's delta and its high end by the high one's — one component,
    several vertex deltas."""
    from auto_patch.engine_v2 import _line_drape
    path = _obj(tmp_path / "zaun.obj", _sheet(0.0, 0.0, -250.0, 0.0, 2.0)
                + _sheet(0.0, 0.0, 250.0, 0.0, 2.0))
    geom = O.parse_obj8(path)
    comps = O.solid_components(geom)
    # z is SOUTH: the sheet at z = −250 lies 250 m NORTH of the anchor
    stations = [(ci, 0.00225, 0.0, 5.0) for ci in range(len(comps))] \
        + [(ci, -0.00225, 0.0, 9.0) for ci in range(len(comps))]
    out = _line_drape(geom, comps, stations, (0.0, 0.0), 0.0)
    ys = {round(float(geom.vertices[i][2]), 1): d for i, d in out.items()}
    assert ys[-250.0] == pytest.approx(5.0)
    assert ys[250.0] == pytest.approx(9.0)


def test_a_structure_seated_member_is_never_a_line_object(law):
    """16.1 rule 1 / 14.1 rule 4: a deck or plate member is governed by
    its structure seat.  The plan never marks one, and a part that
    carries ``line`` still takes its unit's structure delta when the seat
    fixes it — OTHH's tunnel decks and basin plates are untouched."""
    m = _member("tunnel1", [_part(0, 0, 0.0, 0.0, 0.0,
                                  [(0.0, 0.0, 0.0)], line=True)])
    plate = R.Member(m.id, m.resource, m.authored_path, m.live_path, 0.0, m.parts,
                     plate_y=1.0, plate_stations=((0.0, 0.0),))
    pl = _plan([R.Unit("u", (0.0, 0.0), 0.0, (plate,))], [])
    res = R.seat(pl, _surface({0.0: 710.0}), law)
    assert res.units[0].datum == "plate"
    assert res.line_bodies == 0 and not res.units[0].members[0].line_stations


def test_the_plan_round_trips_the_line_verdict():
    """§16.2 C2: ``Part.line`` travels in the plan (version 7; the
    current ``PLAN_VERSION`` is 8, spec §17's abutments)."""
    from auto_patch_v2.model.rebake import PLAN_VERSION, RebakePlan
    assert PLAN_VERSION == 8
    pl = _fence_plan()
    back = RebakePlan.from_json(pl.to_json())
    assert [p.line for u in back.units for m in u.members for p in m.parts] == \
        [True, False, False]
    assert np.isclose(back.units[0].members[0].parts[0].feet[0][0], _FENCE_FEET[0][0])
