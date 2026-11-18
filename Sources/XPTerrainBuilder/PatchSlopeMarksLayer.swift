import SwiftUI
import SceneryKit

// The sloping rectangle on the map (#2137, owner 2026-11-17 15:58Z; Qt's
// `O4_Qt_Patch_Shape_Alt`): the high edge drawn thicker, a large outlined
// arrow in the middle pointing from the high side to the low side, and a
// label at each end against its edge ("High 172.4 m" / "Low 170.9 m"). In
// Edit mode the labels are the edit handles: a click opens a field for that
// side's value. The geometry is `PatchSlopeMarks` (twin of the engine's
// `patch_shape_alt.slope_marks`).

/// One sloping rectangle of the open document, ready to draw.
struct PatchSlopeShape: Sendable, Identifiable {
    let wayID: Int64
    let marks: PatchSlopeMarks
    let high: Double?
    let low: Double?
    var id: Int64 { wayID }

    static func all(in doc: PatchDocument) -> [PatchSlopeShape] {
        doc.ways.compactMap { way in
            guard case .slope(let high, let low, true)? = PatchShapeAltitude(way: way),
                  let marks = PatchSlopeMarks(way: way, in: doc) else { return nil }
            return PatchSlopeShape(wayID: way.id, marks: marks, high: high, low: low)
        }
    }
}

enum PatchSlopeStyle {
    static let highEdgeWidth: CGFloat = 6
    static let arrowLine: CGFloat = 2
    static let line = PatchStyle.hex(0xF2F4F8)
    static let halo = PatchStyle.hex(0x0B0D12, 0.55)

    /// The thick high edge and the outlined arrow, under the labels.
    static func draw(_ slopes: [PatchSlopeShape], camera: MapCamera, in context: GraphicsContext, size: CGSize) {
        func p(_ q: PatchSlopeMarks.LatLon) -> CGPoint { camera.point(lon: q.lon, lat: q.lat, in: size) }
        var edges = Path(), arrows = Path()
        for s in slopes {
            edges.move(to: p(s.marks.highEdge[0]))
            edges.addLine(to: p(s.marks.highEdge[1]))
            arrows.addLines(s.marks.arrow.map(p))
            arrows.closeSubpath()
        }
        let round = StrokeStyle(lineWidth: highEdgeWidth, lineCap: .round)
        context.stroke(edges, with: .color(halo), style: StrokeStyle(lineWidth: highEdgeWidth + 2, lineCap: .round))
        context.stroke(edges, with: .color(line), style: round)
        context.fill(arrows, with: .color(halo.opacity(0.4)))
        context.stroke(arrows, with: .color(halo), style: StrokeStyle(lineWidth: arrowLine + 2, lineJoin: .round))
        context.stroke(arrows, with: .color(line), style: StrokeStyle(lineWidth: arrowLine, lineJoin: .round))
    }
}

/// The end labels; in Edit mode each is a button that edits its side.
struct PatchSlopeLabels: View {
    @ObservedObject var model: PatchEditModel
    @ObservedObject var camera: ViewState<MapCamera>
    let slopes: [PatchSlopeShape]
    @State private var editing: Editing?

    struct Editing: Equatable {
        let way: Int64
        let side: PatchShapeAltitude.Side
    }

    var body: some View {
        GeometryReader { proxy in
            ZStack(alignment: .topLeading) {
                ForEach(slopes) { s in
                    label(s, .high, at: s.marks.highLabel, size: proxy.size)
                    label(s, .low, at: s.marks.lowLabel, size: proxy.size)
                }
            }
        }
    }

    @ViewBuilder
    private func label(_ s: PatchSlopeShape, _ side: PatchShapeAltitude.Side, at q: PatchSlopeMarks.LatLon,
                       size: CGSize) -> some View {
        let point = camera.value.point(lon: q.lon, lat: q.lat, in: size)
        let value = side == .high ? s.high : s.low
        let edits = model.mode == .edit
        Text(PatchShapeAltitude.label(side, value))
            .scaledFont(.caption, weight: side == .high ? .semibold : .regular, monospacedDigit: true)
            .foregroundStyle(.white)
            .padding(.horizontal, 6).padding(.vertical, 2)
            .background(.black.opacity(0.6), in: Capsule())
            .overlay(Capsule().strokeBorder(.white.opacity(edits ? 0.8 : 0.3), lineWidth: 1))
            .fixedSize()
            .position(point)
            .onTapGesture { if edits { editing = Editing(way: s.wayID, side: side) } }
            .allowsHitTesting(edits)
            .help(edits ? "Click to change the \(side == .high ? "high" : "low") side's elevation" : "")
            .popover(isPresented: Binding(get: { editing == Editing(way: s.wayID, side: side) },
                                          set: { if !$0 { editing = nil } })) {
                PatchSlopeValueEditor(side: side, value: value) { v in
                    model.setSlope(s.wayID, side: side, value: v)
                    editing = nil
                }
            }
    }
}

/// The popover a label opens: one value, Return applies.
private struct PatchSlopeValueEditor: View {
    let side: PatchShapeAltitude.Side
    let value: Double?
    let apply: (Double) -> Void
    @State private var text = ""

    var body: some View {
        HStack(spacing: 6) {
            Text(side == .high ? PatchShapeAltitudeBox.highTitle : PatchShapeAltitudeBox.lowTitle)
            TextField(value == nil ? "from the mesh" : "", text: $text)
                .textFieldStyle(.roundedBorder)
                .frame(width: 90)
                .onSubmit { if let v = PatchNodeInspector.number(text) { apply(v) } }
            Text("m").foregroundStyle(.secondary)
        }
        .padding(10)
        .onAppear { text = PatchNodeInspector.metres(value) }
    }
}
