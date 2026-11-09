"""THE TREE MAP (issue #1710): the X-Plane 12 3D trees an old flat tree
is upgraded to.  Data only; read by :mod:`.pack_trees`.

SOURCE.  The X-Plane 12 install's ``Resources/default scenery/1200
forests/library.txt``, read 2026-11-02: every ``lib/vegetation/trees/**``
forest is ONE species at ONE size (a ``.for`` with ``SHADER_3D`` and
``MESH`` lines), plain ``EXPORT`` (coniferous) or ``EXPORT_SEASON``
(deciduous).  The height of each is the largest ``max h`` of its
``TREE`` rows (the summer file).  X-Plane 12 exports no 3D tree OBJECT:
its 3D trees exist only as forests, so a flat tree object becomes a POINT
forest (polygon parameter 512 + density: every vertex is one tree — the
mode WED's "point" forests write, read in the corpus' Aerosoft dumps).

:data:`FAMILIES` — one species (or a generic class) -> its sizes, each
``(virtual path, height m)``, low to high.  The key is the target string
the offer and the record carry.

:data:`NAME_CLASS` / :data:`REGION_FAMILY` / :data:`PALM_FAMILY` — the
REGION (issue #1965, :mod:`.pack_climate`): a generic tree (a name that
says only conifer, broadleaf or palm, or a shape read) takes the species
X-Plane 12 grows in the tile's climate.  A pack's OWN flat ``.for``
takes the ``lib/g8`` forest of its type, density and climate
(``pack_climate.g8_forest``).

:data:`PLANTERS` — the X-Plane 12 3D GROUND cover a pack's own LOW
vegetation maps to (owner 2026-11-06, issue #1920 follow-up: "use xp12
resources where possible if they meet the height requirements"): the
``lib/vegetation/planters/ground/*`` forests of the same install file
(never ``planters/high/*``, raised planters), each with the largest
``max h`` of its ``TREE`` rows (fields 8-9 are min / max height; the
summer file, the other seasons read the same), its ``SPACING`` (a
planter is ground cover at half a metre: a polygon keeps the pack's
plant count, :mod:`.pack_trees_density`) and the plants it holds.
They are inline plant meshes only — no object, no pot or box.
:data:`LOW_CLASS` — a low-vegetation class -> (height cap m, the
planters in order of preference); the first whose height is within the
cap is the target (:func:`.pack_trees.local_forest_target`).
``tests/auto_patch_v2/test_pack_trees_planters.py`` re-reads the
installed library when there is one.
No row names an airport or a pack.
"""
from __future__ import annotations

__all__ = ["FAMILIES", "NAME_FAMILY", "TREE_WORDS", "NAME_CLASS",
           "REGION_FAMILY", "PALM_FAMILY",
           "PLANTERS", "LOW_CLASS", "GRASS_WORDS", "GRASS_M"]

_T = "lib/vegetation/trees/"

#: target id -> ((virtual path, height m), ...) low to high
FAMILIES: dict[str, tuple[tuple[str, float], ...]] = {
    _T + "coniferous/fir_*.for": (
        (_T + "coniferous/fir_small.for", 5.1),
        (_T + "coniferous/fir_medium.for", 10.2),
        (_T + "coniferous/fir_big.for", 18.0),
        (_T + "coniferous/fir_tall.for", 25.0)),
    _T + "coniferous/spruce_*.for": (
        (_T + "coniferous/spruce_small.for", 5.1),
        (_T + "coniferous/spruce_medium.for", 10.2),
        (_T + "coniferous/spruce_big.for", 18.0),
        (_T + "coniferous/spruce_tall.for", 22.0)),
    _T + "coniferous/pine_*.for": (
        (_T + "coniferous/shrubs_pines.for", 2.8),
        (_T + "coniferous/pine_medium.for", 10.0),
        (_T + "coniferous/pine_big.for", 13.5),
        (_T + "coniferous/pine_tall.for", 22.0)),
    _T + "deciduous/oak_*.for": (
        (_T + "deciduous/oak_medium.for", 8.1),
        (_T + "deciduous/oak_big.for", 12.0),
        (_T + "deciduous/oak_tall.for", 17.0)),
    _T + "deciduous/maple_*.for": (
        (_T + "deciduous/maple_small.for", 5.0),
        (_T + "deciduous/maple_medium.for", 8.1),
        (_T + "deciduous/maple_big.for", 12.0)),
    _T + "deciduous/birch_*.for": (
        (_T + "deciduous/birch_medium.for", 7.2),
        (_T + "deciduous/birch_big.for", 10.0),
        (_T + "deciduous/birch_tall.for", 15.0)),
    _T + "deciduous/aspen_*.for": (
        (_T + "deciduous/aspen_medium.for", 8.0),
        (_T + "deciduous/aspen_big.for", 15.3),
        (_T + "deciduous/aspen_tall.for", 20.0)),
    _T + "deciduous/elm_*.for": (
        (_T + "deciduous/elm_medium.for", 9.0),
        (_T + "deciduous/elm_big.for", 12.6),
        (_T + "deciduous/elm_tall.for", 18.7)),
    # a broadleaf tree the file does not name: maple to oak by height
    _T + "deciduous/broadleaf_*.for": (
        (_T + "deciduous/maple_small.for", 5.0),
        (_T + "deciduous/maple_medium.for", 8.1),
        (_T + "deciduous/oak_big.for", 12.0),
        (_T + "deciduous/oak_tall.for", 17.0)),
    _T + "deciduous/shrubs_*.for": (
        (_T + "deciduous/shrubs_small.for", 2.04),
        (_T + "deciduous/shrubs_medium.for", 4.0),
        (_T + "deciduous/shrubs_big.for", 8.0)),
    _T + "evergreen/cypress_*.for": (
        (_T + "evergreen/cypress1_small.for", 2.5),
        (_T + "evergreen/cypress1_medium.for", 5.0),
        (_T + "evergreen/cypress1_big.for", 9.0)),
    _T + "palm/palm_*.for": (
        (_T + "palm/coconut_palm_small.for", 5.6),
        (_T + "palm/coconut_palm_medium.for", 11.0),
        (_T + "palm/coconut_palm_big.for", 22.8)),
    _T + "palm/date_palm_*.for": (
        (_T + "palm/date_palm_small.for", 4.5),
        (_T + "palm/date_palm_medium.for", 10.0),
        (_T + "palm/date_palm_big.for", 18.0)),
    # a tropical broadleaf: X-Plane 12's kapok (``thin`` is the middle size)
    _T + "evergreen/kapok_*.for": (
        (_T + "evergreen/kapok_tree_medium.for", 8.0),
        (_T + "evergreen/kapok_tree_thin.for", 15.3),
        (_T + "evergreen/kapok_tree_big.for", 26.0)),
}

#: a word of an object's file or texture name -> its family
NAME_FAMILY: dict[str, str] = {
    "fir": _T + "coniferous/fir_*.for",
    "spruce": _T + "coniferous/spruce_*.for",
    "pine": _T + "coniferous/pine_*.for",
    "conifer": _T + "coniferous/spruce_*.for",
    "coniferous": _T + "coniferous/spruce_*.for",
    "coni": _T + "coniferous/spruce_*.for",
    "oak": _T + "deciduous/oak_*.for",
    "maple": _T + "deciduous/maple_*.for",
    "birch": _T + "deciduous/birch_*.for",
    "aspen": _T + "deciduous/aspen_*.for",
    "poplar": _T + "deciduous/aspen_*.for",
    "elm": _T + "deciduous/elm_*.for",
    "dec": _T + "deciduous/broadleaf_*.for",
    "decid": _T + "deciduous/broadleaf_*.for",
    "deciduous": _T + "deciduous/broadleaf_*.for",
    "broadleaf": _T + "deciduous/broadleaf_*.for",
    "bush": _T + "deciduous/shrubs_*.for",
    "bushes": _T + "deciduous/shrubs_*.for",
    "shrub": _T + "deciduous/shrubs_*.for",
    "shrubs": _T + "deciduous/shrubs_*.for",
    "cypress": _T + "evergreen/cypress_*.for",
    "palm": _T + "palm/palm_*.for",
    "palms": _T + "palm/palm_*.for",
}

#: the words that make a name tree-like (with every :data:`NAME_FAMILY` key)
TREE_WORDS = frozenset({"tree", "trees", "veg", "vegetation", "forest",
                        "forests", "wood", "woods"}) | frozenset(NAME_FAMILY)

#: a GENERIC word of a name -> the tree class the region picks the
#: species of (issue #1965; a species word keeps :data:`NAME_FAMILY`'s)
NAME_CLASS: dict[str, str] = {
    "conifer": "conifer", "coniferous": "conifer", "coni": "conifer",
    "dec": "broadleaf", "decid": "broadleaf", "deciduous": "broadleaf",
    "broadleaf": "broadleaf", "palm": "palm", "palms": "palm",
}

#: tree class -> X-Plane 12 temperature tier -> the species it grows
#: there (``pack_climate.TEMPS``): in the tropics a conifer-shaped
#: billboard is a palm and a broadleaf the kapok; Mediterranean narrow
#: trees are cypresses and broadleaves oaks; the temperate defaults of
#: issue #1710; birch in the cold
REGION_FAMILY: dict[str, dict[str, str]] = {
    "conifer": {"vhot": _T + "palm/palm_*.for",
                "hot": _T + "palm/palm_*.for",
                "wrm": _T + "evergreen/cypress_*.for",
                "tmp": _T + "coniferous/spruce_*.for",
                "cld": _T + "coniferous/spruce_*.for",
                "vcld": _T + "coniferous/spruce_*.for"},
    "broadleaf": {"vhot": _T + "evergreen/kapok_*.for",
                  "hot": _T + "evergreen/kapok_*.for",
                  "wrm": _T + "deciduous/oak_*.for",
                  "tmp": _T + "deciduous/broadleaf_*.for",
                  "cld": _T + "deciduous/birch_*.for",
                  "vcld": _T + "deciduous/birch_*.for"},
}

#: a palm, by "a hot and wet climate": the coconut palm, else the date palm
PALM_FAMILY: dict[bool, str] = {True: _T + "palm/palm_*.for",
                                False: _T + "palm/date_palm_*.for"}

_P = "lib/vegetation/planters/ground/"

#: virtual path -> (max height m, SPACING m (x, z), the plants it holds)
PLANTERS: dict[str, tuple[float, tuple[float, float], tuple[str, ...]]] = {
    _P + "grass_green_1.for": (1.0, (0.5, 0.5),
                               ("grass", "dryGrass", "tallGrass", "tallWeed")),
    _P + "grass_dry_1.for": (1.0, (0.5, 0.5),
                             ("grass", "dryGrass", "tallGrass", "sm_stone")),
    _P + "shrubs_green_1.for": (1.1, (0.6, 0.6),
                                ("buxus", "lilac", "prunus", "sorbus",
                                 "grass", "dryGrass")),
    _P + "shrubs_green_2.for": (1.1, (0.6, 0.6),
                                ("buxus", "prunus", "sorbus", "grass",
                                 "dryGrass")),
    _P + "shrubs_red_1.for": (1.1, (0.6, 0.6),
                              ("barberry", "tallGrass", "grass", "dryGrass")),
}

#: the height a plant may reach inside a runway strip, safety area or
#: taxiway strip: grass only (issue #1920; a shrub planter is cleared there
#: like a tree)
GRASS_M = 1.0

#: class -> (height cap m, planters in order of preference).  ``grass``
#: (grass, reed, flowers: the pack's own ground cover) takes NO planter:
#: the pack keeps its own flat file (owner 2026-11-07: "move grass
#: swapping to a more thoroughly tested model in beta 8" — X-Plane 12's
#: 3D grass planter at 0.5 m spacing cost KDAL's frame rate badly; grass
#: -> planter is deferred to the Beta 8 optimiser item).  ``shrub`` takes
#: shrubs lower than the lowest source a shrub can be
#: (``pack_trees.GROUND_COVER_M``): barberry with tall grass (owner
#: RULINGS 2026-11-06d (7): "Shrubs, yes switch to barberry").
LOW_CLASS: dict[str, tuple[float, tuple[str, ...]]] = {
    "grass": (GRASS_M, ()),
    "shrub": (1.5, (_P + "shrubs_red_1.for",)),
}

#: a word of a pack ``.for``'s name that makes it grass-class ground cover
GRASS_WORDS = frozenset({"grass", "grasses", "reed", "reeds",
                         "flower", "flowers", "weed", "weeds", "meadow",
                         "hay", "sedge", "rush", "rushes"})
