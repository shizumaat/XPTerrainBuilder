"""THE FOREST MAP (issue #1360): X-Plane's own FLAT forests, each to the
X-Plane 12 3D forest of the same tree type and density.  Data only; read
by :mod:`.pack_forests`.

SOURCE.  Every ``EXPORT*`` line ending ``.for`` in the X-Plane 12
install's ``Resources/default scenery/*/library.txt``, read 2026-10-27
with each target file's kind (a file with any ``SHADER_3D`` or ``MESH``
line is 3D; one with only ``TREE`` lines is flat):
``docs/findings/xp12-forest-exports-20261027.md``.  Every key below is a
file that listing calls flat (all 255 flat exports point at the 29 files
of ``900 forests`` and ``1000 autogen``); every value is a virtual path it
lists only with 3D files (``EXPORT`` or ``EXPORT_SEASON``).

KEYS are the flat file as ``<library folder>/<file>`` under ``Resources/
default scenery`` — the file the pack's definition RESOLVES to, so the
dozens of ``lib/g8/terrain/*.for`` paths that share one file share one
row.  A pack's OWN ``.for`` file is never a key: nothing in it says which
tree it draws, so it is reported unmapped, never guessed.  No row names
an airport or a pack.

THE CHOICE.  Tree type from the flat file's name (broadleaf, conifer,
mixed, shrub, ...), climate from the ``lib/g8/terrain`` names that use it
(``*_cold_*``, ``*_temp_*``, ``*_warm_*``, ``*_hot_*``), density from
``sparse`` / ``woody`` -> the ``lib/g8`` 3D forest of that type, climate
(``vcld`` < ``cld`` < ``tmp`` < ``wrm`` < ``hot`` < ``vhot``) and density
(``_sp_`` = sparse).  Unmapped on purpose: ``palms`` (the 3D palm forests
are orchards, planted in rows) and ``AGtrees_test``.
"""
from __future__ import annotations

__all__ = ["FOREST_MAP"]

#: flat file (``<library>/<file>``) -> X-Plane 12 virtual path of the 3D
#: forest with the same trees, at the same density
FOREST_MAP: dict[str, str] = {
    # ── broadleaf ───────────────────────────────────────────────────────
    "900 forests/broadleaf.for": "lib/g8/broad_tmp_wet.for",
    "900 forests/broadleaf_cold.for": "lib/g8/broad_cld_wet.for",
    "900 forests/broadleaf_sparse.for": "lib/g8/broad_sp_tmp_wet.for",
    "900 forests/small_leaf.for": "lib/g8/broad_sp_tmp_sdry.for",
    "900 forests/med_forest.for": "lib/g8/broad_wrm_sdry.for",
    "900 forests/tropical.for": "lib/g8/broad_vhot_wet.for",
    "900 forests/tropical_sdry.for": "lib/g8/broad_vhot_sdry.for",
    "900 forests/rainforest.for": "lib/g8/rainforest_vhot_rain.for",
    "900 forests/savanna.for": "lib/g8/sparse_tr_hot_dry.for",
    "900 forests/savanna_woody.for": "lib/g8/broad_sp_hot_dry.for",
    # ── conifer ─────────────────────────────────────────────────────────
    "900 forests/conifer.for": "lib/g8/coni_cld_wet.for",
    "900 forests/conifer_cold.for": "lib/g8/coni_vcld_wet.for",
    "900 forests/conifer_sparse.for": "lib/g8/coni_sp_cld_wet.for",
    "900 forests/taiga.for": "lib/g8/coni_sp_vcld_dry.for",
    # ── mixed ───────────────────────────────────────────────────────────
    "900 forests/mixed.for": "lib/g8/mixed_cld_wet.for",
    "900 forests/boreal_forest.for": "lib/g8/mixed_vcld_wet.for",
    # ── shrub ───────────────────────────────────────────────────────────
    "900 forests/tundra.for": "lib/g8/shrb_vcld_dry.for",
    "900 forests/cool_shrub.for": "lib/g8/shrb_cld_dry.for",
    "900 forests/temp_shrub.for": "lib/g8/shrb_tmp_dry.for",
    "900 forests/med_shrub.for": "lib/g8/shrb_wrm_sdry.for",
    "900 forests/dry_shrub.for": "lib/g8/shrb_wrm_dry.for",
    "900 forests/sdesert_shrub.for": "lib/g8/shrb_hot_dry.for",
    # ── autogen trees (``lib/g10/forests``) ─────────────────────────────
    "1000 autogen/forests/AG_temperate1.for": "lib/vegetation/AG_temp_1.for",
    "1000 autogen/forests/AG_temperate2.for": "lib/vegetation/AG_temp_2.for",
    "1000 autogen/forests/AG_trees_EU1.for": "lib/vegetation/AG_temp_1.for",
    "1000 autogen/forests/AG_trees_EU1_dense.for": "lib/vegetation/AG_temp_1.for",
    "1000 autogen/forests/AG_trees_EU2.for": "lib/vegetation/AG_temp_2.for",
}
