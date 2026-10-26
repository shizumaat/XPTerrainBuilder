"""Twins for the synthetic airport identifier (#1353, owner ruling
2026-10-26): every airport of the tile list has an identifier -- its code,
else ``O4_Airport_Apt_Identity.synthetic_airport_id`` of its position --
so no pass keyed by code skips it.  Synthetic dictionaries only."""
import os
import subprocess
import sys
import types

import O4_Airport_Apt_Identity as ID
import O4_Airport_Elevation_Insets as INSETS
import O4_Airport_Modes as MODES
import O4_Airport_Utils as APT
import O4_Geo_Utils as GEO
from shapely import affinity, geometry

#: A cell centre (cells are centred on 0.001 degree multiples), so a 10 m
#: move cannot cross a cell edge: the property pinned is "metres move
#: nothing".
LON, LAT = -121.594, 43.674


def _record(key_type, name, boundary=None, repr_node=(LON, LAT)):
    return {"key_type": key_type, "name": name, "repr_node": repr_node,
            "boundary": boundary, "runway": [], "runway_as_rel": [],
            "taxiway": [], "apron": [], "hangar": []}


def _field(lon=LON, lat=LAT, half_m=300.0):
    dx = half_m / GEO.lon_to_m(lat)
    dy = half_m / GEO.lat_to_m
    return geometry.box(lon - dx, lat - dy, lon + dx, lat + dy)


def _only_key(dico):
    (key,) = dico
    return key


def test_id_is_deterministic_across_runs():
    here = ID.synthetic_airport_id(LON, LAT)
    code = ("import sys; sys.path.insert(0, %r); import O4_Airport_Apt_Identity"
            " as ID; print(ID.synthetic_airport_id(%r, %r))"
            % (os.path.dirname(os.path.abspath(ID.__file__)), LON, LAT))
    for seed in ("0", "1234"):
        out = subprocess.run(
            [sys.executable, "-c", code], capture_output=True, text=True,
            env={**os.environ, "PYTHONHASHSEED": seed}, check=True).stdout.strip()
        assert out.splitlines()[-1] == here
    assert here.startswith("X") and len(here) == 8 and here.isalnum()


def test_id_survives_a_10_m_node_shift():
    shift_lon = 10.0 / GEO.lon_to_m(LAT)
    shift_lat = 10.0 / GEO.lat_to_m
    field = _field()
    moved = affinity.translate(field, shift_lon, shift_lat)
    corners = list(field.exterior.coords)
    corners[0] = (corners[0][0] + shift_lon, corners[0][1] + shift_lat)
    corners[-1] = corners[0]
    one_node = geometry.Polygon(corners)
    ids = set()
    for boundary in (field, moved, one_node):
        dico = {"Field": _record("name", "Field", boundary)}
        ID.assign_synthetic_ids(dico)
        ids.add(_only_key(dico))
    for node in ((LON, LAT), (LON + shift_lon, LAT - shift_lat)):
        dico = {node: _record("repr_node", "****", repr_node=node)}
        ID.assign_synthetic_ids(dico)
        ids.add(_only_key(dico))
    assert ids == {ID.synthetic_airport_id(LON, LAT)}


def test_id_never_takes_a_real_or_tile_code():
    base = ID.synthetic_airport_id(LON, LAT)
    dico = {(LON, LAT): _record("repr_node", "****"),
            "Same Cell Strip": _record("name", "Same Cell Strip",
                                       repr_node=(LON + 1e-5, LAT)),
            "KXYZ": _record("icao", "Real")}
    given = ID.assign_synthetic_ids(dico, known_codes={base.lower()})
    assert base not in dico and len(set(given)) == 2
    assert all(code.startswith(base) and code != base for code in given)
    assert "KXYZ" in dico and dico["KXYZ"]["key_type"] == "icao"
    # 8+ characters: never a 3-7 character apt.dat code, never "ICAO".
    for code in given:
        assert len(code) >= 8 and not MODES.mode_admits(code, "ICAO")


def test_unnamed_aerodrome_is_named_and_listed(capsys, monkeypatch):
    dico = {(LON, LAT): _record("repr_node", "****"),
            "Fall Field": _record("name", "Fall Field", _field(LON + 0.2))}
    ID.assign_synthetic_ids(dico)
    assert all(isinstance(key, str) for key in dico)
    names = {record["name"] for record in dico.values()}
    assert names == {"Fall Field", "Unnamed airstrip (43.6740, -121.5940)"}
    assert {r["key_type"] for r in dico.values()} == {ID.SYNTHETIC_KEY_TYPE}
    lines = []
    monkeypatch.setattr(APT.UI, "vprint",
                        lambda level, *args: lines.append(" ".join(
                            str(a) for a in args)))
    for record in dico.values():
        record["runway"] = [None, [], []]
    APT.list_airports_and_runways(dico)
    assert not any("****" in line for line in lines)
    assert all(any(key in line for line in lines) for key in dico)


def test_unnamed_aerodrome_gets_inset_and_patch_selection_under_all(
        monkeypatch):
    tile = types.SimpleNamespace(lat=43, lon=-122,
                                 airport_elevation_inset_margin_m=500.0)
    dico = {(LON, LAT): _record("repr_node", "****")}
    ID.assign_synthetic_ids(dico)
    code = _only_key(dico)
    # The chain's last step makes the boundary tile-relative.
    dico[code]["boundary"] = affinity.translate(_field(), -tile.lon,
                                                -tile.lat)
    assert MODES.inset_keys(dico, "All") == [code]
    assert MODES.inset_keys(dico, "ICAO") == []
    lines = []
    monkeypatch.setattr(INSETS.UI, "vprint",
                        lambda level, *args: lines.append(" ".join(
                            str(a) for a in args)))
    boxes = INSETS._airport_bounding_boxes(
        tile, dico, only=MODES.inset_keys(dico, "All"))
    assert list(boxes) == [code]
    assert not any("unnamed" in line for line in lines)
    # The patch set's mode predicate (auto_patch.selection) is the same.
    assert MODES.mode_admits(code, "All")
    assert not MODES.mode_admits(code, "ICAO")
