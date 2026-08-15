"""THE SOLVE-MODEL SWITCH (constructive-solve round, K1).

One cfg key ``solve_model`` (spec ``docs/specs/constructive-solve-spec.md``,
"Mode plumbing"): values ``iterative`` | ``constructive``, DEFAULT
``iterative`` until the owner rules after the in-sim A/B.  Flipping the mode
changes ONLY the solve core — the anchor assembly, the law objects, the
writeback/publication tail and every consumer are shared (mode isolation is
a hard acceptance gate: an iterative build must be byte-identical to a
pre-round build).

THE K2 INTERFACE (lane K2 lands the full plumbing — cfg registry entry,
per-tile override, harness ``frame.json`` / artifact-ledger variant key, UI
selector).  This module is the ONE dispatch-site constant both lanes agreed
on: K2's plumbing delivers the resolved cfg value by EITHER

  * setting ``layout.solve_model`` (string) on the ``PavementLayout``
    before ``per_surface_solve`` runs, or
  * exporting ``O4_SOLVE_MODEL`` into the engine build environment
    (the env fallback that makes K1 testable before K2 merges).

``resolve`` reads the layout attribute first (cfg wins over env), then the
env var, then the default.  An unknown value is a loud WARN + the default,
never a silent third mode.
"""
from __future__ import annotations

import os

#: The cfg key K2 plumbs (global + per-tile).  Read here and nowhere else.
SOLVE_MODEL_KEY = "solve_model"

#: The two models.  Two models = two artifacts (ledger variant key, K2).
MODEL_ITERATIVE = "iterative"
MODEL_CONSTRUCTIVE = "constructive"
MODELS = (MODEL_ITERATIVE, MODEL_CONSTRUCTIVE)

#: Owner default until the in-sim A/B rules (spec "Mode plumbing").
DEFAULT_MODEL = MODEL_ITERATIVE

#: Env fallback so a lane can flip the mode without the cfg plumbing.
SOLVE_MODEL_ENV = "O4_SOLVE_MODEL"


def resolve(layout=None) -> str:
    """Resolve the solve model for this build: layout attr > env > default.

    Never raises: an unrecognised value WARNs once (stdout, the UI contract)
    and falls back to :data:`DEFAULT_MODEL` so a typo'd cfg cannot invent a
    third solver.
    """
    raw = None
    if layout is not None:
        raw = getattr(layout, SOLVE_MODEL_KEY, None)
    if not raw:
        raw = os.environ.get(SOLVE_MODEL_ENV)
    if not raw:
        return DEFAULT_MODEL
    val = str(raw).strip().lower()
    if val not in MODELS:
        try:
            import O4_UI_Utils as UI
            UI.vprint(0, f"  [solve-model] WARN: unknown solve_model "
                         f"{raw!r} — using {DEFAULT_MODEL!r} "
                         f"(known: {', '.join(MODELS)})")
        except Exception:                              # pragma: no cover
            pass
        return DEFAULT_MODEL
    return val
