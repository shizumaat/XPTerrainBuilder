"""Seat-law fixes from the carrier-attribution dossier (spec
``docs/specs/dossier-fixes-round-spec.md`` §2 / §3 / §4).

Hermetic — no airport build, no fixtures.  One synthetic layout per
section, driving ``anchors.build_building_seats`` directly with a hand-made
band and DEM sampler.  Covers:

  §2 ``O4_SEAT_BAND_CONSISTENT`` — a large pad's seat clamps into the
     intersection of its selection interval and the NODE band at its
     contact nodes (the band the projection actually enforces); an EMPTY
     intersection keeps today's value and is REPORTED, never silent.
  §3 ``O4_SEAT_COUPLE_SHARED_SURFACE`` — two pads whose rings share a
     paved shape couple even when the straight chord between them is off
     pavement (the false-negative visibility predicate); pads that share
     no surface stay uncoupled; default OFF is byte-inert.
  §4 empty coupling polytope — LOUD attribution on every run (RULINGS
     2026-08-04 split-level building seats), with NO change to the shipped
     values.

THE SEAT-FLIP BATTERY (2026-08-04, lead ruling variant A) separated the
two gates and adopted §2 ONLY:

  * §2 is DEFAULT ON — measured alone it is HECA −303 law-true within with
    every other battery airport byte-identical.  Its pins below follow the
    kill-half pattern: the ON behaviour is pinned as the DEFAULT (unset
    env) and the legacy path survives as the explicit ``=0`` arm.
  * §3 is HELD DEFAULT OFF — measured alone it is KCLT **+145** law-true
    within (defects migrating from buildings into airside pavement).  It
    re-arms after ``docs/specs/route-distance-seat-coupling-spec.md``
    re-prices admission on a route-distance metric, so its pin below still
    reads "defaults off".
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


def test_seat_band_gate_defaults_on_and_clamps_the_seat(monkeypatch):
    """Seat-flip battery, 2026-08-04: with NO ``O4_`` var set — what a user
    build now does — the clamp binds."""
    monkeypatch.delenv("O4_SEAT_BAND_CONSISTENT", raising=False)
    layout, apron, pad = _big_pad_layout()
    b2i = _register(layout, [apron, pad])
    seats = _seats(layout, b2i, _big_band(), lambda x, y: 120.0,
                   {id(pad): 108.0}, monkeypatch)
    got = _level_of(seats, b2i, layout.canonical_points, pad)
    assert got == pytest.approx(104.0), (
        "the gate is DEFAULT ON — an unset env must clamp into the node band")


def test_seat_band_gate_off_leaves_the_seat_alone(monkeypatch):
    """The legacy path survives as the explicit ``=0`` arm."""
    monkeypatch.setenv("O4_SEAT_BAND_CONSISTENT", "0")
    layout, apron, pad = _big_pad_layout()
    b2i = _register(layout, [apron, pad])
    seats = _seats(layout, b2i, _big_band(), lambda x, y: 120.0,
                   {id(pad): 108.0}, monkeypatch)
    got = _level_of(seats, b2i, layout.canonical_points, pad)
    assert got == pytest.approx(108.0), (
        "gate OFF must ship the legacy frontage-band seat unchanged")


def test_seat_clamps_into_its_own_node_band(monkeypatch, capsys):
    """The whole §2 fix: the seat may not exceed the ceiling the band the
    solve enforces gives the pad's own contact nodes."""
    monkeypatch.setenv("O4_SEAT_BAND_CONSISTENT", "1")
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
    monkeypatch.setenv("O4_SEAT_BAND_CONSISTENT", "1")
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
    monkeypatch.setenv("O4_SEAT_BAND_CONSISTENT", "1")
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

def _u_apron_layout():
    """A U-shaped apron with a pad on each arm.

    The two pads sit 60 m apart across the U's MOUTH, so the straight chord
    between their nearest points is entirely off pavement (the visibility
    fraction rejects them) — while both pads' rings share vertices with the
    SAME apron ring.  That is the dossier's HEAZ building4/building5 pair
    (17.6 m apart, dv 1.108 m, rejected at frac 0.057).
    """
    apron = _shape([(0.0, 0.0), (100.0, 0.0), (100.0, 60.0), (80.0, 60.0),
                    (80.0, 20.0), (20.0, 20.0), (20.0, 60.0), (0.0, 60.0)],
                   ROLE_APRON, "apronU")
    left = _shape([(0.0, 60.0), (20.0, 60.0), (20.0, 80.0), (0.0, 80.0)],
                  ROLE_BUILDING, "padL")
    right = _shape([(80.0, 60.0), (100.0, 60.0), (100.0, 80.0),
                    (80.0, 80.0)], ROLE_BUILDING, "padR")
    # a pad that shares NO paved surface (the control): inside the corridor
    # and equally invisible, but standing on its own.
    far = _shape([(150.0, 150.0), (170.0, 150.0), (170.0, 170.0),
                  (150.0, 170.0)], ROLE_BUILDING, "padF")
    return _FakeLayout([apron, left, right, far]), apron, left, right, far


def _u_band(x, y):
    if x < 50.0:
        return (95.0, 100.0)
    if x < 120.0:
        return (95.0, 102.0)
    return (95.0, 110.0)


def _u_seats(monkeypatch):
    layout, apron, left, right, far = _u_apron_layout()
    b2i = _register(layout, [apron, left, right, far])
    levels = {id(left): 100.0, id(right): 102.0, id(far): 105.0}
    seats = _seats(layout, b2i, _u_band, lambda x, y: 105.0, levels,
                   monkeypatch)
    cps = layout.canonical_points
    return (_level_of(seats, b2i, cps, left),
            _level_of(seats, b2i, cps, right),
            _level_of(seats, b2i, cps, far))


def test_shared_surface_gate_defaults_off(monkeypatch, capsys):
    """Today: the pair is 60 m apart with a 0.6 m coupling limit and ships
    2.0 m apart, because the chord between them crosses the U's mouth.

    HELD default OFF by the seat-flip battery (2026-08-04, lead ruling
    variant A) — see the gate comment in ``anchors.py``: measured alone it
    is KCLT +145 law-true within, and it re-arms only after the
    route-distance coupling round re-prices admission."""
    monkeypatch.delenv("O4_SEAT_COUPLE_SHARED_SURFACE", raising=False)
    lv_l, lv_r, lv_f = _u_seats(monkeypatch)
    assert abs(lv_l - lv_r) == pytest.approx(2.0)
    assert "[seat-couple]" not in capsys.readouterr().out


def test_pads_sharing_a_paved_surface_couple(monkeypatch, capsys):
    monkeypatch.setenv("O4_SEAT_COUPLE_SHARED_SURFACE", "1")
    lv_l, lv_r, lv_f = _u_seats(monkeypatch)
    limit = APRON_MAX_GRADE * 60.0
    assert abs(lv_l - lv_r) <= limit + 1e-3, (
        "the pair the law binds must be offered to the coupler")
    text = capsys.readouterr().out
    assert "shared-surface adjacency admitted 1 pair(s)" in text
    assert "padL <-> padR" in text


def test_a_pad_sharing_no_surface_stays_uncoupled(monkeypatch):
    """Adjacency is the literal shared boundary in the sliced arrangement,
    never proximity (RULINGS lateral-contiguity, 2026-08-02)."""
    monkeypatch.setenv("O4_SEAT_COUPLE_SHARED_SURFACE", "1")
    lv_l, lv_r, lv_f = _u_seats(monkeypatch)
    assert lv_f == pytest.approx(105.0), (
        "a pad standing on its own pavement-free ground must not be pulled")


# ── §4 empty-polytope loudness ───────────────────────────────────────────

def _touching_pads_layout():
    """Two TOUCHING pads (gap 0.0 ⇒ coupling limit 0.0) whose feasible
    boxes are disjoint — the HECA building197↔building201 shape."""
    apron = _shape([(0.0, 0.0), (100.0, 0.0), (100.0, 60.0), (40.0, 60.0),
                    (20.0, 60.0), (0.0, 60.0)], ROLE_APRON, "apron1")
    d = _shape([(0.0, 60.0), (20.0, 60.0), (20.0, 80.0), (0.0, 80.0)],
               ROLE_BUILDING, "padD")
    e = _shape([(20.0, 60.0), (40.0, 60.0), (40.0, 80.0), (20.0, 80.0)],
               ROLE_BUILDING, "padE")
    return _FakeLayout([apron, d, e]), apron, d, e


def _touching_band(x, y):
    return (95.0, 100.0) if x < 20.0 else (104.0, 106.0)


def test_empty_polytope_is_loud_and_changes_nothing(monkeypatch, capsys):
    monkeypatch.delenv("O4_SEAT_DEBUG", raising=False)
    layout, apron, d, e = _touching_pads_layout()
    b2i = _register(layout, [apron, d, e])
    levels = {id(d): 100.0, id(e): 106.0}
    seats = _seats(layout, b2i, _touching_band,
                   lambda x, y: 105.0 + 0.05 * y, levels, monkeypatch)
    cps = layout.canonical_points
    lv_d = _level_of(seats, b2i, cps, d)
    lv_e = _level_of(seats, b2i, cps, e)
    # values UNCHANGED — this round lands the loudness only
    assert lv_d == pytest.approx(100.0)
    assert lv_e == pytest.approx(106.0)
    text = capsys.readouterr().out
    assert "EMPTY POLYTOPE" in text
    assert "padD" in text and "padE" in text
    assert "gap=0.0 m" in text
    assert "ring relief" in text


def test_a_feasible_polytope_reports_no_emptiness(monkeypatch, capsys):
    layout, apron, d, e = _touching_pads_layout()
    b2i = _register(layout, [apron, d, e])
    levels = {id(d): 100.0, id(e): 100.0}
    _seats(layout, b2i, lambda x, y: (95.0, 100.0),
           lambda x, y: 105.0, levels, monkeypatch)
    assert "EMPTY POLYTOPE" not in capsys.readouterr().out
