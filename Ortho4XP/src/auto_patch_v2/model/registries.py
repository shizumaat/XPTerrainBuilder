"""THE PLANAR STAGE'S REGISTRIES — one typed record the arrangement fills
and every later stage reads off the map it was built with (stage-cache
spec §3 / §10 step 2, issue #841).

Until #841 these seven were MODULE GLOBALS (``model.platform.HELD``,
``PLATEAUS``, ``LANDINGS``, ``LANDING_RUNOUTS``, ``PLATFORMS``,
``model.pad_terrace.TERRACES``, ``planar.overlay.PAD_AIRSIDE``): the planar
stage filled them and the constraint generators, the solve's datum column
and the publication read whatever the LAST planar build in the process had
left there — so a replay resumed past the planar stage read them empty
(#208, #224) and a second map (stage 1's ribbon-free one, the last stage's)
had to swap them in and out (``pipeline/stage_one_map``).

Now ``planar/overlay.build_arrangement`` builds ONE :class:`Registries`,
hands it to each pass that writes it, and ``planar/build.build`` puts it on
the map (``PlanarMap.registries``).  Every reader takes it from the map it
is handed — a map and its registries cannot come apart, and a map pickled
by ``--capture`` carries its own.  ``pipeline/capture_state`` snapshots and
installs the record at the stage boundary (field names below are its
``fields`` keys).  Lives in ``model`` so ``planar``, ``constraints``,
``solve`` and ``pipeline`` may all import it.
"""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

__all__ = ["Registries", "FIELDS"]


@_dc.dataclass
class Registries:
    """The planar stage's registries (each field's record shape is its
    writer's docstring; the containers are filled IN PLACE, in the order
    the arrangement mints them — their iteration order is the build's)."""

    #: held platform ref -> ``{"unit", "k", "blocks", "datum_pred", ...}``
    #: (``planar/platform.platform_split``; the generators add the hold's
    #: report keys, ``model.platform.HOLD_REPORT_KEYS``)
    held: dict[str, dict[str, _t.Any]] = _dc.field(default_factory=dict)
    #: held block ref -> its stand-line plateau (``planar/pad_cut.plateau_cut``)
    plateaus: dict[str, dict[str, _t.Any]] = _dc.field(default_factory=dict)
    #: ``<unit>/landing<k>`` -> ``{"block", "y", "deck", ...}``
    #: (``planar/landing.landing_regions``)
    landings: dict[str, dict[str, _t.Any]] = _dc.field(default_factory=dict)
    #: ``runout:<landing>`` -> the run-out strip (``planar/landing_runout``)
    landing_runouts: dict[str, dict[str, _t.Any]] = _dc.field(default_factory=dict)
    #: the unit-pad platform verdicts (``model.platform.Platform``)
    platforms: list = _dc.field(default_factory=list)
    #: the declared pad terraces (``model.pad_terrace.Terrace``)
    terraces: list = _dc.field(default_factory=list)
    #: the arrangement's pad/airside publication (RULINGS 2026-09-14ax)
    pad_airside: dict[str, object] = _dc.field(default_factory=dict)


#: The record's field names, in declaration (= the planar stage's fill) order.
FIELDS: tuple[str, ...] = tuple(f.name for f in _dc.fields(Registries))
