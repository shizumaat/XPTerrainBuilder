import SwiftUI
import SceneryKit

/// The "Select from flight plan" panel over the map's top-left corner
/// (issue #829; the Qt half is `O4_Qt_Flight_Plan.FlightPlanDialog`). Not a
/// sheet: the map stays live under it, so the selection can be watched
/// while the radius changes. Copy is `FlightPlanCopy`, shared with Qt.
struct FlightPlanPanel: View {
    @ObservedObject var model: FlightPlanSelection
    let frame: ([AirportTile]) -> Void

    var body: some View {
        if model.isShown {
            panel
                .onChange(of: model.loads) { frame(model.tiles) }
        }
    }

    private var panel: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(FlightPlanCopy.menuTitle.replacingOccurrences(of: "\u{2026}", with: ""))
                .font(.headline)
            Button(FlightPlanCopy.openButton) { model.openFile() }
            HStack {
                TextField(FlightPlanCopy.simBriefPlaceholder, text: $model.simBriefUser)
                    .textFieldStyle(.roundedBorder)
                    .onSubmit { model.fetchSimBrief() }
                Button(FlightPlanCopy.simBriefButton) { model.fetchSimBrief() }
                    .disabled(model.isFetching
                              || model.simBriefUser.trimmingCharacters(in: .whitespaces).isEmpty)
            }
            Text(FlightPlanCopy.simBriefNote)
                .font(.caption)
                .foregroundStyle(.secondary)
            if model.isFetching {
                ProgressView().controlSize(.small)
            }
            if let error = model.errorMessage {
                Text(error).foregroundStyle(.red).fixedSize(horizontal: false, vertical: true)
            } else if let summary = model.summary {
                Text(summary)
            }
            HStack {
                Text(FlightPlanCopy.radiusLabel)
                Slider(value: $model.radius, in: 0...model.radiusMax, step: 1)
                    .frame(minWidth: 120)
                Text("\(Int(model.radius))")
                    .monospacedDigit()
                    .frame(minWidth: 30, alignment: .trailing)
                Picker("", selection: $model.unit) {
                    ForEach(FlightPlanCopy.units, id: \.self) { Text($0).tag($0) }
                }
                .labelsHidden()
                .fixedSize()
                Text(FlightPlanCopy.ofRouteLabel)
            }
            if model.plan != nil {
                Text(RouteTiles.tilesText(model.tiles.count))
                    .foregroundStyle(.secondary)
            }
            HStack {
                Spacer()
                Button("Cancel", role: .cancel) { model.cancel() }
                    .keyboardShortcut(.cancelAction)
                Button("Select") { model.select() }
                    .keyboardShortcut(.defaultAction)
                    .disabled(model.plan == nil)
            }
        }
        .padding(12)
        .frame(width: 440, alignment: .leading)
        .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 10))
        .shadow(radius: 6)
        .padding(.top, 8)
        .padding(.leading, 12)
    }
}

/// The route on the map while the panel is open: magenta polylines (the
/// map's own magenta), its own view so the base map never redraws for it.
struct FlightRouteOverlay: View {
    @ObservedObject var model: FlightPlanSelection
    @ObservedObject var camera: ViewState<MapCamera>

    var body: some View {
        Canvas { context, size in
            let cam = camera.value
            var path = Path()
            for part in model.drawing {
                guard let first = part.first else { continue }
                path.move(to: cam.point(lon: first.lon, lat: first.lat, in: size))
                for p in part.dropFirst() {
                    path.addLine(to: cam.point(lon: p.lon, lat: p.lat, in: size))
                }
            }
            context.stroke(path, with: .color(MapCanvasView.magenta), lineWidth: 2.5)
        }
        .allowsHitTesting(false)
    }
}
