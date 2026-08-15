"""THE SOLVE MODEL — which elevation solve a build runs, and who decided.

`docs/specs/constructive-solve-spec.md`, section "Mode plumbing":

    One cfg key ``solve_model`` (global + per-tile, values ``iterative`` |
    ``constructive``), DEFAULT ``iterative`` until the owner rules after
    the A/B.  Engine reads it at solve dispatch; harness passes/records
    it in frame.json and the artifact-ledger variant key (two models =
    two artifacts, never served for each other); the Qt and Swift UIs
    expose it as a simple selector (engine-owns-features law).  Censuses
    and sidecars identical in both modes.

THE ONE READER.  Every consumer — the engine's solve dispatch, the
harness's frame record and artifact-ledger variant, the reporting in
between — resolves the mode through :func:`resolve` here.  A second
"read the cfg, then check the env" implementation somewhere else is the
census-wrapper defect in a smaller costume: two readers disagree the
first time a precedence rule changes, and the disagreement is silent
because both answers are valid modes.

THE PRECEDENCE, highest first
-----------------------------
1. ``O4_SOLVE_MODEL`` in the environment — THE LANE ARM.  An A/B arm
   must be able to pin the mode without editing a config file that the
   frame checker then reports as a divergence, and without the two arms
   racing each other's writes to a shared cfg.  An unparseable value
   here RAISES: an arm that meant ``constructive`` and silently measured
   ``iterative`` would publish the wrong verdict.
2. The PER-TILE cfg value (``Ortho4XP_+XX+YYY.cfg``) — the tile the
   build is for, when there is one.
3. The GLOBAL cfg value (``Ortho4XP.cfg``).
4. :data:`DEFAULT` — ``iterative``, until the owner rules after the
   in-sim A/B.

2 over 3 is exactly how every other tile var behaves (``O4_Config_Utils``
seeds each ``Tile`` attribute from the global scope, then
``Tile.read_from_config`` overwrites it from the per-tile file), so the
key needs no special case anywhere: registering it in
``O4_Cfg_Vars.cfg_tile_vars`` is what gives it both scopes.

This module deliberately imports NOTHING heavy — ``os`` only, and
``O4_Config_Utils`` lazily inside :func:`live_global_cfg_value`.  The
harness computes the artifact-ledger key BEFORE any engine module is
imported (the guard-arming order), so a reader it cannot import without
dragging the engine in would be a reader it could not use.
"""
from __future__ import annotations

import os

#: The environment override.  Named here once; every consumer imports it
#: rather than spelling the string again (the wire-protocol lesson: a
#: literal that appears in two languages appears in neither's grep).
ENV_VAR = "O4_SOLVE_MODEL"

#: The settings-registry key (``O4_Cfg_Vars.cfg_tile_vars``).
CFG_KEY = "solve_model"

#: The iterative model: today's solve — the per-surface field solver
#: optimising toward DEM fidelity under the law.
ITERATIVE = "iterative"

#: The constructive model: the sub-minute lawful-by-construction solve
#: (spec sections C1-C5), landed beside the iterative one behind this key.
CONSTRUCTIVE = "constructive"

#: Every value the key accepts, in menu order.
MODELS = (ITERATIVE, CONSTRUCTIVE)

#: The default until the owner rules after the in-sim A/B (spec §"Mode
#: plumbing": "DEFAULT ``iterative`` until the owner rules after the A/B").
DEFAULT = ITERATIVE

#: Sentinel distinguishing "no value from this source" from ``None``-the-
#: value; callers pass ``None`` freely and it means the same thing here,
#: but the sentinel keeps :func:`resolve`'s signature honest.
_UNSET = object()

#: The source names :func:`provenance` reports, in precedence order.
SOURCES = ("env", "tile_cfg", "global_cfg", "default")


class SolveModelError(ValueError):
    """An unparseable solve model — raised, never defaulted around.

    Defaulting a typo would run the OTHER model and report the numbers
    as if they were the requested one's.  A build is cheap to re-launch;
    a mis-attributed A/B arm is not.
    """


def normalise(value, *, where: str = "value"):
    """``value`` as a canonical model name, or ``None`` when it is empty.

    Whitespace and case are forgiven (a cfg file typed by hand, an env
    var exported with a trailing space); an unknown non-empty token is
    NOT — it raises :class:`SolveModelError` naming ``where`` and the
    accepted values.
    """
    if value is None or value is _UNSET:
        return None
    text = str(value).strip().strip("'\"").lower()
    if not text:
        return None
    if text not in MODELS:
        raise SolveModelError(
            f"{where}: {value!r} is not a solve model.  Accepted values are "
            f"{' | '.join(MODELS)} (see docs/specs/constructive-solve-spec.md, "
            f"'Mode plumbing').")
    return text


def resolve(*, environ=None, tile_cfg=_UNSET, global_cfg=_UNSET) -> str:
    """The effective solve model.  THE precedence, implemented once.

    Every source is a parameter, so a caller supplies whichever it can
    actually see — the engine reads live module state, the harness reads
    the cfg FILES it has already parsed — and neither re-implements the
    ordering.  See the module docstring for the ordering itself.
    """
    return provenance(environ=environ, tile_cfg=tile_cfg,
                      global_cfg=global_cfg)["solve_model"]


def provenance(*, environ=None, tile_cfg=_UNSET, global_cfg=_UNSET) -> dict:
    """``{"solve_model", "source", "env", "tile_cfg", "global_cfg"}``.

    WHICH source decided is recorded beside the answer because the two
    questions a later reader asks about an A/B arm are "which model" and
    "did my override actually take" — and a bare mode string answers only
    the first.  This dict is what goes into ``frame.json`` /
    ``result.json``; the ledger variant key carries ``solve_model`` alone
    (a mode reached from the env and the same mode reached from the cfg
    produce the SAME artifact, so they must not split the key).
    """
    env = os.environ if environ is None else environ
    values = {
        "env": normalise(env.get(ENV_VAR), where=f"{ENV_VAR} (environment)"),
        "tile_cfg": normalise(tile_cfg, where=f"{CFG_KEY} (per-tile cfg)"),
        "global_cfg": normalise(global_cfg, where=f"{CFG_KEY} (global cfg)"),
    }
    for source in SOURCES[:-1]:
        if values[source] is not None:
            return dict(values, solve_model=values[source], source=source)
    return dict(values, solve_model=DEFAULT, source="default")


def live_global_cfg_value():
    """The global cfg's ``solve_model``, from the live engine config.

    Read through ``O4_Config_Utils``' module attribute — the surface both
    cfg loaders write — with a getattr default, so a frozen engine, a
    bare test process or a tree predating the key all read ``None``
    rather than raising.  (The idiom is ``auto_patch.flat_site._cfg_value``'s;
    the reason it is spelled again rather than imported is that
    ``flat_site`` drags the whole pavement package in, and this module is
    imported by the harness before the engine exists.)

    ONE CAVEAT, and it is why the harness records its OWN provenance
    rather than this one: ``O4_Config_Utils`` seeds every registry key to
    its default before reading any file, so this attribute exists whether
    or not the cfg names the key.  The VALUE is therefore always right and
    the ``source`` label is always at least ``global_cfg`` — never
    ``default`` — from inside the engine.  The harness reads the cfg FILES
    and so can tell the two apart; ``frame.json`` carries that record.
    """
    try:
        import O4_Config_Utils as _CFG                     # noqa: PLC0415
    except Exception:                                      # pragma: no cover
        return None
    return getattr(_CFG, CFG_KEY, None) or None


def current(tile=None) -> str:
    """The solve model for the build running NOW — the engine's entry.

    ``tile`` is an ``O4_Config_Utils.Tile`` when the caller has one (the
    auto-patch driver does); its attribute carries the per-tile cfg
    value, because ``Tile.read_from_config`` writes the per-tile file onto
    the instance and never onto the module.  Deep call sites that have no
    tile pass none and get env → global → default, which is what every
    other deep cfg read in the engine already does.
    """
    return resolve(tile_cfg=getattr(tile, CFG_KEY, None),
                   global_cfg=live_global_cfg_value())


def current_provenance(tile=None) -> dict:
    """:func:`provenance` against the live engine config (see :func:`current`)."""
    return provenance(tile_cfg=getattr(tile, CFG_KEY, None),
                      global_cfg=live_global_cfg_value())


def is_constructive(tile=None) -> bool:
    """Convenience for the dispatch site's ``if``."""
    return current(tile) == CONSTRUCTIVE


class tile_scope:
    """Publish a TILE's solve model to the whole build, then restore it.

    THE PROBLEM THIS CLOSES.  ``Tile.read_from_config`` puts the per-tile
    cfg on the Tile INSTANCE only; the solve dispatch is many frames deep
    inside ``build_airport_pavement`` and has no tile, and the per-airport
    builds may run in worker PROCESSES.  Without a publish, a per-tile
    ``solve_model=constructive`` would be read by nobody and the tile
    would build iteratively — silently, with the cfg line sitting right
    there in the build directory.

    The publish channel is the environment, because that is the one
    channel a forked OR spawned worker inherits.  It never overrides an
    env value the caller already set: the arm's pin outranks the tile's
    cfg (module docstring, precedence 1 over 2), so an already-set
    ``O4_SOLVE_MODEL`` is left exactly as it is.
    """

    def __init__(self, tile):
        self.tile = tile
        self.model = None
        self._had = False
        self._prior = None

    def __enter__(self):
        self.model = current(self.tile)
        self._had = ENV_VAR in os.environ
        self._prior = os.environ.get(ENV_VAR)
        if not self._had:
            os.environ[ENV_VAR] = self.model
        return self

    def __exit__(self, *exc):
        if self._had:
            os.environ[ENV_VAR] = self._prior
        else:
            os.environ.pop(ENV_VAR, None)
        return False
