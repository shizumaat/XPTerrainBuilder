"""A tile that finished with white textures SAYS so, once, loudly.

Connection failures are logged at verbosity 2-3 (``O4_Imagery_Utils``,
the retry loop): invisible at the default verbosity.  The tile then
finished, exit 0, and the user met the white squares in the simulator.

``incomplete_texture_warning`` is the counting function behind the one
``UI.loud_warning`` line the imagery step now ends with — loud_warning
reaches both UIs' consoles and Ortho4XP.log.  No new wire event.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest  # noqa: E402

import O4_Imagery_Utils as IMG  # noqa: E402


@pytest.fixture(autouse=True)
def clean_registers():
    IMG.incomplete_imgs.clear()
    IMG.incomplete_img_paths.clear()
    IMG.incomplete_img_providers.clear()
    yield
    IMG.incomplete_imgs.clear()
    IMG.incomplete_img_paths.clear()
    IMG.incomplete_img_providers.clear()


def test_a_complete_tile_says_nothing():
    assert IMG.incomplete_texture_warning("+30+031") is None


def test_an_untouched_tile_says_nothing():
    IMG.incomplete_imgs["+48-006"] = ["1_2_BI16.jpg"]
    IMG.incomplete_img_providers["+48-006"] = {"BI"}
    assert IMG.incomplete_texture_warning("+30+031") is None


def test_the_count_and_the_provider_are_named():
    IMG.incomplete_imgs["+30+031"] = [
        "1_2_BI16.jpg", "3_4_BI16.jpg", "5_6_BI16.jpg"]
    IMG.incomplete_img_providers["+30+031"] = {"BI"}
    message = IMG.incomplete_texture_warning("+30+031")
    assert "+30+031" in message
    assert "3 textures" in message
    assert "BI" in message
    assert message.startswith("WARNING")


def test_one_failure_is_singular():
    IMG.incomplete_imgs["+30+031"] = ["1_2_BI16.jpg"]
    IMG.incomplete_img_providers["+30+031"] = {"BI"}
    message = IMG.incomplete_texture_warning("+30+031")
    assert "1 texture that" in message


def test_every_failing_layer_of_a_combined_source_is_named():
    IMG.incomplete_imgs["+30+031"] = ["1_2_a16.jpg", "3_4_b16.jpg"]
    IMG.incomplete_img_providers["+30+031"] = {"USA2", "BI"}
    message = IMG.incomplete_texture_warning("+30+031")
    assert "BI, USA2" in message, "sorted, so the line is deterministic"


def test_a_failure_with_no_recorded_provider_still_warns():
    """The count is the load-bearing part; an unknown source must not
    swallow the warning."""
    IMG.incomplete_imgs["+30+031"] = ["1_2_BI16.jpg"]
    message = IMG.incomplete_texture_warning("+30+031")
    assert "the imagery source" in message


class _Tile:
    def __init__(self, lat, lon):
        self.lat = lat
        self.lon = lon


def test_the_step_emits_it_through_loud_warning(monkeypatch):
    """The channel matters: loud_warning is the one that reaches both
    UIs' consoles and Ortho4XP.log. No new wire event was added."""
    import O4_Tile_Utils as TILE
    import O4_UI_Utils as UI

    said = []
    monkeypatch.setattr(UI, "loud_warning", lambda *a: said.append(a))
    IMG.incomplete_imgs["+30+031"] = ["1_2_BI16.jpg"]
    IMG.incomplete_img_providers["+30+031"] = {"BI"}
    TILE.warn_if_imagery_incomplete(_Tile(30, 31))
    assert len(said) == 1
    assert "1 texture" in said[0][0] and "BI" in said[0][0]


def test_a_complete_step_is_silent(monkeypatch):
    import O4_Tile_Utils as TILE
    import O4_UI_Utils as UI

    said = []
    monkeypatch.setattr(UI, "loud_warning", lambda *a: said.append(a))
    assert TILE.warn_if_imagery_incomplete(_Tile(30, 31)) is None
    assert said == []


def test_the_rebuild_attempt_clears_the_register(tmp_path, monkeypatch):
    """``delete_incomplete_imgs`` drops the provider register with the
    other two, so the retry's warning describes the retry."""
    import O4_Tile_Utils as TILE

    IMG.incomplete_imgs["+30+031"] = ["1_2_BI16.jpg"]
    IMG.incomplete_img_providers["+30+031"] = {"BI"}
    tile = _Tile(30, 31)
    tile.build_dir = str(tmp_path)
    TILE.delete_incomplete_imgs(tile)
    assert "+30+031" not in IMG.incomplete_img_providers
    assert IMG.incomplete_texture_warning("+30+031") is None
