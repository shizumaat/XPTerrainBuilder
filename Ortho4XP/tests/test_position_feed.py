"""Twin of ``o4_engine.position_feed`` (World spec §5.1): ONE Web API
position reader, shared; served from the last read while it is young,
fanned out to subscribers, read like a ``PositionReader``."""
from __future__ import annotations

from o4_engine import position_feed as FEED


class FakeReader:
    def __init__(self):
        self.reads, self.resets, self.error = 0, 0, ""

    def read(self):
        self.reads += 1
        return {"lat": 53.0 + self.reads, "lon": -61.0, "cam_lat": 53.5,
                "cam_lon": -61.5}


def test_one_read_per_period_fanned_out():
    now = [100.0]
    reader = FakeReader()
    feed = FEED._PositionFeed(reader, max_age_s=0.5, clock=lambda: now[0])
    seen = []
    stop = feed.subscribe(seen.append)
    first = feed.read()
    assert feed.read() is first and reader.reads == 1     # served again
    now[0] += 0.6
    second = feed.read()
    assert reader.reads == 2 and second["lat"] == 55.0
    assert [r["lat"] for r in seen] == [54.0, 55.0]
    stop()
    now[0] += 1.0
    feed.read()
    assert len(seen) == 2                                  # unsubscribed
    assert feed.latest(max_age_s=5.0)["lat"] == 56.0
    now[0] += 10.0
    assert feed.latest(max_age_s=5.0) is None
    assert feed.resets == 0 and feed.error == ""


def test_a_failing_subscriber_never_stops_the_feed():
    feed = FEED._PositionFeed(FakeReader(), max_age_s=0.0)

    def boom(_rec):
        raise RuntimeError("subscriber")
    feed.subscribe(boom)
    assert feed.read()["lat"] == 54.0


def test_shared_is_one_feed_per_base(monkeypatch):
    import O4_XPlane_WebAPI as WEBAPI
    monkeypatch.setattr(FEED, "_FEEDS", {})
    monkeypatch.setattr(WEBAPI, "PositionReader", lambda base: FakeReader())
    one = FEED.shared("http://127.0.0.1:8086/api/v2")
    assert FEED.shared("http://127.0.0.1:8086/api/v2") is one
    assert FEED.shared("http://127.0.0.1:8087/api/v2") is not one
    assert FEED.latest_position() is None
    one.read()
    assert FEED.latest_position() == WEBAPI.camera_position(one.latest())
