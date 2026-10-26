import SwiftUI

/// The point a coordinate search went to (#1317). It stays on the map
/// until the next search, or until the search field is cleared (Esc or
/// its clear button). The Qt half is `O4_Qt_Reticle.py`.
struct SearchReticle: Equatable {
    let lat: Double
    let lon: Double
}

extension MapCamera {
    /// Pixels per degree at a slippy zoom level: the inverse of the
    /// canvas's `ceil(log2(scale * 360 / 256))`.
    static func pixelsPerDegree(zoomLevel: Int) -> Double {
        256 * pow(2, Double(zoomLevel)) / 360
    }
}

/// Crosshair ring over the searched point: a white stroke on a dark halo,
/// so it reads on imagery and on the plain map alike.
struct SearchReticleOverlay: View {
    @ObservedObject var reticle: ViewState<SearchReticle?>
    @ObservedObject var camera: ViewState<MapCamera>

    static let radius: CGFloat = 14
    static let tick: CGFloat = 9

    var body: some View {
        Canvas { context, size in
            guard let mark = reticle.value else { return }
            let c = camera.value.point(lon: mark.lon, lat: mark.lat, in: size)
            let r = Self.radius, t = Self.tick
            var path = Path(ellipseIn: CGRect(x: c.x - r, y: c.y - r, width: 2 * r, height: 2 * r))
            for (dx, dy) in [(1.0, 0.0), (-1.0, 0.0), (0.0, 1.0), (0.0, -1.0)] {
                path.move(to: CGPoint(x: c.x + dx * (r - t / 2), y: c.y + dy * (r - t / 2)))
                path.addLine(to: CGPoint(x: c.x + dx * (r + t), y: c.y + dy * (r + t)))
            }
            context.stroke(path, with: .color(.black.opacity(0.6)), lineWidth: 4)
            context.stroke(path, with: .color(.white), lineWidth: 2)
        }
        .allowsHitTesting(false)
    }
}
