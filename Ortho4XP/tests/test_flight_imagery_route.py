"""The photo provider of a tile on a planned flight (#2048, RULINGS
2026-11-13n): the departure tile's provider up to the route's midpoint,
the destination tile's after it, no third (region-auto) provider in
between; the #2018 one-tile blend only at the midpoint seam.

Offline: the vendored ``Providers/`` and ``Extents/`` trees; casts are
synthetic."""
import os
import sys
from types import SimpleNamespace

import pytest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
for _path in (os.path.join(REPO_ROOT, "src"), os.path.join(REPO_ROOT, "Providers")):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import O4_Imagery_Provider_Blend as BLEND  # noqa: E402
import O4_World_Imagery_Record as IREC  # noqa: E402
from o4_engine import flight_imagery_route as ROUTE  # noqa: E402
from o4_engine import world_job_run as RUN  # noqa: E402

#: A route east along 48.5 N: departure tile (48, 2), destination (48, 13);
#: its midpoint at 8.0 E, on the edge between tiles (48, 7) and (48, 8).
EAST = [(48.5, 2.5), (48.5, 13.5)]
CORRIDOR = [(48, lon) for lon in range(2, 14)]


@pytest.fixture(scope="module")
def auto():
    old_cwd = os.getcwd()
    os.chdir(REPO_ROOT)
    try:
        import O4_Imagery_Auto as AUTO
        import O4_Imagery_Utils as IMG
        if not (IMG.providers_dict and IMG.combined_providers_dict):
            IMG.initialize_extents_dict()
            IMG.initialize_color_filters_dict()
            IMG.initialize_providers_dict()
            IMG.initialize_combined_providers_dict()
        AUTO.forget()
        yield AUTO
    finally:
        os.chdir(old_cwd)


@pytest.fixture(autouse=True)
def no_route():
    ROUTE.set_active(None)
    yield
    ROUTE.set_active(None)


def test_tiles_take_the_side_their_centre_is_nearest_along_the_route():
    split = ROUTE.RouteSplit("A", "B", RUN_densify(EAST))
    sides = [split.provider(t) for t in CORRIDOR]
    assert sides[0] == "A" and sides[-1] == "B"
    # one switch, at the midpoint (8.0 E): tiles centred west of it are A
    assert sides == ["A"] * 6 + ["B"] * 6
    # off the corridor a tile goes by its nearest route point too
    assert split.provider((50, 3)) == "A" and split.provider((46, 11)) == "B"
    # plain data: the drape's worker process gets the same answer
    again = ROUTE.RouteSplit.from_dict(split.to_dict())
    assert [again.provider(t) for t in CORRIDOR] == sides


def test_the_midpoint_is_measured_along_the_waypoints():
    """A dog-leg: north 4 deg, then east 8 deg.  The midpoint lies on the
    second leg, not at the half of the straight line's span."""
    points = [(44.5, 2.5), (48.5, 2.5), (48.5, 10.5)]
    split = ROUTE.RouteSplit("A", "B", RUN_densify(points))
    assert split.provider((47, 2)) == "A"           # all of the first leg
    assert split.provider((48, 2)) == "A"
    assert split.provider((48, 5)) == "B"           # half the straight span


def RUN_densify(points):
    import O4_Flight_Plan as FP
    return FP.densify(points)


def test_a_route_that_goes_nowhere_has_no_split():
    assert ROUTE.split_for([(48.5, 2.5)], lambda t: "A") is None
    assert ROUTE.split_for([(48.5, 2.5), (48.5, 2.5)], lambda t: "A") is None
    split = ROUTE.split_for(EAST, lambda t: {(48, 2): "A", (48, 13): "B"}[t])
    assert (split.departure, split.destination) == ("A", "B")


def test_an_endpoints_provider_is_its_built_tiles(tmp_path, monkeypatch):
    """The World pack record, else the DDS names of the pack drawing an
    adopted/external tile, else None (region-auto)."""
    import O4_World_Pack as WP
    scenery = tmp_path / "Custom Scenery"
    pack = scenery / WP.PACK_NAME
    held = {(48, 2)}
    monkeypatch.setattr(WP, "holds_tile", lambda s, lat, lon: (lat, lon) in held)
    IREC.write_staged(str(tmp_path / "staged"), {"provider": "GO2", "zl": 17})
    IREC.carry(str(tmp_path / "staged"), str(pack), 48, 2)
    external = tmp_path / "zOrtho4XP_+48+012"
    (external / "textures").mkdir(parents=True)
    (external / "textures" / "88000_136000_FRorth16.dds").write_bytes(b"")
    drawn = {(48, 12): str(external)}
    assert ROUTE.endpoint_provider(str(scenery), (48, 2), drawn.get) == "GO2"
    assert ROUTE.endpoint_provider(str(scenery), (48, 12), drawn.get) == "FRorth"
    assert ROUTE.endpoint_provider(str(scenery), (48, 7), drawn.get) is None


def test_photo_source_follows_the_route_and_the_picker_overrides(monkeypatch, auto):
    """France (FRorth) to the Netherlands (NL) across Belgium: region-auto
    would draw the border tiles with a third provider (Bing); on the
    flight they are the departure's or the destination's."""
    values = {"default_zl": 16}
    monkeypatch.setattr(RUN, "_settings", lambda: dict(values))
    points = [(48.5, 2.5), (52.5, 5.5)]
    middle = (50, 4)
    assert RUN.photo_source(middle)[0] == "BI"        # the third provider
    ROUTE.set_active(ROUTE.split_for(points, lambda t: auto.provider_for(*t)))
    assert RUN.photo_source((48, 2)) == ("FRorth", 16)
    assert RUN.photo_source((52, 5)) == ("NL", 16)
    route = [RUN.photo_source(t)[0] for t in [(48, 2), (49, 3), middle, (51, 4), (52, 5)]]
    assert set(route) == {"FRorth", "NL"} and route == sorted(route, key=["FRorth", "NL"].index)
    values.update(fly_photo_source="GO2", default_zl=17)
    assert RUN.photo_source(middle) == ("GO2", 17)    # the Fly pane's choice
    values.pop("fly_photo_source")
    ROUTE.set_active(None)                            # no flight: region-auto
    assert RUN.photo_source(middle)[0] == "BI"


def test_the_blend_sits_only_at_the_midpoint_seam(monkeypatch):
    """Every corridor drape planned under the split: only the two tiles
    beside the midpoint seam blend, each on that seam's side only."""
    from o4_engine import world_blend
    values = {"default_zl": 16}
    monkeypatch.setattr(RUN, "_settings", lambda: dict(values))
    ROUTE.set_active(ROUTE.RouteSplit("PA", "PB", RUN_densify(EAST)))
    facts = world_blend.facts_reader("", RUN.photo_source)

    def cast(edge, a, b):
        return [(0.5, (10.0, 0.0, -10.0))]
    blended = {}
    for tile in CORRIDOR:
        blend = BLEND.plan(*tile, RUN.photo_source(tile)[0], facts, cast)
        if blend.terms:
            blended[tile] = sorted(blend.terms)
    assert blended == {(48, 7): ["E"], (48, 8): ["W"]}


def test_the_drapes_worker_reads_the_flights_route(monkeypatch):
    """``drape_tile`` hands the active split to the worker process, whose
    blend reads the neighbours with ``photo_source`` under it."""
    import O4_World_Drape_Fetch as FETCH
    from o4_engine import world_drape_process as DRAPE_PROCESS
    split = ROUTE.RouteSplit("PA", "PB", RUN_densify(EAST))
    ROUTE.set_active(split)
    assert RUN._route_dict() == split.to_dict()
    ROUTE.set_active(None)
    assert RUN._route_dict() is None
    seen = []
    monkeypatch.setattr(FETCH, "fetch", lambda *a, **k: seen.append(
        ROUTE.active()) or {})
    DRAPE_PROCESS.fetch_drape("", 48, 7, "", 16, "PB", 0, "", 0.0,
                              route=split.to_dict())
    assert seen[0].provider((48, 3)) == "PA"


def test_the_flight_makes_its_split_and_remakes_it_on_a_new_plan(monkeypatch):
    from o4_engine import flight_job_run as FLIGHT
    import O4_Imagery_Auto as AUTO
    monkeypatch.setattr(FLIGHT, "drawn_build_dir", lambda s, t: None)
    monkeypatch.setattr(FLIGHT.WORLD, "write_log", lambda record: None)
    monkeypatch.setattr(AUTO, "provider_for",
                        lambda lat, lon: {(48, 2): "PA", (48, 13): "PB"}.get((lat, lon), "PC"))
    plan = SimpleNamespace(points=lambda: [(48.5, 2.5)])   # departure only
    manager = SimpleNamespace(plan=plan)
    key = FLIGHT._route_imagery(manager, "")
    assert ROUTE.active() is None
    assert FLIGHT._route_imagery(manager, "", key) == key
    manager.plan = SimpleNamespace(points=lambda: EAST)     # a destination
    key = FLIGHT._route_imagery(manager, "", key)
    split = ROUTE.active()
    assert (split.departure, split.destination) == ("PA", "PB")
    assert FLIGHT._route_imagery(manager, "", key) == key
    assert ROUTE.active() is split                          # not remade
