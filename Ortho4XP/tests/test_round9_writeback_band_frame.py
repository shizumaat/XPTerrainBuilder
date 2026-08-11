"""Round 9 — the writeback clamp reads THE band, in THE frame.

Spec: ``docs/specs/round9-writeback-band-frame-spec.md`` (2026-08-11,
FROZEN).

THE DEFECT these twins pin (app 1.0.233, every airport):
``assert_no_final_band_inversion`` fired on every build with a floor
sitting exactly ONE CROWN above its own hard runway/seam value at zero
route distance.  The writeback clamp built a SECOND reach band of its
own, at writeback time — after ``build_crown_drop_field`` had published
the crown field, so its ``_decrowned_anchor_seeds`` lifted values that
were still profile-space, and its ``reach_band_unified`` call overwrote
the layout's FINAL band record with that crown-shifted snapshot.  On top
of both, the clamp compared EMITTED-space corner values against a
PROFILE-space band.

The law: ONE band — the one the solve computed — carried by canonical
key, resolved (never rebuilt) by the clamp, and compared in the frame it
was computed in.

Twin 6 of the spec is ``tests/test_final_band_inversion.py``, which must
pass UNTOUCHED: the record the post-solve law assert judges is no longer
written by the writeback at all.

Synthetic fixtures only: no X-Plane install, no CIFP, no network, no DEM
download, no write anywhere.  The carriage twin runs the PRODUCTION
solver on the hand-built flat-site fixture with a constant-DEM stub.
"""
from __future__ import annotations

import os
import sys
import types

import pytest
from shapely.geometry import Polygon

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _path in (os.path.join(_ROOT, "src"), _ROOT):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import O4_UI_Utils as UI                                          # noqa: E402
from auto_patch.canonical_points import CanonicalPointRegistry    # noqa: E402
from auto_patch.elevation_per_surface import (                    # noqa: E402
    solver_primitives as SP)
from auto_patch.elevation_per_surface.node_space import (         # noqa: E402
    store_of)
from auto_patch.layout import (                                   # noqa: E402
    ROLE_APRON, SHARED_VERTEX_TOL_M, BuiltShape,
)

RING = [(0.0, 0.0), (40.0, 0.0), (40.0, 40.0), (0.0, 40.0)]


def _layout(*, band=None, crown=None, role=ROLE_APRON,
            node_altitudes=None, mint=True):
    """A one-square layout carrying THE band the way a solve carries it.

    ``band`` is the profile-space ``(floor, ceiling)`` minted on every
    corner's canonical key; ``crown`` the crown drop published for the
    same keys.  ``mint=False`` is the degenerate layout (a probe object,
    an early solve return) the clamp must read as "no carried band"
    rather than as "clamp to nothing".
    """
    shape = BuiltShape(polygon=Polygon(RING + [RING[0]]), role=role,
                       ref="test", node_altitudes=node_altitudes)
    layout = types.SimpleNamespace(shapes=[shape])
    reg = CanonicalPointRegistry(tol_m=SHARED_VERTEX_TOL_M)
    keys = [reg.get_or_add(x, y) for (x, y) in RING]
    layout.canonical_points = reg
    if mint:
        store_of(layout).mint(
            "env_band", "interval",
            {} if band is None else {key: band for key in keys},
            replace=True)
    if crown is not None:
        layout._crown_drop_key = {key: crown for key in keys}
    bucket_to_idx = {key: index for index, key in enumerate(keys)}
    return layout, shape, bucket_to_idx


def _band_warnings(monkeypatch):
    """Capture the ``[writeback-band]`` vprint lines."""
    lines: list = []
    real = UI.vprint

    def _vprint(level, *args, **kwargs):
        text = " ".join(str(a) for a in args)
        if "[writeback-band]" in text:
            lines.append((level, text))
            return None
        return real(level, *args, **kwargs)

    monkeypatch.setattr(UI, "vprint", _vprint)
    return lines


# ══════════════════════════════════════════════════════════════════════
# 1 — the crowned-seam twin: THE shipped regression
# ══════════════════════════════════════════════════════════════════════
def test_a_crowned_seam_node_at_its_own_hard_value_is_not_clamped():
    """Spec twin 1.  A hard runway/seam seed node whose carried band
    FLOOR equals its hard value, carrying a crown drop of 0.23 m.

    Its emitted value is ``hard − crown`` (both writeback call sites
    apply the crown transform back first).  The shipped code compared
    that 49.77 against a floor its own rebuild had lifted to
    ``hard + crown`` = 50.23 and clamped +0.46 m; the fix lifts the value
    into the band's own profile space, where it sits exactly ON the
    floor, and nothing moves.
    """
    hard, crown = 50.0, 0.23
    layout, shape, bucket_to_idx = _layout(band=(hard, 60.0), crown=crown)

    SP._writeback(layout, [hard - crown] * 4, bucket_to_idx)

    assert shape.node_altitudes == [49.77] * 5
    assert layout.band_clamp_findings == []


def test_the_writeback_records_nothing_about_the_final_band():
    """Spec twin 1, second half — the SNAPSHOT OVERWRITE.

    ``reach_band_unified`` → ``spine_value_fields`` →
    ``_record_band_inversions``, whose scope is "the LAST output of the
    build".  A band rebuilt at writeback time therefore REPLACED the
    real final band record that ``assert_no_final_band_inversion`` then
    judged.  With the rebuild deleted the writeback touches none of the
    three attributes — the identity checks below are the point, not the
    values.
    """
    layout, _shape, bucket_to_idx = _layout(band=(50.0, 60.0), crown=0.23)
    inversions = [{"node": 7, "deficit_m": 0.0}]
    provenance = {7: "runway_anchor"}
    layout._final_band_inversions = inversions
    layout._final_band_node_count = 41
    layout._band_anchor_provenance = provenance

    SP._writeback(layout, [49.77] * 4, bucket_to_idx)

    assert layout._final_band_inversions is inversions
    assert layout._final_band_inversions == [{"node": 7, "deficit_m": 0.0}]
    assert layout._final_band_node_count == 41
    assert layout._band_anchor_provenance is provenance


# ══════════════════════════════════════════════════════════════════════
# 2 — the frame round-trip
# ══════════════════════════════════════════════════════════════════════
def test_the_clamp_compares_in_profile_space_and_stamps_in_emitted_space():
    """Spec twin 2.  At a point with c = 0.30 and a profile floor of
    10.0, the emitted value 9.70 IS the floor and must not move; 9.65 is
    0.05 m below it and is lifted by exactly 0.05 m in emitted space."""
    at_floor, _shape, bucket_to_idx = _layout(band=(10.0, 20.0), crown=0.30)
    SP._writeback(at_floor, [9.70] * 4, bucket_to_idx)
    assert at_floor.shapes[0].node_altitudes == [9.70] * 5
    assert at_floor.band_clamp_findings == []

    below, shape, bucket_to_idx = _layout(band=(10.0, 20.0), crown=0.30)
    SP._writeback(below, [9.65] * 4, bucket_to_idx)
    assert shape.node_altitudes == [pytest.approx(9.70)] * 5
    findings = below.band_clamp_findings
    assert len(findings) == 4
    assert {finding[4] for finding in findings} == {"floor"}
    assert all(finding[3] == pytest.approx(0.05) for finding in findings)


def test_a_ceiling_escape_round_trips_the_same_way():
    """The other side of the same frame: c = 0.30, profile ceiling 20.0,
    an emitted 20.0 (profile 20.30) drops to an emitted 19.70."""
    layout, shape, bucket_to_idx = _layout(band=(10.0, 20.0), crown=0.30)

    SP._writeback(layout, [20.0] * 4, bucket_to_idx)

    assert shape.node_altitudes == [pytest.approx(19.70)] * 5
    assert {f[4] for f in layout.band_clamp_findings} == {"ceil"}
    assert all(f[3] == pytest.approx(-0.30)
               for f in layout.band_clamp_findings)


def test_with_no_crown_field_the_clamp_is_byte_identical_to_a_frameless_one():
    """Both writeback call sites can run before the crown field exists,
    and every hermetic caller has none: ``crown_drop_at`` is 0.0 and the
    round trip is the identity."""
    layout, shape, bucket_to_idx = _layout(band=(4.6, 9.4))

    SP._writeback(layout, [3.0, 6.0, 11.0, 9.4], bucket_to_idx)

    assert shape.node_altitudes == [4.6, 6.0, 9.4, 9.4, 4.6]


# ══════════════════════════════════════════════════════════════════════
# 3 — the canyon pin (R8-2's acceptance, on the carried band)
# ══════════════════════════════════════════════════════════════════════
def test_the_canyon_escape_is_clamped_off_the_carried_band():
    """Spec twin 3, and R8-2's acceptance preserved: the VHHH shape —
    solved −12.5 m at an uncrowned node against a carried [4.6, 9.4] —
    lands on 4.6 and mints a floor-side finding per corner."""
    layout, shape, bucket_to_idx = _layout(band=(4.6, 9.4))

    SP._writeback(layout, [-12.5] * 4, bucket_to_idx)

    assert shape.node_altitudes == [4.6] * 5
    findings = layout.band_clamp_findings
    assert len(findings) == 4
    assert {finding[4] for finding in findings} == {"floor"}
    assert all(finding[3] == pytest.approx(17.1) for finding in findings)
    assert {finding[1] for finding in findings} == {ROLE_APRON}


# ══════════════════════════════════════════════════════════════════════
# 4 — the carriage: THE band is minted at the line that BUILDS it
# ══════════════════════════════════════════════════════════════════════
def test_the_solve_carries_the_band_it_computed_with_no_gate(monkeypatch):
    """Spec twin 4.  ``O4_ENVELOPE_FROM_BAND`` unset — the carriage is
    unconditional, so the clamp has a band on EVERY build (the gate only
    ever governed the envelope's CONSUMPTION).  The carried values are
    ``node_band`` itself, joined by canonical key: the band is computed
    once and transported, never sampled a second time."""
    import test_flat_site_fast_path as FIXTURE
    from shapely.geometry import LineString
    from auto_patch.elevation_per_surface.route_profile import solve as SV

    for name in ("O4_ENVELOPE_FROM_BAND", "O4_ROUTE_METRIC_ENVELOPE"):
        monkeypatch.delenv(name, raising=False)

    captured: list = []
    real_node_bands = SV.node_bands

    def _spy(nodes, band, **kwargs):
        out = real_node_bands(nodes, band, **kwargs)
        captured.append((list(nodes), list(out)))
        return out

    monkeypatch.setattr(SV, "node_bands", _spy)

    layout = FIXTURE._fixture(with_tunnel=False, stamp=False)
    # THE FIXTURE'S ONE REQUIREMENT: a band that actually exists.  The
    # centerline must TERMINATE on the runway at a real pavement vertex
    # (the junction's runway-edge corner) and run through further pavement
    # vertices, or there is no runway anchor to seed from and no spine to
    # string — ``[reach-band] NO FIELD``, a band of all-``None``, and a
    # vacuous twin.
    layout.apt_taxi_centerlines = [FIXTURE._Centerline(
        LineString([(60.0, 22.0), (400.0, 400.0), (700.0, 700.0)]))]
    SV.solve_route_profile(layout, "ZZZZ", dem=FIXTURE._ConstDEM(),
                           tile_lat=FIXTURE.TILE_LAT,
                           tile_lon=FIXTURE.TILE_LON)

    assert captured, "the solve never built a band — fixture is vacuous"
    nodes, node_band = captured[0]
    carried = store_of(layout).raw("env_band")
    assert carried, "THE band was not carried"

    registry = layout.canonical_points
    expected = {}
    for index, interval in enumerate(node_band):
        if interval is None:
            continue
        key = registry.get(nodes[index][0], nodes[index][1])
        assert key is not None
        expected[key] = (float(interval[0]), float(interval[1]))
    assert carried == expected


# ══════════════════════════════════════════════════════════════════════
# 5 — no carried band: unclamped, and LOUD about it
# ══════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("kwargs", [
    {"mint": False},                    # nothing ever minted (early return)
    {"band": None},                     # minted EMPTY (every node off-net)
], ids=["absent", "empty"])
def test_without_a_carried_band_nothing_is_clamped_and_it_says_so(
        monkeypatch, kwargs):
    """Spec twin 5.  R8-2's loud-when-inert doctrine: a band-less
    writeback is not a reason to fail a build, but a silently band-less
    airport clamps nothing and nobody knows — so exactly ONE
    ``[writeback-band]`` WARN is emitted and the pass stamps exactly the
    pre-R8-2 values."""
    warnings = _band_warnings(monkeypatch)
    layout, shape, bucket_to_idx = _layout(**kwargs)

    SP._writeback(layout, [-12.5] * 4, bucket_to_idx)

    assert shape.node_altitudes == [-12.5] * 5
    assert layout.band_clamp_findings == []
    assert len(warnings) == 1, warnings
    level, text = warnings[0]
    assert level == 1
    assert "no carried band" in text and "unclamped" in text


def test_a_carried_band_warns_about_nothing(monkeypatch):
    """The control: the WARN is about the ABSENCE, so a band that
    resolved must not print it."""
    warnings = _band_warnings(monkeypatch)
    layout, _shape, bucket_to_idx = _layout(band=(4.6, 9.4))

    SP._writeback(layout, [6.0] * 4, bucket_to_idx)

    assert warnings == []


def test_the_writeback_builds_no_band_of_its_own():
    """The deletion itself: no node-list rebuild, no unified graph, no
    ``reach_band_unified`` anywhere in the writeback path — the two
    graph builds per airport are GONE, not fenced."""
    import inspect
    source = inspect.getsource(SP)
    assert not hasattr(SP, "_writeback_reach_band")
    assert "_writeback_reach_band" not in source
    assert "_NODE_LIST_PUBLISHED_ATTRS" not in source
    assert "_BAND_ATTR_ABSENT" not in source
    # Call syntax, not prose: the docstrings NAME the machinery that was
    # deleted (that is the record of why), so the assertion is that
    # nothing on the clamp path CALLS it.
    clamp_path = "\n".join(
        inspect.getsource(fn) for fn in
        (SP._carried_band_closure, SP._clamp_corner_elevs_to_band,
         SP._writeback))
    assert "reach_band_unified(" not in clamp_path
    assert "build_unified_graph(" not in clamp_path
    assert "_build_node_list(" not in clamp_path
