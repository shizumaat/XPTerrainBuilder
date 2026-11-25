"""#2207: every cleanup pass says in ``logs/storage.log`` WHY it ran --
the age rule, a cache cap, the redundant files or the disk budget, with
the numbers -- before its first deletion, and each deletion line names
the step.  On a synthetic data folder in ``tmp_path``
(``test_storage_settings.root``); no network, no build.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from o4_engine import storage as ST  # noqa: E402
from o4_engine import storage_budget as TOTAL  # noqa: E402
from o4_engine import storage_range as RANGE  # noqa: E402
from test_storage_settings import _write, root  # noqa: E402,F401

_GB = 10**9


def _log(root):  # noqa: F811
    path = root / "logs" / ST.LOG_NAME
    return path.read_text(encoding="utf-8") if path.exists() else ""


def test_the_age_rule_names_itself_and_spares_younger_files(root):  # noqa: F811
    old = _write(str(root / "Masks" / "+45+007" / "old.png"), 10, age_days=61)
    young = _write(str(root / "Masks" / "+45+007" / "young.png"), 10, age_days=18)
    ST.storage_auto_clean(days=60, caps={})
    assert not os.path.exists(old) and os.path.exists(young)
    lines = _log(root).splitlines()
    assert "automatic cleanup: age rule: files not used for 60 days" in lines[0]
    assert "storage_auto_clean_days=60" in lines[0]
    deleted = [line for line in lines if " deleted " in line]
    assert len(deleted) == 1 and "(masks, automatic cleanup, age rule)" in deleted[0]


def test_nothing_old_enough_writes_no_line(root):  # noqa: F811
    _write(str(root / "Masks" / "+45+007" / "young.png"), 10, age_days=18)
    ST.storage_auto_clean(days=60, caps={})
    assert _log(root) == ""


def test_a_cache_cap_names_the_store_and_its_cap(root):  # noqa: F811
    paths = [_write(str(root / "OSM_data" / "_regional_extracts" / f"r{i}.osm.pbf"),
                    1000, age_days=10 - i) for i in range(2)]
    ST.storage_auto_clean(days=0, caps={"osm_extracts": 1})
    lines = _log(root).splitlines()
    assert "automatic cleanup: cache cap: osm_extracts holds" in lines[0]
    assert "over its storage_cache_caps_gb cap of 1 bytes" in lines[0]
    assert not any(os.path.exists(p) for p in paths)
    assert all("cache cap)" in line for line in lines if " deleted " in line)


def _figures(**extra):
    return dict({"budget_bytes": 900 * _GB, "chosen_bytes": 2500 * _GB,
                 "clamped": "", "low_water": 0.9}, **extra)


def test_a_budget_lowered_to_the_disk_says_free_space_ran_it(monkeypatch):
    """The owner's case: a 2500 GB budget on a disk holding less follows
    the disk down (``storage_range.clamp``), so the pass really runs
    because the free space fell under the reserve; the line says so."""
    monkeypatch.setattr(RANGE, "_free_bytes", lambda folder: 40 * _GB)
    why, detail = TOTAL._trigger(_figures(clamped="followed"), 910 * _GB,
                                 100 * _GB)
    assert why.startswith("disk budget (lowered to the disk")
    assert "used 910000000000 bytes over the budget 900000000000" in detail
    assert "set 2500000000000 bytes, followed" in detail
    assert "free space 40000000000 bytes (reserve 50000000000)" in detail
    assert "clearing 100000000000 bytes to 810000000000 bytes" in detail
    why, _detail = TOTAL._trigger(_figures(), 910 * _GB, 100 * _GB)
    assert why == "disk budget"


def test_a_dry_run_writes_no_trigger_line(root):  # noqa: F811
    _write(str(root / "Masks" / "+45+007" / "old.png"), 10, age_days=61)
    sweep = ST._Sweep(True, "automatic cleanup", None)
    sweep.trigger("age rule", "x", now=True)
    sweep.result()
    assert _log(root) == ""
