"""Round-4 spec R1 / R2 / R5 — the changed behaviour, and only that.

R1  the pad plan-box fallback is retired (sidecar v5);
R2  objects claim their CONTAINING airport;
R5  transition surfaces beside below-grade geometry take the transition
    law, never a raw DEM sample.

Written with the change, run once (PRE-SHIP MODE, docs/RULINGS.md).
Everything here is synthetic and tmp_path-scoped: no X-Plane install,
no shared data repo, no network.
"""
from __future__ import annotations

import math

import pytest
from shapely.geometry import Polygon

from auto_patch import driver, groundside, object_anchor, post_mesh


# ──────────────────────────────────────────────────────────────────
# R1 — a part with no contact-band geometry raises no pad request
# ──────────────────────────────────────────────────────────────────

_ANCHOR_LATITUDE = 25.26
_ANCHOR_LONGITUDE = 51.61


def _frame(vertices, resource="pack/deck.obj"):
    return object_anchor._PoolFrame(
        origin_latitude=_ANCHOR_LATITUDE,
        origin_longitude=_ANCHOR_LONGITUDE,
        shared_vertices=list(vertices),
        base_offset_by_resource={resource: 0},
        resource_of_shared_vertex=[resource] * len(vertices),
        included_resources=[resource],
        excluded_resources=[],
    )


def _measurement(triangles, base_y, plan_box, resource="pack/deck.obj"):
    return object_anchor._PartMeasurement(
        key=0,
        triangles=list(triangles),
        base_y=base_y,
        base_resource=resource,
        is_ground=True,
        plan_box=plan_box,
    )


def test_a_part_with_no_contact_band_triangle_raises_nothing():
    """THE R1 LAW.  The measured offender: a pier-supported viaduct deck
    welded into one mega-part, ZERO triangles in the 0.5 m band, whose
    plan box was 564.8 x 534.3 m.  It must not fall back to that box."""
    # One triangle 9 m up — an elevated deck over a part based at 0.
    vertices = [(0.0, 0.0, 0.0), (300.0, 9.0, 0.0), (300.0, 9.0, 300.0)]
    result = object_anchor._contact_band_triangles_lonlat(
        _frame(vertices), _measurement([(0, 1, 2)], 0.0,
                                       (0.0, 564.8, 0.0, 534.3)), 0.5)
    assert result is None


def test_the_degenerate_small_fallback_survives():
    """A part standing IN the contact band whose triangulation simply has
    no triangle wholly inside it keeps the plan box — while it is small
    enough to be trustworthy."""
    vertices = [(0.0, 0.0, 0.0), (10.0, 3.0, 0.0), (10.0, 3.0, 10.0)]
    result = object_anchor._contact_band_triangles_lonlat(
        _frame(vertices),
        _measurement([(0, 1, 2)], 0.0, (0.0, 20.0, 0.0, 20.0)),
        0.5,
    )
    assert result is not None and len(result) == 1
    assert len(result[0]) == 4              # the four plan-box corners


def test_a_big_fallback_is_dropped_and_named(monkeypatch):
    """Over the cap the request is dropped, with a verbosity-1 line
    naming the resource — never a silent loss."""
    import O4_UI_Utils as UI

    lines: list[str] = []
    monkeypatch.setattr(
        UI, "vprint",
        lambda level, *parts: lines.append(" ".join(str(p) for p in parts)))
    vertices = [(0.0, 0.0, 0.0), (10.0, 3.0, 0.0), (10.0, 3.0, 10.0)]
    result = object_anchor._contact_band_triangles_lonlat(
        _frame(vertices),
        _measurement([(0, 1, 2)], 0.0, (0.0, 100.0, 0.0, 100.0)),
        0.5,
    )
    assert result is None
    assert any("pack/deck.obj" in line for line in lines)


def test_the_fallback_cap_is_the_config_constant(monkeypatch):
    """The window is a config constant, not a call-site number."""
    from auto_patch import config

    assert config.DSF_OBJECT_PAD_PLAN_BOX_FALLBACK_MAX_M2 == 2000.0
    vertices = [(0.0, 0.0, 0.0), (10.0, 3.0, 0.0), (10.0, 3.0, 10.0)]
    monkeypatch.setattr(
        config, "DSF_OBJECT_PAD_PLAN_BOX_FALLBACK_MAX_M2", 100.0)
    assert object_anchor._contact_band_triangles_lonlat(
        _frame(vertices),
        _measurement([(0, 1, 2)], 0.0, (0.0, 20.0, 0.0, 20.0)),
        0.5,
    ) is None


def test_the_sidecar_version_gate_discards_the_old_requests():
    """v5: the 30-hectare requests already on disk are refused whole."""
    from auto_patch import object_pads

    assert post_mesh.OBJECT_FOOT_PAD_SIDECAR_VERSION == 5
    assert not object_pads.sidecar_is_current({"version": 4})
    assert object_pads.sidecar_is_current({"version": 5})


# ──────────────────────────────────────────────────────────────────
# R2 — objects claim their CONTAINING airport
# ──────────────────────────────────────────────────────────────────

_OTBD = {
    "05": {"lat": 25.2610, "lon": 51.5650},
    "23": {"lat": 25.2710, "lon": 51.5750},
    "05b": {"lat": 25.2660, "lon": 51.5700},
}
_OTHH = {
    "16": {"lat": 25.2530, "lon": 51.6100},
    "34": {"lat": 25.2790, "lon": 51.6250},
    "16b": {"lat": 25.2660, "lon": 51.6180},
}


def _two_airport_entries(dsf_path="/packs/aeroscape/+25+051.dsf"):
    return [
        {"icao": "OTBD", "dsf_path": dsf_path,
         "claim": driver._airport_claim_lonlat(_OTBD)},
        {"icao": "OTHH", "dsf_path": dsf_path,
         "claim": driver._airport_claim_lonlat(_OTHH)},
    ]


def test_containment_partitions_a_shared_cell():
    """The measured defect: one Global/Aeroscape DSF cell carries both
    airports' objects and OTBD owned all of it because it sorted first.
    Containment answers per object instead."""
    assign = post_mesh.worklist_claim_assigner(_two_airport_entries())
    dsf = "/packs/aeroscape/+25+051.dsf"
    assert assign(dsf, 25.2660, 51.5700) == "OTBD"
    assert assign(dsf, 25.2660, 51.6180) == "OTHH"


def test_an_unclaimed_object_goes_to_the_nearest_airport():
    """No hull covers it, so it is not lost — it joins the nearest
    airport's entry."""
    assign = post_mesh.worklist_claim_assigner(_two_airport_entries())
    dsf = "/packs/aeroscape/+25+051.dsf"
    assert assign(dsf, 25.2660, 51.6800) == "OTHH"
    assert assign(dsf, 25.2660, 51.5000) == "OTBD"


def test_a_single_entry_cell_is_unchanged():
    """Version-2 behaviour verbatim where only one airport wants a
    pack: every placement is that airport's."""
    entries = [{"icao": "OTBD", "dsf_path": "/p/a.dsf",
                "claim": driver._airport_claim_lonlat(_OTBD)}]
    assign = post_mesh.worklist_claim_assigner(entries)
    assert assign("/p/a.dsf", 40.0, -70.0) == "OTBD"


def test_the_worklist_is_per_airport_per_pack(monkeypatch, tmp_path):
    """The dedup key is (airport, DSF), so a shared cell appears once
    for each airport instead of once for the tile."""
    dsf = tmp_path / "+25+051.dsf"
    dsf.write_text("stub")
    pack_root = str(tmp_path)

    monkeypatch.setattr(
        driver, "_enabled_airport_pack_tile_dsfs",
        lambda *a, **k: [(str(dsf), pack_root)], raising=False)
    from auto_patch import dsf_reader, osm_load

    monkeypatch.setattr(
        dsf_reader, "read_dsf_object_placement_positions",
        lambda *a, **k: [(51.6180, 25.2660), (51.5700, 25.2660)])
    monkeypatch.setattr(
        osm_load, "_pick_best_apt_dat_against_osm", lambda *a, **k: None)

    seen: set = set()
    cache: dict = {}
    entries = []
    for icao, runways in (("OTBD", _OTBD), ("OTHH", _OTHH)):
        entries.extend(driver._object_anchor_worklist_entries(
            icao, str(tmp_path), runways, 25, 51, seen, cache,
            claim=driver._airport_claim_lonlat(runways)))

    assert [entry["icao"] for entry in entries] == ["OTBD", "OTHH"]
    assert all(entry["claim"]["hull_lonlat"] for entry in entries)
    assert post_mesh.OBJECT_ANCHOR_WORKLIST_VERSION == 3


def test_the_run_fingerprint_is_keyed_by_the_claiming_airport():
    """Without this the second airport's run matches the FIRST one's
    record, short-circuits, and inherits its pad requests wholesale."""
    from auto_patch import object_rebake

    otbd = object_rebake._run_key("/t/+25+051.mes", "/p/a.dsf", "OTBD")
    othh = object_rebake._run_key("/t/+25+051.mes", "/p/a.dsf", "OTHH")
    assert otbd != othh
    # The historic two-part key still exists for the CLI / tests.
    assert object_rebake._run_key("/t/+25+051.mes", "/p/a.dsf") not in (
        otbd, othh)


# ──────────────────────────────────────────────────────────────────
# R5 — the transition law beside below-grade geometry
# ──────────────────────────────────────────────────────────────────

class _Shape:
    def __init__(self, polygon, role, ref, node_altitudes=None,
                 altitude=None):
        self.polygon = polygon
        self.role = role
        self.ref = ref
        self.node_altitudes = node_altitudes
        self.altitude = altitude


class _Layout:
    def __init__(self, shapes):
        self.shapes = list(shapes)


def _diving_ramp_chain(length_m=600.0, top=4.0, portal=-4.02, pieces=30):
    """A tunnel ramp emitted the way bridges.py emits one: a CHAIN of
    quads descending from grade to the portal.  The portal (deepest
    station, where the below-grade surface meets grade under the
    pavement) is at ``x = length_m``."""
    ramps = []
    for i in range(pieces):
        x0, x1 = length_m * i / pieces, length_m * (i + 1) / pieces
        z0 = top + (portal - top) * (i / pieces)
        z1 = top + (portal - top) * ((i + 1) / pieces)
        ramps.append(_Shape(
            Polygon([(x0, 0), (x1, 0), (x1, 10), (x0, 10)]),
            "tunnel_ramp", "tunnel_ramp",
            node_altitudes=[z0, z1, z1, z0, z0],
        ))
    return ramps


def _densified_band(y_inner=10.6, y_outer=11.6, length_m=600.0, step=10.0):
    """The perimeter wall band's ring, densified the way a shapely buffer
    densifies it — the along-the-ring run is only meaningful on a ring
    that has vertices."""
    xs = [i * step for i in range(int(length_m / step) + 1)]
    return Polygon([(x, y_outer) for x in xs]
                   + [(x, y_inner) for x in reversed(xs)])


def _inner_crest(shape, x_target, y_inner=10.6):
    ring = list(shape.polygon.exterior.coords)[:-1]
    alts = shape.node_altitudes[:len(ring)]
    for (x, y), altitude in zip(ring, alts):
        if abs(x - x_target) < 0.01 and abs(y - y_inner) < 0.01:
            return altitude
    raise AssertionError(f"no inner-band vertex at x={x_target}")


def test_the_wall_crest_stands_at_grade_and_converges_at_the_portal():
    """THE R5 LAW as ruled (lead 2026-08-10).  The crest is the
    SURROUNDING SURFACE AUTHORITY along the ramp's whole length — the
    wall FACE, not the crest, spans the drop — and it descends only
    within the cap-limited run of the portal, converging on the ramp
    there.  The witness is the pre-regression Aug-8 state: a crest at
    surrounding grade (2.90–5.00 m) against a ramp already diving."""
    ramps = _diving_ramp_chain()
    band = _Shape(_densified_band(), "retaining_wall", "tunnel_wall",
                  altitude=4.0)
    layout = _Layout(ramps + [band])
    assert groundside.apply_below_grade_transition(layout) == 1

    # Mid-ramp the ramp is already at grade-8.02/2; the crest is NOT.
    assert _inner_crest(band, 300.0) == pytest.approx(4.0, abs=1e-6)
    assert _inner_crest(band, 100.0) == pytest.approx(4.0, abs=1e-6)
    # At the portal the crest converges on the ramp.
    assert _inner_crest(band, 600.0) == pytest.approx(-4.02, abs=0.1)
    # And the descent is confined to the CAP-LIMITED RUN of the portal:
    # 8.02 m of rise at GROUNDSIDE_MAX_GRADE, so every vertex further
    # back along the ring than that still stands at surrounding grade.
    cap_run = 8.02 / groundside.GROUNDSIDE_MAX_GRADE
    outside = 600.0 - 10.0 * math.ceil((cap_run + 10.0) / 10.0)
    assert outside > 0.0
    assert _inner_crest(band, outside) == pytest.approx(4.0, abs=1e-6)
    # ... while a vertex INSIDE the run has left it.
    assert _inner_crest(band, 600.0 - 10.0) < 4.0 - 0.1


def test_the_crest_does_not_hug_the_ramp():
    """The mirror-image collapse this law forbids: measuring the run
    across the horizontal GAP would put the crest ~0.05 m above the ramp
    the whole way down (a 0.6-1.6 m gap at the 4 % cap), which is terrain
    hugging the ramp instead of standing beside it."""
    ramps = _diving_ramp_chain()
    band = _Shape(_densified_band(), "retaining_wall", "tunnel_wall",
                  altitude=4.0)
    groundside.apply_below_grade_transition(_Layout(ramps + [band]))
    ramp_at_mid = 4.0 - 8.02 / 2.0
    assert _inner_crest(band, 300.0) - ramp_at_mid > 3.0


def _flat_site_layout():
    """THE FLAT CASE IS THE FIXTURE (spec R5's own test note): a ramp
    chain diving to a portal, and a groundside plate beside it whose DEM
    sample is the constant Z0 = 4.00 m flat mode produces."""
    ramps = _diving_ramp_chain(length_m=300.0, top=4.0, portal=-4.0,
                               pieces=15)
    xs = [i * 10.0 for i in range(31)]
    plate = _Shape(
        Polygon([(x, 12.0) for x in xs] + [(x, 220.0) for x in reversed(xs)]),
        "groundside_pavement", "groundside", altitude=4.0,
    )
    return _Layout(ramps + [plate]), ramps, plate


def test_a_flat_plate_beside_a_ramp_takes_the_transition_law():
    """S7's defect: the plate lost its per-node profile, went flat at
    3.96 and met the ramp with a 5.62 m step at 2.6 m spacing."""
    layout, _ramps, plate = _flat_site_layout()
    assert groundside.apply_below_grade_transition(layout) == 1
    alts = plate.node_altitudes
    assert alts is not None and len(set(round(a, 2) for a in alts)) > 1
    # It converges on the ramp at the portal ...
    assert min(alts) < 0.0
    # ... and the surrounding surface still stands where it should.
    assert max(alts) == pytest.approx(4.0, abs=1e-6)


def test_the_transition_never_exceeds_the_lawful_cap():
    """No edge of the re-profiled ring may break GROUNDSIDE_MAX_GRADE —
    the 5.62 m over 2.6 m step is exactly what this forbids."""
    layout, _ramps, plate = _flat_site_layout()
    groundside.apply_below_grade_transition(layout)
    ring = list(plate.polygon.exterior.coords)
    if ring[0] == ring[-1]:
        ring = ring[:-1]
    alts = plate.node_altitudes[:len(ring)]
    for i in range(len(ring)):
        j = (i + 1) % len(ring)
        run = math.hypot(ring[j][0] - ring[i][0], ring[j][1] - ring[i][1])
        # 5e-3 is the relaxation's own convergence floor: the shared
        # ``_grade_limit_ring`` primitive stops at a 1e-3 worst-excess
        # pass, so a converged ring keeps a few mm of slack per edge.
        assert abs(alts[j] - alts[i]) <= (
            groundside.GROUNDSIDE_MAX_GRADE * run + 5e-3)


def test_the_law_holds_on_a_real_dem_site_too():
    """The DEM sample was ALWAYS the wrong witness beside a law-cut ramp;
    flat mode only exposed it.  A varying (real-DEM) surface beside the
    same ramp is governed identically."""
    layout, _ramps, plate = _flat_site_layout()
    ring_length = len(list(plate.polygon.exterior.coords)) - 1
    plate.altitude = None
    plate.node_altitudes = [
        4.0 + 0.4 * math.sin(i) for i in range(ring_length)
    ]
    plate.node_altitudes.append(plate.node_altitudes[0])
    assert groundside.apply_below_grade_transition(layout) == 1
    assert min(plate.node_altitudes) < 0.0


def test_a_plate_out_of_reach_is_untouched():
    """Beyond |dz| / cap the surrounding surface stands: an airport with
    no below-grade geometry near a plate sees no change at all."""
    ramp = _Shape(
        Polygon([(0, 0), (100, 0), (100, 10), (0, 10)]),
        "tunnel_ramp", "tunnel_ramp",
        node_altitudes=[0.0, -4.0, -4.0, 0.0, 0.0],
    )
    far = _Shape(
        Polygon([(0, 5000), (100, 5000), (100, 5100), (0, 5100)]),
        "groundside_pavement", "groundside", altitude=4.0,
    )
    layout = _Layout([ramp, far])
    assert groundside.apply_below_grade_transition(layout) == 0
    assert far.node_altitudes is None


def test_a_layout_with_no_below_grade_geometry_is_a_no_op():
    plate = _Shape(
        Polygon([(0, 0), (100, 0), (100, 100), (0, 100)]),
        "groundside_pavement", "groundside", altitude=4.0,
    )
    layout = _Layout([plate])
    assert groundside.apply_below_grade_transition(layout) == 0
    assert plate.altitude == 4.0


def test_one_anchor_per_below_grade_body():
    """A ramp is emitted as a CHAIN of quads: anchoring per quad would
    pin the transition surface to the ramp along its whole length.  Two
    SEPARATE tunnels beside one plate must still get one portal each."""
    from auto_patch.groundside import _BelowGradeIndex, below_grade_sources

    left = _diving_ramp_chain(length_m=200.0, pieces=10)
    right = []
    for shape in _diving_ramp_chain(length_m=200.0, pieces=10):
        ring = [(x + 1000.0, y) for x, y in shape.polygon.exterior.coords]
        right.append(_Shape(Polygon(ring), "tunnel_ramp", "tunnel_ramp",
                            node_altitudes=list(shape.node_altitudes)))
    index = _BelowGradeIndex(
        below_grade_sources(_Layout(left + right)))
    assert len(set(index.component_of)) == 2
