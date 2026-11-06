"""THE RE-CUT RULE carries max(one inset pixel, 10 m) of slack (owner
2026-11-06T00:12Z; ruled 00:33Z "yes, up to 10m is fine").

A required window that drifted a few metres with code changes is still
served by the cached raster when it lies within that slack of the cut
window; a window further outside is stale.  Measured on the corpus:
SBSP's SDNI / SDTB (Copernicus 30 m) drifted 0.01-0.06 px and were called
stale; EGLL's EGKN / EGLB / EGTF (England 1 m lidar) drifted 1.3-4.7 px.
"""
import json

import O4_Airport_Elevation_Insets as INSETS
import O4_File_Names as FNAMES

CUT = (-0.108580, 51.296433, -0.083421, 51.314449)


def _manifest(tmp_path, monkeypatch, resolution_m):
    path = tmp_path / "X_prov.json"
    path.write_text(json.dumps({"requested_bounding_box_wgs84": list(CUT),
                                "resolution_m": resolution_m}))
    monkeypatch.setattr(FNAMES, "airport_inset_provenance",
                        lambda *_a, **_k: str(path))


def _north(metres):
    w, s, e, n = CUT
    return (w + 1e-5, s, e - 1e-5, n + metres / 111320.0)


def test_drift_inside_one_pixel_is_current(tmp_path, monkeypatch):
    _manifest(tmp_path, monkeypatch, 30.0)
    assert not INSETS.inset_recut_is_needed(51, -1, "X", "c", _north(4.8))


def test_ten_metre_slack_on_fine_lidar(tmp_path, monkeypatch):
    _manifest(tmp_path, monkeypatch, 1.0)          # EGKN: 1 m lidar, 4.8 m
    assert INSETS.INSET_RECUT_SLACK_M == 10.0
    assert not INSETS.inset_recut_is_needed(51, -1, "X", "c", _north(4.8))
    assert not INSETS.inset_recut_is_needed(51, -1, "X", "c", _north(9.9))
    assert INSETS.inset_recut_is_needed(51, -1, "X", "c", _north(10.5))


def test_coarse_pixel_wins_over_ten_metres(tmp_path, monkeypatch):
    _manifest(tmp_path, monkeypatch, 30.0)
    assert not INSETS.inset_recut_is_needed(51, -1, "X", "c", _north(25.0))
    assert INSETS.inset_recut_is_needed(51, -1, "X", "c", _north(31.0))


def test_unjudgeable_pixel_still_has_ten_metres(tmp_path, monkeypatch):
    _manifest(tmp_path, monkeypatch, None)
    assert INSETS._inset_pixel_degrees(51, -1, "X", "c") == (0.0, 0.0)
    assert not INSETS.inset_recut_is_needed(51, -1, "X", "c", _north(5.0))
    assert INSETS.inset_recut_is_needed(51, -1, "X", "c", _north(11.0))


def test_lon_pixel_widens_with_latitude(tmp_path, monkeypatch):
    _manifest(tmp_path, monkeypatch, 30.0)
    lon_deg, lat_deg = INSETS._inset_pixel_degrees(51, -1, "X", "c")
    assert abs(lat_deg - 30.0 / 111320.0) < 1e-12
    assert 1.5 < lon_deg / lat_deg < 1.7          # 1 / cos(51.3 deg)
