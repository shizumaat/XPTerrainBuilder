"""Settings presets, one table in two apps (issue #822).

``src/O4_Settings_Presets.PRESETS`` is the table; the Mac app mirrors it in
``Sources/XPTerrainBuilder/SettingsPresets.swift``.  This twin requires the
two to be equal, every preset to write the same existing keys, Recommended
to be the shipped defaults, Custom to show once a key differs, and every
GB figure on a card to equal its derivation in ``docs/presets.md``.

Hermetic: the repo's own files, no Qt, no network.
"""

from __future__ import annotations

import math
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import O4_Cfg_Vars  # noqa: E402
import O4_DDS_File as DDS  # noqa: E402
import O4_Glossary as GLOSSARY  # noqa: E402
import O4_Settings_Model as SM  # noqa: E402
import O4_Settings_Presets as PRESETS  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
SWIFT = REPO_ROOT / "Sources" / "XPTerrainBuilder" / "SettingsPresets.swift"
DOC = REPO_ROOT / "docs" / "presets.md"

_LITERAL = r'"((?:[^"\\]|\\.)*)"'
_PRESET = re.compile(
    r"SettingsPreset\(" + _LITERAL + ", " + _LITERAL
    + r",\s*summary: " + _LITERAL + r",\s*cost: " + _LITERAL
    + r",\s*values: \[([^\]]*)\]\)")
_PAIR = re.compile(_LITERAL + ": " + _LITERAL)


def swift_presets() -> list:
    text = SWIFT.read_text(encoding="utf-8")
    return [(key, title, summary, cost, tuple(_PAIR.findall(values)))
            for key, title, summary, cost, values in _PRESET.findall(text)]


def _swift_constant(name: str) -> str:
    text = SWIFT.read_text(encoding="utf-8")
    return re.search(r"static let " + name + " = " + _LITERAL, text).group(1)


# ── one table, two apps ───────────────────────────────────────────────

def test_swift_table_equals_python():
    python = [(p.key, p.title, p.summary, p.cost, p.values)
              for p in PRESETS.PRESETS]
    assert swift_presets() == python


def test_swift_words_equal_python():
    assert _swift_constant("zoomKey") == PRESETS.ZOOM_PREF
    assert _swift_constant("sectionTitle") == PRESETS.SECTION_TITLE
    assert _swift_constant("sectionNote") == PRESETS.SECTION_NOTE
    assert _swift_constant("customTitle") == PRESETS.CUSTOM_TITLE


# ── the keys ──────────────────────────────────────────────────────────

def test_every_preset_writes_the_same_existing_keys():
    for entry in PRESETS.PRESETS:
        assert tuple(name for name, _ in entry.values) == PRESETS.PRESET_KEYS
    for name in PRESETS.PRESET_KEYS[1:]:
        assert name in O4_Cfg_Vars.cfg_vars, name
        assert SM.get_setting(name)  # a Settings row shows it


def test_every_value_is_the_stored_cfg_form():
    for entry in PRESETS.PRESETS:
        for name, value in PRESETS.cfg_values(entry).items():
            ok, normalized, error = SM.coerce(name, value)
            assert ok, (entry.key, name, error)
            assert normalized == value, (entry.key, name)
        assert PRESETS.zoom_value(entry) in GLOSSARY.DETAIL_PIXEL_SIZES


def test_recommended_is_the_registry_defaults():
    recommended = PRESETS.preset("recommended")
    for name, value in PRESETS.cfg_values(recommended).items():
        assert SM.values_equivalent(
            name, value, str(O4_Cfg_Vars.cfg_vars[name]["default"])), name
    assert PRESETS.zoom_value(recommended) == PRESETS.default_zoom() == 16
    fresh = PRESETS.current_values({}, PRESETS.default_zoom())
    assert PRESETS.matching_preset(fresh) is recommended


def test_presets_are_distinct():
    seen = set()
    for entry in PRESETS.PRESETS:
        assert entry.values not in seen
        seen.add(entry.values)
        assert PRESETS.matching_preset(
            PRESETS.current_values(PRESETS.cfg_values(entry),
                                   PRESETS.zoom_value(entry))) is entry


# ── Custom ────────────────────────────────────────────────────────────

def test_custom_once_any_key_differs():
    for entry in PRESETS.PRESETS:
        base = PRESETS.cfg_values(entry)
        zoom = PRESETS.zoom_value(entry)
        assert PRESETS.status_text(
            PRESETS.current_values(base, zoom)) == "Current: " + entry.title
        # Equivalent spellings are the same value, not Custom.
        loose = dict(base, cover_extent="1")
        assert PRESETS.matching_preset(
            PRESETS.current_values(loose, zoom)) is entry
        assert PRESETS.matching_preset(
            PRESETS.current_values(base, 17)) is None
        changed = dict(base, cover_extent="2.5")
        assert PRESETS.status_text(
            PRESETS.current_values(changed, zoom)) == "Current: Custom"


def test_a_key_outside_the_set_never_makes_custom():
    values = dict(PRESETS.cfg_values(PRESETS.preset("light_on_disk")),
                  road_level="4")
    assert PRESETS.matching_preset(
        PRESETS.current_values(values, 15)).key == "light_on_disk"


# ── the figures: derived, never invented ──────────────────────────────

def _texture_bytes() -> int:
    """One 4096x4096 BC1 (DXT1) texture with its full mip chain."""
    levels = DDS.mip_dims(4096, 4096, DDS.full_mip_count(4096, 4096))
    return DDS.HEADER_BYTES + sum(DDS.level_size(w, h, "bc1")
                                  for w, h in levels)


def _orthogrid(lat: float, lon: float, zoom: int) -> tuple:
    """O4_Geo_Utils.wgs84_to_orthogrid, restated without pyproj."""
    ratio_x = lon / 180
    ratio_y = math.log(math.tan((90 + lat) * math.pi / 360)) / math.pi
    mult = 2 ** (zoom - 5)
    return (int((ratio_x + 1) * mult) * 16, int((1 - ratio_y) * mult) * 16)


def _textures_per_tile(lat: int, zoom: int) -> int:
    left, top = _orthogrid(lat + 1, 0, zoom)
    right, bottom = _orthogrid(lat, 1 - 1e-9, zoom)
    return ((right - left) // 16 + 1) * ((bottom - top) // 16 + 1)


def imagery_gb_range(zoom: int) -> tuple:
    """(lowest, highest) texture GB of a tile from 0° to 60° latitude."""
    counts = [_textures_per_tile(lat, zoom) for lat in range(60)]
    size = _texture_bytes()
    return (round(min(counts) * size / 1e9, 1),
            round(max(counts) * size / 1e9, 1))


def test_texture_arithmetic():
    assert _texture_bytes() == 11_184_952  # 8 MiB x 4/3 + header
    import O4_Geo_Utils as GEO  # the engine's own grid, where pyproj is
    for lat in (0, 30, 59):
        for zoom in (15, 16):
            assert _orthogrid(lat, 0.5, zoom) == GEO.wgs84_to_orthogrid(
                lat, 0.5, zoom)
    # The docs/presets.md table: textures per tile, 0° to 60° latitude.
    for zoom, expected in ((15, (36, 72)), (16, (144, 276))):
        counts = [_textures_per_tile(lat, zoom) for lat in range(60)]
        assert (min(counts), max(counts)) == expected


def test_card_figures_equal_their_derivation():
    for entry in PRESETS.PRESETS:
        low, high = imagery_gb_range(PRESETS.zoom_value(entry))
        assert "About %.1f–%.1f GB" % (low, high) in entry.cost, entry.key
    light = PRESETS.preset("light_on_disk")
    assert "a quarter of Recommended" in light.cost
    assert (4 ** (PRESETS.zoom_value(PRESETS.preset("recommended"))
                  - PRESETS.zoom_value(light))) == 4


def test_summaries_name_the_zl_number():
    # Owner ruling 2026-10-18: detail levels are named by their ZL number.
    for entry in PRESETS.PRESETS:
        assert "ZL%d" % PRESETS.zoom_value(entry) in entry.summary
    sharper = PRESETS.preset("sharper_airports")
    cover = int(sharper.as_dict()["cover_zl"])
    assert "ZL%d" % cover in sharper.summary


def test_no_preset_writes_cleaning_level():
    # Owner ruling 2026-10-18: "Light on disk" must not set cleaning_level.
    assert "cleaning_level" not in PRESETS.PRESET_KEYS


def test_the_doc_lists_every_preset_value_and_figure():
    doc = DOC.read_text(encoding="utf-8")
    for entry in PRESETS.PRESETS:
        assert entry.title in doc
        assert entry.cost in doc
    for name in PRESETS.PRESET_KEYS:
        assert "`%s`" % name in doc
    assert "SHARPER_AIRPORTS_EXTRA_GB" in doc
    assert "RELATIVE_BUILD_TIME" in doc


def test_card_words_are_plain():
    for entry in PRESETS.PRESETS:
        for text in (entry.title, entry.summary, entry.cost):
            # A ZL number is plain here (owner ruling 2026-10-18).
            words = set(re.findall(r"[A-Za-z]+", text)) - {"ZL"}
            assert not words & set(GLOSSARY.RETIRED_WORDS), (entry.key, text)
            assert "_" not in text
