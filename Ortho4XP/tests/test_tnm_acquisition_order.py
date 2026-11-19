"""RULINGS 2026-11-19g -- a 3DEP mosaic lays the newest GROUND on top.

The order is the ACQUISITION date (FGDC ``timeperd`` beside the raster,
else the year in the project name), publication date the tie-break.
KORD's case in miniature: a project named 2016 (flown 2017, published
2024) over the earthworks, and IL_MidNorth_D22 (flown 2022, published
2023) flat; the D22 heights must win.  No network: the metadata reader
is a stub.
"""

import numpy
from elevation_access import acquisition_order as AO
from tests.test_round13_border_fetch import (
    BBOX,
    DEFINITION,
    _local_strategy,
    _source,
    _values_of,
    requires_gdal,
)

OLD_DIR = ("https://prd-tnm.s3.amazonaws.com/StagedProducts/Elevation/1m/"
           "Projects/IL_4_County_QL1_LiDAR_2016_B16")
NEW_DIR = ("https://prd-tnm.s3.amazonaws.com/StagedProducts/Elevation/1m/"
           "Projects/IL_MidNorth_D22")


def _fgdc(begin, end):
    return ("<metadata><idinfo><timeperd><timeinfo><rngdates>"
            "<begdate>%s</begdate><enddate>%s</enddate>"
            "</rngdates></timeinfo></timeperd></idinfo>"
            "<dataqual><srcinfo><srctime><timeinfo><sngdate>"
            "<caldate>20240101</caldate></sngdate></timeinfo></srctime>"
            "</srcinfo></dataqual></metadata>" % (begin, end))


KORD_METADATA = {
    OLD_DIR + "/metadata/USGS_1M_16_x42y465_IL_4_County_QL1_LiDAR_2016_B16"
    ".xml": _fgdc("20170416", "20170507"),
    NEW_DIR + "/metadata/USGS_1M_16_x42y465_IL_MidNorth_D22.xml":
        _fgdc("20220321", "20220628"),
}


def _kord_pair():
    old = {"title": "USGS 1 Meter 16 x42y465 IL_4_County_QL1_LiDAR_2016_B16",
           "publication_date": "2024-11-18", "source_id": "old",
           "download_url": OLD_DIR + "/TIFF/USGS_1M_16_x42y465_"
           "IL_4_County_QL1_LiDAR_2016_B16.tif"}
    new = {"title": "USGS 1 Meter 16 x42y465 IL_MidNorth_D22",
           "publication_date": "2023-10-31", "source_id": "new",
           "download_url": NEW_DIR + "/TIFF/USGS_1M_16_x42y465_"
           "IL_MidNorth_D22.tif"}
    return (old, new)


def test_the_fgdc_period_end_is_the_acquisition_not_a_later_source_date():
    assert AO._acquisition_date_from_fgdc(
        _fgdc("20220321", "20220628")) == "2022-06-28"
    assert AO._acquisition_date_from_fgdc("<metadata/>") is None
    assert AO._acquisition_date_from_fgdc(None) is None


def test_the_project_name_year_and_delivery_code():
    assert AO._year_from_project_name(
        "USGS 1 Meter 16 x42y465 IL_4_County_QL1_LiDAR_2016_B16") == "2016"
    assert AO._year_from_project_name(
        "USGS 1 Meter 16 x42y465 IL_MidNorth_D22") == "2022"
    assert AO._year_from_project_name("USGS 1 Meter 16 x42y465") is None


def test_newer_acquisition_beats_newer_publication():
    asked = []

    def read(url):
        asked.append(url)
        return KORD_METADATA.get(url)

    ordered = AO.order_newest_acquired(list(_kord_pair()), read)
    assert [s["source_id"] for s in ordered] == ["new", "old"]
    assert ordered[0]["acquisition_date"] == "2022-06-28"
    assert ordered[0]["acquisition_basis"] == "metadata"
    assert sorted(asked) == sorted(KORD_METADATA)       # once per project


def test_without_metadata_the_name_year_decides_and_publication_ties():
    ordered = AO.order_newest_acquired(list(_kord_pair()), lambda url: None)
    assert [s["source_id"] for s in ordered] == ["new", "old"]
    assert ordered[0]["acquisition_basis"] == "project_name"
    (a, b) = _kord_pair()
    b.update(title=a["title"], download_url=a["download_url"].replace(
        "x42y465", "x42y466"))
    ordered = AO.order_newest_acquired([b, a], lambda url: 1 / 0)
    assert [s["source_id"] for s in ordered] == ["old", "new"]   # 2024 > 2023


def test_a_single_project_listing_asks_no_metadata():
    (old, _new) = _kord_pair()
    twin = dict(old, source_id="twin", download_url=old[
        "download_url"].replace("x42y465", "x42y466"))
    AO.order_newest_acquired([old, twin], lambda url: 1 / 0)
    assert old["acquisition_basis"] == "project_name"


@requires_gdal
def test_the_mosaic_lays_the_newest_ground_on_top(tmp_path, monkeypatch):
    """The shipped fetch: the 2016-named project (published LATER) holds
    15 m mounds, D22 is flat; every pixel reads D22."""
    (old, new) = _kord_pair()
    mounds = _source(tmp_path, "old", numpy.full((40, 40), 216.9),
                     old["publication_date"], old["title"])
    flat = _source(tmp_path, "new", numpy.full((40, 40), 201.5),
                   new["publication_date"], new["title"])
    local = {old["download_url"]: mounds["download_url"],
             new["download_url"]: flat["download_url"]}
    mounds["download_url"] = old["download_url"]
    flat["download_url"] = new["download_url"]
    strategy = _local_strategy(monkeypatch, [mounds, flat])  # pub order
    monkeypatch.setattr(
        type(strategy), "_warp_input_for",
        lambda self, source: local[source["download_url"]])
    monkeypatch.setattr(AO, "_read_metadata_text", KORD_METADATA.get)
    destination = str(tmp_path / "KORD_usgs3dep.tif")
    provenance = strategy.fetch(DEFINITION, BBOX, 3000.0, destination)
    assert numpy.allclose(_values_of(destination), 201.5, atol=0.03)
    assert [e["source_id"] for e in provenance["sources_used"]] == [
        "new", "old"]
    assert provenance["acquisition_date"] == "2022-06-28"
