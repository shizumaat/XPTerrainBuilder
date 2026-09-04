"""The census as pure functions over ``GradedSurface`` + ``Law`` (plan §1
``verify`` row) — the SAME tables the solver used, rows with the v1
census's own keys so the two can be diffed.  ``census`` runs every
family."""
from .census import FAMILIES, census

__all__ = ["FAMILIES", "census"]
