import Foundation
import SceneryKit

/// Selecting whole shapes (issue #759, patch-editor spec §4 as amended
/// 2026-10-15): a click on a line selects the shape (way) it belongs to,
/// JOSM-style; ⇧-click adds or removes it; a repeat click on the same spot
/// cycles through the shapes sharing that edge. A selected shape drags as a
/// whole (all its nodes, one undo step, no snap) and deletes as a whole
/// (`deleteWays`). Node selection (`selection`) and shape selection
/// (`shapeSelection`) live side by side; the map, the 3D markers and the
/// inspector read both.
extension PatchEditModel {
    /// The nodes of the selected shapes.
    var shapeNodes: Set<Int64> {
        guard let doc = document, !shapeSelection.isEmpty else { return [] }
        return Set(doc.ways.filter { shapeSelection.contains($0.id) }.flatMap(\.refs))
    }

    /// Every node drawn as selected (and marked in 3D): the selected nodes
    /// plus the selected shapes' nodes.
    var markedNodes: Set<Int64> { selection.union(shapeNodes) }

    /// What a drag that starts on `node` moves: the selected nodes and the
    /// selected shapes' nodes, sorted. Snapping applies only when no shape
    /// is selected (a shape drag never snaps).
    var dragNodes: [Int64] { markedNodes.sorted() }

    /// A click on an edge a–b at screen point (x, y). `toggle` (⇧) adds or
    /// removes the edge's smallest shape; otherwise the shape replaces the
    /// selection, and a repeat click on the same spot steps to the next
    /// shape on that edge. Returns the chosen way id.
    @discardableResult
    func clickEdge(_ a: Int64, _ b: Int64, x: Double, y: Double, toggle: Bool) -> Int64? {
        guard let doc = document else { return nil }
        let candidates = PatchShapePick.shapes(onEdge: a, b, in: doc)
        if toggle {
            guard let first = candidates.first else { return nil }
            if shapeSelection.contains(first) { shapeSelection.remove(first) } else { shapeSelection.insert(first) }
            lastShapeClick = nil
            return first
        }
        let previous = shapeSelection == lastShapeClick.map { [$0.chosen] } ? lastShapeClick : nil
        guard let click = PatchShapePick.choose(candidates: candidates, x: x, y: y, previous: previous) else {
            return nil
        }
        lastShapeClick = click
        selectShapes([click.chosen])
        return click.chosen
    }

    /// Make `ways` the whole selection (no nodes).
    func selectShapes(_ ways: Set<Int64>) {
        if !selection.isEmpty { selection = [] }
        if shapeSelection != ways { shapeSelection = ways }
    }

    /// Esc, a click on empty map: nothing selected.
    func clearSelection() {
        if !selection.isEmpty { selection = [] }
        if !shapeSelection.isEmpty { shapeSelection = [] }
        lastShapeClick = nil
    }

    var hasSelection: Bool { !selection.isEmpty || !shapeSelection.isEmpty }

    /// ⌫ / ⌦, "Delete shape", "Delete node(s)": the selected shapes go
    /// first (`deleteWays`), then the selected nodes that are still there
    /// (`deleteNodes`) — ONE undo step.
    func deleteSelection() {
        let ways = shapeSelection.sorted(), nodes = selection.sorted()
        guard !ways.isEmpty || !nodes.isEmpty else { return }
        let name = ways.isEmpty ? (nodes.count == 1 ? "Delete Node" : "Delete Nodes")
            : (ways.count == 1 ? "Delete Shape" : "Delete Shapes")
        let done = perform(name) { doc in
            if !ways.isEmpty { try doc.deleteWays(ways) }
            let left = nodes.filter { doc.nodes[$0] != nil }
            if !left.isEmpty { try doc.deleteNodes(left) }
        }
        if done { clearSelection() }
    }

    /// After an edit, undo or redo: shapes that no longer exist leave the
    /// selection.
    func dropVanishedShapes() {
        guard let doc = document, !shapeSelection.isEmpty else { return }
        let present = Set(doc.ways.map(\.id))
        let gone = shapeSelection.subtracting(present)
        if !gone.isEmpty { shapeSelection.subtract(gone) }
    }
}
