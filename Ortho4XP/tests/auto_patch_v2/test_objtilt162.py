"""THE SEAT TILT — lane ``objtilt162`` twins (owner RULINGS 2026-10-01k
Q1, verbatim: *"Apron grade under a structure with only post feet, adjust
angle of object if necessary to seat all the feet"*; base-profile spec
§8a Q1; issue #162).

Synthetic and hermetic, in the shape of the site the ruling was read on:
KASE's ``Shelters.OBJ`` — a FLAT post base, no floor plate, 247 m long,
over an apron the hard 1.5 % cap carries at 1.36 %, where the object's
origin drapes mid-run so one end floats 1.64 m and the other is buried
1.88 m.  Here it is 44 posts over 247 x 46 m on a surface with exactly
that gradient, and the twins assert what the ruling states: the body
TILTS, every foot comes within the EXISTING foot tolerance, a base with a
FLOOR PLANE is never touched, and a tilt over the cap is REPORTED and not
applied.  The written file is read back through the engine's OWN parser
(``airport/obj8.parse_obj8``), with its normals, and
``tools/obj8_split_report`` prints the seat row off the same record.
"""
from __future__ import annotations

import math
import os
import sys

import numpy as np

from auto_patch_v2.airport import anchor_rule as AR
from auto_patch_v2.airport import obj8
from auto_patch_v2.airport import obj8_grade as OG
from auto_patch_v2.airport import obj8_split as OS
from auto_patch_v2.airport import placement_record as REC
from auto_patch_v2.airport import placement_seat_tilt as PST

# the site's own numbers (base-profile spec §0 fact 1 / §8a Q1)
LAT, LON = 39.2200, -106.8690
ML, MO = AR._m_per_deg(LAT)
APRON_GRADE = 0.0136           # the hard 1.5 % cap carries pav7 at 1.36 %
SHELTER_LEN_M = 247.0
SHELTER_WIDE_M = 46.0
FOOT_Y = -0.10                 # all 1,752 column feet are authored here
Z0 = 2354.90                   # the surface at the origin
TOL_M = 0.3                    # [placement] split_tol_m, the foot tolerance
BAND_M = 1.0                   # [basin] contact_band_m, the foot band
CAP_DEG = 1.5                  # [placement] seat_tilt_max_deg


def _ll(x_m: float, z_m: float) -> tuple[float, float]:
    """the authored frame at heading 0 (x east, z SOUTH) -> (lat, lon)"""
    return (LAT - z_m / ML, LON + x_m / MO)


def _surface(grade: float = APRON_GRADE):
    """a plane rising ``grade`` along authored +x, read as the design
    surface is read: ``surface(lat, lon) -> z | None``"""
    def s(la: float, lo: float) -> float:
        return Z0 + grade * ((lo - LON) * MO)
    return s


def _feet(nx: int = 22, nz: int = 2):
    """the column feet of a post base: ``(lat, lon, authored y)``, every
    one at the SAME authored y (the shelters' own base fits 0.000 %)"""
    out = []
    for i in range(nx):
        x = -SHELTER_LEN_M / 2.0 + SHELTER_LEN_M * i / (nx - 1)
        for j in range(nz):
            z = -SHELTER_WIDE_M / 2.0 + SHELTER_WIDE_M * j / max(1, nz - 1)
            la, lo = _ll(x, z)
            out.append((la, lo, FOOT_Y))
    return tuple(out)


class _U:
    anchor = (LAT, LON)


class _M:
    heading_deg = 0.0
    resource = "objects/airport/Shelters.OBJ"

    def __init__(self, verdict: str = OG.FEET):
        self.base_profile = {"verdict": verdict}


def _body(feet, cls: str = AR.BUILDING, **anchor_kw) -> REC.Body:
    a = AR.Anchor(cls, LAT, LON, FOOT_Y, "low-side foot", Z0,
                  offset=(0.0, FOOT_Y, 0.0), **anchor_kw)
    return REC.Body(0, cls, (0,), a,
                    OS.body_resource_name(_M.resource, 0, a.offset),
                    feet=tuple(feet))


def _seat(verdict: str = OG.FEET, grade: float = APRON_GRADE,
          body: "REC.Body | None" = None, cap: float = CAP_DEG):
    counts: dict[str, int] = {}
    b = body if body is not None else _body(_feet())
    out = PST.seat_tilt(b, _U(), _M(verdict), surface=_surface(grade),
                        max_total_deg=cap, foot_tol_m=TOL_M, band_m=BAND_M,
                        counts=counts)
    return out, counts


# ── (1) the shelter rows seat on the apron grade ─────────────────────────

def test_the_post_feet_body_tilts_and_every_foot_comes_within_tolerance():
    """10-01k Q1: the terrain stays at the apron grade and the BODY is
    rotated until every foot meets it."""
    out, counts = _seat()
    st = out.seat
    assert st is not None and st.applied
    # the float the owner read: half of 1.36 % x 247 m either side
    assert st.residual_before_m > 1.6
    # ... and 0.0136 is 0.779 deg of tilt, the owner's "~0.8 deg"
    assert abs(st.total_deg - math.degrees(math.atan(APRON_GRADE))) < 1e-6
    assert st.total_deg < CAP_DEG
    # the ROLL is the rise of the authored +x end; nothing across
    assert abs(st.roll_deg - st.total_deg) < 1e-6
    assert abs(st.tilt_deg) < 1e-9
    # ALL THE FEET, judged at the EXISTING foot tolerance
    assert st.residual_max_m <= TOL_M and not st.over_tolerance
    assert st.feet == len(_feet())
    assert counts["seat_tilt_applied"] == 1
    assert "seat_tilt_residual_over_tol" not in counts


def test_the_record_carries_the_fields_the_ruling_names():
    """``seat.tilt_deg`` / ``seat.roll_deg`` / ``seat.residual_max_m`` in
    the object record, and in the dict both censuses read."""
    out, _c = _seat()
    d = out.to_dict()["seat"]
    for k in ("tilt_deg", "roll_deg", "residual_max_m", "total_deg",
              "residual_before_m", "plane_rms_m", "feet", "applied",
              "over_tolerance", "grad", "reason"):
        assert k in d, k
    assert d["applied"] is True
    assert abs(d["residual_max_m"]) <= TOL_M
    assert PST.SEAT_REASON in d["reason"]


def test_the_tilted_bodys_file_is_keyed_on_the_tilt_it_bakes():
    """§4.5 / 14at: a name blind to the tilt would hand the second
    placement of one resource the first one's seated geometry."""
    flat, _c = _seat(grade=0.0)
    tilted, _c2 = _seat()
    assert flat.seat is not None and not flat.seat.applied
    assert flat.new_resource != tilted.new_resource
    # an UNTILTED body keeps exactly the name a pre-tilt write gave it
    assert flat.new_resource == OS.body_resource_name(
        _M.resource, 0, (0.0, FOOT_Y, 0.0))
    assert OS.offset_tag((1.0, 2.0, 3.0)) == OS.offset_tag(
        (1.0, 2.0, 3.0), OS.NO_TILT)
    assert OS.offset_tag((1.0, 2.0, 3.0)) != OS.offset_tag(
        (1.0, 2.0, 3.0), (0.0136, 0.0))


# ── (2) a base with a FLOOR PLANE is never tilted ────────────────────────

def test_a_floor_plane_body_is_left_exactly_as_it_was():
    """10-01k Q1 is about POSTS.  FLAT / STEPPED / SLOPED have a floor and
    are seated by the pad law; tilting one would lift a slab off its pad."""
    for verdict in (OG.FLAT, OG.STEPPED, OG.SLOPED):
        out, counts = _seat(verdict)
        assert out.seat is None, verdict
        assert counts["seat_tilt_floor_plane"] == 1, verdict
        assert out.new_resource == _body(_feet()).new_resource


def test_the_classes_another_law_seats_are_not_tilted():
    for cls in (AR.BASIN, AR.DECK, AR.PLATE_ONLY, AR.LINE_SEGMENT):
        out, _c = _seat(body=_body(_feet(), cls=cls))
        assert out.seat is None, cls
    for kw in ({"datum": True}, {"family": "unit:3"}, {"unit_seat": True},
               {"connector_of": "unit:3|unit:4"}):
        out, _c = _seat(body=_body(_feet(), **kw))
        assert out.seat is None, kw
    # and a body already standing within tolerance has nothing to seat
    out, _c = _seat(grade=0.0)
    assert out.seat is not None and not out.seat.applied
    assert "nothing to seat" in out.seat.reason


# ── (3) a tilt over the cap is REPORTED, never applied ───────────────────

def test_a_tilt_over_the_cap_is_reported_and_not_applied():
    """§8a Q1: past the cap the surface under the feet is a riser or a
    bank, not an apron grade — KASE's own cut-slope staircase reads 17 %.
    Reported, and NEVER a block cut."""
    out, counts = _seat(grade=0.17)
    st = out.seat
    assert st is not None
    assert st.total_deg > CAP_DEG and not st.applied
    assert st.grad == OS.NO_TILT          # nothing is baked
    assert st.over_tolerance              # and it is reported as unseated
    assert "REPORTED NOT APPLIED" in st.reason
    assert counts["seat_tilt_over_cap"] == 1
    assert "seat_tilt_applied" not in counts
    # the residual reported is the one the body is WRITTEN with
    assert st.residual_max_m == st.residual_before_m
    # ... and the file keeps its untilted name
    assert out.new_resource == _body(_feet()).new_resource


def test_the_cap_is_a_named_constant_and_zero_disarms_the_seat():
    from auto_patch_v2.law import tables
    law = tables.load_default()
    assert law.tables.structures.placement.seat_tilt_max_deg == CAP_DEG
    out, counts = _seat(cap=0.0)
    assert out.seat is None and not counts


def test_a_body_with_fewer_than_three_feet_is_not_tilted():
    out, counts = _seat(body=_body(_feet()[:2]))
    assert out.seat is not None and not out.seat.applied
    assert out.seat.feet == 2 and "a plane takes three" in out.seat.reason
    assert counts["seat_tilt_too_few_feet"] == 1


# ── (4) the rotation, as the writer bakes it ─────────────────────────────

def test_tilt_matrix_is_a_rotation_whose_tilt_is_the_fitted_gradient():
    for g in ((0.0136, 0.0), (-0.0136, 0.004), (0.0, -0.02)):
        r = OS.tilt_matrix(g)
        assert np.allclose(r.T @ r, np.eye(3), atol=1e-12)   # no shear
        assert abs(float(np.linalg.det(r)) - 1.0) < 1e-12
        # the authored +x / +z ends rise by the gradients
        assert abs((r @ np.array([1.0, 0.0, 0.0]))[1] - g[0]) < 1e-3
        assert abs((r @ np.array([0.0, 0.0, 1.0]))[1] - g[1]) < 1e-3
    assert np.array_equal(OS.tilt_matrix(OS.NO_TILT), np.eye(3))


def _two_posts(tmp_path, *, x_a: float = 0.0, x_b: float = 100.0):
    """two separated post stacks with UP normals — two solid components,
    so the cut writes two files without ``allow_single``"""
    def box(x0):
        s, h = 4.0, 3.0
        v = [(x0, 0.0, 0.0), (x0 + s, 0.0, 0.0), (x0 + s, 0.0, s),
             (x0, 0.0, s), (x0, h, 0.0), (x0 + s, h, 0.0),
             (x0 + s, h, s), (x0, h, s)]
        t = [(0, 1, 2), (0, 2, 3), (4, 6, 5), (4, 7, 6), (0, 4, 5), (0, 5, 1),
             (1, 5, 6), (1, 6, 2), (2, 6, 7), (2, 7, 3), (3, 7, 4), (3, 4, 0)]
        return v, t
    va, ta = box(x_a)
    vb, tb = box(x_b)
    verts = va + vb
    tris = ta + [(a + 8, b + 8, c + 8) for a, b, c in tb]
    idx = [i for t in tris for i in t]
    out = ["I", "800", "OBJ", "", "TEXTURE\ttest.dds",
           f"POINT_COUNTS\t{len(verts)} 0 0 {len(idx)}", ""]
    for x, y, z in verts:
        out.append(f"VT\t{x:.3f} {y:.3f} {z:.3f}\t0.000000 1.000000 0.000000"
                   f"\t0.0 0.0")
    out.append("")
    for i in range(0, len(idx) - len(idx) % 10, 10):
        out.append("IDX10\t" + " ".join(str(q) for q in idx[i:i + 10]))
    for q in idx[len(idx) - len(idx) % 10:]:
        out.append(f"IDX\t{q}")
    out.append("")
    out.append("ATTR_no_blend")
    out.append(f"TRIS\t0 {len(tris) * 3}")
    p = tmp_path / "posts.obj"
    p.write_text("\n".join(out) + "\n", encoding="utf-8", newline="")
    return p, len(tris)


def _cuts(path, tilt=OS.NO_TILT):
    geom = obj8.parse_obj8(str(path))
    comps = obj8.solid_components(geom)
    assert len(comps) == 2
    order = sorted(range(len(comps)), key=lambda i: comps[i].cx)
    return [OS.BodyCut(k, (order[k],), (0.0, 0.0, 0.0), (), tilt)
            for k in range(2)]


def test_the_written_obj_round_trips_through_the_engines_own_parser(tmp_path):
    """"It parses" means the readers downstream accept it.  The tilted
    file is read back by ``obj8.parse_obj8`` with its triangles conserved
    and its VERTICES rotated — a seated body whose geometry did not move
    is not seated at all."""
    p, total = _two_posts(tmp_path)
    grad = (APRON_GRADE, 0.0)
    res = OS.split_obj8(str(p), _cuts(p, grad), "objects/posts.obj")
    assert res.kept_whole == "" and len(res.files) == 2
    assert res.counts["tilted"] == 2
    rot = OS.tilt_matrix(grad)
    seen = 0
    for f in res.files:
        assert f.tilt == grad
        q = tmp_path / os.path.basename(f.resource)
        q.write_text(f.text, encoding="utf-8", newline="")
        g = obj8.parse_obj8(str(q))
        assert int(np.asarray(g.solid).shape[0]) == f.tris
        v = np.asarray(g.vertices, dtype=float)
        # every vertex sits on the rotated lattice: un-rotating it (R is
        # orthogonal, so R.T is the inverse) returns a y of either 0 (a
        # foot) or the post's own height, to the millimetre the file holds
        back = v @ np.asarray(rot)
        off = np.min(np.abs(back[:, 1][:, None] - np.array([0.0, 3.0])),
                     axis=1)
        assert float(off.max()) < 2e-3
        # ... and the body genuinely moved
        assert abs(float(v[:, 1].max()) - 3.0) > 1e-3
        seen += int(f.tris)
    assert seen == total


def test_the_normals_are_rotated_with_the_vertices(tmp_path):
    """A tilted body whose normals stayed put lights as though it were
    still level."""
    p, _total = _two_posts(tmp_path)
    grad = (APRON_GRADE, -0.004)
    rot = OS.tilt_matrix(grad)
    want = rot @ np.array([0.0, 1.0, 0.0])
    res = OS.split_obj8(str(p), _cuts(p, grad), "objects/posts.obj")
    rows = [ln for f in res.files for ln in f.text.splitlines()
            if ln.startswith("VT")]
    assert rows
    for ln in rows:
        n = np.asarray([float(t) for t in ln.split()[4:7]])
        assert np.allclose(n, want, atol=1e-5)
        assert abs(float(np.linalg.norm(n)) - 1.0) < 1e-5


def test_an_untilted_cut_writes_exactly_the_pre_tilt_bytes(tmp_path):
    """NO_TILT must leave the writer where it was: a pack whose bodies are
    not post-feet must not churn one file."""
    p, _total = _two_posts(tmp_path)
    a = OS.split_obj8(str(p), _cuts(p), "objects/posts.obj")
    b = OS.split_obj8(str(p), [OS.BodyCut(c.body_id, c.comps, c.offset, c.tris)
                               for c in _cuts(p)], "objects/posts.obj")
    assert [f.resource for f in a.files] == [f.resource for f in b.files]
    assert [f.text for f in a.files] == [f.text for f in b.files]
    assert a.counts["tilted"] == 0
    assert all(f.tilt == OS.NO_TILT for f in a.files)
    assert all("tilt" not in ln for f in a.files
               for ln in f.text.splitlines() if ln.startswith("# o4 split"))


def test_a_body_owning_an_anim_block_is_written_untilted(tmp_path):
    """Rule 4's compensation is a TRANSLATION and no ANIM command
    pre-rotates a block's frame: baking the rotation would swing the
    animated part out of its pivot.  Refused, counted, never silent."""
    p, _total = _two_posts(tmp_path)
    text = p.read_text(encoding="utf-8").splitlines()
    tris = [i for i, ln in enumerate(text) if ln.startswith("TRIS")][0]
    # a door on the first post's own north wall: two of its triangles
    text[tris:tris + 1] = ["TRIS\t0 12", "ANIM_begin",
                           "ANIM_trans\t0 0 0\t0 5 0\t0 1\tsim/test/door",
                           "TRIS\t12 6", "ANIM_end", "TRIS\t18 54"]
    p.write_text("\n".join(text) + "\n", encoding="utf-8", newline="")
    grad = (APRON_GRADE, 0.0)
    res = OS.split_obj8(str(p), _cuts(p, grad), "objects/posts.obj")
    assert res.counts["anim_blocks"] == 1
    assert res.counts.get("tilt_refused_anim") == 1
    assert res.counts["tilted"] == 1
    assert sorted(f.tilt for f in res.files) == [OS.NO_TILT, grad]
    # and the refused body's NAME is the untilted one
    untilted = [f for f in res.files if f.tilt == OS.NO_TILT][0]
    assert untilted.resource.endswith(
        OS.offset_tag(untilted.offset) + ".obj")


# ── (5) the instrument prints the seat row ───────────────────────────────

def test_obj8_split_report_prints_the_seat_row():
    """The report reads the plan's own ``seat`` record and derives
    nothing, so the instrument cannot disagree with what was baked."""
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__)))), "tools"))
    import types

    import obj8_split_report as RPT

    tilted, _c = _seat()
    capped, _c2 = _seat(grade=0.17)
    rows = RPT.seat_rows(tilted)
    assert rows and "seat BAKED" in rows[0]
    assert "tilt 0.779 deg" in rows[0] and "feet" in rows[0]
    assert "OVER TOLERANCE" not in rows[0]
    assert PST.SEAT_REASON in rows[1]
    assert RPT.seat_rows(_body(_feet())) == []      # no record, no row
    assert "reported, NOT applied" in RPT.seat_rows(capped)[0]

    ss = types.SimpleNamespace(all=(types.SimpleNamespace(
        bodies=(tilted, capped)),))
    lines = RPT.seat_tilt_lines(ss, cap_deg=CAP_DEG, tol_m=TOL_M)
    assert lines and "SEAT TILT" in lines[0]
    assert "2 post-feet bodies looked at, 1 TILTED" in lines[0]
    assert "1 over the cap (reported)" in lines[0]
    assert any("deg" in ln for ln in lines[1:])
