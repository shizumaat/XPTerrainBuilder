"""The Build panel's run list (issues #1556, #1537; RULINGS 2026-10-28n).

One native item view, two collapsible sections: Activity -- live, failed
and stopped rows -- then Completed, the built tiles, collapsed to its
count ("Completed (12)") until the user opens it onto the compact rows
(#1542); the choice holds for the session.  The view's own selection
model is the map's tile selection: the style draws the highlight, and a
selection the user makes here goes to the map (``selection_edited``,
``O4_Activity_Order.list_edit``).  A row is a widget the view hosts as
the item's index widget (title, bar, steps, status line and its stop /
resume button: no standard item paints those); its margins come from the
style's item-view metrics.  The Mac app's twin is ``ActivitySections``
(``ActivitySections.swift``).
"""

import O4_Activity_Order as ACTORDER
from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QStyle,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

__all__ = ["ActivityList", "completed_title", "row_margins"]


def completed_title(count):
    """The Completed section's title (the Mac app's ``completedTitle``)."""
    return "Completed (%d)" % count


def row_margins(style):
    """A row's contents margins ``(left, top, right, bottom)``: the
    style's own item-view text margins (QCommonStyle pads an item's text
    by the focus frame margin plus one)."""
    side = style.pixelMetric(QStyle.PM_FocusFrameHMargin) + 1
    top = style.pixelMetric(QStyle.PM_FocusFrameVMargin) + 1
    return (side, top, side, top)


class _Cell(QWidget):
    """Hosts one row widget as its item's index widget and keeps the
    item's size hint the row's, so the view lays the row out at its
    height as it grows or shrinks."""

    def __init__(self, item, row):
        super().__init__()
        self._item = item
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(row)
        row.show()
        self._fit()

    def row(self):
        return self.layout().itemAt(0).widget()

    def event(self, event):
        if event.type() == QEvent.LayoutRequest:
            self._fit()
        return super().event(event)

    def _fit(self):
        self._item.setSizeHint(0, self.sizeHint())


class ActivityList(QTreeWidget):
    """The two sections' rows in one tree: the section headers are
    top-level items (not selectable), each tile's row a child."""

    #: The user changed the selection: the set of tiles now selected.
    selection_edited = Signal(object)
    #: Emitted with the new expanded state when Completed is toggled.
    completed_expanded_changed = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHeaderHidden(True)
        self.setColumnCount(1)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.setExpandsOnDoubleClick(False)
        self.activity_item = self._section("Activity")
        self.completed_item = self._section(completed_title(0))
        self.activity_item.setExpanded(True)
        self.completed_item.setHidden(True)
        self._items = {}   # tile -> its row's item
        self._shown = set()   # what the list last showed selected
        self._syncing = False
        self.itemSelectionChanged.connect(self._selection_changed)
        self.itemExpanded.connect(lambda item: self._toggled(item, True))
        self.itemCollapsed.connect(lambda item: self._toggled(item, False))

    def _section(self, title):
        item = QTreeWidgetItem([title])
        item.setFlags(Qt.ItemIsEnabled)
        font = item.font(0)
        font.setBold(True)
        item.setFont(0, font)
        self.addTopLevelItem(item)
        return item

    # ── sections ──────────────────────────────────────────────────────
    def sections(self):
        """The section items, top to bottom."""
        return [self.topLevelItem(i) for i in range(self.topLevelItemCount())]

    def set_activity_shown(self, shown):
        self.activity_item.setHidden(not shown)

    def set_completed_count(self, count):
        self.completed_item.setText(0, completed_title(count))
        self.completed_item.setHidden(count == 0)

    def completed_expanded(self):
        return self.completed_item.isExpanded()

    def set_completed_expanded(self, expanded):
        self.completed_item.setExpanded(bool(expanded))

    def _toggled(self, item, expanded):
        if item is self.completed_item:
            self.completed_expanded_changed.emit(expanded)

    # ── rows ──────────────────────────────────────────────────────────
    def section_tiles(self, section):
        """The tiles of ``section``'s rows (``O4_Activity_Order.ACTIVITY``
        or ``COMPLETED``), top to bottom."""
        parent = (self.completed_item if section == ACTORDER.COMPLETED
                  else self.activity_item)
        children = [parent.child(i) for i in range(parent.childCount())]
        return [tile for child in children
                for tile, item in self._items.items() if item is child]

    def place(self, placed, rows, selected):
        """Lay ``rows`` (tile -> row widget) out as ``placed`` -- ``(tile,
        section)`` pairs in the list's order -- and show ``selected``."""
        kept = [id(row) for row in rows.values()]
        for item in self._items.values():
            cell = self.itemWidget(item, 0)
            if cell is not None and id(cell.row()) in kept:
                cell.row().setParent(None)   # the row outlives its cell
        self._syncing = True
        try:
            self.activity_item.takeChildren()
            self.completed_item.takeChildren()
            self._items = {}
            for tile, section in placed:
                parent = (self.completed_item if section == ACTORDER.COMPLETED
                          else self.activity_item)
                item = QTreeWidgetItem()
                item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                parent.addChild(item)
                self.setItemWidget(item, 0, _Cell(item, rows[tile]))
                self._items[tile] = item
        finally:
            self._syncing = False
        self.show_selected(selected)

    # ── selection ─────────────────────────────────────────────────────
    def selected_tiles(self):
        return {tile for tile, item in self._items.items() if item.isSelected()}

    def show_selected(self, selected):
        """Show the map selection (``O4_Activity_Order.shown_selected``)
        without reporting it back as an edit."""
        shown = ACTORDER.shown_selected(list(self._items), selected)
        self._syncing = True
        try:
            for tile, item in self._items.items():
                item.setSelected(tile in shown)
        finally:
            self._syncing = False
        self._shown = shown

    def shown(self):
        """What the list showed selected before the user's edit."""
        return set(self._shown)

    def _selection_changed(self):
        if self._syncing:
            return
        new = self.selected_tiles()
        if new != self.shown():
            self.selection_edited.emit(new)
