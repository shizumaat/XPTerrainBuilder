"""THE LINE OBJECT (owner RULINGS 2026-09-10bb, lane `v2fence`; spec
``othh-seat-artefacts-spec.md`` §16).

The LEMD read: body 1626 is 38 parts of 5 resources over 1,406 m with ONE
ground part — a `LEMDzaun` fence component — and its single foot seated
`Terminal4_green-LEMD50` 6.86 m under its own ground.  A fence, a kerb, a
jet-blast line, a light string forms NO rigid body with what it touches,
founds NO foot for one, and DRAPES on the design surface.

THE SEAT IS RETIRED (owner RULINGS 2026-09-12s, spec §8): five of the
original seven twins priced the DRAPE at the seat and are deleted with
it.  What stands is the reading the placement path still takes:

1. the READER on authored geometry: a 500 m fence sheet is a line object,
   a 30 m wall 3 m thick is not (10bb's "ratio < 20 still joins");
2. the reader is per RESOURCE: a file with one ribbon and one blob is not
   a line object (what keeps the terminals' own walls out of the class);
3. the tall-curtain refusal (``line_object_max_h``);
4. ``Part.line`` round-trips through the plan (§16.2 C2).
"""
from __future__ import annotations

import numpy as np
import pytest

from auto_patch_v2.airport import line_object as LO
from auto_patch_v2.airport import obj8 as O
from auto_patch_v2.model import rebake as R
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
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="")
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


def _climbing(x_rise, panel, z=0.0):
    """Vertical panels ``panel`` m high whose base climbs ``x_rise``
    ``[(x, base)]`` — a fence authored over a slope."""
    out = []
    for (x0, b0), (x1, b1) in zip(x_rise, x_rise[1:], strict=False):
        out += [((x0, b0, z), (x1, b1, z), (x1, b1 + panel, z)),
                ((x0, b0, z), (x1, b1 + panel, z), (x0, b0 + panel, z))]
    return out


def test_a_fence_climbing_a_slope_is_as_tall_as_its_panel(tmp_path, law):
    """Spec 2068 A3 R4 (replaces A2 F0): a zero-width sheet's height is its
    tallest COLUMN only when it is a GROUND RIBBON — every column a foot and
    a head, the tallest under ``line_object_max_h``, the shortest over
    ``line_ribbon_min_panel_m``, no foot or head between joined columns
    steeper than ``emit.design.bank_slope``, the lowest foot at or under
    ``elevated_base_m``.  Anything else reads its y extent, as on main."""
    rb = law.tables.structures.rebake
    rib = LO.ribbon_law(law)
    cache = O.ResourceCache(0.05)

    def reads(path, ribbon=rib):
        comp = cache.components(path)[0]
        return (LO.component_shape(cache.geometry(path), comp, ribbon, rb.line_object_max_h)[2],
                LO.is_line_object(cache, path, rb, ribbon))

    # a 3.5 m sheet climbing 4 m at 20 %: a line, 3.5 m tall
    fence = _obj(tmp_path / "climb.obj", _climbing([(0.0, 0.0), (10.0, 2.0), (20.0, 4.0)], 3.5))
    comp = cache.components(fence)[0]
    assert comp.max_y - comp.min_y == pytest.approx(7.5)
    assert reads(fence) == (pytest.approx(3.5), True)
    # without the ribbon law (a caller holding none): the y extent, as on main
    assert reads(fence, None) == (pytest.approx(7.5), False)
    # the same climb at 50 %: not a ground ribbon
    steep = _obj(tmp_path / "steep.obj", _climbing([(0.0, 0.0), (4.0, 2.0), (8.0, 4.0)], 3.5))
    assert reads(steep) == (pytest.approx(7.5), False)
    # a 1.0 m rail climbing 6 m (at 20 %): its panel is under the minimum
    rail = _obj(tmp_path / "rail.obj", _climbing([(0.0, 0.0), (15.0, 3.0), (30.0, 6.0)], 1.0))
    assert reads(rail) == (pytest.approx(7.0), False)
    # a ribbon whose foot starts 12 m up: elevated, not on the ground
    high = _obj(tmp_path / "high.obj", _climbing([(0.0, 12.0), (10.0, 14.0), (20.0, 16.0)], 3.5))
    assert reads(high) == (pytest.approx(7.5), False)
    # a sheet whose columns carry one level only (a gable): its y extent
    gable = _obj(tmp_path / "gable.obj", [((0.0, 0.0, 0.0), (10.0, 0.0, 0.0), (5.0, 7.0, 0.0))])
    assert reads(gable)[0] == pytest.approx(7.0)
    # two 5 m sheets stacked at one position: 10 m, not a line
    stacked = _obj(tmp_path / "stacked.obj", _sheet(0.0, 40.0, 0.0, 0.0, 5.0)
                   + _sheet(0.0, 40.0, 0.0, 5.0, 10.0))
    assert reads(stacked) == (pytest.approx(10.0), False)
    # a boxed wall (plan width) keeps its y extent
    wall = _obj(tmp_path / "boxed.obj", _slab(-15.0, 15.0, -1.5, 1.5, 0.0, 2.0))
    assert LO.component_shape(cache.geometry(wall), cache.components(wall)[0], rib,
                              rb.line_object_max_h)[2] == pytest.approx(2.0)
    # the LineLaw carries its own ribbon (the placement half's reader)
    assert LO.is_line_object(cache, fence, LO.line_law(law))


# ── the plan (the seat that read it is RETIRED, 2026-09-12s) ─────────────────────────────────────────────────────────────

def _part(pid, comp, lat, lon, base_y, feet, line=False, half=1e-5):
    return R.Part(pid, comp, lat, lon, base_y, 100.0,
                  (lat - half, lon - half, lat + half, lon + half),
                  tuple(feet), line)


def _member(name, parts):
    return R.Member(name, f"objects/{name}.obj", name, name, 0.0, tuple(parts))


def _plan(units, contacts):
    return R.RebakePlan("ZZZZ", "p", "/p", tuple(units), (), {}, tuple(contacts))


#: 300 m apart in latitude; the fence runs the whole way and 100 m past.
#: The ANCHOR sits mid-way, so its rendered y = 0 plane is 702 and each
#: building's own correction clears ``min_delta_m``.
_ANCHOR = 0.00135
_A, _B = 0.0, 0.0027
_FENCE_FEET = [(-0.0009, 0.0, 0.0), (_A, 0.0, 0.0), (_ANCHOR, 0.0, 0.0),
               (_B, 0.0, 0.0), (0.0036, 0.0, 0.0)]


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


# THE SEAT IS RETIRED (owner RULINGS 2026-09-12s, spec §8).  Five twins
# stood here — the fence founding neither building, the fence and the
# kerb draping on their own stations, ``engine_v2._line_drape``'s
# per-vertex write, and a structure-seated member never being a line
# object.  All five drove ``emit/rebake.seat`` and
# ``engine_v2._decision_from_seats``, DELETED with the mechanism.  The
# READER (`airport/line_object.py`) and the plan's ``Part.line`` verdict
# below are the live law: the placement path cuts a line object into
# stations off the same reading.


def test_the_plan_round_trips_the_line_verdict():
    """§16.2 C2: ``Part.line`` travels in the plan (version 7; the
    current ``PLAN_VERSION`` is 12, ``Member.origin`` — the placement row's
    own ``(lat, lon)``, base-profile spec §1 (3)'s composed-unit roof test
    — over 11's ``Member.base_profile`` (§1 (4)) and 10's welded-deck
    shade, issue #14).

    The pin is deliberate: it is the ONE place a ``PLAN_VERSION`` bump has
    to be acknowledged in a test, so a field cannot be added to the plan
    without someone reading what the bump drops off the accepted window
    (``from_dict`` takes ``PLAN_VERSION - 3``, so 12 retires version 8 —
    ``RebakePlan.abutments``, RULINGS 2026-09-10ay: a v8 owner plan no
    longer replays offline.  Both version 11 and 12 are purely ADDITIVE
    and change no field the seat reads, so widening the window would cost
    nothing; REPORTED for the owner's ruling, not decided — lane
    ``basepads2``).  13 (``authored_seats``, object-placement spec §18,
    lane ``walls3``) is additive too and WIDENS the window to five, so it
    retires nothing (a v9 plan still loads) — reported, not decided."""
    from auto_patch_v2.model.rebake import PLAN_VERSION, RebakePlan
    assert PLAN_VERSION == 15
    pl = _fence_plan()
    back = RebakePlan.from_json(pl.to_json())
    assert [p.line for u in back.units for m in u.members for p in m.parts] == \
        [True, False, False]
    assert np.isclose(back.units[0].members[0].parts[0].feet[0][0], _FENCE_FEET[0][0])
