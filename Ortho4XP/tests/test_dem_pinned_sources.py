"""drop_missing_pinned_files: stale absolute custom_dem pins must fall
back to default sources loudly instead of reaching the DEM loader
(where they error and the build proceeds on a zero/garbage base)."""

import sys

sys.path.insert(0, "src")

import O4_DEM_Utils as DEM


def test_missing_absolute_pin_is_dropped(tmp_path):
    missing = str(tmp_path / "gone" / "N46E006.hgt")
    assert DEM.drop_missing_pinned_files(missing) == ""


def test_existing_pin_and_source_names_pass_through(tmp_path):
    existing = tmp_path / "N46E006.hgt"
    existing.write_bytes(b"x")
    source = "%s;SRTM" % existing
    assert DEM.drop_missing_pinned_files(source) == source
    assert DEM.drop_missing_pinned_files("COPERNICUSGLO30") == "COPERNICUSGLO30"
    assert DEM.drop_missing_pinned_files("") == ""


def test_mixed_list_keeps_survivors(tmp_path):
    existing = tmp_path / "ok.tif"
    existing.write_bytes(b"x")
    source = "%s;%s" % (tmp_path / "gone.hgt", existing)
    assert DEM.drop_missing_pinned_files(source) == str(existing)
