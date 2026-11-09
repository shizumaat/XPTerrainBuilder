"""#1906: a lane whose cfg REDIRECTS ``custom_scenery_dir`` never writes the
owner's real X-Plane install, ``--refresh-data pack_rebake`` included.

Incident 2026-11-05: the lane cfg pointed at a scratch tree; the harness
overwrote that with the owner's install path, the guard defended the
scratch tree, and ``pack_rebake`` let the object stage rewrite three real
packs.  These twins use a tmp "owner install" and a tmp scratch tree only —
no real pack is read or written.
"""
import os
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "tools" / "harness"))

import pack_copy_arm as PCA  # noqa: E402
import shared_repo_guard as SRG  # noqa: E402

_KEYS = ("cifp_data_path", "custom_scenery_dir", "custom_overlay_src")


@pytest.fixture()
def installs(tmp_path):
    """``(owner install, lane scratch install)``, each with one pack."""
    owner, scratch = tmp_path / "X-Plane 12", tmp_path / "scratch" / "XP"
    for inst in (owner, scratch):
        (inst / "Custom Scenery" / "Pack A" / "Earth nav data").mkdir(
            parents=True)
    (owner / "Custom Data" / "CIFP").mkdir(parents=True)
    return owner, scratch


def _cfg(path, **values):
    path.write_text("".join(f"{k}={v}\n" for k, v in values.items()),
                    encoding="utf-8", newline="\n")
    return path


def test_lane_redirect_wins_over_owner_path():
    owner = {"custom_scenery_dir": "/o/CS", "cifp_data_path": "/o/CIFP"}
    applied, redirects = PCA.effective_install_paths(
        owner, {"custom_scenery_dir": "/s/CS", "cifp_data_path": ""}, _KEYS)
    assert applied == {"custom_scenery_dir": "/s/CS",
                       "cifp_data_path": "/o/CIFP"}
    assert redirects == {"custom_scenery_dir": "/s/CS"}
    same, none = PCA.effective_install_paths(owner, dict(owner), _KEYS)
    assert same == owner and none == {}          # an un-redirected lane


def test_apply_install_paths_keeps_the_lane_redirect(tmp_path, installs):
    """The root cause: the redirect must survive into the live globals the
    object stage's pack selection reads."""
    import build_airport as BA
    import O4_Config_Utils as CFG
    owner, scratch = installs
    owner_cfg = _cfg(tmp_path / "owner.cfg",
                     custom_scenery_dir=owner / "Custom Scenery",
                     cifp_data_path=owner / "Custom Data" / "CIFP")
    lane_cfg = _cfg(tmp_path / "lane.cfg",
                    custom_scenery_dir=scratch / "Custom Scenery")
    saved = {k: getattr(CFG, k, None) for k in _KEYS}
    try:
        applied = BA.apply_xplane_install_paths(owner_cfg, lane_cfg)
        assert applied["custom_scenery_dir"] == str(scratch / "Custom Scenery")
        assert CFG.custom_scenery_dir.rstrip("/") == \
            str(scratch / "Custom Scenery")
        assert applied["cifp_data_path"] == str(owner / "Custom Data" / "CIFP")
    finally:
        for k, v in saved.items():
            setattr(CFG, k, v)


def test_explicit_owner_cfg_is_read_alone(tmp_path, installs):
    """A caller naming its own owner cfg (the suite's twins) gets exactly
    that cfg — the worktree's lane cfg is not consulted."""
    import build_airport as BA
    import O4_Config_Utils as CFG
    owner, _scratch = installs
    owner_cfg = _cfg(tmp_path / "owner.cfg",
                     custom_scenery_dir=owner / "Custom Scenery",
                     cifp_data_path=owner / "Custom Data" / "CIFP")
    saved = {k: getattr(CFG, k, None) for k in _KEYS}
    try:
        assert BA.apply_xplane_install_paths(owner_cfg)[
            "custom_scenery_dir"] == str(owner / "Custom Scenery")
    finally:
        for k, v in saved.items():
            setattr(CFG, k, v)


def test_owner_install_roots_come_from_the_owner_cfg():
    roots = PCA.owner_install_roots({"custom_scenery_dir": "/o/X/Custom Scenery"})
    assert "/o/X" in roots
    assert os.path.expanduser("~/X-Plane 12") in roots


def test_pack_rebake_refused_only_for_owner_packs(installs):
    owner, scratch = installs
    real = str(owner / "Custom Scenery" / "Pack A")
    copy = str(scratch / "Custom Scenery" / "Pack A")
    assert PCA.pack_rebake_refusal({"pack_rebake"}, [copy], [str(owner)]) is None
    assert "#1906" in PCA.pack_rebake_refusal({"pack_rebake"}, [copy, real],
                                              [str(owner)])


def _guard(tmp_path, owner, scratch, requested):
    repo = tmp_path / "corpus"
    repo.mkdir(exist_ok=True)
    return SRG.SharedRepoWriteGuard(requested, str(tmp_path), repo=repo,
                                    install_roots=[str(scratch)],
                                    owner_roots=[str(owner)])


@pytest.mark.parametrize("requested", [set(), {"pack_rebake"}])
def test_redirected_build_never_opens_owner_install_for_write(
        tmp_path, installs, requested):
    """Under EVERY scope set, ``pack_rebake`` included: a write into the
    owner's pack refuses at the call and leaves no file."""
    owner, scratch = installs
    target = owner / "Custom Scenery" / "Pack A" / "Earth nav data" / "x.dsf"
    with _guard(tmp_path, owner, scratch, requested) as guard:
        with pytest.raises(SRG.SharedRepoWriteBlocked, match="#1906"):
            with open(target, "wb") as fh:
                fh.write(b"rewritten")
        with pytest.raises(SRG.SharedRepoWriteBlocked):
            os.open(str(target), os.O_WRONLY | os.O_CREAT)
        with open(os.devnull, "rb"):
            pass                                    # reads stay open
    assert not target.exists()
    assert guard.blocked and all(b["scope"] == SRG.OWNER_INSTALL
                                 for b in guard.blocked)


def test_redirected_scratch_install_writable_under_pack_rebake(
        tmp_path, installs):
    owner, scratch = installs
    target = scratch / "Custom Scenery" / "Pack A" / "Earth nav data" / "x.dsf"
    with _guard(tmp_path, owner, scratch, {"pack_rebake"}):
        target.write_bytes(b"lane copy")
    assert target.read_bytes() == b"lane copy"
    with _guard(tmp_path, owner, scratch, set()):
        with pytest.raises(SRG.SharedRepoWriteBlocked):
            target.write_bytes(b"unauthorised")
