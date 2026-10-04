"""THE ROAD FEED JOINS THE ONE GRAPH — cycle 9's twins.

Spec: ``docs/specs/cycle9-road-feed-spec.md``, implementing RULINGS
2026-08-06 "ONE graph: groundside joins the route graph" and
"Service-road mouths seat like apron-edge buildings".

THE MEASURED DEFECT (c8fin's STOP dossier).  ``layout.apt_taxi_centerlines``
carries the apt.dat row-1206 ground-vehicle routes and nothing else — HECA
5, KCLT 15, SPJC 15, HEAZ 0 — so those were the only service edges the ONE
graph ever contained.  The roads that actually CARVE the slice, and that the
emitter ships as ``service_road`` / ``service_junction`` shapes, come from
the per-airport ROAD FEED (HECA 705 lines / 97.9 km after free-road
scoping).  They cut groundside geometry and then never became route edges,
so nothing downstream of them could reach a band: mouths fired, the band
propagated, and the stranded lots still kept their DEM seed.  That is the D′
population.

THE FIX UNDER TEST.  ONE enumeration — ``grade_graph.centerline_specs`` —
is the law's centerline membership, and the service half of it reads the
SLICE's own scoped road set (``layout._slice_service_subsegments``): the
row-1206 routes and the feed ways alike, after free-road scoping (owner
2026-07-27 — a road inside or edge-sharing an apron IS the apron, never
carved, so never its own spine).

THE LOCKSTEP is the point of the shared enumeration.  ``build_context`` is
the SOLVER-and-VALIDATOR context; ``verification.taxi_axes_exact_ll`` is the
SIDECAR mirror the census reads back as ``axes_exact``.  They used to be two
hand-kept copies of the same walk, so a membership change in one was
invisible to the other and the census would judge a patch under a spine the
build never graded to (the half-landed-law defect the RULINGS forbid).  Both
now consume the same list, and the three-way agreement — solver context,
sidecar, census reader — is asserted here directly.

Hand-computed geometry, no build, no network.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest
from shapely.geometry import LineString, Point

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def cg():
    return _load("road_feed_twin_check_grade", ROOT / "tools" / "check_grade.py")


# ══════════════════════════════════════════════════════════════════════
# THE SYNTHETIC AIRPORT (plan metres)
#
#   TAXI centerline T   : x = 0, y = −100 … +100  (an ICAO "C" route)
#   APT service route A : y = 0,  x = 0 … 50      (the row-1206 road)
#   FEED subsegments    : the slice's scoped road set —
#       F1 (the free remains of A, apron portion scoped away)
#       F2 a feed way running out to a lot, 60 m further
#
#   The apt.dat road A is NOT independently registered when the slice ran:
#   F1 IS its scoped remains, and registering both would double-spine the
#   same physical road.
# ══════════════════════════════════════════════════════════════════════
TAXI_PTS = [(0.0, -100.0), (0.0, 100.0)]
APT_SVC_PTS = [(0.0, 0.0), (50.0, 0.0)]


class _FakeCenterline:
    """The ``apt_dat_reader.TaxiCenterline`` surface the law reads."""

    def __init__(self, pts, is_service=False, seg_sizes=None):
        self.line = LineString(pts)
        self.route_line = None
        self.is_service = is_service
        self.name = "svc" if is_service else "T"
        self.seg_sizes = (list(seg_sizes) if seg_sizes is not None
                          else [""] * (len(pts) - 1))


class _FakeLayout:
    """Minimal layout: what both law readers actually touch."""

    def __init__(self, *, sliced=None):
        self.icao = "TEST"
        self.shapes = []
        self.anchor = (0.0, 0.0)
        self.canonical_points = None
        self.apt_taxi_centerlines = [
            _FakeCenterline(TAXI_PTS, seg_sizes=["C"]),
            _FakeCenterline(APT_SVC_PTS, is_service=True),
        ]
        if sliced is not None:
            self._slice_service_subsegments = [LineString(p) for p in sliced]

    # the local-metre → lat/lon map the sidecar export uses
    def m_to_ll(self, x, y):
        return (y / 111320.0, x / 111320.0)


# ── 1. the service SOURCE ────────────────────────────────────────────


# ── 2. THE LOCKSTEP: solver context ↔ sidecar ↔ census reader ────────


def test_a_legacy_sidecar_without_the_flag_still_reads(cg, tmp_path):
    """Sidecars written before the flag existed carry 3-element entries and
    must read as all-taxi — which is exactly how they were graded."""
    patch = tmp_path / "old.osm"
    (tmp_path / "old.osm.axes.json").write_text(json.dumps({
        "axes_exact": [[[[0.0, 0.0], [0.001, 0.0]], [0.015], 0]],
        "routes_exact": [[[0.0, 0.0], [0.001, 0.0]]],
        "anchor": [0.0, 0.0], "ruleset": "icao",
    }), encoding="utf-8", newline="")
    law = cg.law_context_from_sidecar(patch)
    assert [e[4] for e in law["taxi_axes_ll"]] == [False]


def test_axes_exact_is_the_wired_sidecar_key(cg):
    """No new sidecar key is minted: the feed rides the existing exact-axes
    contract, so ``SIDECAR_LAW_KEYS`` (the twin-asserted key registry) is
    already complete for it."""
    assert cg.SIDECAR_LAW_KEYS["axes_exact"] == "taxi_axes_ll"


# ── 3. the graph half: the feed becomes route edges ──────────────────


# ── 4. a truck route is not an aircraft spine (the Q4 gate's law) ────


# ── 5. THE READER HALF: the flag has to REACH the mint ───────────────
#
# Section 4 above twins the SOLVER-side rule.  The census reader states the
# same rule at its own mint site (``_check_transverse_grade``:
# ``_axis_is_svc`` + ``_GROUNDSIDE_ROLES``) — but it resolved the flag by
# TUPLE POSITION, and ``run_checks``' lat/lon → metre conversion truncated
# the axis tuple at 4 slots, dropping it.  So the rule was written, stated
# in a comment, and never fired: every axis read as an aircraft spine and
# service axes stamped apron cross-sections they have no spine for.
#
# MEASURED (cycle 10, clean-tree re-run, the four tmp/c10 patches, one
# instrument): ``transverse::apron|apron`` arm A / arm B — 10 000 m
# 185 / 205, −500 m 210 / 197.  With the flag carried: 57 / 69 and 62 / 54.
# 555 rows removed over the four patches, every one traceable to a service
# axis, none also minted by a taxi axis, no other class moved in any arm or
# world.  These three tests are what make that a property instead of a run.

def test_the_sidecar_service_flag_survives_the_metre_frame_conversion(cg):
    """THE HOLE ITSELF.  ``law_context_from_sidecar`` emits 5 slots
    (pts, seg_caps, None, route_ordinal, is_service); the metre-frame
    conversion must hand all five on, because both readers resolve the
    flag positionally.  Legacy 3- and 4-slot sidecars keep their length
    and read as all-taxi — that is how they were graded."""
    def ll_to_m(lat, lon):
        return (float(lon), float(lat))

    axes_ll = [
        ([(0.0, 0.0), (0.0, 200.0)], [0.015], None, 0, False),   # taxi
        ([(0.0, 0.0), (0.0, 200.0)], [0.080], None, 1, True),    # service
        ([(0.0, 0.0), (0.0, 200.0)], [0.015], None, 2),          # legacy 4
        ([(0.0, 0.0), (0.0, 200.0)], [0.015], None),             # legacy 3
        ([(0.0, 0.0)], [0.015], None, 4, True),                  # degenerate
    ]
    out = cg._axes_to_m(axes_ll, ll_to_m)
    assert len(out) == 4, "the <2-point axis must still be dropped"
    assert len(out[0]) == 5 and out[0][4] is False
    assert len(out[1]) == 5 and out[1][4] is True, (
        "the IS_SERVICE flag was dropped in the metre-frame conversion — "
        "every service axis then reads as an aircraft spine")
    assert len(out[2]) == 4 and len(out[3]) == 3
    assert out[1][0] == [(0.0, 0.0), (200.0, 0.0)]
    assert cg._axes_to_m(None, ll_to_m) is None


# One 40 m-wide surface with a 4 m cross-fall (10 %, far past every
# transverse cap), and one straight axis down its middle.
_XS_COORDS = {"1": (0.0, -20.0), "2": (200.0, -20.0),
              "3": (200.0, 20.0), "4": (0.0, 20.0)}
_XS_NODES = {k: (float(k), 0.0) for k in _XS_COORDS}


def _xs_ll_to_m(lat, lon):
    return _XS_COORDS[f"{int(lat)}"]


def _xs_way(cg, role):
    return cg.Way(wid="-1", role=role, ref="", aeroway="",
                  nids=["1", "2", "3", "4"],
                  elevs=[100.0, 100.0, 104.0, 104.0], tags={"role": role})


def _svc_axis(is_service):
    """The same physical service road, with and without its flag: slot 5
    present is the fixed reader, absent is the pre-fix truncation."""
    axis = ([(0.0, 0.0), (200.0, 0.0)], [0.08], None, 0)
    return [axis + (True,)] if is_service else [axis]


def test_a_service_axis_may_not_mint_an_apron_cross_section(cg):
    """REFUSED AT MINT.  A truck route crossing an apron is not that
    apron's spine, so the cross-section it would stamp is an instrument
    artefact — the row must not exist.  The un-flagged arm is the positive
    control: the geometry IS a 10 % cross-fall, so the refusal is the
    rule firing, not an absent violation."""
    apron = _xs_way(cg, "apron")
    pre, _s, pre_rows, _sh = cg._check_transverse_grade(
        [apron], _XS_NODES, _xs_ll_to_m, _svc_axis(False))
    assert pre, "control: the un-flagged axis must mint the cross-section"
    assert pre[0].grade_pct == pytest.approx(10.0, abs=0.1)

    post, _s2, post_rows, _sh2 = cg._check_transverse_grade(
        [apron], _XS_NODES, _xs_ll_to_m, _svc_axis(True))
    assert not post, (
        "a SERVICE axis stamped an apron cross-section — the rule the "
        "reader states (_axis_is_svc + _GROUNDSIDE_ROLES) did not fire")
    assert post_rows == 0, "the row was censused and then merely forgiven"


def test_a_service_axis_still_mints_its_own_groundside_cross_section(cg):
    """The positive control, by ROLE not by deletion (the twin of
    ``test_the_road_is_still_its_own_spine``): the same flagged axis over
    a GROUNDSIDE surface keeps its cross-section — the road's own face is
    exactly what a service axis is the spine for."""
    road = _xs_way(cg, "service_junction")
    kept, _s, rows, _sh = cg._check_transverse_grade(
        [road], _XS_NODES, _xs_ll_to_m, _svc_axis(True))
    assert kept, "the service axis lost its OWN cross-section"
    assert rows > 0
    assert kept[0].grade_pct == pytest.approx(10.0, abs=0.1)
