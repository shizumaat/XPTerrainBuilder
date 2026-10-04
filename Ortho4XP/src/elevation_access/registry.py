"""The registry: ``access_strategy`` key of a ``.elv`` file -> strategy class.

The key is a STRING IN DATA FILES (every ``Providers/Elevation/*.elv``
names one), so a key is never renamed.  Strategies register themselves
with :func:`register_access_strategy` when their module is imported;
``elevation_access.strategies`` imports every strategy module.
"""

__all__ = [
    "ACCESS_STRATEGIES",
    "register_access_strategy",
]


# =====================================================================
# Access-strategy registry (the code seam; strategy-agnostic below)
# =====================================================================
ACCESS_STRATEGIES = {}


def register_access_strategy(name):
    """Class/callable decorator that adds an access strategy to the registry."""

    def _register(strategy):
        ACCESS_STRATEGIES[name] = strategy
        return strategy

    return _register
