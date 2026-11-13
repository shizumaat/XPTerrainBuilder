"""The Qt window's Fly pane and map layer (spec flight-manager-and-world-
20261110 §4.3, §14; #2001; lane U2), driven on the shared fixture's
events with a fake command table.  Offscreen Qt, no engine, no network.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace as NS

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest  # noqa: E402

pytest.importorskip("PySide6")

import O4_Fly_Text as TEXT  # noqa: E402
import O4_Qt_Fly_Layer as QTFLYLAYER  # noqa: E402
import O4_Qt_Fly_Pane as QTFLY  # noqa: E402
from PySide6.QtCore import QPointF, Qt  # noqa: E402
from PySide6.QtGui import QImage, QPainter  # noqa: E402
from PySide6.QtWidgets import QApplication, QLabel  # noqa: E402

CASES = json.loads((Path(__file__).resolve().parent / "fixtures"
                    / "fly_pane_cases.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


class _Engine:
    """The command table standing in: answers some, refuses the rest."""

    def __init__(self, answers):
        self.answers = answers
        self.calls = []

    def __call__(self, name, **arguments):
        self.calls.append((name, arguments))
        if name not in self.answers:
            raise KeyError("unknown command: %r" % (name,))
        return self.answers[name]


def _pane(engine, prefs=None):
    saved = []
    pane = QTFLY.FlyPane(QLabel("follow"), run=engine,
                         airports=lambda: [NS(code="CYYR", lat=53.3192, lon=-60.4258),
                                           NS(code="CYYT", lat=47.6186, lon=-52.7519)],
                         prefs=prefs if prefs is not None else {},
                         save_prefs=saved.append)
    return pane, saved


def test_plans_list_fills_the_menu_and_a_plan_fills_the_card(qapp):
    plan = CASES["text"]["card"][2][0]
    engine = _Engine({"flight_plans_list": {"plans": [
        {"path": "/p/CYLWCYYC.fms", "name": "CYLWCYYC", "origin": "CYLW",
         "destination": "CYYC", "modified_at": 1}]},
        "flight_plan_read": plan})
    pane, _ = _pane(engine)
    pane.refresh_plans("/X-Plane 12")
    combo = pane.plan_source_combo
    assert [combo.itemText(i) for i in range(combo.count())] == [
        TEXT.PLAN_CHOOSE, TEXT.PLAN_SIMBRIEF, "CYLW → CYYC (CYLWCYYC)", TEXT.PLAN_NONE]
    combo.setCurrentIndex(2)
    pane._source_chosen(2)
    assert engine.calls[-1] == ("flight_plan_read", {"path": "/p/CYLWCYYC.fms"})
    assert pane.cruise_kt() == 280                      # from the plan
    assert pane.card_label.text().split("\n") == TEXT.card_lines(plan, 280)
    assert not pane.chk_build_alternate.isChecked()     # off by default (10g)
    assert pane.chk_build_alternate.isEnabled()         # the plan has one


def test_opening_fly_shows_a_prepared_flight_so_it_can_be_ended(qapp):
    """#2019 (owner: "the end flight button is disabled"): a prepared
    record whose job sent no FlightStatus is read when Fly opens
    (``flight_status``); End flight is enabled and ends it."""
    status = dict(CASES["events"]["FlightStatus"])
    engine = _Engine({"flight_status": status, "flight_end": {}})
    pane, _ = _pane(engine)
    assert not pane.end_flight_btn.isEnabled()
    pane.refresh_status()
    assert engine.calls[-1] == ("flight_status", {})
    assert pane.end_flight_btn.isEnabled()
    pane.end_flight_btn.click()
    assert engine.calls[-1] == ("flight_end", {"flight": status["flight"]})
    none = _Engine({"flight_status": {"flight": None}})
    pane, _ = _pane(none)
    pane.refresh_status()
    assert pane.status is None and not pane.end_flight_btn.isEnabled()


def test_no_plan_closes_a_prepared_flight_only(qapp):
    """"No plan: follow the aircraft" asks the engine to close the active
    flight only while it is still preparing or ready (#2019): a stale
    prepared record never owns build-ahead; a flight in the air stays."""
    status = CASES["events"]["FlightStatus"]
    for reply, cleared in (({"flight": status["flight"], "state": "closed"}, True),
                           ({"flight": None}, False)):
        engine = _Engine({"flight_end": reply})
        pane, _ = _pane(engine)
        pane.show_status(NS(**status))
        combo = pane.plan_source_combo
        combo.setCurrentIndex(combo.findData("none"))
        pane._source_chosen(combo.currentIndex())
        assert ("flight_end", {"if_prepared": True}) in engine.calls
        assert (pane.status is None) is cleared


def test_quick_entry_and_a_refusing_engine(qapp):
    engine = _Engine({})
    pane, _ = _pane(engine)
    pane.quick_from.setText("cyyr")
    pane.quick_to.setText("zzzz")
    pane.use_quick_entry()
    assert pane.plan is None and pane.message_label.text() == TEXT.unknown_airport("zzzz")
    pane.quick_to.setText("CYYT")
    pane.use_quick_entry()
    assert pane.plan == TEXT.quick_plan(("CYYR", 53.3192, -60.4258),
                                        ("CYYT", 47.6186, -52.7519))
    assert not pane.chk_build_alternate.isEnabled()     # no alternate
    pane.prepare()
    name, arguments = engine.calls[-1]
    assert name == "flight_create" and arguments["build_alternate"] is False
    assert arguments["corridor_km"] == TEXT.DEFAULT_CORRIDOR_KM
    assert pane.message_label.text() == TEXT.NO_FLIGHT_MANAGER


def test_status_events_fill_the_checklist_and_countdown(qapp):
    pane, _ = _pane(_Engine({"flight_end": {}}))
    status = CASES["events"]["FlightStatus"]
    assert not pane.divert_btn.isEnabled()
    pane.show_status(NS(**status))
    assert pane.readiness_list.text().split("\n") == [
        TEXT.item_text(r) for r in status["items"]]
    assert TEXT.countdown_text(712) in pane.countdown_label.text()
    assert pane.divert_btn.isEnabled() and pane.end_flight_btn.isEnabled()
    pane.show_world(CASES["events"]["WorldStatus"])
    assert pane.world_line.text() == TEXT.world_line(CASES["events"]["WorldStatus"])
    # the flight's cells, then build-ahead's around the aircraft beside it
    # (#2019): +53-060 stays the flight's, +53-059 and +54-060 are added
    assert [c[2] for c in pane.cells()] == ["built", "draped", "meshing", "own",
                                            "draped", "own"]
    pane.end_flight_btn.click()
    assert pane.status is None and pane.readiness_list.text() == TEXT.NO_STATUS


def test_preferences_are_remembered(qapp):
    prefs = {"simbrief_user": "pilot1", "fly_live_preview": True}
    engine = _Engine({})
    pane, saved = _pane(engine, prefs)
    assert pane.simbrief_edit.text() == "pilot1" and pane.chk_live_preview.isChecked()
    pane.sim_priority_combo.setCurrentIndex(0)
    assert saved and prefs["fly_sim_priority"] == "smooth"
    pane.fetch_simbrief()
    assert engine.calls[-1] == ("flight_plan_simbrief", {"user": "pilot1"})


class _Map:
    def __init__(self):
        self.updates = 0
        self.cell = None

    def clicked_cell(self, _event):
        return self.cell

    def viewport(self):
        return NS(update=self._update)

    def _update(self):
        self.updates += 1

    def _viewport_point(self, lat, lon):
        return QPointF((lon + 70.0) * 20.0, (60.0 - lat) * 20.0)


def test_a_fly_view_click_fills_from_then_a_command_click_fills_to(qapp):
    """#2026: a click on a cell with From/To empty fills From with the
    cell's largest custom airport (else its largest); a Cmd/Ctrl-click on
    a second cell fills To; Use finds a custom airport the index lacks."""
    index = [NS(code="BIGA", lat=53.3, lon=-60.4, extent=None, size_class=0,
                runway_m=3500),
             NS(code="SMLB", lat=53.6, lon=-60.6, extent=None, size_class=3,
                runway_m=900),
             NS(code="ARRV", lat=47.6, lon=-52.7, extent=None, size_class=1,
                runway_m=2500)]
    custom = [("SMLB", 53.6, -60.6), ("XCUS", 47.2, -52.2)]
    pane = QTFLY.FlyPane(QLabel("follow"), run=_Engine({}),
                         airports=lambda: index, prefs={},
                         custom_airports=lambda: custom)
    view = _Map()
    layer = QTFLYLAYER.FlyLayer(view, pane)
    plain = NS(modifiers=lambda: Qt.NoModifier)
    command = NS(modifiers=lambda: Qt.ControlModifier)
    view.cell = (53, -61)
    assert not layer.mouse_release(plain)            # not in Fly
    layer.set_shown(True)
    assert not layer.mouse_release(command)          # From empty: no To
    assert layer.mouse_release(plain)
    assert pane.quick_from.text() == "SMLB"          # custom beats larger
    assert not layer.mouse_release(plain)            # From filled
    view.cell = (47, -53)
    assert layer.mouse_release(command)
    assert pane.quick_to.text() == "XCUS"            # custom-only airport
    pane.use_quick_entry()
    assert pane.plan == TEXT.quick_plan(("SMLB", 53.6, -60.6),
                                        ("XCUS", 47.2, -52.2))
    assert not layer.mouse_release(command)          # To filled
    pane.quick_from.setText("")
    pane.quick_to.setText("")
    view.cell = (10, 10)
    assert not layer.mouse_release(plain)            # no airport there
    view.cell = None
    assert not layer.mouse_release(plain)            # a drag, not a click


def test_the_layer_draws_in_fly_only(qapp):
    pane, _ = _pane(_Engine({}))
    pane.quick_from.setText("CYYR")
    pane.quick_to.setText("CYYT")
    pane.use_quick_entry()
    view = _Map()
    layer = QTFLYLAYER.FlyLayer(view, pane)
    image = QImage(800, 400, QImage.Format_ARGB32)
    image.fill(0)

    def drawn():
        painter = QPainter(image)
        layer.paint(painter)
        painter.end()
        return any(image.pixel(x, y) for x in range(0, 800, 4) for y in range(0, 400, 4))
    assert not drawn()                              # not in Fly
    layer.set_shown(True)
    before = view.updates
    pane.show_position(NS(lat=53.3, lon=-60.4, track_deg=90.0))
    pane.show_position(NS(lat=53.3, lon=-60.3, track_deg=90.0))
    assert view.updates > before and len(pane.track.parts()) == 1
    assert drawn()


def test_divert_waiver_reload_and_notice(qapp):
    """Lane F2: the waiver row shows the tiles that need the internet and
    sends ``flight_update {waive_offline}``; the reload offer shows "Not
    now" only while announced and sends ``flight_reload``; "Divert…"'s
    dialog searches X-Plane's airports and sends ``flight_divert``; a
    ``FlightNotice`` becomes the pane's notice line."""
    import O4_Qt_Fly_Divert as QTDIVERT
    answers = {"flight_update": {}, "flight_reload": {}, "flight_divert": {}}
    engine = _Engine(answers)
    pane, _saved = _pane(engine)
    status = dict(CASES["events"]["FlightStatus"], waivable=["+53-062"],
                  reload="offered", diverted_to="CYQX")
    pane.show_status(status)
    assert not pane.offline_waiver_row.isHidden()
    assert "1 tile(s)" in pane.waiver_label.text()
    pane.offline_waiver_row.buttons[0].click()
    assert engine.calls[-1] == ("flight_update", {
        "flight": status["flight"], "waive_offline": True})
    assert not pane.reload_offer_row.isHidden()
    assert len(pane.reload_offer_row.buttons) == 1      # no "Not now" (#2019)
    pane.show_status(dict(status, waivable=[]))
    assert pane.offline_waiver_row.isHidden()
    pane.reload_offer_row.buttons[0].click()
    assert engine.calls[-1] == ("flight_reload", {"flight": status["flight"]})
    pane.show_status(dict(status, reload="sent", waivable=[]))
    assert pane.reload_offer_row.isHidden()
    pane.divert_to({"ident": "CYYT", "lat": 47.6, "lon": -52.7})
    assert engine.calls[-1] == ("flight_divert", {
        "flight": status["flight"], "to": {"ident": "CYYT", "lat": 47.6,
                                           "lon": -52.7}})
    dialog = QTDIVERT.DivertDialog(
        lambda: [NS(code="CYYT", name="St. John's", lat=47.6, lon=-52.7),
                 NS(code="CYYR", name="Goose Bay", lat=53.3, lon=-60.4)], True)
    dialog.search_edit.setText("goose")
    assert dialog.results.count() == 1
    dialog.divert_btn.click()
    assert dialog.choice() == {"ident": "CYYR", "lat": 53.3, "lon": -60.4}
    alt = QTDIVERT.DivertDialog(lambda: [], True)
    alt.alternate_btn.click()
    assert alt.choice() == "alternate"
    notice = CASES["events"]["FlightNotice"]
    pane.show_notice(notice)
    assert not pane.notice_label.isHidden()
    assert pane.notice_label.text().startswith("Diversion ready")


def test_free_flight_draws_the_drapes_ahead_and_the_detail_is_the_global(
        qapp, monkeypatch):
    """RULINGS 2026-11-11j: with no flight and no plan the map's cells are
    build-ahead's tiles (``WorldStatus.jobs``); "Photo detail ahead" reads
    and writes the global ``drape_photo_px`` (the engine reads it per
    tile), never the window's prefs."""
    import O4_Settings_Model as SM
    written = []
    monkeypatch.setattr(SM, "read_global_raw", lambda *a: {"drape_photo_px": "1024"})
    monkeypatch.setattr(SM, "write_global", lambda values, *a: written.append(values))
    pane, saved = _pane(_Engine({}))
    combo = pane.drape_px_combo
    assert [combo.itemData(i) for i in range(combo.count())] == [
        v for v, _w in TEXT.DRAPE_PX_CHOICES]
    assert combo.currentData() == 1024 and not written
    combo.setCurrentIndex(combo.findData(4096))
    assert written == [{"drape_photo_px": 4096}] and not saved
    world = CASES["events"]["WorldStatus"]
    pane.show_world(world)
    assert pane.cells() == [(53, -60, "draping"), (53, -59, "draped"),
                            (54, -60, "own")]


def test_no_plan_shows_the_aircrafts_tile_and_the_key_always(qapp):
    """#2020: with no plan the here block says where imagery is being
    prepared and how far it is, and offers the reload while the follow
    line does not; the map key shows whatever the plan (#2031: the one
    key's items, "Building" for a mesh or a drape under way, no route or
    sharp item); "Sharp photo" is the live preview's toggle, on by
    default and live only while "Live flight preview" is checked."""
    engine = _Engine({"scenery_reload": {"sent": True}})
    pane, saved = _pane(engine)
    assert pane.here_block.isHidden()
    layer = QTFLYLAYER.FlyLayer(_Map(), pane)
    assert layer.key_items() == ["full", "mesh", "drape", "placeholder",
                                 "building", "custom"]
    assert pane.chk_sharp_photo.isChecked()
    assert not pane.chk_sharp_photo.isEnabled()
    pane.chk_live_preview.setChecked(True)
    assert pane.chk_sharp_photo.isEnabled()
    assert "sharp" not in layer.key_items()
    pane.chk_sharp_photo.setChecked(False)
    assert pane.prefs[QTFLY.PREF_SHARP_PHOTO] is False
    here = [h for h in CASES["text"]["here_lines"] if h[0] and h[0].get("core")
            and h[0].get("job") == "building"][0]
    pane.show_world(dict(CASES["events"]["WorldStatus"],
                         here=dict(here[0], reload_offer="tiles")))
    assert not pane.here_block.isHidden()
    assert pane.here_label.text() == "<br>".join(here[1])
    assert not pane.here_offer_row.isHidden()
    pane.set_plan(TEXT.quick_plan(("CYYR", 53.3, -60.4), ("CYYT", 47.6, -52.7)))
    assert pane.here_block.isHidden()


def test_the_aircraft_is_the_shared_airplane(qapp):
    """Owner 2026-11-12T15:33Z: the map's aircraft is the G1000-style
    airplane of ``O4_Fly_Layers.AIRCRAFT_SYMBOL``, white with a dark
    outline, the same size at any zoom."""
    pane, _ = _pane(_Engine({}))
    view = _Map()
    layer = QTFLYLAYER.FlyLayer(view, pane)
    layer.set_shown(True)
    pane.show_position(NS(lat=53.3, lon=-60.4, track_deg=0.0))
    image = QImage(800, 400, QImage.Format_ARGB32)
    image.fill(0)
    painter = QPainter(image)
    layer.paint(painter)
    painter.end()
    at = view._viewport_point(53.3, -60.4)
    white = QTFLYLAYER.AIRCRAFT_FILL.rgb()
    assert image.pixel(int(at.x()), int(at.y()) - 5) == white      # fuselage
    assert image.pixel(int(at.x()) + 5, int(at.y())) == white      # right wing
    assert image.pixel(int(at.x()) + 7, int(at.y()) - 8) != white  # beside the nose


def test_the_photo_source_is_automatic_or_one_source(qapp, monkeypatch):
    """Owner 2026-11-12T19:17Z / #2018: "Photo source" lists Automatic,
    then the Build pane's imagery entries, and writes the app setting
    ``fly_photo_source`` (the engine reads it per build:
    ``test_flight_manager``'s ``test_the_photo_source_is_read_per_build``),
    never the prefs; unset, it reads Automatic."""
    import O4_Settings_Model as SM
    written, values = [], {"fly_photo_source": "GO2"}
    monkeypatch.setattr(SM, "read_global_raw", lambda *a: dict(values))
    monkeypatch.setattr(SM, "write_global", lambda v, *a: written.append(v))
    pane, saved = _pane(_Engine({}))
    entries = [{"code": c, "label": c, "enabled": True, "tooltip": "",
                "section": "World"} for c in ("BI", "GO2", "Arc")]
    pane.set_photo_sources(entries)
    combo = pane.photo_source_combo
    assert [combo.itemData(i) for i in range(combo.count())] == [
        "auto", "BI", "GO2", "Arc"]
    assert combo.itemText(0) == TEXT.PHOTO_SOURCE_AUTO_LABEL
    assert combo.currentData() == "GO2" and not written
    combo.setCurrentIndex(combo.findData("Arc"))
    combo.activated.emit(combo.currentIndex())
    assert written == [{"fly_photo_source": "Arc"}] and not saved
    values.clear()
    pane.set_photo_sources(entries)
    assert combo.currentData() == "auto"
