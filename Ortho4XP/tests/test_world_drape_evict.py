"""Twin of ``src/o4_engine/world_drape_evict.py`` (#2142 Q3): the disk
budget gives World drapes back least recently flown first, offloads each
to a mounted storage tier with room before reverting it, reverts only
when no tier takes it, never touches a tile in X-Plane's window or the
flown airport's spawn set, and the World job lays an offloaded drape back
instead of fetching it.  All on ``tmp_path``; the pack's kinds are
faked (no DSFTool)."""
from __future__ import annotations

import os

import O4_World_Pack as WP
import pytest
from o4_engine import storage_tiers as TIERS
from o4_engine import world_drape_evict as EVICT


def _drape(pack, tile, nbytes=1000, when=0.0):
    for path in EVICT._own(str(pack), tile):
        if path.endswith(".dsf"):
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "wb") as f:
                f.write(b"X" * nbytes)
        elif path.endswith(".json"):
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w") as f:
                f.write("{}")
        else:
            os.makedirs(path, exist_ok=True)
            with open(os.path.join(path, "a.bin"), "wb") as f:
                f.write(b"Y" * nbytes)
    os.utime(EVICT._own(str(pack), tile)[0], (when, when))


@pytest.fixture
def pack(tmp_path, monkeypatch):
    pack = tmp_path / "pack"
    kinds = {}
    for i, tile in enumerate([(50, 1), (50, 2), (50, 3), (51, 1)]):
        _drape(pack, tile, when=1000.0 + i)
        kinds[tile] = "drape"
    monkeypatch.setattr(EVICT.WP, "world_tiles", lambda p: {
        t: k for t, k in kinds.items()
        if not WP.is_placeholder(os.path.join(p, WP.dsf_relpath(*t)))})
    import o4_engine.imagery_follow_drape as ROWS
    monkeypatch.setattr(ROWS, "forget", lambda lat, lon, store=None: True)
    return str(pack)


def _tier(monkeypatch, tmp_path, gigabytes):
    mount = tmp_path / "Volume"
    mount.mkdir(exist_ok=True)
    monkeypatch.setattr(TIERS, "_configured",
                        lambda raw=None: {str(mount): gigabytes})
    monkeypatch.setattr(TIERS, "_mounted", lambda m: True)
    monkeypatch.setattr(TIERS, "_USED", {})
    return str(mount)


def test_least_recently_flown_first_and_never_a_kept_tile(pack, monkeypatch,
                                                          tmp_path):
    """Flown times from the index win over the DSF's swap time; the kept
    set (window, spawn set, loaded) is never given back."""
    _tier(monkeypatch, tmp_path, 0)                     # no tier: revert
    flown = {(50, 1): 5000.0}                           # flown lately
    rows = EVICT._order(EVICT._drapes(pack, flown), keep={(50, 2)})
    assert [r[2] for r in rows] == [(50, 3), (51, 1), (50, 1)]
    one = rows[0][1]
    done = EVICT._evict(one + 1, pack, {(50, 2)}, flown=flown)
    assert done["reverted"] == ["+50+003", "+51+001"] and not done["offloaded"]
    kinds = WP.world_tiles(pack)
    assert (50, 3) not in kinds and kinds[(50, 2)] == "drape"
    assert WP.is_placeholder(os.path.join(pack, WP.dsf_relpath(50, 3)))
    assert not os.path.exists(os.path.join(pack, "textures", "+50+003"))


def test_a_tier_with_room_takes_the_drape_first(pack, monkeypatch, tmp_path):
    mount = _tier(monkeypatch, tmp_path, 1)
    done = EVICT._evict(1, pack, set(), flown={})
    assert done["offloaded"] == ["+50+001"] and not done["reverted"]
    home = os.path.join(mount, TIERS.TIER_DIR, EVICT.TIER_SUBDIR, "+50+001")
    assert os.path.isfile(EVICT._own(home, (50, 1))[0])
    assert WP.is_placeholder(os.path.join(pack, WP.dsf_relpath(50, 1)))
    assert TIERS._used(mount) == done["freed"]
    # the World job about to drape it lays the tier's copy back instead
    staged = str(tmp_path / "staging" / "+50+001")
    assert EVICT.recall((50, 1), staged)
    assert os.path.isfile(EVICT._own(staged, (50, 1))[0])
    assert not os.path.exists(home) and TIERS._used(mount) == 0
    assert not EVICT.recall((50, 2), str(tmp_path / "staging" / "x"))


def test_a_full_tier_reverts_and_an_offload_only_sweep_reverts_nothing(
        pack, monkeypatch, tmp_path):
    _tier(monkeypatch, tmp_path, 1e-9)                  # no room
    moved = EVICT._evict(10 ** 9, pack, set(), tier_only=True, flown={})
    assert moved == {"freed": 0, "offloaded": [], "reverted": []}
    done = EVICT._evict(1, pack, set(), flown={})
    assert done["reverted"] == ["+50+001"]


def test_a_dry_run_counts_and_moves_nothing(pack, monkeypatch, tmp_path):
    _tier(monkeypatch, tmp_path, 1)
    done = EVICT._evict(10 ** 9, pack, set(), dry_run=True, flown={})
    assert done["freed"] == sum(r[1] for r in EVICT._drapes(pack, {}))
    assert len(EVICT._drapes(pack, {})) == 4
