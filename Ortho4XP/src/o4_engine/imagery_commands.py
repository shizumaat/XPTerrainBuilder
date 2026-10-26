"""``imagery_source_status`` — the launch-time imagery liveness check
(protocol 1.15, #1345).

Replies ``{"started": true, "count": N}`` at once; one
``ImagerySourceStatus`` event per source follows from worker threads
(``O4_Imagery_Sources.check_status``).  A command module, not a session
method, so the imagery menus stay out of the session's import closure
(the patch and step code keys, ``tests/test_patch_code_closure.py``).
"""
from __future__ import annotations

from typing import Any, Callable, Dict, Optional, Sequence

import O4_Imagery_Sources as SOURCES

from .events import ImagerySourceStatus


def start_imagery_source_status(emit: Callable[[Any], None],
                                codes: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    """Start the check; ``emit`` receives each ImagerySourceStatus."""
    return SOURCES.check_status(
        lambda code, status, reason: emit(ImagerySourceStatus(
            code=code, status=status, reason=reason)), codes=codes)
