"""A STOPPED build does not activate the tile (issue #598, owner ruling
2026-10-12h (3)): the previous scenery stays, loadable and unchanged, until
a build completes; activation is the last act of a COMPLETED build.

The imagery step used to delete the live ``terrain`` folder first, move the
previous scenery file aside inside the encoder, and activate the new one
BEFORE asking whether the build had been stopped.  These twins pin:

* a Stop during the texture downloads, or inside the encoder: the previous
  scenery file byte-identical, every terrain file it names still there
  with its own text, nothing activated, no failure named;
* the next build completes with nothing done by hand, asks only for the
  textures that had not arrived, and activates exactly once;
* at the moment of the swap the live folder holds BOTH generations'
  terrain files; what the new file does not name goes afterwards;
* a refused terrain install is a named failure that keeps the previous
  scenery.

Headless: a stub encoder and a fake download step, ``tmp_path`` build
directories, no network.
"""

import errno
import os
import sys
import types

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest  # noqa: E402

import O4_DSF_Utils as DSF  # noqa: E402
import O4_Tile_Staging as STAGING  # noqa: E402
import O4_Tile_Utils as TILE  # noqa: E402
import O4_UI_Utils as UI  # noqa: E402

from test_dsf_activation import (  # noqa: E402,F401
    _Recorder, _dsf_path, _read, _stub_step, _write, reset_ui_routing)


class _Listener(_Recorder):
    """Also keeps the warning lines the step says to the apps."""

    def __init__(self):
        super().__init__()
        self.said = []

    def log_warning(self, text):
        self.said.append(text)


class _Run:
    """One tile folder built several times: a stub encoder that stages one
    terrain file per texture and queues the textures not on disk, and a
    fake download step that can raise the Stop."""

    def __init__(self, tmp_path, monkeypatch):
        self.tile = _stub_step(tmp_path, monkeypatch, None)
        self.tile.texture_mode = "full_ortho"
        self.dsf = _dsf_path(self.tile.build_dir)
        self.textures = []            # this build's texture names
        self.generation = 0
        self.stop_in_encoder = False
        self.stop_after_downloads = None
        self.asked = []               # textures the download step was given
        self.activations = 0
        self.live_at_swap = None
        monkeypatch.setattr(TILE, "skip_converts", True)
        monkeypatch.setattr(DSF, "build_dsf", self._encode)
        monkeypatch.setattr(TILE, "download_textures", self._download)
        real_activate = TILE.activate_dsf

        def counted(dsf_file_name):
            self.activations += 1
            self.live_at_swap = self.live_terrain()
            return real_activate(dsf_file_name)

        monkeypatch.setattr(TILE, "activate_dsf", counted)
        UI.engine_session = self.listener = _Listener()

    def _path(self, *parts):
        return os.path.join(self.tile.build_dir, *parts)

    def _encode(self, tile, download_queue):
        for name in self.textures:
            _write(os.path.join(STAGING.terrain_dir(tile), name + ".ter"),
                   b"gen%d ../textures/%s.dds" % (self.generation,
                                                  name.encode()))
            if not os.path.isfile(self._path("textures", name + ".dds")):
                download_queue.put(name)
        if self.stop_in_encoder:
            _write(self.dsf + ".tmp", b"trunc")
            UI.red_flag = True
            return 0
        _write(self.dsf + ".tmp", self.payload())
        return 1

    def _download(self, tile, download_queue, convert_queue, workers,
                  producer_done_event, stats):
        producer_done_event.wait(10)
        arrived = 0
        while not download_queue.empty():
            name = download_queue.get()
            self.asked.append(name)
            if arrived == self.stop_after_downloads:
                UI.red_flag = True            # the user's Stop
                break
            _write(self._path("textures", name + ".dds"), b"dds " +
                   name.encode())
            arrived += 1
        stats["done"], stats["failed"] = arrived, 0

    def payload(self):
        return ("dsf gen%d: %s" % (self.generation,
                                   " ".join(self.textures))).encode()

    def live_terrain(self):
        folder = self._path("terrain")
        if not os.path.isdir(folder):
            return {}
        return {name: _read(os.path.join(folder, name))
                for name in os.listdir(folder)}

    def build(self, textures, stop_after_downloads=None,
              stop_in_encoder=False):
        self.generation += 1
        self.textures = list(textures)
        self.stop_after_downloads = stop_after_downloads
        self.stop_in_encoder = stop_in_encoder
        self.asked = []
        self.activations = 0
        self.listener.said = []
        return TILE.build_tile(self.tile)


@pytest.fixture
def run(tmp_path, monkeypatch):
    return _Run(tmp_path, monkeypatch)


# ---------------------------------------------------------------------------
# A completed build
# ---------------------------------------------------------------------------
def test_a_completed_build_activates_exactly_once(run):
    assert run.build(["a", "b"]) == 1

    assert run.activations == 1
    assert _read(run.dsf) == run.payload()
    assert sorted(run.live_terrain()) == ["a.ter", "b.ter"]
    assert not os.path.exists(STAGING.staging_dir(run.tile))
    assert run.listener.named == [] and run.listener.said == []


def test_at_the_swap_both_generations_terrain_files_are_there(run):
    assert run.build(["a", "b"]) == 1
    assert run.build(["b", "c"]) == 1

    # when the scenery file was swapped: the old file's AND the new one's
    assert sorted(run.live_at_swap) == ["a.ter", "b.ter", "c.ter"]
    # afterwards: what the new file names, in this build's text
    live = run.live_terrain()
    assert sorted(live) == ["b.ter", "c.ter"]
    assert live["b.ter"].startswith(b"gen2 ")
    assert _read(run.dsf + ".bak").startswith(b"dsf gen1")


def test_a_grouped_build_directory_keeps_the_other_tiles_terrain(run):
    _write(os.path.join(run.tile.build_dir, "terrain", "other_tile.ter"),
           b"another tile of the group")
    run.tile.grouped = True

    assert run.build(["a"]) == 1

    assert sorted(run.live_terrain()) == ["a.ter", "other_tile.ter"]


# ---------------------------------------------------------------------------
# A Stop
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("where", ["textures", "encoder"])
def test_a_stop_leaves_the_previous_scenery_as_it_was(run, where):
    assert run.build(["a", "b"]) == 1
    previous_dsf = _read(run.dsf)
    previous_terrain = run.live_terrain()

    stopped = (dict(stop_after_downloads=1) if where == "textures"
               else dict(stop_in_encoder=True))
    assert run.build(["b", "c", "d"], **stopped) == 0

    assert run.activations == 0
    assert _read(run.dsf) == previous_dsf              # byte-identical
    assert run.live_terrain() == previous_terrain      # names AND text
    assert not os.path.exists(run.dsf + ".bak")
    assert run.listener.named == []                    # a cancel, no failure
    (said,) = run.listener.said
    assert "stopped" in said and "still in place" in said
    assert UI.is_working is False


def test_the_build_after_a_stop_completes_with_what_had_arrived(run):
    assert run.build(["a", "b"]) == 1
    assert run.build(["b", "c", "d"], stop_after_downloads=1) == 0
    assert run.asked == ["c", "d"]                     # c arrived, d did not
    UI.red_flag = False                                # the user builds again

    assert run.build(["b", "c", "d"]) == 1

    assert run.asked == ["d"]                          # c is not fetched again
    assert run.activations == 1
    assert _read(run.dsf) == run.payload()
    live = run.live_terrain()
    assert sorted(live) == ["b.ter", "c.ter", "d.ter"]
    assert all(text.startswith(b"gen3 ") for text in live.values())
    assert not os.path.exists(run.dsf + ".tmp")
    assert not os.path.exists(STAGING.staging_dir(run.tile))


def test_a_stop_on_a_tile_never_built_says_it_has_no_scenery(run):
    assert run.build(["a"], stop_after_downloads=0) == 0

    assert not os.path.exists(run.dsf)
    assert run.live_terrain() == {}
    (said,) = run.listener.said
    assert "no scenery yet" in said
    assert run.listener.named == []


# ---------------------------------------------------------------------------
# A refused install
# ---------------------------------------------------------------------------
def test_a_refused_terrain_install_keeps_the_previous_scenery(
        run, monkeypatch):
    assert run.build(["a", "b"]) == 1
    previous_dsf = _read(run.dsf)
    previous_terrain = run.live_terrain()
    real_replace = os.replace

    def replace(source, destination):
        if str(source).endswith("c.ter"):
            raise PermissionError(errno.EACCES, "Access is denied")
        return real_replace(source, destination)

    monkeypatch.setattr(STAGING.os, "replace", replace)

    assert run.build(["c"]) == 0

    assert run.listener.named == ["scenery_file_locked"]
    assert run.activations == 0
    assert _read(run.dsf) == previous_dsf
    assert run.live_terrain() == previous_terrain


# ---------------------------------------------------------------------------
# Where the encoder writes
# ---------------------------------------------------------------------------
def test_the_encoder_writes_terrain_files_to_the_staging_folder(tmp_path):
    tile = types.SimpleNamespace(
        lat=60, lon=5, build_dir=str(tmp_path), grouped=False,
        use_decal_on_terrain=False, terrain_casts_shadows=True,
        imprint_masks_to_dds=True)
    arguments = (tile, "100_200_Arc16.dds", 100, 200, 16, "Arc", 0, False)

    staged = STAGING.begin(tile)
    name = DSF.create_terrain_file(*arguments)
    assert os.listdir(staged) == [name]
    assert not os.path.exists(os.path.join(str(tmp_path), "terrain"))

    assert STAGING.install(tile) == {name}
    assert os.listdir(os.path.join(str(tmp_path), "terrain")) == [name]
    assert not os.path.exists(staged)

    # no build in progress: the live folder, as before
    os.remove(os.path.join(str(tmp_path), "terrain", name))
    DSF.create_terrain_file(*arguments)
    assert os.listdir(os.path.join(str(tmp_path), "terrain")) == [name]
