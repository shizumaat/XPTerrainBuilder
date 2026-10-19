"""The plain-language words the apps show a user (issue #831).

ONE table of user-facing wording, read by the Qt app (this module), the
Mac app (``Sources/SceneryKit/Glossary.swift``, its mirror) and the user
docs (``docs/glossary.md``, the human table).
``tests/test_glossary_parity.py`` keeps the three equal and greps both
apps for the retired primary labels.

Only DISPLAY text lives here.  The engine's internal names, the wire
protocol values (``StepProgress.step_key``, its ``label``) and the law
vocabulary stay as they are: an app maps them to these words where it
shows them (:func:`step_display`).
"""

__all__ = [
    "TERMS", "RETIRED", "RETIRED_WORDS", "STEP_NAMES", "DETAIL_PIXEL_SIZES",
    "detail_choice", "step_display", "surface_check",
]

# key -> the plain wording a primary label uses.  The owner's wording
# (issue #831), verbatim.
TERMS = {
    "detail": "Detail",
    "scenery_file": "Scenery file",
    "imagery_and_scenery_file": "Imagery and scenery file",
    "shape_ground": "Shape the ground",
    "blend_water": "Blend coastlines and water",
    "map_data": "Download map data (roads, water, airports)",
    "grade_airports": "Grade airports to official standards (FAA / ICAO / EASA)",
    "fit_buildings": "Fit custom airport buildings to the new ground",
    "ground_shape": "Airport ground shape",
    "save_edits": "Save my edits",
    "undo_edits": "Undo my edits",
    "runway_data": "X-Plane's runway data",
    "xplane_objects": "Roads, forests and buildings from X-Plane",
    "airport_elevation": "High-resolution airport elevation",
    "elevation_source": "Elevation source",
    "bathymetry": "Underwater depth near the shore",
    "map_data_server": "Map data server",
    "surface_check": "Airport surface check: {n} spots outside the rules",
    # Derived (not in the owner's table): the progress-row form of
    # "grade_airports", and the Build-pane toggle that runs the first
    # three steps together.
    "grading_airports": "Grading airports",
    "terrain_steps": "Map data, ground shape and water",
}

# key -> the words it retires as a PRIMARY label (titles, buttons, toggles,
# menu items, row names).  They may stay in secondary text (help, tooltips,
# file names) and in Expert settings.
RETIRED = {
    "detail": ("Build ZL",),
    "imagery_and_scenery_file": ("Imagery & DSF", "Imagery && DSF", "Build imagery / DSF"),
    "shape_ground": ("Triangulate 3D mesh",),
    "blend_water": ("Draw water masks",),
    "map_data": ("Assemble vector data",),
    "terrain_steps": ("Vector, mesh & masks", "Vector, mesh && masks"),
    "grade_airports": ("Auto-patch airports",),
    "fit_buildings": ("Modify custom airports",),
    "ground_shape": ("Patch · ",),
    "save_edits": ("Save Patch",),
    "undo_edits": ("Revert to auto",),
    "runway_data": ("CIFP/AIRAC",),
    "xplane_objects": ("Extract overlays",),
    "airport_elevation": ("Airport lidar insets",),
    "elevation_source": ("Custom elevation data (DEM)",),
    "map_data_server": ("Overpass server",),
}

# Bare technical words a Settings row OUTSIDE Expert may not use in its
# label or its category title (issue #823): the row says what it does in
# plain words, and the Expert section keeps the technical names.  Matched
# as whole words, ignoring case.  "ZL" is not retired: detail levels keep
# their ZL numbers (owner ruling 2026-10-18).
RETIRED_WORDS = (
    "DEM", "DSF", "DDS", "OSM", "TMS", "HTTP", "LOD", "CIFP", "AIRAC",
    "Overpass", "lidar", "mesh", "mask", "masks", "masking", "curvature",
    "bathymetry", "bathy", "triangle", "triangles", "ortho", "orthophoto",
    "orthophotos", "inset", "insets", "patch", "patches", "decal", "vector",
    "overlay", "overlays", "texture", "raster",
)

# Engine step key (the wire value ``StepProgress.step_key``, and the legacy
# driver's step names) -> the step's plain name.
STEP_NAMES = {
    "vector": TERMS["map_data"],
    "mesh": TERMS["shape_ground"],
    "masks": TERMS["blend_water"],
    "imagery": TERMS["imagery_and_scenery_file"],
    "dsf": TERMS["imagery_and_scenery_file"],
    "overlays": TERMS["xplane_objects"],
    "overlay": TERMS["xplane_objects"],
}

# Imagery zoom level -> ground size of one pixel.  Detail levels are
# shown by their ZL number (owner ruling 2026-10-18: no invented names);
# the pixel size is secondary text.  Equator figures, rounded:
# 156,543 m / 2**ZL.
DETAIL_PIXEL_SIZES = {
    12: "~40 m",
    13: "~20 m",
    14: "~10 m",
    15: "~5 m",
    16: "~2 m",
    17: "~1 m",
    18: "~0.6 m",
    19: "~0.3 m",
    20: "~0.15 m",
    21: "~0.07 m",
}

# The engine's progress label of the airport-grading phase of a step
# (``o4_engine.session``: ``"auto-patch 2/5 · ICAO"``).
_AUTO_PATCH_LABEL = "auto-patch"
_DETAIL_SEPARATOR = " · "


def detail_choice(zl):
    """A detail menu item: ``"ZL16 · ~2 m per pixel"``; ``"ZL<n>"`` off
    the table."""
    size = DETAIL_PIXEL_SIZES.get(zl)
    if size is None:
        return "ZL%s" % (zl,)
    return "ZL%s · %s per pixel" % (zl, size)


def step_display(step_key, label):
    """The progress text an app shows for an engine ``StepProgress``.

    The engine's label is ``<step label>[ · <what it is doing>]`` (or the
    airport-grading form ``auto-patch i/n[ · ICAO]``); the step's own name
    is replaced by its plain name and the detail kept.  An unknown step
    key passes the label through unchanged."""
    label = label or ""
    if label == _AUTO_PATCH_LABEL or label.startswith(_AUTO_PATCH_LABEL + " "):
        return TERMS["grading_airports"] + label[len(_AUTO_PATCH_LABEL):]
    name = STEP_NAMES.get(step_key)
    if name is None:
        return label
    _head, separator, tail = label.partition(_DETAIL_SEPARATOR)
    return name + separator + tail


def surface_check(n):
    """The one-line airport surface summary, when one is shown."""
    return TERMS["surface_check"].format(n=n)
