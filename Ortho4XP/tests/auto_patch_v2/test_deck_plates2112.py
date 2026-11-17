"""#2112: A PACK DECK IN DISJOINT PLATES SEATS EACH PLATE ON ITS OWN END
LINES (``airport/deck_plates``; owner 2026-11-17T14:57Z "(a) split them so
they can better follow the terrain").

Synthetic and hermetic: a hand-built OBJ8 deck of two hard-deck plates
joined by a plain strip, a wall running past both, the cut read back
through the engine's own reader.
"""
from __future__ import annotations

import dataclasses as _dc
import math

import numpy as np
from auto_patch_v2.airport import anchor_rule as AR
from auto_patch_v2.airport import deck_plates as DP
from auto_patch_v2.airport import obj8
from auto_patch_v2.airport import obj8_split as OS
from auto_patch_v2.airport.placement_record import Body, Split


def _quad(v: list, x0: float, x1: float, z0: float, z1: float, y: float) -> list:
    """Two up-facing triangles of a plan rectangle at height ``y``."""
    b = len(v)
    v += [(x0, y, z0), (x1, y, z0), (x1, y, z1), (x0, y, z1)]
    return [(b, b + 2, b + 1), (b, b + 3, b + 2)]


def _write(path, verts, groups) -> str:
    """``groups``: ``(attr lines, triangles)`` in order."""
    idx: list[int] = []
    cmds: list[str] = []
    for attrs, tris in groups:
        cmds.extend(attrs)
        cmds.append(f"TRIS\t{len(idx)} {len(tris) * 3}")
        for t in tris:
            idx.extend(t)
    out = ["I", "800", "OBJ", "", "TEXTURE\ttest.dds",
           f"POINT_COUNTS\t{len(verts)} 0 0 {len(idx)}", ""]
    out += [f"VT\t{x:.3f} {y:.3f} {z:.3f}\t0.0 1.0 0.0\t0.5 0.5" for x, y, z in verts]
    out += [f"IDX\t{q}" for q in idx]
    out += [""] + cmds
    path.write_text("\n".join(out) + "\n", encoding="utf-8")
    return str(path)


def _deck(tmp_path, gap: float = 20.0) -> str:
    v: list = []
    strip = _quad(v, -gap / 2 - 0.5, gap / 2 + 0.5, 0.0, 3.0, 6.5)   # a walkway over the gap
    deck = (_quad(v, -gap / 2 - 50.0, -gap / 2, 0.0, 40.0, 6.0)
            + _quad(v, gap / 2, gap / 2 + 50.0, 0.0, 40.0, 6.0))
    return _write(tmp_path / f"deck{gap:g}.obj", v,
                  [([], strip), (["ATTR_hard_deck"], deck)])


def test_two_plates_band_at_the_gap_middle(tmp_path):
    p = DP.plates_of(_deck(tmp_path), 2.0)
    assert p is not None and len(p) == 2
    assert abs(abs(p.axis[0]) - 1.0) < 1e-6
    assert abs(p.cuts[0]) < 0.05 and abs(p.gaps[0] - 20.0) < 0.1
    assert p.band_of(-30.0, 10.0) == 0 and p.band_of(30.0, 10.0) == 1


def test_plates_within_the_rigid_reach_are_one_plate(tmp_path):
    assert DP.plates_of(_deck(tmp_path, gap=1.5), 2.0) is None
    assert DP.census_file(_deck(tmp_path, gap=1.5), 2.0)["plates"] == 1


def test_a_wall_past_both_plates_is_clipped_at_the_band_line(tmp_path):
    v: list = []
    b = len(v)
    v += [(-60.0, 0.0, 0.0), (60.0, 0.0, 0.0), (60.0, 6.0, 0.0), (-60.0, 6.0, 0.0)]
    wall = [(b, b + 1, b + 2), (b, b + 2, b + 3)]
    path = _write(tmp_path / "wall.obj", v, [([], wall)])
    p = DP.Plates((1.0, 0.0), ((-60.0, -10.0), (10.0, 60.0)), (0.0,), (20.0,))
    comps = tuple(range(len(obj8.solid_components(obj8.parse_obj8(path)))))
    cuts = [OS.BodyCut(0, comps, (-30.0, 0.0, 0.0), band=p.band(0)),
            OS.BodyCut(1, comps, (30.0, 1.0, 0.0), band=p.band(1))]
    res = OS.split_obj8(path, cuts, "objects/wall.obj")
    assert not res.kept_whole and len(res.files) == 2
    for f, (lo, hi), off in zip(res.files, ((-60.0, 0.0), (0.0, 60.0)), (-30.0, 30.0), strict=True):
        q = tmp_path / f"b{f.body_id}.obj"
        q.write_text(f.text, encoding="utf-8")
        g = obj8.parse_obj8(str(q))
        x = g.vertices[np.unique(g.solid.reshape(-1)), 0] + off
        assert x.min() >= lo - 1e-3 and x.max() <= hi + 1e-3
        # the clipped half keeps the wall's full height and its area
        f3 = g.vertices[g.solid]
        area = 0.5 * np.linalg.norm(np.cross(f3[:, 1] - f3[:, 0], f3[:, 2] - f3[:, 0]),
                                    axis=1).sum()
        assert abs(area - 60.0 * 6.0) < 0.05


def _record(origin=(40.0, -3.0)) -> Split:
    a = AR.Anchor(AR.OTHER, origin[0], origin[1], 4.0, "frame zero", surface_z=104.0,
                  offset=(0.0, 4.0, 0.0))
    return Split(0, "dsf:obj1", "objects/deck.obj", "/x/deck.obj", origin[0], origin[1],
                 0.0, (Body(0, AR.OTHER, (0,), a, "objects/deck__b0.obj"),))


@_dc.dataclass
class _M:
    id: str = "dsf:obj1"
    resource: str = "objects/deck.obj"
    origin: tuple = (40.0, -3.0)
    heading_deg: float = 0.0
    zero_y: float = 0.0


def test_each_band_takes_its_own_end_lines_ground():
    p = DP.Plates((1.0, 0.0), ((-60.0, -10.0), (10.0, 60.0)), (0.0,), (20.0,))
    ml, mo = AR._m_per_deg(40.0)
    # x east: band 0 stations 30 m west, band 1 30 m east; heading 0, z south
    st = ((40.0, -3.0 - 30.0 / mo), (40.0 + 5.0 / ml, -3.0 - 30.0 / mo),
          (40.0, -3.0 + 30.0 / mo), (40.0 + 5.0 / ml, -3.0 + 30.0 / mo))
    fp = DP.FramePlates("dsf:obj1", p, (40.0, -3.0), 0.0, st)

    def surface(lat, lon):
        return 100.0 if lon < -3.0 else 101.0
    counts: dict = {}
    r = DP.split_record(_record(), _M(), fp, surface, counts)
    assert len(r.bodies) == 2 and counts["deck_plate_placements"] == 1
    zeros = [b.anchor.surface_z - b.anchor.y_zero for b in r.bodies]
    # the frame zero 100.0 (= 104 - 4) moves by each band's ground off the mean
    assert math.isclose(zeros[0], 99.5, abs_tol=1e-9)
    assert math.isclose(zeros[1], 100.5, abs_tol=1e-9)
    assert [b.band[2] for b in r.bodies] == [-math.inf, 0.0]
    assert len({b.new_resource for b in r.bodies}) == 2
    # a member authored on another row is left whole
    off = DP.split_record(_record(), _M(origin=(40.001, -3.0)), fp, surface, {})
    assert len(off.bodies) == 1


def test_census_reads_every_airport_pack_deck_once(tmp_path):
    import os
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "tools"))
    import deck_plate_census as C
    pack = tmp_path / "Pack A"
    (pack / "Earth nav data").mkdir(parents=True)
    (pack / "Earth nav data" / "apt.dat").write_text("I\n", encoding="utf-8")
    (pack / "objects").mkdir()
    src = _deck(pack / "objects")
    os.rename(src, str(pack / "objects" / "bridge.obj"))
    (pack / "objects" / "bridge__b0_0011aabb.obj").write_text(
        (pack / "objects" / "bridge.obj").read_text(encoding="utf-8"), encoding="utf-8")
    (tmp_path / "Not an airport").mkdir()
    out = C.census(str(tmp_path), None, 2.0)
    assert out["totals"] == {"packs": 1, "deck_files": 1, "multi_plate": 1, "banded": 1}
    assert out["packs"][0]["files"][0]["file"] == os.path.join("objects", "bridge.obj")
