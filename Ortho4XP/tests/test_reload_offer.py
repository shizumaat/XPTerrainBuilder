"""Twin of "Never ask x-plane to reload unless the user requests it."
(owner 2026-11-12T14:34Z, #2019): ``src/o4_engine/reload_offer.py`` is
the one place X-Plane's reload command is sent, and only the user's
click reaches it -- the follow job's spawn reload and a flight's S6 (a)
/ (b) reloads are offers.  Hermetic: no X-Plane, no network.
"""
from __future__ import annotations

import json
import os
import re
import sys

import pytest
from o4_engine import reload_offer as RELOAD

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, os.pardir, "src")
sys.path.insert(0, os.path.join(HERE, os.pardir, "tools"))

import flight_schedule_replay as R  # noqa: E402

DEST = (53.15, -63.9)


@pytest.fixture(autouse=True)
def fresh(monkeypatch):
    monkeypatch.setattr(RELOAD, "_STATE", {"offer": ""})


def test_only_reload_offer_sends_the_reload_command():
    """No module but ``reload_offer`` calls X-Plane's reload."""
    callers = []
    for root, _dirs, files in os.walk(SRC):
        for name in files:
            if not name.endswith(".py"):
                continue
            path = os.path.join(root, name)
            with open(path, encoding="utf-8") as f:
                text = f.read()
            if re.search(r"(?<!def )(?<!\w)reload_scenery\(|activate_command\(\s*\w*RELOAD", text):
                callers.append(os.path.relpath(path, SRC))
    assert sorted(callers) == sorted([
        os.path.join("o4_engine", "reload_offer.py"),
        "O4_XPlane_WebAPI.py"])       # the definition itself


def test_an_offer_waits_for_the_click(monkeypatch):
    import O4_XPlane_WebAPI as WEBAPI
    sent = []
    monkeypatch.setattr(WEBAPI, "reload_scenery",
                        lambda base=None: bool(sent.append(base)) or True)
    assert RELOAD.current() == ""
    assert RELOAD.offer("imagery") and RELOAD.current() == "imagery"
    assert RELOAD.offer("tiles") and RELOAD.offer("imagery")
    assert RELOAD.current() == "tiles"            # the swap outranks imagery
    assert sent == []                              # nothing until the click
    assert RELOAD.scenery_reload() == {"sent": True}
    assert sent == [None] and RELOAD.current() == ""
    with pytest.raises(ValueError):
        RELOAD.offer("everything")


def test_the_follow_job_offers_instead_of_reloading(monkeypatch):
    """Production wiring: the follow job's reloader is the offer."""
    import O4_XPlane_WebAPI as WEBAPI
    from o4_engine import imagery_commands as CMDS
    from o4_engine import imagery_follow as FOLLOW
    monkeypatch.setattr(WEBAPI, "reload_scenery", lambda base=None: (
        _ for _ in ()).throw(AssertionError("sent without the user")))
    built = {}

    class Job:
        def __init__(self, emit, **kw):
            built.update(kw)

        def start(self):
            return self
    monkeypatch.setattr(FOLLOW, "FollowJob", Job)
    monkeypatch.setattr(CMDS, "follow_settings", lambda: {
        "enabled": True, "port": 8086, "lead_s": 60, "lands_per_s": 4})
    monkeypatch.setattr(CMDS, "_FOLLOW", {"job": None})
    CMDS.start_imagery_follow(lambda e: None, tiles=[["x", 1, 1]])
    assert built["reloader"]() is True and RELOAD.current() == "imagery"
    status = FOLLOW._pending_offer()
    assert status == "imagery"


@pytest.fixture(scope="module")
def recording():
    with open(R.FIXTURE, encoding="utf-8") as f:
        flight = json.load(f)
    with open(R.KIT, encoding="utf-8") as f:
        kit = json.load(f)
    return flight, kit


def test_a_flight_never_reloads_unless_the_pilot_presses(recording):
    """The CYYR flight, with a late diversion that would need the one
    reload near the ground: when the pilot never presses, nothing
    reloads, on the ground or in the air, and the flight still departs
    (the offer does not hold it back)."""
    result = R.replay_flight(*recording, DEST, full_s=600.0, approach=True,
                             divert={"at_s": 1500.0, "lat": 52.95,
                                     "lon": -63.6, "ident": "DIVB"},
                             pilot_reloads=False)
    assert result["reloads"] == [] and result["reloads_air"] == []
    codes = {c for _t, c in result["notices"]}
    assert "reload_offered" in codes
    assert result["state"] in ("flying", "arrived")
