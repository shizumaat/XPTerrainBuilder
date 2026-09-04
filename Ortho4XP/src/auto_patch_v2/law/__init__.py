"""auto_patch_v2.law — THE LAW AS DATA (RULINGS 2026-09-03d).

Values live in the ``*.toml`` files beside this module; ``model`` is the
typed schema + loader, ``tables`` the accessors.  Nothing here imports
from any other v2 package.
"""
from .model import Law, LawError, LawTables, load_tables  # noqa: F401
from .tables import (DEFAULT_LAW_DIR, law_tables_digest, load_default,  # noqa: F401
                     resolve_ruleset)

__all__ = ["Law", "LawError", "LawTables", "load_tables", "DEFAULT_LAW_DIR",
           "load_default", "law_tables_digest", "resolve_ruleset"]
