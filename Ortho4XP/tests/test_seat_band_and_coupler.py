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

    def m_to_ll(self, x, y):
        """The frontage-band EVIDENCE export (anchors a9d9c88) spells every
        recorded point in lat/lon; a fake layout that cannot answer it
        makes the seat pass raise.  A linear stand-in is enough — nothing
        under test reads the value."""
        return (float(y) / 111_320.0, float(x) / 111_320.0)


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


# ── A PAD INSIDE A BASIN SITS AT THE BASIN FLOOR ──────────────────────
# owner RULINGS 2026-08-25f; spec basin-pad-floor-seating-spec.md §1.1:
# "its flat level is the facility's floor elevation, not the surrounding
# grade; downstream consumers (seats, chords, strip adoption) see the
# floor value."

def test_a_declared_basin_floor_overrides_the_band_chosen_seat(monkeypatch):
    """The declaration is DECLARED TERRAIN — the same value, from the same
    pass, as the trench floor pan beside it — so it OVERRIDES the band's
    choice rather than being intersected with it.  A pit floor is not
    reachable at <= 1 % from a taxiway, and that is the point of a pit
    (LEMD: 8.53 m below the surrounding apron grade)."""
    layout, apron, pad = _big_pad_layout()
    pad.basin_floor_seat_m = 95.5
    b2i = _register(layout, [apron, pad])
    seats = _seats(layout, b2i, _big_band(), lambda x, y: 120.0,
                   {id(pad): 108.0}, monkeypatch)
    got = _level_of(seats, b2i, layout.canonical_points, pad)
    assert got == pytest.approx(95.5), (
        "a declared basin floor must not be clamped into the airside band")
    # EVERY ring node carries it — a pad is one flat level.
    cps = layout.canonical_points
    for (x, y) in list(pad.polygon.exterior.coords)[:-1]:
        assert seats[b2i[cps.get(float(x), float(y))]] == pytest.approx(95.5)


def test_the_declared_seat_publishes_its_nodes_and_pins_its_box(monkeypatch):
    """Two consumers of the same declaration: the solve's seat guards read
    the node set (they must not send a declared floor into yield-hard for
    being outside the airside band), and the bounded-yield registry holds
    a POINT box — a declared floor any later pass may yield 8 m upward is
    not declared."""
    layout, apron, pad = _big_pad_layout()
    pad.basin_floor_seat_m = 95.5
    b2i = _register(layout, [apron, pad])
    _seats(layout, b2i, _big_band(), lambda x, y: 120.0,
           {id(pad): 108.0}, monkeypatch)
    cps = layout.canonical_points
    published = getattr(layout, "_basin_pad_seat_idx")
    boxes = AN._store_of(layout).raw("seat_boxes")
    for (x, y) in list(pad.polygon.exterior.coords)[:-1]:
        k = cps.get(float(x), float(y))
        assert b2i[k] in published
        assert boxes[k] == (pytest.approx(95.5), pytest.approx(95.5))


def test_an_undeclared_pad_is_untouched_by_the_basin_law(monkeypatch):
    """The control: same geometry, no declaration, band clamp as before."""
    layout, apron, pad = _big_pad_layout()
    b2i = _register(layout, [apron, pad])
    seats = _seats(layout, b2i, _big_band(), lambda x, y: 120.0,
                   {id(pad): 108.0}, monkeypatch)
    assert _level_of(seats, b2i, layout.canonical_points, pad) == \
        pytest.approx(104.0)
    assert not getattr(layout, "_basin_pad_seat_idx")


def test_a_declared_pad_welded_to_an_undeclared_pad_withdraws(monkeypatch,
                                                              capsys):
    """MEASURED AT LEMD, arm 1 (2026-08-25).  The MERGED RIGID UNIT law is
    standing: pads sharing a ring vertex are ONE flat body at ONE level.
    A declared pad welded to an UNDECLARED neighbour therefore has two
    consistent outcomes and both are wrong — the neighbour sinks with it,
    or the declaration is discarded.  Arm 1 made the declaration anyway
    and the projection SILENTLY discarded it (``building8`` 33,237 m² and
    ``building18`` 75,885 m², three shared ring nodes, both emitting
    600.40 m against a declared 584.50).  The seat is now WITHDRAWN,
    loudly, naming both pads."""
    apron = _shape([(0.0, 0.0), (200.0, 0.0), (200.0, 40.0),
                    (100.0, 40.0), (40.0, 40.0), (0.0, 40.0)],
                   ROLE_APRON, "apron1")
    pad = _shape([(40.0, 40.0), (100.0, 40.0), (100.0, 100.0),
                  (40.0, 100.0)], ROLE_BUILDING, "big1")
    # shares the (100,40)-(100,100) edge with ``pad``
    neighbour = _shape([(100.0, 40.0), (160.0, 40.0), (160.0, 100.0),
                        (100.0, 100.0)], ROLE_BUILDING, "big2")
    pad.basin_floor_seat_m = 95.5
    layout = _FakeLayout([apron, pad, neighbour])
    b2i = _register(layout, [apron, pad, neighbour])
    seats = _seats(layout, b2i, _big_band(), lambda x, y: 120.0,
                   {id(pad): 108.0, id(neighbour): 108.0}, monkeypatch)
    assert _level_of(seats, b2i, layout.canonical_points, pad) != \
        pytest.approx(95.5)
    assert not getattr(layout, "_basin_pad_seat_idx")
    # the declaration is CLEARED, so no later pass acts on a withdrawn one
    assert pad.basin_floor_seat_m is None
    out = capsys.readouterr().out
    assert "BASIN PAD SEAT WITHDRAWN" in out, "the seat was lost SILENTLY"
    assert "big1" in out and "big2" in out


def test_two_declared_pads_welded_together_still_seat(monkeypatch):
    """The scope guard: the withdrawal is about an UNDECLARED neighbour.
    Two pads inside the same basin, welded, are one rigid body at ONE
    level — and that level is the floor both of them declare."""
    apron = _shape([(0.0, 0.0), (200.0, 0.0), (200.0, 40.0),
                    (100.0, 40.0), (40.0, 40.0), (0.0, 40.0)],
                   ROLE_APRON, "apron1")
    pad = _shape([(40.0, 40.0), (100.0, 40.0), (100.0, 100.0),
                  (40.0, 100.0)], ROLE_BUILDING, "big1")
    neighbour = _shape([(100.0, 40.0), (160.0, 40.0), (160.0, 100.0),
                        (100.0, 100.0)], ROLE_BUILDING, "big2")
    pad.basin_floor_seat_m = 95.5
    neighbour.basin_floor_seat_m = 95.5
    layout = _FakeLayout([apron, pad, neighbour])
    b2i = _register(layout, [apron, pad, neighbour])
    seats = _seats(layout, b2i, _big_band(), lambda x, y: 120.0,
                   {id(pad): 108.0, id(neighbour): 108.0}, monkeypatch)
    assert _level_of(seats, b2i, layout.canonical_points, pad) == \
        pytest.approx(95.5)
    assert _level_of(seats, b2i, layout.canonical_points, neighbour) == \
        pytest.approx(95.5)


# ══════════════════════════════════════════════════════════════════════
# PAD BINDING ROUTES — the engine CAPTURE twin
# (spec ``docs/specs/pad-binding-routes-spec.md`` §3.1)
#
# Publication only: the seat pass publishes, per pad, the RECORDED route
# that bound its seat on each side.  The twin drives the same hermetic
# fixture family as everything above — one synthetic layout, a hand-made
# band, a hand-made provenance and a hand-made unified graph — and checks
# that what is published is read out of that field rather than derived.
# ══════════════════════════════════════════════════════════════════════

#: The chain the walk must replay on the CEILING side, and its own budgets.
#: anchor 10 --4 m--> node 6 --4 m--> node 2 (the binding attachment node).
_CEIL_ANCHOR, _CEIL_NODE = 10, 2
#: anchor 11 --5 m--> node 7 --8 m--> node 3.
_FLOOR_ANCHOR, _FLOOR_NODE = 11, 3


class _RouteBand:
    """A band that also answers ``attachment_at`` — the raster band's own
    read-only provenance accessor, which is what the capture reads."""

    #: (floor, ceiling) at each apron-shared edge centre of the pad below.
    #: (20,10) carries the MINIMUM ceiling and (10,20) the MAXIMUM floor,
    #: so the two sides bind at DIFFERENT frontage points — which is the
    #: only way a twin can tell the per-side rule from a per-pad one.
    AT = {(10.0, 0.0): (100.0, 110.0, (1, 5)),
          (20.0, 10.0): (101.0, 108.0, (1, _CEIL_NODE)),
          (10.0, 20.0): (102.0, 112.0, (_FLOOR_NODE, 4)),
          (0.0, 10.0): (100.5, 111.0, (5,))}

    def __call__(self, x, y):
        rec = self.AT.get((round(float(x), 6), round(float(y), 6)))
        return (100.0, 112.0) if rec is None else (rec[0], rec[1])

    def attachment_at(self, x, y):
        rec = self.AT.get((round(float(x), 6), round(float(y), 6)))
        if rec is None:
            return None
        return {"attachment_nodes": list(rec[2]), "leg_m": 1.0,
                "off_mask_m": 0.0, "floor_at_attachment": rec[0],
                "ceiling_at_attachment": rec[1]}


class _RouteGraph:
    """The unified-graph stand-in: ``spine_adj`` + ``pos``, the two things
    the recorded-route walk reads."""

    pos = {_CEIL_ANCHOR: (-100.0, 0.0), 6: (-60.0, 0.0),
           _CEIL_NODE: (-20.0, 0.0),
           _FLOOR_ANCHOR: (-100.0, 100.0), 7: (-70.0, 100.0),
           _FLOOR_NODE: (-40.0, 100.0)}
    spine_adj = {_CEIL_NODE: [(6, 4.0)], 6: [(_CEIL_ANCHOR, 4.0),
                                             (_CEIL_NODE, 4.0)],
                 _CEIL_ANCHOR: [(6, 4.0)],
                 _FLOOR_NODE: [(7, 8.0)], 7: [(_FLOOR_ANCHOR, 5.0),
                                              (_FLOOR_NODE, 8.0)],
                 _FLOOR_ANCHOR: [(7, 5.0)]}


#: The field as ``spine_value_fields._record_anchor_provenance`` writes it.
_ROUTE_PROV = {
    "anchor_value": {_CEIL_ANCHOR: 100.0, _FLOOR_ANCHOR: 115.0},
    # ceiling(n) = anchor_value + budget → node 2 is 108.0, node 1 is 109.0
    "ceiling": {_CEIL_ANCHOR: (_CEIL_ANCHOR, 0.0), 6: (_CEIL_ANCHOR, 4.0),
                _CEIL_NODE: (_CEIL_ANCHOR, 8.0), 1: (_CEIL_ANCHOR, 9.0)},
    # floor(n) = anchor_value − budget → node 3 is 102.0, node 4 is 101.0
    "floor": {_FLOOR_ANCHOR: (_FLOOR_ANCHOR, 0.0), 7: (_FLOOR_ANCHOR, 5.0),
              _FLOOR_NODE: (_FLOOR_ANCHOR, 13.0), 4: (_FLOOR_ANCHOR, 14.0)},
}


def _route_layout():
    """A 20x20 pad (small-pad branch) whose FOUR edges are apron-shared."""
    apron_s = _shape([(-40.0, -40.0), (60.0, -40.0), (60.0, 0.0),
                      (20.0, 0.0), (0.0, 0.0), (-40.0, 0.0)],
                     ROLE_APRON, "apronS")
    apron_n = _shape([(0.0, 20.0), (20.0, 20.0), (20.0, 60.0),
                      (0.0, 60.0)], ROLE_APRON, "apronN")
    pad = _shape([(0.0, 0.0), (20.0, 0.0), (20.0, 20.0), (0.0, 20.0)],
                 ROLE_BUILDING, "pad1")
    layout = _FakeLayout([apron_s, apron_n, pad])
    return layout, [apron_s, apron_n, pad], pad


def _route_seats(monkeypatch, band, *, graph, publish=True, prov=_ROUTE_PROV):
    layout, shapes, pad = _route_layout()
    b2i = _register(layout, shapes)
    if prov is not None:
        layout._band_anchor_provenance = prov
    if publish:
        BF.publish_band_of_record(layout, band)
    monkeypatch.setattr(BF, "building_feasible_levels",
                        lambda *a, **k: {id(pad): 105.0})
    AN.build_building_seats(layout, b2i, band, lambda x, y: 105.0, [],
                            unified_graph=graph)
    return layout, pad


def test_the_pad_binding_route_is_published_per_side(monkeypatch):
    """(a) the record names the pad, the expected BINDING anchor per side,
    ``route_complete=True``, and a chain whose ends are the anchor and the
    binding attachment node."""
    band = _RouteBand()
    layout, pad = _route_seats(monkeypatch, band, graph=_RouteGraph())
    box = layout._pad_binding_routes
    assert box["nodespace"] == "n=6", "the node space must be stamped"
    recs = box["records"]
    assert [r["pad"] for r in recs] == ["pad1"]
    r = recs[0]
    assert r["off_network"] is False
    assert r["seat_m"] == pytest.approx(105.0, abs=0.01)

    ceil = r["sides"]["ceiling"]
    assert ceil["anchor_node"] == _CEIL_ANCHOR
    assert ceil["anchor_value_m"] == pytest.approx(100.0, abs=0.01)
    assert ceil["route_budget_m"] == pytest.approx(8.0, abs=0.01)
    assert ceil["route_complete"] is True
    # the BINDING frontage point is the one with the MINIMUM ceiling
    assert ceil["band_ceiling_m"] == pytest.approx(108.0, abs=0.01)
    assert ceil["band_floor_m"] == pytest.approx(101.0, abs=0.01)

    flo = r["sides"]["floor"]
    assert flo["anchor_node"] == _FLOOR_ANCHOR
    assert flo["anchor_value_m"] == pytest.approx(115.0, abs=0.01)
    assert flo["route_budget_m"] == pytest.approx(13.0, abs=0.01)
    assert flo["route_complete"] is True
    # ... and the floor side binds at the MAXIMUM-floor frontage point,
    # a DIFFERENT one — a per-pad rule could not produce this pair.
    assert flo["band_floor_m"] == pytest.approx(102.0, abs=0.01)
    assert flo["band_ceiling_m"] == pytest.approx(112.0, abs=0.01)
    assert flo["frontage_ll"] != ceil["frontage_ll"]

    # the chain runs ANCHOR → BINDING ATTACHMENT NODE, every hop
    pos = _RouteGraph.pos
    ll = layout.m_to_ll
    for (side, anchor, node) in (("ceiling", _CEIL_ANCHOR, _CEIL_NODE),
                                 ("floor", _FLOOR_ANCHOR, _FLOOR_NODE)):
        chain = r["sides"][side]["route_ll"]
        assert len(chain) == 3, "no hop may be dropped or capped"
        for (end, n) in ((chain[0], anchor), (chain[-1], node)):
            want = [round(v, 7) for v in ll(*pos[n])]
            assert end == want, f"{side} chain end is not node {n}"
        assert r["sides"][side]["anchor_ll"] == [
            round(v, 7) for v in ll(*pos[anchor])]


def test_the_published_plan_length_is_the_chain_length(monkeypatch):
    """(b) ``plan_len_m`` is the hand-computable chain length — 40+40 on the
    ceiling side, 30+30 on the floor side.  It is a PHYSICAL length, and
    deliberately not the priced budget beside it."""
    layout, _pad = _route_seats(monkeypatch, _RouteBand(), graph=_RouteGraph())
    sides = layout._pad_binding_routes["records"][0]["sides"]
    assert sides["ceiling"]["plan_len_m"] == pytest.approx(80.0, abs=0.01)
    assert sides["floor"]["plan_len_m"] == pytest.approx(60.0, abs=0.01)


def test_a_band_without_attachment_at_publishes_the_degraded_shape(
        monkeypatch):
    """(c) §1.6: a hand-made band with no ``attachment_at`` cannot be
    captured from — and says so, rather than publishing a route it did not
    read.  The seat pass itself must not fail."""
    layout, pad = _route_seats(monkeypatch, _big_band(), graph=_RouteGraph())
    assert layout._pad_binding_routes == {"nodespace": None, "records": []}


def test_no_unified_graph_publishes_the_degraded_shape(monkeypatch):
    """§1.6 again, from the other direction: every test caller passes no
    graph, and none of them may publish a route."""
    layout, pad = _route_seats(monkeypatch, _RouteBand(), graph=None)
    assert layout._pad_binding_routes == {"nodespace": None, "records": []}


def test_a_foreign_band_is_refused_loudly(monkeypatch, capsys):
    """The PASS-IDENTITY GUARD (§1.2): a band that is NOT the layout's band
    of record may carry a foreign node space, so nothing is published — and
    the refusal is loud, never a crash."""
    layout, pad = _route_seats(monkeypatch, _RouteBand(), graph=_RouteGraph(),
                               publish=False)
    assert layout._pad_binding_routes == {"nodespace": None, "records": []}
    assert "[pad-routes]" in capsys.readouterr().out


def test_an_off_band_pad_publishes_off_network(monkeypatch):
    """(d) a pad the band serves at NO frontage point is an ANSWER — the
    within-shape law governs it — and publishes ``off_network: true`` with
    its seat and no sides."""

    class _Blind(_RouteBand):
        def __call__(self, x, y):
            return None

        def attachment_at(self, x, y):
            return None

    layout, pad = _route_seats(monkeypatch, _Blind(), graph=_RouteGraph())
    recs = layout._pad_binding_routes["records"]
    assert layout._pad_binding_routes["nodespace"] == "n=6"
    assert len(recs) == 1 and recs[0]["off_network"] is True
    assert "sides" not in recs[0]
