"""§42 OBJECT-BASED PAVEMENT IS A SOURCE (owner RULINGS 2026-09-13cv) —
the twins of ``airport/object_pavement.py``.

The headline twin is the brief's: ONE synthetic draped OBJ8 carrying two
disjoint Y = 0 bodies AND one solid box gives TWO source bodies, and the
solid's footprint stays the pad path's (the pads win where they overlap).
The rest are the refusals the HECA measurement forced into the law — a
shadow (no draped layer group), a decal (``markings``), a painted marking
(``runways +2``), a decorative name, a page under the area floor and
draped geometry authored off Y = 0.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from shapely.geometry import Polygon, box

from auto_patch_v2.airport import object_pavement as OP
from auto_patch_v2.law import Law

LAW = Law.for_airport("CYXY")


def _obj(tmp: Path, name: str, *, header: str, quads: list[tuple[float, float, float, float]],
         y: float = 0.0, solid: tuple[float, float, float, float] | None = None) -> Path:
    """A minimal OBJ8: one draped ``TRIS`` over ``quads`` (plan
    ``(x0, z0, x1, z1)``) at height ``y``, optionally one SOLID box."""
    verts: list[tuple[float, float, float]] = []
    idx: list[int] = []

    def quad(x0: float, z0: float, x1: float, z1: float, h: float) -> None:
        b = len(verts)
        verts.extend([(x0, h, z0), (x1, h, z0), (x1, h, z1), (x0, h, z1)])
        idx.extend([b, b + 1, b + 2, b, b + 2, b + 3])

    for q in quads:
        quad(*q, y)
    n_draped = len(idx)
    if solid is not None:
        quad(*solid, 3.0)
    lines = ["I", "800", "OBJ", "", header,
             f"POINT_COUNTS\t{len(verts)}\t0\t0\t{len(idx)}"]
    lines += [f"VT\t{x}\t{h}\t{z}\t0\t1\t0\t0\t0" for x, h, z in verts]
    lines += [f"IDX\t{i}" for i in idx]
    if solid is not None:
        # the solid range FIRST, so the draped state is entered after it
        lines.append(f"TRIS\t{n_draped}\t{len(idx) - n_draped}")
    lines.append("ATTR_draped")
    lines.append(f"TRIS\t0\t{n_draped}")
    p = tmp / name
    p.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="")
    return p


PAVEMENT_HEADER = ("TEXTURE_DRAPED\tconcrete.png\n"
                   "ATTR_layer_group_draped\trunways\t1")


def _place(path: Path, def_path: str = "Airport/ground/Concrete.obj",
           xy=(0.0, 0.0), heading=0.0) -> OP.Placement:
    return OP.Placement("dsf:obj0", def_path, str(path), xy, heading)


def test_header_facts_reads_texture_and_group_and_stops_at_geometry(tmp_path):
    p = _obj(tmp_path, "a.obj", header=PAVEMENT_HEADER,
             quads=[(0, 0, 20, 20)])
    assert OP.header_facts(str(p)) == (("runways", 1), "concrete.png")
    assert OP.header_facts(str(tmp_path / "absent.obj")) == (None, "")


def test_two_disjoint_bodies_and_a_solid(tmp_path):
    """The brief's twin: two disjoint draped bodies -> two sources; the
    solid box is NOT one of them, and the pad that covers it takes
    nothing from them (§42 (1): pads win where they OVERLAP)."""
    p = _obj(tmp_path, "mixed.obj", header=PAVEMENT_HEADER,
             quads=[(0, 0, 30, 30), (100, 100, 140, 140)],
             solid=(300, 300, 320, 320))
    bodies, rep = OP.read_object_pavements([_place(p)], LAW)
    assert [round(b.polygon.area) for b in bodies] == [900, 1600]
    assert rep.bodies == 2 and round(rep.area_m2) == 2500
    assert rep.rows[0].texture == "concrete.png"
    assert rep.rows[0].resource == "Airport/ground/Concrete.obj"
    # the solid box's plan footprint is not among the bodies
    solid_plan = box(300, -320, 320, -300)
    assert all(b.polygon.intersection(solid_plan).area == 0 for b in bodies)
    # ...and as a pad it takes nothing from them
    bodies2, rep2 = OP.read_object_pavements([_place(p)], LAW, solid_plan)
    assert [round(b.polygon.area) for b in bodies2] == [900, 1600]
    assert rep2.pad_clipped_bodies == 0


def test_a_pad_over_a_body_wins(tmp_path):
    p = _obj(tmp_path, "one.obj", header=PAVEMENT_HEADER, quads=[(0, 0, 40, 40)])
    pad = box(0, -40, 10, 0)          # a quarter of the body, in the frame
    bodies, rep = OP.read_object_pavements([_place(p)], LAW, pad)
    assert round(sum(b.polygon.area for b in bodies)) == 1200
    assert rep.pad_clipped_bodies == 1 and round(rep.pad_clipped_m2) == 400


def test_placement_origin_and_heading_place_the_body(tmp_path):
    p = _obj(tmp_path, "one.obj", header=PAVEMENT_HEADER, quads=[(0, 0, 40, 10)])
    bodies, _rep = OP.read_object_pavements(
        [_place(p, xy=(1000.0, 2000.0), heading=90.0)], LAW)
    minx, miny, maxx, maxy = bodies[0].polygon.bounds
    # the frame law of ``obj8.placement_affine``: east = x.cos h - z.sin h,
    # north = -(x.sin h + z.cos h).  At heading 90 the authored +x runs
    # SOUTH and the authored +z runs WEST.
    assert (round(minx), round(maxx)) == (990, 1000)
    assert (round(miny), round(maxy)) == (1960, 2000)


@pytest.mark.parametrize("header,reason", [
    ("TEXTURE_DRAPED\tao.png", "no draped layer group"),
    ("TEXTURE_DRAPED\td1.png\nATTR_layer_group_draped\tmarkings\t3",
     "layer group markings"),
    ("TEXTURE_DRAPED\twhite.png\nATTR_layer_group_draped\trunways\t2",
     "layer offset +2 (an overlay)"),
])
def test_the_pack_declares_what_is_pavement(tmp_path, header, reason):
    """A shadow, a decal and a painted marking are all draped Y = 0 pages
    covering thousands of m2 (HECA: 31.9 M m2 of them).  The pack says
    which is pavement, and only that is admitted."""
    p = _obj(tmp_path, "x.obj", header=header, quads=[(0, 0, 100, 100)])
    bodies, rep = OP.read_object_pavements([_place(p)], LAW)
    assert bodies == [] and rep.refused == {reason: 1}


def test_a_decorative_name_is_refused_whatever_it_declares(tmp_path):
    p = _obj(tmp_path, "x.obj", header=PAVEMENT_HEADER, quads=[(0, 0, 100, 100)])
    bodies, rep = OP.read_object_pavements(
        [_place(p, def_path="Airport/ground/RwySigns_marking.obj")], LAW)
    assert bodies == [] and rep.refused == {"decorative name": 1}


def test_the_area_floor_and_the_y_tolerance(tmp_path):
    small = _obj(tmp_path, "small.obj", header=PAVEMENT_HEADER,
                 quads=[(0, 0, 10, 10)])
    bodies, rep = OP.read_object_pavements([_place(small)], LAW)
    assert bodies == [] and rep.refused == {"under 200 m2": 1}
    high = _obj(tmp_path, "high.obj", header=PAVEMENT_HEADER,
                quads=[(0, 0, 100, 100)], y=1.0)
    bodies, rep = OP.read_object_pavements([_place(high)], LAW)
    assert bodies == [] and rep.refused == {"draped geometry off Y = 0": 1}
    # ...and the tolerance itself admits the authored near-zero of a real
    # pack (HECA's concrete sits at 1.2e-07)
    tiny = _obj(tmp_path, "tiny.obj", header=PAVEMENT_HEADER,
                quads=[(0, 0, 100, 100)], y=1.2e-07)
    bodies, _rep = OP.read_object_pavements([_place(tiny)], LAW)
    assert len(bodies) == 1


def test_one_resource_is_parsed_once_for_many_placements(tmp_path):
    p = _obj(tmp_path, "one.obj", header=PAVEMENT_HEADER, quads=[(0, 0, 40, 40)])
    pls = [OP.Placement(f"dsf:obj{i}", "Airport/ground/Concrete.obj", str(p),
                        (i * 1000.0, 0.0), 0.0) for i in range(4)]
    calls: list[str] = []
    real = OP._obj8.parse_obj8

    def counting(path: str):
        calls.append(path)
        return real(path)

    OP._obj8.parse_obj8 = counting            # type: ignore[assignment]
    try:
        bodies, rep = OP.read_object_pavements(pls, LAW)
    finally:
        OP._obj8.parse_obj8 = real            # type: ignore[assignment]
    assert len(calls) == 1
    assert rep.resources_seen == 1 and rep.placements == 4 and rep.bodies == 4
    assert rep.rows[0].raw_bodies == 4


def test_no_draped_objects_reads_nothing(tmp_path):
    """A pack with no draped OBJ8 leaves the source list untouched — the
    byte-identity bar's mechanism."""
    p = _obj(tmp_path, "solid.obj", header="TEXTURE\tbuilding.png",
             quads=[], solid=(0, 0, 40, 40))
    bodies, rep = OP.read_object_pavements([_place(p)], LAW)
    assert bodies == [] and rep.bodies == 0
    assert rep.line().startswith("object_pavements 0 bodies")


def test_the_law_keys_are_the_measured_ones():
    lw = LAW.tables.structures.load
    assert lw.draped_y_tol_m == 0.05
    assert lw.object_pavement_min_m2 == 200.0
    assert lw.object_pavement_layer_groups == ("runways", "taxiways")
    assert lw.object_pavement_max_layer_offset == 1
    assert "marking" in lw.object_pavement_skip_tokens


# ── §42 (1b) THE HARD GROUND PLANE (lane ``nlwf``, issue #20) ──────────

def _plane(tmp: Path, name: str, *, quad=(0.0, 0.0, 40.0, 50.0), y_far: float = 0.0,
           hard: bool = True, header: str = "TEXTURE\tapron.png\nTEXTURE_DRAPED\tapron.png") -> Path:
    """NLWF's ``vele_apron.obj`` in miniature: a SOLID plane at Y = 0 (no
    ``ATTR_draped``, no draped layer group), its triangles ``ATTR_hard``;
    ``y_far`` lifts ONE vertex off the ground."""
    x0, z0, x1, z1 = quad
    verts = [(x0, 0.0, z0), (x1, 0.0, z0), (x1, y_far, z1), (x0, 0.0, z1)]
    lines = ["I", "800", "OBJ", "", header, f"POINT_COUNTS\t4\t0\t0\t6"]
    lines += [f"VT\t{x}\t{h}\t{z}\t0\t1\t0\t0\t0" for x, h, z in verts]
    lines += ["IDX\t0", "IDX\t1", "IDX\t2", "IDX\t0", "IDX\t2", "IDX\t3"]
    if hard:
        lines.append("ATTR_hard")
    lines.append("TRIS\t0\t6")
    p = tmp / name
    p.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="")
    return p


def _law_on():
    import dataclasses as dc
    t = LAW.tables
    ld = dc.replace(t.structures.load, object_pavement_hard_planes=True)
    return dc.replace(LAW, tables=dc.replace(
        t, structures=dc.replace(t.structures, load=ld)))


def test_a_hard_ground_plane_is_pavement(tmp_path):
    """NLWF: the pack's whole apron is a hard solid plane at Y = 0 with no
    draped layer group; §42 (1b) admits it as one body of its own area."""
    p = _plane(tmp_path, "vele_apron.obj")
    bodies, rep = OP.read_object_pavements(
        [_place(p, "pavement/vele_apron.obj")], _law_on())
    assert [round(b.polygon.area) for b in bodies] == [2000]
    assert rep.resources_admitted == 1 and rep.refused == {}
    assert rep.rows[0].layer_group == "hard_plane"


@pytest.mark.parametrize("kw", [dict(hard=False), dict(y_far=2.5)],
                         ids=["not hard (a shadow)", "a vertex off the ground (a floor with walls)"])
def test_a_plane_that_is_not_hard_or_not_flat_stays_refused(tmp_path, kw):
    p = _plane(tmp_path, "plane.obj", **kw)
    bodies, rep = OP.read_object_pavements([_place(p, "objects/plane.obj")], _law_on())
    assert bodies == [] and rep.refused == {"no draped layer group": 1}


def test_a_hard_plane_under_the_area_floor_is_refused(tmp_path):
    p = _plane(tmp_path, "small.obj", quad=(0.0, 0.0, 10.0, 10.0))
    bodies, rep = OP.read_object_pavements([_place(p, "objects/small.obj")], _law_on())
    assert bodies == [] and rep.refused == {"under 200 m2": 1}


def _law_off():
    import dataclasses as dc
    t = LAW.tables
    ld = dc.replace(t.structures.load, object_pavement_hard_planes=False)
    return dc.replace(LAW, tables=dc.replace(
        t, structures=dc.replace(t.structures, load=ld)))


def test_the_hard_plane_key_ships_on_and_off_refuses(tmp_path):
    """Q-20 RULED (owner RULINGS 2026-09-27a (5)): the key ships ON; OFF
    keeps §42 (1)'s reading."""
    assert LAW.tables.structures.load.object_pavement_hard_planes is True
    p = _plane(tmp_path, "vele_apron.obj")
    bodies, rep = OP.read_object_pavements(
        [_place(p, "pavement/vele_apron.obj")], _law_off())
    assert bodies == [] and rep.refused == {"no draped layer group": 1}


def test_a_hard_plane_body_is_marked_and_a_draped_one_is_not(tmp_path):
    p = _plane(tmp_path, "vele_apron.obj")
    bodies, _rep = OP.read_object_pavements(
        [_place(p, "pavement/vele_apron.obj")], LAW)
    assert [b.hard_plane for b in bodies] == [True]
    assert OP.is_hard_plane_ref(f"{OP.HARD_PLANE_PREFIX}0#1")
    assert not OP.is_hard_plane_ref("dsf:objpav0#1")
    # a sub-prefix of the object-pavement id: every §42 gate still reads it
    from auto_patch_v2.classify.sources import OBJECT_PAVEMENT_PREFIX
    assert OP.HARD_PLANE_PREFIX.startswith(OBJECT_PAVEMENT_PREFIX)


def _arc_plane(tmp: Path, name: str, r: float = 2.0, step_m: float = 0.55) -> Path:
    """A 40 x 50 m hard plane whose one corner is a fillet of radius ``r``
    chorded every ``step_m`` (NLWF's 0.5-0.6 m corner arcs), fanned from
    the plane's centre."""
    import math
    pts = [(0.0, 0.0), (40.0, 0.0), (40.0, 50.0 - r)]
    n = max(2, int(math.ceil(0.5 * math.pi * r / step_m)))
    for k in range(1, n):
        a = 0.5 * math.pi * k / n
        pts.append((40.0 - r + r * math.cos(a), 50.0 - r + r * math.sin(a)))
    pts += [(40.0 - r, 50.0), (0.0, 50.0)]
    c = (20.0, 25.0)
    verts = [c] + pts
    lines = ["I", "800", "OBJ", "", "TEXTURE\tapron.png",
             f"POINT_COUNTS\t{len(verts)}\t0\t0\t{3 * len(pts)}"]
    lines += [f"VT\t{x}\t0.0\t{z}\t0\t1\t0\t0\t0" for x, z in verts]
    for i in range(len(pts)):
        j = (i + 1) % len(pts)
        lines += ["IDX\t0", f"IDX\t{i + 1}", f"IDX\t{j + 1}"]
    lines += ["ATTR_hard", f"TRIS\t0\t{3 * len(pts)}"]
    p = tmp / name
    p.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="")
    return p


def test_the_planes_corner_arcs_are_not_emitted_as_hairlines(tmp_path):
    """#20: NLWF's apron object rounds its corners in 0.5-0.6 m chords and
    each became an emitted segment under the identity spacing (93
    unmeshable ``hairline_pair`` rows).  The plane's outline is simplified
    at half the spacing: no edge shorter than the spacing survives, and
    the area moves by less than the fillet's own."""
    import math
    p = _arc_plane(tmp_path, "vele_apron.obj")
    bodies, _rep = OP.read_object_pavements(
        [_place(p, "pavement/vele_apron.obj")], LAW)
    assert len(bodies) == 1
    ring = list(bodies[0].polygon.exterior.coords)
    spacing = LAW.tables.emit.identity.min_distinct_spacing_m
    edges = [math.dist(ring[i], ring[i + 1]) for i in range(len(ring) - 1)]
    assert min(edges) >= spacing, sorted(edges)[:4]
    assert abs(bodies[0].polygon.area - (2000.0 - (4.0 - math.pi))) < 0.5


def test_the_hard_plane_is_one_level_off_its_runway_frontage():
    """§42 (1b) as ruled (27a (5)): ONE Flat over the plane's vertices;
    the vertices it shares with a RUNWAY-family face stay out of it (the
    runway is fixed first and is not level to the millimetre)."""
    import types
    from auto_patch_v2.constraints.hard_plane import (hard_plane_level,
                                                      hard_plane_vertices)
    from auto_patch_v2.model.constraints import Flat
    faces = {
        0: types.SimpleNamespace(id=0, role="runway", ref="07/25",
                                 ring=(0, 1, 2, 3), holes=()),
        1: types.SimpleNamespace(id=1, role="apron", ref=f"{OP.HARD_PLANE_PREFIX}0#0",
                                 ring=(2, 3, 4, 5), holes=()),
        2: types.SimpleNamespace(id=2, role="junction", ref=f"{OP.HARD_PLANE_PREFIX}0#1",
                                 ring=(4, 5, 6), holes=()),
        3: types.SimpleNamespace(id=3, role="apron", ref="dsf:objpav3#0",
                                 ring=(7, 8, 9), holes=()),
    }
    pm = types.SimpleNamespace(faces=faces, ring_vertices=lambda cyc: tuple(cyc))
    assert hard_plane_vertices(pm) == {2, 3, 4, 5, 6}
    rows = hard_plane_level(pm, LAW, None)
    assert len(rows) == 1 and isinstance(rows[0], Flat)
    assert rows[0].group == (4, 5, 6)
    # no hard plane: nothing
    pm2 = types.SimpleNamespace(faces={0: faces[0], 3: faces[3]},
                                ring_vertices=lambda cyc: tuple(cyc))
    assert hard_plane_level(pm2, LAW, None) == []
