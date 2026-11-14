"""_core_airports counts a planned-airports mapping (EGNS on 1.0.513:
``int()`` of ``{icao: None}`` raised and failed the tile's imagery step)."""
import types

from o4_engine import session


def _on_demand(monkeypatch):
    import O4_Imagery_Placeholder as PLACEHOLDER
    monkeypatch.setattr(PLACEHOLDER, "drop", lambda tile: True)


def test_a_mapping_of_planned_airports_is_counted(monkeypatch):
    _on_demand(monkeypatch)
    tile = types.SimpleNamespace(lat=54, lon=-5)
    assert session._core_airports(tile, {"EGNS": None, "EGNR": None}) == 2


def test_a_count_and_none_still_work(monkeypatch):
    _on_demand(monkeypatch)
    tile = types.SimpleNamespace(lat=54, lon=-5)
    assert session._core_airports(tile, 3) == 3
    assert session._core_airports(tile, {}) == 1
