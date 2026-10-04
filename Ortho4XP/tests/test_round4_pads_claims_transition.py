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


from auto_patch import driver, object_anchor, post_mesh


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


def test_a_claim_with_no_hull_is_tested_by_its_centre_and_radius():
    """An entry whose hull is unusable (a one-runway strip: two thresholds
    make no polygon) still CLAIMS — by ``centre_lonlat`` + ``radius_m``.
    The flat-site prep reads the mode (``flat_site_mode``: only
    ``CLAIM_CONTAINMENT`` licenses moving terrain), and this arm is the
    one the production tile build takes that no test did (RULINGS
    2026-10-04j "coverage owed")."""
    dsf = "/packs/aeroscape/+25+051.dsf"
    entries = _two_airport_entries(dsf)
    disc = {"centre_lonlat": [51.5700, 25.2660], "radius_m": 800.0,
            "hull_lonlat": [[51.5650, 25.2610], [51.5750, 25.2710]]}
    entries[0]["claim"] = disc                      # OTBD: no polygon
    assign = post_mesh.worklist_claim_assigner(entries)
    # inside the disc: a containment answer, and it beats OTHH's polygon
    # on a genuine overlap (the disc carries area 0 — the tighter claim)
    assert assign(dsf, 25.2660, 51.5700, with_mode=True) == (
        "OTBD", post_mesh.CLAIM_CONTAINMENT)
    assert assign(dsf, 25.2660 + 500.0 / 111320.0, 51.5700) == "OTBD"
    # outside the disc and outside OTHH's hull: the nearest-centre fallback,
    # reported as what it is
    assert assign(dsf, 25.2660 + 1500.0 / 111320.0, 51.5700,
                  with_mode=True) == ("OTBD", post_mesh.CLAIM_NEAREST)
    # OTHH's own hull still answers for OTHH
    assert assign(dsf, 25.2660, 51.6180, with_mode=True) == (
        "OTHH", post_mesh.CLAIM_CONTAINMENT)
    # the radius is measured in METRES east-west too (cos latitude)
    east_m = 700.0
    east_deg = east_m / (111320.0 * math.cos(math.radians(25.2660)))
    assert assign(dsf, 25.2660, 51.5700 + east_deg, with_mode=True) == (
        "OTBD", post_mesh.CLAIM_CONTAINMENT)
    assert assign(dsf, 25.2660, 51.5700 + east_deg * 1.3,
                  with_mode=True)[1] == post_mesh.CLAIM_NEAREST


def test_a_sole_entry_and_an_unknown_dsf_report_their_mode():
    entries = [{"icao": "OTBD", "dsf_path": "/p/a.dsf", "claim": {}}]
    assign = post_mesh.worklist_claim_assigner(entries)
    assert assign("/p/a.dsf", 40.0, -70.0, with_mode=True) == (
        "OTBD", post_mesh.CLAIM_SOLE_ENTRY)
    assert assign("/p/other.dsf", 40.0, -70.0, with_mode=True) == (None, None)
    assert assign("/p/other.dsf", 40.0, -70.0) is None
    assert post_mesh.worklist_claim_assigner(
        [{"icao": "X"}])("/p/a.dsf", 0.0, 0.0) is None    # no dsf_path


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


