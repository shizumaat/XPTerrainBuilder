"""A rebuild asks elevation providers only when there is a reason (owner 2026-11-04).

Two rules, twinned here end to end through ``ensure_airport_insets``:

* THE RECHECK AGE (``elevation_access.recheck``): a recorded answer is
  asked again past ``elevation_recheck_days`` or when the provider's own
  version moves -- never because the engine's did
  (``test_airport_elevation_insets`` holds the negative-record door).
* THE 24-HOUR REST (``elevation_access.refusal_rest``): a provider that
  REFUSED a query (IGN's WFS answered HTTP 400 to every FRANCE50CM query,
  41 times in one run) is not asked again for a day, by any airport, and
  says so in ONE line.  A network failure is not a refusal.

No network: ``requests.get`` is stubbed.
"""

import datetime
import json
import os

import O4_Airport_Elevation_Insets as INSETS
import O4_File_Names as FNAMES
import O4_UI_Utils as UI
import pytest
from elevation_access import base as ea_base
from elevation_access import recheck as ea_recheck
from elevation_access import refusal_rest as REST
from tests.inset_code import patch_inset_code
from tests.test_provider_query_error import (_WFS_DEFINITION, _response,
                                             _stub_get)
from elevation_access import registry as ea_registry

#: three airports of one tile, all inside the provider's box
_BOXES = {"LFAA": (2.30, 49.00, 2.36, 49.05),
          "LFBB": (2.50, 49.00, 2.56, 49.05),
          "LFCC": (2.70, 49.40, 2.76, 49.45)}


def _discovery_only(monkeypatch):
    patch_inset_code(monkeypatch, "has_gdal", True)
    patch_inset_code(
        monkeypatch, "fetch_inset",
        lambda definition, box, *_a, **_k: ea_registry.ACCESS_STRATEGIES[
            definition["access_strategy"]]().discover(definition, box))


def _lines(monkeypatch):
    lines = []
    monkeypatch.setattr(UI, "vprint", lambda level, *a: lines.append(
        " ".join(str(x) for x in a)))
    return lines


def test_a_refusing_provider_is_asked_once_a_day(tmp_path, monkeypatch):
    monkeypatch.setattr(FNAMES, "Elevation_dir", str(tmp_path))
    _discovery_only(monkeypatch)
    lines = _lines(monkeypatch)
    seen = _stub_get(monkeypatch, lambda url: _response(400, url=url))
    index = INSETS.ensure_airport_insets(
        49, 2, dict(_BOXES), [_WFS_DEFINITION], 3.0)
    # ONE request: the first asking goes alone, the others hear the rest.
    first = len(seen)
    assert first == 1, seen
    for icao in _BOXES:                       # never a durable negative
        assert index.get(icao, {}).get("WFSPROVIDER") != INSETS.NO_COVERAGE
    rest = [line for line in lines if "not asked again" in line]
    assert len(rest) == 1 and "WFSPROVIDER" in rest[0], lines
    # The next build of the day asks nothing at all.
    INSETS.ensure_airport_insets(49, 2, dict(_BOXES), [_WFS_DEFINITION], 3.0)
    assert len(seen) == first
    # The rest is on disk: another process (a new build) honours it.
    with open(os.path.join(str(tmp_path), "provider_refusals.json"),
              encoding="utf-8") as handle:
        stored = json.load(handle)
    assert "WFSPROVIDER" in stored and "HTTP 400" in stored[
        "WFSPROVIDER"]["reason"]
    monkeypatch.setattr(REST, "_MEMORY", {})
    monkeypatch.setattr(REST, "_LOADED_FROM", [None])
    assert REST.resting_refusal("WFSPROVIDER") is not None
    # A day later the provider is asked again.
    later = stored["WFSPROVIDER"]["at"] + REST.REST_S + 1
    assert REST.resting_refusal("WFSPROVIDER", now=later) is None


def test_a_network_failure_is_not_a_refusal(tmp_path, monkeypatch):
    import requests

    monkeypatch.setattr(FNAMES, "Elevation_dir", str(tmp_path))
    _discovery_only(monkeypatch)

    def _down(url, timeout=None, **_kwargs):
        raise requests.ConnectionError("no route to host")

    monkeypatch.setattr(requests, "get", _down)
    INSETS.ensure_airport_insets(
        49, 2, {"LFAA": _BOXES["LFAA"]}, [_WFS_DEFINITION], 3.0)
    assert REST.resting_refusal("WFSPROVIDER") is None


def test_what_counts_as_a_refusal():
    assert REST.is_refusal(ea_base.ProviderQueryError("400", status=400))
    envelope = ea_base.TransientFetchError("a 200 error envelope")
    envelope.server_answered = True
    assert REST.is_refusal(envelope)
    assert not REST.is_refusal(ea_base.TransientFetchError("timed out"))
    assert not REST.is_refusal(ea_base.ProviderUnavailable("no LERC"))


def test_the_classifier_marks_server_answers_only():
    from elevation_access import discovery as ea_discovery

    with pytest.raises(ea_base.TransientFetchError) as raised:
        ea_discovery.discovery_json_payload(_response(503), "listing")
    assert raised.value.server_answered is True
    with pytest.raises(ea_base.TransientFetchError) as raised:
        ea_discovery.discovery_listing_items({"message": "boom"}, "listing")
    assert raised.value.server_answered is True
    with pytest.raises(ea_base.TransientFetchError) as raised:
        ea_discovery.raise_transient_discovery_failure("request", "timeout")
    assert raised.value.server_answered is False


def test_the_recheck_age():
    today = datetime.date(2026, 11, 4)
    assert not ea_recheck.is_due("2026-10-05", days=30, today=today)
    assert ea_recheck.is_due("2026-10-04", days=30, today=today)
    assert not ea_recheck.is_due(None, days=30, today=today)
    assert not ea_recheck.is_due("not a date", days=30, today=today)


def test_the_provider_version_is_the_question_asked():
    base = {"code": "X", "url": "https://a", "zones": frozenset("abcdef"),
            "priority": 90.0, "enabled": True}
    version = ea_recheck.provider_version(base, [], 2)
    # Stable: a set's iteration order is not part of it.
    assert version == ea_recheck.provider_version(
        dict(base, zones=frozenset("fedcba")), [], 2)
    # The user's ranking and switch are not the question.
    assert version == ea_recheck.provider_version(
        dict(base, priority=1.0, enabled=False), [], 2)
    # The endpoint, the run's capabilities and the query law are.
    assert version != ea_recheck.provider_version(
        dict(base, url="https://b"), [], 2)
    assert version != ea_recheck.provider_version(base, ["lerc"], 2)
    assert version != ea_recheck.provider_version(base, [], 3)
