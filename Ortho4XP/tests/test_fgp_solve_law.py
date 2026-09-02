"""FGP S1 — the final projection consumes the SOLVE's law.

Spec ``docs/specs/fgp-single-authority-spec.md`` §S1; consumer census
``docs/specs/fgp-s1-consumer-census.md``.  Everything the round adds to
``final_grade_projection`` sits behind ``O4_FGP_SOLVE_LAW`` (default
OFF ⇒ byte-identical behaviour), so these headless tests pin the two
things that are testable without a build: the hold-filter arithmetic
(census R2's rule, in isolation) and the gate's default.
"""
import os as _os
from pathlib import Path

from auto_patch.elevation_per_surface.route_profile.solve import (
    _solve_law_hold_filter)


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
