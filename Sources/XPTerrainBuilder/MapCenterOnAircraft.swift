import SwiftUI
import SceneryKit

/// The map's "Center on aircraft" button, beside the zoom controls
/// (#2016): pans to the aircraft Fly's watch last reported and keeps the
/// zoom. Disabled, with `FlyText.noAircraftPosition` as its help, while no
/// position is current (`FlyText.aircraftIsCurrent`). Its own view so the
/// once-a-second position redraws only this button. Qt:
/// `O4_Qt_Map_Controls.MapControls.center_btn`.
struct CenterOnAircraftButton: View {
    @ObservedObject var model: FlyModel
    @ObservedObject var camera: ViewState<MapCamera>
    @ObservedObject var canvasSize: ViewState<CGSize>

    var body: some View {
        // Re-checked every second: X-Plane going quiet sends nothing.
        TimelineView(.periodic(from: .now, by: 1)) { timeline in
            let current = FlyText.aircraftIsCurrent(seenAt: model.positionAt, now: timeline.date)
            Button(action: center) {
                Image(systemName: "location")
                    .frame(width: 30, height: 24)
                    .contentShape(Rectangle())
            }
            .disabled(!current)
            .help(current ? FlyText.centerOnAircraft : FlyText.noAircraftPosition)
            .accessibilityLabel(FlyText.centerOnAircraft)
        }
    }

    private func center() {
        guard let position = model.position else { return }
        camera.value = Self.centered(camera.value, lat: position.lat, lon: position.lon,
                                     in: canvasSize.value)
    }

    /// `cam` panned to `(lat, lon)`, its zoom kept (clamped to the world).
    static func centered(_ cam: MapCamera, lat: Double, lon: Double, in size: CGSize) -> MapCamera {
        var cam = cam
        cam.centerLat = lat
        cam.centerLon = lon
        cam.clamp(in: size)
        return cam
    }
}
