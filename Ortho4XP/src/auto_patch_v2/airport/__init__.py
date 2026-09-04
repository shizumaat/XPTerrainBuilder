"""auto_patch_v2.airport — the INPUT loaders (plan §1 row 1; M0 §4 step 1).

Pure readers over apt.dat, CIFP, the OSM extracts, the DEM + insets, the
DSFTool dump cache and the scenery pack; ``load.load`` assembles ONE
:class:`~auto_patch_v2.model.airport.Airport` in the local metric frame.
Read-only over the shared data repo (RULINGS ``e9daef5``): nothing here
writes, downloads or regenerates a cache.  Imports ``law`` and ``model``
only.
"""
from .load import Inputs, load  # noqa: F401

__all__ = ["Inputs", "load"]
