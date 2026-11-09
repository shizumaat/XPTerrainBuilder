"""THE CLIMATE a pack's trees grow in (issue #1965): X-Plane 12's own
regional vegetation, read from the tile's Global Scenery definitions, and
the X-Plane 12 forest or tree family each old flat tree takes there.

Owner (2026-11-08, KEYW): "tree replacement needs to be region aware ...
Replacing trees at KEYW resulted in evergreens and trees from the north,
not tropical warm weather varieties."

THE WITNESS.  X-Plane 12's Global Scenery tile names its landclass
terrains and forests with a climate tag, ``_<temp>_<moisture>``
(``lib/g10/terrain10/fst_hot_wet_hill.ter``, ``lib/g8/broad_wrm_sdry.for``;
temperature ``vcld`` < ``cld`` < ``tmp`` < ``wrm`` < ``hot`` < ``vhot``,
moisture ``dry`` < ``sdry`` < ``wet`` < ``rain``).  :func:`climate_of_names`
takes the most-named temperature and the most-named moisture of the
tile's definitions (the forest step of the object stage reads
them): what
X-Plane itself grows there.  Without a Global Scenery tile the latitude
band stands in (:func:`latitude_climate`); with no climate at all the
temperate, wet default of issue #1710 stands (:data:`DEFAULT`).

THE CHOICE.  A pack's own flat ``.for`` takes the ``lib/g8`` forest of
its tree type and density in that climate (:func:`g8_forest`; X-Plane 12
exports every type x density x climate); one the name calls a palm takes
the palm species of the climate.  A flat tree OBJECT keeps a species
its name gives (a fir stays a fir); an unnamed or generic one — its
class read from the name's generic word or its billboard shape — takes
the region's species (:data:`.pack_trees_map.REGION_FAMILY`): in the
tropics a narrow billboard is a palm, not a fir.  No row names an
airport.
"""
from __future__ import annotations

import collections
import re
import typing as _t

from .pack_trees_map import PALM_FAMILY, REGION_FAMILY

__all__ = ["Climate", "DEFAULT", "TEMPS", "MOISTS", "climate_of_names",
           "latitude_climate", "g8_forest", "regional_family"]

#: X-Plane 12's temperature tiers, cold to hot
TEMPS = ("vcld", "cld", "tmp", "wrm", "hot", "vhot")
#: X-Plane 12's moisture tiers, dry to wet
MOISTS = ("dry", "sdry", "wet", "rain")

_TAG = re.compile(r"_(" + "|".join(TEMPS) + r")_(" + "|".join(MOISTS)
                  + r")(?=[_.]|$)")


class Climate(_t.NamedTuple):
    """One climate: ``temp`` (:data:`TEMPS`), ``moist`` (:data:`MOISTS`)
    and where it was read (``"global scenery"`` | ``"latitude"`` |
    ``"default"``)."""

    temp: str
    moist: str
    source: str = "default"

    @property
    def tag(self) -> str:
        return f"{self.temp}_{self.moist}"


#: no climate read: the temperate, wet member (issue #1710's choice)
DEFAULT = Climate("tmp", "wet", "default")

#: |latitude| upper bound -> temperature tier, the stand-in without a
#: Global Scenery tile (tropic, subtropic, the 40th and 55th parallels,
#: the polar circle)
_LAT_BANDS = ((23.5, "vhot"), (30.0, "hot"), (40.0, "wrm"), (55.0, "tmp"),
              (66.5, "cld"), (90.1, "vcld"))


def climate_of_names(names: _t.Iterable[str],
                     source: str = "global scenery") -> Climate | None:
    """The most-named temperature and moisture of definition paths
    (ties to the cooler, then the wetter tier); ``None`` when none
    carries a climate tag."""
    temps: collections.Counter[str] = collections.Counter()
    moists: collections.Counter[str] = collections.Counter()
    for name in names:
        m = _TAG.search(name.replace("\\", "/").rsplit("/", 1)[-1])
        if m:
            temps[m.group(1)] += 1
            moists[m.group(2)] += 1
    if not temps:
        return None
    temp = max(TEMPS, key=lambda t: (temps[t], -TEMPS.index(t)))
    moist = max(MOISTS, key=lambda w: (moists[w], MOISTS.index(w)))
    return Climate(temp, moist, source)


def latitude_climate(lat: float) -> Climate:
    """The latitude band's temperature, moisture ``wet``."""
    a = abs(lat)
    temp = next(t for top, t in _LAT_BANDS if a < top)
    return Climate(temp, "wet", "latitude")


def g8_forest(kind: str, sparse: bool, climate: Climate | None) -> str:
    """The X-Plane 12 ``lib/g8`` 3D forest of tree type ``kind``
    (``broad`` | ``coni`` | ``mixed``), density and climate."""
    c = climate or DEFAULT
    return f"lib/g8/{kind}{'_sp' if sparse else ''}_{c.temp}_{c.moist}.for"


def regional_family(cls: str, climate: Climate | None) -> str:
    """The :data:`.pack_trees_map.FAMILIES` key for a tree of class
    ``cls`` (``conifer`` | ``broadleaf`` | ``palm``) in ``climate``;
    ``""`` for another class."""
    c = climate or DEFAULT
    fam = REGION_FAMILY.get(cls, {}).get(c.temp, "")
    if cls == "palm" or fam in PALM_FAMILY.values():
        return PALM_FAMILY[c.temp in ("hot", "vhot") and c.moist in ("wet", "rain")]
    return fam
