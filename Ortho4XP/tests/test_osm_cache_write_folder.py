"""The OSM cache write creates its folder (#1329).

The parallel-build cache warmer fetches a queued tile's OpenStreetMap
layers before that tile's build has created the tile's OSM folder, so
every warmed layer printed ``Could not open … for writing.`` and was
downloaded again by the build.  ``OSM_layer.write_to_file`` now creates
the missing folder itself, which covers every caller.  Headless: the
Overpass query and the regional-extract backend are stubbed; no network.
"""

from __future__ import annotations

import os
import sys
import types

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import O4_File_Names as FNAMES  # noqa: E402
import O4_OSM_Utils as OSM  # noqa: E402
import O4_UI_Utils as UI  # noqa: E402

_RESPONSE = (
    b'<?xml version="1.0" encoding="UTF-8"?>\n<osm version="0.6">\n'
    b'  <node id="1" lat="40.1" lon="-99.9"/>\n'
    b'  <node id="2" lat="40.2" lon="-99.8"/>\n'
    b'  <way id="10"><nd ref="1"/><nd ref="2"/>'
    b'<tag k="aeroway" v="runway"/></way>\n'
    b'</osm>\n'
)


@pytest.mark.parametrize("name", ["layer.osm", "layer.osm.bz2"])
def test_write_to_file_creates_a_missing_nested_folder(tmp_path, name):
    layer = OSM.OSM_layer()
    layer.update_dicosm(_RESPONSE, None, None)
    target = tmp_path / "not" / "yet" / name
    assert layer.write_to_file(str(target)) != 0
    assert target.is_file()
    reread = OSM.OSM_layer()
    reread.update_dicosm(str(target), None, None)
    assert len(reread.dicosmn) == 2


def test_warmer_fetch_lands_the_layer_in_a_tile_folder_not_yet_made(
    monkeypatch, tmp_path, capsys
):
    """The warmer's call: ``OSM_queries_to_OSM_layer`` with a cache suffix
    for a tile whose OSM folder the build has not created yet."""
    monkeypatch.setattr(FNAMES, "OSM_dir", str(tmp_path / "OSM_data"))
    monkeypatch.setattr(UI, "verbosity", 1)
    monkeypatch.setattr(UI, "red_flag", False)
    no_extracts = types.ModuleType("O4_OSM_Extracts")
    no_extracts.osm_xml_from_local_extracts = (
        lambda statements, bounding_box, request_description="": None)
    monkeypatch.setitem(sys.modules, "O4_OSM_Extracts", no_extracts)
    monkeypatch.setattr(
        OSM, "get_overpass_data", lambda *args, **kwargs: _RESPONSE)

    cached = FNAMES.osm_cached(40, -100, "airports")
    assert not os.path.isdir(os.path.dirname(cached))
    assert OSM.OSM_queries_to_OSM_layer(
        ['way["aeroway"="runway"]'], OSM.OSM_layer(), 40, -100,
        cached_suffix="airports") == 1
    assert os.path.isfile(cached)
    assert "Could not open" not in capsys.readouterr().out
