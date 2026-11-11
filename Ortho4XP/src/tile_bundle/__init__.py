"""TILE BUNDLES (#1699 phase 1): a built tile's mesh, masks and solved
airports, made portable.

A tile bundle is the step-reuse records (``O4_Step_Reuse``) of the
vector, mesh and masks steps and the files they wrote, with every local
path replaced by a token, plus a manifest.  A user whose installed
airport packs match the bundle's key imports it and builds the tile with
their own imagery: the OpenStreetMap, elevation and lidar downloads and
the solve and mesh steps are skipped.  Phase 1 is LOCAL ONLY — an
"Export library bundle" / "Import library bundle" pair in both apps; no
library, no server.

* :mod:`.key` — the match key: the tile, each airport's pack signature
  (from the pristine pack), the mesh profile and the code family;
* :mod:`.paths` — local paths out (export) and back in (import);
* :mod:`.contents` — which files a bundle carries;
* :mod:`.export` / :mod:`.importer` — the two engine commands.

Tile bundles are made only for the default mesh settings (owner Q301,
2026-11-02: "Yes, and yes").  A bundle never carries imagery, a scenery
pack's files or a raw OSM or elevation download.

PACKAGES (#2014, format ``xptb-2``, suffix ``.xptb``) supersede the tile
bundle for sharing: a package carries a tile's (or a region's, or one
airport's) DOWNLOADED DATA instead of its products, so it builds with any
engine that reads its cache schemas and installing it leaves nothing to
download but imagery.  Anyone may make and share one ("Export
Package…"); opening or dropping one on the app shows what it holds and
installs it, combining with packages already installed.

* :mod:`.inputs` — which downloaded files a package carries;
* :mod:`.package` / :mod:`.install` / :mod:`.merge` — save, install,
  and combine several packages into one.

A ``.xptbundle`` is still read (:mod:`.install` dispatches it to
:mod:`.importer`).

DEVELOPER PACKAGES (RULINGS 2026-11-11m): a pack's author says, in the
pack, whether its objects are final (:mod:`.pack_dev`), applies the
object stage's fixes into it (:mod:`.pack_apply`), and ships packages in
its ``XPTerrainBuilder`` folder, which every installation applies as the
airport's tiles build (:mod:`.pack_shipped`).
"""
from __future__ import annotations

__all__ = ["FORMAT", "PACKAGE_FORMAT", "PACKAGE_SUFFIX", "LEGACY_SUFFIX",
           "SUFFIXES", "BundleRefused"]

#: The tile bundle format this engine still reads (and the gate writes).
FORMAT = "xptb-1"

#: The package format this engine writes and reads.
PACKAGE_FORMAT = "xptb-2"

#: A package's file name ends so; a tile bundle's so.
PACKAGE_SUFFIX = ".xptb"
LEGACY_SUFFIX = ".xptbundle"

#: Every suffix the apps hand to the package install.
SUFFIXES = (PACKAGE_SUFFIX, LEGACY_SUFFIX)


class BundleRefused(ValueError):
    """An export or import that cannot be done, with the reason in the
    user's words (a mismatched pack, a non-default mesh setting, …)."""
