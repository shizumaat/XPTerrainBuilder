"""New Zealand imagery: Toitū Te Whenua LINZ Basemaps (#1339).

The provider parses, is offered for New Zealand tiles only, expands its
URL with the stored API key at fetch time and never prints that key; the
retired NZ.lay is never offered and a tile whose textures say NZ is
offered LINZ.  No network: the key store is stubbed.
"""
import os
import sys

import pytest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DUMMY_KEY = "c01dummykey0123456789"


@pytest.fixture(scope="module")
def registry():
    old_cwd = os.getcwd()
    os.chdir(REPO_ROOT)
    for path in (os.path.join(REPO_ROOT, "src"),
                 os.path.join(REPO_ROOT, "Providers")):
        if path not in sys.path:
            sys.path.insert(0, path)
    try:
        import O4_Imagery_Utils as IMG

        if not (IMG.providers_dict and IMG.combined_providers_dict):
            IMG.initialize_extents_dict()
            IMG.initialize_color_filters_dict()
            IMG.initialize_providers_dict()
            IMG.initialize_combined_providers_dict()
        yield IMG
    finally:
        try:
            os.chdir(old_cwd)
        except OSError:
            os.chdir(REPO_ROOT)


@pytest.fixture
def stored_key(monkeypatch):
    import O4_Authenticated_Sessions as SESSIONS
    import O4_UI_Utils as UI

    monkeypatch.setattr(UI, "_secrets", set())
    monkeypatch.setattr(SESSIONS, "load_api_key",
                        lambda session_name: DUMMY_KEY if session_name == "linz_basemaps" else None)
    return DUMMY_KEY


def test_linz_parses_with_attribution_and_ceiling(registry):
    linz = registry.providers_dict["LINZ"]
    assert linz["grid_type"] == "webmercator" and linz["request_type"] == "tms"
    assert linz["max_zl"] == "20"
    assert linz["attribution"] == "CC BY 4.0 Toitū Te Whenua LINZ"
    assert linz["credential_kind"] == "api_key" and linz["session_name"] == "linz_basemaps"
    assert DUMMY_KEY not in open(os.path.join(REPO_ROOT, "Providers", "New_Zealand", "LINZ.lay"),
                                 encoding="utf-8").read()


def test_linz_is_listed_for_a_new_zealand_tile_only(registry):
    import O4_Imagery_Sources as SOURCES

    nz = [row["code"] for row in SOURCES.imagery_sources(tile=[-42, 173])]
    elsewhere = [row["code"] for row in SOURCES.imagery_sources(tile=[47, 11])]
    assert "LINZ" in nz and "LINZ" not in elsewhere
    assert "BI" in nz and "BI" in elsewhere                   # global sources stay
    assert "NZ" not in [row["code"] for row in SOURCES.imagery_sources()]


def test_url_expands_with_the_stored_key(registry, stored_key):
    url, _headers = registry.wmts_request(15, 32350, 20450, registry.providers_dict["LINZ"])
    assert url == ("https://basemaps.linz.govt.nz/v1/tiles/aerial/WebMercatorQuad/"
                   "15/32350/20450.webp?api=" + stored_key)


def test_no_stored_key_is_a_sign_in_error(registry, monkeypatch):
    import O4_Authenticated_Sessions as SESSIONS

    monkeypatch.setattr(SESSIONS, "load_api_key", lambda session_name: None)
    with pytest.raises(SESSIONS.LoginError, match="linz_basemaps"):
        registry.wmts_request(15, 0, 0, registry.providers_dict["LINZ"])


def test_the_key_never_reaches_a_log_line(registry, stored_key, capsys, monkeypatch):
    import O4_UI_Utils as UI
    from o4_engine.redaction import Redactor

    monkeypatch.setattr(UI, "verbosity", 3)
    url, _ = registry.wmts_request(15, 32350, 20450, registry.providers_dict["LINZ"])
    UI.vprint(3, "HTTP request issued :", url)
    UI.lvprint(0, url, {"Referer": url})
    printed = capsys.readouterr().out
    assert stored_key not in printed and "api=<api_key>" in printed
    # The failure report's own redactor drops it too (a log read later).
    assert stored_key not in "\n".join(Redactor().lines([url]))


def test_linz_signs_in_through_the_provider_accounts(registry):
    import O4_Authenticated_Sessions as SESSIONS

    definitions = SESSIONS.account_definitions()
    linz = [d for d in definitions if d.get("code") == "LINZ"]
    assert linz and SESSIONS.credential_kind(linz[0]) == SESSIONS.CREDENTIAL_KIND_API_KEY
    assert [s.split(" ")[0] for s in SESSIONS.setup_steps(linz[0])][:1] == ["Open"]


def test_a_tile_built_from_nz_is_offered_linz(registry, tmp_path):
    import O4_Tile_Info as TINFO

    assert registry.providers_dict["NZ"]["in_GUI"] is False
    (tmp_path / "textures").mkdir()
    (tmp_path / "textures" / "32352_20448_NZ17.dds").write_bytes(b"")
    assert TINFO._detected_imagery(str(tmp_path)) == ("LINZ", 17)
