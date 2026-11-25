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

__all__ = ["Registries", "FIELDS", "GROUP_UP", "LANDSIDE_KERB", "UNIT_LEVELS"]

#: the ``witness`` word of an UPPER PAD's level record in ``landings``
#: (``planar/group_up``, #2068) — read by ``airport/road_ramp.road_terrace``
#: (the level a road arm climbs to) and ``constraints/riser``
GROUP_UP = "group_up"

#: the key of a FLOOR YARD's record on its floor pad's ``held`` record
#: (``classify/floor_yard``, #2068): ``yard_plane``, ``yard_hull``, ``y_p``
#: (the unit floor) -- read through ``model/yard_run.yard_records``
FLOOR_YARD = "floor_yard"

#: the key of a unit block's LANDSIDE KERB records on its ``held`` record
#: (#2279 step 2, ``planar/kerb_frontage``): ``({"lot", "plan", "y"}, ...)``
#: -- the lots that meet the unit's storey at its plan edge, the plan
#: (a shapely geometry, the engine's frame) and the storey's rise over the block's datum
#: (``constraints/kerb_frontage``)
LANDSIDE_KERB = "landside_kerb"

#: the key of a unit block's TWO-FLOOR RECORD on its ``held`` record
#: (RULINGS 2026-11-25g, ``planar/unit_levels_read``): the unit's
#: ``airport/unit_storey.UnitLevels``, reconciled to the level minted on
#: the block -- read by the frontage law (``planar/kerb_frontage``)
UNIT_LEVELS = "unit_levels"


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

    def yard_pads(self) -> frozenset[str]:
        """The pads a yard has a LEVEL on (spec 2068 A4 F1'): an upper
        level's ``landings`` record carrying a ``yard_plane`` names its
        ``pad``; a held floor pad carrying :data:`FLOOR_YARD` is its own."""
        return frozenset({str(r["pad"]) for r in self.landings.values()
                          if r.get("yard_plane") and r.get("pad") is not None}
                         | {str(k) for k, h in self.held.items() if h.get(FLOOR_YARD)})


#: The record's field names, in declaration (= the planar stage's fill) order.
FIELDS: tuple[str, ...] = tuple(f.name for f in _dc.fields(Registries))
