"""THE GEOMETRY FREEZE (owner direction 2026-08-13, staged-solve round S1).

    All plan geometry the solve consumes is COMPLETED before any elevation
    solving — a NAMED FREEZE POINT after which no construction may add,
    move, or split solve-consumed geometry.

This module owns that point.  It is deliberately small: a signature, a
publication, and a rail.

WHY A RAIL AND NOT A CONVENTION.  Before the freeze, six unified graphs
were built per HECA solve (S1 phase-1 attribution, ``tmp/s1_attribution.md``
§1(c)), each on geometry a later pass had already moved.  The failure mode
is silent by construction: a pass that splits an apron or decimates a ring
AFTER a graph was built does not raise — the graph simply describes a
layout that no longer exists, and every value derived from it is off by
whatever the mutation changed.  ``assert_frozen`` turns that into a
traceback naming the shape.

WHAT IS FROZEN.  The SOLVE-CONSUMED plan geometry: for every shape the
solver's node list interns, its role and its exterior ring coordinates.
Altitudes are NOT frozen (the solve's whole job is to move them), and
neither are the pre-solve construction STORES (``gap_fill_presolve``,
``adjacent_ground_presolve``) — those hold solver variables that lie on no
ring, so they cannot change the graph (see ``publish`` below).

WHAT IS *NOT* IN SCOPE, AND WHY (phase-1 verdicts, all named in
``tmp/s1_attribution.md`` §1(b)):

  * the runway FAA vertical profile runs BEFORE this point and its values
    ARE read by the pre-solve bands (``grade_graph.py:3527``,
    ``_sample_runway_segment_elev``).  CIFP thresholds are LOCKED
    (``pipeline.py`` "the solver never moves them"), so the profile is
    pinned stage-A input, not a solve product — the freeze sits after it.
  * the apron-terrace PANEL SPLIT is itself band-triggered and is
    inherently per-stage: it must run before the freeze, and its band must
    therefore be built before the freeze.  That build is the one graph
    this module does not collapse.

Spec: ``docs/specs/staged-solve-round-spec.md`` S1 + "The law this round
lands".  Rulings: RULINGS.md "PERFORMANCE PHASE OPENED" (frozen baseline),
"Airside is king".
"""
from __future__ import annotations

from typing import Any, Optional

# Ring coordinates are compared at 1e-6 m — far below every materiality
# floor in the round (0.01 m) and far above float-repr noise, so a
# signature mismatch is always a real mutation, never a rounding artifact.
_COORD_Q = 6


class GeometryFreezeViolation(RuntimeError):
    """A pass mutated solve-consumed plan geometry after the freeze point.

    Deliberately a ``RuntimeError``: ``pipeline``'s ``_GEOM_EXC`` wrapper
    catches ``ValueError`` + shapely errors, and a freeze violation must
    NOT be swallowed into a degraded build (the fail-loudly doctrine that
    the gate-dependency checks in ``gap_fill``/``pipeline`` already use).
    """


def _ring_signature(layout) -> tuple:
    """The solve-consumed plan geometry, as a comparable value.

    One entry per shape the unified graph could see, in ``layout.shapes``
    order: ``(role, ref, n_vertices, quantised exterior ring)``.  Order is
    part of the signature — a reordered ``layout.shapes`` changes node
    interning order and therefore the whole index space.
    """
    sig: list = []
    for s in layout.shapes:
        poly = getattr(s, "polygon", None)
        if poly is None or poly.is_empty:
            sig.append((s.role, getattr(s, "ref", None), 0, ()))
            continue
        try:
            if poly.geom_type == "Polygon":
                rings = (poly.exterior,)
            else:
                rings = tuple(g.exterior for g in poly.geoms)
            coords = tuple(
                (round(float(x), _COORD_Q), round(float(y), _COORD_Q))
                for r in rings for (x, y) in r.coords)
        except Exception:              # pragma: no cover - degenerate geom
            coords = ()
        sig.append((s.role, getattr(s, "ref", None), len(coords), coords))
    return tuple(sig)


def freeze(layout, icao: str = "") -> None:
    """THE FREEZE POINT.  Record the solve-consumed plan geometry.

    Call once, after the last construction that may add/move/split a ring
    and before the first consumer of the one graph.  Idempotent: a second
    call on unchanged geometry is a no-op; on CHANGED geometry it raises,
    because that is the violation this exists to catch.
    """
    sig = _ring_signature(layout)
    prev = getattr(layout, "_geometry_freeze_sig", None)
    if prev is not None and prev != sig:
        raise GeometryFreezeViolation(_diff_message(prev, sig, layout))
    layout._geometry_freeze_sig = sig
    layout._geometry_freeze_icao = icao


def is_frozen(layout) -> bool:
    return getattr(layout, "_geometry_freeze_sig", None) is not None


def assert_frozen(layout, where: str) -> None:
    """THE RAIL.  Fail if solve-consumed geometry moved since :func:`freeze`.

    ``where`` names the call site, so the traceback says which consumer
    caught it, and :func:`_diff_message` says which shape moved.  A no-op
    (one ``getattr``) when nothing has been frozen — so importing this
    module never changes a build that does not call :func:`freeze`.
    """
    prev = getattr(layout, "_geometry_freeze_sig", None)
    if prev is None:
        return
    sig = _ring_signature(layout)
    if sig != prev:
        raise GeometryFreezeViolation(
            f"[geometry-freeze] {where}: " + _diff_message(prev, sig, layout))


def _diff_message(prev: tuple, now: tuple, layout) -> str:
    """Name the first divergence — a count, or the first shape that moved."""
    if len(prev) != len(now):
        return (f"the shape COUNT changed after the freeze point: "
                f"{len(prev)} -> {len(now)} (a construction added or "
                f"dropped a shape the solver consumes).")
    for i, (a, b) in enumerate(zip(prev, now)):
        if a == b:
            continue
        role_a, ref_a, n_a, _ = a
        role_b, ref_b, n_b, _ = b
        if (role_a, ref_a) != (role_b, ref_b):
            what = f"role/ref {role_a}/{ref_a} -> {role_b}/{ref_b}"
        elif n_a != n_b:
            what = f"vertex count {n_a} -> {n_b}"
        else:
            what = "vertex POSITIONS moved (same count)"
        return (f"shape index {i} ({role_b}) changed after the freeze "
                f"point: {what}.  Solve-consumed plan geometry is frozen "
                f"at the freeze point; a construction that must change it "
                f"belongs BEFORE the freeze, and an elevation-dependent "
                f"emitter belongs after the solve and must be "
                f"ADDITIVE-ONLY.")
    return "signature changed but no shape differs (internal inconsistency)."


# ── THE ONE GRAPH, PUBLISHED AT THE FREEZE ───────────────────────────────

def publish(layout, *, nodes, bucket_to_idx, ctx, graph, band) -> None:
    """Publish the frozen node space, context, graph and band on ``layout``.

    Kept as plain attributes rather than a dataclass so the layout stays
    picklable for ``solve_capture`` without a schema bump.
    """
    layout._frozen_nodes = nodes
    layout._frozen_bucket_to_idx = bucket_to_idx
    layout._frozen_ctx = ctx
    layout._frozen_graph = graph
    layout._frozen_band = band


def frozen_band(layout, where: str):
    """The frozen reach band, or ``None`` if none was published.

    Checks the rail first: handing out a band derived from geometry that
    has since moved is exactly the silent failure the freeze exists to
    stop, so the check is HERE and not left to the caller.
    """
    band = getattr(layout, "_frozen_band", None)
    if band is None:
        return None
    assert_frozen(layout, where)
    return band


def frozen_graph(layout, where: str):
    """``(nodes, bucket_to_idx, ctx, graph)`` or ``None``.  Rail-checked."""
    graph = getattr(layout, "_frozen_graph", None)
    if graph is None:
        return None
    assert_frozen(layout, where)
    return (layout._frozen_nodes, layout._frozen_bucket_to_idx,
            layout._frozen_ctx, graph)


def clear(layout) -> None:
    """Release the freeze (post-solve emission is ADDITIVE and lawful).

    The post-solve phase legitimately adds bands, spines, walls and cuts;
    they are emitted CONFORMING to the solved field and never feed back
    into it, so the rail is lifted once the solve has run.  Everything the
    freeze published is dropped with it — a stale graph must not survive
    into phase [6], where the two ``final_grade_projection`` builds
    legitimately rebuild on mutated geometry.
    """
    for attr in ("_geometry_freeze_sig", "_geometry_freeze_icao",
                 "_frozen_nodes", "_frozen_bucket_to_idx", "_frozen_ctx",
                 "_frozen_graph", "_frozen_band"):
        if hasattr(layout, attr):
            try:
                delattr(layout, attr)
            except AttributeError:                        # pragma: no cover
                pass
