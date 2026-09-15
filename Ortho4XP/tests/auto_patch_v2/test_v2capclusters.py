"""Lane ``capclusters`` (2026-09-14; the RULINGS 2026-09-14ax CHIP):
``tools/v2_solve_replay.py``'s capture carries ``airport.clusters`` as
``pipeline/build.py`` carries them, and a replay never reads pads-OFF
silently.

THE DEFECT: the capture pickled the ``Airport`` with its partition and
groups (12u) but never derived the clusters ``build.py`` derives beside
them (``planar/cluster.clusters``), so ``classify/evidence``'s cluster
pads and ``constraints/cluster_pad.cluster_polys`` — both of which read
``airport.clusters`` — found ``None`` in every registered capture, and a
replay with ``[placement] pad_from_cluster = true`` was INERT (lane
``v2padvert``'s HECA re-read note: "Pads-ON was NOT measurable off this
capture").

1. the capture derives the clusters BEFORE ``classify`` (the build's
   order — the pads are minted inside classify) and carries them;
2. a capture of a synthetic airport with ONE cluster replays with
   ``airport.clusters`` non-empty and ``cluster_polys`` returning it;
3. a pre-fix capture (no clusters) replays with a printed WARNING naming
   the gap — never silently — re-deriving from its carried partition by
   the build's own call, or saying there is nothing to derive from.
"""
from __future__ import annotations

import ast
import dataclasses as _dc
import importlib.util
import inspect
import pickle
from pathlib import Path

import pytest

from auto_patch_v2.law import Law
from auto_patch_v2.model.airport import Airport, Runway, RunwayEnd, SceneryPack
from auto_patch_v2.model.frame import Frame

_TOOL = Path(__file__).resolve().parents[2] / "tools" / "v2_solve_replay.py"
PAD = (-120.0, 200.0, -20.0, 280.0)


def _replay_module():
    spec = importlib.util.spec_from_file_location("_v2_solve_replay_cc", _TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


class _Dem:
    provenance = {"synthetic": "flat"}

    def z(self, x: float, y: float) -> float:
        return 700.0

    def bounds(self):
        return (-5000.0, -5000.0, 5000.0, 5000.0)


def _airport(law) -> Airport:
    frame = Frame("ZZZZ", origin=(60.5, -135.5), identity_dp=11)
    ends = (RunwayEnd("09", (-800.0, 0.0), (60.5, -135.5), 0.0, 0.0, 700.0, "fixture"),
            RunwayEnd("27", (800.0, 0.0), (60.5, -135.5), 0.0, 0.0, 700.0, "fixture"))
    rw = Runway("09/27", 45.0, 1, ends, 3, "D")
    pack = SceneryPack("fixture", "apt.dat", "0", (), ())
    return Airport("ZZZZ", "Synthetic", frame, 700.0, (rw,), (), (), {}, (),
                   (), (), (), (), (), (), pack, _Dem(), law.ruleset_key)


@_dc.dataclass
class _Cluster:
    """What ``planar/cluster.py`` puts on ``Airport.clusters`` — one
    WALLED body with a footprint ring (the field every reader uses)."""
    id: str
    unit: str
    members: tuple
    boxes: tuple
    area_m2: float
    hull: tuple
    floors: tuple
    rings: tuple
    bodies: int
    footed: int
    walled: int


def _one_cluster(airport: Airport) -> _Cluster:
    _to_xy, to_ll = airport.frame.transformers()
    x0, y0, x1, y1 = PAD
    ring = tuple(to_ll(x, y) for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)))
    la0, lo0 = to_ll(x0, y0)
    la1, lo1 = to_ll(x1, y1)
    box = (min(la0, la1), min(lo0, lo1), max(la0, la1), max(lo0, lo1))
    return _Cluster("unit:1#0", "unit:1", ("objects/wall.obj",), (box,), 8000.0,
                    box, (0.0,), (ring,), 1, 1, 1)


def _cap(airport: Airport) -> dict:
    """A capture dict round-tripped through pickle, as the replay reads it."""
    return pickle.loads(pickle.dumps({"icao": "ZZZZ", "airport": airport}))


# ── 1. the capture derives the clusters, before classify ────────────────

def test_the_capture_derives_the_clusters_before_classify():
    mod = _replay_module()
    src = inspect.getsource(mod.capture)
    tree = ast.parse(src)
    order: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            f = node.func
            name = f.id if isinstance(f, ast.Name) else getattr(f, "attr", "")
            if name in ("_derive_clusters", "classify"):
                order.append((node.lineno, name))
    order.sort()
    names = [n for _l, n in order]
    assert "_derive_clusters" in names, "the capture never derives the clusters"
    assert names.index("_derive_clusters") < names.index("classify"), (
        "the clusters must be on the airport BEFORE classify mints the pads")
    # and they are CARRIED on the airport the capture pickles
    assert "clusters=_clusters" in src


# ── 2. a one-cluster capture replays with the cluster readable ──────────

def test_a_captured_cluster_replays_and_cluster_polys_returns_it(law, capsys):
    from auto_patch_v2.constraints.cluster_pad import cluster_polys
    mod = _replay_module()
    airport = _airport(law)
    airport = _dc.replace(airport, partition=object(), groups=object(),
                          clusters=(_one_cluster(airport),))
    cap = _cap(airport)
    assert mod.capture_has_clusters(cap) is True
    got = mod.restore_clusters(cap, law)
    assert got.clusters and got.clusters[0].id == "unit:1#0"
    assert got is cap["airport"], "a carried capture is returned byte-faithful"
    assert "WARNING" not in capsys.readouterr().out
    polys = cluster_polys(got, 0.0, 0.5)
    assert [c.id for _i, c, _g in polys] == ["unit:1#0"], polys
    assert polys[0][2].area == pytest.approx(8000.0, rel=1e-3)


def test_an_empty_cluster_set_is_a_measurement_not_a_gap(law, capsys):
    """KCLT-style: the derivation ran and found none — carried as ``()``,
    never mistaken for a pre-fix capture."""
    mod = _replay_module()
    airport = _dc.replace(_airport(law), partition=object(), groups=object(),
                          clusters=())
    cap = _cap(airport)
    assert mod.capture_has_clusters(cap) is True
    assert mod.restore_clusters(cap, law).clusters == ()
    assert "WARNING" not in capsys.readouterr().out


# ── 3. a pre-fix capture warns by name, never silently ──────────────────

def test_a_pre_fix_capture_re_derives_with_a_warning_naming_the_gap(law, monkeypatch,
                                                                     capsys):
    import auto_patch_v2.planar.cluster as _pc
    mod = _replay_module()
    airport = _airport(law)
    marker = (_one_cluster(airport),)
    seen: list = []

    def _fake(ap, lw):
        seen.append((ap, lw))
        return marker

    monkeypatch.setattr(_pc, "clusters", _fake)
    pre = _dc.replace(airport, partition=object(), groups=object())     # 12u-era
    cap = _cap(pre)
    assert mod.capture_has_clusters(cap) is False
    got = mod.restore_clusters(cap, law)
    out = capsys.readouterr().out
    assert "WARNING" in out and "airport.clusters" in out and "RE-DERIVED" in out
    assert "capclusters" in out
    assert got.clusters == marker
    assert len(seen) == 1 and seen[0][0].partition is not None and seen[0][1] is law


def test_a_capture_with_nothing_to_derive_from_warns_pads_off(law, capsys):
    mod = _replay_module()
    cap = _cap(_airport(law))                                   # no partition
    got = mod.restore_clusters(cap, law)
    out = capsys.readouterr().out
    assert "WARNING" in out and "pads-OFF" in out and "re-capture" in out
    assert got.clusters is None
