"""PADS AS BAND-BOUNDED VARIABLES — the §2 twins (spec
``docs/specs/pads-as-band-variables-spec.md``; owner rulings RULINGS
2026-08-27 late).

Hermetic: no airport build, no fixture patch, no network.  The pure
interval arithmetic is stated on plain numbers, and the two end-to-end
twins drive ``anchors.build_building_seats`` directly with a hand-made
band and DEM sampler — the same fixture family
``tests/test_seat_band_and_coupler.py`` established.

The five twins §2 names:

  1. pad between two-level aprons — the solved value lands INSIDE its
     domain and minimises over-cap rows against the median-seat control;
     the flag OFF reproduces that control exactly;
  2. group accommodation — authored offsets preserved exactly;
  3. group split — the ledger carries the forcing rows, the members are
     lawful individually, and authored offsets survive WITHIN each piece;
  4. empty domain — a ``law_band_contradictions`` entry and the build
     continues (report-first); the refuse arm raises;
  5. solver symmetry — the pad variable moves toward the membrane
     optimum; a derived pad carries no one-sided seniority.
"""
import pytest
from shapely.geometry import Polygon

from auto_patch import config as CFG
from auto_patch import pad_variables as PV
from auto_patch.canonical_points import CanonicalPointRegistry
from auto_patch.law_band import CONTRADICTION_STORE, LawBandRefusal
from auto_patch.layout import BuiltShape, ROLE_APRON, ROLE_BUILDING
from auto_patch.elevation_per_surface import building_feasibility as BF
from auto_patch.elevation_per_surface.route_profile import anchors as AN


# ── the fixture family (mirrors tests/test_seat_band_and_coupler.py) ─────

class _FakeLayout:
    def __init__(self, shapes, icao="TEST"):
        self.icao = icao
        self.shapes = shapes
        self.canonical_points = CanonicalPointRegistry()
        self.apt_taxi_centerlines = []

    def m_to_ll(self, x, y):
        return (float(y) / 111_320.0, float(x) / 111_320.0)


def _shape(ring, role, ref=""):
    return BuiltShape(polygon=Polygon(ring), role=role, ref=ref)


def _register(layout, shapes):
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
    x, y = list(shape.polygon.exterior.coords)[0]
    return seats.get(bucket_to_idx[cps.get(float(x), float(y))])


def _arm(monkeypatch, on):
    """The flag, at CALL time — ``pads_band_variables_enabled`` reads the
    config constant, never a module-level capture."""
    monkeypatch.setattr(CFG, "PADS_BAND_VARIABLES", bool(on))


# ══════════════════════════════════════════════════════════════════════
# §1.1 — the domain arithmetic, on plain numbers
# ══════════════════════════════════════════════════════════════════════

def test_the_domain_is_the_intersection_over_every_ring_vertex():
    """A pad is FLAT, so ONE value must be lawful at EVERY ring vertex:
    the domain ceiling is the MINIMUM ceiling and the floor is the
    MAXIMUM floor — never a median, never a subset of the ring."""
    ring = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]
    bands = {(0.0, 0.0): (90.0, 100.0), (10.0, 0.0): (91.0, 99.0),
             (10.0, 10.0): (88.0, 94.0), (0.0, 10.0): (92.0, 101.0)}
    lo, hi, n = PV.ring_domain(ring, lambda x, y: bands[(x, y)])
    assert (lo, hi, n) == (92.0, 94.0, 4)
    d = PV.ring_domain_detail(ring, lambda x, y: bands[(x, y)])
    assert d["floor_vertex"] == (0.0, 10.0)
    assert d["ceiling_vertex"] == (10.0, 10.0)


def test_an_unserved_ring_is_off_network_not_infeasible():
    """``sampled == 0`` is "this band says nothing here", which a caller
    must be able to tell from "nothing is lawful here"."""
    lo, hi, n = PV.ring_domain([(0.0, 0.0)], lambda x, y: None)
    assert n == 0 and lo == float("-inf") and hi == float("inf")
    assert not PV.domain_empty(lo, hi)


def test_the_materiality_floor_is_not_a_contradiction():
    """A crossing under 0.01 m is PASS-with-residual (convergence
    guards), never a contradiction and never a forced split."""
    assert not PV.domain_empty(100.005, 100.0)
    assert PV.domain_empty(100.5, 100.0)


# ══════════════════════════════════════════════════════════════════════
# §2 twin 1 + twin 5 — a pad between two-level aprons
# ══════════════════════════════════════════════════════════════════════

def _two_level_layout():
    """A small pad whose ring touches a HIGH apron on three vertices and a
    LOW one on the fourth, with NO apron-shared EDGE — so the pre-spec
    pass falls to the whole-ring MEDIAN and the median ignores the one
    vertex that binds.

    Band: three ring vertices reach 100.0, the fourth (beside the low
    apron) only 92.0.  The DEM is high (120.0), so DEM never binds.
    """
    apron = _shape([(-50.0, -50.0), (150.0, -50.0), (150.0, 150.0),
                    (-50.0, 150.0)], ROLE_APRON, "apron1")
    pad = _shape([(0.0, 0.0), (20.0, 0.0), (20.0, 20.0), (0.0, 20.0)],
                 ROLE_BUILDING, "pad1")
    layout = _FakeLayout([apron, pad])
    return layout, apron, pad


def _two_level_band(x, y):
    if abs(x - 20.0) < 1e-6 and abs(y - 20.0) < 1e-6:
        return (80.0, 92.0)          # the binding vertex
    return (80.0, 100.0)


def _over_cap_ring_vertices(pad, band, level):
    """The pad's own over-cap population: a ring vertex whose band cannot
    reach the flat level the pad was seated at."""
    return sum(1 for (x, y) in list(pad.polygon.exterior.coords)[:-1]
               if (b := band(x, y)) is not None and level > b[1] + 0.01)


def test_the_pad_solves_inside_its_domain_and_the_median_control_does_not(
        monkeypatch):
    """§2 twin 1 AND twin 5.  ON: the value lands inside the domain, on
    the bound the MEMBRANE authored — the pad moved to the membrane's
    optimum instead of pinning it (no one-sided seniority).  OFF: the
    ring-median control, which ships 8 m above a vertex it must be flat
    at."""
    layout, apron, pad = _two_level_layout()
    b2i = _register(layout, [apron, pad])

    _arm(monkeypatch, False)
    off = _level_of(_seats(layout, b2i, _two_level_band, lambda x, y: 120.0,
                           {id(pad): 100.0}, monkeypatch),
                    b2i, layout.canonical_points, pad)

    layout2, apron2, pad2 = _two_level_layout()
    b2i2 = _register(layout2, [apron2, pad2])
    _arm(monkeypatch, True)
    on = _level_of(_seats(layout2, b2i2, _two_level_band, lambda x, y: 120.0,
                          {id(pad2): 100.0}, monkeypatch),
                   b2i2, layout2.canonical_points, pad2)

    assert off == pytest.approx(100.0), (
        "the pre-spec control is the whole-ring MEDIAN of the ceilings")
    assert on == pytest.approx(92.0), (
        "the pad's domain is the INTERSECTION over its ring vertices, and "
        "the seat is chosen inside it")
    assert _over_cap_ring_vertices(pad2, _two_level_band, on) == 0
    assert _over_cap_ring_vertices(pad, _two_level_band, off) == 1


def test_the_provenance_names_the_domain_the_value_and_what_binds_it(
        monkeypatch):
    """§1.6 — published into the ``pad_binding_routes`` container, which
    is where the binding ROUTE for the same pad lives: one file read."""
    layout, apron, pad = _two_level_layout()
    b2i = _register(layout, [apron, pad])
    _arm(monkeypatch, True)
    _seats(layout, b2i, _two_level_band, lambda x, y: 120.0,
           {id(pad): 100.0}, monkeypatch)
    cont = getattr(layout, PV.PAD_BINDING_ROUTES_STORE)
    rec = next(r for r in cont["records"] if r["pad"] == "pad1")
    assert rec["pad_variable"] is True
    assert rec["domain"] == pytest.approx([80.0, 92.0])
    assert rec["solved_m"] == pytest.approx(92.0)
    assert rec["binding"]["at_ceiling"] is True
    assert rec["binding"]["at_floor"] is False
    assert rec["binding"]["ring_vertices_sampled"] == 4
    assert "ceiling_ll" in rec["binding"]


def test_the_provenance_publication_merges_and_never_overwrites():
    """EXTEND, NEVER FORK (RULINGS 7e90032).  ``pad_binding_routes`` has
    two producers — the binding-ROUTE capture and this domain
    publication — and both answer "why is this pad here".  An assignment
    would make whichever ran second delete the other's answer."""
    class _L:
        pass
    layout = _L()
    layout._pad_binding_routes = {
        "nodespace": "n=42",
        "records": [{"pad": "pad1", "seat_m": 92.0, "sides": {"ceiling": 1}}]}
    PV.publish_pad_variable_provenance(
        layout, [{"pad": "pad1", "domain": [80.0, 92.0], "solved_m": 92.0},
                 {"pad": "pad2", "domain": [10.0, 20.0], "solved_m": 15.0}],
        nodespace="n=7")
    rows = {r["pad"]: r for r in layout._pad_binding_routes["records"]}
    assert rows["pad1"]["sides"] == {"ceiling": 1}, "route side survived"
    assert rows["pad1"]["domain"] == [80.0, 92.0], "domain joined it"
    assert rows["pad2"]["solved_m"] == 15.0
    assert layout._pad_binding_routes["nodespace"] == "n=42", (
        "the route capture's node-space stamp is the stronger claim")


# ══════════════════════════════════════════════════════════════════════
# §2 twin 4 — an EMPTY domain
# ══════════════════════════════════════════════════════════════════════

def _empty_domain_band(x, y):
    """Two laws contradicting each other across one flat pad: one vertex
    must stay ABOVE 100, another may not exceed 95."""
    if abs(x - 20.0) < 1e-6 and abs(y - 20.0) < 1e-6:
        return (80.0, 95.0)
    if abs(x) < 1e-6 and abs(y) < 1e-6:
        return (100.0, 130.0)
    return (80.0, 130.0)


def test_an_empty_domain_is_a_contradiction_ledger_entry_and_continues(
        monkeypatch):
    """§1.4 report-first: the SAME ledger the band's own inverted
    intervals feed, and the build continues on the pre-spec box."""
    monkeypatch.setattr(CFG, "BAND_LAW_REFUSE", False)
    layout, apron, pad = _two_level_layout()
    b2i = _register(layout, [apron, pad])
    _arm(monkeypatch, True)
    seats = _seats(layout, b2i, _empty_domain_band, lambda x, y: 120.0,
                   {id(pad): 100.0}, monkeypatch)
    rows = list(getattr(layout, CONTRADICTION_STORE).values())
    assert len(rows) == 1
    assert rows[0]["source"] == "pad_domain"
    assert rows[0]["pad"] == "pad1"
    assert rows[0]["deficit_m"] == pytest.approx(5.0)
    assert rows[0]["healed"] == "pre_spec_box"
    assert _level_of(seats, b2i, layout.canonical_points, pad) is not None, (
        "report-first: the pad still ships, on its pre-spec box")


def test_the_refuse_arm_raises_on_the_same_site(monkeypatch):
    """One flag apart, one message, one ledger — the ship-gate arm."""
    monkeypatch.setattr(CFG, "BAND_LAW_REFUSE", True)
    layout, apron, pad = _two_level_layout()
    b2i = _register(layout, [apron, pad])
    _arm(monkeypatch, True)
    with pytest.raises(LawBandRefusal) as exc:
        _seats(layout, b2i, _empty_domain_band, lambda x, y: 120.0,
               {id(pad): 100.0}, monkeypatch)
    assert "pad1" in str(exc.value)
    assert "EMPTY DOMAIN" in str(exc.value)


# ══════════════════════════════════════════════════════════════════════
# §2 twins 2 + 3 — authored-datum groups: ACCOMMODATE, ELSE SPLIT
# ══════════════════════════════════════════════════════════════════════

def _sq(x0, y0, side=10.0):
    return Polygon([(x0, y0), (x0 + side, y0), (x0 + side, y0 + side),
                    (x0, y0 + side)])


def test_a_group_on_gentle_ground_stays_whole_with_its_offsets_exact():
    """§2 twin 2.  A lawful accommodation EXISTS, so it is taken —
    pack-relationship preservation is the preferred outcome."""
    out = PV.solve_pack_groups(
        [{"key": "packA", "members": [0, 1]}],
        domains={0: (90.0, 110.0), 1: (93.0, 113.0)},
        targets={0: 100.0, 1: 103.0},
        offsets={0: 0.0, 1: 3.0},
        weights={0: 100.0, 1: 100.0},
        polygons={0: _sq(0.0, 0.0), 1: _sq(10.0, 0.0)},
        over_cap=lambda vals: [])
    assert out.whole == 1 and out.split == 0
    assert out.rows == []
    assert out.pieces["packA"] == [[0, 1]]
    assert out.values[1] - out.values[0] == pytest.approx(3.0), (
        "the AUTHORED offset survives exactly")
    assert 90.0 <= out.values[0] <= 110.0
    assert 93.0 <= out.values[1] <= 113.0


def test_a_group_with_no_lawful_common_value_splits_and_is_recorded():
    """§2 twin 3.  The intersection is EMPTY over a synthetic hill, so
    grade law outranks the shared datum: the group splits, the ledger
    carries the forcing row, and each member is lawful individually."""
    out = PV.solve_pack_groups(
        [{"key": "packB", "members": [0, 1]}],
        domains={0: (90.0, 92.0), 1: (120.0, 124.0)},
        targets={0: 91.0, 1: 122.0},
        offsets={0: 0.0, 1: 0.0},
        weights={0: 100.0, 1: 100.0},
        polygons={0: _sq(0.0, 0.0), 1: _sq(500.0, 0.0)},
        over_cap=lambda vals: [])
    assert out.split == 1 and out.whole == 0
    row = out.rows[0]
    assert row["group"] == "packB"
    assert row["stage"] == "sub_bodies", "disjoint footprints split by body"
    assert [set(p) for p in row["pieces"]] == [{"0"}, {"1"}]
    assert row["forcing_rows"][0]["why"] == "empty_intersection"
    assert row["worst_m"] == pytest.approx(28.0)
    assert out.values[0] == pytest.approx(91.0)
    assert out.values[1] == pytest.approx(122.0)


def test_a_lawful_intersection_still_splits_when_a_member_goes_over_cap():
    """The ruling's SECOND trigger.  Preservation is the TIEBREAKER among
    LAWFUL placements — a group optimum that leaves a member's law over
    cap is not "the best available", it is a split."""
    seen = {}

    def _over_cap(vals):
        seen.update(vals)
        # Whole-group assignment only: both members land at 100.0, and
        # member 1's neighbour law cannot take it.
        if len(vals) > 1:
            return [{"why": "coupled_pair_over_cap", "excess_m": 4.0}]
        return []

    out = PV.solve_pack_groups(
        [{"key": "packC", "members": [0, 1]}],
        domains={0: (95.0, 105.0), 1: (95.0, 105.0)},
        targets={0: 100.0, 1: 100.0},
        offsets={0: 0.0, 1: 0.0},
        weights={0: 1.0, 1: 1.0},
        polygons={0: _sq(0.0, 0.0), 1: _sq(300.0, 0.0)},
        over_cap=_over_cap)
    assert out.split == 1
    assert out.rows[0]["forcing_rows"][0]["why"] == "coupled_pair_over_cap"
    assert out.rows[0]["worst_m"] == pytest.approx(4.0)


def test_sub_bodies_come_first_and_individual_pads_last():
    """"into sub-bodies by connected proximity first, individual pads
    last" — and the authored offsets survive WITHIN each surviving
    piece."""
    # 0 and 1 TOUCH (one sub-body, authored 2 m apart); 2 is far away and
    # unreachable from either.
    out = PV.solve_pack_groups(
        [{"key": "packD", "members": [0, 1, 2]}],
        domains={0: (90.0, 100.0), 1: (92.0, 102.0), 2: (140.0, 150.0)},
        targets={0: 95.0, 1: 97.0, 2: 145.0},
        offsets={0: 0.0, 1: 2.0, 2: 0.0},
        weights={0: 1.0, 1: 1.0, 2: 1.0},
        polygons={0: _sq(0.0, 0.0), 1: _sq(10.0, 0.0), 2: _sq(900.0, 0.0)},
        over_cap=lambda vals: [])
    row = out.rows[0]
    assert row["stage"] == "sub_bodies"
    assert [sorted(p) for p in row["pieces"]] == [["0", "1"], ["2"]]
    assert out.values[1] - out.values[0] == pytest.approx(2.0), (
        "the authored offset survives INSIDE the surviving piece")


def test_one_chained_body_falls_straight_to_individual_pads():
    """Every member touches every other through the chain, so there are
    no sub-bodies to fall back to and the ruling's LAST resort is the
    only one left."""
    out = PV.solve_pack_groups(
        [{"key": "packE", "members": [0, 1]}],
        domains={0: (90.0, 92.0), 1: (120.0, 124.0)},
        targets={0: 91.0, 1: 122.0},
        offsets={0: 0.0, 1: 0.0},
        weights={0: 1.0, 1: 1.0},
        polygons={0: _sq(0.0, 0.0), 1: _sq(10.0, 0.0)},
        over_cap=lambda vals: [])
    assert out.rows[0]["stage"] == "individual"
    assert [sorted(p) for p in out.rows[0]["pieces"]] == [["0"], ["1"]]


def test_the_ledger_reads_as_all_accommodated_when_nothing_split():
    """An EMPTY ledger is the PREFERRED outcome and must say so — it is
    never a missing result."""
    line = PV.format_pack_group_splits("LEMD", [])
    assert "ACCOMMODATED" in line and "no group was split" in line
    line = PV.format_pack_group_splits(
        "LEMD", [{"group": "packB", "members": ["a", "b"], "stage": "individual",
                  "pieces": [["a"], ["b"]], "worst_m": 28.0,
                  "forcing_rows": [{"why": "empty_intersection"}]}])
    assert "SPLIT" in line and "packB" in line and "28.0" in line


def test_one_domain_dissolves_the_two_instrument_empty_intersection(
        monkeypatch):
    """The §2 seat-vs-band consistency law reconciled TWO instruments — a
    selection interval sampled at the centroid/frontage and the node band
    at the contact nodes — and a DISJOINT pair was reported as an empty
    intersection with today's value shipped anyway (the split-level-seat
    trigger, RULINGS 2026-08-04; its twin is
    ``tests/test_seat_band_and_coupler.py``, now pinned to the OFF arm).

    Under this ruling there is only ONE instrument, so that pairing cannot
    arise: the pad seats at its ring-vertex domain, which is a LAWFUL
    level, instead of shipping an unlawful one loudly."""
    monkeypatch.setattr(CFG, "BAND_LAW_REFUSE", False)
    apron = _shape([(0.0, 0.0), (200.0, 0.0), (200.0, 40.0), (0.0, 40.0)],
                   ROLE_APRON, "apron1")
    pad = _shape([(40.0, 40.0), (100.0, 40.0), (100.0, 100.0),
                  (40.0, 100.0)], ROLE_BUILDING, "big1")
    layout = _FakeLayout([apron, pad])
    b2i = _register(layout, [apron, pad])

    def band(x, y):
        if abs(x - 70.0) < 1e-6 and abs(y - 70.0) < 1e-6:
            return (106.0, 108.0)     # the old SELECTION interval
        return (90.0, 104.0)          # the old NODE band — disjoint below
    _arm(monkeypatch, True)
    seats = _seats(layout, b2i, band, lambda x, y: 120.0,
                   {id(pad): 108.0}, monkeypatch)
    assert _level_of(seats, b2i, layout.canonical_points,
                     pad) == pytest.approx(104.0)
    assert not getattr(layout, CONTRADICTION_STORE, None), (
        "the ring-vertex domain [90, 104] is NOT empty — the emptiness "
        "was an artefact of pairing two instruments, not a law defect")


# ══════════════════════════════════════════════════════════════════════
# §1.5 — OFF is inert
# ══════════════════════════════════════════════════════════════════════

def test_off_publishes_no_ledger_no_provenance_and_no_contradiction(
        monkeypatch):
    """OFF restores the pre-ruling seat pass: no split ledger, no pad
    provenance, no pad-domain contradiction row — the three things whose
    mere PRESENCE would change an emitted sidecar."""
    monkeypatch.setattr(CFG, "BAND_LAW_REFUSE", False)
    layout, apron, pad = _two_level_layout()
    b2i = _register(layout, [apron, pad])
    _arm(monkeypatch, False)
    _seats(layout, b2i, _empty_domain_band, lambda x, y: 120.0,
           {id(pad): 100.0}, monkeypatch)
    assert not getattr(layout, PV.PACK_GROUP_SPLIT_STORE, None)
    assert not getattr(layout, PV.PAD_BINDING_ROUTES_STORE, None)
    assert not getattr(layout, CONTRADICTION_STORE, None)
