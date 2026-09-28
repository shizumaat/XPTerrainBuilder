"""Issue #75: the dry ``planar --stage structures`` replay carries the pack
partition.

``pipeline.build`` puts the partition on the ``Airport`` before classify
(``pack_stage``); the dry path never did, so every structure reading that
asks ``airport.partition`` — §34 (12) (5) (a)'s pack-building refusal —
read nothing there (lane ``tunnelwitness2``: OTHH's dry stage listed
``tunnel:-10442`` / ``tunnel:-1355`` that the capture replay and the real
build refuse).  Headless: the stages are stubbed; what is asserted is the
WIRING — the same ``pack_stage``, never writing its cache, feeding the
airport the structure readings see, and a refusal naming the capture
replay when it cannot run.
"""
from __future__ import annotations

import pytest

import importlib

import auto_patch_v2.planar.__main__ as PM

# ``auto_patch_v2.pipeline`` re-exports the FUNCTION ``build``, which
# shadows the submodule on attribute access — take the module itself
PB = importlib.import_module("auto_patch_v2.pipeline.build")


class _Airport:
    icao = "ZZZZ"
    partition = None


def _stub(monkeypatch, tmp_path, pack_stage):
    seen = {}
    monkeypatch.setattr(PM, "default_inputs", lambda *a, **k: "INPUTS")
    monkeypatch.setattr(PM.Law, "for_airport", staticmethod(lambda icao: "LAW"))
    monkeypatch.setattr(PM, "load_with_report",
                        lambda icao, inputs, law: (_Airport(), "LREP"))
    monkeypatch.setattr(PM, "load_rules", lambda: "RULES")

    def _classify(airport, law, rules, cache=None):
        seen["classify"] = (airport, cache)
        return "CL"
    monkeypatch.setattr(PM, "classify", _classify)

    def _records(airport, cl, law):
        seen["records"] = airport
        raise SystemExit(0)          # stop before the writer
    monkeypatch.setattr(PM, "structure_records", _records)
    monkeypatch.setattr(PB, "pack_stage", pack_stage)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(PM, "ENGINE_DIR", tmp_path)
    return seen


def test_the_dry_structures_stage_runs_the_pack_stage(monkeypatch, tmp_path):
    calls = {}

    def _pack_stage(icao, airport, law, inputs, lrep, out=print, *,
                    write_cache=True):
        calls["write_cache"] = write_cache
        a = _Airport()
        a.partition = "PARTITION"
        return {"airport": a, "ocache": "OCACHE"}
    seen = _stub(monkeypatch, tmp_path, _pack_stage)
    with pytest.raises(SystemExit):
        PM.main(["ZZZZ", "--out", str(tmp_path / "o"), "--stage", "structures"])
    assert calls["write_cache"] is False, "a dry replay writes nothing shared"
    assert seen["records"].partition == "PARTITION"
    assert seen["classify"] == (seen["records"], "OCACHE")


def test_a_pack_stage_that_cannot_run_refuses_naming_the_capture(
        monkeypatch, tmp_path):
    def _boom(*a, **k):
        raise RuntimeError("no pack dump")
    _stub(monkeypatch, tmp_path, _boom)
    with pytest.raises(SystemExit) as e:
        PM.main(["ZZZZ", "--out", str(tmp_path / "o"), "--stage", "structures"])
    msg = str(e.value)
    assert "REFUSING" in msg and "v2_solve_replay.py" in msg and "#75" in msg


def test_pack_stage_write_cache_is_a_keyword_defaulting_on():
    import inspect
    p = inspect.signature(PB.pack_stage).parameters["write_cache"]
    assert p.kind is inspect.Parameter.KEYWORD_ONLY and p.default is True
