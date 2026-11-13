"""Imagery on demand in the Qt window (#1992 P4; the Mac app's
``ImageryFollowLine`` and ``FavoriteStarButton``, same words —
``O4_Imagery_OnDemand_Text``).

* :class:`FollowStatusLine` -- the activity area's line while the follow
  job runs: every ``ImageryFollowStatus`` field (headline and detail),
  and "Follow X-Plane" / "Stop Following", so a flight needs no Terminal;
  a pending reload offer with "Reload scenery" (#2019).
  Shown while the world switch is on or a job runs.
* :class:`FavoriteStar` -- the star beside the tile pane's title (#2033;
  "pin" renamed Favorite, RULINGS 2026-11-10c (1)): outlined, or filled
  on a favorite; a click flips it (engine ``imagery_pin``).  Any tile
  this app built, a build running or not.
* :func:`pin_tile` -- the pin on a daemon thread (the Library and the
  map's stars use it too); while a build runs it changes the tile's
  record and index only (``imagery_pin(serve=False)``).
"""
from __future__ import annotations

import O4_Imagery_OnDemand_Text as TEXT
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QToolButton, QVBoxLayout, QWidget

__all__ = ["FollowStatusLine", "FavoriteStar", "pin_tile"]

NOTE_STYLE = "color: gray; font-size: 11px;"
#: The star's two faces (outlined, filled) and the filled one's colour
#: (``O4_Qt_Map_Favorite.STAR_COLOR``).
STAR_OUTLINED = "\u2606"
STAR_FILLED = "\u2605"
STAR_FILLED_STYLE = "color: #FFD60A;"


def pin_tile(lat, lon, pinned, signal, busy=lambda: False, working_dir=""):
    """``imagery_pin`` for one tile on a daemon thread; its reply (or the
    error) is emitted on ``signal``.  ``busy()`` says a build runs: the
    Favorite is still set, without landing textures (#2033)."""
    from O4_Qt_Library import emit_from_thread  # it imports this module
    serve = not busy()

    def work():
        from o4_engine.imagery_ondemand import imagery_pin
        return imagery_pin(int(lat), int(lon), working_dir=working_dir,
                           pinned=bool(pinned), serve=serve)
    emit_from_thread(work, signal, "o4-qt-imagery-pin")


class FollowStatusLine(QWidget):
    """The follow job's line: headline, detail, and its Start/Stop."""

    #: True: start following; False: stop.
    toggle_requested = Signal(bool)
    #: The user's "Reload scenery" (``scenery_reload``): the only way the
    #: app asks X-Plane to reload (owner 2026-11-12T14:34Z).
    reload_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        self.headline = QLabel(TEXT.FOLLOW_TEMPLATES["stopped"])
        self.headline.setWordWrap(True)
        top.addWidget(self.headline, 1)
        self.toggle_btn = QPushButton(TEXT.FOLLOW_START_TITLE)
        self.toggle_btn.clicked.connect(
            lambda: self.toggle_requested.emit(not self.running))
        top.addWidget(self.toggle_btn, 0)
        layout.addLayout(top)
        self.detail = QLabel("")
        self.detail.setWordWrap(True)
        self.detail.setStyleSheet(NOTE_STYLE)
        self.detail.setVisible(False)
        layout.addWidget(self.detail)
        self.reload_row = QWidget()
        row = QHBoxLayout(self.reload_row)
        row.setContentsMargins(0, 0, 0, 0)
        self.reload_label = QLabel("")
        self.reload_label.setWordWrap(True)
        row.addWidget(self.reload_label, 1)
        self.reload_btn = QPushButton(TEXT.RELOAD_SCENERY_TITLE)
        self.reload_btn.clicked.connect(self.reload_requested.emit)
        row.addWidget(self.reload_btn, 0)
        self.reload_row.setVisible(False)
        layout.addWidget(self.reload_row)
        self.running = False
        self.status = None

    def show_status(self, status) -> None:
        """One ``ImageryFollowStatus`` (the event, or its dict)."""
        fields = status if isinstance(status, dict) else vars(status)
        self.status = dict(fields)
        headline, detail = TEXT.follow_lines(fields)
        self.headline.setText(headline)
        self.detail.setText(detail)
        self.detail.setVisible(True)
        offer = TEXT.reload_offer_line(fields.get("reload_offer") or "")
        self.reload_label.setText(offer)
        self.reload_row.setVisible(bool(offer))
        self.set_running(fields.get("state") not in ("stopped", "error"))

    def set_running(self, running: bool) -> None:
        """The button, and the headline that agrees with it
        (``O4_Imagery_OnDemand_Text.follow_headline``)."""
        self.running = bool(running)
        self.toggle_btn.setText(TEXT.FOLLOW_STOP_TITLE if self.running
                                else TEXT.FOLLOW_START_TITLE)
        self.headline.setText(TEXT.follow_headline(self.status, self.running))


class FavoriteStar(QToolButton):
    """The Favorite star beside the tile pane's title: outlined, or filled
    on a favorite; a click asks for the other state.  Shown on every tile
    this app built."""

    #: (lat, lon, pinned) the user asked for.
    pin_requested = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAutoRaise(True)
        self.setAccessibleName(TEXT.FAVORITE_TITLE)
        self.clicked.connect(self._clicked)
        self._tile = None
        self._pinned = False
        self.set_pinned(False)

    @staticmethod
    def shows(info) -> bool:
        """Does the star show for this tile (any tile this app built)?"""
        import O4_Qt_Map_Legend as QTLEGEND
        return info is not None and not QTLEGEND.built_elsewhere(info)

    def show_tile(self, tile, info) -> None:
        """The active tile and its :class:`O4_Tile_Info.TileInfo`."""
        self._tile = tuple(tile) if tile and self.shows(info) else None
        self.setVisible(self._tile is not None)
        self.set_pinned(bool(getattr(info, "pinned", False)))

    @property
    def pinned(self) -> bool:
        """The favorite state the star shows."""
        return self._pinned

    def set_pinned(self, pinned: bool) -> None:
        """Show the favorite state (the tile's, or the engine's answer)."""
        self._pinned = bool(pinned)
        self.setText(STAR_FILLED if self._pinned else STAR_OUTLINED)
        self.setStyleSheet(STAR_FILLED_STYLE if self._pinned else "")
        self.setToolTip(TEXT.star_help(self._pinned))

    def _clicked(self) -> None:
        if self._tile is not None:
            self.pin_requested.emit((self._tile[0], self._tile[1],
                                     not self._pinned))
