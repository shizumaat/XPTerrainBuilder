"""The hairline pre-flight's two gap constants, in a module with no imports
so a light caller (``auto_patch.terrain_cut_stage``) reads them without
pulling the mesh into its step and patch code closures.  ``O4_Mesh_Utils``
re-exports both; their meaning is documented there."""

HAIRLINE_DEGENERATE_M = 0.010
HAIRLINE_SPACING_M = 0.5
