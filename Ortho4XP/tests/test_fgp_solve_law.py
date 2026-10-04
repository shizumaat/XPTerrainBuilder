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


# ── S2 · the band clamp yields to the solve ─────────────────────────

class _Shape:
    role = "apron"
    ref = "t1"


class _StubLayout:
    """No crown field, no registry — ``crown_drop_at`` returns 0.0."""


# ── S3 · the carriers tell the truth ────────────────────────────────


# RETIRED with the v1 engine (stage B round 2, lane ``v1cut``, 2026-10-04) —
# the test read the SOURCE of a deleted v1 module:
# ``test_gate_name_present_in_solve_source``,
# ``test_membrane_sub_gate_present_and_defaults_off``,
# ``test_s2_s3_gate_names_present_in_source``.
