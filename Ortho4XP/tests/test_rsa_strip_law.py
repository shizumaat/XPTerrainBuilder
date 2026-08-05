"""RSA law round (Fable spec 2026-08-04, docs/specs/rsa-law-round-spec.md):
strip PRECEDENCE (§1, standards gap G-1 general) and the ABEAM-LONGITUDINAL
family (§2, gap G-2).

Headless: synthetic geometry and pure law calls only.  What these tests pin
is (a) that the constants say what the cited regulation says, (b) that the
GENERATION-BINDING half really binds — a patch that violates the law cannot
be emitted — and (c) that the emitter and the validator read the SAME law
function, which is the grade-law completeness standard's "twin" requirement
(docs/RULINGS.md).
"""
import importlib
import math
import os
import random
import sys

import pytest

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (os.path.join(_REPO, "src"), os.path.join(_REPO, "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from auto_patch import config as CFG                     # noqa: E402
from auto_patch import grade_law as GL                   # noqa: E402
import check_grade as CG                                 # noqa: E402


def _straight_runway_ring(length_m=3000.0, half_width_m=22.5):
    return [(0.0, -half_width_m), (length_m, -half_width_m),
            (length_m, half_width_m), (0.0, half_width_m)]


# ── §2 constants vs the primary sources ─────────────────────────────

def test_icao_longitudinal_table_matches_annex_14_3_4_13():
    """ICAO Annex 14 Vol I §3.4.13, verbatim: 1.5 % at code 4, 1.75 % at
    code 3, 2 % at code 1 or 2."""
    assert CFG.RUNWAY_STRIP_MAX_LONGITUDINAL_SLOPE_BY_CODE == {
        1: 0.020, 2: 0.020, 3: 0.0175, 4: 0.015}
    assert GL.runway_strip_max_longitudinal_slope(4) == 0.015
    assert GL.runway_strip_max_longitudinal_slope(3) == 0.0175
    assert GL.runway_strip_max_longitudinal_slope(2) == 0.020
    assert GL.runway_strip_max_longitudinal_slope(1) == 0.020


def test_faa_constant_is_the_runways_own_cap_not_a_new_number():
    """FAA AC 150/5300-13B §3.16.5 item 1: between the ends the RSA takes
    "the same as the comparable standards for the runway" — so the FAA-side
    constant must BE the runway constant, never a second copy of 1.5 %."""
    assert (CFG.RUNWAY_STRIP_MAX_LONGITUDINAL_SLOPE_FAA
            is CFG.RUNWAY_MAX_GRADE)
    for code in (1, 2, 3, 4):
        assert (GL.runway_strip_max_longitudinal_slope(code, "faa")
                == CFG.RUNWAY_MAX_GRADE)


# ── §2 run splitting (the shared emitter/validator selection) ───────

def test_runs_break_on_transverse_steps():
    """A band ring is "inner row out, outer row back": the two turn corners
    are TRANSVERSE steps and must not be read as longitudinal ones."""
    ring = [(0.0, 5.0), (50.0, 5.0), (50.0, 60.0), (0.0, 60.0)]
    runs = GL.runway_strip_longitudinal_runs(ring, (1.0, 0.0))
    assert runs == [[0, 1], [2, 3]]


def test_runs_break_outside_the_footprint():
    pts = [(0.0, 0.0), (10.0, 0.0), (20.0, 0.0), (30.0, 0.0)]
    inside = [True, True, False, True]
    assert GL.runway_strip_longitudinal_runs(
        pts, (1.0, 0.0), inside) == [[0, 1]]


# ── §2 the generation-binding clamp ─────────────────────────────────

def test_clamp_is_identity_on_lawful_ground():
    pts = [(i * 50.0, 0.0) for i in range(6)]
    alts = [10.0 + i * 0.7 for i in range(6)]          # 1.4 % < 1.5 %
    assert GL.runway_strip_longitudinal_clamp(
        pts, alts, (1.0, 0.0), 0.015) == alts


def test_clamp_cuts_a_hump_without_lifting_lawful_neighbours():
    pts = [(i * 50.0, 0.0) for i in range(4)]
    out = GL.runway_strip_longitudinal_clamp(
        pts, [10.0, 10.0, 20.0, 10.0], (1.0, 0.0), 0.015)
    assert out[0] == pytest.approx(10.0)
    assert out[3] == pytest.approx(10.0)
    assert out[2] == pytest.approx(10.75)             # 1.5 % over 50 m


def test_clamp_fills_a_pit_symmetrically():
    pts = [(i * 50.0, 0.0) for i in range(4)]
    out = GL.runway_strip_longitudinal_clamp(
        pts, [10.0, 10.0, 0.0, 10.0], (1.0, 0.0), 0.015)
    assert out[2] == pytest.approx(9.25)


def test_clamp_never_moves_a_pinned_pavement_vertex():
    pts = [(i * 50.0, 0.0) for i in range(4)]
    alts = [10.0, 10.0, 20.0, 10.0]
    out = GL.runway_strip_longitudinal_clamp(
        pts, alts, (1.0, 0.0), 0.015,
        pinned=[False, False, True, False])
    assert out[2] == pytest.approx(20.0)              # pinned, held


def test_clamp_output_satisfies_the_law_it_enforces():
    """The binding half must actually bind: over random unlawful chains the
    clamped profile is Lipschitz at the cap on every consecutive pair."""
    rng = random.Random(20260804)
    for _ in range(400):
        n = rng.randint(2, 40)
        s = 0.0
        pts = []
        for _k in range(n):
            pts.append((s, 0.0))
            s += rng.uniform(1.0, 12.0)
        alts = [rng.uniform(0.0, 30.0) for _ in range(n)]
        out = GL.runway_strip_longitudinal_clamp(
            pts, alts, (1.0, 0.0), 0.015)
        for k in range(1, n):
            ds = pts[k][0] - pts[k - 1][0]
            assert abs(out[k] - out[k - 1]) <= 0.015 * ds + 1e-9


def test_clamp_only_touches_ground_inside_the_footprint():
    pts = [(i * 50.0, 0.0) for i in range(4)]
    alts = [10.0, 10.0, 20.0, 10.0]
    out = GL.runway_strip_longitudinal_clamp(
        pts, alts, (1.0, 0.0), 0.015,
        inside=[False, False, False, False])
    assert out == alts


# ── §1/§2 gating: OFF must be structurally inert ────────────────────

def test_gate_defaults_off_and_zone_is_none():
    assert CFG.STRIP_PRECEDENCE_ENABLED is False
    from auto_patch import adjacent_ground as AG
    assert AG.runway_strip_lateral_zone(object()) is None


def test_gate_on_builds_the_lateral_half_of_the_wall_footprint():
    """§1 must not mint a second geometry: the law-swap zone is the
    LATERAL rectangle of the wall keepout footprint (between the ends;
    the end corridors keep the runway-END regime's own law)."""
    os.environ["O4_STRIP_PRECEDENCE"] = "1"
    try:
        cfg = importlib.reload(CFG)
        ag = importlib.reload(
            importlib.import_module("auto_patch.adjacent_ground"))
        assert cfg.STRIP_PRECEDENCE_ENABLED is True

        class _Shape:
            role = "runway"
            ref = "09/27"

            def __init__(self, poly):
                self.polygon = poly

        from shapely.geometry import Polygon
        ring = _straight_runway_ring()
        layout = type("_L", (), {})()
        layout.shapes = [_Shape(Polygon(ring))]
        zone = ag.runway_strip_lateral_zone(layout)
        assert zone is not None
        a, b, width = GL.runway_axis_and_width(ring)
        lateral = GL.runway_strip_lateral_footprint_ring(a, b, width)
        assert zone.context.equals(Polygon(lateral))
        # …and it is strictly INSIDE the full wall footprint (the ends).
        wall = ag.runway_strip_wall_keepout(layout, require_gate=False)
        assert zone.context.difference(wall).area == pytest.approx(0.0)
        assert wall.area > zone.context.area
    finally:
        os.environ.pop("O4_STRIP_PRECEDENCE", None)
        importlib.reload(CFG)
        importlib.reload(importlib.import_module("auto_patch.adjacent_ground"))
        importlib.reload(importlib.import_module("auto_patch.verification"))


# ── §1 lockstep: emitter march and validator mirror defer together ──

def test_strip_interior_stations_are_governed_not_dropped():
    """MIRROR 7 (lead ruling 2026-08-04).  A non-runway station inside the
    lateral strip must be KEPT by BOTH halves — the emitter builds its band
    from the STRIP closures, the validator judges it by the STRIP family —
    and never dropped (dropping left that ground at raw DEM inside a strip
    Annex 14 §3.4.11-13 says must be prepared)."""
    from shapely.geometry import Polygon
    from shapely.prepared import prep
    from auto_patch import adjacent_ground as AG
    from auto_patch import verification as VF

    a, b, width = GL.runway_axis_and_width(_straight_runway_ring())
    zone = prep(Polygon(
        GL.runway_strip_lateral_footprint_ring(a, b, width)))
    # An apron ring straddling the strip edge: y 40 m (inside the 75 m
    # graded strip) to y 130 m (outside it).
    coords = [(500.0, 40.0), (900.0, 40.0), (900.0, 130.0),
              (500.0, 130.0), (500.0, 40.0)]
    ring_alts = [100.0] * len(coords)
    ccw = True

    def _no_static(_px, _py):
        return False

    class _Prep:
        @staticmethod
        def contains(_pt):
            return False

    strip_law = (lambda d: 1.0, lambda d: -1.0, 75.0, 100.0, 0.3, None)
    zone_rows: list = []
    strip_bands: list = []
    _f, _c, stations, st_alts, _o = AG._derive_shape_stations_and_bands(
        coords, ccw, ring_alts, None, 40.0, 100.0, 0.3,
        lambda d: 1.0, lambda d: 1.0, 5.0, _Prep, set(),
        lambda x, y: 100.0, zone_rows_out=zone_rows,
        strip_zone_prep=zone, strip_law=strip_law,
        strip_bands_out=strip_bands)
    # EVERY station keeps a reference — none is dropped by the strip law.
    inside = [i for i, (x, y) in enumerate(stations) if y < 75.0]
    assert inside, "the fixture must put stations inside the strip"
    assert all(st_alts[i] is not None for i in inside)
    assert AG._APPARATUS_HITS["strip_law_governed_stations"] > 0

    # …and the ground they own is built under the STRIP law, not this
    # shape's own: the strip-law bands come back on their own channel and
    # their zone rows are TAGGED, which is what makes the pre-solve
    # constructor bound them by the strip envelope (NOT the apron's).
    assert strip_bands, "strip-interior stations must produce strip bands"
    tagged = [row for row in zone_rows if row.get("strip_law")]
    assert tagged, "the strip-law rows must be tagged for the constructor"
    # No UNTAGGED row sits on strip-interior ground — the two laws never
    # govern the same patch.  NOTE the scope this pins: the swap is decided
    # per STATION (its seed and its outward probe), so a station just
    # OUTSIDE the strip whose band marches inward is own-law by
    # construction; that boundary case is a per-point refinement, recorded
    # in the round's results, not something this test claims is handled.
    from shapely.geometry import Point as _Pt
    for row in zone_rows:
        if row.get("strip_law"):
            continue
        for px, py in row["pts"]:
            assert not zone.contains(_Pt(px, py)), (
                "an own-law row may not sit on strip-interior ground")

    v_in_strip: list = []
    (vx, vy, _outn, v_ref, _flag, _seam,
     _end) = VF._adjacent_ground_stations(
        coords, ccw, ring_alts, None, 5.0, set(), _no_static,
        strip_zone_prep=zone, in_strip_out=v_in_strip)
    # The validator keeps them too, and MARKS them as strip-governed.
    assert any(v_in_strip)
    for i, flag in enumerate(v_in_strip):
        if flag:
            assert v_ref[i] is not None
    marked = {(round(x, 3), round(y, 3))
              for x, y, f in zip(vx, vy, v_in_strip) if f}
    assert marked and all(y < 75.0 + 1e-6 for _x, y in marked)


# ── §2 validator twin: the reader over an emitted patch ─────────────

def _write_patch(tmp_path, band_alts, y0=20.0, step=25.0):
    """A minimal patch: one runway way + one graded_strip band whose outer
    row runs ALONG the runway inside the strip, with the given altitudes."""
    lat0, lon0 = 0.0, 0.0
    m_per_deg = math.pi * 6378137.0 / 180.0

    def _ll(x, y):
        return (y / m_per_deg + lat0, x / m_per_deg + lon0)

    nodes = []
    ways = []
    nid = [-1]

    def _way(pts, alts, role, ref):
        ids = []
        for (x, y), a in zip(pts, alts):
            nid[0] -= 1
            lat, lon = _ll(x, y)
            nodes.append(
                f"<node id='{nid[0]}' visible='true' lat='{lat:.11f}' "
                f"lon='{lon:.11f}'><tag k='alt_abs' v='{a:.2f}'/></node>")
            ids.append(nid[0])
        nid[0] -= 1
        body = "".join(f"<nd ref='{i}'/>" for i in ids + [ids[0]])
        ways.append(
            f"<way id='{nid[0]}' visible='true'>{body}"
            f"<tag k='role' v='{role}'/><tag k='ref' v='{ref}'/></way>")

    # Densified long edges: ``runway_axis_and_width`` takes the principal
    # axis of the vertex cloud, and a 4-corner ring whose closing vertex
    # repeats one corner tilts that axis by a few milliradians.  Real
    # runway rings carry many vertices; the fixture matches them.
    rw = []
    for i in range(21):
        rw.append((i * 150.0, -22.5))
    for i in range(21):
        rw.append(((20 - i) * 150.0, 22.5))
    _way(rw, [100.0] * len(rw), "runway", "09/27")
    n = len(band_alts)
    pts = ([(500.0 + i * step, y0) for i in range(n)]
           + [(500.0 + (n - 1 - i) * step, y0 + 8.0) for i in range(n)])
    _way(pts, list(band_alts) + list(band_alts)[::-1],
         "graded_strip", "adjacent_ground")
    out = tmp_path / "patch.osm"
    out.write_text(
        "<?xml version='1.0' encoding='UTF-8'?>\n<osm version='0.6'>\n"
        + "\n".join(nodes) + "\n" + "\n".join(ways) + "\n</osm>\n")
    return out


def _read_rows(path):
    nodes, ways = CG._parse_osm(path, feature_out={})
    ll_to_m = CG._ll_to_m_factory(nodes)
    return CG._check_strip_longitudinal_grade(ways, nodes, ll_to_m)


def test_reader_is_silent_with_the_gate_off(tmp_path):
    patch = _write_patch(tmp_path, [100.0, 100.0, 110.0, 100.0])
    rows, pairs, _ways = _read_rows(patch)
    assert rows == [] and pairs == 0


def test_reader_flags_an_over_cap_along_axis_pair(tmp_path):
    os.environ["O4_STRIP_PRECEDENCE"] = "1"
    try:
        # config carries the gate; check_grade snapshots it at import, so
        # BOTH modules must be reloaded (reloading only the reader picks up
        # the cached, gate-off config).
        importlib.reload(CFG)
        cg = importlib.reload(CG)
        patch = _write_patch(tmp_path, [100.0, 100.0, 110.0, 100.0])
        nodes, ways = cg._parse_osm(patch, feature_out={})
        ll_to_m = cg._ll_to_m_factory(nodes)
        rows, pairs, n_ways = cg._check_strip_longitudinal_grade(
            ways, nodes, ll_to_m)
        assert pairs > 0
        assert rows, "a 40 % along-axis step inside the strip must flag"
        assert rows[0].grade_pct > 1.5
        assert n_ways == 1
    finally:
        os.environ.pop("O4_STRIP_PRECEDENCE", None)
        importlib.reload(CFG)
        importlib.reload(CG)


def test_clamped_ground_passes_its_own_reader(tmp_path):
    """LOCKSTEP, the point of the round: run the EMITTER's law over the
    unlawful profile, emit that, and the VALIDATOR must find nothing."""
    os.environ["O4_STRIP_PRECEDENCE"] = "1"
    try:
        importlib.reload(CFG)
        cg = importlib.reload(CG)
        raw = [100.0, 100.0, 110.0, 100.0]
        pts = [(500.0 + i * 25.0, 40.0) for i in range(len(raw))]
        fixed = GL.runway_strip_longitudinal_clamp(
            pts, raw, (1.0, 0.0), GL.runway_strip_max_longitudinal_slope(4))
        patch = _write_patch(tmp_path, [round(v, 1) for v in fixed])
        nodes, ways = cg._parse_osm(patch, feature_out={})
        ll_to_m = cg._ll_to_m_factory(nodes)
        rows, pairs, _n = cg._check_strip_longitudinal_grade(
            ways, nodes, ll_to_m)
        assert pairs > 0
        assert rows == [], [(r.grade_pct, r.distance_m) for r in rows]
    finally:
        os.environ.pop("O4_STRIP_PRECEDENCE", None)
        importlib.reload(CFG)
        importlib.reload(CG)


# ── §2 completeness: the RESULTING surface, not only emitted pairs ──

def test_resulting_surface_reader_covers_unemitted_ground():
    """Lead requirement 2026-08-04: because the corridor emits NOTHING
    where the DEM already conforms, "no band here" must be a VERIFIED
    state.  The DEM-aware reader walks the strip along the axis and reads
    the resulting surface — emitted shape where one covers, raw DEM where
    none does — so un-emitted ground is judged, not skipped."""
    from auto_patch import verification as VF

    groups = [((0.0, 0.0), (1.0, 0.0), 3000.0, 75.0, 0.015)]

    def _flat(_x, _y):
        return (100.0, False, "dem")

    def _lawful(x, _y):
        return (100.0 + 0.014 * x, False, "dem")   # 1.4 % < 1.5 %

    def _unlawful(x, _y):
        return (100.0 + 0.030 * x, False, "dem")   # 3 % — pure DEM, no band

    def _pavement(x, _y):
        return (100.0 + 0.030 * x, True, "shape")  # runway's own law

    assert VF._strip_longitudinal_scan(groups, _flat) == []
    assert VF._strip_longitudinal_scan(groups, _lawful) == []
    rows = VF._strip_longitudinal_scan(groups, _unlawful)
    assert rows, "un-emitted DEM over the cap must be flagged"
    assert rows[0][4] == pytest.approx(0.030, abs=1e-6)
    assert rows[0][5] == pytest.approx(0.015)
    # …and the row says the ground is raw DEM at both ends, which is what
    # distinguishes "the corridor left this alone" from "a band is wrong".
    assert rows[0][6] == "dem" and rows[0][7] == "dem"
    # …and pavement-to-pavement pairs stay with the pavement laws.
    assert VF._strip_longitudinal_scan(groups, _pavement) == []


def test_resulting_surface_reader_is_silent_with_the_gate_off():
    """The whole family is one gate: gate off, the reader returns [] before
    it touches geometry (so it cannot cost a default build anything)."""
    from auto_patch import verification as VF
    assert CFG.STRIP_PRECEDENCE_ENABLED is False
    assert VF.check_strip_longitudinal(object(), None, 0, 0) == []
