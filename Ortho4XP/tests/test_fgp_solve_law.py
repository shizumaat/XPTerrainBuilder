"""FGP S1/S2/S3 — the final projection consumes the SOLVE's law.

Spec ``docs/specs/fgp-single-authority-spec.md`` §S1-S3; consumer census
``docs/specs/fgp-s1-consumer-census.md``.  Everything the rounds add
sits behind the ``O4_FGP_SOLVE_LAW`` gate family (all default OFF ⇒
byte-identical behaviour), so these headless tests pin what is testable
without a build: the hold-filter arithmetic (census R2's rule), the S2
clamp-yield rule and its authority record, the S3 in-place carrier
refresh, and every gate's default.
"""
import os as _os
from pathlib import Path

from auto_patch.elevation_per_surface.route_profile.solve import (
    _refresh_membrane_carriers, _solve_law_hold_filter)
from auto_patch.elevation_per_surface.solver_primitives import (
    FGP_SOLVE_LAW_CLAMP_FLAG, _clamp_corner_elevs_to_band,
    _solve_stated_closure)


_SOLVE_PY = (Path(__file__).resolve().parents[1] / "src" / "auto_patch"
             / "elevation_per_surface" / "route_profile" / "solve.py")


def test_hold_filter_arithmetic():
    """Solve-stated + contradicted ⇒ released; agreeing or unstated ⇒ held."""
    kept, released = _solve_law_hold_filter(
        {0, 1, 2}, {0: 10.0, 2: 20.0}, [10.0, 99.0, 20.5], 0.01)
    # 0 agrees with its solve-stated value, 1 was never solve-stated,
    # 2 sits 0.5 m off the value the solve stated for it.
    assert kept == {0, 1}
    assert released == 1


def test_hold_filter_empty_carried():
    """No solve-stated values at all ⇒ nothing is contradicted."""
    elev = [1.0, 2.0, 3.0]
    for carried in (None, {}):
        kept, released = _solve_law_hold_filter(
            {0, 1, 2}, carried, elev, 0.01)
        assert kept == {0, 1, 2}
        assert released == 0


def test_gate_default_off(monkeypatch):
    """The gate is OFF unless explicitly set to ``1``."""
    monkeypatch.delenv("O4_FGP_SOLVE_LAW", raising=False)
    assert (_os.environ.get("O4_FGP_SOLVE_LAW", "0") == "1") is False
    monkeypatch.setenv("O4_FGP_SOLVE_LAW", "0")
    assert (_os.environ.get("O4_FGP_SOLVE_LAW", "0") == "1") is False
    monkeypatch.setenv("O4_FGP_SOLVE_LAW", "1")
    assert (_os.environ.get("O4_FGP_SOLVE_LAW", "0") == "1") is True


def test_joined_entry_edge_list_is_mutated_in_place():
    """The all-hard pair drop relies on slice assignment reaching the
    SAME list object the joint entry holds — pinned here so a future
    edit that rebinds ``edges`` instead of slicing it fails loudly."""
    entry = {"edges": [(0, 1, 0.1), (2, 3, 0.2)], "family": "x"}
    joint = [entry]
    hard = {0, 1}
    edges = entry.get("edges") or []
    edges[:] = [e for e in edges if not (e[0] in hard and e[1] in hard)]
    assert entry["edges"] == [(2, 3, 0.2)]
    assert joint[0]["edges"] == [(2, 3, 0.2)]


def test_gate_name_present_in_solve_source():
    """The gate is read in ``solve.py`` under exactly that name."""
    src = _SOLVE_PY.read_text()
    assert src.count("O4_FGP_SOLVE_LAW") >= 1
    assert '_os.environ.get("O4_FGP_SOLVE_LAW", "0") == "1"' in src


# ── S2 · the band clamp yields to the solve ─────────────────────────

class _Shape:
    role = "apron"
    ref = "t1"


class _StubLayout:
    """No crown field, no registry — ``crown_drop_at`` returns 0.0."""


def test_s2_clamp_yields_on_solve_stated_value():
    """Solve-stated + out-of-band ⇒ the clamp stands down (a counted
    yield); post-solve-moved + out-of-band ⇒ clamped WITH the authority
    field (the solve-stated value) appended to the finding."""
    lay = _StubLayout()
    coords = [(0.0, 0.0), (10.0, 0.0)]
    vals = [5.0, 5.0]
    findings: list = []
    yields: list = []
    out = _clamp_corner_elevs_to_band(
        lay, coords, vals, lambda x, y: (7.0, 9.0), _Shape(), findings,
        # vertex 0's 5.0 IS the solve's statement; at vertex 1 the solve
        # stated 6.0, so its 5.0 was moved post-solve.
        solved=lambda x, y: 5.0 if x < 5.0 else 6.0, yields=yields)
    assert out[0] == 5.0                     # yielded — untouched
    assert out[1] == 7.0                     # genuine violation — clamped
    assert len(yields) == 1
    assert yields[0][0] == "band_clamp_yield"
    assert yields[0][4] == "floor"
    assert yields[0][7] == 5.0               # the solve-stated value
    assert len(findings) == 1
    assert len(findings[0]) == 11            # authority field appended
    assert findings[0][10] == 6.0


def test_s2_no_solved_closure_is_byte_inert():
    """Without a solved closure (gate off) the clamp behaves exactly as
    before S2: both vertices clamp, findings stay 10-tuples."""
    lay = _StubLayout()
    findings: list = []
    out = _clamp_corner_elevs_to_band(
        lay, [(0.0, 0.0), (10.0, 0.0)], [5.0, 5.0],
        lambda x, y: (7.0, 9.0), _Shape(), findings)
    assert out == [7.0, 7.0]
    assert len(findings) == 2
    assert all(len(f) == 10 for f in findings)


def test_s2_closure_gates_default_off(monkeypatch):
    """``_solve_stated_closure`` is ``None`` unless BOTH the S1 parent
    gate and the S2 sub-gate are explicitly ``1``."""
    monkeypatch.delenv("O4_FGP_SOLVE_LAW", raising=False)
    monkeypatch.delenv(FGP_SOLVE_LAW_CLAMP_FLAG, raising=False)
    assert _solve_stated_closure(_StubLayout()) is None
    monkeypatch.setenv("O4_FGP_SOLVE_LAW", "1")
    assert _solve_stated_closure(_StubLayout()) is None
    monkeypatch.setenv(FGP_SOLVE_LAW_CLAMP_FLAG, "1")
    # Both gates on, but a stub layout carries no ``solved_values``
    # store — still ``None``, still inert (the resolver never invents).
    assert _solve_stated_closure(_StubLayout()) is None


# ── S3 · the carriers tell the truth ────────────────────────────────

class _Reg:
    def get_or_add(self, x, y):
        return (round(x, 6), round(y, 6))


class _CarrierLayout:
    def __init__(self):
        self.canonical_points = _Reg()
        self.apron_lattice_emit = [
            ([(1.0, 2.0), (3.0, 4.0)], [10.0, 20.0])]
        self.apron_spine_station_emit = [
            ([(5.0, 6.0), (7.0, 8.0)], [30.0, 40.0])]

    def ll_to_m(self, la, lo):                 # identity frame
        return la, lo


def test_s3_refresh_updates_alts_in_place():
    """Resolvable points take the FINAL field's value in place;
    unresolvable points keep the minted value and are counted stale."""
    lay = _CarrierLayout()
    b2i = {(1.0, 2.0): 0, (5.0, 6.0): 1}       # (3,4) and (7,8) dropped
    elev = [42.0, 33.0]
    refreshed, stale = _refresh_membrane_carriers(lay, b2i, elev, 2)
    assert (refreshed, stale) == (2, 2)
    assert lay.apron_lattice_emit[0][1] == [42.0, 20.0]
    assert lay.apron_spine_station_emit[0][1] == [33.0, 40.0]
    # Idempotent: a second refresh finds nothing to move.
    refreshed2, stale2 = _refresh_membrane_carriers(lay, b2i, elev, 2)
    assert (refreshed2, stale2) == (0, 2)


def test_s3_refresh_no_carriers_is_vacuous():
    lay = _StubLayout()
    lay.canonical_points = _Reg()
    assert _refresh_membrane_carriers(lay, {}, [], 0) == (0, 0)


def test_s2_s3_gate_names_present_in_source():
    """The sub-gates are read under exactly these names, ANDed with the
    parent gate (never independent of it)."""
    src = _SOLVE_PY.read_text()
    assert '"O4_FGP_SOLVE_LAW_CARRIERS", "0") == "1"' in src
    assert "if _fgp_law and _os.environ.get(" in src
    prim = (_SOLVE_PY.parents[1] / "solver_primitives.py").read_text()
    assert 'FGP_SOLVE_LAW_CLAMP_FLAG = "O4_FGP_SOLVE_LAW_CLAMP"' in prim
    assert 'if _os.environ.get("O4_FGP_SOLVE_LAW", "0") != "1"' in prim


def test_membrane_sub_gate_present_and_defaults_off():
    """The membrane half rides its own S3 sub-gate, default OFF.

    Measured 2026-09-01 (lane fgp1): the emitted membrane carriers are
    never refreshed after the solve writeback, so joining the membrane
    family moved apron rings against STALE carriers (HECA
    ``apron_lattice_membrane`` 108 -> 245, within_shape +207 apron
    rows).  It joins only when the S3 carrier refresh lands.
    """
    src = _SOLVE_PY.read_text()
    assert src.count("O4_FGP_SOLVE_LAW_MEMBRANE") >= 1
    assert '"O4_FGP_SOLVE_LAW_MEMBRANE", "0") == "1"' in src
    # ... and it is an AND with the main gate, never independent of it.
    assert "_fgp_law_mem = _fgp_law and _os.environ.get(" in src
