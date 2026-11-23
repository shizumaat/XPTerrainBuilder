"""#2206: ``build_evidence`` with a law and no cache reads the pack ONCE.

Both ``_pads`` passes must receive one ``ResourceCache``.  Without it each
pass re-read the whole pack, and ``declared_jetways`` (which needs a cache
to measure an ``.obj`` jetway) read a different pad set from the build.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from auto_patch_v2.airport.obj8 import ResourceCache  # noqa: E402
from auto_patch_v2.classify import evidence as _ev, load_rules  # noqa: E402
from auto_patch_v2.law import Law  # noqa: E402
from test_classify import _synthetic  # noqa: E402


def _caches_seen(monkeypatch, law, cache=None) -> list:
    seen: list = []

    def pads(_airport, _rules, _min, _boundary, _pav, _rwy, _law, got, **_kw):
        seen.append(got)
        return [], 0, []

    monkeypatch.setattr(_ev, "_pads", pads)
    monkeypatch.setattr(_ev, "slope_witness", lambda *_a: object())
    _ev.build_evidence(_synthetic(gate=True), load_rules(),
                       law.tables.structures.building_pad.min_area_m2, law, cache)
    return seen


def test_both_pad_passes_share_one_cache(monkeypatch):
    seen = _caches_seen(monkeypatch, Law.for_airport("TEST"))
    assert len(seen) == 2
    assert isinstance(seen[0], ResourceCache) and seen[0] is seen[1]


def test_a_callers_cache_is_the_one_used(monkeypatch):
    law = Law.for_airport("TEST")
    own = ResourceCache(law.tables.structures.basin.min_solid_thickness_m)
    assert _caches_seen(monkeypatch, law, own) == [own, own]
