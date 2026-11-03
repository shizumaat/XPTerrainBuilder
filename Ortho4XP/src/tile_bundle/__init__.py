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
"""
from __future__ import annotations

__all__ = ["FORMAT", "BundleRefused"]

#: The bundle format this engine writes and reads.
FORMAT = "xptb-1"


class BundleRefused(ValueError):
    """An export or import that cannot be done, with the reason in the
    user's words (a mismatched pack, a non-default mesh setting, …)."""
