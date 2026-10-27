"""THE TERRAIN WITNESS (#1359; owner RULINGS 2026-10-26q, 26v, 26w, 26x,
26y, 26z, 27a; spec ``docs/specs/multi-source-terrain-spec.md``).

Synthetic and offline: a 1,200 m runway along x, a painted texture stub
(asphalt, grass, threshold piano keys where a case puts them), a plane or
kinked DEM.  The airports the rule was measured at (KDIJ: both CIFP
records 594 m off the runway the photo shows) are its closing build, never
its scope (RULINGS 2026-10-05e).
"""
from __future__ import annotations

import dataclasses as _dc
import math

import numpy as np
import pytest
from auto_patch_v2.airport import graded_edge_witness as G
from auto_patch_v2.airport import image_edges_classic as IC
from auto_patch_v2.airport import lidar_breaks as LB
from auto_patch_v2.airport import portal_witness as PW
from auto_patch_v2.airport import runway_end_witness as W
from auto_patch_v2.airport.cifp import CifpRunway
from auto_patch_v2.airport.image_provider import ImagePatch
from auto_patch_v2.airport.imagery_read import TextureSet, global_pixel, texture_of_file
from auto_patch_v2.airport.witness_vote import Abstain, Vote, decide
from auto_patch_v2.law import Law, LawError
from auto_patch_v2.law.terrain_witness_schema import check_terrain_witness
from auto_patch_v2.model.airport import Airport, OsmWay, Runway, RunwayEnd, SceneryPack
from auto_patch_v2.model.frame import Frame

L = 1200.0
HW = 22.5
SEN = W.SENIORITY


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


class _Plane:
    provenance = {"synthetic": "plane"}

    def z(self, x, y):
        return 700.0

    def source_pixel_m(self):
        return 1.0, "inset"


class _Paint:
    """A texture stub: asphalt on the runway (|y| <= HW along x), grass
    elsewhere, and threshold piano keys from ``keys_at`` metres in from the
    09 end for 45 m (stripes ALONG the axis: 1.8 m wide, 1.8 m apart)."""

    def __init__(self, keys_at: float | None):
        self.keys_at = keys_at
        self.decodes = 0
        self.refs = ("stub",)

    def __len__(self):
        return 1

    def patch(self, crs, x0, y0, x1, y1, m, corridor=None):
        w, h = int(math.ceil((x1 - x0) / m)), int(math.ceil((y1 - y0) / m))
        xs = x0 + (np.arange(w) + 0.5) * m
        ys = y1 - (np.arange(h) + 0.5) * m
        gx, gy = np.meshgrid(xs, ys)
        on = (np.abs(gy) <= HW) & (np.abs(gx) <= L / 2)
        lum = np.where(on, 100.0, 160.0)
        if self.keys_at is not None:
            s = gx + L / 2
            keys = on & (s >= self.keys_at) & (s <= self.keys_at + 45.0) & (np.abs(gy) <= 20.0)
            lum = np.where(keys & (np.floor((gy + 20.0) / 1.8) % 2 == 0), 230.0, lum)
        rgb = np.repeat(lum[..., None], 3, axis=2).astype(np.uint8)
        return ImagePatch(rgb, m, (x0, y1), "STUB@18", np.ones((h, w), dtype=bool))


def _airport(dem, cifp_elev=(700.0, 700.0), displaced=(0.0, 0.0)):
    frame = Frame("ZZZZ", origin=(60.5, -135.5), identity_dp=11)
    ends = (RunwayEnd("09", (-L / 2, 0.0), (60.5, -135.51), displaced[0], 0.0,
                      cifp_elev[0], "fixture", pin_source="cifp"),
            RunwayEnd("27", (L / 2, 0.0), (60.5, -135.49), displaced[1], 0.0,
                      cifp_elev[1], "fixture", pin_source="cifp"))
    rw = Runway("09/27", 45.0, 1, ends, 3, "D")
    pack = SceneryPack("fixture", "apt.dat", "0", (), ())
    return Airport("ZZZZ", "Synthetic", frame, 700.0, (rw,), (), (), {}, (),
                   (), (), (), (), (), (), pack, dem, "FAA")


def _to_xy(lon, lat):
    """The stub projection: a record's ``lon`` IS its frame x on the axis."""
    return (lon, lat)


def _cifp(*pairs):
    return {d: CifpRunway(d, 0.0, float(x), 700.0, 0.0, "fixture") for d, x in pairs}


# ── the vote ──────────────────────────────────────────────────────────────

def test_the_layout_and_the_imagery_outvote_a_dissenting_cifp():
    d = decide([Vote("layout", 0.0, 3.0), Vote("imagery", -1.5, 5.1), Vote("cifp", 593.5, 1.0)],
               SEN, 2.0)
    assert d.status == "majority" and set(d.winners) == {"layout", "imagery"}
    assert d.yielders == ("cifp",) and d.answer == 0.0


def test_a_loser_agreeing_with_one_winner_does_not_yield():
    """A one-sided imagery bound agrees with both the layout and CIFP: CIFP
    is not overridden (it disagrees with the layout alone)."""
    d = decide([Vote("layout", 0.0, 3.0), Vote("imagery", 5.0, 4.0, bound="min"),
                Vote("cifp", 300.0, 1.0)], SEN, 2.0)
    assert d.yielders == () and d.unresolved == ("cifp",)


def test_one_vote_is_uncorroborated_and_none_is_no_answer():
    assert decide([Vote("cifp", 3.0, 1.0), Abstain("imagery", "x")], SEN, 2.0).status \
        == "uncorroborated"
    assert decide([Abstain("imagery", "x")], SEN, 2.0).answer is None


# ── the image method ──────────────────────────────────────────────────────

def _rows(pattern, n=30, k=80):
    return np.array([pattern(i, np.arange(k)) for i in range(n)], dtype=float)


def test_piano_keys_read_and_chevrons_do_not():
    keys = _rows(lambda i, j: np.where((j // 4) % 2 == 0, 230.0, 100.0))
    chevrons = _rows(lambda i, j: np.where(((j + 2 * i) // 4) % 2 == 0, 230.0, 100.0))
    assert IC._marking_rows(keys, 0.5).all()
    assert not IC._marking_rows(chevrons, 0.5).any()


# ── Q1: where is the landing threshold (RULINGS 2026-10-26v) ─────────────

def test_q1_drops_the_cifp_record_the_layout_and_the_imagery_outvote(law):
    ap = _airport(_Plane())
    cifp = _cifp(("09", -L / 2 + 593.5), ("27", L / 2 + 594.5))
    out, recs, lines = W.witness_runway_ends(ap, cifp, _to_xy, _Paint(keys_at=6.0), law)
    e09 = out.runways[0].ends[0]
    assert e09.threshold_elev_m is None and e09.pin_source == "" and e09.pin_flags == W.OUTVOTED
    r09 = next(r for r in recs if r["end"] == "09")
    assert r09["dropped"] and r09["yielders"] == ["cifp"]
    assert any("RULINGS 2026-10-26v" in ln and "RWY 09" in ln for ln in lines)
    # the 27 end shows no marking: the imagery abstains, the CIFP stands
    assert out.runways[0].ends[1].threshold_elev_m == 700.0


def test_q1_keeps_a_cifp_threshold_the_imagery_confirms(law):
    """A stale apt.dat end and a CIFP displaced threshold the photo's
    markings confirm: CIFP and the imagery outvote the layout."""
    ap = _airport(_Plane())
    out, recs, _ = W.witness_runway_ends(ap, _cifp(("09", -L / 2 + 66.0)), _to_xy,
                                         _Paint(keys_at=66.0), law)
    assert out.runways[0].ends[0].threshold_elev_m == 700.0
    assert not recs[0]["dropped"]


def test_q1_never_outvotes_a_record_inside_the_join_radius(law):
    ap = _airport(_Plane())
    out, recs, _ = W.witness_runway_ends(ap, _cifp(("09", -L / 2 + 25.0)), _to_xy,
                                         _Paint(keys_at=6.0), law)
    assert out.runways[0].ends[0].threshold_elev_m == 700.0 and not recs[0]["dropped"]


def test_q1_without_imagery_today_law_stands(law):
    ap = _airport(_Plane())
    out, recs, lines = W.witness_runway_ends(ap, _cifp(("09", -L / 2 + 593.5)), _to_xy,
                                             None, law)
    assert out.runways[0].ends[0].threshold_elev_m == 700.0 and not lines
    assert any(v.get("abstain") for v in recs[0]["votes"] if v["source"] == "imagery")


# ── the imagery reader ────────────────────────────────────────────────────

def test_a_texture_file_is_read_at_its_own_web_mercator_pixels(tmp_path):
    from PIL import Image
    lat, lon, zoom = 45.5, 7.5, 16
    px, py = global_pixel(np.array([lat]), np.array([lon]), zoom)
    tx, ty = int(px[0] // 256 // 16 * 16), int(py[0] // 256 // 16 * 16)
    img = np.zeros((4096, 4096, 3), dtype=np.uint8)
    col, row = int(px[0] - tx * 256), int(py[0] - ty * 256)
    img[row - 3:row + 4, col - 3:col + 4] = (250, 10, 10)
    path = tmp_path / f"{ty}_{tx}_BI{zoom}.png"
    Image.fromarray(img).save(path)
    ref = texture_of_file(str(path), lat, lon)
    assert ref is not None and ref.zoom == zoom and ref.provider == "BI"
    assert texture_of_file(str(path), lat + 5, lon) is None      # another tile's
    ts = TextureSet.from_files([str(path)], lat, lon)
    rgb, ok, source = ts.sample(np.array([lat]), np.array([lon]))
    assert ok[0] and source == "BI@16" and rgb[0, 0] > 200 and rgb[0, 1] < 50


# ── the DEM reads ─────────────────────────────────────────────────────────

class _Kink:
    """Flat to x = 10, then a 6 % climb: a graded edge meeting a bank."""

    def z(self, x, y):
        return 700.0 + 0.06 * max(0.0, x - 10.0)


class _Pit:
    def z(self, x, y):
        return 700.0 - (6.0 if math.hypot(x, y) < 8.0 else 0.0)


def test_the_slope_break_is_where_the_profile_bends():
    offs = np.arange(-40.0, 40.0 + 1e-9, 1.0)
    at, change = LB.slope_breaks(_Kink(), np.array([[0.0, 0.0]]), np.array([[1.0, 0.0]]),
                                 offs, 5.0, 3.0, 3.0)
    assert at[0] is not None and abs(at[0] - 10.0) <= 3.0 and change[0] >= 3.0


def test_a_cut_reads_deep_and_flat_ground_does_not():
    depth, floor = LB.cut_depth(_Pit(), (0.0, 0.0), (40.0, 60.0), 15.0)
    assert depth == pytest.approx(6.0, abs=0.01) and floor == pytest.approx(694.0, abs=0.01)
    assert LB.cut_depth(_Plane(), (0.0, 0.0), (40.0, 60.0), 15.0)[0] == pytest.approx(0.0)


# ── Q5: only mapped mouths (RULINGS 2026-10-26x) ──────────────────────────

def test_a_mouth_is_an_open_end_of_a_mapped_bore():
    bore = {"tunnel": "yes", "highway": "service"}
    a = OsmWay(1, "roads", ((0.0, 0.0), (50.0, 0.0)), False, bore)
    b = OsmWay(2, "roads", ((50.0, 0.0), (90.0, 0.0)), False, bore)
    passage = OsmWay(3, "roads", ((0.0, 50.0), (9.0, 50.0)), False,
                     {"tunnel": "building_passage", "highway": "service"})
    ap = _dc.replace(_airport(_Plane()), osm_ways=(a, b, passage))
    mouths = PW.mapped_mouths(ap)
    assert sorted(m[0] for m in mouths) == [(0.0, 0.0), (90.0, 0.0)]


# ── Q4: the graded edge (RULINGS 2026-10-26w / 26z / 27a) ─────────────────

class _Coarse(_Plane):
    def source_pixel_m(self):
        return 30.0, "inset"


def _edge(image):
    return G.EdgeRead("09/27", "left", tuple(float(i) * 20 for i in range(len(image))),
                      tuple((0.0, 0.0) for _ in image), tuple(None for _ in image), tuple(image))


def test_q4_on_coarse_dem_the_imagery_widens_and_never_narrows_below_the_standard(law):
    ap = _airport(_Coarse())
    out = G.decide_edges(ap, law, [_edge([12.0] * 10)])
    assert out.moves["09/27"][0] == pytest.approx(12.0)
    out = G.decide_edges(ap, law, [_edge([-15.0] * 10)])
    assert out.moves["09/27"][0] == 0.0
    assert out.records[0]["narrower_asked_m"] == pytest.approx(15.0)
    assert "RULINGS 2026-10-27a" in out.lines[0]


def test_q4_on_lidar_the_imagery_is_only_a_check(law):
    out = G.decide_edges(_airport(_Plane()), law, [_edge([12.0] * 10)])
    assert out.moves["09/27"][0] == 0.0 and out.records[0]["role"] == "check"


# ── the law table ─────────────────────────────────────────────────────────

def test_the_witness_table_refuses_a_bad_value(law):
    t = law.tables.terrain_witness
    with pytest.raises(LawError):
        check_terrain_witness(_dc.replace(t, vote=_dc.replace(t.vote, k=0.0)), LawError)
    with pytest.raises(LawError):
        check_terrain_witness(_dc.replace(t, q5=_dc.replace(t.q5, ring_m=(60.0, 40.0))),
                              LawError)


def test_an_outvoted_end_follows_the_lidar_inside_the_noise_floor(law):
    """26v: "the end follows the lidar" — an end whose CIFP record the
    witness dropped takes the lidar even where the datum line stands within
    the lidar tier's noise of it (an apt.dat-only end keeps its datum
    there, 26e)."""
    from auto_patch_v2.constraints import runway_profile as RP
    from auto_patch_v2.model.airport import PIN_OUTVOTED
    from tests.auto_patch_v2.test_runway_end_pins import _Lidar, _site
    airport, pm = _site(law, _Lidar(0.0), (None, None), elev=700.3)
    plain = RP.end_pin_cases(pm, law, airport)
    assert {p.case for p in plain.values()} == {RP.CASE_DATUM}
    rw = airport.runways[0]
    ends = tuple(_dc.replace(e, pin_flags=PIN_OUTVOTED) for e in rw.ends)
    voted = _dc.replace(airport, runways=(_dc.replace(rw, ends=ends),))
    got = RP.end_pin_cases(pm, law, voted)
    assert {p.case for p in got.values()} == {RP.CASE_LIDAR}
    assert all(abs(p.z - 700.0) < 1e-6 for p in got.values())
