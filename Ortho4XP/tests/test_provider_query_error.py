"""A REFUSED discovery query is a provider error, never no-coverage (#1328).

FRANCE50CM's WFS tile index answered HTTP 400 at LFPG (#1220) and LFSB
(#1328), and ``discovery_json_payload`` recorded that as a durable
``no-coverage``: France's 50 cm lidar was written off for those airports
for good.  The law now: 404 / 410 and a well-formed empty answer are the
only durable negatives; any other 4xx raises ``ProviderQueryError`` (a
``ProviderUnavailable``, so the index records ``unavailable:<reason>``
and the next run asks again), and a ``no-coverage`` stamped before that
law is re-probed once.  No network: ``requests.get`` is stubbed.
"""

import json
import os
import types

import O4_Airport_Elevation_Insets as INSETS
import O4_File_Names as FNAMES
import O4_UI_Utils as UI
import pytest
from elevation_access import base as ea_base
from elevation_access import definitions as ea_definitions
from elevation_access import discovery as ea_discovery
from elevation_access import registry as ea_registry
from tests.inset_code import patch_inset_code

_WFS_DEFINITION = {
    "code": "WFSPROVIDER",
    "access_strategy": "wfs_tile_index",
    "role": ea_definitions.ROLE_AIRPORT_INSET,
    "wfs_service_url": "https://wfs.invalid/wfs/ows?apikey=SECRET123",
    "wfs_type_name": "LAYER:dalle",
    "url_property": "url",
    "coverage_bbox": (-5.2, 41.3, 9.6, 51.1),
}
_LFSB_BOX = (7.50, 47.57, 7.56, 47.62)


def _response(status, payload=None, url="https://wfs.invalid/q"):
    return types.SimpleNamespace(
        status_code=status, url=url,
        json=lambda: payload if payload is not None else {})


def _stub_get(monkeypatch, response):
    import requests

    seen = []

    def _get(url, timeout=None, **_kwargs):
        seen.append(url)
        return response(url) if callable(response) else response

    monkeypatch.setattr(requests, "get", _get)
    return seen


def _discover():
    strategy = ea_registry.ACCESS_STRATEGIES["wfs_tile_index"]()
    return strategy.discover(_WFS_DEFINITION, _LFSB_BOX)


@pytest.mark.parametrize("status", [400, 403])
def test_a_refused_tile_index_query_is_a_provider_error(monkeypatch, status):
    lines = []
    monkeypatch.setattr(UI, "vprint", lambda level, *a: lines.append(
        " ".join(str(x) for x in a)))
    _stub_get(monkeypatch, lambda url: _response(status, url=url))
    with pytest.raises(ea_base.ProviderQueryError) as raised:
        _discover()
    error = raised.value
    assert isinstance(error, ea_base.ProviderUnavailable)
    assert error.status == status
    # Logged loudly, with the query but never the credential.
    assert "LAYER%3Adalle" in error.url or "LAYER:dalle" in error.url
    assert "SECRET123" not in error.url
    assert "SECRET123" not in error.reason
    loud = [line for line in lines if "REFUSED" in line]
    assert loud and "HTTP %d" % status in loud[0]
    assert "SECRET123" not in loud[0]
    assert "NOT recorded as no-coverage" in loud[0]


@pytest.mark.parametrize("status", [404, 410])
def test_absent_stays_a_durable_negative(monkeypatch, status):
    _stub_get(monkeypatch, _response(status))
    assert _discover() is None


def test_an_empty_valid_answer_stays_a_durable_negative(monkeypatch):
    _stub_get(monkeypatch, _response(
        200, {"type": "FeatureCollection", "features": []}))
    assert _discover() is None


def test_a_valid_listing_is_delivered(monkeypatch):
    _stub_get(monkeypatch, _response(200, {"features": [
        {"properties": {"url": "https://wfs.invalid/t.tif",
                        "name": "t1"}}]}))
    assert _discover() == [{"url": "https://wfs.invalid/t.tif",
                            "name": "t1"}]


def test_url_without_credentials():
    clean = ea_discovery.url_without_credentials(
        "https://bob:hunter2@host.invalid/p?apikey=K1&access_token=T2"
        "&X-Amz-Signature=S3&TYPENAMES=A:b&bbox=1,2,3,4")
    for secret in ("bob", "hunter2", "K1", "T2", "S3"):
        assert secret not in clean
    assert clean.startswith("https://host.invalid/p?")
    assert "TYPENAMES=A:b" in clean and "bbox=1,2,3,4" in clean
    assert "apikey=<redacted>" in clean


# ---------------------------------------------------------------------
# Records already written by a refused query are not durable on read.
# ---------------------------------------------------------------------
_PLAIN = dict(_WFS_DEFINITION, coverage_bbox=(-180.0, -90.0, 180.0, 90.0))


def _negative(stamp):
    record = {"WFSPROVIDER": INSETS.NO_COVERAGE,
              "bounding_box": list(_LFSB_BOX)}
    if stamp is not None:
        record["capabilities"] = {"WFSPROVIDER": stamp}
    return record


def test_a_negative_from_before_the_law_is_not_durable(monkeypatch):
    monkeypatch.setattr(INSETS, "_engine_version", lambda: "9.9.9")
    for stamp in (None,
                  {"engine": "9.9.9", "capabilities": []},
                  {"engine": "9.9.9", "capabilities": [],
                   "negative_law": 1}):
        record = _negative(stamp)
        assert INSETS.negative_predates_query_law(record, "WFSPROVIDER")
        # Same engine version, still re-asked: the law is the witness.
        assert INSETS.negative_is_version_stale(
            record, "WFSPROVIDER", _PLAIN)
    current = _negative(INSETS.run_capability_record(_PLAIN))
    assert current["capabilities"]["WFSPROVIDER"]["negative_law"] == (
        INSETS.NEGATIVE_LAW)
    assert not INSETS.negative_predates_query_law(current, "WFSPROVIDER")
    assert not INSETS.negative_is_version_stale(
        current, "WFSPROVIDER", _PLAIN)


def test_a_gated_negative_from_before_the_law_is_unverified():
    gated = dict(_PLAIN, asset_compression="lerc")
    record = _negative({"engine": "1.0", "capabilities": ["lerc"]})
    assert INSETS.negative_is_unverified(record, "WFSPROVIDER", gated)
    record["capabilities"]["WFSPROVIDER"]["negative_law"] = (
        INSETS.NEGATIVE_LAW)
    assert not INSETS.negative_is_unverified(record, "WFSPROVIDER", gated)


def test_a_refused_query_is_recorded_unavailable_not_no_coverage(
    tmp_path, monkeypatch
):
    """End to end through ``ensure_airport_insets``: the old 400 negative
    on disk is re-probed once, the provider refuses the query again, and
    the record becomes ``unavailable:`` -- asked again next run."""
    monkeypatch.setattr(FNAMES, "Elevation_dir", str(tmp_path))
    patch_inset_code(monkeypatch, "has_gdal", True)
    # The fetch stops at discovery (no GDAL in the cloud / CI runners):
    # the refusal is raised exactly where the real fetch would raise it.
    patch_inset_code(
        monkeypatch, "fetch_inset",
        lambda definition, box, *_a, **_k: ea_registry.ACCESS_STRATEGIES[
            definition["access_strategy"]]().discover(definition, box))
    index_path = FNAMES.airport_inset_index(47, 7)
    os.makedirs(os.path.dirname(index_path), exist_ok=True)
    with open(index_path, "w", encoding="utf-8", newline="") as handle:
        json.dump({"LFSB": _negative(
            {"engine": INSETS.engine_version(), "capabilities": []})},
            handle)
    seen = _stub_get(monkeypatch, lambda url: _response(400, url=url))
    index = INSETS.ensure_airport_insets(
        47, 7, {"LFSB": _LFSB_BOX}, [_WFS_DEFINITION], 3.0)
    assert seen, "the pre-law negative was not re-probed"
    status = index["LFSB"]["WFSPROVIDER"]
    assert status != INSETS.NO_COVERAGE
    assert INSETS.status_is_unavailable(status), status
    assert "HTTP 400" in status
