"""The choice for a tile that failed with a cause the user can fix, asked AS
SOON AS the tile fails (issue #695; the cause is #668: the tile's Custom
Scenery folder is a link to a drive that is not mounted).

"Remove the link and build on this … drive" re-queues the tile into the
RUNNING build (or starts it when the run has ended); "Cancel" dismisses.
Several such failures in one run never stack boxes: :class:`LinkFixQueue`
holds the others back until the one on screen is answered.  The run's one
box at the end (``O4_Qt_Tile_Failures.issues_box``) still lists every
failure, a re-queued one as "Fixed and re-queued."

Twin of the mac app's ``O4LinkFixQueue`` (``Sources/SceneryKit/
LinkFixQueue.swift``) and ``LinkFixAlert``.  Everything above the "Qt"
rule is pure and imports no Qt.
"""

from __future__ import annotations

import O4_Qt_Tile_Failures as QTFAIL

__all__ = ["LinkFixQueue", "fixable_link", "link_fix_box"]

CANCEL_BUTTON = "Cancel"


def fixable_link(event):
    """The link a failed tile's ``BuildDone`` offers to remove, or None."""
    found = QTFAIL.removable_links([event])
    return found[0][1] if found else None


class LinkFixQueue:
    """The fixable failures of the running build, one choice at a time.

    ``current`` is the ``(event, link)`` on screen (or None), ``waiting``
    the ones behind it in the order their tiles failed.  ``requeued`` is
    the identity (``id``) of every ``BuildDone`` the user fixed — the
    run-end box marks those and offers them no button.
    """

    def __init__(self):
        self.current = None
        self.waiting = []
        self.requeued = set()

    def idle(self):
        return self.current is None

    def offer(self, event):
        """A tile's ``BuildDone`` arrived: queue its choice when it has one.
        True when queued (a tile already being asked is not asked twice)."""
        link = fixable_link(event)
        if link is None:
            return False
        key = (int(event.lat), int(event.lon), link)
        pending = ([self.current] if self.current else []) + self.waiting
        if any((int(e.lat), int(e.lon), l) == key for (e, l) in pending):
            return False
        if self.current is None:
            self.current = (event, link)
        else:
            self.waiting.append((event, link))
        return True

    def answer(self):
        """The choice on screen was answered: return it, show the next."""
        answered = self.current
        self.current = self.waiting.pop(0) if self.waiting else None
        return answered

    def mark_requeued(self, event):
        self.requeued.add(id(event))


def box_texts(event):
    """``(title, text)`` of the choice: the engine's own three sentences."""
    entry = next(f for f in event.failures
                 if f.get("code") == "output_link_unmounted")
    return (entry.get("what", ""),
            "%s\n\n%s" % (entry.get("why", ""), entry.get("remedy", "")))


# --- Qt ------------------------------------------------------------------
def link_fix_box(event, parent=None):
    """The non-modal choice for one fixable failure: ``(box, remove)`` —
    the build keeps running while it is on screen."""
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QMessageBox

    (title, text) = box_texts(event)
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Warning)
    box.setWindowTitle(title)
    box.setText(title)
    box.setInformativeText(text)
    box.setWindowModality(Qt.NonModal)
    remove = box.addButton(QTFAIL.REMOVE_LINK_BUTTON, QMessageBox.AcceptRole)
    box.addButton(CANCEL_BUTTON, QMessageBox.RejectRole)
    return (box, remove)
