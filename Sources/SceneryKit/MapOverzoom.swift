import Foundation

/// Map overzoom past the imagery source's finest level (issue #1315): the
/// Swift half of ONE rule whose Python half (the Qt map's) is
/// `Ortho4XP/src/O4_Map_Overzoom.py`. Both read
/// `Ortho4XP/tests/fixtures/map_overzoom_cases.json`.
///
/// The map zooms to `maxViewZL` whatever the source offers. A view tile
/// finer than the source's `maxZL` is drawn from its deepest available
/// ancestor: `ancestor(z:x:y:maxZ:)` names that tile and the sub-square of
/// it to crop and scale up. No URL above `maxZL` is ever requested, and
/// the zoom badge says "overzoom ×N" (`badgeText`).
public enum MapOverzoom {
    /// The map's zoom ceiling, independent of any imagery source: deep
    /// enough (about 1 cm a pixel) to edit patch nodes at fine scale.
    public static let maxViewZL = 24

    /// The tile `(z, x, y)` that draws a view tile, and the sub-square of
    /// it the view tile covers, as fractions of the ancestor's side: left
    /// `subX`, top `subY`, side `subSize` (1 = the whole tile, when the
    /// view tile is itself available).
    public struct Ancestor: Equatable {
        public let z: Int, x: Int, y: Int
        public let subX: Double, subY: Double, subSize: Double
    }

    /// The tile at `min(z, maxZ)` covering view tile `(z, x, y)`.
    public static func ancestor(z: Int, x: Int, y: Int, maxZ: Int) -> Ancestor {
        let depth = max(0, z - maxZ)
        guard depth > 0 else {
            return Ancestor(z: z, x: x, y: y, subX: 0, subY: 0, subSize: 1)
        }
        let span = Double(1 << depth)
        let ax = x >> depth, ay = y >> depth
        return Ancestor(z: z - depth, x: ax, y: ay,
                        subX: Double(x - (ax << depth)) / span,
                        subY: Double(y - (ay << depth)) / span,
                        subSize: 1 / span)
    }

    /// How many times the source's finest tiles are scaled up (1 = not).
    public static func overzoomFactor(viewZL: Int, maxZL: Int) -> Int {
        1 << max(0, viewZL - maxZL)
    }

    /// The zoom badge: the view's ZL, and past the source's ceiling the
    /// overzoom factor and the ceiling it scales up from.
    public static func badgeText(viewZL: Int, source: String?, maxZL: Int?) -> String {
        guard let maxZL, viewZL > maxZL else { return "ZL \(viewZL)" }
        return "ZL \(viewZL) · overzoom ×\(overzoomFactor(viewZL: viewZL, maxZL: maxZL))"
            + " (\(source ?? "source") max ZL \(maxZL))"
    }

    /// Map scale (screen pixels per degree of longitude) at which one
    /// 256 px tile of zoom `zl` is drawn at screen resolution.
    public static func scale(forZL zl: Int) -> Double {
        256 * pow(2, Double(zl)) / 360
    }
}
