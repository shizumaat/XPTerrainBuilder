import SwiftUI
import SceneryKit

// A shape's own elevation in the shape inspector (#2137; Qt's
// `O4_Qt_Patch_Shape_Alt`): an Ortho4XP patch way can carry ONE elevation
// for the whole shape (`cst_alt_abs`, `cst_alt_rel`, `var_alt_rel`, the
// legacy `altitude`) or be a sloping rectangle (`altitude_high` /
// `altitude_low`). The box shows the value(s) as editable fields; Return
// writes them back as the same tags, ONE undo step, saved with the patch.
// The words are twin-checked against Qt by `tests/test_qt_layout_parity.py`.

/// The inspector rows for one selected shape's own elevation tags.
struct PatchShapeAltitudeBox: View {
    @ObservedObject var model: PatchEditModel
    let way: PatchWay
    /// Nodes of the shape that carry their own `alt_abs`.
    let nodesWithElevation: Int

    static let levelTitle = "Shape elevation"
    static let meanOffsetTitle = "Above mean ground"
    static let groundOffsetTitle = "Above ground"
    static let slopeTitle = "Sloping rectangle"
    static let highTitle = "High side"
    static let lowTitle = "Low side"

    var body: some View {
        switch PatchShapeAltitude(way: way) {
        case .level(let form, let key, let value)?:
            VStack(alignment: .leading, spacing: 4) {
                PatchAltitudeField(title: Self.title(form), value: value, way: way.id) {
                    model.setShapeLevel(way.id, value: $0)
                }
                note("Tag \(key)" + (form == .absolute ? "" : ": metres added to the ground under the shape."))
                if nodesWithElevation > 0 {
                    note("\(nodesWithElevation.formatted()) nodes carry their own elevation; the build uses theirs.")
                }
            }
        case .slope(let high, let low, let valid)?:
            VStack(alignment: .leading, spacing: 4) {
                Text(Self.slopeTitle).scaledFont(.callout, weight: .semibold)
                PatchAltitudeField(title: Self.highTitle, value: high, way: way.id) {
                    model.setSlope(way.id, side: .high, value: $0)
                }
                PatchAltitudeField(title: Self.lowTitle, value: low, way: way.id) {
                    model.setSlope(way.id, side: .low, value: $0)
                }
                if !valid { note("Not four corners: the build skips this shape.") }
                if (high == nil) != (low == nil) {
                    note("The build takes both sides from the mesh until both are numbers.")
                }
                note("The arrow on the map points downhill; click its labels to edit.")
            }
        case nil:
            EmptyView()
        }
    }

    static func title(_ form: PatchShapeAltitude.Form) -> String {
        switch form {
        case .absolute: levelTitle
        case .meanOffset: meanOffsetTitle
        case .groundOffset: groundOffsetTitle
        }
    }

    private func note(_ text: String) -> some View {
        Text(text).scaledFont(.caption).foregroundStyle(.secondary).fixedSize(horizontal: false, vertical: true)
    }
}

/// One editable value in metres: Return applies it.
struct PatchAltitudeField: View {
    let title: String
    let value: Double?
    let way: Int64
    let apply: (Double) -> Void
    @State private var text = ""

    var body: some View {
        HStack(spacing: 6) {
            Text(title).foregroundStyle(.secondary)
            Spacer()
            TextField(value == nil ? "from the mesh" : "", text: $text)
                .textFieldStyle(.roundedBorder)
                .scaledFont(.callout, monospacedDigit: true)
                .frame(width: 90)
                .onSubmit { if let v = PatchNodeInspector.number(text) { apply(v) } }
            Text("m").foregroundStyle(.secondary)
        }
        .scaledFont(.callout)
        .onAppear { text = PatchNodeInspector.metres(value) }
        .onChange(of: value) { text = PatchNodeInspector.metres(value) }
        .onChange(of: way) { text = PatchNodeInspector.metres(value) }
    }
}

extension PatchEditModel {
    /// Write a shape's whole-shape value under the key it uses (#2137).
    func setShapeLevel(_ wayID: Int64, value: Double) {
        guard let way = document?.ways.first(where: { $0.id == wayID }) else { return }
        perform("Set Shape Elevation") {
            try $0.setWayTags(wayID, put: PatchShapeAltitude.levelTags(way.tags, value: value))
        }
    }

    /// Write one side of a sloping rectangle (#2137).
    func setSlope(_ wayID: Int64, side: PatchShapeAltitude.Side, value: Double) {
        guard let way = document?.ways.first(where: { $0.id == wayID }) else { return }
        let tags = PatchShapeAltitude.slopeTags(way.tags, high: side == .high ? value : nil,
                                                low: side == .low ? value : nil)
        perform(side == .high ? "Set High Side" : "Set Low Side") { try $0.setWayTags(wayID, put: tags) }
    }
}
