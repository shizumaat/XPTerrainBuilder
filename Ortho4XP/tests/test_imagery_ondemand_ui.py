"""Imagery on demand in both apps (#1992 spec §7, §14 P4).

* The words: ``Sources/SceneryKit/ImageryOnDemandText.swift`` says what
  ``src/O4_Imagery_OnDemand_Text.py`` says (the Qt window's), literal for
  literal, and both fill the same template slots.
* The follow status line renders EVERY ``ImageryFollowStatus`` field.
* The settings rows round-trip through the global cfg into the follow
  job's settings and the cap.
* The pin actions (tile pane, Library) call ``imagery_pin``; "Make all
  low-res again" names the space it frees before it runs.

Offscreen Qt where a widget is needed; no network, no engine session.
"""
from __future__ import annotations

import dataclasses
import os
import re
import sys
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import O4_Imagery_OnDemand_Text as TEXT  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
SWIFT_TEXT = REPO / "Sources" / "SceneryKit" / "ImageryOnDemandText.swift"
SWIFT_STATUS = REPO / "Sources" / "SceneryKit" / "ImageryFollowStatus.swift"

#: Swift ``static let`` -> the Python value it mirrors.
SWIFT_TO_PYTHON = {
    "pinTitle": TEXT.PIN_TITLE, "unpinTitle": TEXT.UNPIN_TITLE,
    "pinRowTitle": TEXT.PIN_ROW_TITLE, "lowResState": TEXT.LOW_RES_STATE,
    "pinnedState": TEXT.PINNED_STATE, "pinnedBadge": TEXT.PINNED_BADGE,
    "pinHelp": TEXT.PIN_HELP, "notOnDemandState": TEXT.NOT_ON_DEMAND_STATE,
    "makeLowResTitle": TEXT.MAKE_LOW_RES_TITLE,
    "makeLowResNone": TEXT.MAKE_LOW_RES_NONE, "pinsLine": TEXT.PINS_LINE,
    "coresLine": TEXT.CORES_LINE,
    "olderSharpNote": TEXT.OLDER_SHARP_NOTE,
    "followStartTitle": TEXT.FOLLOW_START_TITLE,
    "followStopTitle": TEXT.FOLLOW_STOP_TITLE,
    "followStarting": TEXT.FOLLOW_TEMPLATES["starting"],
    "followWaiting": TEXT.FOLLOW_TEMPLATES["waiting"],
    "followFollowing": TEXT.FOLLOW_TEMPLATES["following"],
    "followPaused": TEXT.FOLLOW_TEMPLATES["paused"],
    "followStopped": TEXT.FOLLOW_TEMPLATES["stopped"],
    "followError": TEXT.FOLLOW_TEMPLATES["error"],
    "followDetail": TEXT.FOLLOW_DETAIL, "waitingReason": TEXT.WAITING_REASON,
    "followNoTiles": TEXT.FOLLOW_NO_TILES,
    "xplaneAnswering": TEXT.XPLANE_ANSWERING, "xplaneSilent": TEXT.XPLANE_SILENT,
    "bufferNone": TEXT.BUFFER_NONE, "bufferAhead": TEXT.BUFFER_AHEAD,
    "reloadSceneryTitle": TEXT.RELOAD_SCENERY_TITLE,
    "reloadOfferImagery": TEXT.RELOAD_OFFER_IMAGERY,
    "reloadOfferTiles": TEXT.RELOAD_OFFER_TILES,
}


def _swift_literals() -> dict:
    text = SWIFT_TEXT.read_text(encoding="utf-8")
    return dict(re.findall(
        r'public static let (\w+) = "((?:[^"\\]|\\.)*)"', text))


def test_swift_says_what_python_says():
    assert _swift_literals() == SWIFT_TO_PYTHON


def test_swift_fills_the_slots_python_fills():
    text = SWIFT_TEXT.read_text(encoding="utf-8")
    body = text[text.index("func followValues"):text.index("func followLines")]
    swift_keys = set(re.findall(r'"(\w+)":', body)) - {"seconds"}
    assert swift_keys == set(TEXT._follow_values({}))
    slots = set()
    for template in (*TEXT.FOLLOW_TEMPLATES.values(), TEXT.FOLLOW_DETAIL):
        slots |= set(re.findall(r"\{(\w+)\}", template))
    assert slots == set(TEXT._follow_values({}))
    assert float(re.search(r"knotsPerMS = ([\d.]+)", text).group(1)) == \
        TEXT.KNOTS_PER_MS


def _event_fields() -> list:
    from o4_engine.events import ImageryFollowStatus
    return [f.name for f in dataclasses.fields(ImageryFollowStatus)
            if f.name in ImageryFollowStatus.__annotations__]


def test_the_status_line_renders_every_field():
    """Distinct values in every field: each one shows (spec §14 P4)."""
    status = {"state": "following", "reason": "", "xplane": True,
              "lat": 60.123, "lon": -136.456, "speed_ms": 100.0,
              "track_deg": 271.0, "queued": 31, "in_flight": 2, "slots": 3,
              "buffer_s": 47.0, "sharp": 14, "textures": 120, "landed": 9,
              "late": 4, "failed": 5, "bytes_landed": 34_500_000,
              "flight_loads": 6, "jumps": 7, "reloads": 8,
              "reload_offer": "imagery"}   # its own row (#2019), not the line
    assert set(status) == set(_event_fields()), "a field has no test value"
    headline, detail = TEXT.follow_lines(status)
    line = headline + " " + detail
    for shown in ("14 of 120 sharp", "2 downloading", "4 late", "31 queued",
                  "3 at a time", "47 s ahead", "9 landed (34.5 MB)",
                  "5 failed", "X-Plane answering", "60.123, -136.456",
                  "194 kt", "track 271°", "6 flight loads", "7 jumps", "8 reload offers"):
        assert shown in line, shown
    # reason and state: each state has its sentence, the reason verbatim.
    for state, template in TEXT.FOLLOW_TEMPLATES.items():
        said = TEXT.follow_lines({**status, "state": state,
                                  "reason": "A build is running"})[0]
        assert said == template.format(**TEXT._follow_values(
            {**status, "reason": "A build is running"}))
    assert "A build is running" in TEXT.follow_lines(
        {"state": "paused", "reason": "A build is running"})[0]
    assert TEXT.WAITING_REASON in TEXT.follow_lines({"state": "waiting",
                                                     "textures": 1})[0]
    assert TEXT.BUFFER_NONE in TEXT.follow_lines({"buffer_s": -1})[1]
    assert TEXT.XPLANE_SILENT in TEXT.follow_lines({"xplane": False})[1]


def test_swift_reads_every_status_property():
    """The Swift status struct's every property feeds a slot."""
    struct = SWIFT_STATUS.read_text(encoding="utf-8")
    properties = re.findall(r"public let (\w+):", struct)
    assert len(properties) == len(_event_fields())
    text = SWIFT_TEXT.read_text(encoding="utf-8")
    body = text[text.index("func followValues"):text.index("func followLines")]
    for name in properties:
        if name in ("state", "reloadOffer"):
            continue                 # the template; the reload row (#2019)
        assert re.search(r"\$?s\.%s\b" % name, body), name


def test_the_settings_round_trip_through_the_cfg(tmp_path):
    import O4_Cfg_Vars as CV
    import O4_Settings_Model as SM
    from o4_engine import imagery_commands as CMDS
    from o4_engine import imagery_downgrade as DOWNGRADE

    for name, default in (("imagery_on_demand", True),
                          ("imagery_on_demand_cap_gb", 100.0),
                          ("ondemand_lead_s", 30.0),
                          ("ondemand_lands_per_s", 4.0),
                          ("xplane_web_api_port", 8086),
                          ("placeholder_zl_drop", 3)):
        assert CV.cfg_vars[name]["default"] == default, name
        assert SM.get_setting(name) is not None, name
    cfg = str(tmp_path / "XPTerrainBuilder.cfg")
    assert CMDS.follow_settings(SM.read_global_raw(cfg)) == {
        "enabled": True, "port": 8086, "lead_s": 30.0, "lands_per_s": 4.0}
    SM.write_global({"imagery_on_demand": "True", "xplane_web_api_port": "9001",
                     "ondemand_lead_s": "45", "ondemand_lands_per_s": "2",
                     "imagery_on_demand_cap_gb": "12.5"}, cfg)
    raw = SM.read_global_raw(cfg)
    assert CMDS.follow_settings(raw) == {
        "enabled": True, "port": 9001, "lead_s": 45.0, "lands_per_s": 2.0}
    assert DOWNGRADE.cap_bytes(raw) == int(12.5e9)


def test_the_automatic_start_waits_for_the_switch_or_on_demand_tiles(
        monkeypatch, tmp_path):
    """#2019: the follow job starts by itself while the switch is on OR
    the on-demand index holds textures (converted or adopted tiles); the
    switch says only how new builds are made.  Off and empty: "off"."""
    import O4_Imagery_OnDemand_Index as IDX
    from o4_engine import imagery_commands as CMDS
    from o4_engine import imagery_follow as FOLLOW

    monkeypatch.setattr(CMDS, "follow_settings", lambda raw=None: {
        "enabled": False, "port": 8086, "lead_s": 30.0, "lands_per_s": 4.0})
    index = str(tmp_path / "index.sqlite")
    assert not IDX.has_rows(index) and not (tmp_path / "index.sqlite").exists()
    assert CMDS.start_imagery_follow(lambda e: None, if_enabled=True,
                                     index_path=index) == {"status": "off"}
    assert not CMDS.follow_running()
    conn = IDX.open_index(index)
    IDX.upsert(conn, {"tile": "+49-098", "name": "1_2_BI16.dds"})
    conn.close()
    assert IDX.has_rows(index) and CMDS.follow_wanted(index_path=index)

    class Job:
        running = True

        def __init__(self, emit, **kw):
            pass

        def start(self):
            return self
    monkeypatch.setattr(FOLLOW, "FollowJob", Job)
    monkeypatch.setattr(CMDS, "_FOLLOW", {"job": None})
    assert CMDS.start_imagery_follow(lambda e: None, if_enabled=True,
                                     index_path=index, tiles=[["x", 1, 1]]) == {
        "status": "started"}


def test_make_all_low_res_names_the_space_it_frees():
    message = TEXT.make_low_res_message(2_500_000_000, 220)
    assert "2.50 GB" in message and "220" in message
    assert "favorites are kept" in message
    assert TEXT.pins_line(1_400_000_000, 7) == (
        "Favorites: 1.40 GB in 7 texture(s), made low-res last")
    assert TEXT.pins_line(0, 0, 3).startswith("3 of them near airports")


@pytest.fixture
def qapp():
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _sync_thread(monkeypatch):
    import O4_Qt_Library as QTLIB

    def run(work, signal, _name):
        try:
            signal.emit(work())
        except Exception as error:      # noqa: BLE001 — the seam's contract
            signal.emit(error)
    monkeypatch.setattr(QTLIB, "emit_from_thread", run)


def test_the_library_pin_calls_imagery_pin(qapp, monkeypatch):
    import O4_Qt_Library as QTLIB
    from o4_engine import imagery_ondemand as ONDEMAND

    calls = []
    monkeypatch.setattr(ONDEMAND, "imagery_pin", lambda lat, lon, **kw: (
        calls.append((lat, lon, kw)) or {"tile": "+60-136", "pinned": kw["pinned"],
                                         "served": 3, "to_fetch": 5}))
    _sync_thread(monkeypatch)
    dialog = QTLIB.LibraryTilesSection(None, "/tiles", "")
    monkeypatch.setattr(dialog, "refresh", lambda: None)
    row = {"tile": "+60-136", "lat": 60, "lon": -136, "build_dir": "/t",
           "size_bytes": 1, "zl": 16, "provider": "BI", "built": None,
           "airports": [], "packs_modified": [], "link_status": "x",
           "in_xplane": False, "built_by": "XPTerrainBuilder",
           "read_only": False, "on_demand": True, "pinned": False}
    dialog.set_library({"tiles": [row], "caches": [], "tiles_bytes": 1})
    dialog.table.selectRow(0)
    assert dialog.pin_btn.isEnabled()
    assert dialog.pin_btn.text() == TEXT.PIN_TITLE
    dialog.pin_btn.click()
    assert calls == [(60, -136, {"working_dir": "/tiles", "pinned": True})]
    assert "3 texture(s) sharp now, 5 to fetch" in dialog.status_label.text()
    dialog.set_library({"tiles": [{**row, "pinned": True}], "caches": [],
                        "tiles_bytes": 1})
    assert dialog.table.item(0, 0).text() == "+60-136 · " + TEXT.PINNED_BADGE
    dialog.table.selectRow(0)
    assert dialog.pin_btn.text() == TEXT.UNPIN_TITLE


def test_the_tile_pane_pin_row(qapp):
    from types import SimpleNamespace as NS

    import O4_Qt_Imagery_OnDemand as QTONDEMAND

    row = QTONDEMAND.TilePinRow()
    asked = []
    row.pin_requested.connect(asked.append)
    # RULINGS 2026-11-10c (1): a Favorite switch on every tile this app
    # built, working on a tile built on demand.
    full = NS(on_demand=False, pinned=False, origin="")
    assert not row.applies(full) and row.shows(full)
    assert not row.shows(NS(on_demand=False, pinned=False, origin="other"))
    row.show_tile((60, -136), full)
    assert not row.switch.isEnabled()
    assert row.label.text() == TEXT.NOT_ON_DEMAND_STATE
    row.show_tile((60, -136), NS(on_demand=True, pinned=False))
    assert row.label.text() == TEXT.LOW_RES_STATE
    assert row.switch.isEnabled() and not row.switch.isChecked()
    row.switch.click()
    assert asked == [(60, -136, True)]
    row.show_tile((60, -136), NS(on_demand=True, pinned=True))
    assert row.switch.isChecked() and row.label.text() == TEXT.PINNED_STATE
    row.switch.click()
    assert asked[-1] == (60, -136, False)


def test_the_follow_line_shows_every_field_and_toggles(qapp):
    import O4_Qt_Imagery_OnDemand as QTONDEMAND

    line = QTONDEMAND.FollowStatusLine()
    toggles = []
    line.toggle_requested.connect(toggles.append)
    line.toggle_btn.click()
    assert toggles == [True]
    status = {"state": "following", "sharp": 14, "textures": 120,
              "in_flight": 2, "late": 0, "xplane": True}
    line.show_status(status)
    assert (line.headline.text(), line.detail.text()) == TEXT.follow_lines(status)
    assert line.toggle_btn.text() == TEXT.FOLLOW_STOP_TITLE
    line.toggle_btn.click()
    assert toggles == [True, False]
    line.show_status({**status, "state": "stopped"})
    assert line.toggle_btn.text() == TEXT.FOLLOW_START_TITLE


def test_the_reload_offer_shows_a_button_and_reloads_only_on_its_click(qapp):
    """#2019 (owner 2026-11-12T14:34Z: "Never ask x-plane to reload
    unless the user requests it."): a pending offer shows its line and
    "Reload scenery"; only the click asks for the reload."""
    import O4_Qt_Imagery_OnDemand as QTONDEMAND

    line = QTONDEMAND.FollowStatusLine()
    asked = []
    line.reload_requested.connect(lambda: asked.append(1))
    status = {"state": "following", "sharp": 1, "textures": 2}
    line.show_status(status)
    assert line.reload_row.isHidden() and not asked
    for code in ("imagery", "tiles"):
        line.show_status({**status, "reload_offer": code})
        assert not line.reload_row.isHidden() and not asked
        assert line.reload_label.text() == TEXT.reload_offer_line(code)
    assert line.reload_btn.text() == TEXT.RELOAD_SCENERY_TITLE
    line.reload_btn.click()
    assert asked == [1]
    line.show_status(status)
    assert line.reload_row.isHidden()
    assert TEXT.reload_offer_line("") == ""
    swift = SWIFT_TEXT.read_text(encoding="utf-8")
    assert "func reloadOfferLine" in swift
    mac = (REPO / "Sources" / "XPTerrainBuilder" / "ImageryFollowLine.swift"
           ).read_text(encoding="utf-8")
    assert "reloadSceneryTitle" in mac and "reloadScenery()" in mac


def test_storage_makes_all_low_res_after_naming_the_space(qapp, monkeypatch):
    import O4_Qt_Settings_Storage as QTSTORE
    from o4_engine import imagery_ondemand as ONDEMAND
    from o4_engine import storage as STORAGE

    calls = []

    def downgrade_all(**kw):
        calls.append(kw)
        return {"downgraded": 12, "freed_bytes": 3_000_000_000,
                "dry_run": bool(kw.get("dry_run")), "stopped": False,
                "skipped_near": 0}
    monkeypatch.setattr(ONDEMAND, "imagery_ondemand_downgrade_all", downgrade_all)
    _sync_thread(monkeypatch)
    section = QTSTORE.StorageSection()
    monkeypatch.setattr(section, "_run", lambda work, signal: signal.emit(work()))
    monkeypatch.setattr(section, "refresh", lambda: None)
    asked = []
    monkeypatch.setattr(section, "confirm",
                        lambda title, message: asked.append((title, message)) or True)
    store = {"kind": STORAGE.ONDEMAND, "label": "Sharp imagery near flown areas",
             "policy": STORAGE.CACHE, "note": "n", "path": "/p", "bytes": 3e9,
             "apparent_bytes": 3e9, "files": 12, "last_used": None,
             "pinned_bytes": 1_400_000_000, "pinned_files": 7, "core_files": 0}
    section.set_scan({"root": "/r", "cache_bytes": 0, "kept_bytes": 0,
                      "stores": [store]})
    button = section.clear_buttons[STORAGE.ONDEMAND]
    assert button.text() == TEXT.MAKE_LOW_RES_TITLE + "…"
    button.click()
    assert asked == [(TEXT.MAKE_LOW_RES_TITLE + "?",
                      TEXT.make_low_res_message(3_000_000_000, 12))]
    assert calls == [{"dry_run": True}, {"confirm": True}]
    assert section.status_label.text().startswith("Freed ")
    older = QTSTORE._older_message({"files": 4, "freed_bytes": 10,
                                   "kinds": {STORAGE.ONDEMAND: 5}})
    assert older.endswith(TEXT.OLDER_SHARP_NOTE)
    assert TEXT.OLDER_SHARP_NOTE not in QTSTORE._older_message(
        {"files": 4, "freed_bytes": 10, "kinds": {STORAGE.ONDEMAND: 0}})


def test_the_mac_pin_and_low_res_reach_the_engine_commands():
    wire = (REPO / "Sources" / "SceneryKit" / "ImageryOnDemandWire.swift").read_text(
        encoding="utf-8")
    assert 'request("imagery_pin"' in wire
    assert '"imagery_ondemand_downgrade_all"' in wire
    app = REPO / "Sources" / "XPTerrainBuilder"
    for name in ("BuildPane.swift", "LibraryView.swift"):
        assert "setImageryPinned(" in (app / name).read_text(encoding="utf-8"), name
    follow = (app / "BuildModel+ImageryFollow.swift").read_text(encoding="utf-8")
    assert "client.imageryPin(" in follow


def test_favorites_show_a_star_on_both_maps(qapp):
    """RULINGS 2026-11-10c (1): a favorite tile carries a star on the map
    (Qt ``O4_Qt_Map_Favorite``; Mac ``MapCanvasView`` ``star.fill``)."""
    import O4_Qt_Map as QTMAP
    import O4_Qt_Map_Favorite as STAR
    from PySide6.QtCore import QRectF
    from PySide6.QtGui import QImage, QPainter

    points = STAR._star_points(0.0, 0.0, 10.0)
    assert len(points) == 10 and points[0] == (0.0, -10.0)
    image = QImage(64, 64, QImage.Format_ARGB32)
    image.fill(0)
    painter = QPainter(image)
    STAR.draw_star(painter, QRectF(0, 0, 64, 64), 64.0, 1.0)
    painter.end()
    assert image.pixelColor(56, 57).alpha() > 0          # bottom-right
    assert image.pixelColor(8, 8).alpha() == 0
    assert "QTFAVSTAR.draw_star" in Path(QTMAP.__file__).read_text(encoding="utf-8")
    mac = (REPO / "Sources" / "XPTerrainBuilder" / "MapCanvasView.swift").read_text(
        encoding="utf-8")
    assert 'info.pinned == true' in mac and 'systemName: "star.fill"' in mac
