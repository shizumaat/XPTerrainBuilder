"""#1723 twin: the tmp/ age prune lists old entries and keeps the protected."""
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "harness"))
import tmp_prune  # noqa: E402

OLD = time.time() - 30 * 86400


def _age(path):
    for d, dirs, names in os.walk(path):
        for n in dirs + names:
            os.utime(os.path.join(d, n), (OLD, OLD))
    os.utime(path, (OLD, OLD))


def _tree(tmp_path):
    eng = tmp_path / "Ortho4XP"
    t = eng / "tmp"
    (t / "old_run").mkdir(parents=True)
    (t / "old_run" / "x.log").write_text("x" * 5000, encoding="utf-8", newline="\n")
    (t / "fresh.log").write_text("y", encoding="utf-8", newline="\n")
    (t / "frame_dir").mkdir()
    (t / "frame_dir" / "cap.pkl").write_text("z", encoding="utf-8", newline="\n")
    (t / "held").mkdir()
    (t / "held" / "f").write_text("h", encoding="utf-8", newline="\n")
    data = tmp_path / "data"
    (data / "OSM_data").mkdir(parents=True)
    (t / "link").symlink_to(data / "OSM_data")
    mod = t / "engine_caches" / "Airport_mod_cache"
    (mod / "PackOld").mkdir(parents=True)
    (mod / "PackOld" / "a.text").write_text("a", encoding="utf-8", newline="\n")
    (mod / "PackNew").mkdir()
    (mod / "PackNew" / "b.text").write_text("b", encoding="utf-8", newline="\n")
    for p in ("old_run", "frame_dir", "held"):
        _age(t / p)
    _age(mod / "PackOld")
    os.utime(t / "link", (OLD, OLD), follow_symlinks=False)
    return eng, t, data


def test_twin_dry_run_lists_old_and_keeps_the_protected(tmp_path):
    eng, t, data = _tree(tmp_path)
    rows = {Path(p).name: why for p, _s, _a, why in tmp_prune.candidates(
        eng, 7, data, [os.path.realpath(t / "frame_dir" / "cap.pkl")],
        [os.path.realpath(t / "held" / "f")])}
    assert rows == {"old_run": "", "frame_dir": "registered frame",
                    "held": "held open by a process", "link": "symlink",
                    "PackOld": ""}


def test_twin_apply_deletes_only_the_unkept(tmp_path):
    eng, t, data = _tree(tmp_path)
    rows = tmp_prune.candidates(eng, 7, data,
                                [os.path.realpath(t / "frame_dir")], [])
    tmp_prune.prune(rows)
    assert not (t / "old_run").exists()
    assert (t / "frame_dir").exists() and (t / "fresh.log").exists()
    assert (data / "OSM_data").is_dir() and (t / "link").is_symlink()
    assert (t / "engine_caches" / "Airport_mod_cache" / "PackNew").exists()


def test_twin_after_run_prunes_only_the_cache(tmp_path, monkeypatch):
    eng, t, data = _tree(tmp_path)
    monkeypatch.setattr(tmp_prune, "open_paths", lambda tmp: [])
    n, _freed = tmp_prune.prune_cache_after_run(eng, data, None, days=7)
    assert n == 1
    assert not (t / "engine_caches" / "Airport_mod_cache" / "PackOld").exists()
    assert (t / "old_run").exists()
