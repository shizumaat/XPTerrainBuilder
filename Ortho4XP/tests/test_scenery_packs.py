"""The ONE derivation site for pack enablement (RULINGS 2026-09-17b).

Every edge rule the census named is pinned here; the consumers' own twins
assert that they inherit these answers rather than re-deriving them.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

import O4_Scenery_Packs as SP  # noqa: E402


def _install(tmp_path, packs, ini_lines=None):
    """A Custom Scenery directory with ``packs`` on disk and an optional
    ini.  Returns the Custom Scenery path."""
    custom = tmp_path / "Custom Scenery"
    custom.mkdir(parents=True, exist_ok=True)
    for name in packs:
        (custom / name / "Earth nav data").mkdir(parents=True)
    if ini_lines is not None:
        (custom / "scenery_packs.ini").write_text(
            "I\n1000 Version\nSCENERY\n\n" + "\n".join(ini_lines) + "\n")
    return str(custom)


# ── token exactness (the E1 defect) ──────────────────────────────────
def test_disabled_token_is_not_an_enabled_token(tmp_path):
    custom = _install(tmp_path, ["a", "b"], [
        "SCENERY_PACK Custom Scenery/a/",
        "SCENERY_PACK_DISABLED Custom Scenery/b/",
    ])
    ordered, disabled = SP.parse_ini(
        os.path.join(custom, "scenery_packs.ini"))
    assert ordered == ["a"], "startswith('SCENERY_PACK') would admit b"
    assert disabled == {"b"}
    assert SP.enabled_pack_names(custom) == {"a"}
    assert SP.pack_enabled("a", custom) is True
    assert SP.pack_enabled("b", custom) is False


def test_lookalike_tokens_are_ignored(tmp_path):
    custom = _install(tmp_path, ["a"], [
        "SCENERY_PACKAGE Custom Scenery/a/",
        "SCENERY_PACK_DISABLED_TOO Custom Scenery/a/",
    ])
    ordered, disabled = SP.parse_ini(
        os.path.join(custom, "scenery_packs.ini"))
    assert ordered == [] and disabled == set()
    assert SP.enabled_pack_names(custom) == {"a"}


# ── absent / unreadable ini ──────────────────────────────────────────
def test_absent_ini_enables_every_pack_on_disk(tmp_path):
    custom = _install(tmp_path, ["a", "b"], None)
    assert SP.parse_ini(os.path.join(custom, "scenery_packs.ini")) == ([],
                                                                      set())
    assert SP.enabled_pack_names(custom) == {"a", "b"}
    assert SP.pack_enabled("b", custom) is True


@pytest.mark.skipif(os.geteuid() == 0, reason="root reads anything")
def test_unreadable_ini_enables_every_pack_on_disk(tmp_path):
    custom = _install(tmp_path, ["a", "b"], [
        "SCENERY_PACK_DISABLED Custom Scenery/b/",
    ])
    ini = os.path.join(custom, "scenery_packs.ini")
    os.chmod(ini, 0o000)
    try:
        assert SP.parse_ini(ini) == ([], set())
        assert SP.enabled_pack_names(custom) == {"a", "b"}
    finally:
        os.chmod(ini, 0o644)


# ── unlisted packs ───────────────────────────────────────────────────
def test_unlisted_pack_is_enabled(tmp_path):
    custom = _install(tmp_path, ["listed", "fresh"], [
        "SCENERY_PACK Custom Scenery/listed/",
    ])
    assert SP.enabled_pack_names(custom) == {"listed", "fresh"}


# ── listed but absent / dangling symlink ─────────────────────────────
def test_listed_but_absent_and_dangling_symlink_are_never_errors(tmp_path):
    custom = _install(tmp_path, ["real"], [
        "SCENERY_PACK Custom Scenery/real/",
        "SCENERY_PACK Custom Scenery/gone/",
        "SCENERY_PACK Custom Scenery/dangler/",
        "SCENERY_PACK_DISABLED Custom Scenery/also_gone/",
    ])
    os.symlink(os.path.join(tmp_path, "no_such_volume", "pack"),
               os.path.join(custom, "dangler"))
    assert os.path.islink(os.path.join(custom, "dangler"))
    assert not os.path.isdir(os.path.join(custom, "dangler"))
    assert SP.enabled_pack_names(custom) == {"real"}
    ordered, disabled = SP.parse_ini(
        os.path.join(custom, "scenery_packs.ini"))
    assert ordered == ["real", "gone", "dangler"]
    assert disabled == {"also_gone"}


# ── virtual / non-pack entries ───────────────────────────────────────
@pytest.mark.parametrize("entry", [
    "*GLOBAL_AIRPORTS*",
    "Global Scenery/X-Plane 12 Global Scenery/",
    "Resources/default scenery/default apt dat/",
])
def test_non_pack_entries_name_no_pack(entry):
    assert SP.pack_name_from_ini_path(entry) is None


def test_global_airports_is_never_filtered(tmp_path):
    custom = _install(tmp_path, ["Global Airports", "a"], [
        "SCENERY_PACK_DISABLED Custom Scenery/Global Airports/",
        "SCENERY_PACK_DISABLED Custom Scenery/a/",
    ])
    assert SP.enabled_pack_names(custom) == {"Global Airports"}
    assert SP.pack_enabled("Global Airports", custom) is True


def test_virtual_global_airports_row_does_not_disable_anything(tmp_path):
    custom = _install(tmp_path, ["a"], [
        "SCENERY_PACK_DISABLED *GLOBAL_AIRPORTS*",
        "SCENERY_PACK Custom Scenery/a/",
    ])
    _ordered, disabled = SP.parse_ini(
        os.path.join(custom, "scenery_packs.ini"))
    assert disabled == set()


# ── path shapes ──────────────────────────────────────────────────────
def test_windows_backslash_entry(tmp_path):
    custom = _install(tmp_path, ["winpack"], [
        r"SCENERY_PACK_DISABLED Custom Scenery\winpack\\",
    ])
    assert SP.disabled_pack_names(custom) == {"winpack"}
    assert SP.enabled_pack_names(custom) == set()


def test_trailing_slash_and_bare_name(tmp_path):
    assert SP.pack_name_from_ini_path("Custom Scenery/foo/") == "foo"
    assert SP.pack_name_from_ini_path("Custom Scenery/foo") == "foo"
    assert SP.pack_name_from_ini_path("foo/") == "foo"
    assert SP.pack_name_from_ini_path("/X-Plane 12/Custom Scenery/foo/") \
        == "foo"


def test_pack_name_with_spaces_and_dashes(tmp_path):
    custom = _install(tmp_path, ["c_FRA - 100_airport - LFMN"], [
        "SCENERY_PACK_DISABLED Custom Scenery/c_FRA - 100_airport - LFMN/",
    ])
    assert SP.disabled_pack_names(custom) == {"c_FRA - 100_airport - LFMN"}


# ── path-based queries ───────────────────────────────────────────────
def test_pack_enabled_from_a_path_inside_the_pack(tmp_path):
    custom = _install(tmp_path, ["off", "on"], [
        "SCENERY_PACK Custom Scenery/on/",
        "SCENERY_PACK_DISABLED Custom Scenery/off/",
    ])
    off_apt = os.path.join(custom, "off", "Earth nav data", "apt.dat")
    on_apt = os.path.join(custom, "on", "Earth nav data", "apt.dat")
    assert SP.pack_enabled(off_apt) is False
    assert SP.pack_enabled(on_apt) is True
    assert SP.custom_scenery_dir_for(off_apt) == custom


def test_paths_outside_custom_scenery_are_not_governed(tmp_path):
    outside = str(tmp_path / "Global Scenery" / "Global Airports"
                  / "Earth nav data" / "apt.dat")
    assert SP.custom_scenery_dir_for(outside) is None
    assert SP.pack_enabled(outside) is True
    assert SP.pack_state(outside) == ("", "external")
    assert SP.pack_state(None) == ("", "unknown")


def test_pack_state_pair(tmp_path):
    custom = _install(tmp_path, ["off"], [
        "SCENERY_PACK_DISABLED Custom Scenery/off/",
    ])
    apt = os.path.join(custom, "off", "Earth nav data", "apt.dat")
    assert SP.pack_state(apt) == ("off", "disabled")


# ── cache invalidation ───────────────────────────────────────────────
def test_toggling_the_ini_is_seen_immediately(tmp_path):
    custom = _install(tmp_path, ["a"], [
        "SCENERY_PACK Custom Scenery/a/",
    ])
    assert SP.enabled_pack_names(custom) == {"a"}
    ini = os.path.join(custom, "scenery_packs.ini")
    with open(ini, "w") as handle:
        handle.write("I\n1000 Version\nSCENERY\n\n"
                     "SCENERY_PACK_DISABLED Custom Scenery/a/\n")
    os.utime(ini, (0, 0))          # force a different mtime, not a later one
    assert SP.enabled_pack_names(custom) == set()


def test_filter_enabled_preserves_order(tmp_path):
    custom = _install(tmp_path, ["a", "b", "c"], [
        "SCENERY_PACK_DISABLED Custom Scenery/b/",
    ])
    assert SP.filter_enabled(["c", "b", "a"], custom) == ["c", "a"]


# ── stdlib-only import law ───────────────────────────────────────────
def test_module_imports_no_o4_or_auto_patch_module():
    source_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "src", "O4_Scenery_Packs.py")
    with open(source_path) as handle:
        source = handle.read()
    import ast
    tree = ast.parse(source)
    names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            names.append(node.module or "")
    for name in names:
        assert not name.startswith("O4_"), name
        assert not name.startswith("auto_patch"), name
