"""Twins for ``tools/object_pad_anchor_report.py``.

The tool's claim is narrow and load-bearing: it says which of a pack's
ANCHOR DATUMS stand on an emitted patch shape (the only ones with an
in-solve node to couple to) and how the pack's resources, bakes and pad
requests distribute over those datums.  Each twin pins one of the rules
that claim rests on, on synthetic inputs — no pack, no build, no network.
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

_ROOT = Path(__file__).resolve().parent.parent
for _p in (_ROOT / "tools", _ROOT / "src", _ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import object_pad_anchor_report as OPAR  # noqa: E402


def _placement(lat, lon, agl=0.0, resource="a.obj"):
    return SimpleNamespace(latitude=lat, longitude=lon,
                           above_ground_level_metres=agl,
                           resource_path=resource)


def _write_patch(path: Path, rings) -> Path:
    """``rings`` = [(role, [(lat, lon), ...])] → a minimal emitted patch."""
    lines = ["<?xml version='1.0' encoding='UTF-8'?>",
             "<osm version='0.6' generator='twin'>"]
    nid = -1
    way_bodies = []
    for role, ring in rings:
        refs = []
        for (lat, lon) in ring:
            lines.append(
                f"<node id='{nid}' visible='true' lat='{lat}' lon='{lon}'/>")
            refs.append(nid)
            nid -= 1
        refs.append(refs[0])
        body = "".join(f"<nd ref='{r}'/>" for r in refs)
        way_bodies.append((role, body))
    wid = -1000
    for role, body in way_bodies:
        lines.append(f"<way id='{wid}' visible='true'>{body}"
                     f"<tag k='role' v='{role}'/></way>")
        wid -= 1
    lines.append("</osm>")
    path.write_text("\n".join(lines))
    return path


def _square(lat, lon, size=0.001):
    return [(lat, lon), (lat, lon + size),
            (lat + size, lon + size), (lat + size, lon)]


class TestPatchShapes:
    def test_reads_role_and_polygon_in_lon_lat(self, tmp_path):
        patch = _write_patch(tmp_path / "p.osm",
                             [("apron", _square(30.0, 31.0))])
        shapes = OPAR.patch_shapes(patch)
        assert len(shapes) == 1
        role, _ref, poly = shapes[0]
        assert role == "apron"
        # LON/LAT order: the polygon's x range is the LONGITUDE range.
        minx, miny, maxx, maxy = poly.bounds
        assert abs(minx - 31.0) < 1e-9 and abs(maxx - 31.001) < 1e-9
        assert abs(miny - 30.0) < 1e-9 and abs(maxy - 30.001) < 1e-9


class TestGroupByDatum:
    def test_identical_spelling_is_one_datum(self):
        groups = OPAR.group_by_datum([
            _placement(30.1, 31.4, resource="a.obj"),
            _placement(30.1, 31.4, resource="b.obj"),
        ])
        assert len(groups) == 1
        assert len(next(iter(groups.values()))) == 2

    def test_a_different_spelling_is_never_proximity_joined(self):
        # One millimetre apart in the ninth decimal: two datums, because
        # calling them one would invent a sharing the pack does not have.
        groups = OPAR.group_by_datum([
            _placement(30.100000001, 31.4),
            _placement(30.100000002, 31.4),
        ])
        assert len(groups) == 2

    def test_agl_is_part_of_the_datum(self):
        groups = OPAR.group_by_datum([
            _placement(30.1, 31.4, agl=0.0),
            _placement(30.1, 31.4, agl=2.5),
        ])
        assert len(groups) == 2


class TestClassifyDatum:
    def test_a_point_inside_a_pavement_shape_is_hosted(self, tmp_path):
        patch = _write_patch(tmp_path / "p.osm",
                             [("apron", _square(30.0, 31.0))])
        shapes = OPAR.patch_shapes(patch)
        host, distance = OPAR.classify_datum(30.0005, 31.0005, shapes)
        assert host == "apron"
        assert distance == 0.0

    def test_a_point_outside_is_unhosted_with_a_real_distance(self, tmp_path):
        patch = _write_patch(tmp_path / "p.osm",
                             [("apron", _square(30.0, 31.0))])
        shapes = OPAR.patch_shapes(patch)
        host, distance = OPAR.classify_datum(30.0005, 31.0015, shapes)
        assert host is None
        # ~0.0005 deg east of the ring's east edge, ~55 m at this scale.
        assert 40.0 < distance < 70.0

    def test_an_object_pad_is_never_a_host(self, tmp_path):
        # A datum standing on a PAD is self-referential, not hosted: the
        # pad is what a coupling would place.
        patch = _write_patch(tmp_path / "p.osm", [
            ("object_pad", _square(30.0, 31.0)),
            ("apron", _square(30.010, 31.010)),
        ])
        shapes = OPAR.patch_shapes(patch)
        host, distance = OPAR.classify_datum(30.0005, 31.0005, shapes)
        assert host is None
        assert distance > 0.0

    def test_a_blend_ring_is_never_a_host_either(self, tmp_path):
        patch = _write_patch(tmp_path / "p.osm",
                             [("object_pad_blend", _square(30.0, 31.0))])
        shapes = OPAR.patch_shapes(patch)
        host, _distance = OPAR.classify_datum(30.0005, 31.0005, shapes)
        assert host is None


class TestBakedResources:
    def test_finds_anchor_bak_resources_pack_relative(self, tmp_path):
        (tmp_path / "objects").mkdir()
        (tmp_path / "objects" / "hangar.obj").write_text("obj")
        (tmp_path / "objects" / "hangar.obj.anchor_bak").write_text("obj")
        (tmp_path / "objects" / "cone.obj").write_text("obj")
        assert OPAR.baked_resources(tmp_path) == {"objects/hangar.obj"}


class TestSidecarRequests:
    def test_reads_only_the_named_airport(self, tmp_path):
        side = tmp_path / "o4_object_foot_pads.json"
        side.write_text(
            '{"version": 5, "airports": ['
            '{"icao": "HEAZ", "requests": [{"resource_path": "a.obj"}]},'
            '{"icao": "HECA", "requests": ['
            '{"resource_path": "b.obj"}, {"resource_path": "c.obj"}]}]}')
        assert len(OPAR.sidecar_requests(side, "HECA")) == 2
        assert len(OPAR.sidecar_requests(side, "HEAZ")) == 1
        assert OPAR.sidecar_requests(side, "OTHH") == []


class TestIndexAgreesWithTheLinearScan:
    def test_same_answer_hosted_and_unhosted(self, tmp_path):
        patch = _write_patch(tmp_path / "p.osm", [
            ("apron", _square(30.0, 31.0)),
            ("object_pad", _square(30.004, 31.004)),
            ("junction", _square(30.010, 31.010)),
        ])
        shapes = OPAR.patch_shapes(patch)
        index = OPAR.host_index(shapes)
        for (lat, lon) in [(30.0005, 31.0005),      # inside the apron
                           (30.0045, 31.0045),      # inside the PAD only
                           (30.0105, 31.0105),      # inside the junction
                           (30.0500, 31.0500)]:     # far outside
            plain = OPAR.classify_datum(lat, lon, shapes)
            fast = OPAR.classify_datum(lat, lon, shapes, index)
            assert plain[0] == fast[0]
            assert abs(plain[1] - fast[1]) < 1e-6


class TestSolveMemberClassification:
    def test_apron_is_a_solve_role_and_graded_strip_is_not(self):
        # Read from solver_primitives.PAVEMENT_ROLES, never re-listed:
        # a soft receiver carries the mesh value but no solve variable.
        assert OPAR.role_is_solve_member("apron") is True
        assert OPAR.role_is_solve_member("building") is True
        assert OPAR.role_is_solve_member("graded_strip") is False
        assert OPAR.role_is_solve_member("boundary") is False
        assert OPAR.role_is_solve_member(None) is False
