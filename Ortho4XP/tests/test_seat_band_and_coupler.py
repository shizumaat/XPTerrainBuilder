"""Seat-law fixes from the carrier-attribution dossier (spec
``docs/specs/dossier-fixes-round-spec.md`` §2 / §3 / §4).

Hermetic — no airport build, no fixtures.  One synthetic layout per
section, driving ``anchors.build_building_seats`` directly with a hand-made
band and DEM sampler.  Covers:

  §2 SEAT-vs-BAND CONSISTENCY (standing law) — a large pad's seat clamps
     into the intersection of its selection interval and the NODE band at
     its contact nodes (the band the projection actually enforces); an
     EMPTY intersection keeps today's value and is REPORTED, never silent.
  MERGED RIGID UNITS (standing law) — pads sharing a ring vertex are ONE
     flat group at ONE level, transitively; a rigid unit whose members'
     boxes do not intersect is reported LOUD.

RETIRED HERE, 2026-08-05 ("BUILD-COMPLETE-THEN-DEBUG"): the §3
``O4_SEAT_COUPLE_SHARED_SURFACE`` twins.  Route admission SUBSUMES that
predicate — the surviving coverage is
``test_route_metric_seat_coupling.test_route_admission_subsumes_the_shared_surface_predicate``,
which drives the same U-shaped geometry through the law graph.  Coupling
twins live in that file: the coupler prices on the law graph only, and a
synthetic with no ``law_graph`` couples nothing by design.
"""
import pytest
from shapely.geometry import Polygon

from auto_patch.canonical_points import CanonicalPointRegistry
from auto_patch.config import APRON_MAX_GRADE
from auto_patch.layout import BuiltShape, ROLE_APRON, ROLE_BUILDING
from auto_patch.elevation_per_surface import building_feasibility as BF
from auto_patch.elevation_per_surface.route_profile import anchors as AN


class _FakeLayout:
    """Only what ``build_building_seats`` reads."""

    def __init__(self, shapes):
        self.shapes = shapes
        self.canonical_points = CanonicalPointRegistry()
        self.apt_taxi_centerlines = []


def _shape(ring, role, ref=""):
    return BuiltShape(polygon=Polygon(ring), role=role, ref=ref)


def _register(layout, shapes):
    """Intern every ring vertex of ``shapes`` and hand back a
    ``bucket_to_idx`` — the pads' contact nodes as the solve sees them."""
    cps = layout.canonical_points
    bucket_to_idx, idx = {}, 0
    for s in shapes:
        for (x, y) in list(s.polygon.exterior.coords)[:-1]:
            k = cps.get_or_add(float(x), float(y))
            if k not in bucket_to_idx:
                bucket_to_idx[k] = idx
                idx += 1
    return bucket_to_idx


def _seats(layout, bucket_to_idx, band, dem, levels, monkeypatch):
    monkeypatch.setattr(BF, "building_feasible_levels",
                        lambda *a, **k: levels)
    return AN.build_building_seats(layout, bucket_to_idx, band, dem, [])


def _level_of(seats, bucket_to_idx, cps, shape):
    """The seated level stamped on a pad's first ring node."""
    x, y = list(shape.polygon.exterior.coords)[0]
    return seats.get(bucket_to_idx[cps.get(float(x), float(y))])


# ── §2 seat-vs-band consistency ──────────────────────────────────────────

def _big_pad_layout():
    """A 60x60 pad (3600 m^2 => full-frontage branch) on an apron.

    ``band`` is DELIBERATELY two instruments over one population, the
    dossier's HECA building181 shape in miniature: the CENTROID (the
    selection sample) reaches 108.0, while the pad's own ring nodes reach
    only 104.0 — so the selected seat is 4 m above a level the band the
    projection enforces can reach at the pad's contact nodes.
    """
    apron = _shape([(0.0, 0.0), (200.0, 0.0), (200.0, 40.0),
                    (100.0, 40.0), (40.0, 40.0), (0.0, 40.0)],
                   ROLE_APRON, "apron1")
    pad = _shape([(40.0, 40.0), (100.0, 40.0), (100.0, 100.0),
                  (40.0, 100.0)], ROLE_BUILDING, "big1")
    layout = _FakeLayout([apron, pad])
    return layout, apron, pad


def _big_band(ring_ceiling=104.0):
    def band(x, y):
        # centroid of the pad is (70, 70); its ring vertices are at
        # y in {40, 100}.  Anything that is not the centroid reads the
        # (lower) node ceiling.
        if abs(x - 70.0) < 1e-6 and abs(y - 70.0) < 1e-6:
            return (90.0, 108.0)
        return (90.0, ring_ceiling)
    return band


def test_the_seat_clamps_into_its_node_band_by_law(monkeypatch):
    """Standing law: no env can turn the clamp off, so an unset
    environment must clamp."""
    layout, apron, pad = _big_pad_layout()
    b2i = _register(layout, [apron, pad])
    seats = _seats(layout, b2i, _big_band(), lambda x, y: 120.0,
                   {id(pad): 108.0}, monkeypatch)
    got = _level_of(seats, b2i, layout.canonical_points, pad)
    assert got == pytest.approx(104.0), (
        "the seat must clamp into the band the projection enforces")


def test_seat_clamps_into_its_own_node_band(monkeypatch, capsys):
    """The whole §2 fix: the seat may not exceed the ceiling the band the
    solve enforces gives the pad's own contact nodes."""
    layout, apron, pad = _big_pad_layout()
    b2i = _register(layout, [apron, pad])
    seats = _seats(layout, b2i, _big_band(), lambda x, y: 120.0,
                   {id(pad): 108.0}, monkeypatch)
    got = _level_of(seats, b2i, layout.canonical_points, pad)
    assert got == pytest.approx(104.0)
    text = capsys.readouterr().out
    assert "[seat-band]" in text and "big1" in text
    assert "108.000 -> 104.000" in text


def test_a_seat_already_inside_its_node_band_never_moves(monkeypatch):
    layout, apron, pad = _big_pad_layout()
    b2i = _register(layout, [apron, pad])
    # ring ceiling ABOVE the selected level → intersection contains it
    seats = _seats(layout, b2i, _big_band(112.0), lambda x, y: 120.0,
                   {id(pad): 108.0}, monkeypatch)
    got = _level_of(seats, b2i, layout.canonical_points, pad)
    assert got == pytest.approx(108.0)


def test_an_empty_intersection_is_reported_and_ships_todays_value(
        monkeypatch, capsys):
    """The split-level-seat trigger (RULINGS 2026-08-04): no common level
    ⇒ the value is UNCHANGED this round, but it is never silent."""
    layout, apron, pad = _big_pad_layout()
    b2i = _register(layout, [apron, pad])

    def band(x, y):
        if abs(x - 70.0) < 1e-6 and abs(y - 70.0) < 1e-6:
            return (106.0, 108.0)        # selection interval
        return (90.0, 104.0)             # node band — disjoint, below it
    seats = _seats(layout, b2i, band, lambda x, y: 120.0,
                   {id(pad): 108.0}, monkeypatch)
    got = _level_of(seats, b2i, layout.canonical_points, pad)
    assert got == pytest.approx(108.0), "no behaviour change on empty"
    text = capsys.readouterr().out
    assert "EMPTY big1" in text
    assert "sectioned seats" in text


# ── §3 the seat-coupler visibility predicate ─────────────────────────────

# ── MERGED RIGID UNITS: the touching-pad law ─────────────────────────────

def _touching_pads_layout():
    """Two TOUCHING pads whose feasible boxes are disjoint — the HECA
    building197↔building201 shape.  Sharing a ring vertex makes them ONE
    rigid unit; disjoint boxes make that unit's box EMPTY."""
    apron = _shape([(0.0, 0.0), (100.0, 0.0), (100.0, 60.0), (40.0, 60.0),
                    (20.0, 60.0), (0.0, 60.0)], ROLE_APRON, "apron1")
    d = _shape([(0.0, 60.0), (20.0, 60.0), (20.0, 80.0), (0.0, 80.0)],
               ROLE_BUILDING, "padD")
    e = _shape([(20.0, 60.0), (40.0, 60.0), (40.0, 80.0), (20.0, 80.0)],
               ROLE_BUILDING, "padE")
    return _FakeLayout([apron, d, e]), apron, d, e


def _touching_band(x, y):
    return (95.0, 100.0) if x < 20.0 else (104.0, 106.0)


def test_touching_pads_are_one_rigid_unit_at_one_level(monkeypatch, capsys):
    """THE LAW.  The projection makes a ring-sharing pad chain one flat
    group and broadcasts a single level over it; the seat law therefore
    seats it at one level UP FRONT rather than choosing two values the
    projection would overwrite."""
    monkeypatch.delenv("O4_SEAT_DEBUG", raising=False)
    layout, apron, d, e = _touching_pads_layout()
    b2i = _register(layout, [apron, d, e])
    levels = {id(d): 100.0, id(e): 106.0}
    seats = _seats(layout, b2i, _touching_band,
                   lambda x, y: 105.0 + 0.05 * y, levels, monkeypatch)
    cps = layout.canonical_points
    lv_d = _level_of(seats, b2i, cps, d)
    lv_e = _level_of(seats, b2i, cps, e)
    assert lv_d == lv_e, "a rigid unit has exactly one level"
    text = capsys.readouterr().out
    assert "MERGED RIGID unit(s) covering 2 pad(s)" in text
    assert "padD" in text and "padE" in text


def test_an_empty_rigid_unit_box_is_loud_and_takes_the_lowest_ceiling(
        monkeypatch, capsys):
    """``feasibility-is-guaranteed``: two touching pads whose reachable
    levels do not overlap is a LAW DEFECT to attribute, never a silence.
    The unit degenerates to the lowest member CEILING — the highest level
    every member's own frontage can actually grade to."""
    layout, apron, d, e = _touching_pads_layout()
    b2i = _register(layout, [apron, d, e])
    seats = _seats(layout, b2i, _touching_band,
                   lambda x, y: 105.0 + 0.05 * y,
                   {id(d): 100.0, id(e): 106.0}, monkeypatch)
    cps = layout.canonical_points
    assert _level_of(seats, b2i, cps, d) == pytest.approx(100.0), (
        "padD's ceiling is 100.0 and padE's is 106.0 — the unit takes 100.0")
    assert "EMPTY member-box intersection" in capsys.readouterr().out


def test_a_rigid_unit_with_a_common_level_is_not_reported_empty(
        monkeypatch, capsys):
    """The falsifier: overlapping member boxes make an ordinary unit, and
    the EMPTY wording must not fire on it."""
    layout, apron, d, e = _touching_pads_layout()
    b2i = _register(layout, [apron, d, e])
    _seats(layout, b2i, lambda x, y: (95.0, 100.0),
           lambda x, y: 105.0, {id(d): 100.0, id(e): 100.0}, monkeypatch)
    text = capsys.readouterr().out
    assert "MERGED RIGID unit(s)" in text
    assert "EMPTY member-box intersection" not in text


def test_pads_that_only_come_close_are_not_merged(monkeypatch, capsys):
    """Adjacency is the literal SHARED VERTEX in the sliced arrangement,
    never proximity (RULINGS lateral-contiguity 2026-08-02).  Two pads
    0.5 m apart share nothing and stay two units."""
    apron = _shape([(0.0, 0.0), (100.0, 0.0), (100.0, 60.0), (0.0, 60.0)],
                   ROLE_APRON, "apron1")
    d = _shape([(0.0, 60.0), (20.0, 60.0), (20.0, 80.0), (0.0, 80.0)],
               ROLE_BUILDING, "padD")
    e = _shape([(20.5, 60.0), (40.0, 60.0), (40.0, 80.0), (20.5, 80.0)],
               ROLE_BUILDING, "padE")
    layout = _FakeLayout([apron, d, e])
    b2i = _register(layout, [apron, d, e])
    seats = _seats(layout, b2i, _touching_band,
                   lambda x, y: 105.0 + 0.05 * y,
                   {id(d): 100.0, id(e): 106.0}, monkeypatch)
    cps = layout.canonical_points
    assert _level_of(seats, b2i, cps, d) != _level_of(seats, b2i, cps, e)
    assert "MERGED RIGID unit(s)" not in capsys.readouterr().out
