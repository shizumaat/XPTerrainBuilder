"""The inset code as ONE thing: patch a name in all of it, read all of it.

The inset pipeline (``O4_Airport_Elevation_Insets``) and every module of
``elevation_access`` import the helpers they share by name, so one
helper is bound in several modules.  A test that stubs
``warp_vsicurl_sources_to_geotiff`` means "no code under test may reach
the real warp" -- patching only the module that DEFINES it would leave
every strategy calling the real one.  Likewise a twin that reads the
source for a forbidden phrase must read every module, not one file.
"""

import glob
import os
import sys
from typing import Any

PIPELINE = "O4_Airport_Elevation_Insets"
PACKAGE = "elevation_access"
_SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "src")


def inset_code_files() -> list:
    """Every source file of the inset code: the pipeline, then the package."""
    package = os.path.join(_SRC, PACKAGE)
    return [os.path.join(_SRC, PIPELINE + ".py")] + sorted(
        glob.glob(os.path.join(package, "*.py"))
        + glob.glob(os.path.join(package, "strategies", "*.py")))


def inset_code_source() -> str:
    """The text of all of it, concatenated."""
    parts = []
    for path in inset_code_files():
        with open(path, encoding="utf-8") as handle:
            parts.append(handle.read())
    return "\n".join(parts)


def patch_inset_code(monkeypatch: Any, name: str, value: Any) -> int:
    """Bind ``name`` to ``value`` in every loaded inset module that has it.

    Returns the number of modules patched; a name bound nowhere is a
    test bug and fails here.
    """
    patched = 0
    for (module_name, module) in list(sys.modules.items()):
        if module is None:
            continue
        if module_name != PIPELINE and module_name != PACKAGE \
                and not module_name.startswith(PACKAGE + "."):
            continue
        if name in vars(module):
            monkeypatch.setattr(module, name, value)
            patched += 1
    assert patched, "%r is bound in no inset module" % name
    return patched
