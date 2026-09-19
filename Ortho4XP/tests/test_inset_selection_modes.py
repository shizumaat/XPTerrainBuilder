"""The inset/patch mode vocabulary, its legacy values, and the TRUTHINESS hazard.

Spec ``docs/specs/insets-follow-patch-set-spec.md`` §E tests 3a/3c (engine
side of 3d lives in ``test_schema_snapshot.py``), ruled by RULINGS
2026-09-18b/c/e.

The hazard this file exists for: ``airport_elevation_insets`` was a BOOL
and both master gates read it with bare truthiness.  After the relabel the
Off value is the STRING ``"None"``, which is TRUTHY — left alone, Off would
have read as ON on every install that turned the feature off.
"""
from __future__ import annotations

import os
import sys
import types

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "src"))

import O4_Cfg_Vars                                     # noqa: E402
import O4_Settings_Model as SETTINGS                   # noqa: E402
from auto_patch.selection import (                     # noqa: E402
    MODES,
    inset_keys,
    mode_admits,
    normalize_mode,
    resolved_auto_patch_mode,
    resolved_inset_mode,
)


def _tile(**kw):
    return types.SimpleNamespace(**kw)


# ── mode_admits: THE one spelling ─────────────────────────────────────
@pytest.mark.parametrize("code,mode,expected", [
    ("LPMT", "ICAO", True),
    ("KDFW", "ICAO", True),
    ("LIS", "ICAO", False),          # 3-letter IATA key
    ("LP63", "ICAO", False),         # local_ref class
    ("PISTA DE LAVRE", "ICAO", False),   # NAME key — the 17-strip class
    ("LPMT", "All", True),
    ("LIS", "All", True),
    ("PISTA DE LAVRE", "All", True),
    ("LPMT", "None", False),
    ("LIS", "None", False),
    ("", "All", False),
])
def test_mode_admits_table(code, mode, expected):
    assert mode_admits(code, mode) is expected


# ── the legacy-value map (owner RULINGS 2026-09-18e) ──────────────────
@pytest.mark.parametrize("value,expected", [
    (True, "ICAO"), (False, "None"),
    ("True", "ICAO"), ("true", "ICAO"), ("1", "ICAO"),
    ("False", "None"), ("false", "None"), ("0", "None"),
    ("None", "None"), ("ICAO", "ICAO"), ("All", "All"),
    ("  ICAO  ", "ICAO"),
    (None, "ICAO"),                  # absent ⇒ default
])
def test_resolved_inset_mode_table(value, expected):
    assert resolved_inset_mode(_tile(airport_elevation_insets=value)) == expected


def test_garbage_warns_once_and_falls_back_to_icao():
    seen = []
    assert normalize_mode("Sometimes", "airport_elevation_insets",
                          warn=seen.append) == "ICAO"
    assert len(seen) == 1 and "Sometimes" in seen[0]


def test_auto_patch_legacy_map_is_unchanged():
    # auto_patch's own legacy map predates this spec and must not move:
    # True ⇒ All (not ICAO).
    assert resolved_auto_patch_mode(_tile(auto_patch=True)) == "All"
    assert resolved_auto_patch_mode(_tile(auto_patch=False)) == "None"
    assert resolved_auto_patch_mode(_tile(auto_patch="ICAO")) == "ICAO"


# ── THE TRUTHINESS HAZARD (spec rows 23-24) ───────────────────────────
def test_master_gate_reads_the_string_None_as_OFF():
    import O4_Airport_Elevation_Insets as INS

    assert INS.insets_enabled_for_tile(
        _tile(airport_elevation_insets="None")) is False
    # ...and the legacy bool keeps meaning exactly what it meant.
    assert INS.insets_enabled_for_tile(
        _tile(airport_elevation_insets=False)) is False


def test_smoothing_radius_gate_reads_the_string_None_as_OFF():
    import O4_Airport_Elevation_Insets as INS

    tile = _tile(airport_elevation_insets="None", apt_smoothing_pix=8,
                 apt_smoothing_auto=True)
    assert INS.resolve_airport_smoothing_radius(
        tile, "LPMT", None, {}, 30.0) == (8, None, None)


# ── inset_keys: the dico-key population ───────────────────────────────
def _dico():
    return {
        "LPMT": 1, "LPPT": 1, "LPCS": 1,       # 4-letter ICAO
        "LIS": 1, "OPO": 1,                    # IATA
        "LP63": 1,                             # local_ref (has a digit)
        "Pista de Lavre": 1,                   # NAME
        ("way", 12345): 1,                     # unnamed strip (tuple key)
    }


def test_inset_keys_by_mode():
    dico = _dico()
    assert sorted(inset_keys(dico, "ICAO")) == ["LPCS", "LPMT", "LPPT"]
    assert len(inset_keys(dico, "All")) == 7      # every STRING key
    assert inset_keys(dico, "None") == []


# ── the settings plumbing (§A.5) ──────────────────────────────────────
def test_registry_is_the_three_mode_enum():
    spec = O4_Cfg_Vars.cfg_vars["airport_elevation_insets"]
    assert spec["type"] is str
    assert spec["default"] == "ICAO"
    assert tuple(spec["values"]) == MODES
    assert spec["value_labels"]["None"] == "Off"


@pytest.mark.parametrize("text,expected", [
    ("True", "ICAO"), ("False", "None"), ("true", "ICAO"), ("0", "None"),
    ("ICAO", "ICAO"), ("All", "All"), ("None", "None"),
])
def test_coerce_maps_legacy_tokens(text, expected):
    (ok, normalized, error) = SETTINGS.coerce("airport_elevation_insets", text)
    assert (ok, normalized) == (True, expected), error


def test_validator_still_rejects_garbage():
    (ok, _, error) = SETTINGS.coerce("airport_elevation_insets", "Sometimes")
    assert ok is False and "not one of" in error


def test_a_legacy_bool_equals_its_mode_for_the_sparse_rule():
    # The ORDERING TRAP (spec §A.5): a tile cfg saying False must not be
    # seen as a foreign enum and replaced by the global.
    assert SETTINGS.values_equivalent(
        "airport_elevation_insets", "True", "ICAO") is True
    assert SETTINGS.values_equivalent(
        "airport_elevation_insets", "False", "None") is True
    assert SETTINGS.values_equivalent(
        "airport_elevation_insets", "False", "ICAO") is False


def test_registry_legacy_values_cover_the_cfg_reader():
    legacy = O4_Cfg_Vars.cfg_vars["airport_elevation_insets"]["legacy_values"]
    assert legacy["True"] == "ICAO" and legacy["False"] == "None"


# ── freshness / frame normalisation (test 3c) ─────────────────────────
def test_patch_freshness_stamp_records_the_normalised_mode():
    from auto_patch import provenance

    tile = _tile(airport_elevation_insets=True)
    assert provenance.normalize_mode(
        getattr(tile, "airport_elevation_insets"),
        "airport_elevation_insets") == "ICAO"


def test_harness_frame_compare_treats_True_and_ICAO_as_one_frame():
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "tools", "harness"))
    import build_airport

    ours = {"airport_elevation_insets": "True"}
    theirs = {"airport_elevation_insets": "ICAO"}
    assert (build_airport.effective_frame_value(
        "airport_elevation_insets", ours, theirs)
        == build_airport._normalized_frame_value(
            "airport_elevation_insets", theirs["airport_elevation_insets"]))
