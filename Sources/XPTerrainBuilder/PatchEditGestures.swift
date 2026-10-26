import SwiftUI
import AppKit
import SceneryKit

// Edit mode on the map (patch-editor spec §4, §3.3; mockup interaction
// table): click selects (8 pt), ⇧-click toggles, ⇧-drag box-selects, a
// drag on a node moves the selection (snapping the grabbed node while the
// pointer is within 8 pt of another node), a drag on empty map pans, a
// click on a "+" handle inserts a node. A click on a LINE selects its whole
// shape (#759, `PatchShapeSelection.swift`; node > "+" > line > empty map),
// and a drag on a selected shape's line or nodes moves the whole shape
// without snapping. A drag never edits the document
// per frame: the moved shapes are drawn here from the pointer delta, and
// ONE edit commits on mouse-up.

/// What the base patch layer leaves to the edit layer during a node drag.
struct PatchDragSkip: Equatable {
    /// Indices into `document.ways` whose shapes move.
    let ways: Set<Int>
    let nodes: Set<Int64>
}

/// One undirected edge, for the "+" handles.
struct PatchEdgeKey: Hashable {
    let a: Int64
    let b: Int64
    init(_ a: Int64, _ b: Int64) { self.a = min(a, b); self.b = max(a, b) }
}

/// The live drag and hover (redraws the edit layer only).
final class PatchDragState: ObservableObject {
    enum Kind: Equatable {
        case idle
        /// Mouse down on empty map or a handle: a click, or a pan once it moves.
        case pending
        case pan(anchor: MapCamera)
        case nodes(grabbed: Int64, ids: [Int64])
        case box
    }

    @Published var kind: Kind = .idle
    @Published var current: CGPoint = .zero
    @Published var snapTarget: Int64?
    @Published var hoverEdge: PatchEdgeKey?
    var start: CGPoint = .zero
    var dlat = 0.0
    var dlon = 0.0
    var pressedHandle: PatchEditScreen.Handle?
    /// The line the press landed on (no node, no handle there).
    var pressedEdge: PatchEdgeKey?
}

/// The document as seen through the map camera: screen ↔ ground, and the
/// hit tests the gestures and the drawing share.
struct PatchEditScreen {
    let doc: PatchDocument
    let camera: MapCamera
    let size: CGSize

    struct Handle: Equatable {
        let edge: PatchEdgeKey
        let point: CGPoint
    }

    /// The click / snap radius (owner: 8 pt on screen).
    static let hitRadius = PatchSnap.radius
    /// Edges shorter than this on screen get no "+" (it would sit on a node).
    static let minHandleEdge: Double = 24

    func point(lat: Double, lon: Double) -> CGPoint { camera.point(lon: lon, lat: lat, in: size) }

    func point(_ node: PatchNode) -> CGPoint { point(lat: node.lat, lon: node.lon) }

    func coordinate(_ p: CGPoint) -> (lon: Double, lat: Double) { camera.coordinate(of: p, in: size) }

    /// A screen point on the document's metric plane (the grid's frame).
    func metric(_ p: CGPoint) -> (x: Double, y: Double) {
        let c = coordinate(p)
        return doc.frame.metres(lat: c.lat, lon: c.lon)
    }

    /// `points` on screen as metres on the ground, with a margin (the exact
    /// test is then done in screen points).
    func metres(points: Double) -> Double { points / camera.scale * doc.frame.metresPerDegreeLon * 1.1 }

    /// The node the pointer is on (8 pt; nearest, ties by survivor key).
    func nodeHit(at p: CGPoint, grid: PatchSpatialGrid, excluding: Set<Int64> = []) -> Int64? {
        PatchSnap.target(pointerX: p.x, pointerY: p.y,
                         candidates: candidates(near: p, grid: grid, excluding: excluding),
                         identityDp: doc.identityDp)
    }

    private func candidates(near p: CGPoint, grid: PatchSpatialGrid, excluding: Set<Int64>) -> [PatchSnap.Candidate] {
        let m = metric(p), r = metres(points: Self.hitRadius)
        return grid.nodes(minX: m.x - r, minY: m.y - r, maxX: m.x + r, maxY: m.y + r).compactMap { id in
            guard !excluding.contains(id), let n = doc.nodes[id] else { return nil }
            let q = point(n)
            return PatchSnap.Candidate(id: id, x: q.x, y: q.y, lat: n.lat, lon: n.lon)
        }
    }

    /// The edge under the pointer for the hover "+" (none over a node).
    func hoverEdge(at p: CGPoint, grid: PatchSpatialGrid) -> PatchEdgeKey? {
        guard nodeHit(at: p, grid: grid) == nil else { return nil }
        let m = metric(p)
        return grid.nearestEdge(x: m.x, y: m.y, within: metres(points: Self.hitRadius)).map { PatchEdgeKey($0.a, $0.b) }
    }

    /// "+" handles: every edge of the selected nodes' shapes (up to 200
    /// selected nodes), of the selected shapes, and the hovered edge, long
    /// enough on screen.
    func handles(selection: Set<Int64>, shapes: Set<Int64> = [], hover: PatchEdgeKey?) -> [Handle] {
        var seen = Set<PatchEdgeKey>()
        var out: [Handle] = []
        let bounds = CGRect(origin: .zero, size: size)
        func add(_ a: Int64, _ b: Int64) {
            let key = PatchEdgeKey(a, b)
            guard a != b, seen.insert(key).inserted, let na = doc.nodes[a], let nb = doc.nodes[b] else { return }
            let pa = point(na), pb = point(nb)
            let mid = CGPoint(x: (pa.x + pb.x) / 2, y: (pa.y + pb.y) / 2)
            guard hypot(pb.x - pa.x, pb.y - pa.y) >= Self.minHandleEdge, bounds.contains(mid) else { return }
            out.append(Handle(edge: key, point: mid))
        }
        if selection.count <= 200 {
            var ways = Set(selection.flatMap { doc.wayIndicesByNode[$0] ?? [] })
            if !shapes.isEmpty { ways.formUnion(doc.ways.indices.filter { shapes.contains(doc.ways[$0].id) }) }
            for w in ways.sorted() {
                let refs = doc.ways[w].refs
                for i in refs.indices.dropLast() { add(refs[i], refs[i + 1]) }
            }
        }
        if let hover { add(hover.a, hover.b) }
        return out
    }

    func handleHit(at p: CGPoint, in handles: [Handle]) -> Handle? {
        handles.map { ($0, hypot($0.point.x - p.x, $0.point.y - p.y)) }
            .filter { $0.1 <= Self.hitRadius }
            .min { $0.1 < $1.1 }?.0
    }

    /// Nodes inside a screen rectangle (box select).
    func nodes(in rect: CGRect, grid: PatchSpatialGrid) -> [Int64] {
        let corners = [CGPoint(x: rect.minX, y: rect.minY), CGPoint(x: rect.maxX, y: rect.maxY)].map(metric)
        let ids = grid.nodes(minX: min(corners[0].x, corners[1].x), minY: min(corners[0].y, corners[1].y),
                             maxX: max(corners[0].x, corners[1].x), maxY: max(corners[0].y, corners[1].y))
        return ids.filter { id in doc.nodes[id].map { rect.contains(point($0)) } ?? false }
    }
}

/// The Edit-mode layer over the patch: gestures, hover, and the drawing of
/// the selection, the moving shapes, the snap highlight, the "+" handles
/// and the selection box.
struct PatchEditLayer: View {
    @ObservedObject var model: PatchEditModel
    @ObservedObject var drag: PatchDragState
    @ObservedObject var camera: ViewState<MapCamera>

    static let selectionColor = MapCanvasView.buildSelection
    /// Movement below this is a click.
    static let clickSlop: Double = 3

    var body: some View {
        GeometryReader { proxy in
            let selection = model.selection, shapes = model.shapeSelection, skip = model.dragSkip
            Canvas(rendersAsynchronously: false) { context, size in
                guard let doc = model.document else { return }
                let screen = PatchEditScreen(doc: doc, camera: camera.value, size: size)
                draw(screen, selection: selection, shapes: shapes, skip: skip, in: context)
            }
            .contentShape(Rectangle())
            .gesture(DragGesture(minimumDistance: 0)
                .onChanged { changed($0, size: proxy.size) }
                .onEnded { ended($0, size: proxy.size) })
            .onContinuousHover { phase in hover(phase, size: proxy.size) }
        }
    }

    private func screen(_ size: CGSize) -> (PatchEditScreen, PatchSpatialGrid)? {
        guard let doc = model.document, let grid = model.grid else { return nil }
        return (PatchEditScreen(doc: doc, camera: camera.value, size: size), grid)
    }

    // MARK: - Gestures

    private func changed(_ value: DragGesture.Value, size: CGSize) {
        guard let (screen, grid) = screen(size) else { return }
        let moved = hypot(value.translation.width, value.translation.height) >= Self.clickSlop
        switch drag.kind {
        case .idle:
            begin(at: value.startLocation, screen: screen, grid: grid)
        case .pending:
            if moved {
                model.lastShapeClick = nil
                drag.kind = .pan(anchor: camera.value)
                pan(value, size: size)
            }
        case .pan:
            pan(value, size: size)
        case .nodes(_, let ids):
            guard moved || model.dragSkip != nil else { return }
            if model.dragSkip == nil {
                let doc = screen.doc
                model.dragSkip = PatchDragSkip(ways: Set(ids.flatMap { doc.wayIndicesByNode[$0] ?? [] }),
                                               nodes: Set(ids))
            }
            let a = screen.coordinate(drag.start), b = screen.coordinate(value.location)
            drag.dlat = b.lat - a.lat
            drag.dlon = b.lon - a.lon
            let target = model.shapeSelection.isEmpty  // a shape drag never snaps (#759)
                ? screen.nodeHit(at: value.location, grid: grid, excluding: Set(ids)) : nil
            if drag.snapTarget != target { drag.snapTarget = target }
            drag.current = value.location
        case .box:
            drag.current = value.location
        }
    }

    private func begin(at p: CGPoint, screen: PatchEditScreen, grid: PatchSpatialGrid) {
        drag.start = p
        drag.current = p
        drag.hoverEdge = nil
        if NSEvent.modifierFlags.contains(.shift) { drag.kind = .box; return }
        let node = screen.nodeHit(at: p, grid: grid)
        let edge = node == nil ? screen.hoverEdge(at: p, grid: grid) : nil
        let handle = node != nil ? nil
            : screen.handleHit(at: p, in: screen.handles(selection: model.selection, shapes: model.shapeSelection,
                                                         hover: nil)
                                    + screen.handles(selection: [], hover: edge))
        switch PatchShapePick.target(node: node, onHandle: handle != nil, onEdge: edge != nil) {
        case .node(let id):
            if !model.markedNodes.contains(id) { model.selectShapes([]); model.selection = [id] }
            drag.kind = .nodes(grabbed: id, ids: model.dragNodes)
        case .handle:
            drag.pressedHandle = handle
            drag.kind = .pending
        case .edge:
            drag.pressedEdge = edge
            guard let edge, !model.shapeSelection.isDisjoint(with: PatchShapePick.shapes(onEdge: edge.a, edge.b,
                                                                                         in: screen.doc))
            else { drag.kind = .pending; return }
            drag.kind = .nodes(grabbed: edge.a, ids: model.dragNodes) // a selected shape's line: drag it
        case .empty:
            drag.kind = .pending
        }
    }

    private func ended(_ value: DragGesture.Value, size: CGSize) {
        defer { reset() }
        guard let (screen, grid) = screen(size) else { return }
        let moved = hypot(value.translation.width, value.translation.height) >= Self.clickSlop
        switch drag.kind {
        case .nodes(let grabbed, let ids):
            if model.dragSkip != nil {
                model.lastShapeClick = nil
                model.moveSelection(ids, dlat: drag.dlat, dlon: drag.dlon,
                                    merge: drag.snapTarget.map { (source: grabbed, target: $0) })
            } else if let edge = drag.pressedEdge {
                model.clickEdge(edge.a, edge.b, x: drag.start.x, y: drag.start.y, toggle: false)
            } else if model.selection != [grabbed] || !model.shapeSelection.isEmpty {
                model.selectShapes([])
                model.selection = [grabbed]
            }
        case .box:
            if moved {
                let rect = CGRect(x: min(drag.start.x, value.location.x), y: min(drag.start.y, value.location.y),
                                  width: abs(value.location.x - drag.start.x),
                                  height: abs(value.location.y - drag.start.y))
                model.selection.formUnion(screen.nodes(in: rect, grid: grid))
            } else if let node = screen.nodeHit(at: drag.start, grid: grid) {
                if model.selection.contains(node) { model.selection.remove(node) } else { model.selection.insert(node) }
            } else if let edge = screen.hoverEdge(at: drag.start, grid: grid) {
                model.clickEdge(edge.a, edge.b, x: drag.start.x, y: drag.start.y, toggle: true)
            }
        case .pending:
            if let handle = drag.pressedHandle {
                model.insertNode(handle.edge.a, handle.edge.b)
            } else if let edge = drag.pressedEdge {
                model.clickEdge(edge.a, edge.b, x: drag.start.x, y: drag.start.y, toggle: false)
            } else {
                model.clearSelection()
            }
        case .pan, .idle:
            break
        }
    }

    private func reset() {
        drag.kind = .idle
        drag.snapTarget = nil
        drag.pressedHandle = nil
        drag.pressedEdge = nil
        drag.dlat = 0
        drag.dlon = 0
        if model.dragSkip != nil { model.dragSkip = nil }
    }

    private func pan(_ value: DragGesture.Value, size: CGSize) {
        guard case .pan(let anchor) = drag.kind else { return }
        var cam = anchor
        cam.centerLon = anchor.centerLon - Double(value.translation.width) / anchor.scale
        cam.centerLat = MapCamera.latitude(mercatorY: MapCamera.mercatorY(lat: anchor.centerLat)
                                           + Double(value.translation.height) / anchor.scale)
        cam.clamp(in: size)
        camera.value = cam
    }

    private func hover(_ phase: HoverPhase, size: CGSize) {
        guard drag.kind == .idle else { return }
        var edge: PatchEdgeKey?
        if case .active(let p) = phase, let (screen, grid) = screen(size) { edge = screen.hoverEdge(at: p, grid: grid) }
        if drag.hoverEdge != edge { drag.hoverEdge = edge }
    }

    private static func distance(_ a: CGPoint, _ b: CGPoint) -> Double { hypot(a.x - b.x, a.y - b.y) }

    // MARK: - Drawing

    private func draw(_ screen: PatchEditScreen, selection: Set<Int64>, shapes: Set<Int64>,
                      skip: PatchDragSkip?, in context: GraphicsContext) {
        let doc = screen.doc
        var moving: (grabbed: Int64, ids: Set<Int64>)?
        if case .nodes(let grabbed, let ids) = drag.kind, skip != nil { moving = (grabbed, Set(ids)) }
        func at(_ id: Int64) -> CGPoint? {
            guard let n = doc.nodes[id] else { return nil }
            guard let moving, moving.ids.contains(id) else { return screen.point(n) }
            if id == moving.grabbed, let t = drag.snapTarget, let target = doc.nodes[t] { return screen.point(target) }
            return screen.point(lat: n.lat + drag.dlat, lon: n.lon + drag.dlon)
        }
        // The shapes the drag moves (the base layer skips them).
        if let skip {
            var paths: PatchOverlay.StylePaths = [:]
            for w in skip.ways where w < doc.ways.count {
                let way = doc.ways[w]
                let points = way.refs.compactMap(at)
                guard points.count > 1 else { continue }
                var entry = paths[way.style] ?? (Path(), Path(), Path())
                var outline = Path()
                outline.addLines(points)
                if way.isClosed {
                    outline.closeSubpath()
                    entry.fill.addPath(outline)
                    if way.isBelowGrade { entry.hatch.addPath(outline) }
                }
                entry.stroke.addPath(outline)
                paths[way.style] = entry
            }
            PatchOverlay.paint(paths, phase: PatchOverlay.hatchPhase(screen.camera, size: screen.size), in: context)
        }
        // Selected shapes: the full outline in the selection colour at twice
        // the stroke width, over a light selection tint (#759).
        for way in doc.ways where shapes.contains(way.id) {
            let points = way.refs.compactMap(at)
            guard points.count > 1 else { continue }
            var outline = Path()
            outline.addLines(points)
            if way.isClosed {
                outline.closeSubpath()
                context.fill(outline, with: .color(Self.selectionColor.opacity(0.18)))
            }
            context.stroke(outline, with: .color(Self.selectionColor),
                           style: StrokeStyle(lineWidth: 2 * PatchStyle.of(way.style).width, lineJoin: .round))
        }
        // Selected nodes, and the selected shapes' nodes.
        let bounds = CGRect(origin: .zero, size: screen.size).insetBy(dx: -8, dy: -8)
        var squares = Path()
        for id in selection.union(model.shapeNodes) {
            guard let p = at(id), bounds.contains(p) else { continue }
            squares.addRect(CGRect(x: p.x - 4, y: p.y - 4, width: 8, height: 8))
        }
        context.fill(squares, with: .color(Self.selectionColor))
        context.stroke(squares, with: .color(PatchStyle.nodeFill), lineWidth: 1)
        // The snap highlight.
        if moving != nil, let t = drag.snapTarget, let target = doc.nodes[t] {
            let p = screen.point(target)
            context.stroke(Path(ellipseIn: CGRect(x: p.x - 10, y: p.y - 10, width: 20, height: 20)),
                           with: .color(Self.selectionColor), lineWidth: 2)
        }
        // "+" handles (not during a drag).
        if drag.kind == .idle || drag.kind == .pending {
            for handle in screen.handles(selection: selection, shapes: shapes, hover: drag.hoverEdge) {
                Self.drawHandle(at: handle.point, in: context)
            }
        }
        // The selection box.
        if drag.kind == .box, Self.distance(drag.start, drag.current) >= Self.clickSlop {
            let rect = CGRect(x: min(drag.start.x, drag.current.x), y: min(drag.start.y, drag.current.y),
                              width: abs(drag.current.x - drag.start.x), height: abs(drag.current.y - drag.start.y))
            context.fill(Path(rect), with: .color(.white.opacity(0.08)))
            context.stroke(Path(rect), with: .color(.white.opacity(0.8)),
                           style: StrokeStyle(lineWidth: 1, dash: [4, 3]))
        }
    }

    private static func drawHandle(at p: CGPoint, in context: GraphicsContext) {
        let r: CGFloat = 6
        let circle = Path(ellipseIn: CGRect(x: p.x - r, y: p.y - r, width: 2 * r, height: 2 * r))
        context.fill(circle, with: .color(PatchStyle.nodeFill.opacity(0.85)))
        context.stroke(circle, with: .color(selectionColor), lineWidth: 1.2)
        var plus = Path()
        plus.move(to: CGPoint(x: p.x - 3, y: p.y)); plus.addLine(to: CGPoint(x: p.x + 3, y: p.y))
        plus.move(to: CGPoint(x: p.x, y: p.y - 3)); plus.addLine(to: CGPoint(x: p.x, y: p.y + 3))
        context.stroke(plus, with: .color(.white), lineWidth: 1.4)
    }
}
