"""Scenery reloads only when the user asks (owner 2026-11-12T14:34Z:
"Never ask x-plane to reload unless the user requests it.").

A job that knows a reload would show new scenery -- the follow job when
an airport's core landed after X-Plane's flight-start window
(``imagery_follow``, ``O4_Imagery_Spawn``), build-ahead when it swapped
a tile X-Plane already holds (``world_job``, the parked-aircraft rule)
-- calls :func:`offer` with a :data:`CODES` word.  Nothing is sent: the
offer rides on ``ImageryFollowStatus.reload_offer`` and both apps show
it with a "Reload scenery" button (``FlyText.reloadOfferLine`` /
``O4_Fly_Text.reload_offer_line``).  The button sends the command
``scenery_reload`` (:func:`scenery_reload`), the one place X-Plane is
asked to reload; a flight's offered reload (``flight_reload``) is the
same click and sends through :func:`send` too.  No job calls
:func:`send` on its own.
"""
from __future__ import annotations

import threading
from typing import Optional

__all__ = ["CODES", "offer", "current", "send", "scenery_reload"]

#: What a reload would show, the weightiest last: imagery that landed
#: after X-Plane read the tile coarse; World-pack placeholders X-Plane has
#: not seen (world coverage, ``world_commands.ensure_coverage``: a reload
#: or a restart once); World tiles that replaced ones X-Plane holds.
CODES = ("imagery", "coverage", "tiles")
_LOCK = threading.Lock()
_STATE = {"offer": ""}


def offer(code: str) -> bool:
    """Offer the user a reload (``code`` one of :data:`CODES`; a pending
    offer is replaced only by a weightier one).  Returns True: the offer
    stands (``FollowJob`` counts it)."""
    if code not in CODES:
        raise ValueError(f"unknown reload offer {code!r} (known: {CODES})")
    with _LOCK:
        pending = _STATE["offer"]
        if not pending or CODES.index(code) >= CODES.index(pending):
            _STATE["offer"] = code
    return True


def current() -> str:
    """The pending offer's code, or ``""``."""
    with _LOCK:
        return _STATE["offer"]


def send(base: Optional[str] = None) -> bool:
    """The user asked: X-Plane reloads its scenery (``O4_XPlane_WebAPI``);
    the offer is cleared when the request was taken."""
    import O4_XPlane_WebAPI as WEBAPI
    sent = bool(WEBAPI.reload_scenery(base))
    if sent:
        with _LOCK:
            _STATE["offer"] = ""
    return sent


def scenery_reload(port=None, **_ignored) -> dict:
    """ENGINE COMMAND ``scenery_reload``: the user's "Reload scenery"
    button.  ``{"sent": bool}``."""
    import O4_XPlane_WebAPI as WEBAPI
    return {"sent": send(WEBAPI.base_url(int(port)) if port else None)}
