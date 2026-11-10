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
from PySide6.QtCore import QPointF  # noqa: E402
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
    assert [c[2] for c in pane.cells()] == ["built", "quick", "building", "own"]
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

    def viewport(self):
        return NS(update=self._update)

    def _update(self):
        self.updates += 1

    def _viewport_point(self, lat, lon):
        return QPointF((lon + 70.0) * 20.0, (60.0 - lat) * 20.0)


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
