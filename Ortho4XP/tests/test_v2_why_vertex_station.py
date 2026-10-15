"""Issue #738: ``v2_solve_replay --why-at`` / ``--why-vertex`` printed
``s=nan`` and ``chord+nan`` for a crown-ridge vertex — a NAMED vertex
carried no runway, so its station and chord were seeded NaN (since
0e7bc8fb1, 2026-09-08; it predates the ``solve/why.py`` move).  A named
vertex now reads its station and chord on the runway whose ridge holds it,
and a vertex on no ridge says so.  Offline: fakes, no capture, no solve."""
from __future__ import annotations

import importlib.util
import math
import sys
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))


def _replay():
    spec = importlib.util.spec_from_file_location(
        "_v2_solve_replay_738", ROOT / "tools" / "v2_solve_replay.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _scene():
    """A 1000 m east-west runway, thresholds 10 m and 20 m; ridge chain
    v0..v2 at stations 0 / 400 / 1000; v3 lies off every ridge."""
    ends = (NS(xy=(0.0, 0.0), threshold_elev_m=10.0),
            NS(xy=(1000.0, 0.0), threshold_elev_m=20.0))
    rw = NS(id="09/27", ends=ends)
    xy = [(0.0, 0.0), (400.0, 5.0), (1000.0, 0.0), (500.0, 300.0)]
    pm = NS(vertices=[NS(xy=p, dem_z=12.0) for p in xy])
    z = [10.0, 15.0, 20.0, 30.0]
    return NS(runways=[rw]), pm, z, {"09/27": [[0, 1, 2]]}


def test_ridge_stations_reads_station_and_chord():
    M = _replay()
    airport, pm, z, chains = _scene()
    got = list(M._ridge_stations(pm, airport.runways[0], chains, z))
    assert [v for _a, v, _s in got] == [0, 1, 2]
    above, _v, s = got[1]
    assert s == pytest.approx(400.0) and above == pytest.approx(15.0 - 14.0)
    assert all(math.isfinite(a) and math.isfinite(s) for a, _v, s in got)


class _Stop(Exception):
    pass


@pytest.mark.parametrize("vertex, want", [
    (1, "why 09/27: ridge vertex v1 at s=400  z 15.00  chord+1.00"),
    (3, "why vertex: vertex v3 (on no runway ridge: no station, no chord)"),
])
def test_a_named_vertex_prints_no_nan(monkeypatch, vertex, want):
    M = _replay()
    airport, pm, z, chains = _scene()
    import auto_patch_v2.constraints.precedence as PREC
    import auto_patch_v2.constraints.runway_profile as RP
    import v2_why_solve as WHY
    monkeypatch.setattr(PREC, "view", lambda *_a, **_k: None)
    monkeypatch.setattr(RP, "ridge_chains", lambda _vw: chains)

    def stop(*_a, **_k):
        raise _Stop
    monkeypatch.setattr(WHY, "solve_with_pressure", stop)
    lines: list[str] = []
    with pytest.raises(_Stop):
        M._why_hump("ZZZZ", pm, None, airport, None, z, "", 0.0, 0.0,
                    out=lines.append, vertex=vertex)
    assert want in lines[0] and "nan" not in lines[0]
