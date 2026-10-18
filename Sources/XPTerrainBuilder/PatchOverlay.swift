import SwiftUI
import SceneryKit

/// A `PatchDocument` projected once into the map's world units (longitude,
/// mercator Y), so a frame is one multiply-add per point. Shapes are kept
/// per way in draw order: L3's drag rebuilds only the moved nodes' shapes.
struct PatchMapGeometry: Sendable {
    struct Shape: Sendable {
        let way: Int
        let style: PatchStyleClass
        let closed: Bool
        /// (lon, mercator Y) per ref.
        let points: [CGPoint]
        let minX, maxX, minY, maxY: Double
    }

    struct Node: Sendable {
        let id: Int64
        let x: Double
        let y: Double
    }

    let shapes: [Shape]
    let nodes: [Node]

    /// Lower first: graded ground under pavement, buildings and roads on top.
    static let drawOrder: [PatchStyleClass] = [.ground, .apron, .taxiway, .runway, .building, .road]

    init(document: PatchDocument) {
        var projected: [Int64: CGPoint] = [:]
        projected.reserveCapacity(document.nodes.count)
        var nodes: [Node] = []
        nodes.reserveCapacity(document.nodes.count)
        for id in document.nodeOrder {
            guard let n = document.nodes[id] else { continue }
            let p = CGPoint(x: n.lon, y: MapCamera.mercatorY(lat: n.lat))
            projected[id] = p
            nodes.append(Node(id: id, x: p.x, y: p.y))
        }
        var shapes: [Shape] = []
        for (w, way) in document.ways.enumerated() {
            let points = way.refs.compactMap { projected[$0] }
            guard points.count > 1 else { continue }
            let xs = points.map(\.x), ys = points.map(\.y)
            shapes.append(Shape(way: w, style: way.style, closed: way.isClosed, points: points,
                                minX: xs.min()!, maxX: xs.max()!, minY: ys.min()!, maxY: ys.max()!))
        }
        let rank = Dictionary(uniqueKeysWithValues: Self.drawOrder.enumerated().map { ($1, $0) })
        self.shapes = shapes.sorted { (rank[$0.style]!, $0.way) < (rank[$1.style]!, $1.way) }
        self.nodes = nodes
    }
}

/// The patch layer over the map (spec §4, mockup
/// `Ortho4XP/docs/mockups/patch-editor-20261015.html`): fills and strokes
/// by role, node squares where nodes are ≥ 6 pt apart, the legend and the
/// bottom-left chip. Its own view, observing only the patch model and the
/// camera, so the base map never redraws for it. Hit-testing is off in
/// View mode; in Edit mode `PatchEditLayer` (PatchEditGestures.swift) sits
/// on top and takes the clicks and drags. Shapes and nodes a drag is moving
/// are skipped here and drawn by that layer.
struct PatchOverlay: View {
    @ObservedObject var model: PatchEditModel
    @ObservedObject var camera: ViewState<MapCamera>
    @Environment(\.undoManager) private var undoManager

    /// Node squares closer than this on screen are thinned out.
    static let nodeSpacing: CGFloat = 6
    /// The road halo's width (×1.5 with the strokes, #759).
    static let haloWidth: CGFloat = 7.5
    static let nodeSize: CGFloat = 6

    var body: some View {
        ZStack {
            layer
            PatchUnsavedPromptCard(model: model)
            PatchKeyCatcher(model: model)
        }
        .onAppear { model.undoManager = undoManager }
        .onChange(of: undoManager) { model.undoManager = undoManager }
    }

    @ViewBuilder
    private var layer: some View {
        if model.isShowing, let geometry = model.geometry, let document = model.document {
            let skip = model.dragSkip
            Canvas(rendersAsynchronously: false) { context, size in
                Self.draw(geometry, camera: camera.value, skip: skip, in: context, size: size)
            }
            .allowsHitTesting(false)
            .background {
                if let outlines = model.build?.packOutlines {
                    PatchPackOutlineLayer(outlines: outlines, camera: camera)
                }
            }
            .overlay {
                if model.mode == .edit { PatchEditLayer(model: model, drag: model.drag, camera: camera) }
            }
            .overlay(alignment: .topTrailing) {
                PatchLegend(outlines: model.build?.packOutlines).padding(.top, 44).padding(.trailing, 8).allowsHitTesting(false)
            }
            .overlay(alignment: .bottomLeading) {
                Text(Self.chipText(document))
                    .font(.system(size: 11, design: .monospaced))
                    .foregroundStyle(.white.opacity(0.75))
                    .padding(.horizontal, 8).padding(.vertical, 3)
                    .background(.black.opacity(0.45), in: RoundedRectangle(cornerRadius: 6))
                    .padding(8)
                    .allowsHitTesting(false)
            }
        }
    }

    /// "KHIO · automatic shape · 4,576 nodes · 392 shapes".
    static func chipText(_ doc: PatchDocument) -> String {
        let source = doc.source == .auto ? "automatic shape"
            : doc.isHandMade ? "hand-made shape" : "edited shape"
        return "\(doc.icao) · \(source) · \(doc.nodes.count.formatted()) nodes · \(doc.ways.count.formatted()) shapes"
    }

    // MARK: - Drawing

    private static func draw(_ geometry: PatchMapGeometry, camera: MapCamera, skip: PatchDragSkip?,
                             in context: GraphicsContext, size: CGSize) {
        let scale = camera.scale
        let cx = camera.centerLon, cy = MapCamera.mercatorY(lat: camera.centerLat)
        let halfW = Double(size.width) / 2 / scale, halfH = Double(size.height) / 2 / scale
        let view = (minX: cx - halfW, maxX: cx + halfW, minY: cy - halfH, maxY: cy + halfH)
        func screen(_ p: CGPoint) -> CGPoint {
            CGPoint(x: size.width / 2 + (p.x - cx) * scale, y: size.height / 2 - (p.y - cy) * scale)
        }

        var paths: [PatchStyleClass: (fill: Path, stroke: Path)] = [:]
        for shape in geometry.shapes {
            if let skip, skip.ways.contains(shape.way) { continue }
            guard shape.maxX >= view.minX, shape.minX <= view.maxX,
                  shape.maxY >= view.minY, shape.minY <= view.maxY else { continue }
            var entry = paths[shape.style] ?? (Path(), Path())
            var outline = Path()
            outline.addLines(shape.points.map(screen))
            if shape.closed {
                outline.closeSubpath()
                entry.fill.addPath(outline)
            }
            entry.stroke.addPath(outline)
            paths[shape.style] = entry
        }
        paint(paths, in: context)
        drawNodes(geometry, view: view, skip: skip?.nodes ?? [], screen: screen, in: context)
    }

    /// Fill and stroke per style class, in draw order (also the edit
    /// layer's moved shapes).
    static func paint(_ paths: [PatchStyleClass: (fill: Path, stroke: Path)], in context: GraphicsContext) {
        for style in PatchMapGeometry.drawOrder {
            guard let entry = paths[style] else { continue }
            let look = PatchStyle.of(style)
            if let fill = look.fill {
                context.fill(entry.fill, with: .color(fill))
            }
            if let halo = look.halo {
                context.stroke(entry.stroke, with: .color(halo), lineWidth: Self.haloWidth)
            }
            context.stroke(entry.stroke, with: .color(look.stroke), lineWidth: look.width)
        }
    }

    /// Small squares, thinned so no two drawn squares are closer than
    /// `nodeSpacing` on screen.
    private static func drawNodes(_ geometry: PatchMapGeometry,
                                  view: (minX: Double, maxX: Double, minY: Double, maxY: Double),
                                  skip: Set<Int64>,
                                  screen: (CGPoint) -> CGPoint, in context: GraphicsContext) {
        let cell = nodeSpacing
        var taken: [Int64: CGPoint] = [:]
        var squares = Path()
        func key(_ i: Int, _ j: Int) -> Int64 { (Int64(i) << 32) | Int64(UInt32(truncatingIfNeeded: j)) }
        for node in geometry.nodes {
            guard node.x >= view.minX, node.x <= view.maxX,
                  node.y >= view.minY, node.y <= view.maxY, !skip.contains(node.id) else { continue }
            let p = screen(CGPoint(x: node.x, y: node.y))
            let i = Int((p.x / cell).rounded(.down)), j = Int((p.y / cell).rounded(.down))
            var clear = true
            search: for di in -1...1 {
                for dj in -1...1 {
                    if let q = taken[key(i + di, j + dj)], hypot(q.x - p.x, q.y - p.y) < cell {
                        clear = false
                        break search
                    }
                }
            }
            guard clear, taken[key(i, j)] == nil else { continue }
            taken[key(i, j)] = p
            let half = nodeSize / 2
            squares.addRect(CGRect(x: p.x - half, y: p.y - half, width: nodeSize, height: nodeSize))
        }
        context.fill(squares, with: .color(PatchStyle.nodeFill))
        context.stroke(squares, with: .color(PatchStyle.nodeStroke), lineWidth: 1.2)
    }
}

/// The mockup's colours per style class.
struct PatchStyle {
    let fill: Color?
    let stroke: Color
    let width: CGFloat
    /// A wide translucent band under the line (roads).
    let halo: Color?

    static func hex(_ rgb: UInt32, _ opacity: Double = 1) -> Color {
        Color(red: Double((rgb >> 16) & 0xFF) / 255, green: Double((rgb >> 8) & 0xFF) / 255,
              blue: Double(rgb & 0xFF) / 255).opacity(opacity)
    }

    static let nodeFill = hex(0x0B0D12)
    static let nodeStroke = hex(0xE7EBF2)

    /// Widths are the mockup's × 1.5 (owner, #759: "increase the line
    /// weight about 50%"); node squares and hit radii are unchanged.
    static func of(_ style: PatchStyleClass) -> PatchStyle {
        switch style {
        case .runway: PatchStyle(fill: hex(0x8A8F99, 0.28), stroke: hex(0xD6DAE2), width: 2.4, halo: nil)
        case .taxiway: PatchStyle(fill: hex(0xD2B14A, 0.22), stroke: hex(0xE6C95C), width: 2.1, halo: nil)
        case .apron: PatchStyle(fill: hex(0x5AA0E0, 0.22), stroke: hex(0x7DB8EF), width: 2.4, halo: nil)
        case .building: PatchStyle(fill: hex(0xB07AD0, 0.25), stroke: hex(0xC497E0), width: 1.95, halo: nil)
        case .road: PatchStyle(fill: hex(0x9FD18B, 0.18), stroke: hex(0x9FD18B), width: 1.8,
                               halo: hex(0x9FD18B, 0.35))
        case .ground: PatchStyle(fill: nil, stroke: hex(0x9AA4B5, 0.55), width: 1.2, halo: nil)
        }
    }

    /// Legend label per class (the mockup's words; "graded ground" is new).
    static func label(_ style: PatchStyleClass) -> String {
        style == .ground ? "graded ground" : style.rawValue
    }
}

private struct PatchLegend: View {
    let outlines: PatchPackOutlines?

    var body: some View {
        VStack(alignment: .leading, spacing: 3) {
            ForEach([PatchStyleClass.runway, .taxiway, .apron, .building, .road, .ground], id: \.self) { style in
                HStack(spacing: 6) {
                    RoundedRectangle(cornerRadius: 2)
                        .fill(PatchStyle.of(style).stroke)
                        .frame(width: 14, height: 8)
                    Text(PatchStyle.label(style))
                }
            }
            if let outlines { PackOutlineLegendRow(outlines: outlines) }
        }
        .font(.caption)
        .foregroundStyle(.white.opacity(0.85))
        .padding(.horizontal, 9).padding(.vertical, 6)
        .background(.black.opacity(0.45), in: RoundedRectangle(cornerRadius: 8))
    }
}

/// The mockup's "pack apt.dat" row: a dashed swatch, shown while the
/// outlines are on.
private struct PackOutlineLegendRow: View {
    @ObservedObject var outlines: PatchPackOutlines

    var body: some View {
        if outlines.enabled {
            HStack(spacing: 6) {
                RoundedRectangle(cornerRadius: 2)
                    .strokeBorder(PatchPackOutlineLayer.stroke,
                                  style: StrokeStyle(lineWidth: 1, dash: [3, 2]))
                    .frame(width: 14, height: 8)
                Text("pack apt.dat")
            }
        }
    }
}
