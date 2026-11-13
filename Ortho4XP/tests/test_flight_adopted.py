"""Twin of a flight's departure or destination on an adopted tile, or
another tool's (#2025, ``o4_engine.flight_adopted``; owner
2026-11-12T19:42Z: "ask the user if they want to use the old mesh or
upgrade the tile before flying it").

Such an endpoint waits in state ``choice`` with a ``FlightStatus.choices``
row while the rest of the flight prepares; ``keep`` makes it ready with no
build, ``upgrade`` queues a ``full`` build that replaces the mesh in the
pack (``fresh``), and the answer is remembered for the tile.  ``patched``
reads yes / no / unknown from the source's Ortho4XP install, or
for the endpoint's airport from the build's own data in the tile folder.  Hermetic:
tmp_path, no network, no X-Plane, no build.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

import O4_Flight_Plan as FP
import O4_Flight_Schedule as SCHEDULE
import O4_Tile_Info as TINFO
import O4_World_Pack as WP
import pytest
from o4_engine import flight_adopted as ADOPTED
from o4_engine import flight_commands as FC
from o4_engine import flight_record as RECORD
from o4_engine import ortho4xp_patched as PATCHED
from o4_engine.flight_manager import CHOICE_DETAIL, CHOICE_STATE, FlightManager

CYYR = (53.30427, -60.447077)
DEST = (53.15, -63.9)
DEP_TILE, DEST_TILE = (53, -61), (53, -64)
WHEN = datetime(2026, 11, 12, tzinfo=timezone.utc)
FACTS = {"world_installed": True, "budget_fits": True, "network_ok": True,
         "all_on_disk": True, "prefetch_done": True}
INFO = {"origin": TINFO.ORIGIN_ADOPTED, "built_by": "Ortho4XP",
        "patched": "yes", "upgrade_ok": True}


def _estimate(tile, kind, role):
    return SCHEDULE.job_estimate(kind, {"full": 900.0}.get(kind), known=True)


class _Builder:
    def __init__(self):
        self.started = []

    def start(self, tile, kind, due, klass):
        self.started.append((tuple(tile), kind, klass))
        return True

    @staticmethod
    def poll(now):
        return []


class _Publisher:
    def __init__(self):
        self.calls = []

    def settle(self, tile, kind, held, **kw):
        self.calls.append((tuple(tile), kw))
        return "swapped"


def _manager(book=None, adopted=(DEP_TILE,), info=INFO):
    plan = FP.FlightPlan([FP.Waypoint("CYYR", *CYYR),
                          FP.Waypoint("DEST", *DEST)], source="test")
    record = RECORD.from_plan(plan, "none", WHEN)
    builder, publisher = _Builder(), _Publisher()

    def state_of(tile):
        return "full" if tuple(tile) in (DEP_TILE, DEST_TILE) else "placeholder"
    manager = FlightManager(
        record, plan, builder=builder, publisher=publisher,
        facts=lambda: dict(FACTS), state_of=state_of, estimate=_estimate,
        parked_slots=4,
        adopted=lambda t: dict(info) if tuple(t) in adopted else None,
        choices=book)
    return manager, builder, publisher


def _job(manager, tile):
    return next(j for j in manager.jobs if j.tile == tile)


def test_an_adopted_departure_asks_and_the_rest_prepares():
    manager, builder, _pub = _manager()
    assert _job(manager, DEP_TILE).state == CHOICE_STATE
    manager.tick(0.0, None)
    status = manager.status(0.0)
    assert status["choices"] == ({
        "tile": [53, -61], "role": "departure", "icao": "CYYR",
        "origin": "adopted", "built_by": "Ortho4XP", "patched": "yes",
        "upgrade_estimate_s": _estimate(DEP_TILE, "full", "departure")[1],
        "choice": ""},)
    rows = {i[0]: i for i in status["items"]}
    assert rows["departure"][1] == "waiting" and rows["departure"][3] == CHOICE_DETAIL
    assert status["countdown_s"] is None and not status["ready"]
    assert DEP_TILE not in {s[0] for s in builder.started}
    assert builder.started                  # the first window goes on
    # the destination is ours (not adopted): no choice, nothing to build
    assert _job(manager, DEST_TILE).state == "swapped"


def test_keep_makes_it_ready_with_no_build_and_is_remembered(tmp_path):
    book = ADOPTED.ChoiceBook(str(tmp_path / ADOPTED.CHOICES_FILE))
    manager, builder, _pub = _manager(book)
    manager.choose(DEP_TILE, "keep")
    assert _job(manager, DEP_TILE).state == "swapped"
    manager.tick(0.0, None)
    assert DEP_TILE not in {s[0] for s in builder.started}
    assert manager.status(0.0)["choices"][0]["choice"] == "keep"
    assert {i[0]: i[1] for i in manager.status(0.0)["items"]}["departure"] == "done"
    saved = json.loads((tmp_path / ADOPTED.CHOICES_FILE).read_text("utf-8"))
    assert saved["+53-061"]["choice"] == "keep"
    # a later flight: applied without asking
    again, _b, _p = _manager(ADOPTED.ChoiceBook(book.path))
    assert _job(again, DEP_TILE).state == "swapped"
    assert again.status(0.0)["choices"][0]["choice"] == "keep"


def test_upgrade_builds_full_and_replaces_the_mesh():
    manager, builder, publisher = _manager()
    manager.choose(DEP_TILE, "upgrade")
    job = _job(manager, DEP_TILE)
    assert (job.kind, job.state, job.klass) == ("full", "queued", SCHEDULE.P0)
    manager.tick(0.0, None)
    assert (DEP_TILE, "full", "P0") in builder.started
    manager._finished.add(DEP_TILE)         # the build finished
    manager.tick(1.0, None)
    assert (DEP_TILE, {"fresh": True}) in publisher.calls
    with pytest.raises(ValueError, match="keep or upgrade"):
        manager.choose(DEP_TILE, "maybe")
    with pytest.raises(ValueError, match="not an adopted"):
        manager.choose(DEST_TILE, "keep")


def test_an_upgrade_that_would_write_over_the_package_is_refused():
    manager, _b, _p = _manager(info=dict(INFO, upgrade_ok=False))
    with pytest.raises(ValueError, match="write over it"):
        manager.choose(DEP_TILE, "upgrade")
    book = ADOPTED.ChoiceBook()
    book.set(DEP_TILE, "upgrade")           # remembered before: asked again
    again, _b, _p = _manager(book, info=dict(INFO, upgrade_ok=False))
    assert _job(again, DEP_TILE).state == CHOICE_STATE


def test_an_endpoint_of_ours_never_asks():
    manager, _b, _p = _manager(adopted=())
    assert manager.status(0.0)["choices"] == ()
    assert _job(manager, DEP_TILE).state == "swapped"


def test_flight_choose_is_a_command():
    assert "flight_choose" in FC.flight_handlers(type(
        "S", (), {"_emit": staticmethod(lambda e: None)})())
    assert ADOPTED.parse_tile("+53-061") == DEP_TILE
    assert ADOPTED.parse_tile([53, -61]) == DEP_TILE
    with pytest.raises(ValueError):
        ADOPTED.parse_tile(None)


# ------------------------------------------------------------- patched

def _install(root, *, patch=False, mark="Ortho4XP.cfg"):
    tile = root / "Tiles" / "zOrtho4XP_+53-061"
    tile.mkdir(parents=True)
    if mark == "Ortho4XP.cfg":
        (root / mark).write_text("", "utf-8")
    else:
        (root / "Patches").mkdir()
    if patch:
        folder = root / "Patches" / "+50-070" / "+53-061"
        folder.mkdir(parents=True)
        (folder / "CYYR.patch.osm").write_text("<osm/>", "utf-8")
    return tile


def test_patched_reads_the_source_install(tmp_path):
    yes = _install(tmp_path / "a", patch=True)
    no = _install(tmp_path / "b", mark="Patches")
    alone = tmp_path / "c" / "somewhere" / "zOrtho4XP_+53-061"
    alone.mkdir(parents=True)
    assert PATCHED._ortho4xp_root(str(yes)) == str((tmp_path / "a").resolve())
    assert ADOPTED._patched({"source": str(yes)}, *DEP_TILE) == "yes"
    assert ADOPTED._patched({"source": str(no)}, *DEP_TILE) == "no"
    assert ADOPTED._patched({"source": str(alone)}, *DEP_TILE) == "unknown"
    assert ADOPTED._patched(None, *DEP_TILE) == "unknown"
    # a cfg / log of the tile's folder naming a patch
    (alone / "Ortho4XP_+53-061.log").write_text(
        "including CYYR.patch.osm\n", "utf-8")
    assert ADOPTED._patched({"source": str(alone)}, *DEP_TILE) == "yes"
    # a link in Custom Scenery to the install's tile folder
    link = tmp_path / "link"
    link.symlink_to(yes)
    assert ADOPTED._patched({"link_target": str(link)}, *DEP_TILE) == "yes"


def _build_data(folder, *, encoded, other=True):
    """An Ortho4XP build's data in a tile folder: ``Data<tile>.apt``
    listing CYYR (and an airport of no interest), ``.node`` and ``.poly``
    with a RUNWAY-marked edge on CYYR's runway when ``encoded``, and one
    elsewhere when ``other``."""
    import pickle

    from shapely import geometry
    runway = geometry.MultiPolygon([geometry.box(0.40, 0.30, 0.42, 0.32)])
    elsewhere = geometry.MultiPolygon([geometry.box(0.80, 0.80, 0.81, 0.81)])
    airports = {"CYYR": {"key_type": "icao", "runway": (runway, [], [])},
                "Some Field": {"key_type": "name",
                               "runway": (elsewhere, [], [])}}
    stem = folder / "Data+53-061"
    (folder / "Data+53-061.apt").write_bytes(pickle.dumps(airports))
    nodes = [(0.41, 0.305), (0.41, 0.315), (0.805, 0.802), (0.805, 0.808),
             (0.1, 0.1), (0.2, 0.2)]
    stem.with_suffix(".node").write_text(
        "%d 2 1 0\n" % len(nodes) + "".join(
            "%d %.9f %.9f 100.0\n" % (i + 1, x, y)
            for i, (x, y) in enumerate(nodes)), "utf-8")
    edges = [(5, 6, 8 | 32)]                # the build's marker set
    if encoded:
        edges.append((1, 2, 16))
    if other:
        edges.append((3, 4, 16 | 8))
    stem.with_suffix(".poly").write_text(
        "0 2 1 0\n\n%d 1\n" % len(edges) + "".join(
            "%d %d %d %d\n" % (i + 1, a, b, m)
            for i, (a, b, m) in enumerate(edges)) + "\n0\n", "utf-8")


def test_the_build_data_reads_an_airport_patched(tmp_path):
    """Twin of the owner's adopted tiles (2026-11-13, no Ortho4XP install
    on disk): an airport the build knew whose runways carry no RUNWAY
    edge was patched; one with them was not; the witness is silent for an
    airport the build did not know, or a build that marks no runway."""
    no, yes, silent = (tmp_path / n for n in ("no", "yes", "silent"))
    for folder in (no, yes, silent):
        folder.mkdir()
    _build_data(no, encoded=True)
    _build_data(yes, encoded=False)
    _build_data(silent, encoded=False, other=False)
    old = tmp_path / "old"                  # Ortho4XP 1.30: 16 is no runway
    old.mkdir()
    _build_data(old, encoded=True)
    poly = old / "Data+53-061.poly"
    poly.write_text(poly.read_text("utf-8").replace(" 40\n", " 8\n"), "utf-8")
    assert PATCHED._airport_encoded(str(old), *DEP_TILE, "CYYR") is None
    assert PATCHED._airport_encoded(str(no), *DEP_TILE, "cyyr") is True
    assert PATCHED._airport_encoded(str(yes), *DEP_TILE, "CYYR") is False
    assert PATCHED._airport_encoded(str(silent), *DEP_TILE, "CYYR") is None
    assert PATCHED._airport_encoded(str(no), *DEP_TILE, "KXXX") is None
    assert ADOPTED._patched({"source": str(no)}, *DEP_TILE, "CYYR") == "no"
    assert ADOPTED._patched({"source": str(yes)}, *DEP_TILE, "CYYR") == "yes"
    assert ADOPTED._patched({"source": str(yes)}, *DEP_TILE) == "unknown"
    assert ADOPTED._patched({"source": str(silent)}, *DEP_TILE,
                           "CYYR") == "unknown"
    # an install's patch named for the airport answers before the data
    install = _install(tmp_path / "o4", patch=True)
    _build_data(install, encoded=True)
    assert ADOPTED._patched({"source": str(install)}, *DEP_TILE,
                           "CYYR") == "yes"


def test_an_airport_file_naming_anything_else_is_not_read(tmp_path):
    import pickle

    class Planted:
        def __reduce__(self):
            return (print, ("planted",))
    (tmp_path / "Data+53-061.apt").write_bytes(pickle.dumps(
        {"CYYR": Planted()}))
    assert PATCHED._airport_encoded(str(tmp_path), *DEP_TILE, "CYYR") is None


def test_an_endpoint_airport_patched_is_read_once_and_remembered(tmp_path):
    book = ADOPTED.ChoiceBook(str(tmp_path / ADOPTED.CHOICES_FILE))
    reads = []

    def patched_of(tile, icao):
        reads.append((tile, icao))
        return "no"
    manager, _b, _p = _manager(book, info=dict(INFO, patched="unknown"))
    manager.endpoints = ADOPTED.Endpoints(manager.endpoints._read, book,
                                          patched_of)
    assert manager.status(0.0)["choices"][0]["patched"] == "no"
    assert manager.status(1.0)["choices"][0]["patched"] == "no"
    assert reads == [(DEP_TILE, "CYYR")]
    manager.choose(DEP_TILE, "keep")        # the answer keeps the reading
    saved = json.loads((tmp_path / ADOPTED.CHOICES_FILE).read_text("utf-8"))
    assert saved["+53-061"]["patched"] == {"CYYR": "no"}
    assert saved["+53-061"]["choice"] == "keep"
    # a later flight with the source's drive gone: remembered
    again = ADOPTED.Endpoints(lambda t: dict(INFO, patched="unknown"),
                              ADOPTED.ChoiceBook(book.path),
                              lambda t, i: "unknown")
    assert again.patched(DEP_TILE, "CYYR", {}) == "no"
    # unknown is not remembered: read again next time
    book.set_patched(DEP_TILE, "XXXX", "unknown")
    assert book.patched(DEP_TILE, "XXXX") is None


def test_upgrade_overwrites_the_package_folder(tmp_path):
    folder = tmp_path / "zOrtho4XP_+53-061"
    folder.mkdir()
    assert not ADOPTED.upgrade_overwrites(str(folder), {})
    assert ADOPTED.upgrade_overwrites(str(folder), {"source": str(folder)})
    (folder / TINFO.ADOPTED_STAMP).write_text("{}", "utf-8")
    assert not ADOPTED.upgrade_overwrites(str(tmp_path / "other"), {})
    (folder / TINFO.ADOPTED_STAMP).write_text('{"from": "x"}', "utf-8")
    assert ADOPTED.upgrade_overwrites(str(folder), {})


# --------------------------------------------- the World pack's reading

def test_the_reader_asks_for_adopted_and_other_meshes_only(tmp_path,
                                                          monkeypatch):
    import O4_DSF_Binary as DSFB
    scenery = tmp_path / "Custom Scenery"
    pack = scenery / WP.PACK_NAME
    pack.mkdir(parents=True)
    (pack / WP.MARKER).write_text("{}", "utf-8")
    agents = {(53, -61): "Ortho4XP 1.30 [world full]",
              (53, -64): "XPTerrainBuilder 1.0 [world full]",
              (53, -62): "XPTerrainBuilder world drape"}
    for (lat, lon), agent in agents.items():
        path = pack / WP.dsf_relpath(lat, lon)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(DSFB.placeholder_bytes(lat, lon, agent) + b"\0" * 5000)
        textures = pack / "textures" / WP.tile_name(lat, lon)
        textures.mkdir(parents=True)
        (textures / "a.dds").write_bytes(b"DDS ")
    WP.write_placeholder(str(pack), 53, -63)
    source = _install(tmp_path / "o4", patch=True)
    from o4_engine import world_state as WS
    monkeypatch.setattr(WS, "_journal", lambda sd: {
        (53, -61): {"adopted": True, "source": str(source)}})
    info = ADOPTED.endpoint_reader(str(scenery),
                                   lambda la, lo: str(tmp_path / "build"))
    first = info((53, -61))
    assert first == {"origin": TINFO.ORIGIN_ADOPTED, "built_by": "Ortho4XP",
                     "patched": "yes", "upgrade_ok": True}
    for ours in ((53, -64), (53, -62), (53, -63), (50, 0)):
        assert info(ours) is None, ours


def _wild_estimate(tile, kind, role):
    """The HAAB flight of 2026-11-12T22:11Z: the upgraded departure's
    full build priced at one 512 px request's download rate while the
    first window's drapes fetched -- [530, 134406] s, a 2,240 min
    countdown."""
    if kind == "full":
        return (529.8, 134406.1)
    return _estimate(tile, kind, role)


def test_an_upgrade_never_counts_down_past_the_widest_estimate():
    """Twin of the HAAB 2,240 min countdown: the planned range is held to
    ``MAX_SPREAD`` x its low end, a measured scale never lifts it past
    ``RESCALE_RANGE[1]`` x the planned high, and the countdown and the
    choice row show no more than that."""
    manager, _builder, _pub = _manager()
    manager.estimate = _wild_estimate
    assert manager.status(0.0)["choices"][0]["upgrade_estimate_s"] \
        <= 529.8 * SCHEDULE.MAX_SPREAD + 1.0
    manager.choose(DEP_TILE, "upgrade")
    job = _job(manager, DEP_TILE)
    planned_hi = 529.8 * SCHEDULE.MAX_SPREAD
    assert job.est_s == (529.8, pytest.approx(planned_hi))
    assert job.est_s[1] < 134406.1 / 20          # was 51 x the model's
    manager._scale["full"] = 50.0                 # an unclamped scale
    manager.replan()
    job = _job(manager, DEP_TILE)
    assert job.est_s[1] <= SCHEDULE.RESCALE_RANGE[1] * planned_hi + 1e-6
    manager.tick(0.0, None)
    countdown = manager.status(0.0)["countdown_s"]
    assert countdown is not None
    assert countdown <= (SCHEDULE.RESCALE_RANGE[1] * planned_hi
                         + 4 * SCHEDULE.PROFILE_SECONDS["drape"] * 2.5
                         + SCHEDULE.DEPARTURE_MARGIN_S)
