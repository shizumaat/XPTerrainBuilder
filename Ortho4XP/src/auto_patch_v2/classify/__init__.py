"""auto_patch_v2.classify — roles per pavement cell (plan §1 row 2).

One scorer (``roles.classify``), one output (``Classification``), the
thresholds in ``rules.toml``.  Imports ``law``, ``model`` and
``airport`` only; shapely is used here and in ``planar/``.
"""
from .roles import Cell, Classification, CutLine, classify  # noqa: F401
from .rules import Rules, RulesError, load_rules  # noqa: F401

__all__ = ["Cell", "Classification", "CutLine", "classify", "Rules",
           "RulesError", "load_rules"]
