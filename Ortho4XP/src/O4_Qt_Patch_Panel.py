"""The "Patch · ICAO" box in the Qt side panel, below Activity (spec
patch-editor-20261015 §4; mockup side panel; the Mac app's
``PatchInspector``, ``PatchNodeInspector`` and ``PatchSaveBar`` — same
words).

View mode: the source line, counts, the stale note, and "Build this tile
first" when the zoomed airport has no patch.  Edit mode adds the node
inspector (one node: lat/lon, elevation, "Used by", Delete; several: the
range, "Set to", "Offset", Delete N; a selected shape, #759: role, ref,
nodes, area, perimeter, elevation range, "Used by", "Copy shape reference",
"Delete shape").  A click on the node's lat/lon copies ``lat, lon`` (#1281).
The save bar shows in Edit mode and whenever there is something to save
or rebuild; "Undo" confirms inside the box.  The widgets are built once and refreshed in place, so a
field being typed in keeps its focus.
"""
from __future__ import annotations

import typing as _t

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (QFrame, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
                               QPushButton, QVBoxLayout, QWidget)

import O4_Glossary as GLOSSARY
import O4_Qt_Patch_Reference as REFERENCE
import O4_Qt_Patch_ShapePick as PICK
import O4_Qt_Text_Scale as QTTEXT
import O4_Version
from O4_Qt_Patch_Controller import PatchController, built_date_text
from O4_Qt_Patch_Geometry import role_name

__all__ = ["PatchPanel", "parse_number", "source_line", "node_lat_lon", "FEET_PER_METRE"]

FEET_PER_METRE = 3.280839895
STALE_COLOR = "#F29419"
SELECTION_COLOR = "#FFD60A"
#: How long a "Copied" note stays (ms; the Mac's ``copiedNoteSeconds``).
COPIED_NOTE_MS = 1500


def parse_number(text: str) -> float | None:
    """A typed number ("62.7", "62,7", "+0.50"), or None."""
    try:
        return float(text.strip().replace(",", "."))
    except ValueError:
        return None


def source_line(patch, file_mtime: float | None) -> str:
    """"Automatic, built 12 Oct" / "Edited · KHIO_edited.patch.osm" /
    "Manual · KHIO_runways.patch.osm"."""
    if patch.source == "auto":
        date = built_date_text(file_mtime)
        return "Automatic, built %s" % date if date else "Automatic"
    return ("Manual · " if patch.is_hand_made else "Edited · ") + patch.file_name


def _plural(n: int, word: str) -> str:
    return "%s %s%s" % (format(n, ","), word, "" if n == 1 else "s")


def _note(text: str = "", color: str | None = None) -> QLabel:
    label = QLabel(text)
    label.setWordWrap(True)
    # One point under the app font, following the text scale (#827).
    QTTEXT.size_text(label, points=max(QTTEXT.base_points() - 1, 8))
    label.setStyleSheet("color: %s;" % color if color else "color: palette(mid);")
    return label


class _ClickLabel(QLabel):
    """A value a click copies (the node's lat / lon, #1281)."""

    clicked = Signal()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(event)


def _row(key: str, clickable: bool = False) -> tuple[QWidget, QLabel]:
    w = QWidget()
    h = QHBoxLayout(w)
    h.setContentsMargins(0, 0, 0, 0)
    k = QLabel(key)
    k.setStyleSheet("color: palette(mid);")
    v = _ClickLabel() if clickable else QLabel()
    v.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
    if clickable:
        v.setCursor(Qt.PointingHandCursor)
        v.setToolTip("Click to copy “lat, lon”")
    else:
        v.setTextInteractionFlags(Qt.TextSelectableByMouse)
    v.setWordWrap(True)
    h.addWidget(k)
    h.addWidget(v, 1)
    return w, v


def _field(label: str, placeholder: str, apply: _t.Callable[[float], _t.Any],
           button: bool) -> tuple[QWidget, QLineEdit]:
    w = QWidget()
    h = QHBoxLayout(w)
    h.setContentsMargins(0, 0, 0, 0)
    h.setSpacing(6)
    k = QLabel(label)
    k.setStyleSheet("color: palette(mid);")
    k.setMinimumWidth(48)
    edit = QLineEdit()
    edit.setPlaceholderText(placeholder)

    def go():
        v = parse_number(edit.text())
        if v is not None:
            apply(v)
    edit.returnPressed.connect(go)
    h.addWidget(k)
    h.addWidget(edit, 1)
    h.addWidget(QLabel("m"))
    if button:
        b = QPushButton("Apply")
        b.clicked.connect(go)
        edit.textChanged.connect(lambda t: b.setEnabled(parse_number(t) is not None))
        b.setEnabled(False)
        h.addWidget(b)
    return w, edit



def node_coord(value):
    """One node coordinate as the node info shows it: 9 decimals."""
    return "%.9f" % value


def node_lat_lon(lat, lon):
    """A position in the node format: ``lat, lon``, 9 decimals each."""
    return "%s, %s" % (node_coord(lat), node_coord(lon))

class PatchPanel(QGroupBox):
    """The Patch box; hidden while the layer is hidden."""

    def __init__(self, controller: PatchController, parent=None):
        super().__init__(GLOSSARY.TERMS["ground_shape"], parent)
        self.controller = controller
        self.model = controller.model
        v = QVBoxLayout(self)
        v.setSpacing(6)
        self.status = _note()
        v.addWidget(self.status)
        self.source_row, self.source_value = _row("Source")
        self.shapes_row, self.shapes_value = _row("Shapes")
        v.addWidget(self.source_row)
        v.addWidget(self.shapes_row)
        self.mesh_note = _note()
        self.stale_note = _note("The engine, elevation or airport data has changed since this "
                                "ground shape was edited. The automatic shape would now be "
                                "different, but your edited shape is still used.", STALE_COLOR)
        v.addWidget(self.mesh_note)
        v.addWidget(self.stale_note)
        self.inspector = self._make_inspector()
        v.addWidget(self.inspector)
        self.save_bar = self._make_save_bar()
        v.addWidget(self.save_bar)
        self._shown_node = None
        self.model.document_changed.connect(self.refresh)
        self.model.selection_changed.connect(self.refresh)
        self.model.status_changed.connect(self.refresh)
        controller.state_changed.connect(self.refresh)
        self.refresh()

    # ─── construction ──────────────────────────────────────────────────
    def _make_inspector(self) -> QWidget:
        box = QWidget()
        v = QVBoxLayout(box)
        v.setContentsMargins(0, 4, 0, 0)
        v.setSpacing(6)
        m = self.model
        self.hint = _note("Click a node or a line to select it (a line selects its whole shape); "
                          "⇧-click or ⇧-drag to select several.")
        v.addWidget(self.hint)
        # one node
        self.single = QWidget()
        s = QVBoxLayout(self.single)
        s.setContentsMargins(0, 0, 0, 0)
        head = QHBoxLayout()
        self.node_title = QLabel()
        self.node_title.setStyleSheet("font-weight: 600;")
        head.addWidget(self.node_title)
        head.addStretch(1)
        self.node_count_note = _note("1 selected")
        head.addWidget(self.node_count_note)
        s.addLayout(head)
        self.lat_row, self.lat_value = _row("lat", clickable=True)
        self.lon_row, self.lon_value = _row("lon", clickable=True)
        self.lat_value.clicked.connect(self.copy_node_coordinates)
        self.lon_value.clicked.connect(self.copy_node_coordinates)
        s.addWidget(self.lat_row)
        s.addWidget(self.lon_row)
        alt_row, self.alt_edit = _field("Elevation", "", m.set_selection_alt, button=False)
        s.addWidget(alt_row)
        self.alt_note = _note()
        s.addWidget(self.alt_note)
        self.used_by = _note()
        s.addWidget(self.used_by)
        self.delete_one = QPushButton("Delete node")
        self.delete_one.clicked.connect(m.delete_selection)
        s.addWidget(self.delete_one)
        v.addWidget(self.single)
        # several nodes
        self.multi = QWidget()
        u = QVBoxLayout(self.multi)
        u.setContentsMargins(0, 0, 0, 0)
        head = QHBoxLayout()
        self.multi_title = QLabel()
        self.multi_title.setStyleSheet("font-weight: 600;")
        self.multi_range = QLabel()
        head.addWidget(self.multi_title)
        head.addStretch(1)
        head.addWidget(self.multi_range)
        u.addLayout(head)
        self.multi_note = _note()
        u.addWidget(self.multi_note)
        set_row, self.set_edit = _field("Set to", "—", m.set_selection_alt, button=True)
        off_row, self.offset_edit = _field("Offset", "+0.50", m.offset_selection_alt, button=True)
        u.addWidget(set_row)
        u.addWidget(off_row)
        self.delete_many = QPushButton()
        self.delete_many.clicked.connect(m.delete_selection)
        u.addWidget(self.delete_many)
        v.addWidget(self.multi)
        v.addWidget(self._make_shape_inspector())
        return box

    def _make_shape_inspector(self) -> QWidget:
        """Selected shapes (#759; the Mac's ``PatchShapeInspector``)."""
        self.shape_box = QWidget()
        s = QVBoxLayout(self.shape_box)
        s.setContentsMargins(0, 0, 0, 0)
        head = QHBoxLayout()
        self.shape_title = QLabel()
        self.shape_title.setStyleSheet("font-weight: 600;")
        self.shape_id = _note()
        head.addWidget(self.shape_title)
        head.addStretch(1)
        head.addWidget(self.shape_id)
        s.addLayout(head)
        self.shape_rows = {}
        for key in ("ref", "Nodes", "Area", "Perimeter", "Elevation", "Used by"):
            row, value = _row(key)
            self.shape_rows[key] = (row, row.layout().itemAt(0).widget(), value)
            s.addWidget(row)
        self.shape_mesh_note = _note()
        self.shape_extra_note = _note()
        s.addWidget(self.shape_mesh_note)
        s.addWidget(self.shape_extra_note)
        copy_row = QHBoxLayout()
        self.copy_shape = QPushButton(REFERENCE.COPY_SHAPE_REFERENCE)
        self.copy_shape.setToolTip("Copies a text block that identifies this shape, "
                                   "for an issue report.")
        self.copy_shape.clicked.connect(self.copy_shape_reference)
        self.shape_copied = _note("Copied")
        self.shape_copied.setVisible(False)
        copy_row.addWidget(self.copy_shape)
        copy_row.addWidget(self.shape_copied)
        copy_row.addStretch(1)
        s.addLayout(copy_row)
        s.addWidget(_note("Drag a selected shape to move it; nodes it shares with other "
                          "shapes move too."))
        self.delete_shapes = QPushButton()
        self.delete_shapes.clicked.connect(self.model.delete_selection)
        s.addWidget(self.delete_shapes)
        return self.shape_box

    def _make_save_bar(self) -> QWidget:
        bar = QWidget()
        v = QVBoxLayout(bar)
        v.setContentsMargins(0, 4, 0, 0)
        v.setSpacing(6)
        c = self.controller
        self.rebuild_note = _note()
        self.rebuild_button = QPushButton("Rebuild tile")
        self.rebuild_button.clicked.connect(c.rebuild_tile)
        self.hand_made_note = _note()
        v.addWidget(self.rebuild_note)
        v.addWidget(self.rebuild_button)
        v.addWidget(self.hand_made_note)
        self.confirm = QFrame()
        self.confirm.setStyleSheet("QFrame { background: rgba(242,148,25,30); border-radius: 6px; }")
        cv = QVBoxLayout(self.confirm)
        self.confirm_text = _note()
        cv.addWidget(self.confirm_text)
        ch = QHBoxLayout()
        ch.addStretch(1)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(lambda: self._confirming(False))
        self.confirm_button = QPushButton()
        self.confirm_button.clicked.connect(self._revert)
        ch.addWidget(cancel)
        ch.addWidget(self.confirm_button)
        cv.addLayout(ch)
        v.addWidget(self.confirm)
        self.error_note = _note("", "orange")
        v.addWidget(self.error_note)
        row = QHBoxLayout()
        self.unsaved_label = QLabel()
        self.unsaved_label.setStyleSheet("color: %s;" % SELECTION_COLOR)
        row.addWidget(self.unsaved_label)
        row.addStretch(1)
        self.revert_button = QPushButton(GLOSSARY.TERMS["undo_edits"])
        self.revert_button.clicked.connect(lambda: self._confirming(True))
        self.save_button = QPushButton(GLOSSARY.TERMS["save_edits"])
        self.save_button.setDefault(True)
        self.save_button.setToolTip("Save your edits to the airport ground shape (Ctrl+S)")
        self.save_button.clicked.connect(c.save)
        row.addWidget(self.revert_button)
        row.addWidget(self.save_button)
        v.addLayout(row)
        self._confirm_open = False
        self._confirm_path = None
        return bar

    def _confirming(self, on: bool) -> None:
        self._confirm_open = on
        self._confirm_path = self.model.patch.path if (on and self.model.patch) else None
        self.refresh()

    def _revert(self) -> None:
        self._confirming(False)
        self.controller.revert_to_auto()

    # ─── refresh ───────────────────────────────────────────────────────
    def refresh(self) -> None:
        c, m = self.controller, self.model
        icao = (m.patch.icao if c.state == c.LOADED and m.patch else c.state_icao)
        visible = c.state != c.HIDDEN and icao is not None
        self.setVisible(visible)
        if not visible:
            return
        self.setTitle("%s · %s" % (GLOSSARY.TERMS["ground_shape"], icao))
        loaded = c.state == c.LOADED and m.doc is not None
        status = {c.LOADING: "Loading the ground shape…", c.FAILED: c.state_message,
                  c.NO_PATCH: ("No ground shape was built for this airport." if c.tile_built
                               else "Build this tile first.")}.get(c.state, "")
        self.status.setText(status)
        self.status.setStyleSheet("color: orange;" if c.state == c.FAILED else "color: palette(mid);")
        self.status.setVisible(bool(status))
        for w in (self.source_row, self.shapes_row):
            w.setVisible(loaded)
        if not loaded:
            for w in (self.mesh_note, self.stale_note, self.inspector, self.save_bar):
                w.setVisible(False)
            return
        p, doc = m.patch, m.doc
        self.source_value.setText(source_line(p, c.file_mtime))
        self.shapes_value.setText("%s nodes · %s shapes" % (format(len(doc.nodes), ","),
                                                           format(len(doc.ways), ",")))
        mesh = sum(1 for n in doc.nodes.values() if n[3] is None)
        self.mesh_note.setText("%s nodes: elevation from the mesh." % format(mesh, ","))
        self.mesh_note.setVisible(mesh > 0)
        self.stale_note.setVisible(p.stale)
        self.stale_note.setToolTip(", ".join(p.stale_inputs))
        editing = m.mode == "Edit"
        self.inspector.setVisible(editing)
        if editing:
            self._refresh_inspector()
        n = m.unsaved_edits
        show_bar = (editing or n > 0 or p.tile in m.tiles_needing_rebuild
                    or m.edit_error is not None)
        self.save_bar.setVisible(show_bar)
        if show_bar:
            self._refresh_save_bar(n)

    # ─── copying (#1281) ───────────────────────────────────────────────
    def shape_reference(self, way_id: int) -> str:
        """The "Copy shape reference" block for one way of the open patch."""
        m = self.model
        return REFERENCE.shape_reference(m.patch, m.doc, way_id, O4_Version.version)

    def copy_node_coordinates(self) -> None:
        """The selected node's ``lat, lon``, then "Copied" in its header."""
        m = self.model
        ids = [i for i in m.selection if m.doc is not None and i in m.doc.nodes]
        if len(ids) != 1:
            return
        _nid, lat, lon, _alt = m.doc.nodes[ids[0]]
        QGuiApplication.clipboard().setText(node_lat_lon(lat, lon))
        self.node_count_note.setText("Copied")
        QTimer.singleShot(COPIED_NOTE_MS, self.node_count_note,
                          lambda: self.node_count_note.setText("1 selected"))

    def copy_shape_reference(self) -> None:
        m = self.model
        if len(m.shape_selection) != 1 or m.doc is None:
            return
        (way_id,) = m.shape_selection
        QGuiApplication.clipboard().setText(self.shape_reference(way_id))
        self.shape_copied.setVisible(True)
        QTimer.singleShot(COPIED_NOTE_MS, self.shape_copied,
                          lambda: self.shape_copied.setVisible(False))

    def _refresh_inspector(self) -> None:
        m, doc = self.model, self.model.doc
        ids = sorted(i for i in m.selection if i in doc.nodes)
        shapes = bool(m.shape_selection)
        self.shape_box.setVisible(shapes)
        if shapes:
            self.hint.setVisible(False)
            self.single.setVisible(False)
            self.multi.setVisible(False)
            self._refresh_shapes(len(ids))
            return
        self.hint.setVisible(not ids)
        self.single.setVisible(len(ids) == 1)
        self.multi.setVisible(len(ids) > 1)
        if len(ids) == 1:
            node = doc.nodes[ids[0]]
            nid, lat, lon, alt = node
            self.node_title.setText("Node %d" % nid)
            self.lat_value.setText(node_coord(lat))
            self.lon_value.setText(node_coord(lon))
            if self._shown_node != node:
                self._shown_node = node
                self.alt_edit.setText("" if alt is None else "%.2f" % alt)
                self.alt_edit.setPlaceholderText("from the mesh" if alt is None else "")
            parts = []
            if alt is not None:
                parts.append("%.1f ft" % (alt * FEET_PER_METRE))
            was = m.loaded_nodes.get(nid)
            if was is None:
                parts.append("new node")
            else:
                parts.append("was " + ("from the mesh" if was[3] is None else "%.2f m" % was[3]))
            self.alt_note.setText(" · ".join(parts))
            roles = sorted({r for w in doc.ways if nid in w.refs
                            for r in [role_name(w.tags)] if r})
            self.used_by.setText("Used by  " + ", ".join(roles))
            self.used_by.setVisible(bool(roles))
        elif ids:
            self._shown_node = None
            alts = [doc.nodes[i][3] for i in ids if doc.nodes[i][3] is not None]
            self.multi_title.setText("%s nodes" % format(len(ids), ","))
            self.multi_range.setText("%.2f – %.2f m" % (min(alts), max(alts)) if alts else "")
            lacking = len(ids) - len(alts)
            self.multi_note.setText("%s of them take their elevation from the mesh; Offset "
                                    "leaves those alone." % format(lacking, ","))
            self.multi_note.setVisible(lacking > 0)
            self.delete_many.setText("Delete %s nodes" % format(len(ids), ","))

    def _refresh_shapes(self, extra_nodes: int) -> None:
        m, doc = self.model, self.model.doc
        ways = [w for w in doc.ways if w.id in m.shape_selection]
        one = len(ways) == 1
        for row, _key, _value in self.shape_rows.values():
            row.setVisible(one)
        self.shape_mesh_note.setVisible(False)
        if one:
            way = ways[0]
            st = PICK.shape_stats(doc, way.id)
            self.shape_title.setText(role_name(way.tags) or "shape")
            self.shape_id.setText("Way %d" % way.id)
            values = {
                "ref": way.tags.get("ref"),
                "Nodes": format(st.node_count, ","),
                "Area": "%s m²" % format(round(st.area_m2), ",") if way.closed else None,
                "Perimeter": "%s m" % format(round(st.perimeter_m), ","),
                "Elevation": ("%.2f – %.2f m" % (st.min_alt, st.max_alt)
                              if st.min_alt is not None else None),
                "Used by": "1 other shape" if st.neighbours == 1
                else "%s other shapes" % format(st.neighbours, ","),
            }
            for key, (row, label, value) in self.shape_rows.items():
                row.setVisible(values[key] is not None)
                value.setText(values[key] or "")
            self.shape_rows["Perimeter"][1].setText("Perimeter" if way.closed else "Length")
            self.shape_mesh_note.setText("%s nodes: elevation from the mesh."
                                         % format(st.nodes_without_elevation, ","))
            self.shape_mesh_note.setVisible(st.nodes_without_elevation > 0)
        else:
            self.shape_title.setText(_plural(len(ways), "shape"))
            self.shape_id.setText(_plural(len(m.shape_nodes), "node"))
        self.shape_extra_note.setText("Also %s, deleted with the shapes."
                                      % _plural(extra_nodes, "selected node"))
        self.shape_extra_note.setVisible(extra_nodes > 0)
        self.copy_shape.setVisible(one)
        self.delete_shapes.setText("Delete shape" if one else "Delete %s shapes" % format(len(ways), ","))

    def _refresh_save_bar(self, n: int) -> None:
        c, m, p = self.controller, self.model, self.model.patch
        if self._confirm_open and self._confirm_path != p.path:
            self._confirm_open = False
        needs_rebuild = p.tile in m.tiles_needing_rebuild and n == 0
        self.rebuild_note.setText(
            "The tile is out of date until you rebuild it. Fitting custom airport buildings is "
            "off for this airport while the edited ground shape is in use." if p.source == "manual"
            else "The tile is out of date until you rebuild it.")
        self.rebuild_note.setVisible(needs_rebuild)
        self.rebuild_button.setVisible(needs_rebuild)
        self.rebuild_button.setEnabled(not c.is_building())
        self.hand_made_note.setText("This airport ground shape was made outside the editor. "
                                    "Saving writes back to %s; there is no automatic shape to "
                                    "go back to." % p.file_name)
        self.hand_made_note.setVisible(p.is_hand_made)
        can_revert = not p.is_hand_made and (p.source == "manual" or n > 0)
        self.confirm.setVisible(self._confirm_open and can_revert)
        if p.source == "manual":
            text = ("Go back to the automatic ground shape? %s is moved aside to %s.disabled "
                    "(not deleted), and the next build of this tile uses the automatic shape."
                    % (p.file_name, p.file_name))
            if n > 0:
                text += " Your %s discarded." % ("1 unsaved edit is" if n == 1
                                                 else "%d unsaved edits are" % n)
            self.confirm_button.setText(GLOSSARY.TERMS["undo_edits"])
        else:
            text = "Discard your %s and reload the automatic ground shape?" % _plural(n, "unsaved edit")
            self.confirm_button.setText("Discard edits")
        self.confirm_text.setText(text)
        self.error_note.setText(m.edit_error or "")
        self.error_note.setVisible(bool(m.edit_error))
        self.unsaved_label.setText("● %s" % _plural(n, "unsaved edit") if n > 0 else "")
        self.revert_button.setVisible(can_revert and not self._confirm_open)
        self.save_button.setText("Saving…" if m.is_saving else "Save")
        self.save_button.setEnabled(n > 0 and not m.is_saving)
