"""Twin of ``src/o4_engine/fly_here.py`` (#2020): the facts behind the Fly
pane's "Preparing imagery at ..." with no plan -- the airport near the
aircraft, the full-detail squares around it as installed, the reload
offer -- and their road to ``WorldStatus.here``.  Offline, on
``tmp_path``; no airport is named by the code under test."""
from __future__ import annotations

import os

import O4_DDS_File as DDS
import O4_DDS_Tiers as TIERS
import O4_Geo_Utils as GEO
import O4_World_Pack as WP
from o4_engine import events as EV
from o4_engine import fly_here as HERE
from o4_engine import reload_offer as RELOAD
from o4_engine import world_commands as WORLD

AT = (53.3192, -60.4258)
ROWS = (("PAD1", 53.3200, -60.4260, "heliport"),
        ("FAR1", 53.4500, -60.4258, "icao_airport"),      # ~14.5 km north
        ("NEAR", 53.3300, -60.4100, "icao_airport"),
        ("STRP", 53.3260, -60.4200, "airport"))


def _dds(width: int) -> bytes:
    count = DDS.full_mip_count(width, width)
    levels = [b"\0" * DDS.level_size(w, h, "bc1")
              for w, h in DDS.mip_dims(width, width, count)]
    return DDS.assemble(width, width, "bc1", levels)


def _square_at(lat, lon, zl=16):
    x, y = GEO.wgs84_to_gtile(lat, lon, zl)
    return x // 16 * 16, y // 16 * 16


def test_the_nearest_airport_within_reach_heliports_last():
    assert HERE.nearest_airport(*AT, rows=ROWS) == "STRP"
    assert HERE.nearest_airport(*AT, rows=ROWS[:2]) == "PAD1"
    assert HERE.nearest_airport(*AT, rows=ROWS[1:2]) == ""
    assert HERE.nearest_airport(*AT, rows=()) == ""


def test_the_core_squares_around_the_aircraft_and_how_many_are_sharp(tmp_path):
    folder = tmp_path / "textures"
    folder.mkdir()
    x, y = _square_at(*AT)
    near = [(x, y), (x + 16, y), (x, y + 16)]
    far = (x + 16 * 6, y)
    for i, (sx, sy) in enumerate(near + [far]):
        width = TIERS.FULL_WIDTH if i == 0 else 64
        (folder / ("%d_%d_BI16.dds" % (sy, sx))).write_bytes(_dds(width))
    total, sharp = HERE.core_counts([str(folder)], *AT)
    assert sharp == 1 and 1 <= total <= len(near)
    assert HERE.core_counts([], *AT) == (0, 0)


def test_describe_adds_the_facts_and_none_stays_none(tmp_path, monkeypatch):
    scenery = tmp_path / "Custom Scenery"
    tile = WP.tile_name(53, -61)
    textures = scenery / WP.PACK_NAME / "textures" / tile
    textures.mkdir(parents=True)
    x, y = _square_at(*AT)
    (textures / ("%d_%d_BI16.dds" % (y, x))).write_bytes(_dds(TIERS.FULL_WIDTH))
    monkeypatch.setattr(HERE, "_airports", lambda: ROWS)
    monkeypatch.setitem(RELOAD._STATE, "offer", "tiles")
    assert HERE.describe(None, str(scenery)) is None
    job = {"tile": tile, "lat": AT[0], "lon": AT[1], "on_ground": True,
           "kind": "drape", "job": "swapped", "elapsed_s": 0,
           "estimate_s": 0, "core": True}
    out = HERE.describe(job, str(scenery))
    assert out["airport"] == "STRP" and out["reload_offer"] == "tiles"
    assert (out["squares"], out["sharp"]) == (1, 1)
    assert {k: out[k] for k in job} == job
    # The event carries it to both apps.
    event = WORLD.status_event(str(scenery), here=out)
    assert isinstance(event, EV.WorldStatus) and event.here == out


def test_a_fact_that_cannot_be_read_stays_empty(tmp_path, monkeypatch):
    def broken():
        raise OSError("no index")
    monkeypatch.setattr(HERE, "_airports", broken)
    monkeypatch.setitem(RELOAD._STATE, "offer", "")
    out = HERE.describe({"tile": "+53-061", "lat": AT[0], "lon": AT[1]},
                        str(tmp_path / "none"))
    assert (out["airport"], out["squares"], out["sharp"],
            out["reload_offer"]) == ("", 0, 0, "")
    assert not os.path.exists(tmp_path / "none")
